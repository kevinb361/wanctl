---
phase: 201-docsis-aware-ul-congestion-control
plan: 01
type: execute
wave: 0
depends_on: []
files_modified:
  - tests/fixtures/phase201_replay_corpus.py
  - tests/conftest.py
  - .planning/phases/201-docsis-aware-ul-congestion-control/201-01-CORPUS-AUDIT.md
autonomous: true
requirements: [VALN-06]
tags: [phase-201, wave-0, replay, fixtures, validation]

must_haves:
  truths:
    - "Phase 200 Attempt 3 NDJSON capture is parsed and exposed to test code as a typed corpus"
    - "Open Question 1 answered: per-cycle CAKE backlog/delay-delta presence in capture documented"
    - "Open Question 2 answered: Spectrum provisioned upstream rate confirmed (or assumption A4 explicitly recorded)"
    - "Synthetic load-trace generator fixture is callable from any test file"
  artifacts:
    - path: tests/fixtures/phase201_replay_corpus.py
      provides: "Replay corpus loader for Attempt 3 + Attempt 2 NDJSON; synthetic-trace generator"
      contains: "def load_attempt3_trace"
    - path: .planning/phases/201-docsis-aware-ul-congestion-control/201-01-CORPUS-AUDIT.md
      provides: "Audit report documenting which CAKE fields are present/absent in capture; provisioned-rate confirmation"
      contains: "max_delay_delta_us"
  key_links:
    - from: "tests/fixtures/phase201_replay_corpus.py"
      to: ".planning/phases/200-per-direction-rtt-bloat-thresholds/canary/20260504T133207Z/loaded_capture.ndjson"
      via: "Path() relative to repo root"
      pattern: "loaded_capture\\.ndjson"
---

<objective>
Wave 0 inspection + corpus prep. Resolves RESEARCH.md Open Questions #1 (per-cycle CAKE field presence in NDJSON) and #2 (Spectrum provisioned upstream rate). Builds the typed replay-corpus loader and synthetic-trace generator fixtures that all subsequent test plans depend on. This plan MUST land before any production code in Waves 2+ touches `src/wanctl/queue_controller.py` or `src/wanctl/wan_controller.py`.

Purpose: Eliminate test-time guesswork — every downstream test plan imports from `tests/fixtures/phase201_replay_corpus.py` instead of re-parsing NDJSON. The audit doc captures which fields are missing from the capture so canary script extension (Plan 201-08) knows what to add.

Output: One audit markdown file, one fixtures module, one conftest fixture registration.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/STATE.md
@.planning/phases/201-docsis-aware-ul-congestion-control/201-CONTEXT.md
@.planning/phases/201-docsis-aware-ul-congestion-control/201-RESEARCH.md
@.planning/phases/201-docsis-aware-ul-congestion-control/201-PATTERNS.md
@.planning/phases/200-per-direction-rtt-bloat-thresholds/canary/20260504T133207Z/verdict.json
</context>

<interfaces>
<!-- Confirmed during planning by reading first NDJSON line. -->
NDJSON capture line shape (Phase 200 Attempt 3 / 20260504T133207Z, 885 lines, 1 Hz):

Top-level: status, uptime_seconds, version, consecutive_failures, wan_count, wans, storage, alerting, router_reachable, disk_space, summary, sampled_at_utc

wans[0] keys: name, baseline_rtt_ms, load_rtt_ms, download, upload, router_connectivity, cycle_budget, signal_quality, measurement, background_workers, irtt, reflector_quality, fusion, asymmetry_gate, cake_signal, signal_arbitration, tuning, storage, runtime

wans[0].upload keys: current_rate_mbps, state, state_reason, hysteresis

wans[0].cake_signal.upload keys: drop_rate, total_drop_rate, backlog_bytes, peak_delay_us, cold_start, tins
  -> tins[0] keys: name, drop_delta, backlog_bytes, peak_delay_us
  -> NOTE: max_delay_delta_us is ABSENT at both top and per-tin levels.
  -> Implication: replay can validate integral state machine (load_rtt - baseline_rtt) and CAKE backlog corroborator (backlog_bytes), but CANNOT validate the delay-delta arm of `_is_cake_aligned_for_pushup` from this capture.
</interfaces>

<tasks>

