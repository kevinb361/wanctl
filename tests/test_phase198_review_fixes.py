import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_loaded_window_audit_fails_any_non_queue_health_sample(tmp_path):
    health_path = tmp_path / "health.ndjson"
    psv_path = tmp_path / "metrics.psv"
    output_path = tmp_path / "audit.json"

    with health_path.open("w", encoding="utf-8") as fh:
        for offset in range(30):
            active_primary = "rtt" if offset == 7 else "queue"
            sample = {
                "sampled_utc": 1_000 + offset,
                "wans": [
                    {
                        "name": "spectrum",
                        "signal_arbitration": {
                            "active_primary_signal": active_primary,
                            "refractory_active": False,
                        },
                    }
                ],
            }
            fh.write(json.dumps(sample) + "\n")

    with psv_path.open("w", encoding="utf-8") as fh:
        fh.write("sampled_utc|timestamp|wan_name|metric_name|value\n")
        for offset in range(30):
            timestamp = 1_000 + offset
            fh.write(
                f"2026-05-02T00:00:{offset:02d}Z|{timestamp}|spectrum|"
                "wanctl_arbitration_active_primary|1\n"
            )
            fh.write(
                f"2026-05-02T00:00:{offset:02d}Z|{timestamp}|spectrum|"
                "wanctl_arbitration_refractory_active|0\n"
            )

    result = subprocess.run(
        [
            sys.executable,
            "scripts/phase198-loaded-window-audit.py",
            "--health-ndjson",
            str(health_path),
            "--psv",
            str(psv_path),
            "--flent-window-start",
            "1000",
            "--flent-window-end",
            "1029",
            "--run",
            "1",
            "--output",
            str(output_path),
        ],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 1
    audit = json.loads(output_path.read_text(encoding="utf-8"))
    assert audit["health_non_queue"] == 1
    assert audit["health_non_queue_during_refractory"] == 0
    assert audit["verdict"] == "fail"


def test_rerun_harness_writes_summary_when_health_preflight_fails(tmp_path):
    evidence_root = tmp_path / "evidence"
    output_root = tmp_path / "flent"

    result = subprocess.run(
        [
            "bash",
            "-c",
            """
            git() {
                if [ "$1" = "diff" ]; then
                    return 0
                fi
                command git "$@"
            }
            export -f git
            scripts/phase198-rerun-flent-3run.sh \
                --evidence-root "$1" \
                --output-root "$2" \
                --force-window pytest-health-preflight \
                --health-url http://127.0.0.1:1/health
            """,
            "bash",
            str(evidence_root),
            str(output_root),
        ],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 5
    summary_path = evidence_root / "rerun-attempt-1" / "attempt-summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    assert summary["failed"] is True
    assert summary["failure_stage"] == "health_preflight"
    assert summary["decision"] is None
    assert summary["completed_runs"] == 0


def test_rerun_harness_shell_escapes_remote_db_path():
    script = (REPO_ROOT / "scripts/phase198-rerun-flent-3run.sh").read_text(
        encoding="utf-8"
    )
    assert "REMOTE_DB_Q=\"$(printf '%q' \"${REMOTE_DB}\")\"" in script
    assert "'${REMOTE_DB}'" not in script

    remote_db = "/var/lib/wanctl/metrics-'bad.db"
    result = subprocess.run(
        [
            "bash",
            "-c",
            "REMOTE_DB=$1; REMOTE_DB_Q=$(printf '%q' \"$REMOTE_DB\"); "
            "eval \"set -- $REMOTE_DB_Q\"; printf '%s' \"$1\"",
            "bash",
            remote_db,
        ],
        text=True,
        capture_output=True,
        check=True,
    )
    assert result.stdout == remote_db
