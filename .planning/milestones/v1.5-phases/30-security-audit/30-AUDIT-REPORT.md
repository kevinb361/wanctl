# Security Audit Report: wanctl v1.4.0

**Audit Date:** 2026-01-24
**Audited By:** Automated security scanning + manual review
**Status:** CLEAN (all scans pass)

## Executive Summary

All security scans pass. No vulnerabilities found in dependencies. Static analysis findings are false positives addressed with configuration. License compliance verified with one acceptable LGPL dependency (paramiko).

### Tool Versions

| Tool           | Version | Purpose                        |
| -------------- | ------- | ------------------------------ |
| pip-audit      | 2.10.0  | Dependency vulnerability scan  |
| bandit         | 1.9.3   | Static security analysis       |
| detect-secrets | 1.5.0   | Secret detection               |
| pip-licenses   | 5.5.0   | License compliance             |

## 1. Dependency Vulnerabilities (SEC-01)

**Result:** No known vulnerabilities found

```
pip-audit scan completed
No known vulnerabilities found

Skipped (not on PyPI):
- cake-qos 0.1.0 (local development package)
- wanctl 1.4.0 (this package)
```

### Runtime Dependencies

| Package  | Version | Status |
| -------- | ------- | ------ |
| paramiko | 4.0.0   | Clean  |
| pexpect  | 4.9.0   | Clean  |
| pyyaml   | 6.0.3   | Clean  |
| requests | 2.32.5  | Clean  |

All transitive dependencies also scanned and clean.

## 2. Static Security Analysis

**Result:** No issues (after addressing false positives)

### Bandit Configuration

The following checks are skipped in `pyproject.toml` as false positives for this codebase:

| Rule | Description | Justification |
| ---- | ----------- | ------------- |
| B101 | assert_used | Asserts used for invariant checks, not user input validation |
| B311 | random | `random.uniform()` used for retry jitter timing, not cryptographic purposes |
| B601 | paramiko_calls | RouterOS API commands from internal code, not user input |

### Additional Inline Suppressions

The following have inline `# nosec` comments with justifications:

- **B110 (try_except_pass):** Shutdown cleanup code where failure is acceptable
- **B404 (subprocess import):** Required for calibration tools (netperf/ping)
- **B603 (subprocess calls):** Commands are hardcoded, not from user input

### Scan Metrics

- Total lines scanned: 9,880
- Issues after configuration: 0
- False positives suppressed: 15

## 3. Secret Detection

**Result:** Clean

The `.secrets.baseline` file was created with `detect-secrets scan`. One false positive was identified and handled:

- **routeros_rest.py docstring:** Example `password="password"` in docstring
  - Marked with `# pragma: allowlist secret`
  - Not an actual secret, just documentation

No actual secrets detected in codebase.

## 4. License Compliance (SEC-02)

**Result:** Compliant

### License Summary

All dependencies use permissive licenses compatible with closed-source use:

| License Type | Count | Examples |
| ------------ | ----- | -------- |
| MIT | 25 | PyYAML, mypy, pytest, ruff |
| Apache-2.0 | 15 | requests, cryptography, bandit |
| BSD | 6 | Pygments, pycparser, idna |
| ISC | 2 | pexpect, ptyprocess |
| MPL-2.0 | 2 | certifi, pathspec |
| PSF-2.0 | 1 | typing_extensions |
| LGPL-2.1 | 1 | paramiko |
| Unlicense | 1 | filelock |

### LGPL-2.1 Assessment (paramiko)

Paramiko is the only LGPL dependency. LGPL-2.1 is a "weak copyleft" license that:
- Allows linking without copyleft effect on the linking program
- Requires users can replace the library with modified version (dynamic linking)
- Does NOT require wanctl to be open-sourced

**Assessment:** Acceptable. wanctl uses paramiko as an unmodified library via standard Python imports. Users can freely replace paramiko if desired.

### Blocked Licenses

The following licenses are blocked and will fail CI if introduced:
- GPL-2.0 (strong copyleft)
- GPL-3.0 (strong copyleft)
- AGPL-3.0 (network copyleft)

## 5. Transitive Dependency Tree (SEC-05)

Full dependency tree from `uv tree`:

```
wanctl v1.4.0
├── paramiko v4.0.0
│   ├── bcrypt v5.0.0
│   ├── cryptography v46.0.3
│   │   └── cffi v2.0.0
│   │       └── pycparser v2.23
│   ├── invoke v2.2.1
│   └── pynacl v1.6.2
│       └── cffi v2.0.0
├── pexpect v4.9.0
│   └── ptyprocess v0.7.0
├── pyyaml v6.0.3
└── requests v2.32.5
    ├── certifi v2026.1.4
    ├── charset-normalizer v3.4.4
    ├── idna v3.11
    └── urllib3 v2.6.3
```

### Analysis

- **Maximum depth:** 4 levels (wanctl -> paramiko -> cryptography -> cffi -> pycparser)
- **Cryptography dependencies:** bcrypt, cryptography, pynacl (all maintained, well-audited)
- **Network dependencies:** requests, urllib3 (standard HTTP library)
- **No concerning patterns:** No abandoned packages, no suspicious sources

