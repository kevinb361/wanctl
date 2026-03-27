# Phase 120: Adaptive Rate Step Tuning - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md -- this log preserves the alternatives considered.

**Date:** 2026-03-27
**Phase:** 120-adaptive-rate-step-tuning
**Areas discussed:** Episode detection, Oscillation lockout mechanism, Layer placement, Per-direction handling

---

## Episode Detection

| Option | Description | Selected |
|--------|-------------|----------|
| State transition parsing | Scan wanctl_state 1m time series for transitions, extract discrete episodes with start/end/duration | |
| Rate-based heuristics | Measure aggregate recovery speed, overshoot rates without per-episode granularity | |
| You decide | Claude picks based on what 1m metric stream supports and strategy complexity | ✓ |

**User's choice:** You decide
**Notes:** None

---

## Oscillation Lockout Mechanism

| Option | Description | Selected |
|--------|-------------|----------|
| Reuse _parameter_locks with long cooldown | Lock all 3 response params via lock_parameter() with long cooldown (e.g., 6 hours). Unfreezes automatically. | |
| New oscillation freeze state | Separate boolean flag, unfreezes when transitions/minute drops below threshold for sustained period | |
| You decide | Claude picks based on code fit and unfreeze semantics | ✓ |

**User's choice:** You decide
**Notes:** Hard constraint: must fire Discord alert via AlertEngine when triggered

---

## Layer Placement

| Option | Description | Selected |
|--------|-------------|----------|
| New 5th RESPONSE_LAYER | Clean separation, extends rotation from 4 to 5 hours per full cycle | |
| Extend ADVANCED_LAYER | Keeps 4-hour cycle but ADVANCED becomes crowded (7 strategies) | |
| You decide | Claude picks based on tuning cadence impact and separation of concerns | ✓ |

**User's choice:** You decide
**Notes:** None

---

## Per-Direction Handling

| Option | Description | Selected |
|--------|-------------|----------|
| 6 separate parameters | step_up_dl/ul, factor_down_dl/ul, green_required_dl/ul. Max flexibility, doubles parameter space | |
| 3 paired with fixed ratio | Tune one value, derive other direction via ratio. Simpler, assumes constant DL/UL relationship | |
| Download-only tuning | Only tune DL response params, leave UL at static config. Reduces scope by half | |
| You decide | Claude picks based on blast radius management and existing config structure | ✓ |

**User's choice:** You decide
**Notes:** None

---

## Claude's Discretion

All 4 decisions deferred to Claude's judgment:
- D-01: Episode detection approach
- D-02: Oscillation lockout mechanism and unfreeze logic
- D-03: Layer placement in rotation
- D-04: Per-direction parameter handling

## Deferred Ideas

None -- discussion stayed within phase scope
