# Phase 201: DOCSIS-Aware UL Congestion Control - Pattern Map

**Mapped:** 2026-05-04
**Files analyzed:** 12 modified/created code files + 8 test/script targets
**Analogs found:** 18 / 20 (2 net-new with no analog: predeploy gate script, replay corpus)

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `src/wanctl/queue_controller.py` (modify) | controller / state-machine | request-response (tick) | self (existing `_classify_zone_3state` + `_compute_rate_3state`) | exact (augment, not replace) |
| `src/wanctl/wan_controller.py` (modify) | controller / orchestrator | request-response (cycle) | self (lines 402-452, 2978-2984, 4490-4530) | exact (mirror Phase 200 D-03 + Phase 197 corroborator) |
| `src/wanctl/autorate_config.py` (modify) | config / schema | transform (YAML → typed) | self (lines 355-379, 392-438) — `_upload_target_bloat_ms_explicit` pattern | exact |
| `src/wanctl/check_config_validators.py` (modify) | validator / config | transform (dict → CheckResult) | self (lines 28-200 KNOWN_AUTORATE_PATHS; lines 408-453 `_validate_upload_threshold_ordering`) | exact |
| `src/wanctl/cake_signal.py` | (no change) | — | — | n/a — fields already populated |
| `configs/spectrum.yaml` (modify) | config / data | static | self (lines 67-77 upload block) | exact |
| `scripts/phase200-saturation-canary.sh` (extend) | shell / preflight | event-driven | self (lines 314-362 env↔YAML cross-check) | exact (mirror new keys) |
| `scripts/phase200-saturation-canary.env.example` (extend) | config / template | static | self (existing `PHASE200_*` block) | exact |
| `scripts/phase201-predeploy-gate.sh` (NEW) | shell / preflight | event-driven | `scripts/phase200-saturation-canary.sh:314-362` | role-match (new responsibility, mirror SSH+YAML+jq pattern) |
| `tests/test_queue_controller.py` (extend) | test / unit | request-response | self (lines 26-160) | exact |
| `tests/test_autorate_config.py` (extend) | test / unit | transform | self (existing schema/ordering test classes) | exact |
| `tests/test_check_config.py` (extend) | test / unit | transform | self (existing validator tests) | exact |
| `tests/test_wan_controller.py` (extend) | test / integration | request-response | self (lines 71-223 UL threshold-config tests) | exact |
| `tests/test_phase200_canary_script.py` (extend) | test / shell-integration | event-driven | self (existing canary preflight tests) | exact |
| `tests/test_phase_201_replay.py` (NEW) | test / replay | batch | `tests/test_phase_197_replay.py:1-100` | exact (canonical mirror) |
| `tests/test_phase201_predeploy_gate.py` (NEW) | test / shell-integration | event-driven | `tests/test_phase200_canary_script.py` | role-match |
| `tests/test_phase_195_replay.py::test_safe05_threshold_name_counts_are_unchanged` (re-baseline) | test / invariant | batch | self (lines 642-666) | exact |
| `docs/CONFIGURATION.md` (extend) | docs | static | self (Phase 200 DOCS-03 migration note) | exact |
| `CHANGELOG.md` (extend) | docs | static | self (existing `## v1.41.0` entry) | exact |
| `.planning/phases/200-.../canary/20260504T133207Z/loaded_capture.ndjson` (read-only corpus) | test fixture | batch | self | exact (Phase 200 capture reused) |

## Pattern Assignments

### `src/wanctl/queue_controller.py` (controller / state-machine — augment)

**Analog:** itself, lines 19-256 (existing `QueueController` class, `_classify_zone_3state`, `_compute_rate_3state`).

**RESEARCH headline finding (Section 1):** AUGMENT, do not REPLACE. Keep the existing classifier; add an integral *headroom-probe gate* that interacts with the GREEN-streak push-up path only. The RED fast-trip (lines 147-153) and YELLOW R5/R3 hold path (lines 239-256) MUST remain byte-identical when `docsis_mode=False`.

**Imports pattern** (lines 1-16) — extend, do not change shape:
```python
"""Queue bandwidth state machine for download and upload directions."""
from __future__ import annotations
import logging
import time
from collections import deque  # NEW: windowed RTT-integral buffer
from typing import TYPE_CHECKING, Any
from wanctl.rate_utils import enforce_rate_bounds
if TYPE_CHECKING:
    from wanctl.cake_signal import CakeSignalSnapshot
```

**Constructor `__init__` extension pattern** (mirror existing keyword-only signature, lines 24-43):
```python
# Existing tail of __init__ (line 95): self._last_zone: str = "GREEN"
# Phase 201 ADDITIONS — keyword-only with safe defaults so legacy callers untouched:
#   docsis_mode: bool = False
#   setpoint_bps: int | None = None
#   integral_window_seconds: float = 2.0
#   integral_threshold_ms_s: float = 30.0
#   cake_backlog_low_threshold_bytes: int = 5000
#   cake_delay_delta_low_threshold_us: int = 5000
self._docsis_mode = docsis_mode
self._setpoint_bps = setpoint_bps
window_size = max(1, int(round(integral_window_seconds / 0.05)))  # 50ms cycle
self._integral_window: deque[float] = deque(maxlen=window_size)
self._integral_threshold_ms_s = integral_threshold_ms_s
self._cake_backlog_low_threshold_bytes = cake_backlog_low_threshold_bytes
self._cake_delay_delta_low_threshold_us = cake_delay_delta_low_threshold_us
self._headroom_state = "EXHAUSTED"  # safe default; AVAILABLE only after window full
self._cake_aligned = False
self._last_integral_ms_s = 0.0
# DOCSIS-mode current_rate initialization fix (RESEARCH Section 4 recommendation):
if self._docsis_mode and self._setpoint_bps is not None:
    self.current_rate = min(self.current_rate, self._setpoint_bps)
```

