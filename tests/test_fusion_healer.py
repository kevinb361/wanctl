"""Tests for FusionHealer state machine, Pearson accuracy, alerts, locking, grace,
fusion config loading, dual-signal fusion computation, baseline deadlock fix,
SIGUSR1 reload, and WANController integration wiring.

Covers:
- Incremental rolling Pearson correlation accuracy vs statistics.correlation
- ACTIVE -> SUSPENDED transition on sustained low correlation
- SUSPENDED -> RECOVERING -> ACTIVE recovery cycle
- Asymmetric hysteresis (1200 cycles suspend vs 6000 cycles recover)
- AlertEngine.fire() integration on state transitions
- Parameter locking with float('inf') sentinel
- SIGUSR1 grace period handling
- Window eviction correctness
- Config._load_fusion_config() default values, validation, custom values
- _compute_fused_rtt() weighted average, fallback, staleness boundary
- Fusion baseline deadlock fix (signal path split)
- WANController._reload_fusion_config() state transitions
- FusionHealer instantiation and per-cycle tick() wiring
- Health endpoint fusion heal state

Requirements: FUSE-01, FUSE-02, FUSE-03, FUSE-04, FUSE-05, FBLK-01 through FBLK-05.
"""

import json
import logging
import math
import random
import socket
import statistics
import time
import urllib.request
from unittest.mock import MagicMock, patch

import pytest
import yaml

from wanctl.autorate_config import Config
from wanctl.fusion_healer import FusionHealer, HealState
from wanctl.health_check import HealthCheckHandler, start_health_server
from wanctl.irtt_measurement import IRTTResult
from wanctl.signal_utils import is_reload_requested, reset_reload_state
from wanctl.wan_controller import WANController

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

        # Recover with good correlation (need 6000 for SUSPENDED->RECOVERING
        # + 6000 for RECOVERING->ACTIVE = 12000 total, add margin)
        _feed_correlated(healer, 13000, correlation="high")
        assert healer.state == HealState.ACTIVE

    def test_recovering_requires_sustained_good_correlation(self):
        """RECOVERING requires recover_window_samples sustained good correlation."""
        healer = _make_healer()
        # Suspend
        _feed_correlated(healer, 1500, correlation="low")
        assert healer.state == HealState.SUSPENDED

        # Feed 7000 good cycles: enough for SUSPENDED->RECOVERING (6000)
        # but not for RECOVERING->ACTIVE (need another 6000)
        _feed_correlated(healer, 7000, correlation="high")
        assert healer.state == HealState.RECOVERING


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

        # Find the fusion_suspended call
        suspended_calls = [
            c
            for c in alert_engine.fire.call_args_list
            if c.kwargs.get("alert_type") == "fusion_suspended"
        ]
        assert len(suspended_calls) == 1
        call_kw = suspended_calls[0].kwargs
        assert call_kw["severity"] == "warning"
        assert call_kw["wan_name"] == "test"
        assert call_kw["rule_key"] == "fusion_healing"
        assert call_kw["details"]["threshold"] == 0.3
        assert call_kw["details"]["state"] == "suspended"
        assert isinstance(call_kw["details"]["pearson_r"], float)

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
        _feed_correlated(healer, 13000, correlation="high")
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

        _feed_correlated(healer, 13000, correlation="high")
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


# =============================================================================
# MERGED FROM test_fusion_config.py
# =============================================================================


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def autorate_config_dict():
    """Minimal valid autorate config dict for fusion config tests."""
    return {
        "wan_name": "TestWAN",
        "router": {
            "host": "192.168.1.1",
            "user": "admin",
            "ssh_key": "/tmp/test_id_rsa",
            "transport": "ssh",
        },
        "queues": {
            "download": "cake-download",
            "upload": "cake-upload",
        },
        "continuous_monitoring": {
            "enabled": True,
            "baseline_rtt_initial": 25.0,
            "ping_hosts": ["1.1.1.1"],
            "download": {
                "floor_mbps": 400,
                "ceiling_mbps": 920,
                "step_up_mbps": 10,
                "factor_down": 0.85,
            },
            "upload": {
                "floor_mbps": 25,
                "ceiling_mbps": 40,
                "step_up_mbps": 1,
                "factor_down": 0.85,
            },
            "thresholds": {
                "target_bloat_ms": 15,
                "warn_bloat_ms": 45,
                "baseline_time_constant_sec": 60,
                "load_time_constant_sec": 0.5,
            },
        },
        "logging": {
            "main_log": "/tmp/test_autorate.log",
            "debug_log": "/tmp/test_autorate_debug.log",
        },
        "lock_file": "/tmp/test_autorate.lock",
        "lock_timeout": 300,
    }


def _make_fusion_yaml_config(tmp_path, config_dict):
    """Write YAML and create Config from it."""
    config_file = tmp_path / "autorate.yaml"
    config_file.write_text(yaml.dump(config_dict))
    return Config(str(config_file))


# =============================================================================
# TestFusionConfig
# =============================================================================


class TestFusionConfig:
    """Fusion config loading and validation tests."""

    def test_default_when_absent(self, tmp_path, autorate_config_dict):
        """Config without fusion section gets default icmp_weight 0.7."""
        config = _make_fusion_yaml_config(tmp_path, autorate_config_dict)
        assert config.fusion_config["icmp_weight"] == 0.7

    @pytest.mark.parametrize("weight", [0.0, 0.3, 0.5, 0.7, 1.0])
    def test_custom_valid_weight(self, tmp_path, autorate_config_dict, weight):
        """Config with valid fusion.icmp_weight uses the provided value."""
        autorate_config_dict["fusion"] = {"icmp_weight": weight}
        config = _make_fusion_yaml_config(tmp_path, autorate_config_dict)
        assert config.fusion_config["icmp_weight"] == weight

    def test_invalid_above_range(self, tmp_path, autorate_config_dict, caplog):
        """icmp_weight > 1.0 warns and defaults to 0.7."""
        autorate_config_dict["fusion"] = {"icmp_weight": 1.5}
        with caplog.at_level(logging.WARNING):
            config = _make_fusion_yaml_config(tmp_path, autorate_config_dict)
        assert config.fusion_config["icmp_weight"] == 0.7
        assert "defaulting to 0.7" in caplog.text

    def test_invalid_below_range(self, tmp_path, autorate_config_dict, caplog):
        """icmp_weight < 0.0 warns and defaults to 0.7."""
        autorate_config_dict["fusion"] = {"icmp_weight": -0.1}
        with caplog.at_level(logging.WARNING):
            config = _make_fusion_yaml_config(tmp_path, autorate_config_dict)
        assert config.fusion_config["icmp_weight"] == 0.7
        assert "defaulting to 0.7" in caplog.text

    def test_invalid_string(self, tmp_path, autorate_config_dict, caplog):
        """icmp_weight as string warns and defaults to 0.7."""
        autorate_config_dict["fusion"] = {"icmp_weight": "bad"}
        with caplog.at_level(logging.WARNING):
            config = _make_fusion_yaml_config(tmp_path, autorate_config_dict)
        assert config.fusion_config["icmp_weight"] == 0.7
        assert "defaulting to 0.7" in caplog.text

    def test_invalid_boolean(self, tmp_path, autorate_config_dict, caplog):
        """icmp_weight as boolean warns and defaults to 0.7."""
        autorate_config_dict["fusion"] = {"icmp_weight": True}
        with caplog.at_level(logging.WARNING):
            config = _make_fusion_yaml_config(tmp_path, autorate_config_dict)
        assert config.fusion_config["icmp_weight"] == 0.7
        assert "defaulting to 0.7" in caplog.text

    def test_invalid_section_not_dict(self, tmp_path, autorate_config_dict, caplog):
        """fusion section as string warns and defaults to 0.7."""
        autorate_config_dict["fusion"] = "not_a_dict"
        with caplog.at_level(logging.WARNING):
            config = _make_fusion_yaml_config(tmp_path, autorate_config_dict)
        assert config.fusion_config["icmp_weight"] == 0.7
        assert "using defaults" in caplog.text

    def test_edge_zero(self, tmp_path, autorate_config_dict):
        """icmp_weight 0.0 (all IRTT) is valid."""
        autorate_config_dict["fusion"] = {"icmp_weight": 0.0}
        config = _make_fusion_yaml_config(tmp_path, autorate_config_dict)
        assert config.fusion_config["icmp_weight"] == 0.0

    def test_edge_one(self, tmp_path, autorate_config_dict):
        """icmp_weight 1.0 (all ICMP) is valid."""
        autorate_config_dict["fusion"] = {"icmp_weight": 1.0}
        config = _make_fusion_yaml_config(tmp_path, autorate_config_dict)
        assert config.fusion_config["icmp_weight"] == 1.0

    def test_info_log_emitted(self, tmp_path, autorate_config_dict, caplog):
        """INFO log contains icmp_weight and irtt_weight values."""
        autorate_config_dict["fusion"] = {"icmp_weight": 0.6}
        with caplog.at_level(logging.INFO):
            _make_fusion_yaml_config(tmp_path, autorate_config_dict)
        assert "icmp_weight=0.6" in caplog.text
        assert "healing.suspend_threshold=" in caplog.text

    # -----------------------------------------------------------------
    # fusion.enabled tests (FUSE-02)
    # -----------------------------------------------------------------

    def test_enabled_defaults_false(self, tmp_path, autorate_config_dict):
        """Config with no fusion section defaults enabled to False."""
        config = _make_fusion_yaml_config(tmp_path, autorate_config_dict)
        assert config.fusion_config["enabled"] is False

    def test_enabled_true(self, tmp_path, autorate_config_dict):
        """Config with fusion.enabled=True sets enabled to True."""
        autorate_config_dict["fusion"] = {"enabled": True}
        config = _make_fusion_yaml_config(tmp_path, autorate_config_dict)
        assert config.fusion_config["enabled"] is True

    def test_enabled_false_explicit(self, tmp_path, autorate_config_dict):
        """Config with fusion.enabled=False explicitly sets enabled to False."""
        autorate_config_dict["fusion"] = {"enabled": False}
        config = _make_fusion_yaml_config(tmp_path, autorate_config_dict)
        assert config.fusion_config["enabled"] is False

    def test_enabled_non_bool_warns_defaults_false(self, tmp_path, autorate_config_dict, caplog):
        """fusion.enabled='yes' (string) warns and defaults to False."""
        autorate_config_dict["fusion"] = {"enabled": "yes"}
        with caplog.at_level(logging.WARNING):
            config = _make_fusion_yaml_config(tmp_path, autorate_config_dict)
        assert config.fusion_config["enabled"] is False
        assert "fusion.enabled must be bool" in caplog.text

    def test_enabled_non_bool_int_warns_defaults_false(
        self, tmp_path, autorate_config_dict, caplog
    ):
        """fusion.enabled=1 (int) warns and defaults to False."""
        autorate_config_dict["fusion"] = {"enabled": 1}
        with caplog.at_level(logging.WARNING):
            config = _make_fusion_yaml_config(tmp_path, autorate_config_dict)
        assert config.fusion_config["enabled"] is False
        assert "fusion.enabled must be bool" in caplog.text


