# wanctl Observability Runbook

Use this runbook after deploys and during incident response. For YAML tuning details, see [CONFIGURATION.md](/home/kevin/projects/wanctl/docs/CONFIGURATION.md). For deploy flow, service units, and remote rollout steps, see [DEPLOYMENT.md](/home/kevin/projects/wanctl/docs/DEPLOYMENT.md).

## Quick Reference

| Signal | Warn / watch | Critical / act now | Operator action |
| --- | --- | --- | --- |
| Congestion zones (DL) | `YELLOW`: RTT delta above `target_bloat_ms`; `SOFT_RED`: RTT delta above `warn_bloat_ms` **(config)** | `RED`: RTT delta above `hard_red_bloat_ms` **(config)** | Watch YELLOW; act on sustained SOFT_RED/RED or repeated alerts. |
| Congestion zones (UL) | `YELLOW`: RTT delta above `target_bloat_ms` **(config)** | `RED`: RTT delta above `warn_bloat_ms` **(config)** | Watch YELLOW; act on sustained RED. |
| WAL size | `>= 128 MB` (`WAL_WARNING_BYTES`) **(constant)** | `>= 256 MB` (`WAL_CRITICAL_BYTES`) **(constant)** | Check growth trend, maintenance cadence, and free disk. |
| Pending writes | `>= 5` (`PENDING_WRITES_WARNING`) **(constant)** | `>= 20` (`PENDING_WRITES_CRITICAL`) **(constant)** | Inspect writer backlog and storage latency. |
| Lock failures | n/a | `> 0` lock failures **(constant)** | Treat as storage critical; investigate DB lock contention immediately. |
| Checkpoint busy | n/a | `> 0` busy checkpoints **(constant)** | Treat as storage critical; inspect checkpoint pressure and disk state. |
| RSS memory | `>= 256 MB` (`RSS_WARNING_BYTES`) **(constant)** | `>= 512 MB` (`RSS_CRITICAL_BYTES`) **(constant)** | Watch for growth; act for suspected leak or runaway process. |
| Cycle utilization | `>= 80%` (`warning_threshold_pct` default) **(config)** | `>= 100%` **(derived)** | Watch for sustained pressure; act if controller is overrunning cycle budget. |
| Disk space | `< 100 MB` free (`_DISK_SPACE_WARNING_BYTES`) **(constant)** | n/a | Clean logs, snapshots, or stale artifacts before service degrades further. |
| Top-level `/health` | HTTP `200` when healthy **(derived)** | HTTP `503` when degraded **(derived)** | `503` means one of: 3+ consecutive failures, router unreachable, or disk warning. |

## Signal Classes

### Congestion Zones

Congestion zones are per-cycle classifications. The controller reevaluates them every 50 ms, so zones are immediate telemetry, not incident declarations.

| Model | GREEN | YELLOW | SOFT_RED | RED |
| --- | --- | --- | --- | --- |
| Download | `delta <= target_bloat_ms` **(config)** | `target_bloat_ms < delta <= warn_bloat_ms` **(config)** | `warn_bloat_ms < delta <= hard_red_bloat_ms` **(config)** | `delta > hard_red_bloat_ms` **(config)** |
| Upload | `delta <= target_bloat_ms` **(config)** | `target_bloat_ms < delta <= warn_bloat_ms` **(config)** | n/a | `delta > warn_bloat_ms` **(config)** |

`delta` is `load_rtt - baseline_rtt`, not absolute RTT. Default example values in [CONFIGURATION.md](/home/kevin/projects/wanctl/docs/CONFIGURATION.md) are `target_bloat_ms: 15`, `warn_bloat_ms: 45`, `hard_red_bloat_ms: 80`, but operators should treat YAML as authoritative for a given deployment.

Watch:
- Single-WAN `YELLOW`
- Short-lived `SOFT_RED`

Act now:
- Both WANs in `RED`
- One WAN held in `SOFT_RED` or `RED` long enough to trigger sustained alerts

Example autorate `/health` excerpt:

```json
{
  "wans": [
    {
      "name": "<wan_name>",
      "download": { "state": "SOFT_RED", "current_rate_mbps": 412.0 },
      "upload": { "state": "YELLOW", "current_rate_mbps": 31.0 }
    }
  ]
}
```

