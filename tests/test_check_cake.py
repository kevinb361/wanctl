"""Comprehensive tests for wanctl-check-cake CLI tool.

Covers all phase requirements:
  CAKE-01: Router connectivity probe (REST/SSH reachability and auth)
  CAKE-02: Queue tree audit (existence and names)
  CAKE-03: CAKE qdisc type verification
  CAKE-04: Config-vs-router ceiling diff (autorate only)
  CAKE-05: Mangle rule existence check (steering only)
"""

import json
import os
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
import yaml

from wanctl.check_config import CheckResult, Severity


# =============================================================================
# FIXTURES
# =============================================================================


def _autorate_config_data() -> dict:
    """Return a minimal valid autorate config dict for check_cake tests."""
    return {
        "wan_name": "spectrum",
        "router": {
            "transport": "rest",
            "host": "10.10.99.1",
            "user": "admin",
            "password": "${ROUTER_PASSWORD}",
            "port": 443,
            "verify_ssl": False,
        },
        "queues": {
            "download": "WAN-Download-Spectrum",
            "upload": "WAN-Upload-Spectrum",
        },
        "continuous_monitoring": {
            "enabled": True,
            "baseline_rtt_initial": 24,
            "download": {
                "ceiling_mbps": 940,
            },
            "upload": {
                "ceiling_mbps": 38,
            },
        },
        "timeouts": {
            "ssh_command": 15,
        },
    }


def _steering_config_data() -> dict:
    """Return a minimal valid steering config dict for check_cake tests."""
    return {
        "wan_name": "steering",
        "router": {
            "transport": "rest",
            "host": "10.10.99.1",
            "user": "admin",
            "password": "${ROUTER_PASSWORD}",
            "port": 443,
            "verify_ssl": False,
        },
        "topology": {
            "primary_wan": "spectrum",
            "primary_wan_config": "/etc/wanctl/spectrum.yaml",
            "alternate_wan": "att",
        },
        "mangle_rule": {
            "comment": "ADAPTIVE: Steer latency-sensitive to ATT",
        },
        "timeouts": {
            "ssh_command": 15,
        },
    }


def _queue_response(
    name: str = "WAN-Download-Spectrum",
    queue: str = "cake-down-spectrum",
    max_limit: str = "940000000",
) -> dict:
    """Return a mock RouterOS queue tree response dict."""
    return {
        ".id": "*1",
        "name": name,
        "queue": queue,
        "max-limit": max_limit,
        "disabled": "false",
    }


def _write_config(tmp_path, config_data: dict) -> str:
    """Write a config dict to a temp YAML file and return the path string."""
    config_file = tmp_path / "test_config.yaml"
    config_file.write_text(yaml.dump(config_data, default_flow_style=False))
    return str(config_file)


# =============================================================================
# TestConfigExtraction -- config parsing helpers
# =============================================================================


