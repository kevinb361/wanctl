# Phase 243: Cycle-Budget Benchmark Gate - Research

**Researched:** 2026-06-16
**Domain:** Performance measurement harness + pre-registered no-regression gate (systemd, journal-pipe capture, stdlib NDJSON rollups, subprocess hygiene) over the existing wanctl 50ms control loop
**Confidence:** HIGH (almost entirely codebase-grounded; every reusable asset read directly)

## Summary

Phase 243 is a **measurement + gate** phase, not a behavior-change phase. The job is to prove `fping` introduces no 50ms cycle-budget regression vs the same-run `icmplib` control arm, under a **real systemd unit with stdout on a journal pipe** (the TTY-vs-pipe fingerprint), and to commit the pass/fail thresholds **before** collecting any data so the verdict can't be rationalized post-hoc. The gate output is a hard precondition for the Phase 245 live A/B.

The strongly grounded finding: **almost nothing new needs to be built in `src/wanctl/`.** The controller already emits everything the gate measures. `WANController.run_cycle()` wraps every subsystem in `PerfTimer` and calls `record_cycle_profiling()` (perf_profiler.py:234), which records `autorate_cycle_total` into an `OperationProfiler` (avg/p95/**p99** already computed, perf_profiler.py:139-143) **and** emits a per-cycle `"Cycle timing"` DEBUG log carrying `cycle_total_ms` + every subsystem `*_ms` field (perf_profiler.py:287-294). When the daemon runs with `--debug` and `WANCTL_LOG_FORMAT=json`, those records hit the console `StreamHandler` (logging_utils.py:206-221) → stdout → the systemd journal pipe as NDJSON. `scripts/profiling_collector_json.py` already parses exactly those `"Cycle timing"` NDJSON records into per-label avg/p50/p95/p99 (profiling_collector_json.py:45-71). That is the entire cycle-budget capture glue — it exists and was used for the Phase 217 baseline.

So the phase decomposes into: (1) a **throwaway systemd unit** (`systemd-run --unit=` transient, recommended) that launches `autorate_continuous.py --debug` against a benchmark config selecting each backend via the 242 `build_rtt_backend()` factory, with `WANCTL_LOG_FORMAT=json`; (2) **journal capture** of the `"Cycle timing"` NDJSON stream per arm, fed to `profiling_collector_json.py`; (3) a **soak sampler** (clone of `soak-capture.sh`'s NDJSON-per-tick pattern) recording zombies/fd/Tasks from `/proc` + `systemctl show -p TasksCurrent`; (4) **load generation** by reusing the existing flent-RRUL-over-netperf-to-Dallas-Linode (`104.200.21.31`) path for both WANs; (5) a **pre-registration artifact** (`243-BENCHMARK-PREREGISTRATION.md` + thresholds JSON, committed before the run) and a **verdict evaluator** (stdlib, pattern from `phase206-gate-check.py` / `phase224-gate-eval.py`); (6) a **`phase243-safe17-boundary-check.sh`** cloned from the 242 verifier + a mirror test pinned to the **phase-close anchor** (not HEAD).

**Primary recommendation:** Build benchmark scaffolding under `scripts/` + `.planning/phases/243-.../evidence/` only; touch **zero** `src/wanctl/` controller hot-path files (the existing `--debug`/`--profile`/JSON-log path is sufficient to surface cycle budget). Capture cycle budget via the existing `"Cycle timing"` NDJSON → `profiling_collector_json.py` path; capture fd/zombie/Tasks via a new `soak-capture.sh`-shaped sampler; gate against pre-committed D-04 thresholds with a stdlib evaluator. SAFE-17 stays trivially green because no controller source changes.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Run the real 50ms control loop per backend | Existing controller (`autorate_continuous.py`) | — | D-01: must be the *real* loop, not a synthetic one. No new loop code. |
| Backend selection (icmplib vs fping) per arm | 242 factory (`build_rtt_backend()`) + per-WAN config YAML | — | Single construction site; arms swap by config, not code branch. |
| Per-cycle timing emission (avg/p99) | Existing `perf_profiler.record_cycle_profiling` + JSON log | — | Already emits `"Cycle timing"` NDJSON with `cycle_total_ms`. Read-only reuse. |
| Process isolation / journal-pipe stdout | systemd transient unit (`systemd-run`) | committed `wanctl-bench@.service` template | D-01b: TTY-vs-pipe is the STALL fingerprint; unit gives journal pipe. |
| Cycle-budget rollup per arm | `scripts/` (clone `profiling_collector_json.py` glue) | `soak_summary_aggregate.py` percentile helpers | Stdlib NDJSON p50/p95/p99; no NumPy/pandas. |
| fd/zombie/Tasks soak sampling | new `scripts/` sampler (clone `soak-capture.sh`) | `/proc`, `systemctl show -p TasksCurrent` | Off-process observation; never touches controller. |
| Load generation (under-load arm) | existing flent-RRUL path (`benchmark.py` / phase213 capture) | netperf Dallas Linode `104.200.21.31` | D-03: reuse established path; no iperf, no synthetic CPU load. |
| Pre-registration + verdict | `.planning/phases/243-.../` docs + `scripts/` evaluator | — | BENCH-02: thresholds committed before data; verdict recorded after. |
| Boundary enforcement | `scripts/phase243-safe17-boundary-check.sh` + mirror test | — | SAFE-17: fail-closed git-diff verifier, scaffolding-only allowlist. |

## Standard Stack

### Core (all already present in repo — no installs)
| Asset | Location | Purpose | Why Standard |
|-------|----------|---------|--------------|
| `OperationProfiler` | `src/wanctl/perf_profiler.py:66` | Per-cycle avg/p95/**p99** accumulation (already wired into `run_cycle`) | The live cycle-budget metric engine; no new stats code. `[VERIFIED: codebase]` |
| `record_cycle_profiling` | `perf_profiler.py:234` | Records `autorate_cycle_total` + emits `"Cycle timing"` DEBUG NDJSON | The emission seam the benchmark reads; emits `cycle_total_ms` + subsystem `*_ms`. `[VERIFIED: codebase]` |
| `profiling_collector_json.py` | `scripts/profiling_collector_json.py` | Parses `"Cycle timing"` NDJSON → per-label avg/p50/p95/p99 JSON | Exact-match parser for the journal stream; Phase 217 data path. `[VERIFIED: codebase]` |
| `soak_summary_aggregate.py` | `scripts/soak_summary_aggregate.py` | Stdlib NDJSON percentile helpers (`percentile()`, `histogram()`) | Reusable p50/p95/p99 with no NumPy/pandas; import `percentile` for trend math. `[VERIFIED: codebase]` |
| `soak-capture.sh` | `scripts/soak-capture.sh` | NDJSON-per-tick capture loop w/ bounded failure tolerance | Precedent shape for the fd/zombie/Tasks soak sampler. `[VERIFIED: codebase]` |
| `build_rtt_backend()` | `src/wanctl/rtt_backend_factory.py` (242) | Single backend construction site driven by config | The arm selector; benchmark swaps backends purely via per-WAN YAML. `[VERIFIED: codebase]` |
| flent RRUL path | `src/wanctl/benchmark.py` + `scripts/phase213-baseline-capture.sh` (`--bind-map`) | Load generation to netperf Dallas Linode | D-03 reuse; source-bound RRUL per WAN. `[VERIFIED: codebase]` |
| SAFE-17 verifier | `scripts/phase242-safe17-boundary-check.sh` | Fail-closed controller-path git-diff boundary gate | Clone-and-extend pattern (238→242); 243 narrows the allowlist. `[VERIFIED: codebase]` |
| Gate evaluator pattern | `scripts/phase206-gate-check.py`, `scripts/phase224-gate-eval.py`, `scripts/phase206-thresholds.json` | Threshold JSON + stdlib pass/fail verdict | Established pre-registered-threshold → verdict shape. `[VERIFIED: codebase]` |

### Supporting (system tools — confirm on the .226/.233 deploy hosts, NOT this dev VM)
| Tool | Purpose | When to Use |
|------|---------|-------------|
| `systemd-run --unit=... --pty`/`--pipe` | Launch throwaway controller unit with journal-pipe stdout | D-01 vehicle. Use `--collect` for auto-cleanup; do NOT use `--pty` (that gives a TTY — defeats the fingerprint). Use default (journal) or `--pipe` carefully. |
| `journalctl -u <unit> -o cat --no-pager` | Drain the per-arm NDJSON cycle stream | Pipe to `profiling_collector_json.py`. `-o cat` strips journal metadata, leaving raw NDJSON lines. |
| `systemctl show -p TasksCurrent <unit>` | Sample systemd `Tasks=` count over soak | D-04a Tasks/threads bound. |
| `/proc/<pid>/fd` (count) , `/proc/<pid>/task` , `ps`/`/proc/<pid>/stat` state `Z` | fd count, thread count, zombie detection | D-04a fd/zombie/Tasks. Zombie = any child in `Z` state reaped-late. |
| `fping` (5.1 baseline) | The backend under test | Must be installed on both WAN hosts; `-S` source binding. (MISSING on this research VM — not authoritative; verify on .226/.233.) |
| `flent` + `netperf` | Load generation | Present on this VM; confirm on deploy hosts. |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Transient `systemd-run --unit=` | Committed `wanctl-bench@.service` template | Template is more reproducible + reviewable but adds a `deploy/systemd/` artifact and a teardown story; transient unit is fully reversible with `--collect` and leaves zero repo footprint. **Recommend transient** (D-01 lists both; transient is lighter and matches "throwaway"). A committed template is acceptable if the planner wants the invocation pinned in-repo. |
| Existing `--debug` JSON-log NDJSON capture | New explicit "benchmark observe mode" in the controller | A new mode is a **controller hot-path edit** → SAFE-17 risk + behavior surface. The existing `--debug` + `WANCTL_LOG_FORMAT=json` path already emits `"Cycle timing"` NDJSON. **Do not add an observe mode** unless a gap is proven. |
| `profiling_collector_json.py` reuse | New aggregator | The existing collector is an exact match for the `"Cycle timing"` schema; reuse it. Add only a thin per-arm wrapper. |

**Installation:** No Python package installs. System tools (`fping`, `flent`, `netperf`, `systemd`) must be present on the **.226 (Spectrum) and .233 (ATT) deploy hosts** — verify there, not on the dev VM.

**Version verification:** N/A — no new packages. `fping` baseline is 5.1 per the v1.53 milestone (REQUIREMENTS.md:94). Confirm `fping --version` on each WAN host before the run.

## Package Legitimacy Audit

No external packages are installed by this phase. All capabilities reuse in-repo scaffolding (stdlib-only) plus system binaries (`systemd`, `fping`, `flent`, `netperf`) already part of the deployment baseline. **Package Legitimacy Gate: N/A — zero new dependencies.**

## Architecture Patterns

### System Architecture Diagram (per arm; 8 arms total = 2 backends × {idle,load} × 2 WANs)

```
PRE-REGISTRATION (committed BEFORE any run)
  243-BENCHMARK-PREREGISTRATION.md + phase243-thresholds.json  ──┐ (D-04 thresholds frozen in git)
                                                                  │
ARM EXECUTION (operator-run on .226 / .233)                       │
  per-WAN bench config (backend: icmplib|fping, source_ip -S) ──► systemd-run --unit=wanctl-bench-<arm>
                                                                  │   WANCTL_LOG_FORMAT=json
                                                                  │   ExecStart: autorate_continuous.py --debug --config <bench.yaml>
                                                                  ▼
                            ┌─────────────── throwaway unit (journal pipe stdout, NOT TTY) ──────────────┐
                            │  real 50ms loop: run_cycle() → PerfTimer subsystems →                       │
                            │  record_cycle_profiling() → OperationProfiler(p99) + "Cycle timing" NDJSON  │
                            │  fping backend runs OFF-loop on FpingThread (Selection A) ──► contention    │
                            └───────────────────────────────────────────────────────────────────────────┘
                              │ stdout→journal                         │ live process
                              ▼                                        ▼
  (under-load arm only) flent RRUL ──► netperf      journalctl -u <unit> -o cat        soak sampler (clone soak-capture.sh)
   Dallas Linode 104.200.21.31 (-S WAN src)            │ raw NDJSON                       1Hz: /proc/<pid>/fd | task | stat(Z)
   real CAKE rate-adjust + elevated RTT                ▼                                         + systemctl show -p TasksCurrent + CPUUsageNSec
                                            profiling_collector_json.py                          ▼
                                              → <arm>.profile.json (avg/p99)         <arm>.hygiene.ndjson (fd/zombie/tasks/cpu_nsec)
                                                         │                                       │
                                                         └──────────────┬────────────────────────┘
                                                                        ▼
  VERDICT (recorded AFTER, against frozen thresholds)
    phase243-gate-eval.py  ──►  243-BENCHMARK-VERDICT.json
      • fping avg/p99 delta vs same-run icmplib arm ≤ 20%   (D-04)
      • fping p99 < 10ms absolute ceiling                   (D-04)
      • CPU% delta < pre-committed bound (~2 pts)           (D-04; cpu_delta_pts from CPUUsageNSec window deltas)
      • zombies == 0; fd no monotonic upward trend; Tasks bounded  (D-04a)
      • zero cycle gap > 100ms attributable to a burst      (D-04b STALL)
      • per-arm n ≥ max(10k cycles, 30 min)                 (D-04c validity floor)
      • dev icmplib arm ≈ 2.85ms/6.9ms representativeness    (D-02 secondary anchor)
```

### Recommended Project Structure (additive only — no `src/wanctl/` edits)
```
scripts/
├── phase243-bench-run.sh           # launches one arm: systemd-run transient unit, journal capture, teardown (--collect)
├── phase243-hygiene-sampler.sh     # clone of soak-capture.sh shape: 1Hz fd/zombie/Tasks NDJSON
├── phase243-cycle-rollup.py        # thin wrapper over profiling_collector_json.py per arm (+ stall-gap detector)
├── phase243-gate-eval.py           # stdlib verdict vs phase243-thresholds.json (pattern: phase206-gate-check.py)
├── phase243-thresholds.json        # D-04 thresholds (committed BEFORE run)
└── phase243-safe17-boundary-check.sh   # clone of phase242 verifier, scaffolding-only allowlist

configs/bench/                      # OR reuse existing att/spectrum yaml with backend override
├── spectrum-bench-icmplib.yaml
├── spectrum-bench-fping.yaml
├── att-bench-icmplib.yaml
└── att-bench-fping.yaml

.planning/phases/243-cycle-budget-benchmark-gate/
├── 243-BENCHMARK-PREREGISTRATION.md   # the human-readable frozen gate (D-04), committed before data
└── evidence/
    ├── safe17-boundary-243.json
    ├── <wan>-<backend>-<load>.profile.json     # cycle budget per arm
    ├── <wan>-<backend>-<load>.hygiene.ndjson   # fd/zombie/Tasks per arm
    └── 243-BENCHMARK-VERDICT.json              # recorded AFTER, against frozen thresholds
```

### Pattern 1: Cycle-budget capture via existing journal NDJSON
**What:** Run the real loop with `--debug` + `WANCTL_LOG_FORMAT=json`; drain `"Cycle timing"` NDJSON from the journal; feed to `profiling_collector_json.py`.
**When to use:** Every arm. This is the entire cycle-budget capture mechanism — no new controller code.
**Example:**
```bash
# Source: scripts/profiling_collector_json.py:5-8 (canonical invocation) + logging_utils.py:206-221
# Launch throwaway unit (journal pipe, NOT --pty):
sudo systemd-run --unit="wanctl-bench-spectrum-fping-load" --collect \
  --setenv=WANCTL_LOG_FORMAT=json \
  /opt/wanctl/.venv/bin/python -m wanctl.autorate_continuous \
    --debug --config /etc/wanctl/bench/spectrum-bench-fping.yaml
# ... run for >= max(30min, 10k cycles) ...
# Drain raw NDJSON (no journal metadata) and roll up:
journalctl -u wanctl-bench-spectrum-fping-load -o cat --no-pager \
  | python3 scripts/profiling_collector_json.py - \
      --output .planning/phases/243-.../evidence/spectrum-fping-load.profile.json
# Teardown is automatic with --collect; otherwise: systemctl stop <unit>
```
The collector requires `autorate_cycle_total` samples or it errors (profiling_collector_json.py:124) — a built-in validity check that the loop actually ran.

### Pattern 2: Subprocess-hygiene soak sampling (clone soak-capture.sh)
**What:** A 1Hz NDJSON sampler keyed on the unit's MainPID recording fd count, thread/Tasks count, zombie count, and the per-unit cumulative CPUUsageNSec counter (the CPU% gate producer).
**Example:**
```bash
# Source: scripts/soak-capture.sh (NDJSON-per-tick pattern, bounded failure tolerance)
PID=$(systemctl show -p MainPID --value wanctl-bench-spectrum-fping-load)
fd=$(ls /proc/$PID/fd | wc -l)
tasks=$(systemctl show -p TasksCurrent --value wanctl-bench-spectrum-fping-load)
cpu_nsec=$(systemctl show -p CPUUsageNSec --value wanctl-bench-spectrum-fping-load)  # cumulative; gate takes window delta
# zombie children of PID: scan /proc/*/stat for state Z whose PPID==PID
zombies=$(awk '...' /proc/[0-9]*/stat)   # count R/S/D vs Z; Z under this PID = reaping bug
printf '{"t":%s,"fd":%s,"tasks":%s,"zombies":%s,"cpu_nsec":%s}\n' "$(date +%s)" "$fd" "$tasks" "$zombies" "$cpu_nsec"
```
**Trend test (stdlib):** import `percentile` from `soak_summary_aggregate.py`; "flat/bounded" = `(last-quartile median fd) - (first-quartile median fd) <= small_epsilon` AND `max(fd) - min(fd)` within a jitter band. Reject monotonic upward: split the series into N windows, assert window medians are not strictly increasing across all windows. Zombies: assert `max(zombies) == 0`. Tasks: assert `max(tasks) <= baseline_tasks + bound`. **CPU:** `cpu_pct = (cpu_nsec_last - cpu_nsec_first) / (window_wall_ns * n_cores) * 100`; the gate compares the fping-arm cpu_pct vs the same-run icmplib-arm cpu_pct as `cpu_delta_pts`.

### Pattern 3: STALL (cycle-gap) detection — the TTY-vs-pipe fingerprint
**What:** From the per-cycle NDJSON, reconstruct inter-cycle wall gaps (from the `timestamp` field on each `"Cycle timing"` record, JSONFormatter logging_utils.py:84-86) and flag any gap `> 2× budget = >100ms` (D-04b). A pipe-buffering hang manifests as a missing-cycle spike.
**Example:** parse consecutive `"Cycle timing"` record `timestamp`s; `gap_ms = t[i] - t[i-1]`; `stall_events = [g for g in gaps if g > 100]`; gate requires `len(stall_events) == 0`. Pair with a check that every fping burst returned within its bounded timeout (FpingThread already asserts `timeout < cadence`; surface any timeout/recovery via the fping backend's existing recover-and-continue logging).

### Anti-Patterns to Avoid
- **`systemd-run --pty`:** gives the process a TTY, which is line-buffered and *defeats the entire point* of the STALL fingerprint. The unit MUST have stdout on the journal pipe (default `systemd-run` behavior or `--pipe` to a drain). The whole reason for a real unit (D-01) is pipe-vs-TTY buffering.
- **Adding a controller "benchmark/observe mode":** any new `src/wanctl/` code is a SAFE-17 boundary expansion and a behavior surface. The existing `--debug` JSON-log path is sufficient. If a genuine gap exists, it must be flagged to the operator, not silently added.
- **Computing the gate against the historical 2.85/6.9 baseline as PRIMARY:** D-02 is explicit — the **same-run icmplib arm** is the primary control; the historical anchor is only a representativeness sanity check on the dev host.
- **Per-cycle `subprocess.run` assumptions:** fping runs OFF-loop on `FpingThread` (Selection A, 238-PROVENANCE-MAP.md:13). The gate measures **tail contention (p99) + CPU%**, not direct per-cycle cost — the average is expected ~unchanged.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Per-cycle avg/p99 | New profiler | `OperationProfiler` + `record_cycle_profiling` (already in `run_cycle`) | Exists, wired, used for Phase 217 baseline. |
| Cycle NDJSON → stats | New parser | `scripts/profiling_collector_json.py` | Exact match for the `"Cycle timing"` schema. |
| Percentiles without NumPy | Hand-rolled percentile | `percentile()`/`histogram()` in `soak_summary_aggregate.py` | Stdlib, tested, NumPy-free. |
| Soak NDJSON loop w/ failure tolerance | New capture loop | Clone `soak-capture.sh` | Bounded-failure NDJSON pattern already battle-tested. |
| Backend selection per arm | New backend switch | `build_rtt_backend()` (242 factory) | Single construction site; config-driven. |
| Load generation | New traffic generator | flent RRUL via `benchmark.py` / `phase213-baseline-capture.sh --bind-map` | D-03 reuse; source-bound to Dallas Linode. |
| Per-unit CPU% | `/proc/<pid>/stat` utime+stime hand-rolling | `systemctl show -p CPUUsageNSec` cgroup delta | Per-unit cgroup accounting isolates the bench process tree; no PID-tree walking. |
| Pre-registered threshold → verdict | New gate logic | `phase206-gate-check.py` / `phase224-gate-eval.py` + thresholds JSON | Established pre-registration→verdict shape. |
| Boundary diff verifier | New SAFE-17 logic | Clone `phase242-safe17-boundary-check.sh` | Fail-closed pattern proven 238→242. |

**Key insight:** This phase is ~90% orchestration of existing instrumentation. The highest-risk temptation is "just add a tiny observe hook to the controller" — that is exactly what SAFE-17 exists to prevent. The controller already tells you the cycle budget through its JSON debug log.

## Runtime State Inventory

> This is a measurement/scaffolding phase, not a rename/refactor. Inventory included because the throwaway unit interacts with live host state.

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | None — benchmark writes only to `.planning/phases/243-.../evidence/` and `/var/tmp`. No metrics DB writes (bench config should point metrics writer at a throwaway/disabled path, or accept transient rows). | Confirm bench config does not write to the production metrics DB (or uses a temp DB). |
| Live service config | **wanctl@ is disabled on dev hosts** (prod is cake-autorate since 2026-06-08). The throwaway unit must use a **distinct unit name** (`wanctl-bench-*`) and a bench config with a **distinct health port / state path / lock path** so it does not collide with live `cake-autorate-{spectrum,att}.service`, the state bridges, or steering. | Bench config: unique `health` port, unique `/run/wanctl` lock, no shared state files. Verify no port/lock collision before launch. |
| OS-registered state | Transient `systemd-run` unit auto-collects with `--collect`. No persistent unit unless a committed `wanctl-bench@.service` template is chosen (then teardown = `systemctl stop`/`disable`). | Prefer `--collect` transient; if template, document explicit teardown. |
| Secrets/env vars | `WANCTL_LOG_FORMAT=json` (new, benign, env-only). Router password handling unchanged — bench config may not need a router (idle/observe), but if it drives CAKE it uses the same `/etc/wanctl/secrets`. | Pass `WANCTL_LOG_FORMAT=json` via `--setenv`; no new secret. |
| Build artifacts | None — no package rename, no egg-info churn. | None. |

**Canonical question (after run):** the transient unit is gone (`--collect`); the only residue is evidence JSON/NDJSON under `.planning/`. Confirm: no leftover `wanctl-bench-*` unit, no leftover lock in `/run/wanctl`, no stray flent/netperf process, no orphaned `fping` child.

## Common Pitfalls

### Pitfall 1: TTY vs journal pipe buffering (the whole reason this phase exists)
**What goes wrong:** Running the loop in an interactive shell (TTY, line-buffered) hides the pipe-block-buffering stall that only appears when stdout is a non-TTY pipe under systemd. The benchmark would "pass" interactively and the A/B would then stall in production.
**Why it happens:** `fping`/subprocess stdout and Python's own stdout buffering differ between TTY and pipe; the pre-v4.3 `fping -l` STALL root cause was pipe block-buffering (REQUIREMENTS.md:95).
**How to avoid:** Run under a real unit; NEVER `--pty`. Confirm the unit's stdout is the journal (`systemctl show -p StandardOutput`).
**Warning signs:** cycle-gap spikes >100ms; missing `"Cycle timing"` records for stretches.

### Pitfall 2: Bench unit collides with live cake-autorate / bridge state
**What goes wrong:** The throwaway unit grabs the same health port (9101), lock, or state file as the live `cake-autorate-*-state-bridge` or steering, corrupting live state or failing to start.
**How to avoid:** Bench config gets a **unique health port, lock path, and state path**. Verify with `ss -ltnp` before launch.
**Warning signs:** bind errors on start; steering reading bench-written state.

### Pitfall 3: Gating on the wrong baseline
**What goes wrong:** Computing the verdict against the historical 2.85/6.9 numbers as the primary gate instead of the same-run icmplib arm; dev-host CPU drift then masks or fabricates a regression.
**How to avoid:** Primary delta = `fping_arm − icmplib_arm` on the **same host/run/load** (D-02). Historical anchor only validates the dev icmplib arm is representative (~2.85/6.9); if it isn't, re-run on a better host before trusting any fping verdict.

### Pitfall 4: Subprocess reaping / zombie under fping bursts
**What goes wrong:** fping bursts that aren't reaped leave zombies; D-04a fails any zombie strictly.
**How to avoid:** The fping backend already uses bounded-timeout `subprocess.run` with recover-and-continue (FPING-05). The sampler must scan for `Z`-state children whose PPID is the unit MainPID. Any nonzero zombie = fail (reaping bug).
**Warning signs:** `Z` in `/proc/<child>/stat`; rising thread/Tasks count.

### Pitfall 5: Insufficient samples → unstable p99
**What goes wrong:** Short runs give noisy p99 tails; the gate is then meaningless.
**How to avoid:** Enforce D-04c: per arm `n >= max(10k cycles, 30 min)`. At 20Hz, 30 min ≈ 36k cycles. The collector's `autorate_cycle_total` count is the n; assert it before computing the verdict.

### Pitfall 6: SAFE-17 mirror test rots against HEAD
**What goes wrong:** The phase-boundary verifier only holds at its own close; pinning the mirror test to HEAD makes it fail when later phases (244+) legitimately change the controller.
**How to avoid:** Pin the worktree in `test_phase243_safe17_verifier.py` to `PHASE_CLOSE_ANCHOR` (the 243 close commit), exactly as `test_phase241_safe17_verifier.py:25` does. (Memory: "SAFE-17 boundary tests must pin to PHASE_CLOSE_ANCHOR, not HEAD.")

## Code Examples

### Cloning the SAFE-17 verifier for 243 (scaffolding-only allowlist)
```bash
# Source: scripts/phase242-safe17-boundary-check.sh (clone-and-extend)
# 243 is a measurement phase — NO controller hot-path edits expected.
# The CLEANEST 243 posture: assert ZERO src/wanctl/ diff vs the Phase 242 close anchor.
# i.e. CHANGED_PATHS under src/wanctl/ must be EMPTY (the allowlist is the empty set for new edits).
#
# Reuse the existing fail-closed scaffolding:
#   - dirty-tree gate (unstaged/staged/untracked src/wanctl/ → fail)
#   - git diff --name-only <PHASE242_CLOSE_ANCHOR> HEAD -- src/wanctl/  → must be empty
#   - --self-test proving a committed src/wanctl edit trips the gate
#   - emit JSON evidence to .planning/phases/243-.../evidence/safe17-boundary-243.json
ANCHOR="<PHASE242_CLOSE_ANCHOR>"     # 242 close commit (e.g. fcc2e15b or the verified 242 close)
OUT=".planning/phases/243-cycle-budget-benchmark-gate/evidence/safe17-boundary-243.json"
# If 243 truly edits no controller source, the verifier reduces to: changed src/wanctl == ∅.
```
The 242 verifier carries 239/240/241 protected-body machinery because those phases edited controller source. **243 edits none**, so the 243 verifier can be *simpler*: prove the `src/wanctl/` tree is byte-identical to the 242 close anchor (empty diff), plus the standard dirty-tree fail-closed gate and `--self-test`. The mirror test asserts the script contract + an out-of-allowlist commit (any `src/wanctl/` edit) fails closed, pinned to the 243 close anchor.

### Verdict evaluator skeleton (stdlib, pattern from phase206-gate-check.py)
```python
# Reads frozen phase243-thresholds.json + per-arm evidence; writes 243-BENCHMARK-VERDICT.json
# Gates (D-04 / D-04a / D-04b / D-04c), per WAN, fping vs same-run icmplib:
#   avg_delta_pct = (fping.avg - icmplib.avg) / icmplib.avg * 100   ; require <= 20
#   p99_delta_pct = (fping.p99 - icmplib.p99) / icmplib.p99 * 100   ; require <= 20
#   require fping.p99 < 10.0                                         # absolute ceiling
#   cpu_pct(arm) = cpu_nsec_delta / (window_wall_sec*1e9*n_cores) * 100   # from CPUUsageNSec window deltas
#   cpu_delta_pts = fping_arm.cpu_pct - icmplib_arm.cpu_pct ; require cpu_delta_pts < CPU_DELTA_PCT_POINTS  # frozen 2.0
#   require max(hygiene.zombies) == 0
#   require fd trend not monotonic-upward (windowed-median test)
#   require max(hygiene.tasks) <= tasks_baseline + TASKS_BOUND
#   require stall_events(gaps>100ms) == 0                           # STALL
#   require fping.count >= max(10000, cycles_for_30min)             # validity floor
#   secondary: icmplib.avg ~ 2.85 +/- band, icmplib.p99 ~ 6.9 +/- band (representativeness)
# verdict = "pass" iff all primary gates pass; "keep icmplib" is a valid passing close at AB level.
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Phase 217: revive `wanctl@` + ExecStart profiling override on the live service | **Throwaway transient unit** running the real loop, prod-state-isolated | Phase 243 (D-01) | Avoids entangling with disabled `wanctl@` / live cake-autorate; fully reversible. |
| Gate vs historical baseline | **Same-run icmplib control arm** as primary; historical only as representativeness anchor | Phase 243 (D-02) | Controls for dev-host CPU/kernel drift. |
| `fping -l` long-lived loop | One-shot `subprocess.run` bursts off-loop on `FpingThread` | Phase 241 (FPING-01) | Pipe-block-buffering STALL root cause avoided; gate measures contention not the loop process. |

**Deprecated/outdated:** Do not reintroduce timer-era or `wanctl@`-revive profiling guidance (CLAUDE.md: service-based, not timer-based; `wanctl@` disabled).

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `WANCTL_LOG_FORMAT=json` + `--debug` is sufficient to emit `"Cycle timing"` NDJSON to the journal with `cycle_total_ms` per cycle, with no controller edit. | Stack / Pattern 1 | If DEBUG console handler doesn't reach the journal under the unit, a thin capture adjustment (env/handler) is needed — still scaffolding, but verify with a 60s smoke run first. `[ASSUMED]` (grounded in logging_utils.py:206-221 + perf_profiler.py:287-294 but not run end-to-end this session). |
| A2 | Both Spectrum and ATT under-load arms can reuse the flent-RRUL-to-Dallas-Linode (`104.200.21.31`) path with `-S` WAN source binding. | Stack / D-03 | ATT's exact load server: `104.200.21.31` is the IRTT server in att.yaml AND the phase220 matrix `dallas` netperf target for the ATT path — consistent. Confirm netperf reachable from the ATT source IP at run time. `[VERIFIED: codebase]` for the target; `[ASSUMED]` for live reachability at run time. |
| A3 | Dev WAN source-bind IPs: Spectrum `10.10.110.226` (phase220 `--bind-map spectrum=10.10.110.226`), ATT `10.10.110.227`/`.233`. | Runtime State / D-01a | Planner/operator must confirm exact `-S` binding + `ip rule` egress on each host (PROV-03 already proved both WANs egress correctly). `[VERIFIED: codebase]` for .226/.227; `[ASSUMED]` mapping of ".233" to the ATT deploy host vs source IP. |
| A4 | The cleanest 243 SAFE-17 posture is an empty `src/wanctl/` diff vs the 242 close anchor (no controller edits at all). | Code Examples | If the planner discovers a genuine need for a controller observe hook, the allowlist must expand and the protected-body machinery returns — but that should be challenged first. `[ASSUMED]` (design recommendation). |
| A5 | `fping` 5.1 is installed on both .226/.233 hosts. | Supporting Stack | FALL-01/02 means absence falls back to icmplib — but the benchmark *needs* fping present to measure it. Verify `fping --version` on both hosts before the run (MISSING on this research VM). `[ASSUMED]` |
| A6 | The transient bench unit can run with a config that does not collide with live cake-autorate/bridge/steering (unique port/lock/state). | Runtime State | Collision risk on health port 9101 / `/run/wanctl` lock. Verify with `ss -ltnp` + lock inspection before launch. `[ASSUMED]` |

## Open Questions (RESOLVED)

1. **Does the bench unit need to actually drive CAKE, or can it observe-only?**
   - **RESOLVED:** operator-confirmed at run — the bench config drives the dev host's own CAKE (the loop's router communication is part of the measured cycle budget); the Plan 04 runbook instructs the operator to confirm the bench config targets the dev shaper, not production.
   - What we know: D-01 says run the *real* loop; the under-load arm needs the controller "in active CAKE rate-adjustment with elevated RTT" (D-03) to create realistic per-cycle work + contention.
   - What's unclear: whether the bench config should point at a real (dev) router/CAKE or a no-op router backend to avoid mutating dev shaping.
   - Recommendation: bench config drives the dev host's own CAKE (the loop's router communication is part of the cycle budget being measured); ensure it targets the dev shaper, not production. If observe-only is acceptable for the idle arm, the under-load arm still must exercise the real router path for representativeness. Operator-confirm.

