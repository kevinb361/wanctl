---
phase: 78-congestion-steering-alerts
plan: 01
subsystem: alerting
tags: [congestion-detection, recovery-alerts, autorate, time-monotonic, cooldown]

# Dependency graph
requires:
  - phase: 76-alert-engine
    provides: AlertEngine with fire(), cooldown suppression, SQLite persistence
  - phase: 77-webhook-delivery
    provides: WebhookDelivery with DiscordFormatter, delivery_callback wiring
provides:
  - Sustained congestion detection (DL/UL independent timers)
  - Congestion recovery alerts with gate (only if sustained fired)
  - default_sustained_sec config parsing with per-rule override
  - _check_congestion_alerts() method in WANController
affects: [78-02-steering-alerts, config-schema-docs]

# Tech tracking
tech-stack:
  added: []
  patterns: [sustained-timer-pattern, recovery-gate-pattern, zone-dependent-severity]

key-files:
  created:
    - tests/test_congestion_alerts.py
  modified:
    - src/wanctl/autorate_continuous.py

key-decisions:
  - "DL congested = RED or SOFT_RED; UL congested = RED only (3-state model)"
  - "RED->SOFT_RED shares timer (no reset); GREEN/YELLOW clears timer"
  - "Recovery gate: congestion_recovered only fires if congestion_sustained fired first"
  - "Zone-dependent severity: RED=critical, SOFT_RED=warning, recovery=recovery"
  - "Per-rule sustained_sec override via rules dict (same pattern as cooldown_sec)"
  - "Track last congested zone for accurate recovery alert details"

patterns-established:
  - "Sustained timer pattern: monotonic timestamp + fired flag per direction, checked each cycle"
  - "Recovery gate pattern: _sustained_fired bool prevents spurious recovery alerts"

requirements-completed: [ALRT-01]

# Metrics
duration: 6min
completed: 2026-03-12
---

# Phase 78 Plan 01: Sustained Congestion Detection Summary

**DL/UL independent congestion timers with zone-dependent severity and gated recovery alerts via _check_congestion_alerts() in autorate daemon**

## Performance

- **Duration:** 6 min
- **Started:** 2026-03-12T14:32:20Z
- **Completed:** 2026-03-12T14:38:46Z
- **Tasks:** 1 (TDD: RED + GREEN)
- **Files modified:** 2

## Accomplishments
- Sustained congestion detection firing congestion_sustained_dl/ul after configurable threshold (default 60s)
- Independent DL/UL timers with RED/SOFT_RED shared bucket (DL) and RED-only (UL)
- Gated recovery alerts that only fire if sustained alert actually fired first
- Config parsing for default_sustained_sec with validation (warn+disable on invalid)
- 25 new tests covering all detection, recovery, config, and edge cases

## Task Commits

Each task was committed atomically:

1. **Task 1 RED: Failing tests for sustained congestion detection** - `f63456a` (test)
2. **Task 1 GREEN: Implement sustained congestion detection and recovery alerts** - `0daaa67` (feat)

_TDD task: RED phase committed separately from GREEN phase_

## Files Created/Modified
- `tests/test_congestion_alerts.py` - 25 tests: DL/UL sustained detection, recovery, config, timer independence
- `src/wanctl/autorate_continuous.py` - _check_congestion_alerts() method, default_sustained_sec config parsing, congestion timer state in WANController.__init__

## Decisions Made
- DL congested = RED or SOFT_RED; UL congested = RED only (UL is 3-state, no SOFT_RED)
- RED->SOFT_RED does NOT reset timer (shared "congested" bucket)
- GREEN and YELLOW both clear timer (YELLOW counts as recovered)
- Recovery alert only fires if sustained alert actually fired first (recovery gate)
- Zone-dependent severity: RED=critical, SOFT_RED=warning
- Recovery severity is "recovery" (green in Discord)
- Track _dl_last_congested_zone / _ul_last_congested_zone for accurate recovery details
- Per-rule sustained_sec override follows same pattern as per-rule cooldown_sec

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Alert engine fully wired with congestion detection in autorate daemon
- Ready for Plan 02: steering alerts (steering_activated, steering_recovered)
- All 4 congestion alert types operational: congestion_sustained_dl, congestion_sustained_ul, congestion_recovered_dl, congestion_recovered_ul

---
*Phase: 78-congestion-steering-alerts*
*Completed: 2026-03-12*
