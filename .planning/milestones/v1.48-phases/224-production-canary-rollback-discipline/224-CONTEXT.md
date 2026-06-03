# Phase 224: Production Canary + Rollback Discipline - Context

**Gathered:** 2026-06-02
**Status:** Ready for planning
**Source:** Operator invocation (auto mode) + Phase 215 Snapshot A precedent + Phase 223 closure artifacts

<domain>
## Phase Boundary

Final phase of milestone v1.48 Steering Runtime Drift Closure. This phase ships the aligned
steering daemon (work from Phase 222 audit + Phase 223 staging proof) to production behind a
Snapshot-A-pattern rollback anchor, proves contract invariants live via `/health`, and gives
the operator a bounded-time rollback path if any invariant fires fail-closed during canary
observation.

**In scope:**
- Pre-deploy snapshot of current production steering daemon state (binary + config + state +
  `/health` baseline) so revert is mechanical and auditable, mirroring v1.46 Phase 215.
- Production deploy of the aligned steering daemon (`src/wanctl/steering/`) to the production
  WAN host(s), restart of `wanctl-steering.service`, and validation against the deployed unit.
- Post-deploy health-endpoint proof confirming: version alignment (deployed `__version__` matches
  the v1.48 release line), contract invariants live (binary on/off, only-new-connections rerouted,
  autorate baseline RTT authoritative), and steering decision continuity (decision-log fields
  populate as expected — no stuck/empty sections from a pre-alignment build).
- Rollback discipline: a single documented command sequence revert path with an explicit time
  budget. If any contract invariant fires fail-closed during the canary observation window,
  operator rolls back inside that budget and the canary report cites the rollback reason.
- Canary observation window: bounded duration, defined gate verdicts, fail-closed semantics.
- Published canary report citing the snapshot anchor, gate verdicts per invariant, and either
  "kept aligned" or "rolled back with reason" disposition.
- SAFE-12 boundary check at phase entry AND at v1.48 milestone close: zero controller-path
  source diff vs v1.47 close.

**Out of scope:**
- Controller-path mutation (`wan_controller.py`, `queue_controller.py`, `cake_signal.py`, backends,
  `alert_engine.py`, fusion) — SAFE-12 explicitly bars any diff here.
- Daemon-side fix for the bounded ~15-cycle / ~0.75s post-restart steering window (folded
  clean-restart symptom). The operator has accepted the symptom for Phase 224 entry via
  `.planning/decisions/phase-224-clean-restart-risk-acceptance.md`. The default disposition
  stands unless explicitly overridden per the artifact's Override Path.
- Steering algorithm changes — daemon is in scope for *deployment*, not for *behavior change*.
- Multi-WAN canary, secondary host canary, or any production scope beyond the primary steering
  host. One host, one window, one decision.
- Steering tuning, threshold changes, or canary "test" mutations — this phase ships what
  Phase 222/223 produced, nothing more.

</domain>

<decisions>
## Implementation Decisions

### Snapshot Anchor (CANARY-01)

- **D-01 (Snapshot A pattern):** Reuse the v1.46 Phase 215 pattern. Pre-deploy snapshot captures:
  current `/opt/wanctl/` steering binary (or whatever the daemon module path is on the live
  host), current `/etc/wanctl/steering.yaml`, current persisted state under
  `/var/lib/wanctl/`, and current `/health` JSON response. Snapshot is timestamped under the
  phase `evidence/` tree and named so the rollback path can reference it unambiguously.
- **D-02 (Revert mechanism):** Revert restores the captured binary + config + state to their
  pre-deploy paths, restarts `wanctl-steering.service`, and re-queries `/health` to confirm the
  reverted version matches the snapshot. The revert command sequence is documented in plan
  artifacts and rehearsed in staging before the production touch.
- **D-03 (Snapshot ownership):** Snapshot is produced by an operator-runnable script (or a
  documented command sequence) that is idempotent and explicit about what it captures and where
  it writes. It does NOT depend on cluster-state, ad-hoc copies, or operator memory.

### Deploy + Version Alignment Proof (CANARY-02)

- **D-04 (Deploy path):** Uses the project's existing deploy tooling (`scripts/deploy.sh` or
  equivalent paved path). The plan does NOT introduce a one-off deploy procedure. If the existing
  tooling needs a small adjustment for the steering daemon specifically, that adjustment is
  itself a small, reviewable plan with explicit acceptance criteria.
