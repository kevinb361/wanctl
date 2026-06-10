#!/usr/bin/env bash
# phase231-migration-held.sh - Read-only migration-held evaluator for SOAK-01.
# Usage: scripts/phase231-migration-held.sh [--wan spectrum|att|all] [--window-hours N] [--json]

set -euo pipefail

TARGETS=(
    "kevin@10.10.110.223|spectrum|10.10.110.223|spec-router|spec-modem"
    "kevin@10.10.110.223|att|10.10.110.227|att-router|att-modem"
)

HEALTH_PORT=9101
WAN_FILTER="all"
WINDOW_HOURS=24
JSON_MODE="0"
MIGRATION_SINCE_UTC="2026-06-08 00:00:00 UTC"

C3_MAX_TOTAL=5
C3_MAX_DISTINCT_HOURS=2
C3_CLEAN_TRAILING_HOURS=6

SSH_OPTS=(-o ConnectTimeout=10 -o BatchMode=yes)

usage() {
    cat <<'EOF'
Usage: scripts/phase231-migration-held.sh [options]

Read-only SOAK-01 evaluator for the 2026-06-08 cake-autorate migration.

Options:
  --wan spectrum|att|all   WAN to evaluate (default: all)
  --window-hours N         Metrics ingestion trailing window in hours (default: 24)
  --json                   Emit JSON only
  --help, -h               Show this help

Checks:
  bridge_health        HTTP 200 and JSON status == healthy
  metrics_ingestion    sqlite3 -readonly SELECT count in trailing window, pass iff rows > 0
  no_sustained_errors  journal err scan since 2026-06-08 00:00:00 UTC using objective C3 constants
  qdisc_envelope       tc qdisc show bandwidth within repo-configured envelope
EOF
}

require_command() {
    local cmd="$1"
    if ! command -v "$cmd" >/dev/null 2>&1; then
        echo "ERROR: required command missing: $cmd" >&2
        exit 2
    fi
}

validate_window_hours() {
    if [[ ! "$WINDOW_HOURS" =~ ^[1-9][0-9]*$ ]]; then
        echo "ERROR: --window-hours must be a positive integer" >&2
        exit 2
    fi
}

validate_wan() {
    case "$WAN_FILTER" in
        spectrum|att|all) ;;
        *) echo "ERROR: --wan must be spectrum, att, or all" >&2; exit 2 ;;
    esac
}

config_path_for_wan() {
    printf 'configs/cake-autorate/config.%s.sh\n' "$1"
}

config_value() {
    local wan="$1" key="$2" path value
    path="$(config_path_for_wan "$wan")"
    if [[ ! -r "$path" ]]; then
        echo "ERROR: missing config: $path" >&2
        return 1
    fi
    value="$(grep -E "^${key}=" "$path" | tail -n 1 | cut -d= -f2- | tr -d '"' | tr -d "'")"
    if [[ -z "$value" ]]; then
        echo "ERROR: missing ${key} in ${path}" >&2
        return 1
    fi
    printf '%s\n' "$value"
}

ssh_readonly() {
    local ssh_target="$1" remote_cmd="$2"
    ssh "${SSH_OPTS[@]}" "$ssh_target" "$remote_cmd"
}

json_string() {
    python3 -c 'import json, sys; print(json.dumps(sys.argv[1]))' "$1"
}

status_json() {
    local pass="$1" evidence="$2" error="$3"
    python3 - "$pass" "$evidence" "$error" <<'PY'
import json
import sys

passed, evidence, error = sys.argv[1:]
payload = {"pass": passed == "true", "evidence": evidence}
if error:
    payload["error"] = error
print(json.dumps(payload, separators=(",", ":")))
PY
}

health_check() {
    local ssh_target="$1" health_ip="$2" raw status http_code pass="false" error=""
    raw=""
    if raw="$(ssh_readonly "$ssh_target" "curl -fsS --max-time 10 -w '\n%{http_code}' http://${health_ip}:${HEALTH_PORT}/health" 2>&1)"; then
        http_code="${raw##*$'\n'}"
        raw="${raw%$'\n'*}"
        status="$(printf '%s' "$raw" | python3 -c 'import json,sys; print((json.load(sys.stdin).get("status") or ""))' 2>/dev/null || true)"
        if [[ "$http_code" == "200" && "$status" == "healthy" ]]; then
            pass="true"
        fi
        python3 - "$pass" "$http_code" "$raw" <<'PY'
import json
import sys

passed, http_code, raw = sys.argv[1:]
try:
    payload = json.loads(raw)
except json.JSONDecodeError:
    payload = raw
print(json.dumps({"pass": passed == "true", "evidence": {"http_code": http_code, "payload": payload}}, separators=(",", ":")))
PY
        return 0
    fi
    error="$raw"
    status_json "false" "" "$error"
}

