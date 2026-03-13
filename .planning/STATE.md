---
gsd_state_version: 1.0
milestone: v1.17
milestone_name: CAKE Optimization & Benchmarking
status: executing
last_updated: "2026-03-13T21:03:05Z"
last_activity: 2026-03-13 -- Completed 86-02 (benchmark CLI tool)
progress:
  total_phases: 4
  completed_phases: 3
  total_plans: 6
  completed_plans: 6
  percent: 75
---

# Session State

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-13)

**Core value:** Sub-second congestion detection with 50ms control loops
**Current focus:** Phase 86 - Bufferbloat Benchmarking

## Position

**Milestone:** v1.17 CAKE Optimization & Benchmarking
**Phase:** 86 of 87 (Bufferbloat Benchmarking) -- COMPLETE
**Plan:** 02 of 02 complete (benchmark CLI tool)
**Status:** Executing
**Last activity:** 2026-03-13 -- Completed 86-02 (benchmark CLI tool)

Progress: [########..] 75%

## Performance Metrics

**Velocity:**

- Total plans completed: 6
- Average duration: 23min
- Total execution time: 2.3 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
| ----- | ----- | ----- | -------- |
| 84    | 2     | 68min | 34min    |
| 85    | 2     | 51min | 25min    |
| 86    | 2     | 17min | 8min     |

## Accumulated Context

### Key Decisions

- get_queue_types() follows exact get_queue_stats() pattern (GET with name filter, return first item or None)
- cake-ack-filter optimal value is "filter" (RouterOS REST API representation of enabled)
- OPTIMAL_WASH is direction-dependent: upload=yes (strip before ISP), download=no (preserve for LAN WMM)
- INFO-level results mapped to Severity.PASS (no INFO in enum, consistent with max-limit informational PASS pattern)
- \_skippable_categories() helper extracts skip-list logic, avoids duplication between env var and connectivity failure paths
- Step 3.5 re-fetches queue stats rather than modifying check_queue_tree() return signature
- set_queue_type_params uses inline GET+PATCH (not \_find_resource_id cache) for infrequent queue type writes
- Snapshots use json.dump (not atomic_write_json) since they are one-shot archival writes
- \_extract_changes_for_direction returns (actual, expected) tuples for both display and PATCH payload derivation
- datetime.UTC alias used instead of timezone.utc for Python 3.11+ modern style (ruff UP017)
- run_fix() overwrites queue_names with queue type names for PATCH targeting (set_queue_type_params needs queue type name, not queue tree name)
- \_show_diff_table() prints to stderr so --json stdout stays clean for piping
- \_confirm_apply() safe default: empty/anything = No, only y/yes = Yes
- \_apply_changes() sends single PATCH per queue type (RouterOS PATCH is atomic per resource)
- Fix cancelled by user returns PASS severity (user choice, not failure)
- GRADE_THRESHOLDS as list[tuple[float, str]] with strict less-than comparison for grade boundaries
- Both download and upload latency use same ICMP ping series (RRUL Pitfall 1 -- separate fields for future directional tests)
- statistics.quantiles(n=100) for P50/P95/P99 (index 49/94/98)
- check_prerequisites returns (checks, baseline_rtt) tuple to pass baseline to run_benchmark
- Server connectivity probed via 1s netperf TCP_STREAM (validates server + network path)
- Daemon detection warns to stderr but does not block benchmark
- run_benchmark timeout = duration + 30s for flent subprocess overhead
- Quick mode note only shown for duration <= 10s

### Known Issues

- RouterOS REST JSON field names for `/rest/queue/type` CAKE parameters need live router verification during Phase 84
- ATT BGW320 passthrough mode (bridged-ptm vs pppoe-ptm) needs explicit config -- cannot auto-detect

### Blockers

None.

### Quick Tasks Completed

| #   | Description                                                                                       | Date       | Commit  | Directory                                                                                         |
| --- | ------------------------------------------------------------------------------------------------- | ---------- | ------- | ------------------------------------------------------------------------------------------------- |
| 7   | Fix flapping alert bugs: rule name mismatch, deque not cleared, threshold not calibrated for 20Hz | 2026-03-12 | 98f0dab | [7-fix-flapping-alert-bugs-rule-name-mismat](./quick/7-fix-flapping-alert-bugs-rule-name-mismat/) |
| 8   | Fix flapping alert cooldown key mismatch and add dwell filter for zone blips                      | 2026-03-13 | f6babcc | [8-fix-flapping-alert-detection-cooldown-ke](./quick/8-fix-flapping-alert-detection-cooldown-ke/) |

### Pending Todos

5 todos in `.planning/todos/pending/`:

- Research IRTT as RTT measurement alternative (general) -- deferred to future milestone
- Integration test for router communication (testing) -- low priority, contract tests added in v1.12
- Narrow layout truncates WAN panel content (dashboard/ui) -- low priority, wide layout works fine
- Investigate LXC container network optimizations (infrastructure) -- RTT accuracy depends on low-latency container networking
- Audit CAKE qdisc configuration for Spectrum and ATT links (networking) -- verify link-layer compensation and overhead settings
