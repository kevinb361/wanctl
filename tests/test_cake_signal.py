"""Unit tests for CAKE signal processing module.

Tests cover: u32_delta wrapping, CakeSignalProcessor EWMA computation,
per-tin separation (Bulk excluded from active drop rate), cold start
handling, disabled processor, and frozen dataclass contracts.
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from typing import Any

import pytest

from wanctl.cake_signal import (
    SANITY_MAX_DELTA,
    U32_MAX,
    CakeSignalConfig,
    CakeSignalProcessor,
    CakeSignalSnapshot,
    TinSnapshot,
    u32_delta,
)


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------

def make_mock_stats(
    tin_drops: list[int] | None = None,
    tin_backlog: list[int] | None = None,
    tin_peak_delay: list[int] | None = None,
) -> dict[str, Any]:
    """Build a mock get_queue_stats() return value."""
    tin_drops = tin_drops or [0, 0, 0, 0]
    tin_backlog = tin_backlog or [0, 0, 0, 0]
    tin_peak_delay = tin_peak_delay or [0, 0, 0, 0]
    return {
        "packets": 100000,
        "bytes": 150000000,
        "dropped": sum(tin_drops),
        "queued_packets": 5,
        "queued_bytes": 7500,
        "memory_used": 27700000,
        "memory_limit": 67108864,
        "capacity_estimate": 500000000,
        "ecn_marked": 0,
        "tins": [
            {
                "sent_bytes": 1000,
                "sent_packets": 10,
                "dropped_packets": tin_drops[i],
                "ecn_marked_packets": 0,
                "backlog_bytes": tin_backlog[i],
                "peak_delay_us": tin_peak_delay[i],
                "avg_delay_us": 0,
                "base_delay_us": 0,
                "sparse_flows": 0,
                "bulk_flows": 0,
                "unresponsive_flows": 0,
            }
            for i in range(4)
        ],
    }


# ---------------------------------------------------------------------------
# u32_delta
# ---------------------------------------------------------------------------

class TestU32Delta:
    """Tests for u32_delta counter arithmetic."""

    def test_normal_forward(self) -> None:
        assert u32_delta(100, 50) == 50

    def test_wrap_around(self) -> None:
        # (U32_MAX - 0xFFFFFFFA) + 10 + 1 = 5 + 10 + 1 = 16
        assert u32_delta(10, 0xFFFFFFFA) == 16

    def test_zero_change(self) -> None:
        assert u32_delta(50, 50) == 0

    def test_sanity_guard_large_delta(self) -> None:
        # A delta exceeding SANITY_MAX_DELTA is treated as artifact -> returns 0
        assert u32_delta(SANITY_MAX_DELTA + 1, 0) == 0

    def test_sanity_guard_exactly_at_limit(self) -> None:
        # Exactly at limit should still be valid
        assert u32_delta(SANITY_MAX_DELTA, 0) == SANITY_MAX_DELTA

    def test_small_wrap(self) -> None:
        # current=2, previous=U32_MAX -> delta = 3
        assert u32_delta(2, U32_MAX) == 3

    def test_u32_max_constant(self) -> None:
        assert U32_MAX == 0xFFFFFFFF


# ---------------------------------------------------------------------------
# CakeSignalSnapshot
# ---------------------------------------------------------------------------

class TestCakeSignalSnapshot:
    """Tests for CakeSignalSnapshot frozen dataclass."""

    def test_frozen(self) -> None:
        snap = CakeSignalSnapshot(
            drop_rate=0.0,
            total_drop_rate=0.0,
            backlog_bytes=0,
            peak_delay_us=0,
            tins=(),
            cold_start=True,
        )
        with pytest.raises(FrozenInstanceError):
            snap.drop_rate = 1.0  # type: ignore[misc]

    def test_fields_present(self) -> None:
        snap = CakeSignalSnapshot(
            drop_rate=1.5,
            total_drop_rate=2.0,
            backlog_bytes=1024,
            peak_delay_us=500,
            tins=(),
            cold_start=False,
        )
        assert snap.drop_rate == 1.5
        assert snap.total_drop_rate == 2.0
        assert snap.backlog_bytes == 1024
        assert snap.peak_delay_us == 500
        assert snap.tins == ()
        assert snap.cold_start is False


# ---------------------------------------------------------------------------
# TinSnapshot
# ---------------------------------------------------------------------------

class TestTinSnapshot:
    """Tests for TinSnapshot frozen dataclass."""

    def test_frozen(self) -> None:
        tin = TinSnapshot(
            name="BestEffort",
            dropped_packets=10,
            drop_delta=5,
            backlog_bytes=0,
            peak_delay_us=0,
            ecn_marked_packets=0,
        )
        with pytest.raises(FrozenInstanceError):
            tin.name = "Voice"  # type: ignore[misc]

    def test_fields_present(self) -> None:
        tin = TinSnapshot(
            name="Voice",
            dropped_packets=42,
            drop_delta=3,
            backlog_bytes=512,
            peak_delay_us=100,
            ecn_marked_packets=1,
        )
        assert tin.name == "Voice"
        assert tin.dropped_packets == 42
        assert tin.drop_delta == 3
        assert tin.backlog_bytes == 512
        assert tin.peak_delay_us == 100
        assert tin.ecn_marked_packets == 1


# ---------------------------------------------------------------------------
# CakeSignalConfig
# ---------------------------------------------------------------------------

class TestCakeSignalConfig:
    """Tests for CakeSignalConfig defaults."""

    def test_defaults(self) -> None:
        cfg = CakeSignalConfig()
        assert cfg.enabled is False
        assert cfg.drop_rate_enabled is False
        assert cfg.backlog_enabled is False
        assert cfg.peak_delay_enabled is False
        assert cfg.metrics_enabled is False
        assert cfg.time_constant_sec == 1.0

    def test_frozen(self) -> None:
        cfg = CakeSignalConfig()
        with pytest.raises(FrozenInstanceError):
            cfg.enabled = True  # type: ignore[misc]


# ---------------------------------------------------------------------------
# CakeSignalProcessor -- cold start
# ---------------------------------------------------------------------------

class TestCakeSignalProcessorColdStart:
    """Tests for cold start behaviour (first update discards delta)."""

    def test_first_update_returns_cold_start(self) -> None:
        cfg = CakeSignalConfig(enabled=True)
        proc = CakeSignalProcessor(config=cfg)
        stats = make_mock_stats(tin_drops=[10, 20, 5, 2])
        snap = proc.update(stats)

        assert snap is not None
        assert snap.cold_start is True
        assert snap.drop_rate == 0.0
        assert snap.total_drop_rate == 0.0

    def test_second_update_not_cold_start(self) -> None:
        cfg = CakeSignalConfig(enabled=True)
        proc = CakeSignalProcessor(config=cfg)
        stats1 = make_mock_stats(tin_drops=[10, 20, 5, 2])
        proc.update(stats1)

        stats2 = make_mock_stats(tin_drops=[10, 25, 5, 2])
        snap = proc.update(stats2)

        assert snap is not None
        assert snap.cold_start is False


# ---------------------------------------------------------------------------
# CakeSignalProcessor -- EWMA convergence
# ---------------------------------------------------------------------------

class TestCakeSignalProcessorEWMA:
    """Tests for EWMA drop rate computation."""

    def test_ewma_computes_valid_rate(self) -> None:
        cfg = CakeSignalConfig(enabled=True, time_constant_sec=1.0)
        proc = CakeSignalProcessor(config=cfg)

        # Cold start
        proc.update(make_mock_stats(tin_drops=[0, 0, 0, 0]))

        # Second update with 10 drops on BestEffort
        snap = proc.update(make_mock_stats(tin_drops=[0, 10, 0, 0]))
        assert snap is not None
        assert snap.cold_start is False
        assert snap.drop_rate > 0.0

    def test_ewma_convergence_after_20_updates(self) -> None:
        """After 20 constant-rate updates, EWMA should approach steady state."""
        cfg = CakeSignalConfig(enabled=True, time_constant_sec=1.0)
        proc = CakeSignalProcessor(config=cfg)

        # Cold start with zero drops
        proc.update(make_mock_stats(tin_drops=[0, 0, 0, 0]))

        # 20 cycles each adding 10 drops on BestEffort (cumulative)
        for i in range(1, 21):
            snap = proc.update(make_mock_stats(tin_drops=[0, i * 10, 0, 0]))

        # 10 drops per 50ms = 200 drops/sec steady state
        assert snap is not None
        assert not snap.cold_start
        # After 20 cycles at time_constant=1.0, alpha=0.05, should be close to 200
        # (1 - 0.95^20) * 200 ~= 128 -- should be > 100
        assert snap.drop_rate > 100.0

    def test_zero_drops_gives_zero_rate(self) -> None:
        cfg = CakeSignalConfig(enabled=True, time_constant_sec=1.0)
        proc = CakeSignalProcessor(config=cfg)

        proc.update(make_mock_stats(tin_drops=[0, 0, 0, 0]))
        snap = proc.update(make_mock_stats(tin_drops=[0, 0, 0, 0]))

        assert snap is not None
        assert snap.drop_rate == 0.0
        assert snap.total_drop_rate == 0.0


# ---------------------------------------------------------------------------
# CakeSignalProcessor -- tin separation
# ---------------------------------------------------------------------------

class TestCakeSignalProcessorTinSeparation:
    """Tests that Bulk tin (index 0) is excluded from active drop rate."""

    def test_bulk_drops_excluded_from_active_rate(self) -> None:
        cfg = CakeSignalConfig(enabled=True, time_constant_sec=1.0)
        proc = CakeSignalProcessor(config=cfg)

        # Cold start
        proc.update(make_mock_stats(tin_drops=[0, 0, 0, 0]))

        # Only Bulk drops (index 0), no BestEffort+ drops
        snap = proc.update(make_mock_stats(tin_drops=[100, 0, 0, 0]))

        assert snap is not None
        assert snap.drop_rate == 0.0  # Active = excl Bulk
        assert snap.total_drop_rate > 0.0  # Total includes Bulk

    def test_besteffort_drops_in_both_rates(self) -> None:
        cfg = CakeSignalConfig(enabled=True, time_constant_sec=1.0)
        proc = CakeSignalProcessor(config=cfg)

        proc.update(make_mock_stats(tin_drops=[0, 0, 0, 0]))
        snap = proc.update(make_mock_stats(tin_drops=[0, 50, 0, 0]))

        assert snap is not None
        assert snap.drop_rate > 0.0
        assert snap.total_drop_rate > 0.0

    def test_backlog_excludes_bulk(self) -> None:
        cfg = CakeSignalConfig(enabled=True, time_constant_sec=1.0)
        proc = CakeSignalProcessor(config=cfg)

        proc.update(make_mock_stats(tin_backlog=[1000, 200, 300, 0]))
        snap = proc.update(make_mock_stats(tin_backlog=[1000, 200, 300, 0]))

        assert snap is not None
        # backlog_bytes = sum of tins[1:] = 200 + 300 + 0 = 500
        assert snap.backlog_bytes == 500

    def test_peak_delay_excludes_bulk(self) -> None:
        cfg = CakeSignalConfig(enabled=True, time_constant_sec=1.0)
        proc = CakeSignalProcessor(config=cfg)

        proc.update(make_mock_stats(tin_peak_delay=[9999, 100, 500, 200]))
        snap = proc.update(make_mock_stats(tin_peak_delay=[9999, 100, 500, 200]))

        assert snap is not None
        # peak_delay_us = max of tins[1:] = max(100, 500, 200) = 500
        assert snap.peak_delay_us == 500


# ---------------------------------------------------------------------------
# CakeSignalProcessor -- disabled
# ---------------------------------------------------------------------------

class TestCakeSignalProcessorDisabled:
    """Tests for disabled processor."""

    def test_disabled_returns_none(self) -> None:
        cfg = CakeSignalConfig(enabled=False)
        proc = CakeSignalProcessor(config=cfg)
        result = proc.update(make_mock_stats())
        assert result is None


# ---------------------------------------------------------------------------
# CakeSignalProcessor -- None stats
# ---------------------------------------------------------------------------

class TestCakeSignalProcessorNoneStats:
    """Tests that None stats input does not crash."""

    def test_none_stats_returns_none_on_cold_start(self) -> None:
        cfg = CakeSignalConfig(enabled=True)
        proc = CakeSignalProcessor(config=cfg)
        result = proc.update(None)
        # No previous snapshot, so return None
        assert result is None

    def test_none_stats_returns_previous_snapshot(self) -> None:
        cfg = CakeSignalConfig(enabled=True)
        proc = CakeSignalProcessor(config=cfg)

        # Build up a valid snapshot
        proc.update(make_mock_stats(tin_drops=[0, 10, 0, 0]))
        prev = proc.update(make_mock_stats(tin_drops=[0, 20, 0, 0]))

        # Now pass None -- should return previous snapshot
        result = proc.update(None)
        assert result is prev


# ---------------------------------------------------------------------------
# CakeSignalProcessor -- config setter
# ---------------------------------------------------------------------------

class TestCakeSignalProcessorConfigSetter:
    """Tests for config property setter (reload support)."""

    def test_config_setter_updates_alpha(self) -> None:
        cfg1 = CakeSignalConfig(enabled=True, time_constant_sec=1.0)
        proc = CakeSignalProcessor(config=cfg1)
        alpha1 = proc._alpha  # noqa: SLF001

        cfg2 = CakeSignalConfig(enabled=True, time_constant_sec=2.0)
        proc.config = cfg2
        alpha2 = proc._alpha  # noqa: SLF001

        assert alpha2 < alpha1  # Larger time constant -> smaller alpha

    def test_config_setter_disables(self) -> None:
        cfg1 = CakeSignalConfig(enabled=True)
        proc = CakeSignalProcessor(config=cfg1)

        cfg2 = CakeSignalConfig(enabled=False)
        proc.config = cfg2

        result = proc.update(make_mock_stats())
        assert result is None


# ---------------------------------------------------------------------------
# CakeSignalProcessor -- tin snapshots in output
# ---------------------------------------------------------------------------

class TestCakeSignalProcessorTinSnapshots:
    """Tests that TinSnapshot objects are in the output."""

    def test_tins_tuple_has_4_entries(self) -> None:
        cfg = CakeSignalConfig(enabled=True)
        proc = CakeSignalProcessor(config=cfg)

        proc.update(make_mock_stats(tin_drops=[5, 10, 3, 1]))
        snap = proc.update(make_mock_stats(tin_drops=[7, 15, 4, 2]))

        assert snap is not None
        assert len(snap.tins) == 4
        assert snap.tins[0].name == "Bulk"
        assert snap.tins[1].name == "BestEffort"
        assert snap.tins[2].name == "Video"
        assert snap.tins[3].name == "Voice"

    def test_tin_drop_delta_computed(self) -> None:
        cfg = CakeSignalConfig(enabled=True)
        proc = CakeSignalProcessor(config=cfg)

        proc.update(make_mock_stats(tin_drops=[5, 10, 3, 1]))
        snap = proc.update(make_mock_stats(tin_drops=[7, 15, 4, 2]))

        assert snap is not None
        assert snap.tins[0].drop_delta == 2  # 7 - 5
        assert snap.tins[1].drop_delta == 5  # 15 - 10
        assert snap.tins[2].drop_delta == 1  # 4 - 3
        assert snap.tins[3].drop_delta == 1  # 2 - 1


# ---------------------------------------------------------------------------
# YAML config parsing (_parse_cake_signal_config) -- Phase 159, CAKE-05
# ---------------------------------------------------------------------------

class TestCakeSignalYAMLConfig:
    """Tests for _parse_cake_signal_config via WANController."""

    def _make_controller_with_yaml(self, tmp_path, yaml_content: str):
        """Create a minimal mock WANController with a temp YAML config file."""
        import yaml as _yaml
        from unittest.mock import MagicMock

        config_file = tmp_path / "test.yaml"
        config_file.write_text(yaml_content)

        # Minimal mock that exposes config.config_file_path
        mock_ctrl = MagicMock()
        mock_ctrl.config.config_file_path = str(config_file)

        # Bind _parse_cake_signal_config to our mock
        from wanctl.wan_controller import WANController
        return WANController._parse_cake_signal_config.__get__(mock_ctrl, WANController)  # bound method

    def test_parse_missing_section(self, tmp_path) -> None:
        """No cake_signal key in YAML -> all defaults (disabled)."""
        import yaml

        parse = self._make_controller_with_yaml(
            tmp_path, yaml.dump({"some_other_key": True})
        )
        cfg = parse()
        assert cfg.enabled is False
        assert cfg.drop_rate_enabled is False
        assert cfg.backlog_enabled is False
        assert cfg.peak_delay_enabled is False
        assert cfg.metrics_enabled is False
        assert cfg.time_constant_sec == 1.0

    def test_parse_all_enabled(self, tmp_path) -> None:
        """All sub-features enabled with custom time_constant."""
        import yaml

        parse = self._make_controller_with_yaml(
            tmp_path,
            yaml.dump({
                "cake_signal": {
                    "enabled": True,
                    "drop_rate": {"enabled": True, "time_constant_sec": 2.0},
                    "backlog": {"enabled": True},
                    "peak_delay": {"enabled": True},
                    "metrics": {"enabled": True},
                }
            }),
        )
        cfg = parse()
        assert cfg.enabled is True
        assert cfg.drop_rate_enabled is True
        assert cfg.backlog_enabled is True
        assert cfg.peak_delay_enabled is True
        assert cfg.metrics_enabled is True
        assert cfg.time_constant_sec == 2.0

    def test_parse_invalid_types(self, tmp_path) -> None:
        """Non-bool enabled, non-float time_constant -> defaults."""
        import yaml

        parse = self._make_controller_with_yaml(
            tmp_path,
            yaml.dump({
                "cake_signal": {
                    "enabled": "yes",  # not a bool
                    "drop_rate": {"enabled": 42, "time_constant_sec": "fast"},
                    "backlog": {"enabled": None},
                }
            }),
        )
        cfg = parse()
        assert cfg.enabled is False  # "yes" is not bool
        assert cfg.drop_rate_enabled is False  # 42 is not True
        assert cfg.backlog_enabled is False  # None is not True
        assert cfg.time_constant_sec == 1.0  # "fast" not valid

    def test_parse_time_constant_bounds_low(self, tmp_path) -> None:
        """time_constant below 0.1 clamped to 0.1."""
        import yaml

        parse = self._make_controller_with_yaml(
            tmp_path,
            yaml.dump({
                "cake_signal": {
                    "enabled": True,
                    "drop_rate": {"enabled": True, "time_constant_sec": 0.01},
                }
            }),
        )
        cfg = parse()
        assert cfg.time_constant_sec == 0.1

    def test_parse_time_constant_bounds_high(self, tmp_path) -> None:
        """time_constant above 30.0 clamped to 30.0."""
        import yaml

        parse = self._make_controller_with_yaml(
            tmp_path,
            yaml.dump({
                "cake_signal": {
                    "enabled": True,
                    "drop_rate": {"enabled": True, "time_constant_sec": 100.0},
                }
            }),
        )
        cfg = parse()
        assert cfg.time_constant_sec == 30.0

    def test_parse_partial_section(self, tmp_path) -> None:
        """Only some sub-features enabled."""
        import yaml

        parse = self._make_controller_with_yaml(
            tmp_path,
            yaml.dump({
                "cake_signal": {
                    "enabled": True,
                    "drop_rate": {"enabled": True},
                    # backlog, peak_delay, metrics not specified -> disabled
                }
            }),
        )
        cfg = parse()
        assert cfg.enabled is True
        assert cfg.drop_rate_enabled is True
        assert cfg.backlog_enabled is False
        assert cfg.peak_delay_enabled is False
        assert cfg.metrics_enabled is False
        assert cfg.time_constant_sec == 1.0

    def test_parse_file_not_found(self, tmp_path) -> None:
        """Config file doesn't exist -> defaults."""
        from unittest.mock import MagicMock

        from wanctl.wan_controller import WANController

        mock_ctrl = MagicMock()
        mock_ctrl.config.config_file_path = str(tmp_path / "nonexistent.yaml")
        parse = WANController._parse_cake_signal_config.__get__(mock_ctrl, WANController)
        cfg = parse()
        assert cfg.enabled is False

    def test_parse_empty_yaml(self, tmp_path) -> None:
        """Empty YAML file -> defaults."""
        config_file = tmp_path / "empty.yaml"
        config_file.write_text("")

        from unittest.mock import MagicMock

        from wanctl.wan_controller import WANController

        mock_ctrl = MagicMock()
        mock_ctrl.config.config_file_path = str(config_file)
        parse = WANController._parse_cake_signal_config.__get__(mock_ctrl, WANController)
        cfg = parse()
        assert cfg.enabled is False


