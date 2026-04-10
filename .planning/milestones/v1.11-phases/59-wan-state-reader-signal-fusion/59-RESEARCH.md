# Phase 59: WAN State Reader + Signal Fusion - Research

**Researched:** 2026-03-09
**Domain:** Confidence scoring extension, cross-daemon signal fusion, fail-safe defaults
**Confidence:** HIGH

## Summary

Phase 59 integrates WAN congestion zone data (produced by autorate in Phase 58) into the steering daemon's confidence scoring system. The steering daemon already reads the autorate state file every cycle to obtain baseline RTT via `BaselineLoader.load_baseline_rtt()`. This phase extends that same read to also extract `congestion.dl_state`, then maps the zone to new WAN-specific weight constants in `compute_confidence()`. A recovery gate in `update_recovery_timer()` blocks steering recovery unless WAN zone is GREEN or unavailable.

The implementation touches four production code areas: (1) `BaselineLoader` to return WAN zone alongside baseline RTT, (2) `ConfidenceSignals` dataclass to carry the WAN zone, (3) `compute_confidence()` to apply WAN weights, (4) `update_recovery_timer()` to add the WAN GREEN gate. All changes follow established patterns already present in `steering_confidence.py`. The staleness check for WAN zone (5 seconds) reuses the file mtime already available from the existing `_check_staleness()` method.

Weight analysis confirms: WAN_RED=25 satisfies all constraints -- alone (25 < 55 steer_threshold = FUSE-03), combined with CAKE RED (25+50=75 > 55 = FUSE-04), and follows the same 2:1 ratio as CAKE RED:SOFT_RED. WAN_SOFT_RED=12 follows the same proportional scaling.

**Primary recommendation:** Extend `BaselineLoader` to return a `(baseline_rtt, wan_zone)` tuple, add `wan_zone: str | None` to `ConfidenceSignals`, add `WAN_RED=25` and `WAN_SOFT_RED=12` to `ConfidenceWeights`, apply WAN weight in `compute_confidence()` only when zone is not None and not GREEN, and add `wan_zone in ("GREEN", None)` to the recovery eligibility check.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
None -- all implementation decisions delegated to Claude's discretion, informed by requirements, existing CAKE weight patterns, and the "WAN is amplifying only" constraint.

### Claude's Discretion

**WAN weight magnitude:**
- WAN_RED weight must be < steer_threshold (~55) to satisfy FUSE-03
- Should follow existing weight scaling: CAKE RED=50, SOFT_RED=25, YELLOW=10
- WAN weights should be meaningful amplifiers but never dominant -- research should validate specific values
- WAN_SOFT_RED weight should be proportionally lower than WAN_RED (same ratio as CAKE SOFT_RED:RED)

**Recovery gate strictness:**
- FUSE-05: Recovery requires WAN GREEN (or unavailable) in addition to existing CAKE checks
- Whether WAN YELLOW blocks recovery is at Claude's discretion -- research should inform based on operational safety
- Recovery gate integrates with existing `update_recovery_timer()` -- not a separate timer

**Sustained WAN RED detection:**
- Whether WAN RED contributes immediately or requires sustained cycles is at Claude's discretion
- Consider: autorate zone is already EWMA-filtered with streak counters (noted in REQUIREMENTS.md Out of Scope: "WAN state EWMA smoothing" rejected as "double-smoothing")
- This suggests immediate contribution may be appropriate since the signal is already filtered upstream

**State file read integration:**
- WAN zone extracted in `BaselineRTTLoader.load_baseline_rtt()` from same `safe_json_load_file()` call (FUSE-01: zero additional I/O)
- Return both baseline_rtt and WAN zone from the loader, or extend the loader to expose zone separately
- Zone accessed via `state.get("congestion", {}).get("dl_state", None)` per Phase 58 context

