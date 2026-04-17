---
phase: 184-dashboard-history-source-surfacing
plan: 03
type: execute
wave: 2
depends_on:
  - 184-01
files_modified:
  - src/wanctl/dashboard/widgets/history_browser.py
autonomous: true
requirements:
  - DASH-03
task_count: 2

must_haves:
  truths:
    - "Every state the history tab can enter (success + fetch_error + source_missing + mode_missing + db_paths_missing) renders the exact string 'For merged cross-WAN proof, run: python3 -m wanctl.history' in the source-handoff Static."
    - "source-handoff is always mounted, always visible, never keybinding-gated or tooltip-only — it is yielded as a direct child of compose() above the time-range Select."
    - "The dashboard never describes itself as 'authoritative' or as a merged reader; 'authoritative' only appears on the DETAIL_AMBIGUOUS handoff line pointing at python3 -m wanctl.history."
    - "The widget has no runtime logic that could hide, clear, or overwrite source-handoff after compose."
  artifacts:
    - path: "src/wanctl/dashboard/widgets/history_browser.py"
      provides: "Always-visible source-handoff Static with locked merged-CLI invocation + handoff invariant assertion"
      contains: "source-handoff"
  key_links:
    - from: "src/wanctl/dashboard/widgets/history_browser.py::compose"
      to: "HISTORY_COPY.HANDOFF constant"
      via: "Static(HISTORY_COPY.HANDOFF, id=\"source-handoff\")"
      pattern: "Static\\(HISTORY_COPY.HANDOFF, id=\"source-handoff\"\\)"
    - from: "src/wanctl/dashboard/widgets/history_browser.py::_fetch_and_populate"
      to: "source-handoff Static"
      via: "NO update call — handoff text is static across all states"
      pattern: "source-handoff"
---

<objective>
Provide an always-visible, unchanging operator path from the dashboard history
tab to the authoritative merged CLI history workflow (DASH-03, H1–H3). Plan
184-01 already yields `Static(HISTORY_COPY.HANDOFF, id="source-handoff")` in
compose(), which satisfies the structural requirement. This plan (a) locks the
invariant that the handoff line must never change post-compose and
(b) installs a runtime/test guard that proves it.

Purpose: Operators reaching any of the four degraded states — exactly when
they most need merged cross-WAN proof — see the same invocation at the same
place, verbatim, with no state-dependent branching. The handoff is the
escape hatch, not a mode.

Output: A handoff invariant proven both by construction (no `.update` call
ever touches `source-handoff`) and by an explicit invariant check the widget
can be introspected against in Phase 185.
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

<interfaces>
<!-- From 184-01: handoff is seeded at compose time with the locked constant. -->
HISTORY_COPY.HANDOFF = "For merged cross-WAN proof, run: python3 -m wanctl.history"

<!-- compose() yields (order locked by D-01/D-02): -->
Static(HISTORY_COPY.BANNER_SUCCESS, id="source-banner")
Static("", id="source-detail")
Static(HISTORY_COPY.HANDOFF, id="source-handoff")      # <-- this plan's invariant target
Select(..., id="time-range")
Static("Select a time range", id="summary-stats")
DataTable(id="history-table")
Static("", id="source-diagnostic", classes="dim")
</interfaces>
</context>

<tasks>

<task type="auto" tdd="false">
  <name>Task 1: Expose HANDOFF_TEXT class attribute and prove source-handoff text is never mutated after compose</name>
  <files>src/wanctl/dashboard/widgets/history_browser.py</files>
  <read_first>
    - .planning/phases/184-dashboard-history-source-surfacing/184-CONTEXT.md (D-09, D-10, D-11)
    - .planning/phases/183-dashboard-history-contract-audit/183-dashboard-source-contract.md (H1, H2, H3)
    - src/wanctl/dashboard/widgets/history_browser.py (post-184-01 state)
    - src/wanctl/dashboard/widgets/history_state.py (HISTORY_COPY.HANDOFF)
  </read_first>
  <action>
