# Dashboard History Ambiguity Audit

Phase 183 read-only audit. No code changes. Drives 183-02 contract. This document inventories the current `/metrics/history` envelope, the current dashboard history-tab consumer, and the operator-visible ambiguity points that remain between endpoint-local HTTP history and authoritative merged CLI history.

## Current /metrics/history Envelope

The `/metrics/history` handler is routed directly from `do_GET()` when the request path starts with `/metrics/history`; there is no separate dashboard-specific backend path for history reads today. `health_check.py:180`

The handler preserves a top-level envelope with `"data"` and `"metadata"` keys, because it builds `response = {"data": formatted_data, "metadata": {...}}` before returning JSON. `health_check.py:838`

The endpoint preserves newest-first ordering by sorting merged results in descending `timestamp` order before pagination. `health_check.py:830`

The endpoint exposes source context only under `metadata.source`, where the handler literally builds `"source": {"mode": source_mode, "db_paths": [str(path) for path in db_paths]}`. `health_check.py:847`

The current auditable field paths are therefore `metadata.source.mode` and `metadata.source.db_paths`; no sibling top-level `source` field is emitted. `health_check.py:841`

The handler can emit the literal `metadata.source.mode` value `"local_configured_db"` when a live controller is present and its first WAN config includes `storage.db_path`. `health_check.py:873`

The handler can also emit the literal `metadata.source.mode` value `"merged_discovery"` on the fallback path that uses `discover_wan_dbs(DEFAULT_DB_PATH.parent)` and, if needed, `[DEFAULT_DB_PATH]`. `health_check.py:883`

In code terms, "endpoint-local" means the health server reads only the configured DB path attached to the daemon's live controller, because `_resolve_history_db_paths()` returns `[Path(db_path)], "local_configured_db"` from `self.controller.wan_controllers[0]["config"]`. `health_check.py:874`

The endpoint short-circuits with an HTTP 503 JSON error when all resolved metrics databases fail to read, because `getattr(merged_results, "all_failed", False)` triggers `_send_json_error(503, "All metrics databases failed to read")`. `health_check.py:826`

The endpoint falls back to discovery only when there is no usable live-controller storage path in the current process, because the discovery branch begins after the `if self.controller and self.controller.wan_controllers` block. `health_check.py:873`

The current handler does not emit any other source fields beyond `mode` and `db_paths`; fields such as `metadata.source.scope` or `metadata.source.authoritative` do not exist in the current code. `health_check.py:847`

### Test Coverage Today

`tests/test_health_check.py` already checks the basic envelope by asserting both `"data"` and `"metadata"` are present in the `/metrics/history` response. `test_health_check.py:2833`

The test suite already covers newest-first merged ordering and offset semantics in `test_history_prefers_newest_first_after_multi_db_merge`. `test_health_check.py:2989`

The suite explicitly covers the `metadata.source` structure by asserting `metadata["source"]` exists and contains both `"mode"` and `"db_paths"`. `test_health_check.py:3131`

The suite explicitly covers endpoint-local resolution by asserting `data["metadata"]["source"]["mode"] == "local_configured_db"` and that `db_paths` resolves to the configured local DB. `test_health_check.py:3163`

The suite covers the all-databases-failed error path by expecting an HTTP 503 from `/metrics/history` when reads fail. `test_health_check.py:3224`

## Current HistoryBrowserWidget Behavior

The history tab uses `HistoryBrowserWidget`, which fetches only `f"{self._autorate_url}/metrics/history"` through a lazily created `httpx.AsyncClient(timeout=5.0)` and passes the selected range as a query param. `history_browser.py:77`

The widget has no result cache beyond reusing a single `_http_client`; each selection change runs `_fetch_and_populate()` through `run_worker()`. `history_browser.py:48`

The widget reads only `payload.get("data", [])` from the response and assigns that list to `records`; it does not read `payload["metadata"]` at all. `history_browser.py:86`

Rendered table rows use only `timestamp`, `wan_name`, `metric_name`, `value`, and `granularity` from each record. `history_browser.py:90`

The summary line is computed client-side from `metric_name` and `value` only; it does not use any server-provided summary fields or metadata fields. `history_browser.py:99`

The widget does not touch `metadata`, `metadata.source`, `metadata.source.mode`, or `metadata.source.db_paths` anywhere in the render path. The code path from `payload = resp.json()` through both success and error branches references only `data`, per-record fields, and summary text. `history_browser.py:86`

Repo inspection confirms the same absence: `rg -n "metadata|source" src/wanctl/dashboard/widgets/history_browser.py` returns no matches, which is consistent with the cited file body above. `history_browser.py:1`

The operator-visible selector labels are `"1 Hour"`, `"6 Hours"`, `"24 Hours"`, and `"7 Days"`. `history_browser.py:17`

The operator-visible initial summary text is `"Select a time range"`. `history_browser.py:53`

The operator-visible table column labels are `"Time"`, `"WAN"`, `"Metric"`, `"Value"`, and `"Granularity"`. `history_browser.py:59`

The operator-visible loading, empty, and error texts are `"Loading..."`, `"No data"`, and `"Failed to fetch data - No data"`. `history_browser.py:75`

The dashboard app wires the widget into `with TabPane("History", id="history")`, so the tab label presented to the operator is `"History"`. `app.py:199`

The app passes only `autorate_url=self.config.autorate_url` into the widget; no extra source-context or merged-history hint is wired in at the app layer. `app.py:200`

### Widget Test Coverage Today

