# Phase 219: Ingestion-Rate Observability (Scope D) - Research

**Researched:** 2026-05-29
**Domain:** Operator-tooling extension (CLI + cron primitive) over per-WAN SQLite metrics DB
**Confidence:** HIGH (every touch point verified by source read; CONTEXT.md has pre-locked all 4 gray areas)

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

#### Snapshot model (live-query, stateless CLI)
- The CLI computes ingestion rate **live** from SQLite at query time.
- `_snapshot_unix` = wall-clock captured **once per invocation** at the start of the per-WAN query batch (single `fetch_time` carried into every emitted row).
- `_snapshot_age_sec` = `now - _snapshot_unix` computed at output emit (will be ~0 for direct CLI use; meaningful when `phase219-ingestion-digest.py` persists JSON and the file is read later).
- The "snapshot" semantic is produced by `phase219-ingestion-digest.py` persisting the CLI's JSON output to disk. The CLI itself stores no state.
- **Why:** Pitfall 5 forbids new daemon state paths; Pitfall 7 mandates staleness fields. Live-query honors both — the CLI stays a stateless SQLite reader (v1.44 Phase 208 architecture), and the staleness contract is satisfied at the file-consumer layer.

#### JSON output shape

Top-level envelope:
```json
{"schema_version": 1, "rows": [ ... ]}
```

Each row carries discriminator + measurement fields:
- `wan_name` (string) — WAN identifier
- `wan_db` (string) — db path
- `table_name` (string | null) — null when `--by-table` is NOT set; the metric `metric_name` (logical "table") when set
- `window_seconds` (int) — the rolling window for this row; equals the resolved `--last`/full range when `--rolling` is NOT set
- `row_count` (int | null) — null if this table failed to read; never aborts the row
- `rows_per_sec` (float | null) — null if `row_count` is null
- `_snapshot_unix` (int) — invocation-batch wall-clock (same value across all rows in one call)
- `_snapshot_age_sec` (int) — `now - _snapshot_unix` at emit

When both `--by-table` and `--rolling` are set: cartesian product per WAN (one row per (wan, table, window)). When neither is set: behavior **unchanged** from v1.44 Phase 208 — `table_name` null, `window_seconds` = full resolved range, one row per WAN.

#### Dominant-table tie-break (operator-summary `--digest`)
- Top table's `rows_per_sec` ≥ **1.20×** runner-up → render top table name.
- Otherwise → render `mixed: <top1>/<top2>` (slash-separated, alphabetical within `mixed:` payload OK).
- Single non-zero table → render that table.
- All null/zero → render `n/a`.

#### Snapshot persistence (`scripts/phase219-ingestion-digest.py`)
- **Path:** `/var/lib/wanctl/snapshots/ingestion/<unix_ts>.json`
- **Write pattern:** write `<unix_ts>.json.tmp` then `os.rename()` (atomicity).
- **Retention:** keep **288 most recent files** (count-based, not age-based). ~24h at 5-min cadence; ~3MB ceiling.
- **Cron, not systemd** (INGEST-05).
- **Permissions:** `os.makedirs(..., mode=0o755, exist_ok=True)`; tolerate dir existing with different perms.
- **Tolerance:** per-WAN read failures emit null rows; snapshot file always writes.

#### Folded todo (resolves_phase: 219)
- `2026-04-17-ingestion-rate-tool.md` → satisfied by `--rolling=60,300,3600`. No additional work beyond INGEST-01..05.

#### Mutation-boundary scope (SAFE-11)

**Allowlisted for additive edits this phase:**
- `src/wanctl/history.py`
- `src/wanctl/operator_summary.py`
- `scripts/phase219-ingestion-digest.py` (new)
- `tests/test_history_ingestion_rate_bucketed.py` (new)
- `tests/fixtures/phase219/` (new; observed-evidence shape only)
- `tests/test_phase219_mutation_boundary.py` (new SAFE-11 boundary test)
- `docs/CONFIGURATION.md` (staleness semantics paragraph; CLI-tool description only)

**Forbidden:**
- `src/wanctl/wan_controller.py`, `queue_controller.py`, `cake_signal.py`
- All RouterOS/CAKE backends, `alert_engine.py`, fusion code
- Anything in the daemon hot path

### Claude's Discretion
- Argparse mutual-exclusion handling between `--by-table`, `--rolling`, and existing `--summary` — least-surprising combination; error odd combos with helpful messages.
- Exact column set for non-JSON (table) view of `--by-table` / `--rolling` — JSON is the contract; reasonable wide-column rendering OK.
- Whether to emit per-snapshot fields in legacy default-flag mode — recommended **yes** for consistency under `--json`.
- `_per_wan_ingestion_rate_bucketed()` internal structure — single SQL pass per DB grouping by `metric_name` vs. N passes per table — planner picks based on existing storage reader patterns.
- `mixed:` rendering ordering — alphabetical is fine.

### Deferred Ideas (OUT OF SCOPE)
- `/health.metrics.ingestion` block — deferred unless Phase 218 audit proves CLI-only insufficient. ARCH-09 stop-line.
- Per-metric category grouping (signal/fusion/alerts/cake_stats) — P2, may layer in Phase 220+ or post-v1.47.
- Anomaly hints (zero-row flagging) — P2.
- Operator-configurable snapshot path (CLI flag or env) — v2+.
- `wanctl-history --ingestion-rate` query speed on >1GB metrics.db — Pitfall 12, revisit only if measured.
- Threshold-based ingestion-rate alerts — explicit anti-feature.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| INGEST-01 | `wanctl-history --ingestion-rate --by-table` flag added additively. Per-WAN × per-table rows/sec. Per-table read failures emit null. | Code Map §A: `_per_wan_ingestion_rate()` at history.py:651-692 + `count_metrics(metrics=[t], wan=...)` reader.py:467-503 already supports the call shape; only one helper to add. |
| INGEST-02 | `wanctl-history --ingestion-rate --rolling=60,300,3600` flag added additively. Multi-window in one call. Default unchanged. | Code Map §A: extend resolve_time + call helper N times with `(now - W, now)` per W; mutually composable with `--by-table`. |
| INGEST-03 | JSON output mode carries `schema_version: 1` plus `_snapshot_unix` and `_snapshot_age_sec` on every row. | Code Map §A: replace `format_ingestion_rate_json()` at history.py:458-489 with envelope; capture `snapshot_unix = int(time.time())` once at handler entry. |
| INGEST-04 | `wanctl-operator-summary --digest` surfaces compact ingestion-rate block. Read-tolerance carries forward. | Code Map §B: extend `print_digest()` at operator_summary.py:152-197; prefer **in-process** call into `history` module (cycle-budget safe since both are out-of-band CLIs); per-WAN read failure → `n/a` line, never abort. |
| INGEST-05 | `scripts/phase219-ingestion-digest.py` cron-callable (not systemd). Calls extended `wanctl-history --ingestion-rate` in JSON mode. Golden SQLite fixture pins `schema_version=1` + both flag shapes. | Code Map §C + §D: subprocess to `python -m wanctl.history --ingestion-rate --by-table --rolling=60,300,3600 --json --from --to`; `state_utils.atomic_write_json()` analog; count-based retention identical to `check_cake_fix.py:_prune_snapshots`. |
| SAFE-11 | Mutation-boundary pytest covers Phase 219 allowlist; additive edits to `src/wanctl/history.py` explicitly allowlisted; controller-path files forbidden. | Code Map §E: clone `tests/test_phase214_mutation_boundary.py` pattern; flip allowlist (additive to history/operator_summary) and confirm forbidden (controller/CAKE/fusion). |
</phase_requirements>

## Project Constraints (from CLAUDE.md)

- **Production network control system. Change conservatively.** stability > safety > clarity > elegance.
- **Flash-wear protection** is a project posture: count-based retention preferred over age-based unlink sweeps. Phase 219 retention (288 most recent files) honors this.
- **SAFE-11 mutation-boundary** is enforced. Controller-path files (`wan_controller.py`, `queue_controller.py`, `cake_signal.py`, backends, `alert_engine.py`, fusion) remain untouched.
- **Hot-path I/O off the 50ms control thread** (ARCH-12) — Phase 219 is entirely CLI/out-of-band; no daemon touches.
- **`/health` payload shape is contractual** (ARCH-09) — Phase 219 explicitly skips daemon-side escalation; CLI is the boundary.
- **Stdlib-only mandate** (Phase 214 D-10) — no new deps; `time`, `os`, `sqlite3`, `json`, `subprocess`, `pathlib` cover all of Phase 219.
- **Project tests/linters before claiming a code change works.** `.venv/bin/pytest tests/test_history_ingestion_rate_bucketed.py -v`, `.venv/bin/ruff check`, `.venv/bin/mypy src/wanctl/`, `.venv/bin/ruff format` before commit.
- **project-finalizer agent MANDATORY before commits.**
- **Quote semantics:** "table" in Phase 219 JSON output = `metric_name` (a logical group within the single physical `metrics` SQL table). See Risks §R1 — research caught this ambiguity. STACK.md's `autorate_metrics / signal_arbitration_metrics` table-name list is **conceptual grouping wording**, not physical SQL tables.

