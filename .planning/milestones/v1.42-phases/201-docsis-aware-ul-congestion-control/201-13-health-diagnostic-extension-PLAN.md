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
revision: 3  # Round-3 revision — closes codex 201-REVIEWS.md MEDIUM-CODEX-3 (active-knob proof in /health). Adds red_decay_step_pct + red_decay_delta_max_pct to the upload /health payload as runtime-state echoes (live constructor values, not config text) so canary preflight (Plan 201-15 rev 3) can grep /health for the two fields with non-zero values matching deployed YAML, proving live wiring rather than YAML presence alone.
revision_driver: "201-REVIEWS.md round 2 — closes MEDIUM-CODEX-3 (active knob proof for red_decay_step_pct + red_decay_delta_max_pct). Coordinates with Plan 201-15 rev 3 acceptance criteria that grep /health for these two fields."
requirements: [VALN-06]
tags: [phase-201, gap-closure, health-payload, observability, additive, codex-coordinated, codex-round-3]

must_haves:
  truths:
    - "/health.wans[0].upload exposes max_delay_delta_us as a numeric (int microseconds) additive field"
    - "/health.wans[0].upload exposes red_streak as a non-negative int additive field"
    - "/health.wans[0].upload exposes zone_trace as a list of the last N zone strings (RED/YELLOW/GREEN) — bounded ring buffer, default N=200 = 10s @ 20Hz"
    - "/health.wans[0].upload exposes headroom_exhausted_streak as a non-negative int additive field (Plan 201-14 control-model amendment counter; absorbed from Plan 201-14 WARNING 4)"
    - "/health.wans[0].upload exposes anti_windup_cycles as a non-negative int additive field (Plan 201-14 YAML config echo; absorbed from Plan 201-14 WARNING 4)"
    - "/health.wans[0].upload exposes anti_windup_triggers as a non-negative int counter (Plan 201-14 anti-windup engagement counter; absorbed from Plan 201-14 WARNING 6)"
    - "**REV 3 (codex MEDIUM-CODEX-3 closure):** /health.wans[0].upload exposes red_decay_step_pct as a float — runtime-state echo of the live QueueController constructor value (`self._red_decay_step_pct`), NOT a YAML text re-read. Default before Plan 201-14 lands: 0.02 (via getattr fallback)."
    - "**REV 3 (codex MEDIUM-CODEX-3 closure):** /health.wans[0].upload exposes red_decay_delta_max_pct as a float — runtime-state echo of the live QueueController constructor value (`self._red_decay_delta_max_pct`), NOT a YAML text re-read. Default before Plan 201-14 lands: 0.10 (via getattr fallback)."
    - "All EIGHT new fields are present-and-typed in legacy (docsis_mode=false) deployments — no link-type Python branching, no docsis_mode gating on the health payload (additive is global). Plan 201-14 owns the controller-side counter/knob increments; this plan owns serialization."
    - "Existing /health upload fields (docsis_mode_active, setpoint_mbps, headroom_state, rtt_integral_ms_s, cake_aligned, floor_hit_cycles_total) remain present and unchanged in shape (D-16 contract)"
    - "Zone trace is appended each cycle inside QueueController.adjust(); buffer write is O(1); no allocation on the hot path"
    - "**REVISION 2/3 — `sustained_red_cycles` is NOT serialized** (Plan 201-14 rev 4 deletes this knob entirely; Option B has no fall-through threshold by red_streak)"
  artifacts:
    - path: src/wanctl/queue_controller.py
      provides: "Ring-buffer zone_trace + max_delay_delta_us snapshot field; get_health_data() exports all eight new fields (3 from original spec + 3 absorbed from 201-14 WARNING 4/6 + 2 added in rev 3 for codex MEDIUM-CODEX-3 active-knob proof)"
      contains: "zone_trace"
    - path: src/wanctl/health_check.py
      provides: "Upload section serialization passes all eight new fields through"
      contains: "max_delay_delta_us"
  key_links:
    - from: "src/wanctl/queue_controller.py:adjust()"
      to: "self._zone_trace deque"
      via: "self._zone_trace.append(zone) at end of adjust()"
      pattern: "_zone_trace.append"
    - from: "src/wanctl/health_check.py:300-345 (upload result.update block)"
      to: "qc_health dict from get_health_data()"
      via: "result['max_delay_delta_us'] = qc_health.get('max_delay_delta_us'); result['red_decay_step_pct'] = qc_health.get('red_decay_step_pct'); result['red_decay_delta_max_pct'] = qc_health.get('red_decay_delta_max_pct'); result['anti_windup_triggers'] = qc_health.get('anti_windup_triggers')"
      pattern: "max_delay_delta_us|red_decay_step_pct|red_decay_delta_max_pct|anti_windup_triggers"
