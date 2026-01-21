# Codebase Structure

**Analysis Date:** 2026-01-21

## Directory Layout

```
wanctl/
├── src/wanctl/                        # Main source code
│   ├── __init__.py                    # Package metadata (version)
│   ├── autorate_continuous.py         # Primary entry point (50ms daemon)
│   ├── calibrate.py                   # Calibration tool (one-time baseline)
│   ├── config_base.py                 # Configuration loading and validation
│   ├── config_validation_utils.py     # Field validators (bounds, ranges, types)
│   ├── error_handling.py              # Error handling decorators (@handle_errors)
│   ├── health_check.py                # Health status endpoint
│   ├── lock_utils.py                  # File-based locking (prevents concurrent daemons)
│   ├── logging_utils.py               # Dual-file logging (main + debug)
│   ├── metrics.py                     # Prometheus metrics registry
│   ├── path_utils.py                  # File path utilities
│   ├── perf_profiler.py               # Performance profiling decorator
│   ├── rate_utils.py                  # Rate limiting, bandwidth enforcing
│   ├── retry_utils.py                 # Exponential backoff retry helpers
│   ├── router_client.py               # Router transport factory (SSH vs REST)
│   ├── router_command_utils.py        # RouterOS command parsing utilities
│   ├── routeros_rest.py               # REST API client implementation
│   ├── routeros_ssh.py                # SSH client implementation (paramiko)
│   ├── rtt_measurement.py             # Ping-based RTT measurement
│   ├── signal_utils.py                # Signal handling (SIGTERM, SIGUSR1)
│   ├── state_manager.py               # State persistence base classes and validators
│   ├── state_utils.py                 # Atomic file I/O (JSON, locks)
│   ├── steering_logger.py             # Steering-specific logging
│   ├── systemd_utils.py               # systemd integration (watchdog, degraded)
│   ├── timeouts.py                    # Timeout constants
│   ├── wan_controller_state.py        # Autorate state (hysteresis, rates, EWMA)
│   ├── backends/                      # Router backend implementations
│   │   ├── __init__.py
│   │   ├── base.py                    # Abstract RouterBackend interface
│   │   └── routeros.py                # MikroTik RouterOS implementation
│   └── steering/                      # WAN steering subsystem
│       ├── __init__.py
│       ├── daemon.py                  # Secondary entry point (2s timer daemon)
│       ├── cake_stats.py              # CAKE queue statistics reader
│       ├── congestion_assessment.py   # Multi-signal congestion assessment
│       └── steering_confidence.py     # Phase2B dry-run validation (experimental)
│
├── tests/                             # Test suite (594 unit tests)
│   ├── __init__.py
│   ├── conftest.py                    # Pytest fixtures (temp_dir, sample_config_data)
│   ├── test_autorate_*.py             # Autorate controller tests
│   ├── test_baseline_rtt_manager.py   # Baseline RTT tracking tests
│   ├── test_config_*.py               # Configuration validation tests
│   ├── test_health_check.py           # Health endpoint tests
│   ├── test_lock_*.py                 # Locking mechanism tests
│   ├── test_metrics.py                # Prometheus metrics tests
│   ├── test_rate_limiter.py           # Rate limiting tests
│   ├── test_retry_utils.py            # Retry backoff tests
│   ├── test_rtt_measurement.py        # RTT measurement tests
│   ├── test_state_*.py                # State persistence tests
│   ├── test_steering_daemon.py        # Steering daemon tests
│   ├── integration/                   # Integration tests
│   │   ├── conftest.py
│   │   ├── test_latency_control.py    # End-to-end steering tests
│   │   ├── framework/                 # Test utilities
│   │   └── profiles/                  # Test profiles
│   └── test_wan_controller_state.py   # WANController state tests
│
├── pyproject.toml                     # Project metadata, dependencies, build config
├── requirements.txt                   # (deprecated) use pyproject.toml
├── CLAUDE.md                          # Project guidance (CRITICAL: read before changes)
├── README.md                          # Public documentation
├── CHANGELOG.md                       # Version history
├── LICENSE                            # Apache 2.0
│
├── docs/                              # Documentation
│   ├── PRODUCTION_INTERVAL.md         # 50ms interval validation and justification
│   ├── PORTABLE_CONTROLLER_ARCHITECTURE.md
│   ├── CONFIG_SCHEMA.md               # YAML configuration reference
│   ├── TRANSPORT_COMPARISON.md        # SSH vs REST performance
│   └── ...
│
├── systemd/                           # Systemd unit files
│   ├── wanctl@spectrum.service        # autorate_continuous for spectrum WAN
│   ├── wanctl@att.service             # autorate_continuous for att WAN
│   ├── wanctl-steering.timer          # 2s timer for steering daemon
│   └── wanctl-steering.service        # steering daemon service
│
├── configs/                           # Example configurations
│   └── wanctl.yaml                    # Example config (YAML format)
│
└── scripts/                           # Operational scripts
    └── soak-monitor.sh                # Health/status monitoring
```

