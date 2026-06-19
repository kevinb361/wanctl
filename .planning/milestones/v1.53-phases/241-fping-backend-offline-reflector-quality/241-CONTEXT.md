# Phase 241: fping Backend (Offline) + Reflector Quality - Context

**Gathered:** 2026-06-15
**Status:** Ready for planning

<domain>
## Phase Boundary

Build a selectable `fping` `RttBackend` that probes **off the 50ms control loop**
via one-shot subprocess bursts, binds source IP per WAN (`-S`), fans out across
reflectors in a single process, parses real fping 5.1 output loss-safely, survives
subprocess stall/death, and feeds per-reflector loss into reflector-quality
scoring — **all proven offline against captured fixtures**.

Delivers seven requirements:

- **FPING-01** — operator-selectable fping backend probing via one-shot
  `subprocess.run` bursts on a background cadence, never on the synchronous loop.
- **FPING-02** — `-S <source_ip>` binding per WAN, matching existing
  `ping_source_ip`.
- **FPING-03** — multiple reflectors in a single fping process, per-reflector
  results.
- **FPING-04** — parser built from captured real fping 5.1 samples; handles
  reply / total loss / partial loss / partial lines / banner / process-death;
  loss tokens → "no sample", **never recorded as 0ms**.
- **FPING-05** — tolerates subprocess stall/death without crashing the daemon
  (bounded timeout, recover-and-continue), mirroring `irtt_measurement.py`.
- **REFL-01** — per-reflector fping loss feeds reflector-quality scoring
  (additive, gated to fping backend) — the explicitly-accepted SAFE-17
  reflector-scorer exception.
- **SAFE-17** — controller-path edits stay inside the v1.53 allowlist
  (`fping_measurement.py` new, `rtt_backend.py`, `rtt_measurement.py`, factory/
  config/health wiring) plus the accepted reflector-scorer touch; fail-closed
  boundary verifier proves no other drift.

**This phase is OFFLINE.** All proof is against captured fixtures. No live A/B
(Phase 245), no factory/loud-fallback (Phase 242), no `/health` attribution
(Phase 244), no default flip (Phase 246).

**Carried forward (locked — do not re-litigate):**
- **Selection A** (`238-PROVENANCE-MAP.md:13`) — steering is the live RTT
  consumer; the backend is a real consumer target, not theoretical.
- **240 config** — `measurement.backend: icmplib|fping` enum is already validated
  and inert; 241 *reads* the resolved string, it does **not** re-touch the
  validators.
- `icmplib` stays default; no hard fping dependency (fallback is Phase 242).

</domain>

<decisions>
## Implementation Decisions

### fping Invocation + Output Mode
- **D-01:** Use **`-C count` (per-target timestamped)**, not `-c` (summary).
  Each ping is a real RTT or a `-` loss token, so the parser counts `-` tokens
  for **exact** per-reflector loss and FPING-04's "loss never read as 0ms"
  mandate falls out naturally. `-c` summary pre-aggregates and is exactly where a
  bad parse silently turns loss into a number — rejected.
- **D-02:** **Burst geometry `-C 5 -p 200ms`** (~1s burst, 20%-resolution
  per-burst loss). Rationale: `-C 1` collapses per-burst loss to 0%/100% and adds
  nothing over the scorer's rolling window; `-C 5` gives REFL-01 a real
  instantaneous per-cycle loss reading that the scorer window then smooths, at
  acceptable load. **Expose `-C`/`-p` as YAML knobs** under the fping backend
  config (defaults `5` / `200ms`).
- **D-02a:** fping's single-process fanout means burst duration ≈ `C × period`
  **regardless of reflector count** (reflectors are interleaved in one process) —
  this is the efficiency win over icmplib's ThreadPool-per-host and the basis for
  the cadence/timeout math in D-06.

