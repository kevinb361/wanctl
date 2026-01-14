"""SSH-based controller log monitoring for latency validation.

Connects to cake-spectrum via SSH to capture and parse wanctl logs
during load tests. Extracts state transitions and rate changes for
SLA validation.
"""

import re
import subprocess
import time
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class StateTransition:
    """A controller state change event."""

    timestamp: datetime
    dl_state: str  # GREEN, YELLOW, SOFT_RED, RED
    ul_state: str
    rtt_ms: float
    load_ewma_ms: float
    baseline_ms: float
    delta_ms: float
    dl_rate_mbps: float
    ul_rate_mbps: float
    raw_line: str


@dataclass
class ControllerAnalysis:
    """Analysis of controller behavior during test."""

    # State transitions
    state_transitions: list[StateTransition] = field(default_factory=list)

    # Response metrics
    time_to_first_response_ms: float | None = None
    peak_rate_reduction_pct: float | None = None

    # State distribution (percentage of time in each state)
    dl_state_distribution: dict[str, float] = field(default_factory=dict)
    ul_state_distribution: dict[str, float] = field(default_factory=dict)

    # Rate extremes
    min_dl_rate_mbps: float | None = None
    max_dl_rate_mbps: float | None = None
    min_ul_rate_mbps: float | None = None
    max_ul_rate_mbps: float | None = None

    @property
    def detected_congestion(self) -> bool:
        """Whether controller detected congestion (any non-GREEN state)."""
        for t in self.state_transitions:
            if t.dl_state != "GREEN" or t.ul_state != "GREEN":
                return True
        return False


