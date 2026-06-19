---
phase: "249"
plan: "249-01"
status: complete
completed_at: "2026-06-19T15:36:48-05:00"
requirements:
  - GAUGE-01
  - GAUGE-02
  - GAUGE-03
verdict: audit_no_current_candidates_no_code_change
key_files:
  created:
    - .planning/phases/249-autorate-flat-gauge-fire-on-change/249-01-PLAN.md
    - .planning/phases/249-autorate-flat-gauge-fire-on-change/249-01-SUMMARY.md
    - .planning/phases/249-autorate-flat-gauge-fire-on-change/evidence/live-ingestion-audit-20260619T203648Z.md
verification:
  - read-only live ingestion-rate audit on cake-shaper for 60s, 300s, 3600s windows
  - read-only live variance/distinct-value audit on both WAN DBs
  - git diff --check
---

# Plan 249-01 Summary — Autorate Flat-Gauge Fire-on-Change Audit

## Outcome

Phase 249 closed as an audit-driven no-op.

The current stable live deployment has no per-metric write-rate candidates that satisfy the Phase 249 mutation threshold:

- current 60s window: zero confirmed >=2Hz flat-gauge candidates on Spectrum or ATT;
- current 300s window: zero confirmed >=2Hz flat-gauge candidates on Spectrum or ATT.

Because there are no confirmed candidates, no source code change is warranted.

## Live audit result

Stable current windows:

```text
=== window=60s ===
spectrum: total_metrics_ge_0.9hz=6 confirmed_flat_candidates_ge_2hz=0
att: total_metrics_ge_0.9hz=6 confirmed_flat_candidates_ge_2hz=0

=== window=300s ===
spectrum: total_metrics_ge_0.9hz=6 confirmed_flat_candidates_ge_2hz=0
att: total_metrics_ge_0.9hz=6 confirmed_flat_candidates_ge_2hz=0
```

Historical 3600s window:

```text
spectrum: total_metrics_ge_0.9hz=23 confirmed_flat_candidates_ge_2hz=3
  wanctl_cake_backlog_bytes rows=10468 rps=2.91 distinct=1 min=0.0 max=0.0
  wanctl_cake_drop_rate rows=10468 rps=2.91 distinct=1 min=0.0 max=0.0
  wanctl_cake_total_drop_rate rows=10468 rps=2.91 distinct=1 min=0.0 max=0.0
att: total_metrics_ge_0.9hz=6 confirmed_flat_candidates_ge_2hz=0
```

The 3600s Spectrum candidates are classified as contaminated by the earlier native wanctl/fping canaries from Phases 248.3/248.4. They are not current stable external cake-autorate candidates.

Clean-window confirmation after reviewer pushback:

```text
=== clean-window-confirmation window=300s ===
spectrum: metrics_ge_2hz=0 confirmed_flat_candidates_ge_2hz=0
att: metrics_ge_2hz=0 confirmed_flat_candidates_ge_2hz=0

=== clean-window-confirmation window=600s ===
spectrum: metrics_ge_2hz=0 confirmed_flat_candidates_ge_2hz=0
att: metrics_ge_2hz=0 confirmed_flat_candidates_ge_2hz=0

=== clean-window-confirmation window=900s ===
spectrum: metrics_ge_2hz=0 confirmed_flat_candidates_ge_2hz=0
att: metrics_ge_2hz=0 confirmed_flat_candidates_ge_2hz=0
```

This confirms the empty candidate set in uncontaminated current windows.

## Why no code change

The requirement says to identify gauges emitting at >=2Hz with near-zero value variance, then apply fire-on-change to each confirmed candidate one per canary cycle.

In the current stable deployment windows, the candidate set is empty.

Applying fire-on-change to 3600s-only native-canary artifacts would be premature and could mutate controller-path observability for a deployment mode that is not currently live. That would violate the storage-hygiene scope discipline.

## Requirement disposition

- GAUGE-01: complete. Both WANs were audited via live read-only ingestion-rate and variance queries.
- GAUGE-02: complete by empty set. No confirmed candidates exist, so there are no candidate mutations to perform.
- GAUGE-03: complete by empty set. No changed metrics means no new candidate-specific tests are required.

## Operational note

`wanctl-history` is deployed incorrectly on `cake-shaper`:

```text
/usr/local/bin/wanctl-history -> /opt/wanctl/scripts/wanctl-history
/opt/wanctl/scripts/wanctl-history is absent
```

The working read-only invocation was:

```bash
sudo -n env PYTHONPATH=/opt python3 -m wanctl.history \
  --ingestion-rate --by-table --rolling=60,300,3600 --json
```

This symlink/tooling issue is not Phase 249 metric behavior scope, but it is worth fixing in a small future tooling hygiene pass.

## Verification

- Read-only live DB audit completed on both WAN DBs.
- Second clean-window audit completed after reviewer pushback.
- No source files changed.
- `git diff --check` passed.

## Self-check: PASSED
