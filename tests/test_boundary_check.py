"""Tests for the AST-based cross-module private attribute access checker.

Validates that scripts/check_private_access.py correctly detects cross-module
private attribute accesses while ignoring legitimate patterns (self._, cls._,
__dunder__).
"""

import subprocess
import textwrap
from pathlib import Path

import pytest


def _write_snippet(tmp_path: Path, filename: str, code: str) -> Path:
    """Write a Python snippet to a temp file and return its path."""
    filepath = tmp_path / filename
    filepath.write_text(textwrap.dedent(code))
    return filepath


# Import the check_file function from the script
@pytest.fixture
def check_file():
    """Import check_file from the boundary check script."""
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "check_private_access",
        Path("scripts/check_private_access.py"),
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.check_file


class TestPrivateAccessDetection:
    """Test detection of cross-module private attribute access."""

    def test_detects_private_attr_access(self, tmp_path, check_file):
        """Script detects obj._private_attr access (should report violation)."""
        filepath = _write_snippet(
            tmp_path,
            "example.py",
            """\
            obj = get_something()
            val = obj._private_attr
            """,
        )
        violations = check_file(filepath)
        assert len(violations) >= 1
        assert any("_private_attr" in v for v in violations)

    def test_ignores_self_private_access(self, tmp_path, check_file):
        """Script ignores self._private_attr (same-class access is fine)."""
        filepath = _write_snippet(
            tmp_path,
            "example.py",
            """\
            class Foo:
                def method(self):
                    return self._internal_state
            """,
        )
        violations = check_file(filepath)
        assert len(violations) == 0

    def test_ignores_cls_private_access(self, tmp_path, check_file):
        """Script ignores cls._private_attr (classmethod access is fine)."""
        filepath = _write_snippet(
            tmp_path,
            "example.py",
            """\
            class Foo:
                _counter = 0

                @classmethod
                def create(cls):
                    cls._counter += 1
                    return cls()
            """,
        )
        violations = check_file(filepath)
        assert len(violations) == 0

    def test_ignores_dunder_access(self, tmp_path, check_file):
        """Script ignores obj.__dunder__ (dunder methods are public)."""
        filepath = _write_snippet(
            tmp_path,
            "example.py",
            """\
            obj = get_something()
            name = obj.__class__
            rep = obj.__repr__()
            """,
        )
        violations = check_file(filepath)
        assert len(violations) == 0

    def test_reports_correct_filename_and_line(self, tmp_path, check_file):
        """Script reports correct filename and line number for violations."""
        filepath = _write_snippet(
            tmp_path,
            "target.py",
            """\
            x = 1
            y = 2
            result = something._hidden_value
            """,
        )
        violations = check_file(filepath)
        assert len(violations) == 1
        # Should contain the filename and line 3
        assert "target.py" in violations[0]
        assert ":3:" in violations[0]


class TestExitCodes:
    """Test exit code behavior of the script."""

    def test_exit_zero_when_all_allowlisted(self):
        """Script returns exit code 0 when no violations beyond allowlist."""
        result = subprocess.run(
            [
                ".venv/bin/python",
                "scripts/check_private_access.py",
                "src/wanctl/",
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, f"STDOUT: {result.stdout}\nSTDERR: {result.stderr}"

    def test_exit_one_when_new_violations(self, tmp_path, check_file):
        """Script returns exit code 1 when violations found outside allowlist.

        We test this by creating a temp dir with a file that has a violation
        and running the script against it -- none of those will be allowlisted.
        """
        subdir = tmp_path / "pkg"
        subdir.mkdir()
        _write_snippet(
            subdir,
            "violator.py",
            """\
            obj = get_something()
            val = obj._secret_thing
            """,
        )
        result = subprocess.run(
            [
                ".venv/bin/python",
                "scripts/check_private_access.py",
                str(subdir),
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 1, f"STDOUT: {result.stdout}\nSTDERR: {result.stderr}"


class TestSummaryOutput:
    """Test summary output formatting."""

    def test_summary_shows_counts(self):
        """Script prints summary with violation counts."""
        result = subprocess.run(
            [
                ".venv/bin/python",
                "scripts/check_private_access.py",
                "src/wanctl/",
            ],
            capture_output=True,
            text=True,
        )
        # Should contain a summary line with counts
        assert "violations" in result.stdout.lower() or "violation" in result.stdout.lower()
