#!/usr/bin/env python3
"""
Adaptive Multi-WAN Steering Daemon

Routes latency-sensitive traffic to an alternate WAN when the primary WAN degrades.
Uses three-layer architecture:
  Layer 1 (DSCP): EF/AF31 = latency-sensitive
  Layer 2 (Connection-marks): LATENCY_SENSITIVE mark drives routing
  Layer 3 (Address-lists): Surgical overrides via FORCE_OUT_<WAN>

State machine:
  <PRIMARY>_GOOD: All traffic uses primary WAN (default)
  <PRIMARY>_DEGRADED: Latency-sensitive traffic routes to alternate WAN

Decision logic:
  delta = current_rtt - baseline_rtt
  Hysteresis prevents flapping (asymmetric streak counting)

Designed to run every 2 seconds via systemd timer (one-shot execution).
Colocated with autorate_continuous on primary WAN controller.
"""

import argparse
import atexit
import json
import logging
import sys
import time
import traceback
from pathlib import Path

from ..config_base import BaseConfig
from ..config_validation_utils import validate_alpha
from ..lock_utils import validate_and_acquire_lock
from ..logging_utils import setup_logging
from ..metrics import record_steering_state, record_steering_transition
from ..retry_utils import measure_with_retry, verify_with_retry
from ..router_client import get_router_client
from ..rtt_measurement import RTTAggregationStrategy, RTTMeasurement
from ..signal_utils import (
    get_shutdown_event,
    is_shutdown_requested,
    register_signal_handlers,
)
from ..state_manager import StateSchema, SteeringStateManager
from ..systemd_utils import (
    is_systemd_available,
    notify_degraded,
    notify_watchdog,
)
from ..timeouts import DEFAULT_STEERING_PING_TOTAL_TIMEOUT, DEFAULT_STEERING_SSH_TIMEOUT
from .cake_stats import CakeStatsReader, CongestionSignals
from .congestion_assessment import (
    CongestionState,
    StateThresholds,
    assess_congestion_state,
    ewma_update,
)

# =============================================================================
# CONSTANTS
# =============================================================================

# Default congestion thresholds (milliseconds)
DEFAULT_BAD_THRESHOLD_MS = 25.0       # RTT delta threshold for bad state
DEFAULT_RECOVERY_THRESHOLD_MS = 12.0  # RTT delta threshold for recovery

# Default sample counts for state transitions
DEFAULT_GOOD_SAMPLES = 15             # Consecutive good samples before recovery
DEFAULT_GREEN_SAMPLES_REQUIRED = 15   # Consecutive GREEN samples before steering off

# Default RTT thresholds for congestion states (milliseconds)
DEFAULT_GREEN_RTT_MS = 5.0            # Below this = GREEN
DEFAULT_YELLOW_RTT_MS = 15.0          # Above this = YELLOW
DEFAULT_RED_RTT_MS = 15.0             # Above this (with drops) = RED

# Default queue thresholds (packets)
DEFAULT_MIN_QUEUE_YELLOW = 10         # Queue depth for YELLOW warning
DEFAULT_MIN_QUEUE_RED = 50            # Queue depth for RED (deeper congestion)

# Default EWMA smoothing factors
DEFAULT_RTT_EWMA_ALPHA = 0.3
DEFAULT_QUEUE_EWMA_ALPHA = 0.4

# History and state limits
MAX_TRANSITIONS_HISTORY = 50          # Maximum transition records to keep

# Production standard: 0.05s interval, 2400-sample history (validated Phase 2, 2026-01-13)
# - Synchronizes with autorate_continuous.py CYCLE_INTERVAL_SECONDS
# - 40x faster than original 2s baseline
# - History: 2400 samples × 0.05s = 120 seconds (2-minute window)
# - Sample counts scaled proportionally: bad=320 (16s), good=600 (30s)
# See docs/PRODUCTION_INTERVAL.md for time-constant preservation methodology
MAX_HISTORY_SAMPLES = 2400            # Maximum samples in history (2 minutes at 0.05s intervals)
ASSESSMENT_INTERVAL_SECONDS = 0.05    # Time between assessments (daemon cycle interval)

# Baseline RTT sanity bounds (milliseconds) - C4 fix: tightened from 5-100 to 10-60
# Typical home ISP latencies are 20-50ms. Anything below 10ms indicates local LAN,
# anything above 60ms suggests routing issues or compromised autorate state.
MIN_SANE_BASELINE_RTT = 10.0
MAX_SANE_BASELINE_RTT = 60.0
BASELINE_CHANGE_THRESHOLD = 5.0       # Log warning if baseline changes more than this


# =============================================================================
# CONFIGURATION
# =============================================================================

