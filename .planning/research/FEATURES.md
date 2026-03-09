# Feature Research

**Domain:** WAN-Aware Steering for Dual-WAN Controller
**Researched:** 2026-03-09
**Confidence:** HIGH

## Feature Landscape

### Table Stakes (Users Expect These)

Features that any WAN-aware failover enhancement must have. Missing these = the feature is broken or dangerous in production.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Autorate exports dl_state to state file | Steering cannot consume what autorate does not publish. Currently `save_state()` writes streaks and EWMA but NOT the resolved `dl_zone` (GREEN/YELLOW/SOFT_RED/RED). The zone is already computed every cycle but discarded after logging. | LOW | Add `congestion.dl_state` (and `ul_state`) fields to `WANController.save_state()`. The `dl_zone` variable is already in scope from `run_cycle()` line 1430. ~3 line change. |
| Steering reads WAN state from autorate state file | Core data path for the entire milestone. Follows the existing `BaselineLoader` pattern that already reads `ewma.baseline_rtt` from the same JSON file (`/run/wanctl/spectrum_state.json`). | LOW | Extend `BaselineLoader` or create parallel `WanStateLoader` to extract `congestion.dl_state`. Same file, same atomic read, same staleness check. ~15 lines. |
| Sustained SOFT_RED/RED before failover trigger | Every production dual-WAN controller uses sustained degradation detection. Transient spikes must not trigger failover. pfSense uses "trigger level" with time-averaged dpinger probes; OPNsense uses configurable time periods (must be >= 2x probe interval + loss interval); Fortinet uses "Monitor Fail Hold Up Time" (ms); Cisco uses link-flap prevention with 10s thresholds; VRRP uses failover-delay timers (500ms-10s). wanctl already has `sustain_duration` in `ConfidenceController`. | MEDIUM | WAN zone signal becomes an additive contributor to existing `compute_confidence()`. Sustained WAN RED/SOFT_RED boosts confidence above `steer_threshold` (55). Existing `TimerManager.update_degrade_timer()` then counts down `sustain_duration` (2s). No new timer infrastructure needed. |
| Sustained GREEN before recovery | Recovery must be slower than failover (asymmetric timers). Every major platform does this: pfSense can kill states on failback or wait for natural expiry; OPNsense evaluates over configurable time_period; VRRP uses separate failover-delay for recovery. wanctl already has `recovery_sustain_sec` (3s) in confidence config. | MEDIUM | Existing `TimerManager.update_recovery_timer()` already checks `cake_state == "GREEN"` and `rtt_delta < 10.0` and `drops < 0.001`. Add `wan_state in ("GREEN", None)` to recovery eligibility check. ~3 lines. |
| CAKE stats remain primary signal (WAN is secondary/amplifying) | CAKE has ground truth about local queue congestion. WAN RTT can spike from unrelated causes (ISP routing changes, probe path issues, DNS hiccups). PROJECT.md explicitly states: "Existing CAKE stats remain primary signal; WAN state is secondary/amplifying." | LOW | Architectural constraint enforced by weight values. Existing `ConfidenceWeights.RED_STATE = 50` is near threshold (55). WAN RED adds 20-25 points on top. CAKE GREEN (0) + WAN RED (25) = 25 < 55 threshold. WAN alone never steers. |
| Configurable thresholds in YAML | Production tuning without code changes. Pattern established in `configs/steering.yaml` `confidence:` section. PROJECT.md explicitly requires "Configurable thresholds in YAML for production tuning." | LOW | Add `wan_state:` subsection under `confidence:` with keys: `enabled`, `wan_red_weight`, `wan_soft_red_weight`, `wan_yellow_weight`, `startup_grace_sec`. ~6 lines in YAML, matching config loader pattern. |
| Graceful degradation when autorate unavailable | Autorate daemon may restart, state file may be stale or missing. Steering must continue operating with CAKE-only signals. `BaselineLoader._check_staleness()` already warns when state file is >5min old and `load_baseline_rtt()` returns None when unavailable. | LOW | WAN state loader returns None when state unavailable. Confidence computation skips WAN weight when None. Steering continues with CAKE-only assessment. No new failure mode. |
| Backward compatibility (pre-upgrade state files) | During rolling upgrades, autorate may not yet export the `congestion` key. Steering must not crash or misbehave. | LOW | `state.get("congestion", {}).get("dl_state", None)` -- None means "no WAN signal available, use CAKE only." Standard defensive coding pattern already used throughout codebase. |

