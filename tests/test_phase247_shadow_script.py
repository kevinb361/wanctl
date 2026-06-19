from __future__ import annotations

import importlib.util
import io
import json
import sys
import threading
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "phase247-fping-shadow.py"


def load_module():
    if not SCRIPT.exists():
        pytest.skip("phase247 shadow script not present yet")
    spec = importlib.util.spec_from_file_location("phase247_fping_shadow", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def module():
    return load_module()


@pytest.fixture
def config_path(tmp_path: Path) -> Path:
    path = tmp_path / "spectrum.yaml"
    path.write_text(
        "ping_source_ip: 10.10.110.223\n"
        "continuous_monitoring:\n"
        "  ping_hosts: ['1.1.1.1', '9.9.9.9', '208.67.222.222']\n",
        encoding="utf-8",
    )
    return path


class FakeThread:
    def __init__(self, samples=None, stats=None):
        self.samples = list(samples or [])
        self.stats = stats or {"count": 3, "p99_ms": 9.9, "samples": [1, 2, 3]}
        self.started = False
        self.stopped = False

    def start(self):
        self.started = True

    def stop(self):
        self.stopped = True

    def get_latest(self):
        if self.samples:
            return self.samples.pop(0)
        return None

    def get_profile_stats(self):
        return dict(self.stats)


class FakeClock:
    def __init__(self, values):
        self.values = list(values)
        self.last = self.values[-1] if self.values else 0.0

    def __call__(self):
        if self.values:
            self.last = self.values.pop(0)
        return self.last


def sample(
    *,
    timestamp=1.0,
    measurement_ms=42.5,
    rtt_ms=15.3,
    successful_hosts=("1.1.1.1",),
    active_hosts=("1.1.1.1", "9.9.9.9"),
):
    return SimpleNamespace(
        timestamp=timestamp,
        measurement_ms=measurement_ms,
        rtt_ms=rtt_ms,
        successful_hosts=successful_hosts,
        active_hosts=active_hosts,
        per_host_results={"1.1.1.1": 15.3, "9.9.9.9": None},
        per_host_loss={"1.1.1.1": 0.0, "9.9.9.9": 100.0},
        backend="fping",
    )


def run_loop(module, *, samples=None, stats_interval=100, clock=None, max_polls=None):
    out = io.StringIO()
    probe_count = module.run_capture_loop(
        thread=FakeThread(samples=samples),
        fh=out,
        shutdown=threading.Event(),
        source_ip="10.10.110.223",
        reflectors=["1.1.1.1", "9.9.9.9"],
        config_path=Path("/opt/wanctl/configs/spectrum.yaml"),
        cadence_sec=10.0,
        count=5,
        period_ms=200,
        timeout_grace_sec=2.0,
        stats_interval=stats_interval,
        now_fn=clock or (lambda: 1000.0),
        max_polls=max_polls if max_polls is not None else len(samples or []),
    )
    records = [json.loads(line) for line in out.getvalue().splitlines()]
    return probe_count, records


class TestConfigLoading:
    def test_config_loading_extracts_reflectors(self, module, config_path: Path):
        cfg = module.load_spectrum_config(config_path)
        assert cfg["ping_source_ip"] == "10.10.110.223"
        assert cfg["continuous_monitoring"]["ping_hosts"] == ["1.1.1.1", "9.9.9.9", "208.67.222.222"]

    def test_config_loading_missing_section_raises(self, module, tmp_path: Path):
        path = tmp_path / "bad.yaml"
        path.write_text("ping_source_ip: 10.10.110.223\n", encoding="utf-8")
        with pytest.raises(ValueError, match="continuous_monitoring"):
            module.load_spectrum_config(path)

    def test_config_loading_missing_source_ip_raises(self, module, tmp_path: Path):
        path = tmp_path / "bad.yaml"
        path.write_text("continuous_monitoring:\n  ping_hosts: ['1.1.1.1']\n", encoding="utf-8")
        with pytest.raises(ValueError, match="ping_source_ip"):
            module.load_spectrum_config(path)

    def test_cake_autorate_shell_config_extracts_reflectors_and_source(self, module, tmp_path: Path):
        path = tmp_path / "config.spectrum.sh"
        path.write_text(
            'ping_extra_args="-S 10.10.110.223"\n'
            'reflectors=("8.8.8.8" "9.9.9.9" "208.67.222.222")\n',
            encoding="utf-8",
        )
        cfg = module.load_spectrum_config(path)
        assert cfg["ping_source_ip"] == "10.10.110.223"
        assert cfg["continuous_monitoring"]["ping_hosts"] == ["8.8.8.8", "9.9.9.9", "208.67.222.222"]


class TestSourceIpMapping:
    def test_source_ip_key_mapping(self, module, config_path: Path, monkeypatch):
        constructed = {}

        class FakeMeasurement:
            def __init__(self, cfg, logger):
                constructed.update(cfg)

            def is_available(self):
                return False

        monkeypatch.setattr(module, "FpingMeasurement", FakeMeasurement)
        rc = module.main(["--config", str(config_path)])
        assert rc == 1
        assert constructed["source_ip"] == "10.10.110.223"
        assert "ping_source_ip" not in constructed
        assert constructed["count"] == 5
        assert constructed["period_ms"] == 200


class TestRunStartRecord:
    def test_run_start_record_written(self, module):
        _, records = run_loop(module, samples=[], max_polls=0)
        first = records[0]
        assert first["type"] == "run_start"
        assert first["source_ip"] == "10.10.110.223"
        assert first["reflectors"] == ["1.1.1.1", "9.9.9.9"]
        assert first["config_path"] == "/opt/wanctl/configs/spectrum.yaml"
        assert isinstance(first["script_version"], str)
        assert first["cadence_sec"] == 10.0
        assert first["count"] == 5
        assert first["period_ms"] == 200
        assert first["timeout_grace_sec"] == 2.0


class TestProbeCycleRecords:
    def test_probe_cycle_record_on_new_sample(self, module):
        _, records = run_loop(module, samples=[sample(timestamp=2.0)])
        record = records[1]
        assert record["type"] == "probe_cycle"
        assert isinstance(record["ts"], float)
        assert record["sample_monotonic_ts"] == 2.0
        assert record["probe_index"] == 1
        assert record["elapsed_ms"] == 42.5
        assert record["rtt_ms"] == 15.3
        assert record["success"] is True
        assert record["all_loss"] is False
        assert record["inferred"] is False
        assert record["reflector_count"] == 2
        assert record["source_ip"] == "10.10.110.223"

    def test_probe_cycle_includes_per_host_fields(self, module):
        _, records = run_loop(module, samples=[sample()])
        record = records[1]
        assert record["per_host_results"] == {"1.1.1.1": 15.3, "9.9.9.9": None}
        assert record["per_host_loss"] == {"1.1.1.1": 0.0, "9.9.9.9": 100.0}
        assert record["active_hosts"] == ["1.1.1.1", "9.9.9.9"]
        assert record["successful_hosts"] == ["1.1.1.1"]

    def test_probe_cycle_uses_measurement_ms(self, module):
        _, records = run_loop(module, samples=[sample(measurement_ms=123.4)])
        assert records[1]["elapsed_ms"] == 123.4

    def test_successful_record_has_real_elapsed_and_inferred_false(self, module):
        _, records = run_loop(module, samples=[sample(measurement_ms=33.0)])
        assert isinstance(records[1]["elapsed_ms"], float)
        assert records[1]["inferred"] is False

    def test_probe_cycle_probe_index_increments(self, module):
        samples = [sample(timestamp=1.0), sample(timestamp=2.0), sample(timestamp=3.0)]
        _, records = run_loop(module, samples=samples)
        cycles = [record for record in records if record["type"] == "probe_cycle"]
        assert [record["probe_index"] for record in cycles] == [1, 2, 3]

    def test_failed_cycle_logged_as_probe_cycle(self, module):
        failed = sample(timestamp=4.0, successful_hosts=(), active_hosts=("1.1.1.1", "9.9.9.9"))
        _, records = run_loop(module, samples=[failed])
        record = records[1]
        assert record["success"] is False
        assert record["all_loss"] is True
        assert record["inferred"] is False
        assert record["elapsed_ms"] == 42.5

    def test_duplicate_sample_suppressed(self, module):
        repeated = sample(timestamp=5.0)
        _, records = run_loop(module, samples=[repeated, repeated], max_polls=2)
        cycles = [record for record in records if record["type"] == "probe_cycle"]
        assert len(cycles) == 1


class TestInferredDroppedRecords:
    def test_inferred_dropped_record_has_null_elapsed_and_rtt(self, module):
        clock = FakeClock([0.0, 0.0, 13.1, 13.1])
        _, records = run_loop(module, samples=[None], clock=clock, max_polls=1)
        record = records[1]
        assert record["elapsed_ms"] is None
        assert record["rtt_ms"] is None
        assert record["inferred"] is True
        assert record["dropped"] is True
        assert record["reason"] == "no_new_sample_within_cadence"
        assert isinstance(record["expected_probe_index"], int)

    def test_inferred_dropped_record_schema_exact(self, module):
        clock = FakeClock([0.0, 0.0, 13.1, 13.1])
        _, records = run_loop(module, samples=[None], clock=clock, max_polls=1)
        record = records[1]
        assert set(record) == {
            "type",
            "success",
            "all_loss",
            "dropped",
            "inferred",
            "elapsed_ms",
            "rtt_ms",
            "reason",
            "expected_probe_index",
            "ts",
            "source_ip",
        }
        assert record["type"] == "probe_cycle"
        assert record["success"] is False
        assert record["all_loss"] is True


class TestProbeStats:
    def test_probe_stats_logged_at_interval(self, module):
        samples = [sample(timestamp=idx) for idx in range(1, 7)]
        _, records = run_loop(module, samples=samples, stats_interval=3)
        stats = [record for record in records if record["type"] == "probe_stats"]
        assert len(stats) == 2

    def test_probe_stats_excludes_samples_key(self, module):
        _, records = run_loop(module, samples=[sample()], stats_interval=1)
        stats = [record for record in records if record["type"] == "probe_stats"]
        assert stats
        assert "samples" not in stats[0]

    def test_probe_stats_has_cumulative_count(self, module):
        samples = [sample(timestamp=idx) for idx in range(1, 7)]
        _, records = run_loop(module, samples=samples, stats_interval=3)
        stats = [record for record in records if record["type"] == "probe_stats"]
        assert [record["probe_count_at_snapshot"] for record in stats] == [3, 6]


class TestShutdown:
    def test_shutdown_writes_final_stats(self, module):
        _, records = run_loop(module, samples=[sample()], stats_interval=100)
        assert records[-1]["type"] == "probe_stats_final"
        assert records[-1]["probe_count_at_snapshot"] == 1


class TestNdjsonIntegrity:
    def test_ndjson_lines_are_valid_json(self, module):
        _, records = run_loop(module, samples=[sample(timestamp=1.0), sample(timestamp=2.0)], stats_interval=1)
        assert records
        assert all(isinstance(record, dict) for record in records)


class TestCLI:
    def test_help_exits_zero(self, module):
        with pytest.raises(SystemExit) as excinfo:
            module.main(["--help"])
        assert excinfo.value.code == 0

    def test_main_exits_one_when_fping_unavailable(self, module, config_path: Path, monkeypatch):
        measurement = Mock()
        measurement.is_available.return_value = False
        monkeypatch.setattr(module, "FpingMeasurement", Mock(return_value=measurement))
        assert module.main(["--config", str(config_path)]) == 1
