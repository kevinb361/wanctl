#!/usr/bin/env bash
#
# Phase 213 evidence baseline harness.
#
# D-09 single-command operator entry: this orchestrator wires the Phase 213
# leaf scripts into one per-run evidence tree. D-10 mutation posture: allowed
# work is dev-VM traffic generation and read-only evidence capture only;
# forbidden work is service changes, /etc/wanctl writes, steering control
# changes, RouterOS writes, deploys, controller config changes, and profiling
# harness changes. D-11 WAN suites are serialized in --wans order and never run
# concurrently. HIGH-1 uses a per-WAN --bind-map. HIGH-3 splits offline
# --check-manifest from live --check-prereqs. HIGH-4 tracks poller PIDs and
# cleans them via trap. MEDIUM-3 normalizes phase191 flent paths into each test
# dir. MEDIUM-5 writes signal-sheet artifacts inside RUN-<ts>/.

set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  scripts/phase213-baseline-capture.sh --bind-map spectrum=<ip>,att=<ip> [options]

Options:
  --bind-map <map>          Required per-WAN source bindings, e.g. spectrum=10.10.110.226,att=10.10.110.233
  --host <name>             Netperf/flent host (default: dallas)
  --flent-duration <sec>    flent duration seconds (default: 60)
  --browse-duration <sec>   curl browse duration seconds (default: 60)
  --pre-buf <sec>           Pre-test poll/snapshot buffer seconds (default: 10)
  --post-buf <sec>          Post-test poll/snapshot buffer seconds (default: 10)
  --wans <csv>              Serialized WAN order (default: spectrum,att)
  --tests <csv>             Test order per WAN (default: browse,tcp_upload,tcp_download,rrul,tcp_12down)
  --evidence-root <dir>     Evidence root (default: .planning/phases/213-experience-baseline-harness/evidence)
  --check-manifest          OFFLINE: emit schema-valid manifest and exit; no SSH/curl
  --check-prereqs           LIVE: verify local tools, SSH/sudo, bind IPs, and egress gates
  --dry-run                 Alias for --check-prereqs
  --help, -h                Show this help
EOF
}

HOST="dallas"
FLENT_DURATION="60"
BROWSE_DURATION="60"
PRE_BUF="10"
POST_BUF="10"
WANS_CSV="spectrum,att"
TESTS_CSV="browse,tcp_upload,tcp_download,rrul,tcp_12down"
EVIDENCE_ROOT=".planning/phases/213-experience-baseline-harness/evidence"
BIND_MAP_RAW=""
MODE="real"
RUN_TS="$(date -u +%Y%m%dT%H%M%SZ)"
RUN_ID="RUN-${RUN_TS}"
RUN_DIR=""
FLENT_OUTPUT_ROOT="${HOME}/flent-results/phase213"
TESTS_JSON='[]'
declare -A BIND=()
declare -A EGRESS_OBSERVED=()
POLLER_PIDS=()

require_command() {
  local cmd="$1"
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "ERROR: required command missing: $cmd" >&2
    exit 2
  fi
}

csv_to_json() {
  python3 - "$1" <<'PY'
import json, sys
print(json.dumps([x.strip() for x in sys.argv[1].split(',') if x.strip()]))
PY
}

parse_bind_map() {
  local raw="$1" item key val
  [[ -z "$raw" ]] && return 0
  IFS=',' read -r -a items <<<"$raw"
  for item in "${items[@]}"; do
    key="${item%%=*}"
    val="${item#*=}"
    if [[ -z "$key" || -z "$val" || "$key" == "$val" ]]; then
      echo "ERROR: invalid --bind-map entry: $item" >&2
      exit 2
    fi
    BIND["$key"]="$val"
  done
}

bind_map_json() {
  python3 - "$BIND_MAP_RAW" <<'PY'
import json, sys
raw = sys.argv[1]
out = {}
for item in [x for x in raw.split(',') if x.strip()]:
    k, v = item.split('=', 1)
    out[k.strip()] = v.strip()
out.setdefault('spectrum', 'fixture')
out.setdefault('att', 'fixture')
print(json.dumps(out, sort_keys=True))
PY
}

