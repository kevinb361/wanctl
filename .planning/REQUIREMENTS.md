# Requirements: wanctl v1.10

**Defined:** 2026-03-07
**Core Value:** Sub-second congestion detection with 50ms control loops, production reliability

## v1.10 Requirements

Requirements from senior architectural review. Each maps to roadmap phases.

### Hot-Loop & Transport Safety

- [ ] **LOOP-01**: Retry decorator in hot loop uses sub-cycle delays (max 50ms initial, 1 retry) instead of 1s+2s blocking delays
- [ ] **LOOP-02**: `get_router_client_with_failover()` honors `config.router_transport` setting for primary transport selection
- [ ] **LOOP-03**: Failover client periodically re-probes primary transport after fallback, restoring REST when available
- [ ] **LOOP-04**: Main autorate loop uses `shutdown_event.wait()` instead of `time.sleep()` for consistent signal responsiveness

### Steering Reliability

- [ ] **STEER-01**: Legacy state name normalization in `_is_current_state_good()` logs a warning when triggered
- [ ] **STEER-02**: Anomaly detection returns cycle-skip (True) instead of cycle-failure (False) to prevent spurious failure accumulation
- [ ] **STEER-03**: `BaselineLoader` checks autorate state file timestamp and warns/degrades when baseline is stale (>5 minutes)
- [ ] **STEER-04**: `BaselineLoader` uses `safe_json_load_file()` instead of raw `open()`/`json.load()`

### Operational Resilience

- [ ] **OPS-01**: REST API client defaults to `verify_ssl=True` with documentation for self-signed cert setup
- [ ] **OPS-02**: SQLite metrics writer performs `PRAGMA integrity_check` at startup and rebuilds on corruption
- [ ] **OPS-03**: Health endpoint includes disk space status for `/var/lib/wanctl/`, warns when low
- [ ] **OPS-04**: Cryptography dependency updated to patch CVE-2026-26007
- [ ] **OPS-05**: YAML config parse errors surface line numbers in error messages

### Code Cleanup

- [ ] **CLEAN-01**: Rename `self.ssh` to `self.client` in autorate (holds `FailoverRouterClient`, not SSH)
- [ ] **CLEAN-02**: Update stale docstrings referencing "2-second control loop" to 50ms
- [ ] **CLEAN-03**: Remove `import time as time_module` inside hot loop, use module-level `time` import
- [ ] **CLEAN-04**: Resolve contradictory defaults between config (`ssh`) and factory (`rest`) for `router_transport`
- [ ] **CLEAN-05**: Scope `disable_warnings(InsecureRequestWarning)` to REST session instead of process-global
- [ ] **CLEAN-06**: Fix 10 ruff violations (import ordering, unused loop variables)
- [ ] **CLEAN-07**: Extract `validate_config_mode()` from `main()` to reduce complexity

### Codebase Audit

- [ ] **AUDIT-01**: Audit autorate/steering daemons for remaining code duplication and consolidation opportunities
- [ ] **AUDIT-02**: Review module boundaries, `__init__.py` exports, and import structure for clarity
- [ ] **AUDIT-03**: Identify and address remaining complexity hotspots beyond `main()`

### Test Quality

- [ ] **TEST-01**: Consolidate duplicated `mock_config` fixtures (8+ files) into shared conftest.py fixtures
- [ ] **TEST-02**: Add behavioral integration tests for autorate-steering daemon interaction via state file
- [ ] **TEST-03**: Add reduced-mock behavioral tests for router communication layer (REST and SSH)
- [ ] **TEST-04**: Add failure cascade tests (router down + storage error simultaneously)

## Future Requirements

### Deferred from Review

- **CNTR-01**: Contract tests with golden files for RouterOS API responses (Phase 46 deferred from v1.8)
- **INTG-01**: Integration test infrastructure for CI (RouterOS CHR in Docker or VCR-style replay)

## Out of Scope

| Feature | Reason |
|---------|--------|
| Core algorithm changes | Architectural spine — read-only per CLAUDE.md |
| Threshold/timing modifications | Protected zones — requires explicit approval |
| New user-facing features | This milestone is hardening only |
| Prometheus/Grafana integration | Keep self-contained per constraints |
| Breaking config changes | Backward compatibility required |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| LOOP-01 | Phase 50 | Pending |
| LOOP-02 | Phase 50 | Pending |
| LOOP-03 | Phase 50 | Pending |
| LOOP-04 | Phase 50 | Pending |
| STEER-01 | Phase 51 | Pending |
| STEER-02 | Phase 51 | Pending |
| STEER-03 | Phase 51 | Pending |
| STEER-04 | Phase 51 | Pending |
| OPS-01 | Phase 52 | Pending |
| OPS-02 | Phase 52 | Pending |
| OPS-03 | Phase 52 | Pending |
| OPS-04 | Phase 52 | Pending |
| OPS-05 | Phase 52 | Pending |
| CLEAN-01 | Phase 53 | Pending |
| CLEAN-02 | Phase 53 | Pending |
| CLEAN-03 | Phase 53 | Pending |
| CLEAN-04 | Phase 50 | Pending |
| CLEAN-05 | Phase 53 | Pending |
| CLEAN-06 | Phase 53 | Pending |
| CLEAN-07 | Phase 53 | Pending |
| AUDIT-01 | Phase 54 | Pending |
| AUDIT-02 | Phase 54 | Pending |
| AUDIT-03 | Phase 54 | Pending |
| TEST-01 | Phase 55 | Pending |
| TEST-02 | Phase 55 | Pending |
| TEST-03 | Phase 55 | Pending |
| TEST-04 | Phase 55 | Pending |

**Coverage:**
- v1.10 requirements: 27 total
- Mapped to phases: 27
- Unmapped: 0

---
*Requirements defined: 2026-03-07*
*Last updated: 2026-03-07 after roadmap creation*
