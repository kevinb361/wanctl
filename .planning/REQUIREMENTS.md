# Requirements — wanctl

## v1.61 QoS Classification Contract

**Goal:** Make RouterOS the authoritative host-aware classifier and route selector, make cake-shaper the authoritative CAKE enforcement point, and use a tested DSCP/conntrack contract between them without duplicating application policy.

- [x] **REQ-001** — An operator-facing contract documents ownership, trust boundaries, the EF/AF31/CS0/CS1 class map, rejected alternatives, and rollback behavior. (milestone: v1.61)
  Evidence: `docs/QOS_CLASSIFICATION_CONTRACT.md`, `.planning/decisions/2703-routeros-classifies-cake-enforces.md`.
- [x] **REQ-002** — RouterOS-originated AF31 packets on both WAN upload paths seed the bridge connection mark that restores replies into the CAKE Video tin. (milestone: v1.61)
  Evidence: `deploy/nftables/bridge-qos.nft`, `tests/test_bridge_qos_nft.py::test_router_dscp_classification_is_propagated_to_download_replies`, `make ci` 2026-07-17.
- [ ] **REQ-003** — Both WAN paths apply the same four-class contract and unclassified traffic falls back to Best Effort; duplicate bridge application classifiers are removed only after equivalent contract coverage is proven. (milestone: v1.61)
  Partial evidence: exact symmetric import/restore and Best Effort fallback assertions in `tests/test_bridge_qos_nft.py`; the finite registry in `../infra-ansible/artifacts/network-changes/20260717_routeros-qos-composite-policy/generic_rtp_canary.py`; and the read-only audit in `../infra-ansible/scripts/routeros-qos-contract-audit.py`. The latest direct-SSH generic-RTP canary actually inserted enabled rule #36 immediately before the true catch-all #37, but was rolled back fail-closed because the audit misclassified narrow terminal QUIC rule #21 as the default boundary. Root cause and raw evidence: `../infra-ansible/artifacts/network-changes/20260717_routeros-qos-composite-policy/root-cause-audit-false-positive-20260718T131244Z.md`. Infra commit `21187c3` fixes catch-all semantics, fails closed if no catch-all exists, and passed `19` audit tests, `95` full-suite tests, and fresh Claude exact-commit second-pass review with zero blockers. Fresh packet `../infra-ansible/artifacts/network-changes/20260717_routeros-qos-composite-policy/approval-packet-generic-rtp-reapply-20260718T133503Z.md` is paused at explicit production approval after baseline, audit, `25/25` preflight, and DNS passed. Production remains at the healthy five-gap baseline. Approved generic-RTP reapply, explicit per-selector audit proof, traffic proof, the remaining four selectors, and bridge retirement remain open.
- [x] **REQ-004** — Adaptive WAN steering is selected independently from QoS priority, applies only to eligible new connections, and does not move recursive DNS merely because DNS is high priority. (milestone: v1.61)
  Evidence: `src/wanctl/steering/daemon.py::reconcile_steering_rule`, `tests/steering/test_steering_daemon.py`, `docs/QOS_CLASSIFICATION_CONTRACT.md`, and `../infra-ansible/artifacts/network-changes/20260717_routeros-qos-composite-policy/live-canary-result.txt`. The broad `QOS_HIGH` selector is retired; the exact Work-VPN/new-connection producer is controller-owned and DNS-safe.
- [x] **REQ-005** — The effective RouterOS QoS and steering policy has a version-controlled, read-only audit surface that detects ordering, FastTrack, DSCP-map, per-application equivalence, and steering-eligibility drift. (milestone: v1.61)
  Evidence: `../infra-ansible/scripts/routeros-qos-contract-audit.py`, `../infra-ansible/tests/test_routeros_qos_contract_audit.py`, `../infra-ansible/tests/test_routeros_qos_composite_policy.py`, live `make routeros-qos-contract-audit` 2026-07-17.
- [x] **REQ-006** — A reversible live canary under controlled bulk load proves DNS responsiveness, work-VPN reachability, expected CAKE tin counters, both-WAN behavior, and successful rollback. (milestone: v1.61)
  Evidence: `../infra-ansible/artifacts/network-changes/20260717_routeros-qos-composite-policy/live-canary-result.txt`. The corrected canary passed bounded both-WAN load, the real FortiVPN reconnect, DNS probes, expected CAKE counters, approval-gated demigration, and approval-gated remigration to the DNS-safe adaptive layout without clearing conntrack.

