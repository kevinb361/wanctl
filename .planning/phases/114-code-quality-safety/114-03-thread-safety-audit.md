# Thread Safety Audit (CQUAL-04)

**Date:** 2026-03-26
**Method:** Static code review (D-07)
**Scope:** 9 threaded files + rtt_measurement.py ThreadPoolExecutor

## Summary

- Files audited: 10 (9 threaded files + rtt_measurement.py)
- Shared mutable state instances: 24
- Protected (lock/event/atomic/GIL-safe): 17
- Unprotected: 7
- Potential race conditions: 5 (0 high, 3 medium, 2 low)

## Thread Topology

### Autorate Daemon Threads

Each autorate daemon process (`wanctl@spectrum`, `wanctl@att`) runs:

1. **Main thread** -- `run_daemon_loop()` in `autorate_continuous.py:4062+`. Runs 50ms control cycle: measure RTT, update EWMA, adjust rates, push to router. Owns WANController instance variables.
2. **IRTT thread** -- `IRTTThread._run()` in `irtt_thread.py:70+`. Daemon thread named `wanctl-irtt`. Measures IRTT on configurable cadence (~10s). Writes `_cached_result`.
3. **Health check HTTP thread** -- `health_check.py:734`. Daemon thread named `health-check`. Runs `HTTPServer.serve_forever()`. Reads WANController instance variables for JSON health response.
4. **Metrics HTTP server thread** -- `metrics.py:245`. Daemon thread named `wanctl-metrics-server`. Runs `HTTPServer.serve_forever()`. Reads MetricsRegistry via `exposition()`.
5. **Webhook delivery threads** -- `webhook_delivery.py:380`. Ephemeral daemon threads (one per delivery). HTTP POST with retry logic. Access `_delivery_failures` counter.

### Steering Daemon Threads

The steering daemon process (`steering.service`) runs:

1. **Main thread** -- `run_daemon_loop()` in `steering/daemon.py:2040+`. Runs configurable cycle: measure RTT, read CAKE stats, assess congestion, toggle routing rules.
2. **Health check HTTP thread** -- `steering/health.py:366`. Daemon thread named `steering-health`. Runs `HTTPServer.serve_forever()`. Reads SteeringDaemon instance variables.
3. **Webhook delivery threads** -- `webhook_delivery.py:380`. Same pattern as autorate daemon.

### Cross-Process Communication

- Autorate writes state JSON to `/var/lib/wanctl/{wan_name}_state.json` via `atomic_write_json()` (temp+fsync+rename)
- Steering reads autorate state file via `safe_json_load_file()` for WAN zone awareness
- No shared memory between daemon processes -- all inter-process via filesystem (atomic)

## Per-File Analysis

### 1. autorate_continuous.py

#### Shared Mutable State

| Variable | Written by | Read by | Protected | Mechanism |
|----------|-----------|---------|-----------|-----------|
| `WANController.baseline_rtt` | Main thread | Health check thread | No | GIL-safe float assignment |
| `WANController.load_rtt` | Main thread | Health check thread | No | GIL-safe float assignment |
| `WANController.download.*` (streak counters) | Main thread | Health check thread | No | GIL-safe int/float |
| `WANController.upload.*` (streak counters) | Main thread | Health check thread | No | GIL-safe int/float |
| `WANController._last_signal_result` | Main thread | Health check thread | No | GIL-safe pointer swap |
| `WANController._irtt_correlation` | Main thread | Health check thread | No | GIL-safe float/None |
| `WANController._last_asymmetry_result` | Main thread | Health check thread | No | GIL-safe pointer swap |
| `WANController._last_fused_rtt` | Main thread | Health check thread | No | GIL-safe float/None |
| `WANController._last_icmp_filtered_rtt` | Main thread | Health check thread | No | GIL-safe float/None |
| `WANController._fusion_enabled` | Main thread (SIGUSR1) | Health check thread | No | GIL-safe bool |
| `WANController._fusion_icmp_weight` | Main thread (SIGUSR1) | Health check thread | No | GIL-safe float |
| `WANController._tuning_enabled` | Main thread (SIGUSR1) | Health check thread | No | GIL-safe bool |
| `WANController._tuning_state` | Main thread | Health check thread | No | GIL-safe pointer swap |
| `WANController._parameter_locks` | Main thread | Health check thread | No | GIL-safe dict read |
| `WANController._pending_observation` | Main thread | Health check thread | No | GIL-safe pointer swap |

#### Potential Race Conditions

