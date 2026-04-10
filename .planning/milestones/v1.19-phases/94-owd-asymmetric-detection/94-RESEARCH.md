# Phase 94: OWD Asymmetric Detection - Research

**Researched:** 2026-03-17
**Domain:** One-way delay asymmetry detection from IRTT burst measurements
**Confidence:** HIGH

## Summary

This phase adds directional congestion detection by analyzing the difference between IRTT send_delay and receive_delay within each measurement burst. The IRTT JSON output already includes `stats.send_delay` and `stats.receive_delay` as duration stats objects with `median` fields (in nanoseconds), and the current `irtt client` command uses `--tstamp both` by default, so no command-line changes are needed.

The implementation extends four existing components: (1) `IRTTResult` frozen dataclass gains two new float fields, (2) `_parse_json()` extracts `send_delay.median` and `receive_delay.median` from IRTT JSON, (3) a new `AsymmetryAnalyzer` class computes direction from the ratio, and (4) existing IRTT metrics write path and health endpoint gain direction/ratio columns. No new tables, no new threads, no new dependencies. The phase follows established patterns from SignalProcessor (frozen dataclass results), ReflectorScorer (transition logging), and IRTT metrics persistence (dedup via timestamp comparison).

**Primary recommendation:** Extend IRTTResult with send_delay_median_ms and receive_delay_median_ms, create a small AsymmetryAnalyzer class that computes direction + ratio from those fields, wire into WANController.run_cycle() alongside existing IRTT observation block, add two metrics to existing IRTT batch write, and extend IRTT health section with asymmetry_direction + asymmetry_ratio.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Divergence measured as **ratio** of send_delay_median / receive_delay_median (scale-independent)
- Default threshold **2.0x** -- one direction must be at least 2x the other to declare asymmetry
- Threshold is **YAML-configurable** (e.g., `owd_asymmetry.ratio_threshold: 2.0`)
- Uses **median** of burst delays (robust to outlier packets within a single burst)
- **4 named states**: `"upstream"`, `"downstream"`, `"symmetric"`, `"unknown"` (string enum)
- `"upstream"`: send_delay / receive_delay >= ratio_threshold (send is dominant)
- `"downstream"`: receive_delay / send_delay >= ratio_threshold (receive is dominant)
- `"symmetric"`: ratio is within threshold range (both directions similar)
- `"unknown"`: IRTT unavailable, disabled, or measurement stale
- **Ratio magnitude** stored as separate float field alongside direction string
- **Per-measurement burst** writes (one row per IRTT measurement, every ~10s)
- **Extend existing IRTT metrics table** with direction and ratio columns -- zero additional write I/O
- **Extend existing `irtt` health section** with `asymmetry_direction` and `asymmetry_ratio` fields
- **INFO on direction transitions only** (no per-burst log spam)

### Claude's Discretion
- Whether to add send_delay/receive_delay to IRTTResult or compute asymmetry externally
- Internal class/module structure for the asymmetry analyzer
- How to handle edge cases: both delays near zero, one delay zero, divide-by-zero guard
- IRTT JSON field names for send_delay/receive_delay parsing
- Whether ratio is send/receive or max/min (semantic consistency)

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| ASYM-01 | Upstream vs downstream congestion detected from IRTT send_delay vs receive_delay within same burst | IRTTResult extended with send_delay_median_ms/receive_delay_median_ms; AsymmetryAnalyzer computes direction from ratio; IRTT JSON confirmed to contain stats.send_delay.median and stats.receive_delay.median in nanoseconds |
| ASYM-02 | Asymmetric congestion direction available as named attribute for downstream consumers | AsymmetryResult frozen dataclass with direction (str) and ratio (float); stored on WANController for health endpoint and Phase 96 fusion access |
| ASYM-03 | Asymmetric congestion persisted in SQLite for trend analysis | Two new metrics (wanctl_irtt_asymmetry_direction, wanctl_irtt_asymmetry_ratio) added to existing IRTT metrics batch write, deduped by _last_irtt_write_ts |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python stdlib dataclasses | 3.12 | Frozen AsymmetryResult dataclass | Project pattern (IRTTResult, SignalResult, ReflectorStatus) |
| Python stdlib statistics | 3.12 | Not needed (IRTT computes median) | Computation happens in IRTT binary |
| Python stdlib logging | 3.12 | Transition logging | Project pattern |

