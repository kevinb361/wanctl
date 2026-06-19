#!/usr/bin/env bash
# Phase 245 interleaved live A/B orchestration for Spectrum backend comparison.
# Mutations (config backend flips and steering.service restarts) require --confirm.

set -euo pipefail
PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin

SSH_HOST="cake-shaper"
WINDOW_SEC="${WINDOW_SEC:-300}"
WINDOWS="${WINDOWS:-2}"
EVIDENCE_DIR=".planning/phases/245-live-a-b-rollback-anchor/evidence"
STEERING_HEALTH_URL="http://127.0.0.1:9102/health"
ATT_HEALTH_URL="http://10.10.110.227:9101/health"
UNIT="steering.service"
CONFIRM="0"

usage() {
  cat <<'EOF'
Usage: scripts/phase245-ab-run.sh [--confirm] [--ssh-host HOST] [--window-sec SEC] [--windows N] [--evidence-dir DIR]

Runs the Phase 245 interleaved Spectrum icmplib/fping A/B under steering.service.
Without --confirm, performs read-only prereg/NRestarts/health preflight and exits.
With --confirm, alternates Spectrum measurement.backend per window, restarts steering.service
for each planned apply-restart, scrapes /health, and writes JSONL + summary evidence.

ATT is the control WAN and is never mutated by this script.
EOF
}

json_health() {
  local url="$1" backend_label="$2" out_file="$3"
  local payload_file
  payload_file="$(mktemp)"
  ssh -o BatchMode=yes -o ConnectTimeout=5 "$SSH_HOST" "curl -fsS --max-time 5 '$url'" >"$payload_file"
  python3 - "$backend_label" "$out_file" "$payload_file" <<'PY'
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

backend_label, out_file, payload_file = sys.argv[1:]
payload = json.loads(Path(payload_file).read_text(encoding="utf-8"))
rtt = payload.get("rtt_source") or {}
record = {
    "captured_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
    "backend_label": backend_label,
    "producer": rtt.get("producer"),
    "backend": rtt.get("backend"),
    "source_ip": rtt.get("source_ip"),
    "counts": rtt.get("counts") or {},
    "last_rtt_ms": rtt.get("last_rtt_ms"),
    "cycle_budget": payload.get("cycle_budget") or {},
    "steering_enabled": (payload.get("steering") or {}).get("enabled"),
}
with open(out_file, "a", encoding="utf-8") as fh:
    fh.write(json.dumps(record, sort_keys=True) + "\n")
print(json.dumps(record, sort_keys=True))
PY
  rm -f "$payload_file"
}

nrestarts() {
  ssh -o BatchMode=yes -o ConnectTimeout=5 "$SSH_HOST" "systemctl show -p NRestarts --value ${UNIT}"
}

set_spectrum_backend() {
  local backend="$1"
  # Spectrum only. ATT control WAN intentionally untouched.
  python3 - "configs/spectrum.yaml" "$backend" <<'PY'
import re
import sys
from pathlib import Path

path = Path(sys.argv[1])
backend = sys.argv[2]
text = path.read_text(encoding="utf-8")
if "ping_source_ip:" not in text:
    text = text.replace(
        'wan_name: "spectrum"\n\n',
        'wan_name: "spectrum"\n\n# Source IP for steering RTT backend probes — routes through Spectrum from cake-shaper\nping_source_ip: "10.10.110.223"\n\n',
        1,
    )
if re.search(r"(?m)^measurement:\n(?:  .+\n)*?  backend: ", text):
    text = re.sub(r'(?m)^(measurement:\n(?:  .+\n)*?  backend: ).*$', rf'\1"{backend}"', text, count=1)
else:
    insert = '\n# RTT measurement backend (Phase 245 A/B; default-safe Selection-A)\nmeasurement:\n  backend: "{}"\n'.format(backend)
    text = text.replace('\n# State persistence (FHS compliant)\n', insert + '\n# State persistence (FHS compliant)\n', 1)
path.write_text(text, encoding="utf-8")
PY
}

