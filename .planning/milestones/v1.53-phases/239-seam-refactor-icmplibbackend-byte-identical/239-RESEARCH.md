# Phase 239: Seam Refactor + IcmplibBackend (Byte-Identical) - Research

**Researched:** 2026-06-15
**Domain:** Python refactor — introduce an `RttBackend` Protocol seam behind the existing icmplib RTT path in a production 50ms control loop, proven byte-identical, gated by a fail-closed SAFE-17 allowlist verifier.
**Confidence:** HIGH (all claims grounded in repo files at HEAD `b136a706`; the only MEDIUM items are forward-design choices flagged in the Assumptions Log)

## Summary

This is the first controller-path-touching phase in 10 milestones. The deliverable is a *seam*, not a behavior change: a single `RttBackend` Protocol with the existing icmplib measurement refactored behind it, provably behavior-identical to the pre-refactor default. The hard parts are (1) the byte-identical proof and (2) the fail-closed SAFE-17 allowlist verifier — both have direct, exact analogs already in this repo.

The current icmplib path is **entirely contained in one module**: `src/wanctl/rtt_measurement.py` (576 lines). It exports `RTTSnapshot`, `RTTCycleStatus`, `RTTAggregationStrategy`, `RTTMeasurement`, and `BackgroundRTTThread`. `RTTSnapshot` is **only defined and produced here and consumed only inside this module** (by `BackgroundRTTThread`/`measure_rtt()` indirectly) — there is no cross-module `RTTSnapshot` import [VERIFIED: grep `RTTSnapshot` returns only `rtt_measurement.py` hits]. This is the central simplifying fact: the seam can be introduced with a very small blast radius.

Critically, the live topology means **steering does not call `RTTMeasurement` at all**. `SteeringDaemon` constructs an `RTTMeasurement` (`daemon.py:2554`) but `measure_current_rtt()` (`daemon.py:1755-1767`) reads RTT from the autorate `/health` payload (`load_live_rtt()`) and an IRTT fallback — it never pings. This confirms the ROADMAP "RTT-provenance caveat" and Phase 238 Selection A. The real live icmplib consumer is `WANController` (autorate). The "consumed by both steering and autorate" SEAM-01 requirement is satisfied by *both importing the same Protocol type from one module* — not by both invoking it on the hot path.

**Primary recommendation:** Define `RttBackend` (Protocol) + `RttSample` (frozen dataclass, strict superset of `RTTSnapshot`) in a new `src/wanctl/rtt_backend.py`. Keep `RTTSnapshot`, `RTTMeasurement`, and `BackgroundRTTThread` in `rtt_measurement.py` and make `RTTMeasurement` satisfy `RttBackend` (extract a `probe(hosts) -> dict[str,float|None]` method that wraps the existing concurrent ping). Do NOT touch aggregation math, staleness thresholds, blackout logic, or `measure_rtt()` control flow. Prove byte-identity with the existing hot-path slice (673 tests, currently green) plus a new snapshot-equivalence test asserting the refactored path produces an `RttSample` whose `RTTSnapshot`-subset fields equal the pre-refactor `RTTSnapshot` for identical inputs. Build the SAFE-17 verifier by cloning `scripts/check-safe07-source-diff.sh`'s allowlist-regex pattern (not Phase 238's zero-diff pattern) anchored at tag `v1.52`.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| icmplib ICMP probing | Measurement seam (`rtt_measurement.py`) | — | Already isolated here; the seam wraps it |
| RTT aggregation (median-of-3 / avg-of-2 / single) | Measurement seam + WANController | — | Duplicated in two places (see Pitfall 2); both are inside the allowlist |
| RTT consumption / EWMA / classification | Controller (`wan_controller.py`) | — | OUT of scope; SAFE-17 fails closed on any drift here |
| Background cadence / GIL pointer-swap thread | Measurement seam (`BackgroundRTTThread`) | — | Lifecycle owned by WANController, logic in seam |
| Steering RTT input | Autorate `/health` bridge | IRTT fallback | Steering reads health, does NOT ping (live caveat) |
| Backend selection / factory | Deferred to Phase 240/242 | — | Phase 239 lands the Protocol only, not config selection |
| SAFE-17 boundary proof | `scripts/` verifier | git | Allowlist regex over `git diff --name-only` vs `v1.52` |

## User Constraints

> No `239-CONTEXT.md` exists yet [VERIFIED: phase dir contains only this RESEARCH.md]. The binding constraints below are lifted verbatim from `REQUIREMENTS.md` and `ROADMAP.md`. If `/gsd:discuss-phase` produces a CONTEXT.md, it supersedes this section.

