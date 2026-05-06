---
phase: 201-docsis-aware-ul-congestion-control
plan: 06
subsystem: release-config-docs
tags: [phase-201, spectrum-yaml, docsis-mode, version-bump, changelog, configuration-docs, valn-06]

requires:
  - phase: 201-04-controller-core
    provides: DOCSIS-mode QueueController setpoint, integral, corroborator, and floor-hit accounting
  - phase: 201-05-wan-controller-and-health
    provides: WANController DOCSIS plumbing and additive upload health fields
provides:
  - Spectrum YAML DOCSIS-mode opt-in with setpoint 12, integral window, CAKE corroborator thresholds, R0 stripped, and R5+R3 retained
  - v1.42.0 version coherence across pyproject.toml, wanctl.__version__, and docker/Dockerfile
  - v1.42.0 CHANGELOG migration and inherited VALN-06 closure framing
  - DOCSIS-aware upload configuration guidance with restart-required migration note
affects: [201-07-predeploy-gate, 201-08-canary-script-extension, 201-11-canary-execution, VALN-06]

tech-stack:
  added: []
  patterns:
    - deployment-specific DOCSIS behavior remains in Spectrum YAML, not Python branching
    - release-coherence verification across package, runtime, and Docker version surfaces
    - restart-required migration docs for startup-only control-mode keys

key-files:
  created:
    - .planning/phases/201-docsis-aware-ul-congestion-control/201-06-SUMMARY.md
  modified:
    - configs/spectrum.yaml
    - pyproject.toml
    - src/wanctl/__init__.py
    - docker/Dockerfile
    - CHANGELOG.md
    - docs/CONFIGURATION.md
    - .claude/context.md

key-decisions:
  - "Kept Spectrum setpoint_mbps at 12 as an explicit [ASSUMED] canary-validated starting point; if setpoint-specific canary failure occurs, the next parameter branch prefers 10 before 14."
  - "Stripped only rejected v1.41 upload target/warn bloat keys from Spectrum YAML while retaining R5 factor_down_yellow=1.0 and R3 consecutive_yellow_decay_clamp=40."
  - "Documented DOCSIS-mode keys as restart-required; SIGUSR1 remains out of scope for docsis_mode/setpoint/integral/corroborator changes."

patterns-established:
  - "Spectrum-only tuning changes are YAML-local and verified path-aware so non-Spectrum YAMLs remain byte-identical."
  - "Release notes must distinguish canary-validated assumptions from sweep-proven tuning results."

requirements-completed: []

duration: 4min
completed: 2026-05-04
---

# Phase 201 Plan 06: Spectrum YAML and Version Summary

**Spectrum DOCSIS-mode YAML, v1.42.0 release surfaces, and restart-required migration docs now align around a canary-validated setpoint assumption.**

## Performance

- **Duration:** 4 min
- **Started:** 2026-05-04T22:40:12Z
- **Completed:** 2026-05-04T22:44:08Z
- **Tasks:** 3/3 complete
- **Files modified:** 7 files including local execution context

## Accomplishments

- Updated `configs/spectrum.yaml` upload settings for Phase 201: `docsis_mode: true`, `setpoint_mbps: 12`, `integral_window_seconds: 2.0`, `integral_threshold_ms_s: 30.0`, `cake_backlog_low_threshold_bytes: 5000`, and `cake_delay_delta_low_threshold_us: 5000`.
- Removed the rejected v1.41 upload `target_bloat_ms: 42` and `warn_bloat_ms: 105` hypothesis keys while preserving `floor_mbps: 8`, `ceiling_mbps: 18`, `factor_down_yellow: 1.0`, and `consecutive_yellow_decay_clamp: 40`.
- Bumped all three version surfaces to `1.42.0`: `pyproject.toml`, `src/wanctl/__init__.py`, and `docker/Dockerfile`.
- Added a v1.42.0 changelog entry covering Added, Changed, Migration, Inherited blocking closure, and deferred out-of-scope sections.
- Added `docs/CONFIGURATION.md` guidance for DOCSIS-aware upload mode, including strict `floor_mbps < setpoint_mbps < ceiling_mbps` ordering and the `systemctl restart wanctl@<wan>.service` migration path.

## Task Commits

Each task was committed atomically:

1. **Task 1: Edit configs/spectrum.yaml (R5+R3 keep, R0 strip, D-09 setpoint=12, D-10 ceiling=18)** — `130cb16` (`feat`)
2. **Task 2: Bump version to 1.42.0 in pyproject.toml, src/wanctl/__init__.py, docker/Dockerfile** — `30294d7` (`chore`)
3. **Task 3: Add v1.42.0 CHANGELOG entry and DOCSIS-Aware UL Control Mode section in docs/CONFIGURATION.md** — `76b9a01` (`docs`)

**Plan metadata:** final docs commit created after this SUMMARY and state/roadmap updates.

## Files Created/Modified