## 6. CI Integration (SEC-04)

### Current State

Security scans are available via `make security` but NOT included in `make ci`.

### Timing Analysis

```
make security: ~12.5 seconds total
  - pip-audit: ~3s
  - bandit: ~2s
  - detect-secrets: ~1s
  - pip-licenses: ~6s
```

### Recommendation

Since scan time (12.5s) is well under 30 seconds, security scans COULD be added to CI. However, this was not done during the audit to maintain separation of concerns.

**Suggested usage:**
- Run `make security` before releases
- Add to CI pipeline as a separate job (non-blocking or blocking based on team preference)
- Consider adding to pre-push hook for critical branches

## 7. Findings Summary

| Category | Status | Notes |
| -------- | ------ | ----- |
| CVE Vulnerabilities | CLEAN | No known CVEs in dependencies |
| Static Analysis | CLEAN | False positives addressed via config |
| Secrets | CLEAN | One false positive in docstring |
| License Compliance | CLEAN | LGPL-2.1 (paramiko) acceptable |
| Transitive Dependencies | CLEAN | Well-maintained dependency tree |

## 8. Recommendations

1. **Monitor Dependencies:** Run `pip-audit` periodically or on dependency updates
2. **Maintain Baseline:** Update `.secrets.baseline` when adding code with secret-like strings
3. **Review LGPL:** If paramiko is ever forked/modified, reassess license implications
4. **CI Integration:** Consider adding `make security` to release workflow

## Appendix: Full License Table

| Name                    | Version  | License                              |
|-------------------------|----------|--------------------------------------|
| CacheControl            | 0.14.4   | Apache-2.0                           |
| PyNaCl                  | 1.6.2    | Apache Software License              |
| PyYAML                  | 6.0.3    | MIT License                          |
| Pygments                | 2.19.2   | BSD License                          |
| bandit                  | 1.9.3    | Apache-2.0                           |
| bcrypt                  | 5.0.0    | Apache Software License              |
| boolean.py              | 5.0      | BSD-2-Clause                         |
| certifi                 | 2026.1.4 | Mozilla Public License 2.0 (MPL 2.0) |
| cffi                    | 2.0.0    | MIT                                  |
| charset-normalizer      | 3.4.4    | MIT                                  |
| coverage                | 7.13.1   | Apache-2.0                           |
| cryptography            | 46.0.3   | Apache-2.0 OR BSD-3-Clause           |
| cyclonedx-python-lib    | 11.6.0   | Apache Software License              |
| defusedxml              | 0.7.1    | Python Software Foundation License   |
| detect-secrets          | 1.5.0    | Apache Software License              |
| filelock                | 3.20.3   | Unlicense                            |
| idna                    | 3.11     | BSD-3-Clause                         |
| iniconfig               | 2.3.0    | MIT                                  |
| invoke                  | 2.2.1    | BSD License                          |
| librt                   | 0.7.8    | MIT License                          |
| license-expression      | 30.4.4   | Apache-2.0                           |
| markdown-it-py          | 4.0.0    | MIT License                          |
| mdurl                   | 0.1.2    | MIT License                          |
| msgpack                 | 1.1.2    | Apache-2.0                           |
| mypy                    | 1.19.1   | MIT License                          |
| mypy_extensions         | 1.1.0    | MIT                                  |
| packageurl-python       | 0.17.6   | MIT License                          |
| packaging               | 25.0     | Apache Software License; BSD License |
| paramiko                | 4.0.0    | LGPL-2.1                             |
| pathspec                | 1.0.3    | Mozilla Public License 2.0 (MPL 2.0) |
| pexpect                 | 4.9.0    | ISC License (ISCL)                   |
| pip-api                 | 0.0.34   | Apache Software License              |
| pip-requirements-parser | 32.0.1   | MIT                                  |
| pip_audit               | 2.10.0   | Apache Software License              |
| platformdirs            | 4.5.1    | MIT                                  |
| pluggy                  | 1.6.0    | MIT License                          |
| ptyprocess              | 0.7.0    | ISC License (ISCL)                   |
| py-serializable         | 2.1.0    | Apache Software License              |
| pycparser               | 2.23     | BSD License                          |
| pyflakes                | 3.4.0    | MIT License                          |
| pyparsing               | 3.3.2    | MIT                                  |
| pytest                  | 9.0.2    | MIT                                  |
| pytest-cov              | 7.0.0    | MIT                                  |
| requests                | 2.32.5   | Apache Software License              |
| rich                    | 14.2.0   | MIT License                          |
| ruff                    | 0.14.10  | MIT License                          |
| sortedcontainers        | 2.4.0    | Apache Software License              |
| stevedore               | 5.6.0    | Apache Software License              |
| tomli                   | 2.4.0    | MIT                                  |
| tomli_w                 | 1.2.0    | MIT License                          |
| typing_extensions       | 4.15.0   | PSF-2.0                              |
| urllib3                 | 2.6.3    | MIT                                  |
