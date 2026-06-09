---
phase: 227-candidate-diffserv4-wash-deploy-matched-capture
plan: 03
subsystem: production-capture
tags: [spectrum, diffserv4, cake, evidence, production, rollback]
requires:
  - phase: 226-baseline-capture-threshold-lock-snapshot-a
    provides: [Snapshot A anchor, retained besteffort baseline, threshold lock]
  - phase: 227-candidate-diffserv4-wash-deploy-matched-capture
    provides: [marked-EF capture harness, qdisc verification gate]
provides:
  - operator-gated Phase 227 capture runbook
  - mutation-capable Snapshot A rollback script
  - committed Spectrum diffserv4 candidate config and matched-load evidence
affects: [AB-03, AB-04, phase-228-verdict]
key-files:
  created:
    - scripts/phase227-capture-runbook.sh
    - scripts/phase227-rollback.sh
    - .planning/phases/227-candidate-diffserv4-wash-deploy-matched-capture/evidence/qdisc-verify-candidate.json
    - .planning/phases/227-candidate-diffserv4-wash-deploy-matched-capture/evidence/candidate-20260604T163152Z/
  modified:
    - configs/spectrum.yaml
    - scripts/phase226-baseline-capture.sh
    - tests/test_phase227_marked_ef.py
    - .claude/context.md
requirements-completed: [AB-03, AB-04]
duration: checkpointed
completed: 2026-06-04
---

# Phase 227 Plan 03: Candidate diffserv4 Deploy + Matched Capture Summary

**Spectrum is intentionally left live on `diffserv4`; candidate matched-load evidence is committed for Phase 228 verdict review.**

## Performance

- **Started:** 2026-06-04T14:46Z
- **Checkpoint:** production mutation approval required after tooling commits
- **Completed:** 2026-06-04T16:50Z
- **Tasks:** 3

## Accomplishments

- Added `scripts/phase227-capture-runbook.sh`, the operator-gated D-07 runbook for precheck, baseline capture, flip instructions, candidate verification, candidate capture, and abort routing.
- Added `scripts/phase227-rollback.sh`, a real mutation-capable D-09 rollback path that requires `--confirm`, validates Snapshot A besteffort bytes, deploys, restarts, waits for qdisc settle, verifies health/qdisc, and writes rollback proof.
- Split RRUL/netperf and iperf3 reflector surfaces so Flent can use `vultr-chicago` while iperf3 EF/TCP/UDP reference arms use `dallas` on distinct ports.
- Flipped repo Spectrum CAKE mode to `diffserv4` and verified live `spec-router` and `spec-modem` both reported `diffserv4`.
- Captured committed baseline and candidate evidence under the Phase 227 evidence directory, including qdisc proofs, health windows, Flent artifacts, iperf validity, and marked-EF reference records.

## Task Commits

1. **Task 1: Ordered capture-sequence runbook driver** - `2c8752e`
2. **Task 1b: Mutation-capable rollback script** - `677c1b0`
3. **Continuation fix: separate live reference iperf ports** - `080cf28`
4. **Continuation fix: split Flent and iperf reflectors** - `0c22065`
5. **Continuation fix: wait for rollback qdisc settle** - `b954b31`
6. **Task 2/3: Commit live diffserv4 config and evidence** - `d37a3c8`

## Evidence

- `evidence/qdisc-verify-besteffort.json`
- `evidence/qdisc-verify-candidate.json`
- `evidence/qdisc-verify-rollback-late.json`
- `evidence/baseline-20260604T153654Z/`
- `evidence/baseline-20260604T154929Z/`
- `evidence/candidate-20260604T154125Z/`
- `evidence/candidate-20260604T163152Z/`

The final explicit live verification run after continuation returned:

- `QDISC MODE OK: expected diffserv4 got router=diffserv4 modem=diffserv4`
- `HEALTH OK: http://10.10.110.223:9101/health status=healthy`
- `SERVICE OK: active; NRestarts stable at 0`

## Verification

- `bash -n scripts/phase227-capture-runbook.sh` — PASS
- `scripts/phase227-capture-runbook.sh --dry-run ...` — PASS during executor checkpoint setup
- `bash -n scripts/phase227-rollback.sh` — PASS
- `scripts/phase227-rollback.sh --raw-dir /tmp/nonexistent --dry-run ...` — PASS during executor checkpoint setup
- `scripts/phase227-capture-runbook.sh verify` — PASS live qdisc/health/restart guard
- `scripts/phase227-capture-runbook.sh --force-window "operator approved live continuation after partial checkpoint" candidate` — PASS, wrote `candidate-20260604T163152Z`

## Deviations from Plan

### Auto-fixed Issues

1. **Reference-port collisions:** The live sequence needed distinct iperf3 listener ports for unmarked UDP, unmarked TCP, and marked-EF UDP. Fixed in `080cf28` and `0c22065`.
2. **Rollback qdisc settle:** Immediate post-restart qdisc verification can race wanctl's CAKE re-application. Fixed by bounded settle/retry in `b954b31`.

### Execution Deviation

The continuation agent returned an empty result to the orchestrator after making commits and leaving `configs/spectrum.yaml` modified to `diffserv4`. The orchestrator did not trust that return, performed a read-only live qdisc check, confirmed production was already live `diffserv4`, then continued from that state without re-flipping or performing an extra rollback/redeploy cycle.

Impact: the committed evidence includes multiple baseline/candidate attempts from the partial live continuation plus the final explicit candidate run. This is acceptable for Phase 228 review because raw evidence and qdisc proofs are preserved rather than overwritten.

## Current Live State

- Spectrum repo config: `diffserv4`
- Live qdisc: `diffserv4` on both `spec-router` and `spec-modem`
- Health endpoint: healthy at verification time
- `wanctl@spectrum.service`: active with stable `NRestarts=0` at verification time
- Rollback path: `scripts/phase227-rollback.sh --raw-dir <operator-private-snapshot-A-raw-dir> --confirm --out evidence/rollback-proof.json`

## Issues Encountered

- Full post-Wave 1 `tests/` run failed on unrelated historical/version-boundary tests: Docker label version mismatch and archived Phase 220/221 mutation-boundary tests comparing old source floors to current HEAD. Focused Phase 227 tests and live verification passed.
- Pre-commit docs hook required `.claude/context.md` updates for the security-sensitive rollback and live diffserv4 state; those updates were committed.

## User Setup Required

Phase 228 should review the committed evidence and decide whether to keep `diffserv4` live or execute the Snapshot A rollback script.

## Known Stubs

None.

## Threat Flags

Production mutation occurred under explicit operator approval. Rollback is available and gated by `--confirm` plus Snapshot A raw-dir validation.

## Next Phase Readiness

Ready for Plan 227-04 SAFE-13/evidence completeness closeout, then Phase 228 verdict.

## Self-Check: PASSED

- Runbook and rollback scripts exist.
- Candidate config commit exists: `d37a3c8`.
- Live qdisc proof exists: `evidence/qdisc-verify-candidate.json`.
- Candidate evidence exists: `evidence/candidate-20260604T163152Z/`.
- SUMMARY created at `.planning/phases/227-candidate-diffserv4-wash-deploy-matched-capture/227-03-SUMMARY.md`.

---
*Phase: 227-candidate-diffserv4-wash-deploy-matched-capture*
*Completed: 2026-06-04*
