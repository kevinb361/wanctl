---
phase: 74-visualization-history
plan: 01
subsystem: ui
tags: [textual, sparkline, progressbar, tui, dashboard]

# Dependency graph
requires:
  - phase: 73-foundation
    provides: DashboardApp with WanPanelWidget, poll routing, CSS layout
provides:
  - SparklinePanelWidget with 3 bounded deques (DL, UL, RTT delta)
  - CycleBudgetGaugeWidget with ProgressBar for utilization_pct
  - Poll routing for sparkline data extraction and gauge updates
affects: [74-02, 74-03, 75-observability]

# Tech tracking
tech-stack:
  added: [textual.widgets.Sparkline, textual.widgets.ProgressBar]
  patterns: [bounded-deque-sparkline, poll-data-extraction, graceful-missing-data]

key-files:
  created:
    - src/wanctl/dashboard/widgets/sparkline_panel.py
    - src/wanctl/dashboard/widgets/cycle_gauge.py
    - tests/test_dashboard/test_sparkline_panel.py
    - tests/test_dashboard/test_cycle_gauge.py
  modified:
    - src/wanctl/dashboard/app.py
    - src/wanctl/dashboard/dashboard.tcss
    - tests/test_dashboard/conftest.py
    - tests/test_dashboard/test_app.py

key-decisions:
  - "RTT delta sparkline uses green-to-red gradient via Sparkline min_color/max_color params"
  - "Bounded deques (maxlen=120) ensure constant memory regardless of uptime"
  - "cycle_budget utilization_pct added to conftest fixture to match real health endpoint shape"

patterns-established:
  - "Bounded deque sparkline: deque(maxlen=N) -> list(deque) assigned to Sparkline.data reactive"
  - "Graceful missing data: cycle_budget None check prevents gauge update, no crash"
  - "Poll data extraction: DL/UL from download/upload dicts, RTT delta = max(0, load - baseline)"

requirements-completed: [VIZ-01, VIZ-02, VIZ-03, VIZ-04]

# Metrics
duration: 7min
completed: 2026-03-11
---

# Phase 74 Plan 01: Sparkline Trends and Cycle Gauge Summary

**Sparkline trend widgets with bounded deques for DL/UL/RTT and ProgressBar gauge for 50ms cycle budget utilization**

## Performance

- **Duration:** 7 min
- **Started:** 2026-03-11T19:50:19Z
- **Completed:** 2026-03-11T19:57:44Z
- **Tasks:** 2
- **Files modified:** 8

## Accomplishments
- SparklinePanelWidget with 3 bounded deques (maxlen=120) and RTT green-to-red gradient
- CycleBudgetGaugeWidget with ProgressBar (total=100) and None-safe update
- DashboardApp wired with sparkline + gauge per WAN, poll routing extracts DL/UL/RTT/budget
- 23 new tests (15 widget unit + 8 wiring integration), 102 total dashboard tests passing

## Task Commits

Each task was committed atomically:

1. **Task 1: SparklinePanelWidget and CycleBudgetGaugeWidget with tests** - `71529dc` (feat)
2. **Task 2: Wire sparklines and gauge into DashboardApp with poll routing** - `eb3d113` (feat)

## Files Created/Modified
- `src/wanctl/dashboard/widgets/sparkline_panel.py` - SparklinePanelWidget with 3 Sparkline children and bounded deques
- `src/wanctl/dashboard/widgets/cycle_gauge.py` - CycleBudgetGaugeWidget with ProgressBar for utilization_pct
- `src/wanctl/dashboard/app.py` - Imports, compose() layout, poll routing for sparklines and gauges
- `src/wanctl/dashboard/dashboard.tcss` - CSS for SparklinePanelWidget and CycleBudgetGaugeWidget
- `tests/test_dashboard/test_sparkline_panel.py` - 10 tests: init, append, bounded deque, compose, gradient
- `tests/test_dashboard/test_cycle_gauge.py` - 5 tests: init, update, None handling, compose
- `tests/test_dashboard/test_app.py` - 8 new tests: composition, routing, missing data, accumulation
- `tests/test_dashboard/conftest.py` - Added utilization_pct to cycle_budget fixtures

## Decisions Made
- RTT delta sparkline uses Sparkline's min_color="green", max_color="red" for congestion gradient
- Bounded deques with maxlen=120 (~2min at 1Hz) ensure constant memory
- Sparkline.data reactive updated via list(deque) on each append for Textual re-render
- try/except around query_one in append_data/update_utilization for safe operation before compose
- conftest fixture updated to include utilization_pct matching real health endpoint format

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed Static.renderable AttributeError in tests**
- **Found during:** Task 1 (TDD GREEN phase)
- **Issue:** Test used `s.renderable` but Textual Static has no `renderable` attribute in this version
- **Fix:** Changed to `str(s.render())` for label content verification
- **Files modified:** tests/test_dashboard/test_sparkline_panel.py, tests/test_dashboard/test_cycle_gauge.py
- **Verification:** All 15 widget tests pass
- **Committed in:** 71529dc (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** Test API adjustment for Textual version compatibility. No scope creep.

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Sparkline and gauge widgets ready for Phase 74 Plan 02 (history/replay features)
- All 2,400 unit tests passing, 102 dashboard tests
- Widget tree expanded: WanPanel + SparklinePanel + CycleBudgetGauge per WAN

---
*Phase: 74-visualization-history*
*Completed: 2026-03-11*
