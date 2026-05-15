---
gsd_state_version: 1.0
milestone: v1.44
milestone_name: Topology-Correct CAKE — Spectrum besteffort wash migration
current_phase: 206
status: gaps_found
stopped_at: Phase 206 verification found TOPO-05 fail-closed gaps
last_updated: "2026-05-15T02:52:14Z"
last_activity: 2026-05-15
progress:
  total_phases: 5
  completed_phases: 2
  total_plans: 9
  completed_plans: 9
  percent: 100
---

# Session State

## Project Reference

See: .planning/PROJECT.md (updated 2026-05-13 after v1.43 archive close)

**Core value:** Sub-second congestion detection with 50ms control loops, achieved through systematic performance optimization and code quality improvements while maintaining production reliability.
**Current focus:** Phase 206 — a-b-replay-harness-rollback-gates gap closure

## Position

**Last shipped milestone:** v1.43 UL Suppression Metrics & Gate Calibration (shipped 2026-05-13; audit `passed` 15/15)
**Recently archived:** v1.43 (2026-05-13), v1.42 (2026-05-06), v1.41 (2026-05-06), v1.40 (2026-05-03), v1.39 (2026-05-06 retroactive)
**Active milestone:** v1.44 Topology-Correct CAKE — Spectrum besteffort wash migration (planning; phases 205–209 drafted 2026-05-14).
**Current phase:** 206

Progress: [██████████] 100%

## Deferred Items

Items acknowledged and deferred at v1.40 milestone close on 2026-05-03 (per audit-open snapshot):

| Category | Item | Status |
|----------|------|--------|
| debug_sessions | knowledge-base | unknown |
| quick_tasks | 001-rename-phase2b-to-confidence-based-steer | missing |
| quick_tasks | 002-fix-health-version | missing |
| quick_tasks | 003-remove-deprecated-sample-params | missing |
| quick_tasks | 004-fix-socket-warnings | missing |
| quick_tasks | 005-fix-watchdog-safe-startup-maintenance | missing |
| quick_tasks | 260319-lk3-fix-state-file-persistence-and-tuning-pa | missing |
| quick_tasks | 260320-9wi-update-readme-and-config-schema-docs-for | missing |
| quick_tasks | 260327-uy3-add-spike-detector-confirmation-counter- | missing |
| quick_tasks | 6-lan-accessible-health-endpoints-and-dual | missing |
| quick_tasks | 7-fix-flapping-alert-bugs-rule-name-mismat | missing |
| quick_tasks | 8-fix-flapping-alert-detection-cooldown-ke | missing |
| threads | phase-196-queue-primary-refractory-semantics-investigation | in_progress |
| todos | 2026-04-08-investigate-tcp-12down-latency-spikes | unknown |
| todos | 2026-04-10-monitor-proxmox-steal-cpu | unknown |
| todos | 2026-04-12-investigate-steering-cycle-overruns-and-blocking-i-o | unknown |
| todos | 2026-04-15-profile-post-hotpath-baseline-on-production-wan | unknown |
| todos | 2026-04-17-24h-soak-checkpoint-verification | unknown |
| seeds | 001-spectrum-topology-correct-cake-mode | dormant |
| uat_gaps | (2 items) | resolved |

Most quick_tasks at status `missing` are legacy directory entries without metadata files (no live work). v1.41 should triage these via `/gsd-review-backlog`.

The pending todo `2026-04-24-resolve-att-cake-primary-canary-after-phase-196` is preserved in `.planning/todos/pending/` and tied to v1.40 VALN-05b deferral (cross-milestone gate on v1.39 Phase 191 closure).

## Parallel Milestone

**v1.39 Control-Path Timing & Measurement Accounting** — Phase 192 shipped under waiver; Phase 191 remains open

- Phase 191: blocked on ATT RRUL weather-rerun
- Phase 192: Reflector Scorer Blackout + Log Hygiene — shipped to production as `1.39.0` under `192-PRECONDITION-WAIVER.md`; D-08/OPER-02 pre/post soak capture passed against the live 24h journal window
- Serialized Spectrum soak rule: Phase 192 24h soak must land before v1.40 Phase 196 2×24h soak; no concurrent Spectrum experiments
- Cross-milestone dependencies: v1.40 Phase 195 depends on v1.39 Phase 192 (corrected blackout-aware scorer feeds rtt_confidence); v1.40 Phase 196 depends on v1.39 Phase 192 (serialized Spectrum soak) and v1.39 Phase 191 closure (ATT canary gate)

## Accumulated Context

### Roadmap Evolution

- 2026-05-14: v1.44 roadmap drafted with 5 phases (205, 206, 207, 208, 209); 16/16 v1.44 REQ-IDs mapped (TOPO 1–7, HRDN 1–4, TOOL 1–3, SAFE 8–9). Phase numbering continues from v1.43 (last phase 204). Spine: SEED-001 (Spectrum besteffort wash). Cross-cutting SAFE-08 (ATT byte-identical) + SAFE-09 (no controller threshold/algorithm changes) verified at every phase boundary; mechanical closeout in Phase 209. Harness-before-deploy ordering: Phase 206 (A/B harness + rollback gate script) is a prerequisite for Phase 209 production canary. Phase 207 (HRDN-01 fail-closed source-diff verifier) is a prerequisite for SAFE-09 closeout.
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

