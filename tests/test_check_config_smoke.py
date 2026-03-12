"""Smoke tests for check_config module -- TDD RED phase.

Verify that the module exports all required types and functions,
and that basic validation works without triggering daemon code.
"""

from wanctl.check_config import (
    KNOWN_AUTORATE_PATHS,
    CheckResult,
    Severity,
    create_parser,
)


class TestExports:
    """Verify module exports are available."""

    def test_severity_enum_values(self):
        assert Severity.PASS.value == "pass"
        assert Severity.WARN.value == "warn"
        assert Severity.ERROR.value == "error"

    def test_check_result_dataclass(self):
        r = CheckResult("cat", "field", Severity.PASS, "ok")
        assert r.category == "cat"
        assert r.field == "field"
        assert r.severity == Severity.PASS
        assert r.message == "ok"
        assert r.suggestion is None

    def test_check_result_with_suggestion(self):
        r = CheckResult("cat", "field", Severity.WARN, "msg", suggestion="do this")
        assert r.suggestion == "do this"

    def test_known_paths_coverage(self):
        """KNOWN_AUTORATE_PATHS must cover at least 50 valid config paths."""
        assert len(KNOWN_AUTORATE_PATHS) >= 50

    def test_create_parser_returns_parser(self):
        parser = create_parser()
        assert parser.prog == "wanctl-check-config"

    def test_known_paths_includes_schema_paths(self):
        """Paths from BASE_SCHEMA and Config.SCHEMA must be in KNOWN_AUTORATE_PATHS."""
        for required in [
            "wan_name",
            "router.host",
            "queues.download",
            "continuous_monitoring.download.ceiling_mbps",
            "continuous_monitoring.thresholds.target_bloat_ms",
        ]:
            assert required in KNOWN_AUTORATE_PATHS, f"Missing: {required}"

    def test_known_paths_includes_imperative_paths(self):
        """Imperatively-loaded paths must also be in KNOWN_AUTORATE_PATHS."""
        for required in [
            "router.transport",
            "router.password",
            "state_file",
            "timeouts.ssh_command",
            "continuous_monitoring.use_median_of_three",
        ]:
            assert required in KNOWN_AUTORATE_PATHS, f"Missing: {required}"
