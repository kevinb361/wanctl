---
gsd_state_version: 1.0
milestone: v1.45
milestone_name: Flapping Peak-Counter Window Repair
current_phase: 210
current_plan: 3
status: ready_to_plan
stopped_at: Phase 210 complete (3/3) — ready to discuss Phase 211
last_updated: 2026-05-26T17:08:46.281Z
last_activity: 2026-05-26
progress:
  total_phases: 2
  completed_phases: 1
  total_plans: 3
  completed_plans: 3
  percent: 50
---

# Session State

## Project Reference

See: .planning/PROJECT.md (updated 2026-05-26 after v1.44 archive close + v1.45 milestone open)

**Core value:** Sub-second congestion detection with 50ms control loops, achieved through systematic performance optimization and code quality improvements while maintaining production reliability.
**Current focus:** Phase 211 — production verification & milestone closure

## Current Position

Phase: 210 (windowed-peak-accumulator-implementation) — EXECUTING
Plan: 3 of 3
**Last shipped milestone:** v1.44 Topology-Correct CAKE — Spectrum besteffort wash migration (shipped 2026-05-26; audit `passed` 16/16 after Phase 206 restamp)
**Recently archived:** v1.44 (2026-05-26), v1.43 (2026-05-13), v1.42 (2026-05-06), v1.41 (2026-05-06), v1.40 (2026-05-03)
**Active milestone:** v1.45 Flapping Peak-Counter Window Repair (roadmap drafted; planning)
**Current phase:** 211
**Current plan:** Not started
**Status:** Ready to plan
**Last activity:** 2026-05-26

Progress: [██████████] 100%

## Phase Structure (v1.45)

| Phase | Goal | REQ-IDs |
|-------|------|---------|
| 210 | Windowed peak accumulator implementation + tests + SAFE-10 enforcement at code level | ALERT-01, ALERT-02, TEST-01, TEST-02, TEST-03, SAFE-10 |
| 211 | Production verification: real flapping event reports `peak > flap_threshold`; SAFE-10 closeout | ALERT-03, VERIFY-01 |

**Split rationale:** VERIFY-01 is a production-gate that cannot be satisfied at PR-merge time. It requires a real production flapping event after deploy. Phase 211 makes this gate explicit (mirrors v1.44 Phase 209 production-canary pattern) rather than burying it as a milestone-close deferral. ALERT-03 (no-log-spam under sustained events) is paired into Phase 211 because end-to-end behavior is only verifiable in production.

## Cross-Cutting Invariants

**SAFE-10** verified at every phase boundary:

- Zero `src/wanctl/` source diff outside the alerting path between v1.44 close (`c9932d2` or equivalent) and v1.45 close
- Five-file SAFE-09 allowlist from v1.44 untouched: `linux_cake.py`, `netlink_cake.py`, `cake_params.py`, `cake_signal.py`, `check_config_validators.py`
- `alert_engine.py` semantics (cooldown_sec dedup) unchanged — only `wan_controller.py:4275-4360` flapping-detection block and version bump expected to diff

## Deferred Items (carried from v1.44 close)

Items acknowledged and deferred at v1.44 milestone close 2026-05-26. v1.45 scope is alerting-only and does not pull any of these forward.

| Category | Item | Status |
|----------|------|--------|
| debug_sessions | knowledge-base | unknown |
| threads | phase-196-queue-primary-refractory-semantics-investigation | in_progress |
| todos | 2026-04-08-investigate-tcp-12down-latency-spikes-under-multi-flow-downl | pending (tuning; reproduction matrix not re-run post-v1.40) |
| todos | 2026-04-15-profile-post-hotpath-baseline-on-production-wan | pending (rescoped to post-v1.44 baseline) |
| todos | 2026-04-17-investigate-steering-degraded-on-clean-restart | pending (low-pri; spot-checked GOOD on 2026-05-26) |
| todos | 2026-04-17-monitor-flapping-peak-count-on-next-docsis-event | **PROMOTED TO v1.45 SPINE** — confirmed bug, root cause located, Design Option A selected; will close when VERIFY-01 satisfied |
| todos | 2026-04-24-resolve-att-cake-primary-canary-after-phase-196 | pending (gated on Phase 191 closure) |
| seeds | SEED-003-v143-d14-watchdog-recalibration | dormant |
| seeds | SEED-004-v143-target-edge-churn-instrumentation | dormant |
| seeds | SEED-005-v143-conservative-ul-tuning-sweep | dormant |
| seeds | SEED-006-v145-silicom-bypass-tooling-and-harness | dormant (planted 2026-05-26) |
| seeds | SEED-007-v145-storage-hygiene-fire-on-change | dormant (planted 2026-05-26) |

