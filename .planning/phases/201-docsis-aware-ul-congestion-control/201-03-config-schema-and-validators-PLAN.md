---
phase: 201-docsis-aware-ul-congestion-control
plan: 03
type: tdd
wave: 1
depends_on: [02]
files_modified:
  - src/wanctl/autorate_config.py
  - src/wanctl/check_config_validators.py
  - tests/test_phase_195_replay.py
autonomous: true
requirements: [VALN-06]
tags: [phase-201, wave-1, config, schema, safe-06, safe-05]

must_haves:
  truths:
    - "All six new YAML keys (docsis_mode, setpoint_mbps, integral_window_seconds, integral_threshold_ms_s, cake_backlog_low_threshold_bytes, cake_delay_delta_low_threshold_us) are registered in KNOWN_AUTORATE_PATHS so SAFE-06 emits zero unknown-key warnings on production startup"
    - "Per-key explicit-presence flags are presence-based (D-03 Codex catch); never value-derived"
    - "Validator fails closed (Severity.ERROR) when docsis_mode=true and setpoint_mbps absent"
    - "Validator fails closed (Severity.ERROR) when setpoint_mbps does NOT satisfy floor_mbps < setpoint_mbps < ceiling_mbps strict ordering"
    - "Legacy YAML (no docsis_mode key) produces byte-identical Config object — schema additions do NOT change defaults of existing fields"
    - "SAFE-05 v1.42 baseline counts re-established in test_phase_195_replay.py with docsis_mode/setpoint_mbps occurrence pins"
  artifacts:
    - path: src/wanctl/autorate_config.py
      provides: "Six new schema entries; six new instance attributes; six new presence flags; required-when-other validation for setpoint_mbps; ordering validation for floor < setpoint < ceiling"
      contains: "docsis_mode"
    - path: src/wanctl/check_config_validators.py
      provides: "Six new entries in KNOWN_AUTORATE_PATHS; new _validate_docsis_mode_setpoint() function plugged into the validator chain"
      contains: "_validate_docsis_mode_setpoint"
    - path: tests/test_phase_195_replay.py
      provides: "SAFE-05 baseline counts updated for v1.42 (Phase 201 keys added; rejected v1.41 occurrences unchanged)"
      contains: "docsis_mode"
  key_links:
    - from: "src/wanctl/check_config_validators.py"
      to: "src/wanctl/autorate_config.py"
      via: "schema-key registration mirrors autorate_config SCHEMA paths"
      pattern: "continuous_monitoring\\.upload\\.docsis_mode"
    - from: "src/wanctl/autorate_config.py:_validate raises"
      to: "tests/test_autorate_config.py::TestPhase201Schema"
      via: "ValueError raised from Config.__init__"
      pattern: "docsis_mode.*requires setpoint_mbps"
---

<objective>
Wave 1 schema layer. Lands the YAML-key surface and validator wiring for Phase 201's six new keys before any controller-internal code runs. Per Plan 201-02 Wave 0 contracts, this plan satisfies `TestPhase201Schema`, `TestSafe06Phase201KeysKnown`, and `TestDocsisModeValidation` end-to-end.

This plan is the SAFE-06 + D-06 + D-03 (Codex catch) gate. After this lands, ANY production YAML that includes these new keys is parsed correctly, validated, and reports presence flags upward. Without this, Plan 201-04 cannot wire the controller because it has no Config attributes to read.

Output: Updated config + validator modules; updated SAFE-05 baseline test; previously-failing Wave 0 schema tests now GREEN.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/phases/201-docsis-aware-ul-congestion-control/201-CONTEXT.md
@.planning/phases/201-docsis-aware-ul-congestion-control/201-RESEARCH.md
@.planning/phases/201-docsis-aware-ul-congestion-control/201-PATTERNS.md
@.planning/phases/201-docsis-aware-ul-congestion-control/201-02-SUMMARY.md
@src/wanctl/autorate_config.py
@src/wanctl/check_config_validators.py
</context>

<interfaces>
<!-- Existing patterns to mirror EXACTLY (excerpts from PATTERNS.md). -->

Existing schema entry shape (autorate_config.py lines 182-194):
```python
{
    "path": "continuous_monitoring.upload.target_bloat_ms",
    "type": (int, float),
    "required": False,
    "min": 1,
    "max": 200,
},
```

