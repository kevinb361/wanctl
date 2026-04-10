# Phase 160: Congestion Detection - Research

**Researched:** 2026-04-10
**Domain:** CAKE signal integration into autorate zone classification and rate control
**Confidence:** HIGH

## Summary

Phase 160 integrates the CAKE signal infrastructure built in Phase 159 (CakeSignalProcessor, CakeSignalSnapshot) into the rate control decision logic in `wan_controller.py` and `queue_controller.py`. The four requirements map to four distinct behaviors: (1) drop rate above threshold bypasses the dwell timer to confirm congestion immediately (DETECT-01), (2) backlog above threshold suppresses green_streak to prevent premature recovery (DETECT-02), (3) a refractory period after drop-triggered rate reductions prevents feedback oscillation (DETECT-03), and (4) only BestEffort+ tin drops drive decisions, excluding Bulk (DETECT-04).

The existing CakeSignalProcessor already computes EWMA-smoothed `drop_rate` (excluding Bulk) and `backlog_bytes` (excluding Bulk) per cycle. The snapshot is stored on `WANController._dl_cake_snapshot` and `_ul_cake_snapshot`. The key work is: (a) extending `QueueController` to accept CAKE signals as optional inputs to zone classification and rate computation, (b) adding threshold-based logic to bypass dwell and suppress green_streak, (c) implementing a refractory counter on WANController to prevent oscillation, and (d) extending the YAML config with detection thresholds while keeping everything disabled by default.

**Primary recommendation:** Add CAKE signal inputs to `QueueController.adjust_4state()` and `QueueController.adjust()` via an optional `CakeSignalSnapshot` parameter, keeping the methods backward-compatible. All new behavior is gated behind `CakeSignalConfig.drop_rate_enabled` and `CakeSignalConfig.backlog_enabled` flags (already defined in Phase 159, currently unused). No new modules needed -- extend existing ones.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| DETECT-01 | Drop rate above threshold bypasses dwell timer to confirm congestion immediately | CakeSignalSnapshot.drop_rate already computed (excludes Bulk). Dwell timer lives in QueueController._apply_dwell_logic(). When drop_rate exceeds threshold, skip dwell accumulation and return "YELLOW" immediately. |
| DETECT-02 | Queue backlog above threshold suppresses green_streak to prevent premature rate recovery | CakeSignalSnapshot.backlog_bytes already computed (excludes Bulk). green_streak incremented in _classify_zone_3state() and _classify_zone_4state(). When backlog exceeds threshold, reset green_streak to 0 even if zone is GREEN. |
| DETECT-03 | Refractory period prevents feedback loop oscillation after drop-triggered rate reduction | New counter on WANController: _refractory_cycles_remaining. Set to N cycles after any drop-triggered dwell bypass. While active, suppress drop-bypass and backlog-suppression to let the rate reduction take effect. |
| DETECT-04 | Only BestEffort and higher-priority tin drops drive rate decisions (Bulk tin drops excluded) | Already implemented by CakeSignalProcessor -- drop_rate field excludes Bulk (index 0), only sums BestEffort+Video+Voice. No additional code needed; just use snapshot.drop_rate (not total_drop_rate). |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python stdlib | 3.12 | Threshold comparisons, refractory counter | No external deps needed [VERIFIED: existing codebase pattern] |
| wanctl.cake_signal | local | CakeSignalSnapshot, CakeSignalConfig | Phase 159 output, already in codebase [VERIFIED: src/wanctl/cake_signal.py] |
| wanctl.queue_controller | local | Zone classification, dwell timer, green_streak | Existing 353-line module [VERIFIED: src/wanctl/queue_controller.py] |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pytest | 8.0+ | Unit tests | Already in dev deps [VERIFIED: pyproject.toml] |
| pytest-xdist | 3.8+ | Parallel test execution | Already configured [VERIFIED: pyproject.toml] |

**No new dependencies required.** Phase 160 is pure logic integration -- no new libraries.

## Architecture Patterns

### Integration Points in the Control Loop

