# Phase 61: Observability + Metrics - Research

**Researched:** 2026-03-09
**Domain:** WAN-aware steering observability (health endpoints, SQLite metrics, structured logging)
**Confidence:** HIGH

## Summary

Phase 61 adds WAN awareness observability to three existing systems: the steering health endpoint (port 9102), the SQLite metrics database (`/var/lib/wanctl/metrics.db`), and the steering daemon's structured logging. All three systems are well-established with clear extension patterns. No new dependencies, no new files, no new infrastructure -- strictly additive fields and log lines.

The health endpoint (`steering/health.py`) already exposes steering state, congestion, confidence, counters, thresholds, router connectivity, cycle budget, and disk space. Adding a `wan_awareness` section requires reading 4 values from the daemon: zone, staleness age, sustained cycle count from confidence timers, and the WAN contribution to the confidence score. The SQLite metrics writer already records 5 metrics per steering cycle via `write_metrics_batch()`; adding 1-3 WAN metrics (zone code, staleness, WAN weight applied) follows the exact same pattern. Logging requires adding WAN context to the two decision log lines in `steering_confidence.py` (ENABLE_STEERING and DISABLE_STEERING events).

**Primary recommendation:** Extend existing patterns in `steering/health.py`, `steering/daemon.py` run_cycle, and `steering_confidence.py` -- zero new modules needed.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| OBSV-01 | Health endpoint exposes WAN awareness state (zone, staleness, sustained cycles, confidence contribution) | Add `wan_awareness` dict to `_get_health_status()` in `steering/health.py`, reading from daemon's `_wan_zone`, `_wan_state_enabled`, `_get_effective_wan_zone()`, `baseline_loader._is_wan_zone_stale()`, and `confidence_controller.timer_state` |
| OBSV-02 | SQLite metrics record WAN awareness signal each cycle | Extend `metrics_batch` list in `run_cycle()` with WAN zone code and weight applied; uses existing `write_metrics_batch()` |
| OBSV-03 | Log output includes WAN state when it contributes to steering decisions | Enhance decision log lines in `compute_confidence()` contributors list (already includes "WAN_RED"/"WAN_SOFT_RED") and add WAN context to transition log lines |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python stdlib `json` | 3.12 | Health endpoint JSON serialization | Already used in `steering/health.py` |
| Python stdlib `sqlite3` | 3.12 | Metrics persistence | Already used via `storage/writer.py` |
| Python stdlib `logging` | 3.12 | Structured logging | Already used everywhere |
| Python stdlib `time` | 3.12 | Staleness age computation | Already used for monotonic/wall clock |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `storage.writer.MetricsWriter` | internal | SQLite batch writes | Already instantiated as `self._metrics_writer` in daemon |
| `steering_confidence.TimerState` | internal | Access degrade_timer, confidence_score | Already on `self.confidence_controller.timer_state` |
| `steering_confidence.ConfidenceWeights` | internal | WAN weight constants for display | Already imported by daemon |

### Alternatives Considered
None needed -- all requirements extend existing systems.

**Installation:**
```bash
# No new packages required
```

## Architecture Patterns

### Recommended Project Structure
```
src/wanctl/
  steering/
    health.py          # OBSV-01: Add wan_awareness section to _get_health_status()
    daemon.py          # OBSV-02: Extend metrics_batch in run_cycle()
    steering_confidence.py  # OBSV-03: Enhance contributor strings with WAN context
```

No new files. All changes are additive to existing methods.

### Pattern 1: Health Endpoint Section Addition
**What:** Add a `wan_awareness` dict to the health response, following the exact pattern of existing sections (`steering`, `congestion`, `confidence`, `counters`, etc.)
**When to use:** OBSV-01
**Example:**
```python
# In steering/health.py :: _get_health_status()
# Pattern follows existing sections at lines 149-214

# WAN awareness state (OBSV-01)
if self.daemon is not None:
    wan_section: dict[str, Any] = {
        "enabled": self.daemon._wan_state_enabled,
    }
    if self.daemon._wan_state_enabled:
        wan_zone = self.daemon._wan_zone  # Raw zone from autorate
        effective_zone = self.daemon._get_effective_wan_zone()  # After enabled/grace gates
        wan_section["zone"] = wan_zone
        wan_section["effective_zone"] = effective_zone
        wan_section["grace_period_active"] = self.daemon._is_wan_grace_period_active()

        # Staleness
        staleness_age = self.daemon.baseline_loader._get_wan_zone_age()  # New helper
        wan_section["staleness_age_sec"] = round(staleness_age, 1) if staleness_age else None
        wan_section["stale"] = self.daemon.baseline_loader._is_wan_zone_stale()

        # Sustained cycle count from confidence timers
        if self.daemon.confidence_controller:
            ts = self.daemon.confidence_controller.timer_state
            wan_section["sustained_cycles"] = ...  # From degrade/recovery timer
            wan_section["confidence_contribution"] = ...  # WAN weight applied

    health["wan_awareness"] = wan_section
```

