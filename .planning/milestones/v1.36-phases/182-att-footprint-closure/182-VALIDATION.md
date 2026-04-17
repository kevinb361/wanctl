---
phase: 182
slug: att-footprint-closure
status: draft
nyquist_compliant: true
wave_0_complete: true
created: 2026-04-14
---

# Phase 182 - Validation Strategy

> Per-phase validation contract for closing the final ATT-side production footprint gap.

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | `pytest`, `bash -n`, `rg`, `git diff --check`, read-only production checks |
| **Quick run command** | `.venv/bin/pytest -o addopts='' tests/storage/test_storage_maintenance.py tests/test_health_check.py tests/test_history_multi_db.py tests/test_history_cli.py -q` |
| **Estimated runtime** | 1-3 minutes repo-side, plus live ATT reduction and read-only verification |

## Sampling Rate

- After every repo-side task: run the narrowest relevant tests.
- After every plan wave: run `git diff --check`.
- Before closing the phase: rerun the focused repo tests plus live production footprint and operator checks.

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 182-01-01 | 01 | 1 | STOR-06 | T-182-01 | ATT non-reduction cause is identified from production evidence rather than guessed | artifact+read-only | `test -f .planning/phases/182-att-footprint-closure/182-att-reduction-precheck.md && rg -n 'ATT|Spectrum|baseline|compact|stat' .planning/phases/182-att-footprint-closure/182-att-reduction-precheck.md` | ✅ | ⬜ pending |
| 182-02-01 | 02 | 2 | STOR-06 | T-182-02 | any repo-side helper changes stay inside storage/operator surfaces | repo test | `.venv/bin/pytest -o addopts='' tests/storage/test_storage_maintenance.py tests/test_health_check.py tests/test_history_multi_db.py tests/test_history_cli.py -q` | ✅ | ⬜ pending |
| 182-02-02 | 02 | 2 | STOR-06 | T-182-03 | ATT reduction does not break operator surfaces | syntax+live | `bash -n scripts/compact-metrics-dbs.sh scripts/soak-monitor.sh scripts/canary-check.sh && ./scripts/canary-check.sh --ssh kevin@10.10.110.223 --expect-version 1.35.0 --json` | ✅ | ⬜ pending |
| 182-03-01 | 03 | 3 | STOR-06 | T-182-04 | final closure is based on direct baseline comparison for both active per-WAN DBs | live read-only | `ssh -o BatchMode=yes kevin@10.10.110.223 'sudo -n stat -c \"%n %s %y\" /var/lib/wanctl/metrics-spectrum.db /var/lib/wanctl/metrics-spectrum.db-wal /var/lib/wanctl/metrics-att.db /var/lib/wanctl/metrics-att.db-wal /var/lib/wanctl/metrics.db /var/lib/wanctl/metrics.db-wal 2>/dev/null'` | ✅ | ⬜ pending |
| 182-03-02 | 03 | 3 | STOR-06 | T-182-05 | final operator proof path still works after the ATT reduction | live read-only | `./scripts/soak-monitor.sh --ssh kevin@10.10.110.223 --json && ./scripts/canary-check.sh --ssh kevin@10.10.110.223 --expect-version 1.35.0 --json && ssh -o BatchMode=yes kevin@10.10.110.223 'sudo -n env PYTHONPATH=/opt python3 -m wanctl.history --last 1h --metrics wanctl_rtt_ms --json'` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠ flaky*

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Decide whether the ATT delta is materially smaller enough to close `STOR-06` | STOR-06 | Requires judgment against the fixed baseline and the reduction path actually run | Read the final closeout report and compare ATT and Spectrum to the `2026-04-13` baseline |
| Confirm docs match the supported operator story after the ATT reduction | STOR-06 | Requires human review of CLI vs endpoint-local HTTP wording | Compare the final docs and reports to the live commands captured in the phase artifacts |

## Validation Sign-Off

- [x] All tasks have `<automated>` verification or Wave 0 coverage
- [x] Sampling continuity preserved
- [x] Wave 0 covers live production verification
- [x] No watch-mode flags
- [x] `nyquist_compliant: true` set in frontmatter
