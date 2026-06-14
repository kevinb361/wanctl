---
phase: 236
slug: watchdog-fail-open-two-mode-reconciliation
status: planned
nyquist_compliant: true
wave_0_complete: false
created: 2026-06-12
---

# Phase 236 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (repo `.venv`, pytest 9.0.2) |
| **Config file** | `pyproject.toml` (repo standard) |
| **Quick run command** | `.venv/bin/pytest tests/test_silicom_bypass_cli.py -x -q` |
| **Full suite command** | `.venv/bin/pytest tests/ -q` |
| **Estimated runtime** | ~1s quick / full suite per repo norm |

---

## Sampling Rate

- **After every task commit:** Run `.venv/bin/pytest tests/test_silicom_bypass_cli.py -x -q`
- **After every plan wave:** Run `.venv/bin/pytest tests/ -q` plus the hot-path regression slice (CLAUDE.md) — unchanged since this phase does not touch the control path.
- **Before `/gsd:verify-work`:** Full suite green + SAFE-16 boundary `passed=true`.
- **Max feedback latency:** ~5 seconds (quick run)

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 236-01-* | 01 | 1 | WDOG-01 | Spurious live bypass (DoS) | Reconciled template has no `wanctl@%i` coupling; `.env` names live controller; off-by-default (no auto-enable) | static artifact assert | `.venv/bin/pytest tests/test_silicom_bypass_cli.py -k watchdog_unit -q` | ❌ W0 | ⬜ pending |
| 236-01-* | 01 | 1 | WDOG-01 | Controller-path tampering | ATT variant folded / `deploy.sh` + `phase231-rollback.sh` refs updated | static artifact assert | `.venv/bin/pytest tests/test_silicom_bypass_cli.py -k deploy_watchdog -q` | ❌ W0 | ⬜ pending |
| 236-01-* | 01 | 1 | WDOG-03 | Executor arms live relay (DoS) | `arm <pair> [timeout]` requires live gate; `disarm <pair>` idempotent; non-pair refused; integer-validated timeout | behavior (subprocess + fake) | `.venv/bin/pytest tests/test_silicom_bypass_cli.py -k 'arm or disarm' -q` | ❌ W0 | ⬜ pending |
| 236-02-* | 02 | 2 | WDOG-02 | Spurious live bypass (DoS) | Watched-unit inactive → `set_bypass on` + no `reset_bypass_wd`; active → pet + inline | behavior (fake bpctl + fake systemctl) | `.venv/bin/pytest tests/test_silicom_bypass_cli.py -k petter_expiry -q` | ❌ W0 | ⬜ pending |
| 236-02-* | 02 | 2 | SAFE-16 | Controller-path tampering | controller-path zero-diff at boundary | git boundary check (read-only) | `bash scripts/phase225-safe13-boundary-check.sh --anchor v1.51` | ✅ exists | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_silicom_bypass_cli.py` — add watchdog verbs (`set_wd_exp_mode`, `set_wd_autoreset`, `set_bypass_wd`, `reset_bypass_wd`, `get_bypass_wd`, `get_wd_exp_mode`) to the existing `_fake_bpctl` stub.
- [ ] `tests/test_silicom_bypass_cli.py` — add a fake `systemctl` injector (env-path override, like the existing fake `logger`) so the petter's `is-active` branch is testable offline.
- [ ] Static asserts: reconciled `silicom-bypass-watchdog@.service` contains NO `wanctl@%i`; `.env.example` files name the live controller unit; no `[Install]`-driven auto-enable.
- [ ] Behavior tests: petter-body expiry proof; `arm`/`disarm` verbs + live gate.

*Existing 27-test harness fully covers the subprocess+env+fake pattern; gaps are additive, not new infrastructure.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Live `.env` update on `cake-shaper` | WDOG-01 | Touches live host config | Operator-gated checkpoint; rollback = restore prior `.env` |
| `systemctl daemon-reload`/`enable`/`start` of a watchdog unit on live host | WDOG-01/03 | Mutates live host state | Operator-gated checkpoint; never executor-run |
| `silicom-bypass arm <live-pair>` | WDOG-03 | Arms a real relay → can fire live bypass | Operator-gated checkpoint; rollback = `disarm` + restore inline |

*All correctness proof is automated/offline (fake bpctl + fake systemctl). The manual items are live-host arming actions intentionally excluded from autonomous execution.*

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references (236-01 Task 1)
- [x] No watch-mode flags
- [x] Feedback latency < 5s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** planner (2026-06-12)
