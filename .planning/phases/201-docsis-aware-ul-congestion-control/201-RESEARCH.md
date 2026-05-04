# Phase 201: DOCSIS-Aware UL Congestion Control - Research

**Researched:** 2026-05-04
**Domain:** Adaptive shaping control loop for DOCSIS upstream — windowed RTT integral as headroom probe; setpoint clamp pre-classifier; CAKE-backlog secondary corroborator
**Confidence:** HIGH on integration points (codebase verified); MEDIUM on integral window sizing (no live evidence yet); LOW-MEDIUM on D-09 setpoint = 12 Mbit (sweep evidence challenges this — see Section 4)

## Summary

Phase 201 introduces a DOCSIS-aware UL control mode behind a YAML opt-in (`continuous_monitoring.upload.docsis_mode: true`). Three things change inside the upload `QueueController` when the flag is on: (1) a **windowed RTT-integral classifier** replaces (or augments) the existing one-sample RTT-delta classifier in `_classify_zone_3state()`; (2) a **setpoint clamp** sits above `_compute_rate_3state()` so the controller's natural attractor becomes `setpoint_mbps`, and the ceiling becomes a guard rail that only the headroom probe can lift toward; (3) the **CAKE backlog/queue-delay-delta** signal is consumed as a categorical direction-aligned veto — push-toward-ceiling requires RTT integral low for a sustained window AND CAKE direction-aligned. None of this needs new transport, new netlink wiring, or new signal collection. Phase 197's `dl_cake_for_arbitration` pattern (`wan_controller.py:2860-2910`) is a near-exact mirror for the corroborator and should be reused, not reinvented.

The most surprising finding: **the operator-evidence file `spectrum-inline-native-18-upload-test-2026-04-29.md` already named this exact failure mode and recommended the controller-side fix that Phase 201 is now shipping.** The `recovery_held_by_backlog` reason was firing during the 30s saturated test, the controller "repeatedly fell from 18Mbit to the 8Mbit floor", and the recommendation was "an upload-specific control mode that is less eager to collapse to floor during saturated upload if CAKE backlog is controlled" — a one-sentence specification of D-02/D-03/D-04. Phase 200's per-direction-thresholds approach treated this evidence as motivation for *threshold widening*; the evidence was actually pointing at *control-model replacement*. Phase 201 closes the loop.

The second risk-relevant finding: **D-09's `setpoint_mbps: 12` is not directly supported by any of the three Spectrum sweep notes**, and `spectrum-upload-ceiling-sweep-2026-04-29.md` explicitly recommended keeping ceiling at 28 Mbit (later overridden by latency-first decisions). The 12 Mbit value is a *60% rule of thumb* against estimated provisioned upstream rate (~20 Mbit), not a sweep result. See Section 4 — researcher recommends defending this as an explicit assumption, not citing the sweeps as supporting evidence.

**Primary recommendation:** Augment, don't replace, the existing `_classify_zone_3state()` — keep RTT-delta as the fast-trip RED path (immediate decay is a CLAUDE.md control-model invariant that must not be lost), add the RTT-integral as a separate **headroom-probe gate** that lifts the setpoint clamp toward ceiling. CAKE-backlog corroborator mirrors Phase 197's `_select_dl_primary_scalar_ms()` arbitration shape, AND-gated with the integral. Window for the integral: **2 s primary (40 cycles at 50 ms)**, matching the existing `consecutive_yellow_decay_clamp=40` time horizon already validated in Phase 200 Plan 200-10 R3.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| VALN-06 | Spectrum UL saturation gate canary `ul_floor_hits_during_load=0` AND 24h soak UL hysteresis suppression `<5/60s`. Inherited blocking from Phase 200. | Sections 3 (setpoint clamp design — why floor cannot be reached), 4 (setpoint value defensibility), 8 (replay corpus from Phase 200 canary captures), 7 (Validation Architecture / Nyquist gate map). |
</phase_requirements>

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** Single phase, signal locked at SPEC time. NOT a `/gsd-spike` first.
- **D-02:** DOCSIS-aware UL mode runs a **conservative YAML setpoint** as operating point, well below ceiling. YAML opt-in `continuous_monitoring.upload.docsis_mode: true`; absent or `false` preserves byte-identical legacy behavior.
- **D-03:** **Headroom probe = windowed RTT integral.** Replace OR augment (planner decides — researcher recommends AUGMENT, see Section 1).
- **D-04:** **CAKE backlog as direction-aligned secondary corroborator.** Categorical alignment, never µs/ms ratio. Mirrors Phase 197 `dl_cake_for_arbitration` pattern.
- **D-05:** Modem SNMP / DOCSIS HCS counters NOT in scope (defer to v1.43+).
- **D-06:** New keys under `continuous_monitoring.upload.*`, registered in `KNOWN_AUTORATE_PATHS`. Required keys (planner finalizes naming): `docsis_mode`, `setpoint_mbps`, RTT-integral window keys.
- **D-07:** No global default for `setpoint_mbps`. No `setpoint_pct` companion key.
- **D-08:** **Restart-required.** SIGUSR1 reload scope unchanged (dwell/deadband only).
- **D-09:** Spectrum `setpoint_mbps: 12` (CHALLENGEABLE — see Section 4).
- **D-10:** Upload ceiling stays at 18 Mbit; floor stays at 8 Mbit. Phase 200's R5 (`factor_down_yellow=1.0`) and R3 (`consecutive_yellow_decay_clamp=40`) MAY be kept, overridden, or removed (see Section 5).
- **D-11:** Reuse `scripts/phase200-saturation-canary.sh` (do not fork).
- **D-12:** Extend canary preflight YAML cross-check for new keys + add /health DOCSIS-mode probe.
- **D-13:** Zero-floor-hit gate preserved. No relaxation.
- **D-14:** 24h soak watchdog at `<5/60s` (no relaxation/tightening).
- **D-15:** Predeploy gate inspecting `/etc/wanctl/spectrum.yaml` for v1.41-only rejected-hypothesis keys (action shape = planner decision; see Section 9).
- **D-16:** `/health` payload **additive only**, runtime-state semantics. No config-echo fields.
- **D-17:** ATT and non-DOCSIS YAMLs stay byte-identical. Absent `docsis_mode` key preserves legacy 3-state UL behavior verbatim.
- **D-18:** Cross-AI review (Codex pre-review + stop-time review) required, not optional.

### Claude's Discretion

- **D-09 (Spectrum `setpoint_mbps: 12`):** Researcher pick / planner / cross-AI review may challenge against the three Spectrum sweep notes. **Section 4 challenges this** and recommends explicit treatment as an assumption.

### Deferred Ideas (OUT OF SCOPE)

- Modem SNMP / DOCSIS HCS counter signal — v1.43+ only if RTT-integral + CAKE corroborator proves insufficient.
- Tighter soak watchdog `<2/60s` — v1.43+ once steady-state suppression rate established.
- DOCSIS-mode auto-tuning of `setpoint_mbps` — future research/spike candidate.
- Predeploy-gate action shape (strip vs abort) — finalized in PLAN.
- Milestone home (v1.42 solo vs +ATT VALN-05b) — `/gsd-new-milestone` decision.
- VALN-05b ATT cake-primary canary — cross-milestone, gated on v1.39 Phase 191 closure.
- Per-direction DL state-machine changes — DL is healthy.
- ATT, fiber, DSL, non-DOCSIS YAMLs — D-17.
- Live-tunable DOCSIS-mode keys via SIGUSR1 — D-08.
- Global default for `setpoint_mbps` and `setpoint_pct` companion key — D-07.

</user_constraints>

## Project Constraints (from CLAUDE.md)

These are non-negotiable; research recommendations honor all of them. Listed for planner verification.

| Constraint | Source | How Phase 201 Honors |
|------------|--------|----------------------|
| **Stability > safety > clarity > elegance** | CLAUDE.md "Change Policy" | RTT-integral is *augment*, not replace; existing RED fast-trip preserved (Section 1). |
| **Portable controller architecture (NON-NEGOTIABLE)** | CLAUDE.md "Portable Controller Architecture", ARCH-01 in `.planning/intel/arch.md` | All DOCSIS-aware behavior is YAML-gated; no `if wan == 'spectrum'` branching introduced. Default `docsis_mode: false` keeps non-Spectrum byte-identical. |
| **RTT delta drives congestion control, not absolute RTT** | CLAUDE.md "Control Model", ARCH-02 | Integral is computed as integral-of-(load_rtt − baseline_rtt) over window, not integral-of-absolute-RTT. Baseline freeze under load (Section 6) preserved. |
| **Asymmetric rate-change (decreases immediate, increases sustained)** | CLAUDE.md "Control Model", ARCH-03 | Setpoint clamp acts on *increases* only — decreases via RED/YELLOW remain immediate. Headroom probe must show sustained low integral before lifting toward ceiling (mirrors `green_required` shape). |
| **DL=4-state, UL=3-state asymmetric** | ARCH-04 | Phase 201 keeps UL 3-state; integral feeds the existing 3-state classifier, no new state added. |
| **Flash-wear protection: only send rate when value changes** | ARCH-05 | Setpoint clamp produces fewer rate transitions, not more — `last_applied_ul_rate` dedup at the router-write layer is unaffected. New code MUST NOT bypass dedup. |
| **/health payload contract (additive only)** | CLAUDE.md "Health/Observability" | D-16: new fields under `.wans[].upload`, no shape change to existing keys. Phase 200 RETRO bug 2 (`floor_mbps`/`ceiling_mbps` field assumption) is the cautionary tale — config values exposed as runtime state only. |
| **Baseline RTT freeze under load** | ARCH-02; `wan_controller.py:1346-1395` | Section 6 — integral baseline reuses `self.baseline_rtt`; freeze gate lives in `_update_baseline_if_idle()` and is preserved verbatim. |
| **SAFE-06 unknown-key warnings** | Phase 200 ARB-05 + SAFE-06 patterns | Every new YAML key MUST register in `KNOWN_AUTORATE_PATHS` (`check_config_validators.py:28-180`). |
| **Per-key explicit-presence flags** | Phase 200 D-03 (Codex pre-review catch) | `_docsis_mode_explicit` and `_setpoint_mbps_explicit` are presence-based, not value-derived. Mirror at `wan_controller.py:432-437` exactly. |

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|--------------|----------------|-----------|
| Windowed RTT-integral computation | UL `QueueController` (`queue_controller.py`) | — | The integral is direction-aligned to UL only; it travels with the controller that owns UL state. The DL controller MUST NOT be touched (D-17 spirit). |
| Baseline RTT for the integral | `WANController` (`wan_controller.py`) | — | `self.baseline_rtt` already exists and is frozen under load (`_update_baseline_if_idle`, line 1346); a new baseline would violate ARCH-02. |
| Setpoint clamp in rate decision | UL `QueueController._compute_rate_3state()` (`queue_controller.py:229-256`) | `enforce_rate_bounds()` (`rate_utils.py`) | Clamp injects above `enforce_rate_bounds` so floor/ceiling guard rails still apply. Setpoint becomes the new attractor; ceiling becomes ceiling-of-the-headroom-probe. |
| CAKE-backlog corroborator (categorical) | UL `QueueController.adjust()` (already receives `cake_snapshot`) | `CakeSignalSnapshot` fields `backlog_bytes` / `max_delay_delta_us` | Snapshot already plumbed (`wan_controller.py:2978-2984`); reuses Phase 197 categorical pattern (`_classify_direction`, `wan_controller.py:2760-2772`). |
| YAML schema / opt-in flag | `autorate_config.py` (schema), `check_config_validators.py` (KNOWN_AUTORATE_PATHS) | — | Opt-in lives in one place; per-key explicit-presence flags surface to `WANController` constructor. Pattern mirror: `_upload_target_bloat_ms_explicit`. |
| Predeploy gate (D-15) | Shell tooling — `scripts/install.sh` or new `scripts/phase201-predeploy-gate.sh` invoked by `phase200-saturation-canary.sh` preflight | SSH probe of `/etc/wanctl/spectrum.yaml` | Same pattern as Phase 200 `dd67493 → 43838f4` env-vs-YAML cross-check. Not a Python concern. |
| `/health` DOCSIS-mode telemetry | `WANController.get_health_data()` (`wan_controller.py:4510-4511`) | UL `QueueController.get_health_data()` for runtime-state fields | Additive nesting under `.wans[].upload.*`; no existing key is reshaped. |
| Canary verdict + 24h soak watchdog | `scripts/phase200-saturation-canary.sh` (reuse + extend) | Existing soak observability | D-11 reuse; D-12 extends preflight + adds /health DOCSIS-mode probe. |