### Supporting
No new dependencies. Everything builds on existing infrastructure.

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Separate asymmetry module | Inline in autorate_continuous | Module is cleaner, testable independently, consistent with SignalProcessor/ReflectorScorer pattern |
| New SQLite table | Extend metrics table rows | Extending existing IRTT batch write has zero additional I/O overhead |
| Computed ratio (max/min) | Directional ratio (send/receive) | Directional ratio preserves which direction is dominant; max/min loses direction info |

## Architecture Patterns

### Recommended Project Structure
```
src/wanctl/
    irtt_measurement.py      # MODIFY: Add send_delay_median_ms, receive_delay_median_ms to IRTTResult + _parse_json()
    asymmetry_analyzer.py    # NEW: AsymmetryAnalyzer class + AsymmetryResult frozen dataclass
    autorate_continuous.py   # MODIFY: Wire analyzer, add config loading, extend IRTT metrics write
    health_check.py          # MODIFY: Add asymmetry_direction + asymmetry_ratio to IRTT section
    storage/schema.py        # MODIFY: Add two new STORED_METRICS entries
tests/
    test_asymmetry_analyzer.py    # NEW: Unit tests for analyzer
    test_irtt_measurement.py      # MODIFY: Update SAMPLE_IRTT_JSON, test new fields
    test_asymmetry_health.py      # NEW or extend test_health_check.py: asymmetry in health endpoint
    test_asymmetry_config.py      # NEW: Config validation tests
    test_asymmetry_persistence.py # NEW: Metrics write tests
```

### Pattern 1: AsymmetryResult Frozen Dataclass
**What:** Immutable result object following IRTTResult/SignalResult pattern.
**When to use:** Every time asymmetry is computed from an IRTT measurement.
**Example:**
```python
# Source: project pattern from irtt_measurement.py, signal_processing.py
@dataclass(frozen=True, slots=True)
class AsymmetryResult:
    """Directional congestion detection result from IRTT OWD analysis."""
    direction: str       # "upstream", "downstream", "symmetric", "unknown"
    ratio: float         # max(send/receive, receive/send) -- always >= 1.0
    send_delay_ms: float # send_delay_median_ms from IRTTResult
    receive_delay_ms: float  # receive_delay_median_ms from IRTTResult
```

### Pattern 2: AsymmetryAnalyzer Stateful Class
**What:** Lightweight class that holds config (threshold) and last-known direction for transition logging.
**When to use:** Called once per IRTT measurement result (every ~10s), not per cycle.
**Example:**
```python
# Source: project pattern from reflector_scorer.py (transition logging)
class AsymmetryAnalyzer:
    def __init__(self, ratio_threshold: float = 2.0, logger=None, wan_name=""):
        self._threshold = ratio_threshold
        self._last_direction: str = "unknown"
        self._logger = logger
        self._wan_name = wan_name

    def analyze(self, irtt_result: IRTTResult) -> AsymmetryResult:
        """Compute asymmetry direction from IRTT send/receive delay medians."""
        send = irtt_result.send_delay_median_ms
        receive = irtt_result.receive_delay_median_ms

        # Edge case: both near zero or missing
        if send <= 0 and receive <= 0:
            return AsymmetryResult("unknown", 0.0, send, receive)

        # Divide-by-zero guard
        if receive <= 0:
            direction = "upstream"
            ratio = float('inf')
        elif send <= 0:
            direction = "downstream"
            ratio = float('inf')
        else:
            send_ratio = send / receive
            recv_ratio = receive / send
            if send_ratio >= self._threshold:
                direction = "upstream"
                ratio = send_ratio
            elif recv_ratio >= self._threshold:
                direction = "downstream"
                ratio = recv_ratio
            else:
                direction = "symmetric"
                ratio = max(send_ratio, recv_ratio)

        # Transition logging (INFO on change, DEBUG otherwise)
        if direction != self._last_direction:
            self._logger.info(
                f"{self._wan_name}: Asymmetry transition {self._last_direction} -> {direction} "
                f"(ratio={ratio:.2f})"
            )
            self._last_direction = direction

        return AsymmetryResult(direction, ratio, send, receive)
```

