# Phase 207: Soak / harness hardening (v1.43 closeout-routed) - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-15
**Phase:** 207-soak-harness-hardening-v1-43-closeout-routed
**Areas discussed:** HRDN-04 YAML promotion, HRDN-01 verifier scope, HRDN-02 transient-failure shape, HRDN-03 legacy cleanup scope, plan slicing

---

## Gray-area selection

User was offered 4 gray areas (HRDN-01..04). User clarified the question once, then replied **"you decide."** All four areas + plan slicing were resolved by Claude under explicit delegation.

---

## HRDN-04 — CALIB-02 YAML promotion YES/NO

| Option | Description | Selected |
|--------|-------------|----------|
| YES — promote to YAML | Expose `continuous_monitoring.upload.calib_02_threshold` with restart-required semantics, autorate validator schema entry, default 175 matching JSON file | |
| NO — keep JSON-file convention | Rationale recorded in CHANGELOG referencing CALIB-04 PASS evidence; defer deep schema-design work to T17(b) | ✓ |

**Claude's choice:** NO.
**Rationale:** SEED-005 outcomes are required input for the knob-shape design (per REQUIREMENTS.md T17(b) gate). Premature YAML promotion would lock restart-required semantics + validator schema before operational signal exists. CALIB-04 PASS at threshold 175 (soak `20260512T004208Z`) is already in production; no pressure to expose. Lowest-risk, fully-reversible closeout. T17(b) revisits when SEED-005 informs.

---

## HRDN-01 — Verifier scope + SAFE-07 vs SAFE-09 rebadge

| Option | Description | Selected |
|--------|-------------|----------|
| Surgical fail-closed extension | Add uncommitted/staged check; keep SAFE-07 messaging; leave SAFE-09 rebadge to Phase 209 | ✓ |
| Full SAFE-09 rebadge + ATT-config whitelist in this phase | Rename script, update messaging, add Phase 209's whitelist mode now | |
| Two scripts (SAFE-07 + SAFE-09 separate) | Keep existing for v1.43 closeout, add new for v1.44 | |

**Claude's choice:** Surgical fail-closed extension.
**Rationale:** Phase 209 ROADMAP entry explicitly owns SAFE-09 closeout + ATT-config whitelist mode. Spreading the rebadge across phases makes Phase 209's diff harder to audit. HRDN-01's contract is "manual verifier compensation no longer required" — that's purely the dirty-tree pre-check.

---

## HRDN-02 — Transient-failure tolerance shape

| Option | Description | Selected |
|--------|-------------|----------|
| Per-row bypass, lifetime rate cap, sidecar TSV | `|| true` per row, distinct failure-mode counters, threshold env-var configurable, abort with breakdown | ✓ |
| Sentinel NDJSON row | Insert failure marker rows directly into soak-capture.ndjson | |
| Per-minute window cap | Sliding window rather than lifetime cap | |

**Claude's choice:** Per-row bypass + lifetime rate cap + sidecar TSV.
**Rationale:** NDJSON schema cleanliness (sidecar TSV doesn't pollute aggregator input). Lifetime cap matches the operational question ("did this 24h soak produce trustworthy stats?"). Distinct mode counters give postmortem signal without complicating the threshold logic. `MIN_SAMPLES_BEFORE_EVAL=60` guard prevents first-minute spurious abort. Default `0.01` (1%) tolerates 864 missed rows out of 86400 — generous but bounded.

---

## HRDN-03 — Legacy gate cleanup scope

| Option | Description | Selected |
|--------|-------------|----------|
| Retire TestV142WatchdogRegression + sweep all 5 sites atomically | Remove `secondary_gate_legacy` end-to-end, add positive-removal contract test, atomic commit | ✓ |
| Rewrite TestV142WatchdogRegression against new contract | Keep test name, change assertions | |
| Sweep only code, leave docs for later | Just aggregator + tests, defer SOAK_HARNESS.md / CHANGELOG.md | |

**Claude's choice:** Retire + atomic sweep of all 5 sites.
**Rationale:** CHANGELOG line 29 already promised "drops in v1.44" — keep promise literally. Rewriting the test keeps a stale class name for a contract that no longer exists. Atomic commit means no transient state where docs and code disagree. 5 sites identified: `scripts/soak_summary_aggregate.py` (lines 290, 360, 377, 476), `tests/test_phase_204_watchdog.py` (TestV142WatchdogRegression), `tests/test_phase_204_replay.py` (lines 53-55), `docs/SOAK_HARNESS.md` (lines 175-207), `CHANGELOG.md` (line 29 → past-tense v1.44 entry).

---

## Plan slicing (recommendation to gsd-planner)

**Claude's recommendation:** 5 plans
- `207-01` HRDN-01 — verifier fail-closed extension
- `207-02` HRDN-02 — soak-capture transient tolerance
- `207-03` HRDN-03 — atomic legacy-gate sweep across 5 sites
- `207-04` HRDN-04 — CHANGELOG entry documenting NO decision
- `207-05` SAFE-09 phase-boundary verification (zero `src/wanctl/` diff confirmed)

Planner has final say on slicing.

---

## Claude's Discretion

User invoked discuss-phase, was offered four gray areas, then replied "you decide" after clarifying once. All decisions in CONTEXT.md `<decisions>` (D-01 through D-16) are Claude's calls under explicit delegation. User should review CONTEXT.md before `/gsd-plan-phase 207` and override by editing if any call is wrong.

## Deferred Ideas

- T17(b) CALIB-02 YAML knob shape evaluation — REQUIREMENTS.md future requirements; gated on SEED-005.
- SAFE-09 verifier rebadge + ATT-config whitelist mode — Phase 209.
- T6/T7 storage-hygiene CAKE tin skip-on-unchanged consumer audit — REQUIREMENTS.md future requirements.
- SEED-005 conservative UL tuning sweep — REQUIREMENTS.md future requirements; gates T17(b).
