# Production Interval Configuration

**Decision Date:** 2026-01-13
**Production Standard:** 50ms cycle interval
**Status:** Deployed and validated

---

## Executive Summary

After comprehensive testing in Phase 2, **50ms cycle interval** has been selected as the production standard for wanctl. This represents a **40x speed improvement** over the original 2-second baseline, providing sub-second congestion detection while maintaining excellent stability and zero router CPU impact at idle.

**Key Result:** Congestion detected in 50-100ms (vs 1-2 seconds at original 2s interval)

---

## Decision Rationale

### Why 50ms?

**Maximum Responsiveness:**
- 40x faster than original 2s baseline (0.5Hz → 20Hz polling)
- Sub-second congestion detection (50-100ms response time)
- Fastest possible congestion mitigation

**Proven Stability:**
- Validated under 3-minute RRUL bidirectional stress testing
- Zero errors or timing violations throughout testing
- Perfect baseline RTT stability (no drift under extreme alpha values)
- Tested on both cable (Spectrum) and DSL (AT&T) connections

**Acceptable Resource Impact:**
- **0% router CPU at idle** - Zero measurable impact from 20Hz REST API polling
- **~45% CPU peak under heavy load** - Comfortable headroom during stress
- **60-80% cycle utilization** - Within sustainable performance envelope
- MikroTik RB5009 handles 50ms intervals effortlessly

**Time-Constant Preservation:**
- EWMA alpha values scaled mathematically to preserve wall-clock behavior
- Steering thresholds maintain 16s activation, 30s recovery timing
- Same congestion response characteristics regardless of polling rate

### Trade-offs Considered

| Interval | Speed vs Original | Pros | Cons |
|----------|------------------|------|------|
| **50ms (SELECTED)** | 40x faster | Maximum speed, proven stable, sub-second detection | Minimal headroom (60-80% utilization), approaching limits |
| 100ms | 20x faster | 2x headroom vs 50ms, still extremely fast | Not tested (would require validation) |
| 250ms | 8x faster | 4x headroom, very safe, proven stable | Slower than achievable maximum |

**Decision:** 50ms provides maximum user benefit (sub-second congestion response) with proven stability. The 60-80% utilization is sustainable and well within the router's capabilities.

---

## Validation Results

### Phase 2 Testing Summary

**Test 02-01: 250ms Interval (Conservative)**
- Duration: 28 minutes
- Result: ✅ Proven stable, excellent headroom (12-16% utilization)
- Router CPU: 1-3% under load
- Timing: ±2ms consistency

**Test 02-03: 50ms Interval (Extreme)**
- Duration: 11 minutes + 3-minute RRUL stress test
- Result: ✅ Proven stable, identified performance limit
- Router CPU: 0% idle, 45% peak under RRUL stress
- Timing: ATT ±1ms (exceptional), Spectrum ±10ms (acceptable)
- Utilization: 60-80% (30-40ms execution vs 50ms interval)

### RRUL Stress Test Results

**Test Conditions:**
- 3-minute bidirectional stress (upload + download saturation)
- Target: Dallas (104.200.21.31)
- Heavy traffic load maintained throughout

**Performance:**
- **Congestion detection:** 50-100ms (1-2 cycles)
- **State transitions:** GREEN → YELLOW → SOFT_RED/RED
- **RTT response:** Spike from 26ms → 295ms detected immediately
- **Rate response:** Upload reduced 38M → 8M (floor), Download backed off to ~350M
- **Baseline stability:** 26.8-28.4ms maintained, no drift
- **Router CPU:** 1-45% (avg ~37% during stress)
- **Timing consistency:** 50ms cycles maintained throughout load
- **Zero errors:** No timing violations, cycle skips, or failures

**Conclusion:** 50ms interval is production-ready for maximum-speed deployment.

---

## Configuration Details

### Cycle Interval

**Primary constant:**
```python
# src/wanctl/autorate_continuous.py
CYCLE_INTERVAL_SECONDS = 0.05  # 50ms = 20Hz polling
```

**Steering daemon:**
```python
# src/wanctl/steering/daemon.py
ASSESSMENT_INTERVAL_SECONDS = 0.05
MAX_HISTORY_SAMPLES = 2400  # 2 minutes at 50ms
```

