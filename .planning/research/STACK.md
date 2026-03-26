# Stack Research: v1.22 Full System Audit

**Domain:** Audit tooling for a production Python 3.12 network controller (28,629 LOC, 3,723 tests)
**Researched:** 2026-03-26
**Confidence:** HIGH (all tools verified against PyPI, existing toolchain well-understood)

## Existing Toolchain (Already Installed)

Before recommending additions, here is what the project already runs and what each catches:

| Tool | Version | Purpose | What It Catches |
|------|---------|---------|-----------------|
| ruff | 0.14.10 | Linting + formatting | Pyflakes, pycodestyle, isort, bugbear, pyupgrade (E/W/F/I/B/UP rules only) |
| mypy | 1.19.1 | Type checking | Type errors, but with `disallow_untyped_defs = false` and `ignore_missing_imports = true` -- permissive |
| pytest + pytest-cov | 9.0.2 / 7.0.0 | Testing + coverage | 91%+ statement coverage, branch coverage enabled, fail_under=90 |
| bandit | 1.9.3 | Security SAST | Python-specific security issues (skips B101/B311/B601 intentionally) |
| pip-audit | 2.10.0 | Dependency CVEs | Known vulnerabilities in installed packages via OSV database |
| detect-secrets | 1.5.0 | Secret detection | Hardcoded secrets in source files |
| pip-licenses | 5.5.0 | License compliance | GPL/AGPL license violations in dependencies |
| pyflakes | 3.4.0 | Unused imports/vars | Redundant with ruff F rules -- can be removed |

### Gaps in Current Toolchain

The existing tools leave these audit dimensions uncovered:

1. **Dead code** -- ruff F841 catches unused variables, but not unused functions, classes, methods, or unreachable code paths
2. **Code complexity** -- no cyclomatic or cognitive complexity measurement (C901 not enabled in ruff)
3. **Unused dependencies** -- pip-audit checks for CVEs, not for dependencies declared but never imported
4. **Architectural boundaries** -- nothing enforces that e.g. `steering/` never imports from `dashboard/`
5. **Test quality** -- coverage measures execution, not assertion quality (dead assertions, weak tests)
6. **Deeper type safety** -- mypy runs permissive; untyped defs are allowed silently
7. **Simplification opportunities** -- ruff SIM/PERF/RET/TRY rules not enabled
8. **Unused test fixtures** -- 3,723 tests likely have accumulated dead fixtures

## Recommended Audit Additions

### Tier 1: Enable for Audit (Zero Install -- Ruff Rule Expansion)

These are free -- just config changes to the existing ruff installation.

| Rule Set | Prefix | What It Catches That Current Config Misses |
|----------|--------|-------------------------------------------|
| McCabe complexity | C901 | Functions exceeding cyclomatic complexity threshold (default 10) |
| Simplify | SIM | Unnecessarily complex boolean logic, redundant if/else, mergeable isinstance calls |
| Performance | PERF | Unnecessary list() calls in iterations, avoidable dict.items() when only keys needed |
| Return patterns | RET | Superfluous else after return, unnecessary return None, assignment-then-return |
| Pytest style | PT | Inconsistent fixture scope, missing parametrize, raw assert messages |
| Exception handling | TRY | Bare except, overly broad exception types, reraise without cause |
| Unused arguments | ARG | Function parameters that are never used in the body |
| Commented-out code | ERA | Dead commented-out code blocks left in source |
| Private access | SLF | External access to _private members across module boundaries |
| Pathlib migration | PTH | os.path usage that should be pathlib (lower priority for a network controller) |

**Configuration change in pyproject.toml:**

```toml
[tool.ruff.lint]
select = [
    "E", "W", "F", "I", "B", "UP",  # existing
    "C901",   # complexity
    "SIM",    # simplification
    "PERF",   # performance
    "RET",    # return patterns
    "PT",     # pytest style
    "TRY",    # exception handling
    "ARG",    # unused arguments
    "ERA",    # commented-out code
    "SLF",    # private member access
]

[tool.ruff.lint.mccabe]
max-complexity = 15  # start permissive for audit, tighten later
```

