---
phase: 204-d-14-successor-recalibration-calib
verified: 2026-05-13T04:26:19Z
status: passed
score: 6/6 must-haves verified
overrides_applied: 0
re_verification:
  previous_status: satisfied
  previous_score: 6/6
  gaps_closed:
    - "Prior post-d44e2fd evidence gaps remain closed: corrected CALIB-01 rerun 20260509T183037Z, CALIB-02 threshold 175, corrected CALIB-04 pass rerun 20260512T004208Z."
  gaps_remaining: []
  regressions: []
---

# Phase 204: D-14 Successor Recalibration (CALIB) Verification Report

**Phase Goal:** D-14 successor recalibration / CALIB closeout for v1.43 with post-d44e2fd evidence validity.
**Verified:** 2026-05-13T04:26:19Z
**Status:** passed
**Re-verification:** Yes — refreshed from the prior `satisfied` report to canonical verifier status `passed`, and rechecked the actual evidence/code paths.

## Goal Achievement

Phase 204 achieved its goal. The valid closeout chain is the post-d44e2fd chain, not the superseded pre-boundary-marker evidence:

- CALIB-01 corrected baseline rerun: `soak/20260509T183037Z/` has 84,100 rows, parse errors `0`, missing boundary markers `0`, completed-window distribution `valid=true`, `window_count=1440`, top-level p99 `105.2199999999998`, and dwell-hold p99 `95.2199999999998`.
- CALIB-02 final approved threshold: `175`, captured in `204-CALIB-02-OPERATOR-APPROVAL.md` and mirrored in `scripts/calib_02_threshold.json`.
- CALIB-04 final passing rerun: `soak/20260512T004208Z/` has 84,099 rows, parse errors `0`, missing boundary markers `0`, primary gate delta `0`, and completed-window p99 dwell-hold `135.6199999999999 <= 175` with verdict `pass`.
- SAFE-07 holds at close: the helper returned `SAFE-07 OK: only planned src/wanctl/__init__.py version bump vs b72b463`; an additional worktree/staged `src/wanctl/` diff check was clean.

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | 24h baseline soak on production Spectrum under post-Plan-201-14 binary + new metric live produces a representative completed-window suppression-count distribution. | ✓ VERIFIED | `soak/20260509T183037Z/soak-summary.json` reports `valid=true`, `boundary_source=ul_hysteresis_window_start_epoch`, `window_count=1440`, mean `17.131944444444443`, p50 `9.0`, p95 `63.0`, p99 `105.2199999999998`, max `147`; boundary check over NDJSON found `missing_boundary=0`. |
| 2 | Operator-approved D-14 successor threshold is recorded with explicit rationale tied to valid CALIB-01 evidence and post-fix control surface. | ✓ VERIFIED | `204-CALIB-02-OPERATOR-APPROVAL.md` records `decision: approved`, `statistic: p99`, `threshold: 175`, `headroom_factor: 1.5`, `gate_column: by_cause.dwell_hold`, with rationale for the FAIL-A continuation and corrected CALIB-01 reference `20260509T183037Z`; `scripts/calib_02_threshold.json` mirrors these values. |
| 3 | Soak harness watchdog uses the completed-window statistic and emits legacy alongside for one transition cycle. | ✓ VERIFIED | `scripts/soak_summary_aggregate.py` defines `load_calib_02_constants()` and `aggregate_watchdog()`, returns both `secondary_gate_legacy` and `secondary_gate_completed_window`, and `aggregate_soak()` emits both top-level blocks. `tests/test_phase_204_watchdog.py` verifies the v1.42 legacy oracle and active CALIB-02 constants. |
| 4 | Verification 24h soak under the recalibrated threshold passes the dual gate cleanly: D-19 primary 0 floor hits and D-14 successor passes. | ✓ VERIFIED | `204-05-CALIB-04-SOAK-VERDICT.md` records `verdict: pass`, `soak_ts: 20260512T004208Z`, `primary_gate_delta: 0`, `secondary_gate_value: 135.6199999999999`, `secondary_gate_threshold: 175`; `soak-summary.json` has `primary_gate.verdict=pass`, `primary_gate.delta=0`, and `secondary_gate_completed_window.verdict=pass`. |
| 5 | RETRO captures threshold-basis hygiene as a durable lesson. | ✓ VERIFIED | `204-RETRO.md` Key Lesson #1 contains “threshold-basis hygiene”; the post-d44e2fd Gap Closure addendum records the evidence-pipeline revalidation lesson. |
| 6 | SAFE-07 no-controller-tuning invariant holds at v1.43 close. | ✓ VERIFIED | `bash scripts/check-safe07-source-diff.sh` passed; additional `git diff -- src/wanctl/` and `git diff --cached -- src/wanctl/` checks were clean. Phase 204 has only the planned `src/wanctl/__init__.py` version bump vs `b72b463`. |