---

<objective>
**Gap-closure Plan 1 of 4. Revision 3 — closes codex MEDIUM-CODEX-3 from 201-REVIEWS.md round 2.** Lands FIRST so the control-model amendment (Plan 201-14 rev 4) is observable from the moment it ships, AND so Plan 201-15 rev 3's canary preflight can grep /health for `red_decay_step_pct` and `red_decay_delta_max_pct` to prove the rev-4 control knobs are live in the running constructor (not just present as text in `/etc/wanctl/spectrum.yaml`).

The 201-11 canary FAIL was diagnosed by inference (not direct evidence) because three diagnostic fields were absent from /health: `max_delay_delta_us`, `red_streak`, and a downsampled per-cycle zone trace. Per VERIFICATION.md gap "max_delay_delta_us is publicly serialized through /health for post-canary diagnosis": this is BLOCKING for VALN-06 closure.

**Round-3 absorption (codex MEDIUM-CODEX-3 — `201-REVIEWS.md` round 2):** Codex correctly observed that round-2 canary preflight grepped only the YAML for `red_decay_step_pct` / `red_decay_delta_max_pct`. YAML grep proves text presence, not that the running daemon's QueueController actually constructed with those values. The fix: surface both as runtime-state echoes in `/health.wans[].upload` (live `self._red_decay_step_pct` / `self._red_decay_delta_max_pct` values, not config re-read). Plan 201-15 rev 3 asserts these via `/health` with non-zero values matching the deployed YAML — this is the active-wiring proof.

**Why runtime-state semantics, not config echo:** Per Phase 200 RETRO lesson and CONTEXT D-16, `/health.wans[].{download,upload}` carries runtime state only — i.e., the value the controller is currently using. `red_decay_step_pct` and `red_decay_delta_max_pct` are not behavioral counters, they're constructor-time floats, but exposing the live attribute (not a re-parse of YAML) means a wiring failure (e.g., wan_controller.py constructor uses default instead of YAML value) would surface as default 0.02/0.10 in `/health` regardless of what's in `/etc/wanctl/spectrum.yaml`. That is the active-knob proof codex demanded.

**Revision absorption summary (cumulative across rev 2 → rev 3):**

This plan owns serialization of FIVE control-model amendment fields that Plan 201-14 introduces:
- `headroom_exhausted_streak` (cycle counter, increments per EXHAUSTED cycle, resets on AVAILABLE)
- `anti_windup_cycles` (YAML config echo for diagnostic correlation)
- `anti_windup_triggers` (counter, increments each time the anti-windup helper caps the integral)
- `red_decay_step_pct` (REV 3 — runtime-state echo of `self._red_decay_step_pct`, codex MEDIUM-CODEX-3)
- `red_decay_delta_max_pct` (REV 3 — runtime-state echo of `self._red_decay_delta_max_pct`, codex MEDIUM-CODEX-3)

Plus the original three rev-1 fields (`max_delay_delta_us`, `red_streak`, `zone_trace`).

