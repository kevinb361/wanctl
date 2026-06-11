---
phase: 233-gated-repo-hygiene-sweep
verified: 2026-06-11T20:41:29Z
status: passed
score: 18/18 must-haves verified
overrides_applied: 1
overrides:
  - must_have: "After all three SWEEP plans land, the full pytest suite is green"
    reason: "Operator explicitly approved waiving this acceptance criterion because the current full-suite failures are known historical Phase 220/221 boundary-test noise; Phase 233 dedicated SAFE-15, BOUND-01, compile, and focused regression gates passed. The full suite is not claimed green."
    accepted_by: "Kevin/operator"
    accepted_at: "2026-06-11T19:50:55Z"
re_verification:
  previous_status: gaps_found
  previous_score: 17/18
  gaps_closed:
    - "A per-hit disposition table classifies every remaining wanctl@ reference, proving no stale native-ownership claim remains uncovered"
  gaps_remaining: []
  regressions: []
---

# Phase 233: Gated Repo Hygiene Sweep Verification Report

**Phase Goal:** gated repo hygiene sweep under Phase 232 cleanup-boundary guard, covering SWEEP-01, SWEEP-02, SWEEP-03, and SAFE-15.
**Verified:** 2026-06-11T20:41:29Z
**Status:** passed
**Re-verification:** Yes — after SWEEP-02 disposition evidence refresh

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Superseded one-off trial scripts in the "safe to remove soon" category are removed or archived, and the Phase 232 boundary guard passes (SWEEP-01). | ✓ VERIFIED | `.planning/cake-autorate-trials/run_*` no longer exists; manifest records `removed=80 missing=0`; `cleanup-boundary-233-01.json` and final guard evidence have `overall_pass: true`. |
| 2 | The 22 `run_*` trial scripts plus `parse_flent_summary.py` and result dirs no longer exist under `.planning/cake-autorate-trials/`. | ✓ VERIFIED | SWEEP-01 summary records all 80 approved REMOVE entries deleted; no `run_*` entry remains. |
| 3 | Future-doc denylist source still exists and BOUND-01 guard exits 0 after removal. | ✓ VERIFIED | `.planning/cake-autorate-trials/WANCTL_CAKE_AUTORATE_FUTURE.md` exists; fresh `bash scripts/check-cleanup-boundary.sh --out /tmp/verify-cleanup-boundary-233-rerun.json` passed. |
| 4 | Findings/review docs are preserved. | ✓ VERIFIED | `SPECTRUM_CAKE_FINDINGS.md`, `spectrum-att-drain-isolated-production-test-20260609T0231Z.md`, and `spectrum-dallas-endpoint-review-20260607T231556Z.md` remain KEEP-listed/preserved. |
| 5 | Explicit enumerable removal manifest exists and classifies entries remove/keep. | ✓ VERIFIED | `removal-manifest-233-01.txt` is tracked and records explicit `REMOVE`/`KEEP` classifications and zero-reference proof notes. |
| 6 | No remaining active doc describes Spectrum or ATT as native-wanctl-owned rate control without noting current external cake-autorate mode (SWEEP-02). | ✓ VERIFIED | PROFILING, PERFORMANCE, RUNBOOK, and STEERING contain native/external mode notes; CABLE_TUNING and SILICOM-BYPASS hits are classified historical/by-design in refreshed evidence. |
| 7 | PROFILING, PERFORMANCE, and RUNBOOK each carry mode-disambiguation notes mentioning external cake-autorate mode. | ✓ VERIFIED | Current grep finds external `cake-autorate-<wan>.service` / state-bridge notes in all three docs. |
| 8 | Native `wanctl@<wan>` operational examples are retained. | ✓ VERIFIED | Current line counts from `grep -c 'wanctl@'`: PROFILING 10, PERFORMANCE 6, RUNBOOK 4, CABLE_TUNING 7, STEERING 7, SILICOM-BYPASS 18 — all >= captured baselines. |
| 9 | A per-hit disposition table classifies every remaining `wanctl@` reference. | ✓ VERIFIED | Refreshed `sweep02-disposition-233-02.md` records STEERING post-edit count 7 and includes rows for all current STEERING hits at lines 5, 330, 331, 343, 344, 355, and 368; grep confirms the six candidate docs' current hit lines are represented. |
| 10 | Operator-judgment docs are edited only per explicit operator decision. | ✓ VERIFIED | STATE and SWEEP-02 summary record `annotate-steering-only`; CABLE_TUNING and SILICOM-BYPASS were left as historical/by-design and classified in disposition evidence. |
| 11 | Spectrum-only hardcoding remnants are removed only where the generic bridge/service env pattern exists, with no new abstraction (SWEEP-03). | ✓ VERIFIED | Spectrum unit now mirrors ATT's explicit env footprint; no bridge script merge/template or `$wan` abstraction was introduced. |
| 12 | Spectrum state-bridge unit sets explicit `WANCTL_EXTERNAL_*` identity/path/baseline env. | ✓ VERIFIED | `deploy/systemd/cake-autorate-spectrum-state-bridge.service` has explicit WAN name, DL/UL interfaces, state path, metrics DB, and baseline env lines. |
| 13 | Explicit unit values equal current script defaults unless drift is recorded. | ✓ VERIFIED | Unit pins `WANCTL_EXTERNAL_BASELINE_RTT=22.535852814520855`, recorded as operator-approved and matching the Spectrum bridge script default. |
| 14 | Native controller path is untouched and no bridge merge/template was introduced. | ✓ VERIFIED | Fresh `git diff --quiet v1.50..HEAD -- src/wanctl/...` passed; SAFE-15 evidence has `controller_path_diff_count: 0`. |
| 15 | Full pytest suite green after all sweep plans. | ✓ PASSED (override) | Full suite remains red and is not claimed green; operator-approved waiver covers known Phase 220/221 historical boundary-test noise. Dedicated Phase 233 gates passed. |
| 16 | SAFE-15 controller-path zero-diff holds at Phase 233 boundary. | ✓ VERIFIED | `safe15-boundary-233.json` has `passed: true`, `controller_path_diff_count: 0`, `dirty_tree_clean: true`; fresh SAFE-15 rerun passed. |
| 17 | BOUND-01 guard exits 0 on the post-sweep tree with phase-final evidence. | ✓ VERIFIED | `cleanup-boundary-233-final.json` has `overall_pass: true`; fresh BOUND-01 rerun passed. |
| 18 | Final evidence artifacts are durable/tracked. | ✓ VERIFIED | `git ls-files .planning/phases/233-gated-repo-hygiene-sweep/` lists all plans, summaries, review, validation, and evidence artifacts including the refreshed SWEEP-02 disposition file. |

