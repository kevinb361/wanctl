---
phase: 226-baseline-capture-threshold-lock-snapshot-a
verified: 2026-06-04T12:04:27Z
status: gaps_found
score: 3/5 must-haves verified
overrides_applied: 0
gaps:
  - truth: "Operator captures baseline evidence on the current 920/18 besteffort wash with per-tin counters/drops/backlog/delay under load and machine-readable mean/spread summary."
    status: failed
    reason: "The raw tc evidence exists, but scripts/phase226-baseline-summary.py does not parse real CAKE per-tin rows (pkts/drops/backlog/av_delay/pk_delay), so baseline-summary.json reports zero packets/drops/backlog/delay for live loaded runs. This makes the committed baseline summary hollow."
    artifacts:
      - path: "scripts/phase226-baseline-summary.py"
        issue: "parse_tc_qdisc only recognizes synthetic Sent/Dropped/Backlog/Avge/Peak lines, not the real CAKE row labels present in live evidence."
      - path: "tests/phase226/test_tc_qdisc_parser.py"
        issue: "Tests pass because fixtures append synthetic helper lines; they do not catch real CAKE row parsing failure."
      - path: ".planning/phases/226-baseline-capture-threshold-lock-snapshot-a/evidence/baseline/baseline-20260604T113435Z/baseline-summary.json"
        issue: "Reports 0.0 deltas/spreads for spec-router/spec-modem despite live tc rows changing during load."
    missing:
      - "Teach parse_tc_qdisc to parse real CAKE rows: pkts, drops, backlog with units, av_delay, and pk_delay."
      - "Add a regression test using only real CAKE row labels, with no synthetic helper lines."
      - "Regenerate baseline-summary.json / BASELINE-SUMMARY.md from the existing retained raw tc evidence."
  - truth: "GATE-01 thresholds are fully locked before Phase 227, including a tin-separation noise-band constant derived from valid baseline tin_queue_delay_spread_ms data."
    status: failed
    reason: "phase226-thresholds.json is structurally present and pre-registered, but NOISE_BAND_MS.value is 0.0 because it was derived from the broken zero-valued baseline summary. The locked constant is therefore not valid evidence."
    artifacts:
      - path: "scripts/phase226-thresholds.json"
        issue: "TIN_SEPARATION.NOISE_BAND_MS.value is filled from baseline-summary.json sha256 186f4a72..., but that summary is invalid due to parser failure."
      - path: ".planning/phases/226-baseline-capture-threshold-lock-snapshot-a/GATE-01-THRESHOLDS.md"
        issue: "Provenance correctly points to the baseline summary, but the source summary must be regenerated before the constant can be trusted."
    missing:
      - "After fixing/regenerating the baseline summary, recompute NOISE_BAND_MS.value from the corrected tin_queue_delay_spread_ms values."
      - "Update derived_from sha256 and derived_at provenance in scripts/phase226-thresholds.json."
---

# Phase 226: Baseline Capture + Threshold Lock + Snapshot A Verification Report

**Phase Goal:** Establish a reversible, fully-instrumented starting line before any production CAKE-mode change: Snapshot A rollback anchor, baseline evidence set on current 920/18 besteffort wash, pre-registered GATE-01 thresholds, and no candidate deploy/controller-path mutation.
**Verified:** 2026-06-04T12:04:27Z
**Status:** gaps_found
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Snapshot A rollback anchor captured before any production change and restorable to the exact pre-A/B state within declared dry-run scope. | ✓ VERIFIED | `evidence/snapshot-a/MANIFEST.md` records captured UTC 2026-06-04T11:05:28Z, `config_equality: equal`, redacted repo/deployed spectrum YAML, qdisc/nft/health/git-ref artifacts, operator-private raw path, and bounded restore sequence. `restore-equivalence.json` records raw/repo/deployed SHA equality and manifest command identity. |
| 2 | Baseline evidence captured on current `920/18 besteffort wash` with per-tin counters/drops/backlog/delay under load, health/state, and RRUL/flent latency-under-load. | ✗ FAILED | Raw evidence exists for 3 runs and RRUL/health/reference artifacts exist, but the machine summary is hollow: live run-01 `tc` rows changed (`pkts` 1550865904 → 1551553525; `av_delay` 8us → 54us), while `baseline-summary.json` reports zero packet/backlog/drop/delay deltas and zero spread for both interfaces. |
| 3 | GATE-01 accept/rollback thresholds locked before candidate deploy and not reverse-fitted. | ✗ FAILED | `scripts/phase226-thresholds.json` exists and carries the right gate families, inherited values, and provenance, but `TIN_SEPARATION.NOISE_BAND_MS.value` is `0.0` derived from the invalid zero-valued baseline summary. The artifact is structurally locked but evidentially untrustworthy. |
| 4 | No candidate `diffserv4 wash` deploy occurs in Phase 226. | ✓ VERIFIED | Phase artifacts show baseline + anchor + thresholds + dry-run restore only. `restore-dry-run.txt` explicitly states proof text only; no live drill. Relevant file status showed no `configs/spectrum.yaml` source change. Phase 227 remains the candidate deploy phase in ROADMAP. |
| 5 | SAFE-13 verified at phase boundary: controller-path zero-diff vs v1.48 and ATT byte-identical. | ✓ VERIFIED | `safe13-boundary-check.json`: `passed=true`, `controller_path_diff_count=0`, `att_config_diff_count=0`, `dirty_tree_clean=true`, all protected file blob IDs equal vs `v1.48`. |

