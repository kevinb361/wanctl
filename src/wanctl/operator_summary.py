"""Compact operator-facing health summary view for wanctl services."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, cast
from urllib.request import urlopen

from tabulate import tabulate


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


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="wanctl-operator-summary",
        description="Render compact operator summaries from wanctl health JSON",
    )
    parser.add_argument(
        "sources",
        nargs="+",
        help="Health JSON paths or URLs to read",
    )
    parser.add_argument(
        "--json",
        dest="json_output",
        action="store_true",
        help="Output raw summary sections as JSON instead of a table",
    )
    return parser


def main() -> int:
    parser = create_parser()
    args = parser.parse_args()

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
