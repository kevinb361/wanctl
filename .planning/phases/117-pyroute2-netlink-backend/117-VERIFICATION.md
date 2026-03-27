---
phase: 117-pyroute2-netlink-backend
verified: 2026-03-27T12:00:00Z
status: passed
score: 5/5 must-haves verified
re_verification: false
---

# Phase 117: pyroute2 Netlink Backend Verification Report

**Phase Goal:** tc calls in the 50ms hot loop use kernel netlink instead of subprocess fork/exec, reclaiming ~5ms/cycle
**Verified:** 2026-03-27
**Status:** PASSED
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| #  | Truth                                                                                                   | Status     | Evidence                                                                                 |
|----|---------------------------------------------------------------------------------------------------------|------------|------------------------------------------------------------------------------------------|
| 1  | NetlinkCakeBackend can change CAKE bandwidth via pyroute2 netlink with a single ipr.tc('change') call  | VERIFIED   | `set_bandwidth` calls `ipr.tc("change", kind="cake", index=self._ifindex, ...)` (L143)  |
| 2  | A singleton IPRoute instance persists across calls and reconnects automatically when the socket dies    | VERIFIED   | `_get_ipr()` creates `IPRoute(groups=0)` once, nulled in `_reset_ipr()` on failure      |
| 3  | When netlink fails, the backend transparently falls back to subprocess tc and logs a WARNING            | VERIFIED   | All 5 overridden methods catch `(NetlinkError, OSError, ImportError)` and call `super()`|
| 4  | NetlinkCakeBackend reads per-tin CAKE stats via netlink without subprocess tc -j qdisc show            | VERIFIED   | `get_queue_stats` parses `TCA_STATS2/TCA_STATS_APP/TCA_CAKE_TIN_STATS_*` (L186-287)    |
| 5  | Operator can set transport: linux-cake-netlink in YAML and the factory selects NetlinkCakeBackend       | VERIFIED   | `backends/__init__.py` L42-43: `if transport == "linux-cake-netlink": return NetlinkCakeBackend.from_config(config)` |

**Score:** 5/5 truths verified

### Required Artifacts

| Artifact                                   | Expected                                         | Status     | Details                                                         |
|--------------------------------------------|--------------------------------------------------|------------|-----------------------------------------------------------------|
| `src/wanctl/backends/netlink_cake.py`      | NetlinkCakeBackend class inheriting LinuxCakeBackend | VERIFIED | 466 lines (min 100), exports `NetlinkCakeBackend`, inherits `LinuxCakeBackend` |
| `tests/test_netlink_cake_backend.py`       | Unit tests for netlink bandwidth, lifecycle, fallback | VERIFIED | 1154 lines (min 150), 12 test classes, 63 tests passing          |
| `src/wanctl/backends/__init__.py`          | Factory dispatch for linux-cake-netlink transport | VERIFIED  | Contains `linux-cake-netlink` branch, `NetlinkCakeBackend` in `__all__` |
| `tests/test_backends.py`                   | Factory test for linux-cake-netlink transport    | VERIFIED   | Contains `linux-cake-netlink` at L563, `isinstance(backend, NetlinkCakeBackend)` at L569 |
| `pyproject.toml`                           | netlink optional dependency                       | VERIFIED   | L27: `netlink = ["pyroute2>=0.9.5"]`                            |

### Key Link Verification

| From                              | To                          | Via                                         | Status  | Details                                                         |
|-----------------------------------|-----------------------------|---------------------------------------------|---------|-----------------------------------------------------------------|
| `netlink_cake.py`                | `pyroute2.IPRoute`          | singleton `_get_ipr()` with lazy init        | WIRED   | L113: `self._ipr = IPRoute(groups=0)`, pattern `_get_ipr.*IPRoute` confirmed |
| `netlink_cake.py`                | `linux_cake.py`             | inheritance + `super()` fallback on failure  | WIRED   | L68: `class NetlinkCakeBackend(LinuxCakeBackend):`, 8 `super()` fallback calls |
| `backends/__init__.py`           | `netlink_cake.py`           | factory import and dispatch on transport string | WIRED | L14: `from wanctl.backends.netlink_cake import NetlinkCakeBackend`, L42-43 dispatch |
| `netlink_cake.py get_queue_stats` | `pyroute2 tc('dump') stats` | TCA attribute access mapped to dict contract | WIRED   | `TCA_CAKE_STATS_MEMORY_USED`, `TCA_CAKE_TIN_STATS_SENT_BYTES64`, `TCA_CAKE_TIN_STATS_ECN_MARKED_PACKETS` all present |

### Data-Flow Trace (Level 4)

