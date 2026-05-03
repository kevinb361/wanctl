---
phase: 199-obs-02-spec-impl-reconciliation
plan: 01
subsystem: docs
tags: [obs-02, signal-arbitration, sqlite, runbook, subsystems, docs-only]

# Dependency graph
requires:
  - phase: 193-queue-signal-contract-and-arbitration-telemetry
    provides: OBS-01 signal_arbitration field contract; OBS-02 spec row (pre-staged amendment)
  - phase: 195-rtt-confidence-absent-row-test-pin
    provides: tests/test_wan_controller.py absent-row test pin (skip_rtt_confidence_when_none)
provides:
  - docs/SUBSYSTEMS.md signal_arbitration field-shape sub-bullet under wans[]
  - docs/RUNBOOK.md per-cycle SQLite denominator blockquote callout
  - REQUIREMENTS.md OBS-02 wording verified intact (verify-only; no edit)
  - Verbatim spec→doc lockstep on the OBS-02 absent-row phrase (em-dash U+2014 byte-preserved)
affects:
  - 199-02 (consumes files_touched + Observable Truths body for VERIFICATION.md)
  - future audit phases (traceability greps now succeed against SUBSYSTEMS.md and RUNBOOK.md)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Spec-as-source: operator docs quote REQUIREMENTS.md OBS-02 verbatim (D-04) rather than paraphrasing"
    - "Bare > blockquote idiom for operator callouts in RUNBOOK.md (matching existing Pattern A at line 281)"

