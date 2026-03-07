---
phase: 52-operational-resilience
plan: 01
subsystem: security
tags: [ssl, tls, cryptography, yaml, config-validation, cve]

requires:
  - phase: 50-critical-hot-loop-transport-fixes
    provides: REST transport client with verify_ssl parameter
provides:
  - SSL-verify-by-default REST client
  - YAML parse errors with line numbers
  - Patched cryptography dependency
affects: [53-code-cleanup, 52-operational-resilience]

tech-stack:
  added: [cryptography>=46.0.5]
  patterns: [secure-defaults, structured-error-messages]

key-files:
  created: []
  modified:
    - src/wanctl/routeros_rest.py
    - src/wanctl/config_base.py
    - pyproject.toml
    - docs/CONFIG_SCHEMA.md
    - tests/test_routeros_rest.py
    - tests/test_config_base.py

key-decisions:
  - "Pin cryptography>=46.0.5 (not >=45.0.0 as plan suggested) because pip-audit confirmed 46.0.5 is the actual CVE-2026-26007 fix version"
  - "YAML parse errors re-raise as ConfigValidationError to maintain a single exception type for all config errors"

patterns-established:
  - "Secure defaults: all new security-relevant parameters default to the secure value (verify_ssl=True)"
  - "Structured config errors: YAML parse errors include file path, line, and column for operator debugging"

requirements-completed: [OPS-01, OPS-04, OPS-05]

duration: 13min
completed: 2026-03-07
---

# Phase 52 Plan 01: SSL Defaults, CVE Patch, YAML Error Lines Summary

**SSL verify_ssl=True secure default, cryptography>=46.0.5 CVE patch, YAML parse errors with line numbers**

## Performance

- **Duration:** 13 min
- **Started:** 2026-03-07T12:13:50Z
- **Completed:** 2026-03-07T12:27:01Z
- **Tasks:** 3
- **Files modified:** 6

## Accomplishments

- RouterOSREST defaults to verify_ssl=True in both constructor and from_config factory
- CONFIG_SCHEMA.md updated with verify_ssl field documentation and self-signed cert guidance
- YAML parse errors now raise ConfigValidationError with file path, line number, and column
- cryptography pinned to >=46.0.5, upgraded from 46.0.3 to 46.0.5, pip-audit clean

## Task Commits

Each task was committed atomically:

1. **Task 1: SSL verify_ssl=True default + docs** (TDD)
   - RED: `43e9feb` (test: add failing tests for SSL verify_ssl=True default)
   - GREEN: `8136471` (feat: SSL verify_ssl=True default for RouterOS REST client)
2. **Task 2: YAML config parse errors with line numbers** (TDD)
   - RED: `ff80b83` (test: add failing tests for YAML parse error line numbers)
   - GREEN: `cb8ffdb` (feat: YAML parse errors include line numbers via ConfigValidationError)
3. **Task 3: Pin cryptography to patch CVE-2026-26007** - `b78a831` (chore)

## Files Created/Modified

- `src/wanctl/routeros_rest.py` - verify_ssl default changed from False to True in **init** and from_config
- `src/wanctl/config_base.py` - yaml.YAMLError caught and re-raised as ConfigValidationError with line info
- `pyproject.toml` - Added cryptography>=46.0.5 explicit dependency pin
- `docs/CONFIG_SCHEMA.md` - Added verify_ssl field documentation with self-signed cert setup guidance
- `tests/test_routeros_rest.py` - 4 new tests for SSL default behavior (68 total)
- `tests/test_config_base.py` - 4 new tests for YAML parse error handling (106 total)

## Decisions Made

- Pinned cryptography to >=46.0.5 instead of >=45.0.0 because pip-audit confirmed 46.0.5 is the exact version patching CVE-2026-26007 (the currently installed 46.0.3 was still vulnerable)
- YAML parse errors re-raised as ConfigValidationError (not raw yaml.YAMLError) to maintain a single exception type for all configuration errors

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Adjusted cryptography pin from >=45.0.0 to >=46.0.5**

- **Found during:** Task 3 (cryptography pin)
- **Issue:** Plan specified >=45.0.0 as a conservative floor, but pip-audit showed the installed 46.0.3 still had CVE-2026-26007. The actual fix version is 46.0.5.
- **Fix:** Changed pin from >=45.0.0 to >=46.0.5, uv sync upgraded 46.0.3 to 46.0.5
- **Files modified:** pyproject.toml
- **Verification:** pip-audit shows zero cryptography CVEs after upgrade
- **Committed in:** b78a831

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** Essential correction -- the original pin would not have actually fixed the CVE.

## Issues Encountered

- Pre-existing failing test in tests/test_steering_health.py (from plan 52-02 RED phase) -- not caused by this plan's changes, ignored per scope boundary rules

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- SSL defaults in place; production configs should add `verify_ssl: false` if using self-signed router certs
- All config validation errors now provide actionable line numbers
- Ready for plan 52-02 (remaining operational resilience tasks)

## Self-Check: PASSED

All 7 files verified present. All 5 commit hashes verified in git log.

---

_Phase: 52-operational-resilience_
_Completed: 2026-03-07_
