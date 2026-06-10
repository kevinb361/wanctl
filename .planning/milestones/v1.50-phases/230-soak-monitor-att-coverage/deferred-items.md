# Deferred Items

## Full-suite pre-existing Phase 220/221 boundary failures

- **Found during:** Plan 230-01 Task 3 full-suite verification
- **Command:** `.venv/bin/pytest tests/ -q`
- **Observed:** 21 failures in Phase 220/221 matrix/mutation-boundary tests, all refusing because `src/wanctl/` has committed changes since `PHASE214_BASE_SHA=50f3d5136830c284b190b29de939a84406531ecc`.
- **Scope assessment:** Out of scope for Plan 230-01. This plan touched only `scripts/soak-monitor.sh`, `tests/test_soak_monitor_att_coverage.py`, and execution metadata/context; no `src/wanctl/` files were modified by this plan.
- **Action:** Documented here for follow-up; did not alter historical Phase 220/221 boundary tests.
