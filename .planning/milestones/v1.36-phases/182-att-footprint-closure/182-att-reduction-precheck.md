# Phase 182 ATT Reduction Precheck

**Captured:** 2026-04-14T13:28:00Z  
**Host:** `kevin@10.10.110.223`  
**Requirement:** `STOR-06`

## Objective

Explain why ATT remained effectively unchanged after Phase 181 and capture the exact ATT-only operator procedure to finish the remaining production footprint reduction work.

## Fixed Baseline

From the `2026-04-13` baseline used throughout v1.36:

- `metrics-att.db`: `5,082,914,816` bytes
- `metrics-att.db-wal`: `4,243,632` bytes

Current pre-run live values:

- `metrics-att.db`: `5,082,877,952` bytes
- `metrics-att.db-wal`: `4,334,272` bytes

Delta before the Phase 182 ATT run:

- DB body: `-36,864` bytes
- WAL: `+90,640` bytes

Operationally, ATT is still unchanged relative to the fixed baseline.

## Key Production Evidence

### 1. ATT is mostly reclaimable free pages already

Read-only SQLite inspection on the live ATT DB:

- `page_size`: `4096`
- `page_count`: `1,240,937`
- `freelist_count`: `1,188,205`

That means about `4.86 GB` of the `5.08 GB` ATT DB file is already free-list space, not active retained content. This is the decisive signal for Phase 182.

### 2. ATT does not look like a retention-policy problem anymore

Current ATT metric distribution:

- `raw`: `1,427,392` rows
- `1m`: `286` rows
- `5m`: `1,558` rows

The 5m/1h aggregate population is small. The remaining problem is file compaction, not another retention-policy change.

### 3. Spectrum and ATT diverged mainly on compaction outcome

Spectrum is already materially smaller than baseline, while ATT stayed flat. Given the ATT free-list size above, the most likely explanation is simple:

- the ATT file went through cleanup but did not complete a successful offline `VACUUM` rewrite during Phase 181
- or the ATT run was interrupted before the shrink step finished

No evidence here suggests a need to change controller logic, retention semantics, or the history-reader contract.

## ATT-Only Procedure

Use the existing explicit helper. No repo-side helper change is required for the ATT run itself.

```bash
./scripts/compact-metrics-dbs.sh --ssh kevin@10.10.110.223 --wan att
./scripts/canary-check.sh --ssh kevin@10.10.110.223 --expect-version 1.35.0 --json
./scripts/soak-monitor.sh --ssh kevin@10.10.110.223 --json
```

If the helper reports a materially smaller ATT DB and the operator surfaces remain healthy, Phase 182 can proceed directly to final closeout.

## Evidence To Capture

Before the ATT run:

- `stat` for `metrics-att.db` and `metrics-att.db-wal`
- ATT free-list and page counts
- canary and soak status

After the ATT run:

- fresh `stat` for Spectrum and ATT DB/WAL files
- canary result for Spectrum, ATT, and steering
- soak-monitor output
- merged CLI history proof command

## Decision

Phase 182 should treat this as an ATT-only compaction completion problem, not a new product or storage-policy design problem.
