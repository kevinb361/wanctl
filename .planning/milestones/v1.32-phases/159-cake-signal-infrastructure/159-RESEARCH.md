# Phase 159: CAKE Signal Infrastructure - Research

**Researched:** 2026-04-09
**Domain:** Linux CAKE qdisc statistics via pyroute2 netlink, EWMA signal processing, per-tin metrics
**Confidence:** HIGH

## Summary

Phase 159 adds CAKE qdisc statistics reading to the autorate hot path (WANController.run_cycle), computes EWMA-smoothed drop rate from raw counters, separates per-tin stats (Bulk vs BestEffort+), and exposes everything via the health endpoint and metrics DB. Critically, this phase introduces NO behavior change -- signals are read, computed, and exposed but do not affect zone classification or rate decisions. That comes in Phase 160.

The codebase already has extensive infrastructure to support this: NetlinkCakeBackend.get_queue_stats() returns per-tin stats including drops, backlog, peak_delay, ecn_marked. The steering daemon already reads and stores per-tin metrics. The key work is (1) wiring stats reading into the autorate hot path, (2) computing EWMA drop rate with u32-safe delta math, (3) exposing via health endpoint, (4) adding YAML config with SIGUSR1 reload, and (5) keeping it under 1ms per direction.

**Primary recommendation:** Reuse the existing NetlinkCakeBackend.get_queue_stats() method directly from LinuxCakeAdapter's dl_backend/ul_backend -- no new netlink code needed. The u32 wrapping guard and EWMA computation are the only genuinely new algorithms.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| CAKE-01 | CAKE qdisc stats read every cycle via netlink <1ms/direction | NetlinkCakeBackend.get_queue_stats() already exists, returns full per-tin data via single tc("dump") call. Measured ~0.3ms per netlink call in Phase 154 benchmarking. |
| CAKE-02 | Drop rate as EWMA-smoothed drops/sec with u32-safe delta and cold-start warmup | Kernel drops counter is u32 (confirmed from sch_cake.c). Existing signal_processing.py has EWMA pattern with alpha = interval/time_constant. CakeStatsReader._calculate_stats_delta() shows existing delta pattern. |
| CAKE-03 | Per-tin stats tracked separately, Bulk drops distinguished from BestEffort+ | TIN_NAMES = ["Bulk", "BestEffort", "Video", "Voice"] (index 0=Bulk) already defined. Steering daemon already does per-tin metric storage. |
| CAKE-04 | CAKE signal metrics exposed via health endpoint and stored in metrics DB | Health endpoint has established pattern (get_health_data -> _build_wan_status). Metrics schema already has wanctl_cake_tin_* metrics. |
| CAKE-05 | All features independently toggleable via YAML config (default: disabled) | SIGUSR1 reload pattern well-established. reload() calls chain of _reload_*() methods. |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| pyroute2 | 0.9.5 | Netlink CAKE stats reading | Already installed, already used by NetlinkCakeBackend [VERIFIED: `pip show pyroute2` on dev machine] |
| Python stdlib | 3.12 | EWMA math, dataclasses, threading | No external deps needed for signal computation |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pytest | 8.0+ | Unit tests | Already in dev deps [VERIFIED: pyproject.toml] |
| pytest-xdist | 3.8+ | Parallel test execution | Already configured with `-n auto` [VERIFIED: pyproject.toml] |

**No new dependencies required.** All CAKE stats infrastructure uses existing pyroute2 and stdlib.

## Architecture Patterns

### Where CAKE Stats Fit in the Existing Architecture

```
autorate_continuous.py (ContinuousAutoRate)
  -> wan_controller.py (WANController.run_cycle)
     -> _run_rtt_measurement          # existing
     -> _run_signal_processing        # existing
     -> _run_spike_detection          # existing
     -> _run_congestion_assessment    # existing (Phase 160 changes here)
     -> _run_cake_stats               # NEW: read + compute between signal and logging
     -> _run_irtt_observation         # existing
     -> _run_logging_metrics          # existing (add CAKE metrics to batch)
     -> _run_router_communication     # existing
     -> _run_post_cycle               # existing
```

