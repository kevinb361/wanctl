# Phase 25: Health Endpoint Core - Research

**Researched:** 2026-01-23
**Domain:** Python http.server, threading, health endpoints
**Confidence:** HIGH

## Summary

This phase adds an HTTP health endpoint to the steering daemon. The project already has an established pattern for health endpoints in `src/wanctl/health_check.py` (autorate daemon) and `src/wanctl/metrics.py` (Prometheus metrics). Both use Python's stdlib `http.server` module with daemon threads.

The standard approach is to reuse or extend the existing `health_check.py` pattern:
- `http.server.HTTPServer` + `BaseHTTPRequestHandler` for the HTTP layer
- `threading.Thread(daemon=True)` for background operation
- Class-level attributes on the handler for shared state (start_time, consecutive_failures)
- Explicit `shutdown()` + `join(timeout=5.0)` for clean termination

**Primary recommendation:** Create a steering-specific health module (`src/wanctl/steering/health.py`) that mirrors the autorate `health_check.py` pattern but with steering-specific health data.

## Standard Stack

The established libraries/tools for this domain:

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| http.server | stdlib | HTTP server and handler | Already used by project, no external deps |
| threading | stdlib | Background thread management | Already used extensively in project |
| json | stdlib | JSON response serialization | Required for HLTH-03 |
| time | stdlib | uptime_seconds calculation | Already used in health_check.py |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| wanctl.__version__ | internal | Version reporting | HLTH-03 requires version field |
| wanctl.signal_utils | internal | Shutdown coordination | Clean shutdown integration |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| http.server.HTTPServer | ThreadingHTTPServer | More concurrent but overkill for health checks (single client: monitoring system) |
| Class-level handler state | Instance variables | Project pattern uses class-level; maintain consistency |

**Installation:**
```bash
# No installation needed - all stdlib
```

## Architecture Patterns

### Recommended Project Structure
```
src/wanctl/steering/
├── daemon.py           # Main steering daemon (existing)
├── health.py           # NEW: Health endpoint module
├── congestion_assessment.py
├── cake_stats.py
└── steering_confidence.py
```

### Pattern 1: Handler with Class-Level State
**What:** Use class attributes on BaseHTTPRequestHandler for shared state
**When to use:** Always - project established pattern
**Example:**
```python
# Source: src/wanctl/health_check.py (existing project pattern)
class HealthCheckHandler(BaseHTTPRequestHandler):
    # Class-level references set by start_health_server()
    daemon: "SteeringDaemon | None" = None
    start_time: float | None = None
    consecutive_failures: int = 0

    def log_message(self, format: str, *args: Any) -> None:
        """Suppress default HTTP logging to avoid log spam."""
        pass

    def do_GET(self) -> None:
        if self.path == "/health" or self.path == "/":
            health = self._get_health_status()
            status_code = 200 if health["status"] == "healthy" else 503
            self.send_response(status_code)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(health, indent=2).encode())
        else:
            self.send_response(404)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Not found"}).encode())
```

### Pattern 2: Server Wrapper with Clean Shutdown
**What:** Wrap HTTPServer + Thread in a class with shutdown() method
**When to use:** Always - enables clean lifecycle management
**Example:**
```python
# Source: src/wanctl/health_check.py (existing project pattern)
class HealthCheckServer:
    """Wrapper for HTTPServer with clean shutdown support."""

    def __init__(self, server: HTTPServer, thread: threading.Thread):
        self.server = server
        self.thread = thread

    def shutdown(self) -> None:
        """Cleanly shut down the health check server."""
        self.server.shutdown()
        self.thread.join(timeout=5.0)  # Prevent indefinite hang
```

### Pattern 3: Daemon Thread for Background Operation
**What:** Use daemon=True thread to avoid blocking main loop
**When to use:** Always for health servers (HLTH-05)
**Example:**
```python
# Source: src/wanctl/health_check.py
server = HTTPServer((host, port), HealthCheckHandler)
thread = threading.Thread(
    target=server.serve_forever,
    daemon=True,  # CRITICAL: Exits when main process exits
    name="steering-health"
)
thread.start()
```

