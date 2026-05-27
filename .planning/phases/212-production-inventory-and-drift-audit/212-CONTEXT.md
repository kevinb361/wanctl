# Phase 212: Production Inventory And Drift Audit - Context

**Gathered:** 2026-05-27
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 212 produces a read-only production inventory and drift audit for Spectrum, ATT, and steering before any internet-quality tuning begins. The output must state what is actually running, which health endpoints and services are authoritative, whether repo config, deployed YAML, live `/health`, and systemd state agree, and which facts constrain later baseline/tuning phases.

This phase is evidence-gathering first. It may classify drift and recommend follow-up alignment, but it must not silently tune controller behavior, change YAML, restart production services, or deploy code as part of the audit.

</domain>

<decisions>
## Implementation Decisions

### Drift Handling
- **D-01:** Default behavior is classify-only. Phase 212 labels each mismatch as expected staging, accidental drift, unknown drift, or not drift. It does not mutate production by default.
- **D-02:** If a mismatch blocks correct interpretation of later quality work, the plan may include an explicit operator approval checkpoint for alignment. Without approval, record the drift and carry it forward instead of fixing it opportunistically.
- **D-03:** Steering restart/degraded-state persistence is folded into Phase 212 only as inventory/state evidence. Capture current steering service status, `/health`, and `/var/lib/wanctl/steering_state.json` shape if available. Do not stage a controlled degraded restart just to reproduce the old todo.

### Authoritative Inventory Surfaces
- **D-04:** Primary live evidence surfaces are systemd status/uptime, bound `/health` endpoints, deployed `/etc/wanctl/*.yaml`, repo `configs/*.yaml`, deployed package/version surfaces, and steering health/state.
- **D-05:** `/health` is authoritative for daemon-reported version, state, rates, measurement quality, and active status, but not sufficient proof of good user experience. Phase 212 must explicitly preserve that distinction for Phase 213.
- **D-06:** Systemd is authoritative for whether a daemon is currently active, restarted, watchdog-managed, and using the expected unit/config path. If systemd and `/health` disagree, report the disagreement rather than picking one silently.
- **D-07:** RouterOS readback is optional and read-only. Use it only for critical operating points where deployed YAML and `/health` are insufficient to prove the live queue/rule state.

### Secret Redaction And Artifact Safety
- **D-08:** Audit artifacts must not include secrets, tokens, private keys, raw router passwords, or full secret-bearing config dumps. Redact values for keys matching password, secret, token, credential, auth, key, or private material.
- **D-09:** Config comparisons should preserve proof-relevant non-secret values: WAN name, transport type, router host identity, queue names, floors/ceilings/setpoints, DOCSIS mode, health/metrics ports, steering thresholds, state paths, and cooldowns.
- **D-10:** If an unredacted command is needed for local operator use, place the command in the plan/runbook, not its sensitive output in the committed artifact.

### Report Shape
- **D-11:** Final output should optimize for operator decisions first: one compact table per surface with expected value, live value, verdict, evidence path, and impact on later phases.
- **D-12:** Raw evidence should be saved as redacted snapshots or summarized command output under the Phase 212 directory so later planners can cite stable artifacts without re-running production probes.
- **D-13:** The closeout summary must list constraints for Phase 213/214/215, especially any version/config drift, health endpoint binding quirks, steering uncertainty, and Spectrum upload operating points that later tests must account for.

### Claude's Discretion
- User delegated the Phase 212 gray-area choices with "you decide." The planner has discretion over exact command shape, evidence filenames, and whether to split the audit into one plan or multiple plans, provided the read-only/default-no-mutation boundary holds.

### Folded Todos
- `2026-04-17-investigate-steering-degraded-on-clean-restart.md` — fold as a read-only steering state inventory concern. The old problem was a clean restart loading `SPECTRUM_DEGRADED` from persisted steering state before auto-recovering. Phase 212 should capture current steering state/version/service facts and decide whether the todo remains low-priority, is explained by current state, or needs a later controlled-restart investigation.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Milestone And Phase Scope
- `.planning/ROADMAP.md` §"Phase 212: Production Inventory And Drift Audit" — phase goal and success criteria.
- `.planning/REQUIREMENTS.md` §"Production Inventory And Drift (DRIFT)" — DRIFT-01 through DRIFT-03 requirements.
- `.planning/PROJECT.md` §"Current Milestone: v1.46 Internet Quality Recovery" — milestone goal and operating context.
- `.planning/STATE.md` §"Current Position" and §"v1.46 safety posture" — current phase, safety boundaries, and deferred VERIFY context.

### Folded Todo
- `.planning/todos/pending/2026-04-17-investigate-steering-degraded-on-clean-restart.md` — steering persisted-state observation to include as read-only drift/state evidence.

