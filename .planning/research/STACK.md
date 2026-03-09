# Technology Stack: WAN-Aware Steering Integration

**Project:** wanctl v1.11
**Researched:** 2026-03-09
**Overall confidence:** HIGH

## Recommendation: Zero New Dependencies

No new external libraries, frameworks, or tools are needed. Every primitive required for WAN-aware steering already exists in the codebase. This recommendation is based on thorough analysis of the three capability areas (inter-daemon state sharing, hysteresis/debounce, config schema extensions) against existing code.

## Existing Stack (Validated, Reuse As-Is)

| Component | Location | Reuse For |
|-----------|----------|-----------|
| Atomic JSON state file IPC | `state_utils.py:atomic_write_json()` | Autorate writes WAN congestion state, steering reads |
| Safe file reader | `state_utils.py:safe_json_load_file()` | Read WAN state from state file (single read for both baseline + congestion) |
| State file staleness check | `steering/daemon.py:BaselineLoader._check_staleness()` | Same staleness gate applies to WAN congestion data |
| Streak-based hysteresis | `autorate_continuous.py:QueueController` | Counter-based sustained-signal detection (green_streak, red_streak pattern) |
| Sample-count gates | `steering/daemon.py:_update_state_machine_unified()` | `red_count`/`good_count` with configurable thresholds |
| Confidence scoring | `steering_confidence.py:compute_confidence()` | Add WAN state as new weighted signal (additive) |
| Sustained detection | `steering_confidence.py` | SOFT_RED_sustained pattern (check last N history entries) |
| Sustain timers | `steering_confidence.py:ConfidenceController` | Existing degrade/recovery timers gate confidence score |
| Flap detection | `steering_confidence.py:FlapDetector` | Already prevents oscillation; WAN signal benefits automatically |
| Dirty tracking | `wan_controller_state.py:WANControllerState._is_state_changed()` | Extend to include congestion dict |
| Config schema validation | `config_base.py:validate_schema()` | Add `wan_state` section to SteeringConfig SCHEMA |
| Health endpoint | `steering/health.py` | Add WAN state to existing congestion section |
| Dataclass structs | `steering/congestion_assessment.py:StateThresholds` | Pattern for threshold configuration objects |

## Capability Analysis

### 1. Inter-Daemon State Sharing

**Need:** Autorate writes WAN congestion state (RED/YELLOW/SOFT_RED/GREEN); steering reads it.

**Mechanism:** Extend the existing atomic JSON state file that steering already reads.

**Current read path (steering/daemon.py lines 575-618):**

1. `BaselineLoader.load_baseline_rtt()` calls `safe_json_load_file()` on `primary_state_file`
2. Extracts `state["ewma"]["baseline_rtt"]`
3. Validates bounds (C4 fix), checks staleness (STEER-03)

**v1.11 extension -- add congestion extraction to the same read:**

1. Same `safe_json_load_file()` call (already happening, zero additional I/O)
2. Also extract `state["congestion"]["dl_state"]` if present
3. Return both baseline RTT and WAN congestion state
4. Graceful fallback if `congestion` key missing (backward compat with old autorate)

**Critical design constraint:** Do NOT add a second file read. The state file is already read once per steering cycle (500ms). Parse both values from the single existing read. This is why a `WANStateLoader` class that independently reads the file would be wrong -- it would double I/O.

**Current autorate state JSON schema:**
```json
{
  "download": {"green_streak": 0, "soft_red_streak": 0, "red_streak": 0, "current_rate": 940000000},
  "upload": {"green_streak": 0, "soft_red_streak": 0, "red_streak": 0, "current_rate": 38000000},
  "ewma": {"baseline_rtt": 24.5, "load_rtt": 25.1},
  "last_applied": {"dl_rate": 940000000, "ul_rate": 38000000},
  "timestamp": "2026-03-09T12:00:00"
}
```

**v1.11 extension (backward compatible, one new top-level key):**
```json
{
  "download": {"green_streak": 0, ...},
  "upload": {"green_streak": 0, ...},
  "ewma": {"baseline_rtt": 24.5, "load_rtt": 25.1},
  "last_applied": {"dl_rate": 940000000, "ul_rate": 38000000},
  "congestion": {
    "dl_state": "GREEN",
    "ul_state": "GREEN",
    "delta_ms": 1.2
  },
  "timestamp": "2026-03-09T12:00:00"
}
```

**Why `congestion` as key:** Clean namespace, doesn't pollute existing sections. Mirrors steering health endpoint's `congestion` key. The `dl_state` is the primary signal (4-state model: GREEN/YELLOW/SOFT_RED/RED). The `ul_state` and `delta_ms` are for observability.

**Backward compatibility:** Old steering code ignoring `congestion` key continues working. New steering code handles missing key gracefully (existing `safe_json_load_file` + dict `.get()` pattern).

**Deriving dl_state:** The zone is already computed every cycle in `QueueController.adjust_4state()` which returns `(state, new_rate, transition_reason)`. The state string ("GREEN", "YELLOW", "SOFT_RED", "RED") is the exact value to write. No new computation needed.

