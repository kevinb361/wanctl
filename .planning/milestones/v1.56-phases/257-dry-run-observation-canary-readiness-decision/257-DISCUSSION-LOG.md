# Phase 257: Dry-Run Observation + Canary Readiness Decision - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-20
**Phase:** 257-dry-run-observation-canary-readiness-decision
**Areas discussed:** Observation shape, Guard gap handling, Readiness verdict criteria

---

## Todo Folding

Phase todo matching found seven pending todos. Kevin did not respond before timeout; per tool instruction, best judgement was used.

| Todo | Decision | Rationale |
|------|----------|-----------|
| Route ownership: migrate Netwatch failover into wanctl or explicitly retire overlap | Folded | Direct parent thread for route-management readiness; active migration remains deferred. |
| Investigate steering SPECTRUM_DEGRADED on clean restart | Reviewed/deferred | Steering background, but not the route-management readiness decision. |
| Add tool for computing actual metrics.db write rates | Reviewed/deferred | Storage/tooling scope. |
| Monitor flapping peak_transition_count on next real DOCSIS event | Reviewed/deferred | Native-controller alert validation scope. |
| Resolve ATT cake-primary canary after Phase 196 | Reviewed/deferred | ATT CAKE validation scope. |
| Retest Spectrum diffserv4 wash after local QoS changes | Reviewed/deferred | CAKE tinning validation, forbidden by SAFE-20 for this milestone. |
| Evaluate fping as wanctl RTT measurement backend option | Reviewed/deferred | RTT backend scope. |

---

## Gray Area Selection

| Option | Description | Selected |
|--------|-------------|----------|
| Observation shape | How bounded should the dry-run observation be, and what evidence is enough? | |
| Guard gap handling | SSH Netwatch read, REST workaround, or declare not-ready? | |
| Readiness verdict criteria | What must be true for ready-for-approval vs not-ready? | |
| All three | Discuss the full Phase 257 decision surface | ✓ |

**User's choice:** All three — discuss the full Phase 257 decision surface.

---

## Observation shape

| Question | Option | Description | Selected |
|----------|--------|-------------|----------|
| How much dry-run observation before readiness packet? | Short health snapshot only | Fastest, but weak observation | |
| How much dry-run observation before readiness packet? | Bounded observation window, 10-15 minutes | Recommended; enough for intended-action/guard/reconciliation evidence | |
| How much dry-run observation before readiness packet? | Longer soak, 30-60 minutes | Stronger, but more live ops friction | |
| How much dry-run observation before readiness packet? | You decide | Claude selects default | ✓ |
| Mandatory evidence packet? | Health JSON + operator summary only | Minimal acceptance evidence | |
| Mandatory evidence packet? | Health JSON + operator summary + live RouterOS route/Netwatch read-only inventory | Recommended core comparison | |
| Mandatory evidence packet? | Add journal scrape and bridge/service checks too | More complete packet | |
| Mandatory evidence packet? | You decide | Claude selects default | ✓ |
| Guard error at observation start? | Stop immediately | Treat guard error as hard stop | |
| Guard error at observation start? | Continue observing guard fail-closed | Recommended safe evidence collection | |
| Guard error at observation start? | Try alternate read-only inspection path first | Attempt guard-gap resolution before verdict | |
| Guard error at observation start? | You decide | Claude selects default | ✓ |
| Live command discipline? | No live commands without a prewritten allowlist | Same as prior phases | |
| Live command discipline? | Allow ad-hoc read-only commands | Lower friction, weaker auditability | |
| Live command discipline? | Only health endpoint reads | Avoid RouterOS inventory | |
| Live command discipline? | You decide | Claude selects default | ✓ |

**User's choice:** You decide for all four.
**Notes:** Decisions captured: 10-15 minute bounded observation; full health/operator/RouterOS/journal/bridge evidence packet; keep collecting fail-closed evidence; deterministic prevalidated read-only command file required.

---

## Guard gap handling

