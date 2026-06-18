# Phase 244: Health-Payload Attribution Metadata - Context

**Gathered:** 2026-06-18
**Status:** Ready for planning

<domain>
## Phase Boundary

Make every RTT sample **attributable to a backend and a source IP via `/health`**, so
Phase 245's icmplib-vs-fping A/B is interpretable — *before* the A/B starts. The change
is **purely additive**: the existing payload contract (`raw_rtt_ms`, `available`,
`staleness_sec`) must be byte-preserved (HEALTH-01). No live-consumption change, no
backend selection logic, no controller algorithm/timing change — those are Phase 245.

**In scope:** additively expose `backend` + `source_ip` attribution on `/health`
measurement payloads; advance/extend the SAFE-17 boundary to permit the additive diff;
prove byte-preservation of the existing contract fields.

**Out of scope:** flipping steering to consume its own pinger (Phase 245 / AB-01);
reviving the dead `RTTMeasurement` consumption path; any new backend behavior; native
autorate (NATIVE-AB-01, deferred).
</domain>

<decisions>
## Implementation Decisions

### Attribution Surfaces (operator decision)
- **D-01:** Expose the new `backend` + `source_ip` attribution on **all three `/health`
  producers**, per operator selection:
  1. `src/wanctl/steering/health.py` — the path the A/B actually measures on under
     Selection A (Phase 245 flips steering to its own pinger here). **Primary surface.**
  2. `src/wanctl/health_check.py` (autorate controller) — already carries `backend_active`
     from Phase 242; add the fuller attribution here for consistency across wanctl paths.
  3. `deploy/scripts/cake-autorate-{spectrum,att}-state-bridge` — the live production
     `/health` today (both WANs on cake-autorate).
- **D-02 (bridge honesty caveat — MANDATORY for the bridge surface):** On the state-bridge,
  `raw_rtt_ms` is sourced from **upstream bash cake-autorate's EWMA log**, NOT from the
  wanctl `RttBackend` seam (confirmed 238 D-04: the seam cannot reach this producer).
  Therefore the bridge's `backend` field MUST honestly reflect that producer (e.g.
  `"cake-autorate"` / an upstream-producer label) and MUST NOT claim `"icmplib"`/`"fping"`
  from the wanctl seam — doing so would mislabel which code produced the number. If the
  bridge cannot determine a meaningful `source_ip`, emit `null` rather than inventing one.
  **Research item:** confirm whether the bridge process has access to the per-WAN
  `ping_source_ip` (it currently knows `DL_IF`/`UL_IF` env, not necessarily the source IP).

### `backend` key semantics (Claude's discretion — user said "you decide")
- **D-03:** Add a **new per-sample `backend`** field = the backend that produced the
  *current* sample (`RttSample.backend`). Keep Phase 242's `backend_active` = the
  factory-*selected* backend. Rationale: after a loud fallback the two can legitimately
  differ (selected=fping, producing=icmplib); preserving both maximizes A/B fidelity,
  which is the whole point of the milestone. `backend_active` is byte-preserved (it is now
  a contract field per 242); `backend` is the additive newcomer.

