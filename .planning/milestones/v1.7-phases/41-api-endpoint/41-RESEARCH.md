# Phase 41: API Endpoint - Research

**Researched:** 2026-01-25
**Domain:** HTTP endpoint on existing health server for metrics history queries
**Confidence:** HIGH

## Summary

This phase adds a `/metrics/history` endpoint to the existing autorate health server (port 9101). The domain is well-understood: extend the existing `HealthCheckHandler` to handle a new route with query parameter parsing. The codebase already has all supporting infrastructure in place.

Key findings:
- Extend existing `HealthCheckHandler` class in `health_check.py` - no new HTTP server needed
- Use `urllib.parse.parse_qs` for query parameter parsing (stdlib)
- Reuse `query_metrics()`, `compute_summary()`, `select_granularity()` from `storage/reader.py` (already implemented)
- Follow existing JSON response patterns from health endpoint
- Use ISO 8601 timestamps per CONTEXT.md decision (datetime.isoformat() already used in steering/health.py)

**Primary recommendation:** Add new route handling to existing `HealthCheckHandler.do_GET()`. Delegate all database logic to existing reader functions. No new dependencies required.

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| http.server | stdlib | HTTP request handling | Already used by health_check.py |
| urllib.parse | stdlib | Query parameter parsing (parse_qs) | Stdlib, no external deps |
| json | stdlib | JSON serialization | Already used by health_check.py |
| datetime | stdlib | ISO 8601 timestamp formatting | Already used in codebase |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| storage.reader | internal | query_metrics(), select_granularity(), compute_summary() | ALL database queries |
| storage.writer | internal | DEFAULT_DB_PATH constant | Database path reference |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| parse_qs | Manual parsing | parse_qs handles edge cases (encoding, duplicates) |
| Extending health_check.py | New file | Existing file already has the server setup, less duplication |

**Installation:**
```bash
# No new dependencies required - all stdlib + existing internal modules
```

## Architecture Patterns

### Recommended Project Structure
```
src/wanctl/
├── health_check.py      # MODIFY: add /metrics/history route
├── storage/
│   ├── reader.py        # REUSE: query_metrics(), compute_summary(), select_granularity()
│   └── writer.py        # REUSE: DEFAULT_DB_PATH
└── history.py           # REFERENCE: parse_duration(), parse_timestamp() for CLI
```

### Pattern 1: Route Handling in do_GET
**What:** Extend existing path matching to handle new endpoint
**When to use:** Adding new routes to existing health server
**Example:**
```python
# Source: Existing pattern in health_check.py
def do_GET(self) -> None:
    """Handle GET requests."""
    if self.path == "/health" or self.path == "/":
        # ... existing health handling
    elif self.path.startswith("/metrics/history"):
        self._handle_metrics_history()
    else:
        self.send_response(404)
        # ...
```

### Pattern 2: Query Parameter Parsing
**What:** Parse URL query parameters using urllib.parse
**When to use:** Extracting query params from request URL
**Example:**
```python
# Source: Python stdlib documentation
from urllib.parse import urlparse, parse_qs

def _handle_metrics_history(self) -> None:
    """Handle GET /metrics/history with query params."""
    parsed = urlparse(self.path)
    query = parse_qs(parsed.query)

    # Single-value params: get first value or default
    range_param = query.get("range", [""])[0]  # e.g., "1h"
    wan = query.get("wan", [None])[0]          # e.g., "spectrum"
    limit = int(query.get("limit", ["1000"])[0])
    offset = int(query.get("offset", ["0"])[0])

    # Multi-value params (comma-separated in single param)
    metrics_param = query.get("metrics", [""])[0]
    metrics = [m.strip() for m in metrics_param.split(",")] if metrics_param else None
```

### Pattern 3: Reusing Existing Reader Functions
**What:** Delegate database queries to existing reader module
**When to use:** All data access
**Example:**
```python
# Source: Existing pattern in history.py CLI
from wanctl.storage.reader import query_metrics, select_granularity, compute_summary

# Auto-select granularity based on time range
granularity = select_granularity(start_ts, end_ts)

# Query with filters
results = query_metrics(
    db_path=db_path,
    start_ts=start_ts,
    end_ts=end_ts,
    metrics=metrics_list,
    wan=wan,
    granularity=granularity,
)
```

### Pattern 4: ISO 8601 Timestamp Output
**What:** Convert Unix timestamps to ISO 8601 strings
**When to use:** All timestamp fields in response per CONTEXT.md decision
**Example:**
```python
# Source: steering/health.py pattern
from datetime import UTC, datetime

def _unix_to_iso8601(ts: int) -> str:
    """Convert Unix timestamp to ISO 8601 string."""
    return datetime.fromtimestamp(ts, tz=UTC).isoformat()

# Output: "2026-01-25T14:00:00+00:00"
```

### Pattern 5: JSON Response Pattern
**What:** Consistent JSON response structure with Content-Type header
**When to use:** All API responses
**Example:**
```python
# Source: Existing pattern in health_check.py
def _send_json_response(self, data: dict, status_code: int = 200) -> None:
    """Send JSON response with proper headers."""
    self.send_response(status_code)
    self.send_header("Content-Type", "application/json")
    self.end_headers()
    self.wfile.write(json.dumps(data, indent=2).encode())
```