**RED fast-trip preservation pattern (must NOT change)** — lines 147-153:
```python
if delta > warn_delta:
    # RED: immediate, bypasses dwell (D-02)
    self.red_streak += 1
    self.green_streak = 0
    self._probe_multiplier = 1.0
    self._yellow_dwell = 0
    return "RED"
```
ARCH-03 invariant: rate decreases immediate. Phase 201 integral MUST NOT delay this path.

**Existing `_compute_rate_3state` body to mirror, lines 229-256** — clamp injects only inside the GREEN+sustained branch:
```python
def _compute_rate_3state(self, zone: str) -> int:
    if self.red_streak >= 1:
        self._yellow_decay_streak = 0
        return int(self.current_rate * self.factor_down)            # UNCHANGED
    if self.green_streak >= self.green_required:
        self._yellow_decay_streak = 0
        raw_rate = self.current_rate + self._compute_probe_step()
        # NEW Phase 201: setpoint clamp on push-up only (decreases unaffected).
        if self._docsis_mode and self._setpoint_bps is not None:
            if not (self._headroom_state == "AVAILABLE" and self._cake_aligned):
                return min(raw_rate, self._setpoint_bps)
        return raw_rate
    if zone == "YELLOW":
        if (
            self.consecutive_yellow_decay_clamp > 0
            and self._yellow_decay_streak >= self.consecutive_yellow_decay_clamp
        ):
            return self.current_rate                                 # UNCHANGED (R3)
        self._yellow_decay_streak += 1
        return int(self.current_rate * self.factor_down_yellow)      # UNCHANGED
    self._yellow_decay_streak = 0
    return self.current_rate                                         # UNCHANGED
```

**Adjust seam (lines 121-137) — DOCSIS branch additions:**
```python
def adjust(self, baseline_rtt, load_rtt, target_delta, warn_delta, cake_snapshot=None):
    self._dwell_bypassed_this_cycle = False
    self._backlog_suppressed_this_cycle = False
    delta = load_rtt - baseline_rtt
    # NEW Phase 201: integral + cake-aligned BEFORE classify (consumes the
    # same delta the classifier consumes; guarantees identical asymmetry-gate
    # semantics — RESEARCH Open Question 4).
    if self._docsis_mode:
        self._last_integral_ms_s, self._headroom_state = self._update_integral(delta)
        self._cake_aligned = self._is_cake_aligned_for_pushup(cake_snapshot)
    zone = self._classify_zone_3state(delta, target_delta, warn_delta, cake_snapshot)
    if zone in ("YELLOW", "RED"):
        self._window_had_congestion = True
    new_rate = self._compute_rate_3state(zone)
    new_rate = enforce_rate_bounds(new_rate, floor=self.floor_red_bps, ceiling=self.ceiling_bps)
    self.current_rate = new_rate
    transition_reason = self._build_transition_reason(zone, delta, target=target_delta, warn=warn_delta)
    return zone, new_rate, transition_reason
```

**New helpers — verbatim from RESEARCH §1, §2:**
```python
def _update_integral(self, delta_ms: float) -> tuple[float, str]:
    """Append delta sample, return (integral_ms_s, headroom_state)."""
    self._integral_window.append(max(0.0, delta_ms))  # negative deltas → 0 (no credit)
    integral_ms_s = sum(self._integral_window) * 0.05  # 50ms cycle
    if len(self._integral_window) < self._integral_window.maxlen:
        return integral_ms_s, "EXHAUSTED"  # window not full → conservative
    if integral_ms_s <= self._integral_threshold_ms_s:
        return integral_ms_s, "AVAILABLE"
    return integral_ms_s, "EXHAUSTED"

def _is_cake_aligned_for_pushup(self, cake: "CakeSignalSnapshot | None") -> bool:
    """Categorical AND-gate: backlog low AND max_delay_delta_us low. Phase 197 mirror."""
    if cake is None or cake.cold_start:
        return False  # cold-start veto-deny (RESEARCH Pitfall 4)
    backlog_low = cake.backlog_bytes <= self._cake_backlog_low_threshold_bytes
    delay_low = cake.max_delay_delta_us <= self._cake_delay_delta_low_threshold_us
    return backlog_low and delay_low
```

**Health data extension** — extend the existing `get_health_data()` to add additive runtime-state keys (D-16):
```python
# In QueueController.get_health_data() existing dict, add:
"docsis_mode_active": self._docsis_mode,                # runtime state
"setpoint_mbps": (self._setpoint_bps / 1_000_000) if self._setpoint_bps else None,
"headroom_state": self._headroom_state,
"rtt_integral_ms_s": round(self._last_integral_ms_s, 3),
"cake_aligned": self._cake_aligned,
```

