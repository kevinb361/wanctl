---
phase: 184-dashboard-history-source-surfacing
plan: 02
type: execute
wave: 2
depends_on:
  - 184-01
files_modified:
  - src/wanctl/dashboard/widgets/history_browser.py
autonomous: true
requirements:
  - DASH-02
task_count: 2

must_haves:
  truths:
    - "On successful fetch with mode='local_configured_db' and db_paths=['/var/lib/wanctl/spectrum.db'], source-detail reads 'Connected endpoint local database — /var/lib/wanctl/spectrum.db'."
    - "On successful fetch with mode='merged_discovery' and db_paths=['/a/spectrum.db','/b/att.db','/c/foo.db'], source-detail reads 'Discovered database set on this endpoint — 3 databases: spectrum.db, att.db, foo.db'."
    - "source-diagnostic on success renders exactly 'mode=<raw> · db_paths=<joined absolute paths> · http=200' using raw (not translated) mode values."
    - "source-diagnostic on fetch_error renders 'mode=? · db_paths=? · http=<classification>' where classification narrows httpx timeout/connect/status/JSON errors."
    - "The primary operator surface (source-detail) never exposes raw 'local_configured_db' or 'merged_discovery' tokens — only the translated mode phrases from HISTORY_COPY."
  artifacts:
    - path: "src/wanctl/dashboard/widgets/history_browser.py"
      provides: "Success-case source-detail composition and full diagnostic formatter"
      contains: "_format_source_detail"
  key_links:
    - from: "src/wanctl/dashboard/widgets/history_browser.py::_fetch_and_populate (SUCCESS branch)"
      to: "HISTORY_COPY.MODE_PHRASE_LOCAL / MODE_PHRASE_MERGED"
      via: "_format_source_detail helper"
      pattern: "_format_source_detail\\("
    - from: "src/wanctl/dashboard/widgets/history_browser.py::_format_diagnostic_for_payload"
      to: "payload['metadata']['source']['mode'] and db_paths"
      via: "raw read of metadata.source fields per D-08"
      pattern: "mode=.*db_paths=.*http="
---

<objective>
Expose `metadata.source` in the history UI (DASH-02, S1–S3) by filling in the
success-case `source-detail` content and the full `source-diagnostic` line
that Plan 184-01 left as placeholders. This plan owns the D-06 mode-phrase
translation and the D-07 db_paths rendering rules (1 path → full absolute
path; N paths → "N databases: basename1, basename2, ..."), and the D-08 raw
diagnostic format.

Purpose: Translate the backend source contract into operator-comprehensible
wording without leaking raw internals into the primary label. Raw values live
only in `source-diagnostic`.

Output: A successful history fetch that renders translated mode phrase + path
context in `source-detail`, and the raw diagnostic line in `source-diagnostic`,
reusing the state routing already in place from 184-01.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md
@.planning/phases/184-dashboard-history-source-surfacing/184-CONTEXT.md
@.planning/phases/183-dashboard-history-contract-audit/183-dashboard-source-contract.md
@.planning/phases/184-dashboard-history-source-surfacing/184-01-SUMMARY.md
@src/wanctl/dashboard/widgets/history_browser.py
@src/wanctl/dashboard/widgets/history_state.py
@src/wanctl/health_check.py
@CLAUDE.md

<interfaces>
<!-- From Plan 184-01 (history_state.py) -->

```python
# HISTORY_COPY constants (verbatim locked strings)
HISTORY_COPY.MODE_PHRASE_LOCAL   = "Connected endpoint local database"
HISTORY_COPY.MODE_PHRASE_MERGED  = "Discovered database set on this endpoint"
HISTORY_COPY.BANNER_SUCCESS      = "Endpoint-local history from the connected autorate daemon."
HISTORY_COPY.DETAIL_AMBIGUOUS    = "Use python3 -m wanctl.history for authoritative merged proof."

KNOWN_SOURCE_MODES: frozenset[str] = frozenset({"local_configured_db", "merged_discovery"})

def classify_history_state(resp_or_exc: Any) -> HistoryState: ...
```

<!-- From health_check.py (read-only) success payload shape -->
```python
payload["metadata"]["source"] == {
    "mode": "local_configured_db" | "merged_discovery",
    "db_paths": ["/var/lib/wanctl/spectrum.db", ...],  # list of absolute path strings
}
```
</interfaces>
</context>

<tasks>