class SteeringConfig(BaseConfig):
    """Configuration loaded from YAML for steering daemon"""

    # Schema for steering daemon configuration validation
    SCHEMA = [
        # Topology (which WANs to monitor)
        {"path": "topology.primary_wan", "type": str, "required": True},
        {"path": "topology.primary_wan_config", "type": str, "required": True},
        {"path": "topology.alternate_wan", "type": str, "required": True},

        # Mangle rule
        {"path": "mangle_rule.comment", "type": str, "required": True},

        # Measurement
        {"path": "measurement.interval_seconds", "type": (int, float),
         "required": True, "min": 0.01, "max": 60},
        {"path": "measurement.ping_host", "type": str, "required": True},
        {"path": "measurement.ping_count", "type": int,
         "required": True, "min": 1, "max": 20},

        # State persistence
        {"path": "state.file", "type": str, "required": True},
        {"path": "state.history_size", "type": int,
         "required": True, "min": 1, "max": 3000},

        # Logging
        {"path": "logging.main_log", "type": str, "required": True},
        {"path": "logging.debug_log", "type": str, "required": True},

        # Lock file
        {"path": "lock_file", "type": str, "required": True},
        {"path": "lock_timeout", "type": int, "required": True, "min": 1, "max": 3600},

        # Thresholds (required section, individual fields have defaults)
        {"path": "thresholds", "type": dict, "required": True},
    ]

    def _load_specific_fields(self):
        """Load steering daemon-specific configuration fields"""
        # Router transport settings (REST or SSH)
        router = self.data['router']
        self.router_transport = router.get('transport', 'ssh')  # Default to SSH
        # REST-specific settings
        self.router_password = router.get('password', '')
        self.router_port = router.get('port', 443)
        self.router_verify_ssl = router.get('verify_ssl', False)

        # Topology - which WANs to monitor and steer between
        topology = self.data.get('topology', {})
        self.primary_wan = topology.get('primary_wan', 'wan1')
        self.primary_wan_config = Path(topology.get('primary_wan_config', f'/etc/wanctl/{self.primary_wan}.yaml'))
        self.alternate_wan = topology.get('alternate_wan', 'wan2')

        # Derive state names from topology (e.g., "WAN1_GOOD", "WAN1_DEGRADED")
        self.state_good = f"{self.primary_wan.upper()}_GOOD"
        self.state_degraded = f"{self.primary_wan.upper()}_DEGRADED"

        # Primary WAN state file (for baseline RTT)
        self.primary_state_file = Path(self.data.get('cake_state_sources', {}).get(
            'primary', f'/var/lib/wanctl/{self.primary_wan}_state.json'
        ))

        # Legacy support: cake_state_sources.spectrum -> primary
        if 'cake_state_sources' in self.data:
            sources = self.data['cake_state_sources']
            if 'spectrum' in sources and 'primary' not in sources:
                self.primary_state_file = Path(sources['spectrum'])

        # Mangle rule to toggle (validated to prevent command injection)
        self.mangle_rule_comment = self.validate_comment(
            self.data['mangle_rule']['comment'], 'mangle_rule.comment'
        )

        # RTT measurement (ping_host validated to prevent command injection - C3 fix)
        self.measurement_interval = self.data['measurement']['interval_seconds']
        self.ping_host = self.validate_ping_host(
            self.data['measurement']['ping_host'], 'measurement.ping_host'
        )
        self.ping_count = self.data['measurement']['ping_count']

        # CAKE queue names (for statistics polling, validated to prevent command injection)
        cake_queues = self.data.get('cake_queues', {})
        default_dl_queue = f'WAN-Download-{self.primary_wan.capitalize()}'
        default_ul_queue = f'WAN-Upload-{self.primary_wan.capitalize()}'
        self.primary_download_queue = self.validate_identifier(
            cake_queues.get('primary_download', cake_queues.get('spectrum_download', default_dl_queue)),
            'cake_queues.primary_download'
        )
        self.primary_upload_queue = self.validate_identifier(
            cake_queues.get('primary_upload', cake_queues.get('spectrum_upload', default_ul_queue)),
            'cake_queues.primary_upload'
        )

        # Operational mode
        mode = self.data.get('mode', {})
        self.cake_aware = mode.get('cake_aware', True)
        self.enable_yellow_state = mode.get('enable_yellow_state', True)

        # State machine thresholds
        thresholds = self.data['thresholds']

        # Legacy RTT-only thresholds (backward compatibility)
        self.bad_threshold_ms = thresholds.get('bad_threshold_ms', DEFAULT_BAD_THRESHOLD_MS)
        self.recovery_threshold_ms = thresholds.get('recovery_threshold_ms', DEFAULT_RECOVERY_THRESHOLD_MS)
        self.bad_samples = thresholds.get('bad_samples', 8)
        self.good_samples = thresholds.get('good_samples', DEFAULT_GOOD_SAMPLES)

        # CAKE-aware thresholds (three-state model)
        self.green_rtt_ms = thresholds.get('green_rtt_ms', DEFAULT_GREEN_RTT_MS)
        self.yellow_rtt_ms = thresholds.get('yellow_rtt_ms', DEFAULT_YELLOW_RTT_MS)
        self.red_rtt_ms = thresholds.get('red_rtt_ms', DEFAULT_RED_RTT_MS)
        self.min_drops_red = thresholds.get('min_drops_red', 1)
        self.min_queue_yellow = thresholds.get('min_queue_yellow', DEFAULT_MIN_QUEUE_YELLOW)
        self.min_queue_red = thresholds.get('min_queue_red', DEFAULT_MIN_QUEUE_RED)
        # C5 fix: Validate EWMA alpha bounds during config load
        self.rtt_ewma_alpha = validate_alpha(
            thresholds.get('rtt_ewma_alpha', DEFAULT_RTT_EWMA_ALPHA),
            'thresholds.rtt_ewma_alpha',
            logger=logging.getLogger(__name__)
        )
        self.queue_ewma_alpha = validate_alpha(
            thresholds.get('queue_ewma_alpha', DEFAULT_QUEUE_EWMA_ALPHA),
            'thresholds.queue_ewma_alpha',
            logger=logging.getLogger(__name__)
        )
        self.red_samples_required = thresholds.get('red_samples_required', 2)
        self.green_samples_required = thresholds.get('green_samples_required', DEFAULT_GREEN_SAMPLES_REQUIRED)

        # Baseline RTT bounds (C4 fix: configurable, with security defaults)
        baseline_bounds = thresholds.get('baseline_rtt_bounds', {})
        self.baseline_rtt_min = baseline_bounds.get('min', MIN_SANE_BASELINE_RTT)
        self.baseline_rtt_max = baseline_bounds.get('max', MAX_SANE_BASELINE_RTT)

        # State persistence
        self.state_file = Path(self.data['state']['file'])
        self.history_size = self.data['state']['history_size']

        # Logging
        self.main_log = self.data['logging']['main_log']
        self.debug_log = self.data['logging']['debug_log']
        self.log_cake_stats = self.data['logging'].get('log_cake_stats', True)

        # Lock file
        self.lock_file = Path(self.data['lock_file'])
        self.lock_timeout = self.data['lock_timeout']

        # Timeouts (with sensible defaults)
        timeouts = self.data.get('timeouts', {})
        self.timeout_ssh_command = timeouts.get('ssh_command', DEFAULT_STEERING_SSH_TIMEOUT)
        self.timeout_ping = timeouts.get('ping', 2)  # seconds (-W parameter)
        self.timeout_ping_total = timeouts.get('ping_total', DEFAULT_STEERING_PING_TOTAL_TIMEOUT)

        # Router dict for CakeStatsReader
        self.router = {
            'host': self.router_host,
            'user': self.router_user,
            'ssh_key': self.ssh_key,
            'transport': self.router_transport,
            'password': self.router_password,
            'port': self.router_port,
            'verify_ssl': self.router_verify_ssl
        }

        # Metrics configuration (optional, disabled by default)
        metrics_config = self.data.get('metrics', {})
        self.metrics_enabled = metrics_config.get('enabled', False)

