---
phase: 239-seam-refactor-icmplibbackend-byte-identical
plan: 03
subsystem: testing
tags: [safe-17, verifier, ast, source-diff, boundary-evidence]

requires:
  - phase: 239-seam-refactor-icmplibbackend-byte-identical
    provides: RttBackend seam and additive RTTMeasurement.probe() from Plans 01 and 02
provides:
  - Fail-closed SAFE-17 v1.53 boundary checker anchored at v1.52
  - AST protected-body verifier covering RTTSnapshot, RTTMeasurement.__init__, hot-path RTT bodies, and WANController.measure_rtt
  - Complete allowed-diff-shape guard proving rtt_measurement.py only adds RTTMeasurement.probe
  - Tree-safe negative tests and passed:true phase-boundary evidence
affects: [phase-240-config-validator, phase-241-fping-backend, phase-246-safe17-closeout]

tech-stack:
  added: []
  patterns: [fail-closed git diff allowlist, AST source-segment identity guard, disposable linked worktree negative tests]

key-files:
  created:
    - scripts/phase239-protected-body-diff.py
    - scripts/phase239-safe17-boundary-check.sh
    - tests/test_phase239_safe17_verifier.py
    - .planning/phases/239-seam-refactor-icmplibbackend-byte-identical/evidence/safe17-boundary-239.json
  modified: []

key-decisions:
  - "Layer 3 compares RTTMeasurement by header/class-level statements/pre-existing child methods rather than whole-class source so the single additive probe() child is allowed without hiding drift."
  - "Negative drift tests mutate disposable detached git worktrees and commit there with inline identity, keeping the real src/wanctl tree clean while bypassing the verifier's dirty-tree precheck."

patterns-established:
  - "SAFE-17 Phase 239 evidence requires all three layers: path allowlist, protected-body identity, and complete allowed-diff shape."
  - "The allowed-shape helper is pure/importable so the container-plus-one-added-method case is unit-tested without git or filesystem state."

requirements-completed: [SAFE-17]

duration: 6min
completed: 2026-06-15
---

# Phase 239 Plan 03: SAFE-17 v1.53 Boundary Verifier Summary

**Fail-closed SAFE-17 verifier with path allowlist, AST protected-body identity, complete allowed-diff-shape proof, and passed boundary evidence**

## Performance

- **Duration:** 6 min
- **Started:** 2026-06-15T17:12:23Z
- **Completed:** 2026-06-15T17:18:45Z
- **Tasks:** 3/3 completed
- **Files modified:** 4

## Accomplishments

- Added `scripts/phase239-protected-body-diff.py`, a stdlib AST verifier that compares protected nodes byte-for-byte against `v1.52` and proves the full `rtt_measurement.py` shape permits only `RTTMeasurement.probe`.
- Added `scripts/phase239-safe17-boundary-check.sh`, chaining dirty-tree fail-closed checks, a two-file v1.53 allowlist, the AST protected-body/shape gate, and JSON evidence emission.
- Added eight verifier tests covering boundary pass, out-of-allowlist drift, protected-body drift, RTTSnapshot drift, `RTTMeasurement.__init__` drift, module-constant drift, unresolved anchors, and the positive container-plus-added-method helper case.
- Generated `safe17-boundary-239.json` with `passed:true`, `all_identical:true`, `allowed_shape_ok:true`, and `added_qualnames == ["RTTMeasurement.probe"]`.

## Task Commits

Each task was committed atomically:

1. **Task 1: AST protected-body drift extractor + allowed-diff-shape verifier** - `ade7c0b2` (feat)
2. **Task 2: Fail-closed SAFE-17 v1.53 allowlist verifier** - `4b842c20` (feat)
3. **Task 3: Tree-safe negative tests + allowed-shape positive unit test + phase-boundary evidence** - `143915fd` (test)
4. **Task 3 evidence refresh: SAFE-17 boundary evidence after task test commit** - `a4601499` (test)

**Plan metadata:** pending final docs commit

## Files Created/Modified

- `scripts/phase239-protected-body-diff.py` - AST protected-node and allowed-shape verifier with pure `compare_allowed_shape()` helper.
- `scripts/phase239-safe17-boundary-check.sh` - v1.53 SAFE-17 shell boundary checker with dirty-tree precheck, allowlist regex, helper chaining, and evidence output confinement.
- `tests/test_phase239_safe17_verifier.py` - Eight pytest cases proving pass and fail-closed behavior without dirtying the real tree.
- `.planning/phases/239-seam-refactor-icmplibbackend-byte-identical/evidence/safe17-boundary-239.json` - Phase-boundary SAFE-17 evidence record.

## Verification

- PASS: `bash -n scripts/phase239-safe17-boundary-check.sh`
- PASS: `.venv/bin/python scripts/phase239-protected-body-diff.py --anchor v1.52`
- PASS: `.venv/bin/pytest -o addopts='' tests/test_phase239_safe17_verifier.py -q` → `8 passed`
- PASS: `git diff --quiet -- src/wanctl/`
- PASS: `bash scripts/phase239-safe17-boundary-check.sh`
- PASS: JSON evidence asserted `passed:true`, `all_identical:true`, `allowed_shape_ok:true`, and `added_qualnames == ["RTTMeasurement.probe"]`.

## Decisions Made

- Compared `RTTMeasurement` by parts in Layer 3 because adding `probe()` necessarily changes the whole class segment; every pre-existing child method is still byte-identical.
- Kept the shell checker's path allowlist to exactly `rtt_backend.py` and `rtt_measurement.py`; no `wan_controller.py`, `interfaces.py`, or package-version surface was admitted.
- Used detached linked worktrees for negative tests so mutations are committed in disposable trees and the real production tree remains clean.

## Deviations from Plan

None - plan executed exactly as written.

## Known Stubs

None.

## Threat Flags

None - all new file-writing and git-anchor surfaces were planned verifier surfaces and are covered by SAFE-17 tests and evidence confinement.

## Issues Encountered

- Repository documentation hooks are interactive for new functions/classes. Per the hook's supported noninteractive path, task commits used `SKIP_DOC_CHECK=1`; hooks still ran and were not bypassed with `--no-verify`.
- Boundary evidence was refreshed after the test/evidence task commit so the committed evidence reflects the current phase-boundary source state before plan metadata closeout.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Ready for Phase 240 to extend configuration/validator surfaces under the SAFE-17 discipline.
- Future SAFE-17 allowlists should grow deliberately by phase; Phase 239's verifier proves the seam refactor stayed bounded to `rtt_backend.py` plus additive `RTTMeasurement.probe()`.

## Self-Check: PASSED

- FOUND: `scripts/phase239-protected-body-diff.py`
- FOUND: `scripts/phase239-safe17-boundary-check.sh`
- FOUND: `tests/test_phase239_safe17_verifier.py`
- FOUND: `.planning/phases/239-seam-refactor-icmplibbackend-byte-identical/evidence/safe17-boundary-239.json`
- FOUND: `.planning/phases/239-seam-refactor-icmplibbackend-byte-identical/239-03-SUMMARY.md`
- FOUND commits: `ade7c0b2`, `4b842c20`, `143915fd`, `a4601499`

---
*Phase: 239-seam-refactor-icmplibbackend-byte-identical*
*Completed: 2026-06-15*