### Locked Decisions (from REQUIREMENTS.md / ROADMAP.md)
- **SEAM-01**: single `RttBackend` Protocol consumed by both steering and autorate, existing icmplib measurement refactored behind it (no second silo).
- **SEAM-02**: icmplib-default RTT behavior **byte-identical** to pre-refactor, proven by the hot-path test slice plus snapshot equivalence.
- **SEAM-03**: RTT samples carry backend / source-IP / loss metadata (`RttSample` as a **strict superset** of `RTTSnapshot`) without breaking `WANController.measure_rtt()`, the scorer, or other existing consumers.
- **SEAM-04**: abstraction shaped to absorb the existing IRTT path (adapter seam present); **full IRTT migration deferred** (IRTT-MIG-01, future).
- **SAFE-17**: controller-path changes stay within the narrowed v1.53 allowlist (`rtt_backend.py`, `fping_measurement.py`, `rtt_measurement.py`, factory/config/validator/health wiring) plus the REFL-01 reflector-scorer exception (Phase 241, not 239). Fail-closed source-diff verifier proves no out-of-allowlist controller-path drift (state machine, thresholds, EWMA, dwell, deadband, arbitration, fusion) at every phase boundary.

### Claude's Discretion
- Exact module name/location for the Protocol (recommend new `src/wanctl/rtt_backend.py` per the allowlist naming).
- `RttSample` field set and the coercion/adapter strategy to `RTTSnapshot`.
- Whether to extract a thin `probe()` method on `RTTMeasurement` or define the Protocol structurally around the existing public methods.

### Deferred Ideas (OUT OF SCOPE for Phase 239)
- fping backend implementation (Phase 241), config/validator (Phase 240), factory+fallback (Phase 242), benchmark gate (Phase 243), health attribution metadata wiring (Phase 244), live A/B (Phase 245), default flip (Phase 246).
- Full IRTT migration / IRTT as a new backend (IRTT-MIG-01).
- Any controller threshold / algorithm / state-machine change (EWMA, dwell, deadband, arbitration, fusion).
- REFL-01 reflector-quality scoring touch — that is the explicitly-accepted SAFE-17 exception but it lands in **Phase 241**, not 239.

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| SEAM-01 | Single `RttBackend` Protocol consumed by steering + autorate, icmplib refactored behind it | Protocol house style in `interfaces.py` (`@runtime_checkable`); `backends/RouterBackend` ABC+factory precedent; single import site per consumer |
| SEAM-02 | icmplib byte-identical, proven by hot-path slice + snapshot equivalence | Hot-path slice (673 tests) currently green; `RTTSnapshot` is frozen+slots; snapshot-equivalence test is a pure-data assertion |
| SEAM-03 | `RttSample` strict superset of `RTTSnapshot`, no consumer breakage | `RTTSnapshot` field list (lines 92-107); only consumer is `measure_rtt()`; adapter `.to_snapshot()` / superset dataclass |
| SEAM-04 | Adapter seam to absorb IRTT later, migration deferred | `IRTTResult`/`IRTTMeasurement` shape (`irtt_measurement.py`); `IRTTThread` mirrors `BackgroundRTTThread` already |
| SAFE-17 | Fail-closed allowlist source-diff verifier, no out-of-allowlist drift | `check-safe07-source-diff.sh` allowlist-regex pattern; `phase238-safe17-boundary-check.sh` JSON-evidence + dirty-tree fail-closed machinery |

## Standard Stack

### Core (already in the repo — no new dependencies)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `icmplib` | 3.0.4 | Raw-socket ICMP ping (the default backend being wrapped) | [VERIFIED: `.venv/bin/python -c "import icmplib"` → 3.0.4]; already the sole hot-path RTT source |
| `typing.Protocol` + `@runtime_checkable` | stdlib (Py 3.11) | The seam abstraction | [VERIFIED: `interfaces.py:13,20` — house pattern: all Protocols live in `interfaces.py`] |
| `dataclasses` (frozen, slots) | stdlib | `RttSample` / `RTTSnapshot` value types | [VERIFIED: `rtt_measurement.py:92` `@dataclasses.dataclass(frozen=True, slots=True)`] |
| `pytest` | repo venv | Hot-path slice + snapshot-equivalence proof | [VERIFIED: `tests/` 673-test slice runs green] |

### Supporting (existing repo conventions to reuse)
| Tool | Purpose | When to Use |
|------|---------|-------------|
| `scripts/check-safe07-source-diff.sh` | Allowlist source-diff verifier template | Clone for the SAFE-17 fail-closed allowlist verifier |
| `scripts/phase238-safe17-boundary-check.sh` | JSON-evidence + dirty-tree fail-closed machinery | Reuse the dirty-tree precheck, `--anchor` rev-parse hardening, `--out` constraint, evidence JSON record |
| `OperationProfiler` (`perf_profiler.py`) | Cycle timing instrumentation | Already used by `BackgroundRTTThread`; do not touch |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `typing.Protocol` (structural) | `abc.ABC` (nominal, like `RouterBackend`) | ABC requires explicit subclassing → forces editing `RTTMeasurement`'s base class (still in allowlist, but Protocol is the explicitly-named requirement and avoids inheritance coupling). **Use Protocol.** |
| New `rtt_backend.py` module | Defining `RttBackend` in `interfaces.py` (house style) | `interfaces.py` is the documented home for Protocols, BUT the SAFE-17 allowlist names `rtt_backend.py` explicitly. If the Protocol goes in `interfaces.py`, the allowlist must include `interfaces.py` — a much larger, riskier surface. **Use `rtt_backend.py`** to keep the allowlist tight; cross-reference it from `interfaces.py` docstring only if desired (but a docstring-only edit to `interfaces.py` would itself trip SAFE-17 — avoid). |
| `RttSample.to_snapshot()` adapter | Make `RTTSnapshot` an alias / subclass of `RttSample` | Subclassing frozen+slots dataclasses is brittle; an explicit coercion method is clearer and keeps `RTTSnapshot` byte-stable for the equivalence proof. **Use explicit coercion.** |

