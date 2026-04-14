---
phase: 184
slug: dashboard-history-source-surfacing
status: approved
nyquist_compliant: true
wave_0_complete: true
created: 2026-04-14
---

# Phase 184 — Validation Strategy

> Reconstructed and completed Nyquist validation contract for Phase 184.
> This phase now has repo-side automated coverage for the previously deferred
> framing and rendered-state checks, so no manual-only validation remains.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | `pytest` |
| **Config file** | `pyproject.toml` |
| **Quick run command** | `.venv/bin/pytest tests/dashboard/test_history_browser.py -q` |
| **Full suite command** | `.venv/bin/pytest tests/dashboard/test_app.py tests/dashboard/test_history_browser.py tests/dashboard/test_history_state.py -q` |
| **Estimated runtime** | ~16 seconds |

## Sampling Rate

- **After every task commit:** Run `.venv/bin/pytest tests/dashboard/test_history_browser.py -q`
- **After every plan wave:** Run `.venv/bin/pytest tests/dashboard/test_app.py tests/dashboard/test_history_browser.py tests/dashboard/test_history_state.py -q`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 20 seconds

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 184-01-01 | 01 | 1 | `DASH-01` | — | Pure classifier exports locked copy and the five-state routing needed for endpoint-local framing | unit | `.venv/bin/ruff check src/wanctl/dashboard/widgets/history_state.py && .venv/bin/mypy src/wanctl/dashboard/widgets/history_state.py && .venv/bin/python -c "from wanctl.dashboard.widgets.history_state import classify_history_state, HistoryState, HISTORY_COPY; assert classify_history_state(Exception('x')) == HistoryState.FETCH_ERROR; assert classify_history_state({}) == HistoryState.SOURCE_MISSING; assert classify_history_state({'metadata':{'source':{}}}) == HistoryState.MODE_MISSING; assert classify_history_state({'metadata':{'source':{'mode':'local_configured_db'}}}) == HistoryState.DB_PATHS_MISSING; assert classify_history_state({'metadata':{'source':{'mode':'local_configured_db','db_paths':['/a']}}}) == HistoryState.SUCCESS; assert HISTORY_COPY.BANNER_SUCCESS == 'Endpoint-local history from the connected autorate daemon.'"` | ✅ | ✅ green |
| 184-01-02 | 01 | 1 | `DASH-01` | — | Mounted History widget exposes framing surfaces and keeps them ahead of the selector | integration | `.venv/bin/pytest tests/dashboard/test_history_browser.py -q -k framing_block_before_time_range` | ✅ | ✅ green |
| 184-01-03 | 01 | 1 | `DASH-01` | — | History widget imports the classifier and keeps the routing helpers in place | static + lint | `.venv/bin/ruff check src/wanctl/dashboard/widgets/history_browser.py && .venv/bin/mypy src/wanctl/dashboard/widgets/history_browser.py && .venv/bin/python -c "import ast, sys; tree = ast.parse(open('src/wanctl/dashboard/widgets/history_browser.py').read()); names = {n.name for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}; assert 'classify_history_state' not in names; assert '_format_diagnostic_for_error' in names and '_format_diagnostic_for_payload' in names"` | ✅ | ✅ green |
| 184-02-01 | 02 | 1 | `DASH-02` | — | Success-state detail translates source modes and path context into operator-facing wording | unit | `.venv/bin/ruff check src/wanctl/dashboard/widgets/history_browser.py && .venv/bin/mypy src/wanctl/dashboard/widgets/history_browser.py && .venv/bin/python -c "from wanctl.dashboard.widgets.history_browser import HistoryBrowserWidget; w = HistoryBrowserWidget.__new__(HistoryBrowserWidget); assert w._format_source_detail({'mode':'local_configured_db','db_paths':['/var/lib/wanctl/spectrum.db']}) == 'Connected endpoint local database — /var/lib/wanctl/spectrum.db'; assert w._format_source_detail({'mode':'merged_discovery','db_paths':['/a/spectrum.db','/b/att.db','/c/foo.db']}) == 'Discovered database set on this endpoint — 3 databases: spectrum.db, att.db, foo.db'; assert w._format_source_detail({'mode':'merged_discovery','db_paths':['/only.db']}) == 'Discovered database set on this endpoint — /only.db'; print('ok')"` | ✅ | ✅ green |
| 184-02-02 | 02 | 1 | `DASH-02` | — | Success, fetch-error, and ambiguous-source branches render exact `source-diagnostic` strings repo-side | integration | `.venv/bin/pytest tests/dashboard/test_history_browser.py -q -k "success_state_renders_banner_detail_and_handoff or fetch_error_state_clears_table_and_shows_unavailable_banner or source_missing_state_shows_ambiguous_banner_and_preserves_handoff"` | ✅ | ✅ green |
| 184-03-01 | 03 | 2 | `DASH-03` | — | Merged CLI handoff text is locked and immutable after compose | unit + static | `.venv/bin/ruff check src/wanctl/dashboard/widgets/history_browser.py && .venv/bin/mypy src/wanctl/dashboard/widgets/history_browser.py && .venv/bin/python -c "from wanctl.dashboard.widgets.history_browser import HistoryBrowserWidget; assert HistoryBrowserWidget.HANDOFF_TEXT == 'For merged cross-WAN proof, run: python3 -m wanctl.history'; print('ok')" && .venv/bin/python -c "import ast; tree = ast.parse(open('src/wanctl/dashboard/widgets/history_browser.py').read());\nfor node in ast.walk(tree):\n    if isinstance(node, ast.AsyncFunctionDef) and node.name == '_fetch_and_populate':\n        for sub in ast.walk(node):\n            if isinstance(sub, ast.Constant) and isinstance(sub.value, str) and 'source-handoff' in sub.value:\n                raise SystemExit('FAIL: _fetch_and_populate references source-handoff');\nprint('ok')"` | ✅ | ✅ green |
| 184-03-02 | 03 | 2 | `DASH-03` | — | Dashboard app mounts the History widget inside the History tab and preserves the handoff/copy invariants | integration | `.venv/bin/pytest tests/dashboard/test_app.py tests/dashboard/test_history_browser.py tests/dashboard/test_history_state.py -q` | ✅ | ✅ green |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

## Wave 0 Requirements

Existing infrastructure covers all phase requirements.

## Manual-Only Verifications

All phase behaviors have automated verification.

## Validation Audit 2026-04-14

| Metric | Count |
|--------|-------|
| Gaps found | 3 |
| Resolved | 3 |
| Escalated | 0 |

### Gap Closure Notes

- Added mounted compose-tree coverage proving `source-banner`, `source-detail`,
  `source-handoff`, and `source-diagnostic` are mounted ahead of the time-range
  selector.
- Extended widget regressions to assert exact `source-diagnostic` text for
  success, fetch-error, and ambiguous-source states.
- Reused the existing `test_history_tab_contains_history_browser` app test as
  the app-level mount proof for the History widget.

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 20s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved 2026-04-14