**Why these and not others:** SIM/PERF/RET catch real code quality issues in a 28K LOC codebase. PT matters with 3,723 tests. ARG/ERA catch dead code that vulture might miss (and vice versa). C901 gives complexity baselines. Skipped: ANN (type annotations better handled by mypy strictness), D (docstrings are a style choice, not an audit finding), N (naming conventions are already consistent).

### Tier 2: Install for Audit (One-Shot Tools)

| Tool | Version | Purpose | What It Catches Beyond Existing Tools | Install |
|------|---------|---------|---------------------------------------|---------|
| vulture | 2.16 | Dead code detection | Unused functions, classes, methods, variables, unreachable code after return/break/raise. Assigns confidence scores (60-100%). Catches what ruff F rules miss: dead functions, dead class methods, unused module-level names. | `uv pip install vulture` |
| radon | 6.0.1 | Code metrics | Cyclomatic complexity (per-function), Maintainability Index (per-file), Halstead metrics, raw SLOC. Produces ranked reports sorted by complexity -- directly actionable for refactoring prioritization. | `uv pip install radon` |
| complexipy | 5.2.0 | Cognitive complexity | Cognitive complexity (how hard code is to *understand*, not just branch count). Better than cyclomatic for identifying genuinely confusing functions. Written in Rust, fast on large codebases. | `uv pip install complexipy` |
| deptry | 0.25.1 | Dependency hygiene | Missing imports (imported but not declared), unused dependencies (declared but not imported), transitive deps used directly. Understands pyproject.toml natively. | `uv pip install deptry` |
| pytest-deadfixtures | 2.2.1 | Fixture cleanup | Unused or duplicated pytest fixtures. Static analysis mode (no test execution needed). After 21 milestones and 3,723 tests, fixture rot is near-certain. | `uv pip install pytest-deadfixtures` |

### Tier 3: Consider for Audit (Higher Investment)

| Tool | Version | Purpose | Value vs. Cost Assessment |
|------|---------|---------|--------------------------|
| import-linter | 2.11 | Architectural boundaries | Enforces that steering/ does not import dashboard/, that backends/ does not import from controllers. HIGH value for a 28K LOC project, but requires writing contract definitions first. Recommend for post-audit enforcement, not the audit itself. |
| semgrep (CE) | 1.156.0 | Deep SAST | Cross-function dataflow analysis beyond bandit. 3,000+ community rules. Catches taint propagation, SSRF patterns, injection in paramiko/requests usage. Install via pipx (large dependency tree, do NOT put in project venv). |
| mutmut | 3.2.0 | Mutation testing | Tests whether tests actually verify behavior, not just execute code. A 91% coverage score with weak assertions is worse than 70% with strong ones. HIGH value but SLOW (hours for 28K LOC). Run on critical modules only. |

### What NOT to Install

| Tool | Why Skip |
|------|----------|
| pylint | Ruff covers 95%+ of pylint rules with 100x speed. Adding pylint introduces massive config overhead and conflicting opinions for near-zero incremental value. |
| pyflakes (standalone) | Already installed but redundant -- ruff F rules are pyflakes. Remove from dev dependencies. |
| flake8 + plugins | Ruff replaces the entire flake8 ecosystem. Do not add flake8-cognitive-complexity; use complexipy instead. |
| prospector | Aggregator of tools you already have. Adds indirection without value. |
| SonarQube | Server-based platform overkill for a single-maintainer project. The individual tools above cover the same ground. |
| safety (PyUp) | pip-audit already covers the same CVE databases. Safety's free tier database is updated less frequently. Redundant. |
| wily | Tracks complexity over time via git history. Interesting but not needed for a one-shot audit -- radon gives the current snapshot, which is what matters. |

## MyPy Strictness Progression