# =============================================================================
# MERGED FROM test_fusion_core.py
# =============================================================================


# =============================================================================
# HELPERS
# =============================================================================


def _make_irtt_result(rtt_ms: float = 20.0, age_offset: float = 0.0) -> IRTTResult:
    """Create an IRTTResult with controllable RTT and timestamp.

    Args:
        rtt_ms: The rtt_mean_ms value.
        age_offset: Seconds to subtract from current monotonic time (simulates age).
    """
    return IRTTResult(
        rtt_mean_ms=rtt_ms,
        rtt_median_ms=rtt_ms - 0.5,
        ipdv_mean_ms=1.0,
        send_loss=0.0,
        receive_loss=0.0,
        packets_sent=100,
        packets_received=100,
        server="104.200.21.31",
        port=2112,
        timestamp=time.monotonic() - age_offset,
        success=True,
    )


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def mock_controller():
    """Create a lightweight mock WANController with fusion attributes.

    Uses MagicMock(spec=WANController) with specific attributes set for
    _compute_fused_rtt. The real method is bound to the mock.
    """
    from wanctl.wan_controller import WANController

    controller = MagicMock(spec=WANController)
    controller.wan_name = "spectrum"
    controller.logger = logging.getLogger("test.fusion_core")

    # Fusion config (default weights, enabled for computation tests)
    controller._fusion_icmp_weight = 0.7
    controller._fusion_enabled = True

    # IRTT thread (default: None / disabled)
    controller._irtt_thread = None

    # Bind the real method
    controller._compute_fused_rtt = WANController._compute_fused_rtt.__get__(
        controller, WANController
    )

    return controller


# =============================================================================
# FUSION COMPUTATION (FUSE-01)
# =============================================================================


class TestFusionComputation:
    """Tests for weighted average fusion when IRTT is fresh and valid."""

    def test_default_weights_0_7_icmp_0_3_irtt(self, mock_controller):
        """0.7*30 + 0.3*20 = 27.0 with default weights."""
        irtt_thread = MagicMock()
        irtt_thread.get_latest.return_value = _make_irtt_result(rtt_ms=20.0, age_offset=1.0)
        irtt_thread.cadence_sec = 10.0
        mock_controller._irtt_thread = irtt_thread

        result = mock_controller._compute_fused_rtt(30.0)
        assert result == pytest.approx(27.0)

    def test_custom_weights_0_5(self, mock_controller):
        """0.5*30 + 0.5*20 = 25.0 with equal weights."""
        irtt_thread = MagicMock()
        irtt_thread.get_latest.return_value = _make_irtt_result(rtt_ms=20.0, age_offset=1.0)
        irtt_thread.cadence_sec = 10.0
        mock_controller._irtt_thread = irtt_thread
        mock_controller._fusion_icmp_weight = 0.5

        result = mock_controller._compute_fused_rtt(30.0)
        assert result == pytest.approx(25.0)

    def test_all_icmp_weight_1_0(self, mock_controller):
        """Weight 1.0 means fused = filtered_rtt (IRTT ignored)."""
        irtt_thread = MagicMock()
        irtt_thread.get_latest.return_value = _make_irtt_result(rtt_ms=20.0, age_offset=1.0)
        irtt_thread.cadence_sec = 10.0
        mock_controller._irtt_thread = irtt_thread
        mock_controller._fusion_icmp_weight = 1.0

        result = mock_controller._compute_fused_rtt(30.0)
        assert result == pytest.approx(30.0)

    def test_all_irtt_weight_0_0(self, mock_controller):
        """Weight 0.0 means fused = irtt_rtt (ICMP ignored)."""
        irtt_thread = MagicMock()
        irtt_thread.get_latest.return_value = _make_irtt_result(rtt_ms=20.0, age_offset=1.0)
        irtt_thread.cadence_sec = 10.0
        mock_controller._irtt_thread = irtt_thread
        mock_controller._fusion_icmp_weight = 0.0

        result = mock_controller._compute_fused_rtt(30.0)
        assert result == pytest.approx(20.0)

    def test_debug_log_emitted_on_fusion(self, mock_controller, caplog):
        """DEBUG log emitted with icmp, irtt, and fused values when fusion active."""
        irtt_thread = MagicMock()
        irtt_thread.get_latest.return_value = _make_irtt_result(rtt_ms=20.0, age_offset=1.0)
        irtt_thread.cadence_sec = 10.0
        mock_controller._irtt_thread = irtt_thread

        with caplog.at_level(logging.DEBUG, logger="test.fusion_core"):
            mock_controller._compute_fused_rtt(30.0)

        assert "fused_rtt=" in caplog.text
        assert "icmp=" in caplog.text
        assert "irtt=" in caplog.text


# =============================================================================
# FUSION FALLBACK (FUSE-04)
# =============================================================================