### Data Flow: CAKE Stats Through the System

```
NetlinkCakeBackend.get_queue_stats()   [0.3ms netlink call]
  -> raw per-tin dicts (drops, backlog_bytes, peak_delay_us, ...)
  -> CakeSignalProcessor.update()      [new module]
     -> u32 delta calculation with wrapping guard
     -> EWMA smoothing (drops/sec, backlog, peak_delay)
     -> tin separation (active_drop_rate excludes Bulk)
  -> CakeSignalSnapshot (frozen dataclass)
     -> consumed by health endpoint (get_health_data)
     -> consumed by metrics batch (DeferredIOWorker)
     -> consumed by Phase 160 (zone classification, NOT this phase)
```

### Recommended New Module Structure

```
src/wanctl/
  cake_signal.py          # NEW: CakeSignalProcessor + CakeSignalSnapshot + CakeSignalConfig
```

Single new module. Does NOT modify existing modules beyond:
- `wan_controller.py`: add _run_cake_stats(), wire into run_cycle, add to get_health_data()
- `autorate_config.py`: add cake_signal config parsing
- `health_check.py`: add _build_cake_signal_section()
- `storage/schema.py`: add new metric names (drop_rate, active_drop_rate, backlog, peak_delay)
- `interfaces.py`: (optional) add CakeSignalProvider protocol

### Pattern 1: CakeSignalProcessor (stateful per-WAN, per-direction)

**What:** Holds previous counter values, computes deltas, maintains EWMA state.
**When to use:** One instance per direction (download, upload) per WANController.

```python
# Source: based on existing signal_processing.py EWMA pattern
@dataclass(frozen=True, slots=True)
class CakeSignalSnapshot:
    """Per-cycle CAKE signal state (immutable, safe to pass to health endpoint)."""
    drop_rate: float          # EWMA drops/sec (all non-Bulk tins)
    total_drop_rate: float    # EWMA drops/sec (all tins including Bulk)
    backlog_bytes: int        # Current backlog (BestEffort+ tins sum)
    peak_delay_us: int        # Max peak_delay across BestEffort+ tins
    tins: tuple[TinSnapshot, ...]  # Per-tin breakdown
    cold_start: bool          # True until first valid delta computed

@dataclass(frozen=True, slots=True)
class TinSnapshot:
    """Per-tin statistics snapshot."""
    name: str
    dropped_packets: int      # Raw counter (cumulative)
    drop_delta: int           # Delta since last read
    backlog_bytes: int
    peak_delay_us: int
    ecn_marked_packets: int
```

### Pattern 2: u32 Delta With Wrapping Guard

**What:** Safe counter difference that handles u32 wrap-around.
**Critical detail:** CAKE's `dropped_packets` is u32 (max 4,294,967,295). At sustained 10k drops/sec (extreme), wraps in ~5 days. At realistic 100 drops/sec, wraps in ~497 days.

```python
# Source: Linux kernel sch_cake.c confirmed u32 for dropped_packets [VERIFIED: kernel source]
U32_MAX = 0xFFFFFFFF

def u32_delta(current: int, previous: int) -> int:
    """Compute delta between two u32 counters, handling wrap-around."""
    if current >= previous:
        return current - previous
    # Wrap-around: current < previous
    return (U32_MAX - previous) + current + 1
```

### Pattern 3: Cold Start Handling

**What:** First delta after startup is invalid (no previous reference). First-delta MUST be discarded.
**Why:** The existing CakeStatsReader._calculate_stats_delta() returns raw values on first read, which poisons EWMA. The new processor must explicitly track cold_start and suppress the first delta.