**Score:** 6/6 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|---|---|---|---|
| `scripts/soak-capture.sh` | Capture target-edge and boundary-marker fields. | ✓ VERIFIED | Projects `ul_hysteresis_window_start_epoch` at line 55 plus completed-window and lifetime suppression fields. |
| `scripts/soak_summary_aggregate.py` | Completed-window distribution and dual watchdog gates. | ✓ VERIFIED | Defines explicit boundary-marker aggregation, fail-closed missing-boundary behavior, `aggregate_watchdog()`, and JSON constants loader. |
| `tests/test_phase_203_capture_projection.py` | Projection regression includes boundary marker. | ✓ VERIFIED | Complete-set assertion includes `ul_hysteresis_window_start_epoch`; phase-scoped pytest slice passed. |
| `tests/test_phase_204_distribution.py` | Distribution semantics regression coverage. | ✓ VERIFIED | Included in phase-scoped slice: 48 total tests passed across selected phase files. |
| `tests/test_phase_204_watchdog.py` | Watchdog loader, legacy oracle, and pass/fail coverage. | ✓ VERIFIED | Asserts active threshold `175`, v1.42 legacy oracle value, and synthetic pass/fail branches. |
| `soak/20260509T183037Z/soak-capture.ndjson` | Corrected-boundary CALIB-01 raw evidence. | ✓ VERIFIED | 84,100 rows; parse errors `0`; missing boundary markers `0`; span ~86,399.6s. Row-count proxy miss accepted by stronger quality evidence. |
| `soak/20260509T183037Z/soak-summary.json` | CALIB-01 current-code distribution. | ✓ VERIFIED | `valid=true`, `window_count=1440`, dwell-hold p99 `95.2199999999998`. |
| `204-CALIB-02-OPERATOR-APPROVAL.md` | Distinct final operator approval artifact. | ✓ VERIFIED | Records final threshold `175` and explicit FAIL-A continuation rationale. |
| `scripts/calib_02_threshold.json` | Machine-readable CALIB-02 constants. | ✓ VERIFIED | Valid JSON with `threshold: 175`, `statistic: p99`, `headroom_factor: 1.5`, `gate_column: by_cause.dwell_hold`, and corrected CALIB-01 reference. |
| `soak/20260512T004208Z/soak-capture.ndjson` | Corrected-boundary CALIB-04 raw evidence. | ✓ VERIFIED | 84,099 rows; parse errors `0`; missing boundary markers `0`; span ~86,398.19s. Row-count proxy miss accepted by stronger quality evidence. |
| `soak/20260512T004208Z/soak-summary.json` | Current-code CALIB-04 dual-gate verdict source. | ✓ VERIFIED | `primary_gate.delta=0`, completed-window p99 dwell-hold `135.6199999999999`, threshold `175`, verdict `pass`. |
| `204-05-CALIB-04-SOAK-VERDICT.md` | Operator-readable verdict from current summary. | ✓ VERIFIED | `verdict: pass`, cites superseded pre-boundary and FAIL-A runs as provenance. |
| `204-RETRO.md` | CALIB-05 lesson and gap-closure addendum. | ✓ VERIFIED | Contains threshold-basis hygiene and post-d44e2fd revalidation lesson. |