### Anti-Patterns to Avoid
- **Duplicating reader logic:** NEVER rewrite query logic - use storage/reader.py functions
- **Creating new HTTP server:** Extend existing HealthCheckHandler, don't create new server
- **Hardcoding database path:** Use DEFAULT_DB_PATH from storage.writer
- **Returning raw Unix timestamps:** Convert to ISO 8601 per CONTEXT.md decision
- **Ignoring pagination:** Always apply limit/offset to prevent huge responses

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Time range parsing | Custom regex | Reuse parse_duration from history.py | Already tested |
| Metric querying | Raw SQL | query_metrics() from reader.py | Handles filters, read-only |
| Granularity selection | Fixed rules | select_granularity() from reader.py | Consistent with CLI |
| Summary stats | Manual percentiles | compute_summary() from reader.py | Already handles edge cases |
| Query parsing | Manual string split | urllib.parse.parse_qs | Handles encoding, edge cases |

**Key insight:** All database logic exists in storage/reader.py. This phase is thin HTTP glue.

## Common Pitfalls

### Pitfall 1: Missing Time Range Handling
**What goes wrong:** Query returns entire database (millions of rows)
**Why it happens:** No default time range when params missing
**How to avoid:** Default to last 1 hour when no range/from/to params
**Warning signs:** Slow responses, high memory usage

### Pitfall 2: Integer Parsing Errors
**What goes wrong:** ValueError crash when limit="abc"
**Why it happens:** No validation of numeric params
**How to avoid:** Wrap int() conversion in try/except, return 400 Bad Request
**Warning signs:** Uncaught exceptions in logs

### Pitfall 3: Pagination Overflow
**What goes wrong:** limit=1000000 returns massive response
**Why it happens:** No maximum limit enforcement
**How to avoid:** Cap limit at reasonable max (e.g., 10000), document in response
**Warning signs:** Memory errors, slow responses

### Pitfall 4: Missing Database
**What goes wrong:** 500 error when database doesn't exist
**Why it happens:** File not found not handled gracefully
**How to avoid:** query_metrics() already returns [] for missing DB - just return empty results
**Warning signs:** Crashes on fresh installs

### Pitfall 5: Time Zone Confusion
**What goes wrong:** ISO timestamps without timezone info
**Why it happens:** Using datetime.isoformat() without UTC
**How to avoid:** Always use datetime.fromtimestamp(ts, tz=UTC).isoformat()
**Warning signs:** Timestamps missing +00:00 suffix

## Code Examples

### Complete Route Handler Structure
```python
# Source: Pattern from health_check.py + history.py
from urllib.parse import urlparse, parse_qs
from datetime import UTC, datetime, timedelta

from wanctl.storage.reader import query_metrics, select_granularity
from wanctl.storage.writer import DEFAULT_DB_PATH

def _handle_metrics_history(self) -> None:
    """Handle GET /metrics/history endpoint."""
    try:
        params = self._parse_history_params()
    except ValueError as e:
        self._send_json_error(400, str(e))
        return

    # Determine time range
    start_ts, end_ts = self._resolve_time_range(params)

    # Auto-select granularity
    granularity = select_granularity(start_ts, end_ts)

    # Query metrics
    results = query_metrics(
        db_path=DEFAULT_DB_PATH,
        start_ts=start_ts,
        end_ts=end_ts,
        metrics=params.get("metrics"),
        wan=params.get("wan"),
        granularity=granularity,
    )

    # Apply pagination
    total_count = len(results)
    limit = params.get("limit", 1000)
    offset = params.get("offset", 0)
    results = results[offset:offset + limit]

    # Build response
    response = {
        "data": [self._format_metric(r) for r in results],
        "metadata": {
            "total_count": total_count,
            "returned_count": len(results),
            "granularity": granularity,
            "limit": limit,
            "offset": offset,
            "query": {
                "start": datetime.fromtimestamp(start_ts, tz=UTC).isoformat(),
                "end": datetime.fromtimestamp(end_ts, tz=UTC).isoformat(),
                "metrics": params.get("metrics"),
                "wan": params.get("wan"),
            }
        }
    }

    self._send_json_response(response)
```

