---
gsd_state_version: 1.0
milestone: v1.40
milestone_name: Queue-Primary Signal Arbitration
status: blocked
stopped_at: Completed 198-03-PLAN.md; throughput verdict FAIL blocks Plan 04 without operator decision
last_updated: "2026-04-28T15:41:32.964Z"
last_activity: 2026-04-28
progress:
  total_phases: 7
  completed_phases: 5
  total_plans: 23
  completed_plans: 24
  percent: 100
---

# Session State

## Project Reference

See: .planning/PROJECT.md (updated 2026-04-23)

**Core value:** Sub-second congestion detection with 50ms control loops, achieved through systematic performance optimization and code quality improvements while maintaining production reliability.
**Current focus:** Phase 198 — Spectrum cake-primary B-leg rerun on Phase 197 build

## Position

**Milestone:** v1.40 Queue-Primary Signal Arbitration
**Phase:** 198
**Plan:** 198-03
**Status:** Phase 198 Plan 03 complete; VALN-05a throughput verdict is FAIL, so Plan 04 is blocked pending operator decision
**Last activity:** 2026-04-28

Progress: [██████████] 100%

## Parallel Milestone

**v1.39 Control-Path Timing & Measurement Accounting** — Phase 192 shipped under waiver; Phase 191 remains open

- Phase 191: blocked on ATT RRUL weather-rerun
- Phase 192: Reflector Scorer Blackout + Log Hygiene — shipped to production as `1.39.0` under `192-PRECONDITION-WAIVER.md`; D-08/OPER-02 pre/post soak capture passed against the live 24h journal window
- Serialized Spectrum soak rule: Phase 192 24h soak must land before v1.40 Phase 196 2×24h soak; no concurrent Spectrum experiments
- Cross-milestone dependencies: v1.40 Phase 195 depends on v1.39 Phase 192 (corrected blackout-aware scorer feeds rtt_confidence); v1.40 Phase 196 depends on v1.39 Phase 192 (serialized Spectrum soak) and v1.39 Phase 191 closure (ATT canary gate)

## Accumulated Context

### Roadmap Evolution

- 2026-04-23: v1.40 roadmap finalized with 4 phases (193, 194, 195, 196), 10/10 v1.40 REQ-IDs mapped. SAFE-05 is cross-cutting across all four phases. Phase numbering starts at 193 because v1.39 owns 191, 191.1, and 192.
- 2026-04-23: v1.40 Queue-Primary Signal Arbitration opened in parallel with unclosed v1.39. v1.39 Phase 192 stays reserved at its number. v1.40 phases continue at 193 onward.
- 2026-04-23: Joint Claude + Codex architectural decision — Spectrum DOCSIS ~280 Mbps under wanctl vs 591 Mbps CAKE-only static floor is a measurement-architecture problem, not a tuning problem. Primary signal changes from RTT delta to kernel-provided `avg_delay_us - base_delay_us` under load. RTT becomes confidence-gated secondary. Scope is DL-only; UL stays RTT-led because UL is healthy.
- 2026-04-23: Codex pushback retained in plan — use kernel `base_delay_us`, not Python-learned baseline; `avg_delay_us` not `peak_delay_us` as primary (peak too spike-prone, stays as burst corroborator); healer bypass gate is categorical direction-alignment over 6 cycles, never a µs/ms magnitude ratio; new `signal_arbitration` /health block is additive, not nested under `download.hysteresis`.
- 2026-04-23: Implementation order agreed — v1.40 Phase 193 (obs-only) → Phase 194 (DL classification) → v1.39 Phase 192 (scorer + 24h soak) → v1.40 Phase 195 (RTT demotion on corrected scorer) → v1.40 Phase 196 (2×24h Spectrum A/B + ATT canary after 191 closes).
- 2026-04-27: Phase 197 added — Queue-Primary Refractory Semantics: split dl_cake_for_detection (masked during 40-cycle refractory) from dl_cake_for_arbitration (queue-delay scalar live during refractory) to resolve Phase 196 Spectrum throughput regression where corrected DL median was 307.9 Mbps vs 532 Mbps threshold. Must preserve Phase 160 cascade-safety invariant and Phase 194 selector-after-mask invariant. Linked to thread phase-196-queue-primary-refractory-semantics-investigation.

- Phase 191.1 inserted after Phase 191: ATT config drift resolution and Phase 191 closure (URGENT)
- Phase 191 ATT validation isolated the blocker to post-`v1.38` ATT config/runtime drift rather than the narrow Phase 191 timing changes; current code plus `v1.38` ATT config restored RRUL baseline throughput
- Phase 192 originally waited on Phase 191.1 so the next soak would not be confounded by unresolved ATT closure criteria; on 2026-04-24 the operator explicitly waived that precondition for Phase 192 only after another restored-config rerun narrowed the blocker to the old ATT RRUL download comparator.

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