`tests/dashboard/test_history_browser.py` checks that `compose()` yields a `Select`, a summary `Static`, and a `DataTable`, but it does not assert any source semantics. `test_history_browser.py:10`

The widget tests verify `_compute_summary()` behavior for multiple, empty, and single-value inputs. `test_history_browser.py:43`

The fetch-path test asserts that mocked response rows populate the table, but its fixture payload only uses `data` and a minimal `metadata` count object, not `metadata.source`. `test_history_browser.py:80`

The degraded-path test asserts the widget handles HTTP errors without crashing and renders text containing `"No data"` or `"Failed"`, but it does not assert endpoint-local wording or missing-source messaging. `test_history_browser.py:135`

The select-change test checks that selecting a new range triggers `_fetch_and_populate("6h")`; it does not cover source metadata or operator handoff behavior. `test_history_browser.py:177`

## Ambiguity Points

1. The tab label is only `"History"`, and the widget itself adds no endpoint-local qualifier, so an operator could wrongly conclude this tab is the authoritative merged cross-WAN history view rather than a local daemon view. This violates D-01 and D-03. `app.py:199`
2. The table renders a `"WAN"` column for each row but provides no statement about which backing DB set was queried, so an operator could wrongly infer that seeing multiple or single WAN names in rows proves merged cross-WAN scope instead of endpoint-local selection. This violates D-01, D-04, and D-05. `history_browser.py:59`
3. The widget reads only `payload.get("data", [])` and never reads `metadata.source.mode`, so an operator could wrongly conclude the dashboard has no narrower source contract than the authoritative CLI path. This violates D-04, D-05, and D-06. `history_browser.py:86`
4. The widget never surfaces `metadata.source.db_paths`, so an operator could wrongly conclude the tab already explains which DB path or DB set backed the query when it currently exposes no DB provenance at all. This violates D-05 and D-06. `history_browser.py:86`
5. The history surface offers no operator-visible handoff to `python3 -m wanctl.history`, so an operator could wrongly treat the dashboard tab as the only or authoritative proof surface for merged cross-WAN history. This violates D-02, D-07, and D-08. `history_browser.py:50`
6. The summary text and table headings render generic history-stat wording only, so an operator could wrongly conclude the tab has already reconciled the endpoint-local-versus-merged distinction described in the phase decisions. This violates D-01, D-03, and D-14. `history_browser.py:53`
7. The current degraded path collapses fetch failures into `"Failed to fetch data - No data"` and has no branch for missing `metadata.source`, so an operator could wrongly interpret silent source-context absence as a normal history result instead of an ambiguous or degraded state. This violates D-10 and D-11. `history_browser.py:124`

## Degraded And Failure Behavior Today

When the HTTP fetch fails, the widget clears the table and updates the summary text to the literal `"Failed to fetch data - No data"`. It does not distinguish timeout, non-200, or payload-shape failures. `history_browser.py:124`

When the payload is present but `metadata` is missing, the widget still proceeds because it reads only `payload.get("data", [])`; there is no explicit `metadata` validation branch. `history_browser.py:86`

When the payload is present but `metadata.source` is missing or malformed, the widget behaves the same as above because it never references `metadata` or `source`; there is no explicit missing-source handling branch today. `history_browser.py:86`

When the payload has zero rows, the table is cleared and the summary text falls back to the literal `"No data"` because `values_by_metric` remains empty. `history_browser.py:89`

There is no explicit operator-visible warning for "metadata missing," "metadata.source missing," or "endpoint-local source unknown"; those degraded states are unhandled in the current widget code. `history_browser.py:86`

Current widget test coverage only exercises the generic fetch-error branch and accepts output containing `"No data"` or `"Failed"`; it does not assert any dedicated missing-metadata or missing-source behavior because the widget has no such branch. `test_history_browser.py:135`

## Operator Doc Wording Alignment

`docs/RUNBOOK.md` tells operators that "the module-based CLI invocation above is the authoritative cross-WAN proof path" and that "`/metrics/history` is the endpoint-local HTTP history surface for the daemon serving that IP." `RUNBOOK.md:275`

`docs/DEPLOYMENT.md` tells operators that "`/metrics/history` is the endpoint-local history surface for the daemon serving that IP" and "Use the CLI path for authoritative merged cross-WAN reads." `DEPLOYMENT.md:93`

The dashboard tab itself currently shows only `"History"`, `"Select a time range"`, table columns, and generic loading/error text; it does not repeat the endpoint-local versus merged-CLI distinction found in operator docs. `app.py:199`

- The docs name the HTTP path as endpoint-local, but the dashboard tab label is only `"History"`, which leaves scope implicit instead of explicit. `RUNBOOK.md:276`
- The docs name the CLI path as the authoritative merged proof surface, but the widget presents no operator handoff to `wanctl.history` or `python3 -m wanctl.history`. `DEPLOYMENT.md:95`
- The docs explain that `/metrics/history` is tied to "the daemon serving that IP," but the widget does not surface `metadata.source.mode` or `metadata.source.db_paths`, so the dashboard omits the backend source context the docs depend on. `RUNBOOK.md:276`
- The docs distinguish endpoint availability and local-history inspection from authoritative merged proof, but the widget’s current generic summary and error states do not carry that distinction into the history tab. `DEPLOYMENT.md:94`

## Handoff To 183-02

This audit is read-only and records current behavior only. The dashboard-facing source contract that follows from these findings belongs in `.planning/phases/183-dashboard-history-contract-audit/183-dashboard-source-contract.md`.
