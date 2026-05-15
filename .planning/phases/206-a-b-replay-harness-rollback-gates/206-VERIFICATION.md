---
phase: 206-a-b-replay-harness-rollback-gates
verified: 2026-05-15T16:22:02Z
status: gaps_found
score: "4/5 roadmap success criteria verified"
overrides_applied: 0
requirements: [TOPO-04, TOPO-05]
re_verification:
  previous_status: gaps_found
  previous_score: "4/5 roadmap success criteria verified"
  gaps_closed:
    - "Partial restart-counter input now aborts rc=2 in wrapper and Python core paths."
    - "Zero-duration post-soak NDJSON now aborts rc=2 with `no positive t_monotonic duration`."
    - "PHASE206_LOCAL_BASELINE_OVERRIDE no longer mutates production gate inputs: wrapper clears it; Python core rejects it without explicit test-only opt-in."
    - "Post-soak happy-path test now asserts rc == 0, and non-executable VENV_PY aborts rc=2."
  gaps_remaining:
    - "Non-finite --window-hours values (`nan`, `inf`) still return rc=0 instead of fail-closed rc=2."
  regressions: []
gaps:
  - truth: "The predeploy gate fails closed on malformed restart-window input."
    status: failed
    reason: "`--window-hours nan` and `--window-hours inf` are accepted by argparse, bypass the `<= 0` validation, and produce a PASS even with restart-counter input present."
    artifacts:
      - path: "scripts/phase206-gate-check.py"
        issue: "Line 339 checks only `args.window_hours is None or args.window_hours <= 0`; no finite-number validation before restart-rate math."
      - path: "tests/test_phase206_predeploy_gate.py"
        issue: "No regression coverage for `--window-hours nan` or `--window-hours inf`."
    missing:
      - "Reject non-finite restart window values with rc=2 before computing current restart rate."
      - "Add tests for `--window-hours nan` and `--window-hours inf` fail-closed behavior."
---

# Phase 206: A/B Replay Harness + Rollback Gates Verification Report

**Phase Goal:** A deterministic A/B replay harness captures pre-migration controller behavior against the 2026-04-22 out-of-band flent finding, and rollback criteria are encoded as a machine-readable predeploy gate script that fails closed.
**Verified:** 2026-05-15T16:22:02Z
**Status:** gaps_found
**Re-verification:** Yes — after Plan 206-09 gap closure.

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|---|---|---|
| 1 | The A/B replay harness reuses the Phase 193/194/195 replay pattern, ingests a committed deterministic golden fixture, and emits RRUL p99 latency, throughput, and jitter for pre/post configurations. | ✓ VERIFIED | `scripts/phase206-ab-replay.py` imports `_fresh_controller`, `_replay`, `_replay_samples`, and `load_golden`; focused Phase 206 tests passed (`51 passed`). Harness spot-check emitted schema v1 with 350 pre/post samples. |
| 2 | The harness produces an A/B summary JSON whose schema is stable enough for a follow-up post-canary diff. | ✓ VERIFIED | Spot-check output top-level keys: `schema_version`, `phase`, `fixture_provenance`, `fixture_sha256`, `meta`, `pre`, `post`, `delta`, `gates`; `meta.metric_source=controller_replay`. |
| 3 | `PHASE-205-ROLLBACK-GATES.md` documents the three rollback triggers in operator-readable form. | ✓ VERIFIED | Document lists RRUL p99 regression, daemon restart-rate, and pressure-state transition-rate; it references `scripts/phase206-thresholds.json` values 5.0/10.0/10.0 as source of truth. |
| 4 | A predeploy gate script exits non-zero when rollback triggers or malformed gate inputs are breached, and an operator dry-run on the v1.43 baseline exits zero. | ✗ FAILED | Plan 206-09 closed prior fail-closed gaps (partial counters, zero-duration soak, hidden override), and baseline dry-run rc=0. However, `--window-hours nan` and `--window-hours inf` with restart counters return rc=0 PASS instead of rc=2 ABORT. |
| 5 | SAFE-09 phase-boundary check: zero control-path source diff introduced in this phase. | ✓ VERIFIED | `git diff 6508d68 --name-only -- src/wanctl/` remains the Phase 205 allowlist only: `linux_cake.py`, `netlink_cake.py`, `cake_params.py`, `cake_signal.py`, `check_config_validators.py`; cached/unstaged `src/wanctl/` surfaces produced no additional output. |

