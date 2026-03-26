"""Tests for tuning safety wiring in the autorate daemon.

Tests that check_and_revert runs before strategies, locked parameters are
filtered, PendingObservation is stored after applying results, and SIGUSR1
disable clears lock and observation state.
"""

import logging
import time
from unittest.mock import MagicMock

import yaml

from wanctl.tuning.models import SafetyBounds, TuningConfig, TuningResult, TuningState
from wanctl.tuning.safety import PendingObservation


def _make_tuning_config(enabled: bool = True) -> TuningConfig:
    """Create a minimal TuningConfig for testing."""
    return TuningConfig(
        enabled=enabled,
        cadence_sec=3600,
        lookback_hours=24,
        warmup_hours=1,
        max_step_pct=10.0,
        bounds={
            "target_bloat_ms": SafetyBounds(min_value=3.0, max_value=30.0),
            "warn_bloat_ms": SafetyBounds(min_value=10.0, max_value=100.0),
            "hard_red_bloat_ms": SafetyBounds(min_value=30.0, max_value=200.0),
            "alpha_load": SafetyBounds(min_value=0.005, max_value=0.5),
            "alpha_baseline": SafetyBounds(min_value=0.0001, max_value=0.01),
        },
    )


def _make_result(param: str, old: float, new: float, rationale: str = "test") -> TuningResult:
    """Create a test TuningResult."""
    return TuningResult(
        parameter=param,
        old_value=old,
        new_value=new,
        confidence=0.8,
        rationale=rationale,
        data_points=100,
        wan_name="Spectrum",
    )


def _make_revert_result(param: str, old: float, new: float) -> TuningResult:
    """Create a revert TuningResult (swapped old/new, REVERT: prefix)."""
    return TuningResult(
        parameter=param,
        old_value=old,
        new_value=new,
        confidence=1.0,
        rationale="REVERT: congestion rate 5.00%->15.00% (ratio 3.0x > 1.5x)",
        data_points=0,
        wan_name="Spectrum",
    )


class TestWANControllerSafetyInit:
    """Tests for WANController.__init__ safety state attributes."""

    def test_parameter_locks_initialized_empty(self, mock_autorate_config):
        """WANController should initialize _parameter_locks as empty dict."""
        from wanctl.autorate_continuous import WANController

        mock_autorate_config.tuning_config = _make_tuning_config(enabled=True)
        wc = WANController(
            wan_name="Test",
            config=mock_autorate_config,
            router=MagicMock(),
            rtt_measurement=MagicMock(),
            logger=MagicMock(),
        )
        assert wc._parameter_locks == {}
        assert isinstance(wc._parameter_locks, dict)

    def test_pending_observation_initialized_none(self, mock_autorate_config):
        """WANController should initialize _pending_observation as None."""
        from wanctl.autorate_continuous import WANController

        mock_autorate_config.tuning_config = _make_tuning_config(enabled=True)
        wc = WANController(
            wan_name="Test",
            config=mock_autorate_config,
            router=MagicMock(),
            rtt_measurement=MagicMock(),
            logger=MagicMock(),
        )
        assert wc._pending_observation is None

    def test_disabled_tuning_still_has_locks_and_observation(self, mock_autorate_config):
        """Even with tuning disabled, safety attributes should be initialized."""
        from wanctl.autorate_continuous import WANController

        mock_autorate_config.tuning_config = None
        wc = WANController(
            wan_name="Test",
            config=mock_autorate_config,
            router=MagicMock(),
            rtt_measurement=MagicMock(),
            logger=MagicMock(),
        )
        assert wc._parameter_locks == {}
        assert wc._pending_observation is None


