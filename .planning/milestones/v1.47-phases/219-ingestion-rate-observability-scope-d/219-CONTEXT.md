# Phase 219: Ingestion-Rate Observability (Scope D) — Context

**Gathered:** 2026-05-29
**Status:** Ready for planning
**Source:** /gsd:discuss-phase (4 gray areas resolved + 1 folded todo)

<domain>
## Phase Boundary

Ship per-WAN per-table SQLite ingestion-rate observability as **additive** extensions to the existing v1.44 Phase 208 `wanctl-history --ingestion-rate` CLI. Surface in `wanctl-operator-summary --digest`. Provide a cron-callable snapshot script so Phase 218 audit windows have evidence available regardless of when (or if) Phase 218 fires during the v1.47 milestone.

**In scope:**
- `--by-table` flag on `wanctl-history --ingestion-rate` (per-WAN × per-table breakdown)
- `--rolling=60,300,3600` flag (multi-window single-call output)
- JSON output mode with `schema_version: 1` + per-snapshot staleness fields (`_snapshot_unix`, `_snapshot_age_sec`)
- Tolerant per-table read-failure (null per-table row, never abort)
- `wanctl-operator-summary --digest` compact per-WAN ingestion block (per-WAN totals + dominant-table)
- `scripts/phase219_ingestion_digest.py` (cron-callable snapshot writer; underscore name per D-19)
- Golden SQLite fixture pin: `tests/test_history_ingestion_rate_bucketed.py`
- SAFE-11 mutation-boundary pytest covering the Phase 219 allowlist

**Out of scope (deferred):**
- `/health.metrics.ingestion` block — deferred unless Phase 218 audit proves CLI-only insufficient (PITFALL 5, ARCH-09 stop-line)
- Per-metric category grouping (signal/fusion/alerts/cake_stats) — P2, may layer in Phase 220+
- Anomaly hints (zero-row flagging) — P2
- Threshold-based ingestion alerts — explicit anti-feature for v1.47
- Prometheus/Grafana export — deferred from v1.23

</domain>

<decisions>
## Implementation Decisions

### Snapshot model (live-query, stateless CLI)

- The CLI computes ingestion rate **live** from SQLite at query time.
- `_snapshot_unix` = wall-clock captured **once per invocation** at the start of the per-WAN query batch (single `fetch_time` carried into every emitted row).
- `_snapshot_age_sec` = `now - _snapshot_unix` computed at output emit (will be ~0 for direct CLI use; meaningful when `phase219_ingestion_digest.py` persists JSON and the file is read later).
- The "snapshot" semantic is produced by `phase219_ingestion_digest.py` persisting the CLI's JSON output to disk. The CLI itself stores no state.
- **Why:** Pitfall 5 forbids new daemon state paths; Pitfall 7 mandates staleness fields. Live-query honors both — the CLI stays a stateless SQLite reader (v1.44 Phase 208 architecture), and the staleness contract is satisfied at the file-consumer layer.

### JSON output shape

Top-level envelope (NEW MODE — emitted ONLY when `--by-table` OR `--rolling` is set; see D-17 below):
```json
{"schema_version": 1, "rows": [ ... ]}
```

Each row carries discriminator + measurement fields:
- `wan_name` (string) — WAN identifier
- `wan_db` (string) — db path
- `table_name` (string | null) — null when `--by-table` is NOT set; the metric table name when set
- `window_seconds` (int) — the rolling window for this row; equals the resolved `--last`/full range when `--rolling` is NOT set
- `row_count` (int | null) — null on read failure for that row's DB (see D-18 for failure semantics)
- `rows_per_sec` (float | null) — null when `row_count` is null
- `_snapshot_unix` (int) — invocation-batch wall-clock (same value across all rows in one call)
- `_snapshot_age_sec` (int) — `now - _snapshot_unix` at emit

When both `--by-table` and `--rolling` are set, output is the **cartesian product** per WAN: one row per (wan, table, window). When neither is set, behavior is **unchanged** from v1.44 Phase 208 envelope (`{window, generated_at, totals, wans}` — see D-17 version-fork lock).

**Why this shape:**
- Append-only extension of the current `_per_wan_ingestion_rate()` row pattern at `src/wanctl/history.py:683-691`. No legacy consumer breaks.
- Flat rows trivially fixture-pin: golden test compares row list against a known JSON literal.
- Discriminator fields (`table_name`, `window_seconds`) are explicit, so consumers filter without nested-key knowledge.
- Nested map and parallel-arrays shapes were rejected: nested map breaks v1.44 compatibility and is harder to pin; parallel arrays double the fixture surface.

