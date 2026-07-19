# Traceability — wanctl

Most recent milestone first. Generated per the /saga-verify process.

---

## Traceability — Milestone v1.61 QoS Classification Contract

**Date:** 2026-07-18
**Mode:** saga
**Scope:** REQ-001 through REQ-006; SAFE-24
**Verifier:** independent frontier close-out (auditor had no live production access; repo/test evidence reproduced locally, live evidence verified by artifact inspection)

| Requirement | Description | Status | Evidence |
|-------------|-------------|--------|----------|
| REQ-001 | Operator-facing split-classifier contract (ownership, trust boundaries, EF/AF31/CS0/CS1 map, rejected alternatives, rollback) | **PROVEN** | `docs/QOS_CLASSIFICATION_CONTRACT.md` (present, updated 2026-07-18 to "Current implementation status"); `.planning/decisions/2703-routeros-classifies-cake-enforces.md`; `.planning/CONTEXT.md`. Repo artifact — directly inspectable. |
| REQ-002 | Symmetric AF31 upload import seeds bridge conn-mark → CAKE Video restore on both WANs | **PROVEN** | `deploy/nftables/bridge-qos.nft` L46 (`spectrum_ul`) + L52 (`att_ul`): `ip dscp af31 ct mark set 0x2 accept`. Test `tests/test_bridge_qos_nft.py::test_router_dscp_classification_is_propagated_to_download_replies` reproduced GREEN by auditor. Full `make ci` recorded 2026-07-17. |
| REQ-003 | Symmetric four-class enforcement, Best-Effort fallback, and duplicate bridge classifier retirement **only after** equivalence proven | **PROVEN** | **Repo side (auditor-reproduced):** `bridge-qos.nft` `spectrum_dl`/`att_dl` retire generic RTP 16384-32767, TCP/22, NNTP/119, narrow UDP/3478-3480→3478-3479, and drop WireGuard 51820; guard test `test_download_chains_retire_routeros_equivalent_application_fallbacks` + full nft suite = **6 passed** locally. **Live side (artifact-verified):** equivalence for all five RouterOS selectors was proven (contract audit overall PASS, coverage #15/#35/#36/#37/#38 before default #39) **before** any bridge duplicate was removed — correct causal order. Retirement then executed Spectrum-first (`649bd585→12300940`) then ATT (`12300940→e1063434`), each with immutable 0444 root:root rollback backup and audit PASS. AF31 convergence v1 rolled back cleanly on an over-strict zero-drop postcheck vs unrelated Spectrum Bulk saturation; load-aware v2 reached final `e1063434→a6b85d55`, one AF31 import/WAN, audit PASS, wanctl 25/25, health/DNS/HTTPS PASS, CAKE handles/`diffserv4`/four-tin continuity, zero backlog. **Hash lineage is continuous across all four canaries.** Evidence: `../infra-ansible/artifacts/network-changes/20260717_routeros-qos-composite-policy/{live-canary-result-spectrum-bridge-retirement-20260718T183654Z,live-canary-result-att-bridge-retirement-20260718T190353Z,live-attempt-result-af31-convergence-rollback-20260718T201849Z,live-canary-result-af31-convergence-v2-20260718T220448Z}.md`. **Caveat:** generic RTP, WireGuard, SSH have natural-traffic counter proof; UDP/3480 and NNTP immediate counters are `0/0` (natural confirmation deferred, no synthetic probes) — equivalence itself is audit/structural-proven, so this does not block the requirement. |
| REQ-004 | QoS-independent, new-connection-only steering eligibility; DNS not moved by priority | **PROVEN** | `src/wanctl/steering/daemon.py::reconcile_steering_rule`; `tests/steering/test_steering_daemon.py` (in 283-test suite reproduced GREEN by auditor); `docs/QOS_CLASSIFICATION_CONTRACT.md`; live `../infra-ansible/.../live-canary-result.txt`. Broad `QOS_HIGH` route retired; exact Work-VPN/new-connection producer controller-owned and DNS-safe. |
| REQ-005 | Read-only effective-policy audit surface (order, FastTrack, DSCP map, per-app equivalence, steering drift) | **PROVEN** | `../infra-ansible/scripts/routeros-qos-contract-audit.py`; `../infra-ansible/tests/{test_routeros_qos_contract_audit,test_routeros_qos_composite_policy}.py` reproduced GREEN by auditor = **24 passed**. Audit identifies the true catch-all and rejects terminal selectors shadowed by earlier conflicting conn-mark producers. |
| REQ-006 | Reversible live canary under controlled bulk load (DNS, work-VPN, CAKE counters, both-WAN, rollback) | **PROVEN** | `../infra-ansible/.../live-canary-result.txt`: corrected canary + real FortiVPN reconnect + bounded both-WAN load; approval-gated demigration/remigration exercised; 50/50 DNS per resolver; no conntrack cleared. Artifact-verified. |
| SAFE-24 | Production mutation gate (exact anchor + explicit approval per mutation) | **PROVEN** | Every live mutation in the milestone used a fresh read-only anchor, exact hash+token gate, immutable backup, and explicit per-attempt operator approval. Fail-closed behavior demonstrated live: slice 23 blocked when the anchor drifted; AF31 v1 rolled back on postcheck disagreement. Consistent across all canary artifacts. |

**Summary:** REQ-001, REQ-002, REQ-003, REQ-004, REQ-005, REQ-006 all **PROVEN**; SAFE-24 gate **PROVEN**.
**Counts (REQ-001..006):** PROVEN 6 / ASSERTED 0 / OPEN 0.
**Auditor scope note:** repo-side and test-side evidence was independently re-executed and passed; live-production evidence (RouterOS audit captures, wanctl preflights, CAKE counters, live nft hashes) was verified by inspecting the executing model's artifacts — the auditor did not (and per scope should not) touch production. The continuous hash lineage and internally consistent artifact set make the live claims high-confidence but not auditor-re-executed.

---
