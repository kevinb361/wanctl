---
phase: 200-per-direction-rtt-bloat-thresholds
plan: 14
subsystem: production-validation
tags: [valn-06, spectrum, saturation-canary, rollback, gap-closure]

# Dependency graph
requires:
  - phase: 200-per-direction-rtt-bloat-thresholds
    plan: 10
    provides: Approved R5+R3 Spectrum upload remediation
  - phase: 200-per-direction-rtt-bloat-thresholds
    plan: 11
    provides: Hardened canary script with live baseline RTT fields and safe remote YAML validation
provides:
  - Attempt 3 production deploy timeline for the gap-closure binary
  - Attempt 3 saturation canary evidence with explicit fail branch handling
  - D-10 rollback evidence using /opt/wanctl-prephase200-gap-20260504T132936Z.tar.gz
  - Explicit skipped soak record for the canary-fail branch
affects: [VALN-06, phase-200-closeout, plan-200-15, docsis-upload-gap]

# Tech tracking
tech-stack:
  added: []
  patterns: [fail-closed production canary, rollback-before-soak branch, evidence-first deploy log]

key-files:
  created:
    - .planning/phases/200-per-direction-rtt-bloat-thresholds/200-14-SUMMARY.md
    - .planning/phases/200-per-direction-rtt-bloat-thresholds/canary/20260504T133207Z/verdict.json
  modified:
    - .planning/phases/200-per-direction-rtt-bloat-thresholds/200-DEPLOY-LOG.md
    - .planning/phases/200-per-direction-rtt-bloat-thresholds/200-SOAK-LOG.md

key-decisions:
  - "Attempt 3 canary verdict=fail triggered immediate D-10 rollback; Task 4 soak was skipped per fail-closed branch semantics."
  - "Plan 200-15 should close Phase 200 as gaps_found: canary improved from 122 to 4 floor samples but any loaded-window floor hit still fails VALN-06."

patterns-established:
  - "Production gap-closure retries must record the exact rollback tarball path before deploy and use that same path on fail/abort rollback."
  - "A materially improved canary is still not a pass unless the contracted verdict is pass."

requirements-completed: []

# Metrics
duration: 21min27s
completed: 2026-05-04T13:51:37Z
---

# Phase 200 Plan 14: Gap-Closure Deploy Gate Summary

**Attempt 3 deployed the R5+R3 gap-closure binary, verified the explicit-UL log surface, then failed closed on 4 saturated-upload floor hits and rolled back from the authorized snapshot.**

## Performance

- **Started:** 2026-05-04T13:30:10Z
- **Completed:** 2026-05-04T13:51:37Z
- **Duration:** 21min27s active execution including the 1022s canary window
- **Tasks:** 4/4 outcomes recorded (Task 1 pre-approved continuation gate, Task 2 deploy, Task 3 canary+rollback, Task 4 skipped by fail branch)
- **Files modified:** 11 evidence/docs files including canary artifacts

## Accomplishments

- Verified rollback snapshot `/opt/wanctl-prephase200-gap-20260504T132936Z.tar.gz` and used `UTC_TS=20260504T132936Z` throughout Attempt 3 records.
- Deployed commit `57be072` to cake-shaper and confirmed remote Python-tree fingerprint `707bdaedce6cfeb74b21fd1c869263811922a138a487e305514de8940be26d6d` matched local and differed from the v1.40 rollback fingerprint.
- Confirmed the post-restart D-06 journal surface: `phase200 explicit UL thresholds active: upload_target_bloat_ms=42 upload_warn_bloat_ms=105`.
- Re-ran the saturated UL canary at `canary/20260504T133207Z/`; verdict was `fail` with `ul_floor_hits_during_load=4`.
- Verified Plan 200-11 live baseline fix: verdict recorded `pre_baseline_rtt_ms=21.7` and `post_baseline_rtt_ms=22.23`.
- Executed D-10 rollback immediately after the fail verdict and verified `wanctl@spectrum.service` active with `/health` upload GREEN at 18 Mbps.
- Recorded Task 4 as `skipped (canary-fail-branch)`; no 24h soak was launched.

## Task Commits

1. **Task 2: Deploy gap-closure binary and verify D-06 explicit-UL log surface** — `9efa38c` (docs)
2. **Task 3: Run saturation canary with explicit pass/fail/abort branching** — `d48b95b` (docs/evidence)
3. **Task 4: Launch 24h regression soak (PASS branch only)** — `09a2cba` (docs; skipped on canary-fail branch)

**Plan metadata:** pending final metadata commit.

## Attempt 3 Canary Verdict

