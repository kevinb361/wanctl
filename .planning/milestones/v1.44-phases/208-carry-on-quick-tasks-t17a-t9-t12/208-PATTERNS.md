# Phase 208: Carry-on quick-tasks (T17a / T9 / T12) - Pattern Map

**Mapped:** 2026-05-15
**Files analyzed:** 6 modified + 4 test files extended (10 targets)
**Analogs found:** 10 / 10 (every target has at least an in-file analog)

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `scripts/soak_summary_aggregate.py` | aggregator/script | transform (NDJSON→JSON) | self (`_failed_completed_window_distribution()` + existing `aggregate_watchdog()`) | exact (in-file template) |
| `tests/test_phase_204_watchdog.py` (extend) | test | request-response | self (`TestWatchdogMath`, `TestLegacyGateRemovalContract`) | exact |
| `tests/test_phase_204_replay.py` (extend, optional) | test | golden round-trip | self + `tests/test_phase_204_distribution.py::test_aggregate_soak_matches_golden` | exact |
| `tests/test_phase_204_distribution.py` (extend, optional) | test | golden round-trip | self (`test_aggregate_soak_matches_golden`) | exact |
| `src/wanctl/history.py` (extend) | CLI | request-response | self (`_handle_special_query()` for `--tins`/`--tuning`/`--alerts`) | exact |
| `src/wanctl/storage/reader.py` (extend) | reader/query | CRUD (read-only) | self (`count_metrics()`) | exact |
| `src/wanctl/storage/db_utils.py` (reuse only) | discovery | partial-failure read | self (`discover_wan_dbs()`, `query_all_wans()`) | exact |
| `tests/test_history_cli.py` (extend) | test | request-response | self (`TestPerTinHistory` / `_handle_special_query` mocked via `patch("wanctl.history.query_metrics")`) | exact |
| `src/wanctl/operator_summary.py` (modify) | CLI | request-response | self (`print_digest()` + `main()` digest branch) | exact |
| `tests/test_operator_digest.py` (extend) | test | request-response | self (`test_main_digest_outputs_per_wan_summary`) | exact |

All Phase 208 work fits within already-established patterns in the same files; no cross-module analog search is needed.

---

## Pattern Assignments

### `scripts/soak_summary_aggregate.py` — `aggregate_watchdog()` fail-closed guard (TOOL-01 / D-01, D-02)

**Analog:** self — `aggregate_watchdog()` (lines 290-335) and `_failed_completed_window_distribution()` (lines 248-260).

**Current bug (lines 303-312)** — the `else: cell = {}` branch silently passes a `0.0` value when `gate_column` is unrecognized, then `dist_valid and new_value <= new_threshold` returns `pass` because `dist_valid` is `True` (the distribution itself is fine; the misconfig is in column selection):

```python
if gate_column == "suppressions_completed_window_count_distribution":
    cell = dist
elif gate_column.startswith("by_cause."):
    cause = gate_column.split(".", 1)[1]
    cell = dist.get("by_cause", {}).get(cause, {})
else:
    cell = {}

dist_valid = bool(dist.get("valid", True))
new_value = float(cell.get(statistic, 0.0)) if cell and dist_valid else 0.0
```

Two false-pass holes:
1. Unknown `gate_column` → `cell = {}` → `new_value = 0.0` → `verdict = "pass"`.
2. Unknown `statistic` (e.g. typo) → `cell.get(statistic, 0.0)` → `0.0` → `verdict = "pass"`.
3. `by_cause.<unknown>` → `dist["by_cause"].get(cause, {})` → `cell = {}` → same hole.

**Fail-closed shape to copy** (already used in lines 248-260 for missing-boundary failure):

```python
def _failed_completed_window_distribution(reason: str) -> dict[str, Any]:
    result = _distribution_from_boundaries([])
    result["valid"] = False
    result["boundary_source"] = "missing"
    result["reason"] = reason
    ...
```

**Pattern to apply in `aggregate_watchdog()`** — detect misconfig early, compute `config_reason: str | None`, then short-circuit to a `fail` verdict while preserving the existing block shape (name/computation/value/threshold/statistic/headroom_factor/gate_column/verdict/reason/operator_approval). Roughly:

```python
KNOWN_STATISTICS = {"mean", "p50", "p95", "p99", "max"}  # match _distribution_from_boundaries keys
KNOWN_TOP_LEVEL = {"suppressions_completed_window_count_distribution"}

config_reason: str | None = None
if gate_column in KNOWN_TOP_LEVEL:
    cell = dist
elif gate_column.startswith("by_cause."):
    cause = gate_column.split(".", 1)[1]
    if cause not in CAUSES:
        cell = {}
        config_reason = f"unknown gate_column cause: {gate_column!r}"
    else:
        cell = dist.get("by_cause", {}).get(cause, {})
else:
    cell = {}
    config_reason = f"unknown gate_column: {gate_column!r}"

if config_reason is None and statistic not in KNOWN_STATISTICS:
    config_reason = f"unsupported statistic: {statistic!r}"

dist_valid = bool(dist.get("valid", True))
config_ok = config_reason is None
new_value = float(cell.get(statistic, 0.0)) if cell and dist_valid and config_ok else 0.0
verdict = "pass" if dist_valid and config_ok and new_value <= new_threshold else "fail"
reason = config_reason or (None if dist_valid else dist.get("reason"))
```

**Critical contract bits (D-02):**
- Output **shape stays identical**: keep returning `{"secondary_gate_completed_window": {...}}` with the same 10 keys.
- `value` is `0.0` on misconfig (per D-02).
- `reason` is non-null and **names the unknown `gate_column` or `statistic`** (assertable substring).
- Do **not** raise from `aggregate_watchdog()` — fail in-band.

---

### `tests/test_phase_204_watchdog.py` — extend with invalid-config cases (TOOL-01 / D-03)

**Analog:** self — existing `TestWatchdogMath` class (lines 85-122) and `TestLegacyGateRemovalContract` (lines 125-149).

**Test pattern to copy** (lines 96-105):

```python
def test_synthetic_pass_branch(self, aggregator: ModuleType) -> None:
    result = aggregator.aggregate_watchdog(
        _make_rows([10, 10, 10]),
        new_threshold=100,
        statistic="p99",
        gate_column="by_cause.dwell_hold",
    )
    block = result["secondary_gate_completed_window"]
    assert block["value"] == pytest.approx(10.0)
    assert block["verdict"] == "pass"
```

**New tests to add** (same module-scope `aggregator` fixture + `_make_rows()` helper, lines 41-43, 46-82):

```python
def test_unknown_gate_column_fails_closed(self, aggregator: ModuleType) -> None:
    result = aggregator.aggregate_watchdog(
        _make_rows([10]),
        new_threshold=100,
        statistic="p99",
        gate_column="by_cause.bogus_cause",
    )
    block = result["secondary_gate_completed_window"]
    assert block["verdict"] == "fail"
    assert block["value"] == 0.0
    assert block["reason"] is not None
    assert "bogus_cause" in block["reason"]
    # Shape stability
    assert set(result) == {"secondary_gate_completed_window"}

def test_unknown_statistic_fails_closed(self, aggregator: ModuleType) -> None:
    result = aggregator.aggregate_watchdog(
        _make_rows([10]),
        new_threshold=100,
        statistic="p42",  # unsupported
        gate_column="by_cause.dwell_hold",
    )
    block = result["secondary_gate_completed_window"]
    assert block["verdict"] == "fail"
    assert block["value"] == 0.0
    assert "p42" in block["reason"]
```

**Golden round-trip (D-03)** — already exists in `tests/test_phase_204_distribution.py::test_aggregate_soak_matches_golden` (byte-equal compare against `tests/fixtures/phase_204_synthetic_summary.json`). Add a second golden fixture file for the v1.44 fresh-style summary if and only if the v1.43 fixture does not already cover the legacy-absent contract — the existing fixture is post-HRDN-03 so it likely already does. The replay test `tests/test_phase_204_replay.py::test_aggregate_soak_v142_emits_only_completed_window_gate` (lines 49-56) already asserts `"secondary_gate_legacy" not in result` for v1.42 NDJSON.

**Golden compare pattern (copy verbatim shape):**

```python
def test_aggregate_soak_matches_golden() -> None:
    aggregator = _load_module(AGGREGATOR_PATH, "soak_aggregator")
    result = aggregator.aggregate_soak(SYNTHETIC_NDJSON)
    golden = json.loads(SYNTHETIC_SUMMARY.read_text(encoding="utf-8"))
    assert json.dumps(result, sort_keys=True, indent=2) == json.dumps(
        golden, sort_keys=True, indent=2
    )
```

