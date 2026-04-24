---
status: partial
phase: 195-rtt-confidence-demotion-and-fusion-healer-containment
source: [195-VERIFICATION.md]
started: 2026-04-24T12:39:35-05:00
updated: 2026-04-24T12:39:35-05:00
---

## Current Test

[awaiting human testing]

## Tests

### 1. SC-1 production rtt_confidence observation
expected: On a cake_signal-supported WAN, /health signal_arbitration.rtt_confidence and SQLite wanctl_rtt_confidence show non-null floats in [0.0, 1.0] across a 1-hour production window and track ICMP/UDP plus queue-direction agreement.
result: [pending]

### 2. SC-2 production low-confidence RTT spike trace
expected: During a queue-GREEN RTT spike with rtt_confidence < 0.6, control_decision_reason is not rtt_veto and DL zone transitions do not escalate from the RTT path.
result: [pending]

### 3. SC-3 production single-path flip trace
expected: During a single-path ICMP/IRTT flip with queue GREEN for at least 6 cycles, control_decision_reason never shows healer_bypass and fusion bypass remains inactive.
result: [pending]

## Summary

total: 3
passed: 0
issues: 0
pending: 3
skipped: 0
blocked: 0

## Gaps
