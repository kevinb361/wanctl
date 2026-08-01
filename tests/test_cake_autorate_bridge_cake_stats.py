from __future__ import annotations

import copy
import json
import os
import runpy
import subprocess
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
BRIDGES = (
    REPO_ROOT / "deploy" / "scripts" / "cake-autorate-spectrum-state-bridge",
    REPO_ROOT / "deploy" / "scripts" / "cake-autorate-att-state-bridge",
)
FIXTURES = REPO_ROOT / "tests" / "fixtures" / "cake-tc"
RATES = {
    "spectrum": {"download": 450_000_000, "upload": 30_000_000},
    "att": {"download": 95_000_000, "upload": 19_000_000},
}


def _wan(bridge: Path) -> str:
    return "att" if "-att-" in bridge.name else "spectrum"


def _load_bridge(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, bridge: Path) -> dict[str, Any]:
    wan = _wan(bridge)
    monkeypatch.setenv("WANCTL_EXTERNAL_WAN_NAME", wan)
    monkeypatch.setenv("WANCTL_EXTERNAL_DL_IF", f"{wan}-download")
    monkeypatch.setenv("WANCTL_EXTERNAL_UL_IF", f"{wan}-upload")
    monkeypatch.setenv("WANCTL_EXTERNAL_STATE_PATH", str(tmp_path / f"{wan}_state.json"))
    monkeypatch.setenv("WANCTL_EXTERNAL_METRICS_DB", str(tmp_path / f"metrics-{wan}.db"))
    monkeypatch.setenv("WANCTL_EXTERNAL_RTT_ENABLED", "0")
    monkeypatch.setenv("WANCTL_STATE_CHOWN", "0")
    return runpy.run_path(str(bridge))


def _fixture(wan: str, direction: str = "download") -> str:
    data = json.loads((FIXTURES / f"{wan}.json").read_text(encoding="utf-8"))
    data[0]["options"]["bandwidth"] = RATES[wan][direction] // 8
    return json.dumps(data)


def _completed(stdout: str, returncode: int = 0) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess([], returncode, stdout=stdout, stderr="")


@pytest.mark.parametrize("bridge", BRIDGES, ids=("spectrum", "att"))
def test_qdisc_snapshot_parses_representative_four_tin_fixture(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, bridge: Path
) -> None:
    wan = _wan(bridge)
    namespace = _load_bridge(monkeypatch, tmp_path, bridge)
    calls: list[list[str]] = []

    def run(command: list[str], **_kwargs: Any) -> subprocess.CompletedProcess[str]:
        calls.append(command)
        return _completed(_fixture(wan))

    monkeypatch.setattr(namespace["subprocess"], "run", run)
    snapshot, error = namespace["qdisc_snapshot"](f"{wan}-download")

    assert error is None
    assert snapshot["rate_bps"] == RATES[wan]["download"]
    assert [tin["name"] for tin in snapshot["tins"]] == [
        "bulk",
        "best_effort",
        "video",
        "voice",
    ]
    assert snapshot["tins"][1]["backlog_bytes"] > 0
    assert snapshot["tins"][1]["ecn_mark"] > 0
    assert calls == [["tc", "-j", "-s", "qdisc", "show", "dev", f"{wan}-download"]]


@pytest.mark.parametrize("bridge", BRIDGES, ids=("spectrum", "att"))
def test_build_state_uses_exactly_one_bounded_qdisc_read_per_direction(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, bridge: Path
) -> None:
    wan = _wan(bridge)
    namespace = _load_bridge(monkeypatch, tmp_path, bridge)
    calls: list[list[str]] = []

    def run(command: list[str], **_kwargs: Any) -> subprocess.CompletedProcess[str]:
        calls.append(command)
        direction = "upload" if command[-1].endswith("upload") else "download"
        return _completed(_fixture(wan, direction))

    monkeypatch.setattr(namespace["subprocess"], "run", run)
    state, _ = namespace["build_state"]((100_000_000, 20_000_000, "dl_idle", "ul_idle"), 0)

    assert len(calls) == 2
    assert all(command[:6] == ["tc", "-j", "-s", "qdisc", "show", "dev"] for command in calls)
    assert state["download"]["current_rate"] == RATES[wan]["download"]
    assert state["upload"]["current_rate"] == RATES[wan]["upload"]
    assert state["cake_stats"]["collection_ok"] is True
    assert set(state["cake_stats"]["directions"]) == {"download", "upload"}


@pytest.mark.parametrize("bridge", BRIDGES, ids=("spectrum", "att"))
@pytest.mark.parametrize(
    ("failure", "expected_error"),
    [("timeout", "timeout"), ("exec", "exec_error"), ("exit", "tc_error")],
)
def test_qdisc_collection_failures_are_bounded_and_classified(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    bridge: Path,
    failure: str,
    expected_error: str,
) -> None:
    namespace = _load_bridge(monkeypatch, tmp_path, bridge)

    def run(command: list[str], **_kwargs: Any) -> subprocess.CompletedProcess[str]:
        if failure == "timeout":
            raise subprocess.TimeoutExpired(command, 2)
        if failure == "exec":
            raise OSError("tc unavailable")
        return _completed("", returncode=2)

    monkeypatch.setattr(namespace["subprocess"], "run", run)

    assert namespace["qdisc_snapshot"]("test-device") == (None, expected_error)


