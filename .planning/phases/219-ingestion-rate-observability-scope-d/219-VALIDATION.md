---
phase: 219
slug: ingestion-rate-observability-scope-d
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-29
---

# Phase 219 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Generated from `219-RESEARCH.md` §"Validation Architecture (Nyquist)".

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (existing) |
| **Config file** | `pyproject.toml` + `tests/conftest.py` (existing) |
| **Quick run command** | `.venv/bin/pytest tests/test_history_ingestion_rate_bucketed.py tests/test_phase219_mutation_boundary.py -v` |
| **Full suite command** | `.venv/bin/pytest tests/ -q` |
| **Hot-path regression slice** | `.venv/bin/pytest -o addopts='' tests/test_cake_signal.py tests/test_queue_controller.py tests/test_wan_controller.py tests/test_health_check.py -q` |
| **Estimated runtime** | ~1s (quick) · ~30s (hot-path slice) · full suite per project standard |

---

## Sampling Rate

- **After every task commit:** Run quick run command (~1s feedback)
- **After every plan wave:** Run full suite + hot-path slice
- **Before `/gsd:verify-work`:** Full suite must be green AND mutation-boundary green
- **Phase gate (post-deploy):** Cycle-budget capture documented in phase SUMMARY (`cycle_total.avg_ms ≤ 3.0` / `p99_ms ≤ 7.5`)
- **Max feedback latency:** ~30s (hot-path slice for wave merge)

---

## Per-Requirement Verification Map

| Req ID | Behavior | Test Type | Automated Command | File Exists | Status |
|--------|----------|-----------|-------------------|-------------|--------|
| INGEST-01 | `--by-table` emits per-WAN × per-metric_name rows; per-metric read failure → null | unit | `pytest tests/test_history_ingestion_rate_bucketed.py::TestIngestionRateBucketed::test_by_table_emits_per_metric_row -x` | ❌ W0 | ⬜ pending |
| INGEST-02 | `--rolling=60,300,3600` emits one row set per window; default behavior unchanged | unit | `pytest tests/test_history_ingestion_rate_bucketed.py::TestIngestionRateBucketed::test_rolling_emits_one_row_per_window -x` | ❌ W0 | ⬜ pending |
| INGEST-03 | JSON has `schema_version: 1` + `_snapshot_unix` + `_snapshot_age_sec` on every row | unit | `pytest tests/test_history_ingestion_rate_bucketed.py::TestIngestionRateBucketed::test_schema_version_pinned -x` | ❌ W0 | ⬜ pending |
| INGEST-04 | `wanctl-operator-summary --digest` renders ingestion block; tolerates per-WAN read failure | unit | `pytest tests/test_history_ingestion_rate_bucketed.py::TestOperatorSummaryDigest -x` | ❌ W0 | ⬜ pending |
| INGEST-05 | `scripts/phase219-ingestion-digest.py` atomic write + count-based retention (288) | unit | `pytest tests/test_phase219_ingestion_digest.py -x` | ❌ W0 | ⬜ pending |
| SAFE-11 | Mutation-boundary pytest covers Phase 219 allowlist (controller paths forbidden) | unit | `pytest tests/test_phase219_mutation_boundary.py -x` | ❌ W0 | ⬜ pending |
| Success #5 | Post-deploy `cycle_total.avg_ms ≤ 3.0` and `p99_ms ≤ 7.5` (Phase 217 baseline) | manual-only | Operator runs `scripts/profiling_collector_json.py` per `docs/PROFILING.md`; captures ≥1h; verifies gates. Evidence path recorded in phase SUMMARY. | ✅ existing harness | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*
*Per-task rows will be appended by the planner during PLAN.md creation.*

---

## Wave 0 Requirements

- [ ] `tests/test_history_ingestion_rate_bucketed.py` — covers INGEST-01..04 (golden SQLite fixture, in-line test data)
- [ ] `tests/test_phase219_ingestion_digest.py` — covers INGEST-05 cron script (atomic write + retention behavior)
- [ ] `tests/test_phase219_mutation_boundary.py` — covers SAFE-11 (clone `tests/test_phase214_mutation_boundary.py` template, flip allowlist)
- [ ] `tests/fixtures/phase219/.gitkeep` — fixture directory placeholder (golden JSON literals stay inline in test files per CONTEXT.md observed-evidence rule)
- [ ] No framework install needed (pytest already in `pyproject.toml`)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Production cycle budget unchanged | Success #5 | Hot-path timing is observable only on production traffic over ≥1h capture window | Operator runs `scripts/profiling_collector_json.py` per `docs/PROFILING.md` runbook. Capture ≥1h post-deploy. Run `scripts/analyze_profiling.py` and verify `cycle_total.avg_ms ≤ 3.0` and `p99_ms ≤ 7.5`. Record evidence path in phase SUMMARY. |
| `/var/lib/wanctl/snapshots/ingestion/` write permission | INGEST-05 | Filesystem ownership / mode is deploy-environment-specific | After install + first cron tick, operator confirms snapshot files appear under `/var/lib/wanctl/snapshots/ingestion/` owned by `wanctl` user. |

---

## Validation Sign-Off

- [ ] All tasks have automated verify command or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING (❌) test files above
- [ ] No watch-mode flags (`-f`, `--watch`) anywhere in test commands
- [ ] Feedback latency < 30s for hot-path slice
- [ ] `nyquist_compliant: true` set in frontmatter (when all the above hold)

**Approval:** pending
