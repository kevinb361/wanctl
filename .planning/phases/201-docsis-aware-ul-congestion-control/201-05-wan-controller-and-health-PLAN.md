---
phase: 201-docsis-aware-ul-congestion-control
plan: 05
type: tdd
wave: 3
depends_on: [02, 03, 09, 04]
files_modified:
  - src/wanctl/wan_controller.py
  - tests/test_phase_195_replay.py
autonomous: true
requirements: [VALN-06]
tags: [phase-201, wave-3, wan-controller, health, additive, flash-wear, sigusr1]

must_haves:
  truths:
    - "WANController constructor passes the six new Phase 201 kwargs to the upload QueueController via getattr-with-default plumbing (D-17 byte-identity for non-DOCSIS YAMLs)"
    - "WANController records _docsis_mode_explicit and _setpoint_mbps_explicit presence flags from Config (D-03 presence-based mirror)"
    - "One-shot INFO log on docsis_mode opt-in uses self.logger (NOT module-scope logger — Phase 200 Plan 01 Task 2 silent-drop bug)"
    - "/health.wans[].upload gains SIX additive runtime-state fields (REVIEWS HIGH-5 added the 6th): docsis_mode_active, setpoint_mbps, headroom_state, rtt_integral_ms_s, cake_aligned, floor_hit_cycles_total (D-16)"
    - "/health additive fields are RUNTIME STATE (read from QueueController instance attributes), NOT YAML config echoes (Phase 200 RETRO Plan 05 bug 2)"
    - "REVIEWS LOW-1: setpoint_mbps reflects the active configured setpoint (self.upload._setpoint_bps), NOT the current rate"
    - "REVIEWS HIGH-5: floor_hit_cycles_total is the cycle-fidelity (50ms) VALN-06 evidence vector — read from self.upload.floor_hit_cycles, exposed for canary + soak counter-delta verdicts"
    - "SIGUSR1 reload scope (lines ~1894-1899) is UNCHANGED — Phase 201 keys are restart-required (D-08)"
    - "Setpoint clamp does NOT bypass last_applied_ul_rate flash-wear dedup (ARCH-05)"
  artifacts:
    - path: src/wanctl/wan_controller.py
      provides: "Upload QueueController constructor extension; presence flags; one-shot INFO log; /health additive fields"
      contains: "phase201 docsis_mode active"
  key_links:
    - from: "src/wanctl/wan_controller.py constructor"
      to: "src/wanctl/queue_controller.py QueueController.__init__ new kwargs"
      via: "getattr(config, 'docsis_mode', False) etc., passed as kwargs"
      pattern: "docsis_mode=getattr"
    - from: "src/wanctl/wan_controller.py:get_health_data (or equivalent)"
      to: "self.upload._docsis_mode / self.upload._setpoint_bps / self.upload._headroom_state etc."
      via: "runtime-state read from QueueController instance"
      pattern: "self.upload._headroom_state"
---

<objective>
Wave 3 follow-up to 201-04 (REVIEWS HIGH-2: depends_on now includes [04] because Plan 05 passes new kwargs to QueueController whose constructor only exists after Plan 04 lands; was a Wave 2 parallel-with-04 plan, now Wave 3 serial-after-04). Lands the WANController-level plumbing (constructor wiring, presence flags, one-shot INFO log, /health additive fields, **floor_hit_cycles_total runtime-state field per REVIEWS HIGH-5**).

Per Plan 201-02 Wave 0 contracts: TestPhase201HealthAdditive, TestPhase201FlashWear, and TestSigusr1ReloadScopePhase201 all turn GREEN at the end of this plan. Critically, the runtime-state-not-YAML-echo invariant (Phase 200 RETRO Plan 05 bug 2 + REVIEWS LOW-1) is enforced by reading from `self.upload._headroom_state` / `self.upload.floor_hit_cycles` etc. — NOT from `config.setpoint_mbps`.

