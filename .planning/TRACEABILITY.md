# Traceability — wanctl

Most recent milestone first. Generated per the /saga-verify process.

---

## Traceability — Milestone v1.61 QoS Classification Contract

**Date:** 2026-07-17
**Mode:** saga
**Scope:** REQ-001 through REQ-006; SAFE-24

| Requirement | Description | Status | Evidence |
|-------------|-------------|--------|----------|
| REQ-001 | Operator-facing split-classifier contract | **PROVEN** | `docs/QOS_CLASSIFICATION_CONTRACT.md`; `.planning/CONTEXT.md`; `.planning/decisions/2703-routeros-classifies-cake-enforces.md` |
| REQ-002 | Symmetric AF31 import and reply restoration | **PROVEN** | `deploy/nftables/bridge-qos.nft`; `tests/test_bridge_qos_nft.py::test_router_dscp_classification_is_propagated_to_download_replies`; RED then GREEN; full `make ci` evidence |
| REQ-003 | Symmetric four-class enforcement and safe duplicate retirement | **OPEN** | Contract import/restore and CS0 fallback are proven, but fresh live audit `../infra-ansible/artifacts/network-changes/20260717_routeros-qos-composite-policy/live-audit-result.txt` mechanically fails exact coverage for generic RTP `16384-32767`, WireGuard `51820`, SSH class, UDP `3480`, and NNTP `119`. No classifier was removed or deployed. |
| REQ-004 | QoS-independent, new-connection steering eligibility | **OPEN** | Proposal-only `../infra-ansible/artifacts/network-changes/20260717_routeros-qos-composite-policy/policy.json`, `README.md`, and `rollback.rsc`; `../infra-ansible/tests/test_routeros_qos_composite_policy.py` (`3 passed`) and composite audit tests prove the model, but RouterOS has not been mutated and the disabled broad `QOS_HIGH` route remains live. |
| REQ-005 | Read-only effective-policy audit surface | **PROVEN** | `../infra-ansible/scripts/routeros-qos-contract-audit.py`; audit tests (`10 passed`); policy tests (`3 passed`); infra-ansible `make ci` (`39 passed`); fresh live vaulted read-only run correctly returned FAIL for all five application gaps and WARN for the retained disabled broad route. |
| REQ-006 | Reversible controlled live canary | **OPEN** | No v1.61 canary or rollback drill has run; SAFE-24 blocks implicit deployment. |
| SAFE-24 | Production mutation gate | **PROVEN** | Repo-only audit, tests, policy model, and rollback artifact; no deploy, restart, RouterOS mutation, qdisc change, or controlled saturation occurred. |

**Summary:** REQ-001, REQ-002, and REQ-005 PROVEN; REQ-003, REQ-004, and REQ-006 OPEN; SAFE-24 PROVEN. Production unchanged.

---

## Traceability — Milestone v1.60 Ops Consolidation

**Date:** 2026-07-05
**Mode:** saga (no formal REQ-IDs; work items from STATE.md)
**Scope:** Storage hygiene, Silicom bypass tooling, steering clean-restart

---

### Work Item Traceability

| WI-ID | Description | Status | Evidence |
|-------|-------------|--------|----------|
| SEED-007-A | wanctl_state fire-on-change emission | PROVEN | Commit `31e82d8d`; tests `test_state_metric_fire_on_change_skips_unchanged_dl` + `test_state_metric_emits_on_transition` in `tests/test_wan_controller.py`; live verification 95% row reduction (58/30878 in 60s); both `wanctl@spectrum` and `wanctl@att` restarted, healthy |
| SEED-006-A | Silicom bypass Phase A (CLI + watchdog + boot-init) | PROVEN | Deployed since v1.45; CLI `/usr/local/sbin/silicom-bypass` (15209 bytes); systemd units `bpctl-silicom.service`, `silicom-bypass-init.service`, `silicom-bypass-watchdog@.service` enabled; live status `bypass=on` for both pairs |
| SEED-006-B | Silicom bypass Phase B (test harness scenarios) | PROVEN | Commit `acaaeadd`; 7 scenarios deployed to `/usr/local/share/silicom-test-scenarios/`; orchestrator `/usr/local/sbin/silicom-test` on cake-shaper; `deploy.sh` updated to glob `*.sh` |
| steering-restart | steering-degraded-on-clean-restart investigation | PROVEN | Phase 224 fix shipped June 3 (`dccca17b`); grace period mechanism live in `src/wanctl/steering/daemon.py` (`is_wan_grace_period_active`); live restart 2026-07-05 14:57 — came up `SPECTRUM_GOOD` immediately; todo moved to completed |
| ops-mode | saga-mode decision for v1.60 | PROVEN | Decision record `.planning/decisions/2702-saga-mode-for-ops-work.md` — rationale: ops changes are 1-3 commits, low blast radius, no multi-phase execution needed |

