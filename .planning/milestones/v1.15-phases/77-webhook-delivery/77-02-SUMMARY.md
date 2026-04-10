---
phase: 77-webhook-delivery
plan: 02
subsystem: alerting
tags: [webhook, discord, delivery-callback, sigusr1, config-validation]

# Dependency graph
requires:
  - phase: 77-webhook-delivery-01
    provides: WebhookDelivery, DiscordFormatter, AlertFormatter Protocol, delivery_status column
  - phase: 76-alert-engine
    provides: AlertEngine, alerts table, _load_alerting_config
provides:
  - delivery_callback in AlertEngine.fire() triggers WebhookDelivery.deliver()
  - Both daemons construct DiscordFormatter + WebhookDelivery from alerting config
  - SIGUSR1 reload of webhook_url in steering daemon
  - New config fields (mention_role_id, mention_severity, max_webhooks_per_minute)
affects: [78-health-endpoint, daemon-alerting-lifecycle]

# Tech tracking
tech-stack:
  added: []
  patterns:
    [
      delivery_callback pattern for decoupled fire-then-deliver,
      _reload_webhook_url_config for SIGUSR1 webhook hot-reload,
      https:// URL validation at daemon wiring layer,
    ]

key-files:
  created:
    - tests/test_webhook_integration.py
  modified:
    - src/wanctl/alert_engine.py
    - src/wanctl/autorate_continuous.py
    - src/wanctl/steering/daemon.py
    - tests/conftest.py

key-decisions:
  - "delivery_callback as optional parameter to AlertEngine (not subclass or event pattern)"
  - "_persist_alert returns rowid for delivery tracking (alert_id passed to callback)"
  - "Webhook URL validation at daemon wiring layer, not config parsing layer"
  - "conftest mock fixtures updated with alerting_config=None to prevent MagicMock truthy leakage"

patterns-established:
  - "delivery_callback pattern: AlertEngine.fire() -> _persist_alert -> callback(alert_id, type, severity, wan, details)"
  - "Never-crash callback: try/except around delivery_callback with warning log"
  - "SIGUSR1 reload chain: dry_run + wan_state + webhook_url (three independent reloads)"
  - "Mock fixture completeness: new daemon attributes must be set to None in conftest mocks"

requirements-completed: [DLVR-01, DLVR-02, DLVR-03, DLVR-04]

# Metrics
duration: 18min
completed: 2026-03-12
---

# Phase 77 Plan 02: Webhook Integration Wiring Summary

**AlertEngine delivery_callback wiring, both daemons construct WebhookDelivery from config, SIGUSR1 webhook_url reload, new delivery config fields with validation**

## Performance

- **Duration:** 18 min
- **Started:** 2026-03-12T12:44:49Z
- **Completed:** 2026-03-12T13:03:44Z
- **Tasks:** 1 (TDD: RED/GREEN)
- **Files modified:** 5

## Accomplishments

- AlertEngine.fire() now triggers delivery_callback after successful fire (not suppressed), passing alert_id from \_persist_alert rowid
- Both WANController and SteeringDaemon construct DiscordFormatter + WebhookDelivery when alerting enabled, with URL validation (https:// required)
- New config fields parsed with validation: mention_role_id (str|None), mention_severity (default "critical"), max_webhooks_per_minute (default 20)
- SIGUSR1 in steering daemon reloads webhook_url via \_reload_webhook_url_config() calling update_webhook_url()
- 24 new integration tests covering callback invocation, error handling, config parsing, URL validation, SIGUSR1 reload

## Task Commits

Each task was committed atomically (TDD: test then feat):

1. **Task 1: AlertEngine delivery callback and daemon wiring**
   - `9cb9dd8` (test: failing tests for AlertEngine delivery callback and daemon wiring)
   - `5522787` (feat: wire WebhookDelivery into AlertEngine and both daemons)

_Note: TDD tasks have RED commit (test) followed by GREEN commit (feat)._

## Files Created/Modified

- `src/wanctl/alert_engine.py` - Added delivery_callback parameter, \_persist_alert returns rowid, callback invocation after fire()
- `src/wanctl/autorate_continuous.py` - \_load_alerting_config parses new fields, WANController constructs WebhookDelivery
- `src/wanctl/steering/daemon.py` - \_load_alerting_config parses new fields, SteeringDaemon constructs WebhookDelivery, \_reload_webhook_url_config(), SIGUSR1 handler updated
- `tests/test_webhook_integration.py` - 24 tests: callback, config parsing, URL validation, SIGUSR1 reload
- `tests/conftest.py` - Added alerting_config=None to mock_autorate_config and mock_steering_config

## Decisions Made

- delivery_callback as optional Callable parameter to AlertEngine.**init** (lightweight, no new abstraction)
- \_persist_alert returns int|None (rowid or None) so alert_id can be passed to delivery for status tracking
- Webhook URL validation happens at daemon wiring layer (not config parsing) since WebhookDelivery.update_webhook_url also validates
- conftest mock fixtures explicitly set alerting_config=None to prevent MagicMock auto-attribute truthy leakage

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Fixed conftest mock fixtures missing alerting_config attribute**

- **Found during:** Task 1 (full suite verification)
- **Issue:** mock_autorate_config and mock_steering_config in conftest.py did not set alerting_config, causing MagicMock auto-attribute to be truthy; new wiring code in WANController.**init** treated MagicMock as valid config dict, crashing with TypeError on RateLimiter construction
- **Fix:** Added `config.alerting_config = None` to both mock fixtures
- **Files modified:** tests/conftest.py
- **Verification:** Full test suite passes (824 passed, 1 pre-existing unrelated failure)
- **Committed in:** 5522787 (Task 1 GREEN commit)

**2. [Rule 3 - Blocking] Fixed test config dict missing required fields**

- **Found during:** Task 1 (test writing)
- **Issue:** Test \_autorate_config_dict was missing load_time_constant_sec and had incorrect top-level thresholds key
- **Fix:** Matched config dict structure to existing test_alerting_config.py pattern
- **Files modified:** tests/test_webhook_integration.py
- **Verification:** All 24 integration tests pass
- **Committed in:** 5522787 (Task 1 GREEN commit)

---

**Total deviations:** 2 auto-fixed (2 blocking)
**Impact on plan:** Both fixes necessary for test correctness. No scope creep.

## Issues Encountered

- Pre-existing test_deployment_contracts.py failure (Dockerfile LABEL='1.12.0' vs pyproject.toml='1.14.0') is unrelated to this plan. Already noted in 77-01-SUMMARY.md.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- AlertEngine -> WebhookDelivery pipeline is fully wired
- `alerting.enabled: true` with a valid `webhook_url` will now cause fired alerts to appear in Discord
- delivery_failures property ready for health endpoint exposure (Phase 78)
- SIGUSR1 hot-reload of webhook_url is operational in steering daemon
- All test infrastructure in place for Phase 78 (health/observability)

## Self-Check: PASSED

- All 5 files exist (1 created + 4 modified)
- Both commits verified in git log (9cb9dd8, 5522787)
- 24 tests collected and passing in test_webhook_integration.py
- 125 total alert/webhook tests passing (no regressions)

---

_Phase: 77-webhook-delivery_
_Completed: 2026-03-12_
