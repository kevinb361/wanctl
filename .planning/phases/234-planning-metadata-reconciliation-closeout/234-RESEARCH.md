# Phase 234: Planning Metadata Reconciliation + Closeout - Research

**Researched:** 2026-06-11
**Domain:** GSD planning-artifact reconciliation (internal `.planning/` reconnaissance — not external web research)
**Confidence:** HIGH

## Summary

Phase 234 is a pure planning-metadata reconciliation phase. The milestone surface is `scripts/docs/planning/tests` only; **zero `src/wanctl/` controller-path mutation** (SAFE-15). All four success criteria are about making the `.planning/` tree internally consistent and proving an invariant — no production code or config changes.

The reconnaissance resolved every item to concrete on-disk locations and a clear disposition:

- **META-01 (12 orphan quick-task slugs):** They are the 12 directories already physically sitting in `.planning/milestones/quick-archive/`. They are NOT in `.planning/phases/`, so the literal `/gsd-cleanup` workflow (which archives phase dirs) does NOT apply — they are already archived. The real gap is they have no ledger entry and no index. The fix is a `/gsd-cleanup`-*style* sweep: produce an index/manifest (each slug classified shipped-with-SUMMARY vs PLAN-only-no-SUMMARY), record it in the deferred-items ledger, archive-in-place or close-with-pointer, none deleted. `[VERIFIED: filesystem]`
- **META-02 (silicom todos ×2 + SEED-006):** A stale duplicate exists. The two `2026-04-28-add-silicom-bypass-*` todos live in BOTH `.planning/todos/pending/` AND `.planning/todos/completed/`. The `completed/` copies carry a `## Closure — 2026-05-26` footer that consolidated them into SEED-006; the `pending/` copies lack it and still claim pending. SEED-006 cites the `completed/` copies as its canonical sources. Reconciliation: **SEED-006 is the canonical dormant carrier**; the `pending/` duplicates are stale and must be closed-with-pointer to SEED-006 (moved to `closed/`), NOT deleted and NOT false-closed (the underlying bypass-watchdog work is operationally real and deferred to v1.52). `[VERIFIED: filesystem + diff]`
- **META-03 (Phase 230 Nyquist PARTIAL):** Recorded in `milestones/v1.50-phases/230-soak-monitor-att-coverage/230-VALIDATION.md` (`nyquist_compliant: false`, `status: draft`) and in `v1.50-MILESTONE-AUDIT.md`. **The Phase 230 nyquist test file already exists and passes 5/5 right now** (`tests/test_soak_monitor_att_coverage.py`). The PARTIAL was a paperwork gap (VALIDATION.md never flipped to compliant), not a missing-test gap. Both resolution paths are cheap; a **recorded waiver** is the lowest-friction and most honest given the phase is archived and the milestone already shipped — but a retroactive validate is also viable since tests pass. Recommend: **recorded waiver** (see META-03 section for rationale and the retroactive-validate alternative). `[VERIFIED: pytest run]`
- **SAFE-15 (controller-path zero-diff):** The proof is already passing at HEAD right now. The reusable proof is `scripts/phase225-safe13-boundary-check.sh --anchor v1.50 --out <evidence.json>` (read-only, emits JSON with `passed: true`, `controller_path_diff_count: 0`) plus the independent `git diff --quiet v1.50..HEAD -- <protected set>`. Phases 232 and 233 both used this exact pattern; their evidence JSONs are on disk as precedent. `[VERIFIED: git + script]`

**Primary recommendation:** Structure Phase 234 as a small reconciliation plan set (likely 1–2 plans, fine granularity) that (1) indexes + ledgers the 12 quick-archive slugs, (2) closes the 2 stale `pending/` silicom duplicates with SEED-006 pointers, (3) records a Phase 230 Nyquist waiver in `.planning/decisions/` + updates the archived 230-VALIDATION.md frontmatter, and (4) emits the SAFE-15 boundary JSON via the existing script. Every change is reversible doc/metadata; the only "code" touched is committing JSON evidence. Boundary with `/gsd-complete-milestone` is explicit: this phase reconciles metadata and proves SAFE-15; it does NOT run the milestone-close ceremony.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Orphan quick-task resolution (META-01) | Planning metadata (`.planning/milestones/quick-archive/`, `STATE.md` ledger) | — | Pure bookkeeping; slugs already physically archived |
| Silicom todo/SEED reconciliation (META-02) | Planning metadata (`.planning/todos/`, `.planning/seeds/`) | — | Stale-duplicate cleanup; no code/operational change |
| Phase 230 Nyquist resolution (META-03) | Planning metadata (`.planning/decisions/`, archived `230-VALIDATION.md`) | Test suite (already-green) | Waiver is a recorded decision; tests already exist and pass |
| SAFE-15 zero-diff proof | Build/repo invariant (git + evidence JSON) | — | Read-only git inspection; no tier mutation |