If the planner decides the golden fixture needs to be regenerated because the watchdog block's `reason` field changed (now non-null only on actual failure — should still be `None` on the synthetic-pass golden), the regeneration command is `python scripts/soak_summary_aggregate.py tests/fixtures/phase_204_synthetic_capture.ndjson -o tests/fixtures/phase_204_synthetic_summary.json`.

---

### `src/wanctl/storage/reader.py` — new `count_metrics_in_range()` or reuse `count_metrics()` (TOOL-02 / D-08, D-09)

**Analog:** self — `count_metrics()` (lines 467-503) is the exact template. It already supports `start_ts`, `end_ts`, `metrics`, `wan`, `granularity` and returns a plain `int`, opening read-only and handling missing-DB / OperationalError gracefully.

**Pattern to copy verbatim** (lines 467-503):

```python
def count_metrics(
    db_path: Path | str = DEFAULT_DB_PATH,
    start_ts: int | None = None,
    end_ts: int | None = None,
    metrics: list[str] | None = None,
    wan: str | None = None,
    granularity: str | None = None,
) -> int:
    """Count metrics rows matching the provided filters."""
    db_path = Path(db_path)

    if not db_path.exists():
        logger.debug("Database not found: %s", db_path)
        return 0

    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    except sqlite3.OperationalError as e:
        logger.warning("Failed to open database: %s", e)
        return 0

    try:
        where_sql, params = _build_metrics_filter_sql(...)
        sql = "SELECT COUNT(*) " + where_sql
        row = conn.execute(sql, params).fetchone()
        return int(row[0]) if row is not None else 0
    except sqlite3.OperationalError as e:
        logger.debug("Count query failed: %s", e)
        return 0
    finally:
        conn.close()
```

**Reuse strategy (preferred):** `count_metrics()` already exists with the exact signature needed. TOOL-02 should reuse it directly via `query_all_wans(count_metrics, ...)` rather than adding a new function. Note that `query_all_wans()` expects `Callable[..., list[dict]]` returning a list — `count_metrics()` returns an `int`, so the planner has two options:

1. **Wrap inline** in `history.py`: iterate `db_paths` directly (single-purpose loop) calling `count_metrics(db_path=p, ...)` per WAN, catching `(sqlite3.DatabaseError, OSError)` the same way `query_all_wans()` does (db_utils.py lines 70-75). This matches D-09 (reuse discovery) without forcing a type change to `query_all_wans()`.
2. **Add a `_count_metrics_as_rows()` shim** that returns `[{"wan_db": str(db_path), "row_count": count_metrics(...)}]` so `query_all_wans()` can be used unchanged.

Recommend option 1 — simpler and keeps `count_metrics()` semantically pure.

**Per-WAN discovery loop pattern (copy from db_utils.py lines 60-80):**

```python
from wanctl.storage.db_utils import discover_wan_dbs
from wanctl.storage.reader import count_metrics

def _per_wan_ingestion_rate(
    db_paths: list[Path],
    start_ts: int,
    end_ts: int,
    wan: str | None,
    metrics: list[str] | None,
    granularity: str | None,
) -> tuple[list[dict], int]:
    """Returns (rows, failure_count). rows: per-WAN {wan_db, wan_name, row_count, rows_per_sec}."""
    rows: list[dict] = []
    failures = 0
    window_seconds = max(end_ts - start_ts, 1)  # avoid div-by-zero
    for db_path in db_paths:
        wan_name = db_path.stem.removeprefix("metrics-") if db_path.stem.startswith("metrics-") else db_path.stem
        try:
            count = count_metrics(
                db_path=db_path,
                start_ts=start_ts,
                end_ts=end_ts,
                metrics=metrics,
                wan=wan,
                granularity=granularity,
            )
        except (sqlite3.DatabaseError, OSError) as exc:
            logger.warning("Failed to count %s, skipping: %s", db_path.name, exc)
            failures += 1
            continue
        rows.append({
            "wan_db": str(db_path),
            "wan_name": wan_name,
            "row_count": count,
            "window_seconds": window_seconds,
            "rows_per_sec": count / window_seconds,
        })
    return rows, failures
```

