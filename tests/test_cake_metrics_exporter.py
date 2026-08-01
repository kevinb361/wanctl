from __future__ import annotations

import ast
import json
import runpy
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
EXPORTER = REPO_ROOT / "deploy" / "scripts" / "cake-metrics-exporter"
UNIT = REPO_ROOT / "deploy" / "systemd" / "cake-metrics-exporter.service"
DEPLOY = REPO_ROOT / "scripts" / "deploy.sh"
LEGACY_METRICS = {
    "cake_state_up",
    "cake_shaped_rate_bps",
    "cake_green_streak",
    "cake_soft_red_streak",
    "cake_red_streak",
    "cake_congestion_state",
    "cake_baseline_rtt_ms",
    "cake_load_rtt_ms",
    "cake_rtt_delta_ms",
    "cake_state_age_seconds",
}


def _state(wan: str) -> dict[str, Any]:
    rates = (450_000_000, 30_000_000) if wan == "spectrum" else (95_000_000, 19_000_000)
    return {
        "timestamp": "2026-07-31T20:00:00",
        "download": {
            "current_rate": rates[0],
            "green_streak": 5,
            "soft_red_streak": 0,
            "red_streak": 0,
        },
        "upload": {
            "current_rate": rates[1],
            "green_streak": 7,
            "soft_red_streak": 0,
            "red_streak": 0,
        },
        "congestion": {"dl_state": "GREEN", "ul_state": "SOFT_RED"},
        "ewma": {"baseline_rtt": 20.0, "load_rtt": 23.5},
    }


def _rich_state(wan: str) -> dict[str, Any]:
    state = _state(wan)
    state["measurement"] = {"backend": "fping", "source_ip": "test"}
    tins = []
    for index, name in enumerate(("bulk", "best_effort", "video", "voice"), start=1):
        tins.append(
            {
                "name": name,
                "sent_packets": 1000 * index,
                "sent_bytes": 100_000 * index,
                "drops": 10 * index,
                "ecn_mark": index,
                "counter_resets_total": 0,
                "backlog_bytes": 100 * index,
                "peak_delay_us": 1000 * index,
                "avg_delay_us": 100 * index,
                "base_delay_us": 10 * index,
            }
        )
    state["cake_stats"] = {
        "collected_at": "2026-07-31T20:00:00",
        "collection_ok": True,
        "errors": {"download": None, "upload": None},
        "directions": {
            "download": {"interface": f"{wan}-download", "tins": tins},
            "upload": {"interface": f"{wan}-upload", "tins": tins},
        },
    }
    return state


def _load_exporter(monkeypatch: pytest.MonkeyPatch, state_dir: Path) -> dict[str, Any]:
    monkeypatch.setenv("CAKE_EXPORTER_STATE_DIR", str(state_dir))
    monkeypatch.setenv("CAKE_EXPORTER_WANS", "spectrum,att")
    return runpy.run_path(str(EXPORTER))


def _metric_names(exposition: str) -> set[str]:
    return {
        line.split("{", maxsplit=1)[0]
        for line in exposition.splitlines()
        if line and not line.startswith("#")
    }


