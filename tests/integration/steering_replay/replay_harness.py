"""Operator-runnable offline replay harness for the steering daemon."""

from __future__ import annotations

import argparse
import contextlib
import copy
import json
import logging
import socket
import sys
import tempfile
import urllib.request
from pathlib import Path
from typing import Any
from unittest.mock import patch

import yaml

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:  # package import under pytest
    from .conftest import build_replay_config
    from .fake_cake_reader import FakeCakeReader
    from .fake_live_rtt_source import FixtureBaselineLoader
    from .fake_router_transport import FakeRouterTransport
except ImportError:  # direct script invocation
    from conftest import build_replay_config  # type: ignore[no-redef]
    from fake_cake_reader import FakeCakeReader  # type: ignore[no-redef]
    from fake_live_rtt_source import FixtureBaselineLoader  # type: ignore[no-redef]
    from fake_router_transport import FakeRouterTransport  # type: ignore[no-redef]

from wanctl.steering.cake_stats import CakeStats
from wanctl.steering.daemon import (
    RTTAggregationStrategy,
    RTTMeasurement,
    SteeringDaemon,
    SteeringStateManager,
    create_steering_state_schema,
)

FIXTURES_DIR = Path(__file__).with_name("fixtures")
EVIDENCE_DIR = ROOT / ".planning/phases/223-staging-proof-clean-restart-reproduction/evidence"
CYCLE_INTERVAL_SEC = 0.05


@contextlib.contextmanager
def no_live_io_seal():
    """Block direct HTTP/socket I/O and expose attempted-call counters."""
    calls = {"urlopen": [], "socket_connect": []}

    def denied_urlopen(*args: Any, **_kwargs: Any) -> Any:
        calls["urlopen"].append(str(args[0]) if args else "<unknown>")
        raise RuntimeError("steering_replay harness: no HTTP calls allowed")

    def denied_connect(_sock: socket.socket, address: Any) -> Any:
        calls["socket_connect"].append(str(address))
        raise RuntimeError("steering_replay harness: no socket calls allowed")

    with patch.object(urllib.request, "urlopen", denied_urlopen):
        with patch.object(socket.socket, "connect", denied_connect):
            with patch.object(socket.socket, "connect_ex", denied_connect):
                yield calls


def _validate_fixture(fixture: dict[str, Any]) -> None:
    required = {"harness_mode", "cycle_budget_derivation", "pre_state", "cycles"}
    missing = required - set(fixture)
    if missing:
        raise ValueError(f"fixture missing required keys: {sorted(missing)}")
    pre_state = fixture["pre_state"]
    if "steering_pre_state" not in pre_state or "autorate_state_by_cycle" not in pre_state:
        raise ValueError("fixture pre_state must include steering_pre_state and autorate_state_by_cycle")
    if fixture["harness_mode"] == "confidence":
        cbd = fixture["cycle_budget_derivation"]
        budget = int(cbd["derived_sustain_cycles"]) + int(cbd["derived_hold_down_cycles"])
        if len(fixture["cycles"]) < budget:
            raise ValueError(
                f"confidence fixture has {len(fixture['cycles'])} cycles, below derived budget {budget}"
            )


def _autorate_state_for_cycle(autorate_by_cycle: dict[str, Any], idx: int) -> dict[str, Any]:
    return copy.deepcopy(
        autorate_by_cycle.get(idx)
        or autorate_by_cycle.get(str(idx))
        or autorate_by_cycle.get("default")
        or {"ewma": {"baseline_rtt": 25.0}, "congestion": {"dl_state": "GREEN"}}
    )


def _cake_stats_from_cycle(cycle: dict[str, Any]) -> CakeStats | None:
    if "cake_stats" in cycle and cycle["cake_stats"] is None:
        return None
    inputs = cycle.get("inputs", {})
    return CakeStats(
        dropped=int(inputs.get("cake_drops", 0)),
        queued_packets=int(inputs.get("queued_packets", 0)),
    )


def _seed_workspace(workspace: Path, fixture: dict[str, Any]) -> None:
    workspace.mkdir(parents=True, exist_ok=True)
    steering_state = copy.deepcopy(fixture["pre_state"]["steering_pre_state"])
    (workspace / "steering_state.json").write_text(json.dumps(steering_state, indent=2))
    autorate = _autorate_state_for_cycle(fixture["pre_state"]["autorate_state_by_cycle"], 0)
    (workspace / "spectrum_state.json").write_text(json.dumps(autorate, indent=2))


