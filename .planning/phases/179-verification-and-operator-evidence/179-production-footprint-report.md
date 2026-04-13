# Phase 179 Production Footprint Report

**Captured:** 2026-04-13T23:31:23Z
**Host:** `kevin@10.10.110.223`
**Scope:** read-only production file inventory and operator-visible storage evidence after Phase 178

## Objective

Compare the live DB footprint to the fixed 2026-04-13 baseline from Phase 177 so Phase 179 can state whether the deployed footprint actually dropped.

## Evidence Source

```bash
ssh -o BatchMode=yes kevin@10.10.110.223 'sudo -n stat -c "%n %s %y" /var/lib/wanctl/metrics-spectrum.db /var/lib/wanctl/metrics-spectrum.db-wal /var/lib/wanctl/metrics-att.db /var/lib/wanctl/metrics-att.db-wal /var/lib/wanctl/metrics.db /var/lib/wanctl/metrics.db-wal 2>/dev/null'
```

## 2026-04-13 Baseline vs Current Live Sizes

| File | 2026-04-13 baseline | Current live size | Delta | Assessment |
|------|---------------------|-------------------|-------|------------|
| `metrics-spectrum.db` | `5,441,712,128` bytes (`~5.44 GB`) | `5,441,699,840` bytes (`~5.44 GB`) | `-12,288` bytes | unchanged, not materially smaller |
| `metrics-spectrum.db-wal` | `4,268,352` bytes (`~4.27 MB`) | `4,313,672` bytes (`~4.31 MB`) | `+45,320` bytes | slightly larger WAL, not meaningful evidence of reduction |
| `metrics-att.db` | `5,082,914,816` bytes (`~5.08 GB`) | `5,082,902,528` bytes (`~5.08 GB`) | `-12,288` bytes | unchanged, not materially smaller |
| `metrics-att.db-wal` | `4,243,632` bytes (`~4.24 MB`) | `4,288,952` bytes (`~4.29 MB`) | `+45,320` bytes | slightly larger WAL, not meaningful evidence of reduction |
| `metrics.db` | `750,997,504` bytes (`~751 MB`) | `774,041,600` bytes (`~774 MB`) | `+23,044,096` bytes | shared steering DB grew and must be inventoried separately |
| `metrics.db-wal` | `4,523,792` bytes (`~4.52 MB`) | `4,523,792` bytes (`~4.52 MB`) | `0` bytes | unchanged shared WAL |

## Live File Inventory

| File | Current live size | Modified time | Role |
|------|-------------------|---------------|------|
| `/var/lib/wanctl/metrics-spectrum.db` | `5,441,699,840` bytes | `2026-04-13 18:31:22.166006708 -0500` | Spectrum autorate DB |
| `/var/lib/wanctl/metrics-spectrum.db-wal` | `4,313,672` bytes | `2026-04-13 18:31:23.166013723 -0500` | Spectrum WAL |
| `/var/lib/wanctl/metrics-att.db` | `5,082,902,528` bytes | `2026-04-13 18:31:23.002012573 -0500` | ATT autorate DB |
| `/var/lib/wanctl/metrics-att.db-wal` | `4,288,952` bytes | `2026-04-13 18:31:23.194013920 -0500` | ATT WAL |
| `/var/lib/wanctl/metrics.db` | `774,041,600` bytes | `2026-04-13 18:31:08.429910334 -0500` | shared steering DB |
| `/var/lib/wanctl/metrics.db-wal` | `4,523,792` bytes | `2026-04-13 18:31:22.982012433 -0500` | shared steering WAL |

## Comparison Outcome

- The fixed 2026-04-13 baseline for the active per-WAN DBs was already about `5.44 GB` for Spectrum and `5.08 GB` for ATT.
- The current live per-WAN DBs differ from that baseline by only `12,288` bytes each, which is effectively no change in operator terms.
- Phase 179 therefore cannot claim that the deployed per-WAN footprint is materially smaller after Phase 178. The live footprint is unchanged for the active autorate DBs.
- `metrics.db` remains present as the separate shared steering DB and should not be treated as evidence about the per-WAN autorate reduction claim.

## Operator-Visible Storage Status

Evidence source:

```bash
./scripts/soak-monitor.sh --json
```

### Current `storage.status` from supported operator surfaces

| Surface | WAN / scope | `storage.status` | Storage-visible fields |
|---------|-------------|------------------|------------------------|
| `soak-monitor --json` -> `health.wans[].storage` | `spectrum` | `ok` | `db_bytes=5,441,699,840`, `wal_bytes=4,313,672`, `total_bytes=5,447,586,376`, `pending_writes=1` |
| `soak-monitor --json` -> top-level `storage` | `spectrum` | `ok` | `db_bytes=5,441,699,840`, `wal_bytes=4,313,672`, `total_bytes=5,447,586,376`, `pending_writes=1` |
| `soak-monitor --json` -> `health.wans[].storage` | `att` | `ok` | `db_bytes=5,082,902,528`, `wal_bytes=4,288,952`, `total_bytes=5,088,534,968`, `pending_writes=1` |
| `soak-monitor --json` -> top-level `storage` | `att` | `ok` | `db_bytes=5,082,902,528`, `wal_bytes=4,288,952`, `total_bytes=5,088,534,968`, `pending_writes=1` |
| `soak-monitor --json` -> `service_group` summary | `all-claimed-services` | not applicable | `units=[wanctl@spectrum.service, wanctl@att.service, steering.service]`, `errors_1h=0` |

### Interpretation boundary

- The supported operator helper currently reports `storage.status: ok` for both autorate WANs.
- That means the storage path is not presently reporting a failure condition through the supported surface.
- It does not prove the footprint reduction succeeded. The same helper reports DB byte counts that match the `stat` evidence above, and those values remain effectively unchanged from the 2026-04-13 baseline for the per-WAN DBs.
- The correct operator conclusion is therefore: storage is currently non-failing on the supported surface, but the per-WAN footprint has not materially decreased relative to the fixed baseline.
- The evidence in this report is a point-in-time snapshot from a live system; the shared steering DB can continue to advance between reads, so the report treats it as an inventory item rather than proof of per-WAN reduction.
