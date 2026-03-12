---
phase: 77-webhook-delivery
plan: 01
subsystem: alerting
tags: [webhook, discord, retry, rate-limit, threading, protocol]

# Dependency graph
requires:
  - phase: 76-alert-engine
    provides: AlertEngine, alerts table, RateLimiter, retry_utils
provides:
  - AlertFormatter Protocol for extensible formatter backends
  - DiscordFormatter with color-coded embeds, mentions, metrics code blocks
  - WebhookDelivery with background thread dispatch, retry, rate-limiting
  - delivery_status column in alerts table schema
affects: [77-02-webhook-delivery, daemon-wiring, health-endpoint]

# Tech tracking
tech-stack:
  added: [requests]
  patterns:
    [
      AlertFormatter Protocol for duck-typed formatters,
      daemon thread dispatch for non-blocking delivery,
      inline retry loop for thread-safe backoff,
    ]

key-files:
  created:
    - src/wanctl/webhook_delivery.py
    - tests/test_webhook_delivery.py
  modified:
    - src/wanctl/storage/schema.py
    - tests/test_alert_engine.py

key-decisions:
  - "Inline retry loop in WebhookDelivery instead of retry_with_backoff decorator (cleaner for thread context)"
  - "RateLimiter reuse from rate_utils.py for webhook rate limiting"
  - "update_webhook_url validates https:// prefix, empty clears (for SIGUSR1 reload)"
  - "delivery_status column added to existing ALERTS_SCHEMA (pending/delivered/failed)"

patterns-established:
  - "AlertFormatter Protocol: duck-typing compatible, any object with format() method qualifies"
  - "Background thread delivery: daemon=True thread for non-blocking 50ms cycle"
  - "Never-crash pattern: all exceptions caught in _do_deliver thread, logged as warnings"
  - "delivery_status tracking: pending on fire, delivered on HTTP 2xx, failed on 4xx/exhaustion"

requirements-completed: [DLVR-01, DLVR-02, DLVR-03, DLVR-04]

# Metrics
duration: 15min
completed: 2026-03-12
---

# Phase 77 Plan 01: Webhook Delivery Core Summary

**AlertFormatter Protocol + DiscordFormatter with color-coded embeds + WebhookDelivery with daemon-thread dispatch, exponential backoff retry, and RateLimiter gating**

## Performance

- **Duration:** 15 min
- **Started:** 2026-03-12T12:24:55Z
- **Completed:** 2026-03-12T12:39:44Z
- **Tasks:** 2 (both TDD: RED/GREEN)
- **Files modified:** 4

## Accomplishments

- AlertFormatter Protocol enables extensible formatter backends without modifying delivery code
- DiscordFormatter produces rich embeds with severity colors, emoji titles, stacked fields, aligned metrics code blocks, mention logic, and footer with version/container
- WebhookDelivery dispatches HTTP POST in daemon thread (never blocks 50ms cycle), retries on 5xx/timeout with exponential backoff (2s/4s), stops on 4xx, rate-limits at max_per_minute
- delivery_status column tracks pending/delivered/failed in SQLite alerts table
- 56 new tests passing, zero regressions

## Task Commits

Each task was committed atomically (TDD: test then feat):

1. **Task 1: AlertFormatter Protocol + DiscordFormatter**
   - `ce68508` (test: failing tests for formatter)
   - `1e9b6d5` (feat: implement AlertFormatter Protocol and DiscordFormatter)
2. **Task 2: WebhookDelivery class with retry, rate-limit, threading, schema**
   - `51899a8` (test: failing tests for WebhookDelivery)
   - `bdac434` (feat: implement WebhookDelivery with retry, rate-limit, threading)

_Note: TDD tasks have RED commit (test) followed by GREEN commit (feat)._

## Files Created/Modified

- `src/wanctl/webhook_delivery.py` - AlertFormatter Protocol, DiscordFormatter, WebhookDelivery (563 lines)
- `tests/test_webhook_delivery.py` - 56 tests covering formatter, delivery, retry, rate-limit, status (686 lines)
- `src/wanctl/storage/schema.py` - Added delivery_status TEXT DEFAULT 'pending' to ALERTS_SCHEMA
- `tests/test_alert_engine.py` - Updated schema test to include delivery_status column

## Decisions Made

- Used inline retry loop in WebhookDelivery.\_do_deliver() instead of the retry_with_backoff decorator because the decorator isn't designed for thread context and the inline loop gives cleaner control over status updates after exhaustion
- Reused RateLimiter from rate_utils.py rather than creating a new rate-limiting mechanism
- update_webhook_url() validates https:// prefix but allows empty string to clear/disable delivery
- delivery_status added directly to ALERTS_SCHEMA CREATE TABLE (safe for new databases; existing databases need ALTER TABLE migration if needed, noted for Plan 02)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Updated existing schema test for new column**

- **Found during:** Task 2 (schema migration)
- **Issue:** test_alert_engine.py::TestAlertsSchema::test_alerts_table_has_correct_columns expected exact column set without delivery_status
- **Fix:** Added "delivery_status": "TEXT" to expected columns dict
- **Files modified:** tests/test_alert_engine.py
- **Verification:** All 90 alert engine + webhook delivery tests pass
- **Committed in:** bdac434 (Task 2 commit)

**2. [Rule 1 - Bug] Fixed ruff UP017 lint warning (datetime.UTC alias)**

- **Found during:** Task 2 (lint verification)
- **Issue:** `timezone.utc` should use `datetime.UTC` alias per Python 3.11+ convention
- **Fix:** Changed `from datetime import datetime, timezone` to `from datetime import UTC, datetime` and `datetime.now(timezone.utc)` to `datetime.now(UTC)`
- **Files modified:** src/wanctl/webhook_delivery.py
- **Verification:** ruff check passes clean
- **Committed in:** bdac434 (Task 2 commit)

---

**Total deviations:** 2 auto-fixed (1 blocking, 1 bug)
**Impact on plan:** Both auto-fixes necessary for correctness. No scope creep.

## Issues Encountered

- Pre-existing test_deployment_contracts.py failure (Dockerfile LABEL='1.12.0' vs pyproject.toml='1.14.0') is unrelated to this plan. Logged to deferred-items.md.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- WebhookDelivery and DiscordFormatter are ready to be wired into daemon startup by Plan 02
- Plan 02 will instantiate WebhookDelivery in both daemon configs and call deliver() from AlertEngine.fire()
- update_webhook_url() is ready for SIGUSR1 reload integration
- delivery_failures property is ready for health endpoint exposure

## Self-Check: PASSED

- All 4 files exist (created + modified)
- All 4 commits verified in git log
- delivery_status column present in schema.py
- 56 tests collected and passing
- tests/test_webhook_delivery.py is 686 lines (>= 200 minimum)

---

_Phase: 77-webhook-delivery_
_Completed: 2026-03-12_
