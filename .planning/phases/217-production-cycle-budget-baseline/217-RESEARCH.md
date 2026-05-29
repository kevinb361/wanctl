# Phase 217: Production Cycle-Budget Baseline - Research

**Researched:** 2026-05-29
**Domain:** Production performance profiling of a 50ms (20Hz) control loop; log/journal parsing; systemd override capture; measurement + decision (no control-path change)
**Confidence:** HIGH (all findings grounded in current `src/`, `scripts/`, `deploy/`, and existing docs with file:line citations)

## Summary

This is a measurement + decision phase. The full profiling stack already exists (`perf_profiler.py`, `profiling_collector.py`, `analyze_profiling.py`, the `--profile` flag, and `/health` `cycle_budget` telemetry). No new instrumentation is needed. The phase consumes that stack on Spectrum for ≥1h, attributes per-cycle cost across the five PERF-02 categories, writes a committed artifact + 1-page summary, creates the missing `docs/PROFILING.md` runbook, and closes-or-promotes the pending todo against the D-03 absolute bars.

**The single highest-risk finding the planner MUST design around:** the existing analysis scripts (`profiling_collector.py`, `analyze_profiling.py`) parse log files with the regex `(\w+): (\d+\.\d+)ms`. That regex **only matches the `PerfTimer.__exit__` DEBUG lines** (`autorate_rtt_measurement: 40.5ms`), which require the daemon to run at **DEBUG level** (`--debug`). It does **NOT** match the periodic `report()` output that the `--profile` flag actually produces (format: `label: count=1200, min=12.3ms, avg=15.4ms, ...`), and it does **NOT** match JSON-formatted logs. I verified this empirically (see Pitfall 1). So `--profile` alone gives you human-readable aggregate reports in the log, but the analyzer scripts will return "No timing measurements found" against a `--profile`-only log. This is the crux of the capture design and it directly determines what the `.profile.json` artifact can contain and how acceptance criteria must be written.

**Primary recommendation:** Capture via systemd drop-in adding **both `--profile` and `--debug`** (DEBUG produces the analyzer-parseable per-sample `label: X.Xms` lines; `--profile` produces human-readable periodic aggregates as a cross-check). Pull data from the main log file `/var/log/wanctl/spectrum.log` (not journald — the parseable lines live in the rotating file handler). Run `profiling_collector.py ... --output json` to produce the committed `.profile.json` artifact, and `analyze_profiling.py` to produce the dominance/percentage breakdown. Cross-check both against the live `/health` `cycle_budget.subsystems` block, which is computed independently from the same profiler deques and requires no DEBUG. Explicitly state the observer-effect caveat: DEBUG-level capture adds ~11 per-cycle log writes (~220 writes/sec at 20Hz) that are absent in steady-state `--profile`-off production, so the captured `cycle_total` is an upper bound, not the steady-state cost.

## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** Profile **Spectrum only** (`1.45.0`, v1.44 `besteffort wash` CAKE topology). ATT/DSL is out of scope.
- **D-02:** Capture **~1h organic household traffic** (steady-state budget) **plus a short driven RRUL/upload segment** using the Phase 213 harness, to exercise the change-gated `autorate_router_write_*` path.
- **D-03:** Judge against **absolute health bars**: (a) `autorate_cycle_total` headroom vs the 50ms cycle budget, and (b) structural dominance test — **no single subsystem >40% of `autorate_cycle_total`**.
- **D-04:** **Drop the ±15% / ±25%-vs-v1.39 clauses.** Archived v1.0/v1.9 artifacts may be cited as **informational context only**, never as a pass/fail gate. Close-condition partition: **no-action** if cycle_total has comfortable 50ms headroom AND no subsystem >40%; **promote** if either a subsystem exceeds 40% or total headroom is thin.
- **D-05:** Enable `--profile` via a **systemd override drop-in**, not a permanent edit. Clean enable → ≥1h capture → revert drop-in → restart.
- **D-06:** Commit the artifact to `.planning/perf/v1.45-baseline-spectrum-<date>.profile.json` (create `.planning/perf/`) plus a **1-page summary** stating the close-condition outcome and the deprioritize/promote decision (PERF-03).
- **D-07:** **Create the missing `docs/PROFILING.md`** runbook (enable/capture/revert/analyze, repeatable).

### Claude's Discretion
- Exact driven-segment duration.
- The analysis script invocation (`scripts/analyze_profiling.py`).
- Summary format.
- Whether to quantify the profiling observer-effect inline or as a noted caveat.

