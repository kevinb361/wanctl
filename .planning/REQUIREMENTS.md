# Requirements: wanctl — Milestone v1.57

**Milestone:** v1.57 Supported read-only RouterOS ownership inspection
**Status:** Defining → roadmap
**Created:** 2026-06-20

**Goal:** Repair and prove a supported read-only RouterOS ownership-inspection path from `cake-shaper`, then rerun the v1.56-blocked dry-run observation — validating intended wanctl route decisions against live Netwatch/default-route state, with no route ownership change.

**Context:** v1.56 ended `not-ready` because supported live RouterOS Netwatch/default-route inspection could not be proven from `cake-shaper`: the validated SSH key path (`/etc/wanctl/ssh/router.key`) was inaccessible there. Netwatch remains the interim route owner. v1.57 unblocks the access layer first, proves read-only inspection, then re-executes the observation v1.56 could not complete.

---

## v1.57 Requirements

### ACCESS — Validated read-only RouterOS access from cake-shaper

- [ ] **ACCESS-01**: Diagnose root cause of the inaccessible RouterOS inspection credential (`/etc/wanctl/ssh/router.key`) on `cake-shaper` — presence, path, ownership, permissions, and the service user that must read it — and document the root cause.
- [ ] **ACCESS-02**: Repair or establish a *supported* read-only RouterOS access path from `cake-shaper`, proven by a live read-only RouterOS command (restored key with correct owner/perms, or a supported equivalent path).
- [ ] **ACCESS-03**: The access path is least-privilege and read-only — the credential/method used for inspection cannot perform route mutation, Netwatch changes, or config writes (any write capability is explicitly out-of-band and separately gated).

### INSPECT — Read-only RouterOS ownership inspection

- [ ] **INSPECT-01**: wanctl reads live RouterOS Netwatch state from `cake-shaper` over the validated path and surfaces it as ownership-inspection evidence.
- [ ] **INSPECT-02**: wanctl reads live default-route / route-ownership state from `cake-shaper` and attributes the current owner (Netwatch vs wanctl vs none).
- [ ] **INSPECT-03**: Ownership-inspection output/health is attributed distinctly from cake-autorate bridge health (`:9101`) and steering route-management health (`:9102`), with no payload-shape regression to existing health contracts.

### OBSERVE — Dry-run observation rerun + readiness

- [ ] **OBSERVE-01**: Rerun the bounded read-only/dry-run observation v1.56 blocked, now with live RouterOS inspection succeeding — compute intended wanctl route decisions without RouterOS route mutation.
- [ ] **OBSERVE-02**: Compare intended wanctl route decisions against live Netwatch/default-route state and record divergences as evidence, not automatic mutations.
- [ ] **OBSERVE-03**: Produce a canary-readiness decision packet with an explicit `ready-for-approval` or `not-ready` verdict, including blockers, evidence, and rollback readiness.

### SAFE

- [ ] **SAFE-21**: No live RouterOS route mutation, Netwatch disablement, CAKE/qdisc change, controller threshold retuning, or production default route-owner flip occurs during v1.57; any active-route canary remains a separate, explicit, reversible operator gate. (Inherits SAFE-20 intent.)

---

## Future Requirements (deferred)

- Active-route canary execution (wanctl owns a single route under controlled, reversible conditions) — gated behind an explicit operator approval after v1.57 produces `ready-for-approval`.
- Netwatch retirement / route-owner flip — out of scope until a successful canary.

## Out of Scope (this milestone)

- **Any RouterOS route mutation** — read-only inspection only.
- **Netwatch disablement or reconfiguration** — Netwatch remains interim owner.
- **CAKE/qdisc changes and controller threshold retuning** — control path frozen.
- **New steering features beyond inspection + dry-run** — no scope creep past the v1.56 blocker.

---

## Traceability

| REQ-ID | Phase | Status |
|--------|-------|--------|
| ACCESS-01 | Phase 258 | pending |
| ACCESS-02 | Phase 258 | pending |
| ACCESS-03 | Phase 258 | pending |
| INSPECT-01 | Phase 259 | pending |
| INSPECT-02 | Phase 259 | pending |
| INSPECT-03 | Phase 259 | pending |
| OBSERVE-01 | Phase 260 | pending |
| OBSERVE-02 | Phase 260 | pending |
| OBSERVE-03 | Phase 260 | pending |
| SAFE-21 | all phases (258, 259, 260) | pending |
