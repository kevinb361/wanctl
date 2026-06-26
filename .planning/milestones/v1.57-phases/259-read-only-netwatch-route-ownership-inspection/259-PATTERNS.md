# Phase 259: Read-Only Netwatch + Route-Ownership Inspection - Pattern Map

**Mapped:** 2026-06-20
**Files analyzed:** 7 (3 new, 4 modified sections)
**Analogs found:** 7 / 7

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `src/wanctl/steering/route_ownership_inspector.py` | service/background-worker | periodic-refresh + cached snapshot | `src/wanctl/cake_stats_thread.py` (thread/lock/snapshot shape) + `src/wanctl/steering/route_ownership_guard.py` (wrapped call) | exact composite |
| `src/wanctl/steering/daemon.py` | controller | request-response | `daemon.py:1191 _init_route_management()` + `daemon.py:1462 get_health_data()` | exact (self-referential) |
| `src/wanctl/steering/health.py` | service/formatter | request-response | `health.py:353 _build_route_management_section()` + `health.py:157 _populate_daemon_health()` | exact (self-referential) |
| `scripts/phase259-ownership-proof.py` | utility/harness | request-response | `scripts/phase258-readonly-proof.py` | exact |
| `tests/test_route_ownership_inspector.py` | test | unit | `tests/test_route_ownership_guard.py` | exact |
| `tests/test_route_ownership_inspector_rest.py` | test | integration | `tests/test_route_ownership_guard_rest_integration.py` | exact |
| `tests/test_phase259_ownership_proof.py` | test | unit | `tests/test_phase258_readonly_proof.py` | exact |

---

## Pattern Assignments

### `src/wanctl/steering/route_ownership_inspector.py` (service, periodic-refresh)

**Primary analog for thread/cache shape:** `src/wanctl/cake_stats_thread.py` (lines 42–103)
**Primary analog for wrapped logic:** `src/wanctl/steering/route_ownership_guard.py` (lines 60–118)

**Imports pattern** (from cake_stats_thread.py lines 12–20):
```python
from __future__ import annotations

import logging
import threading
import time
from typing import Any

logger = logging.getLogger(__name__)
```

**Class skeleton and Lock-protected cache** (from cake_stats_thread.py lines 42–74, adapted):
```python
class RouteOwnershipInspector:
    """60-second background inspector that wraps RouteOwnershipGuard.

    Constructs its own RouteOwnershipGuard unconditionally from the
    supplied router client. Never reuses daemon.route_ownership_guard,
    which may be None when route_management is disabled.
    """

    INTERVAL_SECONDS = 60

    def __init__(self, router_client: RouteOwnershipClient) -> None:
        self._guard = RouteOwnershipGuard(router_client)
        self._lock = threading.Lock()
        self._cached: RouteOwnershipGuardResult | None = None
        self._last_refresh: float | None = None
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()

    def snapshot(self) -> dict[str, Any]:
        """Return a serialisable dict of the latest cached result, or fail-open sentinel."""
        with self._lock:
            result = self._cached
            last_refresh = self._last_refresh
        ...

    def refresh(self) -> None:
        """Force one synchronous inspection and update the cache."""
        result = self._guard.inspect()
        with self._lock:
            self._cached = result
            self._last_refresh = time.monotonic()

    def start(self) -> None:
        """Start the background refresh thread (daemon=True)."""
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run,
            name="wanctl-ownership-inspector",
            daemon=True,
        )
        self._thread.start()
        logger.info("RouteOwnershipInspector started (interval=%ds)", self.INTERVAL_SECONDS)

    def stop(self) -> None:
        """Signal stop and join (up to 5s timeout)."""
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=5.0)
            logger.info("RouteOwnershipInspector stopped")

    def _run(self) -> None:
        """Periodic loop: refresh immediately, then every INTERVAL_SECONDS."""
        self.refresh()
        while not self._stop_event.wait(timeout=self.INTERVAL_SECONDS):
            self.refresh()
```

**Key differences from cake_stats_thread.py:**
- Uses `threading.Event` for `_stop_event` + `Event.wait(timeout=)` instead of `shutdown_event` parameter (inspector owns its own stop event).
- No external `shutdown_event` constructor parameter — caller calls `stop()` which sets the event.
- `snapshot()` returns a serialisable `dict[str, Any]`, not the raw dataclass, so health.py does not need to import the dataclass.
- `refresh()` is public (used by tests and the loop; analogous to no public equivalent in cake_stats_thread).

