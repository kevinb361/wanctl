# DRIFT-03 Per-Milestone Steering Change Classification

## Methodology

Classification follows `222-RESEARCH.md` Section 6 and is derived from reading the steering-surface diff, not from commit subjects alone.

- **behavior-changing** — alters a decision threshold, branch, rerouting trigger, restart/state recovery path, autorate coupling, or any observable steering decision under any input.
- **behavior-preserving** — refactor, rename, type annotation, cleanup, dead-code removal, log-text rephrase, or comment-only change with no decision-affecting branch change.
- **observability-only** — log, metric, `/health`, or dashboard-only surface that cannot alter decisions.

The steering spine contract is the categorization lens: binary on/off steering, only new latency-sensitive connections rerouted, and autorate baseline RTT remains authoritative.

## Per-Milestone Tally

| Milestone | Behavior-Changing | Behavior-Preserving | Observability-Only | Total |
|---|---:|---:|---:|---:|
| v1.39..v1.40 | 1 | 0 | 0 | 1 |

## Per-Commit Classification

| Milestone | SHA | Subject | Category | Rationale |
|---|---|---|---|---|
| v1.39..v1.40 | `84ad6aa2d5bc7d03ef5069c0b65e7b1cdf930538` | fix: harden steering and storage utility contracts | behavior-changing | Tightens the steering contract guard in `RouterOSController.is_steering_active` to ignore non-dict parsed records and narrows `measure_current_rtt` to numeric autorate/IRTT values, changing which malformed inputs can drive the steering decision path. |

## Findings

- `84ad6aa` is behavior-changing: it hardens `RouterOSController.is_steering_active` against malformed parsed RouterOS records and changes `SteeringDaemon.measure_current_rtt` so only numeric autorate health / IRTT values can feed the steering RTT path, affecting the autorate-coupling decision branch under malformed or non-numeric input.

## Default Dispositions

Behavior-preserving and observability-only changes default to `go`. Behavior-changing changes require a per-finding disposition in Plan 02 (DRIFT-04), with rationale tied to the contract diff and any needed mitigation.
