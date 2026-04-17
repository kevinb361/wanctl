---
phase: 184-dashboard-history-source-surfacing
plan: 02
subsystem: ui
tags: [dashboard, textual, history, metadata-source]
requires:
  - phase: 184-01
    provides: endpoint-local framing statics, state routing, and locked history copy constants
provides:
  - translated success-state source-detail rendering from metadata.source mode and db_paths
  - raw source-diagnostic formatting for success and ambiguous payload states
  - narrowed fetch-error http labels for dashboard history diagnostics
affects: [184-03, 185-01, 185-02]
tech-stack:
  added: []
  patterns: [translated primary-copy helper, raw-vs-translated diagnostic separation]
key-files:
  created: []
  modified: [src/wanctl/dashboard/widgets/history_browser.py]
key-decisions:
  - "Kept the mode translation and db-path rendering in a dedicated _format_source_detail helper so Phase 185 can assert D-06 and D-07 directly without mounting the widget."
  - "Reserved raw metadata.source values for _format_diagnostic_for_payload and _format_diagnostic_for_error so source-detail stays operator-facing while diagnostics remain contract-complete."
patterns-established:
  - "HistoryBrowserWidget success rendering now routes through _format_source_detail for translated mode phrases plus one-path vs many-path formatting."
  - "Diagnostic helpers own all raw mode/db_paths exposure and fetch-error narrowing, while banner/detail copy continues to use HISTORY_COPY constants."
requirements-completed: [DASH-02]
duration: 11 min
completed: 2026-04-14
---

# Phase 184 Plan 02: Metadata Source Surfacing Summary

**Translated `metadata.source` success detail and raw diagnostic formatting now make the dashboard’s endpoint-local history provenance visible without leaking internal mode tokens into the primary label**

## Performance

- **Duration:** 11 min
- **Started:** 2026-04-14T15:26:00Z
- **Completed:** 2026-04-14T15:37:05Z
- **Tasks:** 2
- **Files modified:** 1

## Accomplishments

- Added `_format_source_detail(self, source: dict[str, Any]) -> str` in [history_browser.py](/home/kevin/projects/wanctl/src/wanctl/dashboard/widgets/history_browser.py:213) to implement D-06 mode phrase translation and D-07 one-path vs many-path rendering.
- Wired the success branch in [history_browser.py](/home/kevin/projects/wanctl/src/wanctl/dashboard/widgets/history_browser.py:156) to render `source-detail` from `_format_source_detail` and `source-diagnostic` from `_format_diagnostic_for_payload(payload, http_status=200)`.
- Expanded `_format_diagnostic_for_error(self, exc: BaseException) -> str` and `_format_diagnostic_for_payload(self, payload: dict[str, Any], *, http_status: int) -> str` in [history_browser.py](/home/kevin/projects/wanctl/src/wanctl/dashboard/widgets/history_browser.py:243) to emit the exact D-08 format and narrow timeout, status, connect, and JSON failures.

## D-05 To D-08 Mapping

- D-05 source-field ownership stays in [history_browser.py](/home/kevin/projects/wanctl/src/wanctl/dashboard/widgets/history_browser.py:159), where the success path reads `payload["metadata"]["source"]` directly and passes it to `_format_source_detail`.
- D-06 operator mode translation lives in [history_browser.py](/home/kevin/projects/wanctl/src/wanctl/dashboard/widgets/history_browser.py:213) via `_format_source_detail`, which maps to `HISTORY_COPY.MODE_PHRASE_LOCAL` and `HISTORY_COPY.MODE_PHRASE_MERGED`.
- D-07 db-path rendering also lives in `_format_source_detail`, using the full absolute path for a single element and `Path(...).name` basenames for multi-path lists while preserving payload order.
- D-08 raw diagnostics live in [history_browser.py](/home/kevin/projects/wanctl/src/wanctl/dashboard/widgets/history_browser.py:243) and [history_browser.py](/home/kevin/projects/wanctl/src/wanctl/dashboard/widgets/history_browser.py:268), which are the only helpers that emit raw `mode=` and `db_paths=` values.

## Helper Surface For Phase 185

- `_format_source_detail(self, source: dict[str, Any]) -> str`
- `_format_diagnostic_for_error(self, exc: BaseException) -> str`
- `_format_diagnostic_for_payload(self, payload: dict[str, Any], *, http_status: int) -> str`

These helpers can be called directly on a `HistoryBrowserWidget.__new__(HistoryBrowserWidget)` instance for focused regression assertions without mounting Textual.

## Raw Vs Translated Separation

- `source-detail` is updated only with `_format_source_detail(...)`, which resolves raw `metadata.source.mode` values into `HISTORY_COPY` phrases before rendering.
- `source-diagnostic` is updated only with `_format_diagnostic_for_payload(...)` or `_format_diagnostic_for_error(...)`, which intentionally preserve raw mode and raw path values.
- No `source-banner` or `source-detail` update path writes raw `local_configured_db` or `merged_discovery` tokens directly.

## Task Commits

1. **Task 1: Add _format_source_detail helper implementing D-06 mode phrase + D-07 db_paths rendering rules** - `645c065` (`feat`)
2. **Task 2: Expand _format_diagnostic_for_payload and _format_diagnostic_for_error to full D-08 format with HTTP error narrowing** - `645c065` (`feat`)

## Files Created/Modified

- `src/wanctl/dashboard/widgets/history_browser.py` - Success-state source-detail rendering and full raw diagnostic formatting for success, ambiguous, and fetch-error states.

## Decisions Made

- Kept all new behavior inside `HistoryBrowserWidget` to satisfy the plan without broadening the surface beyond the one owned file.
- Used `Path(str(p)).name` for the multi-path branch exactly as the plan required so basename order matches payload order.
- Annotated the fetch-error helper with `BaseException` so the existing fetch-error call site remains type-correct under `mypy`.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

- `ruff check` initially failed on import ordering after adding `Path`; reordering the imports resolved it without changing behavior.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Plan 184-03 can keep using the same framing block while focusing only on the merged-CLI handoff wording and placement.
- Phase 185 can assert the helper outputs directly for success and fetch-error diagnostics without reintroducing raw tokens into primary copy.

## Self-Check: PASSED
