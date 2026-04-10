# Phase 116: Test & Documentation Hygiene - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.

**Date:** 2026-03-26
**Phase:** 116-test-documentation-hygiene
**Areas discussed:** Test quality fix scope, Docs update depth, Container script archival, Audit summary format

---

## Test Quality Fix Scope

| Option | Description | Selected |
|--------|-------------|----------|
| Fix assertion-free + tautological only | Highest risk tests that give false confidence | x |
| Fix everything found | All quality issues including over-mocked | |
| Catalog only, fix nothing | Document and defer all fixes | |

**User's choice:** Fix assertion-free + tautological only

---

## Docs Update Depth

| Option | Description | Selected |
|--------|-------------|----------|
| Targeted updates | Remove container refs, add VM architecture, don't rewrite | x |
| Full rewrite | Rewrite every doc from scratch | |
| CONFIG_SCHEMA.md only | Minimal scope | |

**User's choice:** Targeted updates

---

## Container Script Archival

| Option | Description | Selected |
|--------|-------------|----------|
| Move to .archive/ with manifest | Move scripts, write manifest.md | x |
| Delete entirely | Remove from repo | |
| Keep but mark deprecated | Add deprecation headers | |

**User's choice:** Move to .archive/ with manifest

---

## Audit Summary Format

| Option | Description | Selected |
|--------|-------------|----------|
| By severity + milestone | P0-P4 severity, recommended milestone, resolved section | x |
| By phase | Organized by originating phase | |
| By category | Grouped by type | |

**User's choice:** By severity + milestone

---

## Claude's Discretion

- Which specific tests are assertion-free or tautological
- Ordering of documentation updates
- Severity classification of findings
- .archive/ directory structure

## Deferred Ideas

None -- discussion stayed within phase scope.