### `source_ip` semantics (Claude's discretion — user said "you decide")
- **D-04:** `source_ip` reports the **per-WAN configured/intended source IP** the backend
  binds with (`-S` for fping; `source=` for icmplib), emitting **`null`** when none is
  configured (e.g. icmplib with no source, or pre-first-sample). Rationale: the phase goal
  is attributability **before the A/B starts**; on Selection A the steering pinger is still
  dead pre-245, so an observed-only value would be `null` exactly when we most need it.
  Configured-intended is populated immediately and matches 242 D-01a ("plumb the correct
  per-WAN source at the steering factory call now"). Place it as `measurement.source_ip`
  (flat in the measurement block, parallel to `backend`).

### SAFE-17 / byte-preservation (deferred to planner — user said "let planner decide")
- **D-05:** Planner chooses the verification mechanics. **Recommended approach** to weigh:
  a contract-snapshot test pinning the exact existing measurement keys+types and asserting
  the new keys are strictly additive, plus advancing the SAFE-17 boundary anchor past the
  Phase 242-close anchor so the `health_check.py` / `steering/health.py` diff is inside the
  allowlist. Note: this is the **first intentional controller-path health-shape change of
  v1.53** — the SAFE-17 allowlist/anchor WILL need updating, not just passing as-is.

### Claude's Discretion
- D-03 (`backend` key), D-04 (`source_ip` semantics), and D-05 (SAFE-17 mechanics) are
  Claude/planner calls. The recommendations above are the intended defaults unless research
  surfaces a contradiction.

### Reviewed Todos (not folded)
- `2026-06-04-evaluate-fping-as-wanctl-rtt-measurement-backend.md` (score 0.6) — keyword
  match on rtt/measurement/backend, but this is the *milestone-level* fping evaluation
  (largely delivered in Phases 241–243), not 244's additive-health scope. Deferred.
- The 0.4-score matches (ingestion-rate tool, steering-degraded-on-restart, DOCSIS
  flapping monitor) are weak keyword hits unrelated to health attribution. Not folded.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements & roadmap (locked scope)
- `.planning/REQUIREMENTS.md` — `HEALTH-01` (additive `measurement.backend` + `source_ip`,
  contract byte-preserved) and `SAFE-17` (additive health surface only).
- `.planning/ROADMAP.md` §"Phase 244" — goal + 3 success criteria.

### A/B target provenance (load-bearing — defines WHERE attribution matters)
- `.planning/phases/238-rtt-provenance-verification-read-only-entry-gate/238-PROVENANCE-MAP.md`
  — operator-ratified **`Selection: A`** (revive steering's own pinger as the A/B RTT
  source); D-04 proves the state-bridge producer is unreachable by the wanctl seam.
- `.planning/phases/242-backend-factory-loud-fallback/242-CONTEXT.md` — **D-01a** (plumb
  per-WAN `source_ip` at the steering factory call; `daemon.py:2554` currently lacks it) and
  **D-03** (242 added the *minimal* `backend_active`/`fell_back`/`fallback_count` signal;
  244 is the fuller attribution).

### Contract / safety spine
- `CLAUDE.md` §"Health / Observability" — "do not break payload shape casually" (the
  byte-preservation contract this phase must honor while adding fields).

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `src/wanctl/rtt_backend.py:36–68` — `RttSample` dataclass **already carries** `backend`
  (default `"icmplib"`) and `source_ip` (default `None`). The data exists end-to-end; 244
  only needs to *surface* it. (frozen, slots — additive only.)
- `src/wanctl/rtt_measurement.py:350–359` — icmplib sets `backend="icmplib"`,
  `source_ip=self.source_ip`. `src/wanctl/fping_measurement.py:122–132` — fping sets
  `backend="fping"`, `source_ip=self._source_ip` (the `-S` bind, line 147).
- `src/wanctl/rtt_backend_factory.py:90–157` — `RttBackendHandle` carries the resolved
  active backend (`.backend_active`) and the source IP; the construction point where 242
  D-01a wants the per-WAN source plumbed.

### Established Patterns
- **Additive health-block pattern (follow exactly):** `health_check.py:454–532`
  (`_build_measurement_section`) returns a dict; Phase 186/242 added keys here without
  moving existing ones. New `backend`/`source_ip` keys append to this return dict; the
  source data is threaded in via `wan_controller.py:4539–4556` (`get_health_data`'s
  `measurement` dict — currently sets `backend_active` but **not** `source_ip`).
- **Steering health:** `src/wanctl/steering/health.py:359–377` (`_build_rtt_source_section`)
  — today reads autorate `/health`; under Selection A this is where steering's own
  backend/source attribution surfaces for the A/B. **Primary surface for D-01.**
- **Bridge health:** `deploy/scripts/cake-autorate-{spectrum,att}-state-bridge`
  `health_payload()` (≈lines 234–272) — emits `{available, raw_rtt_ms, staleness_sec}` only;
  RTT from cake-autorate EWMA. Apply D-02 honesty caveat here.

### Integration Points
- Three `/health` payload builders must each gain the additive fields (D-01); the autorate
  path also needs `source_ip` threaded through `get_health_data()` (it isn't today).
- SAFE-17 verifier: `scripts/phase243-safe17-boundary-check.sh` (+ test
  `tests/test_phase243_safe17_verifier.py`) enforces "no controller-path drift since the
  Phase 242-close anchor." 244 must advance/extend this to allow the additive health diff.

</code_context>

<specifics>
## Specific Ideas

- Field placement: `measurement.backend` and `measurement.source_ip` — flat keys inside the
  existing `measurement` block, parallel to `backend_active` (not a new nested object), so
  consumers parse them the same way they already parse `backend_active`.
- Keep `backend_active` AND add `backend` (D-03) — they are different facts, not duplicates.

</specifics>

<deferred>
## Deferred Ideas

- Flipping steering to consume its own pinger / live A/B execution → **Phase 245** (AB-01).
- Native autorate producer (Interpretation B's wanctl-owned variant) → **NATIVE-AB-01,
  deferred out of v1.53** per 238 D-04.
- Whether the state-bridge should learn the per-WAN `ping_source_ip` (env wiring) — flagged
  as a research item under D-02; if it requires new bridge config, planner decides whether
  that fits 244's additive scope or defers.

</deferred>

---

*Phase: 244-health-payload-attribution-metadata*
*Context gathered: 2026-06-18*
