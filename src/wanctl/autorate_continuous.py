#!/usr/bin/env python3
"""
Continuous CAKE Auto-Tuning System
3-zone controller with EWMA smoothing for responsive congestion control
Expert-tuned for VDSL2, Cable, and Fiber connections

Runs as a persistent daemon with internal 2-second control loop.
"""
import argparse
import concurrent.futures
import datetime
import json
import logging
import signal
import statistics
import subprocess
import time
import traceback
from pathlib import Path
from typing import List, Optional, Tuple

# Optional systemd integration for watchdog support
try:
    from systemd.daemon import notify as sd_notify
    HAVE_SYSTEMD = True
except ImportError:
    HAVE_SYSTEMD = False
    sd_notify = None

from wanctl.config_base import BaseConfig, ConfigValidationError
from wanctl.lockfile import LockFile, LockAcquisitionError
from wanctl.logging_utils import setup_logging
from wanctl.router_client import get_router_client
from wanctl.state_utils import atomic_write_json


# =============================================================================
# CONSTANTS
# =============================================================================

# Baseline RTT update threshold - only update baseline when delta is minimal
# This prevents baseline drift under load (architectural invariant)
DEFAULT_BASELINE_UPDATE_THRESHOLD_MS = 3.0

# Daemon cycle interval - target time between cycle starts (seconds)
# With 2-second cycles and 0.85 factor_down, recovery from 920M to floor takes ~8 cycles = 16 seconds
CYCLE_INTERVAL_SECONDS = 2.0

# Default timeout values (seconds)
DEFAULT_SSH_TIMEOUT = 15
DEFAULT_PING_TIMEOUT = 1

