# Phase 181 Live Reader Parity Report

**Captured:** 2026-04-14T12:26:25Z  
**Host:** `kevin@10.10.110.223`  
**Requirement:** `STOR-06`

## Objective

Capture the final live history-reader behavior after the Phase 181 repo changes and the startup recovery fix, then state the operator truth plainly.

## Evidence Sources

```bash
ssh -o BatchMode=yes kevin@10.10.110.223 'sudo -n env PYTHONPATH=/opt python3 -m wanctl.history --last 1h --metrics wanctl_rtt_ms --json'
ssh -o BatchMode=yes kevin@10.10.110.223 'curl -s "http://10.10.110.223:9101/metrics/history?range=1h&limit=5"'
ssh -o BatchMode=yes kevin@10.10.110.223 'curl -s "http://10.10.110.227:9101/metrics/history?range=1h&limit=5"'
./scripts/canary-check.sh --ssh kevin@10.10.110.223 --expect-version 1.35.0 --json
./scripts/soak-monitor.sh --ssh kevin@10.10.110.223 --json
```

## Live Reader Results

### CLI module path

- invocation:
  - `sudo -n env PYTHONPATH=/opt python3 -m wanctl.history --last 1h --metrics wanctl_rtt_ms --json`
- WANs present:
  - `att`
  - `spectrum`
- total rows returned:
  - `56520`

Interpretation:
- the module-based CLI remains the authoritative merged cross-WAN proof path

### HTTP endpoint on Spectrum

- endpoint:
  - `http://10.10.110.223:9101/metrics/history?range=1h&limit=5`
- response metadata:
  - `mode: local_configured_db`
  - `db_paths: ['/var/lib/wanctl/metrics-spectrum.db']`
- WANs present in sampled rows:
  - `spectrum`

### HTTP endpoint on ATT

- endpoint:
  - `http://10.10.110.227:9101/metrics/history?range=1h&limit=5`
- response metadata:
  - `mode: local_configured_db`
  - `db_paths: ['/var/lib/wanctl/metrics-att.db']`
- WANs present in sampled rows:
  - `att`

Interpretation:
- the live HTTP path now proves its narrowed role explicitly through response metadata
- the old accidental ambiguity is closed
- the CLI and HTTP surfaces are intentionally different, not accidentally inconsistent

## Operator Surface Health

### Canary

`./scripts/canary-check.sh --ssh kevin@10.10.110.223 --expect-version 1.35.0 --json`

Result:
- `spectrum`: `warn`
- `att`: `pass`
- `steering`: `pass`

The Spectrum warning was a `runtime warning`, not a top-level health or storage failure:

- top-level health remained `healthy`
- router reachability remained `true`
- `storage.status` remained `ok`
- version check passed

### Soak monitor

`./scripts/soak-monitor.sh --ssh kevin@10.10.110.223 --json`

Result:
- both WAN health payloads remained `healthy`
- both WANs reported `storage.status: ok`
- `spectrum` reported `runtime.status: warning`
- `att` reported `runtime.status: ok`

## Final Operator Truth

- `python3 -m wanctl.history` is the authoritative merged cross-WAN reader
- `/metrics/history` is the endpoint-local history surface for the daemon serving that IP
- the HTTP endpoint preserves the existing `{data, metadata}` envelope and now makes the narrowed role explicit through `metadata.source`
- canary and soak-monitor remain usable after the startup recovery, though Spectrum currently carries a non-blocking runtime warning

## Docs Alignment

The current operator docs already match this live behavior:

- [docs/DEPLOYMENT.md](/home/kevin/projects/wanctl/docs/DEPLOYMENT.md)
- [docs/RUNBOOK.md](/home/kevin/projects/wanctl/docs/RUNBOOK.md)

No further docs narrowing was required in this closeout because the checked-in docs already describe:

- CLI as the authoritative merged proof path
- `/metrics/history` as endpoint-local
- explicit use of `compact-metrics-dbs.sh` when DB files stay materially larger than expected