### Differentiators (Competitive Advantage)

Features that make wanctl's WAN-aware steering better than commodity dual-WAN failover. Not required for correctness, but provide production quality advantages no competitor offers.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| SOFT_RED as pre-failure early warning | Unlike binary UP/DOWN failover in pfSense/OPNsense/MikroTik, wanctl detects the pre-failure state where CAKE has clamped bandwidth to floor (45-80ms RTT delta) but ISP has not fully degraded. This is a 5-10 second early warning before RED. No gateway-monitoring-based system can provide this because they only see probe reachability, not queue shaping state. | LOW | SOFT_RED already computed by autorate. Weight it at 10-15 confidence points. Sustained SOFT_RED (alone) won't trigger steering (10-15 < 55 threshold) but SOFT_RED + CAKE YELLOW (10) + drops (10) = 30-35, approaching threshold. Creates the "building congestion" detection pattern. |
| Confidence score integration (not separate decision path) | Instead of adding a parallel state machine, WAN zone feeds into the existing `compute_confidence()` scoring as another additive signal. Preserves the proven multi-signal architecture. The same sustain timers, flap detection, hold-down, and dry-run mode all apply automatically. | MEDIUM | Add `ConfidenceWeights.WAN_SOFT_RED_SUSTAINED` (10-15 points) and `ConfidenceWeights.WAN_RED_SUSTAINED` (20-25 points). History check: require last N cycles to be SOFT_RED/RED before contributing points (mirroring existing `SOFT_RED_SUSTAINED` pattern that checks last 3 cycles). |
| Health endpoint exposure of WAN awareness | Operators see what autorate reports (`dl_state`), staleness, zone sustained cycles, whether WAN signal influenced the last decision, and the confidence contribution. Essential for production debugging. | LOW | Extend `SteeringHealthHandler._get_health_status()` with `wan_awareness: {autorate_zone, staleness_sec, sustained_cycles, confidence_contribution, amplifying}`. Port 9102 health endpoint already exposed. |
| SQLite metrics for WAN awareness events | Post-hoc analysis: was WAN awareness helping or hurting? Did it trigger false positives? How often does CAKE GREEN + WAN RED occur? | LOW | Record `wanctl_wan_awareness_signal` metric with labels `{zone, confidence_boost}` each cycle. Record `wanctl_wan_awareness_amplification` when WAN signal materially contributed to a steering decision. Uses existing `MetricsWriter`. |
| Startup grace period | Autorate needs ~50-100 cycles to establish stable baseline RTT after daemon start. During startup, WAN state may be stale or unreliable (from pre-restart values). | LOW | Ignore WAN signal for first N seconds (`startup_grace_sec`, configurable, default 30s). Simple monotonic-clock check in the WAN state reader. |
| RTT delta exported in autorate state file | Convenience: steering could use autorate's computed RTT delta directly for supplementary scoring without recomputing from separate ping. Already computed as `load_rtt - baseline_rtt`. | LOW | Add `congestion.rtt_delta_ms` to autorate state alongside `dl_state`. One additional field in the state dict. |

### Anti-Features (Commonly Requested, Often Problematic)

