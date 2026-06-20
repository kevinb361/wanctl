---
phase: 254
slug: dry-run-observation-operator-gated-canary-retirement-decisio
status: complete
created: 2026-06-20
---

# Phase 254 — Research

## Research Question

What do we need to know to plan Phase 254 well: dry-run observation against live route/Netwatch state, rollback proof, an operator-gated one-WAN active canary if approved, and a final keep/rollback/retire decision, while preserving SAFE-19?

## Key Findings

### 1. Phase 254 is production-ish and must use deterministic read-only gates

The phase crosses from mock-only implementation into live observation. The GSD read-only live command gate is directly applicable.

Planning implication: the first execution task must write a timestamped command file before any live command runs, validate it against a narrow allowlist, and abort on mutation-shaped commands or shell metacharacters. Evidence transcripts must prefix issued commands with `COMMAND:`. No-mutation proof must scan only issued command lines so RouterOS output containing words like `policy=read,write,test` does not false-positive.

### 2. Phase 253 already added the core route ownership state surfaces

Actual current code now includes:

- `RouteOwnershipGuard.inspect()` reading `/tool netwatch print detail` and `/system script print detail` through `run_cmd(..., capture=True)` and failing closed on errors.
- `RouteDecisionPolicy.evaluate()` producing pure intended preferences with evidence and no router client.
- `RouteManager.reconcile_startup()`, `RouteCircuitBreaker`, `last_intended_action`, `last_applied_action`, `last_event`, and `status_snapshot()`.
- `SteeringDaemon.get_health_data()` exposing `route_management` through the health facade.
- `SteeringHealthHandler` adding `route_management` and compact route fields to `summary.rows`.
- `operator_summary.py` rendering route owner, guard, circuit, and route mode in steering notes.

Planning implication: Phase 254 should primarily collect/compare live evidence and write runbooks/decision artifacts, not invent a parallel decision/control system.

### 3. Snapshot-A is the rollback source of truth, but live drift must be checked read-only

Phase 251 captured Snapshot-A route/Netwatch/script evidence and a route ownership decision. That evidence is the rollback anchor, but production may drift.

Planning implication: Wave 1 should re-inventory live state read-only and compare it to Snapshot-A before any canary approval packet is considered complete. If drift exists, the packet must record exact drift and either update the rollback evidence read-only or block the active canary.

### 4. Dry-run observation must compare intended wanctl state to current Netwatch behavior

The useful comparison is not “daemon is healthy.” It is:

- live Netwatch/script route owner evidence;
- route manager guard status and active owner;
- route reconciliation status and current route enabled/disabled states;
- route decision/intended action evidence during the observation window;
- operator summary row tokens;
- last intended vs last applied action, where last applied must remain `None`/not mutated in dry-run.

Planning implication: Wave 1 should define an evidence bundle with health snapshots, operator summary output, command transcript, no-mutation proof, and an observation verdict.

### 5. Active canary must be a separate gated plan, not the automatic next command

The ROADMAP explicitly says Wave 2 requires operator approval before active mutation. SAFE-19 also forbids production mutation outside an explicitly approved canary phase.

Planning implication: Plan 254-02 must include a `CHECKPOINT REQUIRED` task that asks the operator before any mutation. It should be valid for the executor to stop with “operator declined / evidence insufficient; keep Netwatch owner” and still complete the decision artifact.

### 6. Rollback semantics must distinguish code rollback from config/ownership rollback

A canary could involve code already deployed with route-management support, production config changes, and RouterOS route/Netwatch ownership changes. These rollback layers differ.

Planning implication: approval packet and canary plan must state rollback precisely:

- code rollback: revert deployed wanctl version if code caused unexpected behavior;
- config rollback: set route management back to safe/off or dry-run and reload/restart only if explicitly approved in the canary;
- ownership rollback: restore Netwatch route mutation and route enabled/disabled state from Snapshot-A.

### 7. Verification should include both repo checks and live evidence checks

Repo checks still matter for docs/artifact quality, but live observation proof is the main gate.

Planning implication: plans should include deterministic artifact checks:

- command allowlist validator exits 0 before live commands;
- transcript issued-command scan finds no mutating actions;
- health payload includes `route_management` keys;
- operator summary contains route owner/guard/circuit/mode tokens;
- approval packet includes rollback, stop criteria, exact canary scope, and final decision template;
- final decision chooses keep/rollback/retire.

## Risks / Pitfalls

- Running broad SSH/RouterOS commands without a deterministic preflight allowlist.
- Scanning raw RouterOS output for mutating tokens instead of only `COMMAND:` lines.
- Treating dry-run success as implicit active-canary approval.
- Mutating Netwatch, routes, production config, systemd, or CAKE/qdisc while claiming “observation.”
- Failing to account for live drift from Snapshot-A before rollback proof.
- Stating rollback ambiguously: code rollback vs config rollback vs route/Netwatch ownership rollback.
- Accepting a canary with weak evidence because the health endpoint is merely “healthy.”

## Validation Architecture

Phase 254 planning should produce two plans:

1. `254-01-PLAN.md` — Dry-run observation + pre-canary approval packet.
   - Includes read-only live command gate.
   - Writes/validates command file before live commands.
   - Collects health/operator/RouterOS evidence.
   - Produces approval packet or a no-canary recommendation.

2. `254-02-PLAN.md` — Operator-gated one-WAN active canary / rollback / retirement decision.
   - Depends on 254-01 evidence.
   - Starts with evidence and rollback preflight.
   - Has an explicit operator approval checkpoint immediately before mutation.
   - Produces final keep/rollback/retire decision.

Automated planning checks:

- Plan frontmatter contains all Phase 254 requirements across the two plans: CB-02, OBS-02, CANARY-01, CANARY-02, CANARY-03, SAFE-19.
- `254-01-PLAN.md` contains `read-only-commands-<timestamp>.txt`, `COMMAND:`, allowlist validation, and no-mutation transcript scanning.
- `254-02-PLAN.md` contains `CHECKPOINT REQUIRED`, explicit operator approval, Snapshot-A rollback, bounded observation, stop criteria, and final decision artifact.
- Both plans include SAFE-19 prohibitions.
- `git diff --check` passes.

Live/manual execution checks (for later `/gsd-execute-phase 254`, not this planning run):

- No live command runs before the command file validates.
- Dry-run observation evidence proves `last_applied_action` remains unset/not mutated unless an approved active canary begins.
- Active canary does not begin without explicit operator approval at execution time.
- Rollback evidence is available before any mutation.

## RESEARCH COMPLETE
