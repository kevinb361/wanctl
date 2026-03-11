"""Tests for dashboard config loading."""

import argparse
from pathlib import Path

import yaml

from wanctl.dashboard.config import (
    DEFAULTS,
    DashboardConfig,
    apply_cli_overrides,
    get_config_dir,
    load_dashboard_config,
)


class TestDefaults:
    """Verify default values are sane."""

    def test_defaults_has_autorate_url(self):
        assert DEFAULTS["autorate_url"] == "http://127.0.0.1:9101"

    def test_defaults_has_steering_url(self):
        assert DEFAULTS["steering_url"] == "http://127.0.0.1:9102"

    def test_defaults_has_refresh_interval(self):
        assert DEFAULTS["refresh_interval"] == 2

    def test_defaults_has_secondary_autorate_url(self):
        assert DEFAULTS["secondary_autorate_url"] == ""


class TestLoadDashboardConfig:
    """Test config loading from YAML with defaults fallback."""

    def test_returns_defaults_when_no_config_file(self, tmp_path):
        """load_dashboard_config() returns defaults when no config file exists."""
        nonexistent = tmp_path / "nonexistent" / "dashboard.yaml"
        config = load_dashboard_config(nonexistent)
        assert config.autorate_url == "http://127.0.0.1:9101"
        assert config.steering_url == "http://127.0.0.1:9102"
        assert config.refresh_interval == 2

    def test_loads_urls_from_yaml(self, tmp_config_dir):
        """load_dashboard_config(path) loads autorate_url, steering_url from YAML."""
        config_file = tmp_config_dir / "dashboard.yaml"
        config_file.write_text(
            yaml.dump(
                {
                    "autorate_url": "http://10.0.0.1:9101",
                    "steering_url": "http://10.0.0.1:9102",
                    "refresh_interval": 5,
                }
            )
        )
        config = load_dashboard_config(config_file)
        assert config.autorate_url == "http://10.0.0.1:9101"
        assert config.steering_url == "http://10.0.0.1:9102"
        assert config.refresh_interval == 5

    def test_config_file_overrides_defaults(self, tmp_config_dir):
        """Config file overrides defaults (autorate_url changed in YAML)."""
        config_file = tmp_config_dir / "dashboard.yaml"
        config_file.write_text(yaml.dump({"autorate_url": "http://192.168.1.100:9101"}))
        config = load_dashboard_config(config_file)
        assert config.autorate_url == "http://192.168.1.100:9101"
        # Other fields remain defaults
        assert config.steering_url == "http://127.0.0.1:9102"
        assert config.refresh_interval == 2

    def test_invalid_yaml_returns_defaults(self, tmp_config_dir):
        """Invalid YAML returns defaults with no crash."""
        config_file = tmp_config_dir / "dashboard.yaml"
        config_file.write_text(":::invalid yaml{{{")
        config = load_dashboard_config(config_file)
        assert config.autorate_url == "http://127.0.0.1:9101"
        assert config.steering_url == "http://127.0.0.1:9102"
        assert config.refresh_interval == 2

    def test_missing_keys_fall_back_to_defaults(self, tmp_config_dir):
        """Missing keys in YAML fall back to defaults for those keys."""
        config_file = tmp_config_dir / "dashboard.yaml"
        config_file.write_text(yaml.dump({"refresh_interval": 10}))
        config = load_dashboard_config(config_file)
        assert config.autorate_url == "http://127.0.0.1:9101"
        assert config.steering_url == "http://127.0.0.1:9102"
        assert config.refresh_interval == 10

    def test_wan_rate_limits_loaded_from_yaml(self, tmp_config_dir):
        """wan_rate_limits loaded from YAML (e.g., spectrum: {dl_mbps: 300, ul_mbps: 12})."""
        config_file = tmp_config_dir / "dashboard.yaml"
        config_file.write_text(
            yaml.dump(
                {
                    "wan_rate_limits": {
                        "spectrum": {"dl_mbps": 300, "ul_mbps": 12},
                        "att": {"dl_mbps": 100, "ul_mbps": 20},
                    }
                }
            )
        )
        config = load_dashboard_config(config_file)
        assert config.wan_rate_limits == {
            "spectrum": {"dl_mbps": 300, "ul_mbps": 12},
            "att": {"dl_mbps": 100, "ul_mbps": 20},
        }

    def test_secondary_autorate_url_defaults_to_empty(self, tmp_path):
        """secondary_autorate_url defaults to empty string when not in config."""
        nonexistent = tmp_path / "nonexistent" / "dashboard.yaml"
        config = load_dashboard_config(nonexistent)
        assert config.secondary_autorate_url == ""

    def test_secondary_autorate_url_loaded_from_yaml(self, tmp_config_dir):
        """secondary_autorate_url loaded from YAML config."""
        config_file = tmp_config_dir / "dashboard.yaml"
        config_file.write_text(
            yaml.dump({"secondary_autorate_url": "http://10.0.0.2:9101"})
        )
        config = load_dashboard_config(config_file)
        assert config.secondary_autorate_url == "http://10.0.0.2:9101"

    def test_wan_rate_limits_defaults_to_empty_dict(self, tmp_path):
        """wan_rate_limits defaults to empty dict when not in config."""
        nonexistent = tmp_path / "nonexistent" / "dashboard.yaml"
        config = load_dashboard_config(nonexistent)
        assert config.wan_rate_limits == {}


