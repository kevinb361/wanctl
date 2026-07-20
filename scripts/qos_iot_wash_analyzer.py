#!/usr/bin/env python3
"""Analyze one-packet IoT source-subnet DSCP wash canary evidence."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

CANARY_COMMENT = "CANARY: DSCP WASH IoT source subnet"
LEGACY_COMMENT = "DSCP WASH: IoT VLAN"
TRUST_COMMENTS = ("Trust EF", "Trust AF4x")


def _rules(rows: list[dict[str, Any]], comment: str) -> list[dict[str, Any]]:
    return [row for row in rows if row.get("comment") == comment]


def _packet_total(rows: list[dict[str, Any]], comment: str) -> int:
    return sum(int(row.get("packets", 0)) for row in _rules(rows, comment))


def _byte_total(rows: list[dict[str, Any]], comment: str) -> int:
    return sum(int(row.get("bytes", 0)) for row in _rules(rows, comment))


def _is_true(value: Any) -> bool:
    return value is True or str(value).lower() in {"true", "yes"}


def _is_false(value: Any) -> bool:
    return value in (None, False, "false", "no")


def _canary_shape_valid(row: dict[str, Any]) -> bool:
    return all(
        (
            row.get("comment") == CANARY_COMMENT,
            row.get("chain") == "prerouting",
            row.get("action") == "change-dscp",
            str(row.get("new-dscp")) == "0",
            _is_true(row.get("passthrough")),
            row.get("src-address") == "10.10.120.0/24",
            "in-interface" not in row,
            _is_false(row.get("disabled")),
            _is_false(row.get("invalid")),
            not _is_true(row.get("dynamic")),
        )
    )


def _immediately_before(rows: list[dict[str, Any]], first: str, second: str) -> bool:
    first_indexes = [index for index, row in enumerate(rows) if row.get("comment") == first]
    second_indexes = [index for index, row in enumerate(rows) if row.get("comment") == second]
    return (
        len(first_indexes) == len(second_indexes) == 1 and first_indexes[0] + 1 == second_indexes[0]
    )


def analyze(
    before: list[dict[str, Any]], after: list[dict[str, Any]], capture: str
) -> dict[str, Any]:
    canary_before = _rules(before, CANARY_COMMENT)
    canary_after = _rules(after, CANARY_COMMENT)
    source_ef_proven = bool(
        re.search(r"\btos\s+0xb8\b", capture, re.IGNORECASE) and "ICMP echo request" in capture
    )
    canary_packet_delta = _packet_total(after, CANARY_COMMENT) - _packet_total(
        before, CANARY_COMMENT
    )
    canary_byte_delta = _byte_total(after, CANARY_COMMENT) - _byte_total(before, CANARY_COMMENT)
    legacy_wash_packet_delta = _packet_total(after, LEGACY_COMMENT) - _packet_total(
        before, LEGACY_COMMENT
    )
    trust_ef_delta = _packet_total(after, "Trust EF") - _packet_total(before, "Trust EF")
    trust_af_delta = _packet_total(after, "Trust AF4x") - _packet_total(before, "Trust AF4x")
    trust_rules = [row for comment in TRUST_COMMENTS for row in _rules(before, comment)]
    trust_rules_after = [row for comment in TRUST_COMMENTS for row in _rules(after, comment)]
    trust_excludes_iot = (
        bool(trust_rules)
        and len(trust_rules) == len(trust_rules_after)
        and all(
            row.get("in-interface") == "!vlan120-IOT" for row in trust_rules + trust_rules_after
        )
    )
    canary_rule_shape_valid = (
        len(canary_before) == len(canary_after) == 1
        and _canary_shape_valid(canary_before[0])
        and _canary_shape_valid(canary_after[0])
    )
    canary_order_valid = _immediately_before(
        before, CANARY_COMMENT, LEGACY_COMMENT
    ) and _immediately_before(after, CANARY_COMMENT, LEGACY_COMMENT)
    overall_pass = all(
        (
            canary_rule_shape_valid,
            canary_order_valid,
            source_ef_proven,
            canary_packet_delta == 1,
            canary_byte_delta > 0,
            trust_excludes_iot,
        )
    )
    return {
        "overall_pass": overall_pass,
        "canary_rule_shape_valid": canary_rule_shape_valid,
        "canary_order_valid": canary_order_valid,
        "source_ef_proven": source_ef_proven,
        "canary_packet_delta": canary_packet_delta,
        "canary_byte_delta": canary_byte_delta,
        "legacy_wash_packet_delta": legacy_wash_packet_delta,
        "trust_excludes_iot": trust_excludes_iot,
        "trust_ef_packet_delta": trust_ef_delta,
        "trust_af4x_packet_delta": trust_af_delta,
    }


def load_routeros_artifact(path: Path) -> list[dict[str, Any]]:
    text = path.read_text(encoding="utf-8")
    json_start = text.find("[")
    if json_start < 0:
        raise ValueError(f"RouterOS JSON array missing from {path}")
    payload = json.loads(text[json_start:])
    if not isinstance(payload, list):
        raise TypeError(f"RouterOS artifact is not a list: {path}")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--before", required=True, type=Path)
    parser.add_argument("--after", required=True, type=Path)
    parser.add_argument("--source-capture", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    report = analyze(
        load_routeros_artifact(args.before),
        load_routeros_artifact(args.after),
        args.source_capture.read_text(encoding="utf-8", errors="replace"),
    )
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps(report, sort_keys=True))
    return 0 if report["overall_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
