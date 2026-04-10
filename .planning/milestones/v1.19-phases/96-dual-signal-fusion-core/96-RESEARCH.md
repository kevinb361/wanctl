# Phase 96: Dual-Signal Fusion Core - Research

**Researched:** 2026-03-18
**Domain:** Signal fusion (weighted average of ICMP and IRTT RTT for congestion control)
**Confidence:** HIGH

## Summary

Phase 96 inserts a weighted-average fusion step between `signal_processor.process()` (line 2110) and `update_ewma()` in `WANController.run_cycle()`. The fusion combines icmplib ICMP filtered_rtt (20Hz) with IRTT UDP rtt_mean_ms (0.1Hz cached) using configurable weights (default ICMP 0.7 / IRTT 0.3). When IRTT is unavailable, stale, or disabled, fusion is a pure pass-through with zero overhead.

This is an internal-only phase: the fusion computation and config loading. Phase 97 handles the disabled-by-default gate, SIGUSR1 toggle, and health endpoint visibility. The insertion point is precisely identified at line 2110 of `autorate_continuous.py`, replacing `self.update_ewma(signal_result.filtered_rtt)` with `self.update_ewma(fused_rtt)`.

All patterns needed (config loading, staleness gate, warn+default validation, test fixtures, MagicMock conventions) are thoroughly established in the codebase from v1.18 infrastructure. No new libraries, no architectural changes, no external dependencies.

**Primary recommendation:** Add `_load_fusion_config()` and a `_compute_fused_rtt()` method to WANController. Single YAML knob `fusion.icmp_weight`. Keep it minimal -- this is a one-line formula guarded by staleness checks that already exist.

<user_constraints>

## User Constraints (from CONTEXT.md)

### Locked Decisions
- Default **ICMP 0.7 / IRTT 0.3** -- ICMP remains dominant (20Hz vs 0.1Hz)
- Uses **raw IRTT rtt_mean_ms** directly -- no additional filtering
- **Reuse latest IRTT value** between measurements -- cached value used for all ~200 cycles until next burst; staleness gate handles truly old values
- Stale defined as **IRTT age > 3x cadence** (existing gate, default 30s)
- **Instant fallback** to ICMP-only when IRTT goes stale -- no gradual weight shift
- When IRTT is **completely disabled** (_irtt_thread is None), fusion is a **pure pass-through** -- zero overhead
- **DEBUG logging** of fused_rtt alongside icmp_rtt and irtt_rtt
- **Single knob**: `fusion.icmp_weight: 0.7` in YAML -- IRTT weight derived as `1.0 - icmp_weight`
- **Invalid values** (outside 0.0-1.0): WARNING log + clamp to default 0.7
- Fusion happens **between** signal_processor.process() and update_ewma()
- `fused_rtt = icmp_weight * filtered_rtt + irtt_weight * irtt_rtt` when IRTT is fresh
- `fused_rtt = filtered_rtt` (pass-through) when IRTT stale/unavailable/disabled
- `update_ewma(fused_rtt)` replaces `update_ewma(filtered_rtt)`

### Claude's Discretion
- Internal class/module structure (inline in run_cycle vs separate FusionEngine class)
- Whether to compute fused_rtt in a method or inline
- How to structure the fusion YAML section (top-level `fusion:` vs nested under existing section)
- Test fixture design for mocking IRTT results at different staleness levels

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope

</user_constraints>

<phase_requirements>

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| FUSE-01 | IRTT and icmplib RTT signals are combined via configurable weighted average for congestion control input | Fusion formula, insertion point at line 2110, `_compute_fused_rtt()` method pattern |
| FUSE-03 | Fusion weights are YAML-configurable with warn+default validation | `_load_fusion_config()` following established warn+default pattern from `_load_irtt_config`, `_load_owd_asymmetry_config` |
| FUSE-04 | When IRTT is unavailable or stale, fusion falls back to icmplib-only with zero behavioral change | Three-tier fallback: _irtt_thread is None, get_latest() returns None, age > 3x cadence -- all return filtered_rtt unchanged |

</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python stdlib only | 3.12 | Weighted average computation | No dependencies needed for `a*x + b*y` |

### Supporting
No additional libraries. Fusion is pure arithmetic on values already available in `run_cycle()`.

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Inline formula | Kalman filter | Overkill -- two signals with known cadences, simple weighted average is appropriate |
| Static weights | Adaptive weights | Deferred to AFUS-01 (v1.20+) per REQUIREMENTS.md |

## Architecture Patterns

### Recommended Structure

No new files. All changes in existing files:

```
src/wanctl/
├── autorate_continuous.py    # Config._load_fusion_config() + WANController._compute_fused_rtt() + run_cycle() edit
tests/
├── test_fusion_config.py     # NEW: Config validation tests (follows test_irtt_config.py pattern)
├── test_fusion_core.py       # NEW: Fusion computation + fallback tests
├── conftest.py               # Add fusion_config to mock_autorate_config
```

### Pattern 1: Config Loading (from existing codebase)
**What:** `_load_fusion_config()` method on Config class
**When to use:** Loading the `fusion:` YAML section
**Example:**
```python
# Source: autorate_continuous.py _load_owd_asymmetry_config pattern (line 874)
def _load_fusion_config(self) -> None:
    """Load fusion configuration. Validates fusion: YAML section.
    Invalid config warns and falls back to defaults."""
    logger = logging.getLogger(__name__)
    fusion = self.data.get("fusion", {})

    if not isinstance(fusion, dict):
        logger.warning(
            f"fusion config must be dict, got {type(fusion).__name__}; using defaults"
        )
        fusion = {}

    icmp_weight = fusion.get("icmp_weight", 0.7)
    if (
        not isinstance(icmp_weight, (int, float))
        or isinstance(icmp_weight, bool)
        or icmp_weight < 0.0
        or icmp_weight > 1.0
    ):
        logger.warning(
            f"fusion.icmp_weight must be number 0.0-1.0, got {icmp_weight!r}; "
            "defaulting to 0.7"
        )
        icmp_weight = 0.7

    self.fusion_config = {
        "icmp_weight": float(icmp_weight),
    }
    logger.info(
        f"Fusion: icmp_weight={icmp_weight}, irtt_weight={1.0 - icmp_weight}"
    )
```

### Pattern 2: Fusion Computation Method
**What:** `_compute_fused_rtt()` method on WANController
**When to use:** Computing the fused RTT value between signal_processor.process() and update_ewma()
**Example:**
```python
# Discretion recommendation: method, not inline -- testable in isolation
def _compute_fused_rtt(self, filtered_rtt: float) -> float:
    """Compute fused RTT from ICMP filtered_rtt and cached IRTT rtt_mean_ms.

    Returns filtered_rtt unchanged (pass-through) when:
    - IRTT thread is not running (_irtt_thread is None)
    - No IRTT result available (get_latest() returns None)
    - IRTT result is stale (age > 3x cadence)

    Returns weighted average when IRTT is fresh.
    """
    if self._irtt_thread is None:
        return filtered_rtt

    irtt_result = self._irtt_thread.get_latest()
    if irtt_result is None:
        return filtered_rtt

    age = time.monotonic() - irtt_result.timestamp
    cadence = self._irtt_thread._cadence_sec
    if age > cadence * 3:
        return filtered_rtt

    irtt_rtt = irtt_result.rtt_mean_ms
    if irtt_rtt <= 0:
        return filtered_rtt

    fused = self._fusion_icmp_weight * filtered_rtt + (1.0 - self._fusion_icmp_weight) * irtt_rtt
    self.logger.debug(
        f"{self.wan_name}: fused_rtt={fused:.1f}ms "
        f"(icmp={filtered_rtt:.1f}ms, irtt={irtt_rtt:.1f}ms, "
        f"icmp_w={self._fusion_icmp_weight})"
    )
    return fused
```

### Pattern 3: Integration Point Edit
**What:** Single line change at line 2110
**Current code:**
```python
self.update_ewma(signal_result.filtered_rtt)
```
**New code:**
```python
fused_rtt = self._compute_fused_rtt(signal_result.filtered_rtt)
self.update_ewma(fused_rtt)
```

### Anti-Patterns to Avoid
- **Double-reading IRTT in run_cycle**: The existing IRTT block (line 2152-2188) reads IRTT for protocol correlation, asymmetry, and loss alerts. Fusion should read IRTT **before** that block (it needs the value earlier, at line 2110). Do NOT share the irtt_result variable -- compute fusion independently to keep the insertion point clean.
- **Modifying signal_processor.process()**: Fusion is AFTER signal processing, not inside it. SignalProcessor must remain IRTT-unaware.
- **Modifying update_ewma()**: This is architectural spine. Fusion changes the INPUT to update_ewma, never its internals.
- **Creating a separate fusion module/file**: Overkill for a single method + config loader. Inline in autorate_continuous.py matches the project pattern for all similar features (protocol correlation, asymmetry analysis, loss alerts).

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| IRTT staleness check | Custom age calculation | Reuse existing `age > cadence * 3` pattern (line 2165) | Already proven, same threshold for all IRTT consumers |
| Config validation | Custom validation framework | Follow `_load_irtt_config` warn+default pattern | 8 existing config loaders use this exact pattern |
| Thread-safe IRTT read | Lock-based reader | `_irtt_thread.get_latest()` lock-free cache | GIL-protected pointer swap, established in v1.18 |