## Executive Summary

Phase 219 is a tightly-scoped, additive extension of the v1.44 Phase 208 `wanctl-history --ingestion-rate` CLI plus a new cron primitive. Every required surface already exists in shipped form and the new behavior layers on cleanly:

1. **`_per_wan_ingestion_rate_bucketed()`** sits beside the existing `_per_wan_ingestion_rate()` at `history.py:651-692`. For each (WAN db, window) it enumerates the metric_name space (`SELECT DISTINCT metric_name FROM metrics WHERE timestamp BETWEEN ? AND ?` — bounded by window, indexed by `idx_metrics_wan_metric_time`) and calls `count_metrics(metrics=[t], wan=wan, ...)` once per metric. Per-table failure → null row; never aborts.
2. **JSON envelope** replaces the v1.44 nested payload at `history.py:458-489` with the locked `{schema_version: 1, rows: [...]}` shape. `snapshot_unix` is captured once at handler entry inside `_handle_special_query` (line 695); `snapshot_age_sec` is computed at emit. This propagates uniformly through default, `--by-table`, and `--rolling` paths.
3. **Operator-summary digest** extends `print_digest()` at `operator_summary.py:152-197` with a second block that calls the new bucketed helper **in-process** (same Python interpreter, no subprocess — `wanctl-operator-summary` is itself an out-of-band CLI so the cycle-budget concern that drives daemon/CLI boundary does not apply). The block emits `operator-summary digest: ingestion-rate wan=X total_rps=N.NN top=...` lines matching the existing `_DIGEST_SKIP_PREFIX` log convention. Per-WAN read failure → `n/a` line, never aborts the summary.
4. **`scripts/phase219-ingestion-digest.py`** is a thin (~120 line) cron primitive: subprocess to `python -m wanctl.history --ingestion-rate --by-table --rolling=60,300,3600 --json`, atomic-rename to `/var/lib/wanctl/snapshots/ingestion/<unix_ts>.json`, count-based retention to 288 files. The atomic-write pattern reuses `state_utils.atomic_write_json` semantics; the retention pattern is a near-verbatim clone of `check_cake_fix.py:_prune_snapshots` (which keeps `MAX_SNAPSHOTS=20`).
5. **Test scaffold** clones the `TestIngestionRateCli` class pattern from `tests/test_history_cli.py:809-1077`: seed an in-memory SQLite fixture with `MetricsWriter`, drive `main()` via `monkeypatch.setattr(sys, "argv", [...])`, snapshot `capsys.readouterr().out` and pin the JSON literal. Add a fixed clock (`monkeypatch.setattr("time.time", lambda: 1767225600.0)`) so `_snapshot_unix` is deterministic.
6. **SAFE-11 boundary** clones `tests/test_phase214_mutation_boundary.py`. New file is `tests/test_phase219_mutation_boundary.py` (new convention `test_phase<N>_mutation_boundary.py`). Allowlist permits additive history/operator_summary diffs; forbid list covers controller/CAKE/fusion/backends.

**Primary recommendation:** Treat this as Phase 208 v1.44 ÷ N. Every pattern exists; no novel architecture. The only research-flagged gotcha is the `table_name` semantics (R1 below): "table" in Phase 219 vocabulary = `metric_name` within the single `metrics` SQL table.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Per-WAN per-metric ingestion query | CLI / out-of-band reader | SQLite WAL DB (read-only URI) | Stays off the 50ms control thread per ARCH-12. The reader already uses `file:<path>?mode=ro`. |
| JSON envelope + `schema_version` emission | CLI formatter | — | Contract surface; pinned by golden fixture. No daemon involvement. |
| Operator-summary ingestion block | Operator-summary CLI (in-process import of `wanctl.history` helpers) | CLI / out-of-band reader | Both processes are out-of-band; in-process import avoids subprocess overhead while remaining a CLI-only path (no `/health` field added). |
| Snapshot persistence (cron) | Filesystem (`/var/lib/wanctl/snapshots/ingestion/`) | CLI / out-of-band reader (subprocess call) | Snapshots persist across reboots — `/run/wanctl` (tmpfs) is wrong. systemd unit explicitly forbidden by INGEST-05; cron is the orchestration tier. |
| SAFE-11 boundary enforcement | Pytest CI gate | git diff | Enforced at every phase boundary; mirrors Phase 214 pattern. |

## Standard Stack

### Core (all already present)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python `sqlite3` (stdlib) | 3.11+ | Read-only metrics DB query via `file:<path>?mode=ro` URI | Project standard since v1.0; `reader.py` is the canonical entry. **[VERIFIED: src/wanctl/storage/reader.py:94, :483]** |
| Python `json` (stdlib) | 3.11+ | Envelope emission + golden-fixture pinning | Pattern from `format_ingestion_rate_json()`. **[VERIFIED: src/wanctl/history.py:458]** |
| Python `argparse` (stdlib) | 3.11+ | New `--by-table` + `--rolling=N,M,K` flags | Pattern from existing `--ingestion-rate` flag. **[VERIFIED: src/wanctl/history.py:558-567]** |
| Python `time` (stdlib) | 3.11+ | `time.time()` for `_snapshot_unix`; monkeypatchable in tests | Standard; the existing code uses `datetime.now().timestamp()` at history.py:618 — `time.time()` is the more conventional source and is what tests will monkeypatch. |
| Python `subprocess` (stdlib) | 3.11+ | Cron script invokes `python -m wanctl.history` | `subprocess.run([sys.executable, "-m", "wanctl.history", ...], capture_output=True, check=True, timeout=30)` — bounded and check-failing. |
| Python `os` + `pathlib` (stdlib) | 3.11+ | Atomic rename, makedirs, glob/unlink for retention | `os.rename`/`os.replace` pattern at `src/wanctl/state_utils.py:62`; `Path.glob` + `unlink` at `src/wanctl/check_cake_fix.py:73-76`. **[VERIFIED: source read]** |
| `tabulate` (existing) | per pyproject | Optional non-JSON (`--by-table` table view) | Already imported by history.py; matches existing `format_ingestion_rate_table()` style. |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `pytest` (existing) | per pyproject | Golden-fixture test + boundary test + CLI smoke | Mandatory before merge. |
| `pytest.monkeypatch` (built-in) | 3.11+ | Override `sys.argv`, `time.time`, `discover_wan_dbs` | Pattern from `tests/test_history_cli.py:842-855`. |
| `pytest.capsys` (built-in) | 3.11+ | Capture stdout for JSON shape assertions | Same pattern as existing TestIngestionRateCli class. |

### Alternatives Considered

| Instead of | Could Use | Tradeoff | Recommendation |
|------------|-----------|----------|----------------|
| In-process import (`from wanctl.history import _per_wan_ingestion_rate_bucketed`) inside operator_summary.py | Subprocess to `python -m wanctl.history ... --json` | In-process: no fork cost, no env-var/PATH issues, exception bubbles directly. Subprocess: process isolation, but adds ~50ms fork overhead per digest call and requires JSON re-parse. | **In-process** — both are out-of-band CLIs; cycle-budget concern that drives daemon/CLI boundary does not apply. Matches the existing pattern: `operator_summary.py` already imports `discover_wan_dbs` from `wanctl.storage.db_utils`. |
| Single SQL pass: `SELECT metric_name, COUNT(*) FROM metrics WHERE timestamp BETWEEN ? AND ? AND wan_name=? GROUP BY metric_name` | N calls to `count_metrics(metrics=[t], ...)` | Single pass: 1 query, indexed scan, faster. N calls: matches existing reader, simpler tolerance per-metric (each metric_name read is independent). | **Single SQL pass** preferred for performance (CONTEXT.md grants planner discretion). Add `count_metrics_grouped_by_name()` helper in `reader.py` or call grouped SQL inline in `history.py`. Per-metric tolerance still works: query failure → empty result → all metrics null for that WAN. |
| `os.rename` | `os.replace` | `os.replace` is the modern stdlib name; cross-platform overwrite-on-Windows; `state_utils.py:62` uses `os.replace`. | **`os.replace`** — matches existing pattern. |
| Custom retention via mtime sort | Filename-sorted glob (timestamps in name → lexicographic = chronological) | mtime is filesystem-dependent; filename is deterministic. Phase 219 names are `<unix_ts>.json` → `sorted(glob)` is correct order. | **Filename sort** — matches `check_cake_fix.py:73`. |