### Pattern 3: IRTTResult Extension
**What:** Add two new fields to the existing frozen dataclass for OWD medians.
**When to use:** Every IRTT measurement parse.
**Example:**
```python
# Source: irtt_measurement.py (extend existing dataclass)
@dataclass(frozen=True, slots=True)
class IRTTResult:
    # ... existing fields ...
    send_delay_median_ms: float    # NEW: stats.send_delay.median / NS_TO_MS
    receive_delay_median_ms: float # NEW: stats.receive_delay.median / NS_TO_MS
```

### Pattern 4: Extend Existing IRTT Metrics Write
**What:** Add direction encoding and ratio to the existing IRTT metrics batch.
**When to use:** Same dedup guard as existing IRTT metrics (timestamp comparison).
**Example:**
```python
# Source: autorate_continuous.py lines 2161-2168 (existing pattern)
if irtt_result is not None and irtt_result.timestamp != self._last_irtt_write_ts:
    metrics_batch.extend([
        (ts, self.wan_name, "wanctl_irtt_rtt_ms", irtt_result.rtt_mean_ms, None, "raw"),
        # ... existing IRTT metrics ...
        # NEW: asymmetry metrics (only when analyzer has result)
        (ts, self.wan_name, "wanctl_irtt_asymmetry_ratio", asym_result.ratio, None, "raw"),
        (ts, self.wan_name, "wanctl_irtt_asymmetry_direction",
         float(_encode_direction(asym_result.direction)), None, "raw"),
    ])
    self._last_irtt_write_ts = irtt_result.timestamp
```

### Anti-Patterns to Avoid
- **Computing asymmetry every 50ms cycle:** Asymmetry only changes when a new IRTT result arrives (~10s cadence). Compute only when `irtt_result.timestamp != self._last_irtt_write_ts`.
- **Using absolute OWD values for congestion detection:** Without NTP sync, absolute values are meaningless. Only the ratio/divergence within a single burst is meaningful.
- **Storing direction as string in SQLite metrics:** The existing metrics table stores `value REAL`. Encode direction as float (0=unknown, 1=symmetric, 2=upstream, 3=downstream).
- **New SQLite table for asymmetry:** Use existing metrics rows. The phase requirement says "extend existing IRTT metrics table" not "create new table."
- **Logging every measurement:** Only log direction transitions at INFO. Per-burst data at DEBUG.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| OWD median calculation | Compute from per-packet round_trips | Use stats.send_delay.median from IRTT JSON | IRTT already computes it; parsing round_trips array would add complexity and risk |
| Direction state tracking | Ad-hoc previous-state comparison | AsymmetryAnalyzer class with _last_direction | Encapsulates transition detection, testable in isolation |
| Metrics deduplication | New timestamp tracking field | Existing _last_irtt_write_ts guard | Already prevents per-cycle duplicate writes for IRTT metrics |
| Direction string validation | Manual string comparison | Constant set or string enum | Prevent typos in direction values |

**Key insight:** IRTT already computes send/receive delay medians and includes them in JSON output. The implementation is primarily about parsing, computing a ratio, and wiring into existing persistence/health patterns.

## Common Pitfalls

### Pitfall 1: send_delay/receive_delay Missing from IRTT JSON
**What goes wrong:** IRTT only includes send_delay and receive_delay when server timestamps are enabled. If the IRTT server is configured with `--tstamp none`, these fields will be absent.
**Why it happens:** Server-side configuration controls whether timestamps are collected. The client's `--tstamp both` default only *requests* timestamps; the server decides.
**How to avoid:** Use `.get()` with 0 default when extracting send_delay/receive_delay from JSON. When both are 0, the analyzer returns direction="unknown". Log at DEBUG when fields are missing.
**Warning signs:** direction is always "unknown" in production despite IRTT being enabled and healthy.

