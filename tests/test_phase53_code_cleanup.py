"""Nyquist validation tests for Phase 53: Code Cleanup.

Behavioral tests verifying requirements CLEAN-01 through CLEAN-07.
These tests verify the observable behavioral changes from the phase,
not the structural details of the implementation.

Requirements covered:
  CLEAN-01: self.ssh renamed to self.client in RouterOS/RouterOSBackend
  CLEAN-02: No stale "2-second" timing references in src/wanctl/
  CLEAN-03: No function-scoped import time as time_module in src/wanctl/
  CLEAN-05: InsecureRequestWarning suppression scoped to verify_ssl=False
  CLEAN-06: ruff check src/ passes with zero violations
  CLEAN-07: validate_config_mode() is a standalone callable function
"""

import ast
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Project src root
SRC_ROOT = Path(__file__).parent.parent / "src" / "wanctl"


# =============================================================================
# CLEAN-01: self.ssh renamed to self.client
# =============================================================================


class TestClean01SelfSshRenamedToClient:
    """CLEAN-01: RouterOS and RouterOSBackend use self.client, not self.ssh."""

    def test_routeros_class_uses_client_attribute(self):
        """RouterOS.__init__ assigns self.client from get_router_client_with_failover."""
        source = (SRC_ROOT / "autorate_continuous.py").read_text()
        tree = ast.parse(source)

        # Find the RouterOS class and check __init__ assigns self.client
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name == "RouterOS":
                init_method = next(
                    (n for n in node.body if isinstance(n, ast.FunctionDef) and n.name == "__init__"),
                    None,
                )
                assert init_method is not None, "RouterOS.__init__ not found"
                # Check that self.client is assigned
                assigns = [
                    n
                    for n in ast.walk(init_method)
                    if isinstance(n, ast.Assign)
                    and any(
                        isinstance(t, ast.Attribute) and t.attr == "client"
                        for t in n.targets
                    )
                ]
                assert len(assigns) > 0, "self.client assignment not found in RouterOS.__init__"
                # Check that self.ssh is NOT assigned
                ssh_assigns = [
                    n
                    for n in ast.walk(init_method)
                    if isinstance(n, ast.Assign)
                    and any(
                        isinstance(t, ast.Attribute) and t.attr == "ssh"
                        for t in n.targets
                    )
                ]
                assert len(ssh_assigns) == 0, "self.ssh still assigned in RouterOS.__init__"
                break
        else:
            pytest.fail("RouterOS class not found in autorate_continuous.py")

    def test_routeros_backend_uses_client_attribute(self):
        """RouterOSBackend.__init__ assigns self.client, not self.ssh."""
        source = (SRC_ROOT / "backends" / "routeros.py").read_text()
        tree = ast.parse(source)

        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name == "RouterOSBackend":
                init_method = next(
                    (n for n in node.body if isinstance(n, ast.FunctionDef) and n.name == "__init__"),
                    None,
                )
                assert init_method is not None, "RouterOSBackend.__init__ not found"
                assigns = [
                    n
                    for n in ast.walk(init_method)
                    if isinstance(n, ast.Assign)
                    and any(
                        isinstance(t, ast.Attribute) and t.attr == "client"
                        for t in n.targets
                    )
                ]
                assert len(assigns) > 0, "self.client assignment not found in RouterOSBackend.__init__"
                ssh_assigns = [
                    n
                    for n in ast.walk(init_method)
                    if isinstance(n, ast.Assign)
                    and any(
                        isinstance(t, ast.Attribute) and t.attr == "ssh"
                        for t in n.targets
                    )
                ]
                assert len(ssh_assigns) == 0, "self.ssh still assigned in RouterOSBackend.__init__"
                break
        else:
            pytest.fail("RouterOSBackend class not found in backends/routeros.py")

    def test_no_self_dot_ssh_attribute_in_src(self):
        """No self.ssh attribute access anywhere in src/wanctl/ (self.ssh_key is fine)."""
        import re

        for py_file in SRC_ROOT.rglob("*.py"):
            content = py_file.read_text()
            # Match self.ssh but NOT self.ssh_key or self.ssh_*
            matches = re.findall(r"self\.ssh(?!_)\b", content)
            assert len(matches) == 0, (
                f"Found self.ssh in {py_file.relative_to(SRC_ROOT.parent.parent)}: "
                f"{len(matches)} occurrence(s)"
            )


