---
gsd_state_version: 1.0
milestone: v1.38
milestone_name: milestone
status: executing
stopped_at: Completed 187-01-PLAN.md
last_updated: "2026-04-15T10:35:54.491Z"
last_activity: 2026-04-15
progress:
  total_phases: 3
  completed_phases: 1
  total_plans: 6
  completed_plans: 4
  percent: 67
---

# Session State

## Project Reference

See: .planning/PROJECT.md (updated 2026-04-15)

**Core value:** Sub-second congestion detection with 50ms control loops, achieved through systematic performance optimization and code quality improvements while maintaining production reliability.
**Current focus:** Phase 187 — rtt-cache-and-fallback-safety

## Position

**Milestone:** v1.38 Measurement Resilience Under Load
**Phase:** 187 — rtt-cache-and-fallback-safety
**Plan:** 187-01 complete; next up 187-02
**Status:** Executing Phase 187
**Last activity:** 2026-04-15

Progress: [███████░░░] 67%

## Accumulated Context

- v1.34 shipped: latency/burst alerts, storage/runtime pressure monitoring, operator summary surfaces, canary checks, threshold runbook
- v1.35 shipped: storage stabilization, clean deploy/canary, 24-hour soak closeout, verification backfill, and operator-flow alignment
- Phase 174 soak passed: canary exit 0, zero WAN-service errors, operator summaries valid
- Phase 175 closed the remaining audit blockers: STOR-01, DEPL-01, STOR-03, and SOAK-01 are now verification-backed with no orphaned requirements
- Storage at soak closeout: Spectrum 5.1G DB / 4.3M WAL, ATT 4.8G DB / 4.3M WAL, both `storage.status: ok`
- ATT/Spectrum parity confirmed on all operator surfaces
- Phase 176 aligned the active deploy/install flow with the storage migration path, surfaced `wanctl-operator-summary` in deploy.sh, and extended soak evidence coverage to ATT plus `steering.service`
- Milestone archive accepted non-blocking validation debt in Phases 172-174 plus the 1-hour built-in soak-monitor helper window
- Live post-ship inspection shows active per-WAN DBs still at roughly 5.44 GB and 5.08 GB, with a legacy `metrics.db` residue still present on host
- Phase 177 closed STOR-04: active per-WAN DBs are authoritative for autorate, legacy `metrics.db` is still active/shared, and the current multi-GB footprint is mostly live retained content rather than WAL or reclaimable slack
- Phase 178 is complete: steering now declares the shared `metrics.db` role explicitly, the shipped per-WAN configs keep only 1 hour of raw retention while preserving the 24-hour aggregate window, and `/metrics/history` plus operator docs follow the authoritative per-WAN DB topology
- Phase 178 verification passed on repo-side must-haves and deferred live production evidence to Phase 179
- Phase 179 completed the production footprint re-check, live reader-topology evidence, final operator closeout, and Phase verification for `OPER-04`
- Phase 179 closed `OPER-04` with a repeatable proof path while recording two explicit operational truths: the per-WAN footprint did not materially shrink, and live `/metrics/history` still drifts from the intended merged cross-WAN topology
- The v1.36 milestone audit found two blockers: missing Phase 177 verification for `STOR-04`, and failed production outcome for `STOR-06`
- Phase 180 and Phase 181 were added to close those audit gaps before re-auditing the milestone
- Phase 180 completed the `STOR-04` re-audit handoff: the missing Phase 177 verification artifact now exists, and that requirement is back to satisfied state
- The refreshed milestone audit now shows only one remaining blocker: `STOR-06`
- Phase 181 executed all three plans and captured the final production outcome
- The startup/watchdog blocker was traced to pre-health storage work and fixed with bounded startup maintenance plus large-DB validation changes
- Production is stable again under the repo-default `WatchdogSec=30s`, and `/health`, canary, and soak-monitor are usable again
- CLI-vs-HTTP history-reader roles are now explicit and proven in production: CLI merged, HTTP endpoint-local
- Spectrum is materially smaller than the fixed baseline, but ATT remains effectively unchanged
- `STOR-06` therefore remains unsatisfied even though the phase execution itself is complete
- The refreshed milestone audit now routes the remaining work into a single new gap-closure phase: Phase 182 ATT Footprint Closure
- Phase 182 planning is complete with three plans: ATT-specific precheck, ATT-only reduction execution, and final production closeout
- Phase 182 completed the ATT-only compaction run and reduced `metrics-att.db` from about `5.08 GB` to about `202 MB`
- Both active per-WAN DBs are now materially smaller than the fixed `2026-04-13` baseline, so `STOR-06` is satisfied
- v1.36 milestone audit is now clean enough for completion, with only non-blocking dashboard consumer debt remaining
- v1.36 is archived and tagged, and the carried-forward debt is now the seed for v1.37
- The dashboard history widget still queries `/metrics/history` directly and does not surface the endpoint-local versus merged history distinction or `metadata.source`
- v1.37 will focus on dashboard history source clarity, operator comprehension, and matching tests/docs without changing backend history semantics
- Phase 184-02 is complete: success-state history detail now translates `metadata.source.mode` into operator wording, DB-path context follows the one-path vs many-path contract, and `source-diagnostic` carries the raw D-08 mode/db_paths/http surface
- Phase 184-03 is complete: `source-handoff` remains compose-only, `HistoryBrowserWidget.HANDOFF_TEXT` exposes the locked merged-CLI invocation, and import-time parity assertions block dashboard copy from implying `wanctl.history` equivalence
- Phase 185 added the locked dashboard regression matrix for success, fetch-error, source-missing, mode-missing, and db-paths-missing flows without reopening backend `/metrics/history` behavior
- Phase 185 aligned `DEPLOYMENT.md`, `RUNBOOK.md`, and `GETTING-STARTED.md` on the same endpoint-local HTTP versus authoritative merged CLI wording, and `185-VERIFICATION.md` now closes both `DASH-04` and `OPER-05`
- Live production investigation on 2026-04-15 reproduced catastrophic `tcp_12down` tail latency (`p99 3059.16ms`) while Spectrum still reported `healthy` and `GREEN`
- The same run showed repeated three-reflector miss bursts and protocol-correlation churn, while steering remained healthy and VM steal stayed low
- Code investigation points to a measurement-resilience gap: reduced reflector quorum carries no explicit confidence penalty, and zero-success background RTT cycles preserve stale cached RTT until the hard stale cutoff