class ControllerMonitor:
    """Monitor controller logs via SSH during load tests.

    Usage:
        monitor = ControllerMonitor(host="cake-spectrum")
        monitor.start()
        # ... run load test ...
        analysis = monitor.stop()
        print(f"Transitions: {len(analysis.state_transitions)}")
    """

    # Log line pattern for autorate output
    # Format: "spectrum: [SOFT_RED/GREEN] RTT=45.2ms, load_ewma=42.1ms, ..."
    LOG_PATTERN = re.compile(
        r"(\w+):\s*\[(\w+)/(\w+)\]\s*"
        r"RTT=([0-9.]+)ms,\s*load_ewma=([0-9.]+)ms,\s*"
        r"baseline=([0-9.]+)ms,\s*delta=([0-9.]+)ms\s*\|\s*"
        r"DL=([0-9.]+)M,\s*UL=([0-9.]+)M"
    )

    # journalctl timestamp format
    TIMESTAMP_PATTERN = re.compile(r"^(\w{3}\s+\d+\s+\d{2}:\d{2}:\d{2})")

    def __init__(
        self,
        host: str = "cake-spectrum",
        wan_name: str = "spectrum",
        service_name: str = "wanctl@spectrum",
    ):
        """Initialize controller monitor.

        Args:
            host: SSH hostname for controller
            wan_name: WAN name to filter in logs
            service_name: Systemd service name for journalctl
        """
        self.host = host
        self.wan_name = wan_name
        self.service_name = service_name

        self._start_time: float | None = None
        self._start_timestamp: str | None = None
        self._entries: list[str] = []

    def start(self) -> None:
        """Mark start of monitoring period."""
        self._start_time = time.time()
        self._start_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self._entries = []

    def stop(self) -> ControllerAnalysis:
        """Stop monitoring and return analysis.

        Fetches logs via SSH and parses them for state transitions.
        """
        if self._start_time is None:
            raise RuntimeError("Monitor not started")

        # Fetch logs since start
        self._entries = self._fetch_logs()

        # Parse and analyze
        return self._analyze_logs()

    def _fetch_logs(self) -> list[str]:
        """Fetch logs from remote controller via SSH."""
        if self._start_timestamp is None:
            return []

        # Use journalctl with --since to get logs from test period
        # Note: sudo required to see system service logs
        cmd = [
            "ssh",
            self.host,
            f"sudo journalctl -u {self.service_name} --since '{self._start_timestamp}' --no-pager",
        ]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode != 0:
                return []
            return result.stdout.strip().split("\n")
        except (subprocess.TimeoutExpired, subprocess.SubprocessError):
            return []

    def _parse_line(self, line: str) -> StateTransition | None:
        """Parse a single log line into a StateTransition."""
        # Extract timestamp
        ts_match = self.TIMESTAMP_PATTERN.match(line)
        if not ts_match:
            return None

        # Parse timestamp (add current year)
        ts_str = ts_match.group(1)
        try:
            # journalctl uses "Jan 14 12:34:56" format
            timestamp = datetime.strptime(
                f"{datetime.now().year} {ts_str}", "%Y %b %d %H:%M:%S"
            )
        except ValueError:
            return None

        # Extract controller state
        match = self.LOG_PATTERN.search(line)
        if not match:
            return None

        wan_name = match.group(1)
        if wan_name != self.wan_name:
            return None

        return StateTransition(
            timestamp=timestamp,
            dl_state=match.group(2),
            ul_state=match.group(3),
            rtt_ms=float(match.group(4)),
            load_ewma_ms=float(match.group(5)),
            baseline_ms=float(match.group(6)),
            delta_ms=float(match.group(7)),
            dl_rate_mbps=float(match.group(8)),
            ul_rate_mbps=float(match.group(9)),
            raw_line=line,
        )

    def _analyze_logs(self) -> ControllerAnalysis:
        """Analyze parsed log entries."""
        transitions: list[StateTransition] = []

        for line in self._entries:
            entry = self._parse_line(line)
            if entry:
                transitions.append(entry)

        if not transitions:
            return ControllerAnalysis()

        # Calculate state distribution
        dl_counts: dict[str, int] = {}
        ul_counts: dict[str, int] = {}
        for t in transitions:
            dl_counts[t.dl_state] = dl_counts.get(t.dl_state, 0) + 1
            ul_counts[t.ul_state] = ul_counts.get(t.ul_state, 0) + 1

        total = len(transitions)
        dl_distribution = {k: v / total * 100 for k, v in dl_counts.items()}
        ul_distribution = {k: v / total * 100 for k, v in ul_counts.items()}

        # Find rate extremes
        dl_rates = [t.dl_rate_mbps for t in transitions]
        ul_rates = [t.ul_rate_mbps for t in transitions]

        # Calculate time to first non-GREEN response
        time_to_first_response: float | None = None
        first_non_green: StateTransition | None = None
        for t in transitions:
            if t.dl_state != "GREEN" or t.ul_state != "GREEN":
                first_non_green = t
                break

        if first_non_green and transitions:
            first_ts = transitions[0].timestamp
            response_ts = first_non_green.timestamp
            time_to_first_response = (response_ts - first_ts).total_seconds() * 1000

        # Calculate peak rate reduction
        peak_reduction: float | None = None
        if dl_rates:
            max_rate = max(dl_rates)
            min_rate = min(dl_rates)
            if max_rate > 0:
                peak_reduction = (max_rate - min_rate) / max_rate * 100

        return ControllerAnalysis(
            state_transitions=transitions,
            time_to_first_response_ms=time_to_first_response,
            peak_rate_reduction_pct=peak_reduction,
            dl_state_distribution=dl_distribution,
            ul_state_distribution=ul_distribution,
            min_dl_rate_mbps=min(dl_rates) if dl_rates else None,
            max_dl_rate_mbps=max(dl_rates) if dl_rates else None,
            min_ul_rate_mbps=min(ul_rates) if ul_rates else None,
            max_ul_rate_mbps=max(ul_rates) if ul_rates else None,
        )

    def is_available(self) -> bool:
        """Check if SSH connection to controller is available."""
        try:
            result = subprocess.run(
                ["ssh", "-o", "ConnectTimeout=5", self.host, "echo ok"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            return result.returncode == 0 and "ok" in result.stdout
        except (subprocess.TimeoutExpired, subprocess.SubprocessError):
            return False
