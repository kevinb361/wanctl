# Phase 259: Read-Only Netwatch + Route-Ownership Inspection - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-20
**Phase:** 259-read-only-netwatch-route-ownership-inspection
**Areas discussed:** Evidence surface (INSPECT-03), Owner attribution logic (INSPECT-02), Inspection freshness, Route table scope (INSPECT-02)

---

## Evidence surface (INSPECT-03)

| Option | Description | Selected |
|--------|-------------|----------|
| New `ownership_inspection` section in `:9102/health` | Alongside `route_management`; no new port or path; INSPECT-03 "distinctly" = distinct JSON keys | ✓ |
| New `/inspect` path on `:9102` | Separate URL, same port; cleaner URL separation but adds path complexity | |
| Script/harness output only | No HTTP change; evidence as stdout/file; zero payload regression risk | |

**User's choice:** New `ownership_inspection` key in `:9102/health` alongside existing `route_management`.

---

### Follow-up: inspection enabled always vs. only when route_management enabled

| Option | Description | Selected |
|--------|-------------|----------|
| Always run, always visible | Unconditional — standalone read-only sensor, independent of mode | ✓ |
| Only when route_management.enabled=true | Matches current guard behavior; simpler but ties inspection to management subsystem | |

**User's choice:** Always runs — decoupled from route_management mode.

---

## Owner attribution logic (INSPECT-02)

| Option | Description | Selected |
|--------|-------------|----------|
| Conflict-based: netwatch if mutating, else none | observed_owner + configured_owner + match boolean | ✓ |
| Presence-based: netwatch if any entries | Broader signal, less precise | |
| Configured + live overlay: separate fields | Separate configured_owner and observed_owner | |

**User's choice:** Conflict-based with `observed_owner` / `configured_owner` / `match` triple. Current live state: Netwatch has Monitor-Spectrum + Monitor-ATT route-mutating entries → `observed_owner = "netwatch"`, `configured_owner = "netwatch"`, `match = true`. Future canary: `observed_owner = "wanctl"`, `match = true`. Intermediate/clean: `observed_owner = "none"`.

---

### Follow-up: error behavior

| Option | Description | Selected |
|--------|-------------|----------|
| `'unknown'` + `inspector_status: 'error'` | Fail gracefully; health endpoint stays up | ✓ |
| Last cached value + stale=true | Avoids sudden 'unknown' on transient blip; could mislead Phase 260 | |

**User's choice:** `observed_owner = "unknown"`, `inspector_status = "error"`, `inspector_error = <message>`. Phase 260 treats unknown as not-ready.

---

## Inspection freshness

| Option | Description | Selected |
|--------|-------------|----------|
| Background thread, 60s interval | Health endpoint serves cached result with last_inspected_at | ✓ |
| Once at startup + TTL-cached on-demand | No extra thread; inspection in health-request path | |
| Once at startup only | Simplest; stale for life of daemon | |

**User's choice:** Background daemon-thread, re-runs `RouteOwnershipGuard.inspect()` every 60s. Cached result served from health endpoint. `last_inspected_at` timestamp always included.

---

### Follow-up: thread placement

| Option | Description | Selected |
|--------|-------------|----------|
| Inside SteeringDaemon | Alongside existing health/metrics threads | ✓ |
| Standalone OwnershipInspector class | Self-contained class with own thread; same runtime placement | |
| Part of RouteManager.update() cycle | Timer-driven by steering cycle | |

**User's choice:** Spawned in `SteeringDaemon.__init__()` following same pattern as `start_steering_health_server()`.

---

## Route table scope (INSPECT-02)

| Option | Description | Selected |
|--------|-------------|----------|
| Default routes only: dst + gateway + enabled | Filter 0.0.0.0/0; extract gateway, disabled, distance, comment; include total_route_count | ✓ |
| Default routes + comment-based owner inference | Same + check route comments against configured route targets | |
| Existence check only (sanity) | Just verify non-empty; detailed extraction left to Phase 260 | |

**User's choice:** 0.0.0.0/0 filter; per-route fields: `gateway`, `disabled`, `distance`, `comment`; plus `total_route_count` from full route table. Surfaces which WAN gateways Netwatch is currently managing as enabled/disabled.

---

## Claude's Discretion

- Exact field naming within `ownership_inspection` (e.g., `netwatch.entries_count` vs `netwatch.total_entries`) — use names from the target shape in D3.
- Whether `netwatch.entries` includes full entry detail or just counts — counts are sufficient for INSPECT-01 evidence; planner can decide based on Phase 260 needs.
- Background thread interval (60s) — could be made configurable via steering.yaml if needed; start hardcoded.

## Deferred Ideas

- Route comment-based owner inference (would require checking route comments against `steering.yaml` route targets) — deferred, not needed for attribution model chosen.
- Configurable inspection interval via steering.yaml — start hardcoded at 60s; configurable later if needed.
- Route ownership transfer, Netwatch retirement, active canary — all explicitly out of scope (SAFE-21).