## Standard Stack

No external packages installed. This is an internal-tooling phase. The only "stack" is the repo's existing tooling:

| Tool | Version | Purpose | Why Standard |
|------|---------|---------|--------------|
| `scripts/phase225-safe13-boundary-check.sh` | repo-pinned | SAFE-15 controller-path zero-diff proof (read-only git JSON) | Already used for SAFE-13/14/15 at 225/230/232/233 boundaries `[VERIFIED: filesystem]` |
| `scripts/check-cleanup-boundary.sh` | repo-pinned | BOUND-01 denylist guard (optional companion evidence) | Used in 233-04 phase-final evidence `[VERIFIED: filesystem]` |
| `.venv/bin/pytest` | repo-pinned (pyproject.toml) | Confirm Phase 230 tests green for META-03 | Repo standard test runner `[VERIFIED: pytest run]` |
| `gsd-sdk query commit` | installed | Commit doc/evidence changes | GSD repo convention `[VERIFIED: CLAUDE.md]` |

**Installation:** none required.

## Package Legitimacy Audit

Not applicable — this phase installs zero external packages. No `npm`/`pip`/`cargo` additions. The slopcheck gate is moot.

## Architecture Patterns

### System Architecture Diagram

```
Phase 234 reconciliation flow (all read/modify within .planning/, evidence to phase dir)

  ┌─────────────────────────────────────────────────────────────────┐
  │ INPUT: current .planning/ tree (inconsistent metadata)           │
  └─────────────────────────────────────────────────────────────────┘
        │
        ├── META-01 ──► enumerate quick-archive/ (12 dirs)
        │                 │ classify: has-SUMMARY (shipped) vs PLAN-only (005)
        │                 ▼
        │              write index manifest + ledger row in STATE.md
        │                 (archive-in-place; none deleted)
        │
        ├── META-02 ──► detect duplicate: pending/ vs completed/ silicom todos
        │                 │ SEED-006 = canonical (cites completed/ sources)
        │                 ▼
        │              move pending/ duplicates → closed/ with
        │                 frontmatter pointer (closed_by_phase: 234,
        │                 verdict: consolidated_into_SEED-006) — not deleted
        │
        ├── META-03 ──► read archived 230-VALIDATION.md (nyquist_compliant: false)
        │                 │ confirm tests/test_soak_monitor_att_coverage.py green
        │                 ▼
        │              record waiver in .planning/decisions/ + flip
        │                 230-VALIDATION.md frontmatter w/ rationale
        │                 (OR retroactive /gsd-validate-phase 230)
        │
        └── SAFE-15 ──► scripts/phase225-safe13-boundary-check.sh --anchor v1.50
                          │ + git diff --quiet v1.50..HEAD -- <protected set>
                          ▼
                       emit evidence/safe15-boundary-234.json (passed: true)
        │
        ▼
  ┌─────────────────────────────────────────────────────────────────┐
  │ OUTPUT: reconciled .planning/ tree + SAFE-15 boundary evidence   │
  │ (NOT milestone close — that is /gsd-complete-milestone, separate) │
  └─────────────────────────────────────────────────────────────────┘
```

### Component Responsibilities

