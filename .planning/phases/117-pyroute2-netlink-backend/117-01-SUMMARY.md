---
phase: 117-pyroute2-netlink-backend
plan: 01
subsystem: backends
tags: [pyroute2, netlink, cake, tc, qdisc, linux]

# Dependency graph
requires:
  - phase: 105-linuxcakebackend-core
    provides: LinuxCakeBackend base class with subprocess tc
provides:
  - NetlinkCakeBackend class inheriting LinuxCakeBackend
  - Singleton IPRoute lifecycle with reconnect
  - Per-call subprocess fallback on netlink failure
  - pyroute2 optional dependency
affects: [117-02, factory-registration, linux-cake-netlink-transport]

# Tech tracking
tech-stack:
  added: [pyroute2>=0.9.5]
  patterns:
    [
      netlink-fallback-to-subprocess,
      singleton-iproute-with-reconnect,
      lazy-optional-import,
    ]

key-files:
  created:
    - src/wanctl/backends/netlink_cake.py
    - tests/test_netlink_cake_backend.py
  modified:
    - pyproject.toml

key-decisions:
  - "Inherit from LinuxCakeBackend, override methods with netlink + fallback via super()"
  - "IPRoute(groups=0) to disable multicast subscription overhead"
  - "pyroute2 as optional dep under [project.optional-dependencies] netlink extra"
  - "Per-call fallback: catch NetlinkError/OSError/ImportError, null _ipr, delegate to super()"
  - "overhead_keyword 'docsis' maps to overhead=-1 in pyroute2 kwargs"

patterns-established:
  - "Netlink fallback: catch exception, null singleton, call super() subprocess path"
  - "Lazy optional import: _pyroute2_available guard with ImportError fallback"
  - "_OVERHEAD_KEYWORD_TO_PYROUTE2 mapping dict for keyword-to-kwargs conversion"

requirements-completed: [NLNK-01, NLNK-02, NLNK-03]

# Metrics
duration: 5min
completed: 2026-03-27
---

# Phase 117 Plan 01: NetlinkCakeBackend Summary

**NetlinkCakeBackend with pyroute2 netlink for CAKE bandwidth control, singleton IPRoute lifecycle, and per-call subprocess fallback**

## Performance

- **Duration:** 5 min
- **Started:** 2026-03-27T11:00:07Z
- **Completed:** 2026-03-27T11:05:30Z
- **Tasks:** 1 (TDD: RED + GREEN)
- **Files modified:** 3

## Accomplishments

- NetlinkCakeBackend class inheriting LinuxCakeBackend with all method overrides (set_bandwidth, get_bandwidth, initialize_cake, validate_cake, test_connection, close, from_config)
- Singleton IPRoute(groups=0) with lazy initialization, ifindex resolution, and automatic reconnect on failure
- Per-call subprocess fallback on NetlinkError/OSError/ImportError with WARNING logging
- Graceful pyroute2 import with \_pyroute2_available guard for environments without pyroute2
- 47 new tests across 10 test classes, 0 regressions on existing 58 tests

## Task Commits

Each task was committed atomically (TDD flow):

1. **Task 1 RED: Add failing tests for NetlinkCakeBackend** - `465bc03` (test)
2. **Task 1 GREEN: Implement NetlinkCakeBackend** - `948a9d7` (feat)

_TDD task: test committed first (RED), then implementation (GREEN). No refactor needed._

## Files Created/Modified

- `src/wanctl/backends/netlink_cake.py` - NetlinkCakeBackend class (363 lines)
- `tests/test_netlink_cake_backend.py` - 47 tests across 10 classes (635 lines)
- `pyproject.toml` - Added `netlink = ["pyroute2>=0.9.5"]` optional dependency

## Decisions Made

- Inherited from LinuxCakeBackend rather than creating a standalone class -- enables trivial super() fallback and Liskov substitution with LinuxCakeAdapter
- IPRoute(groups=0) disables multicast event subscriptions since we only need request-response tc operations
- pyroute2 is an optional dependency (not core) -- LinuxCakeBackend subprocess path requires zero external deps
- Per-call fallback pattern: on any netlink failure, null \_ipr reference (force reconnect on next call) and delegate current call to super() subprocess path
- overhead_keyword "docsis" maps to overhead=-1 (CAKE kernel preset), compound keywords like "bridged-ptm" map to atm_mode + overhead kwargs
- Unknown overhead keywords (like "conservative") fall through to subprocess since pyroute2 may not support them directly

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- NetlinkCakeBackend ready for factory registration (117-02: add "linux-cake-netlink" transport to backends/**init**.py)
- Stats parsing via netlink (NLNK-04) deferred to 117-02

## Self-Check: PASSED

- All created files exist on disk
- Both commits (465bc03, 948a9d7) verified in git log
- 47/47 tests passing, 0 regressions on 58 existing tests
- ruff lint clean, mypy type clean

---

_Phase: 117-pyroute2-netlink-backend_
_Completed: 2026-03-27_
