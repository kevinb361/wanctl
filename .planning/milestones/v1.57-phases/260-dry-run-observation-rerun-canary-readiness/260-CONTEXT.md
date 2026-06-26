# Phase 260: Dry-Run Observation Rerun + Canary Readiness - Context

**Gathered:** 2026-06-25
**Status:** Ready for planning

<domain>
## Phase Boundary

Re-execute the bounded read-only/dry-run observation that v1.56 (Phase 257) could not complete — now that Phases 258–259 made supported live RouterOS inspection work from `cake-shaper`. From the production steering host: run a bounded observation window, sample the live `ownership_inspection` evidence (259), compute and render wanctl's intended route decisions with no mutation, compare them against live Netwatch/default-route state, record divergences as evidence, and emit an explicit `ready-for-approval` | `not-ready` canary-readiness packet.

This phase supersedes the Phase 257 `not-ready` packet. Its two forcing blockers — `route_management.guard.status=error` and "live RouterOS inventory unavailable" (the `/etc/wanctl/ssh/router.key` access gap) — were fixed by 258 (REST read-only path proven) and 259 (`ownership_inspection` health section live, `match=true`, `inspector_status=ok`).

**Forbidden (SAFE-21):** no live RouterOS route enable/disable/set/add/remove, no Netwatch disablement/enablement/script mutation, no CAKE/qdisc/rate/threshold change, no production route-owner flip, no active route-management mode or active canary. Netwatch remains the active/interim owner through closeout. `ready-for-approval` only means a *future, separate* milestone may ask for approval — it is not approval and must not chain into mutation.

</domain>

<decisions>
## Implementation Decisions

### Authoritative readiness signal (OBSERVE-03)

- **D-01 — `ownership_inspection` is the authoritative ownership signal; old guard is supplementary.** The `ready-for-approval` ownership criterion is gated by `ownership_inspection.inspector_status == "ok"` AND `ownership_inspection.match == true` (the live ownership truth introduced in Phase 259, which 259-CONTEXT explicitly designated as "Phase 260's primary discrepancy signal"). The legacy `route_management.guard.status` is no longer the authoritative ownership signal — it must merely not be circuit-open / hard-fail. This decouples the verdict from a legacy signal that may or may not have been cleared by 258's netwatch-print fix.

- **D-02 — All samples must be clean; any blip forces `not-ready`.** The 259 inspector refreshes every ~60s, so the ~10-min window yields ~10 samples. **Every** sampled refresh across the window must be `status=ok` AND `match=true`. A single mid-window `inspector_status=error` or `match=false` sample — even if it recovers — forces `not-ready`, with that sample recorded as the concrete blocker. Rationale: a transient inspection failure immediately before a route-owner canary is exactly what must surface, not be smoothed over. Consistent with the carried-forward "prefer not-ready when mixed/incomplete."

### Observation mechanism (OBSERVE-01)

- **D-03 — Build a reusable harness script, not a one-shot manual run.** Create `scripts/phase260-observation.py` following the `scripts/phase259-ownership-proof.py` pattern: bootstrap `/opt` import path, validate the read-only command file against the allowlist before any live command, sample over a bounded window, scan for mutation tokens, render the readiness packet + raw JSON + transcript, and emit a `ready-for-approval` | `not-ready` verdict line. Durable and re-runnable before any future canary; avoids 257's flaky background-process supervision (257 fell back to manual split-foreground sleep+sample). Testable via a `tests/test_phase260_observation.py` slice (mutation rejection before any sample, fail-closed verdict on inspector error).

- **D-04 — Sample the health endpoint AND take an independent RouterOS cross-check; assert agreement.** The harness samples `:9102/health` `ownership_inspection` across the window AND takes at least one allowlist-validated direct read-only RouterOS inventory snapshot (netwatch + default routes via the 258-proven REST path), then asserts the two agree. Defense-in-depth on the pre-canary gate: catches a stale or buggy cached inspector before a route-owner canary trusts it. A disagreement between the daemon's `ownership_inspection` and the independent RouterOS read is a recorded divergence (see D-07).

### Intent-comparison depth (OBSERVE-02)

- **D-05 — Render standing per-route intent vs live; do NOT force a failover.** In healthy steady state `last_intended_action` is `null` and `match=true`, so a naive observation is vacuously clean. Instead, render wanctl's **standing** intent — `route_management.active_owner` plus the reconciliation route targets / distances from `route_manager` — as an explicit per-route table, and compare it against live `ownership_inspection.routes.default_routes[]` (gateway / disabled / distance / comment per route). This makes OBSERVE-02 meaningful without mutating anything. Forcing a non-null intended action by driving a failover scenario on the production steering host is **rejected** — it borders SAFE-21 and adds risk for little gain.

### Window + divergence taxonomy

- **D-06 — Bounded ~10-min window (carry forward 257).** Matches Phase 257's ~636s window (~10 samples at 60s refresh). Enough samples to catch an inspector blip; no added friction; keeps the verdict shape comparable to the 257 packet it supersedes.

