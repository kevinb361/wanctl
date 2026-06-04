---
phase: 226
reviewers: [codex]
reviewed_at: 2026-06-04T12:29:00Z
review_cycles: 3
plans_reviewed: [226-01-PLAN.md, 226-02-PLAN.md, 226-03-PLAN.md, 226-04-PLAN.md, 226-05-PLAN.md]
cycle_1:
  reviewed_at: 2026-06-04T05:43:07Z
  high_raised: 5
cycle_2:
  reviewed_at: 2026-06-04T06:00:04Z
  revision_commit: 4dec9a9
  high_unresolved: 0
  high_new: 0
cycle_3:
  reviewed_at: 2026-06-04T12:29:00Z
  scope: 226-05-PLAN.md (gap-closure)
  plan_commit: cc35e96
  high_raised: 2
  high_unresolved: 2
---

# Cross-AI Plan Review — Phase 226

Reviewer set: Codex (`codex exec`, CLI default model). Running inside Claude Code, so the
Claude CLI was skipped for independence per the review workflow's self-CLI rule.

---

# Review Cycle 3 (current) — 2026-06-04T12:29:00Z

**Scope:** ONLY the gap-closure plan `226-05-PLAN.md` (commit `cc35e96`). Plans 226-01..04 are
already executed and were reviewed in cycles 1–2; they were excluded from this cycle.
**Mandate:** Adversarially review whether 226-05 actually closes the two FAILED must-haves
(AB-02 baseline evidence, GATE-01 threshold lock) without breaking SAFE-13. Codex read the broken
parser, the real retained `tc` evidence, the thresholds JSON, and the verification gaps directly.

## Codex Review (Cycle 3)

**Summary** — The plan targets the right root cause and should make the retained real CAKE evidence
parse correctly: the real file uses `pk_delay`/`av_delay`/`backlog`/`pkts`/`drops`, and the current
parser returns zeroes. Actual retained data should produce positive spreads (`spec-router`:
~0.105 ms, `spec-modem`: ~24.206 ms). SAFE-13 is likely preserved via the existing boundary script.
As written, though, the plan has two material gaps: it does not refresh `artifact-sha256.txt` after
regenerating tracked evidence, and its Task 1 inline import verify command is broken in this
environment.

**Strengths**

- Correct diagnosis: `parse_tc_qdisc()` only matches synthetic labels today, and real retained CAKE
  rows are ignored.
- Regex direction is basically sound if implemented as exact, line-anchored lowercase per-tin labels.
- Uses retained raw evidence only; no live recapture or candidate data, so pre-registration is preserved.
- `_spread()` reasoning is correct for this retained baseline: it uses the three `during`
  `avg_delay_ms` values, not before/during deltas.
- `NOISE_BAND_MS` SHA provenance is not circular: `thresholds.json` hashes `baseline-summary.json`;
  the summary does not depend on `thresholds.json`.

**Concerns**

- **HIGH:** `artifact-sha256.txt` is omitted from `files_modified` and Task 3. It currently records
  hashes for `baseline-summary.json` and `BASELINE-SUMMARY.md`. Regenerating either file makes the
  baseline evidence hash manifest stale, undermining the "retained evidence" provenance story even if
  `thresholds.json` points at the new summary hash.
- **HIGH:** Task 1's verify command imports the dataclass module via
  `importlib.util.module_from_spec()` but does not insert it into `sys.modules`. In this environment
  it fails before parsing with `AttributeError` from `dataclasses`. The test file does this correctly
  by assigning `sys.modules["phase226_baseline_summary"] = summary`.
- **MEDIUM:** Task 1/2 acceptance does not actually prove `backlog` or `pk_delay` parsing. The Task 1
  verify target, `run-01/tc-qdisc-spec-router.during.txt`, has per-tin `backlog 0b`, so it cannot
  prove non-zero backlog parsing. The inline regression should assert `backlog_bytes` and
  `peak_delay_ms`; the retained-evidence test should parse `spec-modem.during` for positive backlog.
- **MEDIUM:** The plan's `> 0` acceptance for `tin_queue_delay_spread_ms` is valid for this retained
  evidence, but not a general invariant. A correct parse could legitimately yield `0.0` if all three
  `av_delay` samples are identical. The plan should either lock expected values for this evidence set
  or state the policy for valid zero/near-zero spread.
