"""Behavioral integration tests for autorate-steering daemon state file interface.

These tests verify the contract between WANControllerState (autorate writer) and
BaselineLoader (steering reader) using REAL file I/O through state_utils.py.

Only mocking: logger and BaselineLoader config object.
No mocking: file operations, WANControllerState, BaselineLoader core logic.
"""

import json
import logging
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from wanctl.steering.daemon import BaselineLoader
from wanctl.wan_controller_state import WANControllerState


@pytest.fixture
def state_file(tmp_path: Path) -> Path:
    """Return a temp file path for state."""
    return tmp_path / "test_state.json"


@pytest.fixture
def logger() -> logging.Logger:
    """Return a real logger (not MagicMock) for production-like behavior."""
    return logging.getLogger("test_daemon_interaction")


@pytest.fixture
def make_writer(state_file: Path, logger: logging.Logger):
    """Factory for WANControllerState instances pointing at the temp file."""

    def _make(wan_name: str = "TestWAN") -> WANControllerState:
        return WANControllerState(state_file=state_file, logger=logger, wan_name=wan_name)

    return _make


@pytest.fixture
def make_loader(state_file: Path, logger: logging.Logger):
    """Factory for BaselineLoader instances pointing at the same temp file."""

    def _make(
        baseline_rtt_min: float = 10.0,
        baseline_rtt_max: float = 60.0,
    ) -> BaselineLoader:
        config = MagicMock()
        config.primary_state_file = state_file
        config.baseline_rtt_min = baseline_rtt_min
        config.baseline_rtt_max = baseline_rtt_max
        return BaselineLoader(config=config, logger=logger)

    return _make


def _write_state(writer: WANControllerState, baseline_rtt: float, load_rtt: float = 30.0) -> None:
    """Helper to write state with the given baseline_rtt."""
    writer.save(
        download={
            "green_streak": 0,
            "soft_red_streak": 0,
            "red_streak": 0,
            "current_rate": 920_000_000,
        },
        upload={
            "green_streak": 0,
            "soft_red_streak": 0,
            "red_streak": 0,
            "current_rate": 40_000_000,
        },
        ewma={"baseline_rtt": baseline_rtt, "load_rtt": load_rtt},
        last_applied={"dl_rate": 920_000_000, "ul_rate": 40_000_000},
        force=True,
    )


class TestAutorateSteeringStateInterface:
    """Behavioral integration tests for the autorate->steering state file contract."""

    def test_write_then_read_baseline_rtt_round_trip(self, make_writer, make_loader):
        """Autorate writes baseline_rtt=25.0, steering reads 25.0."""
        writer = make_writer()
        loader = make_loader()

        _write_state(writer, baseline_rtt=25.0)
        baseline_rtt, wan_zone = loader.load_baseline_rtt()

        assert baseline_rtt == 25.0

    def test_baseline_below_min_returns_none(self, make_writer, make_loader):
        """Autorate writes baseline_rtt=5.0 (below min 10.0), steering returns None."""
        writer = make_writer()
        loader = make_loader(baseline_rtt_min=10.0)

        _write_state(writer, baseline_rtt=5.0)
        baseline_rtt, wan_zone = loader.load_baseline_rtt()

        assert baseline_rtt is None

    def test_baseline_above_max_returns_none(self, make_writer, make_loader):
        """Autorate writes baseline_rtt=70.0 (above max 60.0), steering returns None."""
        writer = make_writer()
        loader = make_loader(baseline_rtt_max=60.0)

        _write_state(writer, baseline_rtt=70.0)
        baseline_rtt, wan_zone = loader.load_baseline_rtt()

        assert baseline_rtt is None

    def test_missing_state_file_returns_none(self, make_loader):
        """State file does not exist, steering returns (None, None) gracefully."""
        loader = make_loader()
        baseline_rtt, wan_zone = loader.load_baseline_rtt()

        assert baseline_rtt is None
        assert wan_zone is None

    def test_corrupted_json_returns_none(self, state_file, make_loader):
        """State file contains corrupted JSON, steering returns (None, None) gracefully."""
        state_file.write_text("{invalid json content!!!}")

        loader = make_loader()
        baseline_rtt, wan_zone = loader.load_baseline_rtt()

        assert baseline_rtt is None
        assert wan_zone is None

    def test_second_write_overwrites_first(self, make_writer, make_loader):
        """Autorate writes twice (25.0 then 30.0), steering reads latest (30.0)."""
        writer = make_writer()
        loader = make_loader()

        _write_state(writer, baseline_rtt=25.0)
        _write_state(writer, baseline_rtt=30.0)

        baseline_rtt, wan_zone = loader.load_baseline_rtt()
        assert baseline_rtt == 30.0

    def test_full_round_trip_complete_state(self, make_writer, make_loader):
        """Full round-trip: WANControllerState.save() writes complete state,
        BaselineLoader extracts just baseline_rtt correctly."""
        writer = make_writer()
        loader = make_loader()

        # Write with all fields populated
        writer.save(
            download={
                "green_streak": 5,
                "soft_red_streak": 2,
                "red_streak": 0,
                "current_rate": 800_000_000,
            },
            upload={
                "green_streak": 3,
                "soft_red_streak": 0,
                "red_streak": 1,
                "current_rate": 35_000_000,
            },
            ewma={"baseline_rtt": 22.5, "load_rtt": 28.3},
            last_applied={"dl_rate": 800_000_000, "ul_rate": 35_000_000},
            force=True,
        )

        baseline_rtt, wan_zone = loader.load_baseline_rtt()
        assert baseline_rtt == 22.5

    def test_boundary_values_at_min_max(self, make_writer, make_loader):
        """Baseline RTT exactly at min and max boundaries should be accepted."""
        writer = make_writer()

        # At min boundary
        loader_min = make_loader(baseline_rtt_min=10.0, baseline_rtt_max=60.0)
        _write_state(writer, baseline_rtt=10.0)
        baseline_rtt_min_val, _ = loader_min.load_baseline_rtt()
        assert baseline_rtt_min_val == 10.0

        # At max boundary
        loader_max = make_loader(baseline_rtt_min=10.0, baseline_rtt_max=60.0)
        _write_state(writer, baseline_rtt=60.0)
        baseline_rtt_max_val, _ = loader_max.load_baseline_rtt()
        assert baseline_rtt_max_val == 60.0


