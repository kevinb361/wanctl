# Phase 95: IRTT Loss Alerts - Research

**Researched:** 2026-03-18
**Domain:** Alerting integration -- IRTT packet loss sustained detection via existing AlertEngine
**Confidence:** HIGH

## Summary

This phase adds Discord alerts when sustained IRTT packet loss is detected in either direction. All infrastructure exists: AlertEngine (v1.15) provides cooldown/persistence/webhook delivery, IRTTThread (v1.18) provides cached loss data, and autorate_continuous.py already reads `irtt_result.send_loss` / `irtt_result.receive_loss` every cycle. The implementation follows the exact same sustained-timer pattern used by `_check_congestion_alerts()` (monotonic timestamps, `_*_start` / `_*_fired` state variables, recovery gate).

The scope is narrow: add ~4 state variables to `WANController.__init__()`, one new `_check_irtt_loss_alerts()` method (~60 lines), call it from `run_cycle()` where IRTT results are already consumed, and add a "loss" -> "%" unit mapping to `DiscordFormatter._UNIT_MAP`. No new files, no new dependencies, no config schema changes (IRTT loss alerts use existing `alerting.rules` per-rule override pattern).

**Primary recommendation:** Follow the `_check_congestion_alerts` pattern exactly -- same timer structure, same fire/recovery gate, same test mock approach. One plan is sufficient.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Default loss threshold **5%** -- sustained loss above 5% triggers alert
- **Same threshold** for both upstream and downstream (not independent)
- Threshold is **YAML-configurable** per alert rule in `alerting.rules` section
- Follows existing per-rule override pattern (sustained_sec, cooldown_sec overrides)
- Uses **wall-clock seconds** (existing sustained_sec pattern from v1.15 congestion alerts)
- Default **60 seconds** -- approximately 6 consecutive lossy IRTT bursts at 10s cadence
- Configurable via sustained_sec per-rule override in alerting.rules
- Timer resets when loss drops below threshold
- **Separate alert types**: `irtt_loss_upstream` and `irtt_loss_downstream`
- Independent cooldown suppression via (type, WAN) key
- **Recovery alert**: `irtt_loss_recovered` when loss clears after sustained alert was sent
- Recovery includes outage duration, matches wan_recovered/steering_recovered pattern
- **Discord embed content**: loss %, direction, duration, WAN name
- Example: "IRTT upstream packet loss: 15.0% on spectrum (sustained 62s)"
- Severity: "warning" for loss alerts, "recovery" for recovery alerts

### Claude's Discretion
- Internal timer tracking implementation (monotonic timestamps like existing sustained timers)
- Whether to use one recovery type or direction-specific recovery types
- How to handle IRTT unavailable/stale during sustained loss tracking (likely reset timers)
- DiscordFormatter color choices for loss alerts

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| ALRT-01 | Sustained upstream packet loss triggers alert via existing AlertEngine with configurable threshold | Follows `_check_congestion_alerts` sustained timer pattern; `irtt_result.send_loss` already available in run_cycle |
| ALRT-02 | Sustained downstream packet loss triggers alert via existing AlertEngine with configurable threshold | Same pattern as ALRT-01 using `irtt_result.receive_loss`; independent timer state |
| ALRT-03 | IRTT loss alerts use per-event cooldown consistent with existing alert types | AlertEngine.fire() uses (alert_type, wan_name) cooldown key automatically; per-rule `cooldown_sec` override via `alerting.rules` |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| wanctl AlertEngine | v1.15 | Per-event cooldown, SQLite persistence, webhook dispatch | Already wired into WANController; proven API |
| wanctl IRTTThread | v1.18 | Background IRTT measurement with lock-free cache | Already instantiated; `get_latest()` provides `send_loss`/`receive_loss` |
| wanctl DiscordFormatter | v1.15 | Color-coded Discord embeds | Already configured; needs "loss" -> "%" in `_UNIT_MAP` |

### Supporting
No new libraries needed. Everything is internal.

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Wall-clock sustained timer | Burst-count-based detection | Wall-clock is consistent with v1.15 congestion alerts and is clock-monotonic; burst-count would require knowing IRTT cadence |

**Installation:**
No new dependencies.

## Architecture Patterns

### Recommended Project Structure
No new files. All changes go into existing files:
```
src/wanctl/
  autorate_continuous.py   # 4 state vars in __init__, new _check_irtt_loss_alerts(), call in run_cycle
  webhook_delivery.py      # "loss" -> "%" in _UNIT_MAP (1 line)
tests/
  test_irtt_loss_alerts.py # NEW: test file following test_congestion_alerts.py pattern
```

