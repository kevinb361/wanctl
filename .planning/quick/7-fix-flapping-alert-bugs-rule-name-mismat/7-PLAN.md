---
phase: quick-7
plan: 1
type: execute
wave: 1
depends_on: []
files_modified:
  - src/wanctl/autorate_continuous.py
  - tests/test_anomaly_alerts.py
autonomous: true
must_haves:
  truths:
    - "Flapping config reads from congestion_flapping rule, not flapping_dl/flapping_ul"
    - "After flapping alert fires, deque is cleared so it does not re-fire at next cooldown boundary"
    - "Default flap_threshold is 30 and flap_window_sec is 120, sane for 20Hz cycle rate"
    - "Alert types remain flapping_dl and flapping_ul for per-direction tracking"
  artifacts:
    - path: "src/wanctl/autorate_continuous.py"
      provides: "Fixed _check_flapping_alerts method"
      contains: "congestion_flapping"
    - path: "tests/test_anomaly_alerts.py"
      provides: "Updated tests for all three bug fixes"
      contains: "congestion_flapping"
  key_links:
    - from: "autorate_continuous.py::_check_flapping_alerts"
      to: "alert_engine._rules"
      via: "rules.get('congestion_flapping', {})"
      pattern: '_rules\\.get\\("congestion_flapping"'
---

<objective>
Fix three production bugs in _check_flapping_alerts() that caused 74 false alerts in 3.2 hours.

Purpose: Stop alert spam. The rule name mismatch means config overrides are silently ignored, the deque not clearing causes re-fire every cooldown period, and the default threshold is too low for 20Hz.
Output: Corrected _check_flapping_alerts() and updated tests.
</objective>

<execution_context>
@./.claude/get-shit-done/workflows/execute-plan.md
@./.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@src/wanctl/autorate_continuous.py (lines 2017-2082: _check_flapping_alerts method)
@tests/test_anomaly_alerts.py (lines 195-524: flapping fixture and tests)
@src/wanctl/alert_engine.py (AlertEngine._rules pattern: rules.get(alert_type, {}))

<interfaces>
<!-- AlertEngine rules lookup pattern (used throughout autorate_continuous.py): -->
<!-- The rules dict is keyed by rule name from YAML config, NOT by alert type. -->
<!-- Other alert methods already use the config rule name correctly: -->
<!--   congestion_sustained_dl, congestion_sustained_ul, wan_offline, baseline_drift -->
<!-- Flapping should use congestion_flapping (single config rule for both DL+UL). -->

From src/wanctl/alert_engine.py:
```python
class AlertEngine:
    def fire(self, alert_type: str, severity: str, wan_name: str, details: dict) -> bool:
        # alert_type is the tracking key (flapping_dl, flapping_ul)
        # _rules lookup uses alert_type by default but callers can read from any rule key

    _rules: dict  # Map of rule_name -> {enabled, cooldown_sec, severity, ...custom keys}
```

