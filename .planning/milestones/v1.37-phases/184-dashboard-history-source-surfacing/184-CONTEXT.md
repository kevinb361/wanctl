# Phase 184: Dashboard History Source Surfacing - Context

**Gathered:** 2026-04-14
**Status:** Ready for planning

<domain>
## Phase Boundary

Implement the dashboard UI changes required by the Phase 183 locked contract
(`183-dashboard-source-contract.md`) inside `HistoryBrowserWidget`. This phase
delivers endpoint-local framing (L1–L3), `metadata.source` surfacing (S1–S3),
the merged-CLI handoff (H1–H3), and the four degraded/failure states (F1–F2)
without touching `/metrics/history` backend behavior, storage, retention, or
control-loop semantics.

Phase 184 owns *form and final wording*. Phase 183 already locked *what must be
shown, what must not*, and *which fields are authoritative*. Phase 185 writes
the regression surface and doc alignment.

</domain>

<decisions>
## Implementation Decisions

### Widget Layout — HistoryBrowserWidget.compose()

- **D-01:** `HistoryBrowserWidget` gains three dedicated Static children
  yielded at the top of `compose()`, above the existing `Select`:
  - `Static(id="source-banner")` — L1/L3 endpoint-local framing line
  - `Static(id="source-detail")` — S2 mode phrase + DB-path-derived context
  - `Static(id="source-handoff")` — H1/H2 merged-CLI handoff line
  These three Statics form the "framing block." They are always mounted and
  always visible, and their text is updated on every fetch lifecycle (initial
  mount, success, failure, ambiguous).
- **D-02:** A fourth Static `Static(id="source-diagnostic")` is yielded at the
  bottom of `compose()` (after `DataTable`) in a dim/muted style class. It
  carries the D-06 raw diagnostic surface: raw `metadata.source.mode` string,
  full `metadata.source.db_paths` list, and HTTP status on failure. Always
  mounted, always visible, but visually subordinate.
- **D-03:** The existing `Static(id="summary-stats")` is preserved as-is below
  the `Select` and above the `DataTable`. It continues to carry per-metric
  summary numbers only. The framing block does not reuse it — avoiding any
  accidental banner/stats clobber during load.

### Endpoint-Local Framing Copy (DASH-01, D-01..D-03)

- **D-04:** `source-banner` text on successful render:
  `"Endpoint-local history from the connected autorate daemon."`
  This is the final operator wording (not placeholder). It satisfies L1 by
  naming "endpoint-local" and the "connected autorate daemon", satisfies L3 by
  being plainly visible inside the history tab as a first-child Static, and
  contains no bare `"all WANs" / "merged history" / "cross-WAN history"`
  phrases (L1 forbids those unless explicitly qualified).

### metadata.source Surfacing (DASH-02, D-04..D-06)

- **D-05:** The UI reads `metadata.source.mode` and `metadata.source.db_paths`
  from the `/metrics/history` payload. No other field names are invented. All
  operator wording for mode is derived from those two exact fields (S1/S2).
- **D-06:** Mode → operator phrase mapping (final copy for `source-detail`
  prefix):
  - `local_configured_db` → `"Connected endpoint local database"`
  - `merged_discovery` → `"Discovered database set on this endpoint"`
  These strings are locked by D-05 of the Phase 183 contract; Phase 184 copies
  them verbatim into `source-detail`. Any unknown `mode` value falls into the
  F2 ambiguous branch (see D-12 below).
- **D-07:** `db_paths` rendering inside `source-detail`:
  - **1 path** (typically `local_configured_db`):
    `"<mode phrase> — <full absolute path>"`
    e.g. `"Connected endpoint local database — /var/lib/wanctl/spectrum.db"`
  - **N paths** (typically `merged_discovery`):
    `"<mode phrase> — N databases: <basename1>, <basename2>, ..."`
    e.g. `"Discovered database set on this endpoint — 3 databases: spectrum.db, att.db, foo.db"`
    Basenames come from `Path(p).name`. Order matches the payload order.
- **D-08:** Raw diagnostic detail (D-06 "diagnostic or detail surface") is
  rendered into `source-diagnostic` as:
  `"mode=<raw mode string> · db_paths=<joined absolute paths> · http=<status>"`
  On success, `http=200`. On F1, `http` carries the actual status or exception
  class name. Raw `local_configured_db` / `merged_discovery` values live only
  here — the primary operator surface (`source-detail`) never exposes them
  unwrapped (S3/D-06).

### Merged-CLI Handoff (DASH-03, D-07..D-09)

- **D-09:** `source-handoff` is an always-visible Static, yielded as the third
  Static in the framing block (directly below `source-detail`). It is never
  hidden, never keybinding-gated, never tooltip-only. This satisfies D-09's
  "wording intent locked, placement deferred" by choosing an always-visible
  top-of-tab placement that remains useful in every state — especially the
  four degraded/failure states where operators most need the merged-proof
  pointer.
