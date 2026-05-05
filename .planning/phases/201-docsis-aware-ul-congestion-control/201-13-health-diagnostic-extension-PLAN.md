---
phase: 201-docsis-aware-ul-congestion-control
plan: 13
type: execute
wave: 9
depends_on: [11]
files_modified:
  - src/wanctl/queue_controller.py
  - src/wanctl/health_check.py
  - tests/test_queue_controller.py
  - tests/test_health_check.py
autonomous: true
gap_closure: true
revision: 2  # Iteration 2 — drops sustained_red_cycles per Plan 201-14 rev 3 (Option B has no fall-through threshold). Six absorbed fields, not seven.
requirements: [VALN-06]
tags: [phase-201, gap-closure, health-payload, observability, reviews-low-deferred, additive, codex-coordinated]

must_haves:
  truths:
    - "/health.wans[0].upload exposes max_delay_delta_us as a numeric (int microseconds) additive field"
    - "/health.wans[0].upload exposes red_streak as a non-negative int additive field"
    - "/health.wans[0].upload exposes zone_trace as a list of the last N zone strings (RED/YELLOW/GREEN) — bounded ring buffer, default N=200 = 10s @ 20Hz"
    - "/health.wans[0].upload exposes headroom_exhausted_streak as a non-negative int additive field (Plan 201-14 control-model amendment counter; absorbed from Plan 201-14 WARNING 4)"
    - "/health.wans[0].upload exposes anti_windup_cycles as a non-negative int additive field (Plan 201-14 YAML config echo; absorbed from Plan 201-14 WARNING 4)"
    - "/health.wans[0].upload exposes anti_windup_triggers as a non-negative int counter (Plan 201-14 anti-windup engagement counter; absorbed from Plan 201-14 WARNING 6 — counter pattern is preferred over WARN-level log spam under sustained engagement)"
    - "All SIX new fields are present-and-typed in legacy (docsis_mode=false) deployments — no link-type Python branching, no docsis_mode gating on the health payload (additive is global). Plan 201-14 owns the controller-side counter increments; this plan owns serialization."
    - "Existing /health upload fields (docsis_mode_active, setpoint_mbps, headroom_state, rtt_integral_ms_s, cake_aligned, floor_hit_cycles_total) remain present and unchanged in shape (D-16 contract)"
    - "Zone trace is appended each cycle inside QueueController.adjust(); buffer write is O(1); no allocation on the hot path"
    - "**REVISION 2 — `sustained_red_cycles` is NOT serialized** (Plan 201-14 rev 3 deletes this knob entirely; Option B has no fall-through threshold by red_streak)"
  artifacts:
    - path: src/wanctl/queue_controller.py
      provides: "Ring-buffer zone_trace + max_delay_delta_us snapshot field; get_health_data() exports all six new fields (3 from original spec + 3 absorbed from 201-14 WARNING 4/6, sustained_red_cycles dropped per rev 2)"
      contains: "zone_trace"
    - path: src/wanctl/health_check.py
      provides: "Upload section serialization passes all six new fields through"
      contains: "max_delay_delta_us"
  key_links:
    - from: "src/wanctl/queue_controller.py:adjust()"
      to: "self._zone_trace deque"
      via: "self._zone_trace.append(zone) at end of adjust()"
      pattern: "_zone_trace.append"
    - from: "src/wanctl/health_check.py:300-345 (upload result.update block)"
      to: "qc_health dict from get_health_data()"
      via: "result['max_delay_delta_us'] = qc_health.get('max_delay_delta_us'); result['anti_windup_triggers'] = qc_health.get('anti_windup_triggers')"
      pattern: "max_delay_delta_us|anti_windup_triggers"
---

