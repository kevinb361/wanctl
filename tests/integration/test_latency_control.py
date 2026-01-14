"""Integration tests for wanctl latency control.

These tests verify that wanctl actually controls latency under load
by running RRUL tests while measuring latency concurrently.

Usage:
    # Quick test (30s) for CI
    pytest tests/integration/test_latency_control.py -k quick -v

    # Standard test (2 min) for full validation
    pytest tests/integration/test_latency_control.py -k standard -v

    # With controller monitoring (requires SSH to cake-spectrum)
    pytest tests/integration/test_latency_control.py -k standard --with-controller -v

Requirements:
    - flent or netperf installed locally
    - fping installed (for latency measurement)
    - Network access to Dallas netperf server (104.200.21.31)
    - SSH access to cake-spectrum (for controller monitoring)
"""

from datetime import datetime
from pathlib import Path

import pytest

from tests.integration.framework import (
    ControllerMonitor,
    LatencyCollector,
    LoadProfile,
    ReportGenerator,
    SLAChecker,
    SLAConfig,
    ValidationReport,
)
from tests.integration.framework.latency_collector import measure_baseline_rtt
from tests.integration.framework.load_generator import create_load_generator


PROFILES_DIR = Path(__file__).parent / "profiles"
DALLAS_HOST = "104.200.21.31"


def pytest_addoption(parser: pytest.Parser) -> None:
    """Add integration test CLI options."""
    parser.addoption(
        "--with-controller",
        action="store_true",
        default=False,
        help="Enable controller monitoring via SSH",
    )


@pytest.fixture
def with_controller(request: pytest.FixtureRequest) -> bool:
    """Get controller monitoring flag from CLI."""
    return request.config.getoption("--with-controller", default=False)


@pytest.fixture
def output_dir(tmp_path: Path) -> Path:
    """Directory for test outputs."""
    return tmp_path


@pytest.fixture
def report_generator(output_dir: Path) -> ReportGenerator:
    """Report generator fixture."""
    return ReportGenerator(output_dir=output_dir)


class TestLatencyControl:
    """Test wanctl latency control effectiveness."""

    def run_validation_test(
        self,
        profile_path: Path,
        output_dir: Path,
        with_controller: bool = False,
    ) -> ValidationReport:
        """Run a complete validation test with the given profile.

        Args:
            profile_path: Path to test profile YAML
            output_dir: Directory for output files
            with_controller: Whether to monitor controller logs

        Returns:
            ValidationReport with all test data
        """
        # Load profile
        profile = LoadProfile.from_yaml(profile_path)
        sla_config = SLAConfig.from_yaml(profile_path)

        # Measure baseline RTT
        print(f"\nMeasuring baseline RTT to {profile.host}...")
        baseline_rtt = measure_baseline_rtt(target=profile.host)
        print(f"Baseline RTT: {baseline_rtt:.1f}ms")

        # Initialize components
        latency_collector = LatencyCollector(
            target=profile.host,
            flat_top_threshold_ms=sla_config.flat_top_threshold_ms,
            flat_top_min_duration_sec=sla_config.flat_top_max_duration_sec,
        )
        sla_checker = SLAChecker(config=sla_config)
        load_generator = create_load_generator(output_dir=output_dir)

        # Optional controller monitoring
        controller_monitor: ControllerMonitor | None = None
        if with_controller:
            controller_monitor = ControllerMonitor()
            if controller_monitor.is_available():
                print("Controller monitoring enabled")
            else:
                print("WARNING: Controller not reachable via SSH, disabling monitoring")
                controller_monitor = None

        # Start collection
        print(f"\nStarting latency collection at 10Hz...")
        latency_collector.start()

        if controller_monitor:
            controller_monitor.start()

        # Run load test
        print(f"Running {profile.name} ({profile.duration_seconds}s)...")
        test_start = datetime.now()
        process = load_generator.start(profile)
        load_result = load_generator.wait_and_collect(process, profile)
        test_end = datetime.now()

        if not load_result.success:
            print(f"WARNING: Load test failed: {load_result.error}")

        # Stop collection
        print("Stopping latency collection...")
        latency_stats = latency_collector.stop()

        # Get controller analysis
        controller_analysis = None
        if controller_monitor:
            print("Fetching controller logs...")
            controller_analysis = controller_monitor.stop()

        # Evaluate SLAs
        print("Evaluating SLAs...")
        sla_evaluation = sla_checker.check_all(
            latency_stats=latency_stats,
            controller_analysis=controller_analysis,
            baseline_rtt_ms=baseline_rtt,
        )

        # Build report
        report = ValidationReport(
            test_name=profile.name,
            timestamp=test_start,
            duration_seconds=(test_end - test_start).total_seconds(),
            overall_passed=sla_evaluation.overall_passed,
            latency_stats=latency_stats,
            sla_evaluation=sla_evaluation,
            load_result=load_result,
            controller_analysis=controller_analysis,
            baseline_rtt_ms=baseline_rtt,
            target_host=profile.host,
        )

        return report

    @pytest.mark.integration
    @pytest.mark.slow
    def test_rrul_quick(
        self,
        output_dir: Path,
        report_generator: ReportGenerator,
        with_controller: bool,
    ) -> None:
        """Quick 30-second RRUL validation test.

        Suitable for CI pipelines. Uses relaxed SLAs.
        """
        profile_path = PROFILES_DIR / "rrul_quick.yaml"
        if not profile_path.exists():
            pytest.skip(f"Profile not found: {profile_path}")

        report = self.run_validation_test(
            profile_path=profile_path,
            output_dir=output_dir,
            with_controller=with_controller,
        )

        # Generate reports
        output_files = report_generator.generate(report)
        print(f"\nReport generated: {output_files.get('markdown')}")

        # Print summary
        self._print_summary(report)

        # Assert SLAs passed
        assert report.overall_passed, self._format_failures(report)

    @pytest.mark.integration
    @pytest.mark.slow
    def test_rrul_standard(
        self,
        output_dir: Path,
        report_generator: ReportGenerator,
        with_controller: bool,
    ) -> None:
        """Standard 2-minute RRUL validation test.

        Full validation with strict SLAs. Use for release validation.
        """
        profile_path = PROFILES_DIR / "rrul_standard.yaml"
        if not profile_path.exists():
            pytest.skip(f"Profile not found: {profile_path}")

        report = self.run_validation_test(
            profile_path=profile_path,
            output_dir=output_dir,
            with_controller=with_controller,
        )

        # Generate reports
        output_files = report_generator.generate(report)
        print(f"\nReport generated: {output_files.get('markdown')}")

        # Print summary
        self._print_summary(report)

        # Assert SLAs passed
        assert report.overall_passed, self._format_failures(report)

    def _print_summary(self, report: ValidationReport) -> None:
        """Print test summary to console."""
        status = "PASSED" if report.overall_passed else "FAILED"
        print(f"\n{'='*60}")
        print(f"TEST {status}: {report.test_name}")
        print(f"{'='*60}")
        print(f"Latency: P50={report.latency_stats.p50_ms:.1f}ms, "
              f"P95={report.latency_stats.p95_ms:.1f}ms, "
              f"P99={report.latency_stats.p99_ms:.1f}ms")
        print(f"Baseline: {report.baseline_rtt_ms:.1f}ms")
        print(f"Samples: {report.latency_stats.successful_samples}/{report.latency_stats.samples}")

        if report.latency_stats.flat_top_detected:
            print(f"WARNING: Flat-top detected ({report.latency_stats.flat_top_duration_sec:.1f}s)")

        if report.controller_analysis:
            ca = report.controller_analysis
            print(f"Controller: {len(ca.state_transitions)} transitions, "
                  f"congestion={'detected' if ca.detected_congestion else 'not detected'}")

        print(f"\nSLA Results:")
        for r in report.sla_evaluation.results:
            status_mark = "[+]" if r.passed else "[X]"
            print(f"  {status_mark} {r.sla_name}: {r.actual} (expected {r.expected})")

    def _format_failures(self, report: ValidationReport) -> str:
        """Format failed SLAs for assertion message."""
        failed = report.sla_evaluation.failed_slas
        if not failed:
            return "Unknown failure"

        lines = ["SLA validation failed:"]
        for r in failed:
            lines.append(f"  - {r.sla_name}: {r.actual} (expected {r.expected})")
        return "\n".join(lines)


# Standalone runner for manual testing
if __name__ == "__main__":
    import sys

    # Default to quick test
    profile_name = sys.argv[1] if len(sys.argv) > 1 else "rrul_quick"
    profile_path = PROFILES_DIR / f"{profile_name}.yaml"

    if not profile_path.exists():
        print(f"Profile not found: {profile_path}")
        sys.exit(1)

    output_dir = Path("/tmp/wanctl_validation")
    output_dir.mkdir(exist_ok=True)

    test = TestLatencyControl()
    report = test.run_validation_test(
        profile_path=profile_path,
        output_dir=output_dir,
        with_controller=True,
    )

    # Generate reports
    generator = ReportGenerator(output_dir=output_dir)
    output_files = generator.generate(report)

    print(f"\nReports generated:")
    for fmt, path in output_files.items():
        print(f"  {fmt}: {path}")

    test._print_summary(report)

    sys.exit(0 if report.overall_passed else 1)
