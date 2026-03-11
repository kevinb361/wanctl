"""Tests for hot-loop retry parameters on transport run_cmd methods.

Verifies LOOP-01: run_cmd retry decorator uses sub-cycle delays (max_attempts=2,
initial_delay=0.05) so transient failures block at most ~100ms, not 3+ seconds.

Verifies LOOP-04: autorate main loop uses shutdown_event.wait() for
instant signal responsiveness instead of time.sleep().
"""

import inspect
import time
from unittest.mock import MagicMock, patch

import pytest

from wanctl.routeros_rest import RouterOSREST
from wanctl.routeros_ssh import RouterOSSSH


class TestSSHRunCmdRetryParams:
    """Verify RouterOSSSH.run_cmd uses sub-cycle retry parameters."""

    def test_max_attempts_is_2(self):
        """SSH run_cmd retry decorator should use max_attempts=2."""
        # The retry_with_backoff decorator wraps run_cmd; inspect the closure
        # to verify the parameters passed to the decorator.
        wrapped = RouterOSSSH.run_cmd
        # functools.wraps preserves __wrapped__, but the decorator params
        # are captured in the closure. We can inspect by looking at the
        # decorator's closure variables.
        closure_vars = _extract_retry_closure_vars(wrapped)
        assert closure_vars["max_attempts"] == 2, (
            f"Expected max_attempts=2, got {closure_vars['max_attempts']}"
        )

    def test_initial_delay_is_50ms(self):
        """SSH run_cmd retry decorator should use initial_delay=0.05."""
        wrapped = RouterOSSSH.run_cmd
        closure_vars = _extract_retry_closure_vars(wrapped)
        assert closure_vars["initial_delay"] == 0.05, (
            f"Expected initial_delay=0.05, got {closure_vars['initial_delay']}"
        )

    def test_backoff_factor_is_1(self):
        """SSH run_cmd retry decorator should use backoff_factor=1.0 (no escalation)."""
        wrapped = RouterOSSSH.run_cmd
        closure_vars = _extract_retry_closure_vars(wrapped)
        assert closure_vars["backoff_factor"] == 1.0, (
            f"Expected backoff_factor=1.0, got {closure_vars['backoff_factor']}"
        )

    def test_max_delay_is_100ms(self):
        """SSH run_cmd retry decorator should use max_delay=0.1."""
        wrapped = RouterOSSSH.run_cmd
        closure_vars = _extract_retry_closure_vars(wrapped)
        assert closure_vars["max_delay"] == 0.1, (
            f"Expected max_delay=0.1, got {closure_vars['max_delay']}"
        )


class TestRESTRunCmdRetryParams:
    """Verify RouterOSREST.run_cmd uses sub-cycle retry parameters."""

    def test_max_attempts_is_2(self):
        """REST run_cmd retry decorator should use max_attempts=2."""
        wrapped = RouterOSREST.run_cmd
        closure_vars = _extract_retry_closure_vars(wrapped)
        assert closure_vars["max_attempts"] == 2, (
            f"Expected max_attempts=2, got {closure_vars['max_attempts']}"
        )

    def test_initial_delay_is_50ms(self):
        """REST run_cmd retry decorator should use initial_delay=0.05."""
        wrapped = RouterOSREST.run_cmd
        closure_vars = _extract_retry_closure_vars(wrapped)
        assert closure_vars["initial_delay"] == 0.05, (
            f"Expected initial_delay=0.05, got {closure_vars['initial_delay']}"
        )

    def test_backoff_factor_is_1(self):
        """REST run_cmd retry decorator should use backoff_factor=1.0 (no escalation)."""
        wrapped = RouterOSREST.run_cmd
        closure_vars = _extract_retry_closure_vars(wrapped)
        assert closure_vars["backoff_factor"] == 1.0, (
            f"Expected backoff_factor=1.0, got {closure_vars['backoff_factor']}"
        )

    def test_max_delay_is_100ms(self):
        """REST run_cmd retry decorator should use max_delay=0.1."""
        wrapped = RouterOSREST.run_cmd
        closure_vars = _extract_retry_closure_vars(wrapped)
        assert closure_vars["max_delay"] == 0.1, (
            f"Expected max_delay=0.1, got {closure_vars['max_delay']}"
        )


