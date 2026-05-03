---
phase: 200-per-direction-rtt-bloat-thresholds
reviewed: 2026-05-03T00:00:00Z
depth: standard
files_reviewed: 15
files_reviewed_list:
  - src/wanctl/autorate_config.py
  - src/wanctl/check_config_validators.py
  - src/wanctl/wan_controller.py
  - src/wanctl/__init__.py
  - tests/conftest.py
  - tests/test_autorate_config.py
  - tests/test_wan_controller.py
  - tests/test_phase_195_replay.py
  - scripts/phase200-saturation-canary.sh
  - scripts/phase200-saturation-canary.env.example
  - configs/spectrum.yaml
  - CHANGELOG.md
  - docs/CONFIGURATION.md
  - pyproject.toml
  - docker/Dockerfile
findings:
  critical: 0
  warning: 3
  info: 0
  total: 3
status: issues_found
---

# Phase 200: Code Review Report

**Reviewed:** 2026-05-03T00:00:00Z
**Depth:** standard
**Files Reviewed:** 15
**Status:** issues_found

## Summary

Reviewed the per-direction upload threshold implementation, config validator updates, regression tests, canary script, Spectrum config/docs/versioning, and Docker packaging. The controller-side threshold wiring is generally conservative and respects the existing link-agnostic architecture, but three correctness/security issues should be addressed before relying on the surrounding validation/deploy surfaces.

## Warnings

### WR-01: Config-check cross-field validation misses upload-specific threshold ordering

**File:** `src/wanctl/check_config_validators.py:305-318`
**Issue:** `validate_cross_fields()` validates download floors, upload floors, global threshold ordering, and transport consistency, but it never validates `continuous_monitoring.upload.target_bloat_ms < continuous_monitoring.upload.warn_bloat_ms`. `Config._load_threshold_config()` does reject invalid upload-specific ordering at daemon load, but `wanctl-check-config` can report a config as cross-field valid even though the daemon will fail later. For a production network controller, preflight and daemon validation should agree fail-closed.
**Fix:** Add an upload-specific threshold cross-field validator and call it from `validate_cross_fields()`:

```python
def validate_cross_fields(data: dict) -> list[CheckResult]:
    results: list[CheckResult] = []
    cm = data.get("continuous_monitoring", {})

    results.extend(_validate_download_floors(cm))
    results.extend(_validate_upload_floors(cm))
    results.extend(_validate_threshold_ordering(cm))
    results.extend(_validate_upload_threshold_ordering(cm))
    results.extend(_validate_transport_consistency(data))
    return results


def _validate_upload_threshold_ordering(cm: dict) -> list[CheckResult]:
    ul = cm.get("upload", {})
    thresholds = cm.get("thresholds", {})
    if not isinstance(ul, dict) or not isinstance(thresholds, dict):
        return []

    target = ul.get("target_bloat_ms", thresholds.get("target_bloat_ms"))
    warn = ul.get("warn_bloat_ms", thresholds.get("warn_bloat_ms"))
    if target is None or warn is None:
        return []
    if float(target) < float(warn):
        return [CheckResult("Cross-field Checks", "upload.thresholds", Severity.PASS, "Upload threshold ordering: valid")]
    return [CheckResult("Cross-field Checks", "upload.thresholds", Severity.ERROR, "upload target_bloat_ms must be less than upload warn_bloat_ms")]
```

### WR-02: Remote YAML path is interpolated into an SSH shell command

**File:** `scripts/phase200-saturation-canary.sh:256-266`
**Issue:** `REMOTE_YAML_PATH` comes from `PHASE200_REMOTE_YAML_SSH` and is inserted directly into the remote command string: `"sudo cat ${REMOTE_YAML_PATH}"`. A malformed value containing shell metacharacters can execute unintended commands on the remote host. Even if this is operator-supplied, deploy tooling should not create a command-injection footgun.
**Fix:** Fail closed on unsafe remote paths before constructing the SSH command, or quote via a safe remote wrapper. For example:

```bash
if ! [[ "$REMOTE_YAML_PATH" =~ ^/[A-Za-z0-9._/-]+$ ]]; then
    log_abort "REMOTE_YAML_PATH must be an absolute path with safe characters only: ${REMOTE_YAML_PATH}"
    write_abort_verdict "remote_yaml_path_unsafe"
    exit "$EXIT_ABORT"
fi

YAML_PROBE="$(ssh -o ConnectTimeout=10 -o BatchMode=no "$REMOTE_SSH_TARGET" \
    "sudo cat -- ${REMOTE_YAML_PATH}" 2>/dev/null | python3 -c '...')"
```

### WR-03: Docker image does not preserve the Python package layout

**File:** `docker/Dockerfile:56-59`
**Issue:** The Dockerfile copies `src/wanctl/*.py` into `/opt/wanctl/` and only copies two subdirectories (`backends`, `steering`). With `PYTHONPATH=/opt/wanctl`, imports such as `from wanctl.storage.deferred_writer import DeferredIOWorker` require `/opt/wanctl/wanctl/...`, not loose module files at `/opt/wanctl/*.py`. The image also omits other package subdirectories such as `storage` and `tuning`, so container startup/imports can fail even though the source tree works.
**Fix:** Install the package or copy the package directory intact. Prefer package install so dependencies and entry points stay consistent:

```dockerfile
WORKDIR /app
COPY pyproject.toml /app/
COPY src /app/src
RUN pip install --no-cache-dir .

ENV WANCTL_CONFIG=/etc/wanctl/wan.yaml
ENV PYTHONUNBUFFERED=1
```

If keeping direct-copy mode, use `COPY src/wanctl /opt/wanctl/wanctl` and keep `PYTHONPATH=/opt/wanctl`.

---

_Reviewed: 2026-05-03T00:00:00Z_
_Reviewer: the agent (gsd-code-reviewer)_
_Depth: standard_
