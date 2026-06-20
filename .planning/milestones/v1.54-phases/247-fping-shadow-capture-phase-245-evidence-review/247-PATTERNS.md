# Phase 247: fping Shadow Capture + Phase 245 Evidence Review - Pattern Map

**Mapped:** 2026-06-18
**Files analyzed:** 4 (3 new code/script files + 1 document artifact)
**Analogs found:** 4 / 4

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `scripts/phase247-fping-shadow.py` | utility/script | streaming, event-driven | `scripts/capture_fping_fixtures.py` | role-match (same FpingMeasurement import + argparse + signal pattern); also draws from RESEARCH.md core loop |
| `scripts/phase247-safe18-boundary-check.sh` | utility/script | batch | `scripts/phase245-safe17-boundary-check.sh` | exact |
| `tests/test_phase247_shadow_script.py` | test | batch | `tests/test_phase245_gate_eval.py` + `tests/test_fping_measurement.py` | role-match |
| `.planning/phases/247-.../247-METHODOLOGY-REVIEW.md` | document artifact | — | `scripts/phase245-gate-eval.py` evaluate() output shape + RESEARCH.md table | content-match |

---

## Pattern Assignments

---

### `scripts/phase247-fping-shadow.py` (utility script, streaming)

**Primary analog:** `scripts/capture_fping_fixtures.py`
**Secondary analog:** RESEARCH.md "Shadow Script Core Loop" (lines 390–507 of 247-RESEARCH.md — verified against `src/wanctl/fping_measurement.py`)

#### Imports pattern (`scripts/capture_fping_fixtures.py` lines 1–22)

```python
from __future__ import annotations

import argparse
import json
import logging
import shutil
import subprocess
import sys
import time
from pathlib import Path

from wanctl.fping_measurement import FpingMeasurement
```

For the shadow script, also add:
```python
import signal
import threading
import yaml

from wanctl.fping_measurement import FpingMeasurement, FpingThread
```

Note: `capture_fping_fixtures.py` imports `FpingMeasurement` directly without sys.path manipulation because it runs from within the project venv. The shadow script runs on cake-shaper against `/opt/wanctl/src`; it needs a `sys.path.insert(0, str(Path("/opt/wanctl/src")))` guard at the top before the wanctl imports, following the pattern from RESEARCH.md.

#### FpingMeasurement instantiation pattern (`scripts/capture_fping_fixtures.py` lines 60–68)

```python
measurement = FpingMeasurement(
    {"source_ip": source_ip, "count": count, "period_ms": period_ms},
    logger,
)
```

The shadow script uses the same dict-based config, adding `timeout_grace_sec`. Config values come from `configs/spectrum.yaml`, not hardcoded. The `is_available()` check should gate startup (line 69 of `fping_measurement.py`).

#### FpingThread instantiation and lifecycle (`src/wanctl/fping_measurement.py` lines 291–352)

```python
thread = FpingThread(
    measurement=measurement,
    hosts_fn=lambda: reflectors,
    cadence_sec=cadence_sec,
    shutdown_event=shutdown,
    logger=logger,
)
thread.start()
# ... poll loop ...
thread.stop()
```

Key constraint from `fping_measurement.py` line 299: `measurement._timeout >= cadence_sec` raises `ValueError`. With factory defaults (count=5, period_ms=200, grace=2.0), timeout = 3.0s, so cadence_sec must be > 3.0. The factory uses 10.0s (verified in `rtt_backend_factory.py`).

#### NDJSON append pattern (`scripts/phase243-bench-run.sh` lines 101–116, `verify_journal_invocation` function)

```python
with OUTPUT_PATH.open("a") as fh:
    fh.write(json.dumps(record) + "\n")
    fh.flush()  # critical for overnight soaks
```

Flush after every write. Each NDJSON line is self-contained so partial writes on SIGINT leave the file valid up to the last complete line.