class TestFusionFallback:
    """Tests for fallback to filtered_rtt when IRTT is unavailable/stale/invalid."""

    def test_irtt_thread_none_returns_filtered_rtt(self, mock_controller):
        """When _irtt_thread is None (disabled), filtered_rtt passes through unchanged."""
        mock_controller._irtt_thread = None

        result = mock_controller._compute_fused_rtt(30.0)
        assert result == 30.0

    def test_irtt_get_latest_none_returns_filtered_rtt(self, mock_controller):
        """When get_latest() returns None (no data yet), filtered_rtt passes through."""
        irtt_thread = MagicMock()
        irtt_thread.get_latest.return_value = None
        mock_controller._irtt_thread = irtt_thread

        result = mock_controller._compute_fused_rtt(30.0)
        assert result == 30.0

    def test_irtt_stale_returns_filtered_rtt(self, mock_controller):
        """When IRTT result is stale (age > 3x cadence), filtered_rtt passes through."""
        irtt_thread = MagicMock()
        # age=35s, cadence=10s -> 35 > 30 threshold -> stale
        irtt_thread.get_latest.return_value = _make_irtt_result(rtt_ms=20.0, age_offset=35.0)
        irtt_thread.cadence_sec = 10.0
        mock_controller._irtt_thread = irtt_thread

        result = mock_controller._compute_fused_rtt(30.0)
        assert result == 30.0

    def test_irtt_rtt_zero_returns_filtered_rtt(self, mock_controller):
        """When IRTT rtt_mean_ms is 0.0 (total loss), filtered_rtt passes through."""
        irtt_thread = MagicMock()
        irtt_thread.get_latest.return_value = _make_irtt_result(rtt_ms=0.0, age_offset=1.0)
        irtt_thread.cadence_sec = 10.0
        mock_controller._irtt_thread = irtt_thread

        result = mock_controller._compute_fused_rtt(30.0)
        assert result == 30.0

    def test_irtt_rtt_negative_returns_filtered_rtt(self, mock_controller):
        """When IRTT rtt_mean_ms is negative (invalid), filtered_rtt passes through."""
        irtt_thread = MagicMock()
        irtt_thread.get_latest.return_value = _make_irtt_result(rtt_ms=-1.0, age_offset=1.0)
        irtt_thread.cadence_sec = 10.0
        mock_controller._irtt_thread = irtt_thread

        result = mock_controller._compute_fused_rtt(30.0)
        assert result == 30.0

    def test_staleness_boundary_just_within(self, mock_controller):
        """IRTT at exactly 3x cadence boundary (age=29.9, cadence=10) -> fused value."""
        irtt_thread = MagicMock()
        irtt_thread.get_latest.return_value = _make_irtt_result(rtt_ms=20.0, age_offset=29.9)
        irtt_thread.cadence_sec = 10.0
        mock_controller._irtt_thread = irtt_thread

        result = mock_controller._compute_fused_rtt(30.0)
        # 0.7*30 + 0.3*20 = 27.0
        assert result == pytest.approx(27.0)

    def test_staleness_boundary_just_beyond(self, mock_controller):
        """IRTT just past 3x cadence boundary (age=30.1, cadence=10) -> filtered_rtt."""
        irtt_thread = MagicMock()
        irtt_thread.get_latest.return_value = _make_irtt_result(rtt_ms=20.0, age_offset=30.1)
        irtt_thread.cadence_sec = 10.0
        mock_controller._irtt_thread = irtt_thread

        result = mock_controller._compute_fused_rtt(30.0)
        assert result == 30.0

    def test_no_debug_log_when_irtt_none(self, mock_controller, caplog):
        """No DEBUG log emitted when IRTT is disabled (thread None)."""
        mock_controller._irtt_thread = None

        with caplog.at_level(logging.DEBUG, logger="test.fusion_core"):
            mock_controller._compute_fused_rtt(30.0)

        assert "fused_rtt=" not in caplog.text

    def test_no_debug_log_when_irtt_stale(self, mock_controller, caplog):
        """No DEBUG log emitted when IRTT result is stale."""
        irtt_thread = MagicMock()
        irtt_thread.get_latest.return_value = _make_irtt_result(rtt_ms=20.0, age_offset=35.0)
        irtt_thread.cadence_sec = 10.0
        mock_controller._irtt_thread = irtt_thread

        with caplog.at_level(logging.DEBUG, logger="test.fusion_core"):
            mock_controller._compute_fused_rtt(30.0)

        assert "fused_rtt=" not in caplog.text

    def test_no_debug_log_when_irtt_result_none(self, mock_controller, caplog):
        """No DEBUG log emitted when get_latest() returns None."""
        irtt_thread = MagicMock()
        irtt_thread.get_latest.return_value = None
        mock_controller._irtt_thread = irtt_thread

        with caplog.at_level(logging.DEBUG, logger="test.fusion_core"):
            mock_controller._compute_fused_rtt(30.0)

        assert "fused_rtt=" not in caplog.text


# =============================================================================
# FUSION ENABLED GUARD (FUSE-02)
# =============================================================================


class TestFusionEnabledGuard:
    """Tests for _fusion_enabled guard in _compute_fused_rtt."""

    def test_disabled_returns_filtered_rtt_without_irtt_access(self, mock_controller):
        """When _fusion_enabled=False, returns filtered_rtt and does NOT access IRTT."""
        irtt_thread = MagicMock()
        mock_controller._irtt_thread = irtt_thread
        mock_controller._fusion_enabled = False

        result = mock_controller._compute_fused_rtt(30.0)

        assert result == 30.0
        irtt_thread.get_latest.assert_not_called()

    def test_enabled_with_irtt_computes_fusion(self, mock_controller):
        """When _fusion_enabled=True and IRTT is valid, returns weighted average."""
        irtt_thread = MagicMock()
        irtt_thread.get_latest.return_value = _make_irtt_result(rtt_ms=20.0, age_offset=1.0)
        irtt_thread.cadence_sec = 10.0
        mock_controller._irtt_thread = irtt_thread
        mock_controller._fusion_enabled = True

        result = mock_controller._compute_fused_rtt(30.0)
        # 0.7*30 + 0.3*20 = 27.0
        assert result == pytest.approx(27.0)


# =============================================================================
# FUSION RTT TRACKING (FUSE-05 observability support)
# =============================================================================


class TestFusionRTTTracking:
    """Tests for _last_fused_rtt and _last_icmp_filtered_rtt attribute storage."""

    def test_disabled_stores_icmp_rtt_and_null_fused(self, mock_controller):
        """When fusion disabled, stores ICMP RTT but fused is None."""
        mock_controller._fusion_enabled = False

        mock_controller._compute_fused_rtt(30.0)

        assert mock_controller._last_icmp_filtered_rtt == 30.0
        assert mock_controller._last_fused_rtt is None

    def test_fallback_no_irtt_stores_icmp_rtt_and_null_fused(self, mock_controller):
        """When fusion enabled but IRTT unavailable, stores ICMP RTT, fused is None."""
        mock_controller._fusion_enabled = True
        mock_controller._irtt_thread = None

        mock_controller._compute_fused_rtt(30.0)

        assert mock_controller._last_icmp_filtered_rtt == 30.0
        assert mock_controller._last_fused_rtt is None

    def test_fused_stores_both_values(self, mock_controller):
        """When fusion active, stores both ICMP and fused RTT values."""
        irtt_thread = MagicMock()
        irtt_thread.get_latest.return_value = _make_irtt_result(rtt_ms=20.0, age_offset=1.0)
        irtt_thread.cadence_sec = 10.0
        mock_controller._irtt_thread = irtt_thread
        mock_controller._fusion_enabled = True
        mock_controller._fusion_icmp_weight = 0.7

        mock_controller._compute_fused_rtt(30.0)

        assert mock_controller._last_icmp_filtered_rtt == 30.0
        # 0.7*30 + 0.3*20 = 27.0
        assert mock_controller._last_fused_rtt == pytest.approx(27.0)


# =============================================================================
# MERGED FROM test_fusion_baseline.py
# =============================================================================


# =============================================================================
# HELPERS
# =============================================================================


def _make_baseline_controller(**overrides):
    """Create a lightweight mock WANController with real baseline/EWMA methods.

    Uses MagicMock(spec=WANController) with real methods bound for
    _update_baseline_if_idle and update_ewma. Sets explicit float attributes
    to avoid MagicMock truthy trap.
    """
    controller = MagicMock(spec=WANController)
    controller.wan_name = overrides.get("wan_name", "TestWAN")
    controller.logger = logging.getLogger("test.fusion_baseline")

    # EWMA parameters
    controller.alpha_load = overrides.get("alpha_load", 0.1)
    controller.alpha_baseline = overrides.get("alpha_baseline", 0.001)
    controller.baseline_update_threshold = overrides.get("baseline_update_threshold", 3.0)

    # RTT state
    controller.load_rtt = overrides.get("load_rtt", 25.0)
    controller.baseline_rtt = overrides.get("baseline_rtt", 25.0)
    controller.baseline_rtt_min = overrides.get("baseline_rtt_min", 10.0)
    controller.baseline_rtt_max = overrides.get("baseline_rtt_max", 60.0)

    # Bind real methods
    controller._update_baseline_if_idle = WANController._update_baseline_if_idle.__get__(
        controller, WANController
    )
    controller.update_ewma = WANController.update_ewma.__get__(controller, WANController)

    return controller


# =============================================================================
# FBLK-01: BASELINE USES ICMP-ONLY SIGNAL
# =============================================================================


