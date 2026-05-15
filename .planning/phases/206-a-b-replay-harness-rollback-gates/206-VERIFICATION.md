---
phase: 206-a-b-replay-harness-rollback-gates
verified: 2026-05-15T02:48:44Z
re_verified: 2026-05-15T15:00:30Z
re_verification_plan: 206-08
status: verified
score: "5/5 roadmap success criteria verified after gap closure 2026-05-15"
overrides_applied: 0
requirements: [TOPO-04, TOPO-05]
gaps: []
human_verification: []
---

# Phase 206: A/B Replay Harness + Rollback Gates — Verification Report

**Phase Goal:** A deterministic A/B replay harness captures pre-migration controller behavior against the 2026-04-22 out-of-band flent finding, and rollback criteria are encoded as a machine-readable predeploy gate script that fails closed.
**Verified:** 2026-05-15T02:48:44Z
**Status:** verified (re-verified 2026-05-15 after Plans 05-07)
**Re-verification:** Yes — gap-closure re-verification after Plans 05/06/07 landed the fixes; original gap-discovery audit stamp preserved above.

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | The A/B replay harness reuses Phase 193/194/195 patterns, ingests a committed deterministic fixture, and emits pre/post metrics. | ✓ VERIFIED | `scripts/phase206-ab-replay.py` imports `_fresh_controller`/`_replay` from `tests.test_phase_193_replay` and `_replay_samples` from `tests.test_phase_206_replay`; spot-check emitted schema v1 with 350 pre/post samples. |
| 2 | The summary JSON schema is stable for a one-line consumer change. | ✓ VERIFIED | Harness output top-level keys are `{schema_version, phase, fixture_provenance, fixture_sha256, meta, pre, post, delta, gates}` and focused tests pass. |
| 3 | Operator-readable rollback trigger documentation exists and references JSON-sourced thresholds. | ✓ VERIFIED | `PHASE-205-ROLLBACK-GATES.md` exists; threshold drift gate already passed and `scripts/phase206-thresholds.json` contains 5.0/10.0/10.0. |
| 4 | The predeploy gate blocks threshold breaches, passes baseline dry-run, and fails closed on malformed/inconsistent input. | ✓ VERIFIED | Gap-closure re-verification 2026-05-15 (Plan 08): empty post-soak rc=2 (G1), decreasing restart counters rc=2 (G2), missing shell option rc=2 (G3), default-harness-vs-committed-baseline rc=2 via secondary post-block-key guard (G4). See "Gap Closure Re-Verification" section below. |
| 5 | SAFE-09 boundary: Phase 206 introduces no new control-path source diff. | ✓ VERIFIED | `git diff 6508d68 --name-only -- src/wanctl/` returns exactly the Phase 205 five-file allowlist; unstaged and untracked `src/wanctl/` surfaces are both 0. |

**Score:** 5/5 roadmap success criteria verified (gap closure complete 2026-05-15).

### Required Artifacts

| Artifact | Expected | Status | Details |
|---|---|---|---|
| `tests/fixtures/phase206_golden_capture.ndjson` | Deterministic golden fixture | ✓ VERIFIED | Present; 350 rows; SHA pinned as `68f99440bd41be646dfa64abe77380791d4b2dd7b09722588c808e9749c0bbda`. |
| `tests/fixtures/_phase_206_generator.py` | Regenerator | ✓ VERIFIED | Present and substantive; reads flent gz via gzip/json and writes deterministic NDJSON. |
| `tests/fixtures/phase206_replay_corpus.py` | Frozen loader | ✓ VERIFIED | Frozen `GoldenSample` and `load_golden()` implemented. |
| `scripts/phase206-ab-replay.py` | A/B harness CLI | ✓ VERIFIED | Emits schema v1; imports Phase 193 primitives and `_replay_samples`; optional flent parser present. |
| `scripts/phase206-gate-check.py` | Gate Python core | ✓ VERIFIED | Threshold checks implemented. Gap closure (2026-05-15): malformed soak + decreasing restart counter + mixed metric source (two-tier guard: meta-source + post-block keys) all rc=2 (Plans 05, 07). |
| `scripts/phase206-predeploy-gate.sh` | Operator wrapper | ✓ VERIFIED | Path and SSH validation exist. Gap closure (2026-05-15): missing option values now rc=2 via require_value (Plan 06). |
| `scripts/phase206-thresholds.json` | Threshold source of truth | ✓ VERIFIED | Contains `RRUL_P99_REGRESSION_PCT=5.0`, `RESTART_RATE_INCREASE_PCT=10.0`, `TRANSITION_RATE_INCREASE_PCT=10.0`. |
| `.planning/phases/206-a-b-replay-harness-rollback-gates/PHASE-205-ROLLBACK-GATES.md` | Operator rollback doc | ✓ VERIFIED | Documents three triggers, modes, formulas, threshold source, and SAFE-09 exclusions. |

