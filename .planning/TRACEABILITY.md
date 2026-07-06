# Traceability — Milestone v1.60 Ops Consolidation

**Date:** 2026-07-05
**Mode:** saga (no formal REQ-IDs; work items from STATE.md)
**Scope:** Storage hygiene, Silicom bypass tooling, steering clean-restart

---

## Work Item Traceability

| WI-ID | Description | Status | Evidence |
|-------|-------------|--------|----------|
| SEED-007-A | wanctl_state fire-on-change emission | PROVEN | Commit `31e82d8d`; tests `test_state_metric_fire_on_change_skips_unchanged_dl` + `test_state_metric_emits_on_transition` in `tests/test_wan_controller.py`; live verification 95% row reduction (58/30878 in 60s); both `wanctl@spectrum` and `wanctl@att` restarted, healthy |
| SEED-006-A | Silicom bypass Phase A (CLI + watchdog + boot-init) | PROVEN | Deployed since v1.45; CLI `/usr/local/sbin/silicom-bypass` (15209 bytes); systemd units `bpctl-silicom.service`, `silicom-bypass-init.service`, `silicom-bypass-watchdog@.service` enabled; live status `bypass=on` for both pairs |
| SEED-006-B | Silicom bypass Phase B (test harness scenarios) | PROVEN | Commit `acaaeadd`; 7 scenarios deployed to `/usr/local/share/silicom-test-scenarios/`; orchestrator `/usr/local/sbin/silicom-test` on cake-shaper; `deploy.sh` updated to glob `*.sh` |
| steering-restart | steering-degraded-on-clean-restart investigation | PROVEN | Phase 224 fix shipped June 3 (`dccca17b`); grace period mechanism live in `src/wanctl/steering/daemon.py` (`is_wan_grace_period_active`); live restart 2026-07-05 14:57 — came up `SPECTRUM_GOOD` immediately; todo moved to completed |
| ops-mode | saga-mode decision for v1.60 | PROVEN | Decision record `.planning/decisions/2702-saga-mode-for-ops-work.md` — rationale: ops changes are 1-3 commits, low blast radius, no multi-phase execution needed |

## Gaps

**ASSERTED:** None — every work item has a concrete evidence artifact.

**OPEN:** None — all three STATE.md items completed.

**WAIVED:** None.

## Notes

- No formal REQ-IDs for v1.60 (saga mode). Work items tracked in STATE.md.
- Previous milestone (v1.58) requirements remain unverified in this pass — those are shipped and archived. A separate `/saga-verify` run on v1.58 would map REQ-IDs to evidence.
- UL rate soak (floor 30, ceiling 36 Mbps) is deferred — not a v1.60 work item, tracked separately in STATE.md deferred section.
