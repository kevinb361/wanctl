# Phase 247: fping Shadow Capture + Phase 245 Evidence Review - Research

**Researched:** 2026-06-18
**Domain:** fping shadow profiling script; Phase 245 AB-03 threshold methodology
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** Shadow capture is script-based standalone — a profiling script runs on cake-shaper without any daemon code changes. No touches to `autorate_continuous.py`, `rtt_backend_factory.py`, or any controller-path file. SAFE-18 holds trivially.
- **D-02:** The script imports `FpingMeasurement` directly from `src/wanctl/fping_measurement.py` and reads `configs/spectrum.yaml` to obtain the live reflector list, `source_ip`, and cadence. This ensures the shadow fping runs the exact same code path production would use — not a diverged raw-fping subprocess call.
- **D-03:** Shadow samples are logged to an NDJSON file (one JSON object per sample, timestamped) on cake-shaper's filesystem. No DB writes in shadow mode.
- **D-04:** The goal is diagnosis — read the Phase 245 pre-committed threshold JSON and verdict evidence files, compare fping's measured values against each AB-03 dimension's pass/fail bound, and determine: was `rollback_trigger` caused by genuine fping RTT inferiority, or by threshold calibration mismatch (e.g., thresholds designed around icmplib's continuous-EWMA shape, not fping's burst-sampling shape)?
- **D-05:** Diagnosis output is a standalone artifact: `247-METHODOLOGY-REVIEW.md` — one row per AB-03 dimension (threshold, Phase 245 measured value, margin, diagnosis). This feeds Phase 248's distribution analysis directly and is the authoritative record of the methodology finding.
- **D-06:** Spectrum only — Phase 245 ran on Spectrum; profiling the same WAN produces directly comparable data. ATT is DSL (different RTT characteristics) and would muddy the comparison.
- **D-07:** Capture window: overnight soak ~12h. Enough to span idle + peak traffic patterns without delaying Phase 248. Matches soak discipline used in prior evidence phases.

### Claude's Discretion

- None listed in CONTEXT.md.

### Deferred Ideas (OUT OF SCOPE)

- Replacement AB-03 threshold methodology (new design from scratch) — Phase 248 scope, after shadow data is in hand.
- ATT shadow capture — deferred; ATT is DSL and would muddy Spectrum comparison.
- 24h full soak — not needed for Phase 247; 12h overnight is sufficient.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| PROF-01 | Run fping backend in shadow/read-only mode alongside icmplib on Spectrum, capturing raw RTT samples and cycle p99 timing without touching the control loop or production defaults. | D-01/D-02 locked: standalone script importing `FpingMeasurement`; FpingThread.get_profile_stats() provides p99 probe timing; FpingThread.get_latest() provides RTT samples. |
| PROF-02 | Re-examine Phase 245 AB-03 threshold methodology and rollback_trigger verdict to determine whether fping latency or threshold calibration drove the result. | Phase 245 verdict and thresholds retrieved from git history (commit 7e6844a2); root cause is clear from the numbers. |
</phase_requirements>

---

## Summary

Phase 247 has two parallel workstreams: (A) write and run a standalone shadow fping capture script on cake-shaper, and (B) produce a static methodology review document from already-existing Phase 245 evidence.

Workstream B is pure document work — all evidence is in git history (commit `7e6844a2`). The Phase 245 pre-committed thresholds and A/B summary are accessible via `git show` without any operator action on cake-shaper. The methodology finding is already clear from the numbers: the `cycle_budget_nonregression` gate failed because both backends measured cycle p99 > 100ms in Phase 245, while the absolute ceiling was calibrated at 10ms from an idle/unloaded baseline. This is a calibration mismatch, not fping-specific inferiority — icmplib's p99 (120.7ms) also would have failed the same ceiling.

Workstream A requires a Python script (`scripts/phase247-fping-shadow.py`) that runs on cake-shaper via SSH. The script instantiates `FpingMeasurement` and `FpingThread` directly from the wanctl source tree at `/opt/wanctl`, reads `configs/spectrum.yaml` for reflectors and source IP, and appends one NDJSON record per `FpingThread.get_latest()` poll to a local capture file. It also calls `FpingThread.get_profile_stats()` periodically to log probe cycle timing (fork+exec+parse elapsed ms per burst), which is what Phase 248 needs for the p99 distribution comparison.

SAFE-18 is trivially satisfied: no daemon files are touched. The script is a new file in `scripts/` with no imports from controller-path modules.