Tune thresholds in YAML, not in Python. See [CONFIGURATION.md](/home/kevin/projects/wanctl/docs/CONFIGURATION.md).

### Alert Types

Alerts are rate-limited event notifications layered on top of the per-cycle zones above. Unless overridden per rule, `default_cooldown_sec: 300` and `default_sustained_sec: 60` apply **(config)**.

#### Congestion Alerts

| Alert type | Severity | Trigger | Watch | Act |
| --- | --- | --- | --- | --- |
| `congestion_sustained_dl` | warning in `SOFT_RED`, critical in `RED` **(derived)** | DL stays in `SOFT_RED` or `RED` for `default_sustained_sec` or rule override **(config)** | Confirm whether only one WAN is affected and whether rates are already clamped. | Intervene for critical `RED`, repeated warnings, or user-visible degradation. |
| `congestion_sustained_ul` | critical | UL stays in `RED` for `default_sustained_sec` or rule override **(config)** | Verify whether upstream saturation is expected. | Act immediately; upload has no SOFT_RED buffer state. |
| `congestion_recovered_dl` | recovery | DL returns to `GREEN` after a sustained DL congestion alert **(derived)** | Confirm recovery is stable. | No action unless it flaps back into sustained congestion. |
| `congestion_recovered_ul` | recovery | UL returns to `GREEN` after a sustained UL congestion alert **(derived)** | Confirm recovery is stable. | No action unless RED returns quickly. |

#### Latency And Burst Alerts

| Alert type | Severity | Trigger | Watch | Act |
| --- | --- | --- | --- | --- |
| `latency_regression` | warning or critical **(derived)** | RTT delta stays above `target_bloat_ms` outside GREEN for sustained period; critical when delta reaches `warn_bloat_ms` or zone is `SOFT_RED`/`RED` **(config)** | Compare `baseline_rtt_ms`, `load_rtt_ms`, and zone state. | Act on critical alerts or repeated warnings after traffic normalizes. |
| `burst_churn_dl` | warning by default **(config)** | `trigger_threshold: 3` burst triggers within `trigger_window_sec: 300` **(config)** | Check whether temporary bursts match expected workload. | Investigate recurring burst-trigger storms or correlated user complaints. |
| `baseline_drift` | warning | Baseline drifts `>= 50%` from initial baseline or per-rule override **(config)** | Check if path characteristics changed after routing or ISP changes. | Act if drift persists and invalidates expected congestion thresholds. |
| `congestion_flapping` (`flapping_dl` / `flapping_ul`) | warning by default **(config)** | `flap_threshold: 30` transitions inside `flap_window_sec: 120`, counting only states held for `min_hold_sec: 1.0` **(config)** | Watch if the line is noisy but service remains usable. | Act if flapping prevents stable recovery or follows configuration changes. |

#### WAN Connectivity Alerts

| Alert type | Severity | Trigger | Watch | Act |
| --- | --- | --- | --- | --- |
| `wan_offline` | critical | All ICMP targets unreachable for sustained period, default 60s unless rule override **(config)** | Check if this is a maintenance window or target-side reachability issue. | Treat as service-impacting; verify router path and WAN reachability immediately. |
| `wan_recovered` | recovery | ICMP reaches targets again after `wan_offline` fired **(derived)** | Confirm traffic recovers and alerts stop. | No action unless it oscillates back offline. |

#### Infrastructure Alerts

| Alert type | Severity | Trigger | Watch | Act |
| --- | --- | --- | --- | --- |
| `cycle_budget_warning` | warning | 60 consecutive cycles over `warning_threshold_pct`, default `80%` **(config)** | Watch for transient high utilization after deploy or startup. | Act if it persists or coincides with overruns, delayed reactions, or high RSS. |
| `hysteresis_suppression` | warning | More than `suppression_alert_threshold` suppressions in a 60s congestion window **(config)** | Check if the controller is intentionally holding rates during noisy congestion. | Act when suppressions are frequent enough to mask real instability. |

#### IRTT Alerts

