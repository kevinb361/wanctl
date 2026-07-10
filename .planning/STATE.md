---
gsd_state_version: 1.0
milestone: none
milestone_name: between_milestones
status: between_milestones
stopped_at: none
last_updated: "2026-07-09T08:00:00-05:00"
last_activity: "Backlog triage complete — RECLAIM-04 closed, FLIP-02/TIN-SPARSE/IRTT-MIG deferred post-ROLE-01, rollback drill done"
---

## v1.60 Shipped 2026-07-05

Three work items completed, 5/5 PROVEN in TRACEABILITY.md:

1. **SEED-007 (Storage hygiene):** wanctl_state fire-on-change — 95% row reduction verified live (`31e82d8d`).
2. **SEED-006 (Silicom bypass):** Phase B completed, 7 scenarios + orchestrator deployed (`acaaeadd`).
3. **steering-degraded-on-clean-restart:** Phase 224 fix verified via live restart — SPECTRUM_GOOD immediately (`dccca17b`).

Decision record: `decisions/2702-saga-mode-for-ops-work.md`

### Active Work

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
