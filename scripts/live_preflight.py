#!/usr/bin/env python3
"""Read-only live preflight before any wanctl canary/deploy.

The script collects current live state from cake-shaper over SSH and writes a
JSON proof. It intentionally has no mutation mode.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT_DIR = ROOT / ".planning" / "evidence" / "live-preflight"
SSH_OPTS = ["-n", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10"]

READ_ONLY_REMOTE_COMMANDS = [
    "hostname -f || hostname",
    "date -u +%Y-%m-%dT%H:%M:%SZ",
    "systemctl is-active {unit}",
    "systemctl is-enabled {unit}",
    "systemctl cat {unit}",
    "sudo -n test -f /etc/wanctl/{wan}.yaml",
    "test -f /opt/wanctl/autorate_continuous.py",
    "curl -fsS --max-time 5 {url}",
]

MUTATION_TOKENS = (
    "systemctl start",
    "systemctl stop",
    "systemctl restart",
    "systemctl enable",
    "systemctl disable",
    "systemctl mask",
    "systemctl unmask",
    "systemctl kill",
    "tc qdisc add",
    "tc qdisc del",
    "tc qdisc replace",
    "tc qdisc change",
    "sed -i",
    "install ",
    "cp ",
    "mv ",
    "rm ",
    "kill -",
)

ACTIVE_UNITS = [
    "bpctl-silicom.service",
    "cake-autorate-spectrum.service",
    "cake-autorate-att.service",
    "cake-autorate-spectrum-state-bridge.service",
    "cake-autorate-att-state-bridge.service",
    "silicom-bypass-watchdog@spectrum.service",
    "silicom-bypass-watchdog@att.service",
]

INACTIVE_UNITS = ["wanctl@spectrum.service", "wanctl@att.service"]
ENABLED_UNITS = [
    "cake-autorate-spectrum.service",
    "cake-autorate-att.service",
    "cake-autorate-spectrum-state-bridge.service",
    "cake-autorate-att-state-bridge.service",
]

HEALTH_URLS = {
    "steering": "http://127.0.0.1:9102/health",
    "spectrum_bridge": "http://10.10.110.223:9101/health",
    "att_bridge": "http://10.10.110.227:9101/health",
}


@dataclass
class Check:
    name: str
    command: str
    expected: str
    passed: bool
    exit_code: int
    stdout: str
    stderr: str

    def to_json(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "command": self.command,
            "expected": self.expected,
            "pass": self.passed,
            "exit_code": self.exit_code,
            "stdout": self.stdout.strip(),
            "stderr": self.stderr.strip(),
        }


def utc_now() -> str:
    fixed = os.environ.get("WANCTL_PREFLIGHT_FIXED_TIME")
    if fixed:
        return fixed
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def run_local(args: list[str], *, timeout: int = 30) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=ROOT, text=True, capture_output=True, timeout=timeout, check=False)


def run_ssh(host: str, remote_command: str, *, timeout: int = 20) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["ssh", *SSH_OPTS, host, remote_command],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=timeout,
        check=False,
    )


def add_remote_check(
    checks: list[Check],
    host: str,
    name: str,
    remote_command: str,
    expected: str,
    predicate: Any,
) -> None:
    result = run_ssh(host, remote_command)
    stdout = result.stdout.strip()
    stderr = result.stderr.strip()
    try:
        passed = bool(predicate(result.returncode, stdout, stderr))
    except Exception as exc:  # pragma: no cover - defensive proof recording
        passed = False
        stderr = f"{stderr}\npredicate failed: {exc}".strip()
    checks.append(
        Check(
            name=name,
            command=f"ssh {host!r} {remote_command!r}",
            expected=expected,
            passed=passed,
            exit_code=result.returncode,
            stdout=stdout,
            stderr=stderr,
        )
    )


def json_status(stdout: str) -> dict[str, Any]:
    try:
        data = json.loads(stdout)
    except json.JSONDecodeError:
        return {"_parse_error": True}
    return data if isinstance(data, dict) else {"_non_object": data}


def render_rollback_dry_run(wan: str, host: str) -> Check:
    cmd = ["bash", "scripts/phase231-rollback.sh", "--wan", wan, "--ssh-host", host, "--dry-run"]
    result = run_local(cmd)
    output = result.stdout + result.stderr
    passed = (
        result.returncode == 0
        and "mutation only with --confirm" in output
        and "Rollback sequence:" in output
        and "Return-to-cake sequence" in output
        and "--confirm" not in " ".join(cmd)
    )
    return Check(
        name=f"rollback_dry_run_{wan}",
        command=" ".join(cmd),
        expected="rollback and return-to-cake plans render without mutation",
        passed=passed,
        exit_code=result.returncode,
        stdout=result.stdout,
        stderr=result.stderr,
    )


def assert_script_is_read_only() -> None:
    joined = "\n".join(READ_ONLY_REMOTE_COMMANDS)
    lowered = joined.lower()
    offenders = [token for token in MUTATION_TOKENS if token in lowered]
    if offenders:
        raise SystemExit(f"internal safety check failed, mutation token(s): {', '.join(offenders)}")


def build_payload(host: str, checks: list[Check]) -> dict[str, Any]:
    health: dict[str, Any] = {}
    for check in checks:
        if check.name.startswith("health_") and check.stdout:
            health[check.name.removeprefix("health_")] = json_status(check.stdout)

    route_management = health.get("steering", {}).get("route_management", {})
    return {
        "proof_type": "wanctl-live-preflight",
        "captured_utc": utc_now(),
        "ssh_host": host,
        "read_only": True,
        "mutation_mode_available": False,
        "overall_pass": all(check.passed for check in checks),
        "summary": {
            "checks_total": len(checks),
            "checks_passed": sum(1 for check in checks if check.passed),
            "route_management_mode": route_management.get("mode"),
            "route_management_owner": route_management.get("active_owner")
            or route_management.get("observed_owner"),
            "route_guard_status": (route_management.get("guard") or {}).get("status"),
            "route_conflict_count": (route_management.get("guard") or {}).get("conflict_count"),
        },
        "checks": [check.to_json() for check in checks],
    }


def default_out_path(out_dir: Path) -> Path:
    stamp = utc_now().replace(":", "").replace("-", "")
    return out_dir / f"wanctl-live-preflight-{stamp}.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Read-only live preflight before wanctl canary/deploy. Writes JSON proof."
    )
    parser.add_argument("--ssh-host", default="cake-shaper", help="SSH target, default: cake-shaper")
    parser.add_argument("--out", type=Path, help="Output JSON path")
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=DEFAULT_OUT_DIR,
        help="Output dir when --out is omitted, default: .planning/evidence/live-preflight",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    assert_script_is_read_only()

    checks: list[Check] = []
    host = args.ssh_host

    add_remote_check(checks, host, "ssh_connect", "hostname -f || hostname", "SSH returns hostname", lambda rc, out, _err: rc == 0 and bool(out))
    add_remote_check(checks, host, "remote_clock", "date -u +%Y-%m-%dT%H:%M:%SZ", "remote clock readable in UTC", lambda rc, out, _err: rc == 0 and out.endswith("Z"))

    for unit in ACTIVE_UNITS:
        add_remote_check(
            checks,
            host,
            f"active_{unit}",
            f"systemctl is-active {unit}",
            "stdout exactly active",
            lambda rc, out, _err: rc == 0 and out == "active",
        )
    for unit in INACTIVE_UNITS:
        add_remote_check(
            checks,
            host,
            f"inactive_{unit}",
            f"systemctl is-active {unit} || true",
            "stdout exactly inactive or failed",
            lambda _rc, out, _err: out in {"inactive", "failed", "unknown"},
        )
    for unit in ENABLED_UNITS:
        add_remote_check(
            checks,
            host,
            f"enabled_{unit}",
            f"systemctl is-enabled {unit}",
            "stdout exactly enabled",
            lambda rc, out, _err: rc == 0 and out == "enabled",
        )

    for wan in ("spectrum", "att"):
        add_remote_check(
            checks,
            host,
            f"config_present_{wan}",
            f"sudo -n test -f /etc/wanctl/{wan}.yaml",
            f"/etc/wanctl/{wan}.yaml exists",
            lambda rc, _out, _err: rc == 0,
        )
    add_remote_check(
        checks,
        host,
        "native_code_present",
        "test -f /opt/wanctl/autorate_continuous.py",
        "native rollback controller code exists",
        lambda rc, _out, _err: rc == 0,
    )

    for wan in ("spectrum", "att"):
        add_remote_check(
            checks,
            host,
            f"conflicts_guard_{wan}",
            f"systemctl cat cake-autorate-{wan}.service",
            f"unit contains Conflicts=wanctl@{wan}.service",
            lambda rc, out, _err, wan=wan: rc == 0 and f"Conflicts=wanctl@{wan}.service" in out,
        )

    for name, url in HEALTH_URLS.items():
        add_remote_check(
            checks,
            host,
            f"health_{name}",
            f"curl -fsS --max-time 5 {url}",
            "health endpoint returns JSON object",
            lambda rc, out, _err: rc == 0 and not json_status(out).get("_parse_error"),
        )

    checks.extend(render_rollback_dry_run(wan, host) for wan in ("spectrum", "att"))

    payload = build_payload(host, checks)
    out_path = args.out or default_out_path(args.out_dir)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print(f"wanctl live preflight proof: {out_path}")
    print(f"checks: {payload['summary']['checks_passed']}/{payload['summary']['checks_total']}")
    if not payload["overall_pass"]:
        failed = [check.name for check in checks if not check.passed]
        print("failed checks:", ", ".join(failed), file=sys.stderr)
        return 1
    print("OK: read-only live preflight passed; no production mutation performed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
