# Requirements — wanctl

## v1.62 QoS Validation & Trust Hardening

**Goal:** Add packet-level evidence and bounded hardening to the proven RouterOS-classifies / cake-shaper-enforces contract without retuning or broadening production scope.

- [x] **QVT-001** — A fresh read-only baseline proves the strict RouterOS QoS contract, live cake-shaper service/health posture, both-WAN CAKE continuity, and the exact nature of current bridge artifact drift. (milestone: v1.62)
  Evidence: `.planning/evidence/v1.62-baseline-20260719.md`; `../infra-ansible/artifacts/network-audits/20260719_211000-main-router-firewall-qos/qos-contract-audit.json`; `.planning/evidence/live-preflight/wanctl-live-preflight-20260719T210924Z.json`.
- [x] **QVT-002** — A bounded Spectrum proof demonstrates EF, AF31, CS1, and CS0 on the RouterOS-to-cake-shaper path and shows CAKE remains structurally healthy, with no saturation requirement. (milestone: v1.62)
  Evidence: `.planning/evidence/v1.62-qvt002-second-attempt-pass-20260719.md`; exact live artifacts under `.planning/evidence/qvt002-spectrum-20260719T220859Z/`.
- [x] **QVT-003** — The zero-hit IoT DSCP wash rule is explained by read-only path evidence or a separately approved single-probe test that proves wash/normalization; ambiguity is not recorded as pass. (milestone: v1.62)
  Evidence: `.planning/evidence/v1.62-qvt003-natural-canary-proof-20260720.md`; the exact source-subnet canary increased `1429/377172 → 1458/385374` over ten seconds of natural traffic while the untouched interface rule remained `0/0`, matching the earlier proven EF packet mismatch and bridge/trunk root-cause evidence. No re-proof packet was generated.
- [x] **QVT-004** — DSCP trust is either narrowed to explicit legitimate marking sources through an exact reversible change, or retained by an explicit evidence-backed risk acceptance; broad trust is not left accidental. (milestone: v1.62)
  Evidence: explicit operator LOW-risk acceptance on 2026-07-20; `.planning/evidence/v1.62-qvt004-dscp-trust-analysis-20260720.md`; `.planning/evidence/v1.62-qvt004-ephemeral-v5-observation-20260720.md`. Broad EF/AF4x trust is intentionally retained with no RouterOS rule change: bounded observation found legitimate EF sources, AF4x remained inconclusive, CAKE limits scheduling abuse, and strict/postflight audits stayed healthy.
- [x] **QVT-005** — Repository/live `bridge-qos.nft` drift is reconciled or formally classified with executable-rule parity mechanically proven; no executable nftables change may hide inside comment convergence. (milestone: v1.62)
  Evidence: `.planning/evidence/v1.62-qvt005-bridge-drift-disposition-20260720.md`; fresh repo/live executable lines are ordered-equal `55/55`, both files pass nft syntax, and loaded five-chain/41-rule semantics equal repo. Raw difference is comment-only and formally retained until the next justified executable deployment; no reload occurred.
- [x] **QVT-006** — Disabled `QOS_GAME_DL` output and its absent producer receive an evidence-backed keep/remove disposition; any removal is exact, reversible, and separately approved. (milestone: v1.62)
  Evidence: `.planning/evidence/v1.62-qvt006-game-dl-disposition-20260720.md`. Keep exact `*308` disabled: fresh live scan finds one consumer, zero producers, zero counters, and no script/scheduler references; disabled state has no traffic/audit overhead, while standalone deletion adds rollback risk with no runtime benefit. No removal occurred.

### SAFE-25 — Bounded production proof and hardening

- [x] **SAFE-25** — Every controlled packet-generation step and every RouterOS/nftables/service mutation uses a fresh baseline, explicit action-specific approval, deterministic acceptance, and exact rollback; CAKE rates, autorate thresholds, routing/steering, NAT, firewall policy, topology, and saturation are unchanged. (milestone: v1.62)
  Evidence: `.planning/evidence/v1.62-safe25-invariant-20260720.md`; complete action ledger covers both QVT-002 packet attempts, QVT-003 failed packet and additive canary, all QVT-004 blocked/ephemeral attempts, retained failures, exact cleanup, no-retry/token rotation, risk acceptance, and declined nft/rule cleanup. Fresh strict audit PASS and wanctl `25/25`.

