"""Comprehensive tests for wanctl-check-config CLI tool.

Covers all phase requirements:
  CVAL-01: CLI validates config offline
  CVAL-02: Steering config validation
  CVAL-03: Auto-detection of config type
  CVAL-04: All errors collected (not just first)
  CVAL-05: Cross-field semantic validation
  CVAL-06: File/permission checks
  CVAL-07: Env var resolution warnings
  CVAL-08: Deprecated parameter surfacing
  CVAL-09: Cross-config validation
  CVAL-11: Exit codes 0/1/2
"""

import json
import sys
from unittest.mock import patch

import pytest
import yaml

from wanctl.check_config import (
    CheckResult,
    Severity,
    check_deprecated_params,
    check_env_vars,
    check_paths,
    check_steering_cross_config,
    check_steering_deprecated_params,
    check_steering_unknown_keys,
    check_unknown_keys,
    create_parser,
    detect_config_type,
    format_results,
    format_results_json,
    main,
    validate_cross_fields,
    validate_linux_cake,
    validate_schema_fields,
    validate_steering_cross_fields,
    validate_steering_schema_fields,
)

# =============================================================================
# FIXTURES
# =============================================================================


def _valid_config_data() -> dict:
    """Return a minimal valid autorate config dict.

    All required BASE_SCHEMA + Config.SCHEMA fields present with valid values.
    """
    return {
        "wan_name": "test",
        "router": {
            "host": "10.0.0.1",
            "user": "admin",
            "ssh_key": "/tmp/fake_key",
            "transport": "rest",
            "password": "secret",
        },
        "queues": {
            "download": "WAN-Download",
            "upload": "WAN-Upload",
        },
        "continuous_monitoring": {
            "enabled": True,
            "baseline_rtt_initial": 25,
            "download": {
                "ceiling_mbps": 100,
                "floor_mbps": 10,
                "step_up_mbps": 5,
                "factor_down": 0.85,
            },
            "upload": {
                "ceiling_mbps": 20,
                "floor_mbps": 5,
                "step_up_mbps": 1,
                "factor_down": 0.90,
            },
            "thresholds": {
                "target_bloat_ms": 5,
                "warn_bloat_ms": 15,
                "hard_red_bloat_ms": 80,
                "baseline_time_constant_sec": 50,
                "load_time_constant_sec": 0.25,
            },
            "ping_hosts": ["1.1.1.1"],
        },
        "logging": {
            "main_log": "/tmp/test.log",
            "debug_log": "/tmp/test_debug.log",
        },
        "lock_file": "/tmp/test.lock",
        "lock_timeout": 300,
    }


def _write_config(tmp_path, config_data: dict) -> str:
    """Write a config dict to a temp YAML file and return the path."""
    config_path = tmp_path / "test_config.yaml"
    config_path.write_text(yaml.dump(config_data))
    return str(config_path)


# =============================================================================
# TestCLI (CVAL-01)
# =============================================================================


class TestCLI:
    """Test CLI argument parsing and main() entry point."""

    def test_create_parser_has_config_file_arg(self):
        parser = create_parser()
        args = parser.parse_args(["test.yaml"])
        assert args.config_file == "test.yaml"

    def test_create_parser_has_no_color_flag(self):
        parser = create_parser()
        args = parser.parse_args(["test.yaml", "--no-color"])
        assert args.no_color is True

    def test_create_parser_has_quiet_flag(self):
        parser = create_parser()
        args = parser.parse_args(["test.yaml", "-q"])
        assert args.quiet is True

    def test_create_parser_quiet_long_form(self):
        parser = create_parser()
        args = parser.parse_args(["test.yaml", "--quiet"])
        assert args.quiet is True

    def test_main_valid_config_returns_0(self, tmp_path, monkeypatch):
        """Valid config with all paths existing should return 0."""
        config = _valid_config_data()
        # Use tmp_path for log/state paths so they exist
        config["logging"]["main_log"] = str(tmp_path / "test.log")
        config["logging"]["debug_log"] = str(tmp_path / "debug.log")
        config["router"]["ssh_key"] = str(tmp_path / "key")
        config["router"]["transport"] = "rest"
        config_path = _write_config(tmp_path, config)

        monkeypatch.setattr(sys, "argv", ["wanctl-check-config", config_path, "--no-color"])
        result = main()
        # May be 0 (all pass) or 2 (env var warnings), but not 1
        assert result in (0, 2)

    def test_main_nonexistent_file_returns_1(self, monkeypatch, capsys):
        monkeypatch.setattr(sys, "argv", ["wanctl-check-config", "/nonexistent/config.yaml", "--no-color"])
        result = main()
        assert result == 1
        captured = capsys.readouterr()
        assert "not found" in captured.err

    def test_main_invalid_yaml_returns_1(self, tmp_path, monkeypatch, capsys):
        bad_yaml = tmp_path / "bad.yaml"
        bad_yaml.write_text("key: [unclosed bracket\n  bad: {indent")
        monkeypatch.setattr(sys, "argv", ["wanctl-check-config", str(bad_yaml), "--no-color"])
        result = main()
        assert result == 1
        captured = capsys.readouterr()
        assert "YAML" in captured.err or "Error" in captured.err


# =============================================================================
# TestErrorCollection (CVAL-04)
# =============================================================================


class TestErrorCollection:
    """Verify all errors are collected, not just the first."""

    def test_multiple_schema_errors_all_reported(self):
        """Config with 3+ errors should report all of them."""
        data = {
            # Missing wan_name (required)
            "router": {"host": 12345},  # wrong type
            "logging": {"main_log": "/tmp/a.log", "debug_log": "/tmp/b.log"},
            "lock_file": "/tmp/lock",
            "lock_timeout": 99999,  # out of range (max 3600)
        }
        results = validate_schema_fields(data)
        errors = [r for r in results if r.severity == Severity.ERROR]
        # Should have at least 3 errors: missing wan_name, wrong router.host type, lock_timeout range
        assert len(errors) >= 3


