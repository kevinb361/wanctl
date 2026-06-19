# Phase 244: Health-Payload Attribution Metadata - Research

**Researched:** 2026-06-18
**Domain:** Observability / `/health` payload contract surfacing (additive metadata on a production 24/7 control system)
**Confidence:** HIGH (all file/line claims verified against live `src/` and `deploy/scripts/` at HEAD `8d3969ab`; no external libraries involved)

## Summary

Phase 244 is a **purely additive, internal-data-surfacing phase**. Every fact it needs to
expose already exists in code: `RttSample.backend` and `RttSample.source_ip` are populated
end-to-end by both backends (verified), the autorate `/health` `measurement` block already
carries `backend_active` (242), and the per-WAN configured source IP is reachable on both
the autorate (`config.ping_source_ip`) and steering (`primary_cfg["ping_source_ip"]`) paths.
The work is wiring three `/health` producers to emit a uniform **attribution triple**
(`producer`, `backend`, `source_ip`) without moving or mutating the byte-preserved contract
fields (`raw_rtt_ms`, `available`, `staleness_sec`).

There is one genuine asymmetry the planner must respect: the **state-bridge truly does not
know a source IP** (verified — it only carries `WANCTL_EXTERNAL_DL_IF`/`UL_IF` interface
names, no `ping_source_ip` env). This makes D-02's mandate (`producer="cake-autorate-bridge"`,
`backend=null`, `source_ip=null`) not a stylistic choice but the only honest value. Do **not**
add new bridge env wiring to learn a source IP — that is out of 244's additive scope and the
bridge never ran the wanctl seam anyway (238 D-04).

The single largest risk is **SAFE-17**: this is the first intentional controller-path
health-shape change of v1.53. The existing per-phase verifiers (`phase242`/`phase243`) will
**fail closed** on 244's diff — not because the files are out of allowlist (they aren't), but
because phase 242's verifier additionally asserts `health_check.py`/`wan_controller.py`
*protected bodies* are byte-identical via `phase239-protected-body-diff.py`. 244 must ship its
**own** `phase244-safe17-boundary-check.sh` (cloned from 242, anchor advanced to the 242/243
close, allowlist unchanged, protected-body exception widened to permit the additive health
diff while still proving zero classification/EWMA/dwell/deadband/arbitration/fusion drift).

**Primary recommendation:** Thread the attribution triple through all three producers as flat
keys; add a contract-snapshot test pinning the existing measurement keys+types and asserting
strict-superset; ship a dedicated `phase244-safe17-boundary-check.sh` + mirror test that
advances the anchor and widens the protected-body exception to the new health surface only.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Surface `backend`/`source_ip`/`producer` on autorate `/health` | API/Backend (`health_check.py` payload builder) | Backend data (`wan_controller.get_health_data`) | The builder owns JSON shape; the controller owns the source data threaded into it |
| Surface attribution on steering `/health` | API/Backend (`steering/health.py` `_build_rtt_source_section`) | Backend wiring (`steering/daemon.py`) | Steering daemon must first *carry* the handle/source_ip (it currently discards them) before health.py can emit them |
| Surface attribution on live production `/health` | Deploy script (`cake-autorate-*-state-bridge` `health_payload()`) | — | The bridge is the live `/health` today (both WANs on cake-autorate); it owns its own payload |
| SAFE-17 zero-drift proof | Verification tooling (`scripts/phase244-safe17-boundary-check.sh`) | — | Git-diff + AST protected-body gate; deployment-specific, not controller code |
| Byte-preservation proof | Test tier (`tests/`) | — | Contract-snapshot test pinning existing keys+types |

## Standard Stack

No external packages. This phase touches only first-party Python (`src/wanctl/`), one bash
verifier under `scripts/`, two deploy scripts under `deploy/scripts/`, and pytest tests. The
"Package Legitimacy Audit", "Environment Availability", and external-dependency sections are
therefore **not applicable** — see explicit skip notes below.

**Package Legitimacy Audit:** N/A — phase installs no external packages.

**Environment Availability:** Step 2.6 SKIPPED — no new external tools/services/runtimes.
Existing dev toolchain (`.venv/bin/pytest`, `ruff`, `mypy`, `git`, `python3`, `bash`,
`realpath`) is already present and exercised by the established SAFE-17 verifiers.

## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** Expose `backend` + `source_ip` attribution on **all three** `/health` producers:
  (1) `steering/health.py` — **primary surface** (the A/B measures here under Selection A),
  (2) `health_check.py` (autorate controller), (3) `cake-autorate-{spectrum,att}-state-bridge`.
