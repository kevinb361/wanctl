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
import datetime
import json
import logging
import statistics
import subprocess
import sys
import traceback
from pathlib import Path
from typing import Any, Dict, Optional

from ..config_base import BaseConfig
from ..lockfile import LockFile, LockAcquisitionError
from ..logging_utils import setup_logging
from ..routeros_ssh import RouterOSSSH
from ..state_utils import atomic_write_json

from .cake_stats import CakeStatsReader, CongestionSignals
from .congestion_assessment import (
    CongestionState,
    StateThresholds,
    assess_congestion_state,
    ewma_update
)


# =============================================================================
# CONSTANTS
# =============================================================================

# Default timeout values (seconds)
DEFAULT_SSH_TIMEOUT = 30
DEFAULT_PING_TOTAL_TIMEOUT = 10

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
MAX_HISTORY_SAMPLES = 60              # Maximum samples in history (2 minutes at 2s intervals)
ASSESSMENT_INTERVAL_SECONDS = 2.0     # Time between assessments

# Baseline RTT sanity bounds (milliseconds)
MIN_SANE_BASELINE_RTT = 5.0
MAX_SANE_BASELINE_RTT = 100.0
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
         "required": True, "min": 1, "max": 60},
        {"path": "measurement.ping_host", "type": str, "required": True},
        {"path": "measurement.ping_count", "type": int,
         "required": True, "min": 1, "max": 20},

        # State persistence
        {"path": "state.file", "type": str, "required": True},
        {"path": "state.history_size", "type": int,
         "required": True, "min": 1, "max": 1000},

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

        # RTT measurement
        self.measurement_interval = self.data['measurement']['interval_seconds']
        self.ping_host = self.data['measurement']['ping_host']
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
        self.reset_counters = mode.get('reset_counters', True)
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
        self.rtt_ewma_alpha = thresholds.get('rtt_ewma_alpha', DEFAULT_RTT_EWMA_ALPHA)
        self.queue_ewma_alpha = thresholds.get('queue_ewma_alpha', DEFAULT_QUEUE_EWMA_ALPHA)
        self.red_samples_required = thresholds.get('red_samples_required', 2)
        self.green_samples_required = thresholds.get('green_samples_required', DEFAULT_GREEN_SAMPLES_REQUIRED)

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
        self.timeout_ssh_command = timeouts.get('ssh_command', DEFAULT_SSH_TIMEOUT)
        self.timeout_ping = timeouts.get('ping', 2)  # seconds (-W parameter)
        self.timeout_ping_total = timeouts.get('ping_total', DEFAULT_PING_TOTAL_TIMEOUT)

        # Router dict for CakeStatsReader
        self.router = {
            'host': self.router_host,
            'user': self.router_user,
            'ssh_key': self.ssh_key
        }


# =============================================================================
# STATE MANAGEMENT
# =============================================================================