# =============================================================================
# STATE MANAGEMENT
# =============================================================================

def create_steering_state_schema(config: SteeringConfig) -> StateSchema:
    """Create a StateSchema for steering daemon state.

    Defines all steering state fields with defaults based on config.

    Args:
        config: SteeringConfig instance

    Returns:
        StateSchema configured for steering state
    """
    return StateSchema({
        "current_state": config.state_good,
        "bad_count": 0,
        "good_count": 0,
        "baseline_rtt": None,
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
        "cake_read_failures": 0
    })


# =============================================================================
# ROUTEROS INTERFACE
# =============================================================================

class RouterOSController:
    """RouterOS interface to toggle steering rule (supports SSH and REST)"""

    def __init__(self, config: SteeringConfig, logger: logging.Logger):
        self.config = config
        self.logger = logger
        self.client = get_router_client(config, logger)

    def get_rule_status(self) -> bool | None:
        """
        Check if adaptive steering rule is enabled
        Returns: True if enabled, False if disabled, None on error
        """
        rc, out, _ = self.client.run_cmd(
            f'/ip firewall mangle print where comment~"{self.config.mangle_rule_comment}"',
            capture=True,
            timeout=5  # Fast query operation
        )

        if rc != 0:
            self.logger.error("Failed to read mangle rule status")
            return None

        # Parse output - look for X flag in rule line (not in Flags legend)
        # Disabled rule: " 4 X  ;;; comment"
        # Enabled rule:  " 4    ;;; comment"
        lines = out.split('\n')
        for line in lines:
            if 'ADAPTIVE' in line and ';;;' in line:
                # Found the rule line - check for X flag between number and comment
                # Split on ;;; to get the prefix part with flags
                prefix = line.split(';;;')[0] if ';;;' in line else line
                # Check if X appears in the prefix (after rule number)
                if ' X ' in prefix or '\tX\t' in prefix or '\tX ' in prefix or ' X\t' in prefix:
                    self.logger.debug(f"Rule is DISABLED: {line[:60]}")
                    return False
                else:
                    self.logger.debug(f"Rule is ENABLED: {line[:60]}")
                    return True

        self.logger.error(f"Could not find ADAPTIVE rule in output: {out[:200]}")
        return None


    def enable_steering(self) -> bool:
        """Enable adaptive steering rule (route LATENCY_SENSITIVE to alternate WAN)"""
        self.logger.info(f"Enabling steering rule: {self.config.mangle_rule_comment}")

        rc, _, _ = self.client.run_cmd(
            f'/ip firewall mangle enable [find comment~"{self.config.mangle_rule_comment}"]',
            timeout=10  # State change operation
        )

        if rc != 0:
            self.logger.error("Failed to enable steering rule")
            return False

        # Verify with retry (W6 fix: handle RouterOS processing delay)
        if verify_with_retry(
            self.get_rule_status,
            expected_result=True,
            max_retries=3,
            initial_delay=0.1,
            backoff_factor=2.0,
            logger=self.logger,
            operation_name="steering rule enable verification"
        ):
            self.logger.info("Steering rule enabled and verified")
            return True
        else:
            self.logger.error("Steering rule enable verification failed after retries")
            return False

    def disable_steering(self) -> bool:
        """Disable adaptive steering rule (all traffic uses default routing)"""
        self.logger.info(f"Disabling steering rule: {self.config.mangle_rule_comment}")

        rc, _, _ = self.client.run_cmd(
            f'/ip firewall mangle disable [find comment~"{self.config.mangle_rule_comment}"]',
            timeout=10  # State change operation
        )

        if rc != 0:
            self.logger.error("Failed to disable steering rule")
            return False

        # Verify with retry (W6 fix: handle RouterOS processing delay)
        if verify_with_retry(
            self.get_rule_status,
            expected_result=False,
            max_retries=3,
            initial_delay=0.1,
            backoff_factor=2.0,
            logger=self.logger,
            operation_name="steering rule disable verification"
        ):
            self.logger.info("Steering rule disabled and verified")
            return True
        else:
            self.logger.error("Steering rule disable verification failed after retries")
            return False