- `configs/spectrum.yaml` — Spectrum upload block changed by `+14/-2`; R0 threshold keys stripped, six DOCSIS-mode keys added, R5+R3 retained.
- `pyproject.toml` — Project version changed to `1.42.0`.
- `src/wanctl/__init__.py` — Runtime `__version__` changed to `1.42.0`.
- `docker/Dockerfile` — Docker image label changed to `1.42.0`.
- `CHANGELOG.md` — Added a 43-line v1.42.0 section with VALN-06, canary assumption, migration, and deferred-scope notes.
- `docs/CONFIGURATION.md` — Added a 32-line DOCSIS-aware upload mode section with migration and ordering guidance.
- `.claude/context.md` — Updated local context so the version-only task commit satisfied the project documentation hook without bypassing hooks.

## Verification

- `.venv/bin/python -c "import yaml; yaml.safe_load(open('configs/spectrum.yaml'))"` → passed
- `.venv/bin/python -c "from wanctl.autorate_config import Config; c = Config('configs/spectrum.yaml'); assert c.docsis_mode is True and c.setpoint_mbps == 12 and c._docsis_mode_explicit is True and c._setpoint_mbps_explicit is True"` → passed
- Path-aware YAML assertions confirmed six DOCSIS keys present, R5+R3/floor/ceiling retained, and upload `target_bloat_ms` / `warn_bloat_ms` absent.
- `git diff -- configs/att.yaml | wc -l` → `0`
- Version counts: `pyproject.toml`, `src/wanctl/__init__.py`, and `docker/Dockerfile` each report exactly one `1.42.0` surface; old `1.41.0` package/runtime strings are absent.
- `.venv/bin/python -c "import wanctl; assert wanctl.__version__ == '1.42.0'"` → passed
- `.venv/bin/pytest -o addopts='' tests/test_health_check.py -q` → `178 passed`
- Documentation greps passed for `## v1.42.0`, `VALN-06`, `docsis_mode`, `setpoint_mbps`, `systemctl restart`, `phase201-predeploy-gate.sh`, and `DOCSIS-Aware UL Control Mode`.
- Hot-path release/config slice passed: `.venv/bin/pytest -o addopts='' tests/test_cake_signal.py tests/test_queue_controller.py tests/test_wan_controller.py tests/test_health_check.py tests/test_autorate_config.py -q` → `661 passed`

## Decisions Made

- Kept `setpoint_mbps: 12` but described it as `[ASSUMED]`, not sweep-proven; Phase 201 canary validates it, and a setpoint-specific canary failure should tune down to `10` before testing `14`.
- Preserved R5+R3 because they complement the setpoint clamp: R5 prevents YELLOW push-down and R3 remains a harmless backstop if future tuning lowers `factor_down_yellow`.
- Left VALN-06 open despite listing it in plan frontmatter; this plan prepares release/config/docs surfaces, while live canary Plan 201-11 and soak Plan 201-12 remain the actual closure gates.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Updated local context for version-only documentation hook**
- **Found during:** Task 2 commit
- **Issue:** The pre-commit documentation hook prompted after version/config surfaces changed. The plan's user-facing docs update was Task 3, but the task-atomic version commit still needed hook satisfaction without bypassing hooks.
- **Fix:** Added a concise `.claude/context.md` note that Plan 201-06 was in progress, Spectrum YAML had opted into DOCSIS mode, version surfaces were being bumped, and release docs would follow in the same plan.
- **Files modified:** `.claude/context.md`
- **Verification:** Retried the commit with hooks; documentation check passed.
- **Committed in:** `30294d7`

---

**Total deviations:** 1 auto-fixed (1 Rule 3 blocking)
**Impact on plan:** No production code or operator behavior changed beyond the plan; the fix only satisfied required project documentation-hook context while preserving atomic task commits.

## Issues Encountered

- The first Task 2 commit attempt stopped at the interactive documentation hook. It was resolved by updating `.claude/context.md` and retrying the commit normally with hooks enabled.
- Pre-existing unrelated working-tree change remains untouched: `.planning/phases/200-per-direction-rtt-bloat-thresholds/200-REVIEWS.md`.

## Known Stubs

None. No placeholder, TODO/FIXME, mock-data, or hardcoded-empty UI-flow stubs were introduced in the plan-scoped files.

## Threat Flags

None. This plan changed checked-in YAML, release metadata, and operator documentation. It introduced no new network endpoint, auth path, file-access pattern, or schema trust boundary beyond the documented repo config → production config migration surface already covered by the plan threat model.

## User Setup Required

None - no external service configuration required by this plan. Operators still need the later Plan 201-07/08/11 deploy/canary flow before production restart.

## Next Phase Readiness

Ready for Plan 201-07 (`predeploy-gate`). The repo-side Spectrum YAML now represents the v1.42 desired state, docs warn that a service restart is required, and the next gate can enforce that production `/etc/wanctl/spectrum.yaml` strips only the rejected v1.41 R0 keys before deploy.

## Self-Check: PASSED

- Summary file created at `.planning/phases/201-docsis-aware-ul-congestion-control/201-06-SUMMARY.md`.
- Task commits found: `130cb16`, `30294d7`, `76b9a01`.
- Key files verified present: `configs/spectrum.yaml`, `pyproject.toml`, `src/wanctl/__init__.py`, `docker/Dockerfile`, `CHANGELOG.md`, `docs/CONFIGURATION.md`.
- ATT YAML diff verified empty.

---
*Phase: 201-docsis-aware-ul-congestion-control*
*Completed: 2026-05-04*
