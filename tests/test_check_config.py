"""Comprehensive tests for wanctl-check-config CLI tool.

Covers all 7 phase requirements:
  CVAL-01: CLI validates config offline
  CVAL-04: All errors collected (not just first)
  CVAL-05: Cross-field semantic validation
  CVAL-06: File/permission checks
  CVAL-07: Env var resolution warnings
  CVAL-08: Deprecated parameter surfacing
  CVAL-11: Exit codes 0/1/2
"""

import sys

import yaml

from wanctl.check_config import (
    CheckResult,
    Severity,
    check_deprecated_params,
    check_env_vars,
    check_paths,
    check_unknown_keys,
    create_parser,
    format_results,
    main,
    validate_cross_fields,
    validate_schema_fields,
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