# Note: RTTMeasurement class is now unified in rtt_measurement.py
# This module imports it from there


# =============================================================================
# BASELINE RTT LOADER
# =============================================================================

class BaselineLoader:
    """Load baseline RTT from autorate state file"""

    def __init__(self, config: SteeringConfig, logger: logging.Logger):
        self.config = config
        self.logger = logger

    def load_baseline_rtt(self) -> float | None:
        """
        Load baseline RTT from primary WAN autorate state file
        Reads ewma.baseline_rtt from autorate_continuous state
        Returns None if unavailable (daemon will use config fallback)
        """
        if not self.config.primary_state_file.exists():
            self.logger.warning(f"Primary WAN state file not found: {self.config.primary_state_file}")
            return None

        try:
            with open(self.config.primary_state_file) as f:
                state = json.load(f)

            # autorate_continuous format: state['ewma']['baseline_rtt']
            if 'ewma' in state and 'baseline_rtt' in state['ewma']:
                baseline_rtt = float(state['ewma']['baseline_rtt'])

                # Sanity check using configured bounds (C4 fix: prevents malicious baseline attacks)
                # Default range: 10-60ms (typical home ISP latencies)
                if self.config.baseline_rtt_min <= baseline_rtt <= self.config.baseline_rtt_max:
                    self.logger.debug(f"Loaded baseline RTT from autorate state: {baseline_rtt:.2f}ms")
                    return baseline_rtt
                else:
                    self.logger.warning(
                        f"Baseline RTT out of bounds [{self.config.baseline_rtt_min:.1f}-{self.config.baseline_rtt_max:.1f}ms]: "
                        f"{baseline_rtt:.2f}ms, ignoring (possible autorate compromise)"
                    )
                    return None
            else:
                self.logger.warning("Baseline RTT not found in autorate state file")
                return None

        except Exception as e:
            self.logger.error(f"Failed to load baseline RTT: {e}")
            self.logger.debug(traceback.format_exc())
            return None


# =============================================================================
# STEERING DAEMON
# =============================================================================

