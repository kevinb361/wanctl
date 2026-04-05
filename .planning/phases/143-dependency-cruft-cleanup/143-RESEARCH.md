# Phase 143: Dependency & Cruft Cleanup - Research

**Researched:** 2026-04-05
**Domain:** Python dependency auditing, config key cross-referencing, docstring staleness
**Confidence:** HIGH

## Summary

Phase 143 addresses DEAD-03 (unused pip dependencies) and DEAD-04 (stale annotations, dead config references, outdated comments). The dependency audit is straightforward -- all 8 runtime dependencies are actively imported in `src/wanctl/`. The real substance is the config key audit, where I found significant gaps between what the code reads and what's documented in example files and `KNOWN_AUTORATE_PATHS`.

Key findings: (1) zero unused pip dependencies -- all 5 core and 3 optional are imported; (2) zero TODO/FIXME/HACK comments in src/ or tests/; (3) significant config key drift -- at least 6 top-level sections loaded by code (`irtt`, `reflector_quality`, `owd_asymmetry`, `fusion`, `tuning`, `ping_source_ip`) are missing from `KNOWN_AUTORATE_PATHS` in check_config.py; (4) example files contain stale key names (`duration_ms` should be `duration_sec`, `packet_size` never read, deprecated `alpha_baseline`/`alpha_load` in 4 of 6 examples); (5) `docs/CONFIG_SCHEMA.md` lacks `storage.retention` sub-keys, `owd_asymmetry`, `fusion.healing`, and `ping_source_ip`.

