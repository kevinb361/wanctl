---
phase: 149-type-annotations-protocols
plan: 02
subsystem: type-system
tags: [mypy, type-annotations, strict-mode, BaseConfig, MetricsWriter]
dependency_graph:
  requires: [149-01]
  provides: [strict-mypy-enforcement, zero-config-any, zero-writer-any]
  affects: [tuning/applier, router_client, backends, routeros_rest, routeros_ssh, pyproject.toml]
tech_stack:
  added: []
  patterns: [TYPE_CHECKING-for-circular-imports, no-any-return-boundary-markers, config-data-dict-access]
key_files:
  created: []
  modified:
    - src/wanctl/tuning/applier.py
    - src/wanctl/router_client.py
    - src/wanctl/backends/base.py
    - src/wanctl/backends/__init__.py
    - src/wanctl/backends/linux_cake_adapter.py
    - src/wanctl/backends/linux_cake.py
    - src/wanctl/backends/netlink_cake.py
    - src/wanctl/backends/routeros.py
    - src/wanctl/routeros_rest.py
    - src/wanctl/routeros_ssh.py
    - src/wanctl/check_cake.py
    - src/wanctl/steering/cake_stats.py
    - src/wanctl/alert_engine.py
    - src/wanctl/autorate_config.py
    - src/wanctl/benchmark.py
    - src/wanctl/benchmark_compare.py
    - src/wanctl/dashboard/poller.py
    - src/wanctl/error_handling.py
    - src/wanctl/history.py
    - src/wanctl/state_utils.py
    - src/wanctl/steering/daemon.py
    - src/wanctl/tuning/analyzer.py
    - pyproject.toml
    - tests/backends/test_backends.py
    - tests/backends/test_linux_cake_adapter.py
decisions:
  - Used BaseConfig for config params in backends/router via TYPE_CHECKING to avoid circular imports
  - Changed routeros.py from_config to use config.data["router"] instead of config.router (data dict access)
  - Changed linux_cake_adapter.py to read ceiling from config.data continuous_monitoring (not config.download_ceiling)
  - Added type: ignore[no-any-return] for 29 dict.get()/json.load() returns at system boundaries
  - Added type: ignore[arg-type] for 3 duck-type config proxies (SimpleNamespace, _AutorateConfigProxy)
  - Remaining 23 non-dict Any usages justified (WANController refs, decorator generics, polymorphic backends)
metrics:
  duration: 30m
  completed: "2026-04-08T22:06:00Z"
  tasks_completed: 2
  tasks_total: 2
  files_modified: 25
---

# Phase 149 Plan 02: Any Audit and Strict Mypy Enforcement

Replaced config: Any and writer: Any with BaseConfig/MetricsWriter across 11 backend/router/tuning files, annotated 29 system-boundary returns, and enabled strict mypy (disallow_untyped_defs + warn_return_any) in pyproject.toml.

## Task Summary

| Task | Name | Commit | Key Changes |
|------|------|--------|-------------|
| 1 | Replace config: Any and writer: Any | 43bea56 | 11 files: config -> BaseConfig, writer -> MetricsWriter, removed unused Any imports |
| 2 | Audit remaining Any and enable strict mypy | d54fe2e | pyproject.toml strict mode, 29 no-any-return annotations, 3 arg-type annotations, test fixes |

## What Was Done

### Task 1: Replace config: Any and writer: Any

- **tuning/applier.py**: All 3 `writer: Any | None` replaced with `MetricsWriter | None` via TYPE_CHECKING import
- **router_client.py**: All 7 `config: Any` replaced with `config: BaseConfig` via TYPE_CHECKING import. Removed `Any` from typing imports.
- **backends/base.py**: ABC `from_config(config: Any)` -> `from_config(config: BaseConfig)`
- **backends/__init__.py**: `get_backend(config: Any)` -> `get_backend(config: BaseConfig)`
- **backends/linux_cake.py**: `from_config(config: Any)` -> `from_config(config: BaseConfig)`
- **backends/netlink_cake.py**: `from_config(config: Any)` -> `from_config(config: BaseConfig)`
- **backends/routeros.py**: `from_config(config: Any)` -> `from_config(config: BaseConfig)`, changed `config.router` to `config.data["router"]` and `config.timeouts` to `config.data.get("timeouts", {})`
- **backends/linux_cake_adapter.py**: `from_config(config: Any)` -> `from_config(config: BaseConfig)`, changed ceiling access to `config.data["continuous_monitoring"]` dict
- **routeros_rest.py**: `from_config(config: Any)` -> `from_config(config: BaseConfig)`
- **routeros_ssh.py**: `from_config(config: Any)` -> `from_config(config: BaseConfig)`, removed unused `Any` import

### Task 2: Audit remaining Any and enable strict mypy

- **pyproject.toml**: `disallow_untyped_defs = true` (was false), `warn_return_any = true` (was false)
- **29 no-any-return annotations**: Added `# type: ignore[no-any-return]` to dict.get(), json.load(), and Union-typed returns at system boundaries across 14 files
- **3 arg-type annotations**: Added `# type: ignore[arg-type]` for duck-typed config proxies (SimpleNamespace in check_cake.py, _AutorateConfigProxy in cake_stats.py)
- **Test updates**: Updated test_backends.py mocks to use `config.data` dict, updated test_linux_cake_adapter.py to provide continuous_monitoring in config.data

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] routeros.py accessed config.router attribute not on BaseConfig**
- **Found during:** Task 1
- **Issue:** `RouterOSBackend.from_config()` accessed `config.router` (a dict) and `config.timeouts`, neither of which are attributes on BaseConfig
- **Fix:** Changed to `config.data["router"]` and `config.data.get("timeouts", {})` which access the raw YAML data dict (always available on BaseConfig)
- **Files modified:** src/wanctl/backends/routeros.py, tests/backends/test_backends.py

**2. [Rule 1 - Bug] linux_cake_adapter accessed config.download_ceiling not on BaseConfig**
- **Found during:** Task 1
- **Issue:** `LinuxCakeAdapter.from_config()` accessed `config.download_ceiling` and `config.upload_ceiling` which are Config subclass attributes, not on BaseConfig
- **Fix:** Changed to read from `config.data["continuous_monitoring"]["download"]["ceiling_mbps"]` with sensible defaults
- **Files modified:** src/wanctl/backends/linux_cake_adapter.py, tests/backends/test_linux_cake_adapter.py

## Verification Results

- `mypy src/wanctl/`: Success: no issues found in 93 source files (strict mode)
- `ruff check src/wanctl/`: 2 pre-existing warnings (not introduced by this plan)
- Tests: All pre-existing test results unchanged. 1 test fixed (linux_cake_adapter bandwidth). 0 regressions.

## Self-Check: PASSED

All 25 modified files exist. Both commit hashes (43bea56, d54fe2e) verified in git log.