<task type="auto" tdd="false">
  <name>Task 1: Add _format_source_detail helper implementing D-06 mode phrase + D-07 db_paths rendering rules</name>
  <files>src/wanctl/dashboard/widgets/history_browser.py</files>
  <read_first>
    - .planning/phases/184-dashboard-history-source-surfacing/184-CONTEXT.md (D-05, D-06, D-07 exact copy rules)
    - .planning/phases/183-dashboard-history-contract-audit/183-dashboard-source-contract.md (S1, S2, S3)
    - src/wanctl/dashboard/widgets/history_browser.py (current state after 184-01)
    - src/wanctl/dashboard/widgets/history_state.py (HISTORY_COPY constants, KNOWN_SOURCE_MODES)
  </read_first>
  <behavior>
    - _format_source_detail({"mode":"local_configured_db","db_paths":["/var/lib/wanctl/spectrum.db"]}) → "Connected endpoint local database — /var/lib/wanctl/spectrum.db"
    - _format_source_detail({"mode":"merged_discovery","db_paths":["/a/spectrum.db","/b/att.db","/c/foo.db"]}) → "Discovered database set on this endpoint — 3 databases: spectrum.db, att.db, foo.db"
    - _format_source_detail({"mode":"local_configured_db","db_paths":["/only.db","/second.db"]}) → "Connected endpoint local database — 2 databases: only.db, second.db" (N-path branch when len > 1 regardless of mode — N-path form is triggered by path count, not mode, per D-07)
    - _format_source_detail({"mode":"merged_discovery","db_paths":["/only.db"]}) → "Discovered database set on this endpoint — /only.db" (1-path branch when len == 1)
    - Order of basenames preserved from input list order (D-07: "Order matches the payload order")
  </behavior>
  <action>
Add a new private helper method to `HistoryBrowserWidget` in
`src/wanctl/dashboard/widgets/history_browser.py`, placed directly after
`_compute_summary`. Also add `from pathlib import Path` to the module imports
if not already present. Exact helper body:

```python
    def _format_source_detail(self, source: dict[str, Any]) -> str:
        """Render source-detail text per D-06 (mode phrase) and D-07 (db_paths).

        Primary operator surface. Never exposes raw internals — raw values
        belong in source-diagnostic. Called only in the SUCCESS branch where
        the classifier has already confirmed mode is in KNOWN_SOURCE_MODES and
        db_paths is a non-empty list.

        Contract mapping (184-CONTEXT D-06 / D-07):
          - mode=local_configured_db → "Connected endpoint local database"
          - mode=merged_discovery    → "Discovered database set on this endpoint"
          - len(db_paths) == 1       → "<mode phrase> — <full absolute path>"
          - len(db_paths) > 1        → "<mode phrase> — N databases: <basename1>, <basename2>, ..."
        """
        mode = source.get("mode")
        db_paths = source.get("db_paths") or []

        if mode == "local_configured_db":
            phrase = HISTORY_COPY.MODE_PHRASE_LOCAL
        elif mode == "merged_discovery":
            phrase = HISTORY_COPY.MODE_PHRASE_MERGED
        else:  # Defensive — classifier gates this branch, but keep total.
            phrase = HISTORY_COPY.MODE_PHRASE_LOCAL

        if len(db_paths) == 1:
            return f"{phrase} — {db_paths[0]}"

        basenames = ", ".join(Path(str(p)).name for p in db_paths)
        return f"{phrase} — {len(db_paths)} databases: {basenames}"
```

Then, in `_fetch_and_populate`, replace the SUCCESS branch (the one currently
setting `detail.update("")` and `diagnostic.update("")` placeholders from
Plan 184-01) with:

```python
        if state is HistoryState.SUCCESS:
            # Classifier guarantees metadata.source is a dict with known mode
            # and non-empty db_paths list.
            source = payload["metadata"]["source"]
            banner.update(HISTORY_COPY.BANNER_SUCCESS)
            detail.update(self._format_source_detail(source))
            diagnostic.update(self._format_diagnostic_for_payload(payload, http_status=200))
```

Do NOT change the F2 branches — they already call
`_format_diagnostic_for_payload` from 184-01 and Task 2 of this plan will
upgrade that helper.

Run `.venv/bin/ruff check src/wanctl/dashboard/widgets/history_browser.py` and
`.venv/bin/mypy src/wanctl/dashboard/widgets/history_browser.py`.
  </action>
  <verify>
    <automated>.venv/bin/ruff check src/wanctl/dashboard/widgets/history_browser.py &amp;&amp; .venv/bin/mypy src/wanctl/dashboard/widgets/history_browser.py &amp;&amp; .venv/bin/python -c "
