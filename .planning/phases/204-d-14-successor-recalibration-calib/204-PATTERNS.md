# Phase 204: D-14 Successor Recalibration (CALIB) — Pattern Map

**Mapped:** 2026-05-06
**Files analyzed:** 16 (5 Python/script, 1 test, 7 markdown artifacts, 1 JSON, 1 CHANGELOG, 1 doc)
**Analogs found:** 16 / 16 — every target has a precise existing analog with line citations.
**SAFE-07 audit:** 0 of 16 targets touch `src/wanctl/`. Safe.

This map exists because Phase 204 is uniquely "no source-code work" by SAFE-07 (REQUIREMENTS.md line 38; verified `git diff b72b463..HEAD -- src/wanctl/` returns 0 lines). The planner needs file-and-line excerpts to copy verbatim into PLAN `<read_first>` and `<action>` blocks; abstract guidance is insufficient against a frozen control path.

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `scripts/soak_summary_aggregate.py` (extend) | aggregator (script) | batch transform | `scripts/soak_summary_aggregate.py` (Phase 203 self-extension) | exact (same file) |
| `scripts/calib_02_threshold.json` (NEW) | threshold_artifact (JSON config) | static load | none in `scripts/`; closest is `tests/fixtures/phase_203_synthetic_summary.json` (golden JSON) | role-novel |
| `tests/test_phase_204_distribution.py` (NEW) | test (replay) | fixture-driven | `tests/test_phase_203_replay.py:54-85` (`TestAggregatorMath`) | exact |
| `tests/test_phase_204_watchdog.py` (NEW) | test (replay + regression) | fixture-driven + v1.42 NDJSON regression | `tests/test_phase_203_replay.py:87-122` (`TestV142NdjsonRegression`) | exact |
| `tests/test_phase_204_replay.py` (NEW or fold-into-watchdog) | test (oracle regression) | v1.42 NDJSON regression | `tests/test_phase_203_replay.py:87-122` | exact |
| `tests/fixtures/phase_204_synthetic_capture.ndjson` (NEW) | fixture (NDJSON) | golden replay input | `tests/fixtures/phase_203_synthetic_capture.ndjson` (referenced via test) | exact |
| `tests/fixtures/phase_204_synthetic_summary.json` (NEW) | fixture (JSON oracle) | golden output | `tests/fixtures/phase_203_synthetic_summary.json` | exact |
| `tests/fixtures/_phase_204_generator.py` (NEW, optional) | fixture generator | deterministic emitter | `tests/fixtures/_phase_203_generator.py` (drift-detection precedent in `test_phase_203_replay.py:124-136`) | exact |
| `.planning/phases/204-.../204-CALIB-02-OPERATOR-APPROVAL.md` (NEW) | operator_approval | manual artifact | `.planning/milestones/v1.42-phases/201-docsis-aware-ul-congestion-control/201-16-OPERATOR-APPROVAL-D19.md` (21 lines, full file) | exact |
| `.planning/phases/204-.../204-01-DEPLOY-VERIFICATION.md` (NEW) | deploy verdict | manual artifact | `.planning/milestones/v1.42-phases/201-.../201-15-CANARY-VERDICT.md` | role-match |
| `.planning/phases/204-.../204-05-CALIB-04-SOAK-VERDICT.md` (NEW) | soak verdict | manual artifact | `.planning/milestones/v1.42-phases/201-.../201-16-SOAK-VERDICT.md` | role-match |
| `.planning/phases/204-.../204-RETRO.md` (NEW) | retro_doc | manual artifact | `.planning/milestones/v1.42-phases/201-.../201-RETRO.md` lines 1-80 | exact (structural mirror) |
| `.planning/phases/204-.../204-VERIFICATION.md` (NEW) | verification doc | manual artifact | `.planning/milestones/v1.43-phases/203-.../203-VERIFICATION.md` | exact |
| `.planning/phases/204-.../204-VALIDATION.md` (NEW; partial exists) | validation doc | manual artifact | `.planning/milestones/v1.43-phases/203-.../203-VALIDATION.md` | exact |
| `CHANGELOG.md` (modify) | changelog | doc | `CHANGELOG.md` `## v1.43-dev` block (already exists, line 8) | exact |
| `docs/SOAK_HARNESS.md` (modify) | docs | doc | `docs/SOAK_HARNESS.md` lines 35-58 (Phase 203 added the same kind of schema rows) | exact |

**Files explicitly NOT touched (SAFE-07 invariant):**

- `src/wanctl/**` — any change is a SAFE-07 violation. `scripts/check-safe07-source-diff.sh` line 21 (default ref `b72b463`) catches mechanically.
- `tests/test_phase_195_replay.py:642-714` — the SAFE-05 pin block (three dicts: `expected_counts`, `phase201_expected_counts`, `phase202_expected_counts`). Read-only at v1.43 close. **No `phase204_expected_counts` dict added** — Phase 204 introduces zero new `src/wanctl/` symbols, mirroring Phase 203's "no source pins" approach.
- `configs/*.yaml`, `src/wanctl/autorate_config.py`, `src/wanctl/wan_controller.py` — REQUIREMENTS.md "Out of Scope" §4: CALIB-02 threshold is a soak-harness Python constant, NOT a YAML knob. `_suppression_alert_threshold` references at `wan_controller.py:764, 2200, 2207, 2523, 4556` are control-path; do not touch.

**Version-bump surfaces (touched only in Plan 204-01, Deploy 1; not control-path):**

- `src/wanctl/__init__.py:3` — `__version__ = "1.42.1"` → `"1.43.0"`. NOT a SAFE-07 violation: version string is not in any of the three SAFE-05 pin dicts.
- `pyproject.toml:3` — `version = "1.42.1"` → `"1.43.0"`.
- `docker/Dockerfile:13` — `LABEL version="1.42.1"` → `"1.43.0"`.