| Alert type | Severity | Trigger | Watch | Act |
| --- | --- | --- | --- | --- |
| `irtt_loss_upstream` | warning | Upstream IRTT loss `>= 5%` or rule override for sustained period **(config)** | Compare with ICMP health and path-specific loss. | Act if it persists or pairs with congestion/latency alerts. |
| `irtt_loss_downstream` | warning | Downstream IRTT loss `>= 5%` or rule override for sustained period **(config)** | Compare with downstream queue state and reflector health. | Act if it persists or impacts user flows. |
| `irtt_loss_recovered` | recovery | IRTT loss clears after sustained upstream or downstream alert **(derived)** | Confirm the reflector and path remain clean. | No action unless it regresses again quickly. |

#### Steering Alerts

| Alert type | Severity | Trigger | Watch | Act |
| --- | --- | --- | --- | --- |
| `steering_activated` | warning | Steering daemon transitions from good to degraded state **(derived)** | Check confidence, queue signals, and whether only new flows should move. | Act if steering stays active, if confidence is low, or if both WANs are poor. |
| `steering_recovered` | recovery | Steering returns from degraded to good state **(derived)** | Confirm duration and post-recovery health. | No action unless steering reactivates repeatedly. |

### Storage Pressure

Storage status uses `ok`, `warning`, and `critical`.

| Signal | Warning threshold | Critical threshold | Operator action |
| --- | --- | --- | --- |
| WAL size | `>= 128 MB` (`WAL_WARNING_BYTES`) **(constant)** | `>= 256 MB` (`WAL_CRITICAL_BYTES`) **(constant)** | Warning: inspect WAL growth trend. Critical: check maintenance schedule and disk headroom. |
| Pending writes | `>= 5` (`PENDING_WRITES_WARNING`) **(constant)** | `>= 20` (`PENDING_WRITES_CRITICAL`) **(constant)** | Warning: watch queue drain rate. Critical: investigate blocked writes or slow storage. |
| Lock failures | n/a | any non-zero lock failures **(constant)** | Treat as immediate storage contention. |
| Checkpoint busy | n/a | any non-zero busy count **(constant)** | Treat as immediate checkpoint pressure. |

`queue.error_total` is diagnostic history, not a current-pressure threshold. Storage critical status can degrade a WAN summary row even when top-level `/health` still reports healthy.

### Runtime Pressure

Runtime status also uses `ok`, `warning`, and `critical`.

| Signal | Warning threshold | Critical threshold | Operator action |
| --- | --- | --- | --- |
| RSS memory | `>= 256 MB` (`RSS_WARNING_BYTES`) **(constant)** | `>= 512 MB` (`RSS_CRITICAL_BYTES`) **(constant)** | Warning: monitor trend. Critical: check for leaks, stuck workers, or runaway logging. |
| Cycle utilization | `>= warning_threshold_pct` (default `80%`) **(config)** | `>= 100%` utilization **(derived)** | Warning: watch for sustained pressure. Critical: investigate cycle overruns and controller lag. |

`runtime.status` is the max of memory and cycle status **(derived)**.

### Disk Space

Disk space warning is `< 100 MB` free (`_DISK_SPACE_WARNING_BYTES`) **(constant)**. There is no separate disk critical tier in the current health contract; instead, low disk space directly contributes to top-level degraded status **(derived)**.

Action:
- Warning: clean old logs, retained fixtures, or stale runtime artifacts.
- Escalate if free space stays low after cleanup or prevents maintenance work.

## Reading The Health Endpoint

Top-level `status` is a separate contract from per-WAN storage/runtime pressure:

1. Storage and runtime builders emit `ok` / `warning` / `critical`.
2. Summary rows classify each WAN or steering service as `ok` / `warning` / `degraded`.
3. `summary.rows` feed `degraded_wans` and `warning_wans` lists on autorate.
4. Top-level `status` is `degraded` only when `consecutive_failures >= 3`, any router is unreachable, or disk space is warning **(derived)**.

That means storage/runtime warnings affect summary rows first, not the top-level HTTP status directly.

Autorate example (`http://<host>:9101/health`):