metrics_check() {
    local ssh_target="$1" wan="$2" db="/var/lib/wanctl/metrics-${wan}.db" rows pass="false" query remote_cmd
    query="SELECT COUNT(*) FROM metrics WHERE timestamp >= strftime('%s','now','-${WINDOW_HOURS} hours')"
    remote_cmd="sudo -n sqlite3 -readonly '${db}' \"${query}\""
    if rows="$(ssh_readonly "$ssh_target" "$remote_cmd" 2>&1)" && [[ "$rows" =~ ^[0-9]+$ ]]; then
        if [[ "$rows" -gt 0 ]]; then
            pass="true"
        fi
        python3 - "$pass" "$rows" "$WINDOW_HOURS" "$db" <<'PY'
import json
import sys

passed, rows, window_hours, db = sys.argv[1:]
print(json.dumps({
    "pass": passed == "true",
    "rows": int(rows),
    "window_hours": int(window_hours),
    "evidence": {"db": db, "table": "metrics", "timestamp_column": "timestamp"},
}, separators=(",", ":")))
PY
        return 0
    fi
    python3 - "$rows" "$WINDOW_HOURS" "$db" <<'PY'
import json
import sys

error, window_hours, db = sys.argv[1:]
print(json.dumps({
    "pass": False,
    "rows": None,
    "window_hours": int(window_hours),
    "evidence": {"db": db, "table": "metrics", "timestamp_column": "timestamp"},
    "error": error,
}, separators=(",", ":")))
PY
}

c3_units_for_wan() {
    case "$1" in
        spectrum)
            printf '%s\n' \
                "cake-autorate-spectrum.service" \
                "cake-autorate-spectrum-state-bridge.service" \
                "silicom-bypass-watchdog@spectrum.service" \
                "steering.service"
            ;;
        att)
            printf '%s\n' \
                "cake-autorate-att.service" \
                "cake-autorate-att-state-bridge.service" \
                "silicom-bypass-watchdog-cake-autorate-att.service" \
                "steering.service"
            ;;
    esac
}

journal_check() {
    local ssh_target="$1" wan="$2" unit output unit_file units_file overall="true" tmpdir
    tmpdir="$3"
    units_file="${tmpdir}/${wan}-units.txt"
    c3_units_for_wan "$wan" >"$units_file"
    while IFS= read -r unit; do
        unit_file="${tmpdir}/${wan}-${unit//[^A-Za-z0-9_.-]/_}.log"
        if output="$(ssh_readonly "$ssh_target" "sudo -n journalctl -u '${unit}' --since '${MIGRATION_SINCE_UTC}' -p err --no-pager -o short-iso" 2>&1)"; then
            printf '%s\n' "$output" | grep -v '^-- No entries --$' | sed '/^[[:space:]]*$/d' >"$unit_file" || true
        else
            printf '%s\n' "$output" >"$unit_file"
            overall="false"
        fi
    done <"$units_file"

    python3 - "$units_file" "$tmpdir" "$wan" "$overall" "$C3_MAX_TOTAL" "$C3_MAX_DISTINCT_HOURS" "$C3_CLEAN_TRAILING_HOURS" <<'PY'
from __future__ import annotations

import datetime as dt
import json
import sys
from pathlib import Path

units_file, tmpdir, wan, transport_ok, max_total, max_hours, clean_hours = sys.argv[1:]
max_total_i = int(max_total)
max_hours_i = int(max_hours)
clean_hours_i = int(clean_hours)
now = dt.datetime.now(dt.timezone.utc)
units = [line.strip() for line in Path(units_file).read_text().splitlines() if line.strip()]
unit_results = []
overall = transport_ok == "true"

def parse_ts(line: str) -> dt.datetime | None:
    token = line.split(maxsplit=1)[0] if line.strip() else ""
    try:
        if token.endswith("Z"):
            return dt.datetime.fromisoformat(token.replace("Z", "+00:00"))
        parsed = dt.datetime.fromisoformat(token)
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=dt.timezone.utc)
        return parsed.astimezone(dt.timezone.utc)
    except ValueError:
        return None