Verification (research §A8 + §Q10 line 999): none of the SAFE-05 pinned strings (`factor_down`, `step_up`, ..., `suppressions_lifetime_by_cause`) are version literals; bumping `__version__` produces zero diff against `b72b463` for the pin block.

---

## Pattern Assignments

### `scripts/soak_summary_aggregate.py` extension (aggregator, batch transform)

**Analog:** the same file at HEAD (Phase 203 promoted it from inline jq; Phase 204 extends it the same way).

**Module header / imports pattern** (`scripts/soak_summary_aggregate.py:1-50`):

```python
#!/usr/bin/env python3
"""Phase 203 OBSV-06 soak summary aggregator.

Reads a soak-capture.ndjson and writes a soak-summary.json including:
  * diagnostic_distribution.load_rtt_delta_us — p50/p95/p99/max + histogram
  * load_rtt_delta_us_by_zone_cause          — 4 zones × 3 causes matrix
  * v1.42-compatible diagnostic_distribution fields preserved where applicable

Promoted from the inline-jq pipeline embedded in the v1.42 Plan 201-16 closeout
PLAN. Stdlib-only — no NumPy, no pandas. Reusable by Phase 204 CALIB-01 to
compute the recalibration baseline distribution.
"""

from __future__ import annotations

import argparse
import bisect
import json
import math
import statistics
import sys
from collections.abc import Iterable
from pathlib import Path
from typing import Any

DEFAULT_BUCKETS_US = [0, 1000, 3000, 6000, 10000, 15000, 20000, 30000, 45000, 60000, 100000, 250000]
ZONES = ("GREEN", "YELLOW", "SOFT_RED", "RED")
CAUSES = ("dwell_hold", "backlog_recovery", "other")
```

**Existing reusable helpers** (already implemented; extension code MUST NOT reimplement these):

- `aggregate_completed_windows(snapshots: list[int]) -> list[int]` — `scripts/soak_summary_aggregate.py:52-60`. Detects 60s window resets in a `suppressions_per_min` column. **Phase 204 reuse note (research §A7):** the new column `ul_suppressions_completed_window_count` is monotonic-non-decreasing within a daemon lifetime with discrete jumps at boundaries — NOT reset-to-0. So the new aggregator function must use **"value changed since prev sample"** detection, NOT the existing reset-to-0 helper. Either branch the existing helper or write a sibling helper.
- `percentile(values, p) -> float` — `scripts/soak_summary_aggregate.py:70-83`. Linear-interpolation, NumPy-free, returns `0.0` for empty input. Phase 204 calls this directly.
- `histogram(values, buckets) -> list[int]` — `scripts/soak_summary_aggregate.py:86-103`. Last cell is overflow.
- `_build_cell(values, buckets) -> dict` — `scripts/soak_summary_aggregate.py:120-133`. Returns `{p50, p95, p99, max, count, histogram}` shape.
- `_empty_cell(buckets) -> dict` — `scripts/soak_summary_aggregate.py:106-117`. Zero-fill cell shape.
- `load_ndjson(path: Path) -> list[dict]` — `scripts/soak_summary_aggregate.py:136-145`.

**Pattern for `aggregate_completed_window_distribution()` (Plan 204-02, CALIB-01):**

Follow the structure of `aggregate_load_rtt_delta()` at `scripts/soak_summary_aggregate.py:148-174`:

```python
def aggregate_load_rtt_delta(
    rows: list[dict[str, Any]], buckets: list[int] | None = None
) -> dict[str, Any]:
    """Build the top-level load_rtt_delta_us distribution.

    Rows missing the v1.43 key are ignored for samples_total. Rows where the key
    exists but is null are filtered from percentile/histogram math and counted in
    samples_filtered_null.
    """
    if buckets is None:
        buckets = list(DEFAULT_BUCKETS_US)
    total = 0
    filtered = 0
    deltas: list[int] = []
    for row in rows:
        if "load_rtt_delta_us" not in row:
            continue
        total += 1
        value = row["load_rtt_delta_us"]
        if value is None:
            filtered += 1
            continue
        deltas.append(int(value))
    cell = _build_cell(deltas, buckets)
    cell["samples_total"] = total
    cell["samples_filtered_null"] = filtered
    return cell
```

Plan 204-02 extension shape (`aggregate_completed_window_distribution()`):
- Walks `ul_suppressions_completed_window_count` per row (already captured by `scripts/soak-capture.sh:55`).
- Uses "value changed since prev" boundary detection (per A7 above).
- Returns `{"mean": float, "p50": float, "p95": float, "p99": float, "max": int, "window_count": int}` plus optional histogram. **MUST add `p99` explicitly** — research §Q1 inputs note p99 is unknown today.

**Pattern for `aggregate_watchdog()` (Plan 204-04, CALIB-03):**

Direct port of the v1.42 Plan 201-16 inline jq pipeline at `.planning/milestones/v1.42-phases/201-docsis-aware-ul-congestion-control/201-16-soak-and-closeout-PLAN.md:96-131`. The entire jq block to port:

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

Research §`Code Examples` lines 781-855 already provides the Python skeleton (`aggregate_watchdog()`); planner can copy verbatim. The function emits BOTH `secondary_gate_legacy` AND `secondary_gate_completed_window` keys side-by-side — the v1.42 oracle value `6.466842364880155` lives in `.planning/milestones/v1.42-phases/.../soak/20260505T132736Z/suppression-stats.json:6` as the regression target.

**CLI / `aggregate_soak()` integration pattern** (`scripts/soak_summary_aggregate.py:239-260`):