<task type="auto" tdd="false">
  <name>Task 1: Author corpus audit + Spectrum provisioned-rate confirmation</name>
  <files>.planning/phases/201-docsis-aware-ul-congestion-control/201-01-CORPUS-AUDIT.md</files>
  <read_first>
    - .planning/phases/200-per-direction-rtt-bloat-thresholds/canary/20260504T133207Z/verdict.json (read in full)
    - First two lines of .planning/phases/200-per-direction-rtt-bloat-thresholds/canary/20260504T133207Z/loaded_capture.ndjson via head -2 piped to python -c json.dumps for shape inspection
    - .planning/phases/201-docsis-aware-ul-congestion-control/201-RESEARCH.md sections 8 (Replay Corpus), Open Questions 1 and 2, Assumptions Log A4 + A5 + A6 + A10
  </read_first>
  <action>
Write `.planning/phases/201-docsis-aware-ul-congestion-control/201-01-CORPUS-AUDIT.md` with these exact sections:

1. `## Summary` — one paragraph: capture exists at the path, 885 NDJSON lines at 1 Hz, verdict.json reports `ul_floor_hits_during_load: 4`. Closes Open Question 1.
2. `## Field Presence Audit (Attempt 3 — 20260504T133207Z)` — markdown table with three columns: `Field needed for Phase 201 replay`, `Path in NDJSON`, `Present?`. Rows MUST include verbatim:
   - `load_rtt_ms` -> `wans[0].load_rtt_ms` -> YES
   - `baseline_rtt_ms` -> `wans[0].baseline_rtt_ms` -> YES
   - `upload.current_rate_mbps` -> `wans[0].upload.current_rate_mbps` -> YES
   - `upload.state` (zone label) -> `wans[0].upload.state` -> YES
   - `cake_signal.upload.backlog_bytes` -> `wans[0].cake_signal.upload.backlog_bytes` -> YES
   - `cake_signal.upload.cold_start` -> `wans[0].cake_signal.upload.cold_start` -> YES
   - `cake_signal.upload.max_delay_delta_us` -> `wans[0].cake_signal.upload.max_delay_delta_us` -> NO (CRITICAL GAP)
   - `cake_signal.upload.tins[].max_delay_delta_us` -> per-tin -> NO (only `peak_delay_us` and `backlog_bytes` per tin)
3. `## Replay Implications` — three bullets: (a) RTT-integral state-machine fully testable; (b) CAKE backlog arm of `_is_cake_aligned_for_pushup` testable; (c) `max_delay_delta_us` arm CANNOT be validated from Attempt 3 capture — replay tests for that arm MUST use synthetic traces. Plan 201-08 canary extension MUST add `max_delay_delta_us` to the capture shape.
4. `## Spectrum Provisioned Upstream Rate (Open Question 2)` — record A4 explicitly: "Estimated provisioned upstream rate is ~20 Mbit per Phase 200 RETRO and CONTEXT D-09. This audit does NOT independently verify against ISP-side billing data; the value is treated as `[ASSUMED A4]`. If operator confirms a materially different value (>10% delta), the canary preflight in Plan 201-08 MUST be re-run with adjusted `PHASE201_SETPOINT_MBPS`. Setpoint default 12 Mbit is 60% of 20; if actual is 22, defensible setpoint shifts to 13; if actual is 18, defensible setpoint shifts to 11."
5. `## Sampling Rate Note` — single bullet: "Capture is 1 Hz; integral runs at 20 Hz (50ms cycle). Replay tests can validate integral state-machine logic but not 50ms timing fidelity. Acceptable per RESEARCH Assumption A10. Canary itself is the 20 Hz validator; soak is the 24h watchdog."
6. `## Recommended canary extension for v1.42 corpus` — one bullet: "scripts/phase200-saturation-canary.sh `capture_health_ndjson` should be extended (Plan 201-08) to record `wans[].cake_signal.upload.max_delay_delta_us` at 1 Hz."