**Staleness and degradation:**
- SAFE-01: Zone older than 5s defaults to GREEN (fail-safe)
- SAFE-02: Autorate completely unavailable (state is None) -> skip WAN weight entirely (None = no signal)
- Staleness check can reuse existing `_check_staleness()` infrastructure in BaselineRTTLoader

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| FUSE-01 | Steering reads WAN zone from autorate state file (same read as baseline RTT, zero additional I/O) | `BaselineLoader.load_baseline_rtt()` already calls `safe_json_load_file()` on the autorate state file at line 582; zone extraction adds `state.get("congestion", {}).get("dl_state", None)` to the same method -- no new file I/O |
| FUSE-02 | WAN zone mapped to confidence weights (WAN_RED, WAN_SOFT_RED) in `compute_confidence()` | `ConfidenceWeights` class-level constants (line 27-64) extended with WAN_RED=25, WAN_SOFT_RED=12; `compute_confidence()` adds a WAN zone block after existing CAKE state block |
| FUSE-03 | WAN state alone cannot trigger steering (WAN_RED < steer_threshold enforced by weight values) | WAN_RED=25 < steer_threshold=55; even WAN_RED + max non-CAKE signals (RTT_DELTA_SEVERE=25) = 50 < 55; mathematically impossible to steer without CAKE signal |
| FUSE-04 | Sustained WAN RED amplifies CAKE-based signals toward steer threshold | WAN_RED=25 + CAKE RED=50 = 75 >> 55; WAN_RED=25 + CAKE YELLOW=10 = 35, needs additional signal (+RTT_DELTA_HIGH=15 = 50, still needs queue or drops); WAN zone contributes immediately (already EWMA-filtered upstream, no double-smoothing) |
| FUSE-05 | Recovery eligibility requires WAN state GREEN (or unavailable) in addition to existing CAKE checks | `update_recovery_timer()` line 314 `recovery_eligible` check extended with `and (wan_zone in ("GREEN", None))` |
| SAFE-01 | Stale WAN state (>5s) defaults to GREEN (fail-safe) | `BaselineLoader` checks `file_age` via `stat().st_mtime` in `_check_staleness()` (line 620-637); add WAN zone staleness check with 5s threshold, return "GREEN" if stale |
| SAFE-02 | Graceful degradation when autorate unavailable (None = skip WAN weight) | When `safe_json_load_file()` returns None (line 588), `load_baseline_rtt()` returns None for both baseline and zone; `compute_confidence()` skips WAN weight block when `wan_zone is None` |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python | 3.12 | Runtime | Project standard |
| pytest | existing | Test framework | Project standard |

### Supporting
No new libraries required. Phase 59 uses only existing infrastructure.

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Returning tuple from `load_baseline_rtt()` | Storing zone on BaselineLoader instance attribute | Tuple is explicit, avoids stale state on loader object; instance attr would require careful reset semantics |
| Separate staleness threshold constant (5s) for WAN zone | Reusing existing STALE_BASELINE_THRESHOLD_SECONDS (300s) | WAN zone staleness is operationally different -- 5s matches autorate cycle rate (20Hz = 50ms), while baseline staleness is 5 minutes because baseline updates infrequently; separate constant is correct |

## Architecture Patterns

### Recommended Changes by File

```
src/wanctl/steering/
  steering_confidence.py    # ConfidenceWeights + ConfidenceSignals + compute_confidence + update_recovery_timer
  daemon.py                 # BaselineLoader + SteeringDaemon._build_confidence_signals wiring
tests/
  test_steering_confidence.py  # New tests for WAN weight scoring + recovery gate
  test_steering_daemon.py      # Integration test for BaselineLoader zone extraction
```

### Pattern 1: BaselineLoader Returns Tuple

**What:** Change `load_baseline_rtt()` return type from `float | None` to `tuple[float | None, str | None]` where second element is WAN zone.

**When to use:** When multiple values must be extracted from the same file read.

**Why this approach:** FUSE-01 mandates zero additional I/O. The `safe_json_load_file()` result is local variable `state` at line 582. Zone extraction is a `dict.get()` on the same dict. Returning a tuple makes the zone available to the caller without storing it on the loader instance (which would require lifecycle management).

