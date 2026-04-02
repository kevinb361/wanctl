# Phase 123: Hysteresis Observability - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-03-31
**Phase:** 123-hysteresis-observability
**Areas discussed:** Health JSON structure, Suppression log verbosity, Counter scope

---

## Health JSON Structure

| Option | Description | Selected |
|--------|-------------|----------|
| Per-direction nested | Add hysteresis sub-dict inside download{} and upload{} — matches existing per-direction state/rate pattern | ✓ |
| Per-WAN section | Single hysteresis{} section per WAN like fusion/tuning, combined counters | |
| Top-level minimal | Just dwell_counter and transitions_suppressed, omit config values | |

**User's choice:** Per-direction nested
**Notes:** Consistent with how download/upload already carry their own state and rate. Config values included so operators don't need to cross-reference YAML.

---

## Suppression Log Verbosity

| Option | Description | Selected |
|--------|-------------|----------|
| Every suppressed cycle | DEBUG per absorbed cycle, INFO on dwell expiry with confirmed transition | ✓ |
| Only on dwell expiry | INFO only when transition fires, quieter but less visibility | |
| Both levels with reset | DEBUG per cycle + INFO on both expiry and reset (transient absorbed) | |

**User's choice:** Every suppressed cycle at DEBUG, dwell expiry at INFO
**Notes:** Matches OBSV-02 requirement text. Quiet at default log level, full visibility at DEBUG.

---

## Counter Scope

| Option | Description | Selected |
|--------|-------------|----------|
| Per-direction, since startup | Each QueueController tracks own counter, resets on restart | ✓ |
| Per-direction, persistent | Save to state JSON, survives restarts | |
| Combined per-WAN | Single counter for both directions | |

**User's choice:** Per-direction, since startup
**Notes:** No persistence needed — restarts are rare and Prometheus handles long-term. Per-direction matches health structure choice.

---

## Claude's Discretion

- Helper method vs inline for health dict construction
- Exact log message formatting details

## Deferred Ideas

None
