---
phase: 134-diffserv-tin-separation
verified: 2026-04-03T17:30:00Z
status: human_needed
score: 2/3 success criteria verified
re_verification: false
human_verification:
  - test: "Confirm upload tin differentiation in production"
    expected: "ens16 shows non-zero Voice, Video, Bulk tins with normal traffic (already confirmed by Phase 133 with actual packet deltas)"
    why_human: "Phase 133 verified this with live traffic; Phase 134 plan 01 summary references it as confirmed. No new production test was run in phase 134 for upload direction specifically."
---

# Phase 134: Diffserv Tin Separation Verification Report

**Phase Goal:** CAKE tins correctly separate traffic by DSCP class and wanctl-check-cake validates it automatically
**Verified:** 2026-04-03T17:30:00Z
**Status:** human_needed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths (from Success Criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Download traffic shows differentiated tin distribution OR documented acceptance of current architecture | VERIFIED | 134-01-SUMMARY.md documents architectural limitation (bridge-before-router), confirmed with live data (rule counters non-zero, ens17 tin stats unchanged), rollback executed, decision documented |
| 2 | Per-tin CAKE stats show differentiated upload tin distribution | ? UNCERTAIN | Phase 133 confirmed upload works (Voice +100, Video +113, Bulk +219 deltas). Phase 134 plan 01 summary states "Upload DSCP: MikroTik postrouting marks survive through bridge to ens16 CAKE (confirmed Phase 133)". No new upload verification was performed in phase 134 itself. wanctl-history --tins exists as the reporting mechanism. |
| 3 | wanctl-check-cake includes a DSCP tin distribution check that validates non-trivial tin usage | VERIFIED | check_tin_distribution() exists in src/wanctl/check_cake.py (lines 552-708, 156 lines), integrated into run_audit() step 5 (lines 901-908), called via wanctl-check-cake entry point (pyproject.toml:22) |

**Score:** 2/3 success criteria verified (1 needs human confirmation)

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `src/wanctl/check_cake.py` | check_tin_distribution() function + run_audit() integration | VERIFIED | 156-line function, full error handling, non-BestEffort 0-packet WARN, below-threshold WARN, integrated as step 5 in run_audit() |
| `tests/test_check_cake.py` | TestTinDistribution + TestTinDistributionRunAuditIntegration | VERIFIED | 12 unit tests + 3 integration tests, all 15 pass |
| MikroTik prerouting chain (runtime) | 4 DSCP SET DL rules OR documented rollback | VERIFIED | Rules created, tested, proved non-functional due to bridge timing, rolled back. Architectural decision documented in 134-01-SUMMARY.md. |

### Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| `run_audit()` | `check_tin_distribution()` | conditional call when cake_params present | WIRED | Lines 901-908: `cake_params = data.get("cake_params"); if cake_params and isinstance(cake_params, dict):` then calls `check_tin_distribution(iface, direction)` |
| `check_tin_distribution()` | `tc -s -j qdisc show dev` | `subprocess.run()` | WIRED | Lines 579-584: `subprocess.run(["tc", "-s", "-j", "qdisc", "show", "dev", interface], capture_output=True, text=True, timeout=5)` |
| `wanctl-check-cake` CLI | `run_audit()` | `main()` at line 1394 | WIRED | pyproject.toml entry point `wanctl.check_cake:main`, main() calls run_audit() at line 1394 |
| `check_tin_distribution()` | `TIN_NAMES` from linux_cake | `from wanctl.backends.linux_cake import TIN_NAMES` | WIRED | Line 573: lazy import inside function body (avoids module-level coupling per design decision) |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `check_tin_distribution()` | `tins` list | `tc -s -j qdisc show dev {interface}` subprocess | Yes — reads live CAKE qdisc stats | FLOWING |
| `run_audit()` step 5 | `cake_params` | `data.get("cake_params")` from loaded config dict | Yes — reads from config YAML cake_params section | FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| check_tin_distribution returns WARN for 0-packet non-BE tin | `.venv/bin/pytest tests/test_check_cake.py -k "zero_packet_voice" -q` | PASSED | PASS |
| check_tin_distribution returns PASS for BestEffort | `.venv/bin/pytest tests/test_check_cake.py -k "besteffort_always_pass" -q` | PASSED | PASS |
| run_audit calls tin check when cake_params present | `.venv/bin/pytest tests/test_check_cake.py -k "run_audit_calls_tin_check" -q` | PASSED | PASS |
| run_audit skips tin check when cake_params absent | `.venv/bin/pytest tests/test_check_cake.py -k "skips_tin_check_when_cake_params_absent" -q` | PASSED | PASS |
| All 15 new tests pass | `.venv/bin/pytest tests/test_check_cake.py -k "TinDistribution" -q` | 15 passed | PASS |
| All 163 check_cake tests pass (no regressions) | `.venv/bin/pytest tests/test_check_cake.py -q` | 163 passed | PASS |
| Lint clean | `.venv/bin/ruff check src/wanctl/check_cake.py` | All checks passed | PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| QOS-02 | 134-01-PLAN.md | CAKE tins correctly separate traffic by DSCP class so EF/CS5 traffic gets lower latency than BE/BK | SATISFIED (alt path) | SC1 met via "documented acceptance" path: prerouting approach definitively disproven with data, architectural limitation documented, endpoint-set EF (VoIP/VPN) confirmed working in Voice tin (96M packets = 8.1% of download). Upload tin separation confirmed by Phase 133. |
| QOS-03 | 134-02-PLAN.md | wanctl-check-cake validates DSCP mark survival through the bridge path as an automated check | SATISFIED | check_tin_distribution() implemented, integrated into run_audit(), 15 tests passing, linting clean |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `src/wanctl/check_cake.py` | 244, 315, 732, 862, 869, 1085, 1150, 1156 | mypy "object has no attribute" errors for router client methods | Info | Pre-existing (introduced in phases 83-85, not phase 134). check_tin_distribution() itself has no mypy errors. No impact on tin distribution functionality. |

No TODOs, FIXMEs, or placeholder patterns found in phase 134 code additions.

### Human Verification Required

#### 1. Upload Tin Differentiation Confirmation (Phase 134 Scope)

**Test:** On cake-shaper VM, run `sudo tc -s -j qdisc show dev ens16` and confirm Voice, Video, and Bulk tins have non-zero packet counts from real traffic (not just test packets).

**Expected:** ens16 tin stats show meaningful distribution across all 4 tins — Bulk, BestEffort, Video, Voice all non-zero from production traffic (QOS_HIGH/MEDIUM/LOW connection-marks are active).

**Why human:** Phase 133 verified upload tin separation with a deliberate Python socket test (100 packets per DSCP class). Phase 134's SUMMARY only cross-references Phase 133 for upload direction — no new measurement was taken in Phase 134. The success criterion says "show differentiated traffic distribution for upload direction" which was confirmed in Phase 133 but should be confirmed still holds after Phase 134's MikroTik changes (even though they were rolled back, the chain was modified and restored).

This is a production state check requiring SSH access to cake-shaper VM and the MikroTik router being in normal operation.

### Gaps Summary

No blocking gaps found. The phase achieved its goal:

- **QOS-02 (download):** The architectural limitation (CAKE processes packets before MikroTik marks them) was definitively proven with live data — rules matched 41K+ packets but ens17 tins showed zero change. This is the correct outcome for SC1's "documented acceptance" alternative path. Endpoint-set DSCP (VoIP EF) continues working as the meaningful differentiation.

- **QOS-03 (automated check):** check_tin_distribution() is fully implemented, substantive (156 lines), wired into run_audit() and the wanctl-check-cake CLI, with 15 tests covering all error cases and integration paths. Data flows from live `tc` subprocess.

- **Uncertainty on SC2:** The "upload shows differentiated distribution" criterion was verified in Phase 133 and cross-referenced in Phase 134's summary. Phase 134 rolled back the only MikroTik changes made (prerouting DSCP SET DL rules), restoring the chain to its Phase 133 state. Upload tin separation should be unaffected. This requires a human confirmation step given production chain was temporarily modified.

---

_Verified: 2026-04-03T17:30:00Z_
_Verifier: Claude (gsd-verifier)_