### Deferred Ideas (OUT OF SCOPE)
- **Any actual optimization** (RTT-path restructuring, per-cycle metrics/logging allocation, router/transport cost reduction). If the data promotes the todo, that becomes a v1.46+ optimization phase.
- **ATT cycle-budget profile** — Spectrum-only per D-01.

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| PERF-01 | Close or promote the pending post-hotpath profiling todo by capturing ≥1h of current production cycle-budget data. | Capture mechanics (Q4), artifact schema (Q1), close-condition partition reinterpreted by D-03/D-04. Capture = `--profile`+`--debug` drop-in on Spectrum, ≥1h, parse `/var/log/wanctl/spectrum.log`. |
| PERF-02 | The profile identifies whether RTT measurement, CAKE stats, router communication, logging/metrics, or storage writes is the dominant hot-path cost. | Subsystem label→category map (Q2). 4 of 5 categories have direct labels; **storage writes has NO hot-path label** (deferred to background worker) and must be inferred from `wanctl-history --ingestion-rate` (gap flagged below). |
| PERF-03 | If cycle budget is healthy, performance work is explicitly deprioritized in favor of quality/tuning. | The 1-page summary (D-06) records the explicit decision against the D-03 bars. |

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Per-cycle subsystem timing | Control loop (`wan_controller.run_cycle`) | — | `PerfTimer` wraps each `_run_*` subsystem; `_record_profiling` accumulates into `OperationProfiler` deques. `wan_controller.py:2540-2614` |
| Profiling aggregation + periodic report | Profiler module (`perf_profiler.OperationProfiler`) | — | Bounded deque (maxlen 100) of samples per label; `report()` emits aggregate at INFO every 1200 cycles (~60s). `perf_profiler.py:66-195,231,296-300` |
| `--profile` flag wiring | Daemon entry (`autorate_continuous`) | — | `--profile` → `_configure_controller_flags` → `enable_profiling(True)` per WAN. `autorate_continuous.py:294-298,490-497`; `wan_controller.py:4384-4386` |
| Cycle-budget telemetry surface | Health server (`health_check`) | — | `_build_cycle_budget` reads the same profiler deques and exposes avg/p95/p99 + per-subsystem breakdown over HTTP `/health`. `health_check.py:114-151,259-269`. **No DEBUG needed.** |
| Log → stats extraction | Offline scripts (`scripts/`) | — | `profiling_collector.py` / `analyze_profiling.py` regex-parse the log file. `analyze_profiling.py:23-41`; `profiling_collector.py:22-48` |
| Storage-write attribution | Deferred I/O worker (`DeferredIOWorker`) + `wanctl-history` | — | SQLite writes are off the hot path (background worker, `autorate_continuous.py:518-528`). Hot-path cost is NOT directly profiled; use `wanctl-history --ingestion-rate`. `history.py:559,651-715` |
| Load driving (driven segment) | External harness (dev VM) | — | `scripts/phase213-baseline-capture.sh` → `scripts/phase191-flent-capture.sh` runs `flent rrul`/`tcp_upload` from the dev VM; no production mutation. |

## Standard Stack

This phase builds nothing new. The relevant existing components:

### Core (existing, consumed as-is)
| Component | File:Line | Purpose |
|-----------|-----------|---------|
| `OperationProfiler` | `perf_profiler.py:66-195` | Bounded-deque (maxlen=100) per-label sample store; `stats()` returns count/min/max/avg/p95/p99; `report()` emits aggregate text. |
| `PerfTimer` | `perf_profiler.py:25-63` | Context manager; on `__exit__` logs `label: X.Xms` **at DEBUG, only if logger passed and `isEnabledFor(DEBUG)`**. |
| `record_cycle_profiling` | `perf_profiler.py:234-302` | Shared per-cycle recorder; records timings, detects overruns, emits DEBUG `extra` dict (gated on DEBUG), fires periodic `report()` (gated on `profiling_enabled`). |
| `_record_profiling` | `wan_controller.py:2408-2462` | Autorate wrapper; builds the canonical timings dict (15 labels) and delegates. |
| `_build_cycle_budget` | `health_check.py:78-151` | Builds the `/health` `cycle_budget` block from profiler deques (independent of log level). |
| `profiling_collector.py` | `scripts/profiling_collector.py` | Parses a log file → per-subsystem stats; `--output json|csv|text`. |
| `analyze_profiling.py` | `scripts/analyze_profiling.py` | Parses a log file → markdown report with percentages, utilization, headroom, bottleneck ranking. |
| `wanctl-history --ingestion-rate` | `history.py:559,651-715` | Per-metric SQLite write-rate (storage-write attribution proxy). |

### Supporting (load driving)
| Component | File | Purpose |
|-----------|------|---------|
| `phase213-baseline-capture.sh` | `scripts/` | Orchestrates the baseline suite (browse, tcp_upload, tcp_download, rrul, tcp_12down), paired `/health` NDJSON pollers, manifest. Default `--flent-duration 60`. |
| `phase191-flent-capture.sh` | `scripts/` | Underlying flent runner: `flent <TEST> --local-bind <ip> -H <host> -l <dur> -t <title> -D <dir> -o <plot>`. (`phase191-flent-capture.sh:158-164`) |
| `phase213-health-poller.sh` | `scripts/` | 1Hz `/health` NDJSON projection during a window. |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Parsing `/var/log/wanctl/spectrum.log` (file) | Parsing `journalctl -u wanctl@spectrum` (journal) | Both unit handlers receive the same records, but the analyzer expects a file path (`--log-file`). The file handler is INFO-level for the rotating main log; DEBUG lines only land in the file when DEBUG is enabled. Reading the file is simpler and matches the script contract. Journald is fine for live `grep "Profiling Report"` spot-checks. |
| Log-parse pipeline | `/health` `cycle_budget.subsystems` snapshots | `/health` gives live avg/p95/p99 per subsystem with NO DEBUG observer-effect, but it is a rolling window (deque maxlen 100 = last ~5s at 20Hz), not a full 1h aggregate. **Use as an independent cross-check, not the primary artifact.** |

**Installation:** None. `flent` must be present on the dev VM (Phase 213 used `Flent 2.1.1` / Python 3.12.3). See Environment Availability.

## Architecture Patterns

### Data Flow (capture → artifact → decision)

```
[dev VM] flent rrul/tcp_upload  ──drives load──▶  Spectrum link (driven segment, D-02)
                                                        │
organic household traffic ──────────────────────▶  Spectrum link (steady-state, D-02)
                                                        │
                                            wanctl@spectrum (--profile --debug)
                                                        │
                              run_cycle() PerfTimer per subsystem (always measures)
                                                        │
                          ┌─────────────────────────────┼──────────────────────────────┐
                          ▼                              ▼                              ▼
            PerfTimer DEBUG lines           periodic report() INFO        /health cycle_budget
            "label: X.Xms"  (parseable)     "label: count=.., avg=..ms"   (live avg/p95/p99)
                          │                  (human cross-check)            (independent check)
                          ▼
            /var/log/wanctl/spectrum.log
                          │
            scripts/profiling_collector.py --output json  ──▶  v1.45-baseline-spectrum-<date>.profile.json  (D-06)
            scripts/analyze_profiling.py                  ──▶  markdown breakdown (percentages, >40% test)
                          │
            map labels → PERF-02 categories  +  wanctl-history --ingestion-rate (storage proxy)
                          │
            1-page summary: D-03 bars → close (no-action) | promote
```