Stopped at: Completed 198-03-PLAN.md; throughput verdict FAIL blocks Plan 04 without operator decision
Resume file: None

## Decisions

- [v1.40 Roadmap]: Phase 193 is telemetry-only; zero control-behavior change is a hard requirement so that v1.39 replay remains byte-identical against the Phase 193 build.
- [v1.40 Roadmap]: Phase 195 depends on v1.39 Phase 192 because blackout-aware reflector scoring is a direct input to ICMP-agreement side of rtt_confidence; without it, rtt_confidence would read falsely low during carrier blackouts and the new healer bypass gate would calibrate on a polluted signal.
- [v1.40 Roadmap]: Phase 196 Spectrum A/B is strictly serialized against v1.39 Phase 192's 24h soak (VALN-04); ATT canary is strictly gated on v1.39 Phase 191 closure.
- [v1.40 Roadmap]: SAFE-05 is cross-cutting and listed under every phase's Requirements addressed; arbitration changes classification input, not classification rules.
- [v1.40 Roadmap]: Plan materialization is deferred to `/gsd-plan-phase` per milestone convention; no `.planning/phases/193-*` directories created during roadmap phase.
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
- [Phase 187]: Plan 187-02 preserves timestamp=snapshot.timestamp on both measure_rtt() branches so measurement staleness remains honest during cached RTT reuse.
- [Phase 187]: Plan 187-02 keeps the 5s stale cutoff and fallback path byte-identical while wiring zero-success cycle status into measure_rtt().
- [Phase 187]: Plan 187-04 keeps the gap closure tests-only and pins the producer-side get_cycle_status() contract by driving BackgroundRTTThread._run() directly inside TestBackgroundRTTThread.
- [Phase 191.1]: Restored ATT irtt.server and fusion.enabled together to the v1.38 baseline in one coordinated config commit.
- [Phase 191.1]: Used a semantic YAML diff against v1.38 plus SAFE-03 token scan to prove no other ATT config keys changed.
- [Phase 191.1]: Preserved the milestone-wide SAFE-03 dirty diff as contextual debt while making the phase-local comparator the Phase 191 closure rule.
- [Phase 191.1]: Rejected the TCP `nc` probe as a false negative because IRTT uses UDP; manual `irtt client` validation to `104.200.21.31:2112` succeeded from `cake-shaper`.
- [Phase 191.1]: Used outcome_class=valid_result plus the ATT RRUL comparator, yielding `VALN-02 verdict: FAIL` at `63.83 Mbps` versus the `78.29 Mbps` baseline.
- [Phase 191.1]: Operator context after execution indicates the `2026-04-20` ATT rerun likely happened during severe rain, so the FAIL stays recorded but is now treated as weather-confounded until Plan `191.1-02` is repeated in normal conditions.
- [Phase 191.1]: A second rerun on `2026-04-21` improved ATT RRUL to `74.03 Mbps` but still missed the comparator by `0.44` percentage points, and the Spectrum discriminator sample was clearly bad (`283.40 Mbps`, `733.67 ms` ping p99), so that run is also treated as environment-confounded.
- [Phase 191.1]: A third rerun on `2026-04-21b` dropped ATT RRUL back to `67.83 Mbps` while Spectrum remained degraded (`309.04 Mbps`, `375.64 ms` ping p99), reinforcing that the rerun environment was still unstable.
- [Phase 191.1]: A fourth rerun on `2026-04-23` re-verified the ATT source path cleanly after removing the AI-VM ATT policy (`10.10.110.233` => `99.126.115.47`, `10.10.110.226` => `70.123.224.169`) and produced ATT RRUL `64.40 Mbps`, but the matching Spectrum discriminator was still degraded (`286.42 Mbps`, `812.33 ms` ping p99), so the overall sample remains environment-confounded.
- [Phase 191.1]: Kept Plan 05 ATT failure history intact and added Phase 191.1 closure wording as additive evidence only.
- [Phase 191.1]: A sixth rerun on `2026-04-24` produced ATT RRUL `70.95 Mbps`, ATT tcp_12down `72.95 Mbps`, ATT VoIP one-way p99 `28.02 ms`, and Spectrum RRUL `343.83 Mbps` with poor `653.68 ms` ping p99. Phase 191 remains blocked, but the operator waived the Phase 191 closure precondition for Phase 192 only in `192-PRECONDITION-WAIVER.md`.
- [Phase 193]: Phase 193-01 keeps queue-delay plumbing additive and observability-only; classifier and control-path behavior remain untouched.
- [Phase 193]: Phase 193-01 exposes max_delay_delta_us as the authoritative queue-delay scalar computed per tin before aggregation.
- [Phase 196]: Final closeout records Phase 196 as blocked, not passed: Spectrum A/B evidence is absent because the reversible mode gate is blocked, and ATT canary blocked by Phase 191.
- [Phase 196]: Phase 196 Plan 04 closed as blocked: ATT canary skipped because Phase 191 remains open; VALN-04 and VALN-05 stay blocked while SAFE-05 remains satisfied.
- [Phase 196-06]: Spectrum rtt-blend A-leg passed after 28.2311h with zero non-RTT arbitration samples; Plan 196-07 must reuse same_deployment_token cake-shaper:wanctl@spectrum.service:/etc/wanctl/spectrum.yaml.
- [Phase 196-06]: VALN-04 remains partial until the cake-primary B-leg and A/B comparison pass; SAFE-05 remains satisfied.
- [Phase 196-07]: Spectrum cake-primary B-leg ran for 24.0244h on the same deployment token but failed the primary-signal audit because 153 arbitration metric samples were not exactly queue-primary; throughput and A/B comparison were correctly skipped.
- [Phase 196-07]: VALN-04 and VALN-05 remain blocked after the failed Spectrum B-leg audit; SAFE-05 remains satisfied because no protected controller source changed.
- [Phase 196-10]: Operator accepted the raw-only cake-primary B-leg documented exceptions for continuation while preserving the original fail-closed audit.
- [Phase 196-10]: Spectrum cake-primary tcp_12down throughput failed at 73.92243773827883 Mbps against the 532 Mbps threshold, so no A/B comparison was created.
- [Phase 197-01]: Split DL CAKE detection/arbitration routing so Phase 160 cascade masking remains on `adjust_4state` while refractory arbitration can stay queue-primary from the live snapshot.
- [Phase 197-01]: Selector uses the pre-decrement refractory-active stash for the final 1->0 drain cycle, keeping `/health` and arbitration reasons aligned for the cycle that was actually refractory.
- [Phase 197-02]: Kept `wanctl_arbitration_refractory_active` DL-only and did not add UL placeholder rows.
- [Phase 197-02]: Treat `rtt_fallback_during_refractory` plus `refractory_active=true` as a documented exception audit bucket, not steady-state RTT.
- [Phase 197-02]: Guard Phase 195 healer alignment-streak updates during DL refractory windows so one congestion event cannot both enter cooldown and arm healer bypass.
- [Phase 198-01]: Accepted rsync deployment proof for `/opt/wanctl` instead of remote git metadata: Phase 197-only `/health` field, new metric rows, restart timestamp, and operator-approved deploy/restart commands bind the running process to the Phase 197 ship SHA.
- [Phase 198-01]: Treated cake-primary mode as proven by remote sudo YAML read plus `active_primary_signal=queue` because `/health` exposes the live cake_signal snapshot but not a `cake_signal.enabled` boolean.
- [Phase 198-02]: Accepted existing Task 1 soak evidence without restarting the run: start capture `cake-primary-start-20260427T145714Z-summary.json`, `soak_start_utc=2026-04-27T14:57:14Z`, and finish scheduled by `systemd-run --user --on-active=24h30m` for `2026-04-28T15:27:14Z`.
- [Phase 198-02]: Recorded `granularity_filter_form=sql_only` for the Phase 197 raw-row audit because the capture PSV has no `granularity` header; aggregate PSV rows remain excluded from the verdict.
- [Phase 198-02]: Cake-primary B-leg duration gate passed at 88,236 seconds and the primary-signal audit returned `pass_with_documented_exceptions` with 71,801 raw samples, 99.7493% queue-primary coverage, and 180 documented non-queue rows.
- [Phase 198]: Used TCP download sum, not per-stream TCP download avg, as the aggregate tcp_12down median series for VALN-05a.
- [Phase 198]: VALN-05a failed with medians 450.468331, 681.802267, and 494.834220 Mbps; only one run met 532 Mbps and median-of-medians was 494.834220 Mbps.

