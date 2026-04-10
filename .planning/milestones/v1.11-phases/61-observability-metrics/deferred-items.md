# Deferred Items - Phase 61

## Pre-existing Test Failure

- `tests/test_steering_metrics_recording.py::TestWanAwarenessMetrics::test_wan_zone_in_stored_metrics`
- Fails because `wanctl_wan_zone` not yet in `STORED_METRICS` schema
- This is 61-01 scope (OBSV-02 metrics recording), not 61-02
- The test was added alongside partial daemon.py changes from 61-01 planning
