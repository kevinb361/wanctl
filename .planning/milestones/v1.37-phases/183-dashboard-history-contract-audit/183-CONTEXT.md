# Phase 183: Dashboard History Contract Audit - Context

**Gathered:** 2026-04-14
**Status:** Ready for planning

<domain>
## Phase Boundary

Audit the current dashboard history tab and define the dashboard-facing contract it must follow so operators can tell they are looking at endpoint-local HTTP history, understand the source context exposed by the payload, and know how to reach the authoritative merged CLI path. This phase captures the contract and acceptance criteria only; it does not change backend history semantics, storage topology, or control behavior.

</domain>

<decisions>
## Implementation Decisions

### Labeling Language
- **D-01:** The dashboard contract must use explicit operator-facing language that `/metrics/history` is an endpoint-local HTTP history view for the connected autorate daemon, not an authoritative merged cross-WAN history reader.
- **D-02:** The contract should avoid implying parity between the dashboard history tab and `wanctl.history`; the authoritative merged path must remain named as the CLI/module-based reader.
- **D-03:** The dashboard wording should optimize for operational clarity over brevity. If the UI needs short labels, the acceptance criteria should still require one plainly visible explanation in the history tab itself.

### Source Metadata Contract
- **D-04:** The dashboard-facing contract must treat `metadata.source` as required context for the history tab, not optional debug detail.
- **D-05:** At minimum, the contract should require the UI to surface `metadata.source.mode` in operator-comprehensible wording and preserve enough context to explain which backing DB path(s) the endpoint used.
- **D-06:** Raw payload field names such as `local_configured_db` may appear in diagnostics, but the primary UI contract should translate them into operator-facing wording rather than exposing internal values without explanation.

### Operator Handoff Path
- **D-07:** The dashboard contract must provide a clear operator path from the history tab to the authoritative merged CLI workflow, using the existing module/CLI invocation as the canonical proof path.
- **D-08:** The handoff should be framed as “use this when you need merged cross-WAN proof” rather than as a generic help hint.
- **D-09:** Phase 183 should lock the need for this handoff and the wording intent; exact widget placement and styling remain implementation work for Phase 184.

### Failure And Degraded Cases
- **D-10:** The contract must define failure handling for fetch errors and malformed or incomplete history metadata so the dashboard does not silently fall back to merged-history implications.
- **D-11:** If `metadata.source` is missing or incomplete, the history tab should be treated as degraded or ambiguous, and the acceptance criteria should require explicit operator messaging rather than omission.
- **D-12:** Regression coverage in later phases must cover success, source-label rendering, endpoint-local semantics, and degraded/failure states tied to missing or unusable source context.

### Audit Deliverables
- **D-13:** Phase 183 should produce both an ambiguity audit of the current dashboard behavior and a concrete dashboard-facing source contract that Phase 184 can implement directly.
- **D-14:** The source contract should be specific enough to drive UI copy, test assertions, and doc alignment without reopening backend semantics.

### the agent's Discretion
- Exact wording of the final dashboard copy, provided it preserves the locked HTTP-local vs merged-CLI distinction.
- Exact UI placement, visual treatment, and interaction details for source context and operator handoff elements in Phase 184.
- Exact regression-test structure in Phase 185, provided it enforces the locked contract above.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Milestone Scope And Requirements
- `.planning/ROADMAP.md` — v1.37 phase goals and sequencing for Phases 183-185.
- `.planning/REQUIREMENTS.md` — `DASH-01` through `OPER-05`, out-of-scope boundaries, and traceability.
- `.planning/PROJECT.md` — milestone intent: make dashboard history-source semantics explicit without reopening storage/control work.
- `.planning/STATE.md` — carried-forward operational truth that dashboard history still hides the narrowed source contract.

### History Contract Decisions
- `.planning/phases/181-production-footprint-reduction-and-reader-parity/181-reader-parity-decision.md` — locked reader-role split: CLI merged, HTTP endpoint-local, plus additive `metadata.source`.
- `.planning/phases/181-production-footprint-reduction-and-reader-parity/181-live-reader-parity-report.md` — production evidence for the narrowed HTTP-local behavior and source metadata.
- `.planning/phases/179-verification-and-operator-evidence/179-live-reader-topology-report.md` — earlier live proof showing why HTTP could not remain an implied merged proof surface.
- `.planning/phases/178-retention-tightening-and-legacy-db-cleanup/178-operator-verification-path.md` — prior operator read-path guidance and topology context.

### Operator Documentation
- `docs/RUNBOOK.md` — current operator guidance that HTTP history is endpoint-local and CLI is the authoritative cross-WAN proof path.
- `docs/DEPLOYMENT.md` — deployment-facing wording for endpoint-local `/metrics/history` versus merged CLI reads.

### Current Implementation And Test Surfaces
- `src/wanctl/health_check.py` — `/metrics/history` response contract, including `metadata.source` and endpoint-local DB resolution.
- `src/wanctl/dashboard/widgets/history_browser.py` — current dashboard history consumer that ignores source metadata and implies a generic history browser.
- `tests/dashboard/test_history_browser.py` — current widget coverage that will need contract-aware expansion in later phases.
- `tests/test_health_check.py` — endpoint contract coverage, including local configured DB behavior and `metadata.source`.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `src/wanctl/dashboard/widgets/history_browser.py`: Existing `HistoryBrowserWidget` already owns the history-tab fetch/render path, so Phase 184 can layer source-context UI into one focused widget rather than redesigning the app shell.
- `src/wanctl/dashboard/app.py`: The dashboard already isolates history in its own tab pane, which gives a clean integration point for clarified labeling and operator guidance.
- `src/wanctl/health_check.py`: The HTTP backend already emits `metadata.source.mode` and `metadata.source.db_paths`; Phase 184 should consume that additive metadata rather than invent a parallel contract.

### Established Patterns
- The health/history API preserves a `{data, metadata}` envelope and newest-first ordering; the dashboard contract should stay additive and explanatory, not demand backend shape changes.
- Operator documentation already names the CLI/module path as authoritative for merged cross-WAN proof, so the UI contract should align to that established operational story.
- Existing widget tests focus on rows and summary stats, which means Phase 185 will need to expand coverage around source semantics and degraded states rather than replacing the widget test approach.

### Integration Points
- History-tab contract work centers on `src/wanctl/dashboard/widgets/history_browser.py` and its tests.
- Operator wording alignment will need to stay consistent with `docs/RUNBOOK.md` and `docs/DEPLOYMENT.md`.
- Backend contract assumptions should be validated against `src/wanctl/health_check.py` and `tests/test_health_check.py`, but not changed in this phase.

</code_context>

<specifics>
## Specific Ideas

- Prefer plain operator wording such as “This view shows history from the connected autorate endpoint” over raw internal semantics alone.
- Preserve the backend field names (`metadata.source.mode`, `metadata.source.db_paths`) as the diagnostic truth underneath the UI wording.
- Treat missing source metadata as an explicit ambiguity that the UI must surface, not as a cue to silently render the old generic history experience.

</specifics>

<deferred>
## Deferred Ideas

- Any backend changes to broaden `/metrics/history` back into a merged cross-WAN proof path are out of scope for this milestone.
- Any storage-topology, retention, compaction, or control-loop changes remain out of scope.
- Broader dashboard redesign beyond the history-tab source contract belongs in future phases if needed.

</deferred>

---

*Phase: 183-dashboard-history-contract-audit*
*Context gathered: 2026-04-14*
