---
phase: 208
reviewers: [codex]
reviewed_at: 2026-05-15T00:00:00Z
plans_reviewed: [208-01-PLAN.md, 208-02-PLAN.md, 208-03-PLAN.md]
---

# Cross-AI Plan Review — Phase 208

## Codex Review

I spot-checked the live files. Overall: 208-01 is solid with a couple test-proof gaps, 208-02 needs tighter CLI/filter/failure semantics, and 208-03 has one important exception-scope flaw that should be fixed before execution.

### 208-01 (TOOL-01 — aggregator hardening)

**Summary:** Good, narrow plan. It directly fixes the known false-pass in `scripts/soak_summary_aggregate.py:303` without touching controller code. Main weakness is that the "v1.43 + v1.44 schema round-trip" proof is softer than the roadmap wording.

**Strengths**
- Clean TDD shape for unknown `gate_column` and unsupported `statistic`.
- Preserves in-band fail-closed output instead of raising, matching D-02.
- SAFE-09 is enforceable: `src/wanctl/` must remain untouched.
- Uses existing `CAUSES` and current output key shape.

**Concerns**
- **MEDIUM:** Task 3 uses one fixture as both "v1.43 reference" and "v1.44 fresh-style" proof. That proves determinism, not true cross-version schema compatibility.
- **LOW:** The proposed positive assertion looks under `result["watchdog"]`, but live `aggregate_soak()` emits `secondary_gate_completed_window` at top level in `scripts/soak_summary_aggregate.py:431`.
- **LOW:** Tests assert top-level gate absence, but should also assert the exact 10-key block shape promised by the plan.

**Suggestions**
- Replace the `watchdog` path with top-level `result["secondary_gate_completed_window"]`.
- Add `assert set(block) == {...10 keys...}` for fail-closed and valid paths.
- Use two explicit artifacts if available: existing v1.43 reference summary plus generated v1.44 fresh output. If not, state that the fixture is a proxy and keep the golden byte-equal test as the real schema anchor.

**Risk Assessment:** LOW. Script/test-only, no control path, and failure mode is conservative.

---

### 208-02 (TOOL-02 — `wanctl-history --ingestion-rate`)

**Summary:** The CLI feature is well-scoped, but the plan currently overclaims partial-failure behavior and under-specifies `--wan` filtering. The implementation can still be small, but the contract needs tightening before execution.

**Strengths**
- Reuses `count_metrics()` from `src/wanctl/storage/reader.py:467`, satisfying the "derived from storage reader" requirement.
- Object-shaped JSON is the right choice for window metadata and totals.
- Keeps changes confined to `src/wanctl/history.py:623` and tests.
- Covers parser, table, JSON, and empty DB behavior.

**Concerns**
- **MEDIUM:** `count_metrics()` already catches missing DB / open / query `OperationalError` and returns `0` in `src/wanctl/storage/reader.py:482`. The proposed `_per_wan_ingestion_rate()` failure counter will not detect common unreadable-DB cases, so "all DBs failed" may silently become zero-rate rows.
- **MEDIUM:** Existing no-DB discovery returns `1` before special query dispatch in `src/wanctl/history.py:637`. The plan's "zero WANs discovered → return 0" requires changing that early branch.
- **MEDIUM:** `--wan spectrum` will likely still print an `att` row with `0` count if iterating all discovered DBs. Existing query behavior omits nonmatching rows; this should be pinned.
- **LOW:** Tests use `--last 1h` and wall-clock `now`, but do not assert actual `row_count`, `window_seconds`, or `rows_per_sec`.

**Suggestions**
- Decide explicitly: unreadable DBs through `count_metrics()` are either "0 rows" by design, or the helper must expose failure. Don't claim all-failed semantics unless it is testable.
- Add tests for `--wan` filtering: with spectrum + att DBs, `--wan spectrum` should output only spectrum unless the intended behavior is explicit zero rows.
- Use deterministic `--from/--to` tests and assert `row_count == N`, `window_seconds`, and approximate rate.
- For no discovered DBs, either keep current `1` behavior or add an ingestion-rate-specific bypass before the current early return.

**Risk Assessment:** MEDIUM. Still non-control-path, but operator output could mislead if unreadable DBs or WAN filters become zero-rate rows.

---

### 208-03 (TOOL-03 — operator_summary digest permission guard)

