---
phase: 223-staging-proof-clean-restart-reproduction
verified: 2026-06-02T18:19:40Z
status: gaps_found
score: 9/11 must-haves verified
overrides_applied: 0
gaps:
  - truth: "Operator can read evidence that staging steering behavior preserves the spine contract across the replay corpus."
    status: failed
    reason: "The actual spine evidence reports corpus_verdict=breaks, invariant_3_autorate_baseline=breaks for all seven fixtures, and restart_persistence_verdict=breaks for clean-restart-degraded. This is fail-closed evidence, not proof of preservation."
    artifacts:
      - path: ".planning/phases/223-staging-proof-clean-restart-reproduction/evidence/spine-evidence.json"
        issue: "corpus_verdict is 'breaks'; all fixture overall_fixture_verdict values are 'breaks'."
      - path: ".planning/phases/223-staging-proof-clean-restart-reproduction/evidence/spine-evidence.md"
        issue: "Operator-facing report states Phase 224 BLOCKED unless fix lands or operator accepts risk."
      - path: ".planning/phases/223-staging-proof-clean-restart-reproduction/evidence/clean-restart-reproduction.json"
        issue: "outcome is 'reproduced-bug'; effective steering stayed true through cycles 0-13 before recovery at cycle 14."
    missing:
      - "Resolve the restart-persistence / measurement-authority break, or add explicit operator risk acceptance before Phase 224."
      - "Resolve or reclassify the invariant-3 spectrum_state_write_attempted=True finding; current evidence says it breaks autorate-baseline authority."
  - truth: "Operator can run `.venv/bin/python tests/integration/steering_replay/replay_harness.py --all` and get durable JSON output covering every fixture in the corpus, including the Plan 02 clean-restart-degraded row."
    status: failed
    reason: "The standalone --all path excludes clean-restart-degraded by design and overwrites replay-results.{json,md} with only six fixtures, removing the Plan 02 appended clean-restart row."
    artifacts:
      - path: "tests/integration/steering_replay/replay_harness.py"
        issue: "fixture_paths(include_clean_restart=False) is used by run_all(); main --all writes replay-results.json/md without the clean-restart fixture."
      - path: ".planning/phases/223-staging-proof-clean-restart-reproduction/evidence/replay-results.json"
        issue: "Committed artifact has the clean-restart row, but the documented operator command clobbers it."
    missing:
      - "Make --all either include clean-restart-degraded or preserve/append the Plan 02 observation row when writing replay-results.{json,md}."
---

# Phase 223: Staging Proof + Clean-Restart Reproduction Verification Report

**Phase Goal:** Operator can prove the aligned steering daemon preserves the spine contract against pre-drift behavior captured from runtime, and the folded `steering-degraded-on-clean-restart` symptom is either reproduced and resolved or fail-closed documented before any production touch. Folded todo `2026-04-17-investigate-steering-degraded-on-clean-restart` closes here.
**Verified:** 2026-06-02T18:19:40Z
**Status:** gaps_found
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Operator can run the offline pytest replay harness. | ✓ VERIFIED | `.venv/bin/pytest -o addopts='' tests/integration/steering_replay/ -v` passed: 19 tests in 7.31s. |
| 2 | Standalone replay harness runs offline and emits JSON. | ⚠ PARTIAL | `.venv/bin/python tests/integration/steering_replay/replay_harness.py --all` exited 0, but it overwrote replay-results with only six fixtures and removed `clean-restart-degraded`. |
| 3 | Fake RouterOS transport uses the real daemon-facing surface and blocks live router calls. | ✓ VERIFIED | `FakeRouterTransport` defines only `get_rule_status`, `enable_steering`, `disable_steering`; `__getattr__` records DENIED and raises. Pytest I/O seal tests passed. |
| 4 | Harness state and I/O are staging-only, with no production paths or live sockets. | ✓ VERIFIED | `conftest.py` redirects state/log/lock/storage to workspace, disables metrics DB, blocks urlopen/socket; pytest `test_harness_does_not_touch_production_paths` and per-fixture I/O seal checks passed. |
| 5 | Fixture corpus has explicit harness mode and confidence timing. | ✓ VERIFIED | `README.md` documents hysteresis-only vs confidence; `onset-degraded-confidence.yaml` has derived 40/60/600 cycle budgets and pytest budget gate passed. |
| 6 | Clean-restart symptom is reproduced or fail-closed documented. | ✓ VERIFIED | `clean-restart-reproduction.json` reports `outcome: reproduced-bug`, `cycle_1_observed_state: SPECTRUM_DEGRADED`, `cycle_1_effective_steering_state: true`, `recovery_cycle_to_GOOD: 14`; Markdown marks Phase 224 blocked. |
| 7 | PROOF-02 classification uses effective steering state, not only enable calls. | ✓ VERIFIED | JSON has `pre_steering_rule_state: true`, empty `enable_steering_call_log`, effective steering true for cycles 0-13, and `disable_steering` at cycle 14. |
| 8 | Folded todo is annotated, not silently deleted. | ✓ VERIFIED | `.planning/todos/pending/2026-04-17-investigate-steering-degraded-on-clean-restart.md` contains `## PROOF-02 Closure (Phase 223)` with outcome, rationale, evidence links, and fix-held note. |
| 9 | Operator can read evidence that staging steering preserves the spine contract. | ✗ FAILED | `spine-evidence.json` says `corpus_verdict: breaks`; all 7 fixtures have `overall_fixture_verdict: breaks`, and clean restart has `restart_persistence_verdict: breaks`. |
| 10 | No production mutation occurred in this phase. | ✓ VERIFIED | Phase artifacts and code are tests/planning evidence only; no deploy scripts or production runtime paths mutated. Harness socket/HTTP seals passed. |
| 11 | SAFE-12 controller-path source remains byte-identical to v1.47 close. | ✓ VERIFIED | `safe12-boundary-check.json` has `passed: true`, `committed_clean: true`, `dirty_tree_clean: true`, baseline `bee343b0...`; live git diff/status checks on SAFE-12 paths produced no output. |