### Pattern 2: SQLite Metrics Batch Extension
**What:** Append WAN awareness metrics to the existing `metrics_batch` list in `run_cycle()`
**When to use:** OBSV-02
**Example:**
```python
# In steering/daemon.py :: run_cycle() around line 1617-1659
# Pattern follows existing metrics_batch at lines 1617-1658

# Add WAN awareness metrics to batch
if self._wan_state_enabled:
    wan_zone_val = {"GREEN": 0, "YELLOW": 1, "SOFT_RED": 2, "RED": 3}.get(
        self._wan_zone or "GREEN", 0
    )
    metrics_batch.append(
        (ts, self.config.primary_wan, "wanctl_wan_zone", float(wan_zone_val),
         {"zone": self._wan_zone or "GREEN"}, "raw")
    )
```

### Pattern 3: Structured Log Enhancement
**What:** Add WAN zone to existing log lines that fire on steering decisions
**When to use:** OBSV-03
**Example:**
```python
# In steering_confidence.py :: compute_confidence()
# WAN_RED/WAN_SOFT_RED already appended to contributors list (line 156, 159)
# Contributors like "WAN_RED" already appear in decision log lines

# Key: Also add WAN context to transition log in daemon.py execute_steering_transition()
# and to the degrade_timer/recovery_timer expiry log lines in steering_confidence.py
```

### Anti-Patterns to Avoid
- **Separate WAN polling for health endpoint:** Health reads daemon attributes directly (class-level reference pattern at line 79). Do NOT create a separate read path.
- **New metric names in Prometheus exporter:** OBSV-02 only covers SQLite storage. Prometheus exporter (metrics.py) is out of scope unless explicitly requested.
- **Logging every cycle's WAN state:** OBSV-03 says "when it contributes to a steering decision" -- only log WAN state on steer/recover transitions, not every 50ms cycle. The debug-level `[CONFIDENCE]` log already fires every cycle with contributors.
- **Creating a new _staleness_age method that opens files:** BaselineLoader already computes file age in `_is_wan_zone_stale()` and `_check_staleness()`. Add a small helper to return the numeric age, reusing the same `stat()` call pattern.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| JSON health response | New endpoint/server | Extend `_get_health_status()` in `steering/health.py` | Server already running on port 9102, pattern established |
| Metrics persistence | New database table/schema | Extend `metrics_batch` in `run_cycle()` with same schema | Schema handles arbitrary metric_name+labels, no migration needed |
| Staleness computation | New file watcher | Add `_get_wan_zone_age()` to BaselineLoader (3 lines) | `stat().st_mtime` already used in `_is_wan_zone_stale()` |

**Key insight:** All three observability requirements are strict extensions of existing infrastructure. The SQLite schema (`metrics` table) is generic (metric_name TEXT, value REAL, labels TEXT) -- no schema changes needed.

## Common Pitfalls

### Pitfall 1: Computing Sustained Cycle Count
**What goes wrong:** The term "sustained cycle count" from OBSV-01 is ambiguous -- it could mean the degrade_timer countdown, the red_count counter, or a custom WAN-specific counter.
**Why it happens:** Multiple counters track different "sustained" concepts.
**How to avoid:** Use the confidence controller's `timer_state.degrade_timer` or `timer_state.recovery_timer` as the sustained metric. Convert timer seconds to cycle count via `timer / cycle_interval`. The `red_count` in state tracks hysteresis samples, not confidence sustain.
**Warning signs:** If you're computing a new counter, you're probably duplicating an existing one.

### Pitfall 2: Staleness Age vs Boolean
**What goes wrong:** OBSV-01 asks for "staleness age" but BaselineLoader only has `_is_wan_zone_stale()` returning bool.
**Why it happens:** The boolean was sufficient for SAFE-01 fail-safe. Health endpoint needs the numeric age.
**How to avoid:** Add `_get_wan_zone_age() -> float | None` returning `time.time() - stat().st_mtime`, or return `None` on `OSError`. Keep `_is_wan_zone_stale()` calling this internally.
**Warning signs:** Duplicate `stat()` calls in the same cycle.