Note: `_wan_name_from_db_path()` already exists in `operator_summary.py` (lines 109-112) using the exact `metrics-` prefix-stripping convention. Either import that helper or inline it — inlining matches the existing pattern in `db_utils.py`/`reader.py` (no cross-module helper sharing).

---

### `src/wanctl/history.py` — `--ingestion-rate` flag (TOOL-02 / D-05..D-10)

**Analog:** self — `_handle_special_query()` (lines 554-620) handles `--tins`, `--tuning`, `--alerts`. `--ingestion-rate` slots in as a fourth case with identical structure.

**Parser pattern (copy from lines 480-505):**

```python
filter_group.add_argument(
    "--ingestion-rate",
    dest="ingestion_rate",
    action="store_true",
    help="Show per-WAN metrics ingestion rate (rows/sec) over the selected window",
)
```

Place it in the existing `filter_group` (line 479-505) alongside `--alerts`, `--tuning`, `--tins`. Respect existing time range / `--wan` / `--metrics` / `--db` flags — no new time/discovery surface.

**Dispatch pattern (copy from `_handle_special_query` block, lines 558-576):**

```python
if args.ingestion_rate:
    rows, failures = _per_wan_ingestion_rate(
        db_paths,
        start_ts=start_ts,
        end_ts=end_ts,
        wan=args.wan,
        metrics=metrics_list,  # if --metrics passed, scope to that subset
        granularity=None,      # ingestion rate is across all granularities by default
    )
    if failures == len(db_paths):
        print("All metrics databases failed to read.", file=sys.stderr)
        return 1
    if args.json_output:
        print(format_ingestion_rate_json(rows, start_ts, end_ts))
    else:
        print(format_ingestion_rate_table(rows, start_ts, end_ts))
    return 0
```

`metrics_list` parsing already happens later (line 651-653); for `--ingestion-rate` it needs to happen before dispatch — either move the parse up, or duplicate the 2 lines inside the new branch (the parser pattern preserves locality).

**Table formatter pattern (copy from `format_tins_table` lines 345-399 — tabulate, simple format):**

```python
def format_ingestion_rate_table(rows: list[dict], start_ts: int, end_ts: int) -> str:
    """Per-WAN ingestion rate. D-06: WAN/db identity, window, row count, rows/sec, windowed mean."""
    window_seconds = max(end_ts - start_ts, 1)
    headers = ["WAN", "Database", "Window", "Rows", "Rows/sec", "Mean Rows/sec"]
    out = []
    for r in rows:
        out.append([
            r["wan_name"],
            r["wan_db"],
            f"{format_timestamp(start_ts)}..{format_timestamp(end_ts)}",
            r["row_count"],
            format_value(r["rows_per_sec"]),
            # windowed mean uses requested window (D-08) — equal to rows/sec because
            # the per-WAN row_count is already scoped to the same [start_ts, end_ts]
            format_value(r["row_count"] / window_seconds),
        ])
    return tabulate(out, headers=headers, tablefmt="simple")
```

Note D-06 calls out "rows/sec" and "requested-window mean rows/sec" as distinct columns. If they collapse to the same number in this implementation, either keep both columns for clarity (matches D-06 wording) or document the equivalence in the help text. Planner discretion per CONTEXT line 54.

**JSON formatter pattern (D-07: object-shaped, not array) — depart from existing list-shaped `format_json()` (line 169-178):**

```python
def format_ingestion_rate_json(rows: list[dict], start_ts: int, end_ts: int) -> str:
    """D-07: stable object with top-level window metadata and wans array."""
    window_seconds = max(end_ts - start_ts, 1)
    total_rows = sum(r["row_count"] for r in rows)
    payload = {
        "window": {
            "start_ts": start_ts,
            "end_ts": end_ts,
            "start_iso": datetime.fromtimestamp(start_ts).isoformat(),
            "end_iso": datetime.fromtimestamp(end_ts).isoformat(),
            "window_seconds": window_seconds,
        },
        "generated_at": datetime.now().isoformat(),
        "totals": {
            "row_count": total_rows,
            "rows_per_sec": total_rows / window_seconds,
            "wan_count": len(rows),
        },
        "wans": [
            {
                "wan_name": r["wan_name"],
                "wan_db": r["wan_db"],
                "row_count": r["row_count"],
                "rows_per_sec": r["rows_per_sec"],
                "mean_rows_per_sec_windowed": r["row_count"] / window_seconds,
            }
            for r in rows
        ],
    }
    return json.dumps(payload, indent=2)
```