- **D-05 (Version alignment proof):** Post-deploy, `/health` response must show:
  - `version` matches the deployed v1.48 release line (the expected version string is captured
    pre-deploy from the build artifact and compared, not assumed).
  - `steering` / `decision` / `congestion` sections populate with non-empty, well-formed fields
    consistent with Phase 222 alignment work.
  - `status` is `healthy` (not `starting` and not `degraded`) within a documented
    post-restart settling window.
- **D-06 (Contract invariant probes):** Phase 223 already proved these invariants in staging via
  the offline replay harness. In production, the proof is:
  - **Binary on/off:** steering rule presence on the router (rule exists when steering is
    enabled, absent when disabled) matches daemon `steering.enabled` field. No partial / fractional
    state. Observable via router REST/SSH read-only query plus `/health` cross-check.
  - **Only-new-connections rerouted:** rule scope check — the deployed steering rule's match
    criteria are restricted to new connections (the spec-frozen rule shape). Read-only router
    query verifies the rule selector matches the documented spec.
  - **Autorate baseline RTT authoritative:** `/health` `decision` section's RTT source field
    cites autorate-baseline (not router-direct or other fallback) on every cycle observed during
    the window.
- **D-07 (Decision continuity):** Decision-log fields must continue to populate at expected
  cadence. A stuck decision section (no field update across N cycles) is a fail-closed signal.

### Rollback Discipline (CANARY-03)

- **D-08 (Time budget):** Bounded rollback time budget. Concrete number is operator-chosen during
  planning but bounded by Phase 215 precedent (single-command-sequence revert + service restart +
  `/health` re-check should complete inside a small number of minutes). The budget appears in
  the canary report and the rollback path is rehearsed against it in staging.
- **D-09 (Fail-closed gates):** Any of the following triggers rollback inside the budget:
  - `/health` version drift from expected.
  - Spine invariant probe fails (binary on/off, only-new-connections, autorate authoritative).
  - Decision-section staleness beyond a documented cycle count.
  - Steering daemon enters `degraded` state for longer than a documented dwell.
  - Router-side rule shape deviates from the spec-frozen shape.
- **D-10 (Rollback report):** If rollback fires, the canary report cites which gate fired, the
  snapshot anchor restored, and post-revert `/health` proof that the production state matches
  the pre-deploy snapshot. If rollback does not fire, the report cites window duration, gate
  verdicts (all pass), and the kept-aligned disposition.

### Clean-Restart Decision Artifact Governance

- **D-11 (Decision artifact reference):** Plans MUST reference
  `.planning/decisions/phase-224-clean-restart-risk-acceptance.md` and treat its Default
  Disposition as binding for this phase. The bounded ~15-cycle / ~0.75-second post-restart
  effective-steering window is NOT a rollback trigger by itself — it is the documented,
  accepted symptom. Operator sign-off line should be obtained at the time of production touch.
- **D-12 (Distinguishing restart-window vs steady-state violation):** Canary observation
  distinguishes the accepted restart window (≤ ~15 cycles immediately after a steering daemon
  restart, with measurement-driven recovery to GOOD) from a steady-state spine violation.
  Only steady-state violations trigger rollback. Restart-window symptoms are noted in the report
  but governed by the decision artifact.

### SAFE-12 Boundary Verification

- **D-13 (Phase boundary):** SAFE-12 is checked at phase boundary using the Phase 222/223 schema
  (`safe12-boundary-check.{json,md}`). Controller-path source must be byte-identical to v1.47
  close. Allowlist: `src/wanctl/steering/` is in scope for mutation, everything else in the
  controller-path is NOT.
- **D-14 (Milestone close):** SAFE-12 is also checked at v1.48 milestone close as a final
  cross-phase verification, mirroring SAFE-07/08/09/11 precedent through v1.43–v1.47.

### Claude's Discretion

- Exact rollback time budget number (D-08). Default suggestion: ≤ 5 minutes from gate fire to
  reverted `/health` proof, but the planner should propose and the operator approves.
- Exact canary observation window duration. Default suggestion: a bounded, time-of-day-balanced
  window long enough to observe several decision cycles under representative production load.
- Exact decision-section staleness cycle count for D-09. Default suggestion: 4 cycles
  (~200ms at the 50ms production interval) for a stuck-decision signal, but the planner
  should anchor this in observable cadence from Phase 222 evidence.
- Whether snapshot capture is a new script under `scripts/` or a documented command sequence.
  Plan-author's call based on least-friction operator experience.
- How the canary report is published (`evidence/` tree + a Phase 224 REPORT.md, mirroring Phase
  215 `215-REPORT.md`).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase 215 Snapshot A precedent