## Performance Metrics

- 2026-04-28: Phase 198 Plan 03 completed in ~7 min across 2 tasks and 6 evidence files; three corrected Spectrum-bound tcp_12down flent runs were captured, source-bind probes all confirmed Charter/AS11427 egress, 572-test regression slice passed, and VALN-05a failed with medians 450.468331/681.802267/494.834220 Mbps.
- 2026-04-28: Phase 198 Plan 02 completed across a 24h30m36s Spectrum cake-primary B-leg and ~5 min active continuation; duration gate passed, primary-signal audit passed with documented exceptions at 99.7493% queue-primary coverage, and 584-test regression slice passed.
- 2026-04-27: Phase 198 Plan 01 completed in 3 min continuation time across SAFE-05 baseline verification, post-restart preflight capture, and 9 evidence files; hot-path slice passed with 572 tests.
- 2026-04-27: Phase 197 Plan 01 completed in 6 min across 3 tasks and 5 source/test files; hot-path slice passed with 569 tests and replay battery passed with 32 tests plus 6 skips.
- 2026-04-27: Phase 197 Plan 02 completed in 5 min across 3 tasks and 5 source/test/planning files; hot-path slice passed with 572 tests and replay battery passed with 35 tests plus 6 skips.
- 2026-04-27: Phase 196 Plan 07 completed in ~16 min active execution over a 24h B-leg window across 3 task outcomes and 17 planning/evidence files; Spectrum cake-primary audit failed with 153 non-queue metric samples, blocking throughput and A/B comparison.
- 2026-04-27: Phase 196 documented-exception continuation completed in 6 min across acceptance, two flent captures, and 5 planning/evidence files; Spectrum cake-primary throughput failed at 73.92243773827883 Mbps vs 532 Mbps, blocking A/B comparison.
- 2026-04-26: Phase 196 Plan 06 completed in 9 min active continuation time across 3 tasks and 11 planning/evidence files; Spectrum rtt-blend A-leg passed after 28.2311h with zero non-RTT arbitration samples and flent baseline evidence.
- 2026-04-24: Phase 196 Plan 04 completed in 9 min across 4 tasks and 7 planning files; closeout blocked VALN-04/VALN-05 and created the ATT canary follow-up todo.
- 2026-04-23: v1.40 roadmap written in single pass — 4 phases, 10/10 REQ-IDs mapped, appended to ROADMAP.md without disturbing v1.39 content.
- 2026-04-20: Phase 191.1 Plan 03 completed in 15 min across 2 tasks and 3 files.
- 2026-04-20: Phase 191.1 Plan 02 completed in 22 min across deploy verification, ATT rrul/tcp_12down/voip rerun, and Spectrum RRUL discriminator capture.
- 2026-04-20: Phase 191.1 Plan 01 completed in 3 min across 2 tasks and 2 files.
- 2026-04-15: Phase 187 Plan 04 completed in 4 min across 1 task and 1 test file.
- 2026-04-15: Phase 187 Plan 02 completed in 15 min across 1 task and 1 source file.
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

