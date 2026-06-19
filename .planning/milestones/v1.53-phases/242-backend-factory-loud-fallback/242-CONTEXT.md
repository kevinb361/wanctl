# Phase 242: Backend Factory + Loud Fallback - Context

**Gathered:** 2026-06-15
**Status:** Ready for planning

<domain>
## Phase Boundary

Introduce `build_rtt_backend()` — a single factory that centralizes RTT-backend
construction for **both** consumers (autorate + steering) and falls back to
`icmplib` **automatically and loudly** whenever `fping` is unavailable, never
silently.

Delivers three requirements:

- **FALL-01** — when the `fping` binary is unavailable, the factory falls back to
  `icmplib` automatically.
- **FALL-02** — fallback is loud and observable (WARN-once + fallback counter +
  `/health` attribution), never silent.
- **SAFE-17** — controller-path edits stay inside the v1.53 allowlist (factory +
  additive `/health`/wiring); fail-closed boundary verifier proves no
  out-of-allowlist drift.

**This is a centralization + observability phase, not a behavior-change phase.**
Construction moves into one factory; fallback is loud but **construction-time
only**; `/health` gains a thin observable signal. The risky *live consumption*
change for steering is explicitly **deferred to Phase 245** under the rollback
anchor.

**Carried forward (locked — do not re-litigate):**
- **Selection A** (`238-PROVENANCE-MAP.md:13`) — steering is the live RTT
  consumer; its currently-dead `RTTMeasurement` (`daemon.py:2554`) is the real
  A/B target. Steering today consumes autorate's `/health` `measurement` object,
  **not** its own pinger.
- **icmplib stays default**; no hard fping dependency — the entire point of
  FALL-01/02.
- **240 config** — `measurement.backend: icmplib|fping` enum is already validated
  and inert; 242 *consumes* the resolved string, it does **not** re-touch the
  validators.
- **241 backend** — `FpingMeasurement.probe()` (`fping_measurement.py:73`) +
  `FpingThread` (`:281`, independent `cadence_sec`) exist and conform to the
  Phase 239 `RttBackend` seam. 242 constructs them, it does not rebuild them.

</domain>

<decisions>
## Implementation Decisions

### Steering Wiring Scope (D-01)
- **D-01:** **Route construction only.** `build_rtt_backend()` becomes the single
  construction site for **both** `autorate_continuous.py` (`:145`) **and**
  `steering/daemon.py` (`:2554`) — satisfying Success Criterion 3 literally
  (238 *did* route steering there via Selection A). But steering's pinger stays
  **dead**: it still consumes the autorate `/health` baseline. Reviving actual
  *consumption* (replacing the `/health` baseline read with its own pinger) is the
  live, higher-blast-radius change, **deferred to Phase 245's A/B under the
  rollback anchor**. This mirrors 240's staging logic ("wire both now so the next
  phase only flips, tighter per-phase SAFE-17 surface").
- **D-01a:** **Design `source_ip` binding correctly at the steering factory call
  now.** 238 flagged that `daemon.py:2554` constructs `RTTMeasurement` with **no
  `source_ip=`** argument (the `-S`-equivalent binding). The factory must plumb
  the correct per-WAN source so Phase 245 inherits a correct binding when it flips
  consumption live. Constructing it correctly is harmless while consumption stays
  dead.

### Fallback Trigger Boundary (D-02)
- **D-02:** **Construction-time `shutil.which('fping')` only.** Fallback is a
  one-time decision at `build_rtt_backend()` time: `backend == 'fping'` selected
  but binary missing → construct `icmplib` instead, loudly (D-03). Runtime fping
  subprocess stall/death stays **241's job** — `FpingThread` already does
  failure-as-`None`, recover-in-place, daemon-never-crashes (241 D-05/D-06).
  Clean separation: the **factory owns "is fping installable"**, the **thread owns
  "did this burst fail."** Matches FALL-01's literal "binary is unavailable"
  wording.
- **D-02a:** No runtime backend hot-swap / stateful demotion watcher in 242 —
  explicitly rejected as new controller-path machinery, a larger SAFE-17 surface,
  and overlapping 241's recover-in-place. (Captured under Deferred.)

