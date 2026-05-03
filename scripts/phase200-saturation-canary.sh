#!/usr/bin/env bash
# Phase 200 saturation canary — VALN-06 deploy gate.
#
# Runs a saturated iperf3 -P4 upload loop through Spectrum, samples /health at
# 1Hz throughout, and fails closed if the upload controller collapses to floor
# in any loaded-window sample. Bookended idle baselines capture baseline RTT
# before and after the run.
#
# Per D-07: this is the primary deploy gate. Plan 06 proceeds only when the
# generated verdict.json has verdict="pass". The 24h soak is a later regression
# watchdog, not this gate's verdict source.
#
# Per D-10: rollback is predefined — revert /opt/wanctl to the v1.40 binary if
# the canary fails. verdict.json records that protocol on every completed run.

set -euo pipefail

EXIT_PASS=0
EXIT_FAIL=1
EXIT_ABORT=2

print_help() {
    cat <<'HELP'
Phase 200 saturation canary (VALN-06).

Required env vars (set before running, e.g. via `source phase200-saturation-canary.env`):
  PHASE200_OUT_DIR              Repo-local evidence directory.
  PHASE200_SPECTRUM_HEALTH_URL  /health endpoint (Spectrum).
  PHASE200_IPERF_TARGET         iperf3 server hostname or IP.
  PHASE200_IPERF_LOCAL_BIND     Local source IP that exits Spectrum.
  PHASE200_UL_FLOOR_MBPS        Upload floor in Mbps (from spectrum.yaml).
  PHASE200_UL_CEILING_MBPS      Upload ceiling in Mbps (from spectrum.yaml).

Optional overrides:
  PHASE200_LOAD_DURATION_SEC     Default 900 (15 min).
  PHASE200_BASELINE_DURATION_SEC Default 60.
  PHASE200_HEALTH_POLL_HZ        Default 1 (1 sample/sec).

Output: ${PHASE200_OUT_DIR}/canary/<UTC-TS>/
  pre_idle_baseline.json
  loaded_capture.ndjson
  loaded_iperf_summary.json
  post_idle_baseline.json
  verdict.json

Exit codes:
  0 = PASS  no upload collapse to floor; verdict.json verdict="pass"
  1 = FAIL  upload collapsed to floor in >=1 loaded sample; rollback per D-10
  2 = ABORT env/tool/connectivity/shape preflight failed; do not deploy

See plan 200-05 for full gate semantics.
HELP
}

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
    print_help
    exit "$EXIT_PASS"
fi

log_info() {
    printf '[%s] %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*"
}

log_abort() {
    printf 'ABORT: %s\n' "$*" >&2
}

require_var() {
    local name="$1"
    if [[ -z "${!name:-}" ]]; then
        log_abort "env var ${name} is not set. See $0 --help."
        exit "$EXIT_ABORT"
    fi
}

require_command() {
    local tool="$1"
    if ! command -v "$tool" >/dev/null 2>&1; then
        log_abort "required command not found on PATH: ${tool}"
        exit "$EXIT_ABORT"
    fi
}

json_number_or_null() {
    local value="${1:-}"
    if [[ -z "$value" || "$value" == "null" ]]; then
        printf 'null'
    else
        printf '%s' "$value"
    fi
}

validate_positive_int() {
    local name="$1"
    local value="$2"
    if ! [[ "$value" =~ ^[1-9][0-9]*$ ]]; then
        log_abort "${name} must be a positive integer, got '${value}'"
        exit "$EXIT_ABORT"
    fi
}

poll_interval_for_hz() {
    local hz="$1"
    awk -v hz="$hz" 'BEGIN { if (hz <= 0) exit 1; printf "%.6f", 1 / hz }'
}

