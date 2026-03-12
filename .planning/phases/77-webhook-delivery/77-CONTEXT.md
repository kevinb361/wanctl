# Phase 77: Webhook Delivery - Context

**Gathered:** 2026-03-12
**Status:** Ready for planning

<domain>
## Phase Boundary

Fired alerts reach the operator via Discord webhook with rich, color-coded embeds. The delivery layer is extensible so adding a new backend (e.g., ntfy.sh) requires only implementing a formatter class -- no engine changes. Requirements: DLVR-01, DLVR-02, DLVR-03, DLVR-04.

</domain>

<decisions>
## Implementation Decisions

### Embed appearance
- Bot display name: `wanctl`
- Title format: type-focused in Title Case (e.g., "Sustained Congestion", "Steering Activated")
- Severity emoji prefix in title: 🔴 critical, 🟡 warning, 🟢 recovery, 🔵 info
- Embed sidebar colors: red (#e74c3c) critical, yellow (#f39c12) warning, green (#2ecc71) recovery, blue (#3498db) info
- One-line summary description under the title (e.g., "Spectrum WAN has been in RED state for 5 minutes")
- Stacked fields (not inline): Severity, WAN, Timestamp, then metrics code block
- Metrics displayed in fenced code block with aligned labels and units:
  ```
  DL Rate:  245.0 Mbps
  UL Rate:   38.2 Mbps
  RTT:       42.3 ms
  ```
- Footer: "wanctl vX.Y.Z • cake-spectrum" (version + container identifier)
- Timestamp: Discord relative format (`<t:epoch:R>`) in a field, plus absolute UTC in footer
- WAN display names: Spectrum (capitalized), ATT (all-caps abbreviation exception)
- Alert type names: Title Case conversion from snake_case (congestion_sustained → "Sustained Congestion")
- Recovery alerts include duration context (e.g., "was RED for 5m, now GREEN")
- No thumbnail images -- emoji in title provides visual cue

### Discord mentions
- Configurable `mention_role_id` in alerting config (optional)
- Configurable `mention_severity` threshold (default: `critical`) -- when set to `warning`, both warning and critical alerts trigger @mention
- Mention text prepended outside the embed as `<@&role_id>` before the embed payload

### Alert batching
- Individual messages: one Discord message per alert, no batching
- Webhook rate limiter: configurable `max_webhooks_per_minute` (default 20, under Discord's 30/min limit)

### Failure handling
- Both log warning AND health endpoint counter for delivery failures
- New `delivery_status` column in SQLite `alerts` table: pending/delivered/failed
- Health endpoint exposes delivery failure count (details at Claude's discretion)

### Webhook URL handling
- Empty/missing webhook_url with alerting.enabled=true: warn at startup, engine runs (fires, persists, cools down) but delivery silently skipped
- URL validation: format-only (must start with `https://`)
- HTTPS only -- http:// URLs rejected
- webhook_url reloadable via SIGUSR1 (alongside dry_run and wan_state.enabled)
- Re-validation on SIGUSR1 reload (format check on new URL)

### Claude's Discretion
- Rate limiter drop behavior (log warning vs queue+retry)
- Health endpoint error detail level (count only vs count + last error message)
- Retry exhaustion strategy (mark failed vs retry queue with longer backoff)
- Formatter interface design (ABC, Protocol, or duck typing)
- Thread/async strategy for webhook delivery (must not block 50ms hot loop)
- Internal method signatures and delivery pipeline architecture

</decisions>

<specifics>
## Specific Ideas

- Follow the wan_state pattern: warn+disable on invalid config, never crash the daemon
- Reuse `retry_utils.py` patterns: `is_retryable_error()` already handles requests 5xx vs 4xx distinction
- Reuse `rate_utils.py` RateLimiter pattern for webhook rate limiting
- `requests` library already in use for router REST API -- use it for webhook delivery too
- SIGUSR1 reload already handles dry_run and wan_state.enabled -- extend to webhook_url
- Recovery embeds should feel informative: "Spectrum was in RED for 5m, now GREEN" with before/after metrics

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- `AlertEngine` in `alert_engine.py`: fire() returns True when alert fires -- delivery hook point after fire() returns True
- `retry_utils.py`: `retry_with_backoff` decorator and `is_retryable_error()` with requests 5xx/4xx distinction
- `RateLimiter` in `rate_utils.py`: Sliding window rate limiter -- model for webhook rate limiting
- `MetricsWriter` in `storage/writer.py`: Singleton with WAL mode -- hosts `alerts` table needing `delivery_status` column
- `requests` library: Already imported in `routeros_rest.py` for router REST API communication
- `signal_utils.py`: SIGUSR1 handler with threading.Event -- extend for webhook_url reload
- `config_validation_utils.py`: Validation helpers, warn+disable patterns

### Established Patterns
- **Warn+disable**: Invalid optional-feature config logs warning and disables feature (wan_state model)
- **SIGUSR1 reload**: Per-field reload methods in daemon, reads YAML independently
- **Never crash**: All optional feature errors caught and logged, daemon keeps running
- **Health endpoint sections**: Feature-gated dict additions to health response JSON
- **Retry with backoff**: Decorator pattern with jitter, max_delay cap, on_retry callback

### Integration Points
- `AlertEngine.fire()` returns True -- delivery call happens after successful fire
- Both daemon configs already parse `alerting:` section with `webhook_url` field
- Health endpoint needs new `delivery_failures` field in alerting section
- SQLite `alerts` table needs `delivery_status` column (schema migration)
- SIGUSR1 handler chain needs webhook_url reload method

</code_context>

<deferred>
## Deferred Ideas

None -- discussion stayed within phase scope

</deferred>

---

*Phase: 77-webhook-delivery*
*Context gathered: 2026-03-12*
