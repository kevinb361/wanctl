# Phase 167 Validation Map

## Requirement Coverage

- `ALRT-01` -> `167-01-PLAN.md`
  - sustained latency-regression alert logic
  - bounded degraded/critical detection from existing health signals
- `ALRT-02` -> `167-01-PLAN.md`, `167-02-PLAN.md`
  - burst-related alert gating
  - healthy-state non-chatter and cooldown validation
- `ALRT-03` -> `167-01-PLAN.md`, `167-02-PLAN.md`
  - explicit severity/cooldown mapping
  - manual operator sanity gate for production usefulness

## Planned Verification

- `.venv/bin/pytest -o addopts='' tests/test_alert_engine.py tests/test_health_check.py -q`
- `.venv/bin/mypy src/wanctl/wan_controller.py src/wanctl/alert_engine.py`
- `.venv/bin/ruff check src/wanctl/wan_controller.py src/wanctl/alert_engine.py tests/test_alert_engine.py tests/test_health_check.py`
- manual sanity check of alert-ready operator state

## Nyquist Notes

- Phase 167 intentionally reuses existing AlertEngine and health/metrics signals; it should not introduce a second alerting or persistence path.
- Manual validation is required because production usefulness depends on operator clarity and non-chatter, not just unit-level correctness.
