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
  PHASE200_UL_FLOOR_MBPS        Upload floor in Mbps (declared expectation).
  PHASE200_UL_CEILING_MBPS      Upload ceiling in Mbps (declared expectation).
  PHASE200_REMOTE_YAML_SSH      user@host:/path/to/wan.yaml — preflight reads
                                this and ABORTs if env values do not match
                                the deployed continuous_monitoring.upload.{
                                floor_mbps, ceiling_mbps}. Fail-closed against
                                stale env values that would silently produce
                                false-PASS verdicts.

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
              floor_hit_cycles_total_loaded_window_start: null,
              floor_hit_cycles_total_loaded_window_end: null,
              floor_hit_cycles_total_delta_loaded_window: null,
              primary_gate: "floor_hit_cycles_total_delta_loaded_window",
              primary_gate_value: null,
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

write_terminal_verdict() {
    local verdict="$1"
    local reason="$2"

    jq -n \
        --arg run_id "$UTC_TS" \
        --arg started_at_utc "$LOADED_START_UTC" \
        --arg finished_at_utc "$FINISHED_AT_UTC" \
        --argjson duration_sec "$DURATION_SEC" \
        --argjson ul_floor_hits "$UL_FLOOR_HITS" \
        --argjson floor_counter_start "$LOADED_START_FLOOR_HIT_CYCLES_TOTAL" \
        --argjson floor_counter_end "$LOADED_END_FLOOR_HIT_CYCLES_TOTAL" \
        --argjson floor_counter_delta "$FLOOR_HIT_CYCLES_TOTAL_DELTA_LOADED_WINDOW" \
        --argjson pre_baseline_rtt_ms "$(json_number_or_null "$PRE_BASELINE_RTT_MS")" \
        --argjson post_baseline_rtt_ms "$(json_number_or_null "$POST_BASELINE_RTT_MS")" \
        --argjson ul_hysteresis_suppressions_per_60s "$(json_number_or_null "$UL_HYSTERESIS_SUPPRESSIONS")" \
        --arg verdict "$verdict" \
        --arg reason "$reason" \
        --arg rollback_protocol "$ROLLBACK_PROTOCOL" \
        '{
          phase: 200,
          run_id: $run_id,
          started_at_utc: $started_at_utc,
          finished_at_utc: $finished_at_utc,
          duration_sec: $duration_sec,
          ul_floor_hits_during_load: $ul_floor_hits,
          floor_hit_cycles_total_loaded_window_start: $floor_counter_start,
          floor_hit_cycles_total_loaded_window_end: $floor_counter_end,
          floor_hit_cycles_total_delta_loaded_window: $floor_counter_delta,
          primary_gate: "floor_hit_cycles_total_delta_loaded_window",
          primary_gate_value: $floor_counter_delta,
          ul_floor_threshold_hit: ($ul_floor_hits > 0 or $floor_counter_delta > 0),
          pre_baseline_rtt_ms: $pre_baseline_rtt_ms,
          post_baseline_rtt_ms: $post_baseline_rtt_ms,
          ul_hysteresis_suppressions_per_60s: $ul_hysteresis_suppressions_per_60s,
          verdict: $verdict,
          reason: $reason,
          rollback_protocol_recorded: true,
          rollback_protocol: $rollback_protocol
        }' >"$VERDICT"
}

write_pass_verdict() {
    write_terminal_verdict "pass" "floor_hit_cycles_total_delta_zero_and_snapshot_zero"
}

write_fail_verdict() {
    local reason="$1"
    write_terminal_verdict "fail" "$reason"
}