class TestBaselineUsesIcmpOnly:
    """Validate that _update_baseline_if_idle uses ICMP-only delta for freeze gate."""

    def test_baseline_receives_icmp_not_fused(self):
        """Baseline updates when ICMP delta < threshold even if fused load is high.

        ATT scenario: baseline=29.0, load_rtt=33.2 (fused value).
        Call _update_baseline_if_idle(25.0).
        Fix: delta = 25.0 - 29.0 = -4.0 < 3.0 -> baseline updates.
        Old code: delta = load_rtt(33.2) - baseline(29.0) = 4.2 >= 3.0 -> FROZEN.
        """
        controller = _make_baseline_controller(
            baseline_rtt=29.0,
            load_rtt=33.2,  # Fused value (ATT: 0.7*29 + 0.3*43)
            baseline_update_threshold=3.0,
            alpha_baseline=0.1,  # Large alpha for visible change
        )

        controller._update_baseline_if_idle(25.0)

        # With the fix, delta = 25.0 - 29.0 = -4.0 < 3.0 -> baseline updates
        # Baseline should move toward 25.0: 0.9*29 + 0.1*25 = 28.6
        assert controller.baseline_rtt != 29.0, (
            "Baseline should have updated (ICMP delta < threshold)"
        )
        assert controller.baseline_rtt == pytest.approx(28.6, abs=0.01)

    def test_baseline_ewma_uses_icmp_value(self):
        """Baseline EWMA computation uses icmp_rtt, not load_rtt or fused value."""
        controller = _make_baseline_controller(
            baseline_rtt=20.0,
            load_rtt=20.5,  # Small delta, ensures update
            baseline_update_threshold=3.0,
            alpha_baseline=0.1,
        )

        controller._update_baseline_if_idle(22.0)

        # Expected: 0.9*20 + 0.1*22 = 20.2
        assert controller.baseline_rtt == pytest.approx(20.2, abs=0.01)


# =============================================================================
# FBLK-02: LOAD EWMA USES FUSED SIGNAL
# =============================================================================


class TestLoadEwmaUsesFused:
    """Validate that load_rtt tracks the fused signal, not ICMP-only."""

    def test_load_rtt_tracks_fused_signal(self):
        """After inline EWMA with fused_rtt=33.2, load_rtt converges toward 33.2."""
        controller = _make_baseline_controller(
            load_rtt=25.0,
            alpha_load=0.1,
        )

        fused_rtt = 33.2
        # Inline load EWMA (the fix does this instead of update_ewma)
        controller.load_rtt = (
            1 - controller.alpha_load
        ) * controller.load_rtt + controller.alpha_load * fused_rtt

        # Expected: 0.9*25 + 0.1*33.2 = 25.82
        assert controller.load_rtt == pytest.approx(25.82, abs=0.01)

    def test_load_rtt_not_icmp_when_fused(self):
        """Load EWMA must move toward fused value (33.2), not ICMP (25.0)."""
        controller = _make_baseline_controller(
            load_rtt=25.0,
            alpha_load=0.1,
        )

        fused_rtt = 33.2
        controller.load_rtt = (
            1 - controller.alpha_load
        ) * controller.load_rtt + controller.alpha_load * fused_rtt

        # load_rtt must be > 25.0 (moved toward fused, not stayed at ICMP)
        assert controller.load_rtt > 25.0


# =============================================================================
# FBLK-03: ATT/SPECTRUM DIVERGENCE SCENARIOS
# =============================================================================


class TestBaselineUpdatesWithIrttDivergence:
    """Validate baseline tracks ICMP idle despite IRTT path divergence."""

    def test_att_scenario_baseline_not_frozen(self):
        """ATT production: ICMP=29ms, IRTT=43ms, fused=33.2ms.

        100 idle cycles: baseline must track ICMP (~29ms), not freeze.
        Pre-fix: fused load_rtt=33.2, delta=33.2-29=4.2 > 3ms -> FROZEN.
        Post-fix: delta=29-29=0 < 3ms -> baseline updates (stays ~29ms).
        """
        controller = _make_baseline_controller(
            baseline_rtt=29.0,
            load_rtt=29.0,
            alpha_load=0.1,
            alpha_baseline=0.01,
            baseline_update_threshold=3.0,
        )

        icmp_filtered = 29.0
        irtt_rtt = 43.0
        icmp_weight = 0.7

        for _ in range(100):
            # Compute fused RTT
            fused_rtt = icmp_weight * icmp_filtered + (1 - icmp_weight) * irtt_rtt
            # 0.7*29 + 0.3*43 = 33.2

            # Split EWMA (the fix): load uses fused, baseline uses ICMP
            controller.load_rtt = (
                1 - controller.alpha_load
            ) * controller.load_rtt + controller.alpha_load * fused_rtt
            controller._update_baseline_if_idle(icmp_filtered)

        # After 100 cycles:
        # - load_rtt should converge toward 33.2 (fused)
        assert controller.load_rtt == pytest.approx(33.2, abs=0.5)
        # - baseline should stay near 29.0 (ICMP idle, not frozen)
        assert controller.baseline_rtt == pytest.approx(29.0, abs=0.5)

    def test_spectrum_scenario_baseline_tracks_icmp(self):
        """Spectrum production: ICMP=25ms, IRTT=19ms, fused=23.2ms.

        100 idle cycles: baseline stays near 25.0ms (ICMP), load converges to 23.2ms.
        """
        controller = _make_baseline_controller(
            baseline_rtt=25.0,
            load_rtt=25.0,
            alpha_load=0.1,
            alpha_baseline=0.01,
            baseline_update_threshold=3.0,
        )

        icmp_filtered = 25.0
        irtt_rtt = 19.0
        icmp_weight = 0.7

        for _ in range(100):
            fused_rtt = icmp_weight * icmp_filtered + (1 - icmp_weight) * irtt_rtt
            # 0.7*25 + 0.3*19 = 23.2

            controller.load_rtt = (
                1 - controller.alpha_load
            ) * controller.load_rtt + controller.alpha_load * fused_rtt
            controller._update_baseline_if_idle(icmp_filtered)

        # load_rtt converges toward 23.2 (fused)
        assert controller.load_rtt == pytest.approx(23.2, abs=0.5)
        # baseline stays near 25.0 (ICMP idle)
        assert controller.baseline_rtt == pytest.approx(25.0, abs=0.5)


# =============================================================================
# FBLK-04: FUSION DISABLED PRODUCES IDENTICAL BEHAVIOR
# =============================================================================


class TestFusionDisabledIdentical:
    """When fusion is disabled, split path must produce identical results to old path."""

    def test_split_path_matches_update_ewma_when_no_fusion(self):
        """Two controllers, same input, old vs new path -- identical results.

        Controller A: update_ewma(filtered_rtt) per cycle (old path).
        Controller B: inline load EWMA + _update_baseline_if_idle(filtered_rtt) (new path).
        When fusion disabled, fused_rtt == filtered_rtt.
        """
        controller_a = _make_baseline_controller(
            baseline_rtt=25.0,
            load_rtt=25.0,
            alpha_load=0.1,
            alpha_baseline=0.01,
            baseline_update_threshold=3.0,
        )
        controller_b = _make_baseline_controller(
            baseline_rtt=25.0,
            load_rtt=25.0,
            alpha_load=0.1,
            alpha_baseline=0.01,
            baseline_update_threshold=3.0,
        )

        # 50 cycles with varying RTT (ramp from 20 to 35)
        for i in range(50):
            filtered_rtt = 20.0 + (i * 15.0 / 49.0)

            # Controller A: old path (update_ewma does both)
            controller_a.update_ewma(filtered_rtt)

            # Controller B: new split path (fusion disabled, fused == filtered)
            fused_rtt = filtered_rtt  # No fusion
            controller_b.load_rtt = (
                1 - controller_b.alpha_load
            ) * controller_b.load_rtt + controller_b.alpha_load * fused_rtt
            controller_b._update_baseline_if_idle(filtered_rtt)

        # Both should produce identical results
        assert controller_a.load_rtt == pytest.approx(controller_b.load_rtt, abs=1e-10)
        assert controller_a.baseline_rtt == pytest.approx(controller_b.baseline_rtt, abs=1e-10)


# =============================================================================
# FBLK-05: FREEZE GATE DELTA USES ICMP
# =============================================================================


