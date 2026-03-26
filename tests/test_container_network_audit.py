"""Tests for container network audit script.

Tests computation correctness, error handling, jitter assessment,
report generation, and --dry-run mode for scripts/container_network_audit.py.
"""

import subprocess
from unittest.mock import MagicMock, patch

from scripts.container_network_audit import (
    CONTAINERS,
    JITTER_RATIO_THRESHOLD,
    OVERHEAD_THRESHOLD_MS,
    WAN_JITTER_REFERENCE,
    assess_jitter,
    capture_topology,
    compute_stats,
    generate_report,
    main,
    measure_container,
)


class TestComputeStats:
    """Tests for compute_stats(rtts) -> dict | None."""

    def test_basic_stats_correct(self) -> None:
        """compute_stats with known data returns correct keys and mean."""
        rtts = [0.1, 0.2, 0.3, 0.4, 0.5] * 200
        result = compute_stats(rtts)
        assert result is not None
        expected_keys = {"mean", "median", "stdev", "min", "max", "p95", "p99", "count"}
        assert set(result.keys()) == expected_keys

    def test_mean_approximately_correct(self) -> None:
        """compute_stats mean is approximately 0.3 for uniform [0.1..0.5] data."""
        rtts = [0.1, 0.2, 0.3, 0.4, 0.5] * 200
        result = compute_stats(rtts)
        assert result is not None
        assert abs(result["mean"] - 0.3) < 0.01

    def test_empty_list_returns_none(self) -> None:
        """compute_stats([]) returns None."""
        assert compute_stats([]) is None

    def test_single_element_returns_none(self) -> None:
        """compute_stats([0.5]) returns None (need >= 2 for stdev)."""
        assert compute_stats([0.5]) is None

    def test_count_matches_input(self) -> None:
        """count field matches input length."""
        rtts = [0.1, 0.2, 0.3, 0.4, 0.5] * 200
        result = compute_stats(rtts)
        assert result is not None
        assert result["count"] == 1000

    def test_min_max_correct(self) -> None:
        """min and max are correct for known input."""
        rtts = [0.1, 0.2, 0.3, 0.4, 0.5] * 200
        result = compute_stats(rtts)
        assert result is not None
        assert result["min"] == 0.1
        assert result["max"] == 0.5


class TestAssessJitter:
    """Tests for assess_jitter(stdev, wan_name) -> str."""

    def test_negligible_jitter_spectrum(self) -> None:
        """Low stdev relative to WAN idle jitter returns NEGLIGIBLE."""
        # Spectrum idle jitter = 0.5ms, 0.03 / 0.5 = 6% < 10%
        result = assess_jitter(0.03, "spectrum")
        assert "NEGLIGIBLE" in result

    def test_notable_jitter_spectrum(self) -> None:
        """High stdev relative to WAN idle jitter returns NOTABLE."""
        # Spectrum idle jitter = 0.5ms, 0.1 / 0.5 = 20% >= 10%
        result = assess_jitter(0.1, "spectrum")
        assert "NOTABLE" in result

    def test_unknown_wan_uses_default(self) -> None:
        """Unknown WAN name uses default reference values, returns NEGLIGIBLE for low stdev."""
        # Default idle jitter = 0.5ms, 0.01 / 0.5 = 2% < 10%
        result = assess_jitter(0.01, "unknown_wan")
        assert "NEGLIGIBLE" in result

    def test_result_contains_percentage(self) -> None:
        """Result string contains percentage of WAN jitter."""
        result = assess_jitter(0.03, "spectrum")
        assert "%" in result

    def test_att_negligible(self) -> None:
        """ATT with low stdev returns NEGLIGIBLE."""
        # ATT idle jitter = 0.5ms, 0.04 / 0.5 = 8% < 10%
        result = assess_jitter(0.04, "att")
        assert "NEGLIGIBLE" in result

    def test_att_notable(self) -> None:
        """ATT with high stdev returns NOTABLE."""
        # ATT idle jitter = 0.5ms, 0.06 / 0.5 = 12% >= 10%
        result = assess_jitter(0.06, "att")
        assert "NOTABLE" in result


