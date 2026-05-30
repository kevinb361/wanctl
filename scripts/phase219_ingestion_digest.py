#!/usr/bin/env python3
"""Phase 219 ingestion-rate snapshot writer.

Cron-callable evidence primitive for persisting the Phase 219
``wanctl-history --ingestion-rate --by-table --rolling=60,300,3600 --json``
envelope to disk. Uses the project atomic JSON helper per D-21 so readers never
observe partial snapshot files.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from wanctl.state_utils import atomic_write_json

# resolves_phase: 219

SNAPSHOT_DIR_DEFAULT = Path("/var/lib/wanctl/snapshots/ingestion")
MAX_SNAPSHOTS_DEFAULT = 288
SUBPROCESS_TIMEOUT_SEC = 30


def _ensure_dir(snapshot_dir: Path) -> None:
    """Create the snapshot directory, tolerating permission warnings."""
    try:
        snapshot_dir.mkdir(parents=True, exist_ok=True, mode=0o755)
    except PermissionError as exc:
        print(
            f"phase219-ingestion-digest: snapshot dir warning: {exc}",
            file=sys.stderr,
        )


def _call_history() -> str:
    """Return the Phase 219 ingestion-rate JSON envelope from wanctl-history."""
    argv = [
        sys.executable,
        "-m",
        "wanctl.history",
        "--ingestion-rate",
        "--by-table",
        "--rolling=60,300,3600",
        "--json",
    ]
    result = subprocess.run(
        argv,
        capture_output=True,
        text=True,
        timeout=SUBPROCESS_TIMEOUT_SEC,
        check=True,
    )
    return result.stdout


def _prune_old(snapshot_dir: Path, max_files: int) -> None:
    """Remove oldest completed JSON snapshots when count exceeds max_files."""
    files = sorted(snapshot_dir.glob("*.json"))
    while len(files) > max_files:
        oldest = files.pop(0)
        oldest.unlink()


def _build_parser() -> argparse.ArgumentParser:
    """Build the cron/test CLI parser."""
    parser = argparse.ArgumentParser(
        description="Phase 219 ingestion-rate snapshot writer"
    )
    parser.add_argument(
        "--snapshot-dir",
        type=Path,
        default=SNAPSHOT_DIR_DEFAULT,
        help="Directory for <unix_ts>.json ingestion-rate snapshots",
    )
    parser.add_argument(
        "--max-snapshots",
        type=int,
        default=MAX_SNAPSHOTS_DEFAULT,
        help="Maximum completed JSON snapshots to retain",
    )
    parser.add_argument(
        "--payload-from-stdin",
        action="store_true",
        help="Test affordance: read JSON payload from stdin instead of forking wanctl-history",
    )
    parser.add_argument(
        "--inject-timestamp",
        type=int,
        default=None,
        help="Test affordance: use this integer as the snapshot unix-ts",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Write one ingestion-rate snapshot and return a cron-friendly status code."""
    args = _build_parser().parse_args(argv)
    if args.max_snapshots < 0:
        print("phase219-ingestion-digest: --max-snapshots must be non-negative", file=sys.stderr)
        return 1
    snapshot_ts = (
        args.inject_timestamp if args.inject_timestamp is not None else int(time.time())
    )

    _ensure_dir(args.snapshot_dir)

    if args.payload_from_stdin:
        payload = sys.stdin.read()
    else:
        try:
            payload = _call_history()
        except subprocess.TimeoutExpired as exc:
            print(
                f"phase219-ingestion-digest: TIMEOUT after {exc.timeout}s",
                file=sys.stderr,
            )
            return 1
        except subprocess.CalledProcessError as exc:
            print(
                "phase219-ingestion-digest: "
                f"wanctl-history failed rc={exc.returncode}: {exc.stderr}",
                file=sys.stderr,
            )
            return 1
        except OSError as exc:
            print(
                f"phase219-ingestion-digest: subprocess OSError: {exc}",
                file=sys.stderr,
            )
            return 1

    try:
        payload_dict: dict[str, Any] = json.loads(payload)
    except json.JSONDecodeError as exc:
        print(
            f"phase219-ingestion-digest: malformed JSON from wanctl-history: {exc}",
            file=sys.stderr,
        )
        return 1

    target = args.snapshot_dir / f"{snapshot_ts}.json"
    try:
        atomic_write_json(target, payload_dict)
    except OSError as exc:
        print(f"phase219-ingestion-digest: atomic write failed: {exc}", file=sys.stderr)
        return 1

    try:
        _prune_old(args.snapshot_dir, args.max_snapshots)
    except OSError as exc:
        print(
            f"phase219-ingestion-digest: retention sweep warning: {exc}",
            file=sys.stderr,
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())
