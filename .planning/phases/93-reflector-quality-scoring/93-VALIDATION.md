---
phase: 93
slug: reflector-quality-scoring
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-17
---

# Phase 93 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x |
| **Config file** | pyproject.toml |
| **Quick run command** | `.venv/bin/pytest tests/test_reflector_quality.py -v` |
| **Full suite command** | `.venv/bin/pytest tests/ -v` |
| **Estimated runtime** | ~30 seconds |

---

## Sampling Rate

- **After every task commit:** Run `.venv/bin/pytest tests/test_reflector_quality.py -v`
- **After every plan wave:** Run `.venv/bin/pytest tests/ -v`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 93-01-01 | 01 | 1 | REFL-01 | unit | `.venv/bin/pytest tests/test_reflector_quality.py -k "score"` | ❌ W0 | ⬜ pending |
| 93-01-02 | 01 | 1 | REFL-02 | unit | `.venv/bin/pytest tests/test_reflector_quality.py -k "deprioritize"` | ❌ W0 | ⬜ pending |
| 93-01-03 | 01 | 1 | REFL-03 | unit | `.venv/bin/pytest tests/test_reflector_quality.py -k "recovery"` | ❌ W0 | ⬜ pending |
| 93-02-01 | 02 | 2 | REFL-04 | unit | `.venv/bin/pytest tests/test_reflector_quality.py -k "health"` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_reflector_quality.py` — stubs for REFL-01 through REFL-04
- [ ] Shared fixtures for ReflectorScorer instantiation and mock ping results

*Existing pytest infrastructure and conftest.py patterns cover framework needs.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Health endpoint reflector_quality section | REFL-04 | Full HTTP response structure | `curl -s http://127.0.0.1:9101/health \| python3 -m json.tool \| grep reflector_quality` |

*Unit tests verify the data structure; manual check confirms HTTP integration.*

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
