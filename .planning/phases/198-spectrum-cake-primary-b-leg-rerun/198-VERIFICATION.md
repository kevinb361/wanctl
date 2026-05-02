---
phase: 198-spectrum-cake-primary-b-leg-rerun
verified: 2026-05-02T10:48:52Z
status: passed
score: 4/4 must-haves verified
overrides_applied: 0
requirements: [VALN-04, VALN-05a, SAFE-05]
closed_via_rerun_attempt: 11
rerun_history:
  - attempt: 1
    local_window: "forced:operator requested immediate run outside off-peak"
    throughput_verdict: "n/a"
    median_of_medians_mbps: null
    per_run_audits_pass: false
    operator_decision: "retry"
    failed: true
  - attempt: 2
    local_window: "forced:operator requested immediate run outside off-peak"
    throughput_verdict: "FAIL"
    median_of_medians_mbps: 411.917833
    per_run_audits_pass: false
    operator_decision: "retry"
    failed: false
  - attempt: 3
    local_window: "forced:operator requested immediate run outside off-peak"
    throughput_verdict: "FAIL"
    median_of_medians_mbps: 334.083778
    per_run_audits_pass: false
    operator_decision: "retry"
    failed: false
  - attempt: 4
    local_window: "standard:02-04"
    throughput_verdict: "n/a"
    median_of_medians_mbps: null
    per_run_audits_pass: false
    operator_decision: "retry"
    failed: true
  - attempt: 5
    local_window: "standard:02-04"
    throughput_verdict: "n/a"
    median_of_medians_mbps: null
    per_run_audits_pass: false
    operator_decision: "retry"
    failed: true
  - attempt: 6
    local_window: "standard:02-04"
    throughput_verdict: "n/a"
    median_of_medians_mbps: null
    per_run_audits_pass: false
    operator_decision: null
    failed: true
  - attempt: 7
    local_window: "standard:02-04"
    throughput_verdict: "n/a"
    median_of_medians_mbps: null
    per_run_audits_pass: false
    operator_decision: "retry"
    failed: true
  - attempt: 8
    local_window: "standard:02-04"
    throughput_verdict: "n/a"
    median_of_medians_mbps: null
    per_run_audits_pass: false
    operator_decision: "retry"
    failed: true
  - attempt: 9
    local_window: "standard:02-04"
    throughput_verdict: "n/a"
    median_of_medians_mbps: null
    per_run_audits_pass: false
    operator_decision: "retry"
    failed: true
  - attempt: 10
    local_window: "standard:02-04"
    throughput_verdict: "FAIL"
    median_of_medians_mbps: 519.736152
    per_run_audits_pass: true
    operator_decision: "retry"
    failed: false
  - attempt: 11
    local_window: "standard:02-04"
    throughput_verdict: "PASS"
    median_of_medians_mbps: 674.156379
    per_run_audits_pass: true
    operator_decision: "promote"
    failed: false
---

# Phase 198: Spectrum cake-primary B-leg rerun Verification Report

**Phase Goal:** Close v1.40 milestone by re-running and canonicalizing Spectrum `cake-primary` B-leg evidence on the Phase 197 build so VALN-04 and VALN-05a close without violating SAFE-05.
**Verified:** 2026-05-02T10:48:52Z
**Status:** passed
**Re-verification:** No — current verification file existed, but it had no actionable `gaps:` section; this pass independently rechecked the final canonical artifacts and source guards.

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|---|---|---|
| 1 | Queue-primary invariant holds during each corrected `tcp_12down` loaded window: ≥95% `/health` samples are queue-primary, floor ≥25 samples/run, and no `refractory_active=true` sample is paired with queue-primary false. | ✓ VERIFIED | Canonical `loaded-window-audit-run1..3.json` from promoted attempt 11 each report `verdict: pass`, `health_sample_count: 30`, `queue_primary_health_pct: 100.0`, and `health_non_queue: 0`. |
| 2 | Throughput acceptance (VALN-05a) passes the locked rule: 2-of-3 medians ≥532 Mbps and median-of-medians ≥532 Mbps. | ✓ VERIFIED | `throughput-verdict.json` has `verdict: PASS`, medians `685.992066`, `674.156379`, `560.381543`, `medians_above_532: 3`, and `median_of_medians_mbps: 674.156379`; recomputation from `runs[].median_mbps` matched. |
| 3 | A/B comparison artifact exists against Phase 196 rtt-blend control evidence and all gated deltas pass, including fresh dwell-bypass closure. | ✓ VERIFIED | `ab-comparison.json` has `comparison_verdict: pass`, `regenerated_in_plan: 198-07`, all five gated deltas `pass`, and `dwell_bypass_responsiveness.evidence_source: fresh per-run capture during loaded windows (Plan 198-06)`. |
| 4 | SAFE-05 protected controller files remain unchanged from Phase 197 ship SHA to Phase 198 acceptance. | ✓ VERIFIED | `safe05-diff.json` has `phase_197_ship_sha: 068b804`, `protected_path_diffs: 0`, `diff_exit: 0`, `verdict: pass`, `regenerated_in_plan: 198-07`; `git diff --quiet 068b804..HEAD -- <5 protected files>` exited 0. |