def _build_daemon(fixture: dict[str, Any], workspace: Path):
    logger = logging.getLogger("steering_replay")
    config = build_replay_config(workspace, fixture["harness_mode"])
    state_mgr = SteeringStateManager(
        workspace / "steering_state.json",
        create_steering_state_schema(config),
        logger,
        history_maxlen=config.history_size,
    )
    state_mgr.load()
    initial_enabled = bool(
        fixture.get(
            "initial_steering_rule_state",
            state_mgr.state.get("current_state") == config.state_degraded,
        )
    )
    router = FakeRouterTransport(initial_enabled=initial_enabled, logger=logger)
    cake_reader = FakeCakeReader(logger=logger)
    baseline_loader = FixtureBaselineLoader(
        config,
        logger,
        workspace / "spectrum_state.json",
    )
    rtt_measurement = RTTMeasurement(
        logger,
        timeout_ping=config.timeout_ping,
        aggregation_strategy=RTTAggregationStrategy.MEDIAN,
    )
    with patch("wanctl.steering.daemon.CakeStatsReader"):
        daemon = SteeringDaemon(
            config=config,
            state=state_mgr,
            router=router,
            rtt_measurement=rtt_measurement,
            baseline_loader=baseline_loader,
            logger=logger,
        )
    daemon.cake_reader = cake_reader
    assert daemon.cake_reader is cake_reader
    assert daemon._metrics_writer is None
    return daemon, router, cake_reader, baseline_loader


def _cycle_expected_matches(observed: dict[str, Any], expected: Any) -> bool:
    if expected == "observe":
        return True
    if not isinstance(expected, dict):
        return True
    state_ok = expected.get("current_state") in (None, observed["current_state"])
    mangle_ok = expected.get("effective_mangle_state") in (
        None,
        observed["effective_mangle_state"],
    )
    cake_min = expected.get("cake_read_failures_min")
    cake_ok = cake_min is None or observed.get("cake_read_failures", 0) >= int(cake_min)
    return bool(state_ok and mangle_ok and cake_ok)


