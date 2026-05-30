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
- `scripts/phase219-ingestion-digest.py` (cron-callable snapshot writer)
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
- `_snapshot_age_sec` = `now - _snapshot_unix` computed at output emit (will be ~0 for direct CLI use; meaningful when `phase219-ingestion-digest.py` persists JSON and the file is read later).
- The "snapshot" semantic is produced by `phase219-ingestion-digest.py` persisting the CLI's JSON output to disk. The CLI itself stores no state.
- **Why:** Pitfall 5 forbids new daemon state paths; Pitfall 7 mandates staleness fields. Live-query honors both — the CLI stays a stateless SQLite reader (v1.44 Phase 208 architecture), and the staleness contract is satisfied at the file-consumer layer.

### JSON output shape

Top-level envelope:
```json
{"schema_version": 1, "rows": [ ... ]}
```

Each row carries discriminator + measurement fields:
- `wan_name` (string) — WAN identifier
- `wan_db` (string) — db path
- `table_name` (string | null) — null when `--by-table` is NOT set; the metric table name when set
- `window_seconds` (int) — the rolling window for this row; equals the resolved `--last`/full range when `--rolling` is NOT set
- `row_count` (int | null) — null if this table failed to read; never aborts the row
- `rows_per_sec` (float | null) — null if `row_count` is null
- `_snapshot_unix` (int) — invocation-batch wall-clock (same value across all rows in one call)
- `_snapshot_age_sec` (int) — `now - _snapshot_unix` at emit

When both `--by-table` and `--rolling` are set, output is the **cartesian product** per WAN: one row per (wan, table, window). When neither is set, behavior is **unchanged** from v1.44 Phase 208 (`table_name` is null, `window_seconds` = full resolved range, one row per WAN).

**Why this shape:**
- Append-only extension of the current `_per_wan_ingestion_rate()` row pattern at `src/wanctl/history.py:683-691`. No legacy consumer breaks.
- Flat rows trivially fixture-pin: golden test compares row list against a known JSON literal.
- Discriminator fields (`table_name`, `window_seconds`) are explicit, so consumers filter without nested-key knowledge.
- Nested map and parallel-arrays shapes were rejected: nested map breaks v1.44 compatibility and is harder to pin; parallel arrays double the fixture surface.

### Dominant-table tie-break (operator-summary `--digest`)

For each WAN's digest line, identify the dominant table by `rows_per_sec`:
- If the top table's `rows_per_sec` is **>= 1.20×** the runner-up's, render the top table name.
- Otherwise render `mixed: <top1>/<top2>` (the two highest, slash-separated).
- If there is only one table with non-zero rate, render that table directly (no tie possible).
- If all tables are null/zero (db read failed or empty window), render `n/a`.

**Why:** A one-glance digest line that silently picks a winner from two near-tied tables is operationally misleading. The 20% lead threshold matches the by-design-vs-anomaly threshold elsewhere in the controller. Both branches are deterministic and fixture-testable. Alphabetical and first-encountered tie-breaks were rejected as silently misleading.

### Snapshot persistence (`scripts/phase219-ingestion-digest.py`)

- **Path:** `/var/lib/wanctl/snapshots/ingestion/<unix_ts>.json`
- **Write pattern:** Write to `<unix_ts>.json.tmp` then `os.rename()` for atomicity. Never expose partial files to a concurrent reader.
- **Retention:** Keep the **288 most recent files** (count-based, not age-based). At 5-min cron cadence that is ~24h of coverage; ~288 × ~10KB ≈ 3MB ceiling. Flash-safe per the project's flash-wear posture (CLAUDE.md).
- **Cron, not systemd:** INGEST-05 explicit. No new systemd unit.
- **Permission model:** Script must `os.makedirs(..., mode=0o755, exist_ok=True)` for the snapshot dir and tolerate the dir already existing with different perms (log warning, attempt write anyway).
- **Tolerance:** Per-WAN read failures inside the CLI emit null rows; the snapshot file always writes (atomicity of the JSON envelope, not the underlying read success).

**Why:** `/var/lib/wanctl/` is the persistent state dir per project layout — Phase 218 audit windows can span reboots, so tmpfs (`/run/wanctl/`) is the wrong tradeoff. Count-based retention avoids per-cron `stat()` + `unlink()` sweeps on every run. Configurable-path was deferred to v2; the default has to land somewhere concrete.

### Folded todo (resolves_phase: 219)