**Rejected alternatives:**

| Alternative | Why Not |
|-------------|---------|
| Shared memory (mmap) | Overkill for 500ms reads. Adds complexity. File IPC proven at 50ms write cadence for 11 milestones. |
| Unix domain sockets | Introduces server/client coupling. Current file approach is deliberately decoupled -- daemons restart independently. |
| D-Bus / systemd notify | Heavy dependency for a single signal. Inappropriate for embedded/container deployment. |
| Redis / memcached | External dependency on a production network controller is unacceptable. |
| Named pipes (FIFO) | Blocking semantics unsuitable for real-time control loops. |
| SQLite shared DB | Already have metrics in SQLite, but WAL mode fsync overhead per write exceeds JSON atomic rename. |
| Separate WAN state file | Don't fragment state. Extend existing `{wan}_state.json`. Single file = single read = single atomic operation. |

### 2. Hysteresis / Debounce Gate

**Need:** Sustained WAN RED (~1s) triggers failover amplification; sustained GREEN (~3s) for recovery.

**Mechanism:** Counter-based streak tracking -- identical to three existing patterns in the codebase.

**Existing pattern instances:**

| Location | Counter | Threshold | Purpose |
|----------|---------|-----------|---------|
| `autorate_continuous.py:QueueController` | `green_streak` / `red_streak` | `green_required` (default 3-5) | Rate step-up hysteresis |
| `steering/daemon.py:_update_state_machine_unified()` | `red_count` / `good_count` | `red_samples_required` / `green_samples_required` | Steering state transitions |
| `steering_confidence.py:compute_confidence()` | `cake_state_history[-3:]` | 3 consecutive cycles | SOFT_RED sustained detection |

**v1.11 addition -- same pattern, new counters:**

The WAN-state hysteresis uses the same counter structure. At steering's 500ms cycle rate:
- `wan_red_threshold: 2` = ~1s sustained WAN RED (2 cycles x 500ms)
- `wan_green_threshold: 6` = ~3s sustained WAN GREEN (6 cycles x 500ms)

These are configurable via YAML (see section 3).

**Integration approach:** Two options, both valid:

**Option A: Inline in `_evaluate_degradation_condition()`** -- Add WAN state as an additional condition that can escalate YELLOW to RED-equivalent. ~15 lines. Keeps change minimal.

**Option B: Via confidence scoring** -- Add WAN state as a weighted signal in `compute_confidence()`. Uses existing sustained-detection patterns (check last N entries of a history list). ~20 lines. Better for long-term architecture since confidence scoring is the strategic direction.

**Recommendation: Option B (confidence scoring)** because:
- Confidence controller already has sustain timers, flap detection, hold-down
- WAN state benefits from all existing safeguards automatically
- Aligns with the existing dry-run validation path
- PROJECT.md says "WAN state is secondary/amplifying" -- weighted additive scoring naturally enforces this

**Threshold math proving WAN is amplifier, not trigger:**
- WAN RED (30 pts) alone: 30 < 55 steer threshold. Cannot trigger steering.
- WAN RED (30) + CAKE YELLOW (10): 40 < 55. Still not enough.
- WAN RED (30) + CAKE RED (50): 80 > 55. Steers. (Both signals agree.)
- WAN RED (30) + CAKE YELLOW (10) + drops_increasing (10) + queue_high (10): 60 > 55. Multi-signal agreement.

This preserves the invariant: **CAKE stats remain primary, WAN state amplifies/confirms.**

**However,** the hysteresis gate should ALSO work in the non-confidence (legacy hysteresis) path via `_evaluate_degradation_condition()` so that WAN state is available regardless of `use_confidence_scoring` setting. This means both options are needed but Option A is simpler (a condition modifier, not a new state machine).

### 3. Configuration Schema Extension

**Need:** Configurable thresholds for WAN-state failover tuning in YAML.

**Mechanism:** Extend `SteeringConfig._load_specific_fields()` and SCHEMA entries.

**Proposed YAML section (follows existing `confidence:` pattern):**

```yaml
# WAN-aware steering (v1.11)
wan_state:
  enabled: false                   # Master toggle (safe default: disabled for rollout)
  wan_red_threshold: 2             # Sustained WAN RED samples before amplifying (~1s at 500ms cycle)
  wan_green_threshold: 6           # Sustained WAN GREEN samples before clearing (~3s at 500ms cycle)
  weight_red: 30                   # Confidence score contribution for WAN RED
  weight_soft_red: 15              # Confidence score contribution for WAN SOFT_RED
  weight_yellow: 5                 # Confidence score contribution for WAN YELLOW
  amplify_only: true               # WAN state amplifies CAKE signals, never acts alone
  stale_threshold_sec: 10          # Ignore WAN state if autorate state file older than this
```

**Schema validation entries (follow existing pattern in `SteeringConfig`):**

