"""Calibration measurement functions for WAN link characterization.

Provides connectivity testing, baseline RTT measurement, throughput
measurement, binary search rate optimization, and the CalibrationResult
data model.
"""

import re
import statistics
import subprocess  # nosec B404 - Required for running netperf/ping calibration tools
import time
from dataclasses import dataclass
from typing import Any

from wanctl.rtt_measurement import parse_ping_output
from wanctl.timeouts import (
    DEFAULT_CALIBRATE_PING_TIMEOUT,
    DEFAULT_CALIBRATE_SSH_TIMEOUT,
    TIMEOUT_LONG,
    TIMEOUT_STANDARD,
)

# =============================================================================
# CONSTANTS (duplicated from calibrate.py to avoid circular import)
# =============================================================================

# Test parameters
PING_COUNT = 10
PING_INTERVAL = 0.2
NETPERF_DURATION = 15
BINARY_SEARCH_ITERATIONS = 5


# Console colors
class Colors:
    """ANSI color codes for terminal output formatting.

    Provides color constants for styled console output during calibration.
    Uses standard ANSI escape sequences for terminal color rendering.

    Attributes:
        BLUE: Blue color for section dividers
        CYAN: Cyan color for informational text
        GREEN: Green color for success messages
        YELLOW: Yellow color for warnings
        RED: Red color for errors
        BOLD: Bold text formatting
        END: Reset to default terminal colors
    """

    BLUE = "\033[94m"
    CYAN = "\033[96m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    BOLD = "\033[1m"
    END = "\033[0m"


# =============================================================================
# UI HELPERS (duplicated from calibrate.py to avoid circular import)
# =============================================================================


def print_step(msg: str) -> None:
    """Print a step message."""
    print(f"{Colors.GREEN}[*]{Colors.END} {msg}")


def print_info(msg: str) -> None:
    """Print an info message."""
    print(f"{Colors.CYAN}[i]{Colors.END} {msg}")


def print_warning(msg: str) -> None:
    """Print a warning message."""
    print(f"{Colors.YELLOW}[!]{Colors.END} {msg}")


def print_error(msg: str) -> None:
    """Print an error message."""
    print(f"{Colors.RED}[x]{Colors.END} {msg}")


def print_success(msg: str) -> None:
    """Print a success message."""
    print(f"{Colors.GREEN}[+]{Colors.END} {msg}")


# =============================================================================
# CALIBRATION DATA
# =============================================================================


@dataclass
class CalibrationResult:
    """Results from calibration process."""

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

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
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


def check_ssh_connectivity(host: str, user: str, ssh_key: str | None = None) -> bool:
    """Check SSH connectivity to router."""
    print_step(f"Testing SSH connectivity to {user}@{host}...")

    cmd = ["ssh", "-o", "ConnectTimeout=5", "-o", "BatchMode=yes"]
    if ssh_key:
        cmd.extend(["-i", ssh_key])
    cmd.extend([f"{user}@{host}", "echo ok"])

    try:
        result = subprocess.run(  # nosec B603 - cmd built from config, not user input
            cmd, capture_output=True, text=True, timeout=DEFAULT_CALIBRATE_SSH_TIMEOUT
        )
        if result.returncode == 0 and "ok" in result.stdout:
            print_success("SSH connection successful")
            return True
        print_error(f"SSH connection failed: {result.stderr}")
        return False
    except subprocess.TimeoutExpired:
        print_error("SSH connection timed out")
        return False
    except Exception as e:
        print_error(f"SSH error: {e}")
        return False


def check_netperf_server(host: str) -> bool:
    """Check netperf server connectivity."""
    print_step(f"Testing netperf server at {host}...")

    cmd = ["netperf", "-H", host, "-t", "TCP_STREAM", "-l", "2"]

    try:
        result = subprocess.run(  # nosec B603 - cmd is hardcoded netperf invocation
            cmd, capture_output=True, text=True, timeout=TIMEOUT_STANDARD
        )
        if result.returncode == 0:
            print_success("Netperf server reachable")
            return True
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


def measure_baseline_rtt(ping_host: str) -> float | None:
    """Measure baseline RTT (idle latency)."""
    print_step(f"Measuring baseline RTT to {ping_host}...")

    cmd = ["ping", "-c", str(PING_COUNT), "-i", str(PING_INTERVAL), ping_host]

    try:
        result = subprocess.run(  # nosec B603 - cmd is hardcoded ping invocation
            cmd, capture_output=True, text=True, timeout=TIMEOUT_LONG
        )

        if result.returncode != 0:
            print_error(f"Ping failed: {result.stderr}")
            return None

        # Parse RTT values using unified parser
        rtts = parse_ping_output(result.stdout)

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


def measure_throughput_download(
    netperf_host: str, ping_host: str, baseline_rtt: float
) -> tuple[float, float]:
    """Measure download throughput with latency under load.

    Returns: (throughput_mbps, bloat_ms)
    """
    print_step("Measuring download throughput (latency under load)...")

    # Start netperf in background (TCP_MAERTS = receive from server)
    netperf_cmd = [
        "netperf",
        "-H",
        netperf_host,
        "-t",
        "TCP_MAERTS",
        "-l",
        str(NETPERF_DURATION),
        "-v",
        "2",
    ]

    try:
        netperf_proc = subprocess.Popen(  # nosec B603 - cmd is hardcoded netperf
            netperf_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )

        # Wait for ramp-up
        time.sleep(2)

        # Measure latency under load
        ping_cmd = ["ping", "-c", "30", "-i", "0.2", ping_host]
        ping_result = subprocess.run(  # nosec B603 - cmd is hardcoded ping
            ping_cmd, capture_output=True, text=True, timeout=DEFAULT_CALIBRATE_PING_TIMEOUT
        )

        # Get netperf result
        stdout, stderr = netperf_proc.communicate(timeout=TIMEOUT_LONG)

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

        # Parse loaded RTT using unified parser
        rtts = parse_ping_output(ping_result.stdout)

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


def measure_throughput_upload(
    netperf_host: str, ping_host: str, baseline_rtt: float
) -> tuple[float, float]:
    """Measure upload throughput with latency under load.

    Returns: (throughput_mbps, bloat_ms)
    """
    print_step("Measuring upload throughput (latency under load)...")

    # Start netperf in background (TCP_STREAM = send to server)
    netperf_cmd = [
        "netperf",
        "-H",
        netperf_host,
        "-t",
        "TCP_STREAM",
        "-l",
        str(NETPERF_DURATION),
        "-v",
        "2",
    ]

    try:
        netperf_proc = subprocess.Popen(  # nosec B603 - cmd is hardcoded netperf
            netperf_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )

        # Wait for ramp-up
        time.sleep(2)

        # Measure latency under load
        ping_cmd = ["ping", "-c", "30", "-i", "0.2", ping_host]
        ping_result = subprocess.run(  # nosec B603 - cmd is hardcoded ping
            ping_cmd, capture_output=True, text=True, timeout=DEFAULT_CALIBRATE_PING_TIMEOUT
        )

        # Get netperf result
        stdout, stderr = netperf_proc.communicate(timeout=TIMEOUT_LONG)

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

        # Parse loaded RTT using unified parser
        rtts = parse_ping_output(ping_result.stdout)

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
# CAKE LIMIT CONTROL
# =============================================================================


def set_cake_limit(
    host: str, user: str, queue_name: str, rate_bps: int, ssh_key: str | None = None
) -> bool:
    """Set CAKE queue limit via SSH."""
    cmd = ["ssh", "-o", "ConnectTimeout=5", "-o", "BatchMode=yes"]
    if ssh_key:
        cmd.extend(["-i", ssh_key])
    cmd.extend(
        [f"{user}@{host}", f'/queue/tree set [find name="{queue_name}"] max-limit={rate_bps}']
    )

    try:
        result = subprocess.run(  # nosec B603 - cmd built from config, not user input
            cmd, capture_output=True, text=True, timeout=DEFAULT_CALIBRATE_SSH_TIMEOUT
        )
        return result.returncode == 0
    except Exception as e:
        print_error(f"Failed to set queue rate via SSH: {e}")
        return False


# =============================================================================
# BINARY SEARCH (requires RouterOS SSH)
# =============================================================================


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
    ssh_key: str | None = None,
    iterations: int = BINARY_SEARCH_ITERATIONS,
) -> tuple[float, float]:
    """Binary search for optimal rate that maintains target bloat.

    Returns: (optimal_rate_mbps, final_bloat_ms)
    """
    print_step(f"Binary search for optimal {direction} rate...")
    print_info(f"Target bloat: {target_bloat}ms, range: {min_rate}-{max_rate} Mbps")

    best_rate = min_rate
    best_bloat = 999.0

    for i in range(iterations):
        test_rate = (min_rate + max_rate) / 2
        rate_bps = int(test_rate * 1_000_000)

        print_info(f"  Iteration {i + 1}/{iterations}: Testing {test_rate:.1f} Mbps")

        # Set CAKE limit
        if not set_cake_limit(router_host, router_user, queue_name, rate_bps, ssh_key):
            print_warning("  Failed to set queue limit, skipping iteration")
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
