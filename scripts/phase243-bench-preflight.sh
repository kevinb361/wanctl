#!/usr/bin/env bash
# Phase 243 fail-closed bench isolation preflight.

set -euo pipefail

usage() {
  cat >&2 <<'USAGE'
usage: scripts/phase243-bench-preflight.sh CONFIG WAN POSTURE [EVIDENCE_DIR]

  CONFIG       bench YAML emitted by configs/bench/gen-bench-configs.sh
  WAN          spectrum|att
  POSTURE      throwaway-interface|maintenance-window
  EVIDENCE_DIR output dir for isolation proof JSON and qdisc snapshots
USAGE
}

abort() {
  local msg="$1"
  mkdir -p "$EVIDENCE_DIR"
  printf 'phase243-bench-preflight: ABORT — %s\n' "$msg" >&2
  write_proof "false" "$msg" || true
  exit 2
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
  tc qdisc show dev "$iface" 2>/dev/null | python3 - "$iface" <<'PY'
import re
import sys

iface = sys.argv[1]
for raw in sys.stdin:
    line = raw.strip()
    if not line:
        continue
    # Keep ownership/topology only: qdisc kind, handle, root/parent, dev attachment.
    kind_match = re.search(r"^qdisc\s+(\S+)", line)
    handle_match = re.search(r"\s(\S+:)\s", line)
    parent_match = re.search(r"\s(parent\s+\S+|root)\b", line)
    print(" ".join(part for part in [
        f"dev={iface}",
        f"kind={kind_match.group(1)}" if kind_match else "kind=unknown",
        f"handle={handle_match.group(1)}" if handle_match else "handle=none",
        parent_match.group(1).replace(" ", "=") if parent_match else "attach=unknown",
    ] if part))
PY
}

write_proof() {
  local passed="$1" reason="${2:-}"
  local proof_path="${EVIDENCE_DIR}/phase243-${WAN}-${BACKEND}-isolation-proof.json"
  python3 - "$proof_path" <<PY
import json
import pathlib

payload = {
    "passed": ${passed},
    "reason": ${reason@Q},
    "posture": ${POSTURE@Q},
    "wan": ${WAN@Q},
    "backend": ${BACKEND@Q},
    "bench_config": ${CONFIG@Q},
    "bench_interfaces": [${BENCH_DL@Q}, ${BENCH_UL@Q}],
    "live_interfaces": ${LIVE_IFACES_JSON},
    "live_unit_states": ${UNIT_STATES_JSON},
    "health_port": ${HEALTH_PORT@Q},
    "metrics_port": ${METRICS_PORT@Q},
    "lock_file": ${LOCK_FILE@Q},
    "state_file": ${STATE_FILE@Q},
    "qdisc_snapshot_files": ${SNAPSHOT_FILES_JSON},
}
path = pathlib.Path(${proof_path@Q})
path.parent.mkdir(parents=True, exist_ok=True)
path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY
}

if [ "$#" -lt 3 ] || [ "$#" -gt 4 ]; then
  usage
  exit 2
fi

CONFIG="$1"
WAN="$2"
POSTURE="$3"
EVIDENCE_DIR="${4:-.planning/phases/243-cycle-budget-benchmark-gate/evidence}"

[ -f "$CONFIG" ] || { echo "ERROR: config not found: $CONFIG" >&2; exit 2; }
case "$WAN" in spectrum|att) ;; *) echo "ERROR: WAN must be spectrum|att" >&2; exit 2 ;; esac
case "$POSTURE" in throwaway-interface|maintenance-window) ;; *) echo "ERROR: invalid posture: $POSTURE" >&2; exit 2 ;; esac

mkdir -p "$EVIDENCE_DIR"

BENCH_DL=$(yaml_get cake_params.download_interface)
BENCH_UL=$(yaml_get cake_params.upload_interface)
BACKEND=$(yaml_get measurement.backend)
TRANSPORT=$(yaml_get router.transport)
HEALTH_PORT=$(yaml_get health_check.port)
METRICS_PORT=$(yaml_get metrics.port)
LOCK_FILE=$(yaml_get lock_file)
STATE_FILE=$(yaml_get state_file)

case "$WAN" in
  spectrum) LIVE_IFACES=(spec-router spec-modem) ;;
  att) LIVE_IFACES=(ens28 ens27) ;;
esac
LIVE_IFACES_JSON=$(python3 - "${LIVE_IFACES[@]}" <<'PY'
import json
import sys

print(json.dumps(sys.argv[1:]))
PY
)
UNIT_STATES_JSON='{}'
SNAPSHOT_FILES_JSON='[]'

[[ "$BENCH_DL" == bench-* && "$BENCH_UL" == bench-* ]] || abort "bench interfaces must be throwaway bench-* names"
for live_iface in "${LIVE_IFACES[@]}"; do
  if [ "$BENCH_DL" = "$live_iface" ] || [ "$BENCH_UL" = "$live_iface" ]; then
    abort "bench interface collides with live shaping interface ${live_iface}"
  fi
done

[ "$TRANSPORT" = "linux-cake" ] || abort "bench router.transport must be linux-cake, not ${TRANSPORT}"
[ "$HEALTH_PORT" != "9101" ] || abort "bench health port must not be live 9101"
[ "$METRICS_PORT" != "9100" ] || abort "bench metrics port must not be live 9100"
[[ "$LOCK_FILE" == *bench* && "$STATE_FILE" == *bench* ]] || abort "bench lock/state paths must contain bench marker"
[ ! -e "$LOCK_FILE" ] || abort "bench lock already exists: ${LOCK_FILE}"
[ ! -e "$STATE_FILE" ] || abort "bench state file already exists: ${STATE_FILE}"

if ss -ltnp 2>/dev/null | awk '{print $4}' | grep -Eq ":(${HEALTH_PORT}|${METRICS_PORT})$"; then
  abort "bench health/metrics port already listening"
fi

declare -A UNIT_STATES=()
for unit in \
  cake-autorate-spectrum.service \
  cake-autorate-att.service \
  cake-autorate-spectrum-state-bridge.service \
  cake-autorate-att-state-bridge.service \
  steering.service; do
  UNIT_STATES["$unit"]=$(systemctl is-active "$unit" 2>/dev/null || true)
done
UNIT_STATES_JSON=$(python3 - <<PY
import json
print(json.dumps({
$(for unit in "${!UNIT_STATES[@]}"; do printf '%s: %s,\n' "${unit@Q}" "${UNIT_STATES[$unit]@Q}"; done)
}, sort_keys=True))
PY
)

if [ "$POSTURE" = "maintenance-window" ]; then
  for unit in cake-autorate-spectrum.service cake-autorate-att.service; do
    if [ "${UNIT_STATES[$unit]}" = "active" ]; then
      abort "maintenance-window posture requires inactive live shaper unit: ${unit}"
    fi
  done
fi

SNAPSHOT_FILES=()
for live_iface in "${LIVE_IFACES[@]}"; do
  snapshot="${EVIDENCE_DIR}/phase243-${WAN}-${live_iface}-qdisc-stable-before.txt"
  stable_qdisc_snapshot "$live_iface" >"$snapshot"
  SNAPSHOT_FILES+=("$snapshot")
done
SNAPSHOT_FILES_JSON=$(python3 - "${SNAPSHOT_FILES[@]}" <<'PY'
import json
import sys

print(json.dumps(sys.argv[1:]))
PY
)

write_proof "true" ""
printf 'phase243-bench-preflight: PASS — %s %s posture=%s\n' "$WAN" "$BACKEND" "$POSTURE" >&2
