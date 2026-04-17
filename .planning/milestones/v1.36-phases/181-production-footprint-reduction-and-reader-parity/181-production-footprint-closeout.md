# Phase 181 Production Footprint Closeout

**Captured:** 2026-04-14T12:26:25Z  
**Host:** `kevin@10.10.110.223`  
**Requirement:** `STOR-06`

## Objective

Compare the current live per-WAN DB footprint to the fixed `2026-04-13` baseline and state plainly whether the phase achieved a materially smaller production footprint without breaking the operator surfaces.

## Evidence Sources

```bash
ssh -o BatchMode=yes kevin@10.10.110.223 'sudo -n stat -c "%n %s %y" /var/lib/wanctl/metrics-spectrum.db /var/lib/wanctl/metrics-spectrum.db-wal /var/lib/wanctl/metrics-att.db /var/lib/wanctl/metrics-att.db-wal /var/lib/wanctl/metrics.db /var/lib/wanctl/metrics.db-wal 2>/dev/null'
./scripts/soak-monitor.sh --ssh kevin@10.10.110.223 --json
./scripts/canary-check.sh --ssh kevin@10.10.110.223 --expect-version 1.35.0 --json
```

## Baseline vs Current Live Sizes

| File | 2026-04-13 baseline | 2026-04-14 live size | Delta | Assessment |
|------|---------------------|----------------------|-------|------------|
| `metrics-spectrum.db` | `5,441,712,128` bytes | `5,076,008,960` bytes | `-365,703,168` bytes | materially smaller |
| `metrics-spectrum.db-wal` | `4,268,352` bytes | `6,868,072` bytes | `+2,599,720` bytes | larger WAL, but DB body still materially smaller |
| `metrics-att.db` | `5,082,914,816` bytes | `5,082,898,432` bytes | `-16,384` bytes | effectively unchanged |
| `metrics-att.db-wal` | `4,243,632` bytes | `6,954,592` bytes | `+2,710,960` bytes | larger WAL, not evidence of footprint reduction |
| `metrics.db` | `750,997,504` bytes | `1,116,307,456` bytes | `+365,309,952` bytes | shared steering DB grew and remains a separate inventory item |
| `metrics.db-wal` | `4,523,792` bytes | `4,783,352` bytes | `+259,560` bytes | slightly larger shared WAL |

## Operator-Visible Storage Status

Latest supported operator surfaces reported:

- `spectrum`
  - `storage.status: ok`
  - `runtime.status: warning`
  - `db_bytes: 5,076,008,960`
  - `wal_bytes: 63,406,832`
- `att`
  - `storage.status: ok`
  - `runtime.status: ok`
  - `db_bytes: 5,082,898,432`
  - `wal_bytes: 33,409,112`
- `all-claimed-services`
  - `errors_1h: 46`

## Production Outcome

Phase 181 did recover the restart path and did produce a real footprint improvement for Spectrum:

- Spectrum is down by about `366 MB` versus the fixed baseline.
- ATT is still effectively unchanged.

That means the milestone-wide `STOR-06` claim is **not** yet honestly satisfied:

- the requirement is phrased against the active per-WAN DB footprint in production terms
- only one of the two active per-WAN DBs is materially smaller
- the operator surfaces are working again, but the reduction outcome is mixed rather than complete

## Operational Interpretation Boundary

- This closeout does **not** treat `storage.status: ok` as proof that the reduction succeeded.
- It does **not** treat the larger shared `metrics.db` as evidence for or against the per-WAN autorate reduction claim.
- It does confirm that the production startup/watchdog failure from earlier in Phase 181 is resolved and that health/canary/soak surfaces are usable again.

## Requirement Decision

`STOR-06` remains **unsatisfied** after Phase 181 closeout.

Reason:
- startup and reader-parity regressions were fixed
- operator workflows were restored
- but ATT did not materially shrink versus baseline, so the per-WAN production footprint reduction claim is still incomplete
