# Phase 204: D-14 Successor Recalibration (CALIB) - Research

**Researched:** 2026-05-06
**Domain:** wanctl soak-harness watchdog recalibration + production deploy mechanics + operator-approval artifact pattern. **Zero `src/wanctl/` change** by SAFE-07.
**Confidence:** HIGH for code surfaces, mechanics, and precedent (verified live against current tree). MEDIUM-LOW for the exact statistic / headroom recommendations — those are operator judgment items by design (CALIB-02 is named as an operator-approval artifact, not a research deliverable).

---

## Summary

Phase 204 has zero source code work in `src/wanctl/` and one ~30-line change to `scripts/soak-capture.sh` (or its successor in `soak-evidence/`). Everything else is operator workflow, two production binary deploys, two 24h soaks, an operator-approval artifact, a small new Python module under `scripts/`, RETRO, and milestone closeout. SAFE-07 is verified mechanically by the existing `scripts/check-safe07-source-diff.sh` (already wired against Phase 202 close `b72b463`); the SAFE-05 pin block at `tests/test_phase_195_replay.py:642-714` (three dicts: v1.40/v1.41 + Phase 201 + Phase 202) must remain byte-identical at v1.43 close. **Verified clean as of 2026-05-06:** `git diff b72b463..HEAD -- src/wanctl/` returns 0 lines.

The watchdog computation site that CALIB-03 must update is **NOT** in `src/wanctl/`; it lives in the soak-summary aggregator. Today the `ul_hysteresis_suppression_rate_per_60s_mean` value (the one that produced the FAILED `6.467` reading at v1.42 Phase 201 close) is computed by an inline jq pipeline embedded inside the v1.42 Plan 201-16 closeout PLAN — a one-shot script that has not been promoted to `scripts/`. Phase 203 promoted only the `diagnostic_distribution` math into `scripts/soak_summary_aggregate.py`. The secondary-gate computation was deliberately scoped OUT of Phase 203 (per Phase 203 RESEARCH §`Risks` Risk 3): "secondary-gate computation is Phase 204 territory (CALIB-03 explicitly schedules the watchdog computation update)." **Phase 204 is the milestone slot for that promotion.**

**Primary recommendations (HIGH confidence on mechanics; MEDIUM on slicing; LOW on the operator-judgment statistic):**

1. **Statistic for CALIB-02:** recommend operator-approve **`p99 of completed-window count, with a 1.5× headroom multiplier, rounded up to a clean integer`**. Against the v1.42 reference distribution (mean ~13.9/min, p95=41, max=124, ~1331 windows over 24h) this yields a candidate threshold around `~75-100`. This is presented as the recommended default; the operator picks the actual number in `CALIB-02-OPERATOR-APPROVAL.md`. Rationale in §`Q1: Threshold-derivation method`.
2. **Window granularity:** evaluate the gate over the entire soak window, taking the per-completed-window count distribution and gating on the chosen statistic — not a sub-window rolling max. Mirrors v1.42 D-14's "per-60s-window mean" granularity but with the corrected metric semantics. §`Q3`.
3. **CALIB-03 implementation site:** add a new `aggregate_watchdog()` function to `scripts/soak_summary_aggregate.py` that consumes `ul_suppressions_completed_window_count` deltas and emits both the legacy live-counter mean (verbatim port of the broken jq pipeline, for one transition cycle) AND the new completed-window count statistic. §`Q4` and §`Q5`.
4. **Operator-approval artifact:** mirror `201-16-OPERATOR-APPROVAL-D19.md` byte-for-byte structure. §`Q6` quotes it verbatim.
5. **Two-snapshot rollback:** mirror Plan 201-15's T0/T1/T2/T3/T4 sequence for both deploys; for **Deploy 2 (harness-only change)** the rollback is degenerate (no binary deploy needed), so the pattern collapses to "snapshot A = pre-edit harness, edit harness in place, no Snapshot B needed." §`Q7` quotes Plan 201-15 verbatim.
6. **Plan slicing:** **6 plans**, matching the ROADMAP estimate (5-6). Distribution analysis + threshold derivation + operator approval are best as ONE plan because they are a single operator session that produces one artifact. CALIB-03's harness update is a separate plan. The two soak runs (CALIB-01 + CALIB-04) are each their own operator-blocking plan. RETRO and closeout fold into one plan. §`Recommended plan slicing`.

**Critical scope-creep prevention.** CALIB-02 the threshold value is a **soak-harness Python constant**, not a YAML config knob (REQUIREMENTS.md "Out of Scope" §4). Promotion to YAML is structurally barred from v1.43 and is named as a follow-up after CALIB-04 in REQUIREMENTS.md. Any plan that touches `configs/*.yaml`, `src/wanctl/autorate_config.py`, or `src/wanctl/wan_controller.py` `_suppression_alert_threshold` (live at `wan_controller.py:764, 2200, 2207, 2523, 4556`) is a SAFE-07 violation and must be rejected.

---

## User Constraints (from ROADMAP + REQUIREMENTS + Phase 201/202/203 close artifacts)

### Locked Decisions

- **No `src/wanctl/` source diff between Phase 201 close (== Phase 202 close commit `b72b463`) and v1.43 close** — SAFE-07 cross-cutting invariant. Verified clean today: `git diff b72b463..HEAD -- src/wanctl/` returns zero lines (`scripts/check-safe07-source-diff.sh` exit 0).
- **No control-path tuning permitted within v1.43.** SEED-005 (`dwell_cycles`, `upload_target_bloat_ms`, `factor_down_yellow`, etc.) is structurally barred — named for v1.44, not soft-deferred. ROADMAP / REQUIREMENTS / SEED-005 all use the phrase "structurally barred."
- **CALIB-02 threshold is a soak-harness Python constant, NOT a YAML config knob.** REQUIREMENTS.md "Out of Scope" §4 verbatim: "CALIB-02's recalibrated threshold is a soak-harness constant, not a config knob, until proven through CALIB-04." Promotion to YAML is a follow-up commit AFTER v1.43 close.
- **Two production deploys, both gated on operator approval.** ROADMAP "Production deploy cadence":
  - **Deploy 1:** v1.43-dev binary (METRIC-01 + OBSV-05 fields live in `/health`) on cake-shaper before the CALIB-01 baseline soak.
  - **Deploy 2:** Recalibrated threshold in soak harness before the CALIB-04 verification soak. (Note: Deploy 2 is **harness-only** — no production binary change. The "two deploys" phrasing in ROADMAP is precise but easy to misread.)
- **Two-snapshot rollback per Plan 201-15 / 201-16 pattern** for the production binary deploy (Deploy 1). Verified verbatim in §`Q7` below.
- **Single 24h baseline soak fires only after BOTH binary AND harness changes are deployed.** Phase 202 (METRIC-01 binary) is shipped; Phase 203 (OBSV-05 harness) is shipped. Both predecessors verified complete on 2026-05-06 (`202-VERIFICATION.md` + `203-VERIFICATION.md`).
- **Dual-gate semantics:** D-19 primary (`floor_hit_cycles_total_delta_soak_window == 0`) STAYS as primary; D-14-successor passes at the new threshold. Codex re-aggregation oracle from v1.42 reference soak: `peak mean ~13.9/min, p95=41, max=124` over 1,331 completed windows in 84,117 samples. Verified by `tests/test_phase_202_replay.py` and `202-VERIFICATION.md:24` (independent spot-check `13.890308039068369 / 41.0 / 124`).
- **Replay oracle for the watchdog computation transition is the same 2026-05-05 24h capture** at `.planning/milestones/v1.42-phases/.../soak/20260505T132736Z/`. The legacy live-counter-snapshot mean against that capture is `6.467` (`suppression-stats.json`); the codex completed-window peak mean is `~13.9` (verified). Same NDJSON column → two different aggregations → two different numbers. CALIB-03 must reproduce both for one transition cycle.
- **REQUIREMENTS.md Phase 204 REQ-IDs:** CALIB-01, CALIB-02, CALIB-03, CALIB-04, CALIB-05 (RETRO), SAFE-07 (cross-cutting).

### Claude's Discretion

- **Choice of statistic** (p95 vs p99 vs max+headroom vs mean+kσ): research recommends `p99 + 1.5× headroom`, but operator picks in CALIB-02-OPERATOR-APPROVAL.md.
- **Headroom multiplier value** (1.2× vs 1.5× vs 2.0×): research recommends 1.5× for first soak-grounded threshold; operator picks.
- **Rounding policy** (round to nearest 5? to nearest 10? leave as raw float?): research recommends round-up to nearest 25 to avoid false precision; operator picks.
- **CALIB-01 distribution-analysis script location:** recommend extending `scripts/soak_summary_aggregate.py` with one new function (`aggregate_completed_window_distribution()`). Not a separate `analyze_*.py`. Rationale in §`Q9`.
- **Whether CALIB-03's "one transition cycle" means one soak run or one milestone:** recommend one milestone (v1.43 emits both, v1.44+ drops legacy). §`Q5`.
- **Plan slicing.** Recommend 6 plans; could fold to 5 if Deploy 1 + CALIB-01 are merged.
- **Deploy 1 binary version:** recommend version-bump to **`1.43.0`** at Deploy 1 time (not `1.42.2` or `1.43-dev`), mirroring Plan 201-15's "version distinguishability" lesson. The operator can pick differently in the discuss phase.

### Deferred Ideas (OUT OF SCOPE)

- **Promoting the CALIB-02 threshold to a YAML config knob.** Deferred follow-up after CALIB-04 PASS; not a v1.43 closeout deliverable.
- **Dropping the legacy live-counter-snapshot mean from the watchdog.** CALIB-03 explicitly says emit both for one transition cycle; legacy drop is a follow-up commit, not a Phase 204 plan.
- **Tuning `dwell_cycles`, `upload_target_bloat_ms`, `factor_down_yellow`, or any control-path knob.** SEED-005, structurally barred.
- **CAKE qdisc mode changes (SEED-001).** Dormant; would confound D-14 evidence.
- **ATT cake-primary canary (VALN-05b).** Spectrum-only milestone; ATT canary stays cross-milestone deferred.
- **Asymmetry-gate-attenuated `effective_ul_load_rtt` exposure.** Phase 203 documented this as a known limitation; v1.43 milestone is Spectrum-only and Spectrum has the gate disabled, so the limitation has zero impact on CALIB-01/CALIB-04. Future seed if any link enables the gate.
- **Download-side cause-tag aggregation.** Phase 203's matrix is upload-only; CALIB recalibrates upload-side D-14 only.

