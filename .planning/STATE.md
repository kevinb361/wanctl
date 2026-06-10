---
gsd_state_version: 1.0
milestone: v1.51
milestone_name: Post-Migration Consolidation
status: planning
last_updated: "2026-06-10T20:24:46.238Z"
last_activity: 2026-06-10
progress:
  total_phases: 0
  completed_phases: 0
  total_plans: 0
  completed_plans: 0
  percent: 0
---

# Session State

## Project Reference

See: .planning/PROJECT.md (updated 2026-06-10 after v1.50 milestone close)

**Core value:** Sub-second congestion detection with 50ms control loops, achieved through systematic performance optimization and code quality improvements while maintaining production reliability.
**Current focus:** Planning next milestone (`/gsd:new-milestone`)

## Current Position

Phase: Not started (defining requirements)
Plan: —
Status: Defining requirements
Last activity: 2026-06-10 — Milestone v1.51 started

## Deferred Items (carried into next milestone)

Re-acknowledged at v1.50 milestone close 2026-06-10 via `/gsd-complete-milestone` Acknowledge-all path. All 23 open artifacts remain the same pre-existing carry-forward set acknowledged at v1.47, v1.48, and v1.49 closes (1 debug-session index, 12 orphan quick-task slugs, 5 dormant seeds, 5 event-gated/out-of-scope todos). **Zero new v1.50 debt.** New context at this close: v1.50 audit recorded Phase 230 Nyquist PARTIAL (`nyquist_compliant: false`, optional retroactive `/gsd:validate-phase 230`), pre-existing Phase 220/221 boundary-test noise (classified in archived `milestones/v1.50-phases/230-*/deferred-items.md`), and a residual confirm-path fix in `phase231-rollback.sh` to land before any future live rollback exercise. Phase 218 watch remains dormant (instrumentation lives in the non-live native controller). Carry-forward items below are parallel to any next milestone.

| Category | Item | Status |
|----------|------|--------|
| requirements | VERIFY-01 | deferred to Phase 218 — needs natural production flapping event with `peak_transition_count > 30`; runs parallel to v1.48 |
| requirements | VERIFY-02 | deferred to Phase 218 — gated on VERIFY-01 + ALERT-03 per-`cooldown_sec` bucket audit; runs parallel to v1.48 |
| requirements | STEER-DRIFT-01 | **ACTIVE in v1.48** — addressed by Phases 222–224 (audit → proof → canary) |
| requirements | RECLAIM-04 | deferred indefinitely — Spectrum upload reclaim re-attempt requires fundamentally different probe shape after Phase 215 bounded VOID; NOT in v1.48 |
| phases | Phase 218 (Deferred v1.45 VERIFY Watch-List Closure) | carried as event-gated watch item; no synthetic event generation per ROADMAP; runs parallel to v1.48 |
| debug_sessions | knowledge-base | unknown (index file, not active investigation) |
| todos | 2026-04-08-investigate-tcp-12down-latency-spikes-under-multi-flow-downl | **CLOSED 2026-06-02 by v1.47 Phase 221** — close-with-prejudice rule per CRITERIA-02; no v1.48+ reopen without independent new production evidence |
| todos | 2026-04-17-ingestion-rate-tool | **CLOSED 2026-05-30 by v1.47 Phase 219** — additive `--by-table` + `--rolling` extensions + cron snapshot shipped |
| todos | 2026-04-17-investigate-steering-degraded-on-clean-restart | **FOLDED into v1.48 Phase 223** — closes here via reproduction or fail-closed documentation |
| todos | 2026-04-17-monitor-flapping-peak-count-on-next-docsis-event | pending — primary Phase 218 trigger; closes with VERIFY-01; runs parallel to v1.48 |
| todos | 2026-04-17-operator-summary-digest-permission-handling | pending — OUT of v1.48 scope; candidate for retroactive sweep |
| todos | 2026-04-24-resolve-att-cake-primary-canary-after-phase-196 | pending (gated on Phase 191 closure; ATT canary already deployed in v1.45) |
| todos | 2026-04-15-profile-post-hotpath-baseline-on-production-wan | **CLOSED 2026-05-30 by Phase 217** — see 217-03 SUMMARY |
| seeds | SEED-003-v143-d14-watchdog-recalibration | dormant |
| seeds | SEED-004-v143-target-edge-churn-instrumentation | dormant |
| seeds | SEED-005-v143-conservative-ul-tuning-sweep | dormant; OUT of v1.48 (single-thesis) |
| seeds | SEED-006-v145-silicom-bypass-tooling-and-harness | dormant; OUT of v1.48 (single-thesis) |
| seeds | SEED-007-v145-storage-hygiene-fire-on-change | dormant; v1.48 runner-up explicitly OUT of v1.48 (single-thesis) |
| quick_tasks | 12 orphan slugs from older milestones | metadata noise; OUT of v1.48; candidate for `/gsd-cleanup` retroactive sweep |

