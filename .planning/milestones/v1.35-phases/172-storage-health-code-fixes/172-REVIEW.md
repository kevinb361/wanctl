---
phase: 172-storage-health-code-fixes
reviewed: 2026-04-12T16:34:27Z
depth: standard
files_reviewed: 3
files_reviewed_list:
  - scripts/analyze_baseline.py
  - scripts/deploy.sh
  - tests/test_analyze_baseline.py
findings:
  critical: 0
  warning: 2
  info: 1
  total: 3
status: issues_found
---

# Phase 172: Code Review Report

**Reviewed:** 2026-04-12T16:34:27Z
**Depth:** standard
**Files Reviewed:** 3
**Status:** issues_found

## Summary

Reviewed the three specified files at standard depth. `scripts/analyze_baseline.py` is a thin
wrapper that correctly bootstraps both dev and prod import paths — no issues there.
`tests/test_analyze_baseline.py` covers the key contracts well, with one fragility around
subprocess path resolution. The main finding is a bash `set -e` interaction bug in
`scripts/deploy.sh` that causes `verify_deployment` to silently abort on the first detected
error rather than collecting all errors and reporting them.

## Warnings

### WR-01: `((errors++))` with `set -e` aborts deploy on first verification failure

**File:** `scripts/deploy.sh:379` (also 387, 420)
**Issue:** `verify_deployment` uses `((errors++))` to accumulate error counts. In bash, `((expr))`
returns exit code 1 when the arithmetic result is zero. Because `errors` starts at 0, the very
first `((errors++))` evaluates `((0))`, which is falsy (exit code 1). With `set -e` active
(line 14), the script exits immediately on that first increment — before printing any error
message and before reaching the `[[ $errors -gt 0 ]]` check. The intent is to report all
verification failures and exit non-zero; the actual behavior is a silent abort mid-function.

Reproduction:
```bash
set -e; errors=0; ((errors++))   # exits immediately, errors never reported
```

**Fix:** Use `errors=$((errors + 1))` which is an assignment statement with exit code 0
regardless of value, or disable errexit locally in the function:

```bash
# Option A — safe increment idiom (preferred)
errors=$((errors + 1))

# Option B — disable errexit in accumulation function only
verify_deployment() {
    set +e    # allow accumulation without triggering set -e
    local errors=0
    ...
    [[ $errors -gt 0 ]] && { print_error "..."; return 1; }
    set -e
}
```

Apply to all three increment sites: lines 379, 387, and 420.

### WR-02: `eval rsync` expands unsanitized `TARGET_HOST` in shell context

**File:** `scripts/deploy.sh:163`
**Issue:** `rsync_opts` is built as a string with concatenation and then expanded via
`eval rsync $rsync_opts "src/wanctl/" "$TARGET_HOST:$TARGET_CODE_DIR/"`. The `eval` is
needed to collapse the `--rsync-path='sudo rsync'` single-quoted token, but `$TARGET_HOST`
participates in the eval without sanitization. A `TARGET_HOST` value containing shell
metacharacters (e.g., a hostname like `host; rm -rf /`) would execute arbitrary commands
as the deploying user. `TARGET_HOST` is taken directly from the command-line positional
argument with no validation beyond an SSH connectivity check.

**Fix:** Use an array to build rsync arguments — arrays preserve quoting without eval:

```bash
deploy_code() {
    print_step "Deploying wanctl code to $TARGET_HOST..."
    cd "$PROJECT_ROOT"
    ssh "$TARGET_HOST" "sudo mkdir -p $TARGET_CODE_DIR"

    local -a rsync_opts=(
        -av --delete
        --exclude=__pycache__
        "--exclude=*.pyc"
        --rsync-path="sudo rsync"
        --chmod=F644,D755
        --chown=root:root
    )
    [[ "$DRY_RUN" == "true" ]] && rsync_opts+=(-n)

    rsync "${rsync_opts[@]}" "src/wanctl/" "$TARGET_HOST:$TARGET_CODE_DIR/"
    ...
}
```

## Info

### IN-01: Subprocess test uses relative script path with no `cwd` anchor

**File:** `tests/test_analyze_baseline.py:73-76`
**Issue:** `test_wrapper_script_runs_as_subprocess` passes `"scripts/analyze_baseline.py"` as
a relative path to `subprocess.run()` without specifying `cwd`. The test passes when pytest is
invoked from the project root (the normal case) but silently breaks — raising a
`FileNotFoundError` wrapped as an assertion failure — if run from any other directory. This
makes the test fragile in CI setups that change working directory.

**Fix:** Anchor to the project root via `__file__`:

```python
PROJECT_ROOT = Path(__file__).resolve().parents[1]

def test_wrapper_script_runs_as_subprocess() -> None:
    """Verify scripts/analyze_baseline.py runs without import errors."""
    script = PROJECT_ROOT / "scripts" / "analyze_baseline.py"
    result = subprocess.run(
        [sys.executable, str(script), "--help"],
        capture_output=True,
        text=True,
        timeout=10,
        cwd=PROJECT_ROOT,
    )
    assert result.returncode == 0, f"Wrapper failed: {result.stderr}"
    assert "Analyze CAKE signal baseline" in result.stdout
```

---

_Reviewed: 2026-04-12T16:34:27Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
