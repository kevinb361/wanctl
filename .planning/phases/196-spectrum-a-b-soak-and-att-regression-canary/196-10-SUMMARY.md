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

# Phase 196 Plan 10: B-Leg Acceptance and Initial Throughput Continuation Summary

Human acceptance of the six raw RTT-primary B-leg samples was recorded, then the initially labeled Spectrum cake-primary throughput commands were run and parsed from raw flent JSON. A later source-bind proof in `196-11-SUMMARY.md` showed these throughput captures used `10.10.110.233`, which exits AT&T, so they are preserved for auditability but are invalid for Spectrum VALN-05 acceptance.

## Accomplishments

- Recorded explicit operator acceptance of `raw-only-primary-signal-audit.json` as `pass_with_documented_exceptions` for continuation.
- Preserved the original Plan 196-07 fail-closed `primary-signal-audit.json` evidence unchanged.
- Ran the initially labeled `phase196_cake_primary_tcp12` and `phase196_cake_primary_rrul_voip` flent captures.
- Parsed `results["TCP download sum"]` from the raw tcp_12down `.flent.gz` file and wrote `throughput-summary.json`.
- Recorded the initial throughput verdict as `fail` because the median was `73.92243773827883 Mbps`, below the `532 Mbps` acceptance threshold.
- Superseded the Spectrum-attribution claim after `196-11-SUMMARY.md` proved the capture's `local_bind=10.10.110.233` exits AT&T.
- Did not create `ab-comparison.json`; corrected Spectrum validation is recorded in Plan 196-11.

## Decisions Made

- The raw-only B-leg documented exceptions are accepted only as authorization to proceed with throughput/A-B validation; they do not by themselves satisfy VALN-04.
- VALN-05 Spectrum remained blocked here pending corrected source-bind validation.
- VALN-04 Spectrum remained blocked because no A/B comparison verdict was created.

## Deviations from Plan

Source-bind verification was added after the operator questioned whether the test actually used Spectrum. That verification superseded this initial throughput attribution.

## Known Stubs

None.

## Threat Flags

None.

## Self-Check: PASSED

- `b-leg-documented-exceptions-acceptance.json` records human acceptance and points to both raw-only and original fail-closed audits.
- `throughput-summary.json` exists with numeric `tcp_12down_median_mbps` and `verdict: fail` against `acceptance_mbps: 532`, but Plan 196-11 marks it invalid for Spectrum acceptance due to AT&T egress.
- `ab-comparison.json` remains absent because throughput failed.
- Protected controller files have no diff.