### Out of scope

- CAKE bandwidth/rate or controller-threshold tuning.
- Route ownership, WAN steering, NAT, firewall, VLAN, or topology changes.
- Broad load/saturation tests or clearing conntrack.
- Replacing the split-edge architecture or claiming per-LAN-host fairness.

---

## v1.61 QoS Classification Contract

**Goal:** Make RouterOS the authoritative host-aware classifier and route selector, make cake-shaper the authoritative CAKE enforcement point, and use a tested DSCP/conntrack contract between them without duplicating application policy.

- [x] **REQ-001** — An operator-facing contract documents ownership, trust boundaries, the EF/AF31/CS0/CS1 class map, rejected alternatives, and rollback behavior. (milestone: v1.61)
  Evidence: `docs/QOS_CLASSIFICATION_CONTRACT.md`, `.planning/decisions/2703-routeros-classifies-cake-enforces.md`.
- [x] **REQ-002** — RouterOS-originated AF31 packets on both WAN upload paths seed the bridge connection mark that restores replies into the CAKE Video tin. (milestone: v1.61)
  Evidence: `deploy/nftables/bridge-qos.nft`, `tests/test_bridge_qos_nft.py::test_router_dscp_classification_is_propagated_to_download_replies`, `make ci` 2026-07-17.
- [x] **REQ-003** — Both WAN paths apply the same four-class contract and unclassified traffic falls back to Best Effort; duplicate bridge application classifiers are removed only after equivalent contract coverage is proven. (milestone: v1.61)
  Evidence: exact symmetric import/restore and Best Effort fallback assertions in `tests/test_bridge_qos_nft.py`; the finite registry in `../infra-ansible/artifacts/network-changes/20260717_routeros-qos-composite-policy/generic_rtp_canary.py`; and the read-only audit in `../infra-ansible/scripts/routeros-qos-contract-audit.py`. Root-cause repair commit `21187c3` fixed catch-all semantics and fails closed if no catch-all exists. Generic RTP, WireGuard, SSH, UDP/3480, and NNTP are now active and mechanically audit-proven; fresh audit `20260718_180152-routeros-qos-contract` returned overall PASS with exact coverage at #15/#35/#36/#37/#38 before default #39. Generic RTP, WireGuard, and SSH have natural traffic proof; UDP/3480 and NNTP immediate counters are `0/0`, so natural proof is deferred without synthetic probes. Evidence: `../infra-ansible/artifacts/network-changes/20260717_routeros-qos-composite-policy/live-canary-result-wireguard-20260718T135914Z.md`, `../infra-ansible/artifacts/network-changes/20260717_routeros-qos-composite-policy/wireguard-natural-counter-proof-20260718T151235Z.md`, `../infra-ansible/artifacts/network-changes/20260717_routeros-qos-composite-policy/live-canary-result-ssh-20260718T155557Z.md`, `../infra-ansible/artifacts/network-changes/20260717_routeros-qos-composite-policy/live-canary-result-realtime-udp-3480-20260718T174527Z.md`, and `../infra-ansible/artifacts/network-changes/20260717_routeros-qos-composite-policy/live-canary-result-nntp-20260718T180241Z.md`. Application equivalence is proven. Spectrum and ATT bridge duplicate retirement are live-verified at final staged hash `e1063434...03d8`; bounded natural deltas moved all four tins on both WANs with zero new drops/backlog. Evidence: `../infra-ansible/artifacts/network-changes/20260717_routeros-qos-composite-policy/live-canary-result-spectrum-bridge-retirement-20260718T183654Z.md` and `../infra-ansible/artifacts/network-changes/20260717_routeros-qos-composite-policy/live-canary-result-att-bridge-retirement-20260718T190353Z.md`. The first approved AF31 convergence attempt reached exact target `a6b85d55...04884` and passed structural, audit, preflight, service, health, DNS, and HTTPS checks, but a natural 15-second observation found concurrent Spectrum Bulk saturation with `11,979` drops and `337,644` bytes ending backlog. Per the approved zero-drop/backlog acceptance, exact rollback restored healthy baseline `e1063434...03d8`; evidence: `../infra-ansible/artifacts/network-changes/20260717_routeros-qos-composite-policy/live-attempt-result-af31-convergence-rollback-20260718T201849Z.md`. A fresh independently reviewed v2 package added a mandatory three-window uncongested precondition and load-aware CAKE continuity while retaining exact rollback for structural, audit, service, health, DNS, HTTPS, or qdisc disagreement. The approved v2 reload reached and independently verified final live hash `a6b85d55...04884`, exact one-per-WAN AF31 imports, immutable baseline backup, RouterOS audit overall PASS, wanctl `25/25`, healthy service/endpoints, both resolvers, HTTPS, exact CAKE handles/`diffserv4`/four tins, monotonic counters, and zero ending backlog. Evidence: `../infra-ansible/artifacts/network-changes/20260717_routeros-qos-composite-policy/live-canary-result-af31-convergence-v2-20260718T220448Z.md`.
