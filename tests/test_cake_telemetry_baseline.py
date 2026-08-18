from __future__ import annotations

import copy
import io
import json
import runpy
import subprocess
import sys
import urllib.parse
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "cake_telemetry_baseline.py"


def _load() -> dict[str, Any]:
    return runpy.run_path(str(SCRIPT))


def _coverage_matrices(namespace: dict[str, Any], timestamps: list[int]) -> dict[str, Any]:
    return {
        name: {(wan,): {timestamp: value for timestamp in timestamps} for wan in namespace["WANS"]}
        for name, value in (
            ("stats_up", 1.0),
            ("probe_up", 1.0),
            ("stats_age_seconds", 1.0),
        )
    }


def _complete_matrices(namespace: dict[str, Any]) -> tuple[dict[str, Any], list[int]]:
    base = datetime(2026, 1, 1, tzinfo=UTC)
    hour_utilization = {
        1: 0.05,
        3: 0.20,
        5: 0.80,
        7: 0.05,
        12: 0.20,
        17: 0.80,
        19: 0.05,
        21: 0.20,
        23: 0.80,
    }
    timestamp_utilization = {
        int((base + timedelta(days=day, hours=hour)).timestamp()): utilization
        for day in range(12)
        for hour, utilization in hour_utilization.items()
    }
    timestamps = sorted(timestamp_utilization)
    matrices = _coverage_matrices(namespace, timestamps)
    matrices["rtt_delta_seconds"] = {
        (wan,): {timestamp: 0.01 + index / 1000 for index, timestamp in enumerate(timestamps)}
        for wan in namespace["WANS"]
    }
    matrices["probe_rtt_seconds"] = {
        (wan,): {timestamp: 0.02 + index / 1000 for index, timestamp in enumerate(timestamps)}
        for wan in namespace["WANS"]
    }
    matrices["shaped_rate_bps"] = {}
    matrices["throughput_bps"] = {}
    for name in namespace["CONGESTION_FRACTION_DIMENSIONS"]:
        matrices[name] = {}
    for wan in namespace["WANS"]:
        for direction in namespace["DIRECTIONS"]:
            matrices["shaped_rate_bps"][(wan, direction)] = {
                timestamp: 100_000_000.0 for timestamp in timestamps
            }
            matrices["throughput_bps"][(wan, direction)] = {
                timestamp: 100_000_000.0 * timestamp_utilization[timestamp]
                for timestamp in timestamps
            }
            for name, fraction in (
                ("congestion_green_fraction", 0.5),
                ("congestion_yellow_or_soft_red_fraction", 0.3),
                ("congestion_red_fraction", 0.2),
                ("congestion_unknown_fraction", 0.0),
            ):
                matrices[name][(wan, direction)] = {timestamp: fraction for timestamp in timestamps}
    for name in (
        "tin_average_delay_seconds",
        "tin_peak_delay_seconds",
        "tin_backlog_bytes",
        "tin_drop_rate",
        "tin_ecn_rate",
        "tin_resets_total",
    ):
        matrices[name] = {}
        for wan in namespace["WANS"]:
            for direction in namespace["DIRECTIONS"]:
                for tin_index, tin in enumerate(namespace["TINS"], start=1):
                    matrices[name][(wan, direction, tin)] = {
                        timestamp: (
                            0.0 if name == "tin_resets_total" else float(tin_index + sample_index)
                        )
                        for sample_index, timestamp in enumerate(timestamps)
                    }
    return matrices, timestamps


@pytest.mark.parametrize("value", ["not-a-time", "2026-01-01T00:00:00"])
def test_timestamp_parser_rejects_invalid_or_naive_values(value: str) -> None:
    namespace = _load()

    with pytest.raises(namespace["BaselineError"]):
        namespace["parse_timestamp"](value)


