---
phase: 223
reviewers: [codex]
reviewed_at: 2026-06-02T20:28:46Z
cycles: [1, 2, 3, 4]
cycle_1_reviewed_at: 2026-06-02T16:21:21Z
cycle_2_reviewed_at: 2026-06-02T16:42:11Z
cycle_3_reviewed_at: 2026-06-02T17:09:46Z
cycle_4_reviewed_at: 2026-06-02T20:28:46Z
plans_reviewed: [223-01-PLAN.md, 223-02-PLAN.md, 223-03-PLAN.md, 223-04-PLAN.md]
cycle_4_focus: 223-04-PLAN.md (gap closure; plans 01-03 post-execution and out of scope)
---

# Cross-AI Plan Review — Phase 223

## Cycle 1 — Codex Review (initial)

**Summary**
The three-plan slice is directionally solid: audit-first, harness-only staging, no production mutation, explicit PROOF artifacts, and SAFE-12 boundary checking are the right shape. The main risk is that the harness, as specified, may not actually exercise the live steering daemon contract faithfully. I found several concrete mismatches against current source, especially the fake RouterOS API, confidence-mode timing, and PROOF-02 outcome classification.

**Strengths**
- Good phase ordering: Plan 01 harness, Plan 02 clean-restart scenario, Plan 03 evidence rollup + SAFE-12.
- Strong production safety posture: tempdir state, fake router, no deploy, SAFE-12 allowlist.
- Seam inventory before harness design is the right first task.
- Operator-facing artifacts are well defined and useful for Phase 224 readiness.
- PROOF-02 allows bounded fail-closed documentation instead of forcing a blind fix.

**Concerns**
- **HIGH:** Fake router API is wrong for current code. `RouterOSController` exposes `get_rule_status()`, `enable_steering()`, and `disable_steering()` in [daemon.py](/home/kevin/projects/wanctl/src/wanctl/steering/daemon.py:817), not `set_rule_status()`. A fake with only `set_rule_status()` will either fail or test an adapter instead of the daemon's real routing path.
- **HIGH:** Fixture cycle counts are not mode-aware. Production config has confidence scoring live at [configs/steering.yaml](/home/kevin/projects/wanctl/configs/steering.yaml:57), with `2s` sustain, `30s` hold-down, and `3s` recovery. The daemon confidence controller uses `ASSESSMENT_INTERVAL_SECONDS = 0.05` at [daemon.py](/home/kevin/projects/wanctl/src/wanctl/steering/daemon.py:127). A 15-cycle degrade or 35-cycle recovery fixture is too short unless the harness explicitly disables confidence scoring.
- **HIGH:** PROOF-02 classification watches only new `enabled=True` toggles. If the fake starts with the mangle rule already enabled while persisted state is `SPECTRUM_DEGRADED`, there may be no enable toggle but traffic is still effectively steered during healthy cycles. The evidence must record initial rule status and effective steering state per cycle, not just toggle calls.
- **MEDIUM:** PROOF-01 claims canonical pre-drift behavior, but most fixtures are synthesized from the spine contract. That is useful contract testing, but weaker than "captured from runtime." At least one fixture should cite concrete Phase 212/222 runtime evidence beyond the clean-restart case.
- **MEDIUM:** Baseline-authority proof is under-instrumented. Plan 03 wants to prove baseline RTT came from the tempdir autorate state file, but Plan 01's JSON schema only guarantees `baseline_rtt_reads`, not read path, source file value, write attempts, or BaselineLoader call provenance.
- **MEDIUM:** Plan 03 says it matches the Phase 222 SAFE-12 schema, but the existing artifact uses `allowlist_paths` and `dirty_tree.status_porcelain`; the plan defines `allowlist` and `dirty_tree.porcelain`. Either copy the schema exactly or declare a new schema version.
- **LOW:** The plans refer to `WANSteeringDaemon`, but the current class is `SteeringDaemon` at [daemon.py](/home/kevin/projects/wanctl/src/wanctl/steering/daemon.py:1122). Easy fix, but it matters for executable plans.
- **LOW:** Keeping the folded todo in `pending/` with a closure note may confuse todo tooling. Use the project convention, or explicitly mark it closed in a way pending scans understand.