**Example:**
```python
# In BaselineLoader.load_baseline_rtt()
def load_baseline_rtt(self) -> tuple[float | None, str | None]:
    """
    Load baseline RTT and WAN congestion zone from primary WAN autorate state file.
    Returns (baseline_rtt, wan_zone) tuple.
    wan_zone is None if autorate unavailable or state file missing congestion data.
    wan_zone is "GREEN" if state file is stale (>5s, fail-safe).
    """
    state = safe_json_load_file(
        self.config.primary_state_file,
        logger=self.logger,
        error_context="autorate state",
    )

    if state is None:
        return None, None  # SAFE-02: autorate unavailable

    # Check file staleness
    wan_zone_stale = self._is_wan_zone_stale()

    # Extract WAN zone (FUSE-01: same dict, zero additional I/O)
    wan_zone: str | None = None
    if not wan_zone_stale:
        wan_zone = state.get("congestion", {}).get("dl_state", None)
    else:
        wan_zone = "GREEN"  # SAFE-01: stale defaults to GREEN

    # ... existing baseline_rtt extraction unchanged ...

    return baseline_rtt, wan_zone
```

### Pattern 2: WAN Weight in compute_confidence()

**What:** Add WAN zone weight block to the scoring function, following the same additive pattern as existing CAKE/RTT/drops/queue blocks.

**When to use:** When a new signal source contributes to the confidence score.

**Example:**
```python
# In ConfidenceWeights
WAN_RED = 25          # WAN congestion amplifier (< steer_threshold alone)
WAN_SOFT_RED = 12     # WAN moderate congestion amplifier

# In compute_confidence()
# WAN zone amplification (only when available, never dominant)
if signals.wan_zone == "RED":
    score += ConfidenceWeights.WAN_RED
    contributors.append("WAN_RED")
elif signals.wan_zone == "SOFT_RED":
    score += ConfidenceWeights.WAN_SOFT_RED
    contributors.append("WAN_SOFT_RED")
# GREEN, YELLOW, None: no WAN contribution
```

### Pattern 3: Recovery Gate Extension

**What:** Add WAN zone check to existing `recovery_eligible` boolean in `update_recovery_timer()`.

**When to use:** When recovery must be gated on an additional condition.

**Example:**
```python
# In update_recovery_timer() -- extend existing check
recovery_eligible = (
    confidence <= self.recovery_threshold
    and cake_state == "GREEN"
    and rtt_delta < 10.0
    and drops < 0.001
    and wan_zone in ("GREEN", None)  # FUSE-05: WAN must be clear or unavailable
)
```

### Anti-Patterns to Avoid

- **Double-smoothing WAN zone:** Requirements explicitly reject "WAN state EWMA smoothing" as double-smoothing. Autorate zone is already EWMA-filtered with streak counters. Use WAN zone as-is, contributing immediately.
- **WAN weight as dominant signal:** WAN_RED must remain < steer_threshold. Never set WAN weights high enough to approach or exceed threshold alone.
- **Separate file read for WAN zone:** FUSE-01 mandates zero additional I/O. Never call `safe_json_load_file()` a second time for zone data.
- **Storing zone on BaselineLoader instance without lifecycle management:** If using instance attribute approach, must handle stale zone when file read fails. Tuple return avoids this entirely.
- **WAN YELLOW contributing to score:** WAN YELLOW is a weak signal (autorate delta 15-45ms). Adding weight would make the system overly sensitive. Only RED and SOFT_RED contribute.
- **WAN YELLOW blocking recovery:** WAN YELLOW indicates early warning, not confirmed congestion. Blocking recovery on YELLOW would make the system too sticky. Only RED/SOFT_RED should block recovery (via the confidence score already exceeding recovery_threshold).

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| State file reading | Custom JSON parser | `safe_json_load_file()` already called in `load_baseline_rtt()` | Error handling, logging, default values already handled |
| Staleness detection | Custom file age checker | Extend existing `_check_staleness()` pattern (st_mtime comparison) | Same file stat, same pattern, consistent approach |
| Atomic state key extraction | Try/except chains | `state.get("congestion", {}).get("dl_state", None)` | Standard Python dict traversal, returns None safely on any missing key |
| WAN zone sustained detection | Deque-based history tracking | Use zone as-is (already EWMA-filtered upstream) | REQUIREMENTS.md explicitly rejects double-smoothing |