**Score:** 18/18 truths verified (includes 1 operator-approved override)

### Required Artifacts

| Artifact | Expected | Status | Details |
|---|---|---|---|
| `.planning/cake-autorate-trials/WANCTL_CAKE_AUTORATE_FUTURE.md` | BOUND-01 denylist source preserved | ✓ VERIFIED | Exists; cleanup-boundary guard checks it as `must-exist` with status `ok`. |
| `.planning/phases/233-gated-repo-hygiene-sweep/evidence/removal-manifest-233-01.txt` | Explicit removal manifest | ✓ VERIFIED | Tracked; includes explicit REMOVE/KEEP classifications. |
| `.planning/phases/233-gated-repo-hygiene-sweep/evidence/cleanup-boundary-233-01.json` | SWEEP-01 guard evidence | ✓ VERIFIED | `overall_pass: true`. |
| `docs/PROFILING.md` | Native/external mode note | ✓ VERIFIED | Contains external cake-autorate note and retained native examples. |
| `docs/PERFORMANCE.md` | Native/external mode note | ✓ VERIFIED | Contains external cake-autorate note and retained native examples. |
| `docs/RUNBOOK.md` | Native/external mode note | ✓ VERIFIED | Contains external cake-autorate note and retained native examples. |
| `docs/STEERING.md` | Operator-selected native/external annotation | ✓ VERIFIED | Current STEERING has 7 `wanctl@` hit lines; all are classified in refreshed disposition evidence. |
| `.planning/phases/233-gated-repo-hygiene-sweep/evidence/sweep02-disposition-233-02.md` | Per-hit disposition table for every current `wanctl@` hit | ✓ VERIFIED | Current counts match the refreshed post-edit table: 10/6/4/7/7/18 line hits for the six candidate docs. |
| `deploy/systemd/cake-autorate-spectrum-state-bridge.service` | Explicit Spectrum bridge env | ✓ VERIFIED | Required env keys present once; ExecStart and health env retained. |
| `.planning/phases/233-gated-repo-hygiene-sweep/evidence/safe15-boundary-233.json` | SAFE-15 boundary evidence | ✓ VERIFIED | `passed: true`, `controller_path_diff_count: 0`. |
| `.planning/phases/233-gated-repo-hygiene-sweep/evidence/cleanup-boundary-233-final.json` | Phase-final BOUND-01 evidence | ✓ VERIFIED | `overall_pass: true`. |

### Key Link Verification

