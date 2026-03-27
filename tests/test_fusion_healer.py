"""Tests for FusionHealer state machine, Pearson accuracy, alerts, locking, and grace.

Covers:
- Incremental rolling Pearson correlation accuracy vs statistics.correlation
- ACTIVE -> SUSPENDED transition on sustained low correlation
- SUSPENDED -> RECOVERING -> ACTIVE recovery cycle
- Asymmetric hysteresis (1200 cycles suspend vs 6000 cycles recover)
- AlertEngine.fire() integration on state transitions
- Parameter locking with float('inf') sentinel
- SIGUSR1 grace period handling
- Window eviction correctness

Requirements: FUSE-01, FUSE-02, FUSE-03, FUSE-04.
"""

import math
import random
import statistics
import time
from unittest.mock import MagicMock, patch

import pytest

from wanctl.fusion_healer import FusionHealer, HealState


# =============================================================================
# HELPERS
# =============================================================================


def _feed_correlated(healer: FusionHealer, n: int, correlation: str = "high") -> None:
    """Feed n cycles of signals with approximate target correlation.

    Args:
        healer: FusionHealer instance to feed.
        n: Number of cycles.
        correlation: "high" (r~1.0), "low" (r~0.0), or "anti" (r~-1.0).
    """
    rng = random.Random(42)
    for i in range(n):
        icmp_delta = math.sin(i * 0.1)
        if correlation == "high":
            irtt_delta = math.sin(i * 0.1) + rng.gauss(0, 0.01)
        elif correlation == "low":
            irtt_delta = rng.uniform(-1, 1)
        elif correlation == "anti":
            irtt_delta = -math.sin(i * 0.1) + rng.gauss(0, 0.01)
        else:
            raise ValueError(f"Unknown correlation type: {correlation}")
        healer.tick(icmp_delta, irtt_delta)


def _make_healer(**kwargs) -> FusionHealer:
    """Create a FusionHealer with test defaults."""
    defaults = {
        "wan_name": "test",
        "alert_engine": MagicMock(),
        "parameter_locks": {},
    }
    defaults.update(kwargs)
    return FusionHealer(**defaults)


# =============================================================================
# TEST CLASSES
# =============================================================================


class TestPearsonAccuracy:
    """Verify incremental Pearson matches statistics.correlation."""

    def test_perfectly_correlated(self):
        """Perfectly correlated signals (x, 2x+1) return r > 0.99."""
        healer = _make_healer()
        rng = random.Random(42)
        for i in range(200):
            x = math.sin(i * 0.1)
            y = 2 * x + 1 + rng.gauss(0, 0.001)
            healer.tick(x, y)
        r = healer.pearson_r
        assert r is not None
        assert r > 0.99

    def test_anti_correlated(self):
        """Anti-correlated signals (x, -x) return r < -0.99."""
        healer = _make_healer()
        rng = random.Random(42)
        for i in range(200):
            x = math.sin(i * 0.1)
            y = -x + rng.gauss(0, 0.001)
            healer.tick(x, y)
        r = healer.pearson_r
        assert r is not None
        assert r < -0.99

    def test_uncorrelated(self):
        """Uncorrelated signals return |r| < 0.3."""
        healer = _make_healer()
        rng = random.Random(42)
        for i in range(500):
            x = math.sin(i * 0.1)
            y = rng.uniform(-1, 1)
            healer.tick(x, y)
        r = healer.pearson_r
        assert r is not None
        assert abs(r) < 0.3

    def test_matches_statistics_correlation(self):
        """Incremental Pearson matches statistics.correlation within 1e-10 for 1200-sample window."""
        healer = _make_healer(min_samples=50)
        rng = random.Random(42)
        xs = []
        ys = []
        for i in range(1200):
            x = math.sin(i * 0.1) + rng.gauss(0, 0.1)
            y = 0.8 * x + 0.2 * rng.gauss(0, 1)
            xs.append(x)
            ys.append(y)
            healer.tick(x, y)

        r_incremental = healer.pearson_r
        r_reference = statistics.correlation(xs, ys)
        assert r_incremental is not None
        assert abs(r_incremental - r_reference) < 1e-10

    def test_returns_none_below_min_samples(self):
        """Returns None when n < min_samples (100)."""
        healer = _make_healer(min_samples=100)
        for i in range(99):
            healer.tick(float(i), float(i))
        assert healer.pearson_r is None