**Installation:** None. Zero new packages — this is a pure-refactor phase. The Package Legitimacy Audit below is therefore N/A.

## Package Legitimacy Audit

**N/A — Phase 239 installs no external packages.** It refactors existing code behind a stdlib `Protocol` and proves byte-identity. `icmplib` 3.0.4 and `fping`(future) are already present/deferred. No `npm`/`pip`/`cargo` install occurs in this phase. (slopcheck not run; nothing to check.)

## Runtime State Inventory

> This is a refactor phase, so the inventory applies. The refactor is **code-only** — it changes how RTT is *measured/typed*, not any stored/registered string.

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | None — `RTTSnapshot`/`RttSample` are in-memory frozen dataclasses, GIL-pointer-swapped, never persisted. `_record_live_rtt_snapshot` writes floats/lists to in-memory fields only. | None |
| Live service config | None — no YAML key is added in Phase 239 (config selection is Phase 240). The live `cake-autorate` deployment has `wanctl@` disabled; the seam is dormant on the live path until Phase 245. | None — but note dormancy: the refactor will not change live behavior because the live icmplib producer is the steering pinger (Selection A), not autorate. Verify against 238-PROVENANCE-MAP.md before claiming live coverage. |
| OS-registered state | None — no systemd unit, task, or process name references RTT internals. | None |
| Secrets/env vars | None — `ping_source_ip` is already read from config (`config.ping_source_ip`, `autorate_continuous.py:150`); no new secret/env var. | None |
| Build artifacts | `src/wanctl.egg-info` if installed editable — a new module `rtt_backend.py` is picked up automatically by `src` layout; no reinstall needed for namespace, but `make ci`/pytest import path must resolve the new module. | Confirm new module imports cleanly under `.venv`. |

**Canonical question — after every file is updated, what runtime systems still have old state cached?** Nothing. There is no persisted or registered representation of the RTT type system. The only "cache" is the in-process `BackgroundRTTThread._cached` pointer, recreated every cycle.

## Architecture Patterns

### System Architecture Diagram

```
                         autorate_continuous.py
                         _create_wan_components()           steering/daemon.py
                                 │                          _create_steering_components()
                                 │ constructs                       │ constructs (but DEAD on live path)
                                 ▼                                  ▼
                   ┌─────────────────────────┐          ┌──────────────────────┐
                   │  RTTMeasurement          │          │  RTTMeasurement       │
                   │  (icmplib.ping)          │          │  (MEDIAN, unused)     │
                   │  ── implements ──┐       │          └──────────────────────┘
                   └──────────────────┼───────┘                     │
                                      │                              │ steering RTT actually comes from:
                          ┌───────────▼────────────┐                ▼
                          │   RttBackend (Protocol) │      autorate /health raw_rtt_ms
                          │   [NEW — rtt_backend.py]│      (load_live_rtt) + IRTT fallback
                          │   probe()->RttSample    │      (daemon.py:1755-1767)
                          └───────────┬─────────────┘
                                      │ produces
                          ┌───────────▼─────────────┐
                          │  RttSample (NEW)         │   strict superset of:
                          │  rtt_ms, per_host, ts,   │   ┌──────────────────────────┐
                          │  measurement_ms,         │──▶│ RTTSnapshot (.to_snapshot)│
                          │  active/successful_hosts,│   │ (unchanged, frozen+slots) │
                          │  + backend, source_ip,   │   └─────────────┬────────────┘
                          │  + per_host_loss         │                 │ consumed by
                          └──────────────────────────┘                 ▼
                                      ▲                    BackgroundRTTThread._cached
                                      │ wrapped by                      │
                                      └───── BackgroundRTTThread ───────┘
                                                                        │ get_latest()
                                                                        ▼
                                                       WANController.measure_rtt()
                                                       (UNCHANGED — reads .rtt_ms,
                                                        .per_host_results, .timestamp,
                                                        .active_hosts, .successful_hosts)
                                                                        │
                                                                        ▼
                                                       EWMA / scorer / classification
                                                       (OUT OF SCOPE — SAFE-17 fails closed)
```