Not applicable — `NetlinkCakeBackend` is a hardware control backend, not a data-rendering component. It produces outputs (kernel CAKE qdisc state) that are not dynamically rendered in UI/templates; the stats dict is returned to callers in the hot loop, not rendered from a static source.

### Behavioral Spot-Checks

| Behavior                                         | Command                                                                  | Result         | Status |
|--------------------------------------------------|--------------------------------------------------------------------------|----------------|--------|
| Module import succeeds                           | `python -c "from wanctl.backends.netlink_cake import NetlinkCakeBackend; print('import OK')"` | `import OK`  | PASS   |
| Factory import succeeds                          | `python -c "from wanctl.backends import NetlinkCakeBackend, get_backend; print('factory OK')"` | `factory OK` | PASS   |
| 63 netlink unit tests pass                       | `.venv/bin/pytest tests/test_netlink_cake_backend.py -q`                | `63 passed`    | PASS   |
| 45 backend factory tests pass (no regressions)   | `.venv/bin/pytest tests/test_backends.py -q`                            | `45 passed`    | PASS   |
| 58 linux_cake_backend tests pass (no regressions) | `.venv/bin/pytest tests/test_linux_cake_backend.py -q`                 | `58 passed`    | PASS   |
| Ruff lint clean                                  | `.venv/bin/ruff check src/wanctl/backends/netlink_cake.py`              | `All checks passed!` | PASS |
| Mypy type clean                                  | `.venv/bin/mypy src/wanctl/backends/netlink_cake.py`                    | `Success: no issues found` | PASS |

### Requirements Coverage

| Requirement | Source Plan | Description                                                                                  | Status    | Evidence                                                                |
|-------------|-------------|----------------------------------------------------------------------------------------------|-----------|-------------------------------------------------------------------------|
| NLNK-01     | 117-01      | LinuxCakeBackend can change CAKE bandwidth via pyroute2 netlink instead of subprocess `tc`   | SATISFIED | `set_bandwidth` calls `ipr.tc("change", kind="cake", ...)` (L143)      |
| NLNK-02     | 117-01      | NetlinkCakeBackend maintains a singleton IPRoute connection with reconnect on socket death   | SATISFIED | `_get_ipr()` creates once (L113), `_reset_ipr()` nulls on failure (L122-124) |
| NLNK-03     | 117-01      | NetlinkCakeBackend falls back to subprocess `tc` if netlink call fails                       | SATISFIED | 8 `super()` calls across all overridden methods; WARNING logged at each |
| NLNK-04     | 117-02      | NetlinkCakeBackend reads CAKE per-tin stats via netlink instead of subprocess                | SATISFIED | `get_queue_stats` L186-287: parses all 5 base + 4 extended + 11-field per-tin |
| NLNK-05     | 117-02      | Factory registration allows config `transport: "linux-cake-netlink"` to select netlink backend | SATISFIED | `backends/__init__.py` L42-43 + `TestGetQueueStats` + `TestStatsContractParity` + `test_backends.py` L561-598 |

All 5 NLNK requirements mapped to Phase 117 in REQUIREMENTS.md are satisfied. No orphaned requirements found.

### Anti-Patterns Found

None. Scanned `src/wanctl/backends/netlink_cake.py` and `tests/test_netlink_cake_backend.py` for TODO/FIXME/placeholder comments, `return null`/`return []`/`return {}`, and hardcoded empty stubs. Zero matches found.

### Human Verification Required

None. All observable truths are verifiable programmatically for this backend module (no UI components, no real-time visual behavior, no external service integration beyond what is unit-tested via mocks).

### Gaps Summary

No gaps. All 5 NLNK requirements are fully implemented, tested, and wired:

- `src/wanctl/backends/netlink_cake.py` (466 lines): complete `NetlinkCakeBackend` class with singleton `IPRoute(groups=0)`, all method overrides (`set_bandwidth`, `get_bandwidth`, `get_queue_stats`, `initialize_cake`, `validate_cake`, `test_connection`, `close`, `from_config`), per-call fallback pattern, and lazy optional import guard.
- `tests/test_netlink_cake_backend.py` (1154 lines, 12 test classes, 63 tests): covers all NLNK-01..04 behaviors including lifecycle, fallback, stats contract parity, and graceful degradation.
- `backends/__init__.py`: `linux-cake-netlink` transport branch wired, `NetlinkCakeBackend` exported in `__all__`.
- `tests/test_backends.py`: factory dispatch and package export verified for NLNK-05.
- `pyproject.toml`: `netlink = ["pyroute2>=0.9.5"]` optional dependency added.

Commits verified in git log: `465bc03`, `948a9d7` (plan 01), `da60f7b`, `217c877`, `df0ab95` (plan 02).

---

_Verified: 2026-03-27T12:00:00Z_
_Verifier: Claude (gsd-verifier)_
