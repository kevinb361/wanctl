from __future__ import annotations

import json
import os
import signal
import subprocess
import textwrap
import time
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
HARNESS = REPO_ROOT / "scripts" / "silicom-test"
PAIR = "spec-modem"
REAL_SILICOM_BYPASS = "/usr/local/sbin/silicom-bypass"
RESULT_JSON_KEYS = {
    "scenario",
    "pair",
    "started_at",
    "completed_at",
    "exit_code",
    "result_dir",
    "arms_run",
    "snapshots",
    "journal_extract",
}


def _fake_helper(tmp_path: Path, name: str) -> Path:
    helper = tmp_path / name
    helper.write_text(
        textwrap.dedent(
            f"""\
            #!/usr/bin/env bash
            set -euo pipefail
            printf '%s\n' "$*" >> {tmp_path / f'{name}.log'}
            exit 0
            """
        ),
        encoding="utf-8",
    )
    helper.chmod(0o755)
    return helper


def _fake_silicom_bypass(
    tmp_path: Path, fail_on: str | None = None, block_after: str | None = None
) -> tuple[Path, Path]:
    calls_log = tmp_path / "calls.log"
    fake = tmp_path / "silicom-bypass"
    fail_case = fail_on or "__never_fail__"
    block_case = block_after or "${SILICOM_TEST_BLOCK_AFTER:-}"
    fake.write_text(
        textwrap.dedent(
            f"""\
            #!/usr/bin/env bash
            set -euo pipefail

            calls_log={calls_log}
            verb="${{1:-}}"
            printf '%s\n' "$*" >> "$calls_log"

            if [[ "$verb" == "{fail_case}" ]]; then
              printf 'fake silicom-bypass injected failure on %s\n' "$verb" >&2
              exit 70
            fi

            block_after="{block_case}"
            if [[ -n "$block_after" && "$verb" == "$block_after" ]]; then
              while true; do sleep 1; done
            fi

            case "$verb" in
              status)
                printf '%s NIC\n' "${{2:-all}}"
                ;;
              mark)
                printf 'mark: %s\n' "${{*:2}}"
                ;;
            esac
            exit 0
            """
        ),
        encoding="utf-8",
    )
    fake.chmod(0o755)
    return fake, calls_log


def _scenario_dir(tmp_path: Path) -> Path:
    scenarios = tmp_path / "scenarios"
    scenarios.mkdir(exist_ok=True)
    (scenarios / "fixture.sh").write_text(
        textwrap.dedent(
            f"""\
            # sourced by silicom-test chaos fixture
            mark_touched {PAIR}
            "$SILICOM_BYPASS" disc {PAIR} --yes
            "$SILICOM_BYPASS" conn {PAIR}
            """
        ),
        encoding="utf-8",
    )
    return scenarios