class TestSuspension:
    """Verify ACTIVE -> SUSPENDED transition on sustained low correlation."""

    def test_sustained_low_correlation_suspends(self):
        """1200 cycles of low-correlation deltas transitions ACTIVE -> SUSPENDED."""
        healer = _make_healer()
        assert healer.state == HealState.ACTIVE
        # Feed enough low-correlation data for warmup + sustained detection
        _feed_correlated(healer, 1200 + 200, correlation="low")
        assert healer.state == HealState.SUSPENDED

    def test_stays_active_during_warmup(self):
        """State stays ACTIVE during warmup (first 100 cycles) even with bad correlation."""
        healer = _make_healer(min_samples=100)
        rng = random.Random(42)
        for i in range(99):
            healer.tick(math.sin(i * 0.1), rng.uniform(-1, 1))
        assert healer.state == HealState.ACTIVE

    def test_stays_active_if_correlation_oscillates(self):
        """State stays ACTIVE if correlation oscillates above/below threshold (not sustained)."""
        healer = _make_healer()
        rng = random.Random(42)
        # Alternate between correlated and uncorrelated blocks of 100 cycles
        for block in range(20):
            if block % 2 == 0:
                for i in range(100):
                    x = math.sin(i * 0.1)
                    healer.tick(x, x + rng.gauss(0, 0.01))
            else:
                for i in range(100):
                    healer.tick(math.sin(i * 0.1), rng.uniform(-1, 1))
        assert healer.state == HealState.ACTIVE


class TestRecovery:
    """Verify SUSPENDED -> RECOVERING -> ACTIVE recovery cycle."""

    def test_full_recovery_cycle(self):
        """After SUSPENDED, good correlation transitions SUSPENDED -> RECOVERING -> ACTIVE."""
        healer = _make_healer()
        # Suspend
        _feed_correlated(healer, 1500, correlation="low")
        assert healer.state == HealState.SUSPENDED

        # Recover with good correlation
        _feed_correlated(healer, 7000, correlation="high")
        assert healer.state == HealState.ACTIVE

    def test_recovering_requires_sustained_good_correlation(self):
        """RECOVERING requires recover_window_samples sustained good correlation."""
        healer = _make_healer()
        # Suspend
        _feed_correlated(healer, 1500, correlation="low")
        assert healer.state == HealState.SUSPENDED

        # Some good correlation but not enough for full recovery
        _feed_correlated(healer, 3000, correlation="high")
        # Should be in RECOVERING but not yet ACTIVE (need 6000 total good cycles
        # per the RECOVERING state -- two phases of 6000 each for SUSPENDED->RECOVERING
        # and RECOVERING->ACTIVE)
        assert healer.state in (HealState.SUSPENDED, HealState.RECOVERING)
        assert healer.state != HealState.ACTIVE