2. **CPU% measurement method.**
   - **RESOLVED:** CPUUsageNSec delta, sampled per-arm and rolled into evidence — the Plan 02 hygiene sampler emits a per-tick `cpu_nsec` field (`systemctl show -p CPUUsageNSec`), and the Plan 04 bench-run launcher records `cpu_nsec_start`/`cpu_nsec_end`/`cpu_nsec_delta`/`window_wall_sec`/`n_cores` into each per-arm evidence JSON. The Plan 03 gate-eval derives `cpu_pct = cpu_nsec_delta / (window_wall_sec*1e9*n_cores)*100` and gates `cpu_delta_pts = fping_arm.cpu_pct − icmplib_arm.cpu_pct` against the frozen `CPU_DELTA_PCT_POINTS = 2.0`.
   - What we know: D-04 requires a bounded CPU% delta (~2 pts, planner pre-commits the figure).
   - What's unclear: per-arm CPU% source — `systemctl show -p CPUUsageNSec` (cgroup CPU accounting, clean per-unit) vs `/proc/<pid>/stat` utime+stime sampling.
   - Recommendation: use `systemd` cgroup `CPUUsageNSec` deltas over the soak window divided by wall time × cores → %; it's per-unit and isolates the bench process tree. Pre-commit the exact figure in `phase243-thresholds.json`.

