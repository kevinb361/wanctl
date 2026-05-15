---
phase: 206-a-b-replay-harness-rollback-gates
verified: 2026-05-15T15:15:10Z
status: gaps_found
score: "4/5 roadmap success criteria verified"
overrides_applied: 0
requirements: [TOPO-04, TOPO-05]
re_verification:
  previous_status: verified
  previous_score: "5/5 roadmap success criteria verified after gap closure 2026-05-15"
  gaps_closed:
    - "Original G1-G4 gap-closure checks remain closed: empty soak, decreasing counters, missing shell value, and mixed post-block metric keys all return rc=2."
  gaps_remaining:
    - "Code-review fail-closed gaps WR-01, WR-02, and WR-03 remain in the actual gate behavior."
  regressions: []
gaps:
  - truth: "The predeploy gate fails closed on malformed/inconsistent restart-counter input."
    status: failed
    reason: "Supplying only one restart counter is treated as no restart input and the restart-rate gate is skipped, returning PASS."
    artifacts:
      - path: "scripts/phase206-gate-check.py"
        issue: "restart_inputs_present requires both counters; exactly-one-counter input falls into the skip branch."
      - path: "scripts/phase206-predeploy-gate.sh"
        issue: "Wrapper can forward only --restart-counter-start or only --restart-counter-end instead of aborting before Python."
    missing:
      - "Abort with rc=2 when exactly one of --restart-counter-start / --restart-counter-end is present."
      - "When --ssh-target samples RC_END, require a start counter or abort; do not let Python skip the restart gate."
  - truth: "The post-soak transition-rate gate fails closed on invalid soak timing windows."
    status: failed
    reason: "A post-soak NDJSON with two valid rows at the same t_monotonic timestamp returns PASS as 0.00/h instead of ABORT."
    artifacts:
      - path: "scripts/phase206-gate-check.py"
        issue: "elapsed_s <= 0 is coerced to 1e-9 hours, allowing zero-duration captures to pass."
    missing:
      - "Require strictly positive elapsed soak duration after sorting timed samples; abort rc=2 when elapsed_s <= 0."
  - truth: "The production predeploy gate cannot be silently altered by test-only local override state."
    status: failed
    reason: "PHASE206_LOCAL_BASELINE_OVERRIDE is applied unconditionally; a hidden environment variable can overwrite restart counters/window and mask a restart breach."
    artifacts:
      - path: "scripts/phase206-gate-check.py"
        issue: "_apply_override() reads PHASE206_LOCAL_BASELINE_OVERRIDE in normal execution before validation."
      - path: "scripts/phase206-predeploy-gate.sh"
        issue: "Wrapper does not clear or reject PHASE206_LOCAL_BASELINE_OVERRIDE before execing the Python gate."
    missing:
      - "Remove the implicit production override, require an explicit test-only flag, or have the wrapper reject/clear PHASE206_LOCAL_BASELINE_OVERRIDE."
human_verification: []
deferred: []
---

# Phase 206: A/B Replay Harness + Rollback Gates Verification Report

**Phase Goal:** A deterministic A/B replay harness captures pre-migration controller behavior against the 2026-04-22 out-of-band flent finding, and rollback criteria are encoded as a machine-readable predeploy gate script that fails closed.
**Verified:** 2026-05-15T15:15:10Z
**Status:** gaps_found
**Re-verification:** Yes — previous report said verified; this pass re-checked the actual code after review findings and found additional fail-closed gaps.

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | The A/B replay harness reuses Phase 193/194/195 patterns, ingests a committed deterministic fixture, and emits pre/post metrics. | ✓ VERIFIED | `scripts/phase206-ab-replay.py` imports `_fresh_controller`, `_replay`, `_replay_samples`, and `_snap_for`; focused tests passed (`44 passed`); harness spot-check emitted schema v1 with 350 pre/post samples. |
| 2 | The summary JSON schema is stable for a one-line consumer change. | ✓ VERIFIED | Harness output has stable top-level keys `{schema_version, phase, fixture_provenance, fixture_sha256, meta, pre, post, delta, gates}` and `meta.metric_source='controller_replay'` in default mode. |
| 3 | Operator-readable rollback trigger documentation exists and references JSON-sourced thresholds. | ✓ VERIFIED | `PHASE-205-ROLLBACK-GATES.md` documents all three triggers and cites `scripts/phase206-thresholds.json`; threshold/provenance check passed against JSON values 5.0/10.0/10.0. |
| 4 | The predeploy gate blocks threshold breaches, passes baseline dry-run, and fails closed on malformed/inconsistent input. | ✗ FAILED | Baseline dry-run and original gap checks pass, but new fail-closed spot-checks found: partial restart counter input returns rc=0, zero-duration post-soak returns rc=0, and hidden `PHASE206_LOCAL_BASELINE_OVERRIDE` can mask a restart breach and return rc=0. |
| 5 | SAFE-09 boundary: Phase 206 introduces no new control-path source diff. | ✓ VERIFIED | `git diff 6508d68 --name-only -- src/wanctl/` remains exactly the Phase 205 five-file allowlist; unstaged/untracked `src/wanctl/` counts are both 0. |

