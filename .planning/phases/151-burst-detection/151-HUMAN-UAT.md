---
status: partial
phase: 151-burst-detection
source: [151-VERIFICATION.md]
started: 2026-04-09T00:00:00Z
updated: 2026-04-09T00:00:00Z
---

## Current Test

[awaiting human testing]

## Tests

### 1. tcp_12down Burst Trigger
expected: Run `flent tcp_12down` from dev machine while monitoring `journalctl -u wanctl@spectrum -f | grep BURST` on cake-shaper. "BURST detected" log entry appears within 200ms of flow onset.
result: [pending]

### 2. rrul_be No False Trigger
expected: Run `flent rrul_be` from dev machine while monitoring `journalctl -u wanctl@spectrum -f | grep BURST` on cake-shaper. Zero "BURST detected" entries during the entire run.
result: [pending]

## Summary

total: 2
passed: 0
issues: 0
pending: 2
skipped: 0
blocked: 0

## Gaps
