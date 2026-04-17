# Phase 185: Verification And Operator Alignment - Context

**Gathered:** 2026-04-14
**Status:** Ready for planning

<domain>
## Phase Boundary

Lock the Phase 184 dashboard history contract with regression coverage,
operator-facing documentation/workflow alignment, and milestone-closeout
verification. This phase proves the new endpoint-local dashboard semantics,
the merged-CLI handoff, and the degraded/failure behavior without changing
`/metrics/history` backend behavior, storage topology, retention, or control
logic.

</domain>

<decisions>
## Implementation Decisions

### Regression Scope
- **D-01:** Phase 185 should add focused regression coverage around the locked
  dashboard history contract instead of broad new infrastructure tests. The
  core proof surface is the dashboard history classifier/copy contract plus the
  widget render behavior that consumes it.
- **D-02:** Regression coverage should be layered:
  - pure tests for `src/wanctl/dashboard/widgets/history_state.py` state
    classification and locked copy invariants
  - focused widget tests for `HistoryBrowserWidget` compose/fetch behavior,
    including success, fetch-error, and ambiguous source states
  - only the narrowest additional endpoint assertions needed to keep dashboard
    assumptions aligned with the existing `/metrics/history` payload contract
- **D-03:** The Phase 183 contract surface in `183-dashboard-source-contract.md`
  is the authoritative checklist for `DASH-04`; tests should trace directly to
  its degraded/failure requirements rather than inventing broader dashboard
  expectations.

### Operator Guidance Surfaces
- **D-04:** Operator-facing guidance should be aligned in the docs that already
  define the active deployment and troubleshooting flow:
  - `docs/DEPLOYMENT.md`
  - `docs/RUNBOOK.md`
  - `docs/GETTING-STARTED.md`
  These are the primary workflow surfaces for `OPER-05`.
- **D-05:** The aligned guidance should keep one consistent rule everywhere:
  `/metrics/history` is the endpoint-local HTTP history view for the connected
  daemon, while `python3 -m wanctl.history` is the authoritative merged
  cross-WAN proof path.
- **D-06:** Scripts and helper commands should only be updated when their
  operator-facing output or embedded guidance conflicts with the locked wording.
  Do not expand Phase 185 into deploy-flow refactoring or new helper behavior.

### Closeout Evidence
- **D-07:** Phase 185 closeout should be repo-side and traceability-driven:
  prove `DASH-04` with targeted regressions, prove `OPER-05` with doc/workflow
  alignment, and record both against the Phase 183 contract plus v1.37
  requirements.
- **D-08:** Verification should explicitly show that the dashboard wording still
  avoids parity claims with `wanctl.history`, that the handoff remains verbatim,
  and that degraded/failure states stay operator-visible rather than silently
  trusted.
- **D-09:** Milestone closeout for this phase should not require new production
  storage or live control-loop evidence. The acceptance target is contract
  alignment across tests, widget behavior, and operator docs.

### the agent's Discretion
- Exact split of tests between pure classifier coverage and mounted Textual
  widget coverage, as long as the full Phase 183 regression surface is proven.
- Whether existing `tests/test_health_check.py` coverage is sufficient for the
  backend payload contract or needs one narrow additive assertion.
- The exact verification artifact structure for the closeout plan, as long as
  it traces decisions back to `DASH-04` and `OPER-05`.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Locked Contract And Prior Phase Decisions
- `.planning/phases/183-dashboard-history-contract-audit/183-dashboard-source-contract.md` — locked contract for endpoint-local framing, `metadata.source` surfacing, merged-CLI handoff, and degraded/failure requirements; primary source for Phase 185 traceability
- `.planning/phases/183-dashboard-history-contract-audit/183-dashboard-ambiguity-audit.md` — evidence base for the contract and the ambiguity Phase 185 is meant to keep closed
- `.planning/phases/183-dashboard-history-contract-audit/183-CONTEXT.md` — Phase 183 decision source behind the contract
- `.planning/phases/184-dashboard-history-source-surfacing/184-CONTEXT.md` — locked Phase 184 UI decisions that Phase 185 must verify rather than reopen

