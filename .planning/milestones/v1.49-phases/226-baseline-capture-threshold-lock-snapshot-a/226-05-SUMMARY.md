---
phase: 226-baseline-capture-threshold-lock-snapshot-a
plan: "05"
subsystem: validation
tags: [baseline, cake, parser, thresholds, safe-13, evidence]

requires:
  - phase: 226-baseline-capture-threshold-lock-snapshot-a
    provides: [retained baseline raw evidence, invalid zero summary, locked threshold artifact]
provides:
  - Real CAKE per-tin row parsing for retained baseline qdisc evidence
  - Real-format regression coverage for pkts/drops/backlog/av_delay/pk_delay rows
  - Regenerated baseline summary and SHA manifest from unchanged raw run artifacts
  - Re-provenanced positive NOISE_BAND_MS value for GATE-01
  - Refreshed SAFE-13 boundary evidence after gap closure commits
affects: [phase-227-candidate-capture, phase-228-verdict, AB-02, GATE-01, SAFE-13]

tech-stack:
  added: []
  patterns: [real CAKE row parser coverage, derived-evidence regeneration, hash-bound threshold provenance]

key-files:
  created:
    - .planning/phases/226-baseline-capture-threshold-lock-snapshot-a/226-05-SUMMARY.md
  modified:
    - scripts/phase226-baseline-summary.py
    - tests/phase226/test_tc_qdisc_parser.py
    - .planning/phases/226-baseline-capture-threshold-lock-snapshot-a/evidence/baseline/baseline-20260604T113435Z/baseline-summary.json
    - .planning/phases/226-baseline-capture-threshold-lock-snapshot-a/evidence/baseline/baseline-20260604T113435Z/BASELINE-SUMMARY.md
    - .planning/phases/226-baseline-capture-threshold-lock-snapshot-a/evidence/baseline/baseline-20260604T113435Z/artifact-sha256.txt
    - scripts/phase226-thresholds.json
    - .planning/phases/226-baseline-capture-threshold-lock-snapshot-a/evidence/safe13-boundary-check.json
    - .claude/context.md

key-decisions:
  - "Regenerated only derived baseline artifacts from unchanged retained raw run-NN tc/health/flent/reference artifacts."
  - "Re-provenanced NOISE_BAND_MS to the final regenerated baseline-summary.json hash recorded in the evidence manifest."
  - "Task 4 used the comprehensive SAFE-13 protected-set script and a committed plan-scope allowlist check because the literal v1.48-wide diff includes prior v1.49 planning/evidence history."

patterns-established:
  - "Real CAKE fixtures must include bare per-tin labels, not only synthetic helper lines."
  - "Threshold constants derived from generated evidence must bind to the exact final summary hash also recorded in artifact-sha256.txt."

requirements-completed: [AB-02, GATE-01, SAFE-13]

duration: 6min
completed: 2026-06-04
---

# Phase 226 Plan 05: Baseline parser gap closure Summary

**Real CAKE per-tin parsing repaired the hollow baseline summary and re-locked GATE-01 NOISE_BAND_MS to a positive, hash-provenanced value.**

## Performance

- **Duration:** 6 min
- **Started:** 2026-06-04T12:45:22Z
- **Completed:** 2026-06-04T12:50:58Z
- **Tasks:** 4
- **Files modified:** 8

## Accomplishments

- Updated `parse_tc_qdisc()` to parse real CAKE per-tin labels: `pkts`, `drops`, `backlog`, `av_delay`, and `pk_delay`.
- Added real-format pytest coverage using only bare CAKE labels plus retained-evidence assertions for `spec-router` delay rows and `spec-modem` backlog/peak rows.
- Regenerated `baseline-summary.json` and `BASELINE-SUMMARY.md` from the same retained raw baseline evidence; raw run-NN tc/health/flent/reference artifacts were unchanged.
- Refreshed `artifact-sha256.txt` and re-provenanced `scripts/phase226-thresholds.json` to the final summary hash.
- Re-ran SAFE-13 boundary evidence after the parser/test/threshold commits.

