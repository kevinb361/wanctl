---
phase: 172
reviewers: [codex]
reviewed_at: 2026-04-12T10:30:00Z
plans_reviewed: [172-01-PLAN.md, 172-02-PLAN.md]
---

# Cross-AI Plan Review -- Phase 172

## Codex Review

### Plan 172-01: Per-WAN Storage Config + SystemError-Resilient Maintenance

**Summary:** Mostly well-scoped and aligned with the phase goal. Keeps the per-WAN DB split config-driven, which is appropriately conservative. The retry-on-SystemError approach is pragmatic. Main gaps are around whether retention tuning alone gets the DB below the warning threshold, whether the one-shot VACUUM is operationalized, and whether retry behavior is observable enough.

**Strengths:**
- Keeps per-WAN DB split config-driven rather than changing controller core logic
- Separates storage retention work from broader refactors
- Retry-once behavior is intentionally narrow and avoids swallowing unrelated exceptions
- Test cases are the right baseline set for retry logic
- Threat model is proportional to change scope

**Concerns:**
- **MEDIUM**: Retention config alone does not guarantee immediate shrinkage unless purge + VACUUM is executed as part of rollout
- **MEDIUM**: D-03 (one-shot VACUUM) not clearly assigned in the plan -- phase completion may be ambiguous
- **MEDIUM**: "Skip cycle if retry fails" needs sufficient logging/telemetry -- silent degradation is risky
- **LOW**: Plan doesn't state whether partial maintenance side effects are safe to retry (idempotence)
- **LOW**: No mention of timing/backoff for immediate retry

**Suggestions:**
- Add explicit rollout/verification task for D-03: purge old rows, run VACUUM, confirm DB sizes
- Require warning/error logs and maintenance health signal on SystemError events
- Confirm _run_maintenance() operations are retry-safe mid-cycle
- Define expected storage warning threshold in plan verification

**Risk Assessment: MEDIUM** -- Code change is small and production-safe, but plan under-specifies the operational step needed to reclaim disk space.

---

### Plan 172-02: analyze_baseline Entry Point + CLI Multi-DB Discovery

**Summary:** Directionally sound, matches user decisions well. Promoting analyze_baseline and creating shared DB discovery logic is the right approach. Main risk is hidden coupling: auto-discovery and merged multi-DB reads can introduce ordering, duplication, schema-compatibility, and partial-failure issues unless merge semantics are defined tightly.

**Strengths:**
- Aligns cleanly with D-10 (entry point promotion)
- Consolidates DB discovery into shared utility instead of duplicating logic
- Preserves backward compatibility with thin wrapper and legacy fallback
- Test targets are appropriate for the new merge path

**Concerns:**
- **HIGH**: "Merge results" is underspecified -- overlapping timestamps, different sampling cadences, or schema differences could be misleading
- **MEDIUM**: Auto-discovery precedence: if both legacy and per-WAN DBs exist, naive inclusion could double-count or mix transitional data
- **MEDIUM**: No stated behavior when one DB is missing, unreadable, locked, or corrupt
- **MEDIUM**: No import-stability checks for direct module execution vs console entry point invocation
- **LOW**: Discovery glob ordering should be deterministic for stable output

**Suggestions:**
- Define exact multi-DB merge semantics: row ordering, overlapping timestamp handling, per-WAN labeling
- Specify legacy coexistence: if per-WAN files exist, either ignore metrics.db or require explicit migration rule
- Add tests for partial failure: one DB missing, unreadable, corrupt, or empty
- Ensure CLI output identifies WAN source when relevant for troubleshooting

**Risk Assessment: MEDIUM** -- Packaging cleanup is low-risk, but multi-DB discovery/merge has real correctness risk if edge cases aren't nailed down.

---

### Cross-Plan Assessment

**Concerns:**
- **MEDIUM**: Both plans are Wave 1 with no dependencies, but there's a soft verification dependency -- multi-DB tooling is most meaningful after per-WAN config exists
- **MEDIUM**: Neither plan explicitly owns the D-07 fresh-start migration behavior
- **MEDIUM**: Phase goal says "all code bugs found during v1.34 UAT are fixed" but plans only cover the listed items
- **LOW**: Production validation steps are implied rather than defined

**Suggestions:**
- Add a rollout/verification checklist covering: config deployed, fresh DB creation, purge + VACUUM, post-change DB sizes, maintenance pass, CLI success against production DBs
- Explicitly map each success criterion to a plan task or rollout step
- Confirm whether any additional v1.34 UAT bugs exist outside these two plans

**Overall Phase Risk: MEDIUM** -- Implementation ideas are conservative and appropriate, but verification and ownership gaps around DB shrinkage, migration state, and multi-DB correctness should be tightened.

---

## Consensus Summary

*Single reviewer -- consensus analysis requires 2+ reviewers.*

### Key Concerns (prioritized)

1. **Multi-DB merge semantics underspecified (HIGH)** -- The plan says "merge results" but doesn't define how overlapping timestamps, partial failures, or legacy coexistence are handled. This is the highest-risk item.

2. **One-shot VACUUM not operationalized (MEDIUM)** -- D-03 is a locked decision but no plan task owns it. It may fall through the cracks between Phase 172 and Phase 173.

3. **Maintenance retry observability (MEDIUM)** -- SystemError retry needs sufficient logging to diagnose repeated failures in production. The plan has the log lines but should ensure they're visible in operator surfaces.

4. **Fresh-start migration ownership (MEDIUM)** -- D-07 says new per-WAN DBs start empty, but neither plan explicitly verifies this happens correctly at deploy time.

5. **Legacy + per-WAN coexistence (MEDIUM)** -- discover_wan_dbs() fallback to metrics.db needs explicit precedence rules to avoid double-counting during transition.

### Agreed Strengths

- Conservative, config-driven approach to per-WAN DB split
- Clean separation between runtime (Plan 01) and tooling (Plan 02)
- Appropriate test coverage targets
- No changes to control-loop core logic

### Divergent Views

*Single reviewer -- no divergent views to report.*

---

*Review completed: 2026-04-12*
*Reviewers: Codex (OpenAI o4-mini)*
*To incorporate feedback: `/gsd-plan-phase 172 --reviews`*
