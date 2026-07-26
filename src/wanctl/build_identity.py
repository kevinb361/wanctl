"""Canonical release and immutable source identity surfaces."""

from __future__ import annotations

import argparse
import json
from importlib.metadata import PackageNotFoundError, version

from wanctl._build_identity import BUILD_REVISION


def get_release_version() -> str:
    """Return installed distribution metadata, never a second hard-coded version."""
    try:
        return version("wanctl")
    except PackageNotFoundError:
        return "0+uninstalled"


def get_build_identity() -> dict[str, str]:
    """Return the release and source identities for this installed artifact."""
    return {"version": get_release_version(), "revision": BUILD_REVISION}


def main(argv: list[str] | None = None) -> int:
    """Print the installed identity for operators and automation."""
    parser = argparse.ArgumentParser(description="Show wanctl build identity")
    parser.add_argument("--json", action="store_true", help="emit stable machine-readable JSON")
    args = parser.parse_args(argv)
    identity = get_build_identity()
    if args.json:
        print(json.dumps(identity, sort_keys=True))
    else:
        print(f"wanctl {identity['version']} ({identity['revision']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
