# Phase 259: Read-Only Netwatch + Route-Ownership Inspection - Research

**Researched:** 2026-06-20
**Domain:** Python steering daemon — background-thread sensor + health-endpoint section assembly over an existing read-only RouterOS REST client
**Confidence:** HIGH (all findings VERIFIED by direct codebase read of the exact files named in CONTEXT.md)

## Summary

Phase 259 is a pure-additive, in-repo Python feature with no new external packages and no RouterOS mutation. Every primitive it needs already exists in the codebase and was proven live in Phase 258: `RouteOwnershipGuard.inspect()` reads Netwatch+script state and returns a structured conflict verdict; `RouterOSREST._handle_route_print()` / `_handle_netwatch_print()` / `_handle_script_print()` serve the three GET-only reads; `readonly_validator.validate_command()` enforces the read-only boundary; `SteeringHealthHandler._build_route_management_section()` is the exact template for a new `_build_ownership_inspection_section()`; and `start_steering_health_server()` is the exact daemon-thread lifecycle template for a new background inspection thread.

The work is three thin layers: (1) a small inspection layer that wraps `RouteOwnershipGuard.inspect()` plus a default-route (`0.0.0.0/0`) read to compute `observed_owner` + Netwatch summary + route summary into a cached, lock-protected dataclass/dict; (2) a 60s background daemon-thread that re-runs the inspection and writes the cache, spawned in `SteeringDaemon.__init__()` and shut down in `_cleanup_steering_daemon()`; (3) health wiring that adds a new top-level `ownership_inspection` key to `get_health_data()` and a `_build_ownership_inspection_section()` builder, both strictly additive so the existing `route_management` shape never regresses.

**The one non-obvious gotcha:** D2 (always-runs, independent of `route_management` mode) means the inspection path **cannot** reuse the `_init_route_management()`-gated guard. `_init_route_management()` only constructs `RouteOwnershipGuard` when `route_management_enabled AND mode != "off"` (daemon.py:1212-1215). In the current production deployment that gate may be off. The inspection thread must construct its **own** `RouteOwnershipGuard(self.router.client)` unconditionally, decoupled from `self.route_ownership_guard`.

**Primary recommendation:** Add a `RouteOwnershipInspector` (new module under `src/wanctl/steering/`) that owns a `threading.Lock`-protected cached result and a `refresh()` method; spawn its 60s loop as a `daemon=True` thread in `SteeringDaemon.__init__()` using the `start_steering_health_server()` lifecycle pattern; expose the cached result via a new `ownership_inspection` key in `get_health_data()`; render it via a new strictly-additive `_build_ownership_inspection_section()` in `health.py`. Mirror `scripts/phase258-readonly-proof.py` for the `INSPECT_PROOF_PASS` live harness.

## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D1 — New `ownership_inspection` section in `:9102/health`:** Add a new top-level key `ownership_inspection` **alongside (not inside)** the existing `route_management` section. The existing `:9102/health` payload shape must not regress — existing fields under `route_management` remain unchanged.
- **D2 — Always runs, always visible, independent of route_management mode:** `ownership_inspection` runs unconditionally — a standalone read-only sensor. Even when `route_management.enabled = false` or `mode = "off"`, the section appears in health output.
- **D3 — Conflict-based attribution with configured/observed pair:** Three fields — `observed_owner` (`"netwatch"` if any enabled Netwatch entries reference route-mutating scripts; `"wanctl"` if `route_management.mode == "active"` AND guard clean; `"none"` if no route-mutating Netwatch entries AND wanctl not active; `"unknown"` on error), `configured_owner` (the `active_owner` from `route_management` status), and `match` (boolean equality). `match` is Phase 260's primary discrepancy signal.
- **D4 — Fail-open on error:** On RouterOS inspection failure: `observed_owner = "unknown"`, `inspector_status = "error"`, `inspector_error = <message>`. Health endpoint stays up.
- **D5 — Background thread, 60s refresh interval:** A background daemon-thread re-runs `RouteOwnershipGuard.inspect()` every 60s. Health endpoint always serves cached result (never blocks). `last_inspected_at` ISO 8601 UTC timestamp included.
- **D6 — Thread lives in SteeringDaemon:** Spawned in `SteeringDaemon.__init__()` alongside existing health/metrics threads (same pattern as `start_steering_health_server()`). Uses the daemon's existing router client. No new process/service.
- **D7 — Default routes only, with per-route fields:** Filter `/ip/route/print` to `0.0.0.0/0` routes only. Extract per-route `gateway`, `disabled` (bool), `distance`, `comment`. Surface `total_route_count` (17 in Phase 258 proof). Populate `ownership_inspection.routes.default_routes[]` and `ownership_inspection.routes.total_route_count`.
- **SAFE-21:** All work read-only — GET-only REST calls through the Phase 258 handlers and route-print. No RouterOS mutation, Netwatch disablement, CAKE/qdisc change, or route-owner flip. `readonly_validator.py` remains the enforcement layer.

### Claude's Discretion

The CONTEXT.md `<specifics>` block pins the exact health JSON shape and behaviors (ISO 8601 UTC `last_inspected_at` via `datetime.now(UTC).isoformat()`, `match = observed_owner == configured_owner` with `match=false` always when `observed_owner="unknown"`, harness modeled on `scripts/phase258-readonly-proof.py`). Implementation structure (new module vs. method, dataclass vs. dict cache) is discretionary as long as the pinned shape and behaviors hold.

### Deferred Ideas (OUT OF SCOPE)

