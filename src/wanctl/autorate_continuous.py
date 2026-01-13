#!/usr/bin/env python3
"""
Continuous CAKE Auto-Tuning System
3-zone controller with EWMA smoothing for responsive congestion control
Expert-tuned for VDSL2, Cable, and Fiber connections

Runs as a persistent daemon with internal 2-second control loop.
"""
import argparse
import atexit
import concurrent.futures
import datetime
import logging
import socket
import statistics
import sys
import time
import traceback
from pathlib import Path

from wanctl.config_base import BaseConfig
from wanctl.config_validation_utils import (
    validate_bandwidth_order,
    validate_threshold_order,
)
from wanctl.error_handling import handle_errors
from wanctl.health_check import start_health_server, update_health_status
from wanctl.lock_utils import validate_and_acquire_lock
from wanctl.lockfile import LockAcquisitionError, LockFile
from wanctl.logging_utils import setup_logging
from wanctl.metrics import (
    record_autorate_cycle,
    record_ping_failure,
    record_rate_limit_event,
    record_router_update,
    start_metrics_server,
)
from wanctl.rate_limiter import RateLimiter
from wanctl.rate_utils import enforce_rate_bounds
from wanctl.router_client import get_router_client
from wanctl.rtt_measurement import RTTAggregationStrategy, RTTMeasurement
from wanctl.signal_utils import (
    get_shutdown_event,
    is_shutdown_requested,
    register_signal_handlers,
)
from wanctl.state_utils import atomic_write_json, safe_json_load_file
from wanctl.systemd_utils import (
    is_systemd_available,
    notify_degraded,
    notify_watchdog,
)
from wanctl.timeouts import DEFAULT_AUTORATE_PING_TIMEOUT, DEFAULT_AUTORATE_SSH_TIMEOUT

# =============================================================================
# CONSTANTS
# =============================================================================

# Baseline RTT update threshold - only update baseline when delta is minimal
# This prevents baseline drift under load (architectural invariant)
DEFAULT_BASELINE_UPDATE_THRESHOLD_MS = 3.0

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
# With 0.05-second cycles and 0.85 factor_down, recovery from 920M to floor takes ~80 cycles = 4 seconds
CYCLE_INTERVAL_SECONDS = 0.05

# Default bloat thresholds (milliseconds)
DEFAULT_HARD_RED_BLOAT_MS = 80  # SOFT_RED -> RED transition threshold

# Rate limiter defaults (protects router API during instability)
DEFAULT_RATE_LIMIT_MAX_CHANGES = 10  # Max changes per window
DEFAULT_RATE_LIMIT_WINDOW_SECONDS = 60  # Window duration

# Conversion factors
MBPS_TO_BPS = 1_000_000


# =============================================================================
# CONFIGURATION
# =============================================================================