3. **Transient unit vs committed template — final choice.**
   - **RESOLVED:** transient `systemd-run --unit=... --collect` unit (throwaway, zero repo footprint, reversible) — the Plan 04 bench-run launcher uses the transient form; no committed `wanctl-bench@.service` template is added.
   - Recommendation: transient `systemd-run --unit=... --collect` (throwaway, zero repo footprint, reversible). Only commit a `wanctl-bench@.service` template if the planner wants the invocation pinned/reviewable in-repo; then it lives in `deploy/systemd/` and is in the SAFE-17 scaffolding allowlist (not a controller-path file).

## Environment Availability

> Probed on the research dev VM, which is NOT the .226/.233 deploy hosts. Authoritative check must run on the WAN hosts.

| Dependency | Required By | Available (dev VM) | Version | Fallback |
|------------|------------|-----------|---------|----------|
| `systemd-run` | D-01 throwaway unit | ✓ | — | committed `wanctl-bench@.service` template |
| `journalctl` | cycle NDJSON drain | ✓ | — | unit `StandardOutput=append:<file>` then tail |
| `flent` | under-load arm | ✓ | — | none (D-03 forbids iperf substitution) |
| `netperf` | flent RRUL transport | ✓ | — | none |
| `ss` / `lsof` | fd/port sampling | ✓ | — | `/proc/<pid>/fd` directly |
| `fping` | backend under test | ✗ (this VM) | — | **none** — must be present on .226/.233; absence makes the fping arm un-measurable (falls back to icmplib). |
| `python3` (stdlib) | all rollup/verdict scripts | ✓ | — | — |

