# Phase 243: Cycle-Budget Benchmark Gate - Context

**Gathered:** 2026-06-16
**Status:** Ready for planning

<domain>
## Phase Boundary

Build a **pre-registered, committed-before-the-run** cycle-budget + CPU benchmark
that proves `fping` introduces **no 50ms cycle-budget regression** under a **real
systemd unit**, and that acts as a **hard gate blocking the Phase 245 live A/B** on
any regression (cycle budget, fd/zombie/Tasks leak, or systemd STALL).

Delivers three requirements:

- **BENCH-01** — operator can run an **idle-and-under-load** cycle-budget + CPU
  benchmark of `fping` vs `icmplib` under a real systemd unit (not an interactive
  shell — TTY-vs-pipe is the STALL fingerprint).
- **BENCH-02** — a **pre-registered** no-regression gate, committed before the run,
  blocks the live A/B if fping regresses cycle budget (vs `avg≈2.85ms` /
  `p99≈6.9ms` baseline), leaks file descriptors or zombies, or stalls under
  systemd.
- **SAFE-17** — controller-path edits stay inside the v1.53 allowlist; fail-closed
  boundary verifier proves no out-of-allowlist drift.

**This is a measurement + gate phase, not a behavior-change phase.** No controller
thresholds/algorithms/state machines change. The benchmark is throwaway scaffolding
+ evidence + a pre-committed verdict; the controller hot path is read-only.

**Carried forward (locked — do not re-litigate):**
- **Selection A** (`238-PROVENANCE-MAP.md:13`) — steering is the live RTT consumer;
  fping runs **off-loop** on `FpingThread` (`fping_measurement.py:281`), never on
  the synchronous 50ms loop. So direct per-cycle cost should be ~zero; the gate is
  really about **tail contention** (p99) and CPU%, not the average.
- **icmplib stays default**; no hard fping dependency (242 FALL-01/02).
- **Prod is both-WAN cake-autorate**; `wanctl@` disabled since 2026-06-08. The
  wanctl 50ms control loop is **not** running in prod — which is exactly why the
  benchmark uses a throwaway unit, not the live service (see D-01).
- **242 factory** (`build_rtt_backend()`) is the single construction site the
  benchmark drives to select between backends.

</domain>

<decisions>
## Implementation Decisions

### Benchmark Vehicle + Host (D-01)
- **D-01:** **Throwaway/transient systemd unit, NOT a wanctl@ revive.** A
  purpose-built transient unit (`systemd-run --unit=...` or a committed
  `wanctl-bench@.service` template) runs the **real wanctl controller loop**
  (`autorate_continuous.py`, 50ms `CYCLE_INTERVAL_SECONDS`) with each backend.
  Rationale: the hard requirement is "real systemd unit, not interactive shell"
  because **TTY-vs-pipe is the STALL fingerprint** — fping/subprocess stdout
  buffering behaves differently when stdout is a journal pipe under systemd vs a
  TTY. A purpose-built unit satisfies that exactly, is fully reversible, and avoids
  entangling with prod state (wanctl@ is disabled; prod is cake-autorate). The
  Phase 217 method (revive wanctl@ + profiling ExecStart override) was explicitly
  **rejected** as heavier and prod-state-conflating.
- **D-01a:** **Run on BOTH dev WANs — `.226` (Spectrum) and `.233` (ATT).** The
  gate covers both egress paths and reflector sets. fping probes **live reflectors
  out the real WAN source IP** (`-S` binding) so the fork/exec/parse cost is real,
  not synthetic.
- **D-01b:** Arms = 2 backends (icmplib, fping) × {idle, under-load} × 2 WANs =
  **8 arms**.

### Comparison Basis (D-02)
- **D-02:** **Same-run icmplib control arm is the PRIMARY gate; historical
  `2.85ms`/`6.9ms` is a SECONDARY representativeness anchor.** The no-regression
  gate fires on the **fping − icmplib delta measured on the identical host, same
  run, same load** — this controls for dev-host CPU/kernel drift vs the prod
  Spectrum baseline. The historical baseline (Phase 217: `cycle_total.avg_ms=2.883`
  / `p99_ms=6.9` over 71,560 samples; Phase 219 D-27: `avg_ms=2.857` / `p99_ms=6.4`
  over 73,603) only validates that the **dev icmplib arm is itself representative**
  — if dev-icmplib comes out wildly off `~2.85/6.9`, the host isn't representative
  and the whole run is suspect (re-run on a better host before trusting the gate).

### Load Generation (D-03)
- **D-03:** **Reuse each WAN's established flent/netperf load path.** "Under load"
  = real WAN saturation (flent RRUL) so the controller is in active CAKE
  rate-adjustment with elevated RTT (more work per cycle) **while** fping bursts
  fire and contend for CPU/scheduler — the contention the gate must catch. Spectrum
  → flent RRUL over netperf to the Dallas Linode (`104.200.21.31`, the existing
  hourly path); ATT → its established netperf target (planner to confirm exact
  server). **No iperf, no synthetic CPU load** — memory flags swapping
  netperf→iperf as requiring approval, and reusing netperf keeps load conditions
  consistent with the historical baseline. Idle arm = no generated load.

