---
saga_state_version: 1.0
milestone: v1.61
milestone_name: qos_classification_contract
status: active
stopped_at: REQ-003
last_updated: "2026-07-17T14:29:23-05:00"
last_activity: "v1.61 REQ-003 retirement blocked before commit — live per-application class equivalence is not proven; attempted bridge-only removal reverted; production and repo rules unchanged"
---

## v1.60 Shipped 2026-07-05

Three work items completed, 5/5 PROVEN in TRACEABILITY.md:

1. **SEED-007 (Storage hygiene):** wanctl_state fire-on-change — 95% row reduction verified live (`31e82d8d`).
2. **SEED-006 (Silicom bypass):** Phase B completed, 7 scenarios + orchestrator deployed (`acaaeadd`).
3. **steering-degraded-on-clean-restart:** Phase 224 fix verified via live restart — SPECTRUM_GOOD immediately (`dccca17b`).

Decision record: `decisions/2702-saga-mode-for-ops-work.md`

### Active Work

- **v1.61 / REQ-001–REQ-002 (repo-only): COMPLETE.** Contract recorded and AF31 import added on both WAN upload chains. TDD evidence: expected RED failure, targeted GREEN (`1 passed`), bridge-QoS suite (`4 passed`), namespace nft syntax check (`NFT_SYNTAX_OK`), and full `make ci` (`5,758 passed`, 90.17% coverage). Production unchanged.
- **REQ-003 contract-proof slice (repo-only): COMPLETE.** Exact EF/AF31/CS1 import parity, Voice/Video/Bulk restore parity, carrier wash, and unmatched-CS0 Best Effort fallback are mechanically asserted on both WANs. Evidence: bridge suite `5 passed`, namespace `NFT_SYNTAX_OK`, full `make ci` (`5,759 passed`, 90.17% coverage). No fallback classifier was removed; REQ-003 remains open for safe retirement work.
- **REQ-005 read-only audit: COMPLETE.** `infra-ansible/scripts/routeros-qos-contract-audit.py` checks FastTrack, the EF/AF31/CS1/CS0 map, wash-before-trust ordering, and steering eligibility through the vaulted `ai-readonly` wrapper. Tests: `6 passed`; infra-ansible `make ci`: `32 passed`; live run: three PASS plus one WARN for the retained disabled `QOS_HIGH` adaptive route; strict mode exited nonzero. RouterOS unchanged.
- **REQ-003 retirement checkpoint: BLOCKED.** A bridge-only retirement passed structural tests and nft syntax, but final equivalence review against the live RouterOS capture disproved the prerequisite. The RouterOS class map exists, but it does not prove the same application treatment: generic RTP `16384-32767` and WireGuard `51820` lack equivalent `QOS_HIGH` producers, SSH `22` is `QOS_MEDIUM` rather than the bridge's EF treatment, UDP `3480` is outside the high realtime rule, and NNTP `119` lacks the bridge's Bulk equivalent. The attempted repo diff was reverted before commit; no classifier was removed or deployed.
- **Next bounded slice — REQ-004 prerequisite (repo-only):** define and test an undeployed RouterOS policy artifact that separates steering eligibility from QoS and closes the class-equivalence gaps above. Do not retire bridge exceptions or mutate RouterOS until the audit proves exact per-application coverage.
- **Live checkpoint — REQ-006:** blocked by SAFE-24 until an immutable rollback anchor, one-WAN canary procedure, and explicit operator approval exist.

- **t_bfe1e19b (C901 refactor):** Done — `_run_logging_metrics` extracted into 6 private helpers. Complexity 17→below threshold. Commit `cd777d91`.

### Deferred (post-ROLE-01)

- **FLIP-02 (fping/native keep canary):** Closed as moot. Native Python controller retiring; cake-autorate already uses fping. Code remains available if needed.
- **TIN-SPARSE-01 (CAKE tin skip-on-unchanged):** Deferred. Consumer audit found raw-history semantics in `wanctl-history --tins`. Revisit after ROLE-01 — only state-bridge remains as consumer.
- **IRTT-MIG-01 (IRTT first-class backend):** Deferred. Dead stub (`NotImplementedError`). No value while cake-autorate handles RTT measurement natively. Remove or implement post-ROLE-01.
- **RECLAIM-04 (Spectrum upload reclaim):** Closed — no action needed. Actual demand ~22 Mbps < 30 Mbps floor (73% utilization). Lowering floor tightens the queue, hurts latency. Raising ceiling to 40 Mbps is cosmetic (never approached). Current config optimal for observed workload.
- **ROLE-01 (native-controller retirement):** Rollback drill completed 2026-07-09 (PASS — native wanctl@att started, ran healthy, stopped, cake-autorate resumed cleanly). Remaining gate: >=14 consecutive stable cake-autorate days (~Jul 19 target).

### Deferred

None

### Completed

- **SEED-010 (Silicom test harness validation):** All 7 scenarios tested live 2026-07-09. Fixed 3 bugs: `set_dis_disc off` before disconnect (`silicom-bypass`), `shift` in `cmd_chaos` (`silicom-test`), `--both-wan-confirm` for dual-WAN loss. Commit `e2b0e6f3`.

### Key State

- 6 routes managed, guard ok, 0 conflicts
- Both failover bridges armed
- Steering daemon: healthy, SPECTRUM_GOOD
- Spectrum UL: floor 30 Mbps, ceiling 36 Mbps (soak complete — no changes)
- cake-autorate active rate controller (since 2026-07-05)
- State-bridge downsampling: raw→1m every 15 min (commit `5c410373`)