**Key insight:** This phase adds minimal new code because every infrastructure component already exists. The only novel logic is the weight values and the recovery gate condition.

## Common Pitfalls

### Pitfall 1: Breaking `update_baseline_rtt()` callers when changing return type
**What goes wrong:** `load_baseline_rtt()` currently returns `float | None`. Changing to a tuple breaks every call site.
**Why it happens:** There are at least 2 callers: `SteeringDaemon.update_baseline_rtt()` (line 1074) and tests.
**How to avoid:** Update all callers to unpack the tuple: `baseline_rtt, wan_zone = self.baseline_loader.load_baseline_rtt()`. Search for all references before changing the signature.
**Warning signs:** Tests failing with "cannot unpack non-iterable float" or "cannot unpack non-iterable NoneType".

### Pitfall 2: Zone staleness check using wrong threshold
**What goes wrong:** Using `STALE_BASELINE_THRESHOLD_SECONDS` (300s) instead of a new 5-second WAN zone threshold.
**Why it happens:** The existing `_check_staleness()` uses the 300s constant. Copy-paste error.
**How to avoid:** Create a separate `STALE_WAN_ZONE_THRESHOLD_SECONDS = 5` constant. The 5-second threshold comes from SAFE-01 and matches autorate's 50ms cycle rate (100 cycles of data within 5 seconds).
**Warning signs:** WAN zone contributes to scoring even when autorate has been down for minutes.

### Pitfall 3: WAN zone contributing even when `None`
**What goes wrong:** `None` compared with string operations or not properly gated, causing `TypeError` or unexpected scoring.
**Why it happens:** Zone is None when autorate is unavailable (SAFE-02) or state file lacks congestion key (pre-Phase 58 state files).
**How to avoid:** `compute_confidence()` must check `if signals.wan_zone == "RED"` (not truthiness). None defaults to no WAN contribution (SAFE-02).
**Warning signs:** TypeError in scoring, or stale/missing zone adding score when it shouldn't.

### Pitfall 4: Recovery gate too strict when WAN unavailable
**What goes wrong:** Recovery blocked when autorate is down because `wan_zone is None` not included in the gate.
**Why it happens:** Gate checks `wan_zone == "GREEN"` without also allowing `None`.
**How to avoid:** Use `wan_zone in ("GREEN", None)` -- None means "no WAN signal, skip this gate".
**Warning signs:** Steering never recovers when autorate is restarting or unavailable.

### Pitfall 5: Not passing `wan_zone` through the entire signal chain
**What goes wrong:** Zone extracted in BaselineLoader but never reaches `compute_confidence()` or `update_recovery_timer()`.
**Why it happens:** Multiple intermediate layers: BaselineLoader -> SteeringDaemon.update_baseline_rtt() -> run_cycle() -> update_state_machine() -> ConfidenceSignals -> compute_confidence(). Zone must be threaded through all of them.
**How to avoid:** Map the complete data flow before coding:
1. `BaselineLoader.load_baseline_rtt()` returns `(float|None, str|None)`
2. `SteeringDaemon.update_baseline_rtt()` unpacks and stores zone (instance attr or state dict)
3. `SteeringDaemon.update_state_machine()` builds `ConfidenceSignals` with `wan_zone`
4. `ConfidenceController.evaluate()` passes zone to `update_recovery_timer()`
**Warning signs:** WAN zone always None in confidence logs despite autorate running.

### Pitfall 6: MagicMock leaking through zone value in tests
**What goes wrong:** Tests using `MagicMock` for config/state inadvertently produce `MagicMock` as zone value, which is truthy and matches no string comparison.
**Why it happens:** Known project pattern (see MEMORY.md "MagicMock guard").
**How to avoid:** Use explicit fixtures with real string values for zone. When zone comes from a mock, ensure it returns a real string or None.
**Warning signs:** Tests pass when they shouldn't because `MagicMock != "RED"` silently skips the weight.

