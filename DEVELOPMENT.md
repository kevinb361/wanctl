# Development Guide

This guide covers setting up a development environment for wanctl.

## Prerequisites

- Python 3.11 or later
- Git
- `uv` for dependency management and tool installation
- (Optional) A RouterOS device for integration testing

## Setting Up Your Environment

### 1. Clone the Repository

```bash
git clone https://github.com/kevinb361/wanctl.git
cd wanctl
```

### 2. Install Dependencies

```bash
uv sync
```

This project’s `Makefile` expects tools in `.venv/bin/`, so `uv sync` is the supported setup path.

## Running Tests

### Run All Tests

```bash
make test
```

### Run Specific Test File

```bash
pytest tests/test_config_base.py -v
```

### Run with Coverage

```bash
make coverage
make coverage-check
```

## Linting

### Check for Errors

```bash
make lint
```

### Type Checking

```bash
make type
```

### Full Local CI Pass

```bash
make ci
```

## Project Structure

```
wanctl/
├── src/wanctl/               # Main package
│   ├── autorate_continuous.py  # Primary entry point
│   ├── calibrate.py            # Calibration wizard
│   ├── config_base.py          # Configuration framework
│   ├── lock_utils.py           # Locking helpers
│   ├── state_utils.py          # State persistence
│   ├── backends/               # Router backend implementations
│   │   ├── base.py             # Abstract interface
│   │   └── routeros.py         # MikroTik implementation
│   └── steering/               # Multi-WAN steering
│       ├── daemon.py           # Steering daemon
│       └── congestion_assessment.py
│   ├── dashboard/              # Textual dashboard
│   ├── storage/                # History and retention pipeline
│   └── tuning/                 # Adaptive tuning modules
├── tests/                    # Unit tests
├── configs/examples/         # Example configurations
├── scripts/                  # Deployment and utility scripts
├── deploy/                   # Deployment artifacts
│   ├── systemd/              # Service templates (canonical)
│   └── scripts/              # Boot-time scripts (NIC tuning)
└── docs/                     # Documentation
```

## Adding a New Router Backend

1. Create `src/wanctl/backends/<platform>.py`
2. Implement the `RouterBackend` interface:

```python
from .base import RouterBackend

class MyRouterBackend(RouterBackend):
    def get_queue_stats(self, queue_name: str) -> dict:
        """Get CAKE queue statistics."""
        pass

    def set_bandwidth(self, queue_name: str, rate_bps: int) -> None:
        """Set queue bandwidth limit."""
        pass

    def get_bandwidth(self, queue_name: str) -> int | None:
        """Read the current queue limit."""
        pass

    def enable_rule(self, comment: str) -> bool:
        """Enable a steering rule."""
        pass

    def disable_rule(self, comment: str) -> bool:
        """Disable a steering rule."""
        pass

    def is_rule_enabled(self, comment: str) -> bool | None:
        """Check a steering rule state."""
        pass
```

3. Register in `src/wanctl/backends/__init__.py`
4. Add example config in `configs/examples/`
5. Document in README

See `src/wanctl/backends/routeros.py` as a reference.

## Testing Without Hardware

The test suite uses mocks and doesn't require actual router hardware. For integration testing:

1. Use `--dry-run` flag to prevent actual changes
2. Set up a RouterOS VM (CHR) for safe testing
3. Use example configs as templates

## Common Development Tasks

### Debug a Configuration Issue

```bash
PYTHONPATH=src python -m wanctl.autorate_continuous \
    --config /path/to/config.yaml \
    --debug \
    --dry-run
```

### Test SSH Connectivity

```bash
ssh -i /path/to/key admin@router-ip '/system resource print'
```

### Validate Config Syntax

```bash
PYTHONPATH=src python -m wanctl.check_config /path/to/config.yaml
```

## CI/CD

The repo-local CI entry point is `make ci`, which runs:

- **lint**: Ruff checks
- **type**: mypy on `src/wanctl/`
- **coverage-check**: pytest with the 90% coverage threshold
- **dead-code**: Vulture plus unused-import checks
- **check-deps**: runtime dependency usage validation
- **check-boundaries**: private-boundary enforcement
- **check-brittleness**: brittle test access checks

Additional security targets are available with:

```bash
make security
```

All checks must pass before merging.

### Manual Deploy Dry-Run Gate

Deployment automation is intentionally manual-only. Push and pull-request workflows run validation only; they do not deploy and must not have production SSH keys, router credentials, or sudo authority.

When a deployment path needs CI proof, use the manual `Manual Deploy Dry Run` workflow or run the same gate locally:

```bash
scripts/deploy-dry-run-gate.sh \
    --wan spectrum \
    --target-host cake-shaper \
    --deploy-mode spectrum-cake-autorate
```

The gate runs `scripts/deploy.sh ... --dry-run` and `scripts/phase231-rollback.sh ... --dry-run`, then fails closed unless both the deploy plan and rollback plan prove they are non-mutating. Real canary deploys remain a separate operator-approved milestone.

### Read-Only Live Preflight

Before any real canary, capture live state from `cake-shaper` with the read-only preflight:

```bash
scripts/live_preflight.py --ssh-host cake-shaper
```

The preflight uses SSH only for read-only commands: service state, systemd `Conflicts=` guards, config/code presence, health endpoints, and rollback dry-run rendering. It writes JSON proof under `.planning/evidence/live-preflight/` and has no mutation mode. A passing preflight is required evidence before discussing an operator-approved one-WAN canary.

## Questions?

Open an issue on GitHub for development questions.
