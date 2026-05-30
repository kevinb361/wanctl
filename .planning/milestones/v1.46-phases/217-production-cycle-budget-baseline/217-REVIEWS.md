---
phase: 217
reviewers: [codex]
codex_model: gpt-5.5
reviewed_at: 2026-05-29
plans_reviewed:
  - 217-01-PLAN.md
  - 217-02-PLAN.md
  - 217-03-PLAN.md
orchestrator_verification: complete
---

# Cross-AI Plan Review — Phase 217

## Codex Review

> Codex CLI 0.135.0, model `gpt-5.5`, reasoning effort xhigh, workspace-write sandbox (Codex read the source files directly).

**Top Findings**

- **HIGH:** The plans assume `profiling_collector.py` can produce `autorate_cycle_total`, but current text DEBUG logs do not emit `autorate_cycle_total: X.Xms`. `record_cycle_profiling()` records cycle total in memory, then logs only `Cycle timing` with `extra` fields; the text formatter drops those extras. See `src/wanctl/perf_profiler.py:266` and `src/wanctl/logging_utils.py:132`. Plan 03 will fail or make an unsupported verdict.
- **HIGH:** Plan 02 points at `/var/log/wanctl/spectrum.log` for DEBUG lines, but the main file handler is INFO-only. DEBUG lines go to `debug_log` and journald when `--debug` is on. See `src/wanctl/logging_utils.py:199` and `configs/spectrum.yaml:152`.
- **MEDIUM/HIGH:** The observer-effect cross-check is not valid as written. A mid-window `/health` snapshot while DEBUG is enabled reads the same profiler data from the DEBUG-inflated process, not a no-observer-effect baseline. See `src/wanctl/health_check.py:101`.

**Summary**

- **217-01** is well scoped and stays out of `src/`, but its helper is built around a collector JSON shape that real logs will not produce because `autorate_cycle_total` is not regex-parseable from text DEBUG output.
- **217-02** has the right safety posture: operator-gated, transient drop-in, explicit revert, watchdog monitoring, and driven load inside the window. The capture source is wrong, though, and the raw-log artifact should not be a committed deliverable by default.
- **217-03** has the right decision framing around D-03/D-04 and storage being out-of-band, but it depends on broken upstream data assumptions and leaves "comfortable headroom" subjective.

Overall: strong phase structure, but the capture/analysis contract needs revision before execution.

**Strengths**

- No plan mutates controller thresholds, algorithms, or `src/` control logic.
- `--profile --debug` requirement is correctly recognized; `--profile` alone is not treated as parseable.
- Mandatory `systemctl revert wanctl@spectrum` plus ExecStart verification is correctly elevated as the key safety gate.
- Router sub-timer double-counting is explicitly avoided by using `autorate_router_communication` as the parent category.
- Storage-write cost is correctly treated as non-hot-path and routed to `wanctl-history --ingestion-rate`.

**Concerns**

- **HIGH, 217-01/02/03:** `autorate_cycle_total` is not emitted as a per-cycle text DEBUG line. The regex parsers match `PerfTimer` output only: `scripts/profiling_collector.py:41`, `src/wanctl/perf_profiler.py:62`. Cycle total is recorded at `perf_profiler.py:273`, but not logged in that regex format.
- **HIGH, 217-02:** The plan retrieves `spectrum.log`; DEBUG parse lines are in `spectrum_debug.log` or journald. Main log is INFO-level: `src/wanctl/logging_utils.py:199`.
- **HIGH, 217-02/03:** `grep -c "autorate_cycle_total:" >= 60000` is impossible with current text DEBUG behavior. INFO profiling reports may contain `autorate_cycle_total: count=...`, but only about once per 60s and not in parser format.
- **MEDIUM/HIGH, 217-02 + 217-03:** The observer-effect cross-check needs a different design — `/health` is not a clean baseline while DEBUG is on. Compare `/health` cycle_time_ms with `--debug` ON vs OFF (different windows), or accept the caveat as text rather than pretending to quantify.
- **MEDIUM, 217-02:** Committing `.planning/perf/spectrum-capture-raw.log` risks leaking production operating details and bloating history. D-06 only requires aggregate `.profile.json` plus summary.
- **MEDIUM, 217-03:** `wanctl-history --ingestion-rate --wan spectrum` defaults to the last hour if no time range is supplied: `src/wanctl/history.py:616`. If Plan 03 runs later, storage attribution may not match the capture window.
- **MEDIUM, 217-03:** "Comfortable headroom" is not made falsifiable. The verdict can become subjective unless the plan sets a concrete bar before seeing data.
- **LOW, 217-03:** Hard-coded `2026-05-30` in todo lifecycle text should be actual capture/close date.