class SteeringState:
    """Manages state persistence with measurement history and streak counters"""

    def __init__(self, config: SteeringConfig, logger: logging.Logger):
        self.config = config
        self.logger = logger
        self.state = self._load()

    def _load(self) -> Dict[str, Any]:
        """Load state from file"""
        if self.config.state_file.exists():
            try:
                with open(self.config.state_file, 'r') as f:
                    state = json.load(f)
                self.logger.debug(f"Loaded state: {state}")
                return self._validate(state)
            except Exception as e:
                self.logger.error(f"Failed to load state: {e}")
                self.logger.debug(traceback.format_exc())

        # Initial state (using config-driven state names)
        return {
            "current_state": self.config.state_good,
            "bad_count": 0,
            "good_count": 0,
            "baseline_rtt": None,  # Will be loaded from autorate state
            "history_rtt": [],
            "history_delta": [],
            "transitions": [],  # Log of state changes
            "last_transition_time": None,
            # CAKE-aware fields
            "rtt_delta_ewma": 0.0,      # Smoothed RTT delta
            "queue_ewma": 0.0,          # Smoothed queue depth
            "cake_drops_history": [],   # Recent drop counts
            "queue_depth_history": [],  # Recent queue depths
            "red_count": 0,             # Consecutive RED samples
            "congestion_state": "GREEN" # GREEN/YELLOW/RED
        }

    def _validate(self, state: Dict) -> Dict:
        """Validate and clean state data"""
        # Ensure required fields
        defaults = {
            "current_state": self.config.state_good,
            "bad_count": 0,
            "good_count": 0,
            "baseline_rtt": None,
            "history_rtt": [],
            "history_delta": [],
            "transitions": [],
            "last_transition_time": None,
            # CAKE-aware fields
            "rtt_delta_ewma": 0.0,
            "queue_ewma": 0.0,
            "cake_drops_history": [],
            "queue_depth_history": [],
            "red_count": 0,
            "congestion_state": "GREEN"
        }

        for key, default_value in defaults.items():
            if key not in state:
                state[key] = default_value

        # Validate state value - handle legacy state names and new generic names
        valid_states = {
            self.config.state_good, self.config.state_degraded,
            # Legacy support for existing state files
            "SPECTRUM_GOOD", "SPECTRUM_DEGRADED",
            "WAN1_GOOD", "WAN1_DEGRADED",
            "WAN2_GOOD", "WAN2_DEGRADED",
        }

        if state["current_state"] not in valid_states:
            self.logger.warning(f"Invalid state '{state['current_state']}', resetting to {self.config.state_good}")
            state["current_state"] = self.config.state_good
        elif state["current_state"] in ("SPECTRUM_GOOD", "WAN1_GOOD", "WAN2_GOOD") and \
             state["current_state"] != self.config.state_good:
            # Migrate legacy state name to new config-driven name
            if "_GOOD" in state["current_state"]:
                state["current_state"] = self.config.state_good
        elif state["current_state"] in ("SPECTRUM_DEGRADED", "WAN1_DEGRADED", "WAN2_DEGRADED") and \
             state["current_state"] != self.config.state_degraded:
            if "_DEGRADED" in state["current_state"]:
                state["current_state"] = self.config.state_degraded

        # Validate congestion state
        if state.get("congestion_state") not in ("GREEN", "YELLOW", "RED"):
            state["congestion_state"] = "GREEN"

        # Ensure counts are non-negative integers
        state["bad_count"] = max(0, int(state.get("bad_count", 0)))
        state["good_count"] = max(0, int(state.get("good_count", 0)))
        state["red_count"] = max(0, int(state.get("red_count", 0)))

        return state

    def save(self):
        """Save state to file atomically"""
        try:
            atomic_write_json(self.config.state_file, self.state)
            self.logger.debug(f"Saved state: {self.state}")
        except Exception as e:
            self.logger.error(f"Failed to save state: {e}")
            self.logger.debug(traceback.format_exc())

    def add_measurement(self, current_rtt: float, delta: float):
        """Add RTT measurement and delta to history"""
        self.state["history_rtt"].append(current_rtt)
        self.state["history_delta"].append(delta)

        # Trim to max size
        if len(self.state["history_rtt"]) > self.config.history_size:
            self.state["history_rtt"] = self.state["history_rtt"][-self.config.history_size:]
        if len(self.state["history_delta"]) > self.config.history_size:
            self.state["history_delta"] = self.state["history_delta"][-self.config.history_size:]

    def log_transition(self, old_state: str, new_state: str):
        """Log a state transition"""
        transition = {
            "timestamp": datetime.datetime.now().isoformat(),
            "from": old_state,
            "to": new_state,
            "bad_count": self.state["bad_count"],
            "good_count": self.state["good_count"]
        }

        self.state["transitions"].append(transition)
        self.state["last_transition_time"] = transition["timestamp"]

        # Keep only last 50 transitions
        if len(self.state["transitions"]) > MAX_TRANSITIONS_HISTORY:
            self.state["transitions"] = self.state["transitions"][-MAX_TRANSITIONS_HISTORY:]

    def reset(self):
        """Reset state to initial values"""
        self.logger.info("Resetting state")
        self.state = {
            "current_state": self.config.state_good,
            "bad_count": 0,
            "good_count": 0,
            "baseline_rtt": None,
            "history_rtt": [],
            "history_delta": [],
            "transitions": [],
            "last_transition_time": None
        }
        self.save()


