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
  warning: 3
  info: 1
  total: 4
status: issues_found
---

# Phase 215: Code Review Report

**Reviewed:** 2026-05-29T00:00:00Z
**Depth:** standard
**Files Reviewed:** 5
**Status:** issues_found

## Summary

Reviewed the Phase 215 Spectrum upload-reclaim config, extraction changes, reclaim gate shell/Python scorer, and targeted tests. The main concerns are fail-closed/rollback-contract gaps: several malformed or incomplete-but-plausible inputs can cause the gate to exit without writing `verdict.json`, and the remote deployed-ceiling preflight appears unable to parse a normal `ceiling_mbps: 20` line. There is also a config/script mismatch that can prevent the intended 20 Mbps canary from actually being evaluated.

## Warnings

### WR-01: Gate can crash without verdict when upload throughput is absent from extractor output

**File:** `scripts/phase215-reclaim-gate.sh:294-313`

**Issue:** The gate reads `baseline["upload_throughput"]` and `candidate["upload_throughput"]` outside the guarded load block. `scripts/phase214-extract.py` currently exits successfully if either download or upload throughput exists (`scripts/phase214-extract.py:174-175`), so a download-only extract can be a valid JSON output but still lacks `upload_throughput`. In that case the reclaim gate raises `KeyError`, exits non-deterministically under `set -e`, and may not write `verdict.json`, violating the documented rollback contract.

**Fix:** Validate required scoring fields inside a fail-closed block and write a `void`/abort verdict on missing or non-numeric values, for example:

```python
try:
    if baseline:
        baseline_p95 = float(baseline["latency"]["p95_ms"])
        baseline_p99 = float(baseline["latency"]["p99_ms"])
        baseline_median = float(baseline["upload_throughput"]["throughput_median_mbps"])
    candidate_p95 = float(candidate["latency"]["p95_ms"])
    candidate_p99 = float(candidate["latency"]["p99_ms"])
    candidate_throughput = float(candidate["upload_throughput"]["throughput_median_mbps"])
except (KeyError, TypeError, ValueError) as exc:
    raise SystemExit(write({"verdict": "void", "reason": f"required_metric_missing_or_invalid:{exc}"}, EXIT_ABORT))
```

### WR-02: Remote ceiling regex appears over-escaped and can abort before writing verdict

**File:** `scripts/phase215-reclaim-gate.sh:120-130`

**Issue:** The SSH preflight Python snippet uses `re.match(r'^    ceiling_mbps:\\\\s*([0-9.]+)', line)` after shell double-quote processing. That leaves the Python raw regex matching a literal `\s` sequence rather than whitespace, so a normal YAML line such as `    ceiling_mbps: 20` is not parsed. Because this is inside command substitution under `set -e`, the script can exit before the mismatch branch writes `verdict.json`.

**Fix:** Avoid double-quote/backslash layering or pass the remote path as an argument to a quoted here-doc/script. At minimum, use a regex that reaches Python as `r'^    ceiling_mbps:\s*([0-9.]+)'`, and wrap the SSH assignment so parse failure writes an abort verdict instead of short-circuiting:

```bash
if ! deployed_ceiling="$(ssh "$remote_host" "sudo -n python3 ...")"; then
    python3 - "$VERDICT" <<'PY'
# write {"verdict": "abort", "reason": "deployed_ceiling_unreadable"}
PY
    exit "$EXIT_ABORT"
fi
```

### WR-03: Missing argument values violate the script's abort/void exit-code contract

**File:** `scripts/phase215-reclaim-gate.sh:66-95`

**Issue:** Options such as `--candidate-extract` and `--output-dir` assign `$2` without first checking that a value exists. With `set -u`, a truncated command exits from the shell with an unbound-variable error instead of the documented `EXIT_ABORT=2` path and does not write a verdict. This is a rollback-safety issue for operator or wrapper mistakes.

**Fix:** Add a helper that fail-closes on missing option values before assignment:

```bash
need_value() {
    if [[ "$#" -lt 2 || "${2:-}" == --* ]]; then
        printf 'ABORT: %s requires a value\n' "$1" >&2
        exit "$EXIT_ABORT"
    fi
}

--candidate-extract)
    need_value "$@"
    CANDIDATE_EXTRACT="$2"
    shift 2
    ;;
```

## Info

### IN-01: Reclaim gate default expects 20 Mbps while Spectrum config still deploys 18 Mbps

**File:** `configs/spectrum.yaml:75-78` and `scripts/phase215-reclaim-gate.sh:63`

**Issue:** The gate defaults `EXPECTED_CEILING="20"`, but `configs/spectrum.yaml` still sets Spectrum upload `ceiling_mbps: 18` and documents 18 Mbps as the latency-first operating point. If Phase 215 intends a 20 Mbps upload-reclaim canary, the checked-in config does not deploy the candidate being gated; if Phase 215 intentionally avoids config drift, the script default should be explicitly overridden/documented by the canary runner.

**Fix:** Align the phase artifact with the intended deployment path: either update the canary config to `ceiling_mbps: 20` with an explicit rollback-to-18 comment, or require callers to pass `--expected-ceiling 18` and rename/document the gate as an 18 Mbps validation rather than a 20 Mbps reclaim gate.

---

_Reviewed: 2026-05-29T00:00:00Z_
_Reviewer: the agent (gsd-code-reviewer)_
_Depth: standard_
