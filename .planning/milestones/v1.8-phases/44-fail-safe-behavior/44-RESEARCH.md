# Phase 44: Fail-Safe Behavior - Research

**Researched:** 2026-01-29
**Domain:** Production daemon fail-safe behavior, rate limit persistence, watchdog tolerance
**Confidence:** HIGH

## Summary

This research covers fail-safe behavior for the wanctl controller to ensure rate limits persist during router outages and the systemd watchdog handles transient failures appropriately. The codebase already has solid foundations from Phase 43: `RouterConnectivityState` tracks consecutive failures, `classify_failure_type()` categorizes exceptions, and health endpoints report router reachability.

The primary gaps are: (1) no mechanism to queue rate changes during outages for later application, (2) no clear policy preventing rate limit removal during errors, and (3) the current watchdog logic treats all cycle failures equally without distinguishing router unreachability from daemon crashes.

**Primary recommendation:** Implement pending rate change tracking, enforce fail-closed policy (never send "remove" commands during errors), and modify watchdog logic to continue notifications during router-only failures while stopping for daemon-level crashes.

## Standard Stack

The established libraries/tools for this domain:

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| time.monotonic | stdlib | Failure timestamp tracking | Already used, monotonic prevents clock skew issues |
| collections.deque | stdlib | Pending rate change queue | Bounded, thread-safe, O(1) operations |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| router_connectivity | internal | Failure tracking | All router communication |
| systemd_utils | internal | Watchdog notifications | Daemon health reporting |
| wan_controller_state | internal | State persistence | EWMA/rate preservation |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| deque | list | deque has O(1) popleft, list is O(n) |
| Custom queue | asyncio.Queue | Not needed - single-threaded control loop |

**Installation:**
No new dependencies required - all patterns exist in codebase.

## Architecture Patterns

### Current Error Handling Flow

```
run_cycle()
    |
    v
apply_rate_changes_if_needed()
    |-- Flash wear check (skip if rates unchanged)
    |-- Rate limiter check (skip if throttled)
    |-- router.set_limits()
        |-- FailoverRouterClient.run_cmd()
        |-- retry_with_backoff() [3 attempts]
    |
    v
On failure: router_connectivity.record_failure()
           return False --> consecutive_failures++

After 3 failures: watchdog_enabled = False
                  Systemd restarts daemon
```

### Recommended Pattern: Pending Rate Change Queue

**What:** When router is unreachable, store calculated rate changes instead of discarding them. Apply most recent on reconnection.

**Why not apply all queued changes:** Rates calculated during outage may be stale. The most recent rate reflects current conditions.

**Pattern:**
```python
# Source: Derived from existing patterns in wanctl codebase

class PendingRateChange:
    """Track rate changes during router outage."""

    def __init__(self):
        self.pending_dl_rate: int | None = None
        self.pending_ul_rate: int | None = None
        self.queued_at: float | None = None  # monotonic timestamp

    def queue(self, dl_rate: int, ul_rate: int) -> None:
        """Queue a rate change for later application."""
        self.pending_dl_rate = dl_rate
        self.pending_ul_rate = ul_rate
        self.queued_at = time.monotonic()

    def clear(self) -> None:
        """Clear pending changes after successful application."""
        self.pending_dl_rate = None
        self.pending_ul_rate = None
        self.queued_at = None

    def has_pending(self) -> bool:
        """Check if there are pending changes."""
        return self.pending_dl_rate is not None
```

### Recommended Pattern: Fail-Closed Policy

**What:** During router errors, NEVER send commands that could remove or weaken rate limits.

**Policy rules:**
1. Never send "remove queue" commands during error recovery
2. Never send max-limit=0 or unbounded rates during outages
3. When reconnecting, verify current router state matches expected before modifying
4. If verification fails, apply last known good rate (conservative)