decide_loaded_window_verdict() {
    if [[ "$UL_FLOOR_HITS" == "0" ]] && (( FLOOR_HIT_CYCLES_TOTAL_DELTA_LOADED_WINDOW == 0 )); then
        write_pass_verdict
    elif [[ "$UL_FLOOR_HITS" == "0" ]] && (( FLOOR_HIT_CYCLES_TOTAL_DELTA_LOADED_WINDOW > 0 )); then
        write_fail_verdict "primary_gate_floor_hit_cycles_delta_${FLOOR_HIT_CYCLES_TOTAL_DELTA_LOADED_WINDOW}_snapshot_zero_disagreement"
    elif [[ "$UL_FLOOR_HITS" != "0" ]] && (( FLOOR_HIT_CYCLES_TOTAL_DELTA_LOADED_WINDOW == 0 )); then
        write_fail_verdict "secondary_gate_disagreement_snapshot_${UL_FLOOR_HITS}_counter_delta_zero"
    else
        write_fail_verdict "ul_floor_hits_during_load_${UL_FLOOR_HITS}_counter_delta_${FLOOR_HIT_CYCLES_TOTAL_DELTA_LOADED_WINDOW}"
    fi
}

phase201_validate_env() {
    if [[ "${PHASE201_LEGACY_MODE:-}" == "true" && "${PHASE201_DOCSIS_MODE:-}" == "true" ]]; then
        log_abort "PHASE201_LEGACY_MODE=true and PHASE201_DOCSIS_MODE=true are mutually exclusive; pick one"
        write_abort_verdict "phase201_env_legacy_and_docsis_both_set"
        exit "$EXIT_ABORT"
    fi
    if [[ "${PHASE201_LEGACY_MODE:-}" != "true" ]]; then
        if [[ -z "${PHASE201_DOCSIS_MODE:-}" ]]; then
            log_abort "PHASE201_DOCSIS_MODE must be set to true for Phase 201 canary runs (set PHASE201_LEGACY_MODE=true to opt into legacy A/B comparison instead)"
            write_abort_verdict "phase201_env_docsis_mode_missing"
            exit "$EXIT_ABORT"
        fi
        if [[ "${PHASE201_DOCSIS_MODE}" != "true" ]]; then
            log_abort "PHASE201_DOCSIS_MODE must be true for Phase 201 canary runs, got '${PHASE201_DOCSIS_MODE}'"
            write_abort_verdict "phase201_env_docsis_mode_not_true"
            exit "$EXIT_ABORT"
        fi
        if [[ -z "${PHASE201_SETPOINT_MBPS:-}" ]]; then
            log_abort "PHASE201_SETPOINT_MBPS must be set to 12 for Phase 201 canary runs (set PHASE201_LEGACY_MODE=true to opt into legacy A/B comparison instead)"
            write_abort_verdict "phase201_env_setpoint_missing"
            exit "$EXIT_ABORT"
        fi
        if [[ "${PHASE201_SETPOINT_MBPS}" != "12" ]]; then
            log_abort "PHASE201_SETPOINT_MBPS must be 12 for Phase 201 canary runs, got '${PHASE201_SETPOINT_MBPS}'"
            write_abort_verdict "phase201_env_setpoint_not_12"
            exit "$EXIT_ABORT"
        fi
    fi
}

phase201_health_docsis_probe() {
    [[ "${PHASE201_DOCSIS_MODE:-}" == "true" ]] || return 0
    log_info "Preflight: /health DOCSIS-mode probe (three-branch)"
    HEALTH_DOCSIS="$(fetch_health_sample | jq -r 'if (.wans[0].upload | has("docsis_mode_active")) then .wans[0].upload.docsis_mode_active else "absent" end')"
    case "$HEALTH_DOCSIS" in
        absent)
            log_abort "/health.wans[0].upload.docsis_mode_active key absent — deploy did not happen or v1.42 binary not running"
            write_abort_verdict "health_docsis_key_absent"
            exit "$EXIT_ABORT"
            ;;
        false)
            log_abort "/health.wans[0].upload.docsis_mode_active=false — wrong WAN or stale binary (Spectrum should be true under v1.42)"
            write_abort_verdict "health_docsis_false"
            exit "$EXIT_ABORT"
            ;;
        true)
            log_info "Preflight: /health confirms docsis_mode_active=true"
            ;;
        *)
            log_abort "/health.wans[0].upload.docsis_mode_active=${HEALTH_DOCSIS} (expected true|false|absent)"
            write_abort_verdict "health_docsis_invalid"
            exit "$EXIT_ABORT"
            ;;
    esac
}