### Dominant-table tie-break (operator-summary `--digest`)

For each WAN's digest line, identify the dominant table by `rows_per_sec`:
- If the top table's `rows_per_sec` is **>= 1.20×** the runner-up's, render the top table name.
- Otherwise render `mixed:<top1>/<top2>` (the two highest, slash-separated; **no space after `mixed:`** per D-20).
- If there is only one table with non-zero rate, render that table directly (no tie possible).
- If all tables are null/zero (db read failed or empty window), render `n/a`.

**Why:** A one-glance digest line that silently picks a winner from two near-tied tables is operationally misleading. The 20% lead threshold matches the by-design-vs-anomaly threshold elsewhere in the controller. Both branches are deterministic and fixture-testable. Alphabetical and first-encountered tie-breaks were rejected as silently misleading.

### Snapshot persistence (`scripts/phase219_ingestion_digest.py`)

- **Path:** `/var/lib/wanctl/snapshots/ingestion/<unix_ts>.json`
- **Write pattern:** Reuse `wanctl.state_utils.atomic_write_json` (`tempfile.mkstemp(..., dir=parent)` + `os.replace`) per D-21. Never expose partial files to a concurrent reader. The state_utils helper handles unique temp filenames safely for concurrent writers.
- **Retention:** Keep the **288 most recent files** (count-based, not age-based). At 5-min cron cadence that is ~24h of coverage; ~288 × ~10KB ≈ 3MB ceiling. Flash-safe per the project's flash-wear posture (CLAUDE.md).
- **Cron, not systemd:** INGEST-05 explicit. No new systemd unit.
- **Permission model:** Script must `os.makedirs(..., mode=0o755, exist_ok=True)` for the snapshot dir and tolerate the dir already existing with different perms (log warning, attempt write anyway).
- **Tolerance:** Per-WAN read failures inside the CLI emit null rows; the snapshot file always writes (atomicity of the JSON envelope, not the underlying read success).
- **JSON validation before write:** subprocess stdout is parsed via `json.loads(payload)` before atomic write. JSONDecodeError → stderr log + return 1 (cron retry on next tick). Prevents audit-evidence garbage per D-23.

### Folded todo (resolves_phase: 219)

- `2026-04-17-ingestion-rate-tool.md` — "Add tool for computing actual metrics.db write rates" — pre-tagged `resolves_phase: 219`. The motivating use case (smoothing transient spikes via a tail-rate window) is **directly satisfied** by `--rolling=60,300,3600`. The 60s window matches the "last 10 min" smoothing intent at lower latency; the 3600s window matches the "validate fire-on-change or sparse-sampling optimization" use case. No additional work beyond INGEST-01..05 needed to close this todo.

### Mutation-boundary scope (SAFE-11)

**Allowlisted for additive edits this phase:**
- `src/wanctl/history.py` — extend argparse + `_per_wan_ingestion_rate()` + add `per_wan_ingestion_rate_bucketed()`
- `src/wanctl/operator_summary.py` — extend `print_digest()` / argparse with the ingestion block
- `scripts/phase219_ingestion_digest.py` — new file (underscore name)
- `tests/test_history_ingestion_rate_bucketed.py` — new file (golden SQLite fixture)
- `tests/test_phase219_ingestion_digest.py` — new file
- `tests/test_phase219_mutation_boundary.py` — new file (SAFE-11 boundary clone of Phase 214)
- `tests/fixtures/phase219/` — new fixtures (observed-evidence shape only, never controller-spec shape)
- `docs/CONFIGURATION.md` — staleness semantics paragraph (match v1.38 pattern); CLI-tool-description only, no tuning language

**Forbidden (boundary enforced by mutation-boundary pytest):**
- `src/wanctl/wan_controller.py`, `queue_controller.py`, `cake_signal.py`
- All RouterOS/CAKE backends, `alert_engine.py`, fusion code
- Anything in the daemon hot path

### Post-Review Amendments (added 2026-05-30 after Codex review)

These decisions resolve contradictions in the original CONTEXT against Codex's HIGH-severity findings. Once locked here, plans 01-04 and downstream tests implement them verbatim.