**Note on SEED-006/007 naming:** Both seeds are named `v145-*` but are NOT consumed by the v1.45 milestone. v1.45 spine is the flapping-peak bug fix only. SEED-006/007 may be candidates for v1.46+ depending on operator scoping.

## Accumulated Context

### Roadmap Evolution

- 2026-05-26: v1.45 roadmap drafted with 2 phases (210, 211). All 8 v1.45 REQ-IDs mapped (ALERT-01..03, TEST-01..03, VERIFY-01, SAFE-10). Phase numbering continues from v1.44 (last phase 209). Spine: `2026-04-17-monitor-flapping-peak-count-on-next-docsis-event` confirmed-bug todo. Two-phase split made explicit because VERIFY-01 is a production-gate that cannot be satisfied at PR-merge time. SAFE-10 cross-cutting at every phase boundary (mirrors v1.44 SAFE-08/SAFE-09 mechanism).

### Key Design Decision (carried forward from REQUIREMENTS.md)

- **Design Option A** selected (per-direction windowed peak accumulator independent of deque-clear). Option B (rename payload to `transition_count_at_fire`) explicitly rejected because it would lose the intensity signal that motivated the metric in the first place. Decision ratified by Codex round-2 peer review 2026-05-26.

### Root Cause (carried forward from todo)

- `src/wanctl/wan_controller.py:4322-4323` (DL) and `:4353-4354` (UL): in-fire `deque.clear()` + `self._dl_peak_transitions = 0` (and UL equivalent) destroys window state at the exact moment the alert fires.
- `peak = max(peak, len(deque))` runs immediately before the fire check (line 4307 DL), so at fire-time `peak == len(deque) == flap_threshold == 30` by construction.
- Production data over 30 days (20+ Spectrum + 3 ATT flapping events) confirms `peak_transition_count == transition_count == 30` for every event.
- Existing tests at `tests/test_alert_engine.py:1615-1649` (`TestFlappingDequeClear`) assert clear-after-fire semantics and must be updated for Option A.

### Alerting Boundary

- `alert_engine.py` semantics (cooldown_sec per-rule dedup, see `:50,68,181-184,229`) are NOT changed in v1.45. Only `wan_controller.py` peak tracking changes.
- `min_hold_sec` (`wan_controller.py:4288-4292`, 1.0s default) is a separate dwell filter and is also unchanged.

## Session Continuity

Stopped at: Completed 210-03-PLAN.md
Resume file: None
Archived v1.44 evidence: `.planning/milestones/v1.44-phases/`

## Operator Next Steps

- Run `/gsd-plan-phase 211` to scope the production-verification gate.
- After Phase 210 ships and deploys, verify at least one real flapping event reports `peak_transition_count > flap_threshold`.

## Decisions (v1.45)

- [v1.45 Roadmap]: Two-phase split selected over single-phase. Rationale: VERIFY-01 cannot be satisfied at PR-merge time — it requires a real production flapping event after deploy. Making the production-gate an explicit phase boundary (Phase 211) mirrors v1.44 Phase 209 production-canary pattern and avoids burying the closure gate as a milestone-close deferral.
- [v1.45 Roadmap]: ALERT-03 (alert-once-per-episode, no log-spam) paired into Phase 211 rather than Phase 210 because end-to-end behavior is only verifiable in production under a real sustained event. Phase 210 tests establish the mechanism (cooldown_sec retained, deque-clear-on-fire retained); Phase 211 confirms it holds in production.
- [v1.45 Roadmap]: SAFE-10 owned primarily by Phase 210 (PR-merge-time verification) and re-verified at Phase 211 (milestone-close) to catch drift between merge and deploy.
- [v1.45 Roadmap]: Plan materialization deferred to `/gsd-plan-phase` per milestone convention; no `.planning/phases/210-*` or `.planning/phases/211-*` directories created during roadmap phase.
- [210-02]: Flapping tests now assert `peak_transition_count` from `_dl_peak_window_transitions` / `_ul_peak_window_transitions` deques, with fixed-threshold second-fire coverage for DL and UL.
- [210-02]: Threshold-mutation integration coverage was adjusted because identical `flap_window` pruning makes the old `peak=35` / `transition=30` payload expectation impossible under the accepted two-deque design.
- [210-03]: SAFE-10 baseline uses v1.44 archive marker `21ee630` as the local equivalent close point because `c9932d2` resolves to an earlier v1.42-era commit in this checkout.

## Performance Metrics

| Phase | Plan | Duration | Tasks | Files |
|-------|------|----------|-------|-------|
| 210 | 02 | 6.0min | 2 | 3 |
| 210 | 03 | 4.1min | 1 | 1 |
