# Phase 126: Pre-Test Gate - Context

**Gathered:** 2026-04-02
**Status:** Ready for planning

<domain>
## Phase Boundary

Verify the test environment is correct before any tuning begins. Confirm linux-cake transport is active, CAKE qdiscs are present on all 4 bridge NICs, MikroTik router has no active CAKE queues (disable without deleting), and a wanctl rate change produces a visible bandwidth change in tc output.

</domain>

<decisions>
## Implementation Decisions

### Router CAKE cleanup
- **D-01:** Use MikroTik REST API to check /queue/tree and /queue/type for active CAKE entries
- **D-02:** Disable all CAKE-related queue tree entries and queue types on the router — do NOT delete anything. Keep entries available for re-enablement if needed.
- **D-03:** Also check mangle rules that routed traffic into CAKE queues — disable those too

### Gate verification method
- **D-04:** Write a checklist bash script that runs all gate checks and reports pass/fail. Script lives in the repo for reuse in future test sessions.
- **D-05:** For GATE-03 (rate change test): temporarily lower max rate in spectrum.yaml, SIGUSR1 reload, confirm tc shows new bandwidth, then revert config.

### Pre-test checklist scope
- **D-06:** Include 5 checks total in the gate script (3 from requirements + 2 from original todo):
  1. CAKE qdiscs active on all 4 bridge NICs (ens16, ens17, ens27, ens28)
  2. No active CAKE queues on MikroTik router
  3. Rate change produces visible tc bandwidth change
  4. Verify `transport: "linux-cake"` in spectrum.yaml
  5. Confirm wanctl health endpoint returns correct version

### Claude's Discretion
- Gate script naming and location (suggest: scripts/check-tuning-gate.sh or similar)
- Exact REST API endpoints and payloads for disabling router CAKE
- Script output format (simple pass/fail per check)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Transport and CAKE
- `docs/TRANSPORT_COMPARISON.md` — REST vs SSH vs linux-cake transport comparison
- `docs/CONFIG_SCHEMA.md` — Configuration reference including transport and cake_params sections

### Existing CLI tools
- `src/wanctl/check_cake.py` — Existing CAKE audit tool (checks MikroTik router, not VM qdiscs)
- `src/wanctl/check_config.py` — Config validation tool with CheckResult/Severity model

### Tuning context
- `.planning/todos/pending/2026-04-02-retest-all-params-linux-cake.md` — Original todo with pre-test checklist

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `wanctl-check-cake` CLI: audits CAKE on MikroTik via REST API — reuse its router connection pattern for D-01/D-02
- `CheckResult`/`Severity` data model in `check_config.py`: consistent output format across CLI tools
- `routeros_rest.py`: REST API client for MikroTik router communication

### Established Patterns
- CLI tools use SCHEMA class attributes, never instantiate Config() (avoids daemon side effects)
- SimpleNamespace wraps router config dict for RouterOSREST.from_config() compatibility
- wanctl-check-cake already knows how to query /queue/type and /queue/tree

### Integration Points
- Gate script needs SSH access to cake-shaper VM (10.10.110.223) for tc commands
- Gate script needs REST API access to MikroTik router (10.10.99.1) for CAKE checks
- Health endpoint at http://127.0.0.1:9101/health on cake-shaper VM

</code_context>

<specifics>
## Specific Ideas

- User explicitly wants "disable everything but don't delete" on the router — preservation for rollback
- Gate script should be reusable — not a one-off, stored in the repo
- SIGUSR1 + config edit is the preferred rate change trigger for GATE-03

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

### Reviewed Todos (not folded)
- "Re-test ALL tuning parameters on linux-cake transport" — parent todo for whole milestone, not Phase 126 scope
- "RRUL A/B tuning sweep for ATT WAN" — out of scope, ATT is separate todo
- "Integration test for router communication" — existing testing concern, not related to pre-test gate
- "Post-tuning audit findings" — operational findings, not gate check scope

</deferred>

---

*Phase: 126-pre-test-gate*
*Context gathered: 2026-04-02*