### Parameter Parsing with Validation
```python
# Source: Adapted from history.py patterns
import re

def _parse_history_params(self) -> dict:
    """Parse and validate query parameters."""
    parsed = urlparse(self.path)
    query = parse_qs(parsed.query)

    params = {}

    # Time range: range (relative) or from/to (absolute)
    range_param = query.get("range", [""])[0]
    from_param = query.get("from", [""])[0]
    to_param = query.get("to", [""])[0]

    if range_param:
        params["range"] = self._parse_duration(range_param)
    if from_param:
        params["from"] = self._parse_iso_timestamp(from_param)
    if to_param:
        params["to"] = self._parse_iso_timestamp(to_param)

    # Metrics filter (comma-separated)
    metrics_param = query.get("metrics", [""])[0]
    if metrics_param:
        params["metrics"] = [m.strip() for m in metrics_param.split(",")]

    # WAN filter
    wan = query.get("wan", [None])[0]
    if wan:
        params["wan"] = wan

    # Pagination with validation
    try:
        limit = int(query.get("limit", ["1000"])[0])
        params["limit"] = min(limit, 10000)  # Cap at max
    except ValueError:
        raise ValueError("limit must be an integer")

    try:
        offset = int(query.get("offset", ["0"])[0])
        params["offset"] = max(offset, 0)
    except ValueError:
        raise ValueError("offset must be an integer")

    return params

def _parse_duration(self, value: str) -> timedelta:
    """Parse duration string like '1h', '30m', '7d'."""
    units = {"s": 1, "m": 60, "h": 3600, "d": 86400, "w": 604800}
    match = re.match(r"^(\d+)([smhdw])$", value.lower())
    if not match:
        raise ValueError(f"Invalid duration: '{value}'. Use format like 1h, 30m, 7d")
    return timedelta(seconds=int(match.group(1)) * units[match.group(2)])

def _parse_iso_timestamp(self, value: str) -> int:
    """Parse ISO 8601 timestamp to Unix seconds."""
    try:
        dt = datetime.fromisoformat(value)
        return int(dt.timestamp())
    except ValueError:
        raise ValueError(f"Invalid timestamp: '{value}'. Use ISO 8601 format")
```

### Error Response Pattern
```python
# Source: Pattern from health_check.py
def _send_json_error(self, status_code: int, message: str) -> None:
    """Send JSON error response."""
    self.send_response(status_code)
    self.send_header("Content-Type", "application/json")
    self.end_headers()
    error = {"error": message}
    self.wfile.write(json.dumps(error, indent=2).encode())
```

### Metric Formatting
```python
# Source: ISO 8601 pattern from steering/health.py
def _format_metric(self, row: dict) -> dict:
    """Format metric row with ISO 8601 timestamp."""
    return {
        "timestamp": datetime.fromtimestamp(row["timestamp"], tz=UTC).isoformat(),
        "wan_name": row["wan_name"],
        "metric_name": row["metric_name"],
        "value": row["value"],
        "labels": row.get("labels"),
        "granularity": row["granularity"],
    }
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Manual query parsing | urllib.parse.parse_qs | Always stdlib | Handles encoding |
| datetime.utcnow() | datetime.now(UTC) | Python 3.12+ | utcnow deprecated |
| strftime for ISO | isoformat() | Python 3.7+ | Proper ISO format |

**Deprecated/outdated:**
- datetime.utcnow() - deprecated in Python 3.12, use datetime.now(UTC) instead

## Open Questions

1. **Summary mode via query param**
   - What we know: CLI has --summary mode using compute_summary()
   - What's unclear: Whether to expose via API
   - Recommendation: Add optional `summary=true` param, return aggregated stats per metric

2. **Time zone in input parsing**
   - What we know: Output uses UTC (ISO 8601 with +00:00)
   - What's unclear: Should input timestamps assume UTC or local?
   - Recommendation: fromisoformat() handles timezones if present, assume UTC if missing

## Sources

### Primary (HIGH confidence)
- Existing health_check.py - server pattern and JSON response structure
- Existing storage/reader.py - query_metrics(), compute_summary(), select_granularity()
- Existing history.py - parse_duration(), timestamp parsing patterns
- Existing steering/health.py - ISO 8601 timestamp formatting
- Python urllib.parse documentation - parse_qs behavior

### Secondary (MEDIUM confidence)
- None - all patterns from existing codebase

### Tertiary (LOW confidence)
- None - fully verified from existing code

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - all stdlib + existing internal modules
- Architecture: HIGH - follows existing health_check.py pattern exactly
- Pitfalls: HIGH - based on existing codebase error handling patterns

**Research date:** 2026-01-25
**Valid until:** 2026-03-25 (60 days - stable, stdlib-based)

## Recommendations for Claude's Discretion Items

Based on research and existing codebase patterns:

| Item | Recommendation | Rationale |
|------|----------------|-----------|
| JSON structure | Flat array in `data` key with `metadata` object | Matches common REST patterns |
| Summary mode | Add `summary=true` query param | Consistent with CLI --summary |
| Response metadata | Include count, pagination, query params, granularity | Helps API consumers debug |
| Time range spec | Support both `range=1h` (relative) and `from`/`to` (ISO 8601) | Matches CLI flexibility |
| Default time range | Last 1 hour when no range params | Matches CLI default |
| Metrics filter format | Comma-separated in single param | Simple, common pattern |
| Auto-granularity | Yes, use select_granularity() | Prevents performance issues |
| Pagination style | Offset-based (limit + offset) | Simpler, sufficient for time-series |
| Default page size | 1000, max 10000 | Reasonable for monitoring use |
| Navigation links | No - just return offset/limit/total_count | Keep response simple |
| Error response format | `{"error": "message"}` | Matches existing 404 pattern |
| HTTP status for empty | 200 with empty data array | Empty is valid result |
| Missing database | 200 with empty data array | query_metrics() handles this |
