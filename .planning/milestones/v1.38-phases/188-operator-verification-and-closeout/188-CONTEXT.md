# Phase 188: Operator Verification And Closeout - Context

**Gathered:** 2026-04-15
**Status:** Ready for planning
**Owns requirements:** MEAS-04, OPER-01, VALN-01

<domain>
## Phase Boundary

Prove that the v1.38 measurement-resilience changes close the real
`tcp_12down` stale-healthy gap and lock the operator workflow for
reproducing, inspecting, and verifying that degraded measurement is visible
without reopening controller thresholds, fallback semantics, or steering
policy.

Scope in:
- A bounded operator procedure for reproducing or inspecting measurement
  degradation during `tcp_12down`
- Operator-facing guidance in the existing workflow surfaces plus helper
  command usage where it directly supports the proof path
- Verification evidence that correlates live latency behavior with the new
  measurement-health contract and requirement closeout

Scope out:
- New controller logic or threshold changes
- Steering-policy redesign or new steering mitigation branches
- Generic observability refactors outside the measurement-collapse workflow
- Open-ended performance investigations not needed to prove the Phase 188
  closeout path

</domain>

<decisions>
## Implementation Decisions

### Evidence Strategy

- **D-01:** Phase 188 uses **live preferred, replayable fallback** evidence.
  Planning should aim for one bounded live-host confirmation pass against the
  real `tcp_12down` failure mode, but it may fall back to replayable evidence
  when rerunning live stress is not production-safe or not required to close
  the proof gap.
- **D-02:** Replayable evidence is acceptable only when it preserves the same
  operator-facing correlation the phase cares about: latency under load,
  `/health` measurement state (`healthy | reduced | collapsed`),
  `successful_count`, `stale`, and the absence of unrelated fallback or
  steering behavior changes.
- **D-03:** Live proof should be treated as a bounded verification pass, not
  an open-ended tuning session. The phase verifies the milestone; it does not
  reopen diagnosis work unless the verification procedure itself exposes a new
  blocker.

### Operator Workflow Surface

- **D-04:** The operator workflow remains anchored in the existing production
  docs:
  - `docs/DEPLOYMENT.md`
  - `docs/RUNBOOK.md`
  - `docs/GETTING-STARTED.md`
  These stay authoritative for the bounded reproduction and inspection path.
- **D-05:** Helper guidance may be tightened where it directly supports the
  proof path, specifically around:
  - `scripts/soak-monitor.sh`
  - `scripts/wanctl-operator-summary`
  The goal is to show operators how to gather the new measurement-health
  evidence, not to invent a new helper workflow.
- **D-06:** If a dedicated phase closeout artifact is produced, it is an
  evidence record for this phase, not the long-term operator source of truth.
  Docs stay primary; artifacts document the completed verification.

### Closeout Success Criteria

- **D-07:** Phase 188 closeout must prove four things together:
  - the operator-facing health path makes degraded measurement visible and
    correlatable with live latency behavior
  - the real `tcp_12down` failure mode no longer looks like healthy current
    measurement when reflector success collapses
  - existing bounded safety behavior from Phase 187 remains intact
  - milestone requirements and verification artifacts close traceably
- **D-08:** Verification must explicitly distinguish measurement degradation
  from unrelated failure modes. Steal CPU, steering overruns, or other runtime
  side signals may be noted as context, but they do not become acceptance
  criteria unless the proof path requires them.
- **D-09:** Requirement closeout should map directly to:
  - `MEAS-04` via operator-visible correlation in `/health`
  - `OPER-01` via a documented bounded reproduction/inspection procedure
  - `VALN-01` via repo-side regression evidence plus phase verification

### Reproduction Scope And Safety

- **D-10:** The reproduction path must be tightly bounded: exact command path,
  evidence checkpoints, and a limited observation window. Planning should
  prefer a short, explicit verification run over long soak-style load tests.
- **D-11:** The preferred operator proof path should use the existing
  production-facing commands and surfaces already present in the repo:
  `./scripts/soak-monitor.sh`, `wanctl-operator-summary`, and direct
  `/health` inspection. Additional ad hoc commands are acceptable only when
  they are necessary to make the measurement-collapse proof explicit.
- **D-12:** If live reproduction is skipped or aborted for safety, the phase
  should still preserve a replayable evidence path that shows operators what
  to inspect and what output constitutes pass/fail for measurement honesty.

### Folded Todos

- **Investigate tcp_12down latency spikes under multi-flow download**
  (`2026-04-08-investigate-tcp-12down-latency-spikes-under-multi-flow-downl.md`)
  is folded into this phase as the core production problem the verification
  path must prove and document. The phase should consume the investigation as
  evidence input, not reopen it as a separate research stream.

### the agent's Discretion

- Exact split between doc updates, evidence artifact shape, and verification
  write-up structure, as long as docs remain authoritative and the proof path
  is explicit.
- Whether the live verification is run against production, canary, or a
  comparably trusted bounded environment, as long as the chosen target is
  justified in the plan.
