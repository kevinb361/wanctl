---
phase: 201-docsis-aware-ul-congestion-control
plan: 07
subsystem: deploy-gate
tags: [phase-201, predeploy, spectrum, fail-closed, deploy, valn-06]

requires:
  - phase: 201-02-wave-0-tests
    provides: Predeploy gate pytest contract stubs
  - phase: 201-06-spectrum-yaml-and-version
    provides: Desired v1.42 Spectrum YAML state with R0 keys stripped and DOCSIS mode enabled
provides:
  - Spectrum-scoped fail-closed predeploy gate for rejected v1.41 upload threshold keys
  - deploy.sh integration that runs the gate before /opt/wanctl rsync for Spectrum only
  - Test coverage for gate PASS/BLOCK/ABORT behavior, deploy exit-code propagation, missing-gate fail-closed behavior, Spectrum default derivation, and ATT/non-Spectrum skip behavior
affects: [201-08-canary-script-extension, 201-11-canary-execution, VALN-06, deploy]

tech-stack:
  added: []
  patterns:
    - Shell predeploy gate with three-way exit semantics: PASS=0, BLOCK=1, ABORT=2
    - Spectrum-only deploy gating; non-Spectrum paths skip without reading Spectrum YAML
    - Environment-overridable PREDEPLOY_GATE with fail-closed missing/non-executable handling

key-files:
  created:
    - scripts/phase201-predeploy-gate.sh
    - .planning/phases/201-docsis-aware-ul-congestion-control/201-07-SUMMARY.md
  modified:
    - scripts/deploy.sh
    - tests/test_phase201_predeploy_gate.py
    - .claude/context.md

key-decisions:
  - "Implemented RESEARCH §9 Option B: fail closed with operator-manual reconciliation; auto-strip is intentionally not implemented."
  - "Scoped deploy integration to WAN_NAME=spectrum so ATT/non-Spectrum deploys do not inspect /etc/wanctl/spectrum.yaml."
  - "Derived REMOTE_SSH_TARGET from TARGET_HOST and REMOTE_YAML_PATH from /etc/wanctl/${WAN_NAME}.yaml only for Spectrum gate invocation when unset."
  - "Did not mark VALN-06 complete; this plan provides the deploy safety gate, while Plan 201-11 live canary and Plan 201-12 soak remain the closure gates."

patterns-established:
  - "Use gate_rc=0; gate || gate_rc=$? for shell fail-closed propagation, never if ! gate."
  - "Use PHASE201_LOCAL_YAML_OVERRIDE only for local gate tests; production path reads via SSH + sudo cat + yaml.safe_load."

requirements-completed: []

duration: 3min
completed: 2026-05-04
---

# Phase 201 Plan 07: Predeploy Gate Summary

**Spectrum-only deploy preflight now blocks rejected v1.41 upload-threshold YAML before any `/opt/wanctl` rsync.**

## Performance

- **Duration:** 3 min active execution
- **Started:** 2026-05-04T22:46:16Z
- **Completed:** 2026-05-04T22:49:19Z
- **Tasks:** 2/2 complete
- **Files modified:** 4 plan-scoped files plus this summary

## Accomplishments

- Added `scripts/phase201-predeploy-gate.sh` as a 158-line executable gate with `set -euo pipefail`, safe absolute `REMOTE_YAML_PATH` validation, SSH+sudo YAML reads, local test override, and three exit classes: PASS=0, BLOCK=1, ABORT=2.
- Gate BLOCK messages identify the exact rejected key (`target_bloat_ms` or `warn_bloat_ms`) or missing `setpoint_mbps` under `docsis_mode: true`, and instruct the operator to manually reconcile YAML; auto-strip is not implemented.
- Wired `scripts/deploy.sh` at lines 160-188, before the line 190 rsync to `/opt/wanctl`, so Spectrum deploys run the gate before code movement.
- Implemented the Codex HIGH #4 amendment: `WAN_NAME=att` and other non-Spectrum deploys log a skip and do not touch the gate; Spectrum derives `REMOTE_SSH_TARGET=cake-shaper` from `TARGET_HOST` and `REMOTE_YAML_PATH=/etc/wanctl/spectrum.yaml` when unset.
- Expanded `tests/test_phase201_predeploy_gate.py` to 11 passing cases covering gate shell behavior and deploy integration failure/skip paths.

## Task Commits

Each task was committed atomically:

1. **Task 1: Author scripts/phase201-predeploy-gate.sh with three-way fail-closed exit** — `67eeb16` (`feat`)
2. **Task 2: Wire scripts/deploy.sh to invoke the predeploy gate before rsync** — `308bcb1` (`feat`)
3. **Task 2 cleanup: Remove Wave 0 skip guard now that the gate exists** — `726923e` (`test`)

**Plan metadata:** final docs commit created after this SUMMARY and state/roadmap updates.

## Files Created/Modified

- `scripts/phase201-predeploy-gate.sh` — New executable predeploy gate; local test override, remote dependency precheck, path validation, safe YAML parse, and operator-actionable BLOCK messages.
- `scripts/deploy.sh` — Adds Phase 201 D-15 gate block immediately before rsync; Spectrum-only scope; missing gate exits 2; gate exit 1/2 propagates accurately.
- `tests/test_phase201_predeploy_gate.py` — Keeps the six gate shell tests green and adds five deploy integration tests for static ordering, exit-code propagation, missing gate fail-closed, default env derivation, and non-Spectrum skip.
- `.claude/context.md` — Updated local operational context for the documentation hook to reflect the new deploy gate behavior.

