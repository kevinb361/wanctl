---
id: 204-04
phase: 204
plan: 04
type: execute
wave: 4
depends_on:
  - 204-03
files_modified:
  - scripts/soak_summary_aggregate.py
  - tests/test_phase_204_watchdog.py
  - tests/test_phase_204_replay.py
  - tests/fixtures/phase_204_synthetic_summary.json
  - docs/SOAK_HARNESS.md
  - CHANGELOG.md
autonomous: true
production_canary: false
created: 2026-05-06
requirements:
  - CALIB-03
  - SAFE-07
notes:
  - "Open Q5 (Deploy 2 ritual symmetry): adopting researcher recommendation — explicitly degenerate (named asymmetry, NOT silent skip). Deploy 2 is harness-only (no production binary change). The plan body includes a mandatory `## Why Deploy 2 Looks Different` section at Task 4. decision_basis: \"researcher recommendation, no operator confirmation\" (204-RESEARCH.md §Q7 line 389 + §Risk 4 lines 730-734)."
  - "Open Q6 (one transition cycle = one milestone): adopting researcher recommendation — v1.43 emits BOTH legacy + new; v1.44 follow-up commit drops legacy. Captured here as a TODO entry created at v1.43 closeout (Plan 204-06). decision_basis: \"researcher recommendation, no operator confirmation\" (204-RESEARCH.md §Q5 lines 224-237)."
  - "All four open questions for which researcher provides defaults (Q3 version 1.43.0, Q4 external JSON, Q5 degenerate-explained, Q6 one-milestone) are now adopted across the plan set."
must_haves:
  truths:
    - "scripts/soak_summary_aggregate.py contains `def aggregate_watchdog(`."
    - "scripts/soak_summary_aggregate.py contains `def load_calib_02_constants(`."
    - "aggregate_watchdog() returns dict with keys ['secondary_gate_legacy', 'secondary_gate_completed_window']."
    - "secondary_gate_legacy.value matches the v1.42 oracle 6.466842364880155 within abs=1e-6 when run against the v1.42 reference NDJSON at .planning/milestones/v1.42-phases/201-docsis-aware-ul-congestion-control/soak/20260505T132736Z/soak-capture.ndjson (oracle source: same path /suppression-stats.json:6, value `suppressions_per_min_mean: 6.466842364880155`)."
    - "secondary_gate_completed_window.value, .threshold, .verdict, .statistic, .gate_column all populated from scripts/calib_02_threshold.json (Plan 204-03 output)."
    - "aggregate_soak() top-level output includes both new gate keys; tests/fixtures/phase_204_synthetic_summary.json regenerated; tests/test_phase_203_replay.py still passes."
    - "tests/test_phase_204_watchdog.py contains TestV142WatchdogRegression class asserting secondary_gate_legacy.value == 6.466842364880155 (abs=1e-6)."
    - "tests/test_phase_204_watchdog.py contains synthetic PASS/FAIL branch coverage for secondary_gate_completed_window verdict."
    - "tests/test_phase_204_replay.py exists and exits 0 (covers v1.42 NDJSON regression for the watchdog math, mirroring Phase 203 TestV142NdjsonRegression pattern)."
    - "docs/SOAK_HARNESS.md has a new `## Watchdog computation transition (CALIB-03)` section documenting the dual-emission pattern with the JSON shape from 204-RESEARCH.md §Q5 lines 240-259."
    - "CHANGELOG.md v1.43-dev section has Phase 204 / CALIB-03 entry per 204-PATTERNS.md lines 651-661."
    - "git diff b72b463..HEAD -- src/wanctl/ produces 0 lines (SAFE-07 invariant)."
    - "Deploy 2 is documented as harness-only (no production binary change). Capture-script (scripts/soak-capture.sh) UNCHANGED — already emits all needed columns since Phase 203."
  artifacts:
    - path: scripts/soak_summary_aggregate.py
      provides: "Extended with aggregate_watchdog() (dual-emission per CALIB-03) and load_calib_02_constants() loader."
      contains: "def aggregate_watchdog("
    - path: tests/test_phase_204_watchdog.py
      provides: "Watchdog tests: v1.42 oracle regression + synthetic PASS/FAIL branches."
      contains: "TestV142WatchdogRegression"
    - path: tests/test_phase_204_replay.py
      provides: "v1.42 NDJSON regression for watchdog (sibling to Phase 203 test_phase_203_replay.py::TestV142NdjsonRegression pattern)."
      contains: "test_v142"
    - path: docs/SOAK_HARNESS.md
      provides: "Documents the dual-emission watchdog transition contract for CALIB-03."
      contains: "Watchdog computation transition"
    - path: CHANGELOG.md
      provides: "v1.43-dev entry under CALIB-03."
      contains: "CALIB-03"
  key_links:
    - from: "aggregate_watchdog()"
      to: "scripts/calib_02_threshold.json"
      via: "load_calib_02_constants() reads operator-approved threshold/statistic/gate_column"
      pattern: "calib_02_threshold.json"
    - from: "aggregate_watchdog()"
      to: "v1.42 oracle 6.466842364880155"
      via: "verbatim Python port of v1.42 Plan 201-16 jq pipeline (lines 96-131 of 201-16-soak-and-closeout-PLAN.md); secondary_gate_legacy.value MUST match"
      pattern: "6\\.466842364880155"
    - from: "aggregate_soak()"
      to: "top-level secondary_gate_legacy + secondary_gate_completed_window keys"
      via: "extension of aggregate_soak return dict to surface both gates"
      pattern: "secondary_gate_(legacy|completed_window)"
---