**Summary:** The goal is right and the plan is mostly good, but the proposed exception scope is too broad in the wrong place. Catching `sqlite3.OperationalError` around both open and query can swallow schema/query corruption as a "skipped unreadable DB," contradicting D-13.

**Strengths**
- Stable stderr prefix is useful and testable.
- Deterministic monkeypatch tests avoid flaky chmod behavior.
- Read-only SQLite URI matches existing reader posture.
- Keeps the change confined to `src/wanctl/operator_summary.py:148`.

**Concerns**
- **HIGH:** `sqlite3.OperationalError` includes "no such table," malformed SQL, and schema problems. Catching it around `_query_digest_rows()` would hide real DB/schema issues, despite the plan's must-have that corruption errors surface. Current query is at `src/wanctl/operator_summary.py:95`.
- **MEDIUM:** If stdout write fails for every readable DB, `printed == 0` will trigger `no readable WAN DBs - try sudo`, which is misleading. That is a write failure, not unreadable DBs.
- **LOW:** Removing `OSError` from the outer digest branch means discovery-level `OSError` could turn into an uncaught traceback. Current main catches it at `src/wanctl/operator_summary.py:187`.

**Suggestions**
- Split DB open from DB query. Catch unreadable/open failures narrowly around `sqlite3.connect(...)`; let `_query_digest_rows()` `OperationalError` bubble unless explicitly classified as permission/read denial.
- Add a regression test: DB exists but lacks `alerts` table should return `1`, not emit `operator-summary digest: skipped`.
- Return structured counts from `print_digest()` such as `readable`, `printed`, `read_skipped`, `write_skipped`; only print `no readable WAN DBs - try sudo` when `readable == 0`.
- Keep a small outer guard for `discover_wan_dbs()` `OSError`, or split discovery into its own try/except before calling `print_digest()`.

**Risk Assessment:** MEDIUM-HIGH until exception scope is fixed. It is not control-loop risk, but it can mask storage/schema faults as permission skips, which is exactly the kind of operator-tool drift that becomes expensive later.

---

## Consensus Summary

Single-reviewer review (codex). No cross-reviewer consensus; treat all findings as actionable Codex calls.

### Highest-priority concerns (sorted by severity)

| Sev | Plan | Finding | Action |
|---|---|---|---|
| **HIGH** | 208-03 | `sqlite3.OperationalError` swallows "no such table" / malformed SQL → masks schema faults as permission skips | Split connect from query; only catch open-time exceptions narrowly. Add regression test for missing-table case. |
| MEDIUM | 208-03 | All-writes-fail → emits "no readable WAN DBs" (wrong message — DBs are readable, writes failed) | Track `readable` and `printed` separately; only emit "no readable" when `readable == 0`. |
| MEDIUM | 208-02 | `count_metrics()` silently returns 0 on OperationalError → unreadable DBs become zero-rate rows, not surfaced | Decide explicitly: 0-by-design (acceptance documents it) OR expose failure from helper. |
| MEDIUM | 208-02 | Plan's "0 WANs → return 0" conflicts with existing `history.py:637` early-return-1 behavior | Either keep `1` or add ingestion-rate bypass before the current early return. |
| MEDIUM | 208-02 | `--wan` filter contract not pinned; might emit zero-rate rows for filtered-out WANs | Add `--wan spectrum` filtering test; pin behavior. |
| MEDIUM | 208-01 | "v1.43 + v1.44 round-trip" uses single fixture for both → proves determinism, not cross-version compat | Use two artifacts OR document fixture-as-proxy and rely on byte-equal golden. |
| LOW | 208-01 | Plan asserts under `result["watchdog"]` but live emits at top level | Switch assertion path to `result["secondary_gate_completed_window"]`. |
| LOW | 208-01 | 10-key block shape not asserted | Add `assert set(block) == {...}`. |
| LOW | 208-02 | Tests use wall-clock `now` and don't assert exact counts | Use deterministic `--from/--to`; assert `row_count`, `window_seconds`. |
| LOW | 208-03 | Removing OSError from outer catch leaves discovery-level OSError uncaught | Add small outer guard around `discover_wan_dbs()`. |

### Recommended Next Step

The HIGH finding on 208-03 is a real semantic bug in the proposed exception scope, not just a polish item. Recommend running `/gsd-plan-phase 208 --reviews` to replan incorporating these findings, OR manually patching the three plans before execution.