| File / dir | Role in Phase 234 |
|------------|-------------------|
| `.planning/milestones/quick-archive/*/` | The 12 orphan slugs (already archived in place); META-01 indexes + ledgers them |
| `.planning/todos/pending/2026-04-28-add-silicom-bypass-*.md` | Stale duplicates to close-with-pointer (META-02) |
| `.planning/todos/completed/2026-04-28-add-silicom-bypass-*.md` | Canonical-consolidated copies (already carry Closure footer) — leave as-is |
| `.planning/todos/closed/` | Destination for closed-with-pointer todos (precedent: digest-permission todo) |
| `.planning/seeds/SEED-006-v145-silicom-bypass-tooling-and-harness.md` | Canonical dormant carrier — leave as-is, it is the single source of truth |
| `.planning/milestones/v1.50-phases/230-soak-monitor-att-coverage/230-VALIDATION.md` | Archived; META-03 flips frontmatter if waiver/validate path taken |
| `.planning/decisions/` | Destination for a recorded Nyquist waiver (precedent: phase-224 risk-acceptance) |
| `.planning/STATE.md` | Deferred-items ledger; update all three META rows on resolution |
| `scripts/phase225-safe13-boundary-check.sh` | Reusable SAFE-15 proof generator |
| `.planning/phases/234-.../evidence/` | Destination for SAFE-15 boundary JSON + META manifests |

### Pattern 1: Close-with-pointer todo (META-02 precedent)
**What:** Move a stale `pending/` todo into `closed/`, add frontmatter pointer + a `## Resolution` body section, never delete.
**When to use:** A pending todo whose work was consolidated elsewhere (here: SEED-006).
**Example (verbatim convention from the digest-permission todo just closed by Phase 232):**
```yaml
# .planning/todos/closed/2026-04-28-add-silicom-bypass-nic-operational-tooling.md frontmatter
---
created: 2026-04-28T19:56:51.002Z
title: Add Silicom bypass NIC operational tooling
area: operations
closed_by_phase: 234
verdict: consolidated_into_SEED-006_canonical_dormant_carrier
---
```
```markdown
## Resolution

**Closed by Phase 234 Plan NN (META-02).** This pending todo is a stale duplicate of
`.planning/todos/completed/2026-04-28-add-silicom-bypass-nic-operational-tooling.md`,
which was already consolidated into
`.planning/seeds/SEED-006-v145-silicom-bypass-tooling-and-harness.md` (Phase A) on
2026-05-26. SEED-006 is the single canonical dormant carrier. The underlying
bypass-watchdog work is operationally real (the ATT migration hit a live
bypass-watchdog failure mode) and is NOT false-closed — it remains deferred to
v1.52 scoping under SEED-006. This entry only removes the duplicate pending claim.
```
`[VERIFIED: filesystem — matches closed/2026-04-17-operator-summary-digest-permission-handling.md structure]`

### Pattern 2: SAFE-15 boundary proof (precedent from 232/233)
**What:** Read-only git evidence that the controller path is byte-identical to the `v1.50` anchor.
**When to use:** Phase boundary + milestone close.
**Exact commands (verbatim from 233-04-SUMMARY.md):**
```bash
# Primary evidence (JSON, read-only — no worktree/index/ref mutation):
bash scripts/phase225-safe13-boundary-check.sh \
  --anchor v1.50 \
  --out .planning/phases/234-planning-metadata-reconciliation-closeout/evidence/safe15-boundary-234.json
# Expect JSON: "passed": true, "controller_path_diff_count": 0

# Independent cross-check:
git diff --quiet v1.50..HEAD -- \
  src/wanctl/wan_controller.py \
  src/wanctl/wan_controller_state.py \
  src/wanctl/queue_controller.py \
  src/wanctl/cake_signal.py \
  src/wanctl/alert_engine.py \
  src/wanctl/fusion_healer.py \
  src/wanctl/backends/
# Exit 0 = zero-diff

# Optional companion (BOUND-01 guard, as 233-04 did):
bash scripts/check-cleanup-boundary.sh \
  --out .planning/phases/234-planning-metadata-reconciliation-closeout/evidence/cleanup-boundary-234-final.json
# Expect JSON: "overall_pass": true
```
`[VERIFIED: ran git diff --quiet against HEAD — currently zero-diff; script confirmed read-only]`

