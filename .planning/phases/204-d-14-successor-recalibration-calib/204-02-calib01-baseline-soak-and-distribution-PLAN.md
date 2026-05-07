---
id: 204-02
phase: 204
plan: 02
type: execute
wave: 2
depends_on:
  - 204-01
files_modified:
  - scripts/soak_summary_aggregate.py
  - tests/test_phase_204_distribution.py
  - tests/fixtures/phase_204_synthetic_capture.ndjson
  - tests/fixtures/phase_204_synthetic_summary.json
  - .planning/phases/204-d-14-successor-recalibration-calib/soak/<CALIB_01_TS>/soak-capture.ndjson
  - .planning/phases/204-d-14-successor-recalibration-calib/soak/<CALIB_01_TS>/soak-summary.json
autonomous: false
production_canary: false
created: 2026-05-06
requirements:
  - CALIB-01
notes:
  - "Open Q9 (distribution analysis location): adopting researcher recommendation — extend `scripts/soak_summary_aggregate.py` with a new function `aggregate_completed_window_distribution()` rather than creating a separate `analyze_*.py` script. decision_basis: \"researcher recommendation, no operator confirmation\" (204-RESEARCH.md §Q9 lines 436-455)."
  - "OPEN QUESTION 1 (exact CALIB-02 threshold value) is NOT decided here — Plan 204-03 owns that decision. This plan only produces the distribution analysis the operator needs."
  - "OPEN QUESTION 2 (gate against `dwell_hold` slice vs total) is NOT decided here — Plan 204-03 owns that decision with the CALIB-01 distribution in hand. This plan must compute BOTH the total-distribution AND a per-cause-tag breakdown so the operator can decide informed."
must_haves:
  truths:
    - "scripts/soak_summary_aggregate.py contains `def aggregate_completed_window_distribution(`."
    - "aggregate_completed_window_distribution() returns dict with keys ['mean', 'p50', 'p95', 'p99', 'max', 'window_count'] (p99 is REQUIRED — research §Q1 lines 100-104 notes it was unavailable from v1.42 reference)."
    - "aggregate_completed_window_distribution() computes the distribution using a sibling boundary helper (NOT the existing aggregate_completed_windows reset-to-0 helper) because `ul_suppressions_completed_window_count` is monotonic-non-decreasing within a daemon lifetime — research §A7 / 204-PATTERNS.md line 90."
    - "aggregate_soak() output now includes a top-level `suppressions_completed_window_count_distribution` key with the dict above PLUS a per-cause-tag breakdown sub-dict `by_cause: {dwell_hold: {...}, backlog_recovery: {...}, other: {...}}` so Plan 204-03's slice-vs-total decision is data-backed."
    - "tests/test_phase_204_distribution.py exists with at least 3 test cases: (a) golden-byte comparison against tests/fixtures/phase_204_synthetic_summary.json; (b) p99 explicit-presence assertion; (c) by_cause breakdown sums match top-level total."
    - "tests/test_phase_204_distribution.py exits 0."
    - "CALIB-01 24h soak NDJSON captured at .planning/phases/204-d-14-successor-recalibration-calib/soak/<CALIB_01_TS>/soak-capture.ndjson with line count >= 86,000 (24h × 3600s × ~1Hz, accepting some loss)."
    - "soak-summary.json computed from the CALIB-01 NDJSON includes the new distribution block with all five percentile/stat fields populated."
    - "git diff b72b463..HEAD -- src/wanctl/ produces 0 lines (SAFE-07 invariant)."
  artifacts:
    - path: scripts/soak_summary_aggregate.py
      provides: "Extended with aggregate_completed_window_distribution() function for CALIB-01 stats."
      contains: "def aggregate_completed_window_distribution("
    - path: tests/test_phase_204_distribution.py
      provides: "Distribution-math replay tests (mirrors Phase 203 test_phase_203_replay.py:54-66 structure)."
      contains: "TestDistributionMath"
    - path: tests/fixtures/phase_204_synthetic_capture.ndjson
      provides: "Hand-crafted ~80-row NDJSON exercising distribution edge cases (multi-window, all three cause tags)."
    - path: tests/fixtures/phase_204_synthetic_summary.json
      provides: "Golden expected output for the synthetic NDJSON (byte-comparison oracle)."
    - path: .planning/phases/204-d-14-successor-recalibration-calib/soak/<CALIB_01_TS>/soak-capture.ndjson
      provides: "24h baseline soak raw capture from production cake-shaper under v1.43 binary."
    - path: .planning/phases/204-d-14-successor-recalibration-calib/soak/<CALIB_01_TS>/soak-summary.json
      provides: "Aggregated CALIB-01 distribution — input to Plan 204-03 operator-approval session."
      contains: "suppressions_completed_window_count_distribution"
  key_links:
    - from: "aggregate_completed_window_distribution()"
      to: "ul_suppressions_completed_window_count column"
      via: "value-changed-since-prev boundary detection (NOT reset-to-0 helper)"
      pattern: "ul_suppressions_completed_window_count"
    - from: "aggregate_completed_window_distribution()"
      to: "scripts/soak_summary_aggregate.py::percentile()"
      via: "reuses existing stdlib percentile helper for p50/p95/p99"
      pattern: "percentile\\("
    - from: "soak/<CALIB_01_TS>/soak-summary.json"
      to: "Plan 204-03 operator-approval session"
      via: "distribution stats are operator's input for CALIB-02 threshold derivation"
      pattern: "suppressions_completed_window_count_distribution"
