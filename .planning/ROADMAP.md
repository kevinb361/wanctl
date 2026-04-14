# Roadmap: wanctl v1.37 Dashboard History Source Clarity

## Overview

Make the dashboard history tab reflect the current history contract so operators can tell when they are looking at endpoint-local HTTP history, see the source metadata that explains it, and know how to reach the authoritative merged CLI history path.

## Phases

### Phase 183: Dashboard History Contract Audit

**Goal**: Close the gap between the documented history contract and what the dashboard currently implies
**Depends on**: Phase 182
**Plans**: 2 plans

Plans:

- [x] 183-01: Audit dashboard history behavior, payload usage, and operator ambiguity points
- [x] 183-02: Define the dashboard-facing source contract and acceptance criteria for UI, tests, and docs

### Phase 184: Dashboard History Source Surfacing

**Goal**: Implement the dashboard changes that make local-vs-merged history semantics explicit without changing backend history behavior
**Depends on**: Phase 183
**Plans**: 3 plans

Plans:

- [x] 184-01: Surface source scope and endpoint-local labeling in the history tab
- [x] 184-02: Expose `metadata.source` and related source context in the history UI
- [x] 184-03: Add a clear operator path from the dashboard to the authoritative merged CLI history workflow

### Phase 185: Verification And Operator Alignment

**Goal**: Lock the new dashboard contract with regression coverage and operator-facing guidance
**Depends on**: Phase 184
**Plans**: 3/3 plans complete

Plans:

- [x] 185-01: Add focused dashboard/history regressions for source labeling and failure behavior
- [x] 185-02: Align docs and operator workflow guidance with the dashboard’s source semantics
- [x] 185-03: Verify the milestone closeout against the UI contract and operator workflow