Edit `src/wanctl/dashboard/widgets/history_browser.py`:

1. Add a class-level attribute on `HistoryBrowserWidget` that exposes the
   handoff text so Phase 185 can assert it without importing HISTORY_COPY:
```python
    # Exposed so Phase 185 regressions can assert the handoff stays verbatim
    # across every history tab state. Never mutated post-compose (D-09, D-10).
    HANDOFF_TEXT: str = HISTORY_COPY.HANDOFF
```
   Place it directly below the existing `DEFAULT_CSS` string and above
   `__init__`.

2. Verify (by inspection) that `_fetch_and_populate` does NOT call
   `.update()` on the `source-handoff` Static in any branch. The code
   produced by 184-01 + 184-02 must query only the four other framing
   widgets (`#source-banner`, `#source-detail`, `#source-diagnostic`,
   `#summary-stats`) plus `#history-table`. If any reference to
   `#source-handoff` appears inside `_fetch_and_populate`, delete it.

3. Do NOT change compose() — the Static is already yielded with
   `HISTORY_COPY.HANDOFF` by 184-01. This task only adds the class-level
   proof surface and enforces the no-mutation invariant.

Run `.venv/bin/ruff check` and `.venv/bin/mypy` on the file.
  </action>
  <verify>
    <automated>.venv/bin/ruff check src/wanctl/dashboard/widgets/history_browser.py &amp;&amp; .venv/bin/mypy src/wanctl/dashboard/widgets/history_browser.py &amp;&amp; .venv/bin/python -c "
from wanctl.dashboard.widgets.history_browser import HistoryBrowserWidget
assert HistoryBrowserWidget.HANDOFF_TEXT == 'For merged cross-WAN proof, run: python3 -m wanctl.history'
print('ok')
" &amp;&amp; .venv/bin/python -c "
import ast
tree = ast.parse(open('src/wanctl/dashboard/widgets/history_browser.py').read())
# Walk _fetch_and_populate; fail if any string literal 'source-handoff' appears inside it.
for node in ast.walk(tree):
    if isinstance(node, ast.AsyncFunctionDef) and node.name == '_fetch_and_populate':
        for sub in ast.walk(node):
            if isinstance(sub, ast.Constant) and isinstance(sub.value, str) and 'source-handoff' in sub.value:
                raise SystemExit('FAIL: _fetch_and_populate references source-handoff -- handoff must be immutable post-compose')
print('ok')
"</automated>
  </verify>
  <acceptance_criteria>
    - `grep -q 'HANDOFF_TEXT: str = HISTORY_COPY.HANDOFF' src/wanctl/dashboard/widgets/history_browser.py`
    - `grep -q 'For merged cross-WAN proof, run: python3 -m wanctl.history' src/wanctl/dashboard/widgets/history_state.py`
    - `grep -q 'Static(HISTORY_COPY.HANDOFF, id="source-handoff")' src/wanctl/dashboard/widgets/history_browser.py`
    - `grep -q 'python3 -m wanctl.history' src/wanctl/dashboard/widgets/history_browser.py` (via HANDOFF_TEXT constant reference through history_state import — acceptable via the string appearing on the class attribute line or re-exported value)
    - Invariant: no `#source-handoff` query or `source-handoff` string inside `_fetch_and_populate` — enforced by the AST check in the automated verifier above
    - `! grep -qE '\.update\([^)]*HISTORY_COPY.HANDOFF' src/wanctl/dashboard/widgets/history_browser.py` (handoff is never re-asserted via update)
    - `.venv/bin/ruff check src/wanctl/dashboard/widgets/history_browser.py` exits 0
    - `.venv/bin/mypy src/wanctl/dashboard/widgets/history_browser.py` exits 0
  </acceptance_criteria>
  <done>HANDOFF_TEXT class attribute exposes the locked handoff string; _fetch_and_populate never touches source-handoff; the AST invariant check passes.</done>
</task>

