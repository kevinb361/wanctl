# Phase 40: CLI Tool - Context

**Gathered:** 2026-01-25
**Status:** Ready for planning

<domain>
## Phase Boundary

`wanctl-history` command for querying stored metrics from SQLite. Query by time range, filter by metric type, output as table or JSON, summary statistics mode. Requirements: CLI-01 through CLI-05.

</domain>

<decisions>
## Implementation Decisions

### Output Formatting
- Timestamps: Absolute format (2026-01-25 14:32:05) — precise, good for log correlation
- Default columns: Minimal (timestamp, metric, value) — compact, fits narrow terminals
- Number formatting: Adaptive precision — removes trailing zeros (25.5 ms, 850 Mbps)

### Time Range Interface
- Flexible timestamp parsing: Accept multiple formats including "2026-01-25 14:30", ISO 8601, etc.

### Error Handling
- No data in range: Empty table with message, exit 0 (informational, not an error)

### Claude's Discretion
- Verbose flag: Whether to add -v/--verbose for extra columns (wan, labels, granularity)
- Time units for --last: Which units to support (s, m, h, d, w)
- Default time range: What to query when no --last/--from/--to specified
- Auto-granularity: Whether to auto-select granularity based on time range
- Summary statistics: Which stats to include (min/max/avg/p50/p95/p99)
- Summary grouping: By metric name or by WAN + metric
- Summary metadata: Whether to show record count and time range
- State metric presentation: How to present wanctl_state in summary (percentages vs numeric)
- Database not found: Error message format and hints
- Invalid arguments: Error message style
- --db flag: Whether to support alternate database path

</decisions>

<specifics>
## Specific Ideas

No specific requirements — open to standard CLI patterns. User deferred most implementation details to Claude's discretion, indicating trust in following standard CLI conventions.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 40-cli-tool*
*Context gathered: 2026-01-25*