<objective>
Promote the v1.42 Plan 201-16 inline-jq watchdog computation to a versioned Python function `aggregate_watchdog()` in `scripts/soak_summary_aggregate.py`. Wire the operator-approved constants from `scripts/calib_02_threshold.json` (Plan 204-03 output). Emit BOTH the legacy live-counter mean (verbatim port — must match the v1.42 oracle `6.466842364880155`) AND the new completed-window count statistic side-by-side for one transition cycle (= v1.43 milestone, per researcher recommendation on open Q6). Land regression tests against the v1.42 reference NDJSON. Update docs and CHANGELOG. Deploy 2 is a git commit — no production binary change.

Purpose: CALIB-03 is the load-bearing harness change for the milestone. Plan 204-05's verification soak depends on `aggregate_watchdog()` to render the dual-gate verdict in `soak-summary.json`. Without this plan, CALIB-04 cannot pass cleanly because there's no machine-readable D-14-successor verdict in the soak summary.

Output: Extended aggregator with `aggregate_watchdog()` + `load_calib_02_constants()`; two new test files; refreshed Phase 203 + Phase 204 golden fixtures; docs section; CHANGELOG entry. Zero `src/wanctl/` source diff. Capture script unchanged.
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
@.planning/phases/204-d-14-successor-recalibration-calib/204-03-SUMMARY.md
@.planning/phases/204-d-14-successor-recalibration-calib/204-CALIB-02-OPERATOR-APPROVAL.md
@scripts/soak_summary_aggregate.py
@scripts/calib_02_threshold.json
@tests/test_phase_203_replay.py
@docs/SOAK_HARNESS.md
@CHANGELOG.md
@.planning/milestones/v1.42-phases/201-docsis-aware-ul-congestion-control/201-16-soak-and-closeout-PLAN.md

<interfaces>
<!-- v1.42 inline-jq pipeline being ported to Python — verbatim from 201-16-soak-and-closeout-PLAN.md:96-131 (cited in 204-PATTERNS.md lines 140-159). -->

```jq
jq -s '
  sort_by(.t_monotonic) as $rows
  | ($rows[0].t_monotonic) as $t_start
  | ($rows[-1].t_monotonic) as $t_end
  | (($t_end - $t_start) / 60.0 | floor) as $window_count
  | reduce range(0; $window_count) as $w (
      {windows: []};
      .windows += [
        ([$rows[]
          | select(.t_monotonic >= ($t_start + ($w * 60)))
          | select(.t_monotonic <  ($t_start + (($w + 1) * 60)))
          | .suppressions_per_min // 0
         ] as $vals
         | if ($vals | length) > 0 then ($vals | add / length) else null end)
      ]
    )
  | .windows |= map(select(. != null))
  | { ... suppressions_per_min_mean ... }
' "$SOAK_DIR/soak-capture.ndjson" > "$SOAK_DIR/suppression-stats.json"
```

<!-- v1.42 oracle (regression target for secondary_gate_legacy.value) -->
File: .planning/milestones/v1.42-phases/201-docsis-aware-ul-congestion-control/soak/20260505T132736Z/suppression-stats.json
Line 6: "suppressions_per_min_mean": 6.466842364880155

<!-- aggregate_watchdog() proposed signature — 204-RESEARCH.md §Q4 lines 207-220 + §Code Examples lines 781-799 -->

```python
def aggregate_watchdog(
    rows: list[dict[str, Any]],
    *,
    legacy_threshold: float = 5.0,        # v1.42 D-14 — preserved for transition emission
    new_threshold: int,                   # CALIB-02 — NO default; operator must supply (or load from JSON)
    statistic: str = "p99",               # CALIB-02 — operator-chosen
    gate_column: str = "suppressions_completed_window_count_distribution",  # open-Q2
) -> dict[str, Any]:
```

<!-- Phase 203 test class structure to clone — tests/test_phase_203_replay.py:87-122 -->

class TestV142NdjsonRegression:
    def test_v142_diagnostic_distribution_matches_inline_jq(self, aggregator):
        if not V142_NDJSON.exists() or not V142_SUMMARY.exists():
            pytest.skip(...)
        result = aggregator.aggregate_soak(V142_NDJSON)
        ...
        assert ours["rtt_integral_ms_s"]["mean"] == pytest.approx(v142_diag["..."]["mean"], rel=0.01)

<!-- Phase 204 by 204-PATTERNS.md lines 350-368 -->

class TestV142WatchdogRegression:
    def test_legacy_value_matches_inline_jq_oracle(self, aggregator):
        rows = aggregator.load_ndjson(V142_NDJSON)
        result = aggregator.aggregate_watchdog(
            rows,
            legacy_threshold=5.0,
            new_threshold=75,    # placeholder; CALIB-02 supplies real value via JSON in production
            statistic="p99",
        )
        assert result["secondary_gate_legacy"]["value"] == pytest.approx(
            6.466842364880155, abs=1e-6
        )

<!-- Output shape — 204-RESEARCH.md §Q5 lines 240-259 (verbatim) -->