require_bind_for_wans() {
  local wan
  for wan in ${WANS_CSV//,/ }; do
    if [[ -z "${BIND[$wan]:-}" ]]; then
      echo "ERROR: --bind-map missing bind for WAN '$wan'" >&2
      exit 2
    fi
  done
}

cleanup_pollers() {
  local pid
  for pid in "${POLLER_PIDS[@]:-}"; do
    if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
      kill "$pid" 2>/dev/null || true
      wait "$pid" 2>/dev/null || true
    fi
  done
  POLLER_PIDS=()
}

cleanup_temp() { :; }
trap 'cleanup_pollers; cleanup_temp' EXIT INT TERM

while [[ $# -gt 0 ]]; do
  case "$1" in
    --bind-map) BIND_MAP_RAW="${2:-}"; shift 2 ;;
    --host) HOST="${2:-}"; shift 2 ;;
    --flent-duration) FLENT_DURATION="${2:-}"; shift 2 ;;
    --browse-duration) BROWSE_DURATION="${2:-}"; shift 2 ;;
    --pre-buf) PRE_BUF="${2:-}"; shift 2 ;;
    --post-buf) POST_BUF="${2:-}"; shift 2 ;;
    --wans) WANS_CSV="${2:-}"; shift 2 ;;
    --tests) TESTS_CSV="${2:-}"; shift 2 ;;
    --evidence-root) EVIDENCE_ROOT="${2:-}"; shift 2 ;;
    --check-manifest) MODE="check-manifest"; shift ;;
    --check-prereqs|--dry-run) MODE="check-prereqs"; shift ;;
    --help|-h) usage; exit 0 ;;
    *) echo "Unknown argument: $1" >&2; usage >&2; exit 2 ;;
  esac
done

parse_bind_map "$BIND_MAP_RAW"

if [[ "$MODE" != "check-manifest" && -z "$BIND_MAP_RAW" ]]; then
  echo "ERROR: --bind-map is required outside --check-manifest" >&2
  exit 2
fi

if [[ "$MODE" != "check-manifest" ]]; then
  require_bind_for_wans
fi

make_manifest() {
  local out="$1" started="$2" ended="$3" source_ip="$4" tests_json="$5"
  local flent_version wanctl_version git_head host_name bm_json egress_json
  flent_version="$(flent --version 2>/dev/null | head -n 1 || true)"
  [[ -z "$flent_version" ]] && flent_version="unknown"
  wanctl_version="$(python3 - <<'PY' 2>/dev/null || true
from pathlib import Path
import re
m = re.search(r'^version\s*=\s*"([^"]+)"', Path('pyproject.toml').read_text(), re.M)
print(m.group(1) if m else 'unknown')
PY
)"
  [[ -z "$wanctl_version" ]] && wanctl_version="unknown"
  git_head="$(git rev-parse --short HEAD 2>/dev/null || echo offline)"
  host_name="$(hostname 2>/dev/null || echo unknown)"
  bm_json="$(bind_map_json)"
  egress_json="$(python3 - <<'PY'
import json, os
pairs = os.environ.get('PHASE213_EGRESS_PAIRS','')
out = {}
for pair in pairs.split(','):
    if '=' in pair:
        k,v = pair.split('=',1); out[k]=v
print(json.dumps(out))
PY
)"
  jq -n \
    --argjson phase 213 \
    --arg run_id "${RUN_ID}" \
    --arg started_utc "$started" \
    --arg ended_utc "$ended" \
    --arg host_dev_vm "$host_name" \
    --arg source_ip "$source_ip" \
    --arg netperf_host "$HOST" \
    --arg flent_version "$flent_version" \
    --arg wanctl_version_dev_repo "$wanctl_version" \
    --arg wanctl_version_spectrum_runtime "offline-fixture" \
    --arg wanctl_version_att_runtime "offline-fixture" \
    --arg wanctl_version_steering_runtime "offline-fixture" \
    --arg git_head_sha "$git_head" \
    --argjson tests_ordered "$tests_json" \
    --arg redaction_posture "D-08 key pattern (password|secret|token|credential|auth|key|private) applied to *.redacted.json artifacts" \
    --arg mutation_posture "evidence-only: dev-VM traffic generation plus read-only snapshots; no production mutation" \
    --argjson bind_map "$bm_json" \
    --argjson bind_map_egress_observed "$egress_json" \
    '{phase:$phase, run_id:$run_id, started_utc:$started_utc, ended_utc:$ended_utc,
      host_dev_vm:$host_dev_vm, source_ip:$source_ip, netperf_host:$netperf_host,
      flent_version:$flent_version, wanctl_version_dev_repo:$wanctl_version_dev_repo,
      wanctl_version_spectrum_runtime:$wanctl_version_spectrum_runtime,
      wanctl_version_att_runtime:$wanctl_version_att_runtime,
      wanctl_version_steering_runtime:$wanctl_version_steering_runtime,
      git_head_sha:$git_head_sha, tests_ordered:$tests_ordered,
      redaction_posture:$redaction_posture, mutation_posture:$mutation_posture,
      bind_map:$bind_map, bind_map_egress_observed:$bind_map_egress_observed}' >"$out"
}

