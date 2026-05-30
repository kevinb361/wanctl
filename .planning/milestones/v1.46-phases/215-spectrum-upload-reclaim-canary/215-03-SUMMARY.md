---
phase: 215-spectrum-upload-reclaim-canary
plan: 03
subsystem: production-canary
tags: [spectrum, upload-reclaim, canary, flent, rollback, cake]

requires:
  - phase: 215-spectrum-upload-reclaim-canary
    provides: Plan 01 gate tooling and Plan 02 Snapshot A rollback anchor
  - phase: 211-production-verification-milestone-closure
    provides: proven deploy + mandatory restart pattern and bound Spectrum health endpoint
provides:
  - same-session leg-A and leg-B tcp_upload evidence for Spectrum upload ceiling 18->20
  - loaded-ceiling proof for the approved single-knob ceiling 20 canary
  - bounded-VOID verdict with targeted rollback proof to ceiling 18
  - final operator report closing RECLAIM-01/02/03
affects: [phase-215-closeout, spectrum-upload-reclaim, future-upload-canary]

tech-stack:
  added: []
  patterns: [single-knob semantic YAML delta, captured gate rc, bounded VOID safe rollback, redacted production evidence]

key-files:
  created:
    - .planning/phases/215-spectrum-upload-reclaim-canary/215-REPORT.md
    - .planning/phases/215-spectrum-upload-reclaim-canary/evidence/leg-a-ceiling18/
    - .planning/phases/215-spectrum-upload-reclaim-canary/evidence/leg-b-ceiling20/
    - .planning/phases/215-spectrum-upload-reclaim-canary/evidence/verdict.json
    - .planning/phases/215-spectrum-upload-reclaim-canary/evidence/rollback-ceiling18/
  modified:
    - configs/spectrum.yaml
    - scripts/phase215-reclaim-gate.sh

key-decisions:
  - "Bounded VOID exhausted on three leg-B attempts, so the safe default was targeted rollback to ceiling 18 rather than keeping an unscorable ceiling 20 canary."
  - "The gate remote-yaml preflight quoting bug was fixed inline because deployed-ceiling validation is correctness-critical for Plan 03 scoring."
  - "Final repo and production Spectrum config intentionally remain at ceiling_mbps=18 after rollback."

patterns-established:
  - "Production canary gates must capture rc and branch on verdict.json, not shell exit alone."
  - "Rollback for config canaries restores the specific YAML leaf and then deploys/restarts/proves the loaded value."

requirements-completed: [RECLAIM-01, RECLAIM-02, RECLAIM-03]

duration: 18min
completed: 2026-05-29
---

# Phase 215 Plan 03: Spectrum Upload Reclaim Canary Summary

**Approved ceiling 18→20 upload canary executed, bounded VOID exhausted, and Spectrum safely rolled back to ceiling 18 with proof.**

## Performance

- **Duration:** 18 min
- **Started:** 2026-05-29T14:51:46Z
- **Completed:** 2026-05-29T15:09:00Z
- **Tasks:** 2 auto tasks after the approved checkpoint
- **Files modified:** 35 evidence/config/tooling/report files

## Accomplishments

- Captured leg-A at ceiling 18 in-session before mutation: p95 `45.9 ms`, p99 `56.3 ms`, upload median `13.743 Mbps`.
- Mutated exactly one YAML leaf (`continuous_monitoring.upload.ceiling_mbps: 18 -> 20`), deployed, restarted `wanctl@spectrum.service`, and proved loaded ceiling 20 via DB row plus CAKE `20000kbit` log.
- Captured three leg-B attempts at ceiling 20 and ran the gate with rc captured; all attempts were VOID due to collapsed measurement windows.
- Followed the safe default: targeted ceiling restore to 18, deploy, restart, DB proof `18`, and post-rollback canary-check evidence.
- Authored `215-REPORT.md` closing RECLAIM-01/02/03 and recording the keep-or-rollback decision.

## Task Commits

Each task was committed atomically:

1. **Task 2: Capture leg-A, mutate one knob, deploy/restart/prove ceiling 20** - `80a5f9a` (feat)
2. **Task 3: Capture leg-B, run gate, bounded VOID, targeted rollback, report** - `964dd5c` (fix)

**Plan metadata:** pending final docs commit.

## Files Created/Modified

