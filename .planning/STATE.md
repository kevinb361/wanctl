---
gsd_state_version: 1.0
milestone: v1.56
milestone_name: Route Management Surface Deployment
status: ready_to_plan
stopped_at: Phase 256 rollback-anchor preflight complete — deploy/config edit/restart still gated
last_updated: 2026-06-20T03:29:01.963Z
last_activity: 2026-06-20 -- Phase 256 rollback anchors created; deploy/config edit/restart still requires fresh approval
progress:
  total_phases: 3
  completed_phases: 1
  total_plans: 1
  completed_plans: 1
  percent: 33
---

# Session State

## Project Reference

See: .planning/PROJECT.md (updated 2026-06-19 after v1.53 milestone close)

**Core value:** Sub-second congestion detection with 50ms control loops, achieved through systematic performance optimization and code quality improvements while maintaining production reliability.
**Current focus:** Phase 256 — bounded safe/off deployment + health surface proof

## Current Position

Phase: 256
Plan: 256-01 partial — rollback-anchor preflight complete
Status: Waiting for fresh approval before deploy/config edit/restart
Last activity: 2026-06-20 -- Phase 256 rollback anchors created; deploy/config edit/restart still requires fresh explicit approval

## Active Blockers / Concerns

- SAFE-20 for v1.56: no live RouterOS route mutation, Netwatch disablement, controller threshold retuning, CAKE qdisc change, or production route-owner flip. Deploy/restart gates require explicit operator approval and rollback.
- v1.56 follows v1.55's keep-netwatch result: the next safe step is exposing route-management health/config on cake-shaper in safe/off or dry-run mode, not active canary.
- Phase 256 rollback-anchor preflight complete: remote backups exist under `/var/lib/wanctl/phase256-backups/20260620T033704Z` for the flat `/opt/wanctl` tree and `/etc/wanctl/steering.yaml`. Live config still has no `route_management` block. No deploy, config edit, restart/reload, RouterOS/Netwatch/CAKE mutation, or route-owner flip occurred. Safe/off deploy/restart still requires fresh explicit approval.
- SAFE-18 original zero-controller-diff invariant held through Phase 248.1 and was intentionally superseded by the operator-directed Phase 248.2 fping freshness controller fix. Storage hygiene phases 249/250 must avoid unrelated controller-path changes and document no additional controller behavior drift.
- SAFE-19 for v1.55 held: no live RouterOS route mutation, Netwatch disablement, controller threshold retuning, CAKE qdisc change, or production default flip occurred outside an explicitly approved canary phase.
- Netwatch remains the interim WAN route owner after v1.55 close; future wanctl route ownership requires safe/off deployment evidence, read-only observation, and a new explicit approval gate.
- Phase 252 complete: route-management config/dry-run surface and RouterOS route REST boundary shipped safe/off with mock-only tests; active route ownership remains blocked for Phase 253/254 guard/canary work.
- Phase 253 complete: mock-only guard, route decision, reconciliation/circuit, health/operator observability, and docs shipped. Active live route mutation remains blocked by config/guard/reconciliation/circuit gates. Phase 254 live observation found deployed steering on cake-shaper healthy but without the route_management health/config surface; no canary was approved.
- Phase 250 complete: TIN-01 consumer audit found `wanctl-history --tins` raw-history semantics and counter-shaped dropped/ECN metrics; TIN-02/TIN-03 deferred to future sparse-history work rather than changing emission density.
- fping profiling was shadow-only through Phase 248. Phase 248.2 intentionally mutated the controller path to repair the live canary freshness bug; no production default keep was made.
- Phase 247 complete: partial fping shadow soak ran 6.964h, stopped cleanly with `probe_stats_final`, and produced `.planning/phases/247-fping-shadow-capture-phase-245-evidence-review/evidence/phase247-shadow-summary.json` for Phase 248. No production default flip was made.
- Phase 248 complete: `.planning/phases/248-fping-p99-distribution-analysis-profiling-verdict/248-FPING-VERDICT.md` says fping is switch-eligible for an operator-gated controlled canary; no production default flip was made.
- Phase 248.1 complete: live native wanctl + fping canary was operator-approved, executed, and rolled back. The blocker is not the old 10ms p99 gate; it is current native fping cadence/staleness/fallback behavior: 10s background fping can be treated stale by the 50ms loop, causing repeated TCP fallback, cycle overruns, and cycle-budget warning alerts. Production is restored to external cake-autorate + `icmplib` config.
- Phase 248.2 complete: cadence-aware fping cached-sample staleness limits shipped in `WANController.measure_rtt()`. A bounded native Spectrum fping canary showed `stale_count=0`, `NRestarts=0`, and healthy cycle budget after startup, then rolled back cleanly to external cake-autorate + `icmplib`.
- Phase 248.3 complete: native Spectrum CAKE config now matches the external cake-autorate trial envelope for fair future fping canaries: 550M green floor / 600M ceiling, `rtt 25ms`, download no-ack-filter, upload ack-filter.
- Phase 248.4 complete: native fping startup now treats the bounded first-sample no-cache window as producer readiness instead of ICMP failure. Live canary showed `wait_count=1`, `no_data_count=0`, `fallback_warn_count=0`, `stale_count=0`, and `NRestarts=0`, then rolled back to external cake-autorate + `icmplib`.
- Phase 249 complete: live read-only ingestion audit found no current stable-window >=2Hz flat-gauge candidates on Spectrum or ATT. 3600s-only Spectrum CAKE zero rows were canary-contaminated by earlier native controller tests and deferred; no code change was warranted.
- Phase 250 complete: `.planning/phases/250-cake-tin-consumer-audit-conditional-implementation/evidence/consumer-audit-20260619T213950Z.md` classifies all discovered tin consumers. No source code changed; relevant tests passed.

