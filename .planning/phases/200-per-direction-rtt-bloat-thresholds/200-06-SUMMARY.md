---
phase: 200-per-direction-rtt-bloat-thresholds
plan: 06
subsystem: deploy
tags: [valn-06, deploy-gate, saturation-canary, rollback, d-07, d-10, spectrum]

# Dependency graph
requires:
  - phase: 200-per-direction-rtt-bloat-thresholds
    provides: Plans 01-05 — D-03 fix, SAFE-05/06 wiring, v1.41.0 version coherence, Spectrum D-05 YAML, saturation canary tooling
provides:
  - Phase 200 production deploy outcome (accept-or-rollback) for the v1.41 binary
  - Operator-keyed deploy timeline with byte-identity fingerprint, journal D-06 evidence, canary verdict
  - Either Plan 07 unblock (on PASS) or gap-closure phase planning (on FAIL/persistent ABORT)
affects: [phase-200-spectrum-deploy, valn-06, plan-07-soak, d-10-rollback-protocol]

# Tech tracking
tech-stack:
  added: []
  patterns: [byte-identity sha256 fingerprint deploy verification, per-WAN logger D-06 verification surface, env-driven canary floor source]

key-files:
  created:
    - .planning/phases/200-per-direction-rtt-bloat-thresholds/200-DEPLOY-LOG.md
    - .planning/phases/200-per-direction-rtt-bloat-thresholds/canary/pre-deploy-health.json
    - .planning/phases/200-per-direction-rtt-bloat-thresholds/canary/20260503T215734Z/verdict.json
    - .planning/phases/200-per-direction-rtt-bloat-thresholds/canary/20260503T215734Z/loaded_capture.ndjson
    - .planning/phases/200-per-direction-rtt-bloat-thresholds/canary/20260503T215734Z/loaded_iperf_summary.json
    - .planning/phases/200-per-direction-rtt-bloat-thresholds/canary/20260503T215734Z/pre_idle_baseline.json
    - .planning/phases/200-per-direction-rtt-bloat-thresholds/canary/20260503T215734Z/post_idle_baseline.json
    - .planning/phases/200-per-direction-rtt-bloat-thresholds/200-RETRO.md
    - .planning/phases/201-docsis-aware-ul-congestion-control/201-CONTEXT.md
  modified:
    - src/wanctl/wan_controller.py    # D-06 fix (per-WAN logger emission)
    - tests/test_wan_controller.py    # 2 regression tests for D-06 emission
    - scripts/phase200-saturation-canary.sh    # env-driven UL floor/ceiling
    - scripts/phase200-saturation-canary.env.example    # new PHASE200_UL_FLOOR_MBPS/CEILING_MBPS vars
    - CHANGELOG.md    # two ### Fixed entries under v1.41.0

key-decisions:
  - "Path A (literal plan compliance) selected on Attempt 1 ABORT: rolled back v1.41 per D-10, fixed Plan 01 Task 2 logger emission bug, redeployed."
  - "Plan 05 canary script bug fixed mid-Plan-06: floor/ceiling sourced from operator env vars (PHASE200_UL_FLOOR_MBPS / PHASE200_UL_CEILING_MBPS) rather than nonexistent /health fields; deploy stayed live during the patch window since the script change is non-production."
  - "D-07 verdict: FAIL — saturation canary recorded 122 UL collapse-to-floor events in 900s loaded window (run_id 20260503T215734Z, ul_floor_hits_during_load=122)."
  - "D-10 rollback executed at 2026-05-03T22:15:04Z — production restored to v1.40 baseline; service active, /health upload state=GREEN at 18 Mbps."

patterns-established:
  - "Byte-identity sha256 of the deployed Python tree is the cross-check for rsync deploy correctness — deploy.sh::verify_deployment only confirms file presence; fingerprint confirms content."
  - "Module-scoped loggers do NOT reach the journal in this project; per-WAN named logger via self.logger is the contracted emission path for new INFO surfaces."
  - "Canary scripts must source config values that don't appear in /health from explicit env vars, kept in sync with deployed YAML; /health is runtime state only."

requirements-completed: []    # VALN-06 NOT satisfied — saturation canary FAILED; gap-closure phase required

# Metrics
duration: 2h46m (pre-deploy gate at 21:29Z to rollback complete at 22:15:04Z, plus post-FAIL closeout artifacts to ~22:25Z)
completed: 2026-05-03
---