### Anti-Patterns to Avoid
- **Running literal `/gsd-cleanup` for META-01:** That workflow archives phase dirs from `.planning/phases/` into `milestones/vX.Y-phases/`. The 12 quick slugs are already in `quick-archive/` and are not phase dirs — running it does nothing useful. META-01 is a *style* match (archive/close-with-pointer, none deleted), not the literal command.
- **Deleting the stale `pending/` silicom duplicates:** META-02 explicitly forbids silent deletion. Close-with-pointer (move to `closed/`).
- **False-closing SEED-006 or the silicom work:** The work is operationally real (live ATT bypass-watchdog failure mode). Reconciliation = single canonical state, NOT "done."
- **Touching `src/wanctl/`:** SAFE-15. The only files this phase writes are under `.planning/`, plus committing evidence JSON. If any `src/wanctl/` file shows in `git status`, the phase has failed its own invariant.
- **Re-running Phase 230 tests as if reproving the phase:** META-03 only needs the PARTIAL *resolved* (waiver or validate). Confirming tests are green is sufficient evidence for the waiver rationale.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| SAFE-15 zero-diff proof | A new bespoke git-diff script | `scripts/phase225-safe13-boundary-check.sh --anchor v1.50` | Already produces the canonical JSON shape (`passed`, `controller_path_diff_count`, per-file blob hashes), already used at 225/230/232/233 boundaries `[VERIFIED: filesystem]` |
| Close-with-pointer todo format | Invent a new frontmatter schema | Copy `closed/2026-04-17-operator-summary-digest-permission-handling.md` pattern | Phase 232 just established it for an identical "validated-elsewhere → close" case `[VERIFIED: filesystem]` |
| Recorded waiver format | Invent a decision-doc layout | Copy `decisions/phase-224-clean-restart-risk-acceptance.md` pattern (Symptom / Disposition / Override Path / Sign-Off) | Existing decisions/ convention with operator sign-off block `[VERIFIED: filesystem]` |
| Deferred-items ledger | New tracking file | Update the existing table in `STATE.md` "Deferred Items" section | The ledger the orchestrator already reads `[VERIFIED: filesystem]` |

**Key insight:** Every artifact this phase needs (proof script, close-with-pointer schema, waiver schema, ledger table) already exists in-repo from prior phases. The phase is assembly, not construction.

## Runtime State Inventory

> This is a planning-metadata phase, not a rename/refactor of running systems. But because META-02/03 touch state that could be read by tooling, the categories are answered explicitly.

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | None — no database, datastore, or runtime keys reference the reconciled artifacts. The silicom work is dormant (SEED-006); no live service depends on the pending-todo state. Verified by: META items are all `.planning/` markdown. | none |
| Live service config | None — no n8n/Datadog/Tailscale/Cloudflare config references these slugs/todos/seeds. The SAFE-15 invariant is precisely that no live controller config changes. Verified by: scope is `.planning/` + evidence JSON only. | none |
| OS-registered state | None — no Task Scheduler/pm2/systemd unit embeds a quick-task slug or todo name. The silicom *systemd units* named in SEED-006 are `(planned)`, not deployed (the work is deferred). Verified by: SEED-006 marks all units `(planned)`. | none |
| Secrets/env vars | None — no secret key or env var references these planning artifacts. | none |
| Build artifacts / installed packages | None — no egg-info/binary/global install carries these names. No package rename. | none |

**Nothing found in any category** — verified: every Phase 234 surface is `.planning/` markdown plus read-only git evidence; there is no runtime system holding the old state.

## Common Pitfalls

### Pitfall 1: Treating the 12 slugs as deletable junk
**What goes wrong:** Bulk-deleting `quick-archive/` to "clean up."
**Why it happens:** They look like stale completed work.
**How to avoid:** META-01 requires "archived or closed with pointer, none silently deleted." They are already archived-in-place; the deliverable is an *index + ledger entry*, not removal. Note 11 of 12 are git-untracked (only `260503-cfs` is tracked) — deletion would be invisible to git for those 11, which is exactly why "none deleted" matters.
**Warning signs:** Any `rm` or `git rm` touching `quick-archive/`.

### Pitfall 2: Deleting instead of close-with-pointer for silicom duplicates
**What goes wrong:** `rm` the `pending/` silicom todos.
**Why it happens:** They are duplicates; deletion feels clean.
**How to avoid:** META-02 forbids silent deletion and forbids false-closing. Move `pending/ → closed/` with a SEED-006 pointer and a `verdict: consolidated_into_SEED-006`.
**Warning signs:** `pending/` count drops with no corresponding `closed/` entry.

