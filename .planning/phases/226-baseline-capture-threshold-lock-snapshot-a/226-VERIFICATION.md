---
phase: 226-baseline-capture-threshold-lock-snapshot-a
verified: 2026-06-04T13:02:34Z
status: passed
score: 5/5 must-haves verified
overrides_applied: 0
re_verification:
  previous_status: resolved_prior_gap_report
  previous_score: 3/5
  closed_items:
    - "AB-02 baseline summary is no longer hollow: parse_tc_qdisc now reads real CAKE pkts/drops/backlog/av_delay/pk_delay rows, real-format regression tests pass, and regenerated baseline-summary.json reports non-zero retained-evidence deltas/spreads."
    - "GATE-01 NOISE_BAND_MS is no longer zero/stale: value is 24.206, derived_from.sha256 matches the regenerated baseline-summary.json and artifact-sha256.txt, and derived_at was refreshed."
  remaining_blockers: []
  regressions: []
---

# Phase 226: Baseline Capture + Threshold Lock + Snapshot A Verification Report

**Phase Goal:** Operator can establish a reversible, fully-instrumented starting line before any production CAKE-mode change: a Snapshot A rollback anchor capturing Spectrum config + production CAKE/qdisc state, a complete baseline evidence set on the current `920/18 besteffort wash`, and a pre-registered set of GATE-01 accept/rollback thresholds locked at plan time. No candidate deploy in this phase; SAFE-13 boundary must hold.
**Verified:** 2026-06-04T13:02:34Z
**Status:** passed
**Re-verification:** Yes — after 226-05 gap closure

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Operator captures a Snapshot A rollback anchor before any production change, restorable to the exact pre-A/B state within declared dry-run scope. | ✓ VERIFIED | `evidence/snapshot-a/MANIFEST.md` records captured UTC `2026-06-04T11:05:28Z`, read-only source posture, repo/deployed Spectrum evidence, qdisc/nft/health/git-ref artifacts, operator-private raw restore source, `verdict: equal`, and the Phase 228 restore command. `restore-equivalence.json` records raw/repo/deployed SHA equality and command identity. |
| 2 | Operator captures baseline evidence on current `920/18 besteffort wash`: `tc -s qdisc` on spec-router/spec-modem, per-tin counters/drops/backlog/delay under load, Spectrum health/state, and RRUL/flent latency-under-load. | ✓ VERIFIED | Retained `baseline-20260604T113435Z/` manifest records valid/retained 3x60s baseline. Raw run directories contain before/during/after qdisc triples, health NDJSON, RRUL flent artifacts, and reference-flow artifacts. Regenerated `baseline-summary.json` now reports non-zero live deltas/spreads: spec-modem Tin 0 `mean_packets_delta=168844`, `mean_drops_delta=21.667`, `mean_backlog_bytes_delta=30679.333`, `tin_queue_delay_spread_ms=24.206`; spec-router Tin 0 `mean_packets_delta=686159.333`, `tin_queue_delay_spread_ms=0.105`. |
| 3 | GATE-01 accept/rollback thresholds are pre-registered and locked before candidate deploy, including valid tin-separation noise band provenance. | ✓ VERIFIED | `scripts/phase226-thresholds.json` is valid JSON with inherited RRUL/restart/transition gates, UL_STABILITY, TIN_SEPARATION arms, and `NOISE_BAND_MS.value=24.206`. Its `derived_from.sha256=76570cc55e...` equals the regenerated summary hash and the manifest entry; `derived_at=2026-06-04T12:49:08Z`. `GATE-01-THRESHOLDS.md` preserves JSON single-source discipline. |
| 4 | No candidate `diffserv4 wash` deploy occurs in Phase 226. | ✓ VERIFIED | Phase artifacts are Snapshot A + baseline + thresholds + dry-run restore + SAFE-13 evidence only. Phase 227 remains the candidate deploy phase in ROADMAP. Restore script has no `--apply` path; shell syntax checks passed. |
| 5 | SAFE-13 holds at phase boundary: controller-path zero-diff vs v1.48 and ATT byte-identical. | ✓ VERIFIED | `safe13-boundary-check.json` has `passed=true`, `controller_path_diff_count=0`, `att_config_diff_count=0`, `dirty_tree_clean=true`, and equal blob IDs for protected controller files plus `configs/att.yaml`. |