**Score:** 4/4 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|---|---|---|---|
| `soak/cake-primary/preflight.json` | Phase 197 runtime/deployment proof, mode/source-bind preflight, no-concurrency attestation | ✓ VERIFIED | `verdict: pass`, SHA match true, refractory health field present, recent refractory metric rows `1166`, source-bind preflight egress true. |
| `soak/cake-primary/source-bind-egress-proof.json` | Promoted attempt egress proof for source bind `10.10.110.226` | ✓ VERIFIED | Canonical JSON promoted from attempt 11; per-run verdict links show `70.123.224.169` / `AS11427 Charter Communications Inc`. |
| `soak/cake-primary/safe05-baseline.json` | Phase 197 ship SHA and five protected-file blob baseline | ✓ VERIFIED | Baseline pins `068b804` and five protected files. |
| `soak/cake-primary/soak-window.json` | ≥24h soak duration gate | ✓ VERIFIED | Predicate `.duration_gate_passed == true and .elapsed_seconds >= 86400` passed. |
| `soak/cake-primary/cake-primary-start-20260427T145714Z-summary.json` | B-leg start capture summary | ✓ VERIFIED | Exists and feeds duration/evidence chain. |
| `soak/cake-primary/cake-primary-finish-20260428T152750Z-summary.json` | B-leg finish capture summary | ✓ VERIFIED | Exists and feeds 24h raw-row audit. |
| `soak/cake-primary/primary-signal-audit-phase197.json` | Phase 197 raw-row 24h audit | ✓ VERIFIED | `verdict: pass_with_documented_exceptions`, coverage `99.7493071127143%`, total raw samples `71801`; exceptions recorded. |
| `soak/cake-primary/flent/run1.flent.gz` | Promoted attempt 11 raw flent run 1 | ✓ VERIFIED | File exists and is non-empty. |
| `soak/cake-primary/flent/run2.flent.gz` | Promoted attempt 11 raw flent run 2 | ✓ VERIFIED | File exists and is non-empty. |
| `soak/cake-primary/flent/run3.flent.gz` | Promoted attempt 11 raw flent run 3 | ✓ VERIFIED | File exists and is non-empty. |
| `soak/cake-primary/flent/manifest.json` | Promoted attempt 11 manifest | ✓ VERIFIED | Contains three runs and promoted metadata. |
| `soak/cake-primary/loaded-window-audit-run1.json` | Canonical loaded-window audit run 1 | ✓ VERIFIED | `verdict: pass`, health count `30`, queue-primary `100.0%`, promoted from attempt 11. |
| `soak/cake-primary/loaded-window-audit-run2.json` | Canonical loaded-window audit run 2 | ✓ VERIFIED | `verdict: pass`, health count `30`, queue-primary `100.0%`, promoted from attempt 11. |
| `soak/cake-primary/loaded-window-audit-run3.json` | Canonical loaded-window audit run 3 | ✓ VERIFIED | `verdict: pass`, health count `30`, queue-primary `100.0%`, promoted from attempt 11. |
| `soak/cake-primary/throughput-verdict.json` | Canonical VALN-05a verdict | ✓ VERIFIED | `verdict: PASS`, `promoted_from_attempt: 11`; locked math recomputed from source medians. |
| `soak/cake-primary/ab-comparison.json` | Canonical six-delta comparison | ✓ VERIFIED | `comparison_verdict: pass`, `regenerated_in_plan: 198-07`, fresh dwell-bypass evidence. |
| `soak/cake-primary/safe05-diff.json` | SAFE-05 closeout diff | ✓ VERIFIED | `protected_path_diffs: 0`, `diff_exit: 0`, `verdict: pass`. |
| `198-06-ATTEMPT-LOG.md` | Cross-attempt audit history | ✓ VERIFIED | 11 attempt directories and 11 log sections; exactly one `## Attempt 11` section. |

### Key Link Verification