**Score:** 4/5 roadmap success criteria verified.

### Required Artifacts

| Artifact | Expected | Status | Details |
|---|---|---|---|
| `tests/fixtures/phase206_golden_capture.ndjson` | Deterministic golden fixture | ✓ VERIFIED | Provenance pins 350 rows and SHA256 `68f99440bd41be646dfa64abe77380791d4b2dd7b09722588c808e9749c0bbda`. |
| `tests/fixtures/phase206_replay_corpus.py` | Frozen fixture loader | ✓ VERIFIED | Defines `GoldenSample` and `load_golden()` used by tests and harness. |
| `scripts/phase206-ab-replay.py` | A/B replay CLI | ✓ VERIFIED | Substantive CLI, imports prior replay helpers, supports flent parsing, emits schema v1 JSON. |
| `scripts/phase206-gate-check.py` | Gate Python core | ✗ PARTIAL | Prior Plan 09 gaps closed, but restart-window validation lacks finite-number enforcement. |
| `scripts/phase206-predeploy-gate.sh` | Operator wrapper | ✓ VERIFIED | Validates args, partial counters, executable Python, clears local override, delegates to Python core. Non-finite window value reaches Python as designed but Python currently accepts it. |
| `scripts/phase206-thresholds.json` | Machine-readable thresholds | ✓ VERIFIED | Contains `RRUL_P99_REGRESSION_PCT=5.0`, `RESTART_RATE_INCREASE_PCT=10.0`, `TRANSITION_RATE_INCREASE_PCT=10.0`. |
| `.planning/phases/206-a-b-replay-harness-rollback-gates/PHASE-205-ROLLBACK-GATES.md` | Operator rollback doc | ✓ VERIFIED | Documents trigger formulas, modes, thresholds, and SAFE-09 exclusions. |

### Key Link Verification