```python
def aggregate_soak(ndjson_path: Path, buckets: list[int] | None = None) -> dict[str, Any]:
    if buckets is None:
        buckets = list(DEFAULT_BUCKETS_US)
    rows = load_ndjson(ndjson_path)
    diagnostic = aggregate_v142_diagnostic_distribution(rows)
    diagnostic["load_rtt_delta_us"] = aggregate_load_rtt_delta(rows, buckets)
    return {
        "diagnostic_distribution": diagnostic,
        "load_rtt_delta_us_by_zone_cause": aggregate_by_zone_cause(rows, buckets),
        "phase_203_metadata": {
            "attribution_policy": "dual",
            "attribution_note": "Counts may exceed total_samples because multi-cause rows are dual-attributed.",
            "buckets_us": list(buckets),
            "zone_axis": "upload",
        },
    }
```

Plan 204-04 must extend this to include `secondary_gate_legacy` and `secondary_gate_completed_window` top-level keys. Phase 203 golden fixture `tests/fixtures/phase_203_synthetic_summary.json` will need regeneration if those keys appear at the top level (research §Risk 7). Mitigate by either gating new keys behind an explicit CLI flag or accepting a fixture refresh as a Plan 204-04 deliverable.

**`aggregate_soak()` argument extension pattern:** the existing function takes `buckets: list[int] | None`. Plan 204-04 should add `*, watchdog_constants: dict[str, Any] | None = None` (loaded from `scripts/calib_02_threshold.json` if not supplied), keeping the call from `main()` backward-compat.

**Argparse / CLI pattern** (`scripts/soak_summary_aggregate.py:272-293`):

```python
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Phase 203 soak-summary aggregator")
    parser.add_argument("ndjson_path", type=Path, help="Path to soak-capture.ndjson")
    parser.add_argument("-o", "--output", type=Path, default=None,
                        help="Output soak-summary.json path (default: stdout)")
    parser.add_argument("--target-delta-us", type=int, default=15000)
    parser.add_argument("--warn-delta-us", type=int, default=30000)
    parser.add_argument("--hard-red-us", type=int, default=60000)
    args = parser.parse_args(argv)
    result = aggregate_soak(args.ndjson_path, buckets=_build_buckets(args))
    text = json.dumps(result, indent=2, sort_keys=True)
    if args.output is None:
        sys.stdout.write(text); sys.stdout.write("\n")
    else:
        args.output.write_text(text + "\n", encoding="utf-8")
    return 0
```

Plan 204-04 may add `--calib-02-path <path>` as an override flag for tests; default = `scripts/calib_02_threshold.json` discovered relative to `__file__`.

---

### `scripts/calib_02_threshold.json` (threshold_artifact, static config) — NEW

**No exact analog in `scripts/`.** Closest pattern (research §`Code Examples` line 765-777 + Q4 lines 213-220): a small Python loader inside `scripts/soak_summary_aggregate.py` reads this file with a hard-coded fallback for tests/pre-approval state.

**Loader pattern to add** (Plan 204-04):

```python
# scripts/soak_summary_aggregate.py — proposed addition
import json
from pathlib import Path

CALIB_02_DEFAULTS_PATH = Path(__file__).parent / "calib_02_threshold.json"

def load_calib_02_constants() -> dict[str, Any]:
    """Load CALIB-02 operator-approved constants. Hard-coded fallback for tests."""
    if CALIB_02_DEFAULTS_PATH.exists():
        return json.loads(CALIB_02_DEFAULTS_PATH.read_text())
    # Fallback for tests / pre-approval state
    return {"statistic": "p99", "threshold": 0, "headroom_factor": 1.0,
            "approval_artifact": "(none — pre-approval state)"}
```

**JSON file schema** (Plan 204-04 deliverable):

```json
{
  "statistic": "p99",
  "threshold": 75,
  "headroom_factor": 1.5,
  "rounding_policy": "ceil_to_nearest_25",
  "approval_artifact": ".planning/phases/204-d-14-successor-recalibration-calib/204-CALIB-02-OPERATOR-APPROVAL.md",
  "calib_01_distribution_reference": ".planning/phases/204-d-14-successor-recalibration-calib/soak/<CALIB_01_TS>/soak-summary.json"
}
```

The values shown are illustrative (research §Q1 line 117 candidate); the operator approves the actual numbers in Plan 204-03.

---

### `tests/test_phase_204_distribution.py` and `tests/test_phase_204_watchdog.py` (test, replay)

**Analog:** `tests/test_phase_203_replay.py` (180 lines, three test classes).

**Module header / imports pattern** (`tests/test_phase_203_replay.py:1-37`):

```python
"""Phase 203 replay tests for v1.43 OBSV-06 / OBSV-07 aggregator side.

Dual-fixture strategy:
  * synthetic NDJSON fixture plus checked-in golden summary JSON. Aggregator
    output must byte-equal golden after canonical JSON serialization.
  * v1.42 reference soak NDJSON regression proves the inline-jq → Python
    promotion preserves diagnostic_distribution math on unaffected fields.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import ModuleType

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
AGGREGATOR_PATH = REPO_ROOT / "scripts" / "soak_summary_aggregate.py"
SYNTHETIC_NDJSON = REPO_ROOT / "tests" / "fixtures" / "phase_203_synthetic_capture.ndjson"
SYNTHETIC_SUMMARY = REPO_ROOT / "tests" / "fixtures" / "phase_203_synthetic_summary.json"
V142_NDJSON = (
    REPO_ROOT / ".planning" / "milestones" / "v1.42-phases"
    / "201-docsis-aware-ul-congestion-control" / "soak" / "20260505T132736Z"
    / "soak-capture.ndjson"
)
V142_SUMMARY = V142_NDJSON.with_name("soak-summary.json")
```

Phase 204 should clone this exact preamble, swapping `phase_203_*` → `phase_204_*` for synthetic fixtures while **keeping `V142_NDJSON` pointing at the same path** — that path is the watchdog regression oracle (research §`Risk 3`).

**Module loader pattern** (`tests/test_phase_203_replay.py:40-51`):

```python
def _load_module(path: Path, name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def aggregator() -> ModuleType:
    return _load_module(AGGREGATOR_PATH, "soak_aggregator")
```

