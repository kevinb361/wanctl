---
phase: 227-candidate-diffserv4-wash-deploy-matched-capture
verified: 2026-06-04T16:58:01Z
status: passed
score: 16/16 must-haves verified
overrides_applied: 0
gaps: []
human_verification: []
---

# Phase 227: Candidate diffserv4-wash Deploy + Matched Capture Verification Report

**Phase Goal:** Operator can deploy candidate `diffserv4 wash` (download + upload) on Spectrum only under the Snapshot A anchor and capture the identical evidence set under matched load, plus a realtime-flow protection comparison, so the verdict in Phase 228 has a direct apples-to-apples baseline-vs-candidate dataset.
**Verified:** 2026-06-04T16:58:01Z
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Candidate `diffserv4 wash` is deployed on Spectrum only, with `allow_wash:true`, DL920/UL18/docsis unchanged and ATT untouched. | ✓ VERIFIED | `configs/spectrum.yaml` has `diffserv: diffserv4`, `allow_wash: true`, `ceiling_mbps: 920/18`; `SAFE-13-BOUNDARY.json` has `att_config_diff_count: 0`. |
| 2 | Live candidate qdisc was verified as `diffserv4` on both `spec-router` and `spec-modem` before capture. | ✓ VERIFIED | `evidence/qdisc-verify-candidate.json`: `expected_mode=diffserv4`, `router_got=diffserv4`, `modem_got=diffserv4`, `match=true`. |
| 3 | Candidate capture contains the identical evidence class as Phase 226 under matched load. | ✓ VERIFIED | `candidate-20260604T163152Z` has 3 run dirs with flent RRUL, health before/window/after, before/during/after qdisc for both interfaces, unmarked UDP/TCP iperf, marked-EF iperf, and summary artifacts. |
| 4 | Candidate qdisc evidence is actually `diffserv4 wash` during the run, not only summarized as such. | ✓ VERIFIED | Spot-check over all 18 candidate qdisc proof files found `qdisc cake`, `diffserv4`, and `wash` in every before/during/after proof. |
| 5 | Realtime-flow protection comparison data exists: marked EF UDP vs unmarked UDP plus unmarked TCP. | ✓ VERIFIED | Candidate and baseline summaries contain `marked_ef`, `ref_udp_unmarked`, and `ref_tcp_unmarked` blocks with jitter/loss/throughput metrics. |
| 6 | Marked-EF arm is additive and default-off; matched RRUL/unmarked arms are preserved. | ✓ VERIFIED | Harness has `--marked-ef` flag, dry-run/default gating, unchanged RRUL/unmarked flow invocations, and focused tests passed. |
| 7 | Marked-EF UDP uses a distinct reflector port and does not collide with unmarked UDP/TCP. | ✓ VERIFIED | Harness rejects EF port equal to REF_PORT; candidate manifest uses `ref_port=5201`, `tcp_ref_port=5202`, `ef_ref_port=5203`. |
| 8 | Iperf success is validated as parseable JSON with expected summary blocks, not merely non-empty files. | ✓ VERIFIED | Harness/summary validity guards present; candidate `iperf-validity.*.txt` files record all unmarked UDP/TCP and marked-EF flows valid=true/reason=ok. |
| 9 | EF marking method and cleanliness are recorded, with degrade-to-best-effort fallback available. | ✓ VERIFIED | Harness records `EF_MARK_METHOD`, `EF_CLEAN_MARK`, `EF_REF_PORT`; candidate per-run records show `EF_MARK_METHOD=dscp`, `EF_CLEAN_MARK=true`, `EF_REF_PORT=5203`. |
| 10 | Summary generator emits AB-04/GATE-01 fields while preserving diffable shape. | ✓ VERIFIED | `baseline-summary.json` for baseline and candidate share stable top-level keys and include `baseline_window`, `rrul_p99_latency_under_load_ms_mean`, `ref_udp_unmarked`, `ref_tcp_unmarked`, `marked_ef`. |
| 11 | A read-only qdisc gate exists and fails closed on mismatch/missing/ambiguous/ssh failure states. | ✓ VERIFIED | `scripts/phase227-qdisc-verify.sh` uses bounded SSH, strict `qdisc cake` line parsing, explicit proof states; focused qdisc tests passed. |
| 12 | Candidate capture sequence uses standard deploy path, qdisc gate, health/restart checks, and leaves diffserv4 live for Phase 228. | ✓ VERIFIED | `phase227-capture-runbook.sh` references `scripts/deploy.sh spectrum`, `phase227-qdisc-verify.sh`, health URL `10.10.110.223:9101`, NRestarts checks; summary/evidence record leave-live state. |
| 13 | A genuine mutation-capable Snapshot A rollback exists and is operator-gated. | ✓ VERIFIED | `phase227-rollback.sh` refuses mutation without `--confirm`, applies Snapshot A besteffort bytes, deploys, restarts, verifies besteffort, health, and proof output. |
| 14 | SAFE-13 hole is closed: `wan_controller_state.py` is protected. | ✓ VERIFIED | Boundary script includes `src/wanctl/wan_controller_state.py`; proof JSON includes it in `expanded_protected_files`; test passed. |
| 15 | SAFE-13 phase-boundary invariant holds: controller path zero-diff vs v1.48 and ATT byte-identical. | ✓ VERIFIED | `SAFE-13-BOUNDARY.json`: `passed=true`, `controller_path_diff_count=0`, `att_config_diff_count=0`, protected file blob IDs equal. |
| 16 | Candidate evidence is complete enough for Phase 228 GATE-01 verdict computation. | ✓ VERIFIED | `phase227-evidence-completeness.py` on real candidate+baseline summaries/run tree returned `verdict-ready`; focused test suite returned 25 passed. |

