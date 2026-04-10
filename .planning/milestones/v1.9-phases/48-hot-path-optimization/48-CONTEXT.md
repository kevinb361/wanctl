# Phase 48: Hot Path Optimization — Context

**Created:** 2026-03-06
**Phase goal:** Reduce cycle time based on profiling findings; eliminate subprocess overhead in RTT measurement hot path
**Depends on:** Phase 47 (profiling data drives optimization choices)
**Requirements:** OPTM-01, OPTM-02, OPTM-03, OPTM-04

## Profiling Data Summary (from Phase 47)

Phase 47 collected 1 hour of production data (~141,600 cycles). Key findings:

| Subsystem | Spectrum Avg | ATT Avg | % of Cycle | Optimization? |
|-----------|-------------|---------|------------|---------------|
| RTT measurement | 40.0ms | 30.3ms | 97-98% | **Primary target** |
| Router communication | 0.2ms | 0.0ms | <0.5% | Already near-zero |
| State management | 0.7ms | 0.8ms | 1-3% | P99 spikes to 7-8ms |
| CAKE stats | 6.1ms | — | steering only | 2s interval, N/A |

RTT measurement dominates. 97-98% of cycle time is actual network round-trip latency.
Subprocess fork overhead contributes ~2-5ms per cycle on top of irreducible network RTT.

## Decisions

### D1: Raw ICMP Sockets via icmplib

**Decision:** Replace `subprocess.run(["ping", ...])` with `icmplib` library for direct ICMP socket communication.

**Rationale:**
- Eliminates per-cycle subprocess fork/exec/pipe/parse overhead (~2-5ms savings)
- At 20Hz (50ms cycles), that's 20 forks/second per daemon — expensive
- `icmplib` is pure Python, no C extensions, MIT licensed, well-maintained
- Returns RTT as float directly — no stdout text parsing needed
- wanctl runs as root in Docker containers — CAP_NET_RAW already available
- More consistent timing (no fork jitter), directly improves P99

**Rejected alternatives:**
- Persistent ping subprocess (fping): More complex lifecycle management, fragile output parsing
- Pipelining across cycles: Adds one-cycle latency to congestion detection, undermines core value
- Accept physics floor: 2-5ms savings is real and measurable, worth the effort

**New dependency:** `icmplib` (add to pyproject.toml)

### D2: Keep Current Reflector Configuration

**Decision:** Keep config-driven reflector mode unchanged. Median-of-three for Spectrum, single for ATT.

**Rationale:**
- `ping_hosts_concurrent()` already runs reflectors in parallel via ThreadPoolExecutor
- Wall-clock time for 3 concurrent pings ≈ time for 1 ping
- Adaptive reflector count (3 in GREEN, 1 in YELLOW/RED) provides near-zero savings
- Removing median during congestion reduces accuracy when it matters most
- Config-driven via `use_median_of_three` YAML setting — no code change needed

### D3: Revised Success Criteria

**Decision:** Revise Phase 48 success criteria to reflect profiling reality.

**Original targets** (pre-profiling, aspirational):
1. Average cycle ≤20ms
2. P99 cycle ≤35ms
3. Router CPU ≤30%

**Revised targets** (data-driven):
1. Subprocess overhead eliminated: avg cycle reduced by ≥3ms (measurable before/after)
2. P99 cycle jitter reduced (fewer fork spikes): Spectrum P99 ≤55ms, ATT P99 ≤33ms
3. Router CPU: measured before/after, target ≤40% (was 45% under RRUL)
4. No regression in congestion detection responsiveness (still sub-second)
5. All existing tests pass with no behavioral changes
6. Zero subprocess forks in RTT measurement hot path

**Why revised:** Profiling showed 97% of cycle time is irreducible network RTT. Code optimization can only eliminate the ~2-5ms subprocess overhead, not halve the cycle time.

### D4: Revised Utilization Target

**Decision:** Revise v1.9 milestone utilization target from ~40% to ~55-65%.

