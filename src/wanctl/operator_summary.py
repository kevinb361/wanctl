"""Compact operator-facing health summary view for wanctl services."""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, cast
from urllib.request import urlopen

from tabulate import tabulate

from wanctl.history import per_wan_ingestion_rate_bucketed
from wanctl.storage.db_utils import discover_wan_dbs

# TOOL-03 / D-14: stable stderr prefix for per-DB digest skips. Tests assert on
# this prefix plus wan=/db= context, not the full OS error text.
_DIGEST_SKIP_PREFIX = "operator-summary digest: skipped"
_DIGEST_INGESTION_PREFIX = "operator-summary digest: ingestion-rate"


def _decode_payload(raw: str, source: str) -> dict[str, Any]:
    payload = json.loads(raw)
    if not isinstance(payload, dict):
        raise TypeError(f"Source '{source}' did not decode to a JSON object")
    return cast(dict[str, Any], payload)


def _read_source(source: str) -> dict[str, Any]:
    if source.startswith(("http://", "https://")):
        with urlopen(source, timeout=5) as response:  # noqa: S310 - operator-supplied health URL
            return _decode_payload(response.read().decode(), source)
    return _decode_payload(Path(source).read_text(), source)


def _format_alerts(alerts: dict[str, Any]) -> str:
    status = str(alerts.get("status", "disabled"))
    fire_count = int(alerts.get("fire_count", 0) or 0)
    cooldowns = int(alerts.get("active_cooldowns", 0) or 0)
    return f"{status} f={fire_count} c={cooldowns}"


def _build_table_rows(source: str, payload: dict[str, Any]) -> list[list[str]]:
    summary = payload.get("summary")
    if not isinstance(summary, dict):
        raise TypeError(f"Source '{source}' does not include a summary section")

    service = str(summary.get("service", "unknown"))
    raw_alerts = summary.get("alerts")
    alerts = cast(dict[str, Any], raw_alerts) if isinstance(raw_alerts, dict) else {}
    alert_cell = _format_alerts(alerts)
    rows_data = summary.get("rows")
    if not isinstance(rows_data, list):
        raise TypeError(f"Source '{source}' has invalid summary rows")

    rows: list[list[str]] = []
    for row in rows_data:
        if not isinstance(row, dict):
            continue
        if service == "autorate":
            queue = f"DL {row.get('download_state', 'UNKNOWN')}/UL {row.get('upload_state', 'UNKNOWN')}"
            notes = (
                f"router={'ok' if row.get('router_reachable') else 'down'} "
                f"rates={row.get('download_rate_mbps', '?')}/{row.get('upload_rate_mbps', '?')} "
                f"burst={int(bool(row.get('burst_active', False)))}:{int(row.get('burst_trigger_count', 0) or 0)}"
            )
        else:
            queue = f"{row.get('state', 'UNKNOWN')} / {row.get('congestion_state', 'UNKNOWN')}"
            zone = row.get('wan_zone')
            notes = f"router={'ok' if row.get('router_reachable') else 'down'} zone={zone}"
        rows.append(
            [
                service,
                str(row.get("name", "unknown")),
                str(row.get("status", "unknown")),
                queue,
                str(row.get("storage_status", "unknown")),
                str(row.get("runtime_status", "unknown")),
                alert_cell,
                notes,
            ]
        )
    return rows


def format_operator_summary(payloads: list[tuple[str, dict[str, Any]]]) -> str:
    rows: list[list[str]] = []
    for source, payload in payloads:
        rows.extend(_build_table_rows(source, payload))
    headers = ["Service", "Name", "Status", "State", "Storage", "Runtime", "Alerts", "Notes"]
    return str(tabulate(rows, headers=headers, tablefmt="simple"))


def _format_local_timestamp(timestamp: int) -> str:
    return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")


