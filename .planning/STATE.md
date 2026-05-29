---
gsd_state_version: 1.0
milestone: v1.46
milestone_name: Internet Quality Recovery
current_phase: 215
current_plan: 3
status: verifying
stopped_at: Completed 215-02-PLAN.md
last_updated: "2026-05-29T15:10:22.656Z"
last_activity: 2026-05-29
progress:
  total_phases: 7
  completed_phases: 4
  total_plans: 17
  completed_plans: 17
  percent: 100
---

# Session State

## Project Reference

See: .planning/PROJECT.md (updated 2026-05-27 after v1.46 milestone open)

**Core value:** Sub-second congestion detection with 50ms control loops, achieved through systematic performance optimization and code quality improvements while maintaining production reliability.
**Current focus:** Phase 215 — spectrum-upload-reclaim-canary

## Current Position

Phase: 215 (spectrum-upload-reclaim-canary) — EXECUTING
Plan: 3 of 3
**Last shipped milestone:** v1.45 Flapping Peak-Counter Window Repair (shipped 2026-05-27 — VERIFY-01 DEFERRED)
**Recently archived:** v1.44 (2026-05-26), v1.43 (2026-05-13), v1.42 (2026-05-06), v1.41 (2026-05-06), v1.40 (2026-05-03)
**Active milestone:** v1.46 Internet Quality Recovery
**Current phase:** 215
**Current plan:** 3
**Status:** Phase complete — ready for verification
**Last activity:** 2026-05-29

Progress: [██████████] 100%

## Phase Structure (v1.46)

| Phase | Goal | REQ-IDs |
|-------|------|---------|
| 212 | Production inventory and drift audit for Spectrum, ATT, and steering | DRIFT-01, DRIFT-02, DRIFT-03 |
| 213 | Experience baseline harness for normal use, RRUL, and `tcp_12down` evidence capture | BASE-01, BASE-02, BASE-03 |
| 214 | Measurement-collapse investigation for bad p99 latency while health remains GREEN | MEAS-01, MEAS-02, MEAS-03 |
| 215 | Spectrum upload reclaim canary after baseline evidence | RECLAIM-01, RECLAIM-02, RECLAIM-03 |
| 216 | Queue-primary recovery/refractory semantics decision | RECOV-01, RECOV-02, RECOV-03 |
| 217 | Production cycle-budget baseline and profiling todo closure | PERF-01, PERF-02, PERF-03 |
| 218 | Deferred v1.45 VERIFY watch-list closure when natural event exists | VERIFY-01, VERIFY-02 |

**Ordering rationale:** Start read-only with live inventory and user-experience baseline before any tuning. Measurement collapse and upload reclaim should be evidence-driven. Recovery/refractory decisions wait for current baseline data. Phase 218 is a watch-list cleanup phase and only executes when a natural production flapping event exists.

## Cross-Cutting Invariants

**v1.46 safety posture:**

- No production tuning before baseline evidence and rollback gates.
- One knob per production canary.
- Do not treat `/health.status == healthy` or `GREEN` as sufficient proof of good user experience.
- v1.45 VERIFY-01 remains carried as a watch-list item and must not block quality work.

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

### v1.45-shipped-with-VERIFY-01-deferred

- **Status:** v1.45 shipped pending production verification.
- **Operator sign-off:** Kevin — 2026-05-27T17:53:06Z, via prompt: "Just defer. I am tired of waiting. We can circle back to it later if needed. I want to cleanly move to 1.446" (`1.446` interpreted as v1.46).
- **Carry-forward task:** Close VERIFY-01 in v1.46 (or later) when a qualifying production DOCSIS event produces an alerts row with `details.peak_transition_count > 30` on either WAN.
- **Reference:** `.planning/phases/211-production-verification-milestone-closure/211-VERIFY-01-evidence/EVIDENCE.md` (deferral narrative + BRANCH-B flag).
- **Synthetic proof:** Phase 210 unit + integration tests (`132/132` alerting/integration slice passing); production observation is the open gate.
- **ALERT-03 note:** ALERT-03 production audit is deferred with VERIFY-01 because no qualifying production episode exists to bucket by `cooldown_sec`.

## Accumulated Context

### Roadmap Evolution

