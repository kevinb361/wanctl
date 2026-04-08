---
phase: 147-interface-decoupling
verified: 2026-04-08T18:30:00Z
status: gaps_found
score: 3/4 must-haves verified
overrides_applied: 0
re_verification:
  previous_status: passed
  previous_score: 4/4
  gaps_closed: []
  gaps_remaining:
    - "No module directly accesses private attributes of another module's classes"
  regressions:
    - "check_cake.py reverted to _find_mangle_rule_id (private name) in commit 20b5c5e, breaking make check-boundaries"
gaps:
  - truth: "No module directly accesses private attributes (_prefixed) of another module's classes"
    status: failed
    reason: |
      Two distinct violations of this criterion exist:

      1. REGRESSION (commit 20b5c5e): check_cake.py:699 calls client._find_mangle_rule_id()
         using the old private name. This commit (\"fix: steering failover broken since v1.21\")
         was applied AFTER Phase 147-04 promoted the method to find_mangle_rule_id in
         routeros_rest.py. The hasattr check on line 698 uses \"_find_mangle_rule_id\" which
         now returns False for all REST clients, silently falling to the SSH-fallback path.
         python scripts/check_private_access.py reports: \"1 violations found (0 in allowlist, 1 new)\".

      2. CHECKER FALSE NEGATIVE (pre-existing): wan_controller.py accesses
         self.alert_engine._rules at 7 call sites (lines 2047, 2096, 2148, 2188, 2246, 2298,
         2328). AlertEngine is defined in alert_engine.py (a different module). The boundary
         checker's \"chained-expression inside same-file class\" exclusion silently skips these
         because they appear inside WANController method bodies -- but the chained object
         (alert_engine) is an imported cross-module instance. These were not eliminated by
         Phase 147.
    artifacts:
      - path: "src/wanctl/check_cake.py"
        issue: "line 698-699: hasattr(client, \"_find_mangle_rule_id\") and call use old private name; routeros_rest.py has public find_mangle_rule_id since Phase 147-04 (commit 2a12d43)"
      - path: "src/wanctl/wan_controller.py"
        issue: "7 cross-module accesses to self.alert_engine._rules (lines 2047, 2096, 2148, 2188, 2246, 2298, 2328) evade AST checker via chained-expression exclusion"
    missing:
      - "Restore check_cake.py to use public find_mangle_rule_id: change hasattr(client, \"_find_mangle_rule_id\") to hasattr(client, \"find_mangle_rule_id\") and call client.find_mangle_rule_id(mangle_comment)"
      - "Add AlertEngine.get_rule_config(rule_key) public accessor and replace all self.alert_engine._rules.get(key, {}) calls in wan_controller.py"
---

# Phase 147: Interface Decoupling Verification Report

**Phase Goal:** Modules communicate through well-defined interfaces, reducing the number of direct cross-module attribute accesses
**Verified:** 2026-04-08T18:30:00Z
**Status:** gaps_found
**Re-verification:** Yes — this is a re-verification; prior VERIFICATION.md (2026-04-07T14:00:00Z) claimed status: passed (4/4), but SC1 has since regressed via commit 20b5c5e.

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| SC1 | No module directly accesses private attributes (_prefixed) of another module's classes | FAILED | `python scripts/check_private_access.py src/wanctl/` exits 1: "1 violations found (0 in allowlist, 1 new)" — check_cake.py:699 uses client._find_mangle_rule_id. Additionally 7 cross-module self.alert_engine._rules accesses in wan_controller.py evade AST detection. |
| SC2 | Key integration boundaries (router transport, state persistence, metrics) have clear interface definitions | VERIFIED | interfaces.py defines 4 runtime-checkable Protocols (HealthDataProvider, Reloadable, TunableController, ThreadManager). WANController, QueueController, SteeringDaemon each have get_health_data() facades. routeros_rest.py has public find_mangle_rule_id(). |
| SC3 | Import graphs show reduced fan-in on formerly tightly-coupled modules | VERIFIED | autorate_continuous.py: zero wc._ accesses (uses reload(), shutdown_threads(), get_current_params(), get_parameter_locks()). health_check.py: zero wan_controller._ or qc._ accesses (uses get_health_data()). steering/health.py: zero daemon._ AST-detectable accesses (uses get_health_data()). |
| SC4 | All existing tests pass unchanged (no behavioral regression) | VERIFIED | `.venv/bin/pytest tests/steering/test_steering_daemon.py tests/steering/test_steering_health.py -q`: 316 passed, 0 failed, 32.61s. All 46 steering test failures fixed by Plan 05. Ghost file tests/test_steering_health.py confirmed absent. |

**Score:** 3/4 success criteria verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `src/wanctl/interfaces.py` | Protocol definitions for module boundaries | VERIFIED | 4 runtime-checkable Protocol classes: HealthDataProvider (line 21), Reloadable (line 37), TunableController (line 53), ThreadManager (line 70). Imports only from stdlib/typing. |
| `scripts/check_private_access.py` | AST-based cross-module private access detector | PARTIAL | Script exists with empty ALLOWLIST and check_file() function. But currently exits 1 due to regression in check_cake.py. Also has false negative: chained-expression exclusion at line 184 silently skips wan_controller.py's self.alert_engine._rules accesses. |
| `Makefile` | check-boundaries target in CI | VERIFIED | `check-boundaries:` target at line 60-61, included in `ci:` recipe at line 30. |
| `tests/test_boundary_check.py` | Tests for boundary check script | VERIFIED | 8 tests confirmed present (per 147-01-SUMMARY.md). |
| `src/wanctl/wan_controller.py` | Public facade methods | VERIFIED | 15 facade methods/properties in PUBLIC FACADE API section: reload, shutdown_threads, set_irtt_thread, enable_profiling, init_fusion_healer, get/set/clear_pending_observation, get_parameter_locks, tuning_layer_index (property+setter), is_tuning_enabled, get_current_params, get_metrics_writer, get_health_data. |
| `src/wanctl/signal_processing.py` | Public properties | VERIFIED | sigma_threshold property+setter, window_size property, resize_window() method. |
| `src/wanctl/reflector_scorer.py` | Public min_score property | VERIFIED | min_score property+setter present. |
| `src/wanctl/irtt_thread.py` | Public cadence_sec property | VERIFIED | cadence_sec property present. |
| `src/wanctl/storage/writer.py` | Public db_path + get_instance() | VERIFIED | db_path property and get_instance() classmethod present. |
| `src/wanctl/queue_controller.py` | get_health_data() method | VERIFIED | Present, returns hysteresis dict per Plan 03. |
| `src/wanctl/alert_engine.py` | enabled property | VERIFIED | @property def enabled() returning self._enabled present. |
| `src/wanctl/health_check.py` | Zero cross-module private accesses | VERIFIED | `grep -n 'wan_controller\._\|qc\._\|ae\._' src/wanctl/health_check.py` returns 0 matches. |
| `src/wanctl/autorate_continuous.py` | Zero cross-module private accesses on WANController | VERIFIED | `grep -n 'wc\._\|wan_info\["controller"\]\._' src/wanctl/autorate_continuous.py` returns 0 matches. |
| `src/wanctl/steering/daemon.py` | get_health_data() + public methods | VERIFIED | get_health_data() at line 1242, is_wan_grace_period_active() at line 1297, get_effective_wan_zone() at line 1301. BaselineLoader: get_wan_zone_age() at line 947, is_wan_zone_stale() at line 958. |
| `src/wanctl/steering/health.py` | Zero AST-detectable private accesses | VERIFIED | No self.daemon._ attribute accesses detected by AST checker. Uses self.daemon.get_health_data(). Note: line 212 has getattr(self.daemon.cake_reader, "_is_linux_cake", False) which evades AST detection (WR-03 from code review). |
| `src/wanctl/routeros_rest.py` | Public find_mangle_rule_id | VERIFIED | `def find_mangle_rule_id(` at line 585 (no underscore). |
| `src/wanctl/check_cake.py` | Uses public find_mangle_rule_id | FAILED | Line 698: `hasattr(client, "_find_mangle_rule_id")` uses old private name. Line 699: `client._find_mangle_rule_id(mangle_comment)` calls private method. Regressed in commit 20b5c5e. |
| `tests/steering/test_steering_daemon.py` | Updated for renamed methods | VERIFIED | 259 tests pass. Uses is_wan_grace_period_active() and get_effective_wan_zone() (public names), get_instance.return_value for MetricsWriter. |
| `tests/steering/test_steering_health.py` | Updated for get_health_data() facade | VERIFIED | 57 tests pass. _make_health_data() helper present, daemon.get_health_data.return_value pattern used. Zero old private attr patterns on daemon mock. |
| `tests/test_steering_health.py` | Ghost file deleted | VERIFIED | File does not exist. |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `autorate_continuous.py` | `wan_controller.py` | Public facade (reload, get_current_params, etc.) | VERIFIED | wc.reload(), wc.shutdown_threads(), wc.get_current_params(), wc.get_parameter_locks() all confirmed present. |
| `health_check.py` | `wan_controller.py` | get_health_data() call | VERIFIED | health_data = wan_controller.get_health_data() present. |
| `health_check.py` | `queue_controller.py` | get_health_data() call | VERIFIED | qc.get_health_data() present. |
| `steering/health.py` | `steering/daemon.py` | get_health_data() call | VERIFIED | self.daemon.get_health_data() confirmed. |
| `check_cake.py` | `routeros_rest.py` | public find_mangle_rule_id() | FAILED | check_cake.py line 698-699 uses old private name _find_mangle_rule_id; boundary check fails with 1 new violation. |
| `Makefile` | `scripts/check_private_access.py` | check-boundaries target | VERIFIED | Target confirmed at lines 60-61. |
| `tests/steering/test_steering_daemon.py` | `src/wanctl/steering/daemon.py` | Public method names (no underscore) | VERIFIED | 316 steering tests pass. |

### Data-Flow Trace (Level 4)

Not applicable — pure interface/coupling refactor. No data pipelines or UI rendering affected. Facades pass through data structurally identical to what was previously accessed directly.

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Boundary check exits 0 (SC1) | `python scripts/check_private_access.py src/wanctl/` | "1 violations found (0 in allowlist, 1 new)" — check_cake.py:699 | FAIL |
| Steering tests pass (SC4) | `.venv/bin/pytest tests/steering/test_steering_daemon.py tests/steering/test_steering_health.py -q` | 316 passed, 0 failed | PASS |
| Ghost file absent | `test ! -f tests/test_steering_health.py` | exits 0 (file absent) | PASS |
| health_check.py zero private accesses | `grep 'wan_controller\._' src/wanctl/health_check.py` | 0 matches | PASS |
| autorate_continuous.py zero private accesses | `grep 'wc\._' src/wanctl/autorate_continuous.py` | 0 matches | PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| CPLX-03 | 147-01 through 147-05 | Tight coupling between modules is identified and reduced with cleaner interfaces | PARTIAL | 3/4 success criteria met. SC1 fails because check_cake.py regressed to using _find_mangle_rule_id (private name) in commit 20b5c5e, and 7 self.alert_engine._rules accesses in wan_controller.py evade the boundary checker. |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `src/wanctl/check_cake.py` | 698-699 | `hasattr(client, "_find_mangle_rule_id")` + call | Blocker | SC1 failure; make check-boundaries exits 1; wanctl-check-cake --type steering silently falls to SSH path for all REST clients |
| `src/wanctl/wan_controller.py` | 2047,2096,2148,2188,2246,2298,2328 | `self.alert_engine._rules` (7x) | Blocker | Cross-module private access on AlertEngine (defined in alert_engine.py) that the AST checker silently misses due to chained-expression exclusion false negative |
| `src/wanctl/steering/health.py` | 212 | `getattr(self.daemon.cake_reader, "_is_linux_cake", False)` | Warning | getattr-based private access evades AST checker; same pattern noted as WR-03 in code review |

### Human Verification Required

None. All verification performed programmatically.

### Gaps Summary

**Root cause:** commit 20b5c5e ("fix: steering failover broken since v1.21") applied on 2026-04-07T20:54 reverted check_cake.py from the Phase 147 public-API fix back to the old private method name. This happened AFTER the prior VERIFICATION.md was written (which reflected state at commit 140daac). The prior verification was correct at the time it was written; this is a post-verification regression.

**Gap 1 (regression — SC1):** check_cake.py must be restored: change `hasattr(client, "_find_mangle_rule_id")` to `hasattr(client, "find_mangle_rule_id")` and `client._find_mangle_rule_id(mangle_comment)` to `client.find_mangle_rule_id(mangle_comment)`. The docstring on line 690 also needs updating. This also restores `make check-boundaries` to exit 0.

**Gap 2 (pre-existing false negative — SC1):** 7 cross-module accesses to `self.alert_engine._rules` in wan_controller.py were not eliminated by Phase 147. The AST checker's "chained-expression inside same-file class" exclusion incorrectly skips these because they appear inside WANController methods, even though alert_engine is a cross-module import. Fix requires adding `AlertEngine.get_rule_config(rule_key)` accessor and replacing the 7 call sites.

Both gaps must be closed for SC1 to pass and `make check-boundaries` to exit 0.

**Re-verification summary:**

- **SC4 gap from prior verification:** Fully closed. 316 steering tests pass (259 daemon + 57 health). Plan 05 fix confirmed working.
- **New SC1 regression:** Introduced after prior verification by commit 20b5c5e. check_cake.py reverted to private method name.
- **Pre-existing SC1 false negative (WR-01):** 7 self.alert_engine._rules accesses in wan_controller.py were never caught or fixed by Phase 147. The boundary checker's exclusion logic has a gap here.

---

_Verified: 2026-04-08T18:30:00Z_
_Verifier: Claude (gsd-verifier)_