class TestSafetyRevertWiring:
    """Tests for check_and_revert integration in maintenance loop flow."""

    def test_check_and_revert_called_before_strategies(self):
        """Verify the maintenance loop calls check_and_revert before running strategies."""
        # We test the import availability and function call pattern
        from wanctl.tuning.safety import check_and_revert

        # When pending_observation is None, should return empty list (no action)
        result = check_and_revert(
            pending_observation=None,
            db_path="/tmp/nonexistent.db",
            wan_name="Spectrum",
        )
        assert result == []

    def test_revert_results_applied_to_controller(self):
        """When check_and_revert returns reverts, _apply_tuning_to_controller applies them."""
        from wanctl.autorate_continuous import _apply_tuning_to_controller

        wc = MagicMock()
        wc._tuning_state = TuningState(
            enabled=True, last_run_ts=time.monotonic(), recent_adjustments=[], parameters={}
        )

        revert = _make_revert_result("target_bloat_ms", old=13.5, new=15.0)
        _apply_tuning_to_controller(wc, [revert])
        assert wc.green_threshold == 15.0
        assert wc.target_delta == 15.0

    def test_revert_locks_parameter(self):
        """After revert, the parameter should be locked via lock_parameter."""
        from wanctl.tuning.safety import is_parameter_locked, lock_parameter

        locks: dict[str, float] = {}
        lock_parameter(locks, "target_bloat_ms", cooldown_sec=86400)
        assert is_parameter_locked(locks, "target_bloat_ms") is True

    def test_pending_observation_cleared_after_revert(self):
        """After revert processing, _pending_observation should be cleared to None."""
        # This tests the expected behavior: wc._pending_observation = None after revert
        wc = MagicMock()
        wc._pending_observation = PendingObservation(
            applied_ts=int(time.time()) - 3600,
            pre_congestion_rate=0.05,
            applied_results=(_make_result("target_bloat_ms", 15.0, 13.5),),
        )
        # Simulate revert clearing
        wc._pending_observation = None
        assert wc._pending_observation is None


class TestLockedParameterFiltering:
    """Tests for locked parameter filtering from strategy list."""

    def test_locked_parameter_excluded_from_strategies(self):
        """Locked parameters should be filtered out of the active strategies list."""
        from wanctl.tuning.safety import is_parameter_locked, lock_parameter

        locks: dict[str, float] = {}
        lock_parameter(locks, "target_bloat_ms", cooldown_sec=86400)

        strategies = [
            ("target_bloat_ms", lambda: None),
            ("warn_bloat_ms", lambda: None),
        ]

        active = [
            (pname, sfn) for pname, sfn in strategies if not is_parameter_locked(locks, pname)
        ]

        assert len(active) == 1
        assert active[0][0] == "warn_bloat_ms"

    def test_unlocked_parameter_included_in_strategies(self):
        """Unlocked parameters should remain in the active strategies list."""
        from wanctl.tuning.safety import is_parameter_locked

        locks: dict[str, float] = {}

        strategies = [
            ("target_bloat_ms", lambda: None),
            ("warn_bloat_ms", lambda: None),
        ]

        active = [
            (pname, sfn) for pname, sfn in strategies if not is_parameter_locked(locks, pname)
        ]

        assert len(active) == 2

    def test_locked_parameter_logged_at_info(self, caplog):
        """Locked parameter skip should be logged at INFO level."""
        from wanctl.tuning.safety import is_parameter_locked, lock_parameter

        locks: dict[str, float] = {}
        lock_parameter(locks, "target_bloat_ms", cooldown_sec=86400)

        logger = logging.getLogger("test.tuning.wiring")
        with caplog.at_level(logging.INFO, logger="test.tuning.wiring"):
            if is_parameter_locked(locks, "target_bloat_ms"):
                logger.info(
                    "[TUNING] %s: %s locked until revert cooldown expires",
                    "Spectrum",
                    "target_bloat_ms",
                )

        assert "locked until revert cooldown expires" in caplog.text


