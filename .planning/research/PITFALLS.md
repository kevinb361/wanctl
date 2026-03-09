# Domain Pitfalls: Adding WAN-Aware Steering to Existing Dual-WAN Controller

**Domain:** Inter-daemon WAN state sharing for congestion-aware steering
**Researched:** 2026-03-09
**Confidence:** HIGH (grounded in actual codebase analysis of 16,493 LOC + control systems principles)
**Focus:** Race conditions, oscillation/flapping, stuck states, backward compatibility, production stability

---

## Critical Pitfalls

Mistakes that cause production routing failures, network outages, or require architectural rewrites.

---

### Pitfall 1: Autorate State File Does Not Contain the WAN Zone

**What goes wrong:** Steering tries to read autorate's congestion zone (GREEN/YELLOW/SOFT_RED/RED) from the state file at `/run/wanctl/spectrum_state.json`, but the field does not exist. The current `WANControllerState.save()` (line 1619, `autorate_continuous.py`) persists only: `download.{green_streak, soft_red_streak, red_streak, current_rate}`, `upload.{same}`, `ewma.{baseline_rtt, load_rtt}`, `last_applied.{dl_rate, ul_rate}`, and `timestamp`. The actual zone string ("GREEN", "YELLOW", "SOFT_RED", "RED") is computed fresh each cycle by `download.adjust_4state()` and passed to metrics/logs but never written to the state file.

**Why it happens:** The state file was designed for crash recovery (restoring hysteresis counters and EWMA values), not for inter-process communication. The zone is a derived value from streak counters + RTT thresholds.

**Consequences:**
- Steering gets KeyError/None when reading `dl_zone` from the state file
- If steering attempts to reverse-engineer zone from `red_streak > 0`, it gets a different answer than autorate's actual zone assessment (streak counters are updated before zone is computed, creating a timing window)
- The entire milestone is blocked until autorate publishes the zone

**Prevention:**
- Modify `WANControllerState.save()` to include `dl_zone` and `ul_zone` as explicit string fields
- Add a `schema_version` field (value: 2) so steering can detect old-format files gracefully
- Steering must treat missing `dl_zone` as GREEN (fail-safe default) with a logged warning
- NEVER reverse-engineer zone from streak counters -- the zone is autorate's conclusion

**Detection:** Steering logs "WAN zone field missing from state file, treating as GREEN" on every cycle until autorate is updated.

**Phase:** MUST be the FIRST implementation step. Creates a hard dependency: autorate state file change ships before steering reads it.

---

### Pitfall 2: Dirty Tracking Regression -- 20x Disk Write Amplification

**What goes wrong:** Adding `dl_zone` to the autorate state dict causes `WANControllerState._is_state_changed()` (line 51, `wan_controller_state.py`) to detect changes every cycle because the zone toggles between GREEN and YELLOW frequently during normal operation. Disk writes jump from approximately 1/second to 20/second (every 50ms cycle). Each write calls `atomic_write_json()` with `os.fsync()`, consuming I/O bandwidth in the hot loop.

**Why it happens:** Dirty tracking (line 66-72, `wan_controller_state.py`) compares the full state dict including all fields. Zone is a volatile field that changes far more frequently than the streak counters and EWMA values that the dirty tracking was designed to filter.

**Consequences:**
- `fsync()` latency (typically 0.1-2ms on tmpfs, 5-50ms on ext4) added to every 50ms cycle
- Flash wear on embedded storage deployments
- Cycle overrun rate increases, degrading congestion response time
- The autorate profiling infrastructure (`PerfTimer("autorate_state_management")`) will show this immediately as state_management time spiking

**Prevention -- Two viable approaches:**

Option A (recommended): Write WAN zone to a **separate lightweight file** (e.g., `/run/wanctl/spectrum_wan_zone.json`) that is written only on zone transitions, bypassing dirty tracking entirely. Zone transitions are infrequent (a few per minute under congestion, zero during steady state).

Option B: Add the zone to the existing state dict but **exclude it from dirty tracking comparison** by modifying `_is_state_changed()` to compare a subset of fields (everything except `dl_zone`, `ul_zone`).