```
run_cycle():
  _run_rtt_measurement()
  _run_signal_processing()
  _run_spike_detection()
  _run_cake_stats()              # Phase 159: reads snapshots
  _run_congestion_assessment()   # Phase 160: PASSES snapshots to QueueController
     -> download.adjust_4state(..., cake_snapshot=self._dl_cake_snapshot)
     -> upload.adjust(..., cake_snapshot=self._ul_cake_snapshot)
  _run_irtt_observation()
  _run_logging_metrics()         # Phase 160: adds refractory state to metrics
  _run_router_communication()
  _run_post_cycle()
```

Note: `_run_cake_stats()` already runs BEFORE `_run_congestion_assessment()` in the cycle. The snapshots are available on `self._dl_cake_snapshot` and `self._ul_cake_snapshot` at congestion assessment time. [VERIFIED: wan_controller.py lines 1924-1928]

### Pattern 1: Drop Rate Dwell Bypass (DETECT-01)

**What:** When EWMA drop rate exceeds a configurable threshold, the dwell timer is bypassed and GREEN->YELLOW transition happens immediately.

**Where it goes:** Inside `QueueController._apply_dwell_logic()` or the caller in `_classify_zone_4state()`.

**Why:** The dwell timer exists to filter DOCSIS MAP jitter (false YELLOW triggers). But when CAKE is actively dropping packets, congestion is CONFIRMED by the queue -- the dwell filter is adding unnecessary delay. CAKE's Cobalt AQM has its own 100ms interval before it starts dropping, so drops are already a reliable congestion signal. [CITED: https://www.nsnam.org/docs/models/html/cobalt.html]

```python
# Source: proposed pattern based on existing _classify_zone_4state [VERIFIED: queue_controller.py:252-300]
def _classify_zone_4state(
    self,
    delta: float,
    green_threshold: float,
    soft_red_threshold: float,
    hard_red_threshold: float,
    cake_snapshot: CakeSignalSnapshot | None = None,
) -> str:
    """Classify zone with optional CAKE signal override."""
    # ... existing threshold classification ...

    if raw_state == "YELLOW":
        self.green_streak = 0
        self.soft_red_streak = 0
        self.red_streak = 0
        # DETECT-01: Drop rate bypasses dwell timer
        if (
            cake_snapshot is not None
            and not cake_snapshot.cold_start
            and cake_snapshot.drop_rate > self._drop_rate_threshold
        ):
            self._dwell_bypassed_count += 1
            return "YELLOW"  # Immediate, no dwell
        return self._apply_dwell_logic()
```

### Pattern 2: Backlog Green Streak Suppression (DETECT-02)

**What:** When CAKE queue backlog exceeds a threshold, green_streak is reset to 0 even when zone is GREEN. This prevents rate recovery while the queue is still draining.

**Where it goes:** In the GREEN branch of `_classify_zone_4state()` and `_classify_zone_3state()`.

**Why:** RTT delta can return to GREEN while the CAKE queue still has significant backlog (packets in queue but not yet causing measurable delay because CAKE is AQM-managing them). Allowing recovery during active backlog causes re-congestion.

```python
# In GREEN branch of _classify_zone_4state():
self.green_streak += 1
self.soft_red_streak = 0
self.red_streak = 0
self._yellow_dwell = 0

# DETECT-02: Suppress green_streak while backlog is high
if (
    cake_snapshot is not None
    and not cake_snapshot.cold_start
    and cake_snapshot.backlog_bytes > self._backlog_threshold
):
    self.green_streak = 0  # Prevent recovery
    self._backlog_suppressed_count += 1
```

### Pattern 3: Refractory Period (DETECT-03)

**What:** After a drop-triggered dwell bypass causes a rate reduction, enter a refractory period where CAKE signals are ignored. This breaks the feedback loop: rate down -> fewer drops -> bypass lifts -> rate up -> drops resume -> rate down.

**Where it goes:** On `WANController` (not QueueController), because it spans the rate change + subsequent cycles.

**Why:** Classic control theory feedback loop. Rate reduction reduces queue depth, which reduces drops, which would instantly remove the drop-bypass signal. Without a cooldown, the system oscillates at the cycle frequency. CoDel's own dropping schedule uses a square-root-based inter-drop interval to avoid this; our refractory period is the analogous mechanism at the rate-control layer. [CITED: RFC 8289 - CoDel AQM]