#### Signal handling pattern (from `scripts/capture_fping_fixtures.py` and RESEARCH.md)

```python
shutdown = threading.Event()

def _handle_signal(sig, frame):
    logger.info(f"caught signal {sig}, shutting down")
    shutdown.set()

signal.signal(signal.SIGINT, _handle_signal)
signal.signal(signal.SIGTERM, _handle_signal)
```

Use `shutdown.wait(timeout=cadence_sec)` as the sleep in the poll loop so SIGINT breaks out immediately without sleeping the full cadence interval.

#### Config reading pattern (from RESEARCH.md Pattern 3, verified against `configs/spectrum.yaml`)

```python
config_path = Path("/opt/wanctl/configs/spectrum.yaml")
with config_path.open() as fh:
    cfg = yaml.safe_load(fh)

reflectors = cfg["continuous_monitoring"]["ping_hosts"]   # not cfg["ping_hosts"] -- nested
source_ip = cfg["ping_source_ip"]                        # at root level
```

The `measurement.fping` section is absent from `configs/spectrum.yaml` (verified: `grep -n "fping" configs/spectrum.yaml` returns nothing). Use factory defaults: count=5, period_ms=200, cadence_sec=10.0, timeout_grace_sec=2.0.

#### NDJSON record schema (from `src/wanctl/rtt_backend.py` lines 36–54)

`RttSample` fields to serialize per sample:
```python
record = {
    "type": "rtt_sample",
    "ts": time.time(),
    "rtt_ms": sample.rtt_ms,
    "measurement_ms": sample.measurement_ms,
    "per_host_results": sample.per_host_results,    # dict[str, float | None]
    "per_host_loss": sample.per_host_loss,           # dict[str, float | None]
    "successful_hosts": list(sample.successful_hosts),
    "active_hosts": list(sample.active_hosts),
    "backend": sample.backend,                       # will be "fping"
}
```

Probe stats record (from `src/wanctl/perf_profiler.py` lines 145–152):
```python
stats = thread.get_profile_stats()
# returns: {"count": int, "min_ms": float, "max_ms": float,
#            "avg_ms": float, "p95_ms": float, "p99_ms": float, "samples": list}
stats_record = {
    "type": "probe_stats",
    "ts": time.time(),
    "probe_count_at_snapshot": probe_count,
    **{k: v for k, v in stats.items() if k != "samples"},  # exclude raw samples list
}
```

Log `probe_stats` every `STATS_INTERVAL_PROBES` iterations (100 recommended = ~16 min at 10s cadence), not just at the end. The `OperationProfiler` has `max_samples=1200` (from `FpingThread.__init__` line 308) — at 10s cadence, 1200 samples = 3.3h of data. Periodic snapshots preserve the full 12h distribution.

#### Output path and directory creation

```python
OUTPUT_PATH = Path("/var/lib/wanctl/phase247-fping-shadow.ndjson")
OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
```

Expose `--output` CLI flag for override (following `phase219_ingestion_digest.py` pattern with `--snapshot-dir` argument).

#### argparse pattern (`scripts/phase219_ingestion_digest.py` lines 69–97)

```python
def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Phase 247 fping shadow capture")
    parser.add_argument("--config", type=Path, default=Path("/opt/wanctl/configs/spectrum.yaml"))
    parser.add_argument("--output", type=Path, default=OUTPUT_PATH)
    parser.add_argument("--stats-interval", type=int, default=100)
    return parser

def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    # ...

if __name__ == "__main__":
    sys.exit(main())
```

#### Error handling pattern (`scripts/phase219_ingestion_digest.py` lines 113–135)

```python
if not measurement.is_available():
    logger.error("fping binary not found")
    sys.exit(1)
```

Print errors to stderr with a script-name prefix (e.g., `"phase247-shadow: ..."`) matching the `phase219-ingestion-digest: ...` convention in `phase219_ingestion_digest.py`.

