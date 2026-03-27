# Deferred Items - Phase 118

## Pre-existing Test Failures (Out of Scope)

1. **test_boundary_data_at_exactly_retention_days** - Flaky timing-sensitive boundary test in test_storage_retention.py. time.time() advances between insert and cutoff calculation.
2. **test_container_network_audit.py** - ImportError: No module named 'scripts.container_network_audit'
3. **test_dashboard/test_layout.py** - ImportError: No module named 'httpx'
4. **test_production_steering_yaml_no_unknown_keys** - FileNotFoundError: configs/steering.yaml not found in worktree
5. **test_version_specs_match** - Dockerfile requests version (>=2.31.0) mismatches pyproject.toml (>=2.33.0)
6. **test_netlink_cake_backend.py** - Ruff B905: zip() without strict= parameter