**Missing dependencies with no fallback (on WAN hosts):** `fping` must be confirmed installed on both .226 and .233 before the run — it is the thing being measured.
**Missing dependencies with fallback:** journal capture can fall back to a unit file sink if `-o cat` drain is awkward.

## Validation Architecture

> nyquist_validation treated as enabled (no `workflow.nyquist_validation: false` found). This section drives VALIDATION.md.

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (`.venv/bin/pytest`), ruff, mypy per CLAUDE.md |
| Config file | `pyproject.toml` (project standard) |
| Quick run command | `.venv/bin/pytest tests/test_phase243_safe17_verifier.py -q` |
| Full suite command | `.venv/bin/pytest tests/ -q` (hot-path slice: see CLAUDE.md focused regression slice) |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| SAFE-17 | scaffolding-only; any `src/wanctl/` edit fails the boundary verifier (pinned to 243 close anchor) | unit (git-diff harness) | `.venv/bin/pytest tests/test_phase243_safe17_verifier.py -x` | ❌ Wave 0 (clone `test_phase241_safe17_verifier.py`) |
| SAFE-17 | verifier `--self-test` trips on a committed out-of-allowlist edit | shell self-test | `bash scripts/phase243-safe17-boundary-check.sh --self-test` | ❌ Wave 0 |
| BENCH-01 | cycle rollup parses `"Cycle timing"` NDJSON → avg/p99 per arm | unit | `.venv/bin/pytest tests/test_phase243_cycle_rollup.py -x` (fixture NDJSON) | ❌ Wave 0 |
| BENCH-01 | hygiene sampler emits well-formed fd/zombie/Tasks/cpu_nsec NDJSON | unit | `.venv/bin/pytest tests/test_phase243_hygiene_sampler.py -x` | ❌ Wave 0 |
| BENCH-02 | gate evaluator computes correct pass/fail vs frozen thresholds (delta%, ceiling, CPU delta, zombie, fd-trend, stall, n-floor) on fixtures | unit | `.venv/bin/pytest tests/test_phase243_gate_eval.py -x` | ❌ Wave 0 |
| BENCH-02 | pre-registration thresholds JSON exists & is committed before evidence (git-order assertion / presence check) | unit | `.venv/bin/pytest tests/test_phase243_prereg.py -x` | ❌ Wave 0 |
| BENCH-01/02 | end-to-end smoke: 60s real-unit run produces a non-empty `.profile.json` with `autorate_cycle_total` | manual (operator, on WAN host) | operator runbook step; collector errors if no cycle samples (built-in guard) | manual-only (requires real host + WAN) |