### Pattern 1: Sustained Timer with Recovery Gate
**What:** Monotonic timestamp records when condition first detected. After `sustained_sec` threshold, fire alert and set `_*_fired = True`. When condition clears AND `_*_fired` is True, fire recovery alert. Reset all state.
**When to use:** Any sustained-detection alert with recovery notification.
**Example:**
```python
# From _check_congestion_alerts (lines 2358-2404) -- EXACT pattern to follow
now = time.monotonic()

# Condition detected
if loss_above_threshold:
    if self._irtt_loss_up_start is None:
        self._irtt_loss_up_start = now  # Start timer
    elif not self._irtt_loss_up_fired:
        sustained_sec = self.alert_engine._rules.get(
            "irtt_loss_upstream", {}
        ).get("sustained_sec", self._sustained_sec)
        duration = now - self._irtt_loss_up_start
        if duration >= sustained_sec:
            fired = self.alert_engine.fire(
                "irtt_loss_upstream", "warning", self.wan_name,
                {"loss_pct": send_loss, "direction": "upstream", "duration_sec": round(duration, 1)},
            )
            if fired:
                self._irtt_loss_up_fired = True
else:
    # Condition cleared -- fire recovery if sustained had fired
    if self._irtt_loss_up_start is not None:
        if self._irtt_loss_up_fired:
            duration = now - self._irtt_loss_up_start
            self.alert_engine.fire(
                "irtt_loss_recovered", "recovery", self.wan_name,
                {"direction": "upstream", "duration_sec": round(duration, 1), "loss_pct": send_loss},
            )
        self._irtt_loss_up_start = None
        self._irtt_loss_up_fired = False
```

### Pattern 2: Per-Rule Override Config Access
**What:** Access per-rule config via `self.alert_engine._rules.get("rule_name", {}).get("key", default)`.
**When to use:** For `sustained_sec`, `cooldown_sec`, `loss_threshold_pct` overrides.
**Example:**
```python
# Loss threshold from per-rule config, default 5%
loss_threshold = self.alert_engine._rules.get(
    "irtt_loss_upstream", {}
).get("loss_threshold_pct", 5.0)
```

### Pattern 3: IRTT Staleness Guard
**What:** Skip IRTT loss checking when result is stale (age > 3x cadence). Reset sustained timers on stale-out to avoid alerting on stale data.
**When to use:** Whenever consuming IRTT data for decisions.
**Example:**
```python
# Already done in run_cycle (line 2151):
if age <= cadence * 3 and irtt_result.rtt_mean_ms > 0:
    # Fresh -- safe to use
```

### Anti-Patterns to Avoid
- **Do not create a separate AlertEngine instance.** Use `self.alert_engine` already wired into WANController.
- **Do not check loss on every 50ms cycle independently.** IRTT updates every ~10s; loss checking should only trigger on new IRTT results (use the existing `irtt_result is not None` gate in run_cycle).
- **Do not use `_last_irtt_write_ts` for dedup of alerts.** The sustained timer pattern handles this naturally -- it tracks continuous loss state, not individual measurements.
- **Do not modify `IRTTResult` or `IRTTThread`.** Loss data (`send_loss`, `receive_loss`) is already available.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Cooldown suppression | Custom cooldown tracking | AlertEngine.fire() with (type, wan) key | Already handles per-rule cooldown_sec overrides |
| Webhook delivery | HTTP POST code | WebhookDelivery.deliver() via delivery_callback | Non-blocking background thread with retry |
| SQLite persistence | Manual INSERT | AlertEngine._persist_alert() (internal) | Automatic on fire() |
| Recovery gate | Custom recovery tracking | `_*_fired` bool pattern | Proven pattern from congestion alerts |

## Common Pitfalls

### Pitfall 1: Alerting on stale IRTT data
**What goes wrong:** IRTT server goes down, cached result stays at 10% loss, sustained timer fires alert on stale data.
**Why it happens:** `IRTTThread.get_latest()` returns the last successful result even if hours old.
**How to avoid:** Only check loss when `irtt_result is not None` AND age is within freshness window (already gated in run_cycle). Reset sustained timers if IRTT goes stale.
**Warning signs:** Alert fires with loss data from hours ago.

### Pitfall 2: MagicMock truthy trap on `_irtt_thread`
**What goes wrong:** Tests using `MagicMock(spec=WANController)` have `_irtt_thread` as a MagicMock which is truthy, causing IRTT code paths to execute unexpectedly.
**Why it happens:** MagicMock attributes are truthy by default.
**How to avoid:** Set `controller._irtt_thread = None` explicitly on mock controllers (already documented in MEMORY.md).
**Warning signs:** Tests fail with attribute errors on MagicMock objects.