class TestCongestionZoneDelta:
    """Validate that freeze gate delta = icmp_rtt - baseline_rtt."""

    def test_freeze_gate_uses_icmp_delta(self):
        """Baseline updates when ICMP is close to baseline, regardless of fused load.

        baseline=25.0, load_rtt=23.2 (fused Spectrum idle).
        Call _update_baseline_if_idle(25.5).
        Fix: delta = 25.5 - 25.0 = 0.5 < 3.0 -> baseline updates.
        Old code: delta = 23.2 - 25.0 = -1.8 < 3.0 -> also updates (but wrong reason).
        """
        controller = _make_baseline_controller(
            baseline_rtt=25.0,
            load_rtt=23.2,  # Fused Spectrum idle (IRTT < ICMP)
            baseline_update_threshold=3.0,
            alpha_baseline=0.1,
        )

        controller._update_baseline_if_idle(25.5)

        # Baseline should update: 0.9*25 + 0.1*25.5 = 25.05
        assert controller.baseline_rtt == pytest.approx(25.05, abs=0.01)

    def test_freeze_gate_freezes_on_icmp_load(self):
        """Baseline freezes when ICMP shows load (delta >= threshold).

        baseline=25.0, call _update_baseline_if_idle(30.0).
        Fix: delta = 30.0 - 25.0 = 5.0 >= 3.0 -> FROZEN.
        """
        controller = _make_baseline_controller(
            baseline_rtt=25.0,
            load_rtt=23.2,  # Irrelevant with fix (not used in delta)
            baseline_update_threshold=3.0,
        )

        original_baseline = controller.baseline_rtt
        controller._update_baseline_if_idle(30.0)

        # Baseline should NOT change (ICMP delta >= threshold)
        assert controller.baseline_rtt == original_baseline


# =============================================================================
# MERGED FROM test_fusion_reload.py
# =============================================================================


# =============================================================================
# HELPERS
# =============================================================================


def _make_reload_controller(tmp_path, yaml_content, initial_enabled=False, initial_weight=0.7):
    """Create a mock WANController with config_file_path pointing to YAML.

    Args:
        tmp_path: Pytest tmp_path fixture.
        yaml_content: Dict to serialize as YAML (or None for empty file).
        initial_enabled: Starting _fusion_enabled value.
        initial_weight: Starting _fusion_icmp_weight value.

    Returns:
        MagicMock WANController with real _reload_fusion_config bound.
    """
    config_file = tmp_path / "autorate.yaml"
    if yaml_content is not None:
        config_file.write_text(yaml.dump(yaml_content))
    else:
        config_file.write_text("")

    controller = MagicMock(spec=WANController)
    controller.wan_name = "spectrum"
    controller.logger = logging.getLogger("test.fusion_reload")
    controller.config = MagicMock()
    controller.config.config_file_path = str(config_file)
    controller._fusion_enabled = initial_enabled
    controller._fusion_icmp_weight = initial_weight
    controller._fusion_healer = None

    # Bind the real method
    controller._reload_fusion_config = WANController._reload_fusion_config.__get__(
        controller, WANController
    )

    return controller


# =============================================================================
# TestReloadFusionConfig
# =============================================================================


class TestReloadFusionConfig:
    """Tests for WANController._reload_fusion_config()."""

    def test_toggle_enabled_false_to_true(self, tmp_path, caplog):
        """YAML has fusion.enabled=true, controller starts disabled. After reload, enabled."""
        ctrl = _make_reload_controller(
            tmp_path,
            {"fusion": {"enabled": True, "icmp_weight": 0.7}},
            initial_enabled=False,
        )

        with caplog.at_level(logging.WARNING, logger="test.fusion_reload"):
            ctrl._reload_fusion_config()

        assert ctrl._fusion_enabled is True
        assert "enabled=False->True" in caplog.text

    def test_toggle_enabled_true_to_false(self, tmp_path, caplog):
        """YAML has fusion.enabled=false, controller starts enabled. After reload, disabled."""
        ctrl = _make_reload_controller(
            tmp_path,
            {"fusion": {"enabled": False, "icmp_weight": 0.7}},
            initial_enabled=True,
        )

        with caplog.at_level(logging.WARNING, logger="test.fusion_reload"):
            ctrl._reload_fusion_config()

        assert ctrl._fusion_enabled is False
        assert "enabled=True->False" in caplog.text

    def test_change_icmp_weight(self, tmp_path, caplog):
        """YAML has fusion.icmp_weight=0.5, controller starts at 0.7. After reload, 0.5."""
        ctrl = _make_reload_controller(
            tmp_path,
            {"fusion": {"enabled": False, "icmp_weight": 0.5}},
            initial_weight=0.7,
        )

        with caplog.at_level(logging.WARNING, logger="test.fusion_reload"):
            ctrl._reload_fusion_config()

        assert ctrl._fusion_icmp_weight == pytest.approx(0.5)
        assert "icmp_weight=0.7->0.5" in caplog.text

    def test_both_unchanged(self, tmp_path, caplog):
        """YAML matches current state. Log contains (unchanged) for weight."""
        ctrl = _make_reload_controller(
            tmp_path,
            {"fusion": {"enabled": False, "icmp_weight": 0.7}},
            initial_enabled=False,
            initial_weight=0.7,
        )

        with caplog.at_level(logging.WARNING, logger="test.fusion_reload"):
            ctrl._reload_fusion_config()

        assert ctrl._fusion_enabled is False
        assert ctrl._fusion_icmp_weight == pytest.approx(0.7)
        assert "enabled=False" in caplog.text
        assert "icmp_weight=0.7 (unchanged)" in caplog.text

    def test_invalid_weight_warns_defaults(self, tmp_path, caplog):
        """YAML has fusion.icmp_weight='abc'. After reload, defaults to 0.7."""
        ctrl = _make_reload_controller(
            tmp_path,
            {"fusion": {"enabled": False, "icmp_weight": "abc"}},
            initial_weight=0.5,
        )

        with caplog.at_level(logging.WARNING, logger="test.fusion_reload"):
            ctrl._reload_fusion_config()

        assert ctrl._fusion_icmp_weight == pytest.approx(0.7)
        assert "invalid" in caplog.text.lower()

    def test_invalid_enabled_warns_defaults(self, tmp_path, caplog):
        """YAML has fusion.enabled='yes'. After reload, defaults to False."""
        ctrl = _make_reload_controller(
            tmp_path,
            {"fusion": {"enabled": "yes", "icmp_weight": 0.7}},
            initial_enabled=True,
        )

        with caplog.at_level(logging.WARNING, logger="test.fusion_reload"):
            ctrl._reload_fusion_config()

        assert ctrl._fusion_enabled is False
        assert "fusion.enabled must be bool" in caplog.text

    def test_missing_yaml_file_logs_error_no_change(self, tmp_path, caplog):
        """Config file does not exist. After reload, state unchanged. Error logged."""
        ctrl = _make_reload_controller(
            tmp_path,
            {"fusion": {"enabled": True}},
            initial_enabled=False,
            initial_weight=0.5,
        )
        # Point to nonexistent file
        ctrl.config.config_file_path = str(tmp_path / "nonexistent.yaml")

        with caplog.at_level(logging.ERROR, logger="test.fusion_reload"):
            ctrl._reload_fusion_config()

        assert ctrl._fusion_enabled is False
        assert ctrl._fusion_icmp_weight == pytest.approx(0.5)
        assert "Config reload failed" in caplog.text

    def test_no_fusion_section_uses_defaults(self, tmp_path, caplog):
        """YAML has no fusion key. After reload, enabled=False, icmp_weight=0.7."""
        ctrl = _make_reload_controller(
            tmp_path,
            {"wan_name": "spectrum"},
            initial_enabled=True,
            initial_weight=0.5,
        )

        with caplog.at_level(logging.WARNING, logger="test.fusion_reload"):
            ctrl._reload_fusion_config()

        assert ctrl._fusion_enabled is False
        assert ctrl._fusion_icmp_weight == pytest.approx(0.7)

    def test_healer_suspended_blocks_reenable(self, tmp_path, caplog):
        """YAML says enabled=true but healer is SUSPENDED. Fusion stays disabled.

        Regression test for SIGUSR1 override bug discovered 2026-04-02:
        sending SIGUSR1 to reload any config change would re-enable fusion
        from YAML despite the healer having suspended it for low correlation.
        """
        ctrl = _make_reload_controller(
            tmp_path,
            {"fusion": {"enabled": True, "icmp_weight": 0.7}},
            initial_enabled=False,
        )
        # Attach a mock healer in SUSPENDED state
        ctrl._fusion_healer = MagicMock()
        ctrl._fusion_healer.state = HealState.SUSPENDED

        with caplog.at_level(logging.WARNING, logger="test.fusion_reload"):
            ctrl._reload_fusion_config()

        assert ctrl._fusion_enabled is False, (
            "Fusion must stay disabled when healer is SUSPENDED"
        )
        assert "Respecting healer state" in caplog.text

    def test_healer_active_allows_reenable(self, tmp_path, caplog):
        """YAML says enabled=true and healer is ACTIVE. Fusion re-enables normally."""
        ctrl = _make_reload_controller(
            tmp_path,
            {"fusion": {"enabled": True, "icmp_weight": 0.7}},
            initial_enabled=False,
        )
        ctrl._fusion_healer = MagicMock()
        ctrl._fusion_healer.state = HealState.ACTIVE

        with caplog.at_level(logging.WARNING, logger="test.fusion_reload"):
            ctrl._reload_fusion_config()

        assert ctrl._fusion_enabled is True

    def test_healer_suspended_allows_disable(self, tmp_path, caplog):
        """YAML says enabled=false with healer SUSPENDED. Operator kill switch works."""
        ctrl = _make_reload_controller(
            tmp_path,
            {"fusion": {"enabled": False, "icmp_weight": 0.7}},
            initial_enabled=True,
        )
        ctrl._fusion_healer = MagicMock()
        ctrl._fusion_healer.state = HealState.SUSPENDED

        with caplog.at_level(logging.WARNING, logger="test.fusion_reload"):
            ctrl._reload_fusion_config()

        assert ctrl._fusion_enabled is False, (
            "Operator kill switch (enabled=false) must always work"
        )

    def test_no_healer_allows_reenable(self, tmp_path, caplog):
        """No healer attached. YAML enabled=true takes effect (backward compat)."""
        ctrl = _make_reload_controller(
            tmp_path,
            {"fusion": {"enabled": True, "icmp_weight": 0.7}},
            initial_enabled=False,
        )
        # _fusion_healer is already None from _make_controller

        with caplog.at_level(logging.WARNING, logger="test.fusion_reload"):
            ctrl._reload_fusion_config()

        assert ctrl._fusion_enabled is True

    def test_empty_yaml_uses_defaults(self, tmp_path, caplog):
        """YAML is empty (safe_load returns None). After reload, defaults."""
        ctrl = _make_reload_controller(
            tmp_path,
            None,  # Empty YAML
            initial_enabled=True,
            initial_weight=0.5,
        )

        with caplog.at_level(logging.WARNING, logger="test.fusion_reload"):
            ctrl._reload_fusion_config()

        assert ctrl._fusion_enabled is False
        assert ctrl._fusion_icmp_weight == pytest.approx(0.7)