**D-17 — JSON envelope version-fork (resolves Codex H1):**
INGEST-02 says default behavior unchanged. Plan 02 must preserve the v1.44 envelope (`{window, generated_at, totals, wans}` from `history.py:458-489`) when neither `--by-table` NOR `--rolling` is supplied. The NEW envelope (`{schema_version: 1, rows: [...]}`) is emitted ONLY when at least one of `--by-table`/`--rolling` is set. This honors INGEST-02 as written and prevents downstream consumer breakage.
- Plan 02 keeps both formatters: existing `format_ingestion_rate_json(rows, start_ts, end_ts)` (v1.44 envelope) AND new `format_ingestion_rate_envelope_json(rows, snapshot_unix)` (Phase 219 envelope).
- Plan 02 Task 3 handler dispatches by flag presence: `if args.by_table or args.rolling:` → new envelope; else → existing v1.44 envelope.
- Existing `tests/test_history_cli.py::TestIngestionRateCli` v1.44 envelope pins stay UNCHANGED (no test edits in default mode).
- New tests in `tests/test_history_ingestion_rate_bucketed.py` pin the new envelope only.
- Default-mode `_snapshot_unix`/`_snapshot_age_sec` enrichment (CONTEXT discretion §3 "recommended yes for consistency") is **withdrawn** by D-17 — back-compat takes priority.

**D-18 — Per-DB null semantic, NOT per-metric (resolves Codex H2):**
INGEST-01 says "per-table read failures emit null." The implementation reading is "per-DB-level read failure emits null row(s) for that DB"; success emits one row per non-empty `metric_name` from the single-pass `GROUP BY metric_name` query. Per-metric-level null is not implementable at the SQLite level (one table, one query). The single-pass `GROUP BY` design from Plan 02 stands.
- On DB open/query failure: emit ONE null row per (failed DB, window) tuple: `{wan_name, wan_db, table_name: None, window_seconds, row_count: None, rows_per_sec: None, _snapshot_unix, _snapshot_age_sec}`.
- On DB success with zero matching rows in the window: emit ONE row with `row_count: 0, rows_per_sec: 0.0, table_name: None`.
- Plan 01 test method 5 renamed `test_per_db_read_failure_emits_null_row`: monkeypatch `sqlite3.connect` to raise for one of two seeded WAN DBs; assert failed DB emits one null row, healthy DB emits its metric rows.

**D-19 — Script filename uses underscore (resolves Codex H3):**
`scripts/phase219_ingestion_digest.py` (underscore, not hyphen). Reason: `python -m scripts.phase219_ingestion_digest` requires a valid Python identifier; hyphens parse as subtraction. All references in plans 01 + 04 + tests use the underscore form.

**D-20 — `mixed:` token has no space (resolves Codex M6):**
Operator digest format: `mixed:wanctl_rtt_ms/wanctl_state` (no space after `mixed:`). Improves log-parseability with naive `awk '{print $N}'` scrapers. Supersedes the original "mixed: a/b" rendering in this CONTEXT.md.

**D-21 — Reuse `atomic_write_json` from `wanctl.state_utils` (resolves Codex H4):**
The cron script imports `from wanctl.state_utils import atomic_write_json` and calls it directly. The existing helper at `src/wanctl/state_utils.py:24-70` uses `tempfile.mkstemp(suffix=".tmp", prefix=file_path.name + ".", dir=file_path.parent)` which is collision-safe for concurrent same-second writers; rolling our own `<target>.tmp` is not. This crosses the "scripts/ should not import src/wanctl/" boundary from RESEARCH §F; the boundary is relaxed here because (a) the helper is a thin utility, not controller logic, and (b) the safety win is decisive.
- Note: `atomic_write_json` accepts a `dict`, not a string. The cron script parses subprocess stdout via `json.loads` (per D-23) before calling the helper. This composes cleanly with D-23's JSON validation.

**D-22 — Ingestion block pre-gathered before hard-red loop (resolves Codex H5):**
`operator_summary.print_digest()` aborts on query-time DB errors at `operator_summary.py:152` (the existing hard-red loop). To honor INGEST-04's "never abort digest on per-WAN read failure" for the new ingestion block, plan 03 restructures the function to: (a) call `per_wan_ingestion_rate_bucketed()` ONCE at function entry to pre-gather all per-WAN ingestion rows (with its own per-DB tolerance from D-18); (b) run the existing hard-red loop unchanged; (c) iterate the pre-gathered ingestion data in a SECOND loop after the hard-red block to emit ingestion lines — independent of any hard-red query outcome. A hard-red query failure on WAN X still emits the ingestion line for WAN X.