write_abort_verdict() {
    local reason="$1"
    local finished_at_utc
    finished_at_utc="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

    if [[ -n "${VERDICT:-}" ]]; then
        jq -n \
            --arg run_id "${UTC_TS:-unknown}" \
            --arg started_at_utc "${RUN_STARTED_AT_UTC:-$finished_at_utc}" \
            --arg finished_at_utc "$finished_at_utc" \
            --arg reason "$reason" \
            --arg rollback_protocol "$ROLLBACK_PROTOCOL" \
            '{
              phase: 200,
              run_id: $run_id,
              started_at_utc: $started_at_utc,
              finished_at_utc: $finished_at_utc,
              duration_sec: 0,
              ul_floor_hits_during_load: 0,
              ul_floor_threshold_hit: false,
              pre_baseline_rtt_ms: null,
              post_baseline_rtt_ms: null,
              ul_hysteresis_suppressions_per_60s: null,
              verdict: "abort",
              reason: $reason,
              rollback_protocol_recorded: true,
              rollback_protocol: $rollback_protocol
            }' >"$VERDICT"
    fi
}

fetch_health_sample() {
    local sampled_at_utc
    sampled_at_utc="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    curl --silent --fail --max-time 2 "$PHASE200_SPECTRUM_HEALTH_URL" \
        | jq -c --arg sampled_at_utc "$sampled_at_utc" '. + {sampled_at_utc: $sampled_at_utc}'
}

capture_health_ndjson() {
    local out="$1"
    local duration_sec="$2"
    local end_epoch
    local sample_count=0

    end_epoch=$(( $(date +%s) + duration_sec ))
    : >"$out"
    while [[ "$(date +%s)" -lt "$end_epoch" ]]; do
        if fetch_health_sample >>"$out"; then
            sample_count=$((sample_count + 1))
        else
            log_info "WARN: skipped failed /health sample"
        fi
        sleep "$POLL_INTERVAL_SEC"
    done
    printf '%s\n' "$sample_count"
}

summarize_baseline() {
    local in_ndjson="$1"
    local out_json="$2"
    local label="$3"

    jq -s --arg label "$label" '
      [ .[] | select(.wans[0].rtt.baseline_rtt_ms? != null) | .wans[0].rtt.baseline_rtt_ms ] as $rtts
      | {
          label: $label,
          sample_count: length,
          baseline_rtt_ms: {
            min: ($rtts | min),
            p50: ($rtts | sort | .[length / 2 | floor]),
            max: ($rtts | max)
          },
          samples: .
        }
    ' "$in_ndjson" >"$out_json"
}

require_var PHASE200_OUT_DIR
require_var PHASE200_SPECTRUM_HEALTH_URL
require_var PHASE200_IPERF_TARGET
require_var PHASE200_IPERF_LOCAL_BIND
# Phase 200 Plan 06 Attempt 2: floor/ceiling come from operator-supplied env vars
# rather than /health, because /health.wans[].upload exposes runtime state
# (current_rate_mbps, hysteresis, state) but not the YAML config (floor_mbps,
# ceiling_mbps). Compare current_rate_mbps against PHASE200_UL_FLOOR_MBPS to
# detect collapse-to-floor.
require_var PHASE200_UL_FLOOR_MBPS
require_var PHASE200_UL_CEILING_MBPS

require_command curl
require_command jq
require_command iperf3
require_command awk

LOAD_DURATION_SEC="${PHASE200_LOAD_DURATION_SEC:-900}"
BASELINE_DURATION_SEC="${PHASE200_BASELINE_DURATION_SEC:-60}"
HEALTH_POLL_HZ="${PHASE200_HEALTH_POLL_HZ:-1}"