**Installation:** *Nothing to install.* All stdlib + existing project deps.

**Version verification:** No new packages. Verified Python 3.11+ via project `pyproject.toml` and `.venv/bin/python --version`.

## Code Map (file:line for every touch point)

### A. `src/wanctl/history.py` (additive)

| Surface | Current location | Phase 219 change |
|---------|------------------|------------------|
| Existing `--ingestion-rate` argparse flag | `:558-567` (`filter_group.add_argument("--ingestion-rate", ...)`) | Add adjacent `--by-table` (`action="store_true"`) and `--rolling` (`type=str`, comma-list `60,300,3600`). |
| Existing `_per_wan_ingestion_rate(...)` | `:651-692` | Keep as-is. Used by default `--ingestion-rate` path (no `--by-table`, no `--rolling`). |
| New `_per_wan_ingestion_rate_bucketed(...)` | New, sits after `:692` | For each db_path: `SELECT DISTINCT metric_name FROM metrics WHERE timestamp BETWEEN ? AND ?` (bounded by `idx_metrics_wan_metric_time`), then per-metric `count_metrics(..., metrics=[m])`. Returns list of `{wan_db, wan_name, table_name, window_seconds, row_count, rows_per_sec}` rows. Per-metric exception → `row_count=None, rows_per_sec=None`. |
| New `_resolve_windows(args, now)` | New, beside `_resolve_time_range` at `:616-624` | If `args.rolling`: parse comma-list of int seconds → list of `(now - W, now, W)` tuples. Else: one `(start, end, end-start)` tuple. |
| Existing `format_ingestion_rate_json` | `:458-489` | Replace with `format_ingestion_rate_envelope_json(rows, snapshot_unix)` emitting `{schema_version: 1, rows: [...]}` envelope. Each row carries the locked field set + `_snapshot_unix` + `_snapshot_age_sec`. |
| Existing `format_ingestion_rate_table` | `:438-455` | Extend to render `table_name` and `window_seconds` columns when present. Suppress when both are null (default mode). |
| Existing `_handle_special_query` `if args.ingestion_rate:` branch | `:699-716` | Capture `snapshot_unix = int(time.time())` at branch entry. Build window list via `_resolve_windows`. For each window, call bucketed-or-plain helper. Concatenate rows. Emit via formatter (table or JSON). Both `--by-table` and `--rolling` semantics composed by which helper is called and how many times. |
| Argparse mutual-exclusion guard | New (in `create_parser` or `_handle_special_query`) | `--by-table` and `--rolling` require `--ingestion-rate` (else `parser.error(...)`). `--summary` with `--ingestion-rate` is already error-shaped (current code routes `--summary` only when not in special-query path); preserve that. |

### B. `src/wanctl/operator_summary.py` (additive)

| Surface | Current location | Phase 219 change |
|---------|------------------|------------------|
| `_DIGEST_SKIP_PREFIX` log constant | `:20` | Reuse verbatim; add `_DIGEST_INGESTION_PREFIX = "operator-summary digest: ingestion-rate"` for the new block lines. |
| `print_digest(db_paths)` | `:152-197` | After existing per-WAN hard-red loop, add a second loop. For each `db_path`: call new helper `_collect_ingestion_block(db_path)` which imports `from wanctl.history import _per_wan_ingestion_rate_bucketed` (in-process), runs it for the default window (last hour), computes dominant-table per CONTEXT tie-break rule, emits `operator-summary digest: ingestion-rate wan=X total_rps=N.NN top=Y` line. Per-WAN exception → `... wan=X total_rps=n/a top=n/a` line (analog to `_DIGEST_SKIP_PREFIX`). |
| New `_format_ingestion_digest_line(wan_name, rows)` | New, after `_format_digest_line` at `:119` | Take the bucketed rows for ONE wan, compute total `rows_per_sec`, find top-2 by `rows_per_sec`, apply 1.20× tie-break, render string. |
| `create_parser` (`--digest`) | `:217-220` | No change. `--digest` already exists. The new block is unconditional within `--digest`. |
| `print_digest(...)` return value | `dict[str, int]` with `readable/printed/read_skipped/write_skipped` | Keep shape; do not add ingestion counters (would change return contract — caller at `:244-252` only reads these four keys). Track ingestion failures via the same `read_skipped` accumulator when the ingestion sub-call fails. |

### C. `scripts/phase219-ingestion-digest.py` (new)

Structural skeleton (~120 lines stdlib):

| Block | Responsibility |
|-------|----------------|
| Imports | `argparse`, `json`, `os`, `pathlib.Path`, `subprocess`, `sys`, `time` |
| Constants | `SNAPSHOT_DIR = Path("/var/lib/wanctl/snapshots/ingestion")`; `MAX_SNAPSHOTS = 288`; `WANCTL_HISTORY_CMD = [sys.executable, "-m", "wanctl.history", "--ingestion-rate", "--by-table", "--rolling=60,300,3600", "--json"]`; `DEFAULT_WINDOW_SEC = 3600` |
| `_ensure_dir()` | `SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True, mode=0o755)`; catch `PermissionError` → log warning, attempt write anyway. |
| `_call_history(since_ts, until_ts) -> str` | `subprocess.run([..., "--from", iso(since_ts), "--to", iso(until_ts)], capture_output=True, text=True, check=True, timeout=30)`; return `.stdout`. Bounded timeout; CalledProcessError bubbles to `main()`. |
| `_atomic_write(payload_str, snapshot_ts)` | `target = SNAPSHOT_DIR / f"{snapshot_ts}.json"`; `tmp = target.with_suffix(".json.tmp")`; `tmp.write_text(payload_str)`; `os.replace(tmp, target)`; `os.chmod(target, 0o644)`. |
| `_prune_old(max_files=288)` | `files = sorted(SNAPSHOT_DIR.glob("*.json"))`; `while len(files) > max_files: files.pop(0).unlink()`. **Verbatim analog to `src/wanctl/check_cake_fix.py:_prune_snapshots`**. |
| `main() -> int` | Parse argparse (`--window-sec`, `--max-snapshots`, `--snapshot-dir` for tests). Compute `now`, `since`. Call `_call_history`, `_atomic_write`, `_prune_old`. Return 0 on success, 1 on subprocess failure (log to stderr but never raise unhandled). |
| `if __name__ == "__main__": sys.exit(main())` | Standard CLI entry. |

**Cron stanza (documentation only, NOT installed):**
```cron
*/5 * * * * wanctl /opt/wanctl/.venv/bin/python /opt/wanctl/scripts/phase219-ingestion-digest.py >> /var/log/wanctl/ingestion-digest.log 2>&1
```

### D. Test scaffolding (new)

| File | Purpose | Pattern source |
|------|---------|----------------|
| `tests/test_history_ingestion_rate_bucketed.py` | Golden-JSON pin for `--by-table` + `--rolling` shapes. Seeds in-memory SQLite via `MetricsWriter` (4 metric_names × 60 timestamps), drives `main()` via `monkeypatch.setattr(sys, "argv", [...])`, captures `capsys.readouterr().out`, `json.loads` it, pins `schema_version == 1`, pins exact row count = `targets × windows`, pins per-row field set, pins deterministic `_snapshot_unix` (via `monkeypatch.setattr("time.time", lambda: 1767225600.0)`). | `tests/test_history_cli.py:809-1077` (`TestIngestionRateCli`); fixture creation at `:826-840`. |
| `tests/fixtures/phase219/` | Empty for v1 (golden literal lives inline in test). If extracted later, name as `observed_ingestion_envelope_*.json` per SAFE-11 evidence-shape rule. **Forbidden:** `expected_behavior_*.json`. | SAFE-11 — observed-only shape. |
| `tests/test_phase219_mutation_boundary.py` | Clone of `tests/test_phase214_mutation_boundary.py`. Flip allowlist (history.py/operator_summary.py additive diffs OK; controller-path forbidden). Reuse base-SHA resolution heuristic with `PHASE219_BASE_SHA` env override. | `tests/test_phase214_mutation_boundary.py` (verbatim template). |

### E. SAFE-11 mutation-boundary test details

