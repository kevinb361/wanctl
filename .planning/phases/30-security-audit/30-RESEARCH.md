# Phase 30: Security Audit - Research

**Researched:** 2026-01-24
**Domain:** Python security scanning (dependency vulnerabilities, SAST, secret detection, license compliance)
**Confidence:** HIGH

## Summary

This research covers four security scanning tools decided in CONTEXT.md: pip-audit for dependency vulnerabilities, bandit for static security analysis, detect-secrets for secret detection, and pip-licenses for license compliance checking. All tools are mature, well-maintained, and have straightforward CI integration.

Key finding: pip-audit does NOT support severity filtering (CVSS thresholds). The maintainers explicitly reject this feature, citing that CVSS scores are context-dependent and must come from upstream (OSV/PyPI) which don't yet provide them. The user's requirement for "Critical + High (CVSS 7.0+) blocking" cannot be directly implemented with pip-audit. Workaround: treat ALL pip-audit findings as blocking (any vulnerability = fail), or post-process JSON output with external scoring.

**Primary recommendation:** Use pip-audit with all-vulnerabilities-block approach (simpler and safer than attempting severity filtering), bandit with strict mode (-lll for HIGH severity only is too lenient per CONTEXT.md which requires ALL findings block), detect-secrets with baseline file, and pip-licenses with --fail-on for copyleft detection.

## Standard Stack

The established tools for Python security scanning:

### Core
| Tool | Version | Purpose | Why Standard |
|------|---------|---------|--------------|
| pip-audit | 2.10.0 | Dependency vulnerability scanning | PyPA official, queries PyPI advisory database, well-maintained |
| bandit | 1.9.3 | Static security analysis (SAST) | PyCQA standard, AST-based detection, pyproject.toml support |
| detect-secrets | 1.5.0 | Secret detection | Yelp-maintained, baseline workflow, pragma allowlisting |
| pip-licenses | 5.5.0 | License compliance | --fail-on/--allow-only options, multiple output formats |

### Supporting
| Tool | Version | Purpose | When to Use |
|------|---------|---------|-------------|
| liccheck | 0.9.2 | Alternative license checker | When need authorized/unauthorized list approach |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| pip-audit | safety | safety has CVSS filtering but requires API key for full database |
| bandit | semgrep | semgrep more powerful but heavier, bandit sufficient for Python-specific patterns |
| detect-secrets | gitleaks | gitleaks faster but detect-secrets has better baseline workflow |
| pip-licenses | pip-license-checker | pip-license-checker has built-in copyleft detection but requires Java/Docker |

**Installation:**
```bash
# Add to dev dependency group in pyproject.toml
pip install pip-audit bandit detect-secrets pip-licenses

# Or via uv
uv pip install pip-audit bandit detect-secrets pip-licenses
```

## Architecture Patterns

### Recommended Makefile Integration
```makefile
.PHONY: security security-deps security-code security-secrets security-licenses

# Run all security scans
security: security-deps security-code security-secrets security-licenses

# Dependency vulnerability scan
security-deps:
	.venv/bin/pip-audit

# Static security analysis
security-code:
	.venv/bin/bandit -r src/ -c pyproject.toml

# Secret detection
security-secrets:
	.venv/bin/detect-secrets scan --baseline .secrets.baseline

# License compliance
security-licenses:
	.venv/bin/pip-licenses --fail-on="GPL;AGPL;LGPL" --partial-match
```

### Pattern 1: All-Blocking Dependency Scan
**What:** Treat any vulnerability as blocking (no severity filtering)
**When to use:** When pip-audit doesn't support CVSS filtering (current state)
**Example:**
```bash
# Source: https://github.com/pypa/pip-audit
pip-audit  # Exit code 1 = vulnerabilities found, 0 = clean
```

### Pattern 2: Bandit with pyproject.toml Configuration
**What:** Configure bandit via pyproject.toml for project-specific settings
**When to use:** Always - keeps configuration centralized
**Example:**
```toml
# Source: https://bandit.readthedocs.io/en/latest/config.html
[tool.bandit]
exclude_dirs = ["tests", ".venv"]
# No skips = strict mode (all findings block per CONTEXT.md)
```

### Pattern 3: detect-secrets Baseline Workflow
**What:** Create baseline file, scan against it for new secrets only
**When to use:** When codebase may have intentional test fixtures with secret-like patterns
**Example:**
```bash
# Source: https://github.com/Yelp/detect-secrets
# Initial baseline creation
detect-secrets scan > .secrets.baseline

# Subsequent scans check for NEW secrets
detect-secrets scan --baseline .secrets.baseline
```

