#!/usr/bin/env python3
"""Phase 266 soak watchdog — monitor failover bridge stability."""
import json
import sys
import urllib.request
import time
from pathlib import Path

SOAK_FILE = Path("/tmp/soak_266.json")
HEALTH_URL = "http://127.0.0.1:9102/health"
CHECK_INTERVAL = 300  # 5 minutes
PASS_COUNT = 288  # 24h at 5min intervals = 288 checks


def load_state():
    return json.loads(SOAK_FILE.read_text()) if SOAK_FILE.exists() else {"checks": 0, "errors": [], "started_at": None}


def save_state(state):
    SOAK_FILE.write_text(json.dumps(state, indent=2))


def check():
    state = load_state()
    if state["started_at"] is None:
        state["started_at"] = time.time()

    try:
        with urllib.request.urlopen(HEALTH_URL, timeout=5) as resp:
            health = json.loads(resp.read())

        fo = health.get("failover", {})
        rm = health.get("route_management", {})
        rec = rm.get("reconciliation", {})
        cb = rm.get("circuit_breaker", {})

        # Checks
        errors = []
        if not fo.get("enabled"):
            errors.append("failover not enabled")
        if cb.get("open"):
            errors.append("circuit breaker OPEN")
        if rec.get("route_count") != 4:
            errors.append(f"route_count={rec.get('route_count')} (expected 4)")

        if errors:
            state["errors"].append({"time": time.time(), "errors": errors})
            if len(state["errors"]) > 10:
                state["errors"] = state["errors"][-10:]
        else:
            state["checks"] += 1

    except Exception as e:
        state["errors"].append({"time": time.time(), "errors": [str(e)]})

    save_state(state)

    # Report
    elapsed_h = (time.time() - state["started_at"]) / 3600
    print(f"P266 soak: {state['checks']}/{PASS_COUNT} clean checks ({elapsed_h:.1f}h elapsed)")
    if state["errors"]:
        last = state["errors"][-1]
        print(f"  Last error: {last['errors']}")

    if state["checks"] >= PASS_COUNT:
        print("SOAK PASSED — 24h clean observation complete.")
        sys.exit(0)

    if len(state["errors"]) >= 5:
        print("SOAK FAILED — 5+ consecutive errors.")
        sys.exit(1)


if __name__ == "__main__":
    check()