### Milestone Scope
- `.planning/ROADMAP.md` §Phase 185 — phase goal and three-plan structure for regressions, operator alignment, and closeout verification
- `.planning/REQUIREMENTS.md` — `DASH-04` and `OPER-05` are the only pending v1.37 requirements and define the Phase 185 pass/fail envelope
- `.planning/STATE.md` — current milestone status and prior-phase carry-forward decisions relevant to the history contract

### Dashboard Implementation Under Test
- `src/wanctl/dashboard/widgets/history_state.py` — pure state classifier and locked copy constants extracted in Phase 184 specifically to support Phase 185 regression coverage
- `src/wanctl/dashboard/widgets/history_browser.py` — `HistoryBrowserWidget` implementation consuming the state classifier and rendering the operator-facing framing, handoff, and diagnostics
- `tests/dashboard/test_history_browser.py` — existing dashboard history test file and the natural expansion point for Phase 185 widget regressions

### Payload And Operator Workflow References
- `src/wanctl/health_check.py` §`_handle_metrics_history` and `_resolve_history_db_paths` — read-only backend contract for `metadata.source.mode` and `metadata.source.db_paths`
- `docs/DEPLOYMENT.md` — active deployment/operator flow that already distinguishes endpoint-local HTTP history from merged CLI proof
- `docs/RUNBOOK.md` — operator troubleshooting and proof-path guidance that must stay aligned with dashboard semantics
- `docs/GETTING-STARTED.md` — first-pass operator flow that should not teach conflicting history semantics

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `classify_history_state()` in `src/wanctl/dashboard/widgets/history_state.py`:
  pure decision surface for success, fetch-error, and ambiguous-source cases
- `HISTORY_COPY` and `HistoryBrowserWidget.HANDOFF_TEXT`: locked copy surfaces
  that can be asserted directly without duplicating strings in tests
- `tests/dashboard/test_history_browser.py`: existing widget test module that
  already mounts the widget and mocks HTTP responses

### Established Patterns
- Dashboard contract checks are intentionally conservative: Phase 184 moved the
  state machine and copy constants into a pure module so Phase 185 can test the
  contract without depending entirely on Textual event-loop paths.
- Operator docs already use `python3 -m wanctl.history` as the authoritative
  merged proof path and describe `/metrics/history` as endpoint-local; Phase 185
  should align and tighten this wording, not invent a new workflow.

### Integration Points
- `tests/dashboard/test_history_browser.py` is the main integration point for
  widget regressions.
- `src/wanctl/dashboard/widgets/history_state.py` is the main integration point
  for pure contract tests.
- `docs/DEPLOYMENT.md`, `docs/RUNBOOK.md`, and `docs/GETTING-STARTED.md` are
  the main integration points for `OPER-05` operator alignment.

</code_context>

<specifics>
## Specific Ideas

- Default to targeted, contract-shaped tests rather than broad dashboard test
  expansion.
- Keep the existing operator wording stable: endpoint-local dashboard view,
  authoritative merged CLI proof path.
- Treat milestone verification as a traceability exercise tied to the locked
  contract, not as a request for new live-production evidence.

</specifics>

<deferred>
## Deferred Ideas

### Reviewed Todos (not folded)
- `2026-03-11-narrow-layout-truncates-wan-panels.md` — reviewed because of a
  weak dashboard keyword match, but deferred as out of scope for Phase 185.
  This phase is about history-contract regressions and operator wording, not
  general dashboard layout changes.
- `2026-04-08-add-minimum-confidence-threshold-to-autotuner.md` — unrelated to
  dashboard history verification/operator alignment; remains outside this
  milestone slice.

None beyond the reviewed todos above.

</deferred>

---

*Phase: 185-verification-and-operator-alignment*
*Context gathered: 2026-04-14*
