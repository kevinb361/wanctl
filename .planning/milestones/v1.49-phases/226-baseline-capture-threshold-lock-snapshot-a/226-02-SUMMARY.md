---
phase: 226-baseline-capture-threshold-lock-snapshot-a
plan: "02"
subsystem: validation
tags: [snapshot-a, spectrum, cake, qdisc, nftables, rollback, evidence]

requires:
  - phase: 225-dscp-survival-trace
    provides: [DSCP-03 proceed verdict for Spectrum diffserv4 A/B]
provides:
  - Spectrum CAKE Snapshot A wrapper with redacted evidence/raw restore split
  - Redacted Snapshot A rollback-anchor evidence for repo/deployed spectrum.yaml, qdisc state, bridge qos nft, git ref, and health
  - Operator-private raw restore source path for /etc/wanctl/spectrum.yaml
affects: [phase-226-baseline, phase-228-rollback, SAFE-13]

tech-stack:
  added: []
  patterns: [read-only SSH capture, redacted committable evidence, operator-private raw restore source]

key-files:
  created:
    - scripts/phase226-snapshot-a.sh
    - .planning/phases/226-baseline-capture-threshold-lock-snapshot-a/evidence/snapshot-a/MANIFEST.md
    - .planning/phases/226-baseline-capture-threshold-lock-snapshot-a/evidence/snapshot-a/artifact-sha256.txt
    - .planning/phases/226-baseline-capture-threshold-lock-snapshot-a/evidence/snapshot-a/bridge-qos.live.txt
    - .planning/phases/226-baseline-capture-threshold-lock-snapshot-a/evidence/snapshot-a/deployed-spectrum.redacted.yaml
    - .planning/phases/226-baseline-capture-threshold-lock-snapshot-a/evidence/snapshot-a/pre-deploy-git-ref.txt
    - .planning/phases/226-baseline-capture-threshold-lock-snapshot-a/evidence/snapshot-a/repo-bridge-qos.nft
    - .planning/phases/226-baseline-capture-threshold-lock-snapshot-a/evidence/snapshot-a/repo-spectrum.redacted.yaml
    - .planning/phases/226-baseline-capture-threshold-lock-snapshot-a/evidence/snapshot-a/repo-version.txt
    - .planning/phases/226-baseline-capture-threshold-lock-snapshot-a/evidence/snapshot-a/snapshot-a-health.bound.redacted.json
    - .planning/phases/226-baseline-capture-threshold-lock-snapshot-a/evidence/snapshot-a/tc-qdisc-spec-modem.txt
    - .planning/phases/226-baseline-capture-threshold-lock-snapshot-a/evidence/snapshot-a/tc-qdisc-spec-router.txt
  modified:
    - .claude/context.md

key-decisions:
  - "Snapshot A raw restore bytes remain operator-private under /tmp/opencode/wanctl-phase226-snapshot-a-raw-20260604T1115Z and are not committed."
  - "Deployed and repo redacted spectrum.yaml SHA-256 values are equal, so Snapshot A config_equality verdict is equal."

patterns-established:
  - "Spectrum Snapshot A mirrors the Phase 224 split: committed redacted evidence plus uncommitted mode-0600 restore source."
  - "The manifest documents config-artifact equality and Phase 228 command identity without claiming a live restore drill."

requirements-completed: [AB-01, SAFE-13]

duration: 5min
completed: 2026-06-04
---

# Phase 226 Plan 02: Snapshot A rollback anchor Summary

**Read-only Spectrum CAKE Snapshot A anchor with redacted evidence, operator-private raw restore source, and Phase 228 restore-command identity.**

## Performance

- **Duration:** 5 min
- **Started:** 2026-06-04T11:00:58Z
- **Completed:** 2026-06-04T11:05:28Z
- **Tasks:** 2
- **Files modified:** 14

## Accomplishments

- Added `scripts/phase226-snapshot-a.sh`, a read-only Spectrum CAKE capture wrapper for repo/deployed `spectrum.yaml`, `tc -s qdisc` on `spec-router` and `spec-modem`, live/repo `bridge qos` nft rules, pre-deploy git refs, and Spectrum `/health`.
- Captured Snapshot A evidence under `.planning/phases/226-baseline-capture-threshold-lock-snapshot-a/evidence/snapshot-a/` with redacted YAML and MANIFEST.
- Kept unredacted raw restore bytes outside git at `/tmp/opencode/wanctl-phase226-snapshot-a-raw-20260604T1115Z` with directory mode `0700` and raw files mode `0600`.

## Task Commits

Each task was committed atomically:

1. **Task 1: Write the Spectrum CAKE Snapshot A capture wrapper** - `7e84f43` (feat)
2. **Task 2: Run Snapshot A and commit the redacted evidence tree** - `86cbf8e` (feat)

**Plan metadata:** pending final metadata commit

## Files Created/Modified

- `scripts/phase226-snapshot-a.sh` - Read-only Snapshot A wrapper with raw-dir containment refusal, redaction, capture, SHA inventory, manifest, and required-artifact assertions.
- `.planning/phases/226-baseline-capture-threshold-lock-snapshot-a/evidence/snapshot-a/MANIFEST.md` - Snapshot A manifest with source posture, equality verdict, raw restore path, artifacts, and Phase 228 restore command.
- `.planning/phases/226-baseline-capture-threshold-lock-snapshot-a/evidence/snapshot-a/*.yaml` - Redacted repo/deployed Spectrum config evidence.
- `.planning/phases/226-baseline-capture-threshold-lock-snapshot-a/evidence/snapshot-a/tc-qdisc-spec-router.txt` - Read-only qdisc evidence for Spectrum router-side NIC.
- `.planning/phases/226-baseline-capture-threshold-lock-snapshot-a/evidence/snapshot-a/tc-qdisc-spec-modem.txt` - Read-only qdisc evidence for Spectrum modem-side NIC.
- `.planning/phases/226-baseline-capture-threshold-lock-snapshot-a/evidence/snapshot-a/bridge-qos.live.txt` - Read-only live bridge qos nft evidence.
- `.planning/phases/226-baseline-capture-threshold-lock-snapshot-a/evidence/snapshot-a/repo-bridge-qos.nft` - Repo bridge qos nft copy for comparison.
- `.planning/phases/226-baseline-capture-threshold-lock-snapshot-a/evidence/snapshot-a/pre-deploy-git-ref.txt` - Commit/config tree/blob anchor for Snapshot A.
- `.planning/phases/226-baseline-capture-threshold-lock-snapshot-a/evidence/snapshot-a/snapshot-a-health.bound.redacted.json` - Spectrum `/health` evidence.
- `.planning/phases/226-baseline-capture-threshold-lock-snapshot-a/evidence/snapshot-a/artifact-sha256.txt` - SHA-256 inventory for committed artifacts and operator-private raw restore source.
- `.claude/context.md` - Local technical context updated so pre-commit doc freshness is satisfied.

## Decisions Made

- Raw restore artifacts are intentionally outside the repo at `/tmp/opencode/wanctl-phase226-snapshot-a-raw-20260604T1115Z`; only the path and SHA are committed.
- The manifest records `config_equality: equal` because deployed and repo redacted `spectrum.yaml` SHA-256 values match.
- The restore command is documented as manifest text only; no live restore drill or install command was executed.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed redaction validator false failure from preserved inline comments**
- **Found during:** Task 2 (Run Snapshot A and commit the redacted evidence tree)
- **Issue:** The initial redactor preserved inline comments after secret-bearing values (for example `password: REDACTED # ...`), which failed the plan's stricter validator requiring the value position to be only `REDACTED`, empty, or null.
- **Fix:** Updated `redact_yaml` to write secret-bearing keys as `REDACTED` without preserving the original inline comment, then regenerated the evidence tree.
- **Files modified:** `scripts/phase226-snapshot-a.sh`, regenerated `evidence/snapshot-a/*.yaml`, `MANIFEST.md`, and `artifact-sha256.txt`.
- **Verification:** Redaction validator passed: every secret-bearing key in committed YAML is followed by `REDACTED` with no real value.
- **Committed in:** `86cbf8e` (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 bug).
**Impact on plan:** Correctness-only fix required for the committed redaction gate; no production or architecture scope change.

## Issues Encountered

- Pre-commit doc freshness hook required a context documentation update for security-sensitive capture/redaction script changes; `.claude/context.md` was updated in the task commits.

## User Setup Required

None - no external service configuration required.

## Known Stubs

None. The only empty-string assignments found are argument defaults (`OUTPUT_DIR=""`, `RAW_DIR=""`) and do not flow to UI rendering or committed evidence.

## Next Phase Readiness

Plan 226-01 can now use Snapshot A as the rollback anchor before baseline load generation. Plan 226-04 can use the MANIFEST restore command and raw restore path for dry-run restore proof.

## Self-Check: PASSED

- FOUND: `scripts/phase226-snapshot-a.sh`
- FOUND: `evidence/snapshot-a/MANIFEST.md`
- FOUND: `226-02-SUMMARY.md`
- FOUND commit: `7e84f43`
- FOUND commit: `86cbf8e`

---
*Phase: 226-baseline-capture-threshold-lock-snapshot-a*
*Completed: 2026-06-04*