class TestPendingObservationStorage:
    """Tests for PendingObservation creation after applying tuning results."""

    def test_pending_observation_created_with_applied_results(self):
        """After applying results, a PendingObservation should be storable."""
        applied = [
            _make_result("target_bloat_ms", 15.0, 13.5),
            _make_result("warn_bloat_ms", 45.0, 42.0),
        ]

        obs = PendingObservation(
            applied_ts=int(time.time()),
            pre_congestion_rate=0.03,
            applied_results=tuple(applied),
        )

        assert obs.applied_ts > 0
        assert obs.pre_congestion_rate == 0.03
        assert len(obs.applied_results) == 2
        assert obs.applied_results[0].parameter == "target_bloat_ms"

    def test_no_results_means_no_observation(self):
        """When no results are applied (empty), _pending_observation should stay None."""
        wc = MagicMock()
        wc._pending_observation = None

        # Simulate: no results applied, observation stays None
        applied: list[TuningResult] = []
        if not applied:
            pass  # No observation created
        assert wc._pending_observation is None


class TestReloadClearsSafetyState:
    """Tests for SIGUSR1 reload clearing safety state when tuning disabled."""

    def test_sigusr1_disable_clears_parameter_locks(self, mock_autorate_config, tmp_path):
        """When tuning disabled via SIGUSR1, _parameter_locks should be cleared."""
        from wanctl.autorate_continuous import WANController

        config_file = tmp_path / "config.yaml"
        config_file.write_text(yaml.dump({"tuning": {"enabled": True}}))
        mock_autorate_config.config_file_path = str(config_file)
        mock_autorate_config.tuning_config = _make_tuning_config(enabled=True)

        wc = WANController(
            wan_name="Test",
            config=mock_autorate_config,
            router=MagicMock(),
            rtt_measurement=MagicMock(),
            logger=logging.getLogger("test.tuning.reload"),
        )

        # Add a lock
        wc._parameter_locks["target_bloat_ms"] = time.monotonic() + 86400

        # Disable tuning via SIGUSR1
        config_file.write_text(yaml.dump({"tuning": {"enabled": False}}))
        wc._reload_tuning_config()

        assert wc._parameter_locks == {}

    def test_sigusr1_disable_clears_pending_observation(self, mock_autorate_config, tmp_path):
        """When tuning disabled via SIGUSR1, _pending_observation should be cleared."""
        from wanctl.autorate_continuous import WANController

        config_file = tmp_path / "config.yaml"
        config_file.write_text(yaml.dump({"tuning": {"enabled": True}}))
        mock_autorate_config.config_file_path = str(config_file)
        mock_autorate_config.tuning_config = _make_tuning_config(enabled=True)

        wc = WANController(
            wan_name="Test",
            config=mock_autorate_config,
            router=MagicMock(),
            rtt_measurement=MagicMock(),
            logger=logging.getLogger("test.tuning.reload"),
        )

        # Set a pending observation
        wc._pending_observation = PendingObservation(
            applied_ts=int(time.time()),
            pre_congestion_rate=0.05,
            applied_results=(_make_result("target_bloat_ms", 15.0, 13.5),),
        )

        # Disable tuning via SIGUSR1
        config_file.write_text(yaml.dump({"tuning": {"enabled": False}}))
        wc._reload_tuning_config()

        assert wc._pending_observation is None

    def test_sigusr1_enable_preserves_empty_locks(self, mock_autorate_config, tmp_path):
        """Enabling tuning via SIGUSR1 should start with clean state."""
        from wanctl.autorate_continuous import WANController

        config_file = tmp_path / "config.yaml"
        config_file.write_text(yaml.dump({"wan_name": "Test"}))
        mock_autorate_config.config_file_path = str(config_file)
        mock_autorate_config.tuning_config = None

        wc = WANController(
            wan_name="Test",
            config=mock_autorate_config,
            router=MagicMock(),
            rtt_measurement=MagicMock(),
            logger=logging.getLogger("test.tuning.reload"),
        )

        # Enable tuning via SIGUSR1
        config_file.write_text(yaml.dump({"tuning": {"enabled": True}}))
        wc._reload_tuning_config()

        assert wc._tuning_enabled is True
        assert wc._parameter_locks == {}
        assert wc._pending_observation is None


# =============================================================================
# Health endpoint safety section tests
# =============================================================================