### `/health` Attribution Split — FALL-02 vs Phase 244 (D-03)
- **D-03:** **Minimal fallback signal only.** 242 adds **additive** `/health`
  keys sufficient to make fallback observable: the **active backend name** (what
  actually ran after any fallback) + a **fallback flag/counter** (e.g.
  `backend_active`, `fell_back`, `fallback_count`). **Full per-sample
  `backend`/`source_ip` attribution metadata stays Phase 244 (HEALTH-01).** The
  three existing `measurement` fields steering depends on — `available`,
  `raw_rtt_ms`, `staleness_sec` — must remain **byte-preserved** (238's mandate).
  FALL-02's three pillars map as: WARN-once (log) + counter (here) + `/health`
  attribution (this minimal slice; 244 enriches it).
- **D-03a:** Exact key names/nesting are planner discretion provided they are
  additive, stay consistent with the 240 `measurement:` block and the 244-forward
  `/health` `measurement` naming, and do not mutate the three preserved fields.

### Factory Return Shape (D-04)
- **D-04:** **Factory returns the backend AND its pre-wired driver thread as a
  bundle.** icmplib → `BackgroundRTTThread`; fping → `FpingThread` (with its
  independent `cadence_sec`). The two thread classes are not interchangeable and
  cadence differs per backend, so the factory hides **all** that divergence. Both
  call sites collapse to `backend, thread = build_rtt_backend(...)` with **zero
  backend-type branching** — the strongest reading of "single construction site"
  (Criterion 3).
- **D-04a:** Exact return *shape* (tuple vs small dataclass/handle object) is
  planner/executor discretion, provided call sites don't branch on backend type
  and it stays inside the SAFE-17 allowlist.

### Claude's Discretion (grounded)
- Exact factory module location (new file vs in `rtt_backend.py`) and the precise
  signature (`config`, `source_ip`, `shutdown_event`, `logger`), provided it is
  the single construction site for both consumers and stays in the SAFE-17
  allowlist.
- WARN-once scoping (per-process vs per-WAN) and fallback-counter location
  (in-process vs persisted) — planner's choice; "loud + observable, never
  silent" (FALL-02) is the only hard constraint.
- When falling back to icmplib because fping is absent, the icmplib path is
  constructed via the **existing** `RTTMeasurement` + `BackgroundRTTThread`
  construction (its own params/defaults) — fping-specific sub-params (`-C`/`-p`/
  `cadence_sec`/reflector loss-threshold) simply don't apply on the icmplib path.
- Exact `/health` key names/nesting for the D-03 minimal fallback signal.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase + milestone scope
- `.planning/ROADMAP.md` — Phase 242 entry (goal, 4 success criteria, deps: 240 +
  241; note Criterion 3's conditional "if Phase 238 routed it there" — it did) and
  the v1.53 spine (243 benchmark gate, 244 health attribution, 245 A/B, 246 flip).
- `.planning/REQUIREMENTS.md` — FALL-01, FALL-02, SAFE-17 definitions; the binding
  out-of-scope table (NO controller threshold/algorithm/state-machine changes —
  EWMA, dwell, deadband, arbitration, fusion; no hard fping dependency).
- `.planning/PROJECT.md` — v1.53 milestone thesis; "first controller-path-touching
  milestone in 10; SAFE-07..16 zero-diff streak ends by design, replaced by the
  narrowed SAFE-17 allowlist."
- `.planning/phases/238-rtt-provenance-verification-read-only-entry-gate/238-PROVENANCE-MAP.md`
  — **Selection A** ratification (`:13`); the dead-`RTTMeasurement` analysis
  (`:2554` constructs with **no `source_ip`**, `:1137` stores it, never called);
  steering consumes `/health` `measurement.{available,raw_rtt_ms,staleness_sec}`
  (`:1000-1024`) — the three fields 244 must byte-preserve.

### The seam (Phase 239 — what the factory constructs against)
- `src/wanctl/rtt_backend.py` — `RttBackend` Protocol (`:20`,
  `probe(hosts) -> RttSample|None`), `RttSample` (`:37`) fields
  (`rtt_ms`/`per_host_results`/`per_host_loss`/`backend`/`source_ip`),
  `IrttRttBackend` (`:94`). Both icmplib and fping conform to this contract.

### Backends the factory selects between (241 + icmplib)
- `src/wanctl/fping_measurement.py` — `FpingMeasurement.probe()` (`:73`) and
  `FpingThread` (`:281`, independent `cadence_sec`, asserts `timeout < cadence`).
  The fping half of the bundle (D-04).
- `src/wanctl/rtt_measurement.py` — `RTTMeasurement` (the icmplib conformer,
  `probe()` at `:325`; accepts `source_ip=` and passes it to `icmplib.ping(...,
  source=...)` ~`:199-207`) and `BackgroundRTTThread` (`:412`). The icmplib half
  of the bundle and the fallback target.

### Construction sites the factory replaces (Criterion 3)
- `src/wanctl/autorate_continuous.py` — `_create_wan_components` (`:120`)
  constructs `RTTMeasurement(...)` at `:145`. First factory call site. (`IRTTThread`
  pattern at `:469-485` / `:1091-1103` is the thread-lifecycle precedent.)
- `src/wanctl/steering/daemon.py` — `_create_steering_components` constructs the
  **dead** `RTTMeasurement` at `:2554` (returned `:2561`, passed into
  `SteeringDaemon` at `:2671`, stored `:1137`). Second factory call site;
  consumption stays dead until Phase 245 (D-01).

### `/health` (FALL-02 + 244 boundary — D-03)
- `src/wanctl/health_check.py` — the native wanctl@ `/health` `measurement` shape;
  242 adds additive fallback-signal keys, preserves the three steering-consumed
  fields byte-for-byte.

### SAFE-17 boundary verifier
- The fail-closed controller-path git-diff verifier (Phase 238/239 output, run at
  every phase boundary) — all 242 edits must land inside the allowlist (factory +
  additive `/health`/wiring) and prove zero out-of-allowlist drift before close.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `RttBackend` Protocol + `RttSample` (`rtt_backend.py`) — the factory returns
  Protocol-conforming backends; `backend`/`source_ip` fields already exist to carry
  attribution. No new runtime type needed.
- `RTTMeasurement` + `BackgroundRTTThread` (`rtt_measurement.py:325`/`:412`) — the
  icmplib half of the D-04 bundle and the D-02 fallback target. `RTTMeasurement`
  already accepts `source_ip=` (D-01a's steering binding fix uses this).
- `FpingMeasurement` + `FpingThread` (`fping_measurement.py:73`/`:281`) — the fping
  half of the bundle; `FpingThread` enforces `timeout < cadence_sec` at construction.
- `shutil.which("fping")` — already the 240 validator's absence probe (240 D-03);
  242's runtime fallback reuses the same primitive at construction time (D-02).
- `IRTTThread` lifecycle in `autorate_continuous.py` (`:469-485`, stop at
  `:1091-1103`) — the start/stop precedent for whichever thread the factory bundles.

### Established Patterns
- One config file per WAN — per-WAN `source_ip` and backend selection fall out of
  the existing layout; no special machinery.
- Backend-as-`probe()`-implementation (Phase 239 seam) — keeps consumers unaware
  of which backend runs; the factory is the only place that knows.
- 240's "define in both consumers now so the next phase only consumes" — D-01
  applies the same staging to construction (wire both sites in 242, flip steering
  consumption in 245).

### Integration Points
- Phase 243 (cycle-budget benchmark) benchmarks whichever backend the factory
  builds under a real systemd unit — keep construction deterministic + observable.
- Phase 244 (`/health` attribution) enriches the D-03 minimal signal into full
  per-sample `backend`/`source_ip` attribution — keep 242's keys additive and
  244-forward-consistent.
- Phase 245 (live A/B) flips steering to **consume** its factory-built backend
  under the rollback anchor — D-01/D-01a leave it a correct, `source_ip`-bound
  construction to turn on.
- SAFE-17 verifier runs at the 242 boundary — confine edits to the allowlist.

</code_context>

<specifics>
## Specific Ideas

- Call-site target shape (D-04): both sites become
  `backend, thread = build_rtt_backend(config, source_ip, shutdown_event, logger)`
  with no backend-type branching at the call site.
- Fallback skeleton (D-02/D-03): `if backend == "fping" and not which("fping"):
  WARN-once + fallback_count++ + construct icmplib; else construct selected`.
- The single highest-value FALL-02 regression test: assert that with `fping`
  selected and the binary absent, the process (a) runs on icmplib and (b) emits
  the WARN + counter + `/health` fallback signal — i.e. proves "loud, never
  silent."
- The single highest-value SAFE-17 / 238 regression test: assert the three
  steering-consumed `/health` fields (`available`, `raw_rtt_ms`, `staleness_sec`)
  are byte-identical before/after the additive 242 keys.

</specifics>

<deferred>
## Deferred Ideas

- **Reviving steering's pinger to CONSUME its own RTT live** (replacing the
  `/health` baseline read) — Phase 245, under the Snapshot-A rollback anchor
  (D-01).
- **Full per-sample `/health` `backend`/`source_ip` attribution** (HEALTH-01) —
  Phase 244 (D-03).
- **Runtime backend hot-swap / stateful demotion watcher** (swap fping→icmplib
  mid-flight after N runtime deaths) — rejected for 242 as new controller-path
  machinery and a larger SAFE-17 surface; runtime recovery stays 241's
  `FpingThread` (D-02a). Revisit only if construction-time fallback proves
  insufficient in the A/B.
- **Conditional production default flip to fping** — Phase 246.
- **`irtt` as a selectable backend** (IRTT-MIG-01) — future milestone; the seam
  carries the value, config does not expose it in v1.53.

### Reviewed Todos (not folded)
- `2026-06-04-evaluate-fping-as-wanctl-rtt-measurement-backend.md` — the v1.53
  milestone driver, broader than Phase 242 (spans 240–246). 242 satisfies its
  factory + fallback + observability items; A/B and default-flip items belong to
  245/246. Kept open as the milestone-level tracker.

</deferred>

---

*Phase: 242-backend-factory-loud-fallback*
*Context gathered: 2026-06-15*
