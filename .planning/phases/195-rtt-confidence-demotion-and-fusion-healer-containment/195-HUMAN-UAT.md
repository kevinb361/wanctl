---
status: resolved
phase: 195-rtt-confidence-demotion-and-fusion-healer-containment
source: [195-VERIFICATION.md]
started: 2026-04-24T12:39:35-05:00
updated: 2026-04-24T18:47:14+00:00
---

## Current Test

Completed production verification on cake-shaper after a code-only Phase 195 deploy
and restart of wanctl@spectrum.service and wanctl@att.service at 2026-04-24
12:44:27 CDT. Raw health samples are on the production host at
/tmp/wanctl-phase195/phase195-health-samples.jsonl.

## Tests

### 1. SC-1 production rtt_confidence observation
expected: On a cake_signal-supported WAN, /health signal_arbitration.rtt_confidence and SQLite wanctl_rtt_confidence show non-null floats in [0.0, 1.0] across a 1-hour production window and track ICMP/UDP plus queue-direction agreement.
result: passed - /health was sampled every 10 seconds from 2026-04-24T17:45:49Z to 2026-04-24T18:45:44Z with 360 samples per WAN and zero collection errors. Both WANs reported healthy for all samples. Health rtt_confidence ranged from 0.0 to 1.0. SQLite wanctl_rtt_confidence rows over the same window were present and non-null: spectrum 70,344 rows, att 70,387 rows, each with min 0.0 and max 1.0.

### 2. SC-2 production low-confidence RTT spike trace
expected: During a queue-GREEN RTT spike with rtt_confidence < 0.6, control_decision_reason is not rtt_veto and DL zone transitions do not escalate from the RTT path.
result: passed - SQLite cycle reconstruction found low-confidence queue-GREEN RTT spikes where active primary stayed queue. Spectrum example at 2026-04-24T18:09:03Z: rtt_confidence 0.0, queue_delta_us 2.0, rtt_delta_ms 210.74, active_primary 1.0 queue, fusion_active 0.0. ATT example at 2026-04-24T18:39:33Z: rtt_confidence 0.0, queue_delta_us 194.0, rtt_delta_ms 10.84, active_primary 1.0 queue, fusion_active 0.0.

### 3. SC-3 production single-path flip trace
expected: During a single-path ICMP/IRTT flip with queue GREEN for at least 6 cycles, control_decision_reason never shows healer_bypass and fusion bypass remains inactive.
result: passed - Journal after the Phase 195 restart recorded protocol-deprioritization / single-path flip events, including spectrum ratio 0.62 at 2026-04-24 12:45:00 CDT and multiple ATT ratio flips from 0.23 to 1.52. Across the full health sample, fusion_bypass_active stayed false with reason None for all 720 samples. SQLite fusion_bypass_active max was 0.0 for both WANs, and the filtered journal showed no healer_bypass or queue_rtt_aligned entries.

## Summary

total: 3
passed: 3
issues: 0
pending: 0
skipped: 0
blocked: 0

## Gaps
