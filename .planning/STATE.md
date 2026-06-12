---
gsd_state_version: 1.0
milestone: v1.52
milestone_name: Silicom Bypass Operationalization
status: executing
stopped_at: Completed 235-04-PLAN.md
last_updated: "2026-06-12T20:24:08.880Z"
last_activity: 2026-06-12 -- Phase 236 planning complete
progress:
  total_phases: 3
  completed_phases: 1
  total_plans: 6
  completed_plans: 4
  percent: 33
---

# Session State

## Project Reference

See: .planning/PROJECT.md (updated 2026-06-12 after v1.51 milestone close)

**Core value:** Sub-second congestion detection with 50ms control loops, achieved through systematic performance optimization and code quality improvements while maintaining production reliability.
**Current focus:** Phase 236 — watchdog fail open two mode reconciliation

## Current Position

Phase: 236
Plan: Not started
Status: Ready to execute
Last activity: 2026-06-12 -- Phase 236 planning complete

## Deferred Items (carried into next milestone)

Re-acknowledged at v1.51 milestone close 2026-06-12 via `/gsd-complete-milestone` Acknowledge-all path. Open set shrank from 23 to 12 artifacts: v1.51 resolved the 12 orphan quick-task slugs (META-01), both stale silicom pending todos (META-02), the Phase 230 Nyquist PARTIAL (META-03), the `phase231-rollback.sh` confirm-path risk (FIX-01), and the digest-permission todo (FIX-02). Remaining open: 1 debug-session index file (false positive), 6 pending todos (event-gated/operational, incl. 2026-06-04 fping eval and 2026-06-03 diffserv4 retest), 5 dormant seeds. **Zero new v1.51 debt.** The 234-VERIFICATION SAFE-15 freshness gap found at close was fixed during close (evidence regenerated at HEAD `aa200dd3`, re-verified 11/11) — not deferred.

<details>
<summary>Prior acknowledgment (v1.50 close, 2026-06-10)</summary>

Re-acknowledged at v1.50 milestone close 2026-06-10 via `/gsd-complete-milestone` Acknowledge-all path. All 23 open artifacts remain the same pre-existing carry-forward set acknowledged at v1.47, v1.48, and v1.49 closes (1 debug-session index, 12 orphan quick-task slugs, 5 dormant seeds, 5 event-gated/out-of-scope todos). **Zero new v1.50 debt.** New context at this close: v1.50 audit recorded Phase 230 Nyquist PARTIAL (`nyquist_compliant: false`, optional retroactive `/gsd:validate-phase 230`), pre-existing Phase 220/221 boundary-test noise (classified in archived `milestones/v1.50-phases/230-*/deferred-items.md`), and a residual confirm-path fix in `phase231-rollback.sh` to land before any future live rollback exercise. Phase 218 watch remains dormant (instrumentation lives in the non-live native controller).

**v1.51 directly addresses several carry-forward items:** the 12 orphan quick-task slugs (META-01 → Phase 234), the silicom todos/SEED-006 reconciliation (META-02 → Phase 234), the Phase 230 Nyquist PARTIAL (META-03 → Phase 234), the `phase231-rollback.sh` confirm-path fix (FIX-01 → Phase 232), and the operator-summary digest permission todo (FIX-02 → Phase 232).

</details>