```json
{
  "status": "healthy",
  "consecutive_failures": 0,
  "router_reachable": true,
  "disk_space": { "status": "ok" },
  "summary": {
    "service": "autorate",
    "status": "healthy",
    "degraded_wans": [],
    "warning_wans": ["<wan_name>"],
    "rows": [
      {
        "name": "<wan_name>",
        "status": "warning",
        "download_state": "SOFT_RED",
        "upload_state": "YELLOW",
        "storage_status": "ok",
        "runtime_status": "warning",
        "router_reachable": true
      }
    ]
  }
}
```

Steering example (`http://<host>:9102/health`):

```json
{
  "status": "healthy",
  "router_reachable": true,
  "disk_space": { "status": "ok" },
  "summary": {
    "service": "steering",
    "status": "healthy",
    "rows": [
      {
        "name": "steering",
        "status": "warning",
        "state": "DEGRADED",
        "congestion_state": "RED",
        "wan_zone": "RED",
        "storage_status": "ok",
        "runtime_status": "ok",
        "router_reachable": true
      }
    ]
  }
}
```

Alerting summary status is separate again:
- `disabled`: alerting disabled in YAML
- `idle`: enabled with no active cooldowns
- `active`: enabled with one or more active cooldowns

## Measurement Health Inspection

Multi-flow download reproduction such as `tcp_12down` can collapse reflector
measurement quality while autorate otherwise appears `healthy`/`GREEN`. The
measurement-resilience milestone surfaces that honesty signal on `/health`
inside each WAN entry under `.wans[].measurement` so operators can see when current RTT is
degraded instead of silently treating stale cached RTT as fresh. Phase 187
keeps the SAFE-02 ICMP-failure fallback path unchanged; this is additive
inspection guidance, not a behavior change for real outages.

On shared multi-WAN hosts, treat concurrent same-target IRTT as a separate risk from ICMP reflector collapse. Current production guidance is:
- keep each WAN on a distinct IRTT target when possible
- otherwise disable IRTT on the secondary WAN instead of pointing both daemons at the same server
- do not read a `collapsed` measurement window as proof of router failure by itself

### Measurement Contract

| Field | Values | What it means for the operator |
| --- | --- | --- |
| `measurement.state` | `healthy` / `reduced` / `collapsed` | Derived from the count of reflectors that produced a successful RTT sample in the most recent background cycle. |
| `measurement.successful_count` | integer `>= 0` (practical range `0..3` on the current 3-reflector deployment) | Raw reflector-success count behind `state`. |
| `measurement.stale` | `true` / `false` | `true` when the last raw RTT sample age exceeds `3 * cadence_sec`, or when cadence is unknown (startup, failed thread). |

`state` and `stale` are orthogonal. A WAN can be `state="healthy"` and
`stale=true` simultaneously, so operator judgement must handle the
cross-product rather than assuming a single severity axis.

### Bounded Inspection Recipe

Direct `/health` inspection:

```bash
curl -s http://10.10.110.223:9101/health \
  | python3 -m json.tool \
  | grep -A6 '"measurement"'
```

Direct `/health` inspection with a narrowed measurement view:

```bash
ssh kevin@10.10.110.223 'curl -s http://10.10.110.223:9101/health' \
  | jq '.wans[] | {name, download: .download.state, upload: .upload.state, measurement: .measurement}'
```

Bounded collector via `soak-monitor`:

```bash
./scripts/soak-monitor.sh --json \
  | jq '.[] | select(.wan) | {wan, state: .health.summary.rows[0].status, measurement: .health.wans[0].measurement}'
```

Operator summary entry point:

```bash
wanctl-operator-summary http://10.10.110.223:9101/health http://10.10.110.227:9101/health
```

### Pass / Fail Correlation Rubric

