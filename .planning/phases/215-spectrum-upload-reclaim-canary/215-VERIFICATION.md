---
phase: 215-spectrum-upload-reclaim-canary
verified: 2026-05-29T15:16:59Z
status: passed
score: 25/25 must-haves verified
overrides_applied: 0
---

# Phase 215: Spectrum Upload Reclaim Canary Verification Report

**Phase Goal:** Spectrum upload reclaim canary after baseline evidence  
**Verified:** 2026-05-29T15:16:59Z  
**Status:** passed  
**Re-verification:** No — initial verification

## Goal Achievement

The phase goal was conservative: execute an approved, evidence-backed one-knob Spectrum upload canary and resolve it safely, not necessarily keep a reclaim. Actual evidence shows the ceiling-20 canary was executed, scored as bounded `void` due to collapsed measurement windows, and then rolled back to ceiling 18 with DB and canary-check proof. That satisfies the ROADMAP/RECLAIM contract as a safe, resolved canary with evidence.

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | ROADMAP SC1: Spectrum upload setpoint 12, ceiling 18, plan 40 Mbps, latency, floor-hit counts, and suppression counters are evaluated against baseline evidence. | ✓ VERIFIED | `215-CONTEXT.md` D-02/D-04/D-05, `215-RESEARCH.md` lines 99-131, and `215-REPORT.md` lines 11-17 record knobs, plan anchor, latency, throughput, floor-hit/alert context, and leg-A/leg-B values. |
| 2 | ROADMAP SC2: Exactly one knob is selected for canary or the phase explicitly decides not to tune. | ✓ VERIFIED | `configs/spectrum.yaml` final state is back at `ceiling_mbps: 18`; `215-REPORT.md` lines 18-24 records only `continuous_monitoring.upload.ceiling_mbps: 18 -> 20`, then targeted restore. |
| 3 | ROADMAP SC3: Snapshot A rollback and success/rollback gates are documented before any production mutation. | ✓ VERIFIED | Snapshot A manifest records read-only pre-mutation anchor and targeted revert sequence; gate script and plans define pass/fail/void gates before Plan 03 mutation. |
| 4 | ROADMAP SC4: Canary either improves operator-relevant quality without gate regression or rolls back cleanly with evidence. | ✓ VERIFIED | `evidence/verdict.json` is `void`/exit 2; rollback evidence has DB row `18` and canary-check with Errors: 0. |
| 5 | Upload throughput series (`TCP upload`) can be extracted without failing closed. | ✓ VERIFIED | `scripts/phase214-extract.py` defines `extract_flent_upload_throughput`; leg-A/B extracts use `series_key_used: TCP upload`; extractor tests passed. |
| 6 | Gate emits verdict.json with pass/fail/void scoring D-04/D-05 and derives thresholds from same-session leg-A. | ✓ VERIFIED | `evidence/verdict.json` has `threshold_source: baseline_extract`, leg-A-derived p95/p99/win bounds, candidate values, and verdict `void`. |
| 7 | Gate exit-code contract is pinned with VOID -> 2 and Plan 03 captures rc safely. | ✓ VERIFIED | Script lines 14-16 pin exit codes; `evidence/gate-rc.txt` is `2`; `215-REPORT.md` records rc 2. |
| 8 | D-09: gate emits void when the leg-B window is collapsed with numeric collapse thresholds. | ✓ VERIFIED | `evidence/verdict.json` has `verdict: void`, `reason: collapsed_measurement_window`, `signal_outlier_rate_p90: 0.533`, threshold `0.3`, exit code 2. |
| 9 | Phase 213 reference numbers are recorded as static fallback/sanity-check only. | ✓ VERIFIED | Gate script includes BASELINE_REF and FALLBACK constants; verdict records both fallback constants and `threshold_source: baseline_extract`. |
| 10 | Tooling additions have offline pytest coverage without production access. | ✓ VERIFIED | `tests/test_phase215_extract_upload.py` and `tests/test_phase215_reclaim_gate.py` exist; targeted test run passed 12 tests. |
| 11 | D-06: Snapshot A captures pre-mutation production state via Phase 211 pattern. | ✓ VERIFIED | Snapshot A manifest lists repo/deployed config, state, bound `/health`, version/uptime, DB query; evidence files exist. |
| 12 | D-06/REVIEW-4: revert sequence is targeted single-key restore to 18, not whole-file checkout. | ✓ VERIFIED | Snapshot A manifest lines 34-42 and `215-REPORT.md` lines 20-24 record targeted restore and explicitly reject `git checkout configs/spectrum.yaml`. |
| 13 | Config-snapshot DB query uses exact json_extract query or records absence. | ✓ VERIFIED | Snapshot A `db-query.redacted.json` records exact query and absent row; deploy proof DB reads 20; rollback DB reads 18. |
| 14 | Committed evidence is redacted. | ✓ VERIFIED | Secret grep over evidence found no `ROUTER_PASSWORD`, `DISCORD_WEBHOOK`, or password-shaped values. |
| 15 | Leg-A is captured in Plan 03 immediately before mutation. | ✓ VERIFIED | Leg-A manifest shows capture 14:51:58-14:54:36; leg-B first attempt starts 14:57:01 after deploy/restart proof. |
| 16 | D-01: exactly one knob changes: ceiling 18 -> 20; setpoint/floor/step stay frozen. | ✓ VERIFIED | `215-REPORT.md` records semantic delta; `configs/spectrum.yaml` final floor 8, setpoint 12, step 5, ceiling 18 after rollback. |
| 17 | D-02: ceiling is justified as lever by baseline evidence. | ✓ VERIFIED | `215-CONTEXT.md` and `215-RESEARCH.md` record ceiling-bound baseline rationale and reject setpoint as near-no-op. |
| 18 | D-03: magnitude is +2 to 20, not +4 to 22. | ✓ VERIFIED | Plan/report evidence shows only ceiling 20 canary; final report says future attempt should not jump to 22. |
| 19 | REVIEW-6: pre/post YAML semantic-delta assertion and clean worktree guard before deploy. | ✓ VERIFIED | `215-03-SUMMARY.md` and `215-REPORT.md` record semantic delta exactly one leaf and clean `src/wanctl/` before deploy. |
| 20 | REVIEW-5/D-07/D-10: leg-A and leg-B are back-to-back same session with same bind/host/duration. | ✓ VERIFIED | Leg-A and leg-B manifests both use `spectrum=10.10.110.226`, host `dallas`, `tcp_upload`, 120s duration. |
| 21 | Ceiling=20 was deployed, daemon restarted, and proven via DB row + real `20000kbit` CAKE log. | ✓ VERIFIED | Deploy proof DB row is `20`; CAKE log contains upload `20000kbit`; canary-check after deploy has Errors: 0. |
| 22 | Bounded VOID safe default rolls back to 18, never stranding production at 20. | ✓ VERIFIED | Three leg-B attempts are recorded; final verdict `void`; rollback DB row is `18`; final config is `ceiling_mbps: 18`. |
| 23 | Gate invocation captured rc and branched on parsed verdict.json. | ✓ VERIFIED | `gate-rc.txt` is `2`; `verdict.json` is present and parsed in `215-REPORT.md`; rollback/report branch ran. |
| 24 | On bounded VOID exhausted, rollback is targeted single-key restore and canary-check confirms. | ✓ VERIFIED | `215-REPORT.md` lines 18-32 plus rollback evidence prove targeted restore, DB row 18, and canary-check Errors: 0. |
| 25 | libreqos runs as non-gating corroboration only. | ✓ VERIFIED | `215-REPORT.md` lines 42 and 46 record libreqos corroboration as optional/non-gating. |