### Pitfall 3: Thread Safety on Health Endpoint
**What goes wrong:** Health endpoint runs in a separate thread (background HTTPServer). Reading daemon attributes must be safe.
**Why it happens:** 50ms cycles update daemon state while health endpoint reads it.
**How to avoid:** All daemon attributes being read are simple Python objects (str, float, bool, None). Python GIL ensures atomic reads of these. The existing health endpoint already reads `daemon.state_mgr.state` (a dict) without locks -- same pattern is safe for `_wan_zone`, `_wan_state_enabled`, etc. Do NOT add locking.
**Warning signs:** Adding threading.Lock for health reads -- the existing endpoint doesn't use one and works fine.

### Pitfall 4: Confidence Contribution Value
**What goes wrong:** "Confidence contribution" could mean the WAN weight constant (25 for RED), or the actual score contribution in the last cycle, or the effective weight after config override.
**Why it happens:** Multiple weight values exist (class constant, config override, effective after clamping).
**How to avoid:** Report the actual weight that was applied in the last confidence computation. This is the value from `wan_red_weight` or `wan_soft_red_weight` params passed to `compute_confidence()`, falling back to class constants. Store it on the daemon after each evaluate() call, or compute from the contributors list (if "WAN_RED" is in contributors, weight = `self._wan_red_weight or ConfidenceWeights.WAN_RED`).
**Warning signs:** Hardcoding the class constant value instead of reflecting the config-driven value.

### Pitfall 5: Logging Noise at 20Hz
**What goes wrong:** Adding WAN info to every measurement log line creates 20 lines/sec of WAN data even when WAN is GREEN and not contributing.
**Why it happens:** OBSV-03 says "when it contributes to a steering decision" but developer adds it to the per-cycle measurement log.
**How to avoid:** Only add WAN context to:
1. Decision log lines (ENABLE_STEERING / DISABLE_STEERING events)
2. Transition warning/info lines in `execute_steering_transition()`
3. The existing `[CONFIDENCE]` debug log already includes "WAN_RED" in contributors

Do NOT add WAN to the per-cycle `[SPECTRUM_GOOD]` measurement log line.
**Warning signs:** WAN state appearing in every single log line.

### Pitfall 6: Metric Name Consistency
**What goes wrong:** Using inconsistent metric names like `wanctl_wan_state` vs `wanctl_wan_zone` vs `wanctl_wan_awareness_zone`.
**Why it happens:** Multiple naming conventions exist in codebase.
**How to avoid:** Follow existing pattern: `wanctl_` prefix + descriptive name. Use `wanctl_wan_zone` (numeric, like `wanctl_state`). Add zone string in labels for human readability. Register in `storage/schema.py` STORED_METRICS dict for documentation.

## Code Examples

### Example 1: Health Endpoint wan_awareness Section
```python
# Source: Extrapolated from steering/health.py:103-238 pattern
# In _get_health_status(), after the existing "confidence" section:

# WAN awareness (OBSV-01)
wan_awareness: dict[str, Any] = {
    "enabled": self.daemon._wan_state_enabled,
}
if self.daemon._wan_state_enabled:
    wan_awareness["zone"] = self.daemon._wan_zone
    wan_awareness["effective_zone"] = self.daemon._get_effective_wan_zone()
    wan_awareness["grace_period_active"] = self.daemon._is_wan_grace_period_active()
    wan_awareness["staleness_age_sec"] = round(
        self.daemon.baseline_loader._get_wan_zone_age() or 0.0, 1
    )
    wan_awareness["stale"] = self.daemon.baseline_loader._is_wan_zone_stale()

    # Sustained cycle count and confidence contribution
    if self.daemon.confidence_controller:
        ts = self.daemon.confidence_controller.timer_state
        # Degrade timer remaining (None = not active)
        wan_awareness["degrade_timer_remaining"] = (
            round(ts.degrade_timer, 2) if ts.degrade_timer is not None else None
        )
        # WAN contribution: effective weight if WAN zone is RED or SOFT_RED
        effective_zone = self.daemon._get_effective_wan_zone()
        if effective_zone == "RED":
            wan_awareness["confidence_contribution"] = (
                self.daemon._wan_red_weight or ConfidenceWeights.WAN_RED
            )
        elif effective_zone == "SOFT_RED":
            wan_awareness["confidence_contribution"] = (
                self.daemon._wan_soft_red_weight or ConfidenceWeights.WAN_SOFT_RED
            )
        else:
            wan_awareness["confidence_contribution"] = 0

health["wan_awareness"] = wan_awareness
```