- Route-ownership documentation, ownership-transfer design, and Netwatch retirement (`2026-06-18-route-ownership-netwatch-to-wanctl-failover.md`) — Phase 259 produces inspection evidence + `match` signal only; the transfer decision is a future milestone.
- Steering-degraded-on-clean-restart (`2026-04-17-...`) — separate issue, out of scope.

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| INSPECT-01 | wanctl reads live RouterOS Netwatch state and surfaces it as ownership-inspection evidence | `RouteOwnershipGuard.inspect()` already reads `/tool netwatch print detail` via `_handle_netwatch_print` (proven live Phase 258: `netwatch=3`). Surface `netwatch.entries_count` + `route_mutating_active_count` from guard internals. |
| INSPECT-02 | wanctl reads live default-route/route-ownership state and attributes owner (Netwatch/wanctl/none) | `_handle_route_print()` serves `/ip/route` (proven live: `route=17`). Filter `dst-address == "0.0.0.0/0"`. `observed_owner` derived per D3 from guard conflict result + route_manager mode. |
| INSPECT-03 | Ownership-inspection output distinct from `:9101` bridge + `:9102` route_management, no payload-shape regression | New top-level `ownership_inspection` key in `:9102/health`, separate from `route_management`. Strictly additive — `_build_route_management_section()` untouched. `:9101` is a different process (cake-autorate bridge), already separate. |
| SAFE-21 | No RouterOS mutation/Netwatch/CAKE/route-owner change | All reads go through GET-only REST handlers; `readonly_validator.validate_command()` rejects mutating verbs. The three commands (`/ip route print`, `/tool netwatch print detail`, `/system script print detail`) are all on the validator allowlist. |

## Project Constraints (from CLAUDE.md)

- **Production network control system — change conservatively.** Never refactor core logic/algorithms/thresholds/timing without approval. Phase 259 is purely additive; do not touch the control path, `route_manager.plan_or_apply`, or any mutation code.
- **Priority: stability > safety > clarity > elegance.**
- **Portable controller architecture:** deployment-specific behavior belongs in YAML, not Python branching. The inspector must be link-agnostic (no Spectrum/ATT hardcoding — derive route owner from live state + config, not branches).
- **Health/observability paths are part of the contract — do not break payload shape casually.** This is exactly why D1/D3 mandate a *new* key rather than mutating `route_management`.
- **Dev commands:** `.venv/bin/pytest tests/ -v`, `.venv/bin/ruff check src/ tests/`, `.venv/bin/mypy src/wanctl/`, `.venv/bin/ruff format src/ tests/`. Hot-path slice exists but is not relevant here.
- **Commit gate:** run `project-finalizer` before commit; Conventional Commits enforced by hook; `.planning` is gitignored-but-tracked → stage with `git add -f` + `SKIP_DOC_CHECK=1` if needed (per project memory).
- **Project CLAUDE.md is public-safe:** no real IPs/hostnames in committed code or docs. Note: Phase 258 evidence already contains a live gateway IP `70.123.224.1` in `.planning` (gitignored), but harness output redaction (`_redacted_sample`) should be preserved for the Phase 259 proof.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Live Netwatch read | RouterOS REST client (`routeros_rest.py`) | — | GET `/rest/tool/netwatch`; already implemented + proven Phase 258 |
| Live default-route read | RouterOS REST client | — | GET `/rest/ip/route`; `_handle_route_print()` exists |
| Conflict detection / owner attribution | Steering daemon (inspection layer) | `route_ownership_guard.py` | Reuse `RouteOwnershipGuard.inspect()`; new code computes `observed_owner` |
| 60s refresh loop + cache | Steering daemon (background thread) | — | Daemon owns thread lifecycle; mirrors health server thread |
| Read-only command enforcement | `readonly_validator.py` | — | Allowlist boundary; unchanged |
| Health-endpoint rendering | Steering health handler (`health.py`) | — | New `_build_ownership_inspection_section()`; serves cached result only |
| Live proof | standalone script (`scripts/`) | — | Mirrors `phase258-readonly-proof.py` |

## Standard Stack

No new packages. Everything is stdlib or already-vendored.

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `threading` (stdlib) | py3.11 | `Thread(daemon=True)`, `Lock`, `Event` for the 60s refresh loop + cached-state guard | Already the daemon's threading model (`health.py:572`, `daemon.py:2460`) |
| `datetime` (stdlib) | py3.11 | `datetime.now(UTC).isoformat()` for `last_inspected_at` | Already imported in `health.py:19`; CONTEXT pins this exact call |
| `json` (stdlib) | py3.11 | Parse REST JSON output of `run_cmd` | Already used by guard + route_manager |
| `requests` | (vendored, in use) | REST transport inside `RouterOSREST` | Already the transport; not touched directly by Phase 259 |

**Installation:** none. `[VERIFIED: codebase imports]` — `requests` is already a dependency; all others are stdlib.

