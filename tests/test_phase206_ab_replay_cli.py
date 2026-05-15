"""CLI tests for scripts/phase206-ab-replay.py."""

from __future__ import annotations

import gzip
import hashlib
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
HARNESS = REPO_ROOT / "scripts" / "phase206-ab-replay.py"
FIXTURE = REPO_ROOT / "tests" / "fixtures" / "phase206_golden_capture.ndjson"
VALID_ZONES = {"GREEN", "YELLOW", "SOFT_RED", "RED"}


def _run_harness(out: Path, *extra: str) -> dict:
    subprocess.run(
        [sys.executable, str(HARNESS), "--out", str(out), *extra],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(out.read_text(encoding="utf-8"))


class TestAbReplayCli:
    def test_smoke_run_writes_schema_v1_summary(self, tmp_path: Path) -> None:
        summary = _run_harness(tmp_path / "ab.json")
        assert summary["schema_version"] == 1
        assert summary["phase"] == 206

    def test_missing_fixture_exits_2(self, tmp_path: Path) -> None:
        result = subprocess.run(
            [
                sys.executable,
                str(HARNESS),
                "--fixture",
                str(tmp_path / "missing.ndjson"),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 2

    def test_fixture_sha256_matches_file(self, tmp_path: Path) -> None:
        expected = hashlib.sha256(FIXTURE.read_bytes()).hexdigest()
        summary = _run_harness(tmp_path / "ab.json")
        assert summary["fixture_sha256"] == expected

    def test_pre_post_have_identical_controller_key_sets(self, tmp_path: Path) -> None:
        summary = _run_harness(tmp_path / "ab.json")
        assert set(summary["pre"].keys()) == set(summary["post"].keys())

    def test_zone_distribution_has_all_four_zones(self, tmp_path: Path) -> None:
        summary = _run_harness(tmp_path / "ab.json")
        assert set(summary["pre"]["zone_distribution"].keys()) == VALID_ZONES
        assert set(summary["post"]["zone_distribution"].keys()) == VALID_ZONES

    def test_default_run_marks_metric_source_controller_replay(self, tmp_path: Path) -> None:
        summary = _run_harness(tmp_path / "ab.json")
        assert summary["meta"]["metric_source"] == "controller_replay"
        assert summary["gates"]["rrul_p99_latency_breach"] is None
        assert "rrul_p99_latency_ms" not in summary["pre"]

    def test_flent_gz_parsing(self, tmp_path: Path) -> None:
        pre = tmp_path / "pre.flent.gz"
        post = tmp_path / "post.flent.gz"
        with gzip.open(pre, "wt") as fh:
            json.dump({"results": {"Ping (ms) ICMP": [20.0, 21.0, 22.0, 23.0, 50.0]}}, fh)
        with gzip.open(post, "wt") as fh:
            json.dump({"results": {"Ping (ms) ICMP": [20.0, 21.0, 22.0, 23.0, 55.0]}}, fh)
        summary = _run_harness(
            tmp_path / "ab.json",
            "--flent-gz-pre",
            str(pre),
            "--flent-gz-post",
            str(post),
        )
        assert summary["meta"]["metric_source"] == "flent"
        assert "rrul_p99_latency_ms" in summary["pre"]
        assert "rrul_p99_latency_ms" in summary["post"]
        assert summary["post"]["rrul_p99_latency_ms"] > summary["pre"]["rrul_p99_latency_ms"]
        assert summary["gates"]["rrul_p99_latency_breach"] is not None

    def test_flent_pair_mismatch_aborts(self, tmp_path: Path) -> None:
        pre = tmp_path / "pre.flent.gz"
        with gzip.open(pre, "wt") as fh:
            json.dump({"results": {"Ping (ms) ICMP": [20.0, 21.0]}}, fh)
        result = subprocess.run(
            [sys.executable, str(HARNESS), "--flent-gz-pre", str(pre)],
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 2
