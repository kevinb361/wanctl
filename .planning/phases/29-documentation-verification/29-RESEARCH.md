# Phase 29: Documentation Verification - Research

**Researched:** 2026-01-24
**Domain:** Documentation audit and verification for Python project
**Confidence:** HIGH

## Summary

This phase involves auditing and verifying documentation accuracy for the wanctl project. The scope includes CLAUDE.md, README.md, CHANGELOG.md, and 22 files in docs/. The primary challenge is **version number inconsistency** - the project has multiple version strings in different locations that do not match the target 1.4.0.

Key findings:
- Version strings are scattered across 10+ files with inconsistent values
- Two config schema documents exist (CONFIG_SCHEMA.md and CONFIGURATION.md) with overlapping content
- Several docs reference outdated version numbers (1.0.0-rc7, 1.1.0, etc.)
- ARCHITECTURE.md in docs/ is actually titled "Portable Controller Architecture" which may cause confusion
- Code examples in docs can be verified by grep/syntax-check without full runtime execution

**Primary recommendation:** Start with version number audit (highest risk of visible errors), then verify config docs against actual validation code, then audit remaining architecture/feature docs.

## Standard Stack

This phase requires no external libraries. All verification uses:

### Core
| Tool | Purpose | Why Standard |
|------|---------|--------------|
| grep/Grep | Find version strings, config references | Built-in, fast pattern matching |
| Read tool | Examine file contents | Direct content access |
| Python AST | Verify code examples are syntactically valid | Standard library, no runtime needed |

### Supporting
| Tool | Purpose | When to Use |
|------|---------|-------------|
| diff | Compare doc claims vs code behavior | When discrepancy found |
| git log | Trace when docs became stale | Understand drift timeline |

## Architecture Patterns

### Recommended Audit Structure

```
Audit Phase Order:
1. Version numbers (HIGH risk, quick wins)
   - pyproject.toml
   - src/wanctl/__init__.py
   - CLAUDE.md, README.md
   - scripts/*.sh
   - docs/*.md

2. Config documentation (HIGH value)
   - CONFIG_SCHEMA.md vs config_validation_utils.py
   - CONFIGURATION.md vs config_base.py
   - Example YAML files vs actual validation

3. CLI examples (MEDIUM risk)
   - README.md CLI commands
   - QUICKSTART.md commands
   - DEPLOYMENT.md commands

4. Architecture claims (MEDIUM risk)
   - ARCHITECTURE.md (Portable Controller)
   - State machine descriptions
   - Component interactions

5. Feature-specific docs (LOWER risk)
   - STEERING.md
   - TRANSPORT_COMPARISON.md
   - SECURITY.md
```

### Pattern: Batch-Then-Fix

**What:** Collect all discrepancies first, then fix in organized batches
**When to use:** Full documentation audit (as specified in CONTEXT.md)
**Example:**

```markdown
## AUDIT-REPORT.md structure

### Version Discrepancies
| File | Current | Expected | Line |
|------|---------|----------|------|
| pyproject.toml | 1.0.0-rc7 | 1.4.0 | 3 |

### Config Discrepancies
...

### Command/Example Issues
...
```

### Anti-Patterns to Avoid

- **Fix-as-you-go:** Leads to incomplete audit, missed issues
- **Ignoring context:** "Version 1.0.0" in CHANGELOG history is correct, "Current: 1.0.0" is not
- **Skipping code verification:** Claims about config validation MUST be verified against actual code

## Don't Hand-Roll

Problems that have established solutions:

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Version string extraction | Custom regex | `grep -n 'version\|VERSION\|__version__'` | Standard pattern |
| Python syntax check | Custom parser | `python -m py_compile` or AST | Catches syntax errors without execution |
| YAML validation | Custom validator | Load with PyYAML, check for errors | Standard library |
| Markdown link checking | Custom crawler | Focus on code accuracy first | Links are lower priority |

## Common Pitfalls

### Pitfall 1: Version Context Blindness
**What goes wrong:** Changing version numbers in historical context (CHANGELOG, "as of v1.0.0")
**Why it happens:** Automated find-replace without reading surrounding context
**How to avoid:** Review each version occurrence in context
**Warning signs:** Version number appears in past-tense section

