---
phase: 173
slug: clean-deploy-canary-validation
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-12
---

# Phase 173 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x (existing) + bash scripts |
| **Config file** | pyproject.toml |
| **Quick run command** | `.venv/bin/pytest -o addopts='' tests/test_health_check.py -q` |
| **Full suite command** | `.venv/bin/pytest tests/ -v` |
| **Estimated runtime** | ~45 seconds |

---

## Sampling Rate

- **After every task commit:** Run `.venv/bin/pytest -o addopts='' tests/test_health_check.py -q`
- **After every plan wave:** Run `.venv/bin/pytest tests/ -v`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 45 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 173-01-01 | 01 | 1 | DEPL-01 | — | N/A | unit | `grep -q '__version__ = "1.35.0"' src/wanctl/__init__.py` | ✅ | ⬜ pending |
| 173-01-02 | 01 | 1 | DEPL-01 | — | N/A | manual | `scripts/deploy.sh --dry-run` | ✅ | ⬜ pending |
| 173-01-03 | 01 | 1 | DEPL-01 | — | N/A | manual | `scripts/canary-check.sh --expect-version 1.35.0` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

Existing infrastructure covers all phase requirements. No new test files needed — validation is via deployment scripts and version string grep.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| deploy.sh completes on production | DEPL-01 | Requires SSH to cake-shaper VM | Run `./scripts/deploy.sh spectrum kevin@10.10.110.223` and verify exit 0 |
| canary-check.sh exit 0 | DEPL-01 | Requires live health endpoints | Run `./scripts/canary-check.sh --ssh kevin@10.10.110.223 --expect-version 1.35.0` |
| Per-WAN DB files created | DEPL-01 | Requires production service restart | SSH and verify metrics-spectrum.db, metrics-att.db exist in /var/lib/wanctl/ |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 45s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