**Primary recommendation:** Write the methodology review document first (no operator action required), then write and deploy the shadow script as a second task. The review artifact is fully self-contained and unblocked.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| fping shadow sampling | Script (standalone) | — | D-01 locked: no daemon involvement; script runs on cake-shaper via SSH |
| RTT measurement | `FpingMeasurement.probe()` | — | D-02 locked: real production code path, not a diverged raw-fping call |
| Background cadence management | `FpingThread` | — | Background thread owns the 10s cadence; script polls get_latest() |
| Probe cycle timing (p99) | `FpingThread.get_profile_stats()` | — | Returns OperationProfiler stats("fping_background_cycle") — fork+exec+parse per burst |
| NDJSON logging | Script | — | D-03: append-only NDJSON to local file on cake-shaper; no DB writes |
| AB-03 methodology review | Static document | — | All evidence already in git; pure read-and-write artifact |
| SAFE-18 boundary | Verifier script | — | New script in scripts/ directory; zero diff in protected files |

---

## Standard Stack

### Core

No new packages required. All dependencies are already in the wanctl venv and the system.

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `wanctl.fping_measurement` | existing | FpingMeasurement, FpingThread | D-02 locked: use real production code path [VERIFIED: codebase] |
| `wanctl.rtt_backend` | existing | RttSample dataclass | Used as the per-sample logging unit [VERIFIED: codebase] |
| `wanctl.perf_profiler` | existing | OperationProfiler (via FpingThread) | Returns p99 probe timing [VERIFIED: codebase] |
| `yaml` (PyYAML) | existing | Read configs/spectrum.yaml | Already a wanctl dependency [VERIFIED: codebase] |
| `fping` binary | 5.1 | RTT measurement | Confirmed present on dev machine [VERIFIED: `fping --version`] |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Importing FpingMeasurement | Raw subprocess fping | D-02 locks this; raw subprocess would create an unverified diverged code path |
| NDJSON append | SQLite | D-03 locks NDJSON; simpler, no schema, no lock contention with live DB |
| FpingThread | Manual sleep loop | FpingThread gives us the real cadence + profiler integration out of the box |

**Installation:** No new packages. Shadow script runs against the existing wanctl venv on cake-shaper.

---

## Package Legitimacy Audit

No new packages are installed in this phase. The shadow script uses only existing wanctl dependencies.

| Package | Registry | Age | Downloads | Source Repo | slopcheck | Disposition |
|---------|----------|-----|-----------|-------------|-----------|-------------|
| (none new) | — | — | — | — | — | — |

