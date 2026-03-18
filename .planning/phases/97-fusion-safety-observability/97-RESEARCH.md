# Phase 97: Fusion Safety & Observability - Research

**Researched:** 2026-03-18
**Domain:** Feature gating, SIGUSR1 config reload, health endpoint extension
**Confidence:** HIGH

## Summary

Phase 97 gates the Phase 96 fusion engine behind a disabled-by-default `fusion.enabled` flag, adds SIGUSR1 zero-downtime toggle to the autorate daemon, and exposes fusion state in the health endpoint. All three patterns are well-established in the codebase -- the steering daemon already has SIGUSR1 reload (dry_run, wan_state, webhook_url), the health endpoint already has always-present sections with availability flags (IRTT, signal_quality, reflector_quality), and the config system already has `_load_fusion_config()` with warn+default validation.

This phase touches 3 files (autorate_continuous.py, health_check.py, and the Config class within autorate_continuous.py) plus test files. No new dependencies. No new libraries. The entire implementation follows template patterns from v1.13 (SIGUSR1 graduation) and v1.18 (health endpoint sections).

**Primary recommendation:** Follow the steering daemon SIGUSR1 pattern exactly (lines 2089-2097) and the IRTT health section pattern exactly (lines 203-253). The only novelty is that this is the first SIGUSR1 reload in the autorate daemon.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Config key: `fusion.enabled: false` (default) -- matches wan_state.enabled, alerting.enabled, irtt.enabled patterns
- Disabled means completely skipped -- no observation mode. Pass-through in `_compute_fused_rtt`: early return of `filtered_rtt` when `self._fusion_enabled` is False
- `_fusion_enabled` read once in `__init__` from `config.fusion_config["enabled"]`, updated by SIGUSR1 reload
- No grace period on enable -- fusion is a weighted average, not a threshold-based feature
- First SIGUSR1 reload in autorate daemon -- add `is_reload_requested()` check at top of while loop, before `run_cycle()`
- Loop iterates over all `wan_controllers` and calls `_reload_fusion_config()` on each WANController
- `_reload_fusion_config()` reloads both `enabled` and `icmp_weight` -- operators can tune weights in production without restart
- Log format: `[FUSION] Config reload: enabled=false->true, icmp_weight=0.7 (unchanged)`
- Scope: fusion reload only -- do not add webhook_url or other reloads to autorate in this phase
- New always-present `fusion` section in health response (peer to signal_quality, irtt, reflector_quality)
- When enabled and active (IRTT contributing): show enabled, icmp_weight, irtt_weight, active_source="fused", fused_rtt_ms, icmp_rtt_ms, irtt_rtt_ms
- When enabled but IRTT unavailable (fallback): show configured weights, active_source="icmp_only", fused_rtt_ms=null, irtt_rtt_ms=null
- When disabled: minimal `{"enabled": false, "reason": "disabled"}`
- No SQLite persistence for fusion state -- input signals already persisted, fused_rtt is derivable
- No Discord alert on SIGUSR1 toggle -- INFO logging is sufficient

### Claude's Discretion
- Whether `_reload_fusion_config` reads YAML via existing `_read_yaml()` helper or opens the file directly
- Exact positioning of fusion section in health response dict relative to other sections
- Test structure and fixture design for mocking fusion enabled/disabled states
- How to expose last fused_rtt from WANController to health endpoint (new attribute vs method)

### Deferred Ideas (OUT OF SCOPE)
- Autorate webhook_url SIGUSR1 reload (parity with steering daemon) -- future phase
- Discord alert on fusion toggle -- not needed for single-operator system
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| FUSE-02 | Fusion ships disabled by default with SIGUSR1 toggle for zero-downtime enable/disable | Config `enabled` field in `_load_fusion_config()`, `_fusion_enabled` instance var, SIGUSR1 check in autorate main loop, `_reload_fusion_config()` method on WANController |
| FUSE-05 | Fusion state (enabled, weights, active signal sources) is visible in health endpoint | New `fusion` section in `health_check.py` following IRTT/reflector_quality always-present pattern |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python | 3.12 | Runtime | Production standard |
| pytest | 9.0.2 | Test framework | Already configured in pyproject.toml |
| PyYAML | (existing) | YAML config reload | Used by steering daemon reload pattern |

### Supporting
No new libraries needed. This phase uses only existing infrastructure.

### Alternatives Considered
None. All patterns are locked by CONTEXT.md decisions and established codebase patterns.

## Architecture Patterns

