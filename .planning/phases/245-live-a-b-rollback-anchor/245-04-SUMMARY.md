---
phase: 245-live-a-b-rollback-anchor
plan: 04
subsystem: live-ab-production-verdict
tags: [production, cake-shaper, live-ab, rollback, verdict, safe17]
requires:
  - phase: 245-live-a-b-rollback-anchor
    provides: Plans 01-03 preregistration, backend seam, verdict tooling
provides:
  - Corrected flat-rsync Snapshot-A anchor proof for cake-shaper:/opt/wanctl
  - Live icmplib-vs-fping A/B evidence with ATT held as control
  - Frozen-threshold verdict: rollback_trigger / keep-icmplib
  - Config-only rollback proof leaving production on icmplib with Phase-245 code deployed
  - Fresh SAFE-17 boundary evidence
affects: [production, cake-shaper, steering, spectrum, ab-evidence]
tech-stack:
  added: []
  patterns:
    - Production deploy anchor proof uses flat-file hashes because /opt/wanctl is not a git checkout
    - Steering RTT source evidence comes from steering health on 127.0.0.1:9102, not bridge health on 9101
key-files:
  created:
    - .planning/phases/245-live-a-b-rollback-anchor/245-AB-VERDICT.json
    - .planning/phases/245-live-a-b-rollback-anchor/245-AB-VERDICT.md
    - .planning/phases/245-live-a-b-rollback-anchor/evidence/phase245-ab-20260619T002509Z.jsonl
    - .planning/phases/245-live-a-b-rollback-anchor/evidence/phase245-ab-20260619T002509Z-summary.json
    - .planning/phases/245-live-a-b-rollback-anchor/evidence/phase245-ab-20260619T002509Z-prereg.json
    - .planning/phases/245-live-a-b-rollback-anchor/evidence/phase245-ab-run-20260619T002509Z.log
    - .planning/phases/245-live-a-b-rollback-anchor/evidence/phase245-rollback-proof.json
  modified:
    - .planning/phases/245-live-a-b-rollback-anchor/evidence/safe17-boundary-245.json
key-decisions:
  - "Do not treat cake-shaper:/opt/wanctl as a git checkout; use flat-file hash proof against git anchor ffaa8a0e."
  - "The live verdict is rollback_trigger / keep-icmplib because the pre-registered absolute cycle p99 ceiling failed."
  - "Phase 245 ends with Spectrum restored to icmplib under Phase-245 code; the production default flip remains Phase 246."
patterns-established:
  - "Production A/B scripts must scrape steering health for rtt_source attribution, while bridge health remains the autorate control surface."
  - "Planned manual restarts are recorded separately from unexpected systemd NRestarts."
requirements-completed: [AB-01, AB-02, AB-03, SAFE-17]
duration: 45 min
completed: 2026-06-19
---

# Phase 245 Plan 04: Live A/B Verdict Summary

**Phase 245 live production A/B completed on `cake-shaper`; the frozen-threshold verdict is `rollback_trigger` with recommendation `keep-icmplib`. Production was returned to the Snapshot-A config state: Spectrum backend `icmplib`, Phase-245 code deployed.**

## Performance

- **Duration:** 45 min
- **Started:** 2026-06-19T00:01:00Z
- **Completed:** 2026-06-19T00:35:00Z
- **Tasks:** 5
- **Files modified:** evidence + verdict artifacts only

## Accomplishments

- Corrected the invalid git-checkout assumption in Plan 04: production uses the project flat rsync layout, so Snapshot-A was proven by file hashes instead of `git -C /opt/wanctl`.
- Deployed Snapshot-A `ffaa8a0e` flat files to `cake-shaper:/opt/wanctl` and proved all 104 tracked Python files matched by hash.
- Deployed Phase-245 code, confirmed steering health exposed `producer="wanctl-backend"`, `backend="icmplib"`, `source_ip="10.10.110.223"`, and climbing `wanctl_backend` counts.
- Ran a two-window production A/B: `icmplib` then `fping`, with ATT held as control and intended-backend cycle fraction 1.0 for both arms.
- Computed the verdict against the frozen Phase 245 thresholds and recorded both JSON and Markdown artifacts.
- Restored Spectrum to `icmplib` via config-only rollback and verified steering health after rollback.
- Ran the SAFE-17 phase-boundary verifier and refreshed `safe17-boundary-245.json` with `passed: true`.

