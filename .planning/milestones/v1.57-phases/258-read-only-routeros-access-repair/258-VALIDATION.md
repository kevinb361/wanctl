---
phase: 258
slug: read-only-routeros-access-repair
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-06-20
---

# Phase 258 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x |
| **Config file** | `pyproject.toml` (project addopts) |
| **Quick run command** | `.venv/bin/pytest -o addopts='' tests/test_routeros_rest.py -q` |
| **Full suite command** | `.venv/bin/pytest tests/ -q` |
| **Estimated runtime** | ~60 seconds (full suite) |

---

## Sampling Rate

- **After every task commit:** Run the quick run command
- **After every plan wave:** Run the full suite command
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 60 seconds

---

## Per-Task Verification Map

> The planner populates the concrete task IDs. The dimensions below are the
> verification spine the planner must satisfy.

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| (planner-assigned) | 01 | 1 | ACCESS-01 | — | Root cause of inaccessible read path documented (transport + netwatch-handler gap) | manual/doc | grep evidence doc for both failure layers | ✅ | ⬜ pending |
| (planner-assigned) | 02 | 2 | ACCESS-02 | T-258-01 | REST netwatch read returns parseable JSON; read-only by construction (GET only) | unit | `.venv/bin/pytest -o addopts='' tests/test_routeros_rest.py -q` | ❌ W0 | ⬜ pending |
| (planner-assigned) | 02 | 2 | ACCESS-03 / SAFE-21 | T-258-02 | Inspection command rejected by allowlist validator if not read-only | unit | allowlist validator unit test | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_routeros_rest.py` — add netwatch-handler unit coverage (REST GET → parseable rows) for ACCESS-02
- [ ] Allowlist-validator unit coverage extended to cover `/ip/route/print` + `/tool/netwatch/print` (ACCESS-03 / SAFE-21)

*Existing pytest infrastructure covers framework; only new test cases needed.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Live REST netwatch read returns real state from `cake-shaper` | ACCESS-02 | Requires privileged credential + live RouterOS at 10.10.99.1; operator-at-keyboard (`! <command>`) | Operator runs the documented read-only REST inspection command against the live router; capture exit 0 + non-empty parseable output as evidence |
| Live default-route read returns real state | ACCESS-02 | Same live-host / credential constraint | Operator runs `/ip/route/print` over REST; capture parseable output as evidence |

*Live-host reads are inherently manual under SAFE-21 / operator-at-keyboard. Code-path correctness is automated via unit tests; only the live proof is manual.*

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 60s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
