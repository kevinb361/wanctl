# Phase 215: Spectrum Upload Reclaim Canary - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-29
**Phase:** 215-spectrum-upload-reclaim-canary
**Areas discussed:** Knob & direction, Success gate, Rollback gate + Snapshot A, Measurement + 214 confounder

---

## Knob & Direction

| Option | Description | Selected |
|--------|-------------|----------|
| setpoint_mbps 12 → 14 | Raise DOCSIS congestion target, ceiling stays 18; gentlest, config names setpoint→10 as fallback | |
| ceiling_mbps 18 → 20 | Raise hard cap +2; the binding knob per baseline; small controlled probe | ✓ (Claude's discretion) |
| ceiling_mbps 18 → 22 | Aggressive ceiling raise (~55% of plan); largest latency exposure | |
| Decide not to tune | Conclude 12/18 correctly placed; document no-change | |

**User's choice:** "you decide" → resolved to **ceiling 18→20**.
**Notes:** Baseline showed upload pegged at ceiling 18 for 81.46% of `tcp_upload` samples ⇒ ceiling is the binding constraint and setpoint raise would be a near-no-op / false pass. Chose +2 over +4 because `step_up_mbps` is 5 and +2 is the smallest controlled probe; 22 deferred to a possible follow-up cycle.

---

## Success Gate

| Option | Description | Selected |
|--------|-------------|----------|
| Throughput reclaim | Sustained upload under tcp_upload ↑ ≥ ~1.5 Mbps vs 213 baseline; latency handled by rollback gate | ✓ |
| Quality grade improves | libreqos bufferbloat grade holds/improves, throughput non-regressing | |
| Both required (AND-gate) | Throughput up AND quality non-regressing; strictest, risk of false fails on grade noise | |

**User's choice:** Throughput reclaim.
**Notes:** Win condition kept separate from latency (which is the rollback gate) to avoid double-counting.

---

## Rollback Gate + Snapshot A

| Option | Description | Selected |
|--------|-------------|----------|
| Strict / latency-first | Revert if p95/p99 > baseline +10%, OR sustained > warn_bloat_ms 75ms, OR floor-hits >0, OR alert flapping | ✓ (Claude's discretion) |
| Moderate | Revert if p95/p99 > baseline +25%, OR > hard_red 100ms, OR floor-hits >0, OR flapping | |
| Absolute-only | Revert only on hard_red >100ms / floor-hits >0 / flapping; most permissive | |

**User's choice:** "you decide" → resolved to **Strict / latency-first**.
**Notes:** 18 was chosen as the p95/p99 winner; ceiling=20 should only stick if it costs almost no latency. Snapshot A reuses the Phase 211 pattern (capture config+state+/health → deploy → restart → verify bound endpoint).

---

## Measurement + 214 Confounder

| Option | Description | Selected |
|--------|-------------|----------|
| Fail-closed + VOID, libreqos supplementary | Phase 214 fail-closed extractor; collapse → VOID; 18→20 A/B back-to-back; libreqos non-gating | ✓ |
| Fail-closed + VOID, flent-only | Same guard, drop libreqos from scope | |
| libreqos as co-primary signal | Elevate libreqos grade to gating; adds un-baselined instrument | |

**User's choice:** Fail-closed + VOID, libreqos supplementary.
**Notes:** Phase 213 saw `signal_outlier_rate` 0.933 on Spectrum `tcp_upload`; 214 showed time/path sensitivity ⇒ back-to-back A/B + VOID-on-collapse guard. libreqos's noise floor not yet baselined, so non-gating.

---

## Claude's Discretion

- Knob selection + magnitude (ceiling 18→20).
- Rollback gate strictness (strict / latency-first).
- Baseline-freshness mechanics, observation-window duration, and time-of-day window selection left to research/planning.

## Deferred Ideas

- ceiling_mbps → 22 follow-up cycle (only if 20 passes; one knob per cycle).
- Baseline libreqos-cli.mjs's own noise floor for future gating use.
- setpoint reclaim (ruled out by pegged-at-ceiling evidence this phase).
- Reviewed-not-folded: `2026-04-24-resolve-att-cake-primary-canary-after-phase-196.md` (different control-model concern, gated on Phase 191/196).
