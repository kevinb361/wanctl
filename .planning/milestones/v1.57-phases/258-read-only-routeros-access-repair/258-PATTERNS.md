# Phase 258: Read-Only RouterOS Access Repair - Pattern Map

**Mapped:** 2026-06-20
**Files analyzed:** 4 (2 modified, 2 new tests/validator carry-forward)
**Analogs found:** 4 / 4 (every new/modified file has a strong in-repo analog)

> This is a PRODUCTION network control host phase (SAFE-21, read-only). All new code is read-only by construction (HTTP GET / `print`-only). No mutation handlers, no daemon restart, no threshold changes. Patterns below are inspection-path templates, not mutation templates.

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `src/wanctl/routeros_rest.py` (MODIFY: add `_handle_netwatch_print`, optional `_handle_script_print`, + dispatch lines) | transport client | request-response (HTTP GET) | `_handle_route_print` (same file, lines 609-641) | exact (same file, same shape) |
| `tests/test_routeros_rest.py` (MODIFY: add `TestNetwatchOperations`) | test | request-response | `TestRouteOperations` (same file, lines 822-883) | exact (same file, same fixtures) |
| `tests/test_readonly_validator.py` (NEW: port + generalize Phase 257 validator + negative self-test) | test + utility | transform/validation | `phase257-readonly-validator-*.py` (evidence dir) | role-match (carry-forward, generalize predicate) |
| Read-only allowlist validator module (NEW location TBD — `scripts/` or `tests/`; D2 keeper, generalize the predicate) | utility / guard | transform/validation | `phase257-readonly-validator-*.py` | role-match (generalize, do not rebuild) |
| Live ACCESS-02 proof harness (NEW: operator-run `! <cmd>`, evidence artifact — not pytest) | evidence script | request-response | RESEARCH Code Examples block + `router_client.get_router_client` | composed (no direct analog; see consumer pattern below) |

**Consumers (read-only, NOT modified this phase — context for planner):**

| File | Role | Why it matters |
|------|------|----------------|
| `src/wanctl/router_client.py` (`get_router_client`, `FailoverRouterClient`) | transport factory | The proof and Phase 259 go *through* this factory — never a bespoke client. |
| `src/wanctl/steering/route_ownership_guard.py` (`_read_json_list`) | downstream consumer | Calls `run_cmd("/tool netwatch print detail")` and `run_cmd("/system script print detail")`; fails closed (`status=error`) when the handler returns `None`. This is the exact v1.56 blocker. |

## Pattern Assignments

### `src/wanctl/routeros_rest.py` — add `_handle_netwatch_print` (transport client, request-response)

**Analog:** `_handle_route_print` in the *same file*, lines 609-641. This is a direct copy-with-rename. The netwatch handler is strictly simpler (no `[find]`/enable/disable siblings to worry about — netwatch is read-only here).

**Dispatch fall-through that currently rejects netwatch** (`_execute_single_command`, lines 286-296):
```python
if cmd.startswith("/ip route print") or cmd.startswith("/ip/route/print"):
    return self._handle_route_print(cmd, timeout=timeout_val)
if (
    cmd.startswith("/ip route enable")
    or cmd.startswith("/ip/route/enable")
    or cmd.startswith("/ip route disable")
    or cmd.startswith("/ip/route/disable")
):
    return self._handle_route_rule(cmd, timeout=timeout_val)
self.logger.warning(f"Unsupported command for REST API: {cmd}")
return None   # <-- /tool netwatch print falls through to here today -> run_cmd returns rc=1
```

**New dispatch lines to add (before the `self.logger.warning` fall-through, near line 294):**
```python
if cmd.startswith("/tool netwatch print") or cmd.startswith("/tool/netwatch/print"):
    return self._handle_netwatch_print(cmd, timeout=timeout_val)
# Optional (Phase 259 guard also reads scripts — flag, may add same change):
if cmd.startswith("/system script print") or cmd.startswith("/system/script/print"):
    return self._handle_script_print(cmd, timeout=timeout_val)
```