---

<objective>
Add `aggregate_completed_window_distribution()` to `scripts/soak_summary_aggregate.py` so the CALIB-01 baseline soak can be summarized into a representative completed-window suppression-count distribution. Capture a clean 24h Spectrum baseline soak on cake-shaper under the v1.43 binary deployed in Plan 204-01. Compute the soak summary and stage the distribution stats as Plan 204-03's input.

Purpose: CALIB-02 (Plan 204-03) is an operator-judgment session — the operator must read CALIB-01's distribution and lock the gate threshold. This plan delivers the distribution and the per-cause-tag breakdown the operator needs to make the slice-vs-total decision (research §Risk 2 / open Q2).

Output: Extended aggregator with a new public function, golden-fixture replay tests, a 24h NDJSON capture, and a `soak-summary.json` containing the new `suppressions_completed_window_count_distribution` block (with `mean`, `p50`, `p95`, `p99`, `max`, `window_count`, and a `by_cause` sub-dict). Zero `src/wanctl/` source diff (SAFE-07).
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/ROADMAP.md
@.planning/REQUIREMENTS.md
@.planning/phases/204-d-14-successor-recalibration-calib/204-RESEARCH.md
@.planning/phases/204-d-14-successor-recalibration-calib/204-PATTERNS.md
@.planning/phases/204-d-14-successor-recalibration-calib/204-VALIDATION.md
@.planning/phases/204-d-14-successor-recalibration-calib/204-01-SUMMARY.md
@scripts/soak_summary_aggregate.py
@scripts/soak-capture.sh
@tests/test_phase_203_replay.py
@.planning/milestones/v1.43-phases/203-target-edge-churn-instrumentation-obsv/203-02-soak-summary-aggregator-and-replay-PLAN.md

<interfaces>
<!-- Existing aggregator helpers Plan 204-02 must REUSE (do not reimplement) — extracted from scripts/soak_summary_aggregate.py at HEAD. -->

From scripts/soak_summary_aggregate.py:
```python
DEFAULT_BUCKETS_US = [0, 1000, 3000, 6000, 10000, 15000, 20000, 30000, 45000, 60000, 100000, 250000]  # line 83
ZONES = ("GREEN", "YELLOW", "SOFT_RED", "RED")  # line 84
CAUSES = ("dwell_hold", "backlog_recovery", "other")  # line 85

def aggregate_completed_windows(snapshots: list[int]) -> list[int]:  # line 52
    """Reset-to-0 boundary detector for the legacy `suppressions_per_min` column.
    Phase 204 must NOT reuse this for the new column — see 204-RESEARCH.md §A7."""

def percentile(values, p: float) -> float:  # line 70
    """Linear-interpolation percentile, NumPy-free, returns 0.0 for empty input."""

def histogram(values, buckets: list[int]) -> list[int]:  # line 86
    """Last cell is overflow."""

def _build_cell(values: list[int], buckets: list[int]) -> dict[str, Any]:  # line 120
    """Returns {p50, p95, p99, max, count, histogram}."""

def load_ndjson(path: Path) -> list[dict[str, Any]]:  # line 136

def aggregate_load_rtt_delta(rows, buckets: list[int] | None = None) -> dict[str, Any]:  # line 148
    """Phase 203 reference shape — copy this structural pattern."""

def aggregate_soak(ndjson_path: Path, buckets: list[int] | None = None) -> dict[str, Any]:  # line 239
    """Top-level aggregator. Plan 204-02 extends to add the new distribution key."""
```