def _query_digest_rows(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    conn.row_factory = sqlite3.Row
    cursor = conn.execute(
        """
        SELECT alert_type, timestamp, details
        FROM alerts
        WHERE alert_type IN ('hard_red_dl', 'hard_red_ul')
          AND timestamp >= strftime('%s', 'now', '-24 hours')
        ORDER BY timestamp ASC
        """
    )
    return list(cursor.fetchall())


def _wan_name_from_db_path(db_path: Path) -> str:
    if db_path.stem.startswith("metrics-"):
        return db_path.stem.removeprefix("metrics-")
    return db_path.stem


def _format_digest_line(wan_name: str, rows: list[sqlite3.Row]) -> str:
    if not rows:
        return f"{wan_name}: no hard_red events in last 24h"

    dl_count = 0
    ul_count = 0
    peak_delta_ms = 0.0
    for row in rows:
        if row["alert_type"] == "hard_red_dl":
            dl_count += 1
        elif row["alert_type"] == "hard_red_ul":
            ul_count += 1

        details_raw = row["details"]
        if isinstance(details_raw, str) and details_raw:
            try:
                details = json.loads(details_raw)
            except json.JSONDecodeError:
                details = {}
            if isinstance(details, dict):
                delta_ms = details.get("delta_ms")
                if isinstance(delta_ms, int | float):
                    peak_delta_ms = max(peak_delta_ms, float(delta_ms))

    first_ts = int(rows[0]["timestamp"])
    last_ts = int(rows[-1]["timestamp"])
    return (
        f"{wan_name}: dl={dl_count} ul={ul_count} "
        f"range={_format_local_timestamp(first_ts)}..{_format_local_timestamp(last_ts)} "
        f"peak_delta_ms={peak_delta_ms:.1f}"
    )


def _format_ingestion_digest_line(wan_name: str, rows: list[dict]) -> str:
    """Format one compact per-WAN ingestion-rate digest line."""
    usable_rows = [
        row
        for row in rows
        if row.get("table_name") and row.get("rows_per_sec") is not None
    ]
    if not usable_rows:
        return f"{_DIGEST_INGESTION_PREFIX} wan={wan_name} total_rps=n/a top=n/a"

    total_rps = sum(float(row["rows_per_sec"]) for row in usable_rows)
    if total_rps == 0:
        return f"{_DIGEST_INGESTION_PREFIX} wan={wan_name} total_rps=n/a top=n/a"

    sorted_rows = sorted(
        usable_rows,
        key=lambda row: float(row["rows_per_sec"]),
        reverse=True,
    )
    top1 = sorted_rows[0]
    top1_name = str(top1["table_name"])
    if len(sorted_rows) == 1:
        top_token = top1_name
    else:
        top2 = sorted_rows[1]
        top2_rps = float(top2["rows_per_sec"])
        if top2_rps == 0 or float(top1["rows_per_sec"]) >= 1.20 * top2_rps:
            top_token = top1_name
        else:
            names = sorted([top1_name, str(top2["table_name"])])
            top_token = f"mixed:{names[0]}/{names[1]}"

    return f"{_DIGEST_INGESTION_PREFIX} wan={wan_name} total_rps={total_rps:.2f} top={top_token}"


def print_digest(db_paths: list[Path]) -> dict[str, int]:
    """Print per-DB hard-red digest and ingestion-rate accounting."""
    counts = {
        "readable": 0,
        "printed": 0,
        "read_skipped": 0,
        "write_skipped": 0,
        "ingestion_printed": 0,
    }
    if not db_paths:
        print("no WAN DBs discovered")
        return counts

    now = int(time.time())
    ingestion_data: dict[Path, list[dict] | None] = {}
    for db_path in db_paths:
        wan_name = _wan_name_from_db_path(db_path)
        try:
            ingestion_rows, _failures = per_wan_ingestion_rate_bucketed(
                [db_path],
                start_ts=now - 3600,
                end_ts=now,
                wan=None,
            )
        except (sqlite3.OperationalError, sqlite3.DatabaseError, OSError) as exc:
            print(
                f"{_DIGEST_SKIP_PREFIX} (ingestion) wan={wan_name} db={db_path}: {exc}",
                file=sys.stderr,
            )
            counts["read_skipped"] += 1
            ingestion_data[db_path] = None
        else:
            ingestion_data[db_path] = ingestion_rows

    for db_path in db_paths:
        wan_name = _wan_name_from_db_path(db_path)

        try:
            conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        except (sqlite3.OperationalError, OSError) as exc:
            print(
                f"{_DIGEST_SKIP_PREFIX} wan={wan_name} db={db_path}: {exc}",
                file=sys.stderr,
            )
            counts["read_skipped"] += 1
            continue

        counts["readable"] += 1
        try:
            try:
                hard_red_rows = _query_digest_rows(conn)
            except (sqlite3.OperationalError, sqlite3.DatabaseError) as exc:
                print(
                    f"{_DIGEST_SKIP_PREFIX} (hard-red query) wan={wan_name} db={db_path}: {exc}",
                    file=sys.stderr,
                )
                counts["read_skipped"] += 1
                continue
        finally:
            conn.close()
        line = _format_digest_line(wan_name, hard_red_rows)

        try:
            print(line)
        except OSError as exc:
            print(
                f"{_DIGEST_SKIP_PREFIX} wan={wan_name} db={db_path} (write): {exc}",
                file=sys.stderr,
            )
            counts["write_skipped"] += 1
            continue
        counts["printed"] += 1

    for db_path in db_paths:
        wan_name = _wan_name_from_db_path(db_path)
        gathered_rows = ingestion_data.get(db_path)
        if gathered_rows is None:
            continue
        line = _format_ingestion_digest_line(wan_name, gathered_rows)
        try:
            print(line)
        except OSError as exc:
            print(
                f"{_DIGEST_SKIP_PREFIX} (ingestion-write) wan={wan_name} db={db_path}: {exc}",
                file=sys.stderr,
            )
            counts["write_skipped"] += 1
            continue
        counts["ingestion_printed"] += 1

    return counts


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="wanctl-operator-summary",
        description="Render compact operator summaries from wanctl health JSON",
    )
    parser.add_argument(
        "sources",
        nargs="*",
        help="Health JSON paths or URLs to read",
    )
    parser.add_argument(
        "--json",
        dest="json_output",
        action="store_true",
        help="Output raw summary sections as JSON instead of a table",
    )
    parser.add_argument(
        "--digest",
        action="store_true",
        help="Print last-24h hard-red alert digest from discovered WAN DBs",
    )
    return parser


