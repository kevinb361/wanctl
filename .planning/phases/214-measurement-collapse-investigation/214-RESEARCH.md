# Phase 214: Measurement Collapse Investigation - Research

**Researched:** 2026-05-27
**Domain:** Network measurement-quality forensics on a production CAKE controller; offline flent artifact parsing; multi-source time-aligned correlation.
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Matrix Bounds**
- **D-01:** Spectrum is the primary reproduction target. ATT is contrast evidence, not a full parallel investigation.
- **D-02:** Minimum matrix is three Spectrum `tcp_12down` windows — off-peak, daytime, prime-time. One valid attempt per window. One retry allowed only for invalid artifacts or netperf no-data failure, never to chase a preferred result.
- **D-03:** Phase 198/213 comparability defaults: `dallas` netperf host, source-bound Spectrum IP `10.10.110.226`, 30s `tcp_12down` unless Phase 213 harness reuse requires 60s for artifact consistency. Duration choice must be recorded in run manifest.
- **D-04:** Optional ATT contrast is a single `tcp_12down` run using Phase 213 ATT bind `10.10.110.233`, only if Spectrum reproduces measurement collapse or is inconclusive.

**Evidence Correlation**
- **D-05:** Each run captures flent raw artifacts plus p50/p95/p99 ping latency and throughput, 1Hz autorate `/health` NDJSON, CAKE signal/delay/rate fields, measurement state/count/stale/outlier/confidence fields, IRTT/fusion/protocol-correlation fields, steering pre/post snapshots, and journal/log evidence for reflector misses and protocol-deprioritization messages in the same time window.
- **D-06:** Reproduced bad case = high flent ping tail latency while autorate remains `healthy`/`GREEN`. Default gates: p99 `>1000ms` = fail candidate; p99 `<500ms` with no three-reflector miss burst and no protocol churn = pass candidate; in between = ambiguous, requires evidence-based classification, not automatic closure.
- **D-07:** Explanation classifies bad p99 against: reflector loss/collapse, ICMP/UDP protocol divergence, stale cached RTT reuse, steering behavior, CAKE queue signal mismatch, or external path conditions. If no single driver proven, report ranked likely causes plus missing evidence.
- **D-08:** Do not close the folded todo from `/health.status`, `GREEN`, or Phase 213's clear bucket alone. Phase must cite flent latency percentiles and aligned measurement-quality evidence from the Phase 214 matrix.

**Flent Parser Gap**
- **D-09:** Repair or add Phase 214 latency extraction before interpreting matrix results. Phase 213's classifier looked for throughput-style summary fields, emitted `flent_p99=0.0`/`flent_median=0.0`.
- **D-10:** Parse `.flent.gz` directly using Python stdlib `gzip`/`json`. Extract ping latency series + TCP download throughput series. Fail closed when expected series missing instead of emitting zero percentiles.
- **D-11:** Do not back-edit Phase 213 artifacts. Phase 214 owns its own matrix analyzer and report.

**Signal Disposition**
- **D-12:** If measurement collapse reproduces while `/health` remains GREEN, default output is observational proposal: health/degraded-measurement field, signal-sheet rule, or alert recommendation. No rate-control change in this phase.
- **D-13:** Recommend control-path work only if evidence proves an observational signal is insufficient. Even then, create a follow-up design recommendation, do not slip controller behavior changes into the investigation.
- **D-14:** v1.46 safety posture preserved: no threshold/floor/ceiling tuning, no multi-knob canary, no RouterOS writes, no steering alignment, no production service restarts.

### Claude's Discretion
- Fold only the mapped `tcp_12down` todo; discuss all four gray areas; keep Phase 214 narrow, evidence-only, and observational-first.

### Deferred Ideas (OUT OF SCOPE)
- `2026-04-17-investigate-steering-degraded-on-clean-restart.md` — current steering state clean; outside scope unless evidence newly implicates steering.
- `2026-04-17-monitor-flapping-peak-count-on-next-docsis-event.md` — deferred to Phase 218; depends on a natural event.
- `2026-04-24-resolve-att-cake-primary-canary-after-phase-196.md` — deferred to Phase 216 or later.
- `2026-04-15-profile-post-hotpath-baseline-on-production-wan.md` — deferred to Phase 217. Phase 214 may inspect `/health` cycle-budget fields incidentally, but one-hour profiling is out of scope.

</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| MEAS-01 | Pending `tcp_12down` investigation rerun with bounded matrix across time-of-day, capturing p50/p95/p99 latency, throughput, reflector misses, protocol divergence, controller state. | Phase 213 harness reused with a `--tests tcp_12down`/`--wans spectrum` narrowing; matrix executed three times (off-peak/daytime/prime-time); new flent latency extractor sources ping percentiles from `.flent.gz` raw arrays; correlation joiner aligns flent run window with /health NDJSON, alert window pulls, journal logs, steering pre/post. See `## Architecture Patterns`. |
| MEAS-02 | If health remains `GREEN` during bad p99, operator gets explicit explanation plus proposed health/degraded-signal change or documented reason not to add one. | Classification rubric in `## Architecture Patterns` decision tree assigns one of six drivers; report template (`214-REPORT.md`) carries either an observational signal proposal (a /health field name + emit rule + ADR sketch) or a "no signal needed" justification with cited evidence. |
| MEAS-03 | Any new degraded-measurement signal is observational first unless evidence proves it should affect control decisions. | `## Signal Disposition` section locks the proposal as observational-only (health field + signal-sheet rule + optional alert recommendation, NOT a controller input). Control-path work, if recommended, is a separate follow-up phase recommendation, not a Phase 214 implementation task. |

</phase_requirements>

## Summary

Phase 214 is a closure-grade forensics phase. The valid completion paths are:
1. **Reproduce** the bad-p99-while-GREEN case across the three-window matrix, identify the dominant driver (or ranked candidates), and ship an observational degraded-measurement signal proposal.
2. **Fail to reproduce** with enough variation in conditions to justify closing the folded todo with documented "not reproduced" evidence.

Two technical foundations must exist before interpretation can be trusted:

1. **A new Phase 214 flent latency extractor** — Phase 213's classifier looked for `flent-summary.json` files containing throughput-style fields (`throughput.p99`, `median_mbps`). Those files do not exist in the artifact tree; the actual data is inside `.flent.gz` under `raw_values['Ping (ms) ICMP']` (authoritative ping samples) and `results['TCP download sum']` (throughput). The new extractor must read `.flent.gz` directly using `gzip` + `json` (stdlib), compute percentiles from the raw ping array, and fail closed on missing keys.
2. **A time-aligned correlator** that joins the flent run window `[T_start, T_end]` (from manifests + `metadata.T0`) with 1Hz `/health` NDJSON, SQLite alert windows, journal logs (reflector misses, protocol deprioritization), and steering pre/post snapshots into a single per-run aligned table that makes "bad p99 while GREEN" visible at a glance.

**Primary recommendation:** Build a thin `scripts/phase214-flent-matrix.sh` wrapper around `phase213-baseline-capture.sh` (narrowed to `--wans spectrum --tests tcp_12down`), call it once per window, then run a new Phase 214 analyzer (`scripts/phase214-classify.py`) that owns the corrected flent extractor and the aligned correlator. Do not back-edit Phase 213 artifacts (D-11). The Phase 214 report carries either an observational health field proposal or a documented "no new signal needed" with cited evidence.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Source-bound traffic generation (flent tcp_12down to dallas) | Dev-VM (operator host) | — | Mirrors Phase 213/198 source-bind pattern; production daemons remain read-only. |
| 1Hz `/health` poll | Dev-VM (curl loop) | — | Already implemented in `phase213-health-poller.sh`; calls a read-only HTTP endpoint. |
| Alert window SQLite pull | Dev-VM (SSH) → cake-shaper SQLite | — | Already implemented in `phase213-alert-window.sh`; `sqlite3 -readonly` over SSH. |
| Steering pre/post snapshot | Dev-VM (SSH) → steering health endpoint | — | Already implemented in `phase213-steering-snapshot.sh`; redacted output per D-08. |
| Journal evidence (reflector misses, protocol churn) | Dev-VM (SSH) → cake-shaper journalctl | — | Read-only `journalctl -u wanctl@spectrum --since/--until`; bounded to flent window ± buffer. |
| Flent latency extraction | Dev-VM (offline Python) | — | Pure offline post-processing; no production touch. |
| Correlation/classification | Dev-VM (offline Python) | — | Pure offline analysis; produces `214-REPORT.md`, `aligned-window.json`, classification verdict. |
| Observational signal proposal (deliverable) | Documentation / ADR | health_check.py (future phase only) | D-12/D-13: design recommendation; implementation, if any, is a separate phase. |

**Tier guard:** No tier other than "Dev-VM (operator host)" runs code in this phase. cake-shaper is read-only. Router/steering is untouched. This matches v1.46 evidence-only safety posture.

## Runtime State Inventory