The doc must NOT recommend changing setpoint = 12; it must record A4/A5 as assumptions per RESEARCH.md Section 4 verdict ("keep 12 as SPEC, document as ASSUMED").
  </action>
  <acceptance_criteria>
    - File `.planning/phases/201-docsis-aware-ul-congestion-control/201-01-CORPUS-AUDIT.md` exists.
    - `grep -c "max_delay_delta_us" .planning/phases/201-docsis-aware-ul-congestion-control/201-01-CORPUS-AUDIT.md` returns >= 3.
    - `grep -c "ASSUMED A4" .planning/phases/201-docsis-aware-ul-congestion-control/201-01-CORPUS-AUDIT.md` returns >= 1.
    - `grep -c "885" .planning/phases/201-docsis-aware-ul-congestion-control/201-01-CORPUS-AUDIT.md` returns >= 1 (NDJSON line count anchor).
    - `grep -c "Open Question 1" .planning/phases/201-docsis-aware-ul-congestion-control/201-01-CORPUS-AUDIT.md` returns >= 1.
    - `grep -c "Open Question 2" .planning/phases/201-docsis-aware-ul-congestion-control/201-01-CORPUS-AUDIT.md` returns >= 1.
  </acceptance_criteria>
  <verify>
    <automated>test -f .planning/phases/201-docsis-aware-ul-congestion-control/201-01-CORPUS-AUDIT.md &amp;&amp; grep -q "ASSUMED A4" .planning/phases/201-docsis-aware-ul-congestion-control/201-01-CORPUS-AUDIT.md &amp;&amp; grep -q "Open Question 1" .planning/phases/201-docsis-aware-ul-congestion-control/201-01-CORPUS-AUDIT.md &amp;&amp; grep -q "Open Question 2" .planning/phases/201-docsis-aware-ul-congestion-control/201-01-CORPUS-AUDIT.md</automated>
  </verify>
  <done>Audit file exists with all five sections; max_delay_delta_us gap is explicitly flagged as CRITICAL GAP requiring Plan 201-08 extension.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Build typed replay corpus loader + synthetic-trace generator fixtures</name>
  <files>tests/fixtures/phase201_replay_corpus.py, tests/fixtures/__init__.py, tests/conftest.py, tests/test_phase201_corpus_fixtures.py</files>
  <read_first>
    - tests/test_phase_197_replay.py:1-100 (canonical replay shape — _queue_snapshot helper, MagicMock pattern)
    - tests/conftest.py (full file — to know existing fixture surface and import style)
    - tests/fixtures/ directory listing (run `ls tests/fixtures/` first; create __init__.py if missing)
    - .planning/phases/201-docsis-aware-ul-congestion-control/201-PATTERNS.md section "tests/test_phase_201_replay.py (NEW)"
    - src/wanctl/cake_signal.py:80-170 (CakeSignalSnapshot dataclass shape)
  </read_first>
  <behavior>
    - load_attempt3_trace() returns a list of ReplaySample dataclass instances, one per non-empty NDJSON line in canary/20260504T133207Z/loaded_capture.ndjson, with fields: ts (str), baseline_rtt_ms (float|None), load_rtt_ms (float|None), upload_state (str), upload_current_rate_mbps (float), cake_backlog_bytes (int|None), cake_cold_start (bool|None).
    - load_attempt2_trace() returns the same shape from canary/20260503T215734Z/loaded_capture.ndjson if present, else returns [] without raising.
    - synthesize_sustained_load_trace(cycles=60, baseline_rtt_ms=22.0, peak_delta_ms=30.0, ramp_cycles=10, backlog_bytes=8000) returns a list of ReplaySample with deterministic monotonic-ramp + plateau profile (used by integral and corroborator unit tests).
    - synthesize_idle_trace(cycles=60, baseline_rtt_ms=22.0, jitter_ms=0.5) returns a list with delta ~ 0 (used by AVAILABLE-state tests).
    - Module exports `ATTEMPT3_NDJSON_PATH` (Path) and `ATTEMPT3_VERDICT_PATH` (Path) constants pointing at the corpus.
    - All three callable factories are pickle-free pure-Python; do NOT import wanctl modules at module top-level (defer to function bodies if needed) — keeps test collection fast.
  </behavior>
  <action>
First, create `tests/fixtures/__init__.py` (empty file) if not present so `tests.fixtures` is a package.

Create `tests/fixtures/phase201_replay_corpus.py` with:

```python
"""Phase 201 replay corpus loader and synthetic-trace generator.

Single source of truth for replay-test inputs. All Phase 201 test files
that need historical or synthetic UL traces import from this module.

Origin: RESEARCH.md Section 8 (Replay-Test Corpus); PATTERNS.md
'tests/test_phase_201_replay.py (NEW)'.
"""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import json
from typing import Iterable

REPO_ROOT = Path(__file__).resolve().parents[2]
ATTEMPT3_NDJSON_PATH = REPO_ROOT / ".planning/phases/200-per-direction-rtt-bloat-thresholds/canary/20260504T133207Z/loaded_capture.ndjson"
ATTEMPT3_VERDICT_PATH = REPO_ROOT / ".planning/phases/200-per-direction-rtt-bloat-thresholds/canary/20260504T133207Z/verdict.json"
ATTEMPT2_NDJSON_PATH = REPO_ROOT / ".planning/phases/200-per-direction-rtt-bloat-thresholds/canary/20260503T215734Z/loaded_capture.ndjson"

@dataclass(frozen=True)
class ReplaySample:
    ts: str
    baseline_rtt_ms: float | None
    load_rtt_ms: float | None
    upload_state: str
    upload_current_rate_mbps: float
    cake_backlog_bytes: int | None
    cake_cold_start: bool | None

def _parse_line(raw: str) -> ReplaySample | None:
    raw = raw.strip()
    if not raw:
        return None
    try:
        obj = json.loads(raw)
    except json.JSONDecodeError:
        return None
    wans = obj.get("wans") or []
    if not wans:
        return None
    w = wans[0]
    ul = w.get("upload") or {}
    cs = (w.get("cake_signal") or {}).get("upload") or {}
    return ReplaySample(
        ts=obj.get("sampled_at_utc", ""),
        baseline_rtt_ms=w.get("baseline_rtt_ms"),
        load_rtt_ms=w.get("load_rtt_ms"),
        upload_state=ul.get("state", ""),
        upload_current_rate_mbps=float(ul.get("current_rate_mbps") or 0.0),
        cake_backlog_bytes=cs.get("backlog_bytes"),
        cake_cold_start=cs.get("cold_start"),
    )

def _load_ndjson(path: Path) -> list[ReplaySample]:
    if not path.exists():
        return []
    out: list[ReplaySample] = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            sample = _parse_line(line)
            if sample is not None:
                out.append(sample)
    return out

def load_attempt3_trace() -> list[ReplaySample]:
    return _load_ndjson(ATTEMPT3_NDJSON_PATH)

def load_attempt2_trace() -> list[ReplaySample]:
    return _load_ndjson(ATTEMPT2_NDJSON_PATH)

def synthesize_sustained_load_trace(
    cycles: int = 60,
    baseline_rtt_ms: float = 22.0,
    peak_delta_ms: float = 30.0,
    ramp_cycles: int = 10,
    backlog_bytes: int = 8000,
) -> list[ReplaySample]:
    out: list[ReplaySample] = []
    for i in range(cycles):
        if i < ramp_cycles:
            delta = peak_delta_ms * (i / ramp_cycles)
        else:
            delta = peak_delta_ms
        out.append(ReplaySample(
            ts=f"synthetic-{i:04d}",
            baseline_rtt_ms=baseline_rtt_ms,
            load_rtt_ms=baseline_rtt_ms + delta,
            upload_state="GREEN",
            upload_current_rate_mbps=18.0,
            cake_backlog_bytes=backlog_bytes,
            cake_cold_start=False,
        ))
    return out

def synthesize_idle_trace(
    cycles: int = 60,
    baseline_rtt_ms: float = 22.0,
    jitter_ms: float = 0.5,
) -> list[ReplaySample]:
    out: list[ReplaySample] = []
    for i in range(cycles):
        delta = jitter_ms if (i % 2 == 0) else 0.0
        out.append(ReplaySample(
            ts=f"idle-{i:04d}",
            baseline_rtt_ms=baseline_rtt_ms,
            load_rtt_ms=baseline_rtt_ms + delta,
            upload_state="GREEN",
            upload_current_rate_mbps=18.0,
            cake_backlog_bytes=0,
            cake_cold_start=False,
        ))
    return out
```

Then add to `tests/conftest.py` (append, do not break existing fixtures) — register pytest fixtures wrapping the loaders so tests can use them by name:

```python
# Phase 201 replay corpus fixtures (Plan 201-01).
import pytest
from tests.fixtures.phase201_replay_corpus import (
    load_attempt3_trace,
    load_attempt2_trace,
    synthesize_sustained_load_trace,
    synthesize_idle_trace,
)

@pytest.fixture(scope="session")
def phase201_attempt3_trace():
    return load_attempt3_trace()

@pytest.fixture(scope="session")
def phase201_attempt2_trace():
    return load_attempt2_trace()

@pytest.fixture
def phase201_sustained_load_trace():
    return synthesize_sustained_load_trace()

@pytest.fixture
def phase201_idle_trace():
    return synthesize_idle_trace()
```

Then create `tests/test_phase201_corpus_fixtures.py` with these tests:

