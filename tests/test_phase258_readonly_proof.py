"""Tests for Phase 258 read-only proof harness."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "phase258-readonly-proof.py"
spec = importlib.util.spec_from_file_location("phase258_readonly_proof", SCRIPT)
assert spec is not None
proof = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(proof)


class FakeClient:
    def __init__(self) -> None:
        self.commands: list[str] = []

    def run_cmd(
        self, cmd: str, capture: bool = False, timeout: int | None = None
    ) -> tuple[int, str, str]:
        self.commands.append(cmd)
        if "netwatch" in cmd:
            return (0, json.dumps([{"host": "1.1.1.1", "status": "up"}]), "")
        if "script" in cmd:
            return (0, json.dumps([{"name": "Notify", "source": ":log warning"}]), "")
        if "route" in cmd:
            return (0, json.dumps([{"dst-address": "0.0.0.0/0", "comment": "Spectrum"}]), "")
        return (1, "", "unexpected")

    def close(self) -> None:
        return None


def test_run_proof_happy_path_passes_with_counts_and_redacted_sample() -> None:
    client = FakeClient()

    rc, verdict = proof.run_proof(
        client,
        ["/ip route print", "/tool netwatch print", "/system script print"],
    )

    assert rc == 0
    assert "ACCESS02_PROOF_PASS route=1 netwatch=1 script=1" in verdict
    assert '"source": "<redacted>"' in verdict
    assert client.commands == [
        "/ip route print",
        "/tool netwatch print",
        "/system script print",
    ]


def test_run_proof_rejects_mutating_command_before_run_cmd() -> None:
    client = FakeClient()

    with pytest.raises(ValueError, match="mutating action"):
        proof.run_proof(client, ["/ip route disable 0"])

    assert client.commands == []