---

### `src/wanctl/wan_controller.py` (controller / orchestrator — modify)

**Analog:** itself, three sites.

**Site 1 — Upload constructor wiring (lines 402-418):** Mirror Phase 200's UL constructor pattern; add Phase 201 keyword args. Excerpt verbatim from existing code:
```python
self.upload = QueueController(
    name=f"{wan_name}-Upload",
    floor_green=config.upload_floor_green,
    floor_yellow=config.upload_floor_yellow,
    floor_soft_red=config.upload_floor_yellow,
    floor_red=config.upload_floor_red,
    ceiling=config.upload_ceiling,
    step_up=config.upload_step_up,
    factor_down=config.upload_factor_down,
    factor_down_yellow=config.upload_factor_down_yellow,
    green_required=config.upload_green_required,
    dwell_cycles=config.dwell_cycles,
    deadband_ms=config.deadband_ms,
    consecutive_yellow_decay_clamp=getattr(
        config, "upload_consecutive_yellow_decay_clamp", 0
    ),
    # NEW Phase 201:
    docsis_mode=getattr(config, "docsis_mode", False),
    setpoint_bps=(
        int(config.setpoint_mbps * 1_000_000)
        if getattr(config, "_setpoint_mbps_explicit", False) else None
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

**Site 2 — Per-key explicit-presence flags + INFO log (D-06 mirror, copy shape verbatim from lines 426-452):**
```python
# EXACT MIRROR of existing Phase 200 D-03 pattern.
# Source: wan_controller.py:432-437 — DO NOT alter the getattr fallback shape.
self._docsis_mode_explicit = getattr(config, "_docsis_mode_explicit", False)
self._setpoint_mbps_explicit = getattr(config, "_setpoint_mbps_explicit", False)
# One-shot INFO log when operator opts in. MUST use self.logger (per-WAN
# logger) — module-scope logger has no handlers in production (Phase 200
# Plan 01 Task 2 silent-drop bug, RESEARCH Pitfall 5).
if self._docsis_mode_explicit and getattr(config, "docsis_mode", False):
    self.logger.info(
        "phase201 docsis_mode active: setpoint_mbps=%s window_s=%s threshold_ms_s=%s",
        config.setpoint_mbps,
        getattr(config, "integral_window_seconds", 2.0),
        getattr(config, "integral_threshold_ms_s", 30.0),
    )
```
**Anti-pattern** (do not do): value-derived flag like `flag = (config.docsis_mode != False)` — Codex pre-review caught this exact regression in Phase 200.

**Site 3 — UL `adjust(...)` call site (lines 2977-2984)** — DO NOT change signature. Phase 200 ARB-04 guard at `tests/test_phase_195_replay.py:629-640` regex-pins this call shape:
```python
effective_ul_load_rtt = self._compute_effective_ul_load_rtt()
ul_zone, ul_rate, ul_transition_reason = self.upload.adjust(
    self.baseline_rtt,
    effective_ul_load_rtt,
    self.target_delta,
    self.warn_delta,
    cake_snapshot=ul_cake,
)
```
The new integral state lives INSIDE `QueueController`; the UL cycle call signature is unchanged. `cake_snapshot=ul_cake` already plumbs the corroborator source — no new wiring at this seam.

**Site 4 — `/health` additive fields (D-16, around line 4510):** existing pattern uses `_ul_cake_snapshot` injected as the `"upload"` value of `cake_signal`:
```python
"cake_signal": {
    "enabled": self._dl_cake_signal.config.enabled,
    "supported": self._cake_signal_supported,
    "download": self._dl_cake_snapshot,
    "upload": self._ul_cake_snapshot,
    ...
}
```
Phase 201 D-16 fields are exposed via `QueueController.get_health_data()` (already aggregated under `.wans[].upload.*` by existing health builder) — no new top-level structure. `setpoint_mbps`, `headroom_state`, `rtt_integral_ms_s`, `docsis_mode_active`, `cake_aligned` all become runtime-state keys on `.wans[].upload.*`.

**Site 5 — SIGUSR1 reload scope (lines 1894-1899) — DO NOT EXTEND.** D-08: restart-required for docsis_mode/setpoint keys. The existing fusion/dwell SIGUSR1 path stays narrow.

**Baseline RTT freeze gate (lines 1346-1395) — REUSE, do not duplicate.** RESEARCH Section 6 says: integral consumes `self.baseline_rtt` directly; do NOT introduce a parallel `_integral_baseline_rtt`. The freeze gate at `_update_baseline_if_idle` is the only baseline source.

---

### `src/wanctl/autorate_config.py` (config / schema — modify)

**Analog:** itself, lines 355-379 (UL block load + presence flags) and lines 169-201 (UL SCHEMA entries). Exact mirror.

**Schema-entry pattern (lines 182-194)** — new keys must register here with `min`/`max` and ordering metadata. Existing UL `target_bloat_ms` entry shape:
```python
{
    "path": "continuous_monitoring.upload.target_bloat_ms",
    "type": (int, float),
    "required": False,
    "min": 1,
    "max": 200,
},
{
    "path": "continuous_monitoring.upload.warn_bloat_ms",
    "type": (int, float),
    "required": False,
    "min": 1,
    "max": 250,
},
```
Phase 201 new entries (planner-finalized names; honor SAFE-06 ordering test):
```python
{"path": "continuous_monitoring.upload.docsis_mode",
 "type": bool, "required": False},
{"path": "continuous_monitoring.upload.setpoint_mbps",
 "type": (int, float), "required": False, "min": 1, "max": 1000},
{"path": "continuous_monitoring.upload.integral_window_seconds",
 "type": (int, float), "required": False, "min": 0.5, "max": 10.0},
{"path": "continuous_monitoring.upload.integral_threshold_ms_s",
 "type": (int, float), "required": False, "min": 1.0, "max": 1000.0},
{"path": "continuous_monitoring.upload.cake_backlog_low_threshold_bytes",
 "type": int, "required": False, "min": 0, "max": 1_000_000},
{"path": "continuous_monitoring.upload.cake_delay_delta_low_threshold_us",
 "type": int, "required": False, "min": 0, "max": 1_000_000},
