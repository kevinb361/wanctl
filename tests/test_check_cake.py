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
from pathlib import Path
from unittest.mock import MagicMock, patch

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
        info_results = [r for r in results if "500000000" in r.message and "940000000" in r.message]
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

    def test_parser_accepts_fix_flag(self):
        """Parser accepts --fix flag."""
        from wanctl.check_cake import create_parser

        parser = create_parser()
        args = parser.parse_args(["test.yaml", "--fix"])
        assert args.fix is True

    def test_parser_fix_default_false(self):
        """--fix defaults to False."""
        from wanctl.check_cake import create_parser

        parser = create_parser()
        args = parser.parse_args(["test.yaml"])
        assert args.fix is False

    def test_parser_accepts_yes_flag(self):
        """Parser accepts --yes flag."""
        from wanctl.check_cake import create_parser

        parser = create_parser()
        args = parser.parse_args(["test.yaml", "--yes"])
        assert args.yes is True

    def test_parser_accepts_yes_short_form(self):
        """Parser accepts -y short form for --yes."""
        from wanctl.check_cake import create_parser

        parser = create_parser()
        args = parser.parse_args(["test.yaml", "-y"])
        assert args.yes is True

    def test_parser_yes_default_false(self):
        """--yes defaults to False."""
        from wanctl.check_cake import create_parser

        parser = create_parser()
        args = parser.parse_args(["test.yaml"])
        assert args.yes is False

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
            # Step 3.5 re-fetches queue stats
            _queue_response("WAN-Download-Spectrum", "cake-down-spectrum", "940000000"),
            _queue_response("WAN-Upload-Spectrum", "cake-up-spectrum", "38000000"),
        ]
        mock_client.get_queue_types.side_effect = [
            _queue_type_response("cake-down-spectrum", wash="no"),
            _queue_type_response("cake-up-spectrum", wash="yes"),
        ]

        with (
            patch.dict(os.environ, {"ROUTER_PASSWORD": "secret"}),
            patch("wanctl.check_cake._create_audit_client", return_value=mock_client),
            patch("sys.argv", ["wanctl-check-cake", config_file, "--no-color"]),
        ):
            result = main()
        assert result == 0

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
            _queue_response("WAN-Download-Spectrum", "cake-down-spectrum", "940000000"),
            _queue_response("WAN-Upload-Spectrum", "cake-up-spectrum", "38000000"),
        ]
        mock_client.get_queue_types.side_effect = [
            _queue_type_response("cake-down-spectrum", wash="no"),
            _queue_type_response("cake-up-spectrum", wash="yes"),
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
            _queue_response("WAN-Download-Spectrum", "cake-down-spectrum", "940000000"),
            _queue_response("WAN-Upload-Spectrum", "cake-up-spectrum", "38000000"),
        ]
        mock_client.get_queue_types.side_effect = [
            _queue_type_response("cake-down-spectrum", wash="no"),
            _queue_type_response("cake-up-spectrum", wash="yes"),
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
            _queue_response("WAN-Download-Spectrum", "cake-down-spectrum", "940000000"),
            _queue_response("WAN-Upload-Spectrum", "cake-up-spectrum", "38000000"),
        ]
        mock_client.get_queue_types.side_effect = [
            _queue_type_response("cake-down-spectrum", wash="no"),
            _queue_type_response("cake-up-spectrum", wash="yes"),
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


# =============================================================================
# TestGetQueueTypes -- RouterOSREST.get_queue_types()
# =============================================================================


class TestGetQueueTypes:
    """Test get_queue_types() method on RouterOSREST."""

    def _make_client(self):
        """Create a RouterOSREST instance with mocked session."""
        from wanctl.routeros_rest import RouterOSREST

        client = RouterOSREST(
            host="10.10.99.1",
            user="admin",
            password="test",  # pragma: allowlist secret
            port=443,
            verify_ssl=False,
            timeout=15,
        )
        return client

    def test_returns_dict_on_success(self):
        """get_queue_types returns dict with cake-* fields when type exists."""
        client = self._make_client()
        mock_resp = MagicMock()
        mock_resp.ok = True
        mock_resp.json.return_value = [
            {
                ".id": "*A",
                "name": "cake-down-spectrum",
                "kind": "cake",
                "cake-flowmode": "triple-isolate",
                "cake-diffserv": "diffserv4",
                "cake-nat": "yes",
                "cake-ack-filter": "filter",
                "cake-wash": "yes",
                "cake-overhead": "18",
                "cake-overhead-scheme": "none",
                "cake-rtt": "100ms",
                "cake-rtt-scheme": "internet",
            }
        ]

        with patch.object(client._session, "request", return_value=mock_resp) as mock_req:
            result = client.get_queue_types("cake-down-spectrum")

        assert result is not None
        assert result["name"] == "cake-down-spectrum"
        assert result["cake-flowmode"] == "triple-isolate"
        assert result["cake-nat"] == "yes"
        # Verify correct endpoint and params
        mock_req.assert_called_once()
        call_args = mock_req.call_args
        assert "queue/type" in call_args[0][1]
        assert call_args[1]["params"] == {"name": "cake-down-spectrum"}

    def test_returns_none_on_empty_list(self):
        """get_queue_types returns None when type not found (empty list)."""
        client = self._make_client()
        mock_resp = MagicMock()
        mock_resp.ok = True
        mock_resp.json.return_value = []

        with patch.object(client._session, "request", return_value=mock_resp):
            result = client.get_queue_types("nonexistent")

        assert result is None

    def test_returns_none_on_request_exception(self):
        """get_queue_types returns None on requests.RequestException."""
        import requests

        client = self._make_client()

        with patch.object(client._session, "request", side_effect=requests.RequestException("timeout")):
            result = client.get_queue_types("cake-down-spectrum")

        assert result is None

    def test_calls_correct_endpoint(self):
        """get_queue_types calls GET /rest/queue/type with name param."""
        client = self._make_client()
        mock_resp = MagicMock()
        mock_resp.ok = True
        mock_resp.json.return_value = [{"name": "test", ".id": "*1"}]

        with patch.object(client._session, "request", return_value=mock_resp) as mock_req:
            client.get_queue_types("test-type")

        mock_req.assert_called_once_with(
            "GET",
            f"{client.base_url}/queue/type",
            params={"name": "test-type"},
            timeout=client.timeout,
        )


# =============================================================================
# TestOptimalDefaults -- CAKE optimal constants
# =============================================================================


class TestOptimalDefaults:
    """Test OPTIMAL_CAKE_DEFAULTS and OPTIMAL_WASH constants."""

    def test_optimal_cake_defaults_has_four_keys(self):
        """OPTIMAL_CAKE_DEFAULTS has exactly 4 link-independent params."""
        from wanctl.check_cake import OPTIMAL_CAKE_DEFAULTS

        assert len(OPTIMAL_CAKE_DEFAULTS) == 4

    def test_optimal_cake_defaults_flowmode(self):
        """cake-flowmode optimal is triple-isolate."""
        from wanctl.check_cake import OPTIMAL_CAKE_DEFAULTS

        assert OPTIMAL_CAKE_DEFAULTS["cake-flowmode"] == "triple-isolate"

    def test_optimal_cake_defaults_diffserv(self):
        """cake-diffserv optimal is diffserv4."""
        from wanctl.check_cake import OPTIMAL_CAKE_DEFAULTS

        assert OPTIMAL_CAKE_DEFAULTS["cake-diffserv"] == "diffserv4"

    def test_optimal_cake_defaults_nat(self):
        """cake-nat optimal is yes."""
        from wanctl.check_cake import OPTIMAL_CAKE_DEFAULTS

        assert OPTIMAL_CAKE_DEFAULTS["cake-nat"] == "yes"

    def test_optimal_cake_defaults_ack_filter(self):
        """cake-ack-filter optimal is filter (RouterOS 'enabled' value)."""
        from wanctl.check_cake import OPTIMAL_CAKE_DEFAULTS

        assert OPTIMAL_CAKE_DEFAULTS["cake-ack-filter"] == "filter"

    def test_optimal_wash_upload(self):
        """OPTIMAL_WASH upload is yes."""
        from wanctl.check_cake import OPTIMAL_WASH

        assert OPTIMAL_WASH["upload"] == "yes"

    def test_optimal_wash_download(self):
        """OPTIMAL_WASH download is no."""
        from wanctl.check_cake import OPTIMAL_WASH

        assert OPTIMAL_WASH["download"] == "no"

    def test_optimal_wash_has_two_keys(self):
        """OPTIMAL_WASH has exactly upload and download."""
        from wanctl.check_cake import OPTIMAL_WASH

        assert set(OPTIMAL_WASH.keys()) == {"upload", "download"}

    def test_all_values_are_strings(self):
        """All values in both dicts are strings (RouterOS REST API format)."""
        from wanctl.check_cake import OPTIMAL_CAKE_DEFAULTS, OPTIMAL_WASH

        for val in OPTIMAL_CAKE_DEFAULTS.values():
            assert isinstance(val, str)
        for val in OPTIMAL_WASH.values():
            assert isinstance(val, str)


# =============================================================================
# TestExtractCakeOptimization -- config extractor
# =============================================================================


class TestExtractCakeOptimization:
    """Test _extract_cake_optimization() config extractor."""

    def test_extracts_present_config(self):
        """Returns dict when cake_optimization section exists."""
        from wanctl.check_cake import _extract_cake_optimization

        data = {
            "cake_optimization": {
                "overhead": 18,
                "rtt": "100ms",
            }
        }
        result = _extract_cake_optimization(data)
        assert result is not None
        assert result["overhead"] == 18
        assert result["rtt"] == "100ms"

    def test_returns_none_when_absent(self):
        """Returns None when cake_optimization key is absent."""
        from wanctl.check_cake import _extract_cake_optimization

        data = {"router": {"host": "10.10.99.1"}}
        result = _extract_cake_optimization(data)
        assert result is None

    def test_returns_none_when_value_is_none(self):
        """Returns None when cake_optimization value is None (empty YAML key)."""
        from wanctl.check_cake import _extract_cake_optimization

        data = {"cake_optimization": None}
        result = _extract_cake_optimization(data)
        assert result is None


# =============================================================================
# TestCheckCakeParams -- CAKE param detection
# =============================================================================


def _optimal_queue_type_data(direction: str = "download") -> dict:
    """Return a queue type dict with all optimal CAKE params."""
    from wanctl.check_cake import OPTIMAL_CAKE_DEFAULTS, OPTIMAL_WASH

    data = dict(OPTIMAL_CAKE_DEFAULTS)
    data["cake-wash"] = OPTIMAL_WASH[direction]
    data["name"] = f"cake-{direction}-spectrum"
    data[".id"] = "*A"
    data["cake-overhead"] = "18"
    data["cake-rtt"] = "100ms"
    return data


class TestCheckCakeParams:
    """Test check_cake_params() for link-independent CAKE param detection."""

    def test_all_optimal_returns_pass(self):
        """All params match optimal defaults -> all PASS results."""
        from wanctl.check_cake import check_cake_params

        data = _optimal_queue_type_data("download")
        results = check_cake_params(data, "download")
        assert all(r.severity == Severity.PASS for r in results)
        assert len(results) == 5  # 4 defaults + wash

    def test_suboptimal_flowmode_returns_warning(self):
        """flowmode=dual-srchost -> WARNING with diff message."""
        from wanctl.check_cake import check_cake_params

        data = _optimal_queue_type_data("download")
        data["cake-flowmode"] = "dual-srchost"
        results = check_cake_params(data, "download")
        warnings = [r for r in results if r.severity == Severity.WARN]
        assert len(warnings) >= 1
        assert any("dual-srchost -> triple-isolate" in r.message for r in warnings)

    def test_suboptimal_diffserv_returns_warning(self):
        """diffserv=diffserv3 -> WARNING with diff message."""
        from wanctl.check_cake import check_cake_params

        data = _optimal_queue_type_data("download")
        data["cake-diffserv"] = "diffserv3"
        results = check_cake_params(data, "download")
        warnings = [r for r in results if r.severity == Severity.WARN]
        assert any("diffserv3 -> diffserv4" in r.message for r in warnings)

    def test_suboptimal_nat_returns_warning(self):
        """nat=no -> WARNING with diff message."""
        from wanctl.check_cake import check_cake_params

        data = _optimal_queue_type_data("download")
        data["cake-nat"] = "no"
        results = check_cake_params(data, "download")
        warnings = [r for r in results if r.severity == Severity.WARN]
        assert any("no -> yes" in r.message for r in warnings)

    def test_suboptimal_ack_filter_returns_warning(self):
        """ack-filter=none -> WARNING with diff message."""
        from wanctl.check_cake import check_cake_params

        data = _optimal_queue_type_data("download")
        data["cake-ack-filter"] = "none"
        results = check_cake_params(data, "download")
        warnings = [r for r in results if r.severity == Severity.WARN]
        assert any("none -> filter" in r.message for r in warnings)

    def test_wash_upload_suboptimal_returns_warning(self):
        """wash=no on upload -> WARNING (ISP ignores DSCP rationale)."""
        from wanctl.check_cake import check_cake_params

        data = _optimal_queue_type_data("upload")
        data["cake-wash"] = "no"
        results = check_cake_params(data, "upload")
        warnings = [r for r in results if r.severity == Severity.WARN]
        assert any("no -> yes" in r.message for r in warnings)
        # Verify rationale mentions ISP
        assert any("ISP" in r.suggestion for r in warnings if r.suggestion)

    def test_wash_download_suboptimal_returns_warning(self):
        """wash=yes on download -> WARNING (preserve DSCP for LAN/WMM rationale)."""
        from wanctl.check_cake import check_cake_params

        data = _optimal_queue_type_data("download")
        data["cake-wash"] = "yes"
        results = check_cake_params(data, "download")
        warnings = [r for r in results if r.severity == Severity.WARN]
        assert any("yes -> no" in r.message for r in warnings)
        # Verify rationale mentions DSCP/LAN/WMM
        assert any("DSCP" in r.suggestion for r in warnings if r.suggestion)

    def test_wash_upload_optimal_returns_pass(self):
        """wash=yes on upload -> PASS."""
        from wanctl.check_cake import check_cake_params

        data = _optimal_queue_type_data("upload")
        results = check_cake_params(data, "upload")
        wash_results = [r for r in results if "wash" in r.message]
        assert all(r.severity == Severity.PASS for r in wash_results)

    def test_wash_download_optimal_returns_pass(self):
        """wash=no on download -> PASS."""
        from wanctl.check_cake import check_cake_params

        data = _optimal_queue_type_data("download")
        results = check_cake_params(data, "download")
        wash_results = [r for r in results if "wash" in r.message]
        assert all(r.severity == Severity.PASS for r in wash_results)

    def test_category_includes_direction(self):
        """Category string includes direction (download or upload)."""
        from wanctl.check_cake import check_cake_params

        dl_results = check_cake_params(_optimal_queue_type_data("download"), "download")
        assert all(r.category == "CAKE Params (download)" for r in dl_results)

        ul_results = check_cake_params(_optimal_queue_type_data("upload"), "upload")
        assert all(r.category == "CAKE Params (upload)" for r in ul_results)

    def test_diff_format_in_message(self):
        """Sub-optimal param shows 'current -> recommended' pattern in message."""
        from wanctl.check_cake import check_cake_params

        data = _optimal_queue_type_data("download")
        data["cake-flowmode"] = "dual-srchost"
        results = check_cake_params(data, "download")
        warnings = [r for r in results if r.severity == Severity.WARN]
        assert any("->" in r.message for r in warnings)

    def test_suggestion_present_on_warning(self):
        """WARNING results have a rationale in suggestion field."""
        from wanctl.check_cake import check_cake_params

        data = _optimal_queue_type_data("download")
        data["cake-nat"] = "no"
        results = check_cake_params(data, "download")
        warnings = [r for r in results if r.severity == Severity.WARN]
        assert all(r.suggestion is not None and len(r.suggestion) > 0 for r in warnings)


# =============================================================================
# TestCheckLinkParams -- link-dependent param detection
# =============================================================================


class TestCheckLinkParams:
    """Test check_link_params() for link-dependent CAKE param detection."""

    def test_matching_overhead_and_rtt_returns_pass(self):
        """Overhead and RTT match config -> PASS."""
        from wanctl.check_cake import check_link_params

        data = _optimal_queue_type_data("download")
        cake_config = {"overhead": 18, "rtt": "100ms"}
        results = check_link_params(data, "download", cake_config)
        assert all(r.severity == Severity.PASS for r in results)
        assert len(results) == 2  # overhead + rtt

    def test_wrong_overhead_returns_error(self):
        """Overhead mismatch -> ERROR with diff message."""
        from wanctl.check_cake import check_link_params

        data = _optimal_queue_type_data("download")
        data["cake-overhead"] = "44"
        cake_config = {"overhead": 18, "rtt": "100ms"}
        results = check_link_params(data, "download", cake_config)
        errors = [r for r in results if r.severity == Severity.ERROR]
        assert len(errors) >= 1
        assert any("44 -> 18" in r.message for r in errors)

    def test_wrong_rtt_returns_error(self):
        """RTT mismatch -> ERROR with diff message."""
        from wanctl.check_cake import check_link_params

        data = _optimal_queue_type_data("download")
        data["cake-rtt"] = "200ms"
        cake_config = {"overhead": 18, "rtt": "100ms"}
        results = check_link_params(data, "download", cake_config)
        errors = [r for r in results if r.severity == Severity.ERROR]
        assert len(errors) >= 1
        assert any("200ms -> 100ms" in r.message for r in errors)

    def test_no_config_returns_info(self):
        """cake_config=None -> INFO result about missing config."""
        from wanctl.check_cake import check_link_params

        data = _optimal_queue_type_data("download")
        results = check_link_params(data, "download", None)
        assert len(results) == 1
        assert results[0].severity == Severity.PASS  # INFO-level mapped to PASS
        assert "cake_optimization" in results[0].message

    def test_integer_overhead_compared_as_string(self):
        """YAML int 18 compared as string against router '18' -> PASS."""
        from wanctl.check_cake import check_link_params

        data = _optimal_queue_type_data("download")
        data["cake-overhead"] = "18"
        cake_config = {"overhead": 18, "rtt": "100ms"}  # int from YAML
        results = check_link_params(data, "download", cake_config)
        overhead_results = [r for r in results if "overhead" in r.message]
        assert all(r.severity == Severity.PASS for r in overhead_results)

    def test_rtt_string_comparison(self):
        """YAML '100ms' matches router '100ms' -> PASS."""
        from wanctl.check_cake import check_link_params

        data = _optimal_queue_type_data("download")
        data["cake-rtt"] = "100ms"
        cake_config = {"overhead": 18, "rtt": "100ms"}
        results = check_link_params(data, "download", cake_config)
        rtt_results = [r for r in results if "rtt" in r.message]
        assert all(r.severity == Severity.PASS for r in rtt_results)

    def test_category_includes_direction(self):
        """Category string includes direction."""
        from wanctl.check_cake import check_link_params

        cake_config = {"overhead": 18, "rtt": "100ms"}
        dl_results = check_link_params(
            _optimal_queue_type_data("download"), "download", cake_config
        )
        assert all(r.category == "Link Params (download)" for r in dl_results)

        ul_results = check_link_params(_optimal_queue_type_data("upload"), "upload", cake_config)
        assert all(r.category == "Link Params (upload)" for r in ul_results)


# =============================================================================
# TestRunAuditCakeParams -- pipeline integration
# =============================================================================


def _queue_type_response(
    name: str = "cake-down-spectrum",
    flowmode: str = "triple-isolate",
    diffserv: str = "diffserv4",
    nat: str = "yes",
    ack_filter: str = "filter",
    wash: str = "no",
    overhead: str = "18",
    rtt: str = "100ms",
) -> dict:
    """Return a mock RouterOS queue type response dict."""
    return {
        ".id": "*A",
        "name": name,
        "kind": "cake",
        "cake-flowmode": flowmode,
        "cake-diffserv": diffserv,
        "cake-nat": nat,
        "cake-ack-filter": ack_filter,
        "cake-wash": wash,
        "cake-overhead": overhead,
        "cake-rtt": rtt,
        "cake-rtt-scheme": "internet",
    }


class TestRunAuditCakeParams:
    """Test CAKE param checks wired into run_audit() pipeline."""

    def test_audit_includes_cake_param_checks(self):
        """run_audit includes CAKE Params and Link Params results."""
        from wanctl.check_cake import run_audit

        client = MagicMock()
        client.test_connection.return_value = True
        # First call per direction for check_queue_tree, second for step 3.5
        client.get_queue_stats.side_effect = [
            _queue_response("WAN-Download-Spectrum", "cake-down-spectrum", "940000000"),
            _queue_response("WAN-Upload-Spectrum", "cake-up-spectrum", "38000000"),
            # Step 3.5 re-fetches queue stats
            _queue_response("WAN-Download-Spectrum", "cake-down-spectrum", "940000000"),
            _queue_response("WAN-Upload-Spectrum", "cake-up-spectrum", "38000000"),
        ]
        client.get_queue_types.side_effect = [
            _queue_type_response("cake-down-spectrum", wash="no"),
            _queue_type_response("cake-up-spectrum", wash="yes"),
        ]

        data = _autorate_config_data()
        data["cake_optimization"] = {"overhead": 18, "rtt": "100ms"}

        with patch.dict(os.environ, {"ROUTER_PASSWORD": "secret"}):
            results = run_audit(data, "autorate", client)

        # Should have CAKE Params results
        cake_param_results = [r for r in results if r.category.startswith("CAKE Params")]
        assert len(cake_param_results) >= 10  # 5 per direction

        # Should have Link Params results
        link_param_results = [r for r in results if r.category.startswith("Link Params")]
        assert len(link_param_results) >= 4  # 2 per direction (overhead + rtt)

    def test_audit_skips_cake_params_when_not_cake_type(self):
        """Queue type not starting with 'cake' -> no CAKE Params results."""
        from wanctl.check_cake import run_audit

        client = MagicMock()
        client.test_connection.return_value = True
        client.get_queue_stats.side_effect = [
            # check_queue_tree calls
            _queue_response("DL", "fq_codel", "940000000"),
            _queue_response("UL", "fq_codel", "38000000"),
            # step 3.5 re-fetches
            _queue_response("DL", "fq_codel", "940000000"),
            _queue_response("UL", "fq_codel", "38000000"),
        ]

        data = _autorate_config_data()
        with patch.dict(os.environ, {"ROUTER_PASSWORD": "secret"}):
            results = run_audit(data, "autorate", client)

        cake_param_results = [r for r in results if r.category.startswith("CAKE Params")]
        assert len(cake_param_results) == 0
        # get_queue_types should NOT have been called
        client.get_queue_types.assert_not_called()

    def test_audit_skips_cake_params_on_connectivity_failure(self):
        """Connectivity failure skips CAKE Params and Link Params categories."""
        from wanctl.check_cake import run_audit

        client = MagicMock()
        client.test_connection.return_value = False

        data = _autorate_config_data()
        with patch.dict(os.environ, {"ROUTER_PASSWORD": "secret"}):
            results = run_audit(data, "autorate", client)

        skipped = [r for r in results if "Skipped" in r.message]
        skipped_cats = {r.category for r in skipped}
        assert "CAKE Params (download)" in skipped_cats
        assert "CAKE Params (upload)" in skipped_cats
        assert "Link Params (download)" in skipped_cats
        assert "Link Params (upload)" in skipped_cats

    def test_audit_handles_missing_queue_type(self):
        """get_queue_types returns None -> ERROR result."""
        from wanctl.check_cake import run_audit

        client = MagicMock()
        client.test_connection.return_value = True
        client.get_queue_stats.side_effect = [
            _queue_response("DL", "cake-down-spectrum", "940000000"),
            _queue_response("UL", "cake-up-spectrum", "38000000"),
            # step 3.5 re-fetches
            _queue_response("DL", "cake-down-spectrum", "940000000"),
            _queue_response("UL", "cake-up-spectrum", "38000000"),
        ]
        client.get_queue_types.return_value = None

        data = _autorate_config_data()
        with patch.dict(os.environ, {"ROUTER_PASSWORD": "secret"}):
            results = run_audit(data, "autorate", client)

        cake_errors = [
            r
            for r in results
            if r.category.startswith("CAKE Params") and r.severity == Severity.ERROR
        ]
        assert len(cake_errors) >= 2  # one per direction
        assert any("Queue type not found" in r.message for r in cake_errors)

    def test_audit_link_params_skipped_when_no_config(self):
        """No cake_optimization in data -> INFO message for link params."""
        from wanctl.check_cake import run_audit

        client = MagicMock()
        client.test_connection.return_value = True
        client.get_queue_stats.side_effect = [
            _queue_response("DL", "cake-down-spectrum", "940000000"),
            _queue_response("UL", "cake-up-spectrum", "38000000"),
            _queue_response("DL", "cake-down-spectrum", "940000000"),
            _queue_response("UL", "cake-up-spectrum", "38000000"),
        ]
        client.get_queue_types.side_effect = [
            _queue_type_response("cake-down-spectrum", wash="no"),
            _queue_type_response("cake-up-spectrum", wash="yes"),
        ]

        data = _autorate_config_data()
        # No cake_optimization key
        with patch.dict(os.environ, {"ROUTER_PASSWORD": "secret"}):
            results = run_audit(data, "autorate", client)

        link_results = [r for r in results if r.category.startswith("Link Params")]
        assert len(link_results) >= 2  # one INFO per direction
        assert all("cake_optimization" in r.message for r in link_results)

    def test_audit_link_params_with_config(self):
        """cake_optimization present -> overhead/rtt checks run."""
        from wanctl.check_cake import run_audit

        client = MagicMock()
        client.test_connection.return_value = True
        client.get_queue_stats.side_effect = [
            _queue_response("DL", "cake-down-spectrum", "940000000"),
            _queue_response("UL", "cake-up-spectrum", "38000000"),
            _queue_response("DL", "cake-down-spectrum", "940000000"),
            _queue_response("UL", "cake-up-spectrum", "38000000"),
        ]
        client.get_queue_types.side_effect = [
            _queue_type_response("cake-down-spectrum", wash="no", overhead="18", rtt="100ms"),
            _queue_type_response("cake-up-spectrum", wash="yes", overhead="18", rtt="100ms"),
        ]

        data = _autorate_config_data()
        data["cake_optimization"] = {"overhead": 18, "rtt": "100ms"}

        with patch.dict(os.environ, {"ROUTER_PASSWORD": "secret"}):
            results = run_audit(data, "autorate", client)

        link_results = [r for r in results if r.category.startswith("Link Params")]
        # Should have overhead + rtt for each direction = 4 results
        assert len(link_results) == 4
        assert all(r.severity == Severity.PASS for r in link_results)


# =============================================================================
# TestKnownPaths -- KNOWN_AUTORATE_PATHS includes cake_optimization
# =============================================================================


class TestKnownPaths:
    """Test KNOWN_AUTORATE_PATHS includes cake_optimization paths."""

    def test_cake_optimization_paths_in_known_autorate(self):
        """cake_optimization, cake_optimization.overhead, cake_optimization.rtt in KNOWN_AUTORATE_PATHS."""
        from wanctl.check_config_validators import KNOWN_AUTORATE_PATHS

        assert "cake_optimization" in KNOWN_AUTORATE_PATHS
        assert "cake_optimization.overhead" in KNOWN_AUTORATE_PATHS
        assert "cake_optimization.rtt" in KNOWN_AUTORATE_PATHS


# =============================================================================
# TestSetQueueTypeParams -- RouterOSREST.set_queue_type_params()
# =============================================================================


class TestSetQueueTypeParams:
    """Test set_queue_type_params() method on RouterOSREST."""

    def _make_client(self):
        """Create a RouterOSREST instance with mocked session."""
        from wanctl.routeros_rest import RouterOSREST

        client = RouterOSREST(
            host="10.10.99.1",
            user="admin",
            password="test",  # pragma: allowlist secret
            port=443,
            verify_ssl=False,
            timeout=15,
        )
        return client

    def test_success_finds_id_and_patches(self):
        """set_queue_type_params finds ID via GET, PATCHes to /queue/type/{id}, returns True."""
        client = self._make_client()
        # Mock GET response for finding ID
        get_resp = MagicMock()
        get_resp.ok = True
        get_resp.json.return_value = [{"name": "cake-down-spectrum", ".id": "*A"}]
        # Mock PATCH response
        patch_resp = MagicMock()
        patch_resp.ok = True

        with patch.object(client._session, "request", side_effect=[get_resp, patch_resp]) as mock_req:
            result = client.set_queue_type_params("cake-down-spectrum", {"cake-nat": "yes"})

        assert result is True
        # Verify GET to find ID
        get_call = mock_req.call_args_list[0]
        assert get_call[0][0] == "GET"
        assert "queue/type" in get_call[0][1]
        assert get_call[1]["params"] == {"name": "cake-down-spectrum"}
        # Verify PATCH with correct endpoint and payload
        patch_call = mock_req.call_args_list[1]
        assert patch_call[0][0] == "PATCH"
        assert "/queue/type/*A" in patch_call[0][1]
        assert patch_call[1]["json"] == {"cake-nat": "yes"}

    def test_returns_false_when_type_not_found(self):
        """Returns False when queue type not found (empty GET response)."""
        client = self._make_client()
        get_resp = MagicMock()
        get_resp.ok = True
        get_resp.json.return_value = []

        with patch.object(client._session, "request", return_value=get_resp):
            result = client.set_queue_type_params("nonexistent", {"cake-nat": "yes"})

        assert result is False

    def test_returns_false_on_patch_failure(self):
        """Returns False on PATCH failure (non-200 status)."""
        client = self._make_client()
        get_resp = MagicMock()
        get_resp.ok = True
        get_resp.json.return_value = [{"name": "cake-down-spectrum", ".id": "*A"}]
        patch_resp = MagicMock()
        patch_resp.ok = False
        patch_resp.status_code = 400

        with patch.object(client._session, "request", side_effect=[get_resp, patch_resp]):
            result = client.set_queue_type_params("cake-down-spectrum", {"cake-nat": "yes"})

        assert result is False

    def test_returns_false_on_request_exception(self):
        """Returns False on RequestException."""
        import requests

        client = self._make_client()
        # GET to find ID succeeds
        get_resp = MagicMock()
        get_resp.ok = True
        get_resp.json.return_value = [{"name": "cake-down-spectrum", ".id": "*A"}]

        with patch.object(
            client._session,
            "request",
            side_effect=[get_resp, requests.RequestException("timeout")],
        ):
            result = client.set_queue_type_params("cake-down-spectrum", {"cake-nat": "yes"})

        assert result is False

    def test_all_values_in_patch_body_are_strings(self):
        """All values in PATCH body are strings (never int/bool)."""
        client = self._make_client()
        get_resp = MagicMock()
        get_resp.ok = True
        get_resp.json.return_value = [{"name": "cake-down-spectrum", ".id": "*A"}]
        patch_resp = MagicMock()
        patch_resp.ok = True

        params = {"cake-overhead": "18", "cake-rtt": "100ms", "cake-nat": "yes"}
        with patch.object(client._session, "request", side_effect=[get_resp, patch_resp]) as mock_req:
            client.set_queue_type_params("cake-down-spectrum", params)

        patch_call = mock_req.call_args_list[1]
        json_payload = patch_call[1]["json"]
        for val in json_payload.values():
            assert isinstance(val, str), f"Value {val!r} is not a string"

    def test_uses_queue_type_endpoint_not_tree(self):
        """Uses correct endpoint /queue/type (not /queue/tree)."""
        client = self._make_client()
        get_resp = MagicMock()
        get_resp.ok = True
        get_resp.json.return_value = [{"name": "cake-down-spectrum", ".id": "*A"}]
        patch_resp = MagicMock()
        patch_resp.ok = True

        with patch.object(client._session, "request", side_effect=[get_resp, patch_resp]) as mock_req:
            client.set_queue_type_params("cake-down-spectrum", {"cake-nat": "yes"})

        # GET should use /queue/type
        get_url = mock_req.call_args_list[0][0][1]
        assert "/queue/type" in get_url
        assert "/queue/tree" not in get_url
        # PATCH should use /queue/type/{id}
        patch_url = mock_req.call_args_list[1][0][1]
        assert "/queue/type/" in patch_url
        assert "/queue/tree/" not in patch_url


# =============================================================================
# TestDaemonLock -- check_daemon_lock()
# =============================================================================


class TestDaemonLock:
    """Test check_daemon_lock() for detecting running wanctl daemon."""

    def test_pass_when_lock_dir_does_not_exist(self, tmp_path):
        """Returns PASS when /run/wanctl/ does not exist."""
        from wanctl.check_cake import check_daemon_lock

        fake_run_dir = tmp_path / "run" / "wanctl"
        # Directory does not exist
        with patch("wanctl.check_cake.LOCK_DIR", fake_run_dir):
            results = check_daemon_lock()

        assert len(results) == 1
        assert results[0].severity == Severity.PASS
        assert results[0].category == "Daemon Lock"

    def test_pass_when_lock_files_have_dead_pid(self, tmp_path):
        """Returns PASS when lock files exist but PID is dead."""
        from wanctl.check_cake import check_daemon_lock

        fake_run_dir = tmp_path / "run" / "wanctl"
        fake_run_dir.mkdir(parents=True)
        lock_file = fake_run_dir / "spectrum.lock"
        lock_file.write_text("99999\n")

        with (
            patch("wanctl.check_cake.LOCK_DIR", fake_run_dir),
            patch("wanctl.check_cake.read_lock_pid", return_value=99999),
            patch("wanctl.check_cake.is_process_alive", return_value=False),
        ):
            results = check_daemon_lock()

        assert len(results) == 1
        assert results[0].severity == Severity.PASS

    def test_error_when_lock_file_has_live_pid(self, tmp_path):
        """Returns ERROR when lock file has live PID, with suggestion to stop daemon."""
        from wanctl.check_cake import check_daemon_lock

        fake_run_dir = tmp_path / "run" / "wanctl"
        fake_run_dir.mkdir(parents=True)
        lock_file = fake_run_dir / "spectrum.lock"
        lock_file.write_text("12345\n")

        with (
            patch("wanctl.check_cake.LOCK_DIR", fake_run_dir),
            patch("wanctl.check_cake.read_lock_pid", return_value=12345),
            patch("wanctl.check_cake.is_process_alive", return_value=True),
        ):
            results = check_daemon_lock()

        assert len(results) == 1
        assert results[0].severity == Severity.ERROR
        assert results[0].category == "Daemon Lock"
        assert results[0].field == "lock_check"
        assert "stop" in results[0].suggestion.lower() or "Stop" in results[0].suggestion


# =============================================================================
# TestSnapshot -- save_snapshot() and _prune_snapshots()
# =============================================================================


class TestSnapshot:
    """Test save_snapshot() and _prune_snapshots()."""

    def test_save_snapshot_writes_json_file(self, tmp_path):
        """save_snapshot writes JSON to snapshots dir with correct structure."""
        from wanctl.check_cake_fix import save_snapshot

        queue_data = {
            "cake-down-spectrum": {
                ".id": "*A",
                "name": "cake-down-spectrum",
                "cake-flowmode": "triple-isolate",
            }
        }

        with patch("wanctl.check_cake_fix.SNAPSHOT_DIR", tmp_path):
            path = save_snapshot(queue_data, "spectrum")

        assert path.exists()
        assert path.suffix == ".json"
        assert "spectrum" in path.name

        content = json.loads(path.read_text())
        assert "queue_types" in content
        assert "timestamp" in content
        assert "wan_name" in content
        assert content["wan_name"] == "spectrum"

    def test_prune_snapshots_removes_oldest(self, tmp_path):
        """_prune_snapshots removes oldest files when count exceeds MAX_SNAPSHOTS."""
        from wanctl.check_cake_fix import _prune_snapshots

        # Create 25 snapshot files (MAX_SNAPSHOTS = 20)
        for i in range(25):
            ts = f"20260313T{i:06d}Z"
            f = tmp_path / f"{ts}_spectrum.json"
            f.write_text("{}")

        with patch("wanctl.check_cake_fix.SNAPSHOT_DIR", tmp_path):
            _prune_snapshots("spectrum")

        remaining = list(tmp_path.glob("*_spectrum.json"))
        assert len(remaining) == 20

    def test_prune_keeps_files_for_other_wans(self, tmp_path):
        """_prune_snapshots only prunes files matching the specified WAN name."""
        from wanctl.check_cake_fix import _prune_snapshots

        # Create 25 spectrum files and 5 att files
        for i in range(25):
            ts = f"20260313T{i:06d}Z"
            f = tmp_path / f"{ts}_spectrum.json"
            f.write_text("{}")
        for i in range(5):
            ts = f"20260313T{i:06d}Z"
            f = tmp_path / f"{ts}_att.json"
            f.write_text("{}")

        with patch("wanctl.check_cake_fix.SNAPSHOT_DIR", tmp_path):
            _prune_snapshots("spectrum")

        spectrum_remaining = list(tmp_path.glob("*_spectrum.json"))
        att_remaining = list(tmp_path.glob("*_att.json"))
        assert len(spectrum_remaining) == 20
        assert len(att_remaining) == 5  # Untouched


# =============================================================================
# TestExtractChanges -- _extract_changes_for_direction()
# =============================================================================


class TestExtractChanges:
    """Test _extract_changes_for_direction()."""

    def test_returns_empty_when_all_optimal(self):
        """Returns empty dict when all params are optimal."""
        from wanctl.check_cake_fix import _extract_changes_for_direction

        data = _optimal_queue_type_data("download")
        changes = _extract_changes_for_direction(data, "download", None)
        assert changes == {}

    def test_returns_changes_for_suboptimal_params(self):
        """Returns {key: (current, recommended)} for each sub-optimal param."""
        from wanctl.check_cake_fix import _extract_changes_for_direction

        data = _optimal_queue_type_data("download")
        data["cake-nat"] = "no"
        data["cake-flowmode"] = "dual-srchost"
        changes = _extract_changes_for_direction(data, "download", None)

        assert "cake-nat" in changes
        assert changes["cake-nat"] == ("no", "yes")
        assert "cake-flowmode" in changes
        assert changes["cake-flowmode"] == ("dual-srchost", "triple-isolate")

    def test_includes_wash_with_direction_dependent_value(self):
        """Includes wash with direction-dependent expected value."""
        from wanctl.check_cake_fix import _extract_changes_for_direction

        # Upload with wrong wash
        data = _optimal_queue_type_data("upload")
        data["cake-wash"] = "no"
        changes = _extract_changes_for_direction(data, "upload", None)
        assert "cake-wash" in changes
        assert changes["cake-wash"] == ("no", "yes")

        # Download with wrong wash
        data2 = _optimal_queue_type_data("download")
        data2["cake-wash"] = "yes"
        changes2 = _extract_changes_for_direction(data2, "download", None)
        assert "cake-wash" in changes2
        assert changes2["cake-wash"] == ("yes", "no")

    def test_includes_overhead_and_rtt_when_cake_config_present(self):
        """Includes overhead and rtt when cake_config is present."""
        from wanctl.check_cake_fix import _extract_changes_for_direction

        data = _optimal_queue_type_data("download")
        data["cake-overhead"] = "44"
        data["cake-rtt"] = "200ms"
        cake_config = {"overhead": 18, "rtt": "100ms"}
        changes = _extract_changes_for_direction(data, "download", cake_config)

        assert "cake-overhead" in changes
        assert changes["cake-overhead"] == ("44", "18")
        assert "cake-rtt" in changes
        assert changes["cake-rtt"] == ("200ms", "100ms")

    def test_skips_overhead_rtt_when_no_cake_config(self):
        """Skips overhead/rtt when cake_config is None."""
        from wanctl.check_cake_fix import _extract_changes_for_direction

        data = _optimal_queue_type_data("download")
        data["cake-overhead"] = "44"  # Wrong but should be ignored
        data["cake-rtt"] = "200ms"  # Wrong but should be ignored
        changes = _extract_changes_for_direction(data, "download", None)

        assert "cake-overhead" not in changes
        assert "cake-rtt" not in changes


# =============================================================================
# TestShowDiffTable -- show_diff_table()
# =============================================================================


class TestShowDiffTable:
    """Test show_diff_table() for printing proposed changes."""

    def test_prints_table_with_columns(self, capsys):
        """Prints table with Parameter | Current | Recommended columns."""
        from wanctl.check_cake_fix import show_diff_table

        changes = {
            "download": {
                "cake-nat": ("no", "yes"),
                "cake-flowmode": ("dual-srchost", "triple-isolate"),
            },
        }
        queue_names = {"download": "cake-down-spectrum", "upload": "cake-up-spectrum"}
        total = show_diff_table(changes, queue_names)

        captured = capsys.readouterr()
        assert "Parameter" in captured.err
        assert "Current" in captured.err
        assert "Recommended" in captured.err
        assert total == 2

    def test_strips_cake_prefix_from_param_names(self, capsys):
        """Strips 'cake-' prefix from parameter names for display."""
        from wanctl.check_cake_fix import show_diff_table

        changes = {
            "download": {"cake-nat": ("no", "yes")},
        }
        queue_names = {"download": "cake-down-spectrum", "upload": "cake-up-spectrum"}
        show_diff_table(changes, queue_names)

        captured = capsys.readouterr()
        # Should display "nat" not "cake-nat"
        assert "nat" in captured.err
        # Should NOT have "cake-nat" as a display name (just "nat")
        lines = captured.err.split("\n")
        param_lines = [l for l in lines if "nat" in l and "cake-down" not in l]
        assert any("nat" in l for l in param_lines)

    def test_groups_by_direction(self, capsys):
        """Prints separate section per direction with queue name."""
        from wanctl.check_cake_fix import show_diff_table

        changes = {
            "download": {"cake-nat": ("no", "yes")},
            "upload": {"cake-wash": ("no", "yes")},
        }
        queue_names = {"download": "cake-down-spectrum", "upload": "cake-up-spectrum"}
        total = show_diff_table(changes, queue_names)

        captured = capsys.readouterr()
        assert "cake-down-spectrum" in captured.err
        assert "cake-up-spectrum" in captured.err
        assert "download" in captured.err
        assert "upload" in captured.err
        assert total == 2

    def test_returns_total_change_count(self):
        """Returns total number of changes across all directions."""
        from wanctl.check_cake_fix import show_diff_table

        changes = {
            "download": {"cake-nat": ("no", "yes"), "cake-flowmode": ("x", "y")},
            "upload": {"cake-wash": ("no", "yes")},
        }
        queue_names = {"download": "cake-down-spectrum", "upload": "cake-up-spectrum"}
        total = show_diff_table(changes, queue_names)
        assert total == 3

    def test_prints_to_stderr(self, capsys):
        """Table output goes to stderr, not stdout."""
        from wanctl.check_cake_fix import show_diff_table

        changes = {"download": {"cake-nat": ("no", "yes")}}
        queue_names = {"download": "cake-down-spectrum", "upload": "cake-up-spectrum"}
        show_diff_table(changes, queue_names)

        captured = capsys.readouterr()
        assert captured.out == ""  # Nothing on stdout
        assert len(captured.err) > 0  # Something on stderr


# =============================================================================
# TestConfirmApply -- confirm_apply()
# =============================================================================


class TestConfirmApply:
    """Test confirm_apply() for user confirmation prompt."""

    def test_returns_true_on_y(self):
        """Returns True on 'y' input."""
        from wanctl.check_cake_fix import confirm_apply

        with patch("builtins.input", return_value="y"):
            assert confirm_apply(3) is True

    def test_returns_true_on_Y(self):
        """Returns True on 'Y' input."""
        from wanctl.check_cake_fix import confirm_apply

        with patch("builtins.input", return_value="Y"):
            assert confirm_apply(3) is True

    def test_returns_true_on_yes(self):
        """Returns True on 'yes' input."""
        from wanctl.check_cake_fix import confirm_apply

        with patch("builtins.input", return_value="yes"):
            assert confirm_apply(3) is True

    def test_returns_true_on_YES(self):
        """Returns True on 'YES' input."""
        from wanctl.check_cake_fix import confirm_apply

        with patch("builtins.input", return_value="YES"):
            assert confirm_apply(3) is True

    def test_returns_false_on_n(self):
        """Returns False on 'n' input."""
        from wanctl.check_cake_fix import confirm_apply

        with patch("builtins.input", return_value="n"):
            assert confirm_apply(3) is False

    def test_returns_false_on_empty(self):
        """Returns False on empty input (safe default)."""
        from wanctl.check_cake_fix import confirm_apply

        with patch("builtins.input", return_value=""):
            assert confirm_apply(3) is False

    def test_returns_false_on_anything_else(self):
        """Returns False on arbitrary input."""
        from wanctl.check_cake_fix import confirm_apply

        with patch("builtins.input", return_value="maybe"):
            assert confirm_apply(3) is False


# =============================================================================
# TestApplyChanges -- _apply_changes()
# =============================================================================


class TestApplyChanges:
    """Test _apply_changes() for applying PATCH to router."""

    def test_success_returns_pass_per_param(self):
        """On success, returns PASS CheckResult per changed param."""
        from wanctl.check_cake_fix import _apply_changes

        client = MagicMock()
        client.set_queue_type_params.return_value = True

        changes = {
            "download": {
                "cake-nat": ("no", "yes"),
                "cake-flowmode": ("dual-srchost", "triple-isolate"),
            },
        }
        queue_names = {"download": "cake-down-spectrum", "upload": "cake-up-spectrum"}
        results = _apply_changes(client, changes, queue_names)

        assert len(results) == 2
        assert all(r.severity == Severity.PASS for r in results)
        assert all("Fix Applied (download)" in r.category for r in results)

    def test_single_patch_per_queue_type(self):
        """Sends single PATCH per queue type, not per param."""
        from wanctl.check_cake_fix import _apply_changes

        client = MagicMock()
        client.set_queue_type_params.return_value = True

        changes = {
            "download": {
                "cake-nat": ("no", "yes"),
                "cake-flowmode": ("dual-srchost", "triple-isolate"),
            },
        }
        queue_names = {"download": "cake-down-spectrum", "upload": "cake-up-spectrum"}
        _apply_changes(client, changes, queue_names)

        # Should be called once for download direction (all params in one call)
        assert client.set_queue_type_params.call_count == 1
        call_args = client.set_queue_type_params.call_args
        assert call_args[0][0] == "cake-down-spectrum"
        assert call_args[0][1] == {"cake-nat": "yes", "cake-flowmode": "triple-isolate"}

    def test_failure_returns_error_per_param(self):
        """On failure, returns ERROR CheckResult per param in that direction."""
        from wanctl.check_cake_fix import _apply_changes

        client = MagicMock()
        client.set_queue_type_params.return_value = False

        changes = {
            "download": {
                "cake-nat": ("no", "yes"),
                "cake-flowmode": ("dual-srchost", "triple-isolate"),
            },
        }
        queue_names = {"download": "cake-down-spectrum", "upload": "cake-up-spectrum"}
        results = _apply_changes(client, changes, queue_names)

        assert len(results) == 2
        assert all(r.severity == Severity.ERROR for r in results)
        assert all("Fix Applied (download)" in r.category for r in results)

    def test_category_includes_direction(self):
        """Category is 'Fix Applied ({direction})'."""
        from wanctl.check_cake_fix import _apply_changes

        client = MagicMock()
        client.set_queue_type_params.return_value = True

        changes = {
            "upload": {"cake-wash": ("no", "yes")},
        }
        queue_names = {"download": "cake-down-spectrum", "upload": "cake-up-spectrum"}
        results = _apply_changes(client, changes, queue_names)

        assert len(results) == 1
        assert results[0].category == "Fix Applied (upload)"

    def test_handles_both_directions(self):
        """Applies changes to both download and upload when both have changes."""
        from wanctl.check_cake_fix import _apply_changes

        client = MagicMock()
        client.set_queue_type_params.return_value = True

        changes = {
            "download": {"cake-nat": ("no", "yes")},
            "upload": {"cake-wash": ("no", "yes")},
        }
        queue_names = {"download": "cake-down-spectrum", "upload": "cake-up-spectrum"}
        results = _apply_changes(client, changes, queue_names)

        assert client.set_queue_type_params.call_count == 2
        assert len(results) == 2
        categories = {r.category for r in results}
        assert "Fix Applied (download)" in categories
        assert "Fix Applied (upload)" in categories


# =============================================================================
# TestFixFlow -- run_fix() orchestration
# =============================================================================


class TestFixFlow:
    """Test run_fix() orchestrator for the complete fix flow."""

    def _make_client(self, queue_type_data_dl=None, queue_type_data_ul=None, patch_ok=True):
        """Create a mock client with queue type data responses."""
        client = MagicMock()
        # Default: sub-optimal download, optimal upload
        if queue_type_data_dl is None:
            queue_type_data_dl = _optimal_queue_type_data("download")
            queue_type_data_dl["cake-nat"] = "no"  # Sub-optimal
        if queue_type_data_ul is None:
            queue_type_data_ul = _optimal_queue_type_data("upload")

        def get_queue_stats_side_effect(name):
            if "Download" in name or "down" in name.lower():
                return {
                    "queue": "cake-down-spectrum",
                    "max-limit": "940000000",
                    "name": name,
                    ".id": "*1",
                }
            if "Upload" in name or "up" in name.lower():
                return {
                    "queue": "cake-up-spectrum",
                    "max-limit": "38000000",
                    "name": name,
                    ".id": "*2",
                }
            return None

        def get_queue_types_side_effect(name):
            if "down" in name.lower():
                return queue_type_data_dl
            if "up" in name.lower():
                return queue_type_data_ul
            return None

        client.get_queue_stats.side_effect = get_queue_stats_side_effect
        client.get_queue_types.side_effect = get_queue_types_side_effect
        client.set_queue_type_params.return_value = patch_ok
        client.test_connection.return_value = True
        return client

    def test_blocks_when_daemon_running(self):
        """Returns ERROR when daemon lock check fails."""
        from wanctl.check_cake_fix import run_fix

        client = self._make_client()
        data = _autorate_config_data()

        lock_result = CheckResult(
            "Daemon Lock",
            "lock_check",
            Severity.ERROR,
            "wanctl daemon is running (PID 1234)",
            suggestion="Stop daemon first",
        )

        with patch("wanctl.check_cake.check_daemon_lock", return_value=[lock_result]):
            results = run_fix(data, "autorate", client)

        assert any(r.severity == Severity.ERROR and "daemon" in r.message.lower() for r in results)
        # Should NOT call set_queue_type_params
        client.set_queue_type_params.assert_not_called()

    def test_nothing_to_fix_returns_pass(self):
        """Returns PASS result when all params are optimal."""
        from wanctl.check_cake_fix import run_fix

        # All optimal for both directions
        dl = _optimal_queue_type_data("download")
        ul = _optimal_queue_type_data("upload")
        client = self._make_client(queue_type_data_dl=dl, queue_type_data_ul=ul)
        data = _autorate_config_data()

        lock_pass = CheckResult("Daemon Lock", "lock_check", Severity.PASS, "No daemon running")
        with patch("wanctl.check_cake.check_daemon_lock", return_value=[lock_pass]):
            results = run_fix(data, "autorate", client, yes=True)

        # Should contain a "nothing to fix" message
        nothing_results = [
            r
            for r in results
            if "nothing to fix" in r.message.lower() or "optimal" in r.message.lower()
        ]
        assert len(nothing_results) >= 1
        assert nothing_results[0].severity == Severity.PASS
        client.set_queue_type_params.assert_not_called()

    def test_calls_save_snapshot_before_apply(self, tmp_path):
        """Calls save_snapshot() before applying changes."""
        from wanctl.check_cake_fix import run_fix

        dl = _optimal_queue_type_data("download")
        dl["cake-nat"] = "no"  # Sub-optimal
        ul = _optimal_queue_type_data("upload")
        client = self._make_client(queue_type_data_dl=dl, queue_type_data_ul=ul)
        data = _autorate_config_data()

        lock_pass = CheckResult("Daemon Lock", "lock_check", Severity.PASS, "No daemon running")
        call_order = []

        def mock_save(*args, **kwargs):
            call_order.append("snapshot")
            return tmp_path / "test_snapshot.json"

        def mock_set_params(*args, **kwargs):
            call_order.append("apply")
            return True

        client.set_queue_type_params.side_effect = mock_set_params

        with (
            patch("wanctl.check_cake.check_daemon_lock", return_value=[lock_pass]),
            patch("wanctl.check_cake_fix.save_snapshot", side_effect=mock_save) as mock_snap,
            patch("wanctl.check_cake.run_audit", return_value=[]),
        ):
            run_fix(data, "autorate", client, yes=True)

        mock_snap.assert_called_once()
        assert call_order.index("snapshot") < call_order.index("apply")

    def test_calls_set_queue_type_params_with_correct_params(self):
        """Calls set_queue_type_params with correct params per queue type."""
        from wanctl.check_cake_fix import run_fix

        dl = _optimal_queue_type_data("download")
        dl["cake-nat"] = "no"  # Sub-optimal
        ul = _optimal_queue_type_data("upload")
        client = self._make_client(queue_type_data_dl=dl, queue_type_data_ul=ul)
        data = _autorate_config_data()

        lock_pass = CheckResult("Daemon Lock", "lock_check", Severity.PASS, "No daemon running")

        with (
            patch("wanctl.check_cake.check_daemon_lock", return_value=[lock_pass]),
            patch("wanctl.check_cake_fix.save_snapshot", return_value=Path("/tmp/snap.json")),
            patch("wanctl.check_cake.run_audit", return_value=[]),
        ):
            run_fix(data, "autorate", client, yes=True)

        client.set_queue_type_params.assert_called_once_with(
            "cake-down-spectrum", {"cake-nat": "yes"}
        )

    def test_single_patch_per_queue_type(self):
        """Sends single PATCH per queue type (all changed params in one call)."""
        from wanctl.check_cake_fix import run_fix

        dl = _optimal_queue_type_data("download")
        dl["cake-nat"] = "no"
        dl["cake-flowmode"] = "dual-srchost"
        ul = _optimal_queue_type_data("upload")
        client = self._make_client(queue_type_data_dl=dl, queue_type_data_ul=ul)
        data = _autorate_config_data()

        lock_pass = CheckResult("Daemon Lock", "lock_check", Severity.PASS, "No daemon running")

        with (
            patch("wanctl.check_cake.check_daemon_lock", return_value=[lock_pass]),
            patch("wanctl.check_cake_fix.save_snapshot", return_value=Path("/tmp/snap.json")),
            patch("wanctl.check_cake.run_audit", return_value=[]),
        ):
            run_fix(data, "autorate", client, yes=True)

        # Single PATCH call with both params
        assert client.set_queue_type_params.call_count == 1
        call_args = client.set_queue_type_params.call_args
        assert call_args[0][1] == {"cake-nat": "yes", "cake-flowmode": "triple-isolate"}

    def test_reruns_audit_after_apply(self):
        """Re-runs run_audit after applying and includes verification results."""
        from wanctl.check_cake_fix import run_fix

        dl = _optimal_queue_type_data("download")
        dl["cake-nat"] = "no"
        ul = _optimal_queue_type_data("upload")
        client = self._make_client(queue_type_data_dl=dl, queue_type_data_ul=ul)
        data = _autorate_config_data()

        lock_pass = CheckResult("Daemon Lock", "lock_check", Severity.PASS, "No daemon running")
        verify_result = CheckResult(
            "CAKE Params (download)", "nat", Severity.PASS, "nat: yes (optimal)"
        )

        with (
            patch("wanctl.check_cake.check_daemon_lock", return_value=[lock_pass]),
            patch("wanctl.check_cake_fix.save_snapshot", return_value=Path("/tmp/snap.json")),
            patch("wanctl.check_cake.run_audit", return_value=[verify_result]) as mock_audit,
        ):
            results = run_fix(data, "autorate", client, yes=True)

        mock_audit.assert_called_once()
        # Verification result should be in output
        assert any(r.message == "nat: yes (optimal)" for r in results)

    def test_skips_confirmation_when_yes_true(self):
        """Does not prompt when yes=True."""
        from wanctl.check_cake_fix import run_fix

        dl = _optimal_queue_type_data("download")
        dl["cake-nat"] = "no"
        ul = _optimal_queue_type_data("upload")
        client = self._make_client(queue_type_data_dl=dl, queue_type_data_ul=ul)
        data = _autorate_config_data()

        lock_pass = CheckResult("Daemon Lock", "lock_check", Severity.PASS, "No daemon running")

        with (
            patch("wanctl.check_cake.check_daemon_lock", return_value=[lock_pass]),
            patch("wanctl.check_cake_fix.save_snapshot", return_value=Path("/tmp/snap.json")),
            patch("wanctl.check_cake.run_audit", return_value=[]),
            patch("wanctl.check_cake_fix.confirm_apply") as mock_confirm,
        ):
            run_fix(data, "autorate", client, yes=True)

        mock_confirm.assert_not_called()

    def test_cancelled_returns_pass_result(self):
        """Returns user-cancelled result when confirmation declined."""
        from wanctl.check_cake_fix import run_fix

        dl = _optimal_queue_type_data("download")
        dl["cake-nat"] = "no"
        ul = _optimal_queue_type_data("upload")
        client = self._make_client(queue_type_data_dl=dl, queue_type_data_ul=ul)
        data = _autorate_config_data()

        lock_pass = CheckResult("Daemon Lock", "lock_check", Severity.PASS, "No daemon running")

        with (
            patch("wanctl.check_cake.check_daemon_lock", return_value=[lock_pass]),
            patch("wanctl.check_cake_fix.confirm_apply", return_value=False),
            patch("wanctl.check_cake_fix.show_diff_table", return_value=1),
        ):
            results = run_fix(data, "autorate", client, yes=False)

        cancelled = [r for r in results if "cancel" in r.message.lower()]
        assert len(cancelled) >= 1
        assert cancelled[0].severity == Severity.PASS
        client.set_queue_type_params.assert_not_called()

    def test_json_mode_requires_yes(self):
        """Returns ERROR when json_mode=True and yes=False."""
        from wanctl.check_cake_fix import run_fix

        dl = _optimal_queue_type_data("download")
        dl["cake-nat"] = "no"
        ul = _optimal_queue_type_data("upload")
        client = self._make_client(queue_type_data_dl=dl, queue_type_data_ul=ul)
        data = _autorate_config_data()

        lock_pass = CheckResult("Daemon Lock", "lock_check", Severity.PASS, "No daemon running")

        with patch("wanctl.check_cake.check_daemon_lock", return_value=[lock_pass]):
            results = run_fix(data, "autorate", client, yes=False, json_mode=True)

        error_results = [
            r for r in results if r.severity == Severity.ERROR and "--yes" in r.message
        ]
        assert len(error_results) >= 1
        client.set_queue_type_params.assert_not_called()


# =============================================================================
# TestFixCLI -- main() with --fix flag
# =============================================================================


class TestFixCLI:
    """Test main() with --fix flag integration."""

    def test_fix_calls_run_fix_instead_of_run_audit(self, tmp_path):
        """main() with --fix calls run_fix instead of run_audit."""
        from wanctl.check_cake import main

        data = _autorate_config_data()
        config_file = _write_config(tmp_path, data)

        mock_client = MagicMock()
        fix_result = CheckResult("Fix", "status", Severity.PASS, "Nothing to fix")

        with (
            patch.dict(os.environ, {"ROUTER_PASSWORD": "secret"}),
            patch("wanctl.check_cake._create_audit_client", return_value=mock_client),
            patch("wanctl.check_cake.run_fix", return_value=[fix_result]) as mock_run_fix,
            patch("wanctl.check_cake.run_audit") as mock_run_audit,
            patch("sys.argv", ["wanctl-check-cake", config_file, "--fix", "--yes", "--no-color"]),
        ):
            result = main()

        mock_run_fix.assert_called_once()
        mock_run_audit.assert_not_called()
        assert result == 0

    def test_fix_passes_yes_and_json_flags(self, tmp_path):
        """main() passes --yes and --json flags through to run_fix."""
        from wanctl.check_cake import main

        data = _autorate_config_data()
        config_file = _write_config(tmp_path, data)

        mock_client = MagicMock()
        fix_result = CheckResult("Fix", "status", Severity.PASS, "Nothing to fix")

        with (
            patch.dict(os.environ, {"ROUTER_PASSWORD": "secret"}),
            patch("wanctl.check_cake._create_audit_client", return_value=mock_client),
            patch("wanctl.check_cake.run_fix", return_value=[fix_result]) as mock_run_fix,
            patch("sys.argv", ["wanctl-check-cake", config_file, "--fix", "--yes", "--json"]),
        ):
            main()

        call_kwargs = mock_run_fix.call_args
        assert call_kwargs[1]["yes"] is True or call_kwargs[0][3] is True
        assert call_kwargs[1]["json_mode"] is True or call_kwargs[0][4] is True

    def test_fix_nothing_to_fix_returns_0(self, tmp_path):
        """--fix with nothing to fix returns exit code 0."""
        from wanctl.check_cake import main

        data = _autorate_config_data()
        config_file = _write_config(tmp_path, data)

        mock_client = MagicMock()
        fix_result = CheckResult("Fix", "status", Severity.PASS, "All optimal")

        with (
            patch.dict(os.environ, {"ROUTER_PASSWORD": "secret"}),
            patch("wanctl.check_cake._create_audit_client", return_value=mock_client),
            patch("wanctl.check_cake.run_fix", return_value=[fix_result]),
            patch("sys.argv", ["wanctl-check-cake", config_file, "--fix", "--yes"]),
        ):
            result = main()
        assert result == 0

    def test_fix_with_apply_error_returns_1(self, tmp_path):
        """--fix with apply error returns exit code 1."""
        from wanctl.check_cake import main

        data = _autorate_config_data()
        config_file = _write_config(tmp_path, data)

        mock_client = MagicMock()
        error_result = CheckResult(
            "Fix Applied (download)", "nat", Severity.ERROR, "Failed to apply"
        )

        with (
            patch.dict(os.environ, {"ROUTER_PASSWORD": "secret"}),
            patch("wanctl.check_cake._create_audit_client", return_value=mock_client),
            patch("wanctl.check_cake.run_fix", return_value=[error_result]),
            patch("sys.argv", ["wanctl-check-cake", config_file, "--fix", "--yes"]),
        ):
            result = main()
        assert result == 1

    def test_fix_extracts_wan_name_from_data(self, tmp_path):
        """main() passes wan_name from config data to run_fix."""
        from wanctl.check_cake import main

        data = _autorate_config_data()
        config_file = _write_config(tmp_path, data)

        mock_client = MagicMock()
        fix_result = CheckResult("Fix", "status", Severity.PASS, "Nothing to fix")

        with (
            patch.dict(os.environ, {"ROUTER_PASSWORD": "secret"}),
            patch("wanctl.check_cake._create_audit_client", return_value=mock_client),
            patch("wanctl.check_cake.run_fix", return_value=[fix_result]) as mock_run_fix,
            patch("sys.argv", ["wanctl-check-cake", config_file, "--fix", "--yes"]),
        ):
            main()

        call_kwargs = mock_run_fix.call_args
        assert call_kwargs[1]["wan_name"] == "spectrum" or call_kwargs[0][5] == "spectrum"

    def test_without_fix_uses_run_audit(self, tmp_path):
        """main() without --fix uses run_audit (existing behavior unchanged)."""
        from wanctl.check_cake import main

        data = _autorate_config_data()
        config_file = _write_config(tmp_path, data)

        mock_client = MagicMock()
        audit_result = CheckResult("Queue Tree", "download", Severity.PASS, "Queue exists")

        with (
            patch.dict(os.environ, {"ROUTER_PASSWORD": "secret"}),
            patch("wanctl.check_cake._create_audit_client", return_value=mock_client),
            patch("wanctl.check_cake.run_audit", return_value=[audit_result]) as mock_audit,
            patch("wanctl.check_cake.run_fix") as mock_fix,
            patch("sys.argv", ["wanctl-check-cake", config_file, "--no-color"]),
        ):
            main()

        mock_audit.assert_called_once()
        mock_fix.assert_not_called()


# =============================================================================
# TestFixJson -- --fix --json integration
# =============================================================================


class TestFixJson:
    """Test --fix with --json output mode."""

    def test_fix_json_yes_produces_valid_json(self, tmp_path, capsys):
        """--fix --json --yes produces valid JSON output."""
        from wanctl.check_cake import main

        data = _autorate_config_data()
        config_file = _write_config(tmp_path, data)

        mock_client = MagicMock()
        fix_result = CheckResult("Fix", "status", Severity.PASS, "All optimal -- nothing to fix")

        with (
            patch.dict(os.environ, {"ROUTER_PASSWORD": "secret"}),
            patch("wanctl.check_cake._create_audit_client", return_value=mock_client),
            patch("wanctl.check_cake.run_fix", return_value=[fix_result]),
            patch("sys.argv", ["wanctl-check-cake", config_file, "--fix", "--yes", "--json"]),
        ):
            main()

        captured = capsys.readouterr()
        parsed = json.loads(captured.out)
        assert "config_type" in parsed
        assert "result" in parsed

    def test_fix_json_without_yes_returns_error(self, tmp_path):
        """--fix --json without --yes returns error (exit code 1)."""
        from wanctl.check_cake import main

        data = _autorate_config_data()
        config_file = _write_config(tmp_path, data)

        mock_client = MagicMock()
        error_result = CheckResult(
            "Fix", "mode", Severity.ERROR, "Fix in --json mode requires --yes flag"
        )

        with (
            patch.dict(os.environ, {"ROUTER_PASSWORD": "secret"}),
            patch("wanctl.check_cake._create_audit_client", return_value=mock_client),
            patch("wanctl.check_cake.run_fix", return_value=[error_result]),
            patch("sys.argv", ["wanctl-check-cake", config_file, "--fix", "--json"]),
        ):
            result = main()
        assert result == 1


# =============================================================================
# TIN DISTRIBUTION CHECK TESTS
# =============================================================================


def _tc_json_output(tins: list[dict]) -> str:
    """Create mock tc -s -j qdisc output with CAKE entry."""
    return json.dumps([{"kind": "cake", "tins": tins}])


class TestTinDistribution:
    """Tests for check_tin_distribution() function."""

    def test_happy_path_all_tins_have_traffic(self):
        """4 tins with packets in all tins returns 4 PASS results."""
        from wanctl.check_cake import check_tin_distribution

        tins = [
            {"sent_packets": 10000},  # Bulk
            {"sent_packets": 500000},  # BestEffort
            {"sent_packets": 80000},  # Video
            {"sent_packets": 60000},  # Voice
        ]
        tc_output = _tc_json_output(tins)
        mock_proc = MagicMock(returncode=0, stdout=tc_output, stderr="")

        with patch("wanctl.check_cake.subprocess.run", return_value=mock_proc):
            results = check_tin_distribution("ens17", "download")

        assert len(results) == 4
        assert all(r.severity == Severity.PASS for r in results)
        assert all(r.category == "Tin Distribution (download)" for r in results)

    def test_zero_packet_voice_tin_returns_warn(self):
        """Zero-packet Voice tin returns WARN with suggestion about DSCP marks."""
        from wanctl.check_cake import check_tin_distribution

        tins = [
            {"sent_packets": 10000},  # Bulk
            {"sent_packets": 500000},  # BestEffort
            {"sent_packets": 80000},  # Video
            {"sent_packets": 0},  # Voice
        ]
        tc_output = _tc_json_output(tins)
        mock_proc = MagicMock(returncode=0, stdout=tc_output, stderr="")

        with patch("wanctl.check_cake.subprocess.run", return_value=mock_proc):
            results = check_tin_distribution("ens16", "upload")

        voice_results = [r for r in results if "Voice" in r.message]
        assert len(voice_results) == 1
        assert voice_results[0].severity == Severity.WARN
        assert "DSCP" in voice_results[0].suggestion

    def test_zero_packet_bulk_tin_returns_warn(self):
        """Zero-packet Bulk tin returns WARN (non-BestEffort tin with 0 packets)."""
        from wanctl.check_cake import check_tin_distribution

        tins = [
            {"sent_packets": 0},  # Bulk
            {"sent_packets": 500000},  # BestEffort
            {"sent_packets": 80000},  # Video
            {"sent_packets": 60000},  # Voice
        ]
        tc_output = _tc_json_output(tins)
        mock_proc = MagicMock(returncode=0, stdout=tc_output, stderr="")

        with patch("wanctl.check_cake.subprocess.run", return_value=mock_proc):
            results = check_tin_distribution("ens16", "upload")

        bulk_results = [r for r in results if "Bulk" in r.message]
        assert len(bulk_results) == 1
        assert bulk_results[0].severity == Severity.WARN
        assert "DSCP" in bulk_results[0].suggestion

    def test_all_tins_zero_packets_returns_single_warn(self):
        """All tins zero packets returns single WARN 'No packets processed'."""
        from wanctl.check_cake import check_tin_distribution

        tins = [
            {"sent_packets": 0},
            {"sent_packets": 0},
            {"sent_packets": 0},
            {"sent_packets": 0},
        ]
        tc_output = _tc_json_output(tins)
        mock_proc = MagicMock(returncode=0, stdout=tc_output, stderr="")

        with patch("wanctl.check_cake.subprocess.run", return_value=mock_proc):
            results = check_tin_distribution("ens17", "download")

        assert len(results) == 1
        assert results[0].severity == Severity.WARN
        assert "No packets processed" in results[0].message

    def test_no_cake_qdisc_found_returns_error(self):
        """No CAKE qdisc found returns ERROR."""
        from wanctl.check_cake import check_tin_distribution

        tc_output = json.dumps([{"kind": "htb", "tins": []}])
        mock_proc = MagicMock(returncode=0, stdout=tc_output, stderr="")

        with patch("wanctl.check_cake.subprocess.run", return_value=mock_proc):
            results = check_tin_distribution("ens17", "download")

        assert len(results) == 1
        assert results[0].severity == Severity.ERROR
        assert "No CAKE qdisc" in results[0].message

    def test_tc_command_fails_returns_error(self):
        """tc command fails (non-zero returncode) returns ERROR."""
        from wanctl.check_cake import check_tin_distribution

        mock_proc = MagicMock(returncode=1, stdout="", stderr="Error: device not found")

        with patch("wanctl.check_cake.subprocess.run", return_value=mock_proc):
            results = check_tin_distribution("ens17", "download")

        assert len(results) == 1
        assert results[0].severity == Severity.ERROR
        assert "tc failed" in results[0].message

    def test_tc_command_timeout_returns_error(self):
        """tc command timeout returns ERROR."""
        import subprocess

        from wanctl.check_cake import check_tin_distribution

        with patch(
            "wanctl.check_cake.subprocess.run",
            side_effect=subprocess.TimeoutExpired(cmd="tc", timeout=5),
        ):
            results = check_tin_distribution("ens17", "download")

        assert len(results) == 1
        assert results[0].severity == Severity.ERROR
        assert "Failed to run tc" in results[0].message

    def test_wrong_tin_count_returns_error(self):
        """Wrong tin count (not 4) returns ERROR."""
        from wanctl.check_cake import check_tin_distribution

        tins = [
            {"sent_packets": 10000},
            {"sent_packets": 500000},
            {"sent_packets": 80000},
        ]
        tc_output = _tc_json_output(tins)
        mock_proc = MagicMock(returncode=0, stdout=tc_output, stderr="")

        with patch("wanctl.check_cake.subprocess.run", return_value=mock_proc):
            results = check_tin_distribution("ens17", "download")

        assert len(results) == 1
        assert results[0].severity == Severity.ERROR
        assert "Expected 4 tins" in results[0].message

    def test_below_threshold_tin_returns_warn(self):
        """Below-threshold tin (e.g., 0.05% when threshold is 0.1%) returns WARN."""
        from wanctl.check_cake import check_tin_distribution

        tins = [
            {"sent_packets": 50},  # Bulk: 0.005% -- below 0.1%
            {"sent_packets": 999850},  # BestEffort
            {"sent_packets": 80000},  # Video
            {"sent_packets": 60000},  # Voice
        ]
        tc_output = _tc_json_output(tins)
        mock_proc = MagicMock(returncode=0, stdout=tc_output, stderr="")

        with patch("wanctl.check_cake.subprocess.run", return_value=mock_proc):
            results = check_tin_distribution("ens16", "upload")

        bulk_results = [r for r in results if "Bulk" in r.message]
        assert len(bulk_results) == 1
        assert bulk_results[0].severity == Severity.WARN
        assert "threshold" in bulk_results[0].message

    def test_besteffort_always_pass_regardless_of_percentage(self):
        """BestEffort always PASS regardless of percentage."""
        from wanctl.check_cake import check_tin_distribution

        tins = [
            {"sent_packets": 900000},  # Bulk
            {"sent_packets": 10},  # BestEffort: tiny
            {"sent_packets": 80000},  # Video
            {"sent_packets": 60000},  # Voice
        ]
        tc_output = _tc_json_output(tins)
        mock_proc = MagicMock(returncode=0, stdout=tc_output, stderr="")

        with patch("wanctl.check_cake.subprocess.run", return_value=mock_proc):
            results = check_tin_distribution("ens16", "upload")

        be_results = [r for r in results if "BestEffort" in r.message]
        assert len(be_results) == 1
        assert be_results[0].severity == Severity.PASS

    def test_tc_file_not_found_returns_error(self):
        """FileNotFoundError when tc binary not found returns ERROR."""
        from wanctl.check_cake import check_tin_distribution

        with patch(
            "wanctl.check_cake.subprocess.run",
            side_effect=FileNotFoundError("tc not found"),
        ):
            results = check_tin_distribution("ens17", "download")

        assert len(results) == 1
        assert results[0].severity == Severity.ERROR
        assert "Failed to run tc" in results[0].message

    def test_invalid_json_returns_error(self):
        """Invalid JSON from tc returns ERROR."""
        from wanctl.check_cake import check_tin_distribution

        mock_proc = MagicMock(returncode=0, stdout="not json at all", stderr="")

        with patch("wanctl.check_cake.subprocess.run", return_value=mock_proc):
            results = check_tin_distribution("ens17", "download")

        assert len(results) == 1
        assert results[0].severity == Severity.ERROR
        assert "parse" in results[0].message.lower()


class TestTinDistributionRunAuditIntegration:
    """Tests for check_tin_distribution integration into run_audit()."""

    def test_run_audit_calls_tin_check_when_cake_params_present(self):
        """run_audit calls check_tin_distribution when cake_params present in data."""
        from wanctl.check_cake import run_audit

        data = _autorate_config_data()
        data["cake_params"] = {
            "download_interface": "ens17",
            "upload_interface": "ens16",
        }

        mock_client = MagicMock()
        mock_client.test_connection.return_value = True
        mock_client.get_queue_stats.return_value = None

        tins = [
            {"sent_packets": 10000},
            {"sent_packets": 500000},
            {"sent_packets": 80000},
            {"sent_packets": 60000},
        ]
        tc_output = _tc_json_output(tins)
        mock_proc = MagicMock(returncode=0, stdout=tc_output, stderr="")

        with (
            patch.dict(os.environ, {"ROUTER_PASSWORD": "secret"}),
            patch("wanctl.check_cake.subprocess.run", return_value=mock_proc),
        ):
            results = run_audit(data, "autorate", mock_client)

        tin_results = [r for r in results if "Tin Distribution" in r.category]
        assert len(tin_results) > 0
        # Should have results for both download and upload
        dl_results = [r for r in tin_results if "download" in r.category]
        ul_results = [r for r in tin_results if "upload" in r.category]
        assert len(dl_results) > 0
        assert len(ul_results) > 0

    def test_run_audit_skips_tin_check_when_cake_params_absent(self):
        """run_audit skips check_tin_distribution when cake_params absent."""
        from wanctl.check_cake import run_audit

        data = _autorate_config_data()
        # No cake_params key

        mock_client = MagicMock()
        mock_client.test_connection.return_value = True
        mock_client.get_queue_stats.return_value = None

        with patch.dict(os.environ, {"ROUTER_PASSWORD": "secret"}):
            results = run_audit(data, "autorate", mock_client)

        tin_results = [r for r in results if "Tin Distribution" in r.category]
        assert len(tin_results) == 0

    def test_run_audit_skips_tin_check_when_connectivity_fails(self):
        """run_audit skips check_tin_distribution when router connectivity fails.

        Note: tin check runs locally via tc, but run_audit returns early
        when connectivity fails so the tin check section is never reached.
        """
        from wanctl.check_cake import run_audit

        data = _autorate_config_data()
        data["cake_params"] = {
            "download_interface": "ens17",
            "upload_interface": "ens16",
        }

        mock_client = MagicMock()
        mock_client.test_connection.return_value = False

        with patch.dict(os.environ, {"ROUTER_PASSWORD": "secret"}):
            results = run_audit(data, "autorate", mock_client)

        tin_results = [r for r in results if "Tin Distribution" in r.category]
        assert len(tin_results) == 0
