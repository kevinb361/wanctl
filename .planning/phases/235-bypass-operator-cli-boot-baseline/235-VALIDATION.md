---
phase: 235
slug: bypass-operator-cli-boot-baseline
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-06-12
---

# Phase 235 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (repo `.venv`); no bats — bash CLI tested via pytest + fake `bpctl_util` seam |
| **Config file** | `pyproject.toml` / `tests/conftest.py` (existing) |
| **Quick run command** | `.venv/bin/pytest tests/test_silicom_bypass_cli.py -x -q` |
| **Full suite command** | `make test` (`.venv/bin/pytest tests/ -v`) |
| **Estimated runtime** | quick ~5s; full suite per repo norm |

---

## Sampling Rate

- **After every task commit:** Run `.venv/bin/pytest tests/test_silicom_bypass_cli.py -x -q`
- **After every plan wave:** Run `make test`
- **Before `/gsd:verify-work`:** Full suite must be green AND SAFE-16 boundary check `passed=true` (`scripts/phase225-safe13-boundary-check.sh --anchor v1.51`)
- **Max feedback latency:** ~60 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| TBD | TBD | TBD | TOOL-01 | — | live read-back, never cached | unit (fake tool) | `pytest tests/test_silicom_bypass_cli.py::test_status_reads_live -x` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | TOOL-02 | T-input-validation | idempotent no-op; `--yes` gate; non-pair iface refused | unit (fake tool) | `::test_off_idempotent_noop` `::test_on_requires_yes` `::test_refuses_non_pair_iface` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | TOOL-03 | T-dual-wan-loss | dual-pair non-NIC requires `--both-wan-confirm` | unit (fake tool) | `::test_both_wan_confirm_gate` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | TOOL-04 | T-shell-injection | `mark` → journal + flat log, quoted label | unit (temp log path) | `::test_mark_appends_log` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | BOOT-01 | T-readback-mismatch | baseline applies 5 verbs, asserts read-back, fails loud on mismatch | unit (fake tool, good + mismatch paths) | `::test_baseline_applies_and_asserts` `::test_baseline_fails_on_mismatch` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | BOOT-01 | — | `silicom-bypass-init.service` well-formed, calls baseline | static unit-file asserts | `::test_init_service_artifact` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | SAFE-16 | T-controller-mutation | controller-path zero-diff at phase boundary | git boundary check (read-only) | `scripts/phase225-safe13-boundary-check.sh --anchor v1.51` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*
*Task IDs to be filled by the planner; map rows are the requirement-level contract.*

---

## Wave 0 Requirements

- [ ] `tests/test_silicom_bypass_cli.py` — stubs for TOOL-01..04, BOOT-01
- [ ] Fake `bpctl_util` fixture (inline or `tests/fixtures/`) — the offline seam (`BPCTL_UTIL=` env override)
- [ ] No framework install needed — pytest present; no bats

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Real `silicom-bypass status all` on cake-shaper | TOOL-01 | Live dual-WAN production host — operator-gated | Operator runs `silicom-bypass status all` over SSH; expects per-pair live state; no state change |
| Manual run of `silicom-bypass-init.service` + journal check | BOOT-01 | Live host; mutates card settings (to known-good baseline) | Operator: `systemctl start silicom-bypass-init`, then `journalctl -u silicom-bypass-init`; rollback = `off`+`conn` both pairs |
| Warm-reboot bypass preservation (optional, documented only) | — | Spectrum pair only; ATT is canary elsewhere; not executed by plans | Documented operator procedure; NOT run during phase execution |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 60s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