"secondary_gate_legacy": {
  "name": "ul_hysteresis_suppression_rate_per_60s_mean (legacy live-counter-snapshot mean)",
  "computation": "Mean of live-counter snapshots within each 60s window, then mean across windows. Verbatim port of v1.42 Plan 201-16 jq pipeline. PRESERVED FOR ONE TRANSITION CYCLE — drops in v1.44.",
  "value": <float>,
  "threshold": 5.0,
  "verdict": "<pass|fail>",
  "note": "This metric is metric-semantically broken; see Phase 201 RETRO Lesson #1. Use secondary_gate_completed_window for actual gating."
},
"secondary_gate_completed_window": {
  "name": "ul_suppressions_completed_window_count_<statistic>",
  "computation": "<statistic> of per-completed-window suppression counts over the soak window. Replaces secondary_gate_legacy at v1.44.",
  "value": <number>,
  "threshold": <CALIB_02 integer>,
  "statistic": "<from JSON>",
  "headroom_factor": <from JSON>,
  "gate_column": "<from JSON>",
  "verdict": "<pass|fail>",
  "operator_approval": ".planning/phases/204-d-14-successor-recalibration-calib/204-CALIB-02-OPERATOR-APPROVAL.md"
}
```
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Add load_calib_02_constants() + aggregate_watchdog() to scripts/soak_summary_aggregate.py</name>
  <read_first>
    - scripts/soak_summary_aggregate.py:1-end (full file — confirm helper signatures and aggregate_soak() integration point)
    - 204-PATTERNS.md lines 136-211 (aggregate_watchdog() pattern with verbatim jq excerpt and Python skeleton)
    - 204-PATTERNS.md lines 215-249 (scripts/calib_02_threshold.json schema + loader pattern)
    - 204-RESEARCH.md §Q5 lines 240-259 (output JSON shape)
    - 204-RESEARCH.md §Code Examples lines 763-855 (Python skeletons — copy verbatim)
    - .planning/milestones/v1.42-phases/201-docsis-aware-ul-congestion-control/201-16-soak-and-closeout-PLAN.md:96-131 (verbatim jq pipeline being ported)
    - .planning/milestones/v1.42-phases/201-docsis-aware-ul-congestion-control/soak/20260505T132736Z/suppression-stats.json (line 6: oracle value 6.466842364880155)
    - scripts/calib_02_threshold.json (Plan 204-03 output — operator-approved constants)
  </read_first>
  <files>scripts/soak_summary_aggregate.py</files>
  <behavior>
    Test 1 (loader): load_calib_02_constants() returns the dict shape from scripts/calib_02_threshold.json when the file exists; returns the documented fallback when absent.
    Test 2 (legacy oracle): aggregate_watchdog(rows_from_v142_ndjson, legacy_threshold=5.0, new_threshold=75, statistic="p99").secondary_gate_legacy.value == 6.466842364880155 ± 1e-6.
    Test 3 (legacy verdict): with v1.42 oracle 6.467 against threshold 5.0 → secondary_gate_legacy.verdict == "fail".
    Test 4 (new gate from JSON): when scripts/calib_02_threshold.json supplies threshold=125, statistic="p99", gate_column="by_cause.dwell_hold", and synthetic distribution p99 = 100, the secondary_gate_completed_window.verdict == "pass" and value == 100.
    Test 5 (new gate FAIL): when synthetic p99 = 200 against threshold 125 → secondary_gate_completed_window.verdict == "fail".
  </behavior>
  <action>
    Step 1: Add the loader at the top of `scripts/soak_summary_aggregate.py` (after the existing constants block at lines 83-85; verbatim from 204-PATTERNS.md lines 220-233):

    ```python
    CALIB_02_DEFAULTS_PATH = Path(__file__).parent / "calib_02_threshold.json"


    def load_calib_02_constants() -> dict[str, Any]:
        """Load CALIB-02 operator-approved constants from scripts/calib_02_threshold.json.

        Hard-coded fallback for tests / pre-approval state per 204-PATTERNS.md
        lines 220-233. The fallback explicitly fails the secondary gate (threshold=0)
        so a soak run without a real approval is loud, not silent.
        """
        if CALIB_02_DEFAULTS_PATH.exists():
            return json.loads(CALIB_02_DEFAULTS_PATH.read_text(encoding="utf-8"))
        return {
            "statistic": "p99",
            "threshold": 0,
            "headroom_factor": 1.0,
            "rounding_policy": "none",
            "approval_artifact": "(none — pre-approval state)",
            "calib_01_distribution_reference": "(none)",
            "gate_column": "suppressions_completed_window_count_distribution",
        }
    ```

    Step 2: Add `aggregate_watchdog()` between `aggregate_completed_window_distribution()` (added in Plan 204-02) and `aggregate_by_zone_cause()` (line 177). Implementation has TWO halves:

    Half A — Legacy live-counter mean (verbatim port of the v1.42 jq pipeline at 201-16-soak-and-closeout-PLAN.md:96-131; jq excerpt also in 204-PATTERNS.md lines 140-159):

    ```python
    def aggregate_watchdog(
        rows: list[dict[str, Any]],
        *,
        legacy_threshold: float = 5.0,
        new_threshold: int,
        statistic: str = "p99",
        gate_column: str = "suppressions_completed_window_count_distribution",
    ) -> dict[str, Any]:
        """Compute D-14-successor watchdog gate from a soak NDJSON.

        Emits BOTH legacy live-counter mean (verbatim port of v1.42 Plan 201-16
        jq pipeline at .planning/milestones/v1.42-phases/.../201-16-soak-and-closeout-PLAN.md:96-131)
        AND new completed-window-count statistic side-by-side for ONE TRANSITION
        CYCLE = ONE MILESTONE (v1.43 emits both; v1.44 follow-up drops legacy).
        See 204-RESEARCH.md §Q5 lines 224-237 for the transition-cycle decision.

        Per CALIB-03 (REQUIREMENTS.md), the legacy block is informational only.
        secondary_gate_completed_window is the real gate.
        """
        # ===== Half A: Legacy live-counter mean (verbatim Python port of jq) =====
        # Required columns: t_monotonic, suppressions_per_min
        if not rows:
            legacy_mean: float | None = None
            legacy_window_count = 0
        else:
            sorted_rows = sorted(rows, key=lambda r: float(r.get("t_monotonic", 0.0)))
            t_start = float(sorted_rows[0].get("t_monotonic", 0.0))
            t_end = float(sorted_rows[-1].get("t_monotonic", 0.0))
            window_count = int((t_end - t_start) / 60.0)
            window_means: list[float] = []
            for w in range(window_count):
                lo = t_start + (w * 60)
                hi = t_start + ((w + 1) * 60)
                vals: list[float] = []
                for r in sorted_rows:
                    tm = float(r.get("t_monotonic", -1.0))
                    if lo <= tm < hi:
                        # Match jq `.suppressions_per_min // 0`
                        vals.append(float(r.get("suppressions_per_min") or 0))
                if vals:
                    window_means.append(sum(vals) / len(vals))
            # Match jq `.windows |= map(select(. != null))` (already filtered above)
            legacy_window_count = len(window_means)
            legacy_mean = (sum(window_means) / len(window_means)) if window_means else None

        legacy_value = legacy_mean if legacy_mean is not None else 0.0
        legacy_verdict = "pass" if legacy_value <= legacy_threshold else "fail"
        legacy_block = {
            "name": "ul_hysteresis_suppression_rate_per_60s_mean (legacy live-counter-snapshot mean)",
            "computation": (
                "Mean of live-counter snapshots within each 60s window, then mean "
                "across windows. Verbatim port of v1.42 Plan 201-16 jq pipeline. "
                "PRESERVED FOR ONE TRANSITION CYCLE - drops in v1.44."
            ),
            "value": legacy_value,
            "threshold": legacy_threshold,
            "window_count": legacy_window_count,
            "verdict": legacy_verdict,
            "note": (
                "This metric is metric-semantically broken; see Phase 201 RETRO "
                "Lesson #1. Use secondary_gate_completed_window for actual gating."
            ),
        }

        # ===== Half B: New completed-window count statistic =====
        # Reuse Plan 204-02's aggregate_completed_window_distribution()
        dist = aggregate_completed_window_distribution(rows)
        # Resolve the gate column: top-level distribution or a by_cause slice
        if gate_column == "suppressions_completed_window_count_distribution":
            cell = dist
        elif gate_column.startswith("by_cause."):
            cause = gate_column.split(".", 1)[1]
            cell = dist.get("by_cause", {}).get(cause, {})
        else:
            cell = {}
        new_value: float = float(cell.get(statistic, 0.0)) if cell else 0.0
        new_verdict = "pass" if new_value <= new_threshold else "fail"
        new_block = {
            "name": f"ul_suppressions_completed_window_count_{statistic}",
            "computation": (
                f"{statistic} of per-completed-window suppression counts over the "
                f"soak window (gate_column={gate_column}). Replaces "
                f"secondary_gate_legacy at v1.44."
            ),
            "value": new_value,
            "threshold": new_threshold,
            "statistic": statistic,
            "gate_column": gate_column,
            "verdict": new_verdict,
            "operator_approval": (
                ".planning/phases/204-d-14-successor-recalibration-calib/"
                "204-CALIB-02-OPERATOR-APPROVAL.md"
            ),
        }

        return {
            "secondary_gate_legacy": legacy_block,
            "secondary_gate_completed_window": new_block,
        }
    ```

    Step 3: Extend `aggregate_soak()` (line 239) to load CALIB-02 constants and call `aggregate_watchdog()`, merging both new top-level keys into the return dict. Place the two new keys AFTER `suppressions_completed_window_count_distribution` (added by Plan 204-02) and BEFORE `phase_203_metadata`:

    ```python
    def aggregate_soak(ndjson_path: Path, buckets: list[int] | None = None) -> dict[str, Any]:
        if buckets is None:
            buckets = list(DEFAULT_BUCKETS_US)
        rows = load_ndjson(ndjson_path)
        diagnostic = aggregate_v142_diagnostic_distribution(rows)
        diagnostic["load_rtt_delta_us"] = aggregate_load_rtt_delta(rows, buckets)
        constants = load_calib_02_constants()
        watchdog = aggregate_watchdog(
            rows,
            legacy_threshold=5.0,
            new_threshold=int(constants["threshold"]),
            statistic=constants["statistic"],
            gate_column=constants["gate_column"],
        )
        return {
            "diagnostic_distribution": diagnostic,
            "load_rtt_delta_us_by_zone_cause": aggregate_by_zone_cause(rows, buckets),
            "suppressions_completed_window_count_distribution": (
                aggregate_completed_window_distribution(rows)
            ),
            "secondary_gate_legacy": watchdog["secondary_gate_legacy"],
            "secondary_gate_completed_window": watchdog["secondary_gate_completed_window"],
            "phase_203_metadata": {
                "attribution_policy": "dual",
                "attribution_note": "Counts may exceed total_samples because multi-cause rows are dual-attributed.",
                "buckets_us": list(buckets),
                "zone_axis": "upload",
            },
        }
    ```

    No `src/wanctl/` files touched. Only `scripts/soak_summary_aggregate.py` modified.
  </action>
  <verify>
    <automated>grep -c '^def aggregate_watchdog(' scripts/soak_summary_aggregate.py | grep -q '^1$' &amp;&amp; grep -c '^def load_calib_02_constants(' scripts/soak_summary_aggregate.py | grep -q '^1$' &amp;&amp; .venv/bin/python -c "from scripts.soak_summary_aggregate import aggregate_watchdog, load_calib_02_constants; print(load_calib_02_constants())" &amp;&amp; bash scripts/check-safe07-source-diff.sh</automated>
  </verify>
  <acceptance_criteria>
    - `grep -c '^def aggregate_watchdog(' scripts/soak_summary_aggregate.py` returns 1
    - `grep -c '^def load_calib_02_constants(' scripts/soak_summary_aggregate.py` returns 1
    - Module imports cleanly: `.venv/bin/python -c "from scripts.soak_summary_aggregate import aggregate_watchdog, load_calib_02_constants, aggregate_soak"` exits 0
    - `bash scripts/check-safe07-source-diff.sh` exits 0
    - Hot-path slice green
  </acceptance_criteria>
  <done>Aggregator has both new functions; module loads; SAFE-07 invariant clean.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Author tests/test_phase_204_watchdog.py + tests/test_phase_204_replay.py + refresh fixtures</name>
  <read_first>
    - tests/test_phase_203_replay.py:1-180 (full file — class structure to clone for both new test files)
    - 204-PATTERNS.md lines 253-388 (test class patterns: TestAggregatorMath, TestV142NdjsonRegression, TestGeneratorDriftDetection, TestV142WatchdogRegression)
    - .planning/milestones/v1.42-phases/201-docsis-aware-ul-congestion-control/soak/20260505T132736Z/suppression-stats.json (oracle 6.466842364880155 at line 6)
    - tests/fixtures/phase_204_synthetic_capture.ndjson (Plan 204-02 output; will need to be extended to exercise watchdog branches)
    - tests/fixtures/phase_204_synthetic_summary.json (Plan 204-02 output; needs regeneration to include the two new top-level gate blocks)
  </read_first>
  <files>tests/test_phase_204_watchdog.py, tests/test_phase_204_replay.py, tests/fixtures/phase_204_synthetic_summary.json, tests/fixtures/phase_203_synthetic_summary.json</files>
  <behavior>
    Test file 1 (tests/test_phase_204_watchdog.py):
      Class TestWatchdogMath:
        - test_legacy_block_shape: aggregate_watchdog returns dict with keys ['secondary_gate_legacy', 'secondary_gate_completed_window']; legacy_block has expected name/computation/value/threshold/verdict/note keys.
        - test_new_block_loads_from_calib_02: when scripts/calib_02_threshold.json exists, aggregate_soak() merges threshold/statistic/gate_column into secondary_gate_completed_window.
        - test_synthetic_pass_branch: synthetic rows producing distribution p99=10 against threshold=100 → verdict=pass.
        - test_synthetic_fail_branch: synthetic rows producing distribution p99=200 against threshold=100 → verdict=fail.
      Class TestV142WatchdogRegression (skip if v1.42 NDJSON absent):
        - test_legacy_value_matches_inline_jq_oracle: aggregate_watchdog against v1.42 NDJSON → secondary_gate_legacy.value == 6.466842364880155 ± 1e-6.
        - test_legacy_verdict_against_v142_threshold: with legacy_threshold=5.0, verdict == "fail" (matches v1.42 actual outcome).

    Test file 2 (tests/test_phase_204_replay.py):
      Class TestV142NdjsonRegressionPhase204:
        - test_aggregate_soak_v142_includes_new_gates: aggregate_soak(V142_NDJSON) returns dict containing secondary_gate_legacy AND secondary_gate_completed_window top-level keys.
        - test_diagnostic_distribution_phase_203_unaffected: pre-existing diagnostic_distribution.rtt_integral_ms_s.mean still matches v1.42 within rel=0.01 (Phase 203 backward-compat).
  </behavior>
  <action>
    Step 1: Author `tests/test_phase_204_watchdog.py`. Clone preamble from `tests/test_phase_203_replay.py:1-51` substituting `phase_203_*` → `phase_204_*` for synthetic fixtures, but KEEP `V142_NDJSON` pointing at `.planning/milestones/v1.42-phases/201-docsis-aware-ul-congestion-control/soak/20260505T132736Z/soak-capture.ndjson`. Implement the two test classes per the `<behavior>` block.

    Reference the verbatim TestV142WatchdogRegression skeleton at 204-PATTERNS.md lines 350-368.

    For the synthetic PASS/FAIL branches, hand-craft small inline NDJSON snippets within test bodies (not new files):
    ```python
    def _make_rows(boundary_jumps: list[int]) -> list[dict]:
        """Construct synthetic rows producing the given completed-window jumps."""
        rows = []
        running = 0
        t = 0.0
        for jump in boundary_jumps:
            # Two rows per "boundary" — pre-boundary stable, post-boundary increment
            rows.append({"t_monotonic": t, "ul_suppressions_completed_window_count": running,
                         "suppressions_per_min": 0,
                         "ul_suppressions_completed_window_by_cause": {"dwell_hold": running, "backlog_recovery": 0, "other": 0}})
            t += 60.0
            running += jump
            rows.append({"t_monotonic": t, "ul_suppressions_completed_window_count": running,
                         "suppressions_per_min": 0,
                         "ul_suppressions_completed_window_by_cause": {"dwell_hold": running, "backlog_recovery": 0, "other": 0}})
        return rows
    ```

    Step 2: Author `tests/test_phase_204_replay.py`. Smaller file — focuses on the v1.42 NDJSON regression for the watchdog math (sibling file to keep concerns separate per planner preference noted in 204-RESEARCH.md §Wave 0 lines 670-675).

    Step 3: Refresh `tests/fixtures/phase_204_synthetic_summary.json`:
    - Re-run `.venv/bin/python scripts/soak_summary_aggregate.py tests/fixtures/phase_204_synthetic_capture.ndjson -o /tmp/p204_new.json`
    - Inspect /tmp/p204_new.json — it now contains `secondary_gate_legacy` and `secondary_gate_completed_window` top-level keys (loaded with whatever scripts/calib_02_threshold.json provides — the operator-approved constants from Plan 204-03).
    - Copy to tests/fixtures/phase_204_synthetic_summary.json.

    Step 4: Refresh `tests/fixtures/phase_203_synthetic_summary.json` (per 204-RESEARCH.md §Risk 7 lines 751-755 — the new top-level keys appear in Phase 203's synthetic output too):
    - Re-run aggregator against Phase 203 fixture: `.venv/bin/python scripts/soak_summary_aggregate.py tests/fixtures/phase_203_synthetic_capture.ndjson -o /tmp/p203_new.json`
    - Diff against existing tests/fixtures/phase_203_synthetic_summary.json — expected diff is exactly the two new top-level gate blocks (with secondary_gate_legacy.value=0 since the synthetic Phase 203 fixture has no `suppressions_per_min` column, and secondary_gate_completed_window.value=0 since the Phase 203 fixture has no `ul_suppressions_completed_window_count` column).
    - Copy to tests/fixtures/phase_203_synthetic_summary.json.

    No `src/wanctl/` files touched.
  </action>
  <verify>
    <automated>.venv/bin/pytest tests/test_phase_204_watchdog.py tests/test_phase_204_replay.py tests/test_phase_204_distribution.py tests/test_phase_203_replay.py tests/test_phase_202_replay.py -v &amp;&amp; bash scripts/check-safe07-source-diff.sh &amp;&amp; .venv/bin/pytest -o addopts='' tests/test_cake_signal.py tests/test_queue_controller.py tests/test_wan_controller.py tests/test_health_check.py -q</automated>
  </verify>
  <acceptance_criteria>
    - `tests/test_phase_204_watchdog.py` exists; class TestV142WatchdogRegression present
    - `.venv/bin/pytest tests/test_phase_204_watchdog.py -v` exits 0; at least 5 tests in TestWatchdogMath plus 2 in TestV142WatchdogRegression
    - Specific assertion passes: `aggregate_watchdog(rows_from_v142_ndjson, ...).secondary_gate_legacy.value` is within abs=1e-6 of `6.466842364880155`
    - `tests/test_phase_204_replay.py` exists; exits 0
    - `tests/test_phase_203_replay.py` still passes (golden fixture refreshed for new top-level keys per 204-RESEARCH.md §Risk 7)
    - `tests/test_phase_202_replay.py` still passes
    - Hot-path slice green
    - `bash scripts/check-safe07-source-diff.sh` exits 0
  </acceptance_criteria>
  <done>v1.42 oracle regression passes; synthetic PASS/FAIL branches covered; both Phase 203 + Phase 204 golden fixtures refreshed; Phase 202 + 203 backward-compat tests still green.</done>
</task>

<task type="auto">
  <name>Task 3: Document watchdog transition in docs/SOAK_HARNESS.md and CHANGELOG.md</name>
  <read_first>
    - docs/SOAK_HARNESS.md (existing schema-table style at lines 35-58 added by Phase 203)
    - 204-PATTERNS.md lines 663-680 (docs/SOAK_HARNESS.md extension pattern)
    - 204-PATTERNS.md lines 644-661 (CHANGELOG.md v1.43-dev entry pattern)
    - CHANGELOG.md (current ## v1.43-dev block at line 8)
    - 204-RESEARCH.md §Q5 lines 240-259 (verbatim JSON shape to document)
  </read_first>
  <files>docs/SOAK_HARNESS.md, CHANGELOG.md</files>
  <action>
    Step 1: Append a new section to `docs/SOAK_HARNESS.md` after the existing per-row schema table:

    ```markdown
    ## Watchdog computation transition (CALIB-03)

    Phase 204 introduces a dual-emission watchdog in `soak-summary.json`. Both blocks are emitted side-by-side for **one transition cycle = the v1.43 milestone**; the legacy block drops in a v1.44 follow-up commit.

    ### `secondary_gate_legacy` (informational only — drops in v1.44)

    ```json
    "secondary_gate_legacy": {
      "name": "ul_hysteresis_suppression_rate_per_60s_mean (legacy live-counter-snapshot mean)",
      "computation": "Mean of live-counter snapshots within each 60s window, then mean across windows. Verbatim port of v1.42 Plan 201-16 jq pipeline. PRESERVED FOR ONE TRANSITION CYCLE - drops in v1.44.",
      "value": <float>,
      "threshold": 5.0,
      "verdict": "<pass|fail>",
      "note": "This metric is metric-semantically broken; see Phase 201 RETRO Lesson #1. Use secondary_gate_completed_window for actual gating."
    }
    ```

    ### `secondary_gate_completed_window` (the real gate)

    ```json
    "secondary_gate_completed_window": {
      "name": "ul_suppressions_completed_window_count_<statistic>",
      "value": <number>,
      "threshold": <CALIB_02 integer>,
      "statistic": "<from scripts/calib_02_threshold.json>",
      "gate_column": "<from scripts/calib_02_threshold.json>",
      "verdict": "<pass|fail>",
      "operator_approval": ".planning/phases/204-d-14-successor-recalibration-calib/204-CALIB-02-OPERATOR-APPROVAL.md"
    }
    ```

    The CALIB-04 verification soak (Plan 204-05) PASSES iff both `primary_gate.verdict == "pass"` AND `secondary_gate_completed_window.verdict == "pass"`. The `secondary_gate_legacy` block is NOT part of the pass criterion.

    ### Operator-approved constants

    `scripts/calib_02_threshold.json` is the machine-readable mirror of `204-CALIB-02-OPERATOR-APPROVAL.md`. It provides `statistic`, `threshold`, `headroom_factor`, and `gate_column` (open-Q2 slice-vs-total decision). The aggregator loads it via `load_calib_02_constants()` at `aggregate_soak()` time.
    ```

    Step 2: Append to `CHANGELOG.md` under the existing `## v1.43-dev` section:

    ```markdown
    ### Changed
    - CALIB-03: soak-harness watchdog computation now reads completed-window count statistic from `scripts/calib_02_threshold.json`; legacy live-counter-snapshot mean preserved alongside as `secondary_gate_legacy` for one transition cycle (drops in v1.44).
    - Operator-approved D-14 successor threshold (CALIB-02): see `.planning/phases/204-d-14-successor-recalibration-calib/204-CALIB-02-OPERATOR-APPROVAL.md`.

    ### Added
    - `aggregate_watchdog()` and `load_calib_02_constants()` functions in `scripts/soak_summary_aggregate.py`.
    - `aggregate_completed_window_distribution()` function in `scripts/soak_summary_aggregate.py` (Plan 204-02).
    - `scripts/calib_02_threshold.json` operator-approval-derived constants file (Plan 204-03).
    - `tests/test_phase_204_distribution.py`, `tests/test_phase_204_watchdog.py`, `tests/test_phase_204_replay.py` (replay tests + v1.42 oracle regression).
    - `docs/SOAK_HARNESS.md`: "Watchdog computation transition (CALIB-03)" section.

    ### Deploy notes
    - Deploy 1 (Plan 204-01): METRIC-01 + OBSV-05 binary on cake-shaper at version 1.43.0; full Plan 201-15 two-snapshot rollback ritual.
    - Deploy 2 (Plan 204-04): harness-only — git commit, no production binary change. See "Why Deploy 2 looks different" in `.planning/phases/204-d-14-successor-recalibration-calib/204-04-...-PLAN.md` Task 4.
    ```

    No `src/wanctl/` files touched.
  </action>
  <verify>
    <automated>grep -q "Watchdog computation transition" docs/SOAK_HARNESS.md &amp;&amp; grep -q "secondary_gate_legacy" docs/SOAK_HARNESS.md &amp;&amp; grep -q "secondary_gate_completed_window" docs/SOAK_HARNESS.md &amp;&amp; grep -q "CALIB-03" CHANGELOG.md &amp;&amp; grep -q "aggregate_watchdog" CHANGELOG.md &amp;&amp; bash scripts/check-safe07-source-diff.sh
    <automated>grep -q "Watchdog computation transition" docs/SOAK_HARNESS.md &amp;&amp; grep -q "secondary_gate_legacy" docs/SOAK_HARNESS.md &amp;&amp; grep -q "secondary_gate_completed_window" docs/SOAK_HARNESS.md &amp;&amp; grep -q "CALIB-03" CHANGELOG.md &amp;&amp; grep -q "aggregate_watchdog" CHANGELOG.md &amp;&amp; bash scripts/check-safe07-source-diff.sh</automated>
  </verify>
  <acceptance_criteria>
    - `grep -q "Watchdog computation transition" docs/SOAK_HARNESS.md` exits 0
    - `grep -q "secondary_gate_legacy" docs/SOAK_HARNESS.md` AND `grep -q "secondary_gate_completed_window" docs/SOAK_HARNESS.md` both exit 0
    - `grep -q "CALIB-03" CHANGELOG.md` AND `grep -q "aggregate_watchdog" CHANGELOG.md` both exit 0
    - `bash scripts/check-safe07-source-diff.sh` exits 0
  </acceptance_criteria>
  <done>Docs and CHANGELOG document the dual-emission transition; consumers can read the soak-summary schema without reading the source.</done>