class TestConfigExtraction:
    """Test _extract_router_config, _extract_queue_names, _extract_ceilings,
    _extract_mangle_comment."""

    def test_extract_router_config_rest(self):
        """Extract REST transport config fields from autorate YAML."""
        from wanctl.check_cake import _extract_router_config

        data = _autorate_config_data()
        cfg = _extract_router_config(data)
        assert cfg["router_host"] == "10.10.99.1"
        assert cfg["router_user"] == "admin"
        assert cfg["router_transport"] == "rest"
        assert cfg["router_password"] == "${ROUTER_PASSWORD}"
        assert cfg["router_port"] == 443
        assert cfg["router_verify_ssl"] is False
        assert cfg["timeout_ssh_command"] == 15

    def test_extract_router_config_ssh(self):
        """Extract SSH transport config fields."""
        from wanctl.check_cake import _extract_router_config

        data = _autorate_config_data()
        data["router"]["transport"] = "ssh"
        data["router"]["ssh_key"] = "/etc/wanctl/ssh/router.key"
        cfg = _extract_router_config(data)
        assert cfg["router_transport"] == "ssh"
        assert cfg["ssh_key"] == "/etc/wanctl/ssh/router.key"

    def test_extract_router_config_defaults(self):
        """Missing router section produces safe defaults."""
        from wanctl.check_cake import _extract_router_config

        cfg = _extract_router_config({})
        assert cfg["router_host"] == ""
        assert cfg["router_user"] == "admin"
        assert cfg["router_transport"] == "rest"
        assert cfg["router_port"] == 443

    def test_extract_queue_names_autorate(self):
        """Extract queue names from autorate config."""
        from wanctl.check_cake import _extract_queue_names

        data = _autorate_config_data()
        names = _extract_queue_names(data, "autorate")
        assert names["download"] == "WAN-Download-Spectrum"
        assert names["upload"] == "WAN-Upload-Spectrum"

    def test_extract_queue_names_steering(self):
        """Extract queue names from steering config with defaults from topology."""
        from wanctl.check_cake import _extract_queue_names

        data = _steering_config_data()
        names = _extract_queue_names(data, "steering")
        assert names["download"] == "WAN-Download-Spectrum"
        assert names["upload"] == "WAN-Upload-Spectrum"

    def test_extract_queue_names_steering_explicit(self):
        """Extract queue names from steering config with explicit cake_queues."""
        from wanctl.check_cake import _extract_queue_names

        data = _steering_config_data()
        data["cake_queues"] = {
            "primary_download": "Custom-DL",
            "primary_upload": "Custom-UL",
        }
        names = _extract_queue_names(data, "steering")
        assert names["download"] == "Custom-DL"
        assert names["upload"] == "Custom-UL"

    def test_extract_queue_names_steering_deprecated(self):
        """Deprecated spectrum_download/upload keys still work."""
        from wanctl.check_cake import _extract_queue_names

        data = _steering_config_data()
        data["cake_queues"] = {
            "spectrum_download": "Legacy-DL",
            "spectrum_upload": "Legacy-UL",
        }
        names = _extract_queue_names(data, "steering")
        assert names["download"] == "Legacy-DL"
        assert names["upload"] == "Legacy-UL"

    def test_extract_ceilings_autorate(self):
        """Extract ceiling values (bps) from autorate config."""
        from wanctl.check_cake import _extract_ceilings

        data = _autorate_config_data()
        ceilings = _extract_ceilings(data, "autorate")
        assert ceilings["download"] == 940_000_000
        assert ceilings["upload"] == 38_000_000

    def test_extract_ceilings_steering_returns_none(self):
        """Steering configs have no ceilings."""
        from wanctl.check_cake import _extract_ceilings

        data = _steering_config_data()
        ceilings = _extract_ceilings(data, "steering")
        assert ceilings["download"] is None
        assert ceilings["upload"] is None

    def test_extract_mangle_comment(self):
        """Extract mangle rule comment from steering config."""
        from wanctl.check_cake import _extract_mangle_comment

        data = _steering_config_data()
        comment = _extract_mangle_comment(data)
        assert comment == "ADAPTIVE: Steer latency-sensitive to ATT"

    def test_extract_mangle_comment_missing(self):
        """Returns None when no mangle_rule section."""
        from wanctl.check_cake import _extract_mangle_comment

        comment = _extract_mangle_comment({})
        assert comment is None


# =============================================================================
# TestConnectivityCheck -- CAKE-01
# =============================================================================


