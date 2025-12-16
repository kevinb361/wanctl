#!/usr/bin/env python3
"""
Adaptive Dual-WAN Steering Daemon

Routes latency-sensitive traffic to ATT WAN when Spectrum degrades.
Uses three-layer architecture:
  Layer 1 (DSCP): EF/AF31 = latency-sensitive
  Layer 2 (Connection-marks): LATENCY_SENSITIVE mark drives routing
  Layer 3 (Address-lists): Surgical overrides via FORCE_OUT_ATT

State machine:
  SPECTRUM_GOOD: All traffic → Spectrum (default)
  SPECTRUM_DEGRADED: Latency-sensitive → ATT, bulk stays on Spectrum

Decision logic:
  delta = current_rtt - baseline_rtt
  Hysteresis prevents flapping (asymmetric streak counting)

Designed to run every 2 seconds via systemd timer (one-shot execution).
Colocated with autorate_continuous on cake-spectrum container.
"""

import argparse
import datetime
import json
import logging
import os
import re
import statistics
import subprocess
import sys
import time
import traceback
from pathlib import Path
from typing import Dict, Any, Optional, Tuple

try:
    import yaml
except ImportError:
    print("ERROR: PyYAML not installed. Run: pip3 install --user PyYAML")
    sys.exit(1)

# Import CAKE-aware modules
try:
    from cake_stats import CakeStatsReader, CakeStats, CongestionSignals
    from congestion_assessment import (
        CongestionState,
        StateThresholds,
        assess_congestion_state,
        ewma_update
    )
    CAKE_AWARE_AVAILABLE = True
except ImportError as e:
    print(f"WARNING: CAKE-aware modules not found: {e}")
    print("Falling back to legacy RTT-only mode")
    CAKE_AWARE_AVAILABLE = False


# =============================================================================
# CONFIGURATION
# =============================================================================

class Config:
    """Configuration loaded from YAML"""
    def __init__(self, config_path: str):
        with open(config_path, 'r') as f:
            data = yaml.safe_load(f)

        self.wan_name = data['wan_name']

        # CAKE state sources (baseline RTT)
        self.spectrum_state_file = Path(data['cake_state_sources']['spectrum'])
        self.att_state_file = data['cake_state_sources'].get('att')  # Optional, future use

        # RouterOS connection
        self.router_host = data['router']['host']
        self.router_user = data['router']['user']
        self.ssh_key = data['router']['ssh_key']

        # Mangle rule to toggle
        self.mangle_rule_comment = data['mangle_rule']['comment']

        # RTT measurement
        self.measurement_interval = data['measurement']['interval_seconds']
        self.ping_host = data['measurement']['ping_host']
        self.ping_count = data['measurement']['ping_count']

        # CAKE queue names (for statistics polling)
        cake_queues = data.get('cake_queues', {})
        self.spectrum_download_queue = cake_queues.get('spectrum_download', 'WAN-Download-Spectrum')
        self.spectrum_upload_queue = cake_queues.get('spectrum_upload', 'WAN-Upload-Spectrum')

        # Operational mode
        mode = data.get('mode', {})
        self.cake_aware = mode.get('cake_aware', False) and CAKE_AWARE_AVAILABLE
        self.reset_counters = mode.get('reset_counters', True)
        self.enable_yellow_state = mode.get('enable_yellow_state', True)

        # State machine thresholds
        thresholds = data['thresholds']

        # Legacy RTT-only thresholds (backward compatibility)
        self.bad_threshold_ms = thresholds.get('bad_threshold_ms', 25.0)
        self.recovery_threshold_ms = thresholds.get('recovery_threshold_ms', 12.0)
        self.bad_samples = thresholds.get('bad_samples', 8)
        self.good_samples = thresholds.get('good_samples', 15)

        # CAKE-aware thresholds (three-state model)
        self.green_rtt_ms = thresholds.get('green_rtt_ms', 5.0)
        self.yellow_rtt_ms = thresholds.get('yellow_rtt_ms', 15.0)
        self.red_rtt_ms = thresholds.get('red_rtt_ms', 15.0)
        self.min_drops_red = thresholds.get('min_drops_red', 1)
        self.min_queue_yellow = thresholds.get('min_queue_yellow', 10)
        self.min_queue_red = thresholds.get('min_queue_red', 50)
        self.rtt_ewma_alpha = thresholds.get('rtt_ewma_alpha', 0.3)
        self.queue_ewma_alpha = thresholds.get('queue_ewma_alpha', 0.4)
        self.red_samples_required = thresholds.get('red_samples_required', 2)
        self.green_samples_required = thresholds.get('green_samples_required', 15)

        # State persistence
        self.state_file = Path(data['state']['file'])
        self.history_size = data['state']['history_size']

        # Logging
        self.main_log = data['logging']['main_log']
        self.debug_log = data['logging']['debug_log']
        self.log_cake_stats = data['logging'].get('log_cake_stats', True)

        # Lock file
        self.lock_file = Path(data['lock_file'])
        self.lock_timeout = data['lock_timeout']

        # Router dict for CakeStatsReader
        self.router = {
            'host': self.router_host,
            'user': self.router_user,
            'ssh_key': self.ssh_key
        }