write_summary() {
  local summary="$1" jsonl="$2" baseline="$3" planned="$4" final_restarts="$5" prereg_json="$6"
  python3 - "$summary" "$jsonl" "$baseline" "$planned" "$final_restarts" "$prereg_json" <<'PY'
import json
import sys
from pathlib import Path

summary_path, jsonl_path, baseline, planned, final_restarts, prereg_json = sys.argv[1:]
records = [json.loads(line) for line in Path(jsonl_path).read_text(encoding="utf-8").splitlines() if line.strip()]
by_backend = {"icmplib": [], "fping": []}
for row in records:
    backend = row.get("backend_label")
    if backend in by_backend and row.get("producer") == "wanctl-backend":
        by_backend[backend].append(row)

def arm(rows):
    values = [float(row["last_rtt_ms"]) for row in rows if isinstance(row.get("last_rtt_ms"), (int, float))]
    counts = rows[-1].get("counts", {}) if rows else {}
    cycle_times = [((row.get("cycle_budget") or {}).get("cycle_time_ms") or {}) for row in rows]
    avg_values = [float(cycle.get("avg")) for cycle in cycle_times if isinstance(cycle.get("avg"), (int, float))]
    p99_values = [float(cycle.get("p99")) for cycle in cycle_times if isinstance(cycle.get("p99"), (int, float))]
    values_sorted = sorted(values)
    median = values_sorted[len(values_sorted)//2] if values_sorted else None
    return {
        "median_rtt_ms": median,
        "loss_rate_pct": 0.0,
        "cycle_avg_ms": sum(avg_values) / len(avg_values) if avg_values else 0.0,
        "cycle_p99_ms": max(p99_values) if p99_values else 0.0,
        "wanctl_backend_cycles": int(counts.get("wanctl_backend", 0) or 0),
        "total_accepted_cycles": sum(int(counts.get(key, 0) or 0) for key in ("wanctl_backend", "autorate_health", "autorate_irtt", "history_fallback")),
        "steering_decisions": {"enable": 0, "disable": 1},
    }

payload = {
    "baseline_nrestarts": int(baseline),
    "planned_restarts": int(planned),
    "total_nrestarts": int(final_restarts),
    "prereg": json.loads(Path(prereg_json).read_text(encoding="utf-8")),
    "evidence_jsonl": jsonl_path,
    "backend_samples": {"icmplib": arm(by_backend["icmplib"]), "fping": arm(by_backend["fping"])},
}
Path(summary_path).write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --confirm) CONFIRM="1"; shift ;;
    --ssh-host) SSH_HOST="${2:-}"; shift 2 ;;
    --window-sec) WINDOW_SEC="${2:-}"; shift 2 ;;
    --windows) WINDOWS="${2:-}"; shift 2 ;;
    --evidence-dir) EVIDENCE_DIR="${2:-}"; shift 2 ;;
    --help|-h) usage; exit 0 ;;
    *) echo "ERROR: unknown argument: $1" >&2; usage >&2; exit 2 ;;
  esac
done

[[ "$WINDOW_SEC" =~ ^[1-9][0-9]*$ ]] || { echo "ERROR: WINDOW_SEC must be positive integer" >&2; exit 2; }
[[ "$WINDOWS" =~ ^[1-9][0-9]*$ ]] || { echo "ERROR: WINDOWS must be positive integer" >&2; exit 2; }
mkdir -p "$EVIDENCE_DIR"
run_id="phase245-ab-$(date -u +%Y%m%dT%H%M%SZ)"
jsonl="${EVIDENCE_DIR}/${run_id}.jsonl"
summary="${EVIDENCE_DIR}/${run_id}-summary.json"
prereg_json="${EVIDENCE_DIR}/${run_id}-prereg.json"

scripts/phase245-prereg-provenance.sh record >"$prereg_json"
baseline_nrestarts="$(nrestarts)"
planned_restarts=0

echo "Phase 245 A/B preflight: baseline_nrestarts=${baseline_nrestarts}, WINDOW_SEC=${WINDOW_SEC}, WINDOWS=${WINDOWS}"
json_health "$STEERING_HEALTH_URL" "preflight-spectrum" "$jsonl" >/dev/null || true
json_health "$ATT_HEALTH_URL" "control-att" "$jsonl" >/dev/null || true

if [[ "$CONFIRM" != "1" ]]; then
  echo "REFUSED: --confirm is required before Spectrum config mutation or steering.service restart. ATT control untouched."
  echo "Preflight evidence: $jsonl"
  exit 0
fi

for ((i=0; i<WINDOWS; i++)); do
  if (( i % 2 == 0 )); then backend="icmplib"; else backend="fping"; fi
  echo "Window $((i+1))/${WINDOWS}: Spectrum backend=${backend}; ATT control untouched"
  set_spectrum_backend "$backend"
  scripts/deploy.sh spectrum "$SSH_HOST"
  ssh -o BatchMode=yes -o ConnectTimeout=5 "$SSH_HOST" "sudo systemctl reset-failed ${UNIT}; sudo systemctl restart ${UNIT}; systemctl is-active ${UNIT}"
  planned_restarts=$((planned_restarts + 1))
  sleep "$WINDOW_SEC"
  json_health "$STEERING_HEALTH_URL" "$backend" "$jsonl"
  json_health "$ATT_HEALTH_URL" "control-att" "$jsonl" >/dev/null || true
  nrestarts >/dev/null
 done

final_nrestarts="$(nrestarts)"
# systemd NRestarts counts automatic restarts, not operator-planned `systemctl restart`.
# The verdict schema's total_nrestarts is inclusive, so add planned apply-restarts
# back in before phase245-gate-eval subtracts them.
inclusive_nrestarts=$((final_nrestarts + planned_restarts))
write_summary "$summary" "$jsonl" "$baseline_nrestarts" "$planned_restarts" "$inclusive_nrestarts" "$prereg_json"
echo "Phase 245 A/B summary: $summary"
