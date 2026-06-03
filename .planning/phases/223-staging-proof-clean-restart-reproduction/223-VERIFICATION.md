---
phase: 223-staging-proof-clean-restart-reproduction
verified: 2026-06-03T00:35:29Z
status: passed
score: 11/11 must-haves verified
overrides_applied: 0
re_verification:
  previous_status: gaps_found
  previous_score: 9/11
  gaps_closed:
    - "Operator can read evidence that staging steering behavior preserves the spine contract across the replay corpus."
    - "Operator can run `.venv/bin/python tests/integration/steering_replay/replay_harness.py --all` and get durable JSON output covering every fixture in the corpus, including the Plan 02 clean-restart-degraded row."
  gaps_remaining: []
  regressions: []
---

# Phase 223: Staging Proof + Clean-Restart Reproduction Verification Report

**Phase Goal:** Operator can prove the aligned steering daemon preserves the spine contract against pre-drift behavior captured from runtime, and the folded `steering-degraded-on-clean-restart` symptom is either reproduced and resolved or fail-closed documented before any production touch. Folded todo `2026-04-17-investigate-steering-degraded-on-clean-restart` closes here.
**Verified:** 2026-06-03T00:35:29Z
**Status:** passed
**Re-verification:** Yes — after Plan 04 gap closure

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|---|---|---|
| 1 | Operator can run the offline pytest replay harness. | ✓ VERIFIED | `.venv/bin/pytest -o addopts='' tests/integration/steering_replay/ -q` passed: `19 passed in 7.27s`. |
| 2 | Standalone replay harness runs offline and emits JSON for the full integrated corpus including clean restart. | ✓ VERIFIED | `.venv/bin/python tests/integration/steering_replay/replay_harness.py --all` exits 0 from repo root and writes `replay-results.json` with 7 fixtures including `clean-restart-degraded`. |
| 3 | Fake RouterOS transport uses the real daemon-facing surface and blocks live router calls. | ✓ VERIFIED | `FakeRouterTransport` exposes `get_rule_status`, `enable_steering`, `disable_steering`; replay output contains only documented fake-router methods and no denied live-router calls. |
| 4 | Harness state and I/O are staging-only, with no production paths or live sockets. | ✓ VERIFIED | `no_live_io_seal` blocks urlopen/socket calls; replay artifacts show `urlopen_call_count=0` / `socket_connect_count=0`; staging paths are under phase evidence or pytest tempdirs. |
| 5 | Fixture corpus has explicit harness mode and confidence timing. | ✓ VERIFIED | Fixture schema and README document hysteresis-only vs confidence; `onset-degraded-confidence.yaml` records derived 40/60/600-cycle confidence budgets and passes budget gate. |
| 6 | Clean-restart symptom is reproduced or fail-closed documented. | ✓ VERIFIED | `clean-restart-reproduction.json` records `outcome: reproduced-bug`, `cycle_1_effective_steering_state: true`, recovery to GOOD at cycle 14, and fail-closed Phase 224 handling via decision artifact. |
| 7 | PROOF-02 classification uses effective steering state, not only enable calls. | ✓ VERIFIED | JSON records `pre_steering_rule_state: true`, empty `enable_steering_call_log`, true effective steering cycles 0–13, and `disable_steering` at cycle 14. |
| 8 | Folded todo is annotated, not silently deleted. | ✓ VERIFIED | `.planning/todos/pending/2026-04-17-investigate-steering-degraded-on-clean-restart.md` contains `## PROOF-02 Closure (Phase 223)` with outcome/evidence links. |
| 9 | Operator can read evidence that staging steering preserves the three spine invariants across the replay corpus. | ✓ VERIFIED | `spine-evidence.json` reports invariant 1/2/3 all `preserves` for all 7 fixtures; `corpus_verdict` remains `breaks` only because `clean-restart-degraded.restart_persistence_verdict == breaks`, which is documented separately and linked to `.planning/decisions/phase-224-clean-restart-risk-acceptance.md`. |
| 10 | No production mutation occurred in this phase. | ✓ VERIFIED | Changes are confined to tests, fixtures, planning evidence, and the planning decision artifact; no deploy/runtime paths changed. Harness live-I/O seals passed. |
| 11 | SAFE-12 controller-path source remains byte-identical to v1.47 close. | ✓ VERIFIED | `safe12-boundary-check.json` has `passed: true`, `committed_clean: true`, `dirty_tree_clean: true`, `steering_daemon_clean: true`; live git diff/status checks on controller-path and steering-daemon paths produced no output. |

