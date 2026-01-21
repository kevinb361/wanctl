---
path: /home/kevin/projects/wanctl/src/wanctl/health_check.py
type: api
updated: 2026-01-21
status: active
---

# health_check.py

## Purpose

HTTP health endpoint for monitoring wanctl daemon status. Exposes JSON on port 9101 with uptime, version, consecutive failures, and per-WAN state (RTT baseline/load, current rates, state machine position). Designed for Kubernetes liveness/readiness probes and external monitoring tools.

## Exports

- `HealthCheckHandler(BaseHTTPRequestHandler)` - HTTP request handler
- `HealthCheckServer` - Threaded HTTP server wrapper
- `start_health_server(host, port, controller)` - Factory to start health endpoint
- `update_health_status(failures)` - Update failure counter from main loop

## Dependencies

- http.server - Built-in HTTP server
- [[src-wanctl-__init__]] - Version string
- TYPE_CHECKING: [[src-wanctl-autorate_continuous]] - Controller type hints

## Used By

- [[src-wanctl-autorate_continuous]] - Starts health server at daemon init
- External monitoring (curl, Prometheus)
