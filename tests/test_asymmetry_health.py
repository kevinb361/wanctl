"""Tests for asymmetry fields in IRTT health endpoint section.

Verifies:
- asymmetry_direction and asymmetry_ratio present when IRTT available with result
- "unknown" and None when IRTT available but no asymmetry result yet
- No asymmetry fields when IRTT unavailable (disabled/binary_not_found)
- Correct values passed through from _last_asymmetry_result
"""

import json
import socket
import time
import urllib.request
from unittest.mock import MagicMock

from wanctl.asymmetry_analyzer import AsymmetryResult
from wanctl.health_check import start_health_server
from wanctl.irtt_measurement import IRTTResult


def find_free_port() -> int:
    """Find an available port for the health server."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        return s.getsockname()[1]


def _make_wan_controller() -> MagicMock:
    """Create a mock WAN controller with all required attributes."""
    wan = MagicMock()
    wan.baseline_rtt = 24.5
    wan.load_rtt = 28.3
    wan.download.current_rate = 800_000_000
    wan.download.red_streak = 0
    wan.download.soft_red_streak = 0
    wan.download.soft_red_required = 3
    wan.download.green_streak = 5
    wan.download.green_required = 5
    wan.upload.current_rate = 35_000_000
    wan.upload.red_streak = 0
    wan.upload.soft_red_streak = 0
    wan.upload.soft_red_required = 3
    wan.upload.green_streak = 5
    wan.upload.green_required = 5
    wan.router_connectivity.is_reachable = True
    wan.router_connectivity.to_dict.return_value = {
        "is_reachable": True,
        "consecutive_failures": 0,
        "last_failure_type": None,
        "last_failure_time": None,
    }
    # Prevent MagicMock truthy issues
    wan._last_signal_result = None
    wan._irtt_thread = None
    wan._irtt_correlation = None
    wan._reflector_scorer = None
    wan._last_asymmetry_result = None
    wan._asymmetry_analyzer = None
    wan.alert_engine = None
    wan._fusion_enabled = False
    wan._fusion_icmp_weight = 0.7
    wan._last_fused_rtt = None
    wan._last_icmp_filtered_rtt = None
    return wan


def _make_controller(wan: MagicMock, irtt_config: dict | None = None) -> MagicMock:
    """Build a mock controller wrapping a single WAN."""
    mock_controller = MagicMock()
    mock_config = MagicMock()
    mock_config.wan_name = "spectrum"
    mock_config.irtt_config = irtt_config or {"enabled": False}
    mock_controller.wan_controllers = [
        {"controller": wan, "config": mock_config, "logger": MagicMock()}
    ]
    return mock_controller


def _make_irtt_result(timestamp: float | None = None) -> IRTTResult:
    """Create an IRTTResult for testing."""
    return IRTTResult(
        rtt_mean_ms=28.5,
        rtt_median_ms=27.3,
        ipdv_mean_ms=1.2,
        send_loss=0.5,
        receive_loss=1.0,
        packets_sent=100,
        packets_received=99,
        server="104.200.21.31",
        port=2112,
        timestamp=timestamp or (time.monotonic() - 5.0),
        success=True,
        send_delay_median_ms=15.0,
        receive_delay_median_ms=12.0,
    )


class TestAsymmetryHealthIRTTAvailable:
    """Test asymmetry fields when IRTT is available with result."""

    def test_asymmetry_direction_upstream(self) -> None:
        """asymmetry_direction shows 'upstream' when result.direction == 'upstream'."""
        wan = _make_wan_controller()
        mock_irtt_thread = MagicMock()
        mock_irtt_thread.get_latest.return_value = _make_irtt_result()
        wan._irtt_thread = mock_irtt_thread
        wan._irtt_correlation = 0.95
        wan._last_asymmetry_result = AsymmetryResult(
            direction="upstream", ratio=2.5, send_delay_ms=20.0, receive_delay_ms=8.0
        )

        controller = _make_controller(wan, irtt_config={"enabled": True})
        port = find_free_port()
        server = start_health_server(host="127.0.0.1", port=port, controller=controller)
        try:
            url = f"http://127.0.0.1:{port}/health"
            with urllib.request.urlopen(url, timeout=5) as response:
                data = json.loads(response.read().decode())
            irtt = data["wans"][0]["irtt"]
            assert irtt["asymmetry_direction"] == "upstream"
            assert irtt["asymmetry_ratio"] == 2.5
        finally:
            server.shutdown()

    def test_asymmetry_direction_downstream(self) -> None:
        """asymmetry_direction shows 'downstream' when result.direction == 'downstream'."""
        wan = _make_wan_controller()
        mock_irtt_thread = MagicMock()
        mock_irtt_thread.get_latest.return_value = _make_irtt_result()
        wan._irtt_thread = mock_irtt_thread
        wan._irtt_correlation = None
        wan._last_asymmetry_result = AsymmetryResult(
            direction="downstream", ratio=3.1, send_delay_ms=8.0, receive_delay_ms=24.8
        )

        controller = _make_controller(wan, irtt_config={"enabled": True})
        port = find_free_port()
        server = start_health_server(host="127.0.0.1", port=port, controller=controller)
        try:
            url = f"http://127.0.0.1:{port}/health"
            with urllib.request.urlopen(url, timeout=5) as response:
                data = json.loads(response.read().decode())
            irtt = data["wans"][0]["irtt"]
            assert irtt["asymmetry_direction"] == "downstream"
            assert irtt["asymmetry_ratio"] == 3.1
        finally:
            server.shutdown()

    def test_asymmetry_ratio_rounded_to_2_decimals(self) -> None:
        """asymmetry_ratio is rounded to 2 decimal places."""
        wan = _make_wan_controller()
        mock_irtt_thread = MagicMock()
        mock_irtt_thread.get_latest.return_value = _make_irtt_result()
        wan._irtt_thread = mock_irtt_thread
        wan._irtt_correlation = None
        wan._last_asymmetry_result = AsymmetryResult(
            direction="symmetric", ratio=1.23456789, send_delay_ms=10.0, receive_delay_ms=10.0
        )

        controller = _make_controller(wan, irtt_config={"enabled": True})
        port = find_free_port()
        server = start_health_server(host="127.0.0.1", port=port, controller=controller)
        try:
            url = f"http://127.0.0.1:{port}/health"
            with urllib.request.urlopen(url, timeout=5) as response:
                data = json.loads(response.read().decode())
            irtt = data["wans"][0]["irtt"]
            assert irtt["asymmetry_ratio"] == 1.23
        finally:
            server.shutdown()


class TestAsymmetryHealthNoResult:
    """Test asymmetry fields when IRTT available but no asymmetry result yet."""

    def test_direction_unknown_when_no_result(self) -> None:
        """asymmetry_direction is 'unknown' when _last_asymmetry_result is None."""
        wan = _make_wan_controller()
        mock_irtt_thread = MagicMock()
        mock_irtt_thread.get_latest.return_value = _make_irtt_result()
        wan._irtt_thread = mock_irtt_thread
        wan._irtt_correlation = None
        wan._last_asymmetry_result = None

        controller = _make_controller(wan, irtt_config={"enabled": True})
        port = find_free_port()
        server = start_health_server(host="127.0.0.1", port=port, controller=controller)
        try:
            url = f"http://127.0.0.1:{port}/health"
            with urllib.request.urlopen(url, timeout=5) as response:
                data = json.loads(response.read().decode())
            irtt = data["wans"][0]["irtt"]
            assert irtt["asymmetry_direction"] == "unknown"
            assert irtt["asymmetry_ratio"] is None
        finally:
            server.shutdown()


class TestAsymmetryHealthIRTTDisabled:
    """Test IRTT section when IRTT is disabled -- no asymmetry fields."""

    def test_no_asymmetry_fields_when_irtt_disabled(self) -> None:
        """IRTT section has available=False and does NOT contain 'asymmetry_direction' when disabled."""
        wan = _make_wan_controller()
        wan._irtt_thread = None

        controller = _make_controller(wan, irtt_config={"enabled": False})
        port = find_free_port()
        server = start_health_server(host="127.0.0.1", port=port, controller=controller)
        try:
            url = f"http://127.0.0.1:{port}/health"
            with urllib.request.urlopen(url, timeout=5) as response:
                data = json.loads(response.read().decode())
            irtt = data["wans"][0]["irtt"]
            assert irtt["available"] is False
            assert "asymmetry_direction" not in irtt
            assert "asymmetry_ratio" not in irtt
        finally:
            server.shutdown()

    def test_no_asymmetry_fields_when_binary_not_found(self) -> None:
        """IRTT section has no asymmetry fields when enabled but binary not found."""
        wan = _make_wan_controller()
        wan._irtt_thread = None

        controller = _make_controller(wan, irtt_config={"enabled": True})
        port = find_free_port()
        server = start_health_server(host="127.0.0.1", port=port, controller=controller)
        try:
            url = f"http://127.0.0.1:{port}/health"
            with urllib.request.urlopen(url, timeout=5) as response:
                data = json.loads(response.read().decode())
            irtt = data["wans"][0]["irtt"]
            assert irtt["available"] is False
            assert "asymmetry_direction" not in irtt
            assert "asymmetry_ratio" not in irtt
        finally:
            server.shutdown()


class TestAsymmetryHealthAwaitingMeasurement:
    """Test asymmetry fields when IRTT available but awaiting first measurement."""

    def test_direction_unknown_awaiting_measurement(self) -> None:
        """asymmetry_direction is 'unknown' when IRTT thread exists but no result yet."""
        wan = _make_wan_controller()
        mock_irtt_thread = MagicMock()
        mock_irtt_thread.get_latest.return_value = None
        wan._irtt_thread = mock_irtt_thread

        controller = _make_controller(wan, irtt_config={"enabled": True})
        port = find_free_port()
        server = start_health_server(host="127.0.0.1", port=port, controller=controller)
        try:
            url = f"http://127.0.0.1:{port}/health"
            with urllib.request.urlopen(url, timeout=5) as response:
                data = json.loads(response.read().decode())
            irtt = data["wans"][0]["irtt"]
            assert irtt["asymmetry_direction"] == "unknown"
            assert irtt["asymmetry_ratio"] is None
        finally:
            server.shutdown()