## Standard Stack

This is a Python-only, in-tree change. No new third-party dependencies. The "stack" here is the existing wanctl control-loop primitives.

### Core
| Library / Module | Version | Purpose | Why Standard |
|------------------|---------|---------|--------------|
| `collections.deque(maxlen=N)` | stdlib (Python 3.11+) | Windowed RTT-delta sample buffer for integral computation | O(1) append + amortized window eviction; standard pattern in this codebase (e.g. `_yellow_decay_streak` is a counter; deque generalizes for a true window). [VERIFIED: stdlib, no install] |
| `wanctl.queue_controller.QueueController` | in-tree | Hosts new integral state + setpoint clamp | This is the integration site (D-04 + D-06). [VERIFIED: `queue_controller.py:139-256`] |
| `wanctl.cake_signal.CakeSignalSnapshot` | in-tree | Source of `backlog_bytes` and `max_delay_delta_us` for D-04 corroborator | Already populated for UL via `_ul_cake_signal.update()` (`wan_controller.py:2758`). No new transport. [VERIFIED: `cake_signal.py:92-123`, `wan_controller.py:2746-2758`] |
| `wanctl.autorate_config.Config` schema | in-tree | New YAML key registration | SAFE-06 contract requires it (`check_config_validators.py:28-180`). [VERIFIED] |

### Supporting
| Module | Purpose | When to Use |
|--------|---------|-------------|
| `wanctl.rate_utils.enforce_rate_bounds` | Floor/ceiling guard rails after rate decision | Setpoint clamp lives ABOVE this; bounds remain the outer envelope. [VERIFIED: `queue_controller.py:131`] |
| `WANController._classify_direction` (Phase 197) | Categorical "worsening / improving / held / unknown" comparator | Reuse this exact helper for the CAKE-backlog corroborator's direction signal. [VERIFIED: `wan_controller.py:2760-2772`] |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `deque(maxlen=N)` for window | Ring-buffer with explicit head/tail indices | Marginal performance gain at the cost of code clarity; not justified at 50 ms cadence × 40-cycle window (1600 ops/s, trivial). |
| Augment-the-classifier shape | Replace-the-classifier shape | Replace risks losing the immediate-RED fast-trip path (CLAUDE.md ARCH-03 invariant). Section 1 recommends augment. |
| Multi-window integral (short + long) | Single fixed window | Multi-window adds tunable surface (two more YAML keys) without a clear evidence-based win. Single 2 s window aligns with existing `consecutive_yellow_decay_clamp=40` time horizon already validated in Plan 200-10 R3. Recommend single window for v1.42; revisit if soak data shows oscillation that a long-window component would damp. |

**Installation:** No external dependencies. Verify Python version:
```bash
.venv/bin/python --version  # Expect 3.11+
```

**Version verification:** Not applicable — all dependencies are stdlib or in-tree.

## Architecture Patterns

### System Architecture Diagram

```
                     ┌────────────────────────────────────────────────────┐
                     │         WANController.run_cycle()                  │
                     │  (wan_controller.py — 50ms cadence, 20Hz)          │
                     └──────────────────────┬─────────────────────────────┘
                                            │
                                            ▼
        ┌─────────────────────────────────────────────────────────────┐
        │  RTT measurement → Hampel → fusion → load_rtt EWMA          │
        │  baseline_rtt updated only when idle (line 1346)            │
        └──────────────────────┬──────────────────────────────────────┘
                               │
                               ▼
        ┌─────────────────────────────────────────────────────────────┐
        │  CAKE stats poll (UL):  CakeSignalProcessor.update()        │
        │  → self._ul_cake_snapshot                                   │
        │    .backlog_bytes, .max_delay_delta_us, .cold_start         │
        └──────────────────────┬──────────────────────────────────────┘
                               │
                               ▼
   ┌───────────────────────────────────────────────────────────────────────┐
   │  effective_ul_load_rtt = _compute_effective_ul_load_rtt()             │
   │  (asymmetry-gate attenuated load_rtt; line 2654-2700)                 │
   └──────────────────────────┬────────────────────────────────────────────┘
                              │
                              ▼
   ┌───────────────────────────────────────────────────────────────────────┐
   │  self.upload.adjust(baseline_rtt, effective_ul_load_rtt,              │
   │                     target_delta, warn_delta, ul_cake)                │
   │  (wan_controller.py:2978; QueueController.adjust())                   │
   └──────────────────────────┬────────────────────────────────────────────┘
                              │
                              ▼   <— PHASE 201 INTEGRATION ZONE —>
   ┌─────────────────────────────────────────────────────────────────────────┐
   │  IF docsis_mode_explicit AND docsis_mode:                               │
   │                                                                         │
   │     ┌────────────────────────────────────────────────────────────┐      │
   │     │  (a) RTT-INTEGRAL ACCUMULATOR                              │      │
   │     │      append (load_rtt - baseline_rtt) to deque             │      │
   │     │      integral_ms_s = sum(samples) * cycle_interval_sec     │      │
   │     │      → headroom_state in {AVAILABLE, EXHAUSTED}            │      │
   │     └──────────────────────────┬─────────────────────────────────┘      │
   │                                │                                        │
   │                                ▼                                        │
   │     ┌────────────────────────────────────────────────────────────┐      │
   │     │  (b) CAKE-BACKLOG CORROBORATOR (categorical, AND-gated)    │      │
   │     │      cake_aligned = (max_delay_delta_us low                │      │
   │     │                      AND backlog_bytes low)                │      │
   │     │      OR cake_distress = (either above categorical threshold)      │
   │     └──────────────────────────┬─────────────────────────────────┘      │
   │                                │                                        │
   │                                ▼                                        │
   │     ┌────────────────────────────────────────────────────────────┐      │
   │     │  (c) RTT-DELTA RED FAST-TRIP (UNCHANGED — ARCH-03)         │      │
   │     │      if delta > warn_delta: return RED + factor_down       │      │
   │     │      Decay still immediate; integral does NOT delay it.    │      │
   │     └──────────────────────────┬─────────────────────────────────┘      │
   │                                │                                        │
   │                                ▼                                        │
   │     ┌────────────────────────────────────────────────────────────┐      │
   │     │  (d) ZONE CLASSIFICATION                                   │      │
   │     │      Existing _classify_zone_3state output (GREEN/Y/RED)   │      │
   │     │      OVERLAID with headroom_state to gate push-to-ceiling. │      │
   │     └──────────────────────────┬─────────────────────────────────┘      │
   │                                │                                        │
   │                                ▼                                        │
   │     ┌────────────────────────────────────────────────────────────┐      │
   │     │  (e) RATE DECISION + SETPOINT CLAMP                        │      │
   │     │      raw_rate = _compute_rate_3state(zone)                 │      │
   │     │      if zone == GREEN AND headroom_AVAILABLE AND           │      │
   │     │         cake_aligned:                                      │      │
   │     │          rate = min(raw_rate, ceiling)  # push toward ceil │      │
   │     │      else:                                                 │      │
   │     │          rate = min(raw_rate, setpoint_bps)                │      │
   │     │      rate = enforce_rate_bounds(rate, floor, ceiling)      │      │
   │     └──────────────────────────┬─────────────────────────────────┘      │
   │                                                                         │
   │  ELSE (legacy path — byte-identical):                                   │
   │     existing zone = _classify_zone_3state(delta, target, warn, cake)    │
   │     existing rate = _compute_rate_3state(zone)                          │
   │     rate = enforce_rate_bounds(rate, floor, ceiling)                    │
   └─────────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
   ┌───────────────────────────────────────────────────────────────────────┐
   │  Router write (flash-wear-protected via last_applied_ul_rate dedup)   │
   └───────────────────────────────────────────────────────────────────────┘
```

### Recommended Project Structure

```
src/wanctl/
├── queue_controller.py         # NEW: integral state + setpoint clamp inside QueueController
│                                  Add (in __init__):
│                                    - self._docsis_mode (bool)
│                                    - self._setpoint_bps (int|None)
│                                    - self._integral_window (deque)
│                                    - self._integral_window_size (int)
│                                    - self._integral_threshold_ms_s (float)
│                                  Add (in adjust()):
│                                    - integral update path BEFORE classify
│                                    - cake-aligned check via max_delay_delta_us / backlog_bytes
│                                    - setpoint clamp pre-output
├── autorate_config.py          # NEW: schema entries + presence flags
├── check_config_validators.py  # NEW: KNOWN_AUTORATE_PATHS additions + ordering check
├── wan_controller.py           # NEW: docsis_mode plumbing through Upload QueueController constructor (line 402-418)
│                                    + /health additive fields (line 4510)
└── cake_signal.py              # UNCHANGED — fields already populated

scripts/
├── phase200-saturation-canary.sh  # EXTEND: preflight YAML cross-check (line 314-358)
│                                    + /health DOCSIS-mode-active probe before saturation
├── phase200-saturation-canary.env.example  # ADD: PHASE201_SETPOINT_MBPS + PHASE201_DOCSIS_MODE
└── phase201-predeploy-gate.sh     # NEW (or inline in install.sh): inspect /etc/wanctl/spectrum.yaml
                                     for v1.41-only rejected-hypothesis keys; reconcile or fail closed

tests/
├── test_queue_controller.py    # NEW: TestDocsisModeIntegralClassifier
│                                       TestDocsisModeSetpointClamp
│                                       TestDocsisModeCakeCorroborator
├── test_autorate_config.py     # NEW: docsis_mode/setpoint_mbps validation, missing-required,
│                                       SAFE-06 byte-identity baseline re-establishment
├── test_phase_201_replay.py    # NEW: replay corpus from Phase 200 Attempt 3 canary
│                                       (or freshly captured during 201 canary)
└── test_phase200_canary_script.py # EXTEND: preflight cross-check tests for new env vars
```

### Pattern 1: Per-Key Explicit-Presence Flags (Phase 200 D-03 mirror)

**What:** Each new YAML key has an explicit-presence flag stored on the Config object (e.g. `_docsis_mode_explicit`, `_setpoint_mbps_explicit`). The flag is `True` if and only if the operator wrote the key in YAML — never derived from the value.
**When to use:** Any time live-tuning, classifier-swap, or behavior-gate decision depends on operator intent vs default.
**Why critical:** Phase 200 Codex pre-review caught a value-derived flag bug (`_upload_thresholds_explicit` was set when value differed from DL global, which silently failed when an operator coincidentally set UL key equal to DL global). Per-key presence-based is the only correct shape.
**Example:**
```python
# Source: src/wanctl/wan_controller.py:432-452 (mirror exactly)
self._docsis_mode_explicit = getattr(config, "_docsis_mode_explicit", False)
self._setpoint_mbps_explicit = getattr(config, "_setpoint_mbps_explicit", False)
# One-shot INFO log when operator opts in (mirror Phase 200 D-06 pattern)
if self._docsis_mode_explicit and config.docsis_mode:
    self.logger.info(  # MUST be self.logger, not module logger — Phase 200 Plan 01 bug
        "phase201 docsis_mode active: setpoint_mbps=%s integral_window_s=%s",
        config.setpoint_mbps, config.integral_window_seconds,
    )
```

