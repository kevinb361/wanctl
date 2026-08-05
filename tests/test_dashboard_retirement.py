"""Regression coverage for the retired Textual dashboard surface."""

import importlib.util
import tomllib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_dashboard_package_and_console_entry_point_are_absent() -> None:
    """The unused dashboard cannot silently return through packaging drift."""
    project = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text())

    assert importlib.util.find_spec("wanctl.dashboard") is None
    assert "wanctl-dashboard" not in project["project"]["scripts"]
    assert "dashboard" not in project.get("project", {}).get("optional-dependencies", {})


def test_frozen_runtime_excludes_dashboard_only_dependencies() -> None:
    """Supported all-extras installs no longer carry Textual or HTTPX."""
    requirements = (REPO_ROOT / "requirements.txt").read_text().splitlines()
    package_names = {
        line.split("==", 1)[0].lower()
        for line in requirements
        if line and not line.startswith(("#", " ")) and "==" in line
    }

    assert package_names.isdisjoint({"textual", "httpx"})