### Key Link Verification

| From | To | Via | Status | Details |
|---|---|---|---|---|
| `scripts/phase206-ab-replay.py` | `tests.test_phase_193_replay` | import `_fresh_controller`, `_replay` | ✓ WIRED | Lines 24 and 35-43 reuse the Phase 193 factory path; no local `_fresh_controller` redefinition. |
| `scripts/phase206-ab-replay.py` | `tests.test_phase_206_replay` | import `_replay_samples`, `_snap_for` | ✓ WIRED | `_build_side()` calls `_replay_samples()` and output includes full `rate_trace_mbps`/`zone_sequence`. |
| `scripts/phase206-predeploy-gate.sh` | `scripts/phase206-gate-check.py` | `exec "$VENV_PY" ...` | ✓ WIRED | Wrapper delegates to Python core and bubbles exit codes. |
| `scripts/phase206-gate-check.py` | `scripts/phase206-thresholds.json` | `load_thresholds()` | ✓ WIRED | Thresholds load at module import. |
| `scripts/phase206-gate-check.py` | soak NDJSON | `check_zone_transitions()` | ✓ WIRED | Link exists; gap closure (2026-05-15) added InsufficientSoakSamples / MalformedSoakInput guards (Plan 05). |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|---|---|---|---|---|
| `scripts/phase206-ab-replay.py` | `samples` | `load_golden(fixture_path)` | Yes | ✓ FLOWING — spot-check output had 350 rate/zone samples per side. |
| `scripts/phase206-ab-replay.py` | flent metrics | `_parse_flent_rrul()` from `.flent.gz` | Yes when supplied | ✓ FLOWING — parser uses gzip/json, ping quantiles, and TCP series tail sum; focused test covers synthetic flent gz. |
| `scripts/phase206-gate-check.py` | restart rate | explicit counters/window | Partial | ⚠️ HOLLOW EDGE — computes rate but lacks monotonic validation. |
| `scripts/phase206-gate-check.py` | transition rate | `last_zone` + `t_monotonic` from NDJSON | Partial | ⚠️ HOLLOW EDGE — valid fixture flows, but malformed/empty captures produce a false 0.00/h pass. |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|---|---|---|---|
| Harness emits schema v1 with full replay traces | `.venv/bin/python scripts/phase206-ab-replay.py --out /tmp/opencode/p206-ab.json` | `schema_version=1`, `metric_source=controller_replay`, `350` pre/post samples | ✓ PASS |
| Baseline dry-run passes | `bash scripts/phase206-predeploy-gate.sh --baseline tests/fixtures/phase206_baseline_v143.json --candidate tests/fixtures/phase206_baseline_v143.json` | rc=0 | ✓ PASS |
| Empty post-soak NDJSON fails closed | `... --mode post-soak --soak-ndjson /tmp/opencode/p206-empty-soak.ndjson ...` | rc=2; stderr "insufficient valid soak samples" | ✓ PASS |
| Decreasing restart counters fail closed | `... --restart-counter-start 5 --restart-counter-end 1 --window-hours 1 ...` | rc=2; stderr "restart_counter_end (1) < restart_counter_start (5)" | ✓ PASS |
| Missing shell option value aborts | `bash scripts/phase206-predeploy-gate.sh --baseline` | rc=2; stderr "missing value for --baseline" | ✓ PASS |
| Default harness candidate integrates with gate baseline | generate default candidate then run gate | rc=2; stderr "metric_source mismatch (post-block keys): baseline='rrul_p99_latency_ms' candidate='controller_rate_p99_mbps'" | ✓ PASS |
| Focused Phase 206 tests | `.venv/bin/pytest tests/test_phase_206_replay.py tests/test_phase206_ab_replay_cli.py tests/test_phase206_predeploy_gate.py -q` | `32 passed in 1.50s` | ✓ PASS |
| Full regression gate | Orchestrator-provided `.venv/bin/pytest tests/ -q` | `5027 passed, 6 skipped, 2 deselected` | ✓ PASS (reviewed) |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|---|---|---|---|---|
| TOPO-04 | 206-01, 206-04 | A/B replay harness captures pre/post RRUL p99 latency, throughput, jitter against the out-of-band flent finding; deterministic golden fixture committed. | ✓ SATISFIED | Harness, fixture, loader, generator, flent parser, schema tests, and focused tests are present and passing. Date substitution is documented in provenance. |
| TOPO-05 | 206-02, 206-03, 206-04 | Rollback criteria documented in machine-readable/operator-readable form; predeploy gate enforces RRUL p99, restart-rate, transition-rate and fails closed. | ✓ SATISFIED | Three triggers and docs exist. Gap closure (2026-05-15, Plans 05/06/07) closes all four warning findings WR-01..WR-04. See spot-check table above and re-verification section below. |