```python
class CakeSignalProcessor:
    def __init__(self, ...):
        self._prev_counters: dict[str, int] | None = None  # None = cold start
        self._cold_start = True
    
    def update(self, raw_stats: dict) -> CakeSignalSnapshot:
        if self._prev_counters is None:
            self._prev_counters = self._extract_counters(raw_stats)
            self._cold_start = True
            return CakeSignalSnapshot(cold_start=True, ...)
        
        deltas = self._compute_deltas(raw_stats)
        self._cold_start = False
        # Now compute EWMA from deltas...
```

### Pattern 4: EWMA Drop Rate (drops/sec)

**What:** Smoothed drop rate using same alpha = interval/time_constant pattern as signal_processing.py.
**Time constant:** Configurable, default ~1.0 sec (20 cycles at 50ms). Fast enough to respond to congestion, slow enough to filter DOCSIS jitter.

```python
# alpha = cycle_interval / time_constant = 0.05 / 1.0 = 0.05
# drop_rate_ewma = (1 - alpha) * prev + alpha * (drops_delta / cycle_interval)
drops_per_sec = drops_delta / CYCLE_INTERVAL_SECONDS  # 0.05
self._drop_rate_ewma = (1 - alpha) * self._drop_rate_ewma + alpha * drops_per_sec
```

### Pattern 5: YAML Config + SIGUSR1 Reload

**What:** Independent enable/disable for each CAKE signal sub-feature.
**Default:** All disabled (safe rollout, CAKE-05).

```yaml
# New YAML section in spectrum.yaml
cake_signal:
  enabled: false          # Master switch (CAKE-05)
  drop_rate:
    enabled: false        # EWMA drop rate computation
    time_constant_sec: 1.0
  backlog:
    enabled: false        # Backlog tracking
  peak_delay:
    enabled: false        # Peak delay tracking
  metrics:
    enabled: false        # Per-cycle metrics storage (can be noisy)
```

### Anti-Patterns to Avoid

- **Reading stats on a background thread:** IPRoute is NOT thread-safe (documented in STATE.md: "All netlink calls on main thread only"). Stats must be read in the run_cycle hot path, same as bandwidth changes. This is fine because netlink tc dump is ~0.3ms.
- **Creating a new IPRoute for stats:** Reuse the existing NetlinkCakeBackend._ipr singleton. Creating a second IPRoute wastes FDs and adds socket overhead.
- **Resetting counters instead of computing deltas:** Counter resets have race conditions (events between reset and read are lost). The existing codebase uses delta calculation -- follow this pattern.
- **Storing EWMA state in the snapshot dataclass:** Snapshots are frozen and passed to health/metrics. EWMA state is mutable and stays in CakeSignalProcessor.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Netlink stats reading | Custom netlink parsing | NetlinkCakeBackend.get_queue_stats() | Already written, tested, with per-tin parsing and fallback |
| EWMA smoothing | Custom filter | Copy pattern from signal_processing.py | Proven EWMA with time-constant-based alpha |
| Per-tin naming | Hardcoded strings | TIN_NAMES from linux_cake.py | Already defined: ["Bulk", "BestEffort", "Video", "Voice"] |
| Health endpoint sections | New HTTP handler | Extend existing HealthCheckHandler pattern | _build_*_section() pattern is well-established |
| Config reload | Manual YAML parsing | Follow _reload_*_config() SIGUSR1 pattern | Proven, tested, handles error cases |

**Key insight:** The hardest parts of this phase (netlink communication, per-tin parsing, metrics storage, health endpoint) are already built. The new work is glue: wiring existing infrastructure together with a thin CakeSignalProcessor layer.

## Common Pitfalls

### Pitfall 1: IPRoute Thread Safety
**What goes wrong:** Reading stats on background thread causes intermittent socket errors or corrupted responses.
**Why it happens:** pyroute2 IPRoute is not thread-safe. STATE.md explicitly says "All netlink calls on main thread only."
**How to avoid:** Call get_queue_stats() directly in run_cycle, between signal processing and congestion assessment. At 0.3ms per call, two calls (DL+UL) add only 0.6ms to the 30-40ms cycle.
**Warning signs:** Spurious NetlinkError in logs, FD count creeping up.

