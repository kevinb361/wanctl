---
phase: 203-target-edge-churn-instrumentation-obsv
reviewed: 2026-05-06T23:03:34Z
depth: standard
files_reviewed: 10
files_reviewed_list:
  - scripts/soak-capture.sh
  - tests/test_phase_203_capture_projection.py
  - scripts/soak_summary_aggregate.py
  - tests/fixtures/_phase_203_generator.py
  - tests/fixtures/phase_203_synthetic_capture.ndjson
  - tests/fixtures/phase_203_synthetic_summary.json
  - tests/test_phase_203_replay.py
  - docs/SOAK_HARNESS.md
  - CHANGELOG.md
  - scripts/check-safe07-source-diff.sh
findings:
  critical: 0
  warning: 2
  info: 0
  total: 2
status: issues_found
---

# Phase 203: Code Review Report

**Reviewed:** 2026-05-06T23:03:34Z  
**Depth:** standard  
**Files Reviewed:** 10  
**Status:** issues_found

## Summary

Reviewed the Phase 203 soak-capture harness, projection tests, summary aggregator, deterministic fixtures/goldens, replay tests, operator docs, changelog entries, and SAFE-07 gate. The aggregator math is well-covered for the requested focus areas: bucket boundaries and overflow, percentile output, null filtering, first-row exclusion, dual-attribution, v1.42 diagnostic compatibility, fixture drift, and upload-only zone-axis semantics.

No `src/wanctl/**` files are changed in committed history relative to the Phase 202 close reference, and the Phase 203 test slice passed during review:

- `bash scripts/check-safe07-source-diff.sh` → passed (`SAFE-07 OK: no src/wanctl/ diff vs b72b463`)
- `.venv/bin/pytest tests/test_phase_203_capture_projection.py tests/test_phase_203_replay.py -q` → 22 passed
- `git diff --stat b72b463..HEAD -- src/wanctl/` → empty

Two warning-level robustness issues remain actionable before closeout: the SAFE-07 verifier can false-pass with uncommitted control-path edits, and the long-running capture script aborts the entire soak on a single transient `/health`/`jq` failure.

## Warnings

### WR-01: SAFE-07 gate ignores uncommitted `src/wanctl/` edits

**File:** `scripts/check-safe07-source-diff.sh:32`  
**Issue:** The gate runs `git diff "${REF}..HEAD" -- src/wanctl/`, which compares only committed history between the Phase 202 close ref and `HEAD`. If an operator or workflow has staged or unstaged `src/wanctl/**` changes in the worktree, the script can still print `SAFE-07 OK`, creating a false-pass for the hard no-control-path-change invariant.  
**Fix:** Compare the working tree against the reference, or run both committed and worktree checks. For example:

```bash
DIFF_OUTPUT=$(git diff "${REF}" -- src/wanctl/ 2>&1 || true)
```

If you want to keep the committed-range wording explicit, add a second check before the OK path:

```bash
WORKTREE_DIFF=$(git diff -- src/wanctl/ 2>&1 || true)
STAGED_DIFF=$(git diff --cached -- src/wanctl/ 2>&1 || true)
```

and fail if either is non-empty.

### WR-02: Capture script can lose a 24h soak on one transient fetch/projection failure

**File:** `scripts/soak-capture.sh:28-58`  
**Issue:** The script runs `curl -s "$HEALTH_URL" | jq ... >> soak-capture.ndjson` under `set -euo pipefail`. A transient connection failure, timeout, HTTP error with non-JSON body, or momentary partial response will terminate the entire capture loop instead of preserving the soak and recording/skipping the failed sample. For a 24h evidence harness, this can turn a brief observability blip into a complete missing-artifact failure.  
**Fix:** Make the per-sample fetch fail closed for that row but continue the soak, while still making failures visible. For example, use timeout/fail flags and an explicit branch:

```bash
if curl --fail --silent --show-error --max-time 5 "$HEALTH_URL" \
  | jq -c --arg twall "$(date -u -Iseconds)" --argjson tmono "$T_MONO_DELTA" '...projection...' \
  >> "$CAPTURE_DIR/soak-capture.ndjson"; then
  :
else
  printf '{"t_wall":"%s","capture_error":true}\n' "$(date -u -Iseconds)" >> "$CAPTURE_DIR/soak-capture.ndjson"
fi
```

Alternatively, log the error to stderr and skip the row, but avoid terminating the whole soak unless that is an intentional operator contract documented in `docs/SOAK_HARNESS.md`.

## Residual Risks and Coverage

- The checked-in golden summary provides deterministic drift detection, and replay tests assert key edge behaviors independently of the golden file.
- v1.42 reference replay is skipped if historical planning fixtures are absent; in this repository state it ran as part of the reported 22-test slice.
- Phase 203 remains harness-only: no committed `src/wanctl/**` diff was observed versus `b72b463`.
- Review did not identify security issues, hardcoded production endpoints, command injection, or control-path behavior changes in the changed files.

---

_Reviewed: 2026-05-06T23:03:34Z_  
_Reviewer: the agent (gsd-code-reviewer)_  
_Depth: standard_