### Anti-Patterns to Avoid
- **Using ThreadingHTTPServer without daemon threads:** Can prevent clean shutdown
- **Logging in handler without suppression:** Creates log spam from health probes
- **Forgetting join(timeout=) in shutdown:** Can hang forever if serve_forever wasn't called
- **Instance variables for shared state in handler:** New handler instance per request

## Don't Hand-Roll

Problems that look simple but have existing solutions:

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| HTTP server | Socket-level server | http.server.HTTPServer | Protocol handling, error handling |
| JSON responses | String concatenation | json.dumps() | Proper escaping, formatting |
| Thread lifecycle | Manual thread management | HealthCheckServer wrapper pattern | Clean shutdown, timeout handling |
| Shutdown coordination | Boolean flags | threading.Event via signal_utils | Thread-safe, deadlock-safe |

**Key insight:** The existing `health_check.py` solves all the HTTP server lifecycle problems. Reuse the pattern, don't reinvent.

## Common Pitfalls

### Pitfall 1: shutdown() Hangs Indefinitely
**What goes wrong:** Calling `server.shutdown()` hangs forever
**Why it happens:** shutdown() waits for serve_forever() to complete; if serve_forever() wasn't called or thread died, it waits forever
**How to avoid:** Always use `thread.join(timeout=5.0)` after shutdown()
**Warning signs:** Process won't exit on SIGTERM

### Pitfall 2: Handler Instances Per Request
**What goes wrong:** Storing state in handler instance (self.start_time) loses data between requests
**Why it happens:** BaseHTTPRequestHandler creates new instance per request
**How to avoid:** Use class-level attributes, set before server starts
**Warning signs:** uptime_seconds resets to 0 on each request

### Pitfall 3: Log Spam from Health Probes
**What goes wrong:** Access log fills with health check requests (every 10-30s from monitoring)
**Why it happens:** BaseHTTPRequestHandler.log_message() logs by default
**How to avoid:** Override log_message() to pass (suppress)
**Warning signs:** Log files grow rapidly with GET /health entries

### Pitfall 4: Port Already in Use on Restart
**What goes wrong:** OSError: Address already in use
**Why it happens:** Previous server didn't release socket (daemon thread killed before shutdown())
**How to avoid:** Use SO_REUSEADDR via `server.allow_reuse_address = True` (default in HTTPServer)
**Warning signs:** Service fails to restart after crash

### Pitfall 5: Non-Daemon Thread Blocks Exit
**What goes wrong:** Process hangs on shutdown waiting for health thread
**Why it happens:** Non-daemon threads must complete before process exits
**How to avoid:** Always set daemon=True on health server thread
**Warning signs:** SIGTERM doesn't stop the process

### Pitfall 6: JSON Serialization Errors
**What goes wrong:** TypeError when serializing health response
**Why it happens:** Non-serializable types in health dict (datetime, Path, custom objects)
**How to avoid:** Only use basic types (str, int, float, bool, list, dict, None)
**Warning signs:** 500 errors from health endpoint

## Code Examples

Verified patterns from existing project code:

### Complete Health Handler (Steering-Adapted)
```python
# Source: Adapted from src/wanctl/health_check.py
import json
import logging
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import TYPE_CHECKING, Any

from wanctl import __version__

if TYPE_CHECKING:
    from wanctl.steering.daemon import SteeringDaemon

logger = logging.getLogger(__name__)


class SteeringHealthHandler(BaseHTTPRequestHandler):
    """HTTP handler for steering daemon health endpoint."""

    # Class-level state - set by start_health_server()
    daemon: "SteeringDaemon | None" = None
    start_time: float | None = None
    consecutive_failures: int = 0

    def log_message(self, format: str, *args: Any) -> None:
        """Suppress default HTTP logging."""
        pass

    def do_GET(self) -> None:
        """Handle GET requests."""
        if self.path in ("/", "/health"):
            health = self._get_health_status()
            status_code = 200 if health["status"] == "healthy" else 503
            self.send_response(status_code)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(health, indent=2).encode())
        else:
            self.send_response(404)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Not found"}).encode())

    def _get_health_status(self) -> dict[str, Any]:
        """Build health status response."""
        uptime = time.monotonic() - self.start_time if self.start_time else 0
        is_healthy = self.consecutive_failures < 3
        return {
            "status": "healthy" if is_healthy else "degraded",
            "uptime_seconds": round(uptime, 1),
            "version": __version__,
        }
```

