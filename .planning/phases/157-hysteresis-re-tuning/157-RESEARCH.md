# Phase 157: Hysteresis Re-Tuning - Research

**Researched:** 2026-04-09
**Domain:** EWMA hysteresis tuning (dwell timer + deadband) for DOCSIS jitter filtering
**Confidence:** HIGH

## Summary

Phase 157 is a measurement-and-tuning phase, not a code phase. The controller already has full hysteresis infrastructure (dwell timer, deadband, windowed suppression tracking, Discord alerting, SIGUSR1 hot-reload, health endpoint reporting). The goal is to re-measure the suppression rate after Phases 154-156 changed the control loop's timing profile (netlink replaces subprocess tc, SQLite writes are deferred to a background thread, asymmetry gate attenuates upload deltas) and either confirm current values are correct or A/B test new values.

The known issue is 31 suppressions/min (exceeds the 20/min alert threshold). This was measured pre-v1.31 but post-DSCP (v1.28). Phases 154-156 changed cycle timing: netlink saves ~5ms/cycle (no subprocess fork), deferred I/O removes SQLite write latency from the hot path, and asymmetry gate may reduce upload-side dwell triggers during download-only congestion. These changes may have reduced the suppression rate by reducing jitter in the control loop itself.

**Primary recommendation:** Measure first, tune only if needed. Deploy v1.31 code (Phases 154-156), run a baseline RRUL test, read suppression rate from health endpoint. If already below 20/min, document and close. If still above, A/B test dwell_cycles (5 vs 7) and/or deadband_ms (3.0 vs 5.0) one at a time using established flent methodology.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| TUNE-01 | Hysteresis suppression rate validated against post-v1.31 jitter profile and tuned below 20/min alert threshold | Full hysteresis infrastructure exists (dwell timer, deadband, windowed counters, alerting, health endpoint, SIGUSR1 hot-reload). Measurement via health endpoint + RRUL load. A/B testing via SIGUSR1 config reload + flent. |
</phase_requirements>

## Project Constraints (from CLAUDE.md)

- **Production system:** Conservative changes only. Explain before changing.
- **Portable controller:** All variability in config parameters (YAML), never in code.
- **Architectural spine READ-ONLY:** Control model, state logic, flash wear protection, steering spine.
- **A/B testing discipline:** Test ONE parameter at a time. Never apply untested changes. Always measure.
- **flent from dev machine:** Never from cake-shaper VM.
- **Netperf server:** dallas (104.200.21.31), not public servers.
- **Version bumps:** Always update __init__.py, pyproject.toml, and CLAUDE.md on deploy.

## Architecture Patterns

### Hysteresis System Architecture

```
spectrum.yaml
  continuous_monitoring.thresholds:
    dwell_cycles: 5           # Consecutive above-threshold cycles before GREEN->YELLOW fires
    deadband_ms: 3.0          # Delta gap between enter-YELLOW and exit-YELLOW thresholds
    suppression_alert_pct: 5.0  # DEAD CONFIG KEY -- code reads suppression_alert_threshold (default 20)
                                 |
                                 v
QueueController (queue_controller.py)
  _apply_dwell_logic()         # Increments _yellow_dwell, suppresses GREEN->YELLOW until dwell_cycles reached
  _classify_zone_3state()      # Upload: delta-based zone with dwell + deadband
  _classify_zone_4state()      # Download: 4-state zone with dwell + deadband
  _window_suppressions         # Counter reset every 60s by WANController._check_hysteresis_window()
  get_health_data()            # Returns hysteresis dict: dwell_counter, dwell_cycles, deadband_ms, suppressions_per_min
                                 |
                                 v
WANController (wan_controller.py)
  _check_hysteresis_window()   # Every 60s: reads DL+UL suppression counts, logs, fires alert if > threshold
  _reload_hysteresis_config()  # SIGUSR1: re-reads dwell_cycles + deadband_ms from YAML, applies to both DL+UL
  _reload_suppression_alert_config()  # SIGUSR1: re-reads suppression_alert_threshold from YAML
  _suppression_alert_threshold # Default 20, read from continuous_monitoring.thresholds.suppression_alert_threshold
                                 |
                                 v
Health Endpoint (/health)
  download.hysteresis.suppressions_per_min   # Current window's DL suppression count
  upload.hysteresis.suppressions_per_min     # Current window's UL suppression count
  download.hysteresis.alert_threshold_per_min  # Current alert threshold
```