**Existing route-print handler to mirror** (lines 609-641 — copy this shape exactly):
```python
def _handle_route_print(
    self, cmd: str, timeout: int | None = None
) -> list[dict[str, Any]] | None:
    """Handle /ip route print commands via REST."""
    timeout_val = timeout if timeout is not None else self.timeout
    url = f"{self.base_url}/ip/route"
    filter_spec = self._parse_where_filter(cmd)
    try:
        resp = self._request("GET", url, timeout=timeout_val)
        if not resp.ok:
            self.logger.error(f"Failed to get routes: {resp.status_code}")
            return None
        items = resp.json()
        if filter_spec is None:
            return items  # type: ignore[no-any-return]
        field, value, contains_match = filter_spec
        matched = []
        for item in items:
            item_value = item.get(field)
            if not isinstance(item_value, str):
                continue
            if (contains_match and value in item_value) or (
                not contains_match and item_value == value
            ):
                matched.append(item)
        return matched
    except requests.RequestException as e:
        self.logger.error(f"REST API error getting routes: {e}")
        return None
```

**New handler (rename `route` -> `netwatch`, swap URL to `/tool/netwatch`):**
```python
def _handle_netwatch_print(
    self, cmd: str, timeout: int | None = None
) -> list[dict[str, Any]] | None:
    """Handle /tool netwatch print commands via REST (read-only GET)."""
    timeout_val = timeout if timeout is not None else self.timeout
    url = f"{self.base_url}/tool/netwatch"
    filter_spec = self._parse_where_filter(cmd)  # reuse — guard uses `print detail` (no filter)
    try:
        resp = self._request("GET", url, timeout=timeout_val)
        if not resp.ok:
            self.logger.error(f"Failed to get netwatch: {resp.status_code}")
            return None
        items = resp.json()
        if filter_spec is None:
            return items  # type: ignore[no-any-return]
        # ... identical filter loop as route handler if any where-clause needed ...
    except requests.RequestException as e:
        self.logger.error(f"REST API error getting netwatch: {e}")
        return None
```

**Why read-only by construction:** `_request("GET", ...)` only. No POST/PATCH/PUT. Cannot mutate. The guard calls `/tool netwatch print detail` (the `detail` keyword and no `where` clause means `_parse_where_filter` returns `None` -> returns full list). The route handler's filter machinery is carried for parity but the guard's call path needs only the unfiltered GET.

**Key reused helpers (already exist, do not rebuild):**
- `self._request("GET", url, timeout=...)` — line 124, session wrapper with retry/backoff.
- `self.base_url` — `{protocol}://{host}:{port}/rest`, line 105.
- `self._parse_where_filter(cmd)` — line 585, returns `(field, value, contains_match)` or `None`.
- `run_cmd` -> `_execute_command` -> `_execute_single_command` chain (lines 185-296): a non-`None` handler return becomes `(0, json.dumps(result), "")`; `None` becomes `(1, "", "Command failed")`. This rc=1 path is exactly what made the guard fail closed in v1.56.

---

### `tests/test_routeros_rest.py` — add `TestNetwatchOperations` (test, request-response)

**Analog:** `TestRouteOperations`, same file, lines 822-883. Same fixtures, same MagicMock-session pattern.

**Fixtures to reuse (lines 52-77):** `mock_session` (line 52) returns a `MagicMock(spec=requests.Session)` whose `.request` delegates to `.get/.patch/.post`; `rest_client` (line 66) patches `wanctl.routeros_rest.requests.Session` and builds a `RouterOSREST`. The session's `.get.return_value.json.return_value` is what the handler parses.

**Test analog to copy (route-print success, lines 825-842):**
```python
def test_route_print_filters_dst_address(self, rest_client, mock_session):
    response = MagicMock()
    response.ok = True
    response.json.return_value = [
        {"dst-address": "0.0.0.0/0", "comment": "Spectrum", ".id": "*1"},
        {"dst-address": "10.0.0.0/24", "comment": "LAN", ".id": "*2"},
    ]
    mock_session.get.return_value = response
    rc, stdout, stderr = rest_client.run_cmd(
        '/ip/route/print detail where dst-address="0.0.0.0/0"', capture=True
    )
    assert rc == 0
    assert stderr == ""
    assert json.loads(stdout) == [
        {"dst-address": "0.0.0.0/0", "comment": "Spectrum", ".id": "*1"}
    ]
```