### Pattern 1: Capture via transient systemd drop-in (D-05)
**What:** Add `--profile` (and `--debug` for parseable data) to `ExecStart` via an override that does NOT touch the checked-in unit, then revert.
**When to use:** Any time-bounded production instrumentation pass.
**Mechanics** (the checked-in unit is `deploy/systemd/wanctl@.service`; deployed instance is `wanctl@spectrum`):

```bash
# 1. Create the drop-in. systemctl edit opens an editor; the drop-in path is:
#    /etc/systemd/system/wanctl@spectrum.service.d/override.conf
sudo systemctl edit wanctl@spectrum
```

Drop-in content (ExecStart must be cleared then re-set; the base unit's ExecStart is
`/usr/bin/python3 /opt/wanctl/autorate_continuous.py --config /etc/wanctl/%i.yaml`):

```ini
[Service]
ExecStart=
ExecStart=/usr/bin/python3 /opt/wanctl/autorate_continuous.py --config /etc/wanctl/spectrum.yaml --profile --debug
```

```bash
# 2. Apply + restart, then capture for >= 1h
sudo systemctl daemon-reload
sudo systemctl restart wanctl@spectrum
# ... drive load (D-02 driven segment) + let organic traffic accumulate >= 1h ...

# 3. Revert cleanly (removes the drop-in) and restart back to steady state
sudo systemctl revert wanctl@spectrum
sudo systemctl daemon-reload
sudo systemctl restart wanctl@spectrum
```

**Artifact retrieval:** the parseable data is in `/var/log/wanctl/spectrum.log` (config: `configs/spectrum.yaml:152-154`, `main_log: /var/log/wanctl/spectrum.log`). Copy it off the host (`scp`/`ssh cat`) before rotation evicts it (RotatingFileHandler, default 10MB × 3 backups — at DEBUG/20Hz this rotates fast; see Pitfall 4).

### Pattern 2: Independent triangulation
**What:** Three data sources for the same numbers — DEBUG log parse (primary), `--profile` `report()` text (human cross-check), `/health` `cycle_budget` (no-observer-effect check).
**When to use:** To bound the observer-effect and validate the artifact. If the DEBUG-derived `cycle_total` avg is materially higher than the `/health` snapshot avg taken in the same window, the delta is (mostly) observer-effect.

### Anti-Patterns to Avoid
- **Running `analyze_profiling.py` against a `--profile`-only (INFO) log** and concluding "no data" means the daemon isn't profiling. The scripts' regex doesn't match `report()` format. (Pitfall 1.)
- **Editing the checked-in `deploy/systemd/wanctl@.service`** instead of a drop-in. Violates D-05 and risks leaving `--profile/--debug` permanently enabled.
- **Treating `cycle_total` captured under DEBUG as the steady-state budget.** It includes observer-effect. State the caveat (D-03 judges headroom — be conservative, i.e., a DEBUG-inflated number that still has comfortable headroom is a *stronger* no-action signal, not weaker).
- **Reading the archived v1.0 "2.1% utilization / 1958ms headroom" numbers as a current target.** Those are at the old 2-second interval, not 50ms. Informational only (D-04).

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Per-cycle timing | New instrumentation | `PerfTimer`/`OperationProfiler` already wired in `run_cycle` | Full stack exists; phase boundary forbids `src/` changes. |
| Log → stats | A new parser | `profiling_collector.py --output json` | Already produces count/min/p50/avg/max/p95/p99 JSON per subsystem. |
| Percentage / dominance breakdown | Hand math | `analyze_profiling.py` | Already computes per-subsystem % of cycle_total + ranks bottlenecks + utilization/headroom vs budget. |
| Load generation | Custom traffic gen | `phase213-baseline-capture.sh` / `phase191-flent-capture.sh` | Proven, no-mutation, dev-VM-bound; Phase 213 already validated it on Spectrum. |
| Storage-write rate | Inferring from disk | `wanctl-history --ingestion-rate --wan spectrum` | Purpose-built per-metric write-rate tool (v1.44 Phase 208). |

**Key insight:** The only genuinely new build artifacts in this phase are **data and docs**: the `.planning/perf/` dir, the committed `.profile.json`, the 1-page summary, and `docs/PROFILING.md`. Possibly one small **post-processing helper** if the planner wants the artifact JSON to also embed the category roll-up and the >40% verdict (the scripts give per-subsystem stats but not the PERF-02 5-category mapping — see Q2 gap).

## Question-by-Question Findings

### Q1 — Profiler output schema
There is **no native `.profile.json` writer**. `--profile` only emits a periodic human-readable text `report()` to the log at INFO every `PROFILE_REPORT_INTERVAL = 1200` cycles (~60s) (`perf_profiler.py:231,296-300`). The artifact at `.planning/perf/v1.45-baseline-spectrum-<date>.profile.json` will be produced by **`profiling_collector.py --output json`** (`profiling_collector.py:226-227`), whose schema is a dict keyed by subsystem label, each value:

```json
{
  "autorate_cycle_total": {
    "count": 72000, "min_ms": 9.8, "p50_ms": 14.2, "avg_ms": 15.1,
    "max_ms": 61.3, "p95_ms": 22.0, "p99_ms": 28.4
  },
  "autorate_rtt_measurement": { "...": "..." }
}
```

Units: all `*_ms` are milliseconds, rounded to 2 dp by the formatter. Labels are the raw `autorate_*` names (NOT the `*_ms`-suffixed health-block short names). A "single sample" is one `label: X.Xms` DEBUG log line per timer per cycle; the JSON above is the **aggregate** over all samples in the parsed log. [VERIFIED: `profiling_collector.py:51-80,226-227`]