### Pattern 2: Categorical CAKE Corroborator (Phase 197 mirror)

**What:** CAKE backlog and queue-delay-delta consumed as direction labels (`worsening / improving / held / unknown`) and categorical thresholds (`high / low`). Never µs/ms ratios; never magnitude scoring.
**When to use:** Any time a queue-side signal must AND-gate (or veto) an RTT-side decision.
**Why critical:** Phase 200 RETRO 2026-04-23 Codex pushback explicitly forbade µs/ms ratio scoring — CAKE delays are bursty and one-sided; ratios drift unpredictably. Categorical alignment is the only durable shape.
**Example:**
```python
# Source: src/wanctl/wan_controller.py:2760-2772 (use _classify_direction verbatim)
def _is_cake_aligned_for_pushup(self, cake: CakeSignalSnapshot | None) -> bool:
    """Categorical AND-gate: backlog low AND max_delay_delta_us low."""
    if cake is None or cake.cold_start:
        return False  # Conservative: no signal → no pushup
    backlog_low = cake.backlog_bytes <= self._cake_backlog_low_threshold_bytes
    delay_delta_low = cake.max_delay_delta_us <= self._cake_delay_delta_low_threshold_us
    return backlog_low and delay_delta_low
```

### Pattern 3: Setpoint as Soft Attractor, Not Hard Cap

**What:** `setpoint_mbps` is the rate the controller drifts toward when conditions are unremarkable. The headroom probe lifts the effective ceiling toward `ceiling_mbps` only when both RTT-integral and CAKE corroborator signal "available". When load returns, the controller drifts back toward setpoint (not back to floor).
**When to use:** This IS the Phase 201 control model. (Section 3 details.)
**Why critical:** The shaping-headroom diagnosis (Phase 200 RETRO) says the CMTS upstream queue fills at rates near provisioned. Setpoint sits below provisioned and gives wanctl's CAKE qdisc room to absorb bufferbloat *before* the CMTS does. Without a setpoint attractor, the controller will keep probing toward ceiling and oscillate (Phase 200 Attempt 2: 53% at ceiling / 14% at floor / 33% transitional).

### Anti-Patterns to Avoid

- **Using a separate baseline for the integral.** Don't. `self.baseline_rtt` is the only baseline; it's already frozen under load by ARCH-02 invariant. Adding a second baseline duplicates the freeze logic and creates drift surfaces.
- **µs/ms ratio thresholds for CAKE corroborator.** Phase 200 RETRO line forbids it. Categorical only.
- **Replacing the immediate RED fast-trip.** ARCH-03 says rate decreases are immediate. The integral can ADD a slow-pushup gate; it MUST NOT delay an existing RED.
- **Live-tuning DOCSIS-mode keys via SIGUSR1.** D-08: restart-required. SIGUSR1 path at `wan_controller.py:1894-1899` covers fusion only.
- **Deriving the explicit-presence flag from value comparisons.** Phase 200 Codex pre-review catch. Per-key presence-based, never value-derived.
- **Adding config-echo fields to `/health`.** Phase 200 Plan 05 bug 2: `/health.wans[].upload.{floor_mbps,ceiling_mbps}` were assumed to exist; they don't, because `/health` carries runtime state only. Phase 201 must expose `setpoint_mbps` as the rate the controller is *currently using*, not the YAML value.
- **Using module-scope logger for D-06 INFO line.** Phase 200 Plan 01 Task 2 bug: `logging.getLogger(__name__)` has no handlers in production; messages silently drop. Use `self.logger`.
- **Forking the canary script.** D-11: extend, don't fork. The Phase 200 script's bug-fix history (logger silent-drop, /health field assumption, env-var false-PASS regression) is not transferable.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Direction classifier (worsening/improving/held) | New comparator helper | `WANController._classify_direction()` (`wan_controller.py:2760-2772`) | Phase 197 already established the categorical-only shape; adding a parallel helper risks divergence in semantics. |
| Floor/ceiling guard rails on rate decision | New min/max in `QueueController` | `enforce_rate_bounds(rate, floor, ceiling)` from `wanctl.rate_utils` | Already used at `queue_controller.py:131`; setpoint clamp goes ABOVE it, not in place of it. |
| Windowed sample buffer with O(1) eviction | List-with-index pointer | `collections.deque(maxlen=N)` | stdlib, idiomatic Python, naturally evicts oldest on append. |
| YAML schema validation | New validator | `autorate_config.SCHEMA` entry + `KNOWN_AUTORATE_PATHS` registration | Existing schema layer already enforces type/min/max + SAFE-06 unknown-key warning. |
| YAML ordering check | New ordering helper | `validate_threshold_order()` from `config_validation_utils` | Existing pattern at `check_config_validators.py:389-453` for upload/global thresholds. |
| Predeploy SSH-based YAML probe | New tool | Mirror the pattern at `scripts/phase200-saturation-canary.sh:314-358` (43838f4 fix) | Same fail-closed shape: env declares expectation, SSH probe parses YAML, ABORT on mismatch. |
| Categorical cake-aligned veto | New corroborator | Mirror `_select_dl_primary_scalar_ms()` (`wan_controller.py:2800-2858`) | Phase 197 proved the shape under DL Plan 197-02; mirror for UL. |
| Replay-test corpus capture | New capture tool | Reuse `scripts/phase200-saturation-canary.sh` `loaded_capture.ndjson` output (already 1Hz `/health` sampling) | Phase 200 already captures the right frame shape; Phase 201 only needs to extend to also capture per-cycle `rtt_delta_ms` and CAKE backlog samples (current sampling is 1 Hz; integral wants 20 Hz — see Section 8). |

**Key insight:** Almost everything Phase 201 needs is already in the codebase as a Phase 197 / Phase 200 pattern. The temptation to build a "proper integral controller from scratch" should be resisted. The right shape is: tiny integral computation inside `QueueController.adjust()`, tiny clamp inside `_compute_rate_3state()`, AND-gate via existing `_classify_direction` + categorical thresholds. Total new code surface in `queue_controller.py` should be under ~80 lines.

## Runtime State Inventory

This phase is NOT a rename/refactor/migration in the strict sense — it's a feature add behind a new YAML opt-in. The only "rejected-hypothesis state in production" item is the predeploy gate scope (D-15), which IS a runtime-state inventory concern.

| Category | Items Found | Action Required |
|----------|-------------|-----------------|
| **Stored data** | None — `/var/lib/wanctl/spectrum_state.json` is EWMA + counters, no schema migration needed. New `current_rate` initialization is `ceiling`; setpoint mode just reduces toward setpoint on first cycles. | None |
| **Live service config (rejected-hypothesis state from v1.41)** | `/etc/wanctl/spectrum.yaml` on production deploy target carries inactive v1.41-only keys (`continuous_monitoring.upload.target_bloat_ms`, `warn_bloat_ms`, `consecutive_yellow_decay_clamp`, `factor_down_yellow=1.0`). These are the rejected-hypothesis state that Phase 200 RETRO `## Final Closure` flagged as MUST-reconcile-before-redeploy. | **D-15 predeploy gate** must inspect and either (a) auto-reconcile per Phase 201's design choice on R5/R3 (Section 5) or (b) fail closed with operator-actionable abort message. **Researcher recommends fail-closed-with-explicit-operator-action** — auto-strip is irreversible and the keys MAY be retained in modified form (Section 5). |
| **OS-registered state** | `wanctl@spectrum.service` is the only systemd unit referencing the WAN. No service rename. | None — restart-required for new keys (D-08), but the unit name stays. |
| **Secrets/env vars** | `PHASE200_*` env-var family in `phase200-saturation-canary.env.example` plus operator's local env file. New env vars needed: `PHASE201_SETPOINT_MBPS`, `PHASE201_DOCSIS_MODE` (D-12). Operator-local secrets unaffected. | Plan must specify env-var name additions and update example file. |
| **Build artifacts** | Version bump from 1.41.0 → 1.42.0 in `pyproject.toml`, `src/wanctl/__init__.py`, `docker/Dockerfile`. | Version bump task + CHANGELOG.md v1.42.0 entry. |

**The canonical question for Phase 201:** *After every file is updated and the v1.42 binary is deployed, what runtime state still references the rejected v1.41 hypothesis?* Answer: only `/etc/wanctl/spectrum.yaml` itself, which is the D-15 predeploy gate's exact target. Nothing else in the system caches or registers the rejected-hypothesis state.

## Common Pitfalls

### Pitfall 1: Replacing the RED fast-trip with the integral
**What goes wrong:** Operator sees pretty integral graphs and decides RED can be derived from "integral above high threshold". The 50 ms cycle interval is then ratcheted up to ~2 s minimum reaction time on a real congestion event.
**Why it happens:** Integral is conceptually elegant and looks like a generalization of the delta classifier.
**How to avoid:** Treat the integral as a *headroom probe for pushing UP*, not a replacement for the *RED fast-trip going DOWN*. ARCH-03 invariant: rate decreases immediate. RED path stays exactly as it is in `_classify_zone_3state` lines 147-153.
**Warning signs:** Test that asserts "integral above threshold → RED zone" instead of "integral above threshold → headroom_EXHAUSTED".

### Pitfall 2: Setpoint clamp under floor (or above ceiling)
**What goes wrong:** Operator sets `setpoint_mbps=4` but `floor_mbps=8`. Or `setpoint_mbps=20` but `ceiling_mbps=18`. Without ordering validation, controller silently clamps to floor or ceiling and the setpoint is dead config.
**Why it happens:** No ordering check between setpoint and floor/ceiling. Phase 200's threshold-ordering validator only handles target_bloat < warn_bloat.
**How to avoid:** Add `floor_mbps < setpoint_mbps < ceiling_mbps` ordering check in `_validate_upload_threshold_ordering` (mirror of existing pattern at `check_config_validators.py:408-453`). Validator fail-closed if violated.
**Warning signs:** `enforce_rate_bounds` is doing all the work; setpoint never visibly affects rate.

### Pitfall 3: Integral baseline drift under sustained load
**What goes wrong:** The RTT-integral is computed as integral-of-(load_rtt − baseline_rtt). If `baseline_rtt` drifts upward during sustained load (because the freeze gate is bypassed somehow), the integral collapses to ~zero and signals "headroom available" forever. Controller pushes to ceiling, hits floor, oscillates.
**Why it happens:** ARCH-02 freeze gate is implicit; new code might inadvertently update baseline from a path that doesn't go through `_update_baseline_if_idle`.
**How to avoid:** Section 6 — DO NOT introduce a parallel baseline. Reuse `self.baseline_rtt` exactly. Add a regression test that holds `baseline_rtt` constant at 22.0 ms across the full 60-cycle sustained-load synthetic trace and asserts the integral monotonically increases. (See Validation Architecture Section 7.)
**Warning signs:** Integral graph trends *down* during sustained load (it should trend up if baseline is frozen).

### Pitfall 4: CAKE corroborator at cold-start veto-deny
**What goes wrong:** First few cycles after daemon start, `cake_snapshot.cold_start=True`. If the corroborator returns "aligned" on cold-start, the controller pushes to ceiling immediately, hits the CMTS queue while wanctl's qdisc is empty, and oscillates from cycle 1.
**Why it happens:** CAKE EWMA needs warm-up; cold-start values are stale or zero.
**How to avoid:** Treat `cold_start=True` as **conservative / not-aligned**. The controller stays at setpoint for ~1 cycle (50 ms) — operationally invisible.
**Warning signs:** Test that asserts "cold_start → aligned" — flip it.