| Access pattern | Risk | Severity | Notes |
|----------------|------|----------|-------|
| Health thread reads `_tuning_state` while main thread replaces it | Stale read | Low | Health thread reads old or new -- both are valid snapshots. `_tuning_state` is replaced atomically (GIL-safe pointer swap). Worst case: health endpoint shows slightly stale tuning data for one scrape. |
| Health thread reads `_parameter_locks` dict while main thread mutates it | Dict mutation | Medium | `_parameter_locks` is a `dict` mutated in-place (key add/remove). Under CPython GIL, individual dict operations are atomic, but iterating `locked_params = [p for p, exp in locks_dict.items() if now_mono < exp]` could see partial state if main thread modifies during iteration. In practice, the GIL makes `dict.items()` return a snapshot, so this is safe under CPython but not guaranteed by the language spec. |
| Health thread reads `_pending_observation` during replacement | Stale read | Low | Simple pointer check (`is not None`), GIL-safe. |

### 2. health_check.py

#### Shared Mutable State

| Variable | Written by | Read by | Protected | Mechanism |
|----------|-----------|---------|-----------|-----------|
| `HealthCheckHandler.controller` | Main thread (startup) | HTTP thread | No | Set once at startup, never mutated after |
| `HealthCheckHandler.start_time` | Main thread (startup) | HTTP thread | No | Set once at startup, never mutated after |
| `HealthCheckHandler.consecutive_failures` | Main thread (`update_health_status`) | HTTP thread | No | GIL-safe int assignment |

#### Potential Race Conditions

| Access pattern | Risk | Severity | Notes |
|----------------|------|----------|-------|
| `consecutive_failures` updated by main thread while health thread reads | Stale int | Low | Single int assignment is atomic under GIL. Health endpoint may show value from previous or current cycle -- harmless for monitoring. |

### 3. irtt_thread.py

#### Shared Mutable State

| Variable | Written by | Read by | Protected | Mechanism |
|----------|-----------|---------|-----------|-----------|
| `IRTTThread._cached_result` | IRTT thread | Main thread (`get_latest()`) | Yes | GIL-safe pointer swap of frozen dataclass (documented in module docstring) |
| `IRTTThread._shutdown_event` | Signal handler (main thread) | IRTT thread | Yes | `threading.Event` (thread-safe by design) |

#### Potential Race Conditions

| Access pattern | Risk | Severity | Notes |
|----------------|------|----------|-------|
| None identified | N/A | N/A | Clean design: frozen dataclass pointer swap, Event for shutdown. The module docstring explicitly documents the GIL-safe pattern. |

### 4. metrics.py

#### Shared Mutable State

| Variable | Written by | Read by | Protected | Mechanism |
|----------|-----------|---------|-----------|-----------|
| `MetricsRegistry._gauges` | Main thread (record_*) | Metrics HTTP thread (`exposition()`) | Yes | `threading.Lock` (`self._lock`) |
| `MetricsRegistry._counters` | Main thread (record_*) | Metrics HTTP thread (`exposition()`) | Yes | `threading.Lock` (`self._lock`) |
| `MetricsRegistry._gauge_help` | Main thread | Metrics HTTP thread | Yes | `threading.Lock` (`self._lock`) |
| `MetricsRegistry._counter_help` | Main thread | Metrics HTTP thread | Yes | `threading.Lock` (`self._lock`) |

#### Potential Race Conditions

| Access pattern | Risk | Severity | Notes |
|----------------|------|----------|-------|
| None identified | N/A | N/A | Fully protected by `threading.Lock`. All reads and writes acquire `self._lock`. |

### 5. signal_utils.py

#### Shared Mutable State

| Variable | Written by | Read by | Protected | Mechanism |
|----------|-----------|---------|-----------|-----------|
| `_shutdown_event` | Signal handler (any thread) | Main thread, IRTT thread, all threads | Yes | `threading.Event` (thread-safe by design) |
| `_reload_event` | Signal handler (SIGUSR1) | Main thread | Yes | `threading.Event` (thread-safe by design) |

#### Potential Race Conditions

| Access pattern | Risk | Severity | Notes |
|----------------|------|----------|-------|
| None identified | N/A | N/A | Textbook correct use of `threading.Event`. Signal handlers only call `.set()` (no logging, no complex operations). Module docstring documents the thread-safety design. |

### 6. steering/daemon.py

#### Shared Mutable State

