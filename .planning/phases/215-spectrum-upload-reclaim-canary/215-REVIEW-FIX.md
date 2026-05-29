---
phase: 215-spectrum-upload-reclaim-canary
fixed_at: 2026-05-29T16:02:10Z
review_path: .planning/phases/215-spectrum-upload-reclaim-canary/215-REVIEW.md
iteration: 1
findings_in_scope: 4
fixed: 4
skipped: 0
status: all_fixed
---

# Phase 215: Code Review Fix Report

**Fixed at:** 2026-05-29T16:02:10Z
**Source review:** .planning/phases/215-spectrum-upload-reclaim-canary/215-REVIEW.md
**Iteration:** 1

**Summary:**
- Findings in scope: 4
- Fixed: 4
- Skipped: 0

## Fixed Issues

### WR-01: Non-finite metrics can bypass rollback gates

**Files modified:** `scripts/phase215-reclaim-gate.sh`, `tests/test_phase215_reclaim_gate.py`
**Commit:** 85303be
**Applied fix:** Added finite required-metric parsing for baseline and candidate extract metrics so NaN/Infinity values produce a void verdict before scoring, with regression coverage for non-finite candidate p95, p99, and upload median values.

### WR-02: Extractor accepts non-finite raw values instead of failing closed

**Files modified:** `scripts/phase214-extract.py`, `tests/test_phase215_extract_upload.py`
**Commit:** 4c1427a
**Applied fix:** Centralized extractor numeric conversion through a finite-float helper and made non-finite throughput or ping samples raise `FlentExtractionError`, with regression coverage for NaN/Infinity upload and latency samples.

### WR-03: Parse-error verdict may still be written outside the requested output directory

**Files modified:** `scripts/phase215-reclaim-gate.sh`, `tests/test_phase215_reclaim_gate.py`
**Commit:** 1b2df34
**Applied fix:** Pre-scanned arguments for a valid `--output-dir` before normal parsing so early parse aborts write the verdict to the requested directory, with regression coverage for an unknown argument before `--output-dir`.

### WR-04: Remote YAML host argument can be interpreted as SSH options

**Files modified:** `scripts/phase215-reclaim-gate.sh`, `tests/test_phase215_reclaim_gate.py`
**Commit:** c985db7
**Applied fix:** Rejected unsafe or option-style remote YAML host tokens before invoking SSH, added `ssh --` option termination, and covered option-shaped hosts with a regression test.

---

_Fixed: 2026-05-29T16:02:10Z_
_Fixer: the agent (gsd-code-fixer)_
_Iteration: 1_
