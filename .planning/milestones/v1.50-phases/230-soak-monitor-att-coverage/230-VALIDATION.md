---
phase: 230
slug: soak-monitor-att-coverage
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-06-09
---

# Phase 230 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (repo-pinned, pyproject.toml) |
| **Config file** | `pyproject.toml` `[tool.pytest.ini_options]` |
| **Quick run command** | `.venv/bin/pytest tests/test_soak_monitor_att_coverage.py -q` |
| **Full suite command** | `.venv/bin/pytest tests/ -v` |
| **Estimated runtime** | ~5 seconds (quick) / ~60 seconds (full) |

Additional lint gate: `shellcheck -S error scripts/soak-monitor.sh` (currently exit 0).

---

## Sampling Rate

- **After every task commit:** Run `.venv/bin/pytest tests/test_soak_monitor_att_coverage.py -q` + `shellcheck -S error scripts/soak-monitor.sh`
- **After every plan wave:** Run focused slice + full shellcheck; optional read-only `./scripts/soak-monitor.sh --json` smoke
- **Before `/gsd:verify-work`:** Full suite green + SAFE-14 git-diff empty + criterion-3 evidence recorded
- **Max feedback latency:** 60 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| TBD | TBD | TBD | MON-01 | — | error-scan covers live ATT units, not disabled `wanctl@att.service` | unit (script text) | `.venv/bin/pytest tests/test_soak_monitor_att_coverage.py::test_soak_monitor_scans_live_att_units -x` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | MON-02 | — | mode detection not Spectrum-hardcoded; ATT external mode at parity | unit (script text) | `.venv/bin/pytest tests/test_soak_monitor_att_coverage.py::test_soak_monitor_mode_detection_not_spectrum_hardcoded -x` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | guard | — | script stays shellcheck-clean after edit | unit (subprocess) | `.venv/bin/pytest tests/test_soak_monitor_att_coverage.py::test_soak_monitor_shellcheck_clean -x` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | SAFE-14 | — | controller-path zero-diff at phase boundary | git diff gate | `git diff --stat 87980bdf -- src/wanctl/` (control-path files; expect empty) | ✅ pattern exists | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_soak_monitor_att_coverage.py` — covers MON-01, MON-02, shellcheck guard; mirror `test_spectrum_cake_autorate_artifacts.py` read-and-assert pattern
- [ ] Framework install: none — pytest + shellcheck already present

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Live demonstration: error scan reads live ATT units against live journals | MON-01 (criterion 1 & 3) | Requires read-only run against live host journals; cannot be unit-tested | `./scripts/soak-monitor.sh --json` before/after unit-set contrast; inspect ATT `units`/`errors_1h`; record evidence artifact in phase dir |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 60s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending

> Phase 230 Nyquist PARTIAL resolution PENDING operator approval 2026-06-11 — recorded waiver `.planning/decisions/phase-230-nyquist-waiver.md` (META-03). Archived frontmatter left as-is per archive append-only-addendum policy.
