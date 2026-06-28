#!/usr/bin/env python3
"""Phase 261 D-04 smoke assertion: targeted :9102/health gate.

Pure curl+json gate — does NOT import wanctl (sidesteps deployed-import guard).

Reads ``route_management`` and ``ownership_inspection`` as SIBLING top-level keys
from :9102/health and asserts:
  1. route_management.mode == "dry_run"
  2. route_management.active_owner == "netwatch"
  3. ownership_inspection.inspector_status == "ok"
  4. ownership_inspection.match is True

Exit 0 iff all four PASS.

CRITICAL: mode is asserted EXPLICITLY — active_owner is "netwatch" for both
"off" and "dry_run", so mode is the discriminating field (Pitfall 1).
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
from datetime import UTC, datetime
from typing import Any

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_SSH_HOST = "cake-shaper"
HEALTH_URL = "http://127.0.0.1:9102/health"
READY_STATUSES = {"healthy", "degraded"}

# Expected systemd units that must be active (asserted when --check-units is set)
EXPECTED_UNITS = (
    "steering.service",
    "cake-autorate-spectrum.service",
    "cake-autorate-att.service",
    "cake-autorate-spectrum-state-bridge.service",
    "cake-autorate-att-state-bridge.service",
)


# ---------------------------------------------------------------------------
# Helpers (phase227-rollback.sh idiom translated to Python)
# ---------------------------------------------------------------------------


def require_command(cmd: str) -> str | None:
    """Check that *cmd* is available on PATH; exit 1 if not."""
    if shutil.which(cmd) is None:
        print(f"ERROR: required command missing: {cmd}", file=sys.stderr)
        sys.exit(1)
    return cmd


def ssh(host: str, remote_cmd: str) -> str:
    """Run *remote_cmd* via ssh on *host* and return stdout stripped."""
    result = subprocess.run(
        ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=5", host, remote_cmd],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"ssh {host} returned {result.returncode}: {result.stderr.strip()}")
    return result.stdout.strip()


# ---------------------------------------------------------------------------
# Health fetching & bounded-poll readiness guard
# ---------------------------------------------------------------------------


def fetch_health(host: str, url: str) -> dict[str, Any]:
    """Fetch JSON health payload via ``ssh curl`` on *host*.

    Raises RuntimeError on curl failure or JSON decode error (fail-closed).
    """
    raw = ssh(host, f"curl -fsS {url}")
    return json.loads(raw)


def is_ready(payload: dict[str, Any]) -> bool:
    """Return True if the health payload indicates the daemon is ready.

    Ready = status in (healthy, degraded) AND inspector_status == "ok"
    AND last_inspected_at is present and non-empty.
    """
    status = payload.get("status")
    if status not in READY_STATUSES:
        return False
    oi = payload.get("ownership_inspection")
    if not isinstance(oi, dict):
        return False
    if oi.get("inspector_status") != "ok":
        return False
    last = oi.get("last_inspected_at")
    return isinstance(last, str) and bool(last)


def poll_until_ready(
    host: str, url: str, *, timeout: int = 60, interval: int = 2
) -> dict[str, Any]:
    """Poll *url* via ssh until the daemon is ready or *timeout* expires.

    Returns the last fetched payload on success.
    Raises RuntimeError on timeout (fail-closed).
    """
    deadline = time.monotonic() + timeout
    last_payload: dict[str, Any] | None = None
    while time.monotonic() < deadline:
        try:
            payload = fetch_health(host, url)
        except RuntimeError:
            time.sleep(interval)
            continue
        last_payload = payload
        if is_ready(payload):
            return payload
        time.sleep(interval)

    if last_payload is not None:
        raise RuntimeError(f"timeout after {timeout}s: last status={last_payload.get('status')!r}")
    raise RuntimeError(f"timeout after {timeout}s: could not reach {url}")


# ---------------------------------------------------------------------------
# Gate checks
# ---------------------------------------------------------------------------


def run_gate(
    payload: dict[str, Any],
    *,
    min_inspected_after: int | None = None,
) -> tuple[list[tuple[str, bool]], list[str]]:
    """Run the four core D-04 smoke checks + optional freshness check.

    Returns (checks, failures) where checks is a list of (name, passed)
    and failures is a list of human-readable failure reasons.
    """
    rm = payload.get("route_management")
    if not isinstance(rm, dict):
        rm = {}
    oi = payload.get("ownership_inspection")
    if not isinstance(oi, dict):
        oi = {}

    checks: list[tuple[str, bool]] = [
        (
            "route_management.mode==dry_run",
            rm.get("mode") == "dry_run",
        ),
        (
            "route_management.active_owner==netwatch",
            rm.get("active_owner") == "netwatch",
        ),
        (
            "ownership_inspection.inspector_status==ok",
            oi.get("inspector_status") == "ok",
        ),
        (
            "ownership_inspection.match==true",
            oi.get("match") is True,
        ),
    ]

    # Optional: --min-inspected-after freshness check
    if min_inspected_after is not None:
        last = oi.get("last_inspected_at")
        if last is None or not isinstance(last, str) or not last:
            checks.append(("ownership_inspection.last_inspected_at_present", False))
        else:
            try:
                # Parse ISO 8601 timestamp
                normalized = last.replace("Z", "+00:00")
                inspected_dt = datetime.fromisoformat(normalized)
                if inspected_dt.tzinfo is None:
                    inspected_dt = inspected_dt.replace(tzinfo=UTC)
                inspected_epoch = int(inspected_dt.timestamp())
                checks.append(
                    (
                        f"ownership_inspection.last_inspected_after>{min_inspected_after}",
                        inspected_epoch > min_inspected_after,
                    )
                )
            except (ValueError, OSError):
                checks.append(
                    (
                        "ownership_inspection.last_inspected_at_parseable",
                        False,
                    )
                )

    failures: list[str] = [name for name, passed in checks if not passed]
    return checks, failures


# ---------------------------------------------------------------------------
# Units check
# ---------------------------------------------------------------------------


def check_units(host: str) -> list[tuple[str, bool]]:
    """Assert all expected systemd units are active.

    Returns list of (unit, passed) tuples.
    """
    results: list[tuple[str, bool]] = []
    for unit in EXPECTED_UNITS:
        try:
            active = ssh(host, f"systemctl is-active {unit}")
            results.append((unit, active == "active"))
        except RuntimeError:
            results.append((unit, False))
    return results


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--ssh-host",
        default=DEFAULT_SSH_HOST,
        help="Target host (default: %(default)s)",
    )
    parser.add_argument(
        "--health-url",
        default=HEALTH_URL,
        help="Health endpoint URL on the target (default: %(default)s)",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=60,
        help="Readiness poll timeout in seconds (default: %(default)s)",
    )
    parser.add_argument(
        "--min-inspected-after",
        type=int,
        default=None,
        help="Require last_inspected_at strictly newer than this UNIX epoch",
    )
    parser.add_argument(
        "--check-units",
        action="store_true",
        help="Also assert all expected systemd units are active",
    )
    args = parser.parse_args(argv)

    # Guard required commands
    for cmd in ("ssh", "curl"):
        require_command(cmd)

    # -- Readiness poll --
    print(f"Polling {args.health_url} via ssh {args.ssh_host}...")
    try:
        payload = poll_until_ready(
            args.ssh_host,
            args.health_url,
            timeout=args.timeout,
        )
    except RuntimeError as exc:
        print(f"FAIL readiness: {exc}", file=sys.stderr)
        print("PHASE261_SMOKE_FAIL readiness_timeout")
        return 1
    print(f"Ready: status={payload.get('status')!r}")

    # -- Run gate checks --
    checks, failures = run_gate(payload, min_inspected_after=args.min_inspected_after)
    for name, passed in checks:
        tag = "PASS" if passed else "FAIL"
        print(f"{tag} {name}")

    # -- Optional units check --
    if args.check_units:
        unit_checks = check_units(args.ssh_host)
        for unit, passed in unit_checks:
            tag = "PASS" if passed else "FAIL"
            print(f"{tag} {unit}")
        checks.extend(unit_checks)
        unit_failures = [u for u, p in unit_checks if not p]
        failures.extend(unit_failures)

    # -- Verdict --
    all_pass = all(passed for _, passed in checks)
    if not all_pass:
        print(f"PHASE261_SMOKE_FAIL failures={json.dumps(failures)}")
        return 1

    print("PHASE261_SMOKE_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