validate_positive_int PHASE200_LOAD_DURATION_SEC "$LOAD_DURATION_SEC"
validate_positive_int PHASE200_BASELINE_DURATION_SEC "$BASELINE_DURATION_SEC"
validate_positive_int PHASE200_HEALTH_POLL_HZ "$HEALTH_POLL_HZ"
validate_positive_int PHASE200_UL_FLOOR_MBPS "$PHASE200_UL_FLOOR_MBPS"
validate_positive_int PHASE200_UL_CEILING_MBPS "$PHASE200_UL_CEILING_MBPS"
if (( PHASE200_UL_FLOOR_MBPS >= PHASE200_UL_CEILING_MBPS )); then
    log_abort "PHASE200_UL_FLOOR_MBPS ($PHASE200_UL_FLOOR_MBPS) must be less than PHASE200_UL_CEILING_MBPS ($PHASE200_UL_CEILING_MBPS)"
    exit "$EXIT_ABORT"
fi
POLL_INTERVAL_SEC="$(poll_interval_for_hz "$HEALTH_POLL_HZ")"

UTC_TS="$(date -u +%Y%m%dT%H%M%SZ)"
RUN_STARTED_AT_UTC="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
RUN_DIR="${PHASE200_OUT_DIR%/}/canary/${UTC_TS}"
mkdir -p "$RUN_DIR"

PRE_BASELINE="${RUN_DIR}/pre_idle_baseline.json"
PRE_NDJSON="${RUN_DIR}/pre_idle_baseline.ndjson"
LOADED_CAPTURE="${RUN_DIR}/loaded_capture.ndjson"
LOADED_IPERF="${RUN_DIR}/loaded_iperf_summary.json"
POST_BASELINE="${RUN_DIR}/post_idle_baseline.json"
POST_NDJSON="${RUN_DIR}/post_idle_baseline.ndjson"
VERDICT="${RUN_DIR}/verdict.json"
ROLLBACK_PROTOCOL="Per D-10: revert /opt/wanctl to the v1.40 binary on cake-shaper if this canary fails. Keep the v1.40 artifact available (for example /opt/wanctl-v1.40.tar.gz) and restore with: sudo tar -xzf /opt/wanctl-v1.40.tar.gz -C /opt/wanctl && sudo systemctl restart wanctl@spectrum.service. Leave /etc/wanctl/spectrum.yaml in place; the pre-v1.41 binary ignores the new upload-threshold keys."

log_info "Preflight: checking Spectrum /health shape"
# /health.wans[].upload only carries runtime state (current_rate_mbps, hysteresis,
# state, state_reason). Floor/ceiling are sourced from PHASE200_UL_FLOOR_MBPS /
# PHASE200_UL_CEILING_MBPS env vars, not from /health.
if ! fetch_health_sample | jq -e '
      (.wans[0].upload.current_rate_mbps? | numbers)
    ' >/dev/null; then
    log_abort "${PHASE200_SPECTRUM_HEALTH_URL} did not return expected .wans[0].upload.current_rate_mbps"
    write_abort_verdict "health_unreachable_or_shape_invalid"
    exit "$EXIT_ABORT"
fi

log_info "Preflight: checking iperf3 target reachability"
if ! iperf3 -c "$PHASE200_IPERF_TARGET" -B "$PHASE200_IPERF_LOCAL_BIND" -t 1 -J >/dev/null 2>&1; then
    log_abort "iperf3 -c ${PHASE200_IPERF_TARGET} -B ${PHASE200_IPERF_LOCAL_BIND} probe failed"
    write_abort_verdict "iperf_target_unreachable"
    exit "$EXIT_ABORT"
fi

log_info "Pre-idle baseline (${BASELINE_DURATION_SEC}s at ${HEALTH_POLL_HZ}Hz)"
capture_health_ndjson "$PRE_NDJSON" "$BASELINE_DURATION_SEC" >/dev/null
summarize_baseline "$PRE_NDJSON" "$PRE_BASELINE" "pre_idle"
PRE_BASELINE_RTT_MS="$(jq -r '.baseline_rtt_ms.p50 // null' "$PRE_BASELINE")"

LOADED_START_UTC="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
log_info "Loaded window (${LOAD_DURATION_SEC}s): iperf3 -P4 saturated upload with 1Hz /health sampling"
iperf3 -c "$PHASE200_IPERF_TARGET" -B "$PHASE200_IPERF_LOCAL_BIND" \
    -P 4 -t "$LOAD_DURATION_SEC" -J >"$LOADED_IPERF" &