- 2026-05-27: v1.46 roadmap opened as Internet Quality Recovery after operator reassessment that v1.45 production-observation wait was stalling useful work while internet quality felt worse than it should. Scope is evidence-first quality recovery: production drift audit, experience baseline, measurement-collapse investigation, conservative upload reclaim, recovery/refractory decision, cycle-budget baseline, and deferred v1.45 VERIFY watch-list closure. Phase numbering continues from v1.45 (last phase 211) → v1.46 starts at Phase 212.
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

Last session: 2026-05-29T15:10:22.628Z
Stopped at: Completed 215-03-PLAN.md
Resume file: None
Archived v1.44 evidence: `.planning/milestones/v1.44-phases/`

## Operator Next Steps

- Run `/gsd-plan-phase 215` to plan the Spectrum upload reclaim canary. Phase 215 should consume `.planning/phases/214-measurement-collapse-investigation/evidence/matrix-summary.json` and the Phase 213 baseline as constraint sources.
- Carry the folded `tcp_12down` todo as narrower next steps: Phase 214 left `ambiguous`/`reflector_loss`/`signal none`; the unresolved gap is severe user-visible p99 without journal corroboration, plus target/path sensitivity shown by supplemental Vultr runs.
- Phase 214 official-window flent raw artifacts remain external symlinks into `~/flent-results/`; only the supplemental Vultr `.flent.gz` is committed in-repo. The official matrix is not re-derivable from a fresh clone alone.
- Leave Phase 218 alone until a natural production flapping event creates a qualifying `peak_transition_count > 30` row.

## Decisions (v1.45)

- [v1.45 Roadmap]: Two-phase split selected over single-phase. Rationale: VERIFY-01 cannot be satisfied at PR-merge time — it requires a real production flapping event after deploy. Making the production-gate an explicit phase boundary (Phase 211) mirrors v1.44 Phase 209 production-canary pattern and avoids burying the closure gate as a milestone-close deferral.
- [v1.45 Roadmap]: ALERT-03 (alert-once-per-`cooldown_sec`-window, no per-cycle log-spam; amended 2026-05-26 per codex peer review from "per episode" to "per cooldown_sec window" after live-config audit found Spectrum=600s, ATT=300s default — making "per episode" mathematically infeasible at the documented Spectrum cooldown intent of ~3 firings per 30-min event) paired into Phase 211 rather than Phase 210 because end-to-end behavior is only verifiable in production under a real sustained event. Phase 210 tests establish the mechanism (cooldown_sec retained, deque-clear-on-fire retained); Phase 211 confirms it holds in production.
- [v1.45 Roadmap]: SAFE-10 owned primarily by Phase 210 (PR-merge-time verification) and re-verified at Phase 211 (milestone-close) to catch drift between merge and deploy.
- [v1.45 Roadmap]: Plan materialization deferred to `/gsd-plan-phase` per milestone convention; no `.planning/phases/210-*` or `.planning/phases/211-*` directories created during roadmap phase.
- [210-02]: Flapping tests now assert `peak_transition_count` from `_dl_peak_window_transitions` / `_ul_peak_window_transitions` deques, with fixed-threshold second-fire coverage for DL and UL.
- [210-02]: Threshold-mutation integration coverage was adjusted because identical `flap_window` pruning makes the old `peak=35` / `transition=30` payload expectation impossible under the accepted two-deque design.
- [210-03]: SAFE-10 baseline uses v1.44 archive marker `21ee630` as the local equivalent close point because `c9932d2` resolves to an earlier v1.42-era commit in this checkout.
- [211-01]: Spectrum v1.45 canary deploy verified via bound production health endpoint `http://10.10.110.223:9101/health`; loopback `127.0.0.1:9101` is not listening in current production config.
- [211-01]: `scripts/deploy.sh spectrum cake-shaper` copied v1.45 code but did not restart the running daemon; orchestrator restarted `wanctl@spectrum.service`, after which `/health.version` returned `1.45.0` and the Spectrum 7d observation window opened at approximately `2026-05-26T18:48:06Z`.
- [211-02]: Operator approved ATT rollout before the original T+24h gate; ATT Snapshot A `20260527T174231Z` was captured, `./scripts/deploy.sh att cake-shaper` ran, and `wanctl@att.service` required restart before bound health endpoint `http://10.10.110.227:9101/health` returned `1.45.0 healthy`.
- [211-02]: Operator explicitly chose early D-04(b) deferral before the full 7d observation window elapsed. VERIFY-01 remains open for v1.46/watch-list; Plan 211-03 must follow Branch B and must not archive active phase directories with `git mv`.
- [v1.45 deferral close]: v1.45 shipped with VERIFY-01 DEFERRED by operator sign-off at 2026-05-27T17:53:06Z; ALERT-03 audit is deferred because no qualifying production episode exists; SAFE-10 manual audit passed against `21ee630` with `AWK_EXIT=0`; carry-forward task is to close VERIFY-01 in v1.46/watch-list when a qualifying DOCSIS event appears.