- **MEDIUM:** SAFE-13 relies on the comprehensive boundary script (good), but the extra `git diff`
  command is narrower than SAFE-13: it omits `fusion_healer.py`, `src/wanctl/backends/`, and
  `configs/att.yaml`. The "full change set is limited to…" criterion is stated but not automated.
- **LOW:** The existing fixture `tc-qdisc.before.txt` mixes real rows and synthetic rows with
  conflicting packet values. If the executor interprets "real-format branch is authoritative" as
  "synthetic fallback must not overwrite parsed real fields," existing tests will fail. Clarify
  precedence or add isolated real-only fixtures.
- **LOW:** Overwriting a tracked derived evidence artifact is acceptable here, but the plan should
  explicitly document that only derived summaries were corrected from unchanged raw evidence.
  Otherwise it looks like retroactive evidence mutation rather than corrected derivation.

**Suggestions**

- Add `artifact-sha256.txt` to `files_modified`; regenerate it after `baseline-summary.json` and
  `BASELINE-SUMMARY.md`, excluding `artifact-sha256.txt` itself as the capture script does.
- Add a verify step equivalent to `sha256sum -c artifact-sha256.txt` or a targeted check for the
  regenerated summary/Markdown hashes.
- Fix the Task 1 import command by inserting the module into `sys.modules` before `exec_module()`.
- Add assertions for `backlog_bytes`/`peak_delay_ms` from `run-01/tc-qdisc-spec-modem.during.txt`
  (non-zero backlog), or equivalent inline real-only data.
- Add an allowed-list check for the final change set, not just SAFE-13 paths.
- In `226-05-SUMMARY.md`, record old invalid summary hash `186f4a72...`, new summary hash, and
  "raw run artifacts unchanged."

**Risk Assessment** — **MEDIUM.** The core parser/threshold fix is straightforward and should close
AB-02 + GATE-01 for the retained evidence, and SAFE-13 should hold. The stale artifact hash manifest
and broken verify command are real execution/provenance gaps that should be fixed before running the
plan.

`UNRESOLVED_HIGH_COUNT: 2`

## Cycle 3 Verdict

- **HIGHs raised (226-05):** 2 — both UNRESOLVED in the current plan text.
  1. `artifact-sha256.txt` not refreshed after regenerating tracked evidence (provenance staleness).
  2. Task 1 verify command missing `sys.modules` insertion → fails before parsing (false-fail gate).
- **MEDIUMs:** 4 (backlog/pk_delay not actually proven; `>0` spread not a general invariant; SAFE-13
  git-diff narrower than full protected set; change-set allowlist stated but not automated).
- **LOWs:** 2 (mixed real/synthetic fixture precedence; document derived-only correction).
- **Recommendation:** fold the 2 HIGHs (and ideally the backlog/pk_delay + SAFE-13-diff MEDIUMs)
  before executing 226-05, via `/gsd:plan-phase 226 --reviews`.

---

# Review Cycle 2 (history) — 2026-06-04T06:00:04Z

**Trigger:** Plans revised in commit `4dec9a9` to address the 5 HIGH concerns from cycle 1.
**Mandate:** Verify whether the 5 cycle-1 HIGHs are now resolved AND whether the revision
introduced any new HIGH concern. Only HIGHs that remain UNRESOLVED in the *current* plan state count.

## Codex Review (Cycle 2)

**Summary** — The revision resolves all five prior HIGH concerns in the plan text. Ordering is now
explicit, 226-03 has a real data dependency and fill step, the contradictory grep gates were
rewritten, continuous health/state evidence is required, and `tc -s qdisc` parsing is now delta-based
with fixture tests.

**Prior HIGH Disposition**

- **HIGH#1: FULLY RESOLVED** — 226-02 is Wave 1 with no deps; 226-01 is Wave 2 and `depends_on: 226-02`, explicitly because flent mutates qdisc/controller state before the anchor.
- **HIGH#2: FULLY RESOLVED** — 226-03 is Wave 3 and `depends_on: 226-01`; Task 3 fills `NOISE_BAND_MS.value` from `baseline-summary.json` and requires it committed before Phase 227 (a null placeholder is explicitly not a locked artifact).
- **HIGH#3: FULLY RESOLVED** — redaction validators now allow secret keys whose value is `REDACTED`/empty/null, and mutation checks are scoped to executed paths or comment-safe grep.
- **HIGH#4: FULLY RESOLVED** — 226-01 requires continuous `health.window.ndjson` across each run and summary output for `restart_rate`, `transition_rate`, `floor_hit_cycles`, and `soft_red_dwell_s`.
- **HIGH#5: FULLY RESOLVED** — 226-01 requires before/during/after qdisc samples and computes per-run deltas as `during - before`, with pytest fixture guards before live capture.