- **D-10:** `source-handoff` text (final copy):
  `"For merged cross-WAN proof, run: python3 -m wanctl.history"`
  Verbatim invocation matches H1 canonical form. Clause "For merged cross-WAN
  proof" matches D-08's "use this when you need merged cross-WAN proof" intent.
  The handoff line remains unchanged across success, degraded, and failure
  states — operators see the same escape hatch everywhere.

### Degraded + Failure State Machine (F1/F2, DASH-04 for Phase 185)

- **D-11:** Phase 184 implements **four distinct render states**, each with
  its own copy for `source-banner` and `source-detail`. `source-handoff` text
  never changes. `source-diagnostic` always reflects the latest raw values or
  failure classification. Phase 185 will have a 1:1 regression target per
  state (D-12 contract requirement).
- **D-12:** State matrix (all four mandatory; placement per D-01/D-09):

  | State | Trigger | source-banner | source-detail | DataTable | summary-stats |
  |---|---|---|---|---|---|
  | `success` | 200 OK, `metadata.source.mode` in `{local_configured_db, merged_discovery}`, `db_paths` non-empty | `"Endpoint-local history from the connected autorate daemon."` | mode phrase + paths per D-07 | populated | computed |
  | `fetch_error` (F1) | Timeout, non-200, connection error, malformed JSON | `"History unavailable."` | `"Use python3 -m wanctl.history when you need merged cross-WAN proof."` | cleared | `"No data"` |
  | `source_missing` (F2a) | 200 OK but `metadata.source` absent or not a dict | `"Source context unavailable — treat this history view as ambiguous."` | `"Use python3 -m wanctl.history for authoritative merged proof."` | **rendered from `data` but with ambiguous framing above** | computed |
  | `mode_missing` (F2b) | `metadata.source` present but `mode` missing, not a string, or not in the known set | `"Source mode unavailable — treat this history view as ambiguous."` | `"Use python3 -m wanctl.history for authoritative merged proof."` | **rendered** | computed |
  | `db_paths_missing` (F2c) | `mode` present and known, but `db_paths` missing, not a list, or empty | `"Source database paths unavailable — treat this history view as ambiguous."` | `"Use python3 -m wanctl.history for authoritative merged proof."` | **rendered** | computed |

- **D-13:** `fetch_error` explicitly clears the DataTable and sets
  summary-stats to `"No data"`. No stale rows may remain (F1 forbids
  stale-looking merged history). The framing block (banner + detail + handoff)
  remains mounted and visible — operators keep the merged-CLI pointer exactly
  when they need it most.
- **D-14:** F2 states (source_missing / mode_missing / db_paths_missing)
  **render rows** from `payload["data"]` but flip the framing block to
  ambiguous copy. This matches F2's "ambiguous, not silent" intent: the
  operator sees there is data, but sees equally clearly that its provenance
  is untrusted and that the authoritative path is `python3 -m wanctl.history`.
- **D-15:** State classification precedence (in order): fetch_error → 
  source_missing → mode_missing → db_paths_missing → success. First matching
  predicate wins. This must be documented in the state helper so Phase 185
  tests can assert the precedence deterministically.

### Diagnostic Surface Rendering (D-08 continued)

- **D-16:** `source-diagnostic` uses Textual's class-based styling rather than
  color literals. The plan adds a CSS class (e.g. `dim`) in `DEFAULT_CSS`
  setting `color: $text-muted` (Textual design token) so the diagnostic line is
  visually subordinate without being invisible. No color hex literals.

### Testability Constraints (feeds Phase 185)

- **D-17:** The state classifier must be extracted as a pure function (e.g.
  `classify_history_state(resp_or_exc) -> HistoryState`) testable without
  mounting the Textual widget. The widget then just calls it and routes copy.
  This lets Phase 185 unit-test the 5-state matrix (success + 4 degraded)
  without Textual event loop machinery.
- **D-18:** Copy strings used by the widget live as module-level constants
  (or a small `HistoryCopy` dataclass) so Phase 185 can assert exact phrases
  against the contract placeholders without duplicating string literals.

### Claude's Discretion

- Exact Textual CSS selectors / class names beyond what's named above
  (`source-banner`, `source-detail`, `source-handoff`, `source-diagnostic`,
  `dim`).
- Whether the classifier lives inside `history_browser.py` or in a sibling
  module (e.g. `src/wanctl/dashboard/widgets/history_state.py`) — planner's
  call based on existing layout.
- Internal HTTP error narrowing (timeout vs connection vs status vs JSON
  parse) for populating the `http=` field in `source-diagnostic` — as long
  as all four collapse into the `fetch_error` state for banner purposes.