# =============================================================================
# ROUTEROS INTERFACE
# =============================================================================

class RouterOSController:
    """RouterOS SSH interface to toggle steering rule"""

    def __init__(self, config: SteeringConfig, logger: logging.Logger):
        self.config = config
        self.logger = logger
        self.ssh = RouterOSSSH.from_config(config, logger)

    def get_rule_status(self) -> Optional[bool]:
        """
        Check if adaptive steering rule is enabled
        Returns: True if enabled, False if disabled, None on error
        """
        rc, out, _ = self.ssh.run_cmd(
            f'/ip firewall mangle print where comment~"{self.config.mangle_rule_comment}"',
            capture=True
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

        rc, _, _ = self.ssh.run_cmd(
            f'/ip firewall mangle enable [find comment~"{self.config.mangle_rule_comment}"]'
        )

        if rc != 0:
            self.logger.error("Failed to enable steering rule")
            return False

        # Verify
        status = self.get_rule_status()
        if status is True:
            self.logger.info("Steering rule enabled and verified")
            return True
        else:
            self.logger.error("Steering rule enable verification failed")
            return False

    def disable_steering(self) -> bool:
        """Disable adaptive steering rule (all traffic uses default routing)"""
        self.logger.info(f"Disabling steering rule: {self.config.mangle_rule_comment}")

        rc, _, _ = self.ssh.run_cmd(
            f'/ip firewall mangle disable [find comment~"{self.config.mangle_rule_comment}"]'
        )

        if rc != 0:
            self.logger.error("Failed to disable steering rule")
            return False

        # Verify
        status = self.get_rule_status()
        if status is False:
            self.logger.info("Steering rule disabled and verified")
            return True
        else:
            self.logger.error("Steering rule disable verification failed")
            return False


# =============================================================================
# RTT MEASUREMENT
# =============================================================================

class RTTMeasurement:
    """Measure current RTT via ping"""

    def __init__(self, config: SteeringConfig, logger: logging.Logger):
        self.config = config
        self.logger = logger

    def _parse_ping(self, text: str) -> list:
        """Extract RTT values from ping output"""
        rtts = []
        for line in text.splitlines():
            if "time=" in line:
                try:
                    rtt = float(line.split("time=")[1].split()[0])
                    rtts.append(rtt)
                except (ValueError, IndexError) as e:
                    self.logger.debug(f"Failed to parse RTT from line '{line}': {e}")
                    pass
        return rtts

    def ping_host(self, host: str, count: int) -> Optional[float]:
        """
        Ping host and return median RTT in milliseconds
        Returns None on failure
        """
        cmd = ["ping", "-c", str(count), "-W", str(self.config.timeout_ping), host]

        try:
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=self.config.timeout_ping_total
            )

            if result.returncode != 0:
                self.logger.warning(f"Ping to {host} failed: {result.stderr}")
                return None

            rtts = self._parse_ping(result.stdout)
            if not rtts:
                self.logger.warning(f"No RTT samples from {host}")
                return None

            median_rtt = statistics.median(rtts)
            self.logger.debug(f"Ping {host}: {median_rtt:.2f}ms (median of {len(rtts)} samples)")
            return median_rtt

        except subprocess.TimeoutExpired:
            self.logger.warning(f"Ping to {host} timed out")
            return None
        except Exception as e:
            self.logger.error(f"Ping error: {e}")
            self.logger.debug(traceback.format_exc())
            return None


# =============================================================================
# BASELINE RTT LOADER
# =============================================================================