### Pitfall 2: u32 Overflow False Positive
**What goes wrong:** On counter wrap, delta becomes negative (or huge via unsigned interpretation), EWMA spikes.
**Why it happens:** CAKE drops counter is u32, wraps at 4,294,967,295.
**How to avoid:** Use u32_delta() guard. Also add sanity check: if delta > 1,000,000 (1M drops in one 50ms cycle is impossible), treat as wrap artifact and skip this sample.
**Warning signs:** Sudden spike in drop_rate_ewma followed by slow decay.

### Pitfall 3: Cold Start EWMA Poison
**What goes wrong:** First delta after startup is the entire cumulative counter value, not a real delta. EWMA starts extremely high and takes minutes to decay.
**Why it happens:** First read has no previous reference. The delta IS the cumulative total.
**How to avoid:** Track _cold_start flag. On first read, store counters but return snapshot with cold_start=True and zero rates. Only compute EWMA from second read onward.
**Warning signs:** drop_rate shows impossible value (millions/sec) after daemon restart.

### Pitfall 4: Accessing dl_backend/ul_backend From WANController
**What goes wrong:** WANController has self.router (LinuxCakeAdapter) but needs per-direction NetlinkCakeBackend access for get_queue_stats().
**Why it happens:** LinuxCakeAdapter wraps two backends but only exposes set_limits().
**How to avoid:** Access via router.dl_backend and router.ul_backend (already public attributes on LinuxCakeAdapter). Guard with `hasattr(self.router, 'dl_backend')` for RouterOS transport compatibility.
**Warning signs:** AttributeError on RouterOS transport deployment.

### Pitfall 5: Cycle Budget Blowout
**What goes wrong:** Adding 2 netlink calls pushes cycle time over 50ms budget.
**Why it happens:** Current utilization is 60-80% (30-40ms). Adding 0.6ms is marginal.
**How to avoid:** Wrap stats read in PerfTimer for profiling. Add to cycle_budget subsystem breakdown. If unexpectedly slow, log warning and skip CAKE stats that cycle.
**Warning signs:** overrun_count increasing, utilization_pct > 90%.

### Pitfall 6: Metrics Storage Noise
**What goes wrong:** Storing CAKE stats every 50ms cycle (20Hz) floods SQLite with data.
**Why it happens:** 4 metrics x 4 tins x 2 directions x 20Hz = 640 writes/sec.
**How to avoid:** Use DeferredIOWorker (already proven for SQLite offload). Consider storing aggregate (non-per-tin) CAKE metrics at 1Hz (every 20 cycles) instead of 20Hz. Per-tin detailed stats only in health endpoint, not metrics DB.
**Warning signs:** SQLite WAL file growing fast, maintenance VACUUM taking longer.