# =============================================================================
# TestSchemaValidation
# =============================================================================


class TestSchemaValidation:
    """Test individual schema field validation."""

    def test_valid_field_produces_pass(self):
        data = _valid_config_data()
        results = validate_schema_fields(data)
        pass_results = [r for r in results if r.severity == Severity.PASS]
        assert len(pass_results) > 0

    def test_missing_required_field_produces_error(self):
        data = _valid_config_data()
        del data["wan_name"]
        results = validate_schema_fields(data)
        errors = [r for r in results if r.severity == Severity.ERROR and "wan_name" in r.field]
        assert len(errors) == 1

    def test_out_of_range_value_produces_error(self):
        data = _valid_config_data()
        data["lock_timeout"] = 99999  # max is 3600
        results = validate_schema_fields(data)
        errors = [r for r in results if r.severity == Severity.ERROR and "lock_timeout" in r.field]
        assert len(errors) == 1


# =============================================================================
# TestCrossField (CVAL-05)
# =============================================================================


class TestCrossField:
    """Test cross-field semantic validation."""

    def test_floor_ordering_violation_download(self):
        """floor_green < floor_red should be caught."""
        data = _valid_config_data()
        dl = data["continuous_monitoring"]["download"]
        # Replace legacy floor with modern floors where green < red (violation)
        del dl["floor_mbps"]
        dl["floor_green_mbps"] = 5  # green < red = violation
        dl["floor_yellow_mbps"] = 10
        dl["floor_soft_red_mbps"] = 15
        dl["floor_red_mbps"] = 20
        results = validate_cross_fields(data)
        errors = [r for r in results if r.severity == Severity.ERROR and "download" in r.field]
        assert len(errors) >= 1

    def test_ceiling_less_than_floor(self):
        """ceiling < floor should be caught."""
        data = _valid_config_data()
        dl = data["continuous_monitoring"]["download"]
        dl["ceiling_mbps"] = 5  # ceiling < floor_mbps (10) = violation
        results = validate_cross_fields(data)
        errors = [r for r in results if r.severity == Severity.ERROR and "download" in r.field]
        assert len(errors) >= 1

    def test_threshold_misordering(self):
        """target > warn should be caught."""
        data = _valid_config_data()
        data["continuous_monitoring"]["thresholds"]["target_bloat_ms"] = 50
        data["continuous_monitoring"]["thresholds"]["warn_bloat_ms"] = 10  # less than target
        results = validate_cross_fields(data)
        errors = [r for r in results if r.severity == Severity.ERROR and "threshold" in r.field]
        assert len(errors) >= 1

    def test_valid_floors_and_thresholds_produce_pass(self):
        data = _valid_config_data()
        results = validate_cross_fields(data)
        passes = [r for r in results if r.severity == Severity.PASS]
        assert len(passes) >= 3  # download, upload, thresholds

    def test_legacy_single_floor_accepted(self):
        """Legacy floor_mbps format should not produce errors."""
        data = _valid_config_data()
        # Already uses floor_mbps (legacy), so should work
        results = validate_cross_fields(data)
        errors = [r for r in results if r.severity == Severity.ERROR]
        assert len(errors) == 0


# =============================================================================
# TestPathChecks (CVAL-06)
# =============================================================================


class TestPathChecks:
    """Test file and directory path validation."""

    def test_missing_log_parent_produces_error(self):
        data = _valid_config_data()
        data["logging"]["main_log"] = "/nonexistent/deep/path/test.log"
        results = check_paths(data)
        errors = [
            r for r in results
            if r.severity == Severity.ERROR and "main_log" in r.field
        ]
        assert len(errors) == 1
        assert "mkdir -p" in (errors[0].suggestion or "")

    def test_existing_log_parent_produces_pass(self, tmp_path):
        data = _valid_config_data()
        data["logging"]["main_log"] = str(tmp_path / "test.log")
        data["logging"]["debug_log"] = str(tmp_path / "debug.log")
        results = check_paths(data)
        passes = [
            r for r in results
            if r.severity == Severity.PASS and "log" in r.field
        ]
        assert len(passes) >= 2

    def test_missing_ssh_key_produces_error(self):
        data = _valid_config_data()
        data["router"]["ssh_key"] = "/nonexistent/key"
        data["router"]["transport"] = "ssh"  # SSH transport makes it ERROR
        results = check_paths(data)
        errors = [
            r for r in results
            if r.severity == Severity.ERROR and "ssh_key" in r.field
        ]
        assert len(errors) == 1

    def test_ssh_key_insecure_perms_produces_warn(self, tmp_path):
        key_file = tmp_path / "test_key"
        key_file.write_text("fake key content")
        key_file.chmod(0o644)
        data = _valid_config_data()
        data["router"]["ssh_key"] = str(key_file)
        results = check_paths(data)
        warns = [
            r for r in results
            if r.severity == Severity.WARN and "ssh_key" in r.field
        ]
        assert len(warns) == 1
        assert "chmod 600" in (warns[0].suggestion or "")

    def test_ssh_key_secure_perms_produces_pass(self, tmp_path):
        key_file = tmp_path / "test_key"
        key_file.write_text("fake key content")
        key_file.chmod(0o600)
        data = _valid_config_data()
        data["router"]["ssh_key"] = str(key_file)
        results = check_paths(data)
        passes = [
            r for r in results
            if r.severity == Severity.PASS and "ssh_key" in r.field
        ]
        assert len(passes) == 1


# =============================================================================
# TestEnvVars (CVAL-07)
# =============================================================================