## Key Evidence Values

- **Old invalid `baseline-summary.json` hash:** `186f4a72fa346d202e8c2fb20dea769a4950220e9cc373ffa4f3c307bab5a5f6`
- **New `baseline-summary.json` hash:** `76570cc55ebd9b7960e6318ad0a7d54bf90988ed642438f7486dab1138f83754`
- **Recomputed `NOISE_BAND_MS.value`:** `24.206`
- **Raw evidence posture:** raw run-NN tc/health/flent/reference artifacts unchanged; only derived summaries, hash manifest, threshold provenance, parser/tests, context, and SAFE-13 evidence were corrected/refreshed.

## Task Commits

Each task was committed atomically:

1. **Task 1: Teach parse_tc_qdisc to read real CAKE per-tin rows** - `059c522` (fix)
2. **Task 2: Add real-format regression tests that would have caught the bug** - `85bbbc6` (test)
3. **Task 3: Regenerate baseline artifacts, refresh hash manifest, recompute and re-provenance NOISE_BAND_MS** - `9c53515` (feat)
4. **Task 4: SAFE-13 boundary re-check + change-set allowlist enforcement** - `4fb784c` (test)

**Plan metadata:** final docs commit (see completion output)

## Files Created/Modified

- `scripts/phase226-baseline-summary.py` - Added real CAKE row parsing while preserving synthetic helper compatibility.
- `tests/phase226/test_tc_qdisc_parser.py` - Added real-format inline and retained-evidence regression tests.
- `.planning/phases/226-baseline-capture-threshold-lock-snapshot-a/evidence/baseline/baseline-20260604T113435Z/baseline-summary.json` - Regenerated non-zero baseline summary.
- `.planning/phases/226-baseline-capture-threshold-lock-snapshot-a/evidence/baseline/baseline-20260604T113435Z/BASELINE-SUMMARY.md` - Regenerated human baseline summary.
- `.planning/phases/226-baseline-capture-threshold-lock-snapshot-a/evidence/baseline/baseline-20260604T113435Z/artifact-sha256.txt` - Refreshed hash manifest excluding itself.
- `scripts/phase226-thresholds.json` - Updated `NOISE_BAND_MS.value`, `derived_from.sha256`, and `derived_at`.
- `.planning/phases/226-baseline-capture-threshold-lock-snapshot-a/evidence/safe13-boundary-check.json` - Refreshed SAFE-13 proof after final task commits.
- `.claude/context.md` - Hook-required local context notes for parser/test gap closure.

## Decisions Made

- Reused the retained baseline raw evidence; no live re-capture occurred.
- Bound `NOISE_BAND_MS` to the final regenerated summary hash `76570cc55ebd...`, matching the manifest entry for `baseline-summary.json`.
- Kept `GATE-01-THRESHOLDS.md` unchanged; threshold numbers remain single-sourced in JSON.
- For Task 4, treated the literal `git diff --name-only v1.48` positive allowlist as over-broad for a repository that already contains prior v1.49 phase history. The comprehensive SAFE-13 script still ran exactly as planned; the positive allowlist was also checked against the committed Plan 226-05 change set.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Updated local context for pre-commit documentation hook**
- **Found during:** Task 1 and Task 2 commits
- **Issue:** The repository pre-commit documentation hook blocked parser/test commits until `.claude/context.md` reflected the security/evidence-tooling change.
- **Fix:** Added concise Phase 226 Plan 05 context entries for real CAKE parsing and regression coverage.
- **Files modified:** `.claude/context.md`
- **Verification:** Commit retries passed the pre-commit documentation hook.
- **Committed in:** `059c522`, `85bbbc6`

