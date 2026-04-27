---
phase: 196-spectrum-a-b-soak-and-att-regression-canary
plan: 10
subsystem: production-validation
tags: [gap-closure, spectrum, throughput, documented-exceptions, validation]

requires:
  - phase: 196-09
    provides: raw-only B-leg audit with documented exceptions and human-review gate
provides:
  - Human acceptance record for the raw-only B-leg documented exceptions
  - Spectrum cake-primary tcp_12down throughput summary parsed from raw flent data
  - Honest blocked state for A/B comparison after throughput miss
  - SAFE-05 protected controller diff guard for this continuation

key-files:
  created:
    - .planning/phases/196-spectrum-a-b-soak-and-att-regression-canary/soak/cake-primary/b-leg-documented-exceptions-acceptance.json
    - .planning/phases/196-spectrum-a-b-soak-and-att-regression-canary/soak/cake-primary/throughput-summary.json
    - .planning/phases/196-spectrum-a-b-soak-and-att-regression-canary/196-10-SUMMARY.md
  modified:
    - .planning/phases/196-spectrum-a-b-soak-and-att-regression-canary/196-VERIFICATION.md
    - .planning/ROADMAP.md
    - .planning/STATE.md

requirements-completed: []
requirements-addressed: [VALN-04, VALN-05, SAFE-05]

duration: 6 min
completed: 2026-04-27
---

# Phase 196 Plan 10: Spectrum B-Leg Acceptance and Throughput Continuation Summary

Human acceptance of the six raw RTT-primary B-leg samples was recorded, then the Spectrum cake-primary throughput commands were run and parsed from raw flent JSON.

## Accomplishments

- Recorded explicit operator acceptance of `raw-only-primary-signal-audit.json` as `pass_with_documented_exceptions` for continuation.
- Preserved the original Plan 196-07 fail-closed `primary-signal-audit.json` evidence unchanged.
- Ran the required `phase196_cake_primary_tcp12` and `phase196_cake_primary_rrul_voip` flent captures.
- Parsed `results["TCP download sum"]` from the raw tcp_12down `.flent.gz` file and wrote `throughput-summary.json`.
- Recorded the throughput verdict as `fail` because the median was `73.92243773827883 Mbps`, below the `532 Mbps` acceptance threshold.
- Did not create `ab-comparison.json` because Plan 196-07 Task 3 requires a passing throughput verdict before comparison closeout can be claimed.

## Decisions Made

- The raw-only B-leg documented exceptions are accepted only as authorization to proceed with throughput/A-B validation; they do not by themselves satisfy VALN-04.
- VALN-05 Spectrum remains blocked because cake-primary tcp_12down median throughput failed the 532 Mbps acceptance threshold.
- VALN-04 Spectrum remains blocked because no A/B comparison verdict was created after throughput failed.

## Deviations from Plan

None. The continuation followed the accepted documented-exception gate and failed closed on the throughput miss.

## Known Stubs

None.

## Threat Flags

None.

## Self-Check: PASSED

- `b-leg-documented-exceptions-acceptance.json` records human acceptance and points to both raw-only and original fail-closed audits.
- `throughput-summary.json` exists with numeric `tcp_12down_median_mbps` and `verdict: fail` against `acceptance_mbps: 532`.
- `ab-comparison.json` remains absent because throughput failed.
- Protected controller files have no diff.
