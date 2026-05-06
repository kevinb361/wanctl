---
id: SEED-004
status: dormant
planted: 2026-05-06
planted_during: Phase 201 closeout (Plan 201-17) per operator Route B
trigger_when: v1.43 milestone planning AFTER SEED-002 OR concurrently with SEED-002 if scoped together
scope: Small
priority: 3
prerequisites: [SEED-002]
priority_rationale: "Per-sample load_rtt - baseline_rtt distribution is the diagnostic surface needed before SEED-005's target_bloat_ms tune; SEED-002's metric semantics work establishes the precedent for additive /health and soak-schema fields without breaking existing harness."
---

# SEED-004: target-edge churn instrumentation

> **This seed must not be executed before SEED-002 lands** — the additive `/health` and soak-schema precedent established by SEED-002 is the pattern this seed mirrors. Reading this seed alone, defer to SEED-002 for the schema-extension conventions before adding new fields.

## Why This Matters

The Plan 201-16 24h soak captured RTT integral, zone trace, and CAKE max-delay-delta but **NOT** the per-sample `load_rtt - baseline_rtt` delta. This is the dominant signal that drives target-edge YELLOW classification and dwell-hold suppression — without it, the question "is dwell churn driven by load_rtt sitting near `target_delta` or by spikes above `warn_delta`?" cannot be answered from the existing capture.

Codex correlation analysis on the 20260505T132736Z capture localized D-14 FAIL to the YELLOW-edge dwell-hold path (`_apply_dwell_logic` at `queue_controller.py:348`) with suppression-vs-YELLOW correlation 0.72. That separation is enough to defer D-14 work via Route B but not enough to safely tune `dwell_cycles` or `target_bloat_ms` (SEED-005). A per-sample distribution capture is required first.

This is a soak-schema additive change, not a control-path change. Add the **per-sample delta** as a first-class soak field plus histogram aggregation in soak-summary.json so future plans can read the target-edge distribution directly.

## When to Surface

**Trigger:** v1.43 milestone planning. May be scoped concurrently with SEED-002 if both are presented as paired observability work, but SEED-002's metric-semantics work has higher priority for unblocking SEED-003.

This seed is the **third item** in the v1.43 backlog. **Prerequisite: SEED-002 (for additive /health + soak-schema precedent).**

## Scope Estimate

**Small** — additive soak schema field + harness aggregation.

1. **Soak NDJSON schema addition:** emit per-sample `load_rtt_delta_us` (= `effective_ul_load_rtt - baseline_rtt_ms` in microseconds) on every sample.
2. **soak-summary.json aggregation:** histogram + p50/p95/p99/max of `load_rtt_delta_us` over the soak window, broken down by zone and by cause-tag from SEED-002.
3. **Tests:** golden-fixture replay confirming the new field is populated and aggregated correctly.
4. **Documentation:** soak harness README update; CHANGELOG note.

No production binary change required if the soak-capture script reads existing exposed `/health` fields and computes the delta locally.