**Example enforcement:**
```python
# Source: Pattern for wanctl/autorate_continuous.py

def apply_rate_changes_if_needed(self, dl_rate: int, ul_rate: int) -> bool:
    """Apply rate changes with fail-closed policy."""

    # FAIL-CLOSED: Never remove limits during error recovery
    if not self.router_connectivity.is_reachable:
        self.pending_rates.queue(dl_rate, ul_rate)
        self.logger.debug(
            f"{self.wan_name}: Router unreachable, queuing rate change "
            f"(DL={dl_rate/1e6:.0f}M, UL={ul_rate/1e6:.0f}M)"
        )
        return True  # Cycle succeeds, just can't apply changes

    # Normal application path...
```

### Recommended Pattern: Watchdog Failure Type Distinction

**What:** Router unreachability should NOT stop watchdog notifications. Only daemon-level crashes should.

**Rationale:** The daemon is functioning correctly - measuring RTT, calculating rates, updating EWMA. The router is the problem, not the daemon. Systemd restarting the daemon won't fix router issues.

**Pattern:**
```python
# Source: Pattern for main daemon loop

# Track failures by category
router_unreachable = False
cycle_failures = 0

while not is_shutdown_requested():
    cycle_success = controller.run_cycle()

    # Check if failure is router-specific
    router_unreachable = not controller.router_connectivity.is_reachable

    if cycle_success:
        cycle_failures = 0
    else:
        cycle_failures += 1

    # WATCHDOG POLICY:
    # - Router failures: Continue watchdog, daemon is healthy
    # - Daemon failures (ping, measurement, state): Stop watchdog
    if router_unreachable and cycle_failures < MAX_FAILURES:
        # Daemon healthy, router problem - keep watchdog alive
        notify_watchdog()
        notify_status(f"Router unreachable ({cycle_failures} cycles)")
    elif cycle_success:
        notify_watchdog()
    else:
        # True daemon failure - let watchdog expire
        notify_degraded(f"{cycle_failures} consecutive failures")
```

### Recommended Pattern: Recovery Verification

**What:** On reconnection after outage, verify router state before applying changes.

**Why:** During long outages, router may have been rebooted or manually configured. Blindly applying queued changes could conflict.

**Pattern:**
```python
# Source: Pattern for reconnection handling

def on_reconnection(self) -> None:
    """Handle reconnection after router outage."""
    outage_duration = time.monotonic() - self.router_connectivity.last_failure_time

    self.logger.info(
        f"{self.wan_name}: Router reconnected after {outage_duration:.1f}s outage"
    )

    # For short outages (< 60s): Apply pending rate directly
    # For long outages (>= 60s): Recalculate based on current EWMA
    if outage_duration >= 60.0 and self.pending_rates.has_pending():
        self.logger.info(
            f"{self.wan_name}: Long outage ({outage_duration:.0f}s), "
            f"discarding stale queued rates, using current EWMA state"
        )
        self.pending_rates.clear()
    elif self.pending_rates.has_pending():
        # Apply pending rates
        self.apply_rate_changes_if_needed(
            self.pending_rates.pending_dl_rate,
            self.pending_rates.pending_ul_rate
        )
        self.pending_rates.clear()
```

### Anti-Patterns to Avoid
- **Removing rate limits on error:** NEVER send max-limit=0 or "remove" commands during errors
- **Resetting EWMA on reconnection:** EWMA baseline must be preserved (Phase 43 invariant)
- **Applying all queued changes:** Only apply most recent, older ones are stale
- **Stopping watchdog immediately on router failure:** Distinguish router vs daemon problems
- **Logging every cycle during outage:** Rate-limit to first failure, 3rd, every 10th

## Don't Hand-Roll

Problems that look simple but have existing solutions:

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Failure classification | Ad-hoc exception checks | `classify_failure_type()` | Covers all edge cases, consistent |
| Connectivity tracking | Manual counter | `RouterConnectivityState` | Handles timestamps, logging |
| Atomic state writes | Manual file writes | `atomic_write_json()` | Prevents corruption |
| Watchdog notifications | Direct sd_notify | `notify_watchdog()` | Handles systemd unavailable |

**Key insight:** Phase 43 infrastructure handles detection and tracking. This phase adds *behavior* policies on top.

## Common Pitfalls