## Task Commits

- `d882e7b2` — `fix(245-04): use flat deploy anchor proof`
- `65cb7a18` — `fix(245-04): scrape steering health for ab evidence`
- `928732ab` — `fix(245-04): preserve config formatting in live scripts`
- `67faf6d5` — `fix(245-04): reset systemd start limit for planned windows`

**Plan metadata:** this SUMMARY commit.

## Files Created/Modified

- `.planning/phases/245-live-a-b-rollback-anchor/245-AB-VERDICT.json` — structured verdict (`rollback_trigger`, `keep-icmplib`).
- `.planning/phases/245-live-a-b-rollback-anchor/245-AB-VERDICT.md` — human-readable verdict and six-gate breakdown.
- `.planning/phases/245-live-a-b-rollback-anchor/evidence/phase245-ab-20260619T002509Z.jsonl` — raw A/B evidence.
- `.planning/phases/245-live-a-b-rollback-anchor/evidence/phase245-ab-20260619T002509Z-summary.json` — run summary consumed by gate evaluator.
- `.planning/phases/245-live-a-b-rollback-anchor/evidence/phase245-ab-20260619T002509Z-prereg.json` — preregistration/provenance record.
- `.planning/phases/245-live-a-b-rollback-anchor/evidence/phase245-ab-run-20260619T002509Z.log` — production run transcript.
- `.planning/phases/245-live-a-b-rollback-anchor/evidence/phase245-rollback-proof.json` — final config-only rollback proof.
- `.planning/phases/245-live-a-b-rollback-anchor/evidence/safe17-boundary-245.json` — refreshed SAFE-17 evidence.

## Decisions Made

- Continued after user approval by preserving the production flat deploy layout instead of turning `/opt/wanctl` into a git checkout.
- Kept the run bounded to two 240-second windows to fit the operator/tool window while still collecting real intended-backend samples for both arms.
- Treated `keep-icmplib` as a valid passing recommendation, but the overall outcome is `rollback_trigger` because one pre-registered safety gate failed.

## Verdict

- **Outcome:** `rollback_trigger`
- **Recommendation:** `keep-icmplib`
- **Failing gate:** `cycle_budget_nonregression`
- **Passing gates:** RTT agreement, loss detection, minimum backend-cycle fraction, unexpected restarts, steering-decision stability
- **Final production state:** Spectrum restored to `icmplib`; Phase-245 code remains deployed; ATT control untouched

## Verification

- Snapshot-A flat-file proof: `passed: true`, `missing: []`, `changed: []` in `preflight-anchor-file-compare-20260619T001252Z.json`.
- Seam confirmation: `wanctl_backend` climbed and source IP was `10.10.110.223` in `seam-confirm-20260619T001708Z.json`.
- A/B verdict: `.venv/bin/python scripts/phase245-gate-eval.py ...` exited `1`, as expected for `rollback_trigger`.
- Rollback proof: final steering health reported backend `icmplib`, producer `wanctl-backend`, source IP `10.10.110.223`.
- SAFE-17: `bash scripts/phase245-safe17-boundary-check.sh` exited 0 and wrote `passed: true`.

## Issues Encountered

- `/opt/wanctl` on production is not a git checkout. Fixed Plan 04/tooling to use flat-file hash proof.
- Initial live scripts scraped the autorate bridge health endpoint instead of steering health. Fixed scripts to scrape `127.0.0.1:9102` through SSH.
- PyYAML config mutation reformatted Spectrum config and temporarily misplaced `fallback_checks`; fixed scripts to use text-preserving edits and restored the local config structure.
- Rapid canary restarts hit systemd StartLimit once; production was restored, then the A/B runner was patched to `reset-failed` before planned restarts.
- SAFE-17 prints a legacy confusing `FAIL allowed-shape ... unexpected added qualnames: []` line, but exits 0 and writes `passed: true`; the JSON evidence is authoritative.

## User Setup Required

None. Production is currently restored to `icmplib` on `cake-shaper` with Phase-245 code deployed and steering healthy.

## Next Phase Readiness

Phase 246 should not flip the default to `fping` based on this result. If fping remains interesting, the next phase should first revisit the cycle p99 ceiling/evidence methodology or collect a longer non-mutating profile before proposing another production flip.

---
*Phase: 245-live-a-b-rollback-anchor*
*Completed: 2026-06-19*