### Parser (FPING-04)
- **D-03:** Parser is built **from captured real fping 5.1 output** (see D-08),
  not from a mental model of the format. Required scenarios: reply, total loss,
  partial loss, partial line (truncated/interrupted), banner/stderr noise, and
  process-death (killed mid-burst). Loss tokens (`-`) map to "no sample"; a host
  with **all** pings lost → `per_host_results[host] = None`,
  `per_host_loss[host] = 100.0`. A host with **no** reflectors yielding a sample
  → `probe()` returns `None` (matches the seam's documented all-fail contract).

### Aggregation → RttSample
- **D-04:** Reuse **`RTTAggregationStrategy.MEDIAN`** (already in
  `rtt_measurement.py`) for both per-host (median of that host's received pings)
  and cross-host aggregation into the single `RttSample.rtt_ms`. A
  partial-loss-but-alive reflector **still contributes** its received-ping median
  (see D-05). `RttSample.backend = "fping"`, `source_ip` set to the bound
  `-S` address, `per_host_loss` populated per reflector.

### Reflector-Scoring Feed (REFL-01 — the SAFE-17 exception)
- **D-05:** **Threshold loss%→bool, reuse the existing
  `ReflectorScorer.record_results(dict[str,bool])`** — scorer internals are
  **not** modified. This is the smallest possible SAFE-17 surface: the controller-
  path touch is the fping-gated *call site* that converts each reflector's burst
  loss to a success/fail boolean, not the scorer's scoring math.
- **D-05a:** Mapping is **any-loss-in-burst → fail** for that reflector's scorer
  window entry (default). A flaky-but-alive reflector is **penalized in scoring
  but still contributes its RTT** to `rtt_ms` — scoring and sample-usability are
  decoupled. **Expose the loss→fail threshold as a YAML knob** (default: any loss
  > 0%). The feed is **gated to the fping backend** — icmplib path behavior is
  byte-unchanged.

### Scheduling + Stall/Death Lifecycle (FPING-01, FPING-05)
- **D-06:** fping gets an **independent `cadence_sec` knob, irtt-style (default
  ~10s)** — NOT bound to the fast control interval (a ~1s burst can't fire every
  cycle). Subprocess **timeout = `(C × period) + grace`**, always **< cadence** so
  bursts never pile. `subprocess.TimeoutExpired` → `_log_failure`-style log →
  return `None` → recover-and-continue. Mirror `irtt_measurement.py`'s lifecycle
  shape (bounded run, failure-as-None, daemon never crashes).
- **D-07 (AMENDED 2026-06-15, cycle-2 review):** **Introduce a new cloned
  `FpingThread`** (modeled on `BackgroundRTTThread`) to drive the fping `probe()`
  on its independent `cadence_sec` (D-06). fping remains a second `RttBackend`
  implementing the same `probe(hosts) -> RttSample|None` contract Phase 239
  landed; there is still **no long-lived `fping -l` loop** — the thread fires
  bounded one-shot bursts on cadence, identical in shape to `BackgroundRTTThread`.

  **Amendment rationale (supersedes the original "reuse `BackgroundRTTThread`,
  no new scheduler thread" wording):** cloning `BackgroundRTTThread` into a
  dedicated `FpingThread` keeps the icmplib `BackgroundRTTThread` **byte-frozen**,
  which is the stronger SAFE-17 posture and is consistent with the byte-frozen
  `irtt_thread.py` precedent. Editing `BackgroundRTTThread` to take an independent
  cadence + a swappable backend would mutate a frozen controller-path file to
  serve only the fping path, contradicting SAFE-17's "icmplib path byte-unchanged"
  mandate. The clone lives inside the SAFE-17 allowlist (alongside the new
  `fping_measurement.py` / `rtt_measurement.py` mirror surface), and the original
  reuse intent — "no bespoke scheduler, same cadence-driven bounded-burst shape" —
  is preserved by modeling the clone directly on `BackgroundRTTThread`. The cost
  of the clone (a small amount of structural duplication) is explicitly accepted
  in exchange for not touching the frozen icmplib thread.

### Offline Fixture Capture (FPING-04 proof)
- **D-08:** Phase **ships a small capture helper script**; **operator (Kevin)
  runs it on the live host** to capture real fping 5.1 output for the six D-03
  scenarios; captured samples are **committed as test fixtures**. This satisfies
  "captured real 5.1 samples" genuinely and is repeatable. (Operator-in-the-loop:
  flag the capture step clearly in the plan so it isn't silently skipped.)

### Claude's Discretion (grounded)
- Exact extra fping flags (`-q` quiet, per-ping `-t` timeout, `-e` elapsed) —
  planner's choice provided D-01's per-ping `-C` output shape is preserved and the
  parser's fixtures match the exact invocation.
- Capture-script loss-induction method: e.g. an unreachable/blackhole IP for
  total loss, a deliberately lossy/distant target or `tc`-induced drop for partial
  loss, and a mid-burst `kill`/signal for process-death. Operator-run, so keep it
  safe and non-mutating to production routing.
- Module/file name for the new backend (allowlist names it `fping_measurement.py`)
  and the precise call-site wiring location for the REFL-01 boolean conversion,
  provided it stays fping-gated and inside the SAFE-17 allowlist.
- YAML key names/nesting for `-C`/`-p`/`cadence_sec`/loss-threshold under the
  fping backend config block — keep consistent with the 240 `measurement:` block
  naming and the `/health` `measurement` naming (Phase 244 forward-consistency).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase + milestone scope
- `.planning/ROADMAP.md` — Phase 241 entry (goal, 5 success criteria, deps:
  239 seam → may overlap 240) and the v1.53 phase spine (242 factory/fallback,
  243 benchmark gate, 244 health attribution, 245 A/B, 246 flip).
- `.planning/REQUIREMENTS.md` — FPING-01..05, REFL-01, SAFE-17 definitions; the
  binding out-of-scope table (NO controller threshold/algorithm/state-machine
  changes — EWMA, dwell, deadband, arbitration, fusion).
- `.planning/PROJECT.md` — v1.53 milestone thesis; in-scope source surface;
  "first controller-path-touching milestone in 10, ends SAFE-07..16 by design".
- `.planning/phases/238-rtt-provenance-verification-read-only-entry-gate/238-PROVENANCE-MAP.md`
  — Selection **A** ratification (`:13`); steering as live RTT consumer.

### The seam (Phase 239 output — what 241 implements against)
- `src/wanctl/rtt_backend.py` — `RttBackend` Protocol
  (`probe(hosts) -> RttSample|None`), `RttSample` fields (`rtt_ms`,
  `per_host_results`, `per_host_loss` percent, `backend`, `source_ip`),
  `sample_from_irtt_result` as the loss-mapping precedent. **fping implements
  this contract; `None` = no host yielded a sample.**

### Files this phase edits / mirrors (SAFE-17 allowlist)
- `src/wanctl/rtt_measurement.py` — `RTTMeasurement.probe()` (the icmplib
  conformer at `:325`), `ping_hosts_with_results` (per-host attribution pattern),
  `RTTAggregationStrategy` (MEDIAN reuse, D-04), and **`BackgroundRTTThread`**
  (`:412`, the cadence-driven thread to reuse — D-07).
- `src/wanctl/irtt_measurement.py` — the **lifecycle template** (FPING-05):
  `subprocess.run` with `timeout`, `TimeoutExpired` handling, `_log_failure`,
  advisory lock, failure-as-`None`. fping should rhyme with this.
- `src/wanctl/reflector_scorer.py` — `ReflectorScorer.record_results(dict[str,bool])`
  (`:134`), warmup/`min_score`/deprioritize/recover semantics. **REFL-01 feeds
  the existing interface; do NOT modify scoring math (D-05).**
- New `src/wanctl/fping_measurement.py` (allowlist-named) — the backend itself.

### Config (Phase 240 output — already validated, read-only here)
- `src/wanctl/check_config_validators.py` / `check_steering_validators.py` —
  `measurement.backend` enum already registered + validated. 241 does **not**
  edit these; it consumes the resolved string. New fping sub-param knobs
  (`-C`/`-p`/`cadence_sec`/loss-threshold) WILL need registration — confirm
  whether that lands here or is deferred; keep additive and inside SAFE-17.
- `src/wanctl/autorate_config.py` — `ping_source_ip` handling (`:643`) as the
  `-S` source for D-01/FPING-02; optional-key-with-default precedent.

### SAFE-17 boundary verifier
- The fail-closed controller-path git-diff verifier (Phase 238/239 output, run at
  every phase boundary) — all 241 edits must land inside the allowlist and prove
  zero out-of-allowlist drift before the phase closes.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `RttBackend` Protocol + `RttSample` (`rtt_backend.py`) — fping is a structural
  second implementation; `per_host_loss`/`backend`/`source_ip` fields already
  exist to carry fping's output. No new runtime type needed.
- `BackgroundRTTThread` (`rtt_measurement.py:412`) — the cadence-driven daemon
  thread with GIL-protected pointer swap; drive fping `probe()` through it (D-07).
  Note its current cadence binds to controller interval — fping overrides with an
  independent `cadence_sec` (D-06).
- `RTTAggregationStrategy.MEDIAN` (`rtt_measurement.py:83`) — reuse for per-host
  and cross-host aggregation (D-04); don't invent new aggregation.
- `ping_hosts_with_results` (`rtt_measurement.py:287`) — the per-host-attribution
  shape fping's per-reflector results should match for `RttSample.per_host_results`.
- `irtt_measurement.py` `_run_serialized` / `_parse_*` / `_log_failure` — the
  bounded-subprocess + failure-as-None lifecycle to mirror (FPING-05).
- `ReflectorScorer.record_results(dict[str,bool])` (`reflector_scorer.py:134`) —
  REFL-01's feed target; unchanged interface, fping-gated call site (D-05).

### Established Patterns
- One config file per WAN — "per WAN" `-S` binding and fping knobs fall out of the
  existing per-WAN layout; no special machinery.
- Backend-as-`probe()`-implementation (Phase 239 seam) — keeps consumers
  (autorate, revived steering pinger) unaware of which backend runs.
- `irtt_config.get("cadence_sec", 10.0)` (`autorate_continuous.py:484`) — the
  exact precedent for fping's independent cadence knob (D-06).

### Integration Points
- Phase 242 (factory + loud fallback) constructs this backend at the call sites
  and owns "fping binary absent" runtime handling — 241 builds the backend
  assuming it's selected; it does not build the factory or fallback.
- Phase 243 (cycle-budget benchmark) gates the `-C 5 -p 200ms` × cadence load
  choice (D-02) — keep the burst bounded and the geometry config-driven so 243 can
  measure it.
- Phase 244 (`/health` attribution) surfaces `backend`/`source_ip` — already on
  `RttSample`; keep config block naming consistent (D-02 Discretion).
- SAFE-17 verifier runs at the 241 boundary — confine edits to the allowlist.

</code_context>

<specifics>
## Specific Ideas

- Invocation skeleton: `fping -S <ping_source_ip> -C 5 -p 200 -q <reflector…>`
  (exact extra flags at planner discretion per D-01 Discretion).
- The `-` token is the load-bearing parser signal — a fixture-driven unit test
  must assert a `-`-heavy line is read as loss, never as `0.0ms`. This is the
  single highest-value FPING-04 regression.
- Capture script is operator-run on the **live host** — must not mutate production
  routing/shaping; total-loss via blackhole IP, process-death via mid-burst kill.

</specifics>

<deferred>
## Deferred Ideas

- **Backend factory + loud, observable runtime fallback when fping is absent**
  (FALL-01) — Phase 242.
- **`/health` `measurement.backend` / `source_ip` attribution** (HEALTH-01) —
  Phase 244 (fields already exist on `RttSample`).
- **Live A/B (icmplib vs fping) on the steering consumer under rollback anchor** —
  Phase 245.
- **Conditional production default flip to fping** — Phase 246.
- **Extending `ReflectorScorer` to ingest loss *fractions*** (vs the D-05
  boolean) — considered and rejected for this phase as a larger SAFE-17 surface;
  revisit only if the binary feed proves too coarse in the A/B.
- **`irtt` as a selectable backend** (IRTT-MIG-01) — future milestone; seam
  carries the value, config does not expose it in v1.53.

### Reviewed Todos (not folded)
- `2026-06-04-evaluate-fping-as-wanctl-rtt-measurement-backend.md` (score 0.6) —
  the **milestone driver**, broader than Phase 241 (spans config/factory/health/
  A/B/flip across Phases 240–246). 241 satisfies its backend-build + parser +
  source-binding + fixtures + reflector-loss items; the A/B/default-flip items
  belong to 245/246. Kept open as the milestone-level tracker.
- `2026-04-17-monitor-flapping-peak-count-on-next-docsis-event.md` (score 0.6,
  alerting) and `2026-04-17-investigate-steering-degraded-on-clean-restart.md`
  (score 0.4, steering) — keyword matches only; unrelated to the fping backend.
  Not folded.

</deferred>

---

*Phase: 241-fping-backend-offline-reflector-quality*
*Context gathered: 2026-06-15*
