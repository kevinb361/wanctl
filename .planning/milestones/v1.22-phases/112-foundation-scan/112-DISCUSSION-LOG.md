# Phase 112: Foundation Scan - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-03-26
**Phase:** 112-foundation-scan
**Areas discussed:** Finding disposition, Ruff rule triage, Dead code handling, Production VM access

---

## Finding Disposition

| Option | Description | Selected |
|--------|-------------|----------|
| Fix immediately | Fix safe findings in-phase, log risky findings for later | ✓ |
| Report only | Produce findings report only, all fixes in later phases | |
| Categorized backlog | Structured P0-P4 findings file for later phases | |

**User's choice:** Fix immediately (Recommended)
**Notes:** Safe findings (unused deps, ruff autofixes, permissions) fixed in-phase. Risky findings logged for later phases.

---

## Ruff Rule Triage

| Option | Description | Selected |
|--------|-------------|----------|
| Enable all, autofix safe | All 8 categories at once, autofix safe, triage rest | ✓ |
| Staged by category | One category at a time, fix before adding next | |
| You decide | Claude picks based on finding volume | |

**User's choice:** Enable all, autofix safe (Recommended)
**Notes:** Single pyproject.toml change enables C901/SIM/PERF/RET/PT/TRY/ARG/ERA. Auto-fix what's safe, triage the rest.

---

## Dead Code Handling

| Option | Description | Selected |
|--------|-------------|----------|
| Vulture whitelist file | .vulture_whitelist.py documents why each false positive is live | ✓ |
| Inline noqa comments | Annotate false positives directly in source | |
| Separate findings report | Manual true/false positive distinction in report | |

**User's choice:** Vulture whitelist file (Recommended)
**Notes:** Standard vulture pattern. 15+ known false positive patterns from PITFALLS.md research must be validated against all entry points and transport configs.

---

## Production VM Access

| Option | Description | Selected |
|--------|-------------|----------|
| SSH inline commands | Run via SSH from workstation, same as soak checks | ✓ |
| Deploy audit script | Write shell script, scp, run on VM | |
| You decide | Claude picks per audit | |

**User's choice:** SSH inline commands (Recommended)
**Notes:** cake-shaper at 10.10.110.223 (SSH alias: cake-shaper)

---

## Folded Todos

- "Integration test for router communication" — folded into phase scope

## Deferred Ideas

- "LXC container network optimizations" — likely obsolete post-VM migration
- "Auto-disable fusion on low protocol correlation" — feature work, not audit
