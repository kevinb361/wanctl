---
phase: 242-backend-factory-loud-fallback
plan: 03
subsystem: rtt-backend-wiring
tags: [rtt-backend, fping, icmplib, health, steering, safe-17]

requires:
  - phase: 242-backend-factory-loud-fallback
    provides: RttBackendHandle factory with controller_measurement split and deferred thread builder
provides:
  - Factory-wired autorate RTT backend construction with icmplib controller helper binding
  - Steering construction path resolving backend and source_ip from the primary WAN autorate config
  - Per-WAN additive /health fallback signal: backend_active, fell_back, fallback_count
affects: [phase-242, phase-244, phase-245, rtt-backend-factory, steering-health]

tech-stack:
  added: []
  patterns: [factory handle call-site wiring, Config-like primary WAN wrapper, per-controller health attribution]

key-files:
  created: []
  modified:
    - src/wanctl/autorate_continuous.py
    - src/wanctl/steering/daemon.py
    - src/wanctl/wan_controller.py
    - src/wanctl/health_check.py
    - tests/test_wan_controller.py
    - tests/test_health_check.py

key-decisions:
  - "Bound WANController.rtt_measurement to handle.controller_measurement so fping remains background-thread-only in Phase 242 while helper paths keep icmplib RTTMeasurement semantics."
  - "Resolved steering backend and source_ip from the primary WAN autorate config via an explicit Config-like helper; steering consumption remains deferred to Phase 245."
  - "Surfaced fallback attribution from each controller's own handle status rather than any module-global fallback state."

patterns-established:
  - "Call sites consume RttBackendHandle fields directly: controller_measurement for helper paths, make_thread for background RTT, status fields for /health."
  - "Health measurement extensions are additive beside available/raw_rtt_ms/staleness_sec and preserve existing rounding."

requirements-completed: [FALL-02, SAFE-17]

duration: 15 min
completed: 2026-06-16
---

# Phase 242 Plan 03: Backend Factory Wiring + Health Fallback Signal Summary

**Factory-wired autorate and steering RTT construction with per-WAN backend fallback attribution in `/health`.**

## Performance

- **Duration:** 15 min
- **Started:** 2026-06-16T12:51:40Z
- **Completed:** 2026-06-16T13:06:42Z
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments

- Collapsed autorate RTT construction to `build_rtt_backend()` and passed `handle.controller_measurement` to `WANController`, with the handle also carried as thread factory and backend status.
- Replaced steering's dead no-source RTTMeasurement construction with factory construction sourced from the primary WAN autorate YAML, including loud warnings if `ping_source_ip` cannot be resolved.
- Added per-controller `/health.measurement` fallback attribution fields (`backend_active`, `fell_back`, `fallback_count`) while preserving the three steering-consumed fields.

## Task Commits

Each task was committed atomically:

1. **Task 1: Wire factory call sites and controller thread factory path** - `a640e778` (feat)
2. **Task 2: Expose RTT backend fallback health signal** - `a2512810` (feat)

**Plan metadata:** pending final docs commit

## Files Created/Modified

- `src/wanctl/autorate_continuous.py` - Autorate call site now builds an `RttBackendHandle` and binds `controller_measurement` plus handle state into `WANController`.
- `src/wanctl/steering/daemon.py` - Steering now builds its dead RTT measurement through the factory using a Config-like wrapper around the primary WAN config.
- `src/wanctl/wan_controller.py` - Added optional `rtt_backend_status` state, typed the background RTT driver protocol, and writes fallback attribution into the health producer dict.
- `src/wanctl/health_check.py` - Reflects additive fallback attribution keys in the measurement section without changing preserved fields.
- `tests/test_wan_controller.py` - Added fping live-path, controller-helper-path, and steering primary-config helper regressions.
- `tests/test_health_check.py` - Added additive fallback-key assertions and per-WAN independence coverage.

## Verification Results

