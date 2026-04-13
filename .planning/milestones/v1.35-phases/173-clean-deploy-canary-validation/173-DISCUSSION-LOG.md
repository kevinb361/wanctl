# Phase 173: Clean Deploy & Canary Validation - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md -- this log preserves the alternatives considered.

**Date:** 2026-04-12
**Phase:** 173-clean-deploy-canary-validation
**Areas discussed:** Version Number, Deploy & Restart Sequence, Storage Migration Timing, Canary Validation Scope
**Mode:** --auto (all decisions auto-selected)

---

## Version Number

| Option | Description | Selected |
|--------|-------------|----------|
| 1.35.0 | Standard first release of v1.35 milestone | auto |
| 1.35.1 | Skip .0 to distinguish from milestone start | |

**User's choice:** [auto] 1.35.0 (recommended default)
**Notes:** Follows convention of milestone version = first release version. v1.34 was the last shipped milestone.

---

## Deploy & Restart Sequence

| Option | Description | Selected |
|--------|-------------|----------|
| Rolling, Spectrum first | Deploy and restart Spectrum, validate, then ATT | auto |
| Simultaneous | Deploy both WANs, restart both, canary both | |
| Rolling, ATT first | Deploy ATT first as lower-traffic WAN | |

**User's choice:** [auto] Rolling, Spectrum first (recommended default)
**Notes:** Spectrum is the primary WAN. Rolling minimizes blast radius. deploy.sh does not restart services -- operator handles manually.

---

## Storage Migration Timing

| Option | Description | Selected |
|--------|-------------|----------|
| After deploy, before restart | Archive old DB after new code is in place but before services create new per-WAN DBs | auto |
| Before deploy | Migrate first, then deploy. Risk: old code may not handle missing DB gracefully | |
| Skip if already done | Check for archived DB file to determine if Phase 172 already ran migration | |

**User's choice:** [auto] After deploy, before restart (recommended default)
**Notes:** D-06 adds a safety check -- if migration was already done in Phase 172, skip it here.

---

## Canary Validation Scope

| Option | Description | Selected |
|--------|-------------|----------|
| Health + version + storage pressure | Full validation: health endpoint, version string match, storage status | auto |
| Health endpoint only | Minimal: just canary-check.sh default behavior | |
| Health + version only | Mid-range: confirm version bump, skip storage check | |

**User's choice:** [auto] Health + version + storage pressure (recommended default)
**Notes:** canary-check.sh already supports --expect-version. Storage pressure check validates Phase 172 retention tuning.

---

## Claude's Discretion

- Exact systemctl stop/start commands and waiting strategy
- Whether to run dry-run deploy first
- Config diff verification approach

## Deferred Ideas

None -- discussion stayed within phase scope.
