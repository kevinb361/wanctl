---
phase: 231
slug: migration-held-criteria-rollback-verification-doc-sweep
status: draft
nyquist_compliant: true
wave_0_complete: false
created: 2026-06-10
---

# Phase 231 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (project `.venv`), shellcheck |
| **Config file** | `pyproject.toml` |
| **Quick run command** | `.venv/bin/pytest tests/test_phase231_migration_held.py tests/test_phase231_rollback.py -q` |
| **Full suite command** | `.venv/bin/pytest tests/ -q` |
| **Estimated runtime** | quick ~2s; full ~240s (21 pre-existing Phase 220/221 boundary failures expected — classified, unrelated) |

---

## Sampling Rate

- **After every task commit:** Run the quick run command plus `shellcheck -S error` on any touched script
- **After every plan wave:** Run the hot-path regression slice: `.venv/bin/pytest -o addopts='' tests/test_cake_signal.py tests/test_queue_controller.py tests/test_wan_controller.py tests/test_health_check.py -q`
- **Before `/gsd:verify-work`:** Quick command green; full suite shows only the 21 classified pre-existing failures
- **Max feedback latency:** 300 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 231-01-01 | 01 | 1 | SOAK-01 | T-231-01 | evaluator builds only read-only remote commands | unit | `.venv/bin/pytest tests/test_phase231_migration_held.py -q` | ❌ W0 | ⬜ pending |
| 231-01-02 | 01 | 1 | SOAK-01 | T-231-01 | live evidence capture is read-only (no systemctl mutation, no tc replace) | manual+grep | grep assertions on `231-SOAK01-EVIDENCE.md` | ❌ W0 | ⬜ pending |
| 231-02-01 | 02 | 1 | SOAK-02 | T-231-02 | rollback script refuses mutation without `--confirm` | unit | `.venv/bin/pytest tests/test_phase231_rollback.py -q` | ❌ W0 | ⬜ pending |
| 231-02-02 | 02 | 1 | SOAK-02 | T-231-02 | preflight is read-only; evidence captured | manual+grep | grep assertions on `231-SOAK02-EVIDENCE.md` | ❌ W0 | ⬜ pending |
| 231-03-01 | 03 | 2 | DOCS-04 | — | no secrets/private IPs added to docs prose | grep | grep sweep assertions on README/docs | ✅ | ⬜ pending |
| 231-03-02 | 03 | 2 | SAFE-14 | T-231-03 | controller-path zero-diff vs SAFE_BASE | cli | `test -z "$(git diff --stat 87980bdf -- src/wanctl/wan_controller.py src/wanctl/wan_controller_state.py src/wanctl/queue_controller.py src/wanctl/cake_signal.py src/wanctl/alert_engine.py src/wanctl/fusion_healer.py src/wanctl/backends/)"` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_phase231_migration_held.py` — stubs for SOAK-01 evaluator assertions
- [ ] `tests/test_phase231_rollback.py` — stubs for SOAK-02 `--confirm` gating assertions

*Existing pytest infrastructure covers everything else; no framework install needed.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Live both-WAN migration-held evidence | SOAK-01 | Requires live SSH/curl against production cake-shaper | Run `scripts/phase231-migration-held.sh` read-only; verify per-WAN PASS JSON; commit evidence |
| Optional live rollback exercise | SOAK-02 | Production mutation — operator approval required | Checkpoint task; only with explicit operator GO; otherwise provable path stands |
| Doc readability of both deployment modes | DOCS-04 | Prose quality judgment | Operator skim of swept docs at verify-work |