### Pre-Registered Gate Thresholds (D-04) — committed BEFORE the run
- **D-04 (cycle budget):** fping must not regress **avg OR p99 by more than 20%**
  vs the same-run icmplib arm, **AND** fping **p99 must stay under an absolute
  10ms ceiling** (5× headroom on the 50ms budget). **CPU% delta bounded** (target
  `< 2` percentage points vs icmplib arm; planner may refine the exact figure but
  it must be pre-committed). Relative-delta-only and absolute-ceiling-only postures
  were rejected — both layers are wanted (catch relative regression AND any
  absolute blowup).
- **D-04a (subprocess hygiene — hard):** **Zombies strictly zero** (any zombie =
  reaping bug = fail). **File descriptors flat over the soak** — no monotonic
  upward trend (bounded jitter OK). **Tasks/threads (systemd `Tasks=`)
  bounded/stable** — no unbounded growth.
- **D-04b (STALL — the TTY-vs-pipe fingerprint):** under the unit (stdout =
  journal pipe, not TTY), **zero stall events** — no cycle gap `> 2× budget`
  (`>100ms`) attributable to a backend burst, and every fping burst returns within
  its bounded timeout. A pipe-buffering hang manifests as cycle-gap spikes /
  missed cycles.
- **D-04c (sample floor for validity):** **≥30 min per arm AND ≥10k cycles**
  (whichever is larger). At 20Hz, 30 min ≈ 36k cycles — about half the ~72k
  historical baseline n, ample for stable p99 tail estimation.

### Claude's Discretion (grounded)
- Exact benchmark harness shape: transient `systemd-run` invocation vs a committed
  `wanctl-bench@.service` template; how the controller is launched in a
  benchmark/observe mode; how the throwaway unit is torn down. Must keep stdout on a
  journal pipe (not TTY) and stay inside the SAFE-17 allowlist (scaffolding /
  scripts / evidence only — no controller hot-path edits).
- Exact pre-registration artifact format and location (e.g. a
  `243-BENCHMARK-PREREGISTRATION.md` committed before the run + an evidence JSON +
  recorded verdict). The hard rule: thresholds are committed **before** data
  collection; the verdict is recorded against them after.
- Exact CPU% delta figure and any per-WAN threshold nuance, provided they are
  pre-committed and consistent with D-04.
- How fd/zombie/Tasks counts are sampled over the soak (e.g. `/proc`, `systemctl
  show -p Tasks`, `ss`/`lsof`) and how the "flat / bounded" trend test is computed.
- ATT's exact netperf load target.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase + milestone scope
- `.planning/ROADMAP.md` — Phase 243 entry (goal, 4 success criteria, deps: 242)
  and the v1.53 spine (243 gate → 244 health attribution → 245 A/B → 246 flip).
- `.planning/REQUIREMENTS.md` — BENCH-01, BENCH-02, SAFE-17 definitions; the
  out-of-scope table (NO per-cycle `subprocess.run`; probing runs on a background
  cadence) and AB-03 (the Phase 245 A/B verdict criteria this gate is a precondition
  for).
- `.planning/PROJECT.md` — v1.53 milestone thesis; **baseline provenance**: Phase
  217 `cycle_total.avg_ms=2.883`/`p99_ms=6.9` over 71,560 samples (`:166`, `:241`,
  `:699`) and Phase 219 D-27 `avg_ms=2.857`/`p99_ms=6.4` over 73,603 samples
  (`:140`, `:240`). These are the historical icmplib-era anchor (D-02).
- `.planning/phases/242-backend-factory-loud-fallback/242-CONTEXT.md` — the
  `build_rtt_backend()` factory the benchmark drives; D-04 bundle (backend + thread).
- `.planning/phases/238-rtt-provenance-verification-read-only-entry-gate/238-PROVENANCE-MAP.md`
  — Selection A (`:13`); off-loop fping consumption model.

