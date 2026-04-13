# Roadmap: wanctl v1.35 Storage Health & Stabilization

## Overview

Fix the critical storage bloat (925 MB metrics.db), resolve the periodic maintenance CPython error, make analyze_baseline deployable, then deploy v1.35 cleanly and let the full v1.34 observability stack prove itself in a 24h production soak.

## Phases

- [x] **Phase 172: Storage Health & Code Fixes** - Shrink metrics DB, fix periodic maintenance error, fix analyze_baseline import path (completed 2026-04-12)
- [x] **Phase 173: Clean Deploy & Canary Validation** - Version bump, rolling per-WAN deploy, canary-check.sh exit 0 (completed 2026-04-12)
- [x] **Phase 174: Production Soak** - 24h soak validating storage pressure and full observability stack stability (completed 2026-04-13)
- [ ] **Phase 175: Verification And Evidence Closeout** - Formalize missing phase verification reports and close the remaining audit evidence gaps
- [ ] **Phase 176: Deployment And Soak Flow Alignment** - Align deploy/install/soak operator flows with what v1.35 actually required in production

## Phase Details

### Phase 172: Storage Health & Code Fixes
**Goal**: Production storage is under control and all code bugs found during v1.34 UAT are fixed
**Depends on**: Phase 171
**Requirements**: STOR-01, STOR-02, DEPL-02
**Success Criteria** (what must be TRUE):
  1. Metrics DB size is reduced below the storage-pressure warning threshold and retention settings prevent re-growth
  2. Periodic maintenance runs complete without "error return without exception set" or any other unhandled error
  3. analyze_baseline.py runs successfully on production with correct import paths
**Plans:** 5/5 plans complete
Plans:
- [x] 172-01-PLAN.md -- Per-WAN storage config and SystemError-resilient maintenance
- [x] 172-02-PLAN.md -- analyze_baseline entry point promotion and CLI multi-DB discovery
- [x] 172-03-PLAN.md -- One-shot DB migration script and canary storage verification (gap closure)
- [x] 172-04-PLAN.md -- Top-level storage field in autorate health endpoint (gap closure)
- [x] 172-05-PLAN.md -- Fix wrapper bootstrap and deploy path for analyze_baseline (gap closure)

### Phase 173: Clean Deploy & Canary Validation
**Goal**: Production is running v1.35 with version bump and canary confirms all services healthy
**Depends on**: Phase 172
**Requirements**: DEPL-01
**Success Criteria** (what must be TRUE):
  1. deploy.sh completes without errors and the deployed version reports v1.35.0
  2. canary-check.sh returns exit 0 for both Spectrum and ATT services
**Plans:** 3/3 plans complete
Plans:
- [x] 173-01-PLAN.md -- Version bump to 1.35.0 in three canonical files
- [x] 173-02-PLAN.md -- Spectrum-first deploy, storage migration, Spectrum health validation
- [x] 173-03-PLAN.md -- ATT deploy with steering, full canary validation across both WANs

### Phase 174: Production Soak
**Goal**: The full observability stack runs cleanly in production for 24h, proving storage and runtime stability
**Depends on**: Phase 173
**Requirements**: STOR-03, SOAK-01
**Success Criteria** (what must be TRUE):
  1. Storage pressure stays at ok or warning (not critical) for the full 24h soak period
  2. Zero unexpected service restarts and zero unhandled errors in journalctl for both WAN services over 24h
  3. All v1.34 operator surfaces (alerts, pressure monitoring, summaries, canary) produce valid output at soak end
**Plans:** 1/1 plans complete
Plans:
- [x] 174-01-PLAN.md -- 24h soak validation: eligibility check, 4-tool evidence capture, SUMMARY + REQUIREMENTS update

### Phase 175: Verification And Evidence Closeout
**Goal**: Close the milestone audit blockers by formalizing live evidence and adding the missing phase verification artifacts
**Depends on**: Phase 174
**Requirements**: STOR-01, DEPL-01, STOR-03, SOAK-01
**Gap Closure**: Closes missing verification coverage and the remaining human-needed evidence gate from the v1.35 milestone audit
**Success Criteria** (what must be TRUE):
  1. `172-VERIFICATION.md` is updated to either record the live migration/canary evidence for `STOR-01` or explicitly document accepted residual debt
  2. `173-VERIFICATION.md` exists and verifies `DEPL-01` using the production deploy and canary evidence already captured in milestone artifacts
  3. `174-VERIFICATION.md` exists and verifies `STOR-03` and `SOAK-01` using the recorded soak evidence, including any missing service coverage explicitly addressed
  4. Validation bookkeeping needed for re-audit exists for Phase 174 and no milestone requirement is orphaned from verification
**Plans:** 0/0 plans complete

### Phase 176: Deployment And Soak Flow Alignment
**Goal**: Make the repo's active operator flow match the deployment and soak steps that v1.35 actually depended on in production
**Depends on**: Phase 175
**Requirements**: STOR-01, DEPL-01, STOR-03, SOAK-01
**Gap Closure**: Closes audit integration and E2E flow gaps around migration wiring, install metadata, operator tooling, and soak coverage
**Success Criteria** (what must be TRUE):
  1. `scripts/deploy.sh` includes the required migration guidance or orchestration so the deploy -> migrate -> restart -> canary path is explicit and repeatable
  2. `scripts/install.sh` release metadata matches the shipped runtime version instead of stale `1.32.2` data
  3. The operator-summary invocation path is aligned with what install/deploy actually places on the target system
  4. Soak monitoring and evidence capture cover all claimed services, including `steering.service`, not just Spectrum
**Plans:** 0/0 plans complete

## Progress

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 172. Storage Health & Code Fixes | 5/5 | Complete    | 2026-04-12 |
| 173. Clean Deploy & Canary Validation | 3/3 | Complete    | 2026-04-12 |
| 174. Production Soak | 1/1 | Complete    | 2026-04-13 |
| 175. Verification And Evidence Closeout | 0/0 | Pending     | |
| 176. Deployment And Soak Flow Alignment | 0/0 | Pending     | |