**Suggestions**
- Change `FakeRouterTransport` to implement `get_rule_status()`, `enable_steering()`, and `disable_steering()`. Log method name, cycle, requested effective state, initial state, verification reads, and undocumented calls.
- Pin the harness mode. Either test production confidence mode with cycle windows derived from config, or explicitly create a hysteresis-only config and label the corpus accordingly. Do not mix simple hysteresis expectations with live confidence config.
- Split fixture state into `steering_pre_state` and `autorate_state_by_cycle`; the autorate state should use the real `{"ewma": {"baseline_rtt": ...}, "congestion": {"dl_state": ...}}` shape.
- Use a spy/wrapper around `BaselineLoader.load_baseline_rtt()` or the real loader against a tempdir file, and record `baseline_read_path`, `baseline_read_value`, and `spectrum_state_writes`.
- For PROOF-02, classify based on cycle-1 persisted state plus effective mangle state during healthy input. If `reproduced-bug`, mark Phase 224 blocked unless a fix lands or the operator explicitly accepts the risk.
- For Plan 03, label the "only new connections rerouted" result as a daemon-side surrogate unless the plan also verifies the mangle rule definition from captured/exported RouterOS config.
- Run a cheap SAFE-12 check after any Plan 01 seam edit, not only at final Plan 03.

**Risk Assessment**
Overall risk: **MEDIUM-HIGH as written**. The structure is good, but two issues can invalidate the proof: the fake router does not match the actual daemon API, and the fixture timing does not match production confidence-mode behavior. With those corrected and evidence fields enriched, the plan drops to **LOW-MEDIUM**: still a staging surrogate, but good enough to decide whether Phase 224 can proceed.

---

## Cycle 1 — Consensus Summary

Single-reviewer cycle (Codex only). Synthesis below treats Codex findings as the cycle's consolidated signal.

### Agreed Strengths
- Audit-first slicing across 3 plans (harness → scenario → evidence/SAFE-12) is correctly ordered.
- Strong production safety posture: tempdir state, fake transport, no production mutation, SAFE-12 allowlist.
- PROOF-02 explicitly supports bounded fail-closed documentation rather than forcing a speculative fix.
- Operator-facing evidence artifacts are well-defined and feed Phase 224 readiness.

### Agreed Concerns
Highest priority items (all HIGH, raised by Codex against live source):

1. **Fake router API mismatch** — `RouterOSController` exposes `get_rule_status()` / `enable_steering()` / `disable_steering()`, not `set_rule_status()`. A fake with the wrong surface tests an adapter, not the daemon's routing path.
2. **Fixture cycle counts ignore confidence-mode timing** — production `configs/steering.yaml` uses 2s sustain / 30s hold-down / 3s recovery, with `ASSESSMENT_INTERVAL_SECONDS = 0.05`. 15-cycle degrade / 35-cycle recovery fixtures will not satisfy confidence-mode windows unless confidence scoring is explicitly disabled.
3. **PROOF-02 outcome classification gap** — keying on new `enabled=True` toggles alone misses the case where the rule is already enabled at boot while persisted state is `SPECTRUM_DEGRADED`. Evidence must record initial rule status and effective per-cycle steering state, not only toggle calls.

Secondary (MEDIUM):
- "Canonical pre-drift behavior" claim is weak when most fixtures are synthesized from the spine contract — anchor at least one fixture to concrete Phase 212/222 runtime evidence.
- Baseline-authority proof under-instrumented — capture read path, source file value, write attempts, and BaselineLoader call provenance, not just `baseline_rtt_reads`.
- SAFE-12 schema drift vs Phase 222 — plan defines `allowlist` / `dirty_tree.porcelain`; existing artifact uses `allowlist_paths` / `dirty_tree.status_porcelain`. Match exactly or declare a schema version.

