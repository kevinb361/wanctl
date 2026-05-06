---
phase: 203-target-edge-churn-instrumentation-obsv
verified: 2026-05-06T23:07:07Z
status: passed
score: 8/8 must-haves verified
overrides_applied: 0
---

# Phase 203: Target-Edge Churn Instrumentation Verification Report

**Phase Goal:** Operators can read per-sample `load_rtt_delta_us` directly from soak NDJSON and a zone × cause-tag histogram from `soak-summary.json`, so future plans can read the target-edge distribution directly instead of inferring from RTT-integral and zone-trace surfaces.
**Verified:** 2026-05-06T23:07:07Z
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Soak NDJSON captures per-sample `load_rtt_delta_us` plus the supporting Phase 203 fields while preserving v1.42 keys. | ✓ VERIFIED | `scripts/soak-capture.sh:46-57` projects `load_rtt_ms`, `baseline_rtt_ms`, `load_rtt_delta_us`, `last_zone`, and all three `ul_suppressions_*` fields; `tests/test_phase_203_capture_projection.py:114-216` asserts new fields, v1.42 key preservation, null handling, and negative deltas. |
| 2 | `load_rtt_delta_us` is computed as integer microseconds and null-guarded. | ✓ VERIFIED | `scripts/soak-capture.sh:48-53` uses `if ... == null then null else ((load_rtt_ms - baseline_rtt_ms) * 1000 | floor)`. Test slice passed. |
| 3 | Soak summary aggregation emits `diagnostic_distribution.load_rtt_delta_us` with percentiles, max, histogram counts, and explicit `buckets_us`. | ✓ VERIFIED | `scripts/soak_summary_aggregate.py:148-174` builds top-level distribution; fixture summary has `count`, `p50/p95/p99/max`, `samples_total`, `samples_filtered_null`, and histogram `buckets_us`. CLI spot-check returned `samples_total 42`, `samples_filtered_null 3`, `bucket_count 13`, `buckets_us 12`. |
| 4 | `load_rtt_delta_us_by_zone_cause` is a complete 4-zone × 3-cause matrix with zeroed empty-cell behavior. | ✓ VERIFIED | `scripts/soak_summary_aggregate.py:177-206` initializes every zone/cause cell and `_empty_cell()` emits zeroed histograms. `tests/test_phase_203_replay.py:67-72` verifies all 12 synthetic cells populated; v1.42 regression verifies absent Phase 203 fields produce zero cells. |
| 5 | Cause attribution is dual, based on lifetime-counter deltas, first-row excluded, and null deltas filtered from histogram math. | ✓ VERIFIED | `scripts/soak_summary_aggregate.py:180-204` implements previous-row lifetime deltas and dual cause append; `tests/test_phase_203_replay.py:81-84` checks null count, `159-168` checks dual attribution, and `170-179` checks first-row exclusion. CLI spot-check returned `yellow_dual 4 4` and metadata `dual upload`. |
| 6 | Deterministic generator and golden fixtures protect aggregator behavior. | ✓ VERIFIED | `tests/fixtures/_phase_203_generator.py:19-120` uses fixed seed and deterministic `ROW_CATALOG`; `tests/test_phase_203_replay.py:57-65` byte-compares generated output to golden summary, and `124-136` verifies fixture drift. Test slice passed. |
| 7 | Operator docs and changelog document the schema and harness-only invariant. | ✓ VERIFIED | `docs/SOAK_HARNESS.md` documents `load_rtt_delta_us`, `load_rtt_delta_us_by_zone_cause`, buckets, dual attribution, upload-only axis, limitations, and harness-only invariant; `CHANGELOG.md:17-20,33` records the Phase 203 additions. Grep found all required patterns in both docs/changelog. |
| 8 | SAFE-07 is preserved: no `src/wanctl/**` source diff and no Phase 203 control-path edits. | ✓ VERIFIED | `bash scripts/check-safe07-source-diff.sh` passed: `SAFE-07 OK: no src/wanctl/ diff vs b72b463`. Additional verifier checks for committed, unstaged, and staged `src/wanctl/` diffs produced no output; `git status --short` was clean. |

