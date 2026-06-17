import json
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "phase243-cycle-rollup.py"


def run_rollup(input_text: str, *extra_args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "-", *extra_args],
        input=input_text,
        text=True,
        capture_output=True,
        check=False,
        cwd=ROOT,
    )


def cycle_line(offset_ms: int, cycle_total_ms: float | None = 5.0) -> str:
    timestamp = datetime(2026, 6, 17, tzinfo=UTC) + timedelta(milliseconds=offset_ms)
    record: dict[str, object] = {
        "message": "Cycle timing",
        "timestamp": timestamp.isoformat().replace("+00:00", "Z"),
    }
    if cycle_total_ms is not None:
        record["cycle_total_ms"] = cycle_total_ms
    return json.dumps(record)


def valid_fixture() -> str:
    values = [4.0, 5.0, 6.0, 7.0]
    return "\n".join(cycle_line(index * 50, value) for index, value in enumerate(values)) + "\n"


def test_rolls_up_cycle_stats_and_invocation_id() -> None:
    result = run_rollup(valid_fixture(), "--invocation-id", "inv-123")
    assert result.returncode == 0, result.stderr
    profile = json.loads(result.stdout)

    stats = profile["autorate_cycle_total"]
    assert stats["count"] == 4
    assert stats["avg_ms"] == 5.5
    assert stats["p99_ms"] == 7.0
    assert profile["invocation_id"] == "inv-123"
    assert profile["stall"]["stall_events"] == []


def test_detects_stall_gap_over_100ms() -> None:
    fixture = "\n".join(
        [cycle_line(0, 5.0), cycle_line(50, 5.0), cycle_line(225, 5.0)]
    )
    result = run_rollup(fixture, "--invocation-id", "inv-stall")
    assert result.returncode == 0, result.stderr
    stall = json.loads(result.stdout)["stall"]

    assert stall["stall_event_count"] == 1
    assert stall["stall_events"] == [{"index": 2, "gap_ms": 175.0}]
    assert stall["max_gap_ms"] == 175.0


def test_exits_2_when_cycle_records_lack_cycle_total() -> None:
    result = run_rollup(cycle_line(0, None), "--invocation-id", "inv-no-total")
    assert result.returncode == 2
    assert "no autorate_cycle_total" in result.stderr


def test_exits_2_when_no_cycle_timing_records() -> None:
    result = run_rollup('{"message":"not cycle"}\n', "--invocation-id", "inv-empty")
    assert result.returncode == 2
    assert "no Cycle timing records" in result.stderr


def test_exits_2_without_invocation_id() -> None:
    result = run_rollup(valid_fixture())
    assert result.returncode == 2


def test_parse_counter_counts_malformed_lines_without_crashing() -> None:
    fixture = cycle_line(0, 4.0) + "\nnot-json\n" + cycle_line(50, 6.0) + "\n"
    result = run_rollup(fixture, "--invocation-id", "inv-parse")
    assert result.returncode == 0, result.stderr
    counters = json.loads(result.stdout)["parse_counters"]

    assert counters["lines_seen"] == 3
    assert counters["json_decode_failures"] == 1
    assert counters["cycle_records"] == 2
    assert counters["timestamped_records"] == 2