- **D-07 — Divergence is the union of three classes, recorded as evidence (not mutations):**
  1. Any inspector sample with `inspector_status != "ok"` or `match == false` (per D-02).
  2. Any per-route intended-vs-live mismatch (target / distance / owner) from the D-05 standing-intent table.
  3. Any disagreement between the daemon's `ownership_inspection` and the independent direct RouterOS read-only cross-check (per D-04).
  Each divergence is recorded in the packet as a concrete blocker with its observed values; none triggers automatic remediation or mutation.

### Carried forward from Phase 257 (locked — do not re-derive)

- **D-08 — Deterministic command-file + read-only allowlist validation before any live command.** Every live command comes from a prewritten command file validated against the narrow read-only allowlist; validator prints its pass/negative-self-test tokens before any live execution. (`readonly_validator.py` is the enforcement layer.)
- **D-09 — 257 readiness-packet format is the target shape.** Criteria matrix (criterion / observed / status / readiness impact) + SAFE-21 no-mutation proof block + blockers/remediation + rollback evidence pointers + next-milestone recommendation. Update the matrix rows to reflect the new authoritative signal (D-01) and the now-passing inspection rows.
- **D-10 — Mixed/incomplete evidence → `not-ready` with concrete blockers.** A negative/no-go verdict is a successful safe outcome. This phase produces the packet only; it must not request or imply active canary approval.

### Claude's Discretion

The planner may choose: exact harness CLI/flags, evidence filenames and timestamp convention, sampling interval within the ~10-min window, the test slice composition, and the exact per-route comparison rendering — but must preserve all safety boundaries (SAFE-21), the all-samples-clean rule (D-02), the authoritative-signal choice (D-01), and the independent cross-check (D-04).

### Folded Todos

- `2026-06-18-route-ownership-netwatch-to-wanctl-failover.md` — fold ONLY the readiness/observation piece: produce the canary-readiness packet proving whether wanctl route-management is ready for a future canary while Netwatch remains active. The actual ownership transfer / Netwatch retirement / route-owner flip is explicitly NOT folded — it belongs to a separate future milestone gated behind an explicit operator approval after this phase emits `ready-for-approval`.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements and roadmap
- `.planning/REQUIREMENTS.md` — v1.57 requirements; OBSERVE-01, OBSERVE-02, OBSERVE-03, SAFE-21 are in scope for this phase.
- `.planning/ROADMAP.md` — Phase 260 goal, success criteria, dependency on Phase 259, and the milestone-wide SAFE-21 boundary statement.

### Phase 257 (the observation this phase supersedes)
- `.planning/milestones/v1.56-phases/257-dry-run-observation-canary-readiness-decision/257-CONTEXT.md` — original observation decisions (D-257-01/02/03): window, evidence inputs, verdict criteria, guard-gap handling.
- `.planning/milestones/v1.56-phases/257-dry-run-observation-canary-readiness-decision/evidence/phase257-readiness-packet-20260620T122132Z.md` — the `not-ready` packet to supersede; its criteria matrix is the format template (D-09) and its two failing rows are what 258/259 fixed.
- `.planning/milestones/v1.56-phases/257-dry-run-observation-canary-readiness-decision/257-01-SUMMARY.md` — execution record, including the background-supervision flakiness that motivates the D-03 harness.
- `.planning/milestones/v1.56-phases/257-dry-run-observation-canary-readiness-decision/evidence/phase257-readonly-commands-20260620T120700Z.txt` and `...-readonly-validator-...py` — the command-file + validator pattern to carry forward (D-08).

### Phase 258–259 (the proven foundation this phase consumes)
- `.planning/phases/258-read-only-routeros-access-repair/258-CONTEXT.md` and `258-VERIFICATION.md` — REST read-only path decisions and live proof (`ACCESS02_PROOF_PASS route=17 netwatch=3 script=20`).
- `.planning/phases/259-read-only-netwatch-route-ownership-inspection/259-CONTEXT.md` — the `ownership_inspection` health shape (D1–D7), the pinned JSON preview, and the explicit statement that `match` is Phase 260's primary discrepancy signal.
- `.planning/phases/259-read-only-netwatch-route-ownership-inspection/259-02-SUMMARY.md` — live wiring result and proof: `INSPECT_PROOF_PASS observed_owner=netwatch configured_owner=netwatch match=True ... total_routes=17 default_routes=4`; `ownership_inspection` confirmed present in `:9102/health`.
- `scripts/phase259-ownership-proof.py` — the harness pattern to follow for D-03 (`/opt` bootstrap, validate-before-run_cmd, verdict line).

