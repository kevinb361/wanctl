---
phase: 95-irtt-loss-alerts
plan: 01
subsystem: alerting
tags: [irtt, packet-loss, discord, alertengine, sustained-timer]

# Dependency graph
requires:
  - phase: 89-irtt-foundation
    provides: IRTTResult dataclass with send_loss/receive_loss fields
  - phase: 92-observability
    provides: AlertEngine with per-event cooldown, DiscordFormatter
provides:
  - _check_irtt_loss_alerts method on WANController
  - Sustained upstream/downstream IRTT loss detection
  - Recovery alerting when loss clears
  - DiscordFormatter loss unit mapping
affects: [95-irtt-loss-alerts]

# Tech tracking
tech-stack:
  added: []
  patterns: [sustained-timer-with-recovery-gate, per-rule-threshold-override]

key-files:
  created:
    - tests/test_irtt_loss_alerts.py
  modified:
    - src/wanctl/autorate_continuous.py
    - src/wanctl/webhook_delivery.py

key-decisions:
  - "5% default loss threshold with per-rule loss_threshold_pct override"
  - "Single irtt_loss_recovered type with direction field (not separate up/down recovery types)"
  - "Stale IRTT resets all 4 timer variables inline in run_cycle (not in method)"

patterns-established:
  - "IRTT loss sustained timer: same pattern as congestion timers -- threshold + duration + recovery gate"
  - "Per-rule loss_threshold_pct: extends alert_engine._rules with domain-specific config keys"

requirements-completed: [ALRT-01, ALRT-02, ALRT-03]

# Metrics
duration: 17min
completed: 2026-03-18
---

# Phase 95 Plan 01: IRTT Loss Alerts Summary

**Sustained IRTT packet loss alerting with upstream/downstream timers, recovery gate, per-rule overrides, and Discord loss unit mapping**

## Performance

- **Duration:** 17 min
- **Started:** 2026-03-18T12:08:24Z
- **Completed:** 2026-03-18T12:25:24Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments

- Added \_check_irtt_loss_alerts method with independent upstream/downstream sustained timers
- Wired into run_cycle inside existing IRTT freshness gate with isinstance(AlertEngine) guard
- Stale IRTT data resets all 4 timer variables to prevent false alerts
- Added loss unit mapping to DiscordFormatter for "%" suffix in Discord embeds
- 12 new tests covering sustained fire, recovery gate, per-rule overrides, cooldown suppression, staleness reset
- Full test suite passes (3402 tests, 0 failures)

## Task Commits

Each task was committed atomically:

1. **Task 1 (RED): failing tests for IRTT loss alerting** - `e543291` (test)
2. **Task 1 (GREEN): implement \_check_irtt_loss_alerts** - `2716c13` (feat)
3. **Task 2: DiscordFormatter loss unit mapping** - `681aa53` (feat)

_Note: TDD task had RED + GREEN commits_

## Files Created/Modified

- `tests/test_irtt_loss_alerts.py` - 12 tests for sustained upstream/downstream loss, recovery, overrides, cooldown, staleness
- `src/wanctl/autorate_continuous.py` - \_check_irtt_loss_alerts method, 4 state vars + threshold in **init**, run_cycle wiring with freshness gate
- `src/wanctl/webhook_delivery.py` - Added "loss": "%" to DiscordFormatter.\_UNIT_MAP

## Decisions Made

- Used 5% default loss threshold (configurable via per-rule loss_threshold_pct) -- matches typical ISP SLA ranges
- Single irtt_loss_recovered alert type with direction field in details (not separate upstream/downstream recovery types) -- simpler, consistent with existing recovery pattern
- Staleness reset happens inline in run_cycle (not inside \_check_irtt_loss_alerts) because the method is only called when data is fresh

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- IRTT loss alerting is fully wired and tested
- Ready for next plan in phase 95 or next phase
- Production deployment will activate automatically when IRTT is enabled (already enabled on both containers)

## Self-Check: PASSED

All files exist, all commits verified (e543291, 2716c13, 681aa53).

---

_Phase: 95-irtt-loss-alerts_
_Completed: 2026-03-18_