**Fail-open sentinel in `snapshot()`:**
```python
    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            result = self._cached
            last_refresh = self._last_refresh
        if result is None:
            return {
                "status": "pending",
                "active_allowed": True,   # fail-open: no cached data yet
                "owner": "unknown",
                "conflicts": [],
                "error": None,
                "last_refresh_age_sec": None,
            }
        return {
            "status": result.status,
            "active_allowed": result.active_allowed,
            "owner": result.owner,
            "conflicts": [
                {"source": c.source, "name": c.name, "script": c.script, "reason": c.reason}
                for c in result.conflicts
            ],
            "error": result.error,
            "last_refresh_age_sec": (
                round(time.monotonic() - last_refresh, 1) if last_refresh is not None else None
            ),
        }
```

**CRITICAL GOTCHA — do not reuse daemon.route_ownership_guard:**
`daemon.route_ownership_guard` is `None` when `route_management_enabled=False` or `mode="off"` (set at `daemon.py:1193`, only populated at `daemon.py:1215`). The inspector must call `RouteOwnershipGuard(self.router.client)` in its own `__init__`, unconditionally. This is the whole point: the inspector runs regardless of route_management config.

---

### `src/wanctl/steering/daemon.py` (modified — two sections)

#### Section A: `__init__` / `_init_route_management()` area

**Analog:** `daemon.py:1191-1219` — `_init_route_management()`

**Construction pattern** (lines 1191–1219):
```python
def _init_route_management(self) -> None:
    """Initialize guarded route-management helpers without changing defaults."""
    self.route_ownership_guard: RouteOwnershipGuard | None = None
    self.route_ownership_guard_result: Any | None = None
    ...
    if not self.config.route_management_enabled or self.config.route_management_mode == "off":
        return
    self.route_ownership_guard = RouteOwnershipGuard(self.router.client)
    self.route_ownership_guard_result = self.route_ownership_guard.inspect()
```

**New pattern for inspector:** Add `_init_ownership_inspector()` helper called after `_init_route_management()` in `__init__`:
```python
def _init_ownership_inspector(self) -> None:
    """Initialize the always-on background ownership inspector."""
    from .route_ownership_inspector import RouteOwnershipInspector
    self.ownership_inspector = RouteOwnershipInspector(self.router.client)
    self.ownership_inspector.start()
```
- Unlike `_init_route_management`, no conditional guard — inspector starts unconditionally.
- Import inside method to match the lazy-import style used for other steering submodules.

#### Section B: `get_health_data()` — add `ownership_inspection` key

**Analog:** `daemon.py:1502-1531` — `return {...}` block, specifically:
```python
"route_management": self.route_manager.status_snapshot(),
```

**New pattern:** Add one key immediately after `route_management`:
```python
"ownership_inspection": self.ownership_inspector.snapshot(),
```
Full line range to modify is `daemon.py:1523`. The new key sits at the same level as `route_management`, `rtt_source`, etc.

#### Section C: `_cleanup_steering_daemon()` — stop inspector

**Analog:** `daemon.py:2808-2823` — health server shutdown block (step 1), pattern:
```python
if health_server is not None:
    t0 = time.monotonic()
    try:
        health_server.shutdown()
        logger.debug("Health server stopped")
    except Exception as e:
        logger.warning(f"Error shutting down health server: {e}")
    check_cleanup_deadline("health_server", t0, deadline, SHUTDOWN_TIMEOUT_SECONDS, logger, now=time.monotonic())
```