def _run(
    tmp_path: Path,
    fake_cli: Path,
    *cli_args: str,
    extra_env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    scenarios = _scenario_dir(tmp_path)
    snapshot = _fake_helper(tmp_path, "snapshot")
    poller = _fake_helper(tmp_path, "health-poller")
    env = {
        **os.environ,
        "SILICOM_BYPASS": str(fake_cli),
        "SILICOM_TEST_SCENARIO_DIR": str(scenarios),
        "SILICOM_TEST_RESULT_ROOT": str(tmp_path / "results"),
        "SILICOM_TEST_SNAPSHOT": str(snapshot),
        "SILICOM_TEST_HEALTH_POLLER": str(poller),
        "PATH": f"{tmp_path}:{os.environ.get('PATH', '')}",
        **(extra_env or {}),
    }
    return subprocess.run(
        ["bash", str(HARNESS), *cli_args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )


def _calls(calls_log: Path) -> list[str]:
    if not calls_log.exists():
        return []
    return calls_log.read_text(encoding="utf-8").splitlines()


def _calls_for(calls: list[str], verb: str) -> list[str]:
    prefix = f"{verb} "
    return [line for line in calls if line == verb or line.startswith(prefix)]


def _assert_after(calls: list[str], later: str, earlier: str) -> None:
    assert earlier in calls
    assert later in calls
    assert calls.index(later) > calls.index(earlier)


def test_failover_inject_and_recover(tmp_path: Path) -> None:
    fake_cli, calls_log = _fake_silicom_bypass(tmp_path)
    result = _run(tmp_path, fake_cli, "failover", PAIR)

    assert result.returncode == 0, result.stderr
    calls = _calls(calls_log)
    assert f"disc {PAIR} --yes" in calls
    assert f"conn {PAIR}" in calls
    _assert_after(calls, f"conn {PAIR}", f"disc {PAIR} --yes")


def test_ab_cake_runs_both_arms(tmp_path: Path) -> None:
    fake_cli, calls_log = _fake_silicom_bypass(tmp_path)
    result = _run(tmp_path, fake_cli, "ab-cake", PAIR)

    assert result.returncode == 0, result.stderr
    calls = _calls(calls_log)
    assert calls.count(f"off {PAIR}") >= 2
    assert f"on {PAIR} --yes" in calls
    assert calls.index(f"off {PAIR}") < calls.index(f"on {PAIR} --yes")
    assert calls[-2:] == [f"off {PAIR}", f"conn {PAIR}"]
    result_dirs = sorted((tmp_path / "results").glob("*-ab-cake-*"))
    assert result_dirs
    assert (result_dirs[-1] / "raw-tool-output" / "A-cake-shaped.txt").exists()
    assert (result_dirs[-1] / "raw-tool-output" / "B-raw-isp.txt").exists()


def test_chaos_dispatch_no_scheduling(tmp_path: Path) -> None:
    fake_cli, calls_log = _fake_silicom_bypass(tmp_path)
    result = _run(tmp_path, fake_cli, "chaos", "fixture")

    assert result.returncode == 0, result.stderr
    assert f"disc {PAIR} --yes" in _calls(calls_log)
    source = HARNESS.read_text(encoding="utf-8")
    scheduling_tokens = ("OnCalendar", "crontab", "systemctl enable", "systemctl start", " at ")
    assert not any(token in source for token in scheduling_tokens)


def test_restore_on_midrun_failure(tmp_path: Path) -> None:
    fake_cli, calls_log = _fake_silicom_bypass(tmp_path, fail_on="probe")
    result = _run(tmp_path, fake_cli, "failover", PAIR, extra_env={"SILICOM_TEST_INJECT_FAIL": "probe"})

    assert result.returncode != 0
    calls = _calls(calls_log)
    assert f"disc {PAIR} --yes" in calls
    _assert_after(calls, f"off {PAIR}", f"disc {PAIR} --yes")
    _assert_after(calls, f"conn {PAIR}", f"disc {PAIR} --yes")


def test_restore_on_signal(tmp_path: Path) -> None:
    fake_cli, calls_log = _fake_silicom_bypass(tmp_path, block_after="disc")
    scenarios = _scenario_dir(tmp_path)
    snapshot = _fake_helper(tmp_path, "snapshot")
    poller = _fake_helper(tmp_path, "health-poller")
    env = {
        **os.environ,
        "SILICOM_BYPASS": str(fake_cli),
        "SILICOM_TEST_SCENARIO_DIR": str(scenarios),
        "SILICOM_TEST_RESULT_ROOT": str(tmp_path / "results"),
        "SILICOM_TEST_SNAPSHOT": str(snapshot),
        "SILICOM_TEST_HEALTH_POLLER": str(poller),
        "SILICOM_TEST_BLOCK_AFTER": "disc",
        "PATH": f"{tmp_path}:{os.environ.get('PATH', '')}",
    }
    proc = subprocess.Popen(
        ["bash", str(HARNESS), "failover", PAIR],
        cwd=REPO_ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
    )
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        if f"disc {PAIR} --yes" in _calls(calls_log):
            break
        if proc.poll() is not None:
            stdout, stderr = proc.communicate()
            pytest.fail(f"harness exited before signal point: rc={proc.returncode} {stdout} {stderr}")
        time.sleep(0.05)
    else:
        proc.kill()
        pytest.fail("harness never reached disc signal point")

    proc.send_signal(signal.SIGTERM)
    proc.wait(timeout=5)
    if proc.stdout is not None:
        proc.stdout.read()
    if proc.stderr is not None:
        proc.stderr.read()
    assert proc.returncode == -15
    calls = _calls(calls_log)
    _assert_after(calls, f"off {PAIR}", f"disc {PAIR} --yes")
    _assert_after(calls, f"conn {PAIR}", f"disc {PAIR} --yes")


def test_live_gate_refuses_real_path(tmp_path: Path) -> None:
    _fake_cli, calls_log = _fake_silicom_bypass(tmp_path)
    # Fake-mode points SILICOM_BYPASS under tmp_path and is exempt; real-mode points at the
    # canonical installed CLI path and must refuse unless the live operator gate is present.
    result = _run(tmp_path, Path(REAL_SILICOM_BYPASS), "failover", PAIR)

    assert result.returncode != 0
    assert "SILICOM_TEST_LIVE_CONFIRM" in f"{result.stdout}\n{result.stderr}"
    calls = _calls(calls_log)
    assert not _calls_for(calls, "disc")
    assert not _calls_for(calls, "on")


def test_att_requires_louder_gate(tmp_path: Path) -> None:
    _fake_cli, calls_log = _fake_silicom_bypass(tmp_path)
    missing_gate = _run(
        tmp_path,
        Path(REAL_SILICOM_BYPASS),
        "failover",
        "att-modem",
        extra_env={"SILICOM_TEST_LIVE_CONFIRM": "1"},
    )
    assert missing_gate.returncode != 0
    assert "SILICOM_TEST_ATT_CONFIRM" in f"{missing_gate.stdout}\n{missing_gate.stderr}"
    assert not _calls_for(_calls(calls_log), "disc")
    both_gates = _run(
        tmp_path,
        Path(REAL_SILICOM_BYPASS),
        "failover",
        "att-modem",
        extra_env={"SILICOM_TEST_LIVE_CONFIRM": "1", "SILICOM_TEST_ATT_CONFIRM": "1"},
    )
    assert "SILICOM_TEST_ATT_CONFIRM" not in f"{both_gates.stdout}\n{both_gates.stderr}"


def test_result_dir_layout(tmp_path: Path) -> None:
    fake_cli, _calls_log = _fake_silicom_bypass(tmp_path)
    result = _run(tmp_path, fake_cli, "failover", PAIR)

    assert result.returncode == 0, result.stderr
    result_dirs = sorted((tmp_path / "results").glob(f"*-failover-{PAIR}"))
    assert result_dirs
    run_dir = result_dirs[-1]
    assert (run_dir / "pre-state").is_dir()
    assert (run_dir / "post-state").is_dir()
    assert (run_dir / "snapshots").is_dir()
    assert (run_dir / "journal.txt").exists()
    result_json = run_dir / "result.json"
    assert result_json.exists()
    result_data = json.loads(result_json.read_text(encoding="utf-8"))
    assert set(result_data) >= RESULT_JSON_KEYS