### Pitfall 7: Config-Only Transport Check
**What goes wrong:** CAKE stats code runs on RouterOS transport where get_queue_stats returns different format.
**Why it happens:** WANController doesn't check transport before accessing CAKE-specific features.
**How to avoid:** Gate all CAKE signal logic on `isinstance(self.router, LinuxCakeAdapter)` or a simple bool set at init. When on RouterOS transport, CAKE signal is silently disabled (no error, no warning -- CAKE stats don't exist on RouterOS queues in the same way).
**Warning signs:** AttributeError or nonsensical stats on RouterOS deployments.

## Code Examples

### Example 1: Reading Stats From Existing Backend

```python
# Source: NetlinkCakeBackend.get_queue_stats() already returns this format
# [VERIFIED: src/wanctl/backends/netlink_cake.py lines 191-292]
stats = self.router.dl_backend.get_queue_stats("")
# Returns:
# {
#     "packets": 184614358,
#     "bytes": 272603902153,
#     "dropped": 42,
#     "queued_packets": 5,
#     "queued_bytes": 7500,
#     "memory_used": 27700000,
#     "memory_limit": 67108864,
#     "capacity_estimate": 500000000,
#     "ecn_marked": 0,
#     "tins": [
#         {   # index 0 = Bulk
#             "sent_bytes": ..., "sent_packets": ...,
#             "dropped_packets": 10, "ecn_marked_packets": 0,
#             "backlog_bytes": 0, "peak_delay_us": 500,
#             "avg_delay_us": 100, "base_delay_us": 50,
#             "sparse_flows": 0, "bulk_flows": 2,
#             "unresponsive_flows": 0,
#         },
#         {   # index 1 = BestEffort
#             "dropped_packets": 32, ...
#         },
#         {   # index 2 = Video
#             ...
#         },
#         {   # index 3 = Voice
#             ...
#         },
#     ],
# }
```

### Example 2: SIGUSR1 Reload Pattern

```python
# Source: WANController._reload_hysteresis_config() [VERIFIED: wan_controller.py line 1392]
# Follow this exact pattern for CAKE signal config reload:
def _reload_cake_signal_config(self) -> None:
    """Re-read cake_signal config from YAML (triggered by SIGUSR1)."""
    try:
        with open(self.config.config_file) as f:
            data = yaml.safe_load(f)
        cake_signal = data.get("cake_signal", {})
        enabled = cake_signal.get("enabled", False)
        # Update processor config...
        self.logger.info(f"{self.wan_name}: CAKE signal config reloaded (enabled={enabled})")
    except Exception as e:
        self.logger.warning(f"{self.wan_name}: Failed to reload cake_signal config: {e}")
```

### Example 3: Health Endpoint Section Pattern

```python
# Source: HealthCheckHandler._build_rate_hysteresis_section() [VERIFIED: health_check.py line 271]
# Follow this pattern for CAKE signal section:
def _build_cake_signal_section(self, health_data: dict[str, Any]) -> dict[str, Any] | None:
    cake_data = health_data.get("cake_signal")
    if cake_data is None or not cake_data["enabled"]:
        return None
    dl_snap = cake_data["download"]
    ul_snap = cake_data["upload"]
    return {
        "download": {
            "drop_rate": round(dl_snap.drop_rate, 1),
            "total_drop_rate": round(dl_snap.total_drop_rate, 1),
            "backlog_bytes": dl_snap.backlog_bytes,
            "peak_delay_us": dl_snap.peak_delay_us,
            "cold_start": dl_snap.cold_start,
            "tins": [
                {"name": t.name, "drop_delta": t.drop_delta,
                 "backlog_bytes": t.backlog_bytes, "peak_delay_us": t.peak_delay_us}
                for t in dl_snap.tins
            ],
        },
        "upload": { ... },
    }
```

### Example 4: Metrics Batch Extension

```python
# Source: WANController._run_logging_metrics() [VERIFIED: wan_controller.py line 2098]
# Append CAKE signal metrics to existing batch:
if self._cake_signal_enabled and self._dl_cake_snapshot is not None:
    snap = self._dl_cake_snapshot
    metrics_batch.extend([
        (ts, self.wan_name, "wanctl_cake_drop_rate", snap.drop_rate,
         {"direction": "download"}, "raw"),
        (ts, self.wan_name, "wanctl_cake_active_drop_rate", snap.drop_rate,
         {"direction": "download"}, "raw"),
        (ts, self.wan_name, "wanctl_cake_backlog_bytes", float(snap.backlog_bytes),
         {"direction": "download"}, "raw"),
        (ts, self.wan_name, "wanctl_cake_peak_delay_us", float(snap.peak_delay_us),
         {"direction": "download"}, "raw"),
    ])
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Subprocess `tc -j -s qdisc show` | Netlink via pyroute2 IPRoute.tc("dump") | Phase 154 (v1.31) | 0.3ms vs 3.1ms per call |
| RouterOS queue stats via REST | LinuxCakeBackend local tc | Phase 121 (v1.21) | No network round-trip, full per-tin data |
| Steering reads CAKE stats separately | Autorate will read CAKE stats in hot path | Phase 159 (this) | CAKE signals available for zone classification |

**Deprecated/outdated:**
- RouterOS queue tree stats for CAKE: Only provides aggregate dropped count, no per-tin breakdown. Still used by steering daemon but not suitable for hot-path congestion detection.

## Kernel-Level Counter Details

Per-tin CAKE statistics from `sch_cake.c` [VERIFIED: Linux kernel source]:

| Attribute | Netlink Type | Notes |
|-----------|-------------|-------|
| TCA_CAKE_TIN_STATS_DROPPED_PACKETS | u32 | Wraps at 4,294,967,295. ~5 days at 10k/sec. |
| TCA_CAKE_TIN_STATS_SENT_PACKETS | u32 | Same wrap risk but less critical (not used for rate decisions). |
| TCA_CAKE_TIN_STATS_BACKLOG_BYTES | u32 | Instantaneous, no delta needed. |
| TCA_CAKE_TIN_STATS_PEAK_DELAY_US | u32 | Instantaneous. Resets each measurement interval (~100ms Cobalt). |
| TCA_CAKE_TIN_STATS_AVG_DELAY_US | u32 | Instantaneous. |
| TCA_CAKE_TIN_STATS_ECN_MARKED_PACKETS | u32 | Cumulative, same u32 wrap risk as drops. |
| TCA_CAKE_TIN_STATS_SENT_BYTES64 | u64 | No practical wrap risk. |
| TCA_CAKE_TIN_STATS_DROPPED_BYTES64 | u64 | No practical wrap risk. |

**Key finding:** `dropped_packets` is u32 (confirmed from `nla_put_u32` in `cake_dump_stats()`). The u32 wrapping guard is mandatory, not optional.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | EWMA time constant of 1.0 sec is appropriate for drop rate smoothing | Architecture Patterns | Too fast = noisy, too slow = misses congestion. Can be A/B tested in Phase 160. Low risk since configurable. |
| A2 | Storing CAKE metrics at 20Hz in the metrics batch is acceptable for SQLite throughput | Pitfalls | DeferredIOWorker handles it, but may need 1Hz downsampling. Verify with soak. |
| A3 | Peak delay resets each Cobalt interval (~100ms) so no delta needed | Kernel Counter Details | If peak_delay accumulates, would need delta treatment. CAKE docs confirm it's per-interval max. [CITED: https://www.bufferbloat.net/projects/codel/wiki/CakeTechnical/] |

## Open Questions

1. **Metric storage frequency**
   - What we know: Current metrics (RTT, rate, state) stored every cycle (20Hz). Per-tin stats from steering stored every cycle too.
   - What's unclear: Whether adding drop_rate + backlog + peak_delay per-direction at 20Hz is too much for SQLite.
   - Recommendation: Start with per-cycle storage via DeferredIOWorker (matching existing pattern). If SQLite grows too fast, add 1Hz decimation for CAKE metrics specifically.

2. **Where to store CakeSignalProcessor instances**
   - What we know: WANController has self.download and self.upload (QueueControllers). CAKE stats are per-direction.
   - What's unclear: Should processors live on WANController directly or on QueueController?
   - Recommendation: On WANController as self._dl_cake_signal and self._ul_cake_signal. QueueController is rate-only; CAKE signals are a separate concern consumed by the controller, not the queue.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.0+ with xdist parallel |
| Config file | pyproject.toml [tool.pytest.ini_options] |
| Quick run command | `.venv/bin/pytest tests/test_cake_signal.py -x` |
| Full suite command | `.venv/bin/pytest tests/ -v --timeout=2` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| CAKE-01 | Stats read every cycle via netlink <1ms | unit | `.venv/bin/pytest tests/test_cake_signal.py::TestCakeSignalProcessor -x` | Wave 0 |
| CAKE-02 | EWMA drop rate with u32 wrap and cold start | unit | `.venv/bin/pytest tests/test_cake_signal.py::TestDropRateEWMA -x` | Wave 0 |
| CAKE-03 | Per-tin separation (Bulk excluded from active rate) | unit | `.venv/bin/pytest tests/test_cake_signal.py::TestTinSeparation -x` | Wave 0 |
| CAKE-04 | Health endpoint + metrics DB exposure | unit | `.venv/bin/pytest tests/test_health_check.py tests/test_cake_signal.py -x` | Partial (health exists) |
| CAKE-05 | YAML config with independent enable/disable | unit | `.venv/bin/pytest tests/test_cake_signal.py::TestCakeSignalConfig -x` | Wave 0 |

### Sampling Rate
- **Per task commit:** `.venv/bin/pytest tests/test_cake_signal.py -x`
- **Per wave merge:** `.venv/bin/pytest tests/ -v --timeout=2`
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `tests/test_cake_signal.py` -- covers CAKE-01 through CAKE-05 (all new)
- [ ] No framework install needed (pytest already configured)

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | N/A (local netlink socket, no auth needed) |
| V3 Session Management | no | N/A |
| V4 Access Control | no | N/A (runs as root on cake-shaper VM for netlink) |
| V5 Input Validation | yes | Validate netlink response structure before parsing (MagicMock guard pattern) |
| V6 Cryptography | no | N/A |

### Known Threat Patterns

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Malformed netlink response | Tampering | isinstance/type checks before parsing, guard against None attrs |
| Integer overflow in delta math | Tampering | u32_delta() with explicit wrapping, sanity bounds on result |
| Config injection via YAML | Tampering | Existing YAML parsing with type validation, no eval() |

## Sources

### Primary (HIGH confidence)
- Linux kernel `sch_cake.c` -- per-tin stats types confirmed (u32 for drops, backlog; u64 for bytes) [VERIFIED: https://github.com/torvalds/linux/blob/master/net/sched/sch_cake.c]
- Linux kernel `pkt_sched.h` -- TCA_CAKE_TIN_STATS enum confirmed [VERIFIED: kernel header]
- Existing codebase `netlink_cake.py` -- get_queue_stats() with per-tin parsing [VERIFIED: src/wanctl/backends/netlink_cake.py]
- Existing codebase `signal_processing.py` -- EWMA pattern with time constants [VERIFIED: src/wanctl/signal_processing.py]
- Existing codebase `wan_controller.py` -- run_cycle structure, get_health_data, SIGUSR1 reload [VERIFIED: src/wanctl/wan_controller.py]
- Existing codebase `linux_cake.py` -- TIN_NAMES ["Bulk", "BestEffort", "Video", "Voice"] [VERIFIED: src/wanctl/backends/linux_cake.py:35]
- pyroute2 0.9.5 installed and working [VERIFIED: `.venv/bin/python -c "import pyroute2; print(pyroute2.__version__)"` returns 0.9.5]

### Secondary (MEDIUM confidence)
- [CAKE Technical Information](https://www.bufferbloat.net/projects/codel/wiki/CakeTechnical/) -- peak_delay_us behavior
- [pyroute2 CAKE stats PR](https://github.com/svinota/pyroute2/pull/662) -- stats_app decoder addition

### Tertiary (LOW confidence)
- None. All critical claims verified against kernel source or codebase.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- all libraries already in use, versions confirmed
- Architecture: HIGH -- extends well-established patterns in the codebase
- Pitfalls: HIGH -- derived from known codebase constraints (thread safety, u32 types, cold start)
- Kernel types: HIGH -- verified against kernel source sch_cake.c

**Research date:** 2026-04-09
**Valid until:** 2026-05-09 (stable domain, kernel ABI rarely changes)