# =============================================================================
# CLEAN-02: No stale "2-second" timing references
# =============================================================================


class TestClean02StaleDocstringsRemoved:
    """CLEAN-02: No docstring or comment references "2-second" control loop timing."""

    def test_no_two_second_references_in_source(self):
        """Source files do not reference outdated '2-second' or '2 second' timing."""
        import re

        pattern = re.compile(r"2[\s-]second", re.IGNORECASE)
        violations = []
        for py_file in SRC_ROOT.rglob("*.py"):
            content = py_file.read_text()
            for i, line in enumerate(content.splitlines(), 1):
                if pattern.search(line):
                    rel = py_file.relative_to(SRC_ROOT.parent.parent)
                    violations.append(f"  {rel}:{i}: {line.strip()}")

        assert len(violations) == 0, (
            "Stale '2-second' timing references found:\n" + "\n".join(violations)
        )


# =============================================================================
# CLEAN-03: No function-scoped import time as time_module
# =============================================================================


class TestClean03NoHotLoopImportAlias:
    """CLEAN-03: No function-scoped 'import time as time_module' anywhere in src/."""

    def test_no_import_time_as_time_module(self):
        """No file in src/wanctl/ contains 'import time as time_module'."""
        violations = []
        for py_file in SRC_ROOT.rglob("*.py"):
            content = py_file.read_text()
            for i, line in enumerate(content.splitlines(), 1):
                if "import time as time_module" in line:
                    rel = py_file.relative_to(SRC_ROOT.parent.parent)
                    violations.append(f"  {rel}:{i}: {line.strip()}")

        assert len(violations) == 0, (
            "Function-scoped time alias found:\n" + "\n".join(violations)
        )


# =============================================================================
# CLEAN-05: InsecureRequestWarning scoped to verify_ssl=False
# =============================================================================


class TestClean05WarningScopedToSession:
    """CLEAN-05: InsecureRequestWarning suppression only fires when verify_ssl=False."""

    def test_disable_warnings_not_called_when_verify_ssl_true(self):
        """Creating a REST client with verify_ssl=True does NOT call disable_warnings."""
        with (
            patch("wanctl.routeros_rest.requests.Session") as mock_session_cls,
            patch("wanctl.routeros_rest.urllib3", create=True) as mock_urllib3,
        ):
            mock_session_cls.return_value = MagicMock()
            from wanctl.routeros_rest import RouterOSREST

            RouterOSREST(
                host="192.168.1.1",
                user="admin",
                password="test",  # pragma: allowlist secret
                verify_ssl=True,
            )
            mock_urllib3.disable_warnings.assert_not_called()

    def test_disable_warnings_not_called_when_verify_ssl_false(self):
        """Creating a REST client with verify_ssl=False does NOT call disable_warnings.

        SECR-02: SSL warning suppression is now per-request via warnings.catch_warnings,
        not process-wide via urllib3.disable_warnings.
        """
        with patch("wanctl.routeros_rest.requests.Session") as mock_session_cls:
            mock_session_cls.return_value = MagicMock()
            from wanctl.routeros_rest import RouterOSREST

            with patch("urllib3.disable_warnings") as mock_disable:
                client = RouterOSREST(
                    host="192.168.1.1",
                    user="admin",
                    password="test",  # pragma: allowlist secret
                    verify_ssl=False,
                )
                mock_disable.assert_not_called()
                # Instead, _suppress_ssl_warnings flag is set for per-request suppression
                assert client._suppress_ssl_warnings is True

    def test_no_module_level_disable_warnings_call(self):
        """The routeros_rest.py module has no top-level disable_warnings call."""
        source = (SRC_ROOT / "routeros_rest.py").read_text()
        tree = ast.parse(source)

        # Check module-level statements only (not inside class/function bodies)
        for node in tree.body:
            if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
                func = node.value.func
                func_name = ""
                if isinstance(func, ast.Attribute):
                    func_name = func.attr
                elif isinstance(func, ast.Name):
                    func_name = func.id
                assert func_name != "disable_warnings", (
                    "Found module-level disable_warnings() call -- should be inside __init__"
                )


