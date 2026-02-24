# Phase 29: Documentation Verification - Context

**Gathered:** 2026-01-24
**Status:** Ready for planning

<domain>
## Phase Boundary

Verify that project documentation accurately reflects the current implementation. Audit docs for factual accuracy, fix discrepancies, and ensure code examples work.

</domain>

<decisions>
## Implementation Decisions

### Audit Scope
- **Files in scope:** CLAUDE.md, README.md, CHANGELOG.md, all docs/*.md files
- **Exclude:** .planning/ directory entirely (workflow artifacts)
- **Depth:** Full audit — claims, completeness, and outdated patterns/advice
- **Code examples:** Verify ALL examples work, not just spot-check
- **Comments:** In scope — docstrings AND inline comments for accuracy
- **CHANGELOG:** Structure verification only (format, versions exist), not claim-by-claim

### Discrepancy Handling
- **Default action:** Log and batch — collect all issues first, then fix in organized commits
- **Code vs doc conflict:** Flag for review — create todo/issue, needs decision before changing
- **Misleading content:** Rewrite for clarity — if it could confuse someone, fix it
- **Deprecated features:** Move to archive section for legacy reference

### Verification Criteria
- **Definition of verified:** No factual errors — every claim about code/config/behavior is accurate
- **Command verification:** Claude decides method per example (manual or automated)
- **Environment-specific:** Verify structure is correct, don't test actual paths
- **Version numbers:** Context-dependent — Claude handles appropriately

### Output Format
- **Report location:** .planning/phases/29-documentation-verification/AUDIT-REPORT.md
- **Report format:** Claude decides (structured findings vs checklist)
- **Commit strategy:** Per-file commits — separate commit for each file fixed
- **Archive:** Yes — keep report as permanent record of what was checked/fixed

### Claude's Discretion
- Priority order for auditing (pick based on risk assessment)
- Verification method per code example
- Report format choice
- Version number handling approach

</decisions>

<specifics>
## Specific Ideas

No specific requirements — open to standard approaches.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 29-documentation-verification*
*Context gathered: 2026-01-24*