Template `tests/test_phase214_mutation_boundary.py` (159 lines):
- `_phase_base_sha()` at `:56-72` — env override + `merge-base HEAD origin/main` + `HEAD~10` fallback. **Reuse logic; rename env to `PHASE219_BASE_SHA`.**
- `_assert_no_git_diff(paths, label)` at `:75-89` — checks unstaged/staged/committed diffs. **Reuse verbatim.**
- `PROTECTED_PATHS` at `:23` — Phase 214 forbids `src/wanctl/` entirely + Phase 213 scripts. **Phase 219 changes this:** ALLOW additive diffs to `src/wanctl/history.py` and `src/wanctl/operator_summary.py`; FORBID `src/wanctl/wan_controller.py`, `src/wanctl/queue_controller.py`, `src/wanctl/cake_signal.py`, `src/wanctl/backends/**`, `src/wanctl/alert_engine.py`, `src/wanctl/fusion*.py`.
- `FORBIDDEN_MUTATION_RE` at `:27-43` — line-anchored regex flagging mutation tokens in docs/reports. **Reuse verbatim** to keep Phase 219 docs free of threshold-tuning language.

**Implementation note (forbid-list shape):** Use git pathspec exclude pattern. Two passes:
1. `git diff --name-only <base>..HEAD -- 'src/wanctl/*.py' ':!src/wanctl/history.py' ':!src/wanctl/operator_summary.py' ':!src/wanctl/__init__.py'` — should be empty (no other controller-path diffs).
2. `git diff --name-only <base>..HEAD -- 'src/wanctl/history.py' 'src/wanctl/operator_summary.py'` — diffs OK but must be **additive** (this is harder to assert generically; recommend secondary check via `git diff --stat` showing more lines added than removed).

### F. Existing call sites and read-tolerance patterns to follow

| Pattern | Location | Phase 219 use |
|---------|----------|---------------|
| Read-only SQLite open | `src/wanctl/storage/reader.py:94`, `:483` | `sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)` — use verbatim for the new metric_name enumeration query. |
| Per-WAN DB filter by filename | `src/wanctl/history.py:627-648` (`_filter_db_paths_by_wan`) | Reuse for both bucketed and rolling paths. |
| Skip-on-open-fail (digest tolerance) | `src/wanctl/operator_summary.py:169-176` | New ingestion block uses same `try/except (sqlite3.OperationalError, OSError)` + `_DIGEST_SKIP_PREFIX` log line shape. |
| Reader.py count helper | `src/wanctl/storage/reader.py:467-503` (`count_metrics`) | New bucketed helper calls this once per metric_name with `metrics=[m]`. **Alternative (preferred):** add `count_metrics_by_metric_name(db_path, start_ts, end_ts, wan)` helper that returns `dict[str, int]` from a single `GROUP BY metric_name` query — single SQL pass, lower latency. |
| Atomic JSON write | `src/wanctl/state_utils.py:24-70` (`atomic_write_json`) | `phase219-ingestion-digest.py` uses the same pattern (tempfile in same dir → `os.replace`). Could either import or inline; recommend **inline** because scripts/ should not import from src/wanctl/ for boundary-discipline reasons. |
| Count-based snapshot retention | `src/wanctl/check_cake_fix.py:61-76` (`_prune_snapshots`) | **Direct analog.** Phase 219 keeps 288 instead of 20; otherwise identical. |
| Cycle-budget verification post-deploy | `scripts/profiling_collector_json.py` + `scripts/analyze_profiling.py` + `docs/PROFILING.md` runbook | Success criterion #5: re-run Phase 217 capture cycle and verify `cycle_total.avg_ms ≤ 3.0`, `p99_ms ≤ 7.5`. **No code in Phase 219 invokes this** — it's an operator post-deploy step documented in the phase summary. |

## Implementation Approach (per CONTEXT.md decision)

### Step 1: Argparse extension (history.py:558-567)

Add two flags inside the existing `filter_group`:

```python
filter_group.add_argument(
    "--by-table",
    dest="by_table",
    action="store_true",
    help=(
        "With --ingestion-rate: emit per-WAN x per-metric_name rows. "
        "Per-metric_name read failures emit null rows; never aborts the WAN."
    ),
)
filter_group.add_argument(
    "--rolling",
    dest="rolling",
    metavar="SECS,SECS,...",
    type=str,
    default=None,
    help=(
        "With --ingestion-rate: comma-separated rolling window sizes (seconds), "
        "e.g. '60,300,3600'. Emits one row per (WAN, table_name, window_seconds)."
    ),
)
```

Reject combinations: validate inside `_handle_special_query` that `args.by_table or args.rolling` implies `args.ingestion_rate`; else `parser.error(...)`.

### Step 2: Bucketed helper (new, after history.py:692)

```python
def _per_wan_ingestion_rate_bucketed(
    db_paths: list[Path],
    start_ts: int,
    end_ts: int,
    wan: str | None,
) -> tuple[list[dict], int]:
    """Per-WAN x per-metric_name rows. Per-metric failure -> null row."""
    rows: list[dict] = []
    failures = 0
    window_seconds = max(end_ts - start_ts, 1)
    for db_path in db_paths:
        stem = db_path.stem
        wan_name = stem.removeprefix("metrics-") if stem.startswith("metrics-") else stem
        # Single SQL pass: enumerate + count metric_names in window.
        # Indexed by idx_metrics_wan_metric_time(wan_name, metric_name, timestamp).
        try:
            conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
            try:
                where = "WHERE timestamp BETWEEN ? AND ?"
                params: list = [start_ts, end_ts]
                if wan:
                    where += " AND wan_name = ?"
                    params.append(wan)
                sql = (
                    f"SELECT metric_name, COUNT(*) AS cnt FROM metrics "
                    f"{where} GROUP BY metric_name ORDER BY metric_name"
                )
                cursor = conn.execute(sql, params)
                metric_counts = [(row[0], int(row[1])) for row in cursor.fetchall()]
            finally:
                conn.close()
        except (sqlite3.DatabaseError, OSError) as exc:
            logger.warning("Failed bucketed count for %s: %s", db_path.name, exc)
            failures += 1
            # Emit one null row so the WAN is still represented.
            rows.append({
                "wan_db": str(db_path), "wan_name": wan_name,
                "table_name": None, "window_seconds": window_seconds,
                "row_count": None, "rows_per_sec": None,
            })
            continue
        if not metric_counts:
            # Empty window -> single null row for visibility
            rows.append({
                "wan_db": str(db_path), "wan_name": wan_name,
                "table_name": None, "window_seconds": window_seconds,
                "row_count": 0, "rows_per_sec": 0.0,
            })
            continue
        for metric_name, count in metric_counts:
            rows.append({
                "wan_db": str(db_path), "wan_name": wan_name,
                "table_name": metric_name, "window_seconds": window_seconds,
                "row_count": count,
                "rows_per_sec": (count / window_seconds) if window_seconds > 0 else 0.0,
            })
    return rows, failures
```

### Step 3: Rolling window resolver (new)

```python
def _resolve_rolling_windows(args, now: int) -> list[tuple[int, int, int]]:
    """Return [(start_ts, end_ts, window_seconds), ...].

    If --rolling=60,300,3600, returns 3 windows anchored to `now`.
    Else returns single window from --last/--from/--to via _resolve_time_range.
    """
    if args.rolling:
        try:
            secs = [int(s.strip()) for s in args.rolling.split(",")]
        except ValueError:
            raise argparse.ArgumentTypeError(
                f"Invalid --rolling: '{args.rolling}'. Expected comma-separated integers."
            )
        return [(now - w, now, w) for w in secs]
    start_ts, end_ts = _resolve_time_range(args)
    return [(start_ts, end_ts, max(end_ts - start_ts, 1))]
```

### Step 4: Handler composition (history.py:699-716 rewrite)

```python
if args.ingestion_rate:
    if (args.by_table or args.rolling) and not args.ingestion_rate:
        # Defensive; argparse should already enforce.
        return 2
    filtered_paths = _filter_db_paths_by_wan(db_paths, args.wan)
    snapshot_unix = int(time.time())
    now = snapshot_unix
    windows = _resolve_rolling_windows(args, now)
    all_rows: list[dict] = []
    total_failures = 0
    for start_ts_w, end_ts_w, _window_sec in windows:
        if args.by_table:
            rows, failures = _per_wan_ingestion_rate_bucketed(
                filtered_paths, start_ts_w, end_ts_w, args.wan,
            )
        else:
            rows, failures = _per_wan_ingestion_rate(
                filtered_paths,
                start_ts=start_ts_w, end_ts=end_ts_w,
                wan=args.wan, metrics=metrics_list,
            )
            # Add table_name=null per the locked envelope shape.
            for r in rows:
                r.setdefault("table_name", None)
        total_failures += failures
        all_rows.extend(rows)
    if filtered_paths and total_failures == len(filtered_paths) * len(windows):
        print("All metrics databases failed to read.", file=sys.stderr)
        return 1
    if args.json_output:
        print(format_ingestion_rate_envelope_json(all_rows, snapshot_unix))
    else:
        print(format_ingestion_rate_table_v2(all_rows, snapshot_unix))
    return 0
```