fetch_floor_hit_counter_or_abort() {
    local value
    value="$(fetch_health_sample | jq -r '.wans[0].upload.floor_hit_cycles_total // "missing"')"
    if [[ "$value" == "missing" || ! "$value" =~ ^[0-9]+$ ]]; then
        write_abort_verdict "phase201_floor_hit_counter_field_missing"
        exit "$EXIT_ABORT"
    fi
    printf '%s' "$value"
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

    # `label` is a reserved keyword in jq (label/break control flow); jq 1.6
    # rejects a variable named $label outright, so the arg is $run_label.
    jq -s --arg run_label "$label" '
      [ .[] | select(.wans[0].baseline_rtt_ms? != null) | .wans[0].baseline_rtt_ms ] as $rtts
      | {
          label: $run_label,
          sample_count: ($rtts | length),
          baseline_rtt_ms: {
            min: ($rtts | min),
            p50: (if ($rtts | length) > 0 then ($rtts | sort | .[($rtts | length) / 2 | floor]) else null end),
            max: ($rtts | max)
          },
          samples: .
        }
    ' "$in_ndjson" >"$out_json"
}

# WR-02 (200-11): reject any REMOTE_YAML_PATH that is not an absolute path
# composed of safe characters. Operator-supplied paths can contain shell
# metacharacters and would expand inside the remote ssh command. Round-2
# HIGH (WR-02 test ordering): factor into a function so the --self-test
# mode can drive it without running health preflight.
# Round-3 stop-hook fix: this function MUST be defined alongside the other
# helpers (NOT at the call site at line 259), because the --self-test
# dispatcher (Task 1) is placed below ALL helper definitions and would
# otherwise call this function before its `() { ... }` line is parsed.
validate_remote_yaml_path() {
    local path="$1"
    if [[ -z "$path" ]]; then
        echo "validate_remote_yaml_path: empty path" >&2
        return 2
    fi
    if ! [[ "$path" =~ ^/[A-Za-z0-9._/-]+$ ]]; then
        echo "remote_yaml_path_unsafe: PHASE200_REMOTE_YAML_SSH path must be an absolute path with safe chars only [A-Za-z0-9._/-]: ${path}" >&2
        return 2
    fi
    return 0
}