class TestHysteresis:
    """Verify asymmetric hysteresis: 1200 cycles suspend vs 6000 cycles recover."""

    def test_asymmetric_timing(self):
        """Suspension takes ~1200 cycles, recovery takes ~6000 cycles."""
        healer = _make_healer()

        # Count cycles to suspend
        rng = random.Random(42)
        suspend_cycle = None
        for i in range(2000):
            x = math.sin(i * 0.1)
            y = rng.uniform(-1, 1)
            state = healer.tick(x, y)
            if state == HealState.SUSPENDED and suspend_cycle is None:
                suspend_cycle = i
                break

        assert suspend_cycle is not None
        # Should be around 1200 + min_samples warmup
        assert 1100 < suspend_cycle < 1500

        # Count cycles to recover to ACTIVE
        rng2 = random.Random(99)
        recover_cycle = None
        for i in range(15000):
            x = math.sin(i * 0.1)
            y = x + rng2.gauss(0, 0.01)
            state = healer.tick(x, y)
            if state == HealState.ACTIVE and recover_cycle is None:
                recover_cycle = i
                break

        assert recover_cycle is not None
        # Should be around 12000 (6000 for SUSPENDED->RECOVERING + 6000 for RECOVERING->ACTIVE)
        assert recover_cycle > 5000


class TestAlerts:
    """Verify AlertEngine.fire() called on each transition."""

    def test_active_to_suspended_alert(self):
        """ACTIVE -> SUSPENDED calls alert_engine.fire with fusion_suspended."""
        alert_engine = MagicMock()
        healer = _make_healer(alert_engine=alert_engine)
        _feed_correlated(healer, 1500, correlation="low")
        assert healer.state == HealState.SUSPENDED
        alert_engine.fire.assert_any_call(
            alert_type="fusion_suspended",
            severity="warning",
            wan_name="test",
            details=pytest.approx(
                {
                    "pearson_r": pytest.approx(healer.pearson_r, abs=0.01),
                    "threshold": 0.3,
                    "state": "suspended",
                },
                abs=0.1,
            ),
            rule_key="fusion_healing",
        )

    def test_suspended_to_recovering_alert(self):
        """SUSPENDED -> RECOVERING calls alert_engine.fire with fusion_recovering."""
        alert_engine = MagicMock()
        healer = _make_healer(alert_engine=alert_engine)
        _feed_correlated(healer, 1500, correlation="low")
        assert healer.state == HealState.SUSPENDED

        _feed_correlated(healer, 7000, correlation="high")
        # Look for fusion_recovering alert in fire calls
        recovering_calls = [
            c for c in alert_engine.fire.call_args_list
            if c.kwargs.get("alert_type") == "fusion_recovering"
            or (c.args and c.args[0] == "fusion_recovering")
        ]
        assert len(recovering_calls) > 0

    def test_recovering_to_active_alert(self):
        """RECOVERING -> ACTIVE calls alert_engine.fire with fusion_recovered."""
        alert_engine = MagicMock()
        healer = _make_healer(alert_engine=alert_engine)
        _feed_correlated(healer, 1500, correlation="low")
        _feed_correlated(healer, 15000, correlation="high")
        assert healer.state == HealState.ACTIVE
        recovered_calls = [
            c for c in alert_engine.fire.call_args_list
            if c.kwargs.get("alert_type") == "fusion_recovered"
            or (c.args and c.args[0] == "fusion_recovered")
        ]
        assert len(recovered_calls) > 0


class TestParameterLock:
    """Verify parameter locking with float('inf') sentinel."""

    def test_lock_on_suspend(self):
        """Transition to SUSPENDED calls lock_parameter with float('inf')."""
        locks: dict[str, float] = {}
        healer = _make_healer(parameter_locks=locks)
        _feed_correlated(healer, 1500, correlation="low")
        assert healer.state == HealState.SUSPENDED
        assert "fusion_icmp_weight" in locks
        assert locks["fusion_icmp_weight"] == float("inf")

    def test_lock_persists_during_recovering(self):
        """Lock persists during RECOVERING state."""
        locks: dict[str, float] = {}
        healer = _make_healer(parameter_locks=locks)
        _feed_correlated(healer, 1500, correlation="low")
        assert healer.state == HealState.SUSPENDED
        assert "fusion_icmp_weight" in locks

        # Feed some good data to enter RECOVERING
        _feed_correlated(healer, 7000, correlation="high")
        # Lock should still be present regardless of intermediate state
        assert "fusion_icmp_weight" in locks

    def test_lock_cleared_on_active(self):
        """Transition to ACTIVE clears the lock."""
        locks: dict[str, float] = {}
        healer = _make_healer(parameter_locks=locks)
        _feed_correlated(healer, 1500, correlation="low")
        assert healer.state == HealState.SUSPENDED

        _feed_correlated(healer, 15000, correlation="high")
        assert healer.state == HealState.ACTIVE
        assert "fusion_icmp_weight" not in locks


