# Phase 201 Plan 16 — 24h Soak Verdict (VALN-06 Closeout)

**Soak timestamp:** `20260505T132736Z`  
**Status:** FAIL — primary D-19 gate passed, secondary D-14 watchdog failed  
**Canonical summary:** `.planning/phases/201-docsis-aware-ul-congestion-control/soak/20260505T132736Z/soak-summary.json`  
**Supersedes:** Plan 201-12 failed-canary path

## Soak Run Metadata

| Field | Value |
|---|---|
| Binary | `1.42.1` |
| Capture host | `cake-shaper` on-host tmux |
| Capture method | uploaded script + positional `SOAK_TS` arg + verbatim tmux (codex NEW-HIGH-2) |
| Remote capture | `cake-shaper:/var/tmp/wanctl-soak-20260505T132736Z/soak-capture.ndjson` |
| Local capture | `soak/20260505T132736Z/soak-capture.ndjson` |
| Samples | `84117` |
| Expected 1Hz samples by monotonic span | `86398` |
| Sample coverage ratio | `0.9735842767244641` |

The local capture script is preserved at `soak/20260505T132736Z/soak-capture.sh`. It uses `SOAK_TS="${1:?SOAK_TS positional arg required}"`; no heredoc interpolation was used for the remote launch.

## Primary Gate — D-19 Floor-Hit Counter

**Approval source:** `.planning/phases/201-docsis-aware-ul-congestion-control/201-16-OPERATOR-APPROVAL-D19.md`

| Metric | Required | Actual | Result |
|---|---:|---:|---|
| `floor_hit_cycles_total_delta_soak_window` | `0` | `0` | PASS |

Bookends:

- T+0: `0` from `t0-baseline.json`
- T+24: `0` from `t24-baseline.json`
- Delta: `0`

No daemon restart evidence file was present in the soak directory, and the counter did not go negative. The stricter D-19 primary gate passed.

## Secondary Gate — D-14 Suppression Watchdog

The secondary gate used the timestamp-windowed 60s mean with `$rows` bound outside the reduction body and `$rows[]` used for each window selection (codex NEW-HIGH-3 closure). The accumulator was not iterated.

| Metric | Required | Actual | Result |
|---|---:|---:|---|
| `ul_hysteresis_suppression_rate_per_60s_mean` | `< 5.0` | `6.466842364880155` | FAIL |
| p95 | informational | `21.10169491525424` | — |
| max | informational | `69.91379310344827` | — |

## Diagnostic Distribution

| Metric | Mean | Max / Count |
|---|---:|---:|
| `rtt_integral_ms_s` | `5.144822223807321` | max `270.569` |
| `max_delay_delta_us` | `810.3376368629409` | max `161281` |
| `red_streak` | `0.005872772447899949` | max `101` |
| `headroom_state == EXHAUSTED` | — | `469 / 84117` samples |

## Anti-Windup Triggers

| Metric | Value |
|---|---:|
| Counter delta | `0` |
| Journal log count (`ANTI-WINDUP`, last 24h) | `0` |

## Decision

- [ ] PASS — both D-19 primary and D-14 secondary gates passed.
- [x] FAIL — gates disagreed: primary passed, secondary failed.
- [ ] ABORT — soak evidence unavailable or invalid.

Canonical verdict:

```json
{
  "verdict": "fail",
  "reason": "soak_gates_disagreement_primary_pass_secondary_fail",
  "primary_gate": "pass",
  "secondary_gate": "fail"
}
```

## Closure Action

Phase 201 cannot close VALN-06 as satisfied because the original D-14 watchdog remains part of the plan-defined success criteria and failed at `6.466842364880155` suppressions/minute mean. The D-19 primary tightening was valid and passed, but it does not override the preserved D-14 secondary gate.

Record Phase 201 as a soak FAIL/gap-closure continuation point. The safe operator choices are:

1. **A5-style reattempt:** authorize another controlled canary/soak cycle with revised operational parameters only if the operator accepts the production-risk tradeoff.
2. **v1.43+ control-model follow-up:** leave Phase 201 at gaps_found and plan a follow-up control-model or suppression-watchdog investigation before any new 24h soak.

No production controller behavior or production YAML was changed by this closeout task.
