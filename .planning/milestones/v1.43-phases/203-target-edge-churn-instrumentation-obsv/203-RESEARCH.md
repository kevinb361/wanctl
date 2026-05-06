# Phase 203: Target-Edge Churn Instrumentation (OBSV) - Research

**Researched:** 2026-05-06
**Domain:** wanctl soak-harness additive instrumentation (NDJSON capture schema + soak-summary aggregation). No production binary change.
**Confidence:** HIGH for code surfaces and Phase 202 precedent; MEDIUM for histogram bucket scheme and aggregator implementation choice (greenfield decision space).

---

## Summary

Phase 203 is a soak-harness-only phase that mirrors the Phase 202 additive precedent on the *capture/aggregation* side rather than the `/health` side. Two surfaces change:

1. **`soak-capture.sh`-style harness:** the `jq` projection that writes each NDJSON row gains one new field, `load_rtt_delta_us = (load_rtt_ms - baseline_rtt_ms) * 1000` (integer microseconds), plus the four Phase 202 cause-tag fields needed for the breakdown axis (`suppressions_completed_window_count`, `suppressions_completed_window_by_cause`, `suppressions_lifetime_by_cause`, `last_zone`). All five inputs are already exposed by the post-Phase-202 `/health` surface — no daemon code change is required.
2. **`soak-summary.json` aggregator:** today this is an inline `jq` pipeline embedded in the soak closeout PLAN, not a versioned script in `scripts/`. Phase 203 should promote it to a versioned, reusable Python aggregator under `scripts/` and extend it to emit `load_rtt_delta_us` p50/p95/p99/max + a histogram broken down by `(zone, cause_tag)` cells. Promoting from inline-jq to versioned-script is a *necessary* Phase 203 deliverable — Phase 204 (CALIB) requires a reusable, testable aggregator to compute the recalibration baseline distribution from the CALIB-01 24h soak.

**Critical fixture finding:** the v1.42 reference NDJSON at `.planning/milestones/v1.42-phases/.../soak/20260505T132736Z/soak-capture.ndjson` predates **both** Phase 202 (cause-tag fields not exposed) **and** the Phase 203 capture additions (`load_rtt_ms`, `baseline_rtt_ms` not in projection). The golden-fixture replay test cannot run end-to-end against v1.42 raw NDJSON; it must run against either (a) a v1.42-derived synthetic-augmentation fixture that adds the new columns or (b) a small new in-tree minimal fixture that exercises the aggregator's `(zone, cause)` histogram math. **Recommend (b) plus a separate row-shape contract test that checks the post-203 capture script *would* emit the right keys against a synthesized `/health` blob.** This is documented as Open Question #1 below — the planner needs to lock the choice.

**Primary recommendation:** Three plans, not four. The harness capture additions, the aggregator promotion+extension, and the docs+SAFE-07 verification compose cleanly into three plans. Phase 202's plan-04 SAFE-05 pin extension has no analogue here (no source code added → no new pins) — that work folds into the docs/closeout plan.

**SAFE-07 verification for a harness-only phase:** mechanical `git diff` of `src/wanctl/` between Phase 202 close and Phase 203 close must be empty. The existing `tests/test_phase_195_replay.py::test_safe05_threshold_name_counts_are_unchanged` block (v1.40/v1.41 + v1.42 phase201 + v1.43 phase202 dicts) must produce identical assertion results — no Phase 203 dict added. This is the Phase 203 analogue of "v1.43 closeout invariant" verification.

---

## User Constraints (from ROADMAP + REQUIREMENTS + SEED-004)

### Locked Decisions

- **Additive only.** No control-path source diff between Phase 201 close and v1.43 close (SAFE-07). Existing v1.40/v1.41/v1.42/v1.43-Phase-202 SAFE-05 pin blocks in `tests/test_phase_195_replay.py:642-714` remain byte-identical at Phase 203 close.
- **No production canary required.** Soak-harness change reads existing exposed `/health` fields and computes the delta in the harness (per SEED-004 frontmatter + ROADMAP Phase 203 production-deploy cadence). Production binary change is acceptable ONLY if a needed field is absent from the post-METRIC-01 `/health` surface — see §`Field availability audit` below; conclusion: **no binary change needed**.
- **No new YAML config keys** (per REQUIREMENTS.md "Out of Scope" §3).
- **Replay oracle:** v1.42 reference soak NDJSON at `.planning/milestones/v1.42-phases/201-docsis-aware-ul-congestion-control/soak/20260505T132736Z/soak-capture.ndjson`. With caveats — see §`Golden-fixture replay strategy`.
- **Cause-tag axis:** `dwell_hold` / `backlog_recovery` / `other` (locked by Phase 202 METRIC-02; cannot be re-defined here).
- **Zone axis:** `GREEN` / `YELLOW` / `SOFT_RED` / `RED` for upload (4-state). Download uses 3-state today (no `SOFT_RED`); see §`Zone axis ambiguity` for handling.
- **`load_rtt_delta_us` formula:** `(effective_ul_load_rtt - baseline_rtt_ms) * 1000`, integer microseconds (per SEED-004 + ROADMAP success criterion 1).

### Claude's Discretion

- **Aggregator language and placement.** The Phase 201 inline-jq pipeline is not reusable. Recommend a Python aggregator at `scripts/soak_summary_aggregate.py` (snake-case to match `analyze_baseline.py`, `analyze_profiling.py`, `compare_ab.py`). Reasoning: Phase 204 needs the same aggregator to compute the CALIB-01 baseline distribution; Python is more testable than jq; no new system dependencies (Python is already standard tooling); follows the project's existing `analyze_*.py` pattern.
- **Histogram bucket scheme.** Recommendation in §`Histogram bucket scheme` below: linear buckets keyed to operator-relevant breakpoints (`target_delta_us`, `warn_delta_us`, `hard_red_threshold`) plus a fixed log-scaled tail. Rationale below.
- **Empty-cell encoding in zone × cause-tag matrix.** Recommendation: emit a fully-zeroed histogram object with `count: 0`. Mirrors Phase 202's "empty cause = `0`, not omitted" convention from `suppressions_completed_window_by_cause`. Operator readability + soak-summary diff stability favor this.
- **Field placement in NDJSON.** Top-level `load_rtt_delta_us`. The Phase 202 cause-tag fields needed as input also go top-level (matches the existing flat schema — every other captured field is top-level). No nesting; the existing `soak-capture.sh` projection is flat by design.
- **`baseline_rtt_ms` unset/null handling.** Daemon initialization sets `self.baseline_rtt = config.baseline_rtt_initial` (a numeric YAML value, default 8-12ms depending on link). It is *never* `None` after `WANController.__init__`. Therefore `load_rtt_delta_us` is always computable. Recommendation: emit as integer always; no null branch needed.
- **Plan count and slicing.** Three plans (203-01 capture; 203-02 aggregator; 203-03 docs+SAFE-07 verification). See §`Recommended plan slicing`.

### Deferred Ideas (OUT OF SCOPE)

- **Threshold derivation from the new histogram.** That is Phase 204 (CALIB). Phase 203 ships the data shape; Phase 204 reads it.
- **Tuning recommendations from `load_rtt_delta_us` distribution.** SEED-005 territory; structurally barred from v1.43 by SAFE-07.
- **Soak-monitor.sh changes.** Phase 203 owns soak-CAPTURE harness only. `scripts/soak-monitor.sh` is the live operator dashboard, not the soak capture/aggregation chain. Do not touch.
- **Replacing `suppressions_per_min` capture.** Backward-compat with existing v1.42 traces is preserved by SEED-002 / Phase 202 invariant; Phase 203 *adds* fields, does not remove the existing one.
- **Histogram of `rtt_integral_ms_s`, `max_delay_delta_us`, etc.** SEED-004 names `load_rtt_delta_us` only. Other fields stay where they are (per-sample top-level + ad-hoc analysis). Future seed if needed.