for unit in units:
    path = Path(tmpdir) / f"{wan}-{''.join(ch if ch.isalnum() or ch in '_.-' else '_' for ch in unit)}.log"
    lines = [line for line in path.read_text(errors="replace").splitlines() if line.strip()]
    parsed = [parse_ts(line) for line in lines]
    hours = {stamp.strftime("%Y-%m-%dT%H") for stamp in parsed if stamp is not None}
    trailing_cutoff = now - dt.timedelta(hours=clean_hours_i)
    trailing = sum(1 for stamp in parsed if stamp is not None and stamp >= trailing_cutoff)
    if not lines:
        passed = True
    else:
        passed = len(lines) <= max_total_i and len(hours) <= max_hours_i and trailing == 0
    if not passed:
        overall = False
    unit_results.append({
        "unit": unit,
        "pass": passed,
        "err_lines": lines,
        "total": len(lines),
        "distinct_utc_hours": sorted(hours),
        "trailing_err_lines": trailing,
    })

print(json.dumps({
    "pass": overall,
    "err_lines": sum(item["total"] for item in unit_results),
    "units": unit_results,
    "rule": {
        "since": "2026-06-08 00:00:00 UTC",
        "C3_MAX_TOTAL": max_total_i,
        "C3_MAX_DISTINCT_HOURS": max_hours_i,
        "C3_CLEAN_TRAILING_HOURS": clean_hours_i,
    },
}, separators=(",", ":")))
PY
}

bandwidth_to_kbps() {
    local token="$1"
    python3 - "$token" <<'PY'
import re
import sys

token = sys.argv[1].strip()
match = re.fullmatch(r"([0-9]+(?:\.[0-9]+)?)(bit|Kbit|Mbit|Gbit)", token)
if not match:
    raise SystemExit(1)
value = float(match.group(1))
scale = {"bit": 0.001, "Kbit": 1, "Mbit": 1000, "Gbit": 1000000}[match.group(2)]
print(int(round(value * scale)))
PY
}

parse_qdisc_kbps() {
    local text="$1"
    python3 - "$text" <<'PY'
import re
import sys

text = sys.argv[1]
match = re.search(r"\bbandwidth\s+([0-9]+(?:\.[0-9]+)?(?:bit|Kbit|Mbit|Gbit))\b", text)
if not match:
    raise SystemExit(1)
token = match.group(1)
unit_match = re.fullmatch(r"([0-9]+(?:\.[0-9]+)?)(bit|Kbit|Mbit|Gbit)", token)
if not unit_match:
    raise SystemExit(1)
value = float(unit_match.group(1))
scale = {"bit": 0.001, "Kbit": 1, "Mbit": 1000, "Gbit": 1000000}[unit_match.group(2)]
print(int(round(value * scale)))
PY
}

qdisc_check() {
    local ssh_target="$1" wan="$2" dl_if="$3" ul_if="$4"
    local min_dl max_dl expected_ul dl_raw ul_raw dl_kbps ul_kbps pass="false" error=""
    min_dl="$(config_value "$wan" min_dl_shaper_rate_kbps)" || min_dl=""
    max_dl="$(config_value "$wan" max_dl_shaper_rate_kbps)" || max_dl=""
    expected_ul="$(config_value "$wan" base_ul_shaper_rate_kbps)" || expected_ul=""
    if [[ -z "$min_dl" || -z "$max_dl" || -z "$expected_ul" ]]; then
        error="failed to parse config envelope"
    elif dl_raw="$(ssh_readonly "$ssh_target" "sudo -n tc qdisc show dev '${dl_if}'" 2>&1)" && ul_raw="$(ssh_readonly "$ssh_target" "sudo -n tc qdisc show dev '${ul_if}'" 2>&1)"; then
        if dl_kbps="$(parse_qdisc_kbps "$dl_raw" 2>/dev/null)" && ul_kbps="$(parse_qdisc_kbps "$ul_raw" 2>/dev/null)"; then
            if [[ "$dl_kbps" -ge "$min_dl" && "$dl_kbps" -le "$max_dl" && "$ul_kbps" -eq "$expected_ul" ]]; then
                pass="true"
            fi
            python3 - "$pass" "$dl_kbps" "$min_dl" "$max_dl" "$ul_kbps" "$expected_ul" "$dl_if" "$ul_if" "$dl_raw" "$ul_raw" <<'PY'
import json
import sys

passed, dl, dl_min, dl_max, ul, ul_expected, dl_if, ul_if, dl_raw, ul_raw = sys.argv[1:]
print(json.dumps({
    "pass": passed == "true",
    "dl_kbps": int(dl),
    "dl_min": int(dl_min),
    "dl_max": int(dl_max),
    "ul_kbps": int(ul),
    "ul_expected": int(ul_expected),
    "evidence": {"dl_if": dl_if, "ul_if": ul_if, "dl_raw": dl_raw, "ul_raw": ul_raw},
}, separators=(",", ":")))
PY
            return 0
        fi
        error="unparseable qdisc bandwidth"
    else
        error="${dl_raw:-}${ul_raw:-}"
    fi
    python3 - "$error" "$min_dl" "$max_dl" "$expected_ul" "$dl_if" "$ul_if" <<'PY'
import json
import sys

error, dl_min, dl_max, ul_expected, dl_if, ul_if = sys.argv[1:]
def maybe_int(value):
    try:
        return int(value)
    except ValueError:
        return None
print(json.dumps({
    "pass": False,
    "dl_kbps": None,
    "dl_min": maybe_int(dl_min),
    "dl_max": maybe_int(dl_max),
    "ul_kbps": None,
    "ul_expected": maybe_int(ul_expected),
    "evidence": {"dl_if": dl_if, "ul_if": ul_if},
    "error": error,
}, separators=(",", ":")))
PY
}

