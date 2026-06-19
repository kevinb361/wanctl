# Codebase Structure

**Analysis Date:** 2026-06-19

## Directory Layout

```
wanctl/
├── src/wanctl/              # All production Python source
│   ├── backends/            # RouterBackend implementations (RouterOS, Linux CAKE, netlink)
│   ├── dashboard/           # Optional Textual TUI and widgets
│   │   └── widgets/         # Individual panel widgets
│   ├── steering/            # Steering daemon and supporting modules
│   ├── storage/             # SQLite persistence layer
│   └── tuning/              # Adaptive parameter tuning
│       └── strategies/      # Individual tuning strategy functions
├── tests/                   # All tests (mirrors src/wanctl structure)
│   ├── backends/            # Backend-specific tests
│   ├── dashboard/           # Dashboard widget tests
│   ├── fixtures/            # Replay corpora and fixture generators
│   ├── integration/         # Integration test framework
│   │   └── steering_replay/ # Steering replay harness
│   ├── phase226/            # Phase-specific test stubs
│   ├── steering/            # Steering daemon tests
│   ├── storage/             # Storage layer tests
│   └── tuning/              # Tuning layer tests
├── configs/                 # Active deployment YAML configs (not committed secrets)
│   ├── examples/            # Example YAML templates (cable, dsl, fiber, steering)
│   ├── cake-autorate/       # cake-autorate config fragments
│   └── bench/               # Benchmark configs
├── deploy/                  # Deployment artifacts
│   ├── systemd/             # systemd unit files
│   ├── nftables/            # nftables config fragments
│   └── sysctl/              # sysctl tuning files
├── scripts/                 # Operational and phase-specific scripts
│   └── monitoring/          # Monitoring helpers
├── docs/                    # Documentation
│   ├── RUNBOOKS/            # Operational runbooks
│   └── archive/             # Archived docs
├── docker/                  # Docker development environment
├── .claude/                 # Claude Code agents and reviews
├── .agents/                 # Skills directory (GSD)
├── .planning/               # GSD planning artifacts
│   ├── codebase/            # Codebase maps (this file)
│   ├── intel/               # Precomputed JSON intelligence
│   └── phases/              # Per-phase planning and summaries
├── pyproject.toml           # Project metadata, deps, ruff/mypy config
├── CLAUDE.md                # Project guidance for Claude/Codex
└── CHANGELOG.md             # Version history
```

## Directory Purposes

**`src/wanctl/`:**
- Purpose: All production code; no sub-package has standalone executables
- Key files: `autorate_continuous.py` (main daemon), `wan_controller.py` (control loop), `queue_controller.py` (state machine), `rtt_measurement.py` (RTT), `health_check.py` (HTTP health), `metrics.py` (Prometheus)

**`src/wanctl/backends/`:**
- Purpose: Router backend implementations behind `RouterBackend` ABC
- Key files: `base.py` (ABC), `routeros.py` (RouterOS REST/SSH), `linux_cake.py` (tc subprocess), `netlink_cake.py` (pyroute2 netlink), `linux_cake_adapter.py` (adapter bridging two backends to set_limits() API)

**`src/wanctl/steering/`:**
- Purpose: Steering daemon and its supporting modules; runs as a separate process
- Key files: `daemon.py` (main steering loop), `congestion_assessment.py`, `cake_stats.py`, `health.py`, `steering_confidence.py`

**`src/wanctl/storage/`:**
- Purpose: SQLite time-series metrics persistence with retention and downsampling
- Key files: `writer.py` (singleton MetricsWriter), `reader.py` (query functions), `schema.py` (tables), `downsampler.py`, `retention.py`, `deferred_writer.py` (background I/O)

**`src/wanctl/tuning/`:**
- Purpose: Adaptive parameter tuning from historical metrics
- Key files: `analyzer.py` (queries metrics, runs strategies), `applier.py` (applies results), `models.py` (TuningResult, TuningConfig, SafetyBounds), `safety.py`
- Key subdirectory: `strategies/` — individual pure-function strategy modules

**`src/wanctl/dashboard/`:**
- Purpose: Optional Textual TUI; requires `pip install wanctl[dashboard]`
- Key files: `app.py` (entry point, DashboardApp), `poller.py` (endpoint poller), `config.py`

