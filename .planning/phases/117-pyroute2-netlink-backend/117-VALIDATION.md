---
phase: 117
slug: pyroute2-netlink-backend
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-27
---

# Phase 117 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x |
| **Config file** | `pyproject.toml` |
| **Quick run command** | `.venv/bin/pytest tests/test_netlink_cake_backend.py -v` |
| **Full suite command** | `.venv/bin/pytest tests/ -v` |
| **Estimated runtime** | ~30 seconds (full suite) |

---

## Sampling Rate

- **After every task commit:** Run `.venv/bin/pytest tests/test_netlink_cake_backend.py -v`
- **After every plan wave:** Run `.venv/bin/pytest tests/ -v`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 117-01-01 | 01 | 1 | NLNK-01 | unit | `.venv/bin/pytest tests/test_netlink_cake_backend.py -v` | ❌ W0 | ⬜ pending |
| 117-01-02 | 01 | 1 | NLNK-02 | unit | `.venv/bin/pytest tests/test_netlink_cake_backend.py -v` | ❌ W0 | ⬜ pending |
| 117-01-03 | 01 | 1 | NLNK-03 | unit | `.venv/bin/pytest tests/test_netlink_cake_backend.py -v` | ❌ W0 | ⬜ pending |
| 117-02-01 | 02 | 1 | NLNK-04 | unit | `.venv/bin/pytest tests/test_netlink_cake_backend.py -v` | ❌ W0 | ⬜ pending |
| 117-02-02 | 02 | 1 | NLNK-05 | unit | `.venv/bin/pytest tests/test_netlink_cake_backend.py -v` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_netlink_cake_backend.py` — stubs for NLNK-01..05
- [ ] Mock fixtures for pyroute2 IPRoute (no real netlink socket in unit tests)

*Existing test infrastructure (conftest, fixtures, pytest config) covers general needs.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Netlink bandwidth change produces identical CAKE state | NLNK-01 | Requires real CAKE qdisc on VM | PoC script on cake-shaper VM: change bandwidth via netlink, readback via `tc -j qdisc show` |
| IPRoute reconnect on socket death | NLNK-02 | Requires killing netlink socket | On VM: start daemon, kill IPRoute fd via lsof, verify reconnect in logs |
| Per-tin stats match tc -j output | NLNK-04 | Requires real CAKE stats | On VM: compare netlink stats dict vs subprocess tc -j output field-by-field |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