> Note on `label→*_ms` conversion in CONTEXT: that conversion happens in two unrelated places — (a) the DEBUG `extra` dict in `record_cycle_profiling` (`perf_profiler.py:290-293`, `autorate_rtt_measurement → rtt_measurement_ms`), and (b) the `/health` short-name strip (`health_check.py:142`, `autorate_rtt_measurement → rtt_measurement`). The committed `.profile.json` from `profiling_collector.py` keeps the **full `autorate_*` labels** — plan acceptance criteria against those.

### Q2 — Canonical subsystem label set → PERF-02 category map
The full timings dict has **15 labels** (`wan_controller.py:2434-2450`). Mapped to the 5 PERF-02 categories:

| PERF-02 category | Hot-path label(s) | File:Line |
|------------------|-------------------|-----------|
| RTT measurement | `autorate_rtt_measurement` | `wan_controller.py:2435` |
| CAKE stats | `autorate_cake_stats` | `wan_controller.py:2440` |
| Router communication | `autorate_router_communication` (parent), `autorate_router_apply_primary`, `autorate_router_apply_pending`, `autorate_router_write_download`, `autorate_router_write_upload`, `autorate_router_write_skipped`, `autorate_router_write_fallback` | `wan_controller.py:2437,2444-2449` |
| Logging / metrics | `autorate_logging_metrics` | `wan_controller.py:2443` |
| **Storage writes** | **(no hot-path label)** | — |

Other labels not in a PERF-02 category but counted in `cycle_total`: `autorate_state_management` (parent), `autorate_signal_processing`, `autorate_ewma_spike`, `autorate_congestion_assess`, `autorate_irtt_observation`, `autorate_post_cycle`. The `/health` block uses a slightly different list of 9 (`health_check.py:127-137`) — note it includes `autorate_post_cycle` and omits the router-write sub-labels.

**Gap the planner MUST flag (PERF-02):** there is **no `autorate_storage_*` label**. SQLite writes are deliberately off the hot path — deferred to `DeferredIOWorker` (`autorate_continuous.py:518-528`). So storage-write cost **cannot** come from the cycle profile; it must be attributed via **`wanctl-history --ingestion-rate --wan spectrum`** (`history.py:559,699-715`). The PERF-02 "dominant cost" determination is therefore: rank the four directly-profiled categories by % of `cycle_total`, and separately report storage write-rate as a non-hot-path note. Acceptance criteria must not assert a storage % of cycle_total — that number does not exist by design.

> Beware double-counting: `autorate_router_communication` is the parent timer wrapping the router subsystem; `router_apply_*`/`router_write_*` are sub-timers inside it. For the dominance test, use the **parent** (`autorate_router_communication`) as the category total; use sub-timers only for drill-down. (`wan_controller.py:2585-2607`)

### Q3 — Analysis invocation
Two scripts, both regex-parse a log file (`(\w+): (\d+\.\d+)ms`, `analyze_profiling.py:34`, `profiling_collector.py:41`):

```bash
# Per-subsystem stats as JSON -> this becomes the committed artifact (D-06)
.venv/bin/python scripts/profiling_collector.py /path/to/spectrum.log --all --output json \
  > .planning/perf/v1.45-baseline-spectrum-<date>.profile.json

# Percentage breakdown + >40% dominance + utilization/headroom markdown
.venv/bin/python scripts/analyze_profiling.py --log-file /path/to/spectrum.log --budget 50 \
  --output /tmp/spectrum-analysis.md
```

