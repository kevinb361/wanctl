#!/usr/bin/env bash
#
# Phase 196 soak evidence capture helper.
#
# Operator-run only. This helper captures health, journal, and metrics evidence
# for Phase 196 preflight, Spectrum A/B legs, and the ATT canary gate. It does
# not deploy code, edit config, restart services, or change router/controller
# state.

set -euo pipefail

USAGE="scripts/phase196-soak-capture.sh {preflight|rtt-blend-start|rtt-blend-finish|cake-primary-start|cake-primary-finish|att-canary}"

usage() {
    cat <<EOF
Usage:
  ${USAGE}

Environment:
  PHASE196_OUT_DIR                  Root output directory for captured evidence

Spectrum modes require:
  PHASE196_SPECTRUM_HEALTH_URL      Spectrum /health URL
  PHASE196_SPECTRUM_SSH_HOST        SSH host for Spectrum journal and metrics reads
  PHASE196_SPECTRUM_METRICS_DB      Spectrum metrics SQLite DB path on SSH host

ATT mode requires:
  PHASE196_ATT_HEALTH_URL           ATT /health URL
  PHASE196_ATT_SSH_HOST             SSH host for ATT journal and metrics reads
  PHASE196_ATT_METRICS_DB           ATT metrics SQLite DB path on SSH host
EOF
}

require_command() {
    local cmd="$1"
    if ! command -v "$cmd" >/dev/null 2>&1; then
        echo "ERROR: required command not found: $cmd" >&2
        exit 1
    fi
}

require_var() {
    local var_name="$1"
    local description="$2"
    if [[ -z "${!var_name:-}" ]]; then
        echo "ERROR: $var_name is required ($description)" >&2
        exit 2
    fi
}

resolve_mode() {
    local mode="$1"

    case "$mode" in
        preflight)
            CAPTURE_GROUP="preflight"
            WAN_NAME="spectrum"
            HEALTH_VAR="PHASE196_SPECTRUM_HEALTH_URL"
            SSH_VAR="PHASE196_SPECTRUM_SSH_HOST"
            DB_VAR="PHASE196_SPECTRUM_METRICS_DB"
            ;;
        rtt-blend-start|rtt-blend-finish)
            CAPTURE_GROUP="rtt-blend"
            WAN_NAME="spectrum"
            HEALTH_VAR="PHASE196_SPECTRUM_HEALTH_URL"
            SSH_VAR="PHASE196_SPECTRUM_SSH_HOST"
            DB_VAR="PHASE196_SPECTRUM_METRICS_DB"
            ;;
        cake-primary-start|cake-primary-finish)
            CAPTURE_GROUP="cake-primary"
            WAN_NAME="spectrum"
            HEALTH_VAR="PHASE196_SPECTRUM_HEALTH_URL"
            SSH_VAR="PHASE196_SPECTRUM_SSH_HOST"
            DB_VAR="PHASE196_SPECTRUM_METRICS_DB"
            ;;
        att-canary)
            CAPTURE_GROUP="att-canary"
            WAN_NAME="att"
            HEALTH_VAR="PHASE196_ATT_HEALTH_URL"
            SSH_VAR="PHASE196_ATT_SSH_HOST"
            DB_VAR="PHASE196_ATT_METRICS_DB"
            ;;
        "")
            usage >&2
            exit 2
            ;;
        *)
            echo "ERROR: unknown capture mode: $mode" >&2
            usage >&2
            exit 2
            ;;
    esac
}

remote_sqlite_query() {
    local ssh_host="$1"
    local metrics_db="$2"
    local wan_name="$3"
    local output_file="$4"
    local remote_db

    printf -v remote_db "%q" "$metrics_db"
    ssh -o BatchMode=yes "$ssh_host" \
        "command -v sqlite3 >/dev/null || { echo 'ERROR: sqlite3 missing on remote host' >&2; exit 1; }; sudo -n sqlite3 -readonly -header -separator '|' $remote_db" \
        >"$output_file" <<SQL
SELECT
  datetime(timestamp, 'unixepoch') AS sampled_utc,
  timestamp,
  wan_name,
  metric_name,
  value
FROM metrics
WHERE wan_name = '${wan_name}'
  AND metric_name IN (
    'wanctl_arbitration_active_primary',
    'wanctl_arbitration_refractory_active',
    'wanctl_rtt_confidence',
    'wanctl_cake_avg_delay_delta_us',
    'wanctl_fusion_bypass_active'
  )
  AND timestamp >= strftime('%s', 'now', '-24 hours')
ORDER BY timestamp, metric_name;
SQL
}

