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

SILICOM_BYPASS_ARTIFACTS = {
    "scripts/silicom-bypass",
    "scripts/wanctl-bpctl-init",
    "deploy/scripts/silicom-bypass.conf.example",
    "deploy/systemd/silicom-bypass-init.service",
    "deploy/systemd/bpctl-silicom.service",
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
        ),
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
              *)
                printf 'unknown fake bpctl verb: %s\n' "$verb" >&2
                exit 64
                ;;
            esac
            """
        ),
        encoding="utf-8",
    )
    fake.chmod(0o755)
    return fake, calls_log


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
    env = {
        **os.environ,
        "BPCTL_UTIL": str(fake),
        "PAIRS": "att-modem spec-modem",
        "SILICOM_BYPASS_CONF": "/dev/null",
        "SILICOM_MARKS_LOG": str(tmp_path / "marks.log"),
        "LOGGER": str(logger),
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