### Divergent Views
None — single-reviewer cycle.

---

## Cycle 2 — Codex Review (post-revision)

Reviewing plans after commit 64df625 (Plan 02 grew 182 → 293 lines; Plan 01 and Plan 03 also enriched). Goal: verify each Cycle 1 HIGH was actually addressed, catch new HIGHs introduced by the revision, and check spine-contract compliance.

### Cycle-2 Summary

The revision fully resolves the three Cycle 1 HIGHs: the fake now targets the real `RouterOSController` API, confidence timing is explicitly mode-gated, and PROOF-02 now keys on initial/effective steering state rather than toggle calls. I do see one new HIGH: the harness still does not explicitly seal all non-RouterOS I/O paths in `run_cycle()`, so an executor could accidentally hit live autorate/CAKE paths or bypass the code paths needed to prove baseline authority.

### HIGH Closure Verdict

- **HIGH #1: Fake RouterOS API mismatch — FULLY RESOLVED**
  Plan 01 now requires `get_rule_status`, `enable_steering`, and `disable_steering`, and explicitly bans `set_rule_status`. This matches live source in `src/wanctl/steering/daemon.py:817`.

- **HIGH #2: Confidence-mode timing — FULLY RESOLVED**
  Plan 01 now requires explicit `harness_mode`, records cycle-budget derivation, defaults to hysteresis-only, and gates confidence fixtures against config-derived cycle counts. This addresses the original timing mismatch. Coverage caveat below (MEDIUM under New Concerns).

- **HIGH #3: PROOF-02 toggle-call keying — FULLY RESOLVED**
  Plan 02 now seeds `initial_steering_rule_state: true`, records `pre_steering_rule_state` and `effective_steering_state_per_cycle`, and classifies the pre-enabled / no-toggle case as `reproduced-bug`.

### New Concerns (Cycle 2)

- **HIGH:** **Offline I/O seams under-specified.** `run_cycle()` calls `update_baseline_rtt()`, `collect_cake_stats()`, and current-RTT loading paths; live source can read CAKE/router stats and autorate health via `BaselineLoader.load_live_rtt()` / `load_live_irtt_rtt()` (`src/wanctl/steering/daemon.py:1000`, `:1936`, `:2064`). Plan 01 only fakes `RouterOSController` and baseline reads, then says to use `update_state_machine` or `run_cycle` "whichever can be driven without networking." That can either leak live reads or bypass the baseline/CAKE paths PROOF-03 claims to prove.

- **MEDIUM:** **Plan 02 reintroduces stale schema names** when appending the clean-restart row: `mangle_toggles` and `baseline_rtt_reads` at `223-02-PLAN.md:256`. Plans 01/03 require `steering_interactions` and `baseline_rtt_per_cycle`, so Plan 03 may not be able to classify the clean-restart fixture consistently.

- **MEDIUM:** **Corpus is now mostly `hysteresis-only`,** while deployed steering config has `use_confidence_scoring: true` and `dry_run: false` in Phase 212 evidence. That fixes Cycle 1 timing but weakens Phase 224 readiness unless at least one confidence-mode fixture exercises the live-mode path with derived budgets.

- **MEDIUM:** **Runtime-evidence provenance is muddy.** Plan 01 expects `.planning/phases/212-*`, but Phase 212 is archived under `.planning/milestones/v1.46-phases/...`; Plan 02 also labels the clean-restart fixture `derived-from-phase-212-evidence`, while the actual symptom source is the folded todo and Phase 212 explicitly says reproduction was not attempted.

- **MEDIUM:** **Plan 03 maps `reproduced-bug` to a binary-on/off invariant break.** A pre-enabled rule during persisted DEGRADED is still binary; the real concern is restart persistence / measurement-authority. Keep that separate or classify it under baseline/decision authority.

- **LOW:** `__getattr__` denial should log attempted undocumented calls before raising; otherwise invariant-2 evidence may show an exception without the attempted method name.

### Suggestions

