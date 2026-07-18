---
saga_state_version: 1.0
milestone: v1.61
milestone_name: qos_classification_contract
status: active
stopped_at: REQ-003 renewed approval gate for corrected fresh-session classifier canary
last_updated: "2026-07-17T21:11:20-05:00"
last_activity: "generic RTP canary failed audit and rolled back exactly; fresh-session ordering repair passed CI and independent review"
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
- **REQ-005 read-only audit: COMPLETE.** `infra-ansible/scripts/routeros-qos-contract-audit.py` checks FastTrack, the EF/AF31/CS1/CS0 map, wash-before-trust ordering, per-application class equivalence, multiword RouterOS fields, and same-chain composite producer/consumer safety. Audit tests: `15 passed`; policy tests: `3 passed`; canary tests: `6 passed`; full infra-ansible suite: `50 passed`; `make ci`, Ruff, compilation, JSON validation, and Ansible syntax all pass. Post-rollback live audit still reports the five expected application-equivalence gaps and retained legacy-route warning.
- **REQ-003 retirement checkpoint: BLOCKED and now mechanically gated.** The audit reports generic RTP `16384-32767`, WireGuard `51820`, SSH `22`, UDP `3480`, and NNTP `119` as exact live coverage gaps. A producer counts only when it is enabled, same-class, new-connection-only, terminal, and reachable before the default classifier. No bridge classifier was removed or deployed.
- **REQ-004 package prerequisite: COMPLETE.** `infra-ansible/artifacts/network-changes/20260717_routeros-qos-composite-policy/` defines `QOS_HIGH_ATT` as an inspectable composite of EF queue intent and sticky ATT affinity, restricts assignment to explicit new-connection producers, keeps DNS on plain `QOS_HIGH`, removes the broad legacy route in the proposed full-policy state, and includes an approval-gated bounded Work-VPN canary with exact rollback.
- **Work-VPN composite-mark canary package: LIVE ATTEMPT FAILED SAFELY.** Exact preflight passed and apply reached `state=canary`, but a new TCP connection to the Work-VPN endpoint timed out over `to_ATT`. The producer was restored immediately, active `QOS_HIGH_ATT` connections drained to zero, compatibility rules were removed, and status returned to `baseline`. Both internal resolvers and endpoint TCP/443 passed after rollback; cake-shaper QoS/autorate services remained active.
- **Live checkpoint — REQ-006:** corrected reapply remains active. A download-only Spectrum speedtest transferred 163,662,768 bytes at 130.67 Mbit/s while the actual FortiVPN session remained assured/reply-seen as `QOS_HIGH_ATT` through ATT. Both resolvers passed 40/40 uncached probes, Spectrum connections demoted to `QOS_LOW`, Spectrum Bulk and ATT Voice counters increased, and all QoS/autorate services stayed active.
- **REQ-004/REQ-006 DNS-safe adaptive convergence: COMPLETE.** The broad `QOS_HIGH` route is retired and replaced by exact `ADAPTIVE: Work VPN eligible for ATT` selection for eligible new Work-VPN connections. Live verification exposed and fixed startup logical/rule-state drift; full wanctl CI passed (`5,766 passed`, 90.14%), independent Claude review passed, and the reviewed daemon module was deployed with matching SHA-256. Controller restart disabled and verified the exact producer under `SPECTRUM_GOOD`. Approval-gated demigration and remigration passed without clearing conntrack; both resolvers passed 50/50 final probes; all QoS/autorate services and steering health remained active.
- **Adaptive status gate repair (repo-only): COMPLETE.** Reproduced the stale `canary-active-corrected-verified` assertion, updated it to the live `adaptive-active-corrected-verified` state, and added a direct assertion for `bounded_adaptive_migration_status=live-verified`. Focused test passed; full infra `make ci` passed with 58 tests. No live mutation or policy behavior change.
- **REQ-003 slice 1 — generic RTP migration package (repo-only): COMPLETE.** Added the exact new/unmarked UDP `16384-32767 -> QOS_HIGH` producer, immediate pre-default ordering, read-only status, a counter-insensitive live mangle SHA-256 mutation anchor, distinct confirmations, duplicate/drift checks, failed-move cleanup, idempotent rollback, Ansible wrapper, and operator procedure. Focused suite: `12 passed`; full infra `make ci`: `70 passed`. Independent Claude review passed after one repair cycle. Infra commit `359305a`. No live command, classifier retirement, or conntrack clear occurred.
- **REQ-003 slice 2 — finite classifier registry (repo-only): COMPLETE.** Extended the proven canary machinery behind an explicit five-selector registry covering generic RTP, WireGuard `51820`, SSH `22`, UDP `3480`, and NNTP `119`. Every selector is mechanically bound to `policy.json`, uses new/unmarked exact rules and selector-specific confirmations, converges into one canonical block before the default regardless of apply order, stages disabled until placement succeeds, cleans up on placement/enable failure, and retains fresh-hash gating plus read-only default status. Focused suite: `20 passed`; full infra `make ci`: `78 passed`. Independent Claude review passed after one repair cycle. No live command, classifier retirement, or conntrack clear occurred.
- **REQ-003 slice 3 — live read-only approval packet: COMPLETE / STOPPED AT MUTATION GATE.** Fresh status for all five finite selectors returned `state=baseline`, `changed=false`, and the same current mangle anchor `f59a7c9a2352bc965a5d31c36072d6a34d2f78d96e2269c237d8262216bf7123`. Fresh contract audit capture `20260718_012433-routeros-qos-contract` passed FastTrack, DSCP map, wash/trust ordering, and steering eligibility while reporting the exact five expected application-equivalence gaps. No RouterOS mutation, conntrack clear, service restart, or bridge retirement occurred. Next action requires explicit production approval for the bounded per-selector applies.
- **REQ-003 slice 4 — generic-RTP live canary: FAILED SAFELY / CORRECTION REVIEWED / RENEWED APPROVAL REQUIRED.** The approved generic-RTP apply returned `applied`, but a fresh independent audit found the enabled rule after the terminal default and therefore unreachable. Remaining applies froze immediately. Exact rollback with the fresh post-change anchor restored `baseline` and the original full mangle hash; both resolvers, six shaping/bridge/steering units, steering health, router reachability, route guard, and the original five-gap audit state passed. No conntrack clear occurred. Root cause: the mutating API session's order readback did not match a subsequent fresh connection. Infra commit `f0d71e3` now closes the mutation session, requires fresh-session target/order proof, and exactly removes the new row on fresh-session failure; focused suite `22 passed`, full infra CI `80 passed`, independent Claude second-pass review `PASS`. Corrected live reapply is stopped at renewed explicit approval.

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