**Score:** 9/11 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|---|---|---|---|
| `tests/integration/steering_replay/replay_harness.py` | Standalone + pytest replay entrypoint | ⚠ PARTIAL | Substantive and wired, but `--all` excludes `clean-restart-degraded` and clobbers integrated corpus evidence. |
| `tests/integration/steering_replay/fake_router_transport.py` | RouterOSController-shaped fake | ✓ VERIFIED | Correct method surface; denial logging/raising exists. |
| `tests/integration/steering_replay/conftest.py` | Tempdir, fakes, URL/socket seals, daemon factory | ✓ VERIFIED | Fixtures wire `SteeringDaemon` to fake router/cake/baseline and enforce production path guard. |
| `tests/integration/steering_replay/test_replay_corpus.py` | Corpus pytest entrypoint | ✓ VERIFIED | Exercises all non-clean fixtures; full suite passed. |
| `tests/integration/steering_replay/test_clean_restart.py` | Clean restart pytest/evidence entrypoint | ⚠ WARNING | Functional in full suite, but review warning WR-02 notes the documentation test reads pre-existing evidence when run alone. |
| `tests/integration/steering_replay/fixtures/clean-restart-degraded.yaml` | PROOF-02 fixture | ⚠ WARNING | Fixture is substantive and reproduces the symptom; review warning WR-01 notes `cycle_1_observed_current_state` target name does not match emitted `cycle_1_observed_state`. |
| `evidence/clean-restart-reproduction.{json,md}` | Structured/operator PROOF-02 evidence | ✓ VERIFIED | Parses, records `reproduced-bug`, effective steering window, and Phase 224 block recommendation. |
| `evidence/replay-results.{json,md}` | Integrated corpus evidence | ⚠ PARTIAL | Committed artifact contains clean row, but the documented standalone `--all` command removes it. |
| `evidence/spine-evidence.{json,md}` | PROOF-03 per-invariant verdicts | ✗ FAILED | Artifact exists and is well structured, but verdict is `breaks`, not preservation. |
| `evidence/safe12-boundary-check.{json,md}` | SAFE-12 boundary proof | ✓ VERIFIED | Matches expected schema keys and reports pass. |

### Key Link Verification