- Add explicit fixture fakes for current RTT and CAKE stats: e.g. `FixtureBaselineLoader.load_live_rtt()`, `load_live_irtt_rtt()`, and `FixtureCakeReader.read_stats()`. Patch `daemon.cake_reader`, and monkeypatch `urllib.request.urlopen` / socket creation to fail in tests.
- Normalize the clean-restart appended row to the enriched schema: `steering_interactions`, `baseline_rtt_per_cycle`, `effective_steering_state_per_cycle`, `pre_steering_rule_state`.
- Add one confidence-mode smoke fixture using config-derived budgets, or explicitly label Phase 223 as hysteresis-only proof with a required Phase 224 confidence pre-canary gate.
- Add `derived-from-folded-todo` to `corpus_source`, and allow archived Phase 212 evidence paths.
- Split `restart_persistence_verdict` from the three spine invariants in `spine-evidence`.

### Risk Assessment

**MEDIUM.** The three original HIGHs are genuinely resolved, and SAFE-12/schema discipline is much improved. The remaining risk is harness fidelity: unless all `run_cycle()` I/O is sealed and the Plan 02 schema drift is fixed, the phase can produce evidence that looks complete but is either nondeterministic or not actually proving the claimed daemon paths.

---

## Cycle 2 — Consensus Summary

Single-reviewer cycle (Codex only).

### HIGH Count Transition

| Cycle | HIGH count | Status |
|-------|-----------|--------|
| 1     | 3         | Initial — fake API, confidence timing, PROOF-02 keying |
| 2     | 1         | Cycle 1 HIGHs all FULLY RESOLVED; one new HIGH (I/O seams) |

Strict decrease from 3 → 1; convergence loop continues.

### Cycle 2 — Strengths
- All three Cycle 1 HIGHs fully resolved with verifiable plan-level mechanisms (schema fields, acceptance criteria, in-plan assertions).
- SAFE-12 schema-equivalence test against Phase 222 is a strong cross-phase consistency control.
- PROOF-02 classification now distinguishes pre-enabled + persisted-DEGRADED from clean-toggle behavior.
- Plan 02's "Phase 224 BLOCKED" line gives the downstream operator an unambiguous gate signal.

### Cycle 2 — Outstanding HIGH (carry into next revision)

1. **Offline I/O seams under-specified.** The harness fakes `RouterOSController` and baseline-loader reads, but `run_cycle()` also touches CAKE stats, live-RTT (`load_live_rtt`, `load_live_irtt_rtt`), and possibly other I/O. Either (a) seal those seams with explicit fakes and assert no socket / no other-process I/O occurs during a fixture run, or (b) document precisely which daemon path is exercised (and which is bypassed) so PROOF-03 claims match reality.

### Divergent Views
None — single-reviewer cycle.

---

## Cycle 3 — Codex Review (post-revision, final convergence cycle)

Reviewing plans after commit c76ca48 which addressed the Cycle 2 HIGH (offline I/O seams) by adopting **option (a) FULL I/O SEAL** end-to-end via `daemon.run_cycle()`, plus all 5 Cycle 2 MEDIUMs. Goal: verify each Cycle 2 finding is actually addressed in revised plan text, catch new HIGHs introduced by the full-seal revision, validate `daemon.cake_reader` post-construction injection feasibility, confirm SAFE-12 still holds, and verify the new `restart_persistence_verdict` dimension is well-defined.

### Cycle 3 Summary

Cycle 3 closes the Cycle 2 HIGH at the plan level and materially closes all five Cycle 2 MEDIUMs. The revised Plan 01 now chooses FULL I/O SEAL, drives `daemon.run_cycle()`, adds CAKE/live-RTT/socket/urlopen/state/metrics seals, and records `daemon_io_paths_exercised`. Plan 02 schema drift is fixed in the append step. Plan 03 cleanly splits restart persistence from the three spine invariants. **No unresolved HIGHs remain. Two new MEDIUM executor hazards surface.**

### Cycle-2 HIGH Closure Verdict