| Category | Item | Status |
|----------|------|--------|
| requirements | VERIFY-01 | deferred to Phase 218 — needs natural production flapping event; Phase 218 watch dormant (native controller not live) |
| requirements | VERIFY-02 | deferred to Phase 218 — gated on VERIFY-01 + ALERT-03 audit; dormant |
| requirements | RECLAIM-04 | deferred indefinitely — now a cake-autorate config question, not a wanctl probe-shape question |
| phases | Phase 218 (Deferred v1.45 VERIFY Watch-List Closure) | dormant; instrumentation lives in non-live native controller |
| debug_sessions | knowledge-base | unknown (index file, not active investigation) |
| todos | 2026-04-08-investigate-tcp-12down-latency-spikes-under-multi-flow-downl | **CLOSED 2026-06-02 by v1.47 Phase 221** — close-with-prejudice per CRITERIA-02 |
| todos | 2026-04-17-ingestion-rate-tool | **CLOSED 2026-05-30 by v1.47 Phase 219** |
| todos | 2026-04-17-investigate-steering-degraded-on-clean-restart | **FOLDED into v1.48 Phase 223** |
| todos | 2026-04-17-monitor-flapping-peak-count-on-next-docsis-event | pending — Phase 218 trigger; dormant |
| todos | 2026-04-17-operator-summary-digest-permission-handling | **CLOSED 2026-06-11 by Phase 232 Plan 03** — validated already implemented by v1.44 Phase 208 T12/TOOL-03; no reimplementation needed |
| todos | 2026-04-24-resolve-att-cake-primary-canary-after-phase-196 | pending (ATT canary already deployed in v1.45) |
| todos | 2026-04-28 silicom todos (×2) | **RESOLVED 2026-06-11 by Phase 234 Plan 01 (META-02)** — pending dupes closed-with-pointer to SEED-006 (canonical dormant carrier, v1.52); work NOT false-closed |
| todos | 2026-04-15-profile-post-hotpath-baseline-on-production-wan | **CLOSED 2026-05-30 by Phase 217** |
| seeds | SEED-003-v143-d14-watchdog-recalibration | dormant |
| seeds | SEED-004-v143-target-edge-churn-instrumentation | dormant |
| seeds | SEED-005-v143-conservative-ul-tuning-sweep | dormant; OUT of v1.51 |
| seeds | SEED-006-v145-silicom-bypass-tooling-and-harness | dormant; **v1.51 META-02 reconciles its planning state only** (build deferred to v1.52) |
| seeds | SEED-007-v145-storage-hygiene-fire-on-change | dormant; OUT of v1.51 (biggest scope-explosion risk) |
| quick_tasks | 12 orphan slugs from older milestones | **RESOLVED 2026-06-11 by Phase 234 Plan 01 (META-01)** — 12 slugs indexed archived-in-place (11 shipped, 1 PLAN-only `005`), none deleted; index in evidence/quick-archive-index.{md,json} |
| residual | `phase231-rollback.sh` confirm-path fix | **v1.51 FIX-01 → Phase 232** (no live rollback exercise) |
| residual | Phase 230 Nyquist PARTIAL | **RESOLVED 2026-06-12 by Phase 234 Plan 02 (META-03)** — operator-approved recorded waiver decisions/phase-230-nyquist-waiver.md; tests green 5/5; archive frontmatter immutable |

### v1.51-shipped-clean

- **Status:** Ready to execute
- **Operator sign-off:** Kevin — 2026-06-12, via /gsd-verify-work 234 (operator-delegated checks, 5/5 pass) → /gsd-complete-milestone → Acknowledge-all path. 10/10 v1.51 requirements satisfied.
- **Why this is acceptable:** Milestone surface was scripts/docs/planning/tests only; SAFE-15 controller-path zero-diff held at every phase boundary and was re-proven fresh at close HEAD `aa200dd3` after the verifier flagged stale evidence. No milestone audit was run (planning/docs-only milestone; operator chose acknowledge+close). `/gsd-secure-phase 234` not run — zero code surface, no threat flags declared.

### v1.50-shipped-clean

- **Status:** v1.51 milestone complete
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
- **Carry-forward task:** Close VERIFY-01 in v1.46 (or later) when a qualifying production DOCSIS event produces an alerts row with `details.peak_transition_count > 30` on either WAN. Now lives as Phase 218 watch-list; dormant.

## Accumulated Context

### Roadmap Evolution