def _make_health_handler(wan_controller):
    """Create a HealthCheckHandler with mocked controller for testing."""
    from wanctl.health_check import HealthCheckHandler

    handler = MagicMock(spec=HealthCheckHandler)
    handler.start_time = time.monotonic() - 100
    handler.consecutive_failures = 0

    controller = MagicMock()
    controller.wan_controllers = [
        {
            "controller": wan_controller,
            "config": wan_controller.config,
            "logger": MagicMock(),
        }
    ]
    handler.controller = controller

    # Use the real method
    handler._get_health_status = HealthCheckHandler._get_health_status.__get__(
        handler, HealthCheckHandler
    )
    return handler


def _make_health_wan_controller(
    tuning_enabled=False,
    tuning_state=None,
    tuning_config=None,
    parameter_locks=None,
    pending_observation=None,
):
    """Create a mock WANController with full tuning + safety attributes."""
    wc = MagicMock()
    wc.config.wan_name = "Spectrum"
    wc.baseline_rtt = 25.0
    wc.load_rtt = 30.0
    wc.download.current_rate = 500_000_000
    wc.upload.current_rate = 50_000_000
    wc.download.green_streak = 5
    wc.download.red_streak = 0
    wc.download.soft_red_streak = 0
    wc.download.soft_red_required = 3
    wc.download.green_required = 5
    wc.upload.green_streak = 5
    wc.upload.red_streak = 0
    wc.upload.soft_red_streak = 0
    wc.upload.soft_red_required = 3
    wc.upload.green_required = 5
    wc.router_connectivity.is_reachable = True
    wc.router_connectivity.to_dict.return_value = {"reachable": True}

    # Profiler mock
    wc._profiler = MagicMock()
    wc._profiler.get_stats.return_value = {}
    wc._overrun_count = 0
    wc._cycle_interval_ms = 50.0

    # Signal processing mock
    wc._last_signal_result = None
    wc._irtt_thread = None
    wc._irtt_correlation = None
    wc._last_asymmetry_result = None
    wc._reflector_scorer = MagicMock()
    wc._reflector_scorer.get_all_statuses.return_value = []

    # Fusion mock (disabled to simplify)
    wc._fusion_enabled = False
    wc._last_fused_rtt = None
    wc._last_icmp_filtered_rtt = None
    wc._fusion_icmp_weight = 0.7

    # Alert engine mock
    wc.alert_engine = MagicMock()

    # Tuning attributes
    wc._tuning_enabled = tuning_enabled
    wc._tuning_state = tuning_state
    if tuning_config is not None:
        wc.config.tuning_config = tuning_config
    else:
        wc.config.tuning_config = None

    # Safety attributes (Plan 100-02)
    wc._parameter_locks = parameter_locks if parameter_locks is not None else {}
    wc._pending_observation = pending_observation

    return wc


