# Phase 200: Per-Direction RTT Bloat Thresholds — Summary

**Phase:** 200 (v1.41 single-phase milestone)  
**Started:** 2026-05-03  
**Closed:** 2026-05-03  
**Duration:** same-day implementation, deploy gate, rollback, and closeout  
**Status:** blocked  
**Deploy state:** rolled-back

## Outcome

Phase 200 successfully implemented optional per-direction UL RTT bloat thresholds, startup warnings for unknown `continuous_monitoring.*` keys, v1.41.0 release surfaces, Spectrum YAML adoption, and the saturation-canary deploy gate. Production validation then rejected the v1.41 hypothesis: the Spectrum canary recorded 122 UL collapse-to-floor events during the 900s loaded window even with 42/105 ms UL thresholds live. D-10 rollback restored the v1.40 binary at `2026-05-03T22:15:04Z`, and Plan 07 correctly blocked the 24h soak because the primary gate did not pass.

## Requirements

| ID | Status | Plan(s) | Evidence |
|---|---|---|---|
| ARB-05 | satisfied | 01, 02, 06 | Per-key presence flags; live journal D-06 threshold proof; regression tests |
| SAFE-06 | satisfied | 03, 06 | Startup WARNING path; shipped-config clean checks; clean deploy journal |
| VALN-06 | blocked | 05, 06, 07 | Canary `verdict=fail`, 122 floor hits; D-10 rollback; soak blocked |
| DOCS-03 | satisfied | 04, 06, 07 | CHANGELOG and docs/CONFIGURATION migration note plus failure/rollback known-gap docs |

## Key Files Shipped

See `200-VERIFICATION.md` `files_touched` block for the full code/test/script/config/docs/build surface.

## Operator Decisions Worth Carrying Forward

- D-07 was the correct deploy contract: the saturated UL canary reproduced the failure mode quickly and prevented a misleading 24h soak from becoming milestone acceptance evidence.
- D-10 rollback was executed and verified; production is restored to the v1.40 binary while `configs/spectrum.yaml` retains the v1.41 YAML keys as harmless no-ops under the older binary.
- The 122 floor-hit canary evidence points away from merely wider UL bloat thresholds and toward a gap-closure design such as DOCSIS-aware UL congestion control or a substantially lower Spectrum upload ceiling.

## Followups

- Continue with `.planning/phases/201-docsis-aware-ul-congestion-control/201-CONTEXT.md` as the gap-closure seed.
- Preserve `.planning/phases/200-per-direction-rtt-bloat-thresholds/canary/20260503T215734Z/verdict.json` as the canonical failed deploy-gate evidence for VALN-06.
- Do not mark v1.41 as production-accepted; archive only as a blocked/rolled-back milestone if archiving is needed for bookkeeping.
