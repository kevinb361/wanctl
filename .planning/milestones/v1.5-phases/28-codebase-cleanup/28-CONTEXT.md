# Phase 28: Codebase Cleanup - Context

**Gathered:** 2026-01-24
**Status:** Ready for planning

<domain>
## Phase Boundary

Remove dead code, inventory all TODOs/markers, and analyze cyclomatic complexity. This is a cleanup and documentation phase — only dead code removal changes the codebase; everything else produces reports for future action.

</domain>

<decisions>
## Implementation Decisions

### Dead Code Criteria
- Conservative approach: only truly unreachable code and unused imports
- Leave commented code in place
- Check git blame (age and author) before removing anything
- Flag debug/development artifacts but don't remove — may be needed for troubleshooting

### TODO Handling
- Document only — no removal or conversion to issues
- Create inventory with priority-based categorization (Critical/High/Medium/Low)
- Include all markers: TODO, FIXME, HACK, XXX, NOTE

### Complexity Analysis
- Cyclomatic complexity only (not line-based length metrics)
- Strict threshold: flag anything over 10
- Flag core algorithm functions too — awareness is valuable even if not refactored
- High-complexity functions become pending todos for future work

### Action vs Report
- Code changes: Remove dead code only (unused imports, unreachable paths)
- Per-file commits for dead code removal
- Produce both: summary document AND prioritized action list
- Complexity issues → new pending todo files

### Claude's Discretion
- Judgment on unused helper functions (test presence, comments, context)
- Choice of complexity analysis tool (radon/flake8 vs manual based on availability)
- Location for TODO inventory (phase deliverable vs .planning/ document)

</decisions>

<specifics>
## Specific Ideas

- Git blame check ensures we understand context before removing anything
- Production system — conservative bias on removal, comprehensive on reporting
- Cleanup report should enable future cleanup phases without re-analysis

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 28-codebase-cleanup*
*Context gathered: 2026-01-24*
