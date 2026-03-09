# Phase 43: Error Detection & Reconnection - Research

**Researched:** 2026-01-29
**Domain:** Production daemon error handling, network reconnection, failure type classification
**Confidence:** HIGH

## Summary

This research covers error detection and graceful reconnection for the wanctl controller when the MikroTik router becomes unreachable mid-cycle or when SSH/REST connections drop. The codebase already has robust foundations: `FailoverRouterClient` handles REST-to-SSH failover, `retry_with_backoff` provides exponential backoff for transient errors, and `is_retryable_error()` classifies exception types.

The primary gap is that current error handling triggers at the command level (individual `run_cmd()` calls), but there is no cycle-level detection that tracks overall router reachability state, reports it to health endpoints, or adjusts behavior during sustained outages.

**Primary recommendation:** Extend existing patterns to add router connectivity state tracking at the WANController/SteeringDaemon level, distinguishing failure types (timeout vs connection refused vs DNS), and integrating with health endpoints and systemd watchdog.

## Standard Stack

The established libraries/tools for this domain:

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| requests | 2.32+ | REST API calls | Already used, has clear exception hierarchy |
| paramiko | 3.x | SSH connections | Already used for RouterOSSSH |
| socket | stdlib | TCP connectivity | Used for health checks, error classification |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| retry_utils | internal | Exponential backoff | All transient failures |
| error_handling | internal | Decorator-based error handling | Method-level error suppression |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Custom retry | tenacity library | Not needed - existing retry_utils is sufficient |
| Circuit breaker | pybreaker | Overkill for single-router scenario |

**Installation:**
No new dependencies required - all patterns exist in codebase.

## Architecture Patterns

### Current Error Handling Hierarchy

```
Command Level (run_cmd)
    |
    v
FailoverRouterClient.run_cmd()
    |-- Catches: ConnectionError, TimeoutError, OSError
    |-- Action: Switch to fallback transport
    v
RouterOSREST.run_cmd() / RouterOSSSH.run_cmd()
    |-- @retry_with_backoff decorator
    |-- 3 attempts, exponential backoff
    v
is_retryable_error()
    |-- Classifies exception types
    |-- Returns True/False for retry decision
```

### Recommended Pattern: Cycle-Level Router State

**What:** Add a `RouterConnectivityState` tracker that aggregates command-level failures into cycle-level connectivity assessment.

**When to use:** Every control cycle should update and check connectivity state before making rate decisions.

**Example:**
```python
# Source: Derived from existing patterns in wanctl codebase

class RouterConnectivityState:
    """Track router connectivity across cycles."""

    def __init__(self, logger: logging.Logger):
        self.logger = logger
        self.consecutive_failures = 0
        self.last_failure_type: str | None = None
        self.last_failure_time: float | None = None
        self.is_reachable = True

    def record_success(self) -> None:
        """Record successful router communication."""
        if self.consecutive_failures > 0:
            self.logger.info(
                f"Router reconnected after {self.consecutive_failures} failures"
            )
        self.consecutive_failures = 0
        self.last_failure_type = None
        self.is_reachable = True

    def record_failure(self, exception: Exception) -> str:
        """Record failed router communication, return failure type."""
        self.consecutive_failures += 1
        self.last_failure_time = time.monotonic()
        self.is_reachable = False

        # Classify failure type
        self.last_failure_type = classify_failure_type(exception)
        return self.last_failure_type
```

### Failure Type Classification

**What:** Distinguish between transient and persistent failures for appropriate response.

**Classification scheme:**
```python
# Source: Extended from retry_utils.is_retryable_error()

def classify_failure_type(exception: Exception) -> str:
    """Classify exception into failure type for appropriate handling.

    Returns:
        "timeout" - Request timed out, likely network congestion
        "connection_refused" - Service not listening (router down/rebooting)
        "network_unreachable" - Network path broken
        "dns_failure" - DNS resolution failed
        "auth_failure" - Authentication rejected (not retryable)
        "unknown" - Unclassified error
    """
    # Timeout errors - most common, usually transient
    if isinstance(exception, (TimeoutError, socket.timeout)):
        return "timeout"
    if isinstance(exception, subprocess.TimeoutExpired):
        return "timeout"

    err_str = str(exception).lower()

    # Connection refused - router not listening
    if isinstance(exception, ConnectionRefusedError):
        return "connection_refused"
    if "connection refused" in err_str:
        return "connection_refused"

    # Network unreachable
    if "network is unreachable" in err_str:
        return "network_unreachable"
    if "no route to host" in err_str:
        return "network_unreachable"

    # DNS failure
    if isinstance(exception, socket.gaierror):
        return "dns_failure"
    if "name or service not known" in err_str:
        return "dns_failure"

    # Paramiko auth failures
    if "AuthenticationException" in type(exception).__name__:
        return "auth_failure"
    if "authentication failed" in err_str:
        return "auth_failure"

    # Requests library specific
    try:
        import requests.exceptions
        if isinstance(exception, requests.exceptions.ConnectTimeout):
            return "timeout"
        if isinstance(exception, requests.exceptions.ReadTimeout):
            return "timeout"
        if isinstance(exception, requests.exceptions.ConnectionError):
            if "refused" in err_str:
                return "connection_refused"
            return "network_unreachable"
    except ImportError:
        pass

    return "unknown"
```