@pytest.mark.parametrize("bridge", BRIDGES, ids=("spectrum", "att"))
@pytest.mark.parametrize(
    ("failure", "expected_error"),
    [("not-json", "malformed_json"), ("[]", "malformed_json"), ("short-tins", "invalid_tins")],
)
def test_bad_download_stats_do_not_suppress_or_stale_core_snapshot(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    bridge: Path,
    failure: str,
    expected_error: str,
) -> None:
    wan = _wan(bridge)
    namespace = _load_bridge(monkeypatch, tmp_path, bridge)
    old = {
        "cake_stats": {
            "directions": {"download": {"interface": "stale", "tins": [{"name": "bulk"}]}}
        }
    }
    namespace["STATE"].write_text(json.dumps(old), encoding="utf-8")

    def run(command: list[str], **_kwargs: Any) -> subprocess.CompletedProcess[str]:
        if command[-1].endswith("upload"):
            return _completed(_fixture(wan, "upload"))
        if failure == "short-tins":
            data = json.loads(_fixture(wan))
            data[0]["tins"] = data[0]["tins"][:1]
            return _completed(json.dumps(data))
        return _completed(failure)

    monkeypatch.setattr(namespace["subprocess"], "run", run)
    state, _ = namespace["build_state"]((123_000_000, 17_000_000, "dl_idle", "ul_idle"), 4)
    namespace["write_state"](state)
    published = json.loads(namespace["STATE"].read_text(encoding="utf-8"))

    assert published["download"]["current_rate"] == 123_000_000
    assert published["cake_stats"]["collection_ok"] is False
    assert published["cake_stats"]["errors"]["download"] == expected_error
    assert published["cake_stats"]["directions"]["download"] is None
    assert published["cake_stats"]["directions"]["upload"]["interface"].endswith("upload")
    assert published["timestamp"]


@pytest.mark.parametrize("bridge", BRIDGES, ids=("spectrum", "att"))
def test_counter_decrease_is_visible_per_tin(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, bridge: Path
) -> None:
    wan = _wan(bridge)
    namespace = _load_bridge(monkeypatch, tmp_path, bridge)
    prior = json.loads(_fixture(wan))[0]
    previous_tins = []
    for name, tin in zip(namespace["TIN_NAMES"], prior["tins"], strict=True):
        previous_tins.append(
            {"name": name, **{key: tin[key] + 10 for key in namespace["TIN_COUNTER_KEYS"]}}
        )
    namespace["STATE"].write_text(
        json.dumps(
            {
                "cake_stats": {
                    "directions": {
                        "download": {"tins": previous_tins},
                        "upload": {"tins": copy.deepcopy(previous_tins)},
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        namespace["subprocess"],
        "run",
        lambda command, **_kwargs: _completed(
            _fixture(wan, "upload" if command[-1].endswith("upload") else "download")
        ),
    )

    state, _ = namespace["build_state"]((1, 1, "dl_idle", "ul_idle"), 0)

    for direction in ("download", "upload"):
        assert all(
            tin["counter_reset"] is True and tin["counter_resets_total"] == 1
            for tin in state["cake_stats"]["directions"][direction]["tins"]
        )

    namespace["write_state"](state)
    next_state, _ = namespace["build_state"]((1, 1, "dl_idle", "ul_idle"), 0)
    for direction in ("download", "upload"):
        assert all(
            tin["counter_reset"] is False and tin["counter_resets_total"] == 1
            for tin in next_state["cake_stats"]["directions"][direction]["tins"]
        )


@pytest.mark.parametrize("bridge", BRIDGES, ids=("spectrum", "att"))
def test_state_publication_replaces_only_a_complete_json_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, bridge: Path
) -> None:
    namespace = _load_bridge(monkeypatch, tmp_path, bridge)
    destination = namespace["STATE"]
    real_replace = os.replace
    observed: dict[str, Any] = {}

    def inspect_then_replace(source: str, target: Path) -> None:
        observed["target_absent"] = not Path(target).exists()
        observed["temporary"] = json.loads(Path(source).read_text(encoding="utf-8"))
        real_replace(source, target)

    monkeypatch.setattr(namespace["os"], "replace", inspect_then_replace)
    expected = {"timestamp": "now", "cake_stats": {"collection_ok": False}}

    namespace["write_state"](expected)

    assert observed == {"target_absent": True, "temporary": expected}
    assert json.loads(destination.read_text(encoding="utf-8")) == expected
    assert not list(tmp_path.glob("*.tmp"))
