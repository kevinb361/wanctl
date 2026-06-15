# Phase 241 Plan 01 Deferred Items

## Out-of-scope verification noise

- Full `ruff check src/ tests/` currently reports pre-existing lint findings in files outside Plan 01's edit surface, including `src/wanctl/rtt_backend.py`, `src/wanctl/rtt_measurement.py`, multiple legacy test modules, and steering replay helpers. Plan 01 did not modify those files; focused `ruff check src/wanctl/fping_measurement.py tests/test_fping_measurement.py` passes.
- Full `mypy src/wanctl/` currently reports a pre-existing `RttSample` forward-reference issue in `src/wanctl/rtt_measurement.py`. Plan 01 keeps `rtt_measurement.py` byte-frozen per D-07/SAFE-17; focused `mypy src/wanctl/fping_measurement.py` passes.

## Plan 02 out-of-scope verification noise

- `.venv/bin/mypy src/wanctl/check_config_validators.py` still reports the pre-existing `RttSample` forward-reference issue in byte-frozen `src/wanctl/rtt_measurement.py:325` via imported-module checking. Plan 02 did not modify `rtt_measurement.py`; fixing it would violate the Phase 241 SAFE-17/D-07 frozen-seam boundary and is deferred to a phase that can explicitly reopen that surface.
