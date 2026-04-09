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

    def test_build_controller_state(self, state_manager):
        """Should build correct controller state dict for both download and upload."""
        # Test with download-typical values
        result_dl = state_manager.build_controller_state(5, 1, 0, 100000000)
        assert result_dl == {
            "green_streak": 5,
            "soft_red_streak": 1,
            "red_streak": 0,
            "current_rate": 100000000,
        }

        # Test with upload-typical values
        result_ul = state_manager.build_controller_state(3, 0, 2, 20000000)
        assert result_ul == {
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


class TestDirtyStateTracking:
    """Tests for dirty state tracking optimization."""

    @pytest.fixture
    def state_file(self, tmp_path):
        """Temporary state file path."""
        return tmp_path / "test-state.json"

    @pytest.fixture
    def state_manager(self, state_file):
        """State manager instance."""
        logger = MagicMock()
        return WANControllerState(state_file, logger, "test-wan")

    @pytest.fixture
    def sample_state(self):
        """Sample state data for tests."""
        return {
            "download": {
                "green_streak": 5,
                "soft_red_streak": 0,
                "red_streak": 0,
                "current_rate": 100000000,
            },
            "upload": {
                "green_streak": 3,
                "soft_red_streak": 0,
                "red_streak": 0,
                "current_rate": 20000000,
            },
            "ewma": {"baseline_rtt": 20.0, "load_rtt": 22.0},
            "last_applied": {"dl_rate": 100000000, "ul_rate": 20000000},
        }

    def test_save_skipped_when_unchanged(self, state_manager, sample_state):
        """Consecutive saves with same data should skip disk write."""
        result1 = state_manager.save(**sample_state)
        result2 = state_manager.save(**sample_state)

        assert result1 is True  # First save writes
        assert result2 is False  # Second save skipped

    def test_save_writes_when_changed(self, state_manager, sample_state, monkeypatch):
        """Save should write when state changes AND interval has elapsed."""
        import wanctl.wan_controller_state as wcs

        clock = [100.0]
        monkeypatch.setattr(wcs.time, "monotonic", lambda: clock[0])

        result1 = state_manager.save(**sample_state)

        # Change EWMA value AND advance clock past interval
        clock[0] = 106.0
        modified_state = sample_state.copy()
        modified_state["ewma"] = {"baseline_rtt": 20.0, "load_rtt": 22.5}
        result2 = state_manager.save(**modified_state)

        assert result1 is True
        assert result2 is True  # Changed + interval elapsed, so writes

    def test_force_bypasses_dirty_check(self, state_manager, sample_state):
        """force=True should always write."""
        state_manager.save(**sample_state)
        result = state_manager.save(**sample_state, force=True)

        assert result is True  # Forced write

    def test_load_initializes_hash(self, state_manager, sample_state, state_file):
        """Loading state should initialize hash to prevent immediate rewrite."""
        # Save initial state
        state_manager.save(**sample_state)

        # Create new state manager to simulate restart
        logger = MagicMock()
        new_manager = WANControllerState(state_file, logger, "test-wan")
        new_manager.load()

        # Save same state should be skipped (hash initialized from load)
        result = new_manager.save(**sample_state)

        assert result is False  # Hash initialized from load, no change

    def test_streak_change_triggers_write(self, state_manager, sample_state, monkeypatch):
        """Changing streak counters should trigger write after interval."""
        import wanctl.wan_controller_state as wcs

        clock = [100.0]
        monkeypatch.setattr(wcs.time, "monotonic", lambda: clock[0])

        state_manager.save(**sample_state)

        clock[0] = 106.0  # Past 5s interval
        modified = sample_state.copy()
        modified["download"] = sample_state["download"].copy()
        modified["download"]["green_streak"] = 6
        result = state_manager.save(**modified)

        assert result is True

    def test_rate_change_triggers_write(self, state_manager, sample_state, monkeypatch):
        """Changing rates should trigger write after interval."""
        import wanctl.wan_controller_state as wcs

        clock = [100.0]
        monkeypatch.setattr(wcs.time, "monotonic", lambda: clock[0])

        state_manager.save(**sample_state)

        clock[0] = 106.0  # Past 5s interval
        modified = sample_state.copy()
        modified["last_applied"] = {"dl_rate": 90000000, "ul_rate": 20000000}
        result = state_manager.save(**modified)

        assert result is True


class TestCongestionZoneExport:
    """Tests for congestion zone export in state file.

    Verifies that congestion zone data (dl_state, ul_state) is written to the
    state file when provided, excluded from dirty tracking to prevent write
    amplification, and backward compatible when omitted.
    """

    @pytest.fixture
    def state_file(self, tmp_path):
        """Temporary state file path."""
        return tmp_path / "test-state.json"

    @pytest.fixture
    def state_manager(self, state_file):
        """State manager instance."""
        logger = MagicMock()
        return WANControllerState(state_file, logger, "test-wan")

    @pytest.fixture
    def sample_state(self):
        """Sample state data for tests."""
        return {
            "download": {
                "green_streak": 5,
                "soft_red_streak": 0,
                "red_streak": 0,
                "current_rate": 100000000,
            },
            "upload": {
                "green_streak": 3,
                "soft_red_streak": 0,
                "red_streak": 0,
                "current_rate": 20000000,
            },
            "ewma": {"baseline_rtt": 20.0, "load_rtt": 22.0},
            "last_applied": {"dl_rate": 100000000, "ul_rate": 20000000},
        }

    def test_congestion_written_to_state_file(self, state_manager, state_file, sample_state):
        """save() with congestion parameter writes congestion key to file."""
        state_manager.save(
            **sample_state,
            congestion={"dl_state": "RED", "ul_state": "GREEN"},
        )

        state = json.loads(state_file.read_text())
        assert "congestion" in state
        assert state["congestion"]["dl_state"] == "RED"
        assert state["congestion"]["ul_state"] == "GREEN"

    def test_both_zones_written(self, state_manager, state_file, sample_state):
        """Saved state file contains both dl_state and ul_state values."""
        state_manager.save(
            **sample_state,
            congestion={"dl_state": "YELLOW", "ul_state": "RED"},
        )

        state = json.loads(state_file.read_text())
        assert state["congestion"] == {"dl_state": "YELLOW", "ul_state": "RED"}

    def test_backward_compat_no_congestion(self, state_manager, state_file, sample_state):
        """save() without congestion parameter still works (no congestion key in file)."""
        state_manager.save(**sample_state)

        state = json.loads(state_file.read_text())
        assert "congestion" not in state

    def test_zone_change_alone_no_write(self, state_manager, sample_state):
        """Changing only congestion value should NOT trigger disk write."""
        # First save with one congestion value
        result1 = state_manager.save(
            **sample_state,
            congestion={"dl_state": "GREEN", "ul_state": "GREEN"},
        )
        # Second save with different congestion but same tracked state
        result2 = state_manager.save(
            **sample_state,
            congestion={"dl_state": "RED", "ul_state": "YELLOW"},
        )

        assert result1 is True  # First save writes
        assert result2 is False  # Zone change alone does NOT trigger write

    def test_zone_included_on_normal_write(self, state_manager, state_file, sample_state, monkeypatch):
        """When tracked state changes, congestion is included in the write."""
        import wanctl.wan_controller_state as wcs

        clock = [100.0]
        monkeypatch.setattr(wcs.time, "monotonic", lambda: clock[0])

        state_manager.save(
            **sample_state,
            congestion={"dl_state": "GREEN", "ul_state": "GREEN"},
        )

        # Change download data AND provide new congestion, advance past interval
        clock[0] = 106.0
        modified = sample_state.copy()
        modified["download"] = sample_state["download"].copy()
        modified["download"]["green_streak"] = 10
        state_manager.save(
            **modified,
            congestion={"dl_state": "RED", "ul_state": "YELLOW"},
        )

        state = json.loads(state_file.read_text())
        assert state["congestion"] == {"dl_state": "RED", "ul_state": "YELLOW"}
        assert state["download"]["green_streak"] == 10

    def test_force_save_includes_congestion(self, state_manager, state_file, sample_state):
        """force=True with congestion writes congestion to file."""
        # First save
        state_manager.save(**sample_state)
        # Force save with congestion (same tracked state)
        state_manager.save(
            **sample_state,
            congestion={"dl_state": "SOFT_RED", "ul_state": "GREEN"},
            force=True,
        )

        state = json.loads(state_file.read_text())
        assert state["congestion"] == {"dl_state": "SOFT_RED", "ul_state": "GREEN"}

    def test_load_does_not_track_congestion(self, state_manager, state_file, sample_state):
        """Loading state with congestion key should not affect dirty tracking."""
        # Save state with congestion
        state_manager.save(
            **sample_state,
            congestion={"dl_state": "RED", "ul_state": "GREEN"},
        )

        # Create new manager and load (simulates restart)
        logger = MagicMock()
        new_manager = WANControllerState(state_file, logger, "test-wan")
        new_manager.load()

        # Save same 4 tracked fields -- should be skipped (not dirty)
        result = new_manager.save(**sample_state)
        assert result is False


class TestCoalescingGate:
    """Tests for minimum-interval write coalescing gate.

    Verifies that state writes are throttled to at most once per
    MIN_SAVE_INTERVAL_SEC, reducing I/O from ~20/s to ~1/s while
    ensuring force=True always writes and dirty state is never lost.
    """

    @pytest.fixture
    def state_file(self, tmp_path):
        """Temporary state file path."""
        return tmp_path / "test-state.json"

    @pytest.fixture
    def state_manager(self, state_file):
        """State manager instance."""
        logger = MagicMock()
        return WANControllerState(state_file, logger, "test-wan")

    @pytest.fixture
    def sample_state(self):
        """Sample state data for tests."""
        return {
            "download": {
                "green_streak": 5,
                "soft_red_streak": 0,
                "red_streak": 0,
                "current_rate": 100000000,
            },
            "upload": {
                "green_streak": 3,
                "soft_red_streak": 0,
                "red_streak": 0,
                "current_rate": 20000000,
            },
            "ewma": {"baseline_rtt": 20.0, "load_rtt": 22.0},
            "last_applied": {"dl_rate": 100000000, "ul_rate": 20000000},
        }

    @pytest.fixture
    def changed_state(self, sample_state):
        """Modified state that differs from sample_state."""
        modified = sample_state.copy()
        modified["ewma"] = {"baseline_rtt": 20.0, "load_rtt": 25.0}
        return modified

    def test_first_save_always_writes(self, state_manager, sample_state):
        """First save should always write regardless of interval (no prior write time)."""
        result = state_manager.save(**sample_state)
        assert result is True

    def test_min_interval_suppresses_rapid_unchanged_saves(
        self, state_manager, sample_state, monkeypatch
    ):
        """save() returns False when state unchanged AND interval not elapsed."""
        import wanctl.wan_controller_state as wcs

        clock = [100.0]
        monkeypatch.setattr(wcs.time, "monotonic", lambda: clock[0])

        # First save at t=100.0
        state_manager.save(**sample_state)

        # Try again at t=100.5 (0.5s later, within 1.0s interval)
        clock[0] = 100.5
        result = state_manager.save(**sample_state)
        assert result is False

    def test_dirty_state_writes_even_within_interval(
        self, state_manager, sample_state, changed_state, monkeypatch
    ):
        """save() returns False when interval NOT elapsed, even if state changed."""
        import wanctl.wan_controller_state as wcs

        clock = [100.0]
        monkeypatch.setattr(wcs.time, "monotonic", lambda: clock[0])

        # First save at t=100.0
        state_manager.save(**sample_state)

        # Changed state at t=100.1 (within 5s interval)
        clock[0] = 100.1
        result = state_manager.save(**changed_state)
        assert result is False  # interval gate suppresses even dirty writes

    def test_force_bypasses_interval_gate(
        self, state_manager, sample_state, monkeypatch
    ):
        """save(force=True) bypasses both dirty tracking AND minimum interval gate."""
        import wanctl.wan_controller_state as wcs

        clock = [100.0]
        monkeypatch.setattr(wcs.time, "monotonic", lambda: clock[0])

        # First save at t=100.0
        state_manager.save(**sample_state)

        # Force save at t=100.1 (within interval, unchanged state)
        clock[0] = 100.1
        result = state_manager.save(**sample_state, force=True)
        assert result is True

    def test_force_updates_last_write_time(
        self, state_manager, sample_state, changed_state, monkeypatch
    ):
        """force=True updates _last_write_time so subsequent saves respect interval."""
        import wanctl.wan_controller_state as wcs

        clock = [100.0]
        monkeypatch.setattr(wcs.time, "monotonic", lambda: clock[0])

        # First save at t=100.0
        state_manager.save(**sample_state)

        # Force save at t=100.5
        clock[0] = 100.5
        state_manager.save(**sample_state, force=True)

        # Now try changed state at t=100.8 (only 0.3s after force save)
        # Interval gate applies — 0.3s < 5.0s, so suppressed
        clock[0] = 100.8
        result = state_manager.save(**changed_state)
        assert result is False  # interval gate suppresses even dirty writes

    def test_unchanged_state_skipped_even_after_interval(
        self, state_manager, sample_state, monkeypatch
    ):
        """save() with unchanged state returns False even after interval elapsed."""
        import wanctl.wan_controller_state as wcs

        clock = [100.0]
        monkeypatch.setattr(wcs.time, "monotonic", lambda: clock[0])

        # First save at t=100.0
        state_manager.save(**sample_state)

        # Same state at t=105.0 (well after interval)
        clock[0] = 105.0
        result = state_manager.save(**sample_state)
        assert result is False  # dirty gate still applies

    def test_changed_state_writes_after_interval_elapsed(
        self, state_manager, sample_state, changed_state, monkeypatch
    ):
        """save() with changed state writes when interval has elapsed."""
        import wanctl.wan_controller_state as wcs

        clock = [100.0]
        monkeypatch.setattr(wcs.time, "monotonic", lambda: clock[0])

        # First save at t=100.0
        state_manager.save(**sample_state)

        # Changed state at t=106.0 (after 5s interval)
        clock[0] = 106.0
        result = state_manager.save(**changed_state)
        assert result is True
