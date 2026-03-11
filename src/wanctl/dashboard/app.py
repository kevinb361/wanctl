"""Dashboard CLI entry point and application shell.

Provides the wanctl-dashboard command and DashboardApp placeholder.
"""

import argparse
import sys

from wanctl.dashboard.config import apply_cli_overrides, load_dashboard_config


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments for wanctl-dashboard."""
    parser = argparse.ArgumentParser(
        prog="wanctl-dashboard",
        description="TUI dashboard for wanctl monitoring",
    )
    parser.add_argument(
        "--autorate-url",
        default=None,
        help="Autorate health endpoint URL (default: http://127.0.0.1:9101)",
    )
    parser.add_argument(
        "--steering-url",
        default=None,
        help="Steering health endpoint URL (default: http://127.0.0.1:9102)",
    )
    parser.add_argument(
        "--refresh-interval",
        type=float,
        default=None,
        help="Polling interval in seconds (default: 2)",
    )
    return parser.parse_args(argv)


class DashboardApp:
    """Dashboard application placeholder.

    Will be replaced with a Textual App subclass in Plan 03.
    """

    def __init__(self, config):
        self.config = config


def main(argv: list[str] | None = None) -> None:
    """Entry point for wanctl-dashboard CLI."""
    args = parse_args(argv)
    config = load_dashboard_config()
    config = apply_cli_overrides(config, args)
    print(f"Dashboard starting... (polling {config.autorate_url})")
    sys.exit(0)
