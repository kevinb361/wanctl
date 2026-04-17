---
phase: 178
slug: retention-tightening-and-legacy-db-cleanup
status: draft
nyquist_compliant: true
wave_0_complete: true
created: 2026-04-13
---

# Phase 178 — Validation Strategy

> Per-phase validation contract for storage-topology closure and conservative footprint reduction.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | `pytest`, `rg`, `git diff --check`, optional shell syntax checks for touched scripts |
| **Config file** | `configs/spectrum.yaml`, `configs/att.yaml`, `configs/steering.yaml` |
| **Quick run command** | `.venv/bin/pytest -o addopts='' <targeted tests> -q` |
| **Full suite command** | none required unless execution expands beyond storage/history surfaces |
| **Estimated runtime** | under 60 seconds for the targeted slice |

---

## Sampling Rate

- **After every task commit:** run the task-local targeted pytest or grep listed in the plan.
- **After every plan wave:** run `git diff --check` plus the phase-level targeted regression slice.
- **Before `/gsd-verify-work`:** confirm storage topology, retention config, and operator/history surfaces all match the intended runtime layout.
- **Max feedback latency:** 60 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 178-01-01 | 01 | 1 | STOR-05 | T-178-01 | steering and storage defaults describe the shared legacy DB role explicitly instead of implicitly | targeted pytest + grep | `.venv/bin/pytest -o addopts='' tests/test_config_base.py tests/steering/test_steering_metrics_recording.py -q && rg -n 'metrics\\.db|storage:' configs/steering.yaml src/wanctl/config_base.py src/wanctl/steering/daemon.py` | ✅ | ⬜ pending |
| 178-01-02 | 01 | 1 | STOR-05 | T-178-02 | only clearly stale zero-byte DB artifacts are removed or documented for cleanup | artifact + grep | `rg -n 'spectrum_metrics\\.db|att_metrics\\.db|metrics\\.db' .planning/phases/178-retention-tightening-and-legacy-db-cleanup` | ✅ | ⬜ pending |
| 178-02-01 | 02 | 2 | STOR-06 | T-178-03 | per-WAN retention is reduced without violating tuning-history safety | targeted pytest | `.venv/bin/pytest -o addopts='' tests/test_config_base.py tests/storage/test_storage_maintenance.py tests/tuning/test_tuning_history_reader.py -q` | ✅ | ⬜ pending |
| 178-02-02 | 02 | 2 | STOR-07 | T-178-04 | downsampling/cleanup configuration remains bounded and syntax-valid | grep + focused test | `rg -n 'raw_age_seconds|aggregate_1m_age_seconds|aggregate_5m_age_seconds|maintenance_interval_seconds' configs/spectrum.yaml configs/att.yaml src/wanctl/config_base.py docs/CONFIG_SCHEMA.md && .venv/bin/pytest -o addopts='' tests/test_check_config.py -q` | ✅ | ⬜ pending |
| 178-03-01 | 03 | 3 | STOR-06, STOR-07 | T-178-05 | `/metrics/history` and CLI/history reads follow the authoritative DB topology | targeted pytest | `.venv/bin/pytest -o addopts='' tests/test_health_check.py tests/test_history_multi_db.py tests/test_history_cli.py -q` | ✅ | ⬜ pending |
| 178-03-02 | 03 | 3 | STOR-06 | T-178-06 | operator docs/scripts remain aligned with the updated storage layout | grep + syntax | `rg -n 'metrics\\.db|metrics-spectrum\\.db|metrics-att\\.db|soak-monitor|wanctl-history|storage.status' docs scripts && bash -n scripts/soak-monitor.sh scripts/canary-check.sh` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

Existing infrastructure is sufficient.

No new harness is required before execution because the repo already has:

- config validation coverage
- storage maintenance tests
- history and health endpoint tests
- steering metrics tests

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Confirm the chosen `metrics.db` disposition matches the live production role and operator expectations | STOR-05 | Requires judgment about whether the path is being made explicit, retained, or retired safely | Read the final phase summary and confirm the shared DB role is no longer ambiguous |
| Confirm the retention change is conservative relative to the 2026-04-13 baseline and does not overreach into controller semantics | STOR-06, STOR-07 | Human review is needed to judge whether the storage reduction stays within the milestone’s non-goals | Compare the final retention values against the prior config and ensure only storage thresholds changed |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verification or Wave 0 coverage
- [x] Sampling continuity: no 3 consecutive tasks without automated verification
- [x] Wave 0 covers all storage/history/operator-surface dependencies
- [x] No watch-mode flags
- [x] Feedback latency < 60s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved 2026-04-13