Features that seem good but create problems in this specific context.

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| WAN state overrides CAKE state | "Autorate knows the ISP is degraded, just use that directly for steering." | Violates "CAKE is primary" architecture. CAKE has ground truth about local queue congestion (drops, queue depth, bandwidth utilization). WAN RTT can spike from unrelated causes. If autorate says RED but CAKE shows GREEN, steering would be unnecessary -- the shaping is handling it. This creates false positives. | WAN state amplifies confidence additively. CAKE RED (50) + WAN RED (25) = 75 > threshold. CAKE GREEN (0) + WAN RED (25) = 25 < threshold. WAN alone never steers. |
| Bidirectional state sharing (steering writes back to autorate) | "Steering should tell autorate it activated failover so autorate can adjust its behavior." | Creates circular dependency between daemons. Autorate must remain link-agnostic per PORTABLE_CONTROLLER_ARCHITECTURE.md. Steering decisions must not affect baseline RTT measurement. Back-channel violates unidirectional data flow that keeps both daemons simple and testable. | Unidirectional only: autorate publishes state, steering reads state. No back-channel. |
| Real-time IPC (shared memory, Unix sockets, pipes) | "File polling is slow, use shared memory for sub-millisecond notification." | Over-engineering. Steering polls at 500ms cycles. Autorate writes state atomically on tmpfs (`/run/wanctl/`) every 50ms. File read latency is <1ms on tmpfs. Worst-case propagation delay is one steering cycle (500ms), acceptable for a signal requiring ~1s sustained confirmation. IPC adds complexity, new failure modes, and daemon coupling. File-based sharing handles crashes gracefully (state persists). | Continue JSON state file sharing via `/run/wanctl/`. Already proven, atomic, debuggable (`cat state.json`), crash-resilient. |
| Automatic parameter tuning / ML | "The system should learn optimal weight values over time." | ML-adjacent, hard to test, can diverge. PROJECT.md explicitly marks "ML-based bandwidth prediction" as out of scope. Self-tuning weights introduce unpredictable behavior in a production network controller. | Fixed weights in YAML. Log enough telemetry for informed manual tuning. Operators adjust based on ISP behavior. |
| Kill existing connections on failover | "When steering activates, migrate all TCP connections to alternate WAN." | Breaks TCP sessions. pfSense "kill states" documented as problematic (Bug #5090: "WAN failover fails to recover normal behaviour"; Bug #9054: "Gateway Group slow or never to switch back to Tier 1"). wanctl design is deliberately conservative: only new latency-sensitive connections rerouted. | Continue routing only new connections via mangle rule toggle. Existing connections stay on primary WAN and expire naturally. |
| Per-direction WAN awareness (separate upload zone) | "Upload might be congested while download is fine." | Upload uses 3-state logic (no SOFT_RED). Upload congestion rarely affects latency-sensitive traffic (primarily download: video, voice, gaming). Two directions doubles state surface for minimal benefit. Download zone is the authoritative ISP health signal. | Monitor download zone only. Upload congestion handled by CAKE upload queue shaping independently. |
| WAN state EWMA smoothing | "Apply EWMA to the zone signal to smooth transients." | Double-smoothing. Autorate's zone is already the product of EWMA-smoothed RTT + 4-state hysteresis (streak counters: soft_red_required=3, green_required=5). Smoothing an already-smoothed signal delays detection without adding reliability. | Use zone state directly. Require sustained cycles (N consecutive same-zone) instead of EWMA for temporal filtering. |
| Separate WAN state polling interval | "Poll autorate state at a different rate than CAKE stats." | Timer complexity. Steering already reads the autorate state file every cycle for baseline RTT. | Read WAN state in the same file read as baseline RTT. One `safe_json_load_file()` call, two data points extracted. |

## Feature Dependencies

```
[Autorate exports dl_state in state file]
    |
    +--required-by--> [Steering reads WAN state (extends BaselineLoader)]
    |                     |
    |                     +--required-by--> [Map 4-state to confidence weight]
    |                     |                     |
    |                     |                     +--required-by--> [Sustained WAN RED triggers failover]
    |                     |                     |    (via elevated confidence -> existing sustain timer)
    |                     |                     |
    |                     |                     +--required-by--> [Sustained WAN GREEN allows recovery]
    |                     |                          (via lowered confidence -> existing recovery timer)
    |                     |
    |                     +--required-by--> [SOFT_RED as intermediate signal]
    |                     |                     (additional weight in confidence computation)
    |                     |
    |                     +--enhances-----> [Health endpoint exposure]
    |                     |
    |                     +--enhances-----> [SQLite metrics recording]
    |                     |
    |                     +--enhances-----> [Startup grace period]
    |
    +--enhances-----> [RTT delta exported in state file]

[YAML configuration]
    +--required-by--> [Map 4-state to confidence weight]
    +--required-by--> [Sustained WAN RED/GREEN thresholds]
    +--required-by--> [Startup grace period]

[Graceful degradation] --independent-- (defensive coding, no dependency)
[Backward compatibility] --independent-- (defensive coding, no dependency)

CAKE stats remain primary signal = architectural constraint, enforced by weight values
```

### Dependency Notes

- **Autorate state export is the single foundation:** Every other feature depends on autorate writing `congestion.dl_state` to the state file. This is a ~3-line change to `WANController.save_state()` -- the `dl_zone` variable is already in scope from `adjust_4state()`.
- **Steering reader depends on autorate writer:** Must be developed and deployed together. Backward compatibility handles the transition (`.get("congestion", {}).get("dl_state", None)`).
- **Confidence weight mapping depends on reader:** Cannot score what has not been read. The weight branch in `compute_confidence()` mirrors the existing `cake_state` branch pattern.
- **Hysteresis is already built:** Sustained degradation/recovery are handled by existing `TimerManager`. WAN-boosted confidence flows through existing infrastructure. No new timer code needed.
- **Health, metrics, and grace period are independent enhancements:** Can be added at any point after the reader exists.
- **No feature conflicts:** All features are additive. None conflicts with another.

## MVP Definition

### Launch With (v1.11.0)

Minimum viable WAN-aware steering. All must work for safe production deployment.

- [ ] Autorate writes `congestion.dl_state` to state file -- foundation for all WAN awareness
- [ ] Steering reads WAN zone from autorate state -- the data path
- [ ] Map autorate 4-state to confidence weight (`WAN_RED`, `WAN_SOFT_RED`) -- signal fusion
- [ ] Sustained WAN RED/GREEN via existing sustain timers -- transient filtering
- [ ] WAN state added to recovery eligibility check -- prevents premature recovery
- [ ] CAKE remains primary (weight values enforce this) -- safety constraint
- [ ] YAML configuration for all WAN awareness parameters -- production tuning
- [ ] Graceful degradation when autorate unavailable -- safety net
- [ ] Backward compatibility for pre-upgrade state files -- safe rollout

### Add After Validation (v1.11.x)

Features to add once WAN awareness is proven working in production.

- [ ] Health endpoint exposes WAN awareness state -- when operators need debugging visibility
- [ ] SQLite metrics for WAN awareness events -- when post-hoc analysis is needed
- [ ] SOFT_RED intermediate weight tuning -- once production shows whether 10 or 15 is optimal
- [ ] Startup grace period -- if startup race condition is observed in production

### Future Consideration (v2+)

Features to defer until the v1.11 approach is validated.

- [ ] Upload zone awareness -- only if download-only proves insufficient
- [ ] RTT delta export in state file -- only if steering needs more granular WAN data
- [ ] Asymmetric WAN-specific sustain timers -- only if shared timers prove too coarse

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| Autorate exports dl_state | HIGH | LOW | P1 |
| Steering reads WAN state | HIGH | LOW | P1 |
| Confidence weight mapping | HIGH | LOW | P1 |
| Sustained degradation (existing infra) | HIGH | LOW | P1 |
| Sustained recovery (existing infra) | HIGH | LOW | P1 |
| YAML configuration | HIGH | LOW | P1 |
| Graceful degradation | HIGH | LOW | P1 |
| Backward compatibility | HIGH | LOW | P1 |
| SOFT_RED intermediate weight | HIGH | LOW | P1 (inherent) |
| Health endpoint exposure | MEDIUM | LOW | P2 |
| SQLite metrics recording | MEDIUM | LOW | P2 |
| Startup grace period | LOW | LOW | P2 |

**Priority key:**
- P1: Must have for launch -- required for correct and safe WAN-aware steering
- P2: Should have, add when possible -- operational visibility and safety margins
- P3: Nice to have, future consideration -- not needed for v1.11

## Signal Priority Model

Recommended additive confidence weights (0-100 scale), designed to enforce "CAKE primary, WAN amplifying":

| Signal | Points | Source | Rationale |
|--------|--------|--------|-----------|
| CAKE RED state | 50 | Existing | Ground truth: local queue drops + high RTT delta + deep queue |
| WAN RED from autorate | 20-25 | NEW | Strong amplifier. Alone: below threshold (55). With CAKE YELLOW (10): approaches threshold. |
| CAKE SOFT_RED sustained | 25 | Existing | RTT-only congestion, confirmed >= 3 cycles |
| RTT delta > 120ms (steering) | 25 | Existing | Severe latency spike |
| WAN SOFT_RED from autorate | 10-15 | NEW | Weak amplifier. ISP struggling, CAKE compensating. Early warning. |
| RTT delta > 80ms (steering) | 15 | Existing | Moderate latency |
| CAKE YELLOW | 10 | Existing | Early warning, queue pressure |
| Drops increasing | 10 | Existing | Trend signal |
| Queue depth sustained | 10 | Existing | Pressure signal |
| WAN YELLOW from autorate | 0-5 | NEW | Informational only. Too noisy for meaningful contribution. |
| WAN GREEN from autorate | 0 | NEW | Healthy. No contribution. |

**Key scenarios showing the gap being closed:**

| CAKE State | WAN State | Score | Outcome | Why |
|------------|-----------|-------|---------|-----|
| RED | RED | 70-75 | STEER (fast) | Both signals agree. High confidence. |
| RED | GREEN | 50 | STEER (normal) | CAKE alone sufficient near threshold. |
| GREEN | RED | 20-25 | HOLD | WAN alone insufficient. Could be ISP routing hiccup. |
| YELLOW | RED | 30-35 | HOLD (borderline) | Needs sustained + additional signals to cross threshold. |
| YELLOW + drops | RED | 45-50 | Near threshold | Multiple signals converging. One more cycle of drops tips it. |
| GREEN | GREEN | 0 | HOLD | All clear. |
| YELLOW | SOFT_RED | 20-25 | HOLD | Early warning. Building congestion detected but not actionable. |

**The critical gap scenario (CAKE GREEN + WAN RED):** Score 20-25, intentionally below 55 threshold. WAN RED alone should NOT steer -- it could be ISP routing change, probe path issue, or transient. But if CAKE starts showing YELLOW or drops trend upward, the combined score approaches threshold. This is "amplifying" behavior: WAN signal lowers the bar for CAKE to trigger steering.

## Existing Infrastructure Reuse

This is a wiring milestone, not a building milestone. Nearly all infrastructure exists.

| What's Needed | What Exists | Gap |
|---------------|-------------|-----|
| Autorate writes dl_state | `WANController.save_state()` writes streaks/EWMA. `dl_zone` in scope at line 1430. | Add `congestion: {dl_state, ul_state}` to state dict (~3 lines) |
| Steering reads WAN state | `BaselineLoader.load_baseline_rtt()` reads same file | Add `load_wan_state()` method (~15 lines) |
| Confidence scoring | `compute_confidence()` with signal contributors | Add WAN state weight branch (~10 lines) |
| Sustain timers | `TimerManager` with degrade/recovery/hold_down | None -- WAN-boosted confidence flows through existing timers |
| Recovery eligibility | Checks `cake_state == "GREEN"`, `rtt_delta < 10`, `drops < 0.001` | Add `wan_state in ("GREEN", None)` to eligibility (~3 lines) |
| Flap detection | `FlapDetector` with window, max_toggles, penalty | None -- protects against all steering oscillation |
| YAML config | `configs/steering.yaml` `confidence:` section | Add `wan_state:` subsection (~6 lines YAML + config loader) |
| Staleness check | `BaselineLoader._check_staleness()` | Replicate for WAN state (~10 lines) |
| Health endpoint | `SteeringHealthHandler._get_health_status()` | Add `wan_awareness` dict (~8 lines) |
| Dry-run mode | `DryRunLogger` in confidence controller | None -- WAN-boosted decisions auto-logged in dry-run |
| Backward compat | `state.get()` pattern used throughout | `.get("congestion", {}).get("dl_state", None)` |

**Estimated net new code: ~60-80 lines production, ~200-300 lines tests.**

## Competitor Feature Analysis

| Feature | pfSense/OPNsense | MikroTik Netwatch | sqm-autorate | wanctl v1.11 (proposed) |
|---------|-------------------|-------------------|--------------|-------------------------|
| Congestion detection | Gateway ping loss/latency via dpinger | ICMP/TCP/HTTP probe UP/DOWN | RTT delta + load threshold | 4-state RTT (GREEN/YELLOW/SOFT_RED/RED) + CAKE stats (drops, queue) + WAN RTT state |
| Failover trigger | Binary: gateway UP or DOWN. "Trigger level" option. | Binary: host reachable or not | N/A (single WAN only) | Multi-signal confidence score with WAN zone amplification |
| Hysteresis | dpinger time-period averaging (must be >= 2x probe + loss intervals) | Configurable probe interval + threshold count | N/A | Asymmetric sustained-cycle counters (fast degrade ~1s, slow recover ~3s) + flap penalty |
| Pre-failure detection | No (binary health only) | No (binary health only) | Yes (rate reduction via RTT) | Yes (SOFT_RED = ISP struggling, CAKE compensating, 5-10s early warning) |
| Recovery behavior | Kill states option (buggy -- #5090, #9054) or wait for natural expiry | Re-enable route immediately (no hold-down) | N/A | New connections only; existing expire naturally; recovery requires sustained GREEN on both CAKE + WAN |
| Flap prevention | No built-in mechanism (bugs filed) | No built-in mechanism | N/A | FlapDetector with sliding window, max_toggles, and penalty threshold escalation |
| State sharing | N/A (monolithic) | N/A (monolithic) | N/A (single daemon) | Unidirectional file-based: autorate publishes, steering reads. Crash-resilient, atomic. |
| Configuration | GUI + XML | CLI/Winbox | Shell variables | YAML with schema validation + config_validation_utils |

**Key differentiator:** wanctl is the only system that combines local queue congestion (CAKE drops, queue depth, shaping state) with end-to-end WAN RTT health (4-state model) for steering decisions. Commercial SD-WAN platforms (Meraki, Versa, Fortinet) do similar multi-signal scoring but at enterprise scale/cost. No open-source dual-WAN controller provides this combination.

## Sources

- pfSense gateway groups: [pfSense Gateway Groups](https://docs.netgate.com/pfsense/en/latest/routing/gateway-groups.html)
- pfSense gateway settings: [pfSense Gateway Settings](https://docs.netgate.com/pfsense/en/latest/routing/gateway-configure.html)
- pfSense failback bugs: [Bug #9054](https://redmine.pfsense.org/issues/9054), [Bug #5090](https://redmine.pfsense.org/issues/5090)
- OPNsense multi-WAN: [OPNsense Multi WAN](https://docs.opnsense.org/manual/how-tos/multiwan.html)
- OPNsense gateway groups: [OPNsense Gateway Groups](https://docs.opnsense.org/manual/multiwan.html)
- MikroTik Netwatch: [RouterOS Netwatch](https://help.mikrotik.com/docs/spaces/ROS/pages/8323208/Netwatch)
- Juniper VRRP failover-delay: [VRRP Failover Delay](https://www.juniper.net/documentation/us/en/software/junos/high-availability/topics/concept/vrrp-failover-delay-overview.html)
- Cisco link flap prevention: [Cisco Link Flap Prevention](https://www.cisco.com/c/en/us/support/docs/smb/switches/cisco-350-series-managed-switches/smb5783-configure-the-link-flap-prevention-settings-on-a-switch-thro.html)
- Fortinet failover timers: [FortiGate Convergence Timers](https://community.fortinet.com/t5/FortiGate/Technical-Tip-Timers-used-for-speedup-Convergence-Failover-and/ta-p/292053)
- sqm-autorate project: [sqm-autorate GitHub](https://github.com/sqm-autorate/sqm-autorate)
- Existing wanctl source code: `autorate_continuous.py`, `steering/daemon.py`, `steering/steering_confidence.py`, `steering/congestion_assessment.py`, `wan_controller_state.py`, `state_utils.py`, `state_manager.py` (HIGH confidence -- direct code inspection)

---
*Feature research for: WAN-Aware Steering for Dual-WAN Controller*
*Researched: 2026-03-09*