**Fail-closed analog (lines 872-883) — mirror for netwatch to prove `None` -> rc=1:**
```python
def test_route_print_get_failure_fails_closed(self, rest_client, mock_session):
    response = MagicMock()
    response.ok = False
    response.status_code = 500
    mock_session.get.return_value = response
    rc, stdout, stderr = rest_client.run_cmd('/ip route print detail where comment="Spectrum"')
    assert rc == 1
    assert stdout == ""
    assert stderr == "Command failed"
```

**New tests to add (mirror exactly, swap command + URL):**
1. `test_netwatch_print_returns_json` — `run_cmd("/tool netwatch print detail")` -> rc=0, parseable JSON list (covers ACCESS-02).
2. `test_netwatch_print_get_failure_fails_closed` — `resp.ok=False` -> rc=1, `stderr == "Command failed"` (proves the v1.56 failure mode is now distinguishable from a handler-missing fall-through).
3. `test_netwatch_print_uses_get_not_mutation` — assert `mock_session.post`/`patch` NOT called; only `.get` (proves SAFE-21 read-only-by-construction at unit level).
4. (If script handler added) `test_script_print_returns_json` against `/system/script` URL.

**Regression guard:** the existing `test_run_cmd_unsupported_command` (line 366) asserts unsupported commands return rc=1 — confirm netwatch is NO LONGER in that bucket after the change.

---

### `tests/test_readonly_validator.py` + carried-forward validator module (test + utility, transform/validation)

**Analog:** `.planning/milestones/v1.56-phases/257-dry-run-observation-canary-readiness-decision/evidence/phase257-readonly-validator-20260620T120700Z.py` (full file, 125 lines). **D2 keeper — generalize the predicate, do NOT rebuild a parallel guard.**

