from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
GENERATOR = REPO_ROOT / "scripts" / "generate_cake_observability.py"
DASHBOARD = REPO_ROOT / "deploy" / "monitoring" / "grafana" / "network-cake.json"
RULES = REPO_ROOT / "deploy" / "monitoring" / "prometheus" / "cake-rules.yml"


def test_generated_cake_observability_assets_are_current() -> None:
    result = subprocess.run(
        [sys.executable, str(GENERATOR), "--check"],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr


def test_dashboard_correlates_rate_rtt_and_bounded_tin_dimensions() -> None:
    dashboard = json.loads(DASHBOARD.read_text(encoding="utf-8"))
    expressions = [
        target["expr"] for panel in dashboard["panels"] for target in panel.get("targets", [])
    ]
    joined = "\n".join(expressions)

    assert dashboard["uid"] == "network-cake"
    assert dashboard["editable"] is False
    assert "Read-only evidence, not a controller" in dashboard["panels"][0]["options"]["content"]
    assert "cake_shaped_rate_bps" in joined
    assert "cake_rtt_delta_ms" in joined
    assert "cake_tin_average_delay_seconds" in joined
    assert "cake_tin_backlog_bytes" in joined
    assert "cake_tin_dropped_packets_total" in joined
    assert "cake_tin_ecn_marked_packets_total" in joined
    assert "cake_tin_resets_total" in joined
    assert "cake_stats_up" in joined
    assert "cake_stats_age_seconds" in joined
    assert not any(label in joined for label in ("client", "address", "flow", "src", "dst"))


def test_rules_are_warning_only_and_disclose_baseline_pending_maturity() -> None:
    groups = yaml.safe_load(RULES.read_text(encoding="utf-8"))["groups"]
    rules = [rule for group in groups for rule in group["rules"]]
    alerts = [rule for rule in rules if "alert" in rule]
    records = [rule for rule in rules if "record" in rule]

    assert {rule["record"] for rule in records} == {
        "cake:tin_drop_rate5m",
        "cake:tin_ecn_rate5m",
        "cake:tin_backlog_bytes",
        "cake:rtt_delta_seconds",
    }
    assert {rule["alert"] for rule in alerts} == {
        "CakeStatsUnavailable",
        "CakeStatsStale",
        "CakeProbeUnavailable",
    }
    assert all(
        rule["labels"] == {"severity": "warning", "maturity": "baseline-pending"} for rule in alerts
    )
    assert all("cake_tin_" not in rule["expr"] for rule in alerts)
    assert all(rule["for"] == "5m" for rule in alerts)
