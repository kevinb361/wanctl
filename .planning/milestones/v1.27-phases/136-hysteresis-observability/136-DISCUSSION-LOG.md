# Phase 136: Hysteresis Observability - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md -- this log preserves the alternatives considered.

**Date:** 2026-04-03
**Phase:** 136-hysteresis-observability
**Areas discussed:** Windowed rate tracking, Alert threshold + Discord, Periodic logging, Health endpoint structure

---

## Windowed Rate Tracking

| Option | Description | Selected |
|--------|-------------|----------|
| Fixed 60s window with reset | Count per window, reset at boundary. Simple, deterministic. | ✓ |
| Sliding window (deque) | Store timestamps, count within 60s. Smoother but more memory. | |
| EWMA rate | Exponentially weighted. Robust but hard to interpret. | |

**User's choice:** Fixed 60s window with reset

---

## Alert Threshold

| Option | Description | Selected |
|--------|-------------|----------|
| Configurable, default 20/min | YAML-configurable. 20/min = ~1.7% of cycles. SIGUSR1 reloadable. | ✓ |
| Configurable, default 10/min | More sensitive. May fire during normal jitter. | |

**User's choice:** Default 20/min

### Follow-up: Sustained Exceedance

| Option | Description | Selected |
|--------|-------------|----------|
| Single window exceeds | Fire on first window > threshold. AlertEngine cooldown prevents spam. | ✓ |
| 2 consecutive windows | Require 2 back-to-back. Adds 60s delay. | |

**User's choice:** Single window exceeds threshold

---

## Periodic Logging

| Option | Description | Selected |
|--------|-------------|----------|
| Every window during congestion | Log at 60s reset, only when YELLOW+ during that window. Clean logs. | ✓ |
| Every window unconditionally | Always log. Noisy during idle. | |
| Only when threshold exceeded | Minimal but misses normal rates for tuning. | |

**User's choice:** Every window boundary during congestion

---

## Health Endpoint Structure

| Option | Description | Selected |
|--------|-------------|----------|
| Extend existing hysteresis section | Add windowed fields alongside cumulative. Co-located. | ✓ |
| New top-level section | Separate suppression_monitor. Cleaner but fragments data. | |

**User's choice:** Extend existing hysteresis section

---

## Claude's Discretion

- Congestion tracking method (boolean flag vs cycle count)
- Log message format
- Clock source for window_start
- AlertEngine cooldown duration

## Deferred Ideas

None -- discussion stayed within phase scope