<objective>
**Gap-closure Plan 1 of 4. Revision 2 — coordinated with Plan 201-14 rev 3.** Lands FIRST so the control-model amendment (Plan 201-14) is observable from the moment it ships. The 201-11 canary FAIL was diagnosed by inference (not direct evidence) because three diagnostic fields were absent from /health: `max_delay_delta_us` (the CAKE corroborator's actual numeric driver, not just the boolean `cake_aligned`), `red_streak` (the immediate predictor of RED-decay-to-floor), and a downsampled per-cycle zone trace (the only way to attribute floor hits to specific RED-pulse events without a cycle-level capture harness).

Per VERIFICATION.md gap "max_delay_delta_us is publicly serialized through /health for post-canary diagnosis": this is now BLOCKING for VALN-06 closure, not a LOW-deferred item. Per VERIFICATION.md gap-1 missing item "Cycle-fidelity diagnostic of the actual zone sequence": the loaded_capture.ndjson cannot confirm RED-pulsing vs YELLOW-stuck without per-cycle zone state.

**Revision absorption (WARNING 4 + WARNING 6 from plan-checker review, REV 2 update from codex 201-REVIEWS):** This plan owns serialization of three control-model amendment counters that Plan 201-14 increments inside the controller:
- `headroom_exhausted_streak` (cycle counter, increments per EXHAUSTED cycle, resets on AVAILABLE)
- `anti_windup_cycles` (YAML config echo for diagnostic correlation)
- `anti_windup_triggers` (counter, increments each time the anti-windup helper caps the integral; replaces a WARN-level log spam approach with a queryable counter — HIGH-5 pattern)

**Revision 2 — `sustained_red_cycles` REMOVED.** Plan 201-14 rev 3 (codex HIGH-CODEX-1 closure) replaces the multiplicative-decay-with-fall-through algorithm with bounded-absolute decay (Option B). Option B has no fall-through-by-red_streak threshold — the regime gate is purely on `current_rate` band. The `sustained_red_cycles` knob is deleted from queue_controller.py; this plan no longer serializes it. The two new Plan 201-14 rev-3 knobs (`red_decay_step_pct`, `red_decay_delta_max_pct`) are NOT serialized to /health by this plan — they are static YAML config echoes already inspectable via `cat /etc/wanctl/spectrum.yaml`; surfacing them in /health adds no diagnostic value (codex did not request them).

Output: SIX additive /health fields (down from seven in rev 1), two test classes (one per file modified), no behavior change to the controller.

Purpose: post-deploy root-cause diagnosis of any future canary failure does not require re-running the canary with extra instrumentation. Fields are present in legacy mode too (additive contract — D-16) so they're available for non-DOCSIS deployments as well.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/phases/201-docsis-aware-ul-congestion-control/201-CONTEXT.md
@.planning/phases/201-docsis-aware-ul-congestion-control/201-VERIFICATION.md
@.planning/phases/201-docsis-aware-ul-congestion-control/201-REVIEWS.md
@.planning/phases/201-docsis-aware-ul-congestion-control/201-11-CANARY-VERDICT.md
@src/wanctl/queue_controller.py
@src/wanctl/health_check.py
@./CLAUDE.md
</context>

<interfaces>
<!-- Existing patterns to follow VERBATIM. -->

`QueueController.get_health_data()` already returns a dict with these Phase 201 keys (queue_controller.py:611-619):
```python
"docsis_mode_active": bool(self._docsis_mode),
"setpoint_mbps": ((self._setpoint_bps / 1_000_000) if self._setpoint_bps else None),
"headroom_state": self._headroom_state,
"rtt_integral_ms_s": round(self._last_integral_ms_s, 3),
"cake_aligned": bool(self._cake_aligned),
"floor_hit_cycles_total": int(self.floor_hit_cycles),
```
This plan ADDS six more keys to the same dict.

`health_check.py:323-340` is where `direction == "upload"` extends `result` with the Phase 201 fields via `result.update({...})`. Add the six new fields to the SAME `result.update({...})` block (additive, single statement).

`QueueController.adjust()` returns `(zone, new_rate, transition_reason)` and is called once per 50ms cycle from `wan_controller.py:3024`. The zone string is computed at line 161 (`self._classify_zone_3state(...)`) and is the value to append to the ring buffer.

Cake snapshot: `self._ul_cake_snapshot` is a `CakeSignalSnapshot` dataclass with `.max_delay_delta_us: int` (cake_signal.py:85-123). The upload QueueController already receives this via `cake_snapshot=` parameter to `adjust()` — store the latest value on the controller as `self._last_max_delay_delta_us` and serialize.

**Plan 201-14 rev 3 dependency for absorbed fields:** Plan 201-14 rev 3 (which lands AFTER this plan but tests for both must coexist) initializes three absorbed counters inside QueueController.__init__:
- `self._headroom_exhausted_streak: int = 0`
- `self._anti_windup_cycles: int = 60` (constructor param)
- `self._anti_windup_triggers: int = 0`

Note: `self._sustained_red_cycles` was a planned attribute in Plan 201-14 rev 1, but Plan 201-14 rev 3 deletes it. This plan rev 2 drops the corresponding /health field.

Since this plan lands BEFORE Plan 201-14 rev 3, the absorbed-field serialization in Task 1 step 3 must use `getattr(self, '_attr_name', default)` to be tolerant of pre-201-14 controller state. Once 201-14 lands, the attributes are always present.
</interfaces>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Add zone_trace ring buffer, red_streak passthrough, max_delay_delta_us snapshot, AND three absorbed 201-14 rev-3 counters to QueueController</name>
  <read_first>
    - src/wanctl/queue_controller.py (focus on __init__ lines 25-127, adjust() lines 128-176, get_health_data() lines 595-620)
    - src/wanctl/cake_signal.py (lines 85-123, CakeSignalSnapshot dataclass)
    - tests/test_queue_controller.py (look at TestDocsisModeIntegralClassifier and TestDocsisModeSetpointClamp at lines 3517-3600 for fixture patterns and `_make_docsis_controller` helper)
    - .planning/phases/201-docsis-aware-ul-congestion-control/201-VERIFICATION.md (gap-1 missing-items list)
    - .planning/phases/201-docsis-aware-ul-congestion-control/201-14-control-model-amendment-PLAN.md (rev 3 — three absorbed-field constructor attributes; sustained_red_cycles is NOT one of them)
  </read_first>
  <files>src/wanctl/queue_controller.py, tests/test_queue_controller.py</files>
  <behavior>
    - Test: zone_trace is initialized as a deque(maxlen=200) — bounded ring buffer at exactly 200 entries (10s @ 20Hz).
    - Test: zone_trace appends one entry per adjust() call; after 250 adjusts it contains exactly the last 200 zones.
    - Test: zone_trace tail matches the sequence of zones returned by adjust() (FIFO ordering preserved).
    - Test: get_health_data() returns "zone_trace" as a list[str] (not a deque) of the last <=200 entries.
    - Test: get_health_data() returns "red_streak" matching self.red_streak (an int, >= 0).
    - Test: get_health_data() returns "max_delay_delta_us" as an int matching the most recent cake_snapshot.max_delay_delta_us, or 0 if no snapshot has been provided yet (cold start).
    - Test: zone_trace works in legacy (docsis_mode=False) mode too — test by calling adjust() 5 times on a non-docsis controller and asserting trace length == 5.
    - Test: when adjust() is called without a cake_snapshot (cake_snapshot=None), max_delay_delta_us in get_health_data() retains the previous value (does NOT reset to 0 on a None cycle).
    - **Test (absorbed from 201-14 WARNING 4):** get_health_data() returns "headroom_exhausted_streak" as an int >= 0. Default value before Plan 201-14 lands: 0 (via getattr fallback).
    - **Test (absorbed from 201-14 WARNING 4):** get_health_data() returns "anti_windup_cycles" as an int. Default before 201-14 lands: 60 (via getattr fallback).
    - **Test (absorbed from 201-14 WARNING 6):** get_health_data() returns "anti_windup_triggers" as an int >= 0 counter. Default before 201-14 lands: 0 (via getattr fallback).
    - **REV 2:** No `sustained_red_cycles` test — Plan 201-14 rev 3 deletes the knob entirely.
  </behavior>
  <action>
    1. In `QueueController.__init__()` (queue_controller.py, after line 122 where `self.floor_hit_cycles = 0` is set), add:
       ```python
       # Phase 201 gap-closure: diagnostic fields for /health serialization.
       # Bounded ring buffer; 200 entries = 10s of cycles @ 50ms.
       self._zone_trace: deque[str] = deque(maxlen=200)
       self._last_max_delay_delta_us: int = 0
       ```
       (`deque` is already imported at line 11.)

       NOTE: The three absorbed-field counters (`_headroom_exhausted_streak`, `_anti_windup_cycles`, `_anti_windup_triggers`) are NOT initialized in this plan — they are owned by Plan 201-14. This plan exposes them via getattr-tolerant serialization in step 3.

    2. In `QueueController.adjust()`, AFTER the `zone = self._classify_zone_3state(...)` line (currently line 161) but BEFORE `self._compute_rate_3state(zone)`:
       ```python
       self._zone_trace.append(zone)
       if cake_snapshot is not None:
           self._last_max_delay_delta_us = int(cake_snapshot.max_delay_delta_us)
       ```
       Note: `self.red_streak` is already maintained inside `_classify_zone_3state` (lines 188, 198, 218, 224) — no new bookkeeping needed.

    3. In `QueueController.get_health_data()`, extend the returned dict with six new keys ALONGSIDE the existing Phase 201 block (around lines 611-619). Add INSIDE the same dict literal:
       ```python
       # Original Plan 201-13 fields:
       "max_delay_delta_us": int(self._last_max_delay_delta_us),
       "red_streak": int(self.red_streak),
       "zone_trace": list(self._zone_trace),
       # Absorbed from Plan 201-14 WARNING 4 (control-model amendment counters; rev 2 drops sustained_red_cycles):
       # getattr fallback tolerates pre-201-14 controller state for wave-ordering safety.
       "headroom_exhausted_streak": int(getattr(self, "_headroom_exhausted_streak", 0)),
       "anti_windup_cycles": int(getattr(self, "_anti_windup_cycles", 60)),
       # Absorbed from Plan 201-14 WARNING 6 (counter > log spam):
       "anti_windup_triggers": int(getattr(self, "_anti_windup_triggers", 0)),
       ```
       Keep all existing keys unchanged. **Do NOT add `sustained_red_cycles`** — Plan 201-14 rev 3 deletes that knob.

    4. Add a test class `TestDocsisModeDiagnosticHealth` to `tests/test_queue_controller.py` (place after `TestDocsisModeCakeCorroborator`). It must cover all 11 behaviors above (8 original + 3 absorbed; no sustained_red_cycles test). For the three absorbed-field tests, the test may either set the attributes manually on the controller fixture (testing the serialization path) or rely on the getattr defaults (testing the fallback path). Include both styles.

    5. Hot-path budget: deque.append is O(1); `int(...)` on an int is a no-op; the `list(self._zone_trace)` copy and three `getattr(...)` calls in get_health_data are OUTSIDE the 50ms hot path.
  </action>
  <verify>
    <automated>.venv/bin/pytest -o addopts='' tests/test_queue_controller.py::TestDocsisModeDiagnosticHealth -v</automated>
    <automated>.venv/bin/pytest -o addopts='' tests/test_queue_controller.py -q --tb=short</automated>
    <automated>grep -nE 'self\._zone_trace|self\._last_max_delay_delta_us' src/wanctl/queue_controller.py | grep -v '^#' | wc -l | grep -qE '^[5-9]$|^1[0-9]$'</automated>
    <automated>grep -E '"headroom_exhausted_streak"|"anti_windup_cycles"|"anti_windup_triggers"' src/wanctl/queue_controller.py | grep -v '^#' | wc -l | grep -qE '^[3-9]$'</automated>
    <automated>grep -E '"sustained_red_cycles"' src/wanctl/queue_controller.py | grep -v '^#' | wc -l | grep -qE '^0$'</automated>
  </verify>
  <acceptance_criteria>
    - `grep -q "_zone_trace: deque\[str\] = deque(maxlen=200)" src/wanctl/queue_controller.py` (init present)
    - `grep -q "self._zone_trace.append(zone)" src/wanctl/queue_controller.py` (per-cycle append present)
    - `grep -q '"zone_trace": list(self._zone_trace)' src/wanctl/queue_controller.py` (export present)
    - `grep -q '"red_streak": int(self.red_streak)' src/wanctl/queue_controller.py`
    - `grep -q '"max_delay_delta_us": int(self._last_max_delay_delta_us)' src/wanctl/queue_controller.py`
    - `grep -q '"headroom_exhausted_streak"' src/wanctl/queue_controller.py` (absorbed WARNING 4)
    - `grep -q '"anti_windup_cycles"' src/wanctl/queue_controller.py` (absorbed WARNING 4)
    - `grep -q '"anti_windup_triggers"' src/wanctl/queue_controller.py` (absorbed WARNING 6)
    - **REV 2 negative criterion**: `grep -E '"sustained_red_cycles"' src/wanctl/queue_controller.py | grep -v '^#' | wc -l` returns 0
    - `.venv/bin/pytest -o addopts='' tests/test_queue_controller.py::TestDocsisModeDiagnosticHealth -v` exits 0 with >= 11 tests passing
    - `.venv/bin/pytest -o addopts='' tests/test_queue_controller.py -q` exits 0 (no regression)
  </acceptance_criteria>
  <done>
    Six diagnostic fields (3 original + 3 absorbed from 201-14 rev 3) are computed/exposed via get_health_data() with getattr-tolerant fallbacks for the absorbed fields, and covered by a green test class. `sustained_red_cycles` is NOT serialized (rev 2). No existing test in test_queue_controller.py regresses.
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Pass six new fields through /health upload payload in health_check.py</name>
  <read_first>
    - src/wanctl/health_check.py (lines 295-345, the `_build_direction_section` upload extension block)
    - tests/test_health_check.py (find existing upload-payload tests; mirror their fixture pattern)
    - src/wanctl/queue_controller.py (verify Task 1 landed: get_health_data() now returns the six new fields)
  </read_first>
  <files>src/wanctl/health_check.py, tests/test_health_check.py</files>
  <behavior>
    - Test: GET /health response, when serialized, contains `wans[0].upload.max_delay_delta_us` as an int.
    - Test: GET /health response contains `wans[0].upload.red_streak` as an int.
    - Test: GET /health response contains `wans[0].upload.zone_trace` as a list of strings each in {"GREEN", "YELLOW", "RED"}.
    - Test: GET /health response contains `wans[0].upload.headroom_exhausted_streak` as an int (absorbed WARNING 4).
    - Test: GET /health response contains `wans[0].upload.anti_windup_cycles` as an int (absorbed WARNING 4).
    - Test: GET /health response contains `wans[0].upload.anti_windup_triggers` as an int counter (absorbed WARNING 6).
    - Test: Existing six Phase 201 fields (docsis_mode_active, setpoint_mbps, headroom_state, rtt_integral_ms_s, cake_aligned, floor_hit_cycles_total) are still present and have the same JSON types they had before this plan.
    - Test: When the controller is in legacy mode (docsis_mode=false), all six new fields are STILL present in the upload section (additive, not docsis_mode-gated).
    - **REV 2:** No `sustained_red_cycles` test in this plan.
  </behavior>
  <action>
    1. In `health_check.py`, find the `if direction == "upload":` block (around line 322) where `result.update({...})` adds the Phase 201 fields. Extend the SAME `result.update({...})` dict by adding six keys at the end of the dict literal:
       ```python
       # Original Plan 201-13 fields:
       "max_delay_delta_us": int(qc_health.get("max_delay_delta_us", 0)),
       "red_streak": int(qc_health.get("red_streak", 0)),
       "zone_trace": list(qc_health.get("zone_trace", [])),
       # Absorbed from Plan 201-14 WARNING 4 (control-model amendment counters; rev 2 drops sustained_red_cycles):
       "headroom_exhausted_streak": int(qc_health.get("headroom_exhausted_streak", 0)),
       "anti_windup_cycles": int(qc_health.get("anti_windup_cycles", 60)),
       # Absorbed from Plan 201-14 WARNING 6 (counter > log spam):
       "anti_windup_triggers": int(qc_health.get("anti_windup_triggers", 0)),
       ```
       Do NOT move or rename any existing entry. Do NOT add a docsis_mode-gated branch.

    2. Add a test class `TestPhase201DiagnosticHealthFields` to `tests/test_health_check.py`. It must cover all 8 behaviors above (down from 9 in rev 1). Use the existing health-builder fixture pattern from the file. Build one upload-section result for both `docsis_mode_active=true` and `docsis_mode_active=false`; assert all six new fields are present in BOTH.
  </action>
  <verify>
    <automated>.venv/bin/pytest -o addopts='' tests/test_health_check.py::TestPhase201DiagnosticHealthFields -v</automated>
    <automated>.venv/bin/pytest -o addopts='' tests/test_health_check.py -q --tb=short</automated>
    <automated>grep -nE '"max_delay_delta_us"|"red_streak"|"zone_trace"|"headroom_exhausted_streak"|"anti_windup_cycles"|"anti_windup_triggers"' src/wanctl/health_check.py | grep -v '^#' | wc -l | grep -qE '^[6-9]$|^1[0-9]$'</automated>
    <automated>grep -E '"sustained_red_cycles"' src/wanctl/health_check.py | grep -v '^#' | wc -l | grep -qE '^0$'</automated>
  </verify>
  <acceptance_criteria>
    - `grep -q '"max_delay_delta_us": int(qc_health.get("max_delay_delta_us"' src/wanctl/health_check.py`
    - `grep -q '"red_streak": int(qc_health.get("red_streak"' src/wanctl/health_check.py`
    - `grep -q '"zone_trace": list(qc_health.get("zone_trace"' src/wanctl/health_check.py`
    - `grep -q '"headroom_exhausted_streak": int(qc_health.get("headroom_exhausted_streak"' src/wanctl/health_check.py` (absorbed WARNING 4)
    - `grep -q '"anti_windup_cycles": int(qc_health.get("anti_windup_cycles"' src/wanctl/health_check.py` (absorbed WARNING 4)
    - `grep -q '"anti_windup_triggers": int(qc_health.get("anti_windup_triggers"' src/wanctl/health_check.py` (absorbed WARNING 6)
    - **REV 2 negative criterion**: `grep -E '"sustained_red_cycles"' src/wanctl/health_check.py | grep -v '^#' | wc -l` returns 0
    - `.venv/bin/pytest -o addopts='' tests/test_health_check.py::TestPhase201DiagnosticHealthFields -v` exits 0 with >= 8 tests passing
    - `.venv/bin/pytest -o addopts='' tests/test_health_check.py -q` exits 0 (no regression)
    - Hot-path regression slice still passes: `.venv/bin/pytest -o addopts='' tests/test_cake_signal.py tests/test_queue_controller.py tests/test_wan_controller.py tests/test_health_check.py -q` exits 0
  </acceptance_criteria>
  <done>
    /health upload payload exposes all six diagnostic fields under both docsis_mode and legacy mode; existing six Phase 201 fields unchanged; `sustained_red_cycles` NOT present (rev 2 coordination); no test regression.
  </done>
</task>

</tasks>

<verification>
After both tasks land, run the focused hot-path slice:
```
.venv/bin/pytest -o addopts='' tests/test_cake_signal.py tests/test_queue_controller.py tests/test_wan_controller.py tests/test_health_check.py -q
```
Must exit 0. Then ruff + mypy on touched files:
```
.venv/bin/ruff check src/wanctl/queue_controller.py src/wanctl/health_check.py tests/test_queue_controller.py tests/test_health_check.py
.venv/bin/mypy src/wanctl/queue_controller.py src/wanctl/health_check.py
```
</verification>

<success_criteria>
- /health.wans[0].upload contains 12 Phase 201 fields total (6 existing + 3 original new + 3 absorbed from 201-14 rev 3)
- All field types are JSON-serializable: int, str, list[str], float, bool, None
- No behavior change in QueueController
- `sustained_red_cycles` field is NOT present anywhere in the /health serialization path (rev 2 coordination with Plan 201-14 rev 3)
- Test count grows by >= 19 (>= 11 in test_queue_controller, >= 8 in test_health_check); test count does not shrink
- Hot-path slice passes
</success_criteria>

<output>
After completion, create `.planning/phases/201-docsis-aware-ul-congestion-control/201-13-SUMMARY.md` per the standard template. Note revision 2 in the summary header and confirm `sustained_red_cycles` is NOT serialized (coordinated with Plan 201-14 rev 3 codex Option B).
</output>