# Phase 200 Plan 06: Production Deploy + Saturation Canary Gate

**v1.41 deploy to /opt/wanctl on cake-shaper with Spectrum-side D-06 verification, D-07 saturation canary gate, and D-10 rollback protocol — VALN-06.**

> Status: **D-07 FAIL → D-10 rollback executed.** v1.41 hypothesis (per-direction UL thresholds 42/105 ms) tested in production and rejected with 122 UL collapse-to-floor events in the 900s loaded window. Production restored to v1.40 baseline. Plan 07 BLOCKED. Gap-closure phase Phase 201 (DOCSIS-aware UL congestion control) seeded.

## Performance

- **Duration:** 2h46m (pre-deploy gate Task 1 at `2026-05-03T21:29:42Z` → rollback complete at `2026-05-03T22:15:04Z`; post-FAIL closeout artifacts and commits through `~22:25Z`)
- **Started:** 2026-05-03T21:29:42Z (pre-deploy snapshot UTC_TS pin)
- **Completed:** 2026-05-03T22:15:04Z (D-10 rollback verified)
- **Tasks:** 3 (Task 1 pre-deploy gate, Task 2 deploy + restart + journal verify, Task 3 saturation canary + accept/rollback)
- **Sub-attempts:** 2 deploy attempts, 2 canary sub-attempts (1st aborted on Plan 05 script bug; 2nd ran to completion and FAILed on hypothesis)
- **Mid-plan fixes shipped:** 2 (`417e2b9` D-06 logger; `dd67493` canary env-driven floor/ceiling)

## Accomplishments

- v1.41 binary deployed and verified by byte-identity fingerprint match (`c00f42274ad48c8c61accd326c8bce32eb295b2b1f80a93c09aab4bc06d1f870`); confirms deploy.sh's rsync produced a content-identical tree to local commit `417e2b9`.
- D-06 verification surface confirmed: `[spectrum] [INFO] phase200 explicit UL thresholds active: upload_target_bloat_ms=42 upload_warn_bloat_ms=105 (target_explicit=True warn_explicit=True)` emitted in journal at `2026-05-03 16:48:17,412` (post-restart). Per-direction UL thresholds confirmed live on the deployed binary.
- D-07 saturation canary executed against production (`run_id 20260503T215734Z`, 1023s duration including 60s pre-baseline + 900s loaded + 60s post-baseline + tooling overhead).
- D-07 verdict: **FAIL** — `ul_floor_hits_during_load=122`. Hypothesis "per-direction UL thresholds 42/105 ms prevent UL collapse-to-floor on Spectrum DOCSIS upload" REJECTED.
- D-10 rollback executed at `2026-05-03T22:15:04Z`: pre-deploy tarball `/opt/wanctl-prephase200-20260503T212942Z.tar.gz` restored, service restarted, post-rollback `is-active=active`, `/health.wans[0].upload.state=GREEN at 18 Mbps`, `phase200 explicit UL thresholds active` count=0 in journal (sanity — v1.40 binary running).
- Two upstream Plan 0X verification-surface bugs surfaced and fixed mid-plan:
  - `417e2b9`: Plan 01 Task 2 logger emission (module-scope `getLogger(__name__)` had no handlers → INFO line dropped).
  - `dd67493`: Plan 05 canary script preflight asserted `/health.wans[].upload.{floor_mbps, ceiling_mbps}` shape fields that don't exist (`/health` carries runtime state only).
- DEPLOY-LOG.md captures the full operator-keyed timeline across both deploy attempts and both canary sub-attempts.
- Plan 06 retrospective lessons captured in `200-RETRO.md`; gap-closure direction seeded in `.planning/phases/201-docsis-aware-ul-congestion-control/201-CONTEXT.md`.

### On FAIL outcome (this is what happened)

- ✓ D-10 rollback executed: production restored to v1.40 baseline.
- ✓ Plan 07 (24h regression soak) BLOCKED — running a 24h soak against the v1.40 binary is meaningless for VALN-06.
- ✓ Gap-closure phase Phase 201 seeded — DOCSIS-aware UL congestion control with low setpoint as the most likely correct direction. Sample distribution evidence (53% ceiling, 14% floor, 33% transitional; 59% YELLOW state) ruled out gentler decay or wider thresholds as adequate fixes.

