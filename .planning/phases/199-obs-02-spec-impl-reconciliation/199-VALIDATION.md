---
phase: 199
slug: obs-02-spec-impl-reconciliation
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-02
---

# Phase 199 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> **Phase scope: docs-only.** "Nyquist sampling" maps to: every doc edit has at least one mechanizable check that re-runs in seconds.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.2 (verified via `.venv/bin/pytest --version`) |
| **Config file** | `pyproject.toml` (`[tool.pytest.ini_options]`); `tests/conftest.py` |
| **Quick run command** | `.venv/bin/pytest -o addopts='' tests/test_wan_controller.py -k "skip_rtt_confidence_when_none" -q` |
| **Full suite command** | `.venv/bin/pytest tests/ -v` (full project suite — not required for a docs-only phase) |
| **Estimated runtime** | ~0.40s for the single-test pin; full doc-grep bundle < 5s |

---

## Sampling Rate

- **After every task commit:** Run the doc-grep that corresponds to the file just edited (1–2s).
- **After every plan wave:** Run all four doc-greps + `git diff --name-only -- src/wanctl/` invariant + the optional pytest pin (sum < 5s).
- **Before `/gsd-verify-work`:** All five mechanizable checks must pass and be recorded in `199-VERIFICATION.md`.
- **Max feedback latency:** 5 seconds.

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 199-01-01 | 01 | 1 | OBS-02 | — | REQUIREMENTS.md OBS-02 row contains all four anchor phrases + amendment annotation | doc-grep | `for p in 'absent SQLite rows' 'cold-start' 'invalid-snapshot' 'wanctl_arbitration_active_primary' 'amended in Phase 199'; do grep -qF "$p" .planning/REQUIREMENTS.md \|\| { echo "MISSING: $p"; exit 1; }; done` | ✅ `.planning/REQUIREMENTS.md:27` | ⬜ pending |
| 199-01-02 | 01 | 1 | OBS-02 | — | SUBSYSTEMS.md `## Health And Metrics` mentions `signal_arbitration` and the four OBS-01 field names | doc-grep | `for p in signal_arbitration active_primary_signal rtt_confidence cake_av_delay_delta_us control_decision_reason; do grep -qF "$p" docs/SUBSYSTEMS.md \|\| { echo "MISSING: $p"; exit 1; }; done` | ❌ W0 | ⬜ pending |
| 199-01-03 | 01 | 1 | OBS-02 | — | RUNBOOK.md SQLite/history section names `wanctl_arbitration_active_primary` as the per-cycle denominator | doc-grep | `grep -qF "wanctl_arbitration_active_primary" docs/RUNBOOK.md && grep -qF "denominator" docs/RUNBOOK.md` | ❌ W0 | ⬜ pending |
| 199-01-04 | 01 | 2 | OBS-02 | — | `199-VERIFICATION.md` exists with `phase_scope: docs-only` and `files_touched` listing only `.planning/REQUIREMENTS.md`, `docs/SUBSYSTEMS.md`, `docs/RUNBOOK.md` | doc-grep | `grep -qE '^phase_scope: docs-only' .planning/phases/199-obs-02-spec-impl-reconciliation/199-VERIFICATION.md && grep -qE '^files_touched:' .planning/phases/199-obs-02-spec-impl-reconciliation/199-VERIFICATION.md` | ❌ W0 | ⬜ pending |
| 199-01-05 | 01 | 2 | OBS-02 | — | Docs-only invariant — no Python source under `src/wanctl/` changed for this phase | git-diff | `[ -z "$(git diff --name-only "$PHASE_BASE..HEAD" -- src/wanctl/)" ]` (where `$PHASE_BASE` = the SHA at Phase 199 start, e.g., `41f96e6`) | ✅ infra exists | ⬜ pending |
| 199-01-06 | 01 | 2 | OBS-02 (optional) | — | Test pin still encodes absent-row behavior the spec describes (line drift safe — searches by test name) | unit (test pin) | `.venv/bin/pytest -o addopts='' tests/test_wan_controller.py -k "skip_rtt_confidence_when_none" -q` (timed at 0.40s) | ✅ `tests/test_wan_controller.py:2654` | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `docs/SUBSYSTEMS.md` — add `signal_arbitration` field-shape note covering OBS-02 absent-row semantics. **Targeted edit only — no new file.** Enumerate the **four OBS-01 fields only** (`active_primary_signal`, `rtt_confidence`, `cake_av_delay_delta_us`, `control_decision_reason`); do **not** mention `refractory_active` (Phase 197 addition; outside the OBS-01 contract — see RESEARCH.md Pitfall 5).
- [ ] `docs/RUNBOOK.md` — add operator-query note naming `wanctl_arbitration_active_primary` as the per-cycle denominator. **Targeted edit only — no new file.** Insertion site recommended at line ~365, immediately after the "endpoint-local vs. merged cross-WAN" paragraph.
- [ ] `199-VERIFICATION.md` — write phase-close artifact mirroring `198-VERIFICATION.md` frontmatter shape with `phase_scope: docs-only` + `files_touched: [.planning/REQUIREMENTS.md, docs/SUBSYSTEMS.md, docs/RUNBOOK.md]`.
- [ ] No framework install. No new fixtures. No new test files. Test pin already exists at `tests/test_wan_controller.py:2654`.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Reviewer reads SUBSYSTEMS.md note and confirms wording is in operator-comprehensible English (not internal jargon). | OBS-02 (operator-facing clarity) | Tone/clarity is qualitative; doc-grep can verify presence of anchor phrases but not whether the surrounding paragraph reads naturally. | One-time review during plan checker pass: read the modified paragraph end-to-end and confirm it would be useful to an on-call operator. |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 5s
- [ ] `nyquist_compliant: true` set in frontmatter (set by planner once doc-greps are wired into PLAN.md acceptance criteria)

**Approval:** pending