### Pitfall 1: Aggressive Rate Limit Removal
**What goes wrong:** Controller sends "remove queue" or max-limit=0 during error recovery
**Why it happens:** Assumption that "clean slate" is safer than "stale limits"
**How to avoid:** Explicit fail-closed policy - existing limits are ALWAYS safer
**Warning signs:** Traffic spike after outage recovery, bufferbloat returns

### Pitfall 2: Watchdog Thrashing on Router Issues
**What goes wrong:** Systemd restarts daemon repeatedly during router maintenance
**Why it happens:** All failures treated equally for watchdog
**How to avoid:** Distinguish router failures from daemon failures, continue watchdog for router issues
**Warning signs:** Multiple restarts in logs when router is down, restart loops

### Pitfall 3: Stale Rate Application
**What goes wrong:** Rates calculated during outage applied verbatim on reconnection
**Why it happens:** Queue all rate changes and apply sequentially
**How to avoid:** Keep only most recent pending rate, discard on long outages
**Warning signs:** Rate jumps to inappropriate value after reconnection

### Pitfall 4: EWMA Reset on Reconnection
**What goes wrong:** Baseline RTT resets to config initial value after outage
**Why it happens:** Treating reconnection as fresh start
**How to avoid:** EWMA state preserved in state file (Phase 43 invariant) - don't reset
**Warning signs:** Baseline RTT jumps after reconnection, false GREEN/RED assessment

### Pitfall 5: Log Spam During Extended Outage
**What goes wrong:** Logging every failed cycle during 5-minute outage
**Why it happens:** No rate limiting on failure logs
**How to avoid:** Log first failure, 3rd, every 10th (already in Phase 43)
**Warning signs:** Log files grow rapidly during outages, I/O overhead

### Pitfall 6: Floor-Stuck Forever
**What goes wrong:** Rates stay at floor indefinitely after outage ends
**Why it happens:** Conservative recovery prevents rate increases
**How to avoid:** EWMA is preserved, normal algorithm will increase rates naturally
**Warning signs:** Users report slow speeds long after outage, no rate increases in logs

## Code Examples

### Current: Router Communication in run_cycle()
```python
# Source: wanctl/autorate_continuous.py lines 1411-1430

# Apply rate changes (with flash wear + rate limit protection)
try:
    if not self.apply_rate_changes_if_needed(dl_rate, ul_rate):
        # Router communication failed - record failure
        self.router_connectivity.record_failure(
            ConnectionError("Failed to apply rate limits to router")
        )
        return False
    # Router communication succeeded - record success
    self.router_connectivity.record_success()
except Exception as e:
    # Unexpected exception during router communication
    failure_type = self.router_connectivity.record_failure(e)
    # Log on first failure, every 3rd failure, or on threshold exceeded
    failures = self.router_connectivity.consecutive_failures
    if failures == 1 or failures == 3 or failures % 10 == 0:
        self.logger.warning(...)
    return False
```

### Current: Watchdog Logic in Main Loop
```python
# Source: wanctl/autorate_continuous.py lines 1871-1898

# Track consecutive failures
if cycle_success:
    consecutive_failures = 0
else:
    consecutive_failures += 1
    # ... logging ...

    # Check if we've exceeded failure threshold
    if consecutive_failures >= MAX_CONSECUTIVE_FAILURES and watchdog_enabled:
        watchdog_enabled = False
        # ... logging ...
        notify_degraded("consecutive failures exceeded threshold")

# Notify systemd watchdog ONLY if healthy
if watchdog_enabled and cycle_success:
    notify_watchdog()
elif not watchdog_enabled:
    notify_degraded(f"{consecutive_failures} consecutive failures")
```