class TestConnectivityCheck:
    """Test check_connectivity for REST and SSH transports."""

    def test_rest_connectivity_pass(self):
        """REST transport: test_connection returns True -> PASS."""
        from wanctl.check_cake import check_connectivity

        client = MagicMock()
        client.test_connection.return_value = True

        results = check_connectivity(client, "rest", "10.10.99.1", 443)
        assert len(results) == 1
        assert results[0].severity == Severity.PASS
        assert "rest" in results[0].message
        assert "10.10.99.1" in results[0].message
        assert "443" in results[0].message

    def test_rest_connectivity_fail(self):
        """REST transport: test_connection returns False -> ERROR."""
        from wanctl.check_cake import check_connectivity

        client = MagicMock()
        client.test_connection.return_value = False

        results = check_connectivity(client, "rest", "10.10.99.1", 443)
        assert len(results) == 1
        assert results[0].severity == Severity.ERROR
        assert "rest" in results[0].message

    def test_ssh_connectivity_pass(self):
        """SSH transport: run_cmd returns rc=0 -> PASS."""
        from wanctl.check_cake import check_connectivity

        client = MagicMock(spec=["run_cmd", "close"])  # no test_connection
        client.run_cmd.return_value = (0, "uptime: 5d", "")

        results = check_connectivity(client, "ssh", "10.10.99.1", 22)
        assert len(results) == 1
        assert results[0].severity == Severity.PASS
        assert "ssh" in results[0].message

    def test_ssh_connectivity_fail(self):
        """SSH transport: run_cmd returns rc != 0 -> ERROR."""
        from wanctl.check_cake import check_connectivity

        client = MagicMock(spec=["run_cmd", "close"])
        client.run_cmd.return_value = (1, "", "auth denied")

        results = check_connectivity(client, "ssh", "10.10.99.1", 22)
        assert len(results) == 1
        assert results[0].severity == Severity.ERROR

    def test_connection_exception(self):
        """Connection exception -> ERROR with exception message."""
        from wanctl.check_cake import check_connectivity

        client = MagicMock()
        client.test_connection.side_effect = ConnectionError("Connection refused")

        results = check_connectivity(client, "rest", "10.10.99.1", 443)
        assert len(results) == 1
        assert results[0].severity == Severity.ERROR
        assert "Connection refused" in results[0].message

    def test_timeout_exception(self):
        """TimeoutError -> ERROR."""
        from wanctl.check_cake import check_connectivity

        client = MagicMock()
        client.test_connection.side_effect = TimeoutError("timed out")

        results = check_connectivity(client, "rest", "10.10.99.1", 443)
        assert len(results) == 1
        assert results[0].severity == Severity.ERROR
        assert "timed out" in results[0].message


# =============================================================================
# TestEnvVarCheck -- CAKE-01 env var validation
# =============================================================================


class TestEnvVarCheck:
    """Test check_env_vars for unresolved ${VAR} references."""

    def test_unresolved_env_var_error(self):
        """Unresolved ${ROUTER_PASSWORD} -> ERROR."""
        from wanctl.check_cake import check_env_vars

        data = _autorate_config_data()
        with patch.dict(os.environ, {}, clear=True):
            # Ensure ROUTER_PASSWORD not in environment
            os.environ.pop("ROUTER_PASSWORD", None)
            results = check_env_vars(data)
        assert len(results) >= 1
        errors = [r for r in results if r.severity == Severity.ERROR]
        assert len(errors) == 1
        assert "ROUTER_PASSWORD" in errors[0].message

    def test_resolved_env_var_pass(self):
        """Set env var -> PASS."""
        from wanctl.check_cake import check_env_vars

        data = _autorate_config_data()
        with patch.dict(os.environ, {"ROUTER_PASSWORD": "secret123"}):
            results = check_env_vars(data)
        errors = [r for r in results if r.severity == Severity.ERROR]
        assert len(errors) == 0

    def test_literal_password_pass(self):
        """Literal password (no ${VAR}) -> PASS."""
        from wanctl.check_cake import check_env_vars

        data = _autorate_config_data()
        data["router"]["password"] = "plain_password"
        results = check_env_vars(data)
        errors = [r for r in results if r.severity == Severity.ERROR]
        assert len(errors) == 0

    def test_no_password_pass(self):
        """No password key -> no error (SSH transport uses keys)."""
        from wanctl.check_cake import check_env_vars

        data = _autorate_config_data()
        del data["router"]["password"]
        results = check_env_vars(data)
        errors = [r for r in results if r.severity == Severity.ERROR]
        assert len(errors) == 0