# =============================================================================
# LOGGING SETUP
# =============================================================================

def setup_logging(config: Config, debug: bool) -> logging.Logger:
    """Setup logging with file and optional console output"""
    logger = logging.getLogger(f"wan_steering_{config.wan_name.lower()}")

    if logger.handlers:
        return logger

    logger.setLevel(logging.DEBUG)

    # Ensure log directories exist
    for path in (config.main_log, config.debug_log):
        d = os.path.dirname(path)
        if d and not os.path.isdir(d):
            os.makedirs(d, exist_ok=True)

    # Main log - INFO level
    fh = logging.FileHandler(config.main_log)
    fh.setLevel(logging.INFO)
    fh.setFormatter(logging.Formatter(
        f"%(asctime)s [{config.wan_name}] [%(levelname)s] %(message)s"
    ))
    logger.addHandler(fh)

    # Debug log and console - DEBUG level
    if debug:
        dfh = logging.FileHandler(config.debug_log)
        dfh.setLevel(logging.DEBUG)
        dfh.setFormatter(logging.Formatter(
            f"%(asctime)s [{config.wan_name}] [%(levelname)s] %(message)s"
        ))
        logger.addHandler(dfh)

        ch = logging.StreamHandler()
        ch.setLevel(logging.DEBUG)
        ch.setFormatter(logging.Formatter(
            f"%(asctime)s [{config.wan_name}] [%(levelname)s] %(message)s"
        ))
        logger.addHandler(ch)

    return logger


# =============================================================================
# LOCK FILE MANAGEMENT
# =============================================================================

class LockFile:
    """Context manager for lock file to prevent concurrent execution"""
    def __init__(self, lock_path: Path, timeout: int, logger: logging.Logger):
        self.lock_path = lock_path
        self.timeout = timeout
        self.logger = logger

    def __enter__(self):
        if self.lock_path.exists():
            age = time.time() - self.lock_path.stat().st_mtime
            if age < self.timeout:
                self.logger.warning(
                    f"Lock file exists and is recent ({age:.1f}s old). "
                    "Another instance may be running. Exiting."
                )
                sys.exit(0)
            else:
                self.logger.warning(
                    f"Stale lock file found ({age:.1f}s old). Removing."
                )
                self.lock_path.unlink()

        self.lock_path.touch()
        self.logger.debug(f"Lock acquired: {self.lock_path}")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.lock_path.exists():
            self.lock_path.unlink()
            self.logger.debug(f"Lock released: {self.lock_path}")


# =============================================================================
# STATE MANAGEMENT
# =============================================================================

