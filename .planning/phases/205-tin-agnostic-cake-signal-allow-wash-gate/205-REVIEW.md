---
phase: 205-tin-agnostic-cake-signal-allow-wash-gate
reviewed: 2026-05-14T00:00:00Z
depth: standard
files_reviewed: 10
files_reviewed_list:
  - src/wanctl/cake_signal.py
  - src/wanctl/cake_params.py
  - src/wanctl/backends/linux_cake.py
  - src/wanctl/backends/netlink_cake.py
  - src/wanctl/check_config_validators.py
  - tests/test_cake_signal.py
  - tests/test_cake_params.py
  - tests/backends/test_linux_cake.py
  - tests/backends/test_netlink_cake.py
  - tests/test_check_config.py
findings:
  critical: 0
  warning: 2
  info: 0
  total: 2
status: issues_found
---

# Phase 205: Code Review Report

**Reviewed:** 2026-05-14T00:00:00Z
**Depth:** standard
**Files Reviewed:** 10
**Status:** issues_found

## Summary

Reviewed the CAKE tin aggregation, CAKE parameter building/backend application, netlink parity tests, and config-check integration for the Phase 205 changes. The core single-tin active-signal handling and `allow_wash` builder gate look targeted, but config validation still has two safety gaps that can let production netlink configs drift from what the daemon will actually accept or report false warnings for valid CAKE parameters.

## Warnings

### WR-01: `linux-cake-netlink` configs skip detailed CAKE parameter validation

**File:** `src/wanctl/check_config_validators.py:967`
**Issue:** `_run_autorate_validators()` delegates CAKE-specific checks to `validate_linux_cake(data)`, but that validator only runs for `router.transport == "linux-cake"`. `_validate_transport_consistency()` recognizes both `linux-cake` and `linux-cake-netlink`, but it only checks whether `cake_params` exists. Result: a `linux-cake-netlink` config with missing/empty interface names or invalid `overhead` can produce no config-check error, then fail later at daemon startup.
**Fix:** Update the Linux CAKE validator to cover both transports and add a regression test for the netlink transport path.

```python
# in validate_linux_cake(...)
linux_cake_transports = ("linux-cake", "linux-cake-netlink")
transport = _get_nested(data, "router.transport", "rest")
if transport not in linux_cake_transports:
    return results
```

### WR-02: Valid `cake_params` keys are missing from unknown-key registry

**File:** `src/wanctl/check_config_validators.py:154-165`
**Issue:** `build_cake_params()` supports `diffserv`, `split_gso`, and `ecn` as operator-configurable CAKE parameters, and this phase specifically makes `diffserv: besteffort` operationally important for single-tin layouts. These paths are absent from `KNOWN_AUTORATE_PATHS`, so `wanctl-check-config` flags valid configs such as `cake_params.diffserv: besteffort` as unknown keys.
**Fix:** Add every supported `cake_params` YAML key to `KNOWN_AUTORATE_PATHS`, then extend the existing unknown-key test to cover them.

```python
KNOWN_AUTORATE_PATHS.update({
    "cake_params.diffserv",
    "cake_params.split_gso",
    "cake_params.ecn",
})
```

---

_Reviewed: 2026-05-14T00:00:00Z_
_Reviewer: the agent (gsd-code-reviewer)_
_Depth: standard_