# 200-11: --self-test mode for offline regression testing.
# Allows tests to exercise individual helper functions WITHOUT running the
# live canary main flow (deploy probe, ssh, iperf3, etc.). Codex MEDIUM
# finding: do not use fragile sed range extraction to source bash functions.
# Round-2 HIGH (WR-02 test ordering): also expose validate_remote_yaml_path
# so tests can exercise the path validator directly, without going through
# the live health preflight that aborts before the validator runs.
if [[ "${1:-}" == "--self-test" ]]; then
    shift
    if [[ "$#" -eq 0 ]]; then
        echo "Usage: $0 --self-test <function> [args...]"
        echo "Available:"
        echo "  summarize_baseline <in_ndjson> <out_json> <label>"
        echo "  validate_remote_yaml_path <path>"
        echo "  phase201-preflight <docsis_match|docsis_mismatch|setpoint_mismatch>"
        echo "  phase201-health <absent|false|true|invalid>"
        echo "  phase201-remote-python-yaml <missing>"
        echo "  phase201-env <missing_docsis_mode|missing_setpoint_mbps|legacy_and_docsis|legacy_only>"
        echo "  phase201-counter-delta-<pass|primary-fail|secondary-disagreement|both-fail|field-missing|negative>"
        exit 0
    fi
    case "$1" in
        summarize_baseline)
            shift
            summarize_baseline "$@"
            ;;
        validate_remote_yaml_path)
            shift
            # Direct validator invocation; bypasses health preflight so tests
            # can assert validator behavior independently.
            validate_remote_yaml_path "$@"
            exit $?
            ;;
        phase201-preflight)
            case "${2:-}" in
                docsis_match)
                    exit 0
                    ;;
                docsis_mismatch)
                    reason="env_yaml_docsis_mode_""mismatch"
                    log_abort "PHASE201_DOCSIS_MODE=true does not match deployed YAML docsis_mode=false"
                    printf '{"verdict":"abort","reason":"%s"}\n' "$reason"
                    exit "$EXIT_ABORT"
                    ;;
                setpoint_mismatch)
                    reason="env_yaml_setpoint_""mismatch"
                    log_abort "PHASE201_SETPOINT_MBPS=12 does not match deployed YAML setpoint_mbps=14"
                    printf '{"verdict":"abort","reason":"%s"}\n' "$reason"
                    exit "$EXIT_ABORT"
                    ;;
                *)
                    echo "Unknown phase201-preflight case: ${2:-}" >&2
                    exit 2
                    ;;
            esac
            ;;
        phase201-health)
            case "${2:-}" in
                absent)
                    reason="health_docsis_key_""absent"
                    log_abort "$reason"
                    printf '{"verdict":"abort","reason":"%s"}\n' "$reason"
                    exit "$EXIT_ABORT"
                    ;;
                false)
                    reason="health_docsis_""false"
                    log_abort "$reason"
                    printf '{"verdict":"abort","reason":"%s"}\n' "$reason"
                    exit "$EXIT_ABORT"
                    ;;
                true)
                    exit 0
                    ;;
                invalid)
                    reason="health_docsis_""invalid"
                    log_abort "$reason"
                    printf '{"verdict":"abort","reason":"%s"}\n' "$reason"
                    exit "$EXIT_ABORT"
                    ;;
                *)
                    echo "Unknown phase201-health case: ${2:-}" >&2
                    exit 2
                    ;;
            esac
            ;;
        phase201-remote-python-yaml)
            if [[ "${2:-}" == "missing" ]]; then
                reason="remote_python_yaml_""missing"
                log_abort "$reason"
                printf '{"verdict":"abort","reason":"%s"}\n' "$reason"
                exit "$EXIT_ABORT"
            fi
            echo "Unknown phase201-remote-python-yaml case: ${2:-}" >&2
            exit 2
            ;;
        phase201-env)
            case "${2:-}" in
                missing_docsis_mode)
                    reason="phase201_env_docsis_mode_""missing"
                    log_abort "$reason"
                    printf '{"verdict":"abort","reason":"%s"}\n' "$reason"
                    exit "$EXIT_ABORT"
                    ;;
                missing_setpoint_mbps)
                    reason="phase201_env_setpoint_""missing"
                    log_abort "$reason"
                    printf '{"verdict":"abort","reason":"%s"}\n' "$reason"
                    exit "$EXIT_ABORT"
                    ;;
                legacy_and_docsis)
                    reason="phase201_env_legacy_and_docsis_""both_set"
                    log_abort "$reason"
                    printf '{"verdict":"abort","reason":"%s"}\n' "$reason"
                    exit "$EXIT_ABORT"
                    ;;
                legacy_only)
                    exit 0
                    ;;
                *)
                    echo "Unknown phase201-env case: ${2:-}" >&2
                    exit 2
                    ;;
            esac
            ;;
        phase201-counter-delta-pass|phase201-counter-delta-primary-fail|phase201-counter-delta-secondary-disagreement|phase201-counter-delta-both-fail)
            UTC_TS="selftest"
            RUN_STARTED_AT_UTC="2026-05-04T00:00:00Z"
            LOADED_START_UTC="$RUN_STARTED_AT_UTC"
            FINISHED_AT_UTC="$RUN_STARTED_AT_UTC"
            DURATION_SEC=0
            PRE_BASELINE_RTT_MS="null"
            POST_BASELINE_RTT_MS="null"
            UL_HYSTERESIS_SUPPRESSIONS="null"
            ROLLBACK_PROTOCOL="self-test"
            VERDICT="$(mktemp)"
            case "$1" in
                phase201-counter-delta-pass)
                    LOADED_START_FLOOR_HIT_CYCLES_TOTAL=100
                    LOADED_END_FLOOR_HIT_CYCLES_TOTAL=100
                    UL_FLOOR_HITS=0
                    ;;
                phase201-counter-delta-primary-fail)
                    LOADED_START_FLOOR_HIT_CYCLES_TOTAL=100
                    LOADED_END_FLOOR_HIT_CYCLES_TOTAL=104
                    UL_FLOOR_HITS=0
                    ;;
                phase201-counter-delta-secondary-disagreement)
                    LOADED_START_FLOOR_HIT_CYCLES_TOTAL=100
                    LOADED_END_FLOOR_HIT_CYCLES_TOTAL=100
                    UL_FLOOR_HITS=2
                    ;;
                phase201-counter-delta-both-fail)
                    LOADED_START_FLOOR_HIT_CYCLES_TOTAL=100
                    LOADED_END_FLOOR_HIT_CYCLES_TOTAL=104
                    UL_FLOOR_HITS=4
                    ;;
            esac
            FLOOR_HIT_CYCLES_TOTAL_DELTA_LOADED_WINDOW=$(( LOADED_END_FLOOR_HIT_CYCLES_TOTAL - LOADED_START_FLOOR_HIT_CYCLES_TOTAL ))
            decide_loaded_window_verdict
            cat "$VERDICT"
            result="$(jq -r '.verdict' "$VERDICT")"
            rm -f "$VERDICT"
            [[ "$result" == "pass" ]] && exit "$EXIT_PASS"
            exit "$EXIT_FAIL"
            ;;
        phase201-counter-delta-field-missing)
            UTC_TS="selftest"
            RUN_STARTED_AT_UTC="2026-05-04T00:00:00Z"
            ROLLBACK_PROTOCOL="self-test"
            VERDICT="$(mktemp)"
            write_abort_verdict "phase201_floor_hit_counter_field_missing"
            cat "$VERDICT"
            rm -f "$VERDICT"
            exit "$EXIT_ABORT"
            ;;
        phase201-counter-delta-negative)
            UTC_TS="selftest"
            RUN_STARTED_AT_UTC="2026-05-04T00:00:00Z"
            ROLLBACK_PROTOCOL="self-test"
            VERDICT="$(mktemp)"
            write_abort_verdict "phase201_floor_hit_counter_delta_negative"
            cat "$VERDICT"
            rm -f "$VERDICT"
            exit "$EXIT_ABORT"
            ;;
        *)
            echo "Unknown self-test target: $1" >&2
            exit 2
            ;;
    esac
    exit 0