### Pitfall 2: Config Schema Drift
**What goes wrong:** CONFIG_SCHEMA.md and CONFIGURATION.md diverge from actual validation
**Why it happens:** Code updated, docs not updated
**How to avoid:** Trace doc claims to specific validation functions
**Warning signs:** Doc mentions field not found in config_validation_utils.py

### Pitfall 3: Example Config Staleness
**What goes wrong:** Example YAML files use old field names/values
**Why it happens:** Examples not tested after schema changes
**How to avoid:** Load examples with actual config parser
**Warning signs:** Example uses deprecated field

### Pitfall 4: Docstring/Comment Drift
**What goes wrong:** Inline comments describe old behavior
**Why it happens:** Comments updated less often than code
**How to avoid:** Cross-reference comment claims with actual behavior
**Warning signs:** Comment says "must be X" but code allows other values

### Pitfall 5: Duplicate Documentation Confusion
**What goes wrong:** Two docs describe same thing differently
**Why it happens:** CONFIG_SCHEMA.md and CONFIGURATION.md both exist
**How to avoid:** Consolidate or clearly differentiate purpose
**Warning signs:** Same config field documented differently in two places

## Code Examples

### Verified Version Locations (from codebase scan)

```python
# PRIMARY version source (canonical)
# src/wanctl/__init__.py:3
__version__ = "1.4.0"  # Currently correct

# SECONDARY version (needs update)
# pyproject.toml:3
version = "1.0.0-rc7"  # STALE - needs 1.4.0

# TERTIARY versions (various docs/scripts)
# scripts/install.sh:20
VERSION="1.0.0-rc5"  # STALE

# scripts/validate-deployment.sh:21
VERSION="1.0.0"  # STALE

# README.md:271 (health endpoint example)
"version": "1.0.0-rc7"  # STALE

# CLAUDE.md:10
**Version:** 1.1.0  # STALE
```

### Config Validation Cross-Reference Pattern

```python
# To verify CONFIG_SCHEMA.md claims, check these files:

# 1. Base validation
# src/wanctl/config_base.py
#   - ConfigValidationError class
#   - CURRENT_SCHEMA_VERSION = "1.0"
#   - Required field patterns

# 2. Specific validators
# src/wanctl/config_validation_utils.py
#   - validate_bandwidth_order()
#   - validate_threshold_order()
#   - validate_alpha()
#   - validate_baseline_rtt()
#   - Default bounds: MIN_SANE_BASELINE_RTT = 10, MAX_SANE_BASELINE_RTT = 60

# Cross-reference: Does CONFIG_SCHEMA.md document these bounds?
```

### CLI Command Verification Pattern