### Sampling Rate
- **Per task commit:** SAFE-17 mirror test + the relevant new script's unit test (quick run).
- **Per wave merge:** full `tests/` suite + `scripts/phase243-safe17-boundary-check.sh --self-test`.
- **Phase gate:** full suite green; `phase243-safe17-boundary-check.sh` PASS with evidence JSON; the actual benchmark run is operator-gated (real WAN hosts) and produces the verdict JSON — that verdict, against the pre-committed thresholds, is the BENCH-02 deliverable.
- **Live-run sampling floor (D-04c):** per arm `n >= max(10k cycles, 30 min)` ≈ 36k cycles at 20Hz; hygiene sampler at 1Hz over the same window.

### Wave 0 Gaps
- [ ] `tests/test_phase243_safe17_verifier.py` — clone of 241 mirror test, pinned to 243 `PHASE_CLOSE_ANCHOR`
- [ ] `tests/test_phase243_cycle_rollup.py` — NDJSON fixture → avg/p99 + stall-gap detector
- [ ] `tests/test_phase243_hygiene_sampler.py` — fd/zombie/Tasks/cpu_nsec NDJSON shape + trend test
- [ ] `tests/test_phase243_gate_eval.py` — frozen-threshold verdict logic on synthetic arms (pass + each fail mode, incl. CPU delta)
- [ ] `tests/test_phase243_prereg.py` — pre-registration artifact presence/shape
- [ ] `scripts/phase243-thresholds.json` + `243-BENCHMARK-PREREGISTRATION.md` committed **before** the run (BENCH-02 discipline)
- [ ] Framework install: none (pytest already present)