| Observed `/health` measurement | Operator reading |
| --- | --- |
| `state="healthy"`, `stale=false`, `successful_count=3` | measurement honest, any latency regression is a real congestion or path event, not a measurement collapse. |
| `state="reduced"`, `successful_count=2` | single reflector drop; watch for correlation with latency spikes. Not a controller action on its own. |
| `state="collapsed"`, `successful_count<=1`, `stale=false` | measurement has collapsed on the current cycle; recent latency spikes on this WAN are NOT trustworthy as a controller signal and match the Phase 187 honesty path. |
| `state="healthy"`, `stale=true` | quorum is nominally present but the last raw RTT sample is older than `3 * cadence_sec`; treat as measurement-degraded, not as a fresh healthy sample. |
| any `state` with `successful_count=0` | zero-success cycle; Phase 187 keeps bounded controller behavior but the operator reading is "do not tune on this window." |

Production note from `cake-shaper`:
- If RRUL reproduces repeated `collapsed` windows on one WAN while another WAN shares the host, first check whether both WANs are configured against the same IRTT server.
- If the secondary WAN stays green after disabling its IRTT, leave that safer setting in place until a distinct IRTT target exists.

> What This Does Not Change: SAFE-02 ICMP-failure fallback, total-connectivity
> handling, controller thresholds, and steering policy are unchanged by the
> measurement-resilience milestone.
> This section is inspection-only and must not be read as a tuning instruction.
> Follow the post-deploy flow in [DEPLOYMENT.md](/home/kevin/projects/wanctl/docs/DEPLOYMENT.md)
> and escalate through [Escalation Flow](#escalation-flow) when the rubric
> shows degraded measurement.

## Canary Check

`scripts/canary-check.sh` is the post-deploy gate. It waits for `/health`, checks the compact summary contract, and exits with one of three codes:

| Exit code | Meaning | Checks | Operator action |
| --- | --- | --- | --- |
| `0` | PASS | Top-level health healthy, router reachable, storage ok, runtime ok, autorate states in `GREEN` or `YELLOW`, no warnings | Safe to proceed with normal monitoring. |
| `1` | FAIL | Top-level health not healthy, router unreachable, storage critical, runtime critical, or unknown DL/UL state | Do not leave service running unattended until resolved. |
| `2` | WARN | Storage warning, runtime warning, DL/UL in `SOFT_RED` or `RED`, version mismatch, or low uptime | Investigate before signing off on the deploy. |

Exit 0 means safe to proceed. Exit 1 means do not continue until resolved. Exit 2 means investigate before proceeding.

Use after every deploy:

```bash
scripts/canary-check.sh --ssh <host>
```

Optional offline check:

```bash
scripts/canary-check.sh --input /tmp/<wan_name>-health.json
```

Note: `scripts/canary-check.sh` contains deployment-specific default autorate and steering targets. For non-production installs, either run it with `--input` against captured health JSON or adjust the target arrays before relying on default local/SSH checks.

## Operator Tools Reference

| Tool | Purpose | Example |
| --- | --- | --- |
| `wanctl-operator-summary` | Render compact summary rows from health JSON | `wanctl-operator-summary http://<host>:9101/health http://<host>:9102/health` |
| `scripts/canary-check.sh` | Post-deploy pass/warn/fail validation | `scripts/canary-check.sh --ssh <host>` |
| `scripts/soak-monitor.sh` | Environment-specific soak health and journal summary for the current Spectrum/ATT deployment | `scripts/soak-monitor.sh` |
| `wanctl-check-config` | Validate WAN or steering YAML before restart | `wanctl-check-config /etc/wanctl/<wan_name>.yaml` |
| `wanctl-check-cake` | Audit live CAKE config on the router | `wanctl-check-cake /etc/wanctl/<wan_name>.yaml` |
| `wanctl-benchmark` | Run benchmark workflow for performance validation | `wanctl-benchmark --wan <wan_name> --label post-deploy` |
| `wanctl-history --alerts` | Inspect persisted alert history | `wanctl-history --alerts` |
| `curl .../health` | Inspect full JSON instead of summary view | `ssh <host> 'curl -s http://127.0.0.1:9101/health | python3 -m json.tool'` |

## Storage Topology And History Checks

Phase 178 leaves three active DB files in the production topology:

- `/var/lib/wanctl/metrics-spectrum.db` for Spectrum autorate
- `/var/lib/wanctl/metrics-att.db` for ATT autorate
- `/var/lib/wanctl/metrics.db` for shared steering metrics

The older `/var/lib/wanctl/spectrum_metrics.db` and `/var/lib/wanctl/att_metrics.db` names are
stale zero-byte cleanup candidates, not active runtime targets.

Use read-only checks to confirm the active set and current footprint:

```bash
ssh <host> 'sudo -n stat -c "%n %s %y" /var/lib/wanctl/metrics-spectrum.db /var/lib/wanctl/metrics-att.db /var/lib/wanctl/metrics.db /var/lib/wanctl/spectrum_metrics.db /var/lib/wanctl/att_metrics.db 2>/dev/null'
./scripts/soak-monitor.sh --json
```

`storage.status` remains the production-safe summary signal for footprint/maintenance health.
Use `./scripts/soak-monitor.sh --json` or the `/health` payload before reaching for direct DB inspection.

For retained history, use the supported readers instead of guessing a single DB path:

```bash
ssh <host> 'sudo -n env PYTHONPATH=/opt python3 -m wanctl.history --last 1h --metrics wanctl_rtt_ms --json | python3 -m json.tool | head -n 40'
ssh <host> 'curl -s "http://<health-ip>:9101/metrics/history?range=1h&limit=5" | python3 -m json.tool'
```

On the current production hosts:

- `/metrics/history` is the endpoint-local HTTP history view for the connected autorate daemon.
- `python3 -m wanctl.history` is the authoritative merged cross-WAN proof path.

Use the `curl` command above to confirm endpoint availability, response shape, and that WAN's
local history view. Use the `python3 -m wanctl.history` command above — falling back to direct
DB inventory only if the CLI is unavailable — when you need merged cross-WAN verification. The
dashboard history tab surfaces this same distinction through `metadata.source`, so the rule is
identical in the TUI and in this runbook.

If the per-WAN DB files stay materially larger than expected after retention cleanup runs,
compact them explicitly during a controlled restart window:

```bash
./scripts/compact-metrics-dbs.sh --ssh <host>
./scripts/canary-check.sh --ssh <host> --expect-version <deployed-version> --json
```

If only ATT remains above the expected footprint while Spectrum is already below baseline, use the ATT-only path:

```bash
./scripts/compact-metrics-dbs.sh --ssh <host> --wan att
./scripts/canary-check.sh --ssh <host> --expect-version <deployed-version> --json
./scripts/soak-monitor.sh --json
```

`scripts/compact-metrics-dbs.sh` stops the selected `wanctl@<wan>.service`, prunes old aggregate rows, checkpoints/truncates WAL, vacuums the SQLite DB, and restarts the service. Use it only during a controlled maintenance window; use `--dry-run` first when validating a new target.

`scripts/migrate-storage.sh` is a one-shot migration for older shared `/var/lib/wanctl/metrics.db` layouts. It stops WAN services, prunes legacy data, vacuums the DB, and archives it as `/var/lib/wanctl/metrics.db.pre-v135-archive`. Run it only when the archive marker is missing.

For 24h soak closeout, the err-level review should cover all claimed services, not only the WAN daemons:

```bash
ssh <host> 'journalctl -u wanctl@spectrum.service -u wanctl@att.service -u steering.service --since "24 hours ago" -p err --no-pager'
```

## Escalation Flow

### Watch

- Warning-level signals only
- Single-WAN `YELLOW`
- Storage warning
- Runtime warning
- Canary exit `2`

Action: keep monitoring, compare with recent deploy or traffic changes, and confirm whether the signal clears without intervention.

### Act Now

- Critical alerts such as `wan_offline` or `congestion_sustained_ul`
- Both WANs in `RED`
- Storage critical
- Runtime critical
- Canary exit `1`

Action: investigate immediately, confirm router reachability, inspect `/health`, and check logs with `journalctl -u wanctl@<wan_name> -f`.

### Escalate

- Act-now conditions repeat after intervention
- Unknown state persists in `/health` or canary output
- Canary exit `1` continues after service restart
- Operator cannot reconcile summary rows with detailed health sections

Action: escalate with the latest `/health` payloads from ports `9101` and `9102`, recent canary output, and the relevant deploy timestamp from [DEPLOYMENT.md](/home/kevin/projects/wanctl/docs/DEPLOYMENT.md).
