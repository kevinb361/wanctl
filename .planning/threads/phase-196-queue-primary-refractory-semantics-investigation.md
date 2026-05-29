---
slug: phase-196-queue-primary-refractory-semantics-investigation
title: Phase 196 Queue-Primary Refractory Semantics Investigation
status: closed
created: 2026-04-27
updated: 2026-05-29
---

# Thread: Phase 196 Queue-Primary Refractory Semantics Investigation

## Goal

Review whether Phase 160 CAKE refractory masking is still correct after Phase 194/195 made CAKE queue-delay the primary download distress signal, and decide whether a follow-up phase should redesign refractory semantics.

## Context

Phase 196 corrected Spectrum throughput validation failed after source-bind correction.

Observed evidence:

- Corrected Spectrum source is `10.10.110.226`, public egress `70.123.224.169`, `AS11427 Charter Communications Inc`.
- `10.10.110.233` exits AT&T (`99.126.115.47`, `AS7018 AT&T`) and invalidates the earlier labeled-Spectrum throughput captures for Spectrum acceptance.
- Corrected `tcp_12down` median: `307.9225832916394 Mbps` vs `532 Mbps` threshold.
- Diagnostic rerun reproduced the miss: `302.8955957721772 Mbps`.
- Spectrum qdisc is installed correctly: download `940Mbit` on `ens17`, upload `32Mbit` on `ens16`.
- During load, health transitions from `940 Mbps GREEN queue` to around `350 Mbps YELLOW rtt`.
- `active_primary_signal=rtt` with non-null `cake_av_delay_delta_us` is expected with current code because arbitration uses masked `dl_cake`, while health displays the latest raw `_dl_cake_snapshot`.

Code path:

- `queue_controller.py` sets `dwell_bypassed_this_cycle` when raw DL state is `YELLOW` and `cake_snapshot.drop_rate` exceeds threshold.
- `wan_controller.py` sees `dwell_bypassed_this_cycle` and sets `_dl_refractory_remaining = 40`.
- During refractory, `wan_controller.py` sets `dl_cake = None` before arbitration/classification.
- `_select_dl_primary_scalar_ms(dl_cake)` receives `None` and returns RTT fallback.
- `download.adjust_4state(...)` then uses RTT-derived `load_rtt` and `cake_snapshot=None`.

Important research:

- This was intentional in Phase 194, not accidental.
- `.planning/phases/194-download-queue-primary-distress-classification/194-PATTERNS.md` says the selector MUST run after refractory masking and must see masked `dl_cake`.
- `.planning/phases/194-download-queue-primary-distress-classification/194-01-PLAN.md` says DO NOT read `self._dl_cake_snapshot` inside selector.
- `tests/test_wan_controller.py` explicitly asserts refractory masks snapshots.
- Phase 163 retained `refractory_cycles=40` conservatively because shorter cooldown risks cascading reductions on single events.

Current conclusion:

This is a design conflict between Phase 160 refractory safety and Phase 194/196 queue-primary throughput goals. Do not patch directly without a follow-up design/phase.

## References

- `.planning/phases/196-spectrum-a-b-soak-and-att-regression-canary/196-12-SUMMARY.md`
- `.planning/phases/196-spectrum-a-b-soak-and-att-regression-canary/soak/cake-primary/throughput-root-cause-investigation.json`
- `.planning/phases/194-download-queue-primary-distress-classification/194-PATTERNS.md`
- `.planning/phases/194-download-queue-primary-distress-classification/194-01-PLAN.md`
- `.planning/milestones/v1.33-phases/163-parameter-sweep/163-02-SUMMARY.md`
- `src/wanctl/wan_controller.py`
- `src/wanctl/queue_controller.py`
- `tests/test_wan_controller.py`

## Next Steps

- Reopen with Claude and ask for a second opinion on the design conflict.
- Decide whether to create a follow-up phase/spec named something like `Queue-Primary Refractory Semantics`.
- Any follow-up must preserve Phase 160 safety: no cascading CAKE drop/backlog reductions.
- Any follow-up should preserve queue-primary intent: valid queue-delay scalar remains available for DL classification during refractory, unless research proves that unsafe.
- Candidate design to investigate, not yet approved: split `dl_cake_for_detection` from `dl_cake_for_arbitration`; keep detection CAKE masked during refractory, but keep queue-delay scalar available for primary classification.
- Required tests if a change is approved: no repeated CAKE detection cascade during refractory, fallback still works when queue signal is genuinely unavailable, and `active_primary_signal` remains `queue` during refractory when a valid queue snapshot exists.

## Closeout (Phase 216)

**Verdict:** no-change / resolved-by-197.

Phase 197 shipped the candidate split design named above: `dl_cake_for_detection` stays masked during refractory for Phase 160 cascade safety, while `dl_cake_for_arbitration` keeps the queue-delay scalar live for queue-primary arbitration. The thread was stale-open because that resolution was never mirrored here; Phase 216 closes it explicitly rather than silently overwriting the history.

Exit-criteria findings:

- **D-02 artifact:** Phase 213's `backlog_suppressed_delta=14451` refractory flag is a cross-WAN merge artifact over a cumulative lifetime counter, not a per-event refractory distress signal.
- **D-03 semantic proof:** Phase 197's replay/classifier slice passed (`21 passed`), including `queue_during_refractory`, `rtt_fallback_during_refractory`, and `TestPhase197NoCascadeOnDetection`.
- **D-01 no-symptom framing:** Phase 213 shows no current symptom under the passive baseline, but it did not exercise a refractory window and is not tuning evidence.

Reopen this thread, or open a successor, if a natural production artifact shows `signal_arbitration.refractory_active == true` with RTT fallback under queue-primary load, measurable RED/SOFT_RED recovery lag, or throughput collapse during the refractory window. Also reopen on the telemetry-independent Phase 196 symptom signature: valid queue-delay signal present while `active_primary_signal == "rtt"` under queue-primary download load.

Closeout report: `.planning/phases/216-recovery-refractory-decision/216-REPORT.md`.
