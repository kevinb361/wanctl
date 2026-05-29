#!/usr/bin/env bash
# Phase 215 Spectrum upload-reclaim gate.
#
# Exit-code contract for callers running under set -e:
#   EXIT_PASS=0  verdict="pass"
#   EXIT_FAIL=1  verdict="fail"
#   EXIT_ABORT=2 verdict="abort" or verdict="void"
#
# Callers MUST capture rc explicitly (for example: set +e; gate; rc=$?; set -e)
# and branch on verdict.json. Nonzero exits must never short-circuit rollback.

set -euo pipefail

EXIT_PASS=0
EXIT_FAIL=1
EXIT_ABORT=2

print_help() {
    cat <<'HELP'
Phase 215 Spectrum upload-reclaim gate.

Required scoring inputs:
  --candidate-extract PATH   phase214-extract.py JSON for leg B.
  --candidate-health PATH    /health NDJSON for leg B loaded window.

Optional baseline inputs:
  --baseline-extract PATH    phase214-extract.py JSON for leg A. When present,
                             thresholds are derived from this same-session leg.
  --baseline-health PATH     /health NDJSON for leg A (recorded in verdict metadata).

Optional output/preflight:
  --output-dir PATH          Directory for verdict.json (default: current dir).
  --expected-ceiling MBPS    Expected deployed upload ceiling (default: 20).
  --remote-yaml TARGET:PATH  Read deployed YAML over ssh and ABORT if ceiling
                             does not match --expected-ceiling.

Static fallback / sanity-check only:
  BASELINE_REF_P95=53.4, BASELINE_REF_P99=69.0, BASELINE_REF_MEDIAN=11.43
  FALLBACK_P95_BOUND=58.7, FALLBACK_P99_BOUND=75.9, FALLBACK_WIN_BOUND=12.9

VOID maps to EXIT_ABORT=2. FAIL maps to EXIT_FAIL=1. PASS maps to EXIT_PASS=0.
HELP
}

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
    print_help
    exit "$EXIT_PASS"
fi

require_command() {
    local tool="$1"
    if ! command -v "$tool" >/dev/null 2>&1; then
        printf 'ABORT: required command not found: %s\n' "$tool" >&2
        exit "$EXIT_ABORT"
    fi
}

write_parse_abort() {
    local reason="$1"
    mkdir -p "$OUTPUT_DIR"
    python3 - "$OUTPUT_DIR/verdict.json" "$reason" <<'PY'
import json
import sys

path, reason = sys.argv[1:]
with open(path, "w", encoding="utf-8") as handle:
    json.dump({"verdict": "abort", "exit_code": 2, "reason": reason}, handle, indent=2, sort_keys=True)
    handle.write("\n")
PY
}

need_value() {
    if [[ "$#" -lt 2 || -z "${2:-}" || "${2:-}" == --* ]]; then
        printf 'ABORT: %s requires a value\n' "$1" >&2
        write_parse_abort "missing_option_value:${1}"
        exit "$EXIT_ABORT"
    fi
}

BASELINE_EXTRACT=""
CANDIDATE_EXTRACT=""
BASELINE_HEALTH=""
CANDIDATE_HEALTH=""
OUTPUT_DIR="."
EXPECTED_CEILING="20"
REMOTE_YAML="${PHASE215_REMOTE_YAML_SSH:-}"

while [[ "$#" -gt 0 ]]; do
    case "$1" in
        --baseline-extract)
            need_value "$@"
            BASELINE_EXTRACT="$2"
            shift 2
            ;;
        --candidate-extract)
            need_value "$@"
            CANDIDATE_EXTRACT="$2"
            shift 2
            ;;
        --baseline-health)
            need_value "$@"
            BASELINE_HEALTH="$2"
            shift 2
            ;;
        --candidate-health)
            need_value "$@"
            CANDIDATE_HEALTH="$2"
            shift 2
            ;;
        --output-dir)
            need_value "$@"
            OUTPUT_DIR="$2"
            shift 2
            ;;
        --expected-ceiling)
            need_value "$@"
            EXPECTED_CEILING="$2"
            shift 2
            ;;
        --remote-yaml)
            need_value "$@"
            REMOTE_YAML="$2"
            shift 2
            ;;
        *)
            printf 'ABORT: unknown argument: %s\n' "$1" >&2
            write_parse_abort "unknown_argument:${1}"
            exit "$EXIT_ABORT"
            ;;
    esac