class Config(BaseConfig):
    """Configuration container loaded from YAML"""

    # Schema for autorate_continuous configuration validation
    SCHEMA = [
        # Queue names
        {"path": "queues.download", "type": str, "required": True},
        {"path": "queues.upload", "type": str, "required": True},

        # Continuous monitoring - required structure
        {"path": "continuous_monitoring.enabled", "type": bool, "required": True},
        {"path": "continuous_monitoring.baseline_rtt_initial", "type": (int, float),
         "required": True, "min": 1, "max": 500},

        # Download parameters - ceiling is required, floors validated in _load_specific_fields
        {"path": "continuous_monitoring.download.ceiling_mbps", "type": (int, float),
         "required": True, "min": 1, "max": 10000},
        {"path": "continuous_monitoring.download.step_up_mbps", "type": (int, float),
         "required": True, "min": 0.1, "max": 100},
        {"path": "continuous_monitoring.download.factor_down", "type": float,
         "required": True, "min": 0.1, "max": 1.0},

        # Upload parameters
        {"path": "continuous_monitoring.upload.ceiling_mbps", "type": (int, float),
         "required": True, "min": 1, "max": 1000},
        {"path": "continuous_monitoring.upload.step_up_mbps", "type": (int, float),
         "required": True, "min": 0.1, "max": 100},
        {"path": "continuous_monitoring.upload.factor_down", "type": float,
         "required": True, "min": 0.1, "max": 1.0},

        # Thresholds
        {"path": "continuous_monitoring.thresholds.target_bloat_ms", "type": (int, float),
         "required": True, "min": 1, "max": 100},
        {"path": "continuous_monitoring.thresholds.warn_bloat_ms", "type": (int, float),
         "required": True, "min": 1, "max": 200},
        {"path": "continuous_monitoring.thresholds.alpha_baseline", "type": float,
         "required": True, "min": 0.0001, "max": 1.0},
        {"path": "continuous_monitoring.thresholds.alpha_load", "type": float,
         "required": True, "min": 0.001, "max": 1.0},

        # Ping hosts
        {"path": "continuous_monitoring.ping_hosts", "type": list, "required": True},

        # Logging
        {"path": "logging.main_log", "type": str, "required": True},
        {"path": "logging.debug_log", "type": str, "required": True},

        # Lock file
        {"path": "lock_file", "type": str, "required": True},
        {"path": "lock_timeout", "type": int, "required": True, "min": 1, "max": 3600},
    ]

    def _load_specific_fields(self) -> None:
        """Load autorate-specific configuration fields"""
        # Queues (validated to prevent command injection)
        self.queue_down = self.validate_identifier(
            self.data['queues']['download'], 'queues.download'
        )
        self.queue_up = self.validate_identifier(
            self.data['queues']['upload'], 'queues.upload'
        )

        # Continuous monitoring parameters
        cm = self.data['continuous_monitoring']
        self.enabled = cm['enabled']
        self.baseline_rtt_initial = cm['baseline_rtt_initial']

        # Download parameters (STATE-BASED FLOORS - Phase 2A: 4-state)
        dl = cm['download']
        # Support both legacy (single floor) and v2/v3 (state-based floors)
        if 'floor_green_mbps' in dl:
            self.download_floor_green = dl['floor_green_mbps'] * MBPS_TO_BPS
            self.download_floor_yellow = dl['floor_yellow_mbps'] * MBPS_TO_BPS
            self.download_floor_soft_red = dl.get('floor_soft_red_mbps', dl['floor_yellow_mbps']) * MBPS_TO_BPS  # Phase 2A
            self.download_floor_red = dl['floor_red_mbps'] * MBPS_TO_BPS
        else:
            # Legacy: use single floor for all states
            floor = dl['floor_mbps'] * MBPS_TO_BPS
            self.download_floor_green = floor
            self.download_floor_yellow = floor
            self.download_floor_soft_red = floor  # Phase 2A
            self.download_floor_red = floor
        self.download_ceiling = dl['ceiling_mbps'] * MBPS_TO_BPS
        self.download_step_up = dl['step_up_mbps'] * MBPS_TO_BPS
        self.download_factor_down = dl['factor_down']

        # Validate download floor ordering: red <= soft_red <= yellow <= green <= ceiling
        validate_bandwidth_order(
            name="download",
            floor_red=self.download_floor_red,
            floor_soft_red=self.download_floor_soft_red,
            floor_yellow=self.download_floor_yellow,
            floor_green=self.download_floor_green,
            ceiling=self.download_ceiling,
            convert_to_mbps=True,
            logger=logging.getLogger(__name__),
        )

        # Upload parameters (STATE-BASED FLOORS)
        ul = cm['upload']
        # Support both legacy (single floor) and v2 (state-based floors)
        if 'floor_green_mbps' in ul:
            self.upload_floor_green = ul['floor_green_mbps'] * MBPS_TO_BPS
            self.upload_floor_yellow = ul['floor_yellow_mbps'] * MBPS_TO_BPS
            self.upload_floor_red = ul['floor_red_mbps'] * MBPS_TO_BPS
        else:
            # Legacy: use single floor for all states
            floor = ul['floor_mbps'] * MBPS_TO_BPS
            self.upload_floor_green = floor
            self.upload_floor_yellow = floor
            self.upload_floor_red = floor
        self.upload_ceiling = ul['ceiling_mbps'] * MBPS_TO_BPS
        self.upload_step_up = ul['step_up_mbps'] * MBPS_TO_BPS
        self.upload_factor_down = ul['factor_down']

        # Validate upload floor ordering: red <= yellow <= green <= ceiling
        validate_bandwidth_order(
            name="upload",
            floor_red=self.upload_floor_red,
            floor_yellow=self.upload_floor_yellow,
            floor_green=self.upload_floor_green,
            ceiling=self.upload_ceiling,
            convert_to_mbps=True,
            logger=logging.getLogger(__name__),
        )

        # Thresholds
        thresh = cm['thresholds']
        self.target_bloat_ms = thresh['target_bloat_ms']          # GREEN → YELLOW (15ms)
        self.warn_bloat_ms = thresh['warn_bloat_ms']              # YELLOW → SOFT_RED (45ms)
        self.hard_red_bloat_ms = thresh.get('hard_red_bloat_ms', DEFAULT_HARD_RED_BLOAT_MS)
        self.alpha_baseline = thresh['alpha_baseline']
        self.alpha_load = thresh['alpha_load']
        # Baseline update threshold - only update baseline when delta is below this value
        # Prevents baseline drift under load (architectural invariant)
        self.baseline_update_threshold_ms = thresh.get(
            'baseline_update_threshold_ms', DEFAULT_BASELINE_UPDATE_THRESHOLD_MS
        )

        # Validate threshold ordering: target < warn < hard_red
        # This ensures state transitions are logically correct
        validate_threshold_order(
            target_bloat_ms=self.target_bloat_ms,
            warn_bloat_ms=self.warn_bloat_ms,
            hard_red_bloat_ms=self.hard_red_bloat_ms,
            logger=logging.getLogger(__name__),
        )

        # Ping configuration
        self.ping_hosts = cm['ping_hosts']
        self.use_median_of_three = cm.get('use_median_of_three', False)

        # Fallback connectivity checks (optional, with sensible defaults)
        fallback = cm.get('fallback_checks', {})
        self.fallback_enabled = fallback.get('enabled', True)  # Enabled by default
        self.fallback_check_gateway = fallback.get('check_gateway', True)
        self.fallback_check_tcp = fallback.get('check_tcp', True)
        self.fallback_gateway_ip = fallback.get('gateway_ip', '10.10.110.1')  # Default gateway
        self.fallback_tcp_targets = fallback.get('tcp_targets', [
            ['1.1.1.1', 443],
            ['8.8.8.8', 443],
        ])
        self.fallback_mode = fallback.get('fallback_mode', 'graceful_degradation')
        self.fallback_max_cycles = fallback.get('max_fallback_cycles', 3)

        # Timeouts (with sensible defaults)
        timeouts = self.data.get('timeouts', {})
        self.timeout_ssh_command = timeouts.get('ssh_command', DEFAULT_AUTORATE_SSH_TIMEOUT)
        self.timeout_ping = timeouts.get('ping', DEFAULT_AUTORATE_PING_TIMEOUT)

        # Router transport configuration (ssh or rest)
        router = self.data.get('router', {})
        self.router_transport = router.get('transport', 'ssh')  # Default to SSH
        # REST API specific settings (only used if transport=rest)
        self.router_password = router.get('password', '')
        self.router_port = router.get('port', 443)
        self.router_verify_ssl = router.get('verify_ssl', False)

        # Lock file
        self.lock_file = Path(self.data['lock_file'])
        self.lock_timeout = self.data['lock_timeout']

        # State file (for persisting hysteresis counters)
        # Derive from lock file path: /tmp/wanctl_att.lock -> /tmp/wanctl_att_state.json
        lock_stem = self.lock_file.stem
        self.state_file = self.lock_file.parent / f"{lock_stem}_state.json"

        # Logging
        self.main_log = self.data['logging']['main_log']
        self.debug_log = self.data['logging']['debug_log']

        # Health check configuration (optional, with defaults)
        health = self.data.get('health_check', {})
        self.health_check_enabled = health.get('enabled', True)
        self.health_check_host = health.get('host', '127.0.0.1')
        self.health_check_port = health.get('port', 9101)

        # Metrics configuration (optional, disabled by default)
        # When enabled, exposes Prometheus-compatible metrics at /metrics endpoint
        metrics_config = self.data.get('metrics', {})
        self.metrics_enabled = metrics_config.get('enabled', False)
        self.metrics_host = metrics_config.get('host', '127.0.0.1')
        self.metrics_port = metrics_config.get('port', 9100)


# =============================================================================
# ROUTEROS INTERFACE
# =============================================================================

class RouterOS:
    """RouterOS interface for setting queue limits.

    Supports multiple transports:
    - ssh: SSH via paramiko (default) - uses SSH keys
    - rest: REST API via HTTPS - uses password authentication

    Transport is selected via config.router_transport field.
    """
    def __init__(self, config: Config, logger: logging.Logger):
        self.config = config
        self.logger = logger
        # Use factory function to get appropriate client (SSH or REST)
        self.ssh = get_router_client(config, logger)

    def set_limits(self, wan: str, down_bps: int, up_bps: int) -> bool:
        """Set CAKE limits for one WAN using a single batched SSH command"""
        self.logger.debug(f"{wan}: Setting limits DOWN={down_bps} UP={up_bps}")

        # WAN name for queue type (e.g., "ATT" -> "att", "Spectrum" -> "spectrum")
        wan_lower = self.config.wan_name.lower()

        # Batch both queue commands into a single SSH call for lower latency
        # RouterOS supports semicolon-separated commands
        cmd = (
            f'/queue tree set [find name="{self.config.queue_down}"] '
            f'queue=cake-down-{wan_lower} max-limit={down_bps}; '
            f'/queue tree set [find name="{self.config.queue_up}"] '
            f'queue=cake-up-{wan_lower} max-limit={up_bps}'
        )

        rc, _, _ = self.ssh.run_cmd(cmd)
        if rc != 0:
            self.logger.error(f"Failed to set queue limits: {cmd}")
            return False

        return True


