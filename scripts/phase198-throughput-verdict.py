#!/usr/bin/env python3
"""Phase 198 VALN-05a throughput verdict.

Reads a flent manifest with three runs and emits throughput-verdict.json
applying the locked rule: PASS iff medians_above_532 >= 2 AND
median_of_medians_mbps >= 532.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path
from typing import Any


def _copy_run(run: dict[str, Any]) -> dict[str, Any]:
    return {
        "run": run.get("run"),
        "median_mbps": float(run["median_mbps"]),
        "raw_path": run.get("raw_path"),
        "egress_ip": run.get("egress_ip"),
        "egress_org": run.get("egress_org"),
    }


def build_verdict(manifest: dict[str, Any], threshold: float, label: str) -> dict[str, Any]:
    runs = [_copy_run(run) for run in manifest.get("runs", [])]
    if len(runs) != 3:
        raise ValueError(f"expected exactly 3 runs in manifest, got {len(runs)}")
    medians = [run["median_mbps"] for run in runs]
    medians_above_threshold = sum(1 for median in medians if median >= threshold)
    median_of_medians = float(statistics.median(medians))
    two_of_three = medians_above_threshold >= 2
    mom_ok = median_of_medians >= threshold
    verdict = "PASS" if two_of_three and mom_ok else "FAIL"
    return {
        "phase": 198,
        "leg": "cake-primary",
        "label": label,
        "local_bind": "10.10.110.226",
        "acceptance_mbps": threshold,
        "rule": "VALN-05a: medians_above_532 >= 2 AND median_of_medians_mbps >= 532",
        "runs": runs,
        "median_of_medians_mbps": median_of_medians,
        "medians_above_532": medians_above_threshold,
        "two_of_three_at_or_above_532_mbps": two_of_three,
        "median_of_medians_at_or_above_532_mbps": mom_ok,
        "verdict": verdict,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--threshold", type=float, default=532.0)
    parser.add_argument("--label", default="phase198_rerun_3run")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    manifest = json.loads(Path(args.manifest).read_text(encoding="utf-8"))
    result = build_verdict(manifest, args.threshold, args.label)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    medians = "/".join(f"{run['median_mbps']:.6f}" for run in result["runs"])
    print(
        f"Phase 198 throughput verdict: {result['verdict']} "
        f"(medians={medians}, MoM={result['median_of_medians_mbps']:.6f}, "
        f"medians_above_532={result['medians_above_532']})",
        file=sys.stderr,
    )
    return 0 if result["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