---

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| OBSV-05 | Soak NDJSON captures per-sample `load_rtt_delta_us` (= `effective_ul_load_rtt - baseline_rtt_ms` in microseconds) on every sample. | §`Field availability audit`, §`Capture script delta`. Both source fields already exposed at `/health.wans[].load_rtt_ms` and `/health.wans[].baseline_rtt_ms` (verified at `health_check.py:248-249`). |
| OBSV-06 | `soak-summary.json` aggregates `load_rtt_delta_us` as histogram + p50/p95/p99/max over the soak window, broken down by zone (GREEN/YELLOW/SOFT_RED/RED) and by cause-tag (from Phase 202's METRIC-02). | §`Aggregator promotion`, §`Histogram bucket scheme`, §`Zone axis ambiguity`. The current soak-summary.json producer is an inline jq pipeline embedded in the closeout PLAN — must be promoted to a versioned aggregator. |
| OBSV-07 | Golden-fixture replay test confirms the new field is populated and aggregated correctly against a known-good capture; SAFE-05 control-path pins remain unchanged (SAFE-07 verification). | §`Golden-fixture replay strategy`, §`SAFE-07 verification mechanism`. v1.42 raw NDJSON predates the new fields — replay strategy uses synthesized augmentation + small in-tree contract fixtures. |
| OBSV-08 | Soak harness README and `CHANGELOG.md` document the new field, the zone × cause-tag breakdown contract, and the no-control-path-change invariant. | §`Documentation surface`. No `soak-harness/README.md` exists today — must be created. CHANGELOG follows Phase 202 v1.43-dev pattern. |
| SAFE-07 | No control-path source diff between Phase 201 close and v1.43 close. | §`SAFE-07 verification mechanism`. Mechanical: `git diff <phase-201-close>..HEAD -- src/wanctl/` empty. |

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Per-sample `load_rtt_delta_us` computation | soak-capture harness (jq projection) | — | Both inputs (`load_rtt_ms`, `baseline_rtt_ms`) already exposed in `/health`. Computing the delta in the harness keeps this a pure-additive observability change with no daemon edit. |
| Cause-tag input capture | soak-capture harness (jq projection of Phase 202 fields) | — | Phase 202 already exposes `suppressions_completed_window_by_cause` and `suppressions_lifetime_by_cause` in `/health`. The harness adds them to the per-row projection. |
| Zone label for each sample | soak-capture harness (jq projection of `hysteresis.last_zone`) | — | `last_zone` is already exposed at `/health.wans[].upload.hysteresis.last_zone` (verified at `health_check.py:319`). Currently the v1.42 capture script projects `zone_trace_tail` (last 5 zones) but NOT the canonical `last_zone` — Phase 203 must add it. |
| Soak-summary aggregation | new versioned script (`scripts/soak_summary_aggregate.py`) | — | The Phase 201-16 aggregator was an inline jq pipeline in the closeout PLAN. Promoting to a versioned, testable Python script is a Phase 203 prerequisite for Phase 204's CALIB-01 baseline computation. |
| Histogram + percentile math | aggregator | — | Stdlib `statistics`/`bisect` is sufficient; no NumPy dependency. Matches `tests/test_phase_202_replay.py::_percentile` precedent (NumPy-free). |
| SAFE-07 verification | `git diff` + existing `test_safe05_threshold_name_counts_are_unchanged` test | — | Harness-only phase; no `src/wanctl/` change → mechanical diff plus unchanged pin test results. |

---

## Field availability audit

The Phase 203 harness must capture five additional fields per sample beyond the v1.42 projection. Verify each is already exposed in the post-Phase-202 `/health` surface so no binary change is required.

| Required input | Path in `/health` | Source code | Available? |
|----------------|-------------------|-------------|------------|
| `load_rtt_ms` | `wans[0].load_rtt_ms` | `health_check.py:249` (`round(wan_controller.load_rtt, 2)`) | ✓ exposed since pre-v1.43 |
| `baseline_rtt_ms` | `wans[0].baseline_rtt_ms` | `health_check.py:248` (`round(wan_controller.baseline_rtt, 2)`) | ✓ exposed since pre-v1.43 |
| `suppressions_completed_window_count` (UL) | `wans[0].upload.hysteresis.suppressions_completed_window_count` | `health_check.py:321-323` (Phase 202) | ✓ exposed at v1.43 Phase 202 close |
| `suppressions_completed_window_by_cause` (UL) | `wans[0].upload.hysteresis.suppressions_completed_window_by_cause` | `health_check.py:324-327` (Phase 202) | ✓ exposed at v1.43 Phase 202 close |
| `last_zone` (UL) | `wans[0].upload.hysteresis.last_zone` | `health_check.py:319` | ✓ exposed since pre-v1.43 |

**Conclusion:** all five required inputs are present in the post-Phase-202 `/health` surface. **No production binary change required.** SEED-004 frontmatter expectation holds.

### Asymmetry-gate edge case

The seed says `load_rtt_delta_us = effective_ul_load_rtt - baseline_rtt_ms`. `effective_ul_load_rtt` is computed by `WANController._compute_effective_ul_load_rtt()` at `wan_controller.py:2716-2774` and is **not exposed in `/health`**. It applies asymmetry-gate attenuation when downstream-only congestion is detected.

**Spectrum cable (the v1.43 baseline link):** asymmetry gate is disabled by default (`autorate_config.py:1184`) and `configs/spectrum.yaml` does not enable it. Verified: no `asymmetry_gate:` section exists in the active Spectrum config. Therefore on Spectrum, `effective_ul_load_rtt == self.load_rtt`. The harness can compute `load_rtt_delta_us = (load_rtt_ms - baseline_rtt_ms) * 1000` and get the seed's intended semantics for free.

**ATT / future links with asymmetry gate enabled:** `load_rtt_ms` (raw) and `effective_ul_load_rtt` (attenuated) diverge. The harness-computed delta would over-state the perceived target-edge churn in those windows.

**Recommendation:** for v1.43 Phase 203 ship the raw-`load_rtt_ms`-based delta. Document the limitation. Add to SEED-004's open-questions follow-up: if asymmetry-gate-enabled deployments need accurate target-edge instrumentation, that is a separate seed for a binary `/health` addition (`effective_ul_load_rtt_ms` exposure). v1.43 milestone goal is Spectrum recalibration; portability beyond Spectrum can wait.

**Risk if wrong:** for the CALIB-01 baseline soak (Phase 204) which runs on Spectrum, the delta is exact. For any future ATT-gate-enabled soak, the field would be off by the gate-attenuation factor during gate-active windows. Operator-readable doc note covers this. **Confidence: HIGH** that this is the right v1.43 trade.

---

## Capture script delta

### Reference: existing v1.42 capture projection (`soak-capture.sh:15-33`)

```bash
curl -s "$HEALTH_URL" \
  | jq -c --arg twall "$(date -u -Iseconds)" --argjson tmono "$T_MONO_DELTA" '{
      t_wall: $twall,
      t_monotonic: $tmono,
      version: .version,
      status: .status,
      floor_hit_cycles_total: .wans[0].upload.floor_hit_cycles_total,
      suppressions_per_min: .wans[0].upload.hysteresis.suppressions_per_min,
      max_delay_delta_us: .wans[0].upload.max_delay_delta_us,
      red_streak: .wans[0].upload.red_streak,
      zone_trace_tail: (.wans[0].upload.zone_trace | .[-5:]),
      headroom_state: .wans[0].upload.headroom_state,
      headroom_exhausted_streak: .wans[0].upload.headroom_exhausted_streak,
      anti_windup_triggers: .wans[0].upload.anti_windup_triggers,
      rtt_integral_ms_s: .wans[0].upload.rtt_integral_ms_s,
      docsis_mode_active: .wans[0].upload.docsis_mode_active,
      red_decay_step_pct: .wans[0].upload.red_decay_step_pct,
      red_decay_delta_max_pct: .wans[0].upload.red_decay_delta_max_pct
    }' >> "$CAPTURE_DIR/soak-capture.ndjson"
```

### Phase 203 additions (proposed; verbatim diff against the v1.42 script)

```bash
# Phase 203 capture additions (additive — preserve all existing keys verbatim):
load_rtt_ms: .wans[0].load_rtt_ms,
baseline_rtt_ms: .wans[0].baseline_rtt_ms,
load_rtt_delta_us: ((.wans[0].load_rtt_ms - .wans[0].baseline_rtt_ms) * 1000 | floor),
last_zone: .wans[0].upload.hysteresis.last_zone,
ul_suppressions_completed_window_count: .wans[0].upload.hysteresis.suppressions_completed_window_count,
ul_suppressions_completed_window_by_cause: .wans[0].upload.hysteresis.suppressions_completed_window_by_cause,
ul_suppressions_lifetime_by_cause: .wans[0].upload.hysteresis.suppressions_lifetime_by_cause
```

Notes:
- `load_rtt_ms` and `baseline_rtt_ms` are projected explicitly as raw inputs — not strictly needed once the delta is computed, but valuable for forensic re-aggregation if the delta math ever needs to be re-checked. Cheap (two more numeric fields per row at 1Hz).
- `floor` truncates to integer microseconds. Both source fields are already 2-decimal-rounded ms, so `(load_rtt_ms - baseline_rtt_ms) * 1000` produces an integer-ish float; `floor` is the safe coercion. Alternative: cast via `(... * 1000 | round)` if half-rounding is preferred. Recommendation: `floor` (matches existing `int(...)` casts in `health_check.py` for `max_delay_delta_us` etc.).
- `last_zone` is added as a top-level field even though `zone_trace_tail` already provides the last-5-zones context. Reason: the aggregator's per-sample zone bucket needs ONE canonical zone label per row. Using `zone_trace_tail[-1]` works in jq but is less robust than projecting `last_zone` directly. Both are 1Hz cheap.
- `ul_*` prefix on the three Phase 202 fields disambiguates from any future download-side capture. The same fields exist on `wans[0].download.hysteresis.*`; if the aggregator ever needs DL breakdown, a future seed adds `dl_*` siblings without churning the existing `ul_*` keys.

### Where the new capture script lives

The v1.42 reference `soak-capture.sh` lives **in the soak-evidence directory** (`.planning/milestones/v1.42-phases/.../soak/20260505T132736Z/soak-capture.sh`), uploaded ad-hoc per Plan 201-16's NEW-HIGH-2-fix pattern. There is no versioned canonical `scripts/soak-capture.sh` in the repo today.

**Recommendation:** Phase 203 creates `scripts/soak-capture.sh` as the canonical, versioned harness. Move the existing inline-in-PLAN pattern into `scripts/`. The closeout PLAN can still upload it via `scp`, but the source of truth is `scripts/soak-capture.sh`. This is necessary for OBSV-08 ("soak harness README") to point to a real file, and necessary for Phase 204's CALIB-01 soak which will reuse the same harness with the new fields.

**Risk:** promoting to `scripts/` means the script is now subject to the project's `make ci` test slice. ShellCheck is not currently run on `scripts/*.sh` (verified by glance at Makefile + pre-commit config), so no new lint friction. The script remains executable bash with no Python dependency.

---

## Aggregator promotion

### Current state (verified)

The Phase 201-16 closeout PLAN at `.planning/milestones/v1.42-phases/201-.../201-16-soak-and-closeout-PLAN.md` embeds the soak-summary computation as an inline `jq -s 'sort_by(.t_monotonic) as $rows | reduce $rows[] as $sample (...)'` pipeline executed against `soak-capture.ndjson` to produce `suppression-stats.json`, then a second hand-assembled jq+bash block produces `soak-summary.json`.

This is unsustainable for Phase 203's needs:
- The histogram math in jq for `(zone, cause)` cells with bucket boundaries is gnarly.
- Phase 204 (CALIB-01) needs to re-run this aggregator against a new 24h soak. The aggregator must be reusable, callable, and tested.
- The current jq pipeline has already had two correctness bugs (codex NEW-HIGH-3 `$rows` binding, NEW-HIGH-2 SOAK_TS heredoc). Python aggregator with unit tests is more defensible.

### Proposed: `scripts/soak_summary_aggregate.py`

```
scripts/soak_summary_aggregate.py
  - read NDJSON file, return list of rows
  - aggregate_completed_windows(snapshots) -> existing helper, lift from tests/test_phase_202_replay.py
  - histogram(values, buckets) -> list[(bucket_label, count)]
  - percentile(values, p) -> float (NumPy-free, copy from test_phase_202_replay._percentile)
  - aggregate_load_rtt_delta(rows) -> {p50, p95, p99, max, histogram}
  - aggregate_by_zone_cause(rows) -> {(zone, cause): {p50, p95, p99, max, histogram, count}}
  - cli: aggregate_soak(ndjson_path) -> writes soak-summary.json
```

The existing test helpers in `tests/test_phase_202_replay.py` (`aggregate_completed_windows`, `_percentile`) should be lifted into the new aggregator module and the test should import them from there, eliminating duplication. (This is a small refactor of test imports — not a behavioral change to Phase 202 — and pins the helpers to a stable location for Phase 204 reuse.)

### Output schema delta in `soak-summary.json`

Existing v1.42 reference shape (verified at `.planning/milestones/v1.42-phases/.../soak/20260505T132736Z/soak-summary.json`):

```json
{
  "phase": 201,
  "plan": 16,
  "soak_ts": "...",
  "v_binary": "1.42.1",
  "duration_sec": 86400,
  "sample_coverage_ratio": 0.974,
  "primary_gate": {...},
  "secondary_gate": {...},
  "diagnostic_distribution": {
    "rtt_integral_ms_s": {"mean": 5.14, "max": 270.6},
    "max_delay_delta_us": {"mean": 810.3, "max": 161281},
    "red_streak": {"mean": 0.006, "max": 101},
    "headroom_exhausted_samples": 469,
    "total_samples": 84117
  },
  "anti_windup_triggers_delta": 0,
  "verdict": "fail",
  "reason": "soak_gates_disagreement_primary_pass_secondary_fail"
}
```

Phase 203 additive shape (additions in **bold**):

```json
{
  ...existing keys preserved verbatim...,
  "diagnostic_distribution": {
    ...existing keys preserved verbatim...,
    "load_rtt_delta_us": {
      "p50": 142,
      "p95": 8412,
      "p99": 21305,
      "max": 161281,
      "histogram": {
        "buckets_us": [0, 1000, 3000, 6000, 10000, 15000, 25000, 50000, 100000, 250000],
        "counts":     [12044, 31229, 18113, 9871, 5102, 3344, 2987, 1003, 287, 137]
      }
    }
  },
  "load_rtt_delta_us_by_zone_cause": {
    "GREEN": {
      "dwell_hold":       {"p50": 84, "p95": 712, "p99": 1880, "max": 4012, "count": 31044, "histogram": {"buckets_us": [...], "counts": [...]}},
      "backlog_recovery": {"p50": 0,  "p95": 0,   "p99": 0,    "max": 0,    "count": 0,     "histogram": {"buckets_us": [...], "counts": [...]}},
      "other":            {"p50": 0,  "p95": 0,   "p99": 0,    "max": 0,    "count": 0,     "histogram": {"buckets_us": [...], "counts": [...]}}
    },
    "YELLOW": {
      "dwell_hold":       {...},
      "backlog_recovery": {...},
      "other":            {...}
    },
    "SOFT_RED": {...},
    "RED": {...}
  }
}
```

### Cell-population semantics

Each NDJSON row contributes to exactly **one cell** of the `(zone, cause)` matrix. The `cause` axis is taken from "what caused the suppression at this sample" — i.e. the cause-tag whose lifetime counter incremented since the previous sample. For samples with no suppression in the previous-cycle (most of them), the row is excluded from the `(zone, cause)` decomposition entirely (it appears in the un-decomposed top-level `diagnostic_distribution.load_rtt_delta_us`).

Why "lifetime delta" rather than completed-window snapshot: completed-window counters update only at 60s boundaries, so they cannot attribute a particular sample to a particular cause. Lifetime counters increment per-cycle and the per-sample delta IS the per-cycle attribution.

This is the cleanest semantic; document it explicitly in the soak-harness README. The Phase 204 CALIB-01 baseline read uses the same attribution.

**Edge case:** the very first sample of a soak has no previous sample to delta against → no cause-attribution possible → goes into the top-level histogram only. Mechanically, the aggregator skips the first row's contribution to `load_rtt_delta_us_by_zone_cause`.

---

## Histogram bucket scheme

OBSV-06 wants a histogram in `soak-summary.json`. The bucket scheme must be locked here so the aggregator and test code agree.

### Tradeoffs considered

**Option A: Operator-relevant breakpoints (recommended).** Bucket boundaries align with the controller's threshold semantics in microseconds:
- `[0, target_delta_us, warn_delta_us, hard_red_threshold_us, ∞)` — four operator-meaningful bands corresponding to GREEN-comfortable / YELLOW-edge / SOFT_RED-edge / RED.
- Within each band, sub-buckets log-spaced for resolution: e.g. `[0, 1000, 3000, target_delta, 6000, 10000, warn_delta, 15000, 25000, hard_red, 50000, 100000, 250000]` µs.
- Pros: histogram cells map directly to operator's mental model. The Phase 204 threshold derivation reads the histogram and points at a band boundary.
- Cons: bucket boundaries depend on link config (`target_bloat_ms`, `warn_bloat_ms`, `hard_red_bloat_ms` from YAML). Aggregator needs to read the YAML or accept thresholds as CLI args.

**Option B: Fixed-width µs bins.** E.g. 0-100k µs in 1ms bins → 100 buckets.
- Pros: link-config-independent; cross-link comparison straightforward.
- Cons: 100-bucket JSON is verbose; cells in `(zone, cause)` 4×3 = 12 cells × 100 buckets = 1200 numbers in `soak-summary.json`. Operator-unreadable.

**Option C: Log-spaced.** Powers of 2 from 1µs to 1s.
- Pros: compact; covers full dynamic range cheaply.
- Cons: operator has to translate "bucket 14 = 16ms" — extra cognitive load.

### Recommendation: Option A with link-config-aware boundaries

The aggregator reads `target_bloat_ms`, `warn_bloat_ms`, and (where present) `hard_red_bloat_ms` from a YAML config OR from a CLI flag pair (defaults: target=15ms, warn=30ms, hard_red=60ms — the v1.42 Spectrum values). It emits boundaries into the histogram object itself (`buckets_us` array) so consumers don't need the config to interpret the data.

Default bucket array (Spectrum v1.42 values):
```python
DEFAULT_BUCKETS_US = [
    0,         # GREEN floor
    1000,      # 1ms — GREEN-comfortable resolution
    3000,      # 3ms
    6000,      # 6ms
    10000,     # 10ms — under target_delta (15ms)
    15000,     # target_delta_us — YELLOW-edge boundary
    20000,     # 20ms
    30000,     # warn_delta_us — SOFT_RED-edge boundary
    45000,     # 45ms
    60000,     # hard_red_threshold_us — RED-edge boundary
    100000,    # 100ms
    250000,    # tail
]
# Anything above last bucket counts in an "overflow" cell.
```

12 buckets × 12 cells = 144 numbers in the breakdown. Acceptable. The top-level un-decomposed histogram is one row of 12 numbers.

**Forward-compatibility:** if Phase 204 needs different boundaries (e.g. operator decides target_bloat changes for v1.44), the aggregator accepts CLI flags. The boundary values are written into the JSON output, so old soak-summary.json files remain interpretable even if defaults drift.

---

## Zone axis ambiguity

OBSV-06 names the axis "GREEN/YELLOW/SOFT_RED/RED". This matches the upload 4-state model. **Download uses 3-state today** (GREEN/YELLOW/RED, no SOFT_RED — confirmed at `queue_controller.py:3` module docstring and existing zone classification methods).

### What the axis means in the aggregator

The capture script projects `last_zone` from `wans[0].upload.hysteresis.last_zone` (4-state). All `load_rtt_delta_us` per-sample readings are attributed to the **upload zone state**. This is correct — the seed names `effective_ul_load_rtt`, an upload-side metric, and the recalibration target (D-14 successor) is the UL hysteresis suppression rate. UL zone is the only zone that matters for v1.43.

The aggregator's matrix is therefore 4 zones × 3 causes = 12 cells. SOFT_RED rows will be populated; download-side never enters this aggregation.

**Recommendation:** document explicitly in the soak-harness README that the zone axis is upload-state. If v1.44 or later wants the same matrix for download, it gets a separate `dl_load_rtt_delta_us_by_zone_cause` field with a 3-state matrix. Not in v1.43 scope.

---

## Golden-fixture replay strategy

OBSV-07 requires a golden-fixture replay test. The naive fixture choice — `soak-capture.ndjson` from the v1.42 reference soak — has critical gaps.

### v1.42 fixture limitations (verified)

The v1.42 NDJSON at `.planning/milestones/v1.42-phases/.../soak/20260505T132736Z/soak-capture.ndjson` was produced by the v1.42 `soak-capture.sh` script which projects only the v1.42 fields. Verified by reading row 1:
- ✓ `suppressions_per_min` present
- ✗ `load_rtt_ms` **NOT projected**
- ✗ `baseline_rtt_ms` **NOT projected**
- ✗ `load_rtt_delta_us` **NOT computable** from the row alone
- ✗ `suppressions_completed_window_by_cause` **NOT exposed by v1.42.1 binary** (Phase 202 was post-v1.42.1)
- ✗ `last_zone` **NOT projected** (only `zone_trace_tail`)

Three of the five required fields are simply absent. The v1.42 NDJSON cannot drive an end-to-end Phase 203 aggregator test.

### Recommended approach: dual-fixture strategy

1. **Capture-projection contract test (no soak fixture needed).** Synthesize a single `/health` JSON payload with all five required fields populated to known values; run the new `scripts/soak-capture.sh` jq projection against it via `jq -c`; assert the output row contains the seven new keys with the expected values. This validates OBSV-05 (capture script emits the field correctly) without needing a golden fixture at all. ~20 lines of test, fast, deterministic.

2. **Aggregator math test against a small in-tree synthetic NDJSON.** Author a hand-crafted ~50-200 row NDJSON fixture under `tests/fixtures/phase_203_synthetic_capture.ndjson` that exercises:
   - Multiple zones (GREEN/YELLOW/SOFT_RED/RED rows)
   - Multiple cause-tag events (deltas in `ul_suppressions_lifetime_by_cause`)
   - Boundary-crossing `load_rtt_delta_us` values that fall on each bucket boundary
   - First-row exclusion for cause attribution (no previous sample)
   - Sustained-zone runs (multi-row same zone, same cause)
   - Hand-computed expected aggregator output (golden JSON checked into `tests/fixtures/phase_203_synthetic_summary.json`)

   Aggregator test reads the synthetic NDJSON, runs the aggregator, asserts the produced soak-summary.json matches the golden output byte-identically (or with explicit per-field tolerances for floats — recommend integer-only fields where possible to make this exact).

3. **(Optional) v1.42 NDJSON regression test for the un-affected fields.** Re-run the new aggregator against the v1.42 NDJSON; assert that `diagnostic_distribution.{rtt_integral_ms_s, max_delay_delta_us, red_streak, headroom_exhausted_samples, total_samples}` match the v1.42 `soak-summary.json` values (within float tolerance). This proves the aggregator promotion didn't break the existing math. The new `load_rtt_delta_us` and `..._by_zone_cause` fields are absent from v1.42 NDJSON → aggregator skips them gracefully. Document the absence as expected behavior.

The phrase "golden-fixture replay" in OBSV-07 is **satisfied by tests 1+2 together**: test 1 is the capture-projection golden check, test 2 is the aggregator-math golden replay against a deterministic NDJSON fixture. The Phase 202 precedent of "replay against v1.42 NDJSON" cannot be mirrored here because the v1.42 fixture predates the new fields. This is a real and unavoidable consequence of Phase 203 adding *capture-side* fields, not just *binary-side* fields.

**The planner must lock this dual-fixture strategy** as the OBSV-07 implementation. It is the most-faithful interpretation of "golden-fixture replay" given the source-data constraints.

---

## SAFE-07 verification mechanism

Phase 202 used SAFE-05 token-pin updates because it added new symbols to `src/wanctl/`. **Phase 203 adds zero `src/wanctl/` lines** — all changes are in `scripts/`, `tests/`, `docs/`, and `CHANGELOG.md`. No new SAFE-05 pin block.

The SAFE-07 cross-cutting invariant ("no control-path source diff between Phase 201 close and v1.43 close") is verified for Phase 203 by **two complementary checks at phase close**:

1. **Mechanical source diff:**
   ```bash
   git diff <phase-202-close-tag>..HEAD -- src/wanctl/
   ```
   Expected: empty. Any line of output is a SAFE-07 violation and must be reverted before phase close.

2. **Existing pin tests pass unchanged:**
   ```bash
   .venv/bin/pytest tests/test_phase_195_replay.py -v -k "safe05_threshold_name_counts"
   ```
   The three dicts (`expected_counts`, `phase201_expected_counts`, `phase202_expected_counts`) all assert their counts against current source. Since Phase 203 doesn't touch source, all three should pass with zero modification. **No fourth `phase203_expected_counts` dict is added** — that would be the wrong precedent (it would create the false impression that Phase 203 added new symbols requiring pinning).

3. **Reference tag for the source diff:** the phase-202-close commit hash should be recorded in `203-VERIFICATION.md` so the diff command is reproducible. Recommend the most recent commit on `main` at the time Phase 203 starts as the reference; the planner sets this in plan 203-03 (or the closeout plan).

This is the right mechanism. The Phase 202 RESEARCH §`SAFE-05 / SAFE-07 pin handling` already used the same two-check pattern; Phase 203 just omits the "new pins" step because it has nothing to pin.

---

## Documentation surface

OBSV-08 / success-criterion-4 names two doc artifacts:
- "Soak harness README" — does NOT exist today
- "`CHANGELOG.md`" — exists, has v1.43-dev entry from Phase 202

### Soak harness README — `scripts/soak-harness/README.md` (proposed path)

There is no canonical soak harness README in the repo. The existing references are scattered:
- `scripts/soak-monitor.sh` — live operator dashboard, NOT the soak capture chain
- `docs/RUNBOOK.md:259-353` — references `soak-monitor.sh` for live monitoring, doesn't document the capture-and-aggregate flow
- The actual capture script lives in soak-evidence directories (`.planning/milestones/.../soak/.../soak-capture.sh`), not under `scripts/`

**Recommendation:** Phase 203 creates `scripts/soak-harness/README.md` (or `docs/SOAK_HARNESS.md`; planner picks). Contents:

1. **Purpose.** What the soak harness does (24h capture, aggregate, verdict).
2. **Files.**
   - `scripts/soak-capture.sh` — uploaded to deploy target, runs as tmux session, writes NDJSON (created in Phase 203).
   - `scripts/soak_summary_aggregate.py` — reads NDJSON, writes `soak-summary.json` (created in Phase 203).
   - `scripts/soak-monitor.sh` — live operator dashboard (existing; cross-reference only, not Phase 203 territory).
3. **NDJSON schema.** Full per-row field list, including the v1.43 additions (`load_rtt_ms`, `baseline_rtt_ms`, `load_rtt_delta_us`, `last_zone`, `ul_suppressions_completed_window_count`, `ul_suppressions_completed_window_by_cause`, `ul_suppressions_lifetime_by_cause`).
4. **soak-summary.json schema.** Full output shape including the new `load_rtt_delta_us` block in `diagnostic_distribution` and the `load_rtt_delta_us_by_zone_cause` matrix.
5. **Histogram bucket interpretation.** Document the default bucket scheme + how to override.
6. **Cause-tag attribution rule.** Explicitly state: per-sample cause = lifetime counter delta from previous sample; first sample skipped.
7. **Zone axis = upload only.** Document the v1.43 limitation.
8. **No-control-path-change invariant.** Document SAFE-07's harness-only consequences: this README + this code path NEVER trigger production binary changes; production canary not required for soak-harness updates.

**Path choice:** `scripts/soak-harness/README.md` co-locates with the harness scripts and follows the project's `scripts/monitoring/` pattern. Alternatively `docs/SOAK_HARNESS.md` follows the `docs/STEERING.md`, `docs/RUNBOOK.md` precedent. **Recommendation: `docs/SOAK_HARNESS.md`** — keeps script directory uncluttered and aligns with operator-doc discoverability (operators look in `docs/`).

### CHANGELOG.md — `v1.43-dev` extension

The existing v1.43-dev entry from Phase 202 documents the additive `/health` fields. Phase 203 extends this entry (does not create a new version block) with:

- **Added — soak-harness:** `scripts/soak-capture.sh` and `scripts/soak_summary_aggregate.py` promoted from inline-jq evidence into versioned, tested scripts.
- **Added — NDJSON schema:** seven new per-row fields documented (list).
- **Added — `soak-summary.json` schema:** new `diagnostic_distribution.load_rtt_delta_us` block + new top-level `load_rtt_delta_us_by_zone_cause` matrix.
- **Added — docs:** `docs/SOAK_HARNESS.md`.
- **Notes — invariant:** Phase 203 added zero lines to `src/wanctl/` — additive observability only.
- **Notes — limitation:** `load_rtt_delta_us` uses raw `load_rtt_ms` not asymmetry-gate-attenuated. Spectrum (current v1.43 baseline link) doesn't enable the gate, so the values are exact. Gate-enabled deployments would see over-stated deltas during gate-active windows; future seed if needed.

---

## Recommended plan slicing

Three plans. Phase 202 used four because it had a SAFE-05 pin extension as a discrete deliverable; Phase 203 has no source pins, so the pin work folds into the closeout.

### Plan 203-01 — Capture script (`scripts/soak-capture.sh`)

**Scope:** Promote the v1.42 inline-evidence script to a versioned `scripts/soak-capture.sh`; add the seven new per-row keys.

- Create `scripts/soak-capture.sh` as the canonical, executable harness.
- Verify it produces a valid NDJSON row when curled at a Phase-202-vintage `/health` endpoint (or a synthesized JSON blob in test).
- Test: `tests/test_phase_203_capture_projection.py` synthesizes a `/health` payload, runs the script's jq projection (via `subprocess.run(["jq", "-c", PROJECTION_QUERY], input=health_json)`), asserts each new key + old key exists with expected value. Capture-projection contract test per OBSV-07 strategy.
- Documentation stub in `docs/SOAK_HARNESS.md` listing the new keys (full doc lives in plan 203-03).

**Size:** ~40 LOC for the script (mostly the verbatim v1.42 projection + 7 new fields), ~80 LOC for the test, ~30 LOC of docs stub. **Single PR.**

**Dependencies:** None inside this phase. Depends on Phase 202 close (which is done).

### Plan 203-02 — Aggregator (`scripts/soak_summary_aggregate.py`) + golden-fixture replay

**Scope:** New aggregator script + the in-tree synthetic NDJSON fixture + the math-replay test.

- Create `scripts/soak_summary_aggregate.py` with:
  - `aggregate_completed_windows(snapshots)` — lifted from `tests/test_phase_202_replay.py` (refactor: existing test imports from new module, not duplicates).
  - `_percentile(values, p)` — same lift.
  - `histogram(values, buckets)` — new.
  - `aggregate_load_rtt_delta(rows)` — new.
  - `aggregate_by_zone_cause(rows)` — new.
  - CLI entry `if __name__ == "__main__":` accepting NDJSON path → writes `soak-summary.json`.
- Create `tests/fixtures/phase_203_synthetic_capture.ndjson` (~50-200 hand-authored rows exercising all matrix cells, bucket boundaries, and edge cases).
- Create `tests/fixtures/phase_203_synthetic_summary.json` (golden expected aggregator output).
- Create `tests/test_phase_203_replay.py` with:
  - `TestAggregatorMath` — runs aggregator against synthetic NDJSON, asserts byte-equality against golden JSON.
  - `TestV142NdjsonRegression` — runs aggregator against the v1.42 NDJSON, asserts old `diagnostic_distribution` fields match v1.42's `soak-summary.json` values within tolerance, asserts new `load_rtt_delta_us`-derived fields are emitted as empty/zero (not a crash).
  - `TestZoneAxisUploadOnly` — verifies the aggregator only reads `last_zone` from the upload axis.
  - `TestCauseAttribution` — verifies first row is skipped from `_by_zone_cause` matrix; per-row cause derived from lifetime counter delta.
- Refactor: update `tests/test_phase_202_replay.py` imports to pull `aggregate_completed_windows` and `_percentile` from the new aggregator module (rather than duplicate). Verify `test_phase_202_replay.py` still passes.

**Size:** ~250-350 LOC for the aggregator, ~150 LOC for tests, ~100 LOC for the synthetic NDJSON fixture (machine-generated from a small Python snippet checked into the test, recommended over hand-authoring). **Single PR.**

**Dependencies:** Plan 203-01 lands first (the capture script defines the row schema the aggregator reads).

### Plan 203-03 — Docs, CHANGELOG, SAFE-07 verification

**Scope:** OBSV-08 + SAFE-07 closure + phase-close artifacts.

- Write `docs/SOAK_HARNESS.md` (full content per §`Documentation surface`).
- Extend `CHANGELOG.md` v1.43-dev entry with Phase 203 additions.
- Update `docs/CONFIGURATION.md` (if needed) — likely just a cross-reference to `docs/SOAK_HARNESS.md` from the existing v1.43 suppression-metric semantics section, since the new capture fields tie into that contract.
- SAFE-07 verification:
  - Mechanical `git diff <phase-202-close-tag>..HEAD -- src/wanctl/` returns empty (recorded in `203-VERIFICATION.md`).
  - `tests/test_phase_195_replay.py::test_safe05_threshold_name_counts_are_unchanged` passes unchanged.
  - Hot-path slice green: `.venv/bin/pytest -o addopts='' tests/test_cake_signal.py tests/test_queue_controller.py tests/test_wan_controller.py tests/test_health_check.py -q`.
- Phase-close artifacts:
  - `203-VERIFICATION.md` (truths-and-evidence per Phase 202 precedent)
  - `203-VALIDATION.md` (Nyquist-style validation tracker per Phase 202 precedent)
  - `203-RETRO.md` (durable lessons; recommend mentioning the dual-fixture replay strategy for future seed/phase observability work that adds capture-side fields predating the existing reference soak)
  - REQUIREMENTS.md OBSV-05..08 + SAFE-07 row updates
  - ROADMAP.md Progress table update (Phase 203 4/4 → Complete)
  - STATE.md phase-203 close entry

**Size:** ~250-400 lines of markdown, ~30 lines of CHANGELOG, plus closeout artifacts. **Single PR.**

**Dependencies:** Plans 203-01 and 203-02 land first.

### Plan ordering

```
203-01 (capture script + projection test)
   ↓
203-02 (aggregator + replay tests)
   ↓
203-03 (docs + SAFE-07 verification + closeout)
```

Strictly serial. The aggregator reads the capture-script schema; the docs document both. There is no parallelization gain from splitting 203-01 and 203-02 since 203-02's test fixture authoring depends on 203-01's locked NDJSON schema.

### Why three plans, not four

Phase 202 had four plans because it had a discrete SAFE-05 pin-extension deliverable (Plan 202-03). Phase 203 has no source pins. Folding the SAFE-07 mechanical verification into the closeout/docs plan is right-sized and matches the work actually done.

ROADMAP estimates "3-4 plans". Three is the cleaner answer.

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.0.2 |
| Config file | `pyproject.toml [tool.pytest.ini_options]` |
| Quick run command | `.venv/bin/pytest -o addopts='' tests/test_cake_signal.py tests/test_queue_controller.py tests/test_wan_controller.py tests/test_health_check.py -q` |
| Phase-scoped slice | `.venv/bin/pytest tests/test_phase_203_capture_projection.py tests/test_phase_203_replay.py tests/test_phase_202_replay.py tests/test_phase_195_replay.py -q` |
| Full suite command | `.venv/bin/pytest tests/ -q` |
| Estimated runtime | quick ~43s · full ~189s · phase-scoped slice ~3s |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| OBSV-05 | Capture script emits `load_rtt_delta_us` + 6 supporting fields per NDJSON row | unit / contract | `.venv/bin/pytest tests/test_phase_203_capture_projection.py -v -k "load_rtt_delta_us or new_fields"` | ❌ Wave 0 (plan 203-01) |
| OBSV-06 | `soak-summary.json` aggregator emits `load_rtt_delta_us` p50/p95/p99/max + histogram + zone × cause-tag matrix | unit + replay | `.venv/bin/pytest tests/test_phase_203_replay.py -v -k "aggregator_math or by_zone_cause or histogram"` | ❌ Wave 0 (plan 203-02) |
| OBSV-07 | Golden-fixture replay (dual-fixture: capture-projection contract + aggregator-math against synthetic NDJSON) | replay | `.venv/bin/pytest tests/test_phase_203_replay.py -v` and `.venv/bin/pytest tests/test_phase_203_capture_projection.py -v` | ❌ Wave 0 (plans 203-01, 203-02) |
| OBSV-08 | Docs (`docs/SOAK_HARNESS.md`, CHANGELOG v1.43-dev extension) name the new field, the matrix contract, and the no-control-path-change invariant | manual-only | `grep -E "load_rtt_delta_us\|load_rtt_delta_us_by_zone_cause\|harness-only" docs/SOAK_HARNESS.md CHANGELOG.md` returns ≥1 hit per file per pattern | ❌ Wave 0 (plan 203-03) |
| SAFE-07 | No control-path source diff between Phase 201 close and Phase 203 close. v1.40/v1.41/v1.42/v1.42-Phase-202 pin block in `tests/test_phase_195_replay.py` unchanged. | regression + diff | `.venv/bin/pytest tests/test_phase_195_replay.py -v -k "safe05_threshold_name_counts"` AND `git diff <phase-202-close>..HEAD -- src/wanctl/` returns no output | ✅ pin test exists; diff command is manual at closeout |

### Sampling Rate

- **Per task commit:** quick hot-path slice + the plan's own test file (e.g. plan 203-01 commits run `.venv/bin/pytest tests/test_phase_203_capture_projection.py -v` plus the hot-path slice)
- **Per wave merge:** phase-scoped slice
- **Phase gate (`/gsd-verify-work`):** full suite green; `git diff <phase-202-close>..HEAD -- src/wanctl/` empty; SAFE-05 pin test green

### Wave 0 Gaps

- [ ] `tests/test_phase_203_capture_projection.py` — covers OBSV-05; created in plan 203-01.
- [ ] `tests/test_phase_203_replay.py` — covers OBSV-06 + OBSV-07 (aggregator side); created in plan 203-02.
- [ ] `tests/fixtures/phase_203_synthetic_capture.ndjson` — synthetic NDJSON fixture; created in plan 203-02.
- [ ] `tests/fixtures/phase_203_synthetic_summary.json` — golden expected aggregator output; created in plan 203-02.
- [ ] `scripts/soak-capture.sh` — promoted versioned harness; created in plan 203-01.
- [ ] `scripts/soak_summary_aggregate.py` — new aggregator; created in plan 203-02.
- [ ] `docs/SOAK_HARNESS.md` — new operator-facing soak harness doc; created in plan 203-03.

No framework install needed — pytest, jq, and python3 stdlib are already standard project tooling. ShellCheck is not currently enforced by CI; if the planner chooses to add `shellcheck scripts/soak-capture.sh` to plan 203-01's tests, that is a small addition with no infra change.

### Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| `docs/SOAK_HARNESS.md` and CHANGELOG document the v1.43 capture additions, the zone × cause-tag matrix contract, and the harness-only invariant. | OBSV-08 | Doc-presence grep tests churn on every legitimate edit. Verified once at close via `grep -E "load_rtt_delta_us\|load_rtt_delta_us_by_zone_cause\|harness-only" docs/SOAK_HARNESS.md CHANGELOG.md` returning hits. | `grep -E "load_rtt_delta_us" docs/SOAK_HARNESS.md CHANGELOG.md` returns ≥1 hit per file. Re-run if either file is materially restructured. |
| Phase 203 introduced no controller tuning; `src/wanctl/` byte-identical vs Phase 202 close. | SAFE-07 (cross-cutting) | "No source diff across an entire phase" is git-diff semantics, not unit-test logic. The existing `test_safe05_threshold_name_counts_are_unchanged` test partially automates this: silent token-rename trips the suite. | `git diff <phase-202-close>..HEAD -- src/wanctl/` must be empty. Re-run before Phase 203 closeout. |

### Validation Sign-Off Targets

- [ ] OBSV-05, OBSV-06, OBSV-07 fully automated via `tests/test_phase_203_capture_projection.py` + `tests/test_phase_203_replay.py`
- [ ] OBSV-08 manual-only (docs grep) by design — doc-presence tests are low-signal
- [ ] SAFE-07 partially automated via existing pin test; fully verified by manual `git diff` at closeout
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify (achievable: each plan has a primary automated test)
- [ ] Wave 0 covers all MISSING references (see list above)
- [ ] Feedback latency < 60s on phase-scoped slice (~3s actual)

Phase 203 should target `nyquist_compliant: true` modulo the same OBSV-08 / SAFE-07 manual-only carve-outs Phase 202 took.

---

## Risks

### Risk 1: v1.42 NDJSON cannot drive end-to-end golden replay (HIGH; addressed by dual-fixture strategy)

The natural impulse is "replay against v1.42 soak NDJSON like Phase 202 did." Won't work — three of five required fields are absent. **Mitigation:** dual-fixture strategy in §`Golden-fixture replay strategy`. Plan 203-02 must explicitly author the synthetic NDJSON; this is non-trivial fixture work and should not be glossed over in the plan. **The planner must call out the synthetic-fixture authoring as a discrete Plan 203-02 task** with a worked example.

### Risk 2: Asymmetry-gate attenuation makes per-link delta non-portable (MEDIUM)

`load_rtt_delta_us` computed in the harness uses raw `load_rtt_ms`, not gate-attenuated. On Spectrum (gate disabled) this is exact. On any future deployment with the gate enabled, gate-active windows would over-state the delta. **Mitigation:** documented limitation in `docs/SOAK_HARNESS.md`; v1.43 milestone goal is Spectrum-only recalibration so the limitation has zero impact on v1.43 success criteria. If a future seed needs portable deltas, that seed adds an `effective_ul_load_rtt_ms` field to `/health` (binary change) and the harness preference flips to it.

### Risk 3: Inline-jq → Python aggregator promotion drops a behavior (LOW-MEDIUM)

The Phase 201-16 inline-jq pipeline computes `secondary_gate.computation` (60s sliding-window mean) using a particular `$rows`-binding pattern. The Python aggregator must produce the same number for the v1.42 reference NDJSON to maintain backward-compatibility on the un-affected fields. **Mitigation:** the v1.42-NDJSON regression test in plan 203-02 specifically asserts that running the new aggregator against the v1.42 NDJSON produces matching `diagnostic_distribution.{rtt_integral_ms_s, max_delay_delta_us, red_streak, headroom_exhausted_samples, total_samples}` values within float tolerance. If the secondary_gate computation is also being promoted, assert that too. **Action item for planner:** decide explicitly whether plan 203-02 promotes ONLY the diagnostic-distribution math OR also the secondary-gate (`ul_hysteresis_suppression_rate_per_60s_mean`) computation. Recommendation: scope tightly — diagnostic-distribution only in plan 203-02; the secondary-gate computation is Phase 204 territory (CALIB-03 explicitly schedules the watchdog computation update).

### Risk 4: `load_rtt_ms` and `baseline_rtt_ms` are 2-decimal-rounded floats; integer-µs computation may drift (LOW)

`health_check.py:248-249` rounds to 2 decimal places (10µs precision). A `load_rtt_delta_us` of "120 microseconds" is already at the rounding edge. **Mitigation:** acceptable. The metric is for histogram-bucket aggregation at ms-scale boundaries (1ms, 3ms, target_delta=15ms), so 10µs precision is far better than needed. Document the precision in `docs/SOAK_HARNESS.md`.

### Risk 5: Aggregator dev-environment vs production-target dependency mismatch (LOW)

Phase 203 promotes the harness to `scripts/`. The aggregator runs on whatever machine produces `soak-summary.json` — could be on cake-shaper (live deploy target) post-soak, or on dev-VM after rsync of the NDJSON. Python 3.11+ stdlib only, no NumPy/pandas → runs anywhere with Python 3.11 (which is the project standard per CLAUDE.md). **Mitigation:** none needed; document the runtime requirement in the README.

### Risk 6: Cause-attribution edge cases (multi-cause-incremented-in-same-cycle) (LOW-MEDIUM)

If a single 50ms cycle increments BOTH `dwell_hold` AND `backlog_recovery` lifetime counters (both call `_record_suppression` in the same cycle), the per-sample cause attribution sees two delta increments. The aggregator needs an explicit policy. **Mitigation:** planner must lock this in plan 203-02. Recommendation: row contributes to BOTH `(zone, dwell_hold)` and `(zone, backlog_recovery)` cells, weighted by 1.0 each (NOT split). Sum-of-counts across the matrix can therefore exceed `total_samples` — document this. Alternative: pick a precedence (dwell_hold > backlog_recovery > other) and attribute to one. Less informative but counts add up cleanly. **Recommendation: dual-attribution.** Operator-readable, no information loss; aggregator output documents the count semantics.

### Risk 7: Phase 204 will need to extend the aggregator further (LOW)

CALIB-01 + CALIB-03 will read the aggregator's output and add a watchdog computation for the recalibrated D-14 successor threshold. The aggregator must be designed for extension (modular per-aggregation functions, CLI flags for output sub-sections). **Mitigation:** structure the aggregator per the proposal in §`Aggregator promotion` — separate functions per aggregation, CLI orchestrates. Phase 204 adds a new function + CLI flag, doesn't refactor.

---

## Code examples

### Capture-projection contract test (plan 203-01)

```python
# tests/test_phase_203_capture_projection.py
import json
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
CAPTURE_SCRIPT = REPO_ROOT / "scripts" / "soak-capture.sh"

# Extract the jq projection from the script (or hard-code a known-good copy
# in this test and assert the script contains it verbatim — both work).

SYNTHETIC_HEALTH = {
    "version": "1.43-dev",
    "status": "healthy",
    "wans": [{
        "name": "spectrum",
        "load_rtt_ms": 18.42,
        "baseline_rtt_ms": 12.0,
        "upload": {
            "floor_hit_cycles_total": 0,
            "max_delay_delta_us": 56,
            "red_streak": 0,
            "rtt_integral_ms_s": 2.293,
            "docsis_mode_active": True,
            "red_decay_step_pct": 0.02,
            "red_decay_delta_max_pct": 0.10,
            "headroom_state": "AVAILABLE",
            "headroom_exhausted_streak": 0,
            "anti_windup_triggers": 0,
            "zone_trace": ["GREEN", "GREEN", "GREEN", "GREEN", "GREEN"],
            "hysteresis": {
                "suppressions_per_min": 17,
                "last_zone": "GREEN",
                "suppressions_completed_window_count": 13,
                "suppressions_completed_window_by_cause": {
                    "dwell_hold": 13, "backlog_recovery": 0, "other": 0
                },
                "suppressions_lifetime_by_cause": {
                    "dwell_hold": 13, "backlog_recovery": 0, "other": 0
                },
            }
        }
    }]
}

def test_capture_projection_emits_load_rtt_delta_us():
    """OBSV-05: capture script projects load_rtt_delta_us = (18.42 - 12.0) * 1000 = 6420."""
    proc = subprocess.run(
        ["jq", "-c",
         # Pull the actual projection out of the capture script in a real test.
         # For this example, hard-code a known projection.
         '{load_rtt_delta_us: ((.wans[0].load_rtt_ms - .wans[0].baseline_rtt_ms) * 1000 | floor)}'
        ],
        input=json.dumps(SYNTHETIC_HEALTH),
        capture_output=True, text=True, check=True,
    )
    row = json.loads(proc.stdout)
    assert row["load_rtt_delta_us"] == 6420
```

### Aggregator skeleton (plan 203-02)

```python
# scripts/soak_summary_aggregate.py
"""Phase 203 OBSV-06 soak summary aggregator.

Reads soak-capture.ndjson and emits soak-summary.json with diagnostic_distribution
and the load_rtt_delta_us_by_zone_cause matrix. Promoted from inline-jq evidence
in v1.42 Plan 201-16 closeout.

Exposes helpers for Phase 204 (CALIB) to compute the recalibrated D-14 successor
threshold against an arbitrary 24h soak NDJSON.
"""
from __future__ import annotations
import json
import math
from pathlib import Path
from typing import Iterable

DEFAULT_BUCKETS_US = [
    0, 1000, 3000, 6000, 10000, 15000, 20000, 30000, 45000, 60000, 100000, 250000,
]
ZONES = ("GREEN", "YELLOW", "SOFT_RED", "RED")
CAUSES = ("dwell_hold", "backlog_recovery", "other")


def aggregate_completed_windows(snapshots: list[int]) -> list[int]:
    """Lifted from tests/test_phase_202_replay.py for reuse in Phase 204."""
    if len(snapshots) < 2:
        return []
    out: list[int] = []
    for i in range(1, len(snapshots)):
        if snapshots[i] < snapshots[i - 1]:
            out.append(int(snapshots[i - 1]))
    return out


def percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    rank = (len(ordered) - 1) * (p / 100.0)
    lower = math.floor(rank)
    upper = math.ceil(rank)
    if lower == upper:
        return float(ordered[lower])
    fraction = rank - lower
    return float(ordered[lower] + (ordered[upper] - ordered[lower]) * fraction)


def histogram(values: Iterable[int], buckets: list[int]) -> list[int]:
    counts = [0] * (len(buckets) + 1)  # +1 for overflow
    sorted_buckets = sorted(buckets)
    for v in values:
        # Find first bucket boundary > v; bucket index is one less.
        idx = len(sorted_buckets)
        for i, b in enumerate(sorted_buckets):
            if v < b:
                idx = i
                break
        counts[idx] += 1
    return counts


def aggregate_load_rtt_delta(rows: list[dict]) -> dict:
    deltas = [r["load_rtt_delta_us"] for r in rows if "load_rtt_delta_us" in r]
    if not deltas:
        return {}
    return {
        "p50": percentile(deltas, 50),
        "p95": percentile(deltas, 95),
        "p99": percentile(deltas, 99),
        "max": max(deltas),
        "histogram": {
            "buckets_us": DEFAULT_BUCKETS_US,
            "counts": histogram(deltas, DEFAULT_BUCKETS_US),
        },
    }


def aggregate_by_zone_cause(rows: list[dict]) -> dict:
    """Cause attribution: lifetime counter delta from previous sample.
    First row excluded (no previous sample). Multi-cause cycles dual-attributed.
    """
    matrix: dict[str, dict[str, list[int]]] = {z: {c: [] for c in CAUSES} for z in ZONES}
    prev = None
    for row in rows:
        if prev is not None and "ul_suppressions_lifetime_by_cause" in row:
            for cause in CAUSES:
                cur = row["ul_suppressions_lifetime_by_cause"].get(cause, 0)
                pre = prev.get("ul_suppressions_lifetime_by_cause", {}).get(cause, 0)
                if cur > pre:
                    zone = row.get("last_zone", "GREEN")
                    if zone in matrix:
                        matrix[zone][cause].append(row["load_rtt_delta_us"])
        prev = row
    return {
        z: {c: {
            "p50": percentile(matrix[z][c], 50),
            "p95": percentile(matrix[z][c], 95),
            "p99": percentile(matrix[z][c], 99),
            "max": max(matrix[z][c], default=0),
            "count": len(matrix[z][c]),
            "histogram": {
                "buckets_us": DEFAULT_BUCKETS_US,
                "counts": histogram(matrix[z][c], DEFAULT_BUCKETS_US),
            },
        } for c in CAUSES} for z in ZONES
    }
```

---

## Project Constraints (from CLAUDE.md)

- **Production-critical, change-conservatively.** Phase 203 is harness-additive only; no `src/wanctl/` change. SAFE-07 invariant aligns with project-level "stability > safety > clarity > elegance".
- **Black 100 char, Ruff, MyPy, Pytest.** New code (`scripts/soak_summary_aggregate.py`) must pass `make ci`. Note: `scripts/*.py` is currently included in MyPy's targets (verify in plan 203-02; if not, the aggregator may need to be added to the MyPy include list — small ask).
- **Project-finalizer mandatory before commit.** Each of the three plans terminates in a project-finalizer pass.
- **Public-safe docs.** No IPs, hostnames, or operator identities in `docs/SOAK_HARNESS.md` or CHANGELOG. The `HEALTH_URL="http://10.10.110.223:9101/health"` literal in the v1.42 reference `soak-capture.sh` is a private IP — when promoting to `scripts/soak-capture.sh`, parameterize via env var or YAML lookup so the script itself contains no IP. Operator runs `HEALTH_URL=http://<host>:9101/health bash scripts/soak-capture.sh <SOAK_TS>`.
- **`.venv/bin/pytest`** for direct test invocation.
- **RAG-first knowledge discovery** — verified by reading `.planning/intel/files.json` is not relevant here (research is about new code surfaces, not existing-codebase orientation); but note that `query_rag(..., project="wanctl")` would have surfaced the `health_check.py` and `soak-capture.sh` files faster than direct grep.

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Asymmetry gate is disabled on Spectrum so `effective_ul_load_rtt == load_rtt`. | Field availability audit | If gate is silently enabled in `configs/spectrum.yaml` post-research, harness-computed delta would be wrong on Spectrum. **Mitigation:** verified `configs/spectrum.yaml` contains no `asymmetry_gate:` section and the default is `enabled=False` (`autorate_config.py:1184`). HIGH confidence. |
| A2 | `load_rtt_ms` and `baseline_rtt_ms` 2-decimal rounding (10µs precision) is acceptable for the histogram-at-ms-boundary aggregation use case. | Risk 4 | Histogram buckets are at 1ms, 3ms, 15ms, etc. — 10µs precision is irrelevant at those scales. Phase 204's threshold derivation reads aggregate stats, not individual sample exactness. HIGH confidence. |
| A3 | Cause-tag attribution per sample = lifetime-counter delta from previous sample, with dual-attribution on multi-cause cycles. | Aggregator promotion + Risk 6 | If operators expect per-cause counts to sum to total-samples, the sum-may-exceed semantic surprises them. **Mitigation:** explicit doc note in `docs/SOAK_HARNESS.md`. Alternative: precedence-based single-attribution. **Planner must lock this.** MEDIUM confidence — both choices are defensible. |
| A4 | `scripts/soak-capture.sh` and `scripts/soak_summary_aggregate.py` is the right canonical location for the harness; promoting from inline-PLAN-evidence to `scripts/` is the right move. | Aggregator promotion + Recommended plan slicing | If the planner prefers to keep the harness inline-in-PLAN per Phase 201's pattern, plan 203-01 reduces to "extend the v1.42 inline jq projection in the next soak-evidence directory" — still works but Phase 204 has to re-author the aggregator from scratch. HIGH confidence promotion is the right move; MEDIUM confidence on the exact filename. |
| A5 | Default histogram bucket boundaries `[0, 1000, 3000, 6000, 10000, 15000, 20000, 30000, 45000, 60000, 100000, 250000]` µs aligned with Spectrum v1.42 `target_bloat_ms=15`, `warn_bloat_ms=30` are the right operator-relevant defaults. | Histogram bucket scheme | If the planner picks Option B (fixed-width) or Option C (log-spaced) instead, the JSON shape and operator interpretation changes. **Planner must lock this.** MEDIUM confidence — Option A is recommended on operator-readability grounds. |
| A6 | The v1.42 reference `soak-summary.json` `diagnostic_distribution` field-set is the right baseline for the aggregator's preserved-output contract. The new aggregator emits the same fields (within float tolerance) for the v1.42 NDJSON. | Risk 3 + Plan 203-02 | If the v1.42 diagnostic-distribution math has a bug that the inline jq pipeline produced, the new Python aggregator would either reproduce it (preserve compat) or fix it (break compat). HIGH confidence — the v1.42 numbers were operator-verified at Phase 201-17 closeout; preserve them. |
| A7 | Phase 204 (CALIB) will reuse `scripts/soak_summary_aggregate.py` as the canonical aggregator. Aggregator design must be extensible. | Risk 7 + Aggregator promotion | If Phase 204 instead invents its own aggregator, the Phase 203 deliverable becomes single-use. HIGH confidence Phase 204 will reuse — REQUIREMENTS.md CALIB-03 explicitly says "soak harness updated". |
| A8 | Promoting `aggregate_completed_windows` and `_percentile` from `tests/test_phase_202_replay.py` to `scripts/soak_summary_aggregate.py` (test imports the module) is a non-behavioral refactor that does not violate SAFE-07 or break Phase 202's tests. | Plan 203-02 | If the test imports break, plan 203-02 fails CI. **Mitigation:** the refactor is a pure code-move + import update; existing test logic byte-identical. LOW risk. |

---

## Open Questions

1. **Synthetic NDJSON fixture authoring strategy.** Hand-author 50-200 rows of NDJSON, OR generate via a checked-in Python snippet that emits the fixture deterministically?
   - What we know: hand-authoring is brittle and error-prone for ~150 rows with `(zone, cause)` correctness. A Python generator at `tests/fixtures/_phase_203_generator.py` that emits the fixture deterministically is more maintainable.
   - What's unclear: whether the planner wants the generator script versioned (auditable) or only the resulting NDJSON versioned (operator-readable diff).
   - **Recommendation:** version both. Generator script + checked-in fixture. Re-running the generator must produce byte-identical NDJSON (deterministic seed). Test asserts the fixture matches the generator output; drift detection.

2. **Cause-attribution policy for multi-cause cycles.** Dual-attribution (recommended) or precedence-based single-attribution?
   - What we know: dual-attribution preserves all information but breaks "counts sum to total_samples". Single-attribution loses information but counts sum cleanly.
   - What's unclear: which fits the Phase 204 / SEED-005 downstream use cases better.
   - **Recommendation:** dual-attribution. Document the sum-may-exceed semantic. Phase 204's threshold derivation cares about per-cell percentiles, not sum-of-counts identity.

3. **Histogram bucket boundaries: defaulted from YAML config or hardcoded constants?**
   - What we know: hardcoded with CLI override is simpler; reading from YAML adds aggregator dependency on config-loading.
   - What's unclear: whether the planner wants the aggregator to be link-aware out of the box.
   - **Recommendation:** hardcoded Spectrum-aligned defaults; CLI flags `--target-delta-us`, `--warn-delta-us`, `--hard-red-us` to override. The aggregator emits the boundary array into the JSON output so consumers don't need the config to interpret.

4. **`scripts/soak-capture.sh` parameterization.** The v1.42 inline script hardcodes `HEALTH_URL`, `SOAK_DURATION_SEC`, `CAPTURE_DIR`. The promoted versioned script should parameterize all three.
   - What we know: `HEALTH_URL` MUST be parameterized (CLAUDE.md public-safe rule prevents IPs in repo files). `SOAK_DURATION_SEC` should default to 86400 (24h) but allow override for testing. `CAPTURE_DIR` defaults to `/var/tmp/wanctl-soak-${SOAK_TS}`.
   - What's unclear: env vars vs positional args vs `getopts`.
   - **Recommendation:** positional `SOAK_TS` (as v1.42), env-var-driven `HEALTH_URL` (required), env-var-driven `SOAK_DURATION_SEC` (default 86400), env-var-driven `CAPTURE_DIR` (default `/var/tmp/wanctl-soak-${SOAK_TS}`). Matches the project's existing `phase192-soak-capture.env.example` pattern.

5. **Doc location: `scripts/soak-harness/README.md` vs `docs/SOAK_HARNESS.md`.**
   - What we know: project convention has operator-facing docs in `docs/` (`STEERING.md`, `RUNBOOK.md`, `PERFORMANCE.md`).
   - What's unclear: whether the planner prefers script-co-located README for discoverability from the script directory.
   - **Recommendation:** `docs/SOAK_HARNESS.md`. Cross-referenced from `scripts/soak-capture.sh` header comment (`# See docs/SOAK_HARNESS.md for full schema and usage`) and from `docs/RUNBOOK.md` soak section.

---

## Sources

### Primary (HIGH confidence)
- `src/wanctl/health_check.py` lines 230-380 — `/health` payload structure; verified `load_rtt_ms`, `baseline_rtt_ms`, `last_zone`, and Phase 202 cause-tag fields all exposed.
- `src/wanctl/wan_controller.py` lines 2716-2774 — `_compute_effective_ul_load_rtt`; verified gate-disabled passthrough.
- `src/wanctl/queue_controller.py` lines 87-200, 690-727 — Phase 202 counter accounting; zone-trace mechanics.
- `src/wanctl/autorate_config.py` line 1184 — asymmetry gate default `enabled=False`.
- `configs/spectrum.yaml` — verified no `asymmetry_gate:` section.
- `tests/test_phase_195_replay.py` lines 642-714 — SAFE-05 v1.40/v1.41/v1.42/v1.42-Phase-202 pin block.
- `tests/test_phase_202_replay.py` — `aggregate_completed_windows`, `_percentile` helpers (to be lifted).
- `.planning/seeds/SEED-004-v143-target-edge-churn-instrumentation.md` — phase intent.
- `.planning/seeds/SEED-002-v143-ul-suppression-metric-semantics.md` — SEED-004 prerequisite + precedent.
- `.planning/REQUIREMENTS.md` — OBSV-05..08 + SAFE-07 wording.
- `.planning/ROADMAP.md` — phase ordering rationale + production-deploy cadence.
- `.planning/milestones/v1.43-phases/202-ul-suppression-metric-semantics-metric/202-RESEARCH.md` — additive-precedent template.
- `.planning/milestones/v1.43-phases/202-ul-suppression-metric-semantics-metric/202-VALIDATION.md` — Nyquist precedent.
- `.planning/milestones/v1.43-phases/202-ul-suppression-metric-semantics-metric/202-VERIFICATION.md` — phase-close artifact precedent.
- `.planning/milestones/v1.42-phases/201-docsis-aware-ul-congestion-control/soak/20260505T132736Z/soak-capture.ndjson` — verified row schema (84,117 rows; row 1 inspected).
- `.planning/milestones/v1.42-phases/201-docsis-aware-ul-congestion-control/soak/20260505T132736Z/soak-capture.sh` — v1.42 capture script (full content inspected).
- `.planning/milestones/v1.42-phases/201-docsis-aware-ul-congestion-control/soak/20260505T132736Z/soak-summary.json` — v1.42 reference output schema (full content inspected).
- `.planning/milestones/v1.42-phases/201-docsis-aware-ul-congestion-control/soak/20260505T132736Z/suppression-stats.json` — v1.42 inline-jq aggregation artifact.
- `.planning/milestones/v1.42-phases/201-docsis-aware-ul-congestion-control/201-16-soak-and-closeout-PLAN.md` — inline-jq aggregator current state.
- `CHANGELOG.md` lines 1-30 — v1.43-dev existing entry from Phase 202.
- `docs/CONFIGURATION.md` lines 280-318 — Phase 202 metric semantics docs (reference for tone/depth).
- `CLAUDE.md` (project + global) — non-negotiable conservative-change posture, public-safe doc rule.

### Secondary (MEDIUM confidence)
- (none — every load-bearing claim cites a primary source.)

### Tertiary (LOW confidence / proposed)
- The aggregator filename `scripts/soak_summary_aggregate.py`, the doc location `docs/SOAK_HARNESS.md`, the histogram bucket array values, the cause-attribution policy for multi-cause cycles. All four are **recommendations**; the planner must lock them in `/gsd-plan-phase`.

---

## Metadata

**Confidence breakdown:**
- Field availability audit: HIGH — verified by direct read of `health_check.py`.
- Asymmetry-gate edge case: HIGH — verified by `configs/spectrum.yaml` + `autorate_config.py` default.
- Capture-script delta: HIGH — projection follows v1.42 pattern verbatim plus seven additive jq paths.
- Aggregator promotion: MEDIUM-HIGH — design is sound but exact module API is subject to plan-phase refinement.
- Histogram bucket scheme: MEDIUM — Option A defaults are sensible; alternative options viable; planner must lock.
- Golden-fixture replay strategy: HIGH — dual-fixture approach is the only viable interpretation given v1.42 NDJSON predates the new fields.
- SAFE-07 verification: HIGH — mechanical `git diff` + existing pin tests; precedent from Phase 202.
- Plan slicing: HIGH — three plans align cleanly with the three deliverable axes (capture, aggregate, doc+verify).

**Research date:** 2026-05-06
**Valid until:** 2026-06-05 (30 days; control-path frozen by SAFE-07; harness layer is local repo work).

---

## RESEARCH COMPLETE