### SAFE-24 — Production QoS convergence

- Repo-only docs, tests, audits, and undeployed rules are permitted without a live gate.
- RouterOS mangle, nftables deployment, qdisc changes, steering activation, service restarts, and controlled saturation are production mutations requiring an exact rollback anchor and explicit operator approval.
- CAKE rates, autorate thresholds, route ownership, NAT, and the split-edge topology are outside this milestone unless separately approved.

### Out of scope

- Moving NAT/routing to Linux or replacing the split edge with a DIY router.
- Claiming per-LAN-host CAKE fairness while NAT remains on a different host.
- Application-layer inspection or broad port-list expansion on cake-shaper.
- CAKE rate or controller-threshold tuning.

---

# Historical Requirements — Milestone v1.58 Active Route-Management Canary

**Goal:** Flip wanctl into the active default-route owner role for a single canary route, demoting Netwatch to disabled-but-retained, under an explicit reversible operator gate with automatic abort-to-Netwatch. First *mutating* milestone in the v1.55→v1.57 route-ownership line (`SEED-008`).

**Phase numbering:** continues from v1.57 (ended Phase 260) → v1.58 starts at **Phase 261**.

**Scoping decisions (locked 2026-06-26):**
- First flip granularity: **single-route** (smallest blast radius).
- Netwatch demotion: **disabled-but-retained** (fast one-command revert).
- Deploy reconciliation: **full `deploy.sh` first** (repo==prod before any mutation).
- Abort: **automatic abort wired** (circuit-breaker auto-revert) + manual rollback retained.
- Entry-gates verified at execution: ≥14 consecutive stable cake-autorate days + explicit operator approval.

---

## v1.58 Requirements

### RECON — Pre-flip deploy reconciliation
- [ ] **RECON-01**: Operator can run a full `deploy.sh` to `cake-shaper` bringing `/opt/wanctl` to repo-equal state (resolves the `route_ownership_guard.py` drift from the v1.57 D-07 fix), with a pre/post sha256 audit proving repo==prod.
- [ ] **RECON-02**: The reconcile captures a rollback anchor (pre-deploy `/opt/wanctl` snapshot) so the deploy itself is reversible.
- [ ] **RECON-03**: Post-deploy, the route-management surface and `:9102` health come up clean in the existing dry-run/safe state — the reconcile alone changes no ownership behavior.

### APPROVE — Operator approval gate
- [ ] **APPROVE-01**: The milestone presents the Phase 260 `ready-for-approval` packet and the entry-gate status to the operator as an explicit decision artifact before any flip.
- [ ] **APPROVE-02**: No ownership flip executes without a recorded explicit operator approval (`ready-for-approval` is a verdict, NOT approval — per D-10/SAFE-21); approval is captured auditably (who/when).
- [ ] **APPROVE-03**: The ≥14-consecutive-stable-cake-autorate-days soak gate is machine-verified at execution time and the result recorded; failing the gate blocks the flip.

### OWNFLIP — Single-route ownership flip
- [ ] **OWNFLIP-01**: Operator can flip a single canary route's default-ownership from Netwatch to wanctl via a guarded, gated command.
- [ ] **OWNFLIP-02**: Netwatch is demoted **disabled-but-retained** (config preserved, not deleted); a one-command re-enable restores prior ownership.
- [ ] **OWNFLIP-03**: After the flip, wanctl is the sole active owner of the canary route and Netwatch is not contending for it (no dual-ownership route flap).
- [ ] **OWNFLIP-04**: The flip is bounded to exactly one canary route — no other route or WAN ownership changes.

### ABORT — Automatic abort + rollback drill
- [ ] **ABORT-01**: A rollback drill (flip → revert to Netwatch) is exercised and proven **before** the live canary flip; the revert restores the pre-flip ownership state.
- [ ] **ABORT-02**: Circuit-breaker/guard automatically reverts the canary route to Netwatch ownership on defined trip conditions (link down / route flap / Netwatch contention).
- [ ] **ABORT-03**: Auto-abort trips and the resulting revert are observable/recorded (the operator can see what tripped and that revert completed).
- [ ] **ABORT-04**: Operator retains a manual one-command rollback independent of the automatic path.