### Prior Phase Context
- `.planning/phases/211-production-verification-milestone-closure/211-CONTEXT.md` — production endpoint/deploy lessons from v1.45, including bound health endpoint behavior and manual restart observation.
- `.planning/phases/211-production-verification-milestone-closure/211-03-SUMMARY.md` — v1.45 shipped-with-deferral closeout summary and live deployment context.
- `.planning/phases/211-production-verification-milestone-closure/211-VERIFICATION.md` — SAFE-10 and Branch B verification details.

### Codebase Maps
- `.planning/codebase/STACK.md` — runtime, config files, systemd deployment model, env vars, entry points.
- `.planning/codebase/ARCHITECTURE.md` — autorate/steering daemon architecture, state files, observability surfaces, profiling labels.
- `.planning/codebase/INTEGRATIONS.md` — RouterOS integration, SQLite metrics, JSON state files, health endpoints, systemd watchdog, secrets locations.

### Runtime Surfaces To Inspect Read-Only
- `deploy/systemd/wanctl@.service` — autorate service contract and config/environment handling.
- `deploy/systemd/steering.service` — steering service contract and config/environment handling.
- `configs/spectrum.yaml` — repo Spectrum baseline for comparison to deployed `/etc/wanctl/spectrum.yaml`.
- `configs/att.yaml` — repo ATT baseline for comparison to deployed `/etc/wanctl/att.yaml`.
- `configs/steering.yaml` — repo steering baseline for comparison to deployed `/etc/wanctl/steering.yaml`, if present.
- `src/wanctl/health_check.py` — autorate `/health` payload shape.
- `src/wanctl/steering/health.py` — steering `/health` payload shape.
- `src/wanctl/config_base.py` — YAML/env substitution and config validation behavior.
- `src/wanctl/steering/daemon.py` and `src/wanctl/state_manager.py` — steering state persistence surfaces relevant to the folded todo.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `/health` endpoints expose daemon status, uptime, version, cycle stats, WAN state/rates, and steering state. Phase 212 should capture these as primary JSON evidence.
- `wanctl-history` and SQLite metrics exist for historical state checks, but Phase 212 should use them sparingly; detailed latency/throughput analysis belongs to Phase 213/214.
- `PerfTimer`/`OperationProfiler` labels exist, but one-hour profiling belongs to Phase 217 unless Phase 212 discovers immediate cycle-budget risk.
- `scripts/deploy.sh` is relevant only as context for deployed layout and prior manual restart observations. Phase 212 should not deploy.

### Established Patterns
- Production runs as service-based systemd units, not timers. Active units are `wanctl@<wan>.service` and `steering.service`.
- Runtime layout is `/opt/wanctl` for code, `/etc/wanctl` for config/secrets, `/var/lib/wanctl` for state/SQLite, `/var/log/wanctl` for logs, and `/run/wanctl` for runtime files.
- Controller behavior is link-agnostic; deployment-specific differences must remain YAML/config facts, not Python branches.
- Production evidence phases use explicit artifacts and conservative operator gates before mutation.

### Integration Points
- Spectrum autorate health was previously verified on bound endpoint `http://10.10.110.223:9101/health`, not loopback.
- ATT autorate health was previously verified on bound endpoint `http://10.10.110.227:9101/health`, not loopback.
- Steering health endpoint may use a different port/binding than old maps state; Phase 212 must discover the live endpoint rather than assume.
- Secrets flow through `/etc/wanctl/secrets` and `${ROUTER_PASSWORD}` references; artifacts must redact this path's contents and any substituted values.

</code_context>

<specifics>
## Specific Ideas

- Treat Phase 212 as the "measure before tuning" guardrail for the whole v1.46 milestone.
- The audit should be useful even if it finds no drift: a clean inventory becomes the baseline for Phase 213 experience testing.
- If steering is healthy at observation time, do not close the folded steering restart todo solely from one healthy snapshot; classify it as current-state-good but reproduction not attempted unless evidence is stronger.

</specifics>

<deferred>
## Deferred Ideas

### Reviewed Todos (not folded)
- `2026-04-08-investigate-tcp-12down-latency-spikes-under-multi-flow-downl.md` — belongs to Phase 214 measurement-collapse investigation after baseline context exists.
- `2026-04-15-profile-post-hotpath-baseline-on-production-wan.md` — belongs to Phase 217 production cycle-budget baseline unless Phase 212 discovers immediate service health risk.
- `2026-04-17-monitor-flapping-peak-count-on-next-docsis-event.md` — belongs to Phase 218 watch-list closure when a natural qualifying event exists.
- `2026-04-24-resolve-att-cake-primary-canary-after-phase-196.md` — depends on recovery/refractory and ATT canary context; do not pull into the inventory audit.

</deferred>

---

*Phase: 212-production-inventory-and-drift-audit*
*Context gathered: 2026-05-27*
