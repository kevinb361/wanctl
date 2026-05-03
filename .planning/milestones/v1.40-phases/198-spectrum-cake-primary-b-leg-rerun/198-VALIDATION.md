---
phase: 198
slug: spectrum-cake-primary-b-leg-rerun
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-27
---

# Phase 198 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x (Python 3.11+) for any predicate-on-rows checks; bash + jq for artifact integrity |
| **Config file** | `pyproject.toml` (existing) |
| **Quick run command** | `.venv/bin/pytest -o addopts='' tests/test_cake_signal.py tests/test_queue_controller.py tests/test_wan_controller.py tests/test_health_check.py -q` |
| **Full suite command** | `.venv/bin/pytest tests/ -v` |
| **Estimated runtime** | quick ~10s, full ~60s |

Phase 198 is operator procedure, not source code change. Most validation is artifact-based (presence, schema, predicate output) rather than test-suite. Source-tree diff (SAFE-05) and audit predicate output are the load-bearing checks.

---

## Sampling Rate

- **After every task commit:** Run quick test slice (no source code changes expected, but guards against accidental drift).
- **After every plan wave:** Run full suite if any `.py` file under `src/wanctl/` was touched (should be zero).
- **Before `/gsd-verify-work`:** Full suite green AND all artifact predicates pass.
- **Max feedback latency:** 60s for tests; soak window itself is ≥24h (out-of-band).

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 198-01-01 | 01 | 1 | SAFE-05 | T-198-01 | Phase 197 ship commit pinned, source bind verified, no concurrent experiment | artifact | `jq -e '.deployed_commit and .source_bind_verified == true' .planning/phases/198-*/soak/cake-primary/preflight.json` | ❌ W0 | ⬜ pending |
| 198-01-02 | 01 | 1 | SAFE-05 | T-198-02 | `/health` payload contains `signal_arbitration.refractory_active` field (proves Phase 197 code) | artifact | `jq -e '.signal_arbitration.refractory_active != null' .planning/phases/198-*/soak/cake-primary/health-preflight.json` | ❌ W0 | ⬜ pending |
| 198-02-01 | 02 | 2 | VALN-04 | — | ≥24h soak captured with raw rows, /health, journal | artifact | `test $(sqlite3 .planning/phases/198-*/soak/cake-primary/wanctl.sqlite "SELECT COUNT(*) FROM metrics WHERE granularity='raw'") -ge 1000000` | ❌ W0 | ⬜ pending |
| 198-02-02 | 02 | 2 | VALN-04 | — | Audit predicate run on raw rows; refractory_fallback bucket separated | artifact | `jq -e '.accept_list_pass == true and .rtt_fallback_during_refractory_count >= 0' .planning/phases/198-*/soak/cake-primary/primary-signal-audit-phase197.json` | ❌ W0 | ⬜ pending |
| 198-03-01 | 03 | 3 | VALN-05a | — | Three corrected source-bound flent tcp_12down 30s runs captured | artifact | `test $(ls .planning/phases/198-*/soak/cake-primary/flent/*.flent.gz \| wc -l) -ge 3` | ❌ W0 | ⬜ pending |
| 198-03-02 | 03 | 3 | VALN-05a | — | 2-of-3 individual medians ≥532 Mbps AND median-of-medians ≥532 Mbps | artifact | `jq -e '.verdict == "PASS"' .planning/phases/198-*/soak/cake-primary/flent/throughput-verdict.json` | ❌ W0 | ⬜ pending |
| 198-03-03 | 03 | 3 | VALN-05a | — | Source bind verified pre-run via `curl --interface 10.10.110.226` | artifact | `jq -e '.egress_ip_matches == true' .planning/phases/198-*/soak/cake-primary/source-bind-egress-proof.json` | ❌ W0 | ⬜ pending |
| 198-04-01 | 04 | 4 | VALN-04 | — | `ab-comparison.json` produced with all 6 deltas | artifact | `jq -e '.deltas \| has("rtt_distress_events") and has("burst_triggers") and has("dwell_bypass_responsiveness") and has("fusion_state_transitions") and has("queue_primary_coverage") and has("refractory_fallback_rate")' .planning/phases/198-*/ab-comparison.json` | ❌ W0 | ⬜ pending |
| 198-04-02 | 04 | 4 | SAFE-05 | T-198-03 | SAFE-05 source-tree diff captured (zero diffs in protected paths between Phase 197 ship and Phase 198 close) | artifact | `jq -e '.protected_path_diffs == 0' .planning/phases/198-*/safe05-diff.json` | ❌ W0 | ⬜ pending |
| 198-04-03 | 04 | 4 | VALN-04, VALN-05a | — | 196-VERIFICATION.md and 198-VERIFICATION.md updated | grep | `grep -q 'VALN-04.*\(closed\|✅\)' .planning/phases/196-*/196-VERIFICATION.md && grep -q 'VALN-05a.*\(closed\|✅\)' .planning/phases/198-*/198-VERIFICATION.md` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `.planning/phases/198-spectrum-cake-primary-b-leg-rerun/soak/cake-primary/` — capture directory tree (created by capture script, mirrors Phase 196 layout)
- [ ] No new pytest fixtures expected (no source code changes)
- [ ] If a thin `scripts/phase198-flent-3run.sh` wrapper is added (planner discretion), `tests/test_phase198_flent_wrapper.py` should exist with shellcheck + dry-run smoke test

*If wrapper not added: "Existing infrastructure (`phase191-flent-capture.sh`, `phase196-soak-capture.sh`) covers all phase requirements."*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Soak window ≥24h elapsed wall-clock | VALN-04 | Real-time clock dependency, cannot be simulated | Confirm `(soak_end - soak_start) >= 86400` seconds in capture metadata |
| No concurrent Spectrum experiment scheduled | SAFE-05 | Operator coordination check | Operator confirms in preflight.json `concurrent_experiment_check: clear` |
| flent runs occur during loaded portion of soak window | VALN-05a | Operator times the runs | Each `*.flent.gz` start timestamp falls within the soak window's loaded interval |

---

## Validation Sign-Off

- [ ] All tasks have artifact-based or grep-based automated verify
- [ ] Sampling continuity: artifact predicates run after each plan completes (4 plans, 4 verify gates)
- [ ] Wave 0 covers MISSING references (capture directory creation)
- [ ] No watch-mode flags
- [ ] Feedback latency < 60s for predicates; soak runtime out-of-band by design
- [ ] `nyquist_compliant: true` set in frontmatter after sign-off

**Approval:** pending