- **D-02 (MANDATORY, all surfaces):** Add a separate **`producer`** field naming the
  RTT-producing process class — do NOT overload `backend`. Values:
  - `producer: "wanctl-backend"` → RTT from the wanctl `RttBackend` seam (steering + autorate);
    `backend` is then `icmplib`/`fping`.
  - `producer: "cake-autorate-bridge"` → RTT parsed from upstream bash cake-autorate's EWMA
    log; the wanctl seam never ran (238 D-04), so `backend` MUST be `null` and `source_ip` MUST
    be `null` (unless the bridge genuinely knows the configured source — see research item R1).
- **D-03 (Claude's discretion, default ratified):** Add a **new per-sample `backend`** field =
  the backend that produced the *current* sample (`RttSample.backend`), valued
  `icmplib`|`fping`|`null`. Keep Phase 242's `backend_active` (factory-*selected* backend).
  After a loud fallback, producing vs selected can differ; preserving both maximizes A/B
  fidelity. `backend_active` is byte-preserved (242 contract field).
- **D-04 (Claude's discretion, default ratified):** `source_ip` = the **per-WAN
  configured/intended source IP** the backend binds with (`-S` fping; `source=` icmplib),
  emitting `null` when none configured. Placed flat alongside `backend`/`producer`. `null` on
  the bridge path and on any path with no configured source.
- **D-05 (deferred to planner):** Planner chooses verification mechanics. Recommended: a
  contract-snapshot test pinning existing measurement keys+types asserting additive-only, plus
  advancing the SAFE-17 anchor past the 242-close anchor so the health diff is inside the
  allowlist. This is the **first intentional controller-path health-shape change of v1.53** —
  the SAFE-17 anchor WILL need updating, not just passing as-is.

### Claude's Discretion
- D-03 (`backend` key semantics), D-04 (`source_ip` semantics), D-05 (SAFE-17 mechanics).
- Exact key nesting (CONTEXT recommends flat keys, not a nested object, so consumers parse
  them like the existing `backend_active`).

### Deferred Ideas (OUT OF SCOPE)
- Flipping steering to consume its own pinger / live A/B execution → **Phase 245** (AB-01).
- Reviving the dead `RTTMeasurement` consumption path.
- Native autorate producer (Interpretation B) → **NATIVE-AB-01**, deferred out of v1.53.
- Any new backend behavior / backend selection logic / controller algorithm/timing/threshold.
- Whether the state-bridge should *learn* the per-WAN `ping_source_ip` via new env wiring →
  research item R1 resolves this as **defer / not needed** (see below).

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| HEALTH-01 | `/health` additively exposes `measurement.backend` + `source_ip` so every RTT sample is attributable during the A/B; existing contract (`raw_rtt_ms`, `available`, `staleness_sec`) byte-preserved | Producers + exact attach points mapped (§Architecture); `RttSample` already carries both fields (verified §R5); contract-snapshot test pattern identified (§Validation) |
| SAFE-17 | Controller-path changes stay within the narrowed v1.53 allowlist; fail-closed source-diff verifier proves no out-of-allowlist drift at the phase boundary | SAFE-17 anchor/allowlist/protected-body mechanics fully mapped (§SAFE-17 Mechanics); minimal edit to permit the additive diff identified |

## Architecture Patterns

### System Architecture Diagram (data flow of the attribution triple)

```
                       ┌─────────────────────────────────────────────┐
                       │  RttSample (rtt_backend.py:36-54)            │
                       │  .backend = "icmplib" | "fping"   (verified) │
                       │  .source_ip = <configured -S/source=> | None │
                       └───────────────┬─────────────────────────────┘
            produced by                │  produced by
   rtt_measurement.py:350-359          │  fping_measurement.py:122-132
   (icmplib: backend="icmplib",        │  (fping: backend="fping",
    source_ip=self.source_ip)          │   source_ip=self._source_ip)
                                       │
        ┌──────────────────────────────┴──────────────────────────────┐
        │                                                              │
  AUTORATE PATH                                              STEERING PATH (PRIMARY)
  wan_controller.measure_rtt (1166)                          steering/daemon.py
   → _record_live_rtt_snapshot (1350)  ← stores rtt/ts/hosts  (rtt_source observability,
      [does NOT store backend/source_ip today — see R3a]       1157-1166, 1425-1435)
        │                                                              │
   get_health_data() (4481)                                   _create_steering_components (2545)
    measurement{} block (4539-4556)                            builds handle, then DISCARDS
     backend_active/fell_back/fallback_count                   handle + source_ip (returns only
     from _rtt_backend_status (4496-4509)                      rtt_measurement) — see R3b
        │                                                              │
   health_check.py:_build_measurement_section (454-532)        SteeringHealthServer
    returns measurement dict (520-532)                          _build_rtt_source_section (359)
    ADD: producer/backend/source_ip                             emits rtt_source{} block
                                                                ADD: producer/backend/source_ip
        │                                                              │
        └──────────────────────────────┬───────────────────────────────┘
                                        ▼
  PRODUCTION /health TODAY (both WANs on cake-autorate):
  deploy/scripts/cake-autorate-{spectrum,att}-state-bridge :: health_payload() (234-296)
   measurement{available,raw_rtt_ms,staleness_sec}  ← from cake-autorate EWMA log, NOT the seam
   ADD: producer="cake-autorate-bridge", backend=null, source_ip=null   (D-02 honesty)
```

### Pattern 1: Additive flat-key health block (FOLLOW EXACTLY)
**What:** Append new keys to the existing returned dict without reordering or mutating
existing keys. Established by Phase 186/240/242 in `_build_measurement_section`.
**When to use:** All three producers.
**Example (verified, `health_check.py:520-532`):**
```python
# Source: src/wanctl/health_check.py:520 (HEAD) — Phase 242's additive precedent
return {
    "available": raw_rtt is not None,        # BYTE-PRESERVED (238 contract)
    "raw_rtt_ms": round(raw_rtt, 2) if raw_rtt is not None else None,  # BYTE-PRESERVED
    "staleness_sec": round(staleness, 3) if staleness is not None else None,  # BYTE-PRESERVED
    "active_reflector_hosts": list(active_hosts),
    "successful_reflector_hosts": list(successful_hosts),
    "state": state,
    "successful_count": successful_count,
    "stale": stale,
    "backend_active": backend_active,        # Phase 242 — now a contract field (D-03 keeps it)
    "fell_back": bool(measurement.get("fell_back", False)),
    "fallback_count": fallback_count,
    # Phase 244 additive triple appends HERE:
    # "producer": "wanctl-backend",
    # "backend": <RttSample.backend | None>,
    # "source_ip": <configured source ip | None>,
}
```

### Pattern 2: Source-data threading via `getattr` with safe default (FOLLOW)
**What:** `wan_controller.get_health_data()` reads optional attribution off
`_rtt_backend_status` with `getattr(..., default)` so a `None` status (no factory) degrades
safely. Established at `wan_controller.py:4496-4509` for `backend_active`.
**When to use:** Threading `source_ip` (and per-sample `backend`) through the autorate path.

### Anti-Patterns to Avoid
- **Adding bridge env wiring to fake a source IP** — violates D-02 honesty and 244's additive
  scope. The bridge never ran the seam; `source_ip: null` / `backend: null` is correct.
- **Reordering or mutating `raw_rtt_ms`/`available`/`staleness_sec`** — breaks 238 contract.
- **Reusing the 242/243 verifier as-is** — it will fail closed on the legitimate health diff
  via its protected-body assertion. 244 needs its own advanced verifier (see §SAFE-17).
- **Nesting the triple in a sub-object** — CONTEXT specifies flat keys for parse parity with
  `backend_active`.
- **Threading per-sample `backend` into the autorate path via a new controller field if it
  forces a `measure_rtt` body change beyond the allowlisted/exception scope** — see R3a; a
  simpler `backend_active`-as-proxy or a minimal additive `_last_*` store may be preferable.

## SAFE-17 Mechanics (D-05 — the load-bearing section)

### Anchor / allowlist / verifier topology (verified)
- **Per-phase verifiers are clones, not a shared script.** `scripts/` contains
  `phase238…phase243-safe17-boundary-check.sh`. Phase 244 ships **its own**
  `scripts/phase244-safe17-boundary-check.sh` + `tests/test_phase244_safe17_verifier.py`
  (mirror of `tests/test_phase243_safe17_verifier.py`). This is the established cadence.
- **243 was measurement-only** — its verifier (`scripts/phase243-safe17-boundary-check.sh`)
  hard-rejects *any* `src/wanctl/` diff vs anchor `fcc2e15b` (the 242 close). 244 cannot clone
  243; it must clone **242**, which has the real allowlist + protected-body machinery.
- **242 verifier (`scripts/phase242-safe17-boundary-check.sh`) is the template.** Its
  `V153_ALLOWLIST_RE` (line 25) **already includes** every file 244 touches:
  `health_check.py` and `wan_controller.py` are in the allowlist; `steering/daemon.py` is in
  the allowlist. So the **path allowlist needs no change** for the autorate + steering edits.
- **The blocker is the protected-body layer, not the path allowlist.** The 242 verifier also:
  1. Calls `phase239-protected-body-diff.py --anchor v1.52` and requires `all_identical` OR a
     *single* exception limited to `WANController.measure_rtt`
     (`protected_body_ok_with_measure_rtt_exception`, lines 373-402).
  2. Asserts the RTT seam (`rtt_backend.py`, `rtt_measurement.py`) is **unchanged since the
     Phase 239 close** (lines 506-514).
  3. Asserts `fping_measurement.py`/`reflector_scorer.py` byte-identical since 241 close.
  4. Runs `check_measure_rtt_fping_scorer_guard` AST assertions on `measure_rtt`.

### What 244's verifier must do (minimal edit that preserves zero-drift guarantee)
1. **Advance the anchor.** Set `ANCHOR` to the **Phase 243 close commit** (current candidate:
   the 243 close; note `tests/test_phase243_safe17_verifier.py:22` pins
   `PHASE_CLOSE_ANCHOR = 380fadbd…` as a *temporary scaffolding baseline with a
   `TODO(phase-close)` to repin to the actual 243 close*). The planner must resolve the true
   243-close SHA at plan time (verify with `git log` on the 243 evidence/close commit) and pin
   it; do not blindly copy `380fadbd` which the test comment itself flags as provisional.
2. **Keep `V153_ALLOWLIST_RE` unchanged** — `health_check.py`, `wan_controller.py`,
   `steering/daemon.py` are already allowlisted. (If the planner chooses to surface attribution
   on `steering/health.py`, **that file is NOT in the 242 allowlist regex** — verify and add
   `steering/health\.py` to the regex. This is the one likely allowlist addition.)
3. **Widen the protected-body exception to the health surface only.** The 242 exception
   (`protected_body_ok_with_measure_rtt_exception`) permits exactly one non-identical protected
   function (`WANController.measure_rtt`). 244's additive diff to `get_health_data` /
   `_build_measurement_section` / `_build_rtt_source_section` will trip the protected-body
   diff. The 244 verifier must permit those specific health-builder functions to differ **while
   still asserting** the classification/EWMA/dwell/deadband/arbitration/fusion bodies are
   byte-identical. Keep `check_measure_rtt_fping_scorer_guard`'s `FORBIDDEN_TOKENS`
   (`EWMA/ewma/dwell/deadband/arbitration/fusion/factor_down/step_up/ceiling/floor`) assertion
   in force over the changed functions so the additive health diff structurally cannot
   introduce control-logic drift.
4. **Re-evaluate the RTT-seam-unchanged assertion.** If 244 surfaces per-sample `backend` by
   touching `rtt_backend.py` (it should NOT need to — R5 confirms the data already exists), the
   "seam unchanged since 239" gate (242 lines 506-514) would fire. Plan to **not** touch the
   seam files; surface from already-stored data instead.
5. **Mirror test** (`tests/test_phase244_safe17_verifier.py`): assert the script is executable,
   pins the advanced anchor, rejects a committed out-of-allowlist edit (e.g.
   `queue_controller.py`) in a detached worktree, and rejects a dirty `src/wanctl/` tree —
   exactly the shape of `test_phase243_safe17_verifier.py` (verified, 109 lines).

### SAFE-17 boundary-test pinning caveat (from project memory)
Per-phase SAFE-17 boundary tests **rot against HEAD** as later phases land. Pin the worktree
fixture to the resolved 243-close anchor, **not HEAD**. The full pytest suite is known to carry
~34 pre-existing stale-boundary failures from earlier phases — do not treat those as 244
regressions; gate on the **focused 244 verifier + focused hot-path slice** instead of full-suite
green for this specific guarantee. (Source: project MEMORY.md.)

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Per-sample backend/source attribution data | A new backend-tagging mechanism | `RttSample.backend` / `RttSample.source_ip` (already populated, R5) | Data exists end-to-end; 244 only surfaces it |
| SAFE-17 verifier | A new diff approach | Clone `phase242-safe17-boundary-check.sh` + `phase239-protected-body-diff.py` | Established 6-phase pattern; auditable; fail-closed proven |
| Byte-preservation proof | Ad-hoc field checks | Contract-snapshot test (pin keys+types, assert superset) | D-05 recommendation; matches existing `test_health_check` assertion style |
| Bridge source IP | New env var + `ip route` lookup in bash | `source_ip: null` (D-02) | Bridge never ran the seam; faking it lies; out of additive scope (R1) |

**Key insight:** This phase's entire risk surface is *not adding new behavior* — it is proving
the additive diff did not perturb the control path. Lean on the existing seam data and the
existing verifier machinery; the novel work is the 244 verifier's protected-body exception.

## Runtime State Inventory

> Not a rename/refactor/migration. This is additive code surfacing internal data. The standard
> 5-category inventory does not apply. The one *deployment* concern: the live `/health` is
> served by the **deploy script bridge**, not `health_check.py` (both WANs on cake-autorate
> since 2026-06-08). Therefore:

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Live service config (the real prod `/health`) | `cake-autorate-{spectrum,att}-state-bridge` `health_payload()` is the production endpoint; the two scripts are **byte-identical in the health_payload region** (verified by `diff`) | Apply the identical additive triple to BOTH scripts; do not let them drift |
| Stored data | None — no datastore stores the attribution; it is computed per-request from in-memory `RttSample`/state JSON | None |
| OS-registered state | None — no task/timer/unit embeds attribution strings | None — verified (service names unchanged) |
| Secrets/env vars | Bridge env (`WANCTL_EXTERNAL_*`) carries `DL_IF`/`UL_IF` only, **no `ping_source_ip`** (verified, bridge lines 16-31) | None — confirms `source_ip: null` on bridge (R1) |
| Build artifacts | None — pure source surfacing | None |

## Common Pitfalls

### Pitfall 1: The 242/243 verifier blocks the legitimate health diff
**What goes wrong:** Running `phase242`/`phase243` boundary check after 244's edits fails
closed.
**Why:** 243 rejects any `src/wanctl/` diff; 242 rejects any protected-body change beyond the
`measure_rtt` exception. 244's health-builder diff trips both.
**How to avoid:** Ship `phase244-safe17-boundary-check.sh` with advanced anchor + widened
protected-body exception (see §SAFE-17). Run the **244** verifier, not the older ones.
**Warning signs:** `SAFE-17 VIOLATION: protected-body or allowed-shape drift` on a diff you
know is health-only.

### Pitfall 2: Steering daemon discards the handle and source_ip
**What goes wrong:** Trying to emit `backend`/`source_ip` in `steering/health.py` finds no
data on the daemon.
**Why (verified):** `_create_steering_components` (daemon.py:2545) builds the handle, extracts
`rtt_measurement`, and **returns only `state_mgr, router, rtt_measurement, baseline_loader`**
(line 2571) — the handle, `backend_active`, and `source_ip` are dropped. `SteeringDaemon.__init__`
(line 1126) never receives them.
**How to avoid:** Plan an additive wiring step: carry `source_ip` (and `backend_active`/the
handle) from `_create_steering_components` → `SteeringDaemon.__init__` → a `self._` field →
`_build_rtt_source_section`. This is the largest of the three producer touches and lands in
`steering/daemon.py` (allowlisted) + `steering/health.py` (verify allowlist regex includes it).

### Pitfall 3: Autorate per-sample `backend` is not stored on the controller
**What goes wrong:** `_build_measurement_section` wants `RttSample.backend`, but
`_record_live_rtt_snapshot` (wan_controller.py:1350) stores only `rtt_ms/ts/hosts` — **not**
`backend`/`source_ip` (verified).
**Why:** The snapshot publisher predates the seam metadata.
**How to avoid:** Two viable options for the planner:
  (a) **Proxy via `backend_active`** for the autorate path's per-sample `backend` (simplest;
      `backend_active` already threaded at 4496). After fallback this can differ from the
      true producing backend, slightly reducing fidelity but staying inside the existing
      threading.
  (b) **Add an additive `self._last_sample_backend`/`_last_sample_source_ip`** set in
      `_record_live_rtt_snapshot` and read in `get_health_data`. More faithful to D-03 but a
      larger `wan_controller.py` touch — must stay clear of the `measure_rtt` protected body.
  The **steering path is the A/B-critical surface** (Selection A); prioritize fidelity there.
  CONTEXT D-03's fidelity rationale ("preserving both maximizes A/B fidelity") argues for (b)
  on steering; (a) is acceptable on the non-A/B autorate path. Planner decides.

### Pitfall 4: The two bridge scripts drift
**What goes wrong:** Editing only `cake-autorate-spectrum-state-bridge`.
**Why:** Both WANs run; both serve `/health`; tests cover both
(`test_{spectrum,att}_cake_autorate_artifacts.py`).
**How to avoid:** Apply the identical additive triple to both; the health_payload regions are
currently byte-identical — keep them so.

## Code Examples

### Bridge additive triple (D-02 honesty)
```python
# Source: deploy/scripts/cake-autorate-*-state-bridge :: health_payload() (verified 234-296)
"measurement": {
    "available": available,                          # BYTE-PRESERVED
    "raw_rtt_ms": float(raw_rtt) if isinstance(raw_rtt, (int, float)) else None,  # PRESERVED
    "staleness_sec": age,                            # BYTE-PRESERVED
    # Phase 244 additive — bridge never ran the wanctl seam (238 D-04):
    "producer": "cake-autorate-bridge",
    "backend": None,
    "source_ip": None,
},
```
Apply identically to the degraded-path measurement block (bridge lines 243) too, so the triple
is uniform across both code paths of the bridge.

### Steering source_ip is reachable (verified, daemon.py:2612)
```python
# Source: src/wanctl/steering/daemon.py:2612 — steering DOES have the configured source IP
source_ip = primary_cfg.get("ping_source_ip")
if not isinstance(source_ip, str) or not source_ip:
    source_ip = None  # → D-04 null when unconfigured
```

### Autorate source_ip is reachable (verified, autorate_continuous.py:145)
```python
# Source: src/wanctl/autorate_continuous.py:145
rtt_backend = build_rtt_backend(config, source_ip=config.ping_source_ip, ...)
```

## State of the Art

N/A — no evolving external ecosystem. The only "state of the art" is the project's own SAFE-17
verifier pattern, which has advanced anchor-by-anchor across phases 238→243 (verified by the
distinct `phase23N-safe17-boundary-check.sh` clones).

## Resolved Research Items (from CONTEXT.md)

### R1 — Bridge `source_ip` access → RESOLVED: emit `source_ip: null` (do not wire)
**Verified:** The bridge (`cake-autorate-spectrum-state-bridge` lines 16-31) reads only
`WANCTL_EXTERNAL_WAN_NAME`, `WANCTL_EXTERNAL_DL_IF`, `WANCTL_EXTERNAL_UL_IF`, log/state/metrics
paths, baseline RTT, UID/GID, poll/health host/port, max-state-age. **No `ping_source_ip`,
no source-IP env of any kind.** It parses RTT from cake-autorate's EWMA log and never invokes
the wanctl seam. Per D-02 this mandates `source_ip: null`, `backend: null`. Learning the source
IP would require new env wiring + an `ip route`-style derivation — **out of 244's additive
scope and explicitly deferred** in CONTEXT. Confidence: HIGH.

### R2 — SAFE-17 boundary mechanics → RESOLVED (see §SAFE-17 Mechanics)
Clone `phase242` (not `phase243`), advance the anchor to the resolved 243-close SHA, keep the
path allowlist (add `steering/health\.py` to the regex only if attribution is surfaced there),
widen the protected-body exception to the health-builder functions while retaining the
forbidden-token / control-body byte-identity guarantees. Confidence: HIGH.

### R3 — Three producers: attach points & emitted keys → RESOLVED
- **Autorate:** add triple to the `_build_measurement_section` return
  (`health_check.py:520-532`); thread `source_ip` through `get_health_data()`'s `measurement`
  dict (`wan_controller.py:4539-4556`, which sets `backend_active` at 4553 but not `source_ip`).
  Per-sample `backend`: see Pitfall 3 (R3a — not currently stored on the controller).
- **Steering (primary):** `_build_rtt_source_section` (`steering/health.py:359-377`) emits an
  `rtt_source` block, NOT a `measurement` block. Add the triple keys here so emitted JSON keys
  match (uniform keys, not a shared code path — CONTEXT's explicit nuance). Requires daemon
  wiring first (R3b — `_create_steering_components` currently discards handle+source_ip,
  daemon.py:2571).
- **Bridge:** `health_payload()` (`cake-autorate-*-state-bridge:234-296`) — add triple to both
  the healthy and degraded measurement blocks; `producer="cake-autorate-bridge"`, `backend`/
  `source_ip` null. Top-level already labeled `source: "cake-autorate-state-bridge"`.
Confidence: HIGH.

### R4 — Byte-preservation verification → RESOLVED (see §Validation Architecture)
Cleanest mechanism: a contract-snapshot test that constructs the autorate `/health` payload (or
calls `_build_measurement_section`) with a representative `health_data`, asserts the exact
existing keys+types (`raw_rtt_ms: float|None`, `available: bool`, `staleness_sec: float|None`,
plus 242's `backend_active`/`fell_back`/`fallback_count`), and asserts the new keys are a
strict superset. Pattern matches existing `test_health_check.py` assertions
(e.g. `measurement["backend_active"] == "fping"` at line 1954). For the bridge, extend the
existing `test_state_bridge_serves_wanctl_compatible_health_endpoint`
(`test_spectrum_cake_autorate_artifacts.py:164-210`, which already asserts
`measurement.raw_rtt_ms/available/staleness_sec`) to assert the additive triple + preservation.
Confidence: HIGH.

### R5 — RttSample data availability → RESOLVED: confirmed, data already exists
**Verified:** `RttSample` (`rtt_backend.py:36-54`) carries `backend: str = "icmplib"` (line 52)
and `source_ip: str | None = None` (line 53), frozen+slots. icmplib populates them
(`rtt_measurement.py:355-358`: `backend="icmplib", source_ip=self.source_ip`); fping populates
them (`fping_measurement.py:129-130`: `backend="fping", source_ip=self._source_ip`, with `-S`
bind at line 147). 244 only **surfaces** existing data; it touches **no** seam file. Confidence:
HIGH.

## Validation Architecture

> `workflow.nyquist_validation` not disabled — section included.

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (`.venv/bin/pytest`); ruff + mypy for lint/type |
| Config file | `pyproject.toml` (has `addopts`; SAFE-17 verifiers run with `-o addopts=''`) |
| Quick run command | `.venv/bin/pytest -o addopts='' tests/test_health_check.py tests/test_phase244_safe17_verifier.py -q` |
| Full suite command | `.venv/bin/pytest tests/ -q` (NOTE: carries ~34 pre-existing stale-boundary failures — see SAFE-17 pinning caveat; do not gate 244 on full-suite green) |
| Hot-path regression slice | `.venv/bin/pytest -o addopts='' tests/test_cake_signal.py tests/test_queue_controller.py tests/test_wan_controller.py tests/test_health_check.py -q` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| HEALTH-01 | Autorate `/health` measurement adds `producer`/`backend`/`source_ip`; existing keys+types byte-preserved | unit/contract | `.venv/bin/pytest -o addopts='' tests/test_health_check.py -k "measurement or backend or contract" -q` | ✅ extend `tests/test_health_check.py` |
| HEALTH-01 | Steering `/health` `rtt_source` adds the same triple | unit | `.venv/bin/pytest -o addopts='' tests/test_steering_health*.py -q` | ❌ Wave 0 — confirm/extend steering health test |
| HEALTH-01 | Bridge `/health` adds `producer="cake-autorate-bridge"`, `backend=null`, `source_ip=null`; existing fields preserved | integration | `.venv/bin/pytest -o addopts='' tests/test_spectrum_cake_autorate_artifacts.py tests/test_att_cake_autorate_artifacts.py -q` | ✅ extend existing endpoint test (spectrum:164) |
| HEALTH-01 | `backend`/`source_ip` populated from real `RttSample` (icmplib + fping) | unit | `.venv/bin/pytest -o addopts='' tests/test_rtt_measurement.py tests/test_fping_measurement.py -k source_ip -q` | ✅ already assert source_ip |
| SAFE-17 | 244 verifier rejects out-of-allowlist edit + dirty tree; passes on additive health diff | unit | `.venv/bin/pytest -o addopts='' tests/test_phase244_safe17_verifier.py -q` | ❌ Wave 0 — new mirror test |
| SAFE-17 | Control bodies (EWMA/dwell/deadband/arbitration/fusion) byte-identical; forbidden tokens absent | script | `bash scripts/phase244-safe17-boundary-check.sh` | ❌ Wave 0 — new verifier |

### Sampling Rate
- **Per task commit:** quick run (`test_health_check.py` + `test_phase244_safe17_verifier.py`).
- **Per wave merge:** hot-path slice + both bridge artifact tests + `bash scripts/phase244-safe17-boundary-check.sh`.
- **Phase gate:** `phase244-safe17-boundary-check.sh` passes (zero out-of-allowlist drift,
  control bodies byte-identical) + focused contract tests green. Full suite NOT a gate (stale
  boundary failures).

### Wave 0 Gaps
- [ ] `scripts/phase244-safe17-boundary-check.sh` — cloned from `phase242`, anchor advanced to
      resolved 243-close SHA, protected-body exception widened to health builders, allowlist
      regex extended with `steering/health\.py` iff that file is touched.
- [ ] `tests/test_phase244_safe17_verifier.py` — mirror of `test_phase243_safe17_verifier.py`,
      pinned to the resolved 243-close anchor (NOT HEAD).
- [ ] Steering health test coverage for the triple — confirm a `tests/test_steering_health*.py`
      exists or add the assertion; the daemon-wiring path (handle/source_ip carry) needs a test.
- [ ] Contract-snapshot assertion in `tests/test_health_check.py` pinning existing keys+types
      and asserting strict-superset.

## Project Constraints (from CLAUDE.md)

- **Health/Observability contract:** "do not break payload shape casually" — this phase's core
  constraint; existing `measurement` fields must be byte-preserved (HEALTH-01 + 238 mandate).
- **Portable Controller Architecture (NON-NEGOTIABLE):** deployment-specific behavior belongs
  in YAML config, not Python branching. The attribution triple is link-agnostic; the bridge's
  `null` values are honest (no per-deployment Python branch), satisfying this.
- **Change Policy:** "stability > safety > clarity > elegance"; never refactor core
  logic/algorithms/thresholds/timing without approval; prefer targeted fixes. 244 is additive
  only — no control-path body changes (enforced by the SAFE-17 forbidden-token gate).
- **Network/wanctl:** "Production-critical. Conservative: suggest, don't implement. Minimal
  changes only when approved." 244 is purely additive surfacing; no behavior change.
- **Dev commands:** use `.venv/bin/pytest|ruff|mypy` directly; run `project-finalizer` before
  any commit (mandatory).

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | The Phase 243 *close* commit is the correct 244 anchor; `380fadbd` in the 243 test is a provisional scaffolding baseline the planner must resolve to the true close SHA | SAFE-17 Mechanics | Wrong anchor → verifier compares against the wrong baseline; the `TODO(phase-close)` confirms it is provisional — planner MUST verify via `git log` at plan time |
| A2 | `steering/health.py` is NOT in the 242 `V153_ALLOWLIST_RE` (regex lists `steering/daemon.py` only) | SAFE-17 Mechanics | If surfacing on steering/health.py, the regex needs `steering/health\.py` added; verify the exact regex at plan time |

> Both assumptions are anchor/allowlist bookkeeping the planner resolves with one `git log` and
> one regex read at plan time. No external/compliance/security assumptions exist in this phase.

## Open Questions

1. **Autorate per-sample `backend` fidelity vs simplicity (R3a / Pitfall 3)**
   - What we know: `_record_live_rtt_snapshot` does not store `RttSample.backend`/`source_ip`.
   - What's unclear: whether to proxy via `backend_active` (simpler, lower fidelity after
     fallback) or add additive `_last_sample_*` fields (faithful, larger `wan_controller.py`
     touch).
   - Recommendation: proxy on the autorate path (non-A/B surface); prioritize true per-sample
     fidelity on the **steering** path (the Selection-A A/B surface). Planner's D-03 call.

## Sources

### Primary (HIGH confidence — direct source reads at HEAD 8d3969ab)
- `src/wanctl/rtt_backend.py:36-54` — `RttSample.backend`/`source_ip` fields (R5)
- `src/wanctl/rtt_measurement.py:350-358`, `src/wanctl/fping_measurement.py:122-147` — backend populates triple
- `src/wanctl/health_check.py:454-532` — `_build_measurement_section` additive pattern
- `src/wanctl/wan_controller.py:1166,1199-1200,1264,1342,1350,4481-4509,4539-4556` — measure_rtt, snapshot store, get_health_data
- `src/wanctl/steering/health.py:196,359-377` — `_build_rtt_source_section`
- `src/wanctl/steering/daemon.py:1126-1166,1425-1435,2545-2571,2612,2709-2738` — daemon wiring discards handle/source_ip
- `src/wanctl/rtt_backend_factory.py:90-228` — `RttBackendHandle` (no `source_ip` field), status fields
- `src/wanctl/autorate_continuous.py:118-175` — autorate construction, `config.ping_source_ip`
- `deploy/scripts/cake-autorate-{spectrum,att}-state-bridge:16-31,234-296` — bridge env (no source_ip), health_payload (byte-identical)
- `scripts/phase242-safe17-boundary-check.sh` (allowlist+protected-body template), `scripts/phase243-safe17-boundary-check.sh` (measurement-only)
- `tests/test_phase243_safe17_verifier.py` (mirror-test template; provisional anchor `380fadbd`), `tests/test_health_check.py:391-532,1937-2024`, `tests/test_spectrum_cake_autorate_artifacts.py:164-210`
- `.planning/phases/244-.../244-CONTEXT.md`, `.planning/REQUIREMENTS.md:51,69`, `.planning/ROADMAP.md` §244, `.planning/phases/242-.../242-CONTEXT.md`
- `CLAUDE.md` (project + global), project `MEMORY.md` (SAFE-17 pinning caveat, both-WAN cake-autorate prod state)

### Secondary / Tertiary
- None — no external sources; phase is entirely first-party.

## Metadata

**Confidence breakdown:**
- Producer attach points & emitted keys: HIGH — verified line-by-line against live code.
- SAFE-17 mechanics: HIGH for the mechanism; the exact 243-close anchor SHA is the one
  bookkeeping item the planner resolves (A1).
- Byte-preservation approach: HIGH — matches existing test patterns.
- Bridge source_ip (null): HIGH — env inventory verified, no source-IP wiring exists.

**Research date:** 2026-06-18
**Valid until:** 2026-07-18 (stable internal code; re-verify line numbers if phases 245+ land first)
