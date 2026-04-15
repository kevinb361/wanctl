"""WAN controller for adaptive CAKE bandwidth management.

Contains the core WANController class that runs the 50ms control loop,
managing RTT measurement, congestion state transitions, and queue rate
adjustments for a single WAN interface.
"""

import concurrent.futures
import json
import logging
import socket
import statistics
import threading
import time
from collections import deque
from pathlib import Path
from typing import Any

from wanctl.alert_engine import AlertEngine
from wanctl.asymmetry_analyzer import DIRECTION_ENCODING, AsymmetryAnalyzer, AsymmetryResult
from wanctl.autorate_config import Config
from wanctl.cake_stats_thread import BackgroundCakeStatsThread
from wanctl.config_base import get_storage_config
from wanctl.error_handling import handle_errors
from wanctl.fusion_healer import FusionHealer, HealState
from wanctl.irtt_measurement import IRTTResult
from wanctl.irtt_thread import IRTTThread
from wanctl.metrics import (
    get_storage_metrics_snapshot,
    record_autorate_cycle,
    record_ping_failure,
    record_rate_limit_event,
    record_router_update,
)
from wanctl.pending_rates import PendingRateChange
from wanctl.perf_profiler import (
    OperationProfiler,
    PerfTimer,
    record_cycle_profiling,
)
from wanctl.queue_controller import QueueController
from wanctl.rate_utils import RateLimiter
from wanctl.reflector_scorer import ReflectorScorer
from wanctl.router_connectivity import RouterConnectivityState
from wanctl.routeros_interface import RouterOS
from wanctl.rtt_measurement import (
    BackgroundRTTThread,
    RTTMeasurement,
)
from wanctl.runtime_pressure import get_storage_file_snapshot, read_process_memory_status
from wanctl.signal_processing import SignalProcessor, SignalResult
from wanctl.storage import MetricsWriter
from wanctl.storage.deferred_writer import DeferredIOWorker
from wanctl.tuning.models import TuningResult, TuningState
from wanctl.wan_controller_state import WANControllerState

# =============================================================================
# CONSTANTS
# =============================================================================

# Daemon cycle interval - target time between cycle starts (seconds)
# Production standard: 0.05s (50ms, 20Hz polling) - validated Phase 2 (2026-01-13)
# - 40x faster than original 2s baseline, sub-second congestion detection
# - Proven stable: 0% router CPU idle, 45% peak under RRUL stress
# - Utilization: 60-80% (30-40ms execution vs 50ms interval)
#
# Time-constant preservation when changing intervals:
# - New EWMA alpha = Old alpha × (New interval / Old interval)
# - New sample counts = Old samples × (Old interval / New interval)
# - Preserves wall-clock smoothing behavior
#
# Conservative alternatives: 100ms (20x speed, 2x headroom) or 250ms (8x speed, 4x headroom)
# See docs/PRODUCTION_INTERVAL.md for validation results and configuration guidance
#
# With 0.05s cycles and 0.85 factor_down, recovery from 920M to floor
# takes ~80 cycles = 4 seconds
CYCLE_INTERVAL_SECONDS = 0.05

FORCE_SAVE_INTERVAL_CYCLES = 1200  # Force state save every 60s (1200 * 50ms)
STATE_ENCODING = {"GREEN": 0, "YELLOW": 1, "SOFT_RED": 2, "RED": 3}
SLOW_ROUTER_APPLY_LOG_MS = 10.0


# =============================================================================
# ADAPTIVE TUNING HELPERS
# =============================================================================


def _apply_threshold_param(wc: "WANController", param: str, val: float) -> bool:
    """Apply threshold and EWMA tuning parameters. Returns True if handled."""
    if param == "target_bloat_ms":
        wc.green_threshold = val
        wc.target_delta = val
    elif param == "warn_bloat_ms":
        wc.soft_red_threshold = val
        wc.warn_delta = val
    elif param == "hard_red_bloat_ms":
        wc.hard_red_threshold = val
    elif param == "alpha_load":
        wc.alpha_load = val
    elif param == "alpha_baseline":
        wc.alpha_baseline = val
    elif param == "baseline_rtt_min":
        wc.baseline_rtt_min = val
    elif param == "baseline_rtt_max":
        wc.baseline_rtt_max = val
    else:
        return False
    return True


def _apply_signal_param(wc: "WANController", param: str, val: float) -> bool:
    """Apply signal processing and fusion tuning parameters. Returns True if handled."""
    if param == "hampel_sigma_threshold":
        sigma_descriptor = getattr(type(wc.signal_processor), "sigma_threshold", None)
        if isinstance(sigma_descriptor, property) and sigma_descriptor.fset is not None:
            wc.signal_processor.sigma_threshold = val
        else:
            setattr(wc.signal_processor, "_sigma_threshold", val)
    elif param == "hampel_window_size":
        new_size = round(val)
        resize_window = getattr(type(wc.signal_processor), "resize_window", None)
        if callable(resize_window):
            wc.signal_processor.resize_window(new_size)
        else:
            setattr(wc.signal_processor, "_window_size", new_size)
            setattr(
                wc.signal_processor,
                "_window",
                deque(getattr(wc.signal_processor, "_window"), maxlen=new_size),
            )
            setattr(
                wc.signal_processor,
                "_outlier_window",
                deque(getattr(wc.signal_processor, "_outlier_window"), maxlen=new_size),
            )
    elif param == "load_time_constant_sec":
        # Convert time constant to alpha: alpha = cycle_interval / tc
        # Using 0.05 (50ms) as the cycle interval constant.
        # Tuning operates in tc domain (0.5-10s range) where
        # clamp_to_step's round(1) and trivial filter work correctly;
        # we convert to alpha only at apply time (Pitfall 3 fix).
        wc.alpha_load = 0.05 / val
    elif param == "fusion_icmp_weight":
        wc._fusion_icmp_weight = val
    elif param == "reflector_min_score":
        min_score_descriptor = getattr(type(wc._reflector_scorer), "min_score", None)
        if isinstance(min_score_descriptor, property) and min_score_descriptor.fset is not None:
            wc._reflector_scorer.min_score = val
        else:
            setattr(wc._reflector_scorer, "_min_score", val)
    else:
        return False
    return True


def _apply_queue_param(wc: "WANController", param: str, val: float) -> bool:
    """Apply per-direction queue tuning parameters. Returns True if handled."""
    if param == "dl_step_up_mbps":
        wc.download.step_up_bps = int(val * 1_000_000)
    elif param == "ul_step_up_mbps":
        wc.upload.step_up_bps = int(val * 1_000_000)
    elif param == "dl_factor_down":
        wc.download.factor_down = val
    elif param == "ul_factor_down":
        wc.upload.factor_down = val
    elif param == "dl_green_required":
        wc.download.green_required = round(val)
    elif param == "ul_green_required":
        wc.upload.green_required = round(val)
    else:
        return False
    return True


def _apply_single_tuning_param(wc: "WANController", r: TuningResult) -> None:
    """Apply a single tuning result to the controller.

    Dispatches to category-specific handlers for thresholds, signal
    processing, and per-direction queue parameters.
    """
    param = r.parameter
    val = r.new_value

    if _apply_threshold_param(wc, param, val):
        return
    if _apply_signal_param(wc, param, val):
        return
    _apply_queue_param(wc, param, val)


def _mark_tuning_executed(wc: "WANController") -> None:
    """Update last_run_ts to reflect that tuning executed (even with no changes)."""
    if wc._tuning_state is None:
        return
    wc._tuning_state = TuningState(
        enabled=wc._tuning_state.enabled,
        last_run_ts=time.monotonic(),
        recent_adjustments=wc._tuning_state.recent_adjustments,
        parameters=wc._tuning_state.parameters,
    )


def _update_tuning_state(wc: "WANController", results: list[TuningResult]) -> None:
    """Update TuningState with recent adjustments (capped at 10)."""
    if not results or wc._tuning_state is None:
        return
    params = dict(wc._tuning_state.parameters)
    for r in results:
        params[r.parameter] = r.new_value
    recent = list(wc._tuning_state.recent_adjustments) + list(results)
    recent = recent[-10:]
    wc._tuning_state = TuningState(
        enabled=True,
        last_run_ts=time.monotonic(),
        recent_adjustments=recent,
        parameters=params,
    )


def _apply_tuning_to_controller(
    wc: "WANController",
    results: list[TuningResult],
) -> None:
    """Apply tuning results to WANController attributes.

    Maps parameter names to controller attributes:
      target_bloat_ms       -> green_threshold + target_delta
      warn_bloat_ms         -> soft_red_threshold + warn_delta
      hard_red_bloat_ms     -> hard_red_threshold
      alpha_load            -> alpha_load
      alpha_baseline        -> alpha_baseline
      hampel_sigma_threshold -> signal_processor._sigma_threshold
      hampel_window_size    -> signal_processor._window_size + deque resize
      load_time_constant_sec -> alpha_load (via alpha = 0.05 / tc)
      fusion_icmp_weight    -> _fusion_icmp_weight
      reflector_min_score   -> _reflector_scorer._min_score
      baseline_rtt_min      -> baseline_rtt_min
      baseline_rtt_max      -> baseline_rtt_max
      dl_step_up_mbps       -> download.step_up_bps (Mbps -> bps)
      ul_step_up_mbps       -> upload.step_up_bps (Mbps -> bps)
      dl_factor_down        -> download.factor_down
      ul_factor_down        -> upload.factor_down
      dl_green_required     -> download.green_required (round to int)
      ul_green_required     -> upload.green_required (round to int)

    Also updates TuningState with recent adjustments (capped at 10).
    """
    for r in results:
        _apply_single_tuning_param(wc, r)

    _update_tuning_state(wc, results)


# =============================================================================
# WAN CONTROLLER
# =============================================================================