### Gaps

**ASSERTED:** None — every work item has a concrete evidence artifact.

**OPEN:** None — all three STATE.md items completed.

**WAIVED:** None.

### Notes

- No formal REQ-IDs for v1.60 (saga mode). Work items tracked in STATE.md.
- Previous milestone (v1.58) requirements remain unverified in this pass — those are shipped and archived. A separate `/saga-verify` run on v1.58 would map REQ-IDs to evidence.
- UL rate soak (floor 30, ceiling 36 Mbps) is deferred — not a v1.60 work item, tracked separately in STATE.md deferred section.

---

## Traceability — Milestone v1.58 Active Route-Management Canary

**Date:** 2026-07-09
**Mode:** saga (REQ-IDs from `.planning/REQUIREMENTS.md`)
**Scope:** v1.58 Requirements (Phases 261–264) — 17 REQ-IDs + 1 cross-cutting invariant (SAFE-22)
**Source of truth:** `.planning/REQUIREMENTS.md` (v1.58 section)

---

### Requirements Traceability

| REQ-ID | Description | Status | Evidence |
|--------|-------------|--------|----------|
| RECON-01 | Full `deploy.sh` to `cake-shaper` with sha256 audit proving repo==prod | PROVEN | Commit `c375ce3c` (sha256 audit scripts); commit `6683d5e8` (deploy reconcile evidence); `phase261-sha256-manifest-repo.txt` and `phase261-sha256-manifest-prod.txt` in `.planning/milestones/v1.58-phases/261-pre-flip-deploy-reconciliation/evidence/`; per-file SHA256 comparison showed all files identical |
| RECON-02 | Pre-deploy rollback anchor captured with proven restore path | PROVEN | `.planning/milestones/v1.58-phases/261-pre-flip-deploy-reconciliation/evidence/phase261-rollback-anchor.md`: tarball `opt-wanctl.tgz` with SHA256 `28c25d4...`, scratch restore drill PASS (`PHASE261_RESTORE_DRILL_PASS`), full write-set coverage table classifying every deploy path, one-command code revert and host-config revert documented |
| RECON-03 | Post-deploy route-management surface and `:9102` health clean in dry-run/safe state | PROVEN | Commit `6683d5e8` (deploy reconcile evidence + no-restart gate + sha256 audit); Phase 261 roadmap entry confirms 3/3 plans satisfied; `mode=dry_run`, `active_owner=netwatch` confirmed post-deploy |
| APPROVE-01 | Phase 260 `ready-for-approval` packet + entry-gate status presented as decision artifact | PROVEN | `.planning/milestones/v1.58-phases/263-operator-approval-soak-gate/APPROVAL.md`: all 8 criteria pass from Phase 260 readiness packet (ownership inspector authoritative, reconciliation ok, circuit breaker closed, REST read-only inventory succeeded, rollback anchors current, etc.) |
| APPROVE-02 | No ownership flip without recorded explicit operator approval (who/when) | PROVEN | `APPROVAL.md`: "Operator: Kevin, Date: 2026-06-29"; commit `fa2dc5cb` records the approval in git history; `ready-for-approval` treated as verdict, NOT approval (per D-10/SAFE-21) |
| APPROVE-03 | ≥14-consecutive-stable-cake-autorate-days soak gate machine-verified at execution; failing gate blocks flip | ASSERTED | `APPROVAL.md`: soak gate measured (Spectrum 9.3d, ATT 11.5d, threshold 14d — NOT MET) and explicitly waived by operator. The machine-verification ran and produced a result, but the gate was waived rather than passed. No separate test or script verifying the ≥14-day count independently of the approval document exists in the repo. |
| OWNFLIP-01 | Operator can flip single canary route from Netwatch to wanctl via guarded, gated command | PROVEN | `.planning/milestones/v1.58-phases/264-live-flip/evidence/flip-evidence.md`: steps executed — disabled 3 Netwatch entries, verified guard cleared, set mode to `active`, sent SIGUSR1 to steering PID 980521, verified mode transition; commit `bf8299ad` (live flip success + final evidence) |
| OWNFLIP-02 | Netwatch demoted disabled-but-retained; one-command re-enable restores prior ownership | PROVEN | `flip-evidence.md`: all 3 Netwatch entries disabled via REST PATCH (*4 and *5), *1 already disabled; config preserved, not deleted; rollback path documented: `/tool netwatch set [.id] disabled=no` for each entry |
| OWNFLIP-03 | After flip, wanctl is sole active owner of canary route with no dual-ownership route flap | PROVEN | `flip-evidence.md` post-flip state: `active_owner=wanctl`, `active_allowed=True`, `guard_status=ok`, `conflict_count=0`, `circuit_open=False`, `status=healthy`; zero aborts, zero errors in journal post-flip |
| OWNFLIP-04 | Flip bounded to exactly one canary route — no other route or WAN ownership changes | PROVEN | `flip-evidence.md`: canary route identified as ATT (distance 2, gateway 192.168.2.254); ROADMAP.md Phase 264 explicitly scoped to "single canary route"; SAFE-22 forbids any ownership flip beyond one canary route; Spectrum primary at distance 1 unaffected |
| ABORT-01 | Rollback drill (flip → revert to Netwatch) exercised and proven before live canary flip | PROVEN | `.planning/milestones/v1.58-phases/262-abort-scaffolding-rollback-drill/evidence/phase262-rollback-drill-evidence.md`: drill executed — pre: `mode=active`, trigger: config change + SIGUSR1 to PID 952841, post: `mode=dry_run`, `active_owner=netwatch`; all 8 verification checkboxes pass; 4 bugs fixed during drill execution |
| ABORT-02 | Circuit-breaker/guard automatically reverts canary route to Netwatch on defined trip conditions | PROVEN | `.planning/milestones/v1.58-phases/262-abort-scaffolding-rollback-drill/VERIFICATION.md`: `abort_to_netwatch()` in `route_manager.py` (re-enables routes, sets dry_run, resets circuit breaker, records event); `_check_route_abort()` in `daemon.py` with 3 trip conditions (circuit breaker open, router unreachable, Netwatch contention); commit `aee7ce76` (abort-to-Netwatch scaffolding) |
| ABORT-03 | Auto-abort trips and revert are observable/recorded (operator can see what tripped and that revert completed) | PROVEN | `VERIFICATION.md`: `last_abort` in /health endpoint (trip_condition, mode_before, mode_after, timestamp); `last_event` with full abort details including `route_revert_results`; `circuit_breaker.reset_called` in status_snapshot; `phase262-rollback-drill-evidence.md` shows JSON output from health endpoint with complete abort record |
| ABORT-04 | Operator retains manual one-command rollback independent of automatic path | PROVEN | `VERIFICATION.md`: manual rollback via SIGUSR1 to steering process (config change `mode: active -> dry_run` + signal triggers `_reload_route_management_config` → `_handle_mode_change` → `abort_to_netwatch("manual_rollback")`); rollback script deployed at `/opt/scripts/phase262-rollback.sh` via `deploy.sh` (commit `6c125193`) |
| FLIPOBS-01 | `:9102` route-management health surface asserts owner/mode/guard fields transition cleanly through flip and revert | PROVEN | `flip-evidence.md`: pre-flip (`mode=dry_run`, `active_owner=netwatch`, `guard_status=conflict`); post-flip (`mode=active`, `active_owner=wanctl`, `guard_status=ok`); `phase262-rollback-drill-evidence.md`: revert shows `mode=dry_run`, `active_owner=netwatch` with `last_abort.trip_condition=manual_rollback` |
| FLIPOBS-02 | Health distinctly shows Netwatch-demoted state vs wanctl-active-owner state — no ambiguity | PROVEN | `flip-evidence.md`: `active_owner` field switches from `netwatch` to `wanctl`; `active_allowed` from `False` (guard conflict) to `True`; `observed_owner=netwatch` pre-flip, `active_owner=wanctl` post-flip — unambiguous ownership attribution |
| FLIPOBS-03 | No payload-shape regression on `:9101` (bridge) or `:9102` (steering) health from canary work | ASSERTED | `flip-evidence.md` notes "zero aborts, zero errors in journal" and `VERIFICATION.md` confirms health endpoint healthy post-drill, but no explicit before/after payload-shape diff or schema validation test exists in the repo. Health endpoint continued serving responses, which strongly suggests no regression, but this was not mechanically verified with a structured comparison. |
| SAFE-22 | Cross-cutting safety invariant: permitted mutations (single-route flip, auto-abort, deploy reconcile) only; forbidden (CAKE/qdisc, threshold retuning, Netwatch deletion, multi-route flip, controller-path source diff) | PROVEN | Commit `fa2dc5cb` ("SAFE-22: no controller-path diff"); `APPROVAL.md` checklist item "SAFE-22: no controller-path source diff" checked; SAFE-22 definition in REQUIREMENTS.md and ROADMAP.md; all commits in Phase 261–264 touch only route management, steering, and abort scaffolding — zero diffs in `wan_controller.py`, `queue_controller.py`, `cake_signal.py`, RTT backends, `alert_engine.py`, or fusion |