**`tests/`:**
- Purpose: All test code; organized to mirror `src/wanctl/` structure
- Key files: `conftest.py` (root fixtures), `helpers.py` (shared test utilities)
- Notable: Many `test_phase*.py` files are mutation-boundary and phase-gate tests that pin behavior at specific phase close commits

**`tests/fixtures/`:**
- Purpose: Pre-recorded replay corpora and generators for deterministic integration tests
- Key files: `phase201_replay_corpus.py`, `phase206_replay_corpus.py`

**`tests/integration/`:**
- Purpose: Integration-level tests using fake backends and replay harnesses
- Key files: `framework/controller_monitor.py`, `steering_replay/replay_harness.py`

**`configs/`:**
- Purpose: Live deployment YAML configs and examples; not version-controlled secrets
- Key files: `spectrum.yaml`, `att.yaml`, `steering.yaml` (active configs)
- Key files: `examples/cable.yaml.example`, `dsl.yaml.example`, `fiber.yaml.example` (templates)

**`deploy/systemd/`:**
- Purpose: systemd unit files for all service modes
- Key files: `wanctl@.service` (pure wanctl controller template), `steering.service`, `cake-autorate-spectrum.service`, `cake-autorate-att.service`, `cake-autorate-spectrum-state-bridge.service`, `cake-autorate-att-state-bridge.service`

**`scripts/`:**
- Purpose: Operational scripts, phase-specific preflight/gate/rollback scripts, analysis helpers
- NOT part of the Python package; invoked directly or from CI/deploy workflows

## Key File Locations

**Entry Points:**
- `src/wanctl/autorate_continuous.py`: `main()` for `wanctl` command (autorate daemon)
- `src/wanctl/steering/daemon.py`: `main()` for `wanctl-steering` command
- `src/wanctl/dashboard/app.py`: `main()` for `wanctl-dashboard` command
- `src/wanctl/history.py`: `main()` for `wanctl-history` command
- `src/wanctl/operator_summary.py`: `main()` for `wanctl-operator-summary` command
- All entry points registered in `pyproject.toml:[project.scripts]`

**Configuration:**
- `src/wanctl/config_base.py`: `BaseConfig` with schema validation helpers
- `src/wanctl/autorate_config.py`: `Config(BaseConfig)` for autorate YAML
- `src/wanctl/timeouts.py`: Timeout constants
- `configs/examples/`: YAML templates for new deployments

**Core Logic:**
- `src/wanctl/wan_controller.py`: `WANController` — 50ms cycle, EWMA, congestion assessment, rate application
- `src/wanctl/queue_controller.py`: `QueueController` — 4-state (DL) and 3-state (UL) bandwidth state machines
- `src/wanctl/signal_processing.py`: `SignalProcessor` — Hampel filter, jitter, confidence
- `src/wanctl/rtt_backend_factory.py`: `build_rtt_backend()` — backend selection and `RttBackendHandle` construction
- `src/wanctl/cake_signal.py`: `CakeSignalProcessor` — CAKE qdisc signal processing (drop rate, backlog, peak delay)

**Testing:**
- `tests/conftest.py`: Root pytest fixtures
- `tests/helpers.py`: Shared test utility functions
- `tests/fixtures/`: Replay corpora for integration tests

**Deployment:**
- `scripts/install.sh`: Full install to `/opt/wanctl`
- `scripts/deploy.sh`: Deploy update
- `scripts/install-systemd.sh`: Install systemd units

## Naming Conventions

**Files:**
- `snake_case.py` for all Python modules
- `test_<module_name>.py` for unit tests (co-located at `tests/` root or mirrored subdirectory)
- `test_phase<NNN>_<desc>.py` for phase-specific gate/boundary tests
- `*.yaml.example` for config templates in `configs/examples/`
- `<phase>-<desc>.sh` for phase-specific operational scripts in `scripts/`

**Directories:**
- `snake_case` for Python packages under `src/wanctl/`
- No `__init__.py` needed except where sub-packages export a public API (storage, tuning, backends, steering, dashboard all have `__init__.py`)

**Classes:**
- `PascalCase` — `WANController`, `QueueController`, `LinuxCakeAdapter`, `MetricsWriter`
- Acronyms in names: WAN, RTT, EWMA, CAKE are spelled out in class names (not abbreviated further)