def test_range_query_builds_bounded_http_matrix_request(monkeypatch: pytest.MonkeyPatch) -> None:
    namespace = _load()
    start = datetime(2026, 1, 1, tzinfo=UTC)
    end = start + timedelta(days=14)
    captured: dict[str, Any] = {}
    payload = {"status": "success", "data": {"resultType": "matrix", "result": []}}

    def urlopen(url: str, timeout: int) -> io.BytesIO:
        captured.update(url=url, timeout=timeout)
        return io.BytesIO(json.dumps(payload).encode())

    monkeypatch.setattr(namespace["range_query"].__globals__["urllib"].request, "urlopen", urlopen)

    assert namespace["range_query"]("https://prometheus.example", "up", start, end) == []
    parsed = urllib.parse.urlparse(captured["url"])
    query = urllib.parse.parse_qs(parsed.query)
    assert parsed.scheme == "https"
    assert query["query"] == ["up"]
    assert float(query["start"][0]) == start.timestamp() + 300
    assert float(query["end"][0]) == end.timestamp()
    assert query["step"] == ["300s"]
    assert captured["timeout"] == 30


@pytest.mark.parametrize("url", ["file:///tmp/prometheus", "prometheus:9090", "ftp://example.test"])
def test_range_query_rejects_non_http_urls(url: str) -> None:
    namespace = _load()
    start = datetime(2026, 1, 1, tzinfo=UTC)

    with pytest.raises(namespace["BaselineError"], match="http or https"):
        namespace["range_query"](url, "up", start, start + timedelta(days=14))


def test_normalize_matrix_rejects_duplicate_and_nonfinite_series() -> None:
    namespace = _load()
    duplicate = [
        {"metric": {"wan": "att"}, "values": [[1, "1"]]},
        {"metric": {"wan": "att"}, "values": [[2, "1"]]},
    ]
    nonfinite = [{"metric": {"wan": "att"}, "values": [[1, "NaN"]]}]

    with pytest.raises(namespace["BaselineError"], match="duplicate"):
        namespace["normalize_matrix"](duplicate, ("wan",))
    with pytest.raises(namespace["BaselineError"], match="non-finite"):
        namespace["normalize_matrix"](nonfinite, ("wan",))


def test_short_window_fails_before_any_prometheus_query() -> None:
    namespace = _load()
    start = datetime(2026, 1, 1, tzinfo=UTC)
    end = start + timedelta(days=7)
    namespace["baseline_report"].__globals__["collect_matrices"] = lambda *_args: pytest.fail(
        "must not query Prometheus"
    )

    report, exit_code = namespace["baseline_report"]("http://unreachable", start, end)

    assert exit_code == 2
    assert report["status"] == "not_eligible"
    assert report["eligible_at"] == "2026-01-08T15:05:00Z"
    assert report["safety"] == {
        "read_only_prometheus_api": True,
        "configuration_writes": False,
        "traffic_generation": False,
        "tuning_or_actuation": False,
    }


def test_coverage_gate_accepts_complete_up_fresh_series() -> None:
    namespace = _load()
    start = datetime(2026, 1, 1, tzinfo=UTC)
    end = start + timedelta(days=14)
    timestamps = [int((start + timedelta(days=7)).timestamp()), int(end.timestamp())]
    matrices = _coverage_matrices(namespace, timestamps)

    coverage = namespace["validate_coverage"](matrices, start, end, step_seconds=7 * 24 * 60 * 60)

    assert coverage["expected_points_per_series"] == 2
    assert all(item["ratio"] == 1.0 for item in coverage["series"].values())


@pytest.mark.parametrize(
    ("metric", "value", "message"),
    [
        ("stats_up", 0.0, "contains unavailable samples"),
        ("probe_up", 0.5, "contains non-binary samples"),
        ("stats_age_seconds", 121.0, "exceeds 120s"),
    ],
)
def test_coverage_gate_rejects_unhealthy_samples(metric: str, value: float, message: str) -> None:
    namespace = _load()
    start = datetime(2026, 1, 1, tzinfo=UTC)
    end = start + timedelta(days=14)
    timestamps = [int((start + timedelta(days=7)).timestamp()), int(end.timestamp())]
    matrices = _coverage_matrices(namespace, timestamps)
    matrices[metric][("att",)][timestamps[1]] = value

    with pytest.raises(namespace["BaselineError"], match=message):
        namespace["validate_coverage"](matrices, start, end, step_seconds=7 * 24 * 60 * 60)


