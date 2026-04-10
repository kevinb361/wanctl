# Phase 94: OWD Asymmetric Detection - Context

**Gathered:** 2026-03-17
**Status:** Ready for planning

<domain>
## Phase Boundary

Distinguish upstream-only from downstream-only congestion using IRTT burst-internal send_delay vs receive_delay. Exposes a directional congestion attribute for downstream consumers (Phase 96 fusion). Persists direction and magnitude to SQLite for trend analysis. This phase does NOT change congestion control logic or state transitions -- it adds analysis on top of existing IRTT measurements.

</domain>

<decisions>
## Implementation Decisions

### Asymmetry threshold
- Divergence measured as **ratio** of send_delay_median / receive_delay_median (scale-independent)
- Default threshold **2.0x** -- one direction must be at least 2x the other to declare asymmetry
- Threshold is **YAML-configurable** (e.g., `owd_asymmetry.ratio_threshold: 2.0`)
- Uses **median** of burst delays (robust to outlier packets within a single burst)

### Direction semantics
- **4 named states**: `"upstream"`, `"downstream"`, `"symmetric"`, `"unknown"` (string enum)
- `"upstream"`: send_delay / receive_delay >= ratio_threshold (send is dominant)
- `"downstream"`: receive_delay / send_delay >= ratio_threshold (receive is dominant)
- `"symmetric"`: ratio is within threshold range (both directions similar, even if both elevated)
- `"unknown"`: IRTT unavailable, disabled, or measurement stale -- data availability issue, NOT measurement ambiguity
- **Ratio magnitude** stored as a separate float field alongside the string direction
- Direction + ratio available together for health endpoint, logging, and SQLite

### Persistence model
- **Per-measurement burst** writes (one row per IRTT measurement, every ~10s)
- **Extend existing IRTT metrics table** with direction and ratio columns -- zero additional write I/O
- Enables rich trend analysis ("show me the last hour of asymmetry ratios")
- Follows existing IRTT metrics persistence pattern from v1.18

### Health endpoint
- **Extend existing `irtt` health section** with `asymmetry_direction` and `asymmetry_ratio` fields
- No new top-level section -- asymmetry is a property of the IRTT measurement
- When IRTT unavailable: direction = "unknown", ratio omitted or null

### Logging
- **INFO on direction transitions only** (e.g., symmetric->upstream)
- No per-burst log spam
- Consistent with reflector quality WARNING/INFO transition pattern

### Claude's Discretion
- Whether to add send_delay/receive_delay to IRTTResult or compute asymmetry externally
- Internal class/module structure for the asymmetry analyzer
- How to handle edge cases: both delays near zero, one delay zero, divide-by-zero guard
- IRTT JSON field names for send_delay/receive_delay parsing
- Whether ratio is send/receive or max/min (semantic consistency)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### IRTT measurement infrastructure
- `src/wanctl/irtt_measurement.py` -- IRTTMeasurement class and IRTTResult frozen dataclass; must extend to parse send_delay and receive_delay from IRTT JSON `stats` section
- `src/wanctl/irtt_thread.py` -- IRTTThread with lock-free caching; asymmetry analysis reads from cached IRTTResult

### Health endpoint
- `src/wanctl/health_check.py` -- Autorate health endpoint; extend existing `irtt` section with asymmetry_direction and asymmetry_ratio fields

### SQLite persistence
- `src/wanctl/storage/schema.py` -- Schema definitions; extend IRTT metrics table with direction and ratio columns
- `src/wanctl/autorate_continuous.py` -- IRTT metrics write path; add direction/ratio to existing INSERT

### Configuration
- `src/wanctl/autorate_continuous.py` -- IRTT config loading pattern (`_load_irtt_config()`); model for OWD asymmetry config

### Prior art (patterns to follow)
- `src/wanctl/signal_processing.py` -- SignalProcessor pattern for stateful analysis with frozen dataclass results
- `src/wanctl/reflector_scorer.py` -- Event draining pattern, transition logging pattern

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `IRTTResult`: Frozen dataclass that needs send_delay_median_ms and receive_delay_median_ms fields added
- `IRTTThread.get_latest()`: Lock-free cache read returns latest IRTTResult -- asymmetry analyzer reads from this
- `_parse_json()`: IRTT JSON parser that already extracts rtt, ipdv, and loss -- extend for send_delay/receive_delay
- IRTT metrics write path in autorate_continuous.py -- extend existing INSERT with direction/ratio columns

### Established Patterns
- **Frozen dataclass results**: IRTTResult, SignalResult, ReflectorStatus -- use for asymmetry result
- **Lock-free caching**: GIL pointer swap for thread-safe reads (IRTTThread)
- **Always-present health sections**: `available: true/false` with `reason` field
- **IRTT write deduplication**: `_last_irtt_write_ts` prevents per-cycle row duplication (Phase 92)
- **Transition logging**: INFO on state change, DEBUG on every measurement (reflector_scorer pattern)

### Integration Points
- `WANController.run_cycle()`: Where asymmetry analysis would be triggered after IRTT measurement read
- `_build_irtt_health()` or equivalent in health_check.py: Where asymmetry fields are added to IRTT section
- `MetricsWriter` / existing IRTT write path: Where direction/ratio columns are added

</code_context>

<specifics>
## Specific Ideas

No specific requirements -- open to standard approaches

</specifics>

<deferred>
## Deferred Ideas

None -- discussion stayed within phase scope

</deferred>

---

*Phase: 94-owd-asymmetric-detection*
*Context gathered: 2026-03-17*