</task>

<task type="auto">
  <name>Task 4: Document "Why Deploy 2 Looks Different" + commit Deploy 2</name>
  <read_first>
    - 204-RESEARCH.md §Q7 line 389 (Deploy 2 degenerate explanation)
    - 204-RESEARCH.md §Risk 4 lines 730-734 (operator-confusion risk; mitigation requires explicit explanation in this plan)
    - scripts/soak-capture.sh (verify NO change required — already emits all needed columns since Phase 203)
  </read_first>
  <files>(no new files; embedded explanation in this plan; committed via standard git workflow)</files>
  <action>
    Step 1: Verify capture script unchanged. Per 204-PATTERNS.md line 640: "Capture-script change requirement: none. The Phase 203 harness already emits every field Phase 204 needs."
    ```bash
    git diff HEAD -- scripts/soak-capture.sh
    # MUST produce 0 lines (no change to capture script)
    ```

    Step 2: This task's deliverable is the **explicit asymmetry explanation** to mitigate 204-RESEARCH.md §Risk 4 (operator confusion). The explanation lives in this plan body — both as guidance for the executor and as a reference operators can cite. The text below is the canonical "Why Deploy 2 Looks Different" statement; it is also referenced from CHANGELOG.md Deploy notes (Task 3) and will be cited from 204-RETRO.md (Plan 204-06).

    ## Why Deploy 2 Looks Different

    The ROADMAP says "two production deploys, both gated on operator approval." Deploy 1 (Plan 204-01) was a full Plan 201-15 two-snapshot ritual: production binary swap on cake-shaper, two `.tar.gz` snapshots, predeploy gate, post-deploy `/health` smoke, verdict file. **Deploy 2 (this plan) does NOT have any of that** — and the asymmetry is intentional, not a missed step.

    The reason: CALIB-02's recalibrated threshold is a **soak-harness Python constant** (`scripts/calib_02_threshold.json` consumed by `aggregate_watchdog()`), NOT a production binary or YAML knob. REQUIREMENTS.md "Out of Scope" §4 states verbatim: "CALIB-02's recalibrated threshold is a soak-harness constant, not a config knob, until proven through CALIB-04."

    Concretely:
    - **Production binary on cake-shaper:** unchanged at v1.43.0 since Plan 204-01.
    - **`/etc/wanctl/spectrum.yaml` on cake-shaper:** unchanged.
    - **`scripts/soak-capture.sh`:** unchanged (verified by `git diff HEAD -- scripts/soak-capture.sh` returning 0 lines). The Phase 203 harness already emits every field Phase 204 needs (per 204-PATTERNS.md line 640).
    - **What changes:** `scripts/soak_summary_aggregate.py` (Tasks 1-2 of this plan) and `scripts/calib_02_threshold.json` (Plan 204-03 output).

    Therefore "Deploy 2" reduces to: **commit the harness changes + the operator-approved JSON to git**. There is no production-side artifact to roll back; if `aggregate_watchdog()` produces wrong numbers, the operator amends `scripts/calib_02_threshold.json` (Plan 204-03 re-approval) or reverts the commits.

    For evidence symmetry with Plan 204-01's two-snapshot pattern, this plan optionally captures the pre-edit aggregator state in the soak directory of Plan 204-05 (`soak/<CALIB_04_TS>/aggregator-pre-edit.py.snapshot`). Per 204-RESEARCH.md §Q7 line 389: "do not stand up the full T0/T1/T2/T3/T4 sequence — there is no production binary to roll back."

    **If a future operator reads ROADMAP "two production deploys" and expects a second `tar.gz` snapshot under `/opt/wanctl-prephase204-deploy2-...-snapA.tar.gz`: it does not exist by design.** The deploy is the git commit landing this plan + Plan 204-03 + Plan 204-02 changes.

    Step 3: Commit Deploy 2 — this is a normal git commit at plan close (will be part of the standard project-finalizer workflow). The commit message should explicitly note "Deploy 2 (harness-only)":
    ```
    feat(phase-204): land CALIB-03 dual-emission watchdog (Deploy 2 harness-only)
    ```
  </action>
  <verify>
    <automated>git diff HEAD -- scripts/soak-capture.sh | wc -l | grep -q '^0$' &amp;&amp; bash scripts/check-safe07-source-diff.sh &amp;&amp; .venv/bin/pytest tests/test_phase_204_watchdog.py tests/test_phase_204_replay.py tests/test_phase_204_distribution.py tests/test_phase_203_replay.py tests/test_phase_202_replay.py tests/test_phase_195_replay.py -v</automated>
  </verify>
  <acceptance_criteria>
    - `git diff HEAD -- scripts/soak-capture.sh` produces 0 lines (capture script unchanged — Deploy 2 is harness-aggregator-only)
    - `bash scripts/check-safe07-source-diff.sh` exits 0
    - All Phase 202 / 203 / 204 replay tests pass
    - SAFE-05 pin block test passes: `.venv/bin/pytest tests/test_phase_195_replay.py -v -k "safe05_threshold_name_counts"` exits 0
    - The "Why Deploy 2 Looks Different" section appears in this plan body (operator can cite from here)
  </acceptance_criteria>
  <done>Deploy 2 is committed (harness-only). Asymmetry vs Deploy 1 is explicitly documented. Plan 204-05 verification soak unblocked.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| scripts/calib_02_threshold.json → aggregate_watchdog() | Operator-approved constants drive gate verdict; tampering would silently change CALIB-04 outcome. |
