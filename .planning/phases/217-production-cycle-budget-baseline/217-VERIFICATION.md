---
phase: 217-production-cycle-budget-baseline
verified: 2026-05-30T01:54:42Z
status: passed
score: 12/12 must-haves verified
overrides_applied: 0
---

# Phase 217: Production Cycle-Budget Baseline Verification Report

**Phase Goal:** Close the pending post-hotpath profiling todo and decide whether performance is actually limiting quality.
**Verified:** 2026-05-30T01:54:42Z
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | At least one hour of current production cycle-budget data is captured on representative Spectrum. | ✓ VERIFIED | `.planning/perf/217-capture-window.json` records `2026-05-29T23:43:16Z` → `2026-05-30T00:44:16Z` (`3660s`) and `validation.cycle_timing_records = 71560`. |
| 2 | Capture used JSON `Cycle timing` records with `cycle_total_ms` and subsystem `*_ms` extras. | ✓ VERIFIED | Profile artifact contains `autorate_cycle_total.count = 71560`; capture metadata has `cycle_total_types = ["number"]`; parser tests verify JSON label reconstruction. |
| 3 | Production profiling was transient and reverted after capture. | ✓ VERIFIED | `.planning/perf/217-capture-window.json` has `revert_verified: true`, `systemctl_cat_profile_debug_matches: 0`, `process_profile_debug_matches: 0`, `service_active: active`, `health_status: healthy`. |
| 4 | Driven segment exercised router-write path inside the window. | ✓ VERIFIED | `driven_segment` timestamps are inside the capture window; `validation.router_write_coverage = present`, `router_write_records = 401`. |
| 5 | Subsystem cost summary identifies the dominant hot-path category. | ✓ VERIFIED | `.planning/perf/217-cycle-budget-summary.md` names `logging_metrics` as dominant at `8.26%` and includes RTT, CAKE, router communication, and logging/metrics table. |
| 6 | Router dominance calculation uses parent `autorate_router_communication`, not child double-counting. | ✓ VERIFIED | Summary explicitly states router category uses `autorate_router_communication` only; profile includes parent and child labels separately. |
| 7 | Storage writes are attributed out-of-band with explicit window bounds, not fabricated as a hot-path percentage. | ✓ VERIFIED | `.planning/perf/v1.45-baseline-spectrum-20260529.ingestion.json` is a structured `unmeasured` artifact with the same start/end window; summary says storage has no hot-path label and no storage percent is asserted. |
| 8 | D-03 absolute-bar verdict is falsifiable and stated before narrative. | ✓ VERIFIED | Summary states `passes_headroom = true`, `passes_dominance = true`, with `cycle_total.avg_ms = 2.883`, `p99_ms = 6.9`, max category `8.26%`. |
| 9 | D-04 drops unanchored v1.39-relative clauses. | ✓ VERIFIED | Summary and todo close section state archived baselines are informational only and +/-15%/+/-25%-vs-v1.39 clauses are dropped as unfalsifiable. |
| 10 | Healthy cycle budget leads to explicit PERF-03 deprioritization decision. | ✓ VERIFIED | Summary Decision: “Performance work is deprioritized in favor of quality/tuning work.” |
| 11 | Pending profiling todo is closed or promoted. | ✓ VERIFIED | Todo exists under `.planning/todos/done/2026-04-15-profile-post-hotpath-baseline-on-production-wan.md`, not pending, with `## Closed — 2026-05-30 (Phase 217)`. |
| 12 | No production control-path/source changes were made. | ✓ VERIFIED | `git diff --name-only HEAD~12..HEAD -- src/` returned no files; artifacts are docs/scripts/planning only. |