### Pitfall 2: Divide-by-Zero on receive_delay=0 or send_delay=0
**What goes wrong:** Division by zero when computing send/receive ratio.
**Why it happens:** Zero delay can occur with 100% packet loss in one direction, server timestamps disabled, or very short bursts.
**How to avoid:** Guard both denominators. If both are zero, return "unknown". If only one is zero and the other is positive, the non-zero direction is dominant (but use a capped ratio rather than infinity).
**Warning signs:** ZeroDivisionError in logs.

### Pitfall 3: NTP Clock Offset Polluting OWD Values
**What goes wrong:** Absolute send_delay and receive_delay values are wrong because client/server clocks are not synchronized.
**Why it happens:** IRTT documentation explicitly states OWD requires clock sync. In LXC containers, NTP sync may not be precise.
**How to avoid:** Use the **ratio** of send_delay to receive_delay, not absolute values. Within a single burst, clock offset affects both directions equally (constant offset cancels in the ratio). This is exactly why the user chose ratio-based detection.
**Warning signs:** send_delay always much larger or smaller than receive_delay even under no load -- this is expected with clock offset and does NOT affect the ratio's usefulness for detecting *changes* in asymmetry.

### Pitfall 4: Breaking Existing Tests by Adding Fields to IRTTResult
**What goes wrong:** All existing test code that constructs IRTTResult will fail because the frozen dataclass now requires two additional positional arguments.
**Why it happens:** IRTTResult has `slots=True` and all fields are positional in the dataclass constructor.
**How to avoid:** Add new fields with defaults: `send_delay_median_ms: float = 0.0` and `receive_delay_median_ms: float = 0.0`. This preserves backward compatibility with all existing test constructors. Update SAMPLE_IRTT_JSON in test_irtt_measurement.py to include send_delay/receive_delay.
**Warning signs:** Mass test failures when running existing test suite.

### Pitfall 5: MagicMock Truthy Trap on _asymmetry_analyzer
**What goes wrong:** MagicMock is truthy, so `if self._asymmetry_analyzer:` passes when it shouldn't.
**Why it happens:** Tests that mock WANController may not set _asymmetry_analyzer to None explicitly.
**How to avoid:** Set `_asymmetry_analyzer = None` explicitly on mock WANController objects, same as existing pattern for `_irtt_thread`, `_irtt_correlation`, `_last_signal_result`.
**Warning signs:** AttributeError in test assertions when mock doesn't have expected methods.

### Pitfall 6: Direction Encoding/Decoding Mismatch
**What goes wrong:** SQLite stores direction as REAL (float), but health endpoint and consumers expect string. If encoding/decoding maps don't match, "upstream" becomes "downstream" silently.
**Why it happens:** Separate encode/decode functions without shared constants.
**How to avoid:** Define direction constants and encoding map in one place (asymmetry_analyzer.py). Use a single `DIRECTION_ENCODING` dict for both encode and decode.
**Warning signs:** Health endpoint shows "symmetric" but SQLite history shows the "upstream" encoding value.

## Code Examples

