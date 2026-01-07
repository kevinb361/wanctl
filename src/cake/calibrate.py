#!/usr/bin/env python3
"""
wanctl Calibration Tool

Interactive wizard to discover optimal CAKE bandwidth settings for your connection.
Uses the Flent/LibreQoS methodology: find maximum throughput with acceptable latency.

Usage:
    python -m cake.calibrate --wan-name wan1 --router 192.168.1.1
    python -m cake.calibrate --config /etc/wanctl/wan1.yaml --calibrate

This tool will:
1. Test connectivity to your router
2. Measure baseline RTT (idle latency)
3. Measure raw throughput (unshaped)
4. Binary search for optimal shaped rates
5. Generate a config file with discovered values
"""

import argparse
import json
import os
import re
import signal
import statistics
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple, Dict, Any

import yaml


# =============================================================================
# CONSTANTS
# =============================================================================

# Target bloat for binary search (ms)
DEFAULT_TARGET_BLOAT_MS = 10.0

# Test parameters
PING_COUNT = 10
PING_INTERVAL = 0.2
NETPERF_DURATION = 15
BINARY_SEARCH_ITERATIONS = 5

# Console colors
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BOLD = '\033[1m'
    END = '\033[0m'


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def print_header(msg: str):
    """Print a section header"""
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'=' * 60}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.BLUE}{msg}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'=' * 60}{Colors.END}\n")


def print_step(msg: str):
    """Print a step message"""
    print(f"{Colors.GREEN}[*]{Colors.END} {msg}")


def print_info(msg: str):
    """Print an info message"""
    print(f"{Colors.CYAN}[i]{Colors.END} {msg}")


def print_warning(msg: str):
    """Print a warning message"""
    print(f"{Colors.YELLOW}[!]{Colors.END} {msg}")


def print_error(msg: str):
    """Print an error message"""
    print(f"{Colors.RED}[x]{Colors.END} {msg}")


def print_success(msg: str):
    """Print a success message"""
    print(f"{Colors.GREEN}[+]{Colors.END} {msg}")


def print_result(label: str, value: str, unit: str = ""):
    """Print a result value"""
    print(f"    {Colors.BOLD}{label}:{Colors.END} {Colors.CYAN}{value}{Colors.END} {unit}")


# =============================================================================
# CALIBRATION DATA
# =============================================================================

@dataclass
class CalibrationResult:
    """Results from calibration process"""
    # Connection info
    wan_name: str
    router_host: str
    router_user: str

    # Baseline measurements
    baseline_rtt_ms: float
    raw_download_mbps: float
    raw_upload_mbps: float

    # Optimal rates (from binary search)
    optimal_download_mbps: float
    optimal_upload_mbps: float
    download_bloat_ms: float
    upload_bloat_ms: float

    # Suggested floors (conservative)
    floor_download_mbps: float
    floor_upload_mbps: float

    # Metadata
    timestamp: str
    target_bloat_ms: float

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "wan_name": self.wan_name,
            "router_host": self.router_host,
            "router_user": self.router_user,
            "baseline_rtt_ms": self.baseline_rtt_ms,
            "raw_download_mbps": self.raw_download_mbps,
            "raw_upload_mbps": self.raw_upload_mbps,
            "optimal_download_mbps": self.optimal_download_mbps,
            "optimal_upload_mbps": self.optimal_upload_mbps,
            "download_bloat_ms": self.download_bloat_ms,
            "upload_bloat_ms": self.upload_bloat_ms,
            "floor_download_mbps": self.floor_download_mbps,
            "floor_upload_mbps": self.floor_upload_mbps,
            "timestamp": self.timestamp,
            "target_bloat_ms": self.target_bloat_ms,
        }


# =============================================================================
# CONNECTIVITY TESTS
# =============================================================================