### Anti-Patterns to Avoid
- **Severity filtering workarounds:** Don't pipe pip-audit to external NVD API - unreliable, rate-limited
- **Blanket nosec comments:** Don't use `# nosec` without specifying test IDs and justification
- **Skipping tests directory:** Tests can contain exploitable code too; scan them

## Don't Hand-Roll

Problems with existing solutions:

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Vulnerability database | Custom CVE scraper | pip-audit | PyPI advisory database is authoritative, continuously updated |
| Secret patterns | Custom regex | detect-secrets | 15+ plugins, handles entropy detection, reduces false positives |
| License detection | Manual inspection | pip-licenses | Handles trove classifiers, metadata, mixed sources |
| Code security patterns | grep for "eval" | bandit | AST-based detection catches obfuscated patterns |

**Key insight:** Security scanning requires databases and detection patterns that evolve faster than any project can maintain.

## Common Pitfalls

### Pitfall 1: Expecting pip-audit Severity Filtering
**What goes wrong:** Configuring CI to only fail on "high severity" vulnerabilities
**Why it happens:** Assuming pip-audit works like safety or other tools
**How to avoid:** Accept all-or-nothing approach; pip-audit maintainers explicitly reject severity filtering
**Warning signs:** Looking for --severity or --cvss flags that don't exist

### Pitfall 2: Bandit False Positive Noise
**What goes wrong:** 15%+ false positive rate in untuned configurations
**Why it happens:** Broad regex patterns flag safe code (logging, test fixtures)
**How to avoid:** Use `# nosec B602, B607` with specific test IDs and justification comments
**Warning signs:** Developers disabling bandit rather than addressing findings

### Pitfall 3: detect-secrets Baseline Drift
**What goes wrong:** Baseline becomes stale, new legitimate test secrets trigger failures
**Why it happens:** Not auditing baseline after adding test fixtures
**How to avoid:** Run `detect-secrets audit .secrets.baseline` to review and label findings
**Warning signs:** Frequent `# pragma: allowlist secret` additions without review

### Pitfall 4: License Detection Inconsistency
**What goes wrong:** GPL dependency slips through because license field varies
**Why it happens:** Packages declare licenses differently (metadata vs classifiers)
**How to avoid:** Use `--partial-match` flag with pip-licenses; check both sources with `--from=all`
**Warning signs:** Manual license review finding issues that automated scan missed

### Pitfall 5: Bandit nosec on Multi-line Strings (Python 3.8+)
**What goes wrong:** `# nosec` comment after multi-line string has no effect
**Why it happens:** Known bug in bandit with Python 3.8+ AST changes
**How to avoid:** Place `# nosec` on the line where the vulnerability starts, not the closing line
**Warning signs:** nosec comments that don't suppress warnings

## Code Examples

### Complete Makefile Integration
```makefile
# Source: Research synthesis from official documentation
.PHONY: security security-deps security-code security-secrets security-licenses

security: security-deps security-code security-secrets security-licenses
	@echo "All security checks passed"

security-deps:
	@echo "Scanning dependencies for vulnerabilities..."
	.venv/bin/pip-audit

security-code:
	@echo "Running static security analysis..."
	.venv/bin/bandit -r src/ -c pyproject.toml

security-secrets:
	@echo "Checking for secrets..."
	.venv/bin/detect-secrets scan --baseline .secrets.baseline

security-licenses:
	@echo "Checking license compliance..."
	.venv/bin/pip-licenses --fail-on="GPL;AGPL;LGPL" --partial-match
```

### pyproject.toml Configuration
```toml
# Source: https://bandit.readthedocs.io/en/latest/config.html
[tool.bandit]
exclude_dirs = [".venv", "build", "dist"]
# Strict mode: no skips, all findings block (per CONTEXT.md)
# skips = []  # Explicitly empty - all findings are blocking

# Tests with known nosec suppressions can be documented here
# [tool.bandit.assert_used]
# skips = ["tests/*"]  # Only if tests need assert (they do)
```

