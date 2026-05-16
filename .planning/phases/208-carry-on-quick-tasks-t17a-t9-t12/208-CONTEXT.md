# Phase 208: Carry-on quick-tasks (T17a / T9 / T12) - Context

**Gathered:** 2026-05-15
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 208 is a small carry-on bundle with three scoped deliverables:

- TOOL-01 / T17(a): confirm the post-legacy soak-summary schema after Phase 207 removed `secondary_gate_legacy`, and close the remaining aggregator contract risk.
- TOOL-02 / T9: add `wanctl-history --ingestion-rate` using storage-reader data so operators can measure per-WAN metrics ingestion rate before future sparse-sampling or fire-on-change work.
- TOOL-03 / T12: make `wanctl-operator-summary --digest` tolerate permission-related unreadable DBs and output-write failures without taking down the whole digest.

Out of scope: controller threshold/algorithm/EWMA/dwell/deadband/burst changes, production deployment, Phase 209 SAFE-08 ATT whitelist closeout, and future T6/T7 storage-hygiene optimization work.

</domain>

<decisions>
## Implementation Decisions

### Aggregator Contract (TOOL-01 / T17a)

- **D-01:** Phase 208 should fix the Phase 207 code-review warning in `aggregate_watchdog()` now, not defer it. Unknown `gate_column` or unsupported/missing `statistic` must not false-pass as value `0.0`.
- **D-02:** Invalid watchdog config should fail closed in-band: keep the output shape stable, set `secondary_gate_completed_window.verdict` to `fail`, set `value` to `0.0`, and include a non-null `reason` naming the unknown `gate_column` or `statistic`. Do not raise from aggregation for this case.
- **D-03:** Schema proof should use golden round-trip checks for both a v1.43 reference soak summary and a v1.44 fresh-style summary. Tests should assert `secondary_gate_legacy` stays absent and `secondary_gate_completed_window` remains the only watchdog secondary gate.
- **D-04:** TOOL-01 is allowed to touch `scripts/soak_summary_aggregate.py` and the relevant tests/fixtures only. It must not reopen CALIB-02 YAML promotion; HRDN-04 already routed that to NO in Phase 207.

### Ingestion-Rate CLI (TOOL-02 / T9)

- **D-05:** `wanctl-history --ingestion-rate` human output should be a compact table, consistent with existing `wanctl-history` output style. One row per WAN is required.
- **D-06:** Human rows should include enough operator context to avoid the earlier misread: WAN/database identity, selected window, matching row count, rows/sec, and requested-window mean rows/sec.
- **D-07:** `--json` output should be a stable object, not a bare array. Use a shape with top-level metadata such as `window`, `generated_at`, aggregate totals, and `wans: [...]` for per-WAN rows.
- **D-08:** Windowed mean is based on the selected/requested time range duration from existing `--last`, `--from`, and `--to` semantics. Do not use first-to-last observed row span as the primary rate, because sparse data can inflate rates and complicate empty/one-row cases.
- **D-09:** The flag should respect existing `wanctl-history` filters: `--db`, `--wan`, and time range. Reuse existing per-WAN DB discovery and filtering conventions instead of inventing a separate discovery/filter model.
- **D-10:** The folded T9 todo asks for per-metric top-N volume. Treat that as subordinate to ROADMAP/TOOL-02: Phase 208 must deliver per-WAN rows/sec and windowed mean. Per-metric breakdown can be included only if it stays small and does not obscure the per-WAN contract.

### Digest Permission Guard (TOOL-03 / T12)

- **D-11:** Handle both permission/read failures for individual WAN DBs and output/write `OSError` failures, but narrowly. The digest command should continue processing remaining WAN DBs where possible.
- **D-12:** For unreadable DBs, skip that DB and emit a stable stderr message with WAN/database context. The folded todo's operator-facing intent is: do not require the whole digest command to fail just because one DB needs sudo/group membership.
- **D-13:** For digest line output/write failures, catch only `OSError`, emit a stable stderr skip message, and continue remaining WAN DBs. Keep sqlite/json/type/programming errors on existing error paths unless they are the specific unreadable-DB case being guarded.
- **D-14:** Skip messages should use a stable stderr prefix suitable for tests, e.g. `operator-summary digest: skipped ...`. Tests should assert the prefix and WAN/db context, not the full OS error text.
- **D-15:** Tests should inject failures deterministically by mocking the DB open/query boundary for unreadable DBs and mocking the output/write boundary for `OSError`. Avoid chmod-based permission tests because root/CI behavior can be flaky.
- **D-16:** If all discovered DBs are unreadable/skipped, exit 0 with a clear stable message such as `no readable WAN DBs - try sudo` rather than propagating the first exception.

### Folded Todos

- **T9:** `.planning/todos/pending/2026-04-17-ingestion-rate-tool.md` is folded into TOOL-02. Original problem: prior ingestion audit misestimated write rate by using cleanup deletes instead of steady-state writes.
- **T12:** `.planning/todos/pending/2026-04-17-operator-summary-digest-permission-handling.md` is folded into TOOL-03. Original problem: digest mode can fail for an operator without DB read permission instead of skipping unreadable DBs cleanly.

### the agent's Discretion