### Supporting (existing code to reuse, not install)
| Component | File | Purpose | Reuse mode |
|-----------|------|---------|------------|
| `RouteOwnershipGuard.inspect()` | `steering/route_ownership_guard.py:69` | Netwatch+script conflict verdict → `RouteOwnershipGuardResult(status, active_allowed, owner, conflicts, error)` | Wrap, do not modify |
| `RouterOSREST._handle_route_print` | `routeros_rest.py:617` | `/ip/route` GET, optional `where` filter | Call via `run_cmd("/ip route print")` |
| `readonly_validator.validate_command` | `readonly_validator.py:78` | Read-only allowlist gate | Call before each `run_cmd` in the proof harness |
| `start_steering_health_server` | `steering/health.py:551` | Daemon-thread lifecycle template | Pattern source for inspection thread |
| `_build_route_management_section` | `steering/health.py:353` | Section-builder template | Pattern source for `_build_ownership_inspection_section` |
| `self.router.client` | `daemon.py:834` (`RouterOSController`) | Shared REST client (`get_router_client_with_failover`) | Inspector reuses this client |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Reusing `self.route_ownership_guard` (the `_init_route_management()` one) | Construct a dedicated `RouteOwnershipGuard(self.router.client)` in the inspector | **MUST use dedicated** — the route-management guard is `None` unless `enabled AND mode != off` (daemon.py:1193, 1212-1215). D2 requires unconditional inspection. |
| Threading the inspector lifecycle via `start_steering_health_server`-style module-level class state | Inspector as a daemon-owned instance with `start()`/`stop()` | Instance-owned is cleaner here (one daemon, one inspector); the health server uses class-level state because `BaseHTTPRequestHandler` is instantiated per-request — that constraint does not apply to a plain worker thread. |
| Computing `observed_owner` inside `RouteOwnershipGuard` | Compute in the new inspection layer | Keep the guard's contract frozen (it is consumed by `route_manager` + existing tests). Add the D3 attribution in new code. |

## Package Legitimacy Audit

> No external packages are installed by this phase. All dependencies are Python stdlib or already-vendored (`requests`). slopcheck/registry verification is **not applicable** — there is nothing to install.

| Package | Registry | Disposition |
|---------|----------|-------------|
| (none) | — | N/A — stdlib + existing `requests` only |

## Architecture Patterns

### System Architecture Diagram

```
                    SteeringDaemon.__init__()
                            │
            ┌───────────────┼────────────────────────┐
            │               │                         │
   _init_route_management   │             (NEW) RouteOwnershipInspector
   (gated: enabled+mode)    │              ├─ owns RouteOwnershipGuard(router.client)   ← UNCONDITIONAL
            │               │              ├─ threading.Lock-protected cached result
   self.route_manager       │              └─ start() → daemon Thread(60s loop)
   self.route_ownership_    │                         │
     guard (may be None)    │                         ▼
            │               │              every 60s: refresh()
            │               │                ├─ guard.inspect()  ── GET /tool/netwatch  (read-only)
            │               │                │                   └─ GET /system/script  (read-only)
            │               │                ├─ run_cmd("/ip route print") ── GET /ip/route (read-only)
            │               │                ├─ filter dst-address == 0.0.0.0/0
            │               │                ├─ compute observed_owner / configured_owner / match (D3)
            │               │                └─ write cache (under Lock) + last_inspected_at
            │               │                         │
            ▼               ▼                         ▼
   get_health_data() ──────────────────────► reads cache (under Lock)
       │  returns dict with keys:
       │   "route_management": route_manager.status_snapshot()   ← UNCHANGED
       │   "ownership_inspection": inspector.snapshot()          ← NEW KEY
       ▼
   GET :9102/health
       │  SteeringHealthHandler._populate_daemon_health()
       │   health["route_management"] = _build_route_management_section(hd)   ← UNCHANGED
       │   health["ownership_inspection"] = _build_ownership_inspection_section(hd)  ← NEW
       ▼
   JSON response (additive; existing shape preserved)

   :9101  ── cake-autorate bridge health (SEPARATE PROCESS) ── untouched
```

Data flow trace (primary use case): a monitoring `curl :9102/health` → handler reads `daemon.get_health_data()` → `ownership_inspection` key holds the last cached `refresh()` result (≤60s old) → never triggers a live RouterOS call on the request path.

### Recommended Project Structure (additive)
```
src/wanctl/steering/
├── route_ownership_inspector.py   # NEW: RouteOwnershipInspector + cached dataclass + refresh()
├── route_ownership_guard.py       # UNCHANGED (reused)
├── daemon.py                      # +construct/start/stop inspector; +ownership_inspection key in get_health_data()
└── health.py                      # +_build_ownership_inspection_section(); +call in _populate_daemon_health()
scripts/
└── phase259-ownership-proof.py    # NEW: live INSPECT_PROOF_PASS harness (mirror phase258)
tests/
├── test_route_ownership_inspector.py            # NEW: unit tests for attribution + fail-open
├── test_route_ownership_inspector_rest.py       # NEW: over-mocked-REST integration (mirror 258 integration)
└── test_phase259_ownership_proof.py             # NEW: harness mock + mutation-rejection (mirror 258 proof test)
```

### Pattern 1: Daemon background thread (60s loop with clean shutdown)
**What:** A `daemon=True` worker thread that loops on `shutdown_event.wait(60)` and calls `refresh()`.
**When:** D5/D6 — the 60s inspection refresh.
**Example (mirrors the existing health-server thread + daemon-loop sleep idiom):**
```python
# Pattern source: steering/health.py:572 (Thread(daemon=True)) +
#                 steering/daemon.py:2562 (shutdown_event.wait(timeout=sleep_time))
import threading

class RouteOwnershipInspector:
    def __init__(self, router_client, route_manager, *, interval_sec: float = 60.0, logger=None):
        self._guard = RouteOwnershipGuard(router_client)   # dedicated, unconditional (D2)
        self._router_client = router_client
        self._route_manager = route_manager
        self._interval = interval_sec
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._cached: dict = self._initial_snapshot()      # serve "starting" until first refresh

    def start(self) -> None:
        self.refresh()  # populate cache once synchronously so health is immediately meaningful
        self._thread = threading.Thread(
            target=self._loop, daemon=True, name="ownership-inspection"
        )
        self._thread.start()

    def _loop(self) -> None:
        while not self._stop.is_set():
            if self._stop.wait(self._interval):  # wakes early on shutdown
                break
            self.refresh()

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=5.0)

    def snapshot(self) -> dict:
        with self._lock:
            return dict(self._cached)  # shallow copy out under lock
```