key-files:
  created: []
  modified:
    - docs/SUBSYSTEMS.md (line 133: new signal_arbitration sub-bullet under wans[] in ## Health And Metrics)
    - docs/RUNBOOK.md (line 373: new > blockquote naming wanctl_arbitration_active_primary as per-cycle denominator)
  verified-only:
    - .planning/REQUIREMENTS.md (line 27: OBS-02 row already pre-staged in commit 2e0211f; zero diff)

key-decisions:
  - "Verify-only on REQUIREMENTS.md (D-01): re-amending would re-open audit-accepted wording"
  - "Em-dash U+2014 byte-preserved by copying from REQUIREMENTS.md:27 directly into edits"
  - "refractory_active intentionally NOT enumerated in SUBSYSTEMS.md sub-bullet (RESEARCH.md Pitfall 5: outside OBS-01 contract)"
  - "Sub-bullet placement under existing wans[] line preserves Major response sections enumeration (D-08: no restructure)"
  - "Bare > blockquote idiom in RUNBOOK.md (no '> Note:' prefix) matches existing Pattern A style"

patterns-established:
  - "Pattern: docs-only phases prove invariant via empty git diff -- src/wanctl/ tests/"
  - "Pattern: spec→doc verbatim quoting with parenthetical 'Per REQUIREMENTS.md OBS-XX' back-reference token"

requirements-completed: [OBS-02]

# Metrics
duration: ~3 min
completed: 2026-05-02
---

# Phase 199 Plan 01: OBS-02 Operator-Doc Reconciliation Summary

**Propagated REQUIREMENTS.md OBS-02 absent-row wording verbatim into docs/SUBSYSTEMS.md (signal_arbitration sub-bullet) and docs/RUNBOOK.md (per-cycle denominator blockquote), closing the v1.40 audit caveat with em-dash U+2014 byte-preservation across all three surfaces.**

## Performance

- **Duration:** ~3 min (verify-only Task 1 + 2 doc edits + verification Task 4)
- **Started:** 2026-05-02T12:02:47Z
- **Completed:** 2026-05-02T12:05:18Z
- **Tasks:** 4 (Task 1 verify-only; Tasks 2 and 3 each one-line content insertions; Task 4 verification-only)
- **Files modified:** 2 (docs/SUBSYSTEMS.md, docs/RUNBOOK.md)
- **Files verified-only:** 1 (.planning/REQUIREMENTS.md — zero diff)

## Accomplishments

- **OBS-02 spec→doc lockstep established.** Both operator-facing docs now quote the OBS-02 absent-row phrase verbatim ("cold-start and invalid-snapshot cycles produce absent SQLite rows and `/health` nulls — no NaN, -1, or sentinel emission") with em-dash U+2014 byte-preserved.
- **SUBSYSTEMS.md `## Health And Metrics`** gained a `signal_arbitration` sub-bullet under `wans[]` enumerating exactly the four OBS-01 contract field names (`active_primary_signal`, `rtt_confidence`, `cake_av_delay_delta_us`, `control_decision_reason`); `refractory_active` deliberately omitted per RESEARCH.md Pitfall 5.
- **RUNBOOK.md `/metrics/history` reader block** gained a `>` blockquote callout naming `wanctl_arbitration_active_primary` as the per-cycle denominator and explaining that absent rows for `wanctl_rtt_confidence` and `wanctl_cake_avg_delay_delta_us` are expected, not data loss.
- **Docs-only invariant proven:** `git diff --name-only "${PHASE_BASE}..HEAD" -- src/wanctl/ tests/` returns empty.
- **Test-pin sanity proven:** `tests/test_wan_controller.py -k skip_rtt_confidence_when_none` passes 1/1 in 0.75s (under 5s budget).

## Task Commits

Each Task with content was committed atomically (no-verify, parallel-worktree convention):

1. **Task 1: Verify REQUIREMENTS.md OBS-02 staged wording** — no commit (verify-only; zero diff). 5/5 anchor phrases (`absent SQLite rows`, `cold-start`, `invalid-snapshot`, `wanctl_arbitration_active_primary`, `amended in Phase 199`) confirmed at .planning/REQUIREMENTS.md:27.
2. **Task 2: Add signal_arbitration field-shape sub-bullet to docs/SUBSYSTEMS.md** — `5c0c7bd` (docs)
3. **Task 3: Add per-cycle denominator note to docs/RUNBOOK.md** — `9be8037` (docs)
4. **Task 4: Plan-01 docs-only invariant + test-pin sanity** — no commit (verification-only). PASS on both gates.

**Plan metadata commit:** issued at end of execution (this SUMMARY + STATE/ROADMAP owned by orchestrator).

## Files Created/Modified

- `docs/SUBSYSTEMS.md` (line 133) — Sub-bullet inserted directly under the existing `wans[]` line in "Major response sections":
  ```
    - `signal_arbitration` (per OBS-01): `active_primary_signal`, `rtt_confidence` (float 0.0–1.0 or `null`), `cake_av_delay_delta_us` (int or `null`), `control_decision_reason`. Per REQUIREMENTS.md OBS-02: cold-start and invalid-snapshot cycles produce absent SQLite rows and `/health` nulls — no NaN, -1, or sentinel emission. See RUNBOOK.md `/metrics/history` for the operator-side denominator note.
  ```
- `docs/RUNBOOK.md` (line 373) — Bare `>` blockquote inserted after the "endpoint-local vs. merged cross-WAN" paragraph and before the per-WAN DB compaction subsection:
  ```
  > Per-cycle SQLite denominator: `wanctl_arbitration_active_primary` is emitted on every CAKE-metrics-enabled cycle and is the reliable denominator for coverage queries against the per-WAN metrics SQLite store. `wanctl_rtt_confidence` and `wanctl_cake_avg_delay_delta_us` are emitted only when valid. Per REQUIREMENTS.md OBS-02: cold-start and invalid-snapshot cycles produce absent SQLite rows and `/health` nulls — no NaN, -1, or sentinel emission. Absent rows for those two metrics are expected, not data loss.
  ```

## Decisions Made

- **D-01 verify-only honored:** REQUIREMENTS.md OBS-02 row left untouched; the audit-accepted wording at line 27 is now mirrored verbatim by the two new operator-doc surfaces.
- **D-04 verbatim quoting:** Both edits copy the OBS-02 absent-row phrase byte-for-byte from REQUIREMENTS.md:27 (not from PATTERNS.md, which renders `--` for hook safety).
- **D-08 no-restructure:** Both edits are minimal in-place insertions; neither file's surrounding section was reorganized.
- **Sub-bullet over `### Signal Arbitration` subsection:** chose the sub-bullet form because the existing Major response sections enumeration is a flat bulleted list — a new heading would have introduced asymmetry.
- **Bare `>` blockquote over `> Note:` prefix in RUNBOOK.md:** matches existing Pattern A style at lines 281–287 (no "Note:" prefix); leading capitalized phrase carries the role.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 — Environment] Used parent project's .venv for Task 4 pytest gate**
- **Found during:** Task 4 (test-pin gate)
- **Issue:** This worktree (`agent-ab04b352038bae254`) has no `.venv/` directory. Plan's verification command (`.venv/bin/pytest ...`) failed with "no such file or directory."
- **Fix:** Invoked the parent project's venv directly (`/home/kevin/projects/wanctl/.venv/bin/pytest ...`). This is a standard parallel-worktree pattern — worktrees share the parent project's venv rather than provisioning their own.
- **Files modified:** none (no source change)
- **Verification:** `1 passed, 201 deselected in 0.75s` (well under 5s budget per RESEARCH.md Pitfall 3)
- **Committed in:** n/a (verification-only task; no content change)

### Note: Prettier-style table reformat in RUNBOOK.md

The PostToolUse formatter normalized markdown table column padding throughout `docs/RUNBOOK.md` during the Task 3 edit, producing 87 insertions / 79 deletions in that commit. The substantive change is exactly the one new `>` blockquote paragraph; the rest is whitespace-only column alignment within existing tables. This is **not a deviation in content** — em-dash bytes preserved, OBS-02 phrase identical to REQUIREMENTS.md:27, and the file's docs-only invariant holds (zero `src/wanctl/` or `tests/` diff). Recorded for transparency: the 87/79 stat would otherwise look out of proportion for a one-paragraph insert.