`analyze_profiling.py` **does** compute per-subsystem percentage of `autorate_cycle_total` (`calculate_percentages`, `:86-111`), ranks the top-5 bottlenecks (`:184-193`), and reports utilization + headroom vs the 50ms budget (`:166-175`). It does **NOT** directly emit a boolean ">40% dominance" verdict, and its percentage list excludes the cycle_total itself. **Post-processing the planner must add:** (1) compute the D-03 >40% test from the percentages (the script's top bottleneck % is the number to threshold), and (2) roll the per-subsystem percentages into the 4 PERF-02 categories (the script reports per-label, not per-category). This is a small Python/jq step over the collector JSON, not a new tool. [VERIFIED: `analyze_profiling.py:86-227`]

### Q4 — Capture mechanics & safety
- `--profile` is parsed at `autorate_continuous.py:294-298`, applied to all controllers at `:490-497` (`_configure_controller_flags` → `enable_profiling(True)` → `wan_controller.py:4384-4386` sets `_profiling_enabled`). [VERIFIED]
- Drop-in path: `/etc/systemd/system/wanctl@spectrum.service.d/override.conf`. The `ExecStart=` must be cleared first (single-value directive). Base ExecStart at `deploy/systemd/wanctl@.service` (`ExecStart=/usr/bin/python3 /opt/wanctl/autorate_continuous.py --config /etc/wanctl/%i.yaml`). The override hard-codes `spectrum` (do not rely on `%i` substitution surviving a literal edit unless you re-template it). [VERIFIED]
- Sequence: `systemctl edit` → `daemon-reload` → `restart wanctl@spectrum` → capture ≥1h → `systemctl revert wanctl@spectrum` → `daemon-reload` → `restart`. PERFORMANCE.md already documents this exact pattern (`docs/PERFORMANCE.md:47-73`) and the archived `docs/archive/PROFILING.md` corroborates it. [VERIFIED]
- Artifact written on host: nowhere as JSON natively — the **log file** `/var/log/wanctl/spectrum.log` is the source; retrieve via scp/ssh. (`configs/spectrum.yaml:153`)
- **Watchdog interaction (flag for the planner):** the unit has `WatchdogSec=30s` and `Restart=on-failure` (`deploy/systemd/wanctl@.service`). A `restart` to apply the drop-in is a normal sd_notify-supervised start; the watchdog only fires if the daemon stops heartbeating for 30s. DEBUG logging adds I/O — if DEBUG write volume ever stalled the loop past 30s the watchdog would restart it (would corrupt the capture window and is a real risk on a slow disk). Mitigation: monitor `journalctl -u wanctl@spectrum -f` for overrun warnings / restarts during the window; if restarts occur, drop `--debug` and fall back to `--profile` + `/health` polling (see Pitfall 1 fallback). Also `CPUAffinity=1-2` and `MemoryHigh=512M/MemoryMax=640M` — DEBUG buffers shouldn't approach the memory cap but note it.

### Q5 — Observer-effect
**What always runs regardless of flags:** every `PerfTimer.__enter__/__exit__` (two `perf_counter()` calls per timer) and every `profiler.record()` into the deques. So the *measurement* itself is always-on; the deques are always populated; `/health cycle_budget` is always available. (`wan_controller.py:2544-2614`, `perf_profiler.py:52-63,103-112`)

**What `--profile` adds:** one `profiler.report()` call to the log every ~60s (`perf_profiler.py:296-300`). Negligible per-cycle cost.

**What `--debug` adds (this is the real observer-effect):**
1. `PerfTimer.__exit__` emits a formatted DEBUG log line **per timer per cycle** when `isEnabledFor(DEBUG)` (`perf_profiler.py:62-63`). There are ~11 PerfTimer contexts per cycle in `run_cycle` (`wan_controller.py:2544-2612`). At 20Hz that is ~220 string-formats + log-writes/sec to a RotatingFileHandler.
2. `record_cycle_profiling` builds the `extra` dict (~16 dict insertions + `round()` per cycle) only when `isEnabledFor(DEBUG)` (`perf_profiler.py:287-294`).

**Bound:** roughly ~11 `logger.debug(...)` calls + one `extra`-dict-bearing debug call per 50ms cycle, i.e. ~12 log emissions/cycle × 20 = ~240/sec, all to a file handler. The exact ms cost is not statically derivable (depends on disk/handler), but it is strictly additive and absent in steady-state production (which runs at INFO with these paths gated off — the whole point of the original hot-path optimization the todo references). **Mandatory caveat for the summary:** "Captured under DEBUG; `autorate_cycle_total` includes per-cycle DEBUG logging overhead absent in steady-state INFO operation. The DEBUG-derived budget is an upper bound on real cost. Cross-checked against `/health cycle_budget` (no DEBUG overhead) — delta ≈ observer-effect." If the planner wants to avoid the caveat entirely, the no-`--debug` path (Pitfall 1 fallback: `--profile` report() + `/health` polling) is observer-effect-clean but yields aggregate-only data, not per-sample. [VERIFIED]

### Q6 — Driven segment (D-02)
The driven segment exists because `autorate_router_write_*` only fires on rate change (flash-wear guard: `rates_changed` gate at `wan_controller.py:2578-2590`). A quiet household leaves those labels at ~0. To force sustained rate changes, drive saturating load so the controller steps rates up/down:

```bash
# From the dev VM (no production mutation). Underlying invocation (phase191-flent-capture.sh:158-164):
flent rrul --local-bind <spectrum-dev-bind-ip> -H dallas -l <duration_sec> -t <title> -D <out_dir> -o <plot.png>
flent tcp_upload --local-bind <spectrum-dev-bind-ip> -H dallas -l <duration_sec> -t <title> -D <out_dir> -o <plot.png>
```

Or via the orchestrator (handles paired `/health` polling, manifest, bind map):

```bash
scripts/phase213-baseline-capture.sh --host dallas --flent-duration <sec> --tests tcp_upload,rrul --wans spectrum
```

Phase 213 used `flent_duration=60`, netperf host `dallas`, Spectrum dev bind `10.10.110.226`, and saw Spectrum upload pegged near ceiling for ~81% of `tcp_upload` samples — confirming `rrul`/`tcp_upload` reliably saturate and provoke control activity. Discretion: a single 60s `rrul` + 60s `tcp_upload` inside the 1h window is the minimum to populate the router-write labels; the planner may extend. **Sequencing:** run the driven segment *inside* the ≥1h capture window so its samples land in the same log/deques. [VERIFIED: `scripts/phase191-flent-capture.sh:158-164`; `.planning/phases/213-experience-baseline-harness/213-REPORT.md:13,17-25,97-98`]

### Q7 — Runbook content (D-07)
`docs/PROFILING.md` does not exist (only `docs/archive/PROFILING.md` does). House style of the active perf doc (`docs/PERFORMANCE.md`): H1 title, short intro paragraph, `## Section` headers, fenced `bash` blocks, a "Production Standard / Operational Guardrails" framing, and explicit links to archived material. `docs/TESTING.md` follows the same convention. The new runbook should mirror this: enable (drop-in) → drive load → capture → revert → analyze → interpret-against-D-03-bars, with the `--profile`+`--debug` requirement and the regex/format caveat called out prominently. It should link to (not duplicate) `docs/PERFORMANCE.md §Profiling Workflow` and supersede the stale archived `docs/archive/PROFILING.md` parser commands (which point the collector at a `--profile`-only log — see Pitfall 1). [VERIFIED: `docs/PERFORMANCE.md:1-84`, `docs/archive/PROFILING.md:26-235`]

### Q8 — Archived baselines (informational only, per D-04)
- **v1.0** (`PROFILING-ANALYSIS.md`): cycle_total avg **41.1ms** (Spectrum) / **31.4ms** (other), RTT measurement **98%+** of cycle, but **at the old 2-second interval** → 2.1% budget utilization, ~1959ms headroom. *Citable as: "RTT historically dominated; absolute RTT excellent" — but the % and headroom are NOT comparable to 50ms.* (`:9,31-32,46-47,87-88`)
- **v1.9** (`47-RESEARCH.md`): explicitly frames the 50ms shift — expected **cycle_total 30-45ms**, **RTT 20-40ms (dominant)**, router comms 0ms (skipped) or 15-25ms (on rate change), at 50ms cycles consuming 60-80% of budget. **It also pre-flagged the exact regex risk** this research confirms: "The regex pattern `(\w+): (\d+\.\d+)ms` should still work, but report generation may need updating" (`:213`). *Citable as the most relevant prior expectation for what "healthy at 50ms" looks like.* (`:11,84-87,213`)

Use these as context-setting in the summary ("prior expectation: RTT-dominant, 30-45ms at 50ms"), never as a pass/fail gate (D-04).

## Runtime State Inventory

This is a measurement phase, but the capture mutates live service config transiently. The systemd drop-in IS runtime state that must be reverted.

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | None new written to datastores by this phase. The committed `.profile.json` is derived from logs, not a DB. | None |
| Live service config | **systemd drop-in** `/etc/systemd/system/wanctl@spectrum.service.d/override.conf` (added by `systemctl edit`). This is live config NOT in git. | **MUST `systemctl revert wanctl@spectrum` + daemon-reload + restart** after capture (D-05). Verify drop-in dir is gone. |
| OS-registered state | The `wanctl@spectrum` unit instance itself (already registered; not modified — only overridden). | None beyond the revert above. |
| Secrets/env vars | None touched. `EnvironmentFile=-/etc/wanctl/secrets` unchanged. | None |
| Build artifacts | None. No `src/` change, no reinstall. `/opt/wanctl` code untouched. | None |

**The canonical revert check:** after the phase, `systemctl cat wanctl@spectrum` should show ONLY the base unit (no drop-in), and the running ExecStart must NOT contain `--profile`/`--debug`. This is the single most important safety gate.

## Common Pitfalls

### Pitfall 1: Analyzer scripts return "No timing measurements found" against a `--profile`-only log
**What goes wrong:** You run `--profile` (the flag D-05 names), grep confirms `=== Profiling Report ===` lines exist, but `profiling_collector.py`/`analyze_profiling.py` report no data and exit 1.
**Why it happens:** The regex `(\w+): (\d+\.\d+)ms` only matches `PerfTimer.__exit__` DEBUG output (`label: 40.5ms`). The `report()` output is `label: count=1200, min=12.3ms, avg=15.4ms, ...` — after the label's colon comes `count=`, not a digit, so the regex captures nothing. **Verified empirically:**
```
REPORT-format line ('autorate_cycle_total: count=1200, min=12.3ms, ...'): []  (no match)
PerfTimer DEBUG line ('autorate_rtt_measurement: 40.5ms'):                [('autorate_rtt_measurement','40.5')]  (match)
JSON-formatted line:                                                       []  (no match)
```
**How to avoid:** Capture with **`--debug`** (in addition to `--profile`) so the parseable per-sample lines exist, and ensure the log is **text format** (`WANCTL_LOG_FORMAT` unset/`text`; JSON breaks the regex too — `logging_utils.py:105-119,132-134`). Confirm the deployed Spectrum env does not set `WANCTL_LOG_FORMAT=json`.
**Fallback (observer-effect-clean):** if `--debug` proves too heavy (watchdog/disk), skip it and derive numbers from (a) the `--profile` `report()` aggregates read by eye / a small custom parser, and (b) `/health cycle_budget.subsystems` polled across the window. This loses per-sample granularity but is still sufficient for the D-03 bars (avg + p95/p99 + dominance %).
**Warning signs:** collector exits with `WARNING: No timing measurements found`; `report()` text present but JSON empty.

### Pitfall 2: Attributing storage-write cost from the cycle profile
**What goes wrong:** Looking for an `autorate_storage_*` label to satisfy PERF-02's "storage writes" category and finding none, or worse, inventing one.
**Why it happens:** SQLite writes are off the hot path (DeferredIOWorker). There is intentionally no hot-path storage timer.
**How to avoid:** Report storage-write load via `wanctl-history --ingestion-rate --wan spectrum` as a separate, non-hot-path metric. State in the summary that storage is not a cycle_total contributor by design.

### Pitfall 3: Double-counting router sub-timers in the dominance test
**What goes wrong:** Summing `router_communication` + `router_apply_*` + `router_write_*` overstates router cost above 100%.
**Why it happens:** The sub-timers are nested inside the parent `autorate_router_communication` timer.
**How to avoid:** Use `autorate_router_communication` as the category total for the >40% test; use sub-timers only for drill-down narrative.

### Pitfall 4: Log rotation evicts the capture window
**What goes wrong:** At DEBUG + 20Hz the main log grows fast (~240 lines/sec); default RotatingFileHandler is 10MB × 3 backups — a 1h DEBUG capture can roll over and lose early samples.
**Why it happens:** `RotatingFileHandler(max_bytes, backup_count)` defaults (`logging_utils.py:200`).
**How to avoid:** Either retrieve `/var/log/wanctl/spectrum.log*` (all backups) and concatenate in chronological order before parsing, or capture from `journalctl -u wanctl@spectrum --since ... --until ...` to a file (journal retains regardless of file rotation) and parse that. Check `max_bytes`/`backup_count` in the deployed Spectrum config before starting.

### Pitfall 5: Driven segment runs outside the capture window
**What goes wrong:** Router-write labels stay at 0 because the flent run happened before/after `--profile` was active.
**How to avoid:** Run the flent `rrul`/`tcp_upload` strictly *inside* the enabled window; verify afterward that `autorate_router_write_*` have non-zero counts in the artifact.

## Code Examples

### Verify the `--profile` flag exists on the deployed binary
```bash
# (archived runbook pattern, docs/archive/PROFILING.md:91)
ssh <spectrum-host> '/usr/bin/python3 /opt/wanctl/autorate_continuous.py --help | grep -- --profile'
```

### Produce the committed artifact + breakdown (after retrieving the log)
```bash
LOG=/path/to/spectrum-capture.log   # DEBUG, text-format, full window (concatenated if rotated)

# D-06 artifact:
.venv/bin/python scripts/profiling_collector.py "$LOG" --all --output json \
  > .planning/perf/v1.45-baseline-spectrum-$(date +%Y%m%d).profile.json

# Dominance / utilization / headroom markdown (50ms budget):
.venv/bin/python scripts/analyze_profiling.py --log-file "$LOG" --budget 50 \
  --output /tmp/v1.45-spectrum-analysis.md

# Storage-write attribution (separate from cycle profile):
.venv/bin/python -m wanctl.history --ingestion-rate --wan spectrum
```

### Live no-observer-effect cross-check during the window
```bash
ssh <spectrum-host> 'curl -s http://127.0.0.1:9101/health | python3 -m json.tool' \
  | python3 -c "import sys,json; h=json.load(sys.stdin); print(json.dumps(h['wans'][0]['cycle_budget'], indent=2))"
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| 2-second control interval, 2-4% budget | 50ms (20Hz), 60-80% budget | v1.0 → ~v1.9 | Profiling overhead now matters; <1ms-per-cycle overhead requirement is real (`47-RESEARCH.md:11`). |
| Per-cycle DEBUG/profiling payload always built | Gated behind DEBUG/profile (the original todo's hot-path optimization) | mid-April 2026 | Enabling `--debug` re-activates the gated path → the observer-effect this phase must caveat. |
| `--ingestion-rate` not available | `wanctl-history --ingestion-rate` (v1.44 Phase 208) | v1.44 | Provides the only viable storage-write attribution path. |

**Deprecated/outdated:**
- `docs/archive/PROFILING.md` parser commands point the collector at a `--profile`-only main log and will return no data unless DEBUG is also on. The new `docs/PROFILING.md` must correct this.
- Archived v1.0 utilization/headroom percentages (2s interval) — not comparable to 50ms.

## Validation Architecture

This is a measurement phase. "Validation" = the deliverables exist, are well-formed, and the decision is justified by the data. No new unit tests are required (no `src/` change). The Validation Architecture is artifact/procedure validation.

### Phase Requirements → Validation Map
| Req | Behavior | Validation type | Check |
|-----|----------|-----------------|-------|
| PERF-01 | ≥1h Spectrum profile captured + committed; todo closed/promoted | Artifact existence + content | `.planning/perf/v1.45-baseline-spectrum-<date>.profile.json` exists, parses as JSON, `autorate_cycle_total.count` ≥ ~72000 (1h × 20Hz × 0.5 safety) and `autorate_router_write_*` counts > 0 (driven segment landed). Todo file moved to `done/` or a follow-on phase opened. |
| PERF-02 | Dominant cost category identified | Analysis output | `analyze_profiling.py` markdown ranks subsystems; the 4 PERF-02 hot-path categories are rolled up; >40% dominance test computed; storage write-rate reported separately via `wanctl-history --ingestion-rate`. |
| PERF-03 | Explicit deprioritize/promote decision | Summary content | 1-page summary states the D-03 verdict (headroom comfortable? any category >40%?) and the explicit decision sentence. |

### Acceptance criteria the planner can write (falsifiable)
- Artifact JSON contains keys for all five health-block labels and the four PERF-02 hot-path categories, with `avg_ms`, `p95_ms`, `p99_ms`, `count`.
- `autorate_cycle_total.avg_ms` and `.p99_ms` are reported with explicit headroom vs 50ms.
- Dominance verdict: `max(category % of cycle_total) {<= | >} 40%` stated as a boolean.
- `autorate_router_write_download.count > 0` OR `autorate_router_write_upload.count > 0` (proves the driven segment exercised the change-gated path).
- Observer-effect caveat present in the summary (DEBUG inflation noted; `/health` cross-check delta reported).
- `systemctl cat wanctl@spectrum` shows no drop-in post-phase (revert verified).
- `docs/PROFILING.md` exists and contains the enable→capture→revert→analyze sequence.

### Sampling / cross-checks
- **Per-capture:** tail `journalctl -u wanctl@spectrum -f` during the window for overrun warnings / restarts.
- **Post-capture:** triangulate DEBUG-log avg vs `--profile` `report()` avg vs `/health` snapshot avg.
- **Phase gate:** revert verified; artifact + summary + runbook committed.

### Wave 0 gaps
- Create `.planning/perf/` directory (does not exist).
- Confirm `flent` available on the dev VM (Phase 213 used 2.1.1) and Spectrum dev bind IP / netperf host `dallas` still valid.
- Confirm deployed Spectrum `WANCTL_LOG_FORMAT` is text (not json) and capture/concatenate rotated logs.
- Decide post-processing helper vs jq for category roll-up + >40% verdict (small, not a new tool).

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| `flent` (on dev VM) | Driven segment (D-02) | ✓ (Phase 213) | 2.1.1 / Py 3.12.3 | If absent, skip driven segment → router-write labels stay 0 → note the gap (steady-state still captured). |
| netperf host `dallas` | flent target | ✓ (Phase 213) | — | Any reachable netperf server. |
| Spectrum host SSH + `/health` :9101 | Capture, retrieval, cross-check | ✓ (assumed; Phase 212/213 used it) | — | — |
| `systemctl edit`/`revert` (root on Spectrum host) | Drop-in (D-05) | ✓ (assumed) | — | None — required for D-05. |
| `wanctl-history` | Storage attribution (PERF-02) | ✓ (`history.py`, v1.44) | 1.45 | If unavailable, note storage-write attribution as unmeasured. |
| `.venv` with project deps | Run analysis scripts | ✓ (repo) | — | — |

**Missing dependencies with no fallback:** root access to `systemctl edit/revert wanctl@spectrum` on the production host (D-05 hard requirement).
**Missing dependencies with fallback:** `flent` (degrades the driven segment, not the whole phase).

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Deployed Spectrum logs are **text** format (`WANCTL_LOG_FORMAT` unset → default text). | Pitfall 1, Q3 | If json, the analyzer regex matches nothing even at DEBUG; capture wasted. **Verify before capture** by checking the live log file. |
| A2 | The Spectrum production host allows root `systemctl edit`/`revert` and runs the `wanctl@spectrum` instance. | Q4, Env | If not, D-05 capture path is blocked; needs operator. |
| A3 | flent dev-VM bind IP (`10.10.110.226`) and netperf host `dallas` from Phase 213 are still valid. | Q6 | Driven segment fails to bind/route; router-write labels stay 0. Re-confirm from current bind map. |
| A4 | `/health` is served on `:9101` for Spectrum (CLAUDE.md quick-ref + Phase 213 poller used `10.10.110.223:9101`). | Validation, Q4 | Cross-check unavailable; fall back to log-only. |
| A5 | Default RotatingFileHandler size means a 1h DEBUG capture rotates; concatenation needed. | Pitfall 4 | If max_bytes is large, no concat needed (harmless over-caution). Check deployed config. |
| A6 | ~11 PerfTimer DEBUG emissions/cycle is the dominant observer-effect; exact ms is disk-dependent. | Q5 | If DEBUG cost is larger than assumed and stalls the loop, watchdog restarts the window → fall back to no-`--debug` path. |

## Open Questions (RESOLVED)

1. **Is the deployed Spectrum log text or JSON?** **RESOLVED — Plan 02 Task 1 pre-flight check verifies via `ssh <host> 'head -1 /var/log/wanctl/spectrum.log'`; the drop-in includes `Environment=WANCTL_LOG_FORMAT=text` as the fallback. Capture proceeds only after text-format confirmation.**
   - Known: default is text (`logging_utils.py:115`); JSON breaks the analyzer regex.
   - Unclear: whether the production env sets `WANCTL_LOG_FORMAT=json`.
   - Recommendation: Wave-0 task — `ssh <host> 'head -1 /var/log/wanctl/spectrum.log'`; if JSON, either temporarily force text in the drop-in (`Environment=WANCTL_LOG_FORMAT=text`) or write a JSON-aware parser step.

2. **`--debug` observer-effect magnitude on this specific host.** **RESOLVED — Plan 02 Task 2 captures a mid-window `/health` snapshot; Plan 03 Task 2 reports the delta between DEBUG-log `autorate_cycle_total.avg_ms` and `/health cycle_budget.cycle_time_ms.avg` as the observer-effect figure. Explicit caveat path if the snapshot is missing.**
   - Known: it's strictly additive (~240 log writes/sec) and absent in steady-state.
   - Unclear: the actual ms delta on the production disk.
   - Recommendation: measure it directly — compare DEBUG-log `cycle_total` avg vs `/health` `cycle_budget.cycle_time_ms.avg` taken in the same window. Report the delta as the observer-effect figure (turns a caveat into a number; satisfies the D-03 honesty requirement).

3. **Driven-segment duration.** **RESOLVED (Discretion) — Plan 02 Task 2 invokes `scripts/phase213-baseline-capture.sh --flent-duration 60 --tests tcp_upload,rrul` (60s rrul + 60s tcp_upload) inside the 1h window; sufficient to populate the change-gated router-write labels.** (Discretion) Minimum 60s `rrul` + 60s `tcp_upload` to populate router-write labels; planner may extend within the 1h window.

## Sources

### Primary (HIGH confidence — current code/config/docs in repo)
- `src/wanctl/perf_profiler.py:25-302` — PerfTimer, OperationProfiler, record_cycle_profiling, report format, PROFILE_REPORT_INTERVAL.
- `src/wanctl/wan_controller.py:2408-2462,2540-2614,751-762,4384-4386` — timings dict, run_cycle PerfTimer wiring, rates_changed gate, profiling_enabled.
- `src/wanctl/health_check.py:78-151,259-269` — `_build_cycle_budget`, subsystem label list, /health surface.
- `src/wanctl/autorate_continuous.py:294-298,490-497,518-528` — `--profile` flag, `_configure_controller_flags`, DeferredIOWorker.
- `src/wanctl/logging_utils.py:17-219` — JSONFormatter, get_log_format, setup_logging handler levels.
- `scripts/profiling_collector.py:22-234`, `scripts/analyze_profiling.py:23-322` — regex, JSON/markdown output, percentage/dominance logic.
- `src/wanctl/history.py:438-715` — `--ingestion-rate`.
- `deploy/systemd/wanctl@.service` — ExecStart, WatchdogSec, Restart, CPUAffinity, Memory limits.
- `configs/spectrum.yaml:152-157` — main_log path.
- `docs/PERFORMANCE.md:1-84`, `docs/archive/PROFILING.md:26-370` — existing profiling workflow + house style.
- `scripts/phase213-baseline-capture.sh`, `scripts/phase191-flent-capture.sh:158-164` — driven-segment invocation.
- Empirical regex verification (this session) — confirmed `(\w+): (\d+\.\d+)ms` matches only PerfTimer DEBUG lines.

### Secondary (informational only, per D-04)
- `.planning/milestones/v1.0-phases/01-measurement-infrastructure-profiling/PROFILING-ANALYSIS.md:9,31-47,87-88` — 2s-interval RTT-dominant baseline.
- `.planning/milestones/v1.9-phases/47-cycle-profiling-infrastructure/47-RESEARCH.md:11,84-87,213` — 50ms expectations + pre-flagged regex risk.
- `.planning/phases/213-experience-baseline-harness/213-REPORT.md:13,17-25,97-98` — harness params, flent 2.1.1, dallas, bind map.

## Metadata

**Confidence breakdown:**
- Standard stack / tooling: HIGH — all components read directly from current source.
- Capture mechanics (D-05): HIGH — drop-in pattern corroborated by unit file + existing PERFORMANCE.md.
- Regex/format gap (central risk): HIGH — empirically verified.
- Subsystem→category map: HIGH — direct from timings dict; storage-gap is a structural fact, not an assumption.
- Observer-effect magnitude: MEDIUM — mechanism HIGH, absolute ms cost host-dependent (A6/Q2).
- Driven-segment params (IPs/host): MEDIUM — from Phase 213 evidence, should be re-confirmed live (A3).

**Research date:** 2026-05-29
**Valid until:** ~30 days (stable; the only fast-moving inputs are live host facts in the Assumptions Log).
