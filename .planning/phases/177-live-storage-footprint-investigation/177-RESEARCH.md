# Phase 177: Live Storage Footprint Investigation - Research

**Researched:** 2026-04-13
**Domain:** Production SQLite metrics footprint, retention/downsampling behavior, legacy DB-path closure
**Confidence:** HIGH

## Summary

Phase 177 is an evidence-first investigation phase. Production is healthy and the storage status is still `ok`, but the active per-WAN metrics DBs are larger than expected and a legacy `metrics.db` still exists on the host. The safest path is to treat this as a storage-forensics phase, not a controller-change phase.

The repo and live host already give enough direction to plan conservatively:

1. Do not change queue-control logic, thresholds, timing, or safety behavior.
2. Confirm the authoritative runtime DB paths from code, config, and live production state.
3. Measure which parts of the active DBs are consuming space before proposing retention changes.
4. Close the legacy `metrics.db` ambiguity with evidence, not assumption.
5. Produce Phase 178 inputs that are specific enough to choose between cleanup, retention tightening, or schema/write-volume reduction.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| STOR-04 | Explain current 5+ GB per-WAN footprint | need production evidence for active DB files, retained time window, dominant tables/indexes, and retention shape |
</phase_requirements>

## Verified Current State

### 1. Configured per-WAN DB paths are already explicit

Repo configs point the active autorate services at per-WAN files:

- `configs/spectrum.yaml` -> `/var/lib/wanctl/metrics-spectrum.db`
- `configs/att.yaml` -> `/var/lib/wanctl/metrics-att.db`

This means the large live DBs are not an accidental fallback to the old shared default.

### 2. Legacy defaults still exist in code

The repo still carries `/var/lib/wanctl/metrics.db` as a default path in shared storage/config code:

- `src/wanctl/config_base.py`
- `src/wanctl/storage/writer.py`

Also, `src/wanctl/storage/db_utils.py` prefers `metrics-*.db` files when present and falls back to legacy `metrics.db` only when no per-WAN files exist.

**Implication:** the runtime should prefer the per-WAN DBs, but the old path is still part of the code surface and needs explicit closure.

### 3. Live production storage shows three distinct classes of DB files

From the production host:

- active per-WAN DBs:
  - `/var/lib/wanctl/metrics-spectrum.db` ≈ `5.44 GB`
  - `/var/lib/wanctl/metrics-att.db` ≈ `5.08 GB`
- legacy residue:
  - `/var/lib/wanctl/metrics.db` ≈ `739 MB`
- likely stale zero-byte leftovers:
  - `/var/lib/wanctl/spectrum_metrics.db`
  - `/var/lib/wanctl/att_metrics.db`

**Implication:** Phase 177 must distinguish active, legacy-but-unused, and stale-residue files.

### 4. WAL growth is not the main problem

Live WAL files are only about `4.3 MB` per active DB, while the DB bodies are multi-GB.

**Implication:** this is not a checkpoint/WAL runaway issue. The footprint is mostly live DB pages, not transient WAL accumulation.

### 5. Retention/downsampling appears active, not totally broken

Live checks showed:

- oldest retained metric timestamp around `2026-04-12T15:30:00Z`
- newest retained metric timestamp around `2026-04-13T22:14:10Z`
- oldest sampled granularity already at `5m`
- newest sampled granularity at `raw`

That indicates:

- downsampling is happening
- retention is not completely stuck
- the remaining size is likely due to retained metric volume and/or schema/index density

### 6. DB free-page rates are very low

Production `PRAGMA freelist_count` checks showed only about `0.65%` to `0.75%` free pages in the active DBs.

**Implication:** these files are not large mainly because of reclaimable slack after a missed vacuum. Most of the on-disk size is live allocated content.

## Standard Stack

| Surface | Role | Current Status | Phase 177 Need |
|---------|------|----------------|----------------|
| `configs/spectrum.yaml`, `configs/att.yaml` | runtime DB-path authority | points at per-WAN DBs | verify production matches config and close any divergence |
| `src/wanctl/config_base.py` | shared storage defaults | still carries legacy `metrics.db` default | document whether this default is still reachable in production |
| `src/wanctl/storage/db_utils.py` | DB discovery logic | prefers `metrics-*.db` when present | verify operator/tooling path matches live files |
| production `/var/lib/wanctl/*.db*` | source of truth for actual footprint | active DBs large, legacy/stale files present | inventory and classify each file |
| health endpoints / `soak-monitor.sh` | operator storage signal | report `storage.status=ok` and file sizes | tie operator-visible status back to actual DB footprint |

## Architecture Patterns

### Pattern 1: Evidence before optimization

Storage reduction should not be guessed from file size alone. The next phase needs a measured split:

- active DBs vs stale residue
- table/index footprint
- retention granularity distribution
- legacy path still used vs merely present

### Pattern 2: Close ambiguous runtime paths explicitly

The repo currently has both:

- code/config defaults mentioning legacy `metrics.db`
- live per-WAN DBs as actual production stores

Phase 177 should resolve that ambiguity so Phase 178 can safely remove, archive, or document the old path.

### Pattern 3: Keep investigation tooling read-only

Because this phase is production-facing, any helper introduced during execution should:

- use read-only sqlite access where possible
- avoid modifying DB state
- avoid service restarts
- produce evidence artifacts that can be cited by later verification

## Recommended Plan Split

### Plan 01: Runtime path and file-role closure

Goal: prove which DB files are authoritative, which are stale, and how code/config/tooling discover them.

Likely files:

- phase evidence docs under `.planning/phases/177-live-storage-footprint-investigation/`
- repo docs or helper notes only if needed

### Plan 02: Live DB composition and retention-shape evidence

Goal: capture table/index/granularity evidence from the active per-WAN DBs and quantify what is consuming space.

Likely outputs:

- evidence files in the phase directory
- optional read-only helper command/script if the manual command path is too brittle

### Plan 03: Findings synthesis and operator decision handoff

Goal: document the measured explanation, recommend the smallest safe Phase 178 change, and give operators a repeatable re-check path.

Likely outputs:

- evidence summary doc
- phase summary
- explicit recommendation for retention tightening, legacy cleanup, or both

## Common Pitfalls

### Pitfall 1: Treating `storage.status=ok` as proof the footprint is acceptable

`ok` only means current thresholds are not tripped. It does not mean the DB size is well-bounded.

### Pitfall 2: Assuming `metrics.db` is still active because it exists

The file may be pure residue. Phase 177 must prove activity or inactivity from code/config/runtime evidence.

### Pitfall 3: Proposing retention changes before measuring table/index composition

The DBs may be large because of:

- raw metric volume
- index overhead
- multiple retained granularities
- non-metrics tables

Different causes imply different fixes.

## Validation Architecture

Phase 177 is primarily a documentation/evidence phase, so validation should be lightweight and evidence-oriented:

- repo-side `rg` checks for active DB-path and retention logic
- production read-only `sudo sqlite3` and file-inventory commands
- evidence files written under the phase directory
- no broad pytest suite required unless a helper script is added

Recommended quick checks during execution:

- `rg -n 'db_path|retention|metrics\\.db|metrics-' configs src/wanctl`
- `ssh ... 'sudo -n ls -lh /var/lib/wanctl/*metrics*.db* /var/lib/wanctl/metrics.db*'`
- `ssh ... 'sudo -n sqlite3 /var/lib/wanctl/metrics-spectrum.db \".tables\"'`
- `ssh ... 'sudo -n sqlite3 /var/lib/wanctl/metrics-att.db \".tables\"'`

