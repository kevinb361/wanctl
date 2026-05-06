# Phase 201: DOCSIS-Aware UL Congestion Control - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-04
**Phase:** 201-docsis-aware-ul-congestion-control
**Areas discussed:** Phase shape, Setpoint signal source, Setpoint default + tuning surface, Spectrum-specific setpoint value, VALN-06 closure shape

---

## Phase shape

| Option | Description | Selected |
|--------|-------------|----------|
| Single phase, signal locked at design | Phase 201 = SPEC + PLAN that names the queue-depth signal up front. Cross-AI review catches wrong signal choice before deploy. | ✓ |
| Spike first (`/gsd-spike`), then a smaller Phase 201 | Run a `/gsd-spike` instrumenting queue-depth signal candidates against live Spectrum saturation, then a tighter Phase 201. Lower risk, higher cost. | |
| Hybrid - single phase with an in-phase observability-only Plan first | First plan ships `/health` DOCSIS-mode telemetry (no controller change), validates signal under saturation, then second plan ships controller change. | |

**User's choice:** Single phase, signal locked at design.
**Notes:** Phase 200 RETRO already eliminated architectural ambiguity (residual regime is shaping-headroom dominated). A spike's value would be picking the signal, not validating the conclusion. Cross-AI review (Codex + Claude) is the bug-catching mechanism, mirroring the high-leverage Phase 200 pattern.

---

## Setpoint signal source

| Option | Description | Selected |
|--------|-------------|----------|
| Static-only — no dynamic probe, pure setpoint clamp | Degenerates option A to option B: fixed YAML setpoint, never push past. Simplest; sacrifices peak UL on every cycle. | |
| RTT integral over a window (Phase 200 option C, alone) | Replace RTT-delta with integral-of-RTT-over-baseline. Captures CMTS queueing because RTT traverses CMTS queue. No new transport. | |
| Hybrid: setpoint + RTT integral | YAML setpoint as operating point. RTT integral as headroom probe — push toward ceiling only when integral has been low for sustained window. CAKE backlog as direction-aligned secondary corroborator. Maps to seed option D. | ✓ |
| Modem SNMP / DOCSIS HCS counter | Read CMTS-side or modem-side queue depth via SNMP. Most authentic. Adds new transport + dependency on modem firmware. Higher risk. | |

**User's choice:** Hybrid: setpoint + RTT integral.
**Notes:** Codebase scout confirmed UL `CakeSignalSnapshot` already exposes `backlog_bytes` and `max_delay_delta_us` — secondary corroborator does not need new signal-collection wiring. Mirrors v1.40 queue-primary direction-aligned pattern (Phase 197 dl_cake_for_arbitration semantics). Modem SNMP option D-05 deferred to v1.43+ if hybrid proves insufficient.

---

## Setpoint default + tuning surface

| Option | Description | Selected |
|--------|-------------|----------|
| YAML opt-in `docsis_mode: true` + operator-supplied `setpoint_mbps` (no default) | New `continuous_monitoring.upload.docsis_mode` boolean (default false). When true, `setpoint_mbps` is required (validator fails closed if missing). No principled global default — link-specific. Restart-required. | ✓ |
| YAML opt-in `docsis_mode: true` + `setpoint_pct: 0.60` default | Setpoint as fraction of ceiling. Easier portability; less link-specific tuning. Mixes two YAML schemas. | |
| Three-key surface: `docsis_mode` + `setpoint_mbps` + optional `setpoint_pct` | Both keys allowed; `setpoint_mbps` wins if both set. Maximum flexibility, more validator complexity. | |

**User's choice:** YAML opt-in + operator-supplied `setpoint_mbps` (no default).
**Notes:** Restart-required (NOT live-tunable via SIGUSR1). SIGUSR1 reload scope stays narrow (dwell/deadband only at `wan_controller.py:1894-1899`); expanding for control-mode keys is risky on the control path per CLAUDE.md priority order.

---

## Spectrum-specific setpoint value

| Option | Description | Selected |
|--------|-------------|----------|
| 12 Mbit (60% of 18 Mbit ceiling, 60% of ~20 Mbit provisioned) | Seed's preferred conservative choice. Sacrifices ~33% peak UL on the ceiling-vs-setpoint comparison. | (Claude pick) |
| 14 Mbit (~78% of ceiling) | Less peak sacrifice (~22%). Closer to Phase 200's rejected 18 Mbit. Higher risk canary still hits floor. | |
| Defer to research — planner picks from spectrum-*-2026-04-29.md sweep evidence | Researcher reads three Spectrum sweep notes and recommends value with evidence; planner locks in SPEC. | |

**User's choice:** "you decide" → Claude picked **12 Mbit**.
**Rationale:** 60% of provisioned upstream rate (~20 Mbit), gives 6 Mbit ceiling-margin and ~8 Mbit provisioned-margin — actual shaping headroom for wanctl's CAKE qdisc to absorb bufferbloat before the CMTS queue fills. Phase 200 evidence showed the 2 Mbit gap (18 ceiling vs ~20 provisioned) was insufficient (122 → 4 floor hits with threshold-only stack); 14 Mbit at only 4 Mbit ceiling-margin (22%) was flagged in seed as same architectural failure mode at smaller amplitude. Marked as Claude-discretion in CONTEXT D-09; subject to challenge during research / plan / cross-AI review using the three Spectrum sweep notes.

---

## VALN-06 closure shape + canary reuse

| Option | Description | Selected |
|--------|-------------|----------|
| Reuse Phase 200 canary, extend YAML cross-check + add /health DOCSIS-mode probe | Same `scripts/phase200-saturation-canary.sh`. Extend preflight YAML cross-check for `setpoint_mbps` and `docsis_mode: true`. Add /health DOCSIS-mode probe. Keep zero-floor-hit gate. Keep 24h soak watchdog at <5/60s. Same fail-closed rollback. | ✓ |
| Same as above + tighter soak threshold (<2/60s) | Same canary + extension, but tighten soak watchdog. Justified if higher bar wanted. | |
| Sibling canary script (`phase201-saturation-canary.sh`) | Fork to new name with DOCSIS-mode-specific preflight + verdict logic. Cleaner separation but loses Phase 200 bug-fix history. | |

**User's choice:** Reuse Phase 200 canary, extend YAML cross-check + add /health DOCSIS-mode probe.
**Notes:** Phase 200 tooling caught real production bugs (logger silent-drop, /health field assumption, env-var false-PASS regression). Forking would lose that hardening. Extension lands in preflight + new env var (`PHASE201_SETPOINT_MBPS` or similar) + /health probe assertion. Soak watchdog stays at `<5/60s` for Phase 201 first run; tightening deferred until soak data justifies it.

---

## Final wrap

| Option | Description | Selected |
|--------|-------------|----------|
| Write CONTEXT.md | Decisions captured. Predeploy-gate behavior, ATT no-op, tuning details flow as locked defaults from seed + CLAUDE.md. | ✓ |
| Predeploy gate behavior — strip rejected v1.41 keys, or abort? | Discuss strip+reconcile vs abort+manual reconcile. | |
| Milestone home — v1.42 scope or solo phase | Discuss whether v1.42 includes consolidating deferred ATT VALN-05b. | |

**User's choice:** Write CONTEXT.md. Predeploy-gate action shape and milestone home are noted as planner / `/gsd-new-milestone` decisions in CONTEXT.

---

## Claude's Discretion

- **D-09 Spectrum setpoint value = 12 Mbit.** User said "you decide" on the four-option pick; Claude chose 12 Mbit on Phase 200 evidence + seed framing. Marked open-to-challenge in CONTEXT.

## Deferred Ideas

- Modem SNMP / DOCSIS HCS counter signal (option d in Area 2) — to v1.43+ only if RTT-integral + CAKE-backlog hybrid proves insufficient.
- Tighter soak watchdog `<2/60s` — to v1.43+ once Phase 201 establishes steady-state suppression rate.
- DOCSIS-mode auto-tuning of `setpoint_mbps` — future research/spike candidate.
- Predeploy-gate action shape (strip vs abort) — planner-level decision in PLAN phase.
- Milestone home (v1.42 solo vs v1.42 + ATT VALN-05b consolidation) — `/gsd-new-milestone` decision.
- VALN-05b ATT cake-primary canary — cross-milestone, gated on v1.39 Phase 191 closure.