---

### `scripts/phase247-safe18-boundary-check.sh` (utility/script, batch)

**Analog:** `scripts/phase245-safe17-boundary-check.sh` (exact match)

#### Header and setup pattern (`phase245-safe17-boundary-check.sh` lines 1–30)

```bash
#!/usr/bin/env bash
# Phase 247 SAFE-18 v1.54 boundary check.
set -euo pipefail

ANCHOR="e090a200"  # v1.53 close commit (Phase 247 uses SAFE-18, pinned to v1.53 close)
OUT=".planning/phases/247-fping-shadow-capture-phase-245-evidence-review/evidence/safe18-boundary-247.json"
```

SAFE-18 protected files per REQUIREMENTS.md (from RESEARCH.md Pattern 4):
- `src/wanctl/wan_controller.py`
- `src/wanctl/queue_controller.py`
- `src/wanctl/cake_signal.py`
- `src/wanctl/rtt_backend.py`
- `src/wanctl/fping_measurement.py`
- `src/wanctl/rtt_measurement.py`
- `src/wanctl/alert_engine.py`

#### Core diff pattern (`phase245-safe17-boundary-check.sh` lines 527–536)

```bash
CHANGED_PATHS="$(git diff --name-only "${ANCHOR_SHA}" HEAD -- src/wanctl/)"
DISALLOWED_PATHS="$(printf '%s\n' "${CHANGED_PATHS}" | grep -Ev "${SAFE18_ALLOWLIST_RE}" || true)"
```

SAFE-18 is simpler than SAFE-17: Phase 247 adds only `scripts/` files and a `.planning/` document — zero diff in `src/wanctl/`. The allowlist regex should reject any `src/wanctl/` change as disallowed (empty allowlist = all changes disallowed).

#### `require_command` and `emit_evidence` patterns (lines 51–57, 58–210)

Copy the `require_command` function verbatim. The `emit_evidence` Python heredoc can be simplified for SAFE-18: fewer fields needed since there are no allowlisted src/wanctl changes at all.

#### `--self-test` pattern (`phase245-safe17-boundary-check.sh` lines 213–257)

Copy the git worktree self-test pattern. The self-test commits a disallowed edit to a protected file and verifies the allowlist rejects it. For Phase 247, the test file should be one of the SAFE-18 protected files (e.g., `src/wanctl/queue_controller.py`).

---

### `tests/test_phase247_shadow_script.py` (test, batch)

**Primary analog:** `tests/test_phase245_gate_eval.py` (importlib.util pattern for testing scripts)
**Secondary analog:** `tests/test_fping_measurement.py` (FpingThread + Mock + threading.Event pattern)

#### Module import pattern (`tests/test_phase245_gate_eval.py` lines 1–21)

```python
import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "phase247-fping-shadow.py"

def load_module():
    spec = importlib.util.spec_from_file_location("phase247_fping_shadow", SCRIPT)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module
```

This pattern isolates the script under test without needing it to be a package.

#### FpingThread Mock pattern (`tests/test_fping_measurement.py` lines 273–298)

```python
import threading
import time
import logging
from unittest.mock import Mock

shutdown = threading.Event()
measurement = Mock()
measurement._timeout = 0.01  # must be < cadence_sec
thread = FpingThread(
    measurement=measurement,
    hosts_fn=lambda: ["198.51.100.10"],
    cadence_sec=0.05,
    shutdown_event=shutdown,
    logger=logging.getLogger("test"),
)
thread.start()
time.sleep(0.12)
shutdown.set()
thread.stop()
assert thread.get_latest() is sample
```

For unit tests of the shadow script's config loading and NDJSON writing, use `tmp_path` fixture for the output file, patch `yaml.safe_load` to return a known config dict, and mock `FpingThread` entirely to avoid subprocess calls.

#### Test file structure (from `tests/test_phase245_gate_eval.py` and `tests/test_phase243_safe17_verifier.py`)