### Baseline File Structure (.secrets.baseline)
```json
{
  "version": "1.5.0",
  "plugins_used": [
    {"name": "AWSKeyDetector"},
    {"name": "ArtifactoryDetector"},
    {"name": "AzureStorageKeyDetector"},
    {"name": "BasicAuthDetector"},
    {"name": "PrivateKeyDetector"},
    {"name": "SlackDetector"}
  ],
  "filters_used": [
    {"path": "detect_secrets.filters.allowlist.is_line_allowlisted"},
    {"path": "detect_secrets.filters.heuristic.is_likely_id_string"},
    {"path": "detect_secrets.filters.heuristic.is_potential_uuid"}
  ],
  "results": {},
  "generated_at": "2026-01-24T00:00:00Z"
}
```

### nosec Usage with Justification
```python
# Source: https://github.com/PyCQA/bandit/blob/main/examples/nosec.py
# CORRECT: Specific test IDs with justification
subprocess.Popen(cmd, shell=True)  # nosec B602 - cmd is hardcoded, not user input

# WRONG: Blanket nosec (bad practice)
subprocess.Popen(cmd, shell=True)  # nosec

# CORRECT: For multi-line, put nosec on first line
sql = """  # nosec B608 - parameterized query, no injection
    SELECT * FROM users WHERE id = ?
"""
```

### detect-secrets Inline Allowlisting
```python
# Source: https://github.com/Yelp/detect-secrets
API_KEY = "test-key-for-unit-tests"  # pragma: allowlist secret

# Or for next line
# pragma: allowlist nextline secret
TEST_TOKEN = "fake-token-12345"
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| safety (PyUp) | pip-audit (PyPA) | 2021 | PyPA official tool, no API key needed |
| Manual CVE tracking | Automated scanning in CI | 2020+ | Continuous vulnerability detection |
| grep for secrets | Entropy + pattern detection | 2018+ | detect-secrets reduces false positives |
| Manual license review | Automated --fail-on | 2023+ | CI enforcement of license policy |

**Deprecated/outdated:**
- **safety free tier:** Limited database without API key; pip-audit is fully open
- **bandit INI config:** pyproject.toml is now preferred, INI still supported but legacy

## Open Questions

1. **pip-audit Severity Filtering Workaround**
   - What we know: pip-audit doesn't support CVSS filtering; maintainers reject adding it
   - What's unclear: Whether to accept all-vulnerabilities-block or post-process JSON
   - Recommendation: Use all-vulnerabilities-block (simpler, safer) and document rationale in audit report

2. **Scan Duration for CI Decision**
   - What we know: No benchmarks found in research; wanctl is ~25K lines across 72 files
   - What's unclear: Exact scan times for this codebase
   - Recommendation: Run initial scan, measure duration, decide on `make ci` inclusion based on results (<30s = include, >30s = separate)

3. **Bandit Test Directory Handling**
   - What we know: CONTEXT.md says "all findings block"; tests use assert statements
   - What's unclear: Whether B101 (assert_used) should be skipped for tests/
   - Recommendation: Exclude tests/ from B101 only (assert is idiomatic in pytest), all other rules apply everywhere

## Sources

### Primary (HIGH confidence)
- https://pypi.org/project/pip-audit/ - Version 2.10.0, installation, basic usage
- https://github.com/pypa/pip-audit - CLI options, exit codes, CI patterns
- https://github.com/pypa/pip-audit/issues/654 - Severity filtering status and maintainer position
- https://bandit.readthedocs.io/en/latest/config.html - Configuration, pyproject.toml syntax
- https://bandit.readthedocs.io/en/latest/man/bandit.html - CLI options, severity/confidence levels
- https://github.com/Yelp/detect-secrets - CLI options, baseline format, inline allowlisting
- https://pypi.org/project/pip-licenses/ - Version 5.5.0, --fail-on, --partial-match options
- https://github.com/raimon49/pip-licenses - Full option documentation

### Secondary (MEDIUM confidence)
- https://pypi.org/project/bandit/ - Version 1.9.3, basic features
- https://pypi.org/project/detect-secrets/ - Version 1.5.0, basic usage
- https://pypi.org/project/liccheck/ - Alternative license checker
- https://medium.com/@sparknp1/10-bandit-pip-audit-safeguards-for-secure-python-builds-f4860a1c0771 - CI best practices

### Tertiary (LOW confidence)
- WebSearch results on false positive rates (15% untuned) - needs validation against this codebase
- Scan duration estimates - not found, recommend empirical measurement

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - Official PyPA and PyCQA tools, versions verified via PyPI
- Architecture: HIGH - Patterns from official documentation
- Pitfalls: MEDIUM - Some from community sources, nosec bug verified in GitHub issues

**Research date:** 2026-01-24
**Valid until:** 2026-02-24 (30 days - stable tools, infrequent major changes)
