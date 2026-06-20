---
phase: "250"
plan: "250-01"
status: complete
completed_at: "2026-06-19T16:39:50-05:00"
requirements:
  - TIN-01
  - TIN-02
  - TIN-03
verdict: consumer_audit_blocks_skip_on_unchanged_defer_to_v1_55
key_files:
  created:
    - .planning/phases/250-cake-tin-consumer-audit-conditional-implementation/250-01-PLAN.md
    - .planning/phases/250-cake-tin-consumer-audit-conditional-implementation/250-01-SUMMARY.md
    - .planning/phases/250-cake-tin-consumer-audit-conditional-implementation/evidence/consumer-audit-20260619T213950Z.md
verification:
  - repo/docs/planning consumer audit for wanctl_cake_tin_* metrics
  - live steering health tin-shape read-only check
  - live wanctl-history --tins read-only check
  - .venv/bin/pytest -o addopts='' tests/test_history_cli.py::TestPerTinHistory tests/steering/test_steering_metrics_recording.py -q
  - git diff --check
---

# Plan 250-01 Summary — CAKE Tin Consumer Audit + Conditional Implementation

## Outcome

Phase 250 closes on the audit finding. No skip-on-unchanged implementation shipped.

The audit found that the stored CAKE tin metric family is not an all-last-value consumer set:

- `wanctl-history --tins` is a raw historical row consumer, not last-value-before-T.
- `wanctl_cake_tin_dropped` and `wanctl_cake_tin_ecn_marked` are cumulative counter-shaped values where continuous samples preserve arbitrary-window delta/rate analysis.
- current live external cake-autorate mode has no stored per-tin rows in the recent window, so there is no current write-rate reduction to measure.

Per the Phase 250 gate, TIN-02/TIN-03 defer to v1.55 or a future consumer-redesign phase.

## Consumer classification

| Surface | Path | Classification | Disposition |
|---|---|---|---|
| SQLite producer | `src/wanctl/steering/daemon.py:2340-2388` | producer | writes 4 metrics per tin when Linux CAKE stats exist |
| Health endpoint | `src/wanctl/steering/health.py:230-255` | last-value current telemetry | unaffected by SQLite sparsity; reads in-memory `last_tin_stats` |
| History CLI | `src/wanctl/history.py:39-45`, `355-436`, `940-958` | raw-history / continuous-series | blocker for sparse semantics |
| History tests | `tests/test_history_cli.py::TestPerTinHistory` | test-only | encodes raw `--tins` query/format contract |
| Steering metrics tests | `tests/steering/test_steering_metrics_recording.py` | test-only | encodes current per-tin write contract |
| README/docs | `README.md:419-420`, `docs/SUBSYSTEMS.md:116`, `docs/archive/BRIDGE_QOS.md:43` | doc/operator UX | documents raw history query |
| Seed/todo | `.planning/seeds/SEED-007-v145-storage-hygiene-fire-on-change.md:65-71`, `.planning/todos/completed/2026-04-17-cake-tin-skip-on-unchanged-consumer-audit.md:21-24` | planning gate | says defer if consumer is not last-value-style |

## Metric-specific finding

- `wanctl_cake_tin_dropped`: counter-shaped / delta-sensitive.
- `wanctl_cake_tin_ecn_marked`: counter-shaped / delta-sensitive.
- `wanctl_cake_tin_delay_us`: gauge-shaped, likely sparse-compatible if isolated.
- `wanctl_cake_tin_backlog_bytes`: gauge-shaped, likely sparse-compatible if isolated.

A partial gauge-only optimization was rejected because it would create mixed sparse/continuous density inside the same operator-facing `--tins` output and is outside the phase's all-or-defer gate.

## Live checks

Steering health still exposes current per-tin stats from memory:

```text
health_tins_present=True
health_tins_count=4
Bulk: dropped_packets=0, ecn_marked_packets=0, avg_delay_us=3, peak_delay_us=10, backlog_bytes=0
BestEffort: dropped_packets=67169, ecn_marked_packets=604, avg_delay_us=12, peak_delay_us=76, backlog_bytes=0
```

SQLite history currently has no recent per-tin rows under external cake-autorate ownership:

```text
sudo -n env PYTHONPATH=/opt python3 -m wanctl.history --tins --last 1h --json
No per-tin data found for the specified time range.
```

## Verification

Relevant tests:

```text
.venv/bin/pytest -o addopts='' tests/test_history_cli.py::TestPerTinHistory tests/steering/test_steering_metrics_recording.py -q
28 passed in 0.58s
```

`git diff --check`: passed.

No source code changed.

## Requirement disposition

- TIN-01: complete.
- TIN-02: deferred to v1.55/future phase because the consumer audit found raw-history/counter-sensitive semantics.
- TIN-03: deferred with TIN-02 because no implementation shipped.

## Self-check: PASSED