> Phase 214 is investigation-only. No string rename, no migration, no config edit, no service mutation. Runtime state inventory therefore covers what artifacts get written by Phase 214, not what existing state gets changed.

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | New evidence tree under `.planning/phases/214-measurement-collapse-investigation/evidence/RUN-<ts>/` per matrix window. SQLite reads from `cake-shaper:/var/lib/wanctl/metrics-spectrum.db` are read-only (`sqlite3 -readonly`); no writes. | Phase 214 owns its own evidence tree. Do not write into Phase 213's `evidence/` tree (D-11). |
| Live service config | None — read-only. No `/etc/wanctl/*.yaml` edits, no RouterOS writes, no steering toggles, no systemd restarts (D-14). | None. Explicit refuse-on-edit guard in the harness wrapper (grep-style invariant, mirror of Phase 213 SAFE-05). |
| OS-registered state | None — no systemd units added, no cron, no Task Scheduler. | None. Operator runs the matrix manually per window. |
| Secrets/env vars | Existing `~/.ssh/config` aliases (`cake-shaper`); existing `~/flent-results/phase214/` working dir; no new secrets. SSH `BatchMode=yes` + `sudo -n` patterns reused unchanged. | None. |
| Build artifacts | New scripts: `scripts/phase214-flent-matrix.sh` (orchestrator wrapper), `scripts/phase214-classify.py` (analyzer); new tests under `tests/test_phase214_*.py`. No package install, no compiled artifact. | Add to `pyproject.toml` test discovery only if not auto-picked up. |

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python stdlib `gzip` | 3.11+ | Decompress `.flent.gz` | D-10 explicitly mandates stdlib-only. No external dep. [VERIFIED: stdlib] |
| Python stdlib `json` | 3.11+ | Parse decompressed flent payload | D-10 explicitly mandates stdlib-only. [VERIFIED: stdlib] |
| Python stdlib `statistics` | 3.11+ | p50/p95/p99 of ping series | Pattern reuse from `scripts/phase198-rerun-flent-3run.sh:240-267` `extract_median()` — same shape, extend with quantile computation. [VERIFIED: source] |
| `flent` 2.1.1 (system) | 2.1.1 | Run `tcp_12down` test (12-flow TCP download) | Already used by `scripts/phase191-flent-capture.sh`; Phase 213 manifest records `flent_version=Starting Flent 2.1.1 using Python 3.12.3.` [VERIFIED: `.planning/phases/213-experience-baseline-harness/evidence/RUN-20260527T222043Z/manifest.json:9`] |
| `jq` (system) | 1.6+ | JSON manipulation in bash harness | Already used everywhere in Phase 213/198 harnesses. [VERIFIED: source] |
| `sqlite3 -readonly` (remote) | 3.x | Pull alert rows from cake-shaper | Pattern from `scripts/phase198-rerun-flent-3run.sh:335-352`; sudo -n + readonly enforced. [VERIFIED: source] |
| `curl --interface <bind>` | any | Egress verification before each run | Pattern from `scripts/phase213-baseline-capture.sh:328-334`; refuses if Spectrum egress != `70.123.224.169`. [VERIFIED: source] |
| Phase 213 leaf scripts | current HEAD | Reused as-is | `phase213-health-poller.sh` (1Hz), `phase213-alert-window.sh`, `phase213-steering-snapshot.sh`, `phase191-flent-capture.sh`. [VERIFIED: source] |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| Python `csv` (stdlib) | 3.11+ | If aligned-window output needs an operator-readable side artifact | Only for the per-cycle aligned table written as a sidecar; JSON is the primary form. |
| `pytest` (existing) | per pyproject | Wave 0 unit tests for `phase214-classify.py` extractor and aligner | Add `tests/test_phase214_flent_extract.py` and `tests/test_phase214_align.py` using stored fixture `.flent.gz` files. |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Stdlib `gzip`+`json` extractor | `flent -i <file> -f csv -o ...` shell-out | flent CLI is available, but D-10 mandates stdlib parse; CLI shell-out adds a dependency on flent's output formatter version and is opaque to unit testing. |
| Fork phase213-baseline-capture.sh into a narrower phase214 capture script | Call phase213-baseline-capture.sh with narrowed `--wans` and `--tests` flags | The phase213 orchestrator already accepts `--wans spectrum --tests tcp_12down`, so a thin shell wrapper that calls it three times (one per window) and parks artifacts under Phase 214's evidence tree is simpler. Do not duplicate the orchestrator. |
| Live cross-correlation during run | Offline correlation after all three runs collected | Live correlation adds complexity and risks burning windows on tooling bugs. Offline is comparable, debuggable, and matches Phase 198's `extract_median` pattern. |
| Synthesize `signal-sheet.md` from Phase 213 (back-edit) | New Phase 214 analyzer with own output | D-11 forbids back-editing Phase 213 artifacts. New analyzer is required. |

**Installation:** No new packages. `flent`, `jq`, `curl`, `ssh`, `sqlite3` (remote), Python 3.11+ already present per Phase 213 prereq check.

**Version verification:** Phase 213's manifest records `flent_version=2.1.1` and `wanctl_version_dev_repo=1.45.0` against `git_head_sha=aa4c33e` [VERIFIED: `evidence/RUN-20260527T222043Z/manifest.json`]. Production Spectrum runtime is 1.45.0 per Phase 212 inventory.

## Architecture Patterns

### System Architecture Diagram

```
┌────────────────────────── Operator dev-VM ──────────────────────────┐
│                                                                      │
│  ┌──────────────────────────┐    ┌────────────────────────────┐     │
│  │  Window gate (per-run)   │───>│ phase214-flent-matrix.sh   │     │
│  │  off-peak | day | prime  │    │ (thin wrapper)             │     │
│  └──────────────────────────┘    └─────┬──────────────────────┘     │
│                                        │                            │
│                                        v                            │
│        ┌──────────────────────────────────────────────────────┐     │
│        │  scripts/phase213-baseline-capture.sh                │     │
│        │  --wans spectrum --tests tcp_12down                  │     │
│        │  --bind-map spectrum=10.10.110.226                   │     │
│        │  --evidence-root .planning/phases/214-.../evidence   │     │
│        │  --flent-duration 30 (D-03) | 60 (if reuse forces)   │     │
│        └─────┬───────┬───────────┬───────────┬─────────┬──────┘     │
│              │       │           │           │         │            │
│              v       v           v           v         v            │
│        ┌─────────┐ ┌────────┐ ┌──────┐ ┌────────┐ ┌───────────┐     │
│        │ egress  │ │ health │ │flent │ │steering│ │alert SQL  │     │
│        │ probe   │ │ 1 Hz   │ │tcp_  │ │pre/post│ │window pull│     │
│        │ ipinfo  │ │ NDJSON │ │12down│ │snapshot│ │read-only  │     │
│        └─────────┘ └────────┘ └──────┘ └────────┘ └───────────┘     │
│              │       │           │           │         │            │
│              └───────┴───────┬───┴───────────┴─────────┘            │
│                              v                                      │
│              ┌──────────────────────────────────────┐               │
│              │ evidence/RUN-<window-ts>/spectrum/   │               │
│              │   tcp_12down/                        │               │
│              │     flent -> ~/flent-results/...     │               │
│              │     health-spectrum.ndjson           │               │
│              │     alerts-spectrum.json             │               │
│              │     steering-{pre,post}-state...     │               │
│              │     manifest.json                    │               │
│              └──────────────┬───────────────────────┘               │
│                             v                                       │
│        ┌──────────────────────────────────────────────────┐         │
│        │ scripts/phase214-classify.py (offline)           │         │
│        │  1. extract_flent_latency()  ← D-09/D-10         │         │
│        │  2. extract_flent_throughput()                   │         │
│        │  3. journal_pull()  (SSH read-only)              │         │
│        │  4. align_window()  (T0..Tend, 1Hz join)         │         │
│        │  5. classify_driver()  (D-06/D-07 rubric)        │         │
│        └──────────────┬───────────────────────────────────┘         │
│                       v                                             │
│        ┌──────────────────────────────────────────────────┐         │
│        │ Outputs (per-window + matrix-level):             │         │
│        │  - latency-summary.json (p50/p95/p99 + verdict)  │         │
│        │  - aligned-window.{json,csv}                     │         │
│        │  - driver-classification.json                    │         │
│        │  - 214-REPORT.md (matrix verdict + signal       │         │
│        │    disposition or "no signal needed")            │         │
│        └──────────────────────────────────────────────────┘         │
└──────────────────────────────────────────────────────────────────────┘

Read-only remote surfaces (touched but never mutated):
  - http://10.10.110.223:9101/health  (Spectrum autorate)
  - http://127.0.0.1:9102/health on cake-shaper (steering, via SSH)
  - cake-shaper:/var/lib/wanctl/metrics-spectrum.db (sqlite3 -readonly)
  - cake-shaper journalctl -u wanctl@spectrum (read-only)
```

### Recommended Project Structure

