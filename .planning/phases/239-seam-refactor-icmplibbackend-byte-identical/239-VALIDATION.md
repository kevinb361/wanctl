---
phase: 239
slug: seam-refactor-icmplibbackend-byte-identical
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-06-15
---

# Phase 239 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x (`.venv/bin/pytest`) |
| **Config file** | `pyproject.toml` (`[tool.pytest.ini_options]`) |
| **Quick run command** | `.venv/bin/pytest -o addopts='' tests/test_cake_signal.py tests/test_queue_controller.py tests/test_wan_controller.py tests/test_health_check.py -q` |
| **Full suite command** | `.venv/bin/pytest tests/ -q` |
| **Estimated runtime** | ~43 seconds (hot-path slice); full suite longer |

---

## Sampling Rate

- **After every task commit:** Run quick run command (hot-path slice)
- **After every plan wave:** Run full suite command
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 60 seconds (hot-path slice)

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| TBD | — | — | SEAM-01..04 / SAFE-17 | — | byte-identical icmplib RTT; no out-of-allowlist controller drift | unit + source-diff | hot-path slice + SAFE-17 verifier | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

*Note: planner populates concrete per-task rows during planning. Central proofs: (1) hot-path slice stays green = byte-identical regression proof; (2) snapshot-equivalence unit test asserts `RttSample.to_snapshot() == RTTSnapshot`; (3) SAFE-17 fail-closed source-diff verifier proves no out-of-allowlist controller-path drift at the phase boundary.*

---

## Wave 0 Requirements

- [ ] Snapshot-equivalence test for `RttSample` ↔ `RTTSnapshot` coercion (new test stub)
- [ ] Existing hot-path slice (673 tests) already green — serves as byte-identical regression proof

*Existing infrastructure covers the regression-proof requirement; only the equivalence test stub is net-new.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| SAFE-17 boundary clean | SAFE-17 | Source-diff verifier is a script run at phase boundary, not a pytest case | Run the SAFE-17 source-diff verifier script against the `v1.52` anchor; must exit 0 with no out-of-allowlist controller-path files |

*All code behaviors have automated verification; SAFE-17 is a scripted boundary check.*

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 60s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