### Recommended Project Structure
```
src/wanctl/
├── rtt_backend.py        # NEW — RttBackend Protocol + RttSample dataclass + IRTT adapter stub (SEAM-01/03/04)
├── rtt_measurement.py    # MODIFIED — RTTMeasurement satisfies RttBackend; RTTSnapshot UNCHANGED (SEAM-02)
├── wan_controller.py      # MODIFIED minimally OR untouched — see "Anti-pattern" note (SEAM consumer)
├── irtt_measurement.py    # UNCHANGED — referenced by SEAM-04 adapter stub only
└── interfaces.py          # UNCHANGED — avoid; editing it widens the allowlist

scripts/
└── phase239-safe17-boundary-check.sh   # NEW — fail-closed allowlist verifier (SAFE-17)

tests/
├── test_rtt_backend.py    # NEW — Protocol conformance + RttSample superset + snapshot-equivalence (SEAM-02/03)
└── test_rtt_measurement.py # MODIFIED if needed — existing 61 tests must stay green
```

### Pattern 1: Protocol seam, structural (no inheritance)
**What:** Define `RttBackend` as a `@runtime_checkable Protocol`; `RTTMeasurement` satisfies it structurally without subclassing.
**When to use:** When you must add an abstraction over an existing class without editing its inheritance or touching call sites — exactly SEAM-01.
**Example:**
```python
# Source: house pattern from src/wanctl/interfaces.py:13-28 (RouterClient Protocol)
# [CITED: src/wanctl/interfaces.py]
from typing import Protocol, runtime_checkable

@runtime_checkable
class RttBackend(Protocol):
    """RTT measurement backend. icmplib is the default implementation;
    fping (Phase 241) and IRTT-adapter (SEAM-04) will satisfy the same shape."""

    def probe(self, hosts: list[str]) -> "RttSample": ...
    # source_ip / backend identity carried on the returned RttSample, not the method.
```
> **Design note:** The cleanest shape that both consumers can use without a second silo is a single `probe()`-style method that returns a rich `RttSample`. The existing `RTTMeasurement` already has `ping_hosts_with_results()` (per-host dict) and `ping_host()`. Recommend adding a thin `probe()` that wraps `ping_hosts_with_results()` + the existing aggregation and packages an `RttSample` — leaving every existing method byte-stable.

### Pattern 2: RttSample as strict superset of RTTSnapshot
**What:** `RttSample` has every `RTTSnapshot` field plus `backend`, `source_ip`, and per-host loss; a `.to_snapshot()` coercion returns the exact legacy `RTTSnapshot`.
**When to use:** SEAM-03 — extend the value type without breaking `measure_rtt()` (the only consumer of `RTTSnapshot` fields).
**Example:**
```python
# RTTSnapshot fields (UNCHANGED): rtt_ms, per_host_results, timestamp,
#   measurement_ms, active_hosts, successful_hosts
# [CITED: src/wanctl/rtt_measurement.py:92-107]
@dataclasses.dataclass(frozen=True, slots=True)
class RttSample:
    rtt_ms: float
    per_host_results: dict[str, float | None]
    timestamp: float
    measurement_ms: float
    active_hosts: tuple[str, ...] = ()
    successful_hosts: tuple[str, ...] = ()
    # --- strict superset additions (SEAM-03) ---
    backend: str = "icmplib"
    source_ip: str | None = None
    per_host_loss: dict[str, float | None] = dataclasses.field(default_factory=dict)

    def to_snapshot(self) -> RTTSnapshot:
        return RTTSnapshot(
            rtt_ms=self.rtt_ms,
            per_host_results=self.per_host_results,
            timestamp=self.timestamp,
            measurement_ms=self.measurement_ms,
            active_hosts=self.active_hosts,
            successful_hosts=self.successful_hosts,
        )
```
> **Critical:** `BackgroundRTTThread._cached` is typed `RTTSnapshot | None` and `measure_rtt()` reads `snapshot.rtt_ms`, `.per_host_results`, `.timestamp`, `.active_hosts`, `.successful_hosts` (`wan_controller.py:1151-1235`). The lowest-risk path for SEAM-02 byte-identity is to keep `_cached` as `RTTSnapshot` (so `measure_rtt()` is **literally unchanged**) and have the backend produce `RttSample` internally, coercing via `.to_snapshot()` at the publish boundary inside `BackgroundRTTThread._run`. The richer `RttSample` becomes the carrier later (Phase 244) when health attribution needs it.

### Pattern 3: SEAM-04 IRTT adapter stub (shape only, no migration)
**What:** A `class IrttRttBackend` skeleton in `rtt_backend.py` that *would* wrap `IRTTMeasurement` and map `IRTTResult` → `RttSample`, with the body `raise NotImplementedError("IRTT-MIG-01")` or a thin pass-through that proves the shape fits.
**When to use:** SEAM-04 — prove the Protocol can absorb IRTT without doing the migration.
**Why it fits:** `IRTTResult` already carries `rtt_median_ms`, `send_loss`, `receive_loss`, `server`, `timestamp`, `success` (`irtt_measurement.py:27-46`) — a clean source for `RttSample.rtt_ms` / `per_host_loss` / `source_ip`. `IRTTThread` already mirrors `BackgroundRTTThread` (same `get_latest()`/`start()`/`stop()`/`_cached` shape) so the threading seam is already symmetric.

