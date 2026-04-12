"""Tests for compact operator summary helper."""

import json
import sys
from pathlib import Path

from wanctl.operator_summary import create_parser, format_operator_summary, main


def test_create_parser_accepts_sources():
    parser = create_parser()
    args = parser.parse_args(["health.json"])
    assert args.sources == ["health.json"]
    assert args.json_output is False


def test_format_operator_summary_renders_autorate_and_steering():
    autorate = {
        "summary": {
            "service": "autorate",
            "alerts": {"status": "idle", "fire_count": 0, "active_cooldowns": 0},
            "rows": [
                {
                    "name": "spectrum",
                    "status": "ok",
                    "download_state": "GREEN",
                    "upload_state": "GREEN",
                    "download_rate_mbps": 940.0,
                    "upload_rate_mbps": 35.0,
                    "storage_status": "ok",
                    "runtime_status": "ok",
                    "router_reachable": True,
                    "burst_active": False,
                    "burst_trigger_count": 0,
                },
                {
                    "name": "att",
                    "status": "warning",
                    "download_state": "SOFT_RED",
                    "upload_state": "GREEN",
                    "download_rate_mbps": 320.0,
                    "upload_rate_mbps": 40.0,
                    "storage_status": "ok",
                    "runtime_status": "warning",
                    "router_reachable": True,
                    "burst_active": True,
                    "burst_trigger_count": 2,
                },
            ],
        }
    }
    steering = {
        "summary": {
            "service": "steering",
            "alerts": {"status": "disabled", "fire_count": 0, "active_cooldowns": 0},
            "rows": [
                {
                    "name": "steering",
                    "status": "ok",
                    "state": "SPECTRUM_GOOD",
                    "congestion_state": "GREEN",
                    "wan_zone": "GREEN",
                    "storage_status": "ok",
                    "runtime_status": "ok",
                    "router_reachable": True,
                }
            ],
        }
    }

    table = format_operator_summary([("a.json", autorate), ("s.json", steering)])
    assert "Service" in table
    assert "spectrum" in table
    assert "att" in table
    assert "steering" in table
    assert "DL GREEN/UL GREEN" in table
    assert "SPECTRUM_GOOD / GREEN" in table


def test_main_json_output(tmp_path: Path, monkeypatch, capsys):
    health_path = tmp_path / "health.json"
    health_path.write_text(
        json.dumps(
            {
                "summary": {
                    "service": "autorate",
                    "alerts": {"status": "idle", "fire_count": 1, "active_cooldowns": 0},
                    "rows": [
                        {
                            "name": "spectrum",
                            "status": "ok",
                            "download_state": "GREEN",
                            "upload_state": "GREEN",
                            "download_rate_mbps": 940.0,
                            "upload_rate_mbps": 35.0,
                            "storage_status": "ok",
                            "runtime_status": "ok",
                            "router_reachable": True,
                            "burst_active": False,
                            "burst_trigger_count": 0,
                        }
                    ],
                }
            }
        )
    )
    monkeypatch.setattr(sys, "argv", ["wanctl-operator-summary", str(health_path), "--json"])
    assert main() == 0
    captured = capsys.readouterr()
    output = json.loads(captured.out)
    assert output[0]["summary"]["service"] == "autorate"