**REVIEWS amendments (2026-05-04, see 201-REVIEWS.md):**
- **HIGH-2 (depends_on serialization):** moved from Wave 2 to Wave 3; depends_on adds Plan 04. Plan 04's QueueController surface (new kwargs + `floor_hit_cycles` attribute) MUST exist before this plan wires it. SAFE-05 rebasing in Plans 04 and 05 is now naturally serial (no parallel collision on `tests/test_phase_195_replay.py`).
- **HIGH-5 (floor-hit cycles counter exposure):** Plan 05-T2 adds a SIXTH additive `/health.wans[].upload` field — `floor_hit_cycles_total` (int, monotonic, runtime-state read from `self.upload.floor_hit_cycles`). Plans 11/12 verdict gates compare counter deltas across loaded windows.
- **LOW-1 (setpoint_mbps semantics):** Plan 05-T2 docstrings clarify that `setpoint_mbps` is the *active configured setpoint* (read from `self.upload._setpoint_bps`), NOT the *current rate*. Tests should assert `current_rate != setpoint_mbps under load` as a positive invariant.
- **HIGH-3 (stub removal):** acceptance criterion at the plan level — `grep -c 'Wave 0 stub' tests/test_wan_controller.py` returns 0 for Phase 201 stubs after Plan 05 completes.

Output: wan_controller.py extended with constructor wiring + INFO log + **6 additive /health fields (was 5; +floor_hit_cycles_total)**; SAFE-05 v1.42 pins re-baselined for the wan_controller surface.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/phases/201-docsis-aware-ul-congestion-control/201-CONTEXT.md
@.planning/phases/201-docsis-aware-ul-congestion-control/201-RESEARCH.md
@.planning/phases/201-docsis-aware-ul-congestion-control/201-PATTERNS.md
@.planning/phases/201-docsis-aware-ul-congestion-control/201-03-SUMMARY.md
@src/wanctl/wan_controller.py
</context>

<interfaces>
<!-- Existing pattern shapes (PATTERNS.md verbatim excerpts). -->

Site 1 — Upload QueueController constructor (wan_controller.py:402-418).
Existing kwargs end with `consecutive_yellow_decay_clamp=getattr(config, "upload_consecutive_yellow_decay_clamp", 0)`.
Phase 201 appends six new kwargs using `getattr(config, "<key>", <default>)` pattern.

Site 2 — Per-key explicit-presence flags + INFO log (wan_controller.py:432-452).
Existing: `self._upload_target_bloat_ms_explicit = getattr(config, "_upload_target_bloat_ms_explicit", False)` and similar.
Phase 201 mirror: `self._docsis_mode_explicit = getattr(config, "_docsis_mode_explicit", False)` and `self._setpoint_mbps_explicit`.
INFO log MUST use `self.logger` (NOT `logger`/`logging.getLogger(__name__)`).

Site 3 — UL adjust call (wan_controller.py:2977-2984). DO NOT change the call signature; ARB-04 regex pin in test_phase_195_replay.py:629-640 enforces this.

Site 4 — /health upload payload (~line 4490-4530, where `cake_signal.upload` is built).
Phase 201 additive fields are placed under `.wans[].upload.*` (NOT under `cake_signal.upload`).
The actual integration point is the existing function/method that builds the per-WAN `upload` dict for /health output — locate via grep for `"upload"` in wan_controller.py.