Existing per-key presence-flag pattern (autorate_config.py lines 371-379):
```python
self._upload_target_bloat_ms_raw = ul.get("target_bloat_ms")
self._upload_warn_bloat_ms_raw = ul.get("warn_bloat_ms")
self._upload_target_bloat_ms_explicit = "target_bloat_ms" in ul
self._upload_warn_bloat_ms_explicit = "warn_bloat_ms" in ul
```

Existing required-when-other raise (autorate_config.py lines 429-438) — mirror for `setpoint_mbps`.

Existing cross-field validator (check_config_validators.py:408-453, `_validate_upload_threshold_ordering`) — mirror for `_validate_docsis_mode_setpoint`.

Existing KNOWN_AUTORATE_PATHS UL block (check_config_validators.py:62-77) — append six new lines.
</interfaces>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Land schema entries, presence flags, and required-when-other validation in autorate_config.py</name>
  <files>src/wanctl/autorate_config.py</files>
  <read_first>
    - src/wanctl/autorate_config.py (full file via grep landmarks first: locate the SCHEMA list, the upload-block parsing section, and the existing validation raise; then targeted reads)
    - tests/test_autorate_config.py — TestPhase201Schema (the contract this task must satisfy)
    - .planning/phases/201-docsis-aware-ul-congestion-control/201-PATTERNS.md section "src/wanctl/autorate_config.py (config / schema — modify)"
  </read_first>
  <behavior>
    - SCHEMA gains exactly six entries (paths listed in interfaces); type/min/max per RESEARCH §recommended structure; `required: False` for all (D-06 enforces required-when-other in code, not schema).
    - Config.__init__ reads:
        self.docsis_mode = ul.get("docsis_mode", False)
        self.setpoint_mbps = ul.get("setpoint_mbps")
        self.integral_window_seconds = ul.get("integral_window_seconds", 2.0)
        self.integral_threshold_ms_s = ul.get("integral_threshold_ms_s", 30.0)
        self.cake_backlog_low_threshold_bytes = ul.get("cake_backlog_low_threshold_bytes", 5000)
        self.cake_delay_delta_low_threshold_us = ul.get("cake_delay_delta_low_threshold_us", 5000)
    - Each gets a `_<name>_explicit = "<name>" in ul` companion (presence-based).
    - Validation raises ValueError if `docsis_mode is True and setpoint_mbps is None` with message containing "docsis_mode" and "requires setpoint_mbps".
    - Validation raises ValueError if `docsis_mode is True and setpoint_mbps is not None` and NOT `(upload_floor_red_bps < setpoint_bps < upload_ceiling_bps)`. Message references "floor_mbps", "setpoint_mbps", "ceiling_mbps".
    - Defaults preserve byte-identical legacy: `docsis_mode=False` is the absent-key fallback; ALL existing Config attributes unchanged.
  </behavior>
  <action>
First grep the file structure:
```bash
grep -n "continuous_monitoring.upload.target_bloat_ms\|_upload_target_bloat_ms_explicit\|requires.*upload\|raise ValueError" src/wanctl/autorate_config.py
```

Then read the SCHEMA block, the upload parse block (around line 355-379), and the existing validation raise (around line 429-438). Determine exact MBPS_TO_BPS or `* 1_000_000` literal used.

In the SCHEMA list, immediately AFTER the `continuous_monitoring.upload.warn_bloat_ms` entry, insert six new entries verbatim:

```python
{
    "path": "continuous_monitoring.upload.docsis_mode",
    "type": bool,
    "required": False,
},
{
    "path": "continuous_monitoring.upload.setpoint_mbps",
    "type": (int, float),
    "required": False,
    "min": 1,
    "max": 1000,
},
{
    "path": "continuous_monitoring.upload.integral_window_seconds",
    "type": (int, float),
    "required": False,
    "min": 0.5,
    "max": 10.0,
},
{
    "path": "continuous_monitoring.upload.integral_threshold_ms_s",
    "type": (int, float),
    "required": False,
    "min": 1.0,
    "max": 1000.0,
},
{
    "path": "continuous_monitoring.upload.cake_backlog_low_threshold_bytes",
    "type": int,
    "required": False,
    "min": 0,
    "max": 1_000_000,
},
{
    "path": "continuous_monitoring.upload.cake_delay_delta_low_threshold_us",
    "type": int,
    "required": False,
    "min": 0,
    "max": 1_000_000,
},
```