- Exact helper names and formatting widths are planner discretion, as long as the output contracts above are test-pinned.
- Planner may decide whether per-metric ingestion-rate breakdown fits inside TOOL-02 without expanding scope; per-WAN rows/sec remains mandatory.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase Scope
- `.planning/ROADMAP.md` §"Phase 208: Carry-on quick-tasks (T17a / T9 / T12)" — fixed goal, dependencies, requirements, and success criteria.
- `.planning/REQUIREMENTS.md` §"TOOL — Carry-on quick-tasks (T17a / T9 / T12)" — TOOL-01, TOOL-02, TOOL-03 requirement wording.
- `.planning/PROJECT.md` §"Current Milestone: v1.44" — milestone constraints, SAFE-09 no-controller-threshold-change invariant, and active/deferred scope.

### Prior Phase Decisions
- `.planning/phases/207-soak-harness-hardening-v1-43-closeout-routed/207-CONTEXT.md` — HRDN-03/04 decisions: legacy gate removal, CALIB-02 YAML promotion routed to NO, and T17(b) deferred.
- `.planning/phases/207-soak-harness-hardening-v1-43-closeout-routed/207-REVIEW.md` — WR-01 warning about unknown watchdog `gate_column`/`statistic` false-pass; Phase 208 should close it.
- `.planning/phases/207-soak-harness-hardening-v1-43-closeout-routed/207-VERIFICATION.md` — confirms Phase 207 post-legacy state and SAFE-09 clean boundary.

### Aggregator / Schema
- `scripts/soak_summary_aggregate.py` — `aggregate_watchdog()`, `aggregate_soak()`, and `load_calib_02_constants()` implementation to harden and verify.
- `scripts/calib_02_threshold.json` — operator-approved threshold artifact; remains the source of truth after HRDN-04 NO.
- `tests/test_phase_204_watchdog.py` — existing completed-window and legacy-removal contract tests.
- `tests/test_phase_204_replay.py` — replay assertion that legacy key is absent.
- `tests/test_phase_204_distribution.py` — golden fixture / distribution consumer coverage.
- `CHANGELOG.md` §v1.44 Unreleased — HRDN-03 removal and HRDN-04 NO decision entries.

### Ingestion Rate CLI
- `src/wanctl/history.py` — `wanctl-history` parser, output modes, filter/time-range resolution, and main query flow.
- `src/wanctl/storage/reader.py` — storage reader functions; new rate helper should live here or reuse this module's SQL conventions.
- `src/wanctl/storage/db_utils.py` — per-WAN DB discovery and query-all-WANs semantics.
- `tests/test_history_cli.py` — existing CLI output and subprocess test patterns.
- `.planning/todos/pending/2026-04-17-ingestion-rate-tool.md` — folded T9 motivating problem and desired measurement use case.

### Operator Digest Guard
- `src/wanctl/operator_summary.py` — `print_digest()` and `main()` digest path to harden.
- `tests/test_operator_digest.py` — existing digest tests to extend.
- `.planning/todos/pending/2026-04-17-operator-summary-digest-permission-handling.md` — folded T12 motivating permission-denied problem.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `aggregate_watchdog()` already isolates watchdog gate output. The false-pass fix can stay local to cell/statistic resolution and preserve the return shape.
- `load_calib_02_constants()` already has a fail-closed JSON-file convention. Phase 208 should not add YAML/config surface area.
- `wanctl-history` already has parser groups for time range, filters, output, and DB path. `--ingestion-rate` should slot into the existing CLI rather than becoming a separate script.
- `query_all_wans()` and `discover_wan_dbs()` already define per-WAN DB discovery and partial-failure semantics for read helpers.
- `print_digest()` is compact and currently prints one formatted line per DB; this is the natural guard point for per-DB skip behavior.

### Established Patterns
- Existing CLI JSON modes use explicit JSON output flags and table output for humans. Phase 208 should preserve this split.
- Storage-reader queries return safe empty results on missing DB/read errors where appropriate; programmer bugs should not be swallowed broadly.
- Tests use direct function calls plus subprocess/argv monkeypatching for CLI behavior. Prefer deterministic monkeypatches over filesystem permission scenarios.

### Integration Points
- TOOL-01 integrates with v1.43/v1.44 soak summary fixtures and Phase 207's legacy-removal tests.
- TOOL-02 integrates `src/wanctl/history.py` with `src/wanctl/storage/reader.py` and per-WAN DB discovery in `src/wanctl/storage/db_utils.py`.
- TOOL-03 integrates `operator_summary.print_digest()` with existing digest tests in `tests/test_operator_digest.py`.

</code_context>

<specifics>
## Specific Ideas

- Ingestion-rate JSON should be object-shaped so future fields can be added without breaking parsers: top-level window metadata plus `wans` rows.
- For invalid watchdog config, returning a fail verdict with reason is preferred over raising because it keeps generated summary artifacts inspectable while staying fail-closed.
- For digest permission handling, the final context intentionally broadens the earlier output-write framing to include unreadable DBs because the folded T12 todo specifically describes DB read permission failure.

</specifics>

<deferred>
## Deferred Ideas

- T6/T7 storage-hygiene optimization remains deferred to a future storage phase after TOOL-02 lands. Relevant matched todos were reviewed but not folded: autorate flat-gauge fire-on-change audit and CAKE tin skip-on-unchanged consumer audit.
- SEED-005 conservative UL tuning sweep and T17(b) CALIB-02 YAML knob-shape evaluation remain deferred per `.planning/REQUIREMENTS.md`.
- Unrelated matched todos for tuning, steering, Silicom bypass tooling, archive cleanup, and ATT cake-primary canary were not folded; they are outside Phase 208's three-task boundary.

</deferred>

---

*Phase: 208-carry-on-quick-tasks-t17a-t9-t12*
*Context gathered: 2026-05-15*