**Score:** 16/16 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|---|---|---|---|
| `scripts/phase226-baseline-capture.sh` | Additive marked-EF arm, validity records, manifest provenance. | ✓ VERIFIED | gsd artifact check passed; grep confirms `--marked-ef`, `--ef-ref-port`, `--dscp ef`, `--tos 184`, validity checks. |
| `scripts/phase226-baseline-summary.py` | Parse unmarked UDP/TCP + marked-EF iperf JSON. | ✓ VERIFIED | Emits `ref_udp_unmarked`, `ref_tcp_unmarked`, `marked_ef`; validity handling present. |
| `scripts/phase227-qdisc-verify.sh` | Read-only fail-closed qdisc mode gate. | ✓ VERIFIED | Bounded SSH, strict mode parsing, JSON proof output. |
| `configs/spectrum.yaml` | Candidate one-line diffserv4 flip; allow_wash unchanged. | ✓ VERIFIED | `diffserv: diffserv4`, `allow_wash: true`. |
| `scripts/phase227-capture-runbook.sh` | Ordered baseline→flip→verify→candidate runbook with rollback abort. | ✓ VERIFIED | Calls qdisc gate, capture harness with `--marked-ef`, health/restart guards, rollback script. |
| `scripts/phase227-rollback.sh` | Mutation-capable D-09 rollback, gated by `--confirm`. | ✓ VERIFIED | Standard deploy path and post-rollback qdisc/health proof logic present. |
| `scripts/phase225-safe13-boundary-check.sh` | Protected list includes `wan_controller_state.py`. | ✓ VERIFIED | Protected target present; proof JSON confirms expansion. |
| `scripts/phase227-evidence-completeness.py` | GATE-01 readiness checker. | ✓ VERIFIED | Real evidence returned verdict-ready; tests cover missing/invalid evidence. |
| `evidence/SAFE-13-BOUNDARY.json` | Phase boundary SAFE-13 proof. | ✓ VERIFIED | `passed=true`, zero controller/ATT diff. |
| `evidence/qdisc-verify-candidate.json` | Candidate live qdisc proof. | ✓ VERIFIED | Both interfaces `diffserv4`, match true. |
| `evidence/baseline-20260604T154929Z/` | Fresh besteffort+EF matched baseline. | ✓ VERIFIED | Summary has run_count=3 and marked/unmarked metrics. |
| `evidence/candidate-20260604T163152Z/` | Candidate diffserv4+EF matched capture. | ✓ VERIFIED | Summary/run tree complete and verdict-ready. |

### Key Link Verification

