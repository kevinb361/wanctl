# Roadmap: wanctl v1.35 Storage Health & Stabilization

## Overview

Fix the critical storage bloat (925 MB metrics.db), resolve the periodic maintenance CPython error, make analyze_baseline deployable, then deploy v1.35 cleanly and let the full v1.34 observability stack prove itself in a 24h production soak.

## Phases

- [ ] **Phase 172: Storage Health & Code Fixes** - Shrink metrics DB, fix periodic maintenance error, fix analyze_baseline import path
- [ ] **Phase 173: Clean Deploy & Canary Validation** - Version bump, deploy.sh run, canary-check.sh exit 0
- [ ] **Phase 174: Production Soak** - 24h soak validating storage pressure and full observability stack stability

## Phase Details

### Phase 172: Storage Health & Code Fixes
**Goal**: Production storage is under control and all code bugs found during v1.34 UAT are fixed
**Depends on**: Phase 171
**Requirements**: STOR-01, STOR-02, DEPL-02
**Success Criteria** (what must be TRUE):
  1. Metrics DB size is reduced below the storage-pressure warning threshold and retention settings prevent re-growth
  2. Periodic maintenance runs complete without "error return without exception set" or any other unhandled error
  3. analyze_baseline.py runs successfully on production with correct import paths
**Plans:** 4 plans (3 complete, 1 gap closure)
Plans:
- [x] 172-01-PLAN.md -- Per-WAN storage config and SystemError-resilient maintenance
- [x] 172-02-PLAN.md -- analyze_baseline entry point promotion and CLI multi-DB discovery
- [x] 172-03-PLAN.md -- One-shot DB migration script and canary storage verification (gap closure)
- [ ] 172-04-PLAN.md -- Top-level storage field in autorate health endpoint (gap closure)

### Phase 173: Clean Deploy & Canary Validation
**Goal**: Production is running v1.35 with version bump and canary confirms all services healthy
**Depends on**: Phase 172
**Requirements**: DEPL-01
**Success Criteria** (what must be TRUE):
  1. deploy.sh completes without errors and the deployed version reports v1.35.x
  2. canary-check.sh returns exit 0 for both Spectrum and ATT services
**Plans**: TBD

### Phase 174: Production Soak
**Goal**: The full observability stack runs cleanly in production for 24h, proving storage and runtime stability
**Depends on**: Phase 173
**Requirements**: STOR-03, SOAK-01
**Success Criteria** (what must be TRUE):
  1. Storage pressure stays at ok or warning (not critical) for the full 24h soak period
  2. Zero unexpected service restarts and zero unhandled errors in journalctl for both WAN services over 24h
  3. All v1.34 operator surfaces (alerts, pressure monitoring, summaries, canary) produce valid output at soak end
**Plans**: TBD

## Progress

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 172. Storage Health & Code Fixes | 3/4 | Gap closure in progress | - |
| 173. Clean Deploy & Canary Validation | 0/0 | Not started | - |
| 174. Production Soak | 0/0 | Not started | - |