### Pitfall 7: update_recovery_timer() signature change breaking ConfidenceController
**What goes wrong:** Adding `wan_zone` parameter to `update_recovery_timer()` but not updating the call in `ConfidenceController.evaluate()`.
**Why it happens:** `update_recovery_timer()` is called from `ConfidenceController.evaluate()` at line 606 with 6 positional args.
**How to avoid:** Update both the method signature and the call site. Consider making `wan_zone` a keyword argument with default `None` for backward compatibility.
**Warning signs:** TypeError about missing positional argument, or recovery never working because wan_zone defaults incorrectly.

## Code Examples

### Verified: Current `load_baseline_rtt()` (to be extended)
```python
# Source: src/wanctl/steering/daemon.py:575-618
def load_baseline_rtt(self) -> float | None:
    state = safe_json_load_file(
        self.config.primary_state_file,
        logger=self.logger,
        error_context="autorate state",
    )
    if state is None:
        return None
    self._check_staleness()
    if "ewma" in state and "baseline_rtt" in state["ewma"]:
        # ... validation and return ...
```

### Verified: Current `ConfidenceSignals` dataclass (to be extended)
```python
# Source: src/wanctl/steering/steering_confidence.py:67-82
@dataclass
class ConfidenceSignals:
    cake_state: str  # "GREEN", "YELLOW", "SOFT_RED", "RED"
    rtt_delta_ms: float
    drops_per_sec: float
    queue_depth_pct: float
    cake_state_history: list[str] = field(default_factory=list)
    drops_history: list[float] = field(default_factory=list)
    queue_history: list[float] = field(default_factory=list)
```

### Verified: Current `recovery_eligible` check (to be extended)
```python
# Source: src/wanctl/steering/steering_confidence.py:314-319
recovery_eligible = (
    confidence <= self.recovery_threshold
    and cake_state == "GREEN"
    and rtt_delta < 10.0
    and drops < 0.001
)
```

### Verified: Current `update_state_machine()` builds ConfidenceSignals
```python
# Source: src/wanctl/steering/daemon.py:1150-1158
phase2b_signals = ConfidenceSignals(
    cake_state=state.get("congestion_state", "GREEN"),
    rtt_delta_ms=signals.rtt_delta,
    drops_per_sec=float(signals.cake_drops),
    queue_depth_pct=float(signals.queued_packets),
    cake_state_history=list(state.get("cake_state_history", [])),
    drops_history=list(state.get("cake_drops_history", [])),
    queue_history=list(state.get("queue_depth_history", [])),
)
```

### Verified: Current `update_baseline_rtt()` caller
```python
# Source: src/wanctl/steering/daemon.py:1069-1094
def update_baseline_rtt(self) -> bool:
    baseline_rtt = self.baseline_loader.load_baseline_rtt()
    if baseline_rtt is not None:
        old_baseline = self.state_mgr.state["baseline_rtt"]
        self.state_mgr.state["baseline_rtt"] = baseline_rtt
        # ... logging ...
        return True
    else:
        # ... fallback to cached ...
```

### Verified: State file format (produced by Phase 58)
```python
# Source: src/wanctl/autorate_continuous.py:1642
congestion={"dl_state": self._dl_zone, "ul_state": self._ul_zone}
# Produces JSON:
# {"congestion": {"dl_state": "RED", "ul_state": "GREEN"}, "ewma": {...}, ...}
```

## Weight Analysis

### Recommended Values

| Weight | Value | Rationale |
|--------|-------|-----------|
| WAN_RED | 25 | Same as CAKE SOFT_RED_SUSTAINED; < 55 threshold (FUSE-03); meaningful amplifier |
| WAN_SOFT_RED | 12 | ~half of WAN_RED; follows CAKE ratio pattern (SOFT_RED:RED ~= 1:2) |
| WAN_YELLOW | 0 (skip) | Too weak a signal; autorate YELLOW is delta 15-45ms, not confirmed congestion |
| WAN_GREEN | 0 (skip) | No contribution from healthy WAN |

