---
milestone: v1.45
name: Flapping Peak-Counter Window Repair
status: planning
created: 2026-05-26
---

# Milestone v1.45 Requirements: Flapping Peak-Counter Window Repair

**Goal:** Restore the intensity signal in `flapping_dl` / `flapping_ul` alert payloads by tracking peak transition count via a windowed accumulator that survives the per-fire deque clear, so production operators can see oscillation intensity above the trigger threshold.

**Scope:** Alerting-only. No controller-threshold, autorate, signal-arbitration, or netlink-apply changes. SAFE-09-style control-path boundary preserved by scope.

**Source:** Confirmed bug from 2026-05-26 backlog triage (`.planning/todos/pending/2026-04-17-monitor-flapping-peak-count-on-next-docsis-event.md`). Production alerts table shows `peak == transition_count == 30` across 20+ Spectrum `flapping_ul` events (2026-05-21→25) + 3 ATT `flapping_dl` events. Root cause located at `src/wanctl/wan_controller.py:4322-4323` (DL) and `:4353-4354` (UL): in-fire `deque.clear()` + `self._dl_peak_transitions = 0` (and UL equivalent) destroys window state at the exact moment the alert fires.

**Design option selected:** Option A (windowed peak accumulator), per Codex round-2 peer review. Option B (rename payload to `transition_count_at_fire`) explicitly rejected — would lose the intensity signal that motivated the metric.

---

## v1.45 Requirements

### Alerting Payload (ALERT)

- [x] **ALERT-01**: Operator can read `peak_transition_count` from a fired `flapping_dl` / `flapping_ul` alert and observe a value > `flap_threshold` when oscillation intensity exceeds the trigger threshold within the 120-second flap window.
- [x] **ALERT-02**: Operator can read `transition_count` from the same payload and continue to see the current-window count at fire time (payload-compatible with existing operator tooling and downstream consumers).
- [ ] **ALERT-03**: Operator observes alert-once-per-oscillation-episode semantics in production — `congestion_flapping` does not log-spam at every cycle while transitions stay above threshold (deque-clear-on-fire retained for episode boundaries; `alert_engine.fire()` `cooldown_sec` continues to dedupe).

### Test Surface (TEST)

- [x] **TEST-01**: `tests/test_alert_engine.py::TestFlappingDequeClear` is updated to test peak-over-120s-window semantics rather than peak-equals-fire-value semantics. Existing assertions about deque-clear-on-fire are preserved; new assertions verify peak survives the clear.
- [x] **TEST-02**: New test asserts `peak_transition_count > flap_threshold` when transitions are injected at a rate exceeding the threshold within a single window. Covers both DL and UL paths.
- [x] **TEST-03**: New regression coverage for cooldown interaction — multiple `fire()` calls within the 120s window produce monotonically non-decreasing peak values until the windowed prune drops the deque to zero, at which point peak resets.

### Production Verification (VERIFY)

- [ ] **VERIFY-01**: After deploy, at least one real production flapping event in the alerts table reports `peak_transition_count > flap_threshold`. Closure gate for the v1.45 milestone — the bug is not fixed in production until live data confirms.

### Safety Invariant (SAFE)

- [x] **SAFE-10**: Zero `src/wanctl/` source diff outside the alerting path between v1.44 close (`c9932d2` or equivalent) and v1.45 close. Specifically: no changes to autorate continuous loop, signal arbitration, netlink apply, CAKE backends, fusion healer, or DOCSIS UL controller. The five-file SAFE-09 allowlist from v1.44 (`linux_cake.py`, `netlink_cake.py`, `cake_params.py`, `cake_signal.py`, `check_config_validators.py`) remains untouched.

---

## Future Requirements (deferred)

(none — v1.45 scope is fully captured in the above)

## Out of Scope

- **Rename to `transition_count_at_fire`** — Option B rejected during 2026-05-26 design review; loses intensity signal.
- **Threshold tuning** (`flap_threshold = 30`, `flap_window = 120`) — values unchanged; v1.45 fixes the metric, not the trigger.
- **Steering, autorate, or controller threshold changes** — explicitly outside SAFE-10.
- **`alert_engine.py` semantics changes** — `cooldown_sec` dedup behavior is unchanged; only `wan_controller.py` peak tracking is modified.
- **Other deferred items from v1.44 close** — SEED-003/004/005 (UL tuning chain), SEED-006 (Silicom), SEED-007 (storage hygiene), T17(b) CALIB-02 YAML evaluation, phase-196 queue-primary refractory semantics thread. All remain dormant for v1.46+ consideration.

## Traceability

| REQ-ID    | Phase | Status   |
|-----------|-------|----------|
| ALERT-01  | 210   | Complete |
| ALERT-02  | 210   | Complete |
| ALERT-03  | 211   | Pending  |
| TEST-01   | 210   | Complete |
| TEST-02   | 210   | Complete |
| TEST-03   | 210   | Complete |
| VERIFY-01 | 211   | Pending  |
| SAFE-10   | 210, 211 (cross-cutting) | Complete |

**Coverage:** 8/8 v1.45 REQ-IDs mapped. SAFE-10 is cross-cutting (verified at every phase boundary, mirrors v1.44 SAFE-08/SAFE-09 mechanism); primary verification owned by Phase 210 at PR-merge time, re-verified at Phase 211 at milestone close.
