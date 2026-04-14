# Roadmap: wanctl v1.36 Storage Retention And DB Footprint

## Overview

Production storage is still healthy, but the active per-WAN metrics databases remain larger than expected and the legacy `metrics.db` file still exists alongside them. This milestone explains the live footprint, removes legacy DB ambiguity, and reduces retained metrics size without changing the controller’s decision logic or operator-facing contracts.

## Phases

- [x] **Phase 177: Live Storage Footprint Investigation** - Measure active DB composition, retention shape, and legacy DB activity on production (completed 2026-04-13)
- [x] **Phase 178: Retention Tightening And Legacy DB Cleanup** - Apply the smallest safe storage-footprint reduction that closes the live findings (completed 2026-04-13)
- [x] **Phase 179: Verification And Operator Evidence** - Prove the new storage footprint holds in production and document the operator verification path (completed 2026-04-13)
- [x] **Phase 180: Verification Backfill And Audit Closure** - Close the missing Phase 177 verification trail and re-anchor STOR-04 to milestone-grade evidence (completed 2026-04-14)
- [x] **Phase 181: Production Footprint Reduction And Reader Parity** - Execute the production footprint-reduction attempt, recover the startup regression, and capture final live outcome evidence (completed 2026-04-14; requirement gap remains)

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
| 180. Verification Backfill And Audit Closure | 2/2 | Complete | 2026-04-14 |
| 181. Production Footprint Reduction And Reader Parity | 3/3 | Complete | 2026-04-14 |

### Phase 180: Verification Backfill And Audit Closure
**Goal**: Close the missing milestone verification trail for Phase 177 and leave STOR-04 audit-safe
**Depends on**: Phase 179
**Requirements**: STOR-04
**Gap Closure:** Closes the `STOR-04` orphaned requirement gap and the missing Phase 177 verification trail identified by the v1.36 milestone audit
**Success Criteria** (what must be TRUE):
  1. Phase 177 has a formal verification artifact that maps its evidence and summaries back to STOR-04
  2. STOR-04 is no longer orphaned in milestone audit cross-references
  3. The milestone verification trail for the storage-investigation phase is complete without inventing new evidence
**Plans:** 2/2 plans complete
Plans:
- [x] 180-01-PLAN.md -- Backfill the missing Phase 177 verification artifact for STOR-04
- [x] 180-02-PLAN.md -- Re-anchor the STOR-04 audit trail and route the milestone back to re-audit

### Phase 181: Production Footprint Reduction And Reader Parity
**Goal**: Close the failed production outcome behind STOR-06 and reconcile the remaining live reader-path drift
**Depends on**: Phase 180
**Requirements**: STOR-06
**Gap Closure:** Closes the `STOR-06` unsatisfied requirement, the failed retention->footprint flow, and the live `/metrics/history` parity drift identified by the v1.36 milestone audit
**Success Criteria** (what must be TRUE):
  1. The active per-WAN DB footprint is materially smaller than the 2026-04-13 baseline in production terms
  2. The production operator proof path for history reads is internally consistent, including the deployed CLI/wrapper path and the live HTTP endpoint role
  3. Any remaining HTTP/CLI reader differences are either eliminated or explicitly narrowed without breaking operator workflows
**Plans:** 3/3 plans complete
Plans:
- [x] 181-01-PLAN.md -- Implement a concrete storage-only reduction path that can materially shrink live per-WAN DB files
- [x] 181-02-PLAN.md -- Close or explicitly narrow live CLI/HTTP history-reader parity drift without breaking the HTTP contract
- [x] 181-03-PLAN.md -- Capture final production footprint and reader-parity evidence against the fixed 2026-04-13 baseline