**Score:** 11/11 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|---|---|---|---|
| `tests/integration/steering_replay/replay_harness.py` | Standalone + pytest replay entrypoint | ✓ VERIFIED | `fixture_paths(include_clean_restart=True)` by default; `run_all()` includes `clean-restart-degraded`; daemon-side spectrum-state write fingerprint uses stat fields + SHA-256. |
| `tests/integration/steering_replay/fake_router_transport.py` | RouterOSController-shaped fake | ✓ VERIFIED | Documented daemon-facing method surface only; denial logging exists for other methods. |
| `tests/integration/steering_replay/conftest.py` | Tempdir, fakes, URL/socket seals, daemon factory | ✓ VERIFIED | Wires `SteeringDaemon` to fake router/cake/baseline and production path guards. Review WR-02 notes CWD-dependent config path for non-repo-root invocation (warning only; documented command is repo-root-relative). |
| `tests/integration/steering_replay/test_replay_corpus.py` | Corpus pytest entrypoint | ✓ VERIFIED | Exercises non-clean corpus explicitly with `include_clean_restart=False`; full package pytest passes. Review WR-01 notes confidence-mode expected decisions are not compared (warning only; not blocking current invariant evidence). |
| `tests/integration/steering_replay/test_clean_restart.py` | Clean restart pytest/evidence entrypoint | ✓ VERIFIED | Documentation test generates fresh evidence via `run_fixture()` / `_build_evidence()` rather than reading committed JSON. |
| `tests/integration/steering_replay/fixtures/clean-restart-degraded.yaml` | PROOF-02 fixture | ✓ VERIFIED | `observation_targets` uses emitted key `cycle_1_observed_state`; pre-enabled + persisted DEGRADED reproduction fixture remains substantive. |
| `evidence/replay-results.{json,md}` | Integrated corpus evidence | ✓ VERIFIED | JSON contains 7 fixture rows including `clean-restart-degraded`; every cycle reports `spectrum_state_write_attempted: false` under daemon-side semantics. |
| `evidence/clean-restart-reproduction.{json,md}` | Structured/operator PROOF-02 evidence | ✓ VERIFIED | Records `reproduced-bug`, effective steering window cycles 0–13, and recovery cycle 14. |
| `evidence/spine-evidence.{json,md}` | PROOF-03 per-invariant verdicts | ✓ VERIFIED | Invariant 1/2/3 preserve on every fixture; restart-persistence break is separate, documented, and tied to risk-acceptance artifact. |
| `evidence/safe12-boundary-check.{json,md}` | SAFE-12 boundary proof | ✓ VERIFIED | Phase 222-compatible schema plus `steering_daemon_clean: true`; allowlist includes controller path and `src/wanctl/steering/`. |
| `.planning/decisions/phase-224-clean-restart-risk-acceptance.md` | Concrete risk-acceptance artifact | ✓ VERIFIED | Contains Symptom, Blast Radius, Evidence Links, Default Disposition, Override Path, and Sign-Off sections; cites ~15 cycles / ~0.75 sec at 50ms. |

### Key Link Verification