In the upload parse block, immediately after the existing `_upload_warn_bloat_ms_explicit` line, insert (mirror exact getattr/in-dict shape):

```python
# Phase 201 — DOCSIS-aware UL control mode (per D-02..D-08).
# Per-key explicit-presence flags are PRESENCE-BASED, never value-derived
# (Phase 200 D-03 Codex pre-review catch).
self.docsis_mode = ul.get("docsis_mode", False)
self._docsis_mode_explicit = "docsis_mode" in ul
self.setpoint_mbps = ul.get("setpoint_mbps")
self._setpoint_mbps_explicit = "setpoint_mbps" in ul
self.integral_window_seconds = ul.get("integral_window_seconds", 2.0)
self._integral_window_seconds_explicit = "integral_window_seconds" in ul
self.integral_threshold_ms_s = ul.get("integral_threshold_ms_s", 30.0)
self._integral_threshold_ms_s_explicit = "integral_threshold_ms_s" in ul
self.cake_backlog_low_threshold_bytes = ul.get("cake_backlog_low_threshold_bytes", 5000)
self._cake_backlog_low_threshold_bytes_explicit = "cake_backlog_low_threshold_bytes" in ul
self.cake_delay_delta_low_threshold_us = ul.get("cake_delay_delta_low_threshold_us", 5000)
self._cake_delay_delta_low_threshold_us_explicit = "cake_delay_delta_low_threshold_us" in ul
```

In the validation block (after the existing upload-threshold ordering raise, around line 438), append:

```python
# Phase 201 D-06: docsis_mode: true requires setpoint_mbps (validator
# fails closed). And the setpoint must satisfy floor < setpoint < ceiling
# (strict; D-09 + RESEARCH §3 Pitfall 2). Use the BPS forms because
# upload_floor_red and upload_ceiling are already in bps in the Config.
if self.docsis_mode and self.setpoint_mbps is None:
    raise ValueError(
        "continuous_monitoring.upload.docsis_mode: true requires "
        "setpoint_mbps (D-06; validator fails closed)"
    )
if self.docsis_mode and self.setpoint_mbps is not None:
    setpoint_bps = float(self.setpoint_mbps) * 1_000_000
    if not (self.upload_floor_red < setpoint_bps < self.upload_ceiling):
        raise ValueError(
            f"continuous_monitoring.upload.setpoint_mbps "
            f"({self.setpoint_mbps}) must satisfy "
            f"floor_mbps < setpoint_mbps < ceiling_mbps "
            f"(floor_red_bps={self.upload_floor_red}, "
            f"ceiling_bps={self.upload_ceiling})"
        )
```

NOTE: confirm during the read pass whether the existing fields are named `upload_floor_red` (bps) or `upload_floor_red_bps` and adjust the new code to match the existing names verbatim. The pattern documented in PATTERNS.md uses `self.upload_floor_red`; verify in the actual file.

Do NOT add any new top-level imports. The `1_000_000` literal mirrors existing usage in the same file (locate via grep).