**Score:** 5/5 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|---|---|---|---|
| `scripts/phase226-snapshot-a.sh` | Read-only Snapshot A capture wrapper | ✓ VERIFIED | Exists; `bash -n` passed. Evidence manifest shows Spectrum config/qdisc/nft/health/git-ref capture and raw restore split. |
| `evidence/snapshot-a/MANIFEST.md` | Snapshot A redacted evidence and restore command | ✓ VERIFIED | Records read-only posture, equality, raw operator-private path, and bounded restore sequence. |
| `scripts/phase226-baseline-capture.sh` | Read-only 3-run baseline capture wrapper | ✓ VERIFIED with advisory warnings | Exists; `bash -n` passed. Retained evidence set exists. Advisory review warnings remain for DSCP proof hardcoding, zero numeric validation, SSH/interface allowlisting, health redaction/equality labeling, and floor-hit semantics; none invalidate Phase 226 success criteria after parser/summary closure. |
| `scripts/phase226-baseline-summary.py` | Real CAKE per-tin parser and derived summary builder | ✓ VERIFIED | `py_compile` passed. `parse_tc_qdisc` includes real row regexes for `pkts`, `drops`, `backlog`, `av_delay`, and `pk_delay`; parsing retained run-01 gives non-zero packets/drops/delay for spec-router and non-zero backlog/peak delay for spec-modem. |
| `tests/phase226/test_tc_qdisc_parser.py` | Real-format regression coverage | ✓ VERIFIED | `.venv/bin/pytest tests/phase226/ -q` passed with 7 tests. Tests include real bare CAKE labels without synthetic helper lines and retained evidence assertions. |
| `baseline-summary.json` / `BASELINE-SUMMARY.md` | Regenerated baseline summary | ✓ VERIFIED | JSON/Markdown show non-zero per-tin deltas/spreads. Summary hash is `76570cc55ebd9b7960e6318ad0a7d54bf90988ed642438f7486dab1138f83754`. |
| `artifact-sha256.txt` | Refreshed retained-evidence hash manifest | ✓ VERIFIED | `sha256sum -c .../artifact-sha256.txt` passed for all retained baseline files; entries for regenerated JSON/Markdown match current bytes. |
| `scripts/phase226-thresholds.json` | Fully locked GATE-01 threshold JSON | ✓ VERIFIED | Valid JSON; `NOISE_BAND_MS.value=24.206`; provenance hash matches final summary. |
| `GATE-01-THRESHOLDS.md` | Threshold provenance record | ✓ VERIFIED | Points to JSON as single source, contains Constant Fill provenance, and does not duplicate gate-value literals. |
| `scripts/phase226-restore.sh` / `evidence/restore-proof/` | Dry-run-only restore proof | ✓ VERIFIED | `bash -n` passed; no `--apply` flag. Restore proof records equality and command match. |
| `evidence/safe13-boundary-check.json` | SAFE-13 proof | ✓ VERIFIED | JSON validates and reports zero controller/ATT diff. |

### Key Link Verification

