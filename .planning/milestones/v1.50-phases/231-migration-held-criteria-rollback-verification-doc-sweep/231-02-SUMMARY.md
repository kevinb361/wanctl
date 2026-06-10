---
phase: 231-migration-held-criteria-rollback-verification-doc-sweep
plan: 02
subsystem: ops
tags: [rollback, soak, cake-autorate, preflight, systemd]

# Dependency graph
requires:
  - phase: 230-soak-monitor-att-coverage
    provides: external-mode soak monitor parity and ATT live-unit monitoring
  - phase: 231-migration-held-criteria-rollback-verification-doc-sweep
    provides: SOAK-01 operator-accepted migration-held evidence
provides:
  - SOAK-02 rollback verification by documented, live-preflighted, no-mutation provable path
  - Double-gated per-WAN rollback script with dry-run, preflight, and confirm approval guards
  - Both-WAN rollback/return-to-cake evidence with operator decision record
affects: [phase-231, v1.50-closeout, SAFE-14, rollback-runbook]

# Tech tracking
tech-stack:
  added: []
  patterns: [bash double-confirm mutation gates, fake-ssh regression tests, read-only live preflight JSON proof]

key-files:
  created:
    - scripts/phase231-rollback.sh
    - tests/test_phase231_rollback.py
    - .planning/phases/231-migration-held-criteria-rollback-verification-doc-sweep/231-SOAK02-EVIDENCE.md
    - .planning/phases/231-migration-held-criteria-rollback-verification-doc-sweep/evidence/rollback-preflight-att.json
    - .planning/phases/231-migration-held-criteria-rollback-verification-doc-sweep/evidence/rollback-preflight-spectrum.json
    - .planning/phases/231-migration-held-criteria-rollback-verification-doc-sweep/evidence/rollback-dry-run-att.txt
    - .planning/phases/231-migration-held-criteria-rollback-verification-doc-sweep/evidence/rollback-dry-run-spectrum.txt
  modified:
    - .claude/context.md

key-decisions:
  - "[231-02]: Kevin accepted the SOAK-02 provable path on 2026-06-10; no live rollback exercise or production mutation was performed."
  - "[231-02]: PHASE231_START candidate is 55c33a7b646abe3af9208bc1fb0db3677dd25810 for Phase 231 scope accounting."

patterns-established:
  - "Rollback proof can close SOAK-02 without mutation when dry-run commands, live preflight, historical exercise, and operator decision are all committed."
  - "Any future live rollback exercise remains gated by both --confirm and --i-have-operator-approval plus explicit operator checkpoint approval."

requirements-completed: [SOAK-02]

# Metrics
duration: checkpointed; continuation 2min
completed: 2026-06-10
---

# Phase 231 Plan 02: Rollback Verification Provable Path Summary

**Native `wanctl@{wan}` rollback is proven by a double-gated script, live read-only both-WAN preflight evidence, documented rollback/return-to-cake renders, and Kevin's no-mutation acceptance.**

## Performance

- **Duration:** checkpointed; continuation after operator decision took ~2 min
- **Started:** 2026-06-10T13:43:26Z evidence capture; continuation at 2026-06-10T14:06:55Z
- **Completed:** 2026-06-10T14:08:57Z
- **Tasks:** 3/3 complete
- **Files modified:** 8 plan files/artifacts plus `.claude/context.md`
- **PHASE231_START candidate:** `55c33a7b646abe3af9208bc1fb0db3677dd25810`

## Accomplishments

- Added `scripts/phase231-rollback.sh`, a per-WAN rollback runbook script whose default dry-run is local-only, whose preflight is read-only over bounded SSH, and whose mutation path requires both `--confirm` and `--i-have-operator-approval`.
- Added regression coverage proving dry-run emits zero SSH mutation payloads, confirm without approval fails before remote calls, per-WAN unit/qdisc rendering is correct, and preflight proof JSON has the expected shape.
- Captured both-WAN live preflight evidence showing native `wanctl@{wan}` units disabled/inactive, external cake-autorate units active, Conflicts guards present, and watchdog states matching the migration mode.
- Recorded Kevin's operator decision: **Provable path accepted — 2026-06-10, operator: Kevin**. No live rollback exercise, no `--confirm`, and no production mutation occurred.

## Task Commits

Each task was committed atomically:

1. **Task 1: Gated per-WAN rollback script + confirm-gating regression test** — `c62dccbe` (feat)
2. **Task 2: Live read-only preflight both WANs + SOAK-02 evidence artifact** — `f05047ad` (docs)
3. **Task 3: Operator decision — accept provable path** — `d92b729c` (docs)

**Plan metadata:** final docs commit includes this summary plus STATE/ROADMAP/REQUIREMENTS updates.

## Files Created/Modified

- `scripts/phase231-rollback.sh` — double-gated per-WAN rollback/preflight/dry-run procedure renderer.
- `tests/test_phase231_rollback.py` — fake-SSH regression proof for confirm gating, per-WAN rendering, preflight JSON shape, and no `phase226-restore.sh` dependency.
- `.planning/phases/231-migration-held-criteria-rollback-verification-doc-sweep/231-SOAK02-EVIDENCE.md` — SOAK-02 procedure, preflight proof, historical exercise citation, operator decision, and `SOAK-02 PROVABLE-PATH PASS` verdict.
- `.planning/phases/231-migration-held-criteria-rollback-verification-doc-sweep/evidence/rollback-preflight-att.json` — read-only ATT preflight proof JSON.
- `.planning/phases/231-migration-held-criteria-rollback-verification-doc-sweep/evidence/rollback-preflight-spectrum.json` — read-only Spectrum preflight proof JSON.
- `.planning/phases/231-migration-held-criteria-rollback-verification-doc-sweep/evidence/rollback-dry-run-att.txt` — ATT rollback and return-to-cake rendered commands.
- `.planning/phases/231-migration-held-criteria-rollback-verification-doc-sweep/evidence/rollback-dry-run-spectrum.txt` — Spectrum rollback and return-to-cake rendered commands.
- `.claude/context.md` — current operational context updated with SOAK-02 closure and no-mutation decision.

## Decisions Made

- Kevin accepted the recommended SOAK-02 provable path on 2026-06-10; this closes SOAK-02 without exercising production rollback.
- No `--confirm` rollback exercise was run; the production state remains cake-autorate external mode.
- PHASE231_START candidate for subsequent SAFE-14 scope accounting is `55c33a7b646abe3af9208bc1fb0db3677dd25810`.

## Deviations from Plan

### Auto-fixed Issues

None - plan executed exactly as written after the operator checkpoint.

---

**Total deviations:** 0 auto-fixed.
**Impact on plan:** No scope creep; the zero-mutation path was the plan's default and recommended closure.

## Verification Outputs

- `shellcheck -S error scripts/phase231-rollback.sh` — PASS.
- `.venv/bin/pytest tests/test_phase231_rollback.py -q` — PASS (`7 passed in 0.63s`).
- Evidence text checks — PASS: `231-SOAK02-EVIDENCE.md` contains `Provable path accepted — 2026-06-10, operator: Kevin` and `SOAK-02 PROVABLE-PATH PASS`.
- Ordering proof — PASS: `231-SOAK01-EVIDENCE.md` exists and contains `SOAK-01 PASS` before SOAK-02 closure.
- Evidence artifact existence — PASS: both rollback preflight JSON files and both dry-run command captures exist under the phase evidence directory.

## Auth Gates

None.

## Known Stubs

None. Stub scan found only `WAN=""` in `scripts/phase231-rollback.sh`, which is argument-parser initialization, not a user-facing placeholder or unwired data path.

## Threat Flags

None. The security-relevant rollback/mutation surface was already registered in the plan threat model and mitigated by double-confirm gating, read-only preflight, no-mutation dry-run, and committed evidence.

## Issues Encountered

- Pre-commit documentation freshness hook recommended updating project context for security-related rollback text; `.claude/context.md` was updated and the hook then passed normally.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Phase 231 can continue to Plan 03 for the stale-doc sweep and SAFE-14 closeout. SOAK-02 is complete by provable path, with no production mutation and the current cake-autorate external-mode state preserved.

## Self-Check: PASSED

- Summary file exists.
- Task commits found: `c62dccbe`, `f05047ad`, `d92b729c`.
- Evidence artifacts found: both rollback preflight JSON files and both dry-run command captures.
- Operator decision text found in `231-SOAK02-EVIDENCE.md`.
- Final verdict text found: `SOAK-02 PROVABLE-PATH PASS`.

---
*Phase: 231-migration-held-criteria-rollback-verification-doc-sweep*
*Completed: 2026-06-10*