- `2026-04-17-ingestion-rate-tool.md` — "Add tool for computing actual metrics.db write rates" — pre-tagged `resolves_phase: 219`. The motivating use case (smoothing transient spikes via a tail-rate window) is **directly satisfied** by `--rolling=60,300,3600`. The 60s window matches the "last 10 min" smoothing intent at lower latency; the 3600s window matches the "validate fire-on-change or sparse-sampling optimization" use case. No additional work beyond INGEST-01..05 needed to close this todo.

### Mutation-boundary scope (SAFE-11)

**Allowlisted for additive edits this phase:**
- `src/wanctl/history.py` — extend argparse + `_per_wan_ingestion_rate()` + add `_per_wan_ingestion_rate_bucketed()`
- `src/wanctl/operator_summary.py` — extend `print_digest()` / argparse with the ingestion block
- `scripts/phase219-ingestion-digest.py` — new file
- `tests/test_history_ingestion_rate_bucketed.py` — new file (golden SQLite fixture)
- `tests/fixtures/phase219/` — new fixtures (observed-evidence shape only, never controller-spec shape)
- `tests/test_safety_boundary.py` (or equivalent) — extend the SAFE-11 allowlist
- `docs/CONFIGURATION.md` — staleness semantics paragraph (match v1.38 pattern); CLI-tool-description only, no tuning language

**Forbidden (boundary enforced by mutation-boundary pytest):**
- `src/wanctl/wan_controller.py`, `queue_controller.py`, `cake_signal.py`
- All RouterOS/CAKE backends, `alert_engine.py`, fusion code
- Anything in the daemon hot path

### Claude's Discretion

- Argparse mutual-exclusion handling between `--by-table`, `--rolling`, and the existing `--summary` (legacy summary block) — pick the least surprising combination; defer odd combos to error with a helpful message.
- Exact column set for the non-JSON (table) view of `--by-table` / `--rolling` output — JSON is the contract, table view is for humans. Reasonable wide-column rendering, optionally suppressed under `--json`.
- Whether to emit per-snapshot fields in the legacy default-flag mode — recommended yes for consistency (`schema_version` + `_snapshot_unix` + `_snapshot_age_sec` everywhere under `--json`).
- `_per_wan_ingestion_rate_bucketed()` internal structure — single SQL pass per DB grouping by metric name vs. N passes per table — planner researches and picks based on existing storage reader patterns.
- `mixed:` rendering ordering when two tables are tied — alphabetical within the `mixed:` payload is fine.

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
- `src/wanctl/operator_summary.py` — `print_digest()` at line 152; `_format_digest_line()` at line 119; `_DIGEST_SKIP_PREFIX` tolerance pattern
- `src/wanctl/storage/reader.py` — `count_metrics()` (read-tolerance + per-WAN filtering pattern)

### Test pattern precedents
- `tests/test_history_*` — directly applicable for the new `tests/test_history_ingestion_rate_bucketed.py` golden fixture

### Docs (staleness semantics precedent)
- `docs/CONFIGURATION.md` — v1.38 `measurement_stale`, `measurement_staleness_sec` is the precedent for `_snapshot_unix` / `_snapshot_age_sec` documentation pattern

### Phase 217 anchor (cycle-budget tolerance)
- `.planning/milestones/v1.46-phases/217-production-cycle-budget-baseline/` — Phase 217 baseline (`cycle_total.avg_ms ≤ 3.0`, `p99_ms ≤ 7.5`) inherited by Phase 219 success criterion #5

</canonical_refs>

<specifics>
## Specific References

- The existing `_per_wan_ingestion_rate()` (history.py:651) returns `(rows, failures)` and emits `{wan_db, wan_name, row_count, window_seconds, rows_per_sec}`. The bucketed variant extends this same row shape with `table_name`, the per-invocation `_snapshot_unix`/`_snapshot_age_sec`, and optional per-window multiplexing.
- The existing `--ingestion-rate` flag is at history.py:559 (`dest=ingestion_rate`). New flags (`--by-table`, `--rolling`) sit in the same `filter_group` block.
- `wanctl-operator-summary --digest` currently only emits the hard-red alert digest (`print_digest()` at operator_summary.py:152). The ingestion block is **additive** — render after the hard-red block, prefixed `operator-summary digest: ingestion-rate` for log-parseability matching the existing `_DIGEST_SKIP_PREFIX` convention.
- `count_metrics()` already supports `wan`-filtered SQL row counting and returns 0 for missing/open-failed/query-failed DBs — the new `--by-table` path should call it with a per-table `metric_names=[t]` filter (one call per table) rather than re-implementing the read.
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
