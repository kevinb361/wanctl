#!/usr/bin/env python3
"""Fail-closed secret scan that never prints candidate values or hashes."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any


def _safe_text(value: object) -> str:
    """Render scanner metadata without terminal control characters."""
    text = str(value)
    return "".join(char if char.isprintable() else "?" for char in text)


def _tracked_files() -> list[str]:
    result = subprocess.run(
        ["git", "ls-files", "-z"],
        check=True,
        capture_output=True,
    )
    return [item.decode("utf-8", "surrogateescape") for item in result.stdout.split(b"\0") if item]


def _baseline_digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _result_rows(payload: Any) -> list[tuple[str, int | str, str]]:
    if not isinstance(payload, dict) or not isinstance(payload.get("results"), dict):
        raise TypeError("scanner output is not a detect-secrets result")

    rows: list[tuple[str, int | str, str]] = []
    for filename, findings in payload["results"].items():
        if not isinstance(findings, list):
            raise TypeError("scanner findings are malformed")
        for finding in findings:
            if not isinstance(finding, dict):
                raise TypeError("scanner finding is malformed")
            rows.append(
                (
                    _safe_text(filename),
                    finding.get("line_number", "?"),
                    _safe_text(finding.get("type", "unknown")),
                )
            )
    return rows


def check_secrets(baseline: Path, files: list[str], scanner: str) -> int:
    """Run detect-secrets-hook and report only path, line, and detector type."""
    if not baseline.is_file():
        print(f"secret scan failed: baseline not found: {_safe_text(baseline)}", file=sys.stderr)
        return 2

    selected = [path for path in files if path != str(baseline) and Path(path).is_file()]
    if not selected:
        print("secret scan failed: no tracked files selected", file=sys.stderr)
        return 2

    before = _baseline_digest(baseline)
    try:
        result = subprocess.run(
            [scanner, "--json", "--no-verify", "--baseline", str(baseline), *selected],
            capture_output=True,
            text=True,
            timeout=300,
        )
    except (OSError, subprocess.TimeoutExpired):
        print("secret scan failed: scanner unavailable or timed out", file=sys.stderr)
        return 2

    if _baseline_digest(baseline) != before:
        print("secret scan failed: scanner modified the baseline", file=sys.stderr)
        return 1

    if not result.stdout.strip() and result.returncode == 0:
        rows: list[tuple[str, int | str, str]] = []
    else:
        try:
            rows = _result_rows(json.loads(result.stdout))
        except (json.JSONDecodeError, TypeError):
            print("secret scan failed: scanner returned invalid output", file=sys.stderr)
            return 2

    if rows or result.returncode != 0:
        print(f"secret scan rejected {len(rows)} candidate(s):", file=sys.stderr)
        for filename, line_number, detector_type in rows:
            print(f"  {filename}:{line_number}: {detector_type}", file=sys.stderr)
        return 1

    print(f"Secret scan passed ({len(selected)} tracked files)")
    return 0


def _default_scanner() -> str | None:
    sibling = Path(sys.executable).with_name("detect-secrets-hook")
    return str(sibling) if sibling.is_file() else shutil.which("detect-secrets-hook")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("files", nargs="*", help="files to scan; defaults to tracked files")
    parser.add_argument("--baseline", type=Path, default=Path(".secrets.baseline"))
    parser.add_argument("--scanner", default=_default_scanner())
    args = parser.parse_args()

    if not args.scanner:
        print("secret scan failed: detect-secrets-hook not found", file=sys.stderr)
        return 2

    try:
        files = args.files or _tracked_files()
    except (OSError, subprocess.CalledProcessError):
        print("secret scan failed: unable to list tracked files", file=sys.stderr)
        return 2
    return check_secrets(args.baseline, files, args.scanner)


if __name__ == "__main__":
    raise SystemExit(main())