class TestEnvVars:
    """Test environment variable detection."""

    def test_unset_env_var_produces_warn(self, monkeypatch):
        monkeypatch.delenv("ROUTER_PASSWORD", raising=False)
        data = _valid_config_data()
        data["router"]["password"] = "${ROUTER_PASSWORD}"
        results = check_env_vars(data)
        warns = [r for r in results if r.severity == Severity.WARN]
        assert len(warns) == 1
        assert "ROUTER_PASSWORD" in warns[0].message

    def test_set_env_var_produces_pass(self, monkeypatch):
        monkeypatch.setenv("ROUTER_PASSWORD", "secret123")
        data = _valid_config_data()
        data["router"]["password"] = "${ROUTER_PASSWORD}"
        results = check_env_vars(data)
        passes = [r for r in results if r.severity == Severity.PASS]
        assert len(passes) == 1

    def test_no_env_vars_produces_no_results(self):
        data = _valid_config_data()
        data["router"]["password"] = "plaintext"
        results = check_env_vars(data)
        assert len(results) == 0


# =============================================================================
# TestDeprecated (CVAL-08)
# =============================================================================


class TestDeprecated:
    """Test deprecated parameter detection."""

    def test_alpha_baseline_produces_warn_with_translation(self):
        data = _valid_config_data()
        # Replace time constant with deprecated alpha_baseline
        del data["continuous_monitoring"]["thresholds"]["baseline_time_constant_sec"]
        data["continuous_monitoring"]["thresholds"]["alpha_baseline"] = 0.005
        results = check_deprecated_params(data)
        warns = [r for r in results if r.severity == Severity.WARN]
        assert len(warns) == 1
        assert "alpha_baseline" in warns[0].message
        assert "10.0" in warns[0].message  # 0.05/0.005 = 10.0

    def test_modern_param_produces_no_warn(self):
        """baseline_time_constant_sec without alpha produces no WARN."""
        data = _valid_config_data()
        # Has baseline_time_constant_sec, no alpha_baseline
        results = check_deprecated_params(data)
        warns = [r for r in results if r.severity == Severity.WARN]
        assert len(warns) == 0

    def test_alpha_load_produces_warn(self):
        data = _valid_config_data()
        del data["continuous_monitoring"]["thresholds"]["load_time_constant_sec"]
        data["continuous_monitoring"]["thresholds"]["alpha_load"] = 0.5
        results = check_deprecated_params(data)
        warns = [r for r in results if r.severity == Severity.WARN]
        assert len(warns) == 1
        assert "alpha_load" in warns[0].message


# =============================================================================
# TestExitCodes (CVAL-11)
# =============================================================================


class TestExitCodes:
    """Test exit code calculation."""

    def test_all_pass_returns_0(self, tmp_path, monkeypatch):
        config = _valid_config_data()
        config["logging"]["main_log"] = str(tmp_path / "test.log")
        config["logging"]["debug_log"] = str(tmp_path / "debug.log")
        config["router"]["ssh_key"] = str(tmp_path / "key")
        config["router"]["transport"] = "rest"
        config["router"]["password"] = "plaintext"  # No env var
        config_path = _write_config(tmp_path, config)

        monkeypatch.setattr(sys, "argv", ["wanctl-check-config", config_path, "--no-color"])
        result = main()
        assert result == 0

    def test_errors_present_returns_1(self, tmp_path, monkeypatch):
        config = _valid_config_data()
        del config["wan_name"]  # Missing required field -> ERROR
        config["router"]["password"] = "plaintext"
        config_path = _write_config(tmp_path, config)

        monkeypatch.setattr(sys, "argv", ["wanctl-check-config", config_path, "--no-color"])
        result = main()
        assert result == 1

    def test_warnings_only_returns_2(self, tmp_path, monkeypatch):
        config = _valid_config_data()
        config["logging"]["main_log"] = str(tmp_path / "test.log")
        config["logging"]["debug_log"] = str(tmp_path / "debug.log")
        config["router"]["ssh_key"] = str(tmp_path / "key")
        config["router"]["transport"] = "rest"
        # Add deprecated param (WARN) but no errors
        del config["continuous_monitoring"]["thresholds"]["baseline_time_constant_sec"]
        config["continuous_monitoring"]["thresholds"]["alpha_baseline"] = 0.005
        config["router"]["password"] = "plaintext"
        config_path = _write_config(tmp_path, config)

        monkeypatch.setattr(sys, "argv", ["wanctl-check-config", config_path, "--no-color"])
        result = main()
        assert result == 2


# =============================================================================
# TestUnknownKeys
# =============================================================================


class TestUnknownKeys:
    """Test unknown key detection with fuzzy matching."""

    def test_typo_key_produces_warn_with_suggestion(self):
        data = _valid_config_data()
        data["continuous_monitoring"]["download"]["ceilling_mbps"] = 100  # typo
        results = check_unknown_keys(data)
        warns = [
            r for r in results
            if r.severity == Severity.WARN and "ceilling" in r.field
        ]
        assert len(warns) == 1
        assert "did you mean" in (warns[0].suggestion or "").lower()

    def test_valid_keys_produce_no_warnings(self):
        data = _valid_config_data()
        results = check_unknown_keys(data)
        warns = [r for r in results if r.severity == Severity.WARN]
        assert len(warns) == 0

    def test_alerting_rules_subkeys_not_flagged(self):
        """Dynamic alerting.rules.* sub-keys should not be flagged."""
        data = _valid_config_data()
        data["alerting"] = {
            "enabled": True,
            "webhook_url": "https://example.com",
            "rules": {
                "congestion_download": {
                    "severity": "warning",
                    "cooldown_sec": 300,
                },
            },
        }
        results = check_unknown_keys(data)
        warns = [
            r for r in results
            if r.severity == Severity.WARN and "alerting" in r.field
        ]
        assert len(warns) == 0