### Pitfall 5: One-shot INFO log uses module logger
**What goes wrong:** D-06 verification grep on production journal returns zero matches. Operator concludes the feature didn't deploy. Actually it deployed fine — the log line silently dropped.
**Why it happens:** Phase 200 Plan 01 Task 2 bug (`logging.getLogger(__name__)` has no handlers in production).
**How to avoid:** Use `self.logger` (the per-WAN configured logger passed to `WANController.__init__`). Test the log emission against the configured logger, not a module-scope mock.
**Warning signs:** Any new `logger.info`/`logger.warning` line in `queue_controller.py` or `wan_controller.py` not using `self.logger` or an explicitly-injected logger.

### Pitfall 6: Setpoint clamp bypasses last_applied_ul_rate dedup
**What goes wrong:** Setpoint clamp produces a stable rate close to (but not equal to) the previous applied rate. Without dedup, every cycle writes to the router → flash wear.
**Why it happens:** New rate-decision path that doesn't go through the existing `last_applied_ul_rate` check at the router-write layer.
**How to avoid:** ARCH-05 invariant: `last_applied_ul_rate` lives at the router-write layer (NOT inside `QueueController`). Setpoint clamp produces a rate; the router-write layer dedups. Phase 201 MUST NOT touch the dedup path.
**Warning signs:** Production CAKE-apply log shows continuous writes during steady-state load.

### Pitfall 7: /health DOCSIS-mode probe fails on absent key
**What goes wrong:** The canary preflight (D-12) probes `/health.wans[0].upload.docsis_mode_active` before saturation. On a non-Spectrum or pre-deploy `/health`, this key is absent and the probe fails with "shape invalid". Canary aborts when it should proceed (in dev) or proceeds when it should abort (in prod).
**Why it happens:** Phase 200 Plan 05 bug 2 family — assuming `/health` keys exist before they ship.
**How to avoid:** D-12 probe MUST distinguish "key absent → canary ABORT, deploy didn't happen" vs "key present and `false` → canary ABORT, deploy is wrong WAN" vs "key present and `true` → proceed". Three branches, all explicit.
**Warning signs:** Probe logic uses jq's `?` operator without explicit branches.

## Code Examples

Verified patterns from in-tree sources:

### Per-Key Explicit-Presence Flag (Phase 200 D-03 mirror)
```python
# Source: src/wanctl/wan_controller.py:432-437 (verified VERIFIED)
# In WANController.__init__ (around line 402-418 — Upload QueueController constructor):
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
    # NEW Phase 201 args:
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
self._docsis_mode_explicit = getattr(config, "_docsis_mode_explicit", False)
self._setpoint_mbps_explicit = getattr(config, "_setpoint_mbps_explicit", False)
if self._docsis_mode_explicit and getattr(config, "docsis_mode", False):
    self.logger.info(  # MUST be self.logger — Phase 200 Plan 01 Task 2 bug
        "phase201 docsis_mode active: setpoint_mbps=%s window_s=%s threshold_ms_s=%s",
        config.setpoint_mbps,
        config.integral_window_seconds,
        config.integral_threshold_ms_s,
    )
```

### Integral Window Update (planner-finalized shape)
```python
# Source: planner-authored, in src/wanctl/queue_controller.py
# Inside QueueController.adjust(), before _classify_zone_3state:
def _update_integral(self, delta_ms: float) -> tuple[float, str]:
    """Append delta sample, return (integral_ms_s, headroom_state).

    headroom_state in {"AVAILABLE", "EXHAUSTED"}.
    AVAILABLE iff integral has been below threshold for full window.
    """
    self._integral_window.append(max(0.0, delta_ms))
    # integral over window = sum of samples * cycle_interval_seconds
    integral_ms_s = sum(self._integral_window) * 0.05  # 50ms cycle
    if len(self._integral_window) < self._integral_window.maxlen:
        # Window not yet full — be conservative (EXHAUSTED == do not push up)
        return integral_ms_s, "EXHAUSTED"
    if integral_ms_s <= self._integral_threshold_ms_s:
        return integral_ms_s, "AVAILABLE"
    return integral_ms_s, "EXHAUSTED"
```

### CAKE Corroborator (categorical, Phase 197 mirror)
```python
# Source: src/wanctl/wan_controller.py:2760-2772 (re-used) + new inside QueueController
def _is_cake_aligned_for_pushup(
    self, cake: CakeSignalSnapshot | None
) -> bool:
    """Return True iff CAKE direction-aligns with 'headroom available'.

    Categorical AND-gate. Phase 197 RETRO 2026-04-23: never µs/ms ratio.
    Cold start is conservative (returns False).
    """
    if cake is None or cake.cold_start:
        return False
    backlog_low = cake.backlog_bytes <= self._cake_backlog_low_threshold_bytes
    delay_low = cake.max_delay_delta_us <= self._cake_delay_delta_low_threshold_us
    return backlog_low and delay_low
```

### Setpoint Clamp Inside _compute_rate_3state (planner-finalized)
```python
# Source: planner-authored, modifying src/wanctl/queue_controller.py:229-256
def _compute_rate_3state(self, zone: str) -> int:
    """Existing logic preserved verbatim; setpoint clamp added at end."""
    if self.red_streak >= 1:
        self._yellow_decay_streak = 0
        return int(self.current_rate * self.factor_down)  # immediate decay UNCHANGED
    if self.green_streak >= self.green_required:
        self._yellow_decay_streak = 0
        raw_rate = self.current_rate + self._compute_probe_step()
    elif zone == "YELLOW":
        if (
            self.consecutive_yellow_decay_clamp > 0
            and self._yellow_decay_streak >= self.consecutive_yellow_decay_clamp
        ):
            return self.current_rate
        self._yellow_decay_streak += 1
        return int(self.current_rate * self.factor_down_yellow)
    else:
        self._yellow_decay_streak = 0
        return self.current_rate

    # NEW Phase 201: setpoint clamp on push-up only (decreases unaffected)
    if self._docsis_mode and self._setpoint_bps is not None:
        if not (self._headroom_available and self._cake_aligned):
            # Headroom not confirmed → clamp upward push at setpoint
            return min(raw_rate, self._setpoint_bps)
    return raw_rate
```

### YAML Ordering Check Mirror
```python
# Source: src/wanctl/check_config_validators.py:408-453 (existing pattern)
def _validate_docsis_mode_setpoint(cm: dict) -> list[CheckResult]:
    """Validate docsis_mode requires setpoint_mbps; floor < setpoint < ceiling."""
    ul = cm.get("upload", {})
    if not ul.get("docsis_mode", False):
        return []  # Opt-out path: byte-identical legacy
    setpoint = ul.get("setpoint_mbps")
    if setpoint is None:
        return [CheckResult(
            "Cross-field Checks", "continuous_monitoring.upload",
            Severity.ERROR,
            "docsis_mode: true requires setpoint_mbps (validator fails closed; D-06)",
        )]
    floor = ul.get("floor_mbps")  # or floor_red_mbps depending on schema variant
    ceiling = ul.get("ceiling_mbps")
    if floor is not None and not (float(floor) < float(setpoint)):
        return [CheckResult(
            "Cross-field Checks", "continuous_monitoring.upload.setpoint_mbps",
            Severity.ERROR,
            f"setpoint_mbps ({setpoint}) must be > floor_mbps ({floor})",
        )]
    if ceiling is not None and not (float(setpoint) < float(ceiling)):
        return [CheckResult(
            "Cross-field Checks", "continuous_monitoring.upload.setpoint_mbps",
            Severity.ERROR,
            f"setpoint_mbps ({setpoint}) must be < ceiling_mbps ({ceiling})",
        )]
    return [CheckResult(
        "Cross-field Checks", "continuous_monitoring.upload.setpoint_mbps",
        Severity.PASS, "DOCSIS-mode setpoint ordering: valid",
    )]
```

## State of the Art

This is a project-internal control loop. "State of the art" here is the Phase 197 / Phase 200 lessons absorbed.

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| RTT-delta classifier as sole UL signal (Phase < 200) | RTT-delta + per-direction thresholds (v1.41) | Phase 200 (rejected 2026-05-04) | 96.7% improvement (122 → 4 floor hits) but did not reach zero. Architecturally diagnosed: shaping headroom dominated, not threshold dominated. |
| Per-direction thresholds (v1.41 rejected) | Setpoint + RTT-integral + CAKE-categorical (v1.42) | Phase 201 (this phase) | Targets zero floor hits by giving wanctl's qdisc shaping headroom below CMTS upstream rate. |
| µs/ms magnitude scoring of CAKE backlog | Categorical direction + threshold (Phase 197) | Phase 197 RETRO 2026-04-23 (Codex pushback) | Phase 201 mirrors this: categorical only. |
| Module-scope `logging.getLogger(__name__)` for INFO | Per-WAN `self.logger` | Phase 200 Plan 01 Task 2 (`417e2b9`) | Phase 201 must use `self.logger` for the D-06 INFO line. |
| `/health` carries config + runtime state | `/health` carries runtime state only | Phase 200 RETRO Plan 05 bug 2 | Phase 201 D-16 exposes `setpoint_mbps` as the rate the controller is using, not the YAML value. |
| Env-var-only canary preflight | Env-var declared expectation + SSH probe of deployed YAML | Phase 200 `dd67493 → 43838f4` | Phase 201 D-12 extends to also cross-check `docsis_mode` + `setpoint_mbps`. |
| Single-AI plan review | Codex pre-review + Codex stop-time review (cross-AI) | Phase 200 RETRO "high-leverage on production-control work" | D-18 makes both required, not optional. |

**Deprecated/outdated (must NOT be reintroduced):**
- Timer-based service model (replaced by `wanctl@.service` units; CLAUDE.md explicit warning).
- `/health` payload-shape changes (additive only; D-16).
- Value-derived explicit-presence flags (Phase 200 D-03 Codex pre-review).

## Detailed Research Findings

### 1. RTT-Integral Classifier Design

**Recommendation: AUGMENT, not replace.** Add the integral as a separate **headroom-probe gate** that interacts with the existing `_classify_zone_3state` decision rather than replacing it.

**Rationale:**
- The existing classifier's RED fast-trip path (lines 147-153) is an ARCH-03 invariant: rate decreases must be immediate. Replacing the classifier risks delaying RED detection by up to one window length (~2 s @ 40 cycles).
- The existing GREEN/YELLOW dwell logic (`_apply_dwell_logic`, lines 202-227) is the byte-identity contract for non-DOCSIS deployments (D-17). Replacing it forces a code path divergence between DOCSIS and non-DOCSIS that is harder to test and verify.
- The integral's actual job is *gating push-to-ceiling*, not classifying distress. The distress signal (delta > target/warn) is already correct; the missing piece is "is the cumulative delta low enough to justify probing past setpoint?"

**Window length: 2.0 s primary (40 cycles at 50 ms)** [VERIFIED: cycle interval = 50 ms in `cake_signal.py:36`, `CYCLE_INTERVAL_SECONDS = 0.05`]
- Aligns with the validated `consecutive_yellow_decay_clamp=40` time horizon from Plan 200-10 R3.
- Long enough to integrate over a full TCP burst recovery cycle.
- Short enough to react inside the 24h soak's 60s suppression-rate window.
- Single window only — multi-window is deferred (Section: Alternatives Considered above).

**Integral metric: time-weighted RTT-over-baseline** `[ASSUMED]`
- Formula: `integral_ms_s = sum(max(0, load_rtt - baseline_rtt) for samples in window) * cycle_interval_seconds`
- Negative deltas clamped to zero — they don't add headroom credit (would over-predict during transient improvements).
- "Threshold-overshoot integral" (only count samples above target_delta) was considered but rejected: it loses fidelity in the YELLOW band where most operationally-interesting headroom decisions live.