Anti-pattern reminder (do NOT do): `self._docsis_mode_explicit = self.docsis_mode != False` (value-derived). Codex pre-review caught this exact regression in Phase 200; presence-based via `"key" in ul` is the only correct shape.
  </action>
  <acceptance_criteria>
    - `grep -c "continuous_monitoring.upload.docsis_mode" src/wanctl/autorate_config.py` returns >= 2 (one schema entry, one parse line).
    - `grep -c "continuous_monitoring.upload.setpoint_mbps" src/wanctl/autorate_config.py` returns >= 1.
    - `grep -c "_docsis_mode_explicit" src/wanctl/autorate_config.py` returns >= 1.
    - `grep -c "_setpoint_mbps_explicit" src/wanctl/autorate_config.py` returns >= 1.
    - `grep -c "_integral_window_seconds_explicit" src/wanctl/autorate_config.py` returns >= 1.
    - `grep -c "_cake_backlog_low_threshold_bytes_explicit" src/wanctl/autorate_config.py` returns >= 1.
    - `grep -c "_cake_delay_delta_low_threshold_us_explicit" src/wanctl/autorate_config.py` returns >= 1.
    - `grep -v '^#' src/wanctl/autorate_config.py | grep -c "self.docsis_mode != False"` returns 0 (no value-derived flag).
    - `grep -v '^#' src/wanctl/autorate_config.py | grep -c "= self\\..*_explicit and"` returns 0 (no chained value-derived flags).
    - `grep -c "requires.*setpoint_mbps" src/wanctl/autorate_config.py` returns >= 1.
    - `grep -c "floor_mbps < setpoint_mbps < ceiling_mbps" src/wanctl/autorate_config.py` returns >= 1.
    - All TestPhase201Schema cases pass: `.venv/bin/pytest -o addopts='' tests/test_autorate_config.py -q -k TestPhase201Schema` returns 0.
    - Hot-path slice green: `.venv/bin/pytest -o addopts='' tests/test_cake_signal.py tests/test_queue_controller.py tests/test_wan_controller.py tests/test_health_check.py tests/test_autorate_config.py -q` returns 0.
    - `.venv/bin/ruff check src/wanctl/autorate_config.py` returns 0.
    - `.venv/bin/mypy src/wanctl/autorate_config.py` returns 0.
  </acceptance_criteria>
  <verify>
    <automated>.venv/bin/pytest -o addopts='' tests/test_autorate_config.py -q -k TestPhase201Schema &amp;&amp; .venv/bin/ruff check src/wanctl/autorate_config.py &amp;&amp; .venv/bin/mypy src/wanctl/autorate_config.py</automated>
  </verify>
  <done>Six schema entries + six instance fields + six presence flags + two validation raises landed; all TestPhase201Schema cases green; ruff + mypy clean; hot-path slice unchanged.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Register Phase 201 keys in KNOWN_AUTORATE_PATHS and add _validate_docsis_mode_setpoint validator</name>
  <files>src/wanctl/check_config_validators.py</files>
  <read_first>
    - src/wanctl/check_config_validators.py:1-200 (KNOWN_AUTORATE_PATHS registry)
    - src/wanctl/check_config_validators.py:380-455 (existing _validate_upload_threshold_ordering — exact mirror target)
    - tests/test_check_config.py — TestDocsisModeValidation (contract this task satisfies)
    - .planning/phases/201-docsis-aware-ul-congestion-control/201-PATTERNS.md section "src/wanctl/check_config_validators.py (validator — modify)"
  </read_first>
  <behavior>
    - KNOWN_AUTORATE_PATHS contains all six new path strings (Phase 201 keys).
    - New `_validate_docsis_mode_setpoint(cm: dict) -> list[CheckResult]` function:
        Returns [] when `cm.get("upload", {}).get("docsis_mode") is not True` (legacy byte-identity).
        Returns [Severity.ERROR result] when docsis_mode=True and setpoint_mbps absent.
        Returns [Severity.ERROR result] when setpoint_mbps not strictly between floor_mbps and ceiling_mbps.
        Returns [Severity.PASS result] when valid.
    - Validator function is wired into the existing validator chain so it runs on every config check.
    - SAFE-06: shipped Spectrum/ATT YAMLs produce zero unknown-key warnings post-change (until Plan 201-06 lands the YAML edits, neither file carries the new keys, so validator must remain silent for absent-key paths).
  </behavior>
  <action>
First read the existing KNOWN_AUTORATE_PATHS UL section (around lines 62-77) and locate the validator-chain assembly site (where existing `_validate_upload_threshold_ordering` is appended/called).

Add to the UL block of KNOWN_AUTORATE_PATHS (preserve sorted/grouped style of file):

```python
"continuous_monitoring.upload.docsis_mode",
"continuous_monitoring.upload.setpoint_mbps",
"continuous_monitoring.upload.integral_window_seconds",
"continuous_monitoring.upload.integral_threshold_ms_s",
"continuous_monitoring.upload.cake_backlog_low_threshold_bytes",
"continuous_monitoring.upload.cake_delay_delta_low_threshold_us",
```

