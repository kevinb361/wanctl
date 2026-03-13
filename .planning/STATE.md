---
gsd_state_version: 1.0
milestone: v1.17
milestone_name: CAKE Optimization & Benchmarking
status: executing
last_updated: "2026-03-13T18:50:24Z"
last_activity: 2026-03-13 -- Completed 85-01 (fix infrastructure primitives)
progress:
  total_phases: 4
  completed_phases: 1
  total_plans: 3
  completed_plans: 3
  percent: 30
---

# Session State

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-13)

**Core value:** Sub-second congestion detection with 50ms control loops
**Current focus:** Phase 85 - Auto-Fix CLI Integration

## Position

**Milestone:** v1.17 CAKE Optimization & Benchmarking
**Phase:** 85 of 87 (Auto-Fix CLI Integration)
**Plan:** 01 of 02 complete (fix infrastructure primitives)
**Status:** Executing
**Last activity:** 2026-03-13 -- Completed 85-01 (fix infrastructure primitives)

Progress: [###.......] 30%

## Performance Metrics

**Velocity:**

- Total plans completed: 3
- Average duration: 27min
- Total execution time: 1.3 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
| ----- | ----- | ----- | -------- |
| 84    | 2     | 68min | 34min    |
| 85    | 1     | 13min | 13min    |

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