**Integral threshold: `integral_threshold_ms_s` (default 30.0)** `[ASSUMED]`
- A 2.0 s window with mean delta 15 ms produces integral = 30.0 ms·s. So default = "average sample at exactly target_delta over full window".
- Below 30 → headroom available, push toward ceiling.
- Above 30 → headroom exhausted, clamp at setpoint.
- This default is a **starting point for canary tuning** — it MUST be validated against the Phase 200 Attempt 3 capture (replay) before deploy. Section 8.

**State machine: `headroom_state in {AVAILABLE, EXHAUSTED}`**
- AVAILABLE only when (a) window fully populated AND (b) integral ≤ threshold AND (c) no cold-start.
- EXHAUSTED is the safe default — fails closed.

**Interaction with existing classifier:**
| Existing zone | headroom_state | cake_aligned | Effective rate decision |
|---------------|----------------|--------------|--------------------------|
| RED | (irrelevant) | (irrelevant) | `factor_down` decay — IMMEDIATE (ARCH-03) |
| YELLOW | (irrelevant) | (irrelevant) | Hold or `factor_down_yellow` per existing R5/R3 logic |
| GREEN + sustained streak | AVAILABLE | True | Lift clamp toward ceiling — push step |
| GREEN + sustained streak | EXHAUSTED | (any) | Clamp at setpoint |
| GREEN + sustained streak | AVAILABLE | False | Clamp at setpoint (CAKE veto) |
| GREEN + non-sustained | (any) | (any) | Hold (existing `green_required` logic) |

### 2. CAKE-Backlog Corroborator Wiring

**Source fields:** `CakeSignalSnapshot.backlog_bytes` and `CakeSignalSnapshot.max_delay_delta_us` [VERIFIED: `cake_signal.py:92-123`].
**Already plumbed:** `_ul_cake_snapshot` is updated each cycle (`wan_controller.py:2746-2758`) and passed to `self.upload.adjust(...)` (line 2978-2984). No new transport.

**Phase 197 `dl_cake_for_arbitration` semantic translation to UL:**
The Phase 197 DL pattern has more sophisticated machinery than UL needs:
- `_select_dl_primary_scalar_ms` (lines 2800-2858) chooses queue-vs-RTT primary based on cake validity, refractory, RTT confidence, direction agreement, and queue distress.
- For UL Phase 201, we don't need full primary-selection: the question is simpler — "is CAKE direction-aligned with 'headroom available'?". This is a single AND-gate, not a 4-condition arbitration.

**Recommended UL shape:**
```python
def _is_cake_aligned_for_pushup(self, cake: CakeSignalSnapshot | None) -> bool:
    if cake is None or cake.cold_start:
        return False  # conservative
    backlog_low = cake.backlog_bytes <= self._cake_backlog_low_threshold_bytes
    delay_low = cake.max_delay_delta_us <= self._cake_delay_delta_low_threshold_us
    return backlog_low and delay_low
```

**Default thresholds (planner-tunable):**
- `cake_backlog_low_threshold_bytes = 5000` — Phase 163 sweep winner for UL detection ([CITED: `configs/spectrum.yaml:221`]); reuse the same threshold for the corroborator.
- `cake_delay_delta_low_threshold_us = 5000` (5 ms) `[ASSUMED]` — no direct evidence; 5 ms is the deadband_ms equivalent and a defensible categorical "low" level. Marked for canary validation.

**AND-coupling logic with RTT-integral:** Push-to-ceiling requires `headroom_AVAILABLE AND cake_aligned`. Either signal alone is insufficient. CAKE alone could miss CMTS-side queueing (CAKE is wanctl-local); RTT-integral alone could miss bursty queue-fill events (CAKE catches faster). The AND-gate honors both signals' strengths.

### 3. Setpoint Clamp Pre-Classifier Design

**Injection point:** Inside `QueueController._compute_rate_3state()` (`queue_controller.py:229-256`), at the *very end* — after the existing zone-based decision but BEFORE the `enforce_rate_bounds` outer envelope at `queue_controller.py:131`.

**Decision tree:**
1. RED zone → `factor_down` decay (immediate, ARCH-03 invariant). Setpoint clamp DOES NOT APPLY. Decay can take rate below setpoint; that's correct.
2. YELLOW zone → existing R5/R3 hold-or-decay logic. Setpoint clamp DOES NOT APPLY. (Setpoint is a push-up clamp, not a hold-up clamp.)
3. GREEN + sustained streak → compute raw push step:
   - If `headroom_AVAILABLE AND cake_aligned`: rate = `current_rate + step` (toward ceiling)
   - Else: rate = `min(current_rate + step, setpoint_bps)` (clamped to setpoint)
4. GREEN non-sustained → hold (existing logic).

**Setpoint as soft attractor (not hard ceiling):**
- The clamp limits *upward* movement only. Downward movement (RED/YELLOW decay) can take rate below setpoint.
- Recovery from sub-setpoint: GREEN streaks step up toward `min(setpoint, ceiling)` first; only when both signals confirm headroom does the controller push past setpoint toward ceiling.
- This produces a stable operating point at setpoint with brief excursions toward ceiling under confirmed headroom — the desired bimodal-suppression behavior.

**Recovery policy when load disappears:**
- Load disappears → CAKE backlog drops to ~zero → integral drops below threshold over next 2 s → headroom_AVAILABLE.
- If `cake_aligned`, controller pushes from setpoint toward ceiling on subsequent GREEN streaks.
- If load returns, GREEN streak breaks → push stops. RED decay (if it triggers) takes rate below setpoint, and the GREEN-streak-back-to-setpoint path applies.
- **Net effect:** controller idles at setpoint with sustained-load handling; under no-load it eventually pushes to ceiling; under transient-load it falls back to setpoint, not floor.

**Setpoint clamp does NOT introduce a new dwell timer.** The existing `green_required=3` dwell already gates push-up cadence on Spectrum.

### 4. Spectrum Setpoint Value (D-09 Challenge)

**Decision: Researcher does NOT challenge D-09's `setpoint_mbps: 12`, but explicitly flags it as `[ASSUMED]` rather than evidence-supported.**

**Sweep evidence audit:**

| Sweep file | What it tested | Conclusion | Bears on D-09? |
|------------|----------------|------------|-----------------|
| `spectrum-target-bloat-sweep-2026-04-15.md` | DL `target_bloat_ms` ∈ {12, 13, 14, 15, 16, 17, 18} | Best at 15 ms | NO — DL only, RTT-threshold space, not UL setpoint space. |
| `spectrum-upload-ceiling-sweep-2026-04-29.md` | UL ceiling ∈ {28, 30, 32, 34, 36} | Keep at 28; 30+ produces multi-second p99 ping spikes | NO — argues UL ceiling SHOULD STAY at 28; later overridden to 18 for latency-first reasons. Does not test setpoint-below-ceiling concept. |
| `spectrum-inline-native-18-upload-test-2026-04-29.md` | UL controller behavior at 18 Mbit ceiling, native vs bypass | Controller collapses 18 → 8 floor under saturation; recommends UL-specific control mode "less eager to collapse to floor during saturated upload if CAKE backlog is controlled" | INDIRECTLY — it specifies the *control-mode* fix (which is what Phase 201 ships) but does NOT test any setpoint value directly. |

**Verdict:** None of the three sweeps tested a setpoint-below-ceiling configuration on Spectrum. **D-09's `12 Mbit` is a 60% rule of thumb against estimated provisioned upstream rate (~20 Mbit), defensible but not measured.** The actual measurement Phase 201 needs is the **canary itself**: zero floor hits at `setpoint=12` with the new control mode.

**Defensibility ladder:**
- **Why 12 is defensible:** ~8 Mbit shaping headroom below estimated provisioned rate; 60% utilization is a conservative starting point matching DOCSIS guidance for sustained flows.
- **Why 14 is defensible:** Closer to ceiling (only 4 Mbit headroom); higher peak UL throughput; but the seed CONTEXT flagged this as same architectural failure mode at smaller amplitude.
- **Why 10 is defensible:** Even more headroom (~10 Mbit); minimizes canary risk but sacrifices peak UL.
- **Why "do another sweep first" is NOT defensible:** D-01 locks single-phase, no spike. The canary IS the sweep.

**Researcher recommendation:**
1. **Keep D-09's `setpoint_mbps: 12`** as the SPEC value, but document in PLAN that this is `[ASSUMED]`, not `[VERIFIED via sweep]`.
2. **If the Phase 201 canary fails at 12,** the next attempt should drop to 10 (not raise to 14). The `[ASSUMED]` framing makes this a parameter-tune, not a hypothesis rejection.
3. **The `current_rate` initialization** in `QueueController.__init__` is currently `ceiling`. When `docsis_mode: true`, it should initialize to `min(ceiling, setpoint)` to avoid a 1-cycle ceiling-touch at daemon startup. Plan should add this as an explicit task.

### 5. Existing v1.41 R5+R3 Disposition

**State on production `/etc/wanctl/spectrum.yaml`:**
- `factor_down_yellow: 1.0` (R5: hold during YELLOW)
- `consecutive_yellow_decay_clamp: 40` (R3: bound consecutive YELLOW decay)
- `target_bloat_ms: 42`, `warn_bloat_ms: 105` (R0: per-direction thresholds)
- Inactive under v1.40 binary post-rollback; will silently reactivate under v1.42 unless reconciled.

**Researcher recommendation: KEEP R5 + R3, REMOVE per-direction thresholds.**

**Reasoning:**
- **R5 (`factor_down_yellow=1.0`)**: Hold-during-YELLOW is *complementary* to setpoint clamp, not redundant. Setpoint clamp gates *push-up*; R5 gates *push-down* during YELLOW. Together they make the controller stable around setpoint. Removing R5 reintroduces the multiplicative YELLOW decay that contributed to the 122-collapse pattern.
- **R3 (`consecutive_yellow_decay_clamp=40`)**: Even with R5=1.0 (no decay), R3 is a backstop against any future tuning that raises `factor_down_yellow` below 1.0. Cheap insurance, no cost. KEEP.
- **R0 (per-direction `target_bloat_ms=42, warn_bloat_ms=105`)**: Phase 200 explicitly REJECTED these values as the wrong hypothesis. They MUST be reconciled before v1.42 deploys. Either:
  - **Strip** (set to absent → fall back to DL globals 15/75): risk that 15 ms target is too tight for UL on Spectrum DOCSIS.
  - **Override** (set to a Phase 201 design choice, e.g., 30/75): this is a *new* hypothesis with no Phase 201 evidence supporting it — out of scope.
  - **Strip** is the conservative option: Phase 200 RETRO concluded thresholds aren't the lever; let UL fall back to global thresholds, which the rest of the codebase has years of operational evidence on.

**Plan should:**
1. Remove `target_bloat_ms: 42` and `warn_bloat_ms: 105` from `configs/spectrum.yaml` upload block.
2. Keep `factor_down_yellow: 1.0` and `consecutive_yellow_decay_clamp: 40`.
3. The D-15 predeploy gate enforces this on `/etc/wanctl/spectrum.yaml`: aborts if `target_bloat_ms` or `warn_bloat_ms` keys are present in `continuous_monitoring.upload`.

### 6. Baseline RTT Freeze Interaction

**Verified mechanism:** `_update_baseline_if_idle()` at `wan_controller.py:1346-1395`. Baseline updates only when `delta < self.baseline_update_threshold` (load_rtt is close to baseline → idle). Under load, delta exceeds threshold → freeze.

**Phase 201 question: Does the integral need a separate baseline?**

**Answer: NO.** Reuse `self.baseline_rtt` exactly.