## Blockers

- Phase 191 closure remains blocked: restored ATT config rerun history now contains `2026-04-20` (`63.83 Mbps`), `2026-04-21` (`74.03 Mbps`), `2026-04-21b` (`67.83 Mbps`), `2026-04-23` (`64.40 Mbps`), `2026-04-23c` (`61.47 Mbps`), and `2026-04-24` (`70.95 Mbps`) FAIL samples against the old ATT RRUL download comparator. The `2026-04-24` run narrowed the issue because ATT tcp_12down and VoIP looked healthy and Spectrum throughput was strong, but it still did not close Phase 191. Phase 192 is allowed to proceed only under the explicit operator waiver in `192-PRECONDITION-WAIVER.md`.
- Phase 196 remains blocked after Plan 196-07: Spectrum rtt-blend A-leg passed and cake-primary B-leg duration evidence exists, but the B-leg primary-signal audit failed with 153 non-queue metric samples. Throughput/A-B comparison were skipped, VALN-04/VALN-05 remain blocked, ATT canary remains gated by Phase 191, and SAFE-05 remains satisfied.
- Phase 196 Spectrum continuation remains blocked after human acceptance of the raw-only B-leg documented exceptions: throughput ran and failed at 73.92243773827883 Mbps against 532 Mbps, so no A/B comparison was created and VALN-04/VALN-05 remain blocked.
- Pending follow-up created: `.planning/todos/pending/2026-04-24-resolve-att-cake-primary-canary-after-phase-196.md` tracks the required ATT cake-primary canary rerun after Phase 191 closes.

**Planned Phase:** 197 (queue-primary-refractory-semantics-split-dl-cake-for-detecti) — 2 plans — 2026-04-27T11:22:07Z

- Phase 198 Plan 04 is blocked pending operator decision because Plan 03 VALN-05a throughput verdict is FAIL (medians_above_532=1, median_of_medians_mbps=494.834220).