### A/B Test Workflow (Established Pattern from v1.26)

```
1. Set baseline:  Edit spectrum.yaml with current values
2. Deploy:        SIGUSR1 (kill -USR1 $(pgrep -f wanctl)) -- hot-reload, no restart
3. Measure:       flent rrul -H 104.200.21.31 -l 60 (from dev machine)
                  curl health endpoint for suppression rate
4. Record:        Median/p99 latency, throughput, suppression count, zone distribution
5. Change ONE param: Edit YAML, SIGUSR1 reload
6. Measure again: Same flent + health endpoint
7. Compare:       Winner based on latency improvement without throughput regression
8. Apply winner:  Update YAML permanently, next test uses winner as baseline
```

### Key Integration Points

| Component | File | What It Does |
|-----------|------|--------------|
| Dwell timer logic | `src/wanctl/queue_controller.py:135-160` | `_apply_dwell_logic()` -- increments `_yellow_dwell`, suppresses transition if < `dwell_cycles` |
| Deadband logic | `src/wanctl/queue_controller.py:120-127` (3-state), `284-293` (4-state) | Holds YELLOW when delta drops below threshold but within deadband margin |
| Window counter | `src/wanctl/queue_controller.py:326-336` | `reset_window()` -- returns count and resets for next 60s window |
| Window check | `src/wanctl/wan_controller.py:1746-1786` | `_check_hysteresis_window()` -- fires alert if total > threshold during congestion |
| SIGUSR1 reload | `src/wanctl/wan_controller.py:1391-1465` | `_reload_hysteresis_config()` -- re-reads dwell_cycles + deadband_ms from YAML |
| Health facade | `src/wanctl/wan_controller.py:2734-2736` | `suppression_alert.threshold` in health data dict |
| Health rendering | `src/wanctl/health_check.py:271-289` | `_build_rate_hysteresis_section()` -- formats for /health JSON |

[VERIFIED: codebase grep of queue_controller.py, wan_controller.py, health_check.py]

## What Changed in Phases 154-156 That Affects Jitter Profile

### Phase 154: Netlink Backend Wiring
- **Before:** `subprocess.run(["tc", "qdisc", "change", ...])` at ~3ms/call, fork overhead
- **After:** pyroute2 netlink at ~0.3ms/call, no subprocess fork
- **Impact on jitter:** Removes ~2.7ms of per-cycle variance from the hot path. Subprocess fork time is variable (depends on OS scheduler, memory pressure). Netlink is deterministic kernel IPC. This should **reduce** cycle timing jitter, potentially lowering the number of transient RTT delta spikes caused by the controller's own I/O overhead.
[VERIFIED: Phase 154 verification report, codebase]

### Phase 155: Deferred I/O Worker
- **Before:** SQLite metrics writes on the main thread, ~0.5-5ms per cycle (p99 tail)
- **After:** SQLite writes enqueued to background SimpleQueue thread, main thread returns immediately
- **Impact on jitter:** Removes the largest source of cycle timing tail latency. The 1,833 cycle overruns (p99=51ms) were primarily caused by SQLite I/O tail spikes. With deferred I/O, the control loop measures RTT and makes decisions without being delayed by disk writes. This should **reduce** the number of artificially elevated RTT delta samples caused by the controller itself running long.
[VERIFIED: Phase 155 summaries, STATE.md known issues]

### Phase 156: Asymmetry Gate
- **Before:** Upload rate drops to 8Mbps floor during download-only congestion (both DL and UL see same elevated delta)
- **After:** Asymmetry gate attenuates upload delta by damping_factor (10%) when IRTT detects downstream-only congestion
- **Impact on jitter:** During download-only load, upload-side dwell suppressions should **decrease** because the upload delta is attenuated. This reduces total suppression count (DL+UL combined). However, download-side suppressions are unchanged since the gate only affects upload.
[VERIFIED: Phase 156 summary, wan_controller.py _compute_effective_ul_load_rtt()]

### Net Effect Prediction

All three changes work in the same direction: reducing control loop timing variance and reducing spurious delta elevation. The suppression rate is likely to **decrease** from the baseline 31/min. It may already be below 20/min after these changes, in which case no tuning is needed -- just measurement and documentation.

## Config Key Discovery: Dead `suppression_alert_pct` [VERIFIED: codebase grep]