```
scripts/
├── phase214-flent-matrix.sh        # NEW: thin per-window wrapper calling phase213-baseline-capture
├── phase214-classify.py            # NEW: Phase 214-owned analyzer (extractor + aligner + rubric)
└── phase213-*.sh                   # REUSED unchanged

.planning/phases/214-measurement-collapse-investigation/
├── evidence/
│   ├── RUN-<off-peak-ts>/spectrum/tcp_12down/...
│   ├── RUN-<daytime-ts>/spectrum/tcp_12down/...
│   ├── RUN-<prime-time-ts>/spectrum/tcp_12down/...
│   ├── RUN-<att-contrast-ts>/att/tcp_12down/...  (OPTIONAL per D-04)
│   └── matrix/
│       ├── matrix-summary.json     # per-window roll-up
│       ├── aligned-windows/        # per-run aligned CSV/JSON
│       └── driver-classification.json
├── 214-RESEARCH.md
├── 214-NN-PLAN.md ...
└── 214-REPORT.md                   # final operator-facing verdict + signal disposition

tests/
├── test_phase214_flent_extract.py  # WAVE 0 — uses fixture .flent.gz
├── test_phase214_align.py          # WAVE 0 — uses fixture health.ndjson + alerts.json
└── fixtures/phase214/
    ├── sample-good-p99.flent.gz    # known-clean (e.g., 2026-04-14 17:52 run)
    ├── sample-bad-p99.flent.gz     # known-bad (e.g., 2026-04-15 02:45 run)
    └── sample-health.ndjson        # synthesized GREEN-during-bad window
```

### Pattern 1: Stdlib `.flent.gz` latency extractor (D-09/D-10)

**What:** Open the `.flent.gz` file with `gzip.open(..., "rt")`, parse JSON, read `raw_values['Ping (ms) ICMP']` for authoritative ping samples (list of `{seq, t, val}` dicts), compute p50/p95/p99 from the `val` floats. Read `results['TCP download sum']` for the throughput series. Fail closed if either key is missing.

**When to use:** Every `.flent.gz` artifact produced in Phase 214. This is the corrected replacement for `phase213-classify.py:_flent_summary()` which looks for a non-existent `flent-summary.json` and falls back to zero.

**Verified schema (from inspecting an existing `tcp_ndown` flent.gz):**

```python
# Top-level keys in .flent.gz JSON:
#   ['metadata', 'raw_values', 'results', 'version', 'x_values']
#
# metadata.NAME            -> 'tcp_ndown' (for tcp_12down test)
# metadata.LENGTH          -> 120 (configured duration, seconds)
# metadata.TOTAL_LENGTH    -> 130 (includes warmup/cooldown)
# metadata.STEP_SIZE       -> 0.2 (binned interval for results/x_values)
# metadata.T0              -> '2026-04-16T08:59:03.512987Z' (absolute UTC start)
# metadata.TIME            -> '2026-04-16T08:59:03.274492Z' (flent invocation time)
# metadata.HOST            -> 'dallas' (or whatever -H argument was)
# metadata.LOCAL_HOST      -> dev-VM hostname
# metadata.IP_VERSION      -> 4
# metadata.SERIES_META['Ping (ms) ICMP'] = {
#     'COMMAND': '/usr/bin/ping -n -D -i 0.20 -w 130 <reflector_ip>',
#     'MAX_VALUE': 953.556, 'MEAN_VALUE': 37.845, 'MIN_VALUE': 12.664,
#     'RUNNER': 'PingRunner', 'UNITS': 'ms', 'IDX': 2,
# }
#
# results['Ping (ms) ICMP']    -> list[float|None], len=650, BINNED to step_size,
#                                  contains interpolated values (DO NOT use for p99)
# raw_values['Ping (ms) ICMP'] -> list[dict], len=647, AUTHORITATIVE raw samples,
#                                  shape: {'seq': 1.0, 't': 1776329943.512987, 'val': 26.0}
# results['TCP download sum']  -> list[float|None], Mbit/s per step_size bin
# results['TCP download::1'..'::12'] -> per-flow series
# x_values                     -> list[float], relative seconds from T0 (0.0..129.8)
```

**Example:**

```python
# Source: verified against /home/kevin/projects/wanctl/tcp_ndown-2026-04-16T035903.274492.prod-tcp-ndown12-hammer-2026-04-16T0359.flent.gz
import gzip
import json
import statistics
from datetime import datetime, timezone
from pathlib import Path


class FlentExtractionError(RuntimeError):
    """Raised when expected flent series is missing or empty (D-10 fail-closed)."""


def extract_flent_latency(path: Path) -> dict:
    """Return p50/p95/p99 ping latency (ms) from raw_values, plus run window.

    Fails closed if 'raw_values' or 'Ping (ms) ICMP' is missing or empty.
    Uses raw samples, NOT the interpolated 'results' bin series.
    """
    with gzip.open(path, "rt") as fh:
        data = json.load(fh)

    raw = data.get("raw_values", {})
    series = raw.get("Ping (ms) ICMP")
    if not isinstance(series, list) or not series:
        raise FlentExtractionError(
            f"{path}: raw_values['Ping (ms) ICMP'] missing or empty"
        )

    values = [float(s["val"]) for s in series if isinstance(s, dict) and "val" in s]
    if not values:
        raise FlentExtractionError(f"{path}: ping series has no usable 'val' entries")

    values.sort()
    n = len(values)
    p50 = values[n // 2]
    p95 = values[min(n - 1, int(n * 0.95))]
    p99 = values[min(n - 1, int(n * 0.99))]

    meta = data.get("metadata", {})
    t0_iso = meta.get("T0") or meta.get("TIME")
    if not t0_iso:
        raise FlentExtractionError(f"{path}: metadata.T0/TIME missing")
    # T0 is 'YYYY-MM-DDTHH:MM:SS.ffffffZ' UTC
    t0 = datetime.fromisoformat(t0_iso.replace("Z", "+00:00"))
    length_sec = float(meta.get("TOTAL_LENGTH") or meta.get("LENGTH") or 0)

    return {
        "p50_ms": p50,
        "p95_ms": p95,
        "p99_ms": p99,
        "min_ms": min(values),
        "max_ms": max(values),
        "mean_ms": statistics.mean(values),
        "sample_count": n,
        "window_start_utc": t0.isoformat(),
        "window_end_utc": (t0.timestamp() + length_sec),  # also emit unix
        "ping_command": meta.get("SERIES_META", {})
        .get("Ping (ms) ICMP", {})
        .get("COMMAND"),
    }


def extract_flent_throughput(path: Path) -> dict:
    """Return median + sum-throughput series for tcp_12down/tcp_ndown."""
    with gzip.open(path, "rt") as fh:
        data = json.load(fh)
    results = data.get("results", {})
    for key in ("TCP download sum", "TCP totals", "TCP download avg"):
        series = results.get(key)
        if isinstance(series, list):
            vals = [v for v in series if isinstance(v, (int, float))]
            if vals:
                vals_sorted = sorted(vals)
                n = len(vals_sorted)
                return {
                    "throughput_median_mbps": statistics.median(vals_sorted),
                    "throughput_p95_mbps": vals_sorted[min(n - 1, int(n * 0.95))],
                    "throughput_max_mbps": vals_sorted[-1],
                    "sample_count": n,
                    "series_key_used": key,
                }
    raise FlentExtractionError(f"{path}: no usable TCP download series found")
```

### Pattern 2: Per-window evidence-tree call (matrix orchestration)

**What:** Each window invocation reuses `phase213-baseline-capture.sh` with a narrowed scope and a Phase 214 `--evidence-root`. Run ID is auto-generated by the orchestrator (`RUN-<UTC-ts>`), which naturally separates the three windows.

**Example wrapper (sketch — not full script):**

```bash
#!/usr/bin/env bash
# scripts/phase214-flent-matrix.sh  (per-window invocation)
set -euo pipefail

WINDOW="${1:?off-peak|daytime|prime-time}"          # operator labels the window
DURATION="${PHASE214_FLENT_DURATION:-30}"            # D-03 default; record in manifest
EVIDENCE_ROOT=".planning/phases/214-measurement-collapse-investigation/evidence"

# Refuse if not Spectrum-only (D-01/D-02). ATT contrast uses --att-contrast flag (D-04).
WANS="${PHASE214_WANS:-spectrum}"
TESTS="${PHASE214_TESTS:-tcp_12down}"

# Local hour gates for window discipline (mirror phase198-rerun-flent-3run.sh logic):
LOCAL_HOUR="$(date +%H)"
case "$WINDOW" in
  off-peak)   (( 10#$LOCAL_HOUR >= 1 && 10#$LOCAL_HOUR <= 5 ))  || die "wrong window" ;;
  daytime)    (( 10#$LOCAL_HOUR >= 10 && 10#$LOCAL_HOUR <= 16 )) || die "wrong window" ;;
  prime-time) (( 10#$LOCAL_HOUR >= 19 && 10#$LOCAL_HOUR <= 22 )) || die "wrong window" ;;
esac

bash scripts/phase213-baseline-capture.sh \
  --bind-map spectrum=10.10.110.226 \
  --wans "$WANS" \
  --tests "$TESTS" \
  --flent-duration "$DURATION" \
  --host dallas \
  --evidence-root "$EVIDENCE_ROOT"

# Phase 214 also records the window label and matrix position in a sidecar:
RUN_DIR="$(ls -1d "${EVIDENCE_ROOT}"/RUN-* | sort | tail -n 1)"
jq -n --arg window "$WINDOW" --arg duration "$DURATION" \
   '{phase: 214, window: $window, flent_duration_sec: ($duration|tonumber)}' \
   > "${RUN_DIR}/phase214-window.json"
```

