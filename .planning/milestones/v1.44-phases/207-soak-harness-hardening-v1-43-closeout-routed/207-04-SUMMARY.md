---
phase: 207-soak-harness-hardening-v1-43-closeout-routed
plan: 04
subsystem: decision-routing
tags: [hrdn-04, calib-02, docs-only, phase-207, v1-44]

requires:
  - phase: 207-03
    provides: v1.44 CHANGELOG Unreleased section with HRDN-03 Removed subsection
provides:
  - HRDN-04 NO decision for CALIB-02 threshold YAML promotion
  - CHANGELOG rationale anchors tying the NO route to CALIB-04 PASS evidence, fail-closed JSON convention, and T17(b)/SEED-005 deferral
  - Repo-wide audit evidence that no `calib_02_threshold:` YAML key was introduced
affects: [phase-207, phase-209, CALIB-02, T17b, SAFE-09]

tech-stack:
  added: []
  patterns: [docs-only decision record, negative config-surface audit, git-diff byte-identical invariant]

key-files:
  created: []
  modified: [CHANGELOG.md]

key-decisions:
  - "HRDN-04 routes to NO: CALIB-02 threshold remains in scripts/calib_02_threshold.json; no YAML key or validator schema entry is added."
  - "Deeper CALIB-02 knob-shape/schema design remains deferred to Future Requirement T17(b), gated on SEED-005 outcomes."

patterns-established:
  - "CHANGELOG decision entries can record explicit NO routes with rationale anchors and reversibility notes."
  - "Docs-only NO decisions should pair byte-identical git-diff gates with a repo-wide negative key audit."

requirements-completed: [HRDN-04]

duration: 1 min
completed: 2026-05-15
---

# Phase 207 Plan 04: HRDN-04 CALIB-02 YAML Promotion Decision Summary

**CALIB-02 threshold YAML promotion routed to NO in the v1.44 CHANGELOG, preserving the fail-closed JSON threshold artifact and deferring schema design to T17(b)/SEED-005.**

## Performance

- **Duration:** 1 min
- **Started:** 2026-05-15T21:17:10Z
- **Completed:** 2026-05-15T21:18:33Z
- **Tasks:** 2/2
- **Files modified:** 1

## Accomplishments

- Added a sibling `### Decisions` subsection under the existing `## Unreleased (v1.44 — in progress)` CHANGELOG section without duplicating the Unreleased header.
- Recorded HRDN-04 as a deliberate NO route: `scripts/calib_02_threshold.json` remains the operator-approved threshold artifact; no `continuous_monitoring.upload.calib_02_threshold` YAML key or autorate validator schema entry is added.
- Captured all three required rationale anchors: CALIB-04 PASS evidence at threshold `175` from soak `20260512T004208Z`, the sufficient fail-closed JSON-file convention, and T17(b)/SEED-005 as the correct home for deeper knob-shape design.
- Ran the L-3 repo-wide audit and confirmed zero unexpected `calib_02_threshold:` YAML-key definitions outside allowed paths.

## Task Commits

Each task was handled atomically:

1. **Task 1: Append HRDN-04 NO entry to CHANGELOG.md** — `6faf791` (`docs`)
2. **Task 2: Repo-wide audit for accidental YAML-key introduction** — audit-only task; no file changes were produced, so no empty task commit was created. The audit result is recorded in this metadata commit.

**Plan metadata:** pending final metadata commit

## Files Created/Modified

- `CHANGELOG.md` — adds the v1.44 HRDN-04 Decisions entry documenting the CALIB-02 YAML-promotion NO route, rationale anchors, and reversibility.

## Verbatim HRDN-04 CHANGELOG Entry