Stopped at: Completed 206-04-PLAN.md
Resume file: None
Archived Phase 199 evidence: `.planning/milestones/v1.40-phases/199-obs-02-spec-impl-reconciliation/`

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
- [Phase 198-04]: Operator selected blocked closeout after VALN-05a failed; `198-VERIFICATION.md` is status blocked, `ab-comparison.json` has `comparison_verdict: fail`, VALN-04/VALN-05a remain unsatisfied, and SAFE-05 is satisfied by `safe05-diff.json` with zero protected-path diffs.
- [Phase 198-05]: Use /health 1Hz NDJSON as the primary per-run loaded-window evidence source because persisted SQLite raw rows are too sparse for a 500-row 30s gate.
- [Phase 198-05]: Treat throughput/audit FAIL verdicts as completed attempt facts rather than harness crashes so Plan 198-06/07 can make operator decisions from contracted summaries.
- [Phase 198-06]: Operator selected promote for attempt 11 after locked throughput PASS and all three per-run loaded-window audits passed.
- [Phase 198-06]: Attempt 10 remains recorded as retry because throughput failed despite all per-run loaded-window audits passing.
- [Phase 198]: Promoted attempt 11 after source-of-truth recomputation confirmed throughput PASS, all three loaded-window audits pass, regenerated A/B comparison pass, and SAFE-05 clean.
- [Phase 198]: Closed HIGH-3 cascade via fresh per-run dwell-bypass evidence from Plan 198-06 rather than the failing 24h-soak counter.
- [Phase 200-02]: Applied D-09 by superseding only the SAFE-05 warn_bloat/target_bloat v1.40 pins for v1.41 per-direction upload threshold wiring; the seven non-UL pins remain unchanged. — The v1.41 per-direction threshold wiring intentionally added occurrences in wan_controller.py; preserving the other pins keeps SAFE-05 drift detection active.
- [Phase 200-03]: Applied D-08 as daemon startup WARNING emission (not hard-reject) and reused check_unknown_keys so CLI and daemon drift detection stay aligned.
- [Phase 200-03]: Registered existing shipped Spectrum/ATT config paths in KNOWN_AUTORATE_PATHS so SAFE-06 warnings identify real drift instead of already-supported production keys.
- [Phase 200-04]: Applied D-05 by committing Spectrum D-05 upload settings in YAML while preserving the portable controller architecture (deployment-specific behavior remains in config).
- [Phase 200-04]: Applied D-11 by aligning pyproject.toml, wanctl.__version__, and docker/Dockerfile on version 1.41.0.
- [Phase 200-04]: Applied D-12/DOCS-03 by documenting that the new upload threshold keys are startup-only and require `systemctl restart wanctl@<wan>.service`; SIGUSR1 alone does not reload them.
- [Phase 200-05]: Applied D-07 by adding a fail-closed Spectrum upload saturation canary as the primary Plan 06 deploy gate.
- [Phase 200-05]: Applied D-10 by recording the v1.40 /opt/wanctl binary rollback protocol in verdict.json on pass, fail, and abort paths.
- [Phase 200-07]: Blocked the 24h regression soak because Plan 06 canary verdict was fail, not pass; no production soak capture was launched against the rolled-back v1.40 binary.
- [Phase 200]: Per-key presence flags (_upload_target_bloat_ms_explicit, _upload_warn_bloat_ms_explicit) gate live-tuning writes independently; value-derived single flag is the wrong shape (D-03 fix).
- [Phase 200]: SAFE-05 expected counts for warn_bloat/target_bloat were bumped intentionally for v1.41 per-direction wiring; the other seven v1.40 pins remain drift detectors (D-09).
- [Phase 200]: Validator emits WARNING, not hard-reject, on unknown continuous_monitoring keys at startup; this closes the silent-ignore gap that allowed prod spectrum.yaml to carry unrecognized UL keys without an audible warning (D-08, SAFE-06).
- [Phase 200]: Saturation canary at 18 Mbit Spectrum UL is the primary deploy gate per D-07; the 24h regression soak is a watchdog and was blocked because the canary failed.
- [Phase 200]: Rollback protocol predefined per D-10 was executed after the failed canary — /opt/wanctl was restored to v1.40 while YAML stayed in place inactive under the older binary but requiring reconciliation before any future Spectrum deploy/restart.
- [Phase 200]: Spectrum YAML adoption — ceiling 18 Mbit, factor_down_yellow 0.98, target_bloat_ms 42, warn_bloat_ms 105 — was implemented but failed production validation under saturated DOCSIS upload.
- [Phase 200-09]: Operator approved R5+R3 for Plan 200-10 with factor_down_yellow=1.0 and clamp_count=40.
- [Phase 200-11]: Canary helper tests use --self-test dispatch instead of fragile sed-range sourcing, preventing live canary env validation during unit tests.
- [Phase 200-11]: REMOTE_YAML_PATH is restricted to absolute paths matching ^/[A-Za-z0-9._/-]+$ before SSH command construction.
- [Phase 200]: Upload-specific preflight checks fall back to global thresholds like Config resolution but emit an upload row only when at least one upload-side threshold key is present.
- [Phase 200]: The WR-01 gap was closed in tests/test_check_config.py because tests/test_check_config_validators.py is a stale planned path.
- [Phase 200-13]: Closed WR-03 with direct Docker package-directory copy (`COPY src/wanctl /opt/wanctl/wanctl`) while preserving `PYTHONPATH=/opt/wanctl`.
- [Phase 200-13]: Repo-root `.dockerignore` is the correct location because the canonical Docker build context is `docker build -f docker/Dockerfile .`.
- [Phase 200-10]: Implemented approved R5+R3 only: Spectrum factor_down_yellow=1.0 and upload_consecutive_yellow_decay_clamp=40; R1/R2/R4 remain unimplemented.
- [Phase 200-10]: Consecutive-YELLOW clamp defaults to 0 for byte-identical behavior when absent and resets on any non-YELLOW zone while preserving immediate RED decay.
- [Phase 200]: Attempt 3 canary verdict=fail triggered immediate D-10 rollback; Task 4 soak was skipped per fail-closed branch semantics. — VALN-06 requires zero loaded-window floor hits; Attempt 3 had 4 floor samples despite improvement from Attempt 2.
- [Phase 200]: Plan 200-15 should close Phase 200 as gaps_found. — The canary failed and the 24h soak was correctly skipped after rollback.
- [Phase 200 gap closure]: Operator-provided Plan 200-15 execution context selected the Category B closeout branch: close Phase 200 as `gaps_found` based on Plan 200-14 Attempt 3 canary fail (4 UL floor hits), rollback from `/opt/wanctl-prephase200-gap-20260504T132936Z.tar.gz`, and skipped soak. VALN-06 remains unsatisfied; a second gap-closure cycle requires a new operator decision.
- [Phase 200 closure 2026-05-04]: Operator escalated VALN-06 to Phase 201 (`docsis-aware-ul-congestion-control`) as an inherited blocking requirement rather than entering a second Phase 200 gap-closure cycle. Rationale: Phase 200's RETRO concluded the per-direction-thresholds hypothesis is the wrong fix; the residual 4 loaded-window floor hits live in a shaping-headroom regime that is Phase 201's seeded scope. No second remediation attempted; no production binary change (Spectrum on v1.40); v1.41 YAML keys remain on prod /etc/wanctl/spectrum.yaml inactive under v1.40 but MUST be reconciled before any future Spectrum deploy/restart — a Phase 201 predeploy gate is required.
- [Phase 201-02]: Wave 0 RED scaffolding is complete; production-code plans 201-03 through 201-08 now have named pytest contracts to satisfy before controller/config/canary behavior can ship.
- [Phase 201-02]: Importable Phase 201 stubs use strict xfail or natural missing-symbol failures rather than skip-only placeholders; only the absent predeploy shell script uses function-level skips until Plan 201-07 creates it.
- [Phase 201-02]: `201-VALIDATION.md` now marks `wave_0_complete: true`; downstream implementation plans must remove their matching `Wave 0 stub` markers as they land GREEN behavior.
- [Phase 201-03]: Kept setpoint_mbps required-when-docsis-mode in imperative Config validation rather than schema required=true, preserving byte-identical legacy YAML defaults.
- [Phase 201-03]: Mirrored check-config validation separately from Config.__init__ so offline diagnostics report DOCSIS setpoint errors without relying on daemon construction.
- [Phase 201-03]: SAFE-05 Phase 201 occurrence pins count grep-style matching lines across src/wanctl while preserving original wan_controller.py v1.41 drift pins verbatim.
- [Phase 201-09]: Accepted Codex BLOCK verdict; Wave 1+ is paused until HIGH amendments land for floor-hit counter placement, DOCSIS YELLOW/R5+R3 semantics, replay threshold fidelity, Spectrum-only predeploy gate wiring, and fail-closed Phase 201 canary env enforcement.
- [Phase 201-09]: Setpoint 12 remains an explicit canary-validated assumption, not a Spectrum-sweep-proven value.
- [Phase 201-04]: Task 3 checkpoint revised the Attempt 3 replay contract: the 20x hold-last replay records 1003 RED-heavy floor-hit cycles under exact RED fast-trip and post-bounds floor-hit accounting, so it is a safety diagnostic rather than synthetic VALN-06 closure; Plan 201-11 live canary remains the closure gate.
- [Phase 201-07]: Implemented D-15 as fail-closed operator-manual reconciliation rather than auto-strip; the predeploy gate is read-only and blocks rejected v1.41 upload `target_bloat_ms` / `warn_bloat_ms` before Spectrum deploy.
- [Phase 201-07]: Scoped deploy preflight to `WAN_NAME=spectrum`; ATT and other non-Spectrum deploys skip the gate without inspecting `/etc/wanctl/spectrum.yaml`.
- [Phase 201-07]: VALN-06 remains open because Plan 201-07 delivers deploy safety only; Plan 201-11 live canary and Plan 201-12 soak remain the closure gates.
- [Phase 201-08]: Phase 201 canary mode is fail-closed unless PHASE201_DOCSIS_MODE=true and PHASE201_SETPOINT_MBPS=12 are set; empty Phase 201 vars do not imply legacy mode.
- [Phase 201-08]: Legacy A/B compatibility requires explicit PHASE201_LEGACY_MODE=true and is mutually exclusive with DOCSIS mode.
- [Phase 201-08]: Canary pass/fail verdicts use floor_hit_cycles_total_delta_loaded_window as the primary gate and fail on disagreement with the legacy 1 Hz snapshot count.
- [Phase 201-08]: max_delay_delta_us is already serialized through CakeSignalSnapshot and the wan_controller.py cake_signal.upload payload, so no controller code change was needed for canary captures.
- [Phase 201-10]: Codex stop-time review returned GO WITH FOLLOW-UPS with no HIGH findings; Plan 201-11 canary may proceed if PHASE201_LOCAL_YAML_OVERRIDE is confirmed unset before deploy/canary.
- [Phase 201-10]: Deferred the max_delay_delta_us public /health serialization gap as non-blocking for VALN-06 because the live canary gate uses floor_hit_cycles_total_delta_loaded_window plus ul_floor_hits_during_load, not max_delay_delta_us.
- [Phase 201-11]: Canary at setpoint_mbps=12 failed the primary VALN-06 gate with floor_hit_cycles_total_delta_loaded_window=1453 and ul_floor_hits_during_load=84 (`reason: ul_floor_hits_during_load_84_counter_delta_1453`); both gates reported floor hits, so rollback was required and completed.
- [Phase 201-11]: Rollback restored both `/opt/wanctl` from `/opt/wanctl-prephase201-20260504T231220Z.tar.gz` and `/etc/wanctl/spectrum.yaml` from `/etc/wanctl/spectrum.yaml.prephase201-20260504T231220Z`; post-rollback `/health.version` was 1.39.0 and checked Phase 201 YAML key counts were all zero.
- [Phase 201-11]: Plan 201-12 must not proceed after the failed canary unless an explicit operator decision creates a setpoint_mbps=10 reattempt path or gap-closure planning.
- [Phase 201-13]: Upload `/health` diagnostics now expose `zone_trace`, `max_delay_delta_us`, anti-windup counters, and red-decay runtime knob echoes without DOCSIS gating.
- [Phase 201-13]: `sustained_red_cycles` remains absent from serialization to preserve Plan 201-14 rev 4 Option B coordination.
- [Phase 201-14]: Bounded-absolute RED decay holds at a validator-proven clamp above floor under DOCSIS mode; legacy docsis_mode=false remains multiplicative and byte-identical.
- [Phase 201-14]: Red-decay config now fails closed when step/delta ordering is unsafe or DOCSIS clamp is at/below floor.
- [Phase 201]: Plan 201-15 PASS selected; re-canary primary_gate_value=0 and ul_floor_hits_during_load=0, unblocking Plan 201-16 with T+0 floor-hit baseline 0.
- [Phase 201]: Plan 201-15 validated the two-snapshot rollback strategy: Snapshot A is rollback-clean before reconcile; Snapshot B is post-gate deploy evidence only.
- [Phase 201]: Plan 201-16 24h soak `20260505T132736Z` failed because plan-defined gates disagreed: D-19 primary gate passed with `floor_hit_cycles_total_delta_soak_window=0`, but preserved D-14 secondary watchdog failed with `ul_hysteresis_suppression_rate_per_60s_mean=6.466842364880155` against `<5.0`. D-19 approval was captured pre-soak in `201-16-OPERATOR-APPROVAL-D19.md`; next action requires operator decision between A5-style reattempt and v1.43+ follow-up.
- [Phase 201 closure 2026-05-06]: Operator Route B selected. Phase 201 closes gaps_found; D-19 primary VALN-06 floor-hit gate PASSED on canary 20260505T122513Z and 24h soak 20260505T132736Z (v1.42.1 in production). D-14 secondary suppression watchdog FAIL classified as metric_semantics_and_recalibration on the YELLOW-edge dwell-hold path (queue_controller.py:348), unrelated to bounded RED decay (queue_controller.py:361-376). D-14 deferred to v1.43+ as four ordered backlog items: SEED-002 (suppression-counter metric semantics fix), SEED-003 (D-14 successor recalibration), SEED-004 (target-edge churn instrumentation), SEED-005 (conservative tuning sweep, gated). Order is load-bearing — items 1-3 are prerequisites to item 4. No production binary or YAML change in Plan 201-17. Milestone v1.42 ready for /gsd-complete-milestone.
- [Phase 202-02]: METRIC-03 replay oracle uses strict reset-boundary detection over the v1.42 `suppressions_per_min` snapshots; the observable completed-window distribution is 1,331 windows with mean 13.890308039068369/min, p95 41, and max 124.
- [Phase 202-02]: `suppression-stats.json::window_count=1439` is treated as a nominal elapsed-window count, not the observable reset-boundary count, because zero-suppression windows do not create a decreasing edge in the live counter snapshots.
- [Phase 202-03]: Corrected Phase 201 SAFE-05 expected counts to the shipped `v1.42` tag values before adding v1.43 pins: docsis_mode=36, setpoint_mbps=35, integral_window_seconds=10, integral_threshold_ms_s=13, cake_backlog_low_threshold_bytes=10, cake_delay_delta_low_threshold_us=10.
- [Phase 202-03]: METRIC-04 v1.43 SAFE-05 pins were established line-by-line across `src/wanctl/**/*.py`: _record_suppression=4, _window_suppressions_by_cause=6, _lifetime_suppressions_by_cause=3, _last_completed_window_total=3, _last_completed_window_by_cause=3, suppressions_completed_window_count=3, suppressions_completed_window_by_cause=3, suppressions_lifetime_by_cause=3.
- [Phase 202-04]: Chose `v1.43-dev` for the CHANGELOG heading, placed `Suppression metric semantics (v1.43)` under DOCSIS-aware UL control docs, and corrected active fixture references to the canonical `.planning/milestones/v1.42-phases/201-docsis-aware-ul-congestion-control/soak/20260505T132736Z/soak-capture.ndjson` path.
- [Phase 203-01]: Promoted the v1.42 evidence-only soak capture script into a public-safe, versioned harness requiring HEALTH_URL from the operator environment.
- [Phase 203-01]: Capture-projection tests extract the jq object literal from `scripts/soak-capture.sh` before running synthesized `/health` payloads, keeping the script as the single projection source of truth.
- [Phase 203-02]: Used Option (b) for Phase 202 helper handling: compatible helper logic now exists in `scripts/soak_summary_aggregate.py`, while `tests/test_phase_202_replay.py` remains unchanged to minimize replay-canary churn.
- [Phase 203-02]: Kept the new aggregator diagnostic-only: `diagnostic_distribution.load_rtt_delta_us` and `load_rtt_delta_us_by_zone_cause` landed, while secondary-gate computation remains Phase 204/CALIB-03 territory.
- [Phase 203-03]: Documented the soak harness in `docs/SOAK_HARNESS.md` with the full NDJSON row schema, `soak-summary.json` schema, histogram bucket semantics, dual-attribution policy, upload-only zone axis, and harness-only SAFE-07 invariant.
- [Phase 203-03]: Added `scripts/check-safe07-source-diff.sh` as the reusable SAFE-07 gate. It defaults to Phase 202 close ref `b72b463`, supports CLI and `PHASE_202_CLOSE` overrides, and uses `c8a506d` as the known-violating sanity ref in the current repo graph.
- [Phase 203]: Phase verification passed 8/8 must-haves; `load_rtt_delta_us` capture, summary aggregation, deterministic replay fixtures, docs, changelog, and SAFE-07 gate are implemented without `src/wanctl/**` changes.
- [Phase 203]: Code review warnings WR-01 and WR-02 are non-blocking residual risks: harden `scripts/check-safe07-source-diff.sh` for staged/unstaged `src/wanctl/` diffs and make `scripts/soak-capture.sh` resilient to transient per-sample fetch/projection failures before unattended production soaks.
- [Phase 204-01]: Deploy 1 used Spectrum-bound health endpoint http://10.10.110.223:9101/health because this deployment does not bind /health to localhost.
- [Phase 204-01]: SAFE-07 allows only the exact planned src/wanctl/__init__.py version bump from 1.42.1 to 1.43.0; all other src/wanctl diffs remain violations.
- [Phase 204-02]: Accepted CALIB-01 line count 84098 < 86000 as a documented deviation because operator approved no extension and stronger quality checks passed: full 86400s wall-clock, zero parse errors, zero missing minute buckets, 97.335648% coverage, 1343 completed-window value changes, and floor-hit delta 0.
- [Phase 204-02]: CALIB-01 distribution handoff values are top-level p99=82.0, dwell_hold_p99=70.25999999999999, backlog_recovery_p99=75.77, max=119, window_count=669 for Plan 204-03.
- [Phase 204-03]: CALIB-02 approved p99 with threshold 125, headroom_factor 1.5, rounding_policy ceil_to_nearest_25, and gate_column by_cause.dwell_hold.
- [Phase 204-03]: The open-Q2 slice-vs-total decision gates against by_cause.dwell_hold to preserve the original D-14 dwell-hold watchdog semantics while total/backlog remain informational.
- [Phase 204]: Plan 204-04 Deploy 2 is harness-only: git commits only, with no production binary, YAML, or capture-script change.
- [Phase 204]: Plan 204-04 CALIB-03 gates the D-14 successor on scripts/calib_02_threshold.json values: p99 threshold 125 against by_cause.dwell_hold.
- [Phase 204]: Plan 204-04 v1.43 emits both secondary_gate_legacy and secondary_gate_completed_window; legacy is informational and drops in v1.44 follow-up.
- [Phase 204]: CALIB-04 accepted the 84079-line capture despite the >=86000 proxy miss because operator-approved stronger quality checks passed: full 24h wall-clock, zero parse errors, 1441 minute buckets, 1361 completed-window changes, and floor-hit delta 0.
- [Phase 204]: CALIB-04 PASS used primary_gate.delta=0 plus secondary_gate_completed_window p99 dwell-hold value 68.0 <= threshold 125; legacy secondary gate remains informational only.
- [Phase 204]: Plan 204-06 closed CALIB-05 by recording threshold-basis hygiene in `204-RETRO.md` and created the v1.44 follow-up TODO to drop `secondary_gate_legacy` and consider CALIB-02 YAML promotion.
- [Phase 204]: SAFE-07 closeout checklist passed at v1.43 ship: SAFE-07 source diff, SAFE-05 pin block, hot-path slice, phase-scoped slice, and full suite all green.
- [Phase 204 re-verification 2026-05-09]: Code-review remediation commit `d44e2fd` fixed completed-window aggregation by requiring `ul_hysteresis_window_start_epoch`; this invalidated pre-fix CALIB-01 (`20260507T131911Z`) and CALIB-04 (`20260508T161146Z`) captures because they lack the boundary marker. `204-VERIFICATION.md` is now `gaps_found`; rerun corrected-boundary CALIB-01, revisit CALIB-02, and rerun CALIB-04 before v1.43 archive.
- [Phase 204-07]: Launched corrected-boundary CALIB-01 rerun soak `20260509T183037Z` on cake-shaper using `HEALTH_URL=http://10.10.110.223:9101/health`; pre-soak `floor_hit_cycles_total=0`, version `1.43.0`, and first rows included `ul_hysteresis_window_start_epoch`.
- [Phase 204-07]: Accepted corrected-boundary CALIB-01 rerun `20260509T183037Z` despite the 84100-row line-count proxy miss because continuation approval acknowledged the row count and stronger checks passed: parse errors 0, missing boundary markers 0, `valid=true`, and `window_count=1440`.
- [Phase 204-07]: Plan 204-08 should re-evaluate CALIB-02 from corrected values: top-level p99=105.2199999999998, dwell_hold_p99=95.2199999999998, dwell_hold_mean=14.702083333333333, backlog_recovery_mean=2.4298611111111112.
- [Phase 204]: Branch B selected for CALIB-02 after corrected-boundary CALIB-01 materially changed the threshold basis; threshold re-approved at p99 × 1.5 ceil-to-nearest-25 = 150 against by_cause.dwell_hold. — Tests 1, 2, and 3 failed: recomputed gate moved to 150, backlog/dwell mean ratio fell to 0.165, and dwell_hold p99 moved by 35.5%.
- [Phase 204]: scripts/calib_02_threshold.json now points at corrected CALIB-01 soak 20260509T183037Z and mirrors the approval artifact values. — Plan 204-09 must consume current Branch B constants: statistic=p99, threshold=150, headroom_factor=1.5, gate_column=by_cause.dwell_hold.
- [Phase 204-09]: CALIB-04 rerun `20260510T203642Z` completed with corrected boundary markers and operator accepted the 84,097-row proxy miss; boundary-marker missing rows were 0, primary_gate.delta=0, and secondary_gate_completed_window p99 dwell-hold was 151.0 against threshold 150.
- [Phase 204-09]: Operator verdict recorded exactly as FAIL-A just-over (`secondary_value=151.0`, `secondary_threshold=150`); next action is Branch A — re-approve CALIB-02 at a higher threshold and rerun CALIB-04.
- [Phase 204-09 Branch A continuation]: Operator re-approved CALIB-02 threshold at `175`, the next ceil-to-nearest-25 threshold above observed completed-window p99 dwell-hold `151.0`; preserved `statistic=p99`, `headroom_factor=1.5`, `rounding_policy=ceil_to_nearest_25`, and `gate_column=by_cause.dwell_hold`. Plan 204-10 remains blocked until a subsequent CALIB-04 rerun produces `verdict: pass`.
- [Phase 204-09 Branch A continuation]: Launched CALIB-04 rerun `20260512T004208Z` on cake-shaper using `HEALTH_URL=http://10.10.110.223:9101/health`; production version `1.43.0`, pre-soak floor-hit baseline `0`, threshold `175`, and first rows included `ul_hysteresis_window_start_epoch`. Remote capture path is `/var/tmp/wanctl-soak-20260512T004208Z/soak-capture.ndjson`.
- [Phase 204-09 Branch A continuation]: CALIB-04 rerun `20260512T004208Z` passed the dual gate at threshold `175`: row count `84099` (strict proxy miss accepted via continuation prompt with stronger checks), parse errors `0`, boundary-marker missing rows `0`, wall-clock span `23:59:59`, boundary span `23:59:54.820912`, primary_gate.delta `0`, secondary_gate_completed_window value `135.6199999999999`, and verdict updated to `pass`. Plan 204-10 remains a separate closeout refresh.
- [Phase 204-10]: Used the latest PASS verdict from CALIB-04 threshold-175 rerun `20260512T004208Z` as the closeout truth source; earlier `20260510T203642Z` FAIL-A and `20260508T161146Z` pre-boundary pass are superseded provenance only. Phase 204/v1.43 is satisfied after SAFE-07, phase-scoped, hot-path, focused projection, and full-suite verification passed.
- [Phase 205-01]: Plan 01 is tests-only; RED behavior tests intentionally fail until Plans 02/03, while GREEN invariant guards establish the baseline and production `src/wanctl/` remains untouched.
- [Phase 205-01]: Diffserv4 byte-identity pinned literal values are drop_rate=175.0, total_drop_rate=180.0, backlog_bytes=75000, peak_delay_us=5000, avg_delay_us=4000, base_delay_us=1000, max_delay_delta_us=3000.
- [Phase 205-02]: Active CAKE aggregation now uses _active_tin_indices(tin_count): single-tin besteffort includes index 0, while multi-tin diffserv continues excluding Bulk index 0.
- [Phase 205-02]: Total aggregation sites remain all-tin range(len(tins_raw)) iterations; only active aggregation sites changed.
- [Phase 205-02]: The single-tin label heuristic only rewrites the default four-name list to BestEffort; operator-supplied tin_names pass through unchanged.
- [Phase 205-03]: allow_wash uses strict `is True` parsing so string/operator typos do not truthily bypass D-08 wash protection.
- [Phase 205-03]: linux_cake emits explicit `nowash` when `wash` is present and false, mirroring `no-ack-filter` for operator auditability.
- [Phase 205-03]: Phase 205 remains emission-only; `build_expected_readback()`, `_VALIDATE_KEY_TO_TCA`, and `_DIFFSERV_NAME_TO_INT` are deferred to Phase 209.
- [Phase 205]: Plan 04 SAFE-09 closeout verified the cumulative Phase 205 source diff against v1.43 close (6508d68): exactly the operator-approved 5-file TOPO-01/TOPO-02 set, empty value-invariance grep, and Phase 209 readback/diffserv deferrals untouched.
- [Phase 206-01]: A/B replay harness reuses Phase 193 controller/replay primitives by import; pre-migration 940M is a post-construction ceiling override, not a redefined factory.
- [Phase 206-01]: Default harness output labels controller-derived metrics with meta.metric_source=controller_replay; paired flent .gz inputs are required for real RRUL p99/throughput/jitter fields.
- [Phase 206-01]: Golden NDJSON fixture keeps only five replay-safe fields from the locked 2026-04-29 flent capture; raw flent metadata remains out of git.
- [Phase 206-02]: Threshold constants for TOPO-05 live in scripts/phase206-thresholds.json and are loaded by the Python core via load_thresholds().
- [Phase 206-02]: The Python gate core remains SSH-free; NRestarts sampling and SSH target validation live in the bash wrapper.
- [Phase 206-02]: Post-soak mode is fail-closed and requires all inputs plus both gate_baseline rate fields.
- [Phase 206-03]: Rollback docs cite scripts/phase206-thresholds.json as the threshold source of truth while inlining 5.0/10.0/10.0 for operator readability; Plan 04 verifies doc-vs-JSON drift.
- [Phase 206-03]: Golden fixture provenance records the operator-accepted 2026-04-29 substitute for the missing 2026-04-22 finding and pins SHA256 68f99440bd41be646dfa64abe77380791d4b2dd7b09722588c808e9749c0bbda.
- [Phase 206-04]: SAFE-09 closeout evidence covers committed, staged/index, unstaged worktree, and untracked src/wanctl/ surfaces; the only source diff remains the Phase 205 five-file allowlist.
- [Phase 206-04]: Rollback threshold doc values were verified against scripts/phase206-thresholds.json; JSON remains the source of truth for 5.0/10.0/10.0.

