---
phase: 117-pyroute2-netlink-backend
plan: 02
subsystem: backends
tags: [pyroute2, netlink, cake, stats, per-tin, factory]

# Dependency graph
requires:
  - phase: 117-01
    provides: NetlinkCakeBackend base class with set_bandwidth/get_bandwidth/initialize_cake/validate_cake
provides:
  - get_queue_stats override with netlink per-tin stats parsing
  - Factory dispatch for "linux-cake-netlink" transport
  - Contract parity between netlink and subprocess stats paths
affects: [linux-cake-adapter, daemon-stats-collection]

# Tech tracking
tech-stack:
  added: []
  patterns:
    [
      netlink-stats-parsing-with-fallback,
      contract-parity-testing,
      factory-transport-dispatch,
    ]

key-files:
  created: []
  modified:
    - src/wanctl/backends/netlink_cake.py
    - src/wanctl/backends/__init__.py
    - tests/test_netlink_cake_backend.py
    - tests/test_backends.py

key-decisions:
  - "get_queue_stats uses dict-style access for TCA_STATS_BASIC/QUEUE with isinstance(dict) guard for mock safety"
  - "Per-tin iteration supports up to 8 tins (range(8) with break on None) covering all CAKE diffserv modes"
  - "Missing TCA_STATS_APP returns zero extended fields and empty tins (graceful degradation without fallback)"
  - "Missing TCA_STATS2 triggers subprocess fallback (stats2 is required for any useful output)"
  - "Contract parity tests compare both keys and values between netlink and subprocess paths"

requirements-completed: [NLNK-04, NLNK-05]

# Metrics
duration: 11min
completed: 2026-03-27
---

# Phase 117 Plan 02: Netlink Stats Parsing and Factory Registration Summary

**Netlink-based per-tin CAKE stats via pyroute2 TCA_STATS2 decoder with factory dispatch for linux-cake-netlink transport**

## Performance

- **Duration:** 11 min
- **Started:** 2026-03-27T11:10:26Z
- **Completed:** 2026-03-27T11:22:01Z
- **Tasks:** 2 (Task 1: TDD RED+GREEN, Task 2: auto)
- **Files modified:** 4

## Accomplishments

- get_queue_stats override on NetlinkCakeBackend reads TCA_STATS2/TCA_STATS_APP via pyroute2 tc("dump")
- Maps 5 base fields (packets, bytes, dropped, queued_packets, queued_bytes) from TCA_STATS_BASIC/QUEUE
- Maps 4 extended fields (memory_used, memory_limit, capacity_estimate, ecn_marked) from TCA_CAKE_STATS
- Per-tin parsing: 11 fields each (sent_bytes, sent_packets, dropped_packets, ecn_marked_packets, backlog_bytes, peak/avg/base_delay_us, sparse/bulk/unresponsive_flows)
- ecn_marked computed as sum of ecn_marked_packets across all tins
- Factory registers "linux-cake-netlink" transport in get_backend() for config-driven opt-in
- Contract parity tests prove netlink output matches subprocess output field-for-field and value-for-value
- 63 netlink tests (47 from 117-01 + 16 new), 166 total backend tests, 941/942 full suite (1 pre-existing)

## Task Commits

Each task was committed atomically (TDD flow for Task 1):

1. **Task 1 RED: Add failing tests for get_queue_stats** - `da60f7b` (test)
2. **Task 1 GREEN: Implement get_queue_stats netlink stats** - `217c877` (feat)
3. **Task 2: Factory registration and full suite validation** - `df0ab95` (feat)

## Files Created/Modified

- `src/wanctl/backends/netlink_cake.py` - Added get_queue_stats override (+104 lines)
- `src/wanctl/backends/__init__.py` - Added NetlinkCakeBackend import, factory dispatch, **all** entry
- `tests/test_netlink_cake_backend.py` - Added TestGetQueueStats (13 tests), TestStatsContractParity (3 tests), mock helpers (+520 lines)
- `tests/test_backends.py` - Added factory test for linux-cake-netlink, import/export tests (+28 lines)

## Decisions Made

- get_queue_stats uses dict-style access for TCA_STATS_BASIC/QUEUE with isinstance(dict) guard for mock safety and pyroute2 nla compatibility
- Per-tin iteration uses range(8) with break-on-None to support diffserv4 (4 tins), besteffort (1), and diffserv3 (3) modes
- Missing TCA_STATS_APP returns zero extended fields and empty tins rather than falling back to subprocess (base stats are still valid)
- Missing TCA_STATS2 triggers subprocess fallback since no useful data can be extracted without it
- Contract parity tests use identical numeric values (matching SAMPLE_CAKE_JSON from test_linux_cake_backend.py) to prove exact field-for-field compatibility

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## Known Stubs

None - all code is fully wired and functional.

## Self-Check: PASSED

- All 4 modified files exist on disk
- All 3 commits (da60f7b, 217c877, df0ab95) verified in git log
- 63/63 netlink tests passing, 166/166 backend tests passing
- All acceptance criteria verified (14/14 grep checks pass)
- ruff lint clean, mypy type clean on both modified source files

---

_Phase: 117-pyroute2-netlink-backend_
_Completed: 2026-03-27_