**Score:** 8/8 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `scripts/soak-capture.sh` | Executable public-safe capture harness with v1.42 keys + seven Phase 203 keys. | ✓ VERIFIED | Exists, executable, `bash -n` clean, `HEALTH_URL` mandatory, no RFC1918/hostname literals found in verifier public-safe grep. |
| `tests/test_phase_203_capture_projection.py` | Synthesized `/health` → jq projection test. | ✓ VERIFIED | Extracts projection from script body and asserts field values, null handling, negative deltas, and v1.42 key preservation. |
| `scripts/soak_summary_aggregate.py` | Stdlib aggregator for summary JSON and matrix. | ✓ VERIFIED | Exists, executable, ruff-clean; exposes `aggregate_soak`, `aggregate_load_rtt_delta`, `aggregate_by_zone_cause`, and v1.42 diagnostic aggregation. |
| `tests/fixtures/_phase_203_generator.py` | Deterministic fixture generator. | ✓ VERIFIED | Fixed `SEED = 42`; deterministic `generate_synthetic_ndjson()` protected by replay test. |
| `tests/fixtures/phase_203_synthetic_capture.ndjson` | Synthetic capture fixture. | ✓ VERIFIED | Consumed by replay tests and CLI spot-check. |
| `tests/fixtures/phase_203_synthetic_summary.json` | Golden summary fixture. | ✓ VERIFIED | Byte-compared by `TestAggregatorMath`; includes top-level distribution and matrix. |
| `tests/test_phase_203_replay.py` | Replay tests for aggregator, fixture drift, v1.42 compatibility, zone axis, attribution. | ✓ VERIFIED | Included in passing 56-test phase slice. |
| `docs/SOAK_HARNESS.md` | Operator schema and invariant documentation. | ✓ VERIFIED | Required pattern grep matched; public-safe grep clean. |
| `CHANGELOG.md` | v1.43-dev Phase 203 entries. | ✓ VERIFIED | Required pattern grep matched. |
| `scripts/check-safe07-source-diff.sh` | Re-runnable SAFE-07 gate. | ✓ VERIFIED | Exists, executable, `bash -n` clean; default run passed. |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `scripts/soak-capture.sh` | `/health` endpoint | Mandatory `HEALTH_URL` env var | ✓ WIRED | Guard at `scripts/soak-capture.sh:16`; no hardcoded endpoint. |
| `scripts/soak-capture.sh` jq projection | `tests/test_phase_203_capture_projection.py` | Test extracts same jq object from script body | ✓ WIRED | `_extract_projection()` reads `scripts/soak-capture.sh` and runs jq subprocess. |
| `scripts/soak_summary_aggregate.py` | synthetic fixtures | `aggregate_soak(SYNTHETIC_NDJSON)` byte-compared to golden | ✓ WIRED | `tests/test_phase_203_replay.py:57-65`. |
| `aggregate_by_zone_cause` | lifetime cause counters | Previous-row `ul_suppressions_lifetime_by_cause` delta | ✓ WIRED | `scripts/soak_summary_aggregate.py:191-202`. |
| `docs/SOAK_HARNESS.md` / `CHANGELOG.md` | implemented scripts and schema | Script names and schema fields referenced directly | ✓ WIRED | Grep evidence shows implementation names and new schema terms present. |
| `scripts/check-safe07-source-diff.sh` | Phase 202 close ref | Default `b72b463`, CLI/env override | ✓ WIRED | Script lines 19-23 encode default and override path. |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `scripts/soak-capture.sh` | `load_rtt_delta_us` | Live `/health` JSON via `curl "$HEALTH_URL"`, projected by jq | Yes — computed from `.wans[0].load_rtt_ms` and `.wans[0].baseline_rtt_ms` | ✓ FLOWING |
| `scripts/soak_summary_aggregate.py` | `diagnostic_distribution.load_rtt_delta_us` | NDJSON rows loaded by `load_ndjson()` | Yes — CLI spot-check and replay tests compute non-empty histogram from fixture | ✓ FLOWING |
| `scripts/soak_summary_aggregate.py` | `load_rtt_delta_us_by_zone_cause` | NDJSON `last_zone` + per-cause lifetime counter deltas | Yes — 4×3 matrix populated by fixture and tested | ✓ FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| SAFE-07 gate passes current codebase. | `bash scripts/check-safe07-source-diff.sh` | `SAFE-07 OK: no src/wanctl/ diff vs b72b463` | ✓ PASS |
| Phase 203 replay/capture and compatibility tests pass. | `.venv/bin/pytest tests/test_phase_203_capture_projection.py tests/test_phase_203_replay.py tests/test_phase_202_replay.py tests/test_phase_195_replay.py -q` | `56 passed in 4.45s` | ✓ PASS |
| Hot-path regression remains green. | `.venv/bin/pytest -o addopts='' tests/test_cake_signal.py tests/test_queue_controller.py tests/test_wan_controller.py tests/test_health_check.py -q` | `667 passed in 43.90s` | ✓ PASS |
| Aggregator CLI emits expected summary structure. | `.venv/bin/python scripts/soak_summary_aggregate.py tests/fixtures/phase_203_synthetic_capture.ndjson -o /tmp/phase_203_verify_summary.json` + JSON spot-check | `samples_total 42`, `samples_filtered_null 3`, `bucket_count 13`, zones `GREEN/RED/SOFT_RED/YELLOW`, metadata `dual upload` | ✓ PASS |
| Phase 203 files pass lint. | `.venv/bin/ruff check scripts/soak_summary_aggregate.py tests/fixtures/_phase_203_generator.py tests/test_phase_203_replay.py tests/test_phase_203_capture_projection.py` | `All checks passed!` | ✓ PASS |
| Executable/syntax checks pass. | `test -x ... && bash -n ...` | exit 0 | ✓ PASS |
| Public-safe grep for new public artifacts. | `! grep -nE '(10\.|172\.(1[6-9]|2[0-9]|3[01])\.|192\.168\.)|[a-zA-Z0-9-]+\.local|cake-shaper' ...` | zero matches | ✓ PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| OBSV-05 | 203-01 | Soak NDJSON captures per-sample `load_rtt_delta_us`. | ✓ SATISFIED | Capture script projects `load_rtt_delta_us`; projection tests assert computed/null/negative values. |
| OBSV-06 | 203-02 | `soak-summary.json` aggregates `load_rtt_delta_us` with histogram and zone/cause breakdown. | ✓ SATISFIED | Aggregator emits top-level distribution and `load_rtt_delta_us_by_zone_cause`; CLI spot-check and replay tests pass. |
| OBSV-07 | 203-01, 203-02 | Golden-fixture replay confirms new field populated and aggregated correctly. | ✓ SATISFIED | Capture projection test and replay/golden test both pass; generator drift test present. |
| OBSV-08 | 203-03 | Soak harness README/docs and changelog updated for new field and aggregation contract. | ✓ SATISFIED | `docs/SOAK_HARNESS.md` and `CHANGELOG.md` contain required schema/invariant patterns. Note: `.planning/REQUIREMENTS.md` still shows OBSV-08 unchecked/TBD in metadata, but actual implementation evidence satisfies it. |
| SAFE-07 | 203-01, 203-02, 203-03 | No controller tuning/control-path source diff. | ✓ SATISFIED | SAFE-07 script passed; verifier additionally checked committed, unstaged, and staged `src/wanctl/` diffs and found none. |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `scripts/soak_summary_aggregate.py` | 55 | `return []` in `aggregate_completed_windows()` for fewer than 2 snapshots | ℹ️ Info | Legitimate empty-input helper behavior; not user-visible stub and not part of target-edge matrix path. |