### Step 5: Envelope formatter (replace format_ingestion_rate_json)

```python
def format_ingestion_rate_envelope_json(rows: list[dict], snapshot_unix: int) -> str:
    """Phase 219 envelope: {schema_version: 1, rows: [...]}."""
    now = int(time.time())
    out_rows = []
    for r in rows:
        out_rows.append({
            "wan_name": r["wan_name"],
            "wan_db": r["wan_db"],
            "table_name": r.get("table_name"),
            "window_seconds": r["window_seconds"],
            "row_count": r.get("row_count"),
            "rows_per_sec": r.get("rows_per_sec"),
            "_snapshot_unix": snapshot_unix,
            "_snapshot_age_sec": max(0, now - snapshot_unix),
        })
    return json.dumps({"schema_version": 1, "rows": out_rows}, indent=2)
```

### Step 6: Operator-summary integration (operator_summary.py)

```python
# After existing per-WAN hard-red loop in print_digest(), add:
for db_path in db_paths:
    wan_name = _wan_name_from_db_path(db_path)
    try:
        # In-process call; both processes are out-of-band CLIs.
        from wanctl.history import _per_wan_ingestion_rate_bucketed
        rows, _failures = _per_wan_ingestion_rate_bucketed(
            [db_path],
            start_ts=int(time.time()) - 3600,
            end_ts=int(time.time()),
            wan=None,
        )
    except (sqlite3.DatabaseError, OSError) as exc:
        print(
            f"{_DIGEST_SKIP_PREFIX} (ingestion) wan={wan_name} db={db_path}: {exc}",
            file=sys.stderr,
        )
        counts["read_skipped"] += 1
        continue
    line = _format_ingestion_digest_line(wan_name, rows)
    try:
        print(line)
    except OSError as exc:
        print(
            f"{_DIGEST_SKIP_PREFIX} (ingestion-write) wan={wan_name} db={db_path}: {exc}",
            file=sys.stderr,
        )
        counts["write_skipped"] += 1
        continue
    counts["printed"] += 1
```

Where `_format_ingestion_digest_line` implements the 1.20× tie-break:

```python
def _format_ingestion_digest_line(wan_name: str, rows: list[dict]) -> str:
    non_null = [r for r in rows if r.get("rows_per_sec") is not None]
    if not non_null:
        return f"operator-summary digest: ingestion-rate wan={wan_name} total_rps=n/a top=n/a"
    total_rps = sum(r["rows_per_sec"] for r in non_null)
    by_rps = sorted(non_null, key=lambda r: r["rows_per_sec"], reverse=True)
    top = by_rps[0]
    if len(by_rps) == 1 or by_rps[1]["rows_per_sec"] == 0:
        top_str = top["table_name"] or "n/a"
    elif top["rows_per_sec"] >= 1.20 * by_rps[1]["rows_per_sec"]:
        top_str = top["table_name"] or "n/a"
    else:
        names = sorted([by_rps[0]["table_name"] or "n/a", by_rps[1]["table_name"] or "n/a"])
        top_str = f"mixed: {names[0]}/{names[1]}"
    return (
        f"operator-summary digest: ingestion-rate wan={wan_name} "
        f"total_rps={total_rps:.2f} top={top_str}"
    )
```

## Test Strategy (golden fixture pattern + SAFE-11 extension)

### Golden-JSON pin: `tests/test_history_ingestion_rate_bucketed.py`

Pattern source: `tests/test_history_cli.py:809-1077` (`TestIngestionRateCli`). Key elements:

```python
import json, sys
from datetime import datetime
import pytest
from wanctl.history import create_parser, main
from wanctl.storage.writer import MetricsWriter

BASE_TS = 1767225600  # 2026-01-01 00:00:00 (deterministic anchor)

class TestIngestionRateBucketed:
    def _ts_arg(self, ts: int) -> str:
        return datetime.fromtimestamp(ts).isoformat()

    def test_schema_version_pinned(self, tmp_path, monkeypatch, capsys):
        MetricsWriter._reset_instance()
        db_path = tmp_path / "metrics-spectrum.db"
        writer = MetricsWriter(db_path=db_path)
        # Seed 4 metric_names x 60 timestamps = 240 rows.
        for metric_name in ("wanctl_rtt_ms", "wanctl_state",
                            "wanctl_signal_jitter_ms", "wanctl_cake_drop_rate"):
            for i in range(60):
                writer.write_metric(
                    timestamp=BASE_TS + i, wan_name="spectrum",
                    metric_name=metric_name, value=1.0,
                )
        writer.close()
        MetricsWriter._reset_instance()
        # Pin time.time so _snapshot_unix is deterministic.
        monkeypatch.setattr("wanctl.history.time.time", lambda: float(BASE_TS + 60))
        monkeypatch.setattr(sys, "argv", [
            "wanctl-history", "--ingestion-rate", "--by-table", "--json",
            "--from", self._ts_arg(BASE_TS), "--to", self._ts_arg(BASE_TS + 60),
            "--db", str(db_path),
        ])
        rc = main()
        assert rc == 0
        out = capsys.readouterr().out
        payload = json.loads(out)
        assert payload["schema_version"] == 1
        assert isinstance(payload["rows"], list)
        # 4 metric_names x 1 window x 1 WAN = 4 rows.
        assert len(payload["rows"]) == 4
        for row in payload["rows"]:
            assert set(row.keys()) == {
                "wan_name", "wan_db", "table_name", "window_seconds",
                "row_count", "rows_per_sec",
                "_snapshot_unix", "_snapshot_age_sec",
            }
            assert row["_snapshot_unix"] == BASE_TS + 60
            assert row["wan_name"] == "spectrum"
            assert row["row_count"] == 60
            assert row["window_seconds"] == 60

    def test_rolling_emits_one_row_per_window(self, tmp_path, monkeypatch, capsys):
        # Seed same db; assert --rolling=60,300,3600 emits 3 windows
        # (per WAN, in non-by-table default mode).
        # ...
```

Companion tests to cover:
- `--by-table` AND `--rolling=60,300` → cartesian product rows (4 metric_names × 2 windows = 8 rows per WAN).
- Per-metric read failure tolerance (mock `sqlite3.connect` to raise on second call, assert null row emitted).
- Default mode (neither flag) → unchanged from v1.44 envelope shape **except** new `schema_version`, `_snapshot_unix`, `_snapshot_age_sec` fields are emitted; existing v1.44 fields still present (back-compat). **Note:** this is a back-compat decision needing planner confirmation — see Open Questions §Q1.
- Empty DB tolerance (zero-row window).
- `--wan spectrum` filter still works with `--by-table`.

### SAFE-11 boundary: `tests/test_phase219_mutation_boundary.py`

Clone `tests/test_phase214_mutation_boundary.py` structure:

```python
REPO_ROOT = Path(__file__).resolve().parent.parent
PHASE_DIR = REPO_ROOT / ".planning/phases/219-ingestion-rate-observability-scope-d"
ALLOWED_SRC_PATHS = ["src/wanctl/history.py", "src/wanctl/operator_summary.py"]
FORBIDDEN_SRC_PATHS = [
    "src/wanctl/wan_controller.py",
    "src/wanctl/queue_controller.py",
    "src/wanctl/cake_signal.py",
    "src/wanctl/alert_engine.py",
    # Backends subtree
    # Fusion subtree
]

def test_no_forbidden_src_diff():
    """Controller-path files must not change in Phase 219."""
    _assert_no_git_diff(FORBIDDEN_SRC_PATHS, "controller-path")

def test_no_other_src_diff_outside_allowlist():
    """Only history.py and operator_summary.py may diff under src/wanctl/."""
    # git diff src/wanctl/ excluding allowlist must be empty
    pathspec = ["src/wanctl/"] + [f":!{p}" for p in ALLOWED_SRC_PATHS]
    _assert_no_git_diff(pathspec, "src/wanctl/ outside allowlist")

def test_phase219_docs_have_no_threshold_tuning_tokens():
    """SAFE-11: docs/ edits describe new CLI tool only, no tuning language."""
    # Reuse FORBIDDEN_MUTATION_RE from Phase 214 template verbatim.
    # ...
```