## Directory Purposes

**`src/wanctl/` - Core Application:**
- Purpose: Production-ready dual-daemon adaptive CAKE control system
- Contains: Entry points, controllers, transport layers, utilities
- Key files: autorate_continuous.py (50ms daemon), steering/daemon.py (2s daemon)

**`src/wanctl/backends/` - Router Abstraction:**
- Purpose: Support multiple router platforms through pluggable backend interface
- Contains: Abstract base class, MikroTik RouterOS implementation
- Current: RouterOS (SSH via paramiko, REST via requests)
- Extensible: Can add OpenWrt, pfSense backends without changing core logic

**`src/wanctl/steering/` - WAN Steering Subsystem:**
- Purpose: Latency-sensitive traffic routing to alternate WAN
- Contains: Daemon loop, CAKE stats reader, congestion assessment, Phase2B validation
- Usage: Runs every 2 seconds on primary WAN controller, reads autorate baseline RTT

**`tests/` - Test Suite:**
- Purpose: 594 unit tests covering all major modules
- Contains: Unit tests (single components), integration tests (end-to-end)
- Execution: `pytest tests/` runs all; `pytest tests/test_autorate*.py` filters by pattern

**`docs/` - Technical Documentation:**
- Purpose: Deep dives into architectural decisions
- Critical files:
  - PRODUCTION_INTERVAL.md: Justifies 50ms cycle interval
  - PORTABLE_CONTROLLER_ARCHITECTURE.md: Design principles for link-agnostic operation
  - CONFIG_SCHEMA.md: Full YAML configuration reference

## Key File Locations

**Entry Points:**
- `src/wanctl/autorate_continuous.py:main()` - Primary daemon (50ms control loop)
- `src/wanctl/steering/daemon.py:main()` - Secondary daemon (2s steering timer)
- `src/wanctl/calibrate.py:main()` - Calibration tool

**Configuration:**
- `src/wanctl/config_base.py` - Configuration loading (YAML → Python objects)
- `src/wanctl/config_validation_utils.py` - Field-level validators
- `pyproject.toml` - Project metadata, dependencies

**Core Logic:**
- `src/wanctl/autorate_continuous.py` - BandwidthController (rate state machine)
- `src/wanctl/autorate_continuous.py` - WANController (per-WAN aggregator)
- `src/wanctl/steering/daemon.py` - SteeringDaemon (routing orchestrator)
- `src/wanctl/steering/congestion_assessment.py` - Multi-signal assessment

**Testing:**
- `tests/conftest.py` - Pytest fixtures and configuration
- `tests/test_autorate_*.py` - Autorate controller tests
- `tests/test_steering_daemon.py` - Steering daemon tests
- `tests/integration/` - End-to-end integration tests

**Utilities:**
- `src/wanctl/error_handling.py` - Error handling decorators
- `src/wanctl/retry_utils.py` - Retry with exponential backoff
- `src/wanctl/metrics.py` - Prometheus-compatible metrics
- `src/wanctl/lock_utils.py` - File-based locks
- `src/wanctl/logging_utils.py` - Dual-file logging

**State Persistence:**
- `src/wanctl/wan_controller_state.py` - Autorate state schema and I/O
- `src/wanctl/state_manager.py` - Base classes and field validators
- `src/wanctl/state_utils.py` - Atomic JSON file I/O

**Transport/Network:**
- `src/wanctl/router_client.py` - Transport factory (SSH vs REST)
- `src/wanctl/routeros_ssh.py` - SSH client (paramiko wrapper)
- `src/wanctl/routeros_rest.py` - REST API client (requests wrapper)
- `src/wanctl/backends/base.py` - Router backend interface
- `src/wanctl/backends/routeros.py` - MikroTik backend implementation

