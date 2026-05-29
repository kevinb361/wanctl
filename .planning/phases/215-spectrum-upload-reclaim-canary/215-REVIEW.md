---
phase: 215-spectrum-upload-reclaim-canary
reviewed: 2026-05-29T00:00:00Z
depth: standard
files_reviewed: 5
files_reviewed_list:
  - configs/spectrum.yaml
  - scripts/phase214-extract.py
  - scripts/phase215-reclaim-gate.sh
  - tests/test_phase215_extract_upload.py
  - tests/test_phase215_reclaim_gate.py
findings:
  critical: 0
  warning: 1
  info: 0
  total: 1
status: issues_found
---

# Phase 215: Code Review Report

**Reviewed:** 2026-05-29T00:00:00Z
**Depth:** standard
**Files Reviewed:** 5
**Status:** issues_found

## Summary

Re-reviewed the Phase 215 Spectrum upload-reclaim config, extractor, reclaim gate, and targeted tests after the code-review-fix pass. Prior findings WR-01, WR-02, and WR-03 are materially fixed for their reported cases: missing `upload_throughput` now produces a `void` verdict, the remote YAML preflight uses a parseable regex and writes an abort verdict on unreadable deployed ceiling, and missing values after known options are guarded before `$2` expansion.

One rollback-safety gap remains in adjacent parse-error paths: some argument failures still exit with `EXIT_ABORT=2` without writing `verdict.json`, which can break callers that branch on the documented verdict artifact before rolling back.

## Warnings

### WR-01: Some argument abort paths still exit without verdict.json

**File:** `scripts/phase215-reclaim-gate.sh:117-127`

**Issue:** The fixed `need_value` path writes `verdict.json`, but unknown arguments and missing required `--candidate-extract` / `--candidate-health` still only print to stderr and exit `EXIT_ABORT=2`. The script header explicitly says nonzero exits must not short-circuit rollback and callers should branch on `verdict.json`; these parse-error paths can still leave no verdict artifact for an operator/wrapper mistake.

**Fix:** Route all abort exits after defaults are initialized through a JSON-writing abort helper, and add regression tests for missing required inputs and unknown arguments. For example:

```bash
        *)
            printf 'ABORT: unknown argument: %s\n' "$1" >&2
            write_parse_abort "unknown_argument:${1}"
            exit "$EXIT_ABORT"
            ;;
    esac
done

if [[ -z "$CANDIDATE_EXTRACT" || -z "$CANDIDATE_HEALTH" ]]; then
    printf 'ABORT: --candidate-extract and --candidate-health are required\n' >&2
    write_parse_abort "missing_required_candidate_inputs"
    exit "$EXIT_ABORT"
fi
```

If `write_parse_abort` is reused with raw arbitrary argument text, update it to JSON-escape via Python rather than `printf` string interpolation.

---

_Reviewed: 2026-05-29T00:00:00Z_
_Reviewer: the agent (gsd-code-reviewer)_
_Depth: standard_
