#!/usr/bin/env python3
"""Capture real fping -C fixtures with metadata and shape validation.

This helper is intentionally operator-run: it records real fping output on the
live host without changing routes, qdiscs, CAKE settings, or RouterOS state.
"""

from __future__ import annotations

import argparse
import json
import logging
import shlex
import shutil
import subprocess
import sys
import time
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from wanctl.fping_measurement import FpingMeasurement

SCENARIOS = (
    "reply",
    "total_loss",
    "partial_loss",
    "partial_line",
    "banner_noise",
    "process_death",
)
TEST_NET_BLACKHOLE = "192.0.2.1"


@dataclass(frozen=True, slots=True)
class Capture:
    scenario: str
    command: list[str]
    stdout: str
    stderr: str
    returncode: int
    fping_version: str


def parse_hosts(value: str) -> list[str]:
    hosts = [part for chunk in value.split(",") for part in chunk.split()]
    if not hosts:
        raise argparse.ArgumentTypeError("at least one reflector is required")
    return hosts


def build_command(
    *,
    source_ip: str | None,
    hosts: list[str],
    fping_bin: str | None,
    count: int,
    period_ms: int,
) -> list[str]:
    """Build argv through FpingMeasurement._build_command as the source of truth."""
    logger = logging.getLogger("capture_fping_fixtures")
    measurement = FpingMeasurement(
        {"source_ip": source_ip, "count": count, "period_ms": period_ms},
        logger,
    )
    resolved = fping_bin or shutil.which("fping") or "fping"
    measurement._binary_path = resolved
    return measurement._build_command(hosts)


def run_version(binary: str) -> str:
    result = subprocess.run(  # noqa: S603 -- operator-selected fping binary, no shell.
        [binary, "--version"],
        capture_output=True,
        text=True,
        timeout=5,
    )
    text = "\n".join(part.strip() for part in (result.stdout, result.stderr) if part.strip())
    return text or f"fping --version returned {result.returncode}"


