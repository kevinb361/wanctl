# Roadmap: wanctl v1.36 Storage Retention And DB Footprint

## Overview

Production storage is still healthy, but the active per-WAN metrics databases remain larger than expected and the legacy `metrics.db` file still exists alongside them. This milestone explains the live footprint, removes legacy DB ambiguity, and reduces retained metrics size without changing the controller’s decision logic or operator-facing contracts.

## Phases

- [x] **Phase 177: Live Storage Footprint Investigation** - Measure active DB composition, retention shape, and legacy DB activity on production (completed 2026-04-13)
- [x] **Phase 178: Retention Tightening And Legacy DB Cleanup** - Apply the smallest safe storage-footprint reduction that closes the live findings (completed 2026-04-13)
- [x] **Phase 179: Verification And Operator Evidence** - Prove the new storage footprint holds in production and document the operator verification path (completed 2026-04-13)

## Phase Details

### Phase 177: Live Storage Footprint Investigation
**Goal**: Explain what is consuming space in production and which DB files are actually part of the runtime path
**Depends on**: Phase 176
**Requirements**: STOR-04
**Success Criteria** (what must be TRUE):
  1. Active production DB files are identified and distinguished from stale or legacy residue
  2. Retention/downsampling behavior is characterized well enough to explain the current retained history shape
  3. The dominant contributors to the live DB footprint are documented with production evidence
**Plans:** 3/3 plans complete
Plans:
- [x] 177-01-PLAN.md -- Runtime DB-path closure and production file-role inventory
- [x] 177-02-PLAN.md -- Live DB composition and retained-history evidence capture
- [x] 177-03-PLAN.md -- Findings synthesis, operator re-check path, and Phase 178 recommendation

### Phase 178: Retention Tightening And Legacy DB Cleanup
**Goal**: Reduce the active metrics footprint safely and close out any unused legacy DB path
**Depends on**: Phase 177
**Requirements**: STOR-05, STOR-06, STOR-07
**Success Criteria** (what must be TRUE):
  1. Legacy `metrics.db` ambiguity is removed by code/config/docs and live runtime behavior
  2. Active per-WAN DB files are materially smaller than the 2026-04-13 baseline after the chosen cleanup/retention change
  3. Health, canary, soak-monitor, operator-summary, and history-query paths still work with the updated storage layout
**Plans:** 3/3 plans complete
Plans:
- [x] 178-01-PLAN.md -- Make the shared `metrics.db` role explicit and close stale zero-byte file ambiguity
- [x] 178-02-PLAN.md -- Tighten per-WAN retention conservatively while preserving tuning-safe history
- [x] 178-03-PLAN.md -- Align `/metrics/history` and operator verification paths with the updated storage layout

### Phase 179: Verification And Operator Evidence
**Goal**: Verify in production that the new storage footprint holds and that operators can re-check it without guesswork
**Depends on**: Phase 178
**Requirements**: OPER-04
**Success Criteria** (what must be TRUE):
  1. Production evidence shows which DBs are active, their current sizes, and their storage status after the footprint change
  2. Docs/scripts describe the authoritative operator path for validating storage footprint and legacy DB state
  3. Milestone requirements are closed with verification-backed evidence rather than assumptions
**Plans:** 3/3 plans complete
Plans:
- [x] 179-01-PLAN.md -- Capture live post-change DB sizes and storage status against the April 13 baseline
- [x] 179-02-PLAN.md -- Prove live reader topology and retained-history shape through supported operator surfaces
- [x] 179-03-PLAN.md -- Synthesize operator evidence, close OPER-04, and align final docs

## Progress

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 177. Live Storage Footprint Investigation | 3/3 | Complete | 2026-04-13 |
| 178. Retention Tightening And Legacy DB Cleanup | 3/3 | Complete | 2026-04-13 |
| 179. Verification And Operator Evidence | 3/3 | Complete | 2026-04-13 |