## Session Continuity

Stopped at: Completed 187-01-PLAN.md
Resume file: .planning/phases/187-rtt-cache-and-fallback-safety/187-02-PLAN.md

## Decisions

- Phase 184-01 keeps history fetch-state classification in `src/wanctl/dashboard/widgets/history_state.py` so future tests can cover the state matrix without mounting Textual.
- History tab source framing is always mounted in the widget via dedicated banner/detail/handoff/diagnostic `Static` children.
- Success-state detail and exact diagnostic formatting are intentionally deferred to Plan 184-02; this plan only establishes the shared routing and locked copy surface.
- [Phase 184]: Phase 184-02 routes success-state source-detail through _format_source_detail so D-06 and D-07 stay testable without mounting Textual.
- [Phase 184]: Raw metadata.source mode and db_paths values remain confined to source-diagnostic helpers, while primary history copy stays translated through HISTORY_COPY phrases.
- [Phase 184]: Exposed the merged CLI handoff text as HistoryBrowserWidget.HANDOFF_TEXT so Phase 185 can assert the exact string without importing HISTORY_COPY.
- [Phase 184]: Placed the parity-language guard at module scope so invalid dashboard copy fails at import time instead of relying on a mounted widget path.
- [Phase 185]: Preserved existing browser tests and added a separate contract-focused class for the Phase 183 state matrix.
- [Phase 185]: Kept Phase 185 scoped to dashboard tests only and asserted against HISTORY_COPY and HANDOFF_TEXT instead of duplicating copy literals.
- [Phase 185]: Locked milestone closeout in `185-VERIFICATION.md` and treated repo-side traceability as sufficient evidence for `DASH-04` and `OPER-05`.
- [Milestone v1.37]: Audit refreshed to `passed` after Phase 183-185 validation backfill and integration re-check closed the earlier non-blocking dashboard debt.
- [Phase 186]: Locked the Phase 186 measurement contract inline in 186-01-PLAN.md so Plans 186-02 and 186-03 consume one source of truth.
- [Phase 186]: Kept 186-01 documentation-only and deferred requirement completion until implementation/testing plans land.
- [Phase 187]: Kept RTTCycleStatus parallel to RTTSnapshot so get_latest() and stale-cache consumers remain unchanged.
- [Phase 187]: Published cycle status before the existing success branch so zero-success cycles report current quorum without overwriting _cached.
- [Phase 187]: _last_raw_rtt_ts was intentionally left untouched in Plan 187-01; honesty wiring is deferred to Plan 187-02.

## Performance Metrics

- 2026-04-15: Phase 187 Plan 01 completed in 10 min across 2 tasks and 1 source file.
- 2026-04-15: Phase 186 Plan 01 completed in 8 min across 2 tasks and 2 planning files.
- 2026-04-14: Phase 184 Plan 01 completed in 13 min across 3 tasks and 2 source files.
- 2026-04-14: Phase 184 Plan 02 completed in 11 min across 2 tasks and 1 source file.
- 2026-04-14: Phase 184 Plan 03 completed in 7 min across 2 tasks and 1 source file.
- 2026-04-14: Phase 185 Plan 01 completed in 6 min across 3 tasks and 2 source files.
- 2026-04-14: Phase 185 Plan 02 completed in 1 min across 4 tasks and 3 source files.
- 2026-04-14: Phase 185 Plan 03 completed with repo-side verification evidence and `171` dashboard tests passing.
- 2026-04-14: Milestone v1.37 archived with 5/5 requirements satisfied and 3/3 phases complete.
- 2026-04-14: Milestone v1.37 audit refreshed to `passed`; all three milestone phases now have Nyquist-compliant validation artifacts and no blocker-level integration or flow gaps remain.
