#!/usr/bin/env python3
"""
Continuous CAKE Auto-Tuning System
3-zone controller with EWMA smoothing for responsive congestion control
Expert-tuned for VDSL2, Cable, and Fiber connections
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
from typing import Optional, List, Tuple

import yaml


# =============================================================================
# CONFIGURATION
# =============================================================================

class Config:
    """Configuration container loaded from YAML"""
    def __init__(self, config_path: str):
        with open(config_path, 'r') as f:
            data = yaml.safe_load(f)

        self.wan_name = data['wan_name']

        # Router
        self.router_host = data['router']['host']
        self.router_user = data['router']['user']
        self.ssh_key = data['router']['ssh_key']

        # Queues
        self.queue_down = data['queues']['download']
        self.queue_up = data['queues']['upload']

        # Continuous monitoring parameters
        cm = data['continuous_monitoring']
        self.enabled = cm['enabled']
        self.baseline_rtt_initial = cm['baseline_rtt_initial']

        # Download parameters (STATE-BASED FLOORS - Phase 2A: 4-state)
        dl = cm['download']
        # Support both legacy (single floor) and v2/v3 (state-based floors)
        if 'floor_green_mbps' in dl:
            self.download_floor_green = dl['floor_green_mbps'] * 1_000_000
            self.download_floor_yellow = dl['floor_yellow_mbps'] * 1_000_000
            self.download_floor_soft_red = dl.get('floor_soft_red_mbps', dl['floor_yellow_mbps']) * 1_000_000  # Phase 2A
            self.download_floor_red = dl['floor_red_mbps'] * 1_000_000
        else:
            # Legacy: use single floor for all states
            floor = dl['floor_mbps'] * 1_000_000
            self.download_floor_green = floor
            self.download_floor_yellow = floor
            self.download_floor_soft_red = floor  # Phase 2A
            self.download_floor_red = floor
        self.download_ceiling = dl['ceiling_mbps'] * 1_000_000
        self.download_step_up = dl['step_up_mbps'] * 1_000_000
        self.download_factor_down = dl['factor_down']

        # Upload parameters (STATE-BASED FLOORS)
        ul = cm['upload']
        # Support both legacy (single floor) and v2 (state-based floors)
        if 'floor_green_mbps' in ul:
            self.upload_floor_green = ul['floor_green_mbps'] * 1_000_000
            self.upload_floor_yellow = ul['floor_yellow_mbps'] * 1_000_000
            self.upload_floor_red = ul['floor_red_mbps'] * 1_000_000
        else:
            # Legacy: use single floor for all states
            floor = ul['floor_mbps'] * 1_000_000
            self.upload_floor_green = floor
            self.upload_floor_yellow = floor
            self.upload_floor_red = floor
        self.upload_ceiling = ul['ceiling_mbps'] * 1_000_000
        self.upload_step_up = ul['step_up_mbps'] * 1_000_000
        self.upload_factor_down = ul['factor_down']

        # Thresholds
        thresh = cm['thresholds']
        self.target_bloat_ms = thresh['target_bloat_ms']          # GREEN → YELLOW (15ms)
        self.warn_bloat_ms = thresh['warn_bloat_ms']              # YELLOW → SOFT_RED (45ms)
        self.hard_red_bloat_ms = thresh.get('hard_red_bloat_ms', 80)  # SOFT_RED → RED (80ms)
        self.alpha_baseline = thresh['alpha_baseline']
        self.alpha_load = thresh['alpha_load']

        # Ping configuration
        self.ping_hosts = cm['ping_hosts']
        self.use_median_of_three = cm.get('use_median_of_three', False)

        # Lock file
        self.lock_file = Path(data['lock_file'])
        self.lock_timeout = data['lock_timeout']

        # State file (for persisting hysteresis counters)
        # Derive from lock file path: /tmp/wanctl_att.lock -> /tmp/wanctl_att_state.json
        lock_stem = self.lock_file.stem
        self.state_file = self.lock_file.parent / f"{lock_stem}_state.json"

        # Logging
        self.main_log = data['logging']['main_log']
        self.debug_log = data['logging']['debug_log']


# =============================================================================
# LOGGING
# =============================================================================

def setup_logging(config: Config, debug: bool) -> logging.Logger:
    """Setup logging with file and optional console output"""
    logger = logging.getLogger(f"cake_continuous_{config.wan_name.lower()}")

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
    """Context manager for lock file"""
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
# ROUTEROS SSH INTERFACE
# =============================================================================

class RouterOS:
    """RouterOS SSH interface for setting queue limits"""
    def __init__(self, config: Config, logger: logging.Logger):
        self.config = config
        self.logger = logger

    def _run_cmd(self, cmd: str, capture: bool = False) -> Tuple[int, str, str]:
        """Execute RouterOS command via SSH"""
        args = [
            "ssh", "-i", self.config.ssh_key,
            "-o", "StrictHostKeyChecking=no",
            "-o", "ConnectTimeout=10",
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
                    timeout=15
                )
                self.logger.debug(f"RouterOS stdout: {res.stdout}")
                return res.returncode, res.stdout, res.stderr
            else:
                res = subprocess.run(args, text=True, timeout=15)
                return res.returncode, "", ""
        except subprocess.TimeoutExpired:
            self.logger.error("RouterOS command timeout")
            return 1, "", "Timeout"
        except Exception as e:
            self.logger.error(f"RouterOS SSH error: {e}")
            self.logger.debug(traceback.format_exc())
            return 1, "", str(e)

    def set_limits(self, wan: str, down_bps: int, up_bps: int) -> bool:
        """Set CAKE limits for one WAN"""
        self.logger.debug(f"{wan}: Setting limits DOWN={down_bps} UP={up_bps}")

        # WAN name for queue type (e.g., "ATT" -> "att", "Spectrum" -> "spectrum")
        wan_lower = self.config.wan_name.lower()

        # Apply settings to queue tree with both queue type and max-limit
        for queue, direction, bps in [
            (self.config.queue_down, 'down', down_bps),
            (self.config.queue_up, 'up', up_bps)
        ]:
            queue_type = f"cake-{direction}-{wan_lower}"
            rc, _, _ = self._run_cmd(
                f'/queue tree set [find name="{queue}"] queue={queue_type} max-limit={bps}'
            )
            if rc != 0:
                self.logger.error(f"Failed to set queue tree {queue}")
                return False

        return True


# =============================================================================
# RTT MEASUREMENT
# =============================================================================

class RTTMeasurement:
    """Lightweight RTT measurement via ping"""
    def __init__(self, logger: logging.Logger):
        self.logger = logger

    def ping_host(self, host: str, count: int = 5) -> Optional[float]:
        """
        Ping single host and return average RTT in milliseconds
        Returns None on failure
        """
        try:
            result = subprocess.run(
                ["ping", "-c", str(count), "-W", "1", host],
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
                    except:
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
            # RED: Immediate step-down
            new_rate = int(self.current_rate * self.factor_down)
            # Use state-appropriate floor
            if zone == "RED":
                floor_bps = self.floor_red_bps
            elif zone == "YELLOW":
                floor_bps = self.floor_yellow_bps
            else:  # GREEN
                floor_bps = self.floor_green_bps
            new_rate = max(new_rate, floor_bps)
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
            # RED: Immediate aggressive step-down
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
        """
        if self.use_median_of_three and len(self.ping_hosts) >= 3:
            # Ping multiple hosts, take median to handle reflector variation
            rtts = []
            for host in self.ping_hosts[:3]:  # Use first 3
                rtt = self.rtt_measurement.ping_host(host, count=3)  # Faster for multiple hosts
                if rtt is not None:
                    rtts.append(rtt)

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
            return self.rtt_measurement.ping_host(self.ping_hosts[0], count=5)

    def update_ewma(self, measured_rtt: float):
        """Update both EWMAs (fast load, slow baseline)"""
        # Fast EWMA for load_rtt (responsive to current conditions)
        self.load_rtt = (1 - self.alpha_load) * self.load_rtt + self.alpha_load * measured_rtt

        # Slow EWMA for baseline_rtt (ONLY update when line is genuinely idle)
        # This tracks the "normal" RTT without congestion
        #
        # Critical: Only update baseline when delta is very small (< 3ms)
        # This prevents baseline drift during load, which would mask true bloat
        delta = self.load_rtt - self.baseline_rtt
        if delta < 3.0:
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

            with open(self.config.state_file, 'w') as f:
                json.dump(state, f, indent=2)

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
            logger = setup_logging(config, debug)

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
            rtt_measurement = RTTMeasurement(logger)

            # Create WAN controller
            wan_controller = WANController(config.wan_name, config, router, rtt_measurement, logger)

            self.wan_controllers.append({
                'controller': wan_controller,
                'config': config,
                'logger': logger
            })

    def run_cycle(self):
        """Run one cycle for all WANs"""
        for wan_info in self.wan_controllers:
            controller = wan_info['controller']
            config = wan_info['config']
            logger = wan_info['logger']

            try:
                with LockFile(config.lock_file, config.lock_timeout, logger):
                    controller.run_cycle()
            except Exception as e:
                logger.error(f"Cycle error: {e}")
                logger.debug(traceback.format_exc())


# =============================================================================
# MAIN ENTRY POINT
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Continuous CAKE Auto-Tuning with 3-Zone Controller"
    )
    parser.add_argument(
        '--configs', nargs='+', required=True,
        help='One or more config files (supports single-WAN or multi-WAN)'
    )
    parser.add_argument(
        '--debug', action='store_true',
        help='Enable debug logging to console and debug log file'
    )

    args = parser.parse_args()

    # Create controller
    controller = ContinuousAutoRate(args.configs, debug=args.debug)

    # Run one cycle (systemd timer will invoke repeatedly)
    controller.run_cycle()


if __name__ == "__main__":
    main()
