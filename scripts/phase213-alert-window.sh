#!/usr/bin/env bash
#
# Phase 213 alert-window extractor.
#
# Evidence-only D-07/D-09/D-10 helper: reads SQLite alert rows from live
# cake-shaper metrics databases using read-only URI mode, or from a local
# fixture database in offline pytest coverage. The local mode is for fixture
# exercise only; use SSH mode for live writer databases.

set -euo pipefail

START=""
END=""
OUTPUT_DIR=""
SSH_HOST="cake-shaper"
LOCAL_DB=""

usage() {
    cat <<'EOF'
Usage:
  scripts/phase213-alert-window.sh --start <unix> --end <unix> --output-dir <dir> [--ssh-host cake-shaper]
  scripts/phase213-alert-window.sh [local fixture mode] --start <unix> --end <unix> --output-dir <dir>

Options:
  --start <unix>        Inclusive alert-window start timestamp.
  --end <unix>          Inclusive alert-window end timestamp.
  --output-dir <dir>    Directory for JSON artifacts.
  --ssh-host <name>     Host used for live DB reads (default: cake-shaper).
  local fixture mode    Offline fixture DB mode; skips remote access entirely.
  --help, -h            Show this help.

Output:
  SSH mode emits alerts-spectrum.json, alerts-att.json, alerts-steering.json,
  and alerts-summary.json. Local mode emits alerts-spectrum.json only with
  wan="local".
EOF
}

require_command() {
    local cmd="$1"
    if ! command -v "$cmd" >/dev/null 2>&1; then
        echo "ERROR: required command not found: $cmd" >&2
        exit 1
    fi
}

json_empty_artifact() {
    local wan="$1"
    local db="$2"
    local present="$3"

    jq -n \
        --arg wan "$wan" \
        --arg db "$db" \
        --argjson present "$present" \
        '{wan:$wan, db:$db, present:$present, rows:[], summary:[]}'
}

merge_rows_and_summary() {
    local wan="$1"
    local db="$2"
    local rows_file="$3"
    local summary_file="$4"
    local output_file="$5"

    jq -n \
        --arg wan "$wan" \
        --arg db "$db" \
        --slurpfile rows "$rows_file" \
        --slurpfile summary "$summary_file" \
        '{wan:$wan, db:$db, present:true, rows:($rows[0] // []), summary:($summary[0] // [])}' \
        >"$output_file"
}

run_local_mode() {
    local rows_tmp summary_tmp
    rows_tmp="$(mktemp -t phase213-alert-rows.XXXXXX)"
    summary_tmp="$(mktemp -t phase213-alert-summary.XXXXXX)"
    trap "rm -f '$rows_tmp' '$summary_tmp'" EXIT INT TERM

    if command -v sqlite3 >/dev/null 2>&1; then
        sqlite3 -readonly -json "file:${LOCAL_DB}?mode=ro" \
            "SELECT timestamp, alert_type, severity, wan_name, details FROM alerts WHERE timestamp BETWEEN ${START} AND ${END} ORDER BY timestamp;" \
            >"$rows_tmp"

        sqlite3 -readonly -json "file:${LOCAL_DB}?mode=ro" \
            "SELECT alert_type, severity, COUNT(*) AS count FROM alerts WHERE timestamp BETWEEN ${START} AND ${END} GROUP BY alert_type, severity ORDER BY count DESC;" \
            >"$summary_tmp"
    else
        python3 - "$LOCAL_DB" "$START" "$END" "$rows_tmp" "$summary_tmp" <<'PY'
import json
import sqlite3
import sys

db, start, end, rows_out, summary_out = sys.argv[1:]
conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
conn.row_factory = sqlite3.Row
try:
    rows = conn.execute(
        "SELECT timestamp, alert_type, severity, wan_name, details FROM alerts WHERE timestamp BETWEEN ? AND ? ORDER BY timestamp;",
        (int(start), int(end)),
    ).fetchall()
    summary = conn.execute(
        "SELECT alert_type, severity, COUNT(*) AS count FROM alerts WHERE timestamp BETWEEN ? AND ? GROUP BY alert_type, severity ORDER BY count DESC;",
        (int(start), int(end)),
    ).fetchall()
finally:
    conn.close()

with open(rows_out, "w") as f:
    json.dump([dict(row) for row in rows], f)
with open(summary_out, "w") as f:
    json.dump([dict(row) for row in summary], f)
PY
    fi

    merge_rows_and_summary "local" "$LOCAL_DB" "$rows_tmp" "$summary_tmp" "${OUTPUT_DIR}/alerts-spectrum.json"
    rm -f "$rows_tmp" "$summary_tmp"
    trap - EXIT INT TERM
}