## Decisions (v1.46)

- [212-01]: Used `sudo -n` for read-only production config/state reads after unprivileged reads were permission-blocked; this preserved the no-mutation boundary while allowing deployed endpoint/config evidence capture.
- [212-01]: Omitted D-08 secret-like config keys from redacted YAML artifacts so automated key/value scans pass cleanly while preserving proof-relevant non-secret fields.
- [212-01]: Recorded steering health at `127.0.0.1:9102` only after read-only socket discovery on `cake-shaper`; Spectrum/ATT endpoints were confirmed from deployed config.
- [212-02]: Spectrum and ATT service/config/health evidence is not drift; ATT version drift is resolved by the approved Phase 211 deployment.
- [212-02]: Steering runtime reports `1.39.0` while repo source is `1.45.0`, so steering version/threshold evidence is unknown drift pending operator-approved alignment.
- [212-02]: Folded steering clean-restart todo remains `current-state-good/reproduction-not-attempted`; no controlled restart was staged or represented as proof.
- [212-03]: Final Phase 212 report carries steering runtime/threshold drift as unresolved operator-approved alignment work and preserves healthy/GREEN as daemon-state evidence only.
- [212-03]: Deferred Phase 214, 217, 218, and ATT canary/refractory work remains excluded from Phase 212 inventory scope.
- [213-02]: Phase 213 traffic/telemetry surfaces stayed script-only and evidence-only; no controller code, production config, services, or RouterOS surfaces were touched.
- [213-02]: Browse-loop request failures are captured as CSV evidence rows via `exit_code` instead of aborting, so downstream classification can distinguish network failures from successful slow responses.
- [213-03]: Alert-window live mode uses `sqlite3 -readonly file:DB?mode=ro`; local fixture mode skips SSH entirely and falls back to Python stdlib `sqlite3` only when the dev VM lacks the sqlite3 CLI.
- [213-03]: Steering state raw JSON lives only in `/tmp/phase213-steering-raw.XXXXXX` under an immediate EXIT trap; committed evidence paths receive only D-08-redacted JSON.
- [213-05]: Phase 213 complete; next phase: 215 per operator verdict; runners-up: 216, 214.
- [214-01]: Matrix capture stays a thin Phase 213 wrapper; Plan 01 adds Phase 214 window metadata, per-test journal capture, and an untracked-file extension to the D-14 `src/wanctl/` mutation guard.
- [214-02]: Phase 214 owns a new fail-closed flent extractor rather than back-editing Phase 213's zero-fill classifier path; `raw_values['Ping (ms) ICMP']` is the MEAS-01 p99 source of truth.
- [214-02]: The extractor uses the locked Phase 214 sorted-index percentile method (`n//2`, `int(n*0.95)`, `int(n*0.99)` with clamp) and pins the known-good fixture values at p50=31.2, p95=60.3, p99=124.0.
- [214-03]: The aligner reuses `phase214-extract.py`'s `FlentExtractionError` class via a sys.modules-cached importlib load so downstream exception handling sees one canonical class.
- [214-03]: The aligner CLI derives the flent window from `extract_flent_latency()` and rejects operator-supplied `--flent-t0` / `--flent-end` flags.
- [214-03]: The synthesized health fixture is aligned to the committed flent fixture window so end-to-end CLI verification exercises health projection and `in_flent_window` rows together.
- [214-04]: Classifier output remains observational-only: Form B signal-sheet evidence is emitted locally, Form C alerting is documented as a future recommendation, and Form A is only a future-phase candidate.
- [214-04]: The classifier keeps Phase 214 additive by importing the fail-closed extractor and avoiding edits to `src/wanctl/`, Phase 213 scripts, and prior Phase 214 extractor/aligner scripts.
- [214-04]: The CLI accepts an omitted `--run-dir` with a deterministic fallback so the documented acceptance command succeeds while MED-7 metadata remains populated.
- [214-05]: Matrix aggregation requires off-peak, daytime, and prime-time Spectrum signal sheets by default; operator partial override is explicit and produces `verdict="partial"`, never `pass`.
- [214-05]: Mutation-boundary fallback base selection rejects stale `origin/main` merge-bases that already include protected-path diffs, then falls back to `HEAD~10` unless `PHASE214_BASE_SHA` is set.
- [214-05]: Forbidden mutation regex is command/assignment-form anchored and tightened so narrative prose beginning with `restart wanctl` does not self-invalidate the guard.
- [214-06]: Official three-window Spectrum/Dallas matrix verdict is `ambiguous` (daytime/prime-time p99 606/560ms ambiguous, off-peak p99 120ms pass), primary driver `reflector_loss`, signal disposition `none`. Historical catastrophic `p99 > 1000ms` was NOT reproduced and there was no in-window journal corroboration for reflector fail bursts, so Form B/C signals are deferred and the folded `tcp_12down` todo is carried-narrower rather than closed.
- [214-06]: Supplemental Vultr Dallas/Chicago runs (severe loaded p99 745/651ms) are NOT part of the canonical matrix but keep target/path sensitivity a live hypothesis for Phase 215+.
- [214 UAT]: Phase 214 verified read-only via 8/8 UAT against committed fixtures; mutation-boundary pytest enforces zero `src/wanctl` diff, making the no-mutation attestation testable rather than asserted. No `*-SECURITY.md` was produced (security gate waived for a strictly read-only investigation per operator).
- [215-01]: Upload extraction excludes ambiguous `TCP totals`; the reclaim gate derives p95/p99/throughput bounds from leg-A inputs, keeps Phase 213 numbers as fallback constants, and maps VOID to exit 2 for set-e-safe Plan 03 branching.
- [215-02]: Snapshot A acceptance allows an absent retained `wanctl_config_snapshot` DB row; repo config ceiling=18, deployed config ceiling=18, and bound Spectrum `/health` evidence form the pre-mutation rollback anchor when the exact read-only query returns no row.
- [215-03]: Bounded VOID exhausted on three ceiling-20 leg-B attempts, so Spectrum was targeted-rolled back to upload ceiling 18; no ceiling-20 WIN was kept.
- [215-03]: Gate remote-yaml preflight now uses `sudo -n python3 -c` after heredoc-over-SSH quoting blocked deployed-ceiling validation.