- Whether replayable evidence is captured as a report, checklist, or command
  transcript bundle, as long as operators can follow it without guesswork.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Milestone Scope And Requirements

- `.planning/ROADMAP.md` — Phase 188 goal, two-plan shape, and milestone
  boundary
- `.planning/PROJECT.md` — v1.38 milestone intent and production-stability
  constraints
- `.planning/REQUIREMENTS.md` — `MEAS-04`, `OPER-01`, and `VALN-01`
- `.planning/STATE.md` — current milestone position and recent Phase 187
  completion state

### Prior Phase Contract And Verification

- `.planning/phases/186-measurement-degradation-contract/186-CONTEXT.md` —
  locked measurement-health contract and operator-surface boundaries carried
  into Phase 188
- `.planning/phases/187-rtt-cache-and-fallback-safety/187-VERIFICATION.md` —
  verified repo-side proof that zero-success cycles now report honest current
  measurement state without changing SAFE-02 behavior
- `.planning/phases/187-rtt-cache-and-fallback-safety/187-RESEARCH.md` —
  source investigation notes tying the live `tcp_12down` failure to stale
  cached RTT masking and health honesty

### Operator Workflow Surfaces

- `docs/DEPLOYMENT.md` — active deployment and operator command path, already
  includes `soak-monitor` and `wanctl-operator-summary`
- `docs/RUNBOOK.md` — operator troubleshooting flow that should carry the
  bounded reproduction and inspection guidance
- `docs/GETTING-STARTED.md` — starter operator guidance that must stay aligned
  with the supported verification workflow
- `scripts/soak-monitor.sh` — existing bounded health/status collection helper
- `scripts/wanctl-operator-summary` — existing operator summary entrypoint

### Existing Evidence And Prior Operator Proof Patterns

- `.planning/phases/181-production-footprint-reduction-and-reader-parity/181-live-reader-parity-report.md`
  — prior example of phase-specific live evidence captured as a closeout
  report while leaving docs as the lasting operator surface

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets

- `scripts/soak-monitor.sh`: existing bounded health/status collector for both
  WANs; natural place to reference measurement-health inspection steps
- `scripts/wanctl-operator-summary`: existing operator-oriented summary entry
  point; useful for closeout guidance if its current output already exposes the
  needed measurement surfaces
- `tests/test_health_check.py`: existing contract coverage for
  `measurement.state`, `successful_count`, and `stale`
- `tests/test_wan_controller.py` and `tests/test_autorate_error_recovery.py`:
  existing non-regression witnesses for bounded Phase 187 behavior

### Established Patterns

- Prior operator-alignment phases update the existing docs and helper command
  flow rather than creating a brand-new operator surface.
- Prior closeout phases use a dedicated evidence artifact to record the final
  verification pass without making that artifact the primary documentation
  source.
- v1.38 work is explicitly conservative: measurement honesty and verification
  are in scope; threshold retuning and steering redesign are not.

### Integration Points

- `docs/DEPLOYMENT.md`, `docs/RUNBOOK.md`, and `docs/GETTING-STARTED.md` are
  the main integration points for the operator workflow
- `.planning/phases/188-operator-verification-and-closeout/188-VERIFICATION.md`
  or a sibling evidence artifact is the main integration point for final
  phase closeout
- Existing test files and Phase 187 verification are the repo-side proof base
  that the final verification should cross-reference rather than duplicate

</code_context>

<specifics>
## Specific Ideas

- Prefer a bounded verification recipe that tells operators exactly what to
  look for in `/health` during `tcp_12down`: `measurement.state`,
  `successful_count`, `stale`, and latency correlation.
- Treat the live reproduction as confirmation that the stale-healthy gap is
  closed, not as an excuse to reopen threshold tuning or general performance
  profiling.
- If helper guidance is updated, keep it focused on collecting and inspecting
  measurement evidence, not on adding new automation for unrelated runtime
  issues.

</specifics>

<deferred>
## Deferred Ideas

### Reviewed Todos (not folded)

- `Monitor Proxmox steal CPU on cake-shaper VM`
  (`2026-04-10-monitor-proxmox-steal-cpu.md`) — reviewed because VM-steal was
  part of the original investigation context, but deferred because Phase 188
  is about proving measurement honesty, not expanding host-performance
  monitoring.
- `Investigate steering cycle overruns and blocking I/O`
  (`2026-04-12-investigate-steering-cycle-overruns-and-blocking-i-o.md`) —
  deferred because Phase 188 should only note steering as a non-regression
  surface, not reopen steering internals.
- `Profile post-hotpath baseline on production WAN`
  (`2026-04-15-profile-post-hotpath-baseline-on-production-wan.md`) —
  deferred because this is broader performance instrumentation work, not a
  requirement for the operator verification closeout.

None beyond the reviewed todos above.

</deferred>

---

*Phase: 188-operator-verification-and-closeout*
*Context gathered: 2026-04-15 via /gsd-discuss-phase*