# =============================================================================
# TestOutputFormat
# =============================================================================


class TestOutputFormat:
    """Test output formatting."""

    def test_output_grouped_by_category_headers(self):
        results = [
            CheckResult("Schema Validation", "wan_name", Severity.PASS, "wan_name: valid"),
            CheckResult("Cross-field Checks", "floors", Severity.PASS, "floors: valid"),
        ]
        output = format_results(results, no_color=True)
        assert "=== Schema Validation ===" in output
        assert "=== Cross-field Checks ===" in output

    def test_quiet_suppresses_pass_results(self):
        results = [
            CheckResult("Schema Validation", "wan_name", Severity.PASS, "wan_name: valid"),
            CheckResult("Schema Validation", "bad_field", Severity.ERROR, "bad_field: missing"),
        ]
        output = format_results(results, no_color=True, quiet=True)
        assert "wan_name: valid" not in output
        assert "bad_field: missing" in output

    def test_no_color_strips_ansi(self):
        results = [
            CheckResult("Test", "field", Severity.ERROR, "error msg"),
        ]
        output = format_results(results, no_color=True)
        assert "\033[" not in output

    def test_summary_line_present(self):
        results = [
            CheckResult("Test", "field", Severity.PASS, "ok"),
        ]
        output = format_results(results, no_color=True)
        assert "Result:" in output
        assert "PASS" in output

    def test_suggestion_shown(self):
        results = [
            CheckResult("Test", "field", Severity.ERROR, "error", suggestion="fix it"),
        ]
        output = format_results(results, no_color=True)
        assert "-> fix it" in output

    def test_summary_includes_config_type_steering(self):
        results = [
            CheckResult("Test", "field", Severity.PASS, "ok"),
        ]
        output = format_results(results, no_color=True, config_type="steering")
        assert "steering config" in output

    def test_summary_includes_config_type_autorate(self):
        results = [
            CheckResult("Test", "field", Severity.PASS, "ok"),
        ]
        output = format_results(results, no_color=True, config_type="autorate")
        assert "autorate config" in output


# =============================================================================
# STEERING CONFIG FIXTURE
# =============================================================================


def _valid_steering_data() -> dict:
    """Return a minimal valid steering config dict.

    All required BASE_SCHEMA + SteeringConfig.SCHEMA fields present.
    """
    return {
        "wan_name": "steering",
        "router": {
            "host": "10.0.0.1",
            "user": "admin",
            "ssh_key": "/tmp/fake_key",
            "transport": "rest",
            "password": "${ROUTER_PASSWORD}",
        },
        "topology": {
            "primary_wan": "spectrum",
            "primary_wan_config": "/etc/wanctl/spectrum.yaml",
            "alternate_wan": "att",
        },
        "mangle_rule": {
            "comment": "ADAPTIVE: Steer latency-sensitive to ATT",
        },
        "measurement": {
            "interval_seconds": 0.5,
            "ping_host": "1.1.1.1",
            "ping_count": 3,
        },
        "state": {
            "file": "/var/lib/wanctl/steering_state.json",
            "history_size": 240,
        },
        "thresholds": {
            "bad_threshold_ms": 25.0,
            "recovery_threshold_ms": 12.0,
        },
        "logging": {
            "main_log": "/tmp/test.log",
            "debug_log": "/tmp/test_debug.log",
        },
        "lock_file": "/tmp/test.lock",
        "lock_timeout": 60,
    }


# =============================================================================
# TestConfigTypeDetection (CVAL-03)
# =============================================================================


class TestConfigTypeDetection:
    """Test config type auto-detection."""

    def test_topology_key_returns_steering(self):
        data = _valid_steering_data()
        assert detect_config_type(data) == "steering"

    def test_continuous_monitoring_key_returns_autorate(self):
        data = _valid_config_data()
        assert detect_config_type(data) == "autorate"

    def test_both_keys_raises_value_error(self):
        data = _valid_config_data()
        data["topology"] = {"primary_wan": "wan1"}
        with pytest.raises(ValueError, match="ambiguous"):
            detect_config_type(data)

    def test_neither_key_raises_value_error(self):
        data = {"wan_name": "test", "router": {"host": "1.2.3.4"}}
        with pytest.raises(ValueError, match="could not determine"):
            detect_config_type(data)

    def test_type_flag_overrides_detection(self, tmp_path, monkeypatch):
        """--type autorate forces autorate validation on a steering config."""
        config = _valid_steering_data()
        config["logging"]["main_log"] = str(tmp_path / "test.log")
        config["logging"]["debug_log"] = str(tmp_path / "debug.log")
        config_path = _write_config(tmp_path, config)

        monkeypatch.setattr(
            sys, "argv",
            ["wanctl-check-config", config_path, "--no-color", "--type", "autorate"],
        )
        # Should not crash -- runs autorate validators (may produce errors, that's OK)
        result = main()
        assert isinstance(result, int)


# =============================================================================
# TestSteeringValidation (CVAL-02)
# =============================================================================


