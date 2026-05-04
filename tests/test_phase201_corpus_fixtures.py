"""Smoke tests for Phase 201 replay corpus fixtures (Plan 201-01)."""

from tests.fixtures.phase201_replay_corpus import (
    ATTEMPT3_NDJSON_PATH,
    load_attempt2_trace,
    load_attempt3_trace,
    synthesize_idle_trace,
    synthesize_sustained_load_trace,
)


def test_attempt3_trace_loads_nonempty():
    samples = load_attempt3_trace()
    # 885-line NDJSON; tolerate trailing empty/incomplete lines.
    assert len(samples) >= 800, f"expected >=800 samples, got {len(samples)}"


def test_attempt3_trace_has_baseline_and_load_rtt():
    samples = load_attempt3_trace()
    populated = [
        s for s in samples if s.baseline_rtt_ms is not None and s.load_rtt_ms is not None
    ]
    assert len(populated) >= 800


def test_attempt3_trace_records_upload_state():
    samples = load_attempt3_trace()
    states = {s.upload_state for s in samples}
    # Floor hits = 4 per verdict.json; expect at least GREEN+RED to appear.
    assert "GREEN" in states or "YELLOW" in states or "RED" in states


def test_attempt3_trace_has_cake_backlog():
    samples = load_attempt3_trace()
    populated = [s for s in samples if s.cake_backlog_bytes is not None]
    assert len(populated) >= 800


def test_attempt2_trace_loads_or_empty():
    # Optional secondary corpus — must not raise.
    samples = load_attempt2_trace()
    assert isinstance(samples, list)


def test_synthesize_sustained_trace_shape():
    trace = synthesize_sustained_load_trace(
        cycles=60, baseline_rtt_ms=22.0, peak_delta_ms=30.0, ramp_cycles=10
    )
    assert len(trace) == 60
    # Plateau samples have delta == peak_delta_ms
    plateau = trace[20]
    assert abs((plateau.load_rtt_ms - plateau.baseline_rtt_ms) - 30.0) < 1e-9


def test_synthesize_idle_trace_low_delta():
    trace = synthesize_idle_trace(cycles=60, baseline_rtt_ms=22.0, jitter_ms=0.5)
    assert len(trace) == 60
    deltas = [s.load_rtt_ms - s.baseline_rtt_ms for s in trace]
    assert max(deltas) <= 0.5 + 1e-9


def test_attempt3_path_constant_resolves():
    # Anchor: file exists at runtime; if False, planner-cited path is wrong.
    assert ATTEMPT3_NDJSON_PATH.exists(), f"missing {ATTEMPT3_NDJSON_PATH}"