| v1.42 inline-jq pipeline → Python port | Verbatim port; numerical drift = oracle test failure. |
| Aggregator output schema → CALIB-04 verdict consumers | Plan 204-05 reads the new top-level keys; schema break would cause silent verification failure. |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-204-04-01 | Tampering | scripts/calib_02_threshold.json | mitigate | The file is committed alongside the operator-approval artifact (Plan 204-03); cross-check between the two is a Plan 204-03 acceptance criterion. Plan 204-06 closeout SAFE-07 check would catch any unauthorized edits. |
| T-204-04-02 | Tampering | aggregate_watchdog() Python port of v1.42 jq | mitigate | TestV142WatchdogRegression asserts byte-equivalent oracle (6.466842364880155 ± 1e-6). Drift fails the test. |
| T-204-04-03 | Information Disclosure | aggregate_watchdog return dict in soak-summary.json | accept | Existing soak-summary.json is committed under .planning/; no PII; no secrets. |
| T-204-04-04 | Repudiation | Operator approval flow | mitigate (transitive) | Approval captured in Plan 204-03's artifact; this plan only consumes it. Single source of truth in 204-CALIB-02-OPERATOR-APPROVAL.md. |
</threat_model>

<verification>
- aggregate_watchdog() and load_calib_02_constants() exist in scripts/soak_summary_aggregate.py
- secondary_gate_legacy.value == 6.466842364880155 ± 1e-6 against v1.42 NDJSON
- secondary_gate_completed_window populated from scripts/calib_02_threshold.json
- All Phase 202/203/204 replay tests green
- docs/SOAK_HARNESS.md and CHANGELOG.md document the transition
- "Why Deploy 2 Looks Different" section present in this plan
- scripts/soak-capture.sh unchanged (Deploy 2 is harness-aggregator-only)
- SAFE-07 source-diff invariant clean
- SAFE-05 pin block byte-identical
</verification>

<success_criteria>
CALIB-03 watchdog harness ships: aggregate_watchdog() emits dual gates side-by-side; legacy oracle regression passes; new gate honors operator-approved constants. Deploy 2 = git commit (no production binary change); asymmetry vs Deploy 1 explicitly documented. Phase 203 + Phase 202 backward-compatibility preserved (golden fixtures refreshed). Zero src/wanctl/ source diff. Plan 204-05 verification soak is unblocked.
</success_criteria>

<output>
After completion, create `.planning/phases/204-d-14-successor-recalibration-calib/204-04-SUMMARY.md` recording:
- aggregate_watchdog() function added (line range)
- v1.42 oracle regression test result (PASS — secondary_gate_legacy.value matches 6.466842364880155 ± 1e-6)
- Operator-approved constants from scripts/calib_02_threshold.json (statistic, threshold, gate_column)
- Confirmation: scripts/soak-capture.sh unchanged
- Phase 203 + 202 fixture refresh diff summary
- Hand-off pointer to Plan 204-05 (CALIB-04 verification soak)
</output>