def test_ssh_connectivity(host: str, user: str, ssh_key: Optional[str] = None) -> bool:
    """Test SSH connectivity to router"""
    print_step(f"Testing SSH connectivity to {user}@{host}...")

    cmd = ["ssh", "-o", "ConnectTimeout=5", "-o", "BatchMode=yes"]
    if ssh_key:
        cmd.extend(["-i", ssh_key])
    cmd.extend([f"{user}@{host}", "echo ok"])

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        if result.returncode == 0 and "ok" in result.stdout:
            print_success("SSH connection successful")
            return True
        else:
            print_error(f"SSH connection failed: {result.stderr}")
            return False
    except subprocess.TimeoutExpired:
        print_error("SSH connection timed out")
        return False
    except Exception as e:
        print_error(f"SSH error: {e}")
        return False


def test_netperf_server(host: str) -> bool:
    """Test netperf server connectivity"""
    print_step(f"Testing netperf server at {host}...")

    cmd = ["netperf", "-H", host, "-t", "TCP_STREAM", "-l", "2"]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        if result.returncode == 0:
            print_success("Netperf server reachable")
            return True
        else:
            print_error(f"Netperf test failed: {result.stderr}")
            return False
    except FileNotFoundError:
        print_error("netperf not installed - please install: apt install netperf")
        return False
    except subprocess.TimeoutExpired:
        print_error("Netperf connection timed out")
        return False
    except Exception as e:
        print_error(f"Netperf error: {e}")
        return False


# =============================================================================
# MEASUREMENTS
# =============================================================================

def measure_baseline_rtt(ping_host: str) -> Optional[float]:
    """Measure baseline RTT (idle latency)"""
    print_step(f"Measuring baseline RTT to {ping_host}...")

    cmd = ["ping", "-c", str(PING_COUNT), "-i", str(PING_INTERVAL), ping_host]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

        if result.returncode != 0:
            print_error(f"Ping failed: {result.stderr}")
            return None

        # Parse RTT values
        rtts = []
        for line in result.stdout.splitlines():
            if "time=" in line:
                match = re.search(r"time=([0-9.]+)", line)
                if match:
                    rtts.append(float(match.group(1)))

        if not rtts:
            print_error("No RTT samples collected")
            return None

        # Use minimum RTT as baseline (represents true idle latency)
        baseline = min(rtts)
        median = statistics.median(rtts)

        print_success(f"Baseline RTT: {baseline:.1f}ms (min), {median:.1f}ms (median)")
        return baseline

    except subprocess.TimeoutExpired:
        print_error("Ping timed out")
        return None
    except Exception as e:
        print_error(f"Ping error: {e}")
        return None


