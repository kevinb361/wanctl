#!/usr/bin/env bash
# wanctl soak-capture harness (v1.43 Phase 203)
#
# Usage: HEALTH_URL=http://<host>:9101/health bash scripts/soak-capture.sh <SOAK_TS>
#
# Required env: HEALTH_URL  — full /health endpoint URL (no default; public-safe).
# Optional env: SOAK_DURATION_SEC (default 86400 = 24h)
#               CAPTURE_DIR        (default /var/tmp/wanctl-soak-${SOAK_TS})
#
# Writes one NDJSON row per second to ${CAPTURE_DIR}/soak-capture.ndjson.
# See docs/SOAK_HARNESS.md for the full per-row schema (created in plan 203-03).
#
# HRDN-02 (Phase 207): bounded per-row failure tolerance.
# - SOAK_FAIL_RATE_THRESHOLD (default 0.01) is row_failed/row_total where
#   row_total counts ATTEMPTED iterations, not expected wall-clock slots.
#   A slow curl that holds an iteration for >1s still increments row_total
#   by exactly 1. Wall-clock missed-slot accounting is out of scope for
#   HRDN-02 (deferred to a future requirement).
# - MIN_SAMPLES_BEFORE_EVAL (default 60) is the warmup before the rate gate.
# - Failures append to ${CAPTURE_DIR}/soak-capture-errors.tsv (sidecar).
#   NDJSON schema is unchanged — no sentinel rows.

set -euo pipefail

SOAK_TS="${1:?SOAK_TS:? positional arg required}"
: "${HEALTH_URL:?HEALTH_URL env var required (e.g. HEALTH_URL=http://<host>:9101/health)}"
SOAK_DURATION_SEC="${SOAK_DURATION_SEC:-86400}"
SOAK_FAIL_RATE_THRESHOLD="${SOAK_FAIL_RATE_THRESHOLD:-0.01}"
MIN_SAMPLES_BEFORE_EVAL="${MIN_SAMPLES_BEFORE_EVAL:-60}"
CAPTURE_DIR="${CAPTURE_DIR:-/var/tmp/wanctl-soak-${SOAK_TS}}"

mkdir -p "$CAPTURE_DIR"
SIDECAR_TSV="${CAPTURE_DIR}/soak-capture-errors.tsv"

# HRDN-02: validate threshold is a numeric in [0.0, 1.0]. Fail-closed exit if not.
if ! awk -v v="$SOAK_FAIL_RATE_THRESHOLD" 'BEGIN { if (v ~ /^[0-9]+(\.[0-9]+)?$/ && v+0 >= 0 && v+0 <= 1) exit 0; else exit 1 }'; then
  echo "soak-capture: ABORT — SOAK_FAIL_RATE_THRESHOLD must be numeric in [0.0, 1.0]; got '${SOAK_FAIL_RATE_THRESHOLD}'" >&2
  exit 2
fi
# HRDN-02: validate MIN_SAMPLES_BEFORE_EVAL is a positive integer.
if ! [[ "$MIN_SAMPLES_BEFORE_EVAL" =~ ^[1-9][0-9]*$ ]]; then
  echo "soak-capture: ABORT — MIN_SAMPLES_BEFORE_EVAL must be a positive integer; got '${MIN_SAMPLES_BEFORE_EVAL}'" >&2
  exit 2
fi

row_total=0
row_failed=0
curl_exit_nonzero=0
curl_http_nonzero=0
jq_parse_error=0
empty_body=0
printf 't_wall\tfailure_mode\tlast_curl_exit\tlast_message\n' > "$SIDECAR_TSV"

body_tmp="${CAPTURE_DIR}/.curl_body"
out_tmp="${CAPTURE_DIR}/.jq_out"
err_tmp="${CAPTURE_DIR}/.curl_err"

T0_MONO=$(awk '{print $1; exit}' /proc/uptime)
SOAK_END=$(($(date +%s) + SOAK_DURATION_SEC))