### Server Lifecycle Management
```python
# Source: Adapted from src/wanctl/health_check.py
class SteeringHealthServer:
    """Wrapper for HTTPServer with clean shutdown support."""

    def __init__(self, server: HTTPServer, thread: threading.Thread):
        self.server = server
        self.thread = thread

    def shutdown(self) -> None:
        """Cleanly shut down the health server."""
        self.server.shutdown()
        self.thread.join(timeout=5.0)


def start_steering_health_server(
    host: str = "127.0.0.1",
    port: int = 9102,
    daemon: "SteeringDaemon | None" = None,
) -> SteeringHealthServer:
    """Start health check HTTP server in background thread."""
    SteeringHealthHandler.daemon = daemon
    SteeringHealthHandler.start_time = time.monotonic()
    SteeringHealthHandler.consecutive_failures = 0

    server = HTTPServer((host, port), SteeringHealthHandler)
    thread = threading.Thread(
        target=server.serve_forever,
        daemon=True,
        name="steering-health"
    )
    thread.start()

    logger.info(f"Steering health server started on http://{host}:{port}/health")
    return SteeringHealthServer(server, thread)
```

### Integration with Daemon Main Loop
```python
# Source: Pattern from src/wanctl/autorate_continuous.py main()
health_server = None

# Start health server (non-fatal if fails)
try:
    health_server = start_steering_health_server(
        host=config.health_check_host,
        port=config.health_check_port,
        daemon=daemon,
    )
except OSError as e:
    logger.warning(f"Failed to start health server: {e}")

try:
    # Main daemon loop
    while not shutdown_event.is_set():
        success = daemon.run_cycle()
        if not success:
            consecutive_failures += 1
        else:
            consecutive_failures = 0
        # Update health endpoint
        SteeringHealthHandler.consecutive_failures = consecutive_failures
        # ... rest of loop
finally:
    if health_server:
        try:
            health_server.shutdown()
        except Exception as e:
            logger.debug(f"Error shutting down health server: {e}")
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| External frameworks (Flask) | stdlib http.server | Project decision | Zero external deps for health |
| Socket-level servers | HTTPServer | stdlib | Built-in protocol handling |

**Deprecated/outdated:**
- CGIHTTPRequestHandler: Security vulnerabilities, never use
- SimpleHTTPRequestHandler: File serving only, not for health APIs

## Open Questions

None. All technical questions resolved via existing project code patterns.

## Sources

### Primary (HIGH confidence)
- `src/wanctl/health_check.py` - Existing autorate health implementation (reference pattern)
- `src/wanctl/metrics.py` - Existing metrics server with same HTTPServer pattern
- `src/wanctl/steering/daemon.py` - Target daemon for integration
- `src/wanctl/signal_utils.py` - Shutdown coordination utilities
- [Python 3.12 http.server documentation](https://docs.python.org/3.12/library/http.server.html) - Official stdlib docs

### Secondary (MEDIUM confidence)
- [Python socketserver documentation](https://docs.python.org/3/library/socketserver.html) - ThreadingMixIn details
- [Python bug tracker - shutdown() hangs](https://bugs.python.org/issue12463) - Known issue with workaround

### Tertiary (LOW confidence)
- None needed - stdlib solution fully documented

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - stdlib only, project precedent exists
- Architecture: HIGH - mirrors existing health_check.py exactly
- Pitfalls: HIGH - documented from official sources and project experience

**Research date:** 2026-01-23
**Valid until:** 2026-07-23 (6 months - stdlib, stable patterns)