## Performance Metrics

- 2026-05-15: Phase 206 Plan 04 completed in 6m22s across 2 verification tasks and 2 planning files; SAFE-09 boundary evidence now covers committed, staged/index, unstaged worktree, and untracked `src/wanctl/` surfaces, the committed/index surfaces match the Phase 205 five-file allowlist, unstaged and untracked counts are both 0, threshold docs match `scripts/phase206-thresholds.json`, full suite passed with 5027 passed / 6 skipped / 2 deselected, hot-path slice passed with 673 tests, and Phase 206 focused slice passed with 32 tests.
- 2026-05-15: Phase 206 Plan 02 completed in ~25m across 3 tasks and 6 created files; scripts/phase206-thresholds.json now owns the TOPO-05 5.0/10.0/10.0 thresholds, the Python gate core is SSH-free with fail-closed gate_baseline mismatch handling, the bash wrapper owns NRestarts SSH sampling and path/target validation, focused gate tests passed with 17 tests, full suite passed with 5027 passed / 6 skipped / 2 deselected, dry-run baseline-vs-self exited 0, and SAFE-09 source diff remained at the Phase 205 5-file allowlist.
- 2026-05-15: Phase 206 Plan 03 completed in 4m07s across 2 documentation tasks and 2 created planning artifacts; rollback gates doc now covers RRUL p99, daemon restart-rate, and pressure-transition-rate triggers with JSON-sourced thresholds inlined for readability, fixture provenance pins the accepted 2026-04-29 substitution with SHA256 `68f99440bd41be646dfa64abe77380791d4b2dd7b09722588c808e9749c0bbda`, and SAFE-09 source diff remained at the Phase 205 5-file allowlist.
- 2026-05-15: Phase 206 Plan 01 completed in 11m across 3 tasks and 6 created files; deterministic golden fixture has 350 rows with SHA256 `68f99440bd41be646dfa64abe77380791d4b2dd7b09722588c808e9749c0bbda`, `_replay_samples` consumed all 350 rows, focused Phase 206 tests passed with 15 tests, full suite passed with 5010 passed / 6 skipped / 2 deselected, and SAFE-09 source diff remained at the Phase 205 5-file allowlist.
- 2026-05-14: Phase 205 Plan 04 completed in ~11m across 2 tasks and 2 planning artifacts; SAFE-09 cross-plan diff scope matched the operator-approved 5-file set, value-invariance grep was empty, Phase 209 deferrals stayed untouched, full suite passed with 4995 passed / 6 skipped / 2 deselected, replay passed with 48 passed / 6 skipped, byte-identity guard passed, hot-path passed with 673 tests, and ruff/mypy were clean.
- 2026-05-14: Phase 205 Plan 03 completed in 5m53s across 4 tasks and 4 source files; `allow_wash` now uses strict-bool default-false gating, `wash`/`nowash` emission reaches linux subprocess and netlink kwargs including docsis fallback, validator unknown-key warnings are suppressed for `cake_params.allow_wash` and `cake_params.wash`, ruff/mypy passed, the 330-test plan slice passed, and the hot-path slice passed with 673 tests.
- 2026-05-14: Phase 205 Plan 02 completed in 5m30s across 1 task and 1 source file; `cake_signal.py` now uses `_active_tin_indices()` for active aggregation, single-tin besteffort RED gates are green, diffserv4 literal byte-identity and Phase 193/194/195 replay gates passed, ruff/mypy passed, and SAFE-09 file-scoped checks found no threshold/EWMA/dwell/deadband/burst value changes.
- 2026-05-14: Phase 205 Plan 01 completed in 7m05s across 4 tasks and 5 test files; 14 Phase 205 tests were added/extended, RED behavior gates fail as expected for Plans 02/03, GREEN invariant guards pass, and `git diff HEAD -- src/wanctl/` is empty.
- 2026-05-12: Phase 204 Plan 09 completed corrected-boundary CALIB-04 rerun `20260510T203642Z`; 84,097 rows were accepted despite the >=86,000 proxy miss, boundary-marker missing rows were 0, primary_gate.delta=0, secondary_gate_completed_window value was 151.0 vs threshold 150, verdict FAIL-A just-over was recorded in `204-05-CALIB-04-SOAK-VERDICT.md`, SAFE-07 passed, and the hot-path slice passed with 667 tests.
- 2026-05-12: Phase 204 Plan 09 Branch A continuation reapproved CALIB-02 at threshold 175 after the just-over FAIL-A (`151.0` vs `150`), preserving p99/headroom/rounding/gate-column semantics and keeping Plan 204-10 blocked pending a PASS rerun verdict.
- 2026-05-12: Phase 204 Plan 09 Branch A continuation launched CALIB-04 rerun `20260512T004208Z` with `threshold=175`, `PRE_FH=0`, health URL `http://10.10.110.223:9101/health`, remote tmux `wanctl-soak` running, initial line count 5, and boundary marker present in first rows; post-24h aggregation is pending.
- 2026-05-13: Phase 204 Plan 09 Branch A continuation completed post-24h aggregation for `20260512T004208Z`; 84,099 rows were accepted after row-proxy disclosure, parse errors were 0, missing boundary markers were 0, primary_gate.delta was 0, secondary_gate_completed_window value was 135.6199999999999 vs threshold 175, the dual gate passed, SAFE-07 passed, and the hot-path slice passed with 667 tests.
- 2026-05-10: Phase 204 Plan 08 completed CALIB-02 Branch B re-evaluation after corrected-boundary CALIB-01 `20260509T183037Z`; material-change tests 1/2/3 failed, threshold was re-approved from 125 to 150 using p99 × 1.5 ceil-to-nearest-25 against `by_cause.dwell_hold`, artifact/JSON mirror passed, SAFE-07 passed, and the hot-path slice passed with 667 tests.
- 2026-05-10: Phase 204 Plan 07 completed over the corrected-boundary CALIB-01 rerun soak `20260509T183037Z`; 84,100 rows were accepted after continuation approval despite the >=86,000 proxy miss because parse errors were 0, missing boundary-marker rows were 0, the current aggregator returned `valid=true` with `window_count=1440`, top-level p99 was 105.2199999999998, dwell_hold p99 was 95.2199999999998, SAFE-07 passed, and the hot-path slice passed with 667 tests.
- 2026-05-09: Phase 204 Plan 05 completed over a 24h CALIB-04 verification soak plus active aggregation/verdict work; soak `20260508T161146Z` produced 84,079 lines accepted by operator deviation after full-wall-clock/zero-parse/1441-minute-bucket/1361-completed-window-change checks passed, primary floor-hit delta stayed 0, secondary completed-window p99 dwell-hold value was 68.0 against threshold 125, dual-gate verdict was PASS, SAFE-07 stayed clean, and the hot-path slice passed with 667 tests.
- 2026-05-09: Phase 204 Plan 06 completed milestone closeout; `204-VERIFICATION.md`, `204-VALIDATION.md`, `204-RETRO.md`, and the v1.44 follow-up TODO were written; SAFE-07 source diff passed, SAFE-05 pin block passed, hot-path passed with 667 tests, phase-scoped slice passed with 70 tests, and the full suite passed with 4976 passed / 6 skipped / 2 deselected.
- 2026-05-09: Phase 204 re-verification after code review found gaps: the corrected aggregator fails closed on old CALIB-01/CALIB-04 captures without `ul_hysteresis_window_start_epoch`. Remediation tests passed with 71 phase/regression tests and hot-path passed with 667 tests; production evidence must be recaptured.
- 2026-05-08: Phase 204 Plan 04 completed in ~7min across 4 tasks and 8 plan-scoped files; `aggregate_watchdog()` and `load_calib_02_constants()` landed, v1.42 legacy oracle replay passed at `6.466842364880155`, CALIB-02 constants (`p99`, threshold `125`, `gate_column=by_cause.dwell_hold`) now drive `secondary_gate_completed_window`, Phase 202/203/204 replay tests passed with 60 tests, hot-path passed with 667 tests, SAFE-05 pin passed, SAFE-07 stayed clean, and `scripts/soak-capture.sh` remained unchanged for harness-only Deploy 2.
- 2026-05-08: Phase 204 Plan 03 completed in ~4min active continuation after the operator checkpoint; CALIB-02 approved `p99`, threshold `125`, headroom_factor `1.5`, rounding_policy `ceil_to_nearest_25`, and gate_column `by_cause.dwell_hold`; the approval artifact and `scripts/calib_02_threshold.json` mirror were committed, artifact/JSON cross-check passed, SAFE-07 stayed clean, and the hot-path slice passed with 667 tests.
- 2026-05-08: Phase 204 Plan 02 completed over a 24h wall-clock CALIB-01 baseline soak plus ~35min active execution; `aggregate_completed_window_distribution()` and Phase 204 replay fixtures landed, 84,098 samples were accepted with documented operator deviation from the 86,000 line proxy after full-wall-clock/zero-parse/zero-missing-minute checks passed, top-level p99=82.0 with dwell_hold_p99=70.25999999999999 and backlog_recovery_p99=75.77, floor-hit delta stayed 0, the phase replay slice passed with 26 tests, hot-path passed with 667 tests, and SAFE-07 stayed clean.
- 2026-05-06: Phase 203 verified complete with 8/8 must-haves satisfied; `203-VERIFICATION.md` passed, SAFE-07 was clean against `b72b463`, and the verifier re-ran the phase-scoped slice with 56 passed plus hot-path regression with 667 passed.
- 2026-05-06: Phase 203 Plan 02 completed in ~4min across 4 tasks and 5 new/modified files; `scripts/soak_summary_aggregate.py` now emits `diagnostic_distribution.load_rtt_delta_us` plus upload zone × cause histograms, `tests/test_phase_203_replay.py` passed with 12 tests, Phase 202 replay stayed green, the hot-path slice passed with 667 tests, and `git diff b72b463 -- src/wanctl/` stayed empty.
- 2026-05-06: Phase 203 Plan 03 completed in ~7min across 4 tasks and 3 new/modified files; `docs/SOAK_HARNESS.md` documents the soak harness schema and SAFE-07 invariant, `CHANGELOG.md` v1.43-dev now lists Phase 203 additions, `scripts/check-safe07-source-diff.sh` passed against `b72b463`, the hot-path slice passed with 667 tests, the phase-scoped slice passed with 56 tests, and the full suite passed with 4962 tests, 6 skipped, 2 deselected.
- 2026-05-06: Phase 203 Plan 01 completed in ~2min across 3 tasks and 2 new files; `scripts/soak-capture.sh` now emits the seven v1.43 target-edge churn NDJSON fields, `tests/test_phase_203_capture_projection.py` passed with 10 tests, the hot-path slice passed with 667 tests, SAFE-05 pin check passed, and `git diff b72b463 -- src/wanctl/` stayed empty.
- 2026-05-06: Phase 202 Plan 02 completed in ~2min across 3 tasks and 1 new test file; `tests/test_phase_202_replay.py` passed with 9 tests, the v1.42 oracle computed 84,117 samples, 1,331 observable completed windows, mean 13.890308039068369/min, p95 41.0, max 124, the hot-path slice passed with 667 tests, and SAFE-07 source diff was 0 lines under src/wanctl.
- 2026-05-06: Phase 202 Plan 03 completed in ~2min across 4 tasks and 1 modified test file; `tests/test_phase_195_replay.py` passed with 25 tests, the hot-path slice passed with 667 tests, only `tests/test_phase_195_replay.py` changed since Plan 202-02, and `src/wanctl/wan_controller.py` diff stayed 0 lines.
- 2026-05-06: Phase 202 Plan 04 completed in ~2min across 5 tasks and 5 docs/planning files; CHANGELOG.md and docs/CONFIGURATION.md now document the v1.43 additive suppression metric fields, watchdog-gate warning, and per-cycle backlog-recovery accounting, active fixture paths were corrected, the hot-path slice passed with 667 tests, and this plan introduced 0 `src/wanctl/**` diff lines.
- 2026-05-05: Phase 201 Plan 15 completed the re-canary PASS path in ~30min active continuation over a ~1h30m deploy/canary evidence window; v1.42.1 was deployed with all version surfaces aligned, Snapshot A rollback-clean and Snapshot B deploy-evidence were validated, the saturation canary `20260505T122513Z` passed with `primary_gate_value=0` and `ul_floor_hits_during_load=0`, and Plan 201-16 is unblocked with T+0 floor-hit baseline 0.
- 2026-05-06: Phase 201 Plan 16 completed the 24h soak evidence computation for `20260505T132736Z`; 84,117 samples were copied back from cake-shaper with 0.973584 coverage, D-19 primary floor-hit delta passed at 0, D-14 secondary suppression mean failed at 6.466842364880155 per 60s, anti-windup trigger delta was 0, and Phase 201 remains gaps_found pending operator next-action decision.
- 2026-05-05: Phase 201 Plan 14 completed in ~11min across 4 tasks and 10 plan-scoped files; DOCSIS RED now uses bounded-absolute setpoint-relative decay with an 18-cycle floor-hit-free replay, anti-windup caps stuck integrals below threshold, daemon/check-config validators reject unsafe red-decay knobs, plan regression slice passed with 833 tests, and package mypy passed.
- 2026-05-05: Phase 201 Plan 13 completed in ~18min across 2 TDD tasks and 4 source/test files; upload health diagnostics now expose zone_trace, max_delay_delta_us, red_streak, anti-windup counters, and red_decay_* runtime knob echoes; QueueController diagnostics passed with 13 tests, health payload diagnostics passed with 10 tests, and hot-path slice passed with 635 tests.
- 2026-05-04: Phase 201 Plan 11 completed as blocked/failed after live canary `20260504T231334Z`; predeploy reconciliation/deploy succeeded, but the 1022s loaded canary failed VALN-06 with floor_hit_cycles_total_delta_loaded_window=1453 and ul_floor_hits_during_load=84; D-10 rollback restored binary and YAML to predeploy snapshots and post-rollback health reported version 1.39.0.
- 2026-05-04: Phase 201 Plan 10 completed in 11min across 1 Codex stop-time review gate and 5 planning/context files; Codex returned GO WITH FOLLOW-UPS with no HIGH findings, full suite passed with 4864 tests, and Plan 201-11 may proceed after confirming PHASE201_LOCAL_YAML_OVERRIDE is unset.
- 2026-05-04: Phase 201 Plan 08 completed in 7min across 3 tasks and 5 plan-scoped files; the reused saturation canary now fails closed for Phase 201 env (`PHASE201_DOCSIS_MODE=true`, `PHASE201_SETPOINT_MBPS=12`), keeps legacy A/B behind explicit `PHASE201_LEGACY_MODE=true`, gates verdicts on floor-hit counter deltas, and passed 26 canary script tests.
- 2026-05-04: Phase 201 Plan 07 completed in 3min across 2 tasks plus cleanup and 5 plan-scoped files; Spectrum predeploy gate now blocks rejected v1.41 upload threshold keys before rsync, ATT/non-Spectrum deploys skip without inspecting Spectrum YAML, and the focused predeploy test suite passed with 11 tests.
- 2026-05-04: Phase 201 Plan 04 completed after checkpoint continuation in ~9min active Task 3 time across 3 total tasks and 7 plan-scoped files; DOCSIS QueueController internals landed, Attempt 3 replay now pins the 1003-cycle RED-heavy floor-hit diagnostic, SAFE-05 pins passed, hot-path slice passed with 604 tests, and the full suite passed with 4828 tests.
- 2026-05-04: Phase 201 Plan 09 completed in 4min across 1 Codex review gate and 4 planning/tracking files; Codex returned BLOCK with 5 HIGH, 3 MED, and 1 LOW comments, all HIGH comments were accepted, and Wave 1+ is paused pending plan amendments.
- 2026-05-04: Phase 201 Plan 03 completed in 21min across 3 tasks and 5 files; DOCSIS-mode upload schema keys, presence flags, fail-closed Config/check-config setpoint validation, SAFE-06 registration, and SAFE-05 v1.42 source occurrence pins landed; targeted schema/validator tests, SAFE-05 pin test, scoped hot-path slice, ruff, and mypy passed.
- 2026-05-04: Phase 201 Plan 02 completed in 7min across 2 Wave 0 TDD scaffold tasks and 8 files; 18 named Phase 201 test classes now collect, hot-path baseline passed with 583 tests, and VALIDATION.md wave_0_complete flipped true.
- 2026-05-04: Phase 200 Plan 15 completed documentation closeout in ~9min across 5 planning artifacts plus summary; status is gaps_found, VALN-06 remains blocked after Attempt 3 canary 20260504T133207Z failed with 4 UL floor hits, rollback used /opt/wanctl-prephase200-gap-20260504T132936Z.tar.gz, and soak was skipped.
- 2026-05-04: Phase 200 Plan 14 completed in 21min27s across 4 task outcomes and 11 evidence/docs files; Attempt 3 deployed commit 57be072, canary 20260504T133207Z failed with 4 UL floor hits, D-10 rollback restored /opt/wanctl-prephase200-gap-20260504T132936Z.tar.gz, soak was skipped, and the hot-path slice passed with 583 tests.
- 2026-05-04: Phase 200 Plan 10 completed in 8min15s across 2 TDD gates and 11 files; approved R5+R3 landed with Spectrum factor_down_yellow=1.0, consecutive_yellow_decay_clamp=40, 763-test acceptance slice passed, dedicated single-GREEN clamp reset passed, and ruff/mypy passed.
- 2026-05-04: Phase 200 Plan 13 completed in 1min23s across 1 task and 3 files; WR-03 Docker packaging now preserves the full wanctl package tree, repo-root .dockerignore is present, static checks passed, Docker CLI was unavailable, and the hot-path slice passed with 578 tests.
- 2026-05-04: Phase 200 Plan 12 completed in 3min across 1 TDD task and 3 files; WR-01 preflight/daemon upload threshold-ordering parity is closed, check-config tests passed with 112 tests, ruff/mypy passed, and the hot-path slice passed with 578 tests.
- 2026-05-04: Phase 200 Plan 11 completed in 4min across 2 TDD tasks and 4 files; canary self-test coverage passed with 9 tests, shellcheck was unavailable, and the hot-path slice passed with 578 tests.
- 2026-05-03: Phase 200 Plan 08 completed in 2min — 200-VERIFICATION.md and 200-SUMMARY.md record blocked closeout, VALN-06 failed, and gap-closure recommendation.
- 2026-05-04: Phase 200 Plan 09 completed in 1min continuation — 200-09-HYPOTHESIS.md records operator approval for R5+R3 with factor_down_yellow=1.0 and clamp_count=40, and 200-09-SUMMARY.md hands off to Plan 200-10.
- 2026-05-03: Phase 200 Plan 06 completed in 2h46m — production deploy plus saturation canary verdict=fail with 122 UL floor hits; D-10 rollback restored v1.40.
- 2026-05-03: Phase 200 Plan 01 completed with D-03 per-key presence flags, independent live-tuning gates, and UL threshold regression tests; hot-path slice passed with 614 tests.
- 2026-05-03: Phase 200 Plan 07 completed as blocked in 2min across 1 gate outcome and 6 planning/docs/tracking files; Plan 06 verdict=fail prevented the 24h soak, no production action was taken, and the hot-path slice passed with 619 tests.
- 2026-05-03: Phase 200 Plan 05 completed in 2min across 1 task and 4 files; saturation canary script/env template/tracked evidence directory were created, smoke checks passed without production traffic, and the hot-path slice passed with 617 tests.
- 2026-05-03: Phase 200 Plan 04 completed in 2min across 2 tasks and 7 files; version surfaces report 1.41.0, Spectrum YAML carries D-05 UL settings, changelog/docs cover restart-required migration guidance, and the hot-path slice passed with 617 tests.
- 2026-05-03: Phase 200 Plan 03 completed in 3min across 1 TDD task and 3 source/test files; SAFE-06 startup warnings passed RED/GREEN tests, shipped Spectrum/ATT configs emitted zero unknown-key warnings, and the hot-path slice passed with 617 tests.
- 2026-05-03: Phase 200 Plan 02 completed in 1min across 1 task and 2 files; SAFE-05 now pins v1.41 warn_bloat=12 and target_bloat=14, seven non-UL pins remained unchanged, phase replay passed with 25 tests, and the hot-path slice passed with 615 tests.
- 2026-05-02: Phase 198 Plan 07 completed in 12min across 3 tasks and 12 evidence/verification files; attempt 11 was canonically promoted, VALN-04 and VALN-05a closed, SAFE-05 regenerated with diff_exit=0, and the hot-path slice passed with 573 tests.
- 2026-05-02: Phase 198 Plan 06 completed after checkpointed off-peak reruns; attempt 11 passed VALN-05a with medians 685.992066/674.156379/560.381543 Mbps, all three per-run loaded-window audits passed, SAFE-05 remained clean, and the hot-path slice passed with 573 tests.
- 2026-04-29: Phase 198 Plan 05 completed in ~16 min across 2 tasks and 3 new scripts; off-peak harness, loaded-window audit, and throughput verdict tooling passed syntax/content checks, SAFE-05 protected diff remained clean, and the hot-path slice passed with 572 tests.
- 2026-04-28: Phase 198 Plan 04 completed in ~10 min across 3 tasks and 4 closeout files; ab-comparison.json was produced with comparison_verdict fail, safe05-diff.json passed with zero protected-path diffs, 198-VERIFICATION.md records blocked status, and 196-VERIFICATION.md now cites Phase 198 evidence as failed/blocked rather than closed.
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