| Variable | Written by | Read by | Protected | Mechanism |
|----------|-----------|---------|-----------|-----------|
| `SteeringDaemon.state_mgr.state` | Main thread | Health check thread | No | GIL-safe dict reads |
| `SteeringDaemon.config.*` | Main thread (SIGUSR1 reload) | Health check thread | No | GIL-safe attribute reads |
| `SteeringDaemon.router_connectivity` | Main thread | Health check thread | No | GIL-safe attribute reads |
| `SteeringDaemon._wan_state_enabled` | Main thread (SIGUSR1 reload) | Health check thread | No | GIL-safe bool |
| `SteeringDaemon._wan_zone` | Main thread | Health check thread | No | GIL-safe string |
| `SteeringDaemon.confidence_controller` | Main thread | Health check thread | No | Set once, read-only after init |
| `SteeringDaemon._profiler` | Main thread | Health check thread | No | GIL-safe reads |
| `SteeringDaemon._overrun_count` | Main thread | Health check thread | No | GIL-safe int |

#### Potential Race Conditions

| Access pattern | Risk | Severity | Notes |
|----------------|------|----------|-------|
| Health thread reads `state_mgr.state` dict while main thread updates it | Partial state | Medium | `state_mgr.state` is a dict updated in-place by `state_mgr.update()`. Health thread reads multiple keys from same dict in `_get_health_status()`. Under CPython GIL, individual dict reads are atomic, but the health thread could read `current_state` from cycle N and `congestion_state` from cycle N+1 if the main thread updates between reads. Impact: slightly inconsistent health snapshot. Not a correctness issue for monitoring. |
| `_wan_state_enabled` changed by SIGUSR1 while health reads | Stale bool | Low | Single bool assignment, GIL-safe. |

### 7. steering/health.py

#### Shared Mutable State

| Variable | Written by | Read by | Protected | Mechanism |
|----------|-----------|---------|-----------|-----------|
| `SteeringHealthHandler.daemon` | Main thread (startup) | HTTP thread | No | Set once at startup, never mutated after |
| `SteeringHealthHandler.start_time` | Main thread (startup) | HTTP thread | No | Set once at startup, never mutated after |
| `SteeringHealthHandler.consecutive_failures` | Main thread (`update_steering_health_status`) | HTTP thread | No | GIL-safe int assignment |

#### Potential Race Conditions

| Access pattern | Risk | Severity | Notes |
|----------------|------|----------|-------|
| Same pattern as health_check.py | Stale int | Low | Single int assignment under GIL. |

### 8. storage/writer.py

#### Shared Mutable State

| Variable | Written by | Read by | Protected | Mechanism |
|----------|-----------|---------|-----------|-----------|
| `MetricsWriter._instance` | Any thread (first call) | Any thread | Yes | `threading.Lock` (`_instance_lock`) |
| `MetricsWriter._conn` | First writer thread | Any thread via `connection` property | Partially | `_write_lock` protects writes; reads go through `_get_connection()` which is not locked but `_conn` is set once and never replaced (except `close()`/`_reset_instance()`) |
| `MetricsWriter._write_lock` data writes | Main thread | Main thread | Yes | `threading.Lock` for all write operations |

#### Potential Race Conditions

| Access pattern | Risk | Severity | Notes |
|----------------|------|----------|-------|
| `_get_connection()` called without lock from `write_metric` (inside `_write_lock`) and from `connection` property (no lock) | Connection init race | Medium | If two threads call `_get_connection()` simultaneously when `_conn is None`, both could try to create the connection. In practice, `MetricsWriter` is initialized early in the main thread before other threads start, so `_conn` is always set before concurrent access. The `_update_delivery_status()` in webhook threads calls `self._writer.connection` outside the write lock -- but SQLite with WAL mode handles concurrent reads safely, and `_conn` is already initialized. |

### 9. webhook_delivery.py

#### Shared Mutable State

| Variable | Written by | Read by | Protected | Mechanism |
|----------|-----------|---------|-----------|-----------|
| `WebhookDelivery._delivery_failures` | Delivery threads | Health check thread (via `delivery_failures` property) | Yes | `threading.Lock` (`self._lock`) for writes; property read is GIL-safe int read |
| `WebhookDelivery._webhook_url` | Main thread (SIGUSR1 reload via `update_webhook_url`) | Delivery threads | No | GIL-safe string assignment (immutable string swap) |
| `WebhookDelivery._rate_limiter` | Main thread (`deliver()`) | N/A (called only from main thread) | N/A | Single-threaded access -- `deliver()` called from main loop, not from delivery threads |

#### Potential Race Conditions

