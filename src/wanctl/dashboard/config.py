"""Dashboard configuration loading.

Loads config from XDG-compliant YAML file with CLI override support.
Precedence: CLI args > config file > defaults.
"""

import argparse
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml

logger = logging.getLogger(__name__)

DEFAULTS: dict = {
    "autorate_url": "http://127.0.0.1:9101",
    "steering_url": "http://127.0.0.1:9102",
    "refresh_interval": 2,
}


@dataclass
class DashboardConfig:
    """Dashboard configuration."""

    autorate_url: str = DEFAULTS["autorate_url"]
    steering_url: str = DEFAULTS["steering_url"]
    refresh_interval: int | float = DEFAULTS["refresh_interval"]
    wan_rate_limits: dict[str, dict[str, float]] = field(default_factory=dict)


def get_config_dir() -> Path:
    """Return the config directory, respecting XDG_CONFIG_HOME."""
    xdg_config = os.environ.get("XDG_CONFIG_HOME")
    if xdg_config:
        return Path(xdg_config) / "wanctl"
    return Path.home() / ".config" / "wanctl"


def load_dashboard_config(path: Path | None = None) -> DashboardConfig:
    """Load dashboard config from YAML file, falling back to defaults.

    Args:
        path: Explicit path to config file. If None, uses XDG default location.

    Returns:
        DashboardConfig with merged values (file overrides defaults).
    """
    if path is None:
        path = get_config_dir() / "dashboard.yaml"

    data: dict = {}
    if path.exists():
        try:
            raw = path.read_text()
            parsed = yaml.safe_load(raw)
            if isinstance(parsed, dict):
                data = parsed
            else:
                logger.warning("Config file %s did not contain a mapping, using defaults", path)
        except yaml.YAMLError:
            logger.warning("Invalid YAML in %s, using defaults", path)

    return DashboardConfig(
        autorate_url=data.get("autorate_url", DEFAULTS["autorate_url"]),
        steering_url=data.get("steering_url", DEFAULTS["steering_url"]),
        refresh_interval=data.get("refresh_interval", DEFAULTS["refresh_interval"]),
        wan_rate_limits=data.get("wan_rate_limits", {}),
    )


def apply_cli_overrides(
    config: DashboardConfig, args: argparse.Namespace
) -> DashboardConfig:
    """Override config values with non-None CLI arguments.

    Args:
        config: Base configuration to override.
        args: Parsed CLI arguments (non-None values take precedence).

    Returns:
        New DashboardConfig with overrides applied.
    """
    return DashboardConfig(
        autorate_url=(
            args.autorate_url if getattr(args, "autorate_url", None) is not None
            else config.autorate_url
        ),
        steering_url=(
            args.steering_url if getattr(args, "steering_url", None) is not None
            else config.steering_url
        ),
        refresh_interval=(
            args.refresh_interval if getattr(args, "refresh_interval", None) is not None
            else config.refresh_interval
        ),
        wan_rate_limits=config.wan_rate_limits,
    )