### Pitfall 3: Recovery alert fires without sustained alert
**What goes wrong:** If loss briefly exceeds threshold then clears, recovery fires even though sustained alert never fired.
**Why it happens:** Missing recovery gate (`_*_fired` check).
**How to avoid:** Only fire recovery when `_*_fired is True` (existing pattern). Clear both start timestamp AND fired flag on recovery.
**Warning signs:** Orphan recovery alerts in SQLite without corresponding sustained alerts.

### Pitfall 4: Default threshold applies to wrong direction
**What goes wrong:** User configures `irtt_loss_upstream.loss_threshold_pct: 10` but expects it to also apply to downstream.
**Why it happens:** Threshold is per-rule, not global.
**How to avoid:** Document that threshold applies per alert type. Use `self._loss_threshold_pct` as shared default (5%), with per-rule override.
**Warning signs:** Upstream and downstream fire at different unexpected thresholds.

### Pitfall 5: IRTT result None vs loss of 0.0
**What goes wrong:** When `irtt_result` is None (IRTT disabled or failed), code tries to access `.send_loss`.
**Why it happens:** Conflating "no IRTT data" with "0% loss".
**How to avoid:** Only enter loss checking when `irtt_result is not None`. The existing `if irtt_result is not None:` gate in run_cycle already handles this.
**Warning signs:** AttributeError on None.

## Code Examples

### State Variables to Add in WANController.__init__()
```python
# =====================================================================
# IRTT LOSS ALERT TIMERS (ALRT-01, ALRT-02, ALRT-03)
# =====================================================================
# Monotonic timestamps tracking when upstream/downstream IRTT loss
# exceeded threshold. Fires irtt_loss_upstream/downstream after
# sustained_sec. Fires irtt_loss_recovered when loss clears IF
# sustained had fired.
# =====================================================================
self._irtt_loss_up_start: float | None = None
self._irtt_loss_down_start: float | None = None
self._irtt_loss_up_fired: bool = False
self._irtt_loss_down_fired: bool = False
self._irtt_loss_threshold_pct: float = 5.0  # default, overridable per-rule
```

### _check_irtt_loss_alerts() Method Signature
```python
def _check_irtt_loss_alerts(self, irtt_result: IRTTResult) -> None:
    """Check sustained IRTT packet loss and fire alerts (ALRT-01, ALRT-02).

    Called each run_cycle() when a fresh IRTT result is available.
    Tracks upstream (send_loss) and downstream (receive_loss) independently.
    Fires irtt_loss_upstream/downstream after sustained_sec threshold.
    Fires irtt_loss_recovered when loss clears IF sustained had fired.

    Args:
        irtt_result: Fresh IRTTResult with send_loss and receive_loss fields.
    """
```

### Call Site in run_cycle() (after existing IRTT handling, ~line 2160)
```python
# IRTT loss alerts (ALRT-01, ALRT-02, ALRT-03)
if irtt_result is not None:
    age = time.monotonic() - irtt_result.timestamp
    cadence = self._irtt_thread._cadence_sec if self._irtt_thread else 10.0
    if age <= cadence * 3:
        self._check_irtt_loss_alerts(irtt_result)
    else:
        # Stale IRTT -- reset loss timers
        self._irtt_loss_up_start = None
        self._irtt_loss_up_fired = False
        self._irtt_loss_down_start = None
        self._irtt_loss_down_fired = False
```

### DiscordFormatter _UNIT_MAP Addition
```python
_UNIT_MAP: dict[str, str] = {
    "rate": "Mbps",
    "rtt": "ms",
    "delta": "ms",
    "baseline": "ms",
    "latency": "ms",
    "loss": "%",  # NEW: for IRTT loss alert metrics
}
```