### Pattern 2: Thread-safe cached-state write/read under a Lock
**What:** `refresh()` builds a fresh dict, then swaps it under the lock; readers copy out under the same lock.
**Why:** `get_health_data()` runs on the HTTP handler thread; `refresh()` runs on the inspection thread. The codebase already has multiple `threading.Lock` consumers (`metrics.py`, `storage/writer.py`, `webhook_delivery.py`).
**Example:**
```python
    def refresh(self) -> None:
        result = self._compute()  # does all the I/O OUTSIDE the lock
        with self._lock:
            self._cached = result
```

### Pattern 3: D3 owner attribution (fail-open)
**What:** Derive `observed_owner` from the guard verdict + route_manager mode; never raise.
**Example:**
```python
# observed_owner rules (CONTEXT D3):
def _observed_owner(guard_result, route_mode: str) -> str:
    if guard_result.status == "error":
        return "unknown"
    if guard_result.status == "conflict":   # enabled Netwatch references route-mutating script
        return "netwatch"
    # status == "ok": no route-mutating Netwatch entries
    if route_mode == "active" and guard_result.active_allowed:
        return "wanctl"
    return "none"   # current dry_run / off deployment yields "none"

# configured_owner = route_manager.status_snapshot()["active_owner"]
#   (route_manager._active_owner(): "netwatch" when mode != active — daemon.py route_manager.py:398-403)
# match = (observed_owner == configured_owner) and observed_owner != "unknown"
```

### Pattern 4: Default-route filter (D7)
**What:** Read full route table, filter `dst-address == "0.0.0.0/0"`, project the four fields + total count.
**Example:**
```python
# run_cmd returns (rc, json_string, err); _handle_route_print serves /ip/route GET
rc, out, err = self._router_client.run_cmd("/ip route print", capture=True, timeout=5)
routes = json.loads(out or "[]")          # list[dict]; Phase 258 live proof: 17 entries
total = len(routes)
default_routes = [
    {
        "gateway": r.get("gateway"),
        "disabled": _routeros_bool(r.get("disabled", False)),  # "true"/"false" strings
        "distance": _coerce_int(r.get("distance")),
        "comment": r.get("comment"),
    }
    for r in routes
    if r.get("dst-address") == "0.0.0.0/0"
]
```
**Note on REST shape `[VERIFIED: routeros_rest.py + Phase 258 live proof]`:** RouterOS REST returns booleans as the strings `"true"`/`"false"` (Phase 258 sample: `"disabled": "false"`, `"disabled": "true"`). `distance` may come back as a string. Reuse the existing `_routeros_bool` idiom (`route_manager.py:433`, `routeros_rest.py:734`) and coerce `distance` defensively. Live default-route sample from Phase 258: `{".id":"*8000002C","comment":"Spectrum","disabled":"false","dst-address":"0.0.0.0/0","gateway":"70.123.224.1"}`.

### Anti-Patterns to Avoid
- **Reusing `self.route_ownership_guard`** — it is `None` unless route-management is enabled+non-off. Construct a dedicated guard (D2). `[VERIFIED: daemon.py:1193, 1212-1215]`
- **Calling RouterOS on the health-request path** — D5 mandates cached-only reads; the HTTP handler must never block on `run_cmd`.
- **Mutating `route_management`'s dict or `_build_route_management_section`** — INSPECT-03 + CLAUDE.md forbid payload-shape regression. Add a *sibling* key only.
- **Letting `refresh()` raise** — D4 fail-open: any exception → `inspector_status="error"`, `observed_owner="unknown"`, cache stays serveable.
- **Holding the lock during I/O** — do all `run_cmd`/`inspect()` work outside the lock; only the dict swap is locked.
- **Re-deriving `configured_owner` independently** — pull it from `route_manager.status_snapshot()["active_owner"]` so observed/configured share one source of truth.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Netwatch/script conflict detection | New regex/JSON parser | `RouteOwnershipGuard.inspect()` | Already handles disabled entries, inline scripts, `/system script run X` references, route-mutation regex, fail-closed parse errors (`route_ownership_guard.py`) |
| Read-only command enforcement | New allowlist | `readonly_validator.validate_command()` | Anchored-prefix allowlist + forbidden-action gate, hardened in Phase 258 (`258-03-SUMMARY` mentions prefix-boundary fix) |
| RouterOS REST GET dispatch | New HTTP client | `RouterOSREST.run_cmd` via `self.router.client` | Handles auth, SSL-warning suppression, retry/backoff, JSON serialization |
| Daemon-thread lifecycle | New thread mgmt | `start_steering_health_server` pattern + `_cleanup_steering_daemon` ordering | Proven shutdown ordering (state → health → router → metrics → locks) |
| Health section assembly | Inline dict in handler | `_build_*_section(health_data)` method pattern | Consistent with all 10+ existing section builders; testable in isolation |
| RouterOS bool parsing | `bool(r["disabled"])` | `_routeros_bool()` idiom | REST returns `"true"`/`"false"` strings, not JSON booleans |

**Key insight:** Phase 259 is almost entirely *composition* of Phase-258-proven parts. The genuinely new logic is ~40 lines of D3 attribution + D7 route projection + the cache/thread shell. Treat anything larger as a smell.