### Anti-Patterns to Avoid
- **Editing `measure_rtt()` control flow.** It contains the blackout/zero-success/staleness logic that is explicitly OUT of scope. Any diff there is a SAFE-17 violation risk and breaks byte-identity. Keep `_cached: RTTSnapshot` so this method is untouched.
- **Putting `RttBackend` in `interfaces.py`.** Widens the SAFE-17 allowlist to a high-traffic shared file. Use the explicitly-named `rtt_backend.py`.
- **Changing aggregation math.** The median-of-3 / avg-of-2 / single rule is duplicated in `BackgroundRTTThread._run` (lines 498-503) AND `_measure_rtt_blocking` (lines 1297-1304). Do not "DRY" it in this phase — that refactor would change call sites and threaten byte-identity. Wrap, don't consolidate.
- **A second silo.** Do not create a parallel `IcmplibBackend` class that re-implements pinging. Make the *existing* `RTTMeasurement` satisfy the Protocol (it already does all the work). "IcmplibBackend" is a role, not necessarily a new class.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Source-diff allowlist verifier | A new ad-hoc diff script | Clone `scripts/check-safe07-source-diff.sh` allowlist-regex + `phase238-safe17-boundary-check.sh` JSON/dirty-tree machinery | These are battle-tested across SAFE-07..16; fail-closed semantics already correct |
| Byte-identity proof | A bespoke harness | Existing hot-path slice (`test_cake_signal/queue_controller/wan_controller/health_check`) + a small snapshot-equivalence unit test | Slice already green (673 tests); proves no regression in the actual consumers |
| Protocol conformance check | Manual hasattr checks | `@runtime_checkable` + `isinstance(rtt_measurement, RttBackend)` in a unit test | stdlib, house pattern (`interfaces.py`) |
| Frozen value type | A `dict` or `namedtuple` | `@dataclasses.dataclass(frozen=True, slots=True)` | Matches `RTTSnapshot`/`IRTTResult`; GIL-atomic pointer swap requires immutability |

**Key insight:** Every hard part of this phase already has an exact in-repo analog. The phase is mostly disciplined re-use plus a tight allowlist.

## Common Pitfalls

### Pitfall 1: Steering "consumes" the Protocol but never pings (the SEAM-01 trap)
**What goes wrong:** SEAM-01 says "consumed by both steering and autorate." A naive reading wires the Protocol into steering's live RTT path. But steering's live RTT comes from autorate `/health`, not `RTTMeasurement` (`daemon.py:1755-1767`).
**Why it happens:** The dead `RTTMeasurement` construction in `_create_steering_components` (`daemon.py:2554`) looks like a live consumer.
**How to avoid:** Satisfy SEAM-01 by having steering *import the same `RttBackend` type from the one module* (single abstraction, no second silo) — the dead steering `RTTMeasurement` already satisfies it for free. Do NOT reroute steering's live `measure_current_rtt()`. Cross-check 238-PROVENANCE-MAP.md Selection A.
**Warning signs:** Any diff to `steering/daemon.py:1755-1767` or `baseline_loader` RTT path.

### Pitfall 2: Aggregation math is duplicated — "consolidating" it breaks byte-identity
**What goes wrong:** The median-of-3/avg-of-2/single rule lives in two places (`rtt_measurement.py:498-503` and `wan_controller.py:1297-1304`). Tidying it into one helper changes call sites and risks float-path differences.
**How to avoid:** Leave both untouched. The seam wraps the *output*, not the math.
**Warning signs:** `statistics.median`/`statistics.mean` edits, or new shared aggregation helper.

### Pitfall 3: `_cached` type change cascades into `measure_rtt()`
**What goes wrong:** Changing `BackgroundRTTThread._cached` from `RTTSnapshot` to `RttSample` forces `measure_rtt()` to read superset fields, creating a diff in the most sensitive control method.
**How to avoid:** Keep `_cached: RTTSnapshot`. Produce `RttSample` inside the backend, coerce with `.to_snapshot()` at the publish line (`rtt_measurement.py:505`). `measure_rtt()` stays byte-identical.
**Warning signs:** Type-annotation changes on `_cached`, `get_latest()`, or new attribute reads in `measure_rtt()`.

### Pitfall 4: SAFE-17 anchor mismatch — Phase 238 used `v1.52`, milestone close uses `v1.52` too
**What goes wrong:** The 238 verifier hard-codes `ANCHOR="v1.52"` for a *zero-diff* assertion. Phase 239 needs the same anchor (`v1.52`, the last clean controller-path commit) but an *allowlist* assertion — the controller path is now *allowed* to change within the v1.53 allowlist.
**How to avoid:** New script `phase239-safe17-boundary-check.sh`. Anchor `v1.52` [VERIFIED: `git tag` shows `v1.52` exists]. Replace the "all controller targets must be byte-unchanged" logic with "any changed `src/wanctl/` path must match the v1.53 allowlist regex; anything else is a violation" (the SAFE-09 pattern). Keep the dirty-tree fail-closed precheck and JSON evidence record verbatim.
**Warning signs:** Re-using the 238 zero-diff script unchanged — it will FAIL the moment `rtt_measurement.py` is edited, which is the whole point of the phase.

