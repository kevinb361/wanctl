---
gsd_state_version: 1.0
milestone: v1.16
milestone_name: Validation & Operational Confidence
status: completed
last_updated: "2026-03-13T04:12:59.275Z"
last_activity: 2026-03-13 - Completed 83-01 CAKE qdisc audit CLI tool
progress:
  total_phases: 4
  completed_phases: 4
  total_plans: 5
  completed_plans: 5
---

# Session State

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-12)

**Core value:** Sub-second congestion detection with 50ms control loops
**Current focus:** v1.16 Phase 83 -- CAKE Qdisc Audit (1/1 plans complete) -- MILESTONE COMPLETE

## Position

**Milestone:** v1.16 Validation & Operational Confidence -- COMPLETE
**Phase:** 83 of 83 (CAKE Qdisc Audit) -- COMPLETE
**Plan:** 1 of 1 (83-01 complete)
**Status:** Milestone complete
**Last activity:** 2026-03-13 - Completed 83-01 CAKE qdisc audit CLI tool

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
- [82-01] detect_config_type raises ValueError (not SystemExit) for testability; main() catches
- [82-01] KNOWN_STEERING_PATHS: ~100 paths from SCHEMA + imperative loads + legacy + future
- [82-01] Cross-config depth: file existence + wan_name match only (no recursive validation)
- [82-01] format_results config_type param defaults to "autorate" for backward compat
- [82-02] --json replaces text output entirely (only JSON on stdout, no headers/summary)
- [82-02] --json and --quiet are independent (--quiet only affects text mode)
- [82-02] JSON suggestion key omitted when None (not set to null)
- [82-02] severity values are lowercase enum values (pass, warn, error)
- [83-01] SimpleNamespace wraps extracted router config dict for get_router_client() compatibility
- [83-01] Max-limit diff shows informational PASS note (not ERROR) since max-limit changes dynamically during congestion
- [83-01] Steering configs skip max-limit comparison entirely (no ceiling config)
- [83-01] SSH connectivity falls back to run_cmd when test_connection() unavailable
- [83-01] Mangle rule check via REST uses \_find_mangle_rule_id, SSH uses print where comment filter

### Known Issues

None.

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
