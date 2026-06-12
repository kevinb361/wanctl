# Requirements: wanctl v1.51 Post-Migration Consolidation

**Defined:** 2026-06-10
**Core Value:** Sub-second congestion detection with 50ms control loops, achieved through systematic performance optimization and code quality improvements while maintaining production reliability.
**Milestone Goal:** Consolidate the two-mode (native + cake-autorate) reality and close the pre-existing carry-forward stack — repo hygiene, rollback-tooling fixes, and planning-artifact reconciliation, with zero controller-path mutation.

## v1.51 Requirements

Requirements for this milestone. Each maps to roadmap phases.

### Cleanup Boundary (BOUND)

- [x] **BOUND-01**: Operator can rely on a machine-checkable guard encoding the `WANCTL_CAKE_AUTORATE_FUTURE.md` no-delete list (`src/wanctl/autorate_continuous.py`, native `wanctl@$wan.service` deploy path, native controller tests, native config validation, rollback commands/docs); sweep work fails closed if any denylisted surface is touched

### Rollback & Operator Tooling Fixes (FIX)

- [x] **FIX-01**: Operator can run `phase231-rollback.sh` without the confirm-path risk flagged in v1.50 Phase 231 code review; the script remains double-gated and dry-run by default; NO live rollback is exercised this milestone
- [x] **FIX-02**: The 2026-04-17 operator-summary digest permission-handling todo is closed by validating actual behavior against v1.44 Phase 208 T12/TOOL-03 (unreadable-DB open tolerance) — closed with tests or recorded evidence; reimplemented only if validation shows the todo's acceptance criterion unmet

### Repo Hygiene Sweep (SWEEP)

- [x] **SWEEP-01**: Superseded one-off trial scripts are removed or archived per the future-doc cleanup policy ("safe to remove soon" category only)
- [x] **SWEEP-02**: No remaining active doc describes Spectrum/ATT as native-wanctl-owned without noting the current external mode (residual verification beyond v1.50 Phase 231 DOCS-04)
- [x] **SWEEP-03**: Spectrum-only hardcoding remnants are removed where a generic `$wan` bridge/service pattern already exists (no new abstraction introduced to enable removal)

### Planning Metadata Reconciliation (META)

- [x] **META-01**: The 12 orphan quick-task slugs from older milestones are resolved via a `/gsd-cleanup`-style sweep (archived or closed with pointer, not silently deleted)
- [x] **META-02**: Silicom pending todos (2026-04-28 ×2) and SEED-006 are reconciled to a consistent state — SEED-006 remains the canonical dormant carrier OR todos remain canonical, but not both claiming different states; no false-closing of operationally real bypass work
- [x] **META-03**: v1.50 Phase 230 Nyquist PARTIAL is resolved — retroactive `/gsd-validate-phase 230` executed, or an explicit waiver recorded in planning state

### Safety (SAFE)

- [x] **SAFE-15**: Zero controller-path source diff (`wan_controller.py`, `queue_controller.py`, `cake_signal.py`, backends, `alert_engine.py`, fusion) at every phase boundary AND milestone close — 9th consecutive milestone holding the SAFE-07..14 discipline

## Future Requirements

Deferred to later milestones. Tracked but not in v1.51.

- **ROLE-01**: Native Linux autorate controller retirement/retention decision — time/event-gated on matured cake-autorate soak (~2 days as of v1.51 open is not "observed"); `WANCTL_CAKE_AUTORATE_FUTURE.md` "What not to delete yet" governs until then
- **TAIL-01**: Spectrum loaded-latency tail evidence milestone — NOT exhausted per 2026-06-10 Codex review (managed-inline qdisc path contribution + Dallas repeat/minimal-qdisc branch unexplored)
- **SEED-006**: Silicom bypass tooling + test harness — v1.51 runner-up; operationally real (ATT migration hit a live bypass-watchdog failure mode); revisit at v1.52 scoping
- **SEED-007**: Storage hygiene fire-on-change — must be reshaped for bridge writers (state bridges now own metrics DB writes); requires consumer audit before any sparse-write change; deferred as its own thesis
- **SEED-005**: Conservative UL tuning sweep — deferred not dead; native wanctl remains first-class on RouterOS deployments
- **fping RTT backend evaluation** (2026-06-04 todo) — covers `rtt_measurement.py`, native autorate, and steering cycle budgets; relevance reduced while native controller not live, retained for RouterOS-deployment future

## Out of Scope

Explicitly excluded. Documented to prevent scope creep.

| Feature | Reason |
|---------|--------|
| Live rollback exercise | FIX-01 is pre-rollback hygiene only; conflating fix with exercise creates an unplanned production mutation path |
| Anything on the future-doc denylist | "Not safe to remove until after ATT migration soak" is binding: native controller, native deploy path, native tests, native config validation, rollback commands/docs |
| SEED-007 bridge-writer storage hygiene | Biggest scope-explosion risk (consumer audit could balloon); operator deferred at 2026-06-10 scoping |
| SEED-006 silicom harness | Runner-up at joint scoping; hardware-in-the-loop, Medium-Large — consolidate first |
| ROLE-01 retirement decision | Event-gated, not buildable work |
| TAIL-01 Spectrum tail investigation | Different milestone shape (evidence/investigation) |
| Controller threshold/algorithm changes | SAFE-15 — surface is scripts/docs/planning/tests only |
| New `$wan` abstractions | SWEEP-03 removes hardcoding only where a generic pattern already exists |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| BOUND-01 | Phase 232 | Complete |
| FIX-01 | Phase 232 | Complete |
| FIX-02 | Phase 232 | Complete |
| SWEEP-01 | Phase 233 | Complete |
| SWEEP-02 | Phase 233 | Complete |
| SWEEP-03 | Phase 233 | Complete |
| META-01 | Phase 234 | Complete |
| META-02 | Phase 234 | Complete |
| META-03 | Phase 234 | Complete |
| SAFE-15 | Phase 234 (cross-phase: verified at 232/233/234 boundaries) | Complete |

**Coverage:**
- v1.51 requirements: 10 total
- Mapped to phases: 10
- Unmapped: 0

**Phase mapping:**
- Phase 232 (Cleanup Boundary Guard + Tooling Fixes): BOUND-01, FIX-01, FIX-02
- Phase 233 (Gated Repo Hygiene Sweep): SWEEP-01, SWEEP-02, SWEEP-03
- Phase 234 (Planning Metadata Reconciliation + Closeout): META-01, META-02, META-03, SAFE-15

> SAFE-15 is a cross-phase controller-path zero-diff invariant verified at every phase boundary (232, 233, 234); mapped to closeout Phase 234 for traceability accounting per the v1.50 SAFE-14 precedent.

---
*Requirements defined: 2026-06-10 (joint Claude + Codex scope decision)*
*Roadmap mapped: 2026-06-10 — 10/10 REQs to Phases 232–234, 0 orphans*
