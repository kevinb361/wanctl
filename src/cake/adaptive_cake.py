#!/usr/bin/env python3
"""
Adaptive CAKE Auto-Tuning System
Unified implementation with config file support
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
from typing import Optional, Tuple, Dict, Any

import pexpect

from cake.config_base import BaseConfig
from cake.lockfile import LockFile, LockAcquisitionError
from cake.logging_utils import setup_logging
from cake.routeros_ssh import RouterOSSSH
from cake.state_utils import atomic_write_json


# =============================================================================
# CONSTANTS
# =============================================================================

# Default bloat thresholds (milliseconds)
DEFAULT_TARGET_BLOAT_MS = 10.0        # Target for binary search optimization
DEFAULT_QUICK_CHECK_BLOAT_MS = 15.0   # Threshold to trigger full search

# Default timeout values (seconds)
DEFAULT_SSH_TIMEOUT = 30
DEFAULT_PEXPECT_TIMEOUT = 60
DEFAULT_NETPERF_TIMEOUT = 20

# Binary search parameters
BINARY_SEARCH_WORST_BLOAT = 999.0     # Sentinel for "no good rate found yet"
DEFAULT_K_FACTOR_FALLBACK = 0.5       # Conservative fallback when bloat is severe

# Measurement parameters
PING_INTERVAL_SECONDS = 0.2           # Ping interval during measurements
BASELINE_PING_DURATION = 3            # Seconds for baseline RTT measurement
LOADED_PING_DURATION = 10             # Seconds for loaded RTT measurement
NETPERF_TEST_DURATION = 15            # Seconds for netperf throughput test

# Conversion factors
MBPS_TO_BPS = 1_000_000


# =============================================================================
# CONGESTION STATE CHECK (Option 2: Gate on Steering State)
# =============================================================================

def should_skip_calibration(
    logger: logging.Logger,
    steering_state_file: str = "/var/lib/wanctl/steering_state.json"
) -> bool:
    """
    Check if steering daemon reports congestion (YELLOW or RED).

    Expert guidance: "Never run Dallas tests while YELLOW or RED"
    This prevents calibration tests from contaminating congestion signals.

    Args:
        logger: Logger instance
        steering_state_file: Path to steering daemon state file (default: standard location)

    Returns True if calibration should be skipped (congestion present)
    """
    steering_state_path = steering_state_file

    # If steering daemon not running or state file doesn't exist, allow calibration
    if not os.path.exists(steering_state_path):
        logger.debug("Steering state file not found - proceeding with calibration")
        return False

    try:
        with open(steering_state_path, 'r') as f:
            state = json.load(f)

        congestion_state = state.get('congestion_state', 'GREEN')
        current_system_state = state.get('current_state', 'SPECTRUM_GOOD')

        if congestion_state != 'GREEN':
            logger.info(
                f"⏸️  CALIBRATION DEFERRED - Congestion detected: {congestion_state} "
                f"(system: {current_system_state})"
            )
            logger.info("Fast loop (steering) is active - slow loop (calibration) waiting")
            return True

        logger.debug(f"Congestion state: {congestion_state} - calibration allowed")
        return False

    except Exception as e:
        logger.warning(f"Failed to read steering state: {e} - proceeding with calibration")
        return False


# =============================================================================
# CONFIGURATION
# =============================================================================

class Config(BaseConfig):
    """Configuration container loaded from YAML"""

    # Schema for adaptive_cake configuration validation
    SCHEMA = [
        # Queue names
        {"path": "queues.download", "type": str, "required": True},
        {"path": "queues.upload", "type": str, "required": True},

        # Test servers
        {"path": "test.netperf_host", "type": str, "required": True},
        {"path": "test.ping_host", "type": str, "required": True},

        # Bandwidth limits
        {"path": "bandwidth.down_max", "type": (int, float),
         "required": True, "min": 1, "max": 10000},
        {"path": "bandwidth.down_min", "type": (int, float),
         "required": True, "min": 1, "max": 10000},
        {"path": "bandwidth.up_max", "type": (int, float),
         "required": True, "min": 1, "max": 1000},
        {"path": "bandwidth.up_min", "type": (int, float),
         "required": True, "min": 1, "max": 1000},

        # Tuning - required fields
        {"path": "tuning.alpha", "type": float,
         "required": True, "min": 0.01, "max": 1.0},
        {"path": "tuning.alpha_good_conditions", "type": float,
         "required": True, "min": 0.01, "max": 1.0},
        {"path": "tuning.base_rtt", "type": (int, float),
         "required": True, "min": 1, "max": 500},

        # K-factor thresholds
        {"path": "k_factor.delta_0_5ms", "type": float,
         "required": True, "min": 0.5, "max": 1.5},
        {"path": "k_factor.delta_5_15ms", "type": float,
         "required": True, "min": 0.5, "max": 1.5},
        {"path": "k_factor.delta_15_30ms", "type": float,
         "required": True, "min": 0.3, "max": 1.0},
        {"path": "k_factor.delta_30plus", "type": float,
         "required": True, "min": 0.3, "max": 1.0},

        # Safety limits
        {"path": "safety.max_up_factor", "type": float,
         "required": True, "min": 1.0, "max": 2.0},
        {"path": "safety.max_down_factor", "type": float,
         "required": True, "min": 1.0, "max": 2.0},
        {"path": "safety.sanity_fraction", "type": float,
         "required": True, "min": 0.1, "max": 0.5},
        {"path": "safety.health_fraction", "type": float,
         "required": True, "min": 0.05, "max": 0.3},
        {"path": "safety.outlier_std_dev", "type": float,
         "required": True, "min": 1.0, "max": 5.0},

        # State persistence
        {"path": "state.file", "type": str, "required": True},
        {"path": "state.history_size", "type": int,
         "required": True, "min": 1, "max": 100},

        # Logging
        {"path": "logging.main_log", "type": str, "required": True},
        {"path": "logging.debug_log", "type": str, "required": True},

        # Lock file
        {"path": "lock_file", "type": str, "required": True},
        {"path": "lock_timeout", "type": int, "required": True, "min": 1, "max": 3600},
    ]

    def _load_specific_fields(self):
        """Load adaptive_cake-specific configuration fields"""
        # Queues (validated to prevent command injection)
        self.queue_down = self.validate_identifier(
            self.data['queues']['download'], 'queues.download'
        )
        self.queue_up = self.validate_identifier(
            self.data['queues']['upload'], 'queues.upload'
        )

        # Test servers
        self.netperf_host = self.data['test']['netperf_host']
        self.ping_host = self.data['test']['ping_host']

        # Bandwidth
        self.down_max = self.data['bandwidth']['down_max']
        self.down_min = self.data['bandwidth']['down_min']
        self.up_max = self.data['bandwidth']['up_max']
        self.up_min = self.data['bandwidth']['up_min']

        # Tuning
        self.alpha = self.data['tuning']['alpha']
        self.alpha_good = self.data['tuning']['alpha_good_conditions']
        self.base_rtt = self.data['tuning']['base_rtt']

        # Binary search parameters (Flent/LibreQoS method)
        self.use_binary_search = self.data['tuning'].get('use_binary_search', True)
        self.target_bloat_ms = self.data['tuning'].get('target_bloat_ms', DEFAULT_TARGET_BLOAT_MS)
        self.binary_search_iterations = self.data['tuning'].get('binary_search_iterations', 5)

        # Quick check mode (validation vs full search)
        self.quick_check_enabled = self.data['tuning'].get('quick_check_enabled', True)
        self.quick_check_bloat_threshold = self.data['tuning'].get('quick_check_bloat_threshold', DEFAULT_QUICK_CHECK_BLOAT_MS)
        self.full_search_interval_cycles = self.data['tuning'].get('full_search_interval_cycles', 6)

        # K-factor
        kf = self.data['k_factor']
        self.k_factor_thresholds = [
            (0, 5, kf['delta_0_5ms']),
            (5, 15, kf['delta_5_15ms']),
            (15, 30, kf['delta_15_30ms']),
            (30, float('inf'), kf['delta_30plus'])
        ]

        # Safety
        sf = self.data['safety']
        self.max_up_factor = sf['max_up_factor']
        self.max_down_factor = sf['max_down_factor']
        self.sanity_fraction = sf['sanity_fraction']
        self.health_fraction = sf['health_fraction']
        self.outlier_std_dev = sf['outlier_std_dev']

        # State
        self.state_file = Path(self.data['state']['file'])
        self.history_size = self.data['state']['history_size']

        # Logging
        self.main_log = self.data['logging']['main_log']
        self.debug_log = self.data['logging']['debug_log']

        # Lock file
        self.lock_file = Path(self.data['lock_file'])
        self.lock_timeout = self.data['lock_timeout']

        # Timeouts (with sensible defaults)
        timeouts = self.data.get('timeouts', {})
        self.timeout_ssh_command = timeouts.get('ssh_command', DEFAULT_SSH_TIMEOUT)
        self.timeout_pexpect = timeouts.get('pexpect', DEFAULT_PEXPECT_TIMEOUT)
        self.timeout_netperf = timeouts.get('netperf', DEFAULT_NETPERF_TIMEOUT)

        # External state files (with sensible default)
        paths = self.data.get('paths', {})
        self.steering_state_file = paths.get(
            'steering_state_file',
            '/var/lib/wanctl/steering_state.json'
        )


# =============================================================================
# LOCK FILE MANAGEMENT
# =============================================================================

# =============================================================================
# STATE PERSISTENCE WITH HISTORY
# =============================================================================

class StateManager:
    """Manages state persistence with measurement history"""
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

        return {
            "ewma_down": None,
            "ewma_up": None,
            "last_down_cap": None,
            "last_up_cap": None,
            "history_down": [],
            "history_up": [],
            "history_bloat": [],
            "cycles_since_full_search": 0,
            "last_full_search_timestamp": None
        }

    def _validate(self, state: Dict) -> Dict:
        """Validate and clean state data"""
        def safe_float(key):
            v = state.get(key)
            if v is None:
                return None
            try:
                v = float(v)
                return v if v > 0 else None
            except (ValueError, TypeError) as e:
                self.logger.debug(f"Failed to parse float for key '{key}': {e}")
                return None

        def safe_int(key):
            v = state.get(key)
            if v is None:
                return None
            try:
                v = int(v)
                return v if v > 0 else None
            except (ValueError, TypeError) as e:
                self.logger.debug(f"Failed to parse int for key '{key}': {e}")
                return None

        def safe_list(key):
            v = state.get(key, [])
            if not isinstance(v, list):
                return []
            return [float(x) for x in v if isinstance(x, (int, float)) and x > 0]

        return {
            "ewma_down": safe_float("ewma_down"),
            "ewma_up": safe_float("ewma_up"),
            "last_down_cap": safe_int("last_down_cap"),
            "last_up_cap": safe_int("last_up_cap"),
            "history_down": safe_list("history_down"),
            "history_up": safe_list("history_up"),
            "history_bloat": safe_list("history_bloat"),
            "cycles_since_full_search": int(state.get("cycles_since_full_search", 0)),
            "last_full_search_timestamp": state.get("last_full_search_timestamp")
        }

    def save(self):
        """Save state to file atomically"""
        try:
            atomic_write_json(self.config.state_file, self.state)
            self.logger.debug(f"Saved state: {self.state}")
        except Exception as e:
            self.logger.error(f"Failed to save state: {e}")
            self.logger.debug(traceback.format_exc())

    def add_measurement(self, down: float, up: float, bloat: float) -> bool:
        """
        Add measurement to history with outlier detection
        Returns True if measurement accepted, False if rejected as outlier
        """
        # Check for outliers if we have history
        for value, history_key, name in [
            (down, "history_down", "download"),
            (up, "history_up", "upload"),
            (bloat, "history_bloat", "bloat")
        ]:
            history = self.state[history_key]
            if len(history) >= 3:
                mean = statistics.mean(history[-6:])  # Use recent history
                try:
                    std = statistics.stdev(history[-6:])
                    if abs(value - mean) > self.config.outlier_std_dev * std:
                        self.logger.warning(
                            f"Outlier detected in {name}: {value:.2f} "
                            f"(mean={mean:.2f}, std={std:.2f}). Rejecting."
                        )
                        return False
                except statistics.StatisticsError:
                    pass  # Not enough variance, accept measurement

        # Add to history (with size limit)
        self.state["history_down"].append(down)
        self.state["history_up"].append(up)
        self.state["history_bloat"].append(bloat)

        # Trim to max size
        for key in ["history_down", "history_up", "history_bloat"]:
            if len(self.state[key]) > self.config.history_size:
                self.state[key] = self.state[key][-self.config.history_size:]

        return True

    def reset(self):
        """Reset state to initial values"""
        self.logger.info("Resetting state")
        self.state = {
            "ewma_down": None,
            "ewma_up": None,
            "last_down_cap": None,
            "last_up_cap": None,
            "history_down": [],
            "history_up": [],
            "history_bloat": []
        }
        self.save()


# =============================================================================
# ROUTEROS INTERFACE
# =============================================================================

class RouterOS:
    """RouterOS SSH interface with verification"""
    def __init__(self, config: Config, logger: logging.Logger):
        self.config = config
        self.logger = logger
        self.ssh = RouterOSSSH.from_config(config, logger)

    @staticmethod
    def _parse_rate(value: str) -> int:
        """Convert RouterOS rate format to bps"""
        s = value.strip().lower()

        if s.endswith("m"):
            return int(float(s[:-1]) * 1_000_000)
        if s.endswith("k"):
            return int(float(s[:-1]) * 1_000)

        return int(float(s))

    def get_max_limit(self, queue_name: str) -> Optional[int]:
        """Read current max-limit from queue"""
        rc, out, _ = self.ssh.run_cmd(
            f'/queue tree print detail where name="{queue_name}"',
            capture=True
        )

        if rc != 0:
            self.logger.error(f"Failed to read queue {queue_name}")
            return None

        m = re.search(r"max-limit=([\w\.]+)", out)
        if not m:
            self.logger.error(f"No max-limit found in output: {out}")
            return None

        raw = m.group(1)
        bps = self._parse_rate(raw)
        self.logger.debug(f"Queue {queue_name}: {raw} → {bps} bps")
        return bps

    def set_limits(self, down_bps: int, up_bps: int) -> bool:
        """Set CAKE limits with verification - only sets max-limit"""
        self.logger.info(f"Setting limits: DOWN={down_bps} UP={up_bps}")

        # Apply settings to queue tree max-limit only
        for queue, bps in [
            (self.config.queue_down, down_bps),
            (self.config.queue_up, up_bps)
        ]:
            # Set queue tree max-limit
            rc, _, _ = self.ssh.run_cmd(
                f'/queue tree set [find name="{queue}"] max-limit={bps}'
            )
            if rc != 0:
                self.logger.error(f"Failed to set queue tree {queue}")
                return False

        # Verify
        actual_down = self.get_max_limit(self.config.queue_down)
        actual_up = self.get_max_limit(self.config.queue_up)

        if actual_down is None or actual_up is None:
            self.logger.error("Verification failed: could not read limits")
            return False

        if actual_down != down_bps or actual_up != up_bps:
            self.logger.error(
                f"Verification mismatch: expected ({down_bps}, {up_bps}) "
                f"got ({actual_down}, {actual_up})"
            )
            return False

        self.logger.info("Limits applied and verified")
        return True

    def unshape(self):
        """Remove shaping (set max-limit=0)"""
        self.logger.info("Unshaping queues")
        for queue in [self.config.queue_down, self.config.queue_up]:
            self.ssh.run_cmd(f'/queue tree set [find name="{queue}"] max-limit=0')


# =============================================================================
# MEASUREMENT - LATENCY UNDER LOAD
# =============================================================================

class Measurement:
    """Network measurement with latency-under-load testing"""
    def __init__(self, config: Config, logger: logging.Logger):
        self.config = config
        self.logger = logger

    def _run_pexpect(self, cmd: str) -> str:
        """Run command via pexpect and capture output"""
        self.logger.debug(f"pexpect: {cmd}")
        out = ""
        try:
            child = pexpect.spawn(cmd, encoding="utf-8", timeout=self.config.timeout_pexpect)
            while True:
                line = child.readline()
                if not line:
                    break
                out += line
            child.close()
        except Exception as e:
            self.logger.error(f"pexpect error: {e}")
            self.logger.debug(traceback.format_exc())

        self.logger.debug(f"pexpect output:\n{out}")
        return out

    def _parse_netperf(self, text: str) -> float:
        """Parse netperf output for throughput (Mbps)"""
        # Try numeric table format first
        m = re.search(r"\n\s*\d+\s+\d+\s+\d+\s+[0-9.]+\s+([0-9.]+)\s*\n", text)
        if m:
            return float(m.group(1))

        # Fallback patterns
        for pattern in [r"([0-9.]+)\s*Mbps",
                       r"([0-9.]+)\s*Mbits/sec",
                       r"([0-9.]+)\s*10\^6bits/sec"]:
            m = re.search(pattern, text)
            if m:
                return float(m.group(1))

        self.logger.warning("Could not parse netperf output")
        return 0.0

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

    def measure_baseline_latency(self) -> float:
        """
        Measure idle baseline latency
        Uses minimum RTT as baseline (true unloaded latency)
        """
        self.logger.debug("Measuring baseline latency (idle)")
        out = self._run_pexpect(f"ping -i {PING_INTERVAL_SECONDS} -w {BASELINE_PING_DURATION} {self.config.ping_host}")
        rtts = self._parse_ping(out)

        if not rtts:
            self.logger.warning("No baseline RTT samples")
            return 0.0

        # Use minimum RTT as baseline (represents true idle latency without any queueing)
        baseline = min(rtts)
        self.logger.debug(f"Baseline RTT: {baseline:.2f}ms (min of {len(rtts)} samples, median: {statistics.median(rtts):.2f}ms)")
        return baseline

    def measure_download(self, baseline_rtt: float = None) -> Tuple[float, float]:
        """
        Measure download throughput and latency under load
        Args:
            baseline_rtt: Measured baseline RTT (if None, uses config value)
        Returns: (throughput_mbps, bloat_ms)
        """
        if baseline_rtt is None:
            baseline_rtt = self.config.base_rtt
            self.logger.debug(f"Using config base_rtt: {baseline_rtt}ms")

        self.logger.info("Measuring download (latency under load)")

        # Start netperf in background
        netperf_cmd = [
            "netperf", "-H", self.config.netperf_host,
            "-t", "TCP_MAERTS", "-l", str(NETPERF_TEST_DURATION), "-v", "2"
        ]

        self.logger.debug(f"Starting netperf: {' '.join(netperf_cmd)}")
        netperf_proc = subprocess.Popen(
            netperf_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        # Wait for ramp-up
        time.sleep(2)

        # Measure latency while loaded
        self.logger.debug("Measuring latency under download load")
        out = self._run_pexpect(f"ping -i {PING_INTERVAL_SECONDS} -w {LOADED_PING_DURATION} {self.config.ping_host}")
        rtts_loaded = self._parse_ping(out)

        # Get throughput result
        try:
            stdout, stderr = netperf_proc.communicate(timeout=self.config.timeout_netperf)
            throughput = self._parse_netperf(stdout)
        except subprocess.TimeoutExpired:
            netperf_proc.kill()
            self.logger.error("Netperf timeout")
            return 0.0, 0.0

        # Calculate bloat
        if not rtts_loaded:
            self.logger.warning("No RTT samples under load")
            return throughput, 0.0

        # Use median RTT (standard for bufferbloat measurement, what Flent uses)
        latency_loaded = statistics.median(rtts_loaded)
        bloat = max(0, latency_loaded - baseline_rtt)

        self.logger.info(
            f"Download: {throughput:.2f} Mbps, "
            f"RTT under load: {latency_loaded:.1f}ms, "
            f"Bloat: {bloat:.1f}ms (baseline: {baseline_rtt:.1f}ms)"
        )

        return throughput, bloat

    def measure_upload(self, baseline_rtt: float = None) -> Tuple[float, float]:
        """
        Measure upload throughput and latency under load
        Args:
            baseline_rtt: Measured baseline RTT (if None, uses config value)
        Returns: (throughput_mbps, bloat_ms)
        """
        if baseline_rtt is None:
            baseline_rtt = self.config.base_rtt
            self.logger.debug(f"Using config base_rtt: {baseline_rtt}ms")

        self.logger.info("Measuring upload (latency under load)")

        # Start netperf in background
        netperf_cmd = [
            "netperf", "-H", self.config.netperf_host,
            "-t", "TCP_STREAM", "-l", str(NETPERF_TEST_DURATION), "-v", "2"
        ]

        self.logger.debug(f"Starting netperf: {' '.join(netperf_cmd)}")
        netperf_proc = subprocess.Popen(
            netperf_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        # Wait for ramp-up
        time.sleep(2)

        # Measure latency while loaded
        self.logger.debug("Measuring latency under upload load")
        out = self._run_pexpect(f"ping -i {PING_INTERVAL_SECONDS} -w {LOADED_PING_DURATION} {self.config.ping_host}")
        rtts_loaded = self._parse_ping(out)

        # Get throughput result
        try:
            stdout, stderr = netperf_proc.communicate(timeout=self.config.timeout_netperf)
            throughput = self._parse_netperf(stdout)
        except subprocess.TimeoutExpired:
            netperf_proc.kill()
            self.logger.error("Netperf timeout")
            return 0.0, 0.0

        # Calculate bloat
        if not rtts_loaded:
            self.logger.warning("No RTT samples under load")
            return throughput, 0.0

        # Use median RTT (standard for bufferbloat measurement, what Flent uses)
        latency_loaded = statistics.median(rtts_loaded)
        bloat = max(0, latency_loaded - baseline_rtt)

        self.logger.info(
            f"Upload: {throughput:.2f} Mbps, "
            f"RTT under load: {latency_loaded:.1f}ms, "
            f"Bloat: {bloat:.1f}ms (baseline: {baseline_rtt:.1f}ms)"
        )

        return throughput, bloat

    def test_rate_download(self, rate_mbps: float, router, baseline_rtt: float) -> Tuple[float, float]:
        """
        Test specific download rate to measure bloat
        Temporarily sets CAKE limit, runs test, measures latency
        Returns: (achieved_mbps, bloat_ms)
        """
        # Set CAKE to test rate
        rate_bps = int(rate_mbps * 1_000_000)
        router.set_limits(down_bps=rate_bps, up_bps=int(self.config.up_max * 1_000_000))

        time.sleep(1)  # Let queue stabilize

        # Run download test
        throughput, bloat = self.measure_download(baseline_rtt=baseline_rtt)

        return throughput, bloat

    def test_rate_upload(self, rate_mbps: float, router, baseline_rtt: float) -> Tuple[float, float]:
        """
        Test specific upload rate to measure bloat
        Temporarily sets CAKE limit, runs test, measures latency
        Returns: (achieved_mbps, bloat_ms)
        """
        # Set CAKE to test rate
        rate_bps = int(rate_mbps * 1_000_000)
        router.set_limits(down_bps=int(self.config.down_max * 1_000_000), up_bps=rate_bps)

        time.sleep(1)  # Let queue stabilize

        # Run upload test
        throughput, bloat = self.measure_upload(baseline_rtt=baseline_rtt)

        return throughput, bloat

    def find_optimal_download_rate(self, router, baseline_rtt: float, target_bloat_ms: float = DEFAULT_TARGET_BLOAT_MS, iterations: int = 5) -> Tuple[float, float]:
        """
        Binary search to find maximum download rate that keeps bloat under target
        This is the Flent/LibreQoS approach: find the rate with acceptable latency
        Args:
            router: RouterOS instance
            baseline_rtt: Measured baseline RTT
            target_bloat_ms: Maximum acceptable bloat
            iterations: Number of binary search iterations
        Returns: (optimal_rate_mbps, final_bloat_ms)
        """
        min_rate = self.config.down_min
        max_rate = self.config.down_max

        self.logger.info(f"Binary search for optimal download rate (target bloat: {target_bloat_ms}ms)")

        best_rate = min_rate
        best_bloat = BINARY_SEARCH_WORST_BLOAT

        for i in range(iterations):
            test_rate = (min_rate + max_rate) / 2

            self.logger.info(f"  Iteration {i+1}/{iterations}: Testing {test_rate:.1f} Mbps (range: {min_rate:.1f}-{max_rate:.1f})")

            throughput, bloat = self.test_rate_download(test_rate, router, baseline_rtt)

            self.logger.info(f"    Result: {throughput:.2f} Mbps, bloat: {bloat:.1f}ms")

            if bloat <= target_bloat_ms:
                # Good latency - we can try higher
                best_rate = test_rate
                best_bloat = bloat
                min_rate = test_rate
                self.logger.info(f"    ✓ Acceptable bloat, trying higher rate")
            else:
                # Too much bloat - need to go lower
                max_rate = test_rate
                self.logger.info(f"    ✗ Excessive bloat, trying lower rate")

        self.logger.info(f"Optimal download rate: {best_rate:.2f} Mbps (bloat: {best_bloat:.1f}ms)")
        return best_rate, best_bloat

    def find_optimal_upload_rate(self, router, baseline_rtt: float, target_bloat_ms: float = DEFAULT_TARGET_BLOAT_MS, iterations: int = 5) -> Tuple[float, float]:
        """
        Binary search to find maximum upload rate that keeps bloat under target
        Args:
            router: RouterOS instance
            baseline_rtt: Measured baseline RTT
            target_bloat_ms: Maximum acceptable bloat
            iterations: Number of binary search iterations
        Returns: (optimal_rate_mbps, final_bloat_ms)
        """
        min_rate = self.config.up_min
        max_rate = self.config.up_max

        self.logger.info(f"Binary search for optimal upload rate (target bloat: {target_bloat_ms}ms)")

        best_rate = min_rate
        best_bloat = BINARY_SEARCH_WORST_BLOAT

        for i in range(iterations):
            test_rate = (min_rate + max_rate) / 2

            self.logger.info(f"  Iteration {i+1}/{iterations}: Testing {test_rate:.1f} Mbps (range: {min_rate:.1f}-{max_rate:.1f})")

            throughput, bloat = self.test_rate_upload(test_rate, router, baseline_rtt)

            self.logger.info(f"    Result: {throughput:.2f} Mbps, bloat: {bloat:.1f}ms")

            if bloat <= target_bloat_ms:
                # Good latency - we can try higher
                best_rate = test_rate
                best_bloat = bloat
                min_rate = test_rate
                self.logger.info(f"    ✓ Acceptable bloat, trying higher rate")
            else:
                # Too much bloat - need to go lower
                max_rate = test_rate
                self.logger.info(f"    ✗ Excessive bloat, trying lower rate")

        self.logger.info(f"Optimal upload rate: {best_rate:.2f} Mbps (bloat: {best_bloat:.1f}ms)")
        return best_rate, best_bloat

    def quick_check(self) -> Tuple[float, float, float, float]:
        """
        Quick validation test at current CAKE limits
        Does NOT unshape - tests with existing limits in place
        This is fast (~60 seconds) and validates current settings

        Returns: (down_mbps, up_mbps, down_bloat_ms, up_bloat_ms)
        """
        self.logger.info("Quick check at current CAKE limits (validation mode)")

        # Measure baseline latency
        baseline = self.measure_baseline_latency()

        # Download test (with current CAKE limit)
        down_mbps, down_bloat = self.measure_download(baseline_rtt=baseline)

        time.sleep(3)

        # Upload test (with current CAKE limit)
        up_mbps, up_bloat = self.measure_upload(baseline_rtt=baseline)

        self.logger.info(
            f"Quick check complete: DOWN={down_mbps:.2f}Mbps (bloat={down_bloat:.1f}ms), "
            f"UP={up_mbps:.2f}Mbps (bloat={up_bloat:.1f}ms)"
        )

        return down_mbps, up_mbps, down_bloat, up_bloat

    def run_full_test(self, router=None, use_binary_search: bool = True, target_bloat_ms: float = DEFAULT_TARGET_BLOAT_MS) -> Tuple[float, float, float, float]:
        """
        Run complete measurement cycle using binary search to find optimal rates
        This implements the Flent/LibreQoS methodology:
        - Find max throughput that maintains acceptable latency
        - Not max throughput with massive bufferbloat

        Returns: (down_mbps, up_mbps, down_bloat_ms, up_bloat_ms)
        """
        self.logger.info("Starting full binary search (discovery mode)")

        # Baseline
        baseline = self.measure_baseline_latency()

        if use_binary_search and router:
            # NEW APPROACH: Find optimal rates with binary search
            self.logger.info("Using binary search to find optimal rates (Flent/LibreQoS method)")

            down_mbps, down_bloat = self.find_optimal_download_rate(
                router,
                baseline,
                target_bloat_ms,
                iterations=self.config.binary_search_iterations
            )

            time.sleep(3)  # Pause between tests

            up_mbps, up_bloat = self.find_optimal_upload_rate(
                router,
                baseline,
                target_bloat_ms,
                iterations=self.config.binary_search_iterations
            )
        else:
            # OLD APPROACH: Measure saturated throughput (deprecated)
            self.logger.warning("Using legacy saturated throughput measurement (not recommended)")

            down_mbps, down_bloat = self.measure_download(baseline_rtt=baseline)
            time.sleep(3)
            up_mbps, up_bloat = self.measure_upload(baseline_rtt=baseline)

        self.logger.info(
            f"Test complete: DOWN={down_mbps:.2f}Mbps (bloat={down_bloat:.1f}ms), "
            f"UP={up_mbps:.2f}Mbps (bloat={up_bloat:.1f}ms)"
        )

        return down_mbps, up_mbps, down_bloat, up_bloat


# =============================================================================
# COMPUTE & ADJUSTMENT LOGIC
# =============================================================================

class CakeAdjuster:
    """CAKE bandwidth adjustment logic"""
    def __init__(self, config: Config, logger: logging.Logger):
        self.config = config
        self.logger = logger

    def _get_k_factor(self, bloat: float) -> float:
        """Get k-factor based on bloat level"""
        for low, high, k in self.config.k_factor_thresholds:
            if low <= bloat < high:
                self.logger.debug(f"Bloat={bloat:.1f}ms → k-factor={k}")
                return k
        return DEFAULT_K_FACTOR_FALLBACK

    def compute_caps(
        self,
        ewma_down: float,
        ewma_up: float,
        down_bloat: float,
        up_bloat: float,
        last_down_cap: Optional[int],
        last_up_cap: Optional[int]
    ) -> Tuple[int, int]:
        """
        Compute new CAKE bandwidth caps
        Returns: (down_bps, up_bps)
        """
        # K-factors based on bloat
        k_down = self._get_k_factor(down_bloat)
        k_up = self._get_k_factor(up_bloat)

        # Apply k-factor and clamp to min/max
        down_mbps = max(
            self.config.down_min,
            min(self.config.down_max, ewma_down * k_down)
        )
        up_mbps = max(
            self.config.up_min,
            min(self.config.up_max, ewma_up * k_up)
        )

        down_bps = int(down_mbps * 1_000_000)
        up_bps = int(up_mbps * 1_000_000)

        # Rate-of-change limiting
        down_bps = self._limit_rate_change(
            down_bps, last_down_cap, "DOWN"
        )
        up_bps = self._limit_rate_change(
            up_bps, last_up_cap, "UP"
        )

        self.logger.info(
            f"Computed caps: DOWN={down_bps} UP={up_bps} "
            f"(k_down={k_down:.2f}, k_up={k_up:.2f})"
        )

        return down_bps, up_bps

    def _limit_rate_change(
        self,
        new_cap: int,
        last_cap: Optional[int],
        label: str
    ) -> int:
        """Limit rate of change to prevent wild swings"""
        if last_cap is None:
            return new_cap

        min_allowed = int(last_cap * self.config.max_down_factor)
        max_allowed = int(last_cap * self.config.max_up_factor)

        if new_cap < min_allowed:
            self.logger.warning(
                f"{label}: Clamping decrease "
                f"{new_cap} → {min_allowed}"
            )
            return min_allowed

        if new_cap > max_allowed:
            self.logger.warning(
                f"{label}: Clamping increase "
                f"{new_cap} → {max_allowed}"
            )
            return max_allowed

        return new_cap


# =============================================================================
# SANITY & HEALTH CHECKS
# =============================================================================

def sanity_check(
    down: float,
    up: float,
    config: Config,
    router: RouterOS,
    measurement: Measurement,
    logger: logging.Logger
) -> Tuple[float, float, float, float]:
    """
    If speeds are suspiciously low, unshape and retest
    Returns: (down, up, down_bloat, up_bloat) - may be updated values
    """
    threshold_down = config.down_max * config.sanity_fraction
    threshold_up = config.up_max * config.sanity_fraction

    if down >= threshold_down and up >= threshold_up:
        return down, up, 0, 0  # Bloat values not used in sanity check

    logger.warning(
        f"Sanity check triggered: DOWN={down:.2f} < {threshold_down:.2f} "
        f"or UP={up:.2f} < {threshold_up:.2f}"
    )
    logger.info("Unshaping and retesting...")

    router.unshape()
    time.sleep(3)

    down2, up2, bloat_down2, bloat_up2 = measurement.run_full_test(
        router=router,
        use_binary_search=config.use_binary_search,
        target_bloat_ms=config.target_bloat_ms
    )

    logger.info(
        f"Sanity retest: DOWN={down2:.2f} UP={up2:.2f}"
    )

    return down2, up2, bloat_down2, bloat_up2


def health_check(
    down: float,
    up: float,
    config: Config,
    logger: logging.Logger
) -> bool:
    """
    Reject implausibly low measurements
    Returns True if healthy, False if should skip update
    """
    threshold_down = config.down_max * config.health_fraction
    threshold_up = config.up_max * config.health_fraction

    if down < threshold_down and up < threshold_up:
        logger.error(
            f"Health check FAILED: DOWN={down:.2f} < {threshold_down:.2f} "
            f"and UP={up:.2f} < {threshold_up:.2f}"
        )
        return False

    return True


# =============================================================================
# MAIN LOGIC
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Adaptive CAKE Auto-Tuning System"
    )
    parser.add_argument(
        "--config",
        required=True,
        help="Path to config YAML file"
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Reset state and unshape"
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging"
    )
    args = parser.parse_args()

    # Load config
    try:
        config = Config(args.config)
    except Exception as e:
        print(f"ERROR: Failed to load config: {e}")
        return 1

    # Setup logging
    logger = setup_logging(config, "cake_auto", args.debug)
    logger.info("="*60)
    logger.info(f"Adaptive CAKE - {config.wan_name}")
    logger.info("="*60)

    # Initialize components
    state_mgr = StateManager(config, logger)
    router = RouterOS(config, logger)
    measurement = Measurement(config, logger)
    adjuster = CakeAdjuster(config, logger)

    # Handle reset
    if args.reset:
        logger.info("RESET requested")
        state_mgr.reset()
        router.unshape()
        logger.info("Reset complete")
        return 0

    # Acquire lock
    try:
        with LockFile(config.lock_file, config.lock_timeout, logger):
            # Check congestion state - defer calibration if network under stress
            # Expert: "Never run Dallas tests while YELLOW or RED"
            if should_skip_calibration(logger, config.steering_state_file):
                logger.info("✓ Calibration skipped this cycle - will retry when GREEN")
                return 0

            state = state_mgr.state
            do_full_search = False

            # Decide: Quick check or full search?
            if not config.quick_check_enabled or not config.use_binary_search:
                # Quick check disabled or not using binary search - always do full test
                do_full_search = True
                logger.info("Quick check disabled - running full search")
            elif state["last_down_cap"] is None or state["last_up_cap"] is None:
                # First run - need full search to find optimal rates
                do_full_search = True
                logger.info("First run - running full search to discover optimal rates")
            elif state["cycles_since_full_search"] >= config.full_search_interval_cycles:
                # Periodic refresh - time for full search
                do_full_search = True
                logger.info(
                    f"Periodic refresh triggered - {state['cycles_since_full_search']} cycles "
                    f"since last full search (interval: {config.full_search_interval_cycles})"
                )
            else:
                # Try quick check first
                logger.info(
                    f"Running quick check (cycle {state['cycles_since_full_search'] + 1}/"
                    f"{config.full_search_interval_cycles})"
                )

                down, up, bloat_down, bloat_up = measurement.quick_check()

                # Check if bloat exceeds threshold
                max_bloat = max(bloat_down, bloat_up)
                if max_bloat > config.quick_check_bloat_threshold:
                    logger.warning(
                        f"Quick check bloat ({max_bloat:.1f}ms) exceeds threshold "
                        f"({config.quick_check_bloat_threshold}ms) - escalating to full search"
                    )
                    do_full_search = True
                else:
                    logger.info(
                        f"Quick check passed - bloat {max_bloat:.1f}ms within threshold "
                        f"({config.quick_check_bloat_threshold}ms)"
                    )

            # Run full search if needed
            if do_full_search:
                # Unshape before measurement to get true capacity
                logger.info("Unshaping queues before full search")
                router.unshape()
                time.sleep(5)  # Wait for queues to drain and link to settle

                # Run binary search to find optimal rates
                down, up, bloat_down, bloat_up = measurement.run_full_test(
                    router=router,
                    use_binary_search=config.use_binary_search,
                    target_bloat_ms=config.target_bloat_ms
                )

                # Reset cycle counter and update timestamp
                state["cycles_since_full_search"] = 0
                state["last_full_search_timestamp"] = datetime.datetime.now().isoformat()
                logger.info("Full search complete - reset cycle counter")
            else:
                # Increment cycle counter (quick check was used)
                state["cycles_since_full_search"] += 1

            # Basic validation
            if down == 0 or up == 0:
                logger.error("Zero throughput measured, skipping update")
                return 1

            # Sanity check
            down, up, bloat_down, bloat_up = sanity_check(
                down, up, config, router, measurement, logger
            )

            # Health check
            if not health_check(down, up, config, logger):
                logger.error("Health check failed, skipping update")
                return 0

            # Outlier detection (skip for full search - those are authoritative)
            max_bloat = max(bloat_down, bloat_up)
            if do_full_search:
                # Full search results are authoritative - bypass outlier detection
                logger.info("Full search result - bypassing outlier detection")
                state_mgr.add_measurement(down, up, max_bloat)
            else:
                # Quick check - apply outlier detection
                if not state_mgr.add_measurement(down, up, max_bloat):
                    logger.warning("Quick check measurement rejected as outlier, skipping update")
                    return 0

            # Update EWMA
            state = state_mgr.state
            if state["ewma_down"] is None:
                # First run - initialize
                state["ewma_down"] = down
                state["ewma_up"] = up
                logger.info("Initialized EWMA with first measurement")
            else:
                # Adaptive alpha based on bloat
                if max_bloat < 5:
                    alpha = config.alpha_good
                    logger.debug("Low bloat - using higher alpha")
                else:
                    alpha = config.alpha

                state["ewma_down"] = (
                    (1 - alpha) * state["ewma_down"] + alpha * down
                )
                state["ewma_up"] = (
                    (1 - alpha) * state["ewma_up"] + alpha * up
                )

            # Clamp EWMA to bounds
            state["ewma_down"] = max(
                config.down_min,
                min(config.down_max, state["ewma_down"])
            )
            state["ewma_up"] = max(
                config.up_min,
                min(config.up_max, state["ewma_up"])
            )

            logger.info(
                f"EWMA: DOWN={state['ewma_down']:.2f} Mbps, "
                f"UP={state['ewma_up']:.2f} Mbps"
            )

            # Compute new caps
            if config.use_binary_search:
                # Binary search already found optimal rates - just convert to bps
                # No k-factor or rate limiting needed (search accounts for bloat)
                down_bps = int(state["ewma_down"] * 1_000_000)
                up_bps = int(state["ewma_up"] * 1_000_000)
                logger.info(
                    f"Binary search caps: DOWN={down_bps} UP={up_bps} "
                    f"(bloat already optimized to <{config.target_bloat_ms}ms)"
                )
            else:
                # Legacy method: use k-factor and rate-of-change limiting
                down_bps, up_bps = adjuster.compute_caps(
                    state["ewma_down"],
                    state["ewma_up"],
                    bloat_down,
                    bloat_up,
                    state["last_down_cap"],
                    state["last_up_cap"]
                )

            # Apply to RouterOS
            if not router.set_limits(down_bps, up_bps):
                logger.error("Failed to apply limits to RouterOS")
                return 1

            # Update state
            state["last_down_cap"] = down_bps
            state["last_up_cap"] = up_bps
            state_mgr.save()

            logger.info("Update complete")
            logger.info("="*60)
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
