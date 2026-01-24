# Phase 30: Security Audit - Context

**Gathered:** 2026-01-24
**Status:** Ready for planning

<domain>
## Phase Boundary

Audit dependencies for known vulnerabilities, add security scanning to the development workflow, and produce an initial audit report. Focus on Python dependencies, code patterns, secret detection, and license compliance. Container image scanning is out of scope.

</domain>

<decisions>
## Implementation Decisions

### Scanning Scope
- Python dependency vulnerability scanning (pip-audit or safety)
- Static code analysis with bandit for security anti-patterns
- Secret detection with detect-secrets
- License compliance checking for copyleft licenses
- Container image scanning NOT included (dependencies only)

### Severity Thresholds
- Dependency CVEs: Critical + High (CVSS 7.0+) block, medium/low are warnings
- Bandit findings: All findings block (strict mode)
- Secret detection: Always blocks — no exceptions
- License violations: Block on copyleft (GPL/AGPL/LGPL), permissive allowed

### Tooling Integration
- Add `make security` target (Makefile-based, not pre-commit)
- Whether to include in `make ci`: Claude's discretion based on scan duration
- Output format: Console summary (human-readable terminal output)
- Produce initial audit report + set up ongoing scanning

### Remediation Workflow
- Critical/High vulnerabilities: Fix immediately — blocks everything
- False positives: Inline suppressions with `# nosec` and justification
- Unpatched dependencies: Case-by-case based on severity and exploitability
- Audit report location: `.planning/phases/30-security-audit/` (planning artifact)

### Claude's Discretion
- Specific tool versions (pip-audit vs safety, detect-secrets config)
- Whether `make security` is part of `make ci` (depends on scan duration)
- Baseline file format for detect-secrets
- Exact bandit configuration and rule selection

</decisions>

<specifics>
## Specific Ideas

- Strict blocking on bandit findings — no tolerance for code security issues
- Zero tolerance for detected secrets — always fails immediately
- Report is a planning artifact, not permanent docs (can be removed after milestone)

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 30-security-audit*
*Context gathered: 2026-01-24*
