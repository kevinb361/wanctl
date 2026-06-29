# Phase 264 Evidence — Live Flip + Abort Path Verification

## Dates
- Flip to active: 2026-06-29 ~02:54 UTC
- Abort path tested: 2026-06-29 ~10:15 UTC
- Evidence written: 2026-06-29 ~10:35 UTC

## Bugs Fixed During Phase

### 1. Wrong inspector attribute name
**File:** `src/wanctl/steering/daemon.py`
**Problem:** `_check_route_abort` looked for `self.route_ownership_inspector` which
does not exist. Actual attribute is `self.ownership_inspector`.
**Impact:** Netwatch contention abort never fired.
**Fix:** Changed to `getattr(self, "ownership_inspector", None)`.

### 2. Abort spam (no idempotency)
**File:** `src/wanctl/steering/daemon.py`
**Problem:** After abort fired, the mode stayed `active` (config mode wasn't updated),
so every subsequent cycle re-fired the abort.
**Fix:** Added `if self.route_manager.mode != "active": return` gate AND
set `config.route_management_mode = "dry_run"` after each abort path.

### 3. Config mode not synced on abort
**File:** `src/wanctl/steering/daemon.py`
**Problem:** `abort_to_netwatch` sets `route_manager.mode = "dry_run"` but not
`config.route_management_mode`. SIGUSR1 reload compared config modes (both
still `active`), skipped update, so route_manager.mode stayed stale.
**Fix:** All three abort paths now also set `self.config.route_management_mode = "dry_run"`.

### 4. Guard stale at startup
**File:** `src/wanctl/steering/daemon.py`
**Problem:** Guard was computed once at startup, never refreshed.
**Fix:** Added periodic guard refresh every 60s in daemon cycle + on SIGUSR1 reload.

### 5. Abort check skipped by anomaly gate
**File:** `src/wanctl/steering/daemon.py`
**Problem:** Abort check was after `if anomaly_detected: return True`,
so congestion anomalies could skip the abort path entirely.
**Fix:** Moved abort check before state management subsystem.

## Pre-Flip Baseline
| Metric | Value |
|--------|-------|
| mode | dry_run |
| active_owner | netwatch |
| observed_owner | netwatch |
| guard | ok, 0 conflicts |
| circuit_breaker | closed, 0 failures |

## Flip Execution
1. Disabled all 3 Netwatch entries (retained, not deleted)
2. Guard cleared from 4 conflicts to 0
3. Set mode to `active` via config + SIGUSR1
4. Wanctl now owns route management (`active_owner: wanctl`)

## Abort Path Smoke Test (Netwatch Re-enabled)

### Test: Re-enable Netwatch, flip to active, observe abort
- **Result:** ABORT fired correctly on Netwatch contention
- **Journal:** Single ABORT entry, no spam
- **mode_before:** active
- **mode_after:** dry_run
- **Route revert:** All 3 routes re-enabled successfully (spectrum=true, att=true, att_policy=true)
- **Health endpoint:** `last_abort` recorded with trip_condition=netwatch_contention
- **last_event:** Full abort evidence with route_revert_results

## Post-Test State
- mode: dry_run (auto-reverted by abort)
- active_owner: netwatch
- observed_owner: netwatch (Netwatch entries re-enabled)
- guard: conflict, 4 conflicts (Netwatch contesting)
- No abort spam (idempotency proven)

## Monotonic Timestamps (No Restarts)
- spectrum: 259295876567 (unchanged)
- att: 84347000490 (unchanged)
- steering: varies per restart (expected during deploy)

## Code Changes Summary
- `src/wanctl/steering/daemon.py`: Guard refresh, abort check fix, idempotency
- `src/wanctl/steering/route_manager.py`: (no changes needed)
- `src/wanctl/routeros_rest.py`: Added `_handle_netwatch_set` for REST PATCH support

## Netwatch REST API Note
Fresh REST connections to `/tool/netwatch` time out on this router. The daemon's
persistent session works fine. Netwatch entry disable/re-enable requires the
daemon's own `run_cmd` method or direct SSH with password access.

## Final Live Flip (2026-06-29 ~10:57 UTC)
After disabling all 3 Netwatch entries via SSH (REST API times out for fresh
connections), guard cleared and flip to active succeeded:

| Metric | Value |
|--------|-------|
| mode | active |
| active_owner | wanctl |
| observed_owner | none |
| configured_owner | netwatch |
| active_allowed | True |
| guard | None (clean) |
| circuit_breaker | closed |
| last_abort | None (no aborts after flip) |
| ABORT journal entries (post-flip) | 0 |
| routes | All 4 enabled |
| steering PID | 1318060 (unchanged since deploy) |
| steering uptime | ~26 min (no restarts) |
