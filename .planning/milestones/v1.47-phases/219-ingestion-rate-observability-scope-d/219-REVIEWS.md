---
phase: 219
reviewers: [codex]
reviewed_at: 2026-05-30
plans_reviewed:
  - 219-01-PLAN.md
  - 219-02-PLAN.md
  - 219-03-PLAN.md
  - 219-04-PLAN.md
---

# Cross-AI Plan Review — Phase 219

## Codex Review

**Overall Summary**
The phase is well scoped and mostly additive, with good TDD intent and strong SAFE-11 discipline. The main issues are internal contradictions: the plans require per-metric null rows but also mandate a single `GROUP BY metric_name` query; they say default `--ingestion-rate` behavior is unchanged while replacing the v1.44 JSON envelope; and Phase 219 success criterion #5 is only noted as a post-deploy reminder, not actually planned as a gate.

### 219-01: Wave 0 Test Scaffolds

**Strengths**
- Good contract-first approach: schema, staleness fields, rolling/cartesian behavior, retention, and mutation boundary are pinned before implementation.
- Reuses existing patterns from `tests/test_history_cli.py:809` and `tests/test_phase214_mutation_boundary.py:56`.

**Concerns**
- **HIGH:** `tests/test_phase219_ingestion_digest.py` cannot both module-skip on a missing script and still collect 5 test methods. Also `scripts.phase219_ingestion_digest` is not importable if the file is `scripts/phase219-ingestion-digest.py`.
- **HIGH:** The "second metric fails" test conflicts with the later single-pass `GROUP BY metric_name` design. There is no per-metric `sqlite3.connect`.
- **MEDIUM:** Several bucketed tests rely on deterministic time, but current `_resolve_time_range()` uses `datetime.now()` in `history.py:616`, not `time.time()`.
- **MEDIUM:** The SAFE-11 "outside allowlist" check as written appears to cover committed diffs only, not unstaged/staged changes.

**Suggestions**
- Make scaffold tests collect without importing the future script; load it only inside tests after plan 04 lands.
- Decide whether per-metric null rows are a real requirement. If yes, do per-metric reads. If no, change tests/requirements to per-DB null behavior.
- Use explicit `--from/--to` in all deterministic history CLI tests.
- Reuse `_assert_no_git_diff()` for staged, unstaged, and committed allowlist checks.

**Risk Assessment:** **MEDIUM-HIGH** until collection and per-metric failure contradictions are fixed.

### 219-02: CLI Extension

**Strengths**
- Correctly keeps work in `history.py:651` and tests, avoiding controller-path changes.
- Single SQL grouped query is the right performance instinct for normal per-metric counts.
- Adds parser validation for `--by-table` / `--rolling` requiring `--ingestion-rate`.

**Concerns**
- **HIGH:** Replacing legacy JSON conflicts with "default behavior unchanged." Current JSON is `window/generated_at/totals/wans` in `history.py:458`; plan 02 removes that shape.
- **HIGH:** Single SQL pass cannot satisfy "per-table read failures emit null for that table." A query failure yields one DB-level failure, not one failed metric row.
- **MEDIUM:** Threat model says cap `--rolling` at 16 windows, but tasks/acceptance do not implement that cap.
- **MEDIUM:** Handler recomputes time windows instead of using the already resolved `start_ts/end_ts`; this can drift from CLI `--from/--to` semantics.
- **MEDIUM:** Existing `count_metrics()` returns `0` for missing/open/query-failed DBs in `reader.py:467`, so some planned "all DBs failed" behavior will not trigger in default mode.

**Suggestions**
- Either preserve legacy JSON for `--ingestion-rate --json` without new flags, or explicitly mark this as a breaking operator-contract change.
- Add the rolling-window count cap to implementation and tests.
- Pass resolved `start_ts/end_ts` into `_resolve_rolling_windows()` for fallback mode.
- Align failure semantics: per-metric null rows require per-metric queries; single-pass grouped query should document per-DB failure rows only.

**Risk Assessment:** **MEDIUM-HIGH** because it touches an existing operator contract and has a core requirement/design mismatch.

### 219-03: Operator Summary Digest

**Strengths**
- In-process import is reasonable for an out-of-band CLI.
- Pure `_format_ingestion_digest_line()` is easy to test.
- Tie-break behavior is deterministic and operator-friendly.

**Concerns**
- **HIGH:** Existing `print_digest()` aborts on query-time DB/schema errors after opening a DB, before any new ingestion block runs; see `operator_summary.py:152`. That weakens "never abort digest on per-WAN read failure."
- **MEDIUM:** `top=mixed: a/b` contains a space, which is awkward for log parsing despite the "log-parseability" goal.
- **MEDIUM:** Incrementing `counts["printed"]` for both hard-red and ingestion lines changes the meaning of an existing return counter.
- **LOW:** The plan calls `int(time.time())` twice for one 3600s window; capture once.

**Suggestions**
- Make the ingestion loop independent enough that a hard-red query failure on one WAN does not suppress all ingestion lines.
- Prefer `top=mixed:a/b` or `top="mixed: a/b"` if log parsing matters.
- Clarify whether `printed` means all digest lines or legacy hard-red lines only.
- Capture `now = int(time.time())` once per WAN or once per digest run.