**Existing enforcement primitives to keep verbatim:**
```python
FORBIDDEN_SUBSTRINGS = (';', '&&', '||', '|', '`', '$(', '>', '<')
FORBIDDEN_ROUTEROS_ACTIONS = (
    ' set ', ' add ', ' remove ', ' enable ', ' disable ', ' run ', ' import ', ' reset ',
    '/set', '/add', '/remove', '/enable', '/disable', '/run', '/import', '/reset',
)
```

**Existing `validate_command` predicate (lines 70-83) — the part to GENERALIZE:**
```python
def validate_command(command: str) -> None:
    for token in FORBIDDEN_SUBSTRINGS:
        if token in command:
            raise ValueError(f'rejected shell metacharacter {token!r}: {command}')
    lowered = f' {command.lower()} '
    slash_lowered = command.lower()
    for token in FORBIDDEN_ROUTEROS_ACTIONS:
        if token.startswith('/'):
            if token in slash_lowered:
                raise ValueError(f'rejected RouterOS mutating action {token!r}: {command}')
        elif token in lowered:
            raise ValueError(f'rejected RouterOS mutating action {token!r}: {command}')
    if command not in ALLOWED_COMMANDS:   # <-- BRITTLE: exact-literal set. Generalize this line.
        raise ValueError(f'command is not in Phase 257 read-only allowlist: {command}')
```

**Generalization (RESEARCH Pitfall 3 + Code Examples): replace exact-literal `ALLOWED_COMMANDS` with an object/verb predicate:**
```python
READ_ONLY_ROUTEROS_OBJECTS = (
    "/ip route print", "/ip/route/print",
    "/tool netwatch print", "/tool/netwatch/print",
    "/system script print", "/system/script/print",
)
# pass iff: no FORBIDDEN_SUBSTRING, no FORBIDDEN_ROUTEROS_ACTION,
# AND the embedded RouterOS verb starts with one of READ_ONLY_ROUTEROS_OBJECTS.
```

**Keep the negative self-test pattern verbatim (lines 94-107):** `self_test()` feeds known-bad commands (`/ip route disable 0`, a `; id` injection) and asserts every one raises `ValueError`. Port this into `tests/test_readonly_validator.py` as parametrized rejection tests PLUS keep the `--self-test` CLI entrypoint (line 111) so the evidence harness can call it.

**Location decision for planner:** the 257 file lives under `evidence/` (one-shot). For D2 carry-forward it becomes a reusable module — put the validator in a stable importable location (`scripts/` or a `wanctl` submodule) and the test in `tests/test_readonly_validator.py`. Do not leave it as a per-phase evidence script.

---

### Live ACCESS-02 proof harness (evidence script, request-response)

**No direct file analog** — composed from `router_client.get_router_client` + the `RouterOSREST` GET path. This is operator-run (`! <cmd>` per D3), not pytest.

**Consumer pattern to follow (go through the factory, not a bespoke client):**
```python
from wanctl.router_client import get_router_client
client = get_router_client(cfg, log)          # cfg mirrors /etc/wanctl/steering.yaml (transport=rest)
assert client.test_connection()                # GET /system/resource precondition (line 992)
rc_r, out_r, _ = client.run_cmd("/ip route print", capture=True, timeout=5)
rc_n, out_n, _ = client.run_cmd("/tool netwatch print", capture=True, timeout=5)
assert rc_r == 0 and json.loads(out_r)         # route read (works today)
assert rc_n == 0 and json.loads(out_n)         # netwatch read (needs new handler) -> D4 proof
```

**D4 acceptance:** BOTH reads exit 0, non-empty, parseable. `test_connection()` (line 992-1004, issues `GET {base_url}/system/resource`) is the connectivity precondition that avoids Pitfall 2 (`verify_ssl: false` masking a degraded endpoint). The operator runs this with `steering.service`'s environment so `ROUTER_PASSWORD` resolves identically (A3).

## Shared Patterns

### REST read handler shape (apply to every new GET handler)
**Source:** `src/wanctl/routeros_rest.py::_handle_route_print` (lines 609-641)
**Apply to:** `_handle_netwatch_print`, `_handle_script_print`
```python
url = f"{self.base_url}/<object>"
resp = self._request("GET", url, timeout=timeout_val)
if not resp.ok:
    self.logger.error(f"Failed to get <object>: {resp.status_code}")
    return None        # -> run_cmd returns (1, "", "Command failed")
return resp.json()     # list[dict] -> run_cmd returns (0, json.dumps(...), "")
except requests.RequestException as e:
    self.logger.error(f"REST API error getting <object>: {e}")
    return None
```
Read-only invariant: GET only, `None` on any failure (fail closed). The `None`->rc=1 contract is what `RouteOwnershipGuard._read_json_list` (route_ownership_guard.py line 123) depends on to fail closed.

### Read-only command enforcement (apply to every evidence command)
**Source:** `phase257-readonly-validator-*.py` `FORBIDDEN_SUBSTRINGS` + `FORBIDDEN_ROUTEROS_ACTIONS` + negative self-test
**Apply to:** every command in the D4 proof command-file before execution (ACCESS-03 / SAFE-21 enforcement layer per D2)
Generalize the allowlist from exact literals to a read-only object predicate; retain shell-metachar and mutating-verb rejection and the `--self-test`.

### Transport factory access (apply to proof + Phase 259 inspection)
**Source:** `src/wanctl/router_client.py::get_router_client` (line 63) / `FailoverRouterClient` (line 203)
**Apply to:** all RouterOS reads — never instantiate `RouterOSREST` directly in inspection code; go through the factory so behavior matches the live daemon (REST primary, SSH fallback).

### Fail-closed JSON read contract (downstream consumer — do not break)
**Source:** `src/wanctl/steering/route_ownership_guard.py::_read_json_list` (lines 120-144)
**Constraint:** guard treats `rc != 0` as `status="error"`, owner `unknown`. The new netwatch handler MUST return parseable JSON on success so the guard returns `ok`/`conflict` instead of `error`. This is the precise v1.56 blocker the phase fixes.

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| Live ACCESS-02 proof harness | evidence script | request-response | No existing operator-run two-read proof script in repo; composed from factory + RESEARCH Code Examples. Closest behavioral reference is the consumer pattern in `route_ownership_guard` + `router_client`, not a copyable file. |

## Metadata

**Analog search scope:** `src/wanctl/routeros_rest.py`, `src/wanctl/router_client.py`, `src/wanctl/steering/route_ownership_guard.py`, `tests/test_routeros_rest.py`, `.planning/milestones/v1.56-phases/257-.../evidence/phase257-readonly-validator-*.py`
**Files scanned:** 5 read in full/targeted + grep across `tests/` and `router_client.py`
**Pattern extraction date:** 2026-06-20
**Production-safety note:** All assigned patterns are read-only (HTTP GET / `print`-only). No mutation handler (`_handle_route_rule`, `_handle_queue_tree_set`, `_handle_mangle_rule`) is an analog for this phase — they are explicitly NOT to be mirrored (SAFE-21).
