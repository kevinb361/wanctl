# Phase 119: Auto-Fusion Healing - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md -- this log preserves the alternatives considered.

**Date:** 2026-03-27
**Phase:** 119-auto-fusion-healing
**Areas discussed:** Correlation metric & thresholds, RECOVERING state behavior, Healer vs operator SIGUSR1, Parameter lock mechanism

---

## Correlation Metric & Thresholds

| Option | Description | Selected |
|--------|-------------|----------|
| Tighter ratio bounds | Lower "normal" range (e.g., 0.8-1.2). Simpler, reuses existing metric | |
| Rolling Pearson correlation | Track actual signal correlation over a window. Catches cases where ratio looks OK but signals disagree on trends | ✓ |
| You decide | Claude picks based on signal data and complexity | |

**User's choice:** Rolling Pearson correlation
**Notes:** Catches the ATT scenario (ratio 0.74 looks "normal" but signals disagree on direction)

### Follow-up: Sustained period definition

| Option | Description | Selected |
|--------|-------------|----------|
| Consecutive bad readings | N consecutive cycles below threshold (e.g., 100 cycles = 5s) | |
| Time window average | Average correlation over rolling window (e.g., 60 seconds) | ✓ |
| You decide | Claude picks | |

**User's choice:** Time window average (after asking for recommendation)
**Notes:** Claude recommended option 2: 60s window at 20Hz = 1,200 samples, statistically robust, separates persistent divergence from transient hiccups

---

## RECOVERING State Behavior

| Option | Description | Selected |
|--------|-------------|----------|
| Cooldown timer | Wait fixed period (e.g., 5 min) after correlation improves | |
| Sustained good correlation | Correlation must stay above threshold for N minutes before RECOVERING -> ACTIVE | ✓ |
| Gradual weight ramp-up | Re-enable fusion but ramp icmp_weight from 1.0 toward configured blend over time | |
| You decide | Claude picks | |

**User's choice:** Sustained good correlation (after asking for recommendation)
**Notes:** Claude recommended option 2: asymmetric hysteresis (fast suspend ~1 min, slow recover ~5 min) matches controller's "fast decrease, slow increase" philosophy. False recovery more disruptive than delayed recovery.

---

## Healer vs Operator SIGUSR1

| Option | Description | Selected |
|--------|-------------|----------|
| Operator overrides healer | SIGUSR1 always wins, healer backs off until next correlation drop | |
| Healer holds, operator warned | SIGUSR1 re-enable blocked while SUSPENDED, log warning | |
| Operator overrides with healer pause | SIGUSR1 re-enable works + pauses healer for grace period (default 30 min) | ✓ |
| You decide | Claude picks | |

**User's choice:** Operator overrides with healer pause (after asking for recommendation)
**Notes:** Claude recommended option 3: operator gets immediate control, healer gets defined boundary. Grace period matches tuner's revert cooldown concept. 30 min default long enough for diagnostics, short enough to catch forgotten toggles.

---

## Parameter Lock Mechanism

| Option | Description | Selected |
|--------|-------------|----------|
| Reuse _tuning_parameter_locks | Healer calls lock_parameter() with long cooldown. Reuses existing infra but time-based model doesn't quite fit | |
| New healer_locked_params set | Separate runtime set. Clean separation but adds third locking mechanism | |
| You decide | Claude picks based on code fit and separation of concerns | ✓ |

**User's choice:** You decide
**Notes:** None

---

## Claude's Discretion

- Parameter lock mechanism choice (D-07)
- Pearson correlation implementation details
- Exact threshold defaults
- Grace period default value
- Healer module structure
- Alert message content and severity
- Health endpoint payload structure
- Test structure

## Deferred Ideas

None -- discussion stayed within phase scope