- **HIGH: Offline I/O seams — FULLY RESOLVED.**
  Plan 01 explicitly chooses option (a) FULL I/O SEAL at `223-01-PLAN.md:148`. Inventory must cover CAKE stats, live RTT/urlopen, state saves, and metrics DB writes at `223-01-PLAN.md:159`. Task 02 adds `FakeCakeReader`, `FixtureBaselineLoader`, `_seal_urlopen`, and `_seal_socket` at `223-01-PLAN.md:202`. Task 04 requires `daemon.run_cycle()` end-to-end, `daemon_io_paths_exercised`, and zero urlopen/socket calls at `223-01-PLAN.md:307`.

### Cycle-2 MEDIUM Closure Verdicts

- **MEDIUM #1 (stale schema names): FULLY RESOLVED** for executable schema. Plan 02 Task 03 uses `steering_interactions` and `baseline_rtt_per_cycle`, and its verify command asserts `mangle_toggles` / `baseline_rtt_reads` are absent from the row at `223-02-PLAN.md:256`. Minor stale prose remains in artifact-description text ("mangle toggles" at `223-02-PLAN.md:33`), but not as a schema field.

- **MEDIUM #2 (confidence-mode coverage): FULLY RESOLVED.** Plan 01 adds `onset-degraded-confidence.yaml`, derives cycle counts from `configs/steering.yaml` against `ASSESSMENT_INTERVAL_SECONDS = 0.05`, requires `len(cycles) >= derived_sustain_cycles + derived_hold_down_cycles`, and adds a too-short fixture gate at `223-01-PLAN.md:271` and `223-01-PLAN.md:333`.

- **MEDIUM #3 (Phase 212 archive path): FULLY RESOLVED.** Plan 01 cites `.planning/milestones/v1.46-phases/212-production-inventory-and-drift-audit/`, rejects `.planning/phases/212-*`, and requires `provenance_note` fallback if no concrete row exists at `223-01-PLAN.md:269`.

- **MEDIUM #4 (`restart_persistence_verdict` split): FULLY RESOLVED.** Plan 03 defines `restart_persistence_verdict` as a separate dimension, maps `reproduced-bug` to `restart_persistence_verdict = breaks` (NOT to invariant-1 binary-on/off breaks), and includes it in corpus rollup at `223-03-PLAN.md:100` and `223-03-PLAN.md:115`.

- **MEDIUM #5 (`__getattr__` denial logging): FULLY RESOLVED.** `FakeRouterTransport.__getattr__` must log method + cycle and append a denial entry to `interactions_log` before raising, and the verify command calls `t.run_cmd('foo')` and checks the denial row at `223-01-PLAN.md:200` and `223-01-PLAN.md:219`. `FakeCakeReader` gets identical denial behavior at `223-01-PLAN.md:202`.

### New Concerns (Cycle 3)

- **MEDIUM:** Constructor-time config file I/O is not explicitly sealed. Live `SteeringConfig._derive_primary_health_url()` reads `topology.primary_wan_config`, defaulting to `/etc/wanctl/<wan>.yaml`, during config initialization at `src/wanctl/steering/daemon.py:192` and `:209`. Plan 01 broadly says inspect config seams and reject "any other resolved file path," but `daemon_factory` should explicitly set `topology.primary_wan_config` and `config_file_path` to temp fixtures before constructing `SteeringConfig`.

- **MEDIUM:** Plan 01 frontmatter `files_modified` is stale relative to the full-seal tasks. It omits required files such as `fake_cake_reader.py`, `fake_live_rtt_source.py`, `test_io_seal.py`, `test_cycle_budget_gate.py`, `onset-degraded-from-phase212.yaml`, and `onset-degraded-confidence.yaml`, despite later tasks requiring them. If GSD tooling uses frontmatter manifests, evidence/file accounting can drift.

### `daemon.cake_reader` Injection Feasibility

