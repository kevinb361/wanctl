#!/usr/bin/env python3
"""Analyze captured storage contention telemetry and recommend next steps."""

import argparse
import json
from pathlib import Path
from typing import Any


def _load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text())
    if not isinstance(data, dict):
        raise TypeError(f"expected JSON object in {path}")
    return data


def _parse_metric_value(text: str, metric_name: str, process_role: str) -> float | None:
    prefix = f'{metric_name}{{process="{process_role}"}} '
    for line in text.splitlines():
        if line.startswith(prefix):
            try:
                return float(line.split()[-1])
            except ValueError:
                return None
    return None


def _extract_storage_section(payload: dict[str, Any], key: str) -> dict[str, Any]:
    section = payload.get(key)
    if not isinstance(section, dict):
        raise TypeError(f"missing {key} section")
    return section


def _extract_cycle_utilization(payload: dict[str, Any]) -> float | None:
    cycle_budget = payload.get("cycle_budget")
    if not isinstance(cycle_budget, dict):
        return None
    utilization = cycle_budget.get("utilization_pct")
    return float(utilization) if isinstance(utilization, (int, float)) else None


def _build_summary(
    autorate_storage: dict[str, Any],
    steering_storage: dict[str, Any],
    autorate_utilization: float | None,
    steering_utilization: float | None,
    metrics_text: str,
) -> dict[str, Any]:
    autorate_checkpoint = autorate_storage.get("checkpoint") if isinstance(autorate_storage.get("checkpoint"), dict) else {}
    steering_checkpoint = steering_storage.get("checkpoint") if isinstance(steering_storage.get("checkpoint"), dict) else {}

    observed = {
        "autorate": {
            "pending_writes": int(autorate_storage.get("pending_writes", 0) or 0),
            "queue_error_total": int(autorate_storage.get("queue", {}).get("error_total", 0) or 0),
            "write_lock_failure_total": int(autorate_storage.get("writes", {}).get("lock_failure_total", 0) or 0),
            "write_max_duration_ms": float(autorate_storage.get("writes", {}).get("max_duration_ms") or 0.0),
            "checkpoint_busy": int(autorate_checkpoint.get("busy", 0) or 0),
            "cycle_utilization_pct": autorate_utilization,
        },
        "steering": {
            "pending_writes": int(steering_storage.get("pending_writes", 0) or 0),
            "queue_error_total": int(steering_storage.get("queue", {}).get("error_total", 0) or 0),
            "write_lock_failure_total": int(steering_storage.get("writes", {}).get("lock_failure_total", 0) or 0),
            "write_max_duration_ms": float(steering_storage.get("writes", {}).get("max_duration_ms") or 0.0),
            "checkpoint_busy": int(steering_checkpoint.get("busy", 0) or 0),
            "cycle_utilization_pct": steering_utilization,
        },
        "metrics_export": {
            "autorate_write_success_total": _parse_metric_value(metrics_text, "wanctl_storage_write_success_total", "autorate"),
            "steering_write_success_total": _parse_metric_value(metrics_text, "wanctl_storage_write_success_total", "steering"),
        },
    }

    severe = []
    moderate = []

    total_lock_failures = observed["autorate"]["write_lock_failure_total"] + observed["steering"]["write_lock_failure_total"]
    max_pending = max(observed["autorate"]["pending_writes"], observed["steering"]["pending_writes"])
    max_duration = max(observed["autorate"]["write_max_duration_ms"], observed["steering"]["write_max_duration_ms"])
    total_queue_errors = observed["autorate"]["queue_error_total"] + observed["steering"]["queue_error_total"]
    total_checkpoint_busy = observed["autorate"]["checkpoint_busy"] + observed["steering"]["checkpoint_busy"]
    max_utilization = max(v for v in [autorate_utilization, steering_utilization] if v is not None) if any(v is not None for v in [autorate_utilization, steering_utilization]) else None

    if total_lock_failures >= 3:
        severe.append("multiple lock failures observed")
    elif total_lock_failures > 0:
        moderate.append("lock failures observed")

    if max_pending >= 20:
        severe.append("deferred write backlog exceeded 20 items")
    elif max_pending >= 5:
        moderate.append("deferred write backlog exceeded 5 items")

    if max_duration >= 50.0:
        severe.append("write duration exceeded 50ms")
    elif max_duration >= 15.0:
        moderate.append("write duration exceeded 15ms")

    if total_queue_errors > 0:
        moderate.append("deferred queue drain errors observed")

    if total_checkpoint_busy > 0:
        moderate.append("checkpoint busy signal observed")

    if max_utilization is not None and max_utilization >= 95.0:
        severe.append("cycle utilization exceeded 95%")
    elif max_utilization is not None and max_utilization >= 80.0:
        moderate.append("cycle utilization exceeded 80%")

    if severe:
        classification = "plan_split_db_phase"
        rationale = severe + moderate
    elif moderate:
        classification = "reduce_write_pressure"
        rationale = moderate
    else:
        classification = "keep_shared_db"
        rationale = ["no sustained lock, queue, checkpoint, or cycle-budget pressure observed"]

    return {
        "classification": classification,
        "rationale": rationale,
        "observed": observed,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--autorate-health", required=True, type=Path)
    parser.add_argument("--steering-health", required=True, type=Path)
    parser.add_argument("--metrics-text", required=True, type=Path)
    args = parser.parse_args()

    autorate_payload = _load_json(args.autorate_health)
    steering_payload = _load_json(args.steering_health)
    metrics_text = args.metrics_text.read_text()

    summary = _build_summary(
        _extract_storage_section(autorate_payload.get("wans", [{}])[0] if isinstance(autorate_payload.get("wans"), list) and autorate_payload.get("wans") else {}, "storage"),
        _extract_storage_section(steering_payload, "storage"),
        _extract_cycle_utilization(autorate_payload.get("wans", [{}])[0] if isinstance(autorate_payload.get("wans"), list) and autorate_payload.get("wans") else {}),
        _extract_cycle_utilization(steering_payload),
        metrics_text,
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