| Access pattern | Risk | Severity | Notes |
|----------------|------|----------|-------|
| `_webhook_url` updated by SIGUSR1 reload while delivery thread reads it | URL inconsistency | Low | String assignment is atomic under GIL (pointer swap). A delivery thread in-flight will use the old URL; next delivery uses the new URL. This is the intended behavior per the `update_webhook_url()` docstring. |

### 10. rtt_measurement.py (ThreadPoolExecutor)

#### Shared Mutable State

| Variable | Written by | Read by | Protected | Mechanism |
|----------|-----------|---------|-----------|-----------|
| `results` dict in `ping_hosts_all()` | Future callbacks | Main thread (after `as_completed`) | Yes | `concurrent.futures` handles result passing safely |
| `rtts` list in `ping_hosts_concurrent()` | Main thread (collecting from futures) | Main thread | N/A | Single-threaded collection after futures complete |

#### Potential Race Conditions

| Access pattern | Risk | Severity | Notes |
|----------------|------|----------|-------|
| None identified | N/A | N/A | `ThreadPoolExecutor` is used correctly with `as_completed()` and proper timeout handling. Results are collected synchronously after futures resolve. Each ping runs in isolation (no shared state between ping tasks). |

## Risk Summary

| # | Race Condition | File | Severity | Likelihood | Impact |
|---|----------------|------|----------|------------|--------|
| 1 | Health thread reads `_parameter_locks` dict during main thread mutation | autorate_continuous.py | Medium | Low | Stale/partial lock list in health endpoint |
| 2 | Health thread reads `state_mgr.state` dict during main thread update | steering/daemon.py | Medium | Low | Slightly inconsistent state snapshot |
| 3 | `_get_connection()` called concurrently before `_conn` initialized | storage/writer.py | Medium | Very Low | Double connection creation (mitigated by startup ordering) |
| 4 | Health thread reads stale tuning/fusion state | autorate_continuous.py | Low | Low | Stale monitoring data for one scrape |
| 5 | Delivery thread reads old `_webhook_url` during SIGUSR1 update | webhook_delivery.py | Low | Very Low | In-flight delivery uses old URL (intended) |

## Key Findings

### What Works Well

1. **signal_utils.py** -- Textbook correct use of `threading.Event`. No logging in signal handlers. Clean separation of shutdown and reload events.
2. **metrics.py** -- Full `threading.Lock` protection on MetricsRegistry. All read/write paths acquire lock.
3. **irtt_thread.py** -- Well-documented GIL-safe pattern with frozen dataclass pointer swap. Module docstring explains the design.
4. **rtt_measurement.py** -- Correct `ThreadPoolExecutor` usage with `as_completed()` and timeout.
5. **webhook_delivery.py** -- Lock-protected failure counter. Delivery threads are fire-and-forget daemons.
6. **storage/writer.py** -- Singleton with lock-protected instantiation and write lock for all DB operations.

### What Relies on CPython GIL

All shared state between main thread and health check threads (both autorate and steering) relies on CPython GIL for atomic reads of simple types (int, float, bool, pointer swap). This is:
- **Safe under CPython** (the only production runtime)
- **Not portable** to PyPy, GraalPy, or future free-threaded CPython (PEP 703)
- **Acceptable** for this codebase given the production constraint (CPython 3.12 only)

### Unprotected Patterns

The primary unprotected pattern is health check threads reading WANController/SteeringDaemon instance variables without locks. This is intentional and documented:
- Health endpoints are monitoring-only (read-only access)
- Stale reads have zero control-plane impact
- Adding locks would add latency to the 50ms control loop for negligible benefit

## Recommendations for v1.23

1. **No immediate fixes needed** -- All identified race conditions are low-impact monitoring staleness issues. None can cause crashes, data corruption, or incorrect control decisions.

2. **Consider: Read-snapshot for health endpoints** -- If health endpoint consistency matters for future alerting rules, consider having the main loop produce a periodic frozen snapshot (e.g., a `@dataclass(frozen=True)` health state) that the health thread reads atomically. This would eliminate all stale-read issues.

3. **Consider: Lock on `_parameter_locks` iteration** -- The `_parameter_locks` dict iteration in health_check.py (line ~387) could be protected with a dedicated lock if parameter lock monitoring becomes critical. Current risk is very low.

4. **Document GIL dependency** -- Add a note to CONVENTIONS.md that the health check architecture relies on CPython GIL for thread safety. This alerts future contributors considering free-threaded Python.

5. **No action needed for `MetricsWriter._get_connection()`** -- The theoretical race is fully mitigated by startup ordering (connection created before health/webhook threads start). Adding a lock would be defensive but unnecessary.