### Pattern 3: Time-aligned cycle joiner (correlation)

**What:** Given the flent window `[T_start, T_end]` (unix epoch) and 1Hz health NDJSON, produce one row per second covering the window ± pre/post buffer. Each row has: timestamp, flent ping value(s) within that second from `raw_values`, /health-derived fields (state, signal_outlier_rate, measurement_state, measurement_successful_count, baseline_rtt_ms, load_rtt_ms, cake_dl_peak_delay_us, arb_active_primary_signal, etc.), and journal events that fell within that second (matched by regex on `journalctl --since=<sec-1> --until=<sec+1>`).

**Why:** The single hardest-to-see thing in this phase is "ping p99 exploded at second N+18 while `/health` row at second N+18 still says `GREEN`/`healthy`." The aligned-window CSV makes that row trivially visible.

**Example aligner sketch:**

```python
# Source: synthesis of phase213-classify._all_health_rows() + phase198 SSH SQLite pull pattern
def align_window(
    flent_path: Path,
    health_ndjson: Path,
    journal_lines: list[dict],   # pre-pulled: [{ts, unit, message}, ...]
    alerts_window: list[dict],
    flent_t0_unix: float,
    flent_end_unix: float,
    pre_buf_sec: int = 10,
    post_buf_sec: int = 10,
) -> list[dict]:
    """Return one row per second across [t_start - pre_buf, t_end + post_buf]."""
    health_rows = {int(float(r.get("sampled_utc") or r.get("t_wall_unix") or 0)): r
                   for r in _read_ndjson(health_ndjson)}
    # Pull authoritative raw pings keyed by integer second of their 't' field
    with gzip.open(flent_path, "rt") as fh:
        raw_pings = json.load(fh)["raw_values"]["Ping (ms) ICMP"]
    pings_by_sec: dict[int, list[float]] = {}
    for p in raw_pings:
        sec = int(p["t"])
        pings_by_sec.setdefault(sec, []).append(float(p["val"]))

    journal_by_sec: dict[int, list[dict]] = {}
    for j in journal_lines:
        journal_by_sec.setdefault(int(j["ts"]), []).append(j)

    rows = []
    t = int(flent_t0_unix) - pre_buf_sec
    end = int(flent_end_unix) + post_buf_sec
    while t <= end:
        h = health_rows.get(t, {})
        pings = pings_by_sec.get(t, [])
        rows.append({
            "t_unix": t,
            "in_flent_window": flent_t0_unix <= t <= flent_end_unix,
            "ping_count": len(pings),
            "ping_max_ms": max(pings) if pings else None,
            "ping_mean_ms": sum(pings) / len(pings) if pings else None,
            "health_status": h.get("status"),
            "download_state": h.get("download_state"),
            "measurement_state": h.get("measurement_state"),
            "measurement_successful_count": h.get("measurement_successful_count"),
            "measurement_stale": h.get("measurement_stale"),
            "signal_outlier_rate": h.get("signal_outlier_rate"),
            "signal_confidence": h.get("signal_confidence"),
            "baseline_rtt_ms": h.get("baseline_rtt_ms"),
            "load_rtt_ms": h.get("load_rtt_ms"),
            "load_rtt_delta_us": h.get("load_rtt_delta_us"),
            "cake_dl_peak_delay_us": h.get("cake_dl_peak_delay_us"),
            "arb_active_primary_signal": h.get("arb_active_primary_signal"),
            "arb_refractory_active": h.get("arb_refractory_active"),
            "irtt_rtt_mean_ms": h.get("irtt_rtt_mean_ms"),
            "journal_events": journal_by_sec.get(t, []),
        })
        t += 1
    return rows
```

### Pattern 4: Driver classification decision tree (D-06/D-07)

**What:** A deterministic rubric that maps aligned-window evidence to one of: `reflector_loss`, `icmp_udp_divergence`, `stale_cached_rtt`, `steering_behavior`, `cake_queue_mismatch`, `external_path`, `unexplained`. The rubric runs on the aligned rows that fall inside the flent window and produces a ranked list when more than one driver fires.

**Decision tree (apply in order, accumulate matches):**

| # | Driver | Trigger Evidence (verified field names) | Source |
|---|--------|------------------------------------------|--------|
| 1 | `reflector_loss` | Within flent window, ≥1 cycle with `measurement_successful_count == 0` OR ≥3 consecutive cycles with `measurement_successful_count <= 1`; OR journal lines matching `Ping to .* failed` from ≥3 distinct reflector IPs within a 10s rolling sub-window. | `wan_controller.py:1180-1199` zero-success blackout logging; `reflector_scorer.record_results` |
| 2 | `icmp_udp_divergence` | Journal lines matching `ICMP deprioritized\|UDP deprioritized` inside flent window; OR `/health.irtt_rtt_mean_ms` is null/jumps while `load_rtt_ms` stays stable (fusion-healer signal). | `fusion_healer.py:tick()` Pearson correlation gating; folded todo notes 2026-04-15 02:45 evidence |
| 3 | `stale_cached_rtt` | `/health.measurement_stale == true` for ≥3 cycles in window; OR `measurement_staleness_sec > 0.5` while `load_rtt_ms` value did not change between two cycles (cached snapshot reused). | `wan_controller.py:1170-1217` cached RTT reuse during blackout |
| 4 | `steering_behavior` | Steering pre→post snapshot diff shows `good_count_delta > 0` AND `red_count_delta > 0` AND `cake_read_failures_delta > 0`; OR steering `history_fallback` counter advanced during window. | `phase213-classify._counter()` already computes these deltas — reuse pattern, do NOT back-edit the script (D-11) |
| 5 | `cake_queue_mismatch` | `cake_dl_peak_delay_us` rises above `50000` µs in window while `download_state` stays GREEN (CAKE saw queue depth but controller did not react). | `health_check.py:_build_cake_signal_section` (verify exact field name in v1.45 build); Phase 213 BUCKET_2 threshold reuse |
| 6 | `external_path` | None of 1–5 fire; throughput stays at plan; `signal_outlier_rate` stayed low. Catch-all "path got dirty upstream." | Default. |

**Ranking:** If multiple drivers fire, rank by `evidence_strength_score` = number of cycles in window matching the trigger (1+ for journal events, 1 per cycle for /health-based triggers). Report all firing drivers; primary = highest score; report missing evidence for any driver that would have been definitive but data was incomplete.

**Pass/fail gate application (D-06):**

| Condition | Verdict |
|-----------|---------|
| All three windows: ping `p99 < 500ms` AND no driver 1 fires AND no driver 2 fires | `pass` (not reproduced; close folded todo with documented "not reproduced") |
| Any window: ping `p99 > 1000ms` AND ≥1 driver fires | `fail` (reproduced; emit observational signal proposal) |
| Any window: 500ms ≤ p99 ≤ 1000ms OR p99 > 1000ms with no driver firing | `ambiguous` (do NOT auto-close; carry the todo forward with narrower next steps per Success Criterion 4) |

### Pattern 5: Observational signal proposal (D-12/D-13)

**What:** If the matrix reproduces bad p99, the deliverable is a documented proposal — not an implementation — for an operator-facing "measurement quality collapsed while GREEN" signal. Three concrete forms:

| Form | Where it lives | Example | Scope guard |
|------|----------------|---------|-------------|
| **Form A: new /health field** | `health_check.py:_build_measurement_section()` (recommended, future phase) | `"degraded_quality": {"active": true, "reason": "zero_success_in_window", "cycles_in_window": 8, "since_unix": 1779920851}` | Read-only; daemon emits it, control loop ignores it. Adding the field is itself a follow-up phase, not Phase 214. |
| **Form B: signal-sheet rule** | `phase214-classify.py` rubric only (no daemon change) | New offline classifier rule "measurement_quality_collapse" mirroring Phase 213 bucket pattern. | Lives entirely in Phase 214 analyzer; no production code touched. |
| **Form C: alert recommendation** | Phase 214 report only; no alerts table write | Recommend `alert_type='measurement_degraded'` with criteria + suggested cooldown, deferred to a future phase to wire. | Documentation only. |

**Default (D-12):** Form B + Form C as a documented design recommendation in `214-REPORT.md`. Form A is described as "future-phase implementation candidate" with field name, payload shape, and emit-rule sketch — but not implemented in Phase 214.

