"""Tests for WANControllerState persistence manager."""

import json
from unittest.mock import MagicMock

import pytest

from wanctl.wan_controller_state import WANControllerState


class TestWANControllerState:
    """Tests for WANControllerState class."""

    @pytest.fixture
    def state_file(self, tmp_path):
        """Temporary state file path."""
        return tmp_path / "test-state.json"

    @pytest.fixture
    def state_manager(self, state_file):
        """State manager instance."""
        logger = MagicMock()
        return WANControllerState(state_file, logger, "test-wan")

    def test_load_returns_none_for_missing_file(self, state_manager):
        """Should return None when state file doesn't exist."""
        assert state_manager.load() is None

    def test_load_returns_state_dict(self, state_manager, state_file):
        """Should return state dict when file exists."""
        state = {
            "download": {"green_streak": 5},
            "upload": {"green_streak": 3},
            "ewma": {"baseline_rtt": 20.0},
            "last_applied": {"dl_rate": 100000000},
        }
        state_file.write_text(json.dumps(state))

        result = state_manager.load()

        assert result == state

    def test_save_creates_file(self, state_manager, state_file):
        """Should create state file on save."""
        state_manager.save(
            download={
                "green_streak": 5,
                "soft_red_streak": 0,
                "red_streak": 0,
                "current_rate": 100000000,
            },
            upload={
                "green_streak": 3,
                "soft_red_streak": 0,
                "red_streak": 0,
                "current_rate": 20000000,
            },
            ewma={"baseline_rtt": 20.0, "load_rtt": 22.0},
            last_applied={"dl_rate": 100000000, "ul_rate": 20000000},
        )

        assert state_file.exists()
        state = json.loads(state_file.read_text())
        assert "download" in state
        assert "upload" in state
        assert "ewma" in state
        assert "last_applied" in state
        assert "timestamp" in state

    def test_save_preserves_schema(self, state_manager, state_file):
        """Saved state should match expected schema exactly."""
        state_manager.save(
            download={
                "green_streak": 5,
                "soft_red_streak": 1,
                "red_streak": 0,
                "current_rate": 100000000,
            },
            upload={
                "green_streak": 3,
                "soft_red_streak": 0,
                "red_streak": 2,
                "current_rate": 20000000,
            },
            ewma={"baseline_rtt": 20.5, "load_rtt": 22.3},
            last_applied={"dl_rate": 100000000, "ul_rate": 20000000},
        )

        state = json.loads(state_file.read_text())

        # Verify schema structure
        assert state["download"]["green_streak"] == 5
        assert state["download"]["soft_red_streak"] == 1
        assert state["upload"]["red_streak"] == 2
        assert state["ewma"]["baseline_rtt"] == 20.5
        assert state["last_applied"]["dl_rate"] == 100000000

    def test_build_download_state(self, state_manager):
        """Should build correct download state dict."""
        result = state_manager.build_download_state(5, 1, 0, 100000000)

        assert result == {
            "green_streak": 5,
            "soft_red_streak": 1,
            "red_streak": 0,
            "current_rate": 100000000,
        }

    def test_build_upload_state(self, state_manager):
        """Should build correct upload state dict."""
        result = state_manager.build_upload_state(3, 0, 2, 20000000)

        assert result == {
            "green_streak": 3,
            "soft_red_streak": 0,
            "red_streak": 2,
            "current_rate": 20000000,
        }

    def test_load_invalid_json_returns_none(self, state_manager, state_file):
        """Should return None for invalid JSON."""
        state_file.write_text("not valid json {{{")

        assert state_manager.load() is None

    def test_roundtrip_preserves_data(self, state_manager, state_file):
        """Save then load should preserve all data."""
        original = {
            "download": {
                "green_streak": 5,
                "soft_red_streak": 1,
                "red_streak": 0,
                "current_rate": 100000000,
            },
            "upload": {
                "green_streak": 3,
                "soft_red_streak": 0,
                "red_streak": 2,
                "current_rate": 20000000,
            },
            "ewma": {"baseline_rtt": 20.5, "load_rtt": 22.3},
            "last_applied": {"dl_rate": 100000000, "ul_rate": 20000000},
        }

        state_manager.save(**original)
        loaded = state_manager.load()

        # Compare without timestamp
        for key in ["download", "upload", "ewma", "last_applied"]:
            assert loaded[key] == original[key]