# =============================================================================
# TestQueueAudit -- CAKE-02
# =============================================================================


class TestQueueAudit:
    """Test check_queue_tree for queue existence and names."""

    def test_both_queues_found(self):
        """Both download and upload queues found -> 2+ PASS results."""
        from wanctl.check_cake import check_queue_tree

        client = MagicMock()
        client.get_queue_stats.side_effect = [
            _queue_response("WAN-Download-Spectrum", "cake-down-spectrum", "940000000"),
            _queue_response("WAN-Upload-Spectrum", "cake-up-spectrum", "38000000"),
        ]
        queue_names = {"download": "WAN-Download-Spectrum", "upload": "WAN-Upload-Spectrum"}
        ceilings = {"download": 940_000_000, "upload": 38_000_000}

        results = check_queue_tree(client, queue_names, ceilings, "autorate")
        # Should have PASS for existence + PASS for type for each direction
        passes = [r for r in results if r.severity == Severity.PASS]
        assert len(passes) >= 4  # 2 existence + 2 type (at least)

    def test_download_missing(self):
        """Download queue missing -> ERROR for download, upload still checked."""
        from wanctl.check_cake import check_queue_tree

        client = MagicMock()
        client.get_queue_stats.side_effect = [
            None,  # download missing
            _queue_response("WAN-Upload-Spectrum", "cake-up-spectrum", "38000000"),
        ]
        queue_names = {"download": "WAN-Download-Spectrum", "upload": "WAN-Upload-Spectrum"}
        ceilings = {"download": 940_000_000, "upload": 38_000_000}

        results = check_queue_tree(client, queue_names, ceilings, "autorate")
        errors = [r for r in results if r.severity == Severity.ERROR]
        assert len(errors) >= 1
        assert any("WAN-Download-Spectrum" in r.message for r in errors)
        # Upload should still be checked
        passes = [r for r in results if r.severity == Severity.PASS]
        assert len(passes) >= 1

    def test_upload_missing(self):
        """Upload queue missing -> ERROR for upload."""
        from wanctl.check_cake import check_queue_tree

        client = MagicMock()
        client.get_queue_stats.side_effect = [
            _queue_response("WAN-Download-Spectrum", "cake-down-spectrum", "940000000"),
            None,  # upload missing
        ]
        queue_names = {"download": "WAN-Download-Spectrum", "upload": "WAN-Upload-Spectrum"}
        ceilings = {"download": 940_000_000, "upload": 38_000_000}

        results = check_queue_tree(client, queue_names, ceilings, "autorate")
        errors = [r for r in results if r.severity == Severity.ERROR]
        assert len(errors) >= 1
        assert any("WAN-Upload-Spectrum" in r.message for r in errors)

    def test_partial_failure_reports_both(self):
        """Download found, upload missing -- both reported independently."""
        from wanctl.check_cake import check_queue_tree

        client = MagicMock()
        client.get_queue_stats.side_effect = [
            _queue_response("WAN-Download-Spectrum", "cake-down-spectrum", "940000000"),
            None,  # upload missing
        ]
        queue_names = {"download": "WAN-Download-Spectrum", "upload": "WAN-Upload-Spectrum"}
        ceilings = {"download": 940_000_000, "upload": 38_000_000}

        results = check_queue_tree(client, queue_names, ceilings, "autorate")
        # Should have both PASS (download) and ERROR (upload)
        passes = [r for r in results if r.severity == Severity.PASS]
        errors = [r for r in results if r.severity == Severity.ERROR]
        assert len(passes) >= 1
        assert len(errors) >= 1

    def test_steering_queue_names(self):
        """Steering config uses correct default queue names."""
        from wanctl.check_cake import check_queue_tree

        client = MagicMock()
        client.get_queue_stats.side_effect = [
            _queue_response("WAN-Download-Spectrum", "cake-down-spectrum", "940000000"),
            _queue_response("WAN-Upload-Spectrum", "cake-up-spectrum", "38000000"),
        ]
        queue_names = {"download": "WAN-Download-Spectrum", "upload": "WAN-Upload-Spectrum"}
        ceilings = {"download": None, "upload": None}

        results = check_queue_tree(client, queue_names, ceilings, "steering")
        passes = [r for r in results if r.severity == Severity.PASS]
        assert len(passes) >= 2  # existence + type for each direction