### Score Scenarios

| Scenario | Score | vs Threshold (55) | Behavior |
|----------|-------|-------------------|----------|
| WAN_RED alone | 25 | 25 < 55 | No steer (FUSE-03 satisfied) |
| WAN_RED + RTT_DELTA_SEVERE | 25+25=50 | 50 < 55 | No steer (WAN amplifies but still needs CAKE) |
| CAKE RED alone | 50 | 50 < 55 | No steer (needs sustain timer or additional signal) |
| CAKE RED + WAN_RED | 50+25=75 | 75 > 55 | Steer (FUSE-04 satisfied, strong combined signal) |
| CAKE RED + WAN_SOFT_RED | 50+12=62 | 62 > 55 | Steer (moderate WAN + severe CAKE) |
| CAKE YELLOW + WAN_RED | 10+25=35 | 35 < 55 | No steer (weak CAKE + WAN insufficient) |
| CAKE YELLOW + WAN_RED + RTT_HIGH | 10+25+15=50 | 50 < 55 | No steer (close but needs more evidence) |
| CAKE YELLOW + WAN_RED + RTT_SEVERE | 10+25+25=60 | 60 > 55 | Steer (multiple corroborating signals) |
| CAKE SOFT_RED_SUSTAINED + WAN_RED | 25+25=50 | 50 < 55 | No steer (needs one more signal) |
| CAKE SOFT_RED_SUSTAINED + WAN_RED + drops | 25+25+10=60 | 60 > 55 | Steer (three corroborating signals) |

### Recovery Gate Analysis

**Recommendation: WAN YELLOW should NOT block recovery.**

Rationale:
- WAN YELLOW indicates autorate delta 15-45ms -- moderate, not critical
- Recovery already requires CAKE GREEN + confidence <= 20 + rtt_delta < 10ms + drops < 0.001
- These conditions are very strict already; WAN YELLOW on top makes recovery nearly impossible
- If WAN is YELLOW, the confidence score from WAN_YELLOW=0 adds nothing, so confidence will naturally be low if CAKE is GREEN
- Only RED and SOFT_RED represent confirmed congestion that should prevent recovery

Recovery gate: `wan_zone in ("GREEN", "YELLOW", None)` -- or equivalently, `wan_zone not in ("RED", "SOFT_RED")`.

Simpler formulation: `wan_zone in ("GREEN", None)` if we want YELLOW to block. But given the analysis above, recommend **not** blocking on YELLOW: use `wan_zone not in ("RED", "SOFT_RED")`.

**Wait -- re-reading FUSE-05:** "Recovery from steering requires WAN zone to be GREEN (or unavailable)." This is literal: GREEN or None. YELLOW blocks recovery per the requirement. This is a locked requirement, not discretion.

**Revised recommendation:** `wan_zone in ("GREEN", None)` -- YELLOW, SOFT_RED, and RED all block recovery. This matches the requirement text exactly.

## Staleness Design

### WAN Zone Staleness (5s, SAFE-01)

The existing `_check_staleness()` method uses `stat().st_mtime` to detect stale files. For WAN zone staleness, two approaches:

**Approach A: File mtime check (recommended)**
- Reuse `stat().st_mtime` from `_check_staleness()` with a 5s threshold
- Pro: Zero additional I/O (stat is already called for baseline staleness)
- Pro: Simple, well-tested pattern
- Con: File-level granularity (not per-field)

**Approach B: Timestamp field in state file**
- Read `state["timestamp"]` and parse ISO-8601
- Pro: Per-save granularity
- Con: Parsing overhead, timezone handling, additional code

**Recommendation:** Approach A. File mtime is authoritative for "when was autorate last active" and the 5-second threshold is generous relative to autorate's 50ms cycle (100 cycles). The baseline staleness check already captures `file_age` -- WAN zone staleness check can reuse this value.

