---
created: 2026-01-23T21:18
title: Dependency security audit
area: security
files:
  - pyproject.toml
  - uv.lock
---

## Problem

Production system uses external dependencies (paramiko, requests, pyyaml, pexpect). Need to verify:

- No known CVEs in current versions
- Dependencies are from trusted sources
- Transitive dependencies are also secure

## Solution

1. Run `pip-audit` or `safety check` against current environment
2. Review any findings and update if needed
3. Consider adding security scanning to CI pipeline
4. Document acceptable risk for any unfixable issues