class TestSteeringValidation:
    """Test steering-specific schema validation."""

    def test_valid_steering_config_no_errors(self):
        data = _valid_steering_data()
        results = validate_steering_schema_fields(data)
        errors = [r for r in results if r.severity == Severity.ERROR]
        assert len(errors) == 0

    def test_missing_topology_primary_wan_produces_error(self):
        data = _valid_steering_data()
        del data["topology"]["primary_wan"]
        results = validate_steering_schema_fields(data)
        errors = [
            r for r in results
            if r.severity == Severity.ERROR and "topology.primary_wan" in r.field
        ]
        assert len(errors) == 1

    def test_unknown_steering_key_produces_warn_with_suggestion(self):
        data = _valid_steering_data()
        data["measuremnt"] = {"interval_seconds": 0.5}  # typo
        results = check_steering_unknown_keys(data)
        warns = [
            r for r in results
            if r.severity == Severity.WARN and "measuremnt" in r.field
        ]
        assert len(warns) >= 1
        assert "did you mean" in (warns[0].suggestion or "").lower()

    def test_production_steering_yaml_no_unknown_keys(self):
        """Production steering.yaml must produce zero unknown-key warnings."""
        with open("configs/steering.yaml") as f:
            data = yaml.safe_load(f)
        results = check_steering_unknown_keys(data)
        warns = [r for r in results if r.severity == Severity.WARN]
        assert len(warns) == 0, f"False positive warnings: {[w.message for w in warns]}"

    def test_alerting_rules_subkeys_not_flagged_steering(self):
        """Dynamic alerting.rules.* sub-keys not flagged in steering."""
        data = _valid_steering_data()
        data["alerting"] = {
            "enabled": True,
            "webhook_url": "https://example.com",
            "rules": {
                "congestion_download": {
                    "severity": "warning",
                    "cooldown_sec": 300,
                },
            },
        }
        results = check_steering_unknown_keys(data)
        warns = [
            r for r in results
            if r.severity == Severity.WARN and "alerting" in r.field
        ]
        assert len(warns) == 0


# =============================================================================
# TestSteeringCrossField
# =============================================================================


class TestSteeringCrossField:
    """Test steering-specific cross-field validation."""

    def test_recovery_ge_steer_threshold_produces_error(self):
        """recovery_threshold >= steer_threshold when use_confidence_scoring=true."""
        data = _valid_steering_data()
        data["mode"] = {"use_confidence_scoring": True}
        data["confidence"] = {
            "steer_threshold": 55,
            "recovery_threshold": 60,  # >= steer_threshold
        }
        results = validate_steering_cross_fields(data)
        errors = [r for r in results if r.severity == Severity.ERROR]
        assert len(errors) >= 1
        assert "recovery_threshold" in errors[0].message

    def test_valid_threshold_ordering_produces_pass(self):
        data = _valid_steering_data()
        data["mode"] = {"use_confidence_scoring": True}
        data["confidence"] = {
            "steer_threshold": 55,
            "recovery_threshold": 20,
        }
        results = validate_steering_cross_fields(data)
        passes = [r for r in results if r.severity == Severity.PASS and "confidence" in r.field.lower()]
        assert len(passes) >= 1

    def test_interval_below_005_produces_warn(self):
        data = _valid_steering_data()
        data["measurement"]["interval_seconds"] = 0.01
        results = validate_steering_cross_fields(data)
        warns = [
            r for r in results
            if r.severity == Severity.WARN and "interval" in r.field
        ]
        assert len(warns) == 1

    def test_history_window_below_30s_produces_warn(self):
        data = _valid_steering_data()
        data["measurement"]["interval_seconds"] = 0.5
        data["state"]["history_size"] = 10  # 10 * 0.5 = 5s < 30s
        results = validate_steering_cross_fields(data)
        warns = [
            r for r in results
            if r.severity == Severity.WARN and "history_size" in r.field
        ]
        assert len(warns) == 1


# =============================================================================
# TestSteeringDeprecated
# =============================================================================


class TestSteeringDeprecated:
    """Test steering deprecated parameter detection."""

    def test_mode_cake_aware_produces_warn(self):
        data = _valid_steering_data()
        data["mode"] = {"cake_aware": True}
        results = check_steering_deprecated_params(data)
        warns = [r for r in results if r.severity == Severity.WARN and "cake_aware" in r.field]
        assert len(warns) == 1

    def test_cake_state_sources_spectrum_produces_warn(self):
        data = _valid_steering_data()
        data["cake_state_sources"] = {"spectrum": "/run/wanctl/spectrum_state.json"}
        results = check_steering_deprecated_params(data)
        warns = [r for r in results if r.severity == Severity.WARN and "spectrum" in r.field]
        assert len(warns) == 1

    def test_cake_queues_spectrum_download_produces_warn(self):
        data = _valid_steering_data()
        data["cake_queues"] = {"spectrum_download": "WAN-Download-Spectrum"}
        results = check_steering_deprecated_params(data)
        warns = [r for r in results if r.severity == Severity.WARN and "spectrum_download" in r.field]
        assert len(warns) == 1


# =============================================================================
# TestCrossConfigValidation (CVAL-09)
# =============================================================================