Post-construction assignment is feasible in current live code. `__init__` calls `_init_cake_reader()` once at `src/wanctl/steering/daemon.py:1144`; `_init_cake_reader()` assigns plain `self.cake_reader = CakeStatsReader(...)` at `:1170`. No property/descriptor/`__slots__` found, and no later `_init_cake_reader()` recall in the daemon path. Plan 01 requires the inventory to verify this and Task 02 asserts `daemon.cake_reader is fake_cake_reader`; documented fallback is to mark the seam `needs-edit` in the inventory.

### `restart_persistence_verdict` Definition Review

The new dimension is well-defined and deterministic. The rollup includes four dimensions, with corpus `breaks` triggered if any invariant verdict or any applicable `restart_persistence_verdict` is `breaks`. The only nuance is overlap with invariant 3 (autorate-baseline authority), which Plan 03 explicitly acknowledges in its Methodology section. The specific mapping rule for `clean-restart-degraded` (`reproduced-bug` → `restart_persistence_verdict = breaks`, with invariant-1 `binary_on_off` computed independently) removes ambiguity.

### SAFE-12 Posture

Plans do not mutate controller-path source. The allowlist is correctly limited to `wan_controller.py`, `queue_controller.py`, `cake_signal.py`, `backends/`, `alert_engine.py`, and `fusion*.py`. Reviewer additionally checked the current worktree against `bee343b0c2f16207101aec82007a5e55fa9b6407`; controller-path diff and porcelain status are empty.

### Cycle 3 HIGH Count

**0 unresolved HIGHs.**

### Risk Assessment

**LOW-MEDIUM.** The plan now has the right daemon-path fidelity and closes the prior review loop. Remaining risk is executor hygiene, not plan architecture: constructor-time config path reads need explicit temp overrides, and frontmatter should be brought back in sync with required harness files.

---

## Cycle 3 — Consensus Summary

Single-reviewer cycle (Codex only).

### HIGH Count Transition

| Cycle | HIGH count | Status |
|-------|-----------|--------|
| 1     | 3         | Initial — fake API, confidence timing, PROOF-02 keying |
| 2     | 1         | Cycle 1 HIGHs all FULLY RESOLVED; one new HIGH (I/O seams) |
| 3     | 0         | Cycle 2 HIGH FULLY RESOLVED; all 5 Cycle 2 MEDIUMs FULLY RESOLVED; 2 new MEDIUMs (config-file I/O sealing, frontmatter drift) |

**Convergence achieved.** Strict decrease 3 → 1 → 0 across three cycles. The convergence loop terminates at cycle 3 with zero unresolved HIGHs.

### Cycle 3 — Strengths
- All 6 Cycle 2 findings (1 HIGH + 5 MEDIUMs) close with verifiable plan-level mechanisms (schema fields, acceptance criteria, in-plan assertions, verify commands).
- The FULL I/O SEAL choice (option (a)) is the right architectural call: PROOF-03 spine-invariant verdicts now reflect actual daemon `run_cycle()` execution, not test-side surrogates. The `daemon_io_paths_exercised` audit trail is the right safety net.
- `daemon.cake_reader` post-construction injection is feasible against live source (verified by reviewer) AND Plan 01 has a documented `needs-edit` fallback path if Task 01 inventory discovers a blocker.
- `restart_persistence_verdict` is a clean architectural split — the symptom is restart-persistence / measurement-authority, not a binary-on/off invariant break.
- SAFE-12 verified in live worktree: zero controller-path diff vs `bee343b0c2f16207101aec82007a5e55fa9b6407`.

### Cycle 3 — Outstanding MEDIUMs (carry into execute-phase as executor hygiene)

1. **Config-file I/O sealing.** `SteeringConfig._derive_primary_health_url()` reads `topology.primary_wan_config` at construction time (defaults to `/etc/wanctl/<wan>.yaml`). `daemon_factory` should explicitly override `topology.primary_wan_config` and `config_file_path` to temp fixtures before constructing `SteeringConfig`. (Not a HIGH because the autouse `_seal_urlopen` + `_seal_socket` fixtures would catch any actual live I/O, but the construction-time file read could still touch a production config file — surface it during execute-phase, not a replan blocker.)

