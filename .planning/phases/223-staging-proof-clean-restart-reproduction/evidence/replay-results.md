# Phase 223 Replay Results

| fixture | harness_mode | cycles_run | pre_rule_state | final_state | verdict | verdict_rationale |
|---|---|---:|---|---|---|---|
| cake-read-failure | hysteresis-only | 8 | False | SPECTRUM_GOOD | matches | All expected decisions matched and no live I/O escaped the harness. |
| onset-degraded-confidence | confidence | 700 | False | SPECTRUM_GOOD | matches | All expected decisions matched and no live I/O escaped the harness. |
| onset-degraded-from-phase212 | hysteresis-only | 15 | False | SPECTRUM_DEGRADED | matches | All expected decisions matched and no live I/O escaped the harness. |
| onset-degraded | hysteresis-only | 15 | False | SPECTRUM_DEGRADED | matches | All expected decisions matched and no live I/O escaped the harness. |
| recovery | hysteresis-only | 20 | True | SPECTRUM_GOOD | matches | All expected decisions matched and no live I/O escaped the harness. |
| steady-good | hysteresis-only | 10 | False | SPECTRUM_GOOD | matches | All expected decisions matched and no live I/O escaped the harness. |

## I/O Seal Audit

- **cake-read-failure**: baseline_rtt, cake_stats, live_rtt, state_save
- **onset-degraded-confidence**: baseline_rtt, cake_stats, live_rtt, state_save
- **onset-degraded-from-phase212**: baseline_rtt, cake_stats, live_rtt, state_save
- **onset-degraded**: baseline_rtt, cake_stats, live_rtt, state_save
- **recovery**: baseline_rtt, cake_stats, live_rtt, state_save
- **steady-good**: baseline_rtt, cake_stats, live_rtt, state_save