| From | To | Via | Status | Details |
|---|---|---|---|---|
| `pytest tests/integration/steering_replay/ -q` | replay harness + fixture corpus | pytest calls `run_fixture()` | ✓ WIRED | 19 package tests passed. |
| `replay_harness.py --all` | `evidence/replay-results.{json,md}` | `main()` writes both files | ✓ WIRED | Regenerates all 7 fixture rows including clean restart. |
| `clean-restart-degraded.yaml` | `clean-restart-reproduction.json` | `test_clean_restart_reproduction_runs()` | ✓ WIRED | Evidence includes effective-state, outcome, recovery, and interaction fields. |
| `clean-restart-reproduction.md` | folded todo | closure annotation | ✓ WIRED | Todo carries PROOF-02 closure block with evidence links. |
| `replay-results.json` + `clean-restart-reproduction.json` | `spine-evidence.json` | per-fixture invariant/restart-persistence computation | ✓ WIRED | All invariant columns preserve; only accepted restart-persistence dimension breaks. |
| `spine-evidence.md` | `.planning/decisions/phase-224-clean-restart-risk-acceptance.md` | Phase 224 Readiness link | ✓ WIRED | Markdown relative link resolves to existing decision artifact. |
| SAFE-12 allowlist | `safe12-boundary-check.json` | git diff/status commands | ✓ WIRED | JSON and live commands show no controller/steering source diff or dirt. |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|---|---|---|---|---|
| `replay_harness.py` | fixture cycles/results | YAML fixtures -> `SteeringDaemon.run_cycle()` -> fake logs/evidence | Yes | ✓ FLOWING |
| `clean-restart-reproduction.json` | outcome/effective steering | `run_fixture()` result -> `_build_evidence()` classification | Yes | ✓ FLOWING |
| `spine-evidence.json` | per-invariant verdicts | `replay-results.json` + `clean-restart-reproduction.json` | Yes | ✓ FLOWING |
| `safe12-boundary-check.json` | pass booleans/path diffs | git diff/status evidence | Yes | ✓ FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|---|---|---|---|
| Full replay pytest suite | `.venv/bin/pytest -o addopts='' tests/integration/steering_replay/ -q` | `19 passed in 7.27s` | ✓ PASS |
| Standalone full corpus regeneration | `.venv/bin/python tests/integration/steering_replay/replay_harness.py --all` | exit 0; writes 7 fixture rows including clean restart | ✓ PASS |
| Compile gate | `.venv/bin/python -m compileall -q src tests` | no output / exit 0 | ✓ PASS |
| SAFE-12 dirty diff/status | restricted `git diff`, `git diff --cached`, `git status --porcelain` | no output | ✓ PASS |
| Non-repo-root absolute harness invocation | absolute `replay_harness.py --fixture ...` from `/tmp/opencode` | fails looking for `configs/steering.yaml` relative to CWD | ⚠ WARNING |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|---|---|---|---|---|
| PROOF-01 | 223-01 / 223-04 | Offline replay/fixture harness exercises post-drift code against canonical behavior | ✓ SATISFIED | Pytest and standalone `--all` both run; integrated evidence includes all 7 fixtures. |
| PROOF-02 | 223-02 | Reproduce clean-restart symptom or fail-closed document why not feasible | ✓ SATISFIED | `clean-restart-reproduction.{json,md}` record `reproduced-bug`; folded todo annotated; risk acceptance artifact documents bounded fail-closed handling before production touch. |
| PROOF-03 | 223-03 / 223-04 | Evidence staging behavior preserves spine contract across replay corpus | ✓ SATISFIED | Invariants 1/2/3 preserve on all fixtures in `spine-evidence.json`; restart-persistence finding is separated and accepted. |
| SAFE-12 | 223-03 / 223-04 / cross-phase | Controller-path zero diff vs v1.47 close | ✓ SATISFIED | `safe12-boundary-check.json` passed; live git diff/status checks clean for controller path and steering daemon. |

No orphaned Phase 223 requirement IDs found in `REQUIREMENTS.md`: PROOF-01, PROOF-02, PROOF-03, and SAFE-12 are all mapped to Phase 223 / v1.48 cross-phase traceability.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|---|---:|---|---|---|
| `tests/integration/steering_replay/replay_harness.py` | 256-259 | Confidence-mode expected decisions skipped | ⚠ Warning | Matches post-Plan-04 review WR-01. Current phase still passes because PROOF-03 invariant evidence is computed from observed outputs, but confidence fixture regression detection is weaker. |
| `tests/integration/steering_replay/conftest.py` | 121 | `Path("configs/steering.yaml")` is CWD-dependent | ⚠ Warning | Matches post-Plan-04 review WR-02. Documented repo-root command works; absolute invocation from another CWD fails. |

### Human Verification Required

None.

### Gaps Summary

No blocking gaps remain. The previous `--all` corpus-regeneration gap is closed, and the prior invariant-3 false positive is corrected to daemon-side spectrum-state writes. The clean-restart restart-persistence behavior remains intentionally unfixed, but it is now explicitly represented as a separate accepted risk via `.planning/decisions/phase-224-clean-restart-risk-acceptance.md`, while the three spine invariants preserve across the replay corpus.

---

_Verified: 2026-06-03T00:35:29Z_
_Verifier: the agent (gsd-verifier)_