```python
# On WANController:
self._dl_refractory_remaining = 0  # Cycles remaining
self._ul_refractory_remaining = 0
REFRACTORY_CYCLES_DEFAULT = 40  # 2 seconds at 50ms (configurable)

# In _run_congestion_assessment():
dl_cake = self._dl_cake_snapshot
if self._dl_refractory_remaining > 0:
    dl_cake = None  # Mask CAKE signals during refractory
    self._dl_refractory_remaining -= 1

# After rate reduction triggered by CAKE signal:
if dl_transition_reason and "cake_drop" in dl_transition_reason:
    self._dl_refractory_remaining = self._refractory_cycles
```

### Pattern 4: Bulk Tin Exclusion (DETECT-04)

**What:** Only BestEffort+Video+Voice tin drops drive decisions. Bulk tin drops are excluded.

**Where it goes:** Already implemented in `CakeSignalProcessor.update()` -- `drop_rate` field sums tins[1:] only. [VERIFIED: cake_signal.py lines 244-245]

**No new code needed.** The QueueController receives `snapshot.drop_rate` which already excludes Bulk. Using `snapshot.total_drop_rate` (which includes Bulk) would be incorrect for rate decisions.

### Pattern 5: YAML Config Extension

**What:** Add detection thresholds to existing `cake_signal` YAML section.

```yaml
cake_signal:
  enabled: true
  drop_rate:
    enabled: true                    # Existing (Phase 159)
    time_constant_sec: 1.0           # Existing (Phase 159)
    threshold_drops_per_sec: 10.0    # NEW: DETECT-01 dwell bypass trigger
  backlog:
    enabled: true                    # Existing (Phase 159)
    threshold_bytes: 10000           # NEW: DETECT-02 green_streak suppression
  detection:                         # NEW section
    refractory_cycles: 40            # NEW: DETECT-03 cooldown (2s at 50ms)
```

**Defaults:** All thresholds disabled when `drop_rate.enabled: false` / `backlog.enabled: false` (existing Phase 159 gates). Detection features only activate when the corresponding signal sub-feature is enabled AND the master `cake_signal.enabled: true`.

### Recommended Module Change Scope

```
src/wanctl/
  queue_controller.py    # MODIFY: add cake_snapshot param to adjust/adjust_4state,
                         #   drop bypass in dwell logic, backlog suppression in GREEN
  wan_controller.py      # MODIFY: pass cake_snapshot in _run_congestion_assessment,
                         #   add refractory counter, extend config parsing,
                         #   add refractory to health endpoint
  cake_signal.py         # MODIFY: add threshold fields to CakeSignalConfig
```

### Anti-Patterns to Avoid

- **Making QueueController depend on CakeSignalConfig:** QueueController should receive thresholds as constructor params (like dwell_cycles, deadband_ms), NOT import cake_signal module. Keep QueueController transport-agnostic.
- **Modifying CakeSignalProcessor for detection logic:** The processor computes signals; the controller consumes them. Detection logic belongs in QueueController/WANController, not in the signal module.
- **Bypassing dwell for backlog too:** Backlog suppresses recovery (DETECT-02), it does NOT bypass dwell. These are two separate mechanisms. Dwell bypass = faster congestion confirmation. Backlog suppression = slower recovery.
- **Putting refractory period on QueueController:** Refractory spans the rate change decision and subsequent cycles. It needs WANController-level state because it must mask the snapshot BEFORE it reaches QueueController.
- **Using total_drop_rate instead of drop_rate:** total_drop_rate includes Bulk tin. Bulk drops are expected under load (deprioritized traffic). Using total would cause false triggers. [VERIFIED: DETECT-04 requirement]

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Drop rate computation | New drop counting | CakeSignalSnapshot.drop_rate | Already computed, EWMA-smoothed, Bulk-excluded [VERIFIED: cake_signal.py] |
| Backlog computation | New backlog tracking | CakeSignalSnapshot.backlog_bytes | Already computed, Bulk-excluded [VERIFIED: cake_signal.py] |
| Tin separation | Manual tin filtering | CakeSignalProcessor already excludes Bulk | Indices hardcoded correctly [VERIFIED: cake_signal.py:244-245] |
| SIGUSR1 reload | New config reload path | Extend _reload_cake_signal_config() | Pattern proven [VERIFIED: wan_controller.py:1765-1789] |
| Health endpoint | New HTTP section | Extend _build_cake_signal_section() | Pattern established [VERIFIED: health_check.py:488-524] |