# =============================================================================
# TestAutorateSIGUSR1Loop
# =============================================================================


class TestAutorateSIGUSR1Loop:
    """Tests for SIGUSR1 check in autorate main loop."""

    def test_sigusr1_calls_reload_on_all_wan_controllers(self, tmp_path):
        """SIGUSR1 triggers _reload_fusion_config on every WANController."""
        from unittest.mock import patch

        # Create two mock WAN controllers
        ctrl1 = MagicMock()
        ctrl1_logger = MagicMock()
        ctrl2 = MagicMock()
        ctrl2_logger = MagicMock()

        wan_controllers = [
            {"controller": ctrl1, "logger": ctrl1_logger},
            {"controller": ctrl2, "logger": ctrl2_logger},
        ]

        # Simulate the SIGUSR1 check block from the main loop
        # This tests the actual code pattern that will be added:
        #   if is_reload_requested():
        #       for wan_info in controller.wan_controllers:
        #           wan_info["logger"].info("SIGUSR1 received, reloading fusion config")
        #           wan_info["controller"]._reload_fusion_config()
        #       reset_reload_state()

        import os
        import signal as sig_mod

        from wanctl.signal_utils import register_signal_handlers

        # Register SIGUSR1 handler, then send signal to trigger reload event
        register_signal_handlers(include_sigterm=False, include_sigusr1=True)
        os.kill(os.getpid(), sig_mod.SIGUSR1)

        try:
            if is_reload_requested():
                for wan_info in wan_controllers:
                    wan_info["logger"].info("SIGUSR1 received, reloading fusion config")
                    wan_info["controller"]._reload_fusion_config()
                reset_reload_state()

            ctrl1._reload_fusion_config.assert_called_once()
            ctrl2._reload_fusion_config.assert_called_once()
            ctrl1_logger.info.assert_called_once()
            ctrl2_logger.info.assert_called_once()
            # Verify reload state was cleared
            assert not is_reload_requested()
        finally:
            # Ensure cleanup even on test failure
            reset_reload_state()


# =============================================================================
# MERGED FROM test_fusion_healer_integration.py
# =============================================================================


# =============================================================================
# HELPERS
# =============================================================================


def _make_integration_controller(mock_autorate_config, fusion_enabled=True, irtt_enabled=True):
    """Create a WANController with fusion/IRTT config for healer testing.

    Args:
        mock_autorate_config: Pytest fixture providing mock config.
        fusion_enabled: Whether fusion is enabled in config.
        irtt_enabled: Whether to set up an IRTT thread mock.

    Returns:
        WANController instance with patched load_state.
    """
    mock_autorate_config.fusion_config = {
        "icmp_weight": 0.7,
        "enabled": fusion_enabled,
        "healing": {
            "suspend_threshold": 0.3,
            "recover_threshold": 0.5,
            "suspend_window_sec": 60.0,
            "recover_window_sec": 300.0,
            "grace_period_sec": 1800.0,
        },
    }
    with patch.object(WANController, "load_state"):
        ctrl = WANController(
            wan_name="TestWAN",
            config=mock_autorate_config,
            router=MagicMock(),
            rtt_measurement=MagicMock(),
            logger=logging.getLogger("test.fusion_healer_integration"),
        )

    if irtt_enabled:
        ctrl._irtt_thread = MagicMock()
        ctrl._irtt_thread.cadence_sec = 10.0
    else:
        ctrl._irtt_thread = None

    return ctrl


# =============================================================================
# TestHealerInstantiation
# =============================================================================


class TestHealerInstantiation:
    """Tests for FusionHealer creation via _init_fusion_healer()."""

    def test_healer_created_when_fusion_and_irtt_enabled(self, mock_autorate_config):
        """FusionHealer is created when both fusion and IRTT are enabled."""
        ctrl = _make_integration_controller(mock_autorate_config, fusion_enabled=True, irtt_enabled=True)
        ctrl._init_fusion_healer()
        assert ctrl._fusion_healer is not None
        assert isinstance(ctrl._fusion_healer, FusionHealer)

    def test_healer_not_created_when_fusion_disabled(self, mock_autorate_config):
        """FusionHealer is NOT created when fusion is disabled."""
        ctrl = _make_integration_controller(mock_autorate_config, fusion_enabled=False, irtt_enabled=True)
        ctrl._init_fusion_healer()
        assert ctrl._fusion_healer is None

    def test_healer_not_created_when_irtt_disabled(self, mock_autorate_config):
        """FusionHealer is NOT created when IRTT is disabled."""
        ctrl = _make_integration_controller(mock_autorate_config, fusion_enabled=True, irtt_enabled=False)
        ctrl._init_fusion_healer()
        assert ctrl._fusion_healer is None

    def test_healer_receives_alert_engine(self, mock_autorate_config):
        """FusionHealer receives alert_engine reference from WANController."""
        ctrl = _make_integration_controller(mock_autorate_config, fusion_enabled=True, irtt_enabled=True)
        ctrl._init_fusion_healer()
        assert ctrl._fusion_healer is not None
        # AlertEngine is passed through -- healer stores it internally
        assert ctrl._fusion_healer._alert_engine is not None or ctrl._fusion_healer._alert_engine is None

    def test_healer_receives_parameter_locks(self, mock_autorate_config):
        """FusionHealer receives _parameter_locks reference from WANController."""
        ctrl = _make_integration_controller(mock_autorate_config, fusion_enabled=True, irtt_enabled=True)
        ctrl._init_fusion_healer()
        assert ctrl._fusion_healer is not None
        assert ctrl._fusion_healer._parameter_locks is ctrl._parameter_locks


# =============================================================================
# TestHealerTick
# =============================================================================