### Pitfall 3: Picking the wrong canonical carrier for META-02
**What goes wrong:** Marking the `pending/` todos canonical and re-deriving SEED-006 from them.
**Why it happens:** Ambiguity about which is the source of truth.
**How to avoid:** SEED-006 is canonical — it cites the `completed/` copies as its sources, has `status: dormant`, and is the v1.52 carrier per ROADMAP backlog + STATE ledger. The `pending/` copies are the stale ones (they lack the 2026-05-26 Closure footer the `completed/` copies have).
**Warning signs:** Editing SEED-006 content (it should be left as-is, only referenced).

### Pitfall 4: Over-engineering META-03 by re-running validate-phase machinery on an archived phase
**What goes wrong:** Spawning the nyquist-auditor agent against `milestones/v1.50-phases/230-*` and regenerating tests that already exist and pass.
**Why it happens:** "Resolve PARTIAL" reads as "must run /gsd-validate-phase."
**How to avoid:** The success criterion offers two paths and a waiver is explicitly acceptable. The tests already pass (5/5 today). A recorded waiver citing the green tests is the lowest-friction honest resolution. If validate-phase is preferred, it is still cheap because no gaps need filling — it just flips `nyquist_compliant: true`.
**Warning signs:** New test files being generated for a shipped, archived phase.

### Pitfall 5: Conflating Phase 234 with milestone close
**What goes wrong:** Running `/gsd-complete-milestone` ceremony inside Phase 234.
**Why it happens:** Phase 234 is the "closeout" phase.
**How to avoid:** Phase 234 *reconciles metadata and proves SAFE-15 at the phase boundary + a milestone-close SAFE-15 proof*. The actual milestone-completion ceremony (audit, acknowledge, ship, tag) is `/gsd-complete-milestone`, run after Phase 234 verifies. Keep the boundary explicit in the plan.
**Warning signs:** Plan tasks editing ROADMAP milestone status to ✅, creating a `v1.51-MILESTONE-AUDIT.md`, or tagging `v1.51`.

## Code Examples

### Confirm Phase 230 tests green (META-03 waiver evidence)
```bash
# Source: tests/test_soak_monitor_att_coverage.py (exists on disk)
.venv/bin/pytest tests/test_soak_monitor_att_coverage.py -q -o addopts=''
# Observed 2026-06-11: "5 passed in 0.49s"
```
`[VERIFIED: ran]`

### SAFE-15 proof at milestone close
```bash
# Source: 233-04-SUMMARY.md verbatim invocation
bash scripts/phase225-safe13-boundary-check.sh --anchor v1.50 \
  --out .planning/phases/234-planning-metadata-reconciliation-closeout/evidence/safe15-boundary-234.json
python3 -c "import json;d=json.load(open('.planning/phases/234-planning-metadata-reconciliation-closeout/evidence/safe15-boundary-234.json'));print('passed',d['passed'],'diff',d['controller_path_diff_count'])"
# Expect: passed True diff 0
```
`[VERIFIED: script confirmed read-only; HEAD currently zero-diff vs v1.50]`

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| SAFE-07 source-diff via `scripts/check-safe07-source-diff.sh` | `scripts/phase225-safe13-boundary-check.sh` (per-file blob hashes, JSON evidence, fail-closed on add/delete) | Phase 225 (v1.49) | Use the 225 script with `--anchor v1.50`; it is the established SAFE-13/14/15 proof |
| Todos tracked only in `pending/`/`completed/`/`done/` | `closed/` dir with `closed_by_phase`/`verdict` frontmatter for validated-elsewhere closures | Phase 232 (v1.51) | Use `closed/` + pointer for META-02 |

**Deprecated/outdated:**
- `scripts/check-safe07-source-diff.sh` — superseded for boundary proofs by `phase225-safe13-boundary-check.sh` (still present; not what 232/233 used).

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | A recorded waiver (vs retroactive validate) is the preferred META-03 path | META-03 / Summary | Low — both paths satisfy the criterion; operator may prefer validate. Plan should offer both as a discuss-phase choice. |
| A2 | "12 orphan quick-task slugs" == the 12 dirs in `quick-archive/` | META-01 | Low — count matches exactly (12), STATE ledger says "12 orphan quick-task slugs from older milestones," and `quick-archive/` is the only quick-task location on disk. If the orchestrator means a different registry, re-confirm in discuss. |
| A3 | Milestone-close ceremony (`/gsd-complete-milestone`) is out of Phase 234 scope | Summary / Pitfall 5 | Low — phase description explicitly says "metadata reconciled and SAFE-15 proven"; flagged as a boundary to confirm with operator. |

