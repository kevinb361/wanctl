#!/usr/bin/env python3
"""Phase 214 matrix-summary aggregator.

Walks Phase 214 evidence RUN directories, reads per-window signal-sheet.json
artifacts, and rolls them into a matrix-summary.json for downstream Phase 215
planning. The aggregator is stdlib-only, imports no wanctl modules, touches no
production services, and preserves Phase 214's observational-only posture.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

REQUIRED_SPECTRUM_WINDOWS = {"off-peak", "daytime", "prime-time"}
DEFAULT_EVIDENCE_ROOT = Path(".planning/phases/214-measurement-collapse-investigation/evidence")
WINDOW_CHOICES = {"off-peak", "daytime", "prime-time", "att-contrast"}
DISPOSITION_ORDER = {"form_b": 0, "form_c": 1, "none": 2}


def matrix_verdict(window_verdicts: list[str], *, full_window_set: bool = True) -> str:
    """Roll up per-window verdicts into the matrix verdict.

    Rule: any ``fail`` wins, otherwise any ``ambiguous`` wins, otherwise all
    pass with a full required Spectrum set is ``pass``. A non-full required set
    is always ``partial`` and never silently upgraded to ``pass``.
    """
    if not window_verdicts:
        raise ValueError("matrix_verdict requires at least one window verdict")
    if "fail" in window_verdicts:
        return "fail"
    if "ambiguous" in window_verdicts:
        return "ambiguous"
    return "pass" if full_window_set else "partial"


def _git_head_sha() -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            check=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return ""
    return result.stdout.strip()


def _latency_value(sheet: dict[str, Any], key: str) -> float:
    latency = sheet.get("latency")
    if isinstance(latency, dict) and key in latency:
        return float(latency[key])
    return float(sheet[key])


def _window_row(sheet: dict[str, Any]) -> dict[str, Any]:
    ranked = sheet.get("ranked") or sheet.get("ranked_drivers") or []
    if not isinstance(ranked, list):
        ranked = []
    return {
        "window": str(sheet["window"]),
        "run_dir": str(sheet["run_dir"]),
        "p50_ms": _latency_value(sheet, "p50_ms"),
        "p95_ms": _latency_value(sheet, "p95_ms"),
        "p99_ms": _latency_value(sheet, "p99_ms"),
        "verdict": str(sheet["verdict"]),
        "primary_driver": sheet.get("primary_driver"),
        "ranked": [str(driver) for driver in ranked],
        "signal_disposition": str(sheet.get("signal_disposition") or "none"),
    }


def _ranked_driver_scores(sheets: list[dict[str, Any]]) -> dict[str, float]:
    scores: dict[str, float] = defaultdict(float)
    for sheet in sheets:
        if sheet.get("verdict") == "pass":
            continue
        ranked = sheet.get("ranked") or sheet.get("ranked_drivers") or []
        drivers = sheet.get("drivers") if isinstance(sheet.get("drivers"), dict) else {}
        for index, driver in enumerate(ranked if isinstance(ranked, list) else []):
            driver_name = str(driver)
            driver_score = drivers.get(driver_name, {}).get("score") if isinstance(drivers.get(driver_name), dict) else None
            if isinstance(driver_score, (int, float)):
                scores[driver_name] += float(driver_score)
            else:
                scores[driver_name] += float(len(ranked) - index)
        primary = sheet.get("primary_driver")
        if primary and str(primary) not in scores:
            scores[str(primary)] += 1.0
    return scores


def _most_common_lex(values: list[str]) -> str | None:
    if not values:
        return None
    counts = Counter(values)
    return sorted(counts, key=lambda value: (-counts[value], value))[0]


def _signal_disposition(sheets: list[dict[str, Any]]) -> str:
    failed_dispositions = [
        str(sheet.get("signal_disposition"))
        for sheet in sheets
        if sheet.get("verdict") == "fail" and sheet.get("signal_disposition") not in (None, "none")
    ]
    if not failed_dispositions:
        return "none"
    counts = Counter(failed_dispositions)
    return sorted(counts, key=lambda value: (-counts[value], DISPOSITION_ORDER.get(value, 99), value))[0]


def build_matrix_summary(
    signal_sheets: list[dict[str, Any]],
    *,
    full_window_set: bool = True,
    partial_reason: str | None = None,
    missing_windows: list[str] | None = None,
) -> dict[str, Any]:
    """Aggregate signal-sheet dicts into the Phase 214 matrix-summary schema.

    Primary driver aggregation uses the most frequent ``primary_driver`` across
    non-pass windows, with lexicographic tie-break. Ranked drivers are the union
    of non-pass ranked lists ordered by aggregate score, again with lexical
    tie-break. Signal disposition is the most common non-``none`` form across
    failed windows.
    """
    if not signal_sheets:
        raise ValueError("build_matrix_summary requires at least one signal sheet")

    sorted_sheets = sorted(signal_sheets, key=lambda sheet: str(sheet.get("run_dir") or ""))
    rows = [_window_row(sheet) for sheet in sorted_sheets]
    verdict = matrix_verdict([row["verdict"] for row in rows], full_window_set=full_window_set)
    non_pass_primary = [str(sheet["primary_driver"]) for sheet in sorted_sheets if sheet.get("verdict") != "pass" and sheet.get("primary_driver")]
    driver_scores = _ranked_driver_scores(sorted_sheets)
    ranked_drivers = sorted(driver_scores, key=lambda driver: (-driver_scores[driver], driver))

    return {
        "phase": 214,
        "started_utc": min(str(sheet.get("started_utc") or "") for sheet in sorted_sheets),
        "ended_utc": max(str(sheet.get("ended_utc") or "") for sheet in sorted_sheets),
        "git_head_sha": _git_head_sha(),
        "verdict": verdict,
        "primary_driver": _most_common_lex(non_pass_primary),
        "ranked_drivers": ranked_drivers,
        "windows": rows,
        "signal_disposition": _signal_disposition(sorted_sheets),
        "mutation_posture": "read-only",
        "partial_reason": partial_reason if verdict == "partial" else None,
        "missing_windows": sorted(missing_windows or []),
    }


def _read_signal_sheet(path: Path) -> dict[str, Any]:
    sheet = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(sheet, dict):
        raise TypeError("signal-sheet JSON must be an object")
    for key in ("run_dir", "window", "verdict"):
        if key not in sheet:
            raise ValueError(f"signal-sheet missing required key {key!r}")
    if str(sheet["window"]) not in WINDOW_CHOICES:
        raise ValueError(f"signal-sheet has unknown window {sheet['window']!r}")
    _window_row(sheet)
    return sheet


def discover_signal_sheets(evidence_root: Path) -> tuple[list[dict[str, Any]], list[Path]]:
    """Read signal sheets under RUN-*/*/tcp_12down in lexical path order."""
    sheets: list[dict[str, Any]] = []
    malformed: list[Path] = []
    for path in sorted(evidence_root.glob("RUN-*/*/tcp_12down/signal-sheet.json")):
        try:
            sheets.append(_read_signal_sheet(path))
        except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            print(f"WARNING: skipping malformed signal sheet {path}: {exc}", file=sys.stderr)
            malformed.append(path)
    return sheets, malformed


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence-root", type=Path, default=DEFAULT_EVIDENCE_ROOT)
    parser.add_argument("--output-json", required=True, type=Path)
    parser.add_argument("--allow-partial", action="store_true")
    parser.add_argument("--partial-reason")
    args = parser.parse_args(argv)
    if bool(args.allow_partial) != bool(args.partial_reason):
        parser.error("--allow-partial and --partial-reason must be passed together")
    return args


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    sheets, _malformed = discover_signal_sheets(args.evidence_root)
    if not sheets:
        print(f"REFUSED: no valid signal-sheet.json files found under {args.evidence_root}", file=sys.stderr)
        return 1

    discovered = {str(sheet.get("window")) for sheet in sheets if sheet.get("wan") == "spectrum"}
    missing = sorted(REQUIRED_SPECTRUM_WINDOWS - discovered)
    if missing and not args.allow_partial:
        print(
            "REFUSED: missing required Spectrum window(s): "
            f"{missing}. Either run the missing windows or pass "
            "--allow-partial --partial-reason '<text>'.",
            file=sys.stderr,
        )
        return 1

    full_window_set = not missing
    summary = build_matrix_summary(
        sheets,
        full_window_set=full_window_set,
        partial_reason=args.partial_reason if args.allow_partial else None,
        missing_windows=missing,
    )
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