### Recommended Change Structure
```
src/wanctl/autorate_continuous.py   # Config._load_fusion_config (add enabled field)
                                     # WANController.__init__ (add _fusion_enabled)
                                     # WANController._compute_fused_rtt (add enabled guard)
                                     # WANController._reload_fusion_config (new method)
                                     # daemon main while loop (add SIGUSR1 check)
src/wanctl/health_check.py          # Add fusion section after reflector_quality
tests/test_fusion_config.py          # Extend with enabled field tests
tests/test_fusion_core.py            # Extend with enabled guard tests
tests/test_fusion_reload.py          # NEW: SIGUSR1 reload tests
tests/test_health_check.py           # Extend with fusion section tests
```

### Pattern 1: SIGUSR1 Reload in Autorate Main Loop
**What:** Add `is_reload_requested()` check at top of while loop, iterate wan_controllers, call `_reload_fusion_config()`, then `reset_reload_state()`.
**When to use:** This is the single insertion point in the autorate daemon.
**Template (steering daemon lines 2089-2097):**
```python
# In autorate main loop, after update_health_status(), before watchdog check
if is_reload_requested():
    for wan_info in controller.wan_controllers:
        wan_info["logger"].info(
            "SIGUSR1 received, reloading fusion config"
        )
        wan_info["controller"]._reload_fusion_config()
    reset_reload_state()
```
**Key differences from steering daemon:**
- Steering daemon reloads 3 things (dry_run, wan_state, webhook_url) -- autorate reloads only fusion
- Steering daemon calls methods on `daemon` object -- autorate iterates `controller.wan_controllers`
- Each WANController has its own `_reload_fusion_config()` method (per-WAN, not per-daemon)

### Pattern 2: _reload_fusion_config() Method
**What:** Re-read fusion section from YAML, validate, update instance vars, log transitions.
**Template (steering daemon._reload_wan_state_config lines 1121-1165):**
```python
def _reload_fusion_config(self) -> None:
    """Re-read fusion config from YAML (triggered by SIGUSR1)."""
    try:
        import yaml
        with open(self.config.config_file_path) as f:
            fresh_data = yaml.safe_load(f)
    except Exception as e:
        self.logger.error(f"[FUSION] Config reload failed: {e}")
        return

    fusion = fresh_data.get("fusion", {}) if fresh_data else {}
    if not isinstance(fusion, dict):
        fusion = {}

    # Parse enabled (default False)
    new_enabled = bool(fusion.get("enabled", False))
    old_enabled = self._fusion_enabled

    # Parse icmp_weight with validation (reuse _load_fusion_config logic)
    new_weight = fusion.get("icmp_weight", 0.7)
    if not isinstance(new_weight, (int, float)) or isinstance(new_weight, bool) \
       or new_weight < 0.0 or new_weight > 1.0:
        new_weight = 0.7
    new_weight = float(new_weight)
    old_weight = self._fusion_icmp_weight

    # Log transitions
    enabled_str = f"enabled={old_enabled}->{new_enabled}" if old_enabled != new_enabled else f"enabled={old_enabled}"
    weight_str = f"icmp_weight={old_weight}->{new_weight}" if old_weight != new_weight else f"icmp_weight={old_weight} (unchanged)"
    self.logger.warning(f"[FUSION] Config reload: {enabled_str}, {weight_str}")

    self._fusion_enabled = new_enabled
    self._fusion_icmp_weight = new_weight
```
**Key details:**
- Uses `self.config.config_file_path` (available on all Config objects via BaseConfig, line 289)
- Validates icmp_weight with same range/type checks as `_load_fusion_config()` but inline (not calling the Config method)
- Logs at WARNING level for operator visibility (same as steering daemon reload methods)
- Updates both `_fusion_enabled` and `_fusion_icmp_weight` atomically within same method call

### Pattern 3: Health Endpoint Fusion Section
**What:** Always-present `fusion` section in per-WAN health response, following IRTT pattern.
**Template (health_check.py lines 203-253):**
```python
# After reflector_quality section
fusion_section: dict[str, Any] = {}
if not wan_controller._fusion_enabled:
    fusion_section = {"enabled": False, "reason": "disabled"}
else:
    # Enabled -- check what's active
    irtt_thread = wan_controller._irtt_thread
    irtt_rtt = None
    fused_rtt = None
    active_source = "icmp_only"

    if irtt_thread is not None:
        irtt_result = irtt_thread.get_latest()
        if irtt_result is not None:
            age = time.monotonic() - irtt_result.timestamp
            cadence = irtt_thread._cadence_sec
            if age <= cadence * 3 and irtt_result.rtt_mean_ms > 0:
                irtt_rtt = round(irtt_result.rtt_mean_ms, 2)
                active_source = "fused"

    icmp_rtt = round(wan_controller._last_icmp_rtt, 2) if wan_controller._last_icmp_rtt is not None else None

    if active_source == "fused" and icmp_rtt is not None and irtt_rtt is not None:
        fused_rtt = round(
            wan_controller._fusion_icmp_weight * icmp_rtt
            + (1.0 - wan_controller._fusion_icmp_weight) * irtt_rtt,
            2,
        )

    fusion_section = {
        "enabled": True,
        "icmp_weight": wan_controller._fusion_icmp_weight,
        "irtt_weight": round(1.0 - wan_controller._fusion_icmp_weight, 2),
        "active_source": active_source,
        "fused_rtt_ms": fused_rtt,
        "icmp_rtt_ms": icmp_rtt,
        "irtt_rtt_ms": irtt_rtt,
    }

wan_health["fusion"] = fusion_section
```