| From | To | Via | Status | Details |
|---|---|---|---|---|
| `preflight.json.deployment_proof.phase_197_ship_sha` | Phase 197 ship baseline | `safe05-baseline.json` + deployment proof | ✓ WIRED | Both use `068b804`; runtime proof records SHA match and Phase 197-only health/metric surfaces. |
| `rerun-attempt-11/throughput-verdict.json.runs[]` | Canonical `flent/run{1,2,3}.flent.gz` | Plan 198-07 staged promotion | ✓ WIRED | Canonical verdict is `promoted_from_attempt: 11`; flent files exist and are non-empty. |
| `loaded-window-audit-run{i}.health_ndjson_path` | Attempt 11 health NDJSON source | Per-run audit source paths | ✓ WIRED | Canonical audit JSONs were promoted from attempt 11 and keep source paths plus `promoted_from_attempt: 11`. |
| `source-bind-egress-proof.json.pre_run_probes[]` | `throughput-verdict.json.runs[]` | Joint IP+org probe before each flent run | ✓ WIRED | Throughput run entries show `70.123.224.169` and `AS11427 Charter Communications Inc`. |
| `ab-comparison.json.deltas.dwell_bypass_responsiveness` | Canonical loaded-window audit JSONs | Sum of `health_dwell_bypass_samples` | ✓ WIRED | B-leg fresh per-run total is `0`, evidence source is explicitly Plan 198-06 loaded-window capture. |
| `safe05-diff.json.phase_197_ship_sha` | Git diff over protected files | `git diff --quiet 068b804..HEAD -- ...` | ✓ WIRED | Artifact records `diff_exit: 0`; independent git command returned exit 0. |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|---|---|---|---|---|
| `loaded-window-audit-run1.json` | `queue_primary_health_pct`, `health_non_queue` | Attempt 11 `/health` NDJSON sampler + audit script | Yes — 30 samples, 100% queue, zero non-queue | ✓ FLOWING |
| `loaded-window-audit-run2.json` | `queue_primary_health_pct`, `health_non_queue` | Attempt 11 `/health` NDJSON sampler + audit script | Yes — 30 samples, 100% queue, zero non-queue | ✓ FLOWING |
| `loaded-window-audit-run3.json` | `queue_primary_health_pct`, `health_non_queue` | Attempt 11 `/health` NDJSON sampler + audit script | Yes — 30 samples, 100% queue, zero non-queue | ✓ FLOWING |
| `throughput-verdict.json` | `median_mbps`, `median_of_medians_mbps`, `medians_above_532` | Promoted attempt 11 manifest and flent-derived medians | Yes — medians recompute to 3 above threshold and MoM 674.156379 | ✓ FLOWING |
| `ab-comparison.json` | gated delta verdicts | Phase 196 rtt-blend evidence + canonical attempt 11 audits + throughput verdict | Yes — all five gated deltas pass, refractory fallback documented | ✓ FLOWING |
| `safe05-diff.json` | `protected_path_diffs`, `diff_exit` | Git diff from `068b804..HEAD` across five protected files | Yes — independent git command returned 0 | ✓ FLOWING |

### Behavioral Spot-Checks