**Constants:**
- `UPPER_SNAKE_CASE` — `CYCLE_INTERVAL_SECONDS`, `STATE_ENCODING`, `DEFAULT_MAINTENANCE_INTERVAL`

**Private attributes:**
- `_single_underscore` for internal state (`_dl_zone`, `_fusion_enabled`, `_tuning_state`)
- `_explicit` suffix on presence-flag booleans that gate optional YAML features (`_docsis_mode_explicit`, `_setpoint_mbps_explicit`)

## Where to Add New Code

**New congestion signal / detection feature:**
- Signal processing: `src/wanctl/signal_processing.py` or new module alongside it
- CAKE signal: extend `src/wanctl/cake_signal.py`
- Integrate into cycle: add `_run_<feature>()` helper in `src/wanctl/wan_controller.py` and call from `run_cycle()`
- Tests: `tests/test_<feature>.py`

**New router backend:**
- Implement `RouterBackend` ABC: create `src/wanctl/backends/<platform>.py`
- Register in factory: add `elif transport == "<name>":` to `src/wanctl/backends/__init__.py:get_backend()`
- Tests: `tests/backends/test_<platform>.py`

**New RTT measurement backend:**
- Implement `RttBackend` Protocol structurally: create `src/wanctl/fping_measurement.py`-style module
- Integrate in factory: `src/wanctl/rtt_backend_factory.py:build_rtt_backend()`
- Tests: `tests/test_<backend>_measurement.py`

**New YAML config section:**
- Add schema entries to `Config.SCHEMA` in `src/wanctl/autorate_config.py`
- Add typed dict if needed, add accessor property or dict attribute
- Add presence-flag attribute (`_feature_explicit`) if the feature is optional and can coexist with legacy configs
- Tests: `tests/test_autorate_config.py` or `tests/test_check_config.py`

**New tuning strategy:**
- Create `src/wanctl/tuning/strategies/<strategy_name>.py` returning `TuningResult | None`
- Register strategy function with `TuningAnalyzer`
- Tests: `tests/tuning/test_<strategy_name>_strategies.py`

**New steering capability:**
- Extend `src/wanctl/steering/daemon.py` or add a supporting module under `src/wanctl/steering/`
- Tests: `tests/steering/test_<capability>.py`

**New CLI tool:**
- Create `src/wanctl/<tool_name>.py` with `main()` function
- Register in `pyproject.toml:[project.scripts]`

**New storage table:**
- Add schema to `src/wanctl/storage/schema.py`
- Add write method to `src/wanctl/storage/writer.py`
- Add read function to `src/wanctl/storage/reader.py`
- Add enqueue method to `src/wanctl/storage/deferred_writer.py` if called in the hot path
- Tests: `tests/storage/test_storage_<feature>.py`

## Special Directories

**`.planning/`:**
- Purpose: GSD planning artifacts, phase documents, precomputed intelligence
- Generated: Partially (intel JSON generated by GSD commands)
- Committed: Yes

**`.planning/codebase/`:**
- Purpose: Codebase map documents consumed by `/gsd:plan-phase` and `/gsd:execute-phase`
- Generated: By `/gsd:map-codebase`
- Committed: Yes

**`.planning/intel/`:**
- Purpose: Precomputed per-file roles, API surfaces, stack metadata, arch decisions in JSON
- Generated: By GSD intel extraction
- Committed: Yes

**`.planning/phases/`:**
- Purpose: Per-phase PLAN, SUMMARY, CONTEXT, RESEARCH, REVIEWS, VALIDATION docs
- Generated: By GSD phase workflow
- Committed: Yes (archived phases may be cleaned up)

**`graphify-out/`:**
- Purpose: Knowledge graph output from `/graphify` analysis; `GRAPH_REPORT.md` for architectural orientation
- Generated: Yes
- Committed: Yes (the report; raw graph.json may be large)

**`.venv/`:**
- Purpose: Python virtual environment; managed by `uv`
- Generated: Yes, never committed

**`coverage-report/`:**
- Purpose: pytest-cov HTML reports
- Generated: Yes, never committed

---

*Structure analysis: 2026-06-19*