### v1.50-shipped-clean

- **Status:** v1.50 milestone complete (archived 2026-06-10, tagged v1.50).
- **Operator sign-off:** Kevin — 2026-06-10, via /gsd-complete-milestone → audit-first → Acknowledge-all → ship path. 10/10 v1.50 requirements satisfied; milestone audit `passed` (10/10 integration seams, 3/3 E2E flows). Zero new v1.50 debt; all 23 open artifacts are pre-existing carry-forward from v1.47/v1.48/v1.49 closes.
- **Why this is acceptable:** v1.50 spine (DEPLOY/TEST/MON/SOAK/DOCS) shipped cleanly with SAFE-14 held at every phase boundary and milestone close. SOAK-02 closed via operator-accepted no-mutation provable path (both-WAN preflight `overall_pass: true`); the live rollback exercise remains explicitly opt-in with the residual confirm-path fix noted before any future exercise.

### v1.49-closed-overtaken-by-events

- **Status:** v1.49 milestone complete (archived 2026-06-09)
- **Operator sign-off:** Kevin — 2026-06-09, "do it" on the assessed closure plan (commit migration work → close v1.49 overtaken-by-events → new milestone for cake-autorate hardening).
- **Why this is acceptable:** The Phase 228 verdict gated a wanctl-controlled bridge-root CAKE topology that was replaced wholesale by the cake-autorate member-NIC migration (`fc47a0c`, live 2026-06-08). Computing the verdict post-hoc would be theater; the evidence direction (REJECT diffserv4-wash in the old topology: RRUL p99 +11.5%, EF loss ~44×) is recorded faithfully in MILESTONES.md and marked non-transferable. Wash-vs-nowash was independently re-validated under the new topology and `wash` won.

### v1.47-shipped-clean

- **Status:** v1.47 milestone complete (archived 2026-06-02).
- **Operator sign-off:** Kevin — 2026-06-02, via /gsd-complete-milestone → Acknowledge & close path. 18/18 v1.47 requirements satisfied. Zero new v1.47 debt; all 23 open artifacts are pre-existing carry-forward from v1.46 close.
- **Why this is acceptable:** v1.47 spine (D / A1 / A2) shipped cleanly with SAFE-11 invariant held at every phase boundary. The folded tcp_12down todo is CLOSED with close-with-prejudice rule per CRITERIA-02; no v1.48+ reopen without independent new production evidence.

### v1.46-shipped-with-VERIFY-01-02-deferred

- **Status:** v1.46 milestone complete (archived 2026-05-30); VERIFY-01/02 still parked at Phase 218 event-gated watch.
- **Operator sign-off:** Kevin — 2026-05-30, via /gsd-progress → Acknowledge & close path: "fix STATE drift then complete milestone". 18/20 v1.46 requirements satisfied; VERIFY-01/02 carry forward as watch-list.
- **Why this is acceptable:** v1.46 spine (DRIFT/BASE/MEAS/RECLAIM/RECOV/PERF) is complete and decoupled from VERIFY. VERIFY watch closure requires production-side natural evidence that cannot be hastened without invalidating the metric.

### v1.45-shipped-with-VERIFY-01-deferred

- **Status:** v1.45 shipped pending production verification.
- **Operator sign-off:** Kevin — 2026-05-27T17:53:06Z, via prompt: "Just defer. I am tired of waiting. We can circle back to it later if needed. I want to cleanly move to 1.446" (`1.446` interpreted as v1.46).
- **Carry-forward task:** Close VERIFY-01 in v1.46 (or later) when a qualifying production DOCSIS event produces an alerts row with `details.peak_transition_count > 30` on either WAN. Now lives as Phase 218 watch-list; parallel to v1.48.

