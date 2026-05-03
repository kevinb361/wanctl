# Phase 200 Plan 07 Soak Log

**Status:** BLOCKED — Plan 06 canary verdict was `fail`, not `pass`.

## Gate Check

- Checked at: `2026-05-03T23:13:32Z`
- Gate source: `.planning/phases/200-per-direction-rtt-bloat-thresholds/200-DEPLOY-LOG.md`
- Plan 06 verdict: `fail`
- Canary run: `.planning/phases/200-per-direction-rtt-bloat-thresholds/canary/20260503T215734Z/verdict.json`
- Failure: 122 UL collapse-to-floor events during the 900s loaded window.
- D-10 rollback: executed at `2026-05-03T22:15:04Z`; production restored to the v1.40 baseline.

## Decision

Plan 07 is **BLOCKED** per the plan gate: the 24h regression soak only runs after Plan 06 accepts the v1.41 deploy with `verdict=pass`.

No soak capture was launched, no production traffic was generated, and no production service was touched during Plan 07.

## Next Step

Use the Plan 06 failure evidence and `200-RETRO.md` as the input to gap-closure planning (Phase 201 / DOCSIS-aware UL congestion control). Plan 08 should record VALN-06 as failed/blocked rather than satisfied by a soak.