**Packages removed due to slopcheck [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none

---

## Architecture Patterns

### System Architecture Diagram

```
cake-shaper (SSH from dev)
├── /opt/wanctl/src/wanctl/
│   ├── fping_measurement.py  ──── imported by shadow script
│   ├── rtt_backend.py        ──── RttSample type
│   └── perf_profiler.py      ──── OperationProfiler (via FpingThread)
├── /opt/wanctl/configs/spectrum.yaml
│   └── ping_hosts: [1.1.1.1, 9.9.9.9, 208.67.222.222]
│       ping_source_ip: 10.10.110.223
│
├── scripts/phase247-fping-shadow.py  [NEW]
│   ├── reads spectrum.yaml → reflectors + source_ip
│   ├── instantiates FpingMeasurement(config, logger)
│   ├── instantiates FpingThread(..., cadence_sec=10.0, ...)
│   ├── FpingThread.start()
│   ├── poll loop (e.g. every 10s):
│   │   ├── FpingThread.get_latest() → RttSample | None
│   │   │   └── write NDJSON record: {ts, rtt_ms, per_host_results, ...}
│   │   └── every N polls: FpingThread.get_profile_stats()
│   │       └── append probe_stats NDJSON: {ts, count, avg_ms, p99_ms, ...}
│   └── FpingThread.stop() on SIGINT/SIGTERM
│
└── /var/lib/wanctl/phase247-fping-shadow.ndjson  [capture output]

Internet reflectors ← fping -S 10.10.110.223 → [1.1.1.1, 9.9.9.9, 208.67.222.222]

dev machine (.planning/)
└── 247-METHODOLOGY-REVIEW.md  [NEW — from Phase 245 git evidence, no operator action needed]
```

### Recommended Project Structure

```
scripts/
├── phase247-fping-shadow.py      # NEW: shadow capture script
├── phase247-safe18-boundary-check.sh  # NEW: SAFE-18 verifier

.planning/phases/247-*/
├── 247-METHODOLOGY-REVIEW.md    # NEW: AB-03 methodology finding artifact
└── evidence/
    ├── safe18-boundary-247.json         # from verifier
    └── phase247-shadow-summary.json     # end-of-soak rollup

tests/
└── test_phase247_shadow_script.py  # NEW: unit tests for shadow script
```

### Pattern 1: FpingThread Background Probe Loop

The shadow script instantiates FpingThread identically to how the factory would, but without wiring it to WANController. `FpingThread.start()` launches a daemon thread; the main script loop polls `get_latest()` on the same cadence as the thread (10s default from factory config).

```python
# Source: src/wanctl/fping_measurement.py (verified in codebase)
import threading
import time
import json
import logging
from wanctl.fping_measurement import FpingMeasurement, FpingThread

shutdown = threading.Event()
config = {
    "source_ip": "10.10.110.223",
    "count": 5,
    "period_ms": 200,
    "timeout_grace_sec": 2.0,
}
logger = logging.getLogger("phase247-shadow")
measurement = FpingMeasurement(config, logger)
hosts_fn = lambda: ["1.1.1.1", "9.9.9.9", "208.67.222.222"]
thread = FpingThread(measurement, hosts_fn, cadence_sec=10.0, shutdown_event=shutdown, logger=logger)
thread.start()

with open("/var/lib/wanctl/phase247-fping-shadow.ndjson", "a") as fh:
    try:
        while not shutdown.is_set():
            sample = thread.get_latest()
            if sample is not None:
                record = {
                    "ts": time.time(),
                    "rtt_ms": sample.rtt_ms,
                    "measurement_ms": sample.measurement_ms,
                    "per_host_results": sample.per_host_results,
                    "successful_hosts": list(sample.successful_hosts),
                }
                fh.write(json.dumps(record) + "\n")
                fh.flush()
            probe_stats = thread.get_profile_stats()
            # probe_stats["p99_ms"] is the fping_background_cycle p99 (fork+exec+parse)
            shutdown.wait(timeout=10.0)
    finally:
        thread.stop()
```

### Pattern 2: NDJSON Append (established in Phase 243/245)

One JSON object per line, no atomic rename needed for append (each line is self-contained). The Phase 243 `cycle.ndjson` and Phase 245 `.jsonl` evidence files established this pattern. Flush after each write to avoid data loss on interruption.

```python
# Established pattern from scripts/phase243-bench-run.sh and phase245-ab-run.sh
fh.write(json.dumps(record) + "\n")
fh.flush()  # critical for soak scripts that run overnight
```

### Pattern 3: spec.yaml Config Reading

The shadow script reads `configs/spectrum.yaml` (relative to the wanctl deployment root at `/opt/wanctl`) to extract reflectors and source IP, matching D-02.

```python
import yaml
from pathlib import Path

config_path = Path("/opt/wanctl/configs/spectrum.yaml")
with config_path.open() as fh:
    config = yaml.safe_load(fh)

reflectors = config["continuous_monitoring"]["ping_hosts"]  # ["1.1.1.1", "9.9.9.9", "208.67.222.222"]
source_ip = config["ping_source_ip"]  # "10.10.110.223"
```

### Pattern 4: SAFE-18 Boundary Script

Mirrors the Phase 245 SAFE-17 boundary check pattern. Uses `git diff` against the v1.53 close anchor (`e090a200`) to prove zero diff in protected files. Protected files per REQUIREMENTS.md SAFE-18: `wan_controller.py`, `queue_controller.py`, `cake_signal.py`, `rtt_backend.py`, `fping_measurement.py`, `rtt_measurement.py`, `alert_engine.py`, and any fusion logic module.

```bash
# Established pattern from scripts/phase245-safe17-boundary-check.sh
ANCHOR="e090a200"  # v1.53 close commit
git diff "${ANCHOR}..HEAD" -- \
    src/wanctl/wan_controller.py \
    src/wanctl/queue_controller.py \
    src/wanctl/cake_signal.py \
    src/wanctl/rtt_backend.py \
    src/wanctl/fping_measurement.py \
    src/wanctl/rtt_measurement.py \
    src/wanctl/alert_engine.py \
    | grep -c "^[-+]" || echo "0 lines changed"
```

### Anti-Patterns to Avoid

- **Calling `FpingMeasurement.probe()` directly in the main thread:** The shadow script uses `FpingThread` (background thread on 10s cadence). Direct probe calls in the main thread would block and could interfere with timing.
- **Writing to the live wanctl DB:** D-03 locks NDJSON-only output. No `storage.db_path` writes.
- **Reading spectrum.yaml from the dev machine:** The shadow script runs on cake-shaper; the config path must be `/opt/wanctl/configs/spectrum.yaml` (the deployed copy), not the dev working tree.
- **Using `max(p99_values)` across health scrapes:** This was the Phase 245 ab-run pattern (sampling health endpoint every window), but the shadow script has direct access to the live `OperationProfiler` — use `get_profile_stats()["p99_ms"]` directly.
- **Conflating probe cycle time with RTT:** `FpingThread.get_profile_stats()` returns probe execution time (fork+exec+parse, typically 1-3s for count=5 @ period_ms=200). `RttSample.rtt_ms` is the network RTT (~20-35ms for Spectrum). These are different quantities and must be logged separately.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Subprocess fping management | custom subprocess wrapper | `FpingMeasurement` + `FpingThread` | D-02 locked; the real code handles lock, timeout, parser, loss-safe tokens |
| p99 computation from raw samples | manual percentile math | `OperationProfiler.stats()` | Already computes min/max/avg/p95/p99; accessed via `FpingThread.get_profile_stats()` |
| Reflector list | hardcoded list | read from `configs/spectrum.yaml` | Config is authoritative; hardcoding diverges from production |
| SAFE-18 verification | manual file inspection | `scripts/phase247-safe18-boundary-check.sh` | Consistent with prior phase SAFE-N verifiers; machine-verifiable |

---

## Critical Discovery: What "cycle_p99_ms" Means in Phase 245 vs Phase 247

This is the most important distinction for planning. The Phase 245 AB-03 gate used **two different cycle p99 quantities**:

### Phase 245 `cycle_p99_ms` (from AB verdict)
- **Source:** Wanctl daemon health endpoint `/health` → `cycle_budget.cycle_time_ms.p99`
- **What it measures:** Total wanctl autorate control-loop cycle time (50ms target)
- **How it got there:** `OperationProfiler.stats("autorate_cycle_total")` in `health_check.py:_build_cycle_budget()`
- **Includes:** All daemon work: RTT poll, EWMA, state transition, RouterOS push, metrics flush
- **Expected range (idle, prior calibration):** avg ≈ 2.85ms, p99 ≈ 6.9ms
- **Observed in Phase 245 run:** fping p99 = 112.4ms, icmplib p99 = 120.7ms

### Phase 247 `probe_p99_ms` (from FpingThread.get_profile_stats())
- **Source:** `FpingThread.get_profile_stats()` → `OperationProfiler.stats("fping_background_cycle")`
- **What it measures:** Background fping burst execution time per probe (fork+exec+parse)
- **Expected range:** count=5 @ period_ms=200 → burst takes ~(5 × 200ms) = 1000ms minimum + grace → likely 1.0-3.0s per probe
- **NOT the 50ms control loop:** fping runs on its own 10s cadence in a background thread; its probe time does NOT appear in the 50ms cycle budget

### Implication for methodology review (PROF-02)

The Phase 245 `cycle_budget_nonregression` gate compared fping and icmplib **daemon-level** cycle p99 values, not fping probe times. Both backends showed p99 > 100ms. The calibration baseline (6.9ms p99) was from a low-load system. Under load with real traffic, the 50ms control loop itself sometimes takes longer than 10ms — this inflated both backends' p99 values past the ceiling.

The `fping_p99_ms: 112.4ms` in the Phase 245 verdict is NOT fping probe time; it is the total daemon cycle p99 during the fping-backend window. fping running a 5-ping burst @ 200ms period in a background thread does NOT cause 112ms daemon cycles — the daemon is not blocked by the background thread. The high p99 was from system load affecting the overall cycle time.

**Methodology finding (to document in 247-METHODOLOGY-REVIEW.md):** The `rollback_trigger` was driven by an absolute ceiling (10ms) calibrated at idle that neither backend can satisfy under load. It is not evidence that fping is worse than icmplib — the icmplib-backend window had a higher p99 (120.7ms). The comparative gate (`p99_delta_pct`) was not the disqualifying factor (fping was actually slightly better). The absolute ceiling was the sole failure.

---

## Phase 245 Evidence (All in Git History, No Operator Action Needed)

All Phase 245 artifacts were deleted from `.planning/phases/` during v1.53 archival but are available via `git show <commit>:<path>`.

| Artifact | Git Commit | Path |
|----------|-----------|------|
| AB verdict JSON | `7e6844a2` | `.planning/phases/245-live-a-b-rollback-anchor/245-AB-VERDICT.json` |
| AB verdict MD | `7e6844a2` | `.planning/phases/245-live-a-b-rollback-anchor/245-AB-VERDICT.md` |
| Run summary JSON | `7e6844a2` | `.planning/phases/245-live-a-b-rollback-anchor/evidence/phase245-ab-20260619T002509Z-summary.json` |
| Pre-committed thresholds | `67faf6d5` | `scripts/phase245-thresholds.json` (still present in working tree) |

**Key numbers (verified from git history):** [VERIFIED: git show 7e6844a2]

- Phase 245 run duration: **479 cycles ≈ 24 minutes** (not the full planned 30 min minimum)
- fping: `cycle_avg_ms=48.3`, `cycle_p99_ms=112.4`, `median_rtt_ms=33.22`, `loss=0.0%`
- icmplib: `cycle_avg_ms=49.3`, `cycle_p99_ms=120.7`, `median_rtt_ms=33.58`, `loss=0.0%`
- Gate result: rtt_agreement=PASS, loss_nonregression=PASS, min_backend_fraction=PASS, unexpected_restarts=PASS, steering_stability=PASS, **cycle_budget_nonregression=FAIL**
- Fail reason: `fping_p99_ms=112.4 >= CYCLE_P99_ABS_CEILING_MS=10.0`
- Pre-committed calibration: `ICMPLIB_REPRESENTATIVE_P99_MS=6.9ms` + tolerance `3.5ms` → ceiling `10.0ms`

**Pre-committed thresholds (verified from git):** [VERIFIED: `scripts/phase245-thresholds.json` in working tree]

```json
{
  "CYCLE_AVG_REGRESSION_PCT": 20.0,
  "CYCLE_P99_REGRESSION_PCT": 20.0,
  "CYCLE_P99_ABS_CEILING_MS": 10.0,
  "ICMPLIB_REPRESENTATIVE_AVG_MS": 2.85,
  "ICMPLIB_REPRESENTATIVE_P99_MS": 6.9
}
```

---

## Common Pitfalls

### Pitfall 1: Conflating fping Probe Time with Daemon Cycle Time

**What goes wrong:** Planner or reviewer assumes `fping_p99_ms=112.4` in the Phase 245 verdict means the fping probe takes 112ms. It does not — this is the wanctl daemon's 50ms-target cycle total during the fping-backend window, measured via the health endpoint.

**Why it happens:** Both "p99" values come from the same `OperationProfiler` infrastructure, but they measure different things. The Phase 245 cycle p99 is `autorate_cycle_total`; the Phase 247 probe p99 is `fping_background_cycle`.

**How to avoid:** Document both quantities separately in the NDJSON schema and in `247-METHODOLOGY-REVIEW.md`. Use distinct field names: `daemon_cycle_p99_ms` vs `probe_burst_p99_ms`.

**Warning signs:** If the probe p99 is < 3 seconds, it's plausible (count=5, period=200ms = 1s minimum). If the probe p99 is 100+ms, something is wrong with the config or binary.

### Pitfall 2: Shadow Script Running Against Dev Machine's /opt/wanctl

**What goes wrong:** Script is run from the dev machine with the wrong Python path or working directory, connecting to the local (non-existent or stale) `/opt/wanctl/`.

**Why it happens:** Phase 247 shadow script must run ON cake-shaper via SSH, not locally. The local dev machine may also have a wanctl install, but the source IP `10.10.110.223` only routes correctly from cake-shaper.

**How to avoid:** The shadow script has a `--config` argument defaulting to `/opt/wanctl/configs/spectrum.yaml`, and should check that `source_ip` is reachable via a dry-run `ip route get` before starting the soak.

**Warning signs:** `fping -S <local_dev_ip>` would silently use wrong egress WAN.

### Pitfall 3: FpingThread.stop() Not Called on Interruption

**What goes wrong:** Script is killed via SIGINT during soak; background thread is a daemon thread (exits automatically) but the output file may have a partially written record.

**Why it happens:** NDJSON append without flush at the end of a partial line.

**How to avoid:** Flush after every `json.dumps(record) + "\n"` write. Use `signal.signal(SIGINT/SIGTERM, ...)` to set the shutdown event cleanly before calling `thread.stop()`. Each NDJSON line is complete or absent.

**Warning signs:** Trailing non-JSON content in the NDJSON file; analysis script throws JSON parse error on last line.

### Pitfall 4: OperationProfiler max_samples=1200 Rollover

**What goes wrong:** At cadence_sec=10.0, a 12h soak generates 4320 probe cycles. The `FpingThread._profiler` has `max_samples=1200` (deque with maxlen). After 1200 cycles (~3.3 hours), the profiler only holds the last 1200 samples.

**Why it happens:** `OperationProfiler` uses `deque(maxlen=max_samples)` — older samples are evicted.

**How to avoid:** Log `get_profile_stats()` periodically (e.g., every 100 cycles) to the NDJSON file, not just at the end. The planner should design the script to append a `probe_stats` NDJSON record every N polls. Phase 248 will reconstruct the distribution from these snapshots.

**Warning signs:** A single call to `get_profile_stats()` at the end of a 12h soak only reflects the final 1200 samples, not the full soak window.

### Pitfall 5: Config Section Mismatch for Reflectors

**What goes wrong:** Script reads `config["ping_hosts"]` directly, but spectrum.yaml has the reflectors at `continuous_monitoring.ping_hosts`.

**Why it happens:** spectrum.yaml nesting — reflectors are under `continuous_monitoring:` not at root level.

**How to avoid:** Use `config["continuous_monitoring"]["ping_hosts"]` and `config["ping_source_ip"]` (root level). Validate list is non-empty before starting FpingThread.

---

## Code Examples

### Shadow Script Core Loop

```python
# Source: verified against src/wanctl/fping_measurement.py and src/wanctl/perf_profiler.py

import json
import logging
import signal
import sys
import threading
import time
from pathlib import Path
import yaml

# Adjust sys.path to find wanctl package at /opt/wanctl/src
src_path = Path("/opt/wanctl/src")
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from wanctl.fping_measurement import FpingMeasurement, FpingThread

CONFIG_PATH = Path("/opt/wanctl/configs/spectrum.yaml")
OUTPUT_PATH = Path("/var/lib/wanctl/phase247-fping-shadow.ndjson")
STATS_INTERVAL_PROBES = 100  # log probe stats every 100 probes (~16 min at 10s cadence)


def load_spectrum_config(config_path: Path) -> dict:
    with config_path.open() as fh:
        return yaml.safe_load(fh)


def main() -> None:
    cfg = load_spectrum_config(CONFIG_PATH)
    source_ip: str = cfg["ping_source_ip"]
    reflectors: list[str] = cfg["continuous_monitoring"]["ping_hosts"]
    fping_section: dict = (cfg.get("measurement") or {}).get("fping") or {}
    count: int = int(fping_section.get("count", 5))
    period_ms: int = int(fping_section.get("period_ms", 200))
    cadence_sec: float = float(fping_section.get("cadence_sec", 10.0))
    grace: float = float(fping_section.get("timeout_grace_sec", 2.0))

    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger("phase247-shadow")

    fping_config = {
        "source_ip": source_ip,
        "count": count,
        "period_ms": period_ms,
        "timeout_grace_sec": grace,
    }
    measurement = FpingMeasurement(fping_config, logger)
    if not measurement.is_available():
        logger.error("fping binary not found")
        sys.exit(1)

    shutdown = threading.Event()

    def _handle_signal(sig, frame):
        logger.info(f"caught signal {sig}, shutting down")
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
    thread.start()

    probe_count = 0
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_PATH.open("a") as fh:
        logger.info(f"shadow capture started; output={OUTPUT_PATH}; reflectors={reflectors}; cadence={cadence_sec}s")
        while not shutdown.is_set():
            shutdown.wait(timeout=cadence_sec)
            sample = thread.get_latest()
            if sample is not None:
                record = {
                    "type": "rtt_sample",
                    "ts": time.time(),
                    "rtt_ms": sample.rtt_ms,
                    "measurement_ms": sample.measurement_ms,
                    "per_host_results": sample.per_host_results,
                    "successful_hosts": list(sample.successful_hosts),
                    "active_hosts": list(sample.active_hosts),
                    "backend": sample.backend,
                }
                fh.write(json.dumps(record) + "\n")
                fh.flush()
                probe_count += 1

            if probe_count > 0 and probe_count % STATS_INTERVAL_PROBES == 0:
                stats = thread.get_profile_stats()
                if stats:
                    stats_record = {
                        "type": "probe_stats",
                        "ts": time.time(),
                        "probe_count_at_snapshot": probe_count,
                        **{k: v for k, v in stats.items() if k != "samples"},
                    }
                    fh.write(json.dumps(stats_record) + "\n")
                    fh.flush()

    thread.stop()
    # Final stats snapshot
    final_stats = thread.get_profile_stats()
    if final_stats:
        with OUTPUT_PATH.open("a") as fh:
            fh.write(json.dumps({"type": "probe_stats_final", "ts": time.time(), **{k: v for k, v in final_stats.items() if k != "samples"}}) + "\n")
    logger.info(f"shadow capture complete; total_probes={probe_count}")


if __name__ == "__main__":
    main()
```

### AB-03 Methodology Review Table Structure

```markdown
# 247-METHODOLOGY-REVIEW.md

## AB-03 Gate-by-Gate Methodology Analysis

| Gate | Threshold | Phase245 fping | Phase245 icmplib | Verdict | Diagnosis |
|------|-----------|---------------|-----------------|---------|-----------|
| rtt_agreement | delta < 3.0ms | 33.22ms | 33.58ms → Δ=0.36ms | PASS | RTT agreement is excellent; fping matches icmplib |
| cycle_budget_nonregression (avg) | fping_avg ≤ icmplib_avg × 1.20 | 48.3ms | 49.3ms → -2.0% | PASS | fping avg cycle was marginally better |
| cycle_budget_nonregression (p99 relative) | fping_p99 ≤ icmplib_p99 × 1.20 | 112.4ms | 120.7ms → -6.9% | PASS | fping p99 was marginally better |
| cycle_budget_nonregression (p99 absolute) | fping_p99 < 10.0ms | 112.4ms | — | FAIL | SOLE FAILING GATE; calibration baseline was idle-only |
| loss_detection_nonregression | delta < 1.0% | 0.0% | 0.0% | PASS | Both 0% loss |
| min_backend_cycle_fraction | fraction ≥ 0.95 | 1.0 | 1.0 | PASS | Both backends ran full cycle count |
| unexpected_restarts | 0 | 0 | — | PASS | No unexpected restarts |
| steering_decision_stability | delta < 5.0% | 0% enable | 0% enable | PASS | Both showed no steering enables |

## Finding

The `rollback_trigger` verdict was driven by one gate: the absolute p99 ceiling of 10ms.
This ceiling was calibrated from an idle/unloaded baseline (`ICMPLIB_REPRESENTATIVE_P99_MS=6.9ms` + 3.5ms tolerance).
Under production load, the wanctl daemon's total cycle time (autorate_cycle_total) exceeded 10ms for p99 in BOTH backend windows.

The icmplib p99 (120.7ms) was HIGHER than fping p99 (112.4ms). fping was not the cause of the failure.
The comparative regression test (fping p99 / icmplib p99 - 1 = -6.9%) was a PASS.

Root cause: **calibration mismatch** between idle-baseline threshold (10ms) and production-load p99 (100+ms for both backends).
The AB-03 gate correctly detected that the test conditions differed from calibration conditions.
It did not detect that fping is inferior to icmplib.
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Single-window A/B (one backend at a time) | Interleaved comparison windows (AB-02) | Phase 245 | Controls diurnal confounding; both backends see similar traffic patterns |
| Manual soak monitoring | Evidence NDJSON + rollup script | Phase 243 | Machine-verifiable, reproducible results |
| Health-endpoint-scrape cycle timing | Direct OperationProfiler query | Phase 247 | Shadow script has internal access to profiler; no HTTP dependency |

**Deprecated/outdated:**
- Comparing cycle p99 to an idle-baseline absolute ceiling for production A/B: Phase 245 demonstrated this causes false-negative results when load conditions differ from calibration conditions. Phase 248 will design load-aware thresholds.

---

## Runtime State Inventory

This is a code-addition phase, not a rename/migration. No runtime state inventory required.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| `fping` binary | FpingMeasurement.probe() | ✓ (dev) | 5.1 | None — required |
| `python3` with wanctl venv | Shadow script | ✓ (dev) | 3.12.3 | — |
| `configs/spectrum.yaml` | Shadow script | ✓ | live config | — |
| cake-shaper SSH access | Script deployment + soak execution | assumed | — | Operator-provided |
| `/var/lib/wanctl/` write access | NDJSON output | assumed | — | Use `--output` flag to override path |

**Note on cake-shaper:** The shadow script runs on cake-shaper, not the dev machine. fping and Python availability on cake-shaper should be verified at the start of the soak plan task. The dev machine has both confirmed. `fping` must be available at the WANCTL_RUN_DIR path (usually `/run/wanctl`).

**Missing dependencies with no fallback:** None — all dependencies are present or assumed present on cake-shaper based on prior Phase 243/245 evidence runs.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest (existing) |
| Config file | `pyproject.toml` |
| Quick run command | `.venv/bin/pytest tests/test_phase247_shadow_script.py -v` |
| Full suite command | `.venv/bin/pytest tests/test_phase247_shadow_script.py tests/test_phase247_safe18_verifier.py -v` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| PROF-01 | Shadow script instantiates FpingMeasurement correctly | unit | `.venv/bin/pytest tests/test_phase247_shadow_script.py::test_config_loading -x` | ❌ Wave 0 |
| PROF-01 | RTT sample logged as NDJSON record with correct fields | unit | `.venv/bin/pytest tests/test_phase247_shadow_script.py::test_rtt_sample_logging -x` | ❌ Wave 0 |
| PROF-01 | Probe stats logged periodically at STATS_INTERVAL_PROBES | unit | `.venv/bin/pytest tests/test_phase247_shadow_script.py::test_probe_stats_logging -x` | ❌ Wave 0 |
| PROF-01 | Shutdown on SIGINT writes final probe_stats_final record | unit | `.venv/bin/pytest tests/test_phase247_shadow_script.py::test_shutdown_final_stats -x` | ❌ Wave 0 |
| PROF-02 | Methodology review contains all 7 AB-03 gates | unit | `.venv/bin/pytest tests/test_phase247_methodology_review.py::test_gate_coverage -x` | ❌ Wave 0 |
| SAFE-18 | Zero diff in protected files vs v1.53 close anchor | shell | `bash scripts/phase247-safe18-boundary-check.sh` | ❌ Wave 0 |

### Sampling Rate

- **Per task commit:** `.venv/bin/pytest tests/test_phase247_shadow_script.py -q`
- **Per wave merge:** `.venv/bin/pytest tests/test_phase247_shadow_script.py tests/test_phase247_safe18_verifier.py -v`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps

- [ ] `tests/test_phase247_shadow_script.py` — covers PROF-01 unit tests for shadow script
- [ ] `tests/test_phase247_safe18_verifier.py` — mirrors Phase 245 SAFE-17 verifier test pattern
- [ ] `scripts/phase247-safe18-boundary-check.sh` — SAFE-18 boundary script (new file)

---

## Security Domain

This phase writes a new script to `scripts/` and produces a documentation artifact. No authentication, session management, encryption, or user input involved. The fping subprocess uses a fixed operator-configured reflector list from `configs/spectrum.yaml`. No ASVS categories apply beyond V5 input validation for the YAML config read.

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | — |
| V3 Session Management | no | — |
| V4 Access Control | no | — |
| V5 Input Validation | yes (minimal) | Validate reflector list is non-empty; validate source_ip is a string |
| V6 Cryptography | no | — |

**Known threat patterns for shadow script:**
- `fping` subprocess uses `_run_serialized()` under advisory file lock; no shell=True; reflectors are operator-configured strings, not user input. `[VERIFIED: codebase — S603 noqa is documented with rationale]`

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | fping binary is available on cake-shaper at `/usr/bin/fping` | Environment Availability | Shadow script exits early with FpingMeasurement.is_available()=False; easy to detect and fix |
| A2 | `/var/lib/wanctl/` is writable on cake-shaper without sudo | Environment Availability | Script would need `--output` path override; low risk, prior evidence scripts used this path |
| A3 | wanctl venv on cake-shaper at `/opt/wanctl/.venv` or equivalent can import FpingMeasurement | Shadow script design | If import fails, script will error immediately and not silently misbehave |
| A4 | spectrum.yaml fping section is absent (uses factory defaults: count=5, period_ms=200, cadence_sec=10.0) | Config reading pattern | Confirmed: `grep -n "fping" configs/spectrum.yaml` returned nothing; factory defaults will apply [VERIFIED: codebase] |

**If this table is empty:** N/A — 4 assumptions are listed above.

---

## Open Questions (RESOLVED)

1. **What Python path to use on cake-shaper?**
   - What we know: `/opt/wanctl/src` contains `wanctl/` package; prior scripts used `sys.path.insert(0, str(src_path))`
   - What's unclear: Whether a `pip install -e .` venv activation is preferred or explicit sys.path is acceptable for a profiling script
   - RESOLVED: Use explicit `sys.path.insert(0, str(Path(__file__).parent.parent / "src"))` at top of script, consistent with the pattern in `scripts/capture_fping_fixtures.py`. This avoids assuming a specific venv layout on cake-shaper while still importing the real wanctl package.

2. **Does the existing soak-monitor.sh need to be involved?**
   - What we know: `scripts/soak-monitor.sh` exists; Phase 247 is a standalone shadow capture, not a wanctl controller soak
   - What's unclear: Whether the planner should reference the soak-monitor for health checks alongside the shadow script
   - RESOLVED: Keep them separate. The shadow script is read-only; soak-monitor monitors the live cake-autorate/state-bridge services. The plan instructs the operator to optionally check soak-monitor output to confirm live services stay healthy during the 12h window, but the shadow script does not call or depend on soak-monitor.sh.

---

## Sources

### Primary (HIGH confidence)

- `src/wanctl/fping_measurement.py` — FpingMeasurement, FpingThread, OperationProfiler integration [VERIFIED: codebase]
- `src/wanctl/rtt_backend.py` — RttSample dataclass fields [VERIFIED: codebase]
- `src/wanctl/perf_profiler.py` — OperationProfiler.stats() return shape, max_samples=1200 [VERIFIED: codebase]
- `src/wanctl/health_check.py` — cycle_budget cycle_time_ms construction from OperationProfiler [VERIFIED: codebase]
- `scripts/phase245-thresholds.json` (in working tree) — pre-committed thresholds [VERIFIED: file present]
- git commit `7e6844a2` — Phase 245 AB verdict JSON and summary [VERIFIED: git show]
- `configs/spectrum.yaml` — source_ip, reflectors, fping section absent [VERIFIED: codebase]
- `src/wanctl/rtt_backend_factory.py` — fping cadence default=10.0s [VERIFIED: codebase]

### Secondary (MEDIUM confidence)

- `scripts/phase245-ab-run.sh` — how cycle_p99_ms was computed from health endpoint scrapes [VERIFIED: codebase]
- `scripts/phase243-bench-run.sh` — established NDJSON append pattern [VERIFIED: codebase]
- `.planning/milestones/v1.53-MILESTONE-AUDIT.md` — FPING-PROFILE-01 deferred item [VERIFIED: file present]

### Tertiary (LOW confidence)

- None.

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no new packages; all dependencies verified in codebase
- Architecture: HIGH — FpingThread/FpingMeasurement API fully read; all patterns from prior phases
- Phase 245 evidence: HIGH — retrieved directly from git history
- Methodology finding: HIGH — numbers speak for themselves; calibration mismatch is unambiguous
- Pitfalls: HIGH — all from direct code inspection

**Research date:** 2026-06-18
**Valid until:** stable (no fast-moving dependencies; all wanctl-internal)