The current mypy config is permissive. For the audit, tighten incrementally:

**Current (permissive):**
```toml
[tool.mypy]
disallow_untyped_defs = false    # allows functions without type hints
ignore_missing_imports = true     # silently ignores unresolvable imports
check_untyped_defs = true         # good -- checks bodies of untyped functions
```

**Audit phase (probe for gaps):**
```toml
[tool.mypy]
disallow_untyped_defs = true      # shows every untyped function
warn_return_any = true            # flags Any leaking through returns
no_implicit_optional = true       # requires explicit Optional[X] instead of X = None
disallow_incomplete_defs = true   # catches partially-typed functions
```

**Why not `--strict`:** Strict mode enables ~15 flags at once. For a 28K LOC codebase, that produces thousands of errors making triage impossible. Enable flags one at a time, measure the delta, and decide which are worth fixing vs. suppressing.

**Approach:** Run `mypy --disallow-untyped-defs src/wanctl/ 2>&1 | wc -l` first to gauge the scope. If under 200 errors, fix them. If over 500, focus on critical modules (wan_controller_state.py, state_manager.py, autorate_continuous.py).

## Installation

```bash
# Tier 1: Zero install -- config change only
# Edit pyproject.toml [tool.ruff.lint] select list

# Tier 2: One-shot audit tools (install into project venv)
uv pip install vulture radon complexipy deptry pytest-deadfixtures

# Tier 3: If pursuing deeper analysis
pipx install semgrep           # global, NOT in project venv (huge dep tree)
uv pip install import-linter   # if writing architectural contracts
uv pip install mutmut          # if testing critical module assertion quality
```

## Audit Execution Commands

### Complexity Analysis
```bash
# Cyclomatic complexity -- functions ranked worst-first
.venv/bin/radon cc src/wanctl/ -a -s -n C    # show C and worse (>10)

# Cognitive complexity -- all functions over threshold
.venv/bin/complexipy src/wanctl/ --max-cognitive-complexity 15

# Maintainability index -- files ranked worst-first
.venv/bin/radon mi src/wanctl/ -s -n B       # show B and worse
```

### Dead Code Detection
```bash
# Dead code (functions, classes, methods, unreachable)
.venv/bin/vulture src/wanctl/ --min-confidence 80

# Commented-out code (via ruff, after config change)
.venv/bin/ruff check src/ --select ERA

# Unused fixtures
.venv/bin/pytest --dead-fixtures tests/
```

### Dependency Hygiene
```bash
# Unused/missing/transitive dependency check
.venv/bin/deptry src/

# Existing CVE scan (already in Makefile)
.venv/bin/pip-audit
```

### Extended Linting (after ruff config expansion)
```bash
# Full expanded ruleset
.venv/bin/ruff check src/ tests/

# Complexity gate
.venv/bin/ruff check src/ --select C901
```

### Type Safety Probe
```bash
# Count untyped function definitions
.venv/bin/mypy src/wanctl/ --disallow-untyped-defs 2>&1 | tail -1

# Probe for Any leakage
.venv/bin/mypy src/wanctl/ --warn-return-any 2>&1 | tail -1
```

### Security (Deeper)
```bash
# Semgrep community rules (if installed)
semgrep scan --config auto src/wanctl/

# Existing bandit (already in Makefile)
.venv/bin/bandit -r src/ -c pyproject.toml
```

## Alternatives Considered

| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|-------------------------|
| vulture (dead code) | ruff ERA + F841 | ERA catches commented-out code; F841 catches unused variables. Use vulture when you need dead *functions/classes/methods* -- ruff cannot detect those. |
| radon (cyclomatic) | ruff C901 | C901 flags violations inline. Use radon when you need a ranked report of ALL function complexities for audit triage. Both are complementary. |
| complexipy (cognitive) | flake8-cognitive-complexity | complexipy is Rust-native, actively maintained, standalone. flake8-cognitive-complexity is inactive, depends on flake8 (which you do not use). |
| deptry (dep hygiene) | manual grep of imports | deptry understands pyproject.toml, handles re-exports and conditional imports. Manual grep misses transitive deps and false-positives on dev deps. |
| pip-audit (CVEs) | safety | pip-audit uses OSV (Google-backed, real-time). Safety free tier updates monthly. pip-audit is already installed. |

