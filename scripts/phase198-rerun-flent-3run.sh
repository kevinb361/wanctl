#!/usr/bin/env bash
#
# Phase 198 gap-closure rerun harness — runs three corrected source-bound
# (10.10.110.226) Spectrum tcp_12down 30s flent captures during the off-peak
# window (02:00-05:00 local) with parallel /health 1Hz sampler and SSH-pulled
# SQLite raw rows for cross-correlation. SAFE-05 invariant: this script does
# NOT modify any file under src/wanctl/.

set -euo pipefail

usage() {
    cat <<'EOF'
Usage:
  scripts/phase198-rerun-flent-3run.sh [options]

Options:
  --output-root <dir>        Flent helper output root (default: ~/flent-results/phase198-rerun)
  --evidence-root <dir>      Evidence root (default: .planning/phases/198-spectrum-cake-primary-b-leg-rerun/soak/cake-primary)
  --remote-host <host>       SSH host for metrics DB (default: ${PHASE196_REMOTE_HOST:-cake-shaper})
  --remote-user <user>       SSH user override (default: empty — defer to ~/.ssh/config; remote sqlite3 runs under sudo -n regardless)
  --remote-db <path>         Remote SQLite DB (default: ${PHASE196_REMOTE_DB:-/var/lib/wanctl/wanctl-spectrum.db})
  --health-url <url>         Health URL (default: http://127.0.0.1:9101/health)
  --local-bind <ip>          Required Spectrum source bind (default: 10.10.110.226)
  --duration <sec>           Flent duration seconds (default: 30)
  --force-window <reason>    Override off-peak refusal and record forced:<reason>
  --allow-extended-window    Allow 01:00-05:59 local instead of 02:00-04:59 local
  --dry-run                  Run gates and SAFE-05 only; do not create evidence or run flent/SSH/health
  --test-hour <H>            Dry-run only: synthetic local hour for window gate
  --help                     Show this help
EOF
}

OUTPUT_ROOT="${HOME}/flent-results/phase198-rerun"
EVIDENCE_ROOT=".planning/phases/198-spectrum-cake-primary-b-leg-rerun/soak/cake-primary"
REMOTE_HOST="${PHASE196_REMOTE_HOST:-cake-shaper}"
REMOTE_USER="${PHASE196_REMOTE_USER:-}"
REMOTE_DB="${PHASE196_REMOTE_DB:-/var/lib/wanctl/wanctl-spectrum.db}"
HEALTH_URL="http://127.0.0.1:9101/health"
LOCAL_BIND="10.10.110.226"
DURATION="30"
FORCE_WINDOW=""
ALLOW_EXTENDED="0"
DRY_RUN="0"
TEST_HOUR=""
PHASE_197_SHIP_SHA="068b804"
ATTEMPT_FAILED_STAGE="init"
COMPLETED_RUNS=0

while [[ $# -gt 0 ]]; do
    case "$1" in
        --output-root)
            OUTPUT_ROOT="${2:-}"
            shift 2
            ;;
        --evidence-root)
            EVIDENCE_ROOT="${2:-}"
            shift 2
            ;;
        --remote-host)
            REMOTE_HOST="${2:-}"
            shift 2
            ;;
        --remote-user)
            REMOTE_USER="${2:-}"
            shift 2
            ;;
        --remote-db)
            REMOTE_DB="${2:-}"
            shift 2
            ;;
        --health-url)
            HEALTH_URL="${2:-}"
            shift 2
            ;;
        --local-bind)
            LOCAL_BIND="${2:-}"
            shift 2
            ;;
        --duration)
            DURATION="${2:-}"
            shift 2
            ;;
        --force-window)
            FORCE_WINDOW="${2:-}"
            shift 2
            ;;
        --allow-extended-window)
            ALLOW_EXTENDED="1"
            shift
            ;;
        --dry-run)
            DRY_RUN="1"
            shift
            ;;
        --test-hour)
            TEST_HOUR="${2:-}"
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

if [[ -n "${TEST_HOUR}" && "${DRY_RUN}" != "1" ]]; then
    echo "REFUSED: --test-hour is only honored with --dry-run. Production runs read live wall clock." >&2
    exit 7
fi

if [[ "${LOCAL_BIND}" != "10.10.110.226" ]]; then
    echo "REFUSED: this harness is locked to Spectrum source bind 10.10.110.226 (10.10.110.233 exits AT&T per 196-12-SUMMARY.md)." >&2
    exit 3
