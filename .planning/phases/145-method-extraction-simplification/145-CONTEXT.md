# Phase 145: Method Extraction & Simplification - Context

**Gathered:** 2026-04-06
**Status:** Ready for planning

<domain>
## Phase Boundary

Reduce long functions (>50 lines excluding docstrings) and high cyclomatic complexity in src/wanctl/ to make every function readable in a single screen. No behavioral changes -- all existing tests must pass unchanged after every extraction.

Requirements: CPLX-02 (long methods extracted into smaller, testable functions), CPLX-04 (high cyclomatic complexity functions refactored).

</domain>

<decisions>
## Implementation Decisions

### Scope & Priority
- **D-01:** Target functions >100 lines (Mega + Large tiers, ~21 functions). Medium functions (50-100 lines) are at Claude's discretion -- split proactively if it improves readability, otherwise leave
- **D-02:** Include the steering/ subpackage in scope. steering/daemon.py (run_cycle 268 LOC, main 214 LOC) and steering/health.py (_get_health_status 211 LOC) have the same mega-function problem
- **D-03:** C901 complexity is already clean -- no violations at any threshold. Focus is entirely on line count reduction, not branching depth

### Extraction Strategy
- **D-04:** Decompose mega-functions (>200 LOC) by lifecycle phases: init → setup → validate → execute → cleanup. Each phase becomes a named helper function. Natural for main() and __init__ patterns
- **D-05:** main() stays in autorate_continuous.py. Helpers extracted alongside. pyproject.toml entry_points, systemd units, and docs are NOT modified
- **D-06:** Same approach for steering/daemon.py main() -- keep in place, extract helpers

### Threshold Strictness
- **D-07:** Approximate ~50 line target. Allow 50-60 for functions that are cohesive and readable as-is. Don't force artificial splits on clean code just to hit a number
- **D-08:** Measurement: lines excluding docstrings. Blank lines and comments count toward the total

### Helper Placement
- **D-09:** Extracted helpers stay in the same module as underscore-prefixed private functions (_setup_logging, _init_storage, etc.). Keeps related code together
- **D-10:** Exception: if placing helpers in the same file would push it over ~500 LOC (Phase 144 threshold), move helpers to a new focused module instead
- **D-11:** Follow existing naming patterns: descriptive verb_noun names (e.g., _parse_autorate_args, _init_storage, _acquire_daemon_locks)

### Claude's Discretion
- Exact decomposition boundaries for each function
- Whether medium functions (50-100 lines) get split or left as-is
- Helper grouping when multiple helpers are extracted from one function
- Whether to create new modules for files that would exceed 500 LOC after extraction
- Naming convention for extracted helpers (Claude picks descriptive names per function)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Architecture
- `.planning/codebase/ARCHITECTURE.md` -- Layer decomposition, class locations, daemon structure
- `.planning/codebase/STRUCTURE.md` -- Current file layout and module organization
- `.planning/codebase/CONVENTIONS.md` -- Naming conventions, import patterns

### Phase 144 results (module structure after splitting)
- `.planning/phases/144-module-splitting/144-CONTEXT.md` -- Phase 144 decisions (flat modules, no re-export shims, clean import updates)
- `.planning/phases/144-module-splitting/144-VERIFICATION.md` -- Post-split LOC distribution and known large files

### Requirements
- `.planning/REQUIREMENTS.md` -- CPLX-02 and CPLX-04 definitions and traceability

### Target files (top 6 mega-functions >200 LOC)
- `src/wanctl/autorate_continuous.py` -- main() at 611 LOC
- `src/wanctl/wan_controller.py` -- run_cycle() at 446 LOC, __init__() at 400 LOC
- `src/wanctl/health_check.py` -- _get_health_status() at 346 LOC
- `src/wanctl/steering/daemon.py` -- run_cycle() at 268 LOC, main() at 214 LOC
- `src/wanctl/steering/health.py` -- _get_health_status() at 211 LOC

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- Phase 144 established the module splitting pattern: extract, update imports, verify tests pass
- `vulture_whitelist.py` and `make dead-code` enforce no dead code after refactoring
- `make ci` (ruff + mypy + pytest) validates all changes

### Established Patterns
- Flat module structure (no subpackages except steering/, storage/, backends/)
- Absolute imports throughout (never relative)
- Underscore-prefixed private functions for internal helpers (_parse_args, _init_storage, etc.)
- Phase 144 D-06: No re-export shims -- clean import updates at all sites

### Integration Points
- pyproject.toml entry_points must NOT change (main() stays in place)
- systemd unit files reference autorate_continuous:main
- Test files import specific functions/classes -- mock targets may need updating when functions move

### Current LOC Distribution (post Phase 144)
- wan_controller.py: 2,579 LOC (WANController class -- biggest extraction target)
- autorate_config.py: 1,200 LOC (Config class)
- check_cake.py: 1,114 LOC
- autorate_continuous.py: 1,095 LOC (orchestrator + main)
- calibrate.py: 752 LOC
- benchmark.py: 723 LOC
- health_check.py: ~675 LOC
- check_config_validators.py: 569 LOC (post gap closure)

</code_context>

<specifics>
## Specific Ideas

No specific requirements -- open to standard approaches.

</specifics>

<deferred>
## Deferred Ideas

- Medium functions (50-100 lines, ~79 functions) may be addressed proactively at Claude's discretion but are not mandatory targets
- Pre-existing files between 500-836 LOC deferred from Phase 144 (health_check, routeros_rest, state_manager, history) -- file-level splitting not in scope here, but method extraction within them is

### Reviewed Todos (not folded)
- "Integration test for router communication" -- testing area, not relevant to method extraction scope

</deferred>

---

*Phase: 145-method-extraction-simplification*
*Context gathered: 2026-04-06*