**Reasoning:**
- The integral is `sum(max(0, load_rtt - baseline_rtt))`, computed every cycle. If `baseline_rtt` is frozen during load (which it is, by ARCH-02), then the integral correctly accumulates the bloat magnitude × time area.
- Adding a parallel baseline (e.g., `_integral_baseline_rtt`) duplicates `_update_baseline_if_idle` logic and creates a second freeze surface. Two freeze gates can drift; one cannot.
- The integral threshold (e.g., 30 ms·s) is calibrated against the existing `baseline_rtt` semantics. A different baseline would require a different threshold, multiplying tuning surface for no benefit.

**Edge case: cold-start baseline.** `baseline_rtt_initial: 22` for Spectrum [VERIFIED: `configs/spectrum.yaml:53`]. On daemon start, `baseline_rtt = 22.0` and the integral begins accumulating with that as reference. If actual idle baseline differs (e.g., 25 ms), integral skews by 3 ms × window_seconds = 6.0 ms·s — well under the 30 ms·s threshold. Operationally invisible.

**Edge case: baseline drift after long uptime.** EWMA with `baseline_time_constant_sec: 50` adapts over ~50 s of idle. Phase 201 controller responds in 2 s window — much faster than baseline drift. No interaction concern.

**Test coverage required (see Validation Architecture):** Hold `baseline_rtt = 22.0` constant across a 60-cycle synthetic load trace; assert integral monotonically increases. This catches any future code path that updates baseline under load.

### 7. Validation Architecture (Nyquist)

> nyquist_validation: true (verified in `.planning/config.json`)

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 7.x with `addopts=''` override pattern (project-standard) |
| Config file | `pyproject.toml` (pytest config under `[tool.pytest.ini_options]`) |
| Quick run command | `.venv/bin/pytest -o addopts='' tests/test_queue_controller.py tests/test_wan_controller.py tests/test_autorate_config.py -q` |
| Full suite command | `.venv/bin/pytest -q` |
| Phase-201 focus slice | `.venv/bin/pytest -o addopts='' tests/test_queue_controller.py tests/test_phase_201_replay.py tests/test_phase200_canary_script.py -q -k 'docsis_mode or setpoint or integral or phase201'` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| VALN-06 | DOCSIS-mode UL canary `ul_floor_hits_during_load=0` at saturation | canary (live system) | `scripts/phase200-saturation-canary.sh` (extended per D-12) | YES (extend) |
| VALN-06 | 24h Spectrum UL regression soak with UL hysteresis suppression `<5/60s` | soak (live system) | `scripts/phase200-saturation-canary.sh` soak branch | YES (reuse) |
| VALN-06 | Replay-test of Phase 200 Attempt 3 canary failure trace passes through new controller without floor hits | replay (synthetic) | `pytest tests/test_phase_201_replay.py::TestAttempt3ReplayWithDocsisMode::test_no_floor_hits -x` | ❌ Wave 0 |
| VALN-06 | Sustained-load synthetic trace: setpoint clamp holds rate at setpoint ± step | unit | `pytest tests/test_queue_controller.py::TestDocsisModeSetpointClamp::test_holds_at_setpoint_under_load -x` | ❌ Wave 0 |
| VALN-06 | RTT-integral correctly classifies headroom available/exhausted | unit | `pytest tests/test_queue_controller.py::TestDocsisModeIntegralClassifier::test_integral_state_machine -x` | ❌ Wave 0 |
| VALN-06 | CAKE corroborator vetoes push-up when backlog or delay-delta high | unit | `pytest tests/test_queue_controller.py::TestDocsisModeCakeCorroborator::test_veto_on_high_backlog -x` | ❌ Wave 0 |
| VALN-06 | RED fast-trip path is byte-identical with docsis_mode=true (ARCH-03 invariant) | unit | `pytest tests/test_queue_controller.py::TestDocsisModeByteIdentity::test_red_fast_trip_unchanged -x` | ❌ Wave 0 |
| (D-06 / SAFE-06) | Validator fails closed when docsis_mode=true and setpoint_mbps missing | unit | `pytest tests/test_check_config.py::TestDocsisModeValidation::test_missing_setpoint_fails -x` | ❌ Wave 0 |
| (D-06) | KNOWN_AUTORATE_PATHS contains all new keys | unit | `pytest tests/test_autorate_config.py::TestSafe06UnknownKeyWarning::test_phase201_keys_known -x` | ❌ Wave 0 |
| (D-17) | Non-DOCSIS YAML (no docsis_mode key) produces byte-identical legacy 3-state behavior | replay | `pytest tests/test_phase_201_replay.py::TestLegacyByteIdentity -x` | ❌ Wave 0 |
| (D-08) | SIGUSR1 reload does NOT change docsis_mode/setpoint_mbps live | unit | `pytest tests/test_wan_controller.py::TestSigusr1ReloadScope::test_docsis_keys_not_live_tunable -x` | ❌ Wave 0 |
| (D-12) | Canary preflight aborts on env/YAML mismatch for new env vars | integration | `pytest tests/test_phase200_canary_script.py::TestPhase201Preflight -x` | ❌ Wave 0 |
| (D-15) | Predeploy gate aborts when `/etc/wanctl/spectrum.yaml` carries v1.41-only rejected-hypothesis keys | shell-integration | `pytest tests/test_phase201_predeploy_gate.py -x` (or shell-test equivalent) | ❌ Wave 0 |
| (D-16) | `/health.wans[].upload.docsis_mode_active` reflects runtime state, not YAML echo | integration | `pytest tests/test_wan_controller.py::TestPhase201HealthAdditive -x` | ❌ Wave 0 |
| (CLAUDE.md ARCH-05) | Setpoint clamp does NOT regress flash-wear dedup | integration | `pytest tests/test_wan_controller.py::TestPhase201FlashWear::test_steady_state_no_router_writes -x` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `.venv/bin/pytest -o addopts='' tests/test_queue_controller.py tests/test_wan_controller.py tests/test_autorate_config.py tests/test_check_config.py tests/test_phase_201_replay.py -q` (focused slice, < 30 s)
- **Per wave merge:** `.venv/bin/pytest -q` (full suite; Phase 200 baseline 4787 passed)
- **Phase gate:** Full suite green AND canary `verdict=pass` AND 24h soak `<5/60s` BEFORE `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `tests/test_phase_201_replay.py` — covers VALN-06 replay path against Phase 200 Attempt 3 capture; mirrors `tests/test_phase_197_replay.py` structure (`tests/test_phase_197_replay.py:1-100`)
- [ ] New test classes in `tests/test_queue_controller.py`:
      `TestDocsisModeIntegralClassifier`,
      `TestDocsisModeSetpointClamp`,
      `TestDocsisModeCakeCorroborator`,
      `TestDocsisModeByteIdentity` (covers ARCH-03 RED fast-trip preservation)
- [ ] New test class in `tests/test_check_config.py`: `TestDocsisModeValidation` (missing setpoint, ordering, type errors)
- [ ] New test class in `tests/test_wan_controller.py`: `TestPhase201HealthAdditive` (curl-pattern test against running daemon — NOT JSON fixture; per Phase 200 RETRO Lesson 1)
- [ ] New test class in `tests/test_wan_controller.py`: `TestPhase201FlashWear` (steady-state cycles produce zero router writes)
- [ ] New test class in `tests/test_wan_controller.py`: `TestSigusr1ReloadScope` (parameterized on every new YAML key — none are live-tunable)
- [ ] Extend `tests/test_phase200_canary_script.py` with `TestPhase201Preflight` for new env vars
- [ ] New test file or shell test: `tests/test_phase201_predeploy_gate.py` (or `tests/shell/test_phase201_predeploy_gate.bats`)
- [ ] Conftest fixtures: synthetic load trace generator (60-cycle parameterized RTT/CAKE samples)
- [ ] Replay corpus capture: NDJSON capture from Phase 200 Attempt 3 canary loaded window (already exists at `.planning/phases/200-per-direction-rtt-bloat-thresholds/canary/20260504T133207Z/`); needs per-cycle RTT + CAKE fields — see Section 8.

**Test infrastructure that already covers Phase 201 (no new install needed):**
- pytest framework, fixtures, conftest pattern.
- `tests/test_phase200_canary_script.py` (existing harness for canary preflight tests).
- Replay test pattern from `tests/test_phase_197_replay.py` (canonical shape to mirror).
- `MagicMock` + `mock_autorate_config` fixtures for `WANController` integration tests.

### 8. Replay-Test Corpus

**Source: Phase 200 Attempt 3 canary capture** at `.planning/phases/200-per-direction-rtt-bloat-thresholds/canary/20260504T133207Z/`.

**Files present:**
- `verdict.json` — verdict + 4 floor hits, baseline bookends 21.7 → 22.23 ms.
- `loaded_capture.ndjson` (existing canary captures NDJSON of `/health` at 1 Hz during loaded window) — confirmed by `phase200-saturation-canary.sh` capture loop.
- `pre_idle_baseline.ndjson` / `post_idle_baseline.ndjson` — baseline bookends.
- `loaded_iperf_summary.json` — iperf3 throughput summary.

**Gap analysis for Phase 201 replay needs:**

| Field needed for integral replay | In existing capture? | If absent, source |
|----------------------------------|----------------------|-------------------|
| `load_rtt_ms` per cycle | Yes (1 Hz `/health.wans[0].load_rtt_ms`) | OK at 1 Hz; 50 ms cycle granularity is finer but 1 Hz is enough for replay verification of integral state-machine over 1000+ s loaded window |
| `baseline_rtt_ms` per cycle | Yes (`/health.wans[0].baseline_rtt_ms`) | OK |
| `current_rate_mbps` | Yes (`/health.wans[0].upload.current_rate_mbps`) | OK |
| Upload zone (GREEN/YELLOW/RED) | Yes (`/health.wans[0].upload.state`) | OK |
| `cake.upload.backlog_bytes` per cycle | Likely yes (existing `/health.cake_signal.upload`) | VERIFY in capture; if missing, Phase 201 canary should add it |
| `cake.upload.max_delay_delta_us` per cycle | Likely yes (additive to upload snapshot) | VERIFY in capture |

**Recommended Phase 201 replay setup:**
1. **Reuse Attempt 3 capture as primary corpus** — it has the 4 floor hits Phase 201 must eliminate.
2. **Reuse Attempt 2 capture as secondary corpus** (122 floor hits, bimodal distribution) — proves new controller doesn't regress against worst-case.
3. **Capture richer fields during the Phase 201 canary itself** — extend `phase200-saturation-canary.sh` capture loop to also record per-cycle CAKE backlog and delay-delta (additive to existing NDJSON shape, no breakage). This becomes the v1.42+ replay corpus.
4. **Sample-rate concern:** existing capture is 1 Hz; integral wants 20 Hz. 1 Hz can validate the integral state-machine logic but not the 50 ms response time. **Plan should consider whether canary script should sample /health at higher rate during the Phase 201 loaded window** — 5 Hz is a reasonable compromise (250 ms granularity, 4× capture overhead). Trade-off is /health endpoint load during canary; mitigation is to keep iperf3 the actual load and /health sampling truly read-only.

**Replay test shape (mirror `test_phase_197_replay.py`):**
```python
TRACE_ATTEMPT_3 = [...]  # parsed from loaded_capture.ndjson
EXPECTED_FLOOR_HITS_NEW_CONTROLLER = 0  # the contract

def test_attempt_3_replay_no_floor_hits():
    ctrl = _docsis_mode_controller(setpoint_mbps=12, ceiling=18)
    floor_hits = 0
    for sample in TRACE_ATTEMPT_3:
        zone, rate, _ = ctrl.upload.adjust(
            sample.baseline_rtt, sample.load_rtt, sample.target, sample.warn,
            cake_snapshot=_synthesize_cake(sample),
        )
        if rate <= ctrl.upload.floor_red_bps:
            floor_hits += 1
    assert floor_hits == EXPECTED_FLOOR_HITS_NEW_CONTROLLER