class TestCrossConfigValidation:
    """Test steering cross-config validation."""

    def test_missing_primary_wan_config_file_produces_warn(self):
        data = _valid_steering_data()
        data["topology"]["primary_wan_config"] = "/nonexistent/spectrum.yaml"
        results = check_steering_cross_config(data)
        warns = [
            r for r in results
            if r.severity == Severity.WARN and "primary_wan_config" in r.field
        ]
        assert len(warns) == 1

    def test_file_exists_wan_name_matches_produces_pass(self, tmp_path):
        ref_config = tmp_path / "spectrum.yaml"
        ref_config.write_text(yaml.dump({"wan_name": "spectrum"}))
        data = _valid_steering_data()
        data["topology"]["primary_wan"] = "spectrum"
        data["topology"]["primary_wan_config"] = str(ref_config)
        results = check_steering_cross_config(data)
        passes = [r for r in results if r.severity == Severity.PASS]
        assert len(passes) >= 1  # file exists + wan_name match

    def test_file_exists_wan_name_mismatches_produces_error(self, tmp_path):
        ref_config = tmp_path / "spectrum.yaml"
        ref_config.write_text(yaml.dump({"wan_name": "att"}))
        data = _valid_steering_data()
        data["topology"]["primary_wan"] = "spectrum"
        data["topology"]["primary_wan_config"] = str(ref_config)
        results = check_steering_cross_config(data)
        errors = [r for r in results if r.severity == Severity.ERROR]
        assert len(errors) == 1
        assert "mismatch" in errors[0].message

    def test_file_exists_no_wan_name_key_produces_warn(self, tmp_path):
        ref_config = tmp_path / "spectrum.yaml"
        ref_config.write_text(yaml.dump({"router": {"host": "1.2.3.4"}}))
        data = _valid_steering_data()
        data["topology"]["primary_wan_config"] = str(ref_config)
        results = check_steering_cross_config(data)
        warns = [r for r in results if r.severity == Severity.WARN and "wan_name" in r.field]
        assert len(warns) == 1

    def test_file_exists_invalid_yaml_produces_warn(self, tmp_path):
        ref_config = tmp_path / "spectrum.yaml"
        ref_config.write_text("key: [unclosed bracket\n  bad: {indent")
        data = _valid_steering_data()
        data["topology"]["primary_wan_config"] = str(ref_config)
        results = check_steering_cross_config(data)
        warns = [r for r in results if r.severity == Severity.WARN]
        assert len(warns) >= 1

    def test_file_unreadable_produces_warn(self, tmp_path):
        ref_config = tmp_path / "spectrum.yaml"
        ref_config.write_text(yaml.dump({"wan_name": "spectrum"}))
        ref_config.chmod(0o000)
        data = _valid_steering_data()
        data["topology"]["primary_wan_config"] = str(ref_config)
        results = check_steering_cross_config(data)
        warns = [r for r in results if r.severity == Severity.WARN]
        assert len(warns) >= 1
        # Cleanup permissions for tmp_path cleanup
        ref_config.chmod(0o644)


# =============================================================================
# TestJsonOutput (CVAL-10)
# =============================================================================