No orphaned Phase 206 requirement IDs found in `.planning/REQUIREMENTS.md`: TOPO-04 and TOPO-05 are both mapped to Phase 206 and appear in PLAN frontmatter.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|---|---:|---|---|---|
| `scripts/phase206-gate-check.py` | 121-131 | Silent skip of malformed/missing soak rows | 🛑 Blocker | Empty/malformed post-soak input can pass full-enforcement mode. |
| `scripts/phase206-gate-check.py` | 245 | No validation for decreasing restart counters | 🛑 Blocker | Swapped/reset counters produce a negative healthy rate and pass. |
| `scripts/phase206-predeploy-gate.sh` | 64-85 | `${2:-}; shift 2` without value validation | 🛑 Blocker | Missing operator input exits as rc=1 BLOCK, not rc=2 ABORT. |
| `scripts/phase206-gate-check.py` | 69-84 | Mixed `rrul_p99_latency_ms`/`controller_rate_p99_mbps` comparison | ⚠️ Warning | Default harness candidate vs committed baseline blocks with mixed units; fail-closed but misleading/unusable. |

### Human Verification Required

None. Phase 206 is an offline harness/gate/docs phase; the relevant behaviors were checkable with scripts/tests.

### Gaps Summary

All four gaps closed by Plans 05, 06, 07 (gap-closure wave, 2026-05-15). The rollback gate now fails closed on malformed soak NDJSON, decreasing restart counters, missing shell option values, and mixed metric sources (two-tier guard: primary meta.metric_source check + secondary _read_p99 post-block-key check). See "Gap Closure Re-Verification" section below for verbatim evidence.

## Gap Closure Re-Verification (2026-05-15, Plan 08)

### Gap-Closure Spot-Checks

| Gap | Command | Result | Status |
|-----|---------|--------|--------|
| G1 | `bash scripts/phase206-predeploy-gate.sh --mode post-soak ... --soak-ndjson <empty>` | rc=2; stderr "insufficient valid soak samples" | ✓ CLOSED (Plan 05) |
| G2 | `bash scripts/phase206-predeploy-gate.sh ... --restart-counter-start 5 --restart-counter-end 1 --window-hours 1` | rc=2; stderr "restart_counter_end (1) < restart_counter_start (5)" | ✓ CLOSED (Plan 05) |
| G3 | `bash scripts/phase206-predeploy-gate.sh --baseline` | rc=2; stderr "missing value for --baseline" | ✓ CLOSED (Plan 06) |
| G4 | `phase206-ab-replay.py` default output vs committed baseline | rc=2; stderr `metric_source mismatch (post-block keys): baseline='rrul_p99_latency_ms' candidate='controller_rate_p99_mbps'` (secondary guard; both meta sources are `controller_replay` so the primary guard does not fire) | ✓ CLOSED (Plan 07) |

### Spot-Check Verbatim Output