### Test suite invocation

Per CLAUDE.md project conventions:
```bash
.venv/bin/pytest tests/test_history_ingestion_rate_bucketed.py -v
.venv/bin/pytest tests/test_phase219_mutation_boundary.py -v
.venv/bin/pytest tests/test_history_cli.py -v  # ensure no v1.44 regressions
.venv/bin/ruff check src/wanctl/history.py src/wanctl/operator_summary.py scripts/phase219-ingestion-digest.py tests/
.venv/bin/mypy src/wanctl/history.py src/wanctl/operator_summary.py
.venv/bin/ruff format src/wanctl/history.py src/wanctl/operator_summary.py scripts/phase219-ingestion-digest.py tests/
```

## Cron Script Pattern (atomic write + retention algorithm + dir creation)

### Reference analog: `src/wanctl/check_cake_fix.py:61-76`

```python
def _prune_snapshots(wan_name: str) -> None:
    if not SNAPSHOT_DIR.exists():
        return
    files = sorted(SNAPSHOT_DIR.glob(f"*_{wan_name}.json"))
    while len(files) > MAX_SNAPSHOTS:
        oldest = files.pop(0)
        oldest.unlink()
```

Phase 219 uses an identical structure, no per-WAN suffix (the JSON envelope already covers all WANs), and `MAX_SNAPSHOTS = 288`. Because filenames are `<unix_ts>.json`, lexicographic sort = chronological sort: correct without `key=lambda p: p.stat().st_mtime`.

### Atomic-rename reference: `src/wanctl/state_utils.py:24-70`

The wanctl-canonical pattern uses `tempfile.mkstemp(suffix=".tmp", prefix=name+".", dir=parent)` + `os.replace`. Phase 219 script may either:
- **Inline this pattern** (recommended for boundary-discipline: `scripts/` should not import from `src/wanctl/`).
- Use the simpler `Path.write_text` + `os.replace` since the JSON payload is small (~10KB) and there is no fsync requirement for cron snapshots (loss of last snapshot under power loss is acceptable).

Recommended inline shape:

```python
def _atomic_write(payload: str, target: Path) -> None:
    tmp = target.with_suffix(target.suffix + ".tmp")
    tmp.write_text(payload, encoding="utf-8")
    os.replace(tmp, target)  # POSIX atomic on same filesystem
```

### Directory creation: `src/wanctl/path_utils.py:29-31` (`ensure_directory_exists(path, mode=0o755)`)

Phase 219 script inlines `Path.mkdir(parents=True, exist_ok=True, mode=0o755)`. Tolerate `PermissionError` (dir exists with different perms — log warning, attempt write anyway per CONTEXT decision). systemd unit files at `deploy/systemd/wanctl@.service:34` already declare `ReadWritePaths=/var/lib/wanctl /var/log/wanctl /run/wanctl` so `/var/lib/wanctl/snapshots/ingestion/` lives inside a path the service mode allows. Cron stanza runs as the `wanctl` user (per CLAUDE.md service-model section); install via:
```bash
sudo install -d -m 0755 -o wanctl -g wanctl /var/lib/wanctl/snapshots/ingestion
```
This step belongs in `docs/` documentation, not in `scripts/install.sh` (which is allowlisted but the cron stanza is documentation-only — operators install crontab manually).

### Snapshot file format

Output of `wanctl-history --ingestion-rate --by-table --rolling=60,300,3600 --json` is the locked envelope:

```json
{
  "schema_version": 1,
  "rows": [
    {"wan_name": "spectrum", "wan_db": "/var/lib/wanctl/metrics-spectrum.db",
     "table_name": "wanctl_rtt_ms", "window_seconds": 60,
     "row_count": 60, "rows_per_sec": 1.0,
     "_snapshot_unix": 1767225660, "_snapshot_age_sec": 0},
    ...
  ]
}
```

`phase219-ingestion-digest.py` writes that raw stdout to `/var/lib/wanctl/snapshots/ingestion/<unix_ts>.json` verbatim. When a later reader opens an old snapshot, `now - _snapshot_unix` yields the meaningful staleness — exactly what Pitfall 7 mandates.

## Validation Architecture (Nyquist)

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest (existing) |
| Config file | `pyproject.toml` + `tests/conftest.py` (existing) |
| Quick run command | `.venv/bin/pytest tests/test_history_ingestion_rate_bucketed.py tests/test_phase219_mutation_boundary.py -v` |
| Full suite command | `.venv/bin/pytest tests/ -q` (with hot-path slice: `.venv/bin/pytest -o addopts='' tests/test_cake_signal.py tests/test_queue_controller.py tests/test_wan_controller.py tests/test_health_check.py -q`) |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|--------------|
| INGEST-01 | `--by-table` emits per-WAN × per-metric_name rows; per-metric failure → null | unit | `pytest tests/test_history_ingestion_rate_bucketed.py::TestIngestionRateBucketed::test_by_table_emits_per_metric_row -x` | ❌ Wave 0 |
| INGEST-02 | `--rolling=60,300,3600` emits one row set per window; default unchanged | unit | `pytest tests/test_history_ingestion_rate_bucketed.py::TestIngestionRateBucketed::test_rolling_emits_one_row_per_window -x` | ❌ Wave 0 |
| INGEST-03 | JSON has `schema_version: 1` + `_snapshot_unix` + `_snapshot_age_sec` on every row | unit | `pytest tests/test_history_ingestion_rate_bucketed.py::TestIngestionRateBucketed::test_schema_version_pinned -x` | ❌ Wave 0 |
| INGEST-04 | `wanctl-operator-summary --digest` renders ingestion block; tolerates per-WAN read failure | unit | `pytest tests/test_history_ingestion_rate_bucketed.py::TestOperatorSummaryDigest -x` | ❌ Wave 0 (extend `tests/test_operator_summary.py` if present, else create) |
| INGEST-05 | `scripts/phase219-ingestion-digest.py` atomic write + count-based retention | unit | `pytest tests/test_phase219_ingestion_digest.py -x` (script invoked with `--snapshot-dir tmp_path --max-snapshots 3`; assert exact file count and rename atomicity) | ❌ Wave 0 |
| SAFE-11 | Mutation-boundary pytest covers Phase 219 allowlist | unit | `pytest tests/test_phase219_mutation_boundary.py -x` | ❌ Wave 0 |
| Success #5 | Post-deploy `cycle_total.avg_ms ≤ 3.0` and `p99_ms ≤ 7.5` | manual-only (production observation) | Operator: run `scripts/profiling_collector_json.py` per `docs/PROFILING.md` runbook, capture ≥1h, verify gates. | manual — phase summary records evidence path |

### Sampling Rate

- **Per task commit:** quick run command (Phase 219-only tests; ~1s)
- **Per wave merge:** full suite + hot-path slice (`.venv/bin/pytest tests/ -q` and the hot-path slice; ~30s for hot-path)
- **Phase gate:** full suite green + mutation-boundary green + post-deploy cycle-budget capture documented in phase SUMMARY before `/gsd-verify-work`

### Wave 0 Gaps

- [ ] `tests/test_history_ingestion_rate_bucketed.py` — covers INGEST-01..03 (and INGEST-04 if operator-summary integration tested here)
- [ ] `tests/test_phase219_ingestion_digest.py` — covers INGEST-05 cron script
- [ ] `tests/test_phase219_mutation_boundary.py` — covers SAFE-11
- [ ] `tests/fixtures/phase219/.gitkeep` — fixture directory placeholder (golden literal stays inline)
- [ ] No framework install needed (`pytest` already in `pyproject.toml`)

## Risks & Landmines

### R1 — "table" semantic ambiguity (HIGH risk; resolve at plan time)

CONTEXT.md says `--by-table` and `table_name`. STACK.md says "metric tables (`autorate_metrics`, `signal_arbitration_metrics`, `irtt_metrics`, `cake_metrics`, `alerts`, …)". **But the schema (`src/wanctl/storage/schema.py:42-65`) has exactly ONE physical metrics table: `metrics`.** Telemetry rows are distinguished by `metric_name` (e.g., `wanctl_rtt_ms`, `wanctl_state`, `wanctl_cake_drop_rate`, etc. — see `STORED_METRICS` dict at schema.py:14-39 for the full namespace).

CONTEXT.md §specifics line 156 disambiguates: *"the new --by-table path should call it with a per-table `metric_names=[t]` filter (one call per table)"*. This locks "table" = `metric_name` (logical group within the `metrics` table). The other physical SQL tables (`alerts`, `benchmarks`, `reflector_events`, `tuning_params`) are **out of scope** for Phase 219 (`--by-table` does NOT enumerate them; they have separate `--alerts` / `--tuning` CLI flags).

