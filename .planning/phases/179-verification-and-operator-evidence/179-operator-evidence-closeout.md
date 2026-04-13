# Phase 179 Operator Evidence Closeout

**Requirement:** `OPER-04`
**Closed:** 2026-04-13

## Outcome

`OPER-04` is satisfied.

Operators now have a documented and repeatable production proof path for:

- identifying which DB files are active
- interpreting `storage.status` correctly
- determining whether the footprint reduction actually held in production

That closeout is evidence-backed, and the conclusion is intentionally narrow:

- the active per-WAN footprint did **not** materially shrink relative to the fixed 2026-04-13 baseline
- `storage.status` remains `ok` on the supported operator surface
- the shared steering `metrics.db` remains active and must be evaluated separately from the per-WAN autorate DBs

## Baseline Comparison

From [179-production-footprint-report.md](/home/kevin/projects/wanctl/.planning/phases/179-verification-and-operator-evidence/179-production-footprint-report.md):

- `metrics-spectrum.db`: effectively unchanged versus the 2026-04-13 baseline
- `metrics-att.db`: effectively unchanged versus the 2026-04-13 baseline
- `metrics.db`: grew and remains a separate shared steering inventory item

Operator meaning:

- Phase 178 changed the retention profile in repo and deployment config
- Phase 179 does **not** prove a material size reduction has already happened on production
- the supported operator reading is therefore "healthy but not yet smaller"

## Reader Topology Result

From [179-live-reader-topology-report.md](/home/kevin/projects/wanctl/.planning/phases/179-verification-and-operator-evidence/179-live-reader-topology-report.md):

- the deployed CLI reader works through:

```bash
ssh <host> 'sudo -n env PYTHONPATH=/opt python3 -m wanctl.history --last 1h --metrics wanctl_rtt_ms --json'
```

- that CLI path returns both `att` and `spectrum` and is the authoritative cross-WAN proof surface today
- the live `/metrics/history` endpoint preserves its response envelope, but current deployed behavior does not yet prove merged cross-WAN history
- direct DB inventory still confirms the intended active file layout:
  - `metrics-spectrum.db`
  - `metrics-att.db`
  - `metrics.db`
  - stale zero-byte `spectrum_metrics.db` and `att_metrics.db`

## Repeatable Operator Proof Path

Use this exact order:

1. Active DB inventory

```bash
ssh <host> 'sudo -n stat -c "%n %s %y" /var/lib/wanctl/metrics-spectrum.db /var/lib/wanctl/metrics-att.db /var/lib/wanctl/metrics.db /var/lib/wanctl/spectrum_metrics.db /var/lib/wanctl/att_metrics.db 2>/dev/null'
```

2. Supported storage-status surface

```bash
./scripts/soak-monitor.sh --json
```

3. Cross-WAN history proof

```bash
ssh <host> 'sudo -n env PYTHONPATH=/opt python3 -m wanctl.history --last 1h --metrics wanctl_rtt_ms --json | python3 -m json.tool | head -n 40'
```

4. HTTP envelope check

```bash
ssh <host> 'curl -s "http://<health-ip>:9101/metrics/history?range=1h&limit=5" | python3 -m json.tool'
```

5. Direct DB spot-check, if the reader surfaces disagree

```bash
ssh <host> 'sudo -n sqlite3 -json /var/lib/wanctl/metrics-spectrum.db "SELECT timestamp, granularity, metric_name FROM metrics ORDER BY timestamp ASC LIMIT 1; SELECT timestamp, granularity, metric_name FROM metrics ORDER BY timestamp DESC LIMIT 1;"'
ssh <host> 'sudo -n sqlite3 -json /var/lib/wanctl/metrics-att.db "SELECT timestamp, granularity, metric_name FROM metrics ORDER BY timestamp ASC LIMIT 1; SELECT timestamp, granularity, metric_name FROM metrics ORDER BY timestamp DESC LIMIT 1;"'
ssh <host> 'sudo -n sqlite3 -json /var/lib/wanctl/metrics.db "SELECT timestamp, granularity, metric_name FROM metrics ORDER BY timestamp ASC LIMIT 1; SELECT timestamp, granularity, metric_name FROM metrics ORDER BY timestamp DESC LIMIT 1;"'
```

## Residual Uncertainty

One production mismatch remains explicit:

- the repo intends `/metrics/history` to follow the same discovered per-WAN topology as the CLI reader
- the deployed HTTP endpoint did not prove that on 2026-04-13

That does not block `OPER-04`, because the operator proof path is still repeatable and complete. It does mean the HTTP reader should be treated as a follow-up correctness issue rather than as the authoritative cross-WAN proof surface.
