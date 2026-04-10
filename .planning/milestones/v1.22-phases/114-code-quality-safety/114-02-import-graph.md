# Import Graph Analysis (CQUAL-07)

## Methodology

- Extracted all `from wanctl.X import` and `import wanctl.X` statements from `src/wanctl/`
- Built directed dependency graph (82 modules, 137 import edges)
- Checked for circular import chains using DFS cycle detection
- Self-imports excluded from analysis (e.g., `__init__.py` re-exports)
- Per D-16/D-17: Document only. No code changes.

## Circular Dependencies Found

### 1. autorate_continuous <-> health_check (TYPE_CHECKING guarded)

```
wanctl.autorate_continuous -> wanctl.health_check -> wanctl.autorate_continuous
```

**Details:**
- `autorate_continuous.py` imports `start_health_server`, `update_health_status` from `health_check` (runtime import, line 33)
- `health_check.py` imports `ContinuousAutoRate` from `autorate_continuous` (TYPE_CHECKING guard, line 64)

**Risk: LOW** -- The reverse import is inside `if TYPE_CHECKING:` block, which means it is only evaluated by mypy/type checkers, never at runtime. Python's import machinery never sees the cycle. This is the standard pattern for breaking circular imports while maintaining type safety.

**Recommendation:** No action needed. The `TYPE_CHECKING` guard is the correct solution.

### 2. steering/daemon <-> steering/health (TYPE_CHECKING guarded)

```
wanctl.steering.daemon -> wanctl.steering.health -> wanctl.steering.daemon
```

**Details:**
- `steering/daemon.py` imports from `steering/health.py` (runtime import)
- `steering/health.py` imports `SteeringDaemon` from `steering/daemon` (TYPE_CHECKING guard, line 27)

**Risk: LOW** -- Same TYPE_CHECKING pattern as above. No runtime cycle.

**Recommendation:** No action needed.

## Import Statistics

| Metric | Value |
|--------|-------|
| Total Python files | 82 |
| Total import edges (wanctl.* only) | 137 |
| Leaf modules (0 wanctl imports) | 41 (50%) |
| Modules importing 5+ wanctl modules | 8 |
| Most importing module | autorate_continuous (37 imports) |
| Most imported module | tuning.models (9 importers) |

## Hub Modules (imported by 5+ modules)

| Module | Imported by | Role |
|--------|-------------|------|
| tuning.models | 9 | Tuning data classes (TuningConfig, TuningResult, SafetyBounds) |
| storage.writer | 8 | MetricsWriter singleton + DEFAULT_DB_PATH constant |
| storage.reader | 7 | Query functions for metrics DB |

## Near-Hub Modules (imported by 3-4)

| Module | Imported by | Role |
|--------|-------------|------|
| config_base | 4 | BaseConfig, ConfigValidationError, get_storage_config |
| rtt_measurement | 4 | RTT measurement + parse_ping_output |
| routeros_ssh | 3 | RouterOS SSH client |
| alert_engine | 3 | Alert engine for webhooks |
| path_utils | 3 | File/directory path utilities |
| lock_utils | 3 | File locking utilities |
| irtt_measurement | 3 | IRTT measurement client |
| storage.downsampler | 3 | Metrics downsampling |
| storage.retention | 3 | Data retention policies |
| storage.schema | 3 | Database schema creation |
| dashboard.widgets.status_bar | 3 | Dashboard status bar (format_duration) |
| backends.base | 3 | RouterBackend ABC |
| backends.linux_cake | 3 | LinuxCakeBackend implementation |

## Fan-Out Modules (importing 5+ modules)

| Module | Imports | Role |
|--------|---------|------|
| autorate_continuous | 37 | Main autorate daemon (orchestrator) |
| dashboard.app | 8 | TUI dashboard application |
| storage (\_\_init\_\_) | 8 | Storage package re-exports |
| benchmark | 6 | Benchmarking CLI tool |
| health_check | 5 | HTTP health endpoint |
| check_config | 5 | Config validation CLI |
| check_cake | 5 | CAKE verification CLI |
| steering.health | 5 | Steering health endpoint |

## Graph Shape Analysis

The import graph has a **clear layered architecture:**

1. **Leaf layer (41 modules, 50%):** Zero wanctl imports. Pure utilities, data models, measurement primitives.
2. **Mid layer (~25 modules):** Import 1-4 leaf modules. Config validation, storage operations, backend implementations.
3. **Orchestrator layer (~8 modules):** Import 5+ modules. Daemons, CLI tools, health servers.
4. **God module (1):** `autorate_continuous.py` with 37 imports -- expected for the main daemon orchestrator.

**Health indicators:**
- **50% leaf modules** = strong foundation with no dependency risk
- **No runtime circular dependencies** = import order is well-structured
- **2 TYPE_CHECKING cycles** = properly managed with the standard Python pattern
- **Single high-fan-out module** (autorate_continuous at 37) = expected for daemon entry point but extraction opportunity (see 114-02-complexity-analysis.md)

## Recommendations for v1.23

1. **No circular dependency fixes needed** -- both detected cycles use TYPE_CHECKING correctly
2. **storage.writer fan-in (8)** -- Consider whether DEFAULT_DB_PATH should be extracted to a constants module to reduce imports of the writer module just for the path
3. **autorate_continuous fan-out (37)** -- Reducing this would require extracting responsibilities (config loading, health integration, signal processing setup) into separate orchestration modules. This aligns with complexity reduction recommendations in 114-02-complexity-analysis.md
4. **Consider import-linter** -- Adding `import-linter` to CI would enforce the layered architecture and prevent accidental runtime circular imports in future development