evaluate_wan() {
    local ssh_target="$1" wan="$2" health_ip="$3" dl_if="$4" ul_if="$5" tmpdir="$6"
    local captured health metrics errors qdisc verdict
    captured="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    health="$(health_check "$ssh_target" "$health_ip")"
    metrics="$(metrics_check "$ssh_target" "$wan")"
    errors="$(journal_check "$ssh_target" "$wan" "$tmpdir")"
    qdisc="$(qdisc_check "$ssh_target" "$wan" "$dl_if" "$ul_if")"
    verdict="$(python3 - "$health" "$metrics" "$errors" "$qdisc" <<'PY'
import json
import sys

checks = [json.loads(arg) for arg in sys.argv[1:]]
print("PASS" if all(check.get("pass") is True for check in checks) else "FAIL")
PY
)"
    python3 - "$wan" "$captured" "$health" "$metrics" "$errors" "$qdisc" "$verdict" <<'PY'
import json
import sys

wan, captured, health, metrics, errors, qdisc, verdict = sys.argv[1:]
print(json.dumps({
    "wan": wan,
    "captured_utc": captured,
    "checks": {
        "bridge_health": json.loads(health),
        "metrics_ingestion": json.loads(metrics),
        "no_sustained_errors": json.loads(errors),
        "qdisc_envelope": json.loads(qdisc),
    },
    "verdict": verdict,
}, separators=(",", ":")))
PY
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --wan) WAN_FILTER="${2:-}"; shift 2 ;;
        --window-hours) WINDOW_HOURS="${2:-}"; shift 2 ;;
        --json) JSON_MODE="1"; shift ;;
        --help|-h) usage; exit 0 ;;
        *) echo "ERROR: unknown argument: $1" >&2; usage >&2; exit 2 ;;
    esac
done

validate_wan
validate_window_hours
require_command python3
require_command ssh
require_command grep
require_command sed

tmpdir="$(mktemp -d)"
trap 'rm -rf "$tmpdir"' EXIT

results_file="${tmpdir}/results.ndjson"
exit_code=0
for target in "${TARGETS[@]}"; do
    IFS='|' read -r ssh_target wan health_ip dl_if ul_if <<<"$target"
    if [[ "$WAN_FILTER" != "all" && "$WAN_FILTER" != "$wan" ]]; then
        continue
    fi
    evaluate_wan "$ssh_target" "$wan" "$health_ip" "$dl_if" "$ul_if" "$tmpdir" >>"$results_file"
done

if [[ ! -s "$results_file" ]]; then
    echo "ERROR: no WANs selected" >&2
    exit 2
fi

if [[ "$JSON_MODE" == "1" ]]; then
    python3 - "$results_file" <<'PY'
import json
import sys
from pathlib import Path

rows = [json.loads(line) for line in Path(sys.argv[1]).read_text().splitlines() if line.strip()]
print(json.dumps(rows, indent=2, sort_keys=True))
PY
else
    python3 - "$results_file" <<'PY'
import json
import sys
from pathlib import Path

rows = [json.loads(line) for line in Path(sys.argv[1]).read_text().splitlines() if line.strip()]
for row in rows:
    print(f"{row['wan']}: {row['verdict']} captured={row['captured_utc']}")
    for name, check in row["checks"].items():
        print(f"  {name}: {'PASS' if check.get('pass') else 'FAIL'}")
PY
fi

if python3 - "$results_file" <<'PY'
import json
import sys
from pathlib import Path

rows = [json.loads(line) for line in Path(sys.argv[1]).read_text().splitlines() if line.strip()]
raise SystemExit(0 if all(row.get("verdict") == "PASS" for row in rows) else 1)
PY
then
    exit_code=0
else
    exit_code=1
fi

exit "$exit_code"
