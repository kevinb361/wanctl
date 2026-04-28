# Testing

This project has a large pytest suite plus Makefile targets for coverage, static analysis, boundary checks, and security scans.

## Environment Setup

The development toolchain is defined in [`pyproject.toml`](../pyproject.toml). The simplest setup is:

```bash
uv sync --group dev
```

If you manage the virtualenv manually, create `.venv` and install the dev dependencies before using the Makefile targets.

## Default Pytest Behavior

[`pyproject.toml`](../pyproject.toml) configures pytest with:

- `--cov-config=pyproject.toml`
- `--timeout=30`
- `-m 'not integration'`
- `timeout_method = "thread"`
- coverage settings under `[tool.coverage.*]`

Plain `pytest` and Makefile pytest targets therefore exclude tests marked `integration` unless you explicitly override `addopts`.

## Fast Test Commands

Use the targets in [`Makefile`](../Makefile):

```bash
make test
make coverage
make coverage-check
make lint
make type
make ci
```

What each target does:

- `make test`: `.venv/bin/pytest tests/ -v`
- `make coverage`: `.venv/bin/pytest tests/ --cov=src --cov=tests --cov-report=term-missing --cov-report=html`
- `make coverage-check`: `.venv/bin/pytest tests/ --cov=src --cov-report=term-missing --cov-fail-under=90 -p no:randomly`
- `make lint`: `.venv/bin/ruff check src/ tests/`
- `make type`: `.venv/bin/mypy src/wanctl/`
- `make ci`: `lint`, `type`, `coverage-check`, `dead-code`, `check-deps`, `check-boundaries`, and `check-brittleness`

## Running Specific Test Areas

The suite is organized by subsystem as well as top-level behavior tests.

Examples:

```bash
pytest tests/test_check_config.py -v
pytest tests/steering/ -v
pytest tests/tuning/ -v
pytest tests/dashboard/ -v
pytest tests/storage/ -v
pytest tests/backends/ -v
```

Top-level tests cover the core controller and utility modules under `src/wanctl/`. Subdirectories under `tests/` cover larger feature areas such as steering, adaptive tuning, dashboard UI, storage, backends, and integration validation.

`tests/backends/` covers router backend contracts and Linux CAKE implementations, including RouterOS-compatible APIs, `tc`-based CAKE control, netlink CAKE control, queue stats, validation, and fallback behavior.

`tests/dashboard/` covers the Textual dashboard app, widgets, layout switching, history browser/state classification, endpoint polling/backoff, config loading, and dashboard entry point wiring.

## Integration Tests

Integration coverage lives in [`tests/integration/test_latency_control.py`](../tests/integration/test_latency_control.py) and [`tests/integration/test_flapping_integration.py`](../tests/integration/test_flapping_integration.py).

Integration tests are excluded by default by `pyproject.toml` via `-m 'not integration'`. Run them by clearing pytest addopts:

Common entry points:

```bash
pytest -o addopts='' tests/integration/test_latency_control.py -k quick -v
pytest -o addopts='' tests/integration/test_latency_control.py -k standard -v
pytest -o addopts='' tests/integration/test_latency_control.py -k standard --with-controller -v
WANCTL_TEST_HOST=192.168.1.100 pytest -o addopts='' tests/integration/test_latency_control.py -v
pytest -o addopts='' tests/integration/test_flapping_integration.py -v
```

Requirements checked by [`tests/integration/conftest.py`](../tests/integration/conftest.py):

- `flent` or `netperf`
- `fping` or `ping`
- network access to the configured target host
- optional SSH access for `--with-controller`

You can skip slow or integration-marked tests with standard pytest marker selection:

```bash
pytest -m "not integration"
pytest -m "not slow"
```

## Live Router Communication Smoke Test

For a real router communication check against production-style config, use
[`wanctl-check-cake`](../src/wanctl/check_cake.py). This is the
lowest-risk live integration smoke path because it exercises transport,
authentication, and basic RouterOS reads without changing shaping state unless
you explicitly pass `--fix`.

Examples:

```bash
.venv/bin/python -m wanctl.check_cake /etc/wanctl/steering.yaml --type steering
```

Notes:

- on the current `cake-shaper` deployment, the per-WAN autorate configs use
  `linux-cake-netlink`, so they are not the right live smoke target for RouterOS
  communication
- `steering.yaml` is the correct production smoke path because it still uses the
  RouterOS REST control path

What it verifies:

- router connectivity and authentication
- RouterOS queue lookup/read paths
- mangle rule lookup for steering configs
- response parsing against a live router instead of pure mocks

Operator rule:

- do not use `--fix` during a soak unless you explicitly intend to change live router state

## Quality and Security Gates

Additional Makefile targets:

```bash
make dead-code
make check-deps
make check-boundaries
make check-lines
make security
```

These run:

- `vulture` and Ruff `F401` checks for dead code
- import-to-dependency consistency checks
- AST-based private-boundary enforcement
- function length checks
- `pip-audit`, `bandit`, `detect-secrets`, and `pip-licenses`

## Useful Local Iteration Patterns

Run one file:

```bash
pytest tests/test_deployment_contracts.py -v
```

Run one test:

```bash
pytest tests/test_check_config.py -k ambiguous -v
```

Open the HTML coverage report after `make coverage`:

```bash
xdg-open coverage-report/index.html
```

## When to Use Which Level

- Use `make test` for a quick local regression pass.
- Use `make coverage-check` before merging changes that affect behavior.
- Use `make ci` when touching shared core logic or release-sensitive paths.
- Use the integration tests when validating real latency-control behavior against a reachable test host.

## Related Docs

- [`DEVELOPMENT.md`](../DEVELOPMENT.md)
- [`GETTING-STARTED.md`](GETTING-STARTED.md)
- [`CONFIGURATION.md`](CONFIGURATION.md)