| Question | Option | Description | Selected |
|----------|--------|-------------|----------|
| What to do about REST unsupported Netwatch detail? | Declare not-ready if REST remains unsupported | Safest but may miss SSH fallback | |
| What to do about REST unsupported Netwatch detail? | Plan SSH read-only Netwatch inspection fallback | Recommended before final verdict | |
| What to do about REST unsupported Netwatch detail? | Patch REST client support if feasible | Could be valid but may be impossible with RouterOS REST | |
| What to do about REST unsupported Netwatch detail? | You decide | Claude selects default | ✓ |
| Allow code changes? | No code changes | Evidence/readiness packet only | |
| Allow code changes? | Narrow pure read-only guard inspection fix | Recommended if needed and fully tested | |
| Allow code changes? | Broader route-management implementation changes | Too broad for Phase 257 | |
| Allow code changes? | You decide | Claude selects default | ✓ |
| Is supported guard inspection mandatory? | Supported inspection required | Recommended for ready-for-approval | |
| Is supported guard inspection mandatory? | Operator can waive gap | Higher risk | |
| Is supported guard inspection mandatory? | Gap only blocks active canary | Ambiguous readiness | |
| Is supported guard inspection mandatory? | You decide | Claude selects default | ✓ |
| SSH fallback safety boundary? | Read-only allowlisted SSH; no mutation | Recommended | |
| SSH fallback safety boundary? | Avoid SSH entirely | Simpler but may leave evidence gap | |
| SSH fallback safety boundary? | Use old snapshots only | Stale evidence risk | |
| SSH fallback safety boundary? | You decide | Claude selects default | ✓ |

**User's choice:** You decide for all four.
**Notes:** Decisions captured: attempt/plan SSH read-only fallback; allow only narrow read-only guard-inspection code fix if fully tested; supported ownership inspection required for ready-for-approval; SSH command file must be read-only and allowlist-validated.

---

## Readiness verdict criteria

| Question | Option | Description | Selected |
|----------|--------|-------------|----------|
| What counts as ready-for-approval? | Guard ok + reconciliation ok + circuit closed + no mutation + rollback current | Recommended complete gate | |
| What counts as ready-for-approval? | Health visible + rollback exists even if guard error | Too weak | |
| What counts as ready-for-approval? | Always not-ready in v1.56 | Safe but may ignore solved guard evidence | |
| What counts as ready-for-approval? | You decide | Claude selects default | ✓ |
| What forces not-ready? | Any guard error, inventory mismatch, missing rollback, unhealthy services, or mutation evidence | Recommended | |
| What forces not-ready? | Only guard error or route inventory mismatch | Too narrow | |
| What forces not-ready? | Only actual mutation evidence | Too weak | |
| What forces not-ready? | You decide | Claude selects default | ✓ |
| If ready, ask for active canary approval? | Packet only; no active canary approval in Phase 257 | Recommended | |
| If ready, ask for active canary approval? | Include optional approval gate but do not execute | Could confuse boundary | |
| If ready, ask for active canary approval? | Chain into active canary planning | Out of scope | |
| If ready, ask for active canary approval? | You decide | Claude selects default | ✓ |
| Final artifact shape? | Readiness packet + no-mutation proof + next-milestone recommendation | Recommended | |
| Final artifact shape? | Just update SUMMARY.md with verdict | Too thin | |
| Final artifact shape? | Create full active canary runbook too | Too much / future phase | |
| Final artifact shape? | You decide | Claude selects default | ✓ |

**User's choice:** You decide for all four.
**Notes:** Decisions captured: ready requires clean guard/reconciliation/circuit/no-mutation/rollback/service evidence; not-ready for guard error, mismatch, stale rollback, health failure, mutation evidence, or incomplete evidence; no active canary approval in Phase 257; final artifact is readiness packet plus no-mutation proof and next-milestone recommendation.

---

## Claude's Discretion

Kevin selected "You decide" for all detailed decision questions. Claude locked the recommended conservative defaults in CONTEXT.md.

## Deferred Ideas

- Active one-WAN route mutation canary — future separately approved milestone/phase.
- Netwatch alert-only conversion or retirement — future work after accepted active canary.
- Broad route-management implementation expansion — out of scope unless strictly read-only guard inspection needed for readiness.