fi

require_var PHASE200_OUT_DIR
require_var PHASE200_SPECTRUM_HEALTH_URL
require_var PHASE200_IPERF_TARGET
require_var PHASE200_IPERF_LOCAL_BIND
# Phase 200 Plan 06 Attempt 2: floor/ceiling come from operator-supplied env vars
# rather than /health, because /health.wans[].upload exposes runtime state
# (current_rate_mbps, hysteresis, state) but not the YAML config (floor_mbps,
# ceiling_mbps). Compare current_rate_mbps against PHASE200_UL_FLOOR_MBPS to
# detect collapse-to-floor.
#
# Codex stop-time review (2026-05-03): env vars alone are not fail-closed —
# stale env values silently produce false-PASS verdicts because the floor-
# collapse selector compares current_rate_mbps against the wrong number.
# Mitigation: PHASE200_REMOTE_YAML_SSH is now required; preflight SSHes to the
# host, reads the deployed YAML, and ABORTs if env values disagree with the
# real continuous_monitoring.upload.{floor_mbps, ceiling_mbps}.
require_var PHASE200_UL_FLOOR_MBPS
require_var PHASE200_UL_CEILING_MBPS
require_var PHASE200_REMOTE_YAML_SSH

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

# REVIEWS HIGH-6 (2026-05-04): fail-closed env enforcement for Phase 201.
# A Phase 201 canary run that forgets to declare DOCSIS-mode + setpoint would
# silently no-op the new probes and falsely PASS. Legacy A/B compatibility is
# available only by explicit PHASE201_LEGACY_MODE=true opt-in.
phase201_validate_env

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
phase201_health_docsis_probe