### Core implementation files (read-only consumers for this phase)
- `src/wanctl/steering/health.py` — `_build_ownership_inspection_section()` and `_build_route_management_section()`; defines the exact health payload the harness samples.
- `src/wanctl/steering/route_ownership_inspector.py` — the cached inspector producing `ownership_inspection` (observed_owner/match/inspector_status/netwatch/routes).
- `src/wanctl/steering/route_manager.py` — `status_snapshot()` / `_active_owner()` and reconciliation route targets; source of wanctl's **standing intent** for the D-05 per-route comparison.
- `src/wanctl/routeros_rest.py` — `_handle_netwatch_print()`, route-print dispatch; the 258-proven path for the D-04 independent cross-check.
- `src/wanctl/readonly_validator.py` — allowlist validator; gate for D-08.
- `src/wanctl/router_client.py` — `get_router_client()` factory used by the harness.

### Integration and architecture
- `.planning/codebase/INTEGRATIONS.md` — REST transport details (port 443, `ROUTER_PASSWORD`, `router.verify_ssl`); health endpoint topology (`:9101` autorate bridge, `:9102` steering).

### Tests to extend
- `tests/test_phase259_ownership_proof.py` — proof-harness test pattern (happy path, mutation rejection before `run_cmd`, fail-closed on inspector error); model `tests/test_phase260_observation.py` on it.
- `tests/test_health_check.py` — health-shape / no-regression coverage for `ownership_inspection` and `route_management`.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `scripts/phase259-ownership-proof.py` — closest analog for the D-03 observation harness: `/opt` import bootstrap, secret loading via service-equivalent env, validate read-only commands before any `run_cmd`, single inspector refresh, `INSPECT_PROOF_PASS`/`FAIL` verdict line. Phase 260 generalizes this to a multi-sample bounded window + packet renderer.
- `ownership_inspection` section in `:9102/health` — already exposes `observed_owner`, `configured_owner`, `match`, `inspector_status`, `inspector_error`, `last_inspected_at`, `netwatch.{entries_count,route_mutating_active_count}`, `routes.{total_route_count,default_routes[]}`. This is the live evidence source; the harness samples it rather than rebuilding inspection.
- `RouteOwnershipInspector` / `RouteOwnershipGuard.inspect()` — already proven live; the harness consumes their output via health, and via a direct call only for the independent cross-check (D-04).
- Phase 257 command-file + validator artifacts — copy the allowlist/validator pattern forward (D-08); extend the command set with the now-working netwatch/route read-only commands.

### Established Patterns
- **Deployed proof harness** — standalone script under `scripts/` that imports from `/opt/wanctl`, validates commands, emits a single machine-greppable verdict token. Pattern established by 258/259 proofs.
- **Validate-before-execute** — `readonly_validator.validate_command()` must pass (and a negative self-test must print) before any live RouterOS command runs.
- **Additive, no-regression health** — `ownership_inspection` is a sibling of `route_management`; sampling must not assume one nests in the other, and must not require any payload change.
- **Fail-closed verdict** — any inspection error → `not-ready` (mirrors `inspector_status=error` → not-ready in D-02), never an upgrade to readiness.

### Integration Points
- Harness reads `:9102/health` (steering) for `ownership_inspection` + `route_management` standing intent.
- Harness reads live RouterOS via the 258 REST path (`routeros_rest` + `router_client`) for the D-04 independent cross-check.
- Evidence + packet land under `.planning/phases/260-dry-run-observation-rerun-canary-readiness/evidence/` (mirror 257's evidence layout).

</code_context>

<specifics>
## Specific Ideas

- The packet must explicitly state it **supersedes** the Phase 257 `not-ready` packet and show the two previously-failing matrix rows now passing (with the new authoritative signal noted per D-01).
- Verdict line should be a single greppable token (e.g., `OBSERVE_VERDICT: ready-for-approval` / `not-ready`) plus the SAFE-21 proof booleans (`APPROVED_ACTIVE_CANARY: false`, `NETWATCH_REMAINS_OWNER: true`, `NO_ROUTE_OWNER_FLIP: true`) — mirror the 257 packet header.
- `last_inspected_at` staleness should be sanity-checked against the window (a sample whose timestamp doesn't advance across refreshes is itself evidence of a stuck inspector).
- Expected current live state (from 259 proof): `observed_owner=netwatch`, `match=True`, `total_routes=17`, `default_routes=4` — the harness should treat a deviation from this baseline as a divergence to record, not silently accept.

</specifics>

<deferred>
## Deferred Ideas

- **Active route-management canary** (wanctl owns a single route under controlled, reversible conditions) — gated behind explicit operator approval in a *separate future milestone*, only after this phase emits `ready-for-approval`. Out of scope (SAFE-21).
- **Netwatch retirement / route-owner flip** — out of scope until a successful canary; belongs to the post-`ready-for-approval` milestone.

### Reviewed Todos (not folded)
- `2026-06-18-route-ownership-netwatch-to-wanctl-failover.md` — only the readiness/observation slice is folded (see D-08 Folded Todos). The ownership-transfer/retirement work itself stays deferred to a future milestone.

</deferred>

---

*Phase: 260-dry-run-observation-rerun-canary-readiness*
*Context gathered: 2026-06-25*