```text
$ bash scripts/phase206-predeploy-gate.sh --mode post-soak --baseline tests/fixtures/phase206_baseline_v143.json --candidate tests/fixtures/phase206_baseline_v143.json --soak-ndjson /tmp/p206-revisit/empty-soak.ndjson --restart-counter-start 0 --restart-counter-end 0 --window-hours 1
[phase206-predeploy-gate INFO]  invoking gate-check helper (mode=post-soak)
[phase206-gate-check INFO] RRUL comparison source=rrul_p99_latency_ms
[phase206-gate-check ABORT] ERROR: failed transition-rate check: insufficient valid soak samples: soak NDJSON is empty (/tmp/p206-revisit/empty-soak.ndjson)
rc=2

$ bash scripts/phase206-predeploy-gate.sh --baseline tests/fixtures/phase206_baseline_v143.json --candidate tests/fixtures/phase206_baseline_v143.json --restart-counter-start 5 --restart-counter-end 1 --window-hours 1
[phase206-predeploy-gate INFO]  invoking gate-check helper (mode=predeploy)
[phase206-gate-check INFO] RRUL comparison source=rrul_p99_latency_ms
[phase206-gate-check ABORT] ERROR: restart_counter_end (1) < restart_counter_start (5); counter must be monotonic non-decreasing (systemd NRestarts only grows)
rc=2

$ bash scripts/phase206-predeploy-gate.sh --baseline
[phase206-predeploy-gate ABORT] missing value for --baseline
rc=2

$ .venv/bin/python scripts/phase206-ab-replay.py --out /tmp/p206-revisit/ab-default.json
rc=0
$ bash scripts/phase206-predeploy-gate.sh --baseline tests/fixtures/phase206_baseline_v143.json --candidate /tmp/p206-revisit/ab-default.json
[phase206-predeploy-gate INFO]  invoking gate-check helper (mode=predeploy)
[phase206-gate-check ABORT] ERROR: failed RRUL p99 check: metric_source mismatch (post-block keys): baseline='rrul_p99_latency_ms' candidate='controller_rate_p99_mbps'; refuse to compare across sources (TOPO-05 fail-closed)
rc=2
```

### SAFE-09 Four-Surface Re-Check

```text
$ git diff 6508d68 --name-only -- src/wanctl/ | sort -u
src/wanctl/backends/linux_cake.py
src/wanctl/backends/netlink_cake.py
src/wanctl/cake_params.py
src/wanctl/cake_signal.py
src/wanctl/check_config_validators.py

$ git diff 6508d68 --name-only -- src/wanctl/ | sort -u | wc -l
5

$ git diff --cached 6508d68 --name-only -- src/wanctl/ | sort -u | wc -l
5

$ git diff --name-only -- src/wanctl/ | wc -l
0

$ git ls-files --others --exclude-standard -- src/wanctl/ | wc -l
0

$ git status --short -- src/wanctl/
```

SAFE-09 invariant holds across all four surfaces after gap closure.

### Test Evidence

```text
$ .venv/bin/pytest tests/ -q
5039 passed, 6 skipped, 2 deselected in 199.79s (0:03:19)

$ .venv/bin/pytest -o addopts='' tests/test_cake_signal.py tests/test_queue_controller.py tests/test_wan_controller.py tests/test_health_check.py -q
673 passed in 41.12s

$ .venv/bin/pytest tests/test_phase_206_replay.py tests/test_phase206_ab_replay_cli.py tests/test_phase206_predeploy_gate.py -q
44 passed in 3.27s

$ .venv/bin/pytest tests/test_phase206_predeploy_gate.py::TestPostSoakAbortMalformed tests/test_phase206_predeploy_gate.py::TestRestartCounterMonotonic tests/test_phase206_predeploy_gate.py::TestShellMissingOptionValue tests/test_phase206_predeploy_gate.py::TestMixedMetricSource -q
12 passed in 0.89s
```

### Plan References

- Plan 05 (Wave 1): G1 + G2 — Python core validation (`scripts/phase206-gate-check.py`)
- Plan 06 (Wave 2): G3 — shell `require_value()` helper (`scripts/phase206-predeploy-gate.sh`)
- Plan 07 (Wave 3): G4 — two-tier `metric_source` mismatch ABORT (primary: `meta.metric_source` equality; secondary: `_read_p99` post-block-key equality) + end-to-end integration test
- Plan 08 (Wave 4, this plan): re-verification + status flip

---

_Verified: 2026-05-15T02:48:44Z_
_Re-verified: 2026-05-15T15:00:30Z_
_Re-verifier: Plan 08 closeout task (gap-closure 2026-05-15)_
_Verifier: the agent (gsd-verifier)_
