# Phase 66: Infrastructure & Config Extraction - Context

**Gathered:** 2026-03-10
**Status:** Ready for planning

<domain>
## Phase Boundary

Logging gets rotation, Dockerfile builds are validated via contract tests, config loading boilerplate is consolidated into BaseConfig, and production cryptography version is verified. No new features — infrastructure hygiene and code deduplication.

Requirements: INFR-01, INFR-02, INFR-03, INFR-04

</domain>

<decisions>
## Implementation Decisions

### Log rotation (INFR-01)
- Replace FileHandler with RotatingFileHandler in setup_logging() for both main and debug log handlers
- Defaults: maxBytes=10485760 (10MB), backupCount=3
- Both main_log and debug_log rotate with the same parameters
- Rotation parameters configurable via YAML: logging.max_bytes, logging.backup_count
- These fields go in BaseConfig BASE_SCHEMA with defaults (not required)
- Total disk budget per daemon: ~40MB main + ~40MB debug = ~80MB worst case

### Config consolidation (INFR-03)
- Move logging and lock fields into BaseConfig — NOT transport or metrics (those have daemon-specific differences)
- Consolidated fields: logging.main_log, logging.debug_log, logging.max_bytes, logging.backup_count, lock_file, lock_timeout
- These move into BASE_SCHEMA with appropriate validation
- BaseConfig.__init__ loads common fields (self.main_log, self.debug_log, self.max_bytes, self.backup_count, self.lock_file, self.lock_timeout) BEFORE calling _load_specific_fields()
- Subclasses remove their duplicate schema entries and loading methods for these fields
- Health port stays daemon-specific (different ports by design: 9101 autorate, 9102 steering)

### Docker build validation (INFR-02)
- Pytest contract test — no actual Docker build required
- Test parses Dockerfile pip install line, verifies all pyproject.toml [project.dependencies] appear with matching version specs
- Test verifies Dockerfile COPY paths match actual source directory structure (glob patterns resolve to real files)
- Test verifies Dockerfile LABEL version matches pyproject.toml [project].version
- Same contract test pattern used in Phase 65 for state file schema

### Cryptography verification (INFR-04)
- Pytest version assertion that parses version spec from pyproject.toml (single source of truth)
- Expanded scope: verify ALL runtime dependencies are importable and meet pyproject.toml version specs, not just cryptography
- One test function parametrized over all runtime deps from pyproject.toml

### Claude's Discretion
- Test file organization (new test file vs extending existing contract tests)
- Exact RotatingFileHandler import and wiring details
- How to parse pyproject.toml dependency specs in tests (tomllib vs regex)
- Whether to use packaging.version for version comparison

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `config_base.py:211` — BaseConfig already has SCHEMA validation, BASE_SCHEMA, and `_load_specific_fields()` hook
- `config_base.py:119` — STORAGE_SCHEMA pattern shows how optional schema lists work
- `logging_utils.py:142` — setup_logging() already takes a config object with main_log/debug_log attrs
- Phase 65 contract tests — established pattern for schema-pinning assertions

### Established Patterns
- BaseConfig.__init__ validates schema then calls _load_specific_fields() — new common field loading fits between these
- Both daemons have decomposed _load_*() helpers called from _load_specific_fields()
- YAML config sections: `logging:` with main_log/debug_log, `lock_file:` / `lock_timeout:` top-level keys
- pyproject.toml is canonical dependency source (Phase 62 decision)

### Integration Points
- `setup_logging()` signature: takes `config` object — needs max_bytes/backup_count from config attrs
- Both Config classes: remove duplicate logging/lock schema entries after BaseConfig absorbs them
- `autorate_continuous.py:528` — `_load_logging_config()` sets self.main_log, self.debug_log
- `steering/daemon.py:523` — `_load_logging_config()` sets self.main_log, self.debug_log
- `docker/Dockerfile:47-53` — pip install line to validate against pyproject.toml

</code_context>

<specifics>
## Specific Ideas

- Rotation parameters should have safe defaults so existing YAML configs work without changes (backward compatible)
- The Dockerfile contract test and dependency version test can share a pyproject.toml parsing utility
- "Single source of truth" is the recurring theme: pyproject.toml drives Dockerfile, install.sh, and tests

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 66-infrastructure-config-extraction*
*Context gathered: 2026-03-10*
