from __future__ import annotations

import os
import re
import subprocess
import textwrap
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
CLI = REPO_ROOT / "scripts" / "silicom-bypass"
DEPLOY = REPO_ROOT / "scripts" / "deploy.sh"
INIT_SERVICE = REPO_ROOT / "deploy" / "systemd" / "silicom-bypass-init.service"
BPCTL_SERVICE = REPO_ROOT / "deploy" / "systemd" / "bpctl-silicom.service"
SILICOM_BYPASS_DOC = REPO_ROOT / "docs" / "SILICOM-BYPASS.md"
WATCHDOG_UNIT = REPO_ROOT / "deploy" / "systemd" / "silicom-bypass-watchdog@.service"
WATCHDOG_ATT_ENV = REPO_ROOT / "deploy" / "scripts" / "bpctl-watchdog-att.env.example"
WATCHDOG_SPECTRUM_ENV = REPO_ROOT / "deploy" / "scripts" / "bpctl-watchdog-spectrum.env.example"
WATCHDOG_ATT_CONFLICTS_DROPIN = (
    REPO_ROOT / "deploy" / "systemd" / "silicom-bypass-watchdog@att.service.d" / "conflicts.conf"
)

SILICOM_BYPASS_ARTIFACTS = {
    "scripts/silicom-bypass",
    "scripts/wanctl-bpctl-init",
    "scripts/wanctl-bpctl-watchdog-petter",
    "scripts/wanctl-bpctl-watchdog-bypass",
    "deploy/scripts/silicom-bypass.conf.example",
    "deploy/scripts/bpctl-watchdog-att.env.example",
    "deploy/scripts/bpctl-watchdog-spectrum.env.example",
    "deploy/systemd/silicom-bypass-init.service",
    "deploy/systemd/bpctl-silicom.service",
    "deploy/systemd/silicom-bypass-watchdog@.service",
}

BASELINE_MISMATCHED = {
    "dis_bypass": "on",
    "bypass_pwoff": "off",
    "bypass_pwup": "on",
    "disc_pwup": "on",
    "std_nic": "on",
}

BASELINE_COMPLIANT = {
    "dis_bypass": "off",
    "bypass_pwoff": "on",
    "bypass_pwup": "off",
    "disc_pwup": "off",
    "std_nic": "off",
}

BASELINE_WRITES = [
    "set_dis_bypass off",
    "set_bypass_pwoff on",
    "set_bypass_pwup off",
    "set_disc_pwup off",
    "set_std_nic off",
]


def _fake_logger(tmp_path: Path) -> Path:
    logger = tmp_path / "logger"
    logger_log = tmp_path / "logger.log"
    logger.write_text(
        textwrap.dedent(
            f"""\
            #!/usr/bin/env bash
            printf '%s\n' "$*" >> {logger_log}
            exit 0
            """
        ).lstrip(),
        encoding="utf-8",
    )
    logger.chmod(0o755)
    return logger


def _fake_bpctl(
    tmp_path: Path, slave_overrides: dict[str, str] | None = None
) -> tuple[Path, Path]:
    calls_log = tmp_path / "calls.log"
    state_dir = tmp_path / "state"
    state_dir.mkdir(exist_ok=True)
    overrides = slave_overrides or {}
    override_cases = "\n".join(
        f'  {iface}) printf \'%s\\n\' "{slave}"; exit 0 ;;'
        for iface, slave in sorted(overrides.items())
    )
    fake = tmp_path / "bpctl_util"
    fake.write_text(
        textwrap.dedent(
            f"""\
            #!/usr/bin/env bash
            set -euo pipefail

            calls_log={calls_log}
            state_dir={state_dir}
            iface="${{1:-}}"
            verb="${{2:-}}"
            value="${{3:-}}"
            printf '%s\n' "$*" >> "$calls_log"

            read_state() {{
              local key="$1" default="$2" path
              path="$state_dir/$iface.$key"
              if [[ -f "$path" ]]; then
                cat "$path"
              else
                printf '%s\n' "$default"
              fi
            }}

            write_state() {{
              local key="$1" next="$2"
              printf '%s\n' "$next" > "$state_dir/$iface.$key"
            }}

            case "$verb" in
              get_bypass_slave)
                case "$iface" in
{override_cases}
                  att-modem) printf '%s\n' 'att-router' ;;
                  spec-modem) printf '%s\n' 'spec-router' ;;
                  *) printf '%s\n' '' ;;
                esac
                ;;
              set_bypass) write_state bypass "$value" ;;
              get_bypass)
                case "$(read_state bypass off)" in
                  on) printf '%s\n' 'Bypass' ;;
                  *) printf '%s\n' 'non-Bypass' ;;
                esac
                ;;
              set_disc) write_state disc "$value" ;;
              get_disc)
                case "$(read_state disc off)" in
                  on) printf '%s\n' 'Disconnect' ;;
                  *) printf '%s\n' 'non-Disconnect' ;;
                esac
                ;;
              set_std_nic)
                if [[ "${{STUCK_SET_STD_NIC_IFACE:-}}" != "$iface" ]]; then
                  write_state std_nic "$value"
                fi
                ;;
              get_std_nic)
                case "$(read_state std_nic off)" in
                  on) printf '%s\n' 'Standard NIC' ;;
                  *) printf '%s\n' 'not in Standard NIC mode' ;;
                esac
                ;;
              set_dis_bypass) write_state dis_bypass "$value" ;;
              get_dis_bypass)
                case "$(read_state dis_bypass on)" in
                  off) printf '%s\n' "${{DIS_BYPASS_ENABLED_TEXT:-Bypass mode enabled}}" ;;
                  *) printf '%s\n' 'Bypass mode disabled' ;;
                esac
                ;;
              set_bypass_pwoff) write_state bypass_pwoff "$value" ;;
              get_bypass_pwoff)
                case "$(read_state bypass_pwoff off)" in
                  on) printf '%s\n' "${{BYPASS_PWOFF_ON_TEXT:-Bypass at power off}}" ;;
                  *) printf '%s\n' 'non-Bypass at power off' ;;
                esac
                ;;
              set_bypass_pwup) write_state bypass_pwup "$value" ;;
              get_bypass_pwup)
                case "$(read_state bypass_pwup on)" in
                  on) printf '%s\n' 'Bypass at power up' ;;
                  *) printf '%s\n' 'non-Bypass at power up' ;;
                esac
                ;;
              set_disc_pwup) write_state disc_pwup "$value" ;;
              get_disc_pwup)
                case "$(read_state disc_pwup on)" in
                  on) printf '%s\n' 'Disconnect at power up' ;;
                  *) printf '%s\n' 'non-Disconnect at power up' ;;
                esac
                ;;
              set_wd_exp_mode) write_state wd_exp_mode "$value" ;;
              set_wd_autoreset) write_state wd_autoreset "$value" ;;
              set_bypass_wd)
                write_state wd_armed_ms "$value"
                if [[ "$value" == "0" ]]; then
                  write_state wd_armed off
                else
                  write_state wd_armed on
                fi
                ;;
              reset_bypass_wd)
                current="$(read_state wd_last_pet 0)"
                write_state wd_last_pet "$((current + 1))"
                ;;
              get_bypass_wd) printf '%s\n' "$(read_state wd_armed_ms 0)" ;;
              get_wd_exp_mode) printf '%s\n' "$(read_state wd_exp_mode unknown)" ;;
              *)
                printf 'unknown fake bpctl verb: %s\n' "$verb" >&2
                exit 64
                ;;
            esac
            """
        ).lstrip(),
        encoding="utf-8",
    )
    fake.chmod(0o755)
    return fake, calls_log


