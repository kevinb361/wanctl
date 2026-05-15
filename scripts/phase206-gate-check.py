#!/usr/bin/env python3
"""Phase 206 predeploy-gate Python core.

Computes RRUL p99 regression, daemon restart-rate increase, and pressure-state
transition-rate increase against a committed baseline. Importable for tests;
invoked by scripts/phase206-predeploy-gate.sh in production. Stdlib only -- NO
network calls. SAFE-09: no src/wanctl edits. Fail-closed on input/baseline
mismatch -- see four-state matrix in PLAN.md Task 1 behavior block. Thresholds
loaded from scripts/phase206-thresholds.json (W5).
"""

# ruff: noqa: N999

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

EXIT_PASS = 0
EXIT_BLOCK = 1
EXIT_ABORT = 2


class MalformedSoakInput(ValueError):  # noqa: N818 - planned Phase 206 acceptance name.
    """Raised when soak NDJSON cannot be parsed at all."""


class InsufficientSoakSamples(ValueError):  # noqa: N818 - planned Phase 206 acceptance name.
    """Raised when fewer than 2 rows in the soak NDJSON have both last_zone and t_monotonic."""


def load_thresholds(path: Path | None = None) -> dict:
    target = path or (Path(__file__).resolve().parent / "phase206-thresholds.json")
    with target.open(encoding="utf-8") as fh:
        return json.load(fh)


_T = load_thresholds()
RRUL_P99_REGRESSION_PCT = float(_T["RRUL_P99_REGRESSION_PCT"])
RESTART_RATE_INCREASE_PCT = float(_T["RESTART_RATE_INCREASE_PCT"])
TRANSITION_RATE_INCREASE_PCT = float(_T["TRANSITION_RATE_INCREASE_PCT"])


def _log_info(msg: str) -> None:
    print(f"[phase206-gate-check INFO] {msg}", file=sys.stderr)


def _log_block(msg: str) -> None:
    print(f"[phase206-gate-check BLOCK] {msg}", file=sys.stderr)
    print(msg)


def _log_abort(msg: str) -> None:
    print(f"[phase206-gate-check ABORT] {msg}", file=sys.stderr)


def _read_json(path: str) -> dict:
    with Path(path).open(encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, dict):
        raise TypeError(f"JSON root is not an object: {path}")
    return data


def _read_p99(side: dict) -> tuple[float, str]:
    if "rrul_p99_latency_ms" in side:
        return float(side["rrul_p99_latency_ms"]), "rrul_p99_latency_ms"
    if "controller_rate_p99_mbps" in side:
        return float(side["controller_rate_p99_mbps"]), "controller_rate_p99_mbps"
    raise KeyError("post block lacks both rrul_p99_latency_ms and controller_rate_p99_mbps")


def check_rrul_p99(baseline: dict, candidate: dict, threshold_pct: float) -> tuple[bool, str]:
    # Primary guard: meta.metric_source equality. Runs first; future-proofs against a
    # future flent-sourced baseline. Today's committed fixtures both carry
    # metric_source='controller_replay' so this guard does not fire on the documented
    # scenario -- the secondary guard below does.
    meta_base = baseline.get("meta", {}) if isinstance(baseline, dict) else {}
    meta_cand = candidate.get("meta", {}) if isinstance(candidate, dict) else {}
    src_meta_base = meta_base.get("metric_source") if isinstance(meta_base, dict) else None
    src_meta_cand = meta_cand.get("metric_source") if isinstance(meta_cand, dict) else None
    if src_meta_base and src_meta_cand and src_meta_base != src_meta_cand:
        msg = (
            f"metric_source mismatch: baseline={src_meta_base!r} candidate={src_meta_cand!r}; "
            f"refuse to compare across sources (TOPO-05 fail-closed)"
        )
        raise ValueError(msg)  # metric_source mismatch

    # Secondary guard: _read_p99 post-block-key equality. Runs after the meta check
    # passes; catches the case where meta-sources match (or are absent) but the post
    # block exposes different p99 keys (e.g. baseline has rrul_p99_latency_ms,
    # candidate has controller_rate_p99_mbps). This is the guard that closes G4
    # against today's committed baseline.
    pre, src_pre = _read_p99(baseline["post"])
    cur, src_cur = _read_p99(candidate["post"])
    if src_pre != src_cur:
        msg = (
            f"metric_source mismatch (post-block keys): baseline={src_pre!r} candidate={src_cur!r}; "
            f"refuse to compare across sources (TOPO-05 fail-closed)"
        )
        raise ValueError(msg)  # metric_source mismatch

    pct = ((cur - pre) / pre) * 100.0 if pre > 0 else (0.0 if cur == 0 else float("inf"))
    if src_pre == "controller_rate_p99_mbps":
        # For throughput metric, "regression" means lower-than-baseline; invert sign so the
        # threshold compares consistently against threshold_pct as "% worse than baseline".
        pct = -pct
    _log_info(f"RRUL comparison source={src_pre}")
    if pct > threshold_pct:
        return False, (
            f"RRUL p99 regression: baseline={pre:.2f} current={cur:.2f} "
            f"delta=+{pct:.1f}% > {threshold_pct}% (source: {src_pre})"
        )
    return True, f"RRUL p99: {pct:+.1f}% (within +/-{threshold_pct}%) (source: {src_pre})"


