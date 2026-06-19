# Phase 241 Plan 01 Deferred Items

## Out-of-scope verification noise

- Full `ruff check src/ tests/` currently reports pre-existing lint findings in files outside Plan 01's edit surface, including `src/wanctl/rtt_backend.py`, `src/wanctl/rtt_measurement.py`, multiple legacy test modules, and steering replay helpers. Plan 01 did not modify those files; focused `ruff check src/wanctl/fping_measurement.py tests/test_fping_measurement.py` passes.
- Full `mypy src/wanctl/` currently reports a pre-existing `RttSample` forward-reference issue in `src/wanctl/rtt_measurement.py`. Plan 01 keeps `rtt_measurement.py` byte-frozen per D-07/SAFE-17; focused `mypy src/wanctl/fping_measurement.py` passes.

## Plan 02 out-of-scope verification noise

- `.venv/bin/mypy src/wanctl/check_config_validators.py` still reports the pre-existing `RttSample` forward-reference issue in byte-frozen `src/wanctl/rtt_measurement.py:325` via imported-module checking. Plan 02 did not modify `rtt_measurement.py`; fixing it would violate the Phase 241 SAFE-17/D-07 frozen-seam boundary and is deferred to a phase that can explicitly reopen that surface.

## Plan 04 out-of-scope full-suite noise

- `.venv/bin/pytest tests/ -q` was run at the SAFE-17 boundary and reached `5510 passed, 13 skipped, 2 deselected` before failing 35 historical/boundary tests whose assertions are anchored to older phases or superseded service naming (`BOUND-01` v1.50 real-repo guard, Phase 219/220/221 mutation-boundary tests, Phase 220 matrix wrapper refusal-order tests, Phase 231 rollback/soak-monitor legacy watchdog expectations, and Phase 239/240 old SAFE-17 passes-at-boundary tests). The Phase 241 acceptance-critical focused checks passed: phase-local diff vs `a181ca27`, RTT seam no-drift vs `03c82de0`, hot-path slice (`673 passed`), Phase 241 verifier tests (`7 passed`), and the SAFE-17 boundary verifier evidence (`passed:true`). Fixing or re-scoping these legacy tests is outside Plan 04's controller-path boundary gate and should be handled as a separate historical-test hygiene task.