Copy verbatim. Loads `scripts/soak_summary_aggregate.py` as a Python module under name `soak_aggregator`.

**Golden-byte-comparison test pattern** (`tests/test_phase_203_replay.py:54-66`):

```python
class TestAggregatorMath:
    """OBSV-06 + OBSV-07: synthetic NDJSON → exact golden match."""

    def test_aggregate_soak_matches_golden(self, aggregator: ModuleType) -> None:
        result = aggregator.aggregate_soak(SYNTHETIC_NDJSON)
        golden = json.loads(SYNTHETIC_SUMMARY.read_text(encoding="utf-8"))
        assert json.dumps(result, sort_keys=True, indent=2) == json.dumps(
            golden, sort_keys=True, indent=2
        ), (
            "Aggregator output drifted from golden summary. If intentional, "
            "regenerate tests/fixtures/phase_203_synthetic_summary.json."
        )
```

`tests/test_phase_204_distribution.py` mirrors this verbatim (substitute Phase 204 fixture names) for CALIB-01 distribution math.

**v1.42 NDJSON regression pattern** (`tests/test_phase_203_replay.py:87-109`):

```python
class TestV142NdjsonRegression:
    """Backward-compat: v1.42 diagnostic_distribution math preserved."""

    def test_v142_diagnostic_distribution_matches_inline_jq(self, aggregator: ModuleType) -> None:
        if not V142_NDJSON.exists() or not V142_SUMMARY.exists():
            pytest.skip(f"v1.42 reference fixtures absent at {V142_NDJSON}")
        result = aggregator.aggregate_soak(V142_NDJSON)
        v142 = json.loads(V142_SUMMARY.read_text(encoding="utf-8"))
        v142_diag = v142["diagnostic_distribution"]
        ours = result["diagnostic_distribution"]
        assert ours["rtt_integral_ms_s"]["mean"] == pytest.approx(
            v142_diag["rtt_integral_ms_s"]["mean"], rel=0.01
        )
        # ...
```

`tests/test_phase_204_watchdog.py` clones this for the watchdog math:

```python
class TestV142WatchdogRegression:
    """CALIB-03 transition oracle: legacy live-counter mean must match v1.42."""

    def test_legacy_value_matches_inline_jq_oracle(self, aggregator: ModuleType) -> None:
        # v1.42 oracle: suppression-stats.json:6 — "suppressions_per_min_mean": 6.466842364880155
        # See research §Risk 3 for the regression target.
        rows = aggregator.load_ndjson(V142_NDJSON)
        result = aggregator.aggregate_watchdog(
            rows,
            legacy_threshold=5.0,
            new_threshold=75,    # placeholder; CALIB-02 supplies real value
            statistic="p99",
        )
        assert result["secondary_gate_legacy"]["value"] == pytest.approx(
            6.466842364880155, abs=1e-6
        )
```

The v1.42 oracle file path: `.planning/milestones/v1.42-phases/201-docsis-aware-ul-congestion-control/soak/20260505T132736Z/suppression-stats.json` (verified existing per research §Q4 line 198).

**Generator drift-detection pattern** (`tests/test_phase_203_replay.py:124-136`):

```python
class TestGeneratorDriftDetection:
    """Re-running the generator must produce byte-identical NDJSON."""

    def test_fixture_matches_generator_output(self) -> None:
        generator_path = REPO_ROOT / "tests" / "fixtures" / "_phase_203_generator.py"
        generator = _load_module(generator_path, "phase_203_generator")
        regenerated = generator.generate_synthetic_ndjson()
        checked_in = SYNTHETIC_NDJSON.read_text(encoding="utf-8")
        assert regenerated == checked_in, (
            "Generator output drifted from checked-in fixture. Re-run "
            "python tests/fixtures/_phase_203_generator.py and regenerate the "
            "golden summary if intentional."
        )
```

Phase 204 should create `tests/fixtures/_phase_204_generator.py` only if synthetic fixture is non-trivial; for a watchdog test exercising PASS/FAIL branches a hand-authored 50-100 row NDJSON is fine.

---

### `.planning/phases/204-.../204-CALIB-02-OPERATOR-APPROVAL.md` (operator_approval) — NEW

**Analog:** `.planning/milestones/v1.42-phases/201-docsis-aware-ul-congestion-control/201-16-OPERATOR-APPROVAL-D19.md` (21 lines, full file). Verbatim:

```markdown
# Phase 201 — D-19 Operator Approval (Stricter Primary Soak Gate)

timestamp: 2026-05-05T13:15:37+00:00
decision: approved
operator_justification: |
  canary PASS

---

## D-19 Statement (Approved)

**D-19 (Phase 201 closure gate tightening):** Phase 201 closure adds a STRICTER PRIMARY soak gate beyond the original D-14 secondary watchdog. With the rev-4 control-model amendment in place (bounded-absolute decay + cap-and-clamp anti-windup, Plans 201-13 rev 3 / 201-14 rev 4), zero floor hits over a 24h DOCSIS soak (`floor_hit_cycles_total_delta_soak_window == 0`) is achievable as a cycle-fidelity proof of fix. The original D-14 `<5/60s` suppression-rate threshold STAYS as the SECONDARY gate (legacy compatibility, more permissive). Tightening the primary gate aligns the soak's primary metric with the canary's primary metric, so PASS at canary-time and PASS at soak-time use the same cycle-fidelity surface. Operator-approved 2026-05-XX as the closure shape for Phase 201 gap-closure path (b). Codex 201-REVIEWS LOW-CODEX-5: this tightening is captured here as a distinct operator-approval artifact, NOT silently written into a verdict file.

---

## References

- Plan 201-15 rev 3 canary PASS: `.planning/phases/201-docsis-aware-ul-congestion-control/canary/20260505T122513Z/verdict.json`
- `201-CONTEXT.md` original D-14 watchdog
- `201-REVIEWS.md` round 2 LOW-CODEX-5 (distinct approval checkpoint required)
- Captures operator approval BEFORE soak begins; gates Task 2.
```