From src/wanctl/autorate_continuous.py (correct pattern for other alerts):
```python
# Sustained DL reads from "congestion_sustained_dl" rule
sustained_sec = self.alert_engine._rules.get("congestion_sustained_dl", {}).get("sustained_sec", ...)
# But fires as different alert type
self.alert_engine.fire("congestion_sustained_dl", ...)

# Baseline drift reads from "baseline_drift" rule
threshold = self.alert_engine._rules.get("baseline_drift", {}).get("drift_threshold_pct", 50)
```
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Fix _check_flapping_alerts and update tests</name>
  <files>src/wanctl/autorate_continuous.py, tests/test_anomaly_alerts.py</files>
  <behavior>
    - Test: Rule lookup reads from "congestion_flapping" key (single shared config rule), not "flapping_dl"/"flapping_ul"
    - Test: After DL alert fires, _dl_zone_transitions deque is empty (cleared)
    - Test: After UL alert fires, _ul_zone_transitions deque is empty (cleared)
    - Test: Default threshold is 30 when no rule configured (not 6)
    - Test: Default window is 120s when no rule configured (not 60s)
    - Test: Alert types passed to fire() remain "flapping_dl" and "flapping_ul" (unchanged)
    - Test: Existing tests still pass after fixture updates (rule key changed to congestion_flapping)
  </behavior>
  <action>
    **In src/wanctl/autorate_continuous.py, method _check_flapping_alerts (lines 2017-2082):**

    Bug 1 fix -- Change BOTH rule lookups from per-direction keys to single shared config rule:
    - Line 2036: `dl_rule = self.alert_engine._rules.get("flapping_dl", {})` --> `flap_rule = self.alert_engine._rules.get("congestion_flapping", {})`
    - Line 2063: `ul_rule = self.alert_engine._rules.get("flapping_ul", {})` --> reuse `flap_rule` (already loaded above)
    - Update all references from `dl_rule`/`ul_rule` to `flap_rule` in both DL and UL blocks
    - Move the rule lookup to the top of the method (before DL block) since it is shared

    Bug 2 fix -- Clear deque after firing:
    - After `self.alert_engine.fire("flapping_dl", ...)` (line 2046-2055), add: `self._dl_zone_transitions.clear()`
    - After `self.alert_engine.fire("flapping_ul", ...)` (line 2073-2082), add: `self._ul_zone_transitions.clear()`

    Bug 3 fix -- Raise hardcoded defaults:
    - Change all `flap_window_sec` defaults from 60 to 120: `.get("flap_window_sec", 120)`
    - Change all `flap_threshold` defaults from 6 to 30: `.get("flap_threshold", 30)`

    **In tests/test_anomaly_alerts.py:**

    Update mock_flapping_controller fixture (lines 216-231):
    - Replace the two separate rule keys `"flapping_dl"` and `"flapping_ul"` with a single `"congestion_flapping"` key
    - The single rule should have: `{"enabled": True, "cooldown_sec": 300, "severity": "warning", "flap_threshold": 6, "flap_window_sec": 60}`

    Add new test class TestFlappingDequeClear:
    - test_dl_deque_cleared_after_fire: Generate enough transitions to fire, verify deque is empty afterward
    - test_ul_deque_cleared_after_fire: Same for UL direction
    - test_no_refire_after_cooldown_expires: Generate transitions, fire, advance past cooldown, verify no immediate re-fire (deque was cleared)

    Add new test class TestFlappingDefaults:
    - test_default_threshold_is_30: Create controller with empty rules {}, verify 29 transitions do NOT fire but 30 do
    - test_default_window_is_120: Create controller with empty rules {}, verify transitions >120s old are pruned

    Update existing tests that override rules inline (lines 427-523):
    - test_flapping_severity_configurable_via_rules: Change rule key from "flapping_dl" to "congestion_flapping"
    - test_per_rule_flap_threshold_override: Change rule key from "flapping_dl" to "congestion_flapping"
    - test_per_rule_flap_window_sec_override: Change rule key from "flapping_dl" to "congestion_flapping"

    Update test_dl_flapping_details_include_required_fields: window_sec assertion should match the fixture's configured value (60), not the new default (120). This is already correct since the fixture sets flap_window_sec: 60.
  </action>
  <verify>
    <automated>cd /home/kevin/projects/wanctl && .venv/bin/pytest tests/test_anomaly_alerts.py -v -x 2>&1 | tail -40</automated>
  </verify>
  <done>
    - _check_flapping_alerts reads config from "congestion_flapping" rule key (single rule for both DL and UL)
    - Alert types remain "flapping_dl" and "flapping_ul" when calling fire()
    - Deques cleared after each direction's alert fires
    - Default threshold=30, window=120s when no rule configured
    - All existing + new tests pass
  </done>
</task>

<task type="auto">
  <name>Task 2: Verify lint and type checks pass</name>
  <files>src/wanctl/autorate_continuous.py, tests/test_anomaly_alerts.py</files>
  <action>
    Run ruff check and mypy on modified files. Fix any issues introduced by the changes.
    Run the full test suite to ensure no regressions outside test_anomaly_alerts.py.
  </action>
  <verify>
    <automated>cd /home/kevin/projects/wanctl && .venv/bin/ruff check src/wanctl/autorate_continuous.py tests/test_anomaly_alerts.py && .venv/bin/pytest tests/ -x -q 2>&1 | tail -10</automated>
  </verify>
  <done>
    - ruff check passes with no errors
    - Full test suite passes with no regressions
  </done>
</task>

</tasks>

<verification>
1. `cd /home/kevin/projects/wanctl && .venv/bin/pytest tests/test_anomaly_alerts.py -v` -- all flapping tests pass
2. `cd /home/kevin/projects/wanctl && .venv/bin/ruff check src/wanctl/autorate_continuous.py tests/test_anomaly_alerts.py` -- clean
3. `cd /home/kevin/projects/wanctl && .venv/bin/pytest tests/ -x -q` -- full suite, no regressions
4. `grep -n 'congestion_flapping' src/wanctl/autorate_continuous.py` -- confirms rule name fix
5. `grep -n '\.clear()' src/wanctl/autorate_continuous.py | grep -i transition` -- confirms deque clearing
6. `grep -n 'flap_threshold.*30\|flap_window_sec.*120' src/wanctl/autorate_continuous.py` -- confirms raised defaults
</verification>

<success_criteria>
- Production config rule "congestion_flapping" will be read correctly for both DL and UL flapping parameters
- Deque clearing prevents the every-cooldown-period re-fire pattern (74 alerts in 3.2h)
- Default threshold 30 (up from 6) and window 120s (up from 60s) are sane for 20Hz polling
- Alert types flapping_dl/flapping_ul preserved for per-direction cooldown tracking
- Zero test regressions
</success_criteria>

<output>
After completion, create `.planning/quick/7-fix-flapping-alert-bugs-rule-name-mismat/7-SUMMARY.md`
</output>