class TestTransientFailureBlockingTime:
    """Verify total blocking time on transient failure is sub-cycle (~100ms max)."""

    def test_ssh_transient_failure_blocks_under_200ms(self):
        """SSH run_cmd with transient failure should block at most ~200ms total."""
        ssh = RouterOSSSH(
            host="192.168.1.1",
            user="admin",
            ssh_key="/tmp/fake_key",
            timeout=15,
            logger=MagicMock(),
        )

        # Create a mock client whose exec_command raises ConnectionError
        mock_client = MagicMock()
        mock_client.exec_command.side_effect = ConnectionError("Transient failure")

        with patch.object(ssh, "_ensure_connected"), \
             patch.object(ssh, "_client", mock_client):
            start = time.monotonic()
            with pytest.raises(ConnectionError):
                ssh.run_cmd("/test")
            elapsed = time.monotonic() - start

        # With max_attempts=2, initial_delay=0.05: worst case ~75ms (50ms + jitter)
        # Allow generous 200ms for test environment variance
        assert elapsed < 0.2, (
            f"Transient failure blocked for {elapsed:.3f}s, expected <0.2s"
        )


class TestAutorateShutdownEventWait:
    """Verify autorate main loop uses shutdown_event.wait for interruptible sleep."""

    def test_main_loop_uses_shutdown_event_wait(self):
        """autorate_continuous main loop should use shutdown_event.wait, not time.sleep."""
        import wanctl.autorate_continuous as ac

        source = inspect.getsource(ac)

        # The main loop sleep section should contain shutdown_event.wait
        assert "shutdown_event.wait(timeout=sleep_time)" in source, (
            "Expected shutdown_event.wait(timeout=sleep_time) in autorate_continuous.py"
        )

    def test_get_shutdown_event_imported(self):
        """autorate_continuous should import get_shutdown_event from signal_utils."""
        import wanctl.autorate_continuous as ac

        # Check that get_shutdown_event is available in the module
        assert hasattr(ac, "get_shutdown_event") or "get_shutdown_event" in inspect.getsource(ac), (
            "Expected get_shutdown_event to be imported in autorate_continuous.py"
        )


def _extract_retry_closure_vars(method) -> dict:
    """Extract retry_with_backoff parameters from a decorated method's closure.

    The retry_with_backoff decorator creates a closure chain:
    retry_with_backoff(params) -> decorator(func) -> wrapper(*args, **kwargs)

    The parameters (max_attempts, initial_delay, etc.) are captured as
    free variables in the wrapper's closure.
    """
    # The method is the wrapper function (innermost)
    closure = method.__closure__
    if closure is None:
        raise ValueError(f"Method {method.__name__} has no closure (not decorated?)")

    # Map cell names to values
    code = method.__code__
    freevars = code.co_freevars
    cell_map = dict(zip(freevars, closure, strict=False))

    result = {}
    for name in ("max_attempts", "initial_delay", "backoff_factor", "max_delay", "jitter"):
        if name in cell_map:
            result[name] = cell_map[name].cell_contents

    if not result:
        # Try one level deeper - the decorator function wraps the actual wrapper
        # Walk __wrapped__ if available
        inner = getattr(method, "__wrapped__", None)
        if inner and inner.__closure__:
            freevars = inner.__code__.co_freevars
            cell_map = dict(zip(freevars, inner.__closure__, strict=False))
            for name in ("max_attempts", "initial_delay", "backoff_factor", "max_delay", "jitter"):
                if name in cell_map:
                    result[name] = cell_map[name].cell_contents

    if not result:
        raise ValueError(
            f"Could not extract retry parameters from {method.__name__}. "
            f"Free vars: {freevars}"
        )

    return result