From scripts/soak-capture.sh:48-57 (capture-script field schema — already live since Phase 203):
- ul_suppressions_completed_window_count (line 55) — monotonic non-decreasing per daemon lifetime
- ul_suppressions_completed_window_by_cause (line 56) — JSON object {dwell_hold: int, backlog_recovery: int, other: int}
- ul_suppressions_lifetime_by_cause (line 57)
- load_rtt_delta_us (lines 48-53)
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Author synthetic fixture + add aggregate_completed_window_distribution() with replay tests</name>
  <read_first>
    - scripts/soak_summary_aggregate.py:1-260 (entire current aggregator — full file is ~297 lines; understand existing helpers verbatim)
    - 204-PATTERNS.md lines 51-135 (extension pattern + by-zone/cause analog at aggregate_load_rtt_delta lines 148-174)
    - 204-PATTERNS.md lines 253-330 (test class structure to clone from tests/test_phase_203_replay.py:1-66)
    - 204-RESEARCH.md §Q9 lines 436-455 (function signature recommendation)
    - 204-RESEARCH.md §A7 / 204-PATTERNS.md line 90 (sibling boundary helper rationale: ul_suppressions_completed_window_count is monotonic-non-decreasing — use "value-changed-since-prev" detection, NOT the reset-to-0 helper)
    - 204-RESEARCH.md §Risk 2 lines 709-722 (per-cause-tag breakdown is load-bearing for Plan 204-03)
  </read_first>
  <files>scripts/soak_summary_aggregate.py, tests/test_phase_204_distribution.py, tests/fixtures/phase_204_synthetic_capture.ndjson, tests/fixtures/phase_204_synthetic_summary.json</files>
  <behavior>
    Test 1 (golden-fixture): aggregate_soak(synthetic_ndjson) JSON byte-equals tests/fixtures/phase_204_synthetic_summary.json (sort_keys, indent=2).
    Test 2 (p99 explicit): suppressions_completed_window_count_distribution.p99 is present and is a number (Phase 204 explicitly requires p99 — research §Q1 lines 100-104).
    Test 3 (by_cause breakdown): sum of by_cause.dwell_hold.window_count + by_cause.backlog_recovery.window_count + by_cause.other.window_count uses the SAME boundary count as the top-level window_count (i.e. the per-cause slice operates on the same set of completed windows).
    Test 4 (window_count > 0): synthetic fixture must produce at least 5 completed-window boundaries so percentile math is meaningful.
    Test 5 (boundary detection rejects monotonic spans): a row where ul_suppressions_completed_window_count equals the previous row's value contributes nothing new (no double-counting).
  </behavior>
  <action>
    Step 1: Hand-author `tests/fixtures/phase_204_synthetic_capture.ndjson` (~80 rows). Each row is a JSON object on one line. Required columns per row (mirror what scripts/soak-capture.sh emits at lines 48-57):
    - `t_wall`: ISO UTC string
    - `t_monotonic`: float (seconds since fictional capture start; ascending)
    - `ul_suppressions_completed_window_count`: int (monotonic non-decreasing within the synthetic daemon lifetime; jumps at boundary rows)
    - `ul_suppressions_completed_window_by_cause`: object `{"dwell_hold": int, "backlog_recovery": int, "other": int}` (matches the totals on each boundary row)
    - `ul_suppressions_lifetime_by_cause`: object (monotonic) — needed for compatibility with the existing aggregate_by_zone_cause helper
    - Other Phase 203 columns (load_rtt_delta_us, zone, etc.) can be present-but-zero or omitted; `aggregate_completed_window_distribution()` must ignore them.

    Design ~7 boundary jumps at fictional `t_monotonic` values 60, 120, 180, 240, 300, 360, 420 with completed-window count values e.g. [3, 5, 12, 8, 15, 4, 25] producing a deterministic distribution with non-trivial p95/p99/max separation.

    Step 2: Add to `scripts/soak_summary_aggregate.py` (place between `aggregate_load_rtt_delta` at line 174 and `aggregate_by_zone_cause` at line 177; reuse `percentile`, `_build_cell`, `DEFAULT_BUCKETS_US`):

    ```python
    def _completed_window_boundaries(values: list[int]) -> list[int]:
        """Return the list of completed-window count values, one per boundary.

        ul_suppressions_completed_window_count is monotonic non-decreasing per
        daemon lifetime with discrete jumps at each 60s boundary (per Phase 202
        METRIC-01 semantics). Boundary detection: emit a count whenever the
        value changes from the previous sample (and reset on daemon restart
        signaled by a decrease).

        See 204-RESEARCH.md §A7 / 204-PATTERNS.md line 90 — must NOT reuse
        aggregate_completed_windows() (reset-to-0 detector for legacy
        suppressions_per_min column).
        """
        boundaries: list[int] = []
        prev = None
        for v in values:
            if prev is None:
                prev = v
                continue
            if v < prev:
                # Daemon restart; treat as new lifetime, reset baseline
                prev = v
                continue
            if v > prev:
                boundaries.append(v - prev)
                prev = v
        return boundaries


    def aggregate_completed_window_distribution(
        rows: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """CALIB-01 distribution stats from ul_suppressions_completed_window_count.

        Returns a dict with mean, p50, p95, p99, max, window_count plus a
        by_cause breakdown computed from ul_suppressions_completed_window_by_cause.
        Per Plan 204-03 (open Q2), the by_cause slice exists so the operator
        can decide gate-against-dwell-hold-slice vs gate-against-total
        with data in hand (research §Risk 2).
        """
        col = [int(r["ul_suppressions_completed_window_count"]) for r in rows
               if "ul_suppressions_completed_window_count" in r and r["ul_suppressions_completed_window_count"] is not None]
        boundaries = _completed_window_boundaries(col)
        result: dict[str, Any] = {
            "window_count": len(boundaries),
            "mean": (sum(boundaries) / len(boundaries)) if boundaries else 0.0,
            "p50": percentile(boundaries, 50),
            "p95": percentile(boundaries, 95),
            "p99": percentile(boundaries, 99),
            "max": max(boundaries) if boundaries else 0,
        }
        # by_cause breakdown — same boundary structure, per cause
        by_cause: dict[str, dict[str, Any]] = {}
        for cause in CAUSES:
            cause_col: list[int] = []
            for r in rows:
                blob = r.get("ul_suppressions_completed_window_by_cause")
                if isinstance(blob, dict) and cause in blob and blob[cause] is not None:
                    cause_col.append(int(blob[cause]))
            cause_boundaries = _completed_window_boundaries(cause_col)
            by_cause[cause] = {
                "window_count": len(cause_boundaries),
                "mean": (sum(cause_boundaries) / len(cause_boundaries)) if cause_boundaries else 0.0,
                "p50": percentile(cause_boundaries, 50),
                "p95": percentile(cause_boundaries, 95),
                "p99": percentile(cause_boundaries, 99),
                "max": max(cause_boundaries) if cause_boundaries else 0,
            }
        result["by_cause"] = by_cause
        return result
    ```

    Step 3: Extend `aggregate_soak()` (line 239) to add the new top-level key. Modify the return dict to include:
    ```python
    "suppressions_completed_window_count_distribution": aggregate_completed_window_distribution(rows),
    ```
    Place this key immediately after `"load_rtt_delta_us_by_zone_cause"` so existing keys' positions are stable.

    Step 4: Hand-compute the expected output for the synthetic fixture and write `tests/fixtures/phase_204_synthetic_summary.json` (use `python -c "import json; from scripts.soak_summary_aggregate import aggregate_soak; from pathlib import Path; print(json.dumps(aggregate_soak(Path('tests/fixtures/phase_204_synthetic_capture.ndjson')), indent=2, sort_keys=True))"` to bootstrap; then manually verify the math against the fixture's hand-designed boundary jumps).

    Step 5: Author `tests/test_phase_204_distribution.py` cloning the structure of `tests/test_phase_203_replay.py:1-66` (use the same `_load_module` helper + `aggregator` fixture; substitute `phase_203_*` → `phase_204_*` for fixture names). Implement Tests 1-5 from the `<behavior>` block.

    Step 6: Phase 203 fixture refresh — extending `aggregate_soak()` adds a new top-level key; `tests/fixtures/phase_203_synthetic_summary.json` must be regenerated to include the new key with empty/zero values (since the Phase 203 synthetic fixture has no `ul_suppressions_completed_window_count` column, the new block will be all zeros). Run `tests/fixtures/_phase_203_generator.py` to regenerate, then re-run aggregator and update the golden JSON. Per 204-RESEARCH.md §Risk 7 lines 751-755 this is an explicit deliverable.

    No `src/wanctl/` files touched.
  </action>
  <verify>
    <automated>.venv/bin/pytest tests/test_phase_204_distribution.py tests/test_phase_203_replay.py tests/test_phase_202_replay.py -v &amp;&amp; bash scripts/check-safe07-source-diff.sh &amp;&amp; .venv/bin/pytest -o addopts='' tests/test_cake_signal.py tests/test_queue_controller.py tests/test_wan_controller.py tests/test_health_check.py -q</automated>
  </verify>
  <acceptance_criteria>
    - `grep -c '^def aggregate_completed_window_distribution(' scripts/soak_summary_aggregate.py` returns 1 (using `grep -v '^#' | grep -c` if needed; since regex is anchored on `^def` no comment filtering needed)
    - `grep -c '^def _completed_window_boundaries(' scripts/soak_summary_aggregate.py` returns 1
    - `tests/test_phase_204_distribution.py` exists; `.venv/bin/pytest tests/test_phase_204_distribution.py -v` exits 0 with at least 5 tests passing
    - `tests/test_phase_203_replay.py` still passes (Phase 203 golden fixture refreshed for the new top-level key per 204-RESEARCH.md §Risk 7)
    - `tests/test_phase_202_replay.py` still passes
    - Hot-path slice exits 0
    - `bash scripts/check-safe07-source-diff.sh` exits 0
    - `tests/fixtures/phase_204_synthetic_capture.ndjson` and `tests/fixtures/phase_204_synthetic_summary.json` both exist
  </acceptance_criteria>
  <done>Aggregator has the new function; Phase 204 + Phase 203 + Phase 202 + hot-path tests all green; SAFE-07 invariant clean.</done>
</task>

<task type="checkpoint:human-verify" gate="blocking">
  <name>Task 2: Operator launches CALIB-01 24h baseline soak</name>
  <read_first>
    - 204-PATTERNS.md "Soak harness invocation (Plan 204-02 + Plan 204-05)" lines 609-640
    - .planning/milestones/v1.42-phases/201-docsis-aware-ul-congestion-control/201-16-soak-and-closeout-PLAN.md (24h soak protocol — tmux, scp evidence-back)
    - 204-VALIDATION.md "Manual-Only Verifications" row "24h Spectrum baseline soak (CALIB-01)"
  </read_first>
  <files>(remote /var/tmp/wanctl-soak-${CALIB_01_TS}/soak-capture.ndjson on cake-shaper; .planning/phases/204-d-14-successor-recalibration-calib/soak/${CALIB_01_TS}/ on local)</files>
  <what-built>
    The v1.43.0 binary has been live on cake-shaper since Plan 204-01. The `scripts/soak-capture.sh` harness from Phase 203 already emits the seven Phase 204 fields. Ready to launch the CALIB-01 24h baseline soak.
  </what-built>
  <how-to-verify>
    1. Confirm cake-shaper /health is still reporting 1.43.0: `ssh cake-shaper 'curl -s http://127.0.0.1:9101/health | jq -r .version'` returns `1.43.0`.
    2. Operator picks `CALIB_01_TS` (recommend `date -u +%Y%m%dT%H%M%SZ` at the moment of decision).
    3. Operator launches the soak per 204-PATTERNS.md lines 619-637:
       ```bash
       SOAK_TS=$(date -u +%Y%m%dT%H%M%SZ)
       mkdir -p .planning/phases/204-d-14-successor-recalibration-calib/soak/${SOAK_TS}
       scp scripts/soak-capture.sh cake-shaper:/tmp/soak-capture.sh
       ssh cake-shaper "chmod +x /tmp/soak-capture.sh"
       ssh cake-shaper "tmux new-session -d -s wanctl-soak \"HEALTH_URL=http://127.0.0.1:9101/health bash /tmp/soak-capture.sh ${SOAK_TS} 2>&amp;1 | tee /tmp/soak-capture.log\""
       ssh cake-shaper "tmux list-sessions | grep wanctl-soak"      # verify started
       sleep 5
       ssh cake-shaper "wc -l /var/tmp/wanctl-soak-${SOAK_TS}/soak-capture.ndjson"  # >= 1
       ```
    4. Operator schedules T+24h finish: `ssh cake-shaper 'systemd-run --user --on-active=24h30m -- tmux kill-session -t wanctl-soak'` (mirrors Phase 198 pattern).
    5. Operator decides: approved (24h soak begins; this task ends, Task 3 waits for the wall clock) or rejected (record reason; abort plan).
  </how-to-verify>
  <resume-signal>Type "approved: CALIB-01 soak started, ts=&lt;SOAK_TS&gt;" or "rejected: &lt;reason&gt;".</resume-signal>
  <acceptance_criteria>
    - Operator typed "approved" with literal `SOAK_TS` value
    - Local directory `.planning/phases/204-d-14-successor-recalibration-calib/soak/${SOAK_TS}/` exists
    - Remote tmux session `wanctl-soak` running on cake-shaper at start
    - Pre-soak floor-hit count and `/health` snapshot recorded in operator notes
  </acceptance_criteria>
  <done>Soak running; 24h wall clock has begun; Task 3 will pull the capture and aggregate when complete.</done>
</task>

<task type="checkpoint:human-verify" gate="blocking">
  <name>Task 3: Pull CALIB-01 capture, run aggregator, commit distribution</name>
  <read_first>
    - 204-PATTERNS.md "Soak harness invocation" lines 609-640 (scp-back pattern)
    - scripts/soak_summary_aggregate.py main() argparse (lines 272-293)
    - 204-RESEARCH.md §Risk 2 lines 709-722 (operator must compare dwell_hold vs backlog_recovery slices when reading the distribution)
  </read_first>
  <files>.planning/phases/204-d-14-successor-recalibration-calib/soak/${CALIB_01_TS}/soak-capture.ndjson, .planning/phases/204-d-14-successor-recalibration-calib/soak/${CALIB_01_TS}/soak-summary.json</files>
  <what-built>
    The 24h CALIB-01 baseline soak has completed on cake-shaper. The capture lives at `/var/tmp/wanctl-soak-${CALIB_01_TS}/soak-capture.ndjson` on the remote.
  </what-built>
  <how-to-verify>
    1. Confirm the soak completed (line count check):
       ```bash
       ssh cake-shaper "wc -l /var/tmp/wanctl-soak-${CALIB_01_TS}/soak-capture.ndjson"
       # MUST be >= 86,000 (24h × ~1Hz with some loss tolerance — 204-VALIDATION.md row "24h CALIB-01 soak runs to completion")
       ```
    2. Pull the capture back to local:
       ```bash
       scp cake-shaper:/var/tmp/wanctl-soak-${CALIB_01_TS}/soak-capture.ndjson \
           .planning/phases/204-d-14-successor-recalibration-calib/soak/${CALIB_01_TS}/soak-capture.ndjson
       wc -l .planning/phases/204-d-14-successor-recalibration-calib/soak/${CALIB_01_TS}/soak-capture.ndjson
       ```
    3. Run the aggregator:
       ```bash
       .venv/bin/python scripts/soak_summary_aggregate.py \
         .planning/phases/204-d-14-successor-recalibration-calib/soak/${CALIB_01_TS}/soak-capture.ndjson \
         -o .planning/phases/204-d-14-successor-recalibration-calib/soak/${CALIB_01_TS}/soak-summary.json
       ```
    4. Inspect the new distribution block:
       ```bash
       jq '.suppressions_completed_window_count_distribution' \
         .planning/phases/204-d-14-successor-recalibration-calib/soak/${CALIB_01_TS}/soak-summary.json
       ```
       The operator must read:
       - top-level `mean / p50 / p95 / p99 / max / window_count`
       - `by_cause.dwell_hold.{mean,p99,max}`
       - `by_cause.backlog_recovery.{mean,p99,max}`
       - `by_cause.other.{mean,p99,max}`
       Compare `by_cause.backlog_recovery.mean` vs `by_cause.dwell_hold.mean` — if backlog_recovery >> dwell_hold, the open-Q2 slice-vs-total decision becomes load-bearing for Plan 204-03 (research §Risk 2 lines 709-722).
    5. Operator decides: approved (commit; proceed to Plan 204-03) or rejected (e.g. soak was confounded by infrastructure issues — re-run CALIB-01).
  </how-to-verify>
  <resume-signal>Type "approved: CALIB-01 distribution captured, p99=&lt;value&gt;, dwell_hold_p99=&lt;value&gt;, backlog_recovery_p99=&lt;value&gt;" or "rejected: &lt;reason&gt;".</resume-signal>
  <acceptance_criteria>
    - `wc -l .planning/phases/204-d-14-successor-recalibration-calib/soak/${CALIB_01_TS}/soak-capture.ndjson` returns >= 86000
    - `jq -e '.suppressions_completed_window_count_distribution.p99 != null and .suppressions_completed_window_count_distribution.window_count > 100' .planning/phases/204-d-14-successor-recalibration-calib/soak/${CALIB_01_TS}/soak-summary.json` exits 0
    - `jq -e '.suppressions_completed_window_count_distribution.by_cause.dwell_hold != null and .suppressions_completed_window_count_distribution.by_cause.backlog_recovery != null' .planning/phases/204-d-14-successor-recalibration-calib/soak/${CALIB_01_TS}/soak-summary.json` exits 0
    - Operator typed "approved" with the four numeric values in the resume signal (these become Plan 204-03's CALIB-01 distribution reference)
    - Both the NDJSON and the soak-summary.json are present in the local soak directory
  </acceptance_criteria>
  <done>CALIB-01 24h baseline distribution captured, aggregated, committed. Plan 204-03 unblocked.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| local dev → cake-shaper SSH | Soak script upload + tmux launch + capture scp-back. Same trust boundary as Plan 204-01. |
| cake-shaper /health → soak-capture.sh | Local-only HTTP fetch (127.0.0.1:9101); no external exposure. |
| Synthetic NDJSON fixture | Hand-authored test data; checked into git; no PII. |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-204-02-01 | Tampering | scripts/soak_summary_aggregate.py extension | mitigate | Golden-fixture replay test + Phase 203 + Phase 202 regression suite catches output-shape drift; 204-RESEARCH.md §Risk 7 mandates fixture refresh as explicit deliverable. |
| T-204-02-02 | Information Disclosure | soak NDJSON contains operational metrics | accept | Existing Phase 203 capture-script invariant — same path, same access controls. No new exposure. |
| T-204-02-03 | Denial of Service | 24h soak job on cake-shaper | accept | Same risk profile as Phase 198 / 201-16 24h soaks; tmux + systemd-run kill-timer pattern. |
</threat_model>

<verification>
- `.venv/bin/pytest tests/test_phase_204_distribution.py tests/test_phase_203_replay.py tests/test_phase_202_replay.py -v` exits 0
- Hot-path slice green
- `bash scripts/check-safe07-source-diff.sh` exits 0
- CALIB-01 NDJSON line count >= 86,000
- `soak-summary.json::suppressions_completed_window_count_distribution.p99` is populated
- `by_cause.{dwell_hold,backlog_recovery,other}` sub-dicts all present
</verification>

<success_criteria>
Aggregator extended with `aggregate_completed_window_distribution()`; replay tests green; CALIB-01 24h capture lives in the phase directory; soak-summary.json contains the new distribution block with p99 and the per-cause-tag breakdown the operator needs to make the open-Q2 slice-vs-total decision in Plan 204-03. SAFE-07 source-diff invariant clean.
</success_criteria>

<output>
After completion, create `.planning/phases/204-d-14-successor-recalibration-calib/204-02-SUMMARY.md` recording:
- The literal `CALIB_01_TS` value
- NDJSON line count
- Top-level distribution stats (mean, p50, p95, p99, max, window_count) cited verbatim
- by_cause sub-dict cited verbatim (the operator's input for Plan 204-03 open-Q2 decision)
- Hand-off pointer to Plan 204-03 (CALIB-02 operator-approval session)
</output>