### Test Mock Pattern (from test_congestion_alerts.py)
```python
@pytest.fixture
def mock_controller():
    """Create mock WANController with IRTT loss alert attributes."""
    from wanctl.autorate_continuous import WANController

    controller = MagicMock(spec=WANController)
    controller.wan_name = "spectrum"
    controller.logger = logging.getLogger("test.irtt_loss")

    # Alert engine (enabled, no persistence)
    controller.alert_engine = AlertEngine(
        enabled=True,
        default_cooldown_sec=300,
        rules={},
        writer=None,
    )

    # IRTT loss timer state (initialized like __init__)
    controller._irtt_loss_up_start = None
    controller._irtt_loss_down_start = None
    controller._irtt_loss_up_fired = False
    controller._irtt_loss_down_fired = False
    controller._irtt_loss_threshold_pct = 5.0
    controller._sustained_sec = 60

    # Bind the real method
    controller._check_irtt_loss_alerts = (
        WANController._check_irtt_loss_alerts.__get__(controller, WANController)
    )

    return controller
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| IRTT loss logged only | IRTT loss logged + persisted to SQLite | v1.18 (Phase 92) | Loss data available but no operator notification |
| N/A | IRTT loss Discord alerts | v1.19 (this phase) | Operators notified of sustained packet loss |

**Existing data flow:**
- IRTT loss already persisted to SQLite as `wanctl_irtt_loss_up_pct` and `wanctl_irtt_loss_down_pct` (v1.18 Phase 92)
- Loss data already logged at DEBUG in run_cycle
- Only missing piece: sustained detection + AlertEngine integration + webhook notification

## Open Questions

1. **One recovery type vs direction-specific recovery types**
   - What we know: CONTEXT.md specifies `irtt_loss_recovered` (singular). Congestion alerts use direction-specific recovery (`congestion_recovered_dl`, `congestion_recovered_ul`).
   - Recommendation: Use single `irtt_loss_recovered` with `direction` field in details dict. This matches CONTEXT.md and is simpler for operators. The details dict already carries `direction: "upstream"` or `direction: "downstream"` for differentiation.

2. **IRTT unavailable during sustained loss tracking**
   - What we know: If IRTT goes stale (age > 3x cadence), we should not continue the sustained timer.
   - Recommendation: Reset sustained timers when IRTT goes stale. This prevents false alerts from stale data. If loss was genuine and IRTT recovers, the timer restarts fresh -- no data is lost.

3. **DiscordFormatter description for loss alerts**
   - What we know: Current `_build_description` handles recovery generically ("recovered to normal state") and non-recovery generically ("WAN: Type Display (severity - STATE)").
   - Recommendation: The generic formatter is adequate. `irtt_loss_upstream` becomes "Irtt Loss Upstream (warning - WARNING)" which is readable. For recovery, the generic "has recovered to normal state" works. No DiscordFormatter changes needed beyond the `_UNIT_MAP` addition.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.x |
| Config file | pyproject.toml |
| Quick run command | `.venv/bin/pytest tests/test_irtt_loss_alerts.py -v` |
| Full suite command | `.venv/bin/pytest tests/ -v` |

### Phase Requirements to Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| ALRT-01 | Sustained upstream loss above threshold fires `irtt_loss_upstream` after sustained_sec | unit | `.venv/bin/pytest tests/test_irtt_loss_alerts.py -k "upstream" -x` | No -- Wave 0 |
| ALRT-02 | Sustained downstream loss above threshold fires `irtt_loss_downstream` after sustained_sec | unit | `.venv/bin/pytest tests/test_irtt_loss_alerts.py -k "downstream" -x` | No -- Wave 0 |
| ALRT-03 | Per-event cooldown suppression via (type, WAN) key | unit | `.venv/bin/pytest tests/test_irtt_loss_alerts.py -k "cooldown" -x` | No -- Wave 0 |

### Sampling Rate
- **Per task commit:** `.venv/bin/pytest tests/test_irtt_loss_alerts.py -v`
- **Per wave merge:** `.venv/bin/pytest tests/ -v`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_irtt_loss_alerts.py` -- covers ALRT-01, ALRT-02, ALRT-03 (sustained upstream, sustained downstream, cooldown, recovery, timer reset, stale IRTT handling, per-rule threshold override, per-rule sustained_sec override)

## Sources

### Primary (HIGH confidence)
- `src/wanctl/alert_engine.py` -- AlertEngine.fire() API, cooldown mechanics, rule_key support
- `src/wanctl/autorate_continuous.py` lines 1496-1521 -- sustained timer initialization pattern
- `src/wanctl/autorate_continuous.py` lines 2334-2449 -- `_check_congestion_alerts()` sustained timer implementation (model for IRTT loss)
- `src/wanctl/autorate_continuous.py` lines 2138-2159 -- IRTT result consumption in run_cycle (call site for new method)
- `src/wanctl/irtt_measurement.py` lines 33-34 -- `IRTTResult.send_loss` and `receive_loss` fields
- `src/wanctl/webhook_delivery.py` lines 107-113 -- `_UNIT_MAP` (needs "loss" -> "%" addition)
- `tests/test_congestion_alerts.py` -- test mock pattern (mock_controller fixture, method binding)

### Secondary (MEDIUM confidence)
- `.planning/phases/95-irtt-loss-alerts/95-CONTEXT.md` -- user decisions on thresholds, types, recovery

### Tertiary (LOW confidence)
None -- all findings verified from codebase.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- all infrastructure exists in codebase, no new dependencies
- Architecture: HIGH -- exact pattern exists in `_check_congestion_alerts`, copy-and-adapt
- Pitfalls: HIGH -- documented from existing MagicMock/staleness issues in MEMORY.md

**Research date:** 2026-03-18
**Valid until:** 2026-04-18 (stable -- internal pattern, no external dependencies)