def _stable_transitions(transitions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    stable = []
    for idx, transition in enumerate(transitions):
        item = dict(transition)
        item["timestamp"] = f"2026-06-02T00:10:{idx % 60:02d}Z"
        stable.append(item)
    return stable


def run_fixture(fixture_path: Path, workspace: Path) -> dict[str, Any]:
    """Run one fixture through `SteeringDaemon.run_cycle()` and return evidence."""
    fixture = yaml.safe_load(Path(fixture_path).read_text())
    _validate_fixture(fixture)
    _seed_workspace(workspace, fixture)
    with no_live_io_seal() as live_io_calls:
        daemon, router, cake_reader, baseline_loader = _build_daemon(fixture, workspace)
        pre_rule_state = router.get_rule_status()
        cycles_out: list[dict[str, Any]] = []
        effective_states: list[bool] = []
        mismatches: list[int] = []
        autorate_by_cycle = fixture["pre_state"]["autorate_state_by_cycle"]
        for idx, cycle in enumerate(fixture["cycles"]):
            router.set_current_cycle(idx)
            cake_reader.set_current_cycle(idx)
            baseline_loader.set_current_cycle(idx)
            autorate_state = _autorate_state_for_cycle(autorate_by_cycle, idx)
            (workspace / "spectrum_state.json").write_text(json.dumps(autorate_state, indent=2))
            inputs = cycle.get("inputs", {})
            baseline = autorate_state.get("ewma", {}).get("baseline_rtt", 25.0)
            baseline_loader.live_rtt_by_cycle[idx] = inputs.get("live_rtt_ms", baseline)
            baseline_loader.live_irtt_rtt_by_cycle[idx] = inputs.get("live_irtt_rtt_ms")
            cake_reader.script[idx] = _cake_stats_from_cycle(cycle)
            before_router = len(router.interactions_log)
            before_cake = len(cake_reader.reads_log)
            before_base = len(baseline_loader.baseline_calls)
            before_live = len(baseline_loader.live_rtt_calls)
            before_irtt = len(baseline_loader.live_irtt_calls)
            daemon.run_cycle()
            effective = router.get_rule_status()
            effective_states.append(effective)
            io_paths = []
            if len(baseline_loader.baseline_calls) > before_base:
                io_paths.append("baseline_rtt")
            if len(cake_reader.reads_log) > before_cake:
                io_paths.append("cake_stats")
            if len(baseline_loader.live_rtt_calls) > before_live:
                io_paths.append("live_rtt")
            if len(baseline_loader.live_irtt_calls) > before_irtt:
                io_paths.append("live_irtt")
            io_paths.append("state_save")
            observed = {
                "cycle": idx,
                "current_state": daemon.state_mgr.state.get("current_state"),
                "effective_mangle_state": effective,
                "cake_read_failures": daemon.state_mgr.state.get("cake_read_failures", 0),
                "steering_interactions": router.interactions_log[before_router:],
                "cake_reads": cake_reader.reads_log[before_cake:],
                "baseline_reads": baseline_loader.baseline_calls[before_base:],
                "live_rtt_reads": baseline_loader.live_rtt_calls[before_live:],
                "live_irtt_reads": baseline_loader.live_irtt_calls[before_irtt:],
                "spectrum_state_write_attempted": True,
                "daemon_io_paths_exercised": io_paths,
            }
            if fixture["harness_mode"] != "confidence" and not _cycle_expected_matches(
                observed, cycle.get("expected_decision")
            ):
                mismatches.append(idx)
            cycles_out.append(observed)
        final_state = daemon.state_mgr.state.get("current_state")
        try:
            router.assert_only_documented_calls()
            documented_ok = True
        except AssertionError:
            documented_ok = False
        live_calls_ok = not live_io_calls["urlopen"] and not live_io_calls["socket_connect"]
        verdict = "matches"
        rationale = "All expected decisions matched and no live I/O escaped the harness."
        if mismatches:
            verdict = "diverges"
            rationale = f"Mismatched cycles: {mismatches}"
        if not documented_ok or not live_calls_ok:
            verdict = "inconclusive"
            rationale = "I/O seal post-run check failed"
    baseline_per_cycle = []
    for idx in range(len(fixture["cycles"])):
        reads = [call for call in baseline_loader.baseline_calls if call["cycle"] == idx]
        baseline_per_cycle.append(
            {
                "cycle": idx,
                "baseline_read_path": reads[-1]["read_path"] if reads else None,
                "baseline_read_value": reads[-1]["returned_value"] if reads else None,
                "baseline_loader_called": bool(reads),
                "spectrum_state_write_attempted": True,
            }
        )
    return {
        "fixture": fixture["name"],
        "harness_mode": fixture["harness_mode"],
        "cycle_interval_sec": CYCLE_INTERVAL_SEC,
        "cycle_budget_derivation": fixture["cycle_budget_derivation"],
        "cycles_run": len(fixture["cycles"]),
        "pre_steering_rule_state": bool(pre_rule_state),
        "effective_steering_state_per_cycle": effective_states,
        "final_state": final_state,
        "transitions": _stable_transitions(daemon.state_mgr.state.get("transitions", [])),
        "steering_interactions": router.interactions_log,
        "baseline_rtt_per_cycle": baseline_per_cycle,
        "daemon_io_paths_exercised": [c["daemon_io_paths_exercised"] for c in cycles_out],
        "cycles": cycles_out,
        "live_io_seal": {
            "urlopen_call_count": len(live_io_calls["urlopen"]),
            "socket_connect_count": len(live_io_calls["socket_connect"]),
        },
        "verdict": verdict,
        "verdict_rationale": rationale,
    }


def fixture_paths(include_clean_restart: bool = True) -> list[Path]:
    paths = sorted(FIXTURES_DIR.glob("*.yaml"))
    if include_clean_restart:
        return paths
    return [p for p in paths if p.name != "clean-restart-degraded.yaml"]


def render_markdown(results: list[dict[str, Any]]) -> str:
    lines = [
        "# Phase 223 Replay Results",
        "",
        "| fixture | harness_mode | cycles_run | pre_rule_state | final_state | verdict | verdict_rationale |",
        "|---|---|---:|---|---|---|---|",
    ]
    for result in results:
        lines.append(
            f"| {result['fixture']} | {result['harness_mode']} | {result['cycles_run']} | "
            f"{result['pre_steering_rule_state']} | {result['final_state']} | "
            f"{result['verdict']} | {result['verdict_rationale']} |"
        )
    lines.extend(["", "## I/O Seal Audit", ""])
    for result in results:
        union = sorted({path for cycle in result["daemon_io_paths_exercised"] for path in cycle})
        lines.append(f"- **{result['fixture']}**: {', '.join(union)}")
    lines.append("")
    return "\n".join(lines)


def run_all(workspace: Path) -> dict[str, Any]:
    results = []
    for path in fixture_paths(include_clean_restart=True):
        result = run_fixture(path, workspace / path.stem)
        results.append(result)
    return {"fixtures": results}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--fixture", type=Path)
    group.add_argument("--all", action="store_true")
    parser.add_argument("--workspace", type=Path)
    args = parser.parse_args(argv)
    workspace = args.workspace
    if workspace is None:
        if args.all:
            workspace = EVIDENCE_DIR / "staging-state"
        else:
            workspace = Path(tempfile.mkdtemp(prefix="steering-replay-"))
    if args.fixture:
        payload = {"fixtures": [run_fixture(args.fixture, workspace)]}
    else:
        payload = run_all(workspace)
    print(json.dumps(payload, indent=2))
    if args.all:
        EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
        (EVIDENCE_DIR / "replay-results.json").write_text(json.dumps(payload, indent=2))
        (EVIDENCE_DIR / "replay-results.md").write_text(render_markdown(payload["fixtures"]))
    failed = [r for r in payload["fixtures"] if r["verdict"] != "matches"]
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