### IRTT JSON send_delay/receive_delay Structure (Verified)
```json
{
  "stats": {
    "rtt": {"mean": 37500000, "median": 36000000, "min": ..., "max": ...},
    "send_delay": {"mean": 18000000, "median": 17500000, "min": ..., "max": ..., "n": 10},
    "receive_delay": {"mean": 19500000, "median": 18500000, "min": ..., "max": ..., "n": 10},
    "ipdv_round_trip": {"mean": 2000000},
    "upstream_loss_percent": 0.0,
    "downstream_loss_percent": 0.0,
    "packets_sent": 10,
    "packets_received": 10
  }
}
```
Source: [IRTT man page](https://www.mankier.com/1/irtt-client), verified stats.send_delay and stats.receive_delay are duration stats objects containing median field.

### Extending _parse_json() in irtt_measurement.py
```python
# Source: irtt_measurement.py _parse_json() -- existing pattern for rtt extraction
def _parse_json(self, raw_json: str) -> IRTTResult | None:
    # ... existing parsing ...
    rtt = stats.get("rtt", {})
    ipdv_rt = stats.get("ipdv_round_trip", {})
    send_delay = stats.get("send_delay", {})     # NEW
    receive_delay = stats.get("receive_delay", {})  # NEW

    return IRTTResult(
        rtt_mean_ms=rtt.get("mean", 0) / NS_TO_MS,
        rtt_median_ms=rtt.get("median", 0) / NS_TO_MS,
        ipdv_mean_ms=ipdv_rt.get("mean", 0) / NS_TO_MS,
        send_loss=stats.get("upstream_loss_percent", 0.0),
        receive_loss=stats.get("downstream_loss_percent", 0.0),
        packets_sent=stats.get("packets_sent", 0),
        packets_received=stats.get("packets_received", 0),
        server=self._server,
        port=self._port,
        timestamp=time.monotonic(),
        success=True,
        send_delay_median_ms=send_delay.get("median", 0) / NS_TO_MS,      # NEW
        receive_delay_median_ms=receive_delay.get("median", 0) / NS_TO_MS, # NEW
    )
```

### IRTT Health Endpoint Extension
```python
# Source: health_check.py -- extend existing IRTT section (lines 226-241)
wan_health["irtt"] = {
    "available": True,
    "rtt_mean_ms": round(irtt_result.rtt_mean_ms, 2),
    # ... existing fields ...
    "protocol_correlation": ...,
    # NEW asymmetry fields
    "asymmetry_direction": asym_result.direction if asym_result else "unknown",
    "asymmetry_ratio": round(asym_result.ratio, 2) if asym_result else None,
}
```

### Config Loading Pattern
```python
# Source: autorate_continuous.py _load_irtt_config() pattern
def _load_owd_asymmetry_config(self) -> None:
    owd = self.data.get("owd_asymmetry", {})
    if not isinstance(owd, dict):
        logger.warning(f"owd_asymmetry config must be dict; using defaults")
        owd = {}
    ratio_threshold = owd.get("ratio_threshold", 2.0)
    if not isinstance(ratio_threshold, (int, float)) or ratio_threshold < 1.0:
        logger.warning(f"owd_asymmetry.ratio_threshold must be >= 1.0; defaulting to 2.0")
        ratio_threshold = 2.0
    self.owd_asymmetry_config = {"ratio_threshold": float(ratio_threshold)}
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| RTT-only congestion detection | RTT + IRTT correlation (v1.18) | 2026-03-17 | Added UDP measurement, protocol comparison |
| Symmetric congestion assumption | Directional detection via OWD ratio (this phase) | 2026-03-17 | Can distinguish upload vs download congestion |
| NTP-dependent OWD | Ratio-based (NTP-independent) | Design decision | Works without clock sync; deferred NTP to v1.20 OWD-01/OWD-02 |

**Deprecated/outdated:**
- NTP-synchronized OWD: Explicitly deferred to v1.20 per REQUIREMENTS.md. This phase uses ratio-based detection which is NTP-independent.

## Open Questions

1. **Ratio semantics: send/receive vs max/min**
   - What we know: User wants direction-specific ratio (send/receive for upstream, receive/send for downstream).
   - What's unclear: Should the stored `ratio` always be the "dominant" direction's ratio (always >= 1.0), or the raw send/receive ratio (which could be < 1.0)?
   - Recommendation: Store as max(send/receive, receive/send) so ratio is always >= 1.0 and comparable across directions. The direction string indicates which side is dominant. This is simpler for threshold comparison and trend analysis.

2. **Edge case: both delays near zero but non-zero**
   - What we know: With very short bursts or fast networks, both delays could be sub-millisecond.
   - What's unclear: At what threshold do we consider values "too small to be meaningful"?
   - Recommendation: Use a minimum delay threshold (e.g., 0.1ms). If both delays are below this, report "symmetric" rather than amplifying noise with ratios of tiny numbers. Make this threshold internal (not user-configurable) to keep config simple.

3. **What happens when send_delay is present but receive_delay is absent (or vice versa)?**
   - What we know: Both are conditional on `--tstamp` server settings. Typically both present or both absent.
   - What's unclear: Can one be present without the other?
   - Recommendation: If either is missing (not in JSON), set to 0.0 via `.get("median", 0)`. Analyzer treats single-zero as dominant in the other direction, but with a minimum threshold guard this becomes "unknown."

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.0.2 |
| Config file | pyproject.toml |
| Quick run command | `.venv/bin/pytest tests/test_asymmetry_analyzer.py -x` |
| Full suite command | `.venv/bin/pytest tests/ -v` |

### Phase Requirements to Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| ASYM-01 | IRTTResult contains send_delay/receive_delay; analyzer computes direction from ratio | unit | `.venv/bin/pytest tests/test_asymmetry_analyzer.py tests/test_irtt_measurement.py -x` | No -- Wave 0 |
| ASYM-02 | AsymmetryResult direction accessible on WANController; exposed in health endpoint | unit | `.venv/bin/pytest tests/test_asymmetry_health.py -x` | No -- Wave 0 |
| ASYM-03 | Direction+ratio metrics written to SQLite with IRTT dedup | unit | `.venv/bin/pytest tests/test_asymmetry_persistence.py -x` | No -- Wave 0 |

### Sampling Rate
- **Per task commit:** `.venv/bin/pytest tests/test_asymmetry_analyzer.py tests/test_irtt_measurement.py -x`
- **Per wave merge:** `.venv/bin/pytest tests/ -v`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_asymmetry_analyzer.py` -- covers ASYM-01 (direction computation, thresholds, edge cases, transition logging)
- [ ] `tests/test_asymmetry_health.py` -- covers ASYM-02 (health endpoint asymmetry fields, unknown when IRTT unavailable)
- [ ] `tests/test_asymmetry_persistence.py` -- covers ASYM-03 (metrics batch includes direction/ratio, dedup guard)
- [ ] `tests/test_asymmetry_config.py` -- covers config validation (ratio_threshold bounds, warn+default)
- [ ] Update `tests/test_irtt_measurement.py` -- SAMPLE_IRTT_JSON needs send_delay/receive_delay, test new IRTTResult fields

## Sources

### Primary (HIGH confidence)
- [IRTT man page (mankier.com)](https://www.mankier.com/1/irtt-client) -- confirmed stats.send_delay and stats.receive_delay are duration stats objects with median field, conditional on server timestamps
- [IRTT GitHub (heistp/irtt)](https://github.com/heistp/irtt) -- verified tstamp default is "both", values in nanoseconds
- IRTT result.go source -- confirmed DurationStats includes median computation via setMedian()
- Project source: `src/wanctl/irtt_measurement.py` -- existing _parse_json() pattern, IRTTResult dataclass
- Project source: `src/wanctl/autorate_continuous.py` -- IRTT metrics write path (lines 2161-2168), config loading pattern
- Project source: `src/wanctl/health_check.py` -- IRTT health section (lines 203-241)
- Project source: `src/wanctl/signal_processing.py` -- SignalResult frozen dataclass pattern
- Project source: `src/wanctl/reflector_scorer.py` -- transition logging pattern, drain_events pattern

### Secondary (MEDIUM confidence)
- [IRTT Debian man page](https://manpages.debian.org/testing/irtt/irtt-client.1.en.html) -- corroborates field structure

### Tertiary (LOW confidence)
- None

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- no new dependencies, extends existing infrastructure
- Architecture: HIGH -- follows established project patterns (IRTTResult, SignalProcessor, ReflectorScorer)
- IRTT JSON fields: HIGH -- verified via man page AND source code that stats.send_delay.median exists
- Pitfalls: HIGH -- derived from actual codebase analysis (frozen dataclass defaults, MagicMock trap, dedup guard)

**Research date:** 2026-03-17
**Valid until:** 2026-04-17 (stable domain -- IRTT protocol and project patterns are well-established)
