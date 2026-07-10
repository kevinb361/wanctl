"""Tests for steering_state.json write throttling (_persist_state_throttled).

The steering daemon previously persisted state unconditionally every cycle
(~2 Hz), and each save() writes the file twice (main + .backup, each fdatasync'd)
-> ~14 GB/day of SSD writes. _persist_state_throttled throttles non-forced saves
to STATE_PERSIST_MIN_INTERVAL_S while forcing on real FSM transitions and failover
actions, so recovery-critical fields are never stale on restart.
"""

from unittest.mock import MagicMock, patch

import pytest

from wanctl.steering.daemon import STATE_PERSIST_MIN_INTERVAL_S, SteeringDaemon


@pytest.fixture
def mock_state_mgr():
    state_mgr = MagicMock()
    state_mgr.state = {
        "current_state": "SPECTRUM_GOOD",
        "bad_count": 0,
        "good_count": 0,
        "baseline_rtt": 25.0,
        "history_rtt": [],
        "history_delta": [],
        "transitions": [],
        "last_transition_time": None,
        "rtt_delta_ewma": 0.0,
        "queue_ewma": 0.0,
        "cake_drops_history": [],
        "queue_depth_history": [],
        "red_count": 0,
        "congestion_state": "GREEN",
        "cake_read_failures": 0,
    }
    return state_mgr


@pytest.fixture
def daemon(mock_steering_config, mock_state_mgr):
    with patch("wanctl.steering.daemon.CakeStatsReader"):
        d = SteeringDaemon(
            config=mock_steering_config,
            state=mock_state_mgr,
            router=MagicMock(),
            rtt_measurement=MagicMock(),
            baseline_loader=MagicMock(),
            logger=MagicMock(),
        )
    d.state_mgr.save.reset_mock()
    return d


class TestPersistStateThrottled:
    """The write-throttle: force bypasses, non-forced is rate-limited."""

    def test_last_state_persist_initialized(self, daemon):
        # _init_steering_metrics runs in __init__, so the throttle timestamp exists.
        assert daemon._last_state_persist == 0.0

    def test_force_always_saves(self, daemon):
        daemon._persist_state_throttled(force=True)
        daemon.state_mgr.save.assert_called_once()

    def test_force_updates_timestamp(self, daemon):
        with patch("wanctl.steering.daemon.time.monotonic", return_value=123.0):
            daemon._persist_state_throttled(force=True)
        assert daemon._last_state_persist == 123.0

    def test_throttled_skips_within_interval(self, daemon):
        with patch("wanctl.steering.daemon.time.monotonic", return_value=100.0):
            daemon._persist_state_throttled(force=True)  # seeds timestamp
        daemon.state_mgr.save.reset_mock()
        with patch(
            "wanctl.steering.daemon.time.monotonic",
            return_value=100.0 + STATE_PERSIST_MIN_INTERVAL_S - 0.1,
        ):
            daemon._persist_state_throttled(force=False)
        daemon.state_mgr.save.assert_not_called()

    def test_throttled_saves_after_interval(self, daemon):
        with patch("wanctl.steering.daemon.time.monotonic", return_value=100.0):
            daemon._persist_state_throttled(force=True)  # seeds timestamp
        daemon.state_mgr.save.reset_mock()
        with patch(
            "wanctl.steering.daemon.time.monotonic",
            return_value=100.0 + STATE_PERSIST_MIN_INTERVAL_S + 0.1,
        ):
            daemon._persist_state_throttled(force=False)
        daemon.state_mgr.save.assert_called_once()

    def test_first_nonforced_call_saves(self, daemon):
        # _last_state_persist starts at 0.0, so the first (non-forced) call is
        # well past the interval and must persist.
        with patch("wanctl.steering.daemon.time.monotonic", return_value=1000.0):
            daemon._persist_state_throttled(force=False)
        daemon.state_mgr.save.assert_called_once()
