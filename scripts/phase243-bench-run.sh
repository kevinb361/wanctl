#!/usr/bin/env bash
# Phase 243 per-arm benchmark launcher.

set -euo pipefail
PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin

usage() {
  cat >&2 <<'USAGE'
usage: scripts/phase243-bench-run.sh WAN BACKEND LOAD DURATION_SEC CONFIG POSTURE [EVIDENCE_DIR]

  WAN          spectrum|att
  BACKEND      icmplib|fping
  LOAD         idle|load
  DURATION_SEC arm window, minimum enforced by operator runbook
  CONFIG       bench YAML emitted by configs/bench/gen-bench-configs.sh
  POSTURE      throwaway-interface|maintenance-window
  EVIDENCE_DIR evidence output directory
USAGE
}

yaml_get() {
  local path="$1"
  python3 - "$CONFIG" "$path" <<'PY'
import sys
import yaml

config_path, dotted = sys.argv[1:]
with open(config_path, encoding="utf-8") as fh:
    data = yaml.safe_load(fh) or {}
node = data
for part in dotted.split("."):
    if not isinstance(node, dict) or part not in node:
        raise SystemExit(3)
    node = node[part]
print(node)
PY
}

stable_qdisc_snapshot() {
  local iface="$1"
  tc qdisc show dev "$iface" 2>/dev/null | python3 -c 'import re, sys
iface = sys.argv[1]
for raw in sys.stdin:
    line = raw.strip()
    if not line:
        continue
    kind_match = re.search(r"^qdisc\s+(\S+)", line)
    handle_match = re.search(r"\s(\S+:)\s", line)
    parent_match = re.search(r"\s(parent\s+\S+|root)\b", line)
    print(" ".join(part for part in [
        f"dev={iface}",
        f"kind={kind_match.group(1)}" if kind_match else "kind=unknown",
        f"handle={handle_match.group(1)}" if handle_match else "handle=none",
        parent_match.group(1).replace(" ", "=") if parent_match else "attach=unknown",
    ] if part))' "$iface"
}

residue_check() {
  local status=0
  if [ -n "${UNIT:-}" ]; then
    systemctl stop "$UNIT" >/dev/null 2>&1 || true
  fi
  if [ -n "${HYGIENE_PID:-}" ]; then
    wait "$HYGIENE_PID" >/dev/null 2>&1 || true
  fi

  for live_iface in "${LIVE_IFACES[@]:-}"; do
    local before="${EVIDENCE_DIR}/phase243-${WAN}-${live_iface}-qdisc-stable-before.txt"
    local after="${ARM_DIR}/${live_iface}-qdisc-stable-after.txt"
    stable_qdisc_snapshot "$live_iface" >"$after"
    if [ -f "$before" ] && ! diff -u "$before" "$after" >"${ARM_DIR}/${live_iface}-qdisc-stable.diff"; then
      printf 'phase243-bench-run: residue check failed: live qdisc ownership changed for %s\n' "$live_iface" >&2
      status=1
    fi
  done

  if [ -n "${LOCK_FILE:-}" ] && [ -e "$LOCK_FILE" ]; then
    printf 'phase243-bench-run: residue check failed: lock remains: %s\n' "$LOCK_FILE" >&2
    status=1
  fi
  if [ -n "${UNIT:-}" ] && systemctl is-active --quiet "$UNIT" 2>/dev/null; then
    printf 'phase243-bench-run: residue check failed: unit remains active: %s\n' "$UNIT" >&2
    status=1
  fi
  return "$status"
}

verify_journal_invocation() {
  local journal_json="$1" verified_ndjson="$2" invocation="$3"
  journalctl _SYSTEMD_INVOCATION_ID="$invocation" -o json --no-pager >"$journal_json"
  python3 - "$journal_json" "$verified_ndjson" "$invocation" <<'PY'
import json
import sys
from pathlib import Path

journal_path, output_path, invocation = sys.argv[1:]
records = 0
with open(journal_path, encoding="utf-8") as src, open(output_path, "w", encoding="utf-8") as dst:
    for line_no, line in enumerate(src, start=1):
        if not line.strip():
            continue
        record = json.loads(line)
        if record.get("_SYSTEMD_INVOCATION_ID") != invocation:
            raise SystemExit(f"journal invocation mismatch at line {line_no}")
        message = record.get("MESSAGE")
        if isinstance(message, str):
            dst.write(message + "\n")
        records += 1
if records == 0:
    raise SystemExit("no invocation-scoped journal records captured")
Path(output_path).touch(exist_ok=True)
PY
}