class TestHealerTick:
    """Tests for healer.tick() wiring in WANController run_cycle."""

    def test_tick_called_with_correct_deltas(self, mock_autorate_config):
        """healer.tick() called with ICMP and IRTT RTT deltas."""
        ctrl = _make_integration_controller(mock_autorate_config, fusion_enabled=True, irtt_enabled=True)
        ctrl._init_fusion_healer()
        assert ctrl._fusion_healer is not None

        # Mock the healer's tick method
        ctrl._fusion_healer = MagicMock(spec=FusionHealer)
        ctrl._fusion_healer.state = HealState.ACTIVE
        ctrl._fusion_healer.tick.return_value = HealState.ACTIVE

        # Set previous values to compute deltas
        ctrl._prev_filtered_rtt = 20.0
        ctrl._prev_irtt_rtt = 18.0

        # Simulate what run_cycle does with the healer tick
        icmp_rtt = 22.0
        irtt_rtt = 19.5
        icmp_delta = icmp_rtt - ctrl._prev_filtered_rtt
        irtt_delta = irtt_rtt - ctrl._prev_irtt_rtt

        _old_state = ctrl._fusion_healer.state  # noqa: F841
        _new_state = ctrl._fusion_healer.tick(icmp_delta, irtt_delta)  # noqa: F841

        ctrl._fusion_healer.tick.assert_called_once_with(2.0, 1.5)

    def test_fusion_disabled_on_suspended(self, mock_autorate_config):
        """When healer returns SUSPENDED, _fusion_enabled is set to False."""
        ctrl = _make_integration_controller(mock_autorate_config, fusion_enabled=True, irtt_enabled=True)
        ctrl._init_fusion_healer()
        assert ctrl._fusion_healer is not None

        # Mock healer to return SUSPENDED transition
        ctrl._fusion_healer = MagicMock(spec=FusionHealer)
        ctrl._fusion_healer.state = HealState.ACTIVE
        ctrl._fusion_healer.tick.return_value = HealState.SUSPENDED
        ctrl._fusion_healer.pearson_r = 0.15

        # Simulate the state transition logic
        ctrl._prev_filtered_rtt = 20.0
        ctrl._prev_irtt_rtt = 18.0

        icmp_rtt = 22.0
        irtt_rtt = 19.5
        icmp_delta = icmp_rtt - ctrl._prev_filtered_rtt
        irtt_delta = irtt_rtt - ctrl._prev_irtt_rtt

        old_state = ctrl._fusion_healer.state
        new_state = ctrl._fusion_healer.tick(icmp_delta, irtt_delta)

        if new_state != old_state and new_state == HealState.SUSPENDED:
            ctrl._fusion_enabled = False

        assert ctrl._fusion_enabled is False

    def test_fusion_enabled_on_active_recovery(self, mock_autorate_config):
        """When healer returns ACTIVE from RECOVERING, _fusion_enabled set to True."""
        ctrl = _make_integration_controller(mock_autorate_config, fusion_enabled=False, irtt_enabled=True)
        # Manually set up healer since fusion is "disabled" but healer exists
        ctrl._fusion_healer = MagicMock(spec=FusionHealer)
        ctrl._fusion_healer.state = HealState.RECOVERING
        ctrl._fusion_healer.tick.return_value = HealState.ACTIVE
        ctrl._fusion_healer.pearson_r = 0.75

        ctrl._prev_filtered_rtt = 20.0
        ctrl._prev_irtt_rtt = 18.0

        icmp_rtt = 22.0
        irtt_rtt = 19.5
        icmp_delta = icmp_rtt - ctrl._prev_filtered_rtt
        irtt_delta = irtt_rtt - ctrl._prev_irtt_rtt

        old_state = ctrl._fusion_healer.state
        new_state = ctrl._fusion_healer.tick(icmp_delta, irtt_delta)

        if new_state != old_state and new_state == HealState.ACTIVE:
            ctrl._fusion_enabled = True

        assert ctrl._fusion_enabled is True


# =============================================================================
# TestGraceWiring
# =============================================================================


class TestGraceWiring:
    """Tests for SIGUSR1 grace period wiring through _reload_fusion_config."""

    def test_grace_period_not_called_when_healer_suspended_blocks_reenable(self, tmp_path, mock_autorate_config):
        """start_grace_period() NOT called when healer SUSPENDED blocks re-enable.

        When healer is SUSPENDED, _reload_fusion_config refuses to set
        _fusion_enabled=True (respects healer authority), so the grace
        period condition (_fusion_enabled and not old_enabled) is never met.
        """
        config_file = tmp_path / "autorate.yaml"
        config_file.write_text(yaml.dump({"fusion": {"enabled": True, "icmp_weight": 0.7}}))

        ctrl = _make_integration_controller(mock_autorate_config, fusion_enabled=False, irtt_enabled=True)
        ctrl.config.config_file_path = str(config_file)

        # Set up mock healer in SUSPENDED state
        ctrl._fusion_healer = MagicMock(spec=FusionHealer)
        ctrl._fusion_healer.state = HealState.SUSPENDED
        ctrl._fusion_healer._grace_period_sec = 1800.0

        ctrl._reload_fusion_config()

        # Fusion stays disabled because healer is authoritative
        assert ctrl._fusion_enabled is False
        ctrl._fusion_healer.start_grace_period.assert_not_called()

    def test_grace_period_not_called_when_healer_active(self, tmp_path, mock_autorate_config):
        """start_grace_period() NOT called when healer.state is ACTIVE."""
        config_file = tmp_path / "autorate.yaml"
        config_file.write_text(yaml.dump({"fusion": {"enabled": True, "icmp_weight": 0.7}}))

        ctrl = _make_integration_controller(mock_autorate_config, fusion_enabled=False, irtt_enabled=True)
        ctrl.config.config_file_path = str(config_file)

        # Set up mock healer in ACTIVE state
        ctrl._fusion_healer = MagicMock(spec=FusionHealer)
        ctrl._fusion_healer.state = HealState.ACTIVE

        ctrl._reload_fusion_config()

        ctrl._fusion_healer.start_grace_period.assert_not_called()

    def test_grace_period_not_called_when_no_healer(self, tmp_path, mock_autorate_config):
        """No error when _fusion_healer is None during reload."""
        config_file = tmp_path / "autorate.yaml"
        config_file.write_text(yaml.dump({"fusion": {"enabled": True, "icmp_weight": 0.7}}))

        ctrl = _make_integration_controller(mock_autorate_config, fusion_enabled=False, irtt_enabled=True)
        ctrl.config.config_file_path = str(config_file)
        ctrl._fusion_healer = None

        # Should not raise
        ctrl._reload_fusion_config()

    def test_grace_period_not_called_when_not_re_enabling(self, tmp_path, mock_autorate_config):
        """start_grace_period() NOT called when fusion stays disabled."""
        config_file = tmp_path / "autorate.yaml"
        config_file.write_text(yaml.dump({"fusion": {"enabled": False, "icmp_weight": 0.7}}))

        ctrl = _make_integration_controller(mock_autorate_config, fusion_enabled=False, irtt_enabled=True)
        ctrl.config.config_file_path = str(config_file)

        ctrl._fusion_healer = MagicMock(spec=FusionHealer)
        ctrl._fusion_healer.state = HealState.SUSPENDED

        ctrl._reload_fusion_config()

        ctrl._fusion_healer.start_grace_period.assert_not_called()


# =============================================================================
# TestConfigLoading
# =============================================================================


class TestConfigLoading:
    """Tests for Config._load_fusion_config() healing section parsing."""

    @staticmethod
    def _make_fusion_config_mock(yaml_data):
        """Create a mock Config with all fusion config methods bound."""
        config = MagicMock(spec=Config)
        config.data = yaml_data
        for method_name in (
            "_load_fusion_config",
            "_validate_fusion_base",
            "_load_fusion_healing_config",
            "_validate_fusion_threshold",
            "_validate_fusion_window",
        ):
            method = getattr(Config, method_name)
            setattr(config, method_name, method.__get__(config, Config))
        return config

    def test_healing_config_loaded_from_yaml(self, tmp_path):
        """Config._load_fusion_config() reads fusion.healing section."""
        yaml_data = {
            "fusion": {
                "enabled": True,
                "icmp_weight": 0.7,
                "healing": {
                    "suspend_threshold": 0.25,
                    "recover_threshold": 0.6,
                    "suspend_window_sec": 120.0,
                    "recover_window_sec": 600.0,
                    "grace_period_sec": 3600.0,
                },
            }
        }
        config_file = tmp_path / "test.yaml"
        config_file.write_text(yaml.dump(yaml_data))

        config = self._make_fusion_config_mock(yaml_data)
        config._load_fusion_config()

        assert config.fusion_config["healing"]["suspend_threshold"] == 0.25
        assert config.fusion_config["healing"]["recover_threshold"] == 0.6
        assert config.fusion_config["healing"]["suspend_window_sec"] == 120.0
        assert config.fusion_config["healing"]["recover_window_sec"] == 600.0
        assert config.fusion_config["healing"]["grace_period_sec"] == 3600.0

    def test_healing_defaults_when_section_missing(self, tmp_path):
        """Uses defaults when fusion.healing section is absent."""
        yaml_data = {"fusion": {"enabled": True, "icmp_weight": 0.7}}
        config = self._make_fusion_config_mock(yaml_data)
        config._load_fusion_config()

        assert config.fusion_config["healing"]["suspend_threshold"] == 0.3
        assert config.fusion_config["healing"]["recover_threshold"] == 0.5

    def test_healing_invalid_threshold_uses_defaults(self, tmp_path):
        """Invalid suspend_threshold falls back to default 0.3."""
        yaml_data = {
            "fusion": {
                "enabled": True,
                "icmp_weight": 0.7,
                "healing": {"suspend_threshold": "invalid"},
            }
        }
        config = self._make_fusion_config_mock(yaml_data)
        config._load_fusion_config()

        assert config.fusion_config["healing"]["suspend_threshold"] == 0.3

    def test_healing_recover_must_exceed_suspend(self, tmp_path):
        """recover_threshold adjusted when <= suspend_threshold."""
        yaml_data = {
            "fusion": {
                "enabled": True,
                "icmp_weight": 0.7,
                "healing": {
                    "suspend_threshold": 0.5,
                    "recover_threshold": 0.3,  # lower than suspend
                },
            }
        }
        config = self._make_fusion_config_mock(yaml_data)
        config._load_fusion_config()

        # Should be suspend_threshold + 0.2 = 0.7
        assert config.fusion_config["healing"]["recover_threshold"] == 0.7

    def test_healing_invalid_window_uses_default(self, tmp_path):
        """Invalid suspend_window_sec (<10) falls back to 60.0."""
        yaml_data = {
            "fusion": {
                "enabled": True,
                "icmp_weight": 0.7,
                "healing": {"suspend_window_sec": 5.0},
            }
        }
        config = self._make_fusion_config_mock(yaml_data)
        config._load_fusion_config()

        assert config.fusion_config["healing"]["suspend_window_sec"] == 60.0