# Note: RTTMeasurement class is now unified in rtt_measurement.py
# This module imports it from there


# =============================================================================
# QUEUE CONTROLLER (3-ZONE LOGIC)
# =============================================================================

class QueueController:
    """Controls one queue (download or upload) with 3-zone or 4-zone logic"""
    def __init__(self, name: str, floor_green: int, floor_yellow: int, floor_soft_red: int, floor_red: int, ceiling: int, step_up: int, factor_down: float):
        self.name = name
        self.floor_green_bps = floor_green
        self.floor_yellow_bps = floor_yellow
        self.floor_soft_red_bps = floor_soft_red  # Phase 2A
        self.floor_red_bps = floor_red
        self.ceiling_bps = ceiling
        self.step_up_bps = step_up
        self.factor_down = factor_down
        self.current_rate = ceiling  # Start at ceiling

        # Hysteresis counters (require consecutive green cycles before stepping up)
        self.green_streak = 0
        self.soft_red_streak = 0      # Phase 2A: Track SOFT_RED sustain
        self.red_streak = 0
        self.green_required = 5        # Require 5 consecutive green cycles before stepping up
        self.soft_red_required = 3     # Phase 2A: Require 3 cycles (~6s) to confirm SOFT_RED

    def adjust(self, baseline_rtt: float, load_rtt: float, target_delta: float, warn_delta: float) -> tuple[str, int]:
        """
        Apply 3-zone logic with hysteresis and return (zone, new_rate)

        Zones:
        - GREEN: delta <= target_delta -> slowly increase rate (requires consecutive green cycles)
        - YELLOW: target_delta < delta <= warn_delta -> hold steady
        - RED: delta > warn_delta -> aggressively back off (immediate)

        Hysteresis:
        - RED: Immediate step-down on 1 red sample
        - GREEN: Require 5 consecutive green cycles before stepping up (prevents seesaw)
        """
        delta = load_rtt - baseline_rtt

        # Update streak counters
        if delta > warn_delta:
            # RED zone
            self.red_streak += 1
            self.green_streak = 0
            zone = "RED"
        elif delta > target_delta:
            # YELLOW zone
            self.green_streak = 0
            self.red_streak = 0
            zone = "YELLOW"
        else:
            # GREEN zone
            self.green_streak += 1
            self.red_streak = 0
            zone = "GREEN"

        # Apply rate adjustments with hysteresis
        new_rate = self.current_rate

        if self.red_streak >= 1:
            # RED: Gradual decay using factor_down
            new_rate = int(self.current_rate * self.factor_down)
        elif self.green_streak >= self.green_required:
            # GREEN: Only step up after 5 consecutive green cycles
            new_rate = self.current_rate + self.step_up_bps
        # else: YELLOW or not enough green streak -> hold steady

        # Enforce floor and ceiling constraints
        new_rate = enforce_rate_bounds(new_rate, floor=self.floor_red_bps, ceiling=self.ceiling_bps)

        self.current_rate = new_rate
        return zone, new_rate

    def adjust_4state(self, baseline_rtt: float, load_rtt: float, green_threshold: float, soft_red_threshold: float, hard_red_threshold: float) -> tuple[str, int]:
        """
        Apply 4-state logic with hysteresis and return (state, new_rate)

        Phase 2A: Download-only (Spectrum download)
        Upload continues to use 3-state adjust() method

        States (based on RTT delta from baseline):
        - GREEN: delta ≤ 15ms -> slowly increase rate (requires consecutive green cycles)
        - YELLOW: 15ms < delta ≤ 45ms -> hold steady
        - SOFT_RED: 45ms < delta ≤ 80ms -> clamp to soft_red floor and HOLD (no steering)
        - RED: delta > 80ms -> aggressive backoff (immediate)

        Hysteresis:
        - RED: Immediate on 1 sample
        - SOFT_RED: Requires 3 consecutive samples (~6 seconds)
        - GREEN: Requires 5 consecutive samples before stepping up
        - YELLOW: Immediate
        """
        delta = load_rtt - baseline_rtt

        # Determine raw state based on thresholds
        if delta > hard_red_threshold:
            raw_state = "RED"
        elif delta > soft_red_threshold:
            raw_state = "SOFT_RED"
        elif delta > green_threshold:
            raw_state = "YELLOW"
        else:
            raw_state = "GREEN"

        # Apply sustain logic for SOFT_RED
        # SOFT_RED requires 3 consecutive samples to confirm
        if raw_state == "SOFT_RED":
            self.soft_red_streak += 1
            self.green_streak = 0
            self.red_streak = 0

            if self.soft_red_streak >= self.soft_red_required:
                zone = "SOFT_RED"
            else:
                # Not sustained yet - stay in YELLOW
                zone = "YELLOW"
        elif raw_state == "RED":
            self.red_streak += 1
            self.soft_red_streak = 0
            self.green_streak = 0
            zone = "RED"
        elif raw_state == "YELLOW":
            self.green_streak = 0
            self.soft_red_streak = 0
            self.red_streak = 0
            zone = "YELLOW"
        else:  # GREEN
            self.green_streak += 1
            self.soft_red_streak = 0
            self.red_streak = 0
            zone = "GREEN"

        # Apply rate adjustments with state-appropriate floors
        new_rate = self.current_rate

        # Determine appropriate floor based on state
        state_floor = self.floor_green_bps  # Default

        if self.red_streak >= 1:
            # RED: Gradual decay using factor_down
            new_rate = int(self.current_rate * self.factor_down)
            state_floor = self.floor_red_bps
        elif zone == "SOFT_RED":
            # SOFT_RED: Clamp to soft_red floor and HOLD (no repeated decay)
            # Keep current rate but enforce soft_red floor
            state_floor = self.floor_soft_red_bps
        elif self.green_streak >= self.green_required:
            # GREEN: Only step up after 5 consecutive green cycles
            new_rate = self.current_rate + self.step_up_bps
        elif zone == "YELLOW":
            # YELLOW or not enough green streak -> hold steady with yellow floor
            state_floor = self.floor_yellow_bps
        # else: GREEN but not sustained -> use default floor_green_bps

        # Enforce floor and ceiling constraints based on current state
        new_rate = enforce_rate_bounds(new_rate, floor=state_floor, ceiling=self.ceiling_bps)

        self.current_rate = new_rate
        return zone, new_rate