def _fourteen_day_coverage(
    namespace: dict[str, Any],
) -> tuple[datetime, datetime, list[int], dict[str, Any]]:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    end = start + timedelta(days=14)
    timestamps = namespace["evaluation_timestamps"](start, end)
    return start, end, timestamps, _coverage_matrices(namespace, timestamps)


def test_probe_availability_accepts_bounded_isolated_down_windows() -> None:
    namespace = _load()
    start, end, timestamps, matrices = _fourteen_day_coverage(namespace)
    down_timestamps = timestamps[::200][:20]
    for timestamp in down_timestamps:
        matrices["probe_up"][("spectrum",)][timestamp] = 0.0

    coverage = namespace["validate_coverage"](matrices, start, end)

    probe = coverage["series"]["probe_up:spectrum"]
    assert probe["availability_ratio"] == pytest.approx(4012 / 4032)
    assert probe["down_windows"] == 20
    assert probe["reported_down_windows"] == 20
    assert probe["missing_windows"] == 0
    assert probe["longest_down_run_windows"] == 1
    assert len(probe["down_runs"]) == 20


def test_probe_availability_rejects_excessive_down_windows() -> None:
    namespace = _load()
    start, end, timestamps, matrices = _fourteen_day_coverage(namespace)
    # 98% of 4032 = 3951.36, so 3951 good / 4032 = 97.99% < 98% → rejected
    for timestamp in timestamps[::10][:81]:
        matrices["probe_up"][("spectrum",)][timestamp] = 0.0

    with pytest.raises(namespace["BaselineError"], match="availability .* below 98.0%"):
        namespace["validate_coverage"](matrices, start, end)


def test_probe_availability_rejects_sustained_outage_below_ratio_limit() -> None:
    namespace = _load()
    start, end, timestamps, matrices = _fourteen_day_coverage(namespace)
    for timestamp in timestamps[100:109]:
        matrices["probe_up"][("att",)][timestamp] = 0.0

    with pytest.raises(namespace["BaselineError"], match="9 consecutive down windows"):
        namespace["validate_coverage"](matrices, start, end)


def test_probe_availability_counts_missing_sample_inside_outage_run() -> None:
    namespace = _load()
    start, end, timestamps, matrices = _fourteen_day_coverage(namespace)
    for index in (100, 101, 103, 104, 105, 106, 107, 108):
        matrices["probe_up"][("att",)][timestamps[index]] = 0.0
    del matrices["probe_up"][("att",)][timestamps[102]]

    with pytest.raises(namespace["BaselineError"], match="9 consecutive down windows"):
        namespace["validate_coverage"](matrices, start, end)


def test_probe_availability_uses_expected_grid_for_missing_sample_denominator() -> None:
    namespace = _load()
    start, end, timestamps, matrices = _fourteen_day_coverage(namespace)
    # 82 down (step 49 avoids deleted indices) + 4 missing = 86 bad → 97.87% < 98%
    for timestamp in timestamps[::49][:82]:
        matrices["probe_up"][("spectrum",)][timestamp] = 0.0
    for index in (1000, 1200, 1400, 1600):
        del matrices["probe_up"][("spectrum",)][timestamps[index]]

    with pytest.raises(namespace["BaselineError"], match="availability .* below 98.0%"):
        namespace["validate_coverage"](matrices, start, end)


def test_probe_outage_disclosure_distinguishes_missing_and_reported_down_windows() -> None:
    namespace = _load()
    start, end, timestamps, matrices = _fourteen_day_coverage(namespace)
    matrices["probe_up"][("att",)][timestamps[100]] = 0.0
    del matrices["probe_up"][("att",)][timestamps[200]]

    coverage = namespace["validate_coverage"](matrices, start, end)

    probe = coverage["series"]["probe_up:att"]
    assert probe["down_windows"] == 2
    assert probe["reported_down_windows"] == 1
    assert probe["missing_windows"] == 1
    assert probe["down_runs"] == [
        {
            "start": "2026-01-01T08:25:00Z",
            "end": "2026-01-01T08:25:00Z",
            "windows": 1,
            "reported_down_windows": 1,
            "missing_windows": 0,
        },
        {
            "start": "2026-01-01T16:45:00Z",
            "end": "2026-01-01T16:45:00Z",
            "windows": 1,
            "reported_down_windows": 0,
            "missing_windows": 1,
        },
    ]