| Behavior | Command / Predicate | Result | Status |
|---|---|---|---|
| Phase 198 roadmap contract loaded | `gsd-sdk query roadmap.get-phase 198 --raw` | Four success criteria in ROADMAP section; no parsed `success_criteria` array | ✓ PASS |
| Core artifact predicates | jq predicates over preflight, soak-window, audit, throughput, ab-comparison, safe05 | `all_core_jq_predicates_exit=0` | ✓ PASS |
| Attempt 11 source recompute | Python recomputed throughput and audit verdicts from JSON source fields | `recomputed_above=3`, `recomputed_mom=674.156379`, audits `pass/pass/pass` | ✓ PASS |
| Attempt log integrity | Count `rerun-attempt-*` directories vs `## Attempt` sections | `attempt_dirs=11`, `log_sections=11`, attempt 11 section count `1` | ✓ PASS |
| Protected source diff | `git diff --quiet 068b804..HEAD -- src/wanctl/queue_controller.py src/wanctl/cake_signal.py src/wanctl/fusion_healer.py src/wanctl/wan_controller.py src/wanctl/health_check.py` | exit `0` | ✓ PASS |
| Phase 198 script syntax | `.venv/bin/python3 -m py_compile scripts/phase198-loaded-window-audit.py scripts/phase198-throughput-verdict.py && bash -n scripts/phase198-rerun-flent-3run.sh` | exit `0` | ✓ PASS |
| Promoted flent raw artifacts | `test -s flent/run{1,2,3}.flent.gz` | all three exist and are non-empty | ✓ PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|---|---|---|---|---|
| VALN-04 | 198-02 through 198-07 | Spectrum cake-primary B-leg validation under Phase 197 semantics; A/B comparison against accepted Phase 196 rtt-blend control evidence. | ✓ SATISFIED | `primary-signal-audit-phase197.json` passes at 99.7493% over 71,801 raw samples; canonical `loaded-window-audit-run1..3.json` all pass; `ab-comparison.json` has `comparison_verdict: pass` with all gated deltas pass and fresh dwell-bypass evidence. |
| VALN-05a | 198-03, 198-06, 198-07 | Spectrum `flent tcp_12down` acceptance: 2-of-3 medians ≥532 Mbps and median-of-medians ≥532 Mbps. | ✓ SATISFIED | Attempt 11 canonical `throughput-verdict.json` has `verdict: PASS`, `medians_above_532: 3`, and `median_of_medians_mbps: 674.156379`. |
| SAFE-05 | 198-01 through 198-07 | No state-machine, EWMA, dwell, deadband, threshold, or burst-detection value changes. | ✓ SATISFIED | `safe05-diff.json` regenerated in Plan 198-07 with `protected_path_diffs: 0`, `diff_exit: 0`; independent protected-path `git diff --quiet` exited 0. |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|---|---:|---|---|---|
| `scripts/phase198-rerun-flent-3run.sh` | 325-327 | `REMOTE_DB` is interpolated inside a quoted remote SSH shell command | ⚠️ Residual Critical Review Finding | Code review CR-01 remains present. It does **not** invalidate already-captured/canonicalized attempt 11 evidence or the phase acceptance criteria, but the harness should not be reused with untrusted `--remote-db` values until fixed. |
| `scripts/phase198-loaded-window-audit.py` | 186-188 | `health_non_queue` counts non-queue only when `refractory_active` is true | ⚠️ Residual Review Finding | Code review WR-01 remains present. It does not invalidate attempt 11 because all three windows have 30/30 queue-primary samples (100% coverage), but a future 29/30 non-refractory non-queue window could still pass; fix before reusing as a generic audit gate. |
| `scripts/phase198-rerun-flent-3run.sh` | 190-227 | Health preflight occurs before attempt directory/trap | ⚠️ Residual Review Finding | Code review WR-02 remains partially present. It does not affect completed attempt 11 evidence; reuse risk is that unreachable health preflight can exit before writing contracted `attempt-summary.json`. |

### Human Verification Required

None for phase goal achievement. External observations (live `/health`, flent runs, and operator scheduling) are already preserved as evidence artifacts and were checked by deterministic predicates. Future reuse of the harness should address the residual review findings above.

### Rerun History

| Attempt | Window | Throughput | Median-of-medians Mbps | Per-run audits | Operator decision | Failed |
|---:|---|---|---:|---|---|---|
| 1 | forced:operator requested immediate run outside off-peak | n/a | n/a | fail/n/a | retry | true |
| 2 | forced:operator requested immediate run outside off-peak | FAIL | 411.917833 | fail/n/a | retry | false |
| 3 | forced:operator requested immediate run outside off-peak | FAIL | 334.083778 | fail/n/a | retry | false |
| 4 | standard:02-04 | n/a | n/a | fail/n/a | retry | true |
| 5 | standard:02-04 | n/a | n/a | fail/n/a | retry | true |
| 6 | standard:02-04 | n/a | n/a | fail/n/a | null | true |
| 7 | standard:02-04 | n/a | n/a | fail/n/a | retry | true |
| 8 | standard:02-04 | n/a | n/a | fail/n/a | retry | true |
| 9 | standard:02-04 | n/a | n/a | fail/n/a | retry | true |
| 10 | standard:02-04 | FAIL | 519.736152 | pass | retry | false |
| 11 | standard:02-04 | PASS | 674.156379 | pass | promote | false |

### Cascade Closure (HIGH-3)

HIGH-3 is closed via path (a). The final `ab-comparison.json` does not reuse the earlier failing 24h-soak dwell-bypass delta. Plan 198-07 regenerated the comparison from the canonical attempt 11 per-run loaded-window audits and computed `dwell_bypass_responsiveness.b_leg_count_per_run_total = 0` from `health_dwell_bypass_samples`, with A-leg count `0`; the gated delta verdict is `pass`.

### Gaps Summary

No blocking Phase 198 gaps remain. VALN-04 and VALN-05a are satisfied by canonical attempt 11 promotion and source-of-truth recomputation; SAFE-05 is satisfied by zero protected-path diff. Residual code-review findings are recorded as follow-up risks for future harness reuse, not as evidence invalidators.

---

_Verified: 2026-05-02T10:48:52Z_
_Verifier: the agent (gsd-verifier)_