### Pattern 4: Enabled Guard in _compute_fused_rtt
**What:** Single-line early return at top of `_compute_fused_rtt` when disabled.
```python
def _compute_fused_rtt(self, filtered_rtt: float) -> float:
    if not self._fusion_enabled:
        return filtered_rtt
    # ... existing computation unchanged ...
```

### Anti-Patterns to Avoid
- **Modifying fusion computation logic:** Phase 96 locked the weighted average. Phase 97 only gates it.
- **Adding grace period:** CONTEXT.md explicitly says no grace period -- fusion is a weighted average, not a threshold-based feature.
- **Observation mode:** CONTEXT.md says disabled = completely skipped, no compute-and-log.
- **Adding multiple reload types to autorate:** Scope is fusion-only. No webhook_url or other reloads.
- **SQLite persistence for fusion state:** Explicitly excluded -- input signals already persisted.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Signal handling | Custom signal infrastructure | `signal_utils.is_reload_requested()` / `reset_reload_state()` | Thread-safe, battle-tested, shared between daemons |
| Config validation | New validation framework | Inline checks matching `_load_fusion_config()` pattern | Consistency with existing warn+default pattern |
| YAML reload | Custom file reader | `yaml.safe_load()` + `open(self.config.config_file_path)` | Exact pattern from steering daemon |

## Common Pitfalls

### Pitfall 1: MagicMock Truthy Trap on _fusion_enabled
**What goes wrong:** MagicMock attributes are truthy by default. `if not wan_controller._fusion_enabled:` always returns False with MagicMock.
**Why it happens:** MagicMock auto-creates attributes that evaluate to True.
**How to avoid:** Set `wan._fusion_enabled = False` explicitly on mock WANControllers in test fixtures.
**Warning signs:** Health endpoint tests showing fusion as "enabled" when no explicit _fusion_enabled is set.

### Pitfall 2: Conftest mock_autorate_config Missing enabled Key
**What goes wrong:** WANController.__init__ reads `config.fusion_config["enabled"]` -- if conftest fixture doesn't have it, KeyError.
**Why it happens:** Phase 96 set `fusion_config = {"icmp_weight": 0.7}` (no `enabled` key).
**How to avoid:** Update conftest `mock_autorate_config` to include `config.fusion_config = {"icmp_weight": 0.7, "enabled": False}`.
**Warning signs:** KeyError in WANController.__init__ during existing test runs.

### Pitfall 3: SIGUSR1 Check Position in Autorate Loop
**What goes wrong:** If SIGUSR1 check is placed inside the cycle success/failure block, it may not execute every iteration.
**Why it happens:** The autorate main loop has complex branching after `run_cycle()`.
**How to avoid:** Place SIGUSR1 check at end of the while loop body, after watchdog but before sleep -- same relative position as steering daemon.
**Warning signs:** Slow SIGUSR1 response times, missed reloads.

### Pitfall 4: Health Endpoint Accessing _last_icmp_rtt That Doesn't Exist
**What goes wrong:** The health endpoint needs the last ICMP filtered_rtt to show in the fusion section, but WANController may not store it as a standalone attribute.
**Why it happens:** `_compute_fused_rtt` receives `filtered_rtt` as parameter but doesn't store it.
**How to avoid:** Either store the last filtered_rtt as a WANController attribute (e.g., `_last_filtered_rtt`), or recompute from `_last_signal_result.filtered_rtt`, or use `load_rtt` which is the EWMA-smoothed version. `_last_signal_result.filtered_rtt` is the most accurate representation of what went into fusion.
**Warning signs:** AttributeError or None values in health endpoint fusion section.

