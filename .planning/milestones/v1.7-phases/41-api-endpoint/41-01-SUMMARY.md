---
phase: 41-api-endpoint
plan: 01
subsystem: api
tags: [http, endpoint, metrics, json]
dependency-graph:
  requires: [38-storage, 39-recording, 40-cli]
  provides: [metrics-history-endpoint]
  affects: []
tech-stack:
  added: []
  patterns: [http-api, json-response, query-params]
key-files:
  created:
    - tests/test_health_check_history.py
  modified:
    - src/wanctl/health_check.py
decisions:
  - id: endpoint-route
    choice: "/metrics/history on existing port 9101"
    rationale: "Reuses autorate health server infrastructure"
  - id: pagination-method
    choice: "Python-side offset/limit (not SQL LIMIT)"
    rationale: "query_metrics() returns full result set; pagination in handler"
  - id: timestamp-format
    choice: "ISO 8601 with UTC timezone"
    rationale: "Standard format for API responses"
metrics:
  duration: "12 minutes"
  completed: "2026-01-25"
---

# Phase 41 Plan 01: HTTP Metrics History Endpoint Summary

HTTP API endpoint for programmatic access to stored metrics data via `/metrics/history`.

## Commits

| Hash    | Type | Description                                     |
| ------- | ---- | ----------------------------------------------- |
| 0f9d0fd | feat | Implement /metrics/history endpoint             |
| 9fff6f2 | test | Add 30 comprehensive tests for endpoint         |

## What Was Built

### /metrics/history Endpoint (src/wanctl/health_check.py)

**Route Handler:**
- `_handle_metrics_history()` - main handler for GET requests
- `_parse_history_params()` - parse and validate query string
- `_resolve_time_range()` - convert params to start/end timestamps
- `_format_metric()` - convert Unix timestamps to ISO 8601
- `_send_json_response()` / `_send_json_error()` - response helpers

**Query Parameters:**
| Param   | Type   | Description                        | Default |
| ------- | ------ | ---------------------------------- | ------- |
| range   | string | Relative duration (e.g., "1h")     | 1h      |
| from    | string | Start timestamp (ISO 8601)         | -       |
| to      | string | End timestamp (ISO 8601)           | now     |
| metrics | string | Comma-separated metric names       | all     |
| wan     | string | Filter by WAN name                 | all     |
| limit   | int    | Max results (1-10000)              | 1000    |
| offset  | int    | Skip first N results               | 0       |

**Response Structure:**
```json
{
  "data": [
    {
      "timestamp": "2026-01-25T18:30:00+00:00",
      "wan_name": "spectrum",
      "metric_name": "wanctl_rtt_ms",
      "value": 25.5,
      "labels": null,
      "granularity": "raw"
    }
  ],
  "metadata": {
    "total_count": 100,
    "returned_count": 50,
    "granularity": "raw",
    "limit": 50,
    "offset": 0,
    "query": {
      "start": "2026-01-25T17:30:00+00:00",
      "end": "2026-01-25T18:30:00+00:00",
      "metrics": null,
      "wan": null
    }
  }
}
```

### Test Coverage (tests/test_health_check_history.py)

**30 tests in 3 classes (520 lines):**

- **TestMetricsHistoryEndpoint** (12 tests): Integration tests with real server
  - Returns valid JSON
  - Default time range (1h)
  - Range param filtering
  - From/to absolute timestamps
  - Metrics and WAN filtering
  - Pagination (limit, offset)
  - Metadata structure
  - Empty results handling
  - ISO 8601 timestamp format

- **TestHistoryParamsValidation** (4 tests): Error handling
  - Invalid range format returns 400
  - Invalid limit/offset returns 400
  - Invalid timestamp returns 400

- **TestHistoryHelperMethods** (14 tests): Unit tests
  - Duration parsing (hours, minutes, days, weeks, seconds)
  - ISO timestamp parsing
  - Time range resolution
  - Metric formatting

## Verification Results

- All 41 health check tests pass (30 new + 11 existing)
- mypy type check passes
- Test file has 520 lines (exceeds 100 minimum)

## Deviations from Plan

None - plan executed exactly as written.

## Success Criteria Met

- [x] GET /metrics/history returns JSON with metrics data
- [x] Query params filter results (range, from, to, metrics, wan)
- [x] Pagination works (limit, offset params)
- [x] Invalid params return 400 with error message
- [x] Empty results return 200 with empty data array

## Next Phase Readiness

**Phase 41 complete.** v1.7 Metrics History milestone delivered:
- Phase 38: Storage layer (SQLite, schema, downsampling)
- Phase 39: Data recording (writer integration, steering metrics)
- Phase 40: CLI tool (wanctl-history command)
- Phase 41: HTTP API (this plan)

External tools and monitoring systems can now query metrics via:
```bash
curl "http://127.0.0.1:9101/metrics/history?range=1h&metrics=wanctl_rtt_ms"
```
