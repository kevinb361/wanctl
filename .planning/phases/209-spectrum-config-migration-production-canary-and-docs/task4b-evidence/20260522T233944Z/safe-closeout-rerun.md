---
phase: 209
plan: 209-04
task: 4b
timestamp_utc: 20260522T233944Z
status: passed
---

# SAFE Closeout Rerun

## Context

The first Task 4b SAFE-09 run failed because `src/wanctl/history.py` was outside the verifier allowlist.
Phase 208 artifacts verify that `history.py` is intentional v1.44 TOOL-02 operator-tooling drift for `wanctl-history --ingestion-rate`, not controller-path drift.

## Verifier Fix

Updated `scripts/check-safe07-source-diff.sh` to include `src/wanctl/history.py` in the v1.44 SAFE-09 allowlist.
Updated `tests/test_check_safe07_source_diff.py` so the synthetic v1.44 allowlist happy path covers `history.py`.

## Validation

```text
$ .venv/bin/pytest tests/test_check_safe07_source_diff.py -q
.................                                                        [100%]
17 passed in 1.66s

$ bash scripts/check-safe07-source-diff.sh --att-config-whitelist 6508d68
SAFE-08 OK: no configs/att.yaml diff vs 6508d68

$ bash scripts/check-safe07-source-diff.sh 6508d68
SAFE-09 OK: diff vs 6508d68 bounded to v1.44 allowlist
```

## Verdict

PASS. SAFE-08 and SAFE-09 mechanical closeout gates pass after correcting the verifier allowlist to match Phase 208's verified TOOL-02 source drift.
