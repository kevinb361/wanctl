# Phase 187: RTT Cache And Fallback Safety - Research

**Researched:** 2026-04-15
**Domain:** wanctl autorate — background RTT cache, measurement-degradation
consumption, ICMP/TCP fallback path, regression testing
**Confidence:** HIGH

## Summary

Phase 187 is the behavioral twin of Phase 186. Phase 186 landed an additive,
machine-readable measurement-health contract on `wan_health[wan].measurement`
(`state`, `successful_count`, `stale`). Phase 186 deliberately did **not**
change how the controller reacts when reflector measurement collapses — that
is Phase 187's job.

The concrete gap in today's code is this: when
`BackgroundRTTThread._run()` observes a cycle in which zero reflectors
produced a successful RTT, it intentionally **does not** overwrite its
`_cached` `RTTSnapshot` ("stale data preferred over no data -- do NOT
overwrite _cached", `src/wanctl/rtt_measurement.py:447`). `WANController.measure_rtt()`
then reads `get_latest()`, accepts the cached snapshot up to a hard 5-second
cutoff (`src/wanctl/wan_controller.py:930`), and **republishes** that stale
snapshot through `_record_live_rtt_snapshot()` as if it were current. That
republish populates `_last_raw_rtt`, `_last_raw_rtt_ts`,
`_last_active_reflector_hosts`, and `_last_successful_reflector_hosts` with
the **prior** successful-cycle values. The Phase 186 contract then happily
reports `state="healthy"` and `successful_count=3` because it counts the
last-successful hosts, not the current-cycle hosts. This is the exact
"healthy/GREEN while tcp_12down p99 = 3059ms" failure the live investigation
captured.

Phase 187 must break the implicit assumption that "cached == current" in the
zero-success path without touching the existing `handle_icmp_failure()` /
`verify_connectivity_fallback()` total-outage path, which is validated and
should not be disturbed. It must also avoid threshold retuning, new YAML
surfaces, and any broadening of control policy.

**Primary recommendation:** Teach `BackgroundRTTThread` to publish a
**current-cycle status** alongside the preserved `_cached` snapshot, wire
`WANController._record_live_rtt_snapshot()` so that a zero-success current
cycle updates `_last_active_reflector_hosts` and
`_last_successful_reflector_hosts` from the **current** cycle (not from the
preserved snapshot), and keep `_last_raw_rtt` / `_last_raw_rtt_ts` unchanged
so the existing `staleness_sec` contract stays honest. `measure_rtt()`
continues to return a usable `rtt_ms` to the controller under the existing
5-second hard cutoff — but the machine-readable measurement-health contract
now correctly reports `state="collapsed"` **and** `stale` reflects the real
age of the last successful cycle. No new control branch is required: the
controller's existing behavior when measurement is "healthy-but-aging" is
preserved; downstream consumers of the Phase 186 contract (operators, tests,
Phase 188 verification) gain a trustworthy signal.

## User Constraints (from CONTEXT.md)

Phase 187 has **no CONTEXT.md** yet (this research runs before discuss).
The planner should treat the following as hard constraints derived from
`.planning/REQUIREMENTS.md`, `.planning/ROADMAP.md`, `CLAUDE.md`, and the
Phase 186 decisions that Phase 187 consumes:

### Locked Decisions (carried from Phase 186 contract + ROADMAP)

- The Phase 186 contract on `wan_health[wan].measurement` is additive and
  final for v1.38 — Phase 187 consumes it, it does not reopen it.
- The existing ICMP-failure → TCP-fallback → total-connectivity-loss path
  (`handle_icmp_failure()` / `verify_connectivity_fallback()`) is
  **preserved** behavior (SAFE-02). Phase 187 must not re-route around it,
  rewrite it, or subsume it.
- No CAKE threshold retuning. No new YAML tunables. No new reflector
  architecture. Explicitly out of scope per `.planning/REQUIREMENTS.md`.
- The state taxonomy is exactly `{healthy, reduced, collapsed}`; Phase 187
  does not split or rename these buckets. A four-state taxonomy was
  considered and rejected in Phase 186 D-04.
- The 3-reflector deployment assumption stands. Phase 187 does not lock in
  a 4+ reflector branch.

### Claude's Discretion

- Exact mechanism for exposing "current-cycle successful count" from
  `BackgroundRTTThread` to the controller (new public method, new field on
  `RTTSnapshot`, a parallel lightweight status struct, etc.). Research
  recommends a parallel `_last_cycle_status` struct on
  `BackgroundRTTThread` — see Architecture Patterns below — but the planner
  may justify a different surface if it keeps the change footprint small.
- Exactly how `measure_rtt()` decides whether the current cycle had
  zero-success. Research recommends reading the new status field rather
  than re-inspecting the cached snapshot, because the snapshot is preserved
  and therefore unreliable as a current-cycle signal.
- Whether to add one or several new unit tests for the zero-success cycle
  path. Research recommends at least three (see Validation Architecture).

### Deferred Ideas (OUT OF SCOPE)

- **ALRT-01** — dedicated alert path for sustained measurement-quality
  collapse. Deferred to v2 post-milestone per REQUIREMENTS.md.
- **ANLY-01** — historical reporting for reflector-collapse episodes.
  Deferred to v2.
- Any change to `handle_icmp_failure()` return-value contract.
- Any new YAML key for cadence, stale cutoff, zero-success tolerance, or
  reduced-quorum thresholds.
- Any change to CAKE thresholds, burst detection, or fusion weights.
- Any rewrite of the controller's 4-state download / 3-state upload model.

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| MEAS-02 | A background RTT cycle with zero successful reflectors does not continue to present the last cached RTT as a healthy current measurement. | Documented stale-reuse sites at `rtt_measurement.py:429-447`, `wan_controller.py:923-954`, and `wan_controller.py:3392-3400`. Fix pattern described in Architecture Patterns. |
| SAFE-01 | When measurement quality degrades, controller behavior follows explicit bounded semantics instead of silently acting on stale RTT as if it were current. | The Phase 186 contract (`state`, `stale`, `successful_count`) is the "bounded semantics" surface. Phase 187 wires its producer honestly so the contract becomes actionable. |
| SAFE-02 | Existing ICMP failure fallback and total-connectivity-loss handling remain intact for real outages and do not regress while adding measurement-degradation handling. | Existing path traced at `wan_controller.py:1217-1433`. Regression coverage plan below preserves this path as a hard invariant. |

## Architectural Responsibility Map

Phase 187 is a single-process, single-tier Python change. There is no browser
or frontend server tier. The responsibility map below is framed in terms of
wanctl subsystems instead of web tiers.

| Capability | Primary Subsystem | Secondary Subsystem | Rationale |
|------------|-------------------|---------------------|-----------|
| ICMP probe scheduling and aggregation | `rtt_measurement.BackgroundRTTThread` | — | This is the only place that sees per-cycle `successful_rtts` before aggregation. A current-cycle status must originate here. |
| Current-cycle → controller hand-off | `wan_controller.WANController.measure_rtt` | `BackgroundRTTThread` | `measure_rtt()` already owns the staleness decision; it is the natural place to branch on "zero-success current cycle." |
| Publishing reflector metadata to `/health` | `wan_controller.WANController._record_live_rtt_snapshot` / `get_health_data` | `BackgroundRTTThread` | `_last_*_reflector_hosts` is owned by the controller; the fix must route through `_record_live_rtt_snapshot()` so `health_data["measurement"]` stays the single producer. |
| Reacting to collapsed measurement on `/health` | `health_check.HealthCheckHandler._build_measurement_section` | — | Phase 186 already owns this. Phase 187 MUST NOT re-augment the section. |
| ICMP → TCP → total-outage fallback | `wan_controller.WANController.handle_icmp_failure` / `verify_connectivity_fallback` | — | Preserved verbatim. Phase 187 is a sibling path, not a replacement. |
| Control policy on measurement degradation | `wan_controller.WANController.run_cycle` | `_run_rtt_measurement` | No new control branch in Phase 187. The controller continues to consume `measured_rtt` as today; only the `/health` surface becomes honest. |
| Regression coverage | `tests/test_rtt_measurement.py`, `tests/test_wan_controller.py`, `tests/test_health_check.py`, `tests/test_autorate_error_recovery.py` | — | Each file already covers one of the four concerns Phase 187 touches. No new test file is needed. |

## Standard Stack

Phase 187 is an in-repo behavioral change. No new dependencies are required
or recommended. All work is in existing `src/wanctl/` modules and existing
`tests/` files.

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `icmplib` | already pinned in `pyproject.toml` | Raw ICMP probing in `RTTMeasurement` | [VERIFIED: codebase import in `src/wanctl/rtt_measurement.py`] Already used; unchanged. |
| `concurrent.futures` (stdlib) | Python 3.11+ | Persistent `ThreadPoolExecutor` for per-host pings | [VERIFIED: `src/wanctl/rtt_measurement.py:381`] Already used; unchanged. |
| `pytest` | already pinned | Regression framework | [VERIFIED: `pyproject.toml` and `tests/`] Already used; unchanged. |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `unittest.mock.MagicMock` | stdlib | Mocking `BackgroundRTTThread` in controller tests | Already the established pattern (`tests/test_rtt_measurement.py:872`). |
| `pytest.mark.parametrize` | pytest | Boundary partition coverage | Already used by `TestMeasurementContract` (`tests/test_health_check.py:4151`). |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| In-place mutation of `RTTSnapshot` | Add `successful_count_current` field | Would require changing the `frozen=True, slots=True` dataclass shape and rippling through every test that constructs an `RTTSnapshot`. Rejected: too broad a blast radius for a stability-first change. |
| New YAML tunable `zero_success_tolerance_cycles` | Surface a configurable hysteresis | **Explicitly rejected** — REQUIREMENTS.md forbids new tuning surfaces in v1.38. |
| Rewriting `handle_icmp_failure()` to take measurement-health input | Centralize degradation handling | Would break SAFE-02 (existing fallback must remain intact). Rejected. |
| Making `measure_rtt()` return a richer object instead of `float | None` | Pass structured degradation to the controller | Would ripple through every caller of `measure_rtt()`. Rejected. The controller already has all metadata it needs on `self._last_*`. |

**Installation:** None — all changes are in-repo.

**Version verification:** Not applicable (no new packages).

## Architecture Patterns

### System Architecture Diagram

```
                    BackgroundRTTThread._run() (50ms cadence)
                                    │
                                    ▼
                    ping_hosts_with_persistent_pool(hosts)
                                    │
                                    ▼
                       successful_rtts: list[float]
                                    │
                                    ├─── len > 0 ────┐
                                    │                ▼
                                    │    _cached = RTTSnapshot(...)   ← overwrites
                                    │                │
                                    │                │
                                    └─── len == 0 ───┤
                                                     │
                                                     ▼
                                 [CURRENT BUG] _cached is preserved
                                 [PHASE 187 FIX]  _last_cycle_status updated
                                                  to record zero-success
                                                     │
                                                     ▼
                    ┌────────────────────────────────┴─────────────────────┐
                    │                                                      │
                    ▼                                                      ▼
    WANController.measure_rtt() reads get_latest()      WANController.measure_rtt()
                    │                                       reads [NEW] get_cycle_status()
                    │                                                      │
                    ▼                                                      ▼
       age check (≤5s → float, else → None)              zero-success branch:
                    │                                      • keep float rtt_ms (within 5s)
                    │                                      • override successful_hosts ← ()
                    │                                      • override active_hosts ← current
                    │                                      (leave _last_raw_rtt_ts untouched
                    │                                       so staleness_sec stays honest)
                    │                                                      │
                    └──────────────┬───────────────────────────────────────┘
                                   ▼
                    _record_live_rtt_snapshot(
                        rtt_ms=...,               ← from cached, unchanged
                        timestamp=...,            ← from cached, unchanged
                        active_hosts=...,         ← CURRENT cycle
                        successful_hosts=...,     ← CURRENT cycle (empty on zero-success)
                    )
                                   │
                                   ▼
                    get_health_data()["measurement"] ← same build site
                                   │
                                   ▼
                    HealthCheckHandler._build_measurement_section()
                    (Phase 186 contract, unchanged)
                                   │
                                   ▼
                    state="collapsed", successful_count=0,
                    stale=(staleness_sec > 3*cadence_sec)

                    ─── parallel unaffected path ───

    measure_rtt() returns None (no snapshot, or age>5s cached)
                                   │
                                   ▼
           handle_icmp_failure() → verify_connectivity_fallback()
           (gateway ping + TCP RTT + total-connectivity-loss branch)
                                   │
                                   ▼
                    UNCHANGED by Phase 187 (SAFE-02)
```

**Data flow narrative.** The fix is surgical. On every background cycle,
`BackgroundRTTThread._run()` already knows `len(successful_rtts)` before it
decides whether to overwrite `_cached`. Phase 187 teaches the thread to
**also** record that count (plus the current-cycle host lists) into a
separate, lightweight "current cycle status" field that is always updated,
even when the cached snapshot is not. `WANController.measure_rtt()` then
reads both the cached snapshot (for `rtt_ms`) and the current-cycle status
(for host lists). When the current cycle is zero-success but the cached
snapshot is still within the 5s hard cutoff, the controller gets a usable
`rtt_ms` (preserving today's bounded behavior) AND the health payload
correctly reports `successful_count=0` / `state="collapsed"`. No existing
control branch is changed. The `handle_icmp_failure()` path is untouched.

### Recommended File Scope

```
src/wanctl/
├── rtt_measurement.py          # Add current-cycle status publishing
│                               # in BackgroundRTTThread._run() and a
│                               # new accessor (parallel to get_latest)
├── wan_controller.py           # measure_rtt(): read current-cycle status
│                               # and override host lists on zero-success
│                               # cycle; leave _last_raw_rtt_ts untouched
└── (health_check.py UNCHANGED) # Phase 186 contract is final

tests/
├── test_rtt_measurement.py     # Add zero-success current-cycle status
│                               # unit tests alongside existing
│                               # test_stale_data_preserved_on_all_failures
├── test_wan_controller.py      # Add WANController zero-success
│                               # integration tests (following the
│                               # TestMeasureRTTNonBlocking pattern)
├── test_health_check.py        # Add measurement-section contract
│                               # tests for the zero-success path using
│                               # the existing TestMeasurementContract
│                               # fixture builders
└── test_autorate_error_recovery.py  # Non-regression tests pinning
                                     # handle_icmp_failure behavior
```

### Pattern 1: Parallel Current-Cycle Status Struct

**What:** Add a small immutable record — conceptually a
`RTTCycleStatus(successful_count: int, active_hosts: tuple[str, ...],
successful_hosts: tuple[str, ...], cycle_timestamp: float)` — stored on
`BackgroundRTTThread` as `self._last_cycle_status` and updated on **every**
cycle (including zero-success). Exposed via a read-only accessor method
parallel to `get_latest()`.

**When to use:** When you must preserve the existing "stale cached snapshot"
contract (callers that just want the last known good `rtt_ms`) while
simultaneously publishing a fresh, honest current-cycle signal. The two
axes — "last successful measurement" and "current cycle outcome" — are
genuinely orthogonal and the existing `RTTSnapshot` conflates them.

**Example (illustrative only; exact shape is a planner decision):**

```python
# Source: reuses GIL-atomic pointer-swap pattern from BackgroundRTTThread._cached
#         (verified at src/wanctl/rtt_measurement.py:439-447)

@dataclasses.dataclass(frozen=True, slots=True)
class RTTCycleStatus:
    """Snapshot of the most recent background RTT cycle's outcome.

    Distinct from RTTSnapshot: this is updated every cycle, including
    zero-success cycles. Consumers that want the last known good rtt_ms
    continue to read get_latest(); consumers that want the current-cycle
    quorum signal read get_cycle_status().
    """
    successful_count: int
    active_hosts: tuple[str, ...]
    successful_hosts: tuple[str, ...]
    cycle_timestamp: float  # time.monotonic() of cycle completion

# In BackgroundRTTThread._run(), after the successful_rtts check:
self._last_cycle_status = RTTCycleStatus(
    successful_count=len(successful_rtts),
    active_hosts=tuple(hosts),
    successful_hosts=tuple(successful_hosts),
    cycle_timestamp=time.monotonic(),
)
# _cached is still only overwritten when successful_rtts is non-empty
```

### Pattern 2: Zero-Success Branch in `measure_rtt()` (keep rtt_ms, override hosts)

**What:** When the current cycle reports `successful_count == 0` but the
cached snapshot is still within the 5s hard cutoff, `measure_rtt()`
continues to return the cached `rtt_ms` (preserving SAFE-02's bounded
behavior) but calls `_record_live_rtt_snapshot()` with the **current
cycle's** host lists so the health contract reports collapse honestly.

**When to use:** This is the exact Phase 187 fix.

**Example (illustrative):**

```python
# Source: delta on src/wanctl/wan_controller.py:908-953 (measure_rtt)
snapshot = self._rtt_thread.get_latest()
cycle_status = self._rtt_thread.get_cycle_status()  # NEW

if snapshot is None:
    self.logger.warning(...)
    return None

age = time.monotonic() - snapshot.timestamp
if age > 5.0:
    self.logger.warning(...)
    return None

# ReflectorScorer recording is unchanged — it still consumes
# per_host_results from the cached snapshot because the scorer already
# handles its own staleness.
self._reflector_scorer.record_results(...)
self._persist_reflector_events()

# Phase 187: choose host lists from the current cycle, not the cached
# snapshot, so _last_successful_reflector_hosts reflects TODAY.
if cycle_status is not None and cycle_status.successful_count == 0:
    active_hosts = list(cycle_status.active_hosts)
    successful_hosts = []   # current cycle, honestly zero
    self.logger.warning(
        f"{self.wan_name}: Zero-success RTT cycle; measurement "
        f"collapsed. Reusing cached rtt_ms={snapshot.rtt_ms:.1f} "
        f"(age={age:.2f}s) for bounded controller behavior."
    )
else:
    active_hosts = list(snapshot.active_hosts or snapshot.per_host_results.keys())
    successful_hosts = list(
        snapshot.successful_hosts
        or (host for host, rtt_val in snapshot.per_host_results.items() if rtt_val is not None)
    )

self._record_live_rtt_snapshot(
    rtt_ms=snapshot.rtt_ms,
    timestamp=snapshot.timestamp,  # NOT current — staleness_sec must stay honest
    active_hosts=active_hosts,
    successful_hosts=successful_hosts,
)
return snapshot.rtt_ms
```

**Note on `staleness_sec` honesty:** `_last_raw_rtt_ts` intentionally stays
pinned to the cached snapshot's timestamp. The Phase 186 contract already
makes `stale` flip `True` once the cached sample exceeds `3 * cadence_sec`
of age. Phase 187 does not rewrite staleness semantics — it makes
`successful_count` honest so the consumer sees the cross-product
(`state="collapsed", stale=True`) that Phase 186 D-03 spec'd.

### Anti-Patterns to Avoid

- **Overwriting `_last_raw_rtt_ts = time.monotonic()` in the zero-success
  branch.** This would make a stale cache look fresh to the contract and
  silently break Phase 186 D-11 ("`staleness_sec` continues to mean age of
  the last raw RTT sample"). The whole point of the fix is to make
  `successful_count` honest; staleness must also stay honest.
- **Introducing a new control branch in `run_cycle()` / `_run_rtt_measurement()`.**
  The milestone is explicit: Phase 187 is bounded to measurement surface
  honesty. Adding a new "if collapsed, clamp rates" branch would exceed
  scope and risks destabilizing tuned behavior. Control-policy changes on
  measurement degradation are explicitly left as a future v2 decision.
- **Replacing or rerouting `handle_icmp_failure()`.** SAFE-02 requires the
  existing ICMP/TCP/total-outage fallback path to stay intact. Phase 187
  acts on a different code path (cached-but-collapsed) — not on
  total ICMP loss.
- **Broadening the `RTTSnapshot` dataclass.** The existing class is frozen,
  slotted, and consumed by every measurement test. Adding fields here has
  higher blast radius than adding a parallel struct.
- **Exposing a new public method on `BackgroundRTTThread` that returns
  `None` on the first-ever cycle and forcing callers to branch.** The
  planner should specify a well-defined "no status yet" sentinel (e.g.,
  `None` → treat as "no data, preserve today's behavior"), and the test
  plan must pin the first-cycle contract explicitly.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| GIL-atomic pointer swap for cycle status | A new `threading.Lock` around `_last_cycle_status` | Reuse the existing lock-free pointer-swap pattern (`self._last_cycle_status = ...`) | [VERIFIED: `src/wanctl/rtt_measurement.py:439-446`] The thread already relies on Python's GIL for atomic pointer assignment. Adding a lock would introduce unnecessary contention and diverge from the established pattern. |
| Tracking "time since last successful quorum" | A new monotonic-clock field on the controller | `cycle_status.cycle_timestamp` already captures this, and Phase 186's `staleness_sec` already surfaces it indirectly | Avoids the "two timestamps" problem Phase 186 D-07 explicitly warned against. |
| A new configurable "collapsed tolerance" | A new YAML key | The controller's existing 5s hard cutoff already bounds worst-case staleness | No new tuning surface (REQUIREMENTS.md constraint). |
| A new test fixture class for zero-success cycles | A bespoke harness | Extend `TestBackgroundRTTThread` (patterns at `tests/test_rtt_measurement.py:644-860`) and `TestMeasurementContract._make_health_data` (`tests/test_health_check.py:4132`) | Keeps fixture style consistent and halves the review surface. |

**Key insight:** The `BackgroundRTTThread` and the Phase 186 contract each
solve half the problem. The thread preserves stale data (so consumers never
see "no RTT"); the contract advertises staleness and quorum (so consumers
can distinguish healthy from collapsed). The gap is that the thread's
preservation policy was never wired into the contract's producer —
`_record_live_rtt_snapshot()` always takes host lists from the cached
snapshot. Phase 187 is a ~40-line surgical fix that bridges the two.

## Runtime State Inventory

Phase 187 is not a rename, refactor, or migration. It is a targeted
behavioral fix. The standard rename/refactor inventory does not apply.

**Nothing stored in external systems** — verified: no database rename, no
service config rename, no secret rename.

- Stored data: **None** — no on-disk schema change. The existing
  `metrics.db` schema is untouched. The `_last_*` fields on the controller
  are in-memory only.
- Live service config: **None** — no systemd, n8n, or Datadog change.
- OS-registered state: **None** — no new service, no task scheduler entry.
- Secrets/env vars: **None** — no new configuration surface.
- Build artifacts: **None** — no `pyproject.toml` rename, no package name
  change. `.venv/bin/mypy` and `.venv/bin/pytest` entry points unchanged.

## Common Pitfalls

### Pitfall 1: Silently breaking `staleness_sec` by updating the wrong timestamp

**What goes wrong:** A naive fix "just make it honest" overwrites
`_last_raw_rtt_ts = time.monotonic()` in the zero-success branch, so
`staleness_sec` reports near-zero even though the underlying RTT sample is
stale.

**Why it happens:** The writer thinks "current cycle" and sets the
timestamp to "now."

**How to avoid:** In the zero-success branch, only the host lists are
updated. `_last_raw_rtt` and `_last_raw_rtt_ts` keep the cached snapshot's
values. Phase 186 D-11 is the explicit guardrail.

**Warning signs:** A unit test where `staleness_sec` is near zero in a
zero-success cycle. Should always be `age_of_cached_snapshot > 0`.

### Pitfall 2: Regression in `handle_icmp_failure()` cycle counting

**What goes wrong:** A fix that returns `None` from `measure_rtt()` on
zero-success cycles (instead of returning the cached `rtt_ms`) will trigger
`handle_icmp_failure()` → `icmp_unavailable_cycles += 1` → graceful
degradation → eventual `giving up` at the configured `fallback_max_cycles`.
This is different from today's behavior under pure measurement collapse
(cached RTT still available). Flipping the return contract risks
destabilizing spot ISP-level measurement churn.

**Why it happens:** The writer conflates "cycle collapsed" with "ICMP
unavailable" and routes into the total-outage path.

**How to avoid:** Keep `measure_rtt()`'s return contract unchanged. The
zero-success cycle still returns a usable `rtt_ms` (from cache, within the
5s hard cutoff). The ONLY thing that changes is what goes into
`_last_*_reflector_hosts`.

**Warning signs:** `tests/test_autorate_error_recovery.py` starts failing
on the zero-success branch, or `icmp_unavailable_cycles` starts
incrementing on cycles that previously returned a cached RTT.

### Pitfall 3: Broadcasting "collapsed" during legitimate first-cycle startup

**What goes wrong:** On process start, `_last_cycle_status` is `None` and
`_cached` is `None`. A naive contract read would report
`state="collapsed"`, which is technically correct but operator-unhelpful
during the 50ms startup window.

**Why it happens:** The contract's first-cycle sentinel is ambiguous.

**How to avoid:** Phase 186 already handles "no measurement" via the
`measurement` key being absent or `raw_rtt_ms is None`. Phase 187's
current-cycle status accessor should return `None` when no cycle has
completed yet, and `measure_rtt()` should fall back to today's behavior
(no override) when status is `None`. The health payload then reports
exactly what Phase 186 reports today on first-cycle (which is already
correct).

**Warning signs:** A startup flake in `tests/test_wan_controller.py`
where the first cycle's health payload reports `state="collapsed"` when
it should be either absent or derived from the first real cycle.

### Pitfall 4: GIL-atomicity assumption break

**What goes wrong:** `_last_cycle_status` is written from the background
thread and read from the main control loop thread. If the writer produces
a `RTTCycleStatus` and the reader reads the fields non-atomically, the
reader could see a torn tuple or half-initialized host list.

**Why it happens:** Python's GIL guarantees atomic pointer assignment
(`self._last_cycle_status = new_status`), but field-by-field mutation
would NOT be safe.

**How to avoid:** Make `RTTCycleStatus` a `frozen=True, slots=True`
`dataclass` (same pattern as `RTTSnapshot`), constructed with all fields
at once. Assign the whole object via pointer swap. Never mutate in place.

**Warning signs:** Any `@dataclass(frozen=False)` or any mutation helper
method on the new class. Code review should reject it.

### Pitfall 5: ReflectorScorer double-counting

**What goes wrong:** `measure_rtt()` already calls
`self._reflector_scorer.record_results(...)` based on the cached snapshot's
`per_host_results`. If Phase 187 also records the current-cycle results,
the scorer can count the same or a contradictory outcome twice.

**Why it happens:** The scorer contract is not obvious from the call site.

**How to avoid:** Leave the existing `record_results()` call unchanged. The
scorer consumes cached `per_host_results`; the Phase 187 change only
affects what `_record_live_rtt_snapshot()` writes to the `_last_*` fields.

**Warning signs:** New calls to `_reflector_scorer.record_results(...)`
introduced in the Phase 187 diff. Code review should reject them unless
the planner explicitly justifies the double-record and pins it with
a new test.

## Code Examples

### Zero-success cycle current-state publishing

```python
# Source: illustrative delta on src/wanctl/rtt_measurement.py:414-457
def _run(self) -> None:
    while not self._shutdown_event.is_set():
        elapsed_s = 0.0
        try:
            hosts = self._hosts_fn()
            if not hosts:
                self._shutdown_event.wait(timeout=self._cadence_sec or 0.1)
                continue

            t0 = time.perf_counter()
            per_host, successful_hosts, successful_rtts = (
                self._ping_with_persistent_pool(hosts)
            )
            elapsed_s = time.perf_counter() - t0
            elapsed_ms = elapsed_s * 1000.0

            # Phase 187: always publish current-cycle status, even on
            # zero-success. This is orthogonal to _cached, which still
            # uses stale-prefer-none.
            self._last_cycle_status = RTTCycleStatus(
                successful_count=len(successful_rtts),
                active_hosts=tuple(hosts),
                successful_hosts=tuple(successful_hosts),
                cycle_timestamp=time.monotonic(),
            )

            if successful_rtts:
                # ... existing aggregation unchanged ...
                self._cached = RTTSnapshot(...)
            # else: stale data preferred over no data -- do NOT overwrite _cached
            #       (unchanged Phase 132 contract)
        ...
```

### Zero-success cycle consumption in `measure_rtt`

```python
# Source: illustrative delta on src/wanctl/wan_controller.py:908-953
snapshot = self._rtt_thread.get_latest()
cycle_status = self._rtt_thread.get_cycle_status()

if snapshot is None:
    self.logger.warning(...)
    return None

age = time.monotonic() - snapshot.timestamp
if age > 5.0:
    # Existing hard cutoff -> None -> handle_icmp_failure() path (unchanged)
    self.logger.warning(...)
    return None

self._reflector_scorer.record_results(
    {host: rtt_val is not None for host, rtt_val in snapshot.per_host_results.items()}
)
self._persist_reflector_events()

if cycle_status is not None and cycle_status.successful_count == 0:
    active_hosts = list(cycle_status.active_hosts)
    successful_hosts: list[str] = []
else:
    active_hosts = list(snapshot.active_hosts or snapshot.per_host_results.keys())
    successful_hosts = list(
        snapshot.successful_hosts
        or (host for host, rtt_val in snapshot.per_host_results.items() if rtt_val is not None)
    )

self._record_live_rtt_snapshot(
    rtt_ms=snapshot.rtt_ms,
    timestamp=snapshot.timestamp,
    active_hosts=active_hosts,
    successful_hosts=successful_hosts,
)
return snapshot.rtt_ms
```

### Zero-success contract combination test (pattern match)

```python
# Source: pattern from tests/test_health_check.py:4125-4254 (TestMeasurementContract)
def test_zero_success_cycle_reports_collapsed(self):
    """Phase 187: cached rtt + zero-success current cycle -> state='collapsed'."""
    handler = self._make_handler()
    health_data = self._make_health_data(
        successful_hosts=[],    # current cycle has zero successful
        active_hosts=["a", "b", "c"],
        staleness_sec=0.15,     # cached sample age (> 3*cadence = stale)
        cadence_sec=0.05,
    )

    measurement = handler._build_measurement_section(health_data)

    assert measurement["state"] == "collapsed"
    assert measurement["successful_count"] == 0
    assert measurement["stale"] is True
    # raw_rtt_ms still present — controller has a usable value
    assert measurement["raw_rtt_ms"] is not None
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Stale cached RTT reused as current and reported `state="healthy"` | Stale cached RTT still usable by controller, but `state` and `successful_count` reflect current cycle honestly | Phase 187 (this research) | Operators can correlate `/health` with live latency during `tcp_12down`. |
| `BackgroundRTTThread` exposed only `get_latest()` (successful-only) | `BackgroundRTTThread` exposes `get_latest()` AND a parallel current-cycle status accessor | Phase 187 | No new control branch; contract becomes actionable. |
| `_last_*_reflector_hosts` sourced from the cached snapshot's preserved host list | `_last_*_reflector_hosts` sourced from the current cycle's host list | Phase 187 | Phase 186 D-03 cross-product becomes reachable in reality, not just theory. |

**Deprecated/outdated:**

- The implicit "preserve cached RTT AND preserve cached host lists" coupling
  introduced by Phase 132. Phase 187 decouples: cached RTT is preserved
  (bounded controller safety), cached host lists are NOT preserved for
  the purpose of the Phase 186 contract.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | [ASSUMED] The reflector scorer does not need to be re-called on the current-cycle (zero-success) host list — its existing record from the cached `per_host_results` is sufficient. | Anti-Patterns + Pitfall 5 | If wrong, the scorer may deprioritize the wrong host. Mitigation: the planner should confirm with a targeted unit test that the scorer's rolling window is unchanged by the fix. |
| A2 | [ASSUMED] A `frozen=True, slots=True` dataclass + pointer-swap is a safe cross-thread publishing mechanism in wanctl's deployment. | Pattern 1 | Verified by analogy with `RTTSnapshot` (same code path, same threads, shipped stable since Phase 132). Risk is LOW but not zero. Mitigation: reuse the exact lifecycle test scaffold from `test_caching_updates_after_measurement`. |
| A3 | [ASSUMED] No other caller of `BackgroundRTTThread.get_latest()` exists outside `WANController.measure_rtt()`. | Pattern 2 | A second consumer that treats `get_latest()` as "authoritative current" would need the same fix. | Mitigation: grep check documented in Validation Architecture below. |
| A4 | [ASSUMED] The 5-second hard cutoff in `measure_rtt()` is still the right bound in the zero-success branch, even though Phase 186 now classifies cache older than `3 * cadence_sec` as `stale`. | Phase Boundary + Pattern 2 | If the planner tightens the cutoff to match `3 * cadence_sec`, that is a behavior change outside Phase 187 scope and should surface as a discuss-phase question. The current research keeps the 5s cutoff unchanged for SAFE-02 compliance. |

**These assumptions should be confirmed in `/gsd-discuss-phase` for Phase 187
before the planner commits to specific code.**

## Open Questions (RESOLVED)

1. **Should zero-success cycles propagate `successful_count=0` to
   `ReflectorScorer` record_results?**
   - What we know: Today `record_results()` is called once per
     `measure_rtt()` call using the cached snapshot's `per_host_results`.
     On a zero-success current cycle, the scorer continues to see "all
     hosts returned cached values" — which is technically a lie about the
     current cycle but matches today's behavior.
   - What's unclear: Whether giving the scorer visibility into the
     current-cycle failure would help it deprioritize the failing hosts
     faster, or whether it would conflict with the scorer's own rolling
     window.
   - **RESOLVED:** Out of scope — do not re-call ReflectorScorer on zero-success cycles. Matches Phase 187 conservative scope.

2. **Should the zero-success branch log at WARNING or INFO?**
   - What we know: Production already logs at WARNING for the 5s hard
     cutoff. Logging every zero-success cycle at WARNING during a real
     reflector outage would flood the log.
   - What's unclear: Whether a once-per-N-cycle throttle is acceptable
     within the "no new tuning" constraint.
   - **RESOLVED:** Match existing `icmp_unavailable_cycles` / `ICMP recovered` pattern at wan_controller.py:2272-2277 (WARNING on first cycle then DEBUG).

3. **Does `handle_icmp_failure()` need any awareness of `state="collapsed"`?**
   - What we know: The two paths are orthogonal today. `handle_icmp_failure()`
     fires only when `measure_rtt()` returns `None` (no cached data or
     cache >5s old). The collapsed-but-cached path never reaches it.
   - What's unclear: Whether operators would benefit from seeing
     `state="collapsed"` in the `handle_icmp_failure()` log lines too.
   - **RESOLVED:** No — SAFE-02 preservation requires byte-identical fallback pipeline.

4. **What should `get_cycle_status()` return if the thread has never
   completed a cycle?**
   - What we know: At process start, no cycle has completed.
   - What's unclear: `None` (matches `get_latest()` pattern) vs
     `RTTCycleStatus(successful_count=0, ...)` ("pessimistic default").
   - **RESOLVED:** Return `None`; measure_rtt() falls through to today's behavior on `None` so startup is byte-identical.

## Environment Availability

Phase 187 has **no new external dependencies**. All probing is done at the
repo level.

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.11+ | entire repo | ✓ | `.venv` pinned | — |
| pytest | regression suite | ✓ | `.venv/bin/pytest` | — |
| mypy | type check | ✓ | `.venv/bin/mypy` | — |
| ruff | linter | ✓ | `.venv/bin/ruff` | — |
| cake-shaper VM 206 | optional live verification | ✓ | SSH kevin@10.10.110.223 | Phase 188 handles live verification; Phase 187 is local-only |

**Missing dependencies with no fallback:** None.
**Missing dependencies with fallback:** None.

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest (existing) |
| Config file | `pyproject.toml` |
| Quick run command | `.venv/bin/pytest -o addopts='' tests/test_rtt_measurement.py tests/test_wan_controller.py tests/test_health_check.py tests/test_autorate_error_recovery.py -q` |
| Full suite command | `.venv/bin/pytest -q` |
| Quick gate mypy | `.venv/bin/mypy src/wanctl/rtt_measurement.py src/wanctl/wan_controller.py src/wanctl/health_check.py` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|--------------|
| MEAS-02 | Zero-success cycle publishes current-cycle status on `BackgroundRTTThread` | unit | `.venv/bin/pytest tests/test_rtt_measurement.py::TestBackgroundRTTThread::test_cycle_status_published_on_zero_success -x` | ❌ Wave 0 (new test) |
| MEAS-02 | `_last_successful_reflector_hosts` reflects current cycle (empty) on zero-success | integration | `.venv/bin/pytest tests/test_wan_controller.py::TestZeroSuccessCycle::test_zero_success_overrides_successful_hosts -x` | ❌ Wave 0 (new test class) |
| MEAS-02 | `/health` contract reports `state="collapsed"` + `successful_count=0` end-to-end | contract | `.venv/bin/pytest tests/test_health_check.py::TestMeasurementContract::test_zero_success_cycle_reports_collapsed -x` | ❌ Wave 0 (new test in existing class) |
| SAFE-01 | Zero-success cycle within 5s cutoff still returns a usable `rtt_ms` (bounded controller behavior preserved) | unit | `.venv/bin/pytest tests/test_wan_controller.py::TestZeroSuccessCycle::test_zero_success_preserves_cached_rtt_within_5s -x` | ❌ Wave 0 |
| SAFE-01 | `_last_raw_rtt_ts` stays pinned to cached snapshot timestamp in the zero-success branch (Phase 186 `staleness_sec` honesty) | unit | `.venv/bin/pytest tests/test_wan_controller.py::TestZeroSuccessCycle::test_zero_success_does_not_touch_raw_rtt_timestamp -x` | ❌ Wave 0 |
| SAFE-02 | Cache >5s stale still returns `None` → `handle_icmp_failure()` path intact | regression | `.venv/bin/pytest tests/test_rtt_measurement.py::TestMeasureRTTNonBlocking::test_measure_rtt_stale_hard_fail -x` | ✅ existing |
| SAFE-02 | `handle_icmp_failure()` graceful_degradation / freeze / use_last_rtt modes unchanged | regression | `.venv/bin/pytest tests/test_autorate_error_recovery.py -k handle_icmp_failure -q` | ✅ existing |
| SAFE-02 | `verify_connectivity_fallback()` TCP/gateway paths unchanged | regression | `.venv/bin/pytest tests/test_autorate_error_recovery.py -k verify_connectivity_fallback -q` | ✅ existing |
| SAFE-02 | `icmp_unavailable_cycles` does NOT increment on a cached-but-collapsed cycle | unit | `.venv/bin/pytest tests/test_wan_controller.py::TestZeroSuccessCycle::test_zero_success_does_not_increment_icmp_unavailable_cycles -x` | ❌ Wave 0 |
| Contract | First-ever cycle before `_last_cycle_status` is set: no regression vs today's behavior | unit | `.venv/bin/pytest tests/test_rtt_measurement.py::TestBackgroundRTTThread::test_cycle_status_is_none_before_first_cycle -x` | ❌ Wave 0 |
| Contract | Recovery: after zero-success cycle, next successful cycle clears current-cycle status | unit | `.venv/bin/pytest tests/test_rtt_measurement.py::TestBackgroundRTTThread::test_cycle_status_recovers_after_successful_cycle -x` | ❌ Wave 0 |

### Sampling Rate

- **Per task commit:** `.venv/bin/mypy src/wanctl/rtt_measurement.py src/wanctl/wan_controller.py` plus the focused quick-run command above.
- **Per wave merge:** `.venv/bin/pytest -o addopts='' tests/test_cake_signal.py tests/test_queue_controller.py tests/test_wan_controller.py tests/test_health_check.py tests/test_rtt_measurement.py tests/test_autorate_error_recovery.py -q` (hot-path regression slice per CLAUDE.md + Phase 187 targets).
- **Phase gate:** `.venv/bin/pytest -q` (full suite) + `.venv/bin/ruff check src/wanctl/rtt_measurement.py src/wanctl/wan_controller.py` (ruff on new code only — pre-existing `B009/B010` findings elsewhere in `wan_controller.py` are NOT in Phase 187 scope per the 186-02 summary).

### Wave 0 Gaps

- [ ] `tests/test_rtt_measurement.py` — new tests in `TestBackgroundRTTThread`:
  - [ ] `test_cycle_status_published_on_zero_success`
  - [ ] `test_cycle_status_published_on_successful_cycle`
  - [ ] `test_cycle_status_is_none_before_first_cycle`
  - [ ] `test_cycle_status_recovers_after_successful_cycle`
  - [ ] (Keep `test_stale_data_preserved_on_all_failures` unchanged — it pins the `_cached` contract.)
- [ ] `tests/test_wan_controller.py` — new `TestZeroSuccessCycle` class (following the `TestMeasureRTTNonBlocking` pattern at `tests/test_rtt_measurement.py:862-949`):
  - [ ] `test_zero_success_overrides_successful_hosts`
  - [ ] `test_zero_success_preserves_cached_rtt_within_5s`
  - [ ] `test_zero_success_does_not_touch_raw_rtt_timestamp`
  - [ ] `test_zero_success_does_not_increment_icmp_unavailable_cycles`
- [ ] `tests/test_health_check.py` — extend existing `TestMeasurementContract`:
  - [ ] `test_zero_success_cycle_reports_collapsed` (use the existing `_make_health_data` fixture; no new helpers needed).
- [ ] `tests/test_autorate_error_recovery.py` — no new tests; this suite is the non-regression witness for SAFE-02. Run it as-is.

### Framework install

None — `pytest` / `mypy` / `ruff` already installed.

## Project Constraints (from CLAUDE.md)

These are copied verbatim from `./CLAUDE.md` because Phase 187 is a change
to a production control system and several CLAUDE.md directives are
directly load-bearing for the planner:

- **Conservative change policy.** "Explain risky changes before changing
  behavior." Phase 187 must surface its current-cycle status design in
  `/gsd-discuss-phase` for explicit user sign-off before any code lands.
- **Priority ordering.** `stability > safety > clarity > elegance`. Every
  Phase 187 design choice must be justified against stability first, then
  safety, then clarity, then elegance. The research above deliberately
  rejects more-elegant options (e.g., rewriting `RTTSnapshot`) in favor of
  more-stable ones (parallel status struct).
- **Portable controller architecture.** "NON-NEGOTIABLE: The controller is
  link-agnostic. The same code must run across cable, DSL, fiber, and
  other deployments. Deployment-specific behavior belongs in YAML config,
  not Python branching." Phase 187 adds NO deployment-specific branch —
  the fix is purely about measurement honesty, same code on all links.
- **Control model invariants** (must not violate): "All congestion
  decisions are based on RTT delta, not absolute RTT." "Baseline RTT must
  stay frozen during load." "Rate decreases are immediate. Rate increases
  require sustained healthy cycles." Phase 187 does not change any of
  these because it does not change control policy — it only fixes the
  `/health` surface.
- **Flash wear protection.** Unchanged by Phase 187.
- **Run from venv directly** (not `make ci`). All quick/full commands in
  Validation Architecture use `.venv/bin/pytest` and `.venv/bin/mypy`.
- **Production is cake-shaper VM 206, 24/7.** Deployment verification is
  Phase 188's job; Phase 187 stays local.

## Sources

### Primary (HIGH confidence)

- `src/wanctl/rtt_measurement.py:350-457` — `BackgroundRTTThread` class,
  including the exact `successful_rtts` check and preserve-cached-on-zero
  comment at line 447. Verified via direct code read.
- `src/wanctl/wan_controller.py:861-1024` — `start_background_rtt()`,
  `measure_rtt()`, `_measure_rtt_blocking()`, `_record_live_rtt_snapshot()`.
  Verified via direct code read.
- `src/wanctl/wan_controller.py:1155-1433` — `verify_local_connectivity`,
  `verify_tcp_connectivity`, `verify_connectivity_fallback`,
  `handle_icmp_failure`. The preserved fallback path. Verified via direct
  code read.
- `src/wanctl/wan_controller.py:2258-2280` — `_run_rtt_measurement()` and
  the `measured_rtt is None → handle_icmp_failure()` branch.
- `src/wanctl/wan_controller.py:3383-3405` — `get_health_data()`
  measurement block build site including existing `cadence_sec` Phase 186
  addition.
- `src/wanctl/health_check.py:383-453` — `_build_measurement_section()`
  with the Phase 186 contract (`state`, `successful_count`, `stale`).
- `.planning/phases/186-measurement-degradation-contract/186-CONTEXT.md`
  decisions D-01 through D-16.
- `.planning/phases/186-measurement-degradation-contract/186-01-PLAN.md`
  Collapse Path Audit + Locked Contract sections.
- `.planning/phases/186-measurement-degradation-contract/186-02-SUMMARY.md`
  — implementation outcomes that Phase 187 inherits.
- `.planning/phases/186-measurement-degradation-contract/186-03-SUMMARY.md`
  — test patterns to extend.
- `.planning/REQUIREMENTS.md` — MEAS-02, SAFE-01, SAFE-02 definitions.
- `.planning/ROADMAP.md` — Phase 187 scope and dependency chain.
- `./CLAUDE.md` — production change policy and architectural invariants.

### Secondary (MEDIUM confidence)

- `tests/test_rtt_measurement.py:644-949` — `TestBackgroundRTTThread` +
  `TestMeasureRTTNonBlocking` existing patterns to match.
- `tests/test_health_check.py:4125-4300` — `TestMeasurementContract`
  existing fixture builders.
- `tests/test_autorate_error_recovery.py:257-530` — `handle_icmp_failure`
  regression surface.

### Tertiary (LOW confidence)

- None. All findings are verified from local code and local planning docs.
  No external web search was needed for this phase.

## Metadata

**Confidence breakdown:**

- Standard stack: HIGH — no new packages, all tooling existing.
- Architecture: HIGH — direct read of the exact call sites Phase 186 already
  enumerated in its Collapse Path Audit.
- Pitfalls: HIGH — pitfalls #1, #2, #4 are directly derived from explicit
  Phase 186 decisions (D-11, SAFE-02, GIL pattern). Pitfall #3 (first-cycle)
  and pitfall #5 (scorer double-count) are MEDIUM because they depend on
  a design choice the planner still needs to confirm.
- Validation architecture: HIGH — maps each requirement to a specific file +
  test name using existing fixture patterns.

**Research date:** 2026-04-15
**Valid until:** 2026-05-15 (30 days — stable codebase, no external deps).

---
*Phase: 187-rtt-cache-and-fallback-safety*
*Researched: 2026-04-15*