**`sustained_red_cycles` REMAINS REMOVED** per Plan 201-14 rev 3 (now rev 4) Option B — the regime gate is on `current_rate` band, not on a fall-through threshold by red_streak. This plan rev 3 does NOT serialize it.

Output: EIGHT additive /health fields (3 original + 3 absorbed from 201-14 WARNING 4/6 + 2 new for codex MEDIUM-CODEX-3 active-knob proof), two test classes (one per file modified), no behavior change to the controller.

Purpose: post-deploy root-cause diagnosis of any future canary failure does not require re-running the canary with extra instrumentation. Active-knob proof for the rev-4 RED-decay parameters is a /health grep, not an SSH-into-prod-and-cat-yaml.
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
This plan ADDS eight more keys to the same dict.

`health_check.py:323-340` is where `direction == "upload"` extends `result` with the Phase 201 fields via `result.update({...})`. Add the eight new fields to the SAME `result.update({...})` block (additive, single statement).

`QueueController.adjust()` returns `(zone, new_rate, transition_reason)` and is called once per 50ms cycle from `wan_controller.py:3024`. The zone string is computed at line 161 (`self._classify_zone_3state(...)`) and is the value to append to the ring buffer.

Cake snapshot: `self._ul_cake_snapshot` is a `CakeSignalSnapshot` dataclass with `.max_delay_delta_us: int` (cake_signal.py:85-123). The upload QueueController already receives this via `cake_snapshot=` parameter to `adjust()` — store the latest value on the controller as `self._last_max_delay_delta_us` and serialize.

**Plan 201-14 rev 4 dependency for absorbed fields:** Plan 201-14 rev 4 (which lands AFTER this plan but tests for both must coexist) initializes FIVE controller attributes that this plan exports:
- `self._headroom_exhausted_streak: int = 0`
- `self._anti_windup_cycles: int = 60` (constructor param)
- `self._anti_windup_triggers: int = 0`
- `self._red_decay_step_pct: float = 0.02` (constructor param) — REV 3 active-knob field
- `self._red_decay_delta_max_pct: float = 0.10` (constructor param) — REV 3 active-knob field

Note: `self._sustained_red_cycles` is deleted in Plan 201-14 rev 4. This plan rev 3 also does not serialize it.