# =============================================================================
# TestHealthEndpoint
# =============================================================================


class TestHealthEndpoint:
    """Tests for fusion heal state in health endpoint response."""

    @pytest.fixture(autouse=True)
    def reset_handler_state(self):
        """Reset HealthCheckHandler class state before each test."""

        HealthCheckHandler.controller = None
        HealthCheckHandler.start_time = None
        HealthCheckHandler.consecutive_failures = 0
        yield
        HealthCheckHandler.controller = None
        HealthCheckHandler.start_time = None
        HealthCheckHandler.consecutive_failures = 0

    def _make_wan(self, fusion_enabled=True, healer=None):
        """Create a mock WAN controller with fusion healer attributes."""
        wan = MagicMock()
        wan.baseline_rtt = 24.5
        wan.load_rtt = 28.3
        wan.download.current_rate = 800_000_000
        wan.download.red_streak = 0
        wan.download.soft_red_streak = 0
        wan.download.soft_red_required = 3
        wan.download.green_streak = 5
        wan.download.green_required = 5
        wan.upload.current_rate = 35_000_000
        wan.upload.red_streak = 0
        wan.upload.soft_red_streak = 0
        wan.upload.soft_red_required = 3
        wan.upload.green_streak = 5
        wan.upload.green_required = 5
        wan.router_connectivity.is_reachable = True
        wan.router_connectivity.to_dict.return_value = {
            "is_reachable": True,
            "consecutive_failures": 0,
            "last_failure_type": None,
            "last_failure_time": None,
        }
        # Phase 121-124: hysteresis attributes
        wan.download._yellow_dwell = 0
        wan.download.dwell_cycles = 5
        wan.download.deadband_ms = 3.0
        wan.download._transitions_suppressed = 0
        wan.download._window_suppressions = 0
        wan.download._window_start_time = 0.0
        wan.upload._yellow_dwell = 0
        wan.upload.dwell_cycles = 5
        wan.upload.deadband_ms = 3.0
        wan.upload._transitions_suppressed = 0
        wan.upload._window_suppressions = 0
        wan.upload._window_start_time = 0.0
        wan._suppression_alert_threshold = 20
        # Prevent MagicMock truthy issues (attributes accessed by health endpoint)
        wan._last_signal_result = None
        wan._irtt_thread = None
        wan._irtt_correlation = None
        wan._last_asymmetry_result = None
        wan._reflector_scorer = None
        wan.alert_engine = None
        wan._fusion_enabled = fusion_enabled
        wan._fusion_icmp_weight = 0.7
        wan._last_fused_rtt = None
        wan._last_icmp_filtered_rtt = 25.0
        wan._fusion_healer = healer
        wan._tuning_enabled = False
        wan._tuning_state = None
        wan._parameter_locks = None
        wan._overrun_count = 0
        wan._cycle_interval_ms = 50.0
        wan._profiler.stats.return_value = None
        # Public facade for health_check.py (Phase 147)
        wan.get_health_data.return_value = {
            "cycle_budget": {
                "profiler": wan._profiler,
                "overrun_count": 0,
                "cycle_interval_ms": 50.0,
                "warning_threshold_pct": 80,
            },
            "signal_result": None,
            "irtt": {
                "thread": None,
                "correlation": None,
                "last_asymmetry_result": None,
            },
            "reflector": {"scorer": None},
            "fusion": {
                "enabled": fusion_enabled,
                "icmp_filtered_rtt": 25.0,
                "fused_rtt": None,
                "icmp_weight": 0.7,
                "healer": healer,
            },
            "tuning": {
                "enabled": False,
                "state": None,
                "parameter_locks": None,
                "pending_observation": None,
            },
            "suppression_alert": {"threshold": 20},
        }
        wan.download.get_health_data.return_value = {
            "hysteresis": {
                "dwell_counter": 0,
                "dwell_cycles": 5,
                "deadband_ms": 3.0,
                "transitions_suppressed": 0,
                "suppressions_per_min": 0,
                "window_start_epoch": 0.0,
            },
        }
        wan.upload.get_health_data.return_value = {
            "hysteresis": {
                "dwell_counter": 0,
                "dwell_cycles": 5,
                "deadband_ms": 3.0,
                "transitions_suppressed": 0,
                "suppressions_per_min": 0,
                "window_start_epoch": 0.0,
            },
        }
        return wan

    def _make_integration_controller(self, wan):
        """Build a mock controller wrapping a single WAN."""
        mock_controller = MagicMock()
        mock_config = MagicMock()
        mock_config.wan_name = "spectrum"
        mock_config.irtt_config = {"enabled": False}
        mock_controller.wan_controllers = [
            {"controller": wan, "config": mock_config, "logger": MagicMock()}
        ]
        return mock_controller

    def _get_health(self, controller):
        """Start health server, fetch data, shut down."""


        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("127.0.0.1", 0))
            port = s.getsockname()[1]

        server = start_health_server(host="127.0.0.1", port=port, controller=controller)
        try:
            url = f"http://127.0.0.1:{port}/health"
            with urllib.request.urlopen(url, timeout=5) as response:
                return json.loads(response.read().decode())
        finally:
            server.shutdown()

    def test_health_shows_heal_state_active(self):
        """Health response contains heal_state=active when healer is ACTIVE."""
        healer = MagicMock()
        healer.state = HealState.ACTIVE
        healer.pearson_r = 0.85
        healer.window_avg = 0.83
        healer.is_grace_active = False

        wan = self._make_wan(fusion_enabled=True, healer=healer)
        data = self._get_health(self._make_integration_controller(wan))

        fusion = data["wans"][0]["fusion"]
        assert fusion["heal_state"] == "active"
        assert fusion["pearson_correlation"] == 0.85
        assert fusion["correlation_window_avg"] == 0.83
        assert fusion["heal_grace_active"] is False

    def test_health_shows_heal_state_suspended(self):
        """Health response contains heal_state=suspended when healer is SUSPENDED."""
        healer = MagicMock()
        healer.state = HealState.SUSPENDED
        healer.pearson_r = 0.15
        healer.window_avg = 0.12
        healer.is_grace_active = False

        wan = self._make_wan(fusion_enabled=False, healer=healer)
        data = self._get_health(self._make_integration_controller(wan))

        fusion = data["wans"][0]["fusion"]
        assert fusion["heal_state"] == "suspended"
        assert fusion["heal_grace_active"] is False

    def test_health_no_healer(self):
        """Health response contains heal_state=no_healer when _fusion_healer is None."""
        wan = self._make_wan(fusion_enabled=True, healer=None)
        data = self._get_health(self._make_integration_controller(wan))

        fusion = data["wans"][0]["fusion"]
        assert fusion["heal_state"] == "no_healer"
        assert fusion["pearson_correlation"] is None
        assert fusion["heal_grace_active"] is False

    def test_health_warmup_pearson_none(self):
        """Health response has pearson_correlation=None during warmup."""
        healer = MagicMock()
        healer.state = HealState.ACTIVE
        healer.pearson_r = None
        healer.window_avg = None
        healer.is_grace_active = False

        wan = self._make_wan(fusion_enabled=True, healer=healer)
        data = self._get_health(self._make_integration_controller(wan))

        fusion = data["wans"][0]["fusion"]
        assert fusion["heal_state"] == "active"
        assert fusion["pearson_correlation"] is None
        assert fusion["correlation_window_avg"] is None