### Cycle-budget instrumentation (what the benchmark measures)
- `src/wanctl/perf_profiler.py` — `OperationProfiler` (`:66`) accumulates per-cycle
  timings and computes min/max/avg/p95/**p99** (`:139-143`). The cycle-budget metric
  source.
- `src/wanctl/autorate_continuous.py` — the 50ms control loop (`:1266` `while`,
  `CYCLE_INTERVAL_SECONDS` sleep at `:1297-1299`; daemon banner `:284`). The loop
  whose budget is being gated, and the first `build_rtt_backend()` call site
  (`_create_wan_components` `:120`/`:145`).

### Backends under test
- `src/wanctl/fping_measurement.py` — `FpingMeasurement.probe()` (`:73`),
  `FpingThread` (`:281`, independent `cadence_sec`, asserts `timeout < cadence`).
  The off-loop fping path whose contention the gate measures.
- `src/wanctl/rtt_measurement.py` — `RTTMeasurement` (`probe()` `:325`, accepts
  `source_ip=`) + `BackgroundRTTThread` (`:412`). The icmplib control arm.
- `src/wanctl/rtt_backend.py` — `RttBackend` Protocol + `RttSample` seam both
  backends conform to.

### Soak / load-gen harness (reusable scaffolding)
- `scripts/soak-capture.sh` — NDJSON-per-second soak capture harness (env-driven,
  bounded failure tolerance). Precedent for the over-soak fd/zombie/Tasks sampling.
- `scripts/soak-monitor.sh`, `scripts/soak_summary_aggregate.py` — stdlib-only
  NDJSON p50/p95/**p99** aggregator (`soak_summary_aggregate.py`); reusable to
  compute cycle-budget arm statistics with no NumPy/pandas dependency.
- `src/wanctl/benchmark.py` — the `wanctl-benchmark` flent RRUL harness (netperf,
  Dallas Linode `104.200.21.31`). NOTE: this is a *bufferbloat latency* benchmark,
  NOT a cycle-budget benchmark — but it is the **load-generation** path reused for
  D-03's "under load" arm.

### SAFE-17 boundary verifier (clone-and-extend pattern)
- `scripts/phase242-safe17-boundary-check.sh` (+ `tests/test_phase241_safe17_verifier.py`
  pattern) — the fail-closed controller-path git-diff verifier cloned per phase.
  243 needs its own `phase243-safe17-boundary-check.sh` + mirror test, allowlisting
  only benchmark scaffolding/scripts/evidence (no controller hot-path edits).
- `.planning/phases/242-backend-factory-loud-fallback/evidence/safe17-boundary-242.json`
  — the prior boundary evidence shape to mirror.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `OperationProfiler` (`perf_profiler.py:66`) — already computes avg/p95/p99 over
  accumulated cycle samples; the cycle-budget metric engine, no new stats code
  needed.
- `soak_summary_aggregate.py` — stdlib NDJSON → p50/p95/p99 aggregator; reuse for
  per-arm cycle-budget rollups (no NumPy/pandas).
- `soak-capture.sh` — env-driven NDJSON soak loop with bounded failure tolerance;
  precedent/scaffold for sampling fd/zombie/Tasks counts over the soak window.
- `benchmark.py` / `wanctl-benchmark` (flent RRUL over netperf, Dallas Linode) —
  the established load generator for the "under load" arm (D-03).
- `build_rtt_backend()` (242 factory) — single construction site the benchmark uses
  to swap backends deterministically.

### Established Patterns
- **Backend runs off the 50ms loop** (Phase 239/241 seam) — fping is a background
  `FpingThread`, so the gate measures *contention*, not direct per-cycle cost.
- **Per-WAN config files** — per-WAN `source_ip`/backend selection falls out of the
  existing layout; both dev WANs (.226/.233) configure independently.
- **SAFE-17 verifier cloned per phase** (238→242) — 243 follows the same
  fail-closed git-diff boundary pattern, allowlisting only scaffolding.
- **Phase 217 profiling methodology** — operator-gated, pre-registered cycle capture
  with a validated journal-streaming collector; 243 reuses the *discipline*
  (pre-registration, journal/pipe capture) but a throwaway unit instead of the live
  service (D-01).

### Integration Points
- **Phase 245 (live A/B)** consumes this gate's verdict as a **hard precondition** —
  a regression verdict blocks the A/B. The pre-registered thresholds here must be
  consistent with AB-03's A/B verdict criteria.
- **SAFE-17 verifier** runs at the 243 boundary — all edits confined to benchmark
  scaffolding/scripts/evidence; zero controller hot-path drift.

</code_context>

<specifics>
## Specific Ideas

- Pre-registration discipline: commit a `243-BENCHMARK-PREREGISTRATION.md` (the
  D-04 thresholds) **before** collecting data; record the verdict against it after.
  The whole point of BENCH-02 is the gate can't be rationalized post-hoc.
- Single highest-value validity check: the **dev icmplib arm** must land near the
  `~2.85ms`/`6.9ms` historical anchor (D-02). If it doesn't, the host is
  unrepresentative — fix the host before trusting any fping verdict.
- Single highest-value STALL test: run the benchmark unit with stdout on a journal
  pipe (NOT a TTY) and assert no cycle gap `>100ms` + every fping burst returns
  within timeout — that reproduces the TTY-vs-pipe fingerprint the gate exists for.
- "Keep icmplib" is a legitimate passing outcome at the milestone level (AB-03) —
  this gate's job is only to block the A/B on *regression*, not to prefer fping.

</specifics>

<deferred>
## Deferred Ideas

- **The live A/B itself** (icmplib vs fping on the Phase-238 target, one WAN under
  test, under a Snapshot-A rollback anchor) — Phase 245. This phase only gates it.
- **Full per-sample `/health` `backend`/`source_ip` attribution** (HEALTH-01) —
  Phase 244.
- **Conditional production default flip to fping** — Phase 246 (operator-gated,
  armed rollback).
- **Runtime backend hot-swap / stateful demotion watcher** — rejected in 242
  (D-02a); not revisited here.

None of these belong in 243 — discussion stayed within the benchmark-gate scope.

</deferred>

---

*Phase: 243-cycle-budget-benchmark-gate*
*Context gathered: 2026-06-16*
