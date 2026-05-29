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
  warning: 4
  info: 0
  total: 4
status: issues_found
---

# Phase 215: Code Review Report

**Reviewed:** 2026-05-29T00:00:00Z
**Depth:** standard
**Files Reviewed:** 5
**Status:** issues_found

## Summary

Re-reviewed the Phase 215 Spectrum upload-reclaim config, extractor, reclaim gate, and targeted tests after the second code-review-fix pass. The previously reported parse-error abort cases are fixed for the covered cases: missing candidate inputs, missing option values, and unknown arguments now write a JSON-escaped abort verdict in the tested invocation shape.

Remaining concerns are rollback-safety and input-hardening issues in the gate/extractor path. The highest-risk remaining gap is that non-finite metric values can bypass rollback gates because `NaN` comparisons evaluate false. There is also a narrower parse-error artifact placement edge case when `--output-dir` appears after the parse error, plus an SSH option-injection hardening gap in the optional remote YAML preflight.

## Warnings

### WR-01: Non-finite metrics can bypass rollback gates

**File:** `scripts/phase215-reclaim-gate.sh:368-370`

**Issue:** Candidate latency and upload throughput are converted with `float(...)` but are not checked with `math.isfinite(...)`. Python's `json.loads` accepts non-standard `NaN`/`Infinity` tokens by default, and the extractor currently does not filter non-finite values either. If a candidate extract contains `NaN`, comparisons such as `candidate_p95 > derived_p95_bound` and `candidate_throughput < derived_win_bound` evaluate false, allowing a malformed measurement to reach a `pass` verdict instead of voiding/aborting. For a production rollback gate, malformed metrics should fail closed.

**Fix:** Centralize finite metric parsing and void/abort on non-finite values before scoring. For example:

```python
def required_finite_metric(payload: dict[str, Any], *path: str) -> float:
    cur: Any = payload
    for key in path:
        cur = cur[key]
    value = float(cur)
    if not math.isfinite(value):
        raise ValueError("non-finite metric")
    return value

candidate_p95 = required_finite_metric(candidate, "latency", "p95_ms")
candidate_p99 = required_finite_metric(candidate, "latency", "p99_ms")
candidate_throughput = required_finite_metric(candidate, "upload_throughput", "throughput_median_mbps")
```

Also add tests for `NaN`/`Infinity` candidate extract values asserting `rc == 2` and `verdict in {"void", "abort"}`.

### WR-02: Extractor accepts non-finite raw values instead of failing closed

**File:** `scripts/phase214-extract.py:51-54,77`

**Issue:** `_numeric_values()` and the ping `val` extraction accept numeric-looking values without a finite check. If Flent JSON contains `NaN` or `Infinity`, the extractor can emit invalid/non-finite statistics that then feed the reclaim gate. This weakens the D-09/D-10 fail-closed extraction invariant stated in the file header.

**Fix:** Filter or reject non-finite values consistently. For fail-closed behavior, prefer rejecting a series that contains non-finite samples or produces no finite samples:

```python
def _finite_float(value: Any) -> float | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        converted = float(value)
        return converted if math.isfinite(converted) else None
    return None
```

Use this helper for throughput and ping samples, and raise `FlentExtractionError` if no finite usable samples remain.

### WR-03: Parse-error verdict may still be written outside the requested output directory

**File:** `scripts/phase215-reclaim-gate.sh:80-88,110-128`

**Issue:** `OUTPUT_DIR` defaults to `.` and is only updated as the parser walks arguments. If a parse error occurs before a later `--output-dir`, `write_parse_abort` writes `./verdict.json` rather than the operator-specified verdict path. The new tests cover `--output-dir` before the bad argument, but wrappers commonly append output options after inputs; in that shape, the caller may still see no verdict at the expected path and short-circuit rollback handling.

**Fix:** Pre-scan arguments for a valid `--output-dir` before handling other parse errors, or require and document `--output-dir` as the first option and test that contract. Pre-scan is safer for operator ergonomics:

```bash
for ((i = 1; i <= $#; i++)); do
    if [[ "${!i}" == "--output-dir" ]]; then
        next=$((i + 1))
        if [[ $next -le $# && -n "${!next:-}" && "${!next}" != --* ]]; then
            OUTPUT_DIR="${!next}"
        fi
        break
    fi
done
```

Then keep the existing JSON-escaped `write_parse_abort` path and add a regression test where the bad/missing option appears before `--output-dir`.

### WR-04: Remote YAML host argument can be interpreted as SSH options

**File:** `scripts/phase215-reclaim-gate.sh:154-163`

**Issue:** The remote YAML path is validated, but `remote_host` is not. Because `ssh` treats a first argument beginning with `-` as an option, a hostile or malformed `--remote-yaml`/`PHASE215_REMOTE_YAML_SSH` value can inject SSH options such as `-oProxyCommand=...` before the safe remote Python command is reached. This optional preflight is operator-facing, but it is still a command-execution boundary in a production rollback gate.

**Fix:** Reject unsafe host tokens before invoking SSH, and terminate option parsing when supported:

```bash
if [[ ! "$remote_host" =~ ^[A-Za-z0-9._@-]+$ || "$remote_host" == -* ]]; then
    printf 'ABORT: --remote-yaml host contains unsafe characters\n' >&2
    write_preflight_abort "remote_yaml_invalid"
    exit "$EXIT_ABORT"
fi
deployed_ceiling="$(ssh -- "$remote_host" "sudo -n python3 - '$remote_path'" <<'PY'
```

If `ssh --` compatibility is a concern, the host validation alone still blocks option-style hosts.

---

_Reviewed: 2026-05-29T00:00:00Z_
_Reviewer: the agent (gsd-code-reviewer)_
_Depth: standard_