**Key insight:** Phase 159 built the signal infrastructure. Phase 160 is pure control logic -- consuming signals already available on CakeSignalSnapshot.

## Common Pitfalls

### Pitfall 1: Feedback Oscillation Without Refractory Period
**What goes wrong:** Drop rate bypasses dwell, rate drops, drops decrease, bypass lifts, rate recovers, drops resume. System oscillates at ~2-4 cycle frequency.
**Why it happens:** Classic control loop: the corrective action (rate reduction) removes the signal (drops) that triggered the action.
**How to avoid:** DETECT-03 refractory period. After drop-triggered rate reduction, ignore CAKE signals for N cycles (default 40 = 2 seconds). This gives CAKE's AQM time to stabilize at the new rate.
**Warning signs:** Rapid GREEN<->YELLOW flapping when CAKE signals are enabled, rate oscillating between step_up and factor_down values.

### Pitfall 2: Threshold Too Low Causes Permanent Dwell Bypass
**What goes wrong:** drop_rate_threshold set too low (e.g., 1 drop/sec), normal CAKE AQM behavior at equilibrium triggers constant bypass.
**Why it happens:** CAKE intentionally drops packets as part of AQM even at correctly-shaped rates. A small trickle of drops is normal.
**How to avoid:** Set threshold above normal AQM baseline. Need production measurement to determine baseline drop rate at steady state. Start conservative (e.g., 10 drops/sec) and tune down via A/B testing.
**Warning signs:** dwell_bypassed_count in health endpoint growing even during idle periods.

### Pitfall 3: Backlog Threshold Prevents All Recovery
**What goes wrong:** backlog_threshold set too low, there's always some backlog, green_streak never reaches green_required.
**Why it happens:** CAKE maintains a small working backlog even at optimal rates (packets in transit through the qdisc). Zero backlog only occurs when the link is truly idle.
**How to avoid:** Threshold must be above the "working set" backlog. Production measurement needed. Start conservative (e.g., 10KB = 10000 bytes) and tune.
**Warning signs:** Rate stuck at floor despite GREEN zone, green_streak always 0 in health endpoint.

### Pitfall 4: Cold Start Triggers False Detection
**What goes wrong:** After daemon restart, CakeSignalSnapshot.cold_start is True for first cycle but detection logic doesn't check it.
**Why it happens:** First snapshot has drop_rate=0.0 and backlog_bytes from current queue state (could be high if congested at startup).
**How to avoid:** All detection logic MUST check `snapshot.cold_start is False` before applying. Already shown in code examples above. [VERIFIED: cake_signal.py:229]
**Warning signs:** Immediate dwell bypass or backlog suppression on daemon restart.

### Pitfall 5: Breaking Backward Compatibility of adjust_4state()
**What goes wrong:** Adding required CakeSignalSnapshot parameter to adjust_4state() breaks all existing callers and 99 tests.
**Why it happens:** QueueController.adjust_4state() is called in tests without CAKE snapshot.
**How to avoid:** Make cake_snapshot parameter optional with default None. When None, all CAKE detection is skipped (existing behavior preserved). Tests pass without modification.
**Warning signs:** 99+ test failures after changing method signature.

### Pitfall 6: Refractory Period Too Short
**What goes wrong:** Refractory period shorter than CAKE's AQM convergence time, oscillation still occurs.
**Why it happens:** CAKE's Cobalt AQM interval is ~100ms, but queue drain time depends on rate delta. At 50ms cycles, 10 refractory cycles = 500ms might not be enough for a large rate step to drain the queue.
**How to avoid:** Default to 40 cycles (2 seconds) -- well above CAKE's 100ms interval and allows queue to drain even for large rate reductions. Make configurable for A/B testing.
**Warning signs:** Oscillation resumes immediately after refractory expires.

## Code Examples

### Example 1: QueueController with CAKE-Aware adjust_4state()

```python
# Source: proposed extension of queue_controller.py [VERIFIED: existing signature at line 206]
def adjust_4state(
    self,
    baseline_rtt: float,
    load_rtt: float,
    green_threshold: float,
    soft_red_threshold: float,
    hard_red_threshold: float,
    cake_snapshot: CakeSignalSnapshot | None = None,  # NEW: optional
) -> tuple[str, int, str | None]:
    """Apply 4-state logic with optional CAKE signal integration."""
    delta = load_rtt - baseline_rtt
    zone = self._classify_zone_4state(
        delta, green_threshold, soft_red_threshold, hard_red_threshold,
        cake_snapshot=cake_snapshot,
    )
    # ... rest unchanged ...
```