```python
"""Smoke tests for Phase 201 replay corpus fixtures (Plan 201-01)."""
from tests.fixtures.phase201_replay_corpus import (
    load_attempt3_trace, load_attempt2_trace,
    synthesize_sustained_load_trace, synthesize_idle_trace,
    ATTEMPT3_NDJSON_PATH,
)

def test_attempt3_trace_loads_nonempty():
    samples = load_attempt3_trace()
    # 885-line NDJSON; tolerate trailing empty/incomplete lines.
    assert len(samples) >= 800, f"expected >=800 samples, got {len(samples)}"

def test_attempt3_trace_has_baseline_and_load_rtt():
    samples = load_attempt3_trace()
    populated = [s for s in samples if s.baseline_rtt_ms is not None and s.load_rtt_ms is not None]
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
    trace = synthesize_sustained_load_trace(cycles=60, baseline_rtt_ms=22.0, peak_delta_ms=30.0, ramp_cycles=10)
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
```

Note: do NOT add `from wanctl import ...` at module top-level in the corpus loader — keep it dependency-free so it can be imported even if the package import surface changes.
  </action>
  <acceptance_criteria>
    - `.venv/bin/pytest -o addopts='' tests/test_phase201_corpus_fixtures.py -q` passes (8 tests).
    - `grep -c 'def load_attempt3_trace' tests/fixtures/phase201_replay_corpus.py` returns 1.
    - `grep -c 'def synthesize_sustained_load_trace' tests/fixtures/phase201_replay_corpus.py` returns 1.
    - `grep -c 'phase201_attempt3_trace' tests/conftest.py` returns >= 1.
    - `python3 -c "from tests.fixtures.phase201_replay_corpus import load_attempt3_trace; print(len(load_attempt3_trace()))"` from repo root prints integer >= 800.
    - No import of `wanctl` at module top-level in `tests/fixtures/phase201_replay_corpus.py` (verify with `grep -v '^#' tests/fixtures/phase201_replay_corpus.py | grep -c '^from wanctl\|^import wanctl'` returns 0).
    - Hot-path slice still passes: `.venv/bin/pytest -o addopts='' tests/test_cake_signal.py tests/test_queue_controller.py tests/test_wan_controller.py tests/test_health_check.py -q` returns 0.
  </acceptance_criteria>
  <verify>
    <automated>.venv/bin/pytest -o addopts='' tests/test_phase201_corpus_fixtures.py -q &amp;&amp; .venv/bin/pytest -o addopts='' tests/test_cake_signal.py tests/test_queue_controller.py tests/test_wan_controller.py tests/test_health_check.py -q</automated>
  </verify>
  <done>Corpus loader works end-to-end; 8 smoke tests pass; conftest fixtures registered; hot-path slice green.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| repo → test runner | NDJSON corpus loaded from in-tree files committed to git; integrity via git history (no externally fetched data). |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-201-01 | Tampering | Replay corpus poisoning (planted samples in NDJSON) | accept | Corpus is committed to git under `.planning/phases/200-...`; mutation requires a tracked commit. RESEARCH §Security Domain Known Threat Patterns. |
| T-201-02 | Information Disclosure | Audit doc accidentally embeds real customer/IP data from capture | mitigate | Audit doc references field names only, not sample values; reviewer scans for IP/host/user before commit. |
| T-201-03 | Repudiation | Assumption A4 (~20 Mbit provisioned) recorded without operator confirmation | accept | A4 is explicitly marked `[ASSUMED]`; canary preflight is the live gate — failure surfaces operator-actionable abort. |
</threat_model>

<verification>
1. Corpus audit doc exists and grep-asserted to contain: `max_delay_delta_us` (>=3), `ASSUMED A4`, `Open Question 1`, `Open Question 2`, `885`.
2. Replay-corpus loader exposes `load_attempt3_trace()`, `load_attempt2_trace()`, `synthesize_sustained_load_trace()`, `synthesize_idle_trace()`.
3. Conftest registers session-scoped fixtures `phase201_attempt3_trace`, `phase201_attempt2_trace` and function-scoped `phase201_sustained_load_trace`, `phase201_idle_trace`.
4. Smoke test file passes with 8 assertions; hot-path regression slice green.
</verification>

<success_criteria>
- All Wave 0 fixtures importable from `tests.fixtures.phase201_replay_corpus`.
- Open Questions 1 and 2 documented with verdicts (1 = max_delay_delta_us GAP; 2 = A4 ASSUMED).
- No production-code edits in `src/wanctl/`.
- Hot-path slice unchanged (>= 578 tests pass).
</success_criteria>

<output>
After completion, create `.planning/phases/201-docsis-aware-ul-congestion-control/201-01-SUMMARY.md` with: corpus line counts, audit findings, fixture API surface, and a one-line note flagging that Plan 201-08 MUST add `max_delay_delta_us` to the canary capture shape.
</output>
