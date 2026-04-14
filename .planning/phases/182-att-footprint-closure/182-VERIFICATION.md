---
phase: 182-att-footprint-closure
verified: 2026-04-14T13:42:00Z
status: verified
score: 1/1 requirements verified
overrides_applied: 0
human_verification: []
deferred: []
---

# Phase 182: ATT Footprint Closure Verification Report

**Phase Goal:** Deliver a materially smaller ATT per-WAN DB footprint in production and close the last open milestone requirement  
**Verified:** 2026-04-14T13:42:00Z  
**Status:** verified

## Requirement Coverage

| Requirement | Status | Evidence |
| --- | --- | --- |
| STOR-06 | ✓ SATISFIED | [182-production-footprint-closeout.md](/home/kevin/projects/wanctl/.planning/phases/182-att-footprint-closure/182-production-footprint-closeout.md) shows both active per-WAN DBs materially smaller than the fixed `2026-04-13` baseline. [182-att-reduction-execution.md](/home/kevin/projects/wanctl/.planning/phases/182-att-footprint-closure/182-att-reduction-execution.md) records the ATT-only reduction run and the healthy post-run operator surfaces. |

## Verified Truths

1. ATT was not blocked by retention design anymore; it was blocked by an incomplete file-compaction outcome.
   Evidence:
   - [182-att-reduction-precheck.md](/home/kevin/projects/wanctl/.planning/phases/182-att-footprint-closure/182-att-reduction-precheck.md)

2. The existing ATT-only compaction helper path was sufficient.
   Evidence:
   - [182-att-reduction-execution.md](/home/kevin/projects/wanctl/.planning/phases/182-att-footprint-closure/182-att-reduction-execution.md)
   - no repo-side helper or storage code changes were required during execution

3. The remaining milestone blocker is closed in production terms.
   Evidence:
   - Spectrum remains materially smaller than baseline
   - ATT is now materially smaller than baseline by about `4.88 GB`
   - [182-production-footprint-closeout.md](/home/kevin/projects/wanctl/.planning/phases/182-att-footprint-closure/182-production-footprint-closeout.md)

4. Supported operator workflows remained usable after the ATT reduction run.
   Evidence:
   - `canary-check` passed for `spectrum`, `att`, and `steering`
   - `soak-monitor` stayed healthy
   - merged CLI history still returned both WANs after the ATT run

## Explicit Boundaries

- This verification does not reinterpret the shared `metrics.db` growth as part of `STOR-06`; the requirement is about the active per-WAN autorate DB footprint.
- This verification reuses the narrowed Phase 181 history-reader contract rather than broadening the HTTP role.
- This verification did not require any control-loop, timing, or threshold changes.

## Verification Basis

- `ssh -o BatchMode=yes kevin@10.10.110.223 'sudo -n stat -c "%n %s %y" /var/lib/wanctl/metrics-spectrum.db /var/lib/wanctl/metrics-spectrum.db-wal /var/lib/wanctl/metrics-att.db /var/lib/wanctl/metrics-att.db-wal /var/lib/wanctl/metrics.db /var/lib/wanctl/metrics.db-wal 2>/dev/null'`
- `./scripts/compact-metrics-dbs.sh --ssh kevin@10.10.110.223 --wan att`
- `./scripts/canary-check.sh --ssh kevin@10.10.110.223 --expect-version 1.35.0 --json`
- `./scripts/soak-monitor.sh --ssh kevin@10.10.110.223 --json`
- `ssh -o BatchMode=yes kevin@10.10.110.223 'tmp=$(mktemp); sudo -n env PYTHONPATH=/opt python3 -m wanctl.history --last 1m --metrics wanctl_rtt_ms --json > "$tmp"; python3 - <<\"PY\" "$tmp"\nimport sys, json\nwith open(sys.argv[1]) as f:\n    rows=json.load(f)\nprint(json.dumps({\"rows\": len(rows), \"wans\": sorted({row.get(\"wan_name\") for row in rows})}))\nPY\nrm -f "$tmp"'`