class SteeringDaemon:
    """Main steering daemon logic with state machine"""

    def __init__(
        self,
        config: SteeringConfig,
        state: SteeringStateManager,
        router: RouterOSController,
        rtt_measurement: RTTMeasurement,
        baseline_loader: BaselineLoader,
        logger: logging.Logger
    ):
        self.config = config
        self.state_mgr = state
        self.router = router
        self.rtt_measurement = rtt_measurement
        self.baseline_loader = baseline_loader
        self.logger = logger

        # CAKE-aware components (if enabled)
        if self.config.cake_aware:
            self.cake_reader = CakeStatsReader(config, logger)
            self.thresholds = StateThresholds(
                green_rtt=config.green_rtt_ms,
                yellow_rtt=config.yellow_rtt_ms,
                red_rtt=config.red_rtt_ms,
                min_drops_red=config.min_drops_red,
                min_queue_yellow=config.min_queue_yellow,
                min_queue_red=config.min_queue_red,
                red_samples_required=config.red_samples_required,
                green_samples_required=config.green_samples_required
            )
            self.logger.info("CAKE-aware mode ENABLED - using three-state congestion model")
        else:
            self.cake_reader = None
            self.thresholds = None
            self.logger.info("Legacy RTT-only mode - CAKE-aware disabled")

    def _is_current_state_good(self, current_state: str) -> bool:
        """Check if current state represents 'good' (supports both legacy and config-driven names).

        Args:
            current_state: The current state string to check

        Returns:
            True if state is "good", False otherwise
        """
        return current_state == self.config.state_good or \
               current_state in ("SPECTRUM_GOOD", "WAN1_GOOD", "WAN2_GOOD")

    def measure_current_rtt(self) -> float | None:
        """Measure current RTT to ping host"""
        return self.rtt_measurement.ping_host(
            self.config.ping_host,
            self.config.ping_count
        )

    def _measure_current_rtt_with_retry(self, max_retries: int = 3) -> float | None:
        """
        Measure current RTT with retry and fallback to history (W7 fix)

        Uses measure_with_retry() utility with fallback to last known RTT from state.

        Args:
            max_retries: Maximum ping attempts

        Returns:
            Current RTT or None if all retries fail and no fallback available
        """
        def fallback_to_history():
            """Fallback to historical RTT data when current measurement fails.

            Uses moving average of last N RTT values as fallback when ping fails.
            Prevents steering disruption during transient measurement failures.

            This is a private implementation detail for measurement resilience (W7 fix).
            Returns the most recent RTT from state history if available.

            Returns:
                float | None: Historical RTT average in ms, or None if no history available
            """
            state = self.state_mgr.state
            if state.get("history_rtt") and len(state["history_rtt"]) > 0:
                last_rtt = state["history_rtt"][-1]
                self.logger.warning(
                    f"Using last known RTT from state: {last_rtt:.1f}ms "
                    f"(ping to {self.config.ping_host} failed after retries)"
                )
                return last_rtt
            self.logger.error(
                "No ping response and no RTT history available - cannot proceed"
            )
            return None

        return measure_with_retry(
            self.measure_current_rtt,
            max_retries=max_retries,
            retry_delay=0.5,
            fallback_func=fallback_to_history,
            logger=self.logger,
            operation_name="ping"
        )

    def update_baseline_rtt(self) -> bool:
        """
        Update baseline RTT from autorate state
        Returns True if successful, False otherwise
        """
        baseline_rtt = self.baseline_loader.load_baseline_rtt()

        if baseline_rtt is not None:
            old_baseline = self.state_mgr.state["baseline_rtt"]
            self.state_mgr.state["baseline_rtt"] = baseline_rtt

            if old_baseline is None:
                self.logger.info(f"Initialized baseline RTT: {baseline_rtt:.2f}ms")
            elif abs(baseline_rtt - old_baseline) > BASELINE_CHANGE_THRESHOLD:
                self.logger.info(f"Baseline RTT updated: {old_baseline:.2f}ms -> {baseline_rtt:.2f}ms")

            return True
        else:
            if self.state_mgr.state["baseline_rtt"] is None:
                self.logger.warning("No baseline RTT available, cannot make steering decisions")
                return False
            else:
                self.logger.debug("Using cached baseline RTT")
                return True

    def calculate_delta(self, current_rtt: float) -> float:
        """Calculate RTT delta (current - baseline)"""
        baseline_rtt = self.state_mgr.state["baseline_rtt"]
        if baseline_rtt is None:
            return 0.0

        delta = current_rtt - baseline_rtt
        return max(0.0, delta)  # Never negative

    def update_state_machine(self, signals: CongestionSignals) -> bool:
        """
        Update state machine based on congestion signals

        Args:
            signals: CongestionSignals containing rtt_delta, drops, queue depth, etc.

        Returns:
            True if routing state changed, False otherwise
        """
        if self.config.cake_aware:
            return self._update_state_machine_cake_aware(signals)
        else:
            return self._update_state_machine_legacy(signals.rtt_delta)

    def _update_state_machine_cake_aware(self, signals: CongestionSignals) -> bool:
        """CAKE-aware three-state logic (GREEN/YELLOW/RED)"""
        state = self.state_mgr.state
        current_state = state["current_state"]

        # Assess current congestion state based on all signals
        assessment = assess_congestion_state(signals, self.thresholds, self.logger)
        state["congestion_state"] = assessment.value  # Store for observability

        state_changed = False
        red_count = state["red_count"]
        good_count = state["good_count"]

        # Check if we're in "good" state (handles both legacy and generic names)
        is_good_state = self._is_current_state_good(current_state)

        if is_good_state:
            # Normalize to config-driven state name
            if current_state != self.config.state_good:
                state["current_state"] = self.config.state_good
                current_state = self.config.state_good

            # Check for RED (requires consecutive samples + CAKE drops)
            if assessment == CongestionState.RED:
                red_count += 1
                good_count = 0
                self.logger.info(
                    f"[{self.config.primary_wan.upper()}_GOOD] [{assessment.value}] {signals} | "
                    f"red_count={red_count}/{self.thresholds.red_samples_required}"
                )

                if red_count >= self.thresholds.red_samples_required:
                    self.logger.warning(
                        f"{self.config.primary_wan.upper()} DEGRADED detected - {signals} (sustained {red_count} samples)"
                    )

                    # Enable steering
                    if self.router.enable_steering():
                        self.state_mgr.log_transition(current_state, self.config.state_degraded)
                        state["current_state"] = self.config.state_degraded
                        red_count = 0
                        state_changed = True
                        # Record transition in metrics
                        if self.config.metrics_enabled:
                            record_steering_transition(
                                self.config.primary_wan, current_state, self.config.state_degraded
                            )
                    else:
                        self.logger.error(f"Failed to enable steering, staying in {self.config.state_good}")

            elif assessment == CongestionState.YELLOW:
                red_count = 0
                self.logger.info(
                    f"[{self.config.primary_wan.upper()}_GOOD] [{assessment.value}] {signals} | early warning, no action"
                )
            else:  # GREEN
                red_count = 0
                self.logger.debug(f"[{self.config.primary_wan.upper()}_GOOD] [{assessment.value}] {signals}")

        else:  # Degraded state
            # Normalize to config-driven state name
            if current_state != self.config.state_degraded:
                state["current_state"] = self.config.state_degraded
                current_state = self.config.state_degraded

            # Check for recovery (requires sustained GREEN)
            if assessment == CongestionState.GREEN:
                good_count += 1
                red_count = 0
                self.logger.info(
                    f"[{self.config.primary_wan.upper()}_DEGRADED] [{assessment.value}] {signals} | "
                    f"good_count={good_count}/{self.thresholds.green_samples_required}"
                )

                if good_count >= self.thresholds.green_samples_required:
                    self.logger.info(
                        f"{self.config.primary_wan.upper()} RECOVERED - {signals} (sustained {good_count} samples)"
                    )

                    # Disable steering
                    if self.router.disable_steering():
                        self.state_mgr.log_transition(current_state, self.config.state_good)
                        state["current_state"] = self.config.state_good
                        good_count = 0
                        state_changed = True
                        # Record transition in metrics
                        if self.config.metrics_enabled:
                            record_steering_transition(
                                self.config.primary_wan, current_state, self.config.state_good
                            )
                    else:
                        self.logger.error(f"Failed to disable steering, staying in {self.config.state_degraded}")

            else:  # YELLOW or RED - stay degraded
                good_count = 0
                self.logger.info(
                    f"[{self.config.primary_wan.upper()}_DEGRADED] [{assessment.value}] {signals} | still degraded"
                )

        # Update counters
        state["red_count"] = red_count
        state["good_count"] = good_count

        return state_changed

    def _update_state_machine_legacy(self, delta: float) -> bool:
        """Legacy RTT-only binary logic (backward compatibility)"""
        state = self.state_mgr.state
        current_state = state["current_state"]
        bad_count = state["bad_count"]
        good_count = state["good_count"]

        state_changed = False

        # Check if we're in "good" state
        is_good_state = self._is_current_state_good(current_state)

        if is_good_state:
            # Normalize state name
            if current_state != self.config.state_good:
                state["current_state"] = self.config.state_good
                current_state = self.config.state_good

            if delta > self.config.bad_threshold_ms:
                bad_count += 1
                good_count = 0
                self.logger.debug(
                    f"Delta={delta:.1f}ms > threshold={self.config.bad_threshold_ms}ms, "
                    f"bad_count={bad_count}/{self.config.bad_samples}"
                )
            else:
                bad_count = 0

            if bad_count >= self.config.bad_samples:
                self.logger.warning(
                    f"{self.config.primary_wan.upper()} DEGRADED detected (delta={delta:.1f}ms sustained for {bad_count} samples)"
                )

                if self.router.enable_steering():
                    self.state_mgr.log_transition(current_state, self.config.state_degraded)
                    state["current_state"] = self.config.state_degraded
                    bad_count = 0
                    state_changed = True
                else:
                    self.logger.error(f"Failed to enable steering, staying in {self.config.state_good}")

        else:  # Degraded state
            # Normalize state name
            if current_state != self.config.state_degraded:
                state["current_state"] = self.config.state_degraded
                current_state = self.config.state_degraded

            if delta < self.config.recovery_threshold_ms:
                good_count += 1
                bad_count = 0
                self.logger.debug(
                    f"Delta={delta:.1f}ms < threshold={self.config.recovery_threshold_ms}ms, "
                    f"good_count={good_count}/{self.config.good_samples}"
                )
            else:
                good_count = 0

            if good_count >= self.config.good_samples:
                self.logger.info(
                    f"{self.config.primary_wan.upper()} RECOVERED (delta={delta:.1f}ms sustained for {good_count} samples)"
                )

                if self.router.disable_steering():
                    self.state_mgr.log_transition(current_state, self.config.state_good)
                    state["current_state"] = self.config.state_good
                    good_count = 0
                    state_changed = True
                else:
                    self.logger.error(f"Failed to disable steering, staying in {self.config.state_degraded}")

        state["bad_count"] = bad_count
        state["good_count"] = good_count

        return state_changed

    def run_cycle(self) -> bool:
        """
        Execute one steering cycle
        Returns True on success, False on failure
        """
        state = self.state_mgr.state

        # Update baseline RTT from autorate state
        if not self.update_baseline_rtt():
            self.logger.error("Cannot proceed without baseline RTT")
            return False

        baseline_rtt = state["baseline_rtt"]

        # === CAKE Stats Collection (if enabled) ===
        cake_drops = 0
        queued_packets = 0

        if self.config.cake_aware and self.cake_reader:
            # Read CAKE statistics (using delta math, no resets needed)
            stats = self.cake_reader.read_stats(self.config.primary_download_queue)
            if stats:
                cake_drops = stats.dropped
                queued_packets = stats.queued_packets

                # Reset failure counter on successful read
                state["cake_read_failures"] = 0

                # Update history (W4 fix: deques handle automatic eviction)
                state["cake_drops_history"].append(cake_drops)
                state["queue_depth_history"].append(queued_packets)
                # No manual trim needed - deques with maxlen automatically evict oldest elements
            else:
                # W8 fix: Track consecutive CAKE read failures
                state["cake_read_failures"] += 1
                if state["cake_read_failures"] == 1:
                    # First failure - log warning
                    self.logger.warning(
                        f"CAKE stats read failed for {self.config.primary_download_queue}, "
                        f"using RTT-only decisions (failure {state['cake_read_failures']})"
                    )
                elif state["cake_read_failures"] >= 3:
                    # Multiple failures - enter degraded mode
                    if state["cake_read_failures"] == 3:
                        self.logger.error(
                            f"CAKE stats unavailable after {state['cake_read_failures']} attempts, "
                            f"entering degraded mode (RTT-only decisions)"
                        )
                    # cake_drops=0 and queued_packets=0 signal RTT-only mode downstream

        # === RTT Measurement ===
        # W7 fix: Retry ping up to 3 times, with fallback to last known RTT
        current_rtt = self._measure_current_rtt_with_retry()
        if current_rtt is None:
            self.logger.warning("Ping failed after retries and no fallback available, skipping cycle")
            return False

        # Calculate delta
        delta = self.calculate_delta(current_rtt)

        # === EWMA Smoothing (if CAKE-aware) ===
        if self.config.cake_aware:
            rtt_delta_ewma = ewma_update(
                state["rtt_delta_ewma"],
                delta,
                self.config.rtt_ewma_alpha
            )
            state["rtt_delta_ewma"] = rtt_delta_ewma

            queue_ewma = ewma_update(
                state["queue_ewma"],
                float(queued_packets),
                self.config.queue_ewma_alpha
            )
            state["queue_ewma"] = queue_ewma
        else:
            rtt_delta_ewma = delta

        # Add to history
        self.state_mgr.add_measurement(current_rtt, delta)

        # === Build Congestion Signals ===
        signals = CongestionSignals(
            rtt_delta=delta,
            rtt_delta_ewma=rtt_delta_ewma,
            cake_drops=cake_drops,
            queued_packets=queued_packets,
            baseline_rtt=baseline_rtt
        )

        # === Log Measurement ===
        wan_name = self.config.primary_wan.upper()
        if self.config.cake_aware:
            self.logger.info(
                f"[{wan_name}_{state['current_state'].split('_')[-1]}] {signals} | "
                f"congestion={state.get('congestion_state', 'N/A')}"
            )
        else:
            self.logger.info(
                f"[{wan_name}_{state['current_state'].split('_')[-1]}] "
                f"RTT={current_rtt:.1f}ms, baseline={baseline_rtt:.1f}ms, delta={delta:.1f}ms | "
                f"bad_count={state['bad_count']}/{self.config.bad_samples}, "
                f"good_count={state['good_count']}/{self.config.good_samples}"
            )

        # === Update State Machine ===
        state_changed = self.update_state_machine(signals)

        if state_changed:
            self.logger.info(
                f"State transition: {state['current_state']} "
                f"(last transition: {state.get('last_transition_time', 'never')})"
            )

        # Save state
        self.state_mgr.save()

        # Record steering metrics if enabled
        if self.config.metrics_enabled:
            steering_enabled = state["current_state"] == self.config.state_degraded
            congestion_state = state.get("congestion_state", "GREEN")
            record_steering_state(
                primary_wan=self.config.primary_wan,
                steering_enabled=steering_enabled,
                congestion_state=congestion_state,
            )

        return True


