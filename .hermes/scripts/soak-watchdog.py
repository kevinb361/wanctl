#!/usr/bin/env python3
"""Soak watchdog for route management active mode on cake-shaper.

Checks steering health endpoint for mode changes, abort events,
guard conflicts, and circuit breaker state.

Runs locally, queries cake-shaper via SSH+curl.
Only delivers on anomaly — silent on healthy state.
"""
import json, os, subprocess, sys, time

HOST = "cake-shaper"
HEALTH_URL = "http://127.0.0.1:9102/health"
STATE_FILE = os.path.expanduser("~/.hermes/scripts/soak-watcher-state.json")

def ssh_run(cmd: str, timeout: int = 10) -> str:
    try:
        r = subprocess.run(
            f"ssh {HOST} {cmd}",
            shell=True, capture_output=True, text=True, timeout=timeout
        )
        return r.stdout.strip()
    except subprocess.TimeoutExpired:
        return ""

def check_health() -> dict | None:
    out = ssh_run(f"curl -s --max-time 5 {HEALTH_URL}", timeout=15)
    if not out:
        return None
    try:
        return json.loads(out)
    except json.JSONDecodeError:
        return None

def main():
    h = check_health()
    if h is None:
        print("CRITICAL: Health endpoint unreachable on cake-shaper")
        return

    rm = h.get("route_management", {})
    mode = rm.get("mode")
    active_owner = rm.get("active_owner")
    cb_open = rm.get("circuit_breaker", {}).get("open", False)
    last_abort = rm.get("last_abort")

    oi = h.get("ownership_inspection", {})
    routes = oi.get("routes", {})
    guard = routes.get("guard_status")
    conflicts = routes.get("conflict_count", 0)

    alerts = []

    # Mode must stay active during soak
    if mode != "active":
        alerts.append(f"MODE CHANGE: expected active, got {mode}")

    # Owner should be wanctl in active mode
    if active_owner != "wanctl" and mode == "active":
        alerts.append(f"OWNER MISMATCH: mode=active but owner={active_owner}")

    # Circuit breaker should stay closed
    if cb_open:
        alerts.append("CIRCUIT BREAKER OPEN")

    # New abort event?
    prev = {}
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE) as f:
                prev = json.load(f)
        except (json.JSONDecodeError, IOError):
            pass

    prev_abort = prev.get("last_abort")
    if last_abort and last_abort != prev_abort:
        if prev_abort:
            alerts.append(f"NEW ABORT: {json.dumps(last_abort)}")
        elif last_abort:
            # First check — was abort from before we started watching?
            ts = last_abort.get("timestamp", 0)
            if time.time() - ts < 3600:
                alerts.append(f"ABORT WITHIN LAST HOUR: {json.dumps(last_abort)}")

    # Guard should be clean in active mode
    if guard == "conflict" and mode == "active":
        alerts.append(f"GUARD CONFLICT: {conflicts} conflicts (abort likely imminent)")

    # Save state
    state = {
        "checked_at": time.time(),
        "mode": mode,
        "active_owner": active_owner,
        "last_abort": last_abort,
    }
    try:
        with open(STATE_FILE, "w") as f:
            json.dump(state, f)
    except IOError:
        pass

    # Deliver only on anomaly
    if alerts:
        print("SOAK ALERT:" + "|".join(alerts))
        print(f"  mode={mode}, owner={active_owner}, cb={cb_open}, guard={guard}, conflicts={conflicts}")
        if last_abort:
            print(f"  last_abort={json.dumps(last_abort)}")

if __name__ == "__main__":
    main()