2. **Frontmatter `files_modified` drift.** Plan 01 frontmatter lacks `fake_cake_reader.py`, `fake_live_rtt_source.py`, `test_io_seal.py`, `test_cycle_budget_gate.py`, `onset-degraded-from-phase212.yaml`, `onset-degraded-confidence.yaml`. Update frontmatter at execute-phase entry (not a replan blocker — the task bodies and acceptance criteria are the binding contract).

### Divergent Views
None — single-reviewer cycle.

### Convergence Disposition

Cycle 3 produced 0 HIGHs. Strict decrease maintained across all three cycles (3 → 1 → 0). **Loop terminates cleanly without escalation or stall.** Plans are convergence-approved for execute-phase. The two outstanding MEDIUMs are executor-hygiene items, not replan blockers.

---

## Cycle 4 — Codex Review (Plan 04 gap closure)

**Scope:** Plan 04 only — the new gap-closure plan committed at 37dc6f5. Plans 01-03 are post-execution and out of scope for this cycle. Plan 04 closes the 2 verification gaps + 2 code-review warnings recorded in `223-VERIFICATION.md` and `223-REVIEW.md`.

### Summary

Plan 04 is mostly well-scoped and correctly avoids controller-path source and steering-daemon edits. It should close Gap #2 and both review warnings. The weak point is Gap #1: documenting "fix vs accept" options is not the same as adding explicit operator risk acceptance, and `corpus_verdict` will still remain `breaks`. As written, a verifier can reasonably say truth #9 is still not closed.

### Strengths

- No proposed edit to SAFE-12 controller-path files.
- No proposed edit to `src/wanctl/steering/`; harness-only approach is appropriate.
- `--all` including `clean-restart-degraded` directly fixes the corpus clobber bug.
- Reclassifying harness seeding vs daemon writes is legitimate; current code hardcodes `spectrum_state_write_attempted=True`.
- WR-01 and WR-02 fixes are concrete and low-risk.
- Evidence ordering is right: replay results, clean-restart evidence, spine evidence, SAFE-12 recheck.

### Concerns

- **HIGH:** Gap #1 is not fully closed. "Surface the decision in spine-evidence" does not satisfy "add explicit operator risk acceptance." Either write an actual acceptance artifact or keep Phase 224 blocked. Otherwise `corpus_verdict=breaks` remains and truth #9 can still fail.

- **MEDIUM:** Final SAFE-12 verification checks the controller allowlist but does not enforce the added no-`src/wanctl/steering/` constraint. The plan says not to touch it, but the boundary check should prove it.

- **MEDIUM:** The invariant-3 reclassification is valid only if invariant 3 is explicitly narrowed to "daemon must not write autorate state." The clean-restart issue is still a measurement-authority break, just tracked under `restart_persistence_verdict`.

- **MEDIUM:** `mtime_ns`/`st_size` detection can miss same-size/same-timestamp writes. Better include `st_ctime_ns`, inode, and/or content hash, or instrument writes to the exact spectrum path.

- **LOW:** Flipping `fixture_paths()` default is broader than needed. Safer: make `run_all()` explicitly pass `include_clean_restart=True`, and make tests explicitly pass `False`.

- **LOW:** Spine-evidence recomputation remains ad hoc. A committed small generator or test helper would make future verification less fragile than an inline/optional script.

### Suggestions

- Add a required artifact such as `.planning/decisions/phase-224-clean-restart-risk-acceptance.md`, or explicitly leave `phase_224_readiness: blocked`.
- Add final verification for `git diff/status -- src/wanctl/steering/`.
- Rename or supplement the field with `daemon_wrote_spectrum_state` to avoid semantic drift.
- Assert expected `corpus_verdict` and restart-persistence handling explicitly in verify blocks.
- Harden the clean-checkout test shell snippet so missing evidence files do not short-circuit before pytest runs.

### Risk Assessment

Overall risk: **MEDIUM**.