```

**Per-key explicit-presence pattern (lines 371-379) — EXACT MIRROR:**
```python
# Source: src/wanctl/autorate_config.py:371-379 (verified)
self._upload_target_bloat_ms_raw = ul.get("target_bloat_ms")
self._upload_warn_bloat_ms_raw = ul.get("warn_bloat_ms")
# Per-key presence flags (Phase 200 D-03: must be presence-based, NOT
# value-derived). Codex pre-review caught that a value-derived flag
# silently fails when an operator (a) sets a UL key equal to the DL
# global default, or (b) sets only one of the two keys. Presence
# detection (`"key" in ul`) handles both correctly.
self._upload_target_bloat_ms_explicit = "target_bloat_ms" in ul
self._upload_warn_bloat_ms_explicit = "warn_bloat_ms" in ul
```
Phase 201 mirror (verbatim):
```python
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

**Required-when-other pattern (lines 429-438) — EXACT MIRROR for `setpoint_mbps` requirement:**
```python
# Source pattern: lines 433-438 (existing upload threshold ordering raise)
if self.docsis_mode and self.setpoint_mbps is None:
    raise ValueError(
        "docsis_mode: true requires setpoint_mbps (D-06; validator fails closed)"
    )
if self.docsis_mode and self.setpoint_mbps is not None:
    setpoint_bps = float(self.setpoint_mbps) * MBPS_TO_BPS
    if not (self.upload_floor_red < setpoint_bps < self.upload_ceiling):
        raise ValueError(
            f"setpoint_mbps ({self.setpoint_mbps}) must satisfy "
            f"floor_mbps < setpoint_mbps < ceiling_mbps"
        )
```

---

### `src/wanctl/check_config_validators.py` (validator — modify)

**Analog:** itself, lines 28-200 (KNOWN_AUTORATE_PATHS) and lines 408-453 (`_validate_upload_threshold_ordering`).

**KNOWN_AUTORATE_PATHS registration (SAFE-06 enforcement):** Add Phase 201 keys to the registry at lines 62-77 (UL block):
```python
# EXACT shape of existing entries — strings only; no schema.
"continuous_monitoring.upload.docsis_mode",
"continuous_monitoring.upload.setpoint_mbps",
"continuous_monitoring.upload.integral_window_seconds",
"continuous_monitoring.upload.integral_threshold_ms_s",
"continuous_monitoring.upload.cake_backlog_low_threshold_bytes",
"continuous_monitoring.upload.cake_delay_delta_low_threshold_us",
```
**Anti-pattern:** forgetting to register a key here produces SAFE-06 unknown-key warnings on production startup (Phase 200 closed this exact gap; Phase 201 must not reopen it).

**Cross-field validator pattern (lines 408-453) — MIRROR for setpoint ordering:**
```python
# Source: src/wanctl/check_config_validators.py:408-453 (verified)
def _validate_upload_threshold_ordering(cm: dict) -> list[CheckResult]:
    ul = cm.get("upload", {})
    thresholds = cm.get("thresholds", {})
    if not isinstance(ul, dict) or not isinstance(thresholds, dict):
        return []
    target = ul.get("target_bloat_ms", thresholds.get("target_bloat_ms"))
    warn = ul.get("warn_bloat_ms", thresholds.get("warn_bloat_ms"))
    if target is None or warn is None:
        return []
    ...
    if target_f < warn_f:
        return [CheckResult("Cross-field Checks", "...", Severity.PASS, "Upload threshold ordering: valid")]
    return [CheckResult("Cross-field Checks", "...", Severity.ERROR, "...")]
```
Phase 201 new validator `_validate_docsis_mode_setpoint(cm)` mirrors the shape; keys checked are:
1. `docsis_mode: true` requires `setpoint_mbps` present.
2. `floor_mbps < setpoint_mbps < ceiling_mbps` (strict; A7 in RESEARCH).
3. Returns `Severity.ERROR` on violation; `Severity.PASS` with descriptive message on success.