```

### 9. Predeploy-Gate (D-15) Action Shape

**Two options on the table from CONTEXT D-15:**
- **(A) Auto-strip** rejected-hypothesis keys → reconcile silently, deploy proceeds.
- **(B) Operator-manual reconcile** → fail closed, abort with operator-actionable message; operator runs a one-shot strip script then re-runs deploy.

**Researcher recommendation: (B) operator-manual reconcile, fail closed.**

**Rationale:**
- Auto-strip is irreversible — once the gate runs, the rejected-hypothesis keys are gone from `/etc/wanctl/spectrum.yaml` and the operator has no audit trail of what was changed and when.
- The keys MAY be retained in modified form per Section 5 (R5 + R3 keep, R0 strip). Auto-strip cannot make this distinction without specifying which keys to strip vs keep — that's an SPI-level config decision, not a tooling default.
- Fail-closed mirrors the Phase 200 gate philosophy (operator decides destructive actions; CLAUDE.md "stability > safety > clarity > elegance" gives the operator authority).
- An operator-actionable abort message ("found `target_bloat_ms: 42` in `/etc/wanctl/spectrum.yaml`; this is a Phase 200 rejected-hypothesis key. Run `scripts/phase201-reconcile-yaml.sh --strip-rejected` to remove, OR edit manually, then re-run deploy.") is far more debuggable than silent auto-strip.

**Where the gate runs:**
- Option α: New separate script `scripts/phase201-predeploy-gate.sh`, invoked by `scripts/deploy.sh` immediately before `rsync` of artifacts.
- Option β: Extend `phase200-saturation-canary.sh` preflight (lines 314-358 already do SSH-based YAML probe).
- Option γ: Inline in `scripts/install.sh` install-time check.

**Recommended: Option α (new script) + invocation from `scripts/deploy.sh`.** Reasons:
- The gate's job is *preventing* a bad deploy; it must run BEFORE the canary, not as part of it.
- The canary preflight already does YAML cross-check for env-var floor/ceiling consistency; adding a different responsibility (rejected-key inspection) muddles that script's contract.
- A separate script with single responsibility is easier to test in isolation.
- The script can also be run manually by the operator as a "pre-flight check" before pushing the deploy command.

**Gate logic shape:**
```bash
# scripts/phase201-predeploy-gate.sh
# Inspects $REMOTE_SSH_TARGET:$REMOTE_YAML_PATH for v1.41-only rejected-hypothesis keys.
# Exit 0 if clean (or if all rejected keys are accompanied by docsis_mode: true).
# Exit non-zero with operator-actionable message otherwise.

# Phase 201 reconciliation rules (from RESEARCH.md Section 5):
#   - target_bloat_ms / warn_bloat_ms in continuous_monitoring.upload → REJECT
#   - factor_down_yellow / consecutive_yellow_decay_clamp in continuous_monitoring.upload → ALLOW (kept)
#   - docsis_mode: true requires setpoint_mbps present → enforce
```

### 10. Migration & Docs

**`docs/CONFIGURATION.md` migration note (mirrors Phase 200 DOCS-03 pattern):**
```markdown
### DOCSIS-Aware UL Control Mode (v1.42+)

Enable per-deployment by setting:

    continuous_monitoring:
      upload:
        docsis_mode: true
        setpoint_mbps: 12  # link-specific; no global default
        # (other keys planner-finalized: integral_window_seconds,
        #  integral_threshold_ms_s, cake_backlog_low_threshold_bytes,
        #  cake_delay_delta_low_threshold_us)

When `docsis_mode: true`, the controller:
  - Runs `setpoint_mbps` as the operating point (not ceiling).
  - Uses a windowed RTT integral as the headroom probe.
  - AND-gates push-toward-ceiling on CAKE backlog/delay-delta low.

When `docsis_mode: false` or absent, behavior is byte-identical to v1.41.

**Service restart required.** SIGUSR1 does NOT reload these keys.
Apply changes with: `sudo systemctl restart wanctl@<wan>.service`
```

**`CHANGELOG.md` v1.42.0 entry skeleton:**
```markdown
## v1.42.0 — DOCSIS-Aware UL Congestion Control (2026-MM-DD)

**Phase 201 closes inherited blocking VALN-06 from Phase 200.**

### Added
- `continuous_monitoring.upload.docsis_mode: bool` (default false)
- `continuous_monitoring.upload.setpoint_mbps: int|float` (REQUIRED when docsis_mode: true)
- `continuous_monitoring.upload.integral_window_seconds` (planner-finalized name)
- `continuous_monitoring.upload.integral_threshold_ms_s` (planner-finalized name)
- `continuous_monitoring.upload.cake_backlog_low_threshold_bytes`
- `continuous_monitoring.upload.cake_delay_delta_low_threshold_us`
- `/health.wans[].upload.docsis_mode_active` (runtime state)
- `/health.wans[].upload.setpoint_mbps` (runtime state)
- `/health.wans[].upload.headroom_state` (runtime state)
- `/health.wans[].upload.rtt_integral_ms_s` (runtime state)
- `scripts/phase201-predeploy-gate.sh` (D-15)

### Changed
- Spectrum (`configs/spectrum.yaml`): `docsis_mode: true`, `setpoint_mbps: 12`,
  removed v1.41 rejected-hypothesis `target_bloat_ms` and `warn_bloat_ms`,
  retained `factor_down_yellow: 1.0` and `consecutive_yellow_decay_clamp: 40`.
- Upload `QueueController.adjust()` augmented with optional integral path
  + setpoint clamp. Legacy path byte-identical when docsis_mode absent.

### Migration
**Service restart required** for new keys. SIGUSR1 does not reload them.
Predeploy gate (`scripts/phase201-predeploy-gate.sh`) inspects
`/etc/wanctl/spectrum.yaml` for v1.41-only rejected-hypothesis keys
and aborts the deploy with operator-actionable instructions if found.

### Inherited blocking closure
- VALN-06: Spectrum UL canary `ul_floor_hits_during_load=0` ✓
- 24h soak UL hysteresis suppression `<5/60s` ✓