### Pitfall 5: `__version__` bump expectation
**What goes wrong:** The SAFE-09 verifier asserted a `__version__` bump as part of its allowlist. `__init__.py` is currently `1.47.0` [VERIFIED: `src/wanctl/__init__.py`] (note: CLAUDE.md says 1.47.0; milestone tags are `v1.5x` — version string lags tags).
**How to avoid:** Do NOT add a version-bump requirement to the Phase 239 allowlist unless the milestone convention requires it. v1.53 is mid-milestone; defer any `__version__` change to milestone close (Phase 246) to avoid an unnecessary controller-path-adjacent edit. If `__init__.py` is NOT in the allowlist, do not touch it.
**Warning signs:** A `__init__.py` edit that the verifier then has to whitelist.

## Code Examples

### SAFE-17 allowlist verifier core (clone target)
```bash
# Source: scripts/check-safe07-source-diff.sh:164-200 (SAFE-09 allowlist pattern)
# [CITED: scripts/check-safe07-source-diff.sh]
DIFF_OUTPUT=$(git diff "${REF}..HEAD" -- src/wanctl/ 2>&1 || true)
if [ -n "${DIFF_OUTPUT}" ]; then
  CHANGED_PATHS=$(git diff --name-only "${REF}..HEAD" -- src/wanctl/)
  V153_ALLOWLIST_RE='^src/wanctl/(rtt_backend\.py|rtt_measurement\.py)$'   # Phase 239 surface
  DISALLOWED_PATHS=$(printf '%s\n' "${CHANGED_PATHS}" | grep -Ev "${V153_ALLOWLIST_RE}" || true)
  if [ -z "${DISALLOWED_PATHS}" ]; then
    echo "SAFE-17 OK: diff vs ${REF} bounded to v1.53 Phase-239 allowlist"; exit 0
  fi
  echo "SAFE-17 VIOLATION: out-of-allowlist controller-path drift" >&2
  printf '%s\n' "${DISALLOWED_PATHS}" >&2; exit 1
fi
echo "SAFE-17 OK: no src/wanctl/ diff vs ${REF}"; exit 0
```
> The allowlist regex must GROW per phase: Phase 240 adds config/validator files, Phase 241 adds `fping_measurement.py` + the REFL-01 reflector-scorer exception, Phase 244 adds health-wiring. Phase 239's allowlist is the narrowest: `rtt_backend.py` + `rtt_measurement.py` (and possibly a minimal `wan_controller.py` import-line change — see Open Question 1).

### Dirty-tree fail-closed precheck (reuse verbatim)
```bash
# Source: scripts/check-safe07-source-diff.sh:133-162 [CITED]
git diff --quiet -- src/wanctl/ || DIRTY_UNSTAGED=1
git diff --cached --quiet -- src/wanctl/ || DIRTY_STAGED=1
DIRTY_UNTRACKED_LIST=$(git ls-files --others --exclude-standard -- src/wanctl/ || true)
# any of the three set => VIOLATION (committed-diff check alone is not trustworthy)
```

### Snapshot-equivalence proof (new unit test shape)
```python
# Asserts the refactored backend produces an RttSample whose RTTSnapshot
# subset is byte-equal to the pre-refactor RTTSnapshot for identical inputs.
def test_rttsample_to_snapshot_byte_identical(monkeypatch):
    # feed deterministic per-host results; assert .to_snapshot() == hand-built RTTSnapshot
    sample = backend.probe(["10.0.0.1", "10.0.0.2"])
    snap = sample.to_snapshot()
    assert isinstance(snap, RTTSnapshot)
    assert snap == RTTSnapshot(rtt_ms=..., per_host_results=..., timestamp=snap.timestamp,
                               measurement_ms=snap.measurement_ms,
                               active_hosts=..., successful_hosts=...)
    assert isinstance(backend, RttBackend)  # @runtime_checkable conformance
```

## Validation Architecture