# =============================================================================
# TestCakeType -- CAKE-03
# =============================================================================


class TestCakeType:
    """Test CAKE qdisc type verification within queue audit."""

    def test_cake_type_pass(self):
        """Queue field 'cake-down-spectrum' starts with 'cake' -> PASS."""
        from wanctl.check_cake import check_queue_tree

        client = MagicMock()
        client.get_queue_stats.side_effect = [
            _queue_response("DL", "cake-down-spectrum", "940000000"),
            _queue_response("UL", "cake-up-spectrum", "38000000"),
        ]
        results = check_queue_tree(
            client,
            {"download": "DL", "upload": "UL"},
            {"download": None, "upload": None},
            "steering",
        )
        type_passes = [
            r for r in results if r.severity == Severity.PASS and "cake" in r.message.lower()
        ]
        assert len(type_passes) >= 2

    def test_fq_codel_type_error(self):
        """Queue field 'fq_codel' -> ERROR."""
        from wanctl.check_cake import check_queue_tree

        client = MagicMock()
        client.get_queue_stats.side_effect = [
            _queue_response("DL", "fq_codel", "940000000"),
            _queue_response("UL", "cake-up-spectrum", "38000000"),
        ]
        results = check_queue_tree(
            client,
            {"download": "DL", "upload": "UL"},
            {"download": None, "upload": None},
            "steering",
        )
        errors = [r for r in results if r.severity == Severity.ERROR]
        assert len(errors) >= 1
        assert any("fq_codel" in r.message for r in errors)

    def test_default_type_error(self):
        """Queue field 'default' -> ERROR."""
        from wanctl.check_cake import check_queue_tree

        client = MagicMock()
        client.get_queue_stats.side_effect = [
            _queue_response("DL", "default", "940000000"),
            _queue_response("UL", "default", "38000000"),
        ]
        results = check_queue_tree(
            client,
            {"download": "DL", "upload": "UL"},
            {"download": None, "upload": None},
            "steering",
        )
        errors = [r for r in results if r.severity == Severity.ERROR]
        assert len(errors) >= 2


# =============================================================================
# TestMaxLimitDiff -- CAKE-04
# =============================================================================


class TestMaxLimitDiff:
    """Test ceiling-vs-max-limit comparison for autorate configs."""

    def test_matching_ceiling_pass(self):
        """max-limit equals ceiling -> PASS."""
        from wanctl.check_cake import check_queue_tree

        client = MagicMock()
        client.get_queue_stats.side_effect = [
            _queue_response("DL", "cake-down", "940000000"),
            _queue_response("UL", "cake-up", "38000000"),
        ]
        results = check_queue_tree(
            client,
            {"download": "DL", "upload": "UL"},
            {"download": 940_000_000, "upload": 38_000_000},
            "autorate",
        )
        # All checks should pass
        errors = [r for r in results if r.severity == Severity.ERROR]
        assert len(errors) == 0

    def test_different_ceiling_informational_pass(self):
        """max-limit differs from ceiling -> PASS with informational note."""
        from wanctl.check_cake import check_queue_tree

        client = MagicMock()
        client.get_queue_stats.side_effect = [
            _queue_response("DL", "cake-down", "500000000"),  # currently lower
            _queue_response("UL", "cake-up", "38000000"),
        ]
        results = check_queue_tree(
            client,
            {"download": "DL", "upload": "UL"},
            {"download": 940_000_000, "upload": 38_000_000},
            "autorate",
        )
        # Should still PASS (not ERROR) since max-limit changes during congestion
        errors = [r for r in results if r.severity == Severity.ERROR]
        assert len(errors) == 0
        # Should have an informational message about the difference
        info_results = [
            r for r in results if "500000000" in r.message and "940000000" in r.message
        ]
        assert len(info_results) >= 1

    def test_steering_skips_max_limit(self):
        """Steering config: no ceiling comparison (ceilings are None)."""
        from wanctl.check_cake import check_queue_tree

        client = MagicMock()
        client.get_queue_stats.side_effect = [
            _queue_response("DL", "cake-down", "940000000"),
            _queue_response("UL", "cake-up", "38000000"),
        ]
        results = check_queue_tree(
            client,
            {"download": "DL", "upload": "UL"},
            {"download": None, "upload": None},
            "steering",
        )
        # No max-limit comparison results for steering
        limit_results = [r for r in results if "max-limit" in r.message.lower()]
        assert len(limit_results) == 0