```markdown
### Decisions

- **HRDN-04 (Phase 207): CALIB-02 threshold YAML promotion — NO.** The CALIB-02 D-14-successor watchdog threshold (currently `175`, gate column `by_cause.dwell_hold`) stays in `scripts/calib_02_threshold.json` rather than being promoted to a `continuous_monitoring.upload.calib_02_threshold` YAML key. No autorate validator schema entry is added. No controller-side YAML key is exposed. `scripts/calib_02_threshold.json` is byte-identical at v1.44 close (no value bump, no schema bump).

  **Rationale anchors:**
  - (a) **CALIB-04 PASS at threshold 175.** The v1.43 verification soak `20260512T004208Z` produced a completed-window p99 dwell-hold value of `135.62` against the operator-re-approved threshold `175`, with `primary_gate.verdict = pass` and `secondary_gate_completed_window.verdict = pass`. Recorded in `scripts/calib_02_threshold.json` (operator-approval link: `.planning/phases/204-d-14-successor-recalibration-calib/204-CALIB-02-OPERATOR-APPROVAL.md`) and in v1.43-ROADMAP Plan 204-09.
  - (b) **Fail-closed JSON-file convention is sufficient.** `scripts/soak_summary_aggregate.py::load_calib_02_constants()` already fails closed when the JSON is absent or malformed (threshold=0 fallback). Operators tune the threshold by editing one file, and the operator-approval artifact link is baked into the JSON itself. Premature YAML promotion would lock knob shape (restart-required semantics, validator-schema entry, default-vs-override precedence) before SEED-005 tells us what semantics actually matter operationally.
  - (c) **T17(b) is the right home for deeper schema-design work.** REQUIREMENTS.md "Future Requirements" item `T17(b)` (CALIB-02 YAML knob shape evaluation) is explicitly gated on SEED-005 outcomes (conservative UL tuning sweep). The deeper knob-shape question — restart-required vs hot-reload, validator semantics, default-vs-override precedence — will be answered with SEED-005 data, not anticipated now.

  **Reversibility:** the NO route is fully reversible. If a future milestone routes T17(b) to YES, the JSON convention coexists with a new YAML key as a fallback or migration path — no v1.44 commit is hostile to the eventual YAML promotion.
```

## Verification

- CHANGELOG content gates — PASS:
  - `grep -F "HRDN-04" CHANGELOG.md`
  - `grep -F "CALIB-02 threshold YAML promotion — NO" CHANGELOG.md`
  - `grep -F "20260512T004208Z" CHANGELOG.md`
  - `grep -F "204-CALIB-02-OPERATOR-APPROVAL.md" CHANGELOG.md`
  - `grep -F "T17(b)" CHANGELOG.md`
  - `grep -F "SEED-005" CHANGELOG.md`
- Header preservation — PASS: `grep -cE "^## Unreleased" CHANGELOG.md` produced `1`.
- 207-03 sibling subsection preservation — PASS: `HRDN-03 (Phase 207):` and `removed end-to-end` remain present in `CHANGELOG.md`.
- Byte-identical invariants — PASS:
  - `git diff --exit-code -- scripts/calib_02_threshold.json` exited `0`.
  - `git diff --cached --exit-code -- scripts/calib_02_threshold.json` exited `0`.
  - `git diff --exit-code -- src/wanctl/check_config_validators.py` exited `0`.
  - `git diff --cached --exit-code -- src/wanctl/check_config_validators.py` exited `0`.
- Controller-source invariants — PASS:
  - `git diff --name-only -- src/wanctl/ | wc -l` produced `0`.
  - `git diff --cached --name-only -- src/wanctl/ | wc -l` produced `0`.
- Repo-wide L-3 audit — PASS:
  - `rg "continuous_monitoring\.upload\.calib_02_threshold|calib_02_threshold[[:space:]]*:" --glob '!.planning/**' --glob '!.git/**'` produced only the allowed `CHANGELOG.md` negative reference.
  - YAML-key definition audit excluding planning, git, JSON, and CHANGELOG produced `0` matches.
  - `grep -r "continuous_monitoring.upload.calib_02_threshold" --include="*.yml" --include="*.yaml" --include="*.py" . | wc -l` produced `0`.

## Decisions Made

- Routed HRDN-04 to NO exactly as planned: no YAML key, no validator schema entry, no controller-side config surface.
- Kept T17(b) as the future schema-design container because SEED-005 outcomes should determine the operational knob shape.
- Treated the CHANGELOG negative reference to `continuous_monitoring.upload.calib_02_threshold` as allowed; actual YAML/Python key definitions remain absent.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

- Task 2 was an audit-only task with no expected file edits. No empty commit was created; the audit result is recorded in this SUMMARY metadata commit.

## Known Stubs

None. Stub scan of `CHANGELOG.md` found no TODO/FIXME/placeholder or hardcoded empty UI/data-source stubs.

## Threat Flags

None. This plan introduced no new network endpoints, auth paths, file access patterns, schema changes, or trust-boundary surfaces. It explicitly declined a new YAML/config surface.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Ready for `207-05-PLAN.md`. HRDN-04 is complete, and Phase 207 can proceed to SAFE-09 phase-boundary verification with the CALIB-02 YAML-promotion decision recorded.

## Self-Check: PASSED

- Found `CHANGELOG.md`.
- Found task commit `6faf791` in git log.
- Confirmed `scripts/calib_02_threshold.json` and `src/wanctl/check_config_validators.py` have no worktree or index diff.
- Confirmed both worktree and index `src/wanctl/` diff counts are `0`.
- Confirmed repo-wide YAML-key audit has `0` unexpected matches outside allowed paths.

---
*Phase: 207-soak-harness-hardening-v1-43-closeout-routed*
*Completed: 2026-05-15*