def main() -> int:
    parser = create_parser()
    args = parser.parse_args()

    if args.digest:
        try:
            db_paths = discover_wan_dbs()
        except OSError as exc:
            print(
                f"operator-summary digest: discovery failed ({exc})",
                file=sys.stderr,
            )
            return 1

        try:
            counts = print_digest(db_paths)
        except (sqlite3.DatabaseError, json.JSONDecodeError, TypeError, ValueError) as exc:
            print(str(exc), file=sys.stderr)
            return 1

        if db_paths and counts["readable"] == 0:
            print("no readable WAN DBs - try sudo", file=sys.stderr)
            return 0
        if counts["readable"] > 0 and counts["printed"] == 0:
            print(
                "operator-summary digest: all output writes failed",
                file=sys.stderr,
            )
            return 1
        return 0

    if not args.sources:
        parser.error("the following arguments are required: sources")

    payloads: list[tuple[str, dict[str, Any]]] = []
    try:
        for source in args.sources:
            payloads.append((source, _read_source(source)))
    except (OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.json_output:
        summaries = []
        for source, payload in payloads:
            summary = payload.get("summary")
            if not isinstance(summary, dict):
                print(f"Source '{source}' does not include a summary section", file=sys.stderr)
                return 1
            summaries.append({"source": source, "summary": summary})
        print(json.dumps(summaries, indent=2))
        return 0

    try:
        print(format_operator_summary(payloads))
    except TypeError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