Production/code risk is low because Plan 04 stays in harness/test/evidence space. Verification risk is medium because the main remaining gap may still fail: the plan records a choice, not an acceptance or fix, while the corpus remains `breaks`. The recommended default is to revise Plan 04 to require a concrete acceptance artifact or preserve the Phase 224 block explicitly.

---

## Cycle 4 — Consensus Summary

Single-reviewer cycle (Codex only).

### HIGH Count Transition

| Cycle | HIGH count | Status |
|-------|-----------|--------|
| 1     | 3         | Initial — fake API, confidence timing, PROOF-02 keying |
| 2     | 1         | Cycle 1 HIGHs all FULLY RESOLVED; one new HIGH (I/O seams) |
| 3     | 0         | Cycle 2 HIGH FULLY RESOLVED; all 5 Cycle 2 MEDIUMs FULLY RESOLVED; 2 new MEDIUMs |
| 4     | 1         | New HIGH on Plan 04 — Gap #1 closure mechanism does not satisfy verification language ("explicit operator risk acceptance"). |

### Cycle 4 — Key Findings

- **SAFE-12 spine intact in plan:** Codex confirms Plan 04 proposes no edits to controller-path source or `src/wanctl/steering/`. The architectural boundary is preserved by construction.
- **Gap #2 + WR-01 + WR-02 closures look sound.** The harness-side mechanisms (default flip, fixture rename, self-contained test) directly address the verification findings.
- **Gap #1 invariant-3 reclassification is legitimate** (the hardcoded `True` is genuinely a harness-seeding artifact, not daemon behavior), conditional on the methodology note narrowing invariant 3 to "daemon must not write autorate state."
- **Gap #1 restart-persistence closure is the weak point.** Plan 04 surfaces the operator decision in `spine-evidence.md` rather than producing a concrete acceptance artifact. The verifier may reasonably reject this as not satisfying "either fix … or add explicit operator risk acceptance."

### Cycle 4 — Outstanding HIGH (requires plan revision before execution)

1. **Gap #1 risk-acceptance artifact missing.** Plan 04 should either:
   - (a) Commit a concrete `.planning/decisions/phase-224-clean-restart-risk-acceptance.md` artifact with operator sign-off recorded, OR
   - (b) Keep Phase 224 explicitly blocked in `phase_224_readiness` and accept that truth #9 stays gap-flagged until Phase 224 work (or a follow-up phase) closes it.

   The current "two-options-in-spine-evidence" approach makes the decision visible but does not close the verification gap on its own.

### Cycle 4 — Outstanding MEDIUMs

1. **Steering daemon boundary not asserted in SAFE-12 check.** Plan 04's no-`src/wanctl/steering/` constraint is plan text, not verify-block enforcement. Add `git diff bee343b0c2f16207101aec82007a5e55fa9b6407 -- src/wanctl/steering/` to Task 04-05 (expected empty).
2. **Invariant 3 scope narrowing should be explicit in methodology.** State that invariant 3 is "no daemon-side write to spectrum_state.json during run_cycle()." The clean-restart issue remains a measurement-authority concern tracked under `restart_persistence_verdict`.
3. **Stat-delta detection edge cases.** `mtime_ns`/`st_size` can miss same-size/same-timestamp writes on coarse-mtime filesystems. Add `st_ctime_ns` and/or content hash to the detection.

### Cycle 4 — Outstanding LOWs

1. Default-flip on `fixture_paths()` is broader than necessary; explicit pass-through in `run_all()` and tests would be tighter.
2. Spine-evidence recomputation script is "optional"; committing it as a small helper would reduce future verification fragility.

### Divergent Views

None — single-reviewer cycle.

### Cycle 4 Disposition

Cycle 4 produced 1 HIGH. Plan 04 needs revision before execute-phase: either add the acceptance artifact (Task 04-04 step or new Task 04-06) or explicitly accept that truth #9 stays gap-flagged after Plan 04 with a corresponding update to phase status messaging. The MEDIUMs are executor-hygiene items, with the steering-boundary assertion being the most important to add to the SAFE-12 check.