**Rationale:** With 97% of cycle time being network-bound, raw ICMP sockets bring:
- Spectrum: ~82% → ~72% utilization
- ATT: ~62% → ~55% utilization
- Cannot reach ~40% without fundamentally changing measurement approach

### D5: OPTM-02/03/04 Disposition

**OPTM-02 (Router communication): Satisfied by profiling data**
- Evidence: 0.0-0.2ms average, flash wear protection already prevents unnecessary API calls
- Action: Document finding in phase summary, no code change needed

**OPTM-03 (CAKE stats): Not applicable at current intervals**
- Evidence: CAKE stats only read by steering daemon, which runs at 2s intervals (not 50ms)
- Action: Document finding, revisit if steering moves to 50ms in future

**OPTM-04 (Router CPU): Redefined as measurement task**
- Action: Measure router CPU before/after raw ICMP socket change
- Target: ≤40% peak (was 45% under RRUL stress)
- If still high after change, capture as future work — not a Phase 48 blocker

### D6: State Management P99 — Deferred

**Decision:** Do not address state management P99 spikes (7-8ms) in Phase 48.

**Rationale:** State management averages 0.7ms — P99 spikes are rare and only 7-8ms (GC pauses, fsync). Not worth the complexity of async writes or reduced fsync. Raw ICMP sockets is the higher-impact change. Revisit in Phase 49 or future milestone if needed.

## Code Context

### Files to Modify

| File | Change | Impact |
|------|--------|--------|
| `src/wanctl/rtt_measurement.py` | Replace subprocess ping with icmplib | Core change — RTTMeasurement.ping_host() |
| `src/wanctl/rtt_measurement.py` | Update ping_hosts_concurrent() for icmplib | Concurrent pings without subprocess |
| `pyproject.toml` | Add icmplib dependency | New dependency |
| `tests/test_rtt_measurement.py` | Update tests to mock icmplib instead of subprocess | Test adaptation |

### Files NOT Modified (confirmed by profiling)

| File | Why Not |
|------|---------|
| `src/wanctl/routeros_rest.py` | Router communication already 0.0-0.2ms |
| `src/wanctl/routeros_ssh.py` | Router communication already near-zero |
| `src/wanctl/steering/cake_stats.py` | Only steering daemon, 2s interval |
| `src/wanctl/state_utils.py` | State P99 deferred |
| `src/wanctl/autorate_continuous.py` | measure_rtt() API unchanged — calls same methods |
| `src/wanctl/steering/daemon.py` | RTT API unchanged — calls same methods |

### API Preservation

The `RTTMeasurement` class API must remain unchanged:
- `ping_host(host, count=1) -> float | None`
- `ping_hosts_concurrent(hosts, count=1, timeout=3.0) -> list[float]`
- `parse_ping_output()` can be removed or deprecated (no longer needed with icmplib)

Callers (autorate_continuous.py, steering/daemon.py) should require zero changes.

### Protected Zones (DO NOT TOUCH)

- Baseline RTT freeze logic (autorate_continuous.py)
- Flash wear protection (autorate_continuous.py)
- Rate limiting (autorate_continuous.py)
- CAKE stats delta math (cake_stats.py)
- Atomic state persistence (state_utils.py)
- Signal handling (signal_utils.py)

## Scope Guardrails

**In scope:**
- Replace subprocess ping with icmplib in RTTMeasurement
- Update tests for new implementation
- Measure and document before/after cycle times
- Measure and document router CPU impact

**Out of scope (deferred):**
- State management P99 optimization
- CAKE stats optimization
- Async I/O rewrite
- 25ms cycle interval exploration
- Steering daemon interval change (2s → 50ms)

## Verification Approach

1. **Before:** Collect 1-hour production profiling baseline with `--profile` flag
2. **Implement:** Replace subprocess ping with icmplib
3. **Test:** All existing tests pass, new tests for icmplib path
4. **After:** Collect 1-hour production profiling with same `--profile` flag
5. **Compare:** Measure avg cycle reduction (target ≥3ms), P99 improvement, router CPU

---

_Context created: 2026-03-06_
_Gray areas discussed: RTT optimization approach, success criteria revision, OPTM-02/03/04 disposition_
