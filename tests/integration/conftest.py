"""Pytest configuration for integration tests.

Provides fixtures and markers for latency validation tests.
"""

import shutil
from pathlib import Path

import pytest


def pytest_configure(config: pytest.Config) -> None:
    """Register custom markers."""
    config.addinivalue_line(
        "markers",
        "integration: marks tests as integration tests (deselect with '-m \"not integration\"')",
    )
    config.addinivalue_line(
        "markers",
        "slow: marks tests as slow (deselect with '-m \"not slow\"')",
    )


def pytest_addoption(parser: pytest.Parser) -> None:
    """Add integration test CLI options."""
    parser.addoption(
        "--with-controller",
        action="store_true",
        default=False,
        help="Enable controller monitoring via SSH to cake-spectrum",
    )
    parser.addoption(
        "--integration-output",
        type=str,
        default="/tmp/wanctl_validation",
        help="Directory for integration test output files",
    )


@pytest.fixture
def with_controller(request: pytest.FixtureRequest) -> bool:
    """Get controller monitoring flag from CLI."""
    return request.config.getoption("--with-controller", default=False)


@pytest.fixture
def integration_output_dir(request: pytest.FixtureRequest) -> Path:
    """Get integration test output directory."""
    output_dir = Path(request.config.getoption("--integration-output"))
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


@pytest.fixture(scope="session")
def check_dependencies() -> dict[str, bool]:
    """Check which test dependencies are available."""
    return {
        "flent": shutil.which("flent") is not None,
        "netperf": shutil.which("netperf") is not None,
        "fping": shutil.which("fping") is not None,
        "ping": shutil.which("ping") is not None,
    }


@pytest.fixture(autouse=True)
def skip_if_missing_deps(
    request: pytest.FixtureRequest,
    check_dependencies: dict[str, bool],
) -> None:
    """Skip integration tests if required dependencies are missing."""
    if request.node.get_closest_marker("integration"):
        # Need at least one load generator
        if not check_dependencies["flent"] and not check_dependencies["netperf"]:
            pytest.skip("No load generator available (need flent or netperf)")

        # Need at least one ping tool
        if not check_dependencies["fping"] and not check_dependencies["ping"]:
            pytest.skip("No ping tool available (need fping or ping)")
