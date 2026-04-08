---
phase: 149-type-annotations-protocols
plan: 01
subsystem: type-system
tags: [mypy, TypedDict, Protocol, type-annotations]
dependency_graph:
  requires: []
  provides: [RouterClient-Protocol, AlertFormatter-consolidated, TypedDict-config-types, zero-mypy-errors]
  affects: [autorate_config, config_base, interfaces, wan_controller, check_cake, check_cake_fix, autorate_continuous, webhook_delivery, steering-daemon, congestion_assessment, router_command_utils]
tech_stack:
  added: [TypedDict, Protocol, Mapping]
  patterns: [structural-subtyping, TypedDict-for-config-dicts, Mapping-for-TypedDict-compat]
key_files:
  created: []
  modified:
    - src/wanctl/autorate_config.py
    - src/wanctl/config_base.py
    - src/wanctl/interfaces.py
    - src/wanctl/webhook_delivery.py
    - src/wanctl/wan_controller.py
    - src/wanctl/check_cake.py
    - src/wanctl/check_cake_fix.py
    - src/wanctl/autorate_continuous.py
    - src/wanctl/steering/daemon.py
    - src/wanctl/steering/congestion_assessment.py
    - src/wanctl/router_command_utils.py
    - src/wanctl/config_validation_utils.py
    - src/wanctl/storage/maintenance.py
    - src/wanctl/storage/retention.py
decisions:
  - Used Mapping[str, Any] instead of dict for TypedDict-accepting parameters (mypy TypedDict not subtype of dict[str, Any])
  - Kept _create_audit_client return as Any since RouterOSSSH does not satisfy RouterClient Protocol
  - Added assert client is not None before --fix path in check_cake.py CLI
metrics:
  duration: 28m
  completed: "2026-04-08T21:09:00Z"
  tasks_completed: 2
  tasks_total: 2
  files_modified: 14
---

# Phase 149 Plan 01: Type Annotations and Protocols - Fix 29 mypy errors

Zero mypy --disallow-untyped-defs errors via TypedDicts for config sections, RouterClient/AlertFormatter Protocols in interfaces.py, and root-cause annotation fixes across 8 files.

## Task Summary

| Task | Name | Commit | Key Changes |
|------|------|--------|-------------|
| 1 | Define TypedDicts and add Protocols | 3efcfba | 5 TypedDict classes, RouterClient + AlertFormatter Protocols, AlertFormatter consolidation |
| 2 | Fix all 29 mypy errors | c9ecaef | client: object -> RouterClient, union annotations, return types, Mapping compat |

## What Was Done

### Task 1: TypedDict definitions and Protocol consolidation

- **autorate_config.py**: Added 5 TypedDict classes (FusionHealingConfig, FusionConfig, IRTTConfig, ReflectorQualityConfig, OWDAsymmetryConfig) with class-level annotations on Config
- **config_base.py**: Added RetentionConfig and StorageConfig TypedDicts, changed get_storage_config return type to StorageConfig
- **interfaces.py**: Added RouterClient Protocol (6 methods from RouterOSREST) and AlertFormatter Protocol
- **webhook_delivery.py**: Removed AlertFormatter class definition, replaced with import from interfaces.py

### Task 2: Fix all 29 mypy errors at root cause

- **wan_controller.py** (12 errors): TypedDict annotations on Config class resolved 4 errors automatically. Changed .get() to direct key access on healing_cfg and irtt_config (6 errors). Remaining errors resolved by TypedDict propagation.
- **check_cake.py** (5 errors): All `client: object` replaced with `client: RouterClient`. Added RouterClient import. _create_audit_client returns Any (RouterOSSSH doesn't satisfy Protocol).
- **check_cake_fix.py** (4 errors): All `client: object` replaced with `client: RouterClient`. `run_audit_fn: object` replaced with `Callable[[dict, str, RouterClient], list[CheckResult]]`.
- **autorate_continuous.py** (3 errors): Added `router: "LinuxCakeAdapter | RouterOS"` union annotation. Used TYPE_CHECKING import. Changed retention config to Mapping[str, Any].
- **webhook_delivery.py** (2 errors): Annotated `delay: float | None`. Widened `_handle_retryable_error` param to accept `float | None`.
- **steering/daemon.py** (1 error): StorageConfig TypedDict resolved retention_config type.
- **steering/congestion_assessment.py** (1 error): Added `-> None` to `__post_init__`.
- **router_command_utils.py** (1 error): Added `Iterator[bool | T | None]` return type to `__iter__`.

### Cascading fixes (additional files modified for TypedDict compatibility)

- **config_validation_utils.py**: `validate_retention_tuner_compat` param widened to `Mapping[str, Any]`
- **storage/maintenance.py**: `run_startup_maintenance` retention_config param widened to `Mapping[str, Any]`
- **storage/retention.py**: `cleanup_old_metrics` and `_cleanup_per_granularity` retention_config params widened to `Mapping[str, Any]`

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] TypedDict not compatible with dict[str, Any] in mypy 1.19**
- **Found during:** Task 2
- **Issue:** mypy treats TypedDict as incompatible with `dict[str, Any]` (and bare `dict` = `dict[Any, Any]`). Functions accepting retention config as `dict` rejected `RetentionConfig` TypedDict.
- **Fix:** Widened parameter types to `Mapping[str, Any]` which TypedDict IS a subtype of. Applied to validate_retention_tuner_compat, run_startup_maintenance, cleanup_old_metrics, _cleanup_per_granularity, and autorate_continuous.py internal signatures.
- **Files modified:** config_validation_utils.py, storage/maintenance.py, storage/retention.py, autorate_continuous.py

**2. [Rule 3 - Blocking] RouterOSSSH does not satisfy RouterClient Protocol**
- **Found during:** Task 2
- **Issue:** _create_audit_client returns either RouterOSREST (satisfies Protocol) or RouterOSSSH (only has run_cmd). Returning RouterClient causes mypy error for SSH path.
- **Fix:** Changed _create_audit_client return type to Any. Added assert for None check before --fix CLI path.
- **Files modified:** check_cake.py

**3. [Rule 3 - Blocking] Ruff F823 and I001 lint violations from new imports**
- **Found during:** Task 2 verification
- **Issue:** LinuxCakeAdapter referenced before assignment in type annotation (F823). Import block unsorted in check_cake_fix.py (I001).
- **Fix:** Used string annotation for forward reference. Reordered imports.
- **Files modified:** autorate_continuous.py, check_cake_fix.py

## Verification Results

- `mypy src/wanctl/ --disallow-untyped-defs`: Success: no issues found in 93 source files
- `ruff check --select F,I` on modified files: All checks passed
- Tests: All pre-existing test results unchanged (20 pre-existing failures, 720 passed on targeted suite)

## Self-Check: PASSED

All 14 modified files exist. Both commit hashes (3efcfba, c9ecaef) verified in git log.