class TestGracePeriod:
    """Verify SIGUSR1 grace period handling."""

    def test_resets_counters(self):
        """start_grace_period() resets sustained counters and transitions to ACTIVE."""
        healer = _make_healer()
        _feed_correlated(healer, 1500, correlation="low")
        assert healer.state == HealState.SUSPENDED

        healer.start_grace_period()
        assert healer.state == HealState.ACTIVE

    def test_no_suspend_during_grace(self):
        """During grace period, tick() does not transition to SUSPENDED."""
        with patch("wanctl.fusion_healer.time") as mock_time:
            mock_time.monotonic.return_value = 1000.0
            healer = _make_healer()

            # Start grace
            healer.start_grace_period()
            assert healer.is_grace_active

            # Feed low-correlation data during grace -- should not suspend
            rng = random.Random(42)
            for i in range(2000):
                mock_time.monotonic.return_value = 1000.0 + i * 0.001  # Stay within grace
                x = math.sin(i * 0.1)
                y = rng.uniform(-1, 1)
                healer.tick(x, y)

            assert healer.state == HealState.ACTIVE

    def test_resume_after_grace_expiry(self):
        """After grace expiry, healer resumes normal monitoring."""
        with patch("wanctl.fusion_healer.time") as mock_time:
            mock_time.monotonic.return_value = 1000.0
            healer = _make_healer(grace_period_sec=10.0, min_samples=50)

            healer.start_grace_period()

            # Move time past grace expiry
            mock_time.monotonic.return_value = 1011.0

            assert not healer.is_grace_active

            # Now feed low-correlation data -- should eventually suspend
            rng = random.Random(42)
            for i in range(2000):
                mock_time.monotonic.return_value = 1011.0 + i * 0.05
                x = math.sin(i * 0.1)
                y = rng.uniform(-1, 1)
                healer.tick(x, y)

            assert healer.state == HealState.SUSPENDED

    def test_clears_lock(self):
        """start_grace_period() clears the parameter lock."""
        locks: dict[str, float] = {}
        healer = _make_healer(parameter_locks=locks)
        _feed_correlated(healer, 1500, correlation="low")
        assert healer.state == HealState.SUSPENDED
        assert "fusion_icmp_weight" in locks

        healer.start_grace_period()
        assert "fusion_icmp_weight" not in locks


class TestWindowEviction:
    """Verify old samples evicted and Pearson still accurate after 2x window."""

    def test_eviction_accuracy(self):
        """After 2x window samples, Pearson still accurate from recent data only."""
        healer = _make_healer(min_samples=50)
        rng = random.Random(42)

        # Feed 2400 samples (2x the 1200 window) of mixed data:
        # First 1200: low correlation
        # Last 1200: high correlation
        for i in range(1200):
            x = math.sin(i * 0.1)
            y = rng.uniform(-1, 1)
            healer.tick(x, y)

        rng2 = random.Random(99)
        recent_xs = []
        recent_ys = []
        for i in range(1200):
            x = math.sin(i * 0.1)
            y = x + rng2.gauss(0, 0.01)
            recent_xs.append(x)
            recent_ys.append(y)
            healer.tick(x, y)

        r = healer.pearson_r
        r_ref = statistics.correlation(recent_xs, recent_ys)
        assert r is not None
        # After eviction, should reflect recent high-correlation data
        assert abs(r - r_ref) < 1e-10