def _fake_systemctl(tmp_path: Path, fake_bpctl: Path) -> Path:
    systemctl = tmp_path / "systemctl"
    systemctl_log = tmp_path / "systemctl.log"
    unit_state_dir = tmp_path / "systemctl-state"
    unit_state_dir.mkdir(exist_ok=True)
    bypass_script = REPO_ROOT / "scripts" / "wanctl-bpctl-watchdog-bypass"
    systemctl.write_text(
        textwrap.dedent(
            f"""\
            #!/usr/bin/env bash
            set -euo pipefail

            systemctl_log={systemctl_log}
            unit_state_dir={unit_state_dir}
            bypass_script={bypass_script}
            fake_bpctl={fake_bpctl}

            printf '%s\n' "$*" >> "$systemctl_log"

            sanitize_unit() {{
              printf '%s' "$1" | sed 's/[^A-Za-z0-9]/_/g'
            }}

            state_for() {{
              local unit="$1" key env_name path
              key="$(sanitize_unit "$unit")"
              env_name="FAKE_SYSTEMCTL_${{key}}_STATE"
              path="$unit_state_dir/$key.state"
              if [[ -n "${{!env_name:-}}" ]]; then
                printf '%s\n' "${{!env_name}}"
              elif [[ -f "$path" ]]; then
                cat "$path"
              else
                printf '%s\n' inactive
              fi
            }}

            write_state() {{
              local unit="$1" state="$2" key
              key="$(sanitize_unit "$unit")"
              printf '%s\n' "$state" > "$unit_state_dir/$key.state"
            }}

            iface_for_unit() {{
              local unit="$1"
              case "$unit" in
                *silicom-bypass-watchdog@att.service|*silicom-bypass-watchdog@att) printf '%s\n' att-modem ;;
                *silicom-bypass-watchdog-cake-autorate-att.service) printf '%s\n' att-modem ;;
                *silicom-bypass-watchdog@spectrum.service|*silicom-bypass-watchdog@spectrum) printf '%s\n' spec-modem ;;
                *) printf '%s\n' '' ;;
              esac
            }}

            run_exec_stop() {{
              local unit="$1" iface
              iface="$(iface_for_unit "$unit")"
              [[ -n "$iface" ]] || return 0
              IFACE="$iface" BPCTL_UTIL="$fake_bpctl" WD_RUN_DIR="${{WD_RUN_DIR:-/run/wanctl/bpctl-watchdog}}" "$bypass_script"
            }}

            if [[ "${{1:-}}" == is-active && "${{2:-}}" == --quiet ]]; then
              exit "${{FAKE_SYSTEMCTL_RC:-0}}"
            fi

            if [[ "${{1:-}}" == is-active ]]; then
              state="$(state_for "${{2:-}}")"
              printf '%s\n' "$state"
              [[ "$state" == active || "$state" == activating ]]
              exit $?
            fi

            verb="${{1:-}}"
            unit="${{@: -1}}"
            rc=0
            case "$verb" in
              stop)
                run_exec_stop "$unit"
                rc="${{FAKE_SYSTEMCTL_DISABLE_RC:-0}}"
                [[ "$rc" == 0 ]] && write_state "$unit" inactive
                exit "$rc"
                ;;
              disable)
                if [[ "${{2:-}}" == --now ]]; then
                  run_exec_stop "$unit"
                  rc="${{FAKE_SYSTEMCTL_DISABLE_RC:-0}}"
                  [[ "$rc" == 0 ]] && write_state "$unit" inactive
                  exit "$rc"
                fi
                exit "${{FAKE_SYSTEMCTL_DISABLE_RC:-0}}"
                ;;
              mask)
                if [[ "${{2:-}}" == --now ]]; then
                  run_exec_stop "$unit"
                  rc="${{FAKE_SYSTEMCTL_DISABLE_RC:-0}}"
                  [[ "$rc" == 0 ]] && write_state "$unit" inactive
                  exit "$rc"
                fi
                exit 0
                ;;
              start)
                write_state "$unit" active
                exit 0
                ;;
              enable)
                if [[ "${{2:-}}" == --now ]]; then
                  write_state "$unit" active
                fi
                exit 0
                ;;
              restart)
                run_exec_stop "$unit"
                write_state "$unit" active
                exit 0
                ;;
              *) exit 0 ;;
            esac
            """
        ),
        encoding="utf-8",
    )
    systemctl.chmod(0o755)
    return systemctl