done

if [[ -z "$CANDIDATE_EXTRACT" || -z "$CANDIDATE_HEALTH" ]]; then
    printf 'ABORT: --candidate-extract and --candidate-health are required\n' >&2
    write_parse_abort "missing_required_candidate_inputs"
    exit "$EXIT_ABORT"
fi

require_command python3
mkdir -p "$OUTPUT_DIR"
VERDICT="$OUTPUT_DIR/verdict.json"

write_preflight_abort() {
    local reason="$1"
    python3 - "$VERDICT" "$reason" <<'PY'
import json
import sys

path, reason = sys.argv[1:]
json.dump({"verdict": "abort", "exit_code": 2, "reason": reason}, open(path, "w", encoding="utf-8"), indent=2, sort_keys=True)
PY
}

if [[ -n "$REMOTE_YAML" ]]; then
    require_command ssh
    remote_host="${REMOTE_YAML%%:*}"
    remote_path="${REMOTE_YAML#*:}"
    if [[ "$remote_host" == "$remote_path" || ! "$remote_path" =~ ^/[A-Za-z0-9._/-]+$ ]]; then
        printf 'ABORT: --remote-yaml must be host:/absolute/safe/path\n' >&2
        write_preflight_abort "remote_yaml_invalid"
        exit "$EXIT_ABORT"
    fi
    if ! deployed_ceiling="$(ssh "$remote_host" "sudo -n python3 - '$remote_path'" <<'PY'
import re
import sys
from pathlib import Path

text = Path(sys.argv[1]).read_text(encoding="utf-8")
inside = False
for line in text.splitlines():
    if re.match(r"^  upload:", line):
        inside = True
        continue
    if inside and re.match(r"^  [A-Za-z_]+:", line):
        inside = False
    if inside:
        match = re.match(r"^    ceiling_mbps:\s*([0-9.]+)", line)
        if match:
            print(match.group(1))
            raise SystemExit(0)
raise SystemExit(1)
PY
    )"; then
        write_preflight_abort "deployed_ceiling_unreadable"
        exit "$EXIT_ABORT"
    fi
    if [[ "$deployed_ceiling" != "$EXPECTED_CEILING" ]]; then
        python3 - "$VERDICT" "$EXPECTED_CEILING" "$deployed_ceiling" <<'PY'
import json, sys
path, expected, got = sys.argv[1:]
json.dump({"verdict": "abort", "exit_code": 2, "reason": "deployed_ceiling_mismatch", "expected_ceiling_mbps": expected, "deployed_ceiling_mbps": got}, open(path, "w", encoding="utf-8"), indent=2, sort_keys=True)
PY
        exit "$EXIT_ABORT"
    fi
fi

python3 - "$VERDICT" "$BASELINE_EXTRACT" "$CANDIDATE_EXTRACT" "$BASELINE_HEALTH" "$CANDIDATE_HEALTH" <<'PY'
from __future__ import annotations

import json
import math
import sys
from pathlib import Path
from typing import Any

EXIT_PASS = 0
EXIT_FAIL = 1
EXIT_ABORT = 2

BASELINE_REF_P95 = 53.4
BASELINE_REF_P99 = 69.0
BASELINE_REF_MEDIAN = 11.43
FALLBACK_P95_BOUND = 58.7
FALLBACK_P99_BOUND = 75.9
FALLBACK_WIN_BOUND = 12.9
WARN_BLOAT_MS = 75.0
WARN_BLOAT_CONSECUTIVE_SAMPLES = 5
SIGNAL_OUTLIER_RATE_P90_VOID = 0.30
ALERT_FIRE_BUDGET = 3
ROLLBACK_PROTOCOL = "Snapshot A: restore ceiling_mbps=18, deploy spectrum, restart wanctl@spectrum.service, verify config snapshot and canary-check"

verdict_path = Path(sys.argv[1])
baseline_extract_path = sys.argv[2]
candidate_extract_path = sys.argv[3]
baseline_health_path = sys.argv[4]
candidate_health_path = sys.argv[5]


def load_json(path: str) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def read_ndjson(path: str) -> list[dict[str, Any]]:
    samples = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if line.strip():
            samples.append(json.loads(line))
    return samples


def nested(sample: dict[str, Any], *keys: str) -> Any:
    cur: Any = sample
    for key in keys:
        if isinstance(cur, list):
            try:
                cur = cur[int(key)]
            except (ValueError, IndexError):
                return None
        elif isinstance(cur, dict):
            cur = cur.get(key)
        else:
            return None
    return cur


