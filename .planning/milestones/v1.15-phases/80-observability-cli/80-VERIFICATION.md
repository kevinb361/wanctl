---
phase: 80-observability-cli
verified: 2026-03-12T17:10:00Z
status: passed
score: 9/9 must-haves verified
re_verification: false
---

# Phase 80: Observability & CLI Verification Report

**Phase Goal:** Operators can inspect alerting state via health endpoints and query alert history via CLI
**Verified:** 2026-03-12T17:10:00Z
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| #  | Truth | Status | Evidence |
|----|-------|--------|----------|
| 1  | Health endpoint /health response includes an 'alerting' section | VERIFIED | `health["alerting"] = alerting` in health_check.py:209 and steering/health.py:280 |
| 2  | Alerting section shows enabled status (true/false) | VERIFIED | `ae._enabled` serialized in both endpoints; `enabled=False` default when no controller |
| 3  | Alerting section shows total fired alert count since startup | VERIFIED | `fire_count` property on AlertEngine (line 71-73 alert_engine.py), exposed in both health endpoints |
| 4  | Alerting section shows active cooldowns with seconds remaining per (type, wan) | VERIFIED | `ae.get_active_cooldowns()` called in both endpoints; formatted as `{type, wan, remaining_sec}` |
| 5  | wanctl-history --alerts displays fired alerts from SQLite | VERIFIED | `--alerts` flag in create_parser(), triggers `query_alerts()` path in main() |
| 6  | Each alert row shows timestamp, type, severity, WAN, and details | VERIFIED | `format_alerts_table()` uses Timestamp/Type/Severity/WAN/Details columns |
| 7  | Alert history is filterable by --last time range | VERIFIED | `start_ts`/`end_ts` passed from args.last into `query_alerts()` |
| 8  | Alert history is filterable by --from/--to absolute range | VERIFIED | `--from`/`--to` flags parse to `from_ts`/`to_ts`; used as `start_ts`/`end_ts` in alert query path |
| 9  | wanctl-history --alerts --json outputs JSON format | VERIFIED | `format_alerts_json()` called when `args.json_output` is True |

**Score:** 9/9 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `src/wanctl/alert_engine.py` | fire_count property for total alerts fired | VERIFIED | `_fire_count: int = 0` in __init__, `@property fire_count` at line 70-73, incremented after cooldown check at line 107 |
| `src/wanctl/health_check.py` | alerting section in autorate health response | VERIFIED | Substantive implementation at lines 193-209; builds alerting dict with enabled/fire_count/active_cooldowns |
| `src/wanctl/steering/health.py` | alerting section in steering health response | VERIFIED | Substantive implementation at lines 275-288; same structure as autorate endpoint |
| `tests/test_health_alerting.py` | Tests for alerting section in both health endpoints | VERIFIED | 11 tests covering fire_count behavior, autorate alerting, steering alerting, and no-controller edge cases; all 11 pass |
| `src/wanctl/storage/reader.py` | query_alerts() function for reading alerts table | VERIFIED | `query_alerts()` at line 102 with full SQL SELECT, WHERE clause builder, JSON details parsing, ORDER BY timestamp DESC |
| `src/wanctl/history.py` | --alerts flag and alert table formatting | VERIFIED | `--alerts` argparse flag at line 336, `format_alerts_table()` at line 233, `format_alerts_json()` at line 265, alert query path at line 413-430 |
| `tests/test_alert_history.py` | Tests for query_alerts and --alerts CLI flag | VERIFIED | 13 tests (8 unit + 5 CLI); all 13 pass |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `src/wanctl/health_check.py` | `alert_engine.get_active_cooldowns()` | `wan_controllers[0]["controller"].alert_engine` in `_get_health_status` | WIRED | `ae = self.controller.wan_controllers[0]["controller"].alert_engine; cooldowns = ae.get_active_cooldowns()` at lines 198-200; protected by `isinstance(ae, AlertEngine)` guard |
| `src/wanctl/steering/health.py` | `alert_engine.get_active_cooldowns()` | `self.daemon.alert_engine` in `_get_health_status` | WIRED | `ae = self.daemon.alert_engine; cooldowns = ae.get_active_cooldowns()` at lines 277-279; protected by `isinstance(ae, AlertEngine)` guard |
| `src/wanctl/history.py` | `src/wanctl/storage/reader.py` | `query_alerts()` import and call | WIRED | `from wanctl.storage.reader import query_alerts` at line 415; called at line 417 with all filter params |
| `src/wanctl/storage/reader.py` | alerts table | SQL SELECT from alerts | WIRED | `SELECT id, timestamp, alert_type, severity, wan_name, details, delivery_status FROM alerts WHERE 1=1` at lines 142-145 |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| INFRA-06 | 80-01-PLAN.md | Health endpoint exposes alerting state (enabled, recent alert count, active cooldowns) | SATISFIED | Both /health endpoints return `alerting` section with `enabled`, `fire_count`, `active_cooldowns`; verified by 11 passing tests |
| INFRA-04 | 80-02-PLAN.md | Alert history queryable via wanctl-history CLI (--alerts flag) | SATISFIED | `wanctl-history --alerts` implemented with time range filtering, JSON output, and table format; verified by 13 passing tests |

No orphaned requirements: REQUIREMENTS.md traceability table maps only INFRA-04 and INFRA-06 to Phase 80.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `src/wanctl/storage/reader.py` | 76-77 | `placeholders` variable | Info | SQL placeholder generation (legitimate, not a stub) |

No blockers or warnings. The `placeholders` match is legitimate SQL parameterization in `query_metrics()`, unrelated to Phase 80 work.

### Human Verification Required

None. All observable behaviors are verifiable programmatically via the 24 passing tests (11 health alerting + 13 alert history). No visual, real-time, or external service behaviors require human testing.

### Gaps Summary

No gaps. All 9 truths verified, all 7 artifacts exist and are substantive, all 4 key links are wired. 24/24 new tests pass. 128/128 regression tests pass. Both requirement IDs (INFRA-04, INFRA-06) are satisfied with implementation evidence.

---

_Verified: 2026-03-12T17:10:00Z_
_Verifier: Claude (gsd-verifier)_
