"""Tests for the post-deploy canary script."""

import json
import subprocess
from pathlib import Path

CANARY_SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "canary-check.sh"

EXTERNAL_HEALTHY_FIXTURE = {
    "status": "healthy",
    "version": "cake-autorate-trial",
    "revision": "unknown",
    "uptime_seconds": None,
    "source": "cake-autorate-state-bridge",
    "wans": [
        {
            "name": "spectrum",
            "measurement": {"available": True, "staleness_sec": 0.2},
            "download": {"state": "GREEN", "current_rate_mbps": 450.0},
            "upload": {"state": "GREEN", "current_rate_mbps": 30.0},
        }
    ],
}

HEALTHY_FIXTURE = {
    "status": "healthy",
    "version": "1.33.0",
    "revision": "a" * 40,
    "uptime_seconds": 120.5,
    "disk_space": {"status": "ok"},
    "summary": {
        "service": "autorate",
        "status": "healthy",
        "rows": [
            {
                "name": "spectrum",
                "status": "ok",
                "router_reachable": True,
                "download_state": "GREEN",
                "upload_state": "GREEN",
                "storage_status": "ok",
                "runtime_status": "ok",
                "burst_active": False,
                "burst_trigger_count": 0,
            }
        ],
    },
}


def _write_fixture(tmp_path: Path, name: str, data: dict) -> Path:
    path = tmp_path / name
    path.write_text(json.dumps(data))
    return path


def _run_canary(args: list[str], timeout: int = 10) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(CANARY_SCRIPT), *args],
        capture_output=True,
        text=True,
        timeout=timeout,
    )


class TestCanaryHelp:
    def test_help_exits_zero(self) -> None:
        result = _run_canary(["--help"])
        assert result.returncode == 0
        assert "Exit codes:" in result.stdout


class TestCanaryPassFail:
    def test_healthy_exits_zero(self, tmp_path: Path) -> None:
        fixture = _write_fixture(tmp_path, "healthy.json", HEALTHY_FIXTURE)
        result = _run_canary(["--input", str(fixture)])
        assert result.returncode == 0

    def test_external_bridge_health_exits_zero(self, tmp_path: Path) -> None:
        fixture = _write_fixture(tmp_path, "external-healthy.json", EXTERNAL_HEALTHY_FIXTURE)
        result = _run_canary(["--input", str(fixture)])
        assert result.returncode == 0, result.stdout + result.stderr
        assert "RTT measurement available" in result.stdout
        assert "state fresh" in result.stdout

    def test_external_bridge_stale_state_exits_one(self, tmp_path: Path) -> None:
        data = json.loads(json.dumps(EXTERNAL_HEALTHY_FIXTURE))
        data["wans"][0]["measurement"]["staleness_sec"] = 16.0
        fixture = _write_fixture(tmp_path, "external-stale.json", data)
        result = _run_canary(["--input", str(fixture)])
        assert result.returncode == 1
        assert "state stale" in result.stdout

    def test_router_unreachable_exits_one(self, tmp_path: Path) -> None:
        data = json.loads(json.dumps(HEALTHY_FIXTURE))
        data["status"] = "degraded"
        data["summary"]["rows"][0]["router_reachable"] = False
        fixture = _write_fixture(tmp_path, "degraded-router.json", data)
        result = _run_canary(["--input", str(fixture)])
        assert result.returncode == 1

    def test_warning_storage_exits_two(self, tmp_path: Path) -> None:
        data = json.loads(json.dumps(HEALTHY_FIXTURE))
        data["summary"]["rows"][0]["storage_status"] = "warning"
        fixture = _write_fixture(tmp_path, "warning-storage.json", data)
        result = _run_canary(["--input", str(fixture)])
        assert result.returncode == 2

    def test_critical_storage_exits_one(self, tmp_path: Path) -> None:
        data = json.loads(json.dumps(HEALTHY_FIXTURE))
        data["status"] = "degraded"
        data["summary"]["rows"][0]["storage_status"] = "critical"
        fixture = _write_fixture(tmp_path, "critical-storage.json", data)
        result = _run_canary(["--input", str(fixture)])
        assert result.returncode == 1

    def test_critical_runtime_exits_one(self, tmp_path: Path) -> None:
        data = json.loads(json.dumps(HEALTHY_FIXTURE))
        data["status"] = "degraded"
        data["summary"]["rows"][0]["runtime_status"] = "critical"
        fixture = _write_fixture(tmp_path, "critical-runtime.json", data)
        result = _run_canary(["--input", str(fixture)])
        assert result.returncode == 1

    def test_red_download_exits_two(self, tmp_path: Path) -> None:
        data = json.loads(json.dumps(HEALTHY_FIXTURE))
        data["summary"]["rows"][0]["download_state"] = "RED"
        fixture = _write_fixture(tmp_path, "red-download.json", data)
        result = _run_canary(["--input", str(fixture)])
        assert result.returncode == 2

    def test_version_mismatch_warns(self, tmp_path: Path) -> None:
        data = json.loads(json.dumps(HEALTHY_FIXTURE))
        data["version"] = "1.32.0"
        fixture = _write_fixture(tmp_path, "version-mismatch.json", data)
        result = _run_canary(["--input", str(fixture), "--expect-version", "1.33.0"])
        assert result.returncode == 2

    def test_revision_mismatch_warns(self, tmp_path: Path) -> None:
        fixture = _write_fixture(tmp_path, "revision-mismatch.json", HEALTHY_FIXTURE)
        result = _run_canary(["--input", str(fixture), "--expect-revision", "b" * 40])
        assert result.returncode == 2
        assert "revision" in result.stdout


class TestCanaryJson:
    def test_json_output_valid(self, tmp_path: Path) -> None:
        fixture = _write_fixture(tmp_path, "healthy.json", HEALTHY_FIXTURE)
        result = _run_canary(["--input", str(fixture), "--json"])
        assert result.returncode == 0
        parsed = json.loads(result.stdout)
        assert parsed["result"] == "pass"
