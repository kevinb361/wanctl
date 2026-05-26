# Roadmap: wanctl

## Milestones

- 🚧 **v1.45 Flapping Peak-Counter Window Repair** — planning (Phases 210–211; 8/8 REQ-IDs mapped; spine = confirmed bug at `wan_controller.py:4322-4323/4353-4354`)
- ✅ **v1.44 Topology-Correct CAKE — Spectrum besteffort wash migration** — shipped 2026-05-26 (Phases 205–209; audit `passed` after 206 restamp, 16/16; Spectrum running `920Mbit besteffort wash` in production with 24h soak ✓) — `milestones/v1.44-ROADMAP.md`
- ✅ **v1.43 UL Suppression Metrics & Gate Calibration** — shipped 2026-05-13 (audit `passed` 15/15; gap-closure cycle 204-07..10 closed post-d44e2fd evidence; threshold 175 dual-gate verified) — `milestones/v1.43-ROADMAP.md`
- ✅ **v1.42 DOCSIS-Aware UL Congestion Control** — shipped 2026-05-06 (gaps_found Route B; D-19 PASS / D-14 deferred to v1.43) — `milestones/v1.42-ROADMAP.md`
- ✅ **v1.41 Per-Direction Control Surfaces** — closed 2026-05-04 (gaps_found; ARB-05/SAFE-06/DOCS-03 satisfied; VALN-06 deferred-and-closed via v1.42) — `milestones/v1.41-ROADMAP.md`
- ✅ **v1.40 Queue-Primary Signal Arbitration** — shipped 2026-05-03 — `milestones/v1.40-ROADMAP.md`
- ✅ **v1.39 Control-Path Timing & Measurement Accounting** — shipped 2026-04-24 (operator waiver; archived 2026-05-06 gaps_found) — `milestones/v1.39-ROADMAP.md`
- 📁 **v1.0 — v1.38** — see `MILESTONES.md` for the full historical index

---

## Active Milestone: v1.45 Flapping Peak-Counter Window Repair

**Goal:** Restore the intensity signal in `flapping_dl` / `flapping_ul` alert payloads by tracking peak transition count via a windowed accumulator that survives the per-fire deque clear, so production operators can see oscillation intensity above the trigger threshold.

**Scope:** Alerting-only. No controller-threshold, autorate, signal-arbitration, or netlink-apply changes. SAFE-09-style control-path boundary preserved by scope (`SAFE-10`).

**Design:** Option A (windowed peak accumulator) selected over Option B (rename payload) — preserves the intensity signal that motivated the metric.

**Spine:** `.planning/todos/pending/2026-04-17-monitor-flapping-peak-count-on-next-docsis-event.md` (confirmed bug 2026-05-26; root cause located; Codex peer-reviewed across two rounds).

### Phases

**Phase Numbering:** Continues from v1.44 last phase (209). v1.45 starts at Phase 210.

- [ ] **Phase 210: Windowed Peak Accumulator Implementation** — Add per-direction windowed peak accumulator at `wan_controller.py:4275-4360`, update `TestFlappingDequeClear`, add new tests asserting `peak > flap_threshold` during sustained oscillation; preserve SAFE-10 control-path boundary
- [ ] **Phase 211: Production Verification & Milestone Closure** — Deploy Phase 210 build; confirm at least one real production flapping event reports `peak_transition_count > flap_threshold`; re-verify SAFE-10 at milestone close

### Phase Details

#### Phase 210: Windowed Peak Accumulator Implementation
**Goal**: Implement Design Option A (per-direction windowed peak accumulator independent of deque-clear) in `wan_controller.py`, update `TestFlappingDequeClear` to reflect new semantics, add new tests asserting `peak_transition_count > flap_threshold` during sustained oscillation, and preserve SAFE-10 control-path source boundary.
**Depends on**: Nothing (first phase of v1.45)
**Requirements**: ALERT-01, ALERT-02, TEST-01, TEST-02, TEST-03, SAFE-10
**Success Criteria** (what must be TRUE):
  1. `wan_controller.py:4275-4360` has a new per-direction windowed peak accumulator that updates each cycle from `len(deque)` and resets only when the 120s windowed prune drops the deque to zero — not on fire.
  2. `flapping_dl` / `flapping_ul` alert payloads continue to expose both `peak_transition_count` and `transition_count` (ALERT-02 payload compatibility preserved for existing operator tooling and downstream consumers).
  3. `tests/test_alert_engine.py::TestFlappingDequeClear` is updated to assert peak-over-120s-window semantics rather than peak-equals-fire-value; deque-clear-on-fire assertions are preserved.
  4. New tests assert `peak_transition_count > flap_threshold` when transitions are injected above threshold within a single window (covering both DL and UL paths), and assert monotonically non-decreasing peak across multiple fires within the window until the windowed prune resets it.
  5. SAFE-10 closeout check shows zero `src/wanctl/` source diff outside the alerting path between v1.44 close and Phase 210 close. The five-file SAFE-09 allowlist (`linux_cake.py`, `netlink_cake.py`, `cake_params.py`, `cake_signal.py`, `check_config_validators.py`) is untouched; `alert_engine.py` semantics (`cooldown_sec` dedup) unchanged.
**Plans**: 3 plans
- [x] 210-01-PLAN.md — Implement windowed peak accumulator in wan_controller.py (ALERT-01, ALERT-02)
- [x] 210-02-PLAN.md — Update TestFlappingDequeClear and add TestFlappingPeakWindow (TEST-01, TEST-02, TEST-03)
- [ ] 210-03-PLAN.md — SAFE-10 closeout audit (SAFE-10)

