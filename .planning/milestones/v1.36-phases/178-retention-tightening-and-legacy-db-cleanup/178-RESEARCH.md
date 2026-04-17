# Phase 178: Retention Tightening And Legacy DB Cleanup - Research

**Researched:** 2026-04-13
**Domain:** Storage topology closure, retention tightening, operator-surface safety
**Confidence:** HIGH

## Summary

Phase 178 should make the storage layout explicit first, then reduce the active per-WAN DB footprint with the smallest safe retention change. Phase 177 already proved the large per-WAN DBs are mostly live retained content, not WAL runaway or reclaimable slack, and also proved that the legacy shared `metrics.db` is still active.

The repo shows three important constraints:

1. Autorate already uses explicit per-WAN DB paths from `configs/spectrum.yaml` and `configs/att.yaml`.
2. Steering still inherits the legacy default storage path because `configs/steering.yaml` has no explicit `storage.db_path`.
3. Some read paths still assume `DEFAULT_DB_PATH`, especially `src/wanctl/health_check.py`, while CLI/history discovery already prefers per-WAN files.

So Phase 178 should be framed as a conservative topology-and-retention fix:

1. Make the legacy `metrics.db` role explicit instead of inferred.
2. Tighten per-WAN retention in a way that does not break tuning lookback or operator history surfaces.
3. Keep health, canary, soak-monitor, operator-summary, and history workflows aligned with the chosen layout.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| STOR-05 | Close the runtime role of legacy `/var/lib/wanctl/metrics.db` | steering config, writer defaults, and production evidence show the path is still reachable and active |
| STOR-06 | Materially reduce active per-WAN DB footprint from the 2026-04-13 baseline | per-WAN DBs are 5+ GB and mostly live retained content, so retention tightening is the lowest-risk lever |
| STOR-07 | Keep retention/downsampling/maintenance bounded and production-safe | existing retention and tuning compatibility code already provides guardrails that Phase 178 should preserve |
</phase_requirements>

## Verified Current State

### 1. Steering still defaults to the shared legacy DB path

`src/wanctl/steering/daemon.py` calls `get_storage_config(config.data)` and instantiates `MetricsWriter(Path(db_path))`, but `configs/steering.yaml` does not set `storage.db_path`.

`src/wanctl/config_base.py` still defaults `storage.db_path` to `/var/lib/wanctl/metrics.db`.

**Implication:** production activity in `metrics.db` is expected until steering is either made explicit on that file or moved elsewhere intentionally.

### 2. Autorate retention is currently looser than the documented defaults

The active WAN configs set:

- `raw_age_seconds: 86400`
- `aggregate_1m_age_seconds: 86400`
- `aggregate_5m_age_seconds: 604800`

But docs and code defaults treat shorter raw retention as normal:

- `src/wanctl/storage/downsampler.py` default raw threshold: `900` seconds
- `docs/CONFIG_SCHEMA.md` raw retention default: `3600` seconds

**Implication:** reducing raw retention is likely the safest first footprint cut because it does not shorten the 24h 1-minute aggregate window the tuner depends on.

### 3. The tuning safety guard is already present

`src/wanctl/config_validation_utils.py` validates retention against tuning lookback, specifically guarding `aggregate_1m_age_seconds`.

**Implication:** Phase 178 should preserve the 24h 1-minute aggregate window and avoid changes that would starve tuning history.

### 4. Some reader surfaces are already multi-DB aware, others are not

Good:

- `src/wanctl/history.py`
- `src/wanctl/storage/db_utils.py`

Still legacy-default-bound:

- `src/wanctl/health_check.py` `/metrics/history`
- docs and helper references that still speak about a single `metrics.db`

**Implication:** topology closure is not just config. Read surfaces and operator docs must match the chosen authoritative DB layout.

### 5. Production-safe cleanup must avoid destructive assumptions

Phase 177 evidence showed:

- `metrics.db` is active/shared, not dead residue
- `spectrum_metrics.db` and `att_metrics.db` look like stale zero-byte leftovers

**Implication:** only the stale zero-byte artifacts are candidates for immediate removal. The shared legacy DB cannot be deleted until its role is made explicit and verified.

## Standard Stack

| Surface | Role | Current Status | Phase 178 Need |
|---------|------|----------------|----------------|
| `configs/spectrum.yaml`, `configs/att.yaml` | authoritative autorate DB/retention config | explicit per-WAN DBs, 24h raw retention | tighten retention conservatively |
| `configs/steering.yaml` | steering storage intent | no explicit storage section | make shared/legacy path explicit or deliberately retire it |
| `src/wanctl/config_base.py` | storage defaults | still defaults to `metrics.db` | keep defaults coherent with the chosen topology |
| `src/wanctl/health_check.py` | `/metrics/history` reader path | still hard-wired to `DEFAULT_DB_PATH` | align history reads with active DB topology |
| `src/wanctl/storage/db_utils.py` and `src/wanctl/history.py` | multi-DB read path | already prefers per-WAN DBs | preserve or extend as authoritative read behavior |
| `scripts/soak-monitor.sh`, canary/operator tooling | operator storage verification | already reports storage status, not DB-role intent | verify tooling still works after topology/retention changes |

## Architecture Patterns

### Pattern 1: Explicit storage topology beats implicit defaults

The next change should remove guesswork around `metrics.db`. If the shared DB remains active for steering, Phase 178 should say so explicitly in config/docs/code paths rather than leaving it as an inherited default.

### Pattern 2: Reduce raw data first, preserve aggregate lookback

Because the tuner relies on 24h historical data and validation already guards `aggregate_1m_age_seconds`, the safest reduction path is to cut raw retention while keeping 1-minute aggregates at 24h and 5-minute aggregates at their current safe bound unless evidence later demands more.

### Pattern 3: Reader contracts matter as much as writer paths

A storage-layout change is incomplete if health/history/operator paths still read from the wrong DB or silently ignore the new authoritative set.

## Recommended Plan Split

### Plan 01: Legacy/shared DB role closure

Goal: make the runtime role of `metrics.db` explicit in steering config, code defaults, and authoritative docs while cleaning up only the clearly stale zero-byte artifacts.

### Plan 02: Conservative retention tightening on active per-WAN DBs

Goal: materially reduce the autorate DB footprint by tightening the active per-WAN retention profile without changing controller behavior or breaking tuning safety.

### Plan 03: Reader/operator path alignment and regression coverage

Goal: ensure `/metrics/history`, `wanctl-history`, canary, soak-monitor, and docs all remain coherent with the updated storage topology and reduced footprint.

## Common Pitfalls

### Pitfall 1: Deleting `metrics.db` just because per-WAN DBs exist

Phase 177 already disproved that assumption. The shared DB is still active.

### Pitfall 2: Tightening `aggregate_1m_age_seconds` below the tuning lookback

That would reduce storage, but it would also undermine the tuning contract and conflict with existing validation logic.

### Pitfall 3: Treating history/query surfaces as out of scope

`/metrics/history` currently reads from `DEFAULT_DB_PATH`, so Phase 178 must account for it explicitly.

## Validation Architecture

Phase 178 will change code/config/docs, so validation should combine focused tests with repo checks:

- targeted pytest for health/history/storage config behavior
- `ruff` or syntax checks only if touched files warrant it
- repo grep checks for legacy-path references
- production-safe command references for post-change operator verification

Recommended quick checks during execution:

- `.venv/bin/pytest -o addopts='' tests/test_health_check.py tests/test_history_multi_db.py tests/test_config_base.py -q`
- `rg -n 'metrics\\.db|metrics-spectrum\\.db|metrics-att\\.db|storage\\.retention' configs src/wanctl docs scripts`
- `git diff --check`
