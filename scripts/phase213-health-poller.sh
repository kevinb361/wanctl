#!/usr/bin/env bash
# Phase 213 sibling poller of soak-capture.sh; D-09/D-10 evidence-only;
# emits extended /health projection per RESEARCH §Pattern 2.
#
# Usage:
#   scripts/phase213-health-poller.sh --endpoint <url> --wan <name> --output <ndjson-path> [--duration <sec-or-0>]
#
# The script polls one autorate /health endpoint at 1Hz and appends projected
# NDJSON rows to --output. A duration of 0 means run until SIGTERM/SIGINT,
# which exits cleanly for orchestrator-managed lifecycles.
#
# HRDN-02 bounded-failure behavior is inherited from scripts/soak-capture.sh:
# transient curl, HTTP, empty-body, and jq failures are recorded in a TSV
# sidecar while good rows continue to append to the NDJSON stream.

set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  scripts/phase213-health-poller.sh --endpoint <url> --wan <name> --output <ndjson-path> [--duration <sec-or-0>]

Options:
  --endpoint <url>       Autorate /health endpoint to poll (required)
  --wan <name>           WAN label to include in each row (required)
  --output <path>        NDJSON output path (required)
  --duration <seconds>   Poll duration; 0 means until signal (default: 0)
  --help, -h             Show this help
EOF
}

ENDPOINT=""
WAN=""
OUTPUT=""
DURATION="0"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --endpoint)
      ENDPOINT="${2:-}"
      shift 2
      ;;
    --wan)
      WAN="${2:-}"
      shift 2
      ;;
    --output)
      OUTPUT="${2:-}"
      shift 2
      ;;
    --duration)
      DURATION="${2:-}"
      shift 2
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

if [[ -z "$ENDPOINT" || -z "$WAN" || -z "$OUTPUT" ]]; then
  echo "phase213-health-poller: --endpoint, --wan, and --output are required" >&2
  usage >&2
  exit 2
fi

if ! [[ "$DURATION" =~ ^[0-9]+$ ]]; then
  echo "phase213-health-poller: --duration must be a non-negative integer; got '${DURATION}'" >&2
  exit 2
fi

if ! command -v curl >/dev/null 2>&1; then
  echo "phase213-health-poller: curl is required" >&2
  exit 2
fi

if ! command -v jq >/dev/null 2>&1; then
  echo "phase213-health-poller: jq is required" >&2
  exit 2
fi

SOAK_FAIL_RATE_THRESHOLD="${SOAK_FAIL_RATE_THRESHOLD:-0.30}"
MIN_SAMPLES_BEFORE_EVAL="${MIN_SAMPLES_BEFORE_EVAL:-30}"

if ! awk -v v="$SOAK_FAIL_RATE_THRESHOLD" 'BEGIN { if (v ~ /^[0-9]+(\.[0-9]+)?$/ && v+0 >= 0 && v+0 <= 1) exit 0; else exit 1 }'; then
  echo "phase213-health-poller: ABORT — SOAK_FAIL_RATE_THRESHOLD must be numeric in [0.0, 1.0]; got '${SOAK_FAIL_RATE_THRESHOLD}'" >&2
  exit 2
fi

if ! [[ "$MIN_SAMPLES_BEFORE_EVAL" =~ ^[1-9][0-9]*$ ]]; then
  echo "phase213-health-poller: ABORT — MIN_SAMPLES_BEFORE_EVAL must be a positive integer; got '${MIN_SAMPLES_BEFORE_EVAL}'" >&2
  exit 2
fi

CAPTURE_DIR="$(dirname "$OUTPUT")"
mkdir -p "$CAPTURE_DIR"

SIDECAR_TSV="${CAPTURE_DIR}/poll-failures.tsv"
printf 't_wall\tfailure_mode\tlast_curl_exit\tlast_message\n' > "$SIDECAR_TSV"

body_tmp="${CAPTURE_DIR}/.phase213-curl-body.$$"
out_tmp="${CAPTURE_DIR}/.phase213-jq-out.$$"
err_tmp="${CAPTURE_DIR}/.phase213-curl-err.$$"

cleanup() {
  rm -f "$body_tmp" "$out_tmp" "$err_tmp"
}

finish_signal() {
  cleanup
  exit 0
}

trap finish_signal TERM INT
trap cleanup EXIT

