#!/usr/bin/env bash
#
# Phase 191 flent capture helper.
#
# Runs the required VALN-02 test set (rrul, tcp_12down, voip) from the dev
# machine against the Dallas netperf server and stores plots, raw .flent.gz
# data, and plain-text summaries in a structured directory.
#
# Examples:
#   scripts/phase191-flent-capture.sh \
#     --label baseline_v1.38 \
#     --wan att \
#     --local-bind 10.10.110.233 \
#     --ref v1.38
#
#   scripts/phase191-flent-capture.sh \
#     --label p191_head \
#     --wan att \
#     --local-bind 10.10.110.233 \
#     --ref "$(git rev-parse --short HEAD)"
#
set -euo pipefail

usage() {
    cat <<'EOF'
Usage:
  scripts/phase191-flent-capture.sh --label <name> --wan <att|spectrum> --local-bind <ip> [options]

Required:
  --label <name>         Capture label, e.g. baseline_v1.38 or p191_head
  --wan <name>           WAN identifier used in filenames
  --local-bind <ip>      Source IP to bind flent traffic to

Optional:
  --ref <ref>            Git/tag/descriptor for the capture (recorded in manifest)
  --host <name>          Netperf/flent server host (default: dallas)
  --duration <seconds>   flent duration (default: 60)
  --output-dir <path>    Root output dir (default: ~/flent-results/phase191)
  --tests <csv>          Comma-separated tests (default: rrul,tcp_12down,voip)

This script must be run from the dev machine. It does not deploy or roll back
production code; it only runs flent and records local artifacts.
EOF
}

LABEL=""
WAN=""
LOCAL_BIND=""
REF=""
HOST="dallas"
DURATION="60"
OUTPUT_ROOT="${HOME}/flent-results/phase191"
TESTS_CSV="rrul,tcp_12down,voip"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --label)
            LABEL="${2:-}"
            shift 2
            ;;
        --wan)
            WAN="${2:-}"
            shift 2
            ;;
        --local-bind)
            LOCAL_BIND="${2:-}"
            shift 2
            ;;
        --ref)
            REF="${2:-}"
            shift 2
            ;;
        --host)
            HOST="${2:-}"
            shift 2
            ;;
        --duration)
            DURATION="${2:-}"
            shift 2
            ;;
        --output-dir)
            OUTPUT_ROOT="${2:-}"
            shift 2
            ;;
        --tests)
            TESTS_CSV="${2:-}"
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

if [[ -z "$LABEL" || -z "$WAN" || -z "$LOCAL_BIND" ]]; then
    usage >&2
    exit 2
fi

if ! command -v flent >/dev/null 2>&1; then
    echo "ERROR: flent not found in PATH" >&2
    exit 1
fi

if ! command -v netperf >/dev/null 2>&1; then
    echo "ERROR: netperf not found in PATH" >&2
    exit 1
fi

if ! ping -c 1 "$HOST" >/dev/null 2>&1; then
    echo "ERROR: cannot reach host '$HOST' with ping" >&2
    exit 1
fi

if ! ip addr show | grep -F " ${LOCAL_BIND}/" >/dev/null 2>&1; then
    echo "ERROR: local-bind IP '${LOCAL_BIND}' is not configured on this machine" >&2
    exit 1
fi

TIMESTAMP="$(date '+%Y%m%d-%H%M%S')"
CAPTURE_DIR="${OUTPUT_ROOT}/${LABEL}/${WAN}/${TIMESTAMP}"
mkdir -p "${CAPTURE_DIR}"

IFS=',' read -r -a TESTS <<<"${TESTS_CSV}"

MANIFEST="${CAPTURE_DIR}/manifest.txt"
{
    echo "label=${LABEL}"
    echo "wan=${WAN}"
    echo "local_bind=${LOCAL_BIND}"
    echo "host=${HOST}"
    echo "duration=${DURATION}"
    echo "ref=${REF}"
    echo "timestamp=${TIMESTAMP}"
    echo "capture_dir=${CAPTURE_DIR}"
} >"${MANIFEST}"

echo "Capture directory: ${CAPTURE_DIR}"
echo "Manifest: ${MANIFEST}"

for TEST_NAME in "${TESTS[@]}"; do
    TEST_NAME="${TEST_NAME// /}"
    TITLE="${LABEL}-${WAN}-${TEST_NAME}"
    PLOT_FILE="${CAPTURE_DIR}/${TITLE}.png"
    SUMMARY_FILE="${CAPTURE_DIR}/${TITLE}.summary.txt"

    BEFORE_SNAPSHOT="$(mktemp)"
    find "${CAPTURE_DIR}" -maxdepth 1 -type f -name '*.flent.gz' -printf '%f\n' | sort >"${BEFORE_SNAPSHOT}"

    echo
    echo "=== Running ${TEST_NAME} (${TITLE}) ==="
    flent "${TEST_NAME}" \
        --local-bind "${LOCAL_BIND}" \
        -H "${HOST}" \
        -l "${DURATION}" \
        -t "${TITLE}" \
        -D "${CAPTURE_DIR}" \
        -o "${PLOT_FILE}" | tee "${SUMMARY_FILE}"

    AFTER_SNAPSHOT="$(mktemp)"
    find "${CAPTURE_DIR}" -maxdepth 1 -type f -name '*.flent.gz' -printf '%f\n' | sort >"${AFTER_SNAPSHOT}"
    NEW_FILES="$(comm -13 "${BEFORE_SNAPSHOT}" "${AFTER_SNAPSHOT}" || true)"
    rm -f "${BEFORE_SNAPSHOT}" "${AFTER_SNAPSHOT}"

    RAW_FILE=""
    if [[ -n "${NEW_FILES}" ]]; then
        RAW_FILE="$(echo "${NEW_FILES}" | tail -n 1)"
    else
        RAW_FILE="$(find "${CAPTURE_DIR}" -maxdepth 1 -type f -name '*.flent.gz' -printf '%T@ %f\n' \
            | sort -n | tail -n 1 | awk '{print $2}')"
    fi

    if [[ -n "${RAW_FILE}" ]]; then
        echo "${TEST_NAME}_raw=${CAPTURE_DIR}/${RAW_FILE}" >>"${MANIFEST}"
        echo "${TEST_NAME}_plot=${PLOT_FILE}" >>"${MANIFEST}"
        echo "${TEST_NAME}_summary=${SUMMARY_FILE}" >>"${MANIFEST}"
        echo "Saved raw data: ${CAPTURE_DIR}/${RAW_FILE}"
    else
        echo "WARNING: no .flent.gz data file detected for ${TEST_NAME}" >&2
    fi
done

echo
echo "Capture complete."
echo "Artifacts recorded in ${MANIFEST}"