# =============================================================================
# TestMangleCheck -- CAKE-05
# =============================================================================


class TestMangleCheck:
    """Test check_mangle_rule for steering configs."""

    def test_mangle_rule_found_pass(self):
        """Mangle rule found -> PASS."""
        from wanctl.check_cake import check_mangle_rule

        client = MagicMock()
        client._find_mangle_rule_id.return_value = "*5"

        results = check_mangle_rule(client, "ADAPTIVE: Steer latency-sensitive to ATT")
        assert len(results) == 1
        assert results[0].severity == Severity.PASS
        assert "Mangle" in results[0].category or "mangle" in results[0].message.lower()

    def test_mangle_rule_not_found_error(self):
        """Mangle rule not found -> ERROR."""
        from wanctl.check_cake import check_mangle_rule

        client = MagicMock()
        client._find_mangle_rule_id.return_value = None

        results = check_mangle_rule(client, "ADAPTIVE: Steer latency-sensitive to ATT")
        assert len(results) == 1
        assert results[0].severity == Severity.ERROR

    def test_mangle_only_for_steering(self):
        """run_audit only calls check_mangle_rule for steering config type."""
        from wanctl.check_cake import run_audit

        client = MagicMock()
        client.test_connection.return_value = True
        client.get_queue_stats.return_value = _queue_response()
        client._find_mangle_rule_id.return_value = "*5"

        data = _autorate_config_data()
        results = run_audit(data, "autorate", client)
        # Autorate should NOT have mangle-related results
        mangle_results = [r for r in results if r.category == "Mangle Rule"]
        assert len(mangle_results) == 0


# =============================================================================
# TestSkipOnUnreachable -- CAKE-01 skip behavior
# =============================================================================


class TestSkipOnUnreachable:
    """Test that connectivity failure causes remaining checks to be skipped."""

    def test_skip_all_on_unreachable(self):
        """Connectivity ERROR -> all remaining categories skipped."""
        from wanctl.check_cake import run_audit

        client = MagicMock()
        client.test_connection.return_value = False

        data = _autorate_config_data()
        with patch.dict(os.environ, {"ROUTER_PASSWORD": "secret"}):
            results = run_audit(data, "autorate", client)

        # Should have connectivity ERROR
        connectivity_errors = [
            r for r in results if r.category == "Connectivity" and r.severity == Severity.ERROR
        ]
        assert len(connectivity_errors) >= 1

        # Should have skipped results for remaining categories
        skipped = [r for r in results if "Skipped" in r.message and "unreachable" in r.message]
        assert len(skipped) >= 1

    def test_skip_all_on_connection_exception(self):
        """Connection exception -> remaining categories skipped."""
        from wanctl.check_cake import run_audit

        client = MagicMock()
        client.test_connection.side_effect = ConnectionError("refused")

        data = _autorate_config_data()
        with patch.dict(os.environ, {"ROUTER_PASSWORD": "secret"}):
            results = run_audit(data, "autorate", client)

        skipped = [r for r in results if "Skipped" in r.message]
        assert len(skipped) >= 1

    def test_steering_skips_include_mangle(self):
        """Steering connectivity failure skips Queue Tree and Mangle Rule."""
        from wanctl.check_cake import run_audit

        client = MagicMock()
        client.test_connection.return_value = False

        data = _steering_config_data()
        with patch.dict(os.environ, {"ROUTER_PASSWORD": "secret"}):
            results = run_audit(data, "steering", client)

        skipped = [r for r in results if "Skipped" in r.message]
        assert len(skipped) >= 2  # Queue Tree + Mangle Rule