Implementation detail: `_check_staleness()` currently only logs a warning. For WAN zone, we need the staleness boolean to be returned or stored. Options:
1. Add a `_wan_zone_stale` instance attribute set by `_check_staleness()`
2. Create a separate `_is_wan_zone_stale()` method returning bool
3. Make `load_baseline_rtt()` check file_age directly

Option 2 is cleanest: separate method, separate threshold, clear return value.

```python
STALE_WAN_ZONE_THRESHOLD_SECONDS = 5

def _is_wan_zone_stale(self) -> bool:
    """Check if autorate state file is too old for WAN zone to be trusted."""
    try:
        file_age = time.time() - self.config.primary_state_file.stat().st_mtime
    except OSError:
        return True  # Cannot stat = treat as stale (fail-safe)
    return file_age > STALE_WAN_ZONE_THRESHOLD_SECONDS
```

Note: This calls `stat()` separately from `_check_staleness()`, but `stat()` on tmpfs is < 1 microsecond. Alternatively, compute file_age once in `load_baseline_rtt()` and pass it to both methods.

## Data Flow Map

Complete signal chain from autorate state file to steering decision:

```
autorate state file (JSON on tmpfs)
  |
  | safe_json_load_file() -- single I/O operation
  v
BaselineLoader.load_baseline_rtt()
  |-- extracts: ewma.baseline_rtt (existing)
  |-- extracts: congestion.dl_state (new, FUSE-01)
  |-- checks: file mtime for staleness (SAFE-01)
  |-- returns: (float | None, str | None)
  v
SteeringDaemon.update_baseline_rtt()
  |-- unpacks: baseline_rtt, wan_zone
  |-- stores: baseline_rtt in state (existing)
  |-- stores: wan_zone (new, instance attr or state dict key)
  v
SteeringDaemon.run_cycle()
  |-- calls: update_baseline_rtt() (line 1314)
  |-- builds: CongestionSignals (line 1365, existing)
  v
SteeringDaemon.update_state_machine()
  |-- builds: ConfidenceSignals with wan_zone (line 1150, extended)
  |-- calls: ConfidenceController.evaluate()
  v
ConfidenceController.evaluate()
  |-- calls: compute_confidence(signals) -- WAN weight applied here (FUSE-02, FUSE-03, FUSE-04)
  |-- calls: update_recovery_timer(..., wan_zone=signals.wan_zone) -- recovery gate (FUSE-05)
  v
Steering decision (ENABLE_STEERING / DISABLE_STEERING / None)
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Steering uses only CAKE-local signals | Steering incorporates cross-daemon WAN zone | Phase 59 (this phase) | First cross-daemon signal fusion in wanctl |
| BaselineLoader returns single value | Returns tuple with zone | Phase 59 | Enables zero-cost multi-value extraction |
| Recovery checks CAKE only | Recovery gates on WAN zone too | Phase 59 | Prevents premature recovery during WAN congestion |

## Open Questions

1. **WAN zone storage location in SteeringDaemon**
   - What we know: Zone must be accessible when building ConfidenceSignals in `update_state_machine()` (line 1150)
   - Options: (a) instance attribute `self._wan_zone`, (b) state dict key `state["wan_zone"]`, (c) pass through method chain
   - Recommendation: Instance attribute `self._wan_zone` set in `update_baseline_rtt()`, initialized to `None` in `__init__()`. This follows the pattern of `self.baseline_loader` and avoids polluting the state dict with cross-daemon data. State dict is for steering's own state, not autorate's.

2. **WAN_YELLOW weight value**
   - What we know: CONTEXT.md mentions only WAN_RED and WAN_SOFT_RED weights
   - Recommendation: WAN_YELLOW = 0 (no contribution). Autorate YELLOW is delta 15-45ms, a weak signal. Including it would make the system overly sensitive and contradicts the "amplifying only" philosophy. If needed later, this is a single constant change.

3. **Whether `update_recovery_timer()` needs `wan_zone` as a new parameter vs reading from `ConfidenceSignals`**
   - What we know: Currently, `update_recovery_timer()` takes individual values (confidence, cake_state, rtt_delta, drops, current_state) rather than the signals dataclass
   - Recommendation: Add `wan_zone: str | None = None` as a keyword parameter. Default None preserves backward compatibility. The recovery gate is a simple `and` condition.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (existing) |
| Config file | pyproject.toml (existing) |
| Quick run command | `.venv/bin/pytest tests/test_steering_confidence.py -x -v` |
| Full suite command | `.venv/bin/pytest tests/ -v` |

### Phase Requirements -> Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| FUSE-01 | Zone extracted from same file read as baseline RTT | unit | `.venv/bin/pytest tests/test_steering_daemon.py -k "baseline" -x` | Extend existing |
| FUSE-02 | WAN zone mapped to confidence weights | unit | `.venv/bin/pytest tests/test_steering_confidence.py -k "wan" -x` | New tests needed (Wave 0) |
| FUSE-03 | WAN_RED alone < steer_threshold | unit | `.venv/bin/pytest tests/test_steering_confidence.py -k "wan_red_alone" -x` | New test needed (Wave 0) |
| FUSE-04 | WAN_RED + CAKE signal pushes toward threshold | unit | `.venv/bin/pytest tests/test_steering_confidence.py -k "wan_amplifies" -x` | New test needed (Wave 0) |
| FUSE-05 | Recovery requires WAN GREEN or None | unit | `.venv/bin/pytest tests/test_steering_confidence.py -k "recovery_wan" -x` | New test needed (Wave 0) |
| SAFE-01 | Stale zone (>5s) defaults to GREEN | unit | `.venv/bin/pytest tests/test_steering_daemon.py -k "stale_wan" -x` | New test needed (Wave 0) |
| SAFE-02 | Autorate unavailable skips WAN weight | unit | `.venv/bin/pytest tests/test_steering_confidence.py -k "wan_none" -x` | New test needed (Wave 0) |

### Sampling Rate
- **Per task commit:** `.venv/bin/pytest tests/test_steering_confidence.py tests/test_steering_daemon.py -x -v`
- **Per wave merge:** `.venv/bin/pytest tests/ -v`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_steering_confidence.py` -- New test class `TestWANZoneWeights` covering FUSE-02, FUSE-03, FUSE-04
- [ ] `tests/test_steering_confidence.py` -- New tests in existing recovery test class for FUSE-05 WAN gate
- [ ] `tests/test_steering_confidence.py` -- New tests for SAFE-02 (wan_zone=None skips weight)
- [ ] `tests/test_steering_daemon.py` -- New tests for BaselineLoader zone extraction (FUSE-01) and staleness (SAFE-01)

