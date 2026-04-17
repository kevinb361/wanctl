# Phase 181: Production Footprint Reduction And Reader Parity - Research

**Researched:** 2026-04-14
**Domain:** Production storage-footprint reduction, SQLite retention behavior, history-reader parity
**Confidence:** HIGH

## Summary

Phase 181 is the remaining gap-closure phase for milestone `v1.36`. The audit result is now narrow:

1. `STOR-06` is still open because the shipped Phase 178 retention change did not produce a materially smaller live per-WAN DB footprint.
2. Phase 179 also captured a live parity gap between the module-based CLI reader and the deployed `/metrics/history` HTTP endpoint.

The important constraint is operational safety. This phase must not change congestion logic, control timing, or safety thresholds. It should focus on the storage/reader path only.

## What Earlier Phases Already Proved

### 1. The large per-WAN DBs are mostly live retained content

Phase 177 showed the 5+ GB per-WAN DBs were not primarily WAL growth or reclaimable free-page slack. That means a meaningful size reduction likely requires one or both of:

- more aggressive retention/downsampling than the current 1h raw / 24h 1m / 7d 5m profile
- an explicit compaction step on production after retention cleanup has taken effect

### 2. Phase 178 changed shipped retention safely, but that alone did not shrink production files

Phase 178 tightened raw retention conservatively and aligned reader topology in repo-side code. Phase 179 then showed the live DB files were effectively unchanged from the fixed 2026-04-13 baseline. The likely implication is that:

- retention cleanup may not have reclaimed the multi-GB file footprint in place
- historical aggregates and/or file layout still dominate size
- production needs a deliberate reduction path, not just config changes

### 3. The live operator proof path is asymmetrical today

Phase 179 proved:

- the deployed CLI module path can read both WANs
- the live HTTP endpoint preserved the envelope contract but did not prove merged cross-WAN history
- operators currently need the CLI module path plus direct DB inventory as the authoritative cross-WAN proof surface

Phase 181 should either eliminate that drift or narrow/document it explicitly without pretending the HTTP surface already proves parity.

## Phase Requirement

| ID | Description | Research Support |
|----|-------------|------------------|
| STOR-06 | Active per-WAN metrics DB footprint is materially reduced from the 2026-04-13 baseline without breaking health, canary, soak-monitor, operator-summary, or history workflows | The remaining work is a production-safe footprint reduction path plus verification that the supported reader surfaces remain internally consistent |

## Recommended Plan Split

### Plan 01: Implement the smallest production-safe footprint reduction that can actually shrink files

Goal: identify and ship a concrete reduction path that affects the live DB file footprint, not just repo-side retention settings. This likely means a bounded retention/compaction step plus operator-safe invocation.

### Plan 02: Close or narrow live reader parity drift

Goal: make the supported history-reader story internally consistent. Prefer a targeted fix that preserves the existing HTTP envelope contract and the current CLI discovery model.

### Plan 03: Verify the live result in production

Goal: capture post-change production evidence against the fixed `2026-04-13` baseline and prove that health/operator workflows still work after the reduction step.

## Common Pitfalls

### Pitfall 1: Treating `storage.status: ok` as proof of reduction

Earlier evidence already showed that storage can be healthy while the DB footprint remains too large for the milestone claim.

### Pitfall 2: Tweaking retention defaults without a compaction story

The live DBs remained effectively unchanged after the last retention cut. Phase 181 should assume that a real file-size reduction may require an explicit production compaction/rebuild path once stale data has been removed.

### Pitfall 3: Changing reader contracts casually

The HTTP endpoint already has an operator-facing `{data, metadata}` contract. Any parity fix should preserve that contract unless a narrower documented role is explicitly chosen.

### Pitfall 4: Pulling control-loop behavior into a storage milestone

This phase must stay out of controller thresholds, timing, and decision logic.

## Validation Architecture

Phase 181 needs both repo-side and live production validation:

- focused tests for storage maintenance and history-reader behavior
- syntax checks for any touched operator scripts
- read-only live DB size evidence against the fixed baseline
- supported operator-surface checks (`soak-monitor`, canary, history CLI/HTTP)

The phase should only claim success if production evidence shows a materially smaller per-WAN footprint and the history-reader proof path is not internally contradictory.