## Task Commits

- (Attempt 1 — D-06 verification ABORT) Pre-deploy snapshot + first deploy + missing INFO line: rolled back without an evidence commit (Task 2 verification gate failed before any commit-worthy artifact was produced).
- (Plan 01 fix) D-06 logger emission via per-WAN logger: `417e2b9 fix(200-06): emit Phase 200 D-06 explicit UL log via per-WAN logger` (3 files: src/wanctl/wan_controller.py, tests/test_wan_controller.py, CHANGELOG.md).
- (Plan 05 fix) Canary env-driven floor/ceiling: `dd67493 fix(200-06): canary script sources UL floor/ceiling from env vars` (3 files: scripts/phase200-saturation-canary.sh, scripts/phase200-saturation-canary.env.example, CHANGELOG.md).
- (Attempt 2 — D-07 FAIL evidence) Canary outcome + DEPLOY-LOG.md + SUMMARY skeleton + STATE.md + alerting-severity quick task: `5cbe398 evidence(200): saturation canary 20260503T215734Z verdict=fail (VALN-06)` (11 files, ~11M evidence including 886-sample loaded_capture.ndjson).
- (Post-FAIL closeout) Repo-side alerting fix + Phase 200 RETRO + Phase 201 CONTEXT seed + CHANGELOG entry: `41d4a1f fix(config): restore Spectrum alerting and close Phase 200 FAIL` (4 files).

## Files Created/Modified

Created:
- `.planning/phases/200-per-direction-rtt-bloat-thresholds/200-DEPLOY-LOG.md` (operator-keyed Plan 06 timeline)
- `.planning/phases/200-per-direction-rtt-bloat-thresholds/200-RETRO.md` (Phase 200 retrospective)
- `.planning/phases/200-per-direction-rtt-bloat-thresholds/canary/pre-deploy-health.json` (Attempt 1 baseline)
- `.planning/phases/200-per-direction-rtt-bloat-thresholds/canary/20260503T215734Z/{verdict,pre_idle_baseline,post_idle_baseline,loaded_iperf_summary}.json` (Attempt 2 evidence)
- `.planning/phases/200-per-direction-rtt-bloat-thresholds/canary/20260503T215734Z/{loaded_capture,pre_idle_baseline,post_idle_baseline}.ndjson` (raw 1Hz captures)
- `.planning/phases/201-docsis-aware-ul-congestion-control/201-CONTEXT.md` (gap-closure seed)
- `.planning/quick/260503-cfs-fix-spectrum-alerting-severity/260503-cfs-PLAN.md` (side-discovery quick task)