**Score:** 3/5 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|---|---|---|---|
| `scripts/phase226-snapshot-a.sh` | Read-only Snapshot A wrapper | ✓ VERIFIED | Exists; `bash -n` passed. Captures repo/deployed spectrum YAML, spec-router/spec-modem qdisc, bridge qos, git ref, health, and raw restore source split. |
| `evidence/snapshot-a/MANIFEST.md` | Redacted Snapshot A evidence + bounded restore sequence | ✓ VERIFIED | Contains equality verdict, source posture, artifact hashes, raw path marked operator-private/uncommitted, and Phase 228 rollback command text. |
| `scripts/phase226-baseline-capture.sh` | Read-only 3-run baseline capture wrapper | ⚠️ PARTIAL | Exists; `bash -n` passed. Captures expected raw artifacts. Advisory warnings remain for zero numeric validation, unconstrained SSH/iface args, and unfiltered health JSON, but retained default run is present. |
| `scripts/phase226-baseline-summary.py` | Parse real CAKE tc triples into DELTA/spread baseline summary | ✗ STUB/HOLLOW | Substantive file, but `parse_tc_qdisc()` misses real CAKE rows and returns zero counters/delays for committed live evidence. |
| `tests/phase226/test_tc_qdisc_parser.py` | Regression coverage for parser semantics | ⚠️ PARTIAL | `.venv/bin/pytest tests/phase226/test_tc_qdisc_parser.py -q` passes (4 tests), but fixtures include synthetic lines that mask real CAKE row parsing failure. |
| `evidence/baseline/baseline-20260604T113435Z/` | Retained baseline evidence set | ⚠️ PARTIAL | Raw per-run qdisc/health/flent/reference artifacts and manifest exist; generated baseline summary is invalid due to parser failure. |
| `scripts/phase226-thresholds.json` | Fully locked GATE-01 threshold JSON | ✗ HOLLOW | JSON validates and is schema-shaped, but tin-separation constant is derived from invalid zero baseline summary. |
| `GATE-01-THRESHOLDS.md` | Threshold provenance record | ✓ VERIFIED | Lists gate families, inherited/new provenance, JSON single source of truth, and constant-fill provenance without duplicating numeric threshold values. |
| `scripts/phase226-restore.sh` | Dry-run-only restore proof wrapper | ✓ VERIFIED | Exists; `bash -n` passed; no `--apply` option found; restore proof evidence records equality and command identity. |
| `evidence/restore-proof/restore-equivalence.json` | Restore equality + command identity proof | ✓ VERIFIED | JSON validates; raw/repo/deployed spectrum SHA values equal; apply command matches manifest. |
| `evidence/safe13-boundary-check.json` | SAFE-13 boundary proof | ✓ VERIFIED | JSON validates; all protected controller path and ATT checks pass. |

### Key Link Verification