class SteeringState:
    """Manages state persistence with measurement history and streak counters"""
    def __init__(self, config: Config, logger: logging.Logger):
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

        # Initial state
        return {
            "current_state": "SPECTRUM_GOOD",
            "bad_count": 0,
            "good_count": 0,
            "baseline_rtt": None,  # Will be loaded from CAKE state
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
            "current_state": "SPECTRUM_GOOD",
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

        # Validate state value
        if state["current_state"] not in ("SPECTRUM_GOOD", "SPECTRUM_DEGRADED"):
            self.logger.warning(f"Invalid state '{state['current_state']}', resetting to SPECTRUM_GOOD")
            state["current_state"] = "SPECTRUM_GOOD"

        # Validate congestion state
        if state.get("congestion_state") not in ("GREEN", "YELLOW", "RED"):
            state["congestion_state"] = "GREEN"

        # Ensure counts are non-negative integers
        state["bad_count"] = max(0, int(state.get("bad_count", 0)))
        state["good_count"] = max(0, int(state.get("good_count", 0)))
        state["red_count"] = max(0, int(state.get("red_count", 0)))

        return state

    def save(self):
        """Save state to file"""
        try:
            # Ensure parent directory exists
            self.config.state_file.parent.mkdir(parents=True, exist_ok=True)

            with open(self.config.state_file, 'w') as f:
                json.dump(self.state, f, indent=2)
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
        if len(self.state["transitions"]) > 50:
            self.state["transitions"] = self.state["transitions"][-50:]

    def reset(self):
        """Reset state to initial values"""
        self.logger.info("Resetting state")
        self.state = {
            "current_state": "SPECTRUM_GOOD",
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
    def __init__(self, config: Config, logger: logging.Logger):
        self.config = config
        self.logger = logger

    def _run_cmd(self, cmd: str, capture: bool = False) -> Tuple[int, str, str]:
        """Execute RouterOS command via SSH"""
        args = [
            "ssh", "-i", self.config.ssh_key,
            "-o", "StrictHostKeyChecking=no",
            f"{self.config.router_user}@{self.config.router_host}",
            cmd
        ]

        self.logger.debug(f"RouterOS command: {cmd}")

        try:
            if capture:
                res = subprocess.run(
                    args, text=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    timeout=30
                )
                self.logger.debug(f"RouterOS stdout: {res.stdout}")
                return res.returncode, res.stdout, res.stderr
            else:
                res = subprocess.run(args, text=True, timeout=30)
                return res.returncode, "", ""
        except subprocess.TimeoutExpired:
            self.logger.error("RouterOS command timeout")
            return 1, "", "Timeout"
        except Exception as e:
            self.logger.error(f"RouterOS SSH error: {e}")
            self.logger.debug(traceback.format_exc())
            return 1, "", str(e)

    def get_rule_status(self) -> Optional[bool]:
        """
        Check if adaptive steering rule is enabled
        Returns: True if enabled, False if disabled, None on error
        """
        rc, out, _ = self._run_cmd(
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
        """Enable adaptive steering rule (route LATENCY_SENSITIVE to ATT)"""
        self.logger.info("Enabling adaptive steering rule")

        rc, _, _ = self._run_cmd(
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
        self.logger.info("Disabling adaptive steering rule")

        rc, _, _ = self._run_cmd(
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
    def __init__(self, config: Config, logger: logging.Logger):
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
                except:
                    pass
        return rtts

    def ping_host(self, host: str, count: int) -> Optional[float]:
        """
        Ping host and return median RTT in milliseconds
        Returns None on failure
        """
        cmd = ["ping", "-c", str(count), "-W", "2", host]

        try:
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=10
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
    """Load baseline RTT from CAKE state file"""
    def __init__(self, config: Config, logger: logging.Logger):
        self.config = config
        self.logger = logger

    def load_baseline_rtt(self) -> Optional[float]:
        """
        Load baseline RTT from Spectrum CAKE state file
        Reads ewma.baseline_rtt from autorate_continuous state
        Returns None if unavailable (daemon will use config fallback)
        """
        if not self.config.spectrum_state_file.exists():
            self.logger.warning(f"Spectrum state file not found: {self.config.spectrum_state_file}")
            return None

        try:
            with open(self.config.spectrum_state_file, 'r') as f:
                state = json.load(f)

            # autorate_continuous format: state['ewma']['baseline_rtt']
            if 'ewma' in state and 'baseline_rtt' in state['ewma']:
                baseline_rtt = float(state['ewma']['baseline_rtt'])

                # Sanity check (typical range: 5-100ms)
                if 5.0 <= baseline_rtt <= 100.0:
                    self.logger.debug(f"Loaded baseline RTT from CAKE state: {baseline_rtt:.2f}ms")
                    return baseline_rtt
                else:
                    self.logger.warning(f"Baseline RTT out of range: {baseline_rtt:.2f}ms, ignoring")
                    return None
            else:
                self.logger.warning("Baseline RTT not found in CAKE state file")
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
        config: Config,
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
        Update baseline RTT from CAKE state
        Returns True if successful, False otherwise
        """
        baseline_rtt = self.baseline_loader.load_baseline_rtt()

        if baseline_rtt is not None:
            old_baseline = self.state_mgr.state["baseline_rtt"]
            self.state_mgr.state["baseline_rtt"] = baseline_rtt

            if old_baseline is None:
                self.logger.info(f"Initialized baseline RTT: {baseline_rtt:.2f}ms")
            elif abs(baseline_rtt - old_baseline) > 5.0:
                self.logger.info(f"Baseline RTT updated: {old_baseline:.2f}ms → {baseline_rtt:.2f}ms")

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
        state = self.state_mgr.state

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

        if current_state == "SPECTRUM_GOOD":
            # Check for RED (requires consecutive samples + CAKE drops)
            if assessment == CongestionState.RED:
                red_count += 1
                good_count = 0
                self.logger.info(
                    f"[{assessment.value}] {signals} | red_count={red_count}/{self.thresholds.red_samples_required}"
                )

                if red_count >= self.thresholds.red_samples_required:
                    self.logger.warning(
                        f"Spectrum DEGRADED detected - {signals} (sustained {red_count} samples)"
                    )

                    # Enable steering
                    if self.router.enable_steering():
                        self.state_mgr.log_transition(current_state, "SPECTRUM_DEGRADED")
                        state["current_state"] = "SPECTRUM_DEGRADED"
                        red_count = 0
                        state_changed = True
                    else:
                        self.logger.error("Failed to enable steering, staying in SPECTRUM_GOOD")

            elif assessment == CongestionState.YELLOW:
                red_count = 0
                self.logger.info(f"[{assessment.value}] {signals} | early warning, no action")
            else:  # GREEN
                red_count = 0
                self.logger.debug(f"[{assessment.value}] {signals}")

        elif current_state == "SPECTRUM_DEGRADED":
            # Check for recovery (requires sustained GREEN)
            if assessment == CongestionState.GREEN:
                good_count += 1
                red_count = 0
                self.logger.info(
                    f"[{assessment.value}] {signals} | good_count={good_count}/{self.thresholds.green_samples_required}"
                )

                if good_count >= self.thresholds.green_samples_required:
                    self.logger.info(
                        f"Spectrum RECOVERED - {signals} (sustained {good_count} samples)"
                    )

                    # Disable steering
                    if self.router.disable_steering():
                        self.state_mgr.log_transition(current_state, "SPECTRUM_GOOD")
                        state["current_state"] = "SPECTRUM_GOOD"
                        good_count = 0
                        state_changed = True
                    else:
                        self.logger.error("Failed to disable steering, staying in SPECTRUM_DEGRADED")

            else:  # YELLOW or RED - stay degraded
                good_count = 0
                self.logger.info(f"[{assessment.value}] {signals} | still degraded")

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

        if current_state == "SPECTRUM_GOOD":
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
                    f"Spectrum DEGRADED detected (delta={delta:.1f}ms sustained for {bad_count} samples)"
                )

                if self.router.enable_steering():
                    self.state_mgr.log_transition(current_state, "SPECTRUM_DEGRADED")
                    state["current_state"] = "SPECTRUM_DEGRADED"
                    bad_count = 0
                    state_changed = True
                else:
                    self.logger.error("Failed to enable steering, staying in SPECTRUM_GOOD")

        elif current_state == "SPECTRUM_DEGRADED":
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
                    f"Spectrum RECOVERED (delta={delta:.1f}ms sustained for {good_count} samples)"
                )

                if self.router.disable_steering():
                    self.state_mgr.log_transition(current_state, "SPECTRUM_GOOD")
                    state["current_state"] = "SPECTRUM_GOOD"
                    good_count = 0
                    state_changed = True
                else:
                    self.logger.error("Failed to disable steering, staying in SPECTRUM_DEGRADED")

        state["bad_count"] = bad_count
        state["good_count"] = good_count

        return state_changed

    def run_cycle(self) -> bool:
        """
        Execute one steering cycle
        Returns True on success, False on failure
        """
        state = self.state_mgr.state

        # Update baseline RTT from CAKE state
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
                self.cake_reader.reset_counters(self.config.spectrum_download_queue)

            # Read CAKE statistics
            stats = self.cake_reader.read_stats(self.config.spectrum_download_queue)
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
        if self.config.cake_aware:
            self.logger.info(
                f"[{state['current_state']}] {signals} | "
                f"congestion={state.get('congestion_state', 'N/A')}"
            )
        else:
            self.logger.info(
                f"[{state['current_state']}] "
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
        description="Adaptive Dual-WAN Steering Daemon"
    )
    parser.add_argument("--config", required=True, help="Path to config YAML file")
    parser.add_argument("--reset", action="store_true", help="Reset state and disable steering")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    args = parser.parse_args()

    # Load config
    try:
        config = Config(args.config)
    except Exception as e:
        print(f"ERROR: Failed to load config: {e}")
        traceback.print_exc()
        return 1

    # Setup logging
    logger = setup_logging(config, args.debug)
    logger.info("=" * 60)
    logger.info(f"WAN Steering Daemon - {config.wan_name}")
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

    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        return 130
    except Exception as e:
        logger.error(f"Unhandled exception: {e}")
        logger.error(traceback.format_exc())
        return 1


if __name__ == "__main__":
    sys.exit(main())
