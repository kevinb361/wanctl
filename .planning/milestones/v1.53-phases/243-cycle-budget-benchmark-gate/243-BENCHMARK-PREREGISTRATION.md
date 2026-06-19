# Phase 243 Benchmark Pre-registration

This document freezes the Phase 243 BENCH-02 gate before any cycle-budget
benchmark data is collected. The machine-readable source of truth is
`scripts/phase243-thresholds.json`; this narrative explains the gate without
copying its threshold literals.

## Scope

Phase 243 is a measurement and gate phase. It does not change controller
thresholds, state machines, timing, RouterOS behavior, or live production
services. The benchmark is throwaway scaffolding that must preserve SAFE-17 by
leaving `src/wanctl/` unchanged.

## Arms

The benchmark design has eight arms: backend (`icmplib` or `fping`) crossed with
condition (`idle` or `under-load`) crossed with the two dev WAN paths. The
under-load condition reuses each WAN's established flent/netperf path rather
than synthetic CPU load or a different traffic generator.

## Primary and Secondary Basis

The primary comparison is same-run `fping` minus same-run `icmplib` on the same
host, WAN path, and load condition. This controls for dev-host drift and keeps
the verdict focused on whether `fping` regresses the controller cycle budget or
CPU use relative to the control arm.

The historical `icmplib` performance anchor is secondary. It is a
representativeness check on the dev host, not the primary accept/reject basis.
If the dev `icmplib` arm is outside the frozen representativeness tolerance band
in `scripts/phase243-thresholds.json`, representativeness is a HARD validity
gate: the verdict is `input_error` / abort, not a warning and not a passing
close.

## Gate Narrative

The cycle-budget gate requires the `fping` arm to remain within the frozen
relative average and tail-regression limits against the same-run `icmplib` arm,
and also under the frozen absolute tail ceiling. Both layers are required:
relative deltas catch regressions against the control, while the absolute tail
ceiling catches any budget blow-up even if the control arm is also slow.

The subprocess-hygiene gate is hard: zombie children must remain within the
frozen zero-tolerance rule, file descriptors must not show an upward leak trend,
and systemd Tasks/threads must remain within the frozen bound. `TASKS_BOUND` is
intentionally a small concrete slack value in the JSON to tolerate normal thread
jitter while still failing closed on unbounded subprocess/thread growth.

The STALL gate targets the journal-pipe fingerprint. The benchmark must run
under a real systemd unit with stdout on the journal pipe, not a TTY, and any
cycle gap beyond the frozen stall threshold fails the run.

The validity floor requires each arm to meet the frozen cycle-count and elapsed
time floor. The cadence constant lives in `scripts/phase243-thresholds.json` as
`CYCLE_HZ`, so the n-floor math is explicit rather than an implicit control-loop
literal.

CPU normalization is pre-registered as `CPU_NORMALIZATION=per_core`, meaning the
verdict computes unit CPU as percent-of-whole-machine using cgroup CPU time over
wall time divided by the machine core count. This makes the CPU delta comparison
unambiguous across hosts.

## Passing Close Semantics

"Keep icmplib" is a valid passing close. This gate blocks only on regression or
invalid representativeness; it does not require `fping` to win and does not force
the later Phase 245 A/B or Phase 246 default flip.

## Ordering and Provenance

BENCH-02 requires this pre-registration and `scripts/phase243-thresholds.json` to
be committed before evidence collection. The ordering proof is git-mechanical,
not just file presence: `scripts/phase243-prereg-provenance.sh` records the
thresholds blob SHA and prereg commit SHA, and the later verdict must assert that
benchmark evidence commits descend from the prereg commit while the thresholds
blob stayed unchanged.

## Single-source Rule

Do not copy threshold numbers from `scripts/phase243-thresholds.json` into
benchmark reports or prose. Future evidence and verdict artifacts should cite
the JSON keys and record the frozen blob SHA so reviewers can verify exactly
which thresholds governed the run.