class BaselineLoader:
    """Load baseline RTT from autorate state file"""

    def __init__(self, config: SteeringConfig, logger: logging.Logger):
        self.config = config
        self.logger = logger

    def load_baseline_rtt(self) -> Optional[float]:
        """
        Load baseline RTT from primary WAN autorate state file
        Reads ewma.baseline_rtt from autorate_continuous state
        Returns None if unavailable (daemon will use config fallback)
        """
        if not self.config.primary_state_file.exists():
            self.logger.warning(f"Primary WAN state file not found: {self.config.primary_state_file}")
            return None

        try:
            with open(self.config.primary_state_file, 'r') as f:
                state = json.load(f)

            # autorate_continuous format: state['ewma']['baseline_rtt']
            if 'ewma' in state and 'baseline_rtt' in state['ewma']:
                baseline_rtt = float(state['ewma']['baseline_rtt'])

                # Sanity check (typical range: 5-100ms)
                if MIN_SANE_BASELINE_RTT <= baseline_rtt <= MAX_SANE_BASELINE_RTT:
                    self.logger.debug(f"Loaded baseline RTT from autorate state: {baseline_rtt:.2f}ms")
                    return baseline_rtt
                else:
                    self.logger.warning(f"Baseline RTT out of range: {baseline_rtt:.2f}ms, ignoring")
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
        state: SteeringState,
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

    def measure_current_rtt(self) -> Optional[float]:
        """Measure current RTT to ping host"""
        return self.rtt_measurement.ping_host(
            self.config.ping_host,
            self.config.ping_count
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
        is_good_state = current_state == self.config.state_good or \
                       current_state in ("SPECTRUM_GOOD", "WAN1_GOOD", "WAN2_GOOD")

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
        is_good_state = current_state == self.config.state_good or \
                       current_state in ("SPECTRUM_GOOD", "WAN1_GOOD", "WAN2_GOOD")

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
            # Reset counters for accurate delta measurement
            if self.config.reset_counters:
                self.cake_reader.reset_counters(self.config.primary_download_queue)

            # Read CAKE statistics
            stats = self.cake_reader.read_stats(self.config.primary_download_queue)
            if stats:
                cake_drops = stats.dropped
                queued_packets = stats.queued_packets

                # Update history
                state["cake_drops_history"].append(cake_drops)
                state["queue_depth_history"].append(queued_packets)

                # Trim history
                if len(state["cake_drops_history"]) > self.config.history_size:
                    state["cake_drops_history"] = state["cake_drops_history"][-self.config.history_size:]
                if len(state["queue_depth_history"]) > self.config.history_size:
                    state["queue_depth_history"] = state["queue_depth_history"][-self.config.history_size:]

        # === RTT Measurement ===
        current_rtt = self.measure_current_rtt()
        if current_rtt is None:
            self.logger.warning("Ping failed, skipping cycle")
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

        return True


# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Adaptive Multi-WAN Steering Daemon"
    )
    parser.add_argument("--config", required=True, help="Path to config YAML file")
    parser.add_argument("--reset", action="store_true", help="Reset state and disable steering")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    args = parser.parse_args()

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

    # Initialize components
    state_mgr = SteeringState(config, logger)
    router = RouterOSController(config, logger)
    rtt_measurement = RTTMeasurement(config, logger)
    baseline_loader = BaselineLoader(config, logger)

    # Handle reset
    if args.reset:
        logger.info("RESET requested")
        state_mgr.reset()
        router.disable_steering()
        logger.info("Reset complete")
        return 0

    # Acquire lock
    try:
        with LockFile(config.lock_file, config.lock_timeout, logger):
            # Create daemon
            daemon = SteeringDaemon(
                config, state_mgr, router,
                rtt_measurement, baseline_loader, logger
            )

            # Run one cycle
            if not daemon.run_cycle():
                logger.error("Cycle failed")
                return 1

            logger.debug("Cycle complete")
            return 0

    except LockAcquisitionError:
        # Another instance is running - this is normal, not an error
        logger.debug("Exiting - another instance is running")
        return 0
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        return 130
    except Exception as e:
        logger.error(f"Unhandled exception: {e}")
        logger.error(traceback.format_exc())
        return 1


if __name__ == "__main__":
    sys.exit(main())