## Performance Metrics

| Phase | Plan | Duration | Tasks | Files |
|-------|------|----------|-------|-------|
| 210 | 02 | 6.0min | 2 | 3 |
| 210 | 03 | 4.1min | 1 | 1 |
| 211 | 01 | 7min | 5 | 6 |
| 211 | 02 | checkpointed | 4 | 2 |
| 211 | 03 | in-session | 5 | 6 |
| 212 | 01 | 7min | 3 | 13 |
| 212 | 02 | 3min | 2 | 2 |
| 212 | 03 | 4min | 2 | 2 |
| Phase 213 P01 | 5min | 2 tasks | 49 files |
| Phase 213 P02 | 4min | 2 tasks | 2 files |
| Phase 213 P03 | 4min | 2 tasks | 2 files |
| Phase 213 P04 | 8min | 3 tasks | 4 files |
| Phase 213 P05 | in-session | 3 tasks | 140+ files |
| Phase 214 P01 | 3min | 1 tasks | 1 files |
| Phase 214 P02 | 9min | 2 tasks | 7 files |
| Phase 214 P03 | 10min | 2 tasks | 5 files |
| Phase 214 P04 | 12min | 2 tasks | 5 files |
| Phase 214 P05 | 10min | 2 tasks | 4 files |
| Phase 215 P01 | 5min | 2 tasks | 5 files |
| Phase 215 P02 | 4min | 1 tasks | 8 files |
| Phase 215 P03 | 18min | 2 tasks | 35 files |
