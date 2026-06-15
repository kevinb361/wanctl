from __future__ import annotations

import logging
import subprocess
import threading
import time
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from wanctl.fping_measurement import FpingMeasurement, FpingThread
from wanctl.reflector_scorer import ReflectorScorer

FIXTURES = Path(__file__).parent / "fixtures" / "fping"


def _backend(tmp_path: Path, **overrides: object) -> FpingMeasurement:
    config: dict[str, object] = {
        "source_ip": "10.0.0.2",
        "count": 5,
        "period_ms": 200,
        "timeout_grace_sec": 2.0,
    }
    config.update(overrides)
    with (
        patch("wanctl.fping_measurement.shutil.which", return_value="/usr/bin/fping"),
        patch.dict("os.environ", {"WANCTL_RUN_DIR": str(tmp_path)}),
    ):
        return FpingMeasurement(config, logging.getLogger("test_fping_measurement"))


def _completed(stdout: str = "", stderr: str = "", returncode: int = 0) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(
        args=["/usr/bin/fping"], returncode=returncode, stdout=stdout, stderr=stderr
    )


def test_build_command_uses_resolved_binary(tmp_path: Path) -> None:
    with (
        patch("wanctl.fping_measurement.shutil.which", return_value="/opt/fake/fping"),
        patch.dict("os.environ", {"WANCTL_RUN_DIR": str(tmp_path)}),
    ):
        fping = FpingMeasurement(
            {"source_ip": "192.0.2.10", "count": 5, "period_ms": 200},
            logging.getLogger("test_fping_measurement"),
        )

    assert fping._build_command(["198.51.100.10"])[0] == fping._binary_path
    assert fping._build_command(["198.51.100.10"])[1:] == [
        "-C",
        "5",
        "-p",
        "200",
        "-q",
        "-S",
        "192.0.2.10",
        "198.51.100.10",
    ]


def test_dash_token_never_zero(tmp_path: Path) -> None:
    fping = _backend(tmp_path)
    parsed = fping._parse_fping("198.51.100.10 : 91.7 - 29.2 - 36.8", ["198.51.100.10"])

    assert parsed.per_host_results["198.51.100.10"] == 36.8
    assert parsed.per_host_loss["198.51.100.10"] == 40.0
    assert all(rtt > 0.0 for rtt in parsed.successful_rtts)


def test_total_loss_parse_result_is_not_none(tmp_path: Path) -> None:
    fping = _backend(tmp_path)
    parsed = fping._parse_fping(
        "198.51.100.10 : - - - - -\n198.51.100.11 : - - - - -",
        ["198.51.100.10", "198.51.100.11"],
    )

    assert parsed.successful_rtts == []
    assert parsed.per_host_results == {"198.51.100.10": None, "198.51.100.11": None}
    assert parsed.per_host_loss == {"198.51.100.10": 100.0, "198.51.100.11": 100.0}
    assert parsed.observed_hosts == ["198.51.100.10", "198.51.100.11"]


def test_stderr_only_valid_output(tmp_path: Path) -> None:
    fping = _backend(tmp_path)
    with patch("wanctl.fping_measurement.subprocess.run", return_value=_completed(stderr="198.51.100.10 : 10.0 11.0 12.0 13.0 14.0")):
        sample = fping.probe(["198.51.100.10"])

    assert sample is not None
    assert sample.backend == "fping"
    assert sample.source_ip == "10.0.0.2"
    assert sample.per_host_results["198.51.100.10"] == 12.0


def test_nonzero_exit_loss_is_parsed(tmp_path: Path) -> None:
    fping = _backend(tmp_path)
    stdout = "198.51.100.10 : 10.0 - 12.0 13.0 14.0"
    with patch("wanctl.fping_measurement.subprocess.run", return_value=_completed(stdout=stdout, returncode=1)):
        sample = fping.probe(["198.51.100.10"])

    assert sample is not None
    assert sample.per_host_loss["198.51.100.10"] == 20.0


def test_negative_returncode_is_process_death(tmp_path: Path) -> None:
    scorer = Mock()
    fping = _backend(tmp_path, scorer=scorer)
    stdout = "198.51.100.10 : 10.0 11.0 12.0 13.0 14.0"
    with patch("wanctl.fping_measurement.subprocess.run", return_value=_completed(stdout=stdout, returncode=-15)):
        sample = fping.probe(["198.51.100.10"])

    assert sample is None
    scorer.record_results.assert_not_called()


