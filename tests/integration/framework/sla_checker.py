"""SLA (Service Level Agreement) evaluation for latency validation.

Defines pass/fail criteria for latency control tests.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

import yaml

if TYPE_CHECKING:
    from .controller_monitor import ControllerAnalysis
    from .latency_collector import LatencyStats


@dataclass
class SLAConfig:
    """SLA threshold configuration."""

    # Latency thresholds
    p95_max_ms: float = 50.0
    p99_max_ms: float = 100.0
    avg_max_ms: float = 30.0
    max_bloat_over_baseline_ms: float = 30.0

    # Flat-top detection
    flat_top_threshold_ms: float = 100.0
    flat_top_max_duration_sec: float = 2.0

    # Controller response
    max_response_time_ms: float = 500.0
    min_rate_reduction_pct: float = 10.0
    require_state_transitions: bool = True

    @classmethod
    def from_yaml(cls, path: Path) -> "SLAConfig":
        """Load SLA config from YAML file."""
        with open(path) as f:
            data = yaml.safe_load(f)

        latency = data.get("latency_slas", {})
        controller = data.get("controller_slas", {})

        return cls(
            p95_max_ms=latency.get("p95_max_ms", cls.p95_max_ms),
            p99_max_ms=latency.get("p99_max_ms", cls.p99_max_ms),
            avg_max_ms=latency.get("avg_max_ms", cls.avg_max_ms),
            max_bloat_over_baseline_ms=latency.get(
                "max_bloat_over_baseline_ms", cls.max_bloat_over_baseline_ms
            ),
            flat_top_threshold_ms=latency.get("flat_top_threshold_ms", cls.flat_top_threshold_ms),
            flat_top_max_duration_sec=latency.get(
                "flat_top_max_duration_sec", cls.flat_top_max_duration_sec
            ),
            max_response_time_ms=controller.get("max_response_time_ms", cls.max_response_time_ms),
            min_rate_reduction_pct=controller.get(
                "min_rate_reduction_pct", cls.min_rate_reduction_pct
            ),
            require_state_transitions=controller.get(
                "require_state_transitions", cls.require_state_transitions
            ),
        )


@dataclass
class SLAResult:
    """Result of a single SLA check."""

    passed: bool
    sla_name: str
    expected: str
    actual: str
    message: str


@dataclass
class SLAEvaluation:
    """Complete SLA evaluation results."""

    overall_passed: bool
    results: list[SLAResult] = field(default_factory=list)

    @property
    def failed_slas(self) -> list[SLAResult]:
        """Return only failed SLAs."""
        return [r for r in self.results if not r.passed]

    @property
    def passed_slas(self) -> list[SLAResult]:
        """Return only passed SLAs."""
        return [r for r in self.results if r.passed]


class SLAChecker:
    """Evaluate test results against SLA criteria."""

    def __init__(self, config: SLAConfig | None = None):
        """Initialize with SLA configuration.

        Args:
            config: SLA thresholds. Uses defaults if not provided.
        """
        self.config = config or SLAConfig()

    def check_all(
        self,
        latency_stats: "LatencyStats",
        controller_analysis: "ControllerAnalysis | None" = None,
        baseline_rtt_ms: float = 0,
    ) -> SLAEvaluation:
        """Run all SLA checks and return evaluation.

        Args:
            latency_stats: Computed latency statistics from test
            controller_analysis: Controller state analysis (optional)
            baseline_rtt_ms: Baseline RTT for bloat calculation

        Returns:
            SLAEvaluation with all check results
        """
        results: list[SLAResult] = []

        # Latency SLAs
        results.extend(self._check_latency_slas(latency_stats, baseline_rtt_ms))

        # Controller SLAs (if analysis provided)
        if controller_analysis is not None:
            results.extend(self._check_controller_slas(controller_analysis))

        overall_passed = all(r.passed for r in results)

        return SLAEvaluation(overall_passed=overall_passed, results=results)

    def _check_latency_slas(self, stats: "LatencyStats", baseline_rtt_ms: float) -> list[SLAResult]:
        """Check latency-related SLAs."""
        results = []

        # P95 latency
        results.append(
            SLAResult(
                passed=stats.p95_ms <= self.config.p95_max_ms,
                sla_name="p95_latency",
                expected=f"<= {self.config.p95_max_ms:.0f}ms",
                actual=f"{stats.p95_ms:.1f}ms",
                message="P95 latency under load",
            )
        )

        # P99 latency
        results.append(
            SLAResult(
                passed=stats.p99_ms <= self.config.p99_max_ms,
                sla_name="p99_latency",
                expected=f"<= {self.config.p99_max_ms:.0f}ms",
                actual=f"{stats.p99_ms:.1f}ms",
                message="P99 latency under load",
            )
        )

        # Average latency
        results.append(
            SLAResult(
                passed=stats.avg_ms <= self.config.avg_max_ms,
                sla_name="avg_latency",
                expected=f"<= {self.config.avg_max_ms:.0f}ms",
                actual=f"{stats.avg_ms:.1f}ms",
                message="Average latency under load",
            )
        )

        # Flat-top detection
        results.append(
            SLAResult(
                passed=not stats.flat_top_detected,
                sla_name="no_flat_top",
                expected=f"No sustained >{self.config.flat_top_threshold_ms:.0f}ms for >{self.config.flat_top_max_duration_sec:.0f}s",
                actual=f"{'DETECTED' if stats.flat_top_detected else 'None'} ({stats.flat_top_duration_sec:.1f}s max)",
                message="Flat-top failure detection (sustained high latency)",
            )
        )

        # Bloat over baseline
        if baseline_rtt_ms > 0:
            bloat = stats.avg_ms - baseline_rtt_ms
            results.append(
                SLAResult(
                    passed=bloat <= self.config.max_bloat_over_baseline_ms,
                    sla_name="bloat_over_baseline",
                    expected=f"<= {self.config.max_bloat_over_baseline_ms:.0f}ms over baseline",
                    actual=f"{bloat:.1f}ms over {baseline_rtt_ms:.1f}ms baseline",
                    message="Added latency over idle baseline",
                )
            )

        # Packet loss (informational, always passes unless total loss)
        results.append(
            SLAResult(
                passed=stats.loss_pct < 100,
                sla_name="connectivity",
                expected="< 100% loss",
                actual=f"{stats.loss_pct:.1f}% loss",
                message="Network connectivity maintained",
            )
        )

        return results

    def _check_controller_slas(self, analysis: "ControllerAnalysis") -> list[SLAResult]:
        """Check controller response SLAs."""
        results = []

        # State transitions occurred
        if self.config.require_state_transitions:
            results.append(
                SLAResult(
                    passed=len(analysis.state_transitions) > 0,
                    sla_name="state_transitions",
                    expected="> 0 transitions",
                    actual=f"{len(analysis.state_transitions)} transitions",
                    message="Controller detected congestion",
                )
            )

        # Response time
        if analysis.time_to_first_response_ms is not None:
            results.append(
                SLAResult(
                    passed=analysis.time_to_first_response_ms <= self.config.max_response_time_ms,
                    sla_name="response_time",
                    expected=f"<= {self.config.max_response_time_ms:.0f}ms",
                    actual=f"{analysis.time_to_first_response_ms:.0f}ms",
                    message="Time from congestion to first rate reduction",
                )
            )

        # Rate reduction occurred
        if analysis.peak_rate_reduction_pct is not None:
            results.append(
                SLAResult(
                    passed=analysis.peak_rate_reduction_pct >= self.config.min_rate_reduction_pct,
                    sla_name="rate_reduction",
                    expected=f">= {self.config.min_rate_reduction_pct:.0f}%",
                    actual=f"{analysis.peak_rate_reduction_pct:.1f}%",
                    message="Controller reduced rate in response to congestion",
                )
            )

        return results
