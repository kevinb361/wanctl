"""Tests for Phase 259 ownership inspection proof harness."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "phase259-ownership-proof.py"
spec = importlib.util.spec_from_file_location("phase259_ownership_proof", SCRIPT)
assert spec is not None
proof = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(proof)


class FakeClient:
    def __init__(self, *, fail: str | None = None) -> None:
        self.commands: list[str] = []
        self.fail = fail

    def run_cmd(
        self, cmd: str, capture: bool = False, timeout: int | None = None
    ) -> tuple[int, str, str]:
        self.commands.append(cmd)
        if self.fail and self.fail in cmd:
            return (1, "", "boom")
        if "netwatch" in cmd:
            return (
                0,
                json.dumps(
                    [
                        {"host": "1.1.1.1", "disabled": "false", "down-script": "Disable-Spectrum"},
                        {"host": "9.9.9.9", "disabled": "false", "up-script": "Enable-Att"},
                        {"host": "8.8.8.8", "disabled": "true", "down-script": "Notify"},
                    ]
                ),
                "",
            )
        if "script" in cmd:
            return (
                0,
                json.dumps(
                    [
                        {"name": "Disable-Spectrum", "source": '/ip route disable [find comment="Spectrum"]'},
                        {"name": "Enable-Att", "source": '/ip route enable [find comment="ATT"]'},
                        {"name": "Notify", "source": ":log warning"},
                    ]
                ),
                "",
            )
        if "route" in cmd:
            return (
                0,
                json.dumps(
                    [
                        {"dst-address": "0.0.0.0/0", "comment": "Spectrum", "disabled": "false"},
                        {"dst-address": "10.0.0.0/24", "comment": "LAN", "disabled": "false"},
                    ]
                ),
                "",
            )
        return (1, "", "unexpected")

    def close(self) -> None:
        return None


class FakeRouteManager:
    def status_snapshot(self) -> dict[str, object]:
        return {"active_owner": "wanctl", "mode": "dry_run"}


def test_run_proof_happy_path_emits_inspect_proof_pass() -> None:
    client = FakeClient()

    rc, verdict = proof.run_proof(client, FakeRouteManager())

    assert rc == 0
    assert "INSPECT_PROOF_PASS" in verdict
    assert "observed_owner=none" in verdict
    assert "configured_owner=wanctl" in verdict
    assert "match=False" in verdict
    assert "netwatch_entries=0" in verdict
    assert "route_mutating_active=0" in verdict
    assert "total_routes=2" in verdict
    assert "default_routes=1" in verdict


def test_run_proof_rejects_mutating_command_before_run_cmd() -> None:
    client = FakeClient()

    with pytest.raises(ValueError, match="mutating action"):
        proof.validate_commands_before_run(client, ["/ip route disable 0"])

    assert client.commands == []


def test_run_proof_fail_on_inspector_error() -> None:
    client = FakeClient(fail="script")

    rc, verdict = proof.run_proof(client, FakeRouteManager())

    assert rc != 0
    assert "INSPECT_PROOF_FAIL" in verdict
    assert "inspector_error=" in verdict
