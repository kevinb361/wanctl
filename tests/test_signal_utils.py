"""Unit tests for signal handling utilities."""

import signal
from unittest.mock import patch

from wanctl.signal_utils import (
    _shutdown_event,
    _signal_handler,
    get_shutdown_event,
    is_shutdown_requested,
    register_signal_handlers,
    reset_shutdown_state,
    wait_for_shutdown,
)


class TestSignalUtils:
    """Tests for signal handling utilities."""

    def setup_method(self):
        """Reset shutdown state before each test."""
        reset_shutdown_state()

    def teardown_method(self):
        """Reset shutdown state after each test."""
        reset_shutdown_state()

    def test_is_shutdown_requested_returns_false_when_not_set(self):
        """Test is_shutdown_requested returns False when event not set."""
        assert not is_shutdown_requested()

    def test_is_shutdown_requested_returns_true_when_set(self):
        """Test is_shutdown_requested returns True after event set."""
        _shutdown_event.set()
        assert is_shutdown_requested()

    def test_signal_handler_sets_shutdown_event(self):
        """Test _signal_handler sets the shutdown event."""
        assert not _shutdown_event.is_set()
        _signal_handler(signal.SIGTERM, None)
        assert _shutdown_event.is_set()

    def test_signal_handler_works_for_sigterm(self):
        """Test _signal_handler works for SIGTERM."""
        _signal_handler(signal.SIGTERM, None)
        assert is_shutdown_requested()

    def test_signal_handler_works_for_sigint(self):
        """Test _signal_handler works for SIGINT."""
        reset_shutdown_state()  # Ensure clean state
        _signal_handler(signal.SIGINT, None)
        assert is_shutdown_requested()

    def test_register_signal_handlers_with_sigterm(self):
        """Test register_signal_handlers registers both SIGTERM and SIGINT."""
        with patch("wanctl.signal_utils.signal.signal") as mock_signal:
            register_signal_handlers(include_sigterm=True)

            # Should have registered both signals
            assert mock_signal.call_count == 2
            calls = [call[0] for call in mock_signal.call_args_list]
            assert (signal.SIGTERM, _signal_handler) in calls
            assert (signal.SIGINT, _signal_handler) in calls

    def test_register_signal_handlers_without_sigterm(self):
        """Test register_signal_handlers with include_sigterm=False."""
        with patch("wanctl.signal_utils.signal.signal") as mock_signal:
            register_signal_handlers(include_sigterm=False)

            # Should only register SIGINT
            assert mock_signal.call_count == 1
            mock_signal.assert_called_once_with(signal.SIGINT, _signal_handler)

    def test_get_shutdown_event_returns_module_event(self):
        """Test get_shutdown_event returns the module-level Event."""
        event = get_shutdown_event()
        assert event is _shutdown_event

    def test_get_shutdown_event_returns_same_object(self):
        """Test get_shutdown_event returns the same object on repeated calls."""
        event1 = get_shutdown_event()
        event2 = get_shutdown_event()
        assert event1 is event2

    def test_wait_for_shutdown_returns_true_when_set(self):
        """Test wait_for_shutdown returns True immediately when event set."""
        _shutdown_event.set()
        result = wait_for_shutdown(timeout=None)
        assert result is True

    def test_wait_for_shutdown_returns_false_on_timeout(self):
        """Test wait_for_shutdown returns False after timeout when not set."""
        result = wait_for_shutdown(timeout=0.01)  # 10ms timeout
        assert result is False

    def test_wait_for_shutdown_blocks_then_returns(self):
        """Test wait_for_shutdown blocks until event set or timeout."""
        import threading
        import time

        result_holder = [None]

        def set_event_after_delay():
            time.sleep(0.02)  # 20ms delay
            _shutdown_event.set()

        # Start thread to set event after delay
        thread = threading.Thread(target=set_event_after_delay)
        thread.start()

        # Wait should return True when event is set
        result = wait_for_shutdown(timeout=0.5)  # 500ms max timeout
        result_holder[0] = result

        thread.join()
        assert result_holder[0] is True

    def test_reset_shutdown_state_clears_event(self):
        """Test reset_shutdown_state clears the event."""
        _shutdown_event.set()
        assert _shutdown_event.is_set()

        reset_shutdown_state()

        assert not _shutdown_event.is_set()

    def test_reset_shutdown_state_makes_is_shutdown_return_false(self):
        """Test reset_shutdown_state makes is_shutdown_requested return False."""
        _shutdown_event.set()
        assert is_shutdown_requested()

        reset_shutdown_state()

        assert not is_shutdown_requested()

    def test_signal_handler_idempotent(self):
        """Test calling _signal_handler multiple times is safe."""
        _signal_handler(signal.SIGTERM, None)
        _signal_handler(signal.SIGTERM, None)
        _signal_handler(signal.SIGINT, None)

        # Should still be set
        assert is_shutdown_requested()

    def test_event_modification_via_get_shutdown_event(self):
        """Test setting event via get_shutdown_event reflects in is_shutdown_requested."""
        event = get_shutdown_event()
        assert not is_shutdown_requested()

        event.set()

        assert is_shutdown_requested()