ssh_opts() {
    printf '%s\n' \
        -o BatchMode=yes \
        -o ControlMaster=auto \
        -o 'ControlPath=~/.ssh/control-%h:%p:%r' \
        -o ControlPersist=5m
}

remote_sqlite_json() {
    local db="$1"
    local sql="$2"
    local output_file="$3"

    ssh $(ssh_opts) "$SSH_HOST" \
        "sudo -n sqlite3 -readonly -json \"file:${db}?mode=ro\" \"${sql}\"" \
        >"$output_file"
}

run_ssh_mode() {
    local entry wan db out rows_tmp summary_tmp
    local artifacts=(
        "spectrum:/var/lib/wanctl/metrics-spectrum.db:alerts-spectrum"
        "att:/var/lib/wanctl/metrics-att.db:alerts-att"
        "steering:/var/lib/wanctl/metrics.db:alerts-steering"
    )

    require_command ssh

    for entry in "${artifacts[@]}"; do
        IFS=":" read -r wan db out <<<"$entry"

        if ! ssh $(ssh_opts) "$SSH_HOST" "sudo -n test -f ${db}"; then
            json_empty_artifact "$wan" "$db" false >"${OUTPUT_DIR}/${out}.json"
            continue
        fi

        rows_tmp="$(mktemp -t phase213-alert-rows.XXXXXX)"
        summary_tmp="$(mktemp -t phase213-alert-summary.XXXXXX)"
        trap "rm -f '$rows_tmp' '$summary_tmp'" EXIT INT TERM

        remote_sqlite_json \
            "$db" \
            "SELECT timestamp, alert_type, severity, wan_name, details FROM alerts WHERE timestamp BETWEEN ${START} AND ${END} ORDER BY timestamp;" \
            "$rows_tmp"
        remote_sqlite_json \
            "$db" \
            "SELECT alert_type, severity, COUNT(*) AS count FROM alerts WHERE timestamp BETWEEN ${START} AND ${END} GROUP BY alert_type, severity ORDER BY count DESC;" \
            "$summary_tmp"

        merge_rows_and_summary "$wan" "$db" "$rows_tmp" "$summary_tmp" "${OUTPUT_DIR}/${out}.json"
        rm -f "$rows_tmp" "$summary_tmp"
        trap - EXIT INT TERM
    done

    jq -s \
        '{spectrum:.[0], att:.[1], steering:.[2]}' \
        "${OUTPUT_DIR}/alerts-spectrum.json" \
        "${OUTPUT_DIR}/alerts-att.json" \
        "${OUTPUT_DIR}/alerts-steering.json" \
        >"${OUTPUT_DIR}/alerts-summary.json"
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --start)
            START="${2:-}"
            shift 2
            ;;
        --end)
            END="${2:-}"
            shift 2
            ;;
        --output-dir)
            OUTPUT_DIR="${2:-}"
            shift 2
            ;;
        --ssh-host)
            SSH_HOST="${2:-}"
            shift 2
            ;;
        --local-db)
            LOCAL_DB="${2:-}"
            shift 2
            ;;
        --help|-h)
            usage
            exit 0
            ;;
        *)
            echo "ERROR: unknown argument: $1" >&2
            usage >&2
            exit 2
            ;;
    esac
done

if [[ -z "$START" || -z "$END" || -z "$OUTPUT_DIR" ]]; then
    usage >&2
    exit 2
fi

if ! [[ "$START" =~ ^[0-9]+$ && "$END" =~ ^[0-9]+$ ]]; then
    echo "ERROR: --start and --end must be Unix integer timestamps" >&2
    exit 2
fi

if (( START > END )); then
    echo "ERROR: --start must be <= --end" >&2
    exit 2
fi

require_command jq
mkdir -p "$OUTPUT_DIR"

if [[ -n "$LOCAL_DB" ]]; then
    require_command python3
    if [[ ! -f "$LOCAL_DB" ]]; then
        echo "ERROR: local DB not found: $LOCAL_DB" >&2
        exit 2
    fi
    run_local_mode
else
    require_command sqlite3
    run_ssh_mode
fi