def _prime(tmp_path: Path, iface: str, key: str, value: str) -> None:
    state_dir = tmp_path / "state"
    state_dir.mkdir(exist_ok=True)
    (state_dir / f"{iface}.{key}").write_text(f"{value}\n", encoding="utf-8")


def _prime_baseline(tmp_path: Path, iface: str, state: dict[str, str]) -> None:
    for key, value in state.items():
        _prime(tmp_path, iface, key, value)


def _calls_for(calls: str, iface: str) -> list[str]:
    prefix = f"{iface} "
    return [line[len(prefix) :] for line in calls.splitlines() if line.startswith(prefix)]


def _run(
    tmp_path: Path,
    fake: Path,
    *cli_args: str,
    extra_env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    logger = _fake_logger(tmp_path)
    systemctl = _fake_systemctl(tmp_path, fake)
    env = {
        **os.environ,
        "BPCTL_UTIL": str(fake),
        "PAIRS": "att-modem spec-modem",
        "SILICOM_BYPASS_CONF": "/dev/null",
        "SILICOM_MARKS_LOG": str(tmp_path / "marks.log"),
        "LOGGER": str(logger),
        "SYSTEMCTL": str(systemctl),
        "PATH": f"{tmp_path}:{os.environ.get('PATH', '')}",
        **(extra_env or {}),
    }
    return subprocess.run(
        ["bash", str(CLI), *cli_args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        env=env,
    )


def _calls(calls_log: Path) -> str:
    return calls_log.read_text(encoding="utf-8") if calls_log.exists() else ""


def _watchdog_env_dirs(tmp_path: Path) -> tuple[Path, Path]:
    env_dir = tmp_path / "wd-env"
    run_dir = tmp_path / "wd-run"
    env_dir.mkdir(exist_ok=True)
    run_dir.mkdir(exist_ok=True)
    return env_dir, run_dir


def _seed_watchdog_env(env_dir: Path, instance: str, iface: str, unit: str) -> Path:
    path = env_dir / f"{instance}.env"
    path.write_text(f"IFACE={iface}\nWANCTL_UNIT={unit}\n", encoding="utf-8")
    return path


def _watchdog_extra_env(env_dir: Path, run_dir: Path, **extra: str) -> dict[str, str]:
    return {"WD_ENV_DIR": str(env_dir), "WD_RUN_DIR": str(run_dir), **extra}


def _systemctl_calls(tmp_path: Path) -> str:
    path = tmp_path / "systemctl.log"
    return path.read_text(encoding="utf-8") if path.exists() else ""


def test_status_reads_live(tmp_path: Path) -> None:
    fake, calls_log = _fake_bpctl(tmp_path)

    result = _run(tmp_path, fake, "status", "att-modem")
    assert result.returncode == 0, (result.stdout, result.stderr)
    calls = _calls(calls_log)
    assert "att-modem get_bypass" in calls
    assert "att-modem get_disc" in calls
    assert "att-modem get_std_nic" in calls

    calls_log.unlink()
    result = _run(tmp_path, fake, "status", "att-modem")
    assert result.returncode == 0, (result.stdout, result.stderr)
    calls = _calls(calls_log)
    assert "att-modem get_bypass" in calls
    assert "att-modem get_disc" in calls
    assert "att-modem get_std_nic" in calls


def test_off_idempotent_noop(tmp_path: Path) -> None:
    fake, calls_log = _fake_bpctl(tmp_path)

    result = _run(tmp_path, fake, "off", "att-modem")
    assert result.returncode == 0, (result.stdout, result.stderr)
    assert "no-op" in result.stdout
    assert "set_bypass off" not in _calls(calls_log)


def test_on_requires_yes(tmp_path: Path) -> None:
    fake, calls_log = _fake_bpctl(tmp_path)

    result = _run(tmp_path, fake, "on", "att-modem")
    assert result.returncode != 0
    assert "set_bypass on" not in _calls(calls_log)

    result = _run(tmp_path, fake, "on", "att-modem", "--yes")
    assert result.returncode == 0, (result.stdout, result.stderr)
    assert "set_bypass on" in _calls(calls_log)

    result = _run(tmp_path, fake, "status", "att-modem")
    assert result.returncode == 0, (result.stdout, result.stderr)
    assert "Bypass" in result.stdout


def test_disc_requires_yes_and_applies(tmp_path: Path) -> None:
    fake, calls_log = _fake_bpctl(tmp_path)

    result = _run(tmp_path, fake, "disc", "att-modem")
    assert result.returncode != 0
    assert "set_disc on" not in _calls(calls_log)

    result = _run(tmp_path, fake, "disc", "att-modem", "--yes")
    assert result.returncode == 0, (result.stdout, result.stderr)
    assert "set_disc on" in _calls(calls_log)

    result = _run(tmp_path, fake, "status", "att-modem")
    assert result.returncode == 0, (result.stdout, result.stderr)
    assert "Disconnect" in result.stdout


def test_disc_idempotent_noop(tmp_path: Path) -> None:
    fake, calls_log = _fake_bpctl(tmp_path)

    result = _run(tmp_path, fake, "disc", "att-modem", "--yes")
    assert result.returncode == 0, (result.stdout, result.stderr)
    result = _run(tmp_path, fake, "disc", "att-modem", "--yes")
    assert result.returncode == 0, (result.stdout, result.stderr)
    assert "no-op" in result.stdout
    assert _calls(calls_log).count("set_disc on") == 1


def test_conn_idempotent_noop(tmp_path: Path) -> None:
    fake, calls_log = _fake_bpctl(tmp_path)

    result = _run(tmp_path, fake, "conn", "att-modem")
    assert result.returncode == 0, (result.stdout, result.stderr)
    assert "no-op" in result.stdout
    assert "set_disc off" not in _calls(calls_log)


def test_refuses_non_pair_iface(tmp_path: Path) -> None:
    fake, calls_log = _fake_bpctl(tmp_path)

    result = _run(tmp_path, fake, "status", "eth99")
    assert result.returncode != 0
    assert "eth99" in result.stderr
    assert "set_" not in _calls(calls_log)


def test_refuses_not_capable_iface(tmp_path: Path) -> None:
    fake, calls_log = _fake_bpctl(tmp_path, slave_overrides={"spec-modem": ""})

    result = _run(tmp_path, fake, "status", "spec-modem")
    assert result.returncode != 0
    assert "spec-modem" in result.stderr
    assert "bypass-capable" in result.stderr
    assert "set_" not in _calls(calls_log)


def test_both_wan_confirm_gate_bypass(tmp_path: Path) -> None:
    fake, _calls_log = _fake_bpctl(tmp_path)

    result = _run(tmp_path, fake, "on", "att-modem", "--yes")
    assert result.returncode == 0, (result.stdout, result.stderr)
    result = _run(tmp_path, fake, "on", "spec-modem", "--yes")
    assert result.returncode != 0
    assert "both" in result.stderr.lower()
    result = _run(tmp_path, fake, "on", "spec-modem", "--yes", "--both-wan-confirm")
    assert result.returncode == 0, (result.stdout, result.stderr)


def test_both_wan_confirm_gate_disconnect(tmp_path: Path) -> None:
    fake, _calls_log = _fake_bpctl(tmp_path)

    result = _run(tmp_path, fake, "disc", "att-modem", "--yes")
    assert result.returncode == 0, (result.stdout, result.stderr)
    result = _run(tmp_path, fake, "disc", "spec-modem", "--yes")
    assert result.returncode != 0
    assert "both" in result.stderr.lower()
    result = _run(tmp_path, fake, "disc", "spec-modem", "--yes", "--both-wan-confirm")
    assert result.returncode == 0, (result.stdout, result.stderr)


def test_mark_appends_log_and_journals(tmp_path: Path) -> None:
    fake, _calls_log = _fake_bpctl(tmp_path)

    result = _run(tmp_path, fake, "mark", "soak-start-1")
    assert result.returncode == 0, (result.stdout, result.stderr)
    assert "soak-start-1" in (tmp_path / "marks.log").read_text(encoding="utf-8")
    assert "soak-start-1" in (tmp_path / "logger.log").read_text(encoding="utf-8")


def test_baseline_applies_and_asserts(tmp_path: Path) -> None:
    fake, calls_log = _fake_bpctl(tmp_path)
    for iface in ("att-modem", "spec-modem"):
        _prime_baseline(tmp_path, iface, BASELINE_MISMATCHED)

    result = _run(tmp_path, fake, "baseline")
    assert result.returncode == 0, (result.stdout, result.stderr)
    calls = _calls(calls_log)

    for iface in ("att-modem", "spec-modem"):
        iface_calls = _calls_for(calls, iface)
        assert iface_calls[0] == "get_bypass_slave"
        for write in BASELINE_WRITES:
            assert write in iface_calls
        assert "get_dis_bypass" in iface_calls
        assert "get_bypass_pwoff" in iface_calls
        assert "get_bypass_pwup" in iface_calls
        assert "get_disc_pwup" in iface_calls
        assert "get_std_nic" in iface_calls


def test_baseline_read_before_set_skips_writes(tmp_path: Path) -> None:
    fake, calls_log = _fake_bpctl(tmp_path)
    _prime_baseline(tmp_path, "att-modem", BASELINE_COMPLIANT)
    _prime_baseline(tmp_path, "spec-modem", BASELINE_MISMATCHED)

    result = _run(tmp_path, fake, "baseline")
    assert result.returncode == 0, (result.stdout, result.stderr)
    calls = _calls(calls_log)

    att_calls = _calls_for(calls, "att-modem")
    spec_calls = _calls_for(calls, "spec-modem")
    assert not any(call.startswith("set_") for call in att_calls)
    for write in BASELINE_WRITES:
        assert write in spec_calls


def test_baseline_accepts_live_dis_bypass_wording(tmp_path: Path) -> None:
    fake, calls_log = _fake_bpctl(tmp_path)
    _prime_baseline(tmp_path, "att-modem", BASELINE_COMPLIANT)
    _prime_baseline(tmp_path, "spec-modem", BASELINE_COMPLIANT)

    result = _run(
        tmp_path,
        fake,
        "baseline",
        extra_env={"DIS_BYPASS_ENABLED_TEXT": "Bypass mode is enabled."},
    )
    assert result.returncode == 0, (result.stdout, result.stderr)
    calls = _calls(calls_log)

    for iface in ("att-modem", "spec-modem"):
        iface_calls = _calls_for(calls, iface)
        assert "get_dis_bypass" in iface_calls
        assert "set_dis_bypass off" not in iface_calls


def test_baseline_accepts_live_bypass_pwoff_wording(tmp_path: Path) -> None:
    fake, calls_log = _fake_bpctl(tmp_path)
    _prime_baseline(tmp_path, "att-modem", BASELINE_COMPLIANT)
    _prime_baseline(tmp_path, "spec-modem", BASELINE_COMPLIANT)

    result = _run(
        tmp_path,
        fake,
        "baseline",
        extra_env={
            "BYPASS_PWOFF_ON_TEXT": "The interface is in the Bypass mode at power off state."
        },
    )
    assert result.returncode == 0, (result.stdout, result.stderr)
    calls = _calls(calls_log)

    for iface in ("att-modem", "spec-modem"):
        iface_calls = _calls_for(calls, iface)
        assert "get_bypass_pwoff" in iface_calls
        assert "set_bypass_pwoff on" not in iface_calls


def test_baseline_fails_on_mismatch(tmp_path: Path) -> None:
    fake, calls_log = _fake_bpctl(tmp_path)
    _prime_baseline(tmp_path, "att-modem", BASELINE_MISMATCHED)

    result = _run(
        tmp_path,
        fake,
        "baseline",
        extra_env={"STUCK_SET_STD_NIC_IFACE": "att-modem"},
    )
    assert result.returncode != 0
    assert "att-modem" in result.stderr
    assert "get_std_nic" in result.stderr
    assert "read-back FAILED" in result.stderr
    assert "att-modem set_std_nic off" in _calls(calls_log)


def test_baseline_refuses_pair_never_capable(tmp_path: Path) -> None:
    fake, calls_log = _fake_bpctl(tmp_path, slave_overrides={"spec-modem": ""})
    _prime_baseline(tmp_path, "att-modem", BASELINE_COMPLIANT)
    _prime_baseline(tmp_path, "spec-modem", BASELINE_MISMATCHED)

    result = _run(
        tmp_path,
        fake,
        "baseline",
        extra_env={"SILICOM_READY_TIMEOUT_MS": "1"},
    )
    assert result.returncode != 0
    assert "spec-modem" in result.stderr
    assert "never became bpctl-capable" in result.stderr
    assert "spec-modem set_" not in _calls(calls_log)


def test_arm_requires_yes(tmp_path: Path) -> None:
    fake, _calls_log = _fake_bpctl(tmp_path)
    env_dir, run_dir = _watchdog_env_dirs(tmp_path)
    _seed_watchdog_env(env_dir, "att", "att-modem", "cake-autorate-att.service")

    result = _run(tmp_path, fake, "arm", "att-modem", extra_env=_watchdog_extra_env(env_dir, run_dir))

    assert result.returncode != 0
    assert "arm requires --yes" in result.stderr
    assert "enable" not in _systemctl_calls(tmp_path)
    assert "start" not in _systemctl_calls(tmp_path)


def test_arm_inactive_writes_timeout_before_start(tmp_path: Path) -> None:
    fake, _calls_log = _fake_bpctl(tmp_path)
    env_dir, run_dir = _watchdog_env_dirs(tmp_path)
    env_path = _seed_watchdog_env(env_dir, "att", "att-modem", "cake-autorate-att.service")

    result = _run(
        tmp_path,
        fake,
        "arm",
        "att-modem",
        "5000",
        "--yes",
        extra_env=_watchdog_extra_env(env_dir, run_dir, FAKE_SYSTEMCTL_RC="3"),
    )

    assert result.returncode == 0, (result.stdout, result.stderr)
    assert "TIMEOUT_MS=5000" in env_path.read_text(encoding="utf-8")
    calls = _systemctl_calls(tmp_path).splitlines()
    assert "enable silicom-bypass-watchdog@att.service" in calls
    assert "start silicom-bypass-watchdog@att.service" in calls
    assert not any(call.startswith("restart ") for call in calls)
    assert not any(call.startswith("stop ") for call in calls)


def test_arm_active_rearm_is_sentineled_clean_stop(tmp_path: Path) -> None:
    fake, calls_log = _fake_bpctl(tmp_path)
    env_dir, run_dir = _watchdog_env_dirs(tmp_path)
    env_path = _seed_watchdog_env(env_dir, "att", "att-modem", "cake-autorate-att.service")

    result = _run(
        tmp_path,
        fake,
        "arm",
        "att-modem",
        "6000",
        "--yes",
        extra_env=_watchdog_extra_env(env_dir, run_dir, FAKE_SYSTEMCTL_RC="0"),
    )

    assert result.returncode == 0, (result.stdout, result.stderr)
    assert "TIMEOUT_MS=6000" in env_path.read_text(encoding="utf-8")
    calls = _systemctl_calls(tmp_path).splitlines()
    assert "stop silicom-bypass-watchdog@att.service" in calls
    assert "start silicom-bypass-watchdog@att.service" in calls
    assert not any(call.startswith("restart ") for call in calls)
    iface_calls = _calls_for(_calls(calls_log), "att-modem")
    assert "set_bypass on" not in iface_calls
    assert "set_bypass off" in iface_calls
    assert not (run_dir / "att-modem.disarm").exists()


def test_arm_active_rearm_failed_stop_leaves_no_sentinel(tmp_path: Path) -> None:
    fake, _calls_log = _fake_bpctl(tmp_path)
    env_dir, run_dir = _watchdog_env_dirs(tmp_path)
    _seed_watchdog_env(env_dir, "att", "att-modem", "cake-autorate-att.service")

    result = _run(
        tmp_path,
        fake,
        "arm",
        "att-modem",
        "6000",
        "--yes",
        extra_env=_watchdog_extra_env(
            env_dir, run_dir, FAKE_SYSTEMCTL_RC="0", FAKE_SYSTEMCTL_DISABLE_RC="1"
        ),
    )

    assert result.returncode != 0
    assert "stop silicom-bypass-watchdog@att.service" in _systemctl_calls(tmp_path)
    assert not (run_dir / "att-modem.disarm").exists()


def test_arm_rejects_bad_timeout(tmp_path: Path) -> None:
    fake, _calls_log = _fake_bpctl(tmp_path)
    env_dir, run_dir = _watchdog_env_dirs(tmp_path)
    _seed_watchdog_env(env_dir, "att", "att-modem", "cake-autorate-att.service")

    zero = _run(
        tmp_path,
        fake,
        "arm",
        "att-modem",
        "0",
        "--yes",
        extra_env=_watchdog_extra_env(env_dir, run_dir),
    )
    bad = _run(
        tmp_path,
        fake,
        "arm",
        "att-modem",
        "notanint",
        "--yes",
        extra_env=_watchdog_extra_env(env_dir, run_dir),
    )

    assert zero.returncode == 2
    assert bad.returncode == 2
    assert "timeout must be > 0" in zero.stderr
    assert "timeout must be > 0" in bad.stderr


def test_arm_refuses_stale_native_unit_unless_allowed(tmp_path: Path) -> None:
    fake, _calls_log = _fake_bpctl(tmp_path)
    env_dir, run_dir = _watchdog_env_dirs(tmp_path)
    _seed_watchdog_env(env_dir, "att", "att-modem", "wanctl@att.service")

    result = _run(
        tmp_path,
        fake,
        "arm",
        "att-modem",
        "5000",
        "--yes",
        extra_env=_watchdog_extra_env(env_dir, run_dir, FAKE_SYSTEMCTL_RC="3"),
    )
    allowed = _run(
        tmp_path,
        fake,
        "arm",
        "att-modem",
        "5000",
        "--yes",
        extra_env=_watchdog_extra_env(
            env_dir, run_dir, FAKE_SYSTEMCTL_RC="3", WD_ALLOW_NATIVE_UNIT="1"
        ),
    )

    assert result.returncode != 0
    assert "native wanctl@ unit in cake mode" in result.stderr
    assert allowed.returncode == 0, (allowed.stdout, allowed.stderr)


def test_arm_atomic_timeout_preserves_env_keys(tmp_path: Path) -> None:
    fake, _calls_log = _fake_bpctl(tmp_path)
    env_dir, run_dir = _watchdog_env_dirs(tmp_path)
    env_path = _seed_watchdog_env(env_dir, "att", "att-modem", "cake-autorate-att.service")

    result = _run(
        tmp_path,
        fake,
        "arm",
        "att-modem",
        "7000",
        "--yes",
        extra_env=_watchdog_extra_env(env_dir, run_dir, FAKE_SYSTEMCTL_RC="3"),
    )

    assert result.returncode == 0, (result.stdout, result.stderr)
    text = env_path.read_text(encoding="utf-8")
    assert "IFACE=att-modem" in text
    assert "WANCTL_UNIT=cake-autorate-att.service" in text
    assert "TIMEOUT_MS=7000" in text


def test_arm_refuses_double_petter_att_variant(tmp_path: Path) -> None:
    fake, _calls_log = _fake_bpctl(tmp_path)
    env_dir, run_dir = _watchdog_env_dirs(tmp_path)
    env_path = _seed_watchdog_env(env_dir, "att", "att-modem", "cake-autorate-att.service")

    result = _run(
        tmp_path,
        fake,
        "arm",
        "att-modem",
        "5000",
        "--yes",
        extra_env=_watchdog_extra_env(
            env_dir,
            run_dir,
            FAKE_SYSTEMCTL_RC="3",
            FAKE_SYSTEMCTL_silicom_bypass_watchdog_cake_autorate_att_service_STATE="active",
        ),
    )

    assert result.returncode != 0
    assert "double-petter" in result.stderr
    assert "TIMEOUT_MS=5000" not in env_path.read_text(encoding="utf-8")
    assert "enable silicom-bypass-watchdog@att.service" not in _systemctl_calls(tmp_path)


def test_arm_refuses_bogus_iface(tmp_path: Path) -> None:
    fake, _calls_log = _fake_bpctl(tmp_path)
    env_dir, run_dir = _watchdog_env_dirs(tmp_path)

    result = _run(
        tmp_path,
        fake,
        "arm",
        "bogus-iface",
        "--yes",
        extra_env=_watchdog_extra_env(env_dir, run_dir),
    )

    assert result.returncode == 2
    assert "unknown bypass pair" in result.stderr


def test_disarm_clean_inline_restore(tmp_path: Path) -> None:
    fake, calls_log = _fake_bpctl(tmp_path)
    env_dir, run_dir = _watchdog_env_dirs(tmp_path)

    result = _run(
        tmp_path,
        fake,
        "disarm",
        "spec-modem",
        extra_env=_watchdog_extra_env(env_dir, run_dir, FAKE_SYSTEMCTL_RC="3"),
    )

    assert result.returncode == 0, (result.stdout, result.stderr)
    assert "disable --now silicom-bypass-watchdog@spectrum.service" in _systemctl_calls(tmp_path)
    iface_calls = _calls_for(_calls(calls_log), "spec-modem")
    assert "set_bypass on" not in iface_calls
    assert iface_calls[-2:] == ["set_bypass off", "set_bypass_wd 0"]
    assert not (run_dir / "spec-modem.disarm").exists()


def test_disarm_disable_failure_still_restores_inline(tmp_path: Path) -> None:
    fake, calls_log = _fake_bpctl(tmp_path)
    env_dir, run_dir = _watchdog_env_dirs(tmp_path)

    result = _run(
        tmp_path,
        fake,
        "disarm",
        "spec-modem",
        extra_env=_watchdog_extra_env(
            env_dir, run_dir, FAKE_SYSTEMCTL_RC="3", FAKE_SYSTEMCTL_DISABLE_RC="1"
        ),
    )

    assert result.returncode != 0
    iface_calls = _calls_for(_calls(calls_log), "spec-modem")
    assert "set_bypass on" not in iface_calls
    assert "set_disc off" in iface_calls
    assert "set_bypass off" in iface_calls
    assert "set_bypass_wd 0" in iface_calls
    assert not (run_dir / "spec-modem.disarm").exists()


def test_init_service_artifact() -> None:
    assert INIT_SERVICE.exists()
    text = INIT_SERVICE.read_text(encoding="utf-8")
    assert "Type=oneshot" in text
    assert "ExecStart=/usr/local/sbin/silicom-bypass baseline" in text
    assert "Requires=bpctl-silicom.service" in text
    assert "After=bpctl-silicom.service" in text
    assert "systemd-udev-settle" not in text
    assert "ordering only" in text.lower()
    assert "must be enabled" in text.lower()

    bpctl = BPCTL_SERVICE.read_text(encoding="utf-8")
    assert "ExecStart=/usr/local/sbin/wanctl-bpctl-init" in bpctl
    assert any("Before=" in line and "cake-autorate" in line for line in bpctl.splitlines())


def test_init_service_manual_reapply_docs_match_remain_after_exit() -> None:
    unit_text = INIT_SERVICE.read_text(encoding="utf-8")
    docs_text = SILICOM_BYPASS_DOC.read_text(encoding="utf-8")
    manual_match = re.search(
        r"To manually exercise the oneshot.*?```bash\n(?P<commands>.*?)```",
        docs_text,
        re.S,
    )
    assert manual_match is not None, "manual oneshot exercise block not found"
    manual_block = manual_match.group("commands")

    if "RemainAfterExit=yes" in unit_text:
        assert "systemctl restart silicom-bypass-init.service" in manual_block
        assert "systemctl start silicom-bypass-init.service" not in manual_block
        rationale = docs_text[manual_match.start() : manual_match.end()]
        assert "RemainAfterExit" in rationale or "no-op" in rationale


def _silicom_deploy_function_body(deploy_text: str) -> str:
    match = re.search(r"^deploy_silicom_bypass\(\) \{\n(?P<body>.*?)^\}", deploy_text, re.S | re.M)
    assert match is not None, "deploy_silicom_bypass() function not found"
    return match.group("body")


def _silicom_systemd_array_entries(deploy_text: str) -> set[str]:
    match = re.search(r"^SILICOM_BYPASS_SYSTEMD=\(\n(?P<body>.*?)^\)", deploy_text, re.S | re.M)
    assert match is not None, "SILICOM_BYPASS_SYSTEMD array not found"
    return set(re.findall(r'"(deploy/systemd/[^"]+)"', match.group("body")))


def _array_entries(deploy_text: str, name: str) -> set[str]:
    match = re.search(rf"^{name}=\(\n(?P<body>.*?)^\)", deploy_text, re.S | re.M)
    assert match is not None, f"{name} array not found"
    return set(re.findall(r'"([^"]+)"', match.group("body")))


def _function_body(text: str, name: str) -> str:
    match = re.search(rf"^{name}\(\) \{{\n(?P<body>.*?)^\}}", text, re.S | re.M)
    assert match is not None, f"{name}() function not found"
    return match.group("body")


def test_watchdog_unit_decoupled() -> None:
    assert WATCHDOG_UNIT.exists()
    text = WATCHDOG_UNIT.read_text(encoding="utf-8")

    assert "wanctl@%i" not in text
    assert "Wants=wanctl@" not in text
    assert "EnvironmentFile=/etc/wanctl/bpctl-watchdog/%i.env" in text
    assert text.index("Environment=TIMEOUT_MS=") < text.index("EnvironmentFile=")


def test_watchdog_no_conflicts() -> None:
    text = WATCHDOG_UNIT.read_text(encoding="utf-8")

    assert "Conflicts=" not in text
    assert not WATCHDOG_ATT_CONFLICTS_DROPIN.exists()


def test_watchdog_env_names_live_controller() -> None:
    att = WATCHDOG_ATT_ENV.read_text(encoding="utf-8")
    spectrum = WATCHDOG_SPECTRUM_ENV.read_text(encoding="utf-8")

    assert "IFACE=att-modem" in att
    assert "WANCTL_UNIT=cake-autorate-att.service" in att
    assert "IFACE=spec-modem" in spectrum
    assert "WANCTL_UNIT=cake-autorate-spectrum.service" in spectrum
    assert "wanctl@" not in att
    assert "wanctl@" not in spectrum


def test_deploy_watchdog_off_by_default() -> None:
    deploy_text = DEPLOY.read_text(encoding="utf-8")
    silicom_body = _silicom_deploy_function_body(deploy_text)
    att_body = _function_body(deploy_text, "deploy_att_cake_autorate")
    systemd_entries = _silicom_systemd_array_entries(deploy_text)
    att_entries = _array_entries(deploy_text, "ATT_CAKE_AUTORATE_SYSTEMD")

    assert "deploy/systemd/silicom-bypass-watchdog@.service" in systemd_entries
    assert "deploy_watchdog_artifacts" in deploy_text
    assert "deploy_watchdog_artifacts" in silicom_body
    assert "deploy_watchdog_artifacts" in att_body
    assert "scripts/wanctl-bpctl-watchdog-petter" in deploy_text
    assert "scripts/wanctl-bpctl-watchdog-bypass" in deploy_text
    assert "deploy/scripts/bpctl-watchdog-att.env.example" in deploy_text
    assert "deploy/scripts/bpctl-watchdog-spectrum.env.example" in deploy_text
    assert "silicom-bypass-watchdog-cake-autorate-att.service" not in att_entries
    assert "silicom-bypass-watchdog@att.service.d" not in deploy_text
    assert "conflicts.conf" not in deploy_text
    assert not re.search(r"systemctl\s+enable(?:\s+--now)?\s+[^\n]*silicom-bypass-watchdog", deploy_text)


def test_w_inv_no_raw_watchdog_stop() -> None:
    script = CLI.read_text(encoding="utf-8")

    assert "sentineled_stop()" in script or "function sentineled_stop" in script
    helper_match = re.search(r"^sentineled_stop\(\) \{(?P<body>.*?)^\}", script, re.S | re.M)
    assert helper_match is not None, "sentineled_stop() function not found"
    helper_body = helper_match.group("body")
    assert "trap" in helper_body and "EXIT" in helper_body
    assert ".disarm" in helper_body

    surfaces = [
        CLI,
        DEPLOY,
        REPO_ROOT / "scripts" / "phase231-rollback.sh",
        REPO_ROOT / "scripts" / "soak-monitor.sh",
        Path(__file__),
    ]
    raw_pattern = re.compile(
        r"\bsystemctl\b.*\b(stop|disable|restart|mask)\b.*silicom-bypass-watchdog"
    )
    violations: list[str] = []
    for surface in surfaces:
        lines = surface.read_text(encoding="utf-8").splitlines()
        in_helper = False
        brace_depth = 0
        for lineno, line in enumerate(lines, start=1):
            stripped = line.lstrip()
            if stripped.startswith("#"):
                continue
            if surface == CLI and re.match(r"sentineled_stop\(\) \{", line):
                in_helper = True
                brace_depth = line.count("{") - line.count("}")
                continue
            if in_helper:
                brace_depth += line.count("{") - line.count("}")
                if brace_depth <= 0:
                    in_helper = False
                continue
            if not raw_pattern.search(line):
                continue
            prior = lines[lineno - 2] if lineno >= 2 else ""
            if "sentineled_stop" in line:
                continue
            if "W-INV-SANCTIONED-RETIRE-MASK" in line or "W-INV-SANCTIONED-RETIRE-MASK" in prior:
                continue
            # Plan 02 owns rollback/soak reconciliation; this Plan 01 gate still
            # hard-fails the CLI/deploy/test surfaces and is re-run globally there.
            if surface.name in {"phase231-rollback.sh", "soak-monitor.sh"}:
                continue
            violations.append(f"{surface.relative_to(REPO_ROOT)}:{lineno}: {line.strip()}")

    assert not violations, "raw watchdog systemctl stop/disable/restart/mask:\n" + "\n".join(violations)


def test_artifacts_repo_owned() -> None:
    deploy_text = DEPLOY.read_text(encoding="utf-8")
    function_body = _silicom_deploy_function_body(deploy_text)

    parsed = {
        path
        for path in re.findall(r'\$PROJECT_ROOT/([^"\s]+)', function_body)
        if not path.startswith("$")
    }
    parsed |= _silicom_systemd_array_entries(deploy_text)

    assert INIT_SERVICE.exists()
    assert BPCTL_SERVICE.exists()
    for artifact in SILICOM_BYPASS_ARTIFACTS:
        assert (REPO_ROOT / artifact).exists(), artifact

    assert "scripts/silicom-bypass" in parsed
    assert "scripts/wanctl-bpctl-init" in parsed
    assert "deploy/scripts/silicom-bypass.conf.example" in parsed
    assert "deploy/systemd/silicom-bypass-init.service" in parsed
    assert "deploy/systemd/bpctl-silicom.service" in parsed
    assert "silicom-bypass-init.service" in deploy_text
    assert "bpctl-silicom.service" in deploy_text
    assert "wanctl-bpctl-init" in deploy_text

    nonexistent = {path for path in parsed if not (REPO_ROOT / path).exists()}
    assert not nonexistent, "deploy.sh Silicom path references missing repo file(s): " + ", ".join(
        sorted(nonexistent)
    )


def test_deploy_has_silicom_standalone_mode() -> None:
    text = DEPLOY.read_text(encoding="utf-8")

    assert "--silicom-bypass-only" in text
    assert "SILICOM_BYPASS_ONLY" in text
    assert "deploy_silicom_bypass" in text
    assert "Silicom bypass standalone deploy" in text


def test_deploy_installs_init_unit_dependencies() -> None:
    text = DEPLOY.read_text(encoding="utf-8")
    function_body = _silicom_deploy_function_body(text)
    systemd_entries = _silicom_systemd_array_entries(text)

    assert "deploy/systemd/silicom-bypass-init.service" in systemd_entries
    assert "deploy/systemd/bpctl-silicom.service" in systemd_entries
    assert "scripts/wanctl-bpctl-init" in function_body
    assert "/usr/local/sbin/wanctl-bpctl-init" in function_body


def test_silicom_deploy_uses_private_atomic_staging() -> None:
    text = DEPLOY.read_text(encoding="utf-8")
    function_body = _silicom_deploy_function_body(text)

    assert "mktemp -d" in function_body
    assert "chmod 700" in function_body
    assert "install -o root -g root" in function_body
    assert "rm -rf" in function_body
    assert '"$TARGET_HOST:/tmp/silicom-bypass"' not in function_body
    assert '"$TARGET_HOST:/tmp/wanctl-bpctl-init"' not in function_body


def test_silicom_standalone_short_circuits() -> None:
    text = DEPLOY.read_text(encoding="utf-8")
    handler_match = re.search(
        r'if \[\[ "\$SILICOM_BYPASS_ONLY" == "true" \]\]; then(?P<body>.*?)^fi',
        text,
        re.S | re.M,
    )
    assert handler_match is not None, "SILICOM_BYPASS_ONLY handler not found"
    handler_body = handler_match.group("body")

    handler_start = handler_match.start()
    handler_exit = handler_start + handler_body.rfind("exit 0")
    deploy_code_call = text.index("\ndeploy_code\n")

    assert "TARGET_HOST=\"$WAN_NAME\"" in handler_body
    assert "Usage: $0 --silicom-bypass-only <target_host> [--dry-run]" in handler_body
    assert "deploy_silicom_bypass" in handler_body
    assert "check_silicom_bypass_prerequisites" in handler_body
    assert "check_prerequisites" not in handler_body
    assert handler_exit < deploy_code_call


def test_silicom_standalone_dry_run_is_non_mutating() -> None:
    result = subprocess.run(
        ["bash", str(DEPLOY), "--silicom-bypass-only", "cake-shaper", "--dry-run"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, (result.stdout, result.stderr)
    assert "DRY RUN" in result.stdout
    assert "/usr/local/sbin/silicom-bypass" in result.stdout
    assert "/usr/local/sbin/wanctl-bpctl-init" in result.stdout
    assert "bpctl-silicom.service" in result.stdout
    assert "skip deploy_code" in result.stdout
    assert "Checking prerequisites" not in result.stdout


def test_silicom_standalone_rejects_extra_positional() -> None:
    result = subprocess.run(
        ["bash", str(DEPLOY), "--silicom-bypass-only", "cake-shaper", "extra-host"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    combined = result.stdout + result.stderr

    assert result.returncode != 0
    assert "--silicom-bypass-only" in combined
    assert "Silicom bypass artifacts deployed" not in combined


def test_silicom_standalone_rejects_wan_deploy_flags() -> None:
    result = subprocess.run(
        ["bash", str(DEPLOY), "--silicom-bypass-only", "cake-shaper", "--with-steering"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    combined = result.stdout + result.stderr

    assert result.returncode != 0
    assert "cannot be combined" in combined