| From | To | Via | Status | Details |
|---|---|---|---|---|
| `scripts/phase206-ab-replay.py` | Phase 193/206 replay helpers | direct imports | ✓ WIRED | Imports and uses `_fresh_controller`, `_replay`, `_replay_samples`, `_snap_for`. |
| `scripts/phase206-ab-replay.py` | committed fixture | `load_golden(fixture_path)` | ✓ WIRED | Spot-check consumed 350 samples into both pre/post traces. |
| `scripts/phase206-predeploy-gate.sh` | `scripts/phase206-gate-check.py` | `exec "$VENV_PY" ...` | ✓ WIRED | Wrapper delegates and preserves exit codes. |
| `scripts/phase206-gate-check.py` | `scripts/phase206-thresholds.json` | `load_thresholds()` at import | ✓ WIRED | Threshold constants loaded from JSON. |
| `scripts/phase206-gate-check.py` | restart-counter inputs | CLI args and rate math | ✗ PARTIAL | Counters and positive finite-looking values are wired; non-finite `window_hours` is not rejected. |
| `scripts/phase206-gate-check.py` | soak NDJSON | `check_zone_transitions()` | ✓ WIRED | Empty/malformed/single-sample/zero-duration inputs abort; valid timed soak path remains tested. |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|---|---|---|---|---|
| `scripts/phase206-ab-replay.py` | `samples` | `load_golden(fixture_path)` | Yes | ✓ FLOWING — harness output contained 350 pre and 350 post rate samples. |
| `scripts/phase206-ab-replay.py` | flent metrics | `_parse_flent_rrul()` from `.flent.gz` | Yes when supplied | ✓ FLOWING — CLI test covers synthetic flent `.gz` input. |
| `scripts/phase206-gate-check.py` | restart rate | counters + `window_hours` | Partial | ✗ HOLLOW EDGE — `nan`/`inf` window values pass validation and produce a PASS. |
| `scripts/phase206-gate-check.py` | transition rate | `last_zone` + `t_monotonic` | Yes | ✓ FLOWING — zero-duration and malformed inputs abort; synthetic timed soak tests exercise rate computation. |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|---|---|---|---|
| Focused Phase 206 tests | `.venv/bin/pytest tests/test_phase_206_replay.py tests/test_phase206_ab_replay_cli.py tests/test_phase206_predeploy_gate.py -q` | `51 passed in 2.81s` | ✓ PASS |
| Harness schema/traces | `.venv/bin/python scripts/phase206-ab-replay.py --out /tmp/opencode/p206-verify-ab.json` | schema `1`, source `controller_replay`, 350/350 traces | ✓ PASS |
| Baseline dry-run | `bash scripts/phase206-predeploy-gate.sh --baseline tests/fixtures/phase206_baseline_v143.json --candidate tests/fixtures/phase206_baseline_v143.json` | rc=0 PASS | ✓ PASS |
| Partial restart counter | wrapper with only `--restart-counter-start 0 --window-hours 1` | rc=2, `restart counters must be supplied together` | ✓ PASS |
| Zero-duration post-soak | two rows with identical `t_monotonic` | rc=2, `no positive t_monotonic duration` | ✓ PASS |
| Hidden override direct core | `PHASE206_LOCAL_BASELINE_OVERRIDE=... scripts/phase206-gate-check.py ... --restart-counter-end 1` | rc=2, `local baseline override is not allowed` | ✓ PASS |
| Hidden override wrapper | `PHASE206_LOCAL_BASELINE_OVERRIDE=... bash scripts/phase206-predeploy-gate.sh ...` | rc=0, wrapper logs clearing env var | ✓ PASS |
| NaN restart window | wrapper with `--restart-counter-start 0 --restart-counter-end 1 --window-hours nan` | rc=0 PASS | ✗ FAIL |
| Infinite restart window | wrapper with `--restart-counter-start 0 --restart-counter-end 1 --window-hours inf` | rc=0 PASS | ✗ FAIL |
| Full regression suite | Orchestrator evidence after Plan 09 | `5046 passed, 6 skipped, 2 deselected`; schema drift `drift_detected=false` | ✓ PASS (does not cover non-finite window gap) |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|---|---|---|---|---|
| TOPO-04 | 206-01, 206-04, 206-07, 206-08 | A/B replay harness captures pre/post RRUL p99 latency, throughput, jitter against the out-of-band flent finding; deterministic golden fixture committed. | ✓ SATISFIED | Harness, fixture, loader, provenance, flent parser, schema tests, and focused tests are present and passing. The 2026-04-29 substitute artifact is documented in provenance. |
| TOPO-05 | 206-02, 206-03, 206-04, 206-05, 206-06, 206-07, 206-08, 206-09 | Rollback criteria documented in machine-readable/operator-readable form; predeploy gate enforces RRUL p99, restart-rate, transition-rate and fails closed. | ✗ BLOCKED | Thresholds/docs/gate/tests exist and Plan 09 closed prior WR-01..WR-04/IN-01 gaps, but malformed non-finite `--window-hours` values still fail open with rc=0. |

No orphaned Phase 206 requirement IDs found in `.planning/REQUIREMENTS.md`: TOPO-04 and TOPO-05 are both mapped to Phase 206 and appear in PLAN frontmatter.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|---|---:|---|---|---|
| `scripts/phase206-gate-check.py` | 339-351 | Float input validation checks only `None`/`<= 0`; no `math.isfinite()` guard | 🛑 Blocker | `nan`/`inf` operator input bypasses restart-rate enforcement and returns PASS. |

### Human Verification Required

None. Phase 206 is an offline harness/gate/docs phase; the relevant behaviors are checkable with scripts/tests.

### Gaps Summary

Plan 206-09 successfully closed the previously reported fail-closed gaps for partial restart counters, zero-duration soak windows, hidden local baseline override state, post-soak happy-path assertions, and non-executable interpreter handling. One remaining blocker prevents the phase goal from passing: restart-window values must be finite. Until `--window-hours nan` and `--window-hours inf` abort rc=2, TOPO-05 remains blocked and roadmap success criterion #4 is only partially met.

---

_Verified: 2026-05-15T16:22:02Z_
_Verifier: the agent (gsd-verifier)_