**New Concerns**

- **MEDIUM** — 226-03 prose says the noise-band constant is derived from "Snapshot A baseline 3-run spread" and "filled at Snapshot-A time" (Task 2), while the actual dependency/source is the **226-01 baseline evidence** (`baseline-summary.json`). The surrounding plan and `depends_on: 226-01` make the true source clear, so this does not block execution — but the wording should be corrected to avoid executor confusion.
- **LOW** — Several greps still rely on human interpretation for heredoc/printf text vs executed commands. The plans call this out, so it is acceptable, but the automated verification needs careful implementation.

**Risk Assessment** — **LOW.** The prior blocking issues are addressed structurally in dependencies,
task order, acceptance criteria, and tests. Remaining risk is mostly wording/verification brittleness,
not plan-blocking behavior.

`UNRESOLVED_HIGH_COUNT: 0`

## Cycle 2 Verdict

- **Cycle-1 HIGHs resolved:** 5 / 5 (all FULLY RESOLVED).
- **New HIGHs introduced by the revision:** 0.
- **Unresolved HIGH count (this cycle):** **0.**
- Residual items: 1 MEDIUM (226-03 wording: cite 226-01 baseline-summary.json as the noise-band
  source, not "Snapshot A / Snapshot-A time") + 1 LOW (heredoc-vs-executed grep brittleness). Neither
  is execution-blocking; fold opportunistically.

Convergence reached — no HIGH concerns remain. Phase 226 plans are clear to execute.

---

# Review Cycle 1 (history) — 2026-06-04T05:43:07Z

## Codex Review

## Summary

The phase shape is mostly right: no candidate deploy, Spectrum-only, Snapshot A + baseline + locked gates + SAFE-13 boundary. The plans are conservative in intent, but not yet safe to execute as written. Main problems are dependency ordering, impossible acceptance greps, under-specified baseline metrics for later gates, and overclaiming what the dry-run restore proves. Fix those before execution.

## Strengths

- Clear phase boundary: baseline/anchor/thresholds only; Phase 227 owns candidate `diffserv4 wash`.
- Good reuse of known precedents: `phase224-snapshot-a.sh`, `phase198`, `phase213`, `phase225-safe13-boundary-check.sh`.
- Redacted committable evidence vs operator-private raw restore artifacts is the right split.
- SAFE-13 is treated as a phase-boundary invariant, not a vague "don't touch source" note.
- GATE-01 threshold lock has the right intent: machine-readable JSON as source of truth.
- Live restore drill is correctly rejected for this phase.

## Concerns

- **HIGH: Wave ordering is unsafe.** Snapshot A should run before any baseline load generation. 226-01 and 226-02 are both Wave 1 with no dependency, but baseline flent traffic changes qdisc counters, controller rates/state, logs, and metrics. Run Snapshot A first.

- **HIGH: 226-03 depends on 226-01 but does not declare it.** The tin-separation noise band depends on `baseline-summary.json` `tin_queue_delay_spread_ms`. A placeholder JSON is not a fully locked threshold artifact unless there is a second "fill derived constant" step before Phase 227.

- **HIGH: Several acceptance greps are impossible as written.** 226-01 requires manifest/config text containing `diffserv` and `allow_wash`, then greps for those words as forbidden. 226-02 redacted YAML will likely contain `password: REDACTED`, while acceptance greps for `password|secret|token` returning no lines.

- **HIGH: Baseline capture does not collect enough continuous state for GATE-01.** Pre/during/post `/health` snapshots are not enough for restart rate, transition rate, floor-hit-cycle deltas, or SOFT_RED dwell. It needs a windowed health NDJSON or metrics query around each run.

- **HIGH: `tc -s qdisc` counters need delta semantics.** Packets/drops are cumulative since qdisc creation. The summary plan parses `.during.txt` directly; it should compute per-run deltas from before/during/after or the numbers will be polluted by prior traffic.

- **MEDIUM: Unmarked UDP/TCP reference flows are under-specified.** The plan does not say whether they run concurrently with RRUL or sequentially, what tool generates them, what host/ports they use, how DSCP neutrality is verified, or what schema Phase 228 consumes.

- **MEDIUM: GATE-01 can still be baseline-cherry-picked.** A derived noise band is acceptable only if the first valid baseline run is retained and invalid-run criteria are objective. Otherwise rerunning until the spread is convenient becomes a pre-registration loophole.

