---
phase: 95-irtt-loss-alerts
verified: 2026-03-18T08:00:00Z
status: passed
score: 5/5 must-haves verified
re_verification: false
---

# Phase 95: IRTT Loss Alerts Verification Report

**Phase Goal:** Operators receive Discord notifications when sustained upstream or downstream packet loss is detected via IRTT
**Verified:** 2026-03-18T08:00:00Z
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| #   | Truth                                                                                | Status     | Evidence                                                                                   |
| --- | ------------------------------------------------------------------------------------ | ---------- | ------------------------------------------------------------------------------------------ |
| 1   | Sustained upstream IRTT loss above 5% for 60s triggers a Discord alert              | VERIFIED   | `_check_irtt_loss_alerts` fires `irtt_loss_upstream` after `up_sustained` seconds (line 2501-2512) |
| 2   | Sustained downstream IRTT loss above 5% for 60s triggers a separate Discord alert   | VERIFIED   | Same method fires `irtt_loss_downstream` independently (line 2543-2554)                    |
| 3   | IRTT loss alerts are suppressed during cooldown period (no alert storms)             | VERIFIED   | `alert_engine.fire()` returns False on cooldown; `_*_fired` not set when False (line 2511) |
| 4   | Recovery alert fires when loss clears after sustained alert had fired                | VERIFIED   | `irtt_loss_recovered` fired in the `else` branch gated on `_irtt_loss_up_fired` (line 2515-2526) |
| 5   | Stale IRTT data resets loss timers (no false alerts)                                 | VERIFIED   | `isinstance(AlertEngine)` gate in `run_cycle` resets all 4 vars when `age > cadence * 3` (line 2184-2188) |

**Score:** 5/5 truths verified

### Required Artifacts

| Artifact                                      | Expected                                      | Status     | Details                                                  |
| --------------------------------------------- | --------------------------------------------- | ---------- | -------------------------------------------------------- |
| `src/wanctl/autorate_continuous.py`           | `_check_irtt_loss_alerts` method + 4 state vars | VERIFIED | Method at line 2475, state vars at lines 1531-1535; 44 `irtt_loss` references total |
| `src/wanctl/webhook_delivery.py`              | `"loss": "%"` in `DiscordFormatter._UNIT_MAP` | VERIFIED   | Line 114: `"loss": "%"` present                          |
| `tests/test_irtt_loss_alerts.py`              | 150+ lines, 11+ tests                         | VERIFIED   | 452 lines, 12 test methods — all 12 pass                 |

### Key Link Verification

| From                                          | To                            | Via                                               | Status     | Details                                                  |
| --------------------------------------------- | ----------------------------- | ------------------------------------------------- | ---------- | -------------------------------------------------------- |
| `autorate_continuous.py`                      | `AlertEngine.fire()`          | `alert_engine.fire("irtt_loss_upstream", ...)`    | WIRED      | Lines 2501-2510 (upstream), 2543-2551 (downstream)      |
| `autorate_continuous.py`                      | `IRTTResult.send_loss / receive_loss` | Used in `_check_irtt_loss_alerts`       | WIRED      | Lines 2495, 2506, 2524 (send_loss); 2537, 2548, 2566 (receive_loss) |
| `autorate_continuous.py run_cycle()`          | `_check_irtt_loss_alerts()`   | Called inside IRTT freshness gate                 | WIRED      | Line 2183: `self._check_irtt_loss_alerts(irtt_result)` inside `if age <= cadence * 3` |

### Requirements Coverage

| Requirement | Source Plan  | Description                                                                 | Status     | Evidence                                                                 |
| ----------- | ------------ | --------------------------------------------------------------------------- | ---------- | ------------------------------------------------------------------------ |
| ALRT-01     | 95-01-PLAN   | Sustained upstream packet loss triggers alert via AlertEngine, configurable threshold | SATISFIED | `_irtt_loss_threshold_pct = 5.0` default; per-rule `loss_threshold_pct` override in `_check_irtt_loss_alerts`; `irtt_loss_upstream` fired |
| ALRT-02     | 95-01-PLAN   | Sustained downstream packet loss triggers alert via AlertEngine, configurable threshold | SATISFIED | Independent downstream timer; `irtt_loss_downstream` fired; per-rule override identical to upstream |
| ALRT-03     | 95-01-PLAN   | IRTT loss alerts use per-event cooldown consistent with existing alert types | SATISFIED | `alert_engine.fire()` returns False on cooldown; `_irtt_loss_up_fired` only set when `fire()` returns True; test `TestCooldownSuppression` verifies |

No orphaned requirements — REQUIREMENTS.md lists only ALRT-01, ALRT-02, ALRT-03 for Phase 95, all accounted for.

### Anti-Patterns Found

No anti-patterns found. Scanned `src/wanctl/autorate_continuous.py` (IRTT loss sections), `src/wanctl/webhook_delivery.py`, and `tests/test_irtt_loss_alerts.py` for TODO/FIXME/placeholder patterns and empty implementations. None present.

### Human Verification Required

#### 1. Discord embed "%" suffix rendering

**Test:** Trigger an IRTT loss alert on a live container and observe the Discord notification
**Expected:** The `loss_pct` field in the embed renders with "%" suffix (e.g., "7.3%")
**Why human:** `_UNIT_MAP["loss"] = "%"` is in the code but actual Discord message rendering requires live AlertEngine + DiscordFormatter + webhook delivery chain

#### 2. End-to-end production fire path

**Test:** Configure `irtt_loss_upstream` rule in YAML with `loss_threshold_pct: 2.0` and `sustained_sec: 10`, wait for a lossy period on the Spectrum container
**Expected:** Discord alert arrives within ~10s of sustained loss exceeding 2%
**Why human:** Full stack test — IRTT background thread, run_cycle loop, AlertEngine cooldown, WebhookDelivery retry — cannot simulate in unit tests

### Gaps Summary

None. All 5 truths verified, all 3 artifacts pass level 1-2-3 checks, all 3 key links wired, all 3 requirements satisfied. 12/12 unit tests pass. Full test suite reported 3402 tests / 0 failures by the executor (commit 681aa53).

---

_Verified: 2026-03-18T08:00:00Z_
_Verifier: Claude (gsd-verifier)_