**New pattern:** Insert inspector stop as step 1a (before health server, since it's lighter):
```python
# 1a. Stop ownership inspector background thread
t0 = time.monotonic()
try:
    daemon.ownership_inspector.stop()
    logger.debug("Ownership inspector stopped")
except Exception as e:
    logger.warning(f"Error stopping ownership inspector: {e}")
check_cleanup_deadline("ownership_inspector", t0, deadline, SHUTDOWN_TIMEOUT_SECONDS, logger, now=time.monotonic())
```

---

### `src/wanctl/steering/health.py` (modified — two locations)

#### Section A: `_build_ownership_inspection_section()`

**Analog:** `health.py:353-390` — `_build_route_management_section()` (exact template)

```python
def _build_route_management_section(self, health_data: dict[str, Any]) -> dict[str, Any]:
    """Build route ownership / management observability section."""
    raw = health_data.get("route_management")
    route_management: dict[str, Any] = raw if isinstance(raw, dict) else {}
    guard_raw = route_management.get("guard")
    guard = guard_raw if isinstance(guard_raw, dict) else {}
    ...
    return {
        "enabled": bool(route_management.get("enabled", False)),
        "mode": str(route_management.get("mode", "off")),
        ...
    }
```

**New section** mirrors this but is flatter (inspector snapshot is already flat):
```python
def _build_ownership_inspection_section(self, health_data: dict[str, Any]) -> dict[str, Any]:
    """Build background ownership inspection observability section."""
    raw = health_data.get("ownership_inspection")
    oi: dict[str, Any] = raw if isinstance(raw, dict) else {}
    return {
        "status": str(oi.get("status", "pending")),
        "active_allowed": bool(oi.get("active_allowed", True)),
        "owner": str(oi.get("owner", "unknown")),
        "conflicts": list(oi.get("conflicts") or []),
        "error": oi.get("error"),
        "last_refresh_age_sec": oi.get("last_refresh_age_sec"),
    }
```

**Key difference from _build_route_management_section:** No nested sub-dicts (guard/reconciliation/circuit_breaker). The inspector snapshot is flat, so the builder is flat.

#### Section B: `_populate_daemon_health()` call site

**Analog:** `health.py:195` — immediately after the route_management line:
```python
health["route_management"] = self._build_route_management_section(health_data)
```

**New line** added directly after:
```python
health["ownership_inspection"] = self._build_ownership_inspection_section(health_data)
```

---

### `scripts/phase259-ownership-proof.py` (new, harness)

**Analog:** `scripts/phase258-readonly-proof.py` (exact structure, all lines)

**Structure to mirror:**
```python
#!/usr/bin/env python3
"""Phase 259 ownership inspection proof harness."""
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any, Protocol

import wanctl
from wanctl import routeros_rest
from wanctl.readonly_validator import iter_commands, validate_command
from wanctl.router_client import get_router_client
from wanctl.steering.daemon import SteeringConfig

DEPLOYED_ROOT = Path("/opt/wanctl").resolve()
DEFAULT_CONFIG = Path("/etc/wanctl/steering.yaml")
```

**`run_proof()` shape** (lines 74–101 in phase258 analog):
- Accept `client` + `commands` list.
- Call `validate_command(command)` on each before `run_cmd`.
- Return `(int, str)` verdict tuple with `OWNERSHIP_PROOF_PASS` / `OWNERSHIP_PROOF_FAIL` tokens.
- Parse JSON, assemble counts/samples dict, `json.dumps(samples, sort_keys=True)` in result string.

**`_assert_deployed_imports()`** (lines 104–117): copy verbatim, update module name in docstring only.

**`main()`** (lines 120–148): copy verbatim pattern; update `argparse` description and logger name.

**Key differences from phase258:**
- Proof covers `RouteOwnershipInspector.refresh()` path rather than raw `run_cmd` directly.
- Verdict token changes: `ACCESS02_PROOF_PASS` → `OWNERSHIP259_PROOF_PASS`, etc.
- May call `RouteOwnershipInspector` directly rather than running raw commands — confirm in RESEARCH.md scope.

---

### `tests/test_route_ownership_inspector.py` (new, unit tests)

**Analog:** `tests/test_route_ownership_guard.py` (exact test shape, all lines)

**FakeRouter pattern** (lines 10–27):
```python
class FakeRouter:
    def __init__(self, *, netwatch: object, scripts: object, fail: str | None = None) -> None:
        self.netwatch = netwatch
        self.scripts = scripts
        self.fail = fail
        self.commands: list[str] = []

    def run_cmd(
        self, cmd: str, capture: bool = False, timeout: int | None = None
    ) -> tuple[int, str, str]:
        self.commands.append(cmd)
        if self.fail and self.fail in cmd:
            return (1, "", "boom")
        if "netwatch" in cmd:
            return (0, json.dumps(self.netwatch), "")
        if "script" in cmd:
            return (0, json.dumps(self.scripts), "")
        return (1, "", "unexpected")
```

**`assert_read_only_commands()` helper** (lines 30–33): copy verbatim — asserts all commands contain `" print"` and none contain `" route enable"` / `" route disable"`.

**Test case pattern** (lines 36–47):
```python
def test_non_mutating_scripts_allow_active():
    router = FakeRouter(
        netwatch=[{"name": "Monitor-Spectrum", "disabled": "false", "down-script": "Notify"}],
        scripts=[{"name": "Notify", "source": ":log warning wan down"}],
    )
    result = RouteOwnershipGuard(router).inspect()
    assert result.status == "ok"
    assert result.active_allowed is True
    assert_read_only_commands(router)
```

**New tests to add beyond the guard analog:**

1. **Attribution test** — `snapshot()` dict contains correct status/owner/conflicts keys.
2. **Fail-open test** — `snapshot()` before first `refresh()` returns `status="pending"`, `active_allowed=True`.
3. **Thread/cache test** — after `start()`+small sleep, `snapshot()` returns non-`"pending"` status; `stop()` does not raise.
4. **Read-only assertion** — `assert_read_only_commands(router)` after `refresh()`.

**Key difference from guard tests:** Tests operate on `RouteOwnershipInspector`, not `RouteOwnershipGuard` directly. The `FakeRouter` shape is identical.

---

### `tests/test_route_ownership_inspector_rest.py` (new, integration)

**Analog:** `tests/test_route_ownership_guard_rest_integration.py` (exact shape, all lines)

**`_rest_client_with_get_bodies()` factory** (lines 12–49): copy verbatim — constructs `RouterOSREST` with a `MagicMock(spec=requests.Session)` that routes GET by URL suffix. The `request()` side-effect raises `AssertionError` on any non-GET method, enforcing read-only.

**Test case pattern** (lines 52–84):
```python
def test_guard_over_rest_route_netwatch_script_non_error() -> None:
    client = _rest_client_with_get_bodies({...})
    result = RouteOwnershipGuard(client).inspect()
    assert result.status != "error"
    assert result.status in {"ok", "conflict"}
```

**New tests:** Replace `RouteOwnershipGuard(client).inspect()` with `RouteOwnershipInspector(client).refresh(); snap = inspector.snapshot()` and assert on `snap["status"]`.

**Key difference:** Tests call `inspector.refresh()` (synchronous) rather than the background thread, to avoid timing dependencies.

---

### `tests/test_phase259_ownership_proof.py` (new, harness test)

**Analog:** `tests/test_phase258_readonly_proof.py` (exact structure, all lines)

**Module-load pattern** (lines 10–15):
```python
SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "phase259-ownership-proof.py"
spec = importlib.util.spec_from_file_location("phase259_ownership_proof", SCRIPT)
assert spec is not None
proof = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(proof)
```

**`FakeClient` pattern** (lines 18–35): copy verbatim — records `commands`, returns JSON stubs by keyword match, `close()` is no-op.

**Happy-path test** (lines 38–53): assert `rc == 0`, verdict contains `OWNERSHIP259_PROOF_PASS` token, and that `client.commands` matches expected read-only command list.

**Mutation-rejection test** (lines 56–61):
```python
def test_run_proof_rejects_mutating_command_before_run_cmd() -> None:
    client = FakeClient()
    with pytest.raises(ValueError, match="mutating action"):
        proof.run_proof(client, ["/ip route disable 0"])
    assert client.commands == []
```
This pattern is mandatory: `validate_command()` must fire before `run_cmd` is ever called.

---

## Shared Patterns

### Read-only command validation
**Source:** `src/wanctl/readonly_validator.py` (used in phase258 harness lines 14, 79, 129)
**Apply to:** `scripts/phase259-ownership-proof.py`, `tests/test_phase259_ownership_proof.py`
```python
from wanctl.readonly_validator import iter_commands, validate_command
# validate_command(command) raises ValueError("mutating action") on any route mutation
```

### Lock-protected cached result with explicit sentinel
**Source:** `src/wanctl/cake_stats_thread.py` lines 67–74
**Apply to:** `route_ownership_inspector.py`
```python
self._cached: CakeStatsSnapshot | None = None
# ...
def get_latest(self) -> CakeStatsSnapshot | None:
    return self._cached  # GIL-protected pointer swap (single object ref)
```
Inspector uses an explicit `threading.Lock()` (not GIL reliance) because `snapshot()` also reads `_last_refresh` atomically with `_cached`.

### Cleanup deadline checking
**Source:** `src/wanctl/steering/daemon.py:2804-2806` — `check_cleanup_deadline()` call pattern
**Apply to:** `_cleanup_steering_daemon()` new inspector stop block
```python
check_cleanup_deadline(
    "ownership_inspector", t0, deadline, SHUTDOWN_TIMEOUT_SECONDS, logger, now=time.monotonic()
)
```

### Health section builder — safe dict extraction
**Source:** `health.py:353-390` — `_build_route_management_section()`
**Apply to:** `_build_ownership_inspection_section()`
Pattern: always call `.get()` with a safe default; cast with `bool()`, `str()`, `int()` to prevent None propagation into the health payload.

---

## No Analog Found

None. All 7 files have strong analogs in the codebase.

---

## Metadata

**Analog search scope:** `src/wanctl/steering/`, `src/wanctl/`, `scripts/`, `tests/`
**Files scanned:** 9 analog files read in full; 2 daemon.py sections read via offset
**Pattern extraction date:** 2026-06-20