# =============================================================================
# TestCLI -- CLI argument parsing
# =============================================================================


class TestCLI:
    """Test create_parser and main function."""

    def test_parser_accepts_config_file(self):
        """Parser accepts positional config_file argument."""
        from wanctl.check_cake import create_parser

        parser = create_parser()
        args = parser.parse_args(["test.yaml"])
        assert args.config_file == "test.yaml"

    def test_parser_accepts_type_flag(self):
        """Parser accepts --type autorate|steering."""
        from wanctl.check_cake import create_parser

        parser = create_parser()
        args = parser.parse_args(["test.yaml", "--type", "steering"])
        assert args.type == "steering"

    def test_parser_accepts_json_flag(self):
        """Parser accepts --json flag."""
        from wanctl.check_cake import create_parser

        parser = create_parser()
        args = parser.parse_args(["test.yaml", "--json"])
        assert args.json is True

    def test_parser_accepts_no_color_flag(self):
        """Parser accepts --no-color flag."""
        from wanctl.check_cake import create_parser

        parser = create_parser()
        args = parser.parse_args(["test.yaml", "--no-color"])
        assert args.no_color is True

    def test_parser_accepts_quiet_flag(self):
        """Parser accepts -q / --quiet flag."""
        from wanctl.check_cake import create_parser

        parser = create_parser()
        args = parser.parse_args(["test.yaml", "-q"])
        assert args.quiet is True

    def test_main_clean_config_returns_0(self, tmp_path):
        """Clean config with passing router -> exit code 0."""
        from wanctl.check_cake import main

        data = _autorate_config_data()
        config_file = _write_config(tmp_path, data)

        mock_client = MagicMock()
        mock_client.test_connection.return_value = True
        mock_client.get_queue_stats.side_effect = [
            _queue_response("WAN-Download-Spectrum", "cake-down-spectrum", "940000000"),
            _queue_response("WAN-Upload-Spectrum", "cake-up-spectrum", "38000000"),
        ]

        with (
            patch.dict(os.environ, {"ROUTER_PASSWORD": "secret"}),
            patch("wanctl.check_cake._create_audit_client", return_value=mock_client),
            patch("sys.argv", ["wanctl-check-cake", config_file, "--no-color"]),
        ):
            result = main()
        assert result == 0

    def test_main_connectivity_error_returns_1(self, tmp_path):
        """Connectivity error -> exit code 1."""
        from wanctl.check_cake import main

        data = _autorate_config_data()
        config_file = _write_config(tmp_path, data)

        mock_client = MagicMock()
        mock_client.test_connection.return_value = False

        with (
            patch.dict(os.environ, {"ROUTER_PASSWORD": "secret"}),
            patch("wanctl.check_cake._create_audit_client", return_value=mock_client),
            patch("sys.argv", ["wanctl-check-cake", config_file, "--no-color"]),
        ):
            result = main()
        assert result == 1

    def test_main_json_output_is_valid_json(self, tmp_path, capsys):
        """--json flag produces valid JSON output."""
        from wanctl.check_cake import main

        data = _autorate_config_data()
        config_file = _write_config(tmp_path, data)

        mock_client = MagicMock()
        mock_client.test_connection.return_value = True
        mock_client.get_queue_stats.side_effect = [
            _queue_response("WAN-Download-Spectrum", "cake-down-spectrum", "940000000"),
            _queue_response("WAN-Upload-Spectrum", "cake-up-spectrum", "38000000"),
        ]

        with (
            patch.dict(os.environ, {"ROUTER_PASSWORD": "secret"}),
            patch("wanctl.check_cake._create_audit_client", return_value=mock_client),
            patch("sys.argv", ["wanctl-check-cake", config_file, "--json"]),
        ):
            main()
        captured = capsys.readouterr()
        parsed = json.loads(captured.out)
        assert "config_type" in parsed
        assert "result" in parsed

    def test_main_type_override(self, tmp_path):
        """--type steering forces steering config type."""
        from wanctl.check_cake import main

        # Use autorate data but force steering type
        data = _autorate_config_data()
        config_file = _write_config(tmp_path, data)

        mock_client = MagicMock()
        mock_client.test_connection.return_value = True
        mock_client.get_queue_stats.side_effect = [
            _queue_response("WAN-Download-Spectrum", "cake-down-spectrum", "940000000"),
            _queue_response("WAN-Upload-Spectrum", "cake-up-spectrum", "38000000"),
        ]
        mock_client._find_mangle_rule_id.return_value = None

        with (
            patch.dict(os.environ, {"ROUTER_PASSWORD": "secret"}),
            patch("wanctl.check_cake._create_audit_client", return_value=mock_client),
            patch(
                "sys.argv",
                ["wanctl-check-cake", config_file, "--type", "steering", "--no-color"],
            ),
        ):
            result = main()
        # Would have mangle error since no mangle_rule in config
        assert result == 1