```python
ROOT = Path(__file__).resolve().parents[1]

class TestConfigLoading:
    def test_missing_continuous_monitoring_raises(self, tmp_path): ...
    def test_valid_config_extracts_reflectors(self, tmp_path): ...

class TestRttSampleLogging:
    def test_rtt_sample_written_as_ndjson(self, tmp_path): ...
    def test_ndjson_fields_match_schema(self, tmp_path): ...

class TestProbeStatsLogging:
    def test_stats_written_at_interval(self, tmp_path): ...
    def test_stats_exclude_samples_key(self, tmp_path): ...

class TestShutdown:
    def test_sigint_writes_final_stats(self, tmp_path): ...
```

#### Safe17 verifier test pattern (`tests/test_phase245_safe17_verifier.py` lines 1–33)

```python
ROOT = Path(__file__).resolve().parents[1]
VERIFIER = ROOT / "scripts" / "phase247-safe18-boundary-check.sh"
PHASE_CLOSE_ANCHOR = "e090a200"  # v1.53 close; pin to commit, not HEAD

def run(cmd, *, cwd=ROOT, env=None):
    return subprocess.run(cmd, cwd=cwd, text=True, capture_output=True,
                          check=False, env={**os.environ, **(env or {})})
```

Pin `PHASE_CLOSE_ANCHOR` to the v1.53 close commit, not HEAD, so later phases don't invalidate the test (per MEMORY.md: "SAFE-17 boundary tests must pin to close commit").

---

### `.planning/phases/247-.../247-METHODOLOGY-REVIEW.md` (document artifact)

**Analog:** `scripts/phase245-gate-eval.py` `evaluate()` output — the gate IDs, threshold names, and measured values are all sourced from the Phase 245 AB verdict and thresholds JSON.

This is a static document written from git-retrievable evidence. No code pattern applies — it is a Markdown table with one row per AB-03 gate.

#### Source data locations

| Artifact | How to retrieve |
|----------|----------------|
| Pre-committed thresholds | `scripts/phase245-thresholds.json` (present in working tree) |
| AB verdict JSON | `git show 7e6844a2:.planning/phases/245-live-a-b-rollback-anchor/245-AB-VERDICT.json` |
| Run summary JSON | `git show 7e6844a2:.planning/phases/245-live-a-b-rollback-anchor/evidence/phase245-ab-20260619T002509Z-summary.json` |

#### Table structure (from RESEARCH.md "AB-03 Methodology Review Table Structure")

| Gate | Threshold | Phase 245 fping | Phase 245 icmplib | Verdict | Diagnosis |
|------|-----------|-----------------|-------------------|---------|-----------|
| `rtt_agreement` | delta < 3.0ms | 33.22ms | 33.58ms → Δ=0.36ms | PASS | — |
| `cycle_budget_nonregression` (avg) | fping_avg ≤ icmplib_avg × 1.20 | 48.3ms | 49.3ms → -2.0% | PASS | — |
| `cycle_budget_nonregression` (p99 relative) | fping_p99 ≤ icmplib_p99 × 1.20 | 112.4ms | 120.7ms → -6.9% | PASS | — |
| `cycle_budget_nonregression` (p99 absolute) | fping_p99 < 10.0ms | 112.4ms | — | **FAIL** | SOLE FAILING GATE |
| `loss_detection_nonregression` | delta < 1.0% | 0.0% | 0.0% | PASS | — |
| `min_backend_cycle_fraction` | fraction ≥ 0.95 | 1.0 | 1.0 | PASS | — |
| `unexpected_restarts` | 0 | 0 | — | PASS | — |
| `steering_decision_stability` | delta < 5.0% | 0% | 0% | PASS | — |

Gate IDs are from `phase245-gate-eval.py` `evaluate()` (lines 138, 154, 170, 179, 193, 209). Threshold values are from `scripts/phase245-thresholds.json`.