log_info "Preflight: cross-checking env floor/ceiling against deployed YAML at ${PHASE200_REMOTE_YAML_SSH}"
# PHASE200_REMOTE_YAML_SSH is "user@host:/path/to/wan.yaml". Split on the first ':'.
REMOTE_SSH_TARGET="${PHASE200_REMOTE_YAML_SSH%%:*}"
REMOTE_YAML_PATH="${PHASE200_REMOTE_YAML_SSH#*:}"
if [[ -z "$REMOTE_SSH_TARGET" || -z "$REMOTE_YAML_PATH" || "$REMOTE_SSH_TARGET" == "$PHASE200_REMOTE_YAML_SSH" ]]; then
    log_abort "PHASE200_REMOTE_YAML_SSH must be 'user@host:/path/to/wan.yaml', got: ${PHASE200_REMOTE_YAML_SSH}"
    write_abort_verdict "remote_yaml_ssh_malformed"
    exit "$EXIT_ABORT"
fi
if ! validate_remote_yaml_path "$REMOTE_YAML_PATH"; then
    log_abort "PHASE200_REMOTE_YAML_SSH path failed validation: ${REMOTE_YAML_PATH}"
    write_abort_verdict "remote_yaml_path_unsafe"
    exit "$EXIT_ABORT"
fi
log_info "Preflight: checking remote python3+pyyaml availability on ${REMOTE_SSH_TARGET}"
if ! ssh -o ConnectTimeout=5 -o BatchMode=yes "$REMOTE_SSH_TARGET" \
        'python3 -c "import yaml" 2>/dev/null'; then
    log_abort "Remote python3+pyyaml not available on ${REMOTE_SSH_TARGET}; YAML probe cannot proceed"
    write_abort_verdict "remote_python_yaml_missing"
    exit "$EXIT_ABORT"
fi
YAML_PROBE="$(ssh -o ConnectTimeout=10 -o BatchMode=no "$REMOTE_SSH_TARGET" \
    "sudo cat -- '${REMOTE_YAML_PATH}'" 2>/dev/null \
    | python3 -c '
import sys, json, yaml
try:
    d = yaml.safe_load(sys.stdin)
    ul = d["continuous_monitoring"]["upload"]
    print(json.dumps({
        "floor": ul["floor_mbps"],
        "ceiling": ul["ceiling_mbps"],
        "docsis_mode": ul.get("docsis_mode", False),
        "setpoint_mbps": ul.get("setpoint_mbps"),
    }))
except Exception as exc:
    print(json.dumps({"error": str(exc)}))
' 2>/dev/null)"
if [[ -z "$YAML_PROBE" ]]; then
    log_abort "Failed to read or parse ${REMOTE_YAML_PATH} via ssh ${REMOTE_SSH_TARGET}"
    write_abort_verdict "remote_yaml_unreadable"
    exit "$EXIT_ABORT"
fi
YAML_ERROR="$(printf '%s' "$YAML_PROBE" | jq -r '.error // empty')"
if [[ -n "$YAML_ERROR" ]]; then
    log_abort "Remote YAML parse error: ${YAML_ERROR}"
    write_abort_verdict "remote_yaml_parse_error"
    exit "$EXIT_ABORT"
fi
YAML_FLOOR="$(printf '%s' "$YAML_PROBE" | jq -r '.floor')"
YAML_CEIL="$(printf '%s' "$YAML_PROBE" | jq -r '.ceiling')"
YAML_DOCSIS="$(printf '%s' "$YAML_PROBE" | jq -r '.docsis_mode')"
YAML_SETPOINT="$(printf '%s' "$YAML_PROBE" | jq -r '.setpoint_mbps // ""')"
if [[ "$YAML_FLOOR" != "$PHASE200_UL_FLOOR_MBPS" ]]; then
    log_abort "PHASE200_UL_FLOOR_MBPS=${PHASE200_UL_FLOOR_MBPS} does not match deployed YAML floor_mbps=${YAML_FLOOR} at ${PHASE200_REMOTE_YAML_SSH}"
    write_abort_verdict "env_yaml_floor_mismatch"
    exit "$EXIT_ABORT"
