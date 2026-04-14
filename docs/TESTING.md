# Testing

This project has a large pytest suite plus Makefile targets for coverage, static analysis, boundary checks, and security scans.

## Environment Setup

The development toolchain is defined in [`pyproject.toml`](/home/kevin/projects/wanctl/pyproject.toml). The simplest setup is:

```bash
uv sync --group dev
```

If you manage the virtualenv manually, create `.venv` and install the dev dependencies before using the Makefile targets.

## Default Pytest Behavior

[`pyproject.toml`](/home/kevin/projects/wanctl/pyproject.toml) configures pytest with:

- `-n auto` for parallel execution
- `--timeout=2`
- coverage settings under `[tool.coverage.*]`

That means plain `pytest` runs already inherit xdist and per-test timeouts unless you override them.

## Fast Test Commands

Use the targets in [`Makefile`](/home/kevin/projects/wanctl/Makefile):

```bash
make test
make coverage
make coverage-check
make lint
make type
make ci
```

What each target does:

- `make test`: `pytest tests/ -v`
- `make coverage`: runs pytest with terminal and HTML coverage output
- `make coverage-check`: enforces the 90% coverage threshold
- `make lint`: `ruff check src/ tests/`
- `make type`: `mypy src/wanctl/`
- `make ci`: lint, type, coverage enforcement, dead-code checks, dependency checks, boundary checks, and brittleness checks

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

## Integration Tests

Integration coverage lives in [`tests/integration/test_latency_control.py`](/home/kevin/projects/wanctl/tests/integration/test_latency_control.py).

Common entry points:

```bash
pytest tests/integration/test_latency_control.py -k quick -v
pytest tests/integration/test_latency_control.py -k standard -v
pytest tests/integration/test_latency_control.py -k standard --with-controller -v
WANCTL_TEST_HOST=192.168.1.100 pytest tests/integration/test_latency_control.py -v
```

Requirements checked by [`tests/integration/conftest.py`](/home/kevin/projects/wanctl/tests/integration/conftest.py):

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
[`wanctl-check-cake`](/home/kevin/projects/wanctl/src/wanctl/check_cake.py). This is the
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

- [`DEVELOPMENT.md`](/home/kevin/projects/wanctl/DEVELOPMENT.md)
- [`docs/GETTING-STARTED.md`](/home/kevin/projects/wanctl/docs/GETTING-STARTED.md)
- [`docs/CONFIGURATION.md`](/home/kevin/projects/wanctl/docs/CONFIGURATION.md)