class TestXdgConfigHome:
    """Test XDG_CONFIG_HOME environment variable support."""

    def test_xdg_config_home_changes_config_path(self, tmp_path, monkeypatch):
        """XDG_CONFIG_HOME env var changes config search path."""
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
        config_dir = get_config_dir()
        assert config_dir == tmp_path / "wanctl"

    def test_default_config_dir_without_xdg(self, monkeypatch):
        """Without XDG_CONFIG_HOME, falls back to ~/.config/wanctl."""
        monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
        config_dir = get_config_dir()
        assert config_dir == Path.home() / ".config" / "wanctl"


class TestCliOverrides:
    """Test CLI argument overrides on config."""

    def test_cli_args_override_config_values(self, tmp_config_dir):
        """CLI args override config file values (simulate argparse namespace with non-None)."""
        config_file = tmp_config_dir / "dashboard.yaml"
        config_file.write_text(
            yaml.dump(
                {
                    "autorate_url": "http://10.0.0.1:9101",
                    "steering_url": "http://10.0.0.1:9102",
                    "refresh_interval": 5,
                }
            )
        )
        config = load_dashboard_config(config_file)
        args = argparse.Namespace(
            autorate_url="http://override:9101",
            steering_url=None,
            refresh_interval=1,
        )
        result = apply_cli_overrides(config, args)
        assert result.autorate_url == "http://override:9101"
        assert result.steering_url == "http://10.0.0.1:9102"  # Not overridden
        assert result.refresh_interval == 1

    def test_cli_secondary_autorate_url_overrides_config(self):
        """CLI --secondary-autorate-url overrides config value."""
        config = DashboardConfig(secondary_autorate_url="http://from-config:9101")
        args = argparse.Namespace(
            autorate_url=None,
            steering_url=None,
            refresh_interval=None,
            secondary_autorate_url="http://override:9101",
        )
        result = apply_cli_overrides(config, args)
        assert result.secondary_autorate_url == "http://override:9101"

    def test_cli_none_secondary_autorate_url_does_not_override(self):
        """CLI None secondary_autorate_url does not override config value."""
        config = DashboardConfig(secondary_autorate_url="http://from-config:9101")
        args = argparse.Namespace(
            autorate_url=None,
            steering_url=None,
            refresh_interval=None,
            secondary_autorate_url=None,
        )
        result = apply_cli_overrides(config, args)
        assert result.secondary_autorate_url == "http://from-config:9101"

    def test_cli_none_values_do_not_override(self):
        """CLI args with None values do not override config."""
        config = DashboardConfig(
            autorate_url="http://10.0.0.1:9101",
            steering_url="http://10.0.0.1:9102",
            refresh_interval=5,
        )
        args = argparse.Namespace(
            autorate_url=None,
            steering_url=None,
            refresh_interval=None,
            secondary_autorate_url=None,
        )
        result = apply_cli_overrides(config, args)
        assert result.autorate_url == "http://10.0.0.1:9101"
        assert result.steering_url == "http://10.0.0.1:9102"
        assert result.refresh_interval == 5