class WANController:
    """Controls both download and upload for one WAN"""

    def __init__(
        self,
        wan_name: str,
        config: Config,
        router: RouterOS,
        rtt_measurement: RTTMeasurement,
        logger: logging.Logger,
    ):
        self.wan_name = wan_name
        self.config = config
        self.router = router
        self.rtt_measurement = rtt_measurement
        self.logger = logger
        self.router_connectivity = RouterConnectivityState(self.logger)
        self.pending_rates = PendingRateChange()

        self._init_baseline_and_thresholds()
        self._init_flash_wear_protection()
        self._init_state_persistence()
        self._init_metrics_storage()
        self._init_alerting()
        self._init_signal_processing()
        self._init_irtt_and_fusion()
        self._init_reflector_scoring()
        self._init_alert_timers()
        self._init_profiling()
        self._init_tuning()
        self._init_cake_signal()

        # Load persisted state (hysteresis counters, current rates, EWMA)
        self.load_state()

        # Restore tuning parameters from SQLite (survives daemon restart)
        if self._tuning_enabled and self._metrics_writer is not None:
            self._restore_tuning_params()

    # =========================================================================
    # __init__ concern-grouped helpers (Phase 145-01)
    # =========================================================================

    def _init_baseline_and_thresholds(self) -> None:
        """Initialize baseline RTT, acceleration detection, queue controllers, and thresholds."""
        config = self.config
        wan_name = self.wan_name

        # Initialize baseline from config (will be measured and updated)
        self.baseline_rtt = config.baseline_rtt_initial
        self.load_rtt = self.baseline_rtt

        # Rate-of-change (acceleration) detection for sudden RTT spikes
        self.previous_load_rtt = self.load_rtt
        self.accel_threshold = config.accel_threshold_ms
        self.accel_confirm = config.accel_confirm_cycles
        self._spike_streak = 0
        self._dl_burst_pending = False
        self._dl_burst_reason: str | None = None
        self._dl_burst_trigger_count = 0
        self._dl_burst_last_reason: str | None = None
        self._dl_burst_last_accel_ms: float | None = None
        self._dl_burst_last_delta_ms: float | None = None
        self._dl_burst_last_trigger_ts: float | None = None
        self._dl_burst_exported_trigger_count = 0
        self._dl_burst_candidate_cycles = 0
        self._dl_burst_candidate_accel_ms: float | None = None

        # Create queue controllers
        self.download = QueueController(
            name=f"{wan_name}-Download",
            floor_green=config.download_floor_green,
            floor_yellow=config.download_floor_yellow,
            floor_soft_red=config.download_floor_soft_red,  # Phase 2A
            floor_red=config.download_floor_red,
            ceiling=config.download_ceiling,
            step_up=config.download_step_up,
            factor_down=config.download_factor_down,
            factor_down_yellow=config.download_factor_down_yellow,  # YELLOW decay
            green_required=config.download_green_required,  # Faster recovery
            dwell_cycles=config.dwell_cycles,
            deadband_ms=config.deadband_ms,
        )

        self.upload = QueueController(
            name=f"{wan_name}-Upload",
            floor_green=config.upload_floor_green,
            floor_yellow=config.upload_floor_yellow,
            floor_soft_red=config.upload_floor_yellow,  # Upload uses yellow for soft_red
            floor_red=config.upload_floor_red,
            ceiling=config.upload_ceiling,
            step_up=config.upload_step_up,
            factor_down=config.upload_factor_down,
            factor_down_yellow=config.upload_factor_down_yellow,  # Upload YELLOW decay
            green_required=config.upload_green_required,  # Faster recovery
            dwell_cycles=config.dwell_cycles,
            deadband_ms=config.deadband_ms,
        )

        # Thresholds (Phase 2A: 4-state for download, 3-state for upload)
        self.green_threshold = config.target_bloat_ms  # 15ms: GREEN -> YELLOW
        self.soft_red_threshold = config.warn_bloat_ms  # 45ms: YELLOW -> SOFT_RED
        self.hard_red_threshold = config.hard_red_bloat_ms  # 80ms: SOFT_RED -> RED
        # Legacy 3-state thresholds (for upload)
        self.target_delta = config.target_bloat_ms
        self.warn_delta = config.warn_bloat_ms
        self.alpha_baseline = config.alpha_baseline
        self.alpha_load = config.alpha_load
        self.baseline_update_threshold = config.baseline_update_threshold_ms
        self.baseline_rtt_min = config.baseline_rtt_min
        self.baseline_rtt_max = config.baseline_rtt_max

        # Ping configuration
        self.ping_hosts = config.ping_hosts
        self.use_median_of_three = config.use_median_of_three

    def _init_flash_wear_protection(self) -> None:
        """Initialize flash wear protection, rate limiter, and fallback tracking."""
        # Flash wear protection: only send updates when rates change
        # RATE-04: Skip-identical guard stays on ALL transports
        self.last_applied_dl_rate: int | None = None
        self.last_applied_ul_rate: int | None = None

        # Rate limiter: conditional on transport backend (D-06, D-12)
        # linux-cake writes to kernel memory -- no rate limiting needed
        # REST/SSH writes to RouterOS API -- rate limiting protects responsiveness
        needs_rate_limiting = getattr(self.router, "needs_rate_limiting", False) is True
        if needs_rate_limiting:
            raw_params = getattr(self.router, "rate_limit_params", {})
            params = raw_params if isinstance(raw_params, dict) else {}
            self.rate_limiter: RateLimiter | None = RateLimiter(
                max_changes=int(params.get("max_changes", 5)),
                window_seconds=int(params.get("window_seconds", 10)),
            )
        else:
            self.rate_limiter = None
        self._rate_limit_logged = False

        # Fallback connectivity tracking (ICMP filtered but WAN works)
        self.icmp_unavailable_cycles = 0

    def _init_state_persistence(self) -> None:
        """Initialize state persistence manager and zone tracking."""
        self.state_manager = WANControllerState(
            state_file=self.config.state_file, logger=self.logger, wan_name=self.wan_name
        )
        self._dl_zone: str = "GREEN"
        self._ul_zone: str = "GREEN"
        self._cycles_since_forced_save = 0

    def _init_metrics_storage(self) -> None:
        """Initialize optional SQLite metrics history storage."""
        storage_config = get_storage_config(self.config.data)
        self._metrics_writer: MetricsWriter | None = None
        self._storage_db_path: str | None = None
        self._download_labels = {"direction": "download"}
        self._upload_labels = {"direction": "upload"}
        db_path = storage_config.get("db_path")
        if db_path and isinstance(db_path, str):
            self._storage_db_path = db_path
            self._metrics_writer = MetricsWriter(Path(db_path))
            self.logger.info(f"{self.wan_name}: Metrics history enabled, db={db_path}")

    def _init_alerting(self) -> None:
        """Initialize alert engine and webhook delivery from alerting config."""
        ac = self.config.alerting_config
        if ac:
            # Validate webhook_url
            url = ac["webhook_url"]
            if url and not url.startswith("https://"):
                self.logger.warning(
                    "alerting.webhook_url must start with https://; delivery disabled"
                )
                url = ""
            if not url:
                self.logger.warning(
                    "alerting.webhook_url not set; alerts will fire and persist but not deliver"
                )

            from wanctl import __version__
            from wanctl.webhook_delivery import DiscordFormatter, WebhookDelivery

            formatter = DiscordFormatter(version=__version__, container_id=self.wan_name)
            self._webhook_delivery: WebhookDelivery | None = WebhookDelivery(
                formatter=formatter,
                webhook_url=url,
                max_per_minute=ac["max_webhooks_per_minute"],
                writer=self._metrics_writer,
                mention_role_id=ac["mention_role_id"],
                mention_severity=ac["mention_severity"],
            )
            self.alert_engine = AlertEngine(
                enabled=True,
                default_cooldown_sec=ac["default_cooldown_sec"],
                rules=ac["rules"],
                writer=self._metrics_writer,
                delivery_callback=self._webhook_delivery.deliver,
            )
        else:
            self._webhook_delivery = None
            self.alert_engine = AlertEngine(enabled=False, default_cooldown_sec=300, rules={})

    def _init_signal_processing(self) -> None:
        """Initialize Hampel filter signal processor."""
        self.signal_processor = SignalProcessor(
            wan_name=self.wan_name,
            config=self.config.signal_processing_config,
            logger=self.logger,
        )
        self._last_signal_result: SignalResult | None = None

    def _init_irtt_and_fusion(self) -> None:
        """Initialize IRTT observation, OWD asymmetry, and dual-signal fusion."""
        config = self.config

        # IRTT observation mode (set by main() if IRTT active)
        self._irtt_thread: IRTTThread | None = None
        self._irtt_correlation: float | None = None
        self._irtt_deprioritization_logged: bool = False
        self._irtt_deprioritization_last_transition_ts: float = 0.0
        self._irtt_deprioritization_log_cooldown_sec: float = 5.0
        self._last_irtt_write_ts: float | None = None  # IRTT dedup (OBSV-04)

        # OWD asymmetry detection (ASYM-01 through ASYM-03)
        owd_config = config.owd_asymmetry_config
        self._asymmetry_analyzer: AsymmetryAnalyzer | None = AsymmetryAnalyzer(
            ratio_threshold=owd_config["ratio_threshold"],
            logger=self.logger,
            wan_name=self.wan_name,
        )
        self._last_asymmetry_result: AsymmetryResult | None = None

        # Asymmetry gate (Phase 156: ASYM-01 through ASYM-03)
        gate_cfg = config.asymmetry_gate_config
        self._asymmetry_gate_enabled: bool = bool(gate_cfg["enabled"])
        self._asymmetry_damping_factor: float = float(gate_cfg["damping_factor"])
        self._asymmetry_min_ratio: float = float(gate_cfg["min_ratio"])
        self._asymmetry_confirm_readings: int = int(gate_cfg["confirm_readings"])
        self._asymmetry_staleness_sec: float = float(gate_cfg["staleness_sec"])
        self._asymmetry_gate_active: bool = False
        self._asymmetry_downstream_streak: int = 0
        self._last_asymmetry_result_ts: float = 0.0

        # Dual-signal fusion (FUSE-01, FUSE-03, FUSE-04)
        self._fusion_icmp_weight: float = config.fusion_config["icmp_weight"]
        self._fusion_enabled: bool = config.fusion_config["enabled"]
        self._last_fused_rtt: float | None = None
        self._last_icmp_filtered_rtt: float | None = None
        self._last_raw_rtt: float | None = None
        self._last_raw_rtt_ts: float | None = None
        self._last_active_reflector_hosts: list[str] = []
        self._last_successful_reflector_hosts: list[str] = []

        # Fusion healing (Phase 119: FUSE-01 through FUSE-05)
        self._fusion_healer: FusionHealer | None = None
        self._prev_healer_icmp_rtt: float | None = None
        self._prev_healer_irtt_rtt: float | None = None
        self._prev_irtt_ts: float | None = None

    def _init_reflector_scoring(self) -> None:
        """Initialize per-reflector rolling quality scoring."""
        rq_config = self.config.reflector_quality_config
        self._reflector_scorer = ReflectorScorer(
            hosts=self.config.ping_hosts,
            min_score=rq_config["min_score"],
            window_size=rq_config["window_size"],
            probe_interval_sec=rq_config["probe_interval_sec"],
            recovery_count=rq_config["recovery_count"],
            logger=self.logger,
            wan_name=self.wan_name,
        )

    def _init_alert_timers(self) -> None:
        """Initialize sustained congestion, connectivity, IRTT loss, and flapping timers."""
        ac = self.config.alerting_config

        # Sustained congestion timers (ALRT-01)
        self._dl_congestion_start: float | None = None
        self._ul_congestion_start: float | None = None
        self._dl_sustained_fired: bool = False
        self._ul_sustained_fired: bool = False
        self._dl_last_congested_zone: str = "RED"
        self._sustained_sec: int = ac.get("default_sustained_sec", 60) if ac else 60

        # Connectivity alert timers (ALRT-04, ALRT-05)
        self._connectivity_offline_start: float | None = None
        self._wan_offline_fired: bool = False

        # IRTT loss alert timers (ALRT-01, ALRT-02, ALRT-03)
        self._irtt_loss_up_start: float | None = None
        self._irtt_loss_down_start: float | None = None
        self._irtt_loss_up_fired: bool = False
        self._irtt_loss_down_fired: bool = False
        self._irtt_loss_threshold_pct: float = 5.0

        # Congestion flapping detection (ALRT-07)
        self._dl_zone_transitions: deque[float] = deque()
        self._ul_zone_transitions: deque[float] = deque()
        self._dl_prev_zone: str | None = None
        self._ul_prev_zone: str | None = None
        self._dl_zone_hold: int = 0  # cycles current DL zone has been held
        self._ul_zone_hold: int = 0  # cycles current UL zone has been held

        # Sustained latency regression / burst churn alerts (v1.34 Phase 167)
        self._latency_regression_start: float | None = None
        self._latency_regression_active: bool = False
        self._burst_transition_timestamps: deque[float] = deque()
        self._burst_last_seen_trigger_count: int = 0

    def _init_profiling(self) -> None:
        """Initialize profiling instrumentation, cycle budget monitoring, and background RTT."""
        config = self.config

        # Profiling instrumentation (PROF-01, PROF-02)
        self._profiler = OperationProfiler(max_samples=1200)
        self._profile_cycle_count = 0
        self._profiling_enabled = False
        self._overrun_count = 0
        self._cycle_interval_ms = CYCLE_INTERVAL_SECONDS * 1000.0

        # Cycle budget regression indicator (Phase 132: PERF-03)
        cm_config = config.data.get("continuous_monitoring", {}) if config.data else {}
        if not isinstance(cm_config, dict):
            cm_config = {}
        self._warning_threshold_pct: float = float(cm_config.get("warning_threshold_pct", 80.0))
        self._budget_warning_streak: int = 0
        self._budget_warning_consecutive: int = 60  # 60 cycles = 3 seconds at 50ms

        # Hysteresis observability (Phase 136: HYST-01/HYST-02)
        self._suppression_alert_threshold: int = int(
            cm_config.get("thresholds", {}).get("suppression_alert_threshold", 20)
            if isinstance(cm_config.get("thresholds"), dict) else 20
        )

        # Background RTT measurement (Phase 132: PERF-02)
        self._rtt_thread: BackgroundRTTThread | None = None
        self._rtt_pool: concurrent.futures.ThreadPoolExecutor | None = None

        # Background CAKE stats thread (offloads 7-20ms netlink I/O from main loop)
        self._cake_stats_thread: BackgroundCakeStatsThread | None = None

        # Deferred I/O worker (Phase 155: CYCLE-02)
        self._io_worker: DeferredIOWorker | None = None

    def _init_tuning(self) -> None:
        """Initialize adaptive tuning state and oscillation detection."""
        config = self.config

        if config.tuning_config is not None and config.tuning_config.enabled:
            self._tuning_enabled = True
            self._tuning_state: TuningState | None = TuningState(
                enabled=True,
                last_run_ts=None,
                recent_adjustments=[],
                parameters={},
            )
        else:
            self._tuning_enabled = False
            self._tuning_state = None
        self._last_tuning_ts: float | None = None
        self._tuning_layer_index: int = 0
        self._parameter_locks: dict[str, float] = {}  # param -> monotonic lock expiry
        self._pending_observation = None  # PendingObservation | None (lazy import)

        # Oscillation lockout threshold (RTUN-04)
        from wanctl.tuning.strategies.response import DEFAULT_OSCILLATION_THRESHOLD

        osc_raw = config.data.get("tuning", {}).get("oscillation_threshold")
        if (
            osc_raw is not None
            and isinstance(osc_raw, (int, float))
            and not isinstance(osc_raw, bool)
        ):
            self._oscillation_threshold: float = float(osc_raw)
        else:
            self._oscillation_threshold = DEFAULT_OSCILLATION_THRESHOLD

    def _init_cake_signal(self) -> None:
        """Initialize CAKE signal processing from YAML config (Phase 159, CAKE-05).

        Creates CakeSignalProcessor instances for download and upload.
        Only active when transport is linux-cake (LinuxCakeAdapter).
        """
        from wanctl.backends.linux_cake_adapter import LinuxCakeAdapter
        from wanctl.cake_signal import CakeSignalProcessor, CakeSignalSnapshot

        self._cake_signal_supported = isinstance(self.router, LinuxCakeAdapter)

        config = self._parse_cake_signal_config()
        self._dl_cake_signal = CakeSignalProcessor(config=config)
        self._ul_cake_signal = CakeSignalProcessor(config=config)
        self._dl_cake_snapshot: CakeSignalSnapshot | None = None
        self._ul_cake_snapshot: CakeSignalSnapshot | None = None

        # Refractory period counters (Phase 160: DETECT-03)
        self._dl_refractory_remaining: int = 0
        self._ul_refractory_remaining: int = 0
        self._refractory_cycles: int = config.refractory_cycles

        # Pass detection thresholds to QueueControllers (Phase 160: DETECT-01, DETECT-02)
        if config.enabled and self._cake_signal_supported:
            if config.drop_rate_enabled:
                self.download._drop_rate_threshold = config.drop_rate_threshold
                self.upload._drop_rate_threshold = config.drop_rate_threshold
            if config.backlog_enabled:
                self.download._backlog_threshold_bytes = config.backlog_threshold_bytes
                self.upload._backlog_threshold_bytes = config.backlog_threshold_bytes
            # Phase 161: Wire probe recovery params
            self.download._probe_multiplier_factor = config.probe_multiplier_factor
            self.download._probe_ceiling_pct = config.probe_ceiling_pct
            self.upload._probe_multiplier_factor = config.probe_multiplier_factor
            self.upload._probe_ceiling_pct = config.probe_ceiling_pct

        if config.enabled and self._cake_signal_supported:
            self.logger.info(
                "%s: CAKE signal enabled (drop_rate=%s, backlog=%s, peak_delay=%s, "
                "metrics=%s, tc=%.1fs, drop_thresh=%.1f, backlog_thresh=%d, "
                "refractory=%d, probe_mult=%.1f, probe_ceil=%.0f%%)",
                self.wan_name, config.drop_rate_enabled, config.backlog_enabled,
                config.peak_delay_enabled, config.metrics_enabled,
                config.time_constant_sec, config.drop_rate_threshold,
                config.backlog_threshold_bytes, config.refractory_cycles,
                config.probe_multiplier_factor, config.probe_ceiling_pct * 100,
            )
        elif config.enabled and not self._cake_signal_supported:
            self.logger.warning(
                "%s: CAKE signal enabled in config but transport is not linux-cake -- disabled",
                self.wan_name,
            )

    def _parse_cake_signal_config(self) -> Any:
        """Parse cake_signal section from YAML config file.

        Returns CakeSignalConfig with all booleans defaulting to False
        and time_constant_sec defaulting to 1.0 if section missing or invalid.
        """
        from wanctl.cake_signal import CakeSignalConfig

        try:
            import yaml

            with open(self.config.config_file_path) as f:
                data = yaml.safe_load(f)
        except Exception:
            return CakeSignalConfig()

        cs = data.get("cake_signal", {}) if data else {}
        if not isinstance(cs, dict):
            return CakeSignalConfig()

        enabled = cs.get("enabled", False)
        if not isinstance(enabled, bool):
            enabled = False

        dr = cs.get("drop_rate", {})
        if not isinstance(dr, dict):
            dr = {}
        drop_rate_enabled = dr.get("enabled", False) is True

        tc_sec = dr.get("time_constant_sec", 1.0)
        if not isinstance(tc_sec, (int, float)) or isinstance(tc_sec, bool) or tc_sec <= 0:
            tc_sec = 1.0
        tc_sec = float(tc_sec)
        # Bounds: [0.1, 30.0]
        tc_sec = max(0.1, min(30.0, tc_sec))

        bl = cs.get("backlog", {})
        if not isinstance(bl, dict):
            bl = {}
        backlog_enabled = bl.get("enabled", False) is True

        pd = cs.get("peak_delay", {})
        if not isinstance(pd, dict):
            pd = {}
        peak_delay_enabled = pd.get("enabled", False) is True

        mt = cs.get("metrics", {})
        if not isinstance(mt, dict):
            mt = {}
        metrics_enabled = mt.get("enabled", False) is True

        # Detection thresholds (Phase 160)
        drop_rate_threshold = dr.get("threshold_drops_per_sec", 10.0)
        if not isinstance(drop_rate_threshold, (int, float)) or isinstance(drop_rate_threshold, bool) or drop_rate_threshold <= 0:
            drop_rate_threshold = 10.0
        drop_rate_threshold = max(1.0, min(1000.0, float(drop_rate_threshold)))

        backlog_threshold = bl.get("threshold_bytes", 10000)
        if not isinstance(backlog_threshold, (int, float)) or isinstance(backlog_threshold, bool) or backlog_threshold <= 0:
            backlog_threshold = 10000
        backlog_threshold = max(100, min(10_000_000, int(backlog_threshold)))

        # Detection section for refractory
        det = cs.get("detection", {})
        if not isinstance(det, dict):
            det = {}
        refractory_cycles = det.get("refractory_cycles", 40)
        if not isinstance(refractory_cycles, (int, float)) or isinstance(refractory_cycles, bool) or refractory_cycles <= 0:
            refractory_cycles = 40
        refractory_cycles = max(1, min(200, int(refractory_cycles)))

        # Recovery section (Phase 161: RECOV-01, RECOV-02)
        probe_multiplier, probe_ceiling_pct = WANController._parse_recovery_config(cs)

        return CakeSignalConfig(
            enabled=enabled,
            drop_rate_enabled=drop_rate_enabled,
            backlog_enabled=backlog_enabled,
            peak_delay_enabled=peak_delay_enabled,
            metrics_enabled=metrics_enabled,
            time_constant_sec=tc_sec,
            drop_rate_threshold=drop_rate_threshold,
            backlog_threshold_bytes=backlog_threshold,
            refractory_cycles=refractory_cycles,
            probe_multiplier_factor=probe_multiplier,
            probe_ceiling_pct=probe_ceiling_pct,
        )

    @staticmethod
    def _parse_recovery_config(cs: dict) -> tuple[float, float]:
        """Parse recovery sub-section from cake_signal config (Phase 161).

        Returns:
            (probe_multiplier, probe_ceiling_pct) with validated bounds.
        """
        rec = cs.get("recovery", {})
        if not isinstance(rec, dict):
            rec = {}

        probe_multiplier = rec.get("probe_multiplier", 1.5)
        if not isinstance(probe_multiplier, (int, float)) or isinstance(probe_multiplier, bool) or probe_multiplier < 1.0:
            probe_multiplier = 1.5
        probe_multiplier = max(1.0, min(5.0, float(probe_multiplier)))

        probe_ceiling_pct = rec.get("probe_ceiling_pct", 0.9)
        if not isinstance(probe_ceiling_pct, (int, float)) or isinstance(probe_ceiling_pct, bool) or probe_ceiling_pct <= 0:
            probe_ceiling_pct = 0.9
        probe_ceiling_pct = max(0.5, min(1.0, float(probe_ceiling_pct)))

        return probe_multiplier, probe_ceiling_pct

    def _restore_tuning_params(self) -> None:
        """Restore latest tuning parameter values from SQLite.

        Reads the most recent non-reverted adjustment per parameter for this WAN
        from the tuning_params table. Applies values via _apply_tuning_to_controller
        (same path as live tuning). Only called when tuning is enabled and db exists.
        """
        from wanctl.storage.reader import query_tuning_params
        from wanctl.tuning.models import TuningResult

        try:
            if self._metrics_writer is None:
                return
            db_path = getattr(self._metrics_writer, "_db_path", None) or getattr(
                self._metrics_writer,
                "db_path",
                None,
            )
            if db_path is None:
                return
            rows = query_tuning_params(db_path=db_path, wan=self.wan_name)
            if not rows:
                self.logger.info(f"{self.wan_name}: No prior tuning params to restore")
                return

            # Get latest non-reverted value per parameter
            latest: dict[str, dict] = {}
            for row in rows:  # Already ordered by timestamp DESC
                param = row["parameter"]
                if param not in latest and not row.get("reverted", 0):
                    latest[param] = row

            if not latest:
                self.logger.info(f"{self.wan_name}: No non-reverted tuning params to restore")
                return

            # Build TuningResult list for _apply_tuning_to_controller
            results = []
            for param, row in latest.items():
                results.append(
                    TuningResult(
                        parameter=param,
                        old_value=row["old_value"],
                        new_value=row["new_value"],
                        confidence=row["confidence"],
                        rationale=f"Restored from SQLite (ts={row['timestamp']})",
                        data_points=row["data_points"],
                        wan_name=self.wan_name,
                    )
                )

            _apply_tuning_to_controller(self, results)
            param_summary = ", ".join(f"{r.parameter}={r.new_value}" for r in results)
            self.logger.info(
                f"{self.wan_name}: Restored {len(results)} tuning params: {param_summary}"
            )
        except Exception as e:
            self.logger.warning(
                f"{self.wan_name}: Failed to restore tuning params (using defaults): {e}"
            )

    def start_background_rtt(self, shutdown_event: threading.Event) -> None:
        """Start background RTT measurement thread (Phase 132: D-01, D-05).

        Creates a persistent ThreadPoolExecutor and BackgroundRTTThread that
        runs ICMP pings on the controller cadence. The control loop reads from
        the shared variable via measure_rtt() instead of blocking on ICMP I/O.
        """
        max_workers = max(3, len(self.config.ping_hosts))
        self._rtt_pool = concurrent.futures.ThreadPoolExecutor(
            max_workers=max_workers,
            thread_name_prefix="wanctl-rtt-ping",
        )
        self._rtt_thread = BackgroundRTTThread(
            rtt_measurement=self.rtt_measurement,
            hosts_fn=self._reflector_scorer.get_active_hosts,
            shutdown_event=shutdown_event,
            logger=self.logger,
            pool=self._rtt_pool,
            cadence_sec=self._cycle_interval_ms / 1000.0,
        )
        self._rtt_thread.start()

    def start_background_cake_stats(self, shutdown_event: threading.Event) -> None:
        """Start background CAKE stats thread if transport supports it.

        Creates a BackgroundCakeStatsThread with its own IPRoute connections
        that reads CAKE qdisc stats continuously. The main loop reads cached
        results via _run_cake_stats() instead of blocking on 7-20ms netlink I/O.
        """
        if not self._cake_signal_supported:
            return
        if not self._dl_cake_signal.config.enabled and not self._ul_cake_signal.config.enabled:
            return
        if not self._dl_cake_signal.config.enabled and not self._ul_cake_signal.config.enabled:
            return

        from wanctl.backends.linux_cake_adapter import LinuxCakeAdapter

        adapter: LinuxCakeAdapter = self.router  # type: ignore[assignment]
        self._cake_stats_thread = BackgroundCakeStatsThread(
            dl_interface=adapter.dl_backend.interface,
            ul_interface=adapter.ul_backend.interface,
            shutdown_event=shutdown_event,
            cadence_sec=self._cycle_interval_ms / 1000.0,
        )
        self._cake_stats_thread.start()

    def measure_rtt(self) -> float | None:
        """Read latest RTT from background thread (non-blocking).

        Per D-01: Reads GIL-protected shared variable instead of blocking on ICMP.
        Per D-04: Staleness detection -- warn at 500ms, fail at 5s.
        ReflectorScorer integration preserved -- per-host results from snapshot.

        Falls back to blocking measurement if background thread not started
        (e.g., during tests or startup race).
        """
        if self._rtt_thread is None:
            # Fallback: no background thread (e.g., tests or startup race)
            return self._measure_rtt_blocking()

        snapshot = self._rtt_thread.get_latest()
        if snapshot is None:
            self.logger.warning(
                f"{self.wan_name}: No RTT data available (background thread starting)"
            )
            return None

        age = time.monotonic() - snapshot.timestamp
        if age > 5.0:  # Hard limit per D-04
            self.logger.warning(
                f"{self.wan_name}: RTT data stale ({age:.1f}s), treating as failure"
            )
            return None
        if age > 0.5:  # Soft warning per D-04
            self.logger.debug(f"{self.wan_name}: RTT data aging ({age:.1f}s)")

        # Record per-host results for quality scoring (same as before)
        self._reflector_scorer.record_results(
            {host: rtt_val is not None for host, rtt_val in snapshot.per_host_results.items()}
        )
        self._persist_reflector_events()
        self._record_live_rtt_snapshot(
            rtt_ms=snapshot.rtt_ms,
            timestamp=snapshot.timestamp,
            active_hosts=list(snapshot.active_hosts or snapshot.per_host_results.keys()),
            successful_hosts=list(
                snapshot.successful_hosts
                or (host for host, rtt_val in snapshot.per_host_results.items() if rtt_val is not None)
            ),
        )

        return snapshot.rtt_ms

    def _measure_rtt_blocking(self) -> float | None:
        """
        Measure RTT via blocking ICMP (fallback when background thread unavailable).

        Uses ReflectorScorer to select active (non-deprioritized) hosts, then
        pings them concurrently with per-host attribution for quality tracking.

        Graceful degradation based on active host count:
        - 3+ active: median-of-N (handles reflector variation)
        - 2 active: average-of-2
        - 1 active: single ping value
        - 0 active: impossible (get_active_hosts forces best-scoring)

        Per-host results are recorded back to ReflectorScorer for rolling
        quality scoring, and any deprioritization/recovery events are persisted.
        """
        active_hosts = self._reflector_scorer.get_active_hosts()

        # Ping active hosts with per-host attribution
        results = self.rtt_measurement.ping_hosts_with_results(
            hosts=active_hosts, count=1, timeout=3.0
        )

        # Record per-host results for quality scoring
        self._reflector_scorer.record_results(
            {host: rtt_val is not None for host, rtt_val in results.items()}
        )

        # Persist any deprioritization/recovery events
        self._persist_reflector_events()

        # Extract successful RTT values
        rtts = [v for v in results.values() if v is not None]

        if not rtts:
            self.logger.warning(f"{self.wan_name}: All pings failed")
            return None

        # Graceful degradation based on available results
        if len(rtts) >= 3:
            rtt = statistics.median(rtts)
            self.logger.debug(f"{self.wan_name}: Median-of-{len(rtts)} RTT = {rtt:.2f}ms")
        elif len(rtts) == 2:
            rtt = statistics.mean(rtts)
            self.logger.debug(f"{self.wan_name}: Average-of-2 RTT = {rtt:.2f}ms")
        else:
            rtt = rtts[0]

        self._record_live_rtt_snapshot(
            rtt_ms=float(rtt),
            timestamp=time.monotonic(),
            active_hosts=active_hosts,
            successful_hosts=[host for host, rtt_val in results.items() if rtt_val is not None],
        )
        return rtt

    def _record_live_rtt_snapshot(
        self,
        *,
        rtt_ms: float,
        timestamp: float,
        active_hosts: list[str],
        successful_hosts: list[str],
    ) -> None:
        """Publish the latest direct ICMP RTT snapshot for observability/steering."""
        self._last_raw_rtt = float(rtt_ms)
        self._last_raw_rtt_ts = timestamp
        self._last_active_reflector_hosts = list(active_hosts)
        self._last_successful_reflector_hosts = list(successful_hosts)

    def _persist_reflector_events(self) -> None:
        """Persist any pending reflector deprioritization/recovery events to SQLite.

        Drains transition events from ReflectorScorer and writes them to the
        reflector_events table. Never raises -- follows AlertEngine pattern.
        """
        if self._metrics_writer is None:
            return
        if not self._reflector_scorer.has_pending_events():
            return

        events = self._reflector_scorer.drain_events()
        if not events:
            return
        timestamp = int(time.time())
        for event in events:
            try:
                details_json = json.dumps(
                    {
                        "host": event["host"],
                        "score": round(event["score"], 3),
                        "event": event["event_type"],
                    }
                )
                if self._io_worker is not None:
                    self._io_worker.enqueue_reflector_event(
                        timestamp=timestamp,
                        event_type=event["event_type"],
                        host=event["host"],
                        wan_name=self.wan_name,
                        score=round(event["score"], 3),
                        details_json=details_json,
                    )
                else:
                    writer_method = getattr(type(self._metrics_writer), "write_reflector_event", None)
                    if callable(writer_method):
                        self._metrics_writer.write_reflector_event(
                            timestamp,
                            event["event_type"],
                            event["host"],
                            self.wan_name,
                            round(event["score"], 3),
                            details_json,
                        )
                    else:
                        self._metrics_writer.connection.execute(
                            "INSERT INTO reflector_events "
                            "(timestamp, event_type, host, wan_name, score, details) "
                            "VALUES (?, ?, ?, ?, ?, ?)",
                            (
                                timestamp,
                                event["event_type"],
                                event["host"],
                                self.wan_name,
                                round(event["score"], 3),
                                details_json,
                            ),
                        )
            except Exception:
                self.logger.warning(
                    "Failed to persist reflector event %s for %s",
                    event["event_type"],
                    event["host"],
                    exc_info=True,
                )

    def update_ewma(self, measured_rtt: float) -> None:
        """
        Update both EWMAs (fast load, slow baseline).

        Fast EWMA (load_rtt): Responsive to current conditions, always updates.
        Slow EWMA (baseline_rtt): Only updates when line is idle (delta < threshold).
        """
        # Fast EWMA for load_rtt (responsive to current conditions)
        self.load_rtt = (1 - self.alpha_load) * self.load_rtt + self.alpha_load * measured_rtt

        # Slow EWMA for baseline_rtt (conditional update via protected logic)
        self._update_baseline_if_idle(measured_rtt)

    def _update_baseline_if_idle(self, icmp_rtt: float) -> None:
        """
        Update baseline RTT ONLY when line is idle (delta < threshold).

        PROTECTED ZONE - ARCHITECTURAL INVARIANT
        =========================================
        This logic prevents baseline drift under load. If baseline tracked load RTT,
        delta would approach zero and bloat detection would fail. The threshold
        (baseline_update_threshold) determines "idle" vs "under load".

        Uses ICMP-only signal (not fused RTT) for both the freeze gate and the
        baseline EWMA. This prevents IRTT path divergence from corrupting baseline
        semantics. Baseline is an ICMP-derived concept representing idle propagation
        delay; fusing a different-path IRTT signal corrupts its meaning.

        DO NOT MODIFY without explicit approval. See docs/CORE-ALGORITHM-ANALYSIS.md.

        Args:
            icmp_rtt: ICMP-only filtered RTT in milliseconds (Hampel-filtered,
                pre-fusion). Must NOT be the fused ICMP+IRTT signal.

        Side Effects:
            Updates self.baseline_rtt if delta < threshold (line is idle).
            Logs debug message when baseline updates (helps debug drift issues).
        """
        delta = icmp_rtt - self.baseline_rtt

        # PROTECTED: Baseline ONLY updates when line is idle
        if delta < self.baseline_update_threshold:
            # Line is idle or nearly idle - safe to update baseline
            old_baseline = self.baseline_rtt
            new_baseline = (
                1 - self.alpha_baseline
            ) * self.baseline_rtt + self.alpha_baseline * icmp_rtt

            # Security bounds check - reject corrupted/invalid baseline values
            if not (self.baseline_rtt_min <= new_baseline <= self.baseline_rtt_max):
                self.logger.warning(
                    f"{self.wan_name}: Baseline RTT {new_baseline:.1f}ms outside bounds "
                    f"[{self.baseline_rtt_min}-{self.baseline_rtt_max}ms], ignoring"
                )
                return

            self.baseline_rtt = new_baseline
            self.logger.debug(
                f"{self.wan_name}: Baseline updated {old_baseline:.2f}ms -> "
                f"{self.baseline_rtt:.2f}ms "
                f"(delta={delta:.1f}ms < threshold={self.baseline_update_threshold}ms)"
            )
        # else: Under load - freeze baseline (no update, no logging to avoid spam)

    def verify_local_connectivity(self) -> bool:
        """
        Check if we can reach local gateway via ICMP.

        Returns:
            True if gateway is reachable (WAN issue, not container networking)
            False if gateway unreachable (container networking problem)
        """
        if not self.config.fallback_check_gateway:
            return False

        gateway_ip = self.config.fallback_gateway_ip
        if not gateway_ip:
            return False
        result = self.rtt_measurement.ping_host(gateway_ip, count=1)
        if result is not None:
            self.logger.warning(
                f"{self.wan_name}: External pings failed but gateway {gateway_ip} reachable - "
                f"likely WAN issue, not container networking"
            )
            return True
        return False

    def verify_tcp_connectivity(self) -> tuple[bool, float | None]:
        """
        Check if we can establish TCP connections (HTTPS) and measure RTT.

        Tests multiple targets using TCP handshake to verify Internet connectivity
        when ICMP is blocked/filtered. Times successful connections to provide
        TCP-based RTT as fallback for ICMP.

        Returns:
            (connected, rtt_ms):
            - connected: True if ANY TCP connection succeeds
            - rtt_ms: Median RTT in milliseconds from successful connections, or None
        """
        if not self.config.fallback_check_tcp:
            return (False, None)

        rtts: list[float] = []
        for host, port in self.config.fallback_tcp_targets:
            try:
                start = time.monotonic()
                sock = socket.create_connection((host, port), timeout=0.5)
                sock.close()
                rtt_ms = (time.monotonic() - start) * 1000
                rtts.append(rtt_ms)
                self.logger.debug(f"TCP to {host}:{port} succeeded, RTT={rtt_ms:.1f}ms")
            except (TimeoutError, OSError, socket.gaierror) as e:
                self.logger.debug(f"TCP to {host}:{port} failed: {e}")
                continue

        if rtts:
            median_rtt = statistics.median(rtts) if len(rtts) > 1 else rtts[0]
            self.logger.info(
                f"{self.wan_name}: TCP connectivity verified, RTT={median_rtt:.1f}ms "
                f"(from {len(rtts)} targets)"
            )
            return (True, median_rtt)

        return (False, None)  # All TCP attempts failed

    def verify_connectivity_fallback(self) -> tuple[bool, float | None]:
        """
        Multi-protocol connectivity verification with TCP RTT measurement.

        When all ICMP pings fail, verify if we have ANY connectivity
        using alternative protocols before declaring total failure.
        Also measures TCP RTT to provide fallback latency data.

        Returns:
            (has_connectivity, tcp_rtt_ms):
            - has_connectivity: True if ANY connectivity detected
            - tcp_rtt_ms: TCP RTT in milliseconds if measured, None otherwise
        """
        if not self.config.fallback_enabled:
            return (False, None)

        self.logger.warning(f"{self.wan_name}: All ICMP pings failed - running fallback checks")

        # Check 1: Local gateway (fastest, ~50ms)
        # Note: Gateway RTT is not useful for WAN latency measurement
        gateway_ok = self.verify_local_connectivity()

        # Check 2: TCP HTTPS (most reliable, measures WAN RTT)
        tcp_ok, tcp_rtt = self.verify_tcp_connectivity()

        if tcp_ok:
            # TCP succeeded - we have connectivity AND RTT measurement
            if gateway_ok:
                self.logger.warning(
                    f"{self.wan_name}: External pings failed but gateway and TCP reachable - "
                    f"ICMP filtering detected"
                )
            return (True, tcp_rtt)

        if gateway_ok:
            # Gateway OK but TCP failed - partial connectivity
            self.logger.warning(
                f"{self.wan_name}: External pings failed but gateway reachable - "
                f"likely WAN issue, not container networking"
            )
            return (True, None)

        # Both fail - total connectivity loss
        self.logger.error(
            f"{self.wan_name}: Both ICMP and TCP connectivity failed - "
            f"confirmed total connectivity loss"
        )
        return (False, None)

    def apply_rate_changes_if_needed(self, dl_rate: int, ul_rate: int) -> bool:
        """
        Apply rate changes to router with flash wear protection and rate limiting.

        Only sends updates to router when rates have actually changed (flash wear
        protection) and within the rate limit window (API overload protection).

        PROTECTED LOGIC - RouterOS writes queue changes to NAND flash. Repeated
        writes accelerate flash wear. See docs/CORE-ALGORITHM-ANALYSIS.md.

        Args:
            dl_rate: Download rate in bits per second
            ul_rate: Upload rate in bits per second

        Returns:
            True if cycle should continue (rates applied or skipped),
            False if router update failed (triggers watchdog restart)

        Side Effects:
            - Updates last_applied_dl_rate/last_applied_ul_rate on success
            - Records rate_limiter change on successful router update
            - Records metrics (router_update, rate_limit_event)
            - Calls save_state() when rate limited
        """
        # =====================================================================
        # FAIL-CLOSED: Queue rates when router unreachable (ERRR-03)
        # Rates are preserved for later application instead of being discarded.
        # =====================================================================
        if not self.router_connectivity.is_reachable:
            self.pending_rates.queue(dl_rate, ul_rate)
            self.logger.debug(
                f"{self.wan_name}: Router unreachable, queuing rate change "
                f"(DL={dl_rate / 1e6:.1f}Mbps, UL={ul_rate / 1e6:.1f}Mbps)"
            )
            return True  # Cycle succeeds - rates queued for later

        # =====================================================================
        # PROTECTED: Flash wear protection - only send queue limits when values change.
        # Router NAND has 100K-1M write cycles. See docs/CORE-ALGORITHM-ANALYSIS.md.
        # =====================================================================
        if dl_rate == self.last_applied_dl_rate and ul_rate == self.last_applied_ul_rate:
            self.logger.debug(
                f"{self.wan_name}: Rates unchanged, skipping router update (flash wear protection)"
            )
            return True  # Success - no update needed

        # =====================================================================
        # PROTECTED: Rate limiting prevents RouterOS API overload (RB5009 limit ~50 req/sec).
        # When rate_limiter is None (linux-cake), this block is skipped entirely (RATE-02, RATE-05).
        # =====================================================================
        if self.rate_limiter is not None and not self.rate_limiter.can_change():
            # Log once when entering throttled state (not every cycle)
            if not self._rate_limit_logged:
                wait_time = self.rate_limiter.time_until_available()
                self.logger.debug(
                    f"{self.wan_name}: Rate limit active "
                    f"(>{self.rate_limiter.max_changes} changes/"
                    f"{self.rate_limiter.window_seconds}s), throttling updates "
                    f"(next slot in {wait_time:.1f}s)"
                )
                self._rate_limit_logged = True
            if self.config.metrics_enabled:
                record_rate_limit_event(self.wan_name)
            # Still return True - cycle completed, just throttled the update
            # Save state to preserve EWMA and streak counters
            self.save_state()
            return True

        # Apply to router
        success = self.router.set_limits(wan=self.wan_name, down_bps=dl_rate, up_bps=ul_rate)

        if not success:
            self.logger.error(f"{self.wan_name}: Failed to apply limits")
            return False

        # Record successful change for rate limiting (only when rate limiter active)
        if self.rate_limiter is not None:
            self.rate_limiter.record_change()
        self._rate_limit_logged = False  # Reset so we log next throttle window

        # Record metrics for router update
        if self.config.metrics_enabled:
            record_router_update(self.wan_name)

        # Update tracking after successful write
        self.last_applied_dl_rate = dl_rate
        self.last_applied_ul_rate = ul_rate
        self.pending_rates.clear()
        self.logger.debug(f"{self.wan_name}: Applied new limits to router")
        return True

    def handle_icmp_failure(self) -> tuple[bool, float | None]:
        """
        Handle ICMP ping failure with TCP RTT fallback.

        Called when measure_rtt() returns None. Runs fallback connectivity checks
        (gateway ping, TCP handshake with RTT measurement). If TCP RTT is available,
        uses it directly. Otherwise applies mode-specific degradation behavior.

        Returns:
            (should_continue, measured_rtt):
            - should_continue: True if cycle should proceed, False to trigger restart
            - measured_rtt: RTT value (TCP or last known), or None to freeze rates

        Note:
            TCP RTT is preferred over stale ICMP data when available.
        """
        if self.config.metrics_enabled:
            record_ping_failure(self.wan_name)

        # Run fallback connectivity checks (now includes TCP RTT measurement)
        has_connectivity, tcp_rtt = self.verify_connectivity_fallback()

        if has_connectivity:
            self.icmp_unavailable_cycles += 1

            # If we have TCP RTT, use it directly - no degradation needed
            if tcp_rtt is not None:
                self.logger.warning(
                    f"{self.wan_name}: ICMP unavailable - using TCP RTT={tcp_rtt:.1f}ms as fallback"
                )
                return (True, tcp_rtt)

            # No TCP RTT available (gateway-only connectivity) - use degradation modes
            if self.config.fallback_mode == "graceful_degradation":
                if self.icmp_unavailable_cycles == 1:
                    measured_rtt = self.load_rtt
                    self.logger.warning(
                        f"{self.wan_name}: ICMP unavailable, no TCP RTT (cycle 1/"
                        f"{self.config.fallback_max_cycles}) - using last RTT={measured_rtt:.1f}ms"
                    )
                    return (True, measured_rtt)
                if self.icmp_unavailable_cycles <= self.config.fallback_max_cycles:
                    self.logger.warning(
                        f"{self.wan_name}: ICMP unavailable, no TCP RTT "
                        f"(cycle {self.icmp_unavailable_cycles}/"
                        f"{self.config.fallback_max_cycles}) - freezing rates"
                    )
                    return (True, None)
                self.logger.error(
                    f"{self.wan_name}: ICMP unavailable for "
                    f"{self.icmp_unavailable_cycles} cycles "
                    f"(>{self.config.fallback_max_cycles}) - giving up"
                )
                return (False, None)

            if self.config.fallback_mode == "freeze":
                self.logger.warning(
                    f"{self.wan_name}: ICMP unavailable - freezing rates (mode: freeze)"
                )
                return (True, None)

            if self.config.fallback_mode == "use_last_rtt":
                measured_rtt = self.load_rtt
                self.logger.warning(
                    f"{self.wan_name}: ICMP unavailable - using last RTT={measured_rtt:.1f}ms "
                    f"(mode: use_last_rtt)"
                )
                return (True, measured_rtt)

            self.logger.error(
                f"{self.wan_name}: Unknown fallback_mode: {self.config.fallback_mode}"
            )
            return (False, None)

        # Total connectivity loss confirmed (both ICMP and TCP failed)
        self.logger.warning(f"{self.wan_name}: Total connectivity loss - skipping cycle")
        return (False, None)

    def _check_protocol_correlation(self, ratio: float) -> None:
        """Check ICMP/UDP RTT ratio for protocol deprioritization (IRTT-07).

        Thresholds:
        - ratio > 1.5: ICMP deprioritized (ISP throttling ICMP)
        - ratio < 0.67: UDP deprioritized (ISP throttling UDP)
        - 0.67-1.5: Normal correlation
        """
        deprioritized = ratio > 1.5 or ratio < 0.67
        now = time.monotonic()
        cooldown_elapsed = (
            now - self._irtt_deprioritization_last_transition_ts
            >= self._irtt_deprioritization_log_cooldown_sec
        )

        if deprioritized:
            if ratio > 1.5:
                interpretation = "ICMP deprioritized"
            else:
                interpretation = "UDP deprioritized"

            if not self._irtt_deprioritization_logged:
                if cooldown_elapsed:
                    irtt_result = self._irtt_thread.get_latest() if self._irtt_thread else None
                    udp_rtt = irtt_result.rtt_mean_ms if irtt_result else 0.0
                    self.logger.info(
                        f"{self.wan_name}: Protocol deprioritization detected: "
                        f"ICMP/UDP ratio={ratio:.2f} ({interpretation}), "
                        f"ICMP={self.load_rtt:.1f}ms, UDP={udp_rtt:.1f}ms"
                    )
                else:
                    self.logger.debug(
                        f"{self.wan_name}: Protocol deprioritization transition "
                        f"suppressed by cooldown, ratio={ratio:.2f} ({interpretation})"
                    )
                self._irtt_deprioritization_logged = True
                self._irtt_deprioritization_last_transition_ts = now
            else:
                self.logger.debug(f"{self.wan_name}: Protocol ratio={ratio:.2f}")
        else:
            if self._irtt_deprioritization_logged:
                if cooldown_elapsed:
                    self.logger.info(
                        f"{self.wan_name}: Protocol correlation recovered, ratio={ratio:.2f}"
                    )
                else:
                    self.logger.debug(
                        f"{self.wan_name}: Protocol recovery transition suppressed by "
                        f"cooldown, ratio={ratio:.2f}"
                    )
                self._irtt_deprioritization_logged = False
                self._irtt_deprioritization_last_transition_ts = now

        self._irtt_correlation = ratio

    def _init_fusion_healer(self) -> None:
        """Initialize FusionHealer if both fusion and IRTT are enabled.

        Called by main() after _irtt_thread is assigned. The healer needs
        both ICMP and IRTT signals, so it cannot be created at __init__ time
        when _irtt_thread is still None.
        """
        if not self._fusion_enabled:
            return
        if self._irtt_thread is None:
            return
        healing_cfg = self.config.fusion_config["healing"]
        self._fusion_healer = FusionHealer(
            wan_name=self.wan_name,
            suspend_threshold=healing_cfg["suspend_threshold"],
            recover_threshold=healing_cfg["recover_threshold"],
            suspend_window_sec=healing_cfg["suspend_window_sec"],
            recover_window_sec=healing_cfg["recover_window_sec"],
            grace_period_sec=healing_cfg["grace_period_sec"],
            min_signal_variance=healing_cfg["min_signal_variance"],
            cycle_interval_sec=self.config.irtt_config["cadence_sec"],
            alert_engine=self.alert_engine if isinstance(self.alert_engine, AlertEngine) else None,
            parameter_locks=self._parameter_locks,
        )
        self.logger.info(
            f"{self.wan_name}: FusionHealer initialized "
            f"(suspend<{healing_cfg['suspend_threshold']}, "
            f"recover>{healing_cfg['recover_threshold']})"
        )

    def _compute_fused_rtt(self, filtered_rtt: float) -> float:
        """Compute fused RTT from ICMP filtered_rtt and cached IRTT rtt_mean_ms.

        Returns filtered_rtt unchanged (pass-through) when:
        - IRTT thread is not running (_irtt_thread is None)
        - No IRTT result available (get_latest() returns None)
        - IRTT result is stale (age > 3x cadence)
        - IRTT rtt_mean_ms is zero or negative (total packet loss)

        Returns weighted average when IRTT is fresh and valid.

        Always stores _last_icmp_filtered_rtt and _last_fused_rtt for
        health endpoint observability (FUSE-05).
        """
        self._last_icmp_filtered_rtt = filtered_rtt
        self._last_fused_rtt = None

        if not self._fusion_enabled:
            return filtered_rtt

        if self._irtt_thread is None:
            return filtered_rtt

        irtt_result = self._irtt_thread.get_latest()
        if irtt_result is None:
            return filtered_rtt

        age = time.monotonic() - irtt_result.timestamp
        cadence = self._irtt_thread.cadence_sec
        if age > cadence * 3:
            return filtered_rtt

        irtt_rtt = irtt_result.rtt_mean_ms
        if irtt_rtt <= 0:
            return filtered_rtt

        fused = (
            self._fusion_icmp_weight * filtered_rtt + (1.0 - self._fusion_icmp_weight) * irtt_rtt
        )
        self._last_fused_rtt = fused
        self.logger.debug(
            f"{self.wan_name}: fused_rtt={fused:.1f}ms "
            f"(icmp={filtered_rtt:.1f}ms, irtt={irtt_rtt:.1f}ms, "
            f"icmp_w={self._fusion_icmp_weight})"
        )
        return fused

    def _reload_fusion_config(self) -> None:
        """Re-read fusion config from YAML (triggered by SIGUSR1).

        Reloads both enabled and icmp_weight. Validates with same rules as
        _load_fusion_config(). Logs old->new transitions at WARNING level.
        """
        try:
            import yaml

            with open(self.config.config_file_path) as f:
                fresh_data = yaml.safe_load(f)
        except Exception as e:
            self.logger.error(f"[FUSION] Config reload failed: {e}")
            return

        fusion = fresh_data.get("fusion", {}) if fresh_data else {}
        if not isinstance(fusion, dict):
            fusion = {}

        # Parse enabled (default False)
        new_enabled = fusion.get("enabled", False)
        if not isinstance(new_enabled, bool):
            self.logger.warning(
                f"[FUSION] Reload: fusion.enabled must be bool, got "
                f"{type(new_enabled).__name__}; defaulting to false"
            )
            new_enabled = False
        old_enabled = self._fusion_enabled

        # Parse icmp_weight with same validation as _load_fusion_config
        new_weight = fusion.get("icmp_weight", 0.7)
        if (
            not isinstance(new_weight, (int, float))
            or isinstance(new_weight, bool)
            or new_weight < 0.0
            or new_weight > 1.0
        ):
            self.logger.warning(
                f"[FUSION] Reload: fusion.icmp_weight invalid ({new_weight!r}); defaulting to 0.7"
            )
            new_weight = 0.7
        new_weight = float(new_weight)
        old_weight = self._fusion_icmp_weight

        # Log transitions
        enabled_str = (
            f"enabled={old_enabled}->{new_enabled}"
            if old_enabled != new_enabled
            else f"enabled={new_enabled}"
        )
        weight_str = (
            f"icmp_weight={old_weight}->{new_weight}"
            if old_weight != new_weight
            else f"icmp_weight={new_weight} (unchanged)"
        )
        self.logger.warning(f"[FUSION] Config reload: {enabled_str}, {weight_str}")

        # Respect FusionHealer's runtime state: if the healer has SUSPENDED
        # fusion due to low protocol correlation, don't re-enable just because
        # YAML says enabled=true. The healer's decision is authoritative.
        # Only override if: (a) no healer, (b) healer is ACTIVE, or
        # (c) YAML explicitly disables fusion (operator kill switch).
        if (
            self._fusion_healer is not None
            and new_enabled
            and not old_enabled
            and self._fusion_healer.state == HealState.SUSPENDED
        ):
            self.logger.warning(
                "[FUSION] Config reload: YAML says enabled=true but healer "
                "has SUSPENDED fusion (low correlation). Respecting healer "
                "state — fusion stays disabled. Healer will re-enable when "
                "correlation recovers."
            )
            # Don't change _fusion_enabled — healer is managing it
        else:
            self._fusion_enabled = new_enabled

        self._fusion_icmp_weight = new_weight

        # SIGUSR1 grace period for fusion healer (Phase 119: D-06)
        # Only triggers when fusion was genuinely re-enabled (not blocked above)
        if self._fusion_healer is not None:
            if self._fusion_enabled and not old_enabled:
                if self._fusion_healer.state == HealState.SUSPENDED:
                    self._fusion_healer.start_grace_period()
                    self.logger.warning(
                        f"[FUSION] Operator override: healer paused for "
                        f"{self._fusion_healer._grace_period_sec:.0f}s grace period"
                    )

    def _reload_tuning_config(self) -> None:
        """Re-read tuning config from YAML (triggered by SIGUSR1).

        Reloads enabled state. Validates with same rules as
        _load_tuning_config(). Logs old->new transitions at WARNING level.
        """
        try:
            import yaml

            with open(self.config.config_file_path) as f:
                fresh_data = yaml.safe_load(f)
        except Exception as e:
            self.logger.error(f"[TUNING] Config reload failed: {e}")
            return

        tuning = fresh_data.get("tuning", {}) if fresh_data else {}
        if not isinstance(tuning, dict):
            tuning = {}

        new_enabled = tuning.get("enabled", False)
        if not isinstance(new_enabled, bool):
            self.logger.warning(
                f"[TUNING] Reload: tuning.enabled must be bool, got "
                f"{type(new_enabled).__name__}; defaulting to false"
            )
            new_enabled = False

        old_enabled = self._tuning_enabled

        # Log transition
        if old_enabled != new_enabled:
            self.logger.warning(
                "[TUNING] Config reload: enabled=%s->%s",
                old_enabled,
                new_enabled,
            )
        else:
            self.logger.info(
                "[TUNING] Config reload: enabled=%s (unchanged)",
                new_enabled,
            )

        self._tuning_enabled = new_enabled

        if new_enabled and self._tuning_state is None:
            self._tuning_state = TuningState(
                enabled=True,
                last_run_ts=None,
                recent_adjustments=[],
                parameters={},
            )
        elif not new_enabled:
            self._tuning_state = None
            self._parameter_locks = {}
            self._pending_observation = None

    def _reload_hysteresis_config(self) -> None:
        """Re-read hysteresis config from YAML (triggered by SIGUSR1).

        Reloads dwell_cycles and deadband_ms from continuous_monitoring.thresholds.
        Validates with same bounds as SCHEMA. Logs old->new transitions at WARNING level.
        Applies to both download and upload QueueControllers.
        """
        try:
            import yaml

            with open(self.config.config_file_path) as f:
                fresh_data = yaml.safe_load(f)
        except Exception as e:
            self.logger.error(f"[HYSTERESIS] Config reload failed: {e}")
            return

        cm = fresh_data.get("continuous_monitoring", {}) if fresh_data else {}
        if not isinstance(cm, dict):
            cm = {}
        thresh = cm.get("thresholds", {})
        if not isinstance(thresh, dict):
            thresh = {}

        # Parse dwell_cycles (default 3, bounds [0, 20])
        new_dwell = thresh.get("dwell_cycles", 3)
        if (
            not isinstance(new_dwell, int)
            or isinstance(new_dwell, bool)
            or new_dwell < 0
            or new_dwell > 20
        ):
            self.logger.warning(
                "[HYSTERESIS] Reload: dwell_cycles invalid (%r); keeping current value",
                new_dwell,
            )
            new_dwell = self.download.dwell_cycles

        # Parse deadband_ms (default 3.0, bounds [0.0, 20.0])
        new_deadband = thresh.get("deadband_ms", 3.0)
        if (
            not isinstance(new_deadband, (int, float))
            or isinstance(new_deadband, bool)
            or new_deadband < 0.0
            or new_deadband > 20.0
        ):
            self.logger.warning(
                "[HYSTERESIS] Reload: deadband_ms invalid (%r); keeping current value",
                new_deadband,
            )
            new_deadband = self.download.deadband_ms
        new_deadband = float(new_deadband)

        old_dwell = self.download.dwell_cycles
        old_deadband = self.download.deadband_ms

        # Log transitions
        dwell_str = (
            f"dwell_cycles={old_dwell}->{new_dwell}"
            if old_dwell != new_dwell
            else f"dwell_cycles={new_dwell} (unchanged)"
        )
        deadband_str = (
            f"deadband_ms={old_deadband}->{new_deadband}"
            if old_deadband != new_deadband
            else f"deadband_ms={new_deadband} (unchanged)"
        )
        self.logger.warning(
            "[HYSTERESIS] Config reload: %s, %s", dwell_str, deadband_str
        )

        # Apply to both directions
        self.download.dwell_cycles = new_dwell
        self.download.deadband_ms = new_deadband
        self.upload.dwell_cycles = new_dwell
        self.upload.deadband_ms = new_deadband

    def _reload_cycle_budget_config(self) -> None:
        """Re-read cycle budget warning threshold from YAML (triggered by SIGUSR1).

        Reads continuous_monitoring.warning_threshold_pct from YAML.
        Validates range [1.0, 200.0]. Logs old->new transitions.
        """
        try:
            import yaml

            with open(self.config.config_file_path) as f:
                fresh_data = yaml.safe_load(f)
        except Exception as e:
            self.logger.error(f"[CYCLE_BUDGET] Config reload failed: {e}")
            return

        cm = fresh_data.get("continuous_monitoring", {}) if fresh_data else {}
        if not isinstance(cm, dict):
            cm = {}

        new_threshold = cm.get("warning_threshold_pct", 80.0)
        if (
            not isinstance(new_threshold, (int, float))
            or isinstance(new_threshold, bool)
            or new_threshold < 1.0
            or new_threshold > 200.0
        ):
            self.logger.warning(
                "[CYCLE_BUDGET] Reload: warning_threshold_pct invalid (%r); keeping current value",
                new_threshold,
            )
            return

        new_threshold = float(new_threshold)
        old_threshold = self._warning_threshold_pct

        threshold_str = (
            f"warning_threshold_pct={old_threshold}->{new_threshold}"
            if old_threshold != new_threshold
            else f"warning_threshold_pct={new_threshold} (unchanged)"
        )
        self.logger.warning("[CYCLE_BUDGET] Config reload: %s", threshold_str)
        self._warning_threshold_pct = new_threshold

    def _reload_suppression_alert_config(self) -> None:
        """Re-read suppression alert threshold from YAML (triggered by SIGUSR1).

        Reads continuous_monitoring.thresholds.suppression_alert_threshold from YAML.
        Per D-03: Default 20 suppressions/min, SIGUSR1 hot-reloadable.
        """
        try:
            import yaml

            with open(self.config.config_file_path) as f:
                fresh_data = yaml.safe_load(f)
        except Exception as e:
            self.logger.error(f"[HYSTERESIS] Suppression alert config reload failed: {e}")
            return

        cm = fresh_data.get("continuous_monitoring", {}) if fresh_data else {}
        if not isinstance(cm, dict):
            cm = {}
        thresh = cm.get("thresholds", {})
        if not isinstance(thresh, dict):
            thresh = {}

        new_threshold = thresh.get("suppression_alert_threshold", 20)
        if (
            not isinstance(new_threshold, int)
            or isinstance(new_threshold, bool)
            or new_threshold < 0
            or new_threshold > 1000
        ):
            self.logger.warning(
                "[HYSTERESIS] Reload: suppression_alert_threshold invalid (%r); keeping current value",
                new_threshold,
            )
            return

        old_threshold = self._suppression_alert_threshold
        threshold_str = (
            f"suppression_alert_threshold={old_threshold}->{new_threshold}"
            if old_threshold != new_threshold
            else f"suppression_alert_threshold={new_threshold} (unchanged)"
        )
        self.logger.warning("[HYSTERESIS] Config reload: %s", threshold_str)
        self._suppression_alert_threshold = new_threshold

    def _reload_asymmetry_gate_config(self) -> None:
        """Re-read asymmetry gate config from YAML (triggered by SIGUSR1).

        Reloads continuous_monitoring.upload.asymmetry_gate section.
        Validates with same bounds as _load_asymmetry_gate_config().
        Logs old->new transitions at WARNING level for enabled changes.
        """
        try:
            import yaml

            with open(self.config.config_file_path) as f:
                fresh_data = yaml.safe_load(f)
        except Exception as e:
            self.logger.error(f"[ASYMMETRY_GATE] Config reload failed: {e}")
            return

        cm = fresh_data.get("continuous_monitoring", {}) if fresh_data else {}
        if not isinstance(cm, dict):
            cm = {}
        ul = cm.get("upload", {})
        if not isinstance(ul, dict):
            ul = {}
        gate = ul.get("asymmetry_gate", {})
        if not isinstance(gate, dict):
            gate = {}

        # Parse enabled (default False)
        new_enabled = gate.get("enabled", False)
        if not isinstance(new_enabled, bool):
            self.logger.warning(
                "[ASYMMETRY_GATE] Reload: enabled must be bool, got %s; keeping current",
                type(new_enabled).__name__,
            )
            new_enabled = self._asymmetry_gate_enabled
        old_enabled = self._asymmetry_gate_enabled

        # Parse damping_factor [0.0, 1.0]
        new_damping = gate.get("damping_factor", 0.5)
        if (
            not isinstance(new_damping, (int, float))
            or isinstance(new_damping, bool)
            or new_damping < 0.0
            or new_damping > 1.0
        ):
            self.logger.warning(
                "[ASYMMETRY_GATE] Reload: damping_factor invalid (%r); keeping current",
                new_damping,
            )
            new_damping = self._asymmetry_damping_factor
        new_damping = float(new_damping)

        # Parse min_ratio >= 1.0
        new_ratio = gate.get("min_ratio", 3.0)
        if (
            not isinstance(new_ratio, (int, float))
            or isinstance(new_ratio, bool)
            or new_ratio < 1.0
        ):
            self.logger.warning(
                "[ASYMMETRY_GATE] Reload: min_ratio invalid (%r); keeping current",
                new_ratio,
            )
            new_ratio = self._asymmetry_min_ratio
        new_ratio = float(new_ratio)

        # Parse confirm_readings [1, 10]
        new_confirm = gate.get("confirm_readings", 3)
        if (
            not isinstance(new_confirm, int)
            or isinstance(new_confirm, bool)
            or new_confirm < 1
            or new_confirm > 10
        ):
            self.logger.warning(
                "[ASYMMETRY_GATE] Reload: confirm_readings invalid (%r); keeping current",
                new_confirm,
            )
            new_confirm = self._asymmetry_confirm_readings

        # Parse staleness_sec [5.0, 120.0]
        new_staleness = gate.get("staleness_sec", 30.0)
        if (
            not isinstance(new_staleness, (int, float))
            or isinstance(new_staleness, bool)
            or new_staleness < 5.0
            or new_staleness > 120.0
        ):
            self.logger.warning(
                "[ASYMMETRY_GATE] Reload: staleness_sec invalid (%r); keeping current",
                new_staleness,
            )
            new_staleness = self._asymmetry_staleness_sec
        new_staleness = float(new_staleness)

        # Log transitions
        if old_enabled != new_enabled:
            self.logger.warning(
                "[ASYMMETRY_GATE] Config reload: enabled=%s->%s",
                old_enabled,
                new_enabled,
            )
        else:
            self.logger.info(
                "[ASYMMETRY_GATE] Config reload: enabled=%s (unchanged)",
                new_enabled,
            )

        # Apply
        self._asymmetry_gate_enabled = new_enabled
        self._asymmetry_damping_factor = new_damping
        self._asymmetry_min_ratio = new_ratio
        self._asymmetry_confirm_readings = new_confirm
        self._asymmetry_staleness_sec = new_staleness

        # If gate disabled via reload, reset active state
        if not new_enabled and (self._asymmetry_gate_active or self._asymmetry_downstream_streak > 0):
            self._asymmetry_gate_active = False
            self._asymmetry_downstream_streak = 0

    def _reload_cake_signal_config(self) -> None:
        """Re-read cake_signal config from YAML (triggered by SIGUSR1, CAKE-05)."""
        new_config = self._parse_cake_signal_config()
        old_config = self._dl_cake_signal.config

        # Log transitions
        changes: list[str] = []
        if old_config.enabled != new_config.enabled:
            changes.append(f"enabled={old_config.enabled}->{new_config.enabled}")
        if old_config.drop_rate_enabled != new_config.drop_rate_enabled:
            changes.append(f"drop_rate={old_config.drop_rate_enabled}->{new_config.drop_rate_enabled}")
        if old_config.backlog_enabled != new_config.backlog_enabled:
            changes.append(f"backlog={old_config.backlog_enabled}->{new_config.backlog_enabled}")
        if old_config.peak_delay_enabled != new_config.peak_delay_enabled:
            changes.append(f"peak_delay={old_config.peak_delay_enabled}->{new_config.peak_delay_enabled}")
        if old_config.metrics_enabled != new_config.metrics_enabled:
            changes.append(f"metrics={old_config.metrics_enabled}->{new_config.metrics_enabled}")
        if abs(old_config.time_constant_sec - new_config.time_constant_sec) > 0.001:
            changes.append(f"tc={old_config.time_constant_sec}->{new_config.time_constant_sec}")
        if abs(old_config.drop_rate_threshold - new_config.drop_rate_threshold) > 0.01:
            changes.append(f"drop_threshold={old_config.drop_rate_threshold}->{new_config.drop_rate_threshold}")
        if old_config.backlog_threshold_bytes != new_config.backlog_threshold_bytes:
            changes.append(f"backlog_threshold={old_config.backlog_threshold_bytes}->{new_config.backlog_threshold_bytes}")
        if old_config.refractory_cycles != new_config.refractory_cycles:
            changes.append(f"refractory={old_config.refractory_cycles}->{new_config.refractory_cycles}")
        if abs(old_config.probe_multiplier_factor - new_config.probe_multiplier_factor) > 0.01:
            changes.append(f"probe_multiplier={old_config.probe_multiplier_factor}->{new_config.probe_multiplier_factor}")
        if abs(old_config.probe_ceiling_pct - new_config.probe_ceiling_pct) > 0.01:
            changes.append(f"probe_ceiling_pct={old_config.probe_ceiling_pct}->{new_config.probe_ceiling_pct}")

        change_str = ", ".join(changes) if changes else "(unchanged)"
        self.logger.warning("[CAKE_SIGNAL] Config reload: %s", change_str)

        self._dl_cake_signal.config = new_config
        self._ul_cake_signal.config = new_config

        # Update refractory and detection thresholds (Phase 160)
        self._refractory_cycles = new_config.refractory_cycles

        # Update QueueController thresholds based on enabled state
        if new_config.enabled and self._cake_signal_supported:
            dr_thresh = new_config.drop_rate_threshold if new_config.drop_rate_enabled else 0.0
            bl_thresh = new_config.backlog_threshold_bytes if new_config.backlog_enabled else 0
            self.download._drop_rate_threshold = dr_thresh
            self.upload._drop_rate_threshold = dr_thresh
            self.download._backlog_threshold_bytes = bl_thresh
            self.upload._backlog_threshold_bytes = bl_thresh
            # Phase 161: Update probe recovery params
            self.download._probe_multiplier_factor = new_config.probe_multiplier_factor
            self.download._probe_ceiling_pct = new_config.probe_ceiling_pct
            self.upload._probe_multiplier_factor = new_config.probe_multiplier_factor
            self.upload._probe_ceiling_pct = new_config.probe_ceiling_pct
        else:
            # Disabled: zero thresholds to deactivate detection
            self.download._drop_rate_threshold = 0.0
            self.upload._drop_rate_threshold = 0.0
            self.download._backlog_threshold_bytes = 0
            self.upload._backlog_threshold_bytes = 0
            self.download._probe_multiplier_factor = 1.0
            self.upload._probe_multiplier_factor = 1.0
            self._dl_refractory_remaining = 0
            self._ul_refractory_remaining = 0

    def _record_profiling(
        self,
        rtt_ms: float,
        state_ms: float,
        router_ms: float,
        cycle_start: float,
        *,
        signal_processing_ms: float = 0.0,
        ewma_spike_ms: float = 0.0,
        cake_stats_ms: float = 0.0,
        congestion_assess_ms: float = 0.0,
        irtt_observation_ms: float = 0.0,
        logging_metrics_ms: float = 0.0,
        router_apply_primary_ms: float = 0.0,
        router_apply_pending_ms: float = 0.0,
        router_write_download_ms: float = 0.0,
        router_write_upload_ms: float = 0.0,
        router_write_skipped_ms: float = 0.0,
        router_write_fallback_ms: float = 0.0,
    ) -> None:
        """Record subsystem timing to profiler, emit structured log, and detect overruns.

        Thin wrapper around shared record_cycle_profiling() -- preserves method
        signature for test compatibility. Extended with sub-timer keyword args
        for fine-grained profiling (Phase 131: PERF-01).
        """
        timings: dict[str, float] = {
            "autorate_rtt_measurement": rtt_ms,
            "autorate_state_management": state_ms,
            "autorate_router_communication": router_ms,
            "autorate_signal_processing": signal_processing_ms,
            "autorate_ewma_spike": ewma_spike_ms,
            "autorate_cake_stats": cake_stats_ms,
            "autorate_congestion_assess": congestion_assess_ms,
            "autorate_irtt_observation": irtt_observation_ms,
            "autorate_logging_metrics": logging_metrics_ms,
            "autorate_router_apply_primary": router_apply_primary_ms,
            "autorate_router_apply_pending": router_apply_pending_ms,
            "autorate_router_write_download": router_write_download_ms,
            "autorate_router_write_upload": router_write_upload_ms,
            "autorate_router_write_skipped": router_write_skipped_ms,
            "autorate_router_write_fallback": router_write_fallback_ms,
        }
        self._overrun_count, self._profile_cycle_count = record_cycle_profiling(
            profiler=self._profiler,
            timings=timings,
            cycle_start=cycle_start,
            cycle_interval_ms=self._cycle_interval_ms,
            logger=self.logger,
            daemon_name=f"{self.wan_name}: Cycle",
            label_prefix="autorate",
            overrun_count=self._overrun_count,
            profiling_enabled=self._profiling_enabled,
            profile_cycle_count=self._profile_cycle_count,
        )

        # Check cycle budget alert after recording profiling
        total_ms = sum(timings.values())
        self._check_cycle_budget_alert(total_ms)

        # Check hysteresis window boundary (Phase 136: HYST-01/HYST-02)
        self._check_hysteresis_window()

    def _check_cycle_budget_alert(self, total_ms: float) -> None:
        """Fire cycle_budget_warning if utilization exceeds threshold for N consecutive cycles.

        Per D-07: Reuses AlertEngine with rate limiting. Configurable consecutive threshold.
        """
        utilization = (total_ms / self._cycle_interval_ms) * 100.0
        if utilization >= self._warning_threshold_pct:
            self._budget_warning_streak += 1
            if self._budget_warning_streak >= self._budget_warning_consecutive:
                self.alert_engine.fire(
                    alert_type="cycle_budget_warning",
                    severity="warning",
                    wan_name=self.wan_name,
                    details={
                        "utilization_pct": round(utilization, 1),
                        "threshold_pct": self._warning_threshold_pct,
                        "cycle_time_ms": round(total_ms, 1),
                        "interval_ms": self._cycle_interval_ms,
                        "consecutive_cycles": self._budget_warning_streak,
                    },
                )
        else:
            self._budget_warning_streak = 0

    def _check_hysteresis_window(self) -> tuple[int, int]:
        """Check if 60s hysteresis window has elapsed. Reset, log, and alert if so.

        Returns (dl_count, ul_count) from completed window, or (0, 0) if window not elapsed.
        Per D-06: Only logs at INFO when congestion occurred during the window.
        Per D-04/D-05: Fires hysteresis_suppression alert when count > threshold during congestion.
        Phase 136: HYST-01/HYST-02/HYST-03.
        """
        now = time.time()
        # Use download's window_start_time as canonical (both reset together)
        elapsed = now - self.download._window_start_time
        if elapsed < 60.0:
            return 0, 0

        # Read congestion flags BEFORE reset clears them
        had_congestion = self.download._window_had_congestion or self.upload._window_had_congestion
        dl_count = self.download.reset_window()
        ul_count = self.upload.reset_window()
        total = dl_count + ul_count

        if had_congestion:
            self.logger.info(
                "[HYSTERESIS] %s window: %d suppressions in 60s (DL: %d, UL: %d)",
                self.wan_name, total, dl_count, ul_count,
            )
            # Alert if suppression rate exceeds threshold (Phase 136: HYST-03, per D-04/D-05)
            if total > self._suppression_alert_threshold:
                self.alert_engine.fire(
                    alert_type="hysteresis_suppression",
                    severity="warning",
                    wan_name=self.wan_name,
                    details={
                        "dl_suppressions": dl_count,
                        "ul_suppressions": ul_count,
                        "total_suppressions": total,
                        "threshold": self._suppression_alert_threshold,
                        "window_seconds": 60,
                    },
                )

        return dl_count, ul_count

    def run_cycle(self) -> bool:
        """Main 5-second cycle for this WAN"""
        cycle_start = time.perf_counter()

        with PerfTimer("autorate_rtt_measurement", self.logger) as rtt_timer:
            measured_rtt, rtt_early_return = self._run_rtt_measurement()
        if rtt_early_return is not None:
            self._record_profiling(rtt_timer.elapsed_ms, 0.0, 0.0, cycle_start)
            return rtt_early_return

        assert measured_rtt is not None  # guaranteed by rtt_early_return check above
        with PerfTimer("autorate_state_management", self.logger) as state_timer:
            with PerfTimer("autorate_signal_processing", self.logger) as signal_timer:
                signal_result, fused_rtt = self._run_signal_processing(measured_rtt)
            with PerfTimer("autorate_ewma_spike", self.logger) as ewma_timer:
                self._run_spike_detection()
            with PerfTimer("autorate_cake_stats", self.logger) as cake_stats_timer:
                self._run_cake_stats()
            with PerfTimer("autorate_congestion_assess", self.logger) as congestion_timer:
                dl_zone, dl_rate, dl_tr, ul_zone, ul_rate, ul_tr, delta = (
                    self._run_congestion_assessment()
                )
            with PerfTimer("autorate_irtt_observation", self.logger) as irtt_timer:
                irtt_result = self._run_irtt_observation(signal_result)
            with PerfTimer("autorate_logging_metrics", self.logger) as metrics_timer:
                self._run_logging_metrics(
                    measured_rtt, fused_rtt, dl_zone, ul_zone, dl_rate, ul_rate,
                    delta, dl_tr, ul_tr, irtt_result,
                )

        # Skip router subsystem entirely when rates unchanged (saves netlink round-trip)
        rates_changed = (
            dl_rate != self.last_applied_dl_rate
            or ul_rate != self.last_applied_ul_rate
            or self.pending_rates.has_pending()
            or not self.router_connectivity.is_reachable
        )
        with PerfTimer("autorate_router_communication", self.logger) as router_timer:
            if rates_changed:
                router_failed, router_breakdown = self._run_router_communication(dl_rate, ul_rate)
            else:
                router_failed = False
                router_breakdown = {}
        self._record_profiling(
            rtt_timer.elapsed_ms, state_timer.elapsed_ms, router_timer.elapsed_ms, cycle_start,
            signal_processing_ms=signal_timer.elapsed_ms,
            ewma_spike_ms=ewma_timer.elapsed_ms,
            cake_stats_ms=cake_stats_timer.elapsed_ms,
            congestion_assess_ms=congestion_timer.elapsed_ms,
            irtt_observation_ms=irtt_timer.elapsed_ms,
            logging_metrics_ms=metrics_timer.elapsed_ms,
            router_apply_primary_ms=router_breakdown.get("autorate_router_apply_primary", 0.0),
            router_apply_pending_ms=router_breakdown.get("autorate_router_apply_pending", 0.0),
            router_write_download_ms=router_breakdown.get("autorate_router_write_download", 0.0),
            router_write_upload_ms=router_breakdown.get("autorate_router_write_upload", 0.0),
            router_write_skipped_ms=router_breakdown.get("autorate_router_write_skipped", 0.0),
            router_write_fallback_ms=router_breakdown.get("autorate_router_write_fallback", 0.0),
        )
        if router_failed:
            return False

        with PerfTimer("autorate_post_cycle", self.logger) as post_timer:
            self._run_post_cycle(cycle_start, dl_rate, ul_rate, dl_zone, ul_zone)
        self._profiler.record("autorate_post_cycle", post_timer.elapsed_ms)
        return True

    # =========================================================================
    # run_cycle subsystem helpers (Phase 145-01)
    # =========================================================================

    def _run_rtt_measurement(self) -> tuple[float | None, bool | None]:
        """RTT measurement subsystem: measure, handle ICMP failure, connectivity alerts."""
        measured_rtt = self.measure_rtt()
        raw_measured_rtt = measured_rtt  # Capture before fallback (ALRT-04/05)
        rtt_early_return: bool | None = None

        if measured_rtt is None:
            should_continue, measured_rtt = self.handle_icmp_failure()
            if not should_continue:
                rtt_early_return = False
            elif measured_rtt is None:
                self.save_state()
                rtt_early_return = True
        else:
            if self.icmp_unavailable_cycles > 0:
                self.logger.info(
                    f"{self.wan_name}: ICMP recovered after "
                    f"{self.icmp_unavailable_cycles} cycles"
                )
                self.icmp_unavailable_cycles = 0

        self._check_connectivity_alerts(raw_measured_rtt)
        return measured_rtt, rtt_early_return

    def _run_signal_processing(self, measured_rtt: float) -> tuple[SignalResult, float]:
        """Signal processing subsystem: filter RTT, compute fusion, update EWMAs."""
        signal_result = self.signal_processor.process(
            raw_rtt=measured_rtt,
            load_rtt=self.load_rtt,
            baseline_rtt=self.baseline_rtt,
        )
        self._last_signal_result = signal_result
        fused_rtt = self._compute_fused_rtt(signal_result.filtered_rtt)
        self.load_rtt = (1 - self.alpha_load) * self.load_rtt + self.alpha_load * fused_rtt
        self._update_baseline_if_idle(signal_result.filtered_rtt)
        return signal_result, fused_rtt

    def _run_spike_detection(self) -> None:
        """EWMA spike detection with corroborated burst confirmation.

        A burst is only armed when acceleration is sustained and the current
        RTT delta is above the GREEN threshold. A short candidate window keeps
        the detection alive for a couple of cycles so that the clamp can still
        fire when the RTT delta lags the acceleration spike slightly.
        """
        self._dl_burst_pending = False
        self._dl_burst_reason = None

        if self._dl_burst_candidate_cycles > 0:
            self._dl_burst_candidate_cycles -= 1

        delta_accel = self.load_rtt - self.previous_load_rtt
        current_delta = self.load_rtt - self.baseline_rtt
        burst_window_open = (
            self.download.red_streak == 0
            and self.download.soft_red_streak < self.download.soft_red_required
            and self.download.current_rate >= self.download.floor_yellow_bps
        )
        if not burst_window_open:
            self._dl_burst_candidate_cycles = 0
            self._dl_burst_candidate_accel_ms = None

        if delta_accel > self.accel_threshold:
            self._spike_streak += 1
            if self._spike_streak >= self.accel_confirm and burst_window_open:
                self._dl_burst_candidate_cycles = max(self._dl_burst_candidate_cycles, 2)
                self._dl_burst_candidate_accel_ms = float(delta_accel)
        else:
            self._spike_streak = 0

        if (
            self._dl_burst_candidate_cycles > 0
            and current_delta > self.green_threshold
            and burst_window_open
        ):
            burst_accel_ms = float(self._dl_burst_candidate_accel_ms or delta_accel)
            self._dl_burst_pending = True
            self._dl_burst_reason = (
                f"Burst confirmed from RTT acceleration {burst_accel_ms:.1f}ms "
                f"after {max(self._spike_streak, self.accel_confirm)} consecutive spikes"
            )
            self._dl_burst_trigger_count += 1
            self._dl_burst_last_reason = self._dl_burst_reason
            self._dl_burst_last_accel_ms = burst_accel_ms
            self._dl_burst_last_delta_ms = float(current_delta)
            self._dl_burst_last_trigger_ts = time.monotonic()
            self._dl_burst_candidate_cycles = 0
            self._dl_burst_candidate_accel_ms = None
            self.logger.warning(
                f"{self.wan_name}: RTT spike confirmed; burst confirmed! delta_accel={burst_accel_ms:.1f}ms "
                f"current_delta={current_delta:.1f}ms "
                f"(threshold={self.accel_threshold}ms, {max(self._spike_streak, self.accel_confirm)} consecutive) "
                f"- arming fast clamp"
            )

        self.previous_load_rtt = self.load_rtt

    def _compute_effective_ul_load_rtt(self) -> float:
        """Compute effective upload load_rtt with asymmetry gate attenuation.

        When sustained downstream-only congestion is detected via IRTT, the
        upload delta is attenuated by damping_factor to preserve upload bandwidth
        for latency-sensitive traffic (VoIP, video).

        Gate conditions (all must be true for activation):
        1. Gate enabled in config (ASYM-01)
        2. Valid asymmetry result exists
        3. Result is not stale (< staleness_sec old) (ASYM-03)
        4. Delta below hard_red_threshold (bidirectional override)
        5. Consecutive downstream readings >= confirm_readings (ASYM-02)
        6. Asymmetry ratio >= min_ratio

        Returns:
            Effective load_rtt: attenuated if gate active, raw otherwise.
        """
        # Gate disabled -- passthrough
        if not self._asymmetry_gate_enabled:
            return float(self.load_rtt)

        # No asymmetry data yet -- passthrough
        if self._last_asymmetry_result is None:
            return float(self.load_rtt)

        # Staleness check (ASYM-03): auto-disable if IRTT data too old
        if self._last_asymmetry_result_ts > 0:
            age = time.monotonic() - self._last_asymmetry_result_ts
            if age > self._asymmetry_staleness_sec:
                self._asymmetry_gate_active = False
                self._asymmetry_downstream_streak = 0
                return float(self.load_rtt)

        # Bidirectional override: if delta exceeds hard_red, both directions
        # are genuinely congested -- do not attenuate upload
        delta = float(self.load_rtt) - float(self.baseline_rtt)
        if delta > self.hard_red_threshold:
            self._asymmetry_gate_active = False
            return float(self.load_rtt)

        # Consecutive sample hysteresis (ASYM-02)
        asym = self._last_asymmetry_result
        # On DOCSIS, download-only congestion causes IRTT to report "upstream"
        # asymmetry: the send OWD (client→server) spikes because the downstream
        # request-grant cycle is contended, even though upload itself isn't congested.
        if asym.direction == "upstream" and asym.ratio >= self._asymmetry_min_ratio:
            self._asymmetry_downstream_streak += 1
            if self._asymmetry_downstream_streak >= self._asymmetry_confirm_readings:
                self._asymmetry_gate_active = True
        else:
            self._asymmetry_downstream_streak = 0
            self._asymmetry_gate_active = False

        # Delta attenuation (ASYM-01)
        if self._asymmetry_gate_active:
            return float(self.baseline_rtt) + (delta * self._asymmetry_damping_factor)

        return float(self.load_rtt)

    def _run_cake_stats(self) -> None:
        """Read CAKE qdisc stats and update signal processors (Phase 159).

        Reads from BackgroundCakeStatsThread cache (lock-free, ~0ms) instead
        of inline netlink I/O (7-20ms). Falls back to inline reads if
        background thread not started (e.g., tests or non-netlink transport).
        """
        if not self._cake_signal_supported:
            return
        if not self._dl_cake_signal.config.enabled and not self._ul_cake_signal.config.enabled:
            return

        if self._cake_stats_thread is not None:
            snapshot = self._cake_stats_thread.get_latest()
            if snapshot is not None:
                # Staleness detection: warn at 500ms, fall through to inline at 5s
                age_s = time.monotonic() - snapshot.timestamp
                if age_s > 5.0:
                    self.logger.warning(
                        "%s: CAKE stats cache stale (%.1fs old) — falling back to inline",
                        self.wan_name,
                        age_s,
                    )
                    # Fall through to inline reads below
                else:
                    if age_s > 0.5:
                        self.logger.debug(
                            "%s: CAKE stats cache aging (%.0fms)",
                            self.wan_name,
                            age_s * 1000,
                        )
                    self._dl_cake_snapshot = self._dl_cake_signal.update(snapshot.dl_stats)
                    self._ul_cake_snapshot = self._ul_cake_signal.update(snapshot.ul_stats)
                    return
            # No data yet or stale — fall through to inline

        from wanctl.backends.linux_cake_adapter import LinuxCakeAdapter

        adapter: LinuxCakeAdapter = self.router  # type: ignore[assignment]

        dl_stats = adapter.dl_backend.get_queue_stats("")
        self._dl_cake_snapshot = self._dl_cake_signal.update(dl_stats)

        ul_stats = adapter.ul_backend.get_queue_stats("")
        self._ul_cake_snapshot = self._ul_cake_signal.update(ul_stats)

    def _run_congestion_assessment(
        self,
    ) -> tuple[str, int, str | None, str, int, str | None, float]:
        """Congestion assessment: zone classification, alerts, drift, flapping."""
        # Phase 160: Apply refractory masking BEFORE passing to QueueController
        dl_cake = self._dl_cake_snapshot
        if self._dl_refractory_remaining > 0:
            dl_cake = None  # Mask CAKE signals during refractory
            self._dl_refractory_remaining -= 1

        ul_cake = self._ul_cake_snapshot
        if self._ul_refractory_remaining > 0:
            ul_cake = None
            self._ul_refractory_remaining -= 1

        dl_zone, dl_rate, dl_transition_reason = self.download.adjust_4state(
            self.baseline_rtt,
            self.load_rtt,
            self.green_threshold,
            self.soft_red_threshold,
            self.hard_red_threshold,
            cake_snapshot=dl_cake,
        )
        if self._dl_burst_pending and dl_zone in ("GREEN", "YELLOW"):
            dl_zone = "SOFT_RED"
            dl_rate = self.download.apply_burst_clamp()
            dl_transition_reason = self._dl_burst_reason
        self._dl_zone = dl_zone

        effective_ul_load_rtt = self._compute_effective_ul_load_rtt()
        ul_zone, ul_rate, ul_transition_reason = self.upload.adjust(
            self.baseline_rtt, effective_ul_load_rtt, self.target_delta, self.warn_delta,
            cake_snapshot=ul_cake,
        )
        self._ul_zone = ul_zone

        # Phase 160: Enter refractory if dwell was bypassed this cycle (DETECT-03)
        dl_detection = self.download.get_health_data().get("cake_detection", {})
        ul_detection = self.upload.get_health_data().get("cake_detection", {})
        if dl_detection.get("dwell_bypassed_this_cycle"):
            self._dl_refractory_remaining = self._refractory_cycles
        if ul_detection.get("dwell_bypassed_this_cycle"):
            self._ul_refractory_remaining = self._refractory_cycles

        delta = self.load_rtt - self.baseline_rtt
        self._check_congestion_alerts(dl_zone, ul_zone, dl_rate, ul_rate, delta)
        self._check_baseline_drift()
        self._check_flapping_alerts(dl_zone, ul_zone)
        self._check_latency_regression_alert(dl_zone, ul_zone)
        self._check_burst_churn_alert()

        return dl_zone, dl_rate, dl_transition_reason, ul_zone, ul_rate, ul_transition_reason, delta

    def _run_irtt_observation(
        self, signal_result: SignalResult,
    ) -> IRTTResult | None:
        """IRTT observation: protocol correlation, fusion healer, asymmetry, loss alerts."""
        irtt_result = self._irtt_thread.get_latest() if self._irtt_thread else None
        if irtt_result is not None:
            age = time.monotonic() - irtt_result.timestamp
            cadence = self._irtt_thread.cadence_sec if self._irtt_thread else 10.0
            self.logger.debug(
                f"{self.wan_name}: IRTT RTT={irtt_result.rtt_mean_ms:.1f}ms, "
                f"IPDV={irtt_result.ipdv_mean_ms:.1f}ms, "
                f"loss_up={irtt_result.send_loss:.1f}%, "
                f"loss_down={irtt_result.receive_loss:.1f}%, "
                f"age={age:.1f}s"
            )
            if age <= cadence * 3 and irtt_result.rtt_mean_ms > 0 and self.load_rtt > 0:
                ratio = self.load_rtt / irtt_result.rtt_mean_ms
                self._check_protocol_correlation(ratio)
                self._tick_fusion_healer(signal_result.filtered_rtt, irtt_result)
            elif age > cadence * 3:
                self._irtt_correlation = None
                self._prev_healer_irtt_rtt = None
                self.logger.debug(
                    f"{self.wan_name}: IRTT result stale ({age:.0f}s > {cadence * 3:.0f}s), "
                    f"skipping correlation"
                )

            if self._asymmetry_analyzer is not None:
                asym = self._asymmetry_analyzer.analyze(irtt_result)
                self._last_asymmetry_result = asym
                self._last_asymmetry_result_ts = time.monotonic()

            if isinstance(self.alert_engine, AlertEngine):
                if age <= cadence * 3:
                    self._check_irtt_loss_alerts(irtt_result)
                else:
                    self._irtt_loss_up_start = None
                    self._irtt_loss_up_fired = False
                    self._irtt_loss_down_start = None
                    self._irtt_loss_down_fired = False

        # Reflector quality probing (REFL-03)
        now = time.monotonic()
        probed = self._reflector_scorer.maybe_probe(now, self.rtt_measurement)
        if probed:
            self._persist_reflector_events()
            for probe_host, probe_success in probed:
                self.logger.debug(
                    f"{self.wan_name}: Reflector probe {probe_host}: "
                    f"{'success' if probe_success else 'failed'}"
                )

        return irtt_result

    def _tick_fusion_healer(
        self, filtered_rtt: float, irtt_result: IRTTResult,
    ) -> None:
        """Feed ICMP/IRTT deltas to fusion healer on new IRTT measurements."""
        if self._fusion_healer is None or irtt_result.timestamp == self._prev_irtt_ts:
            return
        self._prev_irtt_ts = irtt_result.timestamp
        icmp_rtt = filtered_rtt
        irtt_rtt = irtt_result.rtt_mean_ms
        icmp_delta = (
            icmp_rtt - self._prev_healer_icmp_rtt
            if self._prev_healer_icmp_rtt is not None
            else 0.0
        )
        irtt_delta = (
            irtt_rtt - self._prev_healer_irtt_rtt
            if self._prev_healer_irtt_rtt is not None
            else 0.0
        )
        self._prev_healer_icmp_rtt = icmp_rtt
        self._prev_healer_irtt_rtt = irtt_rtt

        old_state = self._fusion_healer.state
        new_state = self._fusion_healer.tick(icmp_delta, irtt_delta)

        if new_state != old_state:
            if new_state == HealState.SUSPENDED:
                self._fusion_enabled = False
                self.logger.warning(
                    f"{self.wan_name}: [FUSION HEALER] Suspended fusion "
                    f"(pearson_r={self._fusion_healer.pearson_r:.3f})"
                )
            elif new_state == HealState.ACTIVE:
                self._fusion_enabled = True
                self.logger.warning(
                    f"{self.wan_name}: [FUSION HEALER] Recovered to ACTIVE "
                    f"(pearson_r={self._fusion_healer.pearson_r:.3f})"
                )
            elif new_state == HealState.RECOVERING:
                self.logger.info(
                    f"{self.wan_name}: [FUSION HEALER] Entering RECOVERING "
                    f"(pearson_r={self._fusion_healer.pearson_r:.3f})"
                )

    def _run_logging_metrics(
        self,
        measured_rtt: float,
        fused_rtt: float,
        dl_zone: str,
        ul_zone: str,
        dl_rate: int,
        ul_rate: int,
        delta: float,
        dl_transition_reason: str | None,
        ul_transition_reason: str | None,
        irtt_result: IRTTResult | None,
    ) -> None:
        """Logging and metrics subsystem: cycle log, SQLite history recording."""
        if self.logger.isEnabledFor(logging.DEBUG):
            self.logger.debug(
                "%s: [%s/%s] RTT=%.1fms, load_ewma=%.1fms, baseline=%.1fms, "
                "delta=%.1fms | DL=%.0fM, UL=%.0fM",
                self.wan_name,
                dl_zone,
                ul_zone,
                measured_rtt,
                self.load_rtt,
                self.baseline_rtt,
                delta,
                dl_rate / 1e6,
                ul_rate / 1e6,
            )

        if self._metrics_writer is None:
            return

        ts = int(time.time())
        dl_state = float(STATE_ENCODING.get(dl_zone, 0))
        ul_state = float(STATE_ENCODING.get(ul_zone, 0))
        metrics_batch = [
            (ts, self.wan_name, "wanctl_rtt_ms", measured_rtt, None, "raw"),
            (ts, self.wan_name, "wanctl_rtt_baseline_ms", self.baseline_rtt, None, "raw"),
            (ts, self.wan_name, "wanctl_rtt_load_ewma_ms", self.load_rtt, None, "raw"),
            (ts, self.wan_name, "wanctl_rtt_fused_ms", fused_rtt, None, "raw"),
            (ts, self.wan_name, "wanctl_rtt_delta_ms", delta, None, "raw"),
            (ts, self.wan_name, "wanctl_rate_download_mbps", dl_rate / 1e6, None, "raw"),
            (ts, self.wan_name, "wanctl_rate_upload_mbps", ul_rate / 1e6, None, "raw"),
            (ts, self.wan_name, "wanctl_state", dl_state, self._download_labels, "raw"),
        ]

        if self._last_signal_result is not None:
            sr = self._last_signal_result
            metrics_batch.extend([
                (ts, self.wan_name, "wanctl_signal_jitter_ms", sr.jitter_ms, None, "raw"),
                (ts, self.wan_name, "wanctl_signal_variance_ms2", sr.variance_ms2, None, "raw"),
                (ts, self.wan_name, "wanctl_signal_confidence", sr.confidence, None, "raw"),
                (ts, self.wan_name, "wanctl_signal_outlier_count", float(sr.total_outliers), None, "raw"),
            ])

        if irtt_result is not None and irtt_result.timestamp != self._last_irtt_write_ts:
            metrics_batch.extend([
                (ts, self.wan_name, "wanctl_irtt_rtt_ms", irtt_result.rtt_mean_ms, None, "raw"),
                (ts, self.wan_name, "wanctl_irtt_ipdv_ms", irtt_result.ipdv_mean_ms, None, "raw"),
                (ts, self.wan_name, "wanctl_irtt_loss_up_pct", irtt_result.send_loss, None, "raw"),
                (ts, self.wan_name, "wanctl_irtt_loss_down_pct", irtt_result.receive_loss, None, "raw"),
            ])
            if self._last_asymmetry_result is not None:
                metrics_batch.extend([
                    (ts, self.wan_name, "wanctl_irtt_asymmetry_ratio", self._last_asymmetry_result.ratio, None, "raw"),
                    (ts, self.wan_name, "wanctl_irtt_asymmetry_direction", DIRECTION_ENCODING.get(self._last_asymmetry_result.direction, 0.0), None, "raw"),
                ])
            self._last_irtt_write_ts = irtt_result.timestamp

        # CAKE signal metrics (Phase 159, CAKE-04)
        if self._dl_cake_snapshot is not None and self._dl_cake_signal.config.metrics_enabled:
            snap = self._dl_cake_snapshot
            if not snap.cold_start:
                metrics_batch.extend([
                    (ts, self.wan_name, "wanctl_cake_drop_rate", snap.drop_rate,
                     self._download_labels, "raw"),
                    (ts, self.wan_name, "wanctl_cake_total_drop_rate", snap.total_drop_rate,
                     self._download_labels, "raw"),
                    (ts, self.wan_name, "wanctl_cake_backlog_bytes", float(snap.backlog_bytes),
                     self._download_labels, "raw"),
                    (ts, self.wan_name, "wanctl_cake_peak_delay_us", float(snap.peak_delay_us),
                     self._download_labels, "raw"),
                ])
        if self._ul_cake_snapshot is not None and self._ul_cake_signal.config.metrics_enabled:
            snap = self._ul_cake_snapshot
            if not snap.cold_start:
                metrics_batch.extend([
                    (ts, self.wan_name, "wanctl_cake_drop_rate", snap.drop_rate,
                     self._upload_labels, "raw"),
                    (ts, self.wan_name, "wanctl_cake_total_drop_rate", snap.total_drop_rate,
                     self._upload_labels, "raw"),
                    (ts, self.wan_name, "wanctl_cake_backlog_bytes", float(snap.backlog_bytes),
                     self._upload_labels, "raw"),
                    (ts, self.wan_name, "wanctl_cake_peak_delay_us", float(snap.peak_delay_us),
                     self._upload_labels, "raw"),
                ])

        if self._io_worker is not None:
            self._io_worker.enqueue_batch(metrics_batch)
        else:
            self._metrics_writer.write_metrics_batch(metrics_batch)

        if dl_transition_reason:
            if self._io_worker is not None:
                self._io_worker.enqueue_write(
                    timestamp=ts, wan_name=self.wan_name, metric_name="wanctl_state",
                    value=dl_state,
                    labels={"direction": "download", "reason": dl_transition_reason},
                    granularity="raw",
                )
            else:
                self._metrics_writer.write_metric(
                    timestamp=ts, wan_name=self.wan_name, metric_name="wanctl_state",
                    value=dl_state,
                    labels={"direction": "download", "reason": dl_transition_reason},
                    granularity="raw",
                )
        if ul_transition_reason:
            if self._io_worker is not None:
                self._io_worker.enqueue_write(
                    timestamp=ts, wan_name=self.wan_name, metric_name="wanctl_state",
                    value=ul_state,
                    labels={"direction": "upload", "reason": ul_transition_reason},
                    granularity="raw",
                )
            else:
                self._metrics_writer.write_metric(
                    timestamp=ts, wan_name=self.wan_name, metric_name="wanctl_state",
                    value=ul_state,
                    labels={"direction": "upload", "reason": ul_transition_reason},
                    granularity="raw",
                )

    def _consume_router_write_timings(self) -> dict[str, float]:
        """Return one-cycle write breakdown from Linux CAKE adapter when available."""
        from wanctl.backends.linux_cake_adapter import LinuxCakeAdapter

        if not isinstance(self.router, LinuxCakeAdapter):
            return {}
        return self.router.consume_last_set_limits_stats()

    def _format_cake_snapshot_summary(self, snapshot: Any) -> dict[str, Any] | None:
        """Build a compact CAKE snapshot summary for slow-write diagnostics."""
        if snapshot is None:
            return None
        return {
            "drop_rate": round(snapshot.drop_rate, 1),
            "total_drop_rate": round(snapshot.total_drop_rate, 1),
            "backlog_bytes": snapshot.backlog_bytes,
            "peak_delay_us": snapshot.peak_delay_us,
            "cold_start": snapshot.cold_start,
        }

    def _log_slow_router_apply(
        self,
        elapsed_ms: float,
        dl_rate: int,
        ul_rate: int,
        breakdown: dict[str, float],
    ) -> None:
        """Emit a diagnostic event for unusually slow primary CAKE writes."""
        self.logger.warning(
            "%s: Slow CAKE apply %.1fms (dl_rate=%.1fMbps ul_rate=%.1fMbps breakdown=%s "
            "dl_cake=%s ul_cake=%s)",
            self.wan_name,
            elapsed_ms,
            dl_rate / 1e6,
            ul_rate / 1e6,
            {
                "apply_primary_ms": round(breakdown.get("autorate_router_apply_primary", 0.0), 3),
                "write_download_ms": round(
                    breakdown.get("autorate_router_write_download", 0.0), 3
                ),
                "write_upload_ms": round(
                    breakdown.get("autorate_router_write_upload", 0.0), 3
                ),
                "write_skipped_ms": round(
                    breakdown.get("autorate_router_write_skipped", 0.0), 3
                ),
                "write_fallback_ms": round(
                    breakdown.get("autorate_router_write_fallback", 0.0), 3
                ),
            },
            self._format_cake_snapshot_summary(self._dl_cake_snapshot),
            self._format_cake_snapshot_summary(self._ul_cake_snapshot),
        )

    def _run_router_communication(self, dl_rate: int, ul_rate: int) -> tuple[bool, dict[str, float]]:
        """Router communication subsystem: apply rates with flash wear and rate limiting."""
        breakdown = {
            "autorate_router_apply_primary": 0.0,
            "autorate_router_apply_pending": 0.0,
            "autorate_router_write_download": 0.0,
            "autorate_router_write_upload": 0.0,
            "autorate_router_write_skipped": 0.0,
            "autorate_router_write_fallback": 0.0,
        }
        try:
            with PerfTimer("autorate_router_apply_primary") as primary_timer:
                primary_ok = self.apply_rate_changes_if_needed(dl_rate, ul_rate)
            breakdown["autorate_router_apply_primary"] = primary_timer.elapsed_ms
            for key, value in self._consume_router_write_timings().items():
                breakdown[key] += value
            if primary_timer.elapsed_ms >= SLOW_ROUTER_APPLY_LOG_MS:
                self._log_slow_router_apply(primary_timer.elapsed_ms, dl_rate, ul_rate, breakdown)

            if not primary_ok:
                self.router_connectivity.record_failure(
                    ConnectionError("Failed to apply rate limits to router")
                )
                return True, breakdown  # router_failed = True

            self.router_connectivity.record_success()

            if self.pending_rates.has_pending():
                if self.pending_rates.is_stale():
                    self.logger.info(
                        f"{self.wan_name}: Discarding stale pending rates "
                        f"(queued >{60}s ago)"
                    )
                    self.pending_rates.clear()
                else:
                    pending_dl = self.pending_rates.pending_dl_rate
                    pending_ul = self.pending_rates.pending_ul_rate
                    if pending_dl is not None and pending_ul is not None:
                        self.logger.info(
                            f"{self.wan_name}: Applying pending rates after "
                            f"reconnection "
                            f"(DL={pending_dl / 1e6:.1f}Mbps, "
                            f"UL={pending_ul / 1e6:.1f}Mbps)"
                        )
                        with PerfTimer("autorate_router_apply_pending") as pending_timer:
                            self.apply_rate_changes_if_needed(pending_dl, pending_ul)
                        breakdown["autorate_router_apply_pending"] = pending_timer.elapsed_ms
                        for key, value in self._consume_router_write_timings().items():
                            breakdown[key] += value
        except Exception as e:
            failure_type = self.router_connectivity.record_failure(e)
            failures = self.router_connectivity.consecutive_failures
            if failures == 1 or failures == 3 or failures % 10 == 0:
                self.logger.warning(
                    f"{self.wan_name}: Router communication failed ({failure_type}, "
                    f"{failures} consecutive)"
                )
            return True, breakdown  # router_failed = True

        return False, breakdown  # router_failed = False

    def _run_post_cycle(
        self, cycle_start: float, dl_rate: int, ul_rate: int, dl_zone: str, ul_zone: str,
    ) -> None:
        """Post-cycle subsystem: state persistence and Prometheus metrics recording."""
        self._cycles_since_forced_save += 1
        if self._cycles_since_forced_save >= FORCE_SAVE_INTERVAL_CYCLES:
            self.save_state(force=True)
            self._cycles_since_forced_save = 0
        else:
            self.save_state()

        if self.config.metrics_enabled:
            cycle_duration = time.perf_counter() - cycle_start
            record_autorate_cycle(
                wan_name=self.wan_name,
                dl_rate_mbps=dl_rate / 1e6,
                ul_rate_mbps=ul_rate / 1e6,
                baseline_rtt=self.baseline_rtt,
                load_rtt=self.load_rtt,
                dl_state=dl_zone,
                ul_state=ul_zone,
                cycle_duration=cycle_duration,
                burst_active=self._dl_burst_pending,
                burst_trigger_delta=max(
                    0, self._dl_burst_trigger_count - self._dl_burst_exported_trigger_count
                ),
                burst_last_delta_ms=self._dl_burst_last_delta_ms,
                burst_last_accel_ms=self._dl_burst_last_accel_ms,
            )
            self._dl_burst_exported_trigger_count = self._dl_burst_trigger_count

    def _check_congestion_alerts(
        self,
        dl_zone: str,
        ul_zone: str,
        dl_rate: int,
        ul_rate: int,
        delta: float,
    ) -> None:
        """Check sustained congestion timers and fire alerts (ALRT-01).

        Delegates to per-direction helpers for DL (4-state) and UL (3-state).
        """
        self._check_dl_congestion_alert(dl_zone, dl_rate, ul_rate, delta)
        self._check_ul_congestion_alert(ul_zone, dl_rate, ul_rate, delta)

    def _check_dl_congestion_alert(
        self, dl_zone: str, dl_rate: int, ul_rate: int, delta: float,
    ) -> None:
        """Check download sustained congestion timer (RED/SOFT_RED zones)."""
        now = time.monotonic()
        dl_congested = dl_zone in ("RED", "SOFT_RED")
        if dl_congested:
            self._dl_last_congested_zone = dl_zone
            if self._dl_congestion_start is None:
                self._dl_congestion_start = now
            elif not self._dl_sustained_fired:
                sustained_sec = self.alert_engine.get_rule_param(
                    "congestion_sustained_dl", "sustained_sec", self._sustained_sec
                )
                duration = now - self._dl_congestion_start
                if duration >= sustained_sec:
                    severity = "critical" if dl_zone == "RED" else "warning"
                    fired = self.alert_engine.fire(
                        "congestion_sustained_dl",
                        severity,
                        self.wan_name,
                        {
                            "zone": dl_zone,
                            "dl_rate_mbps": dl_rate / 1e6,
                            "ul_rate_mbps": ul_rate / 1e6,
                            "rtt_ms": self.load_rtt,
                            "delta_ms": delta,
                            "duration_sec": round(duration, 1),
                        },
                    )
                    if fired:
                        self._dl_sustained_fired = True
        else:
            if self._dl_congestion_start is not None:
                if self._dl_sustained_fired:
                    duration = now - self._dl_congestion_start
                    self.alert_engine.fire(
                        "congestion_recovered_dl",
                        "recovery",
                        self.wan_name,
                        {
                            "recovered_from_zone": self._dl_last_congested_zone,
                            "duration_sec": round(duration, 1),
                            "dl_rate_mbps": dl_rate / 1e6,
                            "ul_rate_mbps": ul_rate / 1e6,
                        },
                    )
                self._dl_congestion_start = None
                self._dl_sustained_fired = False

    def _check_ul_congestion_alert(
        self, ul_zone: str, dl_rate: int, ul_rate: int, delta: float,
    ) -> None:
        """Check upload sustained congestion timer (RED zone only)."""
        now = time.monotonic()
        ul_congested = ul_zone == "RED"
        if ul_congested:
            if self._ul_congestion_start is None:
                self._ul_congestion_start = now
            elif not self._ul_sustained_fired:
                sustained_sec = self.alert_engine.get_rule_param(
                    "congestion_sustained_ul", "sustained_sec", self._sustained_sec
                )
                duration = now - self._ul_congestion_start
                if duration >= sustained_sec:
                    fired = self.alert_engine.fire(
                        "congestion_sustained_ul",
                        "critical",
                        self.wan_name,
                        {
                            "zone": ul_zone,
                            "dl_rate_mbps": dl_rate / 1e6,
                            "ul_rate_mbps": ul_rate / 1e6,
                            "rtt_ms": self.load_rtt,
                            "delta_ms": delta,
                            "duration_sec": round(duration, 1),
                        },
                    )
                    if fired:
                        self._ul_sustained_fired = True
        else:
            if self._ul_congestion_start is not None:
                if self._ul_sustained_fired:
                    duration = now - self._ul_congestion_start
                    self.alert_engine.fire(
                        "congestion_recovered_ul",
                        "recovery",
                        self.wan_name,
                        {
                            "recovered_from_zone": "RED",
                            "duration_sec": round(duration, 1),
                            "dl_rate_mbps": dl_rate / 1e6,
                            "ul_rate_mbps": ul_rate / 1e6,
                        },
                    )
                self._ul_congestion_start = None
                self._ul_sustained_fired = False

    def _check_latency_regression_alert(self, dl_zone: str, ul_zone: str) -> None:
        """Alert on sustained elevated RTT delta outside the healthy GREEN state."""
        now = time.monotonic()
        delta = float(self.load_rtt - self.baseline_rtt)
        degraded = delta >= self.green_threshold and (dl_zone != "GREEN" or ul_zone != "GREEN")

        if not degraded:
            self._latency_regression_start = None
            self._latency_regression_active = False
            return

        if self._latency_regression_start is None:
            self._latency_regression_start = now
            return

        if self._latency_regression_active:
            return

        sustained_sec = self.alert_engine.get_rule_param(
            "latency_regression", "sustained_sec", self._sustained_sec
        )
        duration = now - self._latency_regression_start
        if duration < sustained_sec:
            return

        critical = (
            delta >= self.soft_red_threshold
            or dl_zone in ("SOFT_RED", "RED")
            or ul_zone == "RED"
        )
        severity = "critical" if critical else "warning"
        self.alert_engine.fire(
            "latency_regression",
            severity,
            self.wan_name,
            {
                "dl_zone": dl_zone,
                "ul_zone": ul_zone,
                "delta_ms": round(delta, 1),
                "baseline_rtt_ms": round(self.baseline_rtt, 1),
                "load_rtt_ms": round(self.load_rtt, 1),
                "duration_sec": round(duration, 1),
                "warning_delta_ms": round(self.green_threshold, 1),
                "critical_delta_ms": round(self.soft_red_threshold, 1),
            },
        )
        self._latency_regression_active = True

    def _check_burst_churn_alert(self) -> None:
        """Alert on repeated confirmed burst triggers inside a short time window."""
        now = time.monotonic()
        trigger_window_sec = self.alert_engine.get_rule_param(
            "burst_churn_dl", "trigger_window_sec", 300
        )
        trigger_threshold = self.alert_engine.get_rule_param(
            "burst_churn_dl", "trigger_threshold", 3
        )
        severity = self.alert_engine.get_rule_param(
            "burst_churn_dl", "severity", "warning"
        )

        current_count = int(self._dl_burst_trigger_count)
        if current_count < self._burst_last_seen_trigger_count:
            self._burst_transition_timestamps.clear()
        if current_count > self._burst_last_seen_trigger_count:
            self._burst_transition_timestamps.extend(
                now for _ in range(current_count - self._burst_last_seen_trigger_count)
            )
        self._burst_last_seen_trigger_count = current_count

        while (
            self._burst_transition_timestamps
            and now - self._burst_transition_timestamps[0] > trigger_window_sec
        ):
            self._burst_transition_timestamps.popleft()

        if len(self._burst_transition_timestamps) < trigger_threshold:
            return

        self.alert_engine.fire(
            "burst_churn_dl",
            severity,
            self.wan_name,
            {
                "trigger_count": len(self._burst_transition_timestamps),
                "window_sec": int(trigger_window_sec),
                "last_delta_ms": (
                    round(self._dl_burst_last_delta_ms, 1)
                    if self._dl_burst_last_delta_ms is not None
                    else None
                ),
                "last_accel_ms": (
                    round(self._dl_burst_last_accel_ms, 1)
                    if self._dl_burst_last_accel_ms is not None
                    else None
                ),
            },
        )
        self._burst_transition_timestamps.clear()

    def _check_irtt_loss_alerts(self, irtt_result: IRTTResult) -> None:
        """Check sustained IRTT packet loss and fire alerts (ALRT-01, ALRT-02, ALRT-03).

        Called each run_cycle() when IRTT result is fresh (within 3x cadence).
        Tracks how long upstream/downstream loss has exceeded threshold. Fires
        irtt_loss_upstream/downstream after sustained_sec. Fires irtt_loss_recovered
        when loss clears IF sustained alert had fired (recovery gate).

        Args:
            irtt_result: Fresh IRTTResult with send_loss and receive_loss fields.
        """
        now = time.monotonic()

        # --- Upstream loss (send_loss) ---
        up_threshold = self.alert_engine.get_rule_param("irtt_loss_upstream", "loss_threshold_pct", self._irtt_loss_threshold_pct)
        up_sustained = self.alert_engine.get_rule_param("irtt_loss_upstream", "sustained_sec", self._sustained_sec)

        if irtt_result.send_loss >= up_threshold:
            if self._irtt_loss_up_start is None:
                self._irtt_loss_up_start = now
            elif not self._irtt_loss_up_fired:
                duration = now - self._irtt_loss_up_start
                if duration >= up_sustained:
                    fired = self.alert_engine.fire(
                        "irtt_loss_upstream",
                        "warning",
                        self.wan_name,
                        {
                            "loss_pct": irtt_result.send_loss,
                            "direction": "upstream",
                            "duration_sec": round(duration, 1),
                        },
                    )
                    if fired:
                        self._irtt_loss_up_fired = True
        else:
            if self._irtt_loss_up_start is not None:
                if self._irtt_loss_up_fired:
                    duration = now - self._irtt_loss_up_start
                    self.alert_engine.fire(
                        "irtt_loss_recovered",
                        "recovery",
                        self.wan_name,
                        {
                            "direction": "upstream",
                            "duration_sec": round(duration, 1),
                            "loss_pct": irtt_result.send_loss,
                        },
                    )
                self._irtt_loss_up_start = None
                self._irtt_loss_up_fired = False

        # --- Downstream loss (receive_loss) ---
        down_threshold = self.alert_engine.get_rule_param("irtt_loss_downstream", "loss_threshold_pct", self._irtt_loss_threshold_pct)
        down_sustained = self.alert_engine.get_rule_param("irtt_loss_downstream", "sustained_sec", self._sustained_sec)

        if irtt_result.receive_loss >= down_threshold:
            if self._irtt_loss_down_start is None:
                self._irtt_loss_down_start = now
            elif not self._irtt_loss_down_fired:
                duration = now - self._irtt_loss_down_start
                if duration >= down_sustained:
                    fired = self.alert_engine.fire(
                        "irtt_loss_downstream",
                        "warning",
                        self.wan_name,
                        {
                            "loss_pct": irtt_result.receive_loss,
                            "direction": "downstream",
                            "duration_sec": round(duration, 1),
                        },
                    )
                    if fired:
                        self._irtt_loss_down_fired = True
        else:
            if self._irtt_loss_down_start is not None:
                if self._irtt_loss_down_fired:
                    duration = now - self._irtt_loss_down_start
                    self.alert_engine.fire(
                        "irtt_loss_recovered",
                        "recovery",
                        self.wan_name,
                        {
                            "direction": "downstream",
                            "duration_sec": round(duration, 1),
                            "loss_pct": irtt_result.receive_loss,
                        },
                    )
                self._irtt_loss_down_start = None
                self._irtt_loss_down_fired = False

    def _check_connectivity_alerts(self, measured_rtt: float | None) -> None:
        """Check WAN connectivity and fire offline/recovery alerts (ALRT-04, ALRT-05).

        Called each run_cycle() with the raw measured RTT (before fallback processing).
        Tracks how long all ICMP targets have been unreachable. Fires wan_offline
        after sustained_sec threshold (default 30s). Fires wan_recovered when ICMP
        returns IF wan_offline had fired (recovery gate).

        Args:
            measured_rtt: Raw RTT from measure_rtt(), None if all targets unreachable.
        """
        now = time.monotonic()

        if measured_rtt is None:
            # All ICMP targets unreachable
            if self._connectivity_offline_start is None:
                self._connectivity_offline_start = now
            elif not self._wan_offline_fired:
                # Check per-rule sustained_sec override
                sustained_sec = self.alert_engine.get_rule_param(
                    "wan_offline", "sustained_sec", self._sustained_sec
                )
                duration = now - self._connectivity_offline_start
                if duration >= sustained_sec:
                    fired = self.alert_engine.fire(
                        "wan_offline",
                        "critical",
                        self.wan_name,
                        {
                            "duration_sec": round(duration, 1),
                            "ping_targets": len(self.ping_hosts),
                            "last_known_rtt": round(self.load_rtt, 1),
                        },
                    )
                    if fired:
                        self._wan_offline_fired = True
        else:
            # ICMP recovered
            if self._connectivity_offline_start is not None:
                if self._wan_offline_fired:
                    duration = now - self._connectivity_offline_start
                    self.alert_engine.fire(
                        "wan_recovered",
                        "recovery",
                        self.wan_name,
                        {
                            "outage_duration_sec": round(duration, 1),
                            "current_rtt": round(measured_rtt, 1),
                            "ping_targets": len(self.ping_hosts),
                        },
                    )
                self._connectivity_offline_start = None
                self._wan_offline_fired = False

    def _check_baseline_drift(self) -> None:
        """Check if baseline RTT has drifted beyond threshold from initial (ALRT-06).

        Compares the EWMA baseline_rtt against the config-set baseline_rtt_initial.
        Fires baseline_drift alert when absolute percentage drift exceeds threshold.
        Cooldown suppression in AlertEngine handles re-fire naturally.

        Uses absolute percentage so both upward drift (ISP degradation) and
        downward drift (routing change) are detected.
        """
        reference = self.config.baseline_rtt_initial
        if reference <= 0:
            return

        drift_pct = abs(self.baseline_rtt - reference) / reference * 100.0

        # Per-rule threshold override (default 50%)
        threshold = self.alert_engine.get_rule_param(
            "baseline_drift", "drift_threshold_pct", 50
        )

        if drift_pct >= threshold:
            self.alert_engine.fire(
                "baseline_drift",
                "warning",
                self.wan_name,
                {
                    "current_baseline_ms": round(self.baseline_rtt, 2),
                    "reference_baseline_ms": round(reference, 2),
                    "drift_percent": round(drift_pct, 1),
                },
            )

    def _check_flapping_alerts(self, dl_zone: str, ul_zone: str) -> None:
        """Check for rapid congestion zone flapping and fire alerts (ALRT-07).

        Tracks zone transitions per direction in a sliding time window.
        Fires flapping_dl/flapping_ul when transitions exceed configured
        threshold within the window. DL and UL are tracked independently.

        Args:
            dl_zone: Current download zone (GREEN/YELLOW/SOFT_RED/RED).
            ul_zone: Current upload zone (GREEN/YELLOW/RED).
        """
        now = time.monotonic()

        # Shared config rule for both DL and UL flapping
        flap_window = self.alert_engine.get_rule_param("congestion_flapping", "flap_window_sec", 120)
        flap_threshold = self.alert_engine.get_rule_param("congestion_flapping", "flap_threshold", 30)
        flap_severity = self.alert_engine.get_rule_param("congestion_flapping", "severity", "warning")

        # Dwell filter: only count transitions where departing zone was held
        # long enough to be a real state, not a single-cycle blip.
        min_hold_sec = self.alert_engine.get_rule_param("congestion_flapping", "min_hold_sec", 1.0)
        if min_hold_sec <= 0:
            min_hold_cycles = 0
        else:
            min_hold_cycles = max(1, int(min_hold_sec / CYCLE_INTERVAL_SECONDS))

        # --- Download flapping ---
        if self._dl_prev_zone is not None and dl_zone != self._dl_prev_zone:
            # Only count transition if departing zone was held long enough
            if self._dl_zone_hold >= min_hold_cycles:
                self._dl_zone_transitions.append(now)
            self._dl_zone_hold = 0
        else:
            self._dl_zone_hold += 1
        self._dl_prev_zone = dl_zone

        # Prune old transitions outside window
        while self._dl_zone_transitions and (now - self._dl_zone_transitions[0] > flap_window):
            self._dl_zone_transitions.popleft()

        if len(self._dl_zone_transitions) >= flap_threshold:
            self.alert_engine.fire(
                "flapping_dl",
                flap_severity,
                self.wan_name,
                {
                    "transition_count": len(self._dl_zone_transitions),
                    "window_sec": flap_window,
                    "current_zone": dl_zone,
                },
                rule_key="congestion_flapping",
            )
            self._dl_zone_transitions.clear()

        # --- Upload flapping ---
        if self._ul_prev_zone is not None and ul_zone != self._ul_prev_zone:
            # Only count transition if departing zone was held long enough
            if self._ul_zone_hold >= min_hold_cycles:
                self._ul_zone_transitions.append(now)
            self._ul_zone_hold = 0
        else:
            self._ul_zone_hold += 1
        self._ul_prev_zone = ul_zone

        # Prune old transitions outside window
        while self._ul_zone_transitions and (now - self._ul_zone_transitions[0] > flap_window):
            self._ul_zone_transitions.popleft()

        if len(self._ul_zone_transitions) >= flap_threshold:
            self.alert_engine.fire(
                "flapping_ul",
                flap_severity,
                self.wan_name,
                {
                    "transition_count": len(self._ul_zone_transitions),
                    "window_sec": flap_window,
                    "current_zone": ul_zone,
                },
                rule_key="congestion_flapping",
            )
            self._ul_zone_transitions.clear()

    # =========================================================================
    # PUBLIC FACADE API
    # =========================================================================

    def reload(self) -> None:
        """Reload all hot-reloadable config sections (SIGUSR1 handler)."""
        self._reload_fusion_config()
        self._reload_tuning_config()
        self._reload_hysteresis_config()
        self._reload_cycle_budget_config()
        self._reload_suppression_alert_config()
        self._reload_asymmetry_gate_config()
        self._reload_cake_signal_config()  # Phase 159, CAKE-05

    def shutdown_threads(self) -> None:
        """Stop background threads (RTT thread and thread pool)."""
        if self._rtt_thread is not None:
            self._rtt_thread.stop()
        if self._rtt_pool is not None:
            self._rtt_pool.shutdown(wait=True, cancel_futures=True)

    def set_irtt_thread(self, thread: "IRTTThread") -> None:
        """Set the IRTT measurement thread reference."""
        self._irtt_thread = thread

    def enable_profiling(self, enabled: bool = True) -> None:
        """Enable or disable cycle profiling."""
        self._profiling_enabled = enabled

    def init_fusion_healer(self) -> None:
        """Initialize fusion healer (public wrapper for _init_fusion_healer)."""
        self._init_fusion_healer()

    def get_pending_observation(self) -> Any:
        """Get the current pending tuning observation."""
        return self._pending_observation

    def set_pending_observation(self, observation: Any) -> None:
        """Set a pending tuning observation."""
        self._pending_observation = observation

    def clear_pending_observation(self) -> None:
        """Clear the pending tuning observation."""
        self._pending_observation = None

    def get_parameter_locks(self) -> dict[str, float]:
        """Get the current parameter locks dict (reference, not copy)."""
        return self._parameter_locks

    @property
    def tuning_layer_index(self) -> int:
        """Current tuning layer rotation index."""
        return self._tuning_layer_index

    @tuning_layer_index.setter
    def tuning_layer_index(self, value: int) -> None:
        self._tuning_layer_index = value

    @property
    def is_tuning_enabled(self) -> bool:
        """Whether adaptive tuning is enabled."""
        return self._tuning_enabled

    def get_current_params(self) -> dict[str, float]:
        """Return current tunable parameter values.

        Eliminates two-level deep private access like
        wc.signal_processor._sigma_threshold.
        """
        params: dict[str, float] = {
            "hampel_sigma_threshold": self.signal_processor.sigma_threshold,
            "hampel_window_size": float(self.signal_processor.window_size),
        }
        if self._reflector_scorer is not None:
            params["reflector_min_score"] = self._reflector_scorer.min_score
        params["fusion_icmp_weight"] = self._fusion_icmp_weight
        return params

    def set_io_worker(self, worker: DeferredIOWorker) -> None:
        """Set the deferred I/O worker for background metrics writes."""
        self._io_worker = worker

    def get_metrics_writer(self) -> MetricsWriter | None:
        """Get the metrics writer instance."""
        return self._metrics_writer

    def get_health_data(self) -> dict[str, Any]:
        """Return all health-relevant data for the health endpoint.

        Provides raw values. health_check.py handles presentation formatting.
        Replaces ~25 cross-module private attribute accesses.
        """
        storage_snapshot = get_storage_metrics_snapshot("autorate")
        if self._io_worker is not None:
            storage_snapshot["pending_writes"] = self._io_worker.pending_count
        storage_files = get_storage_file_snapshot(self._storage_db_path)
        rss_bytes, swap_bytes = read_process_memory_status()
        return {
            "cycle_budget": {
                "profiler": self._profiler,
                "overrun_count": self._overrun_count,
                "cycle_interval_ms": self._cycle_interval_ms,
                "warning_threshold_pct": self._warning_threshold_pct,
            },
            "signal_result": self._last_signal_result,
            "irtt": {
                "thread": self._irtt_thread,
                "correlation": self._irtt_correlation,
                "last_asymmetry_result": self._last_asymmetry_result,
            },
            "reflector": {
                "scorer": self._reflector_scorer,
            },
            "fusion": {
                "enabled": self._fusion_enabled,
                "icmp_filtered_rtt": self._last_icmp_filtered_rtt,
                "fused_rtt": self._last_fused_rtt,
                "icmp_weight": self._fusion_icmp_weight,
                "healer": self._fusion_healer,
            },
            "measurement": {
                "raw_rtt_ms": self._last_raw_rtt,
                "staleness_sec": (
                    time.monotonic() - self._last_raw_rtt_ts
                    if self._last_raw_rtt_ts is not None
                    else None
                ),
                "active_reflector_hosts": list(self._last_active_reflector_hosts),
                "successful_reflector_hosts": list(self._last_successful_reflector_hosts),
                "cadence_sec": (
                    self._cycle_interval_ms / 1000.0
                    if self._cycle_interval_ms and self._cycle_interval_ms > 0
                    else None
                ),
            },
            "tuning": {
                "enabled": self._tuning_enabled,
                "state": self._tuning_state,
                "parameter_locks": self._parameter_locks,
                "pending_observation": self._pending_observation,
            },
            "suppression_alert": {
                "threshold": self._suppression_alert_threshold,
            },
            "asymmetry_gate": {
                "enabled": self._asymmetry_gate_enabled,
                "active": self._asymmetry_gate_active,
                "downstream_streak": self._asymmetry_downstream_streak,
                "damping_factor": self._asymmetry_damping_factor,
                "last_result_age_sec": (
                    time.monotonic() - self._last_asymmetry_result_ts
                    if self._last_asymmetry_result_ts > 0
                    else None
                ),
            },
            "cake_signal": {
                "enabled": self._dl_cake_signal.config.enabled,
                "supported": self._cake_signal_supported,
                "download": self._dl_cake_snapshot,
                "upload": self._ul_cake_snapshot,
                "detection": {
                    "dl_refractory_remaining": self._dl_refractory_remaining,
                    "ul_refractory_remaining": self._ul_refractory_remaining,
                    "refractory_cycles": self._refractory_cycles,
                    "dl_dwell_bypassed_count": self.download.get_health_data().get("cake_detection", {}).get("dwell_bypassed_count", 0),
                    "ul_dwell_bypassed_count": self.upload.get_health_data().get("cake_detection", {}).get("dwell_bypassed_count", 0),
                    "dl_backlog_suppressed_count": self.download.get_health_data().get("cake_detection", {}).get("backlog_suppressed_count", 0),
                    "ul_backlog_suppressed_count": self.upload.get_health_data().get("cake_detection", {}).get("backlog_suppressed_count", 0),
                    "dl_recovery_probe": self.download.get_health_data().get("recovery_probe", {}),
                    "ul_recovery_probe": self.upload.get_health_data().get("recovery_probe", {}),
                },
                "burst": {
                    "active": self._dl_burst_pending,
                    "trigger_count": self._dl_burst_trigger_count,
                    "last_reason": self._dl_burst_last_reason,
                    "last_accel_ms": self._dl_burst_last_accel_ms,
                    "last_delta_ms": self._dl_burst_last_delta_ms,
                    "last_trigger_ago_sec": (
                        round(time.monotonic() - self._dl_burst_last_trigger_ts, 1)
                        if self._dl_burst_last_trigger_ts is not None
                        else None
                    ),
                },
            },
            "runtime": {
                "process": "autorate",
                "rss_bytes": rss_bytes,
                "swap_bytes": swap_bytes,
            },
            "storage": storage_snapshot,
            "storage_files": storage_files,
        }

    @handle_errors(error_msg="{self.wan_name}: Could not load state: {exception}")
    def load_state(self) -> None:
        """Load persisted hysteresis state from disk."""
        state = self.state_manager.load()

        if state is not None:
            # Restore download controller state
            if "download" in state:
                dl = state["download"]
                self.download.green_streak = dl.get("green_streak", 0)
                self.download.soft_red_streak = dl.get("soft_red_streak", 0)
                self.download.red_streak = dl.get("red_streak", 0)
                self.download.current_rate = dl.get("current_rate", self.download.ceiling_bps)

            # Restore upload controller state
            if "upload" in state:
                ul = state["upload"]
                self.upload.green_streak = ul.get("green_streak", 0)
                self.upload.soft_red_streak = ul.get("soft_red_streak", 0)
                self.upload.red_streak = ul.get("red_streak", 0)
                self.upload.current_rate = ul.get("current_rate", self.upload.ceiling_bps)

            # Restore EWMA state
            if "ewma" in state:
                ewma = state["ewma"]
                self.baseline_rtt = ewma.get("baseline_rtt", self.baseline_rtt)
                self.load_rtt = ewma.get("load_rtt", self.load_rtt)

            # Restore last applied rates (flash wear protection)
            if "last_applied" in state:
                applied = state["last_applied"]
                self.last_applied_dl_rate = applied.get("dl_rate")
                self.last_applied_ul_rate = applied.get("ul_rate")

    def _encode_state(self, state: str) -> int:
        """Encode congestion state to numeric value for storage.

        Matches STORED_METRICS schema: 0=GREEN, 1=YELLOW, 2=SOFT_RED, 3=RED
        """
        return STATE_ENCODING.get(state, 0)

    @handle_errors(error_msg="{self.wan_name}: Could not save state: {exception}")
    def save_state(self, force: bool = False) -> None:
        """Save hysteresis state to disk for persistence across restarts.

        Args:
            force: If True, bypass dirty tracking and always write
        """
        self.state_manager.save(
            download=self.state_manager.build_controller_state(
                self.download.green_streak,
                self.download.soft_red_streak,
                self.download.red_streak,
                self.download.current_rate,
            ),
            upload=self.state_manager.build_controller_state(
                self.upload.green_streak,
                self.upload.soft_red_streak,
                self.upload.red_streak,
                self.upload.current_rate,
            ),
            ewma={"baseline_rtt": self.baseline_rtt, "load_rtt": self.load_rtt},
            last_applied={
                "dl_rate": self.last_applied_dl_rate,
                "ul_rate": self.last_applied_ul_rate,
            },
            congestion={"dl_state": self._dl_zone, "ul_state": self._ul_zone},
            force=force,
        )