- `grep -q 'build_rtt_backend' ... && .venv/bin/pytest -o addopts='' tests/test_wan_controller.py tests/test_rtt_backend_factory.py -q` — **PASS** (`232 passed`).
- `.venv/bin/pytest tests/test_health_check.py -q` — **PASS** (`194 passed`).
- `.venv/bin/pytest tests/test_health_check.py -k byte_preserved -x -q` — **PASS** (`1 passed, 193 deselected`).
- `.venv/bin/pytest -o addopts='' tests/test_cake_signal.py tests/test_queue_controller.py tests/test_wan_controller.py tests/test_health_check.py -q` — **PASS** (`678 passed`).
- `.venv/bin/ruff check src/wanctl/autorate_continuous.py src/wanctl/steering/daemon.py src/wanctl/wan_controller.py src/wanctl/health_check.py tests/test_wan_controller.py tests/test_health_check.py` — **PASS**.
- `.venv/bin/mypy src/wanctl/autorate_continuous.py src/wanctl/steering/daemon.py src/wanctl/wan_controller.py src/wanctl/health_check.py` — **PASS**.
- `git diff --name-only HEAD~2..HEAD -- src/wanctl/` — **PASS**: source edits confined to `autorate_continuous.py`, `health_check.py`, `steering/daemon.py`, and `wan_controller.py`.
- `python scripts/phase239-protected-body-diff.py --anchor HEAD~2` — **PROTECTED BODY PASS** for `RTTMeasurement.*`, `BackgroundRTTThread._run`, `BackgroundRTTThread._ping_with_persistent_pool`, and `WANController.measure_rtt`; the script still exits nonzero on its older allowed-shape check for `rtt_measurement.py` despite no `rtt_measurement.py` diff in this plan.

## Decisions Made

- Bound `WANController.rtt_measurement` to `handle.controller_measurement` instead of `handle.backend`; this keeps the three helper/scorer paths on icmplib while fping only drives the background adapter in Phase 242.
- Used a small `_PrimaryWanRttConfig` wrapper in steering so `build_rtt_backend()` receives the same `.data["measurement"]` and `.timeout_ping` shape as autorate config, without reading backend selection from `steering.yaml`.
- Read fallback status from each controller's own `self._rtt_backend_status` handle so dual-WAN attribution cannot be masked by process-global state.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Typed the background RTT driver protocol for mypy**
- **Found during:** Task 1 verification.
- **Issue:** The plan-required mypy command on `wan_controller.py` surfaced `measure_rtt()` returning `Any` because `_rtt_thread` had been typed as `Any | None` while the factory adapter is protocol-compatible.
- **Fix:** Added a private `_BackgroundRttDriver` protocol and typed `_rtt_thread` against it, without editing the protected `measure_rtt()` body.
- **Files modified:** `src/wanctl/wan_controller.py`
- **Verification:** `.venv/bin/mypy src/wanctl/autorate_continuous.py src/wanctl/steering/daemon.py src/wanctl/wan_controller.py` passed; protected-body check reported `WANController.measure_rtt` PASS.
- **Committed in:** `a640e778`

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** The fix made the new factory adapter statically visible to mypy while preserving protected controller behavior.

## Issues Encountered

- The repository pre-commit hook prompted for documentation updates on new helper/tests; commits used the hook's documented `SKIP_DOC_CHECK=1` path, not `--no-verify`.
- `phase239-protected-body-diff.py` reports an allowed-shape failure when used against this two-commit plan diff, but its protected-body checks passed and `git diff` shows no `rtt_measurement.py` change.

## Known Stubs

None introduced. Existing empty dict/list defaults reported by the stub scan are initialization/test-fixture defaults, not UI/data-source stubs.

## User Setup Required

None - no external service configuration required.

## Threat Flags

None - the new surface is limited to already-planned internal config reads and additive `/health` fields (`backend_active`, `fell_back`, `fallback_count`) with no source IP or per-sample topology data exposed.

## Next Phase Readiness

Ready for 242-04 to run the SAFE-17 boundary verifier/finality gate against the now-wired call sites and health signal.

## Self-Check: PASSED

- Verified summary file exists: `.planning/phases/242-backend-factory-loud-fallback/242-03-SUMMARY.md`.
- Verified modified source files exist: `src/wanctl/autorate_continuous.py`, `src/wanctl/steering/daemon.py`, `src/wanctl/wan_controller.py`, `src/wanctl/health_check.py`.
- Verified task commits exist in git history: `a640e778`, `a2512810`.

---
*Phase: 242-backend-factory-loud-fallback*
*Completed: 2026-06-16*