**Detection:** Monitor `WANControllerState.save()` return value (True = wrote, False = skipped). If True rate jumps from ~1/s to 20/s after the change, dirty tracking is broken. The existing profiling infrastructure (`--profile` flag, `autorate_state_management` timer) will surface this.

**Phase:** Directly impacts the autorate state file modification. Must be profiled before production deployment.

---

### Pitfall 3: Stale State Causing Phantom Congestion or Stuck DEGRADED

**What goes wrong:** Autorate crashes while its zone is RED. The state file persists with RED zone indefinitely. Steering reads the stale RED, activates steering, and holds it in DEGRADED state until autorate restarts. Alternatively: during autorate's steady GREEN operation, dirty tracking skips writes (`_is_state_changed()` returns False), so `st_mtime` stops advancing. The existing staleness check (`BaselineLoader._check_staleness()`, line 620, `steering/daemon.py`) uses a 300-second threshold -- far too long for a signal that should represent sub-second congestion state.

**Why it happens:** Two independent staleness mechanisms interact:
1. `atomic_write_json()` only writes when dirty tracking says "changed"
2. Baseline staleness is checked at 300s because baseline RTT changes slowly
3. WAN zone changes faster than baseline but slower than raw RTT -- no existing staleness mechanism fits

The current steering baseline loading pattern reads the file every cycle (line 1313-1316 of `steering/daemon.py`, `update_baseline_rtt()`) but only checks staleness for baseline RTT, not for zone data.

**Consequences:**
- Autorate crash + RED state = steering stuck in DEGRADED until restart
- Autorate restart takes ~10s (systemd ExecStart, initialization) -- 10 seconds of phantom steering
- If `StartLimitBurst=5` triggers and autorate doesn't restart, stuck DEGRADED until manual intervention
- User loses internet reliability because all latency-sensitive traffic routes to slower ATT WAN