### Code Review Warning Disposition

| Review Finding | Disposition | Rationale |
|----------------|-------------|-----------|
| WR-01: SAFE-07 gate ignores uncommitted `src/wanctl/` edits. | Non-blocking residual warning. | The script meets its planned committed-range contract, and verification compensated by checking `git diff -- src/wanctl/`, `git diff --cached -- src/wanctl/`, and `git status --short`; all were clean. Consider hardening the script later so future users get the same protection automatically. |
| WR-02: Capture script aborts a 24h soak on one transient fetch/projection failure. | Non-blocking residual warning. | This affects long-run harness resilience, not the Phase 203 schema/aggregation goal. No placeholder/stub behavior was found. Worth addressing before relying on unattended 24h evidence collection, but not a blocker for target-edge instrumentation existence and testability. |

### Human Verification Required

None. This phase is harness/schema/test documentation work and all goal-critical behavior was verified with static checks, CLI spot-checks, and pytest.

### Gaps Summary

No blocking gaps found. Phase 203 achieves the roadmap goal: operators have a public-safe capture script that emits per-sample `load_rtt_delta_us`, a tested aggregator that emits top-level and zone × cause distributions with explicit bucket metadata, deterministic replay fixtures, operator documentation, changelog coverage, and a clean SAFE-07 source-diff result.

### Residual Risks

- `scripts/check-safe07-source-diff.sh` should be hardened to fail on staged/unstaged `src/wanctl/` changes, even though the current worktree is clean.
- `scripts/soak-capture.sh` may abort on transient `/health` or `jq` failures under `set -euo pipefail`; consider a row-level error/skip policy before unattended production soaks.
- `.planning/REQUIREMENTS.md` metadata still has OBSV-08 unchecked/TBD despite implementation evidence satisfying it; closeout metadata can be corrected by the orchestrator.

---

_Verified: 2026-05-06T23:07:07Z_
_Verifier: the agent (gsd-verifier)_