### Health Endpoint Integration

**What:** Report router connectivity state in health check response.

**Pattern:**
```python
# Source: Derived from existing health_check.py

# In health response
health = {
    "status": "healthy" if is_healthy else "degraded",
    "router_connectivity": {
        "reachable": connectivity_state.is_reachable,
        "consecutive_failures": connectivity_state.consecutive_failures,
        "last_failure_type": connectivity_state.last_failure_type,
    },
    # ... existing fields
}
```

### Anti-Patterns to Avoid
- **Immediate retry without backoff:** Already avoided via retry_utils - DO NOT bypass
- **Ignoring failure types:** Different types need different response (timeout = wait, auth = don't retry)
- **Logging every failure:** Rate-limit logging during sustained outages
- **Resetting state on reconnect:** Preserve EWMA/baseline, only reset failure counters

## Don't Hand-Roll

Problems that look simple but have existing solutions:

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Exponential backoff | Custom sleep loop | `retry_with_backoff` decorator | Handles jitter, logging, metrics |
| Retryable classification | Ad-hoc isinstance checks | `is_retryable_error()` | Covers all edge cases |
| Transport failover | Manual REST/SSH switching | `FailoverRouterClient` | Handles state, logging |
| Error suppression | Try/except everywhere | `@handle_errors` decorator | Consistent logging |

**Key insight:** The codebase has mature error handling patterns - this phase extends them to cycle-level state, not replaces them.

## Common Pitfalls

### Pitfall 1: Conflating Command Failure with Router Unreachable
**What goes wrong:** A single command failure triggers "router unreachable" state
**Why it happens:** Individual commands can fail for many reasons (syntax, queue not found)
**How to avoid:** Track consecutive failures; require N failures before declaring unreachable
**Warning signs:** State flapping between reachable/unreachable on transient errors

### Pitfall 2: Aggressive Reconnection During Router Reboot
**What goes wrong:** Rapid retry attempts flood logs and waste resources during router reboot
**Why it happens:** No backoff between reconnection attempts
**How to avoid:** Use exponential backoff with max delay (already in retry_utils)
**Warning signs:** Log spam of connection attempts every 50ms

### Pitfall 3: Blocking Cycle on Slow Failure Detection
**What goes wrong:** 15-second SSH timeout blocks entire 50ms cycle
**Why it happens:** Synchronous timeout waits in hot path
**How to avoid:** Use short initial timeout (2-3s), escalate only on retry
**Warning signs:** Cycle time exceeds interval during outages

### Pitfall 4: State Corruption on Reconnection
**What goes wrong:** EWMA baseline or rate limits reset incorrectly after reconnection
**Why it happens:** Assuming reconnection means fresh start
**How to avoid:** Preserve EWMA state; only reset failure counters
**Warning signs:** Rate limits jump to ceiling immediately after reconnect

### Pitfall 5: Auth Failure Infinite Retry
**What goes wrong:** Auth failures retry forever instead of failing fast
**Why it happens:** Treating auth failure as transient error
**How to avoid:** Classify failure type; auth_failure should not retry
**Warning signs:** Log spam of "authentication failed" messages

## Code Examples

### Current: FailoverRouterClient Failover
```python
# Source: wanctl/router_client.py lines 182-206

def run_cmd(
    self, cmd: str, capture: bool = False, timeout: int | None = None
) -> tuple[int, str, str]:
    if self._using_fallback:
        return self._get_fallback().run_cmd(cmd, capture=capture, timeout=timeout)

    try:
        return self._get_primary().run_cmd(cmd, capture=capture, timeout=timeout)
    except (ConnectionError, TimeoutError, OSError) as e:
        self.logger.warning(
            f"Primary transport ({self.primary_transport}) failed: {e}. "
            f"Switching to fallback ({self.fallback_transport})"
        )
        self._using_fallback = True
        return self._get_fallback().run_cmd(cmd, capture=capture, timeout=timeout)
```

### Current: Retry With Backoff
```python
# Source: wanctl/retry_utils.py lines 82-130

@retry_with_backoff(max_attempts=3, initial_delay=1.0, backoff_factor=2.0)
def run_cmd(self, cmd: str, capture: bool = False, timeout: int | None = None):
    # Retries on transient failures with exponential backoff
    # 1.0s -> 2.0s -> give up
    ...
```

### Current: Error Classification
```python
# Source: wanctl/retry_utils.py lines 12-79

def is_retryable_error(exception: Exception) -> bool:
    """Determine if an exception represents a transient/retryable error."""
    # Timeout is always retryable
    if isinstance(exception, subprocess.TimeoutExpired):
        return True
    # Connection errors are retryable
    if isinstance(exception, ConnectionError):
        return True
    # OSError with specific messages
    if isinstance(exception, OSError):
        err_str = str(exception).lower()
        retryable_messages = [
            "connection refused",
            "connection timed out",
            "connection reset",
            "broken pipe",
            "network is unreachable",
        ]
        return any(msg in err_str for msg in retryable_messages)
    # ... requests exceptions
```

### Recommended: Cycle-Level Error Handling in run_cycle()
```python
# Source: Pattern for wanctl/autorate_continuous.py WANController.run_cycle()

def run_cycle(self) -> bool:
    """Main cycle with router connectivity tracking."""
    # ... existing RTT measurement ...

    # Apply rate changes with connectivity tracking
    try:
        if not self.apply_rate_changes_if_needed(dl_rate, ul_rate):
            self.router_connectivity.record_failure(
                ConnectionError("Failed to apply limits")
            )
            return False
        self.router_connectivity.record_success()
    except Exception as e:
        failure_type = self.router_connectivity.record_failure(e)
        self.logger.warning(
            f"{self.wan_name}: Router communication failed "
            f"({failure_type}, {self.router_connectivity.consecutive_failures} consecutive)"
        )
        # Don't return False for first few failures - let watchdog handle sustained issues
        if self.router_connectivity.consecutive_failures >= 3:
            return False

    # ... rest of cycle ...
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Single transport | FailoverRouterClient | v1.3 | REST→SSH automatic failover |
| No retry | retry_with_backoff | v1.0 | 3 attempts with exponential backoff |
| Silent failures | is_retryable_error | v1.0 | Explicit classification |
| Log every error | Rate-limited logging | Needed | Prevents log spam during outages |

**Deprecated/outdated:**
- None - existing patterns are current and appropriate

## Open Questions

1. **Timeout tuning for 50ms cycles**
   - What we know: SSH timeout is 15s, REST timeout is 15s
   - What's unclear: Whether these should be reduced for faster failure detection
   - Recommendation: Keep existing timeouts; rely on consecutive failure count instead

2. **Recovery behavior after long outage**
   - What we know: EWMA baseline should be preserved
   - What's unclear: Should rates start at current or ceiling after 5+ minute outage?
   - Recommendation: Start at current rates; let normal algorithm recover

3. **Interaction with systemd watchdog**
   - What we know: 3 consecutive failures stops watchdog notification
   - What's unclear: Should router unreachable stop watchdog separately?
   - Recommendation: Router failures count toward consecutive_failures; existing logic handles

## Sources

### Primary (HIGH confidence)
- wanctl/router_client.py - FailoverRouterClient implementation
- wanctl/retry_utils.py - Exponential backoff and error classification
- wanctl/autorate_continuous.py - Control loop and health integration
- wanctl/health_check.py - Health endpoint patterns

### Secondary (MEDIUM confidence)
- [Python Requests Timeout Guide](https://oxylabs.io/blog/python-requests-timeout) - Connect vs read timeout distinction
- [Requests Exception Handling](https://requests.readthedocs.io/en/latest/_modules/requests/exceptions/) - Official exception hierarchy
- [Paramiko Exception Documentation](https://docs.paramiko.org/en/stable/api/ssh_exception.html) - SSH exception types

### Tertiary (LOW confidence)
- General daemon error handling patterns from web search

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - All patterns exist in codebase
- Architecture: HIGH - Extends proven patterns
- Pitfalls: HIGH - Based on codebase analysis and production experience

**Research date:** 2026-01-29
**Valid until:** 60 days (stable domain, internal patterns)