case "${MODE:-real}" in
  check-manifest)
    require_command jq
    mkdir -p "${EVIDENCE_ROOT}" "${EVIDENCE_ROOT}/RUN-CHECK-MANIFEST"
    RUN_ID="RUN-CHECK-MANIFEST"
    TS="$(date -u -Iseconds)"
    TESTS_JSON="$(python3 - "$WANS_CSV" "$TESTS_CSV" <<'PY'
import json, sys
wans=[x for x in sys.argv[1].split(',') if x]
tests=[x for x in sys.argv[2].split(',') if x]
print(json.dumps([{'wan':w,'test':t,'test_start_unix':0,'test_end_unix':0} for w in wans for t in tests]))
PY
)"
    make_manifest "${EVIDENCE_ROOT}/manifest.json" "$TS" "$TS" "OFFLINE" "$TESTS_JSON"
    cp "${EVIDENCE_ROOT}/manifest.json" "${EVIDENCE_ROOT}/RUN-CHECK-MANIFEST/manifest.json"
    cat >"${EVIDENCE_ROOT}/RUN-CHECK-MANIFEST/README.md" <<'EOF'
# Phase 213 Check Manifest

Offline schema fixture emitted by --check-manifest. No production access occurs in this mode.
EOF
    echo "CHECK_MANIFEST OK"
    exit 0
    ;;
  check-prereqs)
    require_command flent; require_command jq; require_command curl; require_command ssh
    require_bind_for_wans
    ssh -o BatchMode=yes cake-shaper 'true' || { echo "cake-shaper unreachable" >&2; exit 1; }
    ssh -o BatchMode=yes cake-shaper 'sudo -n true' || { echo "sudo -n unavailable on cake-shaper" >&2; exit 1; }
    for WAN in ${WANS_CSV//,/ }; do
      bind="${BIND[$WAN]}"
      ip -4 addr show | grep -qF " ${bind}/" || { echo "bind $bind for WAN $WAN missing on dev VM" >&2; exit 1; }
      egress="$(curl -s --interface "$bind" --max-time 5 https://ifconfig.io || echo unknown)"
      if [[ "$WAN" == "spectrum" && "$egress" != "70.123.224.169" ]]; then
        echo "REFUSED: spectrum egress via bind=$bind is $egress (expected 70.123.224.169)" >&2
        exit 1
      fi
      echo "WAN=$WAN bind=$bind egress=$egress OK"
    done
    echo "CHECK_PREREQS OK"
    exit 0
    ;;
  real) ;;
  *) echo "ERROR: unknown mode $MODE" >&2; exit 2 ;;
esac

require_command jq; require_command curl; require_command python3
require_bind_for_wans

RUN_DIR="${EVIDENCE_ROOT}/${RUN_ID}"
mkdir -p "$RUN_DIR" "$FLENT_OUTPUT_ROOT"
STARTED_UTC="$(date -u -Iseconds)"
TESTS_JSON='[]'

append_command_log() {
  printf '%s\t%s\n' "$(date -u -Iseconds)" "$*" >>"${RUN_DIR}/.command-log"
}

start_pollers() {
  local test_dir="$1"
  POLLER_PIDS=()
  bash scripts/phase213-health-poller.sh --endpoint http://10.10.110.223:9101/health --wan spectrum --output "${test_dir}/health-spectrum.ndjson" --duration 0 &
  POLLER_PIDS+=("$!")
  bash scripts/phase213-health-poller.sh --endpoint http://10.10.110.227:9101/health --wan att --output "${test_dir}/health-att.ndjson" --duration 0 &
  POLLER_PIDS+=("$!")
}

normalize_flent() {
  local wan="$1" test="$2" test_dir="$3" label="$4" actual
  actual="$(find "${FLENT_OUTPUT_ROOT}/${label}/${wan}" -mindepth 1 -maxdepth 1 -type d -printf '%T@ %p\n' 2>/dev/null | sort -n | tail -n 1 | cut -d' ' -f2- || true)"
  [[ -z "$actual" ]] && { echo "ERROR: no phase191 flent dir under ${FLENT_OUTPUT_ROOT}/${label}/${wan}" >&2; return 1; }
  rm -f "${test_dir}/flent"
  ln -s "$actual" "${test_dir}/flent"
  append_command_log "normalized flent ${wan}/${test} -> ${actual}"
}

