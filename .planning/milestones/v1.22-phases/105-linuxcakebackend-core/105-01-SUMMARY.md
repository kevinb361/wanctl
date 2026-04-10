---
phase: 105-linuxcakebackend-core
plan: 01
subsystem: backends
tags: [cake, tc, qdisc, subprocess, linux, backend]

# Dependency graph
requires:
  - phase: 104-iommu-verification-gate
    provides: "Verified IOMMU groups for PCIe passthrough NICs"
provides:
  - "LinuxCakeBackend class implementing RouterBackend ABC via tc subprocess"
  - "set_bandwidth with bps-to-kbit tc qdisc change"
  - "get_queue_stats with base 5 + extended 4 + per-tin stats parsing"
  - "initialize_cake via tc qdisc replace with configurable params"
  - "validate_cake readback verification"
  - "47 comprehensive tests covering all methods"
affects: [107-config-integration, 108-steering-wiring, 109-vm-setup]

# Tech tracking
tech-stack:
  added: []
  patterns:
    [
      "tc subprocess with JSON parsing",
      "superset stats dict",
      "no-op ABC stubs for cross-device methods",
    ]

key-files:
  created:
    - src/wanctl/backends/linux_cake.py
    - tests/test_linux_cake_backend.py
  modified: []

key-decisions:
  - "subprocess.run with shell=False and noqa S603 for tc invocation"
  - "Per-tin field name mapping: tc JSON 'drops'/'ecn_mark' to D-05 consumer names 'dropped_packets'/'ecn_marked_packets'"
  - "ecn_marked as sum of per-tin ecn_mark values (not from top-level)"
  - "initialize_cake uses 10s timeout vs 5s default for control loop ops"
  - "Mangle rule stubs return True/True/None per D-02 -- steering stays on MikroTik"

patterns-established:
  - "Pattern: tc JSON parsing via _find_cake_entry helper + stdlib json.loads"
  - "Pattern: superset dict return from get_queue_stats (base 5 + extended, backward compatible)"
  - "Pattern: from_config extracts interface + tc_timeout from config object"

requirements-completed: [BACK-01, BACK-02, BACK-03, BACK-04]

# Metrics
duration: 6min
completed: 2026-03-24
---

# Phase 105 Plan 01: LinuxCakeBackend Core Summary

**LinuxCakeBackend implementing RouterBackend ABC with tc subprocess calls for CAKE bandwidth control, per-tin stats parsing, and qdisc initialization/validation**

## Performance

- **Duration:** 6 min
- **Started:** 2026-03-24T21:56:05Z
- **Completed:** 2026-03-24T22:02:09Z
- **Tasks:** 2
- **Files created:** 2

## Accomplishments

- LinuxCakeBackend fully implements RouterBackend ABC (6 abstract + 3 optional overrides) plus initialize_cake, validate_cake
- set_bandwidth converts bps to kbit and runs tc qdisc change (BACK-01)
- get_queue_stats parses tc -j -s JSON into superset dict: base 5 fields + extended 4 (memory, ecn, capacity) + per-tin list with 11 D-05 consumer-named fields (BACK-02, BACK-04)
- initialize_cake uses tc qdisc replace with key-value and boolean flag params, validate_cake reads back and compares (BACK-03)
- 47 comprehensive tests covering all methods, error paths, and field mappings
- Zero new Python dependencies (stdlib only: subprocess, json, shutil)
- Ruff and mypy clean

## Task Commits

Each task was committed atomically:

1. **Task 1: Implement LinuxCakeBackend class** - `d70818b` (feat) -- TDD: RED `3c0b597`, GREEN `d70818b`, cleanup `dd99419`
2. **Task 2: Create comprehensive tests** - `9113cc1` (test) -- 47 tests, 9 test classes

## Files Created/Modified

- `src/wanctl/backends/linux_cake.py` - LinuxCakeBackend class (423 lines): full RouterBackend implementation via tc subprocess
- `tests/test_linux_cake_backend.py` - Comprehensive test suite (596 lines): 47 tests across 9 classes covering all methods and error paths

## Decisions Made

- Used subprocess.run with shell=False and `# noqa: S603` matching existing wanctl pattern (irtt_measurement.py)
- Per-tin field names mapped from tc JSON abbreviations (drops, ecn_mark) to D-05 consumer names (dropped_packets, ecn_marked_packets)
- ecn_marked computed as sum of per-tin ecn_mark values rather than reading top-level (top-level "drops" maps to "dropped")
- initialize_cake uses 10s timeout (less latency-sensitive than control loop), control loop ops use configurable tc_timeout (default 5s)
- Mangle rule stubs return True/True/None per D-02: steering mangle rules handled by separate RouterOSController in Phase 108
- TIN_NAMES constant documents diffserv4 tin order assumption (0=Bulk, 1=BestEffort, 2=Video, 3=Voice)

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- LinuxCakeBackend is self-contained, ready for Phase 107 config integration (wiring into get_backend factory)
- Phase 108 steering wiring can reference the no-op stub pattern for mangle rules
- All 4 BACK requirements satisfied (BACK-01 through BACK-04)

## Self-Check: PASSED

- All created files exist on disk
- All commit hashes found in git log
- 47/47 tests passing
- Ruff and mypy clean

---

_Phase: 105-linuxcakebackend-core_
_Completed: 2026-03-24_