### Key Link Verification

| From | To | Via | Status | Details |
|---|---|---|---|---|
| `scripts/soak-capture.sh` | NDJSON boundary-marker field | jq projection | ✓ WIRED | `ul_hysteresis_window_start_epoch` projected from `/health.wans[0].upload.hysteresis.window_start_epoch`; projection test enforces it. |
| NDJSON boundary marker | `_completed_window_snapshots()` | `row.get("ul_hysteresis_window_start_epoch")` | ✓ WIRED | Missing marker causes fail-closed distribution; corrected CALIB-01/04 captures have zero missing markers. |
| `aggregate_soak()` | completed-window watchdog blocks | `aggregate_watchdog()` + `load_calib_02_constants()` | ✓ WIRED | Latest CALIB-04 summary threshold/value match `scripts/calib_02_threshold.json`. |
| `scripts/calib_02_threshold.json` | `aggregate_watchdog()` constants | loader reads JSON at runtime | ✓ WIRED | Active threshold `175`, statistic `p99`, gate column `by_cause.dwell_hold` reflected in test and latest summary. |
| CALIB-01 corrected summary | CALIB-02 approval | file citation and numeric rationale | ✓ VERIFIED | Approval references `soak/20260509T183037Z/soak-summary.json` and its dwell-hold distribution. |
| CALIB-04 corrected summary | verdict file | copied gate fields | ✓ VERIFIED | Verdict cites `20260512T004208Z` pass with primary `0` and secondary `135.6199999999999 <= 175`. |
| SAFE-07 helper | v1.43 close | git diff vs `b72b463` | ✓ VERIFIED | Helper passed; staged/unstaged `src/wanctl/` diffs additionally checked clean to compensate for advisory WR-01. |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|---|---|---|---|---|
| `scripts/soak-capture.sh` | `ul_hysteresis_window_start_epoch` | Live `/health` response at cake-shaper | Yes — captured rows in `20260509T183037Z` and `20260512T004208Z` include non-null boundary markers. | ✓ FLOWING |
| `scripts/soak_summary_aggregate.py` | `suppressions_completed_window_count_distribution` | NDJSON rows + boundary marker transitions | Yes — current summaries contain non-empty valid distributions (`window_count=1440` / `1439`). | ✓ FLOWING |
| `scripts/calib_02_threshold.json` | threshold/statistic/gate column | Operator approval artifact | Yes — JSON mirrors final approval (`175`, `p99`, `by_cause.dwell_hold`) and is consumed by `aggregate_soak()`. | ✓ FLOWING |
| `204-05-CALIB-04-SOAK-VERDICT.md` | pass/fail verdict fields | `soak/20260512T004208Z/soak-summary.json` | Yes — numeric fields match summary and latest evidence. | ✓ FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|---|---|---|---|
| Corrected soak evidence has boundary markers and expected gate values. | `python` verifier script over `soak/20260509T183037Z` and `soak/20260512T004208Z` NDJSON/summary files | CALIB-01: 84,100 rows, `missing_boundary=0`, `valid=true`, `window_count=1440`; CALIB-04: 84,099 rows, `missing_boundary=0`, `primary.delta=0`, secondary `135.6199999999999 <= 175`. | ✓ PASS |
| SAFE-07 source-diff invariant holds, including uncommitted source changes. | `bash scripts/check-safe07-source-diff.sh; test -z "$(git diff -- src/wanctl/)"; test -z "$(git diff --cached -- src/wanctl/)"` | `SAFE-07 OK: only planned src/wanctl/__init__.py version bump vs b72b463`; `working-tree-src-clean`. | ✓ PASS |
| Phase-scoped regression slice passes. | `.venv/bin/pytest tests/test_phase_203_capture_projection.py tests/test_phase_204_distribution.py tests/test_phase_204_watchdog.py tests/test_phase_195_replay.py -q` | `48 passed in 2.94s`. | ✓ PASS |
| Orchestrator full-suite regression after closeout. | `.venv/bin/pytest tests/ -q` | Documented latest closeout gate: `4977 passed, 6 skipped, 2 deselected in 196.02s` (also corroborated by `204-10-SUMMARY.md`, 197.72s). Not rerun here to keep verification fast. | ✓ PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|---|---|---|---|---|
| CALIB-01 | 204-01, 204-02, refreshed 204-07, closeout 204-10 | Clean 24h Spectrum baseline soak produces representative completed-window distribution. | ✓ SATISFIED | Corrected CALIB-01 rerun `20260509T183037Z`: `valid=true`, `window_count=1440`, p99 fields present, boundary markers valid. |
| CALIB-02 | 204-03, refreshed 204-08/204-09, closeout 204-10 | Operator-approved threshold with explicit rationale referencing CALIB-01 distribution. | ✓ SATISFIED | Final approval artifact and JSON record threshold `175`, with corrected CALIB-01 reference and FAIL-A continuation rationale. |
| CALIB-03 | 204-04 | Watchdog computation uses completed-window statistic and emits legacy alongside. | ✓ SATISFIED | Aggregator functions and latest summary expose `secondary_gate_completed_window` and `secondary_gate_legacy`; tests cover loader/oracle/pass/fail paths. |
| CALIB-04 | 204-05, refreshed 204-09, closeout 204-10 | Verification 24h soak passes D-19 primary and D-14 successor gate. | ✓ SATISFIED | `204-05-CALIB-04-SOAK-VERDICT.md` and `20260512T004208Z/soak-summary.json` show pass with primary delta `0` and secondary `135.6199999999999 <= 175`. |
| CALIB-05 | 204-06 | RETRO captures threshold-basis hygiene. | ✓ SATISFIED | `204-RETRO.md` Key Lesson #1 and Gap Closure addendum. |
| SAFE-07 | 204-01, 204-04, 204-06, 204-10 (cross-cutting) | No controller tuning within v1.43; only planned version bump allowed. | ✓ SATISFIED | SAFE-07 helper passed; manual staged/unstaged `src/wanctl/` checks clean; REQUIREMENTS/ROADMAP record v1.43 no-controller-tuning invariant. |