- Whether summary-stats in F2 states reflects only trusted rows or all
  rendered rows — D-14 permits either as long as framing is ambiguous.

### Folded Todos

None — no backlog todos matched Phase 184.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase 183 locked contract (primary input)
- `.planning/phases/183-dashboard-history-contract-audit/183-dashboard-source-contract.md` — locked contract: Labeling (L1–L3), Source metadata (S1–S3), Handoff (H1–H3), Degraded/Failure (F1–F2), Acceptance Criteria 1–12, Traceability D-01..D-14
- `.planning/phases/183-dashboard-history-contract-audit/183-dashboard-ambiguity-audit.md` — evidence base: current ambiguity inventory the contract was written against
- `.planning/phases/183-dashboard-history-contract-audit/183-CONTEXT.md` — decision source for D-01..D-14

### Current dashboard history implementation (files Phase 184 edits)
- `src/wanctl/dashboard/widgets/history_browser.py` — `HistoryBrowserWidget`: compose(), `_fetch_and_populate`, `_compute_summary`. Current failure path at line 124–126 collapses every error into `"Failed to fetch data - No data"` — replaced by the D-11 state machine.
- `src/wanctl/dashboard/app.py` — history tab mounting: `TabPane("History", id="history")` at line 199 yielding `HistoryBrowserWidget` with `autorate_url`. Layout entry point only; this file should not change.

### Backend source payload (read-only for Phase 184)
- `src/wanctl/health_check.py` §`_handle_metrics_history` (lines 792–860) — emits `metadata.source = {"mode": ..., "db_paths": [...]}`
- `src/wanctl/health_check.py` §`_resolve_history_db_paths` (lines 862–886) — source mode selection logic: controller present → `local_configured_db`, otherwise → `merged_discovery`

### Project-level
- `.planning/REQUIREMENTS.md` — DASH-01, DASH-02, DASH-03 rows assigned to Phase 184 (DASH-04, OPER-05 are Phase 185 territory)
- `.planning/ROADMAP.md` §Phase 184 — three-plan shape: 184-01 endpoint-local labeling, 184-02 metadata.source exposure, 184-03 merged-CLI handoff
- `CLAUDE.md` §Portable Controller Architecture — non-negotiable: no deployment-specific branching in Python; copy strings stay generic (no "Spectrum"/"ATT" mentions in banners)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- Textual `Static` widget — already used for `summary-stats`; framing block
  adds three more Static children in the same widget hierarchy.
- `payload.get("data", [])` row iteration loop (`history_browser.py:87–97`) —
  reused unchanged for F2 states; only the framing copy changes.
- `_compute_summary` helper (`history_browser.py:128–163`) — reused unchanged.

### Established Patterns
- Textual `DEFAULT_CSS` class-level string (`history_browser.py:33–38`) is
  the styling hook — `dim` class for the diagnostic Static belongs there, not
  in a separate `.css` file.
- Widget composition via `compose() -> ComposeResult` yielding children in
  top-to-bottom reading order — new framing Statics must be yielded BEFORE
  the `Select` to appear above it.

### Integration Points
- `_fetch_and_populate` is the only state-mutating path in the widget. The
  D-11 state machine lives there (or is delegated to a classifier called
  from there). No other code path enters the widget's render cycle.
- `src/wanctl/dashboard/app.py:199` mounts the widget; no change needed
  there — Phase 184 is entirely inside `history_browser.py` + optional
  new sibling module.

</code_context>

<specifics>
## Specific Ideas

- Final banner copy is locked in D-04, D-06 phrases are locked in D-06, 
  handoff copy is locked in D-10, and the four degraded banner strings are
  locked in D-12. Phase 184 planner should not re-open copy — only decide
  where constants live and how the classifier is factored.
- `python3 -m wanctl.history` must appear verbatim in `source-handoff` —
  contract H1 ties this to the verified `main()` entrypoint.
- "Authoritative" wording is reserved for the merged CLI description, not
  for the dashboard tab itself (contract L2 / D-02).

</specifics>

<deferred>
## Deferred Ideas

- Key binding 'd' to toggle a dedicated diagnostic panel (considered in A2
  Q3). Not in scope — an always-visible dim Static satisfies D-06 without
  adding hidden state or new Textual bindings.
- Summary-stats behavior tuning in F2 states (whether to recompute on all
  rows or mark stats ambiguous). Left to planner / Phase 185 to refine.
- Click-to-copy for the merged-CLI command. Textual clipboard integration
  is not mandated by the contract; deferred as polish.
- DataTable "Source" column per row. Rejected in A2 Q1 (redundant data,
  schema churn).

</deferred>

---

*Phase: 184-dashboard-history-source-surfacing*
*Context gathered: 2026-04-14 via /gsd-discuss-phase*
