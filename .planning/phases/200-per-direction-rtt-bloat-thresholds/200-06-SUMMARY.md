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
    - .planning/phases/200-per-direction-rtt-bloat-thresholds/canary/<UTC-TS>/verdict.json    # TBD
    - .planning/phases/200-per-direction-rtt-bloat-thresholds/canary/<UTC-TS>/loaded_capture.ndjson    # TBD
    - .planning/phases/200-per-direction-rtt-bloat-thresholds/canary/<UTC-TS>/loaded_iperf_summary.json    # TBD
    - .planning/phases/200-per-direction-rtt-bloat-thresholds/canary/<UTC-TS>/pre_idle_baseline.json    # TBD
    - .planning/phases/200-per-direction-rtt-bloat-thresholds/canary/<UTC-TS>/post_idle_baseline.json    # TBD
  modified:
    - src/wanctl/wan_controller.py    # D-06 fix (per-WAN logger emission)
    - tests/test_wan_controller.py    # 2 regression tests for D-06 emission
    - scripts/phase200-saturation-canary.sh    # env-driven UL floor/ceiling
    - scripts/phase200-saturation-canary.env.example    # new PHASE200_UL_FLOOR_MBPS/CEILING_MBPS vars
    - CHANGELOG.md    # two ### Fixed entries under v1.41.0

key-decisions:
  - "Path A (literal plan compliance) selected on Attempt 1 ABORT: rolled back v1.41 per D-10, fixed Plan 01 Task 2 logger emission bug, redeployed."
  - "Plan 05 canary script bug fixed mid-Plan-06: floor/ceiling sourced from operator env vars (PHASE200_UL_FLOOR_MBPS / PHASE200_UL_CEILING_MBPS) rather than nonexistent /health fields; deploy stayed live during the patch window since the script change is non-production."
  - "D-07 verdict — TBD pending canary completion: pass | fail | abort"
  - "D-10 rollback — TBD pending verdict"

patterns-established:
  - "Byte-identity sha256 of the deployed Python tree is the cross-check for rsync deploy correctness — deploy.sh::verify_deployment only confirms file presence; fingerprint confirms content."
  - "Module-scoped loggers do NOT reach the journal in this project; per-WAN named logger via self.logger is the contracted emission path for new INFO surfaces."
  - "Canary scripts must source config values that don't appear in /health from explicit env vars, kept in sync with deployed YAML; /health is runtime state only."

requirements-completed: [VALN-06]    # PASS-conditional; will revert to in-flight if verdict = fail/abort

# Metrics
duration: TBD
completed: TBD
---

# Phase 200 Plan 06: Production Deploy + Saturation Canary Gate

**v1.41 deploy to /opt/wanctl on cake-shaper with Spectrum-side D-06 verification, D-07 saturation canary gate, and D-10 rollback protocol — VALN-06.**

> Status: **TBD** — awaiting canary verdict from Attempt 2 sub-attempt 2 (kicked off `2026-05-03T22:??Z` after script fix `dd67493`).

## Performance

- **Duration:** TBD
- **Started:** 2026-05-03T~21:29Z (Task 1 pre-deploy gate)
- **Completed:** TBD
- **Tasks:** 3 (Task 1 pre-deploy gate, Task 2 deploy + restart + journal verify, Task 3 saturation canary + accept/rollback)
- **Sub-attempts:** 2 deploy attempts, 2 canary sub-attempts (1st aborted on Plan 05 script bug)
- **Mid-plan fixes shipped:** 2 (`417e2b9` D-06 logger; `dd67493` canary env-driven floor/ceiling)

## Accomplishments

TBD on verdict. Common to all branches:

- v1.41 binary deployed and verified by byte-identity fingerprint match (`c00f4227...`).
- D-06 verification surface restored: `phase200 explicit UL thresholds active: upload_target_bloat_ms=42 upload_warn_bloat_ms=105 (target_explicit=True warn_explicit=True)` confirmed in `[spectrum]` journal at restart `2026-05-03T21:48:15Z`.
- Plan 05 canary script defect surfaced and fixed before VALN-06 verdict.
- DEPLOY-LOG.md captures the full operator-keyed timeline including pre-deploy snapshot, fingerprint match, journal evidence, and canary attempts.

### On PASS (D-07 verdict = pass)

- Plan 07 (24h regression soak) explicitly unblocked.
- Pre-deploy tarball retained on cake-shaper for the 24h soak window in case Plan 07 surfaces a delayed regression.

### On FAIL (D-07 verdict = fail)

- D-10 rollback executed: pre-deploy tarball restored to /opt/wanctl, service restarted, /health back to v1.40 baseline.
- Plan 07 BLOCKED.
- Gap-closure phase planned (candidate areas: gentler factor_down, smaller step_up_mbps, higher target_bloat_ms, DOCSIS-aware UL congestion mode).

### On ABORT (canary tooling unable to run)

- Operator triage path (Step 4 of Plan 06 Task 3): retry with corrected env/tooling, or roll back as a precaution.

## Task Commits

- (Attempt 1) Pre-deploy snapshot + first deploy + first canary ABORT: no commit at this stage; rollback executed locally.
- (Plan 01 fix) D-06 logger emission via per-WAN logger: `417e2b9 fix(200-06): emit Phase 200 D-06 explicit UL log via per-WAN logger`.
- (Plan 05 fix) Canary env-driven floor/ceiling: `dd67493 fix(200-06): canary script sources UL floor/ceiling from env vars`.
- (Attempt 2 evidence commit) `evidence(200): saturation canary <UTC-TS> verdict=<VAL> (VALN-06)` — TBD on canary completion.

## Files Created/Modified

(See key-files frontmatter; final list updates after canary writes its evidence directory.)

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

TBD pending canary completion.

## Known Stubs

- This SUMMARY skeleton was pre-written while the canary was running. Sections marked TBD will be filled in once `verdict.json` lands.

## Threat Flags

None new. T-200-17 through T-200-21 (Plan 06 threat model) all addressed by:
- T-200-17: canary IS the gate; UL floor hits > 0 → immediate rollback.
- T-200-18: only wanctl@spectrum.service was restarted; ATT untouched.
- T-200-19: pre-deploy snapshot captured at Task 1 (verified path on cake-shaper).
- T-200-20: post-restart `is-active` + journal-clean checks performed.
- T-200-21: jq selector uses `(.wans[0].upload.current_rate_mbps? // null) != null` to skip malformed lines.

## Next Plan Readiness

- **On PASS:** Plan 07 (24h regression soak) ready to start immediately. Use the same deployment-token pattern as Phase 196/198 to ensure the soak runs against the same binary commit (`417e2b9`).
- **On FAIL:** Open `phases/201-...` (gap-closure) with the candidate directions listed under "On FAIL" above.
- **On persistent ABORT:** Resolve the abort cause and retry Plan 06 Task 3.

---
*Phase: 200-per-direction-rtt-bloat-thresholds*
*Skeleton drafted: 2026-05-03 (canary in flight)*
*Final completion: TBD*