### Example 2: SQLite Metrics Extension
```python
# Source: Extrapolated from steering/daemon.py:1607-1659 pattern
# In run_cycle(), inside the `if self._metrics_writer is not None:` block:

# WAN awareness metrics (OBSV-02)
if self._wan_state_enabled:
    zone_map = {"GREEN": 0, "YELLOW": 1, "SOFT_RED": 2, "RED": 3}
    effective_zone = self._get_effective_wan_zone()
    zone_val = zone_map.get(effective_zone or "GREEN", 0)
    metrics_batch.append(
        (ts, self.config.primary_wan, "wanctl_wan_zone",
         float(zone_val), {"zone": effective_zone or "none"}, "raw")
    )
```

### Example 3: BaselineLoader Staleness Age Helper
```python
# Source: Extrapolated from steering/daemon.py:761-767 pattern
# In BaselineLoader class:

def _get_wan_zone_age(self) -> float | None:
    """Get age of autorate state file in seconds.

    Returns:
        File age in seconds, or None if file inaccessible.
    """
    try:
        return time.time() - self.config.primary_state_file.stat().st_mtime
    except OSError:
        return None
```

### Example 4: Decision Logging with WAN Context
```python
# Source: Extrapolated from steering_confidence.py:256-274 pattern
# In TimerManager.update_degrade_timer(), when timer expires:

if timer_state.degrade_timer <= 0:
    # Include WAN context in decision log (OBSV-03)
    wan_info = ""
    if "WAN_RED" in timer_state.confidence_contributors:
        wan_info = " wan_zone=RED"
    elif "WAN_SOFT_RED" in timer_state.confidence_contributors:
        wan_info = " wan_zone=SOFT_RED"

    self.logger.warning(
        f"[CONFIDENCE] degrade_timer expired: confidence={confidence} "
        f"sustained={self.sustain_duration}s{wan_info}"
    )
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| No WAN awareness in health | Phase 61 adds wan_awareness section | v1.11 | Operators see WAN state in health checks |
| No WAN metrics in SQLite | Phase 61 adds wanctl_wan_zone metric | v1.11 | Historical WAN zone data queryable |
| WAN contributors in debug log only | Phase 61 adds WAN context to decision logs | v1.11 | Operators see WAN influence at INFO/WARNING level |

**Deprecated/outdated:**
- None -- all existing observability infrastructure is current and well-maintained.

## Open Questions

1. **"Sustained cycle count" exact definition**
   - What we know: OBSV-01 asks for "sustained cycle count." The confidence system tracks sustain via `degrade_timer` (seconds, not cycles). The hysteresis system tracks `red_count` and `good_count`.
   - What's unclear: Should we expose degrade_timer seconds, convert to cycle count, or use red_count?
   - Recommendation: Expose `degrade_timer` as seconds remaining (matches existing timer semantics). Optionally compute `sustained_cycles = degrade_timer / cycle_interval` for the health response.

2. **Prometheus exporter (metrics.py) scope**
   - What we know: OBSV-02 specifies "SQLite metrics database." Prometheus exporter at port 9100 is a separate system.
   - What's unclear: Should WAN metrics also be added to Prometheus exporter?
   - Recommendation: Stick to SQLite for Phase 61. Prometheus can be added later if needed. Keep scope tight.

3. **WAN awareness section when feature disabled**
   - What we know: Phase 60 context says "health endpoint can show 'WAN zone: available but disabled'."
   - What's unclear: How much detail to show when `wan_state.enabled: false` -- just `{"enabled": false}` or also show zone data?
   - Recommendation: Show `{"enabled": false, "zone": "RED"}` (raw zone still read from state file even when disabled). This enables staged rollout verification per Phase 60 decisions.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.x |
| Config file | pyproject.toml |
| Quick run command | `.venv/bin/pytest tests/test_steering_health.py tests/test_steering_metrics_recording.py -x -v` |
| Full suite command | `.venv/bin/pytest tests/ -v` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| OBSV-01a | Health endpoint includes wan_awareness section when enabled | unit | `.venv/bin/pytest tests/test_steering_health.py::TestWanAwarenessHealth -x` | Wave 0 |
| OBSV-01b | Health endpoint shows zone, staleness_age, stale flag | unit | `.venv/bin/pytest tests/test_steering_health.py::TestWanAwarenessHealth -x` | Wave 0 |
| OBSV-01c | Health endpoint shows confidence_contribution from WAN | unit | `.venv/bin/pytest tests/test_steering_health.py::TestWanAwarenessHealth -x` | Wave 0 |
| OBSV-01d | Health endpoint shows enabled:false when WAN disabled | unit | `.venv/bin/pytest tests/test_steering_health.py::TestWanAwarenessHealth -x` | Wave 0 |
| OBSV-01e | Health endpoint shows grace_period_active status | unit | `.venv/bin/pytest tests/test_steering_health.py::TestWanAwarenessHealth -x` | Wave 0 |
| OBSV-02a | SQLite records wanctl_wan_zone each cycle when enabled | unit | `.venv/bin/pytest tests/test_steering_metrics_recording.py::TestWanAwarenessMetrics -x` | Wave 0 |
| OBSV-02b | SQLite records wan zone with labels (zone name string) | unit | `.venv/bin/pytest tests/test_steering_metrics_recording.py::TestWanAwarenessMetrics -x` | Wave 0 |
| OBSV-02c | SQLite skips WAN metrics when feature disabled | unit | `.venv/bin/pytest tests/test_steering_metrics_recording.py::TestWanAwarenessMetrics -x` | Wave 0 |
| OBSV-03a | Steer decision log includes wan_zone when WAN contributes | unit | `.venv/bin/pytest tests/test_steering_confidence.py::TestWanAwarenessLogging -x` | Wave 0 |
| OBSV-03b | Recover decision log includes wan_zone context | unit | `.venv/bin/pytest tests/test_steering_confidence.py::TestWanAwarenessLogging -x` | Wave 0 |
| OBSV-03c | No WAN context logged when WAN does not contribute | unit | `.venv/bin/pytest tests/test_steering_confidence.py::TestWanAwarenessLogging -x` | Wave 0 |

### Sampling Rate
- **Per task commit:** `.venv/bin/pytest tests/test_steering_health.py tests/test_steering_metrics_recording.py tests/test_steering_confidence.py -x -v`
- **Per wave merge:** `.venv/bin/pytest tests/ -v`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_steering_health.py::TestWanAwarenessHealth` -- new test class for OBSV-01
- [ ] `tests/test_steering_metrics_recording.py::TestWanAwarenessMetrics` -- new test class for OBSV-02
- [ ] `tests/test_steering_confidence.py::TestWanAwarenessLogging` -- new test class for OBSV-03