The production YAML has `suppression_alert_pct: 5.0` at line 71 of `configs/spectrum.yaml`. However, the code reads `suppression_alert_threshold` (integer, default 20) at `wan_controller.py:533-536`. The `suppression_alert_pct` key is **never read by any code in src/**. This means:

1. The alert threshold has always been the default of 20 (suppressions per 60s window)
2. The `suppression_alert_pct` YAML key is dead config cruft
3. This should be cleaned up: either remove the dead key or rename the code to read `suppression_alert_pct` and convert appropriately

**Recommendation:** In the Phase 157 plan, include a task to fix this dead config key. Either:
- (a) Remove `suppression_alert_pct` from YAML and add `suppression_alert_threshold: 20` explicitly, or
- (b) Keep `suppression_alert_pct` and convert it to an absolute count in code (e.g., 5% of 1200 cycles/min = 60 suppressions/min)

Option (a) is simpler and matches how the code works. The planner should decide.

## Measurement Protocol

### Baseline Measurement (Success Criteria 1)

1. **Deploy v1.31 code** to cake-shaper VM (Phases 154-156 already complete)
2. **Wait 5+ minutes** for baseline RTT to stabilize after restart
3. **Run RRUL load test** from dev machine:
   ```bash
   flent rrul -H 104.200.21.31 -l 60 -t "p157-baseline"
   ```
4. **During test, check health endpoint** from dev machine:
   ```bash
   ssh kevin@10.10.110.223 'curl -s http://127.0.0.1:9101/health' | jq '.wans[0].download.hysteresis, .wans[0].upload.hysteresis'
   ```
5. **After test, wait for 60s window to roll** and check suppression counts:
   ```bash
   # Watch for the [HYSTERESIS] log lines that report per-window counts
   ssh kevin@10.10.110.223 'sudo journalctl -u wanctl@spectrum --since "5 min ago" --no-pager' | grep HYSTERESIS
   ```
6. **Repeat 3 times** for statistical confidence (3x 60s RRUL = 3 windows of suppression data)

### Decision Gate

| Measured Rate | Action |
|---|---|
| <= 20/min | Confirm current values, document, close phase (SC-3) |
| 21-30/min | A/B test dwell_cycles 5 vs 7 (one parameter only) |
| > 30/min | A/B test dwell_cycles 5 vs 7, then deadband_ms if still above |

### A/B Test Protocol (if needed, Success Criteria 2)

For each candidate value:
1. Edit `/etc/wanctl/spectrum.yaml` on cake-shaper (change one parameter)
2. Hot-reload: `ssh kevin@10.10.110.223 'sudo kill -USR1 $(pgrep -f wanctl)'`
3. Wait 60s for window to reset
4. Run 3x flent RRUL (60s each) with 30s gap between runs
5. Record: suppression count (from health endpoint), ICMP median, ICMP p99, DL throughput, UL throughput, zone distribution
6. Compare against baseline using same metrics

### Candidate Test Matrix

Based on prior A/B testing and DOCSIS jitter characteristics:

| Parameter | Current | Candidate 1 | Candidate 2 | Rationale |
|---|---|---|---|---|
| dwell_cycles | 5 | 7 | 10 | Longer dwell absorbs more DOCSIS MAP scheduling jitter (250ms -> 350ms -> 500ms) |
| deadband_ms | 3.0 | 5.0 | -- | Already validated 3.0 > 5.0 in v1.26; retest only if dwell change alone is insufficient |

**Important:** Do NOT test both parameters simultaneously. Test dwell_cycles first. If that brings rate below 20/min, keep deadband_ms unchanged.

## Common Pitfalls

### Pitfall 1: Testing Both Parameters Simultaneously
**What goes wrong:** Cannot attribute improvement to either parameter. Prior v1.26 methodology: 49 flent runs, 13 params, one at a time.
**How to avoid:** Test dwell_cycles first. Apply winner. Then test deadband_ms if still above threshold.
[VERIFIED: v1.26 roadmap, memory entries]

### Pitfall 2: Increasing Dwell Too Much Masks Real Congestion
**What goes wrong:** dwell_cycles=10 means 500ms before GREEN->YELLOW fires. Real congestion sustained for 500ms is already causing user-visible latency before the controller reacts.
**How to avoid:** Monitor p99 latency alongside suppression rate. If p99 increases while suppression rate decreases, the dwell is too high.
[VERIFIED: .planning/research/PITFALLS.md:206-228]

### Pitfall 3: Confusing Controller Jitter with Network Jitter
**What goes wrong:** The 31/min suppression rate included contributions from the controller's own I/O overhead (subprocess tc forks, synchronous SQLite writes). Phases 154-155 removed these. If the rate drops below 20/min post-v1.31, it was the controller's own jitter, not network jitter.
**How to avoid:** Measure post-v1.31 first. If rate is already below threshold, don't tune -- the problem was already fixed.
[ASSUMED]

### Pitfall 4: Running flent from cake-shaper VM
**What goes wrong:** Netperf traffic goes through the CAKE qdiscs on the VM itself, creating a feedback loop where the test traffic is shaped by the system under test.
**How to avoid:** Always run flent from dev machine. Traffic flows: dev -> MikroTik -> cake-shaper bridge -> internet.
[VERIFIED: CLAUDE.md memory entries]

### Pitfall 5: Dead Config Key Confusion
**What goes wrong:** Operator edits `suppression_alert_pct` in YAML thinking it controls the alert threshold. It does not -- the code reads `suppression_alert_threshold` (default 20). Changes to `suppression_alert_pct` have no effect.
**How to avoid:** Fix the dead config key as part of this phase (see Config Key Discovery section).
[VERIFIED: codebase grep confirmed suppression_alert_pct never read by src/]

### Pitfall 6: Not Waiting for Window Boundary
**What goes wrong:** Reading health endpoint suppression count mid-window gives a partial count. The counter resets every 60s.
**How to avoid:** Wait for 60s window to complete. Check `window_start_epoch` in health endpoint to know when current window started. Log lines at window boundary report the full window's count.
[VERIFIED: wan_controller.py:1746-1786, queue_controller.py:326-336]

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Suppression measurement | Custom metrics collection | Health endpoint `/health` + existing 60s windowed counter | Already built in Phase 136, per-direction tracking, alert threshold comparison |
| Parameter hot-reload | Restart service for each test | SIGUSR1 (`kill -USR1 $(pgrep -f wanctl)`) | Already built in Phase 122, reloads dwell_cycles + deadband_ms from YAML without restart |
| Load generation | Custom traffic generator | `flent rrul -H 104.200.21.31 -l 60` | Established methodology from v1.26 (49 runs across 13 params) |
| Alert threshold tuning | Manual log parsing | `_suppression_alert_threshold` + AlertEngine | Already built in Phase 136, Discord alerts when rate > threshold |

## Code Examples

### Reading Suppression Rate from Health Endpoint

```bash
# From dev machine during RRUL test
ssh kevin@10.10.110.223 'curl -s http://127.0.0.1:9101/health' | \
  jq '{
    dl_suppressions: .wans[0].download.hysteresis.suppressions_per_min,
    ul_suppressions: .wans[0].upload.hysteresis.suppressions_per_min,
    alert_threshold: .wans[0].download.hysteresis.alert_threshold_per_min,
    dl_state: .wans[0].download.state,
    ul_state: .wans[0].upload.state
  }'
```
[VERIFIED: health_check.py:271-289]

### Hot-Reloading Hysteresis Parameters

```bash
# Edit YAML
ssh kevin@10.10.110.223 'sudo sed -i "s/dwell_cycles: 5/dwell_cycles: 7/" /etc/wanctl/spectrum.yaml'

# Hot-reload via SIGUSR1
ssh kevin@10.10.110.223 'sudo kill -USR1 $(pgrep -f wanctl)'

# Verify reload took effect (check journalctl for [HYSTERESIS] Config reload)
ssh kevin@10.10.110.223 'sudo journalctl -u wanctl@spectrum --since "30 sec ago" --no-pager' | grep HYSTERESIS
```
[VERIFIED: wan_controller.py:1391-1465]

### Running RRUL Test from Dev Machine

```bash
# Standard RRUL test (60s, against dallas netperf server)
flent rrul -H 104.200.21.31 -l 60 -t "p157-dwell5-baseline"

# Save output for comparison
flent rrul -H 104.200.21.31 -l 60 -o /tmp/p157-dwell5-baseline.flent.gz -t "p157-dwell5-baseline"
```
[VERIFIED: docs/CABLE_TUNING.md:545, .planning/cake-ceiling-sweep-nighttime-2026-04-05.md]

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.x |
| Config file | pyproject.toml [tool.pytest.ini_options] |
| Quick run command | `.venv/bin/pytest tests/test_queue_controller.py tests/test_hysteresis_observability.py -v --timeout=10` |
| Full suite command | `.venv/bin/pytest tests/ -v` |

### Phase Requirements to Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| TUNE-01 (measure) | Suppression rate measured under RRUL | manual (production) | N/A -- requires flent + production | N/A |
| TUNE-01 (tune) | dwell/deadband A/B tested if rate > 20/min | manual (production) | N/A -- requires flent + production | N/A |
| TUNE-01 (confirm) | Values confirmed correct if rate <= 20/min | manual (production) | N/A -- observation + documentation | N/A |

### Sampling Rate
- **Per task:** No code changes expected -- purely operational measurement phase
- **If dead config key fixed:** `.venv/bin/pytest tests/test_hysteresis_observability.py -v --timeout=10`

### Wave 0 Gaps
None -- existing test infrastructure covers all hysteresis unit tests. This phase is operational (measurement + config tuning), not code development.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Phases 154-155 changes will reduce suppression rate because they removed controller I/O jitter from the hot path | Net Effect Prediction | LOW -- if wrong, we still A/B test as planned |
| A2 | The 31/min measurement was accurate and representative of steady-state behavior | Summary | LOW -- we re-measure anyway |
| A3 | dwell_cycles=7 is a reasonable candidate if 5 is insufficient | Candidate Test Matrix | LOW -- if 7 is too aggressive, test 6 or revert |

## Open Questions

1. **When was the 31/min suppression rate last measured?**
   - What we know: STATE.md lists it as a known issue, research/FEATURES.md says it was measured post-v1.28 DSCP
   - What's unclear: Exact date and conditions of measurement
   - Recommendation: Re-measure as the first step of Phase 157; the old number may no longer be accurate

2. **Should the dead `suppression_alert_pct` config key be fixed in this phase?**
   - What we know: The key is unused. The code reads `suppression_alert_threshold` (default 20).
   - What's unclear: Whether to keep percent-based threshold or explicit count
   - Recommendation: Fix it in this phase since we're already touching hysteresis config. Use explicit count (simpler, matches code). Remove `suppression_alert_pct`, add `suppression_alert_threshold: 20`.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| flent | A/B testing | Needs verification | -- | Install via `pip install flent` on dev machine |
| netperf (dallas) | flent target server | Assumed (104.200.21.31:2112) | -- | No fallback -- required |
| cake-shaper VM | Production target | Assumed (10.10.110.223) | -- | No fallback -- required |
| jq | Health endpoint parsing | Needs verification | -- | Python json.tool fallback |

**Missing dependencies with no fallback:**
- netperf server on dallas and cake-shaper VM are both required and assumed available

## Sources

### Primary (HIGH confidence)
- `src/wanctl/queue_controller.py` -- dwell timer, deadband, windowed counter implementation
- `src/wanctl/wan_controller.py` -- window check, SIGUSR1 reload, alert firing, health data facade
- `src/wanctl/health_check.py` -- health endpoint hysteresis section rendering
- `configs/spectrum.yaml` -- production config with current parameter values
- `.planning/research/PITFALLS.md:206-228` -- DOCSIS jitter bimodal distribution pitfall analysis
- `.planning/research/FEATURES.md:174-194` -- hysteresis tuning feature analysis with test matrix
- `.planning/milestones/v1.27-phases/136-hysteresis-observability/` -- Phase 136 context and verification

### Secondary (MEDIUM confidence)
- Memory entries: `feedback_dwell_cycles_5_validated.md`, `feedback_deadband_3_validated.md` -- prior A/B test data
- `.planning/milestones/v1.26-ROADMAP.md` -- A/B testing methodology (49 flent runs, 13 params)

### Tertiary (LOW confidence)
- None

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- no new libraries, purely operational measurement + config changes
- Architecture: HIGH -- all hysteresis infrastructure verified in codebase, no code changes needed
- Pitfalls: HIGH -- DOCSIS jitter pitfalls well-documented in prior research, A/B methodology proven

**Research date:** 2026-04-09
**Valid until:** 2026-05-09 (stable -- hysteresis infrastructure unchanged since v1.27)