### Pitfall 5: Config._load_fusion_config Not Persisting enabled Key
**What goes wrong:** The existing `_load_fusion_config()` stores `fusion_config = {"icmp_weight": ...}` but not `enabled`.
**Why it happens:** Phase 96 didn't add the `enabled` field.
**How to avoid:** Add `enabled` to the `fusion_config` dict in `_load_fusion_config()` and to WANController.__init__ reading `config.fusion_config["enabled"]`.
**Warning signs:** KeyError on `config.fusion_config["enabled"]`.

### Pitfall 6: YAML Reload Reading From Wrong Path in Tests
**What goes wrong:** `_reload_fusion_config` opens `self.config.config_file_path` which points to a real file path.
**Why it happens:** Test mock configs have MagicMock for config_file_path.
**How to avoid:** In reload tests, use `tmp_path` to create real YAML files and set `controller.config.config_file_path` to that path. Pattern: write initial YAML, create controller, modify YAML, call `_reload_fusion_config()`, assert changes.
**Warning signs:** Tests opening MagicMock objects as file paths.

## Code Examples

### Exposing Last Fused RTT and ICMP RTT for Health Endpoint
The health endpoint needs to show the last fused RTT and component RTTs. Two approaches:

**Option A (recommended): Store last values as attributes in WANController**
```python
# In WANController.__init__:
self._last_fused_rtt: float | None = None
self._last_icmp_filtered_rtt: float | None = None

# In _compute_fused_rtt, before return:
# (when fusion computes a value)
self._last_fused_rtt = fused
self._last_icmp_filtered_rtt = filtered_rtt
return fused

# (when fallback to filtered_rtt)
self._last_fused_rtt = None  # No fusion occurred
self._last_icmp_filtered_rtt = filtered_rtt
return filtered_rtt
```

**Option B: Read from _last_signal_result in health endpoint**
```python
# In health_check.py:
icmp_rtt = None
if wan_controller._last_signal_result is not None:
    icmp_rtt = round(wan_controller._last_signal_result.filtered_rtt, 2)
```

Option A is cleaner for the health endpoint (direct attribute access) and tracks actual fusion state. Option B avoids adding attributes but couples health_check to SignalResult internals.