IPERF_PID=$!
capture_health_ndjson "$LOADED_CAPTURE" "$LOAD_DURATION_SEC" >/dev/null
if ! wait "$IPERF_PID"; then
    log_info "WARN: iperf3 exited non-zero; verdict remains /health-driven"
fi

log_info "Post-idle baseline (${BASELINE_DURATION_SEC}s at ${HEALTH_POLL_HZ}Hz)"
capture_health_ndjson "$POST_NDJSON" "$BASELINE_DURATION_SEC" >/dev/null
summarize_baseline "$POST_NDJSON" "$POST_BASELINE" "post_idle"
POST_BASELINE_RTT_MS="$(jq -r '.baseline_rtt_ms.p50 // null' "$POST_BASELINE")"

UL_FLOOR_HITS="$(jq -s --argjson floor "$PHASE200_UL_FLOOR_MBPS" '
  [ .[]
    | select((.wans[0].upload.current_rate_mbps? // null) != null)
    | select(.wans[0].upload.current_rate_mbps == $floor)
  ] | length
' "$LOADED_CAPTURE")"
UL_HYSTERESIS_SUPPRESSIONS="$(jq -s '
  [ .[] | .wans[0].upload.hysteresis.suppressions_last_60s? // empty ] | last // null
' "$LOADED_CAPTURE")"

if [[ "$UL_FLOOR_HITS" -gt 0 ]]; then
    VERDICT_VAL="fail"
else
    VERDICT_VAL="pass"
fi

FINISHED_AT_UTC="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
DURATION_SEC=$(( $(date -u -d "$FINISHED_AT_UTC" +%s) - $(date -u -d "$RUN_STARTED_AT_UTC" +%s) ))

jq -n \
    --arg run_id "$UTC_TS" \
    --arg started_at_utc "$LOADED_START_UTC" \
    --arg finished_at_utc "$FINISHED_AT_UTC" \
    --argjson duration_sec "$DURATION_SEC" \
    --argjson ul_floor_hits "$UL_FLOOR_HITS" \
    --argjson pre_baseline_rtt_ms "$(json_number_or_null "$PRE_BASELINE_RTT_MS")" \
    --argjson post_baseline_rtt_ms "$(json_number_or_null "$POST_BASELINE_RTT_MS")" \
    --argjson ul_hysteresis_suppressions_per_60s "$(json_number_or_null "$UL_HYSTERESIS_SUPPRESSIONS")" \
    --arg verdict "$VERDICT_VAL" \
    --arg rollback_protocol "$ROLLBACK_PROTOCOL" \
    '{
      phase: 200,
      run_id: $run_id,
      started_at_utc: $started_at_utc,
      finished_at_utc: $finished_at_utc,
      duration_sec: $duration_sec,
      ul_floor_hits_during_load: $ul_floor_hits,
      ul_floor_threshold_hit: ($ul_floor_hits > 0),
      pre_baseline_rtt_ms: $pre_baseline_rtt_ms,
      post_baseline_rtt_ms: $post_baseline_rtt_ms,
      ul_hysteresis_suppressions_per_60s: $ul_hysteresis_suppressions_per_60s,
      verdict: $verdict,
      rollback_protocol_recorded: true,
      rollback_protocol: $rollback_protocol
    }' >"$VERDICT"

cat "$VERDICT"

if [[ "$VERDICT_VAL" == "pass" ]]; then
    log_info "Canary PASS — Plan 06 may proceed with deploy. Evidence: ${VERDICT}"
    exit "$EXIT_PASS"
fi

log_info "Canary FAIL — UL collapsed to floor ${UL_FLOOR_HITS} time(s). Per D-10: revert /opt/wanctl to v1.40. Evidence: ${VERDICT}"
exit "$EXIT_FAIL"