After `_validate_upload_threshold_ordering`, add the new validator:

```python
def _validate_docsis_mode_setpoint(cm: dict) -> list[CheckResult]:
    """Validate Phase 201 DOCSIS-mode setpoint config (D-06).

    Rules:
      - docsis_mode: true requires setpoint_mbps (fail-closed when absent).
      - When docsis_mode: true, setpoint_mbps MUST satisfy
        floor_mbps < setpoint_mbps < ceiling_mbps (strict; RESEARCH §3
        Pitfall 2 + Assumption A7).
      - When docsis_mode is absent or false, this validator is silent
        (D-17 byte-identity invariant).
    """
    ul = cm.get("upload", {})
    if not isinstance(ul, dict):
        return []
    if ul.get("docsis_mode") is not True:
        return []  # opt-out path — byte-identical legacy
    setpoint = ul.get("setpoint_mbps")
    floor = ul.get("floor_mbps")
    ceiling = ul.get("ceiling_mbps")
    if setpoint is None:
        return [CheckResult(
            "Cross-field Checks",
            "continuous_monitoring.upload.setpoint_mbps",
            Severity.ERROR,
            "docsis_mode: true requires setpoint_mbps (D-06; validator fails closed)",
        )]
    try:
        sp = float(setpoint)
    except (TypeError, ValueError):
        return [CheckResult(
            "Cross-field Checks",
            "continuous_monitoring.upload.setpoint_mbps",
            Severity.ERROR,
            f"setpoint_mbps must be numeric, got {setpoint!r}",
        )]
    if floor is not None:
        try:
            fl = float(floor)
        except (TypeError, ValueError):
            fl = None
        if fl is not None and not (fl < sp):
            return [CheckResult(
                "Cross-field Checks",
                "continuous_monitoring.upload.setpoint_mbps",
                Severity.ERROR,
                f"setpoint_mbps ({sp}) must be > floor_mbps ({fl})",
            )]
    if ceiling is not None:
        try:
            ce = float(ceiling)
        except (TypeError, ValueError):
            ce = None
        if ce is not None and not (sp < ce):
            return [CheckResult(
                "Cross-field Checks",
                "continuous_monitoring.upload.setpoint_mbps",
                Severity.ERROR,
                f"setpoint_mbps ({sp}) must be < ceiling_mbps ({ce})",
            )]
    return [CheckResult(
        "Cross-field Checks",
        "continuous_monitoring.upload.setpoint_mbps",
        Severity.PASS,
        f"DOCSIS-mode setpoint ordering valid: floor < {sp} < ceiling",
    )]
```

Wire `_validate_docsis_mode_setpoint(cm)` into the same dispatcher that calls `_validate_upload_threshold_ordering(cm)` (locate via grep — the existing pattern shows how cross-field validators are accumulated).

CheckResult and Severity must match the symbols already imported in this file; do NOT add new imports unless the existing module doesn't expose them (verify via grep).
  </action>
  <acceptance_criteria>
    - `grep -c '"continuous_monitoring.upload.docsis_mode"' src/wanctl/check_config_validators.py` returns 1.
    - `grep -c '"continuous_monitoring.upload.setpoint_mbps"' src/wanctl/check_config_validators.py` returns 1.
    - `grep -c '"continuous_monitoring.upload.integral_window_seconds"' src/wanctl/check_config_validators.py` returns 1.
    - `grep -c '"continuous_monitoring.upload.integral_threshold_ms_s"' src/wanctl/check_config_validators.py` returns 1.
    - `grep -c '"continuous_monitoring.upload.cake_backlog_low_threshold_bytes"' src/wanctl/check_config_validators.py` returns 1.
    - `grep -c '"continuous_monitoring.upload.cake_delay_delta_low_threshold_us"' src/wanctl/check_config_validators.py` returns 1.
    - `grep -c "def _validate_docsis_mode_setpoint" src/wanctl/check_config_validators.py` returns 1.
    - `grep -c "_validate_docsis_mode_setpoint(cm)" src/wanctl/check_config_validators.py` returns >= 1 (wired into chain).
    - All TestDocsisModeValidation cases pass: `.venv/bin/pytest -o addopts='' tests/test_check_config.py -q -k TestDocsisModeValidation` returns 0.
    - All TestSafe06Phase201KeysKnown cases pass: `.venv/bin/pytest -o addopts='' tests/test_autorate_config.py -q -k TestSafe06Phase201KeysKnown` returns 0.
    - Existing validator tests still pass: `.venv/bin/pytest -o addopts='' tests/test_check_config.py -q -k 'not TestDocsisModeValidation'` returns 0.
    - `.venv/bin/ruff check src/wanctl/check_config_validators.py` returns 0.
    - `.venv/bin/mypy src/wanctl/check_config_validators.py` returns 0.
  </acceptance_criteria>
  <verify>
    <automated>.venv/bin/pytest -o addopts='' tests/test_check_config.py tests/test_autorate_config.py -q -k 'TestDocsisModeValidation or TestSafe06Phase201KeysKnown' &amp;&amp; .venv/bin/ruff check src/wanctl/check_config_validators.py &amp;&amp; .venv/bin/mypy src/wanctl/check_config_validators.py</automated>
  </verify>
  <done>All six keys registered; new validator landed and wired; SAFE-06 + D-06 contract tests green; static checks clean.</done>