**Score:** 4/5 roadmap success criteria verified.

### Required Artifacts

| Artifact | Expected | Status | Details |
|---|---|---|---|
| `tests/fixtures/phase206_golden_capture.ndjson` | Deterministic golden fixture | ✓ VERIFIED | Present; 350 rows; SHA `68f99440bd41be646dfa64abe77380791d4b2dd7b09722588c808e9749c0bbda` pinned in provenance. |
| `tests/fixtures/_phase_206_generator.py` | Regenerator | ✓ VERIFIED | Present and substantive; provenance documents deterministic regeneration from 2026-04-29 substitute artifact. |
| `tests/fixtures/phase206_replay_corpus.py` | Frozen loader | ✓ VERIFIED | `GoldenSample` + `load_golden()` used by harness/tests. |
| `scripts/phase206-ab-replay.py` | A/B harness CLI | ✓ VERIFIED | Schema-v1 output, optional flent parsing, Phase 193/206 helper imports, 350-sample traces. |
| `scripts/phase206-gate-check.py` | Gate Python core | ✗ PARTIAL | Enforces many checks, but has three fail-closed gaps: exactly-one restart counter skips, zero-duration soak passes, env override can alter inputs. |
| `scripts/phase206-predeploy-gate.sh` | Operator wrapper | ✗ PARTIAL | Validates paths/options and delegates to Python, but does not reject partial restart-counter input and does not clear/reject `PHASE206_LOCAL_BASELINE_OVERRIDE`. |
| `scripts/phase206-thresholds.json` | Threshold source of truth | ✓ VERIFIED | Contains `RRUL_P99_REGRESSION_PCT=5.0`, `RESTART_RATE_INCREASE_PCT=10.0`, `TRANSITION_RATE_INCREASE_PCT=10.0`. |
| `.planning/phases/206-a-b-replay-harness-rollback-gates/PHASE-205-ROLLBACK-GATES.md` | Operator rollback doc | ✓ VERIFIED | Documents triggers, modes, formulas, threshold source, and SAFE-09 exclusions. |

### Key Link Verification

