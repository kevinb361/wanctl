"""Shared fixtures for dashboard tests."""

import pytest


@pytest.fixture
def sample_autorate_response() -> dict:
    """Dict matching the autorate health JSON schema (GET /health on port 9101)."""
    return {
        "status": "healthy",
        "uptime_seconds": 3600,
        "version": "1.13.0",
        "wan_count": 2,
        "wans": [
            {
                "name": "spectrum",
                "baseline_rtt_ms": 12.3,
                "load_rtt_ms": 18.7,
                "download": {"current_rate_mbps": 245.0, "state": "GREEN"},
                "upload": {"current_rate_mbps": 10.5, "state": "GREEN"},
                "router_connectivity": True,
                "cycle_budget": {"used_ms": 35.2, "budget_ms": 50.0},
            },
            {
                "name": "att",
                "baseline_rtt_ms": 8.1,
                "load_rtt_ms": 9.2,
                "download": {"current_rate_mbps": 85.0, "state": "GREEN"},
                "upload": {"current_rate_mbps": 18.0, "state": "GREEN"},
                "router_connectivity": True,
                "cycle_budget": {"used_ms": 28.1, "budget_ms": 50.0},
            },
        ],
        "disk_space": {
            "path": "/var/lib/wanctl",
            "free_bytes": 5000000000,
            "total_bytes": 10000000000,
            "free_pct": 50.0,
            "status": "ok",
        },
    }


@pytest.fixture
def sample_steering_response() -> dict:
    """Dict matching the steering health JSON schema (GET /health on port 9102)."""
    return {
        "status": "healthy",
        "steering": {"enabled": True, "state": "monitoring", "mode": "active"},
        "confidence": {"primary": 72.5},
        "wan_awareness": {
            "enabled": True,
            "zone": "GREEN",
            "effective_zone": "GREEN",
            "grace_period_active": False,
            "staleness_age_sec": 1.2,
            "stale": False,
            "confidence_contribution": 25.0,
        },
        "decision": {
            "last_transition_time": "2026-03-11T12:00:00Z",
            "time_in_state_seconds": 120.5,
        },
    }


@pytest.fixture
def tmp_config_dir(tmp_path):
    """Temporary directory for config file tests."""
    config_dir = tmp_path / "wanctl"
    config_dir.mkdir()
    return config_dir
