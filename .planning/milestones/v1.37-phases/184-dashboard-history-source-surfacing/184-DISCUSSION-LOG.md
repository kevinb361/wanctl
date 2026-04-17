# Phase 184: Dashboard History Source Surfacing - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-14
**Phase:** 184-dashboard-history-source-surfacing
**Areas discussed:** Endpoint-local framing form, metadata.source surfacing layout, Merged-CLI handoff form, Degraded + failure state differentiation

---

## Endpoint-local framing form

### Q1: Where should the plainly visible endpoint-local explanation (L1/L3) live inside HistoryBrowserWidget?

| Option | Description | Selected |
|---|---|---|
| New Static banner above Select | Dedicated `Static(id='source-banner')` as first child; independent of summary-stats; always visible. | ✓ |
| Replace summary-stats Static with dual-line | Fewer widgets, but banner text risks being stripped during load. | |
| Footer Static below DataTable | Plainly visible but bottom of tab — operators may read table first. | |

**User's choice:** New Static banner above Select

### Q2: Final banner copy

| Option | Description | Selected |
|---|---|---|
| "Endpoint-local history from the connected autorate daemon." | Short, names the daemon, no bare merged phrases. | ✓ |
| "History from this autorate endpoint only — not merged cross-WAN history." | Explicit contrast; permitted since "merged cross-WAN" is negated. | |
| "Local view: /metrics/history for this daemon. For merged cross-WAN proof, see below." | Clearest for code-reading operators, noisier for new ones. | |

**User's choice:** "Endpoint-local history from the connected autorate daemon."

---

## metadata.source surfacing layout

### Q1: How should metadata.source.mode + db_paths be rendered in the history tab?

| Option | Description | Selected |
|---|---|---|
| Second Static line under source-banner | Dedicated `Static(id='source-detail')` below the framing banner; keeps source context adjacent. | ✓ |
| Footer Static below DataTable | Separates "what this is" from "what it came from". | |
| New DataTable column "Source" | Per-row clarity but redundant, widens table, schema change. | |

**User's choice:** Second Static line under source-banner

### Q2: db_paths rendering for 1 vs N paths

| Option | Description | Selected |
|---|---|---|
| Full path for 1, count + basenames for N | Local: full path. merged_discovery: count + basenames. | ✓ |
| Always full absolute paths joined | Maximum fidelity, wraps badly in narrow terminals. | |
| Count only | Hides which DBs — violates D-05. | |

**User's choice:** Full path for 1, count + basenames for N

### Q3: Raw diagnostic detail surface (D-06)

| Option | Description | Selected |
|---|---|---|
| Dim footer Static always visible | `Static(id='source-diagnostic', classes='dim')` at bottom. | ✓ |
| Keybinding 'd' toggles diagnostic panel | Hidden state, Textual event handling, out of scope. | |
| No dedicated diagnostic surface | Pushes operators to logs, defeats in-tab purpose. | |

**User's choice:** Dim footer Static always visible

---

## Merged-CLI handoff form

### Q1: Widget form for the DASH-03 merged-CLI handoff

| Option | Description | Selected |
|---|---|---|
| Always-visible Static below source-detail | Third Static in framing block; always visible; works best in degraded states. | ✓ |
| Textual footer binding 'm' showing toast | Discoverable via footer but hidden until pressed. | |
| Dedicated Static at bottom of tab | Separates handoff from framing; easy to miss. | |

**User's choice:** Always-visible Static below source-detail

### Q2: Final handoff copy

| Option | Description | Selected |
|---|---|---|
| "For merged cross-WAN proof, run: python3 -m wanctl.history" | Short, names canonical invocation verbatim. | ✓ |
| "Need merged cross-WAN history? Run: python3 -m wanctl.history" | Question framing, slightly less direct. | |
| "Authoritative merged history: python3 -m wanctl.history (run from a shell)" | "Authoritative" wording may blur contract vocabulary. | |

**User's choice:** "For merged cross-WAN proof, run: python3 -m wanctl.history"

---

## Degraded + failure state differentiation

### Q1: How many distinct states?

| Option | Description | Selected |
|---|---|---|
| 4 distinct states, each with own banner copy | fetch_error / source_missing / mode_missing / db_paths_missing — 1:1 regression target for Phase 185. | ✓ |
| 2 states: hard failure vs ambiguous | Simpler but collapses 3 regression cases. | |
| 1 unified ambiguous banner | Violates F1/F2, not viable under contract. | |

**User's choice:** 4 distinct states, each with its own banner copy

### Q2: F1 fetch error — DataTable rows and summary-stats

| Option | Description | Selected |
|---|---|---|
| Clear table + stats, show banner, keep framing/handoff Static | No stale rows; framing and handoff remain visible. | ✓ |
| Keep stale rows dimmed | F1 forbids stale-looking merged history. | |
| Replace widget with centered error panel | Loses framing and handoff. | |

**User's choice:** Clear table + stats, show banner, keep framing/handoff static

### Q3: F2 metadata.source missing — render rows?

| Option | Description | Selected |
|---|---|---|
| Render rows but switch framing to ambiguous | Matches F2 "ambiguous, not silent". | ✓ |
| Suppress rows entirely | Harsher than F2 requires. | |
| Render rows unchanged; only diagnostic reflects ambiguity | Violates F2 "MUST NOT render as trusted". | |

**User's choice:** Render rows but switch banner + detail to ambiguous framing

---

## Claude's Discretion

- Exact CSS class names beyond the four Static ids named in decisions
- Whether the classifier lives in `history_browser.py` or a sibling module
- HTTP error narrowing for the `http=` diagnostic field
- Summary-stats behavior in F2 states

## Deferred Ideas

- Keybinding-toggled diagnostic panel
- Summary-stats ambiguity handling refinement
- Click-to-copy for merged-CLI command
- Per-row "Source" DataTable column (rejected)