# =============================================================================
# CLEAN-06: ruff check passes
# =============================================================================


class TestClean06RuffViolations:
    """CLEAN-06: ruff check src/ reports zero violations."""

    def test_ruff_check_passes(self):
        """Running ruff check src/ produces no violations."""
        project_root = SRC_ROOT.parent.parent
        result = subprocess.run(
            [sys.executable, "-m", "ruff", "check", str(project_root / "src")],
            capture_output=True,
            text=True,
            cwd=str(project_root),
        )
        assert result.returncode == 0, (
            f"ruff check failed with {result.returncode}:\n{result.stdout}\n{result.stderr}"
        )


# =============================================================================
# CLEAN-07: validate_config_mode() extracted as standalone function
# =============================================================================


class TestClean07ValidateConfigModeExtracted:
    """CLEAN-07: validate_config_mode() is a standalone function callable directly."""

    def test_validate_config_mode_is_importable(self):
        """validate_config_mode can be imported directly from autorate_continuous."""
        from wanctl.autorate_continuous import validate_config_mode

        assert callable(validate_config_mode)

    def test_validate_config_mode_returns_zero_for_valid_config(self, tmp_path):
        """Calling validate_config_mode() directly with a valid config returns 0."""
        config_yaml = """
wan_name: TestWAN
router:
  host: "192.168.1.1"
  user: "admin"
  ssh_key: "/tmp/test_id_rsa"
  transport: "ssh"

queues:
  download: "cake-download"
  upload: "cake-upload"

continuous_monitoring:
  enabled: true
  baseline_rtt_initial: 25.0
  ping_hosts:
    - "1.1.1.1"
    - "8.8.8.8"
  download:
    floor_green_mbps: 800
    floor_yellow_mbps: 600
    floor_soft_red_mbps: 500
    floor_red_mbps: 400
    ceiling_mbps: 920
    step_up_mbps: 10
    factor_down: 0.85
  upload:
    floor_green_mbps: 35
    floor_yellow_mbps: 30
    floor_red_mbps: 25
    ceiling_mbps: 40
    step_up_mbps: 1
    factor_down: 0.85
  thresholds:
    target_bloat_ms: 15
    warn_bloat_ms: 45
    baseline_time_constant_sec: 60
    load_time_constant_sec: 0.5

logging:
  main_log: "/tmp/test_autorate.log"
  debug_log: "/tmp/test_autorate_debug.log"

lock_file: "/tmp/test_autorate.lock"
lock_timeout: 300
"""
        config_file = tmp_path / "valid.yaml"
        config_file.write_text(config_yaml)

        from wanctl.autorate_continuous import validate_config_mode

        result = validate_config_mode([str(config_file)])
        assert result == 0

    def test_validate_config_mode_returns_one_for_invalid_config(self, tmp_path):
        """Calling validate_config_mode() directly with invalid config returns 1."""
        invalid_yaml = """
wan_name: TestWAN
# Missing router, queues, continuous_monitoring
logging:
  main_log: "/tmp/test.log"
  debug_log: "/tmp/test_debug.log"
lock_file: "/tmp/test.lock"
lock_timeout: 300
"""
        config_file = tmp_path / "invalid.yaml"
        config_file.write_text(invalid_yaml)

        from wanctl.autorate_continuous import validate_config_mode

        result = validate_config_mode([str(config_file)])
        assert result == 1

    def test_validate_config_mode_mixed_valid_and_invalid(self, tmp_path):
        """Mixed valid/invalid configs: returns 1 when any config is invalid."""
        valid_yaml = """
wan_name: TestWAN
router:
  host: "192.168.1.1"
  user: "admin"
  ssh_key: "/tmp/test_id_rsa"
  transport: "ssh"

queues:
  download: "cake-download"
  upload: "cake-upload"

continuous_monitoring:
  enabled: true
  baseline_rtt_initial: 25.0
  ping_hosts:
    - "1.1.1.1"
    - "8.8.8.8"
  download:
    floor_green_mbps: 800
    floor_yellow_mbps: 600
    floor_soft_red_mbps: 500
    floor_red_mbps: 400
    ceiling_mbps: 920
    step_up_mbps: 10
    factor_down: 0.85
  upload:
    floor_green_mbps: 35
    floor_yellow_mbps: 30
    floor_red_mbps: 25
    ceiling_mbps: 40
    step_up_mbps: 1
    factor_down: 0.85
  thresholds:
    target_bloat_ms: 15
    warn_bloat_ms: 45
    baseline_time_constant_sec: 60
    load_time_constant_sec: 0.5

logging:
  main_log: "/tmp/test_autorate.log"
  debug_log: "/tmp/test_autorate_debug.log"

lock_file: "/tmp/test_autorate.lock"
lock_timeout: 300
"""
        invalid_yaml = """
wan_name: BadConfig
logging:
  main_log: "/tmp/test.log"
  debug_log: "/tmp/test_debug.log"
lock_file: "/tmp/test.lock"
lock_timeout: 300
"""
        valid_file = tmp_path / "valid.yaml"
        invalid_file = tmp_path / "invalid.yaml"
        valid_file.write_text(valid_yaml)
        invalid_file.write_text(invalid_yaml)

        from wanctl.autorate_continuous import validate_config_mode

        result = validate_config_mode([str(valid_file), str(invalid_file)])
        assert result == 1

    def test_validate_config_mode_prints_wan_details(self, tmp_path, capsys):
        """validate_config_mode() prints WAN name, transport, and floor details."""
        config_yaml = """
wan_name: TestWAN
router:
  host: "192.168.1.1"
  user: "admin"
  ssh_key: "/tmp/test_id_rsa"
  transport: "ssh"

queues:
  download: "cake-download"
  upload: "cake-upload"

continuous_monitoring:
  enabled: true
  baseline_rtt_initial: 25.0
  ping_hosts:
    - "1.1.1.1"
    - "8.8.8.8"
  download:
    floor_green_mbps: 800
    floor_yellow_mbps: 600
    floor_soft_red_mbps: 500
    floor_red_mbps: 400
    ceiling_mbps: 920
    step_up_mbps: 10
    factor_down: 0.85
  upload:
    floor_green_mbps: 35
    floor_yellow_mbps: 30
    floor_red_mbps: 25
    ceiling_mbps: 40
    step_up_mbps: 1
    factor_down: 0.85
  thresholds:
    target_bloat_ms: 15
    warn_bloat_ms: 45
    baseline_time_constant_sec: 60
    load_time_constant_sec: 0.5

logging:
  main_log: "/tmp/test_autorate.log"
  debug_log: "/tmp/test_autorate_debug.log"

lock_file: "/tmp/test_autorate.lock"
lock_timeout: 300
"""
        config_file = tmp_path / "valid.yaml"
        config_file.write_text(config_yaml)

        from wanctl.autorate_continuous import validate_config_mode

        validate_config_mode([str(config_file)])

        captured = capsys.readouterr()
        assert "WAN: TestWAN" in captured.out
        assert "Transport: ssh" in captured.out
        assert "Floors:" in captured.out
        assert "GREEN=" in captured.out