## Security Domain

> `security_enforcement` not set to `false` in config → treated as enabled. This phase adds no network-facing surface and no auth/crypto; it runs a throwaway local unit and reads `/proc` + journal.

### Applicable ASVS Categories
| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | benchmark is local operator-run; no new auth surface |
| V3 Session Management | no | — |
| V4 Access Control | yes (lightly) | bench unit must not bind the live health port / read-write production state; run as the wanctl service user, not root beyond `systemd-run` |
| V5 Input Validation | yes | gate evaluator + collector parse NDJSON/JSON from journal — fail-closed on malformed records (existing collector skips bad lines; gate must reject incomplete arms, not silently pass) |
| V6 Cryptography | no | no crypto introduced |
| V12 Files/Resources | yes | `--out` path confinement (the 242 verifier already enforces evidence-dir confinement + `..` rejection — clone that into the 243 verifier) |

### Known Threat Patterns for this stack
| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Bench unit collides with / corrupts live cake-autorate state | Tampering | unique unit name + port + lock + state path; `ss`/lock preflight |
| Malformed journal record silently passes the gate | Tampering / Repudiation | gate fails closed on incomplete arms / missing `autorate_cycle_total` (collector already errors) and on n below the D-04c floor |
| Path traversal in evidence `--out` | Tampering | clone the 242 verifier's realpath confinement to the evidence prefix + `..` rejection |
| Post-hoc threshold rationalization | Repudiation | thresholds committed in git **before** data; verdict references the frozen commit |
| Leftover bench process tree (zombies/orphans) | DoS (resource) | `--collect` teardown + post-run residue check (the hygiene sampler itself proves zero zombies) |

