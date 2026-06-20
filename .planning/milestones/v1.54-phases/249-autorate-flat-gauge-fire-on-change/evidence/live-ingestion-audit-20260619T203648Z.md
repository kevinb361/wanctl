# Phase 249 Live Ingestion Audit Evidence — 2026-06-19T203648Z

## Purpose

Satisfy GAUGE-01 and determine whether GAUGE-02/GAUGE-03 have any current live candidates.

## Commands

Initial documented CLI path was stale on `cake-shaper`:

```text
wanctl-history: command not found
/usr/local/bin/wanctl-history -> /opt/wanctl/scripts/wanctl-history
/opt/wanctl/scripts/wanctl-history: No such file or directory
```

Working read-only module invocation:

```bash
sudo -n env PYTHONPATH=/opt python3 -m wanctl.history \
  --ingestion-rate --by-table --rolling=60,300,3600 --json
```

Additional variance check:

```sql
SELECT metric_name,
       COUNT(*) AS n,
       COUNT(DISTINCT value) AS distinct_values,
       MIN(value) AS min_value,
       MAX(value) AS max_value
FROM metrics
WHERE timestamp BETWEEN ? AND ?
GROUP BY metric_name
HAVING (COUNT(*) / ?) >= 0.9
ORDER BY (COUNT(*) / ?) DESC, metric_name;
```

Run with windows 60s, 300s, and 3600s against:

- `/var/lib/wanctl/metrics-spectrum.db`
- `/var/lib/wanctl/metrics-att.db`

## Stable-window results

Current stable deployment windows:

```text
=== window=60s ===
spectrum: total_metrics_ge_0.9hz=6 confirmed_flat_candidates_ge_2hz=0
att: total_metrics_ge_0.9hz=6 confirmed_flat_candidates_ge_2hz=0

=== window=300s ===
spectrum: total_metrics_ge_0.9hz=6 confirmed_flat_candidates_ge_2hz=0
att: total_metrics_ge_0.9hz=6 confirmed_flat_candidates_ge_2hz=0
```

Interpretation:

- No metric on either WAN currently emits at >=2Hz in the stable 60s/300s windows.
- Therefore there are no current confirmed flat-gauge candidates for fire-on-change mutation.

## Clean-window confirmation after reviewer pushback

A second read-only audit was run after additional time had elapsed, explicitly checking clean 300s/600s/900s windows after the earlier native canaries had aged out of the short windows:

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

This addresses the closeout concern that the first audit's 3600s window was contaminated. The short clean windows still have an empty candidate set.

## Historical 3600s context

The 3600s window included earlier native wanctl/fping canaries from Phases 248.3/248.4, so it is not representative of the current stable external cake-autorate deployment.

It did show Spectrum candidates:

```text
=== window=3600s ===
spectrum: total_metrics_ge_0.9hz=23 confirmed_flat_candidates_ge_2hz=3
  wanctl_cake_backlog_bytes rows=10468 rps=2.91 distinct=1 min=0.0 max=0.0
  wanctl_cake_drop_rate rows=10468 rps=2.91 distinct=1 min=0.0 max=0.0
  wanctl_cake_total_drop_rate rows=10468 rps=2.91 distinct=1 min=0.0 max=0.0
```

Additional >=2Hz rows in the 3600s contaminated window:

```text
wanctl_cake_backlog_bytes rows=10468 rps=2.91 distinct=1 min=0 max=0
wanctl_cake_drop_rate rows=10468 rps=2.91 distinct=1 min=0 max=0
wanctl_cake_peak_delay_us rows=10468 rps=2.91 distinct=6 min=310 max=2817
wanctl_cake_total_drop_rate rows=10468 rps=2.91 distinct=1 min=0 max=0
wanctl_state rows=8511 rps=2.36 distinct=2 min=0 max=1
wanctl_rate_download_mbps rows=8509 rps=2.36 distinct=194 min=500 max=920
wanctl_rate_upload_mbps rows=8509 rps=2.36 distinct=3 min=12 max=18
wanctl_rtt_baseline_ms rows=8509 rps=2.36 distinct=3938 min=20.9619 max=23.5719
wanctl_rtt_delta_ms rows=8509 rps=2.36 distinct=4303 min=-4.24373 max=26.3145
wanctl_rtt_ms rows=8509 rps=2.36 distinct=30 min=18.9 max=52.3021
```

ATT 3600s:

```text
att: total_metrics_ge_0.9hz=6 confirmed_flat_candidates_ge_2hz=0
```

Interpretation:

- The 3600s Spectrum CAKE rows came from the earlier native controller canary window, not the current stable external cake-autorate owner.
- They are useful future candidates if native controller ownership becomes stable again, but they are not safe current Phase 249 mutation targets.

## Requirement disposition

- GAUGE-01: complete. Both WANs audited with read-only live DB queries.
- GAUGE-02: complete by empty set. No confirmed current candidates exist, so there are no metrics to mutate one-per-canary.
- GAUGE-03: complete by empty set. No changed metrics means no candidate-specific tests are required.

## Operational note

`/usr/local/bin/wanctl-history` on `cake-shaper` is a stale symlink to `/opt/wanctl/scripts/wanctl-history`, which is absent. This is not Phase 249 scope because the module invocation worked and no production metric behavior depends on the symlink, but it is a small future tooling hygiene item.

## Verdict

Phase 249 closes as audit-driven no-op.

No source code change is warranted from current live data.
