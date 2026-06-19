#!/usr/bin/env python3
# ruff: noqa: N999,E402,TRY004
"""Phase 247 fping shadow capture.

Runs a standalone, read-only fping shadow probe on cake-shaper using the real
wanctl FpingMeasurement/FpingThread code path and appends NDJSON evidence to
/var/lib/wanctl/phase247-fping-shadow.ndjson by default.

Phase 248 must compute TWO distinct full-window p99 values from probe_cycle
records: rtt_p99_ms (from rtt_ms across SUCCESSFUL records) and
probe_elapsed_p99_ms_full_window (from elapsed_ms across SUCCESSFUL records;
inferred/dropped records have elapsed_ms=null and are EXCLUDED). Do NOT use
probe_stats.p99_ms (OperationProfiler rolling window, last ~3.3h only).
PROF-01 requires BOTH the raw RTT distribution AND the cycle-timing distribution.
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import shlex
import signal
import subprocess
import sys
import threading
import time
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

import yaml

_DEPLOY_SRC = Path("/opt/wanctl/src")
_LOCAL_SRC = Path(__file__).resolve().parents[1] / "src"
_SCRIPT_ROOT = Path(__file__).resolve().parents[1]
_FLAT_DEPLOY_PARENT = _SCRIPT_ROOT.parent if (_SCRIPT_ROOT / "__init__.py").exists() else None
for _src_path in (_DEPLOY_SRC, _LOCAL_SRC, _FLAT_DEPLOY_PARENT):
    if _src_path is None:
        continue
    if _src_path.exists() and str(_src_path) not in sys.path:
        sys.path.insert(0, str(_src_path))

from wanctl.fping_measurement import FpingMeasurement, FpingThread

OUTPUT_PATH = Path("/var/lib/wanctl/phase247-fping-shadow.ndjson")
CONFIG_PATH = Path("/opt/wanctl/configs/spectrum.yaml")
STATS_INTERVAL_PROBES = 100


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Phase 247 fping shadow capture")
    parser.add_argument("--config", type=Path, default=CONFIG_PATH)
    parser.add_argument("--output", type=Path, default=OUTPUT_PATH)
    parser.add_argument("--stats-interval", type=int, default=STATS_INTERVAL_PROBES)
    return parser


def load_spectrum_config(config_path: Path) -> dict[str, Any]:
    with config_path.open(encoding="utf-8") as fh:
        text = fh.read()
    if config_path.suffix == ".sh":
        return _load_cake_autorate_config(text)
    cfg = yaml.safe_load(text) or {}
    continuous = cfg.get("continuous_monitoring")
    if not isinstance(continuous, dict):
        raise ValueError("missing continuous_monitoring section")
    reflectors = continuous.get("ping_hosts")
    if not isinstance(reflectors, list) or not reflectors or not all(isinstance(host, str) and host for host in reflectors):
        raise ValueError("continuous_monitoring.ping_hosts must be a non-empty string list")
    source_ip = cfg.get("ping_source_ip")
    if not isinstance(source_ip, str) or not source_ip:
        raise ValueError("ping_source_ip must be a non-empty string")
    return cfg


def _load_cake_autorate_config(text: str) -> dict[str, Any]:
    """Return the shadow config shape from a cake-autorate shell config."""
    reflectors_match = re.search(r"(?ms)^reflectors=\((.*?)\)", text)
    if reflectors_match is None:
        raise ValueError("cake-autorate config missing reflectors=(...)")
    reflectors = shlex.split(reflectors_match.group(1))
    if not reflectors:
        raise ValueError("cake-autorate reflectors list is empty")

    ping_args_match = re.search(r'(?m)^ping_extra_args=(.*)$', text)
    if ping_args_match is None:
        raise ValueError("cake-autorate config missing ping_extra_args")
    ping_args_raw = ping_args_match.group(1).strip()
    if (ping_args_raw.startswith('"') and ping_args_raw.endswith('"')) or (
        ping_args_raw.startswith("'") and ping_args_raw.endswith("'")
    ):
        ping_args_raw = ping_args_raw[1:-1]
    ping_args = shlex.split(ping_args_raw)
    source_ip = None
    for idx, token in enumerate(ping_args):
        if token == "-S" and idx + 1 < len(ping_args):
            source_ip = ping_args[idx + 1]
            break
    if not source_ip:
        raise ValueError("cake-autorate ping_extra_args missing '-S <source_ip>'")

    return {
        "ping_source_ip": source_ip,
        "continuous_monitoring": {"ping_hosts": reflectors},
    }


def _fping_defaults(cfg: dict[str, Any]) -> tuple[float, int, int, float]:
    fping_section = ((cfg.get("measurement") or {}).get("fping") or {})
    cadence_sec = float(fping_section.get("cadence_sec", 10.0))
    count = int(fping_section.get("count", 5))
    period_ms = int(fping_section.get("period_ms", 200))
    timeout_grace_sec = float(fping_section.get("timeout_grace_sec", 2.0))
    return cadence_sec, count, period_ms, timeout_grace_sec


def _get_script_version() -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return "unknown"
    if result.returncode != 0:
        return "unknown"
    return result.stdout.strip() or "unknown"


def _write_record(fh: Any, record: dict[str, Any]) -> None:
    fh.write(json.dumps(record, sort_keys=True) + "\n")
    fh.flush()


def _stats_record(record_type: str, thread: Any, probe_index: int, now_fn: Callable[[], float]) -> dict[str, Any]:
    stats = dict(thread.get_profile_stats() or {})
    stats.pop("samples", None)
    return {
        "type": record_type,
        "ts": now_fn(),
        "probe_count_at_snapshot": probe_index,
        **stats,
    }


def _probe_cycle_record(sample: Any, probe_index: int, source_ip: str, now_fn: Callable[[], float]) -> dict[str, Any]:
    successful_hosts = tuple(getattr(sample, "successful_hosts", ()) or ())
    active_hosts = tuple(getattr(sample, "active_hosts", ()) or ())
    return {
        "type": "probe_cycle",
        "ts": now_fn(),
        "sample_monotonic_ts": sample.timestamp,
        "probe_index": probe_index,
        "elapsed_ms": sample.measurement_ms,
        "rtt_ms": sample.rtt_ms,
        "success": len(successful_hosts) > 0,
        "all_loss": len(successful_hosts) == 0,
        "inferred": False,
        "reflector_count": len(active_hosts),
        "source_ip": source_ip,
        "backend": sample.backend,
        "per_host_results": dict(sample.per_host_results),
        "per_host_loss": dict(sample.per_host_loss),
        "active_hosts": sorted(active_hosts),
        "successful_hosts": sorted(successful_hosts),
    }


def _inferred_dropped_record(probe_index: int, source_ip: str, now_fn: Callable[[], float]) -> dict[str, Any]:
    return {
        "type": "probe_cycle",
        "success": False,
        "all_loss": True,
        "dropped": True,
        "inferred": True,
        "elapsed_ms": None,
        "rtt_ms": None,
        "reason": "no_new_sample_within_cadence",
        "expected_probe_index": probe_index + 1,
        "ts": now_fn(),
        "source_ip": source_ip,
    }


def run_capture_loop(
    *,
    thread: Any,
    fh: Any,
    shutdown: threading.Event,
    source_ip: str,
    reflectors: list[str],
    config_path: Path,
    cadence_sec: float,
    count: int,
    period_ms: int,
    timeout_grace_sec: float,
    stats_interval: int,
    now_fn: Callable[[], float] = time.time,
    max_polls: int | None = None,
) -> int:
    """Run the NDJSON capture loop; exposed for unit tests."""
    if stats_interval <= 0:
        raise ValueError("stats_interval must be positive")

    _write_record(
        fh,
        {
            "type": "run_start",
            "ts": now_fn(),
            "source_ip": source_ip,
            "reflectors": list(reflectors),
            "config_path": str(config_path),
            "script_version": _get_script_version(),
            "cadence_sec": cadence_sec,
            "count": count,
            "period_ms": period_ms,
            "timeout_grace_sec": timeout_grace_sec,
        },
    )

    last_sample_ts: float | None = None
    last_sample_wall_time = now_fn()
    probe_index = 0
    polls = 0

    while not shutdown.is_set():
        if max_polls is None:
            shutdown.wait(timeout=cadence_sec)
            if shutdown.is_set():
                break
        sample = thread.get_latest()
        observed_new_sample = sample is not None and sample.timestamp != last_sample_ts

        if observed_new_sample:
            assert sample is not None
            probe_index += 1
            _write_record(fh, _probe_cycle_record(sample, probe_index, source_ip, now_fn))
            last_sample_ts = sample.timestamp
            last_sample_wall_time = now_fn()
            if probe_index % stats_interval == 0:
                _write_record(fh, _stats_record("probe_stats", thread, probe_index, now_fn))
        elif now_fn() - last_sample_wall_time > cadence_sec + timeout_grace_sec:
            _write_record(fh, _inferred_dropped_record(probe_index, source_ip, now_fn))
            last_sample_wall_time += cadence_sec

        polls += 1
        if max_polls is not None and polls >= max_polls:
            break

    _write_record(fh, _stats_record("probe_stats_final", thread, probe_index, now_fn))
    return probe_index


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    logger = logging.getLogger("phase247-shadow")

    try:
        cfg = load_spectrum_config(args.config)
    except (OSError, ValueError, yaml.YAMLError) as exc:
        print(f"phase247-shadow: config error: {exc}", file=sys.stderr)
        return 1

    source_ip = cfg["ping_source_ip"]
    reflectors = list(cfg["continuous_monitoring"]["ping_hosts"])
    cadence_sec, count, period_ms, timeout_grace_sec = _fping_defaults(cfg)
    fping_config = {
        "source_ip": source_ip,
        "count": count,
        "period_ms": period_ms,
        "timeout_grace_sec": timeout_grace_sec,
    }

    measurement = FpingMeasurement(fping_config, logger)
    if not measurement.is_available():
        print("phase247-shadow: fping binary not found", file=sys.stderr)
        return 1

    shutdown = threading.Event()

    def _handle_signal(signum: int, _frame: Any) -> None:
        logger.info("caught signal %s, shutting down", signum)
        shutdown.set()

    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    thread = FpingThread(
        measurement=measurement,
        hosts_fn=lambda: reflectors,
        cadence_sec=cadence_sec,
        shutdown_event=shutdown,
        logger=logger,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    thread.start()
    try:
        with args.output.open("a", encoding="utf-8") as fh:
            probe_count = run_capture_loop(
                thread=thread,
                fh=fh,
                shutdown=shutdown,
                source_ip=source_ip,
                reflectors=reflectors,
                config_path=args.config,
                cadence_sec=cadence_sec,
                count=count,
                period_ms=period_ms,
                timeout_grace_sec=timeout_grace_sec,
                stats_interval=args.stats_interval,
            )
    finally:
        shutdown.set()
        thread.stop()
    logger.info("shadow capture complete; total_observed_probes=%s", probe_count)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