### FLIPOBS — Live flip observability
- [ ] **FLIPOBS-01**: The `:9102` route-management health surface asserts owner/mode/guard fields transition cleanly through the flip (netwatch→wanctl) and back on revert.
- [ ] **FLIPOBS-02**: Health distinctly shows the Netwatch-demoted state vs the wanctl-active-owner state — no ambiguity about who owns the route.
- [ ] **FLIPOBS-03**: No payload-shape regression on `:9101` (bridge) or `:9102` (steering) health from the canary work.

---

## Cross-Cutting Safety Invariant — SAFE-22

SAFE-22 narrows SAFE-21: it is the first invariant in this line that *permits* a production mutation, scoped tightly.

**Permitted (and only these):**
- The gated single-route default-route owner flip (Netwatch → wanctl) on exactly one canary route.
- The automatic abort / revert-to-Netwatch mutation on that same canary route.
- The pre-flip `deploy.sh` reconciliation of `/opt/wanctl` on `cake-shaper`.

**Forbidden:**
- CAKE/qdisc change.
- Controller threshold retuning.
- Netwatch **deletion** (disable-but-retain only).
- Any ownership flip beyond the one canary route (no second route, no whole-WAN, no both-WAN).
- Any controller-path source diff: `wan_controller.py`, `queue_controller.py`, `cake_signal.py`, RTT backends, `alert_engine.py`, fusion.

SAFE-22 is a milestone-wide cross-cutting invariant checked at every phase boundary and at milestone close — not a standalone phase.

---

## Out of Scope (explicit exclusions)

- **Whole-WAN or both-WAN ownership flip** — first canary is single-route only; widening is a future milestone after the single-route flip is proven.
- **Netwatch deletion / permanent retirement** — demote disabled-but-retained only; full Netwatch retirement (ROLE/RETIRE line) stays deferred.
- **Controller-path tuning or algorithm changes** — SAFE-22 keeps the control loop zero-diff.
- **CAKE/qdisc / DSCP / threshold work** — unrelated to ownership; barred.
- **Steering disposition logic changes** — steering health surface is asserted, not modified.
- **Native `wanctl@` controller revival** — production stays on cake-autorate bridges.

---

## Future Requirements (deferred)

- **Widen-the-canary** — multi-route, then single-WAN, then both-WAN ownership once single-route is proven stable.
- **Netwatch full retirement** — remove (not just disable) once wanctl ownership is durably trusted.
- Pre-existing deferred items carried from v1.56/v1.57 close (steering clean-restart, ingestion-rate tool, flapping-peak monitor, ATT-cake-primary canary, diffserv4-wash retest) — unchanged, not v1.58 drivers.

---

## Traceability

_Each REQ mapped to exactly one phase (roadmap 2026-06-26). 17/17 mapped, 0 orphans, 0 duplicates._

| REQ-ID | Phase | Status |
|--------|-------|--------|
| RECON-01 | Phase 261 | Pending |
| RECON-02 | Phase 261 | Pending |
| RECON-03 | Phase 261 | Pending |
| ABORT-01 | Phase 262 | Pending |
| ABORT-02 | Phase 262 | Pending |
| ABORT-04 | Phase 262 | Pending |
| APPROVE-01 | Phase 263 | Pending |
| APPROVE-02 | Phase 263 | Pending |
| APPROVE-03 | Phase 263 | Pending |
| OWNFLIP-01 | Phase 264 | Pending |
| OWNFLIP-02 | Phase 264 | Pending |
| OWNFLIP-03 | Phase 264 | Pending |
| OWNFLIP-04 | Phase 264 | Pending |
| FLIPOBS-01 | Phase 264 | Pending |
| FLIPOBS-02 | Phase 264 | Pending |
| FLIPOBS-03 | Phase 264 | Pending |
| ABORT-03 | Phase 264 | Pending |
| SAFE-22 | All phases (cross-cutting invariant, checked at every phase boundary + milestone close) | Pending |
