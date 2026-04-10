---
phase: 162
slug: baseline-measurement
status: draft
nyquist_compliant: true
wave_0_complete: true
created: 2026-04-09
---

# Phase 162 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x |
| **Config file** | pyproject.toml |
| **Quick run command** | `.venv/bin/pytest tests/ -x -q --tb=short` |
| **Full suite command** | `.venv/bin/pytest tests/ -v` |
| **Estimated runtime** | ~45 seconds |

---

## Sampling Rate

- **After every task commit:** Run `.venv/bin/pytest tests/ -x -q --tb=short`
- **After every plan wave:** Run `.venv/bin/pytest tests/ -v`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 45 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 162-01-01 | 01 | 1 | VALID-02 | — | N/A | integration | `.venv/bin/pytest tests/ -k cake_signal -v` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

*Existing infrastructure covers all phase requirements.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Health endpoint reports drop_rate and backlog_bytes at idle | VALID-02 | Requires live CAKE qdiscs on production | `curl -s http://10.10.110.223:9101/health \| python3 -m json.tool` — verify cake_signal fields present |
| Baseline values recorded after 24h | VALID-02 | Requires 24h soak on production | `wanctl-history --summary` — verify mean/p50/p99 for drop_rate and backlog_bytes |
| No detection state changes at idle | VALID-02 | Requires idle production traffic | Check `dwell_bypassed_count` and `backlog_suppressed_count` remain 0 during idle window |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 45s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