<task type="auto" tdd="false">
  <name>Task 2: Forbid "authoritative" / "wanctl-history" parity phrasing anywhere in history_browser or history_state except on the DETAIL_AMBIGUOUS handoff line</name>
  <files>src/wanctl/dashboard/widgets/history_browser.py</files>
  <read_first>
    - .planning/phases/184-dashboard-history-source-surfacing/184-CONTEXT.md (D-09, deferred key binding, L2 forbids parity language)
    - .planning/phases/183-dashboard-history-contract-audit/183-dashboard-source-contract.md (L2 Acceptance item 7)
    - src/wanctl/dashboard/widgets/history_browser.py (post Tasks 1/184-02)
    - src/wanctl/dashboard/widgets/history_state.py (HISTORY_COPY constants)
  </read_first>
  <action>
This task is a guard task — it proves by construction that the widget does
not imply parity between the dashboard history tab and `wanctl.history`
(Acceptance criterion 7, L2).

Add a module-level docstring constant at the top of
`src/wanctl/dashboard/widgets/history_browser.py` immediately after the
existing module docstring:

```python
# Contract invariants (Phase 184 / 183-contract L2 + H1):
#   * The string "python3 -m wanctl.history" MUST appear verbatim via
#     HISTORY_COPY.HANDOFF and HISTORY_COPY.DETAIL_AMBIGUOUS /
#     DETAIL_FETCH_ERROR — these are the only operator-facing places the
#     merged CLI is named.
#   * The dashboard history tab MUST NOT describe itself as
#     "authoritative", "merged", "wanctl-history", or "cross-WAN reader".
#     "authoritative" is reserved for DETAIL_AMBIGUOUS pointing AT the CLI.
#   * source-handoff text is immutable post-compose (enforced by the absence
#     of any `#source-handoff` reference inside `_fetch_and_populate`).
```

Then add a small helper at module level, below the imports and above
`TIME_RANGES`, that Phase 185 can call to verify the parity invariant:

```python
def _assert_no_parity_language(text: str) -> None:
    """Raise AssertionError if `text` contains parity language forbidden by L2.

    Phase 185 calls this against every HISTORY_COPY banner/detail string to
    prove the dashboard never describes itself as the authoritative merged
    reader. The only legitimate use of "authoritative" is in
    DETAIL_AMBIGUOUS, which points AT `python3 -m wanctl.history`, so that
    specific string is whitelisted.
    """
    whitelist = {
        HISTORY_COPY.DETAIL_AMBIGUOUS,  # "Use python3 -m wanctl.history for authoritative merged proof."
    }
    if text in whitelist:
        return
    forbidden = ("authoritative", "wanctl-history", "merged history reader", "cross-WAN history")
    lowered = text.lower()
    for token in forbidden:
        if token.lower() in lowered:
            raise AssertionError(
                f"L2 parity violation: dashboard copy {text!r} contains forbidden token {token!r}"
            )
```

Verify at import time (cheap) that every HISTORY_COPY banner/detail that the
widget actually renders passes the parity check, by adding a module-level
assertion block right after the helper:

```python
for _copy in (
    HISTORY_COPY.BANNER_SUCCESS,
    HISTORY_COPY.BANNER_FETCH_ERROR,
    HISTORY_COPY.BANNER_SOURCE_MISSING,
    HISTORY_COPY.BANNER_MODE_MISSING,
    HISTORY_COPY.BANNER_DB_PATHS_MISSING,
    HISTORY_COPY.DETAIL_FETCH_ERROR,
    HISTORY_COPY.DETAIL_AMBIGUOUS,
    HISTORY_COPY.HANDOFF,
    HISTORY_COPY.MODE_PHRASE_LOCAL,
    HISTORY_COPY.MODE_PHRASE_MERGED,
):
    _assert_no_parity_language(_copy)