---

### `configs/spectrum.yaml` (config / data — modify)

**Analog:** itself, lines 67-77 upload block. Modifications:
```yaml
# EXISTING (rejected-hypothesis keys to REMOVE per RESEARCH Section 5):
#  target_bloat_ms: 42      # REMOVE
#  warn_bloat_ms: 105       # REMOVE
# RETAIN (RESEARCH Section 5: R5+R3 complementary, not redundant):
#  factor_down_yellow: 1.0
#  consecutive_yellow_decay_clamp: 40
# ADD (D-09, D-02):
docsis_mode: true                              # opt-in, byte-identical when absent
setpoint_mbps: 12                              # ASSUMED — no sweep evidence; canary validates
integral_window_seconds: 2.0                   # 40 cycles at 50ms; mirrors R3 horizon
integral_threshold_ms_s: 30.0                  # ASSUMED A2 — canary tunes
cake_backlog_low_threshold_bytes: 5000         # Phase 163 sweep winner
cake_delay_delta_low_threshold_us: 5000        # ASSUMED A3 — canary tunes
```
**Anti-pattern:** keeping `target_bloat_ms: 42 / warn_bloat_ms: 105` after deploy of v1.42 — these are the rejected v1.41 hypothesis keys. The D-15 predeploy gate fails closed if they remain.

---

### `scripts/phase200-saturation-canary.sh` (extend lines 314-362)

**Analog:** itself. The existing env↔YAML SSH cross-check is the verbatim shape; just add new keys.

**Existing pattern (lines 328-362) — copy verbatim, extend the YAML probe:**
```bash
# Source: scripts/phase200-saturation-canary.sh:328-362 (verified)
YAML_PROBE="$(ssh -o ConnectTimeout=10 -o BatchMode=no "$REMOTE_SSH_TARGET" \
    "sudo cat -- '${REMOTE_YAML_PATH}'" 2>/dev/null \
    | python3 -c '
import sys, json, yaml
try:
    d = yaml.safe_load(sys.stdin)
    ul = d["continuous_monitoring"]["upload"]
    print(json.dumps({
        "floor": ul["floor_mbps"],
        "ceiling": ul["ceiling_mbps"],
        # NEW Phase 201 fields (D-12):
        "docsis_mode": ul.get("docsis_mode", False),
        "setpoint_mbps": ul.get("setpoint_mbps"),
    }))
except Exception as exc:
    print(json.dumps({"error": str(exc)}))
' 2>/dev/null)"
```

**Mismatch ABORT pattern (lines 352-361) — mirror for new vars:**
```bash
# Source pattern: lines 352-361
YAML_DOCSIS="$(printf '%s' "$YAML_PROBE" | jq -r '.docsis_mode')"
YAML_SETPOINT="$(printf '%s' "$YAML_PROBE" | jq -r '.setpoint_mbps')"
if [[ "$YAML_DOCSIS" != "$PHASE201_DOCSIS_MODE" ]]; then
    log_abort "PHASE201_DOCSIS_MODE=${PHASE201_DOCSIS_MODE} does not match deployed YAML docsis_mode=${YAML_DOCSIS}"
    write_abort_verdict "env_yaml_docsis_mode_mismatch"
    exit "$EXIT_ABORT"
fi
if [[ "$YAML_SETPOINT" != "$PHASE201_SETPOINT_MBPS" ]]; then
    log_abort "PHASE201_SETPOINT_MBPS=${PHASE201_SETPOINT_MBPS} does not match deployed YAML setpoint_mbps=${YAML_SETPOINT}"
    write_abort_verdict "env_yaml_setpoint_mismatch"
    exit "$EXIT_ABORT"
fi
```

**/health DOCSIS-mode probe (D-12, NEW after line 312):** insert before saturation begins. Three-branch logic per RESEARCH Pitfall 7:
```bash
HEALTH_DOCSIS="$(fetch_health_sample | jq -r '.wans[0].upload.docsis_mode_active // "absent"')"
case "$HEALTH_DOCSIS" in
    absent) log_abort "/health.wans[0].upload.docsis_mode_active key absent — deploy did not happen"; \
            write_abort_verdict "health_docsis_key_absent"; exit "$EXIT_ABORT" ;;
    false)  log_abort "/health.wans[0].upload.docsis_mode_active=false — wrong WAN or stale binary"; \
            write_abort_verdict "health_docsis_false"; exit "$EXIT_ABORT" ;;
    true)   log_info "Preflight: /health confirms docsis_mode_active=true" ;;
    *)      log_abort "Unexpected /health.wans[0].upload.docsis_mode_active=${HEALTH_DOCSIS}"; \
            write_abort_verdict "health_docsis_invalid"; exit "$EXIT_ABORT" ;;
esac
```

**Missing-deps precheck (RESEARCH Section 11 — closes WR-02):** add before the YAML probe:
```bash
require_command python3
ssh -o ConnectTimeout=5 "$REMOTE_SSH_TARGET" 'python3 -c "import yaml" 2>/dev/null' \
    || { log_abort "Remote python3+pyyaml not available on ${REMOTE_SSH_TARGET}"; \
         write_abort_verdict "remote_python_yaml_missing"; exit "$EXIT_ABORT"; }
```