# =============================================================================
# TestExitCodes -- exit code convention
# =============================================================================


class TestExitCodes:
    """Test exit code mapping: 0=pass, 1=errors, 2=warnings-only."""

    def test_exit_code_0_all_pass(self, tmp_path):
        """All checks pass -> exit code 0."""
        from wanctl.check_cake import main

        data = _autorate_config_data()
        config_file = _write_config(tmp_path, data)

        mock_client = MagicMock()
        mock_client.test_connection.return_value = True
        mock_client.get_queue_stats.side_effect = [
            _queue_response("WAN-Download-Spectrum", "cake-down-spectrum", "940000000"),
            _queue_response("WAN-Upload-Spectrum", "cake-up-spectrum", "38000000"),
        ]

        with (
            patch.dict(os.environ, {"ROUTER_PASSWORD": "secret"}),
            patch("wanctl.check_cake._create_audit_client", return_value=mock_client),
            patch("sys.argv", ["wanctl-check-cake", config_file, "--no-color"]),
        ):
            result = main()
        assert result == 0

    def test_exit_code_1_errors(self, tmp_path):
        """Any ERROR -> exit code 1."""
        from wanctl.check_cake import main

        data = _autorate_config_data()
        config_file = _write_config(tmp_path, data)

        mock_client = MagicMock()
        mock_client.test_connection.return_value = False

        with (
            patch.dict(os.environ, {"ROUTER_PASSWORD": "secret"}),
            patch("wanctl.check_cake._create_audit_client", return_value=mock_client),
            patch("sys.argv", ["wanctl-check-cake", config_file, "--no-color"]),
        ):
            result = main()
        assert result == 1

    def test_exit_code_1_env_var_error(self, tmp_path):
        """Unresolved env var -> exit code 1."""
        from wanctl.check_cake import main

        data = _autorate_config_data()
        config_file = _write_config(tmp_path, data)

        with (
            patch.dict(os.environ, {}, clear=True),
            patch("sys.argv", ["wanctl-check-cake", config_file, "--no-color"]),
        ):
            # Need to ensure ROUTER_PASSWORD is not in env
            os.environ.pop("ROUTER_PASSWORD", None)
            result = main()
        assert result == 1