merge_cpu_evidence() {
  python3 - "$PROFILE_JSON" "$MERGED_PROFILE_JSON" "$CPU_START" "$CPU_END" "$WINDOW_WALL_SEC" "$N_CORES" "$INVOCATION" <<'PY'
import json
import sys

profile_path, output_path, start, end, wall, cores, invocation = sys.argv[1:]
with open(profile_path, encoding="utf-8") as fh:
    profile = json.load(fh)
start_i = int(start)
end_i = int(end)
profile.update({
    "cpu_nsec_start": start_i,
    "cpu_nsec_end": end_i,
    "cpu_nsec_delta": end_i - start_i,
    "window_wall_sec": float(wall),
    "n_cores": int(cores),
    "invocation_id": invocation,
})
with open(output_path, "w", encoding="utf-8") as fh:
    json.dump(profile, fh, indent=2, sort_keys=True)
    fh.write("\n")
PY
}

if [ "$#" -lt 6 ] || [ "$#" -gt 7 ]; then
  usage
  exit 2
fi

WAN="$1"
BACKEND="$2"
LOAD="$3"
DURATION_SEC="$4"
CONFIG=$(realpath "$5")
POSTURE="$6"
EVIDENCE_DIR="${7:-.planning/phases/243-cycle-budget-benchmark-gate/evidence}"
CODE_DIR="${WANCTL_BENCH_CODE_DIR:-/opt/wanctl}"
CODE_PARENT=$(dirname "$CODE_DIR")

case "$WAN" in spectrum|att) ;; *) echo "ERROR: WAN must be spectrum|att" >&2; exit 2 ;; esac
case "$BACKEND" in icmplib|fping) ;; *) echo "ERROR: BACKEND must be icmplib|fping" >&2; exit 2 ;; esac
case "$LOAD" in idle|load) ;; *) echo "ERROR: LOAD must be idle|load" >&2; exit 2 ;; esac
[[ "$DURATION_SEC" =~ ^[1-9][0-9]*$ ]] || { echo "ERROR: DURATION_SEC must be positive integer" >&2; exit 2; }

scripts/phase243-bench-preflight.sh "$CONFIG" "$WAN" "$POSTURE" "$EVIDENCE_DIR"

RUN_TS=$(date +%s)
UNIT="wanctl-bench-${WAN}-${BACKEND}-${LOAD}-${RUN_TS}"
ARM="${WAN}-${BACKEND}-${LOAD}-${RUN_TS}"
ARM_DIR="${EVIDENCE_DIR}/${ARM}"
mkdir -p "$ARM_DIR"
LOCK_FILE=$(yaml_get lock_file)
SOURCE_IP=$(yaml_get ping_source_ip || true)
if [ -f "/etc/wanctl/${WAN}.yaml" ]; then
  LIVE_CONFIG_READER=(python3)
  if [ ! -r "/etc/wanctl/${WAN}.yaml" ]; then
    sudo -n test -r "/etc/wanctl/${WAN}.yaml" 2>/dev/null || LIVE_CONFIG_READER=()
    if [ "${#LIVE_CONFIG_READER[@]}" -gt 0 ]; then
      LIVE_CONFIG_READER=(sudo -n python3)
    fi
  fi
  if [ "${#LIVE_CONFIG_READER[@]}" -gt 0 ]; then
    mapfile -t LIVE_IFACES < <("${LIVE_CONFIG_READER[@]}" - "/etc/wanctl/${WAN}.yaml" <<'PY'
import sys
import yaml

with open(sys.argv[1], encoding="utf-8") as fh:
    data = yaml.safe_load(fh) or {}
cake = data.get("cake_params") or {}
for key in ("download_interface", "upload_interface"):
    value = cake.get(key)
    if value:
        print(value)
PY
)
  else
    LIVE_IFACES=()
  fi
else
  LIVE_IFACES=()