# =============================================================================
# MAIN
# =============================================================================

def main():
    """Main entry point for adaptive multi-WAN steering daemon.

    Runs continuous steering control loop that monitors congestion state from
    autorate daemons and makes routing decisions to steer latency-sensitive
    traffic between WANs. Uses hysteresis-based state machine to prevent
    flapping while ensuring responsive failover.

    The daemon performs these operations in each cycle:
    - Checks congestion state from autorate state files
    - Measures current RTT to detect network issues
    - Updates baseline RTT from autorate measurements
    - Applies hysteresis logic to determine steering state
    - Enables/disables routing rule when state transitions occur
    - Persists steering history and state to survive restarts

    Operational modes:
    - Normal: Continuous daemon mode with cycle-based control loop
    - Reset: Clears state file and disables steering (--reset flag)

    Signal handling:
    - SIGTERM/SIGINT: Graceful shutdown with state save and lock cleanup
    - Uses event-based sleep for immediate shutdown response

    Optional systemd watchdog support:
    - Notifies systemd on each successful cycle
    - Stops watchdog after 3 consecutive failures (triggers restart)
    - Reports degraded status when unhealthy

    Returns:
        int: Exit code - 0 for success, 1 for error, 130 for interrupt
    """
    parser = argparse.ArgumentParser(
        description="Adaptive Multi-WAN Steering Daemon"
    )
    parser.add_argument("--config", required=True, help="Path to config YAML file")
    parser.add_argument("--reset", action="store_true", help="Reset state and disable steering")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    args = parser.parse_args()

    # Register signal handlers early (W5: Graceful Shutdown)
    # This must be done before any long-running operations
    register_signal_handlers()

    # Load config
    try:
        config = SteeringConfig(args.config)
    except Exception as e:
        print(f"ERROR: Failed to load config: {e}")
        traceback.print_exc()
        return 1

    # Setup logging
    logger = setup_logging(config, "steering", args.debug)
    logger.info("=" * 60)
    logger.info(f"Steering Daemon - Primary: {config.primary_wan}, Alternate: {config.alternate_wan}")
    logger.info("=" * 60)

    # Check for early shutdown (signal received during startup)
    if is_shutdown_requested():
        logger.info("Shutdown requested during startup, exiting gracefully")
        return 0

    # Initialize components
    schema = create_steering_state_schema(config)
    state_mgr = SteeringStateManager(
        config.state_file, schema, logger,
        history_maxlen=config.history_size
    )
    state_mgr.load()
    router = RouterOSController(config, logger)
    # Use unified RTTMeasurement with MEDIAN aggregation and total timeout
    rtt_measurement = RTTMeasurement(
        logger,
        timeout_ping=config.timeout_ping,
        timeout_total=config.timeout_ping_total,
        aggregation_strategy=RTTAggregationStrategy.MEDIAN,
        log_sample_stats=False  # Steering only uses single sample (count=1)
    )
    baseline_loader = BaselineLoader(config, logger)

    # Handle reset
    if args.reset:
        logger.info("RESET requested")
        state_mgr.reset()
        router.disable_steering()
        logger.info("Reset complete")
        return 0

    # Acquire lock at startup (held for daemon lifetime)
    if not validate_and_acquire_lock(config.lock_file, config.lock_timeout, logger):
        logger.error("Another instance is running, refusing to start")
        return 1

    # Register emergency cleanup handler for lock file
    def emergency_lock_cleanup():
        """Emergency cleanup - runs via atexit if finally block doesn't complete."""
        try:
            config.lock_file.unlink(missing_ok=True)
        except OSError:
            pass  # Best effort - nothing we can do

    atexit.register(emergency_lock_cleanup)

    # Check for shutdown before starting daemon
    if is_shutdown_requested():
        logger.info("Shutdown requested before startup, exiting gracefully")
        config.lock_file.unlink(missing_ok=True)
        return 0

    # Create daemon
    daemon = SteeringDaemon(
        config, state_mgr, router,
        rtt_measurement, baseline_loader, logger
    )

    # Daemon mode variables
    consecutive_failures = 0
    MAX_CONSECUTIVE_FAILURES = 3
    watchdog_enabled = True

    logger.info(f"Starting daemon mode with {config.measurement_interval}s cycle interval")
    if is_systemd_available():
        logger.info("Systemd watchdog support enabled")

    # Get shutdown event for direct access in timed waits
    shutdown_event = get_shutdown_event()

    try:
        # Main event loop - runs continuously until shutdown signal
        while not shutdown_event.is_set():
            cycle_start = time.monotonic()

            # Run one cycle
            cycle_success = daemon.run_cycle()

            elapsed = time.monotonic() - cycle_start

            # Track consecutive failures for watchdog
            if cycle_success:
                consecutive_failures = 0
            else:
                consecutive_failures += 1
                logger.warning(f"Cycle failed ({consecutive_failures}/{MAX_CONSECUTIVE_FAILURES})")

                # Stop watchdog notifications if sustained failures
                if consecutive_failures >= MAX_CONSECUTIVE_FAILURES and watchdog_enabled:
                    watchdog_enabled = False
                    logger.error(
                        f"Sustained failure: {consecutive_failures} consecutive failed cycles. "
                        f"Stopping watchdog - systemd will terminate us."
                    )
                    notify_degraded("consecutive failures exceeded threshold")

            # Notify systemd watchdog ONLY if healthy
            if watchdog_enabled and cycle_success:
                notify_watchdog()
            elif not watchdog_enabled:
                notify_degraded(f"{consecutive_failures} consecutive failures")

            # Sleep for remainder of cycle interval (interruptible)
            sleep_time = max(0, config.measurement_interval - elapsed)
            if sleep_time > 0 and not shutdown_event.is_set():
                shutdown_event.wait(timeout=sleep_time)

        logger.info("Shutdown signal received, exiting gracefully")
        return 0

    except KeyboardInterrupt:
        # KeyboardInterrupt may bypass signal handler in some cases
        logger.info("Interrupted by user (KeyboardInterrupt)")
        return 130
    except Exception as e:
        # Check if exception was due to shutdown
        if is_shutdown_requested():
            logger.info("Exception during shutdown, exiting gracefully")
            return 0
        logger.error(f"Unhandled exception: {e}")
        logger.error(traceback.format_exc())
        return 1
    finally:
        # Cleanup: release lock file
        logger.info("Shutting down daemon...")
        if config.lock_file.exists():
            config.lock_file.unlink()
            logger.debug(f"Lock released: {config.lock_file}")
        logger.info("Shutdown complete")


if __name__ == "__main__":
    sys.exit(main())