### EWMA Alpha Values (Time-Constant Preservation)

**Principle:** When interval decreases Nx, alpha decreases Nx to maintain same wall-clock smoothing.

**Spectrum (Cable):**
```yaml
# configs/spectrum.yaml
continuous_monitoring:
  thresholds:
    alpha_baseline: 0.0005  # 2000 samples × 0.05s = 100s time constant
    alpha_load: 0.005       # 200 samples × 0.05s = 10s time constant
```

**AT&T (DSL):**
```yaml
# configs/att.yaml
continuous_monitoring:
  thresholds:
    alpha_baseline: 0.000375  # 2667 samples × 0.05s = 133s time constant
    alpha_load: 0.005         # 200 samples × 0.05s = 10s time constant
```

### Steering Thresholds

**Sample counts scaled 40x from original 2s baseline:**
```yaml
# /etc/wanctl/steering.yaml
measurement:
  interval_seconds: 0.05

state:
  bad_samples_required: 320   # 320 × 0.05s = 16 seconds (activation)
  good_samples_required: 600  # 600 × 0.05s = 30 seconds (recovery)
  history_size: 2400          # 2400 × 0.05s = 120 seconds (2-minute window)
```

**Wall-clock timing preserved:** Steering still takes 16s to activate, 30s to recover (same as slower intervals).

### Schema Validation

**Extended for extreme values:**
```python
# src/wanctl/autorate_continuous.py
alpha_baseline: min=0.0001 (was 0.001)  # Supports extreme smoothing at 20Hz
alpha_load: min=0.001 (was 0.01)

# src/wanctl/steering/daemon.py
interval_seconds: min=0.01 (was 0.5)     # Supports extreme intervals
history_size: max=3000 (was 1000)        # Supports large sample buffers
```

---

## Performance Characteristics

### Timing Consistency

**AT&T (VDSL):**
- Target: 50ms
- Actual: 50-51ms
- Variance: ±1ms (exceptional)
- Notes: DSL provides stable, predictable scheduling

**Spectrum (Cable):**
- Target: 50ms
- Actual: 35-79ms (median 50ms)
- Variance: ±10ms typical, occasional outliers
- Notes: Cable CMTS introduces scheduling variation (acceptable)

### Execution Budget

**Cycle execution time:** 30-40ms (from Phase 1 profiling)
**Cycle interval:** 50ms
**Utilization:** 60-80%
**Headroom:** 20-40%

This represents the practical performance limit. Faster intervals are not recommended.

### Router Efficiency

**MikroTik RB5009UG+S+ (ARM64, 4 cores @ 1400MHz):**
- **Idle:** 0% CPU (20Hz REST API polling = zero measurable impact)
- **Under load:** 27-45% CPU (RRUL stress test)
- **Peak:** 45% CPU (comfortable headroom, well below 70% threshold)

**Comparison across intervals:**
| Interval | Polling Rate | Router CPU (idle) | Router CPU (load) | Utilization |
|----------|--------------|-------------------|-------------------|-------------|
| 2s (original) | 0.5 Hz | N/A | N/A | 3-4% |
| 500ms | 2 Hz | 1-3% | ~10-15% | 6-8% |
| 250ms | 4 Hz | 1-3% | ~20-25% | 12-16% |
| **50ms** | **20 Hz** | **0%** | **~37-45%** | **60-80%** |

---

## Conservative Alternatives

### When to Use 100ms

**Use 100ms if:**
- You want 2x headroom over 50ms for variance/load spikes
- Still 20x faster than original (excellent speed)
- Lower risk for production
- Haven't tested 50ms in your specific environment

**Configuration:** Scale all parameters by 2x from 50ms values (alpha values × 2, sample counts ÷ 2).

### When to Use 250ms

**Use 250ms if:**
- You prefer conservative approach (proven over extended testing)
- Want 4x headroom (very safe margin)
- Still 8x faster than original 2s
- Router has higher baseline CPU load from other services

**Configuration:** Available in Phase 2 test results (docs/INTERVAL_TESTING_250MS.md).

### Time-Constant Preservation Formula

When changing intervals, preserve EWMA time constants:

```
New Alpha = Old Alpha × (New Interval / Old Interval)
New Sample Count = Old Sample Count × (Old Interval / New Interval)

Example (50ms → 100ms):
alpha_baseline: 0.0005 × (0.1 / 0.05) = 0.001
bad_samples_required: 320 × (0.05 / 0.1) = 160
```

Wall-clock smoothing behavior remains identical.

---

## Rollback Procedure

If 50ms interval causes issues in your deployment:

### Option 1: Revert to 250ms (Tested, Safe)

```bash
cd /home/kevin/projects/wanctl

# Find the 250ms commit (from Phase 2 Plan 01)
git log --oneline --grep="250ms" | head -5

# Revert to 250ms configuration
git revert <50ms-commits> --no-edit

# Redeploy configurations
# (Copy updated files to containers and restart services)
```

### Option 2: Adjust to 100ms (Untested, Interpolated)

Modify source and config files:
- `CYCLE_INTERVAL_SECONDS = 0.1` (autorate and steering)
- Scale alpha values × 2 (0.0005 → 0.001)
- Scale sample counts ÷ 2 (320 → 160)
- Test thoroughly before production use

### Verification After Rollback

```bash
# Monitor for stability
./scripts/soak-monitor.sh

# Check logs for errors
ssh cake-spectrum 'journalctl -u wanctl@spectrum -f'
ssh cake-att 'journalctl -u wanctl@att -f'

# Verify router CPU
ssh cake-spectrum 'curl -s http://127.0.0.1:9101/health | python3 -m json.tool'
```

---

## Production Deployment

### For New Installations

1. **Install wanctl** using standard installation procedure
2. **Configure interval** in source:
   ```python
   # src/wanctl/autorate_continuous.py
   CYCLE_INTERVAL_SECONDS = 0.05
   ```
3. **Configure EWMA alphas** in WAN configs (see Configuration Details above)
4. **Configure steering** if using multi-WAN (see Configuration Details above)
5. **Deploy and monitor** for initial stability period

### For Existing Installations

Current installations already running at 50ms (deployed 2026-01-13). No action needed.

If running slower interval and want to upgrade:
1. Review this document thoroughly
2. Update source files (CYCLE_INTERVAL_SECONDS)
3. Update WAN configs (alpha values scaled appropriately)
4. Update steering config (sample counts scaled appropriately)
5. Deploy and monitor for 24-48 hours
6. Validate with stress test (optional: run RRUL to confirm)

---

## Monitoring

### Health Check Indicators

**Normal operation at 50ms:**
```bash
# Expected output
[GREEN/GREEN] RTT=25.5ms, baseline=24.0ms, delta=1.5ms | DL=940M, UL=38M
```

**Timing consistency:**
- ATT: 50-51ms (±1ms is normal)
- Spectrum: 35-79ms (median 50ms, ±10ms variance normal)

**Router CPU:**
- Idle: 0-4% (0% typical)
- Under load: 27-45% (acceptable range)

### Warning Signs

**Monitor for these issues:**
- Cycle timing consistently >70ms (indicates system overload)
- Router CPU >70% sustained (indicates resource exhaustion)
- Baseline RTT drifting over time (indicates EWMA misconfiguration)
- Frequent state oscillation (GREEN ↔ YELLOW ↔ RED flapping)

**If observed:** Consider rollback to 250ms or investigate system load.

---

## References

- **Phase 2 Plan 01:** docs/INTERVAL_TESTING_250MS.md (250ms validation)
- **Phase 2 Plan 03:** docs/INTERVAL_TESTING_50MS.md (50ms validation)
- **RRUL Stress Test:** /tmp/rrul-test-50ms/STRESS_TEST_SUMMARY.md
- **Performance Analysis:** docs/FASTER_RESPONSE_INTERVAL.md
- **Profiling Data:** docs/PROFILING-ANALYSIS.md (Phase 1 baseline)

---

## Conclusion

The 50ms production interval provides maximum congestion responsiveness with proven stability. The configuration has been validated under stress testing and operates within sustainable performance limits.

**Deployed:** 2026-01-13
**Status:** Production standard
**Next Review:** Monitor for 30 days, reassess if issues observed

For questions or issues, refer to project documentation or Phase 2/3 planning artifacts.