**Why object-shaped (D-07 rationale):** existing `format_json()` returns a bare array because per-row records are the unit of meaning. For ingestion-rate, window metadata + aggregate totals are first-class — a bare array forces consumers to compute them per-call. Object shape lets future fields (per-metric breakdown per D-10, sampling cadence, etc.) be added without breaking parsers.

---

### `tests/test_history_cli.py` — extend with ingestion-rate tests (TOOL-02 / D-05..D-08)

**Analog:** self — `TestPerTinHistory` class (lines 616-806) is the exact template for parser flag + mocked-query + table-shape + JSON-shape + no-data assertions.

**Parser test pattern (copy from lines 619-623):**

```python
def test_ingestion_rate_flag_recognized(self):
    parser = create_parser()
    args = parser.parse_args(["--ingestion-rate", "--last", "1h"])
    assert args.ingestion_rate is True
```

**Mocked-query monkeypatch pattern (copy from lines 625-667):**

```python
def test_ingestion_rate_queries_count(self, tmp_path, monkeypatch, capsys):
    MetricsWriter._reset_instance()
    db_path = tmp_path / "metrics-spectrum.db"
    writer = MetricsWriter(db_path=db_path)
    now = int(datetime.now().timestamp())
    for i in range(60):
        writer.write_metric(timestamp=now - i, wan_name="spectrum",
                            metric_name="wanctl_rtt_ms", value=15.0)
    writer.close()
    MetricsWriter._reset_instance()

    monkeypatch.setattr(sys, "argv",
        ["wanctl-history", "--ingestion-rate", "--last", "1h", "--db", str(db_path)])
    assert main() == 0
    out = capsys.readouterr().out
    assert "spectrum" in out
    assert "Rows/sec" in out or "rows_per_sec" in out
```

**JSON-shape assertion pattern (copy from lines 440-462, then enforce D-07 object shape):**

```python
def test_ingestion_rate_json_is_object_shaped(self, tmp_path, monkeypatch, capsys):
    # ... populate db_path ...
    monkeypatch.setattr(sys, "argv",
        ["wanctl-history", "--ingestion-rate", "--json", "--last", "1h", "--db", str(db_path)])
    assert main() == 0
    payload = json.loads(capsys.readouterr().out)
    # D-07: top-level dict, not bare array
    assert isinstance(payload, dict)
    assert "window" in payload
    assert "generated_at" in payload
    assert "wans" in payload
    assert isinstance(payload["wans"], list)
    # D-06: per-row context
    assert payload["wans"][0]["wan_name"] == "spectrum"
    assert "row_count" in payload["wans"][0]
    assert "rows_per_sec" in payload["wans"][0]
```

**No-data / single-WAN-with-zero-rows pattern (copy from `test_tins_no_data` lines 750-774).**

---

### `src/wanctl/operator_summary.py` — `print_digest()` permission guard (TOOL-03 / D-11..D-16)

**Analog:** self — `print_digest()` (lines 148-156) + `main()` digest branch (lines 187-193).

**Current code (lines 148-156):**

```python
def print_digest(db_paths: list[Path]) -> None:
    if not db_paths:
        print("no WAN DBs discovered")
        return

    for db_path in db_paths:
        with sqlite3.connect(db_path) as conn:
            rows = _query_digest_rows(conn)
        print(_format_digest_line(_wan_name_from_db_path(db_path), rows))
```

**Current main() digest branch (lines 187-193):**

```python
if args.digest:
    try:
        print_digest(discover_wan_dbs())
    except (OSError, sqlite3.DatabaseError, json.JSONDecodeError, TypeError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0
```

Problem: any single unreadable DB raises, hits the broad `except` in `main()`, prints once to stderr, and returns `1` — the whole digest dies on the first inaccessible WAN. Also, D-13 requires narrowing the OSError to be the catchable case, not bundled with sqlite/json/type/value errors.

**Pattern to apply (narrow per-iteration guard, D-11..D-16):**