> `nyquist_validation: true` in `.planning/config.json` → section included.

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (repo `.venv`) |
| Config file | `pyproject.toml` / `Makefile` (`make test`) [VERIFIED: CLAUDE.md commands] |
| Quick run command | `.venv/bin/pytest -o addopts='' tests/test_rtt_backend.py tests/test_rtt_measurement.py -q` |
| Hot-path slice (byte-identity) | `.venv/bin/pytest -o addopts='' tests/test_cake_signal.py tests/test_queue_controller.py tests/test_wan_controller.py tests/test_health_check.py -q` |
| Full suite command | `.venv/bin/pytest tests/ -q` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| SEAM-01 | `RTTMeasurement` satisfies `RttBackend`; one abstraction | unit | `pytest tests/test_rtt_backend.py::test_protocol_conformance -x` | ❌ Wave 0 |
| SEAM-02 | icmplib byte-identical | regression | hot-path slice (above) — must stay 673 green | ✅ |
| SEAM-02 | snapshot equivalence | unit | `pytest tests/test_rtt_backend.py::test_rttsample_to_snapshot_byte_identical -x` | ❌ Wave 0 |
| SEAM-03 | `RttSample` strict superset, no consumer break | unit | `pytest tests/test_rtt_backend.py::test_rttsample_superset_fields -x` + full `test_wan_controller.py` | ✅ (consumer) / ❌ (new) |
| SEAM-04 | IRTT adapter shape present | unit | `pytest tests/test_rtt_backend.py::test_irtt_adapter_shape -x` | ❌ Wave 0 |
| SAFE-17 | allowlist verifier fails closed | script | `bash scripts/phase239-safe17-boundary-check.sh` (exit 0 clean / 1 violation) | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** quick run (`test_rtt_backend.py` + `test_rtt_measurement.py`)
- **Per wave merge:** hot-path slice (673 tests) — proves byte-identity
- **Phase gate:** full suite green + `phase239-safe17-boundary-check.sh` exit 0 before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_rtt_backend.py` — Protocol conformance, RttSample superset, snapshot equivalence, IRTT adapter shape (SEAM-01/02/03/04)
- [ ] `scripts/phase239-safe17-boundary-check.sh` — fail-closed allowlist verifier (SAFE-17)
- [ ] Confirm hot-path slice stays 673-green AFTER the refactor (no new tests needed — existing slice IS the byte-identity proof)

*(Existing `tests/test_rtt_measurement.py` (61 tests) and `tests/test_reflector_scorer.py`/`test_irtt_*.py` cover the wrapped internals; keep them green.)*

## Security Domain

> `security_enforcement` not set to false in config → section included. This is a refactor with no new external input surface; security scope is narrow.

### Applicable ASVS Categories
| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V5 Input Validation | yes (verifier CLI args) | `--anchor`/`--out` hardening already in `phase238-safe17-boundary-check.sh:52-78` — reuse: rev-parse `--end-of-options`, `--out` realpath-confined to phase evidence dir, reject `..` |
| V6 Cryptography | no | none |
| V2/V3/V4 (auth/session/access) | no | refactor adds no auth surface |
| V12 Files/Resources | yes (verifier writes JSON evidence) | confine `--out` to phase evidence dir (existing pattern) |

### Known Threat Patterns
| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Verifier `--out` path traversal into controller source | Tampering | realpath confinement + `..` rejection (already implemented in 238 script) |
| Unresolved git ref passed as anchor | Tampering | `git rev-parse --verify --end-of-options` (238 script) |
| Source-IP injection via config | (existing) | `source_ip` is operator-set config, passed to `icmplib.ping(source=...)`; unchanged by this phase |

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| SAFE-07..16 zero-diff streak (controller path byte-frozen) | SAFE-17 narrowed allowlist (controller path may change within named files) | v1.53 (this milestone) | The streak ends *by design*; the verifier inverts from "no diff" to "diff bounded to allowlist" |
| icmplib hard-wired as the only RTT path | Pluggable `RttBackend` Protocol (icmplib default) | Phase 239 (this phase) | Seam only — behavior identical until Phase 245 A/B |

**Deprecated/outdated:** Nothing deprecated in this phase. The 238 zero-diff `phase238-safe17-boundary-check.sh` is NOT reused as-is — it is superseded by the allowlist verifier (it would fail on the intended `rtt_measurement.py` edit).

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `RttBackend` should live in new `rtt_backend.py`, not `interfaces.py` | Stack/Alternatives | If discuss-phase prefers `interfaces.py`, the SAFE-17 allowlist must widen to include it — larger surface, more careful diff review |
| A2 | Keeping `BackgroundRTTThread._cached: RTTSnapshot` (coerce at publish) is the lowest-risk byte-identity path | Pitfall 3 / Pattern 2 | If planner instead retypes `_cached` to `RttSample`, `measure_rtt()` must change → byte-identity proof gets harder and SAFE-17 surface includes `wan_controller.py` |
| A3 | No `__version__` bump in Phase 239 (defer to milestone close) | Pitfall 5 | If milestone convention requires per-phase bump, `__init__.py` must enter the allowlist |
| A4 | A minimal `wan_controller.py` import-line edit may be needed if the Protocol type is referenced for typing there | Open Question 1 | If yes, `wan_controller.py` enters the allowlist for an import-only line — needs explicit operator/discuss approval since it is the most sensitive file |
| A5 | SEAM-01 is satisfied by both consumers *importing the same type*, not both invoking it live | Pitfall 1 | If the requirement is read as "steering must invoke the backend live," that contradicts the live topology (Selection A) and would be a much larger, riskier change |
| A6 | SAFE-17 anchor is tag `v1.52` (last clean controller-path commit) | Pitfall 4 | If the intended anchor is a different SHA, the verifier baseline is wrong; confirm with 238 evidence/operator |

## Open Questions

1. **Does `wan_controller.py` need ANY edit (e.g., a type import for `RttBackend`)?**
   - What we know: `measure_rtt()` reads `RTTSnapshot` fields and never references the Protocol type. The construction site is in `autorate_continuous.py`, not `wan_controller.py`.
   - What's unclear: whether the planner wants `WANController.__init__`'s `rtt_measurement: RTTMeasurement` annotation (`wan_controller.py:332`) re-typed to `rtt_measurement: RttBackend`. That is a one-line annotation change but it puts the single most sensitive file in the allowlist.
   - Recommendation: **Avoid.** Keep `wan_controller.py` byte-unchanged (annotation stays `RTTMeasurement`, which still satisfies `RttBackend` structurally). Surface to discuss-phase if SEAM-01 is read to require it. (Assumption A4.)

2. **Should the SEAM-04 IRTT adapter be a real pass-through or a `NotImplementedError` stub?**
   - What we know: `IRTTResult` → `RttSample` mapping is mechanically clean; full migration is explicitly deferred (IRTT-MIG-01).
   - Recommendation: A shape-proving stub (constructs the mapping, raises `NotImplementedError("IRTT-MIG-01")` or returns a clearly-marked sample) plus a unit test asserting the field mapping compiles. Enough to satisfy "adapter seam present" without doing the migration.

3. **Does the live path get any coverage in Phase 239?**
   - What we know: live deployment is `cake-autorate` with `wanctl@` disabled; the seam is dormant on the live path. The live icmplib producer (per Selection A) is the steering pinger, evaluated at Phase 245.
   - Recommendation: Phase 239 is offline-proven only (tests + verifier). State explicitly in the plan that no live deploy happens here. Cross-reference 238-PROVENANCE-MAP.md.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.11+ | refactor + tests | ✓ | `.venv` | — |
| icmplib | wrapped backend | ✓ | 3.0.4 | — |
| pytest | byte-identity proof | ✓ | repo venv (673-test slice runs green in ~43s) | — |
| git + `v1.52` tag | SAFE-17 anchor | ✓ | tag present | — |
| `fping` | NOT this phase | n/a | deferred to 241 | n/a |

**Missing dependencies with no fallback:** None — Phase 239 is fully serviceable offline with existing tooling.

## Sources

### Primary (HIGH confidence — repo files at HEAD `b136a706`)
- `src/wanctl/rtt_measurement.py` (full read) — `RTTSnapshot`/`RTTMeasurement`/`BackgroundRTTThread`, aggregation, blackout logic
- `src/wanctl/wan_controller.py:1080-1395` — `measure_rtt()`, `_measure_rtt_blocking()`, construction
- `src/wanctl/steering/daemon.py:1755-1822, 2544-2561` — live RTT path is health/IRTT, not RTTMeasurement
- `src/wanctl/autorate_continuous.py:120-170` — autorate construction site
- `src/wanctl/irtt_measurement.py:1-120`, `irtt_thread.py:1-75` — SEAM-04 adapter source shape
- `src/wanctl/interfaces.py:13-117` — Protocol house style (`@runtime_checkable`)
- `src/wanctl/backends/base.py:1-40` — ABC+factory precedent
- `src/wanctl/health_check.py:486-524` — health measurement contract (Phase 244 forward-context)
- `scripts/check-safe07-source-diff.sh` (full) — allowlist source-diff verifier template
- `scripts/phase238-safe17-boundary-check.sh` (full) — JSON-evidence + dirty-tree + arg-hardening machinery
- `.planning/REQUIREMENTS.md`, `.planning/ROADMAP.md`, `.planning/STATE.md` — SEAM/SAFE-17 definitions, live caveat, Selection A
- `.planning/phases/238-.../238-PATTERNS.md` — established script conventions

### Verified via tooling
- `git tag` → `v1.50/v1.51/v1.52` present (SAFE-17 anchor confirmed)
- `.venv/bin/python -c "import icmplib"` → 3.0.4
- hot-path slice → 673 passed in 42.66s (green baseline for byte-identity)
- `grep RTTSnapshot src/wanctl` → only `rtt_measurement.py` (no cross-module consumer)

### Tertiary
- None — every claim is grounded in repo files or tooling output.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — zero new deps; everything verified in `.venv`/repo
- Architecture: HIGH — single-module containment of `RTTSnapshot`; consumers fully mapped via grep
- Pitfalls: HIGH — duplicated aggregation, dead steering path, and anchor mismatch all verified in code
- SAFE-17 verifier: HIGH — exact allowlist analog (`check-safe07-source-diff.sh`) + hardening analog (`phase238-...`) exist
- Forward design (RttSample fields, module placement): MEDIUM — defensible defaults; flagged in Assumptions Log for discuss-phase

**Research date:** 2026-06-15
**Valid until:** 2026-07-15 (stable internal refactor; no fast-moving external dependency)