class TestJsonOutput:
    """Test JSON output mode for CI/scripting integration."""

    def test_json_output_has_top_level_keys(self):
        """JSON output contains config_type, result, errors, warnings, categories."""
        results = [
            CheckResult("Schema Validation", "wan_name", Severity.PASS, "wan_name: valid"),
        ]
        output = format_results_json(results, config_type="autorate")
        data = json.loads(output)
        assert "config_type" in data
        assert "result" in data
        assert "errors" in data
        assert "warnings" in data
        assert "categories" in data

    def test_json_config_type_matches_detected_type_steering(self):
        results = [
            CheckResult("Schema Validation", "topology", Severity.PASS, "topology: valid"),
        ]
        output = format_results_json(results, config_type="steering")
        data = json.loads(output)
        assert data["config_type"] == "steering"

    def test_json_config_type_matches_detected_type_autorate(self):
        results = [
            CheckResult("Schema Validation", "wan_name", Severity.PASS, "wan_name: valid"),
        ]
        output = format_results_json(results, config_type="autorate")
        data = json.loads(output)
        assert data["config_type"] == "autorate"

    def test_json_result_pass_when_no_errors_or_warnings(self):
        results = [
            CheckResult("Schema Validation", "wan_name", Severity.PASS, "wan_name: valid"),
        ]
        output = format_results_json(results, config_type="autorate")
        data = json.loads(output)
        assert data["result"] == "PASS"

    def test_json_result_warn_when_warnings_only(self):
        results = [
            CheckResult("Unknown Keys", "typo_key", Severity.WARN, "Unknown config key: typo_key"),
        ]
        output = format_results_json(results, config_type="autorate")
        data = json.loads(output)
        assert data["result"] == "WARN"

    def test_json_result_fail_when_errors(self):
        results = [
            CheckResult("Schema Validation", "wan_name", Severity.ERROR, "wan_name: missing"),
        ]
        output = format_results_json(results, config_type="autorate")
        data = json.loads(output)
        assert data["result"] == "FAIL"

    def test_json_errors_and_warnings_are_integer_counts(self):
        results = [
            CheckResult("Schema Validation", "wan_name", Severity.ERROR, "missing"),
            CheckResult("Schema Validation", "router.host", Severity.ERROR, "wrong type"),
            CheckResult("Unknown Keys", "typo_key", Severity.WARN, "unknown key"),
        ]
        output = format_results_json(results, config_type="autorate")
        data = json.loads(output)
        assert data["errors"] == 2
        assert data["warnings"] == 1
        assert isinstance(data["errors"], int)
        assert isinstance(data["warnings"], int)

    def test_json_categories_is_dict_with_category_keys(self):
        results = [
            CheckResult("Schema Validation", "wan_name", Severity.PASS, "wan_name: valid"),
            CheckResult("Cross-field Checks", "floors", Severity.PASS, "floors: valid"),
        ]
        output = format_results_json(results, config_type="autorate")
        data = json.loads(output)
        assert isinstance(data["categories"], dict)
        assert "Schema Validation" in data["categories"]
        assert "Cross-field Checks" in data["categories"]

    def test_json_check_objects_have_required_keys(self):
        results = [
            CheckResult("Schema Validation", "wan_name", Severity.PASS, "wan_name: valid"),
        ]
        output = format_results_json(results, config_type="autorate")
        data = json.loads(output)
        checks = data["categories"]["Schema Validation"]
        assert len(checks) == 1
        check = checks[0]
        assert "field" in check
        assert "severity" in check
        assert "message" in check

    def test_json_suggestion_present_when_not_none(self):
        results = [
            CheckResult("Test", "field", Severity.WARN, "warning", suggestion="fix it"),
        ]
        output = format_results_json(results, config_type="autorate")
        data = json.loads(output)
        check = data["categories"]["Test"][0]
        assert check["suggestion"] == "fix it"

    def test_json_suggestion_omitted_when_none(self):
        results = [
            CheckResult("Test", "field", Severity.PASS, "ok"),
        ]
        output = format_results_json(results, config_type="autorate")
        data = json.loads(output)
        check = data["categories"]["Test"][0]
        assert "suggestion" not in check

    def test_json_severity_values_are_lowercase_strings(self):
        results = [
            CheckResult("Test", "f1", Severity.PASS, "ok"),
            CheckResult("Test", "f2", Severity.WARN, "warn"),
            CheckResult("Test", "f3", Severity.ERROR, "err"),
        ]
        output = format_results_json(results, config_type="autorate")
        data = json.loads(output)
        severities = [c["severity"] for c in data["categories"]["Test"]]
        assert severities == ["pass", "warn", "error"]

    def test_json_all_results_included_not_filtered(self):
        """All results (pass, warn, error) appear in JSON output."""
        results = [
            CheckResult("Cat1", "f1", Severity.PASS, "pass msg"),
            CheckResult("Cat1", "f2", Severity.WARN, "warn msg"),
            CheckResult("Cat1", "f3", Severity.ERROR, "error msg"),
        ]
        output = format_results_json(results, config_type="autorate")
        data = json.loads(output)
        assert len(data["categories"]["Cat1"]) == 3

    def test_json_output_is_valid_json(self):
        results = [
            CheckResult("Test", "field", Severity.PASS, "ok"),
        ]
        output = format_results_json(results, config_type="autorate")
        # Should not raise
        parsed = json.loads(output)
        assert isinstance(parsed, dict)

    def test_json_output_has_no_ansi_escape_codes(self):
        results = [
            CheckResult("Test", "field", Severity.ERROR, "error msg"),
            CheckResult("Test", "f2", Severity.WARN, "warn msg"),
            CheckResult("Test", "f3", Severity.PASS, "pass msg"),
        ]
        output = format_results_json(results, config_type="autorate")
        assert "\033[" not in output

    def test_json_exit_code_0_for_clean_config(self, tmp_path, monkeypatch):
        config = _valid_config_data()
        config["logging"]["main_log"] = str(tmp_path / "test.log")
        config["logging"]["debug_log"] = str(tmp_path / "debug.log")
        config["router"]["ssh_key"] = str(tmp_path / "key")
        config["router"]["transport"] = "rest"
        config["router"]["password"] = "plaintext"
        config_path = _write_config(tmp_path, config)

        monkeypatch.setattr(
            sys, "argv", ["wanctl-check-config", config_path, "--json"]
        )
        result = main()
        assert result == 0

    def test_json_exit_code_1_for_config_with_errors(self, tmp_path, monkeypatch):
        config = _valid_config_data()
        del config["wan_name"]  # Missing required field -> ERROR
        config["router"]["password"] = "plaintext"
        config_path = _write_config(tmp_path, config)

        monkeypatch.setattr(
            sys, "argv", ["wanctl-check-config", config_path, "--json"]
        )
        result = main()
        assert result == 1

    def test_json_exit_code_2_for_warnings_only(self, tmp_path, monkeypatch):
        config = _valid_config_data()
        config["logging"]["main_log"] = str(tmp_path / "test.log")
        config["logging"]["debug_log"] = str(tmp_path / "debug.log")
        config["router"]["ssh_key"] = str(tmp_path / "key")
        config["router"]["transport"] = "rest"
        del config["continuous_monitoring"]["thresholds"]["baseline_time_constant_sec"]
        config["continuous_monitoring"]["thresholds"]["alpha_baseline"] = 0.005
        config["router"]["password"] = "plaintext"
        config_path = _write_config(tmp_path, config)

        monkeypatch.setattr(
            sys, "argv", ["wanctl-check-config", config_path, "--json"]
        )
        result = main()
        assert result == 2

    def test_json_and_quiet_are_independent(self, tmp_path, monkeypatch, capsys):
        """--json output unchanged by --quiet."""
        config = _valid_config_data()
        config["logging"]["main_log"] = str(tmp_path / "test.log")
        config["logging"]["debug_log"] = str(tmp_path / "debug.log")
        config["router"]["ssh_key"] = str(tmp_path / "key")
        config["router"]["transport"] = "rest"
        config["router"]["password"] = "plaintext"
        config_path = _write_config(tmp_path, config)

        # Run with --json only
        monkeypatch.setattr(
            sys, "argv", ["wanctl-check-config", config_path, "--json"]
        )
        main()
        json_only = capsys.readouterr().out.strip()

        # Run with --json --quiet
        monkeypatch.setattr(
            sys, "argv", ["wanctl-check-config", config_path, "--json", "-q"]
        )
        main()
        json_quiet = capsys.readouterr().out.strip()

        # Both should produce identical JSON
        assert json.loads(json_only) == json.loads(json_quiet)

    def test_json_pipe_friendly(self):
        """json.loads(output)["result"] works for piping."""
        results = [
            CheckResult("Test", "field", Severity.PASS, "ok"),
        ]
        output = format_results_json(results, config_type="autorate")
        assert json.loads(output)["result"] == "PASS"

    def test_json_cli_flag_parsed(self):
        """--json flag is recognized by parser."""
        parser = create_parser()
        args = parser.parse_args(["test.yaml", "--json"])
        assert args.json is True

    def test_json_cli_flag_default_false(self):
        """--json defaults to False."""
        parser = create_parser()
        args = parser.parse_args(["test.yaml"])
        assert args.json is False


# =============================================================================
# LINUX CAKE VALIDATION (CONF-04)
# =============================================================================