</task>

<task type="auto" tdd="false">
  <name>Task 3: Update SAFE-05 baseline counts in test_phase_195_replay.py for v1.42</name>
  <files>tests/test_phase_195_replay.py</files>
  <read_first>
    - tests/test_phase_195_replay.py:620-680 (existing pinned counts in test_safe05_threshold_name_counts_are_unchanged)
    - .planning/phases/201-docsis-aware-ul-congestion-control/201-PATTERNS.md section "tests/test_phase_195_replay.py::test_safe05_threshold_name_counts_are_unchanged (re-baseline)"
    - .planning/phases/200-per-direction-rtt-bloat-thresholds/200-RETRO.md (D-13 notes on SAFE-05 count drift discipline)
  </read_first>
  <action>
First, run the existing SAFE-05 test to see current counts pre-change:
```bash
.venv/bin/pytest -o addopts='' tests/test_phase_195_replay.py::test_safe05_threshold_name_counts_are_unchanged -v 2>&1 | tail -40
```

If existing counts changed because Task 1 added occurrences of `target_bloat`/`warn_bloat`/etc., note the diffs. (Task 1 should NOT add such occurrences — its new keys are `docsis_mode`, `setpoint_mbps`, etc., distinct strings — so existing pins should remain stable. If a pin drifts, investigate why Task 1 introduced an incidental occurrence and fix Task 1.)

Add new entries to the `expected_counts` dict for Phase 201 keys. Compute the actual current counts in source files via:

```bash
# Run from repo root after Task 1 + Task 2 have landed:
for key in docsis_mode setpoint_mbps integral_window_seconds integral_threshold_ms_s cake_backlog_low_threshold_bytes cake_delay_delta_low_threshold_us; do
  count=$(grep -r "$key" src/wanctl/ | wc -l)
  echo "$key: $count"
done
```

Add the resulting counts as new entries in `expected_counts`. Example shape (replace `<count>` with actual):

```python
expected_counts = {
    # ... existing pins preserved verbatim ...
    "docsis_mode": <count>,
    "setpoint_mbps": <count>,
    "integral_window_seconds": <count>,
    "integral_threshold_ms_s": <count>,
    "cake_backlog_low_threshold_bytes": <count>,
    "cake_delay_delta_low_threshold_us": <count>,
}
```

Add a comment block immediately above the dict:
```python
# Phase 201 (v1.42) SAFE-05 baseline. Phase 200 v1.41 pins (warn_bloat=12,
# target_bloat=14, etc.) preserved verbatim — Phase 201 keys are distinct
# strings and do NOT add incidental occurrences of v1.41 thresholds.
# If a v1.41 pin drifts during a future change, treat that drift as a
# real signal and reconcile manually (do not auto-bump).
```

