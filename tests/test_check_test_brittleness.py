"""Tests for scripts/check_test_brittleness.py -- cross-module private patch detection in tests."""

import subprocess
import sys
import textwrap
from pathlib import Path

import pytest


@pytest.fixture
def test_dir(tmp_path: Path) -> Path:
    """Create a temporary test directory for scanning."""
    return tmp_path / "tests"


def _write_test_file(test_dir: Path, filename: str, content: str) -> Path:
    """Helper to write a test file with given content."""
    test_dir.mkdir(parents=True, exist_ok=True)
    filepath = test_dir / filename
    filepath.write_text(textwrap.dedent(content))
    return filepath


class TestCrossModulePatchDetection:
    """Test detection of cross-module private patches in test files."""

    def test_detects_cross_module_string_patch(self, test_dir: Path) -> None:
        """Script detects patch('wanctl.other_module._func') as cross-module."""
        _write_test_file(
            test_dir,
            "test_foo.py",
            '''\
            from unittest.mock import patch

            def test_example():
                with patch("wanctl.bar._private_func"):
                    pass
            ''',
        )

        from scripts.check_test_brittleness import scan_file

        count = scan_file(test_dir / "test_foo.py")
        assert count > 0, "Should detect cross-module private patch"

    def test_ignores_same_module_string_patch(self, test_dir: Path) -> None:
        """Script does NOT count same-module patches (test_foo.py patching wanctl.foo._func)."""
        _write_test_file(
            test_dir,
            "test_foo.py",
            '''\
            from unittest.mock import patch

            def test_example():
                with patch("wanctl.foo._private_func"):
                    pass
            ''',
        )

        from scripts.check_test_brittleness import scan_file

        count = scan_file(test_dir / "test_foo.py")
        assert count == 0, "Same-module patches should not be counted"

    def test_ignores_same_module_patch_object(self, test_dir: Path) -> None:
        """Script does NOT count patch.object(self_instance, '_method') for same-module."""
        _write_test_file(
            test_dir,
            "test_foo.py",
            '''\
            from unittest.mock import patch, MagicMock

            def test_example():
                obj = MagicMock()
                with patch.object(obj, "_method"):
                    pass
            ''',
        )

        from scripts.check_test_brittleness import scan_file

        count = scan_file(test_dir / "test_foo.py")
        assert count == 0, "patch.object with instance should not be counted"

    def test_detects_cross_module_patch_object(self, test_dir: Path) -> None:
        """Script counts patch.object(imported_obj, '_method') from different module."""
        _write_test_file(
            test_dir,
            "test_foo.py",
            '''\
            from unittest.mock import patch

            def test_example():
                with patch("wanctl.bar._helper"):
                    pass
                with patch("wanctl.baz._other"):
                    pass
            ''',
        )

        from scripts.check_test_brittleness import scan_file

        count = scan_file(test_dir / "test_foo.py")
        assert count == 2, "Should count each cross-module private patch"


class TestThresholdExitCodes:
    """Test exit code behavior based on threshold."""

    def test_exits_0_when_under_threshold(self, test_dir: Path) -> None:
        """Script exits 0 when all files have <= threshold cross-module patches."""
        _write_test_file(
            test_dir,
            "test_foo.py",
            '''\
            from unittest.mock import patch

            def test_example():
                with patch("wanctl.foo._private_func"):
                    pass
            ''',
        )

        from scripts.check_test_brittleness import scan_directory

        _total, files_over, exit_code = scan_directory(test_dir, threshold=3)
        assert exit_code == 0

    def test_exits_1_when_over_threshold(self, test_dir: Path) -> None:
        """Script exits 1 when any file exceeds threshold."""
        _write_test_file(
            test_dir,
            "test_foo.py",
            '''\
            from unittest.mock import patch

            def test_a():
                with patch("wanctl.bar._f1"):
                    pass
            def test_b():
                with patch("wanctl.bar._f2"):
                    pass
            def test_c():
                with patch("wanctl.bar._f3"):
                    pass
            def test_d():
                with patch("wanctl.bar._f4"):
                    pass
            ''',
        )

        from scripts.check_test_brittleness import scan_directory

        _total, files_over, exit_code = scan_directory(test_dir, threshold=3)
        assert exit_code == 1, "Should fail when file has >3 cross-module patches"


class TestConftestExemption:
    """Test that conftest.py files are exempt."""

    def test_conftest_exempt(self, test_dir: Path) -> None:
        """conftest.py files are exempt from the check."""
        _write_test_file(
            test_dir,
            "conftest.py",
            '''\
            from unittest.mock import patch

            def fixture():
                with patch("wanctl.bar._private_func"):
                    pass
            ''',
        )

        from scripts.check_test_brittleness import scan_file

        count = scan_file(test_dir / "conftest.py")
        assert count == 0, "conftest.py should be exempt"