Modified:
- `src/wanctl/wan_controller.py` (D-06 logger fix; incidental ruff-format collapses)
- `tests/test_wan_controller.py` (2 regression tests for D-06 emission)
- `scripts/phase200-saturation-canary.sh` (env-var-driven floor/ceiling; preflight shape relaxed)
- `scripts/phase200-saturation-canary.env.example` (new PHASE200_UL_FLOOR_MBPS / PHASE200_UL_CEILING_MBPS)
- `configs/spectrum.yaml` (alerting.rules.congestion_flapping.severity restored)
- `CHANGELOG.md` (3 ### Fixed entries under v1.41.0)
- `.planning/STATE.md` (stopped_at + last_updated reflect FAIL closeout)

## Decisions Made

- **Path A on Attempt 1 ABORT (operator-driven)**: rolled back per D-10 literal plan compliance rather than substituting alternate evidence; this kept plan integrity intact and revealed a second Plan 0X bug (Plan 05) that would have blocked Plan 07 anyway. Validated as the correct call.
- **Stay-deployed during Plan 05 script fix window**: v1.41 binary remained active on Spectrum during the ~5-minute canary script patch (script-only change, no production touch); accepted because GREEN baseline at idle + D-06 evidence confirmed runtime correctness.
- D-07: `verdict.json.verdict == "pass"` is the deploy gate; canary is the primary VALN-06 verifier.
- D-10: rollback protocol embedded in every verdict variant (pass, fail, abort) and pre-deploy snapshot tarball captured before any binary swap.
- (PASS only) Plan 07 24h soak runs as a regression watchdog, not as the primary gate.

## Deviations from Plan

- **Two implementation bugs surfaced in upstream Plan 0X work, fixed mid-Plan-06**:
  1. Plan 01 Task 2 used module-scope logger that has no handlers in production. Fixed at `417e2b9`.
  2. Plan 05 canary script asserted /health shape fields (floor_mbps, ceiling_mbps) that don't exist in /health. Fixed at `dd67493`.
- Both were verification-surface bugs, not control-path bugs; in-process Python proof during Attempt 1 confirmed v1.41's runtime control behavior was correct (target_explicit=True, warn_explicit=True, 42/105 ms thresholds resolved). Worth flagging in retrospective: smoke checks across upstream plans must include at least one real-/health curl + journal grep against a running daemon, not just JSON/YAML fixtures.

## Issues Encountered

- Attempt 1 D-06 verification grep returned zero matches despite correct binary deployment (root cause: wrong logger).
- Attempt 2 canary preflight ABORTed on missing /health shape fields (root cause: Plan 05 design assumption).
- Both bugs were caught **in production by Plan 06's literal verification protocol**, not by upstream smoke checks — exactly the design intent of D-06 and D-07.
- Unrelated: every restart still emits `alerting.rules.congestion_flapping missing required 'severity'; disabling alerting` on Spectrum (silently disables ALL alerting). Tracked as quick-task `260503-cfs-fix-spectrum-alerting-severity`.

## Verification

- DEPLOY-LOG.md exists with pre-deploy snapshot path, deploy commit SHA (`417e2b9`), deploy/restart/rollback timestamps, post-restart /health excerpt, canary run-id (`20260503T215734Z`), verdict (`fail`), and rollback decision recorded.
- `canary/20260503T215734Z/verdict.json` exists with `verdict: "fail"`, `ul_floor_hits_during_load: 122`, `rollback_protocol_recorded: true`.
- One git commit `5cbe398 evidence(200): saturation canary 20260503T215734Z verdict=fail (VALN-06)` contains the canary evidence files plus DEPLOY-LOG.md, SUMMARY skeleton, and STATE.md update.
- Post-rollback verification: `wanctl@spectrum.service is-active=active`, `/health.wans[0].upload.state=GREEN at 18 Mbps`, `phase200 explicit UL thresholds active` count=0 in journal.
- Plan 07 (24h regression soak) status: BLOCKED — phase moves to gap-closure rather than soak.
- Phase 201 seeded with 122-collapse evidence as input to `/gsd-discuss-phase`.

**Rollback semantics:** D-10 was triggered because the canary failed; pre-deploy tarball was applied successfully and immediately verified.

## Known Stubs

- None remaining at SUMMARY close. Task 1 of quick-task `260503-cfs` (production-side YAML severity edit on cake-shaper) is operator-driven and tracked separately.

## Threat Flags

None new. T-200-17 through T-200-21 (Plan 06 threat model) all addressed by:
- T-200-17: canary IS the gate; UL floor hits > 0 → immediate rollback.
- T-200-18: only wanctl@spectrum.service was restarted; ATT untouched.
- T-200-19: pre-deploy snapshot captured at Task 1 (verified path on cake-shaper).
- T-200-20: post-restart `is-active` + journal-clean checks performed.
- T-200-21: jq selector uses `(.wans[0].upload.current_rate_mbps? // null) != null` to skip malformed lines.

## Next Plan Readiness

- Plan 07 (24h regression soak) is BLOCKED — running a 24h soak against the v1.40 binary is meaningless for VALN-06.
- Phase 201 (DOCSIS-aware UL congestion control) seeded at `.planning/phases/201-docsis-aware-ul-congestion-control/201-CONTEXT.md`. Next operator action: `/gsd-discuss-phase 201` to refine root cause and design direction. The 122-collapse evidence file from this canary run is the seed.
- Quick-task `260503-cfs-fix-spectrum-alerting-severity`: Task 2 (repo-side YAML at `configs/spectrum.yaml`) shipped at `41d4a1f`; Task 1 (production YAML edit on cake-shaper) operator-driven and pending.

---
*Phase: 200-per-direction-rtt-bloat-thresholds*
*Drafted as skeleton: 2026-05-03 (during canary execution)*
*Closed with FAIL verdict: 2026-05-03T22:15:04Z (D-10 rollback complete)*
