# Codebase Structure

**Analysis Date:** 2026-01-09

## Directory Layout

```
wanctl/
├── src/wanctl/                 # Main source code
│   ├── __init__.py
│   ├── autorate_continuous.py  # Continuous bandwidth control loop
│   ├── calibrate.py            # Baseline RTT discovery utility
│   ├── baseline_rtt_manager.py # EWMA baseline tracking
│   ├── config_base.py          # Configuration schema and loading
│   ├── config_validation_utils.py # Validation rules for all config values
│   ├── error_handling.py        # Error handling decorator
│   ├── lock_utils.py            # Lock file acquisition and cleanup
│   ├── lockfile.py             # File-based locking implementation
│   ├── logging_utils.py        # Logging setup and utilities
│   ├── rate_utils.py           # Bandwidth rate limiting and bounds
│   ├── retry_utils.py          # Retry logic with backoff
│   ├── rtt_measurement.py      # RTT measurement and aggregation
│   ├── router_client.py        # Factory for REST/SSH clients
│   ├── routeros_rest.py        # RouterOS REST API client
│   ├── routeros_ssh.py         # RouterOS SSH client
│   ├── state_manager.py        # State persistence and schema
│   ├── state_utils.py          # State file utilities
│   ├── timeouts.py             # Timeout constants
│   │
│   └── steering/               # Multi-WAN steering daemon
│       ├── __init__.py
│       ├── daemon.py           # Main steering control loop
│       ├── cake_stats.py       # CAKE queue statistics reader
│       ├── congestion_assessment.py # Congestion state machine
│       └── steering_confidence.py   # Confidence scoring for decisions
│
├── tests/                      # Unit tests
│   ├── test_config_validation_utils.py
│   ├── test_baseline_rtt_manager.py
│   ├── test_rate_utils.py
│   ├── test_rtt_measurement.py
│   └── (and others)
│
├── configs/                    # Configuration examples
│   ├── examples/
│   │   ├── spectrum.yaml.example
│   │   ├── att.yaml.example
│   │   └── steering_config.yaml.example
│   ├── spectrum.yaml           # Spectrum (cable) config
│   ├── att.yaml                # AT&T (DSL) config
│   ├── steering_config.yaml    # Steering daemon config
│   └── logrotate-cake          # Log rotation config
│
├── docker/                     # Containerization
│   ├── Dockerfile             # Multi-stage build (deploy image)
│   ├── docker-compose.yml     # Multi-WAN deployment example
│   └── .dockerignore          # Build context exclusions
│
├── scripts/                    # Deployment and utility scripts
│   ├── deploy.sh              # Unified deployment script
│   ├── install.sh             # System installation
│   └── (and others)
│
├── docs/                       # Documentation
│   ├── DESIGN.md              # Overall system design
│   ├── PHASE_*.md             # Phase implementation details
│   ├── SYNTHETIC_TRAFFIC_DISABLED.md
│   └── (and others)
│
├── CLAUDE.md                   # Developer guide
├── DEVELOPMENT.md             # Development setup guide
├── README.md                  # User-facing documentation
├── pyproject.toml             # Project configuration and dependencies
├── uv.lock                    # Dependency lock file
├── LICENSE                    # GPL v2
└── .gitignore                 # Git exclusions
```

## Directory Purposes