---

### `scripts/phase200-saturation-canary.env.example` (extend)

**Analog:** itself. Add new vars to the `PHASE200_*` block:
```bash
# Phase 201 D-12 additions (env-declared expectation; canary preflight
# cross-checks against deployed YAML and ABORTs on mismatch).
# Current Spectrum production after Phase 201 deploy: docsis_mode=true, setpoint=12.
# Example: PHASE201_DOCSIS_MODE=true
# Example: PHASE201_SETPOINT_MBPS=12
PHASE201_DOCSIS_MODE=""
PHASE201_SETPOINT_MBPS=""
```

---

### `scripts/phase201-predeploy-gate.sh` (NEW)

**Analog:** `scripts/phase200-saturation-canary.sh` — preflight section, lines 314-362. Same SSH+sudo+yaml.safe_load+jq pattern, different responsibility (rejected-key inspection per D-15). RESEARCH §9 chose Option α: separate script invoked from `scripts/deploy.sh` before rsync.

**Pattern to mirror (header + helpers from canary):**
```bash
#!/usr/bin/env bash
# Phase 201 predeploy gate — D-15 reconciliation check.
# Inspects $REMOTE_SSH_TARGET:$REMOTE_YAML_PATH for v1.41-only rejected-hypothesis
# keys (target_bloat_ms / warn_bloat_ms in continuous_monitoring.upload).
# Exits 0 if clean OR if all rejected keys are accompanied by docsis_mode: true
# (operator's deliberate Phase 201 choice). Exits non-zero with an
# operator-actionable message otherwise. Fail-closed (RESEARCH §9 Option B).

set -euo pipefail
EXIT_PASS=0
EXIT_BLOCK=1
EXIT_ABORT=2
# (reuse log_info, log_abort, validate_remote_yaml_path from canary script)
```

**Gate logic (RESEARCH §9):**
```bash
YAML_PROBE="$(ssh ... | python3 -c '
import sys, json, yaml
d = yaml.safe_load(sys.stdin)
ul = d["continuous_monitoring"]["upload"]
print(json.dumps({
    "has_target_bloat_ms": "target_bloat_ms" in ul,
    "has_warn_bloat_ms": "warn_bloat_ms" in ul,
    "docsis_mode": ul.get("docsis_mode", False),
    "setpoint_mbps": ul.get("setpoint_mbps"),
}))')"
# Reject rules (RESEARCH §5):
# - target_bloat_ms / warn_bloat_ms present in continuous_monitoring.upload → BLOCK
# - docsis_mode: true requires setpoint_mbps present → BLOCK
# - factor_down_yellow / consecutive_yellow_decay_clamp → ALLOW (kept per Section 5)
```

---

### `tests/test_queue_controller.py` (extend)

**Analog:** itself, lines 26-160 (existing fixtures + 3-state tests).

**Fixture pattern (lines 26-48):** copy `controller_3state` shape; add docsis fixture:
```python
@pytest.fixture
def controller_docsis():
    return QueueController(
        name="TestUpload-DOCSIS",
        floor_green=8_000_000, floor_yellow=8_000_000, floor_soft_red=8_000_000,
        floor_red=8_000_000,
        ceiling=18_000_000,
        step_up=5_000_000,
        factor_down=0.90,
        factor_down_yellow=1.0,
        green_required=3,
        dwell_cycles=3, deadband_ms=3.0,
        consecutive_yellow_decay_clamp=40,
        docsis_mode=True,
        setpoint_bps=12_000_000,
        integral_window_seconds=2.0,
        integral_threshold_ms_s=30.0,
        cake_backlog_low_threshold_bytes=5000,
        cake_delay_delta_low_threshold_us=5000,
    )
```

**Test class structure (lines 82-141):** mirror `TestAdjust3StateZoneClassification` shape.

New test classes per RESEARCH Section 7 Wave 0 gaps:
- `TestDocsisModeIntegralClassifier` — `_update_integral` state machine (window-not-full → EXHAUSTED; integral ≤ threshold → AVAILABLE; integral > threshold → EXHAUSTED).
- `TestDocsisModeSetpointClamp` — sustained GREEN streak with `headroom_AVAILABLE AND cake_aligned` lifts toward ceiling; otherwise clamps at setpoint.
- `TestDocsisModeCakeCorroborator` — `_is_cake_aligned_for_pushup` returns False on `cold_start=True`, on high backlog, on high delay-delta; True only on AND-aligned-low.
- `TestDocsisModeByteIdentity` — `docsis_mode=False` produces byte-identical zone+rate trace to controller_3state on a fixed-seed delta sequence (preserves D-17).
- `TestRedFastTripUnchanged` — RED fast-trip with `docsis_mode=True` returns `factor_down` decay regardless of integral state (ARCH-03 invariant; RESEARCH Pitfall 1).

---

### `tests/test_phase_201_replay.py` (NEW)

**Analog:** `tests/test_phase_197_replay.py:1-100` — canonical replay shape.

