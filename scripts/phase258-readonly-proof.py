#!/usr/bin/env python3
"""Phase 258 live read-only RouterOS proof harness."""
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any, Protocol

import wanctl
from wanctl import routeros_rest
from wanctl.readonly_validator import iter_commands, validate_command
from wanctl.router_client import get_router_client
from wanctl.steering.daemon import SteeringConfig

DEPLOYED_ROOT = Path("/opt/wanctl").resolve()
DEFAULT_CONFIG = Path("/etc/wanctl/steering.yaml")


class RouterClientLike(Protocol):
    def run_cmd(
        self, cmd: str, capture: bool = False, timeout: int | None = None
    ) -> tuple[int, str, str]: ...

    def close(self) -> None: ...


def _count_key(command: str) -> str:
    if "netwatch" in command:
        return "netwatch"
    if "script" in command:
        return "script"
    if "route" in command:
        return "route"
    return "unknown"


def _redacted_sample(items: list[dict[str, Any]]) -> dict[str, Any]:
    if not items:
        return {}
    item = items[0]
    allowed = (
        ".id",
        "name",
        "comment",
        "host",
        "status",
        "disabled",
        "dst-address",
        "gateway",
    )
    sample = {key: item[key] for key in allowed if key in item}
    if "source" in item:
        sample["source"] = "<redacted>"
    for key in list(sample):
        if "password" in key.lower() or "secret" in key.lower() or "key" in key.lower():
            sample[key] = "<redacted>"
    return sample


def _parse_json_list(stdout: str, command: str) -> list[dict[str, Any]]:
    parsed = json.loads(stdout)
    if isinstance(parsed, dict):
        parsed = [parsed]
    if not isinstance(parsed, list) or not all(isinstance(item, dict) for item in parsed):
        raise ValueError(f"{command}: expected list[dict] JSON output")
    if not parsed:
        raise ValueError(f"{command}: empty JSON result")
    return parsed


def run_proof(client: RouterClientLike, commands: list[str]) -> tuple[int, str]:
    counts: dict[str, int] = {}
    samples: dict[str, dict[str, Any]] = {}

    for command in commands:
        validate_command(command)
        rc, stdout, stderr = client.run_cmd(command, capture=True, timeout=5)
        if rc != 0:
            return 1, f"ACCESS02_PROOF_FAIL command={command!r} rc={rc} err={stderr or stdout}"
        try:
            items = _parse_json_list(stdout, command)
        except (json.JSONDecodeError, ValueError) as exc:
            return 1, f"ACCESS02_PROOF_FAIL command={command!r} parse={exc}"
        key = _count_key(command)
        counts[key] = len(items)
        samples[key] = _redacted_sample(items)

    missing = {"route", "netwatch", "script"} - set(counts)
    if missing:
        return 1, f"ACCESS02_PROOF_FAIL missing={','.join(sorted(missing))}"

    detail = json.dumps(samples, sort_keys=True)
    return (
        0,
        "ACCESS02_PROOF_PASS "
        f"route={counts['route']} netwatch={counts['netwatch']} script={counts['script']} "
        f"samples={detail}",
    )


def _assert_deployed_imports() -> None:
    wanctl_path = Path(wanctl.__file__ or "").resolve()
    rest_path = Path(routeros_rest.__file__ or "").resolve()
    print(f"wanctl.__file__={wanctl_path}")
    print(f"routeros_rest.__file__={rest_path}")
    if not wanctl_path.is_relative_to(DEPLOYED_ROOT) or not rest_path.is_relative_to(
        DEPLOYED_ROOT
    ):
        print(
            "ACCESS02_PROOF_FAIL import-path "
            f"wanctl={wanctl_path} routeros_rest={rest_path}",
            file=sys.stderr,
        )
        raise SystemExit(1)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command_file", type=Path)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    args = parser.parse_args(argv)

    _assert_deployed_imports()
    commands = iter_commands(args.command_file)
    for command in commands:
        validate_command(command)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    logger = logging.getLogger("phase258-readonly-proof")
    print(f"config={args.config}")
    config = SteeringConfig(str(args.config))
    print(f"config_loader=SteeringConfig transport={config.router_transport}")
    client = get_router_client(config, logger)
    try:
        rc, verdict = run_proof(client, commands)
    finally:
        close = getattr(client, "close", None)
        if callable(close):
            close()
    print(verdict)
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