while [ "$(date +%s)" -lt "$SOAK_END" ]; do
  # HRDN-02: truncate per-iteration temp files to prevent stale-success bugs.
  : > "$body_tmp"
  : > "$out_tmp"
  : > "$err_tmp"

  T_MONO=$(awk '{print $1; exit}' /proc/uptime)
  T_MONO_DELTA=$(awk -v a="$T_MONO" -v b="$T0_MONO" 'BEGIN{print a-b}')

  failure_mode=""
  last_message=""
  curl_exit=0
  http_code=""

  # Capture HTTP code via --write-out, body via --output, and exit status via || capture.
  http_code=$(curl --silent --max-time 10 --write-out '%{http_code}' \
                   --output "$body_tmp" "$HEALTH_URL" 2>"$err_tmp") || curl_exit=$?

  if [ "$curl_exit" -ne 0 ]; then
    failure_mode="curl_exit_nonzero"
    last_message="curl exit ${curl_exit}; http_code=${http_code}; $(head -c 200 "$err_tmp" 2>/dev/null || true)"
    curl_exit_nonzero=$((curl_exit_nonzero + 1))
  elif [ -z "$http_code" ] || [ "$http_code" != "200" ]; then
    failure_mode="curl_http_nonzero"
    last_message="http_code=${http_code}"
    curl_http_nonzero=$((curl_http_nonzero + 1))
  elif [ "$(wc -c < "$body_tmp")" -eq 0 ]; then
    failure_mode="empty_body"
    last_message="empty body, http_code=${http_code}"
    empty_body=$((empty_body + 1))
  else
    # Run the jq projection. The full projection from the original script is
    # preserved verbatim — every existing NDJSON field name/expression stays.
    if ! jq -c --arg twall "$(date -u -Iseconds)" --argjson tmono "$T_MONO_DELTA" '{
          t_wall: $twall,
          t_monotonic: $tmono,
          version: .version,
          status: .status,
          floor_hit_cycles_total: .wans[0].upload.floor_hit_cycles_total,
          suppressions_per_min: .wans[0].upload.hysteresis.suppressions_per_min,
          max_delay_delta_us: .wans[0].upload.max_delay_delta_us,
          red_streak: .wans[0].upload.red_streak,
          zone_trace_tail: (.wans[0].upload.zone_trace | .[-5:]),
          headroom_state: .wans[0].upload.headroom_state,
          headroom_exhausted_streak: .wans[0].upload.headroom_exhausted_streak,
          anti_windup_triggers: .wans[0].upload.anti_windup_triggers,
          rtt_integral_ms_s: .wans[0].upload.rtt_integral_ms_s,
          docsis_mode_active: .wans[0].upload.docsis_mode_active,
          red_decay_step_pct: .wans[0].upload.red_decay_step_pct,
          red_decay_delta_max_pct: .wans[0].upload.red_decay_delta_max_pct,
          load_rtt_ms: .wans[0].load_rtt_ms,
          baseline_rtt_ms: .wans[0].baseline_rtt_ms,
          load_rtt_delta_us: (
            if (.wans[0].load_rtt_ms == null) or (.wans[0].baseline_rtt_ms == null)
            then null
            else ((.wans[0].load_rtt_ms - .wans[0].baseline_rtt_ms) * 1000 | floor)
            end
          ),
          last_zone: .wans[0].upload.hysteresis.last_zone,
          ul_hysteresis_window_start_epoch: .wans[0].upload.hysteresis.window_start_epoch,
          ul_suppressions_completed_window_count: .wans[0].upload.hysteresis.suppressions_completed_window_count,
          ul_suppressions_completed_window_by_cause: .wans[0].upload.hysteresis.suppressions_completed_window_by_cause,
          ul_suppressions_lifetime_by_cause: .wans[0].upload.hysteresis.suppressions_lifetime_by_cause
        }' < "$body_tmp" > "$out_tmp" 2>/dev/null; then
      failure_mode="jq_parse_error"
      last_message="jq parse failed; body first 200 chars: $(head -c 200 "$body_tmp" 2>/dev/null || true)"
      jq_parse_error=$((jq_parse_error + 1))
    elif [ "$(wc -c < "$out_tmp")" -eq 0 ]; then
      failure_mode="jq_parse_error"
      last_message="jq produced empty output; body first 200 chars: $(head -c 200 "$body_tmp" 2>/dev/null || true)"
      jq_parse_error=$((jq_parse_error + 1))
    fi
  fi

  row_total=$((row_total + 1))

  if [ -z "$failure_mode" ]; then
    cat "$out_tmp" >> "$CAPTURE_DIR/soak-capture.ndjson"
  else
    row_failed=$((row_failed + 1))
    # HRDN-02 (M-4): scrub tab/newline/CR from last_message before TSV write.
    last_message_clean=$(printf '%s' "$last_message" | tr -d '\t\n\r')
    printf '%s\t%s\t%s\t%s\n' "$(date -u -Iseconds)" "$failure_mode" "$curl_exit" "$last_message_clean" >> "$SIDECAR_TSV"
  fi

  sleep 1

  # HRDN-02: threshold gate, evaluated each iteration after the sleep.
  if [ "$row_total" -ge "$MIN_SAMPLES_BEFORE_EVAL" ] && [ "$row_failed" -gt 0 ]; then
    exceeded=$(awk -v f="$row_failed" -v t="$row_total" -v thr="$SOAK_FAIL_RATE_THRESHOLD" \
      'BEGIN { print ((f/t) > thr) ? 1 : 0 }')
    if [ "$exceeded" = "1" ]; then
      rate=$(awk -v f="$row_failed" -v t="$row_total" 'BEGIN { printf "%.4f", f/t }')
      echo "soak-capture: ABORT — lifetime failure rate ${rate} exceeded threshold ${SOAK_FAIL_RATE_THRESHOLD} after ${row_total} attempted rows" >&2
      echo "  row_failed=${row_failed} row_total=${row_total}" >&2
      echo "  curl_exit_nonzero=${curl_exit_nonzero} curl_http_nonzero=${curl_http_nonzero} jq_parse_error=${jq_parse_error} empty_body=${empty_body}" >&2
      echo "  sidecar: ${SIDECAR_TSV}" >&2
      exit 1
    fi
  fi
done

echo "soak-capture: complete — row_total=${row_total} row_failed=${row_failed} (threshold=${SOAK_FAIL_RATE_THRESHOLD})" >&2
echo "  curl_exit_nonzero=${curl_exit_nonzero} curl_http_nonzero=${curl_http_nonzero} jq_parse_error=${jq_parse_error} empty_body=${empty_body}" >&2