- [x] **REQ-004** — Adaptive WAN steering is selected independently from QoS priority, applies only to eligible new connections, and does not move recursive DNS merely because DNS is high priority. (milestone: v1.61)
  Evidence: `src/wanctl/steering/daemon.py::reconcile_steering_rule`, `tests/steering/test_steering_daemon.py`, `docs/QOS_CLASSIFICATION_CONTRACT.md`, and `../infra-ansible/artifacts/network-changes/20260717_routeros-qos-composite-policy/live-canary-result.txt`. The broad `QOS_HIGH` selector is retired; the exact Work-VPN/new-connection producer is controller-owned and DNS-safe.
- [x] **REQ-005** — The effective RouterOS QoS and steering policy has a version-controlled, read-only audit surface that detects ordering, FastTrack, DSCP-map, per-application equivalence, and steering-eligibility drift. (milestone: v1.61)
  Evidence: `../infra-ansible/scripts/routeros-qos-contract-audit.py`, `../infra-ansible/tests/test_routeros_qos_contract_audit.py`, `../infra-ansible/tests/test_routeros_qos_composite_policy.py`, live `make routeros-qos-contract-audit` 2026-07-17.
- [x] **REQ-006** — A reversible live canary under controlled bulk load proves DNS responsiveness, work-VPN reachability, expected CAKE tin counters, both-WAN behavior, and successful rollback. (milestone: v1.61)
  Evidence: `../infra-ansible/artifacts/network-changes/20260717_routeros-qos-composite-policy/live-canary-result.txt`. The corrected canary passed bounded both-WAN load, the real FortiVPN reconnect, DNS probes, expected CAKE counters, approval-gated demigration, and approval-gated remigration to the DNS-safe adaptive layout without clearing conntrack.

### SAFE-24 — Production QoS convergence

- [x] **SAFE-24** — Every production mutation requires a fresh exact rollback anchor and explicit operator approval; unrelated CAKE rates, autorate thresholds, route ownership, NAT, and topology changes remain out of scope. (milestone: v1.61)

- Repo-only docs, tests, audits, and undeployed rules are permitted without a live gate.
- RouterOS mangle, nftables deployment, qdisc changes, steering activation, service restarts, and controlled saturation are production mutations requiring an exact rollback anchor and explicit operator approval.
- CAKE rates, autorate thresholds, route ownership, NAT, and the split-edge topology are outside this milestone unless separately approved.

### Out of scope

- Moving NAT/routing to Linux or replacing the split edge with a DIY router.
- Claiming per-LAN-host CAKE fairness while NAT remains on a different host.
- Application-layer inspection or broad port-list expansion on cake-shaper.
- CAKE rate or controller-threshold tuning.

---