**Score:** 25/25 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|---|---|---|---|
| `scripts/phase214-extract.py` | Upload throughput extractor reading `TCP upload`, no `TCP totals` fallback | ✓ VERIFIED | `UPLOAD_THROUGHPUT_KEYS` excludes `TCP totals`; leg extracts use `TCP upload`; tests passed. |
| `tests/test_phase215_extract_upload.py` | Offline upload extraction/fail-closed tests | ✓ VERIFIED | Covers upload, download-only, and TCP-totals-only fail-closed cases. |
| `scripts/phase215-reclaim-gate.sh` | Verdict-emitting D-04/D-05/D-09 gate with derived bounds and exit codes | ✓ VERIFIED | Emits verdict JSON; constants and scoring logic present; bash syntax passes. |
| `tests/test_phase215_reclaim_gate.py` | Offline pass/fail/void exit-code tests | ✓ VERIFIED | Targeted pytest run passed. |
| `evidence/snapshot-a/20260529T144229Z/` | Snapshot A rollback anchor | ✓ VERIFIED | Manifest, repo/deployed YAML, state, health, DB query evidence exist. |
| `evidence/leg-a-ceiling18/` | Leg-A tcp_upload evidence at ceiling 18 | ✓ VERIFIED | Manifest + extract + run directory exist; extract has p95/p99 and upload median. |
| `evidence/leg-b-ceiling20/` | Leg-B tcp_upload attempts and deploy proof | ✓ VERIFIED | Three attempts, deploy proof, extract, and manifest exist. |
| `evidence/verdict.json` | Gate verdict with derived bounds and per-gate values | ✓ VERIFIED | Contains `void`, exit 2, derived bounds, candidate values, outlier p90. |
| `evidence/rollback-ceiling18/` | Rollback proof | ✓ VERIFIED | DB row `18`, health, and canary-check evidence exist. |
| `configs/spectrum.yaml` | Final safe state after rollback | ✓ VERIFIED | Final checked-in upload ceiling is `18`; setpoint/floor/step unchanged. |
| `215-REPORT.md` | Operator closeout for RECLAIM-01/02/03 | ✓ VERIFIED | Report closes all three RECLAIM IDs and records bounded VOID + rollback outcome. |

### Key Link Verification