## Common Pitfalls

### Pitfall 1: MagicMock Truthy Trap for fusion_config
**What goes wrong:** Mock config returns truthy MagicMock for `fusion_config` attribute, causing unexpected behavior in tests.
**Why it happens:** MagicMock auto-creates attributes that are truthy. If test code checks `self.config.fusion_config` without explicit setup, it gets a MagicMock dict-like object.
**How to avoid:** Add `config.fusion_config = {"icmp_weight": 0.7}` to `mock_autorate_config` fixture in conftest.py. Initialize `self._fusion_icmp_weight` from config dict in `__init__`, not from config attribute directly.
**Warning signs:** Tests pass individually but fail in batch, or fusion behaves unexpectedly in test.

### Pitfall 2: Double IRTT Read Creating Inconsistency
**What goes wrong:** Fusion reads `get_latest()` at line ~2110, then the existing IRTT block reads it again at line 2153. Between the two reads, the IRTT thread could update the cached result (GIL pointer swap).
**Why it happens:** Two independent reads of a lock-free cache in the same cycle.
**How to avoid:** Accept the race -- at 10s cadence vs 50ms cycle, the probability is ~0.5% and the difference would be one measurement burst. The two consumers (fusion vs correlation/asymmetry) have independent purposes. Do NOT try to share a single read variable -- it creates coupling between the insertion point and the observation block.
**Warning signs:** None in practice. This is a theoretical concern that does not warrant a fix.

### Pitfall 3: Fusion With Zero/Negative IRTT RTT
**What goes wrong:** `irtt_result.rtt_mean_ms` could be 0.0 if IRTT returned all losses (0 packets received). Weighted average with 0.0 would pull fused_rtt toward zero, causing false GREEN.
**Why it happens:** IRTT reports rtt_mean_ms=0.0 when all packets are lost.
**How to avoid:** Guard with `if irtt_rtt <= 0: return filtered_rtt` before applying the fusion formula. This is consistent with the existing guard at line 2165 (`irtt_result.rtt_mean_ms > 0`).
**Warning signs:** Sudden baseline drift or unexpected GREEN zone during packet loss events.

### Pitfall 4: Config Not Added to _load_specific_fields Chain
**What goes wrong:** `_load_fusion_config()` is written but never called, so `fusion_config` attribute is never set on Config.
**Why it happens:** Forgetting to add the call in `_load_specific_fields()` (line 905).
**How to avoid:** Add `self._load_fusion_config()` to `_load_specific_fields()` alongside the other optional config loaders (signal_processing, irtt, reflector_quality, owd_asymmetry). Place it after `_load_irtt_config()` since fusion depends on IRTT being configured.
**Warning signs:** `AttributeError: 'Config' object has no attribute 'fusion_config'` at WANController instantiation.

### Pitfall 5: Forgetting conftest.py mock_autorate_config Update
**What goes wrong:** All existing tests that construct WANController break because `__init__` tries to access `config.fusion_config` which doesn't exist on the mock.
**Why it happens:** WANController.__init__ reads `config.fusion_config` but the shared mock fixture doesn't have it.
**How to avoid:** Add `config.fusion_config = {"icmp_weight": 0.7}` to `mock_autorate_config` in conftest.py. This is the FIRST thing to do before any other code changes.
**Warning signs:** Hundreds of test failures across unrelated test files.

## Code Examples

### Fusion Config in YAML
```yaml
# /etc/wanctl/autorate-spectrum.yaml
fusion:
  icmp_weight: 0.7   # IRTT weight derived as 1.0 - 0.7 = 0.3
```

### WANController.__init__ Additions
```python
# After signal processor setup (line ~1448), before IRTT thread setup
# Source: follows _irtt_correlation pattern (line 1459)
self._fusion_icmp_weight: float = config.fusion_config["icmp_weight"]
```

### run_cycle Integration (line 2110 replacement)
```python
# Source: autorate_continuous.py line 2110
# Before:
#   self.update_ewma(signal_result.filtered_rtt)
# After:
fused_rtt = self._compute_fused_rtt(signal_result.filtered_rtt)
self.update_ewma(fused_rtt)
```