## Open Questions

1. **META-03: waiver vs retroactive validate-phase — operator preference?**
   - What we know: Phase 230 tests exist and pass 5/5; VALIDATION.md frontmatter is `nyquist_compliant: false`/`status: draft`; the phase is archived under `milestones/v1.50-phases/`.
   - What's unclear: Whether the operator wants the audit trail of a retroactive `/gsd-validate-phase 230` (flips frontmatter to compliant, appends a Validation Audit row) or a lighter recorded waiver in `.planning/decisions/`.
   - Recommendation: Default to a recorded waiver citing the green tests; offer retroactive-validate as the alternative in discuss-phase. Both are cheap; waiver is lower-ceremony and honest about the phase being shipped/archived.

2. **META-01: index manifest location + format?**
   - What we know: Convention is to record dispositions in evidence JSON/MD under the phase dir and update the `STATE.md` ledger.
   - What's unclear: Whether to also drop an `INDEX.md` inside `quick-archive/` itself.
   - Recommendation: Write a per-slug manifest (`evidence/quick-archive-index.{md,json}`) classifying each as shipped (has SUMMARY) vs PLAN-only (`005`, no SUMMARY), update the STATE ledger row, and optionally add a short `quick-archive/INDEX.md`. Decide in discuss.

3. **META-03 frontmatter edit on an archived phase — allowed?**
   - What we know: `230-VALIDATION.md` lives under `milestones/v1.50-phases/` (archived, but git-tracked).
   - What's unclear: Whether the operator wants the archived artifact mutated or prefers the waiver to live only in `decisions/` + STATE, leaving the archive immutable.
   - Recommendation: Prefer recording resolution in `decisions/` + STATE and adding a one-line pointer note to `230-VALIDATION.md` rather than rewriting archived history. Confirm in discuss.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| git (annotated tag `v1.50`) | SAFE-15 anchor | ✓ | tag → `00924077` (peeled commit `d7771ed1`) | — |
| `scripts/phase225-safe13-boundary-check.sh` | SAFE-15 proof | ✓ | repo-pinned, read-only | direct `git diff --quiet` cross-check |
| `.venv/bin/pytest` | META-03 evidence | ✓ | repo pyproject.toml | — |
| `python3` | JSON evidence verification | ✓ | system | — |
| `scripts/check-cleanup-boundary.sh` | optional BOUND-01 companion | ✓ | repo-pinned | omit (not required for META-01..03) |

**Missing dependencies with no fallback:** none.
**Missing dependencies with fallback:** none.

> Note: `git rev-parse v1.50` returns the annotated-tag object SHA `00924077` (this is what the proof script records as `baseline_commit`), while `git rev-parse v1.50^{commit}` peels to `d7771ed1`. The script's `git rev-parse v1.50:<path>` resolves the tree correctly through the tag, so diffs are accurate — confirmed zero-diff at HEAD. This is expected behavior and matches the 232/233 evidence JSONs exactly; do not "fix" it.

## Validation Architecture

> Nyquist validation is enabled (`workflow.nyquist_validation: true`). Each success criterion has an objective, automatable check.

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (repo-pinned, `pyproject.toml` `[tool.pytest.ini_options]`) |
| Config file | `pyproject.toml` |
| Quick run command | `.venv/bin/pytest tests/test_soak_monitor_att_coverage.py -q -o addopts=''` |
| Full suite command | `.venv/bin/pytest tests/ -q` |

> Known full-suite noise: 21–23 pre-existing Phase 220/221 boundary tests fail because they refuse committed `src/wanctl/` drift since `PHASE214_BASE_SHA`. These are documented historical failures (STATE.md decision [233-04]) unrelated to Phase 234. As in 233-04, full-suite-green may be operator-waived; SAFE-15 + META evidence are the binding gates. Phase 234 adds ZERO `src/wanctl/` changes, so it cannot worsen this count.