**Imports + helper pattern:**
```python
# Source mirror: tests/test_phase_197_replay.py:23-100 (verified)
from __future__ import annotations
from unittest.mock import MagicMock, patch
import pytest
from wanctl.cake_signal import CakeSignalConfig, CakeSignalProcessor, CakeSignalSnapshot
from wanctl.wan_controller import WANController

@pytest.fixture
def integrated_controller(mock_autorate_config):
    router = MagicMock(); router.set_limits.return_value = True
    router.needs_rate_limiting = True
    router.rate_limit_params = {"max_changes": 5, "window_seconds": 10}
    rtt_measurement = MagicMock(); logger = MagicMock()
    with patch.object(WANController, "load_state"):
        ctrl = WANController(
            wan_name="TestWAN", config=mock_autorate_config,
            router=router, rtt_measurement=rtt_measurement, logger=logger,
        )
    return ctrl

def _queue_snapshot(max_delay_delta_us, *, cold_start=False, backlog_bytes=0):
    return CakeSignalSnapshot(
        drop_rate=0.0, total_drop_rate=0.0,
        backlog_bytes=backlog_bytes,
        peak_delay_us=max_delay_delta_us + 1000,
        tins=(), cold_start=cold_start,
        avg_delay_us=max_delay_delta_us + 500, base_delay_us=500,
        max_delay_delta_us=max_delay_delta_us,
    )
```

**Replay corpus loader (NEW shape, RESEARCH §8):**
```python
TRACE_ATTEMPT_3 = _load_ndjson(
    ".planning/phases/200-per-direction-rtt-bloat-thresholds/canary/20260504T133207Z/loaded_capture.ndjson"
)

class TestAttempt3ReplayWithDocsisMode:
    def test_no_floor_hits(self):
        ctrl = _docsis_mode_controller(setpoint_mbps=12, ceiling=18)
        floor_hits = sum(
            1 for sample in TRACE_ATTEMPT_3
            if _adjust_replay(ctrl, sample).rate <= ctrl.upload.floor_red_bps
        )
        assert floor_hits == 0  # contract per RESEARCH §8
```

**Legacy byte-identity invariant (D-17):**
```python
class TestLegacyByteIdentity:
    def test_no_docsis_key_produces_byte_identical_3state(self):
        # Mirror test_phase_193_replay TRACE; assert zones+rates unchanged
        ...
```

---

### `tests/test_phase_195_replay.py::test_safe05_threshold_name_counts_are_unchanged` (re-baseline)

**Analog:** itself, lines 642-666 (verified).

**Existing pin (lines 653-663):**
```python
expected_counts = {
    "factor_down": 17,
    "step_up": 12,
    "dwell_cycles": 14,
    "deadband_ms": 14,
    "warn_bloat": 12,   # v1.41 bumped from v1.40 pin of 4
    "target_bloat": 14, # v1.41 bumped from v1.40 pin of 4
    "hard_red": 17,
    "burst_threshold": 0,
    "green_required": 12,
}
```
**Phase 201 re-baseline:** the new docsis_mode/setpoint plumbing in `wan_controller.py` does NOT add `target_bloat`/`warn_bloat` substring occurrences (the new keys are `docsis_mode`, `setpoint_mbps`, etc., which are distinct strings). The existing pinned counts MAY remain at 12/14, but the planner MUST re-run the test after each commit and update pins if any ancillary code change adds incidental occurrences. Add new pins:
```python
"docsis_mode": <count>,        # NEW Phase 201
"setpoint_mbps": <count>,      # NEW Phase 201
```

---

## Shared Patterns

### Per-Key Explicit-Presence Flags
**Source:** `src/wanctl/autorate_config.py:371-379`, mirrored in `src/wanctl/wan_controller.py:432-452`.
**Apply to:** every new YAML key in Phase 201 (`docsis_mode`, `setpoint_mbps`, `integral_window_seconds`, `integral_threshold_ms_s`, `cake_backlog_low_threshold_bytes`, `cake_delay_delta_low_threshold_us`).
**Rule:** `_<key>_explicit = "<key>" in <subsection_dict>` — NEVER value-derived. Phase 200 Codex pre-review caught the value-derived regression; Phase 201 must not reopen it.

### Categorical Direction / Categorical Threshold (Phase 197 corroborator)
**Source:** `src/wanctl/wan_controller.py:2760-2772` (`_classify_direction`) and `:2823-2848` (queue-primary AND-gate).
**Apply to:** `_is_cake_aligned_for_pushup` in `QueueController`. Backlog and delay-delta are compared against categorical thresholds; never µs/ms ratio (Phase 200 RETRO 2026-04-23 Codex pushback).
**Cold-start veto:** `cake.cold_start=True → return False` (conservative; RESEARCH Pitfall 4).

### `self.logger` for Per-WAN INFO/WARNING
**Source:** `src/wanctl/wan_controller.py:443-452` (Phase 200 D-06 INFO log).
**Apply to:** every new INFO/WARNING line added in Phase 201.
**Anti-pattern:** `logging.getLogger(__name__).info(...)` — module logger has NO handlers in production; messages silently drop. Phase 200 Plan 01 Task 2 bug (`417e2b9`).

