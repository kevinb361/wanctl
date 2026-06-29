# Phase 264 Evidence — Live Single-Route Owner Flip

## Flip Details
- **Canary route**: ATT (distance 2, gateway 192.168.2.254)
- **Date**: 2026-06-29
- **Operator**: Kevin

## Pre-Flip Baseline (mode: dry_run)
- mode: dry_run
- active_owner: netwatch
- observed_owner: netwatch
- guard_status: conflict (4 Netwatch conflicts)
- All 4 routes enabled

## Steps Executed
1. Disabled all 3 Netwatch entries (*1 already disabled, *4 and *5 disabled via REST PATCH)
2. Verified guard clears (conflict_count: 0, guard_status: ok)
3. Set mode to `active` in steering.yaml
4. Sent SIGUSR1 to steering daemon (PID 980521)
5. Verified mode transition: dry_run -> active

## Post-Flip State
- mode: active
- active_owner: wanctl
- active_allowed: True
- guard_status: ok, conflict_count: 0
- circuit_open: False
- status: healthy
- All 4 routes still enabled
- Zero aborts, zero errors in journal

## Bugs Fixed During Flip
1. **REST API netwatch set support** — Added `_handle_netwatch_set` to `routeros_rest.py`
2. **Stale guard result** — Guard was only computed at startup. Added `_refresh_guard()` and 60s periodic refresh in daemon cycle

## Rollback Path
- Manual: `sudo sed -i "s/mode: active/mode: dry_run/" /etc/wanctl/steering.yaml` + SIGUSR1
- Auto-abort: circuit breaker open, router unreachable, Netwatch contention
- Netwatch re-enable: `/tool netwatch set [.id] disabled=no` for each entry

## Observations
- Guard refresh works on both periodic cycle (60s) and SIGUSR1 reload
- No route disruption during flip (Spectrum primary at distance 1 handles traffic)
- Daemon cycles cleanly at 50ms with no errors