### Phase Requirements → Validation Map
| Req ID | Behavior to prove | Validation type | Automated/assertable command | Artifact exists? |
|--------|-------------------|-----------------|------------------------------|------------------|
| META-01 | 12 quick-archive slugs each archived/closed-with-pointer, none deleted; ledger reflects resolved state | file assertions | `test $(ls -d .planning/milestones/quick-archive/*/ \| wc -l) -eq 12` AND grep the new index manifest lists all 12 AND `git status --porcelain .planning/milestones/quick-archive/` shows no deletions | ✅ (slugs on disk; manifest to be written) |
| META-02 | No silicom todo simultaneously in `pending/` and `completed/`; `pending/` duplicates moved to `closed/` with SEED-006 pointer; SEED-006 unchanged | file assertions | `test ! -e .planning/todos/pending/2026-04-28-add-silicom-bypass-nic-operational-tooling.md` AND `test ! -e .planning/todos/pending/2026-04-28-add-silicom-bypass-test-harness.md` AND `grep -q 'closed_by_phase: 234' .planning/todos/closed/2026-04-28-add-silicom-bypass-*.md` AND `grep -q 'consolidated_into_SEED-006\|SEED-006' .planning/todos/closed/2026-04-28-add-silicom-bypass-*.md` AND `git diff --quiet -- .planning/seeds/SEED-006-v145-silicom-bypass-tooling-and-harness.md` | ✅ (dupes on disk; `closed/` convention exists) |
| META-03 | Phase 230 Nyquist PARTIAL resolved (waiver recorded OR validate executed) with rationale | file assertion + test green | Waiver path: `test -e .planning/decisions/phase-230-nyquist-waiver.md` (or named equiv) AND it cites green tests; Validate path: `grep -q 'nyquist_compliant: true' .planning/milestones/v1.50-phases/230-soak-monitor-att-coverage/230-VALIDATION.md`. Supporting evidence either path: `.venv/bin/pytest tests/test_soak_monitor_att_coverage.py -q -o addopts=''` → 5 passed | ✅ (tests pass today) |
| SAFE-15 | Controller-path zero-diff at phase boundary AND milestone close | git + JSON assertion | `bash scripts/phase225-safe13-boundary-check.sh --anchor v1.50 --out .planning/phases/234-.../evidence/safe15-boundary-234.json` then assert JSON `passed==true && controller_path_diff_count==0`; independent `git diff --quiet v1.50..HEAD -- <protected set>` exits 0 | ✅ (script exists; passes at HEAD now) |

### Sampling Rate
- **Per task commit:** for the SAFE-15-bearing task, re-run the boundary script + `git status --porcelain -- src/wanctl/` (must be empty). For META tasks, the per-criterion file assertions above (sub-second).
- **Per wave/phase merge:** full assertion set for all four criteria; emit SAFE-15 JSON.
- **Phase gate / milestone close:** SAFE-15 JSON `passed: true` + `git diff --quiet v1.50..HEAD` exit 0, recorded in `evidence/`.

### Wave 0 Gaps
- None for test infrastructure — `tests/test_soak_monitor_att_coverage.py` already exists and passes; no new tests needed (this phase writes metadata + evidence, not testable `src/` behavior).
- New artifacts to *create* (not test gaps): the META-01 index manifest, the two META-02 `closed/` pointer todos, the META-03 waiver/validate record, and the SAFE-15 evidence JSON.

## Security Domain

> `security_enforcement` is not set in config (treat as enabled), but this phase touches no auth, no input handling, no crypto, no network, no data flow. It edits planning markdown and runs read-only git inspection.

### Applicable ASVS Categories
| ASVS Category | Applies | Standard Control |
|---------------|---------|------------------|
| V2 Authentication | no | — |
| V3 Session Management | no | — |
| V4 Access Control | no | — |
| V5 Input Validation | no | No external/user input processed |
| V6 Cryptography | no | git blob SHAs are integrity refs, not crypto this phase manages |

