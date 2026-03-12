---
gsd_state_version: 1.0
milestone: v1.16
milestone_name: Validation & Operational Confidence
status: planning
last_updated: "2026-03-12T20:12:55.237Z"
last_activity: 2026-03-12 - Completed quick task 7: Fix flapping alert bugs
progress:
  total_phases: 3
  completed_phases: 2
  total_plans: 2
  completed_plans: 2
---

# Session State

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-12)

**Core value:** Sub-second congestion detection with 50ms control loops
**Current focus:** v1.16 Phase 81 -- Config Validation Foundation (plan 1/1 complete)

## Position

**Milestone:** v1.16 Validation & Operational Confidence
**Phase:** 81 of 83 (Config Validation Foundation) -- COMPLETE
**Plan:** 1 of 1 (complete)
**Status:** Ready to plan
**Last activity:** 2026-03-12 - Completed quick task 7: Fix flapping alert bugs

## Accumulated Context

### Key Decisions

- Research recommends zero new deps -- reuse BaseConfig, validate_schema, argparse, tabulate
- Two standalone CLI tools (check-config, check-cake) following wanctl-history pattern
- Backward compat is primary constraint -- new validation must not reject existing production configs
- Router probes are GET-only -- never modify router state from CLI tools
- [81-01] Never instantiate Config() -- only access SCHEMA class attributes to avoid daemon side effects
- [81-01] Env var ${VAR} unset is WARN not ERROR (environment-specific, not config bug)
- [81-01] alerting.rules.\* sub-keys skip unknown-key checking (dynamic per-alert-type config)
- [81-01] Exit codes follow ruff/mypy convention: 0=pass, 1=errors, 2=warnings-only

### Known Issues

None.

### Blockers

None.

### Quick Tasks Completed

| #   | Description                                                                                       | Date       | Commit  | Directory                                                                                         |
| --- | ------------------------------------------------------------------------------------------------- | ---------- | ------- | ------------------------------------------------------------------------------------------------- |
| 7   | Fix flapping alert bugs: rule name mismatch, deque not cleared, threshold not calibrated for 20Hz | 2026-03-12 | 98f0dab | [7-fix-flapping-alert-bugs-rule-name-mismat](./quick/7-fix-flapping-alert-bugs-rule-name-mismat/) |

### Pending Todos

5 todos in `.planning/todos/pending/`:

- Research IRTT as RTT measurement alternative (general) -- deferred to future milestone
- Integration test for router communication (testing) -- low priority, contract tests added in v1.12
- Narrow layout truncates WAN panel content (dashboard/ui) -- low priority, wide layout works fine
- Investigate LXC container network optimizations (infrastructure) -- RTT accuracy depends on low-latency container networking
- Audit CAKE qdisc configuration for Spectrum and ATT links (networking) -- verify link-layer compensation and overhead settings
