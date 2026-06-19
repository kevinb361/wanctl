#!/usr/bin/env bash
# Snapshot-A rollback: config-revert to icmplib under Phase-245 code (NOT a code rollback to ffaa8a0e)
#
# Snapshot-A rollback = restore the Spectrum measurement.backend config to icmplib
# under the currently-deployed Phase-245 code. This is NOT a code rollback to
# ffaa8a0e. The ffaa8a0e anchor proves Selection-A was the production-deployed
# starting point before Plans 01-03; after the Phase-245 deploy, the daemon flip
# remains deployed and only the backend config reverts to icmplib.

set -euo pipefail
PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin

SSH_HOST="cake-shaper"
HEALTH_URL="http://10.10.110.223:9101/health"
OUT_FILE=".planning/phases/245-live-a-b-rollback-anchor/evidence/phase245-rollback-proof.json"
CONFIRM="0"

usage() {
  cat <<'EOF'
Usage: scripts/phase245-rollback.sh [--confirm] [--ssh-host HOST] [--health-url URL] [--out FILE]

Without --confirm, prints the ordered config-only rollback plan and performs a
read-only health probe when reachable. With --confirm, mutates Spectrum config,
deploys, restarts steering.service, and verifies /health backend == icmplib (or
producer != wanctl-backend). ATT control WAN is untouched.
EOF
}

print_plan() {
  cat <<EOF
Phase 245 Snapshot-A CONFIG-only rollback plan (real mutation requires --confirm):
  1. Check production-deployed ref on ${SSH_HOST}: git -C /opt/wanctl rev-parse --short HEAD
  2. Restore Spectrum measurement.backend to icmplib in configs/spectrum.yaml
  3. Deploy Spectrum only: scripts/deploy.sh spectrum ${SSH_HOST}
  4. Restart steering.service: ssh ${SSH_HOST} 'sudo systemctl restart steering.service'
  5. Verify ${HEALTH_URL} rtt_source.backend == icmplib OR producer != wanctl-backend
  6. Record proof JSON: ${OUT_FILE}

This is a config-only revert under Phase-245 code; it is NOT a code rollback to ffaa8a0e.
ATT control WAN is untouched.
EOF
}

production_ref() {
  ssh -o BatchMode=yes -o ConnectTimeout=5 "$SSH_HOST" 'git -C /opt/wanctl rev-parse --short HEAD'
}

nrestarts() {
  ssh -o BatchMode=yes -o ConnectTimeout=5 "$SSH_HOST" 'systemctl show -p NRestarts --value steering.service'
}

health_check() {
  python3 - "$HEALTH_URL" <<'PY'
import json
import sys
from urllib.request import urlopen

url = sys.argv[1]
try:
    with urlopen(url, timeout=3) as fh:
        payload = json.load(fh)
except Exception as exc:
    raise SystemExit(f"HEALTH FAIL: {url}: {exc}")
rtt = payload.get("rtt_source") if isinstance(payload, dict) else None
if not isinstance(rtt, dict):
    raise SystemExit("HEALTH FAIL: missing rtt_source")
backend = rtt.get("backend")
producer = rtt.get("producer")
if backend != "icmplib" and producer == "wanctl-backend":
    raise SystemExit(f"HEALTH FAIL: backend={backend!r} producer={producer!r}; expected icmplib or non-wanctl producer")
print(json.dumps({"backend": backend, "producer": producer, "source_ip": rtt.get("source_ip"), "counts": rtt.get("counts")}, sort_keys=True))
PY
}

set_spectrum_icmplib() {
  python3 - "configs/spectrum.yaml" <<'PY'
import sys
from pathlib import Path
import yaml

path = Path(sys.argv[1])
data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
measurement = data.setdefault("measurement", {})
measurement["backend"] = "icmplib"
path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
PY
}

write_proof() {
  local ref="$1" before="$2" after="$3" health_json="$4"
  mkdir -p "$(dirname "$OUT_FILE")"
  python3 - "$OUT_FILE" "$ref" "$before" "$after" "$health_json" <<'PY'
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

out, ref, before, after, health_json = sys.argv[1:]
payload = {
    "checked_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
    "rollback_type": "config-only icmplib revert under Phase-245 code",
    "production_ref_short": ref,
    "nrestarts_before": before,
    "nrestarts_after": after,
    "health": json.loads(health_json),
    "att_control_touched": False,
}
Path(out).write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --confirm) CONFIRM="1"; shift ;;
    --ssh-host) SSH_HOST="${2:-}"; shift 2 ;;
    --health-url) HEALTH_URL="${2:-}"; shift 2 ;;
    --out) OUT_FILE="${2:-}"; shift 2 ;;
    --help|-h) usage; exit 0 ;;
    *) echo "ERROR: unknown argument: $1" >&2; usage >&2; exit 2 ;;
  esac
done

print_plan
if [[ "$CONFIRM" != "1" ]]; then
  echo "REFUSED: --confirm required for config mutation/deploy/restart. Read-only plan printed."
  exit 0
fi

ref="$(production_ref)"
before="$(nrestarts)"
set_spectrum_icmplib
scripts/deploy.sh spectrum "$SSH_HOST"
ssh -o BatchMode=yes -o ConnectTimeout=5 "$SSH_HOST" 'sudo systemctl restart steering.service'
sleep 10
health_json="$(health_check)"
after="$(nrestarts)"
write_proof "$ref" "$before" "$after" "$health_json"
echo "Phase 245 config-only rollback proof recorded: $OUT_FILE"