## Deferred Items (carried into v1.54)

Acknowledged and deferred at v1.53 milestone close 2026-06-19:

| Category | Item | Status |
|----------|------|--------|
| requirements | VERIFY-01 | deferred to Phase 218 — needs natural production flapping event; Phase 218 watch dormant (native controller not live) |
| requirements | VERIFY-02 | deferred to Phase 218 — gated on VERIFY-01 + ALERT-03 audit; dormant |
| requirements | RECLAIM-04 | deferred indefinitely — now a cake-autorate config question, not a wanctl probe-shape question |
| phases | Phase 218 (Deferred v1.45 VERIFY Watch-List Closure) | dormant; instrumentation lives in non-live native controller |
| todos | 2026-04-17-monitor-flapping-peak-count-on-next-docsis-event.md | open; event-gated carry-forward |
| todos | 2026-04-24-resolve-att-cake-primary-canary-after-phase-196.md | open; validation carry-forward |
| todos | 2026-06-03-retest-spectrum-diffserv4-wash-after-local-qos-changes.md | open; validation carry-forward |
| todos | 2026-06-18-route-ownership-netwatch-to-wanctl-failover.md | open; high-priority pipeline item |
| seeds | SEED-003-v143-d14-watchdog-recalibration | dormant |
| seeds | SEED-004-v143-target-edge-churn-instrumentation | dormant |
| seeds | SEED-005-v143-conservative-ul-tuning-sweep | dormant |
| seeds | SEED-006-v145-silicom-bypass-tooling-and-harness | shipped in v1.52; dormant metadata |
| seeds | SEED-007-v145-storage-hygiene-fire-on-change | active in v1.54 (GAUGE-01..03, TIN-01..03) |

## Deferred Items (acknowledged at v1.55 close)

Acknowledged and deferred at v1.55 milestone close 2026-06-20:

| Category | Item | Status |
|----------|------|--------|
| debug_sessions | knowledge-base | open/pre-existing |
| todos | 2026-04-17-ingestion-rate-tool.md | pending/pre-existing |
| todos | 2026-04-17-investigate-steering-degraded-on-clean-restart.md | pending/pre-existing |
| todos | 2026-04-17-monitor-flapping-peak-count-on-next-docsis-event.md | pending/pre-existing |
| todos | 2026-04-24-resolve-att-cake-primary-canary-after-phase-196.md | pending/pre-existing |
| todos | 2026-06-03-retest-spectrum-diffserv4-wash-after-local-qos-changes.md | pending/pre-existing |
| todos | audit remainder | 2 additional pending todos reported by audit-open |
| seeds | SEED-003-v143-d14-watchdog-recalibration | dormant |
| seeds | SEED-004-v143-target-edge-churn-instrumentation | dormant |
| seeds | SEED-005-v143-conservative-ul-tuning-sweep | dormant |
| seeds | SEED-006-v145-silicom-bypass-tooling-and-harness | dormant |
| seeds | SEED-007-v145-storage-hygiene-fire-on-change | active/pre-existing |

## Accumulated Context

### Roadmap Evolution

- **2026-06-18 (v1.54 ROADMAP commit):** v1.54 ROADMAP.md created with 4-phase scope (fine granularity), continuing from v1.53 last phase (246) → Phase 247. Natural ordering: fping profiling (shadow capture + evidence review) → fping verdict → flat-gauge hygiene → tin consumer audit + conditional ship. SAFE-18 declared as cross-phase controller-path zero-diff invariant, mapped to closeout Phase 250 for traceability. Phase 250 has an explicit conditional gate: if TIN-01 audit finds count-over-window consumer, TIN-02/03 defer to v1.55. 11/11 v1.54 REQs mapped, 0 orphans.
- **2026-06-10 (v1.51 ROADMAP commit):** 3-phase scope (fine granularity, deliberately small). Final order: 232 → 233 → 234. SAFE-15 cross-phase invariant.
- **2026-06-09 (v1.50 ROADMAP commit):** 3-phase scope. Order: 229 → 230 → 231. SAFE-14 cross-phase invariant.

### Pending Todos

See `.planning/todos/pending/` — 7+ active todos as listed in Deferred Items.

### Blockers / Concerns

v1.55 closed route ownership / Netwatch retirement with final decision `keep-netwatch`. The route-management code path is present in repo code, but production cake-shaper still needs a safe/off deployment exposing `route_management` health/config before any future active canary. Phases 248.2–248.4 fixed the known native fping mechanical blockers; native fping keep remains deferred to an operator-gated keep canary. Phase 250 closed the CAKE tin gate by deferring skip-on-unchanged to future sparse-history work because raw-history/counter-shaped semantics are not sparse-safe.

## Session Continuity

Last session: 2026-06-20T03:37:04Z
Stopped at: Phase 256 rollback-anchor preflight complete; deploy/restart still approval-gated
Resume file: None
Archived v1.53 evidence: `.planning/milestones/v1.53-phases/` (see milestones/v1.53-ROADMAP.md)

## Operator Next Steps

- Next safe step is asking for fresh explicit approval before the Phase 256 safe/off or dry-run deploy/config edit/restart of `steering.service`. Rollback anchors now exist. Do not deploy, restart, reload, edit live config, mutate RouterOS/Netwatch, change CAKE/qdisc, or flip route ownership without approval.