## Sources

### Primary (HIGH confidence — codebase, read this session)
- `src/wanctl/perf_profiler.py` — `OperationProfiler` p99, `record_cycle_profiling` "Cycle timing" emission
- `src/wanctl/wan_controller.py:2576-2660` — `run_cycle` PerfTimer wiring; `:4514` health `cycle_budget.profiler`; `:4420` `enable_profiling`
- `src/wanctl/autorate_continuous.py` — `--debug`/`--profile` flags, `build_rtt_backend()` call site (`_create_wan_components`)
- `src/wanctl/logging_utils.py:17-130,180-221` — `JSONFormatter`, `WANCTL_LOG_FORMAT`, console StreamHandler → journal
- `scripts/profiling_collector_json.py` — `"Cycle timing"` NDJSON → avg/p50/p95/p99 collector
- `scripts/soak_summary_aggregate.py` — stdlib `percentile()`/`histogram()`
- `scripts/soak-capture.sh` — NDJSON-per-tick soak pattern
- `src/wanctl/benchmark.py` — flent RRUL / netperf load path
- `scripts/phase242-safe17-boundary-check.sh` + `tests/test_phase241_safe17_verifier.py` — SAFE-17 clone pattern + PHASE_CLOSE_ANCHOR pinning
- `.planning/phases/242-.../evidence/safe17-boundary-242.json` — boundary evidence shape
- `configs/att.yaml`, `configs/spectrum.yaml`, `docs/PHASE220-MATRIX-RUNNER.md` — netperf target `104.200.21.31`, source IPs, `--bind-map spectrum=10.10.110.226`
- `.planning/phases/243-.../243-CONTEXT.md`, `REQUIREMENTS.md`, `ROADMAP.md` — locked decisions D-01..D-04c, BENCH-01/02, SAFE-17

### Secondary (MEDIUM)
- `scripts/phase206-gate-check.py`, `phase206-thresholds.json`, `phase224-gate-eval.py` — pre-registered-threshold verdict pattern (referenced, not fully read this session)

### Tertiary (LOW)
- None — no WebSearch needed; phase is fully codebase-internal.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — every asset read directly; cycle-budget capture path proven to exist.
- Architecture: HIGH — reuses existing instrumentation; minimal new surface, all in `scripts/`.
- Pitfalls: HIGH — TTY/pipe, collision, baseline, reaping all grounded in code + CONTEXT decisions.
- Live-run reachability (fping installed, netperf reachable, source binding): MEDIUM — must be confirmed on the .226/.233 hosts at run time (this research VM is not those hosts).

**Research date:** 2026-06-16
**Valid until:** ~2026-07-16 (stable; codebase-internal, low churn risk while v1.53 controller-path is frozen by SAFE-17)