**Observability:**
- `src/wanctl/metrics.py` - Prometheus metrics registry and HTTP server
- `src/wanctl/health_check.py` - Health status endpoint
- `src/wanctl/logging_utils.py` - Dual-file logging (main + debug)

## Naming Conventions

**Files:**
- `*.py` - Python source files
- Module files: lowercase, underscores for word separation (snake_case)
- Example: `autorate_continuous.py`, `wan_controller_state.py`

**Directories:**
- Core: `src/wanctl/` (package root)
- Subsystems: `src/wanctl/{subsystem}/` (backends/, steering/)
- Tests: `tests/` with parallel structure to src

**Classes:**
- PascalCase for all classes (Config, BandwidthController, RouterBackend, etc.)
- Abstract base classes: Lead with descriptive name + suffix (RouterBackend)
- Implementation classes: Descriptor + implementation name (RouterOSBackend, RouterOSSSH)

**Functions:**
- snake_case for all functions
- Private (module-level): leading underscore prefix (_get_nested)
- Public decorators/utilities: clear purpose names (handle_errors, enforce_rate_bounds)

**Constants:**
- SCREAMING_SNAKE_CASE for module-level constants
- Example: DEFAULT_BASELINE_UPDATE_THRESHOLD_MS, CYCLE_INTERVAL_SECONDS

**Type Aliases:**
- PascalCase for TypeVars and aliases
- Example: F = TypeVar("F", bound=Callable[..., Any])

## Where to Add New Code

**New Feature (rate control enhancement):**
- Primary code: `src/wanctl/autorate_continuous.py` (BandwidthController or WANController)
- Tests: `tests/test_autorate_*.py` (create or extend existing)
- Integration test: `tests/integration/test_latency_control.py` (if affects steering)

**New Router Backend (e.g., OpenWrt):**
- Implementation: `src/wanctl/backends/openwrt.py` (subclass RouterBackend)
- Register: `src/wanctl/backends/__init__.py` (add to get_backend() factory)
- Tests: `tests/test_backends_openwrt.py`

**New Measurement Strategy:**
- Location: `src/wanctl/rtt_measurement.py` or new file (e.g., `latency_measurement.py`)
- Pattern: Subclass RTTMeasurement or add new RTTAggregationStrategy enum value
- Tests: `tests/test_rtt_measurement.py`

**New Utility/Helper:**
- Shared: `src/wanctl/{utility_name}_utils.py` (follow naming pattern)
- Tests: `tests/test_{utility_name}_utils.py`
- Error handling: Add to `src/wanctl/error_handling.py` (consolidates patterns)

**New Configuration Option:**
- Schema: `src/wanctl/config_base.py` (add to SCHEMA list)
- Validator: `src/wanctl/config_validation_utils.py` (if custom validation needed)
- Tests: `tests/test_config_*.py` (validation edge cases)

**Documentation:**
- Feature explanation: `docs/` (new .md file as needed)
- Configuration reference: `docs/CONFIG_SCHEMA.md`
- Deployment guide: `docs/DEPLOYMENT.md` (if new)

## Special Directories

**`.planning/` - GSD Planning Directory:**
- Purpose: Generated by `/gsd:map-codebase` and `/gsd:plan-phase`
- Generated: Yes (do not commit; .gitignore prevents it)
- Committed: No
- Contents: Phase plans, codebase analysis, implementation specs

**`systemd/` - Systemd Unit Files:**
- Purpose: Service and timer definitions for deployment
- Generated: No (source-controlled)
- Committed: Yes
- Usage: `systemctl start wanctl@spectrum` for autorate, timers for steering

**`configs/` - Example Configuration:**
- Purpose: Reference YAML configuration
- Generated: No
- Committed: Yes (public-safe example only, no real credentials)
- Usage: Users copy and customize for their deployment

**`scripts/` - Operational Tools:**
- Purpose: Deployment, monitoring, debugging helpers
- Generated: No
- Committed: Yes
- Usage: Called from systemd or manually for diagnostics

**`.mypy_cache/`, `.pytest_cache/`, `.ruff_cache/`:**
- Purpose: Build artifacts (linting, type checking, testing)
- Generated: Yes (during development/CI)
- Committed: No (.gitignore enforces)

**`.venv/` - Virtual Environment:**
- Purpose: Isolated Python environment (uv managed)
- Generated: Yes (created by `uv sync`)
- Committed: No (.gitignore enforces)

---

*Structure analysis: 2026-01-21*