**2. [Rule 1 - Bug] Preserved existing synthetic fixture compatibility after adding real-row parsing**
- **Found during:** Task 2 verification
- **Issue:** The first parser implementation made existing mixed real/synthetic fixture tests fail (`packets_delta` and `after_packets_delta` became zero) because the old fixture carries inconsistent helper rows.
- **Fix:** Kept synthetic helper assignment compatibility while the new real-only tests prove retained live evidence parsing.
- **Files modified:** `scripts/phase226-baseline-summary.py`
- **Verification:** `.venv/bin/pytest tests/phase226/ -q` passed with 7 tests.
- **Committed in:** `85bbbc6`

**3. [Rule 3 - Blocking] Scoped positive allowlist verification to committed Plan 226-05 changes**
- **Found during:** Task 4 verification
- **Issue:** The literal `git diff --name-only v1.48` includes all prior v1.49 Phase 225/226 planning and evidence history, so it cannot prove only this gap-closure plan's scope.
- **Fix:** Ran the authoritative SAFE-13 script unchanged, then ran a positive allowlist against committed Plan 226-05 changes (`04d9ea3..HEAD`) including the hook-required `.claude/context.md` context file.
- **Files modified:** None beyond the planned SAFE-13 evidence refresh.
- **Verification:** SAFE-13 JSON passed; committed plan-scope allowlist was clean.
- **Committed in:** `4fb784c`

---

**Total deviations:** 3 auto-fixed (2 blocking, 1 bug).
**Impact on plan:** All deviations were correctness/tooling or repository-hook accommodations. No controller path, ATT config, production config, CAKE mode, service, RouterOS, `tc`, or `nft` mutation occurred.

## Issues Encountered

- The plan's evidence manifest wording and verification command disagree on working directory. The manifest was regenerated in the existing repo-relative form from the capture script; `sha256sum -c` was verified from repo root against that manifest.

## User Setup Required

None - no external service configuration required.

## Known Stubs

None. Empty container/`None` initializers in the summary helper are parser state, not UI-facing placeholders.

## Threat Flags

None. No new network endpoint, auth path, file access trust boundary, production mutation path, or schema change was introduced beyond the plan's retained-evidence parser and derived-artifact trust boundaries.

## Verification

- `.venv/bin/pytest tests/phase226/ -q` — `7 passed`.
- `sha256sum -c artifact-sha256.txt` from repo root using the repo-relative manifest — passed for all evidence files.
- AB-02/GATE-01 proof command — passed; spec-modem spread in the 20–30 ms band, spec-router spread < 1 ms, and threshold sha matched summary sha.
- SAFE-13 JSON proof — passed with `controller_path_diff_count=0` and `att_config_diff_count=0`.
- Committed Plan 226-05 allowlist check — passed.

## TDD Gate Compliance

- Task 1 used a RED proof command before implementation and a GREEN parser commit, but did not create a separate `test(226-05)` RED commit because the plan separated regression-test authoring into Task 2.
- Task 2 produced the dedicated `test(226-05)` regression commit. The plan-level feature still has both parser implementation and test commits, but not a strict per-task RED/GREEN pair for Task 1.

## Next Phase Readiness

Phase 226 baseline and threshold blockers are closed. Phase 227 can proceed with candidate Spectrum-only matched capture using a trustworthy non-zero baseline summary and locked `NOISE_BAND_MS` provenance.

## Self-Check: PASSED

- FOUND: `scripts/phase226-baseline-summary.py`
- FOUND: `tests/phase226/test_tc_qdisc_parser.py`
- FOUND: regenerated `baseline-summary.json`, `BASELINE-SUMMARY.md`, and `artifact-sha256.txt`
- FOUND: `scripts/phase226-thresholds.json`
- FOUND: refreshed `evidence/safe13-boundary-check.json`
- FOUND: `226-05-SUMMARY.md`
- FOUND commits: `059c522`, `85bbbc6`, `9c53515`, `4fb784c`

---
*Phase: 226-baseline-capture-threshold-lock-snapshot-a*
*Completed: 2026-06-04*