| From | To | Via | Status | Details |
|---|---|---|---|---|
| Snapshot wrapper | Snapshot evidence manifest | `phase226-snapshot-a.sh` writes `MANIFEST.md` and required artifacts | WIRED | Manifest exists with hashes and raw restore path. |
| Snapshot manifest | Restore proof | `phase226-restore.sh` parses manifest apply command and compares printed command | WIRED | `APPLY_COMMAND_MATCHES_MANIFEST=true` in transcript and JSON. |
| Baseline capture wrapper | Summary helper | `scripts/phase226-baseline-summary.py --capture-dir "$CAPTURE_DIR"` | WIRED but HOLLOW | The helper is invoked, but its parser returns zeros against real evidence. |
| Baseline summary | Threshold noise-band constant | `NOISE_BAND_MS.derived_from.path` / sha256 | WIRED but HOLLOW | SHA matches current summary, but the source summary is invalid. |
| SAFE-13 boundary script | Boundary JSON | `phase225-safe13-boundary-check.sh --anchor v1.48 --out ...` | WIRED | JSON evidence shows pass. |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|---|---|---|---|---|
| `phase226-baseline-summary.py` | `packets_delta`, `drops_delta`, `backlog_bytes_delta`, `avg_delay_ms`, `tin_queue_delay_spread_ms` | Raw `tc-qdisc-*.{before,during,after}.txt` | No — parser ignores real row labels and emits zeros | ✗ HOLLOW |
| `baseline-summary.json` | `baseline_window` | `health.window.ndjson` | Yes — sample counts, max gaps, restart/transition/floor/SOFT_RED fields populated | ✓ FLOWING |
| `phase226-thresholds.json` | `TIN_SEPARATION.NOISE_BAND_MS.value` | `baseline-summary.json` `tin_queue_delay_spread_ms` | No — source is invalid zero summary | ✗ HOLLOW |
| `restore-equivalence.json` | `restore_equivalence`, command match | Raw restore source + repo/deployed SHA + manifest parse | Yes | ✓ FLOWING |
| `safe13-boundary-check.json` | `passed`, diff counts, per-file equality | Git blob/diff checks vs v1.48 | Yes | ✓ FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|---|---|---|---|
| Phase 226 shell scripts parse | `bash -n scripts/phase226-snapshot-a.sh && bash -n scripts/phase226-baseline-capture.sh && bash -n scripts/phase226-restore.sh` | exit 0 | ✓ PASS |
| Python/JSON artifacts validate | `python3 -m py_compile scripts/phase226-baseline-summary.py && python3 -m json.tool ...` | exit 0 | ✓ PASS |
| Parser fixture tests pass | `.venv/bin/pytest tests/phase226/test_tc_qdisc_parser.py -q` | `4 passed` | ✓ PASS (but insufficient) |
| Parser against live qdisc evidence | import parser and parse run-01 spec-router before | `TinCounters(... packets=0, drops=0, backlog_bytes=0, avg_delay_ms=0.0...)` despite real rows | ✗ FAIL |
| Threshold provenance sha matches summary | `sha256sum baseline-summary.json` | `186f4a72...` matches `derived_from.sha256` | ✓ PASS (link valid, source invalid) |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|---|---|---|---|---|
| AB-01 | 226-02, 226-04 | Snapshot A rollback anchor before production change, with bounded restore proof | ✓ SATISFIED | Snapshot manifest and restore-equivalence JSON prove config-artifact equality and command identity; dry-run-only scope is explicit. |
| AB-02 | 226-01 | Baseline evidence on current `920/18 besteffort wash` including qdisc counters/drops/backlog/delay, health/state, RRUL/flent | ✗ BLOCKED | Raw capture exists, but summary parser fails on real CAKE rows, causing zero deltas/spreads. Operator does not yet have a trustworthy baseline summary. |
| GATE-01 | 226-03 | Pre-registered accept/rollback thresholds before candidate deploy | ✗ BLOCKED | JSON/provenance exist, but tin-separation noise-band constant is derived from invalid baseline data. |
| SAFE-13 | 226-01/02/03/04 | Controller-path zero-diff vs v1.48 and ATT byte-identical | ✓ SATISFIED | Boundary JSON passed with zero controller/ATT diffs and all protected hashes equal. |

No orphaned Phase 226 requirement IDs found in `.planning/REQUIREMENTS.md`: AB-01, AB-02, GATE-01, and SAFE-13 are all accounted for in plan frontmatter and this verification.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|---|---:|---|---|---|
| `scripts/phase226-baseline-summary.py` | 24-80 | Parser recognizes synthetic `Sent`/`Dropped`/`Backlog`/`Avge`/`Peak` lines only | 🛑 Blocker | Live CAKE `pkts`/`drops`/`backlog`/`av_delay`/`pk_delay` rows are ignored, invalidating baseline summary and threshold constant. |
| `tests/phase226/test_tc_qdisc_parser.py` | 20-31 | Test fixture masks real-format parser gap | 🛑 Blocker | Passing tests do not verify the committed live evidence shape. |
| `scripts/phase226-baseline-capture.sh` | 191-193 | Allows zero for positive integer options | ⚠️ Warning | Advisory debt; retained run used default positive values, so not the current goal blocker. |
| `scripts/phase226-baseline-capture.sh`, `scripts/phase226-snapshot-a.sh`, `scripts/phase226-restore.sh` | multiple | User-controlled SSH/iface params not strictly allowlisted | ⚠️ Warning | Advisory production-safety hardening; no evidence it invalidated retained artifacts. |
| `scripts/phase226-snapshot-a.sh`, `scripts/phase226-baseline-capture.sh` | health writes | Health evidence labeled redacted/unredacted inconsistently and not recursively filtered | ⚠️ Warning | Future leak risk; current required secret scans/JSON validation did not show a blocking leak. |

### Human Verification Required

None. The blocking failures are static/data-flow verifiable from committed code and artifacts.

### Gaps Summary

Phase 226 achieved the Snapshot A anchor, dry-run restore proof, no-candidate-deploy boundary, and SAFE-13 boundary proof. It did **not** fully achieve the baseline/threshold goal because the committed baseline summary is generated by a parser that cannot read the real CAKE per-tin rows in the retained evidence. That same invalid zero summary feeds the GATE-01 tin-separation noise-band constant, so the threshold artifact is present but not trustworthy.

Fix path: update the parser/tests, regenerate the baseline summary from existing raw evidence, then recompute and re-provenance `TIN_SEPARATION.NOISE_BAND_MS.value` before Phase 227.

---

_Verified: 2026-06-04T12:04:27Z_
_Verifier: the agent (gsd-verifier)_
