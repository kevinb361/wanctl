---
phase: 229
slug: att-deploy-path-artifact-tests
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-06-09
---

# Phase 229 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (existing project infrastructure) |
| **Config file** | pyproject.toml |
| **Quick run command** | `.venv/bin/pytest tests/test_att_cake_autorate_artifacts.py tests/test_spectrum_cake_autorate_artifacts.py -q` |
| **Full suite command** | `.venv/bin/pytest -o addopts='' tests/test_cake_signal.py tests/test_queue_controller.py tests/test_wan_controller.py tests/test_health_check.py -q` (hot-path slice) plus phase tests |
| **Estimated runtime** | ~30 seconds (phase tests), ~120 seconds (hot-path slice) |

---

## Sampling Rate

- **After every task commit:** Run quick command (phase artifact tests)
- **After every plan wave:** Run quick command + hot-path regression slice
- **Before `/gsd:verify-work`:** Full phase test set + hot-path slice green; SAFE-14 git-diff gate clean
- **Max feedback latency:** 120 seconds

---

## Per-Task Verification Map

To be filled by planner. Mapping skeleton from RESEARCH.md Validation Architecture:

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| TBD | TBD | TBD | DEPLOY-01 | — | deploy.sh ATT path mirrors Spectrum rigor; `bash -n` clean; usage lists flag | integration | `bash -n scripts/deploy.sh && grep -q -- '--with-att-cake-autorate' scripts/deploy.sh` | ✅ | ⬜ pending |
| TBD | TBD | TBD | DEPLOY-02 | — | read-only live-vs-repo sha256 diff captured (phase226-snapshot-a.sh precedent) | manual+evidence | read-only ssh `sudo -n cat \| sha256sum` comparison script | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | TEST-01 | — | ATT artifact tests at parity with Spectrum's | unit | `.venv/bin/pytest tests/test_att_cake_autorate_artifacts.py -q` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | TEST-02 | — | deploy.sh ATT file list ⇔ repo artifacts bidirectional set-equality | unit | `.venv/bin/pytest tests/test_att_cake_autorate_artifacts.py -q -k deploy_list` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | SAFE-14 | — | controller-path zero-diff at phase boundary | gate | `git diff --stat <boundary>.. -- src/wanctl/wan_controller.py src/wanctl/queue_controller.py src/wanctl/cake_signal.py src/wanctl/linux_cake.py src/wanctl/netlink_cake.py src/wanctl/alert_engine.py` (empty output) | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_att_cake_autorate_artifacts.py` — stubs for TEST-01/TEST-02 assertions
- [ ] Read-only DEPLOY-02 diff evidence script/procedure (phase precedent: `scripts/phase226-snapshot-a.sh`)

*Existing pytest infrastructure covers framework needs — no installs.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Live-vs-repo artifact diff on cake-shaper | DEPLOY-02 | Requires read-only SSH to production host; cannot run in CI | Run read-only diff script; capture sha256 table as phase evidence; repo is source of truth — report any drift honestly |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 120s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
