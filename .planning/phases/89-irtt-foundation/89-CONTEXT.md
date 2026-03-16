# Phase 89: IRTT Foundation - Context

**Gathered:** 2026-03-16
**Status:** Ready for planning

<domain>
## Phase Boundary

IRTT binary is installed, wrapped, and configurable so that IRTT measurements can be invoked and parsed reliably. Delivers an IRTTMeasurement wrapper class, IRTTResult frozen dataclass, YAML config loading, Dockerfile update, and production container installation with live verification. Does NOT include background threading (Phase 90), daemon wiring (Phase 90), or SQLite persistence (Phase 92).

</domain>

<decisions>
## Implementation Decisions

### IRTT Invocation & Parsing
- Short burst measurement: `irtt client -o - --json -d {duration} -i {interval} -l 48 {server}:{port}`
- Default burst: 1s duration, 100ms interval (10 packets), 48-byte payload (hardcoded)
- Core params YAML-configurable: duration_sec and interval_ms. Payload size hardcoded.
- IRTT uses nanoseconds internally -- divide by 1_000_000 for milliseconds
- Extracted JSON fields: rtt_mean, rtt_median, ipdv_mean, send_loss, receive_loss, packets_sent, packets_received
- Field paths: stats.rtt.mean, stats.rtt.median, stats.ipdv.mean, stats.send_call.lost, stats.receive_call.lost (need live verification)
- IRTT server: 104.200.21.31:2112 (self-hosted Dallas, standard IRTT port)

### Result Data Model
- IRTTResult frozen dataclass (frozen=True, slots=True) -- same pattern as SignalResult
- Fields: rtt_mean_ms, rtt_median_ms, ipdv_mean_ms, send_loss, receive_loss, packets_sent, packets_received, server, port, timestamp (monotonic), success
- measure() returns IRTTResult | None -- None on any failure (binary missing, server unreachable, timeout, parse error)
- Matches RTTMeasurement.ping_host() pattern (returns value or None)

### IRTTMeasurement Class
- Class with measure() method, not module-level function -- follows RTTMeasurement pattern
- Constructor takes config dict + logger. Checks shutil.which("irtt") at init time.
- is_available() method returns whether binary exists AND config has enabled=True and server set
- Always instantiated even when disabled -- measure() returns None immediately (no-op pattern)
- Simplifies caller code: no conditional checks, just call measure()

### Fallback & Error Handling
- First failure logged at WARNING, subsequent identical failures at DEBUG (avoids log spam)
- Recovery logged at INFO with consecutive failure count
- Binary missing at startup: WARNING with apt install hint, measurements permanently disabled
- Subprocess timeout: duration_sec + 5 seconds grace period
- Track _consecutive_failures and _first_failure_logged for log level management and recovery messages
- Zero behavioral change on any failure (IRTT-05) -- controller continues with icmplib only

### YAML Configuration
- New `irtt:` section in autorate YAML config, disabled by default
- Config keys: enabled (bool, default false), server (str, default None), port (int, default 2112), duration_sec (float, default 1.0), interval_ms (int, default 100)
- Config loading follows _load_signal_processing_config() warn+default pattern
- Invalid config warns and falls back to defaults (never crashes)
- No SCHEMA entry needed -- warn+default handles validation internally

### Container Installation
- Dockerfile updated: add `irtt` to apt-get install line
- Manual install on existing containers: `sudo apt install -y irtt` on cake-spectrum and cake-att
- Live JSON output verification against Dallas IRTT server from both containers
- Server connectivity verified from both containers during phase execution
- If server unreachable: document as blocker for Phase 90, code still works (returns None)

### Claude's Discretion
- Internal method organization (_run_irtt, _parse_json, etc.)
- Exact IRTT command-line flag formatting
- Test fixture design and mock subprocess patterns
- JSON parsing error handling details beyond "return None"
- Whether to cache the shutil.which result or check each time

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Subprocess invocation pattern
- `src/wanctl/benchmark.py` -- subprocess.run() with shutil.which(), capture_output, timeout, graceful fallback (lines 301-306, 441-446, 353-361)

### RTT measurement interface
- `src/wanctl/rtt_measurement.py` -- RTTMeasurement class, ping_host() returns float|None, aggregation strategies

### Config loading pattern
- `src/wanctl/autorate_continuous.py` lines 633-704 -- _load_signal_processing_config() warn+default pattern (template for _load_irtt_config)
- `docs/CONFIG_SCHEMA.md` -- Configuration reference (add irtt section)

### Container installation
- `docker/Dockerfile` -- apt-get install line (add irtt)
- `scripts/install.sh` -- Installation script (may need irtt addition)

### Phase 88 context (prior decisions)
- `.planning/phases/88-signal-processing-core/88-CONTEXT.md` -- Signal processing architecture decisions, observation mode boundaries

### Requirements
- `.planning/REQUIREMENTS.md` -- IRTT-01, IRTT-04, IRTT-05, IRTT-08

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `benchmark.py` subprocess pattern: shutil.which() binary check, subprocess.run() with capture_output/text/timeout, TimeoutExpired handling -- direct template for IRTT invocation
- RTTMeasurement class structure: constructor with config, measure method returning typed result or None
- _load_signal_processing_config() in autorate_continuous.py: exact config loading pattern for irtt section

### Established Patterns
- Frozen dataclass (slots=True) for measurement results (SignalResult in signal_processing.py)
- warn+default config validation (never crash on invalid YAML)
- shutil.which() for binary availability checks
- subprocess.run() with capture_output=True, text=True, explicit timeout
- None return for failed measurements (RTTMeasurement.ping_host pattern)

### Integration Points
- autorate_continuous.py Config class: add _load_irtt_config() method following signal_processing pattern
- WANController.__init__(): instantiate IRTTMeasurement (Phase 90 will add background thread)
- docker/Dockerfile: add irtt to apt-get install line
- docs/CONFIG_SCHEMA.md: add irtt section documentation

</code_context>

<specifics>
## Specific Ideas

- IRTT JSON field names documented from man pages but STATE.md flags them as needing live verification -- Phase 89 resolves this by running test measurements against Dallas server
- The no-op instantiation pattern (always create, return None when disabled) is specifically chosen to simplify Phase 90 integration -- the background thread doesn't need conditional creation logic
- Consecutive failure tracking is designed for Phase 92 health endpoint consumption (server status field)
- First-failure-WARNING/repeat-at-DEBUG logging pattern prevents operator alert fatigue while ensuring first occurrence is visible

</specifics>

<deferred>
## Deferred Ideas

None -- discussion stayed within phase scope

</deferred>

---

*Phase: 89-irtt-foundation*
*Context gathered: 2026-03-16*