- **MEDIUM: Snapshot restore proof overclaims.** Dry-run can prove raw config equality and command identity. It cannot prove runtime qdisc restoration, sudo/install permissions at rollback time, service reload behavior, or qdisc reapplication without a live drill.

- **MEDIUM: 226-04 should depend on all prior plans.** SAFE-13 boundary evidence and "no candidate deploy" summary should be final-phase evidence, not merely "after snapshot".

- **MEDIUM: Mutation-capable restore path is unnecessary in Phase 226.** Implementing `--apply` now increases risk. Prefer dry-run-only in 226; add apply behavior in Phase 228.

- **LOW: Raw-dir containment should resolve symlinks.** The precedent uses `abspath`; for operator-private safety, use `realpath`/`Path.resolve()`.

## Suggestions

- Make execution order explicit: `226-02 -> 226-01 -> 226-03 -> 226-04`.
- Split 226-03 into rule lock and baseline-derived constant fill, both committed before Phase 227.
- Replace broad forbidden-word greps with command-aware checks, and replace secret greps with a redaction validator that allows `REDACTED`.
- Add per-run continuous health capture and/or metrics DB reads for restart rate, state transitions, floor-hit cycles, and SOFT_RED dwell.
- Require parser fixture tests for representative CAKE `tc -s qdisc` output before the live off-peak run.
- Define reference-flow schedule exactly and make Phase 227 reuse the same harness unchanged.
- Scope restore proof language to "config artifact and command identity proven," not "runtime restore proven."
- Keep `phase226-restore.sh` dry-run-only for this phase.

## Risk Assessment

**Overall risk: HIGH until revised.** Production mutation risk is mostly controlled, but evidence-validity risk is high: as written, the plans can run in the wrong order, fail their own acceptance checks, produce non-delta counter summaries, and leave GATE-01 partially unresolved. With the sequencing and validation fixes above, this drops to **MEDIUM/LOW** for production safety.

---

## Consensus Summary

Single external reviewer this cycle (Codex). No cross-reviewer consensus to synthesize, so the
items below are Codex's findings triaged by severity and load-bearing impact for a planner to action
via `/gsd:plan-phase 226 --reviews`.

### Agreed Strengths

- Phase boundary discipline is correct: baseline + anchor + locked thresholds only, candidate
  deploy deferred to Phase 227.
- Reuse of proven precedents (phase224 snapshot/rollback, phase198/213 capture, phase225 SAFE-13
  check) rather than re-inventing.
- Redacted-committable vs operator-private-raw split, and the explicit rejection of a live restore
  drill, are the right safety calls.

### Agreed Concerns (highest priority — all HIGH from Codex)

1. **Wave ordering / capture contamination** — Snapshot A (226-02) and baseline load (226-01) are
   both Wave 1 with no ordering; running flent before Snapshot A pollutes qdisc counters and
   controller state. Snapshot A should precede load generation.
2. **Undeclared 226-03 → 226-01 data dependency** — the GATE-01 tin-separation noise-band constant
   (D-06) is derived from 226-01's `tin_queue_delay_spread_ms`, but 226-03 declares no dependency and
   leaves a null placeholder. A placeholder JSON is not a *locked* threshold artifact unless there is
   an explicit "fill derived constant" step committed before Phase 227.
3. **Self-contradicting acceptance checks** — 226-01/226-02 require evidence text to contain
   `diffserv`/`allow_wash`/`password: REDACTED` while other acceptance greps forbid those exact
   tokens. As written the plans can fail their own gates. Needs command-aware / redaction-aware checks
   (allow `REDACTED`).
4. **Insufficient continuous state for GATE-01** — pre/during/post `/health` snapshots cannot
   produce restart-rate, transition-rate, floor-hit-cycle, or SOFT_RED-dwell deltas the gates (D-02,
   D-03, D-04) require. Needs windowed health NDJSON or a metrics-DB query around each run.
5. **`tc -s qdisc` delta semantics** — counters are cumulative since qdisc creation; parsing
   `.during.txt` directly yields polluted numbers. Must compute before→during→after per-run deltas.

### Divergent Views

None — single reviewer. The MEDIUM items (under-specified reference flows, baseline-cherry-pick
loophole, restore-proof overclaim, 226-04 dependency breadth, unnecessary `--apply` path, symlink
resolution in raw-dir containment) are Codex-only and worth folding but are not consensus-blocking.