- ~~Phase 201 Plan 201-16 soak failed after the re-canary pass~~ — RESOLVED 2026-05-06 via operator Route B: D-19 primary PASS shipped, D-14 deferred to v1.43+ (SEED-002..SEED-005). See 201-RETRO.md and Decisions entry [Phase 201 closure 2026-05-06]. The remaining VALN-06 partial-closure trail is now in v1.41 traceability under REQUIREMENTS.md.
- VALN-06 inherited by Phase 201 (`docsis-aware-ul-congestion-control`) as a blocking requirement per operator escalation 2026-05-04. Phase 200 closed as `gaps_found` after gap-closure cycle 1: Plan 200-14 Attempt 3 canary `20260504T133207Z` improved loaded-window UL floor hits from 122 (Attempt 2) to 4 but did not reach the zero-hit gate; D-10 rollback restored `/opt/wanctl-prephase200-gap-20260504T132936Z.tar.gz`; the 24h soak was skipped fail-closed. No second Phase 200 remediation cycle was attempted; the residual failure regime is shaping-headroom dominated, which is Phase 201's scope. Production binary remains v1.40; v1.41 YAML keys remain on prod `/etc/wanctl/spectrum.yaml` and are inactive under v1.40 but MUST be reconciled before any future Spectrum deploy/restart (Phase 201 predeploy gate). See `200-VERIFICATION.md` `closure: deferred-to-phase-201`, `200-RETRO.md` `## Final Closure (2026-05-04)`, and `201-CONTEXT.md` `## Inherited Requirements`.
- Phase 191 closure remains blocked: restored ATT config rerun history now contains `2026-04-20` (`63.83 Mbps`), `2026-04-21` (`74.03 Mbps`), `2026-04-21b` (`67.83 Mbps`), `2026-04-23` (`64.40 Mbps`), `2026-04-23c` (`61.47 Mbps`), and `2026-04-24` (`70.95 Mbps`) FAIL samples against the old ATT RRUL download comparator. The `2026-04-24` run narrowed the issue because ATT tcp_12down and VoIP looked healthy and Spectrum throughput was strong, but it still did not close Phase 191. Phase 192 is allowed to proceed only under the explicit operator waiver in `192-PRECONDITION-WAIVER.md`.
- Phase 196 remains blocked only for the deferred ATT canary because Phase 191 closure is still open; Spectrum VALN-04 and VALN-05a were closed by Phase 198 Plan 07 attempt 11 canonical promotion.
- Pending follow-up created: `.planning/todos/pending/2026-04-24-resolve-att-cake-primary-canary-after-phase-196.md` tracks the required ATT cake-primary canary rerun after Phase 191 closes.

## Current Position

Phase: 206 (a-b-replay-harness-rollback-gates) — EXECUTING
Plan: 4 of 4
Status: Ready to execute
Last activity: 2026-05-15
