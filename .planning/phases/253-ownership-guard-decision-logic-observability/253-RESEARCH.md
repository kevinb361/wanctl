---
phase: 253
slug: ownership-guard-decision-logic-observability
status: complete
created: 2026-06-19
---

# Phase 253 — Research

## Research Question

What do we need to know to plan Phase 253 well: ownership guard, multi-signal/hysteretic route decision logic, startup/circuit-breaker behavior, and route ownership observability, while preserving SAFE-19 and keeping Netwatch interim owner?

## Key Findings

### 1. Phase 252 created only inert building blocks

Phase 252 shipped:

- `route_management` config loading in `SteeringConfig` with missing-section defaults: disabled/off/no routes.
- `RouteManager.plan_or_apply()` that emits dry-run intended actions and blocks active mode.
- `RouterOSREST` support for mocked `/ip route print`, `/ip route enable`, and `/ip route disable` command forms.
- Validation that rejects `route_management.mode: active` by default.

Planning implication: Phase 253 must intentionally open only guarded/canaried code paths. It should not casually flip validation to allow active mode without a named acknowledgement and runtime guard.

### 2. Existing steering state machine already has multi-signal hysteresis, but it controls mangle steering

`src/wanctl/steering/congestion_assessment.py` and `SteeringDaemon.update_state_machine()` already use:

- RTT delta EWMA;
- CAKE drops;
- queue depth;
- RED/YELLOW/GREEN state;
- `red_samples_required` and `green_samples_required` hysteresis counters;
- optional confidence scoring with WAN zone contribution.

That logic currently calls `execute_steering_transition()` to enable/disable the mangle steering rule. Route ownership must not fork in a way that replaces this with a one-sample Netwatch clone.

Planning implication: add a separate route-decision policy that consumes these existing signals/counters or their summaries and returns intended route actions, rather than adding one-off probes or changing core threshold semantics.

### 3. Router communication failure handling already has patterns to reuse

`SteeringDaemon.execute_steering_transition()` and `collect_cake_stats()` use `RouterConnectivityState` to record successes/failures and fail the transition when router commands fail. `run_daemon_loop()` tracks consecutive cycle failures and eventually surrenders watchdog notification.

Planning implication: route active mutation should have its own circuit-breaker state at the route-management layer, but reuse the fail-closed posture: no false state update after failed route read/apply, visible failure reason, and health output that tells operators whether mutation is blocked.

### 4. Startup reconciliation belongs before active mutation, not after

Phase 253 success criteria require startup reconciliation to read current route state and prior decision state before active mutation can run. The Phase 252 REST route boundary can read routes by comment/id, but no current `RouteManager` state model tracks:

- current route enabled/disabled state;
- last intended action;
- last applied action;
- last apply success/failure;
- reconciliation timestamp/result;
- circuit-breaker status.

Planning implication: Plan 253-02 should add route-management state dataclasses and tests for reconciliation failure/success before wiring active apply. A failed reconciliation must keep active mutation blocked.

### 5. Netwatch/script conflict detection can be mocked through RouterOS command output

Phase 251 found enabled Netwatch entries and route-mutating scripts. Runtime guard needs to inspect:

- Netwatch entries, likely `/tool netwatch print detail` or equivalent REST command form;
- scripts, likely `/system script print detail` or equivalent;
- enabled state and script references;
- script source strings containing route mutation commands.

Planning implication: add a guard module that accepts router client command output and parses JSON/list dicts when available, with conservative fallback behavior. Tests should cover no conflict, enabled conflict, disabled/non-mutating entries ignored, ambiguous/unparseable output fail-closed, and router read failure fail-closed.

### 6. Observability already has a health facade and compact operator summary

`SteeringDaemon.get_health_data()` is the intended facade for `src/wanctl/steering/health.py`; health currently adds steering/congestion/decision/counters/router/runtime/storage/alerting sections. `operator_summary.py` consumes `summary.rows` for compact output.

Planning implication: add route ownership data via `SteeringDaemon.get_health_data()` and build additive health sections in `steering/health.py`. Then include compact route owner/guard/circuit status in `summary.rows[*].route_owner` or `route_management` fields and render them in operator summary notes.

### 7. Config validation must evolve carefully

`src/wanctl/check_steering_validators.py` currently rejects active mode unconditionally. Phase 253 can add explicit acknowledgement config, but must preserve fail-closed validation for these unsafe combinations:

- active mode with no routes;
- active mode with missing acknowledgement;
- active mode with guard disabled/skipped by default;
- active mode with invalid thresholds/counters;
- route entries without comment/id anchors;
- acknowledgement true while `enabled: false` should warn or be harmless, not enable mutation.

Planning implication: put config schema/validator changes in Plan 253-01 with tests before route decision/apply wiring.

## Risks / Pitfalls

- Accidentally enabling active route mutation while Netwatch is still owner.
- Adding a route decision path that bypasses existing multi-signal/hysteresis behavior.
- Treating failed RouterOS reads as safe to proceed.
- Updating health payload by renaming/removing existing keys, breaking consumers.
- Running live RouterOS or Netwatch commands during tests or planning; Phase 253 must remain mock-only.
- Making migration acknowledgement too generic or easy to miss in config review.

## Validation Architecture

Phase 253 should validate through unit and focused integration-style tests only. No live infrastructure is required.

Automated checks:

1. New guard tests for Netwatch/script conflict detection and fail-closed router read failures.
2. Config validator tests for active-mode acknowledgement and unsafe combinations.
3. Decision-policy tests for multi-signal/consecutive/hysteretic intended actions.
4. Startup reconciliation/circuit-breaker tests proving active apply is blocked until route state is known and circuit is closed.
5. RouteManager tests proving active mutation only calls router commands when guard/reconciliation/circuit preconditions pass, and failure does not mark changed/applied.
6. Health/operator summary tests for route ownership/guard/circuit/last-action fields.
7. Targeted lint, full mypy, and `git diff --check`.

Manual/live checks:

- None in Phase 253. Live dry-run observation and canary approval are Phase 254.

## RESEARCH COMPLETE