**Anti-pattern (forbidden by D-13/D-14):** Wiring any of these into a control input, threshold, refractory trigger, or rate-clamping decision. If evidence proves an observational signal is insufficient, recommend a separate follow-up design phase. Do not slip controller behavior changes into the investigation.

### Anti-Patterns to Avoid

- **Back-editing `phase213-classify.py` or its evidence tree:** Forbidden by D-11. The classifier's `_flent_summary()` zero-fill bug must NOT be patched in-place; the Phase 214 analyzer is a separate file.
- **Reading ping percentiles from `results['Ping (ms) ICMP']`:** That series is binned and interpolated to step_size; it contains synthesized values between real samples. Use `raw_values['Ping (ms) ICMP']` exclusively. [VERIFIED: schema inspection]
- **Treating `/health.status=healthy` or `GREEN` as proof of acceptable p99:** Project CLAUDE.md spine: "`/health.status=healthy` and `GREEN` are daemon-state only. They are not sufficient proof of acceptable user experience." Also the explicit reason this phase exists.
- **Skipping the source-bind egress probe:** Without verifying `curl --interface 10.10.110.226 https://ifconfig.io == 70.123.224.169`, you risk running flent over ATT and silently producing meaningless evidence. Phase 198/213 both refuse on mismatch.
- **Retrying a window to chase a desired result (D-02):** Retry is permitted only for invalid artifacts or netperf no-data failure. Retrying because "the p99 looked too clean" invalidates the matrix.
- **Live correlation during the run:** The bash poll loop is bounded and proven. Move correlation entirely offline; do not add complexity that could burn a window if it breaks.
- **Using flent CLI summary as the latency source:** The CLI's `-f summary` format is version-coupled and harder to unit-test than the raw `.flent.gz` JSON.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Per-WAN traffic generation + evidence tree | New capture script from scratch | `phase213-baseline-capture.sh` with narrowed `--wans`/`--tests` | Already handles bind-map, egress refuse-on-mismatch, serialized WAN suites, poller PID cleanup via trap, normalized flent symlinking, manifest emission. |
| 1Hz `/health` NDJSON polling | New curl loop | `scripts/phase213-health-poller.sh` (1Hz, bounded failure-rate gate, SOAK_FAIL_RATE_THRESHOLD) | Already invoked by phase213-baseline-capture for every test. |
| Read-only SQLite pull from cake-shaper | Direct sqlite open | `phase213-alert-window.sh` + `phase198-rerun-flent-3run.sh:335-352` SSH `sudo -n sqlite3 -readonly` pattern | Proven, batch-mode SSH, redacted output. |
| Steering pre/post snapshot with D-08 redaction | New jq filter | `phase213-steering-snapshot.sh` | Already redacts `password\|secret\|token\|credential\|auth\|key\|private`. |
| Source-bind egress proof | New ipinfo check | `phase213-baseline-capture.sh:328-334` and `phase198-rerun-flent-3run.sh:270-289` | Already refuses on egress mismatch; mandatory before each flent invocation. |
| `.flent.gz` extraction shape | Custom percentile or shell-out to `flent -f summary` | Stdlib `gzip`+`json` + `statistics` (Pattern 1) | D-10 mandate; pattern already proven in `phase198-rerun-flent-3run.sh:240-267`. |
| Windowed journal pull | Shell awk scan of full log | `ssh cake-shaper "sudo -n journalctl -u wanctl@spectrum --since '<start>' --until '<end>' --output=json --no-pager"` | Bounded by time window; structured JSON output keys map directly to align_window seconds. |
| Time alignment of disparate streams | Pandas/DataFrame dependency | Stdlib dict-keyed-by-int-second (Pattern 3) | Stdlib-only invariant; ~50 lines; trivially unit-testable. |

**Key insight:** This phase is mostly *reusing* Phase 213 leaf scripts in a different shape. The two genuinely new pieces are (a) the correct flent extractor and (b) the offline correlation/classification analyzer. Everything else is composition.

## Common Pitfalls

### Pitfall 1: Ping percentile computed from binned `results` series
**What goes wrong:** `data['results']['Ping (ms) ICMP']` is a fixed-cadence interpolated list. Its p99 will be smoothed and substantially understated vs raw samples.
**Why it happens:** It's the obvious-looking field, same length as `x_values`, easy to compute on. The naming is misleading — these are not raw measurements.
**How to avoid:** Use `data['raw_values']['Ping (ms) ICMP']` and extract `s['val']` from each dict. [VERIFIED: schema inspection of `tcp_ndown-2026-04-16T035903.flent.gz` — raw len=647 with `{seq, t, val}` shape; results len=650 includes synthesized step-size bins.]
**Warning signs:** Computed p99 closely matches `metadata.SERIES_META['Ping (ms) ICMP'].MEAN_VALUE * ~3`; or computed p99 differs from `MAX_VALUE` by orders of magnitude.

### Pitfall 2: Zero-fill on missing flent summary file (Phase 213 bug)
**What goes wrong:** Phase 213's `_flent_summary()` looks for `flent-summary.json` files that the harness never creates, so it always returns `{}`, then the caller falls back to `0.0` for `flent_p99`/`flent_median`. The bucket then never fires because `flent_p99 > flent_median * 5` becomes `0 > 0`.
**Why it happens:** The classifier assumed there'd be a structured summary file; flent only emits the `.flent.gz` raw artifact and a non-JSON `summary` text format unless explicitly run with `-f json`.
**How to avoid:** Fail closed in Pattern 1 (`FlentExtractionError`) — never silently return zero. Add a unit test that asserts the extractor raises on a missing-series fixture.
**Warning signs:** Aggregated p99 across runs is suspiciously uniform; verdicts always come back "clear."

### Pitfall 3: Source-bind drift mid-run
**What goes wrong:** The Spectrum bind IP `10.10.110.226` is on the dev VM; if it's removed or rebound between window invocations, flent silently exits via ATT/default route and the entire run measures the wrong WAN.
**Why it happens:** Bind IPs are NetworkManager / netplan / manual aliases; nothing in Phase 213/214 prevents external changes.
**How to avoid:** Egress probe before each flent invocation (Pattern: phase213-baseline-capture.sh:328-334). Refuse if `curl --interface 10.10.110.226 https://ifconfig.io` != `70.123.224.169`. This is already the phase213 behavior — keep it.
**Warning signs:** Flent results that look like ATT throughput (much higher floor); manifest's `bind_map_egress_observed.spectrum` not matching the expected Spectrum public IP.

### Pitfall 4: Journal time skew vs flent T0
**What goes wrong:** Dev VM clock and cake-shaper clock may differ by 100-500ms. Aligning journal events to per-second buckets can place an event in the wrong second.
**Why it happens:** No NTP-strict synchronization required between hosts.
**How to avoid:** Use a ±1 second tolerance when matching journal events to aligned-window rows; record clock skew in the run manifest (compare dev VM `date +%s.%N` vs `ssh cake-shaper date +%s.%N` immediately before run). If skew > 1s, refuse the run.
**Warning signs:** Driver classifier shows "reflector loss" events that fall outside the flent window by ≥1s.

### Pitfall 5: Off-peak time-of-day gate burned for nothing
**What goes wrong:** The off-peak window (Spectrum DOCSIS-quiet hours, typically 02:00-05:00 local) is operationally precious. Tooling bugs that fail mid-run waste the only off-peak slot for the day.
**Why it happens:** First-time analyzer code paths are usually tested on fixtures, not live runs.
**How to avoid:** Wave 0 unit tests for `phase214-classify.py` using stored fixture `.flent.gz` files (the historical `tcp_12down-2026-04-15T024543` artifact mentioned in the folded todo and the current `tcp_ndown-2026-04-16T035903` artifact already in the repo). Dry-run the matrix wrapper with a synthesized RUN dir before live invocation.
**Warning signs:** Wave 0 fixture tests are skipped or marked TODO.

### Pitfall 6: Treating ICMP-only `Ping (ms) ICMP` as the universe of measurement quality
**What goes wrong:** Bad p99 might be ICMP-only; UDP/TCP-derived measurement might still be fine. Without IRTT cross-reference, "measurement collapse" verdict is incomplete.
**Why it happens:** flent's tcp_12down test uses ICMP for the latency series. The wanctl autorate daemon, by contrast, can fuse ICMP with IRTT (via fusion_healer). A run can show bad ICMP p99 while the daemon's fused signal is healthy — that's actually evidence that fusion is doing its job, not a collapse.
**How to avoid:** In the aligned-window row, include `irtt_rtt_mean_ms`, `irtt_loss_up_pct`, `irtt_loss_down_pct`, `irtt_asymmetry_ratio` fields from `/health`. The classifier rubric (Pattern 4 driver 2) already cross-checks for ICMP/UDP divergence; emphasize this in the report.
**Warning signs:** Verdict cites "bad ICMP p99" without mentioning IRTT state.

