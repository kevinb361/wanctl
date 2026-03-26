# Phase 116: Test & Documentation Hygiene - Context

**Gathered:** 2026-03-26
**Status:** Ready for planning

<domain>
## Phase Boundary

Fix test quality issues, update documentation for post-v1.21 VM architecture, archive container-era scripts, align CONFIG_SCHEMA.md, and produce the capstone v1.22 audit findings summary. This is the final phase of the v1.22 Full System Audit milestone.

Requirements: TDOC-01 through TDOC-06 (6 requirements)

</domain>

<decisions>
## Implementation Decisions

### Test Quality Audit (TDOC-01, TDOC-02)
- **D-01:** Catalog ALL test quality issues: assertion-free, over-mocked, and tautological tests.
- **D-02:** FIX only assertion-free and tautological tests (highest risk — give false confidence). Over-mocked tests are lower risk and documented only.
- **D-03:** Phase 112 already fixed 2 stale contract tests and cataloged 8 orphaned fixtures. Use those as input.

### Documentation Review (TDOC-03)
- **D-04:** Targeted updates only — review each doc in docs/*, remove container/LXC references, add VM architecture where relevant. Do NOT rewrite entire docs.
- **D-05:** Focus on accuracy against current architecture (post-v1.21 VM migration). Container references should be replaced with VM/bridge/CAKE-on-Linux references.

### CONFIG_SCHEMA.md Alignment (TDOC-05)
- **D-06:** Align CONFIG_SCHEMA.md with config_validation_utils.py — every accepted param documented, no stale entries. This is the most impactful docs update.

### Container Script Archival (TDOC-04)
- **D-07:** Move container-era scripts to .archive/ directory. Scripts include: container_install_*.sh, verify_steering*.sh, and any other pre-VM scripts.
- **D-08:** Write .archive/manifest.md documenting each script's original purpose and why it was archived.

### Audit Findings Summary (TDOC-06)
- **D-09:** Structure by severity (P0-P4) + recommended milestone (v1.23, v1.24, backlog).
- **D-10:** Include a "Resolved in v1.22" section showing what was fixed across all 5 phases.
- **D-11:** Aggregate findings from ALL phases: 112 (foundation scan), 113 (network audit), 114 (code quality), 115 (operational hardening), 116 (this phase).
- **D-12:** This is the capstone document for the entire v1.22 milestone.

### Claude's Discretion
- Which specific tests are assertion-free or tautological (discovered during scan)
- Ordering of documentation updates
- Severity classification of individual findings (P0-P4 scale)
- .archive/ directory structure

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Prior Phase Findings (aggregate for TDOC-06)
- `.planning/phases/112-foundation-scan/112-01-findings.md` — pip-audit, deptry, deadfixtures, log rotation
- `.planning/phases/112-foundation-scan/112-03-findings.md` — Ruff expansion, complexity baseline
- `.planning/phases/112-foundation-scan/112-04-findings.md` — Vulture dead code inventory
- `.planning/phases/112-foundation-scan/112-02-findings.md` — VM permissions, systemd scores
- `.planning/phases/113-network-engineering-audit/113-01-findings.md` — CAKE params, DSCP trace
- `.planning/phases/113-network-engineering-audit/113-02-findings.md` — Steering audit, measurement methodology
- `.planning/phases/113-network-engineering-audit/113-03-findings.md` — Queue depth baselines
- `.planning/phases/114-code-quality-safety/114-01-exception-triage.md` — Exception triage (96 catches)
- `.planning/phases/114-code-quality-safety/114-02-mypy-probe.md` — MyPy strictness results
- `.planning/phases/114-code-quality-safety/114-02-complexity-analysis.md` — Complexity hotspots
- `.planning/phases/114-code-quality-safety/114-02-import-graph.md` — Import graph analysis
- `.planning/phases/114-code-quality-safety/114-03-thread-safety-audit.md` — Thread safety catalog
- `.planning/phases/114-code-quality-safety/114-03-sigusr1-catalog.md` — SIGUSR1 chain
- `.planning/phases/115-operational-hardening/115-02-backup-recovery-runbook.md` — Backup/recovery runbook

### Documentation Files
- `docs/CONFIG_SCHEMA.md` — Config reference (needs alignment with code)
- `docs/PRODUCTION_INTERVAL.md` — 50ms interval docs
- `docs/PORTABLE_CONTROLLER_ARCHITECTURE.md` — Design principles
- `docs/TRANSPORT_COMPARISON.md` — REST vs SSH performance
- `src/wanctl/config_validation_utils.py` — Source of truth for accepted config params

### Container-Era Scripts (candidates for archival)
- `scripts/container_install_*.sh` — Pre-VM installation scripts (if they exist)
- `scripts/verify_steering*.sh` — Pre-VM verification scripts (if they exist)

### Test Files
- `tests/` — Full test suite (~3,900 tests)
- `.planning/phases/112-foundation-scan/112-01-findings.md` — 8 orphaned fixtures from deadfixtures scan

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- Phase 112-01 deadfixtures scan — 8 orphaned fixtures already cataloged
- Phase 112-03 ruff findings — 33 ERA001 commented-out code instances
- Phase 114-01 exception triage — complete catalog of all 96 catches with dispositions
- `config_validation_utils.py` — source of truth for config params (for CONFIG_SCHEMA.md alignment)

### Established Patterns
- Contract tests in test_phase*_validation.py files — parametrized from pyproject.toml
- CONFIG_SCHEMA.md uses markdown tables for param documentation
- docs/ uses standard markdown with section headers

### Integration Points
- .archive/ directory is new — will need .gitignore review
- CONFIG_SCHEMA.md cross-references config_validation_utils.py accepted params
- Audit summary references all prior phase findings files

</code_context>

<specifics>
## Specific Ideas

No specific requirements — standard test/docs hygiene with the decisions captured above.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 116-test-documentation-hygiene*
*Context gathered: 2026-03-26*
