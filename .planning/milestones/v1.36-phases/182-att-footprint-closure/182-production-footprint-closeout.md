# Phase 182 Production Footprint Closeout

**Captured:** 2026-04-14T13:40:00Z  
**Host:** `kevin@10.10.110.223`  
**Requirement:** `STOR-06`

## Objective

Compare the current live per-WAN DB footprint to the fixed `2026-04-13` baseline after the ATT-only reduction run and state plainly whether `STOR-06` is now satisfied.

## Baseline vs Current Live Sizes

| File | 2026-04-13 baseline | 2026-04-14 final live size | Delta | Assessment |
|------|---------------------|----------------------------|-------|------------|
| `metrics-spectrum.db` | `5,441,712,128` bytes | `5,076,008,960` bytes | `-365,703,168` bytes | materially smaller |
| `metrics-spectrum.db-wal` | `4,268,352` bytes | `67,108,864` bytes | `+62,840,512` bytes | larger WAL, but DB body still materially smaller |
| `metrics-att.db` | `5,082,914,816` bytes | `201,723,904` bytes | `-4,881,190,912` bytes | materially smaller |
| `metrics-att.db-wal` | `4,243,632` bytes | `5,401,352` bytes | `+1,157,720` bytes | slightly larger WAL, but DB body is now materially smaller |
| `metrics.db` | `750,997,504` bytes | `1,145,167,872` bytes | `+394,170,368` bytes | shared steering DB remains a separate inventory item |
| `metrics.db-wal` | `4,523,792` bytes | `4,783,352` bytes | `+259,560` bytes | slightly larger shared WAL |

## Operator-Visible Storage Status

Latest supported operator surfaces reported:

- `spectrum`
  - `storage.status: ok`
  - `runtime.status: ok`
  - `db_bytes: 5,076,008,960`
  - `wal_bytes: 67,108,864`
- `att`
  - `storage.status: ok`
  - `runtime.status: ok`
  - `db_bytes: 201,723,904`
  - `wal_bytes: 5,401,352`
- host disk free: `19,281,530,880 / 30,878,322,688` bytes (`62.4% free`)

## History And Operator Proof Path

Fresh Phase 182 checks confirmed:

- merged CLI history still works after the ATT reduction run and returns both `att` and `spectrum`
- canary passed for `spectrum`, `att`, and `steering`
- soak-monitor stayed healthy for both WANs

Phase 182 did not modify the history-reader implementation. The explicit Phase 181 reader-role contract remains the supported interpretation:

- CLI is the authoritative merged cross-WAN proof path
- `/metrics/history` remains the endpoint-local HTTP history surface

## Requirement Decision

`STOR-06` is now **satisfied**.

Reason:

- Spectrum remains materially smaller than baseline
- ATT is now materially smaller than baseline by about `4.88 GB`
- health, canary, soak-monitor, operator-summary, and the supported merged CLI history proof path remained usable after the ATT-only reduction run

## Boundary

- This closeout does not treat the larger shared `metrics.db` as evidence against the per-WAN autorate footprint claim.
- This closeout does not reopen the earlier CLI-vs-endpoint-local HTTP distinction; that operator story was already narrowed explicitly in Phase 181 and Phase 182 did not change it.

