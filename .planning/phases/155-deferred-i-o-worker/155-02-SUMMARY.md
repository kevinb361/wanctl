---
phase: 155-deferred-i-o-worker
plan: 02
subsystem: storage/control-loop
tags: [io-worker, background-thread, sqlite, performance, cycle-budget]
dependency_graph:
  requires: []
  provides: [deferred-io-worker, background-sqlite-writes]
  affects: [wan-controller-hot-path, daemon-lifecycle, shutdown-sequence]
tech_stack:
  added: []
  patterns: [SimpleQueue-sentinel-drain, daemon-thread-lifecycle, conditional-dispatch]
key_files:
  created:
    - src/wanctl/storage/deferred_writer.py
    - tests/storage/test_deferred_writer.py
  modified:
    - src/wanctl/wan_controller.py
    - src/wanctl/autorate_continuous.py
decisions:
  - "SimpleQueue (not Queue with maxsize) for lock-free unbounded enqueue -- write rate bounded by 20Hz cycle"
  - "Sentinel-based drain ensures all items processed before thread exits"
  - "Conditional dispatch (io_worker or direct write) preserves backward compatibility for tests and edge cases"
  - "Steering daemon untouched -- separate process with its own write cadence"
metrics:
  duration: 612s
  completed: "2026-04-09T02:59:50Z"
  tasks_completed: 2
  tasks_total: 2
  files_created: 2
  files_modified: 2
---

# Phase 155 Plan 02: DeferredIOWorker Background Thread Summary

**One-liner:** SimpleQueue-based background I/O worker offloads all per-cycle SQLite writes from 50ms control loop to daemon thread with sentinel drain and health observability.

## Task Summary

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Create DeferredIOWorker class with tests (TDD) | 0f365d6, 4ac2d0b | deferred_writer.py, test_deferred_writer.py |
| 2 | Wire DeferredIOWorker into control loop lifecycle | 9580e1a | wan_controller.py, autorate_continuous.py |

## What Was Built

### DeferredIOWorker (src/wanctl/storage/deferred_writer.py)
- Background daemon thread consuming write requests from `queue.SimpleQueue`
- Type-safe dataclass payloads: `_BatchWrite`, `_SingleWrite`, `_AlertWrite`, `_ReflectorEventWrite`
- Sentinel-based shutdown with `_drain_remaining()` to process all queued items before exit
- Exception resilience: `_process_item()` wrapped in try/except, thread continues after writer errors
- Health properties: `pending_count` (thread-safe counter) and `is_alive` (thread status)
- Pattern: Follows BackgroundRTTThread lifecycle (daemon=True, join timeout=5s, shutdown_event)

### Control Loop Integration (wan_controller.py)
- `_run_logging_metrics`: `write_metrics_batch` -> `enqueue_batch` (hot path batch writes)
- `_run_logging_metrics`: `write_metric` -> `enqueue_write` (DL/UL transition reason writes)
- `_persist_reflector_events`: `write_reflector_event` -> `enqueue_reflector_event` (score changes)
- All sites have `else:` fallback to direct `MetricsWriter` calls when `_io_worker is None`
- New `set_io_worker()` method for dependency injection

### Daemon Lifecycle (autorate_continuous.py)
- `_setup_daemon_state` creates `DeferredIOWorker`, starts it, injects into all WAN controllers
- Returns `io_worker` for cleanup tracking
- `_cleanup_daemon` calls `io_worker.stop()` BEFORE `_close_metrics_writer()` (ordered shutdown)
- Deadline-checked cleanup with `check_cleanup_deadline()` for watchdog safety

## Tests

13 unit tests in `tests/storage/test_deferred_writer.py`:
- `TestDeferredIOWorker` (5): enqueue_batch non-blocking, batch dispatch, single write, alert, reflector event
- `TestShutdownDrain` (3): drain all items, timeout safety, pre-sentinel items processed
- `TestErrorHandling` (2): exception doesn't crash thread, subsequent enqueues still processed
- `TestHealth` (3): pending_count starts at 0, tracks enqueue/processing, is_alive lifecycle

## Deviations from Plan

None - plan executed exactly as written.

## Threat Surface Scan

No new threat surfaces introduced. All queue payloads are internal dataclass instances created within the process. No new network endpoints, auth paths, or file access patterns added.

## Self-Check: PASSED

- All 2 created files exist on disk
- All 3 commits (0f365d6, 4ac2d0b, 9580e1a) found in git log
- 13/13 DeferredIOWorker tests passing
- 0 regressions introduced (3 pre-existing failures unrelated to changes)