#### Phase 211: Production Verification & Milestone Closure
**Goal**: Deploy the Phase 210 fix to production, observe at least one real flapping event in the alerts table where `peak_transition_count > flap_threshold`, and close v1.45 with operator-verified evidence that the metric now carries the intensity signal it was designed to carry.
**Depends on**: Phase 210
**Requirements**: ALERT-03, VERIFY-01
**Success Criteria** (what must be TRUE):
  1. Phase 210 build is deployed to production (cake-shaper Spectrum and ATT) with `/health.version` reflecting the v1.45 bump and pre-deploy snapshot artifact captured for rollback.
  2. Production alerts table shows at least one `flapping_dl` or `flapping_ul` event after deploy where `details.peak_transition_count > details.flap_threshold` (i.e., `> 30`).
  3. Operator confirms in production that `congestion_flapping` does not log-spam at every cycle during a sustained event — `alert_engine.fire()` `cooldown_sec` continues to dedupe per episode (ALERT-03 alert-once-per-episode semantics preserved end-to-end).
  4. SAFE-10 closeout check at Phase 211 boundary shows zero `src/wanctl/` source diff outside the alerting path between v1.44 close and v1.45 close; five-file SAFE-09 allowlist remains untouched.
**Plans**: TBD

### Progress

**Execution Order:** Phases execute in numeric order: 210 → 211

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 210. Windowed Peak Accumulator Implementation | 2/3 | In Progress|  |
| 211. Production Verification & Milestone Closure | 0/TBD | Not started | - |

### Coverage

All 8 v1.45 REQ-IDs map to exactly one phase. No orphans.

| Phase | REQ-IDs |
|-------|---------|
| 210 | ALERT-01, ALERT-02, TEST-01, TEST-02, TEST-03, SAFE-10 |
| 211 | ALERT-03, VERIFY-01 |

**Mapping rationale:**
- **ALERT-01** (`peak > flap_threshold` observable): Phase 210 — metric semantic is fixed in code. Phase 211 verifies it in production but does not introduce the behavior.
- **ALERT-02** (`transition_count` payload compatibility): Phase 210 — payload-shape is implementation-time.
- **ALERT-03** (alert-once-per-episode, no log-spam): Phase 211 — end-to-end behavior is only verifiable in production under a real sustained event. Phase 210 unit tests establish the mechanism (cooldown_sec retained, deque-clear-on-fire retained); Phase 211 confirms it holds.
- **TEST-01/02/03**: Phase 210 — tests live with the code change.
- **VERIFY-01**: Phase 211 — production-gate by design, cannot be satisfied at PR-merge time.
- **SAFE-10**: Phase 210 owns primary verification at PR-merge time; Phase 211 re-verifies at milestone close to catch any drift between PR-merge and deploy.

### Cross-Cutting Invariants

**SAFE-10** is verified at every phase boundary (mirrors v1.44 SAFE-08/SAFE-09 mechanism):
- No changes to autorate continuous loop, signal arbitration, netlink apply, CAKE backends, fusion healer, or DOCSIS UL controller
- The five-file SAFE-09 allowlist from v1.44 (`linux_cake.py`, `netlink_cake.py`, `cake_params.py`, `cake_signal.py`, `check_config_validators.py`) remains untouched
- `alert_engine.py` semantics (`cooldown_sec` dedup) unchanged
- Only `src/wanctl/wan_controller.py` flapping-detection block (`:4275-4360`) and version bump are expected to diff

---

## Backlog

(None at root scope. Historical 999.x items lived under earlier ROADMAPs and are preserved in milestone archives.)

### Deferred to v1.46+ (carried forward from v1.44 close; not consumed by v1.45)

- **SEED-003** D-14 successor recalibration (dormant; v1.43 deferral, still awaiting metric-semantics decision)
- **SEED-004** target-edge churn instrumentation (dormant; v1.43 carry-forward)
- **SEED-005** conservative UL tuning sweep (dormant; prereqs satisfied; deferred to avoid 3 consecutive UL-only milestones)
- **SEED-006** Silicom bypass NIC tooling + test harness (dormant; planted 2026-05-26 from two silicom todos; two-phase: operational tooling → harness; independent of v1.43-era seeds)
- **SEED-007** Storage hygiene — autorate flat-gauge fire-on-change + CAKE tin skip-on-unchanged (dormant; planted 2026-05-26 from former T6/T7 todos; two-phase: Phase A shippable independently, Phase B gated on consumer audit)
- **T17(b)** CALIB-02 YAML knob shape evaluation (gated on SEED-005 outcomes; HRDN-04 in v1.44 answered NO — fail-closed JSON threshold preserved)
- **phase-196 queue-primary refractory semantics** — thread `in_progress` since 2026-04-27; cross-milestone investigation
- **knowledge-base debug session** — status unknown; needs triage
- **4 pending todos** under `.planning/todos/pending/` (one of the five from v1.44 close — `2026-04-17-monitor-flapping-peak-count-on-next-docsis-event` — is now the v1.45 spine; closes when VERIFY-01 satisfied)

**Note on SEED-006/007 naming:** Both seeds are named `v145-*` in their seed IDs but are NOT consumed by the v1.45 milestone. v1.45 spine is the flapping-peak bug fix only. SEED-006/007 are candidates for v1.46+ depending on operator scoping.