def number(value: Any) -> float | None:
    if isinstance(value, (int, float)) and math.isfinite(float(value)):
        return float(value)
    return None


def floor_counter(sample: dict[str, Any]) -> int | None:
    value = nested(sample, "wans", "0", "upload", "floor_hit_cycles_total")
    if value is None:
        value = nested(sample, "upload", "floor_hit_cycles_total")
    return int(value) if isinstance(value, int) and value >= 0 else None


def floor_delta(samples: list[dict[str, Any]]) -> int | None:
    counters = [value for sample in samples if (value := floor_counter(sample)) is not None]
    if len(counters) < 2:
        return None
    return max(0, counters[-1] - counters[0])


def sample_number(sample: dict[str, Any], key: str) -> float | None:
    value = nested(sample, "wans", "0", key)
    if value is None:
        value = sample.get(key)
    return number(value)


def upload_number(sample: dict[str, Any], key: str) -> float | None:
    value = nested(sample, "wans", "0", "upload", key)
    if value is None:
        value = nested(sample, "upload", key)
    return number(value)


def measurement_state(sample: dict[str, Any]) -> str | None:
    value = nested(sample, "wans", "0", "measurement_state")
    if value is None:
        value = sample.get("measurement_state")
    return value if isinstance(value, str) else None


def p_index(values: list[float], percentile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(len(ordered) * percentile))]


def max_sustained_bloat(samples: list[dict[str, Any]]) -> tuple[float | None, int]:
    max_excursion = None
    current = 0
    longest = 0
    for sample in samples:
        load = sample_number(sample, "load_rtt_ms")
        baseline = sample_number(sample, "baseline_rtt_ms")
        if load is None or baseline is None:
            current = 0
            continue
        excursion = load - baseline
        max_excursion = excursion if max_excursion is None else max(max_excursion, excursion)
        if excursion > WARN_BLOAT_MS:
            current += 1
            longest = max(longest, current)
        else:
            current = 0
    return max_excursion, longest


def spectrum_alert_events(samples: list[dict[str, Any]]) -> int:
    count = 0
    for sample in samples:
        events = sample.get("alert_fire_events") or sample.get("alerts") or []
        if not isinstance(events, list):
            continue
        for event in events:
            if isinstance(event, dict) and event.get("wan_name") == "spectrum":
                count += 1
    return count


def write(payload: dict[str, Any], code: int) -> int:
    payload.setdefault("exit_code", code)
    payload.setdefault("rollback_protocol", ROLLBACK_PROTOCOL)
    verdict_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return code


try:
    candidate = load_json(candidate_extract_path)
    candidate_health = read_ndjson(candidate_health_path)
    baseline = load_json(baseline_extract_path) if baseline_extract_path else None
except Exception as exc:  # noqa: BLE001 - extraction/read failure is a scored VOID/abort boundary.
    raise SystemExit(write({"verdict": "void", "reason": f"candidate_or_baseline_unreadable:{exc}"}, EXIT_ABORT))

try:
    if baseline:
        baseline_p95 = float(baseline["latency"]["p95_ms"])
        baseline_p99 = float(baseline["latency"]["p99_ms"])
        baseline_median = float(baseline["upload_throughput"]["throughput_median_mbps"])
        derived_p95_bound = baseline_p95 * 1.10
        derived_p99_bound = baseline_p99 * 1.10
        derived_win_bound = baseline_median + 1.5
        threshold_source = "baseline_extract"
    else:
        baseline_p95 = BASELINE_REF_P95
        baseline_p99 = BASELINE_REF_P99
        baseline_median = BASELINE_REF_MEDIAN
        derived_p95_bound = FALLBACK_P95_BOUND
        derived_p99_bound = FALLBACK_P99_BOUND
        derived_win_bound = FALLBACK_WIN_BOUND
        threshold_source = "static_fallback"

    candidate_p95 = float(candidate["latency"]["p95_ms"])
    candidate_p99 = float(candidate["latency"]["p99_ms"])
    candidate_throughput = float(candidate["upload_throughput"]["throughput_median_mbps"])
except (KeyError, TypeError, ValueError) as exc:
    raise SystemExit(write({"verdict": "void", "reason": f"required_metric_missing_or_invalid:{exc}"}, EXIT_ABORT))