| From | To | Via | Status | Details |
|---|---|---|---|---|
| Snapshot wrapper | Snapshot manifest/evidence | capture script artifacts and manifest | WIRED | Manifest and evidence tree exist with required artifacts. |
| Snapshot manifest | Restore proof | manifest apply-command parsed by restore wrapper | WIRED | Restore proof shows raw/repo/deployed equality and command identity. |
| Baseline capture wrapper | Summary helper | `phase226-baseline-summary.py --capture-dir` | WIRED | Retained evidence has generated JSON/Markdown from raw qdisc/health/flent artifacts. |
| Summary parser | Real retained CAKE rows | regexes for `pkts`/`drops`/`backlog`/`av_delay`/`pk_delay` | WIRED | Spot-check parser returned `TinCounters(... packets=1551553525, drops=657899, avg_delay_ms=0.054, peak_delay_ms=0.131)` for router and modem backlog `1844`. |
| Baseline summary | Threshold noise band | `NOISE_BAND_MS.derived_from.sha256` | WIRED | Threshold hash equals regenerated summary SHA and manifest entry. |
| SAFE-13 script | Boundary JSON | `phase225-safe13-boundary-check.sh --anchor v1.48` | WIRED | JSON proof passes. |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|---|---|---|---|---|
| `phase226-baseline-summary.py` | `packets_delta`, `drops_delta`, `backlog_bytes_delta`, `avg_delay_ms`, `peak_delay_ms`, `tin_queue_delay_spread_ms` | Raw `tc-qdisc-*.{before,during,after}.txt` | Yes | ✓ FLOWING — real retained rows parse to non-zero counters/delays; summary reflects non-zero deltas/spreads. |
| `baseline-summary.json` | `baseline_window`, RRUL headline | `health.window.ndjson` and flent gz files | Yes | ✓ FLOWING — window samples, rates/counts, and p99 mean populated. |
| `phase226-thresholds.json` | `TIN_SEPARATION.NOISE_BAND_MS.value` | regenerated `baseline-summary.json` | Yes | ✓ FLOWING — `24.206` equals max retained spread and hash provenance matches final summary bytes. |
| `restore-equivalence.json` | equality verdict and command match | Snapshot raw/repo/deployed config hashes + manifest command | Yes | ✓ FLOWING. |
| `safe13-boundary-check.json` | pass/fail and protected file equality | git blob/diff checks vs `v1.48` | Yes | ✓ FLOWING. |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|---|---|---|---|
| Real-format parser regression suite | `.venv/bin/pytest tests/phase226/ -q` | `7 passed in 0.08s` | ✓ PASS |
| Python and JSON artifacts validate | `py_compile` + `python3 -m json.tool` on summary/threshold/SAFE artifacts | exit 0 | ✓ PASS |
| Parser against retained real evidence | import helper and parse run-01 qdisc files | router non-zero packets/drops/delay; modem backlog `1844`, peak `3.78` | ✓ PASS |
| Baseline summary + threshold provenance | Python hash/spread check | spreads `{spec-modem: 24.206, spec-router: 0.105}`, threshold value `24.206`, SHA matched | ✓ PASS |
| Evidence hash manifest | `sha256sum -c .../artifact-sha256.txt` | all entries OK | ✓ PASS |
| SAFE-13 boundary | JSON assertion on pass/diff counts | `SAFE-13 OK 2026-06-04T12:49:52Z` | ✓ PASS |
| Phase shell scripts syntax / dry-run-only restore | `bash -n ... && ! grep -- '--apply' scripts/phase226-restore.sh` | exit 0 | ✓ PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|---|---|---|---|---|
| AB-01 | 226-02, 226-04 | Snapshot A rollback anchor and bounded restore proof | ✓ SATISFIED | Snapshot manifest, redacted evidence, operator-private raw path, restore-equivalence JSON, and dry-run command identity proof exist. |
| AB-02 | 226-01, 226-05 | Baseline evidence on current `920/18 besteffort wash` with qdisc counters/drops/backlog/delay, health/state, RRUL/flent | ✓ SATISFIED | Retained baseline tree is valid/retained; regenerated summary parses real CAKE rows and reports non-zero deltas/spreads; manifest/hash check passes. |
| GATE-01 | 226-03, 226-05 | Pre-registered accept/rollback thresholds before candidate deploy | ✓ SATISFIED | Threshold JSON is valid and fully locked, with `NOISE_BAND_MS.value=24.206` hash-provenanced to the final regenerated baseline summary. |
| SAFE-13 | 226-01/02/03/04/05 | Controller-path zero-diff vs v1.48 and ATT byte-identical | ✓ SATISFIED | SAFE-13 JSON passed with zero controller/ATT diffs and equal protected file blob IDs. |

No orphaned Phase 226 requirement IDs found in `.planning/REQUIREMENTS.md`: AB-01, AB-02, GATE-01, and SAFE-13 are all accounted for by plan frontmatter and verification evidence.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|---|---:|---|---|---|
| `scripts/phase226-baseline-capture.sh` | review WR-01 | DSCP neutrality proof is recorded as fixed `0` rather than observed packet parsing | ⚠️ Warning | Advisory evidence-hardening issue for future matched captures; Phase 226 roadmap success does not require DSCP proof as an AB-02 blocker. |
| `scripts/phase226-baseline-summary.py` | 202-204 | Health `floor_hit_cycles` summed across samples | ⚠️ Warning | Advisory gate-eval semantics risk. Does not reopen prior parser/NOISE_BAND_MS gap; baseline health fields are present and SAFE-13/AB-02 evidence exists. |
| `scripts/phase226-baseline-capture.sh` | 191-193 | Numeric validation accepts zero | ⚠️ Warning | Retained run used valid defaults; not a current retained-evidence blocker. |
| phase shell scripts | review WR-04/WR-05/WR-06 | SSH/interface allowlisting, recursive health redaction, and redacted config equality labeling | ⚠️ Warning | Production-safety/documentation hardening noted by advisory review; no Phase 226 success criterion is broken. |
| `.planning/ROADMAP.md`, `.planning/STATE.md` | Plan 226-05 scope check | Added by committed metadata after gap-closure base | ℹ️ Info | Not controller-path/ATT and not a SAFE-13 violation; noted because a literal `git diff --name-only v1.48` allowlist is too broad for this repository history. |

### Human Verification Required

None. This phase's success criteria are evidence/tooling/provenance checks verifiable from committed artifacts without live mutation. No visual, realtime, or external-service behavior remains uncertain for Phase 226 closeout.

### Gaps Summary

No blocking gaps remain. The previous AB-02/GATE-01 failures are closed by real CAKE per-tin row parsing, real-format tests, regenerated retained baseline summaries, refreshed evidence hashes, re-provenanced positive `NOISE_BAND_MS`, and refreshed SAFE-13 evidence. Advisory code-review warnings remain, but they do not break Phase 226's roadmap success criteria.

---

_Verified: 2026-06-04T13:02:34Z_
_Verifier: the agent (gsd-verifier)_