def measure_throughput_download(netperf_host: str, ping_host: str, baseline_rtt: float) -> Tuple[float, float]:
    """
    Measure download throughput with latency under load.
    Returns: (throughput_mbps, bloat_ms)
    """
    print_step("Measuring download throughput (latency under load)...")

    # Start netperf in background (TCP_MAERTS = receive from server)
    netperf_cmd = ["netperf", "-H", netperf_host, "-t", "TCP_MAERTS",
                   "-l", str(NETPERF_DURATION), "-v", "2"]

    try:
        netperf_proc = subprocess.Popen(
            netperf_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        # Wait for ramp-up
        time.sleep(2)

        # Measure latency under load
        ping_cmd = ["ping", "-c", "30", "-i", "0.2", ping_host]
        ping_result = subprocess.run(ping_cmd, capture_output=True, text=True, timeout=15)

        # Get netperf result
        stdout, stderr = netperf_proc.communicate(timeout=30)

        # Parse throughput
        throughput = 0.0
        match = re.search(r"\n\s*\d+\s+\d+\s+\d+\s+[0-9.]+\s+([0-9.]+)\s*\n", stdout)
        if match:
            throughput = float(match.group(1))
        else:
            # Fallback patterns
            for pattern in [r"([0-9.]+)\s*Mbps", r"([0-9.]+)\s*10\^6bits/sec"]:
                match = re.search(pattern, stdout)
                if match:
                    throughput = float(match.group(1))
                    break

        # Parse loaded RTT
        rtts = []
        for line in ping_result.stdout.splitlines():
            if "time=" in line:
                match = re.search(r"time=([0-9.]+)", line)
                if match:
                    rtts.append(float(match.group(1)))

        if rtts:
            loaded_rtt = statistics.median(rtts)
            bloat = max(0, loaded_rtt - baseline_rtt)
        else:
            bloat = 0.0

        print_info(f"Download: {throughput:.1f} Mbps, bloat: {bloat:.1f}ms")
        return throughput, bloat

    except Exception as e:
        print_error(f"Download measurement error: {e}")
        return 0.0, 0.0


def measure_throughput_upload(netperf_host: str, ping_host: str, baseline_rtt: float) -> Tuple[float, float]:
    """
    Measure upload throughput with latency under load.
    Returns: (throughput_mbps, bloat_ms)
    """
    print_step("Measuring upload throughput (latency under load)...")

    # Start netperf in background (TCP_STREAM = send to server)
    netperf_cmd = ["netperf", "-H", netperf_host, "-t", "TCP_STREAM",
                   "-l", str(NETPERF_DURATION), "-v", "2"]

    try:
        netperf_proc = subprocess.Popen(
            netperf_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        # Wait for ramp-up
        time.sleep(2)

        # Measure latency under load
        ping_cmd = ["ping", "-c", "30", "-i", "0.2", ping_host]
        ping_result = subprocess.run(ping_cmd, capture_output=True, text=True, timeout=15)

        # Get netperf result
        stdout, stderr = netperf_proc.communicate(timeout=30)

        # Parse throughput
        throughput = 0.0
        match = re.search(r"\n\s*\d+\s+\d+\s+\d+\s+[0-9.]+\s+([0-9.]+)\s*\n", stdout)
        if match:
            throughput = float(match.group(1))
        else:
            for pattern in [r"([0-9.]+)\s*Mbps", r"([0-9.]+)\s*10\^6bits/sec"]:
                match = re.search(pattern, stdout)
                if match:
                    throughput = float(match.group(1))
                    break

        # Parse loaded RTT
        rtts = []
        for line in ping_result.stdout.splitlines():
            if "time=" in line:
                match = re.search(r"time=([0-9.]+)", line)
                if match:
                    rtts.append(float(match.group(1)))

        if rtts:
            loaded_rtt = statistics.median(rtts)
            bloat = max(0, loaded_rtt - baseline_rtt)
        else:
            bloat = 0.0

        print_info(f"Upload: {throughput:.1f} Mbps, bloat: {bloat:.1f}ms")
        return throughput, bloat

    except Exception as e:
        print_error(f"Upload measurement error: {e}")
        return 0.0, 0.0


# =============================================================================
# BINARY SEARCH (requires RouterOS SSH)
# =============================================================================

def set_cake_limit(host: str, user: str, queue_name: str, rate_bps: int,
                   ssh_key: Optional[str] = None) -> bool:
    """Set CAKE queue limit via SSH"""
    cmd = ["ssh", "-o", "ConnectTimeout=5", "-o", "BatchMode=yes"]
    if ssh_key:
        cmd.extend(["-i", ssh_key])
    cmd.extend([f"{user}@{host}",
                f'/queue/tree set [find name="{queue_name}"] max-limit={rate_bps}'])

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        return result.returncode == 0
    except Exception:
        return False


def binary_search_optimal_rate(
    direction: str,  # "download" or "upload"
    netperf_host: str,
    ping_host: str,
    router_host: str,
    router_user: str,
    queue_name: str,
    min_rate: float,
    max_rate: float,
    baseline_rtt: float,
    target_bloat: float,
    ssh_key: Optional[str] = None,
    iterations: int = BINARY_SEARCH_ITERATIONS
) -> Tuple[float, float]:
    """
    Binary search for optimal rate that maintains target bloat.
    Returns: (optimal_rate_mbps, final_bloat_ms)
    """
    print_step(f"Binary search for optimal {direction} rate...")
    print_info(f"Target bloat: {target_bloat}ms, range: {min_rate}-{max_rate} Mbps")

    best_rate = min_rate
    best_bloat = 999.0

    for i in range(iterations):
        test_rate = (min_rate + max_rate) / 2
        rate_bps = int(test_rate * 1_000_000)

        print_info(f"  Iteration {i+1}/{iterations}: Testing {test_rate:.1f} Mbps")

        # Set CAKE limit
        if not set_cake_limit(router_host, router_user, queue_name, rate_bps, ssh_key):
            print_warning(f"  Failed to set queue limit, skipping iteration")
            continue

        time.sleep(1)  # Let queue stabilize

        # Measure throughput and bloat
        if direction == "download":
            throughput, bloat = measure_throughput_download(netperf_host, ping_host, baseline_rtt)
        else:
            throughput, bloat = measure_throughput_upload(netperf_host, ping_host, baseline_rtt)

        print_info(f"    Result: {throughput:.1f} Mbps, bloat: {bloat:.1f}ms")

        if bloat <= target_bloat:
            # Good latency - try higher
            best_rate = test_rate
            best_bloat = bloat
            min_rate = test_rate
            print_info(f"    {Colors.GREEN}Acceptable bloat, trying higher{Colors.END}")
        else:
            # Too much bloat - go lower
            max_rate = test_rate
            print_info(f"    {Colors.YELLOW}Excessive bloat, trying lower{Colors.END}")

    print_success(f"Optimal {direction}: {best_rate:.1f} Mbps (bloat: {best_bloat:.1f}ms)")
    return best_rate, best_bloat


# =============================================================================
# CONFIG GENERATION
# =============================================================================

def generate_config(result: CalibrationResult, output_path: Path) -> bool:
    """Generate wanctl config file from calibration results"""

    # Determine connection type hints based on baseline RTT
    if result.baseline_rtt_ms < 15:
        connection_type = "fiber"
        alpha_baseline = 0.01
    elif result.baseline_rtt_ms < 35:
        connection_type = "cable"
        alpha_baseline = 0.02
    else:
        connection_type = "dsl"
        alpha_baseline = 0.015

    # Calculate thresholds based on baseline
    target_bloat = max(5, result.baseline_rtt_ms * 0.5)
    warn_bloat = max(15, result.baseline_rtt_ms * 1.5)
    hard_red_bloat = max(30, result.baseline_rtt_ms * 3.0)

    config = {
        "wan_name": result.wan_name,
        "router": {
            "type": "routeros",
            "host": result.router_host,
            "user": result.router_user,
            "ssh_key": "/etc/wanctl/ssh/router.key",
        },
        "queues": {
            "download": f"WAN-Download-{result.wan_name.capitalize()}",
            "upload": f"WAN-Upload-{result.wan_name.capitalize()}",
        },
        "continuous_monitoring": {
            "enabled": True,
            "baseline_rtt_initial": round(result.baseline_rtt_ms, 1),
            "download": {
                "floor_green_mbps": round(result.optimal_download_mbps * 0.6, 0),
                "floor_yellow_mbps": round(result.optimal_download_mbps * 0.4, 0),
                "floor_soft_red_mbps": round(result.optimal_download_mbps * 0.3, 0),
                "floor_red_mbps": round(result.floor_download_mbps, 0),
                "ceiling_mbps": round(result.optimal_download_mbps * 1.05, 0),
                "step_up_mbps": max(5, round(result.optimal_download_mbps * 0.01, 0)),
                "factor_down": 0.85,
            },
            "upload": {
                "floor_mbps": round(result.floor_upload_mbps, 0),
                "ceiling_mbps": round(result.optimal_upload_mbps * 1.05, 0),
                "step_up_mbps": max(1, round(result.optimal_upload_mbps * 0.02, 0)),
                "factor_down": 0.90,
            },
            "thresholds": {
                "target_bloat_ms": round(target_bloat, 0),
                "warn_bloat_ms": round(warn_bloat, 0),
                "hard_red_bloat_ms": round(hard_red_bloat, 0),
                "alpha_baseline": alpha_baseline,
                "alpha_load": 0.20,
            },
            "ping_hosts": ["1.1.1.1", "8.8.8.8", "9.9.9.9"],
            "use_median_of_three": True,
        },
        "logging": {
            "main_log": f"/var/log/wanctl/{result.wan_name}.log",
            "debug_log": f"/var/log/wanctl/{result.wan_name}_debug.log",
        },
        "lock_file": f"/run/wanctl/{result.wan_name}.lock",
        "lock_timeout": 300,
        "timeouts": {
            "ssh_command": 15,
            "ping": 1,
        },
        "state_file": f"/var/lib/wanctl/{result.wan_name}_state.json",
    }

    # Add calibration metadata as comment
    header = f"""# wanctl Configuration - {result.wan_name}
#
# Auto-generated by calibration tool on {result.timestamp}
#
# Detected connection type: {connection_type}
# Baseline RTT: {result.baseline_rtt_ms:.1f}ms
# Raw download: {result.raw_download_mbps:.1f} Mbps
# Raw upload: {result.raw_upload_mbps:.1f} Mbps
# Optimal download: {result.optimal_download_mbps:.1f} Mbps (bloat: {result.download_bloat_ms:.1f}ms)
# Optimal upload: {result.optimal_upload_mbps:.1f} Mbps (bloat: {result.upload_bloat_ms:.1f}ms)
#
# IMPORTANT: Review and customize these values for your specific setup.
# Adjust queue names to match your RouterOS configuration.
#

"""

    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, 'w') as f:
            f.write(header)
            yaml.dump(config, f, default_flow_style=False, sort_keys=False)

        print_success(f"Config written to: {output_path}")
        return True
    except Exception as e:
        print_error(f"Failed to write config: {e}")
        return False


# =============================================================================
# MAIN CALIBRATION WIZARD
# =============================================================================

def run_calibration(
    wan_name: str,
    router_host: str,
    router_user: str = "admin",
    ssh_key: Optional[str] = None,
    netperf_host: str = "netperf.bufferbloat.net",
    ping_host: str = "1.1.1.1",
    download_queue: Optional[str] = None,
    upload_queue: Optional[str] = None,
    target_bloat: float = DEFAULT_TARGET_BLOAT_MS,
    output_dir: str = "/etc/wanctl",
    skip_binary_search: bool = False,
) -> Optional[CalibrationResult]:
    """
    Run the full calibration wizard.

    Args:
        wan_name: Name for this WAN (e.g., "wan1")
        router_host: Router IP or hostname
        router_user: SSH username for router
        ssh_key: Path to SSH private key (optional)
        netperf_host: Netperf server hostname
        ping_host: Host to ping for RTT measurements
        download_queue: RouterOS download queue name (for binary search)
        upload_queue: RouterOS upload queue name (for binary search)
        target_bloat: Target bloat for binary search (ms)
        output_dir: Directory for generated config
        skip_binary_search: Skip binary search (measure raw only)

    Returns:
        CalibrationResult or None on failure
    """
    print_header(f"wanctl Calibration - {wan_name}")

    # Default queue names
    if not download_queue:
        download_queue = f"WAN-Download-{wan_name.capitalize()}"
    if not upload_queue:
        upload_queue = f"WAN-Upload-{wan_name.capitalize()}"

    # Step 1: Test connectivity
    print_header("Step 1: Connectivity Tests")

    if not test_ssh_connectivity(router_host, router_user, ssh_key):
        print_error("Router SSH connectivity failed. Please check:")
        print_info("  - Router IP/hostname is correct")
        print_info("  - SSH key is configured (if using key auth)")
        print_info("  - SSH is enabled on router")
        return None

    if not test_netperf_server(netperf_host):
        print_warning("Netperf server not reachable - will measure RTT only")
        skip_throughput = True
    else:
        skip_throughput = False

    # Step 2: Baseline RTT
    print_header("Step 2: Baseline RTT Measurement")

    baseline_rtt = measure_baseline_rtt(ping_host)
    if baseline_rtt is None:
        print_error("Failed to measure baseline RTT")
        return None

    print_result("Baseline RTT", f"{baseline_rtt:.1f}", "ms")

    # Suggest connection type
    if baseline_rtt < 15:
        print_info("Detected: Low-latency connection (fiber)")
    elif baseline_rtt < 35:
        print_info("Detected: Medium-latency connection (cable)")
    else:
        print_info("Detected: Higher-latency connection (DSL)")

    # Step 3: Raw throughput (unshaped)
    if skip_throughput:
        print_header("Step 3: Throughput Measurement (Skipped)")
        print_warning("Netperf not available - using default values")
        raw_download = 100.0
        raw_upload = 20.0
        download_bloat_raw = 0.0
        upload_bloat_raw = 0.0
    else:
        print_header("Step 3: Raw Throughput Measurement")
        print_info("Measuring unshaped throughput (this may cause latency spikes)...")

        raw_download, download_bloat_raw = measure_throughput_download(
            netperf_host, ping_host, baseline_rtt
        )

        time.sleep(3)  # Pause between tests

        raw_upload, upload_bloat_raw = measure_throughput_upload(
            netperf_host, ping_host, baseline_rtt
        )

        print_result("Raw download", f"{raw_download:.1f}", "Mbps")
        print_result("Download bloat", f"{download_bloat_raw:.1f}", "ms")
        print_result("Raw upload", f"{raw_upload:.1f}", "Mbps")
        print_result("Upload bloat", f"{upload_bloat_raw:.1f}", "ms")

    # Step 4: Binary search for optimal rates
    if skip_binary_search or skip_throughput:
        print_header("Step 4: Optimal Rate Discovery (Skipped)")
        print_warning("Using 90% of raw throughput as optimal")
        optimal_download = raw_download * 0.90
        optimal_upload = raw_upload * 0.90
        download_bloat = download_bloat_raw
        upload_bloat = upload_bloat_raw
    else:
        print_header("Step 4: Binary Search for Optimal Rates")
        print_info(f"Finding maximum rates with <{target_bloat}ms bloat...")
        print_info("This will temporarily modify your CAKE queue limits.")

        # Binary search download
        optimal_download, download_bloat = binary_search_optimal_rate(
            direction="download",
            netperf_host=netperf_host,
            ping_host=ping_host,
            router_host=router_host,
            router_user=router_user,
            queue_name=download_queue,
            min_rate=raw_download * 0.3,
            max_rate=raw_download,
            baseline_rtt=baseline_rtt,
            target_bloat=target_bloat,
            ssh_key=ssh_key,
        )

        time.sleep(3)

        # Binary search upload
        optimal_upload, upload_bloat = binary_search_optimal_rate(
            direction="upload",
            netperf_host=netperf_host,
            ping_host=ping_host,
            router_host=router_host,
            router_user=router_user,
            queue_name=upload_queue,
            min_rate=raw_upload * 0.3,
            max_rate=raw_upload,
            baseline_rtt=baseline_rtt,
            target_bloat=target_bloat,
            ssh_key=ssh_key,
        )

        # Reset queues to unshaped
        print_step("Resetting queue limits...")
        set_cake_limit(router_host, router_user, download_queue, 0, ssh_key)
        set_cake_limit(router_host, router_user, upload_queue, 0, ssh_key)

    # Calculate suggested floors (20% of optimal for emergency)
    floor_download = max(10, optimal_download * 0.20)
    floor_upload = max(2, optimal_upload * 0.20)

    # Build result
    result = CalibrationResult(
        wan_name=wan_name,
        router_host=router_host,
        router_user=router_user,
        baseline_rtt_ms=baseline_rtt,
        raw_download_mbps=raw_download,
        raw_upload_mbps=raw_upload,
        optimal_download_mbps=optimal_download,
        optimal_upload_mbps=optimal_upload,
        download_bloat_ms=download_bloat,
        upload_bloat_ms=upload_bloat,
        floor_download_mbps=floor_download,
        floor_upload_mbps=floor_upload,
        timestamp=datetime.now().isoformat(),
        target_bloat_ms=target_bloat,
    )

    # Step 5: Summary and config generation
    print_header("Step 5: Results Summary")

    print_result("Baseline RTT", f"{baseline_rtt:.1f}", "ms")
    print_result("Raw download", f"{raw_download:.1f}", "Mbps")
    print_result("Raw upload", f"{raw_upload:.1f}", "Mbps")
    print_result("Optimal download", f"{optimal_download:.1f}", f"Mbps (bloat: {download_bloat:.1f}ms)")
    print_result("Optimal upload", f"{optimal_upload:.1f}", f"Mbps (bloat: {upload_bloat:.1f}ms)")
    print_result("Suggested floor (download)", f"{floor_download:.1f}", "Mbps")
    print_result("Suggested floor (upload)", f"{floor_upload:.1f}", "Mbps")

    # Generate config
    output_path = Path(output_dir) / f"{wan_name}.yaml"

    print_header("Step 6: Generate Configuration")
    generate_config(result, output_path)

    # Also save raw results as JSON
    results_path = Path(output_dir) / f"{wan_name}_calibration.json"
    try:
        with open(results_path, 'w') as f:
            json.dump(result.to_dict(), f, indent=2)
        print_info(f"Raw results saved to: {results_path}")
    except Exception as e:
        print_warning(f"Could not save raw results: {e}")

    print_header("Calibration Complete!")
    print_info("Next steps:")
    print_info(f"  1. Review the generated config: {output_path}")
    print_info(f"  2. Update queue names to match your RouterOS config")
    print_info(f"  3. Copy SSH key: sudo cp ~/.ssh/router_key /etc/wanctl/ssh/router.key")
    print_info(f"  4. Enable the service: sudo systemctl enable --now wanctl@{wan_name}.timer")

    return result


# =============================================================================
# CLI ENTRY POINT
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="wanctl Calibration Tool - Discover optimal CAKE settings",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --wan-name wan1 --router 192.168.1.1
  %(prog)s --wan-name cable --router 10.10.99.1 --user admin
  %(prog)s --wan-name fiber --router 192.168.1.1 --skip-binary-search
        """
    )

    parser.add_argument("--wan-name", required=True,
                        help="Name for this WAN (e.g., wan1, cable, fiber)")
    parser.add_argument("--router", required=True,
                        help="Router IP or hostname")
    parser.add_argument("--user", default="admin",
                        help="SSH username for router (default: admin)")
    parser.add_argument("--ssh-key",
                        help="Path to SSH private key")
    parser.add_argument("--netperf-host", default="netperf.bufferbloat.net",
                        help="Netperf server hostname")
    parser.add_argument("--ping-host", default="1.1.1.1",
                        help="Host for RTT measurements (default: 1.1.1.1)")
    parser.add_argument("--download-queue",
                        help="RouterOS download queue name")
    parser.add_argument("--upload-queue",
                        help="RouterOS upload queue name")
    parser.add_argument("--target-bloat", type=float, default=DEFAULT_TARGET_BLOAT_MS,
                        help=f"Target bloat for binary search (default: {DEFAULT_TARGET_BLOAT_MS}ms)")
    parser.add_argument("--output-dir", default="/etc/wanctl",
                        help="Directory for generated config (default: /etc/wanctl)")
    parser.add_argument("--skip-binary-search", action="store_true",
                        help="Skip binary search (measure raw throughput only)")

    args = parser.parse_args()

    # Handle Ctrl+C gracefully
    def signal_handler(sig, frame):
        print("\n\nCalibration interrupted.")
        sys.exit(130)

    signal.signal(signal.SIGINT, signal_handler)

    # Run calibration
    result = run_calibration(
        wan_name=args.wan_name,
        router_host=args.router,
        router_user=args.user,
        ssh_key=args.ssh_key,
        netperf_host=args.netperf_host,
        ping_host=args.ping_host,
        download_queue=args.download_queue,
        upload_queue=args.upload_queue,
        target_bloat=args.target_bloat,
        output_dir=args.output_dir,
        skip_binary_search=args.skip_binary_search,
    )

    if result:
        return 0
    else:
        return 1


if __name__ == "__main__":
    sys.exit(main())
