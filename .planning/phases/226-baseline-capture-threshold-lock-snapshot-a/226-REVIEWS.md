---
phase: 226
reviewers: [codex]
reviewed_at: 2026-06-04T05:43:07Z
plans_reviewed: [226-01-PLAN.md, 226-02-PLAN.md, 226-03-PLAN.md, 226-04-PLAN.md]
---

# Cross-AI Plan Review — Phase 226

Reviewer set: Codex (`codex exec`, CLI default model). Running inside Claude Code, so the
Claude CLI was skipped for independence per the review workflow's self-CLI rule.

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