**Phase 204 mirror template** (research §Q6 lines 293-330; structurally identical, with three additional machine-readable fields in the front-matter):

```markdown
# Phase 204 — CALIB-02 Operator Approval (D-14 Successor Threshold)

timestamp: <UTC ISO from `date -u -Iseconds`>
decision: <approved|rejected>
statistic: <p99|p95|max|mean+kσ>          # Operator picks
threshold: <integer>                        # Operator picks (the number to gate against)
headroom_factor: <float>                    # Operator picks (e.g. 1.5)
operator_justification: |
  <free-text rationale referencing CALIB-01 distribution>

---

## CALIB-02 Statement (Approved)

**CALIB-02 (D-14 successor threshold, soak-grounded):** ... [verbatim statement, research §Q6]

---

## CALIB-01 Distribution Reference

- Soak run: `.planning/phases/204-d-14-successor-recalibration-calib/soak/<CALIB_01_TS>/`
- soak-summary.json fields: mean, p50, p95, p99, max, window_count

## References

- Phase 201 RETRO Lesson #1 (metric-semantics framing)
- Phase 201 RETRO Lesson #2 (threshold-basis hygiene)
- 201-16-OPERATOR-APPROVAL-D19.md (precedent format)
- CALIB-01 baseline soak summary (path above)
- Captures operator approval BEFORE Deploy 2 + CALIB-04 verification soak begins; gates the verification plan.
```

**Front-matter machine-readable contract** (research §Q6 lines 297-303 + Plan 204-04 loader contract):

The three fields `statistic`, `threshold`, `headroom_factor` are extracted by Plan 204-04 and written into `scripts/calib_02_threshold.json`. Acceptance criterion at the artifact level:

```bash
grep -q "^decision: approved" 204-CALIB-02-OPERATOR-APPROVAL.md
grep -qE "^statistic: (p99|p95|max|mean\+ksigma)" 204-CALIB-02-OPERATOR-APPROVAL.md
grep -qE "^threshold: [0-9]+" 204-CALIB-02-OPERATOR-APPROVAL.md
grep -qE "^headroom_factor: [0-9]+\.?[0-9]*" 204-CALIB-02-OPERATOR-APPROVAL.md
```

---

### `204-RETRO.md` (retro_doc) — NEW

**Analog:** `.planning/milestones/v1.42-phases/201-docsis-aware-ul-congestion-control/201-RETRO.md` lines 1-80.

**Top-matter / outcome line pattern** (`201-RETRO.md:1-5`):

```markdown
# Phase 201 Retrospective: DOCSIS-Aware UL Congestion Control

**Phase outcome:** D-19 primary VALN-06 floor-hit gate PASSED on production v1.42.1; D-14 secondary suppression watchdog FAILED, classified as metric_semantics_and_recalibration on the YELLOW-edge dwell-hold path (independent of the bounded RED decay fix). Closed `gaps_found` via operator Route B 2026-05-06; D-14 successor work deferred to v1.43+.
**Plans completed:** 16 of 16 active plans (17 PLAN.md files materialized; ...).
**Time-on-phase:** ~3 calendar days end-to-end ...
```

**Section structure (copy verbatim, swap content):**