del _copy
```

Note: `HANDOFF` ("For merged cross-WAN proof, run: python3 -m wanctl.history")
contains "merged cross-WAN" which is explicitly ALLOWED by L1 — "merged
history", "cross-WAN history" are the forbidden *bare* phrases, not any
occurrence of the word "merged". The forbidden list above targets the exact
bare phrases L2 / L1 prohibit: "merged history reader", "cross-WAN history",
"wanctl-history", "authoritative" (unqualified). Double-check the HANDOFF
string does not trip the check before committing — if it does, tighten the
forbidden list so the locked HANDOFF passes.

Run `.venv/bin/ruff check` and `.venv/bin/mypy` on the file. Import the
module via `.venv/bin/python -c "import wanctl.dashboard.widgets.history_browser"`
to prove the module-level assertion passes.
  </action>
  <verify>
    <automated>.venv/bin/ruff check src/wanctl/dashboard/widgets/history_browser.py &amp;&amp; .venv/bin/mypy src/wanctl/dashboard/widgets/history_browser.py &amp;&amp; .venv/bin/python -c "
import wanctl.dashboard.widgets.history_browser as m
# Parity check function is exposed and callable.
assert callable(m._assert_no_parity_language)
# DETAIL_AMBIGUOUS is whitelisted (contains 'authoritative') and must not raise.
m._assert_no_parity_language('Use python3 -m wanctl.history for authoritative merged proof.')
# An obviously-violating phrase must raise.
try:
    m._assert_no_parity_language('This dashboard is the authoritative merged history.')
except AssertionError:
    pass
else:
    raise SystemExit('FAIL: parity guard did not catch obvious violation')
print('ok')
"</automated>
  </verify>
  <acceptance_criteria>
    - `grep -q 'def _assert_no_parity_language' src/wanctl/dashboard/widgets/history_browser.py`
    - `grep -q 'L2 parity violation' src/wanctl/dashboard/widgets/history_browser.py`
    - `grep -q 'HISTORY_COPY.DETAIL_AMBIGUOUS' src/wanctl/dashboard/widgets/history_browser.py`
    - `grep -q 'HISTORY_COPY.BANNER_SUCCESS' src/wanctl/dashboard/widgets/history_browser.py`
    - `grep -q 'HISTORY_COPY.HANDOFF' src/wanctl/dashboard/widgets/history_browser.py`
    - `.venv/bin/python -c 'import wanctl.dashboard.widgets.history_browser'` exits 0 (module-level parity assertions all pass)
    - `.venv/bin/ruff check src/wanctl/dashboard/widgets/history_browser.py` exits 0
    - `.venv/bin/mypy src/wanctl/dashboard/widgets/history_browser.py` exits 0
  </acceptance_criteria>
  <done>_assert_no_parity_language helper exists, module-level for-loop asserts every HISTORY_COPY banner/detail/phrase is parity-clean at import time, and Phase 185 has a documented pluck-point for L2 regression.</done>
</task>

</tasks>

<verification>
- `.venv/bin/python -c "import wanctl.dashboard.widgets.history_browser"` exits 0 (proves parity invariant holds at import time)
- `.venv/bin/ruff check src/wanctl/dashboard/widgets/history_browser.py` exits 0
- `.venv/bin/mypy src/wanctl/dashboard/widgets/history_browser.py` exits 0
- `HistoryBrowserWidget.HANDOFF_TEXT == "For merged cross-WAN proof, run: python3 -m wanctl.history"`
- AST check in Task 1 passes: `_fetch_and_populate` contains no `source-handoff` reference
</verification>

<success_criteria>
- source-handoff Static is yielded once (by 184-01 compose) and never mutated
- HANDOFF_TEXT class attribute exposes the locked string for regression tests
- _assert_no_parity_language helper proves by construction that no HISTORY_COPY string tripped on forbidden L2 parity language
- Module imports cleanly, meaning every banner/detail/phrase string passed the parity check at import time
</success_criteria>

<output>
After completion, create `.planning/phases/184-dashboard-history-source-surfacing/184-03-SUMMARY.md` documenting: the exact handoff invariant (compose-only, never updated), the HANDOFF_TEXT pluck-point for Phase 185, and the parity-check helper's call signature.
</output>