- `.planning/milestones/v1.46-phases/215-spectrum-upload-reclaim-canary/215-CONTEXT.md` — Snapshot A pattern, gate/rollback shape, evidence tree layout.
- `.planning/milestones/v1.46-phases/215-spectrum-upload-reclaim-canary/215-REPORT.md` — published canary report shape.
- `.planning/milestones/v1.46-phases/215-spectrum-upload-reclaim-canary/215-VERIFICATION.md` — verification shape for a canary phase.

### Phase 223 closure artifacts
- `.planning/phases/223-staging-proof-clean-restart-reproduction/223-VERIFICATION.md` — 11/11 must-haves verified, including the clean-restart risk-acceptance link.
- `.planning/phases/223-staging-proof-clean-restart-reproduction/evidence/spine-evidence.{json,md}` — per-invariant verdicts the production proof must reproduce.
- `.planning/phases/223-staging-proof-clean-restart-reproduction/evidence/safe12-boundary-check.{json,md}` — SAFE-12 boundary-check schema.

### Risk-acceptance decision artifact
- `.planning/decisions/phase-224-clean-restart-risk-acceptance.md` — governs the bounded post-restart steering window. Default disposition stands; Override Path documented.

### Milestone artifacts
- `.planning/REQUIREMENTS.md` — CANARY-01/02/03 + SAFE-12 + coverage table.
- `.planning/ROADMAP.md` — Phase 224 section, success criteria, dependency chain.

### Steering daemon surface
- `src/wanctl/steering/daemon.py` — deploy target.
- `src/wanctl/steering/health.py` — `/health` endpoint shape (version, steering, decision, congestion).
- `deploy/systemd/steering.service` — production unit.
- `deploy/systemd/wanctl@.service` — controller-path unit (SAFE-12 NOT in scope for mutation).

### Operational scripts
- `scripts/deploy.sh` — existing deploy paved path.
- `scripts/install-systemd.sh` — systemd unit installation.
- `scripts/soak-monitor.sh` — observation tooling pattern.

### Project guidance
- `CLAUDE.md` — wanctl change policy (stability > safety > clarity > elegance), conservative on prod, REST API preferred for RouterOS.
- `docs/DEPLOYMENT.md` — current deploy guidance.
- `docs/STEERING.md` — steering daemon docs.

</canonical_refs>

<specifics>
## Specific Ideas

- **Snapshot capture is mechanical, not interpretive.** It produces files the operator can `cp`
  back into place. No "derived" snapshot, no state reconstruction. Mirror Phase 215 evidence/
  layout where `pre-deploy-snapshot/` carries the captured files plus a manifest.
- **Health-endpoint proof is the primary observable.** Phase 222/223 made this the canonical
  alignment surface. Production proof reads the same endpoint and validates the same fields.
- **Rollback is rehearsed in staging FIRST.** Before the production touch, the rollback sequence
  is executed end-to-end against a staging steering host so the time budget is grounded in real
  measurement, not estimate.
- **Canary observation is bounded and explicit.** Window has a start time, an end time, and a
  decision at end-of-window: kept aligned (publish report) or rolled back (publish report with
  rollback reason). No open-ended "we're watching it" state.
- **One host, one window.** No multi-host parallel canary. If the deploy needs to extend to
  additional hosts post-canary, that is a follow-up decision, not a Phase 224 deliverable.
- **REST transport preferred** for any router-side probe per `CLAUDE.md` RouterOS Integration
  guidance.

</specifics>

<deferred>
## Deferred Ideas

- Daemon-side fix for the bounded ~15-cycle / ~0.75-second post-restart steering window —
  governed by `.planning/decisions/phase-224-clean-restart-risk-acceptance.md`. If the operator
  invokes the Override Path, that fix becomes its own phase / pre-work item, not a Phase 224
  scope expansion.
- Multi-host canary rollout — out of scope. Possibly a v1.49 candidate.
- Storage hygiene fire-on-change (SEED-007) — explicitly out of v1.48 scope.
- Conservative UL tuning sweep (SEED-005) — dormant; SAFE allowlist burden.
- Steering algorithm tuning during canary — out of scope. This phase ships Phase 222/223 output
  unchanged.
- VERIFY-01 / VERIFY-02 watch-list — event-gated; not a Phase 224 driver.

</deferred>

---

*Phase: 224-production-canary-rollback-discipline*
*Context gathered: 2026-06-02 via operator invocation (auto mode)*