row_total=0
row_failed=0
curl_exit_nonzero=0
curl_http_nonzero=0
jq_parse_error=0
empty_body=0

T0_MONO=$(awk '{print $1; exit}' /proc/uptime)
START_EPOCH=$(date +%s)
END_EPOCH=0
if [[ "$DURATION" -gt 0 ]]; then
  END_EPOCH=$((START_EPOCH + DURATION))
fi

while [[ "$DURATION" -eq 0 || "$(date +%s)" -lt "$END_EPOCH" ]]; do
  : > "$body_tmp"
  : > "$out_tmp"
  : > "$err_tmp"

  T_MONO=$(awk '{print $1; exit}' /proc/uptime)
  T_MONO_DELTA=$(awk -v a="$T_MONO" -v b="$T0_MONO" 'BEGIN{print a-b}')

  failure_mode=""
  last_message=""
  curl_exit=0
  http_code=""

  http_code=$(curl --silent --max-time 10 --write-out '%{http_code}' \
                   --output "$body_tmp" "$ENDPOINT" 2>"$err_tmp") || curl_exit=$?

  if [[ "$curl_exit" -ne 0 ]]; then
    failure_mode="curl_exit_nonzero"
    last_message="curl exit ${curl_exit}; http_code=${http_code}; $(head -c 200 "$err_tmp" 2>/dev/null || true)"
    curl_exit_nonzero=$((curl_exit_nonzero + 1))
  elif [[ -z "$http_code" || "$http_code" != "200" ]]; then
    failure_mode="curl_http_nonzero"
    last_message="http_code=${http_code}"
    curl_http_nonzero=$((curl_http_nonzero + 1))
  elif [[ "$(wc -c < "$body_tmp")" -eq 0 ]]; then
    failure_mode="empty_body"
    last_message="empty body, http_code=${http_code}"
    empty_body=$((empty_body + 1))
  else
    if ! jq -c --arg twall "$(date -u -Iseconds)" --argjson tmono "$T_MONO_DELTA" --arg wan "$WAN" '{
      t_wall: $twall, t_monotonic_sec: $tmono, wan: $wan,
      version: .version, status: .status,
      download_state: .wans[0].download.state,
      download_state_reason: .wans[0].download.state_reason,
      download_rate_mbps: .wans[0].download.current_rate_mbps,
      download_green_streak: .wans[0].download.hysteresis.green_streak,
      download_green_required: .wans[0].download.hysteresis.green_required,
      upload_state: .wans[0].upload.state,
      upload_state_reason: .wans[0].upload.state_reason,
      upload_rate_mbps: .wans[0].upload.current_rate_mbps,
      upload_setpoint_mbps: .wans[0].upload.setpoint_mbps,
      upload_docsis_mode_active: .wans[0].upload.docsis_mode_active,
      upload_floor_hit_cycles_total: .wans[0].upload.floor_hit_cycles_total,
      upload_headroom_state: .wans[0].upload.headroom_state,
      upload_headroom_exhausted_streak: .wans[0].upload.headroom_exhausted_streak,
      upload_red_streak: .wans[0].upload.red_streak,
      upload_anti_windup_triggers: .wans[0].upload.anti_windup_triggers,
      cake_dl_peak_delay_us: .wans[0].cake_signal.download.peak_delay_us,
      cake_dl_drop_rate: .wans[0].cake_signal.download.drop_rate,
      cake_ul_peak_delay_us: .wans[0].cake_signal.upload.peak_delay_us,
      cake_ul_drop_rate: .wans[0].cake_signal.upload.drop_rate,
      cake_dl_backlog_suppressed_count: .wans[0].cake_signal.detection.dl_backlog_suppressed_count,
      cake_ul_backlog_suppressed_count: .wans[0].cake_signal.detection.ul_backlog_suppressed_count,
      cake_dl_refractory_remaining: .wans[0].cake_signal.detection.dl_refractory_remaining,
      cake_ul_refractory_remaining: .wans[0].cake_signal.detection.ul_refractory_remaining,
      cake_refractory_cycles: .wans[0].cake_signal.detection.refractory_cycles,
      cake_burst_active: .wans[0].cake_signal.burst.active,
      cake_burst_trigger_count: .wans[0].cake_signal.burst.trigger_count,
      arb_active_primary_signal: .wans[0].signal_arbitration.active_primary_signal,
      arb_control_decision_reason: .wans[0].signal_arbitration.control_decision_reason,
      arb_refractory_active: .wans[0].signal_arbitration.refractory_active,
      arb_rtt_confidence: .wans[0].signal_arbitration.rtt_confidence,
      signal_confidence: .wans[0].signal_quality.confidence,
      signal_outlier_rate: .wans[0].signal_quality.outlier_rate,
      signal_warming_up: .wans[0].signal_quality.warming_up,
      measurement_state: .wans[0].measurement.state,
      measurement_stale: .wans[0].measurement.stale,
      measurement_staleness_sec: .wans[0].measurement.staleness_sec,
      measurement_successful_count: .wans[0].measurement.successful_count,
      baseline_rtt_ms: .wans[0].baseline_rtt_ms,
      load_rtt_ms: .wans[0].load_rtt_ms,
      load_rtt_delta_us: (
        if (.wans[0].load_rtt_ms == null) or (.wans[0].baseline_rtt_ms == null)
        then null
        else ((.wans[0].load_rtt_ms - .wans[0].baseline_rtt_ms) * 1000 | floor)
        end
      ),
      irtt_rtt_mean_ms: (.wans[0].irtt.rtt_mean_ms // null),
      irtt_loss_up_pct: (.wans[0].irtt.loss_up_pct // null),
      irtt_loss_down_pct: (.wans[0].irtt.loss_down_pct // null),
      irtt_asymmetry_ratio: (.wans[0].irtt.asymmetry_ratio // null),
      router_reachable: .wans[0].router_connectivity.is_reachable,
      alerting_fire_count: .alerting.fire_count,
      alerting_active_cooldowns_count: (.alerting.active_cooldowns | length)
    }' < "$body_tmp" > "$out_tmp" 2>/dev/null; then
      failure_mode="jq_parse_error"
      last_message="jq parse failed; body first 200 chars: $(head -c 200 "$body_tmp" 2>/dev/null || true)"
      jq_parse_error=$((jq_parse_error + 1))
    elif [[ "$(wc -c < "$out_tmp")" -eq 0 ]]; then
      failure_mode="jq_parse_error"
      last_message="jq produced empty output; body first 200 chars: $(head -c 200 "$body_tmp" 2>/dev/null || true)"
      jq_parse_error=$((jq_parse_error + 1))
    fi
  fi

  row_total=$((row_total + 1))

  if [[ -z "$failure_mode" ]]; then
    cat "$out_tmp" >> "$OUTPUT"
  else
    row_failed=$((row_failed + 1))
    last_message_clean=$(printf '%s' "$last_message" | tr -d '\t\n\r')
    printf '%s\t%s\t%s\t%s\n' "$(date -u -Iseconds)" "$failure_mode" "$curl_exit" "$last_message_clean" >> "$SIDECAR_TSV"
  fi

  sleep 1

  if [[ "$row_total" -ge "$MIN_SAMPLES_BEFORE_EVAL" && "$row_failed" -gt 0 ]]; then
    exceeded=$(awk -v f="$row_failed" -v t="$row_total" -v thr="$SOAK_FAIL_RATE_THRESHOLD" \
      'BEGIN { print ((f/t) > thr) ? 1 : 0 }')
    if [[ "$exceeded" = "1" ]]; then
      rate=$(awk -v f="$row_failed" -v t="$row_total" 'BEGIN { printf "%.4f", f/t }')
      echo "phase213-health-poller: ABORT — lifetime failure rate ${rate} exceeded threshold ${SOAK_FAIL_RATE_THRESHOLD} after ${row_total} attempted rows" >&2
      echo "  row_failed=${row_failed} row_total=${row_total}" >&2
      echo "  curl_exit_nonzero=${curl_exit_nonzero} curl_http_nonzero=${curl_http_nonzero} jq_parse_error=${jq_parse_error} empty_body=${empty_body}" >&2
      echo "  sidecar: ${SIDECAR_TSV}" >&2
      exit 1
    fi
  fi
done

echo "phase213-health-poller: complete — row_total=${row_total} row_failed=${row_failed} (threshold=${SOAK_FAIL_RATE_THRESHOLD})" >&2
echo "  curl_exit_nonzero=${curl_exit_nonzero} curl_http_nonzero=${curl_http_nonzero} jq_parse_error=${jq_parse_error} empty_body=${empty_body}" >&2