fi
if [ "${#LIVE_IFACES[@]}" -eq 0 ]; then
  LIVE_ROUTE_DEV=$(python3 -c 'import sys
tokens = sys.stdin.read().split()
dev = None
for idx, token in enumerate(tokens):
    if token == "dev" and idx + 1 < len(tokens):
        dev = tokens[idx + 1]
        break
if dev:
    print(dev)
    raise SystemExit(0)
raise SystemExit(1)' < <(ip route get 104.200.21.31 from "$SOURCE_IP" 2>/dev/null)) \
    || { echo "ERROR: cannot resolve route dev for source IP ${SOURCE_IP}" >&2; exit 2; }
  LIVE_IFACES=("$LIVE_ROUTE_DEV")
fi

HYGIENE_PID=""
trap 'residue_check' EXIT INT TERM

sudo systemd-run \
  --unit="$UNIT" \
  --collect \
  --property=CPUAccounting=yes \
  --property="AmbientCapabilities=CAP_NET_RAW CAP_NET_ADMIN" \
  --property="CapabilityBoundingSet=CAP_NET_RAW CAP_NET_ADMIN" \
  --property="RuntimeMaxSec=${DURATION_SEC}" \
  --uid=wanctl \
  --working-directory="$CODE_DIR" \
  --setenv=WANCTL_LOG_FORMAT=json \
  --setenv=PYTHONPATH="$CODE_PARENT" \
  /usr/bin/python3 "$CODE_DIR/autorate_continuous.py" \
    --debug --config "$CONFIG"

INVOCATION=$(systemctl show -p InvocationID --value "$UNIT")
[ -n "$INVOCATION" ] || { echo "ERROR: InvocationID not captured" >&2; exit 2; }

for _ in $(seq 1 30); do
  MAIN_PID=$(systemctl show -p MainPID --value "$UNIT" 2>/dev/null || true)
  if [[ "$MAIN_PID" =~ ^[1-9][0-9]*$ ]]; then
    break
  fi
  sleep 1
done
[[ "${MAIN_PID:-0}" =~ ^[1-9][0-9]*$ ]] || { echo "ERROR: unit MainPID did not become live" >&2; exit 2; }

CPU_START=$(systemctl show -p CPUUsageNSec --value "$UNIT")
WINDOW_START_EPOCH=$(date +%s)

BENCH_UNIT="$UNIT" SOAK_DURATION_SEC="$DURATION_SEC" CAPTURE_DIR="$ARM_DIR" \
  scripts/phase243-hygiene-sampler.sh &
HYGIENE_PID=$!

if [ "$LOAD" = "load" ]; then
  FLENT_DIR="${ARM_DIR}/flent"
  mkdir -p "$FLENT_DIR"
  flent_args=(rrul -H 104.200.21.31 -l "$DURATION_SEC" -D "$FLENT_DIR")
  if [ -n "$SOURCE_IP" ]; then
    flent_args+=(--test-parameter "local_bind=${SOURCE_IP}")
  fi
  flent "${flent_args[@]}"
else
  sleep "$DURATION_SEC"
fi

CPU_END=$(systemctl show -p CPUUsageNSec --value "$UNIT")
WINDOW_END_EPOCH=$(date +%s)
WINDOW_WALL_SEC=$((WINDOW_END_EPOCH - WINDOW_START_EPOCH))
N_CORES=$(getconf _NPROCESSORS_ONLN)

systemctl stop "$UNIT" >/dev/null 2>&1 || true
wait "$HYGIENE_PID" >/dev/null 2>&1 || true

JOURNAL_JSON="${ARM_DIR}/journal.jsonl"
VERIFIED_NDJSON="${ARM_DIR}/cycle.ndjson"
PROFILE_JSON="${ARM_DIR}/profile.raw.json"
MERGED_PROFILE_JSON="${ARM_DIR}/profile.json"
verify_journal_invocation "$JOURNAL_JSON" "$VERIFIED_NDJSON" "$INVOCATION"
python3 scripts/phase243-cycle-rollup.py "$VERIFIED_NDJSON" --invocation-id "$INVOCATION" --output "$PROFILE_JSON"
merge_cpu_evidence

residue_check
trap - EXIT INT TERM

printf 'phase243-bench-run: PASS arm=%s profile=%s hygiene=%s invocation=%s\n' \
  "$ARM" "$MERGED_PROFILE_JSON" "${ARM_DIR}/hygiene.ndjson" "$INVOCATION" >&2