def test_cohort_output_is_deterministic_and_declares_missing_data() -> None:
    namespace = _load()
    matrices, timestamps = _complete_matrices(namespace)

    first = namespace["build_cohorts"](copy.deepcopy(matrices), timestamps)
    second = namespace["build_cohorts"](copy.deepcopy(matrices), timestamps)

    assert first == second
    cohorts, disclosure = first
    assert len(cohorts) == 36
    assert {cohort["load_cohort"] for cohort in cohorts} == {
        "idle_lt_10pct",
        "active_10_to_60pct",
        "loaded_ge_60pct",
    }
    assert {cohort["time_cohort"] for cohort in cohorts} == {
        "utc_00_to_06",
        "utc_06_to_18",
        "utc_18_to_24",
    }
    assert all(cohort["sample_count"] == 12 for cohort in cohorts)
    assert all(
        cohort["dimensions"]["congestion_green_fraction"]["mean"] == 0.5 for cohort in cohorts
    )
    assert disclosure["candidate_points"] == 432
    assert disclosure["accepted_points"] == 432
    assert disclosure["discarded_incomplete_points"] == 0
    assert disclosure["completeness_ratio"] == 1.0
    assert disclosure["missing_by_dimension"] == {}
    assert disclosure["observed_cohort_count"] == 36
    assert disclosure["published_cohort_count"] == 36
    assert disclosure["insufficient_cohorts"] == []
    assert disclosure["missing_cohorts"] == []


def test_cohort_gate_rejects_unknown_congestion_state_before_cohort_publication() -> None:
    namespace = _load()
    matrices, timestamps = _complete_matrices(namespace)
    matrices["congestion_unknown_fraction"][("att", "download")][timestamps[0]] = 0.1

    with pytest.raises(namespace["BaselineError"], match="unknown congestion state"):
        namespace["build_cohorts"](matrices, timestamps)


def test_cohort_gate_rejects_out_of_bounds_congestion_fraction() -> None:
    namespace = _load()
    matrices, timestamps = _complete_matrices(namespace)
    matrices["congestion_green_fraction"][("att", "download")][timestamps[0]] = 1.7

    with pytest.raises(namespace["BaselineError"], match="out of bounds"):
        namespace["build_cohorts"](matrices, timestamps)


def test_cohort_gate_rejects_congestion_fractions_that_do_not_sum_to_one() -> None:
    namespace = _load()
    matrices, timestamps = _complete_matrices(namespace)
    matrices["congestion_red_fraction"][("att", "download")][timestamps[0]] = 0.1

    with pytest.raises(namespace["BaselineError"], match="do not sum to one"):
        namespace["build_cohorts"](matrices, timestamps)


def test_cohort_gate_rejects_missing_fixed_tin_series() -> None:
    namespace = _load()
    matrices, timestamps = _complete_matrices(namespace)
    del matrices["tin_backlog_bytes"][("att", "download", "voice")]

    with pytest.raises(namespace["BaselineError"], match="label mismatch"):
        namespace["build_cohorts"](matrices, timestamps)


def test_probe_down_timestamp_is_disclosed_and_excluded_from_both_direction_cohorts() -> None:
    namespace = _load()
    matrices, timestamps = _complete_matrices(namespace)
    matrices["probe_up"][("att",)][timestamps[0]] = 0.0

    _cohorts, disclosure = namespace["build_cohorts"](matrices, timestamps)

    assert disclosure["missing_by_dimension"]["probe_down"] == 2
    assert disclosure["candidate_points"] == 432
    assert disclosure["accepted_points"] == 430
    assert disclosure["discarded_incomplete_points"] == 2


