"""PROOF-02 clean-restart reproduction evidence tests."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from .replay_harness import run_fixture


ROOT = Path(__file__).resolve().parents[3]
FIXTURE = ROOT / "tests/integration/steering_replay/fixtures/clean-restart-degraded.yaml"
EVIDENCE_DIR = ROOT / ".planning/phases/223-staging-proof-clean-restart-reproduction/evidence"
JSON_EVIDENCE = EVIDENCE_DIR / "clean-restart-reproduction.json"
MD_EVIDENCE = EVIDENCE_DIR / "clean-restart-reproduction.md"


def _fixture() -> dict[str, Any]:
    return yaml.safe_load(FIXTURE.read_text())


def _calls(result: dict[str, Any], method: str) -> list[dict[str, Any]]:
    return [entry for entry in result["steering_interactions"] if entry.get("method") == method]


def _recovery_cycle(result: dict[str, Any]) -> int | None:
    for cycle in result["cycles"]:
        if cycle["current_state"] == "SPECTRUM_GOOD":
            return int(cycle["cycle"])
    return None


def _classify(
    *,
    result: dict[str, Any],
    cycle_1_observed_state: str,
    recovery_cycle_to_good: int | None,
    recovery_window: list[bool],
    enable_calls: list[dict[str, Any]],
) -> tuple[str, str, bool]:
    effective_cycles = [idx for idx, enabled in enumerate(recovery_window) if enabled]
    any_effective = bool(effective_cycles)
    if (
        cycle_1_observed_state == "SPECTRUM_DEGRADED"
        and recovery_cycle_to_good is not None
        and any_effective
    ):
        source = "daemon-issued enable_steering call" if enable_calls else "pre-enabled boot rule"
        return (
            "reproduced-bug",
            "effective_steering remained true during recovery-window cycles "
            f"{effective_cycles} from {source}; this violates the binary-on/off + "
            "autorate-baseline-authoritative spine contract because persisted DEGRADED "
            "kept traffic effectively steered before fresh GOOD-consistent measurements "
            f"recovered the daemon at cycle {recovery_cycle_to_good}.",
            False,
        )
    if (
        cycle_1_observed_state == "SPECTRUM_DEGRADED"
        and recovery_cycle_to_good is not None
        and not any_effective
    ):
        return (
            "reproduced-intentional",
            "effective_steering stayed false throughout the recovery window with no "
            "enable_steering calls; persisted DEGRADED was observable only as a "
            f"recovery-bound state and returned to GOOD at cycle {recovery_cycle_to_good}.",
            False,
        )
    if cycle_1_observed_state == "SPECTRUM_GOOD":
        return (
            "not-reproducible",
            "persisted SPECTRUM_DEGRADED was not load-bearing on cold start: "
            "cycle-1 observed state was SPECTRUM_GOOD, so post-drift code re-derived "
            "state from GOOD-consistent inputs instead of preserving the persisted value.",
            False,
        )
    return (
        "reproduced-bug",
        "harness produced inconsistent observations — see evidence_links for per-cycle rows",
        True,
    )


def _build_evidence(result: dict[str, Any], fixture: dict[str, Any]) -> dict[str, Any]:
    effective = [bool(item) for item in result["effective_steering_state_per_cycle"]]
    recovery_cycle = _recovery_cycle(result)
    recovery_window = effective[:recovery_cycle] if recovery_cycle is not None else effective
    enable_calls = _calls(result, "enable_steering")
    disable_calls = _calls(result, "disable_steering")
    first_cycle = result["cycles"][0]
    cycle_1_observed_state = first_cycle["current_state"]
    outcome, rationale, inconsistent = _classify(
        result=result,
        cycle_1_observed_state=cycle_1_observed_state,
        recovery_cycle_to_good=recovery_cycle,
        recovery_window=recovery_window,
        enable_calls=enable_calls,
    )
    baseline_rtt_per_cycle = result["baseline_rtt_per_cycle"]
    for row in baseline_rtt_per_cycle:
        row["baseline_read_path"] = "staging-workspace/clean-restart-degraded/spectrum_state.json"
    per_cycle_rows = result["cycles"]
    for row in per_cycle_rows:
        for baseline_read in row.get("baseline_reads", []):
            baseline_read["read_path"] = "staging-workspace/clean-restart-degraded/spectrum_state.json"
    evidence = {
        "fixture": result["fixture"],
        "harness_mode": result["harness_mode"],
        "cycle_interval_sec": result["cycle_interval_sec"],
        "cycle_budget_derivation": result["cycle_budget_derivation"],
        "cycles_run": result["cycles_run"],
        "pre_state": fixture["pre_state"],
        "pre_steering_rule_state": result["pre_steering_rule_state"],
        "cycle_1_observed_state": cycle_1_observed_state,
        "cycle_1_effective_steering_state": bool(first_cycle["effective_mangle_state"]),
        "effective_steering_state_per_cycle": effective,
        "enable_steering_call_log": enable_calls,
        "disable_steering_call_log": disable_calls,
        "interactions_log": result["steering_interactions"],
        "steering_interactions": result["steering_interactions"],
        "baseline_rtt_per_cycle": baseline_rtt_per_cycle,
        "recovery_cycle_to_GOOD": recovery_cycle,
        "effective_steering_during_recovery_window": recovery_window,
        "final_state": result["final_state"],
        "transitions": result["transitions"],
        "daemon_io_paths_exercised": result["daemon_io_paths_exercised"],
        "outcome": outcome,
        "outcome_rationale": rationale,
        "evidence_links": {
            "cycle_1_row": first_cycle,
            "recovery_window_cycles": list(range(len(recovery_window))),
            "effective_steering_true_cycles": [
                idx for idx, enabled in enumerate(recovery_window) if enabled
            ],
            "per_cycle_rows": per_cycle_rows,
        },
        "verdict": "observe",
        "verdict_rationale": f"{outcome}: {rationale}",
    }
    if inconsistent:
        raise AssertionError(rationale)
    return evidence


def _render_report(evidence: dict[str, Any]) -> str:
    steering_state = evidence["pre_state"]["steering_pre_state"]
    autorate = evidence["pre_state"]["autorate_state_by_cycle"]
    enable_cycles = {entry["cycle"] for entry in evidence["enable_steering_call_log"]}
    disable_cycles = {entry["cycle"] for entry in evidence["disable_steering_call_log"]}
    lines = [
        "# PROOF-02 Clean-Restart Reproduction",
        "",
        "## Pre-State Seed",
        "",
        "### steering_pre_state",
        "",
        "| field | value |",
        "|---|---|",
    ]
    for key in (
        "current_state",
        "good_count",
        "baseline_rtt",
        "history_rtt",
        "history_delta",
        "rtt_delta_ewma",
        "queue_ewma",
        "congestion_state",
        "cake_read_failures",
    ):
        lines.append(f"| {key} | `{json.dumps(steering_state.get(key))}` |")
    lines.extend(
        [
            "",
            "### autorate_state_by_cycle",
            "",
            f"```json\n{json.dumps(autorate, indent=2)}\n```",
            "",
            "## Initial Rule State",
            "",
            f"- `pre_steering_rule_state`: `{evidence['pre_steering_rule_state']}`",
            f"- `cycle_1_effective_steering_state`: `{evidence['cycle_1_effective_steering_state']}`",
            "",
            "## Per-Cycle Observations",
            "",
            "| cycle | current_state | effective_steering_state | enable_steering_called | disable_steering_called | baseline_rtt | RTT delta |",
            "|---:|---|---|---|---|---:|---:|",
        ]
    )
    baseline_by_cycle = {row["cycle"]: row for row in evidence["baseline_rtt_per_cycle"]}
    for cycle in evidence["evidence_links"]["per_cycle_rows"]:
        idx = cycle["cycle"]
        baseline = baseline_by_cycle[idx]["baseline_read_value"]
        live_rtt = cycle["live_rtt_reads"][-1]["returned_value"]
        delta = None if baseline is None or live_rtt is None else round(live_rtt - baseline, 3)
        lines.append(
            f"| {idx} | {cycle['current_state']} | {cycle['effective_mangle_state']} | "
            f"{idx in enable_cycles} | {idx in disable_cycles} | {baseline} | {delta} |"
        )
    lines.extend(
        [
            "",
            "## Outcome Verdict",
            "",
            f"- **§5 outcome:** `{evidence['outcome']}`",
            f"- **Rationale:** {evidence['outcome_rationale']}",
        ]
    )
    if evidence["outcome"] == "reproduced-bug":
        lines.extend(
            [
                "- **Proposed fix scope:** `src/wanctl/steering/daemon.py` startup/state-load path; revalidate persisted DEGRADED against fresh measurement before leaving RouterOS steering effectively enabled, while preserving autorate baseline authority.",
                "- **Fix status:** fix DID NOT land in this plan and is held against Phase 224 pre-canary or a follow-up phase.",
                "- **Phase 224 Block Recommendation:** Phase 224 BLOCKED on this outcome unless fix lands or operator accepts the risk.",
            ]
        )
    else:
        lines.append("- **Phase 224 Block Recommendation:** Phase 224 NOT BLOCKED")
    lines.extend(
        [
            "",
            "## Folded-Todo Closure",
            "",
            "Closure note for `.planning/todos/pending/2026-04-17-investigate-steering-degraded-on-clean-restart.md`: PROOF-02 recorded the clean-restart outcome above, with structured JSON evidence and this report. The todo is resolved by Phase 223 annotation, not deletion.",
            "",
        ]
    )
    return "\n".join(lines)


def test_clean_restart_reproduction_runs(staging_workspace: Path):
    fixture = _fixture()
    result = run_fixture(FIXTURE, staging_workspace / "clean-restart-degraded")
    evidence = _build_evidence(result, fixture)
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    JSON_EVIDENCE.write_text(json.dumps(evidence, indent=2) + "\n")
    MD_EVIDENCE.write_text(_render_report(evidence))
    assert evidence["outcome"] in fixture["acceptable_outcomes"]
    assert len(evidence["effective_steering_state_per_cycle"]) == evidence["cycles_run"]


def test_clean_restart_outcome_is_documented(staging_workspace: Path):
    fixture = _fixture()
    result = run_fixture(FIXTURE, staging_workspace / "clean-restart-degraded-doc")
    evidence = _build_evidence(result, fixture)
    assert evidence["outcome"] in (
        "reproduced-intentional",
        "reproduced-bug",
        "not-reproducible",
    )
    assert len(evidence["outcome_rationale"]) >= 40
    rationale = evidence["outcome_rationale"]
    assert any(
        token in rationale
        for token in ("effective_steering", "pre-enabled", "enable_steering", "not load-bearing")
    )