remote_sqlite_aggregate_query() {
    local ssh_host="$1"
    local metrics_db="$2"
    local wan_name="$3"
    local output_file="$4"
    local remote_db

    printf -v remote_db "%q" "$metrics_db"
    ssh -o BatchMode=yes "$ssh_host" \
        "command -v sqlite3 >/dev/null || { echo 'ERROR: sqlite3 missing on remote host' >&2; exit 1; }; sudo -n sqlite3 -readonly -header -separator '|' $remote_db" \
        >"$output_file" <<SQL
SELECT
  metric_name,
  COUNT(*) AS samples,
  MIN(value) AS min_value,
  MAX(value) AS max_value,
  AVG(value) AS avg_value,
  MAX(datetime(timestamp, 'unixepoch')) AS latest_utc
FROM metrics
WHERE wan_name = '${wan_name}'
  AND metric_name IN (
    'wanctl_arbitration_active_primary',
    'wanctl_arbitration_refractory_active',
    'wanctl_rtt_confidence',
    'wanctl_cake_avg_delay_delta_us',
    'wanctl_fusion_bypass_active'
  )
  AND timestamp >= strftime('%s', 'now', '-24 hours')
GROUP BY metric_name
ORDER BY metric_name;
SQL
}

capture_journal_excerpt() {
    local ssh_host="$1"
    local wan_name="$2"
    local output_file="$3"

    ssh -o BatchMode=yes "$ssh_host" \
        "sudo -n journalctl -u 'wanctl@${wan_name}' --since '-24h' --no-pager | grep -E 'Fusion healer|Protocol deprioritization|rtt_veto|queue_distress|healer_bypass|dwell|burst|ERROR|WARNING' || true" \
        >"$output_file"
}

json_number_or_null() {
    local value="$1"
    if [[ -z "$value" || "$value" == "null" ]]; then
        printf 'null'
    else
        printf '%s' "$value"
    fi
}

MODE="${1:-}"
resolve_mode "$MODE"

require_command curl
require_command jq
require_command ssh

require_var PHASE196_OUT_DIR "root output directory for Phase 196 evidence"
require_var "$HEALTH_VAR" "health endpoint URL for $WAN_NAME"
require_var "$SSH_VAR" "SSH host for $WAN_NAME journal and metrics reads"
require_var "$DB_VAR" "metrics SQLite DB path for $WAN_NAME on SSH host"

HEALTH_URL="${!HEALTH_VAR}"
SSH_HOST="${!SSH_VAR}"
METRICS_DB="${!DB_VAR}"

CAPTURED_AT_ISO="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
FILE_TS="$(date -u +%Y%m%dT%H%M%SZ)"
OUT_DIR="${PHASE196_OUT_DIR%/}/${CAPTURE_GROUP}"
RAW_DIR="${OUT_DIR}/raw"
PREFIX="${MODE}-${FILE_TS}"

mkdir -p "$RAW_DIR"

RAW_HEALTH="${RAW_DIR}/${PREFIX}-health.json"
RAW_JOURNAL="${RAW_DIR}/${PREFIX}-journal.log"
RAW_FUSION="${RAW_DIR}/${PREFIX}-fusion-transitions.log"
SQLITE_OUT="${RAW_DIR}/${PREFIX}-sqlite-metrics.psv"
SQLITE_AGGREGATE_OUT="${RAW_DIR}/${PREFIX}-sqlite-metrics-aggregate.psv"
SUMMARY_JSON="${OUT_DIR}/${PREFIX}-summary.json"

curl --fail --silent --show-error --max-time 10 "$HEALTH_URL" >"$RAW_HEALTH"
capture_journal_excerpt "$SSH_HOST" "$WAN_NAME" "$RAW_JOURNAL"
grep -E 'Fusion healer.*->' "$RAW_JOURNAL" >"$RAW_FUSION" || true
remote_sqlite_query "$SSH_HOST" "$METRICS_DB" "$WAN_NAME" "$SQLITE_OUT"
remote_sqlite_aggregate_query "$SSH_HOST" "$METRICS_DB" "$WAN_NAME" "$SQLITE_AGGREGATE_OUT"

