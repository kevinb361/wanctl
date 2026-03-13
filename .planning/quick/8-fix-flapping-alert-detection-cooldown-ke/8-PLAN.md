---
phase: quick-8
plan: 1
type: execute
wave: 1
depends_on: []
files_modified:
  - src/wanctl/alert_engine.py
  - src/wanctl/autorate_continuous.py
  - tests/test_anomaly_alerts.py
autonomous: false
requirements: []
must_haves:
  truths:
    - "flapping_dl/flapping_ul alerts use congestion_flapping rule's cooldown_sec (600s), not default 300s"
    - "Single-cycle zone blips (departing zone held < 1s) do not count as transitions"
    - "Sustained zone changes (held >= min_hold_sec) still count and fire flapping alert at threshold"
    - "Production config updated and reloaded on cake-spectrum"
  artifacts:
    - path: "src/wanctl/alert_engine.py"
      provides: "fire() and _is_cooled_down() accept optional rule_key for parent-rule cooldown lookup"
    - path: "src/wanctl/autorate_continuous.py"
      provides: "_dl_zone_hold/_ul_zone_hold counters, min_hold_cycles dwell filter, rule_key passed to fire()"
    - path: "tests/test_anomaly_alerts.py"
      provides: "Tests for cooldown key fix and dwell filter behavior"
  key_links:
    - from: "autorate_continuous.py _check_flapping_alerts"
      to: "alert_engine.py fire()"
      via: "rule_key='congestion_flapping' parameter"
      pattern: "fire.*rule_key.*congestion_flapping"
---

<objective>
Fix two flapping alert detection bugs: (1) cooldown key mismatch where fire("flapping_dl") can't look up
the "congestion_flapping" rule's cooldown_sec, and (2) missing dwell filter that counts single-cycle noise
as real zone transitions. Then deploy to production.

Purpose: Eliminate false flapping alerts (74 in 3.2h before quick-7, still noisy due to single-cycle blips)
Output: Corrected alert_engine.py, autorate_continuous.py, updated tests, production config deployed
</objective>

<context>
@src/wanctl/alert_engine.py
@src/wanctl/autorate_continuous.py (lines 1180-1190, 2017-2083)
@tests/test_anomaly_alerts.py
@.planning/quick/7-fix-flapping-alert-bugs-rule-name-mismat/7-SUMMARY.md
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Fix cooldown key mismatch and add dwell filter</name>
  <files>src/wanctl/alert_engine.py, src/wanctl/autorate_continuous.py, tests/test_anomaly_alerts.py</files>
  <behavior>
    - Test: fire("flapping_dl", rule_key="congestion_flapping") uses congestion_flapping's cooldown_sec (600), not default (300)
    - Test: fire() without rule_key still uses alert_type for rule lookup (backward compat)
    - Test: _is_cooled_down respects rule_key for cooldown lookup
    - Test: get_active_cooldowns uses rule_key mapping when available
    - Test: Zone change where departing zone was held < min_hold_cycles does NOT count as transition
    - Test: Zone change where departing zone was held >= min_hold_cycles DOES count as transition
    - Test: min_hold_sec configurable via congestion_flapping rule (default 1.0)
    - Test: At 50ms cycle (CYCLE_INTERVAL_SECONDS=0.05), min_hold_sec=1.0 => min_hold_cycles=20
    - Test: Rapid GREEN->YELLOW->GREEN blips (1-2 cycles in YELLOW) do not accumulate transitions
    - Test: Sustained YELLOW (held 25+ cycles) then change to GREEN counts as one transition
  </behavior>
  <action>
    **Part A -- AlertEngine rule_key parameter (src/wanctl/alert_engine.py):**

    1. Add optional `rule_key: str | None = None` parameter to `fire()` method signature.
       When provided, use `rule_key` instead of `alert_type` for:
       - Per-rule enabled gate: `self._rules.get(rule_key or alert_type, {})`
       - Pass rule_key to `_is_cooled_down()`
    2. Update `_is_cooled_down()` to accept optional `rule_key: str | None = None`.
       Use `rule_key or alert_type` for the `self._rules.get()` cooldown lookup.
       The cooldown dict key remains `(alert_type, wan_name)` -- only the rule config lookup changes.
    3. Update `get_active_cooldowns()`: store a `_rule_key_map: dict[str, str]` on the engine
       that maps alert_type -> rule_key. Populated in fire() when rule_key is provided.
       Use this map in get_active_cooldowns() for correct cooldown_sec lookup.

    **Part B -- Dwell filter (src/wanctl/autorate_continuous.py):**

    4. Add instance vars at line ~1187 (after _ul_prev_zone):
       ```python
       self._dl_zone_hold: int = 0  # cycles current DL zone has been held
       self._ul_zone_hold: int = 0  # cycles current UL zone has been held
       ```

    5. In `_check_flapping_alerts()`, read min_hold config:
       ```python
       min_hold_sec = flap_rule.get("min_hold_sec", 1.0)
       min_hold_cycles = max(1, int(min_hold_sec / CYCLE_INTERVAL_SECONDS))
       ```

    6. Replace DL transition logic (lines 2037-2039):
       ```python
       # --- Download flapping ---
       if self._dl_prev_zone is not None and dl_zone != self._dl_prev_zone:
           # Only count transition if departing zone was held long enough
           if self._dl_zone_hold >= min_hold_cycles:
               self._dl_zone_transitions.append(now)
           self._dl_zone_hold = 0
       else:
           self._dl_zone_hold += 1
       self._dl_prev_zone = dl_zone
       ```
       Same pattern for UL (lines 2061-2063).

    7. Pass `rule_key="congestion_flapping"` in both fire() calls:
       ```python
       self.alert_engine.fire(
           "flapping_dl",
           flap_severity,
           self.wan_name,
           {...},
           rule_key="congestion_flapping",
       )
       ```

    **Part C -- Tests (tests/test_anomaly_alerts.py):**

    8. Add new test class `TestFlappingCooldownKeyFix`:
       - Test that fire("flapping_dl", rule_key="congestion_flapping") picks up congestion_flapping's cooldown_sec
       - Test backward compat: fire() without rule_key uses alert_type

    9. Add new test class `TestFlappingDwellFilter`:
       - Test single-cycle blips don't count (hold=1, threshold never reached)
       - Test sustained zones do count (hold=25 cycles, transitions accumulate)
       - Test min_hold_sec configurable
       - Test min_hold_cycles calculation (1.0s / 0.05s = 20)

    10. Update `mock_flapping_controller` fixture: add `_dl_zone_hold = 0` and `_ul_zone_hold = 0`.

    11. Update existing tests that generate rapid transitions: they now need to simulate sustained holds.
        For tests with threshold=6 and zones like ["GREEN","RED","GREEN",...], each zone must be repeated
        for min_hold_cycles (default 20) before changing. Alternatively, set min_hold_sec=0 in those
        test fixtures' rules to disable the dwell filter for tests that aren't testing dwell behavior.
        PREFERRED: add `"min_hold_sec": 0` to the congestion_flapping rule in mock_flapping_controller
        fixture so existing tests pass unchanged, then use explicit min_hold_sec > 0 only in dwell-specific tests.

    RED: Write all new tests first, verify they fail.
    GREEN: Implement changes, verify all tests pass.
  </action>
  <verify>
    <automated>.venv/bin/pytest tests/test_anomaly_alerts.py -v -x && .venv/bin/ruff check src/wanctl/alert_engine.py src/wanctl/autorate_continuous.py tests/test_anomaly_alerts.py && .venv/bin/mypy src/wanctl/alert_engine.py src/wanctl/autorate_continuous.py</automated>
  </verify>
  <done>
    - fire("flapping_dl", rule_key="congestion_flapping") looks up cooldown from congestion_flapping rule
    - _is_cooled_down uses rule_key for config lookup, alert_type for cooldown dict key
    - Zone changes where departing zone held < min_hold_cycles are filtered out
    - All existing tests pass (min_hold_sec: 0 in default fixture)
    - New dwell filter tests pass with min_hold_sec > 0
    - ruff clean, mypy clean
  </done>