from wanctl.dashboard.widgets.history_browser import HistoryBrowserWidget
w = HistoryBrowserWidget.__new__(HistoryBrowserWidget)
assert w._format_source_detail({'mode':'local_configured_db','db_paths':['/var/lib/wanctl/spectrum.db']}) == 'Connected endpoint local database — /var/lib/wanctl/spectrum.db'
assert w._format_source_detail({'mode':'merged_discovery','db_paths':['/a/spectrum.db','/b/att.db','/c/foo.db']}) == 'Discovered database set on this endpoint — 3 databases: spectrum.db, att.db, foo.db'
assert w._format_source_detail({'mode':'merged_discovery','db_paths':['/only.db']}) == 'Discovered database set on this endpoint — /only.db'
print('ok')
"</automated>
  </verify>
  <acceptance_criteria>
    - `grep -q 'def _format_source_detail' src/wanctl/dashboard/widgets/history_browser.py`
    - `grep -q 'HISTORY_COPY.MODE_PHRASE_LOCAL' src/wanctl/dashboard/widgets/history_browser.py`
    - `grep -q 'HISTORY_COPY.MODE_PHRASE_MERGED' src/wanctl/dashboard/widgets/history_browser.py`
    - `grep -q 'databases: ' src/wanctl/dashboard/widgets/history_browser.py`
    - `grep -q 'self._format_source_detail(source)' src/wanctl/dashboard/widgets/history_browser.py`
    - `grep -q 'from pathlib import Path' src/wanctl/dashboard/widgets/history_browser.py`
    - `! grep -q 'detail.update("")' src/wanctl/dashboard/widgets/history_browser.py` (success placeholder removed)
    - The primary surface must not expose raw tokens: `! grep -qE '(detail|banner).update\([^)]*local_configured_db' src/wanctl/dashboard/widgets/history_browser.py`
    - `! grep -qE '(detail|banner).update\([^)]*merged_discovery' src/wanctl/dashboard/widgets/history_browser.py`
    - `.venv/bin/ruff check src/wanctl/dashboard/widgets/history_browser.py` exits 0
    - `.venv/bin/mypy src/wanctl/dashboard/widgets/history_browser.py` exits 0
  </acceptance_criteria>
  <done>_format_source_detail implements the D-06/D-07 rules verbatim, SUCCESS branch of _fetch_and_populate wires it, and the primary operator surface never contains raw mode tokens.</done>
</task>

<task type="auto" tdd="false">
  <name>Task 2: Expand _format_diagnostic_for_payload and _format_diagnostic_for_error to full D-08 format with HTTP error narrowing</name>
  <files>src/wanctl/dashboard/widgets/history_browser.py</files>
  <read_first>
    - .planning/phases/184-dashboard-history-source-surfacing/184-CONTEXT.md (D-08 raw diagnostic format, D-02 discretion on http error narrowing)
    - src/wanctl/dashboard/widgets/history_browser.py (current placeholder helpers from 184-01)
  </read_first>
  <action>
Replace the two placeholder helpers `_format_diagnostic_for_payload` and
`_format_diagnostic_for_error` in `HistoryBrowserWidget` with their full D-08
implementations.

Ensure `import httpx` is already imported (it is — used by the fetch path).

Exact bodies:

```python
    def _format_diagnostic_for_payload(
        self, payload: dict[str, Any], *, http_status: int
    ) -> str:
        """Render source-diagnostic text per D-08 (raw values + http status).

        Used for SUCCESS and all F2 states. Raw mode and raw absolute paths
        appear here and ONLY here — the primary source-detail surface
        translates mode into operator wording (see _format_source_detail).

        Format (D-08):
          "mode=<raw mode string> · db_paths=<joined absolute paths> · http=<status>"
        """
        metadata = payload.get("metadata") if isinstance(payload, dict) else None
        source = metadata.get("source") if isinstance(metadata, dict) else None

        if isinstance(source, dict):
            raw_mode = source.get("mode")
            raw_paths = source.get("db_paths")
        else:
            raw_mode = None
            raw_paths = None

        mode_str = str(raw_mode) if raw_mode is not None else "missing"

        if isinstance(raw_paths, list):
            paths_str = ",".join(str(p) for p in raw_paths) if raw_paths else "empty"
        elif raw_paths is None:
            paths_str = "missing"
        else:
            paths_str = f"malformed({type(raw_paths).__name__})"

        return f"mode={mode_str} · db_paths={paths_str} · http={http_status}"

    def _format_diagnostic_for_error(self, exc: BaseException) -> str:
        """Render source-diagnostic text on fetch_error.

        Narrows common httpx failure modes so operators can distinguish
        timeout / connect / status / JSON-parse failures (D-02 discretion:
        "all four collapse into fetch_error state for banner purposes"; the
        banner remains HISTORY_COPY.BANNER_FETCH_ERROR, only the diagnostic
        line narrows).
        """
        if isinstance(exc, httpx.TimeoutException):
            http_label = "timeout"
        elif isinstance(exc, httpx.HTTPStatusError):
            http_label = f"{exc.response.status_code}"
        elif isinstance(exc, httpx.ConnectError):
            http_label = "connect_error"
        elif isinstance(exc, httpx.HTTPError):
            http_label = f"http_error({type(exc).__name__})"
        elif isinstance(exc, ValueError):
            # resp.json() raises ValueError / JSONDecodeError subclass on malformed JSON
            http_label = "invalid_json"
        else:
            http_label = type(exc).__name__

        return f"mode=? · db_paths=? · http={http_label}"
```