All requested IDs are accounted for: CALIB-01, CALIB-02, CALIB-03, CALIB-04, CALIB-05, and SAFE-07. `.planning/REQUIREMENTS.md` maps exactly these Phase 204 IDs; no Phase 204 orphan requirement was found.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|---|---:|---|---|---|
| `scripts/soak_summary_aggregate.py` | 76, 214 | `return []` empty-data paths | ℹ️ Info | Legitimate empty-input/fail-closed helper paths; not user-visible stub data and not a Phase 204 goal blocker. |
| `204-REVIEW.md` | 42-99 | WR-01/WR-02/WR-03 advisory warnings | ⚠️ Warning | Non-blocking for this verification: WR-01 compensated by explicit worktree/staged source checks; WR-02 does not affect valid active constants; WR-03 did not invalidate completed soaks. These should be considered future hardening, not must-have gaps. |
| `204-RETRO.md` / `204-10-SUMMARY.md` | various | TODO references | ℹ️ Info | Intentional v1.44 follow-up tracking for dropping legacy gate / YAML promotion; not an unimplemented v1.43 must-have. |

### Human Verification Required

None. The phase goal is evidence/artifact based and was verified programmatically from committed artifacts, JSON summaries, tests, and SAFE-07 diff checks.

### Gaps Summary

No blocking gaps remain. The post-d44e2fd evidence chain is valid, the final threshold is explicitly approved at `175`, the final CALIB-04 rerun passes the dual gate, and SAFE-07 remains clean. Phase 204 goal achieved.

---

_Verified: 2026-05-13T04:26:19Z_
_Verifier: the agent (gsd-verifier)_