fi

if [[ "${DRY_RUN}" == "1" && -n "${TEST_HOUR}" ]]; then
    LOCAL_HOUR="${TEST_HOUR}"
else
    LOCAL_HOUR="$(date +%H)"
fi
ATTEMPTED_AT_UTC="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

ATTEMPT_DIR_PREFIX="${EVIDENCE_ROOT}/rerun-attempt-"
N=1
while [[ -d "${ATTEMPT_DIR_PREFIX}${N}" ]]; do
    N=$((N + 1))
done

ATTEMPT_LOG="${EVIDENCE_ROOT%/soak/cake-primary}/198-06-ATTEMPT-LOG.md"
if [[ ! -f "${ATTEMPT_LOG}" ]]; then
    ATTEMPT_LOG=".planning/phases/198-spectrum-cake-primary-b-leg-rerun/198-06-ATTEMPT-LOG.md"
fi

ATTEMPT_FAILED_STAGE="gates"
if [[ -z "${FORCE_WINDOW}" ]]; then
    if [[ "${ALLOW_EXTENDED}" == "1" ]]; then
        if (( 10#${LOCAL_HOUR} < 1 || 10#${LOCAL_HOUR} > 5 )); then
            echo "REFUSED: hour ${LOCAL_HOUR} outside extended off-peak window 01..05 local. Use --force-window <reason> to override." >&2
            exit 2
        fi
        WINDOW_USED="extended:01-05"
    else
        if (( 10#${LOCAL_HOUR} < 2 || 10#${LOCAL_HOUR} > 4 )); then
            echo "REFUSED: hour ${LOCAL_HOUR} outside off-peak window 02..04 local. Use --allow-extended-window or --force-window <reason>." >&2
            exit 2
        fi
        WINDOW_USED="standard:02-04"
    fi
else
    WINDOW_USED="forced:${FORCE_WINDOW}"
fi

if (( N >= 4 )); then
    FAILED_COUNT=0
    if [[ -f "${ATTEMPT_LOG}" ]]; then
        FAILED_COUNT=$(grep -cE '^- \*\*Operator decision:\*\* (abort|retry)|^- \*\*Failed:\*\* true' "${ATTEMPT_LOG}" 2>/dev/null || true)
    fi
    if (( FAILED_COUNT >= 3 )) && ! grep -q '^continuation_justification:' "${ATTEMPT_LOG}" 2>/dev/null; then
        echo "REFUSED: ${FAILED_COUNT} failed/abort/retry attempts recorded and no 'continuation_justification:' line present in ${ATTEMPT_LOG}. Add the justification line before invoking attempt ${N}." >&2
        exit 6
    fi
fi

ATTEMPT_FAILED_STAGE="safe05"
if ! git diff --quiet "${PHASE_197_SHIP_SHA}..HEAD" -- \
    src/wanctl/queue_controller.py src/wanctl/cake_signal.py \
    src/wanctl/fusion_healer.py src/wanctl/wan_controller.py \
    src/wanctl/health_check.py; then
    echo "REFUSED: SAFE-05 violated — protected source diff non-empty vs ${PHASE_197_SHIP_SHA}" >&2
    exit 4
fi

if [[ "${DRY_RUN}" == "1" ]]; then
    echo "DRY_RUN: gates passed (window=${WINDOW_USED}, bind=10.10.110.226, SAFE-05=clean, hard-abort=ok, next_attempt=${N}). Exiting 0 without running flent."
    exit 0
fi

REF="$(git rev-parse --short HEAD)"
ATTEMPT_DIR="${ATTEMPT_DIR_PREFIX}${N}"
mkdir -p "${ATTEMPT_DIR}/flent" "${OUTPUT_ROOT}"

write_partial_summary() {
    local exit_code=$?
    if [[ -n "${ATTEMPT_DIR:-}" && -d "${ATTEMPT_DIR}" ]]; then
        jq -n \
            --argjson n "${N:-0}" \
            --arg stage "${ATTEMPT_FAILED_STAGE}" \
            --argjson ec "${exit_code}" \
            --argjson cr "${COMPLETED_RUNS}" \
            --arg window "${WINDOW_USED:-pre-gates}" \
            --arg head "${REF:-unknown}" \
            --arg attempted_at_utc "${ATTEMPTED_AT_UTC:-}" \
            --argjson local_hour "$((10#${LOCAL_HOUR:-0}))" \
            '{phase: 198, attempt_number: $n, failed: true,
              harness_exit_code: $ec, failure_stage: $stage,
              completed_runs: $cr, off_peak_window_used: $window,
              head_sha: $head, phase_197_ship_sha: "068b804",
              attempted_at_utc: $attempted_at_utc,
              local_hour_at_start: $local_hour,
              decision: null}' \
            >"${ATTEMPT_DIR}/attempt-summary.json" 2>/dev/null || true
    fi
}
trap 'write_partial_summary' ERR

declare -a PROBE_FILES=()
declare -a FLENT_STARTS=()
declare -a FLENT_ENDS=()
declare -a RUN_MEDIANS=()
declare -a RUN_RAW_EXTERNALS=()

extract_median() {
    .venv/bin/python3 - "$1" <<'PY'
import gzip
import json
import statistics
import sys

with gzip.open(sys.argv[1], "rt") as fh:
    data = json.load(fh)
results = data.get("results", {})
preferred = []
for key in ("TCP download sum", "TCP totals", "TCP download"):
    values = results.get(key)
    if isinstance(values, list):
        preferred = [v for v in values if isinstance(v, (int, float))]
        if preferred:
            break
if not preferred:
    for key, values in results.items():
        kl = key.lower()
        if "tcp" in kl and "download" in kl and "sum" in kl and isinstance(values, list):
            preferred = [v for v in values if isinstance(v, (int, float))]
            if preferred:
                break
if not preferred:
    raise SystemExit("ERROR_NO_TCP_DOWNLOAD_SUM_SERIES")
print(f"{statistics.median(preferred):.6f}")
PY
}

for i in 1 2 3; do
    ATTEMPT_FAILED_STAGE="probe"
    PROBE_FILE="${ATTEMPT_DIR}/probe-run${i}.json"
    curl -s --interface 10.10.110.226 https://ipinfo.io/json >"${PROBE_FILE}"
    EGRESS_IP="$(jq -r '.ip // empty' "${PROBE_FILE}")"
    EGRESS_ORG="$(jq -r '.org // empty' "${PROBE_FILE}")"
    if [[ "${EGRESS_IP}" != "70.123.224.169" ]]; then
        echo "REFUSED: egress IP '${EGRESS_IP}' != 70.123.224.169 (Spectrum). Source bind drift detected." >&2
        exit 5
    fi
    if ! grep -Eq 'Charter|AS11427' <<<"${EGRESS_ORG}"; then
        echo "REFUSED: egress org '${EGRESS_ORG}' does not match Charter|AS11427." >&2
        exit 5
    fi
    TMP_PROBE="${PROBE_FILE}.tmp"
    jq --argjson run "${i}" \
        --arg captured_at_utc "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
        '. + {run: $run, captured_at_utc: $captured_at_utc, public_ip: .ip, egress_ip_matches: true, egress_org_matches: true}' \
        "${PROBE_FILE}" >"${TMP_PROBE}"
    mv "${TMP_PROBE}" "${PROBE_FILE}"
    PROBE_FILES+=("${PROBE_FILE}")

    FLENT_START="$(date -u +%s)"
    FLENT_STARTS+=("${FLENT_START}")
    HEALTH_FILE="${ATTEMPT_DIR}/health-window-run${i}.ndjson"
    ATTEMPT_FAILED_STAGE="health"
    (
        for _ in $(seq 1 "${DURATION}"); do
            TS="$(date -u +%s.%N)"
            curl -s -m 1 "${HEALTH_URL}" | jq -c --arg ts "${TS}" '. + {sampled_utc: $ts}' >>"${HEALTH_FILE}" || true
            sleep 1
        done
    ) &
    HEALTH_PID=$!

    ATTEMPT_FAILED_STAGE="flent"
    LABEL="phase198_rerun_attempt${N}_run${i}"
    ./scripts/phase191-flent-capture.sh \
        --label "${LABEL}" \
        --wan spectrum \
        --local-bind 10.10.110.226 \
        --duration "${DURATION}" \
        --output-dir "${OUTPUT_ROOT}" \
        --tests tcp_12down \
        --ref "${REF}"
    wait "${HEALTH_PID}"
    FLENT_END="$(date -u +%s)"
    FLENT_ENDS+=("${FLENT_END}")

    RAW_FLENT="$(find "${OUTPUT_ROOT}/${LABEL}" -type f -name '*.flent.gz' -printf '%T@ %p\n' | sort -n | tail -n 1 | cut -d' ' -f2-)"
    if [[ -z "${RAW_FLENT}" ]]; then
        echo "ERROR: no flent raw output found under ${OUTPUT_ROOT}/${LABEL}" >&2
        exit 1
    fi
    cp "${RAW_FLENT}" "${ATTEMPT_DIR}/flent/run${i}.flent.gz"
    RUN_RAW_EXTERNALS+=("${RAW_FLENT}")
    RUN_MEDIANS+=("$(extract_median "${ATTEMPT_DIR}/flent/run${i}.flent.gz")")

    ATTEMPT_FAILED_STAGE="sqlite"
    PSV_FILE="${ATTEMPT_DIR}/loaded-window-run${i}.psv"
    ssh -o BatchMode=yes ${REMOTE_USER:+"${REMOTE_USER}@"}"${REMOTE_HOST}" \
        "command -v sqlite3 >/dev/null && sudo -n sqlite3 -readonly -header -separator '|' '${REMOTE_DB}'" \
        >"${PSV_FILE}" <<SQL
SELECT
  datetime(timestamp, 'unixepoch') AS sampled_utc,
  timestamp,
  wan_name,
  metric_name,
  value
FROM metrics
WHERE wan_name = 'spectrum'
  AND metric_name IN (
    'wanctl_arbitration_active_primary',
    'wanctl_arbitration_refractory_active'
  )
  AND timestamp BETWEEN ${FLENT_START} AND ${FLENT_END}
ORDER BY timestamp, metric_name;
SQL

    COMPLETED_RUNS=$((COMPLETED_RUNS + 1))
    if [[ "${i}" != "3" ]]; then
        sleep 5
    fi
done

ATTEMPT_FAILED_STAGE="audit"
for i in 1 2 3; do
    if ! .venv/bin/python3 scripts/phase198-loaded-window-audit.py \
        --health-ndjson "${ATTEMPT_DIR}/health-window-run${i}.ndjson" \
        --psv "${ATTEMPT_DIR}/loaded-window-run${i}.psv" \
        --flent-window-start "${FLENT_STARTS[$((i - 1))]}" \
        --flent-window-end "${FLENT_ENDS[$((i - 1))]}" \
        --run "${i}" \
        --output "${ATTEMPT_DIR}/loaded-window-audit-run${i}.json"; then
        if [[ ! -f "${ATTEMPT_DIR}/loaded-window-audit-run${i}.json" ]]; then
            echo "ERROR: audit run ${i} failed without writing its JSON artifact" >&2
            exit 1
        fi
    fi
done

jq -n \
    --argjson n "${N}" \
    --arg ref "${REF}" \
    --arg bind "10.10.110.226" \
    --slurpfile p1 "${PROBE_FILES[0]}" \
    --slurpfile p2 "${PROBE_FILES[1]}" \
    --slurpfile p3 "${PROBE_FILES[2]}" \
    --arg m1 "${RUN_MEDIANS[0]}" --arg m2 "${RUN_MEDIANS[1]}" --arg m3 "${RUN_MEDIANS[2]}" \
    --arg r1 "${RUN_RAW_EXTERNALS[0]}" --arg r2 "${RUN_RAW_EXTERNALS[1]}" --arg r3 "${RUN_RAW_EXTERNALS[2]}" \
    --arg duration "${DURATION}" \
    --argjson s1 "${FLENT_STARTS[0]}" --argjson s2 "${FLENT_STARTS[1]}" --argjson s3 "${FLENT_STARTS[2]}" \
    --argjson e1 "${FLENT_ENDS[0]}" --argjson e2 "${FLENT_ENDS[1]}" --argjson e3 "${FLENT_ENDS[2]}" \
    '{phase: 198, leg: "cake-primary", attempt_number: $n, ref_sha: $ref,
      local_bind: $bind, tests: "tcp_12down", duration_seconds: ($duration | tonumber),
      runs: [
        {run: 1, raw_path: "flent/run1.flent.gz", raw_path_external: $r1, egress_ip: $p1[0].ip, egress_org: $p1[0].org, median_mbps: ($m1|tonumber), flent_start_utc: $s1, flent_end_utc: $e1},
        {run: 2, raw_path: "flent/run2.flent.gz", raw_path_external: $r2, egress_ip: $p2[0].ip, egress_org: $p2[0].org, median_mbps: ($m2|tonumber), flent_start_utc: $s2, flent_end_utc: $e2},
        {run: 3, raw_path: "flent/run3.flent.gz", raw_path_external: $r3, egress_ip: $p3[0].ip, egress_org: $p3[0].org, median_mbps: ($m3|tonumber), flent_start_utc: $s3, flent_end_utc: $e3}
      ]}' >"${ATTEMPT_DIR}/flent/manifest.json"

jq -n --slurpfile p1 "${PROBE_FILES[0]}" --slurpfile p2 "${PROBE_FILES[1]}" --slurpfile p3 "${PROBE_FILES[2]}" \
    '{phase: 198, purpose: "Per-run source-bind egress proof; joint IP+org assertion before each flent run.", required_ip: "70.123.224.169", required_org_regex: "Charter|AS11427", pre_run_probes: [$p1[0], $p2[0], $p3[0]]}' \
    >"${ATTEMPT_DIR}/source-bind-egress-proof.json"

ATTEMPT_FAILED_STAGE="verdict"
if ! .venv/bin/python3 scripts/phase198-throughput-verdict.py \
    --manifest "${ATTEMPT_DIR}/flent/manifest.json" \
    --output "${ATTEMPT_DIR}/throughput-verdict.json"; then
    if [[ ! -f "${ATTEMPT_DIR}/throughput-verdict.json" ]]; then
        echo "ERROR: throughput verdict failed without writing its JSON artifact" >&2
        exit 1
    fi
fi

trap - ERR

THROUGHPUT_VERDICT="$(jq -r '.verdict' "${ATTEMPT_DIR}/throughput-verdict.json")"
MEDIAN_OF_MEDIANS="$(jq -r '.median_of_medians_mbps' "${ATTEMPT_DIR}/throughput-verdict.json")"
AUDIT_VERDICTS="$(jq -n \
    --slurpfile a1 "${ATTEMPT_DIR}/loaded-window-audit-run1.json" \
    --slurpfile a2 "${ATTEMPT_DIR}/loaded-window-audit-run2.json" \
    --slurpfile a3 "${ATTEMPT_DIR}/loaded-window-audit-run3.json" \
    '[$a1[0].verdict, $a2[0].verdict, $a3[0].verdict]')"
ALL_AUDITS_PASS="$(jq -n --argjson v "${AUDIT_VERDICTS}" '$v | all(. == "pass")')"

jq -n \
    --argjson n "${N}" \
    --arg attempted_at_utc "${ATTEMPTED_AT_UTC}" \
    --argjson local_hour "$((10#${LOCAL_HOUR}))" \
    --arg window "${WINDOW_USED}" \
    --arg head "${REF}" \
    --arg throughput_verdict "${THROUGHPUT_VERDICT}" \
    --argjson medians "[$(IFS=,; echo "${RUN_MEDIANS[*]}")]" \
    --argjson mom "${MEDIAN_OF_MEDIANS}" \
    --argjson audit_verdicts "${AUDIT_VERDICTS}" \
    --argjson all_audits_pass "${ALL_AUDITS_PASS}" \
    '{phase: 198, attempt_number: $n, attempted_at_utc: $attempted_at_utc,
      local_hour_at_start: $local_hour, off_peak_window_used: $window,
      head_sha: $head, phase_197_ship_sha: "068b804",
      safe05_protected_diff_empty: true,
      throughput_verdict: $throughput_verdict,
      throughput_medians_mbps: $medians,
      throughput_median_of_medians_mbps: $mom,
      per_run_audit_verdicts: $audit_verdicts,
      all_per_run_audits_pass: $all_audits_pass,
      completed_runs: 3, failed: false, decision: null}' \
    >"${ATTEMPT_DIR}/attempt-summary.json"

echo "Phase 198 rerun attempt ${N} complete."
echo "  Window used:               ${WINDOW_USED}"
echo "  Throughput:                ${THROUGHPUT_VERDICT} (medians: ${RUN_MEDIANS[0]}/${RUN_MEDIANS[1]}/${RUN_MEDIANS[2]}, MoM: ${MEDIAN_OF_MEDIANS})"
echo "  Per-run loaded-window:     $(jq -r 'join(" / ")' <<<"${AUDIT_VERDICTS}")"
echo "  Evidence:                  ${ATTEMPT_DIR}"
echo "  Next step:                 see attempt-summary.json; if throughput PASS and all per-run audits pass, run /gsd-execute-phase 198-07 to promote and close."