**D-23 — JSON-validate subprocess stdout before snapshot write (resolves Codex M8):**
The cron script parses subprocess stdout via `json.loads(payload)` before atomic write. On JSONDecodeError: stderr log + return 1 (cron retries on next tick). Prevents audit-evidence garbage from a malformed wanctl-history output. Composes with D-21 (atomic_write_json takes the parsed dict, not the raw stdout string).

**D-24 — `--rolling` window count cap = 16 (resolves Codex M1):**
`_resolve_rolling_windows` rejects lists longer than 16 windows with `argparse.ArgumentTypeError("--rolling accepts at most 16 windows")`. Matches the threat-model entry in plan 02. Tested via `wanctl-history --ingestion-rate --rolling=$(seq -s, 1 17) 2>&1 | grep -c "at most 16"` ≥ 1.

**D-25 — Window resolver uses `time.time()` AND respects `--from/--to` (resolves Codex M2 + M4):**
- `_resolve_time_range` migrates from `int(datetime.now().timestamp())` to `int(time.time())` in plan 02 Task 1 (resolves M2; deterministic monkeypatching via `wanctl.history.time.time`).
- `_resolve_rolling_windows(args, now)` uses `now` (which is `end_ts` from `_resolve_time_range(args)`) as the upper bound. Window starts = `now - window_sec`. This means `--from/--to --rolling=60,300` anchors windows to the operator-supplied `--to`, not the wall clock. Plan 02 Task 3 passes the resolved `end_ts` as `now` into the window resolver.

**D-26 — `counts["ingestion_printed"]` is a new dict key (resolves Codex M7):**
`print_digest()`'s return dict gains `"ingestion_printed"` as a separate counter from `"printed"` (which stays hard-red-only). Avoids changing the semantic of an existing counter while still tracking the new emit. Plan 03 acceptance pins both keys.

**D-27 — Cycle-budget verification gate (resolves Codex H6):**
Phase 219 ROADMAP success criterion #5 (`cycle_total.avg_ms ≤ 3.0` AND `p99_ms ≤ 7.5`) gets an explicit verification task in plan 04 (Task 4, `type: checkpoint:human-verify`). Operator runs `scripts/profiling_collector_json.py` per `docs/PROFILING.md`, captures ≥1h of post-deploy production data, runs `scripts/analyze_profiling.py`, records evidence path + numbers in `219-04-SUMMARY.md` "Production Verification" section. Plan 04 becomes `autonomous: false` because Task 4 requires production observation.

### Claude's Discretion