- `configs/spectrum.yaml` - Temporarily raised upload ceiling to 20 for the canary, then targeted-restored it to 18 after bounded VOID exhausted.
- `scripts/phase215-reclaim-gate.sh` - Fixed remote-yaml preflight quoting so deployed-ceiling validation works under SSH/sudo.
- `.planning/phases/215-spectrum-upload-reclaim-canary/evidence/leg-a-ceiling18/` - Leg-A manifest, extract, health NDJSON, and flent symlink.
- `.planning/phases/215-spectrum-upload-reclaim-canary/evidence/leg-b-ceiling20/` - Three leg-B attempts, final extract, deploy proof, and manifest.
- `.planning/phases/215-spectrum-upload-reclaim-canary/evidence/verdict.json` - Final gate verdict (`void`) with leg-A-derived bounds and candidate values.
- `.planning/phases/215-spectrum-upload-reclaim-canary/evidence/rollback-ceiling18/` - DB/health/canary-check proof after targeted rollback.
- `.planning/phases/215-spectrum-upload-reclaim-canary/215-REPORT.md` - Operator-facing canary report and requirement closeout.

## Decisions Made

- Bounded VOID exhausted after the initial leg-B plus two retries; the canary was not kept because production should not stay at ceiling 20 on an unscorable window.
- Final repo and deployed production state are intentionally back at `ceiling_mbps: 18`.
- `scripts/libreqos-cli.mjs` output was recorded as non-gating corroboration only; it did not influence the verdict.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Fixed gate remote-yaml preflight quoting**
- **Found during:** Task 3 (gate invocation)
- **Issue:** `scripts/phase215-reclaim-gate.sh --remote-yaml` attempted to pass a heredoc through `ssh` with literal escaped newlines, causing a remote shell syntax error before `verdict.json` could be written.
- **Fix:** Replaced the remote heredoc with a `sudo -n python3 -c` preflight that reads `/etc/wanctl/spectrum.yaml` and extracts `continuous_monitoring.upload.ceiling_mbps`.
- **Files modified:** `scripts/phase215-reclaim-gate.sh`
- **Verification:** `bash -n scripts/phase215-reclaim-gate.sh`; gate then successfully emitted `verdict.json` with rc captured.
- **Committed in:** `964dd5c`

---

**Total deviations:** 1 auto-fixed (Rule 3 blocking issue)
**Impact on plan:** Required for the planned deployed-ceiling preflight; no change to canary scope or production knobs.

## Issues Encountered

- Leg-B attempt 1, retry 1, and retry 2 all scored `void` due to `collapsed_measurement_window`; after the bounded retry budget, rollback was executed exactly per the plan.
- The documentation pre-commit hook recommended docs for security-shaped evidence commits; commits used the existing `SKIP_DOC_CHECK=1` hook path without `--no-verify`.
- Pre-existing untracked `scripts/libreqos-cli.mjs` remains uncommitted and untouched except for being executed as the plan's optional non-gating corroboration source.

## Known Stubs

None.

## Authentication Gates

None.

## Threat Flags

None. No new endpoints, auth paths, file-access patterns, or trust-boundary schema changes were introduced; the only production mutation was an existing YAML config value and existing evidence paths.

## Verification

- `scripts/phase213-baseline-capture.sh --bind-map spectrum=10.10.110.226 --wans spectrum --tests tcp_upload --flent-duration 120 ... --check-prereqs` — PASS.
- Leg-A extractor — PASS: p95 `45.9`, p99 `56.3`, upload median `13.743`.
- Semantic YAML delta assertion — PASS: only `continuous_monitoring.upload.ceiling_mbps: 18 -> 20` before deploy.
- Ceiling 20 deploy proof — PASS: DB row `20`, CAKE log contains `20000kbit`, canary-check captured.
- Gate rc capture — PASS: final `gate-rc.txt` = `2`, `verdict.json.verdict` = `void`.
- Rollback proof — PASS: repo config ceiling `18`, DB row `18`, canary-check captured after restart.
- Evidence D-08 grep — PASS: no `ROUTER_PASSWORD`, `DISCORD_WEBHOOK`, or password-shaped values found under `evidence/`.
- `bash -n scripts/phase215-reclaim-gate.sh` — PASS.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Phase 215 can close with a conservative no-keep outcome: the canary was executed safely, but no scorable WIN was obtained. A future upload reclaim attempt should treat measurement collapse/path quality as a prerequisite rather than immediately trying ceiling 22 or another upload knob.

## Self-Check: PASSED

- Key files exist: `215-REPORT.md`, `evidence/leg-a-ceiling18/leg-a-extract.json`, `evidence/leg-b-ceiling20/leg-b-extract.json`, `evidence/verdict.json`, `evidence/rollback-ceiling18/db-row.redacted.txt`.
- Task commits found: `80a5f9a`, `964dd5c`.
- Final config state verified as `continuous_monitoring.upload.ceiling_mbps: 18`.

---
*Phase: 215-spectrum-upload-reclaim-canary*
*Completed: 2026-05-29*
