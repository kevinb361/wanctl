#!/usr/bin/env python3
"""Analyze bounded tcpdump text for the Spectrum four-class DSCP proof."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

CLASS_BY_PORT = {
    22: ("EF", 46),
    443: ("AF31", 26),
    119: ("CS1", 8),
    9: ("CS0", 0),
}
TOS_RE = re.compile(r"\btos\s+0x([0-9a-fA-F]+)\b")
DEST_PORT_RE = re.compile(r"\s>\s[^ ]+\.(22|443|119|9):")
TCP_SYN_RE = re.compile(r"\bFlags\s+\[S\]")


def packet_records(text: str) -> list[str]:
    records: list[str] = []
    current: list[str] = []
    for line in text.splitlines():
        if not line.strip():
            continue
        if not line[:1].isspace():
            if current:
                records.append(" ".join(current))
            current = [line]
        elif current:
            current.append(line.strip())
    if current:
        records.append(" ".join(current))
    return records


def analyze_capture(text: str) -> dict[str, Any]:
    observed: dict[int, set[int]] = {port: set() for port in CLASS_BY_PORT}
    packet_counts: dict[int, int] = {port: 0 for port in CLASS_BY_PORT}

    for record in packet_records(text):
        tos_match = TOS_RE.search(record)
        port_match = DEST_PORT_RE.search(record)
        if not tos_match or not port_match:
            continue
        port = int(port_match.group(1))
        if port != 9 and not TCP_SYN_RE.search(record):
            continue
        dscp = int(tos_match.group(1), 16) >> 2
        observed[port].add(dscp)
        packet_counts[port] += 1

    classes: list[dict[str, Any]] = []
    for port, (name, expected) in CLASS_BY_PORT.items():
        values = sorted(observed[port])
        passed = packet_counts[port] > 0 and values == [expected]
        classes.append(
            {
                "class": name,
                "port": port,
                "expected_dscp": expected,
                "observed_dscp": values,
                "packets": packet_counts[port],
                "pass": passed,
            }
        )

    return {
        "overall_pass": all(item["pass"] for item in classes),
        "classes": classes,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capture", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    report = analyze_capture(args.capture.read_text(encoding="utf-8", errors="replace"))
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps(report, sort_keys=True))
    return 0 if report["overall_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