# =============================================================================
# WAN CONTROLLER
# =============================================================================

class WANController:
    """Controls both download and upload for one WAN"""
    def __init__(self, wan_name: str, config: Config, router: RouterOS, rtt_measurement: RTTMeasurement, logger: logging.Logger):
        self.wan_name = wan_name
        self.config = config
        self.router = router
        self.rtt_measurement = rtt_measurement
        self.logger = logger

        # Initialize baseline from config (will be measured and updated)
        self.baseline_rtt = config.baseline_rtt_initial
        self.load_rtt = self.baseline_rtt

        # Create queue controllers
        self.download = QueueController(
            name=f"{wan_name}-Download",
            floor_green=config.download_floor_green,
            floor_yellow=config.download_floor_yellow,
            floor_soft_red=config.download_floor_soft_red,  # Phase 2A
            floor_red=config.download_floor_red,
            ceiling=config.download_ceiling,
            step_up=config.download_step_up,
            factor_down=config.download_factor_down
        )

        self.upload = QueueController(
            name=f"{wan_name}-Upload",
            floor_green=config.upload_floor_green,
            floor_yellow=config.upload_floor_yellow,
            floor_soft_red=config.upload_floor_yellow,  # Phase 2A: Upload unchanged, use yellow for soft_red
            floor_red=config.upload_floor_red,
            ceiling=config.upload_ceiling,
            step_up=config.upload_step_up,
            factor_down=config.upload_factor_down
        )

        # Thresholds (Phase 2A: 4-state for download, 3-state for upload)
        self.green_threshold = config.target_bloat_ms         # 15ms: GREEN → YELLOW
        self.soft_red_threshold = config.warn_bloat_ms        # 45ms: YELLOW → SOFT_RED
        self.hard_red_threshold = config.hard_red_bloat_ms    # 80ms: SOFT_RED → RED
        # Legacy 3-state thresholds (for upload)
        self.target_delta = config.target_bloat_ms
        self.warn_delta = config.warn_bloat_ms
        self.alpha_baseline = config.alpha_baseline
        self.alpha_load = config.alpha_load
        self.baseline_update_threshold = config.baseline_update_threshold_ms

        # Ping configuration
        self.ping_hosts = config.ping_hosts
        self.use_median_of_three = config.use_median_of_three

        # =====================================================================
        # FLASH WEAR PROTECTION - Track last applied rates
        # =====================================================================
        # RouterOS writes queue changes to NAND flash. To prevent excessive
        # flash wear, we only send updates when rates actually change.
        # DO NOT REMOVE THIS - it protects the router's flash memory.
        # =====================================================================
        self.last_applied_dl_rate: int | None = None
        self.last_applied_ul_rate: int | None = None

        # =====================================================================
        # RATE LIMITER - Protect router API during instability
        # =====================================================================
        # Limits configuration changes to prevent API overload during rapid
        # state oscillations. Default: 10 changes per 60 seconds.
        # =====================================================================
        self.rate_limiter = RateLimiter(
            max_changes=DEFAULT_RATE_LIMIT_MAX_CHANGES,
            window_seconds=DEFAULT_RATE_LIMIT_WINDOW_SECONDS
        )

        # =====================================================================
        # FALLBACK CONNECTIVITY TRACKING
        # =====================================================================
        # Track consecutive cycles where ICMP failed but other connectivity exists.
        # Used for graceful degradation when ICMP is filtered but WAN works.
        # =====================================================================
        self.icmp_unavailable_cycles = 0

        # Load persisted state (hysteresis counters, current rates, EWMA)
        self.load_state()

    def measure_rtt(self) -> float | None:
        """
        Measure RTT and return average in milliseconds

        For connections with reflector variation (cable): Use median-of-three reflectors
        For stable connections (DSL, fiber): Single reflector is fine

        Pings are run concurrently for faster cycle times.
        """
        if self.use_median_of_three and len(self.ping_hosts) >= 3:
            # Ping multiple hosts CONCURRENTLY, take median to handle reflector variation
            hosts_to_ping = self.ping_hosts[:3]  # Use first 3

            # Run pings in parallel using ThreadPoolExecutor
            with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
                futures = {
                    executor.submit(self.rtt_measurement.ping_host, host, 1): host
                    for host in hosts_to_ping
                }

                rtts = []
                for future in concurrent.futures.as_completed(futures, timeout=3):
                    try:
                        rtt = future.result()
                        if rtt is not None:
                            rtts.append(rtt)
                    except Exception as e:
                        host = futures[future]
                        self.logger.debug(f"{self.wan_name}: Ping to {host} failed: {e}")

            if len(rtts) >= 2:
                median_rtt = statistics.median(rtts)
                self.logger.debug(f"{self.wan_name}: Median-of-{len(rtts)} RTT = {median_rtt:.2f}ms")
                return median_rtt
            elif len(rtts) == 1:
                return rtts[0]
            else:
                self.logger.warning(f"{self.wan_name}: All pings failed (median-of-three)")
                return None
        else:
            # Single host ping
            return self.rtt_measurement.ping_host(self.ping_hosts[0], count=1)

    def update_ewma(self, measured_rtt: float) -> None:
        """Update both EWMAs (fast load, slow baseline)"""
        # Fast EWMA for load_rtt (responsive to current conditions)
        self.load_rtt = (1 - self.alpha_load) * self.load_rtt + self.alpha_load * measured_rtt

        # Slow EWMA for baseline_rtt (ONLY update when line is genuinely idle)
        # This tracks the "normal" RTT without congestion
        #
        # Critical: Only update baseline when delta is very small
        # This prevents baseline drift during load, which would mask true bloat
        delta = self.load_rtt - self.baseline_rtt
        if delta < self.baseline_update_threshold:
            # Line is idle or nearly idle - safe to update baseline
            self.baseline_rtt = (1 - self.alpha_baseline) * self.baseline_rtt + self.alpha_baseline * measured_rtt
        # else: Under load - freeze baseline to prevent drift

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
        result = self.rtt_measurement.ping_host(gateway_ip, count=1)
        if result is not None:
            self.logger.warning(
                f"{self.wan_name}: External pings failed but gateway {gateway_ip} reachable - "
                f"likely WAN issue, not container networking"
            )
            return True
        return False

    def verify_tcp_connectivity(self) -> bool:
        """
        Check if we can establish TCP connections (HTTPS).

        Tests multiple targets using TCP handshake to verify Internet connectivity
        when ICMP is blocked/filtered.

        Returns:
            True if ANY TCP connection succeeds (ICMP-specific issue)
            False if all TCP attempts fail (total connectivity loss)
        """
        if not self.config.fallback_check_tcp:
            return False

        for host, port in self.config.fallback_tcp_targets:
            try:
                sock = socket.create_connection((host, port), timeout=2)
                sock.close()
                self.logger.warning(
                    f"{self.wan_name}: ICMP failed but TCP to {host}:{port} succeeded - "
                    f"ICMP-specific issue, continuing with degraded monitoring"
                )
                return True
            except (socket.timeout, OSError, socket.gaierror) as e:
                self.logger.debug(f"TCP to {host}:{port} failed: {e}")
                continue

        return False  # All TCP attempts failed

    def verify_connectivity_fallback(self) -> bool:
        """
        Multi-protocol connectivity verification.

        When all ICMP pings fail, verify if we have ANY connectivity
        using alternative protocols before declaring total failure.

        Returns:
            True if ANY connectivity detected (ICMP-specific issue)
            False if total connectivity loss confirmed
        """
        if not self.config.fallback_enabled:
            return False

        self.logger.warning(f"{self.wan_name}: All ICMP pings failed - running fallback checks")

        # Check 1: Local gateway (fastest, ~50ms)
        if self.verify_local_connectivity():
            return True

        # Check 2: TCP HTTPS (most reliable, ~100-200ms)
        if self.verify_tcp_connectivity():
            return True

        # If both fail, it's likely a real WAN outage
        self.logger.error(
            f"{self.wan_name}: Both ICMP and TCP connectivity failed - "
            f"confirmed total connectivity loss"
        )
        return False

    def run_cycle(self) -> bool:
        """Main 5-second cycle for this WAN"""
        cycle_start = time.monotonic()

        measured_rtt = self.measure_rtt()

        # =====================================================================
        # ICMP FAILURE HANDLING WITH FALLBACK CHECKS (Mode C)
        # =====================================================================
        # When ICMP pings fail, verify connectivity using alternative protocols
        # (gateway ping, TCP connections) before declaring total failure.
        # Implements graceful degradation to handle ISP ICMP filtering.
        # =====================================================================
        if measured_rtt is None:
            if self.config.metrics_enabled:
                record_ping_failure(self.wan_name)

            # Run fallback connectivity checks
            has_connectivity = self.verify_connectivity_fallback()

            if has_connectivity:
                # We have connectivity, just can't measure RTT via ICMP
                self.icmp_unavailable_cycles += 1

                if self.config.fallback_mode == 'graceful_degradation':
                    # Mode C: Graceful degradation with cycle-based strategy
                    if self.icmp_unavailable_cycles == 1:
                        # Cycle 1: Use last known RTT and continue normally
                        measured_rtt = self.load_rtt
                        self.logger.warning(
                            f"{self.wan_name}: ICMP unavailable (cycle 1/{self.config.fallback_max_cycles}) - "
                            f"using last RTT={measured_rtt:.1f}ms"
                        )
                        # Continue with normal processing below
                    elif self.icmp_unavailable_cycles <= self.config.fallback_max_cycles:
                        # Cycles 2-3: Freeze rates (don't adjust, but don't fail)
                        self.logger.warning(
                            f"{self.wan_name}: ICMP unavailable (cycle {self.icmp_unavailable_cycles}/"
                            f"{self.config.fallback_max_cycles}) - freezing rates"
                        )
                        self.save_state()
                        return True  # Success (no watchdog trigger), but skip adjustments
                    else:
                        # Cycle 4+: Give up (ICMP down for too long)
                        self.logger.error(
                            f"{self.wan_name}: ICMP unavailable for {self.icmp_unavailable_cycles} cycles "
                            f"(>{self.config.fallback_max_cycles}) - giving up"
                        )
                        return False  # Trigger watchdog restart

                elif self.config.fallback_mode == 'freeze':
                    # Mode A: Always freeze rates when ICMP unavailable
                    self.logger.warning(f"{self.wan_name}: ICMP unavailable - freezing rates (mode: freeze)")
                    self.save_state()
                    return True

                elif self.config.fallback_mode == 'use_last_rtt':
                    # Mode B: Always use last known RTT
                    measured_rtt = self.load_rtt
                    self.logger.warning(
                        f"{self.wan_name}: ICMP unavailable - using last RTT={measured_rtt:.1f}ms "
                        f"(mode: use_last_rtt)"
                    )
                    # Continue with normal processing below
                else:
                    # Unknown mode, default to original behavior
                    self.logger.error(f"{self.wan_name}: Unknown fallback_mode: {self.config.fallback_mode}")
                    return False

            else:
                # Total connectivity loss confirmed (both ICMP and TCP failed)
                self.logger.warning(f"{self.wan_name}: Total connectivity loss - skipping cycle")
                return False

        else:
            # ICMP succeeded - reset fallback counter if it was set
            if self.icmp_unavailable_cycles > 0:
                self.logger.info(
                    f"{self.wan_name}: ICMP recovered after {self.icmp_unavailable_cycles} cycles"
                )
                self.icmp_unavailable_cycles = 0

        # At this point, measured_rtt is valid (either from ICMP or last known value)
        self.update_ewma(measured_rtt)

        # Download: 4-state logic (GREEN/YELLOW/SOFT_RED/RED) - Phase 2A
        dl_zone, dl_rate = self.download.adjust_4state(
            self.baseline_rtt, self.load_rtt,
            self.green_threshold, self.soft_red_threshold, self.hard_red_threshold
        )

        # Upload: 3-state logic (GREEN/YELLOW/RED) - unchanged for Phase 2A
        ul_zone, ul_rate = self.upload.adjust(
            self.baseline_rtt, self.load_rtt,
            self.target_delta, self.warn_delta
        )

        # Log decision
        delta = self.load_rtt - self.baseline_rtt
        self.logger.info(
            f"{self.wan_name}: [{dl_zone}/{ul_zone}] "
            f"RTT={measured_rtt:.1f}ms, load_ewma={self.load_rtt:.1f}ms, "
            f"baseline={self.baseline_rtt:.1f}ms, delta={delta:.1f}ms | "
            f"DL={dl_rate/1e6:.0f}M, UL={ul_rate/1e6:.0f}M"
        )

        # =====================================================================
        # FLASH WEAR PROTECTION - Only update router if rates changed
        # =====================================================================
        # RouterOS writes queue changes to NAND flash. Sending the same values
        # repeatedly would cause unnecessary flash wear over time.
        # DO NOT REMOVE THIS CHECK - it protects the router's flash memory.
        # =====================================================================
        if dl_rate != self.last_applied_dl_rate or ul_rate != self.last_applied_ul_rate:
            # =====================================================================
            # RATE LIMITING - Protect router API during instability
            # =====================================================================
            # During rapid state oscillations, limit how often we send updates
            # to prevent router API overload. Skip update if rate limited.
            # =====================================================================
            if not self.rate_limiter.can_change():
                wait_time = self.rate_limiter.time_until_available()
                self.logger.warning(
                    f"{self.wan_name}: Rate limit exceeded (>{DEFAULT_RATE_LIMIT_MAX_CHANGES} "
                    f"changes/{DEFAULT_RATE_LIMIT_WINDOW_SECONDS}s), throttling update - "
                    f"possible instability (next slot in {wait_time:.1f}s)"
                )
                if self.config.metrics_enabled:
                    record_rate_limit_event(self.wan_name)
                # Still return True - cycle completed, just throttled the update
                # Save state to preserve EWMA and streak counters
                self.save_state()
                return True

            success = self.router.set_limits(
                wan=self.wan_name,
                down_bps=dl_rate,
                up_bps=ul_rate
            )

            if not success:
                self.logger.error(f"{self.wan_name}: Failed to apply limits")
                return False

            # Record successful change for rate limiting
            self.rate_limiter.record_change()

            # Record metrics for router update
            if self.config.metrics_enabled:
                record_router_update(self.wan_name)

            # Update tracking after successful write
            self.last_applied_dl_rate = dl_rate
            self.last_applied_ul_rate = ul_rate
            self.logger.debug(f"{self.wan_name}: Applied new limits to router")
        else:
            self.logger.debug(f"{self.wan_name}: Rates unchanged, skipping router update (flash wear protection)")

        # Save state after successful cycle
        self.save_state()

        # Record metrics if enabled
        if self.config.metrics_enabled:
            cycle_duration = time.monotonic() - cycle_start
            record_autorate_cycle(
                wan_name=self.wan_name,
                dl_rate_mbps=dl_rate / 1e6,
                ul_rate_mbps=ul_rate / 1e6,
                baseline_rtt=self.baseline_rtt,
                load_rtt=self.load_rtt,
                dl_state=dl_zone,
                ul_state=ul_zone,
                cycle_duration=cycle_duration,
            )

        return True

    @handle_errors(error_msg="{self.wan_name}: Could not load state: {exception}")
    def load_state(self) -> None:
        """Load persisted hysteresis state from disk"""
        # Use unified JSON parsing utility
        state = safe_json_load_file(
            self.config.state_file,
            logger=self.logger,
            default=None,
            error_context=f"{self.wan_name} state"
        )

        if state is not None:
            # Restore download controller state
            if 'download' in state:
                dl = state['download']
                self.download.green_streak = dl.get('green_streak', 0)
                self.download.soft_red_streak = dl.get('soft_red_streak', 0)  # Phase 2A
                self.download.red_streak = dl.get('red_streak', 0)
                self.download.current_rate = dl.get('current_rate', self.download.ceiling_bps)

            # Restore upload controller state
            if 'upload' in state:
                ul = state['upload']
                self.upload.green_streak = ul.get('green_streak', 0)
                self.upload.soft_red_streak = ul.get('soft_red_streak', 0)  # Phase 2A
                self.upload.red_streak = ul.get('red_streak', 0)
                self.upload.current_rate = ul.get('current_rate', self.upload.ceiling_bps)

            # Restore EWMA state
            if 'ewma' in state:
                ewma = state['ewma']
                self.baseline_rtt = ewma.get('baseline_rtt', self.baseline_rtt)
                self.load_rtt = ewma.get('load_rtt', self.load_rtt)

            # Restore last applied rates (flash wear protection)
            if 'last_applied' in state:
                applied = state['last_applied']
                self.last_applied_dl_rate = applied.get('dl_rate')
                self.last_applied_ul_rate = applied.get('ul_rate')

            self.logger.debug(f"{self.wan_name}: Loaded state from {self.config.state_file}")

    @handle_errors(error_msg="{self.wan_name}: Could not save state: {exception}")
    def save_state(self) -> None:
        """Save hysteresis state to disk for persistence across timer invocations"""
        state = {
            'download': {
                'green_streak': self.download.green_streak,
                'soft_red_streak': self.download.soft_red_streak,  # Phase 2A
                'red_streak': self.download.red_streak,
                'current_rate': self.download.current_rate
            },
            'upload': {
                'green_streak': self.upload.green_streak,
                'soft_red_streak': self.upload.soft_red_streak,  # Phase 2A
                'red_streak': self.upload.red_streak,
                'current_rate': self.upload.current_rate
            },
            'ewma': {
                'baseline_rtt': self.baseline_rtt,
                'load_rtt': self.load_rtt
            },
            # Flash wear protection: track last values sent to router
            'last_applied': {
                'dl_rate': self.last_applied_dl_rate,
                'ul_rate': self.last_applied_ul_rate
            },
            'timestamp': datetime.datetime.now().isoformat()
        }

        atomic_write_json(self.config.state_file, state)
        self.logger.debug(f"{self.wan_name}: Saved state to {self.config.state_file}")