**Prevention:**
- WAN zone staleness threshold: 5 seconds (matches the milestone context specification)
- Read both `st_mtime` of the file AND the `timestamp` field inside the JSON (belt and suspenders)
- Stale + RED = treat as GREEN (fail-safe: if we don't know, assume healthy)
- Stale + GREEN = treat as GREEN (no action needed)
- Stale + any = log WARNING with file age
- If the separate zone file approach (Pitfall 2 Option A) is used, the zone file will have its own `st_mtime` that advances only on zone transitions, making staleness detection simpler

**Detection:** Log `wan_zone_age_sec` every cycle. Alert if age > 5s. Health endpoint should expose `wan_state.stale: true/false`.

**Phase:** Must be addressed in the WAN state reader implementation. Highest-risk integration point.

---

### Pitfall 4: Signal Conflict -- CAKE Says GREEN, WAN RTT Says RED

**What goes wrong:** Autorate's download zone is RED (ISP backbone congestion detected via RTT spikes) while steering's own CAKE stats show GREEN (local queue healthy, no drops, no backlog). Without explicit conflict resolution, the system either: (a) ignores WAN RED entirely (defeating the feature), (b) triggers steering on ISP transients that CAKE correctly filters out, or (c) requires both to agree (making the system more conservative than before -- the opposite of the goal).

**Why it happens:** CAKE stats measure LOCAL queue health (backlog, drops at the home router). WAN RTT measures END-TO-END path quality. These observe different phenomena. ISP peering congestion raises WAN RTT without causing CAKE drops (bottleneck is upstream). Conversely, local buffer overrun causes CAKE RED without necessarily raising WAN RTT.

**The specific gap this milestone targets:** SOFT_RED in autorate means "CAKE has clamped to floor" -- the only lever left is routing. This is the case where WAN state provides unique value. But SOFT_RED is NOT the same as ISP congestion; it means local queue tuning hit its minimum.

**Consequences:**
- If WAN RED can independently trigger steering: false positives during ISP transients
- If WAN RED is ignored when CAKE is GREEN: feature provides zero value
- Combined with ConfidenceController's additive scoring, the interaction is non-obvious

**Prevention -- Define explicit fusion rules:**
- WAN RED + CAKE RED = fast-track (both agree, reduce sustain timer -- this is the v1.11 goal)
- WAN RED + CAKE YELLOW = promote to RED-equivalent (WAN confirms early warning)
- WAN RED + CAKE GREEN = **no action** (CAKE is authoritative for local queue health)
- WAN SOFT_RED + any CAKE state = treat as WAN YELLOW (moderate signal)
- WAN GREEN/YELLOW = zero effect on steering (normal operation)
- WAN state NEVER independently triggers DEGRADED -- it only amplifies existing CAKE signals

**Implementation in existing architecture:** Add `wan_zone` weight to `ConfidenceWeights` in `steering_confidence.py`:
- `WAN_RED_WITH_CAKE_SIGNAL = 20` (only applied when CAKE is YELLOW or worse)
- `WAN_RED_ALONE = 0` (explicitly zero -- WAN RED cannot contribute without CAKE corroboration)

**Detection:** Log both signals side-by-side. Monitor for WAN RED + CAKE GREEN lasting >30s -- this is the "ISP transient" pattern that should NOT trigger steering.

**Phase:** Architecture decision in the signal fusion design phase. Must be the first design document before any code.

---

### Pitfall 5: Oscillation Amplification -- Faster Degrade, Same Recovery

**What goes wrong:** Adding WAN state creates a faster path to DEGRADED (WAN RED amplifies CAKE YELLOW to cross the confidence threshold sooner) but recovery still requires the same `green_samples_required=15` consecutive GREEN samples (7.5s at 0.5s interval) plus `recovery_sustain_sec=3.0`. The asymmetry becomes too aggressive: easier to enter DEGRADED, same difficulty to exit.

Under intermittent congestion, this increases time spent in DEGRADED. More traffic on ATT means ATT gets loaded, which can degrade ATT performance, which means steering's own RTT measurements (to 1.1.1.1 via Spectrum) may improve while ATT suffers -- a cascade the system cannot detect.

**Why it happens:** The existing hysteresis is tuned for single-signal behavior. `red_samples_required=2` at 0.5s interval = 1 second to degrade. Adding WAN RED to the confidence score can bring total score from 50 (CAKE RED alone) to 70 (CAKE RED + WAN RED), which crosses the `steer_threshold=55` faster. But nothing changes on the recovery side.

**Consequences:**
- Increased time in DEGRADED state
- ATT link receives more traffic, potentially saturating it
- `FlapDetector` engages more often (>4 toggles in 5 minutes), adding `penalty_threshold_add=15` to the steer threshold -- making recovery even slower
- Net effect: worse user experience than before the feature was added

**Prevention:**
- If WAN state accelerates the degrade path, proportionally reduce recovery requirements (e.g., from 15 GREEN samples to 10, or reduce `recovery_sustain_sec` from 3.0 to 2.0)
- Better: have WAN state affect ONLY the confidence score, not the hysteresis counters. The ConfidenceController already has separate degrade and recovery thresholds that can be tuned independently
- Add an invariant test: "WAN RED alone (without CAKE RED) never causes more than +20 to confidence score"
- Add an integration test: simulate intermittent WAN RED (alternating 2s RED / 2s GREEN) with stable CAKE GREEN, verify zero state transitions
- Monitor state transition frequency before and after enabling WAN signal. If transitions/hour increases by >50%, the signal weight is too aggressive

**Detection:** Compare `wanctl_steering_transition` metric rate before/after deployment. Track `FlapDetector` engagement rate.

**Phase:** Must be addressed alongside signal fusion. Needs explicit invariant tests.

---

## Moderate Pitfalls

---

### Pitfall 6: 50ms Hot Loop Blocking on File Read

**What goes wrong:** The steering daemon's `run_cycle()` (line 1305, `steering/daemon.py`) already reads the autorate state file once per cycle via `update_baseline_rtt()` -> `BaselineLoader.load_baseline_rtt()` -> `safe_json_load_file()`. Adding WAN zone reading means a second file read in the hot path. While `safe_json_load_file()` is fast on tmpfs (~0.1ms), on degraded I/O conditions (disk full, NFS mount, high load average), it can block.

**Why it happens:** `safe_json_load_file()` does synchronous `open()` + `json.load()`. No timeout mechanism. On tmpfs this is safe; on real filesystems under load, `open()` can block on directory lookup.

**Consequences:**
- If both baseline and zone reads are from the same file, no additional I/O (same `open()` call, just different field extraction)
- If zone is in a separate file (Pitfall 2 Option A), each cycle does TWO file opens instead of one
- Under I/O pressure, cycle overrun increases, degrading congestion response

**Prevention:**
- If possible, read zone from the SAME state file as baseline RTT (already opened per cycle) -- zero additional I/O
- If a separate file is needed, cache the zone in memory and only re-read when `st_mtime` changes (stat is cheaper than open+parse)
- Never add a file lock between autorate and steering -- POSIX atomic rename is sufficient for the data freshness requirements
- Accept one-cycle staleness (50ms for autorate's file, 500ms for steering's read interval) -- negligible for a secondary signal with 1-3 second hysteresis

**Detection:** `PerfTimer("steering_state_management")` in `run_cycle()` will capture any I/O latency increase.

**Phase:** Implementation detail during WAN state reader. Decide same-file vs separate-file early.

---

### Pitfall 7: Over-Engineering -- Creating a Third State Machine

**What goes wrong:** Developer creates a new "WAN congestion state machine" with its own RED/YELLOW/GREEN states, hysteresis counters, and sustain timers alongside the existing CAKE congestion assessment (`congestion_assessment.py`) and ConfidenceController (`steering_confidence.py`). Three independent decision systems can disagree, creating a combinatorial explosion: 4 autorate zones * 3 CAKE states * 3 WAN states * 2 steering states = 72 possible combinations.

**Why it happens:** Symmetry bias: "CAKE has a state machine, WAN should too." But the signals are not symmetric. CAKE stats are sampled directly by the steering daemon. WAN state is a pre-computed signal from another process.

**Consequences:**
- Impossible to reason about system behavior
- Testing matrix explodes
- The ConfidenceController already exists to fuse multiple signals into a single score -- a third state machine duplicates its role

**Prevention:**
- Do NOT create a new state machine for WAN state
- WAN state is a simple enum (`GREEN | YELLOW | SOFT_RED | RED`) read from a file
- Feed it directly into `compute_confidence()` in `steering_confidence.py` as additional `ConfidenceWeights`
- Reuse ALL existing timer, flap detection, and dry-run infrastructure
- Total new code in `steering_confidence.py` should be <50 lines (new weights + one signal check)
- Total new code in `steering/daemon.py` should be <30 lines (read zone, pass to signals)

**Detection:** If a PR introduces a new class with "state machine" in the docstring, question whether `ConfidenceController` can absorb the functionality.

**Phase:** Architecture decision, first phase. Make the ConfidenceController integration path explicit.

---

### Pitfall 8: Hysteresis Stacking -- Compounding Delays

**What goes wrong:** If WAN state has its own sustained-RED timer (e.g., ~1s of sustained RED before acting), this stacks with autorate's `red_streak` requirement (1-2 cycles = 50-100ms), the steering daemon's `red_samples_required=2` at 0.5s interval (1s), and the ConfidenceController's `sustain_duration_sec=2.0`. Total end-to-end latency from congestion start to steering activation: autorate detection (50-100ms) + zone file write (50ms) + steering read staleness (up to 500ms) + WAN hysteresis (1s) + confidence sustain (2s) = 3.6-3.7 seconds. This is **slower** than the current CAKE-only path (1s + 2s = 3s), making the new signal worse than useless for fast response.

**Why it happens:** Each layer adds "are you sure?" filtering. When composing layers, nobody calculates total pipeline latency.

**Prevention:**
- WAN zone should be read AS-IS from the autorate state file -- autorate already applies its own hysteresis via streak counters
- Steering should NOT add another hysteresis layer on top of the pre-filtered zone
- Calculate and document full decision pipeline latency:
  - CAKE-only path: CAKE RED detection (1s at 0.5s interval) + confidence sustain (2s) = 3s
  - WAN-amplified path: autorate RED zone (already filtered) + confidence sustain (2s, possibly shortened to 1s due to higher score) = 2-3s
- The WAN path should be the SAME speed or FASTER than the CAKE-only path, never slower

**Detection:** Integration test: inject congestion, measure wall-clock time to steering activation via both paths.

**Phase:** Integration testing, with end-to-end latency measurement.

---

### Pitfall 9: Backward Compatibility -- Breaking Existing Configs and State Files

**What goes wrong:** Three backward compatibility risks:

1. **State file format change:** Adding `dl_zone` to autorate's state file breaks any external tooling that parses the file (monitoring scripts, `wanctl-history` CLI). If `schema_version` is not present, old readers may error on the new fields.

2. **Steering config change:** Adding `wan_state:` section to `steering.yaml` fails validation on old installations that don't have this section. The `SteeringConfig` class uses a strict schema (`SCHEMA` list in `steering/daemon.py` line 150-165) that requires listed paths to exist.

3. **Autorate restart behavior:** If autorate is updated to write zone but steering is not yet updated to read it, the new field is harmless. But if steering is updated to READ zone before autorate writes it, steering logs warnings every cycle until autorate is deployed.

**Why it happens:** The system runs two independently deployed daemons (autorate in `cake-spectrum` container, steering in the same container but separate process). Deployment order matters.

**Consequences:**
- Rolling update fails if steering deploys before autorate
- Config validation rejects existing `steering.yaml` files missing the new section
- External monitoring tools break on state file format change

**Prevention:**
- New config fields MUST have defaults: `wan_state: {enabled: false}` is the default when the section is missing entirely
- `SteeringConfig._load_wan_state()` should use `.get("wan_state", {})` with all inner fields defaulted
- Autorate's state file change should be deployed FIRST, verified in production, then steering update deployed
- Add `schema_version` to state files (default: 1 if missing, new format: 2)
- Steering treats missing zone fields as GREEN (safe default), not as an error
- Update `docs/CONFIG_SCHEMA.md` with new optional section

**Detection:** Test both deployment orders: (autorate first, steering second) AND (steering first, autorate second). Both must work without errors.

**Phase:** Configuration design phase. Must be explicitly tested for backward compatibility.

---

### Pitfall 10: Testing in Isolation vs. Integration

**What goes wrong:** Unit tests verify "when WAN state is RED, confidence score increases by 20" and "when WAN state is GREEN, score is unchanged." All pass. But in production, WAN RED fires during CAKE YELLOW (confidence = 10 + 20 = 30, below `steer_threshold=55`), so the signal has zero effect. Or, WAN RED fires during CAKE RED with RTT spike (confidence = 50 + 25 + 20 = 95), causing instant steering that the existing system would have filtered through sustained timers.

**Why it happens:** The confidence scoring is additive. Signal interactions create non-obvious combined scores. The ConfidenceController's sustain timers add temporal behavior that unit tests skip.

**Prevention -- Required test matrix:**

| CAKE State | WAN Zone | Expected Confidence Delta | Expected Behavior |
|-----------|----------|--------------------------|-------------------|
| GREEN | GREEN | 0 | No change |
| GREEN | RED | 0 | No action (WAN alone cannot trigger) |
| YELLOW | GREEN | +10 | Existing behavior |
| YELLOW | RED | +10 + WAN weight | May or may not cross threshold -- document expected score |
| SOFT_RED (sustained) | GREEN | +25 | Existing behavior |
| SOFT_RED (sustained) | RED | +25 + WAN weight | Document expected score |
| RED | GREEN | +50 | Existing behavior |
| RED | RED | +50 + WAN weight | Faster threshold crossing |

- Test full `run_cycle()` path, not just `compute_confidence()`
- Include ConfidenceController sustain timer behavior (confidence > threshold is necessary but not sufficient)
- Test the recovery path: once steered, verify WAN GREEN alone does not accelerate recovery
- Test stale zone: verify stale WAN RED has zero effect (treated as GREEN)

**Detection:** Coverage analysis on signal combination paths in `compute_confidence()`.

**Phase:** Dedicated testing phase after implementation. Must include the full signal combination matrix.

---

### Pitfall 11: Zone Enum Mismatch -- SOFT_RED Not Handled

**What goes wrong:** Autorate uses 4-state download zones: GREEN, YELLOW, SOFT_RED, RED. Steering's `CongestionState` enum (`congestion_assessment.py`, line 15-20) has only 3 states: GREEN, YELLOW, RED. If steering reads `dl_zone: "SOFT_RED"` from the autorate state file and does an enum match or string comparison, SOFT_RED falls through to a default case (likely GREEN), effectively ignoring moderate congestion.

**Why it happens:** The steering congestion model and the autorate state model were designed independently. SOFT_RED exists only in the 4-state download model.

**Prevention:**
- Add explicit mapping in the WAN state reader: `SOFT_RED -> YELLOW` (SOFT_RED means clamped-at-floor, which is a warning signal, not critical)
- Or add SOFT_RED to the ConfidenceWeights with its own weight (e.g., `WAN_SOFT_RED = 10`, same as YELLOW)
- Test every possible autorate zone value explicitly
- Use a mapping dict, not if/elif chains, to make missing values obvious

**Phase:** Implementation phase, in the zone reader code.

---

## Minor Pitfalls

---

### Pitfall 12: Health Endpoint Not Exposing WAN State

**What goes wrong:** After deployment, operators cannot see WAN state influence on steering decisions because the health endpoint (port 9102, `steering/health.py`) does not include WAN state data. Debugging requires log analysis.

**Prevention:** Add to health response: `wan_state: {zone: "GREEN", age_sec: 0.3, stale: false, source_file: "/run/wanctl/spectrum_state.json"}`.

**Phase:** Same phase as signal reader implementation.

---

### Pitfall 13: Forgetting the Disabled Path

**What goes wrong:** When `wan_state.enabled: false` (the default), code still attempts to read the zone file and fails because the file does not exist (e.g., on the ATT container, which has no Spectrum autorate state file). Error log spam every 0.5 seconds.

**Prevention:** Guard with `if self.config.wan_state_enabled:` BEFORE any file I/O. Disabled path must skip entirely, not read-and-ignore.

**Phase:** Implementation phase. Test the disabled path explicitly.

---

### Pitfall 14: Recovery Bounce -- Steering Off, Then Immediately Back On

**What goes wrong:** Steering detects GREEN sustained for 3 seconds, disables steering (switches latency-sensitive traffic back to Spectrum). But the sudden influx of returned traffic re-congests Spectrum, autorate goes back to RED within 1-2 seconds, and steering re-enables. This creates a 5-8 second oscillation loop that the `FlapDetector` (4 toggles in 5 minutes) is too slow to catch.

**Why it happens:** Recovery is based on congestion clearing, but congestion cleared BECAUSE traffic was offloaded to ATT. Returning traffic recreates the congestion. This is a fundamental feedback loop, not a tuning issue.

**Consequences:** Latency-sensitive traffic oscillates between WANs every 5-8 seconds, causing connection disruptions.

**Prevention:**
- The existing `hold_down_duration_sec=30` in the ConfidenceController (line 279, `steering_confidence.py`) is specifically designed for this -- after steering is disabled, 30 seconds must pass before re-enabling
- Verify that hold_down is enforced on the recovery path, not just the degrade path
- Consider making hold_down configurable separately for initial degrade vs. re-degrade after recovery
- The natural connection expiry mechanism (only new connections are steered, existing connections stay on ATT) already provides dampening -- document this explicitly

**Detection:** If the `FlapDetector` engages within 5 minutes of the feature going live, the hold_down timer is insufficient.

**Phase:** Testing phase, with simulated recovery scenarios.

---

### Pitfall 15: Configuration Sprawl

**What goes wrong:** Each pitfall above motivates a configuration option. The feature ends up adding 8+ new YAML parameters to `steering.yaml`, making the system unmanageable.

**Prevention:** Maximum 3 new config parameters:
1. `wan_state.enabled` (bool, default: false)
2. `wan_state.weight` (int, default: 20, range 0-50)
3. `wan_state.staleness_threshold_sec` (float, default: 5.0)

Everything else (fusion rules, zone mapping, file path) should be derived or hardcoded with documented rationale. The file path is derived from existing `primary_state_file`. The fusion logic is an architectural decision, not a deployment parameter.

**Phase:** Config design in first phase. Lock it down early.

---

## Phase-Specific Warning Summary

| Phase Topic | Critical Pitfall | Moderate Pitfall | Prevention |
|---|---|---|---|
| Autorate state file modification | P1 (missing zone), P2 (dirty tracking regression) | P9 (backward compat) | Add zone to separate file or exclude from dirty tracking; add schema_version |
| WAN state reader in steering | P3 (staleness/stuck states), P6 (hot loop I/O) | P11 (SOFT_RED mapping), P13 (disabled path) | 5s staleness threshold, stale=GREEN, same-file read, explicit zone mapping |
| Signal fusion design | P4 (signal conflict), P5 (oscillation amplification) | P7 (over-engineering), P8 (hysteresis stacking) | ConfidenceWeights integration, WAN amplifies only, calculate pipeline latency |
| Configuration | P15 (sprawl) | P9 (backward compat) | Max 3 new params, all fields defaulted, optional section |
| Testing | P10 (isolation vs integration) | P14 (recovery bounce) | Signal combination matrix, end-to-end latency test, recovery scenario tests |
| Observability | | P12 (health endpoint) | Add wan_state to health response |

## Key Architectural Constraint

The existing `ConfidenceController` and `compute_confidence()` in `steering_confidence.py` (lines 85-146) already provide the correct integration point. WAN state should be an additional input to `ConfidenceSignals` and an additional weight in `ConfidenceWeights`. This reuses all existing timer, flap detection, hold-down, and dry-run infrastructure. Creating any parallel decision system is the primary over-engineering risk.

The steering daemon already reads autorate's state file every cycle for baseline RTT (`update_baseline_rtt()`, line 1313). The WAN zone read should piggyback on this same file read with zero additional I/O.

## Sources

- Codebase: `src/wanctl/autorate_continuous.py` -- `save_state()` (line 1613), `WANControllerState` schema, dirty tracking
- Codebase: `src/wanctl/wan_controller_state.py` -- `_is_state_changed()` (line 51), `save()` (line 104)
- Codebase: `src/wanctl/steering/daemon.py` -- `BaselineLoader.load_baseline_rtt()` (line 575), `SteeringDaemon.run_cycle()` (line 1305), `update_baseline_rtt()` (line 1069)
- Codebase: `src/wanctl/steering/steering_confidence.py` -- `compute_confidence()` (line 85), `ConfidenceWeights` (line 27), `TimerManager` (line 182)
- Codebase: `src/wanctl/steering/congestion_assessment.py` -- `CongestionState` enum (line 15), `assess_congestion_state()` (line 50)
- Codebase: `src/wanctl/state_utils.py` -- `atomic_write_json()` (line 20), `safe_json_load_file()` (line 132)
- Codebase: `configs/steering.yaml` -- production config with confidence scoring dry-run enabled
- [POSIX write() is not atomic in the way you might like](https://utcc.utoronto.ca/~cks/space/blog/unix/WriteNotVeryAtomic) -- confirms atomic rename is sufficient for cross-process state sharing (HIGH confidence)
- [Understanding Control Valve Hysteresis](https://instrunexus.com/understanding-control-valve-hysteresis-deadband-response-time/) -- hysteresis stacking in control systems causes limit cycling (MEDIUM confidence)
- [OPNsense Multi WAN documentation](https://docs.opnsense.org/manual/how-tos/multiwan.html) -- sticky connections and failover state management patterns (MEDIUM confidence)