### Known Threat Patterns
| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Accidental controller-path mutation masquerading as metadata edit | Tampering | SAFE-15 zero-diff proof + `git status --porcelain -- src/wanctl/` gate fail-closed |
| Silent loss of operationally-real work (false-close SEED-006) | Repudiation / data loss | META-02 close-with-pointer (no delete, no false-close); SEED-006 left canonical |
| Silent deletion of orphan slugs (11/12 untracked → invisible to git) | Tampering / data loss | META-01 "none deleted"; assert no removals in `git status` + filesystem count stays 12 |

## Project Constraints (from CLAUDE.md)

- **Production network control system — change conservatively.** This phase is metadata-only; it satisfies that by construction (SAFE-15).
- **Never refactor core logic/algorithms/thresholds/timing without approval.** N/A — zero `src/wanctl/` changes.
- **Priority: stability > safety > clarity > elegance.** Reconciliation must not introduce risk; close-with-pointer over delete.
- **MANDATORY before every commit: run `project-finalizer` agent.** Plan must route commits through project-finalizer (per `~/CLAUDE.md` git workflow); evidence/doc commits are still subject to the pre-commit doc hook.
- **Use the virtualenv directly** (`.venv/bin/pytest`, etc.) — not a global interpreter.
- **`commit_docs: true`** in config — research/plan/evidence docs get committed via `gsd-sdk query commit`.
- **Public-safe docs:** no secrets, IPs, hostnames in committed planning docs (this file already follows that).

## Sources

### Primary (HIGH confidence)
- `.planning/REQUIREMENTS.md` — META-01/02/03, SAFE-15 definitions + Out-of-Scope binding table
- `.planning/ROADMAP.md` — Phase 234 success criteria, backlog (SEED-006 v1.52 carrier), SAFE-15 cross-phase note
- `.planning/STATE.md` — deferred-items ledger (the three META rows), SAFE baseline decisions [232/233]
- `.planning/milestones/quick-archive/` (12 dirs) — the META-01 orphan slugs, classified by SUMMARY presence
- `.planning/todos/{pending,completed,closed}/` — META-02 duplicate detection + close-with-pointer precedent
- `.planning/seeds/SEED-006-v145-silicom-bypass-tooling-and-harness.md` — canonical carrier; cites `completed/` sources
- `.planning/milestones/v1.50-phases/230-soak-monitor-att-coverage/{230-VALIDATION.md,deferred-items.md,230-SAFE14-BOUNDARY.md}` — META-03 PARTIAL record + SAFE proof precedent
- `.planning/milestones/v1.50-MILESTONE-AUDIT.md` — Nyquist PARTIAL audit row, closeout convention
- `.planning/phases/{232,233}-.../evidence/safe15-boundary-{232,233}.json` — exact SAFE-15 evidence shape
- `.planning/phases/233-.../233-04-SUMMARY.md` — exact SAFE-15 proof invocation + full-suite waiver precedent
- `.planning/decisions/phase-224-clean-restart-risk-acceptance.md` — recorded-decision/waiver format precedent
- `$HOME/.claude/get-shit-done/workflows/{cleanup,validate-phase}.md` — what the referenced commands actually do
- `scripts/phase225-safe13-boundary-check.sh` — reusable SAFE-15 proof generator (read-only confirmed)
- Live tool output: `git diff --quiet v1.50..HEAD -- <protected set>` (zero-diff), `pytest tests/test_soak_monitor_att_coverage.py` (5 passed), `git ls-files quick-archive/` (11/12 untracked)

### Secondary (MEDIUM confidence)
- none required — all claims verified against on-disk artifacts or live tool runs

### Tertiary (LOW confidence)
- none

## Metadata

**Confidence breakdown:**
- META-01 (orphan slugs): HIGH — exact 12 dirs located, classified, tracking status confirmed
- META-02 (silicom/SEED reconciliation): HIGH — duplicate confirmed via diff, canonical carrier identified, close-with-pointer precedent on disk
- META-03 (Phase 230 Nyquist): HIGH — PARTIAL record located, tests confirmed green live, both resolution paths verified cheap
- SAFE-15: HIGH — proof script confirmed read-only, ran the diff, currently zero-diff vs v1.50, 232/233 evidence precedent on disk
- Validation architecture: HIGH — every criterion has a runnable file/git assertion

**Research date:** 2026-06-11
**Valid until:** 2026-06-25 (stable internal-metadata domain; only invalidated by new commits touching `.planning/` or `src/wanctl/` before planning)