```python
# Stable stderr prefix for tests (D-14)
_DIGEST_SKIP_PREFIX = "operator-summary digest: skipped"

def print_digest(db_paths: list[Path]) -> int:
    """Print per-DB hard-red digest. Returns count of readable DBs successfully printed."""
    if not db_paths:
        print("no WAN DBs discovered")
        return 0

    printed = 0
    for db_path in db_paths:
        wan_name = _wan_name_from_db_path(db_path)
        # D-12: unreadable DB → skip with stable stderr message, continue
        try:
            with sqlite3.connect(f"file:{db_path}?mode=ro", uri=True) as conn:
                rows = _query_digest_rows(conn)
        except (sqlite3.OperationalError, OSError) as exc:
            # Narrow: permission/IO failure opening or reading the DB
            print(
                f"{_DIGEST_SKIP_PREFIX} wan={wan_name} db={db_path}: {exc}",
                file=sys.stderr,
            )
            continue
        line = _format_digest_line(wan_name, rows)
        # D-13: output/write OSError → skip line, continue (narrow to OSError only)
        try:
            print(line)
        except OSError as exc:
            print(
                f"{_DIGEST_SKIP_PREFIX} wan={wan_name} db={db_path} (write): {exc}",
                file=sys.stderr,
            )
            continue
        printed += 1
    return printed
```

**Main() change (D-16):**

```python
if args.digest:
    db_paths = discover_wan_dbs()
    printed = print_digest(db_paths)
    # D-16: zero readable DBs from a non-empty discovery → stable message, exit 0
    if db_paths and printed == 0:
        print("no readable WAN DBs - try sudo", file=sys.stderr)
    return 0
```

**Key contract bits:**
- **D-13 narrowing:** only catch `(sqlite3.OperationalError, OSError)` around DB open/query, only `OSError` around output write. Do **not** catch `sqlite3.DatabaseError` broadly — corrupt schemas should still surface on the existing error path (a separate `main()` outer try if needed). D-13 explicitly says "Keep sqlite/json/type/programming errors on existing error paths unless they are the specific unreadable-DB case being guarded." `sqlite3.OperationalError` covers "unable to open database file" and "authorization denied" — the actual permission failure modes. `sqlite3.DatabaseError` is the broader parent for corruption; leave it on the existing path.
- **D-14 stable prefix:** `operator-summary digest: skipped wan=<wan> db=<path>: <os-error-text>` — tests assert prefix + `wan=`/`db=` context, not the full OS error text.
- **D-16 exit code:** all-skipped is **exit 0** with a stderr hint, not a failure. Distinguishes "operator forgot sudo" from "actual bug".

**Read-only DB open (defensive)** — the current code uses `sqlite3.connect(db_path)` which can create the file if the path is wrong and permits writes. The reader module uses `sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)` (reader.py line 94). Switching `print_digest()` to read-only mode is a free win and makes the OperationalError surface cleaner on permission failures.

---

### `tests/test_operator_digest.py` — extend with permission/write guard tests (TOOL-03 / D-14, D-15)

**Analog:** self — `test_main_digest_outputs_per_wan_summary` (lines 78-95) is the exact template for monkeypatching `discover_wan_dbs` and `sys.argv`.

**Existing monkeypatch pattern (lines 84-88):**

```python
monkeypatch.setattr(
    "wanctl.operator_summary.discover_wan_dbs",
    lambda: [db_path],
)
monkeypatch.setattr(sys, "argv", ["wanctl-operator-summary", "--digest"])
```

**New test pattern — unreadable-DB skip (D-15 deterministic injection):**