**Suggestions**

- Revise the data path before execution. Best low-risk option: add a full-window `/health` NDJSON poll artifact for cycle total and category percentages, and use DEBUG log only for sub-timer/router-write coverage.
- Correct docs and Plan 02 to retrieve `/var/log/wanctl/spectrum_debug.log*` or `journalctl -u wanctl@spectrum --since ... --until ...`, not only `spectrum.log`.
- If exact per-cycle cycle-total samples are required from logs, either parse JSON `Cycle timing` records or add a non-control-path log/parser path deliberately. Do not pretend the current regex collector can produce them.
- Keep raw production DEBUG logs untracked or temporary; commit only aggregate JSON, summary, and sanitized evidence.
- Capture storage ingestion with explicit window bounds: `wanctl-history --ingestion-rate --wan spectrum --from "<start>" --to "<end>" --json`, preferably on the production host or against the production DB.
- Define the D-03 headroom gate numerically — e.g. avg utilization below the existing 80% warning threshold plus a p99/overrun bound — **before** looking at the data.

**Risk Assessment**

Overall risk is **HIGH until the capture contract is fixed**. The live-production mutation is bounded and well guarded, but the current plans are likely to produce unusable or misleading analysis artifacts because they rely on log lines that the code does not emit. After fixing the log source, cycle-total source, observer-effect method, and raw-log handling, the phase drops to **MEDIUM** due to the transient DEBUG load on a 24/7 daemon.

---

## Orchestrator Verification (post-review)

> Each HIGH finding was verified against the source before writing this file. Codex had workspace-write sandbox access and read the source directly; cross-checked here to confirm.

| Finding | Verdict | Evidence |
|---|---|---|
| 1: `autorate_cycle_total: X.Xms` not emitted as parseable text DEBUG line | **CONFIRMED** | `src/wanctl/perf_profiler.py:288` emits `logger.debug("Cycle timing", extra={"cycle_total_ms":...})` — message string is literally `"Cycle timing"`; `cycle_total_ms` lives in `extra`. Text formatter at `src/wanctl/logging_utils.py:135` is `"%(asctime)s [{wan_name}] [%(levelname)s] %(message)s"` — drops extras entirely. The collector regex `(\w+): (\d+\.\d+)ms` at `scripts/profiling_collector.py:41` matches per-subsystem PerfTimer lines (which DO fire from `wan_controller.py:2435-2447`) but **never** `autorate_cycle_total: X.Xms`. Plan 02 Task 3 `grep -c "autorate_cycle_total:" >= 60000` will return **0**, not 60000, on a real text-DEBUG capture. |
| 2: spectrum.log is INFO-only; DEBUG goes to spectrum_debug.log + journald | **CONFIRMED** | `src/wanctl/logging_utils.py:199-208`: main file handler `RotatingFileHandler(config.main_log).setLevel(logging.INFO)`; debug file handler `RotatingFileHandler(config.debug_log).setLevel(logging.DEBUG)`. `configs/spectrum.yaml:153-154` confirms `main_log: /var/log/wanctl/spectrum.log` (INFO) and `debug_log: /var/log/wanctl/spectrum_debug.log` (DEBUG). Plan 02 Task 2 step 9 retrieves the wrong file. |
| 3: `/health` cycle_time_ms shares observer-effect with DEBUG samples | **CONFIRMED** | `src/wanctl/health_check.py:101`: `stats = profiler.stats(total_label)`. Both `/health` and DEBUG read from the same in-process `profiler` object, fed by `record_cycle_profiling`'s `total_ms = (time.perf_counter() - cycle_start) * 1000.0`. They will be ~identical; their delta is ~0 by construction. Plan 03 Task 2's observer-effect quantification design is invalid. |

