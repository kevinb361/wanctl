# Domain Pitfalls: Adding WAN RTT State to CAKE-Based Steering

**Domain:** Multi-signal congestion-aware WAN steering
**Researched:** 2026-03-08
**Confidence:** HIGH (analysis grounded in codebase evidence + established control systems literature)

## Critical Pitfalls

Mistakes that cause production routing failures, oscillation, or require rewrites.

---

### Pitfall 1: Signal Conflict Deadlock -- CAKE Says GREEN, WAN Says RED

**What goes wrong:** Autorate's download state is RED (ISP-level congestion detected via RTT spikes) while steering's CAKE stats show GREEN (local queue is healthy, no drops, no backlog). The signals contradict. Without an explicit conflict resolution policy, the system either ignores the WAN signal entirely (defeating the purpose) or triggers steering unnecessarily on WAN-only transients.

**Why it happens:** CAKE stats measure local queue health (backlog, drops). WAN RTT measures end-to-end path quality. These observe fundamentally different phenomena. ISP congestion (backbone saturation, peering issues) raises WAN RTT without causing CAKE drops because the bottleneck is upstream of the local queue. Conversely, local buffer overrun causes CAKE RED without necessarily raising WAN RTT if the bottleneck is at the home uplink.

**Consequences:**
- If WAN RED overrides CAKE GREEN: steering activates on ISP transients that CAKE correctly ignores, increasing flap rate
- If CAKE GREEN overrides WAN RED: the new signal is silently ignored, the entire milestone is wasted
- If both must agree: the system becomes MORE conservative than before (requires two signals to agree), which is the opposite of the goal