## Code Examples

### Common Operation 1: Compute aligned-window driver verdict
```python
# Source: synthesis of patterns above; runs offline post-capture
def classify(aligned_rows: list[dict]) -> dict:
    in_window = [r for r in aligned_rows if r["in_flent_window"]]
    drivers: dict[str, dict] = {}

    # Driver 1: reflector_loss
    zero_success = [r for r in in_window if (r.get("measurement_successful_count") or 0) == 0]
    if zero_success:
        drivers["reflector_loss"] = {
            "fired": True,
            "evidence": f"{len(zero_success)} cycles with measurement_successful_count==0",
            "score": len(zero_success),
            "first_unix": zero_success[0]["t_unix"],
        }

    # Driver 2: icmp_udp_divergence (journal-based)
    proto_events = [
        e for r in in_window for e in r.get("journal_events", [])
        if "deprioritized" in (e.get("message") or "").lower()
    ]
    if proto_events:
        drivers["icmp_udp_divergence"] = {
            "fired": True,
            "evidence": f"{len(proto_events)} protocol deprioritization events",
            "score": len(proto_events),
        }

    # Driver 3: stale_cached_rtt
    stale = [r for r in in_window if r.get("measurement_stale") is True]
    if len(stale) >= 3:
        drivers["stale_cached_rtt"] = {
            "fired": True,
            "evidence": f"{len(stale)} cycles with measurement_stale=true",
            "score": len(stale),
        }

    # (drivers 4-6 analogous — omitted for brevity)

    if not drivers:
        return {"primary": "external_path_or_unexplained", "ranked": [], "drivers": {}}
    ranked = sorted(drivers.items(), key=lambda kv: kv[1]["score"], reverse=True)
    return {"primary": ranked[0][0], "ranked": [k for k, _ in ranked], "drivers": drivers}
```

### Common Operation 2: Window gate (per-window run discipline)
```bash
# Source: simplified from scripts/phase198-rerun-flent-3run.sh:140-156
LOCAL_HOUR="$(date +%H)"
case "$WINDOW" in
  off-peak)
    if (( 10#$LOCAL_HOUR < 1 || 10#$LOCAL_HOUR > 5 )); then
      echo "REFUSED: hour $LOCAL_HOUR outside off-peak window 01..05 local" >&2
      exit 2
    fi ;;
  daytime)
    if (( 10#$LOCAL_HOUR < 10 || 10#$LOCAL_HOUR > 16 )); then
      echo "REFUSED: hour $LOCAL_HOUR outside daytime window 10..16 local" >&2
      exit 2
    fi ;;
  prime-time)
    if (( 10#$LOCAL_HOUR < 19 || 10#$LOCAL_HOUR > 22 )); then
      echo "REFUSED: hour $LOCAL_HOUR outside prime-time window 19..22 local" >&2
      exit 2
    fi ;;
esac
```