floor_hit_delta = floor_delta(candidate_health)
alert_fire_delta = spectrum_alert_events(candidate_health)
outliers = [value for sample in candidate_health if (value := upload_number(sample, "signal_outlier_rate")) is not None]
if not outliers:
    outliers = [value for sample in candidate_health if (value := sample_number(sample, "signal_outlier_rate")) is not None]
signal_outlier_rate_p90 = p_index(outliers, 0.90)
collapsed = any(measurement_state(sample) == "collapsed" for sample in candidate_health)
max_excursion, sustained_bloat_count = max_sustained_bloat(candidate_health)

fallback_note = "not_checked_static_fallback_in_use"
if threshold_source == "baseline_extract":
    divergences = [
        abs(derived_p95_bound - FALLBACK_P95_BOUND) / FALLBACK_P95_BOUND,
        abs(derived_p99_bound - FALLBACK_P99_BOUND) / FALLBACK_P99_BOUND,
        abs(derived_win_bound - FALLBACK_WIN_BOUND) / FALLBACK_WIN_BOUND,
    ]
    fallback_note = "derived_within_15pct_of_static_fallback" if max(divergences) <= 0.15 else "derived_diverges_from_static_fallback_gt_15pct"

common = {
    "verdict": None,
    "threshold_source": threshold_source,
    "candidate_p95_ms": candidate_p95,
    "candidate_p99_ms": candidate_p99,
    "candidate_throughput_median_mbps": candidate_throughput,
    "floor_hit_delta": floor_hit_delta,
    "alert_fire_delta": alert_fire_delta,
    "alert_fire_source": "candidate_health_ndjson_spectrum_events",
    "max_load_rtt_excursion_ms": max_excursion,
    "sustained_bloat_sample_count": sustained_bloat_count,
    "signal_outlier_rate_p90": signal_outlier_rate_p90,
    "measurement_state_collapsed": collapsed,
    "warn_bloat_ms": WARN_BLOAT_MS,
    "warn_bloat_consecutive_samples": WARN_BLOAT_CONSECUTIVE_SAMPLES,
    "signal_outlier_rate_p90_void_threshold": SIGNAL_OUTLIER_RATE_P90_VOID,
    "alert_fire_budget": ALERT_FIRE_BUDGET,
    "derived_p95_bound": derived_p95_bound,
    "derived_p99_bound": derived_p99_bound,
    "derived_win_bound": derived_win_bound,
    "baseline_p95_ms_used": baseline_p95,
    "baseline_p99_ms_used": baseline_p99,
    "baseline_upload_median_mbps_used": baseline_median,
    "BASELINE_REF_P95": BASELINE_REF_P95,
    "BASELINE_REF_P99": BASELINE_REF_P99,
    "BASELINE_REF_MEDIAN": BASELINE_REF_MEDIAN,
    "FALLBACK_P95_BOUND": FALLBACK_P95_BOUND,
    "FALLBACK_P99_BOUND": FALLBACK_P99_BOUND,
    "FALLBACK_WIN_BOUND": FALLBACK_WIN_BOUND,
    "derived_vs_fallback_sanity_note": fallback_note,
}

if collapsed or (signal_outlier_rate_p90 is not None and signal_outlier_rate_p90 >= SIGNAL_OUTLIER_RATE_P90_VOID):
    common.update({"verdict": "void", "reason": "collapsed_measurement_window"})
    raise SystemExit(write(common, EXIT_ABORT))

fail_reasons = []
if candidate_p95 > derived_p95_bound:
    fail_reasons.append("p95_latency_regression")
if candidate_p99 > derived_p99_bound:
    fail_reasons.append("p99_latency_regression")
if floor_hit_delta is None or floor_hit_delta > 0:
    fail_reasons.append("floor_hit_delta")
if alert_fire_delta > ALERT_FIRE_BUDGET:
    fail_reasons.append("spectrum_alert_fire_budget")
if sustained_bloat_count >= WARN_BLOAT_CONSECUTIVE_SAMPLES:
    fail_reasons.append("sustained_warn_bloat")
if candidate_throughput < derived_win_bound:
    fail_reasons.append("throughput_win_not_met")

if fail_reasons:
    common.update({"verdict": "fail", "reason": ",".join(fail_reasons)})
    raise SystemExit(write(common, EXIT_FAIL))

common.update({"verdict": "pass", "reason": "throughput_win_with_no_rollback_gates"})
raise SystemExit(write(common, EXIT_PASS))
PY