</task>

<task type="auto">
  <name>Task 2: Run full test suite and verify no regressions</name>
  <files>tests/</files>
  <action>
    Run the full test suite (excluding integration tests) to confirm zero regressions from the
    alert_engine.py signature change (rule_key parameter). The fire() signature changed -- any
    callers or mocks in other test files must still work since rule_key defaults to None.

    1. Run: `.venv/bin/pytest tests/ --ignore=tests/integration -x -q`
    2. If any failures, investigate and fix (likely mock specs needing update for new parameter).
    3. Run: `.venv/bin/ruff check src/ tests/`
  </action>
  <verify>
    <automated>.venv/bin/pytest tests/ --ignore=tests/integration -x -q</automated>
  </verify>
  <done>All 2700+ tests pass, zero regressions from fire() signature change</done>
</task>

<task type="checkpoint:human-action" gate="blocking">
  <name>Task 3: Deploy updated config to production</name>
  <what-built>Cooldown key fix and dwell filter implemented and tested locally</what-built>
  <action>
    Deploy to cake-spectrum production:

    1. SSH to cake-spectrum and update /etc/wanctl/spectrum.yaml:
       Under `alerting.rules.congestion_flapping`, add:
       ```yaml
       min_hold_sec: 1.0
       ```

    2. Deploy updated code to /opt/wanctl/ on cake-spectrum (rsync or git pull)

    3. Send SIGUSR1 to reload config:
       ```bash
       ssh cake-spectrum 'kill -USR1 $(systemctl show wanctl@spectrum --property=MainPID --value)'
       ```

    4. Verify via health endpoint:
       ```bash
       ssh cake-spectrum 'curl -s http://127.0.0.1:9101/health | python3 -m json.tool'
       ```

    5. Monitor logs for 5 minutes to confirm no false flapping alerts:
       ```bash
       ssh cake-spectrum 'journalctl -u wanctl@spectrum --since "5 min ago" | grep -i flapping'
       ```

    6. Repeat for cake-att if alerting is enabled there.
  </action>
  <resume-signal>Confirm production deployment complete or describe issues</resume-signal>
</task>

</tasks>

<verification>
1. `.venv/bin/pytest tests/test_anomaly_alerts.py -v` -- all flapping tests pass
2. `.venv/bin/pytest tests/ --ignore=tests/integration -x -q` -- full suite passes
3. `grep rule_key src/wanctl/alert_engine.py` -- confirms new parameter in fire() and _is_cooled_down()
4. `grep min_hold src/wanctl/autorate_continuous.py` -- confirms dwell filter
5. `grep _zone_hold src/wanctl/autorate_continuous.py` -- confirms hold counters
6. `grep rule_key.*congestion_flapping src/wanctl/autorate_continuous.py` -- confirms rule_key passed in fire()
</verification>

<success_criteria>
- Flapping alerts use congestion_flapping rule's cooldown_sec (600s not default 300s)
- Single-cycle zone blips filtered out by min_hold_cycles dwell gate
- All 2700+ tests pass with zero regressions
- Production config deployed with min_hold_sec: 1.0
</success_criteria>

<output>
After completion, create `.planning/quick/8-fix-flapping-alert-detection-cooldown-ke/8-SUMMARY.md`
</output>