Site 5 — SIGUSR1 reload scope (wan_controller.py:1894-1899). DO NOT TOUCH. Phase 201 keys are NOT live-tunable (D-08).
</interfaces>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Wire upload QueueController constructor + presence flags + one-shot INFO log</name>
  <files>src/wanctl/wan_controller.py</files>
  <read_first>
    - src/wanctl/wan_controller.py — locate via grep before reading: `grep -n "self.upload = QueueController\\|_upload_target_bloat_ms_explicit\\|self.logger.info.*upload\\|consecutive_yellow_decay_clamp=getattr" src/wanctl/wan_controller.py | head -20`
    - Then targeted reads of the constructor block (around lines 390-460), the presence-flag block (around 426-452), and the SIGUSR1 reload site (1894-1899) to confirm boundary.
    - .planning/phases/201-docsis-aware-ul-congestion-control/201-PATTERNS.md section "src/wanctl/wan_controller.py (controller / orchestrator — modify)" — Site 1 + Site 2 verbatim
    - tests/test_wan_controller.py — TestSigusr1ReloadScopePhase201 (the contract for "must NOT touch SIGUSR1 reload")
    - .planning/phases/200-per-direction-rtt-bloat-thresholds/200-RETRO.md — search for "Plan 01 Task 2" / "logger silent-drop" (the bug pattern this task must avoid)
  </read_first>
  <behavior>
    - Upload QueueController constructor receives six new kwargs via `getattr(config, "<key>", <default>)`. Defaults exactly match Plan 201-04 QueueController defaults.
    - Special handling for `setpoint_bps`: `int(config.setpoint_mbps * 1_000_000) if getattr(config, "_setpoint_mbps_explicit", False) else None` — the constructor receives the BPS form when the key was explicitly set, else None (controller's setpoint clamp gates on `is None` / `is not None`).
    - Two new presence flags stored on WANController: `self._docsis_mode_explicit` and `self._setpoint_mbps_explicit`.
    - One-shot INFO log emitted via `self.logger.info(...)` ONLY when `self._docsis_mode_explicit and getattr(config, "docsis_mode", False)`.
    - SIGUSR1 reload site is NOT modified (verified by acceptance grep).
  </behavior>
  <action>
First locate the exact constructor call:
```bash
grep -n 'self.upload = QueueController' src/wanctl/wan_controller.py
grep -n '_upload_target_bloat_ms_explicit' src/wanctl/wan_controller.py
grep -n 'def _reload_runtime_config\\|sigusr\\|signal.SIGUSR1' src/wanctl/wan_controller.py
```

Read the constructor body around the `self.upload = QueueController(` line. Note the current closing `)` line number — the new kwargs append BEFORE that closing paren.

Append to the upload constructor call (after the existing last kwarg, before the closing `)`):

```python
            consecutive_yellow_decay_clamp=getattr(
                config, "upload_consecutive_yellow_decay_clamp", 0
            ),
            # Phase 201 (DOCSIS-aware UL control mode) — getattr with safe
            # defaults so legacy YAMLs with no Phase 201 keys are byte-identical
            # (D-17). setpoint_bps is the BPS conversion of setpoint_mbps,
            # gated by the per-key explicit-presence flag (D-03).
            docsis_mode=getattr(config, "docsis_mode", False),
            setpoint_bps=(
                int(config.setpoint_mbps * 1_000_000)
                if getattr(config, "_setpoint_mbps_explicit", False)
                else None
            ),
            integral_window_seconds=getattr(config, "integral_window_seconds", 2.0),
            integral_threshold_ms_s=getattr(config, "integral_threshold_ms_s", 30.0),
            cake_backlog_low_threshold_bytes=getattr(
                config, "cake_backlog_low_threshold_bytes", 5000
            ),
            cake_delay_delta_low_threshold_us=getattr(
                config, "cake_delay_delta_low_threshold_us", 5000
            ),
        )
```

After the existing `_upload_warn_bloat_ms_explicit` line (or wherever Phase 200 D-03 flags live), append:

```python
        # Phase 201 D-03 mirror: presence-based per-key flags. NEVER value-derived.
        # Codex pre-review caught the value-derived flag regression in Phase 200.
        self._docsis_mode_explicit = getattr(config, "_docsis_mode_explicit", False)
        self._setpoint_mbps_explicit = getattr(config, "_setpoint_mbps_explicit", False)
        # One-shot INFO log when operator opts into DOCSIS-mode. MUST use
        # self.logger (per-WAN configured logger). Phase 200 Plan 01 Task 2:
        # logging.getLogger(__name__) silently drops in production.
        if self._docsis_mode_explicit and getattr(config, "docsis_mode", False):
            self.logger.info(
                "phase201 docsis_mode active: setpoint_mbps=%s window_s=%s threshold_ms_s=%s",
                getattr(config, "setpoint_mbps", None),
                getattr(config, "integral_window_seconds", 2.0),
                getattr(config, "integral_threshold_ms_s", 30.0),
            )
```

Anti-pattern reminder (do NOT do):
- `logging.getLogger(__name__).info(...)` — silent drop in production.
- `self._docsis_mode_explicit = config.docsis_mode != False` — value-derived; Codex pre-review catch.
- Modifying the SIGUSR1 reload block at lines ~1894-1899 — D-08 keeps it narrow.

Critically, the upload constructor's existing `consecutive_yellow_decay_clamp` getattr line stays — only ADD the six new kwargs after it. Verify with diff that no existing kwarg was reordered or removed.
  </action>
  <acceptance_criteria>
    - `grep -c "docsis_mode=getattr" src/wanctl/wan_controller.py` returns 1.
    - `grep -c "setpoint_bps=" src/wanctl/wan_controller.py` returns 1.
    - `grep -c "integral_window_seconds=getattr" src/wanctl/wan_controller.py` returns 1.
    - `grep -c "cake_backlog_low_threshold_bytes=getattr" src/wanctl/wan_controller.py` returns 1.
    - `grep -c "self._docsis_mode_explicit" src/wanctl/wan_controller.py` returns >= 1.
    - `grep -c "self._setpoint_mbps_explicit" src/wanctl/wan_controller.py` returns >= 1.
    - `grep -c "phase201 docsis_mode active" src/wanctl/wan_controller.py` returns 1.
    - `grep -c "self.logger.info" src/wanctl/wan_controller.py` returns >= 1 (NOT `logger.info` module-scope; verify via `grep -E '^[^#]*[^.]logger\\.info\\(.*phase201' src/wanctl/wan_controller.py | wc -l` returns 0).
    - `grep -c "logging.getLogger(__name__).info" src/wanctl/wan_controller.py` is unchanged from pre-task baseline (acceptable to have legacy occurrences elsewhere; this task adds NONE).
    - SIGUSR1 reload site is unchanged: `git diff src/wanctl/wan_controller.py | grep -E '^[+-]' | grep -E 'sigusr|SIGUSR1|_reload_runtime_config' | grep -v '^[+-]{3}'` returns empty.
    - TestSigusr1ReloadScopePhase201 passes: `.venv/bin/pytest -o addopts='' tests/test_wan_controller.py -q -k TestSigusr1ReloadScopePhase201` returns 0.
    - Hot-path slice green: `.venv/bin/pytest -o addopts='' tests/test_cake_signal.py tests/test_queue_controller.py tests/test_wan_controller.py tests/test_health_check.py -q` returns 0.
    - `.venv/bin/ruff check src/wanctl/wan_controller.py` returns 0.
  </acceptance_criteria>
  <verify>
    <automated>.venv/bin/pytest -o addopts='' tests/test_wan_controller.py -q -k 'TestSigusr1ReloadScopePhase201' &amp;&amp; .venv/bin/pytest -o addopts='' tests/test_cake_signal.py tests/test_queue_controller.py tests/test_health_check.py -q &amp;&amp; .venv/bin/ruff check src/wanctl/wan_controller.py</automated>
  </verify>
  <done>Constructor wired with six new kwargs; presence flags landed; one-shot INFO log uses self.logger; SIGUSR1 unchanged; static checks clean.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Add five additive /health runtime-state fields under .wans[].upload</name>
  <files>src/wanctl/wan_controller.py, tests/test_phase_195_replay.py</files>
  <read_first>
    - src/wanctl/wan_controller.py — locate via grep: `grep -n '"upload":\\|self._ul_cake_snapshot\\|def get_health\\|def _build_health\\|def _wan_health' src/wanctl/wan_controller.py | head -20`
    - Then targeted read of the /health upload-block construction site (PATTERNS.md cites around line 4490-4530)
    - tests/test_wan_controller.py — TestPhase201HealthAdditive (the contract)
    - tests/test_wan_controller.py — TestPhase201FlashWear (the regression gate)
    - .planning/phases/200-per-direction-rtt-bloat-thresholds/200-RETRO.md — search "Plan 05 bug 2" / "floor_mbps/ceiling_mbps field assumption" (the bug pattern to avoid)
  </read_first>
  <behavior>
    - The per-WAN /health builder produces a dict for `.wans[].upload`. Phase 201 adds SIX new keys to that dict:
        "docsis_mode_active": self.upload._docsis_mode (bool — runtime, mirror of config but fed through controller instance)
        "setpoint_mbps": (self.upload._setpoint_bps / 1_000_000) if self.upload._setpoint_bps else None  # runtime, in Mbit — REVIEWS LOW-1: active configured setpoint, NOT current_rate
        "headroom_state": self.upload._headroom_state  # str AVAILABLE|EXHAUSTED — runtime state machine
        "rtt_integral_ms_s": round(self.upload._last_integral_ms_s, 3)  # runtime accumulator
        "cake_aligned": self.upload._cake_aligned  # bool — runtime corroborator state
        "floor_hit_cycles_total": int(self.upload.floor_hit_cycles)  # REVIEWS HIGH-5: monotonic counter, daemon-lifetime
    - All six fields are READ from the QueueController instance, not from the Config object. This ensures runtime-state semantics (Phase 200 RETRO Plan 05 bug 2 trap + REVIEWS LOW-1).
    - The existing `.wans[].upload` keys (current_rate_mbps, state, state_reason, hysteresis) are UNCHANGED.
    - SAFE-05 v1.42 pins are re-baselined to absorb new occurrences in wan_controller.py.
  </behavior>
  <action>
First locate the /health upload-block builder. Likely in a method like `get_health_data` or `_build_wan_health` or inline in a larger health builder. Run:

```bash
grep -n '"current_rate_mbps":\\|"state":.*self.upload\\|"hysteresis":' src/wanctl/wan_controller.py | head -20
```

Read that section. The integration point is the dict literal that produces the upload sub-dict for the WAN's health payload.

Add the five new keys to that dict literal. Place them AFTER the existing keys to make the addition append-only:

```python
        upload_health = {
            "current_rate_mbps": ...,           # existing — unchanged
            "state": ...,                        # existing — unchanged
            "state_reason": ...,                 # existing — unchanged
            "hysteresis": ...,                   # existing — unchanged
            # Phase 201 additive runtime-state fields (D-16). All values are
            # READ FROM THE CONTROLLER INSTANCE, not from config — runtime
            # semantics, never YAML echo (Phase 200 RETRO Plan 05 bug 2).
            "docsis_mode_active": bool(self.upload._docsis_mode),
            "setpoint_mbps": (
                (self.upload._setpoint_bps / 1_000_000)
                if getattr(self.upload, "_setpoint_bps", None) else None
            ),
            "headroom_state": getattr(self.upload, "_headroom_state", "EXHAUSTED"),
            "rtt_integral_ms_s": round(
                getattr(self.upload, "_last_integral_ms_s", 0.0), 3
            ),
            "cake_aligned": bool(getattr(self.upload, "_cake_aligned", False)),
            # REVIEWS HIGH-5 (2026-05-04): cycle-fidelity floor-hit counter
            # exposed for canary + soak counter-delta verdicts.
            # Counter is monotonic per daemon lifetime — Plans 11/12 read
            # the value at start-of-loaded-window and end-of-loaded-window
            # and compare deltas (delta == 0 is the VALN-06 PASS condition).
            "floor_hit_cycles_total": int(getattr(self.upload, "floor_hit_cycles", 0)),
        }
```

The exact dict-literal layout depends on the file's existing style; locate the actual literal during the read pass and adapt the diff to fit. Preserve key order of existing fields; new keys go at the end of the literal.

Anti-pattern reminder (do NOT do):
- `"setpoint_mbps": config.setpoint_mbps` — that's a YAML echo (Phase 200 RETRO Plan 05 bug 2).
- `"docsis_mode": ...` (without `_active` suffix) — could be confused with the YAML key. Use `docsis_mode_active` for runtime distinction.
- Modifying the existing keys (`current_rate_mbps`, etc.) — D-16 is additive only.

After the dict-literal edit, re-run the SAFE-05 v1.42 baseline check. Phase 201 keys (`docsis_mode`, `setpoint_mbps`, `integral_window_seconds`, `integral_threshold_ms_s`, `cake_backlog_low_threshold_bytes`, `cake_delay_delta_low_threshold_us`) now have additional occurrences in wan_controller.py. Update the `expected_counts` dict in `tests/test_phase_195_replay.py` to match. Add an inline comment near the new pins:

```python
# v1.42 baseline (Plan 201-05 wave-2 partner): Phase 201 keys gain
# additional occurrences in wan_controller.py constructor wiring + /health
# additive fields. Plan 201-04 already bumped for queue_controller.py
# surface; this is the second bump for the wan_controller surface.
```
  </action>
  <acceptance_criteria>
    - `grep -c '"docsis_mode_active":' src/wanctl/wan_controller.py` returns 1.
    - `grep -c '"headroom_state":' src/wanctl/wan_controller.py` returns 1.
    - `grep -c '"rtt_integral_ms_s":' src/wanctl/wan_controller.py` returns 1.
    - `grep -c '"cake_aligned":' src/wanctl/wan_controller.py` returns 1.
    - `grep -c '"setpoint_mbps":' src/wanctl/wan_controller.py` returns 1.
    - **REVIEWS HIGH-5:** `grep -c '"floor_hit_cycles_total":' src/wanctl/wan_controller.py` returns 1.
    - **REVIEWS HIGH-5:** `grep -c "self.upload.floor_hit_cycles\|getattr(self.upload, .floor_hit_cycles" src/wanctl/wan_controller.py` returns >= 1 (runtime-state read).
    - **REVIEWS HIGH-3 (stub removal):** `grep -c 'Wave 0 stub' tests/test_wan_controller.py 2>/dev/null` returns 0 for any test class touched by this plan (every implemented stub has its xfail/fail decorator removed in this commit).
    - `grep -v '^#\\|^ *#' src/wanctl/wan_controller.py | grep -c 'config.setpoint_mbps' | awk '{print $1}'` shows occurrences of `config.setpoint_mbps` are bounded — new /health code MUST NOT use `config.setpoint_mbps` directly (it must read from `self.upload._setpoint_bps`). Specifically: `grep -v '^#' src/wanctl/wan_controller.py | grep -A 0 '"setpoint_mbps":' | grep -c 'config.setpoint_mbps'` returns 0.
    - TestPhase201HealthAdditive passes: `.venv/bin/pytest -o addopts='' tests/test_wan_controller.py -q -k TestPhase201HealthAdditive` returns 0.
    - TestPhase201FlashWear passes: `.venv/bin/pytest -o addopts='' tests/test_wan_controller.py -q -k TestPhase201FlashWear` returns 0.
    - SAFE-05 v1.42 pins green: `.venv/bin/pytest -o addopts='' tests/test_phase_195_replay.py::test_safe05_threshold_name_counts_are_unchanged -v` returns 0.
    - Full hot-path slice green: `.venv/bin/pytest -o addopts='' tests/test_cake_signal.py tests/test_queue_controller.py tests/test_wan_controller.py tests/test_health_check.py -q` returns 0.
    - Full Phase 201 unit + replay slice green: `.venv/bin/pytest -o addopts='' tests/test_queue_controller.py tests/test_wan_controller.py tests/test_autorate_config.py tests/test_check_config.py tests/test_phase_201_replay.py tests/test_phase_195_replay.py tests/test_phase_197_replay.py -q` returns 0.
    - `.venv/bin/ruff check src/wanctl/wan_controller.py` returns 0.
  </acceptance_criteria>
  <verify>
    <automated>.venv/bin/pytest -o addopts='' tests/test_queue_controller.py tests/test_wan_controller.py tests/test_autorate_config.py tests/test_check_config.py tests/test_phase_201_replay.py tests/test_phase_195_replay.py tests/test_phase_197_replay.py tests/test_health_check.py tests/test_cake_signal.py -q &amp;&amp; .venv/bin/ruff check src/wanctl/wan_controller.py</automated>
  </verify>
  <done>Five additive /health fields live; runtime-state semantics enforced (no config-echo); flash-wear regression gate green; SAFE-05 v1.42 baseline absorbs the wan_controller surface increase.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| /health endpoint → downstream consumers (operator-summary, dashboard, monitoring) | New fields are additive; no shape change to existing keys. Consumers that read only existing keys are unaffected (D-16). |
| Config object → WANController constructor | Constructor uses `getattr(config, "<key>", <default>)` so a Config without Phase 201 attributes (legacy build) cannot crash construction. Forward-compat hedge against test-time mocks. |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-201-18 | Tampering | /health field is a YAML echo not runtime state (Phase 200 Plan 05 bug 2 family) | mitigate | All five new fields are READ from `self.upload.*` instance attributes; TestPhase201HealthAdditive::test_setpoint_mbps_runtime_field_reflects_state_not_yaml asserts the runtime-vs-config distinction. |
| T-201-19 | Repudiation | One-shot INFO log silently drops (Phase 200 Plan 01 Task 2 bug) | mitigate | INFO uses `self.logger`; acceptance grep ensures module-scope `logger.info(...phase201...)` does not exist. |
| T-201-20 | Tampering | SIGUSR1 reload silently extends to docsis_mode/setpoint_mbps (D-08 violation) | mitigate | Acceptance gate: SIGUSR1 reload site git diff is empty for this plan; TestSigusr1ReloadScopePhase201 asserts no live-tunable behavior. |
| T-201-21 | DoS | /health payload size grows unbounded | accept | Five scalar fields per WAN; <100 bytes per WAN; 2 WANs = trivial growth. ASVS V13. |
| T-201-22 | Information Disclosure | Runtime-state fields expose internal control state to operators reading /health | accept | /health is operator-facing by design; new fields are diagnostic, not sensitive (no PII, no secrets). |
| T-201-23 | DoS to router | Setpoint clamp triggers excess router writes (flash-wear regression) | mitigate | TestPhase201FlashWear::test_steady_state_no_router_writes_when_rate_unchanged asserts last_applied_ul_rate dedup is intact. Plan 201-05 does NOT touch the router-write layer. |
</threat_model>

<verification>
- TestSigusr1ReloadScopePhase201 + TestPhase201HealthAdditive + TestPhase201FlashWear all green.
- Phase 195 replay (SAFE-05) green with v1.42 pins.
- Phase 197 replay (regression gate) green.
- Hot-path slice + full unit slice green.
- Static checks clean.
- SIGUSR1 reload site bytes-identical (git diff confirmation).
</verification>

<success_criteria>
- WANController upload constructor receives six new Phase 201 kwargs via getattr-with-default.
- Per-key explicit-presence flags presence-based (D-03).
- One-shot INFO log uses self.logger (D-06 + Phase 200 Plan 01 lesson).
- /health adds five additive runtime-state fields under .wans[].upload (D-16 + Phase 200 RETRO Plan 05 lesson).
- D-08 invariant preserved (SIGUSR1 reload scope unchanged).
- ARCH-05 invariant preserved (flash-wear dedup intact).
</success_criteria>

<output>
After completion, create `.planning/phases/201-docsis-aware-ul-congestion-control/201-05-SUMMARY.md` listing: lines added in wan_controller.py, the five new /health field paths, SAFE-05 v1.42 final pin counts, and a one-line confirmation that SIGUSR1 reload diff is empty.
</output>
