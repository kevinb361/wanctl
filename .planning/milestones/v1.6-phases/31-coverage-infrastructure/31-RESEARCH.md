# Phase 31: Coverage Infrastructure - Research

**Researched:** 2026-01-24
**Domain:** pytest-cov coverage enforcement and CI integration
**Confidence:** HIGH

## Summary

This phase enforces coverage thresholds in CI using pytest-cov and coverage.py. The project already has pytest-cov 7.0.0 and coverage 7.13.1 installed, with `[tool.coverage.run]` and `[tool.coverage.report]` sections in pyproject.toml. Current coverage is 45.7% statement / 72% branch.

The standard approach is to add `fail_under = 90` to `[tool.coverage.report]` in pyproject.toml, update the Makefile `ci` target to include coverage checking, and update the README badge to show the 90% threshold.

**Primary recommendation:** Add `fail_under = 90` to `[tool.coverage.report]` and add `--cov-fail-under=90` to pytest addopts or Makefile coverage target.

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| pytest-cov | 7.0.0 | Coverage plugin for pytest | Already installed, standard pytest coverage solution |
| coverage.py | 7.13.1 | Underlying coverage measurement | Already installed, pytest-cov dependency |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| shields.io | N/A | Badge generation service | Static badges for README (already in use) |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Static badge | coverage-badge, genbadge | Dynamic generation requires CI workflow; static badge is simpler for this project's needs |
| pyproject.toml config | .coveragerc | pyproject.toml is already in use, no reason to add another file |

**Installation:**
```bash
# Already installed - no new dependencies needed
```

## Architecture Patterns

### Configuration Location

All coverage configuration should be in `pyproject.toml` under `[tool.coverage.*]` sections.

**Current structure (already exists):**
```toml
[tool.coverage.run]
source = ["src", "tests"]
branch = true
parallel = true
relative_files = true

[tool.coverage.report]
show_missing = true
skip_empty = true
precision = 1

[tool.pytest.ini_options]
addopts = "--cov-config=pyproject.toml"
```

### Pattern 1: fail_under in pyproject.toml
**What:** Configure coverage threshold in coverage.py config
**When to use:** Standard approach, works with any coverage invocation
**Example:**
```toml
# Source: https://coverage.readthedocs.io/en/latest/config.html
[tool.coverage.report]
fail_under = 90
```

### Pattern 2: --cov-fail-under in pytest
**What:** Pass threshold via pytest command line
**When to use:** Alternative to pyproject.toml config
**Example:**
```bash
pytest --cov=src --cov-fail-under=90
```

### Pattern 3: Makefile with Coverage Enforcement
**What:** CI target that runs tests with coverage and fails on threshold
**When to use:** Integrating into existing `make ci` workflow
**Example:**
```makefile
# Add --cov and --cov-fail-under to test target or create separate coverage-check target
ci: lint type coverage-check

coverage-check:
	.venv/bin/pytest tests/ --cov=src --cov-report=term-missing --cov-fail-under=90
```

### Anti-Patterns to Avoid
- **Duplicate thresholds:** Don't set fail_under in both pyproject.toml AND command line (pick one)
- **Mixing config files:** Don't create .coveragerc if pyproject.toml already has coverage config
- **Ignoring precision:** If using precision > 0, be aware of rounding issues with fail_under

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Coverage threshold checking | Custom scripts parsing coverage output | `fail_under` config or `--cov-fail-under` | Built-in, tested, handles edge cases |
| Badge generation | Manual shield.io URL construction | Static badge (current approach) | Simple, works, no CI dependency |

**Key insight:** coverage.py already has fail_under built in. No custom solution needed.

## Common Pitfalls

### Pitfall 1: Config File Precedence
**What goes wrong:** Coverage ignores pyproject.toml settings
**Why it happens:** setup.cfg, .coveragerc, or tox.ini exists and takes precedence
**How to avoid:** Verify no conflicting config files exist (none found in this project)
**Warning signs:** Settings in pyproject.toml appear to be ignored

### Pitfall 2: Precision/fail_under Mismatch
**What goes wrong:** Coverage reports 80.16% but fails with threshold of 80.2%
**Why it happens:** fail_under uses raw float, display uses precision rounding
**How to avoid:** Use integer thresholds (90 not 90.5), or set precision = 0
**Warning signs:** "FAIL Required test coverage of X% not reached" when display shows passing

### Pitfall 3: Current Coverage Far Below Threshold
**What goes wrong:** CI immediately starts failing after adding 90% threshold
**Why it happens:** Current coverage is 45.7%, threshold is 90%
**How to avoid:** Either (a) add tests first to reach 90%, or (b) temporarily set lower threshold and ratchet up
**Warning signs:** This project specifically - current coverage is 45.7%

### Pitfall 4: Separate test vs ci Targets
**What goes wrong:** `make test` passes but `make ci` fails (or vice versa)
**Why it happens:** Coverage enforcement only in one target
**How to avoid:** Decide: either both have coverage, or only `ci` enforces
**Warning signs:** Developers confused when local tests pass but CI fails

## Code Examples

### Adding fail_under to pyproject.toml
```toml
# Source: https://coverage.readthedocs.io/en/latest/config.html
[tool.coverage.report]
show_missing = true
skip_empty = true
precision = 1
fail_under = 90
```

### Updating Makefile for CI Integration
```makefile
# Option A: Add coverage to existing test target (changes behavior)
test:
	.venv/bin/pytest tests/ -v --cov=src --cov-report=term-missing --cov-fail-under=90

# Option B: Keep test fast, add separate coverage-check target
test:
	.venv/bin/pytest tests/ -v

coverage-check:
	.venv/bin/pytest tests/ --cov=src --cov-report=term-missing --cov-fail-under=90

ci: lint type coverage-check
```

### Updating README Badge
```markdown
# Current (shows actual 72%)
[![Coverage](https://img.shields.io/badge/coverage-72%25-yellowgreen)](coverage-report/index.html)

# Updated to show 90% threshold (informational)
[![Coverage](https://img.shields.io/badge/coverage-90%25_threshold-brightgreen)](coverage-report/index.html)

# Or show actual coverage with threshold note
[![Coverage](https://img.shields.io/badge/coverage-72%25_(90%25_required)-yellow)](coverage-report/index.html)
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| .coveragerc file | pyproject.toml [tool.coverage.*] | coverage.py 5.0+ | Single config file |
| Post-hoc coverage checks | Built-in fail_under | Always available | No custom scripts needed |

**Deprecated/outdated:**
- `.coveragerc`: Still works but pyproject.toml is preferred for Python projects
- `setup.cfg` for coverage: Deprecated in favor of pyproject.toml

## Open Questions

1. **How to handle 45.7% -> 90% gap?**
   - What we know: Current coverage is 45.7%, target is 90%
   - What's unclear: Does user want immediate enforcement (CI will fail) or gradual ratchet?
   - Recommendation: Requirements say "threshold enforcement", so set fail_under=90 and accept CI will fail until tests are added. The purpose of this phase is infrastructure, not achieving 90%.

2. **Badge format preference?**
   - What we know: Current badge shows actual coverage (72%)
   - What's unclear: Should badge show threshold (90%) or actual coverage?
   - Recommendation: Show threshold (90%) since that's what COV-03 requests ("reflect new threshold")

## Sources

### Primary (HIGH confidence)
- coverage.py official docs - https://coverage.readthedocs.io/en/latest/config.html
- pytest-cov official docs - https://pytest-cov.readthedocs.io/en/latest/config.html
- Project pyproject.toml - `/home/kevin/projects/wanctl/pyproject.toml` (existing config)
- Project Makefile - `/home/kevin/projects/wanctl/Makefile` (existing targets)

### Secondary (MEDIUM confidence)
- [pytest-cov GitHub issue #390](https://github.com/pytest-dev/pytest-cov/issues/390) - pyproject.toml precedence
- [pytest-cov GitHub issue #638](https://github.com/pytest-dev/pytest-cov/issues/638) - precision/fail_under interaction

### Tertiary (LOW confidence)
- None

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - Already installed, verified versions
- Architecture: HIGH - Official docs consulted, patterns are standard
- Pitfalls: HIGH - GitHub issues document known problems

**Research date:** 2026-01-24
**Valid until:** 2026-03-24 (60 days - stable domain, slow-changing tools)
