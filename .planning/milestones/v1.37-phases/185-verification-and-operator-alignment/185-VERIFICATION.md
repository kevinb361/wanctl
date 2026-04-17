# Phase 185 Verification — Dashboard History Source Clarity Closeout

## Purpose

This artifact closes `DASH-04` and `OPER-05` for milestone `v1.37` against the
locked Phase 183 dashboard history contract in
`.planning/phases/183-dashboard-history-contract-audit/183-dashboard-source-contract.md`.
Per Phase 185 context decisions `D-07` and `D-09`, this closeout is
intentionally repo-side: it proves the contract with targeted regressions,
widget behavior, and operator-doc alignment without requiring new live-host,
storage-footprint, or control-loop evidence.

## Regression Proof Command

```bash
.venv/bin/pytest tests/dashboard/ -q
# exit 0
# 171 passed in 34.69s
```

## Contract Traceability Table

| Phase 183 Contract Item | Requirement | Evidence (test or doc) | File |
| --- | --- | --- | --- |
| Acceptance Criterion 1: endpoint-local history is plainly visible | `DASH-04` | `test_history_copy_banner_success_is_endpoint_local`; `test_success_state_renders_banner_detail_and_handoff` | `tests/dashboard/test_history_state.py`; `tests/dashboard/test_history_browser.py` |
| Acceptance Criterion 2: no bare merged/parity phrasing in dashboard copy | `DASH-04` | `test_history_copy_no_parity_language_in_banners`; import-time `_assert_no_parity_language` guard | `tests/dashboard/test_history_state.py`; `src/wanctl/dashboard/widgets/history_browser.py` |
| Acceptance Criterion 3: success detail uses translated mode-specific label | `DASH-04` | `test_success_state_renders_banner_detail_and_handoff`; `test_success_state_merged_discovery_lists_db_basenames` | `tests/dashboard/test_history_browser.py` |
| Acceptance Criterion 4: success detail includes db_paths-derived context | `DASH-04` | `test_success_state_renders_banner_detail_and_handoff`; `test_success_state_merged_discovery_lists_db_basenames` | `tests/dashboard/test_history_browser.py` |
| Acceptance Criterion 5: raw mode values do not become the primary operator label | `DASH-04` | `test_success_state_renders_banner_detail_and_handoff`; `test_success_state_merged_discovery_lists_db_basenames` | `tests/dashboard/test_history_browser.py` |
| Acceptance Criterion 6: merged CLI handoff remains visible | `DASH-04` | `test_history_copy_handoff_mentions_python3_m_wanctl_history_verbatim`; `test_handoff_text_is_verbatim_across_all_states` | `tests/dashboard/test_history_state.py`; `tests/dashboard/test_history_browser.py` |
| Acceptance Criterion 7: dashboard does not claim equivalence with `wanctl.history` | `DASH-04` | `test_history_copy_no_parity_language_in_banners`; import-time `_assert_no_parity_language` guard | `tests/dashboard/test_history_state.py`; `src/wanctl/dashboard/widgets/history_browser.py` |
| Acceptance Criterion 8: fetch failure is explicit and clears stale rows | `DASH-04` | `test_fetch_error_state_clears_table_and_shows_unavailable_banner`; `test_classify_history_state_fetch_error_for_exception`; `test_classify_history_state_fetch_error_for_httpx_timeout`; `test_classify_precedence_fetch_error_beats_source_missing` | `tests/dashboard/test_history_browser.py`; `tests/dashboard/test_history_state.py` |
| Acceptance Criterion 9: missing `metadata.source` stays ambiguous and operator-visible | `DASH-04` | `test_source_missing_state_shows_ambiguous_banner_and_preserves_handoff`; `test_classify_history_state_source_missing_when_payload_not_dict`; `test_classify_history_state_source_missing_when_metadata_not_dict`; `test_classify_history_state_source_missing_when_source_absent`; `test_classify_history_state_source_missing_when_source_not_dict` | `tests/dashboard/test_history_browser.py`; `tests/dashboard/test_history_state.py` |
| Acceptance Criterion 10: missing or empty `db_paths` stays ambiguous and operator-visible | `DASH-04` | `test_db_paths_missing_state_shows_db_paths_ambiguous_banner`; `test_classify_history_state_db_paths_missing_when_absent`; `test_classify_history_state_db_paths_missing_when_empty_list`; `test_classify_history_state_db_paths_missing_when_not_list` | `tests/dashboard/test_history_browser.py`; `tests/dashboard/test_history_state.py` |
| Acceptance Criterion 11: success classification depends on both mode and db_paths | `DASH-04` | `test_classify_history_state_success_returns_success`; `test_classify_history_state_success_merged_discovery`; `test_success_state_renders_banner_detail_and_handoff` | `tests/dashboard/test_history_state.py`; `tests/dashboard/test_history_browser.py` |
| Acceptance Criterion 12: operator docs match the dashboard wording | `OPER-05` | `8. Re-check the active storage topology and retained history with read-only commands`; `## Storage Topology And History Checks`; `## Monitoring And History` | `docs/DEPLOYMENT.md`; `docs/RUNBOOK.md`; `docs/GETTING-STARTED.md` |
| F3 mode-missing regression surface: absent mode stays ambiguous | `DASH-04` | `test_classify_history_state_mode_missing_when_mode_absent` | `tests/dashboard/test_history_state.py` |
| F3 mode-missing regression surface: unknown mode stays ambiguous | `DASH-04` | `test_mode_missing_state_shows_mode_ambiguous_banner`; `test_classify_history_state_mode_missing_when_mode_unknown` | `tests/dashboard/test_history_browser.py`; `tests/dashboard/test_history_state.py` |
| F3 mode-missing regression surface: non-string mode stays ambiguous | `DASH-04` | `test_classify_history_state_mode_missing_when_mode_not_string` | `tests/dashboard/test_history_state.py` |
| F3 mode-missing regression surface: handoff remains visible even when mode is ambiguous | `DASH-04` | `test_mode_missing_state_shows_mode_ambiguous_banner`; `test_handoff_text_is_verbatim_across_all_states` | `tests/dashboard/test_history_browser.py` |

