# Requirements: wanctl

**Defined:** 2026-01-23
**Core Value:** Sub-second congestion detection with 50ms control loops

## v1.5 Requirements

Requirements for Quality & Hygiene milestone. Each maps to roadmap phases.

### Test Coverage

- [ ] **COV-01**: pytest-cov configured in pyproject.toml with source paths
- [ ] **COV-02**: `make coverage` target generates coverage report
- [ ] **COV-03**: HTML coverage report generated in htmlcov/
- [ ] **COV-04**: Coverage threshold enforced (fail if below target)
- [ ] **COV-05**: Coverage badge added to README.md

### Codebase Cleanup

- [ ] **CLN-01**: Dead code identified and removed (unused imports, functions)
- [ ] **CLN-02**: TODO/FIXME comments triaged (resolved or documented)
- [ ] **CLN-03**: Complexity analysis run, high-complexity functions identified
- [ ] **CLN-04**: Automated ruff --fix applied for style consistency
- [ ] **CLN-05**: Pattern consistency reviewed across modules

### Documentation Verification

- [ ] **DOC-01**: Version numbers verified in all docs (match 1.4.0)
- [ ] **DOC-02**: CLI examples and commands verified working
- [ ] **DOC-03**: Config docs match current schema (CONFIG_SCHEMA.md)
- [ ] **DOC-04**: Architecture descriptions match current implementation
- [ ] **DOC-05**: Stale documentation sections removed

### Security Audit

- [ ] **SEC-01**: pip-audit or safety check run against dependencies
- [ ] **SEC-02**: Findings documented (even if none)
- [ ] **SEC-03**: Dependencies updated if CVEs found
- [ ] **SEC-04**: Security scanning added to CI pipeline
- [ ] **SEC-05**: Transitive dependencies reviewed

## Future Requirements

None currently.

## Out of Scope

| Feature | Reason |
|---------|--------|
| Prometheus integration | External monitoring out of scope per constraints |
| Automated doc generation | Manual verification sufficient for this milestone |
| Full test rewrite | Cleanup only, not refactoring test architecture |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| COV-01 | 27 | Pending |
| COV-02 | 27 | Pending |
| COV-03 | 27 | Pending |
| COV-04 | 27 | Pending |
| COV-05 | 27 | Pending |
| CLN-01 | 28 | Pending |
| CLN-02 | 28 | Pending |
| CLN-03 | 28 | Pending |
| CLN-04 | 28 | Pending |
| CLN-05 | 28 | Pending |
| DOC-01 | 29 | Pending |
| DOC-02 | 29 | Pending |
| DOC-03 | 29 | Pending |
| DOC-04 | 29 | Pending |
| DOC-05 | 29 | Pending |
| SEC-01 | 30 | Pending |
| SEC-02 | 30 | Pending |
| SEC-03 | 30 | Pending |
| SEC-04 | 30 | Pending |
| SEC-05 | 30 | Pending |

**Coverage:**
- v1.5 requirements: 20 total
- Mapped to phases: 20
- Unmapped: 0

---
*Requirements defined: 2026-01-23*
*Last updated: 2026-01-24 after roadmap creation*
