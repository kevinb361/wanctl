---
phase: 200-per-direction-rtt-bloat-thresholds
reviewed: 2026-05-04T14:07:47Z
depth: standard
files_reviewed: 18
files_reviewed_list:
  - src/wanctl/queue_controller.py
  - src/wanctl/wan_controller.py
  - src/wanctl/autorate_config.py
  - src/wanctl/check_config_validators.py
  - src/wanctl/__init__.py
  - configs/spectrum.yaml
  - scripts/phase200-saturation-canary.sh
  - scripts/phase200-saturation-canary.env.example
  - docker/Dockerfile
  - .dockerignore
  - pyproject.toml
  - tests/conftest.py
  - tests/test_autorate_config.py
  - tests/test_wan_controller.py
  - tests/test_queue_controller.py
  - tests/test_check_config.py
  - tests/test_phase200_canary_script.py
  - tests/test_phase_195_replay.py
findings:
  critical: 0
  warning: 2
  info: 1
  total: 3
status: issues_found
---

# Phase 200: Code Review Report

**Reviewed:** 2026-05-04T14:07:47Z  
**Depth:** standard  
**Files Reviewed:** 18  
**Status:** issues_found

## Summary

Reviewed Phase 200 source, config, script, packaging, and test changes with emphasis on Plans 200-10 through 200-14. The core controller/config wiring for per-upload thresholds, presence-based live-tuning gates, SAFE-06 unknown-key warning, and the R3/R5 upload remediation is coherent and covered by targeted tests. The production canary outcome remains a validation gap (`VALN-06` failed with 4 loaded-window floor hits), but I did not find a direct source-level correctness bug explaining that residual behavior.

I found two packaging/operational-script warnings and one Dockerfile documentation issue. No critical security issues were found.

## Warnings

### WR-01: Docker dependency constraints are parsed as shell redirections

**File:** `docker/Dockerfile:46-52`  
**Issue:** The Dockerfile passes unquoted requirement specifiers such as `requests>=2.33.0` to a shell-form `RUN`. In `/bin/sh`, `>` is a redirection operator, so these tokens can be parsed as package names plus output redirections instead of version-constrained pip requirements. That means the image may install unconstrained/latest packages (and create stray files like `=2.33.0`) even though the line appears pinned. This is a packaging correctness risk for a production controller image and also weakens the Plan 200-13 “dependencies must match pyproject.toml” claim.  
**Fix:** Quote each requirement or move them to a requirements file copied into the image. For the minimal fix:

```dockerfile
RUN pip install --no-cache-dir \
    'requests>=2.33.0' \
    'pyyaml>=6.0.1' \
    'paramiko>=3.4.0' \
    'tabulate>=0.9.0' \
    'icmplib>=3.0.4' \
    'cryptography>=46.0.5'
```

### WR-02: Canary remote-YAML preflight can exit without an abort verdict if Python/PyYAML is missing

**File:** `scripts/phase200-saturation-canary.sh:268-271,328-338`  
**Issue:** The script requires `curl`, `jq`, `iperf3`, and `awk`, but it also depends on `python3` plus the `yaml` module for the remote YAML preflight. Because `import yaml` runs before the `try:` block inside a command substitution and the script has `set -euo pipefail`, a missing `python3` or PyYAML import failure can terminate the script immediately instead of writing `verdict.json` with `verdict="abort"`. Plan 200-14 requires explicit pass/fail/abort handling, so this creates a fail-closed evidence gap for a tool-dependency failure.  
**Fix:** Add explicit dependency checks after `VERDICT` is initialized, or make the Python preflight return structured JSON errors. Example:

```bash
require_command python3
if ! python3 -c 'import yaml' >/dev/null 2>&1; then
    log_abort "required Python module not available: yaml"
    write_abort_verdict "python_yaml_unavailable"
    exit "$EXIT_ABORT"
fi
```

Alternatively, move `import yaml` inside the existing Python `try:` and ensure the assignment cannot trigger `set -e` before `write_abort_verdict` runs.

## Info

### IN-01: Dockerfile top-level usage comment still shows an invalid build invocation

**File:** `docker/Dockerfile:5-7`  
**Issue:** Plan 200-13 correctly documents the canonical build command later in the file (`docker build -f docker/Dockerfile -t wanctl:latest .`), but the top usage block still says `docker build -t wanctl .`. From the repository root that will not find `docker/Dockerfile`; from `docker/` as context it will not contain `src/wanctl`.  
**Fix:** Update the usage comment to the canonical repo-root command:

```dockerfile
# Usage:
#   docker build -f docker/Dockerfile -t wanctl:latest .
#   docker run -v ./configs/wan1.yaml:/etc/wanctl/wan.yaml wanctl:latest
```

---

_Reviewed: 2026-05-04T14:07:47Z_  
_Reviewer: the agent (gsd-code-reviewer)_  
_Depth: standard_
