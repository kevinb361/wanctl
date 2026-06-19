---
phase: 239
slug: seam-refactor-icmplibbackend-byte-identical
status: approved
nyquist_compliant: true
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
| 239-01-T1 | 01 | 1 | SEAM-01, SEAM-03, SEAM-04 | controller-path drift | RttBackend Protocol + RttSample superset + IRTT adapter stub | unit/import | `python -c "from wanctl.rtt_backend import RttBackend, RttSample, IrttRttBackend"` | ❌ W1 | ⬜ pending |
| 239-01-T2 | 01 | 1 | SEAM-03, SEAM-04 | byte-identity regression | RttSample↔RTTSnapshot equivalence + irtt adapter shape | unit | `.venv/bin/pytest -o addopts='' tests/test_rtt_backend.py -q` | ❌ W1 | ⬜ pending |
| 239-02-T1 | 02 | 2 | SEAM-01, SEAM-02 | broken consumers / drift | probe() returns RttSample; publish boundary `_cached:RTTSnapshot` unchanged | unit | `python -c "import wanctl.rtt_measurement, wanctl.rtt_backend"` + isinstance check | ❌ W2 | ⬜ pending |
| 239-02-T2 | 02 | 2 | SEAM-02 | byte-identity regression | hot-path slice green = byte-identical proof | unit/regression | hot-path slice (`test_cake_signal/queue_controller/wan_controller/health_check`) | ✅ existing | ⬜ pending |
| 239-03-T1 | 03 | 3 | SAFE-17 | out-of-allowlist controller drift | fail-closed allowlist verifier anchored at v1.52 | source-diff/script | `bash -n scripts/phase239-safe17-boundary-check.sh && grep -q V153_ALLOWLIST_RE ...` | ❌ W3 | ⬜ pending |
| 239-03-T2 | 03 | 3 | SAFE-17 | out-of-allowlist controller drift | verifier passes; evidence JSON `passed:true` | source-diff/script | `bash scripts/phase239-safe17-boundary-check.sh` (exit 0, writes safe17-boundary-239.json) | ❌ W3 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

*Central proofs: (1) hot-path slice stays green = byte-identical regression proof; (2) snapshot-equivalence unit test asserts `RttSample.to_snapshot() == RTTSnapshot`; (3) SAFE-17 fail-closed source-diff verifier proves no out-of-allowlist controller-path drift at the phase boundary.*

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