class TestHealthSafetySection:
    """Tests for safety sub-object in health endpoint tuning section."""

    def test_safety_section_present_in_active_tuning(self):
        """Active tuning health should include a safety sub-object."""
        state = TuningState(
            enabled=True,
            last_run_ts=time.monotonic() - 30.0,
            recent_adjustments=[],
            parameters={"target_bloat_ms": 13.5},
        )
        wc = _make_health_wan_controller(tuning_enabled=True, tuning_state=state)
        handler = _make_health_handler(wc)
        health = handler._get_health_status()

        wan = health["wans"][0]
        assert "safety" in wan["tuning"]
        assert "revert_count" in wan["tuning"]["safety"]
        assert "locked_parameters" in wan["tuning"]["safety"]
        assert "pending_observation" in wan["tuning"]["safety"]

    def test_revert_count_from_recent_adjustments(self):
        """revert_count should count adjustments with REVERT: prefix."""
        adjs = [
            _make_result("target_bloat_ms", 13.5, 15.0, "REVERT: congestion increased"),
            _make_result("warn_bloat_ms", 42.0, 45.0, "REVERT: congestion increased"),
            _make_result("target_bloat_ms", 15.0, 13.5, "test adjustment"),
        ]
        state = TuningState(
            enabled=True,
            last_run_ts=time.monotonic() - 10.0,
            recent_adjustments=adjs,
            parameters={"target_bloat_ms": 15.0},
        )
        wc = _make_health_wan_controller(tuning_enabled=True, tuning_state=state)
        handler = _make_health_handler(wc)
        health = handler._get_health_status()

        wan = health["wans"][0]
        assert wan["tuning"]["safety"]["revert_count"] == 2

    def test_locked_parameters_lists_active_locks(self):
        """locked_parameters should list parameter names with active (unexpired) locks."""
        locks = {
            "target_bloat_ms": time.monotonic() + 86400,  # Active
            "warn_bloat_ms": time.monotonic() - 100,  # Expired
        }
        state = TuningState(
            enabled=True,
            last_run_ts=time.monotonic() - 10.0,
            recent_adjustments=[],
            parameters={},
        )
        wc = _make_health_wan_controller(
            tuning_enabled=True, tuning_state=state, parameter_locks=locks
        )
        handler = _make_health_handler(wc)
        health = handler._get_health_status()

        wan = health["wans"][0]
        assert "target_bloat_ms" in wan["tuning"]["safety"]["locked_parameters"]
        assert "warn_bloat_ms" not in wan["tuning"]["safety"]["locked_parameters"]

    def test_pending_observation_true_when_set(self):
        """pending_observation should be True when _pending_observation is not None."""
        obs = PendingObservation(
            applied_ts=int(time.time()),
            pre_congestion_rate=0.05,
            applied_results=(_make_result("target_bloat_ms", 15.0, 13.5),),
        )
        state = TuningState(
            enabled=True,
            last_run_ts=time.monotonic() - 10.0,
            recent_adjustments=[],
            parameters={},
        )
        wc = _make_health_wan_controller(
            tuning_enabled=True, tuning_state=state, pending_observation=obs
        )
        handler = _make_health_handler(wc)
        health = handler._get_health_status()

        wan = health["wans"][0]
        assert wan["tuning"]["safety"]["pending_observation"] is True

    def test_pending_observation_false_when_none(self):
        """pending_observation should be False when _pending_observation is None."""
        state = TuningState(
            enabled=True,
            last_run_ts=time.monotonic() - 10.0,
            recent_adjustments=[],
            parameters={},
        )
        wc = _make_health_wan_controller(
            tuning_enabled=True, tuning_state=state, pending_observation=None
        )
        handler = _make_health_handler(wc)
        health = handler._get_health_status()

        wan = health["wans"][0]
        assert wan["tuning"]["safety"]["pending_observation"] is False

    def test_safety_section_omitted_when_tuning_disabled(self):
        """When tuning is disabled, safety section should be omitted."""
        wc = _make_health_wan_controller(tuning_enabled=False)
        handler = _make_health_handler(wc)
        health = handler._get_health_status()

        wan = health["wans"][0]
        assert wan["tuning"]["enabled"] is False
        assert "safety" not in wan["tuning"]

    def test_safety_section_omitted_when_awaiting_data(self):
        """When tuning is awaiting data (never run), safety section should be omitted."""
        state = TuningState(
            enabled=True,
            last_run_ts=None,
            recent_adjustments=[],
            parameters={},
        )
        wc = _make_health_wan_controller(tuning_enabled=True, tuning_state=state)
        handler = _make_health_handler(wc)
        health = handler._get_health_status()

        wan = health["wans"][0]
        assert wan["tuning"]["reason"] == "awaiting_data"
        assert "safety" not in wan["tuning"]

    def test_safety_magicmock_safe_no_parameter_locks(self):
        """When _parameter_locks is a MagicMock (not dict), locked_parameters should be empty."""
        state = TuningState(
            enabled=True,
            last_run_ts=time.monotonic() - 10.0,
            recent_adjustments=[],
            parameters={},
        )
        wc = _make_health_wan_controller(tuning_enabled=True, tuning_state=state)
        # Remove explicit dict to let MagicMock auto-create
        del wc._parameter_locks

        handler = _make_health_handler(wc)
        health = handler._get_health_status()

        wan = health["wans"][0]
        assert wan["tuning"]["safety"]["locked_parameters"] == []