class TestLinuxCakeValidation:
    """Tests for linux-cake transport validation (CONF-04)."""

    def _make_config(self, transport="linux-cake", cake_params=None):
        """Helper to build a config dict with transport and optional cake_params."""
        data = {
            "wan_name": "test",
            "router": {"host": "10.0.0.1", "user": "admin", "transport": transport},
        }
        if cake_params is not None:
            data["cake_params"] = cake_params
        return data

    def test_skips_rest_transport(self):
        data = self._make_config(transport="rest")
        results = validate_linux_cake(data)
        assert results == []

    def test_skips_ssh_transport(self):
        data = self._make_config(transport="ssh")
        results = validate_linux_cake(data)
        assert results == []

    def test_missing_cake_params_error(self):
        data = self._make_config(transport="linux-cake")
        results = validate_linux_cake(data)
        errors = [r for r in results if r.severity == Severity.ERROR]
        assert len(errors) >= 1
        assert any("cake_params" in r.message for r in errors)

    def test_cake_params_not_dict_error(self):
        data = self._make_config(transport="linux-cake", cake_params="bad")
        results = validate_linux_cake(data)
        errors = [r for r in results if r.severity == Severity.ERROR]
        assert len(errors) >= 1

    def test_valid_cake_params_passes(self):
        data = self._make_config(
            transport="linux-cake",
            cake_params={
                "upload_interface": "enp8s0",
                "download_interface": "enp9s0",
            },
        )
        results = validate_linux_cake(data)
        errors = [r for r in results if r.severity == Severity.ERROR]
        assert len(errors) == 0
        passes = [r for r in results if r.severity == Severity.PASS]
        assert len(passes) >= 2  # both interfaces pass

    def test_missing_upload_interface_error(self):
        data = self._make_config(
            transport="linux-cake",
            cake_params={"download_interface": "enp9s0"},
        )
        results = validate_linux_cake(data)
        errors = [r for r in results if r.severity == Severity.ERROR]
        assert any("upload_interface" in r.field for r in errors)

    def test_missing_download_interface_error(self):
        data = self._make_config(
            transport="linux-cake",
            cake_params={"upload_interface": "enp8s0"},
        )
        results = validate_linux_cake(data)
        errors = [r for r in results if r.severity == Severity.ERROR]
        assert any("download_interface" in r.field for r in errors)

    def test_empty_string_interface_error(self):
        data = self._make_config(
            transport="linux-cake",
            cake_params={
                "upload_interface": "",
                "download_interface": "enp9s0",
            },
        )
        results = validate_linux_cake(data)
        errors = [r for r in results if r.severity == Severity.ERROR]
        assert any("upload_interface" in r.field for r in errors)

    def test_valid_overhead_no_error(self):
        data = self._make_config(
            transport="linux-cake",
            cake_params={
                "upload_interface": "enp8s0",
                "download_interface": "enp9s0",
                "overhead": "docsis",
            },
        )
        results = validate_linux_cake(data)
        errors = [r for r in results if r.severity == Severity.ERROR]
        assert len(errors) == 0

    def test_invalid_overhead_error(self):
        data = self._make_config(
            transport="linux-cake",
            cake_params={
                "upload_interface": "enp8s0",
                "download_interface": "enp9s0",
                "overhead": "bogus",
            },
        )
        results = validate_linux_cake(data)
        errors = [r for r in results if r.severity == Severity.ERROR]
        assert any("overhead" in r.field for r in errors)
        assert any(
            "suggestion" in dir(r) and r.suggestion
            for r in errors
            if "overhead" in r.field
        )

    def test_no_overhead_no_error(self):
        """Overhead is optional -- absence is not an error."""
        data = self._make_config(
            transport="linux-cake",
            cake_params={
                "upload_interface": "enp8s0",
                "download_interface": "enp9s0",
            },
        )
        results = validate_linux_cake(data)
        errors = [r for r in results if r.severity == Severity.ERROR]
        assert len(errors) == 0

    @patch("shutil.which", return_value="/usr/sbin/tc")
    def test_tc_binary_found_pass(self, mock_which):
        data = self._make_config(
            transport="linux-cake",
            cake_params={
                "upload_interface": "enp8s0",
                "download_interface": "enp9s0",
            },
        )
        results = validate_linux_cake(data)
        passes = [
            r for r in results if r.severity == Severity.PASS and "tc" in r.field.lower()
        ]
        assert len(passes) >= 1

    @patch("shutil.which", return_value=None)
    def test_tc_binary_not_found_warn(self, mock_which):
        """tc absence is WARN (not ERROR) -- check-config is an offline validator."""
        data = self._make_config(
            transport="linux-cake",
            cake_params={
                "upload_interface": "enp8s0",
                "download_interface": "enp9s0",
            },
        )
        results = validate_linux_cake(data)
        warns = [
            r for r in results if r.severity == Severity.WARN and "tc" in r.field.lower()
        ]
        assert len(warns) >= 1
        errors = [r for r in results if r.severity == Severity.ERROR]
        assert len(errors) == 0  # tc absence must NOT be ERROR

    def test_cake_params_no_unknown_key_warnings(self):
        """cake_params paths must be in KNOWN_AUTORATE_PATHS -- no false positives."""
        data = self._make_config(
            transport="linux-cake",
            cake_params={
                "upload_interface": "enp8s0",
                "download_interface": "enp9s0",
                "overhead": "docsis",
                "memlimit": "32mb",
                "rtt": "100ms",
            },
        )
        # Add required fields so check_unknown_keys doesn't fail on other missing paths
        data["queues"] = {"download": "WAN-Download", "upload": "WAN-Upload"}
        data["continuous_monitoring"] = {"enabled": True}
        results = check_unknown_keys(data)
        unknown_cake = [
            r for r in results if r.severity == Severity.WARN and "cake_params" in r.field
        ]
        assert len(unknown_cake) == 0, f"Unexpected unknown key warnings: {unknown_cake}"
