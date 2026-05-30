# Phase 217: Production Cycle-Budget Baseline - Research (refresh)

**Researched:** 2026-05-29 (refresh — supersedes the original 217-RESEARCH.md of the same date)
**Domain:** Production performance profiling of a 50ms (20Hz) control loop; structured-log capture; systemd override capture; measurement + decision (no control-path change)
**Confidence:** HIGH (every load-bearing claim cites file:line in current `src/`/`scripts/`/`configs/`; the three previously-broken assumptions are now flagged and replaced)

## Corrections Superseding the Previous Research

Codex peer-review surfaced three blindspots in the prior 217-RESEARCH.md. Each was independently verified against source by the orchestrator and is **corrected** here. The planner must NOT re-inherit any of these:

1. **`autorate_cycle_total: X.Xms` is NOT emitted as a parseable text DEBUG line.** The prior recommendation to capture in text DEBUG and parse `cycle_total` with the existing regex collector is **wrong**. `record_cycle_profiling()` logs cycle_total only as a structured `extra` field on the message `"Cycle timing"`, and the text formatter drops `extra` entirely. See "Verified findings" below for citations and the empirical pattern test.
2. **`/var/log/wanctl/spectrum.log` is INFO-only.** DEBUG lines go to `/var/log/wanctl/spectrum_debug.log` (plus journald when `--debug` runs the console at DEBUG). The prior research's "capture from `/var/log/wanctl/spectrum.log`" was wrong as written; that file does not contain the per-cycle DEBUG samples even when `--debug` is on.
3. **`/health` and DEBUG-logged `cycle_total` cannot cross-check observer-effect within one window.** Both read the same in-process `profiler.stats("autorate_cycle_total")`. The prior research's "report the delta as the observer-effect figure" yields ~0 by construction. A real observer-effect bound needs **adjacent windows** with `--debug` ON vs OFF, or the requirement is downgraded to a documented caveat.

Anchor citations (orchestrator-verified):

- `src/wanctl/perf_profiler.py:266-294` — `total_ms = (time.perf_counter() - cycle_start) * 1000.0`; `profiler.record(f"{label_prefix}_cycle_total", total_ms)`; `logger.debug("Cycle timing", extra=extra)` where `extra = {"cycle_total_ms": ..., "<suffix>_ms": ...}`. Message string is literally `"Cycle timing"`; `cycle_total_ms` lives only in `extra`.
- `src/wanctl/logging_utils.py:122-134` — text formatter is `"%(asctime)s [{wan_name}] [%(levelname)s] %(message)s"`. Drops `extra` entirely.
- `src/wanctl/logging_utils.py:74-102` — JSONFormatter walks `record.__dict__` and includes every key that is not internal to LogRecord. **`extra=` keys ARE preserved** under JSON format. (Verified.)
- `src/wanctl/logging_utils.py:199-214` — main `RotatingFileHandler` is `setLevel(logging.INFO)`; debug `RotatingFileHandler` is `setLevel(logging.DEBUG)` and only added when `debug=True`. Console handler is upgraded to DEBUG only when `debug=True`.
- `configs/spectrum.yaml:152-154` — `main_log: /var/log/wanctl/spectrum.log` and `debug_log: /var/log/wanctl/spectrum_debug.log`.
- `src/wanctl/health_check.py:101` — `stats = profiler.stats(total_label)` reads the same in-process profiler that `record_cycle_profiling` writes.
- `scripts/profiling_collector.py:38-46` — regex `(\w+): (\d+\.\d+)ms` matches per-`PerfTimer.__exit__` text DEBUG lines (`label: X.Xms`) but does NOT match the `"Cycle timing"` message (no `cycle_total` in the message string) and does NOT match JSON lines. Sub-timer coverage from the text DEBUG remains useful; cycle-total coverage requires a different path.

The rest of this document is built around those corrected facts.

## Summary

This is a measurement + decision phase. The profiling stack itself is fine — `OperationProfiler`, `PerfTimer`, `record_cycle_profiling`, the `--profile` flag, the `/health cycle_budget` block, and `scripts/analyze_profiling.py` all exist and work. What this phase needs to lock down is the **data path**: how do we get a 1h sample of `autorate_cycle_total` plus the 4 PERF-02 hot-path category labels into a committed artifact under D-05 (no `src/` changes), and how do we compute a falsifiable D-03 verdict over those samples.

**Primary recommendation: Option A — capture under `WANCTL_LOG_FORMAT=json` + `--profile --debug` via systemd drop-in; analyze with a small offline JSON parser; `/health` polled at low cadence as an independent INFO-only sanity track.** Rationale below.

The headline trade is: Option A needs one small JSON-aware offline parser (zero `src/` risk, sits in `scripts/`), but yields the full {cycle_total + 15 subsystem labels} per cycle, lets the existing `OperationProfiler.stats()` math run client-side, and survives all three of the broken assumptions cleanly. Option B (full-window `/health` poll) avoids the parser but is structurally limited by `/health`'s rolling 100-sample window and cannot bound observer-effect any better than Option A. Option C is `src/` editing and is rejected under D-05.

## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** Profile **Spectrum only** (`1.45.0`, v1.44 `besteffort wash` CAKE topology). ATT/DSL is out of scope.
- **D-02:** Capture **~1h organic household traffic** (steady-state budget) **plus a short driven RRUL/upload segment** using the Phase 213 harness, to exercise the change-gated `autorate_router_write_*` path.
- **D-03:** Judge against **absolute health bars**: (a) `autorate_cycle_total` headroom vs the 50ms cycle budget, and (b) structural dominance test — **no single subsystem >40% of `autorate_cycle_total`**.
- **D-04:** **Drop the ±15% / ±25%-vs-v1.39 clauses.** Archived v1.0/v1.9 artifacts may be cited as **informational context only**, never as a pass/fail gate. Close-condition partition: **no-action** if cycle_total has comfortable 50ms headroom AND no subsystem >40%; **promote** if either a subsystem exceeds 40% or total headroom is thin.
- **D-05:** Enable `--profile` via a **systemd override drop-in**, not a permanent edit. Clean enable → ≥1h capture → revert drop-in → restart. **No `src/` changes.**
- **D-06:** Commit the artifact to `.planning/perf/v1.45-baseline-spectrum-<date>.profile.json` (create `.planning/perf/`) plus a **1-page summary** stating the close-condition outcome and the deprioritize/promote decision (PERF-03).
- **D-07:** **Create the missing `docs/PROFILING.md`** runbook (enable/capture/revert/analyze, repeatable).

