---
phase: 108-steering-dual-backend-observability
plan: 01
subsystem: steering
tags: [linux-cake, dual-backend, per-tin, health-endpoint, transport-routing]

# Dependency graph
requires:
  - phase: 105-linux-cake-backend
    provides: LinuxCakeBackend.get_queue_stats() with per-tin data
  - phase: 107-config-factory-wiring
    provides: get_backend() factory routing linux-cake transport
provides:
  - Transport-aware CakeStatsReader with linux-cake code path
  - Per-tin CAKE statistics in steering health endpoint
  - last_tin_stats cache on CakeStatsReader for downstream consumers
affects: [108-02-per-tin-metrics-history, 110-production-cutover]

# Tech tracking
tech-stack:
  added: []
  patterns:
    [
      autorate config YAML transport detection,
      config proxy for factory,
      per-tin health nesting,
    ]

key-files:
  created: []
  modified:
    - src/wanctl/steering/cake_stats.py
    - src/wanctl/steering/health.py
    - tests/test_cake_stats.py
    - tests/test_steering_health.py

key-decisions:
  - "Transport detected from autorate config YAML (primary_wan_config), not steering config (Pitfall 5)"
  - "_AutorateConfigProxy inner class wraps parsed YAML for get_backend() factory compatibility"
  - "Per-tin data cached on CakeStatsReader.last_tin_stats (not on daemon) -- reader owns stats lifecycle"
  - "raw_tin_stats local var in health.py for mypy type narrowing through getattr"

patterns-established:
  - "Autorate config proxy: _AutorateConfigProxy class wraps parsed YAML dict for factory dispatch"
  - "Per-tin health nesting: congestion.primary.tins[] gated on _is_linux_cake + last_tin_stats"
  - "Config fallback: try/except around transport detection with RouterOS fallback"

requirements-completed: [CONF-03, CAKE-07]

# Metrics
duration: 7min
completed: 2026-03-25
---

# Phase 108 Plan 01: Steering Dual-Backend & Per-Tin Health Summary

**Transport-aware CakeStatsReader delegates to LinuxCakeBackend for linux-cake transport with per-tin CAKE stats in health endpoint**

## Performance

- **Duration:** 7 min
- **Started:** 2026-03-25T15:34:39Z
- **Completed:** 2026-03-25T15:42:25Z
- **Tasks:** 2 (both TDD: RED + GREEN)
- **Files modified:** 4

## Accomplishments

- CakeStatsReader detects linux-cake transport from autorate config YAML, creates LinuxCakeBackend via get_backend() factory
- Linux-cake path: dict-to-CakeStats conversion with delta calculation and per-tin caching
- Health endpoint shows tins[] array (4 tins, 9 fields each) under congestion.primary when linux-cake active
- Config load errors fall back gracefully to RouterOS path
- 14 new tests (8 cake_stats + 6 health), 98 total tests passing across both files

## Task Commits

Each task was committed atomically:

1. **Task 1 RED: Failing linux-cake CakeStatsReader tests** - `9e2468b` (test)
2. **Task 1 GREEN: Transport-aware CakeStatsReader implementation** - `4a6c86c` (feat)
3. **Task 2 RED: Failing per-tin health tests** - `3d13728` (test)
4. **Task 2 GREEN: Per-tin CAKE stats in health endpoint** - `619ce94` (feat)

## Files Created/Modified

- `src/wanctl/steering/cake_stats.py` - Transport-aware CakeStatsReader with linux-cake code path, \_AutorateConfigProxy, last_tin_stats cache
- `src/wanctl/steering/health.py` - Per-tin tins[] array in congestion.primary, gated on \_is_linux_cake + data availability
- `tests/test_cake_stats.py` - TestCakeStatsReaderLinuxCake class (8 tests: backend creation, contract, delta, tin cache, None, fallback)
- `tests/test_steering_health.py` - TestPerTinHealth class (6 tests: present, names, fields, values, omission conditions)

## Decisions Made

- Transport detected from autorate config YAML (primary_wan_config path), not steering config -- steering config's router.transport stays rest/ssh for mangle rules (D-03, Pitfall 5)
- \_AutorateConfigProxy inner class wraps parsed YAML for get_backend() factory compatibility (avoids importing BaseConfig which has side effects)
- Per-tin data cached on CakeStatsReader.last_tin_stats -- reader owns the stats lifecycle, health endpoint accesses via daemon.cake_reader.last_tin_stats
- Used local variable raw_tin_stats in health.py for mypy type narrowing through getattr chains

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- CakeStatsReader linux-cake path complete, ready for steering daemon integration
- last_tin_stats cache ready for per-tin metrics recording (Plan 108-02)
- Health endpoint per-tin data ready for wanctl-history --tins display (Plan 108-02)

## Self-Check: PASSED

All 4 source/test files verified present. All 4 commit hashes verified in git log.

---

_Phase: 108-steering-dual-backend-observability_
_Completed: 2026-03-25_