### Current: Health Endpoint Router Status
```python
# Source: wanctl/health_check.py lines 86-119

# Check router connectivity across all WANs
all_routers_reachable = all(
    wan_info["controller"].router_connectivity.is_reachable
    for wan_info in self.controller.wan_controllers
)

# ... per-WAN health ...
wan_health: dict[str, Any] = {
    # ...
    "router_connectivity": wan_controller.router_connectivity.to_dict(),
}

# Top-level router reachability aggregate
health["router_reachable"] = all_routers_reachable

# Determine overall health status
# Healthy if consecutive failures < threshold AND all routers reachable
is_healthy = self.consecutive_failures < 3 and all_routers_reachable
health["status"] = "healthy" if is_healthy else "degraded"
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Fail-fast (discard on error) | Fail-closed (preserve limits) | This phase | Safety during outages |
| All failures = daemon problem | Distinguish router vs daemon | This phase | Fewer unnecessary restarts |
| No pending rate queue | Queue most recent rate | This phase | Smoother recovery |
| Immediate watchdog stop | Continue on router issues | This phase | Stability during maintenance |

**Deprecated/outdated:**
- None - this phase extends current patterns

## Design Recommendations (Claude's Discretion Items)

Based on CONTEXT.md guidance to prioritize fail-safe over fail-fast:

### Rate Limit Persistence
**Recommendation:** Never send "remove queue" commands. Implement `PendingRateChange` class to track most recent calculated rate during outage. Clear pending on application or after long outage (>60s).

**Rate aging policy:** Discard queued rates after 60 seconds - EWMA state is authoritative, not stale calculations.

**Floor-stuck concern:** Not a real problem. EWMA is preserved (Phase 43). Normal algorithm will increase rates naturally when congestion clears. No special handling needed.

### Watchdog Thresholds
**Recommendation:** Router failures should NOT count toward watchdog failure threshold. The daemon is healthy - it's measuring RTT, updating EWMA, persisting state. Only true daemon failures (ping failure, measurement exception, state corruption) should stop watchdog.

**Implementation:** Add `router_only_failure` flag to distinguish. Continue `notify_watchdog()` when `router_only_failure=True` and `consecutive_failures < threshold`.

**Current default (3 failures):** Keep this threshold for daemon failures. Router failures don't count toward it.

### Recovery Behavior
**Recommendation:**
- Short outage (<60s): Apply most recent pending rate immediately
- Long outage (>=60s): Discard stale pending rates, let EWMA drive next cycle
- Always verify router is reachable before sending any commands

**Verification on reconnection:** Not needed for rate limits - current rates don't need verification. The `last_applied_dl_rate`/`last_applied_ul_rate` tracking handles flash wear protection automatically.

### Logging During Outage
**Recommendation:**
- Include outage duration in reconnection log message (easy, valuable for debugging)
- Metrics recording: Write `router_unreachable` flag to SQLite, not null values (preserves data integrity)
- Health endpoint already degrades on unreachable (Phase 43) - sufficient for alerting
- No additional alerting beyond health endpoint - keep simple per user guidance

## Open Questions

1. **Timeout vs connection_refused treatment**
   - What we know: Both are transient, but different causes
   - What's unclear: Should auth_failure stop watchdog immediately?
   - Recommendation: Auth failures should stop watchdog (daemon misconfigured, needs intervention)

2. **Multi-WAN coordination during outage**
   - What we know: Both daemons independent, health aggregates all routers
   - What's unclear: If one WAN router down, does other continue normally?
   - Recommendation: Yes, each WANController independent. Global health degrades but individual daemons continue.

## Sources

### Primary (HIGH confidence)
- wanctl/autorate_continuous.py - Control loop, watchdog integration, state management
- wanctl/router_connectivity.py - Failure tracking (Phase 43 implementation)
- wanctl/health_check.py - Health endpoint patterns
- wanctl/wan_controller_state.py - State persistence patterns
- wanctl/systemd_utils.py - Watchdog notification API

### Secondary (MEDIUM confidence)
- wanctl/steering/daemon.py - Parallel implementation patterns
- .planning/phases/43-error-detection-reconnection/43-RESEARCH.md - Prior phase research

### Tertiary (LOW confidence)
- General fail-safe daemon patterns from training data

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - All patterns exist in codebase
- Architecture: HIGH - Extends proven Phase 43 patterns
- Pitfalls: HIGH - Based on codebase analysis and CONTEXT.md guidance
- Recommendations: HIGH - Grounded in user decisions and codebase patterns

**Research date:** 2026-01-29
**Valid until:** 60 days (stable domain, internal patterns)
