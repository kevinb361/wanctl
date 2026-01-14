"""Pytest configuration and shared fixtures."""

import sys
import tempfile
from pathlib import Path

import pytest

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


@pytest.fixture
def temp_dir():
    """Create a temporary directory for test files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def sample_config_data():
    """Sample configuration data for testing."""
    return {
        "wan_name": "TestWAN",
        "router": {"host": "192.168.1.1", "user": "admin", "ssh_key": "/path/to/key"},
        "queues": {"download": "WAN-Download-Test", "upload": "WAN-Upload-Test"},
        "bandwidth": {"down_max": 100, "down_min": 10, "up_max": 20, "up_min": 5},
        "logging": {"main_log": "/tmp/test.log", "debug_log": "/tmp/test_debug.log"},
        "lock_file": "/tmp/test.lock",
        "lock_timeout": 300,
    }