class TestMeasureContainer:
    """Tests for measure_container(host, count, interval) -> dict | None."""

    @patch("scripts.container_network_audit.subprocess.run")
    @patch("scripts.container_network_audit.parse_ping_output")
    def test_successful_measurement(self, mock_parse: MagicMock, mock_run: MagicMock) -> None:
        """Successful ping returns stats dict with host key."""
        mock_run.return_value = MagicMock(stdout="time=0.2\ntime=0.3\ntime=0.4\n")
        mock_parse.return_value = [0.2, 0.3, 0.4] * 100
        result = measure_container("10.10.110.246", count=300, interval=0.01)
        assert result is not None
        assert result["host"] == "10.10.110.246"
        assert "mean" in result
        assert "median" in result
        assert "p95" in result
        assert "p99" in result

    @patch("scripts.container_network_audit.subprocess.run")
    def test_timeout_returns_none(self, mock_run: MagicMock) -> None:
        """subprocess.TimeoutExpired returns None."""
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="ping", timeout=30)
        result = measure_container("10.10.110.246")
        assert result is None

    @patch("scripts.container_network_audit.subprocess.run")
    @patch("scripts.container_network_audit.parse_ping_output")
    def test_empty_rtts_returns_none(self, mock_parse: MagicMock, mock_run: MagicMock) -> None:
        """Empty parse_ping_output result returns None."""
        mock_run.return_value = MagicMock(stdout="")
        mock_parse.return_value = []
        result = measure_container("10.10.110.246")
        assert result is None


class TestCaptureTopology:
    """Tests for capture_topology(container) -> dict."""

    @patch("scripts.container_network_audit.subprocess.run")
    def test_successful_capture(self, mock_run: MagicMock) -> None:
        """Successful SSH returns dict with ip_link and ip_addr keys."""
        mock_run.return_value = MagicMock(stdout="eth0@if67: <BROADCAST> mtu 1500\n", returncode=0)
        result = capture_topology("cake-spectrum")
        assert "ip_link" in result
        assert "ip_addr" in result

    @patch("scripts.container_network_audit.subprocess.run")
    def test_timeout_returns_timeout_values(self, mock_run: MagicMock) -> None:
        """subprocess.TimeoutExpired returns dict with 'timeout' values."""
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="ssh", timeout=10)
        result = capture_topology("cake-spectrum")
        assert result["ip_link"] == "timeout"
        assert result["ip_addr"] == "timeout"

    @patch("scripts.container_network_audit.subprocess.run")
    def test_nonzero_returncode_returns_unavailable(self, mock_run: MagicMock) -> None:
        """Non-zero returncode returns dict with 'unavailable' values."""
        mock_run.return_value = MagicMock(stdout="", returncode=1)
        result = capture_topology("cake-spectrum")
        assert result["ip_link"] == "unavailable"
        assert result["ip_addr"] == "unavailable"