- **Run ID:** `20260504T133207Z`
- **Loaded window:** `2026-05-04T13:33:08Z` → `2026-05-04T13:48:09Z`
- **Verdict:** `fail`
- **Script exit code:** `1`
- **UL floor hits during load:** `4`
- **Sample distribution:** 871 ceiling / 4 floor / 10 transitional from 885 loaded-window samples
- **UL state distribution:** GREEN 227 / YELLOW 655 / RED 3
- **Baseline RTT bookends:** pre `21.7 ms`, post `22.23 ms`

## Rollback and Soak Branch

- **Rollback branch:** `fail`
- **Rollback command:** `ssh kevin@10.10.110.223 "sudo tar -xzf /opt/wanctl-prephase200-gap-20260504T132936Z.tar.gz -C / && sudo systemctl restart wanctl@spectrum.service"`
- **Rollback issued:** `2026-05-04T13:49:19Z`
- **Post-rollback service:** `active`
- **Post-rollback health:** upload `state=GREEN`, `current_rate_mbps=18.0`
- **Soak verdict:** not run; `200-SOAK-LOG.md` records `skipped (canary-fail-branch)`.

## Files Created/Modified

- `.planning/phases/200-per-direction-rtt-bloat-thresholds/200-DEPLOY-LOG.md` — Attempt 3 deploy, canary, fail branch, and rollback evidence.
- `.planning/phases/200-per-direction-rtt-bloat-thresholds/200-SOAK-LOG.md` — Explicit skipped soak record for the canary-fail branch.
- `.planning/phases/200-per-direction-rtt-bloat-thresholds/canary/20260504T133207Z/` — Raw canary evidence (`verdict.json`, pre/post baseline JSON+NDJSON, loaded health capture, iperf summary).
- `.planning/phases/200-per-direction-rtt-bloat-thresholds/200-14-SUMMARY.md` — This summary.

## Decisions Made

- Treated the canary fail verdict literally even though the result improved substantially versus Attempt 2. VALN-06 remains failed because the plan requires zero floor hits on pass.
- Executed rollback immediately on `verdict=fail` and skipped soak per the plan rather than collecting misleading 24h evidence against a rollback binary.
- Recommend Plan 200-15 close Phase 200 as `gaps_found`; a second gap-closure cycle requires an operator decision.

## Deviations from Plan

None - plan executed exactly as written from the pre-deploy checkpoint. The missing rollback snapshot blocker was resolved before continuation, and the authorized `UTC_TS=20260504T132936Z` was used for deploy and rollback evidence.

## Issues Encountered

- The pre-deploy remote `127.0.0.1:9101` curl failed, but the operator-approved health URL `http://10.10.110.223:9101/health` was reachable and was used consistently by the canary. This did not alter the plan branch.
- The deploy script reported an existing non-critical validation warning for `linux-cake-netlink`; critical validation errors were zero and the service restarted cleanly.
- The documentation hook required `SKIP_DOC_CHECK=1` for the large canary-evidence commit to avoid an interactive prompt; hooks still ran and no `--no-verify` was used.

## Verification

- `grep -q "Attempt 3" 200-DEPLOY-LOG.md` passed.
- `grep -q "phase200 explicit UL thresholds active" 200-DEPLOY-LOG.md` passed.
- `jq -e '.verdict == "pass" or .verdict == "fail" or .verdict == "abort"' canary/20260504T133207Z/verdict.json` passed.
- `grep -qE "skipped \(canary-(fail|abort)-branch\)" 200-SOAK-LOG.md` passed.
- Focused hot-path regression slice passed: `.venv/bin/pytest -o addopts='' tests/test_cake_signal.py tests/test_queue_controller.py tests/test_wan_controller.py tests/test_health_check.py -q` → `583 passed in 40.77s`.

## Known Stubs

None.

## Threat Flags

None. Production network/SSH/rollback surfaces were the planned Plan 200-14 validation surfaces, and the canary fail branch restored the pre-deploy snapshot.

## Next Plan Readiness

- Plan 200-15 can consume Attempt 3 as `gaps_found` evidence.
- Phase 200 should not be marked verified: canary pass criteria were not met and the soak was correctly skipped.

## Self-Check: PASSED

- Found `.planning/phases/200-per-direction-rtt-bloat-thresholds/200-14-SUMMARY.md`.
- Found `.planning/phases/200-per-direction-rtt-bloat-thresholds/200-DEPLOY-LOG.md`.
- Found `.planning/phases/200-per-direction-rtt-bloat-thresholds/200-SOAK-LOG.md`.
- Found `.planning/phases/200-per-direction-rtt-bloat-thresholds/canary/20260504T133207Z/verdict.json`.
- Found task commits `9efa38c`, `d48b95b`, and `09a2cba`.
- Stub scan found no plan-introduced stubs; canary env-template placeholders are pre-existing operator-template values from Plan 200-05/11 and were not modified by this plan.

---
*Phase: 200-per-direction-rtt-bloat-thresholds*
*Completed: 2026-05-04T13:51:37Z*
