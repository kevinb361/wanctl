---
phase: 173
reviewers: [codex]
reviewed_at: 2026-04-12T17:15:00Z
plans_reviewed: [173-01-PLAN.md, 173-02-PLAN.md]
---

# Cross-AI Plan Review -- Phase 173

## Codex Review

### Plan 173-01: Version Bump

**Summary:** Appropriately small and matches phase scope, but treats version as purely cosmetic when it's actually a release gate (canary depends on it).

**Strengths:**
- Scope is tight and avoids touching controller logic
- Targets exact user-approved version surfaces from D-01
- Verification is lightweight and proportional
- Isolated Wave 1 sequencing is sensible before production deploy

**Concerns:**
- `MEDIUM` Calling version tampering "accepted" understates risk -- reported version is a release gate because canary-check.sh --expect-version depends on it
- `MEDIUM` "Verify import chain" is vague -- if packaging or service startup reads version differently than import path, plan may pass locally but fail on host
- `LOW` Commit and push are operational but plan doesn't confirm deploy host will receive that exact commit

**Suggestions:**
- Reframe threat model: incorrect version strings are a deploy-validation failure mode, not cosmetic
- Verify all version consumers explicitly, not just Python import
- Add check that deploy path resolves to intended commit before Wave 2 starts
- Confirm pyproject.toml, runtime import, and canary expectation are all identical 1.35.0

**Risk Assessment:** LOW-MEDIUM

---

### Plan 173-02: Rolling Deploy & Canary

**Summary:** Directionally correct but has one major operational flaw: stopping all services up front behaves more like a coordinated outage than a canary. Needs clearer failure handling, rollback rules, and per-WAN sequencing.

**Strengths:**
- Matches user decisions on order (Spectrum first, ATT with --with-steering)
- Includes migration timing and idempotency handling
- Separates deployment actions from post-deploy validation with human checkpoints
- Includes explicit success checks for version, per-WAN DB, and storage pressure
- Keeps focused on deployment, no refactor creep

**Concerns:**
- `HIGH` "Stop all services" conflicts with rolling/canary intent -- creates broader outage window than necessary
- `HIGH` No explicit rollback strategy if Spectrum deploys but fails canary
- `HIGH` Migration scope underspecified -- if global/shared, could have cross-service effects
- `MEDIUM` 5s wait for steering start not justified -- should be event-based
- `MEDIUM` 20s stabilization wait is brittle -- could use health endpoint readiness
- `MEDIUM` Pre-flight config diff doesn't specify what diffs are acceptable vs blocking
- `MEDIUM` Checks DB-file existence but not whether service is writing to correct per-WAN DB
- `MEDIUM` Storage pressure checked only post-deploy, should also check pre-migration
- `LOW` No handling for partial deploy states (code updated but restart failure)

**Suggestions:**
- True per-WAN canary sequencing: stop Spectrum only -> deploy -> migrate -> start -> validate -> only then touch ATT
- Hard stop rules: if Spectrum fails at any stage, do not touch ATT
- Explicit rollback steps: restore previous code, restart prior known-good service set
- Replace fixed sleeps with observable gates (systemctl is-active, health endpoint)
- Expand post-deploy checks: confirm DB file mtime changes after startup
- Keep steering out of Spectrum canary blast radius

**Risk Assessment:** MEDIUM-HIGH

---

## Consensus Summary

### Agreed Strengths
- Plans are well-scoped and aligned to phase goal
- Version bump is appropriately isolated in Wave 1
- Human checkpoints for operational tasks are appropriate
- Migration idempotency handling is solid

### Agreed Concerns
- **HIGH: Stop-all-services approach defeats rolling/canary purpose** -- need true per-WAN isolation
- **HIGH: No rollback strategy** if deployment partially fails
- **HIGH: Migration blast radius** not scoped to individual WANs
- **MEDIUM: Fixed sleep gates** instead of health-endpoint readiness checks
- **MEDIUM: Version as release gate** not properly reflected in threat model

### Divergent Views
(Single reviewer -- no divergence to report)

### Recommendation
Plan 173-02 needs revision before execution. Key change: restructure deploy sequence to be a true per-WAN canary (deploy+validate Spectrum completely before touching ATT) with explicit rollback gates.