- **2026-06-10 (v1.51 ROADMAP commit):** v1.51 ROADMAP.md created with 3-phase scope (fine granularity, deliberately small per joint Claude + Codex scoping), continuing phase numbering from v1.50 last phase (231) → Phase 232. Ordering driven by the boundary-gates-sweep dependency: Phase 232 (Cleanup Boundary Guard + Tooling Fixes — BOUND-01, FIX-01, FIX-02; BOUND-01 encodes the future-doc no-delete list as a machine-checkable guard that MUST exist before any sweep so it fails closed on a denylist touch; FIX-01 is pre-rollback hygiene only with NO live rollback exercise; FIX-02 is validate-then-close against v1.44 Phase 208 T12/TOOL-03) → Phase 233 (Gated Repo Hygiene Sweep — SWEEP-01/02/03; superseded trial scripts, residual stale native-ownership docs, Spectrum-only hardcoding removal where a generic `$wan` pattern already exists — no new abstraction; all under the Phase 232 guard) → Phase 234 (Planning Metadata Reconciliation + Closeout — META-01/02/03, SAFE-15; 12 orphan quick-task slugs, silicom todo/SEED-006 single-canonical reconciliation with no false-closing of real bypass work, Phase 230 Nyquist resolution, SAFE-15 milestone-close proof). 10/10 REQs mapped, 0 orphans. SAFE-15 declared as cross-phase controller-path zero-diff invariant verified at every phase boundary (232/233/234) per the SAFE-07..14 precedent; mapped to closeout Phase 234 for traceability. Milestone surface is scripts/docs/planning/tests only — zero src/wanctl controller-path mutation. Out-of-Scope (REQUIREMENTS.md) binding: live rollback exercise, future-doc denylist, SEED-006 build, SEED-007, ROLE-01, TAIL-01, controller threshold/algorithm changes, new `$wan` abstractions.
- **2026-06-09 (v1.50 ROADMAP commit):** v1.50 ROADMAP.md created with 3-phase scope (fine granularity, deliberately small), continuing phase numbering from v1.49 last phase (228) → Phase 229. Natural ordering by production risk: Phase 229 (ATT Deploy Path + Artifact Tests — DEPLOY-01/02, TEST-01/02) → Phase 230 (soak-monitor ATT Coverage — MON-01/02) → Phase 231 (Migration-Held Criteria, Rollback Verification & Doc Sweep — SOAK-01/02, DOCS-04, SAFE-14). 10/10 REQs mapped, 0 orphans. SAFE-14 declared as cross-phase controller-path zero-diff invariant verified at every phase boundary (229/230/231); mapped to closeout phase (231) for traceability.
- **2026-06-03 (v1.49 ROADMAP commit):** v1.49 ROADMAP.md created with 4-phase scope, continuing phase numbering from v1.48 last phase (224) → Phase 225. Two-thread single thesis: 225 (DSCP Survival Trace) → 226 (Baseline + Threshold Lock + Snapshot A) → 227 (Candidate Deploy + Matched Capture) → 228 (Verdict + Closeout, never executed). 13/13 REQs mapped. SAFE-13 cross-phase invariant.
- **2026-06-02 (v1.48 ROADMAP commit):** v1.48 ROADMAP.md created with 3-phase scope: 222 (Steering Drift Audit) → 223 (Staging Proof + Clean-Restart Reproduction) → 224 (Production Canary + Rollback Discipline). SAFE-12 cross-phase invariant.
- **2026-05-30 (v1.47 ROADMAP commit):** v1.47 ROADMAP.md created with 3-phase LOCKED scope: 219 (Scope D Ingestion-Rate Observability) → 220 (Scope A1 Matrix Runner) → 221 (Scope A2 Matrix Evidence + Closeout).

## Session Continuity

Last session: 2026-06-12T16:59:14.818Z
Stopped at: Completed 235-04-PLAN.md
Resume file: None
Archived v1.46 evidence: `.planning/milestones/v1.46-phases/`
Archived v1.47 evidence: `.planning/milestones/v1.47-phases/`
Archived v1.50 evidence: `.planning/milestones/v1.50-phases/`
Archived v1.51 evidence: `.planning/milestones/v1.51-phases/`

## Operator Next Steps

- Start the next milestone with /gsd-new-milestone

## Decisions (v1.52)