Plan 201-04 (controller core) will add MORE occurrences for the new keys when it lands, requiring another bump. That bump happens in Plan 201-04 Task 3 (a re-baseline-only sub-task). This Task 3 only re-baselines for the schema-layer occurrences from Tasks 1 and 2 above.
  </action>
  <acceptance_criteria>
    - `grep -c '"docsis_mode":' tests/test_phase_195_replay.py` returns 1 (new pin).
    - `grep -c '"setpoint_mbps":' tests/test_phase_195_replay.py` returns 1.
    - `grep -c '"integral_window_seconds":' tests/test_phase_195_replay.py` returns 1.
    - `grep -c '"integral_threshold_ms_s":' tests/test_phase_195_replay.py` returns 1.
    - `grep -c '"cake_backlog_low_threshold_bytes":' tests/test_phase_195_replay.py` returns 1.
    - `grep -c '"cake_delay_delta_low_threshold_us":' tests/test_phase_195_replay.py` returns 1.
    - The full test passes: `.venv/bin/pytest -o addopts='' tests/test_phase_195_replay.py::test_safe05_threshold_name_counts_are_unchanged -v` returns 0.
    - Existing v1.41 pins (warn_bloat=12, target_bloat=14, factor_down=17, etc.) are NOT modified (verify by diff against pre-task state).
  </acceptance_criteria>
  <verify>
    <automated>.venv/bin/pytest -o addopts='' tests/test_phase_195_replay.py::test_safe05_threshold_name_counts_are_unchanged -v</automated>
  </verify>
  <done>SAFE-05 v1.42 baseline established for the schema-layer surface. Phase 201 keys pinned; Phase 200 pins unchanged.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| operator YAML → Config | New keys parsed via `yaml.safe_load`; presence-based flags eliminate value-derived ambiguity (D-03). |
| Config → controller | Validator fails closed before controller construction; bad config never reaches the rate-decision path. |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-201-07 | Tampering | Operator typos a key (`docsis_modee`) and SAFE-06 silently drops it | mitigate | All six keys registered in KNOWN_AUTORATE_PATHS; SAFE-06 emits an audible startup WARNING for unknown `continuous_monitoring.*` keys (Phase 200 closed gap). |
| T-201-08 | Tampering | Operator sets `docsis_mode: true` without `setpoint_mbps` | mitigate | Validator returns Severity.ERROR; Config.__init__ raises ValueError. Both paths fail closed before controller starts. |
| T-201-09 | Tampering | Operator sets `setpoint_mbps` outside `floor_mbps < setpoint_mbps < ceiling_mbps` | mitigate | Strict ordering check in both Config validation and check_config validator chain (RESEARCH Assumption A7). |
| T-201-10 | Repudiation | Value-derived presence flag silently fails when operator sets `docsis_mode: false` matching default (Phase 200 D-03 Codex catch family) | mitigate | All flags use `"key" in ul`; test `test_explicit_presence_flags_are_presence_based` asserts `_docsis_mode_explicit=True` even when value=False. |
| T-201-11 | Information Disclosure | Validator error messages reveal internal field names (low risk, operator-context) | accept | Error messages cite operator-facing YAML key names (`floor_mbps`, `setpoint_mbps`, `ceiling_mbps`); no secrets leaked. ASVS V7 compliant. |
</threat_model>

<verification>
- All TestPhase201Schema, TestSafe06Phase201KeysKnown, TestDocsisModeValidation cases green.
- SAFE-05 v1.42 baseline test green; v1.41 pins unchanged.
- Hot-path regression slice unchanged.
- Static checks clean (ruff + mypy).
- Anti-pattern grep returns 0 (no value-derived flags).
</verification>

<success_criteria>
- Six new YAML keys land in schema, parse correctly, register in SAFE-06 path registry.
- D-06 fail-closed validation in two layers (Config raise + check_config CheckResult ERROR).
- Per-key explicit-presence flags presence-based (D-03 invariant preserved).
- D-17 byte-identity preserved: legacy YAMLs produce no new errors and no new warnings.
- SAFE-05 v1.42 pins reflect schema-layer changes only.
</success_criteria>

<output>
After completion, create `.planning/phases/201-docsis-aware-ul-congestion-control/201-03-SUMMARY.md` with: list of six new keys with min/max + defaults; Wave 0 tests now green (TestPhase201Schema, TestSafe06Phase201KeysKnown, TestDocsisModeValidation); SAFE-05 v1.42 occurrence counts captured; ruff/mypy/regression slice status.
</output>
