---
phase: 181-production-footprint-reduction-and-reader-parity
plan: 03
status: completed_with_gap
requirements-completed: ""
date: 2026-04-14
---

# Plan 181-03 Summary

## Intended goal

Capture final production footprint evidence, confirm post-change reader behavior, and close `STOR-06` only if the live host proved the claim.

## What happened

The original live validation attempt was blocked by daemon startup behavior after restart.

That blocker was then resolved inside Phase 181:

- pre-health startup storage work was bounded so restart no longer collides with the watchdog budget
- both WAN daemons now restart successfully under the repo-default `WatchdogSec=30s`
- `/health`, canary, and soak-monitor became usable again as operator validation surfaces

## What was learned

- the explicit Spectrum offline compaction path did reclaim real DB size
- the startup blocker was in pre-health storage work, not in the Phase 181 history-reader changes
- the live reader-role story is now explicit and proven:
  - CLI merges `att` and `spectrum`
  - `/metrics/history` is endpoint-local and exposes `metadata.source`

## Phase implication

Plan 03 is now complete as evidence capture, but it closes with a requirement gap rather than a full milestone win.

`STOR-06` still cannot be honestly closed, because:
- Spectrum is materially smaller, but ATT is still effectively unchanged versus the fixed baseline
- canary and soak-monitor are working again, but Spectrum currently reports a non-blocking runtime warning
- the per-WAN footprint reduction claim therefore remains incomplete in production terms
