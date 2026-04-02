# Phase 127: DL Parameter Sweep - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-02
**Phase:** 127-dl-parameter-sweep
**Areas discussed:** Test ordering, Test conditions, Results documentation, Config change method

---

## Test Ordering

| Option | Description | Selected |
|--------|-------------|----------|
| Same as original | factor_down_yellow → green_required → step_up → factor_down → dwell → deadband → target_bloat → warn_bloat → hard_red_bloat | ✓ |
| Thresholds first | Start with state boundary definitions, then response factors | |
| Impact order | Start with largest A/B deltas from original sweep | |

**User's choice:** "what do you think" → Claude recommended same as original
**Notes:** Enables direct comparison with REST results. Confirmation pass in Phase 129 catches interaction issues.

---

## Test Conditions

| Option | Description | Selected |
|--------|-------------|----------|
| Evening prime-time | 7-10pm, realistic congestion | |
| Late night / early morning | Cleaner baseline, less noise | |
| Consistent window, any time | Pick a window and stick to it | |

**User's choice:** "I want to run it asap" — no waiting for specific window
**Notes:** Document time of day with each result. Afternoon cable plant conditions expected.

### Follow-up: Runs per test

| Option | Description | Selected |
|--------|-------------|----------|
| 1 run each | Quick, 2 runs per A/B pair | |
| 2 runs each | More confidence, doubles time | |
| 1 run, re-test if close | Adaptive — re-run on <5% delta | ✓ |

**User's choice:** "what do you think" → Claude recommended adaptive approach

---

## Results Documentation

| Option | Description | Selected |
|--------|-------------|----------|
| Cable tuning guide (existing) | Update docs/CABLE_TUNING_GUIDE.md with linux-cake section | ✓ |
| New linux-cake results doc | Separate docs/LINUX_CAKE_TUNING.md | |
| .planning/ findings doc | Phase artifacts, move to docs later | |

**User's choice:** "what do you think" → Claude recommended existing guide
**Notes:** Original REST results stay as historical. New section for linux-cake.

---

## Config Change Method

| Option | Description | Selected |
|--------|-------------|----------|
| YAML edit + SIGUSR1 | SSH to VM, edit YAML, reload via signal | ✓ |
| Tuner DB override | Override via metrics.db tuning_params table | |
| Script the changes | Helper script for sed + SIGUSR1 | |

**User's choice:** YAML edit + SIGUSR1

---

## Claude's Discretion

- flent command-line flags and test duration
- A/B results table structure
- Raw flent data path inclusion in docs

## Deferred Ideas

None — discussion stayed within phase scope.
