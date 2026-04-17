---
phase: 181
slug: production-footprint-reduction-and-reader-parity
status: draft
nyquist_compliant: true
wave_0_complete: true
created: 2026-04-14
---

# Phase 181 — Validation Strategy

> Per-phase validation contract for real production footprint reduction and history-reader parity closure.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | `pytest`, `bash -n`, `rg`, `git diff --check`, read-only production checks |
| **Config file** | current shipped configs and operator docs |
| **Quick run command** | `.venv/bin/pytest -o addopts='' tests/storage/test_storage_maintenance.py tests/test_health_check.py tests/test_history_multi_db.py tests/test_history_cli.py -q` |
| **Full suite command** | add targeted tests for any newly touched storage/reader modules |
| **Estimated runtime** | 1-3 minutes repo-side, plus live production checks |

---

## Sampling Rate

- **After every task commit:** run the task-local focused validation listed in the plan.
- **After every plan wave:** run `git diff --check`.
- **Before closing the phase:** rerun the focused repo tests plus the read-only production footprint/reader checks.
- **Max feedback latency:** 5 minutes

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 181-01-01 | 01 | 1 | STOR-06 | T-181-01 | footprint-reduction path changes storage behavior without touching control logic | repo test | `.venv/bin/pytest -o addopts='' tests/storage/test_storage_maintenance.py tests/test_health_check.py -q` | ✅ | ⬜ pending |
| 181-01-02 | 01 | 1 | STOR-06 | T-181-02 | operator/deploy surface documents the real reduction path and preserves safety boundaries | syntax+artifact | `bash -n scripts/soak-monitor.sh scripts/canary-check.sh 2>/dev/null || true; rg -n 'metrics-spectrum\\.db|metrics-att\\.db|vacuum|compact|retention|storage' docs scripts` | ✅ | ⬜ pending |
| 181-02-01 | 02 | 2 | STOR-06 | T-181-03 | HTTP and CLI history readers are either aligned or their narrowed roles are explicit and tested | repo test | `.venv/bin/pytest -o addopts='' tests/test_health_check.py tests/test_history_multi_db.py tests/test_history_cli.py -q` | ✅ | ⬜ pending |
| 181-02-02 | 02 | 2 | STOR-06 | T-181-04 | reader parity changes preserve the HTTP response envelope and newest-first ordering | repo test | `.venv/bin/pytest -o addopts='' tests/test_health_check.py tests/test_history_multi_db.py -q` | ✅ | ⬜ pending |
| 181-03-01 | 03 | 3 | STOR-06 | T-181-05 | production size evidence is measured against the fixed 2026-04-13 baseline rather than guessed | live read-only | `ssh -o BatchMode=yes kevin@10.10.110.223 'sudo -n stat -c \"%n %s %y\" /var/lib/wanctl/metrics-spectrum.db /var/lib/wanctl/metrics-spectrum.db-wal /var/lib/wanctl/metrics-att.db /var/lib/wanctl/metrics-att.db-wal /var/lib/wanctl/metrics.db /var/lib/wanctl/metrics.db-wal 2>/dev/null'` | ✅ | ⬜ pending |
| 181-03-02 | 03 | 3 | STOR-06 | T-181-06 | supported operator surfaces still work after the reduction step | live read-only | `./scripts/soak-monitor.sh --json && ./scripts/canary-check.sh --ssh kevin@10.10.110.223 --expect-version 1.35.0 --json` | ✅ | ⬜ pending |
| 181-03-03 | 03 | 3 | STOR-06 | T-181-07 | live history proof path is internally consistent enough for operators | live read-only | `ssh -o BatchMode=yes kevin@10.10.110.223 'sudo -n env PYTHONPATH=/opt python3 -m wanctl.history --last 1h --metrics wanctl_rtt_ms --json'` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

Existing repo test infrastructure is sufficient for reader/storage logic.

Production verification is intentionally read-only and uses the same operator-safe commands already established in Phase 179.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Decide whether the post-change production size delta is "material" enough to close the milestone claim | STOR-06 | Requires judgment against the fixed baseline and the actual reduction mechanism shipped | Read the final footprint report and compare deltas to the 2026-04-13 baseline values |
| Confirm the documented operator story is honest if HTTP and CLI roles remain non-identical | STOR-06 | Requires human judgment about operator semantics, not just code/tests | Compare the final docs against the live CLI and HTTP evidence captured in the phase artifacts |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verification or Wave 0 coverage
- [x] Sampling continuity: no 3 consecutive tasks without automated verification
- [x] Wave 0 covers the live-read-only verification path
- [x] No watch-mode flags
- [x] Feedback latency < 5 minutes
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved 2026-04-14