| From | To | Via | Status | Details |
|---|---|---|---|---|
| `scripts/phase215-reclaim-gate.sh` | Leg-A/leg-B extract JSON from `phase214-extract.py` | `--baseline-extract` / `--candidate-extract` | ✓ WIRED | Verdict uses leg-A baseline and leg-B candidate values from extract JSON. |
| Gate | Health NDJSON | `--baseline-health` / `--candidate-health` | ✓ WIRED | Gate computes floor-hit, alert events, bloat, outlier p90, and collapse state from health NDJSON. |
| `configs/spectrum.yaml` ceiling=20 | Deployed service | deploy + restart + DB/log proof | ✓ WIRED | DB row 20 and CAKE `20000kbit` proof exist before leg-B capture. |
| Verdict | Rollback branch | rc captured + parsed `verdict.json` | ✓ WIRED | `void`/rc 2 did not abort; rollback evidence and report were produced. |
| Snapshot A | Rollback | targeted ceiling restore to 18 | ✓ WIRED | Rollback DB row 18 and canary-check proof exist. |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|---|---|---|---|---|
| `phase214-extract.py` | `upload_throughput` | Flent `results["TCP upload"]` | Yes — leg-A sample_count 594, leg-B sample_count 596 | ✓ FLOWING |
| `phase215-reclaim-gate.sh` | `derived_*_bound`, candidate metrics | Leg-A/leg-B extract JSON and health NDJSON | Yes — verdict records real derived bounds and candidate values | ✓ FLOWING |
| `215-REPORT.md` | closeout values | Evidence manifests/extracts/verdict/rollback proof | Yes — report numbers match evidence files | ✓ FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|---|---|---|---|
| Tooling tests and gate syntax | `.venv/bin/pytest tests/test_phase215_extract_upload.py tests/test_phase215_reclaim_gate.py tests/test_phase214_flent_extract.py -q && bash -n scripts/phase215-reclaim-gate.sh` | 12 passed; bash syntax clean | ✓ PASS |
| Regression gate from verification notes | `.venv/bin/pytest tests/test_alert_engine.py tests/integration/test_flapping_integration.py -q` | 132 passed | ✓ PASS |
| Evidence redaction | grep-equivalent scan for secret tokens/password-shaped values under evidence | No matches | ✓ PASS |
| Deploy proof string | scan deploy proof for `20000kbit` and wrong `bandwidth_kbit=20000` | `20000kbit` present; wrong string absent | ✓ PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|---|---|---|---|---|
| RECLAIM-01 | Plans 02/03 | Spectrum upload operating points evaluated against current production evidence. | ✓ SATISFIED | `215-REPORT.md` RECLAIM-01 records starting knobs, leg-A values, leg-B values, and non-decisive VOID throughput delta. |
| RECLAIM-02 | Plans 01/02/03 | At most one upload knob changes per canary cycle, with Snapshot A rollback, explicit success and rollback gates. | ✓ SATISFIED | Snapshot A exists; semantic delta is one leaf; gate exists; rollback targeted ceiling restore to 18. |
| RECLAIM-03 | Plans 01/03 | Successful reclaim improves throughput/perceived quality without increasing floor-hit, alert spam, or p95/p99 beyond bounds. | ✓ SATISFIED | No successful reclaim was kept; bounded VOID forced safe rollback. The requirement is satisfied conservatively by not declaring success and restoring production to ceiling 18 with proof. |

No orphaned Phase 215 requirements found: REQUIREMENTS.md maps exactly RECLAIM-01, RECLAIM-02, and RECLAIM-03 to Phase 215.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|---|---:|---|---|---|
| `scripts/phase214-extract.py` | 53 | `return []` in `_numeric_values` | ℹ️ Info | Intentional fail-closed helper behavior; missing series later raises `FlentExtractionError`, not a user-visible stub. |
| `scripts/phase215-reclaim-gate.sh` | 66-95 | Missing option-value validation reported by code review WR-03 | ⚠️ Warning | Advisory robustness issue for malformed operator commands; did not affect actual canary because required args were supplied and verdict/rollback evidence exists. |
| `scripts/phase215-reclaim-gate.sh` | 294-313 | Missing required metric validation reported by code review WR-01 | ⚠️ Warning | Advisory fail-closed hardening issue for malformed extract JSON; actual leg-A/leg-B extracts include required upload throughput and verdict was emitted. |
| `scripts/phase215-reclaim-gate.sh` | 120-130 | Remote YAML preflight quoting concern from code review WR-02 | ⚠️ Warning | Advisory preflight hardening concern; actual loaded-ceiling proof is independently established by config-snapshot DB row and CAKE log before leg-B. |

### Human Verification Required

None. The relevant outcome is evidence-backed and already resolved: the live canary was performed, produced a bounded VOID, and rolled back with machine-verifiable DB/log/canary-check proof.

### Gaps Summary

No blocking gaps found. Code review warnings remain advisory robustness hardening opportunities, but they do not invalidate the achieved phase goal: a safe, bounded, evidence-backed canary was executed and cleanly rolled back rather than keeping an unscorable reclaim.

---

_Verified: 2026-05-29T15:16:59Z_  
_Verifier: the agent (gsd-verifier)_