### Claude's Discretion
- Exact driven-segment duration (recommended below as the Phase 213 default; planner may tune).
- The analysis script invocation (the new offline JSON parser; existing `scripts/analyze_profiling.py` is no longer load-bearing because cycle_total isn't in text DEBUG).
- Summary format.
- Whether to quantify the profiling observer-effect inline or as a noted caveat (this research downgrades to **documented caveat + optional cheap adjacent-window estimate**; see Q5).

### Deferred Ideas (OUT OF SCOPE)
- **Any actual optimization** (RTT-path restructuring, per-cycle metrics/logging allocation, router/transport cost reduction). If the data promotes the todo, that becomes a v1.46+ optimization phase.
- **ATT cycle-budget profile** — Spectrum-only per D-01.

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| PERF-01 | Close or promote the pending post-hotpath profiling todo by capturing ≥1h of current production cycle-budget data. | Capture mechanics (Q4) + artifact schema (Q1) — JSON-format DEBUG capture with the recommended data path. |
| PERF-02 | The profile identifies whether RTT measurement, CAKE stats, router communication, logging/metrics, or storage writes is the dominant hot-path cost. | Subsystem label→category map (Q2). 4 of 5 categories have direct hot-path labels; **storage writes has NO hot-path label** (deferred to background worker) and is attributed out-of-band via `wanctl-history --ingestion-rate --from <start> --to <end> --wan spectrum`. |
| PERF-03 | If cycle budget is healthy, performance work is explicitly deprioritized in favor of quality/tuning. | The 1-page summary (D-06) records the explicit decision against the D-03 bars, using the pre-data numeric headroom bar in Q5. |

## Capture & Analysis Data Path (recommended)

### Chosen option: A — JSON-format DEBUG capture + offline JSON parser

**Why A over B and C:**

- **vs C (in-process one-liner in `record_cycle_profiling`):** violates D-05 (no `src/` changes). Rejected on scope; not revisited.
- **vs B (full-window `/health` NDJSON poll):** B avoids a new parser but inherits two structural limits. (1) `/health._build_cycle_budget` (`health_check.py:101-151`) reads `profiler.stats(...)` over a deque of `max_samples=100` (`perf_profiler.py:91-101`). At 20Hz that is a ~5-second rolling window — every `/health` GET is a snapshot of the last 5s, not a 1h aggregate. To approximate a 1h aggregate from `/health` you'd average snapshot avgs, which is a sample-of-means, not a true sample distribution, and degrades p95/p99 fidelity. (2) `/health.cycle_budget.subsystems` enumerates 9 labels (`health_check.py:127-137`) and crucially **omits the router-write sub-labels** (`autorate_router_write_*`) that are needed to confirm the D-02 driven segment landed. Option A captures every cycle, all 16 labels (15 subsystems + cycle_total), in one file with no rolling-window loss.
- **Option A pros:** complete data, observer-effect bounded by capturing one extra short ON-vs-OFF pair if desired (cheap), `WANCTL_LOG_FORMAT=json` is an env switch already plumbed (`logging_utils.py:115`, `setup_logging` accepts it), JSONFormatter already preserves `extra=` keys verbatim (`logging_utils.py:91-96`), and no `src/` change.
- **Option A cons:** introduces one offline parser script (~50 lines) in `scripts/`; the existing `scripts/profiling_collector.py` / `scripts/analyze_profiling.py` are bypassed for the cycle-total path (they remain usable as a sub-timer text cross-check on the SAME log if we briefly run text-format first, but this is optional). One residual verification needed: confirm at capture-time that the JSON output actually contains `cycle_total_ms` (see Open Question 1 below — this is the one item the planner's Wave 0 must verify before committing to the full 1h window).

### Capture mechanics (locked)

**Drop-in path:** `/etc/systemd/system/wanctl@spectrum.service.d/override.conf`. The checked-in unit at `deploy/systemd/wanctl@.service` runs `ExecStart=/usr/bin/python3 /opt/wanctl/autorate_continuous.py --config /etc/wanctl/%i.yaml`. ExecStart is a single-value directive, so the override must clear it first.

**Drop-in content (verbatim, the planner can encode this as an acceptance shape):**

```ini
[Service]
Environment=WANCTL_LOG_FORMAT=json
ExecStart=
ExecStart=/usr/bin/python3 /opt/wanctl/autorate_continuous.py --config /etc/wanctl/spectrum.yaml --profile --debug
```

**Sequence:**

```bash
sudo systemctl edit wanctl@spectrum            # paste the drop-in above; saving writes override.conf
sudo systemctl daemon-reload
sudo systemctl restart wanctl@spectrum
# >= 1h window. Inside that window, run the D-02 driven segment from the dev VM (see Q6).
sudo systemctl revert wanctl@spectrum          # removes the drop-in
sudo systemctl daemon-reload
sudo systemctl restart wanctl@spectrum
# Verify: `systemctl cat wanctl@spectrum` shows base unit only; `ps -ef | grep autorate_continuous` has no --profile/--debug.
```

**Retrieval (Spectrum host → analysis workstation):** the DEBUG sink under `--debug` is `config.debug_log` (`logging_utils.py:209-214`). For Spectrum that is `/var/log/wanctl/spectrum_debug.log` (`configs/spectrum.yaml:154`). `RotatingFileHandler` defaults are `maxBytes=10_485_760` (10 MB), `backupCount=3` (`logging_utils.py:196-197,211`). At ~12 structured DEBUG records/cycle × 20Hz the JSON file rotates fast — pull the whole rotated set:

```bash
ssh <spectrum-host> "ls -la /var/log/wanctl/spectrum_debug.log*"
scp '<spectrum-host>:/var/log/wanctl/spectrum_debug.log*' .planning/perf/capture/
# Concatenate in chronological (oldest→newest) order before parsing. The handler writes:
#   spectrum_debug.log.3 -> .2 -> .1 -> .log (current).
cat .planning/perf/capture/spectrum_debug.log.3 \
    .planning/perf/capture/spectrum_debug.log.2 \
    .planning/perf/capture/spectrum_debug.log.1 \
    .planning/perf/capture/spectrum_debug.log \
  > .planning/perf/capture/spectrum_debug.ndjson
```

**Belt-and-braces (recommended):** also save `journalctl -u wanctl@spectrum --since "<start>" --until "<end>" -o cat > .planning/perf/capture/spectrum_journal.ndjson`. Journald carries the same DEBUG (console handler at DEBUG when `--debug` is on, `logging_utils.py:216`) and is immune to file rotation. Use the file as primary, journald as fallback if rotation cost a tail of the window.

The capture artifacts themselves (raw `spectrum_debug.log*`, journald dump, `/health` poll NDJSON if collected) **should not be committed** per the MEDIUM review finding — keep them under `.planning/perf/capture/` and `.gitignore` that directory; only the aggregate `.profile.json` and the summary are committed.

### Analysis (locked)

A new tiny script — call it `scripts/profiling_collector_json.py` (the planner picks the final name; this RESEARCH treats the name as illustrative) — reads NDJSON, filters records where `message == "Cycle timing"`, extracts `cycle_total_ms` and the `*_ms` extras, accumulates per-label sample lists, and emits the **same shape `profiling_collector.py --output json` already produces** so downstream tooling (analyze_profiling.py, jq, the summary template) stays compatible.

**Per-record JSON shape (exact, from JSONFormatter at `logging_utils.py:74-102` + `record_cycle_profiling` at `perf_profiler.py:287-294`):**

```json
{
  "timestamp": "2026-05-30T12:34:56.789Z",
  "level": "DEBUG",
  "logger": "cake_continuous_spectrum",
  "message": "Cycle timing",
  "cycle_total_ms": 14.2,
  "overrun": false,
  "rtt_measurement_ms": 8.1,
  "state_management_ms": 0.3,
  "router_communication_ms": 2.4,
  "signal_processing_ms": 0.5,
  "ewma_spike_ms": 0.1,
  "cake_stats_ms": 1.2,
  "congestion_assess_ms": 0.4,
  "irtt_observation_ms": 0.0,
  "logging_metrics_ms": 0.7,
  "router_apply_primary_ms": 0.0,
  "router_apply_pending_ms": 0.0,
  "router_write_download_ms": 0.0,
  "router_write_upload_ms": 0.0,
  "router_write_skipped_ms": 0.0,
  "router_write_fallback_ms": 0.0
}
```

Note the label transform at `perf_profiler.py:292`: `autorate_rtt_measurement` → `rtt_measurement_ms` (the `autorate_` prefix is stripped, `_ms` is appended). The parser must reconstruct the canonical `autorate_*` label for the committed artifact (to match the `profiling_collector.py --output json` schema and the canonical name space used in `/health` and elsewhere).

**Committed artifact shape (matches existing `profiling_collector.py --output json`, see `profiling_collector.py:51-80` for `calculate_statistics`):**

```json
{
  "autorate_cycle_total": {
    "count": 72000, "min_ms": 9.8, "p50_ms": 14.2, "avg_ms": 15.1,
    "max_ms": 61.3, "p95_ms": 22.0, "p99_ms": 28.4
  },
  "autorate_rtt_measurement": { "...": "..." },
  "autorate_router_communication": { "...": "..." },
  "autorate_cake_stats": { "...": "..." },
  "autorate_logging_metrics": { "...": "..." },
  "autorate_router_write_download": { "...": "..." },
  "autorate_router_write_upload": { "...": "..." }
}
```

Stats math: identical to `OperationProfiler.stats()` at `perf_profiler.py:132-153` (sorted percentiles by index). The parser can either reuse that class directly (import from `wanctl.perf_profiler`) or reimplement the four lines — either is fine; the import path is cleaner.

**Analysis commands (the data path the planner encodes as acceptance criteria):**

```bash
# 1. Concatenate the captured rotated files into a single NDJSON stream (see Retrieval above).

# 2. Produce the committed D-06 artifact:
.venv/bin/python scripts/profiling_collector_json.py \
    .planning/perf/capture/spectrum_debug.ndjson \
    --output json \
  > .planning/perf/v1.45-baseline-spectrum-$(date +%Y%m%d).profile.json

# 3. Storage-write attribution (out-of-band; PERF-02 fifth category). Explicit window required
#    (default is last hour — `history.py:616-624` `_resolve_time_range`):
.venv/bin/python -m wanctl.history \
    --ingestion-rate --wan spectrum \
    --from <ISO start> --to <ISO end> --json \
  > .planning/perf/v1.45-baseline-spectrum-$(date +%Y%m%d).ingestion.json

# 4. PERF-02 dominance verdict + D-03 headroom verdict.
#    The existing scripts/analyze_profiling.py operates on log text not on the JSON artifact,
#    so the summary computation is done either inline in the new parser (preferred — single
#    pass, emits both the artifact and a "summary" sub-object) or with a small jq pipeline
#    over the committed artifact. Either way, the math is:
#      utilization_pct       = cycle_total.avg_ms / 50 * 100
#      headroom_avg_ms       = 50 - cycle_total.avg_ms
#      p99_overrun           = cycle_total.p99_ms > 50
#      category_pct[cat]     = category_total_avg_ms / cycle_total.avg_ms * 100
#      dominance_verdict     = max(category_pct.values()) <= 40
```

### Acceptance criteria the planner can encode (falsifiable)

1. Drop-in present during capture: `systemctl cat wanctl@spectrum` contains both `Environment=WANCTL_LOG_FORMAT=json` and an `ExecStart=` line ending `--profile --debug`.
2. Drop-in absent post-phase: `systemctl cat wanctl@spectrum` matches the checked-in base unit exactly; running ExecStart contains neither `--profile` nor `--debug`.
3. Capture contains `"message":"Cycle timing"` records with a `cycle_total_ms` field. **Concrete check (replaces the broken `grep -c "autorate_cycle_total:" >= 60000`):**
   ```bash
   jq -c 'select(.message == "Cycle timing") | .cycle_total_ms' \
       .planning/perf/capture/spectrum_debug.ndjson | wc -l
   # Expected: >= 60000  (1h × 20Hz × 0.83 safety margin for rotation/restart tail)
   ```
4. Committed artifact JSON contains keys for `autorate_cycle_total` and at least the 4 PERF-02 hot-path categories (`autorate_rtt_measurement`, `autorate_cake_stats`, `autorate_router_communication`, `autorate_logging_metrics`), each with `count`, `avg_ms`, `p95_ms`, `p99_ms`. `count >= 60000`.
5. **Driven segment landed:** `autorate_router_write_download.count > 0` OR `autorate_router_write_upload.count > 0` in the artifact (these labels are change-gated; presence proves the flent run exercised the path inside the window).
6. **D-03 verdict computed as a boolean pair** (numeric headroom bar — see Q5):
   - `passes_headroom = cycle_total.avg_ms < 40.0 AND cycle_total.p99_ms < 50.0` (i.e. avg utilization < 80% per existing `/health` warning threshold, and no p99 overrun)
   - `passes_dominance = max(category_pct.values()) < 40.0`
   - `no_action` if both true; `promote` otherwise.
7. Storage write-rate JSON has explicit window matching the capture window (not the default last-hour) and is reported as a non-hot-path note in the summary (no claim about % of cycle_total).
8. `docs/PROFILING.md` exists; the runbook references this data path (JSON capture, parser, both numeric bars).

### How PERF-02 subsystem dominance is computed

Roll the 15 subsystem labels into the 5 PERF-02 categories using the map below (Q2). For each category, `category_total_avg_ms = sum(label.avg_ms for label in category)`. Then `category_pct = category_total_avg_ms / cycle_total.avg_ms * 100`. The dominance test is `max(category_pct.values()) < 40.0`.

**Critical sub-rule (avoid double-counting):** `autorate_router_communication` is the parent timer wrapping the router subsystem; `autorate_router_apply_*` and `autorate_router_write_*` are sub-timers measured inside it (the `with PerfTimer("autorate_router_communication", ...)` block wraps the router-apply work — see the cluster at `src/wanctl/wan_controller.py:2444-2449` showing those keys originate inside the router pass). For the dominance test use the **parent** (`autorate_router_communication`) only. Sub-timers contribute to per-cycle attribution narrative but NOT to the category sum. (This was already correct in the previous research; preserving.)

**Storage writes (5th PERF-02 category) has no hot-path label by design** (`DeferredIOWorker`, `autorate_continuous.py` deferred I/O). Report `wanctl-history --ingestion-rate --from/--to --wan spectrum` rows-per-second as a separate non-hot-path note in the summary. State explicitly that storage % of cycle_total is undefined by design.

### How D-03 absolute headroom is bounded (pre-data numeric bar)

Per the MEDIUM review finding, "comfortable headroom" is not falsifiable without a pre-data bar. Concrete bar:

- `passes_headroom = cycle_total.avg_ms < 40.0` (i.e. avg utilization < 80% of the 50ms budget — matches the existing `/health cycle_budget` warning threshold at `health_check.py:84,109`)
- **AND** `cycle_total.p99_ms < 50.0` (no p99 overruns)

Rationale: 80% utilization is already the system's own self-reported "warning" threshold (`warning_threshold_pct: 80.0`, default in `_build_cycle_budget`). Using it here aligns the phase verdict with the daemon's runtime self-assessment. The p99-under-budget criterion catches "avg is fine but tail eats the headroom" cases, which a single avg bar misses on a 20Hz loop where p99 corresponds to ~1 cycle every ~5 seconds. Both bars must hold for `no-action`; either failing means `promote`.

### How observer-effect is bounded

Cross-checking `/health.cycle_time_ms.avg` against DEBUG-logged `cycle_total_ms` **within the same window is invalid** (both read `profiler.stats("autorate_cycle_total")` — `health_check.py:101`). Two acceptable shapes; **recommend (a), accept (b) as fallback:**

**(a) Adjacent-window ON/OFF estimate (cheap, ~10 min total).** Outside the main 1h window, run two short steady-state windows ~5 min each, on the same evening, no driven load:

- Window X: drop-in with `--profile --debug` and `WANCTL_LOG_FORMAT=json`. Poll `/health` once per minute for 5 minutes; record `cycle_budget.cycle_time_ms.avg`.
- Window Y: revert; the daemon runs at INFO with no `--debug`, no `--profile`. Poll `/health` once per minute for 5 minutes; record `cycle_budget.cycle_time_ms.avg`.
- `observer_effect_ms ≈ avg(window_X) - avg(window_Y)`. Report in the summary as `--debug` overhead under production conditions.

This is honest: `/health` reads the same profiler that the daemon uses internally, so under both modes it reports the actual cycle_total the daemon is experiencing. The ON window includes the DEBUG-emission cost; the OFF window does not. The two `/health` reads are from different profiler states, so the comparison is real.

**(b) Documented caveat (fallback if (a) is operationally inconvenient).** State in the summary: "Captured under `--debug`; per-cycle DEBUG JSON emission (`~12 records/cycle × 20Hz ≈ 240 records/sec`) adds I/O cost absent in steady-state INFO operation. The DEBUG-derived `cycle_total` is an **upper bound** on real cost. Read the headroom verdict accordingly — a DEBUG-inflated number that still has comfortable headroom is a **stronger** no-action signal." This is the previous research's intended caveat; it stands on its own without the invalid cross-check.

The planner should default to (a) — it's a 10-min extension to the operational schedule and turns a caveat into a number. If the operator can't easily run the adjacent windows, (b) is sufficient for D-03's structural framing.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Per-cycle subsystem timing | Control loop (`wan_controller.run_cycle`) | — | `PerfTimer` wraps each `_run_*` subsystem; `_record_profiling` populates the 15-label dict and delegates to `record_cycle_profiling`. `wan_controller.py:2408-2462` |
| Profiling aggregation + periodic report | Profiler module (`perf_profiler.OperationProfiler`) | — | Bounded deque (maxlen 100) per label; `report()` emits aggregate at INFO every 1200 cycles (~60s). `perf_profiler.py:91-101,166-195,231,296-300` |
| `--profile` flag wiring | Daemon entry (`autorate_continuous`) | — | `--profile` → `_configure_controller_flags` → `enable_profiling(True)` per WAN. (Already known to work — drives `report()` cadence; NOT the path for analyzer-parseable data.) |
| Structured per-cycle log emission | Profiler module | Logging module | `record_cycle_profiling` builds the `extra` dict (gated on `isEnabledFor(DEBUG)`) and calls `logger.debug("Cycle timing", extra=extra)`. **JSONFormatter preserves; text formatter drops.** `perf_profiler.py:287-294`, `logging_utils.py:74-134` |
| Log format selection | Logging module (env-controlled) | — | `WANCTL_LOG_FORMAT=json` switches formatter for all handlers in the unit. `logging_utils.py:115,185,193` |
| Cycle-budget telemetry surface | Health server (`health_check`) | — | `_build_cycle_budget` reads the same in-process profiler deques. Independent of log level. Rolling ~5s window per snapshot (deque maxlen 100 × 50ms). `health_check.py:78-151` |
| Subsystem→category dominance + headroom verdict | Offline analysis script (`scripts/`) | — | New small JSON parser (Option A) computes per-category roll-up, D-03 verdict pair, and emits the committed artifact. |
| Storage-write attribution (non-hot-path) | `wanctl-history --ingestion-rate` | — | Hot-path has no storage timer (deferred I/O). `history.py:651-715`. Requires explicit `--from`/`--to` to match the capture window (`history.py:616-624`). |
| Load driving (driven segment) | External harness (dev VM) | — | `scripts/phase213-baseline-capture.sh` → `scripts/phase191-flent-capture.sh`; no production mutation. |

## Standard Stack

This phase consumes existing components and adds one offline parser. No new runtime instrumentation.

### Core (existing, consumed as-is)
| Component | File:Line | Purpose |
|-----------|-----------|---------|
| `OperationProfiler` | `src/wanctl/perf_profiler.py:66-195` | Bounded-deque per-label sample store; `stats()` returns count/min/max/avg/p95/p99; `report()` emits aggregate text. |
| `PerfTimer` | `src/wanctl/perf_profiler.py:25-63` | Context manager; emits `label: X.Xms` at DEBUG when logger is DEBUG-enabled. Drives sub-timer text DEBUG (still useful as a side cross-check). |
| `record_cycle_profiling` | `src/wanctl/perf_profiler.py:234-302` | Per-cycle recorder; logs `"Cycle timing"` with `extra={"cycle_total_ms": ..., "<subsystem>_ms": ...}`. **Only JSON formatter preserves the extras.** |
| `_record_profiling` (autorate) | `src/wanctl/wan_controller.py:2408-2462` | Builds the 15-label timings dict and delegates. |
| `JSONFormatter` | `src/wanctl/logging_utils.py:17-102` | Walks `record.__dict__`, includes every non-internal key. **Preserves `extra=` fields verbatim — verified.** |
| `setup_logging` | `src/wanctl/logging_utils.py:137-223` | Main file handler INFO-level; debug file handler DEBUG-level (only when `debug=True`); console upgraded to DEBUG when `debug=True`. |
| `_build_cycle_budget` | `src/wanctl/health_check.py:78-151` | `/health` `cycle_budget` block; rolling ~5s window per snapshot; 9-subsystem breakdown (omits router-write sub-labels). |
| `wanctl-history --ingestion-rate` | `src/wanctl/history.py:651-715` (with `--from/--to` plumbing at `:616-624`) | Per-WAN SQLite write-rate; required for PERF-02 storage attribution; **must pass explicit window**. |

### New (this phase, no `src/` change)
| Component | Location | Purpose |
|-----------|----------|---------|
| Offline JSON parser | `scripts/profiling_collector_json.py` (illustrative name) | Reads NDJSON; filters `"Cycle timing"` records; reconstructs canonical `autorate_*` labels; computes count/min/p50/avg/max/p95/p99 per label; emits the existing `profiling_collector.py --output json` schema. |
| `.profile.json` artifact | `.planning/perf/v1.45-baseline-spectrum-<date>.profile.json` | Committed aggregate (D-06). |
| 1-page summary | `.planning/perf/217-cycle-budget-summary.md` | D-06 summary with D-03 verdict + close/promote decision (PERF-03). |
| Runbook | `docs/PROFILING.md` | D-07 enable/capture/revert/analyze, references this data path. |

### Supporting (load driving — unchanged from previous research)
| Component | File | Purpose |
|-----------|------|---------|
| `phase213-baseline-capture.sh` | `scripts/` | Orchestrates browse/tcp_upload/tcp_download/rrul/tcp_12down baseline suite with paired `/health` NDJSON pollers. Default `--flent-duration 60`. |
| `phase191-flent-capture.sh` | `scripts/` | Underlying flent runner: `flent <TEST> --local-bind <ip> -H <host> -l <dur> -t <title> -D <dir> -o <plot>`. |

### Alternatives considered (and not chosen)
| Instead of | Could Use | Why not |
|------------|-----------|---------|
| JSON-format DEBUG capture (A) | Full-window `/health` NDJSON poll (B) | Rolling 5s window; omits router-write sub-labels (`autorate_router_write_*`) needed for D-02 verification; p95/p99 fidelity degrades vs per-cycle samples. Keep `/health` polling as a low-cadence INFO-only sanity track instead. |
| Offline parser (A) | One-line `logger.debug(f"... {total_ms:.1f}ms")` in `record_cycle_profiling` (C) | Violates D-05 (no `src/` changes). Rejected on scope. |
| Concatenated rotated files | Parse `journalctl -u wanctl@spectrum` only | Both work; file path is the primary because the raw file is preserved across host restarts and is the existing tool contract. Journald is the rotation-safe fallback if rotation evicted a tail. |

## Architecture Patterns

### Data Flow (capture → artifact → decision) — corrected

```
[dev VM] flent rrul / tcp_upload  ──drives load──▶  Spectrum link (driven segment inside the 1h window, D-02)
                                                            │
organic household traffic  ─────────────────────────▶  Spectrum link (steady-state, D-02)
                                                            │
                                                wanctl@spectrum (drop-in: --profile --debug, WANCTL_LOG_FORMAT=json)
                                                            │
                                  run_cycle() PerfTimer per subsystem (always measures into profiler deques)
                                                            │
                              ┌─────────────────────────────┼──────────────────────────────────┐
                              ▼                              ▼                                  ▼
              JSONFormatter on debug handler        report() at INFO every ~60s        /health (low-cadence poll,
              => /var/log/wanctl/spectrum_debug.log  => /var/log/wanctl/spectrum.log    INFO-only sanity track,
              (one structured "Cycle timing" record  (human aggregate; not parseable     rolling ~5s window)
               per cycle, with cycle_total_ms +       for cycle_total)
               15 subsystem *_ms extras)
                              │
                              ▼
              concatenated NDJSON  +  optional journald dump
                              │
              scripts/profiling_collector_json.py --output json
              ──▶  .planning/perf/v1.45-baseline-spectrum-<date>.profile.json   (D-06 committed)
                              │
              category roll-up + D-03 verdict (avg_ms<40 AND p99_ms<50; max category %<40)
              + wanctl-history --ingestion-rate --from <S> --to <E> --wan spectrum (PERF-02 storage)
                              │
              .planning/perf/217-cycle-budget-summary.md  (1-page, PERF-03 explicit decision)
                              │
              todo close (no-action)  |  todo promote → v1.46+ optimization phase
```

### Pattern 1: Transient systemd drop-in (D-05)
**What:** Add `--profile --debug` and `Environment=WANCTL_LOG_FORMAT=json` to `ExecStart` via an override that does NOT touch the checked-in unit, then revert.
**Why drop-in (not a permanent edit):** D-05 requires zero permanent flag changes; this is the only mechanism that touches the running daemon without modifying tracked `deploy/systemd/wanctl@.service` content.
**Revert verification gate (the single most important safety check):** post-phase, `systemctl cat wanctl@spectrum` must show the base unit only (no drop-in override block); `ps -ef | grep autorate_continuous` must show neither `--profile` nor `--debug` in the running command line. This is the "did the live mutation get fully undone" gate.

### Pattern 2: Independent triangulation (corrected)
**What:** Two data sources for the dominance/headroom verdict — the per-cycle JSON DEBUG capture (primary, full distribution) and the low-cadence `/health.cycle_budget` poll (secondary, rolling 5s snapshots).
**Limitation acknowledged:** `/health` and the JSON capture share an in-process profiler — they will agree within the same window, which means `/health` is NOT a clean observer-effect cross-check. It IS a useful sanity track to confirm the daemon is alive, the cycle_budget block has data, and the avg/p95/p99 numbers from the parser line up with what the daemon itself reports. Treat it as that, not as a second independent measurement.

### Anti-patterns to avoid
- **Running the regex collector against the new JSON capture.** `scripts/profiling_collector.py:38-46` regex `(\w+): (\d+\.\d+)ms` will match nothing inside JSON lines. Use the new JSON-aware parser.
- **Capturing into `/var/log/wanctl/spectrum.log`** under the assumption it contains DEBUG. It doesn't — main handler is INFO-only.
- **Cross-checking observer-effect with `/health` against DEBUG-logged cycle_total in the same window.** Same profiler; delta ~0 by construction.
- **Editing the checked-in `deploy/systemd/wanctl@.service`** instead of a drop-in. Violates D-05.
- **Committing raw `spectrum_debug.log*` to the repo.** Bloats history and risks operator-detail leakage. Commit only the aggregate `.profile.json`, summary, and (optionally) sanitized excerpts.
- **Calling `wanctl-history --ingestion-rate` without `--from`/`--to`.** Defaults to last hour (`history.py:616-624`); if the analysis runs hours after the capture, attribution misaligns with the window.
- **Treating "RTT was 98% in v1.0" as a current target.** v1.0 was the 2-second interval era. Use the archived numbers as informational context only (D-04).

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Per-cycle timing instrumentation | New `PerfTimer` wrappers | Existing `PerfTimer`/`OperationProfiler` in `run_cycle` | Already wired; phase forbids `src/` changes. |
| Statistical math (percentiles) | Custom sort/index routine | `OperationProfiler.stats()` imported into the offline parser, or copy the 4-line block from `perf_profiler.py:132-153` | Already battle-tested; reuse keeps the artifact schema identical to `scripts/profiling_collector.py`'s. |
| Load generation | Custom traffic generator | `scripts/phase213-baseline-capture.sh` (60s rrul + 60s tcp_upload) | Proven, no-mutation, dev-VM-bound; Phase 213 validated it on Spectrum. |
| Storage-write rate | Disk-watching glue | `wanctl-history --ingestion-rate --from --to --wan spectrum` | Purpose-built per-metric write-rate; matches PERF-02 framing. |
| Log retrieval | Tailing while capturing | `scp` the rotated set + journald dump post-window | Capturing in flight risks log handler contention; offline retrieval is clean. |

**Key insight:** The new build surface is **one ~50-line offline JSON parser + the artifact/summary/runbook docs**. Nothing in `src/` changes. The phase's deliverables are 100% in `scripts/`, `.planning/perf/`, and `docs/`.

## Question-by-Question Findings

### Q1 — Profiler output schema (corrected)
The committed `.profile.json` schema mirrors the existing `scripts/profiling_collector.py --output json` output (`profiling_collector.py:51-80`, `calculate_statistics`):

```json
{
  "<autorate_label>": {
    "count": <int>,
    "min_ms": <float>,
    "p50_ms": <float>,
    "avg_ms": <float>,
    "max_ms": <float>,
    "p95_ms": <float>,
    "p99_ms": <float>
  },
  ...
}
```

Source is the new JSON parser, not the regex collector — but the schema is intentionally identical so downstream consumers (jq pipelines, summary template) don't have to branch on source.

**Label space:** the parser must reconstruct canonical `autorate_*` labels from the JSON capture. The transform at `perf_profiler.py:290-293` strips `autorate_` and appends `_ms` for the `extra` dict; the parser inverts it (`rtt_measurement_ms` → `autorate_rtt_measurement`). The `cycle_total_ms` field maps to `autorate_cycle_total`.

### Q2 — Canonical subsystem label set → PERF-02 category map (unchanged from previous, preserved)

| PERF-02 category | Hot-path label(s) | File:Line |
|------------------|-------------------|-----------|
| RTT measurement | `autorate_rtt_measurement` | `wan_controller.py:2435` |
| CAKE stats | `autorate_cake_stats` | `wan_controller.py:2440` |
| Router communication | `autorate_router_communication` (parent; use for dominance), `autorate_router_apply_*`, `autorate_router_write_*` (drill-down only) | `wan_controller.py:2437,2444-2449` |
| Logging / metrics | `autorate_logging_metrics` | `wan_controller.py:2443` |
| **Storage writes** | **(no hot-path label — deferred to `DeferredIOWorker`)** | — |

Other labels counted in `cycle_total` but outside PERF-02: `autorate_state_management`, `autorate_signal_processing`, `autorate_ewma_spike`, `autorate_congestion_assess`, `autorate_irtt_observation`. Report them in the artifact (full label space) but exclude from the 4-category dominance roll-up.

**Gap (PERF-02 fifth category):** confirmed there is no `autorate_storage_*` label. Storage writes are attributed via `wanctl-history --ingestion-rate --from <S> --to <E> --wan spectrum` and reported as rows-per-second over the capture window, separately from the cycle_total roll-up. **No claim about storage % of cycle_total** — that number does not exist by design.

**Double-counting note (preserved):** sub-timers (`autorate_router_apply_*`, `autorate_router_write_*`) live inside the `autorate_router_communication` parent timer. The dominance test sums the **parent only**; sub-timers contribute to per-cycle narrative drill-down but NOT to the category total. Same rule still applies under the JSON capture.

### Q3 — Analysis invocation (revised)
Three commands (one new, two existing — locked in the recommended data path above):

```bash
# 1. New JSON parser → committed artifact
.venv/bin/python scripts/profiling_collector_json.py \
    .planning/perf/capture/spectrum_debug.ndjson \
    --output json \
  > .planning/perf/v1.45-baseline-spectrum-$(date +%Y%m%d).profile.json

# 2. Storage attribution (existing tool; explicit window required)
.venv/bin/python -m wanctl.history \
    --ingestion-rate --wan spectrum \
    --from <ISO start> --to <ISO end> --json \
  > .planning/perf/v1.45-baseline-spectrum-$(date +%Y%m%d).ingestion.json

# 3. Category roll-up + D-03 verdict (jq, or inline in the parser)
jq -n --slurpfile p .planning/perf/v1.45-baseline-spectrum-<date>.profile.json '
  def cat(labels): [labels[] as $l | $p[0][$l].avg_ms // 0] | add;
  ($p[0]["autorate_cycle_total"].avg_ms) as $total
  | ($p[0]["autorate_cycle_total"].p99_ms) as $p99
  | {
      cycle_total_avg_ms: $total,
      cycle_total_p99_ms: $p99,
      utilization_pct: ($total / 50 * 100),
      headroom_avg_ms: (50 - $total),
      passes_headroom: ($total < 40 and $p99 < 50),
      categories: {
        rtt_measurement: cat(["autorate_rtt_measurement"]),
        cake_stats: cat(["autorate_cake_stats"]),
        router_communication: cat(["autorate_router_communication"]),
        logging_metrics: cat(["autorate_logging_metrics"])
      }
    }
  | .category_pct = (.categories | with_entries(.value = (.value / $total * 100)))
  | .max_category_pct = (.category_pct | [.[]] | max)
  | .passes_dominance = (.max_category_pct < 40)
  | .verdict = (if .passes_headroom and .passes_dominance then "no_action" else "promote" end)
'
```

The existing `scripts/analyze_profiling.py` is **not load-bearing** under Option A (it parses log text, not JSON, and depends on the same broken regex for cycle_total). It MAY be invoked against an additional brief text-format DEBUG capture if the planner wants sub-timer text-cross-check confidence, but this is optional and not required for D-06.

### Q4 — Capture mechanics & safety (corrected)
- `--profile` parsing: `src/wanctl/autorate_continuous.py:295` (CLI), `:494` (apply); enables `report()` cadence (`perf_profiler.py:296-300`). It does NOT enable the per-cycle DEBUG log emission — that requires `--debug`.
- `--debug`: routes through `setup_logging(..., debug=True)`; adds the debug file handler at DEBUG level (`logging_utils.py:209-214`) and upgrades the console handler to DEBUG (`logging_utils.py:216`).
- `Environment=WANCTL_LOG_FORMAT=json`: read by `get_log_format()` (`logging_utils.py:105-119`); flows into `_create_formatter` (`logging_utils.py:122-134`); applied to ALL handlers (`logging_utils.py:185,193,200-214`). So under the drop-in, both `spectrum.log` (INFO+) and `spectrum_debug.log` (DEBUG+) become JSON-line files for the window.
- Drop-in path: `/etc/systemd/system/wanctl@spectrum.service.d/override.conf`. The drop-in's `ExecStart=` must be cleared then re-set (single-value directive). The literal value substitutes `spectrum` for `%i` (the override is per-instance).
- Sequence: `systemctl edit` → `daemon-reload` → `restart` → ≥1h capture (driven segment INSIDE the window) → `systemctl revert wanctl@spectrum` → `daemon-reload` → `restart`. Revert removes the override file and restores the base unit (`man systemd.unit` revert semantics).
- **Watchdog interaction:** the unit has `WatchdogSec=30s` and `Restart=on-failure` (`deploy/systemd/wanctl@.service`). DEBUG-emission cost is strictly additive I/O. On the production disk it's almost certainly fine, but if it ever stalled the loop past 30s the watchdog would restart — that would corrupt the capture window. Monitor `journalctl -u wanctl@spectrum -f` for overrun warnings and unit restarts during the window. If restarts happen, drop `--debug` (keep `--profile` and JSON format; lose per-cycle samples; fall back to Option B for that attempt) and re-plan.
- **Memory:** unit has `MemoryHigh=512M`/`MemoryMax=640M`. JSON emission buffers are bounded — not a real concern, but noted.
- **CPU:** `CPUAffinity=1-2` is unchanged by the drop-in.

### Q5 — Observer-effect (corrected)
- What runs regardless of flags: `PerfTimer.__enter__/__exit__` (two `perf_counter()` calls) and `profiler.record()` into deques. The MEASUREMENT itself is always on; only the LOG EMISSION is gated.
- What `--profile` adds: one `profiler.report()` INFO log every ~60s. Negligible.
- What `--debug` adds (the observer-effect):
  1. `PerfTimer.__exit__` emits a formatted `label: X.Xms` DEBUG line per timer per cycle (~11 timer contexts × 20Hz ≈ 220 lines/sec). Same under JSON capture, just as JSON rather than plain text.
  2. `record_cycle_profiling` builds the `extra` dict (~16 dict insertions + `round()` per cycle) and calls `logger.debug("Cycle timing", extra=extra)` once per cycle (~20 lines/sec).
- Under JSON formatter: same line count, slightly higher CPU per line (JSON serialization vs string format). Strictly additive, absent in steady-state production.
- **Bound:** the previous research's "this is an upper bound" framing is correct; only the cross-check method was broken. The corrected observer-effect protocol is the adjacent-window ON/OFF estimate described in "How observer-effect is bounded" above. If skipped, use the documented caveat — D-03 is structural enough that the caveat doesn't change the verdict shape (an upper-bound `cycle_total` that still passes is a strong pass).

### Q6 — Driven segment (D-02) — unchanged from previous
The driven segment exists because `autorate_router_write_*` only fires on rate change (flash-wear guard at `wan_controller.py` `rates_changed`-gated block). A quiet household leaves those labels at zero counts. To force sustained rate changes:

```bash
# From the dev VM, inside the 1h capture window:
scripts/phase213-baseline-capture.sh --host dallas --flent-duration 60 --tests tcp_upload,rrul --wans spectrum
```

Phase 213 used `flent_duration=60`, netperf host `dallas`, Spectrum dev bind `10.10.110.226`, and saw Spectrum upload pegged at ceiling for ~81% of `tcp_upload` samples — confirming `rrul`/`tcp_upload` reliably saturate and provoke control activity. **Acceptance:** after capture, the artifact must have `autorate_router_write_download.count > 0` OR `autorate_router_write_upload.count > 0`. If both are zero, the driven segment fell outside the window or the flent run didn't saturate — investigate before declaring the capture valid.

### Q7 — Runbook content (D-07) — unchanged framing, corrected commands
`docs/PROFILING.md` does not exist (only `docs/archive/PROFILING.md` does). House style: H1 title, short intro, `## Section` headers, fenced `bash` blocks, "Production Standard / Operational Guardrails" framing (per `docs/PERFORMANCE.md` and `docs/TESTING.md`). Required sections:

1. **Pre-flight.** Check service is running, healthy, no existing drop-in. Confirm `flent` available on dev VM and Spectrum dev bind IP / netperf host still valid.
2. **Enable.** `systemctl edit wanctl@spectrum` with the exact drop-in (Environment=WANCTL_LOG_FORMAT=json + --profile --debug); daemon-reload + restart.
3. **Drive load.** Phase 213 harness invocation inside the window.
4. **Capture.** ≥1h. Tail `journalctl -u wanctl@spectrum` for overrun/restart warnings.
5. **Revert + verify.** `systemctl revert`; daemon-reload + restart; verify `systemctl cat` and `ps -ef` show no remnant.
6. **Retrieve.** scp the rotated `/var/log/wanctl/spectrum_debug.log*` set and journald dump.
7. **Analyze.** Concatenate; run the JSON parser; run `wanctl-history --ingestion-rate --from --to`; run the jq verdict pipeline.
8. **Interpret against D-03 bars.** Numeric headroom bar (`avg < 40ms AND p99 < 50ms`) AND dominance (`max category % < 40`). Both pass = no-action; either fails = promote.
9. **Caveat language.** Observer-effect notes; storage-write attribution caveat.

The runbook should explicitly supersede `docs/archive/PROFILING.md`'s parser commands (which point the regex collector at a `--profile`-only main log — broken assumption that this phase corrects).

### Q8 — Archived baselines (informational only, per D-04) — unchanged
- **v1.0** (`PROFILING-ANALYSIS.md`): cycle_total avg **41.1ms** (Spectrum) / **31.4ms** (other), RTT measurement **98%+** of cycle — but at the **2-second** interval, so 2.1% budget utilization, ~1959ms headroom. Citable as "RTT historically dominated; absolute RTT excellent." **Not comparable to 50ms budget.**
- **v1.9** (`47-RESEARCH.md`): pre-flagged the regex risk this phase is now correcting (`:213`); expected 50ms-era cycle_total of 30-45ms, RTT 20-40ms (dominant), router comms 0ms (skipped) or 15-25ms (on rate change). Most relevant prior expectation for "healthy at 50ms."

Use as context-setting in the summary; never as a pass/fail gate (D-04).

## Runtime State Inventory

Measurement phase, but capture mutates live service config transiently. The systemd drop-in IS runtime state that must be reverted.

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | None new written to datastores by this phase. The committed `.profile.json` is derived from logs, not a DB. Storage attribution reads existing per-WAN SQLite DB. | None |
| Live service config | **systemd drop-in** `/etc/systemd/system/wanctl@spectrum.service.d/override.conf` (added by `systemctl edit`, sets `WANCTL_LOG_FORMAT=json` + `--profile --debug` ExecStart). Live config NOT in git. | **MUST `systemctl revert wanctl@spectrum` + daemon-reload + restart** after capture (D-05). Verify drop-in dir is gone. |
| OS-registered state | The `wanctl@spectrum` unit instance itself (already registered; not modified — only overridden). | None beyond the revert. |
| Secrets / env vars | The drop-in adds `WANCTL_LOG_FORMAT=json` for the window. `EnvironmentFile=-/etc/wanctl/secrets` unchanged. | Reverted with the drop-in. |
| Build artifacts | None. No `src/` change, no reinstall. `/opt/wanctl` code untouched. | None |

**The canonical revert check (single most important safety gate):** post-phase, `systemctl cat wanctl@spectrum` shows base unit only (no `[Service]` override block); `ps -ef | grep autorate_continuous` shows neither `--profile` nor `--debug` nor `WANCTL_LOG_FORMAT=json`.

## Common Pitfalls

### Pitfall 1: Re-inheriting the regex / text-DEBUG assumption
**What goes wrong:** Capturing in text format under `--debug` and feeding `scripts/profiling_collector.py` produces per-subsystem stats but **zero `autorate_cycle_total` samples**. The D-03 headroom verdict is uncomputable from that artifact.
**Why it happens:** The regex `(\w+): (\d+\.\d+)ms` (`profiling_collector.py:38-46`) matches PerfTimer DEBUG lines (`label: X.Xms`), but `cycle_total` is logged only as a structured `extra` field on the `"Cycle timing"` message — never as text matching that pattern.
**How to avoid:** Use Option A (JSON capture + JSON parser). Don't re-use the regex collector for cycle_total.
**Warning sign:** `grep -c "autorate_cycle_total:" spectrum_debug.log` returns 0. Either capture format is wrong (text instead of JSON), or the wrong source file was pulled, or `--debug` wasn't actually applied.

### Pitfall 2: Pulling the wrong log file
**What goes wrong:** Retrieving `/var/log/wanctl/spectrum.log` and finding INFO-level lines only (no per-cycle records). Parsing produces empty results.
**Why it happens:** Main file handler is INFO-only (`logging_utils.py:200-201`); the debug file handler writes a separate file at `config.debug_log` (`logging_utils.py:209-214`) which for Spectrum is `/var/log/wanctl/spectrum_debug.log` (`configs/spectrum.yaml:154`).
**How to avoid:** Pull `/var/log/wanctl/spectrum_debug.log*` (with all rotated backups) and/or `journalctl -u wanctl@spectrum -o cat`. The runbook lists the exact `scp` invocation.

### Pitfall 3: Cross-checking observer-effect with `/health` in the same window
**What goes wrong:** Reporting `health.cycle_time_ms.avg - debug.cycle_total_avg ≈ 0` as the observer-effect figure.
**Why it happens:** `_build_cycle_budget` (`health_check.py:101`) reads `profiler.stats("autorate_cycle_total")` — the same in-process profiler the DEBUG records draw from. Same data source; delta by construction is ~0.
**How to avoid:** Use adjacent-window ON/OFF estimate, or downgrade to documented caveat. See "How observer-effect is bounded" above.

### Pitfall 4: Storage-window misalignment
**What goes wrong:** `wanctl-history --ingestion-rate --wan spectrum` runs later in the day and reports the last-hour write-rate that doesn't overlap the capture window.
**Why it happens:** `_resolve_time_range` (`history.py:616-624`) defaults to `now - 3600, now` when no `--from`/`--to` provided.
**How to avoid:** Always pass `--from <ISO> --to <ISO>` matching the capture window. Record the start/end timestamps when the drop-in goes in and out.

### Pitfall 5: Driven segment outside the capture window
**What goes wrong:** flent run happened before/after `--profile --debug` was active; router-write labels stay at count=0.
**How to avoid:** Run the flent harness AFTER `restart` and BEFORE `revert`. Verify post-capture by querying the artifact for non-zero `autorate_router_write_*.count`.

### Pitfall 6: Log rotation evicts the capture window
**What goes wrong:** At ~240 records/sec × ~150 bytes/record ≈ ~36 KB/sec, a 10MB file rolls every ~5 min. With `backupCount=3`, the rotation window is ~20 min — a 1h capture loses the first ~40 min of samples from the file unless backups are pulled.
**Why it happens:** `RotatingFileHandler(maxBytes=10_485_760, backupCount=3)` defaults (`logging_utils.py:196-197,211`).
**How to avoid:** Pull `/var/log/wanctl/spectrum_debug.log*` (with all rotated backups) and concatenate oldest→newest. Belt-and-braces: also save `journalctl -u wanctl@spectrum --since <start> --until <end> -o cat` — journald isn't rotation-bound by the file handler. The Wave 0 pre-flight should check the deployed rotation config (`max_bytes`/`backup_count`) — if it's been tuned away from the defaults, recompute expected file lifetime.

### Pitfall 7: Committing raw DEBUG capture to the repo
**What goes wrong:** `.planning/perf/spectrum_debug.ndjson` lands in git, leaking production operating details and bloating history.
**How to avoid:** `.gitignore` `.planning/perf/capture/` (or any equivalent capture subdir); commit only the aggregate `.profile.json`, the ingestion JSON, the summary, and the runbook. If any raw excerpt is needed in the summary, scrub it manually first.

## Code Examples

### Verify Spectrum log format before capture (Wave 0 gate)

```bash
# If the file starts with '{', it's already JSON-format (likely WANCTL_LOG_FORMAT=json is set somewhere).
# Either way, the drop-in's explicit Environment= sets JSON for the capture window.
ssh <spectrum-host> 'head -1 /var/log/wanctl/spectrum.log'
ssh <spectrum-host> 'systemctl show wanctl@spectrum -p Environment'
```

### Drop-in (paste into `systemctl edit wanctl@spectrum`)

```ini
[Service]
Environment=WANCTL_LOG_FORMAT=json
ExecStart=
ExecStart=/usr/bin/python3 /opt/wanctl/autorate_continuous.py --config /etc/wanctl/spectrum.yaml --profile --debug
```

### Post-capture revert verification

```bash
ssh <spectrum-host> 'systemctl cat wanctl@spectrum | grep -E "^Environment|^ExecStart"'
# Expected: matches checked-in deploy/systemd/wanctl@.service exactly; no drop-in lines.
ssh <spectrum-host> 'ps -ef | grep [a]utorate_continuous'
# Expected: no --profile, no --debug in the running command.
```

### Sanity check the capture before committing the artifact

```bash
# 1. Count "Cycle timing" records with cycle_total_ms present
jq -c 'select(.message == "Cycle timing") | .cycle_total_ms' \
    .planning/perf/capture/spectrum_debug.ndjson | wc -l
# Expected: >= 60000

# 2. Confirm driven-segment landing (non-zero router-write counts)
jq -c 'select(.message == "Cycle timing")
       | select((.router_write_download_ms // 0) > 0 or (.router_write_upload_ms // 0) > 0)' \
    .planning/perf/capture/spectrum_debug.ndjson | wc -l
# Expected: > 0
```

### Storage attribution (window-aligned)

```bash
.venv/bin/python -m wanctl.history --ingestion-rate --wan spectrum \
    --from 2026-05-30T18:00:00 --to 2026-05-30T19:00:00 --json \
  > .planning/perf/v1.45-baseline-spectrum-20260530.ingestion.json
```

## State of the Art

| Old approach | Current approach | When changed | Impact |
|--------------|------------------|--------------|--------|
| 2-second control interval, 2-4% budget | 50ms (20Hz), 60-80% budget expected | v1.0 → ~v1.9 | Profiling overhead matters; per-cycle DEBUG cost is real. |
| Per-cycle DEBUG/profiling payload always built | Gated behind DEBUG/profile (original todo's hot-path optimization) | mid-April 2026 | Enabling `--debug` re-activates the gated path → the observer-effect this phase must caveat. |
| `--ingestion-rate` not available | `wanctl-history --ingestion-rate` with `--from`/`--to` (v1.44 Phase 208) | v1.44 | Only viable storage-write attribution path; must use explicit window. |
| Regex-collector cycle_total assumption | JSON-format DEBUG + offline JSON parser (this phase) | v1.45 (Phase 217) | Cycle_total is in structured `extra=`, not in the message string; this is the corrected data path. |

**Deprecated / outdated:**
- `docs/archive/PROFILING.md` parser commands (point regex collector at a `--profile`-only main log; would return no cycle_total today regardless).
- v1.0 utilization/headroom percentages (2s interval; not comparable to 50ms).
- Previous 217-RESEARCH.md "primary recommendation: capture in text DEBUG, parse cycle_total with the existing collector" — superseded by Option A above.

## Validation Architecture

This is a measurement phase. "Validation" = the deliverables exist, are well-formed, and the decision is justified by the data. No new unit tests required (no `src/` change). Validation = artifact + procedure validation.

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (existing) — only relevant if a future phase wants a unit test on the new JSON parser; not required by this phase |
| Config file | `pyproject.toml` (existing) |
| Quick run command | `.venv/bin/pytest tests/test_perf_profiler.py -q` (sanity that the profiler core didn't change) |
| Full suite command | `make ci` |

### Phase Requirements → Validation Map
| Req | Behavior | Validation type | Check |
|-----|----------|-----------------|-------|
| PERF-01 | ≥1h Spectrum profile captured + committed; todo closed/promoted | Artifact existence + content | Committed `.planning/perf/v1.45-baseline-spectrum-<date>.profile.json` parses as JSON; `autorate_cycle_total.count >= 60000`; `autorate_router_write_download.count > 0` OR `autorate_router_write_upload.count > 0`; todo moved to `done/` (no-action) or a follow-on phase opened (promote). |
| PERF-02 | Dominant cost category identified | Analysis output | Summary computes `category_pct` for all 4 hot-path categories; storage write-rate reported separately from window-aligned `wanctl-history --ingestion-rate`; dominance boolean (`max(category_pct) < 40`) stated explicitly. |
| PERF-03 | Explicit deprioritize/promote decision | Summary content | 1-page summary states the D-03 verdict pair (`passes_headroom` boolean, `passes_dominance` boolean) and the explicit decision sentence. |

### Sampling rate
- **During capture:** tail `journalctl -u wanctl@spectrum -f` for `<wan>: Cycle overrun: ...` warnings (rate-limited at `perf_profiler.py:279-284`, fires 1st, 3rd, every 10th — any cluster of overruns is a sign the DEBUG cost is too heavy on the host). One unit restart during the window invalidates that segment of the capture.
- **Post-capture, pre-commit:** the two `jq` sanity checks above (cycle-timing record count, driven-segment landed).
- **Phase gate:** revert verified, artifact + summary + runbook committed, all acceptance criteria above pass, todo state transitioned.

### Wave 0 gaps (the planner must seed before the capture)
- Create `.planning/perf/` (does not exist).
- `.gitignore` `.planning/perf/capture/` for raw-log retrieval.
- Confirm deployed Spectrum `WANCTL_LOG_FORMAT` and rotation config (`max_bytes`, `backup_count`); the drop-in's explicit `Environment=` makes JSON capture deterministic regardless of host env, but knowing the rotation config sets correct retrieval expectations.
- Confirm `flent` available on the dev VM and Spectrum dev bind IP / netperf host `dallas` still valid (Phase 213 used 2.1.1 / Py 3.12.3).
- Decide: adjacent ON/OFF windows for observer-effect (recommended) or documented caveat only.
- Decide: parser script final name and location (`scripts/profiling_collector_json.py` recommended; planner picks).

## Environment Availability

| Dependency | Required by | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Root `systemctl edit/revert wanctl@spectrum` on Spectrum host | Drop-in (D-05) | ✓ (assumed; Phase 212/213 used the same host) | — | None — hard requirement. |
| `WANCTL_LOG_FORMAT` env switch | Option A capture | ✓ (`logging_utils.py:115`) | — | None — Option A depends on it. |
| `flent` on dev VM | Driven segment (D-02) | ✓ (Phase 213 used 2.1.1) | 2.1.1 / Py 3.12.3 | If absent: skip driven segment, router-write labels stay 0, summary notes the gap. Steady-state still captured. |
| netperf host `dallas` | flent target | ✓ (Phase 213) | — | Any reachable netperf server. |
| Spectrum `/health` on :9101 | Low-cadence sanity track; adjacent-window observer-effect estimate | ✓ (assumed; Phase 213 poller used `:9101`) | — | Skip; degrades observer-effect to caveat-only. |
| `wanctl-history` with `--from`/`--to` | PERF-02 storage attribution | ✓ (`history.py`, v1.44) | 1.45 | If unavailable: note storage as unmeasured. |
| `jq` (workstation) | Verdict computation | ✓ (standard) | any | Pure-Python replacement in the parser script. |
| `.venv` with project deps (workstation) | Run new JSON parser; run `wanctl.history` CLI | ✓ (repo) | — | — |

**Missing dependencies with no fallback:** root access to `systemctl edit/revert wanctl@spectrum` on the production host (D-05 hard requirement); `WANCTL_LOG_FORMAT` env handling in `setup_logging` (Option A foundation — confirmed present).

**Missing dependencies with fallback:** `flent` (degrades only the driven segment), `/health` (degrades observer-effect protocol).

## Assumptions Log

Every claim above is either verified against current source or explicitly tagged here as an assumption the planner should validate or the operator should confirm at capture time.

| # | Claim | Section | Risk if wrong |
|---|-------|---------|---------------|
| A1 | `WANCTL_LOG_FORMAT=json` set via systemd `Environment=` propagates through `setup_logging` to BOTH the main and debug handlers for the running daemon. | Capture mechanics; Q4 | [VERIFIED via `logging_utils.py:115,185,193,202,213` — same `formatter` instance is set on both file handlers and the console.] |
| A2 | JSONFormatter actually emits the `extra=` keys verbatim alongside the standard fields. | Per-record JSON shape | [VERIFIED via `logging_utils.py:91-96` — walks `record.__dict__` and includes every non-internal key. The list of excluded attrs at `:47-72` does NOT include `cycle_total_ms` or any `*_ms` extras.] |
| A3 | `record_cycle_profiling` is reached whenever `--debug` is on (no other guard prevents emission once DEBUG is enabled at the logger). | Per-record JSON shape | [VERIFIED via `perf_profiler.py:287` — single `if logger.isEnabledFor(logging.DEBUG):` gate; nothing else above it skips the structured log path.] |
| A4 | The drop-in's `ExecStart=` clear-then-set pattern works for this unit. | Capture mechanics | [VERIFIED — `ExecStart` is a single-value directive in systemd's grammar; the clear+set pattern is documented in `systemd.service(5)`. The previous research already exercised this assumption against archived `docs/PERFORMANCE.md` instructions.] |
| A5 | Spectrum host runs the `wanctl@spectrum` instance and allows root `systemctl edit/revert`. | Capture mechanics; Env | [ASSUMED — Phase 212/213 evidence; operator should confirm.] |
| A6 | flent dev-VM bind IP (`10.10.110.226`) and netperf host `dallas` from Phase 213 are still valid. | Q6 | [ASSUMED — re-confirm from current bind map at Wave 0.] |
| A7 | `/health` is served on `:9101` for Spectrum. | Observer-effect estimate; Validation | [ASSUMED — Phase 213 poller used `10.10.110.223:9101`; confirm host IP.] |
| A8 | Default rotation config (`max_bytes=10_485_760`, `backup_count=3`) is in effect on the deployed Spectrum host. | Pitfall 6 | [ASSUMED — Wave 0 should check `getattr(config, "max_bytes", ...)` on the running config. If the deployed config has larger values, the rotation window is wider; if smaller, narrower.] |
| A9 | DEBUG JSON emission cost on the production disk stays well under the 30s `WatchdogSec` threshold (i.e. no per-cycle stall pushes the loop past 30s). | Capture mechanics; Q4 | [ASSUMED — strictly additive I/O; historical evidence is the prior gated-DEBUG hot-path optimization was a few % cost on the loop, not a 30s stall. Operator should monitor `journalctl` during the window.] |
| A10 | `wanctl-history --ingestion-rate` `--from`/`--to` flags are wired the same as the rest of the time-range args. | Q3; PERF-02 storage | [VERIFIED via `history.py:616-624` — `_resolve_time_range` accepts `args.from_ts`/`args.to_ts`. The argparser includes them via the shared `--from`/`--to` flags (standard wanctl-history CLI shape).] |
| A11 | `OperationProfiler.stats()` math (`perf_profiler.py:132-153`) is appropriate to apply over the full 1h sample set, not just the 100-sample rolling deque. | Q1; analysis | [VERIFIED — the math itself is pure (sort + index percentile), bounded only by input list size; the offline parser feeds it the full 1h sample list, not the rolling deque. The deque only exists in the running daemon to bound memory.] |

## Open Questions

1. **Does the JSONFormatter output for a real `record_cycle_profiling` call actually contain `cycle_total_ms` (and the per-subsystem `*_ms` extras) as top-level JSON keys?** — RESOLVED by static analysis (A2 above), but the planner's Wave 0 MUST verify in production conditions before committing to the full 1h window. Concrete Wave 0 check: 5-minute pilot capture with the drop-in, then `jq 'select(.message == "Cycle timing") | keys' spectrum_debug.log | head -1` to inspect actual keys. If `cycle_total_ms` is missing for any reason (e.g. a logging filter strips it), abort and re-evaluate before the full window.
2. **Will the production disk sustain ~240 JSON records/sec at DEBUG without watchdog impact?** — UNKNOWN. Mitigation: the 5-minute pilot also serves as the disk-cost check (tail `journalctl -u wanctl@spectrum -f` for overrun warnings or restarts).
3. **Observer-effect estimate vs documented caveat — which does the operator prefer?** — DEFERRED to operator/planner; both shapes accepted (see "How observer-effect is bounded"). Recommendation: do the adjacent ON/OFF estimate (10 min total, cheap).
4. **Driven-segment duration tuning beyond the Phase 213 default (60s rrul + 60s tcp_upload)?** — DISCRETION (CONTEXT.md). The default populates the change-gated router-write labels; longer durations give richer router-write distributions but don't change the dominance verdict shape.

## Sources

### Primary (HIGH confidence — current code/config/docs in repo)
- `src/wanctl/perf_profiler.py:25-302` — PerfTimer, OperationProfiler (deque maxlen 100), `record_cycle_profiling` (`total_ms` computation, `"Cycle timing"` DEBUG with structured extras, `report()` cadence).
- `src/wanctl/logging_utils.py:17-223` — JSONFormatter (preserves all non-internal `extra=` keys), text formatter (drops extras), `get_log_format`, `setup_logging` (main handler INFO, debug handler DEBUG only when `debug=True`, formatter shared across handlers).
- `src/wanctl/wan_controller.py:2408-2462` — `_record_profiling`, 15-label timings dict, delegation to `record_cycle_profiling`.
- `src/wanctl/health_check.py:78-151` — `_build_cycle_budget` reads `profiler.stats("autorate_cycle_total")`; rolling-5s-window snapshots; 9-label subsystems breakdown (omits router-write sub-labels).
- `src/wanctl/autorate_continuous.py:295,494` — `--profile` flag wiring.
- `src/wanctl/history.py:599-715` — `--ingestion-rate`; `_resolve_time_range` default-last-hour at `:616-624`.
- `scripts/profiling_collector.py:22-80` — regex `(\w+): (\d+\.\d+)ms`, `calculate_statistics` schema (reused by Option A's new parser).
- `configs/spectrum.yaml:152-154` — `main_log` / `debug_log` paths.
- `deploy/systemd/wanctl@.service` — base unit ExecStart, WatchdogSec, CPUAffinity, memory limits.
- `docs/PERFORMANCE.md:1-84`, `docs/archive/PROFILING.md` — existing profiling workflow + house style (corrected by the new docs/PROFILING.md per D-07).

### Secondary (informational only, per D-04)
- `.planning/milestones/v1.0-phases/01-measurement-infrastructure-profiling/PROFILING-ANALYSIS.md` — 2s-interval RTT-dominant baseline.
- `.planning/milestones/v1.9-phases/47-cycle-profiling-infrastructure/47-RESEARCH.md` — 50ms expectations + pre-flagged regex risk.
- `.planning/phases/213-experience-baseline-harness/213-REPORT.md` — harness params (flent 2.1.1, dallas, bind map).
- `.planning/phases/217-production-cycle-budget-baseline/217-REVIEWS.md` — Codex peer-review of the previous RESEARCH/PLANS, with orchestrator-verified citations driving this refresh.

## Metadata

**Confidence breakdown:**
- Standard stack / tooling: HIGH — read directly from current source.
- Capture mechanics (D-05): HIGH — drop-in pattern is `systemd.unit(5)` standard; `WANCTL_LOG_FORMAT=json` propagation verified through `setup_logging`.
- JSON capture data path (Option A): HIGH — JSONFormatter `extra` preservation verified; `record_cycle_profiling` emission path verified; offline parser is straightforward.
- Subsystem→category map: HIGH — direct from timings dict; storage-gap is structural, not assumed.
- D-03 numeric headroom bar: HIGH — aligned with existing `/health.warning_threshold_pct=80` and a structurally honest p99-under-budget criterion.
- Observer-effect estimate: MEDIUM — adjacent-window ON/OFF is honest but depends on stable household load during the comparison; documented caveat is a sound fallback.
- Production disk performance under DEBUG JSON load: MEDIUM — strictly additive, almost certainly fine, but Wave 0 5-min pilot is the right gate.
- Driven-segment params (IPs/host): MEDIUM — from Phase 213 evidence; re-confirm live.

**Research date:** 2026-05-29 (refresh)
**Valid until:** ~30 days (stable; the only fast-moving inputs are live host facts in the Assumptions Log).
**Supersedes:** the prior 217-RESEARCH.md of the same date, whose regex/text-DEBUG/cycle_total assumption was broken by Codex peer-review and confirmed broken against current source.