---

### Summary

**Total REQ-IDs:** 18 (17 requirements + 1 cross-cutting invariant)
**PROVEN:** 16
**ASSERTED:** 2
**OPEN:** 0
**WAIVED:** 0

---

### ASSERTED Set (requires attention)

These requirements have documentary evidence of being addressed during execution but lack a locatable mechanical artifact (test, script, or verifiable data capture) that would independently prove them:

- **APPROVE-03**: Soak gate (≥14 consecutive stable cake-autorate days) was measured at execution time and found NOT MET (Spectrum 9.3d, ATT 11.5d), then waived by operator. The measurement happened and was recorded in APPROVAL.md, but there is no standalone soak-gate verification script or cron log that independently proves the day counts. The waiver is well-documented, but the underlying measurement mechanism is not locatable as a reusable artifact.

- **FLIPOBS-03**: No payload-shape regression on `:9101` or `:9102` health endpoints. Health endpoints continued serving after the flip with no errors, but no before/after JSON diff or schema validation test was run. This is a reasonable assertion given the successful operation, but it was not mechanically verified.

---

### OPEN Set

None — all 18 REQ-IDs have been addressed during v1.58 execution (shipped 2026-06-29).

---

### WAIVED Set

None as standalone waivers. APPROVE-03 includes an embedded soak-gate waiver (the ≥14-day threshold was waived by operator), but the requirement itself is classified ASSERTED because the measurement was performed and recorded, just not passed.

---

### Notes

- v1.58 is shipped (2026-06-29). All phases (261–264) executed successfully.
- Evidence artifacts live under `.planning/milestones/v1.58-phases/` with subdirectories per phase.
- The v1.60 ops-consolidation section above is retained; this v1.58 pass was generated 2026-07-09 as a separate milestone section.
- Per saga-verify rules: `[x]` checkboxes with no locatable artifact are classified ASSERTED, never PROVEN.
- Controller-path source diff check for SAFE-22 verified by inspecting git commit range for Phase 261–264: no modifications to `wan_controller.py`, `queue_controller.py`, `cake_signal.py`, RTT backends, `alert_engine.py`, or fusion.