append_test_entry() {
  local wan="$1" test="$2" start="$3" end="$4" tmp
  tmp="$(mktemp)"
  jq --arg wan "$wan" --arg test "$test" --argjson s "$start" --argjson e "$end" \
    '. + [{wan:$wan,test:$test,test_start_unix:$s,test_end_unix:$e}]' <<<"$TESTS_JSON" >"$tmp"
  TESTS_JSON="$(cat "$tmp")"
  rm -f "$tmp"
}

run_bracketed_test() {
  local wan="$1" test="$2" bind test_dir label t_start t_end
  bind="${BIND[$wan]}"
  test_dir="${RUN_DIR}/${wan}/${test}"
  mkdir -p "$test_dir"
  bash scripts/phase213-steering-snapshot.sh --output "${test_dir}/steering-pre"
  append_command_log "phase213-steering-snapshot pre ${wan}/${test}"
  start_pollers "$test_dir"
  sleep "$PRE_BUF"
  t_start="$(date -u +%s)"
  if [[ "$test" == "browse" ]]; then
    append_command_log "phase213-browse-loop --local-bind ${bind} --duration ${BROWSE_DURATION}"
    bash scripts/phase213-browse-loop.sh --output "${test_dir}/browse.curl.csv" --duration "$BROWSE_DURATION" --local-bind "$bind"
  else
    label="phase213-${RUN_TS}-${test}"
    append_command_log "phase191-flent-capture --tests ${test} --wan ${wan} --local-bind ${bind}"
    bash scripts/phase191-flent-capture.sh --tests "$test" --label "$label" --wan "$wan" --local-bind "$bind" --host "$HOST" --duration "$FLENT_DURATION" --output-dir "$FLENT_OUTPUT_ROOT" --ref "$(git rev-parse --short HEAD 2>/dev/null || echo unknown)"
    normalize_flent "$wan" "$test" "$test_dir" "$label"
  fi
  t_end="$(date -u +%s)"
  sleep "$POST_BUF"
  cleanup_pollers
  bash scripts/phase213-steering-snapshot.sh --output "${test_dir}/steering-post"
  append_command_log "phase213-steering-snapshot post ${wan}/${test}"
  bash scripts/phase213-alert-window.sh --start "$((t_start - PRE_BUF))" --end "$((t_end + POST_BUF))" --output-dir "$test_dir"
  append_command_log "phase213-alert-window ${wan}/${test}"
  jq -n --arg wan "$wan" --arg test "$test" --argjson s "$t_start" --argjson e "$t_end" --argjson pre "$PRE_BUF" --argjson post "$POST_BUF" \
    '{wan:$wan,test:$test,test_start_unix:$s,test_end_unix:$e,pre_buf_sec:$pre,post_buf_sec:$post}' >"${test_dir}/manifest.json"
  append_test_entry "$wan" "$test" "$t_start" "$t_end"
}

for WAN in ${WANS_CSV//,/ }; do
  bind="${BIND[$WAN]}"
  egress="$(curl -s --interface "$bind" --max-time 5 https://ifconfig.io || echo unknown)"
  EGRESS_OBSERVED[$WAN]="$egress"
  if [[ "$WAN" == "spectrum" && "$egress" != "70.123.224.169" ]]; then
    echo "REFUSED: spectrum egress signature mismatch via bind=$bind (got $egress, expected 70.123.224.169)" >&2
    exit 1
  fi
  for TEST in ${TESTS_CSV//,/ }; do
    run_bracketed_test "$WAN" "$TEST"
    sleep 5
  done
done

EGRESS_PAIRS=()
for WAN in ${!EGRESS_OBSERVED[@]}; do EGRESS_PAIRS+=("${WAN}=${EGRESS_OBSERVED[$WAN]}"); done
PHASE213_EGRESS_PAIRS="$(IFS=,; echo "${EGRESS_PAIRS[*]:-}")" export PHASE213_EGRESS_PAIRS
ENDED_UTC="$(date -u -Iseconds)"
make_manifest "${RUN_DIR}/manifest.json" "$STARTED_UTC" "$ENDED_UTC" "${BIND[spectrum]:-${BIND[att]:-unknown}}" "$TESTS_JSON"
.venv/bin/python3 scripts/phase213-classify.py --run-dir "$RUN_DIR" --output-json "${RUN_DIR}/signal-sheet.json" --output-md "${RUN_DIR}/signal-sheet.md"
echo "Phase 213 baseline capture complete: ${RUN_DIR}"
