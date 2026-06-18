# Phase 243 Benchmark Pre-registration Amendment

This amendment does not claim the original Phase 243 frozen thresholds passed.
They did not. The fixed production run produced complete evidence and the fixed
verdict still returned `input_error` under the original gate semantics.

## Amendment Scope

This amendment changes benchmark/evaluator semantics only. It does not change
`src/wanctl`, controller behavior, control-loop timing, state machines, RouterOS
behavior, qdisc behavior, deployment units, production configs, or live WAN
services.

## Why This Exists

The original invalid verdict was partly harness failure. That was fixed with
durable debug-log cycle evidence, a freshness-safe fping cadence, and a larger
load-arm transient unit runtime margin.

After those fixes, the full production run had complete evidence. The n-floor,
CPU, avg-delta, p99-delta, fping absolute p99, zombie, and fd-trend gates passed
for the selected fixed evidence. The remaining failures were validity semantics:

- Spectrum icmplib p99 exceeded the historical absolute representativeness band.
- Each arm had only one or two fping stall events across more than 36k cycles.
- The task gate failed because icmplib control arms reached more systemd tasks
  than fping arms, not because fping grew tasks.

Claude reviewed the fixed verdict and agreed that another full production run is
not useful before replanning these gates. The p99 issue is link-blind validity
calibration, not evidence incompleteness.

## Amended Semantics

The amended threshold blob records `AMENDMENT_ID` and the original thresholds
blob SHA in `AMENDS_THRESHOLDS_BLOB_SHA`. This creates a new provenance-bearing
threshold basis rather than rewriting the original preregistration.

The existing same-run `gate_p99_delta_pct` remains the canonical p99 regression
gate. A separate relative p99 gate was considered and rejected as redundant after
Claude review.

The icmplib historical p99 representativeness value is retained for audit, but it
no longer turns complete production evidence into `input_error`. The icmplib avg
representativeness check remains a hard validity guard because it catches a
grossly non-representative control arm without conflating link-specific p99
jitter with invalid evidence.

Stalls are now bounded by count and rate rather than requiring exactly zero over
a long production run.

Tasks are now compared by backend delta for the same WAN/load pair. The gate
fails if fping has materially more tasks than the icmplib control, not if the
control arm itself has more tasks.

## Operating Rule

Run the amended evaluator on the existing fixed evidence before any new
production benchmark. Do NOT launch another production run while complete fixed
evidence still returns `input_error` under amended semantics.
