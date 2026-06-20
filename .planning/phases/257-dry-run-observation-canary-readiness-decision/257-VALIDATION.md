---
phase: 257
slug: dry-run-observation-canary-readiness-decision
status: draft
nyquist_compliant: true
wave_0_complete: false
created: 2026-06-19
---

# Phase 257 — Validation Strategy

> Per-phase validation contract for dry-run observation and canary-readiness planning.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest |
| **Config file** | `pyproject.toml` |
| **Quick run command** | `.venv/bin/pytest -o addopts='' tests/test_route_ownership_guard.py tests/test_health_check.py tests/test_operator_summary.py tests/test_check_config.py -q` |
| **Full suite command** | `.venv/bin/pytest tests/ -q` |
| **Estimated runtime** | quick slice ~30-90 seconds; full suite project-dependent |

---

## Sampling Rate

- **After any code change:** Run `.venv/bin/pytest -o addopts='' tests/test_route_ownership_guard.py tests/test_health_check.py tests/test_operator_summary.py tests/test_check_config.py -q`.
- **After evidence/docs-only tasks:** Run deterministic artifact checks listed in the task, plus `git diff --check`.
- **Before `/gsd:verify-work`:** Required plan verification commands and final evidence packet checks must be green.
- **Max feedback latency:** Keep automated feedback under 2 minutes for code changes; evidence collection is bounded by the 10-15 minute observation window.

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 257-01-01 | 01 | 1 | SAFE-20 | T-257-01 | Live commands are predeclared, allowlist-validated, and read-only before execution | artifact/source | `python3 scripts/validate-readonly-command-file.py <artifact>` or equivalent plan-local validator | ❌ W0 | ⬜ pending |
| 257-01-02 | 01 | 1 | OBSERVE-01, SAFE-20 | T-257-02 | Dry-run observation records intended route decisions without RouterOS route mutation | evidence/manual | evidence transcript contains only `COMMAND:` lines passing the allowlist and no applied route action | ❌ W0 | ⬜ pending |
| 257-01-03 | 01 | 1 | OBSERVE-02 | T-257-03 | Intended wanctl state is compared to live Netwatch/default-route inventory with divergences recorded as evidence | evidence/manual | readiness packet includes intended-vs-live comparison table | ❌ W0 | ⬜ pending |
| 257-01-04 | 01 | 1 | OBSERVE-03 | T-257-04 | Final packet says exactly `ready-for-approval` or `not-ready`, with blockers and rollback pointers | artifact/source | `grep -E '^(Verdict|Decision): (ready-for-approval|not-ready)' <packet>` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] A plan-local read-only command validator or shell/Python check exists before any live command task can run.
- [ ] The validator rejects mutating RouterOS verbs/actions (`set`, `add`, `remove`, `enable`, `disable`, `run`, `import`, `reset`) and shell metacharacters on issued-command lines.
- [ ] The validator scans only lines prefixed `COMMAND:` when proving no mutation.
- [ ] If a narrow code fix is needed for read-only ownership inspection, focused tests cover the fallback and fail-closed behavior before any deploy/restart gate.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Bounded live dry-run observation from `cake-shaper` | OBSERVE-01, SAFE-20 | Requires production steering host and live RouterOS/Netwatch read-only state | Execute only the prevalidated command file, preserve transcript with `COMMAND:` prefixes, and verify no route/Netwatch/CAKE/qdisc mutation occurred. |
| Intended-vs-live route ownership comparison | OBSERVE-02 | Depends on current live Netwatch/default-route inventory | Compare route-management health/operator summary against RouterOS read-only inventory and record divergences, not mutations. |
| Canary-readiness verdict | OBSERVE-03 | Operator-facing decision artifact | Packet must state exactly `ready-for-approval` or `not-ready`; if mixed/incomplete evidence exists, choose `not-ready` with blockers. |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies.
- [ ] Sampling continuity: no 3 consecutive tasks without automated/source/evidence verification.
- [ ] Wave 0 covers all missing validator/test references.
- [ ] No watch-mode flags.
- [ ] Feedback latency < 2 minutes for automated tests; live observation explicitly bounded to 10-15 minutes.
- [x] `nyquist_compliant: true` set in frontmatter.

**Approval:** pending
