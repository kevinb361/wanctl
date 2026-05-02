---
phase: 198-spectrum-cake-primary-b-leg-rerun
reviewed: 2026-05-02T00:00:00Z
depth: standard
files_reviewed: 3
files_reviewed_list:
  - scripts/phase198-rerun-flent-3run.sh
  - scripts/phase198-loaded-window-audit.py
  - scripts/phase198-throughput-verdict.py
findings:
  critical: 1
  warning: 2
  info: 0
  total: 3
status: issues_found
---

# Phase 198: Code Review Report

**Reviewed:** 2026-05-02T00:00:00Z
**Depth:** standard
**Files Reviewed:** 3
**Status:** issues_found

## Summary

Reviewed the Phase 198 source/script changes: the off-peak rerun harness, loaded-window audit tool, and throughput verdict tool. The throughput verdict script is straightforward and did not show actionable issues. The harness and audit script have three actionable risks: one remote command-injection exposure in the SQLite SSH command, one false-pass audit predicate edge case, and one failure-summary contract gap that can make failed off-peak attempts harder to recover.

## Critical Issues

### CR-01: Remote SQLite path is interpolated into an SSH shell command

**File:** `scripts/phase198-rerun-flent-3run.sh:325-327`

**Issue:** `REMOTE_DB` comes from `--remote-db` / environment and is embedded inside a single-quoted remote shell command. A value containing a single quote can break out of the quoted filename and execute additional commands on the remote host under the operator's SSH account / `sudo -n sqlite3` context. Even though this is an operator harness, it is still a command-injection boundary in a production network validation script.

**Fix:** Quote the remote database path for the remote shell before constructing the SSH command, or pass it as a safely escaped argument. For example:

```bash
REMOTE_DB_Q=$(printf '%q' "${REMOTE_DB}")
ssh -o BatchMode=yes ${REMOTE_USER:+"${REMOTE_USER}@"}"${REMOTE_HOST}" \
    "command -v sqlite3 >/dev/null && sudo -n sqlite3 -readonly -header -separator '|' ${REMOTE_DB_Q}" \
    >"${PSV_FILE}" <<SQL
```

Also add a dry-run or unit-style shell test with a database path containing a single quote to verify the command is not split or executed as shell syntax.

## Warnings

### WR-01: Loaded-window audit can pass with non-queue health samples

**File:** `scripts/phase198-loaded-window-audit.py:186-188`

**Issue:** `health_non_queue` only counts samples where `queue_primary_active` is false **and** `refractory_active` is true. The Phase 198 gate requires `health_non_queue == 0`, but with the current logic a 30-sample window containing one non-queue/non-refractory sample would still report `health_non_queue: 0`, `queue_primary_health_pct: 96.67`, and `verdict: pass`. That can falsely promote a loaded window that was not continuously queue-primary.

**Fix:** Count all non-queue health samples for the gate, and optionally keep the refractory-specific count as a separate diagnostic field:

```python
health_non_queue = sum(not r["queue_primary_active"] for r in health_rows)
health_non_queue_during_refractory = sum(
    (not r["queue_primary_active"]) and r["refractory_active"]
    for r in health_rows
)
```

Add a regression fixture with 29 queue samples and 1 RTT/non-refractory sample; it should fail because `health_non_queue != 0`.

### WR-02: Health preflight failures do not write the contracted attempt summary

**File:** `scripts/phase198-rerun-flent-3run.sh:190-203,205-227`

**Issue:** The harness performs the `/health` preflight before creating `ATTEMPT_DIR` and before installing the `ERR` trap. If the health endpoint is unreachable or returns no Spectrum WAN, the script exits without `rerun-attempt-N/attempt-summary.json`. That violates the Plan 198-05/06 partial-failure contract for post-gate failures and can leave Plan 198-06 without a machine-readable failed attempt record after an off-peak window was consumed.

**Fix:** Create the attempt directory and install the partial-summary trap before any post-gate network preflight, or explicitly write a summary on health-preflight refusal:

```bash
REF="$(git rev-parse --short HEAD)"
ATTEMPT_DIR="${ATTEMPT_DIR_PREFIX}${N}"
mkdir -p "${ATTEMPT_DIR}/flent" "${OUTPUT_ROOT}"
trap 'write_partial_summary' ERR

ATTEMPT_FAILED_STAGE="health_preflight"
HEALTH_PROBE="$(curl -fsS -m 2 "${HEALTH_URL}" 2>&1)" || exit 5
```

Then verify that an unreachable `--health-url` produces `attempt-summary.json` with `failed: true`, `failure_stage: "health_preflight"`, and `decision: null`.

---

_Reviewed: 2026-05-02T00:00:00Z_
_Reviewer: the agent (gsd-code-reviewer)_
_Depth: standard_
