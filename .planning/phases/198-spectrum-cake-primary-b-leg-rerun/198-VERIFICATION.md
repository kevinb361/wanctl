---
phase: 198-spectrum-cake-primary-b-leg-rerun
verified: 2026-04-28T15:55:54Z
status: gaps_found
score: 1/4 must-haves verified
overrides_applied: 0
requirements: [VALN-04, VALN-05a, SAFE-05]
gaps:
  - truth: "Queue-primary invariant holds during each corrected tcp_12down loaded window"
    status: partial
    reason: "primary-signal-audit-phase197.json verifies the 24h raw soak window at 99.7493% queue-primary coverage, but the three flent runs occurred after that audit source_window and no per-run loaded-window active-primary audit artifact proves ≥95% queue-primary during each 30s run."
    artifacts:
      - path: ".planning/phases/198-spectrum-cake-primary-b-leg-rerun/soak/cake-primary/primary-signal-audit-phase197.json"
        issue: "source_window ends 2026-04-28T15:27:50Z; flent pre-run probes are 2026-04-28T15:35:11Z, 15:35:57Z, and 15:36:43Z."
      - path: ".planning/phases/198-spectrum-cake-primary-b-leg-rerun/soak/cake-primary/flent/manifest.json"
        issue: "Contains throughput run evidence but no matching active-primary coverage samples for each run window."
    missing:
      - "Per-run loaded-window queue-primary coverage audit (≥100 health samples or ≥500 raw SQLite active-primary rows per run) aligned to the three tcp_12down windows."
  - truth: "Spectrum throughput acceptance (VALN-05a) passes the locked 2-of-3 plus median-of-medians rule"
    status: failed
    reason: "throughput-verdict.json records medians 450.468331, 681.802267, and 494.834220 Mbps; only one run is >=532 Mbps and median-of-medians is 494.834220 Mbps. Operator selected blocked closeout rather than retry."
    artifacts:
      - path: ".planning/phases/198-spectrum-cake-primary-b-leg-rerun/soak/cake-primary/throughput-verdict.json"
        issue: "verdict == FAIL; medians_above_532 == 1; median_of_medians_mbps == 494.834220."
    missing:
      - "Passing 3-run Spectrum tcp_12down evidence with medians_above_532 >= 2 and median_of_medians_mbps >= 532."
  - truth: "A/B comparison closes VALN-04 with comparison_verdict pass"
    status: failed
    reason: "ab-comparison.json was produced and references the correct Phase 196 rtt-blend comparator, but comparison_verdict is fail because throughput failed and gated operational deltas did not all pass."
    artifacts:
      - path: ".planning/phases/198-spectrum-cake-primary-b-leg-rerun/soak/cake-primary/ab-comparison.json"
        issue: "comparison_verdict == fail; dwell_bypass_responsiveness and queue_primary_coverage_pct are fail; throughput.verdict == FAIL."
    missing:
      - "Passing A/B comparison verdict from the five gated operational deltas plus throughput PASS."
---

# Phase 198: Spectrum cake-primary B-leg rerun Verification Report

**Phase Goal:** Close v1.40 milestone by re-running the Spectrum `cake-primary` B-leg on the Phase 197 build to satisfy VALN-04 and VALN-05a, capture fresh corrected-source Spectrum throughput, and produce the missing `ab-comparison.json` artifact without violating SAFE-05.

**Verified:** 2026-04-28T15:55:54Z  
**Status:** gaps_found — operator-selected blocked closeout is preserved; this is not a passing validation.  
**Re-verification:** Yes — previous `198-VERIFICATION.md` existed with blocked gaps; actual artifact checks confirm blocking gaps remain and add the loaded-window queue-primary proof gap.

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Queue-primary invariant holds during each corrected tcp_12down loaded window with ≥95% active-primary queue coverage and no unexplained refractory RTT fallback. | ⚠️ PARTIAL / GAP | The 24h audit artifact exists and records `verdict: pass_with_documented_exceptions`, `raw_metric_total_samples: 71801`, `raw_metric_queue_samples: 71621`, `queue_primary_coverage_pct: 99.7493071127143`, and `rtt_fallback_during_refractory_count: 0`; however its source window ends `2026-04-28T15:27:50Z`, before the flent pre-run probes at `15:35:11Z`, `15:35:57Z`, and `15:36:43Z`. No per-run loaded-window active-primary audit proves the ROADMAP criterion for each 30s tcp_12down run. |
| 2 | Throughput acceptance (VALN-05a) passes: 2-of-3 individual medians ≥532 Mbps and median-of-medians ≥532 Mbps. | ❌ FAILED | `throughput-verdict.json` records medians `450.468331`, `681.802267`, `494.834220`, `medians_above_532: 1`, `median_of_medians_mbps: 494.834220`, and `verdict: FAIL`. |
| 3 | A/B comparison artifact exists against Phase 196 rtt-blend control evidence and computes all six deltas with pass closeout. | ❌ FAILED | `ab-comparison.json` exists, references `.planning/phases/196-.../soak/rtt-blend/manifest.json`, and has all six deltas, but `comparison_verdict: fail`; `dwell_bypass_responsiveness`, `queue_primary_coverage_pct`, and throughput fail. |
| 4 | SAFE-05 protected controller files have zero diff from Phase 197 ship SHA to Phase 198 closeout. | ✅ VERIFIED | `safe05-diff.json` records `phase_197_ship_sha: 068b804`, `protected_path_diffs: 0`, `diff_empty: true`, and `verdict: pass`; direct `git diff --quiet 068b804..HEAD -- <5 protected files>` returned exit 0. |

