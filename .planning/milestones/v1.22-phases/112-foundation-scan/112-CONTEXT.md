# Phase 112: Foundation Scan - Context

**Gathered:** 2026-03-26
**Status:** Ready for planning

<domain>
## Phase Boundary

Run all mechanical audit tools to produce actionable inventories that unblock Phases 113-116. Safe findings are fixed in-phase; risky findings are logged for later phases. No architectural changes, no dead code removal (identification only).

Requirements: FSCAN-01 through FSCAN-08 (8 requirements)

</domain>

<decisions>
## Implementation Decisions

### Finding Disposition
- **D-01:** Fix safe findings immediately in-phase (unused deps, ruff autofixes, permission corrections). Log risky findings for later phases with P0-P4 severity.
- **D-02:** Each tool run produces findings that are either fixed inline or documented in a structured findings section of the phase output.

### Ruff Rule Expansion
- **D-03:** Enable all 8 new rule categories at once (C901/SIM/PERF/RET/PT/TRY/ARG/ERA) in a single pyproject.toml change.
- **D-04:** Auto-fix everything ruff can fix safely. Manually triage the rest. One commit for the expansion + autofixes.

### Dead Code Handling
- **D-05:** Use vulture with a `.vulture_whitelist.py` file to document false positives. Standard vulture pattern.
- **D-06:** The 15+ "looks dead but isn't" patterns from PITFALLS.md research must be validated against all 8 CLI entry points and both transport configurations (linux-cake and rest/ssh) before any code is flagged as truly dead.
- **D-07:** No dead code removal in this phase — identification and inventory only.

### Production VM Access
- **D-08:** Run all production audits via SSH inline commands from workstation (`ssh cake-shaper '...'`). No script deployment needed.
- **D-09:** Production VM is cake-shaper at 10.10.110.223 (SSH alias: `cake-shaper`).

### Folded Todos
- **D-10:** "Integration test for router communication" todo folded into scope — assess current router communication test coverage as part of the foundation scan.

### Claude's Discretion
- Tool installation method (pip install vs pipx vs uv) for one-shot audit tools
- Specific ruff rule ignore list for rules that produce too many false positives on this codebase
- pytest-deadfixtures output format and triage approach

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Research
- `.planning/research/SUMMARY.md` — Full research synthesis with tool recommendations and pitfall catalog
- `.planning/research/STACK.md` — Detailed tool analysis with versions and execution commands
- `.planning/research/PITFALLS.md` — 15 "looks dead but isn't" patterns with exact code locations

### Project Configuration
- `pyproject.toml` — Current ruff rules, mypy config, dependencies, tool settings
- `.planning/codebase/CONVENTIONS.md` — Established coding patterns (2026-03-10)
- `.planning/codebase/STACK.md` — Current technology stack

### Production
- `/etc/wanctl/spectrum.yaml` — Production Spectrum config (on cake-shaper VM)
- `/etc/wanctl/att.yaml` — Production ATT config (on cake-shaper VM)
- `/etc/systemd/system/wanctl-nic-tuning.service` — NIC tuning unit (on cake-shaper VM)
- `/etc/systemd/system/wanctl@.service` — Service template (on cake-shaper VM)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `pyproject.toml` already has ruff, mypy, pytest-cov, bandit, pip-audit, detect-secrets, pip-licenses configured
- `Makefile` has `make lint`, `make type`, `make test`, `make ci`, `make security` targets
- `.planning/codebase/` has 7 analysis documents from 2026-03-10 codebase mapping

### Established Patterns
- Ruff format + ruff check as dual linting (format is separate from check)
- MyPy running with `disallow_untyped_defs = false` (permissive)
- pytest with coverage enforcement at 90% (`fail_under=90`)
- `make security` runs bandit + pip-audit + detect-secrets + pip-licenses

### Integration Points
- `pyproject.toml [tool.ruff.lint.select]` — where rule expansion happens
- `pyproject.toml [tool.mypy]` — where strictness flags live
- Production VM systemd units at `/etc/systemd/system/wanctl@.service` and `wanctl-nic-tuning.service`

</code_context>

<specifics>
## Specific Ideas

No specific requirements — standard audit tool execution with the decisions captured above.

</specifics>

<deferred>
## Deferred Ideas

### Reviewed Todos (not folded)
- "Investigate LXC container network optimizations" — likely obsolete post-VM migration, belongs in cleanup (Phase 116)
- "Auto-disable fusion when protocol correlation drops" — feature work, not audit scope

</deferred>

---

*Phase: 112-foundation-scan*
*Context gathered: 2026-03-26*