### Full Config._load_fusion_config Update
```python
def _load_fusion_config(self) -> None:
    """Load fusion configuration. Validates fusion: YAML section."""
    logger = logging.getLogger(__name__)
    fusion = self.data.get("fusion", {})

    if not isinstance(fusion, dict):
        logger.warning(f"fusion config must be dict, got {type(fusion).__name__}; using defaults")
        fusion = {}

    # enabled (default: False for safe deployment)
    enabled = fusion.get("enabled", False)
    if not isinstance(enabled, bool):
        logger.warning(f"fusion.enabled must be bool, got {type(enabled).__name__}; defaulting to false")
        enabled = False

    # icmp_weight (existing validation, unchanged)
    icmp_weight = fusion.get("icmp_weight", 0.7)
    if (not isinstance(icmp_weight, (int, float)) or isinstance(icmp_weight, bool)
            or icmp_weight < 0.0 or icmp_weight > 1.0):
        logger.warning(f"fusion.icmp_weight must be number 0.0-1.0, got {icmp_weight!r}; defaulting to 0.7")
        icmp_weight = 0.7

    self.fusion_config = {
        "enabled": enabled,
        "icmp_weight": float(icmp_weight),
    }
    logger.info(f"Fusion: enabled={enabled}, icmp_weight={icmp_weight}, irtt_weight={1.0 - icmp_weight}")
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| No SIGUSR1 in autorate | SIGUSR1 in steering only (v1.13) | 2026-03-11 | Phase 97 extends to autorate |
| Fusion always active (Phase 96) | Fusion gated by enabled flag | Phase 97 (this phase) | Safe production rollout |

**Existing infrastructure this phase builds on:**
- `signal_utils.py`: `is_reload_requested()`, `reset_reload_state()`, `register_signal_handlers()` -- all already imported/called in autorate daemon
- `health_check.py`: Always-present section pattern with IRTT (lines 203-253) -- template for fusion section
- `Config._load_fusion_config()`: Already validates icmp_weight -- add `enabled` field to same method
- `WANController.__init__`: Already reads `config.fusion_config["icmp_weight"]` -- add `config.fusion_config["enabled"]`

## Open Questions

1. **How to expose ICMP filtered_rtt to health endpoint**
   - What we know: `_compute_fused_rtt` receives `filtered_rtt` as parameter, health_check.py accesses WANController attributes
   - What's unclear: Whether to store as a new attribute or read from `_last_signal_result.filtered_rtt`
   - Recommendation: Store as `_last_icmp_filtered_rtt` attribute (Option A) for clean health endpoint access. Alternatively, `_last_signal_result.filtered_rtt` works without a new attribute but couples health to SignalResult internals. Both are valid -- Claude's discretion per CONTEXT.md.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.0.2 |
| Config file | pyproject.toml [tool.pytest.ini_options] |
| Quick run command | `.venv/bin/pytest tests/test_fusion_config.py tests/test_fusion_core.py -x -v` |
| Full suite command | `.venv/bin/pytest tests/ -v` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| FUSE-02a | fusion.enabled defaults to False in config | unit | `.venv/bin/pytest tests/test_fusion_config.py -x -k enabled` | Wave 0 (extend existing) |
| FUSE-02b | _compute_fused_rtt returns filtered_rtt when disabled | unit | `.venv/bin/pytest tests/test_fusion_core.py -x -k disabled` | Wave 0 (extend existing) |
| FUSE-02c | SIGUSR1 toggles _fusion_enabled on WANController | unit | `.venv/bin/pytest tests/test_fusion_reload.py -x` | Wave 0 (new file) |
| FUSE-02d | SIGUSR1 reloads icmp_weight | unit | `.venv/bin/pytest tests/test_fusion_reload.py -x -k weight` | Wave 0 (new file) |
| FUSE-02e | Invalid reload values warn+default | unit | `.venv/bin/pytest tests/test_fusion_reload.py -x -k invalid` | Wave 0 (new file) |
| FUSE-05a | Health shows enabled=false when disabled | unit | `.venv/bin/pytest tests/test_health_check.py -x -k fusion_disabled` | Wave 0 (extend existing) |
| FUSE-05b | Health shows fused state when enabled+active | unit | `.venv/bin/pytest tests/test_health_check.py -x -k fusion_enabled` | Wave 0 (extend existing) |
| FUSE-05c | Health shows icmp_only when enabled but IRTT unavailable | unit | `.venv/bin/pytest tests/test_health_check.py -x -k fusion_icmp_only` | Wave 0 (extend existing) |

### Sampling Rate
- **Per task commit:** `.venv/bin/pytest tests/test_fusion_config.py tests/test_fusion_core.py tests/test_fusion_reload.py tests/test_health_check.py -x -v`
- **Per wave merge:** `.venv/bin/pytest tests/ -v`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_fusion_reload.py` -- NEW file covering FUSE-02 SIGUSR1 reload behavior
- [ ] Update `tests/conftest.py` `mock_autorate_config` -- add `enabled: False` to `fusion_config`
- [ ] Extend `tests/test_fusion_config.py` -- add `enabled` field config loading tests
- [ ] Extend `tests/test_fusion_core.py` -- add `_fusion_enabled=False` guard tests
- [ ] Extend `tests/test_health_check.py` -- add fusion section tests (disabled, enabled+active, enabled+fallback)

## Sources

### Primary (HIGH confidence)
- `src/wanctl/autorate_continuous.py` lines 905-933 -- `_load_fusion_config()` current implementation
- `src/wanctl/autorate_continuous.py` lines 1514-1521 -- `_fusion_icmp_weight` init
- `src/wanctl/autorate_continuous.py` lines 2078-2111 -- `_compute_fused_rtt()` current implementation
- `src/wanctl/autorate_continuous.py` lines 3322-3415 -- autorate daemon main loop
- `src/wanctl/steering/daemon.py` lines 2089-2097 -- steering SIGUSR1 check pattern
- `src/wanctl/steering/daemon.py` lines 1084-1165 -- `_reload_dry_run_config()`, `_reload_wan_state_config()` templates
- `src/wanctl/signal_utils.py` lines 49-166 -- `is_reload_requested()`, `reset_reload_state()`
- `src/wanctl/health_check.py` lines 191-274 -- IRTT, signal_quality, reflector_quality sections
- `src/wanctl/config_base.py` line 289 -- `config_file_path` attribute

### Secondary (MEDIUM confidence)
- `tests/test_fusion_config.py` -- existing test patterns for fusion config
- `tests/test_fusion_core.py` -- existing test patterns for fusion computation mocking
- `tests/test_health_check.py` lines 840-919 -- health endpoint test fixture patterns
- `tests/conftest.py` lines 47-131 -- `mock_autorate_config` shared fixture

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- no new libraries, all existing infrastructure
- Architecture: HIGH -- all three patterns (SIGUSR1, config gating, health section) have exact templates in codebase
- Pitfalls: HIGH -- known from v1.13 SIGUSR1 graduation, v1.18 health sections, and Phase 96 fusion work

**Research date:** 2026-03-18
**Valid until:** 2026-04-18 (stable -- no external dependencies, all patterns are internal)
