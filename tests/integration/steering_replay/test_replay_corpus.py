"""Replay corpus integration tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from .replay_harness import fixture_paths, run_fixture


@pytest.mark.parametrize("fixture_path", fixture_paths(include_clean_restart=False), ids=lambda p: p.stem)
def test_replay_fixture_matches(fixture_path: Path, tmp_path: Path):
    result = run_fixture(fixture_path, tmp_path / fixture_path.stem)
    assert result["verdict"] == "matches", result["verdict_rationale"]


def test_harness_does_not_touch_production_paths():
    checked = [
        Path("tests/integration/steering_replay/replay_harness.py"),
        Path("tests/integration/steering_replay/conftest.py"),
    ]
    forbidden = ("/var/lib/wanctl", "/etc/wanctl", "/var/log/wanctl", "/run/wanctl")
    offenders = []
    for path in checked:
        for lineno, line in enumerate(path.read_text().splitlines(), start=1):
            stripped = line.strip()
            if not any(token in line for token in forbidden):
                continue
            if (
                stripped.startswith("#")
                or "AssertionError" in line
                or "PRODUCTION_ROOTS" in line
                or "Path(" in line
            ):
                continue
            offenders.append(f"{path}:{lineno}: {line}")
    assert not offenders, "production path literal outside allowed guard context: " + repr(offenders)


@pytest.mark.parametrize("fixture_path", fixture_paths(include_clean_restart=False), ids=lambda p: p.stem)
def test_full_io_seal_per_fixture(fixture_path: Path, tmp_path: Path):
    result = run_fixture(fixture_path, tmp_path / f"seal-{fixture_path.stem}")
    required = {"baseline_rtt", "cake_stats", "state_save"}
    for cycle_paths in result["daemon_io_paths_exercised"]:
        assert required.issubset(set(cycle_paths))
    assert result["live_io_seal"]["urlopen_call_count"] == 0
    assert result["live_io_seal"]["socket_connect_count"] == 0


def test_confidence_cycle_budget_gate(tmp_path: Path):
    source = Path("tests/integration/steering_replay/fixtures/onset-degraded-confidence.yaml")
    import yaml

    data = yaml.safe_load(source.read_text())
    data["cycles"] = data["cycles"][:10]
    bad = tmp_path / "too-short-confidence.yaml"
    bad.write_text(yaml.safe_dump(data))
    with pytest.raises(ValueError, match="below derived budget"):
        run_fixture(bad, tmp_path / "workspace")