- [235-01]: Implemented Plan 01 as a bash-only operator tool with `BPCTL_UTIL`, `LOGGER`, `SILICOM_BYPASS_CONF`, and `SILICOM_MARKS_LOG` seams so automated tests never touch the live card.
- [235-01]: Used `att-modem spec-modem` as the shipped config pair list; stale `sil-spare*` names remain excluded from non-comment artifact content.
- [235-01]: Baseline, systemd unit, and deploy work stay in later plans; Plan 01 only ships TOOL-01..04 CLI behavior and the reusable stateful fake.
- [235-02]: Kept boot policy in `silicom-bypass baseline` so the systemd oneshot and operator CLI share one bpctl invocation path.
- [235-02]: Used read-before-set for all five baseline verbs to avoid redundant card writes while still asserting every read-back string.
- [235-02]: Kept `bpctl-silicom.service` responsible only for module/device setup and moved policy ownership to `silicom-bypass-init.service`.
- [235-03]: Used a TRUE standalone `--silicom-bypass-only <host>` deploy mode that exits before the wanctl release/restart path while installing the init unit's `bpctl-silicom.service` + `wanctl-bpctl-init` dependency chain.
- [235-03]: Accepted observed live bpctl read-back wording variants in the centralized matcher/tests rather than changing baseline order, timings, interfaces, or safety policy.
- [235-03]: Live baseline is verified on `cake-shaper`: `silicom-bypass-init.service` exited `0/SUCCESS` and both pairs remained non-bypass/non-disconnect before and after the run.
- [235-04]: Kept RemainAfterExit=yes on `silicom-bypass-init.service` and fixed the manual reapply runbook to use `systemctl restart`, preserving boot-ordering anchor semantics.
- [235-04]: Hardened only deploy/docs/tests surfaces; `src/wanctl` remained untouched to preserve SAFE-16.

## Decisions (v1.51)

- [v1.51 Roadmap]: 3-phase scope per joint Claude + Codex scoping 2026-06-10. Final order: 232 (Boundary Guard + Tooling Fixes) → 233 (Gated Repo Hygiene Sweep) → 234 (Planning Metadata Reconciliation + Closeout). Deliberately small (v1.50 precedent: 3 phases, 8 plans).
- [v1.51 Roadmap]: BOUND-01 lands in Phase 232 BEFORE any SWEEP work — the machine-checkable denylist guard must exist so the Phase 233 sweep fails closed if a protected ("not safe to remove yet") surface is touched.
- [v1.51 Roadmap]: FIX-01 is pre-rollback hygiene only — `phase231-rollback.sh` confirm-path fix with NO live rollback exercise anywhere in the milestone (live rollback is OUT of scope per REQUIREMENTS.md).
- [v1.51 Roadmap]: FIX-02 is validate-then-close — check live digest behavior against v1.44 Phase 208 T12/TOOL-03 before reimplementing anything; reimplement only if the acceptance criterion is unmet.
- [v1.51 Roadmap]: META-02 reconciles silicom todo/SEED-006 to a SINGLE canonical state without false-closing operationally real bypass work (the ATT migration hit a live bypass-watchdog failure mode); SEED-006 BUILD remains deferred to v1.52.
- [v1.51 Roadmap]: SAFE-15 declared as cross-phase controller-path zero-diff invariant — listed on every phase's requirements line and mapped to closeout Phase 234 for traceability accounting. Same handling as SAFE-14 in v1.50; 9th consecutive milestone holding the SAFE-07..14 discipline. Surface is scripts/docs/planning/tests only.
- [232-01]: BOUND-01 manifest rows carry explicit `must-match-anchor` or `must-exist` policy semantics so Phase 233 sweep/audit tooling can distinguish immutable surfaces from authorized living-doc/tooling drift.
- [232-01]: The future planning doc remains existence-protected even when absent from the anchor tree; it is the canonical denylist source and must fail closed on deletion.
- [232-02]: Confirm `bash -s` omits `-n` so real OpenSSH delivers the stdin rollback payload; read-only probe calls retain `-n`.
- [232-02]: External cake-autorate writer verification treats both `active` and `activating` as fail-closed dual-writer hazards after native rollback.
- [232-03]: FIX-02 closes by validation against v1.44 Phase 208 T12/TOOL-03; current tests already prove the digest permission tolerance, so no source reimplementation was needed.
- [232-03]: SAFE-15 phase-boundary evidence reuses the phase225 checker; its `configs/att.yaml` assertion is broader than the controller-path invariant and should be read as a config-drift guard, not part of SAFE-15 itself.
- [232-04]: BOUND-01 guard status classification treats regular-file presence as mandatory before hash comparison and requires tracked status for anchor-present protected rows; anchor-absent future-doc rows may be untracked only while still regular files.
- [233-01]: Operator-approved destructive removal followed the explicit manifest exactly: 80 REMOVE entries under the ignored `.planning/cake-autorate-trials/` subtree were deleted, while the FUTURE denylist source and curated findings/review docs remained present; deletion is intentionally invisible to git except for committed evidence.
- [233-02]: Operator selected `annotate-steering-only` for SWEEP-02: annotate `docs/STEERING.md`, leave `docs/CABLE_TUNING.md` historical references and `docs/SILICOM-BYPASS.md` by-design bypass references as-is, and close residual native-mode doc claims via per-hit disposition evidence.
- [233-03]: Spectrum bridge unit now mirrors ATT's explicit env pattern for identity, interfaces, log/state/metrics paths, and baseline RTT; Kevin approved pinning the script-default `WANCTL_EXTERNAL_BASELINE_RTT=22.535852814520855`, so the repo edit is behavior-preserving and live apply remains an operator-gated redeploy/daemon-reload.
- [233-04]: Kevin approved waiving the full-suite-green acceptance criterion for known Phase 220/221 historical boundary-test failures (`23 failed, 5385 passed, 11 skipped, 2 deselected`); Plan 04 does not claim full-suite green, while SAFE-15 passed with `controller_path_diff_count=0`, independent controller-path diff passed, and BOUND-01 phase-final evidence passed with `overall_pass=true`.
- [234-01]: META-01 quick-archive slugs are archived in place with a pointer index; none deleted, exact slug-set proof used because 11/12 are untracked.
- [234-01]: META-02 keeps SEED-006 as canonical dormant carrier; stale pending silicom duplicates moved to closed/ with v1.52 pointer and unchanged-hash proof.
- [234-02]: Kevin approved the recorded Phase 230 Nyquist waiver at the checkpoint; META-03 is resolved via signed waiver rather than retroactive validation, while archived `230-VALIDATION.md` frontmatter remains immutable and the append-only pointer records the closeout.
- [234-02]: All three Phase 234 META rows are reconciled: META-01 indexed quick-archive slugs, META-02 closed stale silicom pending duplicates with SEED-006 pointer, and META-03 accepted the evidence-backed waiver for the Phase 230 Nyquist PARTIAL.

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

