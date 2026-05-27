---
phase: 213-experience-baseline-harness
reviewed: 2026-05-27T22:48:31Z
depth: standard
files_reviewed: 17
files_reviewed_list:
  - docs/RUNBOOKS/baseline.md
  - scripts/phase213-alert-window.sh
  - scripts/phase213-baseline-capture.sh
  - scripts/phase213-browse-loop.sh
  - scripts/phase213-classify.py
  - scripts/phase213-health-poller.sh
  - scripts/phase213-steering-snapshot.sh
  - tests/conftest.py
  - tests/fixtures/phase213/alerts-test.db
  - tests/fixtures/phase213/health-att-snapshot.json
  - tests/fixtures/phase213/health-spectrum-snapshot.json
  - tests/fixtures/phase213/health-steering-snapshot.json
  - tests/test_phase213_alert_window.py
  - tests/test_phase213_classify.py
  - tests/test_phase213_manifest_schema.py
  - tests/test_phase213_mutation_boundary.py
  - tests/test_phase213_ndjson_schema.py
findings:
  critical: 0
  warning: 2
  info: 0
  total: 2
status: issues_found
---

# Phase 213: Code Review Report

**Reviewed:** 2026-05-27T22:48:31Z
**Depth:** standard
**Files Reviewed:** 17
**Status:** issues_found

## Summary

Reviewed the Phase 213 runbook, baseline harness shell/Python helpers, health/alert/steering fixtures, and pytest coverage. The implementation preserves the intended evidence-only/no-mutation posture in the reviewed code, with no critical security issues found. Two correctness risks remain: poller failures can be masked by the orchestrator, and unrecovered RED/SOFT_RED windows can be misclassified as zero recovery lag.

## Warnings

### WR-01: Orchestrator masks health-poller aborts

**File:** `scripts/phase213-baseline-capture.sh:113-119`
**Issue:** `cleanup_pollers` kills each poller and ignores `wait` status with `|| true`. If `phase213-health-poller.sh` exits early because the lifetime failure-rate threshold is exceeded, the orchestrator can continue, snapshot alerts, and classify an incomplete evidence window as if it were valid.
**Fix:** Preserve and fail on already-exited non-zero poller statuses before suppressing expected SIGTERM statuses for pollers that are still running. For example:

```bash
cleanup_pollers() {
  local pid failed=0
  for pid in "${POLLER_PIDS[@]:-}"; do
    if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
      kill "$pid" 2>/dev/null || true
      wait "$pid" 2>/dev/null || true  # expected after orchestrator stop
    elif [[ -n "$pid" ]]; then
      wait "$pid" || failed=1          # unexpected early exit
    fi
  done
  POLLER_PIDS=()
  return "$failed"
}
```

Then call it in `run_bracketed_test` as `cleanup_pollers || return 1` so bad health capture fails the run rather than producing partial evidence.

### WR-02: Unrecovered RED/SOFT_RED is recorded as zero recovery lag

**File:** `scripts/phase213-classify.py:146-159`
**Issue:** `analyze_download_recovery` leaves `green_after` as `None` when a test window enters RED/SOFT_RED and never returns to confirmed GREEN. It then computes `lag = float(green_after or 0)`, making a non-recovery look like `0` seconds and preventing the download-recovery bucket from flagging.
**Fix:** Track whether RED/SOFT_RED occurred and mark unrecovered windows as flagged, using elapsed samples as the lower-bound lag or an explicit `recovered: false` field. For example:

```python
entered_red = last_red_idx is not None
if green_after is None and entered_red:
    lag = max(0, len(rows) - 1 - last_red_idx)
    recovered = False
else:
    lag = float(green_after or 0)
    recovered = True
evidence.append({
    "wan": wan,
    "test": test,
    "recovered": recovered,
    "time_to_green_after_red_sec": lag,
    "cake_dl_peak_delay_us_p99": peak_p99,
})
```

Include `not r.get("recovered", True)` in the bucket flag condition.

---

_Reviewed: 2026-05-27T22:48:31Z_
_Reviewer: the agent (gsd-code-reviewer)_
_Depth: standard_
