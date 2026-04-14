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