| From | To | Via | Status | Details |
|---|---|---|---|---|
| `phase226-baseline-capture.sh` | `iperf3` | `--dscp ef`, fallback `--tos 184`, then best-effort fallback. | ✓ WIRED | Link check passed; source contains all paths. |
| `phase226-baseline-summary.py` | capture artifacts | Reads `ref-udp-unmarked`, `ref-tcp-bulk-unmarked`, `ref-udp-marked-ef`, `ref-ef-marking`. | ✓ WIRED | Summary parses emitted artifacts. |
| `phase227-qdisc-verify.sh` | `cake-shaper` | SSH `sudo -n tc -s qdisc show dev <iface>`. | ✓ WIRED | Link check passed; bounded timeout present. |
| `phase227-capture-runbook.sh` | `scripts/deploy.sh` | Standard `deploy.sh spectrum ${SSH_HOST}` instruction. | ✓ WIRED | Link check passed. |
| `phase227-capture-runbook.sh` | qdisc gate | `--expected-mode diffserv4` before candidate. | ✓ WIRED | Link check passed. |
| `phase227-capture-runbook.sh` | capture harness | Builds args with `--marked-ef`, then invokes `scripts/phase226-baseline-capture.sh "${args[@]}"`. | ✓ WIRED | Manual check corrects gsd literal-pattern false negative. |
| `phase227-rollback.sh` | deploy/qdisc gate | Reapply besteffort, deploy, restart, verify besteffort. | ✓ WIRED | Link check passed. |
| `phase227-evidence-completeness.py` | `scripts/phase226-thresholds.json` | Required `--thresholds` CLI; validates locked GATE-01 threshold keys. | ✓ WIRED | Manual check corrects gsd literal-pattern false negative. |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|---|---|---|---|---|
| `phase226-baseline-summary.py` | `ref_udp_unmarked`, `ref_tcp_unmarked`, `marked_ef` | Per-run iperf JSON + `ref-ef-marking.*.txt` | Yes | ✓ FLOWING — real baseline/candidate summary metrics populated with run_count=3. |
| `phase227-evidence-completeness.py` | GATE-01 readiness fields | Candidate summary, baseline summary, candidate run tree, thresholds JSON | Yes | ✓ FLOWING — real command returned `verdict-ready`. |
| `SAFE-13-BOUNDARY.json` | controller/ATT diff counts | `phase225-safe13-boundary-check.sh --anchor v1.48` | Yes | ✓ FLOWING — per-file object IDs equal, counts zero. |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|---|---|---|---|
| Focused Phase 227 regression suite | `.venv/bin/pytest tests/test_phase227_marked_ef.py tests/test_phase227_qdisc_verify.py tests/test_phase227_safe13_boundary.py tests/test_phase227_evidence_completeness.py -q` | `25 passed in 1.44s` | ✓ PASS |
| Real candidate evidence is verdict-ready | `python3 scripts/phase227-evidence-completeness.py --candidate-summary ...candidate... --baseline-summary ...baseline... --thresholds scripts/phase226-thresholds.json --run-tree ...candidate...` | `verdict-ready: required GATE-01 signals present and successful` | ✓ PASS |
| Candidate qdisc files prove diffserv4 wash | Python scan over 18 candidate `tc-qdisc-*` files | `qdisc_files=18 bad=0` | ✓ PASS |
| Candidate iperf validity + EF marking records | Python scan over 3 validity and 3 marking records | `validity_files=3 mark_files=3 bad=0` | ✓ PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|---|---|---|---|---|
| AB-03 | 227-02, 227-03, 227-04 | Deploy candidate `diffserv4 wash` on Spectrum and capture identical evidence under matched load. | ✓ SATISFIED | Config flip, qdisc proof, candidate run tree, completeness gate, rollback/runbook artifacts. |
| AB-04 | 227-01, 227-03 | Compare realtime-flow protection: marked EF UDP vs unmarked UDP plus unmarked TCP. | ✓ SATISFIED | Baseline/candidate summaries contain valid `marked_ef`, `ref_udp_unmarked`, `ref_tcp_unmarked` metrics. |
| SAFE-13 | 227-04 (cross-phase invariant) | Controller path zero-diff vs v1.48 and ATT byte-identical. | ✓ SATISFIED | `SAFE-13-BOUNDARY.json` passed with zero counts; `wan_controller_state.py` included. |

No orphaned Phase 227 requirements found: `.planning/REQUIREMENTS.md` maps AB-03, AB-04, and SAFE-13 to Phase 227, all accounted for in plan frontmatter and evidence.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|---|---:|---|---|---|
| `scripts/phase226-baseline-summary.py` | 354/359/365 | `return None` | ℹ️ Info | Legitimate optional parsing fallback, not a stub. |
| `scripts/phase225-safe13-boundary-check.sh` | 170/179 | `return None` | ℹ️ Info | Legitimate helper return, not a stub. |
| `227-REVIEW.md` | WR-01..WR-03 | Advisory review warnings | ⚠️ Warning | Not goal-blocking: WR-01 mitigated by manual qdisc diffserv4/wash evidence scan; WR-02 is about non-default interface portability, not this Spectrum evidence; WR-03 is test-reliability advice, while focused tests currently pass. |

### Human Verification Required

None. The production mutation checkpoint was already completed and represented by committed qdisc/health/evidence artifacts; this verification checked committed evidence rather than performing live network mutation.

### Gaps Summary

No blocking gaps found. Phase 227 achieved its goal: candidate `diffserv4 wash` is deployed/evidenced, baseline and candidate matched captures contain the AB-04 comparison fields, SAFE-13 holds, and Phase 228 has a verdict-ready dataset.

---

_Verified: 2026-06-04T16:58:01Z_
_Verifier: the agent (gsd-verifier)_