# =============================================================================
# MAIN CONTROLLER
# =============================================================================

class ContinuousAutoRate:
    """Main controller managing one or more WANs"""
    def __init__(self, config_files: list[str], debug: bool = False):
        self.wan_controllers = []
        self.debug = debug

        # Load each WAN config and create controller
        for config_file in config_files:
            config = Config(config_file)
            logger = setup_logging(config, "cake_continuous", debug)

            logger.info(f"=== Continuous CAKE Controller - {config.wan_name} ===")
            logger.info(f"Download: GREEN={config.download_floor_green/1e6:.0f}M, YELLOW={config.download_floor_yellow/1e6:.0f}M, "
                       f"SOFT_RED={config.download_floor_soft_red/1e6:.0f}M, RED={config.download_floor_red/1e6:.0f}M, "
                       f"ceiling={config.download_ceiling/1e6:.0f}M, step={config.download_step_up/1e6:.1f}M, factor={config.download_factor_down}")
            logger.info(f"Upload: GREEN={config.upload_floor_green/1e6:.0f}M, YELLOW={config.upload_floor_yellow/1e6:.0f}M, RED={config.upload_floor_red/1e6:.0f}M, ceiling={config.upload_ceiling/1e6:.0f}M, "
                       f"step={config.upload_step_up/1e6:.1f}M, factor={config.upload_factor_down}")
            logger.info(f"Download Thresholds: GREEN→YELLOW={config.target_bloat_ms}ms, YELLOW→SOFT_RED={config.warn_bloat_ms}ms, SOFT_RED→RED={config.hard_red_bloat_ms}ms")
            logger.info(f"Upload Thresholds: GREEN→YELLOW={config.target_bloat_ms}ms, YELLOW→RED={config.warn_bloat_ms}ms")
            logger.info(f"EWMA: baseline_alpha={config.alpha_baseline}, load_alpha={config.alpha_load}")
            logger.info(f"Ping: hosts={config.ping_hosts}, median-of-three={config.use_median_of_three}")

            # Create shared instances
            router = RouterOS(config, logger)
            # Use unified RTTMeasurement with AVERAGE aggregation and sample stats logging
            rtt_measurement = RTTMeasurement(
                logger,
                timeout_ping=config.timeout_ping,
                aggregation_strategy=RTTAggregationStrategy.AVERAGE,
                log_sample_stats=True  # Log min/max for debugging
            )

            # Create WAN controller
            wan_controller = WANController(config.wan_name, config, router, rtt_measurement, logger)

            self.wan_controllers.append({
                'controller': wan_controller,
                'config': config,
                'logger': logger
            })

    def run_cycle(self, use_lock: bool = True) -> bool:
        """Run one cycle for all WANs

        Args:
            use_lock: If True, acquire lock per-cycle (oneshot mode).
                     If False, assume lock is already held (daemon mode).

        Returns:
            True if ALL WANs successfully completed cycle
            False if ANY WAN failed
        """
        all_success = True

        for wan_info in self.wan_controllers:
            controller = wan_info['controller']
            config = wan_info['config']
            logger = wan_info['logger']

            try:
                if use_lock:
                    with LockFile(config.lock_file, config.lock_timeout, logger):
                        success = controller.run_cycle()
                        all_success = all_success and success
                else:
                    # Lock already held by daemon - just run the cycle
                    success = controller.run_cycle()
                    all_success = all_success and success
            except LockAcquisitionError:
                # Another instance is running - this is normal, not an error
                logger.debug("Skipping cycle - another instance is running")
                all_success = False
            except Exception as e:
                logger.error(f"Cycle error: {e}")
                logger.debug(traceback.format_exc())
                all_success = False

        return all_success

    def get_lock_paths(self) -> list[Path]:
        """Return lock file paths for all configured WANs"""
        return [wan_info['config'].lock_file for wan_info in self.wan_controllers]