Since this plan lands BEFORE Plan 201-14 rev 4, the absorbed-field serialization in Task 1 step 3 must use `getattr(self, '_attr_name', default)` to be tolerant of pre-201-14 controller state. Once 201-14 lands, the attributes are always present.
</interfaces>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Add zone_trace ring buffer, red_streak passthrough, max_delay_delta_us snapshot, three absorbed 201-14 counters, AND two REV-3 active-knob floats (red_decay_step_pct, red_decay_delta_max_pct) to QueueController</name>
  <read_first>
    - src/wanctl/queue_controller.py (focus on __init__ lines 25-127, adjust() lines 128-176, get_health_data() lines 595-620)
    - src/wanctl/cake_signal.py (lines 85-123, CakeSignalSnapshot dataclass)
    - tests/test_queue_controller.py (look at TestDocsisModeIntegralClassifier and TestDocsisModeSetpointClamp at lines 3517-3600 for fixture patterns and `_make_docsis_controller` helper)
    - .planning/phases/201-docsis-aware-ul-congestion-control/201-VERIFICATION.md (gap-1 missing-items list)
    - .planning/phases/201-docsis-aware-ul-congestion-control/201-REVIEWS.md (round 2 — MEDIUM-CODEX-3 PARTIALLY-CLOSED active-knob proof requirement)
    - .planning/phases/201-docsis-aware-ul-congestion-control/201-14-control-model-amendment-PLAN.md (rev 4 — three absorbed-field constructor attributes + two new red_decay_*_pct floats; sustained_red_cycles is NOT one of them)
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
    - **Test (REV 3, codex MEDIUM-CODEX-3):** get_health_data() returns "red_decay_step_pct" as a float. Default before 201-14 lands: 0.02 (via getattr fallback). When the controller's `self._red_decay_step_pct` is set to 0.05 (e.g., via constructor), the field reports 0.05 — proves runtime-state echo, NOT a hard-coded literal.
    - **Test (REV 3, codex MEDIUM-CODEX-3):** get_health_data() returns "red_decay_delta_max_pct" as a float. Default before 201-14 lands: 0.10 (via getattr fallback). When the controller's `self._red_decay_delta_max_pct` is set to 0.15, the field reports 0.15 — same runtime-state echo proof.
    - **REV 2/3:** No `sustained_red_cycles` test — Plan 201-14 rev 4 deletes the knob entirely.
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

       NOTE: The five absorbed-field attributes (`_headroom_exhausted_streak`, `_anti_windup_cycles`, `_anti_windup_triggers`, `_red_decay_step_pct`, `_red_decay_delta_max_pct`) are NOT initialized in this plan — they are owned by Plan 201-14 rev 4. This plan exposes them via getattr-tolerant serialization in step 3.

    2. In `QueueController.adjust()`, AFTER the `zone = self._classify_zone_3state(...)` line (currently line 161) but BEFORE `self._compute_rate_3state(zone)`:
       ```python
       self._zone_trace.append(zone)
       if cake_snapshot is not None:
           self._last_max_delay_delta_us = int(cake_snapshot.max_delay_delta_us)
       ```
       Note: `self.red_streak` is already maintained inside `_classify_zone_3state` (lines 188, 198, 218, 224) — no new bookkeeping needed.

    3. In `QueueController.get_health_data()`, extend the returned dict with EIGHT new keys ALONGSIDE the existing Phase 201 block (around lines 611-619). Add INSIDE the same dict literal:
       ```python
       # Original Plan 201-13 fields (rev 1):
       "max_delay_delta_us": int(self._last_max_delay_delta_us),
       "red_streak": int(self.red_streak),
       "zone_trace": list(self._zone_trace),
       # Absorbed from Plan 201-14 rev 4 WARNING 4 (control-model amendment counters):
       # getattr fallback tolerates pre-201-14 controller state for wave-ordering safety.
       "headroom_exhausted_streak": int(getattr(self, "_headroom_exhausted_streak", 0)),
       "anti_windup_cycles": int(getattr(self, "_anti_windup_cycles", 60)),
       # Absorbed from Plan 201-14 rev 4 WARNING 6 (counter > log spam):
       "anti_windup_triggers": int(getattr(self, "_anti_windup_triggers", 0)),
       # REV 3 (codex MEDIUM-CODEX-3 active-knob proof) — runtime-state echoes,
       # NOT YAML re-reads. A wiring failure in wan_controller.py constructor would
       # surface here as the 0.02/0.10 default rather than the deployed YAML values,
       # which is exactly what the canary preflight grep is designed to detect.
       "red_decay_step_pct": float(getattr(self, "_red_decay_step_pct", 0.02)),
       "red_decay_delta_max_pct": float(getattr(self, "_red_decay_delta_max_pct", 0.10)),
       ```
       Keep all existing keys unchanged. **Do NOT add `sustained_red_cycles`** — Plan 201-14 rev 4 deletes that knob.

    4. Add a test class `TestDocsisModeDiagnosticHealth` to `tests/test_queue_controller.py` (place after `TestDocsisModeCakeCorroborator`). It must cover all 13 behaviors above (8 original + 3 absorbed + 2 REV-3 active-knob). For the five absorbed/active-knob field tests, the test must include BOTH styles:
       - **Default-fallback style:** controller fixture without setting the underlying `_attr_name`; asserts `get_health_data()` returns the documented default (0 / 60 / 0.02 / 0.10).
       - **Runtime-state-echo style:** set `controller._red_decay_step_pct = 0.05` (or `controller._red_decay_delta_max_pct = 0.15`) directly on the fixture; assert `get_health_data()["red_decay_step_pct"] == 0.05` (resp. 0.15). This is the core MEDIUM-CODEX-3 proof: the field tracks the controller attribute, not a constant.

    5. Hot-path budget: deque.append is O(1); `int(...)` on an int is a no-op; `float(...)` on a float is a no-op; the `list(self._zone_trace)` copy and five `getattr(...)` calls in get_health_data are OUTSIDE the 50ms hot path.
  </action>
  <verify>
    <automated>.venv/bin/pytest -o addopts='' tests/test_queue_controller.py::TestDocsisModeDiagnosticHealth -v</automated>
    <automated>.venv/bin/pytest -o addopts='' tests/test_queue_controller.py -q --tb=short</automated>
    <automated>grep -nE 'self\._zone_trace|self\._last_max_delay_delta_us' src/wanctl/queue_controller.py | grep -v '^#' | wc -l | tr -d '[:space:]' | grep -qE '^([5-9]|1[0-9])$'</automated>
    <automated>grep -E '"headroom_exhausted_streak"|"anti_windup_cycles"|"anti_windup_triggers"' src/wanctl/queue_controller.py | grep -v '^#' | wc -l | tr -d '[:space:]' | grep -qE '^[3-9]$'</automated>
    <automated>grep -E '"red_decay_step_pct"|"red_decay_delta_max_pct"' src/wanctl/queue_controller.py | grep -v '^#' | wc -l | tr -d '[:space:]' | grep -qE '^[2-9]$'</automated>
    <automated>grep -E '"sustained_red_cycles"' src/wanctl/queue_controller.py | grep -v '^#' | wc -l | tr -d '[:space:]' | grep -qE '^0$'</automated>
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
    - `grep -q '"red_decay_step_pct": float(getattr(self, "_red_decay_step_pct"' src/wanctl/queue_controller.py` (REV 3 active-knob, codex MEDIUM-CODEX-3)
    - `grep -q '"red_decay_delta_max_pct": float(getattr(self, "_red_decay_delta_max_pct"' src/wanctl/queue_controller.py` (REV 3 active-knob, codex MEDIUM-CODEX-3)
    - **REV 2/3 negative criterion**: `grep -E '"sustained_red_cycles"' src/wanctl/queue_controller.py | grep -v '^#' | wc -l` returns 0
    - `.venv/bin/pytest -o addopts='' tests/test_queue_controller.py::TestDocsisModeDiagnosticHealth -v` exits 0 with >= 13 tests passing
    - `.venv/bin/pytest -o addopts='' tests/test_queue_controller.py -q` exits 0 (no regression)
  </acceptance_criteria>
  <done>
    Eight diagnostic fields (3 original + 3 absorbed + 2 REV-3 active-knob) are computed/exposed via get_health_data() with getattr-tolerant fallbacks for the absorbed/active-knob fields, and covered by a green test class. `sustained_red_cycles` is NOT serialized. No existing test in test_queue_controller.py regresses.
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Pass eight new fields through /health upload payload in health_check.py (3 original + 3 absorbed + 2 REV-3 active-knob)</name>
  <read_first>
    - src/wanctl/health_check.py (lines 295-345, the `_build_direction_section` upload extension block)
    - tests/test_health_check.py (find existing upload-payload tests; mirror their fixture pattern)
    - src/wanctl/queue_controller.py (verify Task 1 landed: get_health_data() now returns the eight new fields)
    - .planning/phases/201-docsis-aware-ul-congestion-control/201-15-recanary-PLAN.md (rev 3 — Task 3 acceptance_criteria greps /health for red_decay_step_pct + red_decay_delta_max_pct; this task must wire those fields end-to-end so that grep succeeds)
  </read_first>
  <files>src/wanctl/health_check.py, tests/test_health_check.py</files>
  <behavior>
    - Test: GET /health response, when serialized, contains `wans[0].upload.max_delay_delta_us` as an int.
    - Test: GET /health response contains `wans[0].upload.red_streak` as an int.
    - Test: GET /health response contains `wans[0].upload.zone_trace` as a list of strings each in {"GREEN", "YELLOW", "RED"}.
    - Test: GET /health response contains `wans[0].upload.headroom_exhausted_streak` as an int (absorbed WARNING 4).
    - Test: GET /health response contains `wans[0].upload.anti_windup_cycles` as an int (absorbed WARNING 4).
    - Test: GET /health response contains `wans[0].upload.anti_windup_triggers` as an int counter (absorbed WARNING 6).
    - **Test (REV 3, codex MEDIUM-CODEX-3):** GET /health response contains `wans[0].upload.red_decay_step_pct` as a float.
    - **Test (REV 3, codex MEDIUM-CODEX-3):** GET /health response contains `wans[0].upload.red_decay_delta_max_pct` as a float.
    - Test: Existing six Phase 201 fields (docsis_mode_active, setpoint_mbps, headroom_state, rtt_integral_ms_s, cake_aligned, floor_hit_cycles_total) are still present and have the same JSON types they had before this plan.
    - Test: When the controller is in legacy mode (docsis_mode=false), all eight new fields are STILL present in the upload section (additive, not docsis_mode-gated).
    - **REV 2/3:** No `sustained_red_cycles` test in this plan.
  </behavior>
  <action>
    1. In `health_check.py`, find the `if direction == "upload":` block (around line 322) where `result.update({...})` adds the Phase 201 fields. Extend the SAME `result.update({...})` dict by adding eight keys at the end of the dict literal:
       ```python
       # Original Plan 201-13 fields (rev 1):
       "max_delay_delta_us": int(qc_health.get("max_delay_delta_us", 0)),
       "red_streak": int(qc_health.get("red_streak", 0)),
       "zone_trace": list(qc_health.get("zone_trace", [])),
       # Absorbed from Plan 201-14 rev 4 WARNING 4 (control-model amendment counters):
       "headroom_exhausted_streak": int(qc_health.get("headroom_exhausted_streak", 0)),
       "anti_windup_cycles": int(qc_health.get("anti_windup_cycles", 60)),
       # Absorbed from Plan 201-14 rev 4 WARNING 6 (counter > log spam):
       "anti_windup_triggers": int(qc_health.get("anti_windup_triggers", 0)),
       # REV 3 (codex MEDIUM-CODEX-3) — active-knob proof for Plan 201-15 rev 3 canary preflight:
       "red_decay_step_pct": float(qc_health.get("red_decay_step_pct", 0.02)),
       "red_decay_delta_max_pct": float(qc_health.get("red_decay_delta_max_pct", 0.10)),
       ```
       Do NOT move or rename any existing entry. Do NOT add a docsis_mode-gated branch.

    2. Add a test class `TestPhase201DiagnosticHealthFields` to `tests/test_health_check.py`. It must cover all 10 behaviors above (up from 8 in rev 2 because of two new active-knob fields). Use the existing health-builder fixture pattern from the file. Build one upload-section result for both `docsis_mode_active=true` and `docsis_mode_active=false`; assert all eight new fields are present in BOTH. For the two REV-3 active-knob fields, include a test that varies the underlying `qc_health` dict's `red_decay_step_pct` value (e.g., 0.03) and asserts the /health output reflects that value (proves passthrough, not a literal).
  </action>
  <verify>
    <automated>.venv/bin/pytest -o addopts='' tests/test_health_check.py::TestPhase201DiagnosticHealthFields -v</automated>
    <automated>.venv/bin/pytest -o addopts='' tests/test_health_check.py -q --tb=short</automated>
    <automated>grep -nE '"max_delay_delta_us"|"red_streak"|"zone_trace"|"headroom_exhausted_streak"|"anti_windup_cycles"|"anti_windup_triggers"|"red_decay_step_pct"|"red_decay_delta_max_pct"' src/wanctl/health_check.py | grep -v '^#' | wc -l | tr -d '[:space:]' | grep -qE '^([8-9]|1[0-9])$'</automated>
    <automated>grep -E '"sustained_red_cycles"' src/wanctl/health_check.py | grep -v '^#' | wc -l | tr -d '[:space:]' | grep -qE '^0$'</automated>
  </verify>
  <acceptance_criteria>
    - `grep -q '"max_delay_delta_us": int(qc_health.get("max_delay_delta_us"' src/wanctl/health_check.py`
    - `grep -q '"red_streak": int(qc_health.get("red_streak"' src/wanctl/health_check.py`
    - `grep -q '"zone_trace": list(qc_health.get("zone_trace"' src/wanctl/health_check.py`
    - `grep -q '"headroom_exhausted_streak": int(qc_health.get("headroom_exhausted_streak"' src/wanctl/health_check.py` (absorbed WARNING 4)
    - `grep -q '"anti_windup_cycles": int(qc_health.get("anti_windup_cycles"' src/wanctl/health_check.py` (absorbed WARNING 4)
    - `grep -q '"anti_windup_triggers": int(qc_health.get("anti_windup_triggers"' src/wanctl/health_check.py` (absorbed WARNING 6)
    - `grep -q '"red_decay_step_pct": float(qc_health.get("red_decay_step_pct"' src/wanctl/health_check.py` (REV 3, codex MEDIUM-CODEX-3)
    - `grep -q '"red_decay_delta_max_pct": float(qc_health.get("red_decay_delta_max_pct"' src/wanctl/health_check.py` (REV 3, codex MEDIUM-CODEX-3)
    - **REV 2/3 negative criterion**: `grep -E '"sustained_red_cycles"' src/wanctl/health_check.py | grep -v '^#' | wc -l` returns 0
    - `.venv/bin/pytest -o addopts='' tests/test_health_check.py::TestPhase201DiagnosticHealthFields -v` exits 0 with >= 10 tests passing
    - `.venv/bin/pytest -o addopts='' tests/test_health_check.py -q` exits 0 (no regression)
    - Hot-path regression slice still passes: `.venv/bin/pytest -o addopts='' tests/test_cake_signal.py tests/test_queue_controller.py tests/test_wan_controller.py tests/test_health_check.py -q` exits 0
  </acceptance_criteria>
  <done>
    /health upload payload exposes all eight diagnostic fields (3 original + 3 absorbed + 2 REV-3 active-knob) under both docsis_mode and legacy mode; existing six Phase 201 fields unchanged; `sustained_red_cycles` NOT present (rev 2/3 coordination); no test regression. Plan 201-15 rev 3 canary preflight grep target is wired end-to-end.
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
- /health.wans[0].upload contains 14 Phase 201 fields total (6 existing + 3 original new + 3 absorbed from 201-14 rev 4 + 2 REV-3 active-knob)
- All field types are JSON-serializable: int, str, list[str], float, bool, None
- No behavior change in QueueController
- `sustained_red_cycles` field is NOT present anywhere in the /health serialization path (rev 2/3 coordination with Plan 201-14 rev 4)
- `red_decay_step_pct` and `red_decay_delta_max_pct` are present in /health.wans[0].upload as floats (codex MEDIUM-CODEX-3 closed)
- Test count grows by >= 23 (>= 13 in test_queue_controller, >= 10 in test_health_check); test count does not shrink
- Hot-path slice passes
</success_criteria>

<output>
After completion, create `.planning/phases/201-docsis-aware-ul-congestion-control/201-13-SUMMARY.md` per the standard template. Note revision 3 in the summary header. Confirm the eight new fields land in /health upload payload, including the two REV-3 active-knob fields (`red_decay_step_pct`, `red_decay_delta_max_pct`) that close codex MEDIUM-CODEX-3. Confirm `sustained_red_cycles` is NOT serialized (coordinated with Plan 201-14 rev 4 codex Option B).
</output>
</content>
</invoke>