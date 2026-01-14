"""Report generation for latency validation tests.

Produces JSON and markdown reports from test results.
"""

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from .controller_monitor import ControllerAnalysis
from .latency_collector import LatencyStats
from .load_generator import LoadProfile, LoadResult
from .sla_checker import SLAEvaluation


@dataclass
class ValidationReport:
    """Complete validation test report."""

    # Test identification
    test_name: str
    timestamp: datetime
    duration_seconds: float

    # Results
    overall_passed: bool
    latency_stats: LatencyStats
    sla_evaluation: SLAEvaluation
    load_result: LoadResult
    controller_analysis: ControllerAnalysis | None = None

    # Metadata
    baseline_rtt_ms: float = 0
    target_host: str = ""
    notes: list[str] = field(default_factory=list)


class ReportGenerator:
    """Generate reports from validation test results."""

    def __init__(self, output_dir: Path | None = None):
        """Initialize report generator.

        Args:
            output_dir: Directory for report files. Defaults to /tmp.
        """
        self.output_dir = output_dir or Path("/tmp")
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate(
        self,
        report: ValidationReport,
        formats: list[str] | None = None,
    ) -> dict[str, Path]:
        """Generate reports in specified formats.

        Args:
            report: Validation report data
            formats: List of formats ("json", "markdown"). Defaults to both.

        Returns:
            Dict mapping format to output file path
        """
        if formats is None:
            formats = ["json", "markdown"]

        output_files: dict[str, Path] = {}

        timestamp_str = report.timestamp.strftime("%Y%m%d_%H%M%S")
        base_name = f"wanctl_validation_{report.test_name}_{timestamp_str}"

        if "json" in formats:
            json_path = self.output_dir / f"{base_name}.json"
            self._write_json(report, json_path)
            output_files["json"] = json_path

        if "markdown" in formats:
            md_path = self.output_dir / f"{base_name}.md"
            self._write_markdown(report, md_path)
            output_files["markdown"] = md_path

        return output_files

    def _write_json(self, report: ValidationReport, path: Path) -> None:
        """Write JSON report."""
        data = self._report_to_dict(report)
        with open(path, "w") as f:
            json.dump(data, f, indent=2, default=str)

    def _report_to_dict(self, report: ValidationReport) -> dict[str, Any]:
        """Convert report to JSON-serializable dict."""
        return {
            "test_name": report.test_name,
            "timestamp": report.timestamp.isoformat(),
            "duration_seconds": report.duration_seconds,
            "overall_passed": report.overall_passed,
            "baseline_rtt_ms": report.baseline_rtt_ms,
            "target_host": report.target_host,
            "notes": report.notes,
            "latency": {
                "min_ms": report.latency_stats.min_ms,
                "max_ms": report.latency_stats.max_ms,
                "avg_ms": report.latency_stats.avg_ms,
                "median_ms": report.latency_stats.median_ms,
                "p50_ms": report.latency_stats.p50_ms,
                "p95_ms": report.latency_stats.p95_ms,
                "p99_ms": report.latency_stats.p99_ms,
                "jitter_ms": report.latency_stats.jitter_ms,
                "samples": report.latency_stats.samples,
                "successful_samples": report.latency_stats.successful_samples,
                "loss_pct": report.latency_stats.loss_pct,
                "flat_top_detected": report.latency_stats.flat_top_detected,
                "flat_top_duration_sec": report.latency_stats.flat_top_duration_sec,
            },
            "sla_evaluation": {
                "overall_passed": report.sla_evaluation.overall_passed,
                "results": [
                    {
                        "sla_name": r.sla_name,
                        "passed": r.passed,
                        "expected": r.expected,
                        "actual": r.actual,
                        "message": r.message,
                    }
                    for r in report.sla_evaluation.results
                ],
            },
            "load_test": {
                "profile_name": report.load_result.profile.name,
                "tool": report.load_result.profile.tool,
                "duration_seconds": report.load_result.duration_seconds,
                "success": report.load_result.success,
                "error": report.load_result.error,
            },
            "controller": self._controller_to_dict(report.controller_analysis),
        }

    def _controller_to_dict(
        self, analysis: ControllerAnalysis | None
    ) -> dict[str, Any] | None:
        """Convert controller analysis to dict."""
        if analysis is None:
            return None

        return {
            "transition_count": len(analysis.state_transitions),
            "detected_congestion": analysis.detected_congestion,
            "time_to_first_response_ms": analysis.time_to_first_response_ms,
            "peak_rate_reduction_pct": analysis.peak_rate_reduction_pct,
            "dl_state_distribution": analysis.dl_state_distribution,
            "ul_state_distribution": analysis.ul_state_distribution,
            "rate_range": {
                "dl_min_mbps": analysis.min_dl_rate_mbps,
                "dl_max_mbps": analysis.max_dl_rate_mbps,
                "ul_min_mbps": analysis.min_ul_rate_mbps,
                "ul_max_mbps": analysis.max_ul_rate_mbps,
            },
        }

    def _write_markdown(self, report: ValidationReport, path: Path) -> None:
        """Write markdown report."""
        lines: list[str] = []

        # Header
        status = "PASSED" if report.overall_passed else "FAILED"
        status_emoji = "+" if report.overall_passed else "X"
        lines.append(f"# wanctl Latency Validation Report")
        lines.append("")
        lines.append(f"**Status:** [{status_emoji}] {status}")
        lines.append(f"**Test:** {report.test_name}")
        lines.append(f"**Date:** {report.timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append(f"**Duration:** {report.duration_seconds:.1f}s")
        lines.append(f"**Target:** {report.target_host}")
        lines.append("")

        # Latency Summary
        lines.append("## Latency Summary")
        lines.append("")
        lines.append("| Metric | Value |")
        lines.append("|--------|-------|")
        lines.append(f"| Baseline RTT | {report.baseline_rtt_ms:.1f}ms |")
        lines.append(f"| Average | {report.latency_stats.avg_ms:.1f}ms |")
        lines.append(f"| Median (P50) | {report.latency_stats.median_ms:.1f}ms |")
        lines.append(f"| P95 | {report.latency_stats.p95_ms:.1f}ms |")
        lines.append(f"| P99 | {report.latency_stats.p99_ms:.1f}ms |")
        lines.append(f"| Max | {report.latency_stats.max_ms:.1f}ms |")
        lines.append(f"| Jitter | {report.latency_stats.jitter_ms:.1f}ms |")
        lines.append(f"| Samples | {report.latency_stats.successful_samples}/{report.latency_stats.samples} |")
        lines.append(f"| Packet Loss | {report.latency_stats.loss_pct:.1f}% |")
        lines.append("")

        # Flat-top status
        if report.latency_stats.flat_top_detected:
            lines.append(f"**WARNING:** Flat-top detected ({report.latency_stats.flat_top_duration_sec:.1f}s at >{report.latency_stats.flat_top_threshold_ms:.0f}ms)")
            lines.append("")

        # SLA Results
        lines.append("## SLA Results")
        lines.append("")
        lines.append("| SLA | Expected | Actual | Status |")
        lines.append("|-----|----------|--------|--------|")
        for r in report.sla_evaluation.results:
            status_mark = "[+]" if r.passed else "[X]"
            lines.append(f"| {r.message} | {r.expected} | {r.actual} | {status_mark} |")
        lines.append("")

        # Failed SLAs summary
        failed = report.sla_evaluation.failed_slas
        if failed:
            lines.append("### Failed SLAs")
            lines.append("")
            for r in failed:
                lines.append(f"- **{r.sla_name}**: {r.message}")
                lines.append(f"  - Expected: {r.expected}")
                lines.append(f"  - Actual: {r.actual}")
            lines.append("")

        # Controller Analysis (if available)
        if report.controller_analysis:
            lines.append("## Controller Analysis")
            lines.append("")
            ca = report.controller_analysis
            lines.append(f"- **State Transitions:** {len(ca.state_transitions)}")
            lines.append(f"- **Detected Congestion:** {'Yes' if ca.detected_congestion else 'No'}")
            if ca.time_to_first_response_ms is not None:
                lines.append(f"- **Response Time:** {ca.time_to_first_response_ms:.0f}ms")
            if ca.peak_rate_reduction_pct is not None:
                lines.append(f"- **Peak Rate Reduction:** {ca.peak_rate_reduction_pct:.1f}%")
            lines.append("")

            # State distribution
            if ca.dl_state_distribution:
                lines.append("### Download State Distribution")
                lines.append("")
                for state, pct in sorted(ca.dl_state_distribution.items()):
                    lines.append(f"- {state}: {pct:.1f}%")
                lines.append("")

            if ca.ul_state_distribution:
                lines.append("### Upload State Distribution")
                lines.append("")
                for state, pct in sorted(ca.ul_state_distribution.items()):
                    lines.append(f"- {state}: {pct:.1f}%")
                lines.append("")

            # Rate range
            lines.append("### Rate Range")
            lines.append("")
            if ca.min_dl_rate_mbps is not None:
                lines.append(f"- Download: {ca.min_dl_rate_mbps:.0f}M - {ca.max_dl_rate_mbps:.0f}M")
            if ca.min_ul_rate_mbps is not None:
                lines.append(f"- Upload: {ca.min_ul_rate_mbps:.0f}M - {ca.max_ul_rate_mbps:.0f}M")
            lines.append("")

        # Load Test Info
        lines.append("## Load Test Details")
        lines.append("")
        lines.append(f"- **Profile:** {report.load_result.profile.name}")
        lines.append(f"- **Tool:** {report.load_result.profile.tool}")
        lines.append(f"- **Duration:** {report.load_result.profile.duration_seconds}s")
        lines.append(f"- **Success:** {'Yes' if report.load_result.success else 'No'}")
        if report.load_result.error:
            lines.append(f"- **Error:** {report.load_result.error}")
        lines.append("")

        # Notes
        if report.notes:
            lines.append("## Notes")
            lines.append("")
            for note in report.notes:
                lines.append(f"- {note}")
            lines.append("")

        # Footer
        lines.append("---")
        lines.append("*Generated by wanctl latency validation framework*")

        with open(path, "w") as f:
            f.write("\n".join(lines))