class TestGenerateReport:
    """Tests for generate_report(results, topology, wan_mapping) -> str."""

    def _make_results(self, *, include_unreachable: bool = False) -> dict:
        """Helper to create mock results dict."""
        results = {
            "cake-spectrum": {
                "host": "10.10.110.246",
                "count": 1000,
                "mean": 0.205,
                "median": 0.194,
                "stdev": 0.063,
                "min": 0.116,
                "max": 0.443,
                "p95": 0.320,
                "p99": 0.410,
            },
            "cake-att": {
                "host": "10.10.110.247",
                "count": 1000,
                "mean": 0.172,
                "median": 0.165,
                "stdev": 0.031,
                "min": 0.114,
                "max": 0.255,
                "p95": 0.230,
                "p99": 0.248,
            },
        }
        if include_unreachable:
            results["cake-att"] = None
        return results

    def _make_topology(self) -> dict:
        """Helper to create mock topology dict."""
        return {
            "cake-spectrum": {
                "ip_link": "2: eth0@if67: <BROADCAST,MULTICAST,UP> mtu 1500",
                "ip_addr": "inet 10.10.110.246/24",
            },
            "cake-att": {
                "ip_link": "2: eth0@if74: <BROADCAST,MULTICAST,UP> mtu 1500",
                "ip_addr": "inet 10.10.110.247/24",
            },
        }

    def test_report_contains_header(self) -> None:
        """Report starts with Container Network Audit header."""
        report = generate_report(self._make_results(), self._make_topology())
        assert "# Container Network Audit" in report

    def test_report_contains_measurement_table(self) -> None:
        """Report includes per-container table with stat columns."""
        report = generate_report(self._make_results(), self._make_topology())
        assert "Mean" in report
        assert "Median" in report
        assert "P95" in report
        assert "P99" in report
        assert "Stddev" in report

    def test_report_contains_jitter_analysis(self) -> None:
        """Report includes jitter analysis with NEGLIGIBLE/NOTABLE."""
        report = generate_report(self._make_results(), self._make_topology())
        # 0.063 / 0.5 = 12.6% >= 10% -> NOTABLE for spectrum
        # 0.031 / 0.5 = 6.2% < 10% -> NEGLIGIBLE for att
        assert "NEGLIGIBLE" in report or "NOTABLE" in report

    def test_report_contains_recommendation(self) -> None:
        """Report includes recommendation section referencing 0.5ms threshold."""
        report = generate_report(self._make_results(), self._make_topology())
        assert "0.5" in report
        # Could be in recommendation or executive summary
        assert "Recommendation" in report or "recommendation" in report

    def test_report_handles_unreachable_container(self) -> None:
        """Report handles one container with None stats gracefully."""
        results = self._make_results(include_unreachable=True)
        report = generate_report(results, self._make_topology())
        assert "unreachable" in report.lower() or "unavailable" in report.lower()

    def test_report_contains_topology_section(self) -> None:
        """Report includes network topology section."""
        report = generate_report(self._make_results(), self._make_topology())
        assert "Topology" in report or "topology" in report


class TestDryRun:
    """Tests for --dry-run flag behavior."""

    @patch("scripts.container_network_audit.subprocess.run")
    def test_dry_run_does_not_call_subprocess(self, mock_run: MagicMock) -> None:
        """--dry-run flag does not call subprocess."""
        with patch("builtins.open", MagicMock()), patch("builtins.print"):
            main(["--dry-run"])
        mock_run.assert_not_called()


class TestContainerConstants:
    """Tests for module-level constants."""

    def test_containers_has_spectrum(self) -> None:
        """CONTAINERS dict has entry for cake-spectrum."""
        assert "cake-spectrum" in CONTAINERS
        assert CONTAINERS["cake-spectrum"] == "10.10.110.246"

    def test_containers_has_att(self) -> None:
        """CONTAINERS dict has entry for cake-att."""
        assert "cake-att" in CONTAINERS
        assert CONTAINERS["cake-att"] == "10.10.110.247"

    def test_overhead_threshold(self) -> None:
        """OVERHEAD_THRESHOLD_MS is 0.5."""
        assert OVERHEAD_THRESHOLD_MS == 0.5

    def test_jitter_ratio_threshold(self) -> None:
        """JITTER_RATIO_THRESHOLD is 0.10."""
        assert JITTER_RATIO_THRESHOLD == 0.10

    def test_wan_jitter_reference_has_spectrum(self) -> None:
        """WAN_JITTER_REFERENCE has spectrum entry with idle and loaded keys."""
        assert "spectrum" in WAN_JITTER_REFERENCE
        assert "idle" in WAN_JITTER_REFERENCE["spectrum"]
        assert "loaded" in WAN_JITTER_REFERENCE["spectrum"]

    def test_wan_jitter_reference_has_att(self) -> None:
        """WAN_JITTER_REFERENCE has att entry with idle and loaded keys."""
        assert "att" in WAN_JITTER_REFERENCE
        assert "idle" in WAN_JITTER_REFERENCE["att"]
        assert "loaded" in WAN_JITTER_REFERENCE["att"]