**Source of the blindspot:** The Phase 217 researcher empirically verified the regex against per-subsystem `PerfTimer` DEBUG output and reported HIGH confidence — that part is correct. The miss is that `cycle_total` does NOT flow through `PerfTimer` like sub-timings do; it's computed inside `record_cycle_profiling` and only ever logged as a structured `extra=` field (drops in text formatter; preserved only in JSON formatter). The plans inherited this blindspot.

---

## Consensus Summary

Single-reviewer (Codex) but every HIGH finding was independently verified against the source code. There is no divergence to investigate.

### Agreed Strengths
- Measurement-only scope honored (no `src/` mutations anywhere).
- Live-production safety: transient drop-in, mandatory `systemctl revert` + ExecStart verification, watchdog monitoring, operator-gated capture.
- Router sub-timer double-count avoided (parent category only).
- Storage-write cost correctly routed to `wanctl-history --ingestion-rate` rather than the hot path.

### Agreed Concerns (HIGH — blocking)
1. **Cycle-total source is wrong (HIGH).** `autorate_cycle_total: X.Xms` does not appear in text DEBUG output. Plan 02 Task 3 sample-count floor and Plan 03 Task 1 cycle-total derivation are both built on a false premise. Fix options:
   - **(A)** Switch capture format to JSON for the window (`Environment=WANCTL_LOG_FORMAT=json` in the drop-in) and write a JSON-aware parser for `Cycle timing` records — preserves `cycle_total_ms` and per-subsystem `*_ms` extras together.
   - **(B)** Poll `/health` over the full window as NDJSON to source cycle_total and category %; reserve text DEBUG only for sub-timer / router-write coverage which the regex collector still parses correctly.
   - **(C)** Add a one-line `logger.debug(f"{label_prefix}_cycle_total: {total_ms:.1f}ms")` next to the structured log in `record_cycle_profiling` — but this is a `src/` change and violates the measurement-only scope of D-05.
2. **Log source is wrong (HIGH).** Plan 02 retrieves `/var/log/wanctl/spectrum.log` (INFO-only). The DEBUG sink is `/var/log/wanctl/spectrum_debug.log` (+ rotated backups) when `--debug` is enabled, or `journalctl -u wanctl@spectrum`. Trivial Plan-02 + docs/PROFILING.md correction.
3. **Observer-effect cross-check design is invalid (MEDIUM/HIGH).** `/health` and the DEBUG-logged cycle_total both come from the same in-process measurement; their delta is ~0. To get a real observer-effect number, capture `/health cycle_time_ms.avg` over two short windows — `--debug` ON vs `--debug` OFF — in adjacent steady-state intervals. Or downgrade the requirement to a documented caveat rather than a number.

### Agreed Concerns (MEDIUM)
4. Committing raw DEBUG log to the repo (`.planning/perf/spectrum-capture-raw.log`) is heavier than D-06 requires and risks operator-detail leakage. T-217-05's pre-commit scrub partially mitigates, but the cleaner option is to keep raw logs untracked and commit only the aggregate `.profile.json`, the summary, and sanitized evidence.
5. `wanctl-history --ingestion-rate` defaults to the last hour. If Plan 03 runs hours after the capture, the storage attribution misaligns with the capture window. Use explicit `--from`/`--to` window bounds.
6. "Comfortable 50ms headroom" in the D-03 partition is not numerically falsifiable. Set a concrete bar — e.g. `avg utilization < 80%` (the existing `/health` warning threshold) AND `p99 < 50ms` (no overruns) — **before** looking at the data.

### Divergent Views
None — single reviewer, all findings cross-validated against source.

---

## Recommended Next Step

The HIGH findings are upstream of the plans (research blindspot) — the planner alone cannot fix them without revised research input. Two options:

**Option A (cheaper):** `/gsd-plan-phase 217 --research-phase 217 --research` — force-refresh research to update the capture data-path (JSON-format capture OR /health NDJSON poll), confirm `spectrum_debug.log` is the DEBUG sink, and replace the invalid observer-effect cross-check design. Then `/gsd-plan-phase 217 --reviews` to replan against the updated research with these review findings folded in.

**Option B:** `/gsd-plan-phase 217 --reviews` directly — let the planner read this REVIEWS.md and the existing RESEARCH.md together and self-correct. Riskier because the research file currently asserts the regex assumption is HIGH-confidence.

Recommend Option A.