### Common Operation 3: Journal pull bounded to flent window
```bash
# Source: standard journalctl pattern; bind to UTC for unambiguous matching
START="$(date -u -d "@$((T_START - PRE_BUF))" '+%Y-%m-%d %H:%M:%S')"
END="$(date -u -d "@$((T_END + POST_BUF))" '+%Y-%m-%d %H:%M:%S')"
ssh -o BatchMode=yes cake-shaper "sudo -n journalctl \
    -u wanctl@spectrum -u steering \
    --since '${START} UTC' --until '${END} UTC' \
    --output=json --no-pager" > "${TEST_DIR}/journal-window.ndjson"
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Phase 213 `_flent_summary()` looks for `flent-summary.json` summary files | Phase 214 reads `.flent.gz` directly via stdlib gzip+json | 2026-05-27 (this phase) | Replaces silent zero-fill with fail-closed extraction; valid p99 source of truth. |
| Phase 213 binary bucket-flagged classifier | Phase 214 ranked-driver classification with explicit "unexplained" path | 2026-05-27 (this phase) | Supports D-07 ranked-cause output and D-06 ambiguous-zone discipline. |
| Manual reproduction with operator running flent + observing /health | Single-command per-window orchestrator + offline analyzer | 2026-05-27 (this phase) | Reduces operator burden, makes runs comparable, preserves Phase 213 evidence-tree shape. |

**Deprecated/outdated:** Nothing is being deprecated. Phase 213 artifacts and scripts remain unchanged (D-11). Phase 214 is additive.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (per `pyproject.toml`) |
| Config file | `pyproject.toml` (existing) |
| Quick run command | `.venv/bin/pytest tests/test_phase214_flent_extract.py tests/test_phase214_align.py -x -q` |
| Full suite command | `.venv/bin/pytest tests/ -q` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| MEAS-01 | Matrix wrapper accepts `--window <off-peak\|daytime\|prime-time>` and refuses out-of-window hours | unit (bash dry-run) | `bash scripts/phase214-flent-matrix.sh --dry-run --test-hour 14 daytime` (mirror phase198 `--test-hour` pattern) | Wave 0 |
| MEAS-01 | `extract_flent_latency` returns p50/p95/p99 from a known-good fixture | unit | `.venv/bin/pytest tests/test_phase214_flent_extract.py::test_extract_known_good -x` | Wave 0 |
| MEAS-01 | `extract_flent_latency` raises `FlentExtractionError` on missing raw_values key | unit | `.venv/bin/pytest tests/test_phase214_flent_extract.py::test_extract_missing_raw_fails_closed -x` | Wave 0 |
| MEAS-01 | `extract_flent_throughput` returns median/p95 from `TCP download sum` series | unit | `.venv/bin/pytest tests/test_phase214_flent_extract.py::test_extract_throughput -x` | Wave 0 |
| MEAS-01 | `align_window` produces one row per second across window ± buffer with correct in_flent_window flag | unit | `.venv/bin/pytest tests/test_phase214_align.py::test_align_basic -x` | Wave 0 |
| MEAS-01 | Aligned rows correctly bucket raw_values pings into per-second `ping_max_ms`/`ping_mean_ms` | unit | `.venv/bin/pytest tests/test_phase214_align.py::test_align_ping_bucketing -x` | Wave 0 |
| MEAS-02 | `classify()` correctly identifies `reflector_loss` from a fixture with `measurement_successful_count==0` cycles | unit | `.venv/bin/pytest tests/test_phase214_classify.py::test_classify_reflector_loss -x` | Wave 0 |
| MEAS-02 | `classify()` correctly identifies `icmp_udp_divergence` from journal fixture | unit | `.venv/bin/pytest tests/test_phase214_classify.py::test_classify_protocol_divergence -x` | Wave 0 |
| MEAS-02 | `classify()` returns ranked-list when multiple drivers fire | unit | `.venv/bin/pytest tests/test_phase214_classify.py::test_classify_multi_driver_ranking -x` | Wave 0 |
| MEAS-02 | Pass/fail/ambiguous verdict gate emits `ambiguous` for 500-1000ms p99 | unit | `.venv/bin/pytest tests/test_phase214_classify.py::test_verdict_ambiguous_zone -x` | Wave 0 |
| MEAS-03 | Report template includes signal-disposition section (Form B + Form C documented; no controller field added) | structural (grep) | `grep -q 'Signal Disposition\|observational' .planning/phases/214-measurement-collapse-investigation/214-REPORT.md` | Manual (Wave N) |
| MEAS-03 | No production code under `src/wanctl/` was modified in this phase | structural (git) | `git diff --name-only <phase-base-sha>..HEAD -- src/wanctl/ \| wc -l` returns 0 | Manual (verification gate) |
| (live) | Live matrix run end-to-end across three windows produces three RUN dirs + matrix-summary.json | manual | Operator runs `scripts/phase214-flent-matrix.sh <window>` three times across calendar | Manual-only (live capture, cannot be unit tested) |

### Sampling Rate
- **Per task commit:** `.venv/bin/pytest tests/test_phase214_flent_extract.py tests/test_phase214_align.py tests/test_phase214_classify.py -x -q`
- **Per wave merge:** `.venv/bin/pytest tests/ -q`
- **Phase gate:** Full suite green AND structural checks pass before `/gsd-verify-work`. Live matrix capture is a separate operator step recorded in 214-REPORT.md.

### Wave 0 Gaps
- [ ] `tests/test_phase214_flent_extract.py` — covers MEAS-01 extractor with known-good and missing-series fixtures
- [ ] `tests/test_phase214_align.py` — covers MEAS-01 aligner with synthesized health NDJSON
- [ ] `tests/test_phase214_classify.py` — covers MEAS-02 driver classification and verdict gate
- [ ] `tests/fixtures/phase214/sample-tcp_12down.flent.gz` — copy from `tcp_ndown-2026-04-16T035903.274492.prod-tcp-ndown12-hammer-2026-04-16T0359.flent.gz` (already in repo root); verified to contain real raw_values
- [ ] `tests/fixtures/phase214/sample-bad-p99-health.ndjson` — synthesize a 30-second NDJSON with download_state=GREEN, measurement_successful_count cycling 0/0/0/2 to simulate collapse
- [ ] `tests/fixtures/phase214/sample-journal-window.ndjson` — synthesize journal events with `ICMP deprioritized` and `Ping to .* failed` lines
- [ ] Framework install: none needed (pytest already present per `.venv/bin/pytest` invocations in CLAUDE.md and `pyproject.toml`)
- [ ] Bash dry-run hook for `phase214-flent-matrix.sh --dry-run --test-hour <H> <window>` (mirror phase198 pattern)

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| flent | tcp_12down traffic generation | ✓ (assumed; phase213 prereq) | 2.1.1 | — (required) |
| Python 3.11+ | extractor + analyzer | ✓ (.venv) | 3.11+ | — (required) |
| jq | bash harness | ✓ (phase213 prereq) | 1.6+ | — (required) |
| curl | egress probe + health poll | ✓ (phase213 prereq) | 7.x | — (required) |
| ssh `cake-shaper` BatchMode | journal + sqlite pull + steering snapshot | ✓ (phase213 prereq) | OpenSSH | — (required) |
| `sudo -n` on cake-shaper for journalctl / sqlite3 | read-only remote pulls | ✓ (phase213 prereq) | — | — (required) |
| Source bind IP `10.10.110.226` on dev VM | source-bound Spectrum flent | ✓ (phase213/198 verified) | — | Refuse-on-mismatch; no fallback (D-03) |
| `/var/lib/wanctl/metrics-spectrum.db` on cake-shaper | alert window pull | ✓ (Phase 212 inventory) | sqlite3 | — (required) |
| Off-peak network window 02:00-05:00 local | one run per matrix; first window | ✓ (operator-gated) | — | Allow `--allow-extended-window` per phase198 pattern; or `--force-window <reason>` |
| Daytime + prime-time windows | windows 2 and 3 | ✓ (operator-gated) | — | — |

**Missing dependencies with no fallback:** none.
**Missing dependencies with fallback:** none — all are required.

## Project Constraints (from CLAUDE.md)

The active project CLAUDE.md (wanctl) imposes the following directives the planner MUST honor:

| Directive | Source | How Phase 214 honors it |
|-----------|--------|--------------------------|
| Change conservatively; production network control system | `CLAUDE.md` "What It Does" | Phase 214 is read-only forensics; no `src/wanctl/` edits (verified by the MEAS-03 grep test). |
| Stability > safety > clarity > elegance | `CLAUDE.md` "Change Policy" | Analyzer fails closed rather than producing zero-fill; harness refuses on egress mismatch and window violation. |
| Never refactor core logic, algorithms, thresholds, or timing without approval | `CLAUDE.md` "Change Policy" | D-14 carries this verbatim. Phase 214 produces no controller changes. |
| Portable controller: deployment-specific behavior in YAML config, not Python branching | `CLAUDE.md` "Portable Controller Architecture" | Phase 214 touches no controller code; Spectrum/ATT difference is in run parameters, not Python. |
| Use the virtualenv directly | `CLAUDE.md` "Development Commands" | Test commands use `.venv/bin/pytest` (mirrored in Validation Architecture). |
| Production investigation phases create stable `.planning/phases/<phase>/evidence/` artifacts with manifests, redacted snapshots, command provenance, mutation-boundary notes | Phase 213 context "Established Patterns" | Phase 214 follows the same evidence-tree shape: `evidence/RUN-<ts>/spectrum/tcp_12down/<artifacts>` with manifest.json, redacted steering, command provenance. |
| `/health.status=healthy` and `GREEN` are daemon-state only | Phase 213 context "Established Patterns" | Phase 214's entire reason to exist. |
| Production mutation requires operator approval | Phase 213 context | Phase 214 is traffic generation + read-only capture only (D-14). |
| Always run `project-finalizer` before commits | Global CLAUDE.md | Plans should include `make ci` or equivalent + project-finalizer invocation in their final task. |
| RAG-first discovery | Global CLAUDE.md | Research used direct file reads + folded todo (canonical problem statement); RAG could supplement but is not load-bearing for Phase 214. |

## Sources

### Primary (HIGH confidence)
- `tcp_ndown-2026-04-16T035903.274492.prod-tcp-ndown12-hammer-2026-04-16T0359.flent.gz` — **directly inspected** via Python; top keys `[metadata, raw_values, results, version, x_values]`; raw_values['Ping (ms) ICMP'] has 647 `{seq, t, val}` entries; results['TCP download sum'] has 650 Mbit/s float values with leading None warmup samples; metadata.T0 is ISO8601 UTC.
- `rrul-2026-04-15T091821.493475.prod-rrul-12tcp-120s-2026-04-15.flent.gz` — **directly inspected**; confirms RRUL adds `Ping (ms) UDP BE/BK/EF`, `Ping (ms) avg`, multi-class TCP series. Phase 214 only uses tcp_12down but extractor must tolerate other test types in fixtures.
- `/home/kevin/projects/wanctl/scripts/phase213-classify.py:173-191` — `_flent_summary()` source of the Phase 213 zero-fill bug.
- `/home/kevin/projects/wanctl/scripts/phase213-baseline-capture.sh:269-345` — proves the orchestrator already accepts narrowed `--wans`/`--tests` and produces a Phase-214-shaped evidence tree.
- `/home/kevin/projects/wanctl/scripts/phase198-rerun-flent-3run.sh:240-267` — proven `extract_median` stdlib gzip+json pattern; Phase 214 extends with quantile computation.
- `/home/kevin/projects/wanctl/scripts/phase198-rerun-flent-3run.sh:335-352` — proven SSH `sudo -n sqlite3 -readonly` pattern for cake-shaper.
- `/home/kevin/projects/wanctl/src/wanctl/wan_controller.py:1137-1235` — measure_rtt cached-RTT-reuse logic; source of the "zero-success blackout while controller state stays bounded" behavior central to D-07 driver 3 (stale_cached_rtt).
- `/home/kevin/projects/wanctl/src/wanctl/health_check.py:454-526` — `_build_measurement_section` field shape; defines the field names the aligner must read (`measurement.staleness_sec`, `measurement.successful_reflector_hosts`, etc.).
- `/home/kevin/projects/wanctl/.planning/phases/213-experience-baseline-harness/evidence/RUN-20260527T222043Z/spectrum/tcp_12down/health-spectrum.ndjson` — verified concrete `/health` row keys: `status`, `download_state`, `measurement_state`, `measurement_successful_count`, `measurement_stale`, `measurement_staleness_sec`, `signal_outlier_rate`, `signal_confidence`, `baseline_rtt_ms`, `load_rtt_ms`, `load_rtt_delta_us`, `cake_dl_peak_delay_us`, `arb_active_primary_signal`, `arb_refractory_active`, `irtt_rtt_mean_ms`, `irtt_loss_up_pct`, `irtt_loss_down_pct`, `irtt_asymmetry_ratio`.
- `/home/kevin/projects/wanctl/.planning/todos/pending/2026-04-08-investigate-tcp-12down-latency-spikes-under-multi-flow-downl.md` — folded problem statement, historical p99 evidence, pass/fail gates inherited by D-06.
- `/home/kevin/projects/wanctl/.planning/phases/214-measurement-collapse-investigation/214-CONTEXT.md` — locked decisions D-01..D-14.
- `/home/kevin/projects/wanctl/.planning/phases/213-experience-baseline-harness/evidence/RUN-20260527T222043Z/manifest.json` — flent_version 2.1.1, wanctl_version 1.45.0, bind_map confirmed, serialized WAN order.
- `/home/kevin/projects/wanctl/.planning/REQUIREMENTS.md:34-36` — MEAS-01/02/03 verbatim.

### Secondary (MEDIUM confidence)
- flent's `.flent.gz` schema treated as stable across runs based on inspecting 2 distinct test types (tcp_ndown, rrul) producing the same top-level shape. Confidence MEDIUM (rather than HIGH) because the extractor relies on stable key names from upstream flent; pinning to `flent 2.1.1` matches the Phase 213 manifest.
- Driver classification thresholds (Pattern 4) inherit some values from Phase 213's `BUCKET_*` constants (e.g., `BUCKET_2_PEAK_DELAY_US = 50000`). Phase 214 must validate against the matrix evidence and adjust the rubric (still observational) if a threshold misfires.

### Tertiary (LOW confidence) / ASSUMED
- The "fusion-healer suspension event" referenced in the folded todo as a leading suspect — the exact `/health` field name for fusion suspension state was not verified in this research session. The aligner pulls `irtt_*` fields confirmed by Phase 213 NDJSON; if a more specific fusion field exists (e.g., `fusion.state`), it should be added to the aligner before the matrix runs. `[ASSUMED]`
- Production journal log message regexes (`Ping to .* failed`, `ICMP deprioritized`, `UDP deprioritized`) are quoted from the folded todo's 2026-04-15 evidence. Exact log strings should be sanity-checked against `wan_controller.py`/`reflector_scorer.py`/`fusion_healer.py` log statements during Wave 0; if the messages have evolved between v1.39 and v1.45.0, update the regex. `[ASSUMED]`
- Daytime/prime-time hour windows (10..16 / 19..22 local) chosen as reasonable defaults; the planner may narrow them based on operator availability and Spectrum's typical DOCSIS congestion profile. `[ASSUMED]`

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | A `/health` field named "fusion suspension state" exists or is reachable via `irtt_*` fields | Pattern 3, Pattern 4 driver 2 | Driver 2 (icmp_udp_divergence) falls back to journal-only evidence; aligner would miss a richer fusion signal. Mitigation: verify before Wave 0 by grepping `src/wanctl/health_check.py` for fusion-related fields. |
| A2 | Production journal regex strings still match v1.45.0 builds | Pattern 4 driver 1+2, Code Example 3 | Driver detection misses real events; matrix produces "no driver fired" verdict despite evidence. Mitigation: Wave 0 task to grep current log messages and update regexes. |
| A3 | Daytime/prime-time hour bands (10..16, 19..22) are operationally sensible | Pattern 2, Code Example 2 | Operator may want different windows; bands are easy to override via env var. Low risk. |
| A4 | flent's `.flent.gz` JSON keys (`raw_values`, `results`, `metadata.T0`, etc.) remain stable for flent 2.1.1 across `tcp_12down`/`tcp_ndown` test names | Pattern 1, Sources | If a future flent build renames keys, the extractor's fail-closed behavior surfaces the change immediately. Pin extractor to flent 2.1.1 in manifest. |
| A5 | One off-peak window per day is operationally achievable across three calendar days OR three windows on the same day | Pattern 2 | Matrix duration extends if operator cannot get all three windows in one day; not a correctness risk. |

**User confirmation suggested for:** A1, A2 — these should be verified during Wave 0 by reading `health_check.py` and grepping recent journal output before the live matrix runs. The remaining assumptions are operational defaults the planner can adjust without invalidating the research.

## Open Questions (RESOLVED)

1. **Does `health_check.py` v1.45.0 emit a fusion-suspension boolean or string field?**
   - What we know: `/health` rows contain `irtt_*` fields; fusion-healer transitions to alert.
   - **RESOLVED (2026-05-27 source read):** The structured `/health` payload DOES carry fusion state at `wan_health.fusion.heal_state` with values `{active, suspended, recovering, no_healer}` (verified at `src/wanctl/health_check.py:617-722` `_build_fusion_section`, and `src/wanctl/fusion_healer.py:43-44,231` `HealState` enum). It also exposes `fusion.heal_grace_active`, `fusion.pearson_correlation`, `fusion.correlation_window_avg`, and `fusion.bypass_active`/`bypass_reason`/`bypass_count`. **HOWEVER**, the flat NDJSON emitted by `scripts/phase213-health-poller.sh:166-221` does NOT project any `fusion.*` field — the jq projection ends at `irtt_*` + `router_reachable` + `alerting_*`. Adding `fusion_heal_state` to that projection would be a Phase-213-script back-edit (forbidden by D-11). **Resolution for Phase 214:** the aligner reads only the fields the existing poller already projects; the `icmp_udp_divergence` driver in 214-04 uses (a) journal evidence (verified regex below) and (b) `irtt_rtt_mean_ms` going null while `load_rtt_ms` stable — both already in the NDJSON. The `/health.fusion.heal_state` field is documented in `214-REPORT.md` Signal Disposition as a future-phase candidate to add to the poller projection (separate phase; not a D-11 violation when proposed, only when implemented here).

2. **Are exact journal log messages stable between v1.39 (when folded todo was captured) and v1.45.0?**
   - What we know: Folded todo quotes `ICMP deprioritized` (ratio `2.21`) and `UDP deprioritized` (ratio `0.58`) and `Ping to <ip> failed`.
   - **RESOLVED (2026-05-27 source read):** The v1.45.0 log strings are verified:
     - **Reflector miss:** `src/wanctl/rtt_measurement.py:210` emits literal `"Ping to %s failed (no response)"`. Existing rubric regex `Ping to \S+ failed` MATCHES. No change.
     - **Protocol deprioritization:** `src/wanctl/wan_controller.py:1786-1790` emits literal `"<wan>: Protocol deprioritization detected: ICMP/UDP ratio=<r> (<ICMP deprioritized|UDP deprioritized>), ICMP=<x>ms, UDP=<y>ms"`. The interpretation substring `ICMP deprioritized` / `UDP deprioritized` is verbatim from v1.39. Existing rubric regex `(ICMP|UDP)\s+deprioritized` MATCHES (case-sensitive is sufficient; case-insensitive optional and harmless).
     - **Additional v1.45.0 signals NOT in the original v1.39 quote** (available for richer rubric, low-risk add):
       - `src/wanctl/reflector_scorer.py:161-164` emits `"<wan>: Reflector <host> deprioritized (score=<s> < <min>)"` — distinct from ICMP/UDP deprioritization; this is reflector-pool-quality, not protocol-divergence. Belongs in `reflector_loss` driver, not `icmp_udp_divergence`.
       - `src/wanctl/fusion_healer.py:250-256` emits `"Fusion healer <wan>: <old_state> -> <new_state> (r=<pearson>)"` with `<new_state>` ∈ `{active, suspended, recovering}`. This is the journal proxy for the absent `fusion.heal_state` NDJSON field; classifier may match `Fusion healer .* -> suspended` as an `icmp_udp_divergence` trigger when journal evidence is needed.
   - **Resolution for Phase 214:** Plan 214-04's `JOURNAL_PROTO_DIVERGENCE_REGEX` is updated to `(?i)(ICMP|UDP)\s+deprioritized|Fusion healer.*->\s*suspended` (alternation captures both signals). `JOURNAL_REFLECTOR_FAIL_REGEX` stays at `Ping to \S+ failed`. Optional: `JOURNAL_REFLECTOR_DEPRIORITIZED_REGEX = r"Reflector \S+ deprioritized"` as a secondary `reflector_loss` trigger.

3. **NDJSON time-key drift (related — surfaced during Q1/Q2 source read):**
   - What we know (from 214-03 plan): aligner reads `r.get("sampled_utc") or r.get("t_wall_unix")` as the per-row epoch.
   - **RESOLVED (2026-05-27 source read of live NDJSON):** Live `/health` NDJSON rows from `phase213-health-poller.sh` have ONLY `t_wall` (ISO8601 like `"2026-05-27T22:27:06+00:00"`) — NOT `sampled_utc`, NOT `t_wall_unix`. The aligner contract must read `t_wall` and convert via `datetime.fromisoformat(t_wall)` → `int(.timestamp())`. Plan 214-03 aligner interface updated accordingly; Plan 214-02 extractor returns `window_start_utc` and `window_end_utc` as ISO8601 strings (consumer converts when needed). This also resolves checker Warning #5 (asymmetric naming).

4. **Should the optional ATT contrast run (D-04) be conducted in the same window as the inconclusive Spectrum run, or in a comparable but separate window?** (STILL OPEN — operator decision at run time)
   - What we know: D-04 says one ATT run if Spectrum reproduces collapse OR is inconclusive; no time-of-day stipulation given.
   - What's unclear: Whether contrast requires same-window comparability (less DOCSIS, share NTP-syncable contextual conditions) or just "any window."
   - Recommendation: Plan default to same-window-as-the-inconclusive-Spectrum-window; record decision in the matrix-summary.json.

5. **What is the expected matrix-summary.json schema for downstream phases?** (RESOLVED — default schema locked in 214-05 plan)
   - What we know: Phase 215 (Spectrum upload reclaim) will consult Phase 214 outputs.
   - Resolution: Plan 214-05 ships default `{"phase": 214, "verdict": "pass|fail|ambiguous", "primary_driver": "<name>|null", "ranked_drivers": [...], "windows": [...], "signal_disposition": "form_b|form_c|none", "started_utc", "ended_utc", "git_head_sha", "mutation_posture"}`. Phase 215 planning maps onto this.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — stdlib only, all integration points verified via direct file inspection or running existing scripts.
- Architecture: HIGH — every component is either reused from Phase 213 unchanged or has a working precedent (phase198 extractor, phase213 aligner shape).
- Pitfalls: HIGH — flent schema verified by inspecting actual .flent.gz files; Phase 213 bug verified by reading the classifier source.
- Validation architecture: HIGH — pytest already in use; fixtures are pre-existing artifacts already in the repo.
- Signal disposition (Pattern 5): HIGH — directly maps onto D-12/D-13/D-14 lock; nothing speculative.

**Research date:** 2026-05-27
**Valid until:** 2026-06-27 (stable: stdlib parsing + locked decisions + no upstream library dependency). Re-verify if (a) flent version on the dev VM changes, (b) wanctl `/health` payload shape changes, (c) D-XX decisions are revised, or (d) Phase 213 scripts/structure are modified.
