---
phase: 172
reviewers: [codex]
reviewed_at: 2026-04-12T11:00:00Z
review_round: 2
plans_reviewed: [172-01-PLAN.md, 172-02-PLAN.md]
---

# Cross-AI Plan Review -- Phase 172 (Round 2)

## Round 1 Concern Resolution

| # | Original Concern | Severity | Status |
|---|-----------------|----------|--------|
| 1 | Multi-DB merge semantics underspecified | HIGH | ADDRESSED |
| 2 | One-shot VACUUM not operationalized | MEDIUM | PARTIALLY ADDRESSED |
| 3 | Legacy + per-WAN DB coexistence precedence | MEDIUM | ADDRESSED |
| 4 | Maintenance retry observability | MEDIUM | ADDRESSED |
| 5 | Partial failure behavior in multi-DB reads | MEDIUM | ADDRESSED |
| 6 | Fresh-start migration ownership | MEDIUM | ADDRESSED |

**5 of 6 concerns fully addressed. 1 partially addressed (VACUUM deferred to Phase 173).**

---

## Codex Review (Round 2)

### Round 1 Concern Details

**1. Multi-DB merge semantics (HIGH) -- ADDRESSED**
Discovery, precedence, merge behavior, ordering, and no-dedup semantics are now defined with explicit tests.

**2. One-shot VACUUM (MEDIUM) -- PARTIALLY ADDRESSED**
Plan now explicitly assigns D-03 to Phase 173 with exact commands documented. Concern: Phase 172 STOR-01 says "DB size reduced" but the actual size-reduction step is deferred. Phase can finish without requirement being fully achieved unless Phase 173 is treated as a hard dependency.

**3-6. All ADDRESSED** -- precedence rules explicit, retry logging observable, partial failure handled, migration ownership clear.

### New Concerns (Round 2)

- **MEDIUM**: Mixed rollout data loss -- If one WAN migrates to per-WAN DB but another still writes to legacy metrics.db, the "per-WAN present = ignore legacy" rule drops valid history. Needs either atomic rollout precondition or narrower rule ("ignore legacy only when all configured WAN DBs have migrated").
- **MEDIUM**: Total failure semantics -- If all DB reads fail or discovery finds no DBs, CLI should fail loudly with non-zero exit. Currently unspecified.
- **LOW**: Broad Exception catch per-DB may mask programmer bugs. Should be scoped to sqlite3.Error or OSError for resilience against corrupt/unreadable files only.

### Summary

Revision quality is materially better. The original design gaps around merge semantics, precedence, retry logging, and migration ownership are mostly resolved. Plans are now implementation-grade. Remaining issues are about rollout safety and failure-mode correctness rather than missing detail.

### Risk Assessment

**MEDIUM** -- If the three remaining semantics are tightened, plans are ready.

---

## Consensus Summary (Round 2)

### Resolution Progress

- Round 1: 6 concerns raised (1 HIGH, 5 MEDIUM)
- Round 2: 5 resolved, 1 partially resolved, 3 new (all MEDIUM or LOW)

### Remaining Concerns (prioritized)

1. **STOR-01 depends on Phase 173 VACUUM (MEDIUM)** -- Phase 172 sets retention config, Phase 173 actually reclaims space. This is by design (D-03 is a manual deploy step), but STOR-01 won't be fully satisfied until Phase 173 runs. The ROADMAP already captures this dependency.

2. **Mixed rollout data loss risk (MEDIUM)** -- Mitigated in practice: deploy.sh deploys both WAN configs atomically, and both services restart together. The "one migrated, one not" state is transient at most. Plan could note this as a deployment precondition.

3. **Total failure exit code (MEDIUM)** -- The plan already has `if not db_paths: print(..., file=sys.stderr); return 1` in history.py. Codex may have missed this. The discover_wan_dbs empty case returns `[]` which triggers the check.

4. **Broad Exception catch (LOW)** -- Valid style concern. Could narrow to `(sqlite3.Error, OSError)` for production correctness while still being resilient to corrupt files.

### Agreed Strengths (both rounds)

- Conservative, config-driven per-WAN DB split
- Clean plan separation (runtime vs tooling)
- No changes to control-loop core logic
- Revision genuinely addressed the substance of Round 1 feedback

---

*Review completed: 2026-04-12 (Round 2)*
*Reviewer: Codex (OpenAI o4-mini)*
*To incorporate feedback: `/gsd-plan-phase 172 --reviews`*