```python
# Direct extension of existing SCHEMA list
{"path": "wan_state.enabled", "type": bool, "required": False, "default": False},
{"path": "wan_state.wan_red_threshold", "type": int, "required": False, "default": 2, "min": 1, "max": 20},
{"path": "wan_state.wan_green_threshold", "type": int, "required": False, "default": 6, "min": 1, "max": 60},
{"path": "wan_state.weight_red", "type": int, "required": False, "default": 30, "min": 0, "max": 100},
{"path": "wan_state.weight_soft_red", "type": int, "required": False, "default": 15, "min": 0, "max": 100},
{"path": "wan_state.weight_yellow", "type": int, "required": False, "default": 5, "min": 0, "max": 100},
{"path": "wan_state.amplify_only", "type": bool, "required": False, "default": True},
{"path": "wan_state.stale_threshold_sec", "type": (int, float), "required": False, "default": 10, "min": 1, "max": 300},
```

**Why configurable weights:** Different ISPs have different RTT characteristics. Cable (Spectrum) has more volatile RTT than fiber. Portable controller architecture (CLAUDE.md: "All variability in config parameters (YAML)") requires external tuning.

**Why `enabled: false` default:** Safe rollout. Deploy code, validate in dry-run via confidence scoring, then enable in config. Same safe-by-default pattern as `confidence.dry_run: true`.

**State source:** Reuses the existing `cake_state_sources.primary` path. No need for a separate config field -- the WAN state lives in the same file that `BaselineLoader` already reads.

## What NOT to Add

| Temptation | Why Avoid |
|------------|-----------|
| New pip dependency | Zero new deps needed. Everything is stdlib + existing deps. |
| Separate WAN state file | Don't fragment state. Extend existing `{wan}_state.json`. |
| Message queue between daemons | File-based decoupling is a deliberate architectural choice. |
| Complex state machine library | Counter-based hysteresis is ~20 lines. A library adds 10x complexity. |
| Protocol buffers / msgpack | JSON is fast enough. `json.dump()` compact on 200-byte dict takes ~0.01ms. |
| Configuration migration tool | New fields have defaults. Old configs work unchanged. |
| Feature flag service | YAML `enabled: true/false` is the feature flag. |
| New WANStateLoader class with own file I/O | Doubles file reads. Refactor `BaselineLoader` to return both values from single read. |

## Estimated Code Volume

| Addition | File(s) | Lines | Complexity |
|----------|---------|-------|------------|
| `congestion` dict in autorate state write | `wan_controller_state.py`, `autorate_continuous.py` | ~15 | Low |
| Refactored BaselineLoader returns WAN state | `steering/daemon.py` | ~25 | Low |
| WAN state hysteresis counters in steering state schema | `steering/daemon.py` | ~5 | Low |
| WAN state integration in `_evaluate_degradation_condition()` | `steering/daemon.py` | ~15 | Low |
| WAN state signal in `compute_confidence()` | `steering/steering_confidence.py` | ~20 | Low |
| `wan_state` YAML config section + schema validation | `steering/daemon.py:SteeringConfig` | ~15 | Low |
| Health endpoint WAN state exposure | `steering/health.py` | ~5 | Low |
| **Total new production code** | | **~100** | **Low** |

All changes are in existing files. Zero new files needed.

## Installation

**No changes to `pyproject.toml` dependencies.** No new packages on production containers.

```bash
# Development (unchanged)
uv sync

# Production (unchanged -- no new pip installs)
```

## Confidence Assessment

| Area | Level | Reason |
|------|-------|--------|
| Inter-daemon state sharing | HIGH | Extending proven pattern used since v1.0, 11 milestones of production validation |
| Hysteresis/debounce | HIGH | Reusing exact counter pattern from 3 existing implementations |
| Config schema extension | HIGH | Following established BaseConfig/SCHEMA pattern with validate_field() |
| Signal fusion via confidence scoring | HIGH | Additive weighted scoring already implemented; adding one more term |
| Backward compatibility | HIGH | New JSON key + optional YAML section with defaults = non-breaking |

## Sources

All from direct codebase analysis (no external sources needed for this milestone):
- `src/wanctl/state_utils.py` -- atomic_write_json / safe_json_load_file (existing IPC)
- `src/wanctl/wan_controller_state.py` -- WANControllerState.save() (writer, state schema)
- `src/wanctl/autorate_continuous.py` -- QueueController.adjust_4state() (zone computation, state source)
- `src/wanctl/steering/daemon.py` -- BaselineLoader (existing cross-daemon reader), SteeringDaemon._update_state_machine_unified() (decision point)
- `src/wanctl/steering/congestion_assessment.py` -- StateThresholds, assess_congestion_state() (hysteresis pattern)
- `src/wanctl/steering/steering_confidence.py` -- compute_confidence(), ConfidenceSignals (scoring integration point)
- `src/wanctl/config_base.py` -- BaseConfig, validate_schema() (config extension pattern)
- `configs/steering.yaml` -- production steering config (YAML structure)
- `configs/spectrum.yaml` -- production autorate config (state source path)
- `.planning/PROJECT.md` -- v1.11 feature requirements and constraints
