---
phase: 184-dashboard-history-source-surfacing
verified: 2026-04-14T21:30:00Z
status: human_needed
score: 7/7 must-haves verified
overrides_applied: 0
deferred:
  - truth: "Focused regression coverage for dashboard history source labeling and failure behavior exists"
    addressed_in: "Phase 185"
    evidence: "Phase 185 goal: 'Lock the new dashboard contract with regression coverage and operator-facing guidance'; plan 185-01: 'Add focused dashboard/history regressions for source labeling and failure behavior'"
human_verification:
  - test: "Open the dashboard History tab and confirm the framing block is plainly visible above the time-range selector"
    expected: "The tab shows source-banner, source-detail, and source-handoff above the Select, with source-diagnostic visually subordinate below the table"
    why_human: "Widget compose order is visible in code, but actual Textual layout and prominence require a mounted UI"
  - test: "Exercise success, fetch-error, and ambiguous-source responses against a running dashboard"
    expected: "Success shows endpoint-local banner plus translated source detail; fetch-error clears rows and shows 'History unavailable.'; ambiguous states keep rows but switch to ambiguous framing"
    why_human: "End-to-end state transitions depend on live widget rendering and runtime fetch behavior, which was not mounted during verification"
---

# Phase 184: Dashboard History Source Surfacing Verification Report

**Phase Goal:** surface endpoint-local framing, metadata.source provenance, and merged-CLI handoff in the dashboard history widget without changing backend history semantics.
**Verified:** 2026-04-14T21:30:00Z
**Status:** human_needed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
| --- | --- | --- | --- |
| 1 | The History tab exposes plainly visible endpoint-local framing instead of implying merged cross-WAN scope. | ✓ VERIFIED | [history_browser.py](/home/kevin/projects/wanctl/src/wanctl/dashboard/widgets/history_browser.py:123) mounts `source-banner` before the selector with `HISTORY_COPY.BANNER_SUCCESS`; [history_state.py](/home/kevin/projects/wanctl/src/wanctl/dashboard/widgets/history_state.py:33) defines the locked phrase `Endpoint-local history from the connected autorate daemon.` |
| 2 | Fetch outcomes are classified through a pure five-state helper that can be tested without mounting the widget. | ✓ VERIFIED | [history_state.py](/home/kevin/projects/wanctl/src/wanctl/dashboard/widgets/history_state.py:59) implements `classify_history_state`; [history_browser.py](/home/kevin/projects/wanctl/src/wanctl/dashboard/widgets/history_browser.py:165) routes `_fetch_and_populate` through it; import spot-checks passed for fetch-error, source-missing, mode-missing, db-paths-missing, and success states. |
| 3 | Fetch-error handling shows explicit unavailable framing and clears rows instead of leaving stale history visible. | ✓ VERIFIED | [history_browser.py](/home/kevin/projects/wanctl/src/wanctl/dashboard/widgets/history_browser.py:167) clears the table, updates the banner to `History unavailable.`, sets detail to the merged-proof CLI guidance, sets summary to `No data`, and writes a narrowed diagnostic line. |
| 4 | Successful history rendering surfaces `metadata.source` in operator-facing wording with DB-path-derived context. | ✓ VERIFIED | [history_browser.py](/home/kevin/projects/wanctl/src/wanctl/dashboard/widgets/history_browser.py:220) reads `payload["metadata"]["source"]`; [history_browser.py](/home/kevin/projects/wanctl/src/wanctl/dashboard/widgets/history_browser.py:274) translates `local_configured_db` and `merged_discovery` into operator phrases and formats one-path vs many-path output. |
| 5 | Raw source mode and DB-path internals are confined to the diagnostic surface, not the primary operator label. | ✓ VERIFIED | [history_browser.py](/home/kevin/projects/wanctl/src/wanctl/dashboard/widgets/history_browser.py:222) writes primary detail only via `_format_source_detail`; [history_browser.py](/home/kevin/projects/wanctl/src/wanctl/dashboard/widgets/history_browser.py:329) emits raw `mode=` and `db_paths=` only in `_format_diagnostic_for_payload`; parity/import checks passed. |
| 6 | The widget exposes a clear, always-visible handoff to `python3 -m wanctl.history` for merged cross-WAN proof. | ✓ VERIFIED | [history_browser.py](/home/kevin/projects/wanctl/src/wanctl/dashboard/widgets/history_browser.py:109) exposes `HANDOFF_TEXT`; [history_browser.py](/home/kevin/projects/wanctl/src/wanctl/dashboard/widgets/history_browser.py:125) mounts `source-handoff` above the selector; `_fetch_and_populate` never queries or updates that widget. |
| 7 | Phase 184 leaves backend history semantics unchanged and consumes the existing source metadata contract. | ✓ VERIFIED | The phase’s implementation files are [history_browser.py](/home/kevin/projects/wanctl/src/wanctl/dashboard/widgets/history_browser.py:1) and [history_state.py](/home/kevin/projects/wanctl/src/wanctl/dashboard/widgets/history_state.py:1); backend payload production remains in [health_check.py](/home/kevin/projects/wanctl/src/wanctl/health_check.py:816) and [health_check.py](/home/kevin/projects/wanctl/src/wanctl/health_check.py:862), which still emit `metadata.source.mode` and `metadata.source.db_paths` using the pre-existing `local_configured_db` / `merged_discovery` modes. |