*(No new framework install needed -- pytest and all fixtures already in place)*

## Sources

### Primary (HIGH confidence)
- `src/wanctl/steering/steering_confidence.py` -- Full read of confidence scoring, weights, recovery timer, controller
- `src/wanctl/steering/daemon.py` -- Full read of BaselineLoader, SteeringDaemon, run_cycle, update_state_machine
- `src/wanctl/wan_controller_state.py` -- Full read of state file schema including Phase 58 congestion extension
- `src/wanctl/autorate_continuous.py` -- Verified zone production (_dl_zone, _ul_zone, save_state congestion param)
- `tests/test_steering_confidence.py` -- Full read of existing confidence test patterns

### Secondary (MEDIUM confidence)
- `.planning/phases/58-state-file-extension/58-01-SUMMARY.md` -- Phase 58 completion details and state file format
- `.planning/REQUIREMENTS.md` -- All FUSE and SAFE requirement definitions
- `.planning/phases/59-wan-state-reader-signal-fusion/59-CONTEXT.md` -- User decisions and code context

### Tertiary (LOW confidence)
None -- all findings verified from source code.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - no new libraries, all existing infrastructure
- Architecture: HIGH - verified every integration point in source code, traced complete data flow
- Pitfalls: HIGH - identified from actual code structure and known project patterns (MagicMock, tuple unpacking)
- Weight values: HIGH - mathematical verification against steer_threshold=55 with exhaustive scenario table

**Research date:** 2026-03-09
**Valid until:** 2026-04-09 (stable domain, no external dependencies)