## Gate Script Exit Conditions and Messages

| Exit | Meaning | Operator-facing behavior |
|------|---------|--------------------------|
| 0 | PASS | Logs `PASS: continuous_monitoring.upload is clean...` when rejected keys are absent and `docsis_mode: true` has `setpoint_mbps`. |
| 1 | BLOCK | Prints `BLOCK:` for `target_bloat_ms`, `warn_bloat_ms`, or `docsis_mode: true` without `setpoint_mbps`, with manual reconciliation instructions. |
| 2 | ABORT | Prints `ABORT:` for malformed/missing env, unsafe remote path, missing SSH/python dependencies, unreadable YAML, empty YAML, or parse errors. |

Auto-strip confirmation: **auto-strip is NOT implemented**; the gate is read-only and uses fail-closed operator-manual reconciliation per RESEARCH §9 Option B.

## Verification

- `test -x scripts/phase201-predeploy-gate.sh` → passed.
- Gate acceptance greps passed: one `set -euo pipefail`, one `EXIT_BLOCK=1`, one `EXIT_ABORT=2`, `PHASE201_LOCAL_YAML_OVERRIDE` present, `validate_remote_yaml_path` present, rejected-key strings present, exactly one `yaml.safe_load`, exactly one remote `python3 -c "import yaml"` precheck, and no `phase201-reconcile-yaml` reference.
- `bash -n scripts/phase201-predeploy-gate.sh` → passed.
- `bash -n scripts/deploy.sh` → passed.
- Deploy acceptance greps passed: gate mention before rsync, `D-15` traceability, fail-closed missing-gate check, no legacy warning/skip pattern, `|| gate_rc=$?` propagation, no `if ! phase201-predeploy-gate` anti-pattern, env-overridable `PREDEPLOY_GATE`, and default `REMOTE_YAML_PATH=/etc/wanctl/spectrum.yaml` in the gate.
- `.venv/bin/pytest -o addopts='' tests/test_phase201_predeploy_gate.py -v` → `11 passed`.

## Decisions Made

- Implemented fail-closed manual reconciliation instead of auto-strip because production YAML changes are operator decisions and R5/R3 are intentionally retained while R0 threshold keys are rejected.
- Scoped deploy integration by `WAN_NAME=spectrum`; this preserves D-17 byte-identity expectations for ATT/non-Spectrum deploys and avoids inspecting Spectrum YAML for unrelated WANs.
- Preserved deploy rsync/restart behavior; the only deploy behavior change is the new pre-rsync gate block.
- Left `VALN-06` open despite plan frontmatter listing it, because this plan closes D-15 deploy safety only; live canary/soak evidence remains required for requirement closure.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Updated local context for documentation hook**
- **Found during:** Task 1 and Task 2 commits
- **Issue:** The project documentation hook stopped security/deploy-related commits until local context reflected the new predeploy behavior.
- **Fix:** Updated `.claude/context.md` with the Phase 201 Plan 07 gate status, Spectrum-only deploy integration, fail-closed behavior, and non-Spectrum skip rule.
- **Files modified:** `.claude/context.md`
- **Verification:** Retried commits with hooks enabled; documentation check passed.
- **Committed in:** `67eeb16`, `308bcb1`

---

**Total deviations:** 1 auto-fixed (Rule 3 blocking)
**Impact on plan:** No production code behavior changed beyond the planned gate; the context update only satisfied required repository documentation hygiene.

## Issues Encountered

- Pre-commit documentation checks prompted twice on security/deploy changes; resolved by updating `.claude/context.md` and retrying the commits normally.
- Pre-existing unrelated working-tree change remains untouched: `.planning/phases/200-per-direction-rtt-bloat-thresholds/200-REVIEWS.md`.

## Known Stubs

None. The Wave 0 skip guard in `tests/test_phase201_predeploy_gate.py` was removed after the gate script landed; no TODO/FIXME, placeholder, mock-data UI flow, or hardcoded-empty output stubs were introduced.

## Threat Flags

None beyond the plan threat model. This plan introduced a remote YAML read and deploy preflight trust boundary already covered by T-201-29 through T-201-35; the implementation validates remote paths, uses read-only `sudo cat`, does not auto-strip, logs PASS/BLOCK/ABORT, and fails closed on missing gate/dependencies.

## User Setup Required

None for repo-side completion. Operators must manually reconcile production `/etc/wanctl/spectrum.yaml` if the gate reports BLOCK before any future Spectrum deploy.

## Next Phase Readiness

Ready for Plan 201-08 (`canary-script-extension`). The deploy path now prevents Spectrum v1.42 code from moving while rejected v1.41 upload threshold keys remain in production YAML, while ATT/non-Spectrum deployments continue without Spectrum-specific gate inspection.

## Self-Check: PASSED

- Summary file created at `.planning/phases/201-docsis-aware-ul-congestion-control/201-07-SUMMARY.md`.
- Task commits found: `67eeb16`, `308bcb1`, `726923e`.
- Key files verified present: `scripts/phase201-predeploy-gate.sh`, `scripts/deploy.sh`, `tests/test_phase201_predeploy_gate.py`.
- Final verification passed with `11 passed` in `tests/test_phase201_predeploy_gate.py`.
- Gate integration line ordering verified: deploy gate block starts at `scripts/deploy.sh:160`; rsync executes at `scripts/deploy.sh:190`.

---
*Phase: 201-docsis-aware-ul-congestion-control*
*Completed: 2026-05-04*