1. `## What Was Built` — bullet list
2. `## What Was Tested in Production` — Hypothesis / Result / Evidence files
3. `## What Worked` — bullets
4. `## What Was Inefficient / What Was Harder Than Expected` — bullets
5. `## Patterns Established (carry into future phases)` — bullets
6. `## Key Lessons` — numbered list (CALIB-05 lives here as Lesson #1: "threshold-basis hygiene")
7. `## Cross-Reference` — bullets pointing at REQUIREMENTS, CONTEXT, CALIB artifacts
8. `## Lessons for v1.44` — backlog (e.g., "drop secondary_gate_legacy; promote CALIB-02 threshold to YAML")
9. `## Open Questions / Nothing-Claimed-But-Not-Shipped`

**CALIB-05 lesson text** (verbatim mirror of Phase 201 RETRO Lesson #2 at `201-RETRO.md` line ~80):

> **Threshold-basis hygiene: inherited thresholds need explicit re-justification when the control surface changes materially.** D-14's `<5/60s` was inherited from Phase 200's qualitative framing of a pre-fix degraded baseline. The D-19 pattern (operator-approved threshold revision with documented rationale, captured in a distinct file pre-soak) should be the default.

**Acceptance grep** (research §Validation Manual-Only line 684):

```bash
grep -q "threshold-basis hygiene" .planning/phases/204-.../204-RETRO.md
```

---

### `204-VERIFICATION.md` and `204-VALIDATION.md`

**Analogs:** `.planning/milestones/v1.43-phases/203-target-edge-churn-instrumentation-obsv/203-VERIFICATION.md` and `203-VALIDATION.md`. Same project conventions; structural mirror sufficient.

`204-VALIDATION.md` already exists in the phase directory (per `ls` of `.planning/phases/204-d-14-successor-recalibration-calib/`); planner extends it rather than recreating.

---

### `204-01-DEPLOY-VERIFICATION.md` (deploy verdict, Plan 204-01)

**Analog:** `.planning/milestones/v1.42-phases/201-docsis-aware-ul-congestion-control/201-15-CANARY-VERDICT.md` — operator-readable verdict capturing two-snapshot rollback evidence + active-knob assertion table.

**Two-snapshot rollback evidence pattern** (Plan 201-15 `<interfaces>` block lines 141-171, quoted verbatim above in research §Q7):

```
T0:  snapshot A (legacy state — rollback-clean)
        - /opt/wanctl  -> /opt/wanctl-prephase201-recanary-<TS>-snapA.tar.gz
        - /etc/wanctl/spectrum.yaml -> /etc/wanctl/spectrum.yaml.prephase201-recanary-<TS>-snapA
        - VERIFY snapA YAML has 0 Phase 201 keys

T1:  predeploy gate run #1
        - if PASS: skip to T3 (no reconcile needed)
        - if BLOCK: continue to T2

T2:  reconcile YAML
        - scp configs/spectrum.yaml cake-shaper:/tmp/spectrum.yaml.new
        - ssh cake-shaper "sudo install -o root -g wanctl -m 0640 /tmp/spectrum.yaml.new /etc/wanctl/spectrum.yaml"
        - re-run predeploy gate -> must PASS

T3:  snapshot B (post-gate-PASS candidate state)
        - /opt/wanctl  -> /opt/wanctl-prephase201-recanary-<TS>-snapB.tar.gz
        - /etc/wanctl/spectrum.yaml -> /etc/wanctl/spectrum.yaml.prephase201-recanary-<TS>-snapB
        - snapB YAML now contains Phase 201 keys (the candidate); deploy evidence only

T4:  deploy v1.42.1 binary
        - REMOTE_SSH_TARGET=cake-shaper REMOTE_YAML_PATH=/etc/wanctl/spectrum.yaml ./scripts/deploy.sh spectrum cake-shaper
        - ssh cake-shaper "sudo systemctl restart wanctl@spectrum.service"

ON FAIL:
  - tar -xzf <...>-snapA.tar.gz -C /         # restore legacy binary from snapshot A
  - cp <...>-snapA /etc/wanctl/spectrum.yaml  # restore legacy YAML from snapshot A
  - VERIFY post-rollback /health.version == 1.39.0 AND Phase 201 YAML key count == 0
```

**Phase 204 application** (research §Q7 lines 376-389): Snapshot A captures `/opt/wanctl` (currently `v1.42.1`) + `/etc/wanctl/spectrum.yaml` BEFORE v1.43 install. v1.43 ships **no new YAML keys** (REQUIREMENTS.md "Out of Scope" §3); the T1/T2 reconcile step is trivially a no-op. Snapshot B is byte-identical to A, captured separately for evidence symmetry.

**Predeploy gate command** (verified existing tool at `scripts/check-safe07-source-diff.sh`, full file 51 lines):

```bash
bash scripts/check-safe07-source-diff.sh
# Default ref: b72b463 (Phase 202 close, line 21).
# Exit 0 → SAFE-07 OK; exit 1 → VIOLATION; exit 2 → ref not found.
```

**Active-control-knob assertion (Phase 204 application — METRIC-01 + OBSV-05 fields)** — pattern lifted from Plan 201-15 `<interfaces>` lines 183-193:

```bash
curl -s http://<host>:9101/health | jq -e '
  .version == "1.43.0"
  and (.wans[0].upload.hysteresis.suppressions_completed_window_count != null)
  and (.wans[0].upload.hysteresis.suppressions_completed_window_by_cause != null)
  and (.wans[0].upload.hysteresis.suppressions_lifetime_by_cause != null)
  and (.wans[0].load_rtt_ms != null)
  and (.wans[0].baseline_rtt_ms != null)
'
```

(The five new field paths are confirmed live in `scripts/soak-capture.sh:35-57` per the post-METRIC-01 / post-OBSV-05 schema.)

---

### `204-05-CALIB-04-SOAK-VERDICT.md` (soak verdict, Plan 204-05)

**Analog:** `.planning/milestones/v1.42-phases/201-docsis-aware-ul-congestion-control/201-16-SOAK-VERDICT.md` — operator-readable soak outcome + closure decisions.

**Pass-criterion code** (research §Q8 / `Code Examples` lines 859-867):

```python
import json
summary = json.loads(open("soak/<CALIB_04_TS>/soak-summary.json").read())
primary_pass = summary["primary_gate"]["verdict"] == "pass" and summary["primary_gate"]["delta"] == 0
secondary_pass = summary["secondary_gate_completed_window"]["verdict"] == "pass"
calib_04_pass = primary_pass and secondary_pass
assert calib_04_pass, f"CALIB-04 FAIL: primary={primary_pass}, secondary={secondary_pass}"
```

**Bash equivalent for verdict file** (lifted from `201-16-soak-and-closeout-PLAN.md` Task 3 patterns):

```bash
SOAK_DIR=.planning/phases/204-d-14-successor-recalibration-calib/soak/${CALIB_04_TS}
jq -e '
  .primary_gate.verdict == "pass"
  and .primary_gate.delta == 0
  and .secondary_gate_completed_window.verdict == "pass"
' $SOAK_DIR/soak-summary.json
```

**Note:** the legacy `secondary_gate_legacy` block is informational only and NOT part of the CALIB-04 pass criterion (research §Q8 line 422).

---

### Soak harness invocation (Plan 204-02 + Plan 204-05)

**Analog:** `scripts/soak-capture.sh` (60 lines, current Phase 203 capture harness, full file). Already captures all fields needed for Phase 204:
- `ul_suppressions_completed_window_count` (line 55)
- `ul_suppressions_completed_window_by_cause` (line 56)
- `ul_suppressions_lifetime_by_cause` (line 57)
- `load_rtt_delta_us` (lines 48-53)

**Invocation pattern** (verbatim from Plan 201-16 lines 188 + `scripts/soak-capture.sh` usage line 5):

```bash
SOAK_TS=$(date -u +%Y%m%dT%H%M%SZ)
mkdir -p .planning/phases/204-d-14-successor-recalibration-calib/soak/${SOAK_TS}
SOAK_DIR=.planning/phases/204-d-14-successor-recalibration-calib/soak/${SOAK_TS}

# Upload script (avoids set -u + heredoc trap; codex NEW-HIGH-2 lesson)
scp scripts/soak-capture.sh cake-shaper:/tmp/soak-capture.sh
ssh cake-shaper "chmod +x /tmp/soak-capture.sh"

# Launch in tmux with positional arg
ssh cake-shaper "tmux new-session -d -s wanctl-soak \"HEALTH_URL=http://127.0.0.1:9101/health bash /tmp/soak-capture.sh ${SOAK_TS} 2>&1 | tee /tmp/soak-capture.log\""

# Verify capture started
ssh cake-shaper "tmux list-sessions | grep wanctl-soak"
sleep 5
ssh cake-shaper "wc -l /var/tmp/wanctl-soak-${SOAK_TS}/soak-capture.ndjson"  # must be >= 1

# At T+24h:
scp cake-shaper:/var/tmp/wanctl-soak-${SOAK_TS}/soak-capture.ndjson $SOAK_DIR/soak-capture.ndjson
```

Capture-script change requirement: **none.** The Phase 203 harness already emits every field Phase 204 needs. Plan 204-04 may optionally re-upload `/tmp/soak-capture.sh` to cake-shaper for ritual symmetry, but is not required (research §A6).

---

### `CHANGELOG.md` — modify

**Analog:** `CHANGELOG.md:8` (`## v1.43-dev` block already exists). Phase 204 appends entries under existing v1.43-dev section, then on Plan 204-06 closeout flips heading to `## v1.43.0 — <YYYY-MM-DD>`.

**Pattern** (Plan 201-15 Task 1 step 5 lines 224-231):

```markdown
## v1.43.0 — 2026-05-XX

### Changed
- CALIB-03: soak-harness watchdog computation now reads completed-window count statistic; legacy live-counter-snapshot mean preserved alongside for one transition cycle (drops in v1.44).
- Operator-approved D-14 successor threshold (CALIB-02): see `.planning/phases/204-d-14-successor-recalibration-calib/204-CALIB-02-OPERATOR-APPROVAL.md`.

### Added
- METRIC-01 + OBSV-05 fields live in production `/health` (binary deploy via Plan 204-01).
- `aggregate_watchdog()` and `aggregate_completed_window_distribution()` functions in `scripts/soak_summary_aggregate.py`.
- `scripts/calib_02_threshold.json` operator-approval-derived constants file.
```

---

### `docs/SOAK_HARNESS.md` — modify

**Analog:** the file itself (Phase 203 added the per-row schema table at lines 35-58). Phase 204 appends a new section "Watchdog computation transition (CALIB-03)" describing the dual-emission pattern (research §Q5 output shape lines 240-259).

Pattern (existing schema-table style at `docs/SOAK_HARNESS.md:41-58`):

```markdown
| Key | Type | Source in `/health` | Semantics |
|-----|------|---------------------|-----------|
| `t_wall` | string | capture host clock | UTC wall-clock timestamp emitted by the capture script. |
| `t_monotonic` | float | capture host `/proc/uptime` | Seconds since capture start, monotonic-clock derived. |
...
```

For the watchdog transition section, document the two top-level keys `secondary_gate_legacy` and `secondary_gate_completed_window` with the exact JSON-shape from research §Q5 lines 240-259.

---

## Shared Patterns

### Stdlib-only Python (applies to all script/test work)

**Source:** `scripts/soak_summary_aggregate.py:1-32` + Phase 203 RESEARCH §`Stdlib-only Python` lock.

**Apply to:** `scripts/soak_summary_aggregate.py` extensions, `tests/test_phase_204_*.py`, `tests/fixtures/_phase_204_generator.py` (if created).

**Excerpt** (`scripts/soak_summary_aggregate.py:22-32`):

```python
from __future__ import annotations

import argparse
import bisect
import json
import math
import statistics
import sys
from collections.abc import Iterable
from pathlib import Path
from typing import Any
```

No NumPy. No pandas. No external deps. Phase 204 inherits this discipline.

### Black 100 char + Ruff + MyPy + Pytest gates

**Source:** project `CLAUDE.md` line 81 + `pyproject.toml`. **Apply to:** all Python edits.

```bash
.venv/bin/ruff check src/ tests/      # Note: Phase 204 doesn't touch src/, but tests/ runs.
.venv/bin/mypy src/wanctl/            # Phase 204 doesn't touch src/wanctl/, MyPy is no-op for diff.
.venv/bin/ruff format src/ tests/
make ci                               # Per CLAUDE.md
```

### Hot-path regression gate (per-plan commit)

**Source:** `CLAUDE.md` "Focused hot-path regression slice".

**Apply to:** every plan's verify block.

```bash
.venv/bin/pytest -o addopts='' \
  tests/test_cake_signal.py \
  tests/test_queue_controller.py \
  tests/test_wan_controller.py \
  tests/test_health_check.py -q
```

### SAFE-07 verification (Plan 204-01 predeploy gate AND Plan 204-06 closeout)

**Source:** `scripts/check-safe07-source-diff.sh` (51 lines, full file already shipped).

**Apply to:** Plan 204-01 predeploy step; Plan 204-06 closeout checklist.

```bash
# Predeploy / closeout — MUST exit 0
bash scripts/check-safe07-source-diff.sh
# Expected output: "SAFE-07 OK: no src/wanctl/ diff vs b72b463"
```

The default ref is `b72b463` baked at line 21. If a future phase rebaselines, the script accepts a positional arg or `PHASE_202_CLOSE` env var.

### SAFE-05 pin verification (Plan 204-06 closeout)

**Source:** `tests/test_phase_195_replay.py:642-714` (three-dict pin block).

**Apply to:** Plan 204-06 closeout. Three dicts must remain byte-identical to Phase 202 close state:

- `expected_counts` (lines 663-673) — v1.40/v1.41 thresholds
- `phase201_expected_counts` (lines 686-693) — v1.42 keys
- `phase202_expected_counts` (lines 702-711) — v1.43 Phase 202 keys

```bash
.venv/bin/pytest tests/test_phase_195_replay.py -v -k "safe05_threshold_name_counts"
# Expected: 1 passed.
```

**No `phase204_expected_counts` dict added** (research §Q10 line 480). Phase 204 introduces zero new `src/wanctl/` symbols.

### Operator-blocking checkpoint task pattern (Plans 204-01, 204-02, 204-03, 204-05)

**Source:** Plan 201-15 Task 2 (`.planning/milestones/v1.42-phases/201-.../201-15-recanary-PLAN.md:261-325`) and Plan 201-16 Task 1.

Excerpt (`201-16-soak-and-closeout-PLAN.md:244-310`):

```xml
<task type="checkpoint:human-verify" gate="blocking">
  <name>...</name>
  <read_first>...</read_first>
  <files>...</files>
  <what-built>...</what-built>
  <how-to-verify>
    1. Confirm prerequisite ...
    2. Operator decides: ...
  </how-to-verify>
  <resume-signal>Type one of: "approved: <free-text>" or "rejected: <reason>". ...</resume-signal>
  <acceptance_criteria>
    - Operator typed "approved"
    - ...
  </acceptance_criteria>
</task>
```

**Apply to:** Plan 204-01 predeploy approval, Plan 204-02 soak-start approval, Plan 204-03 CALIB-02 threshold approval, Plan 204-05 soak-start approval. CLAUDE.md change policy explicitly requires operator approval for all production deploys.

### Plan front-matter pattern (every Plan 204-* file)

**Source:** `.planning/milestones/v1.43-phases/203-target-edge-churn-instrumentation-obsv/203-02-soak-summary-aggregator-and-replay-PLAN.md:1-60`.

```yaml
---
id: 203-02
phase: 203
plan: 02
type: execute
wave: 2
depends_on:
  - 203-01
files_modified:
  - <files>
autonomous: true
production_canary: false
created: 2026-05-06
requirements:
  - OBSV-06
  - OBSV-07
  - SAFE-07
must_haves:
  truths:
    - "<short, grep-verifiable claim>"
  artifacts:
    - path: <path>
      provides: "<what this artifact provides>"
      contains: "<grep-friendly substring>"
  key_links:
    - from: "<source>"
      to: "<target>"
      via: "<relationship>"
      pattern: "<grep substring>"
---
```

Every Plan 204-* PLAN.md MUST use this front-matter shape. Map per-plan REQ-IDs (CALIB-01..05 + SAFE-07) into the `requirements` list.

---

## No Analog Found

| File | Role | Reason |
|------|------|--------|
| `scripts/calib_02_threshold.json` | threshold_artifact | No precedent of a JSON config file under `scripts/` consumed by another script. Closest pattern is `tests/fixtures/phase_203_synthetic_summary.json` (golden test JSON), but that lives under `tests/`. Planner should treat this as a NEW pattern; the loader code in `scripts/soak_summary_aggregate.py` is the reusable interface (research §`Code Examples` lines 765-777). |

Everything else has an exact or role-match analog with file/line citations above.

---

## Critical Pre-Verified Facts (planner can cite verbatim without re-research)

1. **`b72b463` is clean today** — `git diff b72b463..HEAD -- src/wanctl/` returns 0 lines (research §11 line 32).
2. **v1.42 oracle value** — `suppressions_per_min_mean = 6.466842364880155` at `.planning/milestones/v1.42-phases/201-docsis-aware-ul-congestion-control/soak/20260505T132736Z/suppression-stats.json:6` (research §Q4 line 198).
3. **v1.42 codex re-aggregation oracle** — peak mean ~13.9, p95=41, max=124, n=1331 windows over 84,117 samples. Pinned in `tests/test_phase_202_replay.py` (research §Q1 lines 100-104).
4. **All Phase 203 capture fields needed by Phase 204 are already live** — `scripts/soak-capture.sh:55-57` (`ul_suppressions_completed_window_count`, `ul_suppressions_completed_window_by_cause`, `ul_suppressions_lifetime_by_cause`) and lines 48-53 (`load_rtt_delta_us`).
5. **Aggregator already exists and is extensible** — `scripts/soak_summary_aggregate.py` 297 lines, stdlib-only, with `percentile()`, `histogram()`, `_build_cell()`, `aggregate_completed_windows()` reusable helpers.
6. **Predeploy gate already wired** — `scripts/check-safe07-source-diff.sh` 51 lines, exit-0 today.
7. **Operator-approval template precedent is a 21-line file** — verbatim available; planner can mirror byte-for-byte.
8. **Two-snapshot rollback semantics are documented verbatim** — Plan 201-15 lines 30-31 + 141-171.

---

## Metadata

**Analog search scope:**
- `scripts/` (all .py + .sh) — full enumeration via `ls`
- `tests/test_phase_{202,203}_*.py` — read for class-structure patterns
- `.planning/milestones/v1.42-phases/201-.../*.md` — operator-approval, two-snapshot, soak-verdict precedents
- `.planning/milestones/v1.43-phases/{202,203}-.../*.md` — recent Phase 202/203 plan front-matter and structure
- `docs/SOAK_HARNESS.md` — schema documentation pattern
- `CHANGELOG.md` — changelog conventions
- `tests/test_phase_195_replay.py` — SAFE-05 pin block (read-only at v1.43 close)

**Files scanned (counted):** 16 source/script + 8 markdown precedents + 3 docs + 2 CHANGELOG/pyproject = 29 distinct file reads, with no overlapping ranges.

**SAFE-07 audit confirmation:** none of the 16 file targets fall inside `src/wanctl/` except the version-bump trio (`src/wanctl/__init__.py`, `pyproject.toml`, `docker/Dockerfile`) at Plan 204-01 — verified via cross-reference against the SAFE-05 pin dicts that those literals are not pinned.

**Pattern extraction date:** 2026-05-06.

**Confidence:** HIGH on every analog (each cited with file path + line range, verified via `Read` against current tree). MEDIUM on whether `tests/test_phase_204_replay.py` should be a sibling file vs folded into `tests/test_phase_204_watchdog.py` — research §Wave 0 Gaps lines 670-675 leaves this to planner preference.
