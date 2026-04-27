---
phase: 197-queue-primary-refractory-semantics-split-dl-cake-for-detecti
reviewed: 2026-04-27T11:32:23Z
depth: standard
files_reviewed: 6
files_reviewed_list:
  - src/wanctl/wan_controller.py
  - src/wanctl/health_check.py
  - tests/test_phase_197_replay.py
  - tests/test_wan_controller.py
  - tests/test_health_check.py
  - scripts/phase196-soak-capture.sh
findings:
  critical: 0
  warning: 1
  info: 0
  total: 1
status: issues_found
---

# Phase 197: Code Review Report

**Reviewed:** 2026-04-27T11:32:23Z
**Depth:** standard
**Files Reviewed:** 6
**Status:** issues_found

## Summary

Reviewed the Phase 197 controller arbitration split, health rendering, replay/metric tests, and the soak capture helper. The core controller and health-path changes look consistent with the intended refractory semantics: detection masking remains separate from queue-primary arbitration, health exposes the new refractory flag, and DL-only metric emission is covered. One warning was found in the operator evidence script: it reads burst counters from paths that are not present in the health payload, so captured summaries can falsely report zero burst activity.

## Warnings

### WR-01: Soak summary reads burst counters from nonexistent health paths

**File:** `scripts/phase196-soak-capture.sh:221-222`
**Issue:** The health payload exposes burst telemetry under `cake_signal.burst` (see `src/wanctl/health_check.py:732-754` and `src/wanctl/wan_controller.py:4203-4214`), but the capture script reads `download.burst.trigger_count` and `upload.burst.trigger_count`. Those paths are absent in the rendered WAN health structure, so both summary counters default to `0` even when a DL burst has actually occurred. This can hide Phase 197 soak evidence and make canary/audit artifacts misleading.
**Fix:** Read the existing `cake_signal.burst.trigger_count` field for the DL burst count, and either remove/rename the UL counter or source it from a real UL health field if one is added later. For the current payload shape:

```bash
download_burst_trigger_count="$(jq -r '(.wans[0] // .).cake_signal.burst.trigger_count // 0 | floor' "$RAW_HEALTH")"
upload_burst_trigger_count="0"
```

---

_Reviewed: 2026-04-27T11:32:23Z_
_Reviewer: the agent (gsd-code-reviewer)_
_Depth: standard_