### Out of scope (deferred to v1.43+)
- Modem SNMP / DOCSIS HCS counter signal
- Tighter soak watchdog `<2/60s`
- DOCSIS-mode auto-tuning of setpoint_mbps
- Multi-window integral
```

## Environment Availability

> Phase 201 has external dependencies in canary execution (iperf3, ssh, jq, python3+pyyaml on canary runner; ssh access to deploy target).

| Dependency | Required By | Available | Version | Fallback |
|------------|-------------|-----------|---------|----------|
| Python 3.11+ | All Python code, canary preflight YAML parse | ✓ (project venv) | 3.11+ | — |
| pytest 7.x | Test suite | ✓ (in venv) | 7.x | — |
| iperf3 | Canary saturated upload | ✓ (canary runner has it; Phase 200 used it) | 3.x | — |
| ssh client | Canary preflight + deploy machinery | ✓ | OpenSSH | — |
| jq | Canary verdict parsing | ✓ (Phase 200 hardened) | 1.6+ | — |
| python3-yaml on canary runner | Canary preflight YAML parse | ✓ (Phase 200 used it) | — | — |
| RouterOS REST API | wanctl daemon control path | ✓ (production) | — | SSH transport (already in YAML) |
| Linux kernel CAKE qdisc | UL CakeSignalSnapshot source | ✓ (production cake-shaper VM) | 6.x | — |

**Missing dependencies with no fallback:** None — all infrastructure is the same as Phase 200.

**Missing dependencies with fallback:** None.

**Phase 200 RETRO advisory item (carries forward):** `200-REVIEW.md` WR-02 flagged that the canary script does not explicitly precheck python/yaml availability before the YAML parse. Phase 201 PLAN should close this as part of the preflight extension (D-12) — a missing-deps ABORT verdict before `python3 -c` invocation.

## Validation Architecture

> See Section 7 above for the full table — duplicated here under the heading the orchestrator expects.

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 7.x with `addopts=''` override pattern |
| Config file | `pyproject.toml` (`[tool.pytest.ini_options]`) |
| Quick run command | `.venv/bin/pytest -o addopts='' tests/test_queue_controller.py tests/test_wan_controller.py tests/test_autorate_config.py tests/test_check_config.py -q` |
| Full suite command | `.venv/bin/pytest -q` |

### Phase Requirements → Test Map

See Section 7 above. VALN-06 is the only phase requirement; it has 6 unit tests, 2 integration tests, 1 replay test, 1 canary, and 1 24h soak as its closure stack.

### Sampling Rate
- **Per task commit:** focused slice (< 30 s)
- **Per wave merge:** full pytest suite + ruff + mypy
- **Phase gate:** full suite green AND canary `verdict=pass` AND 24h soak `<5/60s`

### Wave 0 Gaps

See Section 7 above. Summary: 8+ new test files / classes are required before implementation tasks land. The replay-test infrastructure (`tests/test_phase_201_replay.py`) is the highest-leverage gap — it gates VALN-06 closure under synthetic conditions before the canary runs in production.

## Security Domain

> security_enforcement is not explicitly disabled; treat as enabled.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|------------------|
| V2 Authentication | no | No new auth surface; new keys are config-only. |
| V3 Session Management | no | No session surface added. |
| V4 Access Control | yes | Predeploy gate runs SSH-as-deploy-user; no privilege change. Reuses Phase 200 SSH-with-sudo pattern (`scripts/phase200-saturation-canary.sh:328`). |
| V5 Input Validation | yes | New YAML keys validated by `autorate_config.SCHEMA` (type / min / max) + `_validate_docsis_mode_setpoint` (ordering). KNOWN_AUTORATE_PATHS entry blocks unknown-key surface. |
| V6 Cryptography | no | No crypto surface added. |
| V7 Error Handling | yes | Validator fails closed on missing required key (`setpoint_mbps` when `docsis_mode: true`). Predeploy gate fails closed with operator-actionable message (D-15 (B)). Canary preflight fails closed on env/YAML mismatch (Phase 200 `43838f4` pattern preserved). |
| V8 Data Protection | no | Not handling user data. |
| V9 Comms | yes | RouterOS control already uses TLS or SSH key auth (existing). Phase 201 doesn't introduce new comms. |
| V10 Malicious Code | yes | Predeploy gate's `python3 -c` reads remote YAML via SSH; reuses Phase 200's `validate_remote_yaml_path` helper (path-traversal guard). |
| V11 Business Logic | yes | Setpoint clamp enforces `floor < setpoint < ceiling` ordering — invariant of the rate-decision business rule. Validator rejects violation. |
| V12 Files / Resources | no | No file upload or resource exposure. |
| V13 API | yes | `/health` is the existing API; D-16 additive only. New fields exposed are non-sensitive runtime state. |
| V14 Config | yes | YAML-as-code: SAFE-06 unknown-key warning + KNOWN_AUTORATE_PATHS registration prevents silent config drift (Phase 200 closed gap). |

### Known Threat Patterns for wanctl

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Operator drift in env vars (Phase 200 false-PASS regression) | Tampering | Env-var-declared expectation + SSH probe of deployed YAML — extended to Phase 201 keys (D-12). |
| Rejected-hypothesis state in production config | Tampering / Repudiation | Predeploy gate inspects `/etc/wanctl/spectrum.yaml` (D-15); fail-closed with operator-actionable message. |
| Unknown YAML key silently ignored (Phase 200 SAFE-06 closed gap) | Tampering | KNOWN_AUTORATE_PATHS registration + SAFE-06 startup warning. |
| Module-scope logger drops INFO (Phase 200 Plan 01 bug) | Repudiation | Use `self.logger` for all D-06-style INFO lines; test against configured logger. |
| `/health` shape change breaks downstream (Phase 200 Plan 05 bug) | DoS to downstream consumers | D-16 additive only; NEW fields nested under `.wans[].upload.*`; existing keys untouched. |
| Setpoint clamp bypasses flash-wear dedup | DoS to router (flash wear) | ARCH-05 invariant: dedup at router-write layer; Phase 201 MUST NOT touch dedup path. Test: TestPhase201FlashWear. |
| Replay-test corpus poisoning (planted samples) | Tampering | Corpus loaded from in-tree `.planning/phases/200-...` directory committed to git; integrity via git history. |

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Window length of 2.0 s (40 cycles) is appropriate for the integral | Section 1, Architecture | Too-short window misses sustained bloat; too-long window delays push-up. Operationally tunable via canary; default has rationale (matches existing R3 horizon). |
| A2 | Integral threshold default 30 ms·s | Section 1 | Wrong threshold causes either (a) push-up never happens (controller stuck at setpoint, sacrifices peak UL) or (b) push-up always happens (controller behaves like legacy, oscillates). Canary will tune. |
| A3 | `cake_delay_delta_low_threshold_us = 5000` (5 ms) for corroborator | Section 2 | Wrong threshold either vetoes valid push-ups or fails to veto invalid ones. Canary will tune. Reuse of `deadband_ms=3` analog is best-available default. |
| A4 | Spectrum provisioned upstream rate is ~20 Mbit | Section 4 | If actual is 22+, setpoint=12 gives more headroom than estimated (safer). If actual is 18, setpoint=12 still gives 6 Mbit headroom (works). If actual is 15, setpoint=12 is too close to provisioned — canary will reveal. |
| A5 | `setpoint_mbps: 12` produces zero floor hits in the Phase 201 canary | Section 4 | If canary fails, fallback is `setpoint_mbps: 10` (more headroom). This is a tunable, not a hypothesis. |
| A6 | Phase 200 Attempt 3 capture has per-cycle CAKE backlog and delay-delta in NDJSON | Section 8 | If absent, Phase 201 replay can only validate integral state-machine, not corroborator. Need to verify capture shape during planning. |
| A7 | `floor_mbps < setpoint_mbps < ceiling_mbps` ordering is the right invariant | Section 3, Pitfall 2 | Edge case: `setpoint == ceiling` would make DOCSIS-mode equivalent to legacy at ceiling. Strict `<` rejection forces operator to choose; safer than implicit. |
| A8 | Phase 200's R5 (`factor_down_yellow=1.0`) and R3 (`consecutive_yellow_decay_clamp=40`) should be retained in Phase 201 | Section 5 | If retained but no longer needed under new control model, they're dead config (cheap). If removed and the new control model has a YELLOW-decay edge case, controller could regress. Keeping is safer. |
| A9 | Predeploy gate fail-closed (Section 9 option B) is preferable to auto-strip | Section 9 | If operator workflow tolerates auto-strip well, fail-closed adds friction. CLAUDE.md priority order (stability > safety) supports fail-closed. |
| A10 | Replay-test sample rate of 1 Hz from existing capture is sufficient for state-machine validation | Section 8 | Integral has 50 ms granularity; 1 Hz sampling means each replay sample represents 20 cycles. State-machine logic is correctly validated; timing fidelity is not. Acceptable for unit-replay; canary provides true 50 ms validation. |

**Confirmation strategy:** Before plan execution, the operator should confirm A4 (Spectrum provisioned rate) by reading the ISP plan or the SLA. If A4 is wrong (e.g., provisioned is 25 Mbit, not 20), A5 reasoning shifts and `setpoint_mbps: 14` becomes more defensible than 12. This is the single highest-leverage assumption to verify pre-canary.

## Open Questions

1. **Are per-cycle CAKE backlog and delay-delta fields present in Phase 200 Attempt 3 NDJSON capture?**
   - What we know: `loaded_capture.ndjson` exists; `phase200-saturation-canary.sh` captures `/health` at 1 Hz.
   - What's unclear: whether `/health.cake_signal.upload.{backlog_bytes, max_delay_delta_us}` is in the capture shape or only in `/health.wans[].upload`.
   - Recommendation: PLAN should include a Wave 0 task that inspects the existing NDJSON to confirm; if absent, extend the capture shape during the Phase 201 canary itself.

2. **What is Spectrum's actual provisioned upstream rate?**
   - What we know: Phase 200 RETRO says "~20 Mbit"; CONTEXT D-09 uses "60% of ~20 Mbit".
   - What's unclear: ISP-side actual provisioned rate. Could be 20, 22, 24, or 25 depending on speedtier.
   - Recommendation: operator should confirm before canary; if rate differs from ~20 by more than 10%, recompute setpoint as 60% of actual. This is the highest-impact pre-canary assumption.

3. **Should the canary script sample `/health` at 5 Hz instead of 1 Hz during the Phase 201 loaded window?**
   - What we know: 1 Hz catches floor hits at second granularity; loaded window is 900 s; 1 Hz produces 900 samples.
   - What's unclear: whether 5 Hz overhead degrades the canary's own validity or signals.
   - Recommendation: PLAN can leave at 1 Hz for canary verdict (it's the gate-driving signal — `current_rate_mbps` snapshot every second is sufficient to detect floor); raise to 5 Hz only if the replay corpus needs finer resolution. Defer to v1.43 if needed.

4. **Does `_compute_effective_ul_load_rtt()` (asymmetry-gate attenuated) interact with the integral correctly?**
   - What we know: the function returns `self.load_rtt` attenuated by `damping_factor` when downstream-only congestion is detected (`wan_controller.py:2654-2750`).
   - What's unclear: if the attenuated load_rtt is fed into the integral, the integral could be biased low during DL-only events, falsely signaling headroom available, leading to push-up that masks an actual problem.
   - Recommendation: integral should consume the SAME `effective_ul_load_rtt` that the existing classifier consumes (preserves current asymmetry-gate semantics). Add a regression test that exercises asymmetry-gate active + integral path together to catch divergence.

5. **Is there an existing `green_required` analog for "sustained low integral"?**
   - What we know: `green_required=3` for Spectrum UL gates push-up cadence on consecutive GREEN cycles.
   - What's unclear: whether the integral's "below threshold for full window" requirement subsumes `green_required` or runs in parallel.
   - Recommendation: integral runs IN PARALLEL with `green_required`. Push-up requires BOTH (sustained green streak AND headroom_AVAILABLE AND cake_aligned). Triple-AND is a stronger gate than the current double-AND-implicit-headroom of legacy.

## Sources

### Primary (HIGH confidence)
- `src/wanctl/queue_controller.py` (lines 1-280) — VERIFIED via Read; integration points line 139-256 confirmed.
- `src/wanctl/wan_controller.py` (lines 367-455, 1330-1395, 1880-1900, 2654-2858, 2960-2990, 4490-4530) — VERIFIED via Read.
- `src/wanctl/cake_signal.py` (lines 1-270) — VERIFIED via Read; `CakeSignalSnapshot.backlog_bytes` and `.max_delay_delta_us` populated for UL.
- `src/wanctl/check_config_validators.py` (lines 1-200, 385-455) — VERIFIED via Read.
- `src/wanctl/autorate_config.py` (lines 170-220) — VERIFIED via Read.
- `configs/spectrum.yaml` — VERIFIED via Read; current state of UL block.
- `scripts/phase200-saturation-canary.sh` (lines 300-380) — VERIFIED via Read; reuse target for D-11 + D-12.
- `tests/test_queue_controller.py` (lines 1-150) — VERIFIED via Read; existing test patterns.
- `tests/test_phase_197_replay.py` (lines 1-100) — VERIFIED via Read; canonical replay shape.
- `.planning/phases/201-docsis-aware-ul-congestion-control/201-CONTEXT.md` — VERIFIED via Read.
- `.planning/phases/201-docsis-aware-ul-congestion-control/201-DISCUSSION-LOG.md` — VERIFIED via Read.
- `.planning/phases/200-per-direction-rtt-bloat-thresholds/200-RETRO.md` — VERIFIED via Read.
- `.planning/phases/200-per-direction-rtt-bloat-thresholds/200-VERIFICATION.md` — VERIFIED via Read.
- `.planning/phases/200-per-direction-rtt-bloat-thresholds/canary/20260504T133207Z/verdict.json` — VERIFIED via Read.
- `.planning/phases/200-per-direction-rtt-bloat-thresholds/canary/20260503T215734Z/verdict.json` — VERIFIED via Read.
- `.planning/spectrum-inline-native-18-upload-test-2026-04-29.md` — VERIFIED via Read.
- `.planning/spectrum-upload-ceiling-sweep-2026-04-29.md` — VERIFIED via Read.
- `.planning/spectrum-target-bloat-sweep-2026-04-15.md` — VERIFIED via Read.
- `.planning/REQUIREMENTS.md` (VALN-06 row + v1.41 status) — VERIFIED via Read.
- `.planning/ROADMAP.md` (Phase 201 entry, lines 175-228) — VERIFIED via Read.
- `.planning/intel/arch.md` (ARCH-01 through ARCH-05) — VERIFIED via Read.
- `.planning/config.json` — VERIFIED (`nyquist_validation: true`).
- `CLAUDE.md` (project) — VERIFIED in conversation context.

### Secondary (MEDIUM confidence)
- Phase 197 `dl_cake_for_arbitration` semantics — inferred from `wan_controller.py:2860-2910` and `_select_dl_primary_scalar_ms`; cross-referenced against the seed CONTEXT D-04 explanation.
- Spectrum provisioned upstream rate "~20 Mbit" — cited in CONTEXT D-09 and Phase 200 RETRO; not independently verified in this research session (assumption A4).

### Tertiary (LOW confidence) — Marked for validation
- Default `integral_threshold_ms_s = 30.0` (assumption A2): no live evidence; canary will validate.
- Default `cake_delay_delta_low_threshold_us = 5000` (assumption A3): inferred from `deadband_ms=3` analog; canary will validate.
- 5 Hz canary sample rate suggestion (Open Question 3): no overhead measurement.

## Metadata

**Confidence breakdown:**
- Standard stack (in-tree, no new deps): HIGH — entire stack is existing wanctl primitives, all VERIFIED.
- Architecture patterns: HIGH — Phase 197 / Phase 200 patterns are explicit mirrors; `_classify_direction` and `_select_dl_primary_scalar_ms` are direct sources.
- Integration points: HIGH — every line cited above was Read-verified.
- Pitfalls: HIGH — every pitfall traces to a specific Phase 200 RETRO bug or CLAUDE.md invariant.
- D-09 setpoint = 12 Mbit defensibility: LOW-MEDIUM — sweep evidence does NOT directly support 12; recommendation is to keep as `[ASSUMED]`, validated by canary.
- Default thresholds for integral and CAKE corroborator: LOW — defaults are reasoned starting points, not measured. Canary will tune.
- Validation Architecture map: HIGH — every test target maps to an existing test pattern in the project.

**Research date:** 2026-05-04
**Valid until:** 2026-06-03 (30 days; control-loop research domain is stable; only invalidation events are RouterOS / kernel CAKE changes which have not been signaled).

---

*Phase: 201-docsis-aware-ul-congestion-control*
*Researched: 2026-05-04*
*Next step: `/gsd-plan-phase 201` consumes this RESEARCH.md to produce per-plan PLAN.md files. Pay particular attention to Section 4 (D-09 setpoint defensibility), Section 8 (replay corpus shape), Section 9 (predeploy-gate action shape), and the Assumptions Log (A1–A10).*