---

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| CALIB-01 | Operator runs a clean 24h Spectrum baseline soak under post-Plan-201-14 production with METRIC-01 + OBSV-05 live; produces a representative completed-window suppression-count distribution (mean, p50, p95, p99, max). | §`Q4: Watchdog computation site`, §`Q9: Distribution analysis script choice`, §`Q10: SAFE-07 verification`. The harness from Phase 203 (`scripts/soak-capture.sh` + `scripts/soak_summary_aggregate.py`) already captures the inputs; CALIB-01 needs one new aggregator function (`aggregate_completed_window_distribution`). |
| CALIB-02 | Operator-approved D-14 successor threshold is recorded with explicit rationale in a distinct approval artifact (`CALIB-02-OPERATOR-APPROVAL.md` pattern), referencing CALIB-01's distribution. | §`Q1: Statistic`, §`Q2: Headroom`, §`Q6: Operator-approval artifact format`. Mirrors `201-16-OPERATOR-APPROVAL-D19.md` byte-for-byte. |
| CALIB-03 | Soak harness watchdog computation now uses completed-window count statistic; legacy live-counter-snapshot mean is emitted alongside for one transition cycle, then dropped in a follow-up commit. | §`Q4: Site`, §`Q5: Transition cycle definition`. New `aggregate_watchdog()` function in `scripts/soak_summary_aggregate.py`; emits both `secondary_gate_legacy` and `secondary_gate_completed_window` keys side-by-side in `soak-summary.json` for v1.43 only. |
| CALIB-04 | Verification 24h soak passes the dual gate cleanly: D-19 primary stays at 0 floor hits AND D-14-successor passes at the new threshold. | §`Q8: Dual-gate definition`. Both gates are computed from `soak-summary.json`; D-19 is the unchanged primary from Plan 201-16; D-14-successor is the CALIB-02 threshold against the CALIB-03 statistic. |
| CALIB-05 | RETRO references threshold-basis hygiene as a durable lesson. | §`Recommended plan slicing` Plan 6. Mirrors the Phase 201-RETRO Lesson #2 framing. |
| SAFE-07 | No control-path source diff between Phase 201 close and v1.43 close. SAFE-05 control-path pins remain byte-identical at v1.43 close. | §`Q10`. `scripts/check-safe07-source-diff.sh` already wired; v1.40/v1.41 + Phase 201 + Phase 202 dicts in `tests/test_phase_195_replay.py:642-714` must remain byte-identical. No `phase204_expected_counts` dict added (no new src/wanctl symbols). |

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Per-completed-window count distribution computation | `scripts/soak_summary_aggregate.py` (extend) | — | Phase 203 already promoted the aggregator; CALIB-01's inputs are already captured per-row by Phase 203's `ul_suppressions_completed_window_count` field. |
| D-14 successor watchdog gate computation | `scripts/soak_summary_aggregate.py` `aggregate_watchdog()` (new) | — | Replaces the inline jq pipeline embedded in Plan 201-16 closeout PLAN. Promotion of the watchdog math is the analogue of Phase 203's promotion of the diagnostic-distribution math. |
| Legacy live-counter-snapshot mean (transition emission) | same `aggregate_watchdog()` function (one cycle only) | — | Verbatim port of the v1.42 inline jq `[.[] | select(...)]`-corrected `$rows`-binding pipeline, kept alongside the new stat for one milestone cycle. Drops in v1.44+ follow-up. |
| Operator approval artifact | `.planning/phases/204-.../CALIB-02-OPERATOR-APPROVAL.md` | — | Mirrors `201-16-OPERATOR-APPROVAL-D19.md` precedent — a discrete pre-soak operator artifact, not a planner-written claim. |
| Production binary deploy (Deploy 1) | `scripts/deploy.sh` + two-snapshot rollback per Plan 201-15 | `scripts/check-safe07-source-diff.sh` predeploy | Existing deploy machinery; predeploy gate uses `check-safe07-source-diff.sh` to confirm v1.43 binary contains zero control-path diff vs Phase 201 close. |
| Verification 24h soak (CALIB-04) | `scripts/soak-capture.sh` + `aggregate_watchdog()` | operator-monitored tmux session per Plan 201-16 | Reuses Phase 203 capture harness verbatim; gate evaluation reuses the new aggregator function. |
| SAFE-07 verification at v1.43 close | `scripts/check-safe07-source-diff.sh` + SAFE-05 pin tests | manual `git diff` | Mechanical: script already exit-0 today; SAFE-05 pins already byte-identical today. Phase 204 must keep both green. |

---

## Per-Question Findings

### Q1: Threshold-derivation method

**The question:** Given a 24h CALIB-01 distribution of `suppressions_completed_window_count` (per-completed-window totals over ~1,331 boundaries in 24h), what statistic should CALIB-02 set the D-14-successor threshold against?

**Inputs available** (verified):
- v1.42 reference distribution (codex re-aggregation, oracle-pinned in `tests/test_phase_202_replay.py`):
  - **Peak mean ~13.9/min** (`13.890308039068369` per `202-VERIFICATION.md:24`)
  - **p95 = 41** (`41.0`)
  - **max = 124**
  - **p99 not yet computed** — CALIB-01 is the first soak whose summary will report p99 explicitly. Recommend the planner add `p99` as a required field in `aggregate_completed_window_distribution()`.
  - **window count: 1331** (1,331 observable completed windows in the 24h capture).

**Candidates and tradeoffs** [VERIFIED against v1.42 distribution + Phase 201 RETRO framing]:

| Candidate | Math against v1.42 | Pros | Cons | Risk of false PASS / false FAIL |
|-----------|--------------------|------|------|----------------------------------|
| **mean + k·σ** | `13.9 + 3·σ` (σ unknown — would need recompute) | Statistical convention | Sensitive to distribution skew. Tail of `[..., 124]` strongly implies positive skew → mean+kσ understates the true tail risk. | Could pass at threshold ~30 against the v1.42 distribution which already has 5% > 41 — false PASS hazard. |
| **p95 × multiplier** | `41 × 1.5 = 61.5 ≈ 65` | Easy to explain | Allows up to 5% of windows to nominally fail; risk of borderline PASS/FAIL flip-flop. | MEDIUM-HIGH false-FAIL on slightly-noisier soaks. |
| **p99 + headroom** *(recommended)* | p99 not known yet; if p99 ≈ 70 then `70 × 1.5 = 105 ≈ 100` | Tight enough to fail on real regression (>1% of windows above threshold = real); loose enough to absorb benign drift. Aligns with Phase 201 RETRO Lesson #2 "soak-calibrated against the actual control surface." | Operator must commit to a tail-aware threshold; some operators prefer mean-based gates. | LOW false-FAIL; LOW false-PASS. |
| **max + headroom** | `124 × 1.2 = 148.8 ≈ 150` | Easy to explain; absolutely-conservative | Single-sample spike dominates threshold; one-shot 124-event window would push threshold up to 150. | LOW false-FAIL but **HIGH false-PASS** — would hide gradual regression up to ~1.2× the worst observed window. |
| **fixed multiplier of v1.42 mean** | `13.9 × 5 = 70` | Simple round number | No tail-awareness; if v1.43 binary produces a tighter distribution, threshold is conservative; if looser, threshold is meaningless. | MEDIUM false-FAIL or PASS depending on real distribution shift. |

**Recommendation: `p99 + 1.5× headroom, rounded up to nearest 25`** [ASSUMED — operator picks final value].

Three reasons:
1. **Tail-aware:** D-14 is a watchdog for "did the dwell-hold path produce more suppressions than the post-fix control surface should." A regression manifests as right-tail growth; p99 is the right slice to gate against.
2. **Headroom factor of 1.5×** absorbs 30-50% benign drift in distribution shape across Spectrum link conditions (line noise, CMTS scheduler variations, traffic mix) without inviting false PASSes. Lower (1.2×) risks flapping; higher (2.0×) starts approaching `max + headroom` semantics and loses regression-detection sensitivity.
3. **Round-up to nearest 25** avoids false precision. The operator-readable threshold "75" is more defensible than "73.4521" in any future post-mortem.

**Concrete proposal against v1.42 distribution** (numbers below are illustrative; CALIB-01 produces the actual 24h distribution under post-Plan-201-14 production):
- If CALIB-01 p99 ≈ 50 (post-fix tighter than v1.42): threshold ≈ `50 × 1.5 = 75` rounded up to `75`.
- If CALIB-01 p99 ≈ 70 (similar to v1.42 distribution shape, since v1.42 reference soak is itself post-Plan-201-14): threshold ≈ `70 × 1.5 = 105` rounded up to `125`.
- If CALIB-01 p99 ≈ 100 (substantially looser than v1.42): threshold ≈ `100 × 1.5 = 150` rounded up to `150`. *Operator should investigate why post-fix is looser before approving.*