### Example 2: WANController Refractory Tracking

```python
# Source: proposed extension of wan_controller.py _run_congestion_assessment [VERIFIED: line 2096]
def _run_congestion_assessment(self) -> tuple[str, int, str | None, str, int, str | None, float]:
    # Apply refractory masking BEFORE passing to QueueController
    dl_cake = self._dl_cake_snapshot
    if self._dl_refractory_remaining > 0:
        dl_cake = None  # Mask CAKE during refractory
        self._dl_refractory_remaining -= 1

    ul_cake = self._ul_cake_snapshot
    if self._ul_refractory_remaining > 0:
        ul_cake = None
        self._ul_refractory_remaining -= 1

    dl_zone, dl_rate, dl_transition_reason = self.download.adjust_4state(
        self.baseline_rtt, self.load_rtt,
        self.green_threshold, self.soft_red_threshold, self.hard_red_threshold,
        cake_snapshot=dl_cake,
    )
    # ... upload adjust similarly ...

    # Enter refractory if dwell was bypassed this cycle
    if self.download._dwell_bypassed_this_cycle:
        self._dl_refractory_remaining = self._refractory_cycles
    if self.upload._dwell_bypassed_this_cycle:
        self._ul_refractory_remaining = self._refractory_cycles
```

### Example 3: Health Endpoint Extension

```python
# Source: extend existing cake_signal health data [VERIFIED: wan_controller.py:2920-2925]
"cake_signal": {
    "enabled": self._dl_cake_signal.config.enabled,
    "supported": self._cake_signal_supported,
    "download": self._dl_cake_snapshot,
    "upload": self._ul_cake_snapshot,
    # NEW: detection state
    "detection": {
        "dl_refractory_remaining": self._dl_refractory_remaining,
        "ul_refractory_remaining": self._ul_refractory_remaining,
        "dl_dwell_bypassed_count": self.download._dwell_bypassed_count,
        "ul_dwell_bypassed_count": self.upload._dwell_bypassed_count,
        "dl_backlog_suppressed_count": self.download._backlog_suppressed_count,
        "ul_backlog_suppressed_count": self.upload._backlog_suppressed_count,
    },
},
```

### Example 4: Config Parsing Extension

```python
# Source: extend _parse_cake_signal_config [VERIFIED: wan_controller.py:610-668]
# New threshold fields under drop_rate and backlog subsections:
drop_rate_threshold = dr.get("threshold_drops_per_sec", 10.0)
if not isinstance(drop_rate_threshold, (int, float)) or drop_rate_threshold <= 0:
    drop_rate_threshold = 10.0
drop_rate_threshold = max(1.0, min(1000.0, float(drop_rate_threshold)))

backlog_threshold = bl.get("threshold_bytes", 10000)
if not isinstance(backlog_threshold, (int, float)) or backlog_threshold <= 0:
    backlog_threshold = 10000
backlog_threshold = max(100, min(10_000_000, int(backlog_threshold)))
```

## CAKE AQM Timing Relationship

Understanding when CAKE drops relative to wanctl's 50ms cycle is critical for threshold tuning:

| CAKE AQM Event | Timing | Wanctl Cycles | Implication |
|-----------------|--------|---------------|-------------|
| Cobalt target exceeded | ~5ms sojourn | 0.1 cycles | Not yet dropping |
| Cobalt interval expired (first drop) | ~100ms after target exceeded | 2 cycles | First drop appears in stats |
| CoDel drop schedule ramp-up | 100ms + sqrt(N)*interval | 2+ cycles | Increasing drop rate |
| BLUE probability increase | On queue full events | Varies | Complements CoDel |
| Queue drain after rate reduction | Depends on rate delta | 10-40 cycles (0.5-2s) | Why refractory period needed |