class TestAutorateSteeringStateContract:
    """Schema-pinning contract tests for the autorate->steering state file.

    Unlike TestAutorateSteeringStateInterface above which tests behavioral
    round-trips through BaselineLoader, these tests inspect the RAW JSON
    written by WANControllerState.save(). They pin the exact key paths that
    the steering daemon depends on.

    If a key is renamed on the writer side (wan_controller_state.py), these
    tests fail even if the reader side (BaselineLoader) is updated in sync.
    This catches silent schema drift that behavioral tests would miss.
    """

    def test_ewma_baseline_rtt_key_path_exists(self, make_writer, state_file):
        """ewma.baseline_rtt key path must exist in raw JSON."""
        writer = make_writer()
        _write_state(writer, baseline_rtt=25.0)

        raw = json.loads(state_file.read_text())
        assert "ewma" in raw
        assert "baseline_rtt" in raw["ewma"]

    def test_ewma_load_rtt_key_path_exists(self, make_writer, state_file):
        """ewma.load_rtt key path must exist in raw JSON."""
        writer = make_writer()
        _write_state(writer, baseline_rtt=25.0, load_rtt=30.0)

        raw = json.loads(state_file.read_text())
        assert "load_rtt" in raw["ewma"]

    def test_congestion_dl_state_key_path_exists(self, make_writer, state_file):
        """congestion.dl_state key path must exist when congestion is provided."""
        writer = make_writer()
        writer.save(
            download={
                "green_streak": 0,
                "soft_red_streak": 0,
                "red_streak": 0,
                "current_rate": 920_000_000,
            },
            upload={
                "green_streak": 0,
                "soft_red_streak": 0,
                "red_streak": 0,
                "current_rate": 40_000_000,
            },
            ewma={"baseline_rtt": 25.0, "load_rtt": 30.0},
            last_applied={"dl_rate": 920_000_000, "ul_rate": 40_000_000},
            congestion={"dl_state": "GREEN", "ul_state": "GREEN"},
            force=True,
        )

        raw = json.loads(state_file.read_text())
        assert "congestion" in raw
        assert "dl_state" in raw["congestion"]

    def test_congestion_ul_state_key_path_exists(self, make_writer, state_file):
        """congestion.ul_state key path must exist when congestion is provided."""
        writer = make_writer()
        writer.save(
            download={
                "green_streak": 0,
                "soft_red_streak": 0,
                "red_streak": 0,
                "current_rate": 920_000_000,
            },
            upload={
                "green_streak": 0,
                "soft_red_streak": 0,
                "red_streak": 0,
                "current_rate": 40_000_000,
            },
            ewma={"baseline_rtt": 25.0, "load_rtt": 30.0},
            last_applied={"dl_rate": 920_000_000, "ul_rate": 40_000_000},
            congestion={"dl_state": "RED", "ul_state": "YELLOW"},
            force=True,
        )

        raw = json.loads(state_file.read_text())
        assert "ul_state" in raw["congestion"]

    def test_top_level_tracked_sections_exist(self, make_writer, state_file):
        """All top-level sections required by steering must be present."""
        writer = make_writer()
        _write_state(writer, baseline_rtt=25.0)

        raw = json.loads(state_file.read_text())
        for key in ("download", "upload", "ewma", "last_applied", "timestamp"):
            assert key in raw, f"Missing required top-level key: {key}"

    def test_download_section_has_required_keys(self, make_writer, state_file):
        """download section must contain all hysteresis counters and current_rate."""
        writer = make_writer()
        _write_state(writer, baseline_rtt=25.0)

        raw = json.loads(state_file.read_text())
        for key in ("green_streak", "soft_red_streak", "red_streak", "current_rate"):
            assert key in raw["download"], f"Missing download key: {key}"

    def test_upload_section_has_required_keys(self, make_writer, state_file):
        """upload section must contain all hysteresis counters and current_rate."""
        writer = make_writer()
        _write_state(writer, baseline_rtt=25.0)

        raw = json.loads(state_file.read_text())
        for key in ("green_streak", "soft_red_streak", "red_streak", "current_rate"):
            assert key in raw["upload"], f"Missing upload key: {key}"