def test_returncode_gt2_no_scorer_feed(tmp_path: Path) -> None:
    scorer = Mock()
    fping = _backend(tmp_path, scorer=scorer)
    stdout = "198.51.100.10 : 10.0 11.0 12.0 13.0 14.0"
    with patch("wanctl.fping_measurement.subprocess.run", return_value=_completed(stdout=stdout, returncode=3)):
        sample = fping.probe(["198.51.100.10"])

    assert sample is None
    scorer.record_results.assert_not_called()


def test_unmeasured_host_not_scored(tmp_path: Path) -> None:
    scorer = Mock()
    fping = _backend(tmp_path, scorer=scorer)
    stdout = "198.51.100.10 : 10.0 11.0 12.0 13.0 14.0\ngarbled line"
    with patch("wanctl.fping_measurement.subprocess.run", return_value=_completed(stdout=stdout)):
        sample = fping.probe(["198.51.100.10", "198.51.100.11"])

    assert sample is not None
    scorer.record_results.assert_called_once_with({"198.51.100.10": True})


def test_unknown_host_line_ignored(tmp_path: Path) -> None:
    scorer = Mock()
    fping = _backend(tmp_path, scorer=scorer)
    stdout = "203.0.113.99 : 1.0 1.0 1.0 1.0 1.0\n198.51.100.10 : 10.0 11.0 12.0 13.0 14.0"
    with patch("wanctl.fping_measurement.subprocess.run", return_value=_completed(stdout=stdout)):
        sample = fping.probe(["198.51.100.10"])

    assert sample is not None
    assert "203.0.113.99" not in sample.per_host_results
    scorer.record_results.assert_called_once_with({"198.51.100.10": True})


def test_measurement_ms_recorded(tmp_path: Path) -> None:
    fping = _backend(tmp_path)
    stdout = "198.51.100.10 : 10.0 11.0 12.0 13.0 14.0"
    with patch("wanctl.fping_measurement.subprocess.run", return_value=_completed(stdout=stdout)):
        sample = fping.probe(["198.51.100.10"])

    assert sample is not None
    assert sample.measurement_ms > 0.0


def test_timeout_expired_returns_none_then_recovers(tmp_path: Path) -> None:
    fping = _backend(tmp_path)
    good = _completed(stdout="198.51.100.10 : 10.0 11.0 12.0 13.0 14.0")
    with patch(
        "wanctl.fping_measurement.subprocess.run",
        side_effect=[subprocess.TimeoutExpired(cmd=["fping"], timeout=3.0), good],
    ):
        assert fping.probe(["198.51.100.10"]) is None
        assert fping.probe(["198.51.100.10"]) is not None


def test_process_death_fixture_returns_none(tmp_path: Path) -> None:
    fping = _backend(tmp_path)
    with patch(
        "wanctl.fping_measurement.subprocess.run",
        return_value=_completed(stdout="", stderr="", returncode=-15),
    ):
        assert fping.probe(["198.51.100.10"]) is None


def test_fping_thread_caches_latest_success_and_skips_none(tmp_path: Path) -> None:
    shutdown = threading.Event()
    measurement = Mock()
    first = _backend(tmp_path)._parse_fping(
        "198.51.100.10 : 10.0 11.0 12.0 13.0 14.0", ["198.51.100.10"]
    )
    sample = Mock(name="sample")
    measurement._timeout = 0.01
    measurement.probe.side_effect = [sample, None]

    thread = FpingThread(
        measurement=measurement,
        hosts_fn=lambda: ["198.51.100.10"],
        cadence_sec=0.05,
        shutdown_event=shutdown,
        logger=logging.getLogger("test_fping_measurement"),
    )

    assert first.observed_hosts == ["198.51.100.10"]
    thread.start()
    time.sleep(0.12)
    shutdown.set()
    thread.stop()

    assert thread.get_latest() is sample
    assert measurement.probe.call_count >= 2


def test_timeout_must_be_less_than_cadence(tmp_path: Path) -> None:
    measurement = _backend(tmp_path)
    with pytest.raises(ValueError, match="timeout .* cadence"):
        FpingThread(
            measurement=measurement,
            hosts_fn=lambda: ["198.51.100.10"],
            cadence_sec=measurement._timeout,
            shutdown_event=threading.Event(),
            logger=logging.getLogger("test_fping_measurement"),
        )


def test_dash_token_never_zero_from_fixture(tmp_path: Path) -> None:
    fping = _backend(tmp_path)
    stdout = (FIXTURES / "partial_loss.txt").read_text()
    with patch("wanctl.fping_measurement.subprocess.run", return_value=_completed(stdout=stdout, returncode=1)):
        sample = fping.probe(["198.51.100.10", "198.51.100.11"])

    assert sample is not None
    assert all(value is None or value > 0.0 for value in sample.per_host_results.values())
    assert sample.per_host_loss == {"198.51.100.10": 20.0, "198.51.100.11": 20.0}