```bash
# Verify documented commands exist
# Check entrypoints in pyproject.toml:14-17
[project.scripts]
wanctl = "wanctl.autorate_continuous:main"
wanctl-calibrate = "wanctl.calibrate:main"
wanctl-steering = "wanctl.steering.daemon:main"

# Documented: wanctl --config X --validate-config
# Verify: grep for 'validate-config' in autorate_continuous.py
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Single CONFIG.md | Split CONFIG_SCHEMA.md + CONFIGURATION.md | Unknown | Potential duplication |
| SSH-only transport | REST API + SSH | v1.0.0-rc4 | Check docs mention both |
| 3-state model | 4-state model (SOFT_RED) | v4.x | Verify all state refs updated |
| 2s cycle interval | 50ms cycle interval | v1.1.0 | Some docs may reference old timing |

**Deprecated/outdated patterns found:**
- `floor_mbps` (legacy single floor) - still documented for backward compat
- 2-second cycle interval - mentioned in some test logs
- SSH transport as primary - now REST is recommended

## Known Version Discrepancies (Pre-Audit)

**CRITICAL:** These were discovered during research and must be fixed:

| File | Current Value | Should Be | Notes |
|------|---------------|-----------|-------|
| `pyproject.toml` | 1.0.0-rc7 | 1.4.0 | Package version |
| `CLAUDE.md` | 1.1.0 | 1.4.0 | Multiple references |
| `README.md` | 1.0.0-rc7 | 1.4.0 | Health endpoint example |
| `scripts/install.sh` | 1.0.0-rc5 | 1.4.0 | VERSION variable |
| `scripts/validate-deployment.sh` | 1.0.0 | 1.4.0 | VERSION variable |
| `docs/FALLBACK_CHECKS_IMPLEMENTATION.md` | 1.0.0-rc8 | 1.4.0 | Document header |
| `docs/TRANSPORT_COMPARISON.md` | 4.6 | Remove or update | Footer version |

**NOTE:** `src/wanctl/__init__.py` already has `__version__ = "1.4.0"` (correct)

## Document Inventory

### Root Level (3 files)
- CLAUDE.md - Project instructions, version refs
- README.md - Public docs, CLI examples, version in health example
- CHANGELOG.md - Version history (structure only, per CONTEXT.md)

### docs/ Directory (22 files)

**Config-related (verify against code):**
- CONFIG_SCHEMA.md - Full schema reference
- CONFIGURATION.md - Shorter config reference (potential duplicate)

**Architecture (verify claims):**
- ARCHITECTURE.md - "Portable Controller Architecture" (filename misleading?)

**Features (verify accuracy):**
- STEERING.md - Multi-WAN steering
- TRANSPORT_COMPARISON.md - REST vs SSH
- SECURITY.md - SSH host key validation

**Deployment/Operations:**
- QUICKSTART.md - First-time setup
- DEPLOYMENT.md - Production deployment
- UPGRADING.md - Version upgrade guide
- DOCKER.md - Container deployment
- CALIBRATION.md - Calibration wizard

**Technical Deep-Dives:**
- CORE-ALGORITHM-ANALYSIS.md - Algorithm details
- PRODUCTION_INTERVAL.md - 50ms interval analysis
- PROFILING.md - Performance profiling
- EF_QUEUE_PROTECTION.md - Queue protection
- FALLBACK_CONNECTIVITY_CHECKS.md - Connectivity fallback
- FALLBACK_CHECKS_IMPLEMENTATION.md - Implementation details

**Historical/Testing:**
- INTERVAL_TESTING_50MS.md - 50ms testing results
- INTERVAL_TESTING_250MS.md - 250ms testing results
- FASTER_RESPONSE_INTERVAL.md - Interval analysis
- SPECTRUM_WATCHDOG_RESTARTS.md - Issue documentation
- STEERING_CONFIG_MISMATCH_ISSUE.md - Bug documentation

## Open Questions

1. **CONFIG_SCHEMA.md vs CONFIGURATION.md**
   - What we know: Both describe config schema
   - What's unclear: Which is canonical, should one be deprecated
   - Recommendation: Audit both, note differences, recommend consolidation if significant

2. **docs/ARCHITECTURE.md naming**
   - What we know: File is titled "Portable Controller Architecture"
   - What's unclear: Is there a missing "ARCHITECTURE.md" covering full system?
   - Recommendation: Rename to PORTABLE_CONTROLLER_ARCHITECTURE.md for clarity

3. **Historical docs in docs/**
   - What we know: Several docs document past issues/testing
   - What's unclear: Should these move to docs/archive/ or stay?
   - Recommendation: Leave as-is per CONTEXT.md (deprecated features move to archive section)

## Sources

### Primary (HIGH confidence)
- Source code: `src/wanctl/__init__.py`, `config_base.py`, `config_validation_utils.py`
- Project files: `pyproject.toml`
- Git grep for version patterns

### Secondary (MEDIUM confidence)
- CONTEXT.md decisions from user discussion

### Tertiary (N/A)
- No external sources needed for this phase

## Metadata

**Confidence breakdown:**
- Version locations: HIGH - direct code inspection
- Config validation behavior: HIGH - read actual validators
- Document inventory: HIGH - glob of actual files
- Pitfalls: MEDIUM - based on common patterns

**Research date:** 2026-01-24
**Valid until:** Indefinite (internal codebase audit)
