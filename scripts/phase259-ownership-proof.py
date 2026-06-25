#!/usr/bin/env python3
"""Phase 259 live read-only ownership inspection proof harness."""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import Protocol

DEPLOYED_ROOT = Path("/opt/wanctl").resolve()
if DEPLOYED_ROOT.exists():
    sys.path.insert(0, str(DEPLOYED_ROOT.parent))

import wanctl  # noqa: E402
from wanctl.readonly_validator import iter_commands, validate_command  # noqa: E402
from wanctl.router_client import get_router_client  # noqa: E402
from wanctl.steering.daemon import SteeringConfig  # noqa: E402
from wanctl.steering.route_manager import RouteManager  # noqa: E402
from wanctl.steering.route_ownership_inspector import (  # noqa: E402
    ROUTE_PRINT,
    RouteOwnershipInspector,
)

DEFAULT_CONFIG = Path("/etc/wanctl/steering.yaml")
STATIC_READ_COMMANDS = (
    "/tool netwatch print detail",
    "/system script print detail",
    ROUTE_PRINT,
)


class RouterClientLike(Protocol):
    def run_cmd(
        self, cmd: str, capture: bool = False, timeout: int | None = None
    ) -> tuple[int, str, str]: ...

    def close(self) -> None: ...


class RouteManagerLike(Protocol):
    def status_snapshot(self) -> dict[str, object]: ...


def validate_commands_before_run(
    client: RouterClientLike, commands: list[str] | tuple[str, ...]
) -> None:
    """Validate commands before any client.run_cmd can be reached."""
    _ = client
    for command in commands:
        validate_command(command)


def run_proof(client: RouterClientLike, route_manager: RouteManagerLike) -> tuple[int, str]:
    validate_commands_before_run(client, STATIC_READ_COMMANDS)
    inspector = RouteOwnershipInspector(
        router_client=client,
        route_manager=route_manager,
        interval_sec=60.0,
    )
    inspector.refresh()
    snap = inspector.snapshot()
    if snap["inspector_status"] == "error":
        return 1, f"INSPECT_PROOF_FAIL inspector_error={snap['inspector_error']}"

    netwatch = snap["netwatch"]
    routes = snap["routes"]
    return (
        0,
        "INSPECT_PROOF_PASS "
        f"observed_owner={snap['observed_owner']} "
        f"configured_owner={snap['configured_owner']} "
        f"match={snap['match']} "
        f"netwatch_entries={netwatch['entries_count']} "
        f"route_mutating_active={netwatch['route_mutating_active_count']} "
        f"total_routes={routes['total_route_count']} "
        f"default_routes={len(routes['default_routes'])}",
    )


def _assert_deployed_imports() -> None:
    wanctl_path = Path(wanctl.__file__ or "").resolve()
    inspector_path = Path(sys.modules[RouteOwnershipInspector.__module__].__file__ or "").resolve()
    print(f"wanctl.__file__={wanctl_path}")
    print(f"route_ownership_inspector.__file__={inspector_path}")
    if not wanctl_path.is_relative_to(DEPLOYED_ROOT) or not inspector_path.is_relative_to(
        DEPLOYED_ROOT
    ):
        print(
            "INSPECT_PROOF_FAIL import-path "
            f"wanctl={wanctl_path} route_ownership_inspector={inspector_path}",
            file=sys.stderr,
        )
        raise SystemExit(1)


def _route_manager_from_config(config: SteeringConfig, client: RouterClientLike) -> RouteManager:
    return RouteManager(
        enabled=bool(config.route_management_enabled),
        mode=str(config.route_management_mode),
        routes=config.route_management_routes,
        router_client=client,
        ownership_guard_result=None,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command_file", type=Path)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    args = parser.parse_args(argv)

    _assert_deployed_imports()
    commands = iter_commands(args.command_file)
    validate_commands_before_run(_NoRunClient(), commands)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    logger = logging.getLogger("phase259-ownership-proof")
    print(f"config={args.config}")
    config = SteeringConfig(str(args.config))
    print(f"config_loader=SteeringConfig transport={config.router_transport}")
    client = get_router_client(config, logger)
    try:
        route_manager = _route_manager_from_config(config, client)
        rc, verdict = run_proof(client, route_manager)
    finally:
        close = getattr(client, "close", None)
        if callable(close):
            close()
    print(verdict)
    return rc


class _NoRunClient:
    def run_cmd(
        self, cmd: str, capture: bool = False, timeout: int | None = None
    ) -> tuple[int, str, str]:
        raise AssertionError("validate_commands_before_run must not execute commands")

    def close(self) -> None:
        return None


if __name__ == "__main__":
    raise SystemExit(main())