**Risk Assessment:** **MEDIUM**. The implementation is straightforward, but tolerance semantics need tightening.

### 219-04: Cron Script + Docs

**Strengths**
- Good cron-not-systemd boundary.
- Atomic write + count-based retention matches the phase's flash-wear posture.
- Docs plan correctly explains staleness semantics and avoids tuning guidance.

**Concerns**
- **HIGH:** Objective says script is invokable via `python -m`, but `scripts/phase219-ingestion-digest.py` with a hyphen is not module-invokable.
- **HIGH:** Atomic write temp name `<target>.tmp` is not safe for concurrent same-second writers. Existing `state_utils.py:24` uses unique temp files for a reason.
- **MEDIUM:** Failure test using `PYTHONPATH=/nonexistent` is not deterministic from the repo because current working directory can still make `wanctl.history` importable.
- **MEDIUM:** The script writes subprocess stdout without validating JSON, despite producing audit evidence.
- **MEDIUM:** Phase success criterion #5, production cycle budget, is only documented as a post-deploy requirement. It is not a real plan task or verification gate.

**Suggestions**
- Either rename to importable form or drop the `python -m` claim.
- Use `tempfile.mkstemp(..., dir=target.parent)` plus `os.replace()`.
- Validate `json.loads(payload)` before writing snapshots.
- Add an explicit final verification step for production cycle-budget evidence, or split it into a separate deployment/verify plan.

**Risk Assessment:** **MEDIUM**. Operationally safe, but the module invocation and atomic-write details should be corrected.

### Overall Risk
**MEDIUM-HIGH** as written. The phase goal is achievable and the scope is sane, but Codex would not execute these plans unchanged. Fix the three contract mismatches first: default JSON compatibility, per-metric failure semantics, and the missing production cycle-budget gate.

---

## Consensus Summary

*Single reviewer (Codex) — consensus = single-reviewer judgment. Treat as one independent opinion, not multi-AI convergence.*

### Agreed Strengths
- TDD/contract-first discipline (Wave 0 scaffolds before implementation).
- SAFE-11 mutation boundary honored across all plans.
- Atomic-write + count-based retention is correct for flash-wear posture.
- In-process import for operator-summary → history avoids subprocess overhead on the out-of-band CLI.

### Agreed Concerns (HIGH-severity findings worth addressing before execution)

1. **JSON envelope back-compat vs "default unchanged" contradiction** (plan 02). INGEST-02 says default behavior unchanged, but plan 02 Task 3 replaces the v1.44 envelope unconditionally (`{schema_version:1, rows:[...]}`). Either (a) version-fork the envelope on flag presence, or (b) explicitly document the breaking change in REQUIREMENTS + SUMMARY before merging.

2. **Per-metric null-row semantics vs single `GROUP BY` query** (plans 01, 02). INGEST-01 + CONTEXT.md JSON shape says `row_count` is null per failed table. But the single-pass `GROUP BY metric_name` design fails at the DB level — one failure yields one DB row, not one row per metric. Either (a) switch to per-metric queries (perf cost on big DBs), or (b) tighten the contract to "per-DB null, not per-metric null" and update tests + acceptance.

3. **`scripts/phase219-ingestion-digest.py` hyphen vs `python -m` invocation** (plan 04). Python module loading via `python -m` requires underscores, not hyphens. Either rename file to `phase219_ingestion_digest.py` or drop the `python -m` claim and invoke via direct path.

4. **Atomic write temp filename collision** (plan 04). `<target>.tmp` is not safe for concurrent same-second writers. The existing `state_utils.py:24` `atomic_write_json` uses unique temp files. Either reuse that helper, or rewrite Plan 04 Task 1 to use `tempfile.mkstemp(..., dir=target.parent)`.

5. **`print_digest()` early-abort on DB error** (plan 03). The existing function aborts on query-time DB/schema errors before any new ingestion block can run, undermining the "never abort digest on per-WAN read failure" promise. Plan 03 must restructure the per-WAN loop to ensure ingestion lines emit even when hard-red queries fail.

6. **Cycle-budget success criterion #5 lacks a planned gate** (plan 04). The post-deploy `cycle_total.avg_ms ≤ 3.0` / `p99_ms ≤ 7.5` requirement is described as an operator narrative in plan 04's SUMMARY, but no plan task verifies it. Either add a Wave-3 verification task referencing `scripts/profiling_collector_json.py`, or split into a separate post-deploy phase with explicit acceptance.

### MEDIUM concerns to triage

- Rolling-window count cap (threat model says 16; tasks don't enforce).
- `time.time()` capture cadence — currently 2× per WAN, should be 1× per invocation (already CONTEXT-locked, but plan 03 drifts).
- `count_metrics()` returns 0 for failed-DB, so "all DBs failed" path may not trigger in default mode.
- `printed` counter semantic ambiguity in plan 03.
- `mixed: a/b` token contains a space — log-parseability concern.
- Subprocess JSON not validated before snapshot write.

### Divergent Views
N/A — single reviewer.

---

## Action

To incorporate this feedback into a revised plan:

```
/gsd:plan-phase 219 --reviews
```

The planner will read this REVIEWS.md, address each HIGH/MEDIUM concern, and re-run plan-checker.