def test_exporter_preserves_existing_ten_metric_contract(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    for wan in ("spectrum", "att"):
        (tmp_path / f"{wan}_state.json").write_text(json.dumps(_state(wan)), encoding="utf-8")

    namespace = _load_exporter(monkeypatch, tmp_path)
    first = namespace["render"]()
    second = namespace["render"]()

    assert _metric_names(first) >= LEGACY_METRICS
    assert _metric_names(second) >= LEGACY_METRICS
    assert first.count("# TYPE cake_state_up gauge") == 1
    assert second.count("# TYPE cake_state_up gauge") == 1
    assert 'cake_state_up{wan="spectrum"} 1' in first
    assert 'cake_state_up{wan="att"} 1' in first
    assert 'cake_shaped_rate_bps{wan="spectrum",direction="download"} 450000000' in first
    assert 'cake_shaped_rate_bps{wan="att",direction="upload"} 19000000' in first
    assert 'cake_congestion_state{wan="att",direction="upload"} 1' in first
    assert 'cake_rtt_delta_ms{wan="spectrum"} 3.5' in first


def test_rich_exposition_has_fixed_labels_types_units_and_cardinality(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    for wan in ("spectrum", "att"):
        (tmp_path / f"{wan}_state.json").write_text(json.dumps(_rich_state(wan)), encoding="utf-8")

    exposition = _load_exporter(monkeypatch, tmp_path)["render"]()
    samples = [line for line in exposition.splitlines() if line and not line.startswith("#")]
    names = _metric_names(exposition)

    assert len(samples) == 182
    assert len(names) == 23
    assert names >= LEGACY_METRICS
    assert "# TYPE cake_tin_sent_packets_total counter" in exposition
    assert "# TYPE cake_tin_resets_total counter" in exposition
    assert "# TYPE cake_tin_average_delay_seconds gauge" in exposition
    assert 'cake_probe_up{wan="att"} 1' in exposition
    assert 'cake_probe_rtt_seconds{wan="att"} 0.0235' in exposition
    assert 'cake_stats_up{wan="spectrum"} 1' in exposition
    assert (
        'cake_tin_average_delay_seconds{wan="spectrum",direction="download",tin="voice"} 0.0004'
        in exposition
    )
    assert (
        'cake_tin_sent_packets_total{wan="att",direction="upload",tin="best_effort"} 2000'
        in exposition
    )
    labels = {
        part.split("=", maxsplit=1)[0]
        for line in samples
        if "{" in line
        for part in line.split("{", maxsplit=1)[1].split("}", maxsplit=1)[0].split(",")
    }
    assert labels == {"wan", "direction", "tin"}


def test_partial_stats_fail_closed_without_unbounded_tin_labels(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    state = _rich_state("spectrum")
    state["cake_stats"]["collection_ok"] = False
    state["cake_stats"]["directions"]["upload"] = None
    state["cake_stats"]["directions"]["download"]["tins"].append(
        {"name": "attacker-controlled", "sent_packets": 999}
    )
    (tmp_path / "spectrum_state.json").write_text(json.dumps(state), encoding="utf-8")

    exposition = _load_exporter(monkeypatch, tmp_path)["render"]()

    assert 'cake_stats_up{wan="spectrum"} 0' in exposition
    assert "attacker-controlled" not in exposition
    assert 'direction="download",tin="voice"' in exposition
    assert 'direction="upload",tin=' not in exposition
    assert 'cake_state_up{wan="att"} 0' in exposition


@pytest.mark.parametrize("invalid_state", ["not-json", "[]"], ids=("invalid-json", "wrong-shape"))
def test_exporter_fails_one_wan_closed_without_hiding_the_other(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, invalid_state: str
) -> None:
    (tmp_path / "spectrum_state.json").write_text(json.dumps(_state("spectrum")), encoding="utf-8")
    (tmp_path / "att_state.json").write_text(invalid_state, encoding="utf-8")

    exposition = _load_exporter(monkeypatch, tmp_path)["render"]()

    assert 'cake_state_up{wan="spectrum"} 1' in exposition
    assert 'cake_state_up{wan="att"} 0' in exposition
    assert 'cake_shaped_rate_bps{wan="att"' not in exposition


def test_exporter_source_has_no_control_or_write_surface() -> None:
    source = EXPORTER.read_text(encoding="utf-8")
    tree = ast.parse(source)
    imports = {
        alias.name.split(".", maxsplit=1)[0]
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for alias in node.names
    }
    called_attributes = {
        node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }
    called_names = {
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }

    assert "subprocess" not in imports
    assert not ({"write_text", "write_bytes", "unlink", "rename"} & called_attributes)
    assert not ({"open", "exec", "eval", "compile"} & called_names)
    assert "read_text" in called_attributes


def test_exporter_unit_retains_read_only_hardening() -> None:
    unit = UNIT.read_text(encoding="utf-8")

    assert "User=wanctl" in unit
    assert "Group=wanctl" in unit
    assert "Environment=CAKE_EXPORTER_PORT=9103" in unit
    assert "Environment=CAKE_EXPORTER_BIND=10.10.110.223" in unit
    assert 'os.environ.get("CAKE_EXPORTER_BIND", "127.0.0.1")' in EXPORTER.read_text(
        encoding="utf-8"
    )
    assert "Environment=CAKE_EXPORTER_BIND=0.0.0.0" not in unit
    assert "ExecStart=/usr/local/sbin/cake-metrics-exporter" in unit
    assert "NoNewPrivileges=true" in unit
    assert "ProtectSystem=strict" in unit
    assert "PrivateDevices=true" in unit
    assert "ReadOnlyPaths=/var/lib/wanctl" in unit
    assert "CapabilityBoundingSet=" in unit
    assert "ReadWritePaths=" not in unit


def test_external_mode_deploy_owns_exporter_artifacts_without_restart() -> None:
    deploy = DEPLOY.read_text(encoding="utf-8")

    assert 'CAKE_METRICS_EXPORTER_SCRIPT="deploy/scripts/cake-metrics-exporter"' in deploy
    assert 'CAKE_METRICS_EXPORTER_UNIT="deploy/systemd/cake-metrics-exporter.service"' in deploy
    assert "deploy_cake_metrics_exporter" in deploy
    assert "sudo chmod 755 /usr/local/sbin/cake-metrics-exporter" in deploy
    assert "sudo chmod 644 $TARGET_SYSTEMD_DIR/cake-metrics-exporter.service" in deploy
    assert "CAKE metrics exporter artifacts deployed (restart remains operator-gated)" in deploy
    assert "systemctl restart cake-metrics-exporter" not in deploy
