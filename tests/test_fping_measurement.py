from __future__ import annotations

import logging
import subprocess
from pathlib import Path
from unittest.mock import Mock, patch

from wanctl.fping_measurement import FpingMeasurement


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