No framework install needed. All fixtures and patterns exist in conftest.py and existing test files.

## Sources

### Primary (HIGH confidence)
- `src/wanctl/steering/health.py` -- Full health endpoint implementation reviewed (291 lines)
- `src/wanctl/steering/daemon.py` -- Full daemon with run_cycle, BaselineLoader, WAN zone flow reviewed (~1700 lines)
- `src/wanctl/steering/steering_confidence.py` -- Confidence scoring, TimerState, contributors reviewed (668 lines)
- `src/wanctl/metrics.py` -- Prometheus exporter and metric definitions reviewed (478 lines)
- `src/wanctl/storage/writer.py` -- MetricsWriter singleton, batch write pattern reviewed (257 lines)
- `src/wanctl/storage/schema.py` -- SQLite schema and STORED_METRICS dict reviewed (58 lines)
- `src/wanctl/steering_logger.py` -- Structured logging patterns reviewed (266 lines)
- `src/wanctl/health_check.py` -- Autorate health endpoint (parallel pattern) reviewed (518 lines)
- `tests/test_steering_health.py` -- Existing health endpoint tests reviewed
- `tests/test_steering_metrics_recording.py` -- Existing metrics tests reviewed
- `tests/conftest.py` -- Shared fixtures reviewed (mock_steering_config)

### Secondary (MEDIUM confidence)
- `.planning/REQUIREMENTS.md` -- OBSV-01, OBSV-02, OBSV-03 specifications
- `.planning/phases/60-configuration-safety-wiring/60-CONTEXT.md` -- Phase 60 decisions on disabled-mode and grace period health display

### Tertiary (LOW confidence)
None -- all findings verified against source code.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- no new dependencies, extending existing systems
- Architecture: HIGH -- all patterns verified in source code, clear extension points
- Pitfalls: HIGH -- identified from actual code review (thread safety, timer semantics, logging frequency)

**Research date:** 2026-03-09
**Valid until:** 2026-04-09 (stable internal architecture, no external dependencies)