## Performance Metrics

| Phase | Plan | Duration | Tasks | Files |
|-------|------|----------|-------|-------|
| Phase 229 P01 | 5min | 2 tasks | 1 file |
| Phase 229 P02 | 5min | 2 tasks | 1 file |
| Phase 229 P03 | 10min | 3 tasks | 2 files |
| Phase 230 P01 | 9min | 3 tasks | 4 files |
| Phase 230 P02 | 8min | 2 tasks | 3 files |
| Phase 231 P01 | checkpointed | 2 tasks | 4 files |
| Phase 231 P02 | checkpointed; continuation 2min | 3 tasks | 8 files |
| Phase 231 P03 | 17 min | 2 tasks | 7 files |
| Phase 232 P01 | 4 min | 2 tasks | 2 files |
| Phase 232 P02 | 3 min | 3 tasks | 4 files |
| Phase 232 P03 | 6 min | 2 tasks | 3 files |
| Phase 232 P04 | 1 min | 3 tasks | 2 files |
| Phase 233 P01 | checkpointed; continuation 8 min | 3 tasks | 3 files |
| Phase 233 P02 | checkpointed; continuation 10 min | 3 tasks | 8 files |
| Phase 233 P03 | checkpointed; continuation 5 min | 2 tasks | 4 files |
| Phase 233 P04 | checkpointed; continuation 5 min | 1 tasks | 3 files |
| Phase 234 P01 | 4 min | 2 tasks | 7 files |
| Phase 234 P02 | checkpointed; continuation 2 min | 3 tasks | 6 files |
| Phase 235 P01 | 4 min | 2 tasks | 3 files |
| Phase 235 P02 | 4 min | 2 tasks | 4 files |
| Phase 235 P03 | 10 min | 3 tasks | 6 files |
| Phase 235 P04 | 4 min | 2 tasks | 4 files |