## Runtime State Inventory

> Phase 259 is additive Python on a running service. There is no rename/migration of stored data, but the deploy *does* mutate runtime service state (a daemon restart loads the new code). Categories assessed for completeness:

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | None — `ownership_inspection` is computed live, never persisted. No new DB/state file. The cache is in-memory only. | None |
| Live service config | `steering.service` on `cake-shaper` runs the steering daemon; new code requires deploying updated `src/wanctl/steering/*.py` to `/opt/wanctl` and **restarting `steering.service`**. The `:9102` health contract is consumed by operator tooling (`wanctl-operator-summary`) — additive key is backward-compatible. | Deploy code to `/opt/wanctl`; restart `steering.service` (operator-gated; this is the only runtime mutation and is NOT a SAFE-21 route/Netwatch change). |
| OS-registered state | None — no new systemd unit, timer, or task. Same `steering.service`. | None |
| Secrets/env vars | `ROUTER_PASSWORD` already required + present (Phase 258 proved live REST auth). No new secret. Inspector reuses the daemon's authenticated client. | None |
| Build artifacts | `/opt/wanctl` is a deployed copy (Phase 258 used `sudo install` of individual files after `rsync --delete` proved too broad). New file `route_ownership_inspector.py` + modified `daemon.py`/`health.py` must reach `/opt/wanctl`. | Deploy new + modified files; the live proof harness asserts imports resolve under `/opt/wanctl` (mirror `_assert_deployed_imports`). |

**Canonical question answer:** After repo files land, the running `steering.service` still holds the *old* code until restarted. The only runtime state that changes is the daemon process itself (restart). No RouterOS-side, Netwatch-side, or stored-data state changes — SAFE-21 holds.

## Common Pitfalls

### Pitfall 1: Guard is None in current deployment
**What goes wrong:** Reusing `self.route_ownership_guard` yields `AttributeError`/`None` because `_init_route_management()` skips guard construction when route-management is off.
**Why:** daemon.py:1212-1215 — guard only built when `enabled AND mode != "off"`.
**How to avoid:** Inspector constructs its own `RouteOwnershipGuard(self.router.client)` unconditionally.
**Warning sign:** `ownership_inspection` missing or erroring when `route_management.enabled=false`.

### Pitfall 2: REST returns strings for booleans/ints
**What goes wrong:** `disabled` treated as truthy string `"false"` → wrong `disabled=True`.
**Why:** RouterOS REST serializes `disabled` as `"true"`/`"false"` strings (Phase 258 live sample).
**How to avoid:** Use `_routeros_bool()`; coerce `distance` with a defensive int-parse.
**Warning sign:** Every default route shows `disabled=true`.

### Pitfall 3: Blocking the health endpoint on a live RouterOS call
**What goes wrong:** Health request latency spikes / 503s when RouterOS is slow.
**Why:** Inspection on the request path instead of cached.
**How to avoid:** D5 — serve cache only; refresh on the 60s thread.
**Warning sign:** `:9102/health` p99 latency tracks RouterOS RTT.

### Pitfall 4: Lock held during I/O → contention/deadlock risk
**What goes wrong:** Health reads block for the full inspection duration.
**How to avoid:** Compute outside the lock; only swap the cached dict under the lock.

### Pitfall 5: Payload-shape regression
**What goes wrong:** Adding fields under `route_management` or reordering breaks the existing contract → INSPECT-03 fail.
**How to avoid:** New sibling key only; `_build_route_management_section` byte-for-byte unchanged. Add a regression test asserting the existing `route_management` keys are present and unchanged.