- Argparse mutual-exclusion handling between `--by-table`, `--rolling`, and the existing `--summary` (legacy summary block) — pick the least surprising combination; defer odd combos to error with a helpful message.
- Exact column set for the non-JSON (table) view of `--by-table` / `--rolling` output — JSON is the contract, table view is for humans. Reasonable wide-column rendering, optionally suppressed under `--json`.
- ~~Whether to emit per-snapshot fields in the legacy default-flag mode~~ — **WITHDRAWN by D-17**: default mode keeps v1.44 envelope verbatim; no schema_version/staleness fields enrichment.
- ~~`_per_wan_ingestion_rate_bucketed()` internal structure — single SQL pass per DB grouping by metric name vs. N passes per table~~ — **RESOLVED by D-18**: single-pass `GROUP BY metric_name`, per-DB-level null tolerance.
- ~~`mixed:` rendering ordering when two tables are tied — alphabetical within the `mixed:` payload is fine.~~ — **REFINED by D-20**: alphabetical AND no space after `mixed:`.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase 219 source-of-truth
- `.planning/REQUIREMENTS.md` — INGEST-01..05, SAFE-11 acceptance criteria
- `.planning/ROADMAP.md` — Phase 219 section (success criteria #1–5)

### v1.47 research (anchors approach + pitfall mitigation)
- `.planning/research/SUMMARY.md` — Scope D rationale, expected features, deferred items
- `.planning/research/PITFALLS.md` — Pitfalls 5 (hot-path), 7 (staleness), 8 (mutation boundary), 11 (D-first sequencing)
- `.planning/research/ARCHITECTURE.md` — ARCH-09 payload contract, escalation stop-line
- `.planning/research/FEATURES.md` — P1/P2/anti-feature split for Scope D
- `.planning/research/STACK.md` — stdlib-only mandate, no new deps

### Code (analog patterns + files being modified)
- `src/wanctl/history.py` — `_per_wan_ingestion_rate()` at line 651; argparse at line 558; the file being extended
- `src/wanctl/operator_summary.py` — `print_digest()` at line 152; `_format_digest_line()` at line 119; `_DIGEST_SKIP_PREFIX` tolerance pattern; `_wan_name_from_db_path` at :113
- `src/wanctl/storage/reader.py` — `count_metrics()` (read-tolerance + per-WAN filtering pattern)
- `src/wanctl/state_utils.py` — `atomic_write_json` at :24-70 (reused by Phase 219 cron script per D-21)

### Test pattern precedents
- `tests/test_history_*` — directly applicable for the new `tests/test_history_ingestion_rate_bucketed.py` golden fixture

### Docs (staleness semantics precedent)
- `docs/CONFIGURATION.md` — v1.38 `measurement_stale`, `measurement_staleness_sec` is the precedent for `_snapshot_unix` / `_snapshot_age_sec` documentation pattern

### Phase 217 anchor (cycle-budget tolerance)
- `.planning/milestones/v1.46-phases/217-production-cycle-budget-baseline/` — Phase 217 baseline (`cycle_total.avg_ms ≤ 3.0`, `p99_ms ≤ 7.5`) inherited by Phase 219 success criterion #5 (verified by plan 04 Task 4 per D-27)

</canonical_refs>

<specifics>
## Specific References

- The existing `_per_wan_ingestion_rate()` (history.py:651) returns `(rows, failures)` and emits `{wan_db, wan_name, row_count, window_seconds, rows_per_sec}`. The bucketed variant extends this same row shape with `table_name`, the per-invocation `_snapshot_unix`/`_snapshot_age_sec`, and optional per-window multiplexing. Per D-18, per-DB failure emits one null row with the same field set (null row_count + rows_per_sec).
- The existing `--ingestion-rate` flag is at history.py:559 (`dest=ingestion_rate`). New flags (`--by-table`, `--rolling`) sit in the same `filter_group` block.
- `wanctl-operator-summary --digest` currently only emits the hard-red alert digest (`print_digest()` at operator_summary.py:152). The ingestion block is **additive** — render after the hard-red block (per D-22 pre-gathered before, emitted after), prefixed `operator-summary digest: ingestion-rate` for log-parseability matching the existing `_DIGEST_SKIP_PREFIX` convention.
- `count_metrics()` already supports `wan`-filtered SQL row counting and returns 0 for missing/open-failed/query-failed DBs. Plan 02 uses a single-pass `GROUP BY metric_name` query directly instead of `count_metrics()` so it can distinguish "DB returned 0 rows" (legitimate empty window) from "DB failed to open/query" (per D-18 null-row emission).
- v1.38 measurement-staleness fields in `docs/CONFIGURATION.md` are the documentation template; the new section should sit alongside it, not replace it.

</specifics>

<deferred>
## Deferred Ideas

- `/health.metrics.ingestion` block — deferred unless Phase 218 audit proves CLI-only is insufficient. ARCH-09 stop-line is explicit: if bucketed CLI satisfies Phase 218 audit needs, do **not** cut the daemon-side escalation path.
- Per-metric category grouping (signal/fusion/alerts/cake_stats) — P2, may layer cleanly in Phase 220+ matrix work or post-v1.47.
- Anomaly hints (flag zero-row table in window) — P2, simple to add later as a non-breaking field.
- Operator-configurable snapshot path (CLI flag or env) — v2+. Single concrete default lands first.
- `wanctl-history --ingestion-rate` query speed on >1GB metrics.db — Pitfall 12 risk; current pattern bounds via `--since`/`--last` already. Revisit only if measured.
- Threshold-based ingestion alerts — explicit anti-feature for v1.47.

</deferred>

---

*Phase: 219-ingestion-rate-observability-scope-d*
*Context gathered: 2026-05-29 via /gsd:discuss-phase*
*Post-review amendments locked: 2026-05-30 (D-17..D-27 resolve Codex H1-H6 + M1-M8)*
