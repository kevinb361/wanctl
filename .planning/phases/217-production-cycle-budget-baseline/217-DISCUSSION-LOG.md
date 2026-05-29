# Phase 217: Production Cycle-Budget Baseline - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-29
**Phase:** 217-production-cycle-budget-baseline
**Areas discussed:** Target WAN, Load conditions, Reference baseline, Capture & safety

---

## Target WAN

| Option | Description | Selected |
|--------|-------------|----------|
| Spectrum only | Cable, live 1.45.0 besteffort wash, active quality-concern link, milestone subject. | ✓ |
| ATT only | DSL, diffserv4; different transport, not the milestone subject. | |
| Both WANs | Full picture but doubles capture/analysis cost + risk on the 24/7 loop. | |

**User's choice:** "what do you think" → locked recommended (Spectrum only).
**Notes:** Spectrum is the v1.46 quality-concern link and on current production version.

---

## Load conditions

| Option | Description | Selected |
|--------|-------------|----------|
| Organic + driven segment | ~1h organic steady-state + short driven RRUL/upload segment (Phase 213 harness) to catch under-load router-write cost. | ✓ |
| Organic traffic only | Pure passive 1h; may under-sample router-write path if quiet. | |
| Fully driven (harness) | Maximizes hot-path exercise but synthetic, not representative steady-state. | |

**User's choice:** "what do you think" → locked recommended (Organic + driven segment).
**Notes:** Router writes are change-gated (flash-wear guard), so a quiet household under-samples that path.

---

## Reference baseline

| Option | Description | Selected |
|--------|-------------|----------|
| Absolute health bars | 50ms budget headroom + no-subsystem-over-40% dominance test; drop the unanchored ±15%-vs-v1.39 clause. | ✓ |
| Reconstruct v1.39 number | Dig archived v1.0/v1.9 artifacts, honor ±15%/±25% literally; more archaeology. | |
| Relax to new reference | Document v1.45 budget as new canonical, skip historical comparison entirely. | |

**User's choice:** "what do you think" → locked recommended (Absolute health bars).
**Notes:** No concrete v1.39-era cycle-budget number was ever committed as data, so the original comparison is unfalsifiable. This reinterprets the todo's close conditions 1/2 (documented in CONTEXT.md D-03/D-04).

---

## Capture & safety

| Option | Description | Selected |
|--------|-------------|----------|
| Override drop-in + runbook | systemd override drop-in for --profile, ≥1h, revert, commit artifact to .planning/perf/ + summary, create docs/PROFILING.md. | ✓ |
| Override drop-in, no runbook | Same safe enable/revert + artifact, skip docs/PROFILING.md. | |
| Ad-hoc manual enable | Fastest, but no clean rollback path or durable procedure. | |

**User's choice:** "what do you think" → locked recommended (Override drop-in + runbook).
**Notes:** docs/PROFILING.md is referenced by the todo's files block but does not exist. Profiling observer-effect to be quantified by research.

---

## Claude's Discretion

User deferred all four gray areas to Claude ("what do you think"); recommended option locked for each. Remaining discretion: driven-segment duration, analyze_profiling.py invocation, summary format, observer-effect treatment.

## Deferred Ideas

- Actual optimization work (RTT-path, metrics/logging allocation, router/transport cost) — out of scope; becomes a v1.46+ phase only if data promotes the todo.
- ATT cycle-budget profile — Spectrum-only this phase; separate pass if DSL budget later becomes a concern.