### Pitfall 6: Thread not joined on shutdown → dirty exit / test leakage
**What goes wrong:** Inspection thread outlives the daemon in tests or shutdown.
**How to avoid:** Wire `inspector.stop()` into `_cleanup_steering_daemon()` (after health server, before/with router close — but BEFORE `daemon.router.client.close()` so an in-flight refresh doesn't hit a closed session). `daemon=True` is a backstop, not a substitute for explicit join.
**Warning sign:** pytest warns about lingering threads; shutdown logs show refresh after router close.

### Pitfall 7: `match` semantics on error
**What goes wrong:** `observed_owner="unknown"` but `match` computed as `True` because `configured_owner` also degenerate.
**How to avoid:** `match = (observed_owner == configured_owner) and observed_owner != "unknown"` (CONTEXT specifics: "If `observed_owner = "unknown"`, `match = false` always").

## Code Examples

### Health wiring (strictly additive)
```python
# steering/daemon.py  get_health_data()  (after line ~1523)
# Source: existing get_health_data() facade pattern, daemon.py:1502-1531
return {
    ...
    "route_management": self.route_manager.status_snapshot(),   # UNCHANGED
    "ownership_inspection": self.ownership_inspector.snapshot(),  # NEW (D1)
    ...
}
```
```python
# steering/health.py  _populate_daemon_health()  (after line ~195)
# Source: _build_route_management_section call site, health.py:195
health["route_management"] = self._build_route_management_section(health_data)
health["ownership_inspection"] = self._build_ownership_inspection_section(health_data)  # NEW
```
```python
# steering/health.py  NEW builder, modeled on _build_route_management_section (health.py:353)
def _build_ownership_inspection_section(self, health_data: dict[str, Any]) -> dict[str, Any]:
    raw = health_data.get("ownership_inspection")
    oi: dict[str, Any] = raw if isinstance(raw, dict) else {}
    netwatch = oi.get("netwatch") if isinstance(oi.get("netwatch"), dict) else {}
    routes = oi.get("routes") if isinstance(oi.get("routes"), dict) else {}
    return {
        "observed_owner": str(oi.get("observed_owner", "unknown")),
        "configured_owner": str(oi.get("configured_owner", "unknown")),
        "match": bool(oi.get("match", False)),
        "inspector_status": str(oi.get("inspector_status", "unknown")),
        "inspector_error": oi.get("inspector_error"),
        "last_inspected_at": oi.get("last_inspected_at"),
        "netwatch": {
            "entries_count": int(netwatch.get("entries_count", 0) or 0),
            "route_mutating_active_count": int(netwatch.get("route_mutating_active_count", 0) or 0),
        },
        "routes": {
            "total_route_count": int(routes.get("total_route_count", 0) or 0),
            "default_routes": list(routes.get("default_routes", []) or []),
        },
    }
```

### Daemon construct + start + stop
```python
# steering/daemon.py SteeringDaemon.__init__()  (after self._init_route_management(), line ~1185)
self.ownership_inspector = RouteOwnershipInspector(
    router_client=self.router.client,    # dedicated, unconditional (D2)
    route_manager=self.route_manager,    # source of configured_owner
    interval_sec=60.0,
    logger=self.logger,
)
self.ownership_inspector.start()
```
```python
# steering/daemon.py  _cleanup_steering_daemon()  (BEFORE router.client.close(), ~line 2808)
# Pattern source: health_server.shutdown() block, daemon.py:2808-2823
try:
    daemon.ownership_inspector.stop()
except Exception as e:
    logger.warning(f"Error stopping ownership inspector: {e}")
```

### Live proof harness verdict line (mirror Phase 258)
```python
# scripts/phase259-ownership-proof.py — mirror scripts/phase258-readonly-proof.py
# Reuses: _assert_deployed_imports, validate_command, get_router_client, SteeringConfig
# Builds the inspector against the live client, runs ONE refresh(), prints:
print(
    "INSPECT_PROOF_PASS "
    f"observed_owner={snap['observed_owner']} configured_owner={snap['configured_owner']} "
    f"match={snap['match']} netwatch_entries={snap['netwatch']['entries_count']} "
    f"route_mutating_active={snap['netwatch']['route_mutating_active_count']} "
    f"total_routes={snap['routes']['total_route_count']} "
    f"default_routes={len(snap['routes']['default_routes'])}"
)
# FAIL path: INSPECT_PROOF_FAIL <reason>   (and INSPECT_PROOF_FAIL on inspector_status=='error')
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Guard inspection only on startup, gated by route-management mode | Standalone 60s background sensor, unconditional | Phase 259 (this) | Decouples ownership visibility from route-management config; enables Phase 260 readiness packet |
| Owner attribution via `route_manager._active_owner()` (mode-based) | Live `observed_owner` from RouterOS state + `match` against `configured_owner` | Phase 259 | First time observed-vs-configured discrepancy is surfaced |
| SSH key path for RouterOS reads (v1.56 blocker) | REST transport over `get_router_client` (Phase 258) | Phase 258 | Inspector inherits the working REST path; no SSH key dependency |

**Deprecated/outdated:** none relevant. The Phase 258 REST handlers (`_handle_netwatch_print`, `_handle_script_print`, `_handle_route_print`) are current and live-proven.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `configured_owner` should be sourced from `route_manager.status_snapshot()["active_owner"]` (no dedicated `active_owner` YAML key exists). | D3 attribution | LOW — grep confirms no `active_owner` config key; `_active_owner()` returns "netwatch" in dry_run/off. If a future explicit config key is desired, planner can add it. Confirm with operator that "netwatch" (current dry_run) is the intended `configured_owner`. |
| A2 | RouterOS REST `/ip/route` includes `distance` and `comment` fields on default routes; `distance` may be a string. | D7 route projection | LOW — Phase 258 live sample shows `comment`/`gateway`/`disabled`/`dst-address` present; `distance` not in the redacted sample, so its exact type is unconfirmed. Coerce defensively; if absent, surface `null`. The live Phase 259 proof will confirm the real shape. |
| A3 | `netwatch.entries_count` = total Netwatch entries; `route_mutating_active_count` = count of enabled entries whose referenced/inline script matches the route-mutation regex (i.e., `len(guard_result.conflicts)` when source=="netwatch"). | INSPECT-01 summary | LOW — guard already computes conflicts; entries_count needs the raw Netwatch list length, which means the inspector should also read Netwatch directly (or have the guard expose it). Planner: decide whether to read Netwatch once in the inspector and feed both the guard and the count, or read twice. Reading once and reusing is cleaner. |
| A4 | Inspector should run one synchronous `refresh()` at `start()` so the first `:9102/health` after boot already has a real `ownership_inspection` (not a "starting" placeholder). | Pattern 1 | LOW — matches operator expectation; if startup latency budget is tight, planner can defer to first loop tick and serve `inspector_status="starting"`. |

## Open Questions

1. **Where exactly does `configured_owner` come from?**
   - What we know: no `active_owner` config key exists; `route_manager.status_snapshot()["active_owner"]` returns `_active_owner()` = "netwatch" in dry_run/off.
   - What's unclear: whether the planner wants `configured_owner` literally wired to `status_snapshot()["active_owner"]` or to a new explicit config field.
   - Recommendation: wire to `status_snapshot()["active_owner"]` (A1). Single source of truth, zero new config surface, matches CONTEXT D3 wording ("the `active_owner` value from ... `route_management` config").

2. **Read Netwatch once or twice?**
   - What we know: `RouteOwnershipGuard.inspect()` reads Netwatch internally but only returns conflicts, not the raw entry count.
   - What's unclear: cleanest way to get `entries_count` without a second GET.
   - Recommendation: inspector reads Netwatch + script + route directly (3 GETs), computes its own conflict detection by reusing the guard's `_contains_route_mutation` / `_extract_script_names` helpers, OR call `guard.inspect()` for the verdict AND do one extra `/tool netwatch print` for the count. Prefer exposing entry count from the guard if a tiny non-breaking addition is acceptable; otherwise one extra read is fine (read-only, 60s cadence). Planner decides; both satisfy SAFE-21.

3. **Does `total_route_count` count all routes or only IPv4 unicast?**
   - What we know: Phase 258 proof returned `route=17` from `/ip/route` (IPv4 only; `/ipv6/route` is a separate endpoint not queried).
   - Recommendation: `total_route_count = len(/ip route print)` = 17 in current deployment. Matches CONTEXT D7's "17 in Phase 258 proof". Do not add IPv6.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| RouterOS REST (`/rest/ip/route`, `/rest/tool/netwatch`, `/rest/system/script`) | All inspection reads | ✓ (proven live Phase 258) | RouterOS 7.x | — |
| `ROUTER_PASSWORD` secret | REST auth | ✓ (present on `cake-shaper`, proven Phase 258) | — | — |
| Python `threading`, `datetime`, `json` | thread/cache/timestamp/parse | ✓ stdlib | py3.11 | — |
| `requests` | REST transport (inside `RouterOSREST`) | ✓ vendored | in use | — |
| `/opt/wanctl` deploy target | live proof | ✓ (Phase 258 deployed code there) | — | — |

**Missing dependencies with no fallback:** none.
**Missing dependencies with fallback:** none. (Unit/integration tests run fully mocked with no router; only the live proof needs `cake-shaper` + `ROUTER_PASSWORD`.)

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (config in `pyproject.toml`; `.venv/bin/pytest`) |
| Config file | `pyproject.toml` (`[tool.pytest...]`; note `-o addopts=''` used to bypass default addopts in fast slices) |
| Quick run command | `.venv/bin/pytest -o addopts='' tests/test_route_ownership_inspector.py -q` |
| Full suite command | `.venv/bin/pytest tests/ -v` (note: full suite carries ~34 known pre-existing stale-boundary failures per project memory — scope verification to the phase slice) |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| INSPECT-01 | Netwatch entries surfaced (count + route-mutating count) | unit | `.venv/bin/pytest -o addopts='' tests/test_route_ownership_inspector.py -k netwatch -q` | ❌ Wave 0 |
| INSPECT-02 | observed_owner attribution (netwatch/wanctl/none/unknown) + default-route filter | unit | `... -k "owner or default_route" -q` | ❌ Wave 0 |
| INSPECT-02 | over-mocked-REST end-to-end (guard+route via `RouterOSREST`) | integration | `.venv/bin/pytest -o addopts='' tests/test_route_ownership_inspector_rest.py -q` | ❌ Wave 0 (mirror `test_route_ownership_guard_rest_integration.py`) |
| INSPECT-03 | new `ownership_inspection` key present; `route_management` shape unchanged | unit (regression) | `.venv/bin/pytest -o addopts='' tests/test_steering_health.py -k "ownership or route_management" -q` | partial — extend existing health test |
| INSPECT-03 | health serves cached result, never blocks | unit | thread/cache test in `test_route_ownership_inspector.py` | ❌ Wave 0 |
| SAFE-21 | only read-only commands issued (no enable/disable) | unit | assert issued commands all contain `print`, none contain enable/disable (mirror `assert_read_only_commands`, `test_route_ownership_guard.py:30`) | ❌ Wave 0 |
| SAFE-21 / live | live `INSPECT_PROOF_PASS` from deployed `/opt/wanctl` | manual (operator-run, mock-tested) | `.venv/bin/pytest -o addopts='' tests/test_phase259_ownership_proof.py -q` (mock) + operator live run | ❌ Wave 0 (mirror `test_phase258_readonly_proof.py`) |
| D4 fail-open | router error → `inspector_status="error"`, `observed_owner="unknown"`, `match=false`, health stays up | unit | `... -k fail_open -q` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `.venv/bin/pytest -o addopts='' tests/test_route_ownership_inspector.py tests/test_route_ownership_inspector_rest.py -q` + `.venv/bin/ruff check src/wanctl/steering tests`
- **Per wave merge:** add `tests/test_steering_health.py tests/test_route_ownership_guard.py tests/test_routeros_rest.py tests/test_readonly_validator.py tests/test_phase259_ownership_proof.py` (mirror the Phase 258 combined slice that ran `116 passed`)
- **Phase gate:** phase slice green + live `INSPECT_PROOF_PASS` recorded as evidence before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_route_ownership_inspector.py` — attribution, fail-open, thread/cache, read-only assertion (covers INSPECT-01/02, SAFE-21, D4)
- [ ] `tests/test_route_ownership_inspector_rest.py` — over-mocked-`RouterOSREST` integration (mirror `test_route_ownership_guard_rest_integration.py`); confirms `request` method only ever sees GET
- [ ] `tests/test_phase259_ownership_proof.py` — harness happy-path mock + pre-run mutation rejection (mirror `test_phase258_readonly_proof.py`)
- [ ] Extend `tests/test_steering_health.py` — assert `ownership_inspection` key present AND `route_management` keys unchanged (INSPECT-03 no-regression)
- [ ] No framework install needed — pytest already present.

## Security Domain

> `security_enforcement` config status not located in `.planning/config.json` during research; treating as enabled per default. Phase 259 is read-only by mandate (SAFE-21), so the security surface is narrow.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | yes | REST basic auth via `ROUTER_PASSWORD` (existing, unchanged); inspector reuses the daemon's authenticated client. No new auth surface. |
| V3 Session Management | no | No user sessions; `:9102` binds localhost. |
| V4 Access Control | yes | `readonly_validator` enforces read-only command allowlist; least-privilege RouterOS account (Phase 258 ACCESS-03). Inspector issues only allowlisted reads. |
| V5 Input Validation | yes | JSON from RouterOS parsed defensively (fail-closed on bad shape, per guard pattern); `_routeros_bool`/int coercion on untrusted REST fields. |
| V6 Cryptography | no (delegated) | TLS handled by `requests`/`RouterOSREST`; `verify_ssl` config governs it. Phase 259 adds none. |
| V7 Error Handling/Logging | yes | D4 fail-open: errors captured into `inspector_error` string; harness `_redacted_sample` redacts `source`/secret-ish keys before printing. |

### Known Threat Patterns for {Python steering daemon + RouterOS REST}

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Command injection into RouterOS via crafted comment/script content | Tampering | Inspector issues only static read commands; `readonly_validator` rejects shell metachars + mutating verbs (`readonly_validator.py:17-45`). Inspector never interpolates router data into a command. |
| Accidental mutation (a future edit adds an enable/disable) | Tampering / Elevation | SAFE-21 read-only unit test (`assert_read_only_commands`) + validator gate in the proof harness fail the build if a mutating command appears. |
| Secret leakage via health endpoint or proof output | Information Disclosure | `:9102` localhost-bound; harness `_redacted_sample` redacts `source` and secret-like keys; `ownership_inspection` exposes only gateway/disabled/distance/comment + counts (no script source, no credentials). |
| Health-endpoint DoS via slow RouterOS | Denial of Service | Cached-only serving (D5) decouples health latency from RouterOS; 60s cadence bounds router load. |
| Cross-thread race corrupting cached result | Tampering | `threading.Lock` guards the cache swap; compute-outside-lock avoids long holds. |

## Sources

### Primary (HIGH confidence — direct codebase read)
- `src/wanctl/steering/route_ownership_guard.py` — `RouteOwnershipGuard.inspect()` contract, `RouteOwnershipGuardResult` fields, conflict/parse fail-closed logic
- `src/wanctl/steering/health.py` — `_populate_daemon_health()` (line 157), `_build_route_management_section()` (line 353), `start_steering_health_server()` (line 551), `SteeringHealthServer.shutdown()` (line 544), `Thread(daemon=True)` (line 572)
- `src/wanctl/steering/daemon.py` — `__init__` (1150), `_init_route_management()` (1191, guard-gating at 1212-1215), `get_health_data()` (1462, return dict 1502-1531), `RouterOSController.__init__` (831, `self.client`), `run_daemon_loop` shutdown_event.wait idiom (2562), `_cleanup_steering_daemon()` ordering (2786-2834), `_load_route_management_config` (365-386)
- `src/wanctl/steering/route_manager.py` — `status_snapshot()` (280), `_active_owner()` (398-403), `_routeros_bool` (433)
- `src/wanctl/routeros_rest.py` — `run_cmd` (185), dispatch (260-304), `_handle_route_print` (617), `_handle_netwatch_print` (651), `_handle_script_print` (685), `_route_disabled_bool` (734), `_parse_where_filter` (593)
- `src/wanctl/readonly_validator.py` — allowlist (`READ_ONLY_ROUTEROS_OBJECTS` 8-15), `validate_command` (78), forbidden actions (28-45)
- `scripts/phase258-readonly-proof.py` — harness structure, `_assert_deployed_imports`, `_redacted_sample`, `run_proof`, verdict-line format
- `tests/test_route_ownership_guard.py` — `FakeRouter`, `assert_read_only_commands` (30), conflict/no-conflict/fail-closed cases
- `tests/test_route_ownership_guard_rest_integration.py` — over-mocked-`RouterOSREST` pattern, GET-only assertion in `request`
- `.planning/phases/258-read-only-routeros-access-repair/258-03-SUMMARY.md` — live proof result (`route=17 netwatch=3 script=20`), live default-route sample shape, deploy method
- `.planning/REQUIREMENTS.md` — INSPECT-01/02/03, SAFE-21 wording
- `.planning/ROADMAP.md` — Phase 259 goal + success criteria
- `docs/STEERING.md` (140-194) — `route_management` YAML shape, health payload field list

### Secondary (MEDIUM)
- Project memory (`MEMORY.md`) — full-suite ~34 stale-boundary failures; `.planning` gitignored-but-tracked commit workflow

### Tertiary (LOW)
- none — no WebSearch needed; entirely in-codebase.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no new packages; all reused components read directly
- Architecture: HIGH — every integration point (init, get_health_data, _populate_daemon_health, cleanup) located by line number; thread + section-builder patterns have working in-repo templates
- Pitfalls: HIGH — guard-gating, REST string-bools, and payload-shape regression are all confirmed against source, not inferred
- Owner attribution (D3 specifics): MEDIUM — `configured_owner` source and `entries_count` mechanism are A1/A3 assumptions the planner should confirm (both low-risk)

**Research date:** 2026-06-20
**Valid until:** 2026-07-20 (stable in-repo target; re-verify only if `health.py`/`daemon.py`/`routeros_rest.py` change before planning)