**Score:** 12/12 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `docs/PROFILING.md` | Durable JSON capture runbook with pilot, revert, retrieve, analyze, D-03 bars. | ✓ VERIFIED | Contains `WANCTL_LOG_FORMAT=json`, `--profile --debug`, `systemctl revert wanctl@spectrum`, `profiling_collector_json.py`, `spectrum_debug.log`, `ingestion-rate`, `router_communication`, and pilot section. |
| `.planning/perf/.gitkeep` | Committed perf artifact directory placeholder. | ✓ VERIFIED | Exists. |
| `.planning/perf/capture/.gitignore` | Raw capture directory ignores all except `.gitignore`. | ✓ VERIFIED | Body is `*` then `!.gitignore`; `git ls-files '.planning/perf/capture/*'` returns only `.gitignore`. |
| `scripts/profiling_collector_json.py` | Stdlib NDJSON parser emitting collector-compatible stats. | ✓ VERIFIED | 136 lines; no third-party imports; focused tests passed `3 passed`. Fails closed when `autorate_cycle_total` is absent. |
| `tests/test_profiling_collector_json.py` | Regression coverage for parser behavior. | ✓ VERIFIED | Covers label reconstruction, malformed/non-cycle skip, output-file CLI, empty-input exit 2, and missing cycle total exit 2. |
| `.planning/perf/217-capture-window.json` | Structured capture metadata with window, pilot, driven segment, validation, revert proof. | ✓ VERIFIED | Parses JSON; window spans 3660s; `revert_verified: true`; `router_write_coverage: present`; `cycle_timing_records: 71560`. |
| `.planning/perf/v1.45-baseline-spectrum-20260529.profile.json` | Canonical per-label profile artifact. | ✓ VERIFIED | Contains `autorate_cycle_total` with `count=71560`, `avg_ms=2.883`, `p99_ms=6.9`, plus four PERF-02 hot-path labels. |
| `.planning/perf/v1.45-baseline-spectrum-20260529.ingestion.json` | Windowed storage attribution artifact or structured unmeasured stub. | ✓ VERIFIED | Structured `status: unmeasured`; window matches capture metadata; no fabricated storage number. |
| `.planning/perf/217-cycle-budget-summary.md` | One-page verdict/dominance/observer/storage/decision summary. | ✓ VERIFIED | Contains all required numbers and decision; no `TBD`, placeholder token, or production IP match found. |
| `.planning/todos/done/2026-04-15-profile-post-hotpath-baseline-on-production-wan.md` | Closed/promoted todo with Phase 217 verdict. | ✓ VERIFIED | Original content preserved; Phase 217 close section references summary and profile artifact; date matches capture end date. |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `scripts/profiling_collector_json.py` | Existing collector JSON schema | Per-label `count/min_ms/p50_ms/avg_ms/max_ms/p95_ms/p99_ms` output | ✓ WIRED | Parser `calculate_statistics()` and tests produce the canonical keys; committed profile has the same schema for each label. |
| `docs/PROFILING.md` | JSON parser + storage attribution workflow | Analyze section invokes parser and `wanctl.history --ingestion-rate --from --to` | ✓ WIRED | Runbook encodes both commands and D-03 jq verdict pipeline. |
| `.planning/perf/capture/spectrum_debug.ndjson` | `.profile.json` | `scripts/profiling_collector_json.py` | ✓ WIRED | Summary and artifacts show parser generated `.planning/perf/v1.45-baseline-spectrum-20260529.profile.json`; focused parser tests pass. |
| `.planning/perf/217-capture-window.json` | `.ingestion.json` | Explicit window bounds | ✓ WIRED | Ingestion artifact window exactly equals capture metadata window. |
| `.profile.json` | `217-cycle-budget-summary.md` | D-03 verdict math | ✓ WIRED | Summary numbers match profile: avg `2.883`, p99 `6.9`, dominant `logging_metrics` `8.26%`. |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `scripts/profiling_collector_json.py` | per-label samples | NDJSON `Cycle timing` records with numeric `*_ms` keys | Yes | ✓ FLOWING — tests and committed profile prove `autorate_cycle_total` and subsystem labels are populated. |
| `.planning/perf/v1.45-baseline-spectrum-20260529.profile.json` | `autorate_cycle_total`, hot-path label stats | Plan 02 validated capture (`71560` records) | Yes | ✓ FLOWING — count matches `217-capture-window.json` validation. |
| `.planning/perf/217-cycle-budget-summary.md` | cycle budget + dominance numbers | `.profile.json`, `.ingestion.json`, `217-capture-window.json` | Yes | ✓ FLOWING — all cited numbers match committed JSON artifacts. |
| `.planning/perf/v1.45-baseline-spectrum-20260529.ingestion.json` | storage attribution | `wanctl-history --ingestion-rate` attempted against production DB window | Structured unmeasured | ✓ FLOWING — planned fallback used; explicitly reports no DB access instead of inventing data. |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| JSON collector tests pass | `.venv/bin/pytest -q tests/test_profiling_collector_json.py` | `3 passed in 0.27s` | ✓ PASS |
| Committed artifacts satisfy numeric gates | Python validation of capture/profile/ingestion JSON | window `3660s`, `71560` records, `revert_verified=True`, `router_write_coverage=present`, `avg=2.883`, `p99=6.9` | ✓ PASS |
| Raw capture files are not committed | `git ls-files '.planning/perf/capture/*'` | only `.planning/perf/capture/.gitignore` | ✓ PASS |
| No `src/` files changed in phase commits | `git diff --name-only HEAD~12..HEAD -- src/` | no output | ✓ PASS |
| Full suite after final fix | User-provided verification fact: `make test` | `5221 passed, 6 skipped, 2 deselected` | ✓ PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| PERF-01 | 217-01, 217-02, 217-03 | Pending post-hotpath production profiling todo is closed or promoted after ≥1h production cycle-budget capture. | ✓ SATISFIED | Capture window is ≥1h with `71560` records; todo moved to `done/` with Phase 217 close section. |
| PERF-02 | 217-01, 217-03 | Profile identifies whether RTT measurement, CAKE stats, router communication, logging/metrics, or storage writes dominate. | ✓ SATISFIED | Summary identifies `logging_metrics` as dominant at `8.26%`; table covers RTT, CAKE, router parent, logging; storage is separately attributed as structured `unmeasured`. |
| PERF-03 | 217-03 | If cycle budget is healthy, performance work is explicitly deprioritized in favor of quality/tuning work. | ✓ SATISFIED | Both D-03 gates pass; summary contains explicit deprioritization sentence. Note: `.planning/REQUIREMENTS.md` still marks PERF-03 pending in the checklist/traceability table, but the committed Phase 217 artifacts satisfy the requirement. |

No orphaned Phase 217 requirements were found beyond PERF-01, PERF-02, and PERF-03.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| — | — | — | — | No blocker/warning anti-patterns found in reviewed Phase 217 files. Grep found no TODO/FIXME/stub patterns in `scripts/profiling_collector_json.py`, no placeholder/IP matches in `217-cycle-budget-summary.md`, and no secret/IP/key patterns in committed `.planning/perf` JSON/MD artifacts. |

### Human Verification Required

None. The production-host action itself was operator-gated during Plan 02 and is represented by committed metadata with `revert_verified: true`; no additional human verification is needed for goal achievement.

### Gaps Summary

No blocking gaps found. Phase 217 achieved the roadmap goal: it captured and analyzed the production cycle-budget baseline, produced committed aggregate artifacts, identified the dominant cost category, closed the pending profiling todo, and explicitly deprioritized performance work because the measured cycle budget is healthy.

---

_Verified: 2026-05-30T01:54:42Z_
_Verifier: the agent (gsd-verifier)_
