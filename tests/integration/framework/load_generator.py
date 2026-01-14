"""Load generation for latency validation tests.

Wraps flent/netperf to generate RRUL (Realtime Response Under Load) traffic.
"""

import shutil
import subprocess
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass
class LoadProfile:
    """Configuration for a load test profile."""

    name: str
    description: str
    tool: str  # "flent", "netperf", "iperf3"
    duration_seconds: int
    warmup_seconds: int = 5
    cooldown_seconds: int = 5
    host: str = "104.200.21.31"
    parameters: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_yaml(cls, path: Path) -> "LoadProfile":
        """Load profile from YAML file."""
        with open(path) as f:
            data = yaml.safe_load(f)
        # Filter out SLA config keys (used by SLAConfig, not LoadProfile)
        profile_keys = {
            "name",
            "description",
            "tool",
            "duration_seconds",
            "warmup_seconds",
            "cooldown_seconds",
            "host",
            "parameters",
        }
        filtered = {k: v for k, v in data.items() if k in profile_keys}
        return cls(**filtered)


@dataclass
class LoadResult:
    """Results from a load generation run."""

    profile: LoadProfile
    start_time: float
    end_time: float
    duration_seconds: float
    success: bool
    output_file: Path | None = None
    error: str | None = None
    throughput_mbps: float | None = None


class LoadGenerator(ABC):
    """Abstract base for load generation tools."""

    @abstractmethod
    def start(self, profile: LoadProfile) -> subprocess.Popen:
        """Start load generation, return process handle."""
        pass

    @abstractmethod
    def wait_and_collect(self, process: subprocess.Popen, profile: LoadProfile) -> LoadResult:
        """Wait for completion and collect results."""
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Check if this tool is installed and working."""
        pass


class FlentGenerator(LoadGenerator):
    """Flent-based RRUL load generation.

    Flent (FLExible Network Tester) runs RRUL tests which generate
    bidirectional TCP traffic with concurrent latency measurement.
    """

    def __init__(self, output_dir: Path | None = None):
        """Initialize flent generator.

        Args:
            output_dir: Directory for flent output files
        """
        self.output_dir = output_dir or Path("/tmp")

    def is_available(self) -> bool:
        """Check if flent is installed."""
        return shutil.which("flent") is not None

    def start(self, profile: LoadProfile) -> subprocess.Popen:
        """Start flent RRUL test."""
        if not self.is_available():
            raise RuntimeError("flent is not installed")

        output_file = self.output_dir / f"flent_{profile.name}_{int(time.time())}.json"

        cmd = [
            "flent",
            profile.parameters.get("test_name", "rrul"),
            "-H",
            profile.host,
            "-l",
            str(profile.duration_seconds),
            "-o",
            str(output_file),
            "--data-dir",
            str(self.output_dir),
        ]

        # Add extra parameters
        for key, value in profile.parameters.items():
            if key == "test_name":
                continue
            if key.startswith("test_parameter_"):
                param_name = key.replace("test_parameter_", "")
                cmd.extend(["--test-parameter", f"{param_name}={value}"])

        return subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    def wait_and_collect(self, process: subprocess.Popen, profile: LoadProfile) -> LoadResult:
        """Wait for flent to complete and collect results."""
        start_time = time.time()

        try:
            stdout, stderr = process.communicate(
                timeout=profile.duration_seconds + profile.warmup_seconds + 60
            )
            success = process.returncode == 0
            error = stderr if not success else None
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
            success = False
            error = "Test timed out"

        end_time = time.time()

        # Find output file
        output_files = list(self.output_dir.glob("flent_*.json"))
        output_file = max(output_files, key=lambda p: p.stat().st_mtime) if output_files else None

        return LoadResult(
            profile=profile,
            start_time=start_time,
            end_time=end_time,
            duration_seconds=end_time - start_time,
            success=success,
            output_file=output_file,
            error=error,
        )


class NetperfGenerator(LoadGenerator):
    """Netperf-based load generation.

    Uses netperf for TCP throughput testing. Less integrated than flent
    but more widely available.
    """

    def __init__(self, output_dir: Path | None = None):
        self.output_dir = output_dir or Path("/tmp")

    def is_available(self) -> bool:
        return shutil.which("netperf") is not None

    def start(self, profile: LoadProfile) -> subprocess.Popen:
        """Start netperf test."""
        if not self.is_available():
            raise RuntimeError("netperf is not installed")

        test_type = profile.parameters.get("test_type", "TCP_STREAM")

        cmd = [
            "netperf",
            "-H",
            profile.host,
            "-l",
            str(profile.duration_seconds),
            "-t",
            test_type,
        ]

        return subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    def wait_and_collect(self, process: subprocess.Popen, profile: LoadProfile) -> LoadResult:
        """Wait for netperf to complete."""
        start_time = time.time()

        try:
            stdout, stderr = process.communicate(timeout=profile.duration_seconds + 30)
            success = process.returncode == 0
            error = stderr if not success else None
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
            success = False
            error = "Test timed out"

        end_time = time.time()

        return LoadResult(
            profile=profile,
            start_time=start_time,
            end_time=end_time,
            duration_seconds=end_time - start_time,
            success=success,
            error=error,
        )


def create_load_generator(output_dir: Path | None = None) -> LoadGenerator:
    """Create appropriate load generator based on available tools.

    Prefers flent for full RRUL support, falls back to netperf.
    """
    flent = FlentGenerator(output_dir)
    if flent.is_available():
        return flent

    netperf = NetperfGenerator(output_dir)
    if netperf.is_available():
        return netperf

    raise RuntimeError("No load generation tool available (tried: flent, netperf)")


def run_load_test(profile: LoadProfile, output_dir: Path | None = None) -> LoadResult:
    """Run a complete load test with the given profile.

    Args:
        profile: Load test configuration
        output_dir: Directory for output files

    Returns:
        LoadResult with test outcome
    """
    generator = create_load_generator(output_dir)
    process = generator.start(profile)
    return generator.wait_and_collect(process, profile)