def test_all_fail_feeds_scorer(tmp_path: Path) -> None:
    hosts = ["198.51.100.10", "198.51.100.11"]
    real_scorer = ReflectorScorer(hosts, wan_name="test")
    scorer_spy = Mock(wraps=real_scorer)
    fping = _backend(tmp_path, scorer=scorer_spy)
    stdout = (FIXTURES / "total_loss.txt").read_text()

    with patch("wanctl.fping_measurement.subprocess.run", return_value=_completed(stdout=stdout, returncode=1)):
        sample = fping.probe(hosts)

    assert sample is None
    scorer_spy.record_results.assert_called_once_with({"198.51.100.10": False, "198.51.100.11": False})


def test_unmeasured_host_not_scored_from_fixture(tmp_path: Path) -> None:
    scorer = Mock()
    fping = _backend(tmp_path, scorer=scorer)
    stdout = (FIXTURES / "partial_line.txt").read_text()

    with patch("wanctl.fping_measurement.subprocess.run", return_value=_completed(stdout=stdout, returncode=1)):
        sample = fping.probe(["198.51.100.10", "198.51.100.11"])

    assert sample is not None
    assert sample.per_host_loss["198.51.100.11"] is None
    scorer.record_results.assert_called_once_with({"198.51.100.10": True})


def test_exact_aggregation_1_2_3(tmp_path: Path) -> None:
    fping = _backend(tmp_path)
    one = "198.51.100.10 : 10.0 - - - -"
    two = "198.51.100.10 : 10.0 - - - -\n198.51.100.11 : 20.0 - - - -"
    three = (
        "198.51.100.10 : 10.0 - - - -\n"
        "198.51.100.11 : 20.0 - - - -\n"
        "198.51.100.12 : 100.0 - - - -"
    )

    with patch("wanctl.fping_measurement.subprocess.run", return_value=_completed(stdout=one, returncode=1)):
        sample_one = fping.probe(["198.51.100.10"])
    with patch("wanctl.fping_measurement.subprocess.run", return_value=_completed(stdout=two, returncode=1)):
        sample_two = fping.probe(["198.51.100.10", "198.51.100.11"])
    with patch("wanctl.fping_measurement.subprocess.run", return_value=_completed(stdout=three, returncode=1)):
        sample_three = fping.probe(["198.51.100.10", "198.51.100.11", "198.51.100.12"])

    assert sample_one is not None and sample_one.rtt_ms == 10.0
    assert sample_two is not None and sample_two.rtt_ms == 15.0
    assert sample_three is not None and sample_three.rtt_ms == 20.0


def test_reply_fixture_loss_zero(tmp_path: Path) -> None:
    fping = _backend(tmp_path)
    stdout = (FIXTURES / "reply.txt").read_text()

    with patch("wanctl.fping_measurement.subprocess.run", return_value=_completed(stdout=stdout)):
        sample = fping.probe(["198.51.100.10", "198.51.100.11", "198.51.100.12"])

    assert sample is not None
    assert sample.rtt_ms == 22.0
    assert sample.per_host_loss == {
        "198.51.100.10": 0.0,
        "198.51.100.11": 0.0,
        "198.51.100.12": 0.0,
    }


def test_banner_noise_ignored(tmp_path: Path) -> None:
    fping = _backend(tmp_path)
    stdout = (FIXTURES / "banner_noise.txt").read_text()

    with patch("wanctl.fping_measurement.subprocess.run", return_value=_completed(stdout=stdout, returncode=1)):
        sample = fping.probe(["198.51.100.10", "198.51.100.11"])

    assert sample is not None
    assert sample.per_host_results == {"198.51.100.10": 12.0, "198.51.100.11": 22.5}
    assert sample.per_host_loss == {"198.51.100.10": 0.0, "198.51.100.11": 20.0}


def test_process_death_fixture_empty_output_returns_none(tmp_path: Path) -> None:
    fping = _backend(tmp_path)
    stdout = (FIXTURES / "process_death.txt").read_text()

    with patch("wanctl.fping_measurement.subprocess.run", return_value=_completed(stdout=stdout, returncode=-15)):
        assert fping.probe(["198.51.100.10"]) is None


def test_scorer_feed_shape(tmp_path: Path) -> None:
    fping = _backend(tmp_path)
    parsed = fping._parse_fping(
        (FIXTURES / "partial_loss.txt").read_text(), ["198.51.100.10", "198.51.100.11"]
    )

    assert fping._scorer_results(parsed) == {"198.51.100.10": False, "198.51.100.11": False}