# Default bloat thresholds (milliseconds)
DEFAULT_HARD_RED_BLOAT_MS = 80  # SOFT_RED -> RED transition threshold

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
         "required": True, "min": 0.001, "max": 1.0},
        {"path": "continuous_monitoring.thresholds.alpha_load", "type": float,
         "required": True, "min": 0.01, "max": 1.0},

        # Ping hosts
        {"path": "continuous_monitoring.ping_hosts", "type": list, "required": True},

        # Logging
        {"path": "logging.main_log", "type": str, "required": True},
        {"path": "logging.debug_log", "type": str, "required": True},

        # Lock file
        {"path": "lock_file", "type": str, "required": True},
        {"path": "lock_timeout", "type": int, "required": True, "min": 1, "max": 3600},
    ]

    def _load_specific_fields(self):
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
        if not (self.download_floor_red <= self.download_floor_soft_red <= self.download_floor_yellow
                <= self.download_floor_green <= self.download_ceiling):
            raise ConfigValidationError(
                f"Download floor ordering violation: expected "
                f"floor_red ({self.download_floor_red / MBPS_TO_BPS:.1f}) <= "
                f"floor_soft_red ({self.download_floor_soft_red / MBPS_TO_BPS:.1f}) <= "
                f"floor_yellow ({self.download_floor_yellow / MBPS_TO_BPS:.1f}) <= "
                f"floor_green ({self.download_floor_green / MBPS_TO_BPS:.1f}) <= "
                f"ceiling ({self.download_ceiling / MBPS_TO_BPS:.1f})"
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
        if not (self.upload_floor_red <= self.upload_floor_yellow
                <= self.upload_floor_green <= self.upload_ceiling):
            raise ConfigValidationError(
                f"Upload floor ordering violation: expected "
                f"floor_red ({self.upload_floor_red / MBPS_TO_BPS:.1f}) <= "
                f"floor_yellow ({self.upload_floor_yellow / MBPS_TO_BPS:.1f}) <= "
                f"floor_green ({self.upload_floor_green / MBPS_TO_BPS:.1f}) <= "
                f"ceiling ({self.upload_ceiling / MBPS_TO_BPS:.1f})"
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
        if not (self.target_bloat_ms < self.warn_bloat_ms):
            raise ConfigValidationError(
                f"Threshold ordering violation: target_bloat_ms ({self.target_bloat_ms}) "
                f"must be less than warn_bloat_ms ({self.warn_bloat_ms})"
            )
        if not (self.warn_bloat_ms < self.hard_red_bloat_ms):
            raise ConfigValidationError(
                f"Threshold ordering violation: warn_bloat_ms ({self.warn_bloat_ms}) "
                f"must be less than hard_red_bloat_ms ({self.hard_red_bloat_ms})"
            )

        # Ping configuration
        self.ping_hosts = cm['ping_hosts']
        self.use_median_of_three = cm.get('use_median_of_three', False)

        # Timeouts (with sensible defaults)
        timeouts = self.data.get('timeouts', {})
        self.timeout_ssh_command = timeouts.get('ssh_command', DEFAULT_SSH_TIMEOUT)
        self.timeout_ping = timeouts.get('ping', DEFAULT_PING_TIMEOUT)

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


# =============================================================================
# RTT MEASUREMENT
# =============================================================================

class RTTMeasurement:
    """Lightweight RTT measurement via ping"""
    def __init__(self, logger: logging.Logger, timeout_ping: int = DEFAULT_PING_TIMEOUT):
        self.logger = logger
        self.timeout_ping = timeout_ping

    def ping_host(self, host: str, count: int = 5) -> Optional[float]:
        """
        Ping single host and return average RTT in milliseconds
        Returns None on failure
        """
        try:
            result = subprocess.run(
                ["ping", "-c", str(count), "-W", str(self.timeout_ping), host],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=count + 2
            )

            if result.returncode != 0:
                self.logger.warning(f"Ping to {host} failed (returncode {result.returncode})")
                return None

            # Parse RTT values from output
            rtts = []
            for line in result.stdout.splitlines():
                if "time=" in line:
                    try:
                        rtt_str = line.split("time=")[1].split()[0]
                        # Handle both "12.3" and "12.3 ms" formats
                        rtt = float(rtt_str.replace("ms", ""))
                        rtts.append(rtt)
                    except (ValueError, IndexError) as e:
                        self.logger.debug(f"Failed to parse RTT from line '{line}': {e}")
                        pass

            if not rtts:
                self.logger.warning(f"No RTT samples from {host}")
                return None

            avg_rtt = statistics.mean(rtts)
            self.logger.debug(f"Ping {host}: {avg_rtt:.2f}ms (min={min(rtts):.2f}, max={max(rtts):.2f})")
            return avg_rtt

        except subprocess.TimeoutExpired:
            self.logger.warning(f"Ping to {host} timed out")
            return None
        except Exception as e:
            self.logger.error(f"Ping error to {host}: {e}")
            return None


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

    def adjust(self, baseline_rtt: float, load_rtt: float, target_delta: float, warn_delta: float) -> Tuple[str, int]:
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
            new_rate = max(new_rate, self.floor_red_bps)
        elif self.green_streak >= self.green_required:
            # GREEN: Only step up after 5 consecutive green cycles
            new_rate = self.current_rate + self.step_up_bps
            new_rate = min(new_rate, self.ceiling_bps)
        # else: YELLOW or not enough green streak -> hold steady

        self.current_rate = new_rate
        return zone, new_rate

    def adjust_4state(self, baseline_rtt: float, load_rtt: float, green_threshold: float, soft_red_threshold: float, hard_red_threshold: float) -> Tuple[str, int]:
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

        if self.red_streak >= 1:
            # RED: Gradual decay using factor_down
            new_rate = int(self.current_rate * self.factor_down)
            new_rate = max(new_rate, self.floor_red_bps)
        elif zone == "SOFT_RED":
            # SOFT_RED: Clamp to soft_red floor and HOLD (no repeated decay)
            new_rate = max(self.current_rate, self.floor_soft_red_bps)
        elif self.green_streak >= self.green_required:
            # GREEN: Only step up after 5 consecutive green cycles
            new_rate = self.current_rate + self.step_up_bps
            new_rate = min(new_rate, self.ceiling_bps)
        else:
            # YELLOW or not enough green streak -> hold steady
            # Apply state-appropriate floor
            if zone == "YELLOW":
                new_rate = max(new_rate, self.floor_yellow_bps)
            else:  # GREEN but not sustained
                new_rate = max(new_rate, self.floor_green_bps)

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

        # Load persisted state (hysteresis counters, current rates, EWMA)
        self.load_state()

    def measure_rtt(self) -> Optional[float]:
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

    def update_ewma(self, measured_rtt: float):
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

    def run_cycle(self) -> bool:
        """Main 5-second cycle for this WAN"""
        measured_rtt = self.measure_rtt()
        if measured_rtt is None:
            self.logger.warning(f"{self.wan_name}: Ping failed, skipping cycle")
            return False

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

        # Apply to router
        success = self.router.set_limits(
            wan=self.wan_name,
            down_bps=dl_rate,
            up_bps=ul_rate
        )

        if not success:
            self.logger.error(f"{self.wan_name}: Failed to apply limits")
            return False

        # Save state after successful cycle
        self.save_state()

        return True

    def load_state(self):
        """Load persisted hysteresis state from disk"""
        try:
            if self.config.state_file.exists():
                with open(self.config.state_file, 'r') as f:
                    state = json.load(f)

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

                self.logger.debug(f"{self.wan_name}: Loaded state from {self.config.state_file}")
        except Exception as e:
            self.logger.warning(f"{self.wan_name}: Could not load state: {e}")

    def save_state(self):
        """Save hysteresis state to disk for persistence across timer invocations"""
        try:
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
                'timestamp': datetime.datetime.now().isoformat()
            }

            atomic_write_json(self.config.state_file, state)
            self.logger.debug(f"{self.wan_name}: Saved state to {self.config.state_file}")
        except Exception as e:
            self.logger.warning(f"{self.wan_name}: Could not save state: {e}")


# =============================================================================
# MAIN CONTROLLER
# =============================================================================

class ContinuousAutoRate:
    """Main controller managing one or more WANs"""
    def __init__(self, config_files: List[str], debug: bool = False):
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
            rtt_measurement = RTTMeasurement(logger, config.timeout_ping)

            # Create WAN controller
            wan_controller = WANController(config.wan_name, config, router, rtt_measurement, logger)

            self.wan_controllers.append({
                'controller': wan_controller,
                'config': config,
                'logger': logger
            })

    def run_cycle(self, use_lock: bool = True):
        """Run one cycle for all WANs

        Args:
            use_lock: If True, acquire lock per-cycle (oneshot mode).
                     If False, assume lock is already held (daemon mode).
        """
        for wan_info in self.wan_controllers:
            controller = wan_info['controller']
            config = wan_info['config']
            logger = wan_info['logger']

            try:
                if use_lock:
                    with LockFile(config.lock_file, config.lock_timeout, logger):
                        controller.run_cycle()
                else:
                    # Lock already held by daemon - just run the cycle
                    controller.run_cycle()
            except LockAcquisitionError:
                # Another instance is running - this is normal, not an error
                logger.debug("Skipping cycle - another instance is running")
            except Exception as e:
                logger.error(f"Cycle error: {e}")
                logger.debug(traceback.format_exc())

    def get_lock_paths(self) -> List[Path]:
        """Return lock file paths for all configured WANs"""
        return [wan_info['config'].lock_file for wan_info in self.wan_controllers]


# =============================================================================
# MAIN ENTRY POINT
# =============================================================================

def main():
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

    args = parser.parse_args()

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
        # Force remove any stale lock file from previous run
        if lock_path.exists():
            try:
                age = time.time() - lock_path.stat().st_mtime
                for wan_info in controller.wan_controllers:
                    wan_info['logger'].info(f"Removing stale lock file ({age:.1f}s old): {lock_path}")
                lock_path.unlink()
            except (FileNotFoundError, OSError):
                pass

        # Create new lock file
        try:
            import os
            fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
            os.close(fd)
            lock_files.append(lock_path)
            for wan_info in controller.wan_controllers:
                wan_info['logger'].debug(f"Lock acquired: {lock_path}")
        except FileExistsError:
            for wan_info in controller.wan_controllers:
                wan_info['logger'].error(f"Failed to acquire lock: {lock_path}")
            return 1

    running = True

    def handle_signal(signum, frame):
        nonlocal running
        # Log shutdown on first signal
        for wan_info in controller.wan_controllers:
            wan_info['logger'].info(f"Received signal {signum}, shutting down...")
        running = False

    signal.signal(signal.SIGTERM, handle_signal)
    signal.signal(signal.SIGINT, handle_signal)

    # Log startup
    for wan_info in controller.wan_controllers:
        wan_info['logger'].info(f"Starting daemon mode with {CYCLE_INTERVAL_SECONDS}s cycle interval")
        if HAVE_SYSTEMD:
            wan_info['logger'].info("Systemd watchdog support enabled")

    try:
        while running:
            cycle_start = time.monotonic()
            controller.run_cycle(use_lock=False)  # Lock already held
            elapsed = time.monotonic() - cycle_start

            # Notify systemd watchdog that we're alive
            if HAVE_SYSTEMD:
                sd_notify("WATCHDOG=1")

            # Sleep for remainder of cycle interval
            sleep_time = max(0, CYCLE_INTERVAL_SECONDS - elapsed)
            if sleep_time > 0 and running:
                time.sleep(sleep_time)
    finally:
        # Clean up SSH connections on exit
        for wan_info in controller.wan_controllers:
            try:
                wan_info['controller'].router.ssh.close()
            except Exception as e:
                wan_info['logger'].debug(f"Error closing SSH: {e}")

        # Clean up lock files on exit
        for lock_path in lock_files:
            try:
                lock_path.unlink()
                for wan_info in controller.wan_controllers:
                    wan_info['logger'].debug(f"Lock released: {lock_path}")
            except (FileNotFoundError, OSError):
                pass

        # Log clean shutdown
        for wan_info in controller.wan_controllers:
            wan_info['logger'].info("Daemon shutdown complete")


if __name__ == "__main__":
    main()