## Version Compatibility

| Package | Compatible With | Notes |
|---------|-----------------|-------|
| vulture 2.16 | Python 3.8-3.13 | No external dependencies |
| radon 6.0.1 | Python 3.8-3.12 | Verify 3.12 compat -- last release was ~12 months ago |
| complexipy 5.2.0 | Python 3.8-3.13 | Rust binary wheel, no Python dep conflicts |
| deptry 0.25.1 | Python 3.12+ | Rust core, reads pyproject.toml natively |
| pytest-deadfixtures 2.2.1 | pytest 7+ | Lightweight plugin, no conflicts |
| import-linter 2.11 | Python 3.8-3.13 | Depends on grimp for import analysis |
| semgrep 1.156.0 | Python 3.8+ | Large dep tree -- install via pipx, not project venv |

## Tool-to-Audit-Dimension Mapping

This shows which tools address which audit dimensions:

| Audit Dimension | Primary Tool | Supporting Tool | Already Have? |
|-----------------|-------------|-----------------|---------------|
| Dead code (functions/classes) | vulture | ruff ERA/F841 | No / Partial |
| Dead code (commented-out) | ruff ERA | vulture | No (rule not enabled) |
| Cyclomatic complexity | radon | ruff C901 | No |
| Cognitive complexity | complexipy | -- | No |
| Unused dependencies | deptry | -- | No |
| Missing dependencies | deptry | -- | No |
| Transitive dep leaks | deptry | -- | No |
| Dependency CVEs | pip-audit | -- | YES |
| Security SAST | bandit | semgrep (optional) | YES / No |
| Secret detection | detect-secrets | -- | YES |
| License compliance | pip-licenses | -- | YES |
| Type safety gaps | mypy (stricter config) | -- | Partial (permissive config) |
| Code simplification | ruff SIM | -- | No (rule not enabled) |
| Performance patterns | ruff PERF | -- | No (rule not enabled) |
| Return patterns | ruff RET | -- | No (rule not enabled) |
| Exception handling | ruff TRY | -- | No (rule not enabled) |
| Pytest style | ruff PT | -- | No (rule not enabled) |
| Unused arguments | ruff ARG | -- | No (rule not enabled) |
| Unused fixtures | pytest-deadfixtures | -- | No |
| Architectural boundaries | import-linter | -- | No |
| Test assertion quality | mutmut | -- | No |

## Sources

- [Ruff rules documentation](https://docs.astral.sh/ruff/rules/) -- full rule catalog verified 2026-03-26
- [Vulture GitHub](https://github.com/jendrikseipp/vulture) -- v2.16 confirmed via PyPI
- [Radon documentation](https://radon.readthedocs.io/en/latest/) -- v6.0.1, last release ~12 months ago
- [complexipy GitHub](https://github.com/rohaquinlop/complexipy) -- v5.2.0, Rust-based cognitive complexity
- [deptry documentation](https://deptry.com/) -- v0.25.1, actively maintained
- [import-linter documentation](https://import-linter.readthedocs.io/en/stable/) -- v2.11
- [Semgrep Community Edition](https://semgrep.dev/products/community-edition/) -- v1.156.0, LGPL-2.1
- [mutmut documentation](https://mutmut.readthedocs.io/en/latest/) -- mutation testing for Python
- [mypy command line docs](https://mypy.readthedocs.io/en/stable/command_line.html) -- strict mode flags
- PyPI version checks performed locally via `pip index versions` on 2026-03-26

---
*Stack research for: v1.22 Full System Audit*
*Researched: 2026-03-26*