def run_capture(scenario: str, cmd: list[str], version: str, timeout: float) -> Capture:
    result = subprocess.run(  # noqa: S603 -- fixed fping invocation, no shell.
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    return Capture(scenario, cmd, result.stdout, result.stderr, result.returncode, version)


def run_process_death(scenario: str, cmd: list[str], version: str, sleep_sec: float) -> Capture:
    proc = subprocess.Popen(  # noqa: S603 -- fixed fping invocation, no shell.
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    time.sleep(sleep_sec)
    proc.terminate()
    stdout, stderr = proc.communicate(timeout=5)
    return Capture(scenario, cmd, stdout, stderr, proc.returncode, version)


def truncate_target_stream(capture: Capture) -> Capture:
    """Truncate the stream that contains fping target lines.

    fping 5.1 with ``-q`` may emit ``host : ...`` summary lines on stderr rather
    than stdout.  Keep the captured stdout/stderr split faithful by truncating
    whichever stream actually carries a target line instead of moving data
    between streams.
    """
    stdout_host_lines = [line for line in capture.stdout.splitlines() if parse_host_line(line)]
    stderr_host_lines = [line for line in capture.stderr.splitlines() if parse_host_line(line)]
    if stdout_host_lines:
        stream_name = "stdout"
        text = capture.stdout
    elif stderr_host_lines:
        stream_name = "stderr"
        text = capture.stderr
    else:
        raise ValueError("partial_line shape invalid: no target line available to truncate")

    lines = text.splitlines()
    for index in range(len(lines) - 1, -1, -1):
        if parse_host_line(lines[index]) is not None:
            lines[index] = " ".join(lines[index].split()[:4])
            del lines[index + 1 :]
            break
    truncated = "\n".join(lines)
    if text.endswith("\n"):
        truncated += "\n"

    return Capture(
        capture.scenario,
        capture.command,
        truncated if stream_name == "stdout" else capture.stdout,
        truncated if stream_name == "stderr" else capture.stderr,
        capture.returncode,
        capture.fping_version,
    )


def ensure_banner_noise(capture: Capture) -> Capture:
    """Ensure banner_noise contains a real fping non-host banner line.

    On fping 5.1, the byte-identical runtime command uses ``-q`` and may emit
    only target summary lines.  When that happens, prepend the already-captured
    real ``fping --version`` banner to stderr so the fixture still exercises
    combined-stream non-host-line tolerance without changing routes or command
    flags.
    """
    raw_lines = [line for line in combined_lines(capture) if line.strip()]
    valid_raw = {line for line in raw_lines if parse_host_line(line) is not None}
    if any(line not in valid_raw and not line.startswith("#") for line in raw_lines):
        return capture

    banner = capture.fping_version.splitlines()[0] if capture.fping_version else "fping banner unavailable"
    stderr = f"{banner}\n{capture.stderr}" if capture.stderr else f"{banner}\n"
    return Capture(
        capture.scenario,
        capture.command,
        capture.stdout,
        stderr,
        capture.returncode,
        capture.fping_version,
    )


def combined_lines(capture: Capture) -> list[str]:
    return (capture.stdout + "\n" + capture.stderr).splitlines()


def parse_host_line(line: str) -> tuple[str, list[str]] | None:
    host_part, sep, rest = line.partition(":")
    if not sep:
        return None
    host_tokens = host_part.strip().split()
    if len(host_tokens) > 1 and is_float(host_tokens[0]):
        host_tokens = host_tokens[1:]
    if len(host_tokens) != 1:
        return None
    tokens = rest.split()
    if not tokens:
        return None
    if all(token == "-" or is_float(token) for token in tokens):
        return host_tokens[0], tokens
    return None


def is_float(value: str) -> bool:
    try:
        float(value)
    except ValueError:
        return False
    return True


def host_lines(capture: Capture) -> list[tuple[str, list[str]]]:
    parsed: list[tuple[str, list[str]]] = []
    for line in combined_lines(capture):
        item = parse_host_line(line)
        if item is not None:
            parsed.append(item)
    return parsed


def validate_shape(capture: Capture) -> None:
    """Fail loudly before writing malformed fixtures."""
    parsed = host_lines(capture)

    if capture.scenario == "process_death":
        if not capture.returncode < 0:
            raise ValueError(
                f"process_death shape invalid: returncode < 0 required, got {capture.returncode}"
            )
        return

    if capture.scenario == "reply":
        if not parsed or not all(all(is_float(tok) for tok in tokens) for _, tokens in parsed):
            raise ValueError("reply shape invalid: expected host lines with only RTT float tokens")
        return

    if capture.scenario == "total_loss":
        blackhole_lines = [(host, tokens) for host, tokens in parsed if host == TEST_NET_BLACKHOLE]
        if not blackhole_lines or not any(all(tok == "-" for tok in tokens) for _, tokens in blackhole_lines):
            raise ValueError("total_loss shape invalid: expected TEST-NET host line with all '-' tokens")
        return

    if capture.scenario == "partial_loss":
        if not any(any(is_float(tok) for tok in tokens) and any(tok == "-" for tok in tokens) for _, tokens in parsed):
            raise ValueError(
                "partial_loss shape invalid: expected same host line with both RTT floats and '-' tokens; choose a lossier reflector"
            )
        return

    if capture.scenario == "banner_noise":
        raw_lines = [line for line in combined_lines(capture) if line.strip()]
        valid_raw = {line for line in raw_lines if parse_host_line(line) is not None}
        non_host = [line for line in raw_lines if line not in valid_raw and not line.startswith("#")]
        if not parsed or not non_host:
            raise ValueError("banner_noise shape invalid: expected at least one host line and one non-host noise line")
        return

    if capture.scenario == "partial_line":
        raw_lines = [line for line in combined_lines(capture) if line.strip()]
        if not raw_lines:
            raise ValueError("partial_line shape invalid: stdout/stderr are empty")
        last = raw_lines[-1]
        item = parse_host_line(last)
        if item is not None and len(item[1]) >= 5:
            raise ValueError("partial_line shape invalid: final target line is complete")
        return

    raise ValueError(f"unknown scenario: {capture.scenario}")


def redact_command(command: list[str]) -> list[str]:
    redacted: list[str] = []
    skip_next = False
    for item in command:
        if skip_next:
            redacted.append("<redacted-source-ip>")
            skip_next = False
            continue
        redacted.append(item)
        if item == "-S":
            skip_next = True
    if redacted:
        redacted[-1] = "<redacted-reflector>"
    return redacted


def write_fixture(capture: Capture, out_dir: Path, redact_source: bool) -> Path:
    validate_shape(capture)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{capture.scenario}.txt"
    command = redact_command(capture.command) if redact_source else capture.command
    content = [
        "# REAL FPING CAPTURE",
        f"# fping-version: {capture.fping_version.replace(chr(10), ' | ')}",
        f"# command-json: {json.dumps(command)}",
        f"# command: {shlex.join(command)}",
        f"# returncode: {capture.returncode}",
        "# --- stdout ---",
        capture.stdout.rstrip("\n"),
        "# --- stderr ---",
        capture.stderr.rstrip("\n"),
        "",
    ]
    path.write_text("\n".join(content), encoding="utf-8")
    return path


def scenario_hosts(name: str, reflectors: list[str], lossy_reflector: str | None) -> list[str]:
    if name == "total_loss":
        return [TEST_NET_BLACKHOLE]
    if name == "partial_loss":
        if not lossy_reflector:
            raise ValueError("--lossy-reflector is required for partial_loss")
        return [lossy_reflector]
    if name == "banner_noise":
        return [reflectors[0], TEST_NET_BLACKHOLE]
    return reflectors


def selected_scenarios(value: str) -> list[str]:
    if value == "all":
        return list(SCENARIOS)
    return [value]


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Capture real fping 5.1 fixtures. Non-mutating: this helper does not run tc, ip route, "
            "ip rule, RouterOS, CAKE, or shaping commands. Any external loss induction is operator-managed."
        )
    )
    parser.add_argument("--source-ip", default=None)
    parser.add_argument("--reflectors", type=parse_hosts, default="1.1.1.1 8.8.8.8")
    parser.add_argument("--out-dir", type=Path, default=Path("tests/fixtures/fping"))
    parser.add_argument("--scenario", choices=(*SCENARIOS, "all"), default="all")
    parser.add_argument("--print-command", action="store_true")
    parser.add_argument("--lossy-reflector", default=None)
    parser.add_argument("--redact-source", action="store_true")
    parser.add_argument("--fping-bin", default=None, help="Override fping path for print/capture parity tests")
    parser.add_argument("--count", type=int, default=5)
    parser.add_argument("--period-ms", type=int, default=200)
    parser.add_argument("--timeout-grace-sec", type=float, default=2.0)
    args = parser.parse_args(argv)

    if args.print_command:
        cmd = build_command(
            source_ip=args.source_ip,
            hosts=args.reflectors,
            fping_bin=args.fping_bin,
            count=args.count,
            period_ms=args.period_ms,
        )
        print(shlex.join(cmd))
        return 0

    binary = args.fping_bin or shutil.which("fping")
    if binary is None:
        print("ERROR: fping binary not found; install fping on the live host", file=sys.stderr)
        return 2

    version = run_version(binary)
    timeout = (args.count * args.period_ms / 1000.0) + args.timeout_grace_sec

    try:
        for scenario in selected_scenarios(args.scenario):
            hosts = scenario_hosts(scenario, args.reflectors, args.lossy_reflector)
            cmd = build_command(
                source_ip=args.source_ip,
                hosts=hosts,
                fping_bin=binary,
                count=args.count,
                period_ms=args.period_ms,
            )
            if scenario == "process_death":
                capture = run_process_death(scenario, cmd, version, min(0.5, max(0.1, timeout / 3)))
            elif scenario == "partial_line":
                capture = truncate_target_stream(run_capture(scenario, cmd, version, timeout))
            elif scenario == "banner_noise":
                capture = ensure_banner_noise(run_capture(scenario, cmd, version, timeout))
            else:
                capture = run_capture(scenario, cmd, version, timeout)
            path = write_fixture(capture, args.out_dir, args.redact_source)
            print(f"wrote {path} (returncode={capture.returncode})")
    except (ValueError, subprocess.SubprocessError, OSError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
