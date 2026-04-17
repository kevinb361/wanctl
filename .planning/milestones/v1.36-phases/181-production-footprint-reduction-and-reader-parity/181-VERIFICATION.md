---
phase: 181-production-footprint-reduction-and-reader-parity
verified: 2026-04-14T12:26:25Z
status: gaps_found
score: 0/1 requirements verified
overrides_applied: 0
human_verification: []
deferred:
  - truth: "Dashboard history consumer still does not surface the narrowed CLI vs endpoint-local HTTP distinction"
    addressed_in: "follow-up work after v1.36"
    evidence: "The dashboard still reads a single autorate URL and does not render `metadata.source` from `/metrics/history`."
---

# Phase 181: Production Footprint Reduction And Reader Parity Verification Report

**Phase Goal:** Close the failed production outcome behind `STOR-06` and reconcile the remaining live reader-path drift
**Verified:** 2026-04-14T12:26:25Z
**Status:** gaps_found

## Requirement Coverage

| Requirement | Status | Evidence |
| --- | --- | --- |
| STOR-06 | ✗ UNSATISFIED | [181-production-footprint-closeout.md](/home/kevin/projects/wanctl/.planning/phases/181-production-footprint-reduction-and-reader-parity/181-production-footprint-closeout.md) shows Spectrum materially smaller versus baseline, but ATT remains effectively unchanged. [181-live-reader-parity-report.md](/home/kevin/projects/wanctl/.planning/phases/181-production-footprint-reduction-and-reader-parity/181-live-reader-parity-report.md) shows operator surfaces and reader-role behavior are restored, but the per-WAN footprint reduction claim is still incomplete. |

## Verified Truths

1. The startup/watchdog regression that blocked Plan 181-03 is fixed.
   Evidence:
   - production restart validation under the repo-default `WatchdogSec=30s`
   - canary and soak-monitor became usable again
   - [181-live-reader-parity-report.md](/home/kevin/projects/wanctl/.planning/phases/181-production-footprint-reduction-and-reader-parity/181-live-reader-parity-report.md)

2. The reader-role story is now explicit and proven on the live host.
   Evidence:
   - CLI returns both `att` and `spectrum`
   - Spectrum HTTP returns `metadata.source.mode=local_configured_db` with only `spectrum`
   - ATT HTTP returns `metadata.source.mode=local_configured_db` with only `att`
   - [181-reader-parity-decision.md](/home/kevin/projects/wanctl/.planning/phases/181-production-footprint-reduction-and-reader-parity/181-reader-parity-decision.md)
   - [181-live-reader-parity-report.md](/home/kevin/projects/wanctl/.planning/phases/181-production-footprint-reduction-and-reader-parity/181-live-reader-parity-report.md)

3. The explicit offline reduction path can materially shrink at least one live per-WAN DB without changing control logic.
   Evidence:
   - [181-footprint-reduction-design.md](/home/kevin/projects/wanctl/.planning/phases/181-production-footprint-reduction-and-reader-parity/181-footprint-reduction-design.md)
   - [181-production-footprint-closeout.md](/home/kevin/projects/wanctl/.planning/phases/181-production-footprint-reduction-and-reader-parity/181-production-footprint-closeout.md)

## Remaining Gap

The phase goal is still not fully achieved:

- Spectrum is materially smaller than the fixed `2026-04-13` baseline.
- ATT is not materially smaller than the fixed baseline.

Because `STOR-06` is framed against the active per-WAN DB footprint in production terms, the requirement remains unsatisfied.

## Explicit Boundaries

- This verification does **not** treat restored startup, `storage.status: ok`, or a mostly-passing canary as proof that the footprint reduction requirement is satisfied.
- This verification does **not** reopen the old HTTP parity ambiguity: the CLI-vs-HTTP split is now explicit and supported.
- This verification does treat the current Spectrum canary warning as non-blocking because the warning is runtime-only while top-level health, router reachability, storage, and version checks all pass.

## Tech Debt

- The dashboard history consumer still assumes a single autorate URL and does not surface the narrowed endpoint-local role or `metadata.source`.
- Spectrum currently carries a runtime warning on operator surfaces even though health, canary, and soak workflows remain usable.

## Verification Basis

- `ssh -o BatchMode=yes kevin@10.10.110.223 'sudo -n stat -c "%n %s %y" /var/lib/wanctl/metrics-spectrum.db /var/lib/wanctl/metrics-spectrum.db-wal /var/lib/wanctl/metrics-att.db /var/lib/wanctl/metrics-att.db-wal /var/lib/wanctl/metrics.db /var/lib/wanctl/metrics.db-wal 2>/dev/null'`
- `./scripts/soak-monitor.sh --ssh kevin@10.10.110.223 --json`
- `./scripts/canary-check.sh --ssh kevin@10.10.110.223 --expect-version 1.35.0 --json`
- `ssh -o BatchMode=yes kevin@10.10.110.223 'sudo -n env PYTHONPATH=/opt python3 -m wanctl.history --last 1h --metrics wanctl_rtt_ms --json'`
- endpoint-local `/metrics/history` checks on `10.10.110.223:9101` and `10.10.110.227:9101`