**Plan must:**
- Explicitly document this in the new flag's `help=` string.
- Use `table_name` as the JSON field name per CONTEXT lock (don't rename to `metric_name` — preserves the locked envelope).
- Document in CLI help and docs/CONFIGURATION.md: *"`table_name` in the JSON envelope is the `metric_name` of the row in the `metrics` SQL table — wanctl's metrics namespace, see schema.py."*

### R2 — Default-mode envelope back-compat (MEDIUM risk; planner decides)

Today (v1.44), `wanctl-history --ingestion-rate --json` returns:
```json
{"window": {...}, "generated_at": "...", "totals": {...}, "wans": [...]}
```

Tests at `tests/test_history_cli.py:896-921` pin this shape exactly. Phase 219 locks the **NEW** envelope `{schema_version: 1, rows: [...]}`. **The v1.44 envelope is incompatible with the v1.47 envelope.**

Two options:
- **(a) Replace** the v1.44 envelope unconditionally → breaks the existing v1.44 tests at `:862-921`. Test updates required.
- **(b) Conditional** on `--by-table || --rolling` → keep v1.44 envelope for plain `--ingestion-rate --json`; emit Phase 219 envelope when bucketed/rolling. Preserves back-compat but creates schema fork.

CONTEXT.md "Claude's Discretion" §3 says: *"Whether to emit per-snapshot fields in the legacy default-flag mode — recommended yes for consistency (`schema_version` + `_snapshot_unix` + `_snapshot_age_sec` everywhere under `--json`)."* This implies **(a)** — replace unconditionally. Plan must update `tests/test_history_cli.py:862-921` to the new envelope shape and **document the break in the phase SUMMARY**. Mitigation: the v1.44 `--ingestion-rate --json` output had no production-pinned external consumer (operator ad-hoc only); `wanctl-operator-summary --digest` consumes the helper in-process, not the JSON wire format.

### R3 — In-process import couples operator_summary → history (MEDIUM)

Adding `from wanctl.history import _per_wan_ingestion_rate_bucketed` inside `operator_summary.py` creates a new import edge. Both modules are CLI surfaces; neither is on the hot path. The function is single-underscore-private — convention says external callers should not import it. Two mitigations:
- Drop the underscore (rename to `per_wan_ingestion_rate_bucketed`) → publicly importable.
- Or accept the convention break, document the cross-CLI shared helper in a comment.

**Recommendation:** drop the underscore on the new bucketed helper. The existing `_per_wan_ingestion_rate()` can keep its underscore for v1.44 backward compatibility. Future planning may unify.

### R4 — `time.time()` vs `datetime.now().timestamp()` (LOW)

Existing code at `history.py:618` uses `int(datetime.now().timestamp())`. New code should use `int(time.time())` — both return the same value but `time.time()` is more conventional and trivially monkeypatched in tests as shown in §Test Strategy. Plan should import `time` at the top of `history.py` (currently not imported — verified).

### R5 — Subprocess timeout in cron script (LOW)

`subprocess.run(..., timeout=30)` will raise `TimeoutExpired` if `wanctl-history` hangs on a corrupt DB. Cron script must `try/except subprocess.TimeoutExpired` and log to stderr, then return 1 (cron logs the failure; next cron tick retries). Do NOT raise — cron job must always exit cleanly.

### R6 — `/var/lib/wanctl/snapshots/ingestion/` doesn't exist at first run (LOW)

`SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True, mode=0o755)` handles this. But the parent `/var/lib/wanctl/snapshots/` is already used by `check_cake_fix.py` for CAKE audit snapshots. Co-existence is fine — Phase 219 lives in a sibling subdirectory. systemd unit's `ReadWritePaths=/var/lib/wanctl` already covers it. Cron user (`wanctl`) needs write access — verified via `chown -R wanctl:wanctl /var/lib/wanctl` precedent in `scripts/install.sh`.

### R7 — Hot-path-test slice regression (MEDIUM)

Phase 219 does not touch the hot path, but CLAUDE.md's focused hot-path regression slice (`tests/test_cake_signal.py tests/test_queue_controller.py tests/test_wan_controller.py tests/test_health_check.py`) must still pass green per project standard. Phase 219 plan must run this slice in the wave merge step and confirm zero regressions before the SAFE-11 boundary test is allowed to merge.

### R8 — Phase 217 cycle-budget post-deploy verification cadence (LOW)

Success criterion #5 (`cycle_total.avg_ms ≤ 3.0` and `p99_ms ≤ 7.5`) is **post-deploy on production**, not a pre-merge test. The verification step is documented in `docs/PROFILING.md` (already exists; runbook references `scripts/profiling_collector_json.py` + `scripts/analyze_profiling.py`). Phase 219 deploys nothing that touches the hot path, so the expected outcome is "unchanged from Phase 217 baseline (2.883 ms / 6.9 ms over 71,560 samples)". The verification step is operator-driven and recorded in the phase SUMMARY's "Production Verification" section, not gated by pytest.

## Code Examples

### Pattern 1: Read-only SQLite open (from `reader.py:94`)
```python
# Source: src/wanctl/storage/reader.py:94
conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
conn.row_factory = sqlite3.Row
```

### Pattern 2: Per-WAN db filter (from `history.py:627-648`)
```python
# Source: src/wanctl/history.py:627-648 (use verbatim)
def _filter_db_paths_by_wan(db_paths: list[Path], wan: str | None) -> list[Path]:
    if not wan:
        return list(db_paths)
    out: list[Path] = []
    for db_path in db_paths:
        stem = db_path.stem
        if stem.startswith("metrics-"):
            if stem.removeprefix("metrics-") == wan:
                out.append(db_path)
        else:
            out.append(db_path)
    return out
```

### Pattern 3: Atomic write (from `state_utils.py:24-70`)
```python
# Source: src/wanctl/state_utils.py:24-70 (inline-adapted for scripts/)
def atomic_write(payload: str, target: Path) -> None:
    tmp = target.with_suffix(target.suffix + ".tmp")
    tmp.write_text(payload, encoding="utf-8")
    os.replace(tmp, target)  # POSIX atomic on same filesystem
```

### Pattern 4: Count-based retention (from `check_cake_fix.py:61-76`)
```python
# Source: src/wanctl/check_cake_fix.py:61-76 (use verbatim, MAX_SNAPSHOTS=288)
def _prune_old(snapshot_dir: Path, max_snapshots: int = 288) -> None:
    if not snapshot_dir.exists():
        return
    files = sorted(snapshot_dir.glob("*.json"))
    while len(files) > max_snapshots:
        files.pop(0).unlink()
```

### Pattern 5: Digest-line read-tolerance (from `operator_summary.py:169-176`)
```python
# Source: src/wanctl/operator_summary.py:169-176 (extend for ingestion block)
try:
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
except (sqlite3.OperationalError, OSError) as exc:
    print(
        f"{_DIGEST_SKIP_PREFIX} wan={wan_name} db={db_path}: {exc}",
        file=sys.stderr,
    )
    counts["read_skipped"] += 1
    continue
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| v1.44 Phase 208 `--ingestion-rate` single per-WAN row | v1.47 Phase 219 envelope with per-table/per-window rows | v1.47 milestone | Adds per-metric_name granularity; breaks v1.44 JSON consumers (R2). |
| v1.38 `measurement_stale` / `measurement_staleness_sec` fields | Same pattern; new `_snapshot_unix` / `_snapshot_age_sec` for ingestion-rate envelope | v1.47 | Re-uses the v1.38 staleness documentation precedent. |
| Single global ingestion counter (rejected) | Per-WAN × per-metric_name from out-of-band SQL | v1.47 (research-locked) | Pitfall 6 mitigation — Phase 218 audit needs the dimension. |

**Deprecated/outdated:**
- None (Phase 219 is purely additive).

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `SELECT DISTINCT metric_name FROM metrics GROUP BY metric_name` over a bounded window uses `idx_metrics_wan_metric_time` and runs in O(log n) for the index lookup | Implementation §Step 2 | LOW — SQLite query planner verified for this index shape; if slow on >1GB DBs, Pitfall 12 escalation applies (deferred in CONTEXT) |
| A2 | Both `wanctl-history` and `wanctl-operator-summary` are out-of-band CLIs (NOT daemons), so in-process import is cycle-budget-safe | Implementation §Step 6 | LOW — verified via `pyproject.toml` entry_points (both are CLI scripts, neither runs as systemd unit) |
| A3 | `/var/lib/wanctl/snapshots/ingestion/` does not conflict with existing `/var/lib/wanctl/snapshots/` (used by `check_cake_fix.py`) | §R6 | LOW — different subdirectory; both fall under existing systemd `ReadWritePaths` |
| A4 | Cron user is `wanctl` (matches systemd unit user) | §Cron Script Pattern | LOW — documented in CLAUDE.md service-model section; operator confirms at install time |
| A5 | v1.44 `--ingestion-rate --json` has no production-pinned external consumer (operator ad-hoc only); breaking its envelope shape is acceptable | §R2 | MEDIUM — if Phase 218 fallback documentation references the v1.44 JSON shape verbatim, update needed |
| A6 | Phase 219 deploys nothing on the hot path → success criterion #5 cycle-budget gates pass by construction | §R8 | LOW — code map confirms zero controller-path touches |
| A7 | The new bucketed helper should be **public** (no leading underscore) so operator_summary.py can import without convention break | §R3 | LOW — recommendation; planner may choose either fork |

## Open Questions

1. **Q1: Default-mode envelope (R2) — replace v1.44 unconditionally or fork on flag?**
   - What we know: CONTEXT.md "Claude's Discretion" §3 leans replace-unconditionally. v1.44 envelope shape is pinned by `tests/test_history_cli.py:896-921`.
   - What's unclear: are external consumers (e.g., Phase 218 fallback docs, ops scripts on `cake-shaper`) pinned to v1.44 shape?
   - Recommendation: **replace unconditionally**, update v1.44 tests to new envelope, document the break in phase SUMMARY's "Schema Change" subsection. Phase 218 fallback per ROADMAP simply *uses* `wanctl-history --ingestion-rate` — does not pin a JSON shape.

2. **Q2: New helper visibility (R3) — `_per_wan_ingestion_rate_bucketed` vs `per_wan_ingestion_rate_bucketed`?**
   - What we know: Operator-summary needs to import it. Single-underscore is "private" convention.
   - Recommendation: **public name** (`per_wan_ingestion_rate_bucketed`). Existing `_per_wan_ingestion_rate` keeps its underscore.

3. **Q3: Where does the `tests/test_phase219_ingestion_digest.py` live in the success-criteria checklist?**
   - INGEST-05 specifies the golden SQLite fixture test in `tests/test_history_ingestion_rate_bucketed.py`. It does NOT specifically require a separate test for `phase219-ingestion-digest.py` script behavior.
   - Recommendation: **include both** in the plan. The cron script needs its own unit test for retention + atomic-write semantics (it's the most failure-prone surface). Cite INGEST-05 success criterion #3 as covering it.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|-------------|-----------|---------|----------|
| Python 3.11+ | All Phase 219 code | ✓ | 3.12.3 (dev VM) / 3.11+ (production) | — |
| `sqlite3` (stdlib) | All reader/cron code | ✓ | bundled | — |
| `pytest` (existing) | Wave 0 unit tests | ✓ | per pyproject | — |
| `ruff`, `mypy`, `tabulate` (existing) | Lint/type/format/CLI output | ✓ | per pyproject | — |
| `cron` (system) | INGEST-05 scheduling | ✓ | system cron (operator-installed; documented stanza only) | — |
| `/var/lib/wanctl/snapshots/ingestion/` | Cron snapshot persistence | ✗ (will be created at first cron run via `mkdir(parents=True, exist_ok=True, mode=0o755)`) | — | Phase 219 script tolerates parent dir existing with different perms (log + attempt) |
| systemd `ReadWritePaths=/var/lib/wanctl` | Operator-summary in-process access | ✓ | `deploy/systemd/wanctl@.service:34` | — |

**Missing dependencies with no fallback:** None — every dependency is already on the dev VM and production target.

**Missing dependencies with fallback:** The snapshot dir is created at first cron run; no preflight install step blocks the phase.

## Security Domain

Per `.planning/config.json`: `security_enforcement` is not set (default behavior). Phase 219 surface is read-only SQLite + filesystem snapshot writes to a system-state dir already controlled by systemd. No new authentication, no network input, no privilege boundary changes. Brief check:

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | No new auth path |
| V3 Session Management | no | CLI tool, no sessions |
| V4 Access Control | yes | File permissions on `/var/lib/wanctl/snapshots/ingestion/` enforced via `mode=0o755` on dir, `0o644` implicit on snapshot files (read-allowed to operator group; write-restricted to `wanctl` user via systemd unit) |
| V5 Input Validation | yes | `--rolling=N,M,K` is `int(s)` parsed with `ValueError` → `argparse.ArgumentTypeError` (well-defined fail-closed). `subprocess.run` uses argv list (no shell injection). `--from`/`--to` already validated by `parse_timestamp` at history.py:73-106. |
| V6 Cryptography | no | No crypto in Phase 219 |

### Known Threat Patterns for {stack}

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Subprocess shell injection | Tampering | `subprocess.run([list, of, args])` — never `shell=True`. **[VERIFIED: planner template above]** |
| Path traversal on `--snapshot-dir` test override | Tampering | `Path(args.snapshot_dir).resolve()` constraint; default is hardcoded constant; test override is acceptable because it only affects unit tests (not production) |
| SQL injection on metric_name from user input | Tampering | All user-supplied values go through parameterized SQL (`conn.execute(sql, params)` pattern from reader.py); metric_name in `--by-table` is enumerated from the DB itself, not user input |
| TOCTOU on snapshot file rename | Tampering | `os.replace` is atomic on POSIX same-filesystem; matches existing wanctl pattern |
| Resource exhaustion (cron job hangs DB connection) | DoS | `subprocess.run(..., timeout=30)` bounds the call; on `TimeoutExpired` log + return 1, next cron tick proceeds independently |

## Sources

### Primary (HIGH confidence)
- `src/wanctl/history.py:438-715` — existing `--ingestion-rate` implementation **[VERIFIED: source read]**
- `src/wanctl/operator_summary.py:1-287` — existing `print_digest()` + `_DIGEST_SKIP_PREFIX` pattern **[VERIFIED: source read]**
- `src/wanctl/storage/reader.py:94, 467-503` — read-only DB open + `count_metrics` **[VERIFIED: source read]**
- `src/wanctl/storage/schema.py:14-65` — `metrics` SQL table schema + `STORED_METRICS` namespace **[VERIFIED: source read]**
- `src/wanctl/state_utils.py:24-70` — `atomic_write_json` pattern **[VERIFIED: source read]**
- `src/wanctl/check_cake_fix.py:21-76` — count-based snapshot retention **[VERIFIED: source read]**
- `tests/test_history_cli.py:809-1077` — `TestIngestionRateCli` golden-fixture test pattern **[VERIFIED: source read]**
- `tests/test_phase214_mutation_boundary.py:1-159` — SAFE-11 boundary test template **[VERIFIED: source read]**
- `.planning/phases/219-ingestion-rate-observability-scope-d/219-CONTEXT.md` — all 4 gray areas locked **[VERIFIED: source read]**
- `.planning/REQUIREMENTS.md` §v1.47 — INGEST-01..05 + SAFE-11 **[VERIFIED: source read]**
- `.planning/research/PITFALLS.md` — pitfalls 5, 7, 8, 11 inform the locked posture **[VERIFIED: source read]**
- `.planning/research/STACK.md:115-145` — stdlib-only mandate; v1.44 Phase 208 surface inventory **[VERIFIED: source read]**
- `.planning/milestones/v1.46-phases/217-production-cycle-budget-baseline/217-VERIFICATION.md` — Phase 217 baseline 2.883 ms / 6.9 ms over 71,560 samples **[VERIFIED: source read]**
- `deploy/systemd/wanctl@.service:34` — `ReadWritePaths=/var/lib/wanctl /var/log/wanctl /run/wanctl` **[VERIFIED: source read]**

### Secondary (MEDIUM confidence)
- `docs/PROFILING.md` — `wanctl-history --ingestion-rate` is the documented analyze step **[CITED: line 167]**

### Tertiary (LOW confidence)
- None — every fact above is either directly observed in source or pre-locked in CONTEXT.md.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — every dep is stdlib + pre-existing project dep
- Architecture: HIGH — Phase 208 v1.44 is the template; Phase 219 layers on identically
- Pitfalls: HIGH — Pitfall 5/7/8/11 are pre-mitigated by CONTEXT lock; new risks (R1, R2, R3) surfaced from source read

**Research date:** 2026-05-29
**Valid until:** 2026-06-29 (30 days; Phase 208 surface is stable and the v1.47 milestone is scoped LOCKED)

## RESEARCH COMPLETE
