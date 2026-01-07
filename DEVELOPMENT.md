# Development Guide

This guide covers setting up a development environment for wanctl.

## Prerequisites

- Python 3.12 or later
- Git
- (Optional) A RouterOS device for integration testing

## Setting Up Your Environment

### 1. Clone the Repository

```bash
git clone https://github.com/kevinb361/wanctl.git
cd wanctl
```

### 2. Create a Virtual Environment

```bash
python3 -m venv .venv
source .venv/bin/activate  # Linux/macOS
# or
.venv\Scripts\activate     # Windows
```

### 3. Install Dependencies

```bash
# Production dependencies
pip install -r requirements.txt

# Development dependencies
pip install pytest pyflakes
```

Or using uv (faster):

```bash
uv sync
```

## Running Tests

### Run All Tests

```bash
pytest tests/ -v
```

### Run Specific Test File

```bash
pytest tests/test_config_base.py -v
```

### Run with Coverage (if pytest-cov installed)

```bash
pip install pytest-cov
pytest tests/ --cov=src/wanctl --cov-report=term-missing
```

## Linting

### Check for Errors

```bash
pyflakes src/ tests/
```

### Verify Syntax

```bash
python3 -m py_compile src/wanctl/*.py
```

## Project Structure

```
wanctl/
├── src/wanctl/               # Main package
│   ├── autorate_continuous.py  # Primary entry point
│   ├── calibrate.py            # Calibration wizard
│   ├── config_base.py          # Configuration framework
│   ├── lockfile.py             # Lock file management
│   ├── state_utils.py          # State persistence
│   ├── backends/               # Router backend implementations
│   │   ├── base.py             # Abstract interface
│   │   └── routeros.py         # MikroTik implementation
│   └── steering/               # Multi-WAN steering
│       ├── daemon.py           # Steering daemon
│       └── congestion_assessment.py
├── tests/                    # Unit tests
├── configs/examples/         # Example configurations
├── scripts/                  # Deployment scripts
├── systemd/                  # Service templates
└── docs/                     # Documentation
```

## Adding a New Router Backend

1. Create `src/wanctl/backends/<platform>.py`
2. Implement the `RouterBackend` interface:

```python
from .base import RouterBackend

class MyRouterBackend(RouterBackend):
    def connect(self) -> None:
        """Establish connection to router."""
        pass

    def get_queue_stats(self, queue_name: str) -> dict:
        """Get CAKE queue statistics."""
        pass

    def set_bandwidth(self, queue_name: str, rate_bps: int) -> None:
        """Set queue bandwidth limit."""
        pass

    def disconnect(self) -> None:
        """Close connection."""
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
python3 -m wanctl.autorate_continuous \
    --config /path/to/config.yaml \
    --debug \
    --dry-run
```

### Test SSH Connectivity

```bash
ssh -i /path/to/key admin@router-ip '/system resource print'
```

### Validate Config Syntax

```python
from wanctl.config_base import load_config
config = load_config('/path/to/config.yaml')
```

## CI/CD

GitHub Actions runs on every push and PR:

- **lint**: pyflakes static analysis
- **test**: pytest unit tests
- **syntax-check**: Python compilation check

All checks must pass before merging.

## Questions?

Open an issue on GitHub for development questions.
