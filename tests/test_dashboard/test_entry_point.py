"""Tests for dashboard entry point and pyproject.toml correctness."""

from pathlib import Path

import tomllib


class TestEntryPoint:
    """Verify the wanctl-dashboard entry point is importable and configured."""

    def test_main_is_importable(self):
        """wanctl.dashboard.app.main is importable."""
        from wanctl.dashboard.app import main

        assert callable(main)

    def test_dashboard_app_is_importable(self):
        """wanctl.dashboard.app.DashboardApp is importable."""
        from wanctl.dashboard.app import DashboardApp

        assert DashboardApp is not None


class TestPyprojectToml:
    """Verify pyproject.toml has correct dashboard configuration."""

    @staticmethod
    def _load_pyproject() -> dict:
        pyproject_path = Path(__file__).resolve().parents[2] / "pyproject.toml"
        with open(pyproject_path, "rb") as f:
            return tomllib.load(f)

    def test_has_wanctl_dashboard_entry_point(self):
        """pyproject.toml has wanctl-dashboard entry point."""
        data = self._load_pyproject()
        scripts = data.get("project", {}).get("scripts", {})
        assert "wanctl-dashboard" in scripts
        assert scripts["wanctl-dashboard"] == "wanctl.dashboard.app:main"

    def test_has_dashboard_optional_dependency_group(self):
        """pyproject.toml has dashboard optional dependency group with textual and httpx."""
        data = self._load_pyproject()
        optional_deps = data.get("project", {}).get("optional-dependencies", {})
        assert "dashboard" in optional_deps
        dashboard_deps = optional_deps["dashboard"]
        dep_names = [d.split(">=")[0].split("[")[0].strip().lower() for d in dashboard_deps]
        assert "textual" in dep_names
        assert "httpx" in dep_names