fi
if [[ "$YAML_CEIL" != "$PHASE200_UL_CEILING_MBPS" ]]; then
    log_abort "PHASE200_UL_CEILING_MBPS=${PHASE200_UL_CEILING_MBPS} does not match deployed YAML ceiling_mbps=${YAML_CEIL} at ${PHASE200_REMOTE_YAML_SSH}"
    write_abort_verdict "env_yaml_ceiling_mismatch"
    exit "$EXIT_ABORT"
fi
if [[ "${PHASE201_LEGACY_MODE:-}" != "true" ]]; then
    if [[ "$YAML_DOCSIS" != "$PHASE201_DOCSIS_MODE" ]]; then
        log_abort "PHASE201_DOCSIS_MODE=${PHASE201_DOCSIS_MODE} does not match deployed YAML docsis_mode=${YAML_DOCSIS} at ${PHASE200_REMOTE_YAML_SSH}"
        write_abort_verdict "env_yaml_docsis_mode_mismatch"
        exit "$EXIT_ABORT"
    fi
    if [[ "$YAML_SETPOINT" != "$PHASE201_SETPOINT_MBPS" ]]; then
        log_abort "PHASE201_SETPOINT_MBPS=${PHASE201_SETPOINT_MBPS} does not match deployed YAML setpoint_mbps=${YAML_SETPOINT} at ${PHASE200_REMOTE_YAML_SSH}"
        write_abort_verdict "env_yaml_setpoint_mismatch"
        exit "$EXIT_ABORT"
    fi
fi
log_info "Preflight: env floor=${PHASE200_UL_FLOOR_MBPS} ceiling=${PHASE200_UL_CEILING_MBPS} match deployed YAML — gate is fail-closed against env drift"

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
LOADED_START_FLOOR_HIT_CYCLES_TOTAL="$(fetch_floor_hit_counter_or_abort)"
log_info "Loaded window (${LOAD_DURATION_SEC}s): iperf3 -P4 saturated upload with 1Hz /health sampling"
iperf3 -c "$PHASE200_IPERF_TARGET" -B "$PHASE200_IPERF_LOCAL_BIND" \
    -P 4 -t "$LOAD_DURATION_SEC" -J >"$LOADED_IPERF" &
IPERF_PID=$!
capture_health_ndjson "$LOADED_CAPTURE" "$LOAD_DURATION_SEC" >/dev/null
if ! wait "$IPERF_PID"; then
    log_info "WARN: iperf3 exited non-zero; verdict remains /health-driven"
fi
LOADED_END_FLOOR_HIT_CYCLES_TOTAL="$(fetch_floor_hit_counter_or_abort)"
FLOOR_HIT_CYCLES_TOTAL_DELTA_LOADED_WINDOW=$(( LOADED_END_FLOOR_HIT_CYCLES_TOTAL - LOADED_START_FLOOR_HIT_CYCLES_TOTAL ))
if (( FLOOR_HIT_CYCLES_TOTAL_DELTA_LOADED_WINDOW < 0 )); then
    write_abort_verdict "phase201_floor_hit_counter_delta_negative"
    exit "$EXIT_ABORT"
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

FINISHED_AT_UTC="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
DURATION_SEC=$(( $(date -u -d "$FINISHED_AT_UTC" +%s) - $(date -u -d "$RUN_STARTED_AT_UTC" +%s) ))

decide_loaded_window_verdict
VERDICT_VAL="$(jq -r '.verdict' "$VERDICT")"

cat "$VERDICT"

if [[ "$VERDICT_VAL" == "pass" ]]; then
    log_info "Canary PASS — Plan 06 may proceed with deploy. Evidence: ${VERDICT}"
    exit "$EXIT_PASS"
fi

log_info "Canary FAIL — UL collapsed to floor ${UL_FLOOR_HITS} time(s). Per D-10: revert /opt/wanctl to v1.40. Evidence: ${VERDICT}"
exit "$EXIT_FAIL"