## DASH-04 Confirmation

`tests/dashboard/test_history_state.py` is now the pure regression surface for
the classifier and locked copy constants. It covers all five `HistoryState`
branches: `SUCCESS`, `FETCH_ERROR`, `SOURCE_MISSING`, `MODE_MISSING`, and
`DB_PATHS_MISSING`, plus the D-15 precedence rule where exception handling wins
before payload-shape checks. `tests/dashboard/test_history_browser.py` now adds
`TestHistoryBrowserSourceContract`, which exercises the widget state matrix for
success-local, success-merged, fetch-error, source-missing, mode-missing, and
db-paths-missing flows. `HistoryBrowserWidget.HANDOFF_TEXT` is asserted
verbatim across every state by
`test_handoff_text_is_verbatim_across_all_states`, so the merged-CLI proof path
cannot silently drift. `src/wanctl/dashboard/widgets/history_state.py`
documents the Phase 184 D-15 precedence rule inline and the new tests prove the
implementation still follows it. DASH-04 is satisfied by the evidence above.

## OPER-05 Confirmation

`docs/DEPLOYMENT.md` Step 8 now contains the canonical D-05 distinction and
explicitly ties the dashboard wording to `metadata.source`. `docs/RUNBOOK.md`
uses the same canonical rule in `## Storage Topology And History Checks`, so
troubleshooting guidance matches the dashboard contract. `docs/GETTING-STARTED.md`
adds `## Monitoring And History`, giving first-pass operators the same rule
before they reach the deeper workflow docs. Across all three docs,
`/metrics/history` is described as the endpoint-local HTTP history view for the
connected autorate daemon, and `python3 -m wanctl.history` is described as the
authoritative merged cross-WAN proof path. OPER-05 is satisfied by the evidence
above.

## Invariant Confirmations

1. Dashboard wording avoids parity claims with `wanctl.history`. This is
   enforced in code by the import-time `_assert_no_parity_language` guard in
   `src/wanctl/dashboard/widgets/history_browser.py` and proven by
   `test_history_copy_no_parity_language_in_banners` in
   `tests/dashboard/test_history_state.py`.
2. Merged-CLI handoff stays verbatim across every history state. This is
   enforced by `HistoryBrowserWidget.HANDOFF_TEXT` and proven by
   `test_handoff_text_is_verbatim_across_all_states` in
   `tests/dashboard/test_history_browser.py`.
3. Degraded and failure states stay operator-visible, never silently fallen
   back. This is proven by
   `test_fetch_error_state_clears_table_and_shows_unavailable_banner`,
   `test_source_missing_state_shows_ambiguous_banner_and_preserves_handoff`,
   `test_mode_missing_state_shows_mode_ambiguous_banner`,
   `test_db_paths_missing_state_shows_db_paths_ambiguous_banner`,
   `test_handoff_text_is_verbatim_across_all_states`, and the classifier branch
   tests for source-missing, mode-missing, db-paths-missing, and fetch-error in
   `tests/dashboard/test_history_state.py`.

## Out Of Scope For Closeout

This closeout does not add live-production storage evidence, does not re-open
control-loop or `/metrics/history` backend semantics, and does not assert any
new host-side outcome beyond the repo evidence listed here. Those concerns were
explicitly kept out of Phase 185 by context decision `D-09` and remain deferred
beyond milestone `v1.37`.

## References

- `.planning/REQUIREMENTS.md` (`DASH-04`, `OPER-05`)
- `.planning/phases/183-dashboard-history-contract-audit/183-dashboard-source-contract.md`
- `.planning/phases/184-dashboard-history-source-surfacing/184-CONTEXT.md`
- `.planning/phases/185-verification-and-operator-alignment/185-CONTEXT.md`
- `.planning/phases/185-verification-and-operator-alignment/185-01-SUMMARY.md`
- `.planning/phases/185-verification-and-operator-alignment/185-02-SUMMARY.md`
- `.planning/ROADMAP.md` Phase 185

*Verification locked: 2026-04-14. Milestone v1.37.*