```python
def test_digest_skips_unreadable_db(tmp_path, monkeypatch, capsys):
    """D-12/D-14/D-15: permission failure on one DB → skip with stable prefix, exit 0."""
    good_db = tmp_path / "metrics-spectrum.db"
    _create_alerts_db(good_db)
    bad_db = tmp_path / "metrics-att.db"
    # Don't create it; we'll inject an OperationalError via monkeypatch instead.

    real_connect = sqlite3.connect

    def fake_connect(target, *args, **kwargs):
        # Match the read-only URI form used by print_digest
        if "metrics-att" in str(target):
            raise sqlite3.OperationalError("unable to open database file")
        return real_connect(target, *args, **kwargs)

    monkeypatch.setattr("wanctl.operator_summary.sqlite3.connect", fake_connect)
    monkeypatch.setattr(
        "wanctl.operator_summary.discover_wan_dbs",
        lambda: [good_db, bad_db],
    )
    monkeypatch.setattr(sys, "argv", ["wanctl-operator-summary", "--digest"])

    assert main() == 0  # D-16: skip is not a failure
    captured = capsys.readouterr()
    # Good DB still produced output
    assert "spectrum:" in captured.out
    # Bad DB produced stable-prefix skip on stderr (D-14)
    assert "operator-summary digest: skipped" in captured.err
    assert "wan=att" in captured.err
    assert "db=" in captured.err
    # D-15 anti-pattern: do NOT assert the full OS error text
```

**New test pattern — all-DBs-unreadable (D-16):**

```python
def test_digest_all_unreadable_exits_zero_with_hint(tmp_path, monkeypatch, capsys):
    db_a = tmp_path / "metrics-spectrum.db"
    db_b = tmp_path / "metrics-att.db"

    def fake_connect(target, *args, **kwargs):
        raise sqlite3.OperationalError("unable to open database file")

    monkeypatch.setattr("wanctl.operator_summary.sqlite3.connect", fake_connect)
    monkeypatch.setattr(
        "wanctl.operator_summary.discover_wan_dbs",
        lambda: [db_a, db_b],
    )
    monkeypatch.setattr(sys, "argv", ["wanctl-operator-summary", "--digest"])

    assert main() == 0
    captured = capsys.readouterr()
    assert "no readable WAN DBs" in captured.err
    assert "try sudo" in captured.err
```

**New test pattern — output-write OSError (D-13, D-15):**

```python
def test_digest_skips_on_output_write_oserror(tmp_path, monkeypatch, capsys):
    db_path = tmp_path / "metrics-spectrum.db"
    _create_alerts_db(db_path)

    # Inject OSError at the print() boundary by monkeypatching builtins.print
    # specifically for stdout writes inside print_digest. Cleaner: monkeypatch
    # sys.stdout.write or use a custom file-like that raises.
    real_print = print
    def fake_print(*args, file=None, **kwargs):
        if file is None or file is sys.stdout:
            raise OSError("disk full")
        return real_print(*args, file=file, **kwargs)

    monkeypatch.setattr("builtins.print", fake_print)
    monkeypatch.setattr(
        "wanctl.operator_summary.discover_wan_dbs",
        lambda: [db_path],
    )
    monkeypatch.setattr(sys, "argv", ["wanctl-operator-summary", "--digest"])

    assert main() == 0
    captured = capsys.readouterr()
    assert "operator-summary digest: skipped" in captured.err
    assert "(write)" in captured.err
```

The `builtins.print` monkeypatch is messy; an alternative is to refactor `print_digest()` to take an injectable `out_stream` parameter and swap that in the test — planner discretion. The cleaner injection point is `sys.stdout` itself or wrapping `print(line)` in a one-line `_emit_line()` helper that can be monkeypatched.

**D-15 anti-pattern (do NOT do):** chmod-based permission tests (`os.chmod(db, 0o000)`) — root in CI bypasses the bit, making the test flaky. Always inject via monkeypatch of `sqlite3.connect` or the write boundary.

---

## Shared Patterns

### Per-WAN DB Discovery + Partial-Failure Read

**Source:** `src/wanctl/storage/db_utils.py` (entire file, 80 lines).

**Apply to:** TOOL-02 (`history.py` ingestion-rate dispatch), TOOL-03 (`operator_summary.py` digest — already uses `discover_wan_dbs()`).

**Key contract (lines 14-17):**
- One unreadable DB → log warning, continue with others.
- Every DB fails → `all_failed=True` on result.
- Only `sqlite3.DatabaseError` and `OSError` caught; programmer bugs surface.

```python
for db_path in paths:
    try:
        results.extend(query_fn(db_path=db_path, **kwargs))
    except (sqlite3.DatabaseError, OSError) as exc:
        failures += 1
        logger.warning("Failed to query %s, skipping: %s", db_path.name, exc)
```

TOOL-03's D-13 narrows further to `(sqlite3.OperationalError, OSError)` because `sqlite3.DatabaseError` includes corruption — that should keep raising, not be auto-skipped per-DB.