| From | To | Via | Status | Details |
|---|---|---|---|---|
| `scripts/phase206-ab-replay.py` | `tests.test_phase_193_replay` | import `_fresh_controller`, `_replay` | ✓ WIRED | Harness imports Phase 193 primitives and does not redefine the controller factory. |
| `scripts/phase206-ab-replay.py` | `tests.test_phase_206_replay` | import `_replay_samples`, `_snap_for` | ✓ WIRED | Harness uses per-sample replay helper that consumes all fixture rows. |
| `scripts/phase206-predeploy-gate.sh` | `scripts/phase206-gate-check.py` | `exec "$VENV_PY" ...` | ✓ WIRED | Wrapper delegates to Python core and bubbles exit codes. |
| `scripts/phase206-gate-check.py` | `scripts/phase206-thresholds.json` | `load_thresholds()` | ✓ WIRED | Thresholds loaded at module import. |
| `scripts/phase206-gate-check.py` | restart-counter input | CLI args | ✗ PARTIAL | Both-counter case is wired; exactly-one-counter malformed input is not rejected and is skipped. |
| `scripts/phase206-gate-check.py` | soak NDJSON | `check_zone_transitions()` | ✗ PARTIAL | Empty/malformed/single-sample guards exist; zero-duration windows still pass. |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|---|---|---|---|---|
| `scripts/phase206-ab-replay.py` | `samples` | `load_golden(fixture_path)` | Yes | ✓ FLOWING — spot-check output had 350 rate/zone samples per side. |
| `scripts/phase206-ab-replay.py` | flent metrics | `_parse_flent_rrul()` from `.flent.gz` | Yes when supplied | ✓ FLOWING — focused CLI test covers synthetic flent gz path. |
| `scripts/phase206-gate-check.py` | restart rate | explicit counters/window | Partial | ✗ HOLLOW EDGE — one missing counter causes the gate to skip restart-rate enforcement. |
| `scripts/phase206-gate-check.py` | transition rate | `last_zone` + `t_monotonic` from NDJSON | Partial | ✗ HOLLOW EDGE — no positive elapsed-duration validation. |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|---|---|---|---|
| Focused Phase 206 tests | `.venv/bin/pytest tests/test_phase_206_replay.py tests/test_phase206_ab_replay_cli.py tests/test_phase206_predeploy_gate.py -q` | `44 passed in 2.20s` | ✓ PASS |
| Harness emits schema v1 with full replay traces | `.venv/bin/python scripts/phase206-ab-replay.py --out /tmp/opencode/p206-verify-ab.json` | schema v1; `metric_source=controller_replay`; 350 post samples | ✓ PASS |
| Baseline dry-run passes | `bash scripts/phase206-predeploy-gate.sh --baseline tests/fixtures/phase206_baseline_v143.json --candidate tests/fixtures/phase206_baseline_v143.json` | rc=0 | ✓ PASS |
| Empty post-soak NDJSON fails closed | `--mode post-soak --soak-ndjson <empty> ...` | rc=2; stderr `insufficient valid soak samples` | ✓ PASS |
| Decreasing restart counters fail closed | `--restart-counter-start 5 --restart-counter-end 1 --window-hours 1` | rc=2; stderr `restart_counter_end (1) < restart_counter_start (5)` | ✓ PASS |
| Missing shell option value aborts | `bash scripts/phase206-predeploy-gate.sh --baseline` | rc=2; stderr `missing value for --baseline` | ✓ PASS |
| Default harness candidate vs committed baseline fails closed | candidate from `phase206-ab-replay.py` vs baseline | rc=2; stderr `metric_source mismatch (post-block keys)` | ✓ PASS |
| Partial restart-counter input fails closed | `--restart-counter-start 0 --window-hours 1` without `--restart-counter-end` | rc=0; stderr says `restart-rate check skipped` and `PASS` | ✗ FAIL |
| Zero-duration post-soak fails closed | two valid soak rows with same `t_monotonic` in `--mode post-soak` | rc=0; stderr says transition-rate `0.00/h` and `PASS` | ✗ FAIL |
| Hidden override cannot mask restart breach | `PHASE206_LOCAL_BASELINE_OVERRIDE=<0/0 counters>` with CLI `--restart-counter-end 1` | rc=0; restart breach overwritten to `0.00/h` PASS | ✗ FAIL |
| Full regression suite | Orchestrator evidence | `5039 passed, 6 skipped, 2 deselected in 202.92s`; schema drift gate `drift_detected=false` | ✓ PASS (test suite not sufficient for fail-closed gaps above) |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|---|---|---|---|---|
| TOPO-04 | 206-01, 206-04, 206-07 | A/B replay harness captures pre/post RRUL p99 latency, throughput, jitter against the out-of-band flent finding; deterministic golden fixture committed. | ✓ SATISFIED | Harness, fixture, loader, generator, flent parser, schema tests, and focused tests are present and passing. Date substitution is documented in provenance. |
| TOPO-05 | 206-02, 206-03, 206-04, 206-05, 206-06, 206-07, 206-08 | Rollback criteria documented in machine-readable/operator-readable form; predeploy gate enforces RRUL p99, restart-rate, transition-rate and fails closed. | ✗ BLOCKED | Docs/thresholds/tests exist, but actual gate does not fail closed for partial restart-counter input, zero-duration soak windows, or hidden local override state. |

No orphaned Phase 206 requirement IDs found in `.planning/REQUIREMENTS.md`: TOPO-04 and TOPO-05 are both mapped to Phase 206 and appear in PLAN frontmatter.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|---|---:|---|---|---|
| `scripts/phase206-gate-check.py` | 231-244 | Unconditional `PHASE206_LOCAL_BASELINE_OVERRIDE` | 🛑 Blocker | Hidden environment state can overwrite validated CLI inputs in production. |
| `scripts/phase206-gate-check.py` | 293-319 | Exactly-one restart counter falls into skip branch | 🛑 Blocker | Malformed restart input returns PASS instead of ABORT. |
| `scripts/phase206-gate-check.py` | 191-197 | `elapsed_s <= 0` coerced to `1e-9` hours | 🛑 Blocker | Zero-duration soak evidence can pass post-soak mode. |
| `tests/test_phase206_predeploy_gate.py` | 283-305 | Happy-path post-soak test accepts `returncode in (0, 1)` | ⚠️ Warning | Test can pass on a BLOCK and does not prove a valid full-input post-soak pass path. |
| `scripts/phase206-predeploy-gate.sh` | 178-184 | Python interpreter check accepts non-executable files until `exec` rc=126 | ⚠️ Warning | Malformed interpreter path may violate documented rc=2 ABORT contract. |

### Human Verification Required

None. Phase 206 is an offline harness/gate/docs phase; the relevant behaviors are checkable with scripts/tests.

### Gaps Summary

Phase 206 achieves the deterministic A/B harness and documentation portions of the goal, but the predeploy gate is not yet fail-closed for all malformed/inconsistent input. The remaining blocking gaps are in TOPO-05: reject partial restart-counter input, reject zero-duration soak windows, and eliminate or explicitly gate the production-visible local override path. These are not clearly deferred to later phases; Phase 209 depends on this gate rather than owning these fixes.

---

_Verified: 2026-05-15T15:15:10Z_
_Verifier: the agent (gsd-verifier)_