---

**Total deviations:** 1 environmental adjustment (parent-venv pytest invocation) + 1 cosmetic note (formatter re-wrap of existing tables).
**Impact on plan:** Zero impact on the docs-only invariant or any acceptance criterion. Both items are mechanical/environmental, not scope changes.

## Issues Encountered

- **Worktree branch base mismatch on agent start.** `git merge-base HEAD 413a3444cc...` returned `90a8ffcf...` (the worktree was created from a later commit than expected). Per the executor's worktree_branch_check protocol, performed `git reset --hard 413a3444cc...` to set HEAD to the correct phase base before executing tasks. All subsequent commits land on this corrected base.

## Verification Output

### Task 1 — Anchor phrases in REQUIREMENTS.md
```
FOUND: absent SQLite rows
FOUND: cold-start
FOUND: invalid-snapshot
FOUND: wanctl_arbitration_active_primary
FOUND: amended in Phase 199
```

### Task 2 — SUBSYSTEMS.md acceptance
```
OK: signal_arbitration
OK: active_primary_signal
OK: rtt_confidence
OK: cake_av_delay_delta_us
OK: control_decision_reason
OK: absent SQLite rows
OK: cold-start and invalid-snapshot
OK: Per REQUIREMENTS.md OBS-02
OK: no NaN, -1, or sentinel emission
refractory_active count (must be 0): 0
src/wanctl|tests diff: (empty)
OK: em-dash present
```

### Task 3 — RUNBOOK.md acceptance
```
OK: wanctl_arbitration_active_primary
OK: denominator
OK: absent SQLite rows
OK: cold-start and invalid-snapshot
OK: Per REQUIREMENTS.md OBS-02
OK: no NaN, -1, or sentinel emission
OK: both metric names (wanctl_rtt_confidence + wanctl_cake_avg_delay_delta_us)
src/wanctl|tests diff: (empty)
OK: em-dash present in callout region
```

### Task 4 — Docs-only invariant + test pin
```
git diff --name-only -- src/wanctl/ tests/   →   (empty)   ⇒ PASS
[ -z "$(git diff --name-only -- src/wanctl/ tests/)" ]   ⇒ PASS

pytest -k "skip_rtt_confidence_when_none" -q  →  1 passed, 201 deselected in 0.75s   ⇒ PASS
```

### Em-dash byte-preservation (Python check)
```
python3 -c "assert '—' in open('docs/SUBSYSTEMS.md').read()"   ⇒ PASS
python3 -c "content=open('docs/RUNBOOK.md').read(); assert '—' in content[content.index('denominator'):]"   ⇒ PASS
```

Hex evidence (em-dash U+2014 = `e2 80 94`):
- SUBSYSTEMS.md sub-bullet: `…6e756c6c7320 e28094 206e6f204e614e…` (` nulls — no NaN`)
- RUNBOOK.md blockquote: `…6e756c6c7320 e28094 206e6f204e614e…` (` nulls — no NaN`)
- REQUIREMENTS.md:27 source: same `e28094` byte sequence at the corresponding position.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- **Plan 02 (199-02-PLAN.md) ready to consume.** This SUMMARY's `files_touched` (`docs/SUBSYSTEMS.md`, `docs/RUNBOOK.md`) and the recorded acceptance-grep outputs populate Plan 02's VERIFICATION.md `Observable Truths` body. The `.planning/REQUIREMENTS.md` entry must NOT appear in Plan 02's `files_touched` (verify-only here, per D-06).
- **Audit-trace surfaces in lockstep:** REQUIREMENTS.md OBS-02 ↔ SUBSYSTEMS.md `signal_arbitration` sub-bullet ↔ RUNBOOK.md `>` blockquote. A future Phase 200 traceability check can `grep -F "Per REQUIREMENTS.md OBS-02"` across both doc surfaces and confirm spec→doc fidelity.
- **No blockers.** Test pin still passes; docs-only invariant holds; no Python source change anywhere in the phase.

## Self-Check: PASSED

- `docs/SUBSYSTEMS.md` exists and contains the new sub-bullet at line 133: FOUND
- `docs/RUNBOOK.md` exists and contains the new blockquote at line 373: FOUND
- Commit `5c0c7bd` (Task 2): FOUND in `git log --oneline`
- Commit `9be8037` (Task 3): FOUND in `git log --oneline`
- Em-dash U+2014 byte-preserved in both docs: VERIFIED
- `refractory_active` absent from `docs/SUBSYSTEMS.md`: VERIFIED (count=0)
- Docs-only invariant (zero `src/wanctl/` or `tests/` diff since phase base): VERIFIED

---
*Phase: 199-obs-02-spec-impl-reconciliation*
*Completed: 2026-05-02*