**Score:** 1/4 must-haves verified.

### Required Artifacts

| Artifact | Expected | Status | Details |
|---|---|---|---|
| `soak/cake-primary/preflight.json` | Phase 197 deployment proof + mode/source-bind preflight | ✅ VERIFIED | `verdict: pass`, `sha_match: true`, refractory field present, 1166 recent refractory metric rows, Spectrum egress proof. |
| `soak/cake-primary/source-bind-egress-proof.json` | Preflight and three pre-run probes | ✅ VERIFIED | Preflight plus 3 probes all `10.10.110.226` → `70.123.224.169` / `AS11427 Charter Communications Inc`. |
| `soak/cake-primary/safe05-baseline.json` | Phase 197 ship SHA and 5 protected-file blobs | ✅ VERIFIED | Pins `068b804`; all five protected paths present; `working_tree_diff_empty: true`. |
| `soak/cake-primary/soak-window.json` | ≥24h duration gate | ✅ VERIFIED | `elapsed_seconds: 88236`, `duration_gate_passed: true`, no-concurrent-experiment attestation true. |
| `cake-primary-start-20260427T145714Z-summary.json` | Start capture summary | ✅ EXISTS | Start anchor exists. |
| `cake-primary-finish-20260428T152750Z-summary.json` | Finish capture summary | ✅ EXISTS | Finish anchor exists. |
| `primary-signal-audit-phase197.json` | Raw-row Phase 197 audit | ⚠️ PARTIAL | Full-soak verdict is `pass_with_documented_exceptions` with 99.7493% coverage, but does not cover the later flent run windows. |
| `flent/run1.flent.gz` | Run 1 raw capture | ✅ VERIFIED | Exists (44,021 bytes) and gzip JSON parses. Median `450.468331` Mbps. |
| `flent/run2.flent.gz` | Run 2 raw capture | ✅ VERIFIED | Exists (43,737 bytes) and gzip JSON parses. Median `681.802267` Mbps. |
| `flent/run3.flent.gz` | Run 3 raw capture | ✅ VERIFIED | Exists (44,041 bytes) and gzip JSON parses. Median `494.834220` Mbps. |
| `flent/manifest.json` | Three-run flent manifest | ✅ VERIFIED | 3 runs, each with Spectrum egress, sample_count 151, series `TCP download sum`. |
| `throughput-verdict.json` | VALN-05a locked-rule verdict | ❌ FAILED | Internally consistent FAIL: `medians_above_532: 1`, `median_of_medians_mbps: 494.83422`. |
| `ab-comparison.json` | Six-delta A/B comparison | ❌ FAILED | Artifact exists and is substantive, but `comparison_verdict: fail`. |
| `safe05-diff.json` | SAFE-05 diff proof | ✅ VERIFIED | `protected_path_diffs: 0`, `diff_empty: true`, `verdict: pass`. |
| `196-VERIFICATION.md` | Cross-phase status update | ✅ VERIFIED | References Phase 198 as failed/blocked evidence and does not falsely close VALN-04/VALN-05a. |

### Key Link Verification