def check_restart_rate(
    baseline_rate_per_hour: float, current_rate_per_hour: float, threshold_pct: float
) -> tuple[bool, str]:
    baseline_rate_per_hour = float(baseline_rate_per_hour)
    current_rate_per_hour = float(current_rate_per_hour)
    if baseline_rate_per_hour == 0.0:
        if current_rate_per_hour > 0.0:
            return False, (
                f"Daemon restart-rate: baseline=0.00/h current={current_rate_per_hour:.2f}/h "
                f"(zero-baseline policy: any restart triggers breach)"
            )
        return True, "Daemon restart-rate: 0.00/h (matches baseline)"
    pct = ((current_rate_per_hour - baseline_rate_per_hour) / baseline_rate_per_hour) * 100.0
    if pct > threshold_pct:
        return False, (
            f"Daemon restart-rate: baseline={baseline_rate_per_hour:.2f}/h "
            f"current={current_rate_per_hour:.2f}/h delta=+{pct:.1f}% > {threshold_pct}%"
        )
    return True, (
        f"Daemon restart-rate: {current_rate_per_hour:.2f}/h "
        f"(baseline {baseline_rate_per_hour:.2f}/h, +{pct:.1f}%)"
    )


def check_zone_transitions(
    soak_ndjson_path: str, baseline_rate_per_hour: float, threshold_pct: float
) -> tuple[bool, str]:
    timed_samples: list[tuple[float, str]] = []
    lines_seen = 0
    parsed_rows = 0
    rows_with_zone = 0
    with open(soak_ndjson_path, encoding="utf-8") as fh:
        for raw_line in fh:
            line = raw_line.strip()
            if not line:
                continue
            lines_seen += 1
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(obj, dict):
                continue
            parsed_rows += 1
            zone = obj.get("last_zone")
            if zone is None:
                continue
            rows_with_zone += 1
            t = obj.get("t_monotonic")
            if not isinstance(t, (int, float)):
                continue
            timed_samples.append((float(t), str(zone)))

    if lines_seen == 0:
        raise InsufficientSoakSamples(
            f"insufficient valid soak samples: soak NDJSON is empty ({soak_ndjson_path})"
        )
    if parsed_rows == 0:
        raise MalformedSoakInput(
            f"no valid soak rows: every non-blank line in {soak_ndjson_path} failed JSON parsing"
        )
    if rows_with_zone > 0 and not timed_samples:
        raise InsufficientSoakSamples(
            f"soak rows missing t_monotonic: {rows_with_zone} row(s) had last_zone but none had numeric t_monotonic"
        )
    if len(timed_samples) < 2:
        raise InsufficientSoakSamples(
            f"insufficient valid soak samples: need >= 2 rows with both last_zone and t_monotonic, got {len(timed_samples)}"
        )

    timed_samples.sort(key=lambda pair: pair[0])
    zones = [z for _, z in timed_samples]
    ts = [t for t, _ in timed_samples]
    transitions = sum(1 for i in range(1, len(zones)) if zones[i] != zones[i - 1])
    elapsed_s = ts[-1] - ts[0]
    if elapsed_s <= 0:
        raise InsufficientSoakSamples(
            f"soak NDJSON has no positive t_monotonic duration "
            f"(elapsed_s={elapsed_s!r}); need a real timed window "
            f"(first_t={ts[0]!r} last_t={ts[-1]!r})"
        )
    hours = elapsed_s / 3600.0
    actual = transitions / hours
    baseline_rate_per_hour = float(baseline_rate_per_hour)
    if baseline_rate_per_hour == 0.0:
        if actual > 0.0:
            return False, (
                f"Pressure-state transition-rate: baseline=0.00/h current={actual:.2f}/h "
                f"(zero-baseline policy)"
            )
        return True, "Pressure-state transition-rate: 0.00/h (matches baseline)"
    pct = ((actual - baseline_rate_per_hour) / baseline_rate_per_hour) * 100.0
    if pct > threshold_pct:
        return False, (
            f"Pressure-state transition-rate: baseline={baseline_rate_per_hour:.2f}/h "
            f"current={actual:.2f}/h delta=+{pct:.1f}% > {threshold_pct}%"
        )
    return True, (
        f"Pressure-state transition-rate: {actual:.2f}/h "
        f"(baseline {baseline_rate_per_hour:.2f}/h, +{pct:.1f}%)"
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Phase 206 rollback gate core")
    parser.add_argument("--baseline", required=True)
    parser.add_argument("--candidate", required=True)
    parser.add_argument("--soak-ndjson")
    parser.add_argument("--restart-counter-start", type=int)
    parser.add_argument("--restart-counter-end", type=int)
    parser.add_argument("--window-hours", type=float)
    parser.add_argument("--mode", choices=("predeploy", "post-soak"), default="predeploy")
    parser.add_argument("--journal-since")
    parser.add_argument(
        "--allow-local-baseline-override",
        action="store_true",
        help=argparse.SUPPRESS,  # test-only; not for production operators
    )
    return parser


def _apply_override(args: argparse.Namespace) -> int | None:
    """Apply PHASE206_LOCAL_BASELINE_OVERRIDE only when explicitly allowed.

    Returns EXIT_ABORT (int) when the env var is set but the opt-in CLI flag is
    absent. Returns None on success (override applied or env var unset).
    The caller in main() MUST treat a non-None return as an abort.
    """
    override = os.environ.get("PHASE206_LOCAL_BASELINE_OVERRIDE")
    if not override:
        return None
    if not getattr(args, "allow_local_baseline_override", False):
        _log_abort(
            "ERROR: PHASE206_LOCAL_BASELINE_OVERRIDE is set but "
            "--allow-local-baseline-override was not passed; "
            "local baseline override is not allowed in production gate-check"
        )
        return EXIT_ABORT
    with Path(override).open(encoding="utf-8") as fh:
        data = json.load(fh)
    for attr in ("restart_counter_start", "restart_counter_end", "window_hours"):
        if attr in data:
            _log_info(f"applying local baseline override: {attr}={data[attr]!r}")
            setattr(args, attr, data[attr])
    return None


def main(argv: list[str] | None = None) -> int:  # noqa: C901
    args = _parser().parse_args(argv)
    rc = _apply_override(args)
    if rc is not None:
        return rc
    if args.journal_since:
        if not re.match(r"^[0-9TZ:+_. -]+$", args.journal_since):
            _log_info(f"journal-since supplied for audit: {args.journal_since}")
        else:
            _log_info(f"journal-since={args.journal_since}")

    try:
        baseline = _read_json(args.baseline)
        candidate = _read_json(args.candidate)
    except Exception as exc:  # noqa: BLE001 - CLI fail-closed path includes parser details.
        _log_abort(f"ERROR: failed to read baseline/candidate JSON: {exc}")
        return EXIT_ABORT

    gb = baseline.get("gate_baseline", {})
    if not isinstance(gb, dict):
        gb = {}

    if args.mode == "post-soak":
        if args.soak_ndjson is None:
            _log_abort("ERROR: --mode post-soak requires --soak-ndjson")
            return EXIT_ABORT
        if (
            args.restart_counter_start is None
            or args.restart_counter_end is None
            or args.window_hours is None
        ):
            _log_abort(
                "ERROR: --mode post-soak requires --restart-counter-start and "
                "--restart-counter-end and --window-hours"
            )
            return EXIT_ABORT
        if (
            "restart_rate_per_hour_baseline" not in gb
            or "transition_rate_per_hour_baseline" not in gb
        ):
            _log_abort(
                "ERROR: --mode post-soak requires gate_baseline with both "
                "restart_rate_per_hour_baseline and transition_rate_per_hour_baseline"
            )
            return EXIT_ABORT

    results: list[tuple[bool, str]] = []
    try:
        results.append(check_rrul_p99(baseline, candidate, RRUL_P99_REGRESSION_PCT))
    except Exception as exc:  # noqa: BLE001 - malformed input is an ABORT, not traceback.
        _log_abort(f"ERROR: failed RRUL p99 check: {exc}")
        return EXIT_ABORT

    start_present = args.restart_counter_start is not None
    end_present = args.restart_counter_end is not None
    if start_present != end_present:
        _log_abort(
            "ERROR: restart counters must be supplied together "
            f"(got start={args.restart_counter_start!r} end={args.restart_counter_end!r}); "
            "both --restart-counter-start and --restart-counter-end are required or neither"
        )
        return EXIT_ABORT
    restart_inputs_present = start_present and end_present
    baseline_restart = gb.get("restart_rate_per_hour_baseline")
    if restart_inputs_present and baseline_restart is None:
        _log_abort(
            "ERROR: --restart-counter-start/--restart-counter-end provided but "
            "gate_baseline missing restart_rate_per_hour_baseline; cannot enforce TOPO-05"
        )
        return EXIT_ABORT
    if restart_inputs_present and baseline_restart is not None:
        if args.window_hours is None or args.window_hours <= 0:
            _log_abort(
                f"ERROR: --window-hours must be > 0 when restart-counter inputs present "
                f"(got {args.window_hours!r})"
            )
            return EXIT_ABORT
        if args.restart_counter_end < args.restart_counter_start:
            _log_abort(
                f"ERROR: restart_counter_end ({args.restart_counter_end}) < restart_counter_start ({args.restart_counter_start}); "  # noqa: E501
                f"counter must be monotonic non-decreasing (systemd NRestarts only grows)"
            )
            return EXIT_ABORT
        current = (args.restart_counter_end - args.restart_counter_start) / args.window_hours
        results.append(check_restart_rate(baseline_restart, current, RESTART_RATE_INCREASE_PCT))
    else:
        _log_info("restart-rate check skipped (no --restart-counter-* inputs)")

    soak_present = args.soak_ndjson is not None
    baseline_transition = gb.get("transition_rate_per_hour_baseline")
    if soak_present and baseline_transition is None:
        _log_abort(
            "ERROR: --soak-ndjson provided but gate_baseline missing "
            "transition_rate_per_hour_baseline; cannot enforce TOPO-05"
        )
        return EXIT_ABORT
    if soak_present and baseline_transition is not None:
        try:
            results.append(
                check_zone_transitions(
                    args.soak_ndjson, baseline_transition, TRANSITION_RATE_INCREASE_PCT
                )
            )
        except Exception as exc:  # noqa: BLE001 - malformed soak input fail-closed.
            _log_abort(f"ERROR: failed transition-rate check: {exc}")
            return EXIT_ABORT
    else:
        _log_info("transition-rate check skipped (no --soak-ndjson input)")

    blocked = False
    for passed, message in results:
        if passed:
            _log_info(message)
        else:
            _log_block(message)
            blocked = True
    if blocked:
        return EXIT_BLOCK
    _log_info("PASS: Phase 206 rollback gates clear")
    return EXIT_PASS


if __name__ == "__main__":
    raise SystemExit(main())