# =============================================================================
# MAIN ENTRY POINT
# =============================================================================

def main() -> int | None:
    """Main entry point for continuous CAKE auto-tuning daemon.

    Runs persistent bandwidth control with adaptive rate adjustment based on real-time
    latency measurements. Supports both single-WAN and multi-WAN configurations with
    concurrent control loops for each interface.

    The daemon operates in several modes:
    - **Daemon mode** (default): Runs continuous control loop at 50ms intervals,
      monitoring latency and adjusting CAKE queue limits to prevent bufferbloat while
      maximizing throughput. Handles SIGTERM/SIGINT gracefully and integrates with
      systemd watchdog for automatic recovery.
    - **Oneshot mode** (--oneshot): Executes single measurement and adjustment cycle,
      useful for testing and manual verification.
    - **Validation mode** (--validate-config): Validates configuration files and exits,
      ideal for CI/CD pipelines and pre-deployment checks.

    Startup sequence:
    1. Parse command-line arguments and load YAML configurations
    2. Initialize ContinuousAutoRate controller with per-WAN state machines
    3. Acquire exclusive locks to prevent concurrent instances
    4. Register signal handlers for graceful shutdown
    5. Start optional metrics (Prometheus) and health check servers
    6. Enter control loop with automatic watchdog notification

    Shutdown sequence (on SIGTERM/SIGINT):
    1. Stop accepting new cycles (shutdown_event set)
    2. Release all lock files
    3. Close router connections (SSH/REST)
    4. Shut down metrics and health servers
    5. Log clean shutdown and exit

    Returns:
        int | None: Exit code indicating daemon termination reason:
            - 0: Configuration validation passed (--validate-config mode)
            - 1: Configuration validation failed or lock acquisition failed
            - 130: Interrupted by signal (SIGINT/Ctrl+C)
            - None: Clean shutdown in daemon mode (SIGTERM or oneshot completion)
    """
    parser = argparse.ArgumentParser(
        description="Continuous CAKE Auto-Tuning Daemon with 2-second Control Loop"
    )
    parser.add_argument(
        '--config', nargs='+', required=True,
        help='One or more config files (supports single-WAN or multi-WAN)'
    )
    parser.add_argument(
        '--debug', action='store_true',
        help='Enable debug logging to console and debug log file'
    )
    parser.add_argument(
        '--oneshot', action='store_true',
        help='Run one cycle and exit (for testing/manual runs)'
    )
    parser.add_argument(
        '--validate-config', action='store_true',
        help='Validate configuration and exit (dry-run mode for CI/CD)'
    )

    args = parser.parse_args()

    # Validate-config mode: check configuration and exit
    if args.validate_config:
        all_valid = True
        for config_file in args.config:
            try:
                config = Config(config_file)
                print(f"Configuration valid: {config_file}")
                print(f"  WAN: {config.wan_name}")
                print(f"  Transport: {config.router_transport}")
                print(f"  Router: {config.router_host}:{config.router_user}")
                print(f"  Download: {config.download_floor_red/1e6:.0f}M - {config.download_ceiling/1e6:.0f}M")
                print(f"    Floors: GREEN={config.download_floor_green/1e6:.0f}M, "
                      f"YELLOW={config.download_floor_yellow/1e6:.0f}M, "
                      f"SOFT_RED={config.download_floor_soft_red/1e6:.0f}M, "
                      f"RED={config.download_floor_red/1e6:.0f}M")
                print(f"  Upload: {config.upload_floor_red/1e6:.0f}M - {config.upload_ceiling/1e6:.0f}M")
                print(f"    Floors: GREEN={config.upload_floor_green/1e6:.0f}M, "
                      f"YELLOW={config.upload_floor_yellow/1e6:.0f}M, "
                      f"RED={config.upload_floor_red/1e6:.0f}M")
                print(f"  Thresholds: GREEN<={config.target_bloat_ms}ms, "
                      f"SOFT_RED<={config.warn_bloat_ms}ms, RED>{config.hard_red_bloat_ms}ms")
                print(f"  Ping hosts: {config.ping_hosts}")
                print(f"  Queue names: {config.queue_down}, {config.queue_up}")
            except Exception as e:
                print(f"Configuration INVALID: {config_file}")
                print(f"  Error: {e}")
                all_valid = False
        return 0 if all_valid else 1

    # Create controller
    controller = ContinuousAutoRate(args.config, debug=args.debug)

    # Oneshot mode for testing - use per-cycle locking
    if args.oneshot:
        controller.run_cycle(use_lock=True)
        return

    # Daemon mode: continuous loop with 2-second cycle time
    # Acquire locks once at startup and hold for entire run
    lock_files = []
    for lock_path in controller.get_lock_paths():
        # Use unified lock validation and acquisition from lock_utils
        # This handles PID validation, stale lock cleanup, and atomic lock creation
        logger = controller.wan_controllers[0]['logger']  # Use first logger for multi-WAN
        lock_timeout = controller.wan_controllers[0]['config'].lock_timeout
        try:
            if not validate_and_acquire_lock(lock_path, lock_timeout, logger):
                # Another instance is running
                for wan_info in controller.wan_controllers:
                    wan_info['logger'].error(
                        "Another instance is running, refusing to start"
                    )
                return 1
            lock_files.append(lock_path)
        except RuntimeError as e:
            # Unexpected error during lock validation
            for wan_info in controller.wan_controllers:
                wan_info['logger'].error(f"Failed to validate lock: {e}")
            return 1

    # Register emergency cleanup handler for abnormal termination (e.g., SIGKILL)
    # atexit handlers run on normal exit, sys.exit(), and unhandled exceptions
    # but NOT on SIGKILL - that's unavoidable. However, this covers more cases
    # than relying solely on the finally block.
    def emergency_lock_cleanup():
        """Emergency cleanup - runs via atexit if finally block doesn't complete."""
        for lock_path in lock_files:
            try:
                lock_path.unlink(missing_ok=True)
            except OSError:
                pass  # Best effort - nothing we can do

    atexit.register(emergency_lock_cleanup)

    # Register signal handlers for graceful shutdown
    register_signal_handlers()

    consecutive_failures = 0
    MAX_CONSECUTIVE_FAILURES = 3
    watchdog_enabled = True
    health_server = None
    metrics_server = None

    # Start metrics server if enabled (use first WAN's config for settings)
    first_config = controller.wan_controllers[0]['config']
    if first_config.metrics_enabled:
        try:
            metrics_server = start_metrics_server(
                host=first_config.metrics_host,
                port=first_config.metrics_port,
            )
            for wan_info in controller.wan_controllers:
                wan_info['logger'].info(
                    f"Prometheus metrics available at http://{first_config.metrics_host}:{first_config.metrics_port}/metrics"
                )
        except OSError as e:
            # Non-fatal: log warning but continue without metrics
            for wan_info in controller.wan_controllers:
                wan_info['logger'].warning(f"Failed to start metrics server: {e}")

    # Start health check server
    if first_config.health_check_enabled:
        try:
            health_server = start_health_server(
                host=first_config.health_check_host,
                port=first_config.health_check_port,
                controller=controller,
            )
        except OSError as e:
            # Non-fatal: log warning but continue without health check
            for wan_info in controller.wan_controllers:
                wan_info['logger'].warning(f"Failed to start health check server: {e}")

    # Log startup
    for wan_info in controller.wan_controllers:
        wan_info['logger'].info(f"Starting daemon mode with {CYCLE_INTERVAL_SECONDS}s cycle interval")
        if is_systemd_available():
            wan_info['logger'].info("Systemd watchdog support enabled")

    try:
        while not is_shutdown_requested():
            cycle_start = time.monotonic()

            # Run cycle - returns True if successful
            cycle_success = controller.run_cycle(use_lock=False)  # Lock already held

            elapsed = time.monotonic() - cycle_start

            # Track consecutive failures
            if cycle_success:
                consecutive_failures = 0
            else:
                consecutive_failures += 1

                for wan_info in controller.wan_controllers:
                    wan_info['logger'].warning(
                        f"Cycle failed ({consecutive_failures}/{MAX_CONSECUTIVE_FAILURES})"
                    )

                # Check if we've exceeded failure threshold
                if consecutive_failures >= MAX_CONSECUTIVE_FAILURES and watchdog_enabled:
                    watchdog_enabled = False
                    for wan_info in controller.wan_controllers:
                        wan_info['logger'].error(
                            f"Sustained failure: {consecutive_failures} consecutive "
                            f"failed cycles. Stopping watchdog - systemd will terminate us."
                        )
                    notify_degraded("consecutive failures exceeded threshold")

            # Update health check endpoint with current failure count
            update_health_status(consecutive_failures)

            # Notify systemd watchdog ONLY if healthy
            if watchdog_enabled and cycle_success:
                notify_watchdog()
            elif not watchdog_enabled:
                notify_degraded(f"{consecutive_failures} consecutive failures")

            # Sleep for remainder of cycle interval
            sleep_time = max(0, CYCLE_INTERVAL_SECONDS - elapsed)
            if sleep_time > 0 and not is_shutdown_requested():
                time.sleep(sleep_time)

        # Log shutdown when detected (safe - in main loop, not signal handler)
        if is_shutdown_requested():
            for wan_info in controller.wan_controllers:
                wan_info['logger'].info("Shutdown requested, exiting gracefully...")

    finally:
        # CLEANUP PRIORITY: locks > connections > servers
        # Lock cleanup is most critical - enables restart if we crash mid-cleanup

        # 1. Clean up lock files FIRST (highest priority for restart capability)
        for lock_path in lock_files:
            try:
                lock_path.unlink(missing_ok=True)
                for wan_info in controller.wan_controllers:
                    wan_info['logger'].debug(f"Lock released: {lock_path}")
            except OSError:
                pass  # Best effort - may already be gone

        # Unregister atexit handler since we've cleaned up successfully
        try:
            atexit.unregister(emergency_lock_cleanup)
        except Exception:
            pass  # Not critical if this fails

        # 2. Clean up SSH/REST connections
        for wan_info in controller.wan_controllers:
            try:
                router = wan_info['controller'].router
                # Handle both SSH and REST transports
                if hasattr(router, 'ssh') and router.ssh:
                    router.ssh.close()
                if hasattr(router, 'close'):
                    router.close()
            except Exception as e:
                wan_info['logger'].debug(f"Error closing router connection: {e}")

        # 3. Shut down metrics server
        if metrics_server:
            try:
                metrics_server.stop()
            except Exception as e:
                for wan_info in controller.wan_controllers:
                    wan_info['logger'].debug(f"Error shutting down metrics server: {e}")

        # 4. Shut down health check server
        if health_server:
            try:
                health_server.shutdown()
            except Exception as e:
                for wan_info in controller.wan_controllers:
                    wan_info['logger'].debug(f"Error shutting down health server: {e}")

        # Log clean shutdown
        for wan_info in controller.wan_controllers:
            wan_info['logger'].info("Daemon shutdown complete")


if __name__ == "__main__":
    sys.exit(main())
