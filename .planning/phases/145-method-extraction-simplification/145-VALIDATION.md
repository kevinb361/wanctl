---
phase: 145
slug: method-extraction-simplification
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-06
---

# Phase 145 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x |
| **Config file** | pyproject.toml |
| **Quick run command** | `.venv/bin/pytest tests/ -x --tb=short -q` |
| **Full suite command** | `make ci` |
| **Estimated runtime** | ~630 seconds |

---

## Sampling Rate

- **After every task commit:** Run `.venv/bin/pytest tests/ -x --tb=short -q`
- **After every plan:** Run `make ci` (ruff + mypy + pytest)
- **After final plan:** Run `make ci && make dead-code`

---

## Validation Architecture

### Wave 0 — Baseline (pre-execution)

| Check | Command | Expected |
|-------|---------|----------|
| All tests pass | `.venv/bin/pytest tests/ -x --tb=short -q` | 4,178+ passed |
| Ruff clean | `.venv/bin/ruff check src/wanctl/` | 0 violations |
| MyPy clean | `.venv/bin/mypy src/wanctl/` | Success |

### Per-Task Validation

| Check | Command | Expected |
|-------|---------|----------|
| No regressions | `.venv/bin/pytest tests/ -x --tb=short -q` | Same pass count |
| No lint violations | `.venv/bin/ruff check src/wanctl/` | 0 violations |
| Import integrity | `python -c "from wanctl.{module} import {function}"` | No ImportError |

### Per-Plan Validation

| Check | Command | Expected |
|-------|---------|----------|
| Full CI | `make ci` | Exit 0 |
| Dead code | `make dead-code` | Exit 0 |
| C901 at threshold 15 | `.venv/bin/ruff check src/wanctl/ --select C901` | 0 violations |

### Phase Gate — Final Validation

| Check | Command | Expected |
|-------|---------|----------|
| No function >50 lines | AST analysis script | 0 violations |
| C901 ≤ 15 | `.venv/bin/ruff check src/wanctl/ --select C901` | 0 violations |
| All tests pass | `.venv/bin/pytest tests/ -x --tb=short -q` | 4,178+ passed |
| All helpers named | grep for docstrings on new functions | All present |