# ---------------------------------------------------------------------------
# SIGUSR1 reload (_reload_cake_signal_config) -- Phase 159, CAKE-05
# ---------------------------------------------------------------------------

class TestCakeSignalReload:
    """Tests for _reload_cake_signal_config via WANController."""

    def _make_mock_ctrl(self, tmp_path, yaml_content: str):
        """Create mock WANController with real _parse and _reload bound."""
        import yaml
        from unittest.mock import MagicMock

        from wanctl.wan_controller import WANController

        config_file = tmp_path / "test.yaml"
        config_file.write_text(yaml_content)

        mock_ctrl = MagicMock()
        mock_ctrl.config.config_file_path = str(config_file)

        # Bind real methods so they call the actual implementation
        mock_ctrl._parse_cake_signal_config = (
            WANController._parse_cake_signal_config.__get__(mock_ctrl, WANController)
        )
        mock_ctrl._reload_cake_signal_config = (
            WANController._reload_cake_signal_config.__get__(mock_ctrl, WANController)
        )
        return mock_ctrl, config_file

    def test_reload_updates_processor_config(self, tmp_path) -> None:
        """Reload updates both DL and UL processor configs."""
        import yaml

        from wanctl.cake_signal import CakeSignalConfig, CakeSignalProcessor

        mock_ctrl, config_file = self._make_mock_ctrl(
            tmp_path, yaml.dump({"cake_signal": {"enabled": False}})
        )
        mock_ctrl._dl_cake_signal = CakeSignalProcessor(config=CakeSignalConfig())
        mock_ctrl._ul_cake_signal = CakeSignalProcessor(config=CakeSignalConfig())

        # Verify initial state
        assert mock_ctrl._dl_cake_signal.config.enabled is False

        # Update YAML to enable
        config_file.write_text(yaml.dump({
            "cake_signal": {
                "enabled": True,
                "drop_rate": {"enabled": True, "time_constant_sec": 3.0},
                "metrics": {"enabled": True},
            }
        }))

        # Call reload
        mock_ctrl._reload_cake_signal_config()

        # Both processors should have new config
        assert mock_ctrl._dl_cake_signal.config.enabled is True
        assert mock_ctrl._dl_cake_signal.config.drop_rate_enabled is True
        assert mock_ctrl._dl_cake_signal.config.metrics_enabled is True
        assert mock_ctrl._dl_cake_signal.config.time_constant_sec == 3.0
        assert mock_ctrl._ul_cake_signal.config.enabled is True

    def test_reload_logs_transitions(self, tmp_path) -> None:
        """Reload logs transition descriptions at WARNING level."""
        import yaml

        from wanctl.cake_signal import CakeSignalConfig, CakeSignalProcessor

        mock_ctrl, _ = self._make_mock_ctrl(
            tmp_path,
            yaml.dump({
                "cake_signal": {
                    "enabled": True,
                    "drop_rate": {"enabled": True},
                }
            }),
        )
        mock_ctrl._dl_cake_signal = CakeSignalProcessor(
            config=CakeSignalConfig(enabled=False)
        )
        mock_ctrl._ul_cake_signal = CakeSignalProcessor(
            config=CakeSignalConfig(enabled=False)
        )

        mock_ctrl._reload_cake_signal_config()

        # Check logger.warning was called with transition info
        mock_ctrl.logger.warning.assert_called_once()
        call_args = mock_ctrl.logger.warning.call_args
        assert "[CAKE_SIGNAL]" in call_args[0][0]
        # The formatted string should contain enabled transition
        formatted = call_args[0][0] % call_args[0][1:]
        assert "enabled=False->True" in formatted

    def test_reload_unchanged_logs_unchanged(self, tmp_path) -> None:
        """Reload with no changes logs (unchanged)."""
        import yaml

        from wanctl.cake_signal import CakeSignalConfig, CakeSignalProcessor

        mock_ctrl, _ = self._make_mock_ctrl(
            tmp_path, yaml.dump({"cake_signal": {"enabled": False}})
        )
        mock_ctrl._dl_cake_signal = CakeSignalProcessor(
            config=CakeSignalConfig(enabled=False)
        )
        mock_ctrl._ul_cake_signal = CakeSignalProcessor(
            config=CakeSignalConfig(enabled=False)
        )

        mock_ctrl._reload_cake_signal_config()

        call_args = mock_ctrl.logger.warning.call_args
        formatted = call_args[0][0] % call_args[0][1:]
        assert "(unchanged)" in formatted