**Score:** 7/7 truths verified

### Deferred Items

Items not yet met but explicitly addressed in later milestone phases.

| # | Item | Addressed In | Evidence |
| --- | --- | --- | --- |
| 1 | Focused regression coverage for dashboard history source labeling and failure behavior | Phase 185 | [ROADMAP.md](/home/kevin/projects/wanctl/.planning/ROADMAP.md:32) defines Phase 185 as regression and operator-alignment work; plan name `185-01` is `Add focused dashboard/history regressions for source labeling and failure behavior`. |

### Required Artifacts

| Artifact | Expected | Status | Details |
| --- | --- | --- | --- |
| `src/wanctl/dashboard/widgets/history_state.py` | Pure state classifier, copy constants, known source modes | ✓ VERIFIED | Exists, substantive, importable, and consumed by `history_browser.py`. |
| `src/wanctl/dashboard/widgets/history_browser.py` | History framing UI, state routing, source formatting, merged-CLI handoff | ✓ VERIFIED | Exists, substantive, mounted by the dashboard app, and wired to backend payload fields. |

### Key Link Verification

| From | To | Via | Status | Details |
| --- | --- | --- | --- | --- |
| `HistoryBrowserWidget._fetch_and_populate` | `classify_history_state` | direct import and call | ✓ WIRED | [history_browser.py](/home/kevin/projects/wanctl/src/wanctl/dashboard/widgets/history_browser.py:28) imports `classify_history_state`; [history_browser.py](/home/kevin/projects/wanctl/src/wanctl/dashboard/widgets/history_browser.py:165) calls it on every fetch outcome. |
| `HistoryBrowserWidget.compose` | `Static(id="source-banner")` / `Static(id="source-handoff")` | yielded before `Select(id="time-range")` | ✓ WIRED | [history_browser.py](/home/kevin/projects/wanctl/src/wanctl/dashboard/widgets/history_browser.py:123) through [history_browser.py](/home/kevin/projects/wanctl/src/wanctl/dashboard/widgets/history_browser.py:126) define the framing block above the selector. |
| `HistoryBrowserWidget` success branch | `metadata.source.mode` / `metadata.source.db_paths` | `_format_source_detail` and `_format_diagnostic_for_payload` | ✓ WIRED | [history_browser.py](/home/kevin/projects/wanctl/src/wanctl/dashboard/widgets/history_browser.py:220) reads the source dict and passes it into the success formatting helpers. |
| Dashboard app History tab | `HistoryBrowserWidget` | `TabPane("History")` mount | ✓ WIRED | [app.py](/home/kevin/projects/wanctl/src/wanctl/dashboard/app.py:199) mounts the widget inside the History tab. |
| Dashboard history fetch | Backend history metadata contract | `/metrics/history` payload fields | ✓ WIRED | [history_browser.py](/home/kevin/projects/wanctl/src/wanctl/dashboard/widgets/history_browser.py:156) fetches `/metrics/history`; [health_check.py](/home/kevin/projects/wanctl/src/wanctl/health_check.py:841) through [health_check.py](/home/kevin/projects/wanctl/src/wanctl/health_check.py:848) return `metadata.source` with `mode` and `db_paths`. |
| `compose` handoff surface | `HISTORY_COPY.HANDOFF` | immutable compose-only mount | ✓ WIRED | [history_browser.py](/home/kevin/projects/wanctl/src/wanctl/dashboard/widgets/history_browser.py:109) exposes `HANDOFF_TEXT`; [history_browser.py](/home/kevin/projects/wanctl/src/wanctl/dashboard/widgets/history_browser.py:125) mounts the handoff once; no later `source-handoff` updates exist in the file. |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
| --- | --- | --- | --- | --- |
| `history_browser.py` | `payload["metadata"]["source"]` | `/metrics/history` response from `health_check._handle_metrics_history` | Yes | ✓ FLOWING |
| `history_browser.py` | `records` / `values_by_metric` | `payload["data"]` from `/metrics/history` | Yes | ✓ FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
| --- | --- | --- | --- |
| Pure classifier handles all five states | `PYTHONPATH=src .venv/bin/python - <<'PY' ... classify_history_state ... PY` | All five state assertions passed | ✓ PASS |
| Success detail and diagnostic formatting match contract examples | `PYTHONPATH=src .venv/bin/python - <<'PY' ... _format_source_detail/_format_diagnostic_for_payload ... PY` | Local-path, merged-path, and raw diagnostic assertions passed | ✓ PASS |
| Handoff text and parity guard remain locked | `PYTHONPATH=src .venv/bin/python - <<'PY' ... HANDOFF_TEXT/_assert_no_parity_language ... PY` | All copy-surface assertions passed | ✓ PASS |
| Touched files remain lint-clean | `.venv/bin/ruff check src/wanctl/dashboard/widgets/history_browser.py src/wanctl/dashboard/widgets/history_state.py` | `All checks passed!` | ✓ PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
| --- | --- | --- | --- | --- |
| `DASH-01` | 184-01 | History tab is explicit that `/metrics/history` is endpoint-local, not authoritative merged history | ✓ SATISFIED | Visible banner and framing block in [history_browser.py](/home/kevin/projects/wanctl/src/wanctl/dashboard/widgets/history_browser.py:123) plus locked copy in [history_state.py](/home/kevin/projects/wanctl/src/wanctl/dashboard/widgets/history_state.py:33). |
| `DASH-02` | 184-02 | History tab surfaces `metadata.source` context in operator-comprehensible form | ✓ SATISFIED | Success branch reads `payload["metadata"]["source"]` and formats translated detail plus raw diagnostic surfaces in [history_browser.py](/home/kevin/projects/wanctl/src/wanctl/dashboard/widgets/history_browser.py:220) and [history_browser.py](/home/kevin/projects/wanctl/src/wanctl/dashboard/widgets/history_browser.py:274). |
| `DASH-03` | 184-03 | Dashboard provides a clear path to authoritative merged history proof | ✓ SATISFIED | Compose-only handoff line and class-level `HANDOFF_TEXT` in [history_browser.py](/home/kevin/projects/wanctl/src/wanctl/dashboard/widgets/history_browser.py:109) and [history_browser.py](/home/kevin/projects/wanctl/src/wanctl/dashboard/widgets/history_browser.py:125). |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
| --- | --- | --- | --- | --- |
| `src/wanctl/dashboard/widgets/history_browser.py` | 247 | `return {}` on empty summary input | ℹ️ Info | Benign utility fallback; not a stub because `_compute_summary` is used and populated by real history values before render. |

### Human Verification Required

### 1. History Tab Framing Layout

**Test:** Open the dashboard, switch to the History tab, and inspect the area above the time-range selector.
**Expected:** The tab shows the source banner, source detail, and merged-CLI handoff as plainly visible lines above the selector, with the diagnostic line subdued below the table.
**Why human:** Code confirms compose order, but the contract also depends on actual visibility and prominence in the mounted Textual UI.

### 2. Runtime State Transitions

**Test:** Point the dashboard at a live autorate endpoint and exercise a normal success response, a fetch failure, and a response with missing `metadata.source` fields.
**Expected:** Success renders translated source provenance; fetch failure clears stale rows and shows `History unavailable.`; ambiguous payloads keep rows but switch framing to ambiguous wording and retain the CLI handoff.
**Why human:** Programmatic helper checks passed, but full widget rendering and state transitions were not mounted during verification.

### Gaps Summary

No implementation gaps were found against the Phase 184 goal. The remaining work is human UI verification and the deferred regression/doc alignment already scheduled for Phase 185.

---

_Verified: 2026-04-14T21:30:00Z_
_Verifier: Claude (gsd-verifier)_
