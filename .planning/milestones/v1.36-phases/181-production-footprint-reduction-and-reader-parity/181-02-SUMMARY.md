---
phase: 181-production-footprint-reduction-and-reader-parity
plan: 02
status: completed
requirements-completed: ""
date: 2026-04-14
---

# Plan 181-02 Summary

## Shipped repo changes

- `/metrics/history` now uses the configured local `storage.db_path` when running under a live controller
- standalone/test usage still keeps the older merged-discovery fallback
- response metadata now includes `metadata.source.mode` and `metadata.source.db_paths`
- operator docs now say:
  - CLI module path is authoritative for merged cross-WAN reads
  - HTTP `/metrics/history` is the endpoint-local history surface

## Validation

Passed:

```bash
.venv/bin/pytest -o addopts='' tests/storage/test_storage_maintenance.py tests/test_health_check.py tests/test_history_multi_db.py tests/test_history_cli.py -q
bash -n scripts/compact-metrics-dbs.sh scripts/deploy.sh scripts/soak-monitor.sh scripts/canary-check.sh
git diff --check
```

Result:
- `229 passed`

## Operator effect

This closes the accidental ambiguity between the two reader surfaces in repo-side behavior and documentation.

Later production verification confirmed the intended narrowed role:

- CLI remains the authoritative merged cross-WAN proof path
- `/metrics/history` is the endpoint-local HTTP surface and now exposes explicit source metadata

That is a real phase success, but it does not by itself satisfy `STOR-06`, because the footprint-reduction claim still depends on the live size outcome.