### Test Pattern: Mock IRTT at Various Staleness
```python
# Source: test_irtt_loss_alerts.py _make_irtt helper pattern
def _make_irtt_result(rtt_ms: float = 20.0, age_offset: float = 0.0) -> IRTTResult:
    """Create an IRTTResult with controllable RTT and timestamp."""
    return IRTTResult(
        rtt_mean_ms=rtt_ms,
        rtt_median_ms=rtt_ms - 0.5,
        ipdv_mean_ms=1.0,
        send_loss=0.0,
        receive_loss=0.0,
        packets_sent=100,
        packets_received=100,
        server="104.200.21.31",
        port=2112,
        timestamp=time.monotonic() - age_offset,
        success=True,
    )

# Fresh IRTT (age=0):
irtt_thread.get_latest.return_value = _make_irtt_result(rtt_ms=25.0)

# Stale IRTT (age=35s, cadence=10s, threshold=30s):
irtt_thread.get_latest.return_value = _make_irtt_result(rtt_ms=25.0, age_offset=35.0)

# No IRTT:
irtt_thread.get_latest.return_value = None
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| ICMP-only RTT input to EWMA | Fused ICMP+IRTT RTT input | Phase 96 (this phase) | More robust congestion signal; stabilizing cross-check from UDP |
| N/A (new feature) | Single-knob weight config | Phase 96 | Operator control via one YAML value |

**Unchanged:**
- update_ewma() internals -- unchanged, just receives different input
- signal_processor.process() -- unchanged, fusion is downstream
- IRTT observation mode -- unchanged, fusion is a separate consumer
- Staleness threshold (3x cadence) -- reused, not modified

## Open Questions

1. **Ordering of _compute_fused_rtt vs existing IRTT block in run_cycle**
   - What we know: Fusion needs IRTT data at line 2110; existing IRTT block is at line 2152.
   - What's unclear: Whether to move the existing IRTT read earlier (consolidate) or keep two independent reads.
   - Recommendation: Keep two independent reads. Fusion is in the state management subsystem at line 2110; the existing IRTT block handles observation/correlation/alerts and has its own staleness guards. Coupling them would create a fragile dependency.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (via .venv/bin/pytest) |
| Config file | pyproject.toml [tool.pytest.ini_options] |
| Quick run command | `.venv/bin/pytest tests/test_fusion_config.py tests/test_fusion_core.py -x -v` |
| Full suite command | `.venv/bin/pytest tests/ -v` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| FUSE-01 | Weighted average computed when IRTT fresh | unit | `.venv/bin/pytest tests/test_fusion_core.py::TestFusionComputation -x` | No -- Wave 0 |
| FUSE-03 | fusion.icmp_weight validated with warn+default | unit | `.venv/bin/pytest tests/test_fusion_config.py -x` | No -- Wave 0 |
| FUSE-04 | Fallback to ICMP-only when IRTT unavailable/stale/disabled | unit | `.venv/bin/pytest tests/test_fusion_core.py::TestFusionFallback -x` | No -- Wave 0 |

### Sampling Rate
- **Per task commit:** `.venv/bin/pytest tests/test_fusion_config.py tests/test_fusion_core.py -x -v`
- **Per wave merge:** `.venv/bin/pytest tests/ -v`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_fusion_config.py` -- covers FUSE-03 (config validation)
- [ ] `tests/test_fusion_core.py` -- covers FUSE-01, FUSE-04 (computation + fallback)
- [ ] `tests/conftest.py` update -- add `fusion_config` to `mock_autorate_config` fixture (CRITICAL: must happen first to avoid breaking 3400+ tests)

## Sources

### Primary (HIGH confidence)
- `src/wanctl/autorate_continuous.py` -- Config._load_irtt_config (line 713), _load_owd_asymmetry_config (line 874), _load_specific_fields (line 905), WANController.__init__ (line 1258), run_cycle integration point (line 2110), IRTT observation block (line 2152)
- `src/wanctl/irtt_thread.py` -- IRTTThread.get_latest() lock-free cache API
- `src/wanctl/irtt_measurement.py` -- IRTTResult frozen dataclass with rtt_mean_ms field
- `src/wanctl/signal_processing.py` -- SignalProcessor.process() returning SignalResult with filtered_rtt
- `tests/conftest.py` -- mock_autorate_config fixture (line 48), established mock patterns
- `tests/test_irtt_config.py` -- Config validation test pattern (26 tests, same structure needed for fusion config)
- `tests/test_irtt_loss_alerts.py` -- Mock controller pattern for testing features that consume IRTT data in run_cycle

### Secondary (MEDIUM confidence)
- None needed -- all patterns are established in the codebase

### Tertiary (LOW confidence)
- None

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- no libraries needed, pure arithmetic
- Architecture: HIGH -- insertion point precisely identified, all patterns established in codebase
- Pitfalls: HIGH -- all pitfalls derived from direct codebase analysis of similar features (v1.18)

**Research date:** 2026-03-18
**Valid until:** 2026-04-18 (stable -- no external dependencies, internal codebase patterns)