**Key insight:** CAKE's first drops appear ~100ms (2 cycles) after congestion begins. By the time wanctl sees elevated drop_rate in the EWMA, congestion has been ongoing for 3-5 cycles (150-250ms). This means the drop signal is a LAGGING confirmation of what RTT delta already detected -- but it provides CERTAINTY. The dwell bypass uses this certainty to skip the dwell timer's 5-cycle (250ms) wait, recovering ~150ms of reaction time. [CITED: https://www.nsnam.org/docs/models/html/cobalt.html, https://www.man7.org/linux/man-pages/man8/tc-cake.8.html]

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| RTT-only congestion detection | RTT + CAKE drop/backlog signals | Phase 160 (this) | Faster confirmation, smarter recovery |
| Fixed dwell timer for all cases | Dwell with CAKE-aware bypass | Phase 160 (this) | 150ms faster congestion response when drops confirm |
| Unconditional green_streak counting | Backlog-suppressed recovery | Phase 160 (this) | Prevents re-congestion during queue drain |

**Related work:** cake-autorate (lynxthecat) does NOT use CAKE stats for rate control -- relies only on OWD/RTT. wanctl's approach of using CAKE drop rate and backlog as secondary signals alongside RTT is novel in this space. [CITED: https://deepwiki.com/lynxthecat/cake-autorate]

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Default drop_rate_threshold of 10 drops/sec is reasonable starting point | Architecture Patterns | Too low = permanent bypass, too high = never triggers. Must be A/B tested in production. Low risk: configurable via YAML. |
| A2 | Default backlog_threshold of 10000 bytes (10KB) is above working-set backlog | Architecture Patterns | Too low = blocks all recovery, too high = never triggers. Must measure production baseline. Low risk: configurable via YAML. |
| A3 | Refractory period of 40 cycles (2s) is sufficient for queue drain | Architecture Patterns | Too short = oscillation, too long = slow response to new congestion. Based on CAKE's 100ms AQM interval + queue drain math. Low risk: configurable via YAML. |
| A4 | CAKE's first drops appear ~100ms (2 cycles) after congestion onset | CAKE AQM Timing | Based on Cobalt's 100ms interval and 5ms target. Actual timing depends on bandwidth and queue depth. Verified against CoDel RFC and CAKE docs. |
| A5 | Backlog bytes from non-Bulk tins is the right metric (not packet count) | Pattern 2 | Byte-based backlog correlates better with queue drain time than packet count. If wrong, could use queued_packets instead. |

## Open Questions (RESOLVED)

1. **Production baseline drop rate** — RESOLVED: Deploy with conservative threshold=10.0 drops/sec, measure 24h baseline via health endpoint, tune via A/B test.
   - What we know: CAKE drops packets as part of normal AQM behavior even at correctly shaped rates. The threshold must be above this baseline.
   - Decision: Conservative default, measure and tune in production.

2. **Production baseline backlog** — RESOLVED: Deploy with conservative threshold_bytes=10000, measure via health endpoint, tune via A/B test.
   - What we know: CAKE maintains a small working backlog for packet scheduling. Zero backlog only occurs on truly idle links.
   - Decision: Conservative default, measure and tune in production.

3. **Refractory period optimal length** — RESOLVED: Default 40 cycles (2s), configurable via YAML. A/B test 20 and 60 cycles in Phase 161 validation window.
   - What we know: Must be longer than CAKE's AQM convergence (~100ms) and queue drain time. Must be short enough to respond to sustained congestion.
   - Decision: 2s default balances safety and responsiveness for DOCSIS.

4. **Should refractory also suppress backlog suppression?** — RESOLVED: Mask entire snapshot (pass None to QueueController during refractory). Simpler, safer — backlog naturally decreases as queue drains.
   - What we know: DETECT-03 says "prevents feedback loop oscillation after drop-triggered rate reduction."
   - Decision: Mask everything during refractory. Refractory expiring at 2s gives time for queue drain.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.0+ with xdist parallel |
| Config file | pyproject.toml [tool.pytest.ini_options] |
| Quick run command | `.venv/bin/pytest tests/test_queue_controller.py tests/test_cake_signal.py -x` |
| Full suite command | `.venv/bin/pytest tests/ -v --timeout=2` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| DETECT-01 | Drop rate above threshold bypasses dwell timer | unit | `.venv/bin/pytest tests/test_queue_controller.py::TestCakeDropBypass -x` | Wave 0 |
| DETECT-02 | Backlog above threshold suppresses green_streak | unit | `.venv/bin/pytest tests/test_queue_controller.py::TestCakeBacklogSuppression -x` | Wave 0 |
| DETECT-03 | Refractory period prevents oscillation | unit | `.venv/bin/pytest tests/test_wan_controller.py::TestRefractoryPeriod -x` | Wave 0 |
| DETECT-04 | Only BestEffort+ tin drops, Bulk excluded | unit | `.venv/bin/pytest tests/test_cake_signal.py::TestTinSeparation -x` | Exists (Phase 159) |

### Sampling Rate
- **Per task commit:** `.venv/bin/pytest tests/test_queue_controller.py tests/test_cake_signal.py -x`
- **Per wave merge:** `.venv/bin/pytest tests/ -v --timeout=2`
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `tests/test_queue_controller.py::TestCakeDropBypass` -- covers DETECT-01 (dwell bypass with drop_rate)
- [ ] `tests/test_queue_controller.py::TestCakeBacklogSuppression` -- covers DETECT-02 (green_streak suppression)
- [ ] `tests/test_wan_controller.py::TestRefractoryPeriod` -- covers DETECT-03 (refractory counter logic)
- [ ] No framework install needed (pytest already configured)
- [ ] DETECT-04 already covered by existing test_cake_signal.py::TestTinSeparation

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | N/A |
| V3 Session Management | no | N/A |
| V4 Access Control | no | N/A |
| V5 Input Validation | yes | Validate threshold bounds in YAML parsing (same pattern as existing config) |
| V6 Cryptography | no | N/A |

### Known Threat Patterns

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Malicious YAML threshold (negative or extreme values) | Tampering | Bounds checking in _parse_cake_signal_config() with safe defaults |
| CakeSignalSnapshot with cold_start=True used for detection | Information Disclosure (false trigger) | cold_start guard in all detection paths |
| MagicMock in test leaks to detection logic | Tampering (test) | isinstance guard or cold_start check blocks mock snapshots |

## Sources

### Primary (HIGH confidence)
- Existing codebase `cake_signal.py` -- CakeSignalProcessor, CakeSignalSnapshot, CakeSignalConfig [VERIFIED: src/wanctl/cake_signal.py, 293 lines]
- Existing codebase `queue_controller.py` -- QueueController, dwell timer, green_streak, adjust/adjust_4state [VERIFIED: src/wanctl/queue_controller.py, 353 lines]
- Existing codebase `wan_controller.py` -- run_cycle, _run_congestion_assessment, _run_cake_stats [VERIFIED: src/wanctl/wan_controller.py, 2998 lines]
- Existing codebase `health_check.py` -- _build_cake_signal_section [VERIFIED: src/wanctl/health_check.py:488-524]
- Phase 159 research [VERIFIED: .planning/phases/159-cake-signal-infrastructure/159-RESEARCH.md]

### Secondary (MEDIUM confidence)
- [COBALT AQM ns-3 model docs](https://www.nsnam.org/docs/models/html/cobalt.html) -- Cobalt timing: 100ms interval, 5ms target [CITED]
- [tc-cake(8) man page](https://www.man7.org/linux/man-pages/man8/tc-cake.8.html) -- CAKE AQM parameter auto-tuning [CITED]
- [RFC 8289 - CoDel AQM](https://datatracker.ietf.org/doc/rfc8289/) -- CoDel control law and drop scheduling [CITED]
- [CAKE Technical Information](https://www.bufferbloat.net/projects/codel/wiki/CakeTechnical/) -- per-tin stats, peak_delay behavior [CITED]
- [cake-autorate DeepWiki](https://deepwiki.com/lynxthecat/cake-autorate) -- Confirmed cake-autorate does NOT use CAKE stats [CITED]

### Tertiary (LOW confidence)
- None. All critical claims verified against codebase or official documentation.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- no new deps, all existing code
- Architecture: HIGH -- extends well-understood codebase patterns (dwell, green_streak, SIGUSR1)
- Pitfalls: HIGH -- feedback oscillation is classic control theory, refractory period is standard mitigation
- Threshold defaults: MEDIUM -- A1, A2, A3 are reasonable starting points but need A/B validation in production

**Research date:** 2026-04-10
**Valid until:** 2026-05-10 (stable domain, extends existing patterns)
