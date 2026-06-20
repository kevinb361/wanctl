---
phase: 255
slug: deploy-shape-safe-off-config-contract
status: complete
created: 2026-06-20
---

# Phase 255 — Research

## Research Question

What do we need to know to plan Phase 255 well: prove cake-shaper's actual steering deploy shape read-only, define a safe/off route-management production config contract, and prepare a rollback/restart plan for Phase 256 while preserving SAFE-20?

## Key Findings

### 1. The phase is about deploy truth, not deploy action

Phase 254 found the active `steering.service` healthy but without the `route_management` health/config surface. The next useful work is to prove the live deploy mechanism and target state before touching production.

Planning implication: Phase 255 should run only read-only live discovery and local/offline config validation. It should produce a Phase 256 proposal, not restart anything.

### 2. Live deploy shape is load-bearing

Prior live-production pitfalls say not to assume git checkout vs flat rsync. The repo supports `/opt/wanctl`, `/etc/wanctl`, systemd units, and deploy scripts, but the live host must be inspected because Phase 254 proved production lagged repo capabilities.

Planning implication: the evidence bundle must capture service unit path, `ExecStart`, process argv, Python interpreter/venv, live code path, git status if applicable, deploy markers, config path, config presence, and health binding.

### 3. Read-only SSH needs a deterministic command gate

A general SSH command channel can mutate services/configs/routes if misused. The existing GSD read-only command gate pattern applies even though this phase targets Linux/service state more than RouterOS.

Planning implication: first execution task must write a command file, validate it against explicit allowed read-only command shapes, reject restart/edit/mutation verbs and shell metacharacters, then execute only validated commands. Transcript no-mutation proof scans `COMMAND:` lines only.

### 4. Safe/off route-management config must be concrete

Phase 252/253 added repo code and examples for route management. Phase 255 should define the exact intended production config shape and validate it offline before proposing a restart.

Planning implication: the config contract artifact must state exact mode/enablement requirements: safe/off or dry-run/observe only, active mutation impossible, explicit migration acknowledgement absent/false unless future active gate, route identifiers/comment anchors present only for validation, guard enabled, and rollback readiness stated.

### 5. Bridge health and steering health are separate surfaces

Phase 254 showed `:9101` bridge health can be healthy while steering lacks `route_management`. This distinction must be carried forward.

Planning implication: Phase 255 evidence may inspect bridge health only to document baseline service health; the Phase 256 proposal must require `steering.service` health from cake-shaper localhost `:9102` as the route-management acceptance source.

### 6. Rollback has to be multi-layered

A future safe/off deploy can fail at code, config, or service health layers without involving route ownership. Rollback should not mention Netwatch mutation except to preserve it unchanged.

Planning implication: the Phase 256 proposal must separate code rollback, config rollback, service restart rollback/stop conditions, bridge-health stop conditions, and no-route-mutation proof.

## Risks / Pitfalls

- Running live commands before command-file validation.
- Including `systemctl restart`, `reload`, `enable`, `disable`, `start`, `stop`, file writes, package installs, rsync, git pull/reset/checkout, or RouterOS mutation in a read-only command file.
- Treating bridge health `:9101` as route-management health.
- Writing a vague safe/off config contract that leaves active mutation ambiguity.
- Failing to capture the rollback anchor before proposing Phase 256 deploy/restart.
- Scanning raw command output for no-mutation proof instead of explicit `COMMAND:` lines.

## Validation Architecture

Phase 255 should produce one plan:

1. `255-01-PLAN.md` — Deploy-shape proof + safe/off config contract + Phase 256 rollback/restart proposal.
   - Writes and validates read-only command file before live SSH.
   - Creates deploy-shape proof artifact.
   - Creates safe/off route-management config contract artifact.
   - Creates Phase 256 deploy/restart proposal with rollback/stop criteria.

Automated planning checks:

- Plan frontmatter contains DEPLOY-01, CONFIG-01, CONFIG-02, SAFE-20.
- Plan contains read-only command artifacts and `COMMAND:` transcript/no-mutation scan requirements.
- Plan forbids live service restart/reload, config edits, RouterOS mutation, Netwatch disablement, CAKE/qdisc mutation, and route-owner flip.
- Plan names the expected evidence artifacts and Phase 256 proposal.
- `git diff --check` passes.

Live/manual execution checks for later `/gsd-execute-phase 255`:

- Command validation artifact reports `passed: true` before live command transcript exists.
- Deploy-shape proof identifies service unit/source/config/code path or records a blocker.
- Config contract validates offline and remains safe/off or dry-run only.
- Phase 256 proposal exists and contains explicit approval gate/rollback/stop criteria.

## RESEARCH COMPLETE