| From | To | Via | Status | Details |
|---|---|---|---|---|
| `pytest tests/integration/steering_replay/ -v` | replay harness + fixture corpus | pytest calls `run_fixture()` | ✓ WIRED | Full suite passed; per-fixture tests use `fixture_paths()` and I/O seal tests. |
| `replay_harness.py --all` | `evidence/replay-results.{json,md}` | `main()` writes both files | ✗ WIRED-BUT-WRONG | Writes evidence, but excludes clean-restart fixture and can erase integrated corpus proof. |
| `clean-restart-degraded.yaml` | `clean-restart-reproduction.json` | `test_clean_restart_reproduction_runs()` | ✓ WIRED | Evidence includes required effective-state and outcome fields. |
| `clean-restart-reproduction.md` | folded todo | closure annotation | ✓ WIRED | Todo contains PROOF-02 closure with links. |
| `replay-results.json` + `clean-restart-reproduction.json` | `spine-evidence.json` | per-fixture verdict computation | ✓ WIRED | Evidence row exists for all 7 committed fixture rows; verdict is intentionally `breaks`. |
| SAFE-12 allowlist | `safe12-boundary-check.json` | git diff/status commands | ✓ WIRED | JSON and live command checks show no controller-path diff/dirty state. |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|---|---|---|---|---|
| `replay_harness.py` | fixture cycles/results | YAML fixtures -> `SteeringDaemon.run_cycle()` -> fake logs | Yes | ✓ FLOWING |
| `clean-restart-reproduction.json` | outcome/effective steering | `run_fixture()` result -> `_build_evidence()` classification | Yes | ✓ FLOWING |
| `spine-evidence.json` | per-invariant verdicts | `replay-results.json` + `clean-restart-reproduction.json` | Yes, but verdict is failing | ⚠ FLOWING-FAIL |
| `safe12-boundary-check.json` | pass booleans/path diffs | git diff/status evidence | Yes | ✓ FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|---|---|---|---|
| Full replay pytest suite | `.venv/bin/pytest -o addopts='' tests/integration/steering_replay/ -v` | `19 passed in 7.31s` | ✓ PASS |
| Standalone replay harness | `.venv/bin/python tests/integration/steering_replay/replay_harness.py --all` | exit 0, but rewrote replay-results without clean row | ✗ FAIL |
| SAFE-12 dirty tree/baseline check | `git diff/status` restricted to SAFE-12 paths | no output | ✓ PASS |
| Evidence JSON parse and key sanity | Python JSON checks | replay=7 committed fixtures after restore, clean outcome reproduced-bug, spine=breaks, SAFE-12 pass | ⚠ PASS-WITH-GAPS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|---|---|---|---|---|
| PROOF-01 | 223-01 | Offline replay/fixture harness exercises post-drift code against canonical behavior | ⚠ PARTIAL | Pytest and standalone run work; standalone `--all` does not preserve full integrated corpus after Plan 02. |
| PROOF-02 | 223-02 | Reproduce clean-restart symptom or fail-closed document why not feasible | ✓ SATISFIED | `clean-restart-reproduction.{json,md}` and todo closure record `reproduced-bug` and Phase 224 block/fix-held note. |
| PROOF-03 | 223-03 | Evidence staging behavior preserves spine contract across replay corpus | ✗ BLOCKED | `spine-evidence.{json,md}` exists but says `corpus_verdict: breaks`; preservation is not achieved. |
| SAFE-12 | 223-03 / cross-phase | Controller-path zero diff vs v1.47 close | ✓ SATISFIED | `safe12-boundary-check.json` passed; live git checks on SAFE-12 paths were clean. |

No orphaned Phase 223 requirement IDs found in `REQUIREMENTS.md`: PROOF-01, PROOF-02, PROOF-03, and SAFE-12 are all mapped to Phase 223 / v1.48 cross-phase traceability.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|---|---:|---|---|---|
| `tests/integration/steering_replay/fixtures/clean-restart-degraded.yaml` | 47 | Declared `cycle_1_observed_current_state` but evidence emits `cycle_1_observed_state` | ⚠ Warning | Matches code review WR-01; does not block current evidence but weakens declared observation contract. |
| `tests/integration/steering_replay/test_clean_restart.py` | 246-247 | Reads pre-existing generated evidence | ⚠ Warning | Matches code review WR-02; full suite passes, but single-test/parallel reliability is weaker. |
| `tests/integration/steering_replay/replay_harness.py` | 290-347 | `--all` excludes clean fixture and writes corpus artifact | 🛑 Blocker | Operator command can erase clean-restart integrated evidence row. |

### Human Verification Required

None for this verification decision. The unresolved choice is not a UI/manual test; it is an operator risk-acceptance or fix decision for Phase 224.

### Gaps Summary

Phase 223 produced useful fail-closed evidence, not a passing proof that the steering spine is preserved. The clean-restart symptom is reproduced as `reproduced-bug`, the spine corpus verdict is `breaks`, and Phase 224 is explicitly blocked unless a fix lands or the operator accepts risk. Separately, the documented standalone `--all` command is not safe as an integrated corpus evidence regeneration path because it removes the clean-restart row from `replay-results.{json,md}`.

---

_Verified: 2026-06-02T18:19:40Z_
_Verifier: the agent (gsd-verifier)_