### Stable-stderr-prefix Convention (NEW for Phase 208 — TOOL-03)

**Source:** new in this phase; closest existing analogs are positional messages like `print(f"Database not found: {args.db}. Run wanctl to generate data.", file=sys.stderr)` in `history.py:634` and `print("All metrics databases failed to read.", file=sys.stderr)` in `history.py:570,589,610,669`.

**Apply to:** TOOL-03 only.

**Prefix:** `operator-summary digest: skipped` (planner may tighten; tests assert prefix + `wan=`/`db=` substring, not full OS error text per D-14).

**Why a constant:** Centralize as `_DIGEST_SKIP_PREFIX` in `operator_summary.py` so tests import it for assertion stability if desired.

### Read-only SQLite URI

**Source:** `src/wanctl/storage/reader.py:94` and four other reader functions (lines 169, 257, 336, 483).

**Apply to:** TOOL-03 — `print_digest()` should switch to `sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)` for the same defensive read-only posture all other CLI readers use.

```python
conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
conn.row_factory = sqlite3.Row
```

### CLI Test: subprocess vs monkeypatch + capsys

**Source:** `tests/test_history_cli.py` shows both styles. `TestIntegration` (lines 378-507) uses `subprocess.run([sys.executable, "-m", "wanctl.history", ...])`. `TestMain` (lines 587-608) and `TestPerTinHistory` (lines 625-806) use `monkeypatch.setattr(sys, "argv", [...])` + `main()` + `capsys`.

**Apply to:** All Phase 208 CLI tests — prefer **monkeypatch + capsys** (faster, no subprocess overhead, can inject mocks at module boundaries like `wanctl.history.query_metrics` or `wanctl.operator_summary.sqlite3.connect`). Subprocess style is only useful for end-to-end exit-code smoke tests; the D-15 deterministic-injection requirement rules subprocess out for permission-guard tests.

### Aggregator Test: dynamic module load via `_load_module()`

**Source:** `tests/test_phase_204_watchdog.py:32-43`, `test_phase_204_replay.py:32-43`, `test_phase_204_distribution.py:16-22`.

**Apply to:** TOOL-01 — any new test in `test_phase_204_watchdog.py` reuses the existing module-scoped `aggregator` fixture (line 41-43); any new test file should copy the `_load_module()` helper verbatim because `scripts/soak_summary_aggregate.py` is loaded via `importlib.util` rather than as a package.

---

## No Analog Found

None. Every Phase 208 target has a direct in-file template, and the cross-cutting concerns (DB discovery, stable stderr, dynamic module load) all have existing analogs.

The one **new** convention is the stable stderr **skip prefix** `operator-summary digest: skipped ...` (D-14) — TOOL-03 introduces it; no prior `<prog>: skipped <context>` pattern exists. The closest precedent is `wan_controller.py:132-156` logging `"phase200 live-tuning skipped: ..."` which uses logger output rather than stderr-print, so it is a weak analog only.

---

## Metadata

**Analog search scope:**
- `/home/kevin/projects/wanctl/scripts/`
- `/home/kevin/projects/wanctl/src/wanctl/` (root and `storage/`)
- `/home/kevin/projects/wanctl/tests/`
- `/home/kevin/projects/wanctl/tests/fixtures/`

**Files scanned (full read):**
- `scripts/soak_summary_aggregate.py` (475 lines)
- `src/wanctl/history.py` (689 lines)
- `src/wanctl/operator_summary.py` (226 lines)
- `src/wanctl/storage/reader.py` (503 lines)
- `src/wanctl/storage/db_utils.py` (80 lines)
- `tests/test_operator_digest.py` (95 lines)
- `tests/test_phase_204_watchdog.py` (148 lines)
- `tests/test_phase_204_replay.py` (70 lines)
- `tests/test_phase_204_distribution.py` (145 lines)
- `tests/test_history_cli.py` (1018 lines — targeted reads on test indexes, integration, and per-tin sections)

**Files scanned (targeted grep only):**
- `src/wanctl/storage/writer.py` (DEFAULT_DB_PATH constant)
- `src/wanctl/wan_controller.py`, `src/wanctl/check_config.py`, `src/wanctl/metrics.py` (stderr/skip-prefix search)

**Pattern extraction date:** 2026-05-15