#### Finding summary structure

The document must state the root cause unambiguously:
- Failing gate: `cycle_budget_nonregression` absolute ceiling (10.0ms)
- Calibration source: `ICMPLIB_REPRESENTATIVE_P99_MS=6.9ms` + 3.5ms tolerance from idle/unloaded baseline
- Both backends exceeded ceiling under load: fping p99=112.4ms, icmplib p99=120.7ms
- fping was NOT the cause: icmplib p99 was HIGHER; comparative gate was PASS (-6.9%)
- Conclusion: calibration mismatch, not fping inferiority

---

## Shared Patterns

### FpingMeasurement Import
**Source:** `src/wanctl/fping_measurement.py` lines 1–30, `scripts/capture_fping_fixtures.py` line 22
**Apply to:** `scripts/phase247-fping-shadow.py`, `tests/test_phase247_shadow_script.py`

```python
from wanctl.fping_measurement import FpingMeasurement, FpingThread
```

When running on cake-shaper (outside the venv), prepend:
```python
import sys
from pathlib import Path
src_path = Path("/opt/wanctl/src")
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))
```

### NDJSON Append
**Source:** `scripts/phase243-bench-run.sh` lines 101–116 (NDJSON append pattern in `verify_journal_invocation`)
**Apply to:** `scripts/phase247-fping-shadow.py`

One JSON object per line, `fh.flush()` after every write. No atomic rename for append — each line is self-contained.

### Git Boundary Check (SAFE-N)
**Source:** `scripts/phase245-safe17-boundary-check.sh` (full file)
**Apply to:** `scripts/phase247-safe18-boundary-check.sh`

Copy the overall structure: `set -euo pipefail`, `require_command`, `--anchor`/`--out` args, dirty-tree check, diff against anchor, `emit_evidence` Python heredoc, `--self-test` worktree pattern.

### Test importlib.util module loading
**Source:** `tests/test_phase245_gate_eval.py` lines 14–21
**Apply to:** `tests/test_phase247_shadow_script.py`, `tests/test_phase247_safe18_verifier.py` (for Python parts)

```python
import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "phase247-fping-shadow.py"

def load_module():
    spec = importlib.util.spec_from_file_location("phase247_fping_shadow", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module
```

### argparse + `main(argv=None)` + `sys.exit(main())` pattern
**Source:** `scripts/phase219_ingestion_digest.py` lines 69–165
**Apply to:** `scripts/phase247-fping-shadow.py`

Return integer exit code from `main()`. Use `if __name__ == "__main__": raise SystemExit(main())` or `sys.exit(main())`.

### Phase verifier test: worktree + pinned anchor
**Source:** `tests/test_phase245_safe17_verifier.py` lines 1–60
**Apply to:** `tests/test_phase247_safe18_verifier.py` (or `tests/test_phase247_shadow_script.py` if combined)

Pin `PHASE_CLOSE_ANCHOR` to the exact commit that closed Phase 246 (the v1.53 final anchor, `e090a200`), not HEAD.

---

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| (none) | — | — | All files have strong analogs in the codebase |

---

## Metadata

**Analog search scope:** `scripts/`, `src/wanctl/`, `tests/`, `.planning/phases/`
**Files read:** `scripts/phase219_ingestion_digest.py`, `scripts/phase243-bench-run.sh`, `scripts/phase245-safe17-boundary-check.sh`, `scripts/capture_fping_fixtures.py`, `scripts/phase245-gate-eval.py`, `src/wanctl/fping_measurement.py` (partial), `src/wanctl/rtt_backend.py`, `src/wanctl/perf_profiler.py` (partial), `tests/test_fping_measurement.py` (partial), `tests/test_phase245_gate_eval.py` (partial), `tests/test_phase245_safe17_verifier.py` (partial)
**Pattern extraction date:** 2026-06-18
