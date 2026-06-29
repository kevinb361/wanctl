#!/usr/bin/env bash
# Phase 265: Add backup route to active route management on cake-shaper.
#
# Usage: ./scripts/phase265-apply.sh
#
# Prerequisites:
#   - 24h soak completed with zero alerts
#   - Current state: mode=active, active_owner=wanctl, guard=clean
#
# What it does:
#   1. Adds "backup" route to /etc/wanctl/steering.yaml route_management.routes
#   2. Reloads steering daemon via SIGUSR1 (no restart)
#   3. Verifies reconciliation for all 4 routes
set -euo pipefail

HOST="${1:-cake-shaper}"

echo "=== Phase 265: Add backup route to $HOST ==="

# Step 1: Pre-check — verify current state
echo "[1/5] Pre-check: current state..."
ssh "$HOST" 'curl -s http://127.0.0.1:9102/health | python3 -c "
import sys, json
h = json.load(sys.stdin)
rm = h.get("route_management", {})
print(f"  mode={rm.get(\"mode\")}, owner={rm.get(\"active_owner\")}, cb={rm.get(\"circuit_breaker\",{}).get(\"open\")}")
routes = h.get("ownership_inspection",{}).get("routes",{})
print(f"  guard={routes.get(\"guard_status\")}, conflicts={routes.get(\"conflict_count\",0)}")
# Count configured routes in reconciliation
rec = rm.get("reconciliation", {})
print(f"  reconciliation routes: {len(rec.get(\"routes\", {}))}")
"'

# Step 2: Add backup route to steering.yaml
echo "[2/5] Adding backup route to /etc/wanctl/steering.yaml..."
ssh "$HOST" 'sudo python3 -c "
import yaml, sys
with open(\"/etc/wanctl/steering.yaml\") as f:
    data = yaml.safe_load(f)
rm = data.get(\"route_management\", {})
routes = rm.get(\"routes\", {})
if \"backup\" in routes:
    print(\"  backup route already present, skipping\")
    sys.exit(0)
routes[\"backup\"] = {\"comment\": \"Backup to Spectrum if ATT fails\"}
rm[\"routes\"] = routes
with open(\"/etc/wanctl/steering.yaml\", \"w\") as f:
    yaml.dump(data, f, default_flow_style=False, sort_keys=False)
print(\"  backup route added\")
"'

# Step 3: Reload daemon via SIGUSR1
echo "[3/5] Reloading steering daemon..."
ssh "$HOST" 'STEER_PID=$(systemctl show -p MainPID steering.service | cut -d= -f2) && sudo kill -USR1 "$STEER_PID" && echo "  SIGUSR1 sent to PID $STEER_PID"'

# Step 4: Wait and verify
echo "[4/5] Waiting for reconciliation..."
sleep 10
ssh "$HOST" 'curl -s http://127.0.0.1:9102/health | python3 -c "
import sys, json
h = json.load(sys.stdin)
rm = h.get("route_management", {})
print(f"  mode={rm.get(\"mode\")}, owner={rm.get(\"active_owner\")}")
rec = rm.get("reconciliation", {})
print(f"  reconciliation status: {rec.get(\"status\")}")
for k, v in rec.get("routes", {}).items():
    print(f"    {k}: {v.get(\"status\", \"?\")}")
print(f"  circuit_breaker open: {rm.get(\"circuit_breaker\",{}).get(\"open\")}")
print(f"  last_abort: {rm.get(\"last_abort\")}")
"'

# Step 5: Check journal for errors
echo "[5/5] Checking journal..."
ssh "$HOST" 'sudo journalctl -u steering.service --since "1 minute ago" --no-pager | grep -i "error\|fail\|exception" | head -5 || echo "  No errors"'

echo "=== Phase 265 complete ==="
