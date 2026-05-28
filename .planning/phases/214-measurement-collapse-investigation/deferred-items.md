# Phase 214 Deferred Items

## Plan 214-02

- **Out-of-scope full-suite failure:** `.venv/bin/pytest tests/ -q` failed in
  `tests/test_autorate_metrics_recording.py::TestPerformanceOverhead::test_many_cycles_no_degradation`
  with `Max write time 10.04ms, expected <5ms` after 5,150 tests passed. This
  is an unrelated timing-sensitive performance assertion outside the Phase 214
  extractor/fixture changes. Focused Plan 214-02 tests passed.