| From | To | Via | Status | Details |
|---|---|---|---|---|
| `preflight.json.deployment_proof.phase_197_ship_sha` | Phase 197 ship runtime | deploy/restart proof + health field + metric rows | ✅ WIRED | SHA `068b804` matches deployed commit; restart timestamp and Phase-197-specific `refractory_active`/metric evidence present. |
| `source-bind-egress-proof.json.pre_run_probes[]` | `throughput-verdict.json.runs[]` | One egress probe before each flent run | ✅ WIRED | All three probes and all verdict runs use `70.123.224.169` / `AS11427`. |
| `throughput-verdict.json.runs[].raw_path` | `flent/run{1,2,3}.flent.gz` | Manifest/verdict path references | ✅ WIRED | Raw files exist and parse as flent gzip JSON. |
| `ab-comparison.json.comparator.a_leg.manifest` | Phase 196 rtt-blend A-leg evidence | explicit path reference | ✅ WIRED | Path contains `196-spectrum-a-b-soak` and `rtt-blend`; no A-leg flent throughput baseline is used. |
| `ab-comparison.json.throughput` | `throughput-verdict.json` | copied verdict input | ✅ WIRED / FAILED INPUT | Copied throughput verdict is `FAIL`, so comparison correctly fails. |
| `safe05-diff.json.phase_197_ship_sha` | `safe05-baseline.json.phase_197_ship_sha` | Plan 01 baseline reference | ✅ WIRED | Both record `068b804`. |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|---|---|---|---|---|
| `primary-signal-audit-phase197.json` | raw active-primary samples | raw SQLite PSV `cake-primary-finish-...-sqlite-metrics.psv` | Yes, 71,801 raw samples | ⚠️ PARTIAL — real full-soak data, but not aligned to the later flent windows. |
| `throughput-verdict.json` | per-run medians | parsed `TCP download sum` series from three flent gzip captures | Yes | ✅ FLOWING — verdict fails because real data misses rule, not because data is hollow. |
| `ab-comparison.json` | deltas + throughput verdict | Phase 196 rtt-blend artifacts + Phase 198 audit/throughput artifacts | Yes | ✅ FLOWING — comparison fails from real inputs. |
| `safe05-diff.json` | protected-path diff count | git diff from `068b804..HEAD` over five protected files | Yes | ✅ FLOWING. |

### Behavioral Spot-Checks

| Behavior | Command / Predicate | Result | Status |
|---|---|---|---|
| Preflight deployment gate | `jq` over `preflight.json` for pass, SHA match, refractory field, recent metric count, Spectrum source bind | `pass`, `true`, `true`, `1166`, `true` | ✅ PASS |
| 24h duration gate | `jq -r '.duration_gate_passed, .elapsed_seconds' soak-window.json` | `true`, `88236` | ✅ PASS |
| Full-soak primary signal audit continuation gate | `jq` over `primary-signal-audit-phase197.json` | `pass_with_documented_exceptions`, `99.7493071127143`, `71801`, `180` | ⚠️ PARTIAL |
| Flent raw artifacts parse | Python gzip/json parse of `run1..3.flent.gz` | All 3 parse, 15 result series each | ✅ PASS |
| Throughput locked rule | `(.verdict == "PASS") == ((.medians_above_532 >= 2) and (.median_of_medians_mbps >= 532))` | Math internally consistent; result is `FAIL` | ❌ FAILING VERDICT |
| A/B comparison verdict | `jq -r '.comparison_verdict, .deltas...verdict, .throughput.verdict' ab-comparison.json` | `fail`, dwell fail, queue coverage fail, throughput FAIL | ❌ FAILING VERDICT |
| SAFE-05 source diff | `git diff --quiet 068b804..HEAD -- <5 protected files>` | exit 0 | ✅ PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|---|---|---|---|---|
| VALN-04 | 198-02, 198-04 | Spectrum cake-primary B-leg validation on Phase 197 build, A/B comparison artifact against accepted Phase 196 rtt-blend evidence. | ✗ BLOCKED / FAILED | `ab-comparison.json` exists and references the correct A-leg comparator, but `comparison_verdict: fail`; queue-primary coverage closeout gate and dwell-bypass delta fail, and throughput is FAIL. |
| VALN-05a | 198-03 | Spectrum DL `flent tcp_12down` acceptance: 2-of-3 medians ≥532 Mbps and median-of-medians ≥532 Mbps. | ✗ FAILED | `throughput-verdict.json`: medians `450.468331`, `681.802267`, `494.834220`; `medians_above_532=1`; `median_of_medians_mbps=494.834220`; `verdict=FAIL`. |
| SAFE-05 | 198-01, 198-04 | No protected state-machine/EWMA/dwell/deadband/threshold/burst changes. | ✓ SATISFIED | `safe05-baseline.json` and `safe05-diff.json`; direct git diff over five protected files returned exit 0. |

No orphaned Phase 198 requirement IDs were found beyond VALN-04, VALN-05a, and SAFE-05.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|---|---|---|---|---|
| n/a | n/a | Evidence-only artifacts; no production source modified. | ℹ️ Info | No TODO/FIXME/placeholder or hollow code issue applies. The blocking outcome is from real validation data. |

### Human Verification Required

None for this blocked closeout. The prior operator decision to close as blocked is already captured in Plan 04; no additional human test can turn the failed predicates into pass without new evidence.

### Gaps Summary

Phase 198 achieved evidence production but did **not** achieve the phase goal of closing VALN-04 and VALN-05a. SAFE-05 passed, and the 24h full-soak audit exists, but (1) per-run loaded-window queue-primary proof is missing, (2) the locked throughput rule failed, and (3) the A/B comparison verdict failed. The correct status is therefore `gaps_found` / blocked closeout, not passed.

---

_Verified: 2026-04-28T15:55:54Z_  
_Verifier: the agent (gsd-verifier)_