**src/wanctl/**
- Purpose: Core application logic
- Contains: Python modules for bandwidth control, routing, state management
- Organization: Flat structure with one-shot commands (calibrate) and daemons (autorate_continuous, steering/daemon)
- Subdirectories: steering/ for multi-WAN steering logic

**src/wanctl/steering/**
- Purpose: Multi-WAN traffic steering
- Contains: Daemon loop, congestion assessment, confidence scoring, CAKE stats
- Key files: daemon.py (main entry), congestion_assessment.py (state machine)

**tests/**
- Purpose: Unit test suite
- Contains: Test files (one per module)
- Naming: test_*.py files with pytest
- Coverage: Core validation, state management, measurements

**configs/**
- Purpose: Configuration examples and templates
- Contains: YAML files for different WAN types (Spectrum cable, AT&T DSL)
- Key files: spectrum.yaml (production config), steering_config.yaml
- Subdirectories: examples/ has .example templates

**docker/**
- Purpose: Containerization for deployment
- Contains: Multi-stage Dockerfile, Docker Compose for multi-WAN
- Key files: Dockerfile (application image), docker-compose.yml (orchestration)

**scripts/**
- Purpose: Deployment and installation
- Contains: Bash scripts for system setup
- Key files: deploy.sh (unified deployment), install.sh (system installation)

**docs/**
- Purpose: Developer and user documentation
- Contains: Design docs, phase documentation, operational guides
- Key files: DESIGN.md (architecture), PHASE_*.md (development phases)

## Key File Locations

**Entry Points:**
- `src/wanctl/autorate_continuous.py` - Continuous bandwidth control (main())
- `src/wanctl/steering/daemon.py` - Multi-WAN steering (main())
- `src/wanctl/calibrate.py` - Baseline RTT discovery utility

**Configuration:**
- `pyproject.toml` - Project manifest, dependencies, build config
- `configs/spectrum.yaml` - Production configuration (Spectrum cable)
- `configs/steering_config.yaml` - Steering daemon configuration

**Core Logic:**
- `src/wanctl/autorate_continuous.py` - Control loop and state machine
- `src/wanctl/steering/daemon.py` - Steering control and decision making
- `src/wanctl/config_validation_utils.py` - All validation rules (centralized)

**Infrastructure:**
- `src/wanctl/state_manager.py` - State persistence
- `src/wanctl/router_client.py` - Router API abstraction (factory pattern)
- `src/wanctl/lockfile.py` - File-based locking

**Testing:**
- `tests/test_config_validation_utils.py` - Validation tests (590 lines)
- `tests/test_baseline_rtt_manager.py` - Baseline RTT tests

**Documentation:**
- `CLAUDE.md` - Developer guide (detailed for this project)
- `README.md` - User-facing introduction and features
- `DEVELOPMENT.md` - Development setup instructions

## Naming Conventions

**Files:**
- snake_case.py for modules (autorate_continuous.py, config_base.py)
- test_*.py for test files (test_rate_utils.py)
- Deployment scripts: deploy.sh, install.sh (lowercase with hyphens)

**Directories:**
- snake_case for directories (src/wanctl/, configs/, scripts/)
- steering/ for multi-WAN steering subsystem

**Classes:**
- PascalCase for classes (WANController, RouterOS, StateManager)
- BaseClassName for base classes (BaseConfig)

**Functions:**
- snake_case for functions (update_state_machine, read_stats)
- Async functions: async def function_name()

**Constants:**
- UPPER_SNAKE_CASE for module-level constants (DEFAULT_BAD_THRESHOLD_MS)
- Private constants: _leading_underscore (not enforced)

## Where to Add New Code

**New Feature:**
- Core logic: `src/wanctl/<feature_name>.py`
- Tests: `tests/test_<feature_name>.py`
- Config schema: Add to `src/wanctl/config_base.py` SCHEMA

**New Steering Component:**
- Implementation: `src/wanctl/steering/<component_name>.py`
- Tests: `tests/steering/test_<component_name>.py`

**New Daemon Mode:**
- Entry point: `src/wanctl/<mode_name>.py` with main()
- State schema: Add to `src/wanctl/state_manager.py`
- Docker: Update `docker/docker-compose.yml` for new service

**New Config Parameter:**
- Schema: Add to class SCHEMA in `src/wanctl/config_base.py`
- Validation: Add to `src/wanctl/config_validation_utils.py` if complex
- Example: Update `configs/examples/*.yaml.example`

**Utility Function:**
- Location: Create `src/wanctl/<feature>_utils.py` if > 50 lines
- Single-file utilities: Add to existing module
- Avoid: Don't create utilities for one-time operations

## Special Directories

**`.planning/`**
- Purpose: GSD project planning
- Committed: Yes (except STATE.md and ROADMAP.md during active development)
- Contents: PROJECT.md, ROADMAP.md, codebase/ analysis

**`configs/.obsolete/`**
- Purpose: Old configuration files
- Committed: Yes (for historical reference)
- Status: Not used in current deployments

**`docker/`**
- Purpose: Container definitions
- Image: Python 3.12 slim base, installs dependencies, copies src/
- Deployment: Multi-WAN setup via docker-compose

---

*Structure analysis: 2026-01-09*
*Update when directory structure changes*