## Accumulated Context

### Roadmap Evolution

- **2026-06-09 (v1.50 ROADMAP commit):** v1.50 ROADMAP.md created with 3-phase scope (fine granularity, deliberately small), continuing phase numbering from v1.49 last phase (228) → Phase 229. Natural ordering by production risk: Phase 229 (ATT Deploy Path + Artifact Tests — DEPLOY-01/02, TEST-01/02; repo-only, zero production touch, makes repo the drift-proof source of truth for the hand-deployed ATT artifact set) → Phase 230 (soak-monitor ATT Coverage — MON-01/02; closes the error-scan blind spot where soak-monitor watches the DISABLED `wanctl@att.service` instead of live `cake-autorate-att*` units) → Phase 231 (Migration-Held Criteria, Rollback Verification & Doc Sweep — SOAK-01/02, DOCS-04, SAFE-14; touches production evidence, operator-gated for any rollback exercise, with the preflighted-provable alternative for SOAK-02). 10/10 REQs mapped, 0 orphans. SAFE-14 declared as cross-phase controller-path zero-diff invariant verified at every phase boundary (229/230/231) per the SAFE-07..13 precedent; mapped to the closeout phase (231) for traceability. Milestone surface is deploy/test/ops/doc only — no controller threshold/algorithm changes. Out-of-Scope (REQUIREMENTS.md) binding: ROLE-01 native-controller retirement (time/event-gated), TAIL-01 Spectrum tail (different milestone shape), SEED-006/007, `$wan` symmetry refactor, CAKE retuning all excluded.
- **2026-06-03 (v1.49 ROADMAP commit):** v1.49 ROADMAP.md created with 4-phase scope, continuing phase numbering from v1.48 last phase (224) → Phase 225. Two-thread single thesis: Phase 225 (DSCP Survival Trace — DSCP-01..03, read-only precondition with DSCP-03 early-exit gate) → Phase 226 (Baseline Capture + Threshold Lock + Snapshot A — AB-01, AB-02, GATE-01; GATE-01 thresholds locked BEFORE candidate deploy per v1.44/v1.47 discipline) → Phase 227 (Candidate diffserv4-wash Deploy + Matched Capture — AB-03, AB-04) → Phase 228 (Verdict + Evidence-Gated Decision + Closeout — GATE-02, GATE-03). 13/13 REQs mapped. Conditional gate: DSCP-03 "marks don't survive" early-exit short-circuits Phases 226–228 and closes the milestone negative (v1.44 confirmed). SAFE-13 declared as cross-phase controller-path zero-diff invariant on all four phases — any lift is an explicit evidence-gated decision inside Phase 228 (default expectation: zero controller-path diff; v1.44 Phase 205 already shipped the tin-agnostic CAKE signal + allow_wash gate). ATT byte-identical the entire milestone; external network gear (CRS/Ruckus/router) NOT mutated (read-only trace); cake-shaper bridge nftables rules MAY change. Negative result (keep besteffort wash) is a valid close.
- **2026-06-02 (v1.48 ROADMAP commit):** v1.48 ROADMAP.md created with 3-phase scope per joint Claude + Codex scope review: Phase 222 (Steering Drift Audit — DRIFT-01..04) → Phase 223 (Staging Proof + Clean-Restart Reproduction — PROOF-01..03, folded `steering-degraded-on-clean-restart` todo) → Phase 224 (Production Canary + Rollback Discipline — CANARY-01..03, v1.46 Phase 215 Snapshot A precedent). SAFE-12 declared as cross-phase controller-path zero-diff invariant on all three phases.
- **2026-06-02 (v1.47 close):** v1.47 Measurement Evidence Closure shipped. Phases 219/220/221 complete; 18/18 REQs satisfied. Folded tcp_12down todo closed with CRITERIA-02 close-with-prejudice rule per the post-D-10-BGP-overlay verdict `carried_narrower_with_close_with_prejudice_rule`. Phase 218 continues parallel as event-gated v1.45 VERIFY watch-list. Phase directories archived to `.planning/milestones/v1.47-phases/`.
- **2026-05-30 (v1.47 ROADMAP commit):** v1.47 ROADMAP.md created with 3-phase LOCKED scope per joint Claude + Codex operator decision: Phase 219 (Scope D — Ingestion-Rate Observability, D-first per Pitfall 11) → Phase 220 (Scope A1 — Matrix Runner with pre-registered CRITERIA gate) → Phase 221 (Scope A2 — Matrix Evidence + Closeout).
- 2026-05-27: v1.46 roadmap opened as Internet Quality Recovery after operator reassessment that v1.45 production-observation wait was stalling useful work while internet quality felt worse than it should.