### `getattr(config, "<key>", <default>)` Constructor Plumbing
**Source:** `src/wanctl/wan_controller.py:415-417` (existing `consecutive_yellow_decay_clamp` plumbing).
**Apply to:** every new Phase 201 keyword arg passed to `QueueController(...)`. Default value MUST preserve byte-identical legacy behavior (D-17). For `docsis_mode`: `getattr(config, "docsis_mode", False)`.

### Flash-Wear Protection (do NOT touch)
**Source:** `src/wanctl/wan_controller.py:467-468` and downstream router-write layer.
**Apply to:** Phase 201 setpoint clamp must NOT bypass `last_applied_ul_rate` dedup. Dedup lives at the router-write layer, NOT inside `QueueController`. RESEARCH Pitfall 6: regression test required — `TestPhase201FlashWear::test_steady_state_no_router_writes`.

### `enforce_rate_bounds(rate, floor, ceiling)` Outer Envelope
**Source:** `src/wanctl/queue_controller.py:131` (`enforce_rate_bounds(new_rate, floor=self.floor_red_bps, ceiling=self.ceiling_bps)`).
**Apply to:** setpoint clamp lives ABOVE this call, not in place of it. After the clamp returns a rate, `enforce_rate_bounds` still applies floor/ceiling guard rails.

### Env-Var-Declared Expectation + SSH+YAML Cross-Check
**Source:** `scripts/phase200-saturation-canary.sh:314-362` (43838f4 fix pattern).
**Apply to:** D-12 canary preflight extension AND D-15 predeploy gate. Same shape: env declares expectation, SSH probe parses deployed YAML via `python3 -c "import yaml; yaml.safe_load(...)"`, ABORT on mismatch with `write_abort_verdict "<reason>"`.

### `/health` Additive-Only (D-16)
**Source:** `src/wanctl/wan_controller.py:4490-4530` (existing `cake_signal` block).
**Apply to:** all Phase 201 telemetry. NEW fields nested under `.wans[].upload.*`; existing keys untouched. Runtime state only — no config echo. Tested via curl-pattern, NOT JSON fixture (RESEARCH §7 Wave 0 gap; Phase 200 RETRO Lesson 1).

### KNOWN_AUTORATE_PATHS Registration (SAFE-06)
**Source:** `src/wanctl/check_config_validators.py:28-200`.
**Apply to:** every Phase 201 YAML key. Forgetting a key produces SAFE-06 unknown-key warnings on production startup. Phase 200 closed this gap; Phase 201 must not reopen it.

### Replay-Test Harness Shape (Phase 197 mirror)
**Source:** `tests/test_phase_197_replay.py:1-100`.
**Apply to:** `tests/test_phase_201_replay.py` — fixtures, `_queue_snapshot` helper, `WANController` MagicMock pattern, `_prepare_queue_primary_controller` analog. Replay corpus loaded from in-tree NDJSON (`.planning/phases/200-.../canary/20260504T133207Z/loaded_capture.ndjson`).

---

## No Analog Found

Files with no close match in the codebase (planner should use RESEARCH.md patterns directly):

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| `scripts/phase201-predeploy-gate.sh` (NEW) | shell / preflight | event-driven | Net-new responsibility (rejected-key inspection separate from canary preflight). RESEARCH §9 Option α — borrow SSH+YAML+jq mechanics from canary script lines 314-362 but the gate's contract is novel. |
| `tests/test_phase201_predeploy_gate.py` (NEW) | shell-integration test | event-driven | No existing predeploy-gate test analog. Closest is `tests/test_phase200_canary_script.py` (canary preflight); planner uses that as scaffolding shape but gate-specific assertions are new. |

---

## Metadata

**Analog search scope:**
- `src/wanctl/queue_controller.py`, `wan_controller.py`, `cake_signal.py`, `autorate_config.py`, `check_config_validators.py`, `rate_utils.py`
- `configs/spectrum.yaml`
- `scripts/phase200-saturation-canary.sh`, `phase200-saturation-canary.env.example`
- `tests/test_queue_controller.py`, `test_wan_controller.py`, `test_autorate_config.py`, `test_check_config.py`, `test_phase_197_replay.py`, `test_phase_195_replay.py`, `test_phase200_canary_script.py`
- `.planning/phases/200-.../canary/20260504T133207Z/` (replay corpus)

**Files Read-verified during pattern extraction:**
- `queue_controller.py:1-280` — full file under 2000 lines, single Read
- `wan_controller.py:390-455, 1340-1400, 1880-1900, 2740-3000, 4490-4530` — five non-overlapping targeted reads
- `check_config_validators.py:1-200, 380-455` — two non-overlapping reads
- `autorate_config.py:1-75, 170-201, 355-440` — three non-overlapping reads
- `cake_signal.py:80-170` — single targeted read
- `configs/spectrum.yaml:50-100` — single read
- `scripts/phase200-saturation-canary.sh:1-100, 300-380` — two non-overlapping reads
- `scripts/phase200-saturation-canary.env.example:1-58` — full file
- `tests/test_phase_197_replay.py:1-100` — header read
- `tests/test_phase_195_replay.py:620-678` — targeted read
- `tests/test_queue_controller.py:1-160` — header + fixtures read

**Pattern extraction date:** 2026-05-04