active_primary_signal="$(jq -r '(.wans[0] // .).signal_arbitration.active_primary_signal // null' "$RAW_HEALTH")"
rtt_confidence="$(jq -r '(.wans[0] // .).signal_arbitration.rtt_confidence // null' "$RAW_HEALTH")"
cake_av_delay_delta_us="$(jq -r '(.wans[0] // .).signal_arbitration.cake_av_delay_delta_us // null' "$RAW_HEALTH")"
control_decision_reason="$(jq -r '(.wans[0] // .).signal_arbitration.control_decision_reason // null' "$RAW_HEALTH")"
refractory_active="$(jq -r '(.wans[0] // .).signal_arbitration.refractory_active // false' "$RAW_HEALTH")"
dwell_bypassed_count="$(jq -r '(.wans[0] // .).download.hysteresis.dwell_bypassed_count // 0 | floor' "$RAW_HEALTH")"
download_burst_trigger_count="$(jq -r '(.wans[0] // .).download.burst.trigger_count // 0 | floor' "$RAW_HEALTH")"
upload_burst_trigger_count="$(jq -r '(.wans[0] // .).upload.burst.trigger_count // 0 | floor' "$RAW_HEALTH")"
fusion_transition_count_24h="$(wc -l <"$RAW_FUSION" | tr -d ' ')"
sqlite_metric_rows="$(tail -n +2 "$SQLITE_OUT" | wc -l | tr -d ' ')"
sqlite_metric_aggregate_rows="$(tail -n +2 "$SQLITE_AGGREGATE_OUT" | wc -l | tr -d ' ')"
journal_excerpt_lines="$(wc -l <"$RAW_JOURNAL" | tr -d ' ')"

jq -n \
    --arg mode "$MODE" \
    --arg capture_group "$CAPTURE_GROUP" \
    --arg wan_name "$WAN_NAME" \
    --arg captured_at_iso "$CAPTURED_AT_ISO" \
    --arg health_json "$RAW_HEALTH" \
    --arg journal_excerpt "$RAW_JOURNAL" \
    --arg fusion_transitions "$RAW_FUSION" \
    --arg sqlite_metrics "$SQLITE_OUT" \
    --arg sqlite_metrics_aggregate "$SQLITE_AGGREGATE_OUT" \
    --arg active_primary_signal "$active_primary_signal" \
    --arg control_decision_reason "$control_decision_reason" \
    --argjson refractory_active "$refractory_active" \
    --argjson rtt_confidence "$(json_number_or_null "$rtt_confidence")" \
    --argjson cake_av_delay_delta_us "$(json_number_or_null "$cake_av_delay_delta_us")" \
    --argjson dwell_bypassed_count "$dwell_bypassed_count" \
    --argjson download_burst_trigger_count "$download_burst_trigger_count" \
    --argjson upload_burst_trigger_count "$upload_burst_trigger_count" \
    --argjson fusion_transition_count_24h "$fusion_transition_count_24h" \
    --argjson sqlite_metric_rows "$sqlite_metric_rows" \
    --argjson sqlite_metric_aggregate_rows "$sqlite_metric_aggregate_rows" \
    --argjson journal_excerpt_lines "$journal_excerpt_lines" \
    '{
      mode: $mode,
      capture_group: $capture_group,
      wan_name: $wan_name,
      captured_at_iso: $captured_at_iso,
      artifacts: {
        health_json: $health_json,
        journal_excerpt: $journal_excerpt,
        fusion_transitions: $fusion_transitions,
        sqlite_metrics: $sqlite_metrics,
        sqlite_metrics_aggregate: $sqlite_metrics_aggregate
      },
      signal_arbitration: {
        active_primary_signal: $active_primary_signal,
        rtt_confidence: $rtt_confidence,
        cake_av_delay_delta_us: $cake_av_delay_delta_us,
        control_decision_reason: $control_decision_reason,
        refractory_active: $refractory_active
      },
      counters: {
        dwell_bypassed_count: $dwell_bypassed_count,
        download_burst_trigger_count: $download_burst_trigger_count,
        upload_burst_trigger_count: $upload_burst_trigger_count,
        fusion_transition_count_24h: $fusion_transition_count_24h,
        sqlite_metric_rows: $sqlite_metric_rows,
        sqlite_metric_aggregate_rows: $sqlite_metric_aggregate_rows,
        journal_excerpt_lines: $journal_excerpt_lines
      }
    }' >"$SUMMARY_JSON"

echo "Phase 196 capture complete: $SUMMARY_JSON"