def test_cohort_gate_rejects_missing_probe_label() -> None:
    namespace = _load()
    matrices, timestamps = _complete_matrices(namespace)
    del matrices["probe_up"][("att",)]

    with pytest.raises(namespace["BaselineError"], match="probe_up label mismatch"):
        namespace["build_cohorts"](matrices, timestamps)


def test_dimension_coverage_gate_uses_fixed_expected_denominator() -> None:
    namespace = _load()
    matrices, timestamps = _complete_matrices(namespace)
    start = datetime.fromtimestamp(timestamps[0] - 300, UTC)
    end = start + timedelta(seconds=len(timestamps) * 300)

    coverage = namespace["validate_dimension_coverage"](matrices, start, end)
    assert all(item["ratio"] == 1.0 for item in coverage.values())

    del matrices["throughput_bps"][("att", "download")][timestamps[0]]
    del matrices["throughput_bps"][("att", "download")][timestamps[1]]
    with pytest.raises(namespace["BaselineError"], match="coverage"):
        namespace["validate_dimension_coverage"](matrices, start, end)


def test_cohort_completeness_gate_counts_expected_timestamps() -> None:
    namespace = _load()
    matrices, timestamps = _complete_matrices(namespace)
    for timestamp in timestamps[:5]:
        del matrices["throughput_bps"][("att", "download")][timestamp]

    with pytest.raises(namespace["BaselineError"], match="complete cohort samples"):
        namespace["build_cohorts"](matrices, timestamps)


def test_sparse_cohorts_are_rejected_instead_of_publishing_single_sample_quantiles() -> None:
    namespace = _load()
    matrices, timestamps = _complete_matrices(namespace)
    one_day = timestamps[:9]

    with pytest.raises(namespace["BaselineError"], match="at least 12 samples"):
        namespace["build_cohorts"](matrices, one_day)


def test_counter_reset_sample_is_disclosed_and_not_summarized() -> None:
    namespace = _load()
    matrices, timestamps = _complete_matrices(namespace)
    reset_at = timestamps[1]
    tin_key = ("att", "download", "bulk")
    matrices["tin_resets_total"][tin_key][reset_at] = 1.0

    cohorts, disclosure = namespace["build_cohorts"](matrices, timestamps)

    assert disclosure["missing_by_dimension"]["counter_reset:bulk"] == 1
    assert disclosure["discarded_incomplete_points"] == 1
    assert any(item["sample_count"] == 11 for item in disclosure["insufficient_cohorts"])
    assert all(cohort["sample_count"] >= 12 for cohort in cohorts)


def test_eligible_window_rejects_prometheus_api_failure() -> None:
    namespace = _load()
    start = datetime(2026, 1, 1, tzinfo=UTC)
    end = start + timedelta(seconds=659100)

    def fail(*_args: Any) -> None:
        raise OSError("Prometheus unavailable")

    namespace["baseline_report"].__globals__["collect_matrices"] = fail
    report, exit_code = namespace["baseline_report"]("http://unreachable", start, end)

    assert exit_code == 2
    assert report["status"] == "rejected"
    assert report["reason"] == "Prometheus unavailable"


def test_cli_not_eligible_result_is_stable_and_needs_no_server(tmp_path: Path) -> None:
    output = tmp_path / "baseline.json"
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--prometheus-url",
            "http://127.0.0.1:1",
            "--start",
            "2026-07-31T22:20:36.035Z",
            "--end",
            "2026-08-01T02:25:36.035Z",
            "--output",
            str(output),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    report = json.loads(output.read_text(encoding="utf-8"))
    assert result.returncode == 2
    assert result.stdout == ""
    assert report["status"] == "not_eligible"
    # eligible_at = start + MIN_WINDOW_SECONDS (659100s = ~7.63d)
    assert report["eligible_at"] == "2026-08-08T13:25:36.035000Z"
    assert report["queries"] == _load()["QUERIES"]


def test_script_has_no_control_command_surface() -> None:
    source = SCRIPT.read_text(encoding="utf-8")

    assert "import subprocess" not in source
    assert "os.system" not in source
    assert "shell=True" not in source
    assert "tc " not in source
    assert "nft" not in source
    assert "RouterOS" not in source
    assert "systemctl" not in source