**Confidence:** MEDIUM on the recommendation pattern; LOW on the actual number (CALIB-01 hasn't run; p99 not yet computed). The operator is the right authority for this decision.

### Q2: Headroom factor / safety multiplier

Covered in Q1. Recommended: **1.5×**. Tradeoffs:

| Multiplier | Effect | When operator might prefer |
|------------|--------|----------------------------|
| 1.2× | Tight; flags regression early | High-traffic Spectrum customer, very stable baseline |
| **1.5× (recommended)** | Balanced; absorbs benign drift | Default; first soak-grounded threshold |
| 2.0× | Conservative; allows substantial drift | Operator unsure whether CALIB-01 distribution is representative |
| 3.0× | Equivalent to "close to max + headroom" | Not recommended — defeats the watchdog |

[ASSUMED — operator picks based on CALIB-01 distribution shape]

### Q3: Statistic window granularity

**The question:** D-14-successor evaluates the gate over what window — full 24h soak, rolling 1h max, per-minute peak, etc.?

**v1.42 D-14 precedent** (verified in `201-16-soak-and-closeout-PLAN.md` lines 460-509 and the soak-summary `secondary_gate.computation` field):
> "timestamp-windowed 60s sliding mean (codex NEW-HIGH-3 fix: $rows binding inside reduce)"

i.e. v1.42 D-14 took the 60s-window-bucketed live-counter-snapshot averages, then took the **mean across all 60s windows over the 24h soak**. One number against the threshold; no rolling sub-window.

**Recommendation: mirror v1.42 windowing.** The CALIB-03 update preserves the "per-completed-window stat over the 24h soak" granularity but swaps the per-window aggregation from "mean of live-counter snapshots within the window" to "the single completed-window count value emitted at the boundary." The summary statistic over those 1,331 windows (chosen in Q1: p99) is what the threshold gates against.

Concretely, in `aggregate_watchdog()`:
```python
# Each completed window contributes ONE integer (the snapshot at the 60s boundary)
window_counts = aggregate_completed_windows(snapshots)  # already in scripts/soak_summary_aggregate.py
# Single statistic across the 24h:
gate_statistic = percentile(window_counts, 99)  # CALIB-02 chooses 99
gate_pass = gate_statistic <= CALIB_02_THRESHOLD
```

No rolling sub-window. No per-minute peak. Single 24h-aggregate stat compared to the threshold. Matches D-14 precedent semantics minus the broken metric.

**Confidence:** HIGH. Mirrors v1.42 verbatim windowing.

### Q4: Soak-harness watchdog computation site

**The question:** Identify the exact file/function where the legacy live-counter-snapshot mean is computed today and the new completed-window count statistic must be substituted.

**Verified findings:**

1. **The legacy computation does NOT live in `scripts/`.** It is an inline jq pipeline in the v1.42 Plan 201-16 closeout PLAN (`.planning/milestones/v1.42-phases/201-docsis-aware-ul-congestion-control/201-16-soak-and-closeout-PLAN.md` lines 462-498). The exact pipeline:

   ```bash
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

2. **It computes the WRONG metric** by design — it averages live-counter-snapshot values across each 60s window. That averaging is what produced the `6.467` mean for the v1.42 reference soak (verified at `.planning/milestones/v1.42-phases/.../soak/20260505T132736Z/suppression-stats.json:6` — `"suppressions_per_min_mean": 6.466842364880155`).

3. **Phase 203 explicitly did NOT promote this computation.** Phase 203 RESEARCH §Risk 3: "scope tightly — diagnostic-distribution only in plan 203-02; the secondary-gate computation is Phase 204 territory."

4. **The current `scripts/soak_summary_aggregate.py` does NOT compute either gate.** Verified by reading `scripts/soak_summary_aggregate.py` lines 239-260: `aggregate_soak()` returns `diagnostic_distribution`, `load_rtt_delta_us_by_zone_cause`, and `phase_203_metadata`. There is no `primary_gate`, no `secondary_gate`, no `verdict`. The verdict-bearing fields in v1.42 `soak-summary.json` are written by hand-assembled bash in the Plan 201-16 closeout, not the aggregator.

**Conclusion: CALIB-03's site is `scripts/soak_summary_aggregate.py`, in a NEW function `aggregate_watchdog(rows, threshold) -> dict`.** Plan 204 promotes the inline-jq pipeline to Python (analogue of Phase 203's promotion) AND adds the new completed-window statistic alongside.

**Proposed signature:**
```python
def aggregate_watchdog(
    rows: list[dict[str, Any]],
    *,
    legacy_threshold: float = 5.0,        # v1.42 D-14 — preserved for transition emission
    new_threshold: int,                   # CALIB-02 — NO default; operator must supply
    statistic: str = "p99",               # CALIB-02 — operator-chosen statistic
) -> dict[str, Any]:
    """Compute D-14-successor watchdog gate from completed-window suppression counts.

    Emits BOTH legacy live-counter mean (for one transition cycle, CALIB-03)
    AND new completed-window-based statistic (for D-14-successor gating).
    """
```

**Confidence:** HIGH on the site; HIGH on the function shape. The transition pattern is closely analogous to Phase 203's diagnostic-distribution aggregator promotion.

### Q5: Legacy-emission transition cycle definition

**The question:** "harness emits both legacy and new metric for one transition cycle, then drops legacy in a follow-up commit" — what does "one transition cycle" mean operationally?

**Precedent search:** No identical "emit both metrics for one cycle then drop" precedent in v1.39, v1.40, or v1.41 closure artifacts. The closest analogue is Phase 202's METRIC-01 explicit preservation of `suppressions_per_min` alongside `suppressions_completed_window_count` — but METRIC-01 is permanent backward-compat, not a transition.

**Two viable interpretations:**

| Interpretation | What it means | Downside |
|---|---|---|
| **One soak run** | CALIB-04 verification soak emits both; the next soak (post-v1.43 close) drops legacy | Risk of v1.43 closeout commit accidentally containing the legacy-drop, blurring milestone boundary |
| **One milestone (recommended)** | v1.43 emits both for the entire milestone (CALIB-01 + CALIB-04 both emit both); legacy drops in a v1.44 follow-up commit | Clean milestone boundary; legacy mean visible across both Phase 204 soaks for cross-validation |

**Recommendation: one milestone.** CALIB-03 ships the dual-emission in `aggregate_watchdog()`. The v1.44+ follow-up commit (or a separate CALIB-05-RETRO-FOLLOWUP) removes the `secondary_gate_legacy` block from `aggregate_watchdog()`'s output. The follow-up is NOT a Phase 204 plan; it is a TODO entry created at v1.43 closeout pointing at v1.44 work.

**Concrete output shape during v1.43 (recommended):**
```json
"secondary_gate_legacy": {
  "name": "ul_hysteresis_suppression_rate_per_60s_mean (legacy live-counter-snapshot mean)",
  "computation": "Mean of live-counter snapshots within each 60s window, then mean across windows. Verbatim port of v1.42 Plan 201-16 jq pipeline. PRESERVED FOR ONE TRANSITION CYCLE — drops in v1.44.",
  "value": 6.467,
  "threshold": 5.0,
  "verdict": "fail",
  "note": "This metric is metric-semantically broken; see Phase 201 RETRO Lesson #1. Use secondary_gate_completed_window for actual gating."
},
"secondary_gate_completed_window": {
  "name": "ul_suppressions_completed_window_count_p99",
  "computation": "p99 of per-completed-window suppression counts over the soak window. Replaces secondary_gate_legacy at v1.44.",
  "value": <CALIB_01_observed_p99>,
  "threshold": <CALIB_02_operator_approved>,
  "statistic": "p99",
  "headroom_factor": 1.5,
  "verdict": "<pass|fail>",
  "operator_approval": ".planning/phases/204-d-14-successor-recalibration-calib/204-CALIB-02-OPERATOR-APPROVAL.md"
}
```

**Confidence:** MEDIUM-HIGH. No exact precedent; recommendation derived from Phase 201 closeout's overall hygiene patterns and Phase 202's explicit-naming-of-each-metric framing.

### Q6: Operator approval artifact format

**Verified precedent:** `.planning/milestones/v1.42-phases/201-docsis-aware-ul-congestion-control/201-16-OPERATOR-APPROVAL-D19.md` (21 lines). Quoted verbatim:

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

**Phase 204 mirrors this byte-for-byte at `.planning/phases/204-d-14-successor-recalibration-calib/204-CALIB-02-OPERATOR-APPROVAL.md`:**

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

**CALIB-02 (D-14 successor threshold, soak-grounded):** Phase 204 closure replaces the inherited Phase 201 D-14 `<5/60s` live-counter-snapshot mean threshold with a soak-calibrated successor based on the post-Plan-201-14 production control surface. The threshold is `<chosen statistic>` of the per-completed-window suppression-count distribution observed in the CALIB-01 24h baseline soak, multiplied by a `<headroom factor>` safety margin, giving a final gate value of `<integer>`. The legacy `<5/60s` framing is acknowledged as metric-semantically ambiguous (Phase 201 RETRO Lesson #1) and is emitted alongside the new statistic for one transition cycle (CALIB-03), then dropped in a v1.44 follow-up. This approval references the CALIB-01 distribution by file path; the statistic + headroom + threshold are operator decisions captured here as a distinct pre-deploy artifact, NOT silently written into a verdict file. Operator-approved 2026-05-XX.

---

## CALIB-01 Distribution Reference

- Soak run: `.planning/phases/204-d-14-successor-recalibration-calib/soak/<CALIB_01_TS>/`
- soak-summary.json fields:
  - `suppressions_completed_window_count_distribution.mean = <X>`
  - `..._distribution.p50 = <X>`
  - `..._distribution.p95 = <X>`
  - `..._distribution.p99 = <X>`  ← operator-chosen statistic if statistic=p99
  - `..._distribution.max = <X>`
  - `window_count = <X>` (number of completed 60s windows over the soak)

## References

- Phase 201 RETRO Lesson #1 (metric-semantics framing): `.planning/milestones/v1.42-phases/201-docsis-aware-ul-congestion-control/201-RETRO.md`
- Phase 201 RETRO Lesson #2 (threshold-basis hygiene): same.
- 201-16-OPERATOR-APPROVAL-D19.md (precedent format)
- CALIB-01 baseline soak summary (path above)
- Captures operator approval BEFORE Deploy 2 + CALIB-04 verification soak begins; gates the verification plan.
```

**Confidence:** HIGH. Direct mirror of verified precedent.

### Q7: Two-snapshot rollback specifics

**Verified precedent (Plan 201-15 rev 3, lines 30-31, 71-87, 141-171, 369-417 — quoted verbatim where load-bearing):**

The strict ordering, from Plan 201-15:
> ```
> T0:  snapshot A (legacy state — rollback-clean)
>         - /opt/wanctl  -> /opt/wanctl-prephase201-recanary-<TS>-snapA.tar.gz
>         - /etc/wanctl/spectrum.yaml -> /etc/wanctl/spectrum.yaml.prephase201-recanary-<TS>-snapA
>         - VERIFY snapA YAML has 0 Phase 201 keys
>
> T1:  predeploy gate run #1
>         - if PASS: skip to T3 (no reconcile needed)
>         - if BLOCK: continue to T2
>
> T2:  reconcile YAML
>         - scp configs/spectrum.yaml cake-shaper:/tmp/spectrum.yaml.new
>         - ssh cake-shaper "sudo install -o root -g wanctl -m 0640 /tmp/spectrum.yaml.new /etc/wanctl/spectrum.yaml"
>         - re-run predeploy gate -> must PASS
>
> T3:  snapshot B (post-gate-PASS candidate state)
>         - /opt/wanctl  -> /opt/wanctl-prephase201-recanary-<TS>-snapB.tar.gz
>         - /etc/wanctl/spectrum.yaml -> /etc/wanctl/spectrum.yaml.prephase201-recanary-<TS>-snapB
>         - snapB YAML now contains Phase 201 keys (the candidate); deploy evidence only
>
> T4:  deploy v1.42.1 binary
>         - REMOTE_SSH_TARGET=cake-shaper REMOTE_YAML_PATH=/etc/wanctl/spectrum.yaml ./scripts/deploy.sh spectrum cake-shaper
>         - ssh cake-shaper "sudo systemctl restart wanctl@spectrum.service"
>
> ON FAIL:
>   - tar -xzf <...>-snapA.tar.gz -C /         # restore legacy binary from snapshot A
>   - cp <...>-snapA /etc/wanctl/spectrum.yaml  # restore legacy YAML from snapshot A
>   - VERIFY post-rollback /health.version == 1.39.0 AND Phase 201 YAML key count == 0
> ```

**Verbatim definition of "two snapshots" (Plan 201-15 must_haves line 30):**
> "Snapshot A (rollback-clean) is captured BEFORE any Phase 201 YAML is reconciled into /etc/wanctl/spectrum.yaml. Snapshot A is the rollback target. ... Snapshot B (post-gate candidate) is captured AFTER predeploy gate PASS (i.e., after configs/spectrum.yaml has been reconciled into /etc/wanctl/spectrum.yaml). Snapshot B holds the candidate Phase 201 YAML and is used as deploy evidence ONLY — it is NEVER used as a rollback target. The strict ordering: snapshot A -> predeploy gate -> reconcile Phase 201 YAML -> snapshot B -> deploy."

**Verbatim "snapshot pair" definition (Plan 201-15 must_haves line 31):**
> "Pre-deploy snapshot pair: /opt/wanctl binary archive AND /etc/wanctl/spectrum.yaml — captured at the snapshot-A moment for rollback-clean state, captured AGAIN at the snapshot-B moment for deploy evidence."

**Phase 204 application:**

- **Deploy 1 (v1.43 binary with METRIC-01 + OBSV-05 fields)** — full Plan 201-15 pattern applies. Snapshot A captures `/opt/wanctl` (currently v1.42.1) + `/etc/wanctl/spectrum.yaml` BEFORE any v1.43-binary install. v1.43 ships **no new YAML keys** (REQUIREMENTS.md "Out of Scope" §3 — additive `/health` schema only), so the predeploy-gate "reconcile" step from Plan 201-15 is trivially a no-op (no v1.41-keys-to-remove problem; no v1.43 YAML keys to add). The strict ordering still holds:

  ```
  T0:  snapshot A — /opt/wanctl + /etc/wanctl/spectrum.yaml at v1.42.1 (rollback-clean)
  T1:  predeploy gate run #1 — runs scripts/check-safe07-source-diff.sh against the candidate v1.43 binary's source tree;
        confirms zero src/wanctl/ diff vs Phase 201 close (b72b463). PASS expected (Phase 202 + 203 are additive).
  T2:  no reconcile needed (no new YAML keys in v1.43)
  T3:  snapshot B — /opt/wanctl + /etc/wanctl/spectrum.yaml at v1.42.1 still
        (because nothing was reconciled; A and B are byte-identical here, captured separately for evidence symmetry with Plan 201-15)
  T4:  deploy v1.43 binary via scripts/deploy.sh
  ```

- **Deploy 2 (recalibrated threshold in soak harness)** — pattern degenerates because the change is a soak-harness Python constant, not a production binary or YAML. The "deploy" is a git commit to `scripts/soak_summary_aggregate.py` and (optionally) re-uploading `/tmp/soak-capture.sh` to cake-shaper. **Recommendation: still capture the pre-edit harness state in the soak directory** as the rollback artifact (`soak/<CALIB_04_TS>/aggregator-pre-edit.py.snapshot`), but do not stand up the full T0/T1/T2/T3/T4 sequence — there is no production binary to roll back. Document this asymmetry explicitly in the plan to avoid operator confusion ("why is Deploy 2 simpler than Deploy 1?").

**Confidence:** HIGH on the verbatim Plan 201-15 pattern; HIGH on Deploy 1 application; MEDIUM on Deploy 2 simplification (the planner could choose to keep the full pattern for ritual symmetry — defensible either way).

### Q8: CALIB-04 dual-gate pass criterion

**The question:** What is the exact pass criterion for "D-19 primary stays at 0 floor hits AND D-14-successor passes at the new threshold"?

**Verified gate fields in `soak-summary.json` (from v1.42 reference at `soak/20260505T132736Z/soak-summary.json`):**

```json
"primary_gate": {
  "name": "floor_hit_cycles_total_delta_soak_window",
  "threshold": "== 0 (operator-approved D-19, see 201-16-OPERATOR-APPROVAL-D19.md)",
  "t0": 0, "t24": 0, "delta": 0,
  "verdict": "pass",
  "reason": null
}
```

**CALIB-04 dual-gate concrete criterion:**

```python
calib_04_pass = (
    soak_summary["primary_gate"]["verdict"] == "pass"
    and soak_summary["primary_gate"]["delta"] == 0
    and soak_summary["secondary_gate_completed_window"]["verdict"] == "pass"
    and soak_summary["secondary_gate_completed_window"]["value"] <= soak_summary["secondary_gate_completed_window"]["threshold"]
)
```

Disagreement (one PASS, one FAIL) is a `verdict=fail` with explicit reason — same pattern as v1.42 reference soak's `"reason": "soak_gates_disagreement_primary_pass_secondary_fail"`.

**The legacy `secondary_gate_legacy` block is NOT part of the CALIB-04 pass criterion.** It is informational only (transition emission). v1.43 close has it; v1.44 follow-up drops it.

**Confidence:** HIGH.

### Q9: Distribution-analysis script choice

**The question:** Should CALIB-01's distribution analysis be a one-off jq/python in the plan, or a versioned script under `scripts/`?

**Verified state:**
- `scripts/soak_summary_aggregate.py` already exists (Phase 203). 297 lines. Stdlib-only.
- The function `aggregate_completed_windows(snapshots)` already exists (lines 52-60) — it computes per-window counts from a `suppressions_per_min` column. **Phase 204 reuses this verbatim against the new `ul_suppressions_completed_window_count` column** (which is even simpler — values come directly from the field, no boundary-detection algorithm needed; though the existing function is direction-agnostic and works on any monotonic-then-resetting integer column).
- `scripts/soak_summary_aggregate.py` already exposes `percentile()`, `histogram()`, `_build_cell()` — all stdlib, all reusable.
- Phase 203's RESEARCH §`Aggregator promotion` Risk 7: "CALIB-01 + CALIB-03 will read the aggregator's output and add a watchdog computation for the recalibrated D-14 successor threshold. The aggregator must be designed for extension."

**Recommendation: extend `scripts/soak_summary_aggregate.py` with TWO new functions, do not create a separate `analyze_*.py`:**

1. `aggregate_completed_window_distribution(rows) -> dict` — produces the CALIB-01 distribution stats (mean, p50, p95, p99, max, window_count).
   - Input: NDJSON rows with `ul_suppressions_completed_window_count` per row.
   - Algorithm: walk the column, detect window boundaries (the value resets at every 60s boundary AT the boundary; in practice the same value persists between boundaries since `_last_completed_window_total` is a snapshot). Take the value once per distinct boundary epoch.
   - Output: `{"mean": float, "p50": float, "p95": float, "p99": float, "max": int, "window_count": int}` plus optional histogram.

2. `aggregate_watchdog(rows, *, legacy_threshold, new_threshold, statistic) -> dict` — emits both gates per Q5.

Both functions are stdlib-only, no NumPy. Both extend the existing module pattern.

**Why not a separate script:**
- Reusing the existing module preserves the aggregator's "single source of truth for soak-summary.json math" identity.
- Tests live in `tests/test_phase_203_replay.py`; Phase 204 adds a sibling `tests/test_phase_204_replay.py` rather than duplicating fixture machinery.
- No new MyPy/Ruff target to register.

**Why not jq/inline-bash:**
- Phase 201 RETRO + Phase 203 RESEARCH §Risk 3 already learned this lesson — the broken `[.[] | select(...)]` in Plan 201-16 rev 1/rev 2 motivated the codex NEW-HIGH-3 finding. Inline jq is fragile for `reduce`-with-inner-select.

**Confidence:** HIGH. Direct application of Phase 203's "promote inline-jq to versioned aggregator" precedent.

### Q10: SAFE-07 verification at v1.43 close

**The question:** What's the exact mechanical check Phase 204's closeout does to verify SAFE-07?

**Two complementary checks (already wired today, verified by reading the live tools):**

1. **Mechanical source diff** — `scripts/check-safe07-source-diff.sh` (Phase 203, 51 lines):
   ```bash
   bash scripts/check-safe07-source-diff.sh
   ```
   - Default ref: `b72b463` (Phase 202 close, recorded in script line 21). For Phase 204, the script can be re-run as-is — the SAFE-07 invariant is "no diff vs Phase 201 close == Phase 202 close" because Phase 202 was additive-only and Phase 203 made zero `src/wanctl/` changes.
   - Exit 0 → SAFE-07 OK; exit 1 → VIOLATION; exit 2 → ref not found.
   - **Verified clean today (2026-05-06):** `git diff b72b463..HEAD -- src/wanctl/` returns 0 lines.

2. **SAFE-05 pin block** — `tests/test_phase_195_replay.py:642-714`:
   ```bash
   .venv/bin/pytest tests/test_phase_195_replay.py -v -k "safe05_threshold_name_counts"
   ```
   - Three dicts checked:
     - `expected_counts` (lines 663-673) — v1.40/v1.41 thresholds: `factor_down=17, step_up=12, dwell_cycles=14, deadband_ms=14, warn_bloat=12, target_bloat=14, hard_red=17, burst_threshold=0, green_required=12`
     - `phase201_expected_counts` (lines 686-693) — v1.42 keys: `docsis_mode=36, setpoint_mbps=35, integral_window_seconds=10, integral_threshold_ms_s=13, cake_backlog_low_threshold_bytes=10, cake_delay_delta_low_threshold_us=10`
     - `phase202_expected_counts` (lines 702-711) — v1.43 Phase 202 keys: `_record_suppression=4, _window_suppressions_by_cause=6, _lifetime_suppressions_by_cause=3, _last_completed_window_total=3, _last_completed_window_by_cause=3, suppressions_completed_window_count=3, suppressions_completed_window_by_cause=3, suppressions_lifetime_by_cause=3`
   - All three must remain byte-identical at v1.43 close (Phase 204 close).
   - **No `phase204_expected_counts` dict added** — Phase 204 adds zero new symbols to `src/wanctl/` (mirror of Phase 203's "no source pins" approach, RESEARCH §`SAFE-07 verification mechanism`).

3. **Predeploy comparator at Deploy 1** — Plan 201-15's predeploy gate analogue. The new v1.43 binary's source tree must show zero diff vs `b72b463` in `src/wanctl/` BEFORE the binary lands on cake-shaper. `scripts/check-safe07-source-diff.sh` is the right tool.

**End-of-Phase-204 closure checklist (mechanical):**
```bash
# 1. SAFE-07 source diff (must exit 0):
bash scripts/check-safe07-source-diff.sh

# 2. SAFE-05 pin block (must pass; dicts byte-identical):
.venv/bin/pytest tests/test_phase_195_replay.py -v -k "safe05_threshold_name_counts"

# 3. Hot-path slice (regression):
.venv/bin/pytest -o addopts='' tests/test_cake_signal.py tests/test_queue_controller.py tests/test_wan_controller.py tests/test_health_check.py -q

# 4. Phase 202 + 203 + 204 replay tests (CALIB-03 aggregator tests + existing replay tests all green):
.venv/bin/pytest tests/test_phase_204_replay.py tests/test_phase_203_replay.py tests/test_phase_203_capture_projection.py tests/test_phase_202_replay.py tests/test_phase_195_replay.py -q
```

**Confidence:** HIGH. All four commands runnable today; the first two return clean as of 2026-05-06.

---

## Recommended Plan Slicing

**6 plans (matches ROADMAP estimate "5-6 plans").** Granular, but each plan has a discrete deliverable, a discrete operator gate, and an obvious dependency arrow.

### Plan 204-01 — Predeploy gate + Deploy 1 (METRIC-01 + OBSV-05 binary on cake-shaper)

**Scope:** Two-snapshot rollback per Plan 201-15; deploy v1.43 binary built from current main (Phase 202 + 203 already merged); confirm `/health` exposes new METRIC-01 + OBSV-05 fields.

- Operator-approval checkpoint BEFORE deploy (verify SAFE-07 clean, hot-path tests green, version-bump to `1.43.0` landed in `__init__.py`/`pyproject.toml`/`docker/Dockerfile`).
- Snapshot A (cake-shaper /opt/wanctl + /etc/wanctl/spectrum.yaml at v1.42.1).
- Predeploy gate — `bash scripts/check-safe07-source-diff.sh` returns exit 0.
- Snapshot B (degenerate; same as A since no YAML reconcile).
- Deploy v1.43 binary; restart wanctl@spectrum.service.
- Post-deploy `/health` smoke: assert `version == "1.43.0"`, `wans[0].upload.hysteresis.suppressions_completed_window_count` field present (METRIC-01), `wans[0].load_rtt_ms` present (OBSV-05 source).
- Write `204-01-DEPLOY-VERIFICATION.md` (operator-readable verdict).

**autonomous: false** (production deploy).

**Size:** ~30 LOC of orchestration shell, no new tests, ~150 lines of operator-readable verdict markdown.

**Dependencies:** none (Phase 202 + 203 close).

### Plan 204-02 — CALIB-01 baseline soak + distribution analysis

**Scope:** Operator runs the 24h baseline soak with the new harness. Aggregator gets a new function for the distribution stats.

- Add `aggregate_completed_window_distribution(rows)` to `scripts/soak_summary_aggregate.py`.
- Add `tests/test_phase_204_distribution.py` with synthetic-fixture replay (mirrors Phase 203's pattern; 50-100 row fixture exercising the distribution math).
- Operator runs the 24h soak via existing `scripts/soak-capture.sh` (Plan 201-16 protocol, harness from Phase 203). Capture lands in `.planning/phases/204-d-14-successor-recalibration-calib/soak/<CALIB_01_TS>/`.
- Aggregator runs against the capture; `soak-summary.json` includes the new `suppressions_completed_window_count_distribution` block.
- Operator reviews the distribution; commits `soak/<CALIB_01_TS>/soak-summary.json` + `soak-capture.ndjson`.

**autonomous: false** for the soak (24h wall clock, operator-monitored); **autonomous: true** for the aggregator function + tests.

**Size:** ~80 LOC for the function + tests, ~30 lines of fixture, plus the 24h soak (no LOC).

**Dependencies:** Plan 204-01 close.

### Plan 204-03 — CALIB-02 threshold derivation + operator approval artifact

**Scope:** Operator session — review the CALIB-01 distribution, pick the statistic + headroom + threshold, write the operator-approval artifact.

- Operator-blocking checkpoint with the prepared CALIB-01 distribution in front of them (the planner can render the distribution as a small ASCII histogram or table inside the plan's `<how-to-verify>` block).
- Operator types `approved: <statistic, headroom, threshold, justification>`.
- Plan writes `204-CALIB-02-OPERATOR-APPROVAL.md` with the byte-for-byte format from Q6.
- The approved triple (statistic, headroom_factor, threshold) becomes constants in the soak harness — but the harness change is Plan 204-04, not here. This plan only writes the artifact.

**autonomous: false** (operator decision).

**Size:** ~50 lines of artifact markdown; no code.

**Dependencies:** Plan 204-02 close (distribution must exist).

### Plan 204-04 — CALIB-03 watchdog harness update + Deploy 2

**Scope:** Add `aggregate_watchdog()` to `scripts/soak_summary_aggregate.py` with both legacy + new emission. Update soak-summary schema. Tests. Optional re-upload of `/tmp/soak-capture.sh` to cake-shaper.

- Read `204-CALIB-02-OPERATOR-APPROVAL.md` to extract the approved threshold/statistic/headroom — encode as **constants in `aggregate_watchdog()` defaults OR as a small operator-approval-derived JSON file** (`scripts/calib_02_threshold.json` or similar). **Recommendation: JSON file** with one record `{"statistic": "p99", "threshold": 75, "headroom_factor": 1.5, "approval_artifact": ".planning/phases/204-.../204-CALIB-02-OPERATOR-APPROVAL.md"}`. Aggregator reads it. This is operator-readable, easy to override for testing, and the JSON file's existence + shape can be tested.
- Add `aggregate_watchdog(rows, *, legacy_threshold, new_threshold, statistic) -> dict` per Q4 signature.
- Update `aggregate_soak()` to call `aggregate_watchdog()` and merge its output into the summary.
- Add `tests/test_phase_204_watchdog.py`:
  - Replay against v1.42 reference NDJSON. Assert `secondary_gate_legacy.value` matches `6.467` (the inline-jq oracle). Assert `secondary_gate_completed_window.value` matches the codex re-aggregation (mean ~13.9 / p99 ≈ TBD).
  - Synthetic fixture exercising the `verdict: pass` and `verdict: fail` branches.
- Update `docs/SOAK_HARNESS.md` with the new soak-summary schema (the two new gate blocks).
- Update `CHANGELOG.md` v1.43-dev with the CALIB-03 transition.
- **No production binary deploy.** "Deploy 2" is a git commit + (optionally) `scp scripts/soak-capture.sh cake-shaper:/tmp/soak-capture.sh` if the capture script changed (it should NOT — capture rows are unchanged from Phase 203).

**autonomous: true** (no production binary change). Operator approval was the precondition, captured in Plan 204-03.

**Size:** ~150 LOC for `aggregate_watchdog()` + JSON loader; ~120 LOC tests; ~30 lines docs + CHANGELOG.

**Dependencies:** Plan 204-03 close (artifact must exist).

### Plan 204-05 — CALIB-04 verification soak + dual-gate pass

**Scope:** Operator runs the verification 24h soak. Same harness, same aggregator (now with `aggregate_watchdog()` live). Pass criterion per Q8.

- Capture lands in `.planning/phases/204-d-14-successor-recalibration-calib/soak/<CALIB_04_TS>/`.
- `soak-summary.json` is computed; `verdict: pass` requires both primary and `secondary_gate_completed_window` PASS.
- On PASS: `204-05-CALIB-04-SOAK-VERDICT.md` records pass; CALIB-04 row in REQUIREMENTS.md flips to `[x]`.
- On FAIL: explicit FAIL reason recorded; operator decides whether to re-run (suspect transient), recalibrate threshold (CALIB-02 was too tight), or escalate.

**autonomous: false** (24h wall clock; operator-monitored; verdict-recording requires operator approval per CLAUDE.md).

**Size:** ~80 lines of operator-readable verdict markdown; no LOC.

**Dependencies:** Plan 204-04 close.

### Plan 204-06 — RETRO + closeout

**Scope:** CALIB-05 + SAFE-07 closure + standard closeout artifacts.

- Write `204-RETRO.md` capturing CALIB-05's threshold-basis hygiene lesson (verbatim mirror of Phase 201 RETRO Lesson #2: "Threshold-basis hygiene: inherited thresholds need explicit re-justification when the control surface changes materially.").
- SAFE-07 verification — run the four-command checklist from §`Q10`. All four green.
- Update REQUIREMENTS.md: CALIB-01..05 + SAFE-07 row → satisfied.
- Update ROADMAP.md: Phase 204 5/6 → Complete; v1.43 milestone → Complete.
- Update STATE.md.
- Write `204-VERIFICATION.md` (Phase 202 / 203 precedent).
- Write `204-VALIDATION.md` (`nyquist_compliant: true`).
- Optionally: write a TODO entry pointing at v1.44 follow-up (drop `secondary_gate_legacy` from `aggregate_watchdog()`; promote CALIB-02 threshold to YAML).

**autonomous: false** (closeout decisions; CLAUDE.md change policy).

**Size:** ~400 lines of markdown; no LOC.

**Dependencies:** Plan 204-05 PASS.

### Could-fold-together alternatives considered (and why I'm recommending NOT to fold)

- **Plan 204-01 + Plan 204-02:** "Deploy 1 + CALIB-01 are one operator session." True — the operator sequence is "deploy v1.43 binary, then start the 24h soak." But: the deploy is a discrete artifact (verdict file, two-snapshot proofs) and the soak is a discrete 24h wait. Folding them would create a single plan with TWO operator-blocking gates (predeploy approval + 24h soak completion), violating the "one plan, one main deliverable" pattern Phase 201 used. **Keep separate.**

- **Plan 204-03 + Plan 204-04:** "Threshold approval and harness encoding could be one plan." False — the operator-approval artifact must exist BEFORE harness encoding (per the Phase 201 LOW-CODEX-5 lesson: "the operator must explicitly approve [the gate] BEFORE [encoding it], not have it written into a verdict file post hoc"). **Keep separate.**

- **Plan 204-05 + Plan 204-06:** "Verification soak + closeout could be one plan." Possible, but a FAIL on CALIB-04 should not trigger a closeout sequence. Keeping them separate makes the FAIL path defensible. **Keep separate.**

### Plan ordering and dependencies

```
204-01 (Deploy 1 + binary verification)
   ↓
204-02 (CALIB-01 24h soak + distribution analysis)
   ↓
204-03 (Operator-approval artifact for CALIB-02)
   ↓
204-04 (CALIB-03 harness update + Deploy 2 commit)
   ↓
204-05 (CALIB-04 verification 24h soak)
   ↓
204-06 (RETRO + closeout)
```

Strictly serial. No parallelization gain — each plan depends on the prior plan's operator artifact or production state.

**Confidence:** HIGH on the 6-plan partition; HIGH on the ordering; MEDIUM on whether 204-04 should split into "harness update" + "Deploy 2 commit" (currently they're one plan because the "deploy" is just a git commit).

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (existing; same as Phase 202 + 203) |
| Config file | `pyproject.toml [tool.pytest.ini_options]` |
| Quick run command | `.venv/bin/pytest -o addopts='' tests/test_cake_signal.py tests/test_queue_controller.py tests/test_wan_controller.py tests/test_health_check.py -q` |
| Phase-scoped slice | `.venv/bin/pytest tests/test_phase_204_distribution.py tests/test_phase_204_watchdog.py tests/test_phase_204_replay.py tests/test_phase_203_replay.py tests/test_phase_203_capture_projection.py tests/test_phase_202_replay.py tests/test_phase_195_replay.py -q` |
| Full suite | `.venv/bin/pytest tests/ -q` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| CALIB-01 | Distribution analysis emits mean/p50/p95/p99/max from completed-window-count column | unit + replay | `.venv/bin/pytest tests/test_phase_204_distribution.py -v` | ❌ Wave 0 (Plan 204-02) |
| CALIB-02 | Operator-approval artifact exists with `decision: approved` and machine-readable threshold | manual (operator workflow) + grep | `grep -q "decision: approved" .planning/phases/204-.../204-CALIB-02-OPERATOR-APPROVAL.md && jq -e '.threshold' scripts/calib_02_threshold.json` | ❌ Wave 0 (Plan 204-03 + 204-04) |
| CALIB-03 | `aggregate_watchdog()` emits both `secondary_gate_legacy` (matches v1.42 oracle 6.467) and `secondary_gate_completed_window` (matches codex re-aggregation) | replay + synthetic | `.venv/bin/pytest tests/test_phase_204_watchdog.py -v` | ❌ Wave 0 (Plan 204-04) |
| CALIB-04 | Verification soak's `soak-summary.json` shows `primary_gate.verdict == "pass" AND secondary_gate_completed_window.verdict == "pass"` | manual (24h soak) + automated verdict check | grep + jq against `soak/<CALIB_04_TS>/soak-summary.json` | ❌ Wave 0 (Plan 204-05) |
| CALIB-05 | RETRO documents threshold-basis hygiene lesson | manual-only | `grep -q "threshold-basis hygiene" .planning/phases/204-.../204-RETRO.md` | ❌ Wave 0 (Plan 204-06) |
| SAFE-07 | No `src/wanctl/` source diff between Phase 201 close and v1.43 close. SAFE-05 pins byte-identical. | regression + diff | `bash scripts/check-safe07-source-diff.sh` AND `.venv/bin/pytest tests/test_phase_195_replay.py -v -k "safe05_threshold_name_counts"` | ✅ both already wired |

### Sampling Rate

- **Per task commit:** quick hot-path slice + the plan's own test file (e.g., Plan 204-04 commits run `.venv/bin/pytest tests/test_phase_204_watchdog.py -v` plus the hot-path slice).
- **Per wave merge:** phase-scoped slice.
- **Phase gate (`/gsd-verify-work`):** full suite green; `bash scripts/check-safe07-source-diff.sh` exit 0; SAFE-05 pin test green.

### Wave 0 Gaps

- [ ] `tests/test_phase_204_distribution.py` — covers CALIB-01 distribution math; created in Plan 204-02.
- [ ] `tests/test_phase_204_watchdog.py` — covers CALIB-03 dual-emission + dual-gate verdict math; created in Plan 204-04.
- [ ] `tests/test_phase_204_replay.py` — replay against v1.42 reference NDJSON for the watchdog computation (verifies legacy oracle 6.467 and codex re-aggregation match); folds into the watchdog test file or sibling depending on planner preference.
- [ ] `tests/fixtures/phase_204_synthetic_capture.ndjson` — synthetic NDJSON exercising the `aggregate_watchdog()` PASS/FAIL branches; mirrors Phase 203 `_phase_203_generator.py` deterministic-fixture pattern.
- [ ] `tests/fixtures/phase_204_synthetic_summary.json` — golden expected aggregator output.
- [ ] `scripts/calib_02_threshold.json` — operator-approval-derived constant file consumed by `aggregate_watchdog()` defaults; created in Plan 204-04.

### Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|---|---|---|---|
| 24h CALIB-01 soak runs to completion under v1.43 binary on cake-shaper | CALIB-01 | 24h wall clock; production hardware; operator monitoring | `scripts/soak-capture.sh` per Plan 201-16 protocol; verify NDJSON line count >= 86,000 |
| Operator approves CALIB-02 threshold pre-Deploy-2 | CALIB-02 | Operator decision is the artifact | `grep -q "decision: approved" .planning/phases/204-.../204-CALIB-02-OPERATOR-APPROVAL.md` |
| 24h CALIB-04 verification soak runs to completion under recalibrated threshold | CALIB-04 | 24h wall clock | same harness; verify dual-gate verdict in soak-summary.json |
| RETRO captures threshold-basis hygiene lesson | CALIB-05 | Doc-presence test would churn on edits | `grep -q "threshold-basis hygiene" .planning/phases/204-.../204-RETRO.md` |
| Phase 204 introduced no controller tuning; `src/wanctl/` byte-identical vs Phase 201 close | SAFE-07 (cross-cutting) | "No source diff across an entire phase" is git-diff semantics | `bash scripts/check-safe07-source-diff.sh` exit 0 |

### Validation Sign-Off Targets

- [ ] CALIB-01, CALIB-03 fully automated via `tests/test_phase_204_distribution.py` + `tests/test_phase_204_watchdog.py`
- [ ] CALIB-02 manual-only by design (operator approval artifact)
- [ ] CALIB-04 manual-only (24h soak); verdict file structure automated
- [ ] CALIB-05 manual-only (doc-presence)
- [ ] SAFE-07 partially automated via existing pin test + check-safe07-source-diff.sh; fully verified at closeout
- [ ] Sampling continuity: each plan has a primary automated test
- [ ] Wave 0 covers all MISSING references (see list above)

Phase 204 should target `nyquist_compliant: true` modulo the same operator-judgment manual-only carve-outs Phase 202 and Phase 203 took.

---

## Risks

### Risk 1: CALIB-01 distribution differs materially from v1.42 reference (MEDIUM)

The v1.42 reference soak distribution (mean ~13.9, p95=41, max=124, n=1331) was captured under post-Plan-201-14 production. Phase 204 reruns this on the same code (no control-path change in v1.43 by SAFE-07), so the distribution **should** be statistically similar — but Spectrum link conditions (CMTS scheduler, traffic mix, line noise) drift over a one-week interval. If CALIB-01's p99 is materially different (>2×) from what would be predicted from the v1.42 distribution, the operator should investigate before approving CALIB-02.

**Mitigation:** Plan 204-03's operator session has the v1.42 distribution as a reference-comparison artifact. If CALIB-01 looks anomalous, the operator can re-run CALIB-01 (extra 24h wall clock; defer the approval session by a day).

### Risk 2: Phase 202's per-cycle backlog-recovery semantics inflate CALIB-01 distribution (MEDIUM-HIGH)

Phase 202 RESEARCH §Risk 2 + CHANGELOG warning: "backlog_recovery accounting is per-cycle: a 60s window at 20Hz can produce up to ~1,200 backlog_recovery counts per cause per window."

The new `suppressions_completed_window_count` includes `backlog_recovery` summed in. If production exhibits any sustained backlog recovery, completed-window counts could be massively higher than v1.42's reference (which only counted dwell-hold).

**This is by design** (Phase 202 Option A documented in 202-RESEARCH.md), but the implication for CALIB-02 is significant: the recommended `p99 + 1.5× = 75-150` numbers above are derived from the v1.42 dwell-hold-only distribution. If Spectrum production exhibits even occasional backlog-recovery, the CALIB-01 distribution could be 10× higher.

**Mitigation:**
- The v1.42 reference soak distribution is dwell-hold-only (Phase 202 hadn't shipped); CALIB-01 is the **first** soak under the new metric and may surface new behavior.
- Plan 204-02 must explicitly compare CALIB-01's `dwell_hold` cause-tag count to its `backlog_recovery` cause-tag count. If `backlog_recovery >> dwell_hold`, the operator + planner need to decide: gate against the **per-cause `dwell_hold` slice** (matches v1.42 D-14 spirit) or the total. **Recommend gating against the `dwell_hold` slice** for the CALIB-02 successor, and surfacing the total + backlog as separate informational fields. This preserves the metric-semantic intent of D-14 (the YELLOW-edge dwell-hold path) while still emitting the full new metric.
- This is a **load-bearing decision** the planner must lock at Plan 204-03 time, with operator judgment.

**Confidence:** MEDIUM-HIGH on the risk; LOW on the actual production behavior (CALIB-01 will surface this).

### Risk 3: Inline-jq → Python promotion drops a behavior (LOW-MEDIUM)

The Plan 201-16 inline jq pipeline computes `suppressions_per_min_mean = 6.467` against the v1.42 reference NDJSON. Plan 204-04's `aggregate_watchdog()` must reproduce this number exactly (within float tolerance) for the legacy `secondary_gate_legacy.value` field, otherwise the transition emission is lying about backward compatibility.

**Mitigation:** `tests/test_phase_204_watchdog.py` includes a regression test against the v1.42 NDJSON asserting `secondary_gate_legacy.value` matches `6.466842364880155` to 6+ decimal places. Same precedent as Phase 203 RESEARCH §Risk 3.

### Risk 4: Two-snapshot rollback simplification on Deploy 2 invites operator confusion (LOW)

Per Q7, Deploy 2 has no production binary change → no rollback → the two-snapshot pattern degenerates. An operator who reads only ROADMAP "two production deploys, both gated on operator approval" without reading the plan may expect a full T0/T1/T2/T3/T4 sequence and be confused when Plan 204-04 doesn't have one.

**Mitigation:** Plan 204-04 includes an explicit "Why Deploy 2 looks different" section explaining the asymmetry. Plan 204-01 reciprocally cites Plan 201-15 for the full pattern.

### Risk 5: SAFE-07 false-positive on a stale `b72b463` ref (LOW)

`scripts/check-safe07-source-diff.sh` defaults to `b72b463` (Phase 202 close). If Phase 204 work somehow produced a `src/wanctl/` change (against SAFE-07), the script catches it. If `b72b463` is rewritten or rebased away, the script returns exit 2 and the planner must update the ref.

**Mitigation:** none needed today; ref is stable on `main`. If the v1.43 close commit becomes the new ref for v1.44, that's a one-line update to the script done at v1.44 phase 0.

### Risk 6: CALIB-04 FAIL recovery path (MEDIUM)

If the verification soak FAILs, the operator is in an awkward spot — either the threshold was wrong (too tight; rerun CALIB-02 approval with a higher number) or the production binary has a real regression that v1.42's reference soak didn't surface (unlikely — same code by SAFE-07, but environment drift is real). The recovery path is not specified in REQUIREMENTS.md or ROADMAP.

**Mitigation:** Plan 204-05 includes an explicit FAIL-handling section:
- If `secondary_gate_completed_window.value` is just over the threshold (within ~10%): operator can re-approve CALIB-02 at a slightly higher number, re-run CALIB-04. No new soak needed.
- If `secondary_gate_completed_window.value` is materially higher (>2× threshold) OR `primary_gate.delta != 0`: stop. Investigate. v1.43 milestone closure gets deferred to v1.44 with a new RETRO entry.
- If a daemon restart occurred mid-soak (`primary_gate.reason == soak_primary_gate_uncollectible_negative_delta_*`): re-run CALIB-04 (transient infra issue, not a real regression).

### Risk 7: Aggregator API churn breaks Phase 203 tests (LOW)

Plan 204-04 extends `scripts/soak_summary_aggregate.py` with `aggregate_watchdog()` and possibly modifies `aggregate_soak()`'s output shape. Phase 203 tests at `tests/test_phase_203_replay.py` golden-fixture-compare against `tests/fixtures/phase_203_synthetic_summary.json`. If `aggregate_soak()` returns new top-level keys (`secondary_gate_*`), the golden fixture must be regenerated.

**Mitigation:** Plan 204-04 explicitly notes the golden-fixture refresh as a required deliverable. Re-run `_phase_203_generator.py` (deterministic) or hand-edit the golden JSON to include the new keys with empty/zero values (since the synthetic fixture has no completed-window-count column).

---

## Code Examples

### Operator-approval artifact loader (Plan 204-04)

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

### `aggregate_watchdog()` skeleton (Plan 204-04)

```python
# scripts/soak_summary_aggregate.py — proposed addition

def aggregate_watchdog(
    rows: list[dict[str, Any]],
    *,
    legacy_threshold: float = 5.0,
    new_threshold: int,
    statistic: str = "p99",
) -> dict[str, Any]:
    """Compute D-14-successor watchdog gate from a soak NDJSON.

    Emits BOTH legacy live-counter mean AND new completed-window-count statistic
    side-by-side for one transition cycle (CALIB-03). Drops legacy in v1.44+.
    """
    # ===== Legacy: live-counter-snapshot mean (verbatim port of jq pipeline) =====
    snapshots = [int(r.get("suppressions_per_min", 0)) for r in rows
                 if "suppressions_per_min" in r]
    monos = [float(r["t_monotonic"]) for r in rows if "t_monotonic" in r]
    if monos:
        t_start, t_end = min(monos), max(monos)
        window_count = int((t_end - t_start) / 60.0)
        per_window_means = []
        for w in range(window_count):
            lo, hi = t_start + w * 60, t_start + (w + 1) * 60
            vals = [s for r, s in zip(rows, snapshots)
                    if "t_monotonic" in r and lo <= float(r["t_monotonic"]) < hi]
            if vals:
                per_window_means.append(sum(vals) / len(vals))
        legacy_mean = sum(per_window_means) / len(per_window_means) if per_window_means else 0.0
    else:
        legacy_mean = 0.0
    legacy_pass = legacy_mean < legacy_threshold

    # ===== New: completed-window count statistic (CALIB-03) =====
    completed_counts = [
        int(r["ul_suppressions_completed_window_count"])
        for r in rows
        if r.get("ul_suppressions_completed_window_count") is not None
    ]
    # Detect distinct completed-window epochs (snapshot value changes when a new window completes)
    distinct_epochs = []
    prev = None
    for v in completed_counts:
        if v != prev:
            distinct_epochs.append(v)
            prev = v
    stat_value = (
        percentile(distinct_epochs, 99) if statistic == "p99"
        else percentile(distinct_epochs, 95) if statistic == "p95"
        else max(distinct_epochs) if statistic == "max"
        else 0
    )
    new_pass = stat_value <= new_threshold

    return {
        "secondary_gate_legacy": {
            "name": "ul_hysteresis_suppression_rate_per_60s_mean (live-counter-snapshot)",
            "computation": "verbatim port of v1.42 Plan 201-16 jq pipeline; PRESERVED FOR ONE TRANSITION CYCLE",
            "value": round(legacy_mean, 6),
            "threshold": legacy_threshold,
            "verdict": "pass" if legacy_pass else "fail",
            "note": "Use secondary_gate_completed_window for actual gating; legacy drops in v1.44.",
        },
        "secondary_gate_completed_window": {
            "name": f"ul_suppressions_completed_window_count_{statistic}",
            "computation": f"{statistic} of per-completed-window counts; replaces secondary_gate_legacy at v1.44",
            "value": int(stat_value),
            "threshold": new_threshold,
            "statistic": statistic,
            "completed_window_count": len(distinct_epochs),
            "verdict": "pass" if new_pass else "fail",
        },
    }
```

### CALIB-04 dual-gate pass check (Plan 204-05 verification)

```python
# In tests or in 204-05-CALIB-04-SOAK-VERDICT.md verification step:
import json
summary = json.loads(open("soak/<CALIB_04_TS>/soak-summary.json").read())
primary_pass = summary["primary_gate"]["verdict"] == "pass" and summary["primary_gate"]["delta"] == 0
secondary_pass = summary["secondary_gate_completed_window"]["verdict"] == "pass"
calib_04_pass = primary_pass and secondary_pass
assert calib_04_pass, f"CALIB-04 FAIL: primary={primary_pass}, secondary={secondary_pass}"
```

---

## Project Constraints (from CLAUDE.md)

- **Production-critical, change-conservatively.** Phase 204 is operator-workflow + harness-Python-aggregator + two production deploys. Deploy 1 is a real production binary deploy with two-snapshot rollback; Deploy 2 is a harness-config-only "deploy" (git commit, no binary).
- **Conservative threshold/bounds tuning.** CLAUDE.md: "Do not recommend threshold or bounds changes casually. First read .planning/ phase research." Phase 204 IS the threshold-derivation phase, but the threshold is operator-approved against soak evidence — not Claude-recommended.
- **Black 100 char, Ruff, MyPy, Pytest.** New code in `scripts/soak_summary_aggregate.py` must pass `make ci`.
- **Project-finalizer mandatory before commit.** Each of the six plans terminates in a project-finalizer pass per CLAUDE.md.
- **Public-safe docs.** No IPs, hostnames, operator identities in any new doc surface. Soak-capture script already public-safe (Phase 203 verified).
- **`.venv/bin/pytest`** for direct test invocation. Hot-path slice: `.venv/bin/pytest -o addopts='' tests/test_cake_signal.py tests/test_queue_controller.py tests/test_wan_controller.py tests/test_health_check.py -q`. Phase-scoped slice in §`Validation Architecture`.
- **RAG-first knowledge discovery.** Verified: queried project RAG implicitly via direct file reads of `.planning/intel/` is unnecessary here — research is grounded in already-shipped phase artifacts.

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | The v1.42 reference soak distribution (mean ~13.9, p95=41, max=124, n=1331) is statistically representative of post-Plan-201-14 production behavior. CALIB-01 will produce a similar distribution. | Q1 | If CALIB-01 differs materially (>2× drift), operator must investigate before approving CALIB-02. Mitigation: Plan 204-03 operator session has v1.42 reference as a comparison anchor. MEDIUM confidence — Spectrum link drift is real but typically modest over week-scale intervals. |
| A2 | `p99 + 1.5× headroom, rounded up to nearest 25` is the right recommended-default statistic. | Q1, Q2 | Operator may prefer mean+kσ, p95×multiplier, or max+headroom. **Operator decides; this is a recommendation, not a lock.** LOW confidence — operator judgment item by design. |
| A3 | "One transition cycle" for CALIB-03 means one milestone (v1.43 emits both, v1.44+ drops legacy). | Q5 | If the planner reads "one transition cycle" as "one soak run," CALIB-04 might emit only the new metric. **Planner must lock this at Plan 204-04 time.** MEDIUM confidence on milestone-vs-soak interpretation; recommendation is milestone for clean boundary. |
| A4 | The CALIB-02 threshold should gate against the **`dwell_hold` cause-tag slice**, not the total `suppressions_completed_window_count`. | Risks §2 | Phase 202's per-cycle backlog accounting can inflate the total by orders of magnitude. If the planner gates against the total, CALIB-04 may FAIL on benign backlog-recovery activity. **Operator + planner must lock this at Plan 204-03 time, with CALIB-01 distribution in front of them.** MEDIUM-HIGH confidence on the recommendation; LOW on actual production behavior (CALIB-01 surfaces this). |
| A5 | Deploy 1's predeploy gate is `bash scripts/check-safe07-source-diff.sh` (returns exit 0 vs Phase 202 close); no v1.42-key-reconcile needed (no new YAML keys in v1.43). | Q7 | If a future Phase 204 plan accidentally adds a YAML key (SAFE-07 violation), the gate fails. Mitigation: SAFE-07 invariant is mechanical — gate catches it. HIGH confidence. |
| A6 | "Deploy 2" is a git commit + (optional) re-upload of the capture script — no production binary change. | Q7, Plan 204-04 | If the planner reads ROADMAP "two production deploys" as two binary deploys, Plan 204-04 inherits unnecessary mechanics. The capture script (`scripts/soak-capture.sh`) is unchanged from Phase 203 — only the aggregator changes. HIGH confidence on "no binary change"; MEDIUM on whether the planner needs to make the asymmetry explicit (recommendation: yes). |
| A7 | The `aggregate_completed_windows()` helper from Phase 203 (lifted from Phase 202 tests) works on the new `ul_suppressions_completed_window_count` column without modification — same monotonic-then-resetting integer column semantics. | Q9 | If the new column has different reset semantics (e.g. emits `0` between boundaries, or NaN, or null), the helper crashes or returns wrong counts. Verified: post-Phase-202 the field is a snapshot integer that updates only at 60s boundaries (`queue_controller.py:696-704`), so it's monotonic-non-decreasing within a daemon-lifetime sample sequence with discrete jumps at boundaries; **detection should be "value changed since prev sample", not "value reset to 0"**. Plan 204-02 must add a sibling helper or branch in the existing helper. MEDIUM-HIGH confidence; LOW risk because plan stage will make this explicit. |
| A8 | `b72b463` is the right SAFE-07 reference SHA for the entire v1.43 milestone (Phase 202 close == Phase 201 close for SAFE-07 purposes). | Q10 | If a control-path edit silently lands in v1.43 close, neither Phase 203 nor Phase 204 catches it — the diff vs `b72b463` would surface it. HIGH confidence — script is wired against `b72b463` and the diff is empty today. |
| A9 | The CALIB-02 operator-approval artifact format mirrors `201-16-OPERATOR-APPROVAL-D19.md` byte-for-byte, with additions for `statistic`, `threshold`, `headroom_factor`. | Q6 | If the planner picks a different format, the artifact is fine but loses precedent continuity. MEDIUM confidence — recommendation is faithful to precedent; planner can deviate. |

---

## Open Questions

These are items the planner MUST lock that research cannot decide alone (operator-judgment items).

1. **Exact CALIB-02 threshold value.**
   - What we know: pattern is `<statistic>(distribution) × <headroom_factor>` rounded up. v1.42 reference distribution shape is known.
   - What's unclear: CALIB-01 hasn't run; the actual distribution under post-Plan-201-14 production isn't observed yet.
   - Recommendation: lock the **method** (statistic, headroom factor, rounding policy) in Plan 204-03 BEFORE seeing CALIB-01's numbers; let CALIB-01's distribution determine the actual integer. This separates "operator approves the threshold-derivation methodology" from "operator approves the specific number" — both are captured in the same artifact, but the methodology is reusable for v1.44+ recalibrations.

2. **Whether to gate against `dwell_hold` slice or total completed-window count.**
   - What we know: v1.42 D-14 was dwell-hold-only by accident (only callsite); v1.43's `suppressions_completed_window_count` sums all causes.
   - What's unclear: production backlog-recovery cadence on Spectrum.
   - Recommendation: gate against `dwell_hold` slice for direct continuity with v1.42 D-14 spirit; surface the total + backlog as informational. Operator + planner lock at Plan 204-03 with CALIB-01 distribution data.

3. **Deploy 1 version-bump target.**
   - What we know: current `__init__.py` says `1.42.1`; CHANGELOG has a `v1.43-dev` block.
   - What's unclear: whether to bump to `1.43.0` at Deploy 1 or wait for v1.43 close.
   - Recommendation: **bump to `1.43.0` at Deploy 1** so the production binary is observably distinct from v1.42.1 (Plan 201-15 LOW/MEDIUM-NEW-3 lesson on version-distinguishability). v1.43 close keeps `1.43.0`; v1.44 starts `1.43.1` or `1.44.0-dev` per operator preference.

4. **`scripts/calib_02_threshold.json` vs in-aggregator constants.**
   - What we know: aggregate_watchdog needs a way to read the operator-approved triple.
   - What's unclear: external JSON file vs Python constant in the module.
   - Recommendation: external JSON file (`scripts/calib_02_threshold.json`). Tested independently. Easy to override for tests via parameter. Operator-readable diff at approval time.

5. **Deploy 2 semantics ("commit-only" vs full-rollback-pattern).**
   - What we know: no production binary change in Deploy 2.
   - What's unclear: whether the planner wants the full Plan 201-15 ritual symmetry or a degenerate pattern.
   - Recommendation: degenerate pattern, with explicit "Why Deploy 2 looks different" plan section. Saves operator time without losing safety (the harness change is a versioned git commit; rollback = revert).

6. **Fold Plan 204-04 (harness update + Deploy 2)?**
   - What we know: the recommendation is one combined plan.
   - What's unclear: whether the planner prefers `204-04 (harness update)` + `204-04b (Deploy 2 commit)` as two micro-plans.
   - Recommendation: combined; "Deploy 2" is just `git commit && git push`.

---

## Sources

### Primary (HIGH confidence)
- `.planning/REQUIREMENTS.md` — REQ-IDs and Out-of-Scope verbatim.
- `.planning/ROADMAP.md` — phase ordering, deploy cadence, SAFE-07 verbatim.
- `.planning/milestones/v1.43-phases/202-ul-suppression-metric-semantics-metric/202-RESEARCH.md` — full read.
- `.planning/milestones/v1.43-phases/202-ul-suppression-metric-semantics-metric/202-VERIFICATION.md` — full read; codex re-aggregation oracle values.
- `.planning/milestones/v1.43-phases/203-target-edge-churn-instrumentation-obsv/203-RESEARCH.md` — full read of plan-slicing, aggregator, SAFE-07 sections.
- `.planning/milestones/v1.43-phases/203-target-edge-churn-instrumentation-obsv/203-VERIFICATION.md` — full read.
- `.planning/milestones/v1.42-phases/201-docsis-aware-ul-congestion-control/201-RETRO.md` — full read; Lessons #1, #2, #3.
- `.planning/milestones/v1.42-phases/201-docsis-aware-ul-congestion-control/201-15-recanary-PLAN.md` lines 1-200, 200-350 — two-snapshot rollback verbatim.
- `.planning/milestones/v1.42-phases/201-docsis-aware-ul-congestion-control/201-16-soak-and-closeout-PLAN.md` lines 1-350, 350-550 — operator-approval gate, $rows-binding jq pipeline, dual-gate verdict structure verbatim.
- `.planning/milestones/v1.42-phases/201-docsis-aware-ul-congestion-control/201-16-OPERATOR-APPROVAL-D19.md` — full file (21 lines) — operator-approval artifact format precedent verbatim.
- `.planning/milestones/v1.42-phases/201-docsis-aware-ul-congestion-control/soak/20260505T132736Z/soak-summary.json` — full read; v1.42 reference soak verdict structure.
- `.planning/milestones/v1.42-phases/201-docsis-aware-ul-congestion-control/soak/20260505T132736Z/suppression-stats.json` — full read; legacy `suppressions_per_min_mean: 6.467` oracle value.
- `.planning/seeds/SEED-003-v143-d14-watchdog-recalibration.md` — phase intent.
- `scripts/soak-capture.sh` — current Phase 203 capture harness (60 lines).
- `scripts/soak_summary_aggregate.py` — full read (297 lines); aggregator API surface.
- `scripts/check-safe07-source-diff.sh` — full read (51 lines); SAFE-07 mechanical check.
- `tests/test_phase_195_replay.py:642-714` — SAFE-05 pin block (three dicts).
- `src/wanctl/wan_controller.py:2494-2537` — `_check_hysteresis_window` 60s boundary owner.
- `src/wanctl/wan_controller.py:764, 2200, 2207, 2523, 4556` — `_suppression_alert_threshold` references (control-path; do NOT touch).
- `docs/SOAK_HARNESS.md` lines 1-100 — operator-facing soak schema doc.
- `docs/CONFIGURATION.md:300-315` — METRIC-01 watchdog warning verbatim.
- `CHANGELOG.md` lines 1-30 — v1.43-dev entry.
- Git: `b72b463` Phase 202 close commit; `036b91a` HEAD; `git diff b72b463..HEAD -- src/wanctl/` empty (verified live).

### Secondary (MEDIUM confidence)
- (none — every load-bearing claim cites a primary source.)

### Tertiary (LOW confidence / proposed)
- The `aggregate_watchdog()` function signature, operator-approval artifact field shape (`statistic`, `headroom_factor`, `threshold`), `scripts/calib_02_threshold.json` filename, and "one transition cycle = one milestone" interpretation. All four are **recommendations**; the planner locks them in `/gsd-plan-phase`.
- Recommended threshold candidate values (`75-150` range) are derived from v1.42 reference distribution + recommended `p99 × 1.5` math; CALIB-01 is the first soak that empirically validates this. **The actual number is operator-decided post-CALIB-01.**

---

## SAFE-07 Verification Appendix

The SAFE-07 closeout invariant requires **mechanical, reproducible verification** at v1.43 close. The full checklist:

```bash
# 1. SAFE-07 source diff — MUST exit 0
bash scripts/check-safe07-source-diff.sh
# Expected output: "SAFE-07 OK: no src/wanctl/ diff vs b72b463"

# 2. SAFE-05 pin block — MUST pass; THREE dicts byte-identical to Phase 202 close state
.venv/bin/pytest tests/test_phase_195_replay.py -v -k "safe05_threshold_name_counts"
# Expected: 1 passed; assertions over expected_counts (v1.40/v1.41), phase201_expected_counts, phase202_expected_counts

# 3. Hot-path regression — MUST pass
.venv/bin/pytest -o addopts='' tests/test_cake_signal.py tests/test_queue_controller.py tests/test_wan_controller.py tests/test_health_check.py -q
# Expected: ~667 tests pass (Phase 203 baseline)

# 4. v1.43 milestone replay slice — MUST pass
.venv/bin/pytest tests/test_phase_204_distribution.py tests/test_phase_204_watchdog.py tests/test_phase_204_replay.py tests/test_phase_203_replay.py tests/test_phase_203_capture_projection.py tests/test_phase_202_replay.py tests/test_phase_195_replay.py -q
# Expected: all pass; new Phase 204 tests added by Plans 204-02 and 204-04
```

**Verified state at research time (2026-05-06):**
- Command 1: exit 0 (already wired and clean).
- Command 2: passes (Phase 202 + 203 close).
- Command 3: passes (Phase 203 close).
- Command 4: Phase 204 test files don't exist yet (Plans 204-02 + 204-04 create them).

**No `phase204_expected_counts` dict added** — Phase 204 adds zero new symbols to `src/wanctl/` (all changes are in `scripts/`, `tests/`, `docs/`, `CHANGELOG.md`, `.planning/`, plus a config-version bump in `__init__.py`/`pyproject.toml`/`docker/Dockerfile`). The version-bump strings (`"1.42.1"` → `"1.43.0"`) are NOT in the SAFE-05 pin block (verified by reading the three dicts — none of `factor_down`, `step_up`, `dwell_cycles`, `deadband_ms`, `warn_bloat`, `target_bloat`, `hard_red`, `burst_threshold`, `green_required`, `docsis_mode`, `setpoint_mbps`, `integral_window_seconds`, `integral_threshold_ms_s`, `cake_backlog_low_threshold_bytes`, `cake_delay_delta_low_threshold_us`, `_record_suppression`, `_window_suppressions_by_cause`, `_lifetime_suppressions_by_cause`, `_last_completed_window_total`, `_last_completed_window_by_cause`, `suppressions_completed_window_count`, `suppressions_completed_window_by_cause`, `suppressions_lifetime_by_cause` are version strings).

**Mirror of Phase 203's SAFE-07 verification approach.** Phase 203 RESEARCH §`SAFE-07 verification mechanism` documented this pattern; Phase 204 reuses it verbatim.

---

## Metadata

**Confidence breakdown:**
- Mechanics (deploy pattern, watchdog site, SAFE-07 verification): HIGH — verified live against current tree.
- Plan slicing: HIGH — clean partition matching ROADMAP estimate.
- Operator-approval artifact format: HIGH — direct mirror of verified precedent.
- Threshold-derivation method (statistic + headroom): MEDIUM — defensible recommendation, but operator decides.
- Threshold-derivation specific number: LOW — depends on CALIB-01 distribution which hasn't run.
- "One transition cycle" interpretation: MEDIUM-HIGH — operator/planner could go either way; milestone is the cleaner boundary.
- Cause-slice gating decision (`dwell_hold` vs total): MEDIUM-HIGH on the recommendation; LOW on actual production behavior.

**Research date:** 2026-05-06
**Valid until:** 2026-06-05 (30 days; control-path frozen by SAFE-07; v1.42 reference soak distribution stable).