**Prevention:**
- Define explicit signal hierarchy: CAKE stats remain primary, WAN state is _amplifying only_. WAN RED cannot trigger steering alone but CAN accelerate the degrade timer or lower the confidence threshold when CAKE is YELLOW
- WAN RED + CAKE GREEN = no action (CAKE is authoritative for local queue health)
- WAN RED + CAKE YELLOW = promote to RED-equivalent (WAN confirms the early warning)
- WAN RED + CAKE RED = fast-track (both signals agree, reduce sustain timer)
- WAN GREEN should have zero effect on steering decisions (it's the normal state)
- Document the fusion matrix explicitly in code comments and config schema

**Detection:** Log both signals side-by-side every cycle. If WAN RED fires while CAKE stays GREEN for >30 seconds, emit a specific INFO-level message. Monitor for this pattern in production before enabling any WAN-based action.

**Phase:** Must be addressed in the signal fusion design phase (first phase). This is an architectural decision, not a tuning decision.

---

### Pitfall 2: Oscillation Amplification from Faster Degradation Path

**What goes wrong:** Adding WAN state creates a faster path to DEGRADED (two signals can now trigger steering) but recovery still requires the same sustained GREEN period. The asymmetry becomes too aggressive: the system enters DEGRADED more easily but exits at the same rate. Under intermittent congestion, this increases the time spent in DEGRADED state, which means more traffic on ATT, which means ATT gets loaded, which can cascade.

**Why it happens:** The existing hysteresis is tuned for single-signal behavior. `red_samples_required=2` and `green_samples_required=15` work because CAKE RED is a strong signal (requires RTT + drops + queue depth simultaneously). But if WAN RED can contribute to the degrade path, the effective threshold for entering DEGRADED drops without a corresponding change to recovery conditions.

**Consequences:**
- Increased time in DEGRADED state
- ATT link receives more traffic, potentially degrading ATT performance
- FlapDetector engages more often, adding penalty delays that make recovery even slower
- User-visible symptoms: latency-sensitive traffic bounces between WANs with neither being optimal

**Prevention:**
- WAN state should ONLY accelerate an existing CAKE signal, never independently trigger degradation
- If WAN state reduces the degrade threshold (e.g., from 2 RED samples to 1), correspondingly reduce the recovery threshold proportionally (e.g., from 15 GREEN samples to 10)
- Or better: don't touch the hysteresis counters at all. Instead, have WAN RED lower the `steer_threshold` in the ConfidenceController (from 55 to 40 when WAN is RED), making it easier for existing CAKE signals to trigger steering without adding a new independent trigger
- Add a unit test: "WAN RED alone never triggers DEGRADED transition"
- Add an integration test: simulate intermittent WAN RED with stable CAKE GREEN, verify zero state transitions

**Detection:** Monitor state transition frequency before and after enabling WAN signal. If transitions/hour increases by >50%, the signal is too aggressive.

**Phase:** Must be addressed alongside signal fusion. Needs explicit invariant test.

---

### Pitfall 3: Stale State File Reads Causing Phantom Congestion

**What goes wrong:** Steering reads autorate's state file and interprets `download.red_streak > 0` or the zone as "RED", but autorate stopped updating the file 30 seconds ago (process restart, crash, rate-limited save). Steering keeps acting on stale data, maintaining DEGRADED state long after congestion ended.

**Why it happens:** The autorate state file (`/var/lib/wanctl/WANNAME_state.json`) uses dirty tracking -- `WANControllerState._is_state_changed()` skips writes when state is unchanged. During sustained GREEN, the file's `st_mtime` stops advancing. Meanwhile, the existing `BaselineLoader._check_staleness()` only checks staleness for baseline RTT, not for the new WAN congestion state fields. The staleness threshold is 300 seconds (5 minutes), which is far too long for a signal that should represent "current" congestion.

**Consequences:**
- Steering enters DEGRADED based on a WAN RED state from minutes ago
- During autorate restart, the last-written state persists indefinitely
- If autorate crashes in RED state, steering holds DEGRADED until autorate restarts and writes GREEN

**Prevention:**
- Add a `timestamp` field to the autorate state file (already exists but is ISO-8601, needs to be compared)
- Implement a WAN-state-specific staleness check with a much tighter threshold (5-10 seconds, not 300 seconds)
- If WAN state data is older than the threshold, treat it as UNKNOWN/GREEN (fail-safe default)
- Consider adding `dl_zone` and `ul_zone` to the autorate state file explicitly (currently only stored in metrics, not in the state file)
- Never trust a RED state from a stale file. Stale + RED = treat as GREEN

**Detection:** Log the age of the WAN state data every time it is read. Alert if age exceeds 2x the expected autorate cycle interval (2 * 50ms = 100ms is unrealistic for file I/O; more practically, alert if age > 5 seconds).

**Phase:** Must be addressed in the state file reader phase. This is the highest-risk integration point.

---

### Pitfall 4: Autorate State File Missing WAN Zone -- Reading the Wrong Fields

**What goes wrong:** The autorate state file schema (`WANControllerState.save()`) contains `download.green_streak`, `download.red_streak`, `ewma.baseline_rtt`, and `ewma.load_rtt` but does NOT contain the download zone string ("GREEN", "YELLOW", "SOFT_RED", "RED"). The zone is computed fresh each cycle by `download.adjust_4state()` and passed to metrics, but never persisted to the state file. Steering would need to either: (a) reverse-engineer the zone from streak counters, or (b) add the zone to the state file.

**Why it happens:** The autorate state file was designed for crash recovery (restoring hysteresis counters), not for inter-process communication. The zone is a derived value, not persisted state.

**Consequences:**
- If steering tries to read `download.zone` from the state file, it gets KeyError/None
- If steering reverse-engineers zone from `red_streak > 0`, it may get a different answer than autorate's actual assessment (race condition between streak update and file write)
- If autorate adds the zone to the state file, it changes the file format, requiring backward compatibility handling

**Prevention:**
- Modify `WANControllerState.save()` to include `dl_zone` and `ul_zone` as explicit fields
- Make this change in the autorate side first, deploy it, verify the file format before steering reads it
- Use a version field in the state file so steering can detect old-format files: `"schema_version": 2`
- Steering should gracefully handle missing zone fields (treat as GREEN, log warning)
- NEVER reverse-engineer zone from streak counters. The zone is autorate's conclusion; steering should read the conclusion, not re-derive it

**Detection:** If steering reads a state file without `dl_zone`, log a warning with the file path and available keys.

**Phase:** Must be the FIRST implementation step. The autorate state file change must ship before steering can read it. This creates a hard phase dependency.

---

### Pitfall 5: Breaking Existing Behavior with "Innocent" Changes

**What goes wrong:** To expose WAN state, the developer modifies `autorate_continuous.py`'s `save_state()` method. This seemingly safe change (adding a field to a JSON dict) triggers unexpected behavior: dirty tracking (`_is_state_changed()`) now detects changes every cycle because the new `dl_zone` field changes between GREEN/YELLOW frequently, increasing disk writes from ~1/second to 20/second (every 50ms cycle).

**Why it happens:** The dirty tracking compares the full state dict. Adding a volatile field (zone changes frequently) defeats the optimization. This is especially bad because the autorate state file uses `atomic_write_json()` with `os.fsync()` -- every write is a sync to disk, consuming I/O bandwidth and potentially increasing cycle latency.

**Consequences:**
- 20x increase in disk writes (50ms interval = 20 writes/second vs current ~1/second)
- Increased cycle latency from `fsync()` overhead
- Flash wear on the router's storage (if deployed on embedded systems)
- Performance regression in the autorate hot path

**Prevention:**
- Do NOT add volatile fields to the main state dict tracked by `_is_state_changed()`
- Instead, write WAN zone to a SEPARATE lightweight file (e.g., `/var/lib/wanctl/WANNAME_wan_state.json`) that does not use dirty tracking
- Or: add the zone field but exclude it from the dirty-tracking comparison in `_is_state_changed()`
- Or: only update the zone field when it actually changes (zone transitions are infrequent -- a few per minute, not 20/second)
- Measure disk write frequency before and after the change

**Detection:** Monitor `WANControllerState.save()` return value (True = wrote, False = skipped). If the True rate jumps from ~1/s to 20/s after the change, the dirty tracking is broken.

**Phase:** Directly impacts the autorate state file modification phase. Must be tested with a profiling run.

---

## Moderate Pitfalls

---

### Pitfall 6: Race Condition Between Autorate Write and Steering Read

**What goes wrong:** Autorate writes the state file every 50ms. Steering reads it every 50ms (or at its own cycle interval). Despite `atomic_write_json()` using temp-file-then-rename (POSIX atomic rename), there is still a window where steering reads a state file that is one cycle behind, or (in edge cases) gets the file mid-rename on certain filesystems.

**Why it happens:** `safe_json_load_file()` uses `open()` + `json.load()`, not `fcntl` locking. The rename is atomic, but the read is not coordinated with the write. On tmpfs (where `/var/lib/wanctl/` likely lives), this is mostly safe, but if the state file is on ext4 with delayed allocation, metadata updates can lag.

**Prevention:**
- The existing atomic-write pattern is sufficient for the data freshness requirements here (one cycle of staleness is acceptable for a secondary signal)
- Do NOT add file locking between autorate and steering -- it would create contention at 20Hz and risks deadlock
- Accept that steering may read a state that is one cycle (50ms) old. For a secondary signal with 1-3 second hysteresis, this is negligible
- Document this explicitly: "WAN state may lag autorate by up to one cycle (50ms)"

**Detection:** Not needed. The existing atomic write pattern makes partial reads impossible (rename is atomic). One-cycle staleness is by design.

**Phase:** No dedicated phase needed, but document the design decision in the architecture.

---

### Pitfall 7: Over-Engineering the Fusion -- Adding a Third State Machine

**What goes wrong:** The developer creates a new "WAN state machine" with its own RED/YELLOW/GREEN states, its own hysteresis counters, its own sustain timers, running alongside the existing CAKE state machine and the ConfidenceController. Now there are three independent decision systems that can disagree, creating a combinatorial explosion of states (3 CAKE states * 3 WAN states * 2 steering states = 18 possible combinations).

**Why it happens:** The temptation to treat the new signal symmetrically with the existing signal. "CAKE has a state machine, so WAN should too." But the signals are not symmetric -- CAKE is the primary decision-maker, WAN is a secondary input.

**Consequences:**
- Impossible to reason about system behavior (18 state combinations)
- Testing matrix explodes (each combination needs coverage)
- Debugging production issues requires understanding three interacting state machines
- The ConfidenceController already exists to fuse signals -- adding another layer duplicates its role

**Prevention:**
- Do NOT create a new state machine for WAN state
- WAN state should be a simple enum read from the state file: `GREEN | YELLOW | SOFT_RED | RED`
- Feed it into the existing ConfidenceController as an additional weight in `compute_confidence()`
- Add a `WAN_RED` weight to `ConfidenceWeights` (e.g., 20-30 points) and a `WAN_YELLOW` weight (e.g., 5-10 points)
- This reuses all existing hysteresis, flap detection, and timer infrastructure
- Total new code should be <100 lines, not a new subsystem

**Detection:** Code review. If a PR introduces a new class with "state" in the name, question whether it's needed.

**Phase:** Architecture decision in the first phase. The ConfidenceController integration path should be the explicit recommendation.

---

### Pitfall 8: WAN State Hysteresis Stacking with CAKE Hysteresis

**What goes wrong:** If WAN state has its own hysteresis (sustained RED for N cycles before acting), this hysteresis stacks with CAKE's `red_samples_required` and the ConfidenceController's `sustain_duration_sec`. Total latency from congestion start to steering action becomes: WAN hysteresis (1s) + CAKE hysteresis (2 samples * 50ms = 100ms) + confidence sustain (2s) = 3.1 seconds. This is slower than the current system (100ms + 2s = 2.1s), making the new signal worse than useless for fast response.

**Why it happens:** Each layer adds its own "are you sure?" timer. When stacking layers, nobody calculates the total end-to-end delay.

**Prevention:**
- Calculate the full decision pipeline latency BEFORE implementing
- WAN state hysteresis should be done in autorate (where the state is assessed), not in steering
- Steering should read the already-hysteresis-filtered zone from autorate's state file
- If WAN RED is read from the file, it already reflects autorate's `red_streak >= N` threshold -- steering should not add another layer
- Document the end-to-end latency: "From congestion start to steering action: [X]ms via CAKE path, [Y]ms via WAN-amplified path"

**Detection:** Measure time from simulated congestion injection to steering activation in integration tests.

**Phase:** Integration testing phase. Add an end-to-end latency test.

---

### Pitfall 9: Testing the New Signal in Isolation but Not in Combination

**What goes wrong:** Unit tests verify "when WAN state is RED, confidence score increases by N" and "when WAN state is GREEN, confidence score is unchanged." All tests pass. But in production, the WAN signal fires during a CAKE YELLOW period and the combined score (YELLOW=10 + WAN_RED=25 = 35) doesn't cross the `steer_threshold=55`, so the signal has zero effect. Or worse, it crosses the threshold in unexpected combinations that were not tested.

**Why it happens:** Combinatorial testing is tedious. Developers test individual signals, not signal combinations. The confidence scoring is additive, so the interaction effects are non-obvious.

**Prevention:**
- Create a test matrix of all meaningful signal combinations:
  - CAKE GREEN + WAN GREEN (baseline, no effect)
  - CAKE GREEN + WAN RED (should NOT trigger steering alone)
  - CAKE YELLOW + WAN GREEN (existing behavior, unchanged)
  - CAKE YELLOW + WAN RED (key scenario: should this trigger?)
  - CAKE RED + WAN GREEN (existing behavior, unchanged)
  - CAKE RED + WAN RED (should accelerate)
- For each combination, document the expected behavior and the expected confidence score
- Test the full `run_cycle()` path, not just `compute_confidence()`
- Include the ConfidenceController sustain timer in tests (confidence > threshold is necessary but not sufficient)

**Detection:** Code coverage analysis on the signal combination paths. If coverage reports show uncovered branches in `compute_confidence()`, the test matrix is incomplete.

**Phase:** Dedicated testing phase after implementation.

---

### Pitfall 10: Configuration Sprawl -- Too Many Knobs

**What goes wrong:** The feature adds `wan_state.enabled`, `wan_state.weight_red`, `wan_state.weight_yellow`, `wan_state.staleness_threshold_sec`, `wan_state.hysteresis_cycles`, and `wan_state.file_path` to the YAML config. Combined with existing `confidence.steer_threshold`, `confidence.recovery_threshold`, `thresholds.red_rtt`, etc., there are now 15+ tuning knobs for steering behavior. No human can reason about the interaction of 15 parameters.

**Why it happens:** Each pitfall above motivates a configuration option ("make the staleness threshold configurable", "make the WAN weight configurable"). This is a reasonable instinct, but the accumulation creates an unmanageable system.

**Prevention:**
- Add at most 3 new config parameters: `wan_state.enabled` (bool), `wan_state.weight` (int, default 20), and `wan_state.staleness_threshold_sec` (float, default 5.0)
- All other values should be derived or hardcoded with documented rationale
- The `wan_state.file_path` should be derived from existing `primary_state_file` (same file, different field)
- Do NOT make the fusion logic configurable. The signal hierarchy (CAKE primary, WAN amplifying) is an architectural decision, not a deployment parameter

**Detection:** Count config parameters before and after. If the delta is >3, reconsider.

**Phase:** Config design in the first phase. Lock it down early.

---

## Minor Pitfalls

---

### Pitfall 11: Health Endpoint Not Exposing WAN State

**What goes wrong:** After deployment, operators cannot see whether WAN state is influencing steering decisions because the health endpoint (port 9102) does not include WAN state information. Debugging requires reading logs, which is slow and fragile.

**Prevention:** Add `wan_state: {zone: "GREEN", age_sec: 0.3, stale: false}` to the health endpoint response in the same phase that adds the signal reading.

**Phase:** Implementation phase, alongside the signal reader.

---

### Pitfall 12: Forgetting the "Disabled" Path

**What goes wrong:** When `wan_state.enabled: false`, the code still tries to read the state file and fails (file does not exist on ATT container, which does not run autorate for spectrum). Error log spam ensues.

**Prevention:** The disabled path must skip the file read entirely, not just ignore the result. Guard with `if self.config.wan_state_enabled:` before any file I/O.

**Phase:** Implementation phase. Add a test for the disabled path.

---

### Pitfall 13: Autorate and Steering Using Different Zone Definitions

**What goes wrong:** Autorate uses 4-state download zones (GREEN/YELLOW/SOFT_RED/RED) and 3-state upload zones (GREEN/YELLOW/RED). Steering's congestion assessment uses 3-state (GREEN/YELLOW/RED). If steering reads autorate's `dl_zone: "SOFT_RED"` and does not handle it, it may default to GREEN (no match), effectively ignoring moderate congestion.

**Prevention:**
- Map SOFT_RED to YELLOW in the steering signal reader (SOFT_RED means "clamped at floor" which is a warning, not critical)
- Or map SOFT_RED to RED if the WAN signal is intended to be aggressive
- Document the mapping explicitly
- Add a test for each autorate zone value

**Phase:** Implementation phase. Must be in the zone reader code.

---

## Phase-Specific Warnings

| Phase Topic | Likely Pitfall | Mitigation |
|-------------|---------------|------------|
| Autorate state file modification | Pitfall 4 (missing zone), Pitfall 5 (dirty tracking regression) | Add zone field, exclude from dirty tracking comparison |
| WAN state reader in steering | Pitfall 3 (staleness), Pitfall 12 (disabled path), Pitfall 13 (zone mapping) | Tight staleness threshold, disabled guard, explicit zone map |
| Signal fusion / ConfidenceController integration | Pitfall 1 (conflict deadlock), Pitfall 2 (oscillation), Pitfall 7 (over-engineering) | Use ConfidenceWeights, WAN amplifies only, no new state machine |
| Configuration | Pitfall 10 (config sprawl) | Maximum 3 new parameters |
| Testing | Pitfall 9 (combinatorial coverage) | Signal combination matrix, end-to-end latency test |
| Hysteresis tuning | Pitfall 8 (stacking delays) | Calculate full pipeline latency, use autorate's pre-filtered zone |
| Health/observability | Pitfall 11 (missing from endpoint) | Add wan_state to health response |
| Production deployment | Pitfall 5 (disk write regression) | Profile before/after, monitor write frequency |

## Key Architectural Constraint

The existing `ConfidenceController` and `compute_confidence()` in `steering_confidence.py` already provide the correct integration point. WAN state should be an additional input to `ConfidenceSignals` and an additional weight in `ConfidenceWeights`. This reuses all existing timer, flap detection, and dry-run infrastructure. Creating any parallel decision system is the primary over-engineering risk.

## Sources

- Codebase analysis: `src/wanctl/steering/daemon.py` (BaselineLoader, run_cycle, state machine)
- Codebase analysis: `src/wanctl/steering/steering_confidence.py` (ConfidenceController, compute_confidence)
- Codebase analysis: `src/wanctl/steering/congestion_assessment.py` (assess_congestion_state)
- Codebase analysis: `src/wanctl/wan_controller_state.py` (WANControllerState.save, dirty tracking)
- Codebase analysis: `src/wanctl/state_utils.py` (atomic_write_json, safe_json_load_file)
- [Information Fusion of Conflicting Input Data](https://pmc.ncbi.nlm.nih.gov/articles/PMC5134457/) (MEDIUM confidence)
- [Sensor Fusion 101](https://www.jacksonhedden.com/iterate/sensor-fusion-guide) (MEDIUM confidence)
- [POSIX write() is not atomic in the way you might like](https://utcc.utoronto.ca/~cks/space/blog/unix/WriteNotVeryAtomic) (HIGH confidence)
- [TCP Congestion Control: A Systems Approach](https://tcpcc.systemsapproach.org/intro.html) (HIGH confidence)
- [MikroTik WAN failover flapping discussion](https://forum.mikrotik.com/viewtopic.php?t=206691) (MEDIUM confidence)
- [Inter-process communication in Linux: Shared storage](https://opensource.com/article/19/4/interprocess-communication-linux-storage) (MEDIUM confidence)