### Key v1.47 Outcomes (archived to PROJECT.md + RETROSPECTIVE.md + milestones/v1.47-ROADMAP.md)

- 18/18 v1.47 REQ-IDs satisfied (INGEST x5, CRITERIA x2, MATRIX x4, AGGREGATE x3, CLOSEOUT x3, SAFE-11 x1).
- Folded `2026-04-08-investigate-tcp-12down` todo CLOSED with close-with-prejudice rule per CRITERIA-02.
- SAFE-11 invariant held end-to-end: zero controller-path source diff across all three phases.
- D-27 production cycle-budget within Phase 217 baseline: `avg_ms=2.857`, `p99_ms=6.4` over 73,603 samples with Phase 219 cron snapshot active.

## Session Continuity

Last session: 2026-06-10T14:31:38.475Z
Stopped at: Completed 231-03-PLAN.md
Resume file: None
Archived v1.46 evidence: `.planning/milestones/v1.46-phases/`
Archived v1.47 evidence: `.planning/milestones/v1.47-phases/`
Archived v1.50 evidence: `.planning/milestones/v1.50-phases/`

## Operator Next Steps

- Start the next milestone with /gsd-new-milestone

## Decisions (v1.50)

- [229-01]: ATT deploy path mirrors Spectrum as a sibling function rather than introducing a generic WAN abstraction.
- [229-01]: ATT ships the silicom watchdog unit but only warns if bpctl runtime scripts are absent, preserving the deploy boundary.
- [229-02]: ATT bridge health verification waits for a healthy payload so startup races do not make the parity suite flaky.
- [229-02]: The deploy-list drift gate parses deploy.sh text directly because no central ATT artifact manifest exists.
- [229-03]: Repo-owned ATT artifacts matched live cake-shaper bytes for all six DEPLOY-02 artifacts; no reconciliation was needed.
- [229-03]: SAFE-14 baseline pinned to 87980bdf as the last docs/planning-only commit before Phase 229 implementation.
- [230-01]: Kept native wanctl@<wan>.service as fallback scanning path when external cake-autorate mode is not detected.
- [230-01]: Aggregate soak-monitor JSON units, labels, and journal hints are generated from the same live-unit array used for check_errors.
- [230-02]: Criterion-3 production proof stayed read-only; representative error injection was confined to a local fake-ssh shim.
- [230-02]: SAFE_BASE=87980bdf is used only for controller-path zero-diff, while PHASE230_START=4ad2986e is used for Phase 230 scripts/tests scope accounting.
- [231-01]: PHASE231_START candidate pinned to 55c33a7b646abe3af9208bc1fb0db3677dd25810, the parent of the first 231-01 implementation commit.
- [231-01]: SOAK-01 verdict is machine-derived PASS for both WANs; operator approval confirmed the evidence and criteria after capture.
- [231-01]: C3 no_sustained_errors remains objective: historical bounded err lines can pass only under encoded constants, not operator judgment.
- [231-02]: Kevin accepted the SOAK-02 provable path on 2026-06-10; no live rollback exercise or production mutation was performed.
- [231-02]: PHASE231_START candidate remains 55c33a7b646abe3af9208bc1fb0db3677dd25810 for Phase 231 SAFE-14 scope accounting.
- [231-03]: Active docs now present native wanctl@ mode as the portable default and external cake-autorate mode as a sibling deployment model, not as a replacement for generic wanctl@ usage.
- [231-03]: SAFE-14 milestone-close proof uses SAFE_BASE=87980bdf8ea52e5537110cd9bbc7a368f523d2e2 for controller-path zero-diff and PHASE231_START=55c33a7b646abe3af9208bc1fb0db3677dd25810 for Phase 231 scope accounting.
- [231-03]: Every commit after boundary tracking commit 2a2a1022 is restricted to .planning/** so the boundary proof remains valid through SUMMARY/STATE/ROADMAP metadata closeout.

## Decisions (v1.49)

- [225-01]: Counter absence on bridge `ip dscp set` rules is recorded as `bridge_counter_signal=unknown`, never `negligible`.
- [225-01]: CRS trust and Ruckus QoS mirroring remain documented assumptions unless backed by concrete read-only artifacts and do not feed DSCP-03.
- [225-02]: Capture point proof defaults to unknown and only records `pre_wash_ingress` when machine-checkable wash-ordering evidence passes.
- [225-02]: DL EF probe negative/STRIPPED semantics require source-side DL EF proof; otherwise the DL probe remains degraded/unknown.
- [225-03]: DSCP-03 verdict is `MARKS_SURVIVE_QUALIFIED` because committed raw evidence does not prove valid DL gating channels; Phase 226 remains blocked by default pending better evidence or an explicit operator override.
- [225-03]: SAFE-13 boundary proof expands `src/wanctl/backends/` to per-file targets and verifies committed, staged, dirty-tree, and ATT config channels against `v1.48`.
- [225-04]: Probe/SSH/numeric args are allowlist+range validated before any SSH command is built; an unsafe value exits 2 with no remote invocation (GAP-1/CR-01 closed).
- [225-04]: Wash-ordering proof booleans (WASH_PROOF_PASS/WASH_ORDERING_PROVEN/CAPTURE_POINT) rest only on a machine-checkable predicate — parse_qdisc_ordering (ingress/clsact hook + CAKE root parsed) or paired_bitflip — not topology prose or qdisc presence; default false/unknown (GAP-2/WR-01 closed).
- [225-04]: DL source-side EF proof is honest — opt-in real source capture (--dl-source-ssh-host/--dl-source-iface) or explicit SRC_CAPTURE_POINT=unsupported degrade with no empty pcap; raw/dl-ef-probe-source.pcap is a conditional artifact; DL STRIPPED still only when DL_SOURCE_EF_PROVEN=true (GAP-3/WR-02 closed).
- [225-05]: SAFE-13 boundary record re-run LAST (after 225-04 commits) so head_commit stamps the true final phase HEAD (62f74b2); committed JSON references the commit immediately prior to its own tracking commit — expected final-boundary parent-reference semantics, not the stale multi-commit lag GAP-4 was about (baa9b4b was 3 commits behind). passed=true with zero controller/ATT diff and all hashes byte-identical vs v1.48 (GAP-4 closed).
- [226-02]: Snapshot A raw restore bytes remain operator-private under `/tmp/opencode/wanctl-phase226-snapshot-a-raw-20260604T1115Z` and are not committed.
- [226-02]: Deployed and repo redacted `spectrum.yaml` SHA-256 values are equal, so Snapshot A `config_equality` verdict is `equal`.
- [226-01]: Task 4 used the exact operator-approved forced-window reason: `operator approved forced run now at checkpoint`.
- [226-01]: Retained baseline used `ref_host=vultr-chicago` after objective invalid `dallas` run-sets hit netperf errors/resets; discarded run-set names are recorded in the retained MANIFEST.
- [226-03]: `TIN_SEPARATION.NOISE_BAND_MS.value` was filled from the retained baseline max `tin_queue_delay_spread_ms` and recorded with `baseline-summary.json` sha256 provenance.
- [226-03]: GATE-01 prose points to `scripts/phase226-thresholds.json` rather than duplicating threshold values.
- [226-04]: Restore proof remains dry-run-only in Phase 226; mutation-capable restore behavior is deferred to Phase 228.
- [226-04]: Restore proof claims only config-artifact equality plus command identity, not runtime qdisc restoration or live rollback validity.
- [226-04]: SAFE-13 boundary was verified after the restore-proof task commit, so evidence reflects the final Phase 226 implementation state.
- [226-05]: Regenerated only derived baseline artifacts from unchanged retained raw run-NN tc/health/flent/reference artifacts.
- [226-05]: Re-provenanced NOISE_BAND_MS to the final regenerated baseline-summary.json hash recorded in the evidence manifest.
- [226-05]: Task 4 used the comprehensive SAFE-13 protected-set script and a committed plan-scope allowlist check because the literal v1.48-wide diff includes prior v1.49 planning/evidence history.
- [227-02]: Qdisc verification gate exits 0 only when both Spectrum NICs resolve to the requested expected mode; all missing/ambiguous/SSH/wrong-mode states fail closed.
- [227-02]: Regression tests use local input flags and simulated SSH failure so qdisc parser proof states are tested without live target mutation.
- [227-04]: `wan_controller_state.py` is explicitly listed in the SAFE-13 protected controller targets because `wan_controller.py` imports it and `expand_protected_files()` only auto-expands directory-suffixed targets.
- [227-04]: Evidence completeness is a Phase 228 readiness gate only: it validates GATE-01 signals, run success, qdisc proofs, stable top-level shape, and BE/non-BE tin computability without computing the accept/reject verdict.

## Decisions (v1.48)

- [v1.48 Roadmap]: 3-phase sliced scope per joint Claude + Codex review 2026-06-02. Single-thesis discipline. Final order: 222 (Audit) → 223 (Staging Proof + folded steering-degraded-on-clean-restart) → 224 (Production Canary + Snapshot-A rollback).
- [v1.48 Roadmap]: SAFE-12 declared as cross-phase controller-path zero-diff invariant — listed on every phase's requirements line (not mapped to a separate phase). Same discipline as SAFE-07/08/09/11 through v1.43–v1.47.
- [v1.48 Roadmap]: Steering daemon source IS in scope for mutation; controller path (`wan_controller.py`, `queue_controller.py`, `cake_signal.py`, backends, `alert_engine.py`, fusion) is NOT.
- [v1.48 Roadmap]: Spine constraints (binary on/off, only-new-connections rerouted, autorate-baseline-RTT-authoritative) declared immutable across the milestone; every phase's success criteria preserve them.
- [v1.48 Roadmap]: Phase 218 (v1.45 VERIFY watch) stays parallel and event-gated; NOT renumbered into v1.48.
- [v1.48 Roadmap]: SEED-007 storage hygiene, operator-summary digest permission sweep, `/gsd-cleanup` orphan sweep, and RECLAIM-04 explicitly OUT of v1.48 scope.
- [v1.48 Roadmap]: Folded todo `2026-04-17-investigate-steering-degraded-on-clean-restart` closes in Phase 223 either by reproduction or fail-closed documentation.
- [v1.48 Roadmap]: Phase 224 canary models on v1.46 Phase 215 Snapshot A pattern (pre-deploy snapshot anchor + bounded rollback path + post-deploy health-endpoint gate proof).
- [222-01]: Used v1.39 tag commit as conservative steering runtime baseline because Phase 212 did not identify a more precise deployed-binary commit.
- [222-01]: Pinned all Plan 01 diff/log endpoints to v1.47-peeled source-floor commit `bee343b0c2f16207101aec82007a5e55fa9b6407`; audit_head is diagnostics only.
- [222-01]: Classified `84ad6aa` as behavior-changing because it tightens RouterOS parsed-record handling and numeric RTT source acceptance in the steering decision path.
- [222-02]: Classified `84ad6aa` as contract-preserving despite behavior-changing hardening because all three steering spine invariant verdicts are yes.
- [222-02]: Assigned go disposition to `84ad6aa` because the contract-diff row preserves binary steering, new-only rerouting, and autorate-baseline authority.
- [222-02]: No mitigation owner phase is required by Plan 222-02 because there are zero mitigate and zero no-go findings.
- [222-03]: Confirmed v1.47 peeled commit `bee343b0c2f16207101aec82007a5e55fa9b6407` as the SAFE-12 controller-path source floor.
- [222-03]: SAFE-12 boundary verification requires both empty committed controller-path diff and clean staged/unstaged/untracked/porcelain dirty-tree state.
- [223-01]: Selected FULL I/O SEAL option (a) for the replay harness; all `SteeringDaemon.run_cycle()` live-I/O seams are sealed through constructor injection, post-construction fake CAKE reader assignment, tempdir state, and urlopen/socket guards to preserve daemon-path fidelity without steering-source or controller-path mutation.
- [223-02]: Classified the pre-enabled-rule clean restart fixture as `reproduced-bug`; steering remains effectively enabled through cycles 0–13 before recovery disables at cycle 14, so Phase 224 must not proceed unless a fix lands or operator accepts risk.
- [223-03]: Reported restart persistence separately from the three spine invariants; the clean-restart symptom is authority/persistence drift, not a binary-state-shape violation.
- [223-03]: SAFE-12 passed against v1.47 close `bee343b0c2f16207101aec82007a5e55fa9b6407` with Phase 222 schema compatibility and empty committed/staged/unstaged/untracked/porcelain controller-path checks.

## Decisions (v1.47)

- [v1.47 Roadmap]: 3-phase LOCKED scope per joint Claude + Codex operator decision 2026-05-30. Final order: 219 (D) → 220 (A1) → 221 (A2).
- [v1.47 Roadmap]: Phase 218 reserved as parallel event-gated v1.45 VERIFY watch-list; v1.47 phases start at 219.
- [v1.47 Roadmap]: SAFE-11 cross-cutting at every phase boundary; expanded allowlist beyond `src/wanctl/` to cover `configs/`, `deploy/systemd/`, `scripts/`, `tests/fixtures/phase22*/`, `docs/`.
- [v1.47 Roadmap]: Stdlib-only mandate (`statistics`, `random`, `math`, `json`, `sqlite3`, `gzip`) carries forward from Phase 214 D-10. No SciPy/NumPy/pandas.
- [v1.47 Roadmap]: Close-with-prejudice rule for `carried_narrower` verdict locked in CRITERIA-02 to prevent the degenerate "ambiguous forever" outcome.
- [v1.47 Roadmap]: Phase 218 fallback documented: if Phase 218 fires before INGEST-01..05 ship, fall back to v1.44 Phase 208 `wanctl-history --ingestion-rate` CLI as-is.
- [219-02]: D-17 version-fork preserved the v1.44 ingestion-rate JSON envelope unless `--by-table` or `--rolling` is set.
- [219-02]: D-18 bucketed ingestion reads use a single `GROUP BY metric_name` pass and emit one null row per failed DB/window.
- [219-03]: Used in-process `per_wan_ingestion_rate_bucketed` import for operator-summary digest to avoid subprocess overhead while staying out-of-band.
- [219-03]: Pre-gathered ingestion rows before hard-red queries so D-22 hard-red failures cannot suppress ingestion-rate lines.
- [219-03]: Preserved `printed` as hard-red-only and added `ingestion_printed` as the D-26 counter.
- [219-04]: D-19 kept the cron script at `scripts/phase219_ingestion_digest.py` so direct and `python -m scripts.phase219_ingestion_digest` invocation both work.
- [219-04]: D-21 reused `wanctl.state_utils.atomic_write_json` for collision-safe ingestion snapshot writes despite the normal scripts-to-src boundary.
- [219-04]: D-23 validates `wanctl-history` subprocess stdout with `json.loads` before atomic persistence.
- [219-04]: D-27 production profile passed avg/p99 gates with cron active: 2.857ms avg, 6.4ms p99 over 73,603 samples.
- [220-03]: YAML base_sha remains the only source-floor authority; PHASE220_BASE_SHA is accepted only when it matches YAML.
- [220-03]: ATT egress validation is hard-fail by default; missing egress_signature exits 4 before curl and mismatched live egress exits 2.
- [220-04]: Wet dallas/Spectrum daytime rehearsal reproduced the Phase 214 canonical anchor: verdict `ambiguous`, primary_driver `reflector_loss`, comparison `✓ MATCH`.
- [220-04]: Phase 220 source-floor semantics are operator-facing and verified as protected-path drift checks against base_sha, not exact HEAD equality.
- [221-02]: Plan 03 readiness latched after 54/54 deduplicated valid replicates, canonical_complete=6, supplemental_incomplete=0; aggregator remains deferred to Plan 03.
- [221-03]: Published `carried_narrower_with_close_with_prejudice_rule` as the authoritative post-D-10 BGP-overlay verdict while preserving raw `defect_located` `matrix_verdict` for audit.
- [221-03]: D-10 BGP overlay excluded three BGP-flagged defect cells using the Phase 220 aggregator `matrix_verdict()` helper as the single source of verdict logic.
- [v1.47 Close]: Open-artifact audit at close showed 23 carry-forward items from v1.46 close (zero new v1.47 debt); acknowledged-and-closed per operator decision. Phase directories archived to `.planning/milestones/v1.47-phases/`.

## Decisions (v1.46)

- [212-01]: Used `sudo -n` for read-only production config/state reads after unprivileged reads were permission-blocked; this preserved the no-mutation boundary while allowing deployed endpoint/config evidence capture.
- [214-06]: Official three-window Spectrum/Dallas matrix verdict is `ambiguous` (daytime/prime-time p99 606/560ms ambiguous, off-peak p99 120ms pass), primary driver `reflector_loss`, signal disposition `none`. Folded `tcp_12down` todo carried-narrower rather than closed.
- [214-06]: Supplemental Vultr Dallas/Chicago runs (severe loaded p99 745/651ms) are NOT part of the canonical matrix but keep target/path sensitivity a live hypothesis for v1.47.
- [215-03]: Bounded VOID exhausted on three ceiling-20 leg-B attempts, so Spectrum was targeted-rolled back to upload ceiling 18; no ceiling-20 WIN was kept.
- [216-01]: Closed Phase 196 as no-change / resolved-by-197; Phase 197's tests are the semantic proof and Phase 213 only shows no current symptom.
- [217-02]: Final passing capture used live `journalctl` streaming and was validated at 71,560 cycle samples with router-write coverage present.

## Performance Metrics

| Phase | Plan | Duration | Tasks | Files |
|-------|------|----------|-------|-------|
| Phase 219 P01 | 5min | 3 tasks | 4 files |
| Phase 219 P02 | 7min | 3 tasks | 2 files |
| Phase 219 P03 | 6min | 2 tasks | 3 files |
| Phase 219 P04 | checkpointed; production capture 62min | 4 tasks | 5 files |
| Phase 220 P01 | 10min | 5 tasks | 31 files |
| Phase 220 P02 | 7min | 3 tasks | 4 files |
| Phase 220 P03 | 6min | 2 tasks | 2 files |
| Phase 220 P04 | checkpointed; wet rehearsal completed 2026-06-01 | 3 tasks | 8 files |
| Phase 221 P01 | 5 min | 3 tasks | 3 files |
| Phase 221 P02 | 3min | 3 tasks | 2 files |
| Phase 221 P03 | 5 min | 3 tasks | 3 files |
| Phase 221 P04 | 4 min | 6 tasks | 4 files |
| Phase 222 P01 | 4min 12s | 5 tasks | 7 files |
| Phase 222 P02 | 1min 58s | 4 tasks | 5 files |
| Phase 222 P03 | 4min 10s | 3 tasks | 3 files |
| Phase 223 P01 | ~45 min | 4 tasks | 20 files |
| Phase 223 P02 | 16 min | 3 tasks | 9 files |
| Phase 223 P03 | 11 min | 2 tasks | 5 files |
| Phase 223 P04 | 13 min | 6 tasks | 13 files |
| Phase 224 P01 | 6 min | 2 tasks | 3 files |
| Phase 224 P02 | 6 min | 2 tasks | 3 files |
| Phase 225 P01 | 4min | 2 tasks | 2 files |
| Phase 225 P02 | 6min | 2 tasks | 2 files |
| Phase 225 P03 | 5min | 3 tasks | 3 files |
| Phase 225 P04 | ~9min | 3 tasks | 1 file |
| Phase 225 P05 | ~3min | 1 task | 1 file |
| Phase 226 P02 | 5min | 2 tasks | 14 files |
| Phase 226 P01 | 19min | 4 tasks | 55 files |
| Phase 226 P03 | 3min | 3 tasks | 3 files |
| Phase 226 P04 | 2min | 2 tasks | 4 files |
| Phase 226 P05 | 6min | 4 tasks | 8 files |
| Phase 227 P01 | 6 min | 3 tasks | 4 files |
| Phase 227 P02 | 4 min | 2 tasks | 3 files |
| Phase 227 P04 | 6 min | 4 tasks | 6 files |
| Phase 229 P01 | 5min | 2 tasks | 1 file |
| Phase 229 P02 | 5min | 2 tasks | 1 file |
| Phase 229 P03 | 10min | 3 tasks | 2 files |
| Phase Phase 230 PP01 | 9min | 3 tasks tasks | 4 files files |
| Phase 230 P02 | 8min | 2 tasks | 3 files |
| Phase 231 P01 | checkpointed | 2 tasks | 4 files |
| Phase 231 P02 | checkpointed; continuation 2min | 3 tasks | 8 files |
| Phase 231 P03 | 17 min | 2 tasks | 7 files |