Also update the `_fetch_and_populate` call site that uses
`_format_diagnostic_for_error`: the parameter must be the caught exception.
The 184-01 skeleton already passes `payload_or_exc`, which is the Exception in
the fetch_error branch — no call-site change needed, but verify the type
signature accepts the typed exception by using `BaseException` as annotated.

Do NOT modify `_format_source_detail`, the state routing, or compose().

Run `.venv/bin/ruff check` and `.venv/bin/mypy` on the file.
  </action>
  <verify>
    <automated>.venv/bin/ruff check src/wanctl/dashboard/widgets/history_browser.py &amp;&amp; .venv/bin/mypy src/wanctl/dashboard/widgets/history_browser.py &amp;&amp; .venv/bin/python -c "
import httpx
from wanctl.dashboard.widgets.history_browser import HistoryBrowserWidget
w = HistoryBrowserWidget.__new__(HistoryBrowserWidget)
# D-08 format
s = w._format_diagnostic_for_payload({'metadata':{'source':{'mode':'local_configured_db','db_paths':['/var/lib/wanctl/spectrum.db']}}}, http_status=200)
assert s == 'mode=local_configured_db · db_paths=/var/lib/wanctl/spectrum.db · http=200', repr(s)
# Timeout narrowing
s = w._format_diagnostic_for_error(httpx.ConnectTimeout('x'))
assert s == 'mode=? · db_paths=? · http=timeout', repr(s)
# Invalid JSON narrowing
s = w._format_diagnostic_for_error(ValueError('bad json'))
assert s == 'mode=? · db_paths=? · http=invalid_json', repr(s)
print('ok')
"</automated>
  </verify>
  <acceptance_criteria>
    - `grep -q 'mode={mode_str} · db_paths={paths_str} · http={http_status}' src/wanctl/dashboard/widgets/history_browser.py`
    - `grep -q 'mode=? · db_paths=? · http={http_label}' src/wanctl/dashboard/widgets/history_browser.py`
    - `grep -q 'httpx.TimeoutException' src/wanctl/dashboard/widgets/history_browser.py`
    - `grep -q 'httpx.HTTPStatusError' src/wanctl/dashboard/widgets/history_browser.py`
    - `grep -q 'httpx.ConnectError' src/wanctl/dashboard/widgets/history_browser.py`
    - `grep -q 'invalid_json' src/wanctl/dashboard/widgets/history_browser.py`
    - `.venv/bin/ruff check src/wanctl/dashboard/widgets/history_browser.py` exits 0
    - `.venv/bin/mypy src/wanctl/dashboard/widgets/history_browser.py` exits 0
  </acceptance_criteria>
  <done>Diagnostic helpers emit the exact D-08 format "mode=X · db_paths=Y · http=Z" and narrow timeout/connect/status/JSON errors into distinct http labels while the banner stays on HISTORY_COPY.BANNER_FETCH_ERROR.</done>
</task>

</tasks>

<verification>
- `.venv/bin/ruff check src/wanctl/dashboard/widgets/history_browser.py` exits 0
- `.venv/bin/mypy src/wanctl/dashboard/widgets/history_browser.py` exits 0
- Smoke tests for `_format_source_detail` and diagnostic helpers pass (embedded in Task verifiers)
- Raw `local_configured_db` / `merged_discovery` tokens appear ONLY in `_format_diagnostic_for_payload` read code, never in a `.update(...)` call for `source-banner` or `source-detail`
</verification>

<success_criteria>
- SUCCESS branch renders `source-detail` via `_format_source_detail` using locked D-06/D-07 copy rules
- SUCCESS branch renders `source-diagnostic` via `_format_diagnostic_for_payload` with raw mode + absolute paths + `http=200`
- FETCH_ERROR branch renders `source-diagnostic` with narrowed HTTP error label
- F2 branches already use `_format_diagnostic_for_payload` from 184-01 — upgraded transparently by Task 2
- Primary surfaces never expose raw mode tokens (S3 enforced via grep acceptance criteria)
</success_criteria>

<output>
After completion, create `.planning/phases/184-dashboard-history-source-surfacing/184-02-SUMMARY.md` documenting: the exact mapping of D-05..D-08 to code symbols, the helper signatures Phase 185 will call directly for regression assertions, and how the raw-vs-translated separation is enforced.
</output>