| From | To | Via | Status | Details |
|---|---|---|---|---|
| Trial-script removal | `scripts/check-cleanup-boundary.sh` | Post-removal and final guard runs with explicit `--out` paths | ✓ WIRED | SWEEP-01 and final JSON evidence passed; fresh guard command passed. |
| Docs mode notes | README native/external mode pattern | Copied mode-disambiguation phrasing | ✓ WIRED | Edited docs reference native `wanctl@` examples and external cake-autorate/state-bridge services. |
| SWEEP-02 evidence | Six candidate docs | Current `grep -n 'wanctl@'` output classified line-by-line | ✓ WIRED | The prior STEERING evidence gap is closed; every current STEERING hit appears in the table. |
| Spectrum unit | ATT state-bridge unit pattern | Mirrored explicit env footprint | ✓ WIRED | Spectrum unit carries identity/interface/log/state/metrics/baseline env block. |
| Post-sweep worktree | SAFE-15 checker | `phase225-safe13-boundary-check.sh --anchor v1.50` | ✓ WIRED | Evidence JSON emitted by checker and fresh command passed. |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|---|---|---|---|---|
| N/A | N/A | Documentation/systemd/evidence phase, no dynamic renderer | N/A | SKIPPED |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|---|---|---|---|
| SWEEP-02 current candidate-doc counts | `grep -c 'wanctl@' docs/PROFILING.md docs/PERFORMANCE.md docs/RUNBOOK.md docs/CABLE_TUNING.md docs/STEERING.md docs/SILICOM-BYPASS.md` | `10, 6, 4, 7, 7, 18`; matches refreshed evidence post-edit counts | ✓ PASS |
| SAFE-15 controller boundary holds | `bash scripts/phase225-safe13-boundary-check.sh --anchor v1.50 --out /tmp/verify-safe15-233-rerun.json` | `SAFE-13 boundary check passed` | ✓ PASS |
| BOUND-01 guard holds | `bash scripts/check-cleanup-boundary.sh --out /tmp/verify-cleanup-boundary-233-rerun.json` | `cleanup boundary check passed` | ✓ PASS |
| Python compile gate | `.venv/bin/python -m compileall -q src scripts` | exit 0 | ✓ PASS |
| Focused regression slice | `.venv/bin/pytest -o addopts='' tests/test_cleanup_boundary_guard.py tests/test_cake_signal.py tests/test_queue_controller.py tests/test_wan_controller.py tests/test_health_check.py -q` | `682 passed in 43.70s` | ✓ PASS |
| Spectrum unit syntax/structure | `systemd-analyze verify deploy/systemd/cake-autorate-spectrum-state-bridge.service` | Only expected missing repo-host ExecStart path plus unrelated host warning; structural env keys verified | ✓ PASS |
| Controller path zero diff | `git diff --quiet v1.50..HEAD -- src/wanctl/...` | exit 0 | ✓ PASS |
| Full suite | `.venv/bin/pytest tests/ -q` | Not rerun by verifier; 233-04 summary records `23 failed, 5385 passed, 11 skipped, 2 deselected` | ✓ PASSED (override) |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|---|---|---|---|---|
| SWEEP-01 | 233-01 | Superseded one-off trial scripts removed/archived per future-doc policy | ✓ SATISFIED | No `run_*` entries remain; manifest/evidence exist; keep docs preserved; BOUND-01 passed. |
| SWEEP-02 | 233-02 | No active doc describes Spectrum/ATT as native-owned without external mode note | ✓ SATISFIED | Current docs are annotated/classified, and refreshed disposition evidence covers every current hit including all 7 STEERING rows. |
| SWEEP-03 | 233-03 | Spectrum-only hardcoding removed where generic pattern exists; no new abstraction | ✓ SATISFIED | Spectrum unit explicit env mirrors ATT; no controller/script abstraction changes. |
| SAFE-15 | 233-04 | Zero controller-path source diff at phase boundary | ✓ SATISFIED | SAFE-15 JSON and fresh checker run passed with `controller_path_diff_count: 0`; independent git diff passed. |

No orphaned Phase 233 requirement IDs were found in `REQUIREMENTS.md` beyond SWEEP-01, SWEEP-02, SWEEP-03, and cross-phase SAFE-15.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|---|---:|---|---|---|
| None in modified/evidence surfaces | - | - | - | Placeholder/TODO scan of Phase 233 verification surfaces found no blocking stub indicators. |

### Human Verification Required

None. The remaining full-suite-red condition has an explicit operator waiver; no visual, external-service, or ambiguous behavior check is required for this repo-hygiene phase.

### Gaps Summary

No blocking gaps remain. The prior SWEEP-02 evidence gap is closed: `evidence/sweep02-disposition-233-02.md` now records STEERING post-edit `wanctl@` count as 7 and classifies all current STEERING hits. SWEEP-01, SWEEP-02, SWEEP-03, BOUND-01, and SAFE-15 are verified. The full pytest suite is still not green and is not claimed green; it is covered only by the recorded operator-approved waiver for known Phase 220/221 historical boundary-test noise.

---

_Verified: 2026-06-11T20:41:29Z_
_Verifier: the agent (gsd-verifier)_