**Primary recommendation:** Structure work as three plans: (1) dependency audit + `make check-deps` target, (2) config key cross-reference audit + fixes, (3) docstring/comment staleness audit + doc sync.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** Manual grep for each package's import name across src/wanctl/. All 8 packages audited: 5 core (requests, pyyaml, paramiko, tabulate, icmplib) + 3 optional (textual, httpx, pyroute2)
- **D-02:** If a dependency has no matching imports, remove from pyproject.toml. No stdlib replacement needed -- nothing uses it
- **D-03:** Add `make check-deps` Makefile target -- inline shell grep loop mapping pip name to import name, exit non-zero with list on unused deps. Comment block in Makefile documents pip-to-import name mapping
- **D-04:** Add `make check-deps` to `make ci` pipeline for ongoing enforcement (consistent with Phase 142's `make dead-code`)
- **D-05:** Skip dev/test dependencies (pytest, ruff, mypy, vulture). Scope is runtime deps in [dependencies] and [optional-dependencies] only
- **D-06:** Leave version pins as-is (>=minimum). Pin strategy changes are out of scope
- **D-07:** Scope is src/ only -- no scripts/ directory. No separate audit findings document
- **D-08:** Keep ALL deprecated config translation code -- backward compatibility is a feature
- **D-09:** Add deprecated translation functions to vulture_whitelist.py to prevent false positives
- **D-10:** Verify deprecated-to-new translations actually match current config schema. Fix dead translations
- **D-11:** Fix deprecated translation bugs if found (factual bugs are in scope)
- **D-12:** Deprecated warnings stay as warnings indefinitely
- **D-13:** No refactoring of deprecated param functions, no changes to wanctl-check-config CLI output
- **D-14:** Code comments in check_config.py are sufficient for deprecated key documentation
- **D-15:** Manual bidirectional cross-reference: extract all keys from configs/examples/*.yaml.example, grep each in src/. Extract all config reads from code, check they exist in examples
- **D-16:** configs/examples/*.yaml.example (5 files: cable, dsl, fiber, steering, wan1) are the source of truth for config keys
- **D-17:** Audit at full nesting depth (e.g., thresholds.download.target_bloat_ms), not just top-level sections
- **D-18:** Dead keys in examples: remove entirely (including stale commented-out keys)
- **D-19:** Undocumented keys read by code: add to examples with sensible defaults
- **D-20:** Manual review for dynamic config access patterns (f-strings, getattr, **kwargs)
- **D-21:** Separate audit for steering config vs autorate config -- different code paths
- **D-22:** Sync docs/CONFIG_SCHEMA.md with audit findings (remove dead keys, add undocumented ones)
- **D-23:** One-time audit only -- no ongoing enforcement mechanism for config key drift
- **D-24:** Audit and strip deprecated key names from example files -- examples should show current names only
- **D-25:** Manual audit of most-changed modules: autorate_continuous.py, check_config.py, health_check.py, wan_controller_state.py, backends/
- **D-26:** Fix factually wrong content only -- don't rewrite mediocre docstrings
- **D-27:** Stale inline comments (non-docstring) are also in scope
- **D-28:** Correct stale docstrings, don't remove them
- **D-29:** Leave version references in docstrings (e.g., "Added in v1.12")
- **D-30:** src/wanctl/ only for docstring audit -- test file docstrings are Phase 146/148 scope
- **D-31:** Quick scan of docs/*.md files for stale references to removed modules/config keys

### Claude's Discretion
- Exact grep patterns for pip-to-import name mapping
- Order of commit categories (deps first vs config first vs interleaved)
- Which additional modules beyond the priority list to audit for stale docstrings
- Whether to group config key findings by file or by config section

### Deferred Ideas (OUT OF SCOPE)
- CI integration beyond Makefile (GitHub Actions, pre-commit hooks)
- Dep consolidation / stdlib replacement for single-use deps
- Automated config schema validation tool
- Test file docstring cleanup -- Phase 146/148 scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| DEAD-03 | Unused pip dependencies are identified and removed from pyproject.toml | All 8 runtime deps verified as imported. `make check-deps` pattern established. Pip-to-import name mapping documented |
| DEAD-04 | Stale TODO comments, outdated docstrings, and dead config references are cleaned up | Zero TODOs found. Config key audit identifies ~15 gaps (dead keys in examples, missing keys in KNOWN_*_PATHS, stale documentation). Docstring audit targets 5 priority modules |
</phase_requirements>

## Standard Stack

No new dependencies needed. This phase uses existing project tools only.

### Core Tools
| Tool | Version | Purpose | Why Standard |
|------|---------|---------|--------------|
| grep | system | Dependency import verification | Simple, reliable, no false positives for import detection |
| vulture | existing | Dead code detection (extend whitelist) | Already configured in Phase 142, `make dead-code` target |
| ruff | existing | F401 unused import check | Already in CI pipeline |
| pytest | existing | Regression verification | 4,178 tests, `make ci` pipeline |

### Pip-to-Import Name Mapping
This is the critical knowledge for the `make check-deps` target. [VERIFIED: grep of src/wanctl/]

| Pip Package | Import Name | Used In |
|------------|-------------|---------|
| requests | `requests` | routeros_rest.py, webhook_delivery.py |
| pyyaml | `yaml` | config_base.py, check_config.py, calibrate.py, check_cake.py, dashboard/config.py, steering/cake_stats.py |
| paramiko | `paramiko` | routeros_ssh.py |
| tabulate | `tabulate` | history.py, benchmark.py |
| icmplib | `icmplib` | rtt_measurement.py |
| textual | `textual` | dashboard/app.py, dashboard/widgets/*.py (optional) |
| httpx | `httpx` | dashboard/app.py, dashboard/poller.py, dashboard/widgets/history_browser.py (optional) |
| pyroute2 | `pyroute2` | backends/netlink_cake.py (optional, try/except guarded) |

**Result: All 8 dependencies are actively imported. DEAD-03 is satisfied if `make check-deps` verifies this and the target is added to CI.** [VERIFIED: grep of src/wanctl/]

## Architecture Patterns

### make check-deps Target Pattern

Follows the Phase 142 pattern of `make dead-code` -- a simple shell command in Makefile that exits non-zero on failure, added to `make ci`.

```makefile
# Dependency audit (unused pip packages in [dependencies] and [optional-dependencies])
# Pip name -> import name mapping (update when adding/removing deps):
#   requests -> requests | pyyaml -> yaml | paramiko -> paramiko
#   tabulate -> tabulate | icmplib -> icmplib
#   textual -> textual | httpx -> httpx | pyroute2 -> pyroute2
check-deps:
	@echo "Checking for unused pip dependencies..."
	@UNUSED=""; \
	for pair in "requests:requests" "pyyaml:yaml" "paramiko:paramiko" \
	            "tabulate:tabulate" "icmplib:icmplib" \
	            "textual:textual" "httpx:httpx" "pyroute2:pyroute2"; do \
	    pkg=$${pair%%:*}; imp=$${pair##*:}; \
	    if ! grep -rq "^import $${imp}\b\|^from $${imp}" src/wanctl/; then \
	        UNUSED="$${UNUSED} $${pkg}"; \
	    fi; \
	done; \
	if [ -n "$${UNUSED}" ]; then \
	    echo "FAIL: Unused dependencies:$${UNUSED}"; exit 1; \
	else \
	    echo "All runtime dependencies are imported"; \
	fi
```

**Key details:**
- Dollar signs doubled for Make (`$$` not `$`)
- Grep uses `^import X\b` and `^from X` anchored patterns to avoid false matches
- Maps pip names to import names (the non-obvious mapping is `pyyaml -> yaml`)
- Only searches `src/wanctl/` per D-07
- `make ci` line changes from `ci: lint type coverage-check dead-code` to `ci: lint type coverage-check dead-code check-deps`

### Config Key Audit Pattern

The bidirectional cross-reference (D-15) needs two passes:

**Pass 1: Example keys -> Code** (find dead keys in examples)
- Extract all YAML keys from `configs/examples/*.yaml.example` at full nesting depth
- For each key, grep `src/wanctl/` for the key string (in `.get("key_name")`, SCHEMA paths, etc.)
- Dead keys: present in examples but never accessed by code

**Pass 2: Code config reads -> Examples** (find undocumented keys)
- Extract all `.get("key_name")` and `data["key_name"]` patterns from config loading code
- For each key, check if it appears in appropriate example file
- Undocumented keys: accessed by code but not in examples

**Key source files for config reading:**
- `src/wanctl/autorate_continuous.py` (Config class, 5,218 LOC) -- lines 300-560 for SCHEMA, lines 758-1220 for optional config loaders
- `src/wanctl/config_base.py` -- BaseConfig, STORAGE_SCHEMA, get_storage_config
- `src/wanctl/steering/daemon.py` -- SteeringConfig
- `src/wanctl/check_config.py` -- KNOWN_AUTORATE_PATHS, KNOWN_STEERING_PATHS

### Anti-Patterns to Avoid
- **Grepping only top-level keys:** Must audit nested keys like `fusion.healing.suspend_threshold`, not just `fusion` [VERIFIED: D-17 requirement]
- **Assuming KNOWN_*_PATHS is complete:** These sets are manually maintained and have significant gaps -- code reads many keys not listed there
- **Editing deprecated translation code:** D-08 and D-13 explicitly forbid this. Only verify translations point to valid current keys

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Dep import detection | AST parsing, pipdeptree | grep for `^import X` / `^from X` | Simple grep catches all import patterns; AST is overkill for 8 packages |
| Config key extraction | YAML schema parser | Manual grep + code reading | Config is loaded imperatively with `.get()` calls, not declaratively |
| Docstring validation | Automated docstring linter | Manual review of priority modules | D-26 requires judgment -- only fix factually wrong content |

## Common Pitfalls

### Pitfall 1: pip name != import name
**What goes wrong:** Checking `import pyyaml` instead of `import yaml`, concluding the dep is unused
**Why it happens:** pip package names don't always match Python import names
**How to avoid:** The pip-to-import mapping table above. The only non-obvious mapping is `pyyaml -> yaml`
**Warning signs:** `make check-deps` reports a dep as unused that you know is used

### Pitfall 2: Optional imports with try/except
**What goes wrong:** Missing optional dep imports because they're wrapped in try/except
**Why it happens:** textual, httpx, pyroute2 use conditional import patterns
**How to avoid:** Grep pattern `^import X\|^from X` catches both direct and try/except imports since the import statement itself is still present
**Warning signs:** grep returns no results for a package you know is installed

### Pitfall 3: KNOWN_*_PATHS Incompleteness
**What goes wrong:** Concluding a config key is dead because it's not in KNOWN_AUTORATE_PATHS
**Why it happens:** These sets are manually maintained and significantly incomplete -- at least 30+ config paths loaded by code are missing
**How to avoid:** Always verify against actual code `.get()` calls, not just the KNOWN sets. The KNOWN sets are for check_config.py's "unknown key" warnings, not an authoritative registry
**Warning signs:** `wanctl-check-config` reporting valid keys as "unknown"

### Pitfall 4: Confusing deprecated key presence with dead code
**What goes wrong:** Removing deprecated keys from KNOWN_*_PATHS or code
**Why it happens:** Deprecated keys look like dead code but are actively translated for backward compatibility
**How to avoid:** D-08 is explicit: keep ALL deprecated config translation code. Only verify translations point to valid current keys (D-10)
**Warning signs:** check_config.py stops detecting deprecated params in production configs

### Pitfall 5: Example file key name mismatch with code
**What goes wrong:** Example files document keys the code never reads (or reads under different names)
**Why it happens:** Config key names evolved over time; examples weren't updated
**How to avoid:** The bidirectional audit. Already found: `irtt.duration_ms` in examples vs `irtt.duration_sec` in code, `irtt.packet_size` in examples but never read by code
**Warning signs:** Users copy example configs and get "unknown key" warnings

## Pre-Researched Config Key Findings

These concrete findings accelerate the planning phase. [VERIFIED: grep and code reading]

### Dead/Stale Keys in Example Files
| Example File | Stale Key | Issue | Fix |
|-------------|-----------|-------|-----|
| All 5 autorate examples | `irtt.duration_ms` | Code reads `irtt.duration_sec` | Rename to `duration_sec: 1.0` |
| All 5 autorate examples | `irtt.packet_size` | Never read by code | Remove entirely |
| wan1, wan2, dsl, fiber | `thresholds.alpha_baseline` (active) | Deprecated per D-24 | Replace with `baseline_time_constant_sec` |
| wan1, wan2, dsl, fiber | `thresholds.alpha_load` (active) | Deprecated per D-24 | Replace with `load_time_constant_sec` |
| wan1, wan2, dsl, fiber | `tuning.bounds.alpha_load` (commented) | Deprecated bound name | Update or remove |
| wan1, wan2, dsl, fiber | `tuning.bounds.alpha_baseline` (commented) | Deprecated bound name | Update or remove |

### Undocumented Keys (in code but not in examples)
| Config Key | Code Location | Type | Fix |
|------------|--------------|------|-----|
| `owd_asymmetry` + sub-keys | autorate_continuous.py:903-932 | Optional section | Add commented-out block to examples |
| `ping_source_ip` | autorate_continuous.py:518 | Optional string | Add commented-out line to examples |
| `fusion.healing.*` (5 sub-keys) | autorate_continuous.py:967-1038 | Optional sub-section | Add to fusion block in examples |
| `storage.retention.*` (4 sub-keys) | config_base.py:168-217 | Optional sub-section | Add to examples, update CONFIG_SCHEMA.md |

### Missing from KNOWN_AUTORATE_PATHS
These keys are loaded by code but missing from the `KNOWN_AUTORATE_PATHS` set in check_config.py, causing false "unknown key" warnings:

| Missing Path Group | Count | Source |
|-------------------|-------|--------|
| `irtt.*` (enabled, server, port, duration_sec, interval_ms, cadence_sec) | 7 | _load_irtt_config |
| `reflector_quality.*` (min_score, window_size, probe_interval_sec, recovery_count) | 5 | _load_reflector_quality_config |
| `owd_asymmetry.*` (ratio_threshold) | 2 | _load_owd_asymmetry_config |
| `fusion.*` (enabled, icmp_weight, healing.*) | 9 | _load_fusion_config |
| `tuning.*` (enabled, cadence_sec, lookback_hours, warmup_hours, max_step_pct, exclude_params, bounds.*) | 8+ | _load_tuning_config |
| `ping_source_ip` | 1 | Config._load_specific_fields |
| `storage.retention.*` (raw_age_seconds, aggregate_1m_age_seconds, aggregate_5m_age_seconds, prometheus_compensated) | 5 | get_storage_config |

**Total missing paths: ~37+** -- this is a significant completeness gap in check_config.py's unknown-key detection.

### CONFIG_SCHEMA.md Gaps
| Gap | Current State | Fix |
|-----|--------------|-----|
| `storage.retention.*` sub-keys | Only documents deprecated `retention_days` | Add new retention section with all 4 sub-keys |
| `owd_asymmetry` section | Not documented at all | Add optional section documentation |
| `fusion.healing` sub-section | Not documented | Add healing parameters to fusion section |
| `ping_source_ip` | Not documented | Add to common fields or ping section |
| IRTT key name mismatch | Documents `duration_ms` via examples | Correct to `duration_sec`, remove `packet_size` |

## Deprecated Config Translation Verification (D-10)

Deprecated-to-new translations in the codebase: [VERIFIED: code reading]

| Deprecated Key | New Key | Translation Function | Location | Valid? |
|---------------|---------|---------------------|----------|--------|
| `alpha_baseline` | `baseline_time_constant_sec` | `cycle_interval / alpha` | check_config.py:738-761 | Yes -- translation math is correct |
| `alpha_load` | `load_time_constant_sec` | `cycle_interval / alpha` | check_config.py:764-786 | Yes -- translation math is correct |
| `storage.retention_days` | `storage.retention` | lambda in get_storage_config | config_base.py:191-201 | Yes -- translates to retention sub-dict |
| `mode.cake_aware` | (removed) | No translation, just warns | check_config.py:976-987 | Yes -- correctly ignored |
| `cake_state_sources.spectrum` | `cake_state_sources.primary` | No auto-translation, just warns | check_config.py:990-998 | Needs review -- warns but doesn't translate |
| `cake_queues.spectrum_download` | `cake_queues.primary_download` | No auto-translation, just warns | check_config.py:1002-1020 | Needs review -- warns but doesn't translate |

**Findings:** The autorate deprecated params (alpha_*) properly translate values. The steering deprecated params (spectrum -> primary) only warn but don't translate -- this may be intentional (D-08 says keep the translation code, but these don't actually translate). Worth documenting whether the steering daemon code handles the deprecated key names directly.

## Vulture Whitelist Extensions (D-09)

Functions that should be added to `vulture_whitelist.py` for deprecated config handling: [VERIFIED: code reading]

| Function | File | Reason |
|----------|------|--------|
| `check_deprecated_params` | check_config.py:726 | Called from validate_autorate, but vulture may flag if called only in one path |
| `check_steering_deprecated_params` | check_config.py:967 | Called from validate_steering, same concern |
| `deprecate_param` | config_validation_utils.py:22 | Called from config_base.py and potentially flagged |

**Note:** These may already be reachable and not flagged by vulture. Only add if vulture actually reports them. The current whitelist (150 lines) does not include these.

## Code Examples

### Verified Makefile Integration Pattern
```makefile
# Source: Phase 142 Makefile (current codebase)
# All CI checks (lint, type, coverage, dead-code, check-deps)
ci: lint type coverage-check dead-code check-deps
```
[VERIFIED: Makefile in codebase]

### Deprecated Param Check Pattern
```python
# Source: src/wanctl/config_validation_utils.py
# This is the existing deprecation helper -- do NOT modify (D-13)
translated = deprecate_param(
    config, old_key="alpha_baseline", new_key="baseline_time_constant_sec",
    logger=logger, transform_fn=lambda alpha: round(cycle_interval / alpha, 1)
)
```
[VERIFIED: config_validation_utils.py:22-58]

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|-------------|------------------|--------------|--------|
| `alpha_baseline` / `alpha_load` | `baseline_time_constant_sec` / `load_time_constant_sec` | v1.20 (Phase 98+) | Examples still show old names in 4/6 files |
| `irtt.duration_ms` | `irtt.duration_sec` | v1.18 (Phase 88+) | Examples never updated |
| `irtt.packet_size` | (removed) | v1.18 (Phase 88+) | Examples still show it |
| `storage.retention_days` | `storage.retention.*` sub-keys | v1.20 (Phase 98+) | Schema docs never updated |
| `cake_state_sources.spectrum` | `cake_state_sources.primary` | v1.13 (Phase 75+) | Portable controller rename |

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | wan2.yaml.example is the 6th example file (CONTEXT.md says 5 but there are 6) | Config Key Findings | Low -- D-16 lists 5 files but wan2 exists; planner should include it |
| A2 | vulture will not flag deprecated param functions | Vulture Whitelist Extensions | Low -- if flagged, just add to whitelist |

## Open Questions (RESOLVED)

1. **wan2.yaml.example count discrepancy**
   - What we know: CONTEXT.md D-16 says "5 files: cable, dsl, fiber, steering, wan1" but `configs/examples/` has 6 files (also wan2)
   - What's unclear: Whether wan2 was intentionally excluded from scope
   - Recommendation: Include wan2 in the audit -- it has the same stale keys as wan1
   - RESOLVED: wan2.yaml.example included in Plan 02 scope (files_modified lists all 6 example files including wan2)

2. **Steering deprecated param translation behavior**
   - What we know: check_config.py warns about spectrum->primary renaming but doesn't auto-translate
   - What's unclear: Whether the steering daemon code (`steering/daemon.py`) handles deprecated key names directly at load time
   - Recommendation: Verify in the daemon's config loading -- if it doesn't translate, the deprecated keys are purely warning-only (not broken, but worth documenting per D-10)
   - RESOLVED: Plan 02 Task 1 Part A explicitly reads steering/daemon.py SteeringConfig to investigate whether deprecated keys are handled at load time and documents findings per D-10

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.0+ |
| Config file | pyproject.toml [tool.pytest.ini_options] |
| Quick run command | `.venv/bin/pytest tests/ -x -q` |
| Full suite command | `.venv/bin/pytest tests/ -v` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| DEAD-03 | No unused pip deps in pyproject.toml | smoke | `make check-deps` (new target) | Wave 0 |
| DEAD-04a | Zero TODO/FIXME/HACK referencing resolved work | manual-only | N/A (already zero -- verified by grep) | N/A |
| DEAD-04b | Config key cross-reference is clean | smoke | `make ci` (no new unknown-key warnings) | Existing (test_check_config.py) |
| DEAD-04c | Docstrings factually correct | manual-only | N/A (judgment required per D-26) | N/A |
| DEAD-04d | All tests pass unchanged | regression | `.venv/bin/pytest tests/ -v` | Existing (4,178 tests) |

### Sampling Rate
- **Per task commit:** `.venv/bin/pytest tests/ -x -q` + `make ci`
- **Per wave merge:** `.venv/bin/pytest tests/ -v` (full suite)
- **Phase gate:** Full suite green + `make ci` green before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `make check-deps` Makefile target -- covers DEAD-03
- No test file creation needed -- existing test_check_config.py (99 tests) covers config validation

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | N/A |
| V3 Session Management | no | N/A |
| V4 Access Control | no | N/A |
| V5 Input Validation | no | N/A (config validation exists, not being modified) |
| V6 Cryptography | no | N/A |

No security implications -- this phase only removes unused dependencies and fixes documentation/config key references. No behavioral changes, no new code paths.

## Sources

### Primary (HIGH confidence)
- Codebase grep of `src/wanctl/` for all import statements [VERIFIED: grep tool]
- `pyproject.toml` [dependencies] and [optional-dependencies] sections [VERIFIED: file read]
- `src/wanctl/autorate_continuous.py` Config class config loading methods [VERIFIED: file read]
- `src/wanctl/check_config.py` KNOWN_AUTORATE_PATHS and KNOWN_STEERING_PATHS [VERIFIED: file read]
- `src/wanctl/config_base.py` STORAGE_SCHEMA and get_storage_config [VERIFIED: file read]
- `src/wanctl/config_validation_utils.py` deprecate_param [VERIFIED: file read]
- `configs/examples/*.yaml.example` (6 files) [VERIFIED: file read]
- `docs/CONFIG_SCHEMA.md` [VERIFIED: grep and partial read]
- Phase 142 CONTEXT.md and 142-02-SUMMARY.md [VERIFIED: file read]

### Secondary (MEDIUM confidence)
- None needed -- all findings from direct codebase analysis

### Tertiary (LOW confidence)
- None

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - no new tools, all existing infrastructure
- Architecture: HIGH - follows Phase 142 `make dead-code` pattern exactly
- Config key findings: HIGH - all gaps verified by comparing code reads vs example files vs KNOWN paths
- Pitfalls: HIGH - derived from actual codebase analysis, not hypothetical

**Research date:** 2026-04-05
**Valid until:** 2026-05-05 (stable -- internal cleanup, no external dependencies to change)
