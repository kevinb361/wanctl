#!/usr/bin/env python3
"""Generate the bounded CAKE Grafana dashboard and Prometheus rule source."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DASHBOARD = ROOT / "deploy/monitoring/grafana/network-cake.json"
RULES = ROOT / "deploy/monitoring/prometheus/cake-rules.yml"
DATASOURCE = {"type": "prometheus", "uid": "prometheus-ds"}


def target(expression: str, legend: str, ref_id: str) -> dict:
    return {
        "datasource": DATASOURCE,
        "editorMode": "code",
        "expr": expression,
        "legendFormat": legend,
        "range": True,
        "refId": ref_id,
    }


def timeseries(panel_id: int, title: str, y: int, expressions: list[tuple[str, str]]) -> dict:
    return {
        "id": panel_id,
        "type": "timeseries",
        "title": title,
        "description": "Read-only telemetry. Align series in time; this panel never actuates shaping.",
        "datasource": DATASOURCE,
        "gridPos": {"x": 0, "y": y, "w": 24, "h": 8},
        "fieldConfig": {"defaults": {}, "overrides": []},
        "options": {"legend": {"displayMode": "table", "placement": "bottom"}},
        "targets": [
            target(expression, legend, chr(ord("A") + index))
            for index, (expression, legend) in enumerate(expressions)
        ],
    }


def stat(panel_id: int, title: str, x: int, expression: str, description: str) -> dict:
    return {
        "id": panel_id,
        "type": "stat",
        "title": title,
        "description": description,
        "datasource": DATASOURCE,
        "gridPos": {"x": x, "y": 3, "w": 8, "h": 4},
        "fieldConfig": {"defaults": {}, "overrides": []},
        "options": {"reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": False}},
        "targets": [target(expression, "", "A")],
    }


def dashboard() -> dict:
    panels = [
        {
            "id": 100,
            "type": "text",
            "title": "CAKE telemetry safety boundary",
            "gridPos": {"x": 0, "y": 0, "w": 24, "h": 3},
            "options": {
                "mode": "markdown",
                "content": (
                    "**Read-only evidence, not a controller.** Missing/stale data is explicit. "
                    "Queue thresholds are intentionally not treated as tuning verdicts until the "
                    "14-day baseline is accepted."
                ),
            },
        },
        stat(
            101,
            "CAKE collection up",
            0,
            "min(cake_stats_up)",
            "1 only when both WAN collectors are healthy.",
        ),
        stat(
            102,
            "Worst collection age",
            8,
            "max(cake_stats_age_seconds)",
            "Freshness in seconds; missing data is not zero.",
        ),
        stat(
            103,
            "RTT probes up",
            16,
            "min(cake_probe_up)",
            "1 only when both WAN raw RTT probes are current.",
        ),
        timeseries(
            104,
            "Rate, loaded RTT, and worst tin delay correlation",
            7,
            [
                ("cake_shaped_rate_bps / 1000000", "{{wan}} {{direction}} shaped Mbit/s"),
                ("cake_rtt_delta_ms", "{{wan}} loaded RTT delta ms"),
                (
                    "max by (wan, direction) (cake_tin_average_delay_seconds) * 1000",
                    "{{wan}} {{direction}} worst average tin delay ms",
                ),
            ],
        ),
        timeseries(
            105,
            "Per-tin delay",
            15,
            [
                (
                    "cake_tin_average_delay_seconds * 1000",
                    "{{wan}} {{direction}} {{tin}} average ms",
                ),
                ("cake_tin_peak_delay_seconds * 1000", "{{wan}} {{direction}} {{tin}} peak ms"),
            ],
        ),
        timeseries(
            106,
            "Per-tin backlog and drops",
            23,
            [
                ("cake_tin_backlog_bytes", "{{wan}} {{direction}} {{tin}} backlog bytes"),
                (
                    "rate(cake_tin_dropped_packets_total[$__rate_interval])",
                    "{{wan}} {{direction}} {{tin}} drops/s",
                ),
            ],
        ),
        timeseries(
            107,
            "Per-tin throughput, ECN, and reset visibility",
            31,
            [
                (
                    "rate(cake_tin_sent_bytes_total[$__rate_interval]) * 8 / 1000000",
                    "{{wan}} {{direction}} {{tin}} Mbit/s",
                ),
                (
                    "rate(cake_tin_ecn_marked_packets_total[$__rate_interval])",
                    "{{wan}} {{direction}} {{tin}} ECN/s",
                ),
                ("cake_tin_resets_total", "{{wan}} {{direction}} {{tin}} resets"),
            ],
        ),
    ]
    return {
        "uid": "network-cake",
        "title": "Network · CAKE Shaper",
        "tags": ["network", "cake", "wan", "read-only"],
        "timezone": "browser",
        "schemaVersion": 39,
        "version": 4,
        "refresh": "30s",
        "graphTooltip": 1,
        "editable": False,
        "time": {"from": "now-3h", "to": "now"},
        "panels": panels,
    }


RULE_SOURCE = """groups:
  - name: cake-telemetry
    interval: 30s
    rules:
      - record: cake:tin_drop_rate5m
        expr: sum by (wan, direction, tin) (rate(cake_tin_dropped_packets_total[5m]))
      - record: cake:tin_ecn_rate5m
        expr: sum by (wan, direction, tin) (rate(cake_tin_ecn_marked_packets_total[5m]))
      - record: cake:tin_backlog_bytes
        expr: max by (wan, direction, tin) (cake_tin_backlog_bytes)
      - record: cake:rtt_delta_seconds
        expr: cake_rtt_delta_ms / 1000
      - alert: CakeStatsUnavailable
        expr: min_over_time(cake_stats_up[5m]) == 0
        for: 5m
        labels:
          severity: warning
          maturity: baseline-pending
        annotations:
          summary: "CAKE statistics unavailable for {{ $labels.wan }}"
      - alert: CakeStatsStale
        expr: cake_stats_age_seconds > 120
        for: 5m
        labels:
          severity: warning
          maturity: baseline-pending
        annotations:
          summary: "CAKE statistics for {{ $labels.wan }} are stale"
      - alert: CakeProbeUnavailable
        expr: cake_probe_up == 0
        for: 5m
        labels:
          severity: warning
          maturity: baseline-pending
        annotations:
          summary: "CAKE RTT probe unavailable for {{ $labels.wan }}"
"""


def generated() -> dict[Path, str]:
    return {
        DASHBOARD: json.dumps(dashboard(), indent=2, sort_keys=True) + "\n",
        RULES: RULE_SOURCE,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    stale = []
    for path, content in generated().items():
        if args.check:
            if not path.exists() or path.read_text(encoding="utf-8") != content:
                stale.append(str(path.relative_to(ROOT)))
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
    if stale:
        parser.error("stale generated files: " + ", ".join(stale))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
