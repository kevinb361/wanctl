# Dashboard History Source Contract

Phase 183-02 locked contract. Markdown-only. No backend changes. Consumed by Phase 184 (UI) and Phase 185 (tests + docs). This contract uses [183-dashboard-ambiguity-audit.md](/home/kevin/projects/wanctl/.planning/phases/183-dashboard-history-contract-audit/183-dashboard-ambiguity-audit.md) as the evidence base and [183-CONTEXT.md](/home/kevin/projects/wanctl/.planning/phases/183-dashboard-history-contract-audit/183-CONTEXT.md) as the decision source.

## Scope And Non-Goals

This contract governs dashboard history-tab source semantics, required labeling, required surfacing of source metadata, the operator handoff to merged proof, and degraded-state messaging. Per D-14, it is specific enough to drive UI copy, test assertions, and doc alignment without reopening backend history semantics.

Scope includes the dashboard wording envelope for endpoint-local framing, operator comprehension of `metadata.source`, and the visible path to merged cross-WAN proof. D-13 and D-14 make this file the locked source of truth for Phases 184 and 185.

Non-goals:
- No backend change to `/metrics/history`.
- No storage, retention, or compaction changes.
- No control-loop or autorate semantic changes.
- No exact widget placement, styling, or visual-treatment mandate.
- No test implementation details beyond the required regression surface.

## Labeling Requirements

### L1. Endpoint-Local Framing (D-01)

Per D-01, the history tab MUST make it explicit that `/metrics/history` is an endpoint-local HTTP history view for the connected autorate daemon, not an authoritative merged cross-WAN history reader. REQUIRED PHRASE (placeholder, final wording is Phase 184 discretion): "This view shows history from the connected autorate endpoint only."

The primary history-tab wording MUST NOT use bare phrases such as "all WANs", "merged history", or "cross-WAN history" unless they are explicitly qualified as referring to the separate merged CLI proof path.

### L2. No Implied Parity With wanctl.history (D-02)

Per D-02, the contract forbids the UI from implying parity between the history tab and `wanctl.history`. Any wording that names `wanctl.history` or `python3 -m wanctl.history` MUST frame it as the separate authoritative merged reader, not as a parallel description of the dashboard tab itself.

### L3. Plainly Visible Explanation (D-03)

Per D-03, at least one plainly visible explanatory sentence MUST appear inside the history tab itself. Tooltip-only, modal-only, or hidden diagnostic wording does not satisfy the contract, even if shorter labels exist elsewhere in the tab.

## Source Metadata Requirements

### S1. metadata.source Is Required Context (D-04)

Per D-04, the dashboard contract treats `metadata.source` as required operator context, not optional debug detail. The authoritative backend fields are `metadata.source.mode` and `metadata.source.db_paths`, and the UI contract MUST derive operator wording from those exact fields without inventing new field names.

### S2. Mode Surfacing In Operator Wording (D-05)

Per D-05, the UI MUST surface `metadata.source.mode` in operator-comprehensible wording and MUST preserve enough context to explain which backing DB path or DB set the endpoint used through information derived from `metadata.source.db_paths`.

Minimum mode mapping:
- `local_configured_db` -> placeholder operator phrase: "Connected endpoint local database"
- `merged_discovery` -> placeholder operator phrase: "Discovered database set on this endpoint"

Phase 184 may refine wording, but it may not hide the source mode distinction or remove the DB-path-derived context.

### S3. Raw Field Values Allowed In Diagnostics Only (D-06)

Per D-06, raw payload field values such as `local_configured_db` may appear in a diagnostic or detail surface only. The primary operator label MUST translate the internal value into operator-facing wording rather than exposing raw internals without explanation.

## Operator Handoff Requirements

### H1. Canonical Merged-Proof Path (D-07)

Per D-07, the history tab MUST expose a clear operator path to the authoritative merged CLI workflow. The verified canonical invocation is `python3 -m wanctl.history`: the module has a `main()` entrypoint and is the form already used by repo docs, while the parser also declares `prog="wanctl-history"` for CLI naming. This handoff exists to prove merged cross-WAN history, not endpoint-local history.

### H2. Framed As "Use When You Need Merged Proof" (D-08)

Per D-08, the handoff MUST be framed as the answer to "what do I run when I need merged cross-WAN proof?" It MUST NOT be framed as generic help, an unlabeled docs link, or a tooltip-only hint.

### H3. Wording Intent Locked, Placement Deferred (D-09)

Per D-09, this contract locks the need for the handoff and its wording intent, but exact widget placement, visual treatment, and interaction details remain Phase 184 discretion.

## Degraded And Failure Requirements

### F1. Explicit Failure Messaging, No Silent Fallback (D-10)

Per D-10, on fetch error, timeout, non-200 response, or malformed JSON, the history tab MUST show an explicit operator-visible failure state and MUST NOT render stale rows in a way that implies current merged history. REQUIRED ERROR PHRASE (placeholder): "History unavailable - use python3 -m wanctl.history when you need merged cross-WAN proof."

### F2. Missing/Incomplete metadata.source Is Ambiguous, Not Silent (D-11)

Per D-11, if `metadata.source` is absent, malformed, or missing `metadata.source.mode`, the history tab MUST surface that the source context is ambiguous and MUST NOT render as if it were trusted endpoint-local history. REQUIRED DEGRADED PHRASE (placeholder): "Source context unavailable - treat this history view as ambiguous; use python3 -m wanctl.history for authoritative merged proof."

If `metadata.source.mode` is present but `metadata.source.db_paths` is missing or empty, the UI MUST remain in degraded or ambiguous framing rather than silently presenting the view as fully trusted.

### F3. Regression Surface Areas For Phase 185 (D-12)

Per D-12, Phase 185 MUST cover these regression surface areas:
- success rendering with `metadata.source.mode == "local_configured_db"`
- plainly visible endpoint-local label
- DB-path-derived source context rendered from `metadata.source.db_paths`
- visible CLI handoff to `python3 -m wanctl.history`
- fetch-error failure state
- missing-`metadata.source` degraded state
- missing-`metadata.source.mode` degraded state
- missing-or-empty-`metadata.source.db_paths` degraded state

## Acceptance Criteria

These criteria are the Phase 184 and Phase 185 pass/fail envelope. Phase 184 may refine wording within these constraints, but it may not relax them.

1. The history tab contains a plainly visible explanation equivalent to "endpoint-local" or "from the connected autorate endpoint." [D-01, D-03, DASH-01]
2. The history tab UI does not contain any bare phrase implying merged cross-WAN scope without qualification. [D-01, DASH-01]
3. When `metadata.source.mode == "local_configured_db"`, the UI renders an operator-facing label distinct from merged-history wording. [D-04, D-05, D-06, DASH-02]
4. The UI renders operator-comprehensible information derived from `metadata.source.db_paths`. [D-05, DASH-02]
5. The raw string `local_configured_db` is not the primary operator label; it may appear only in a diagnostic or detail surface. [D-06, DASH-02]
6. The history tab exposes a visible CLI handoff naming `python3 -m wanctl.history`, framed as "use this when you need merged cross-WAN proof." [D-07, D-08, DASH-03]
7. The history tab does not describe itself as equivalent to `wanctl.history` or `wanctl-history`. [D-02, DASH-03]
8. On fetch failure, the UI shows a visible "History unavailable" style message and does not render stale rows implying merged history. [D-10, DASH-04]
9. When `metadata.source` is missing or malformed, the UI shows an explicit "source context unavailable" or "ambiguous" style message and does not render as trusted endpoint-local history. [D-11, DASH-04]
10. When `metadata.source.mode` is present but `metadata.source.db_paths` is missing or empty, the UI still renders degraded or ambiguous framing. [D-11, DASH-04]
11. A successful render includes a source label derived from `metadata.source.mode` and a separate surface derived from `metadata.source.db_paths`. [D-04, D-05, DASH-02]
12. After Phase 185 alignment, operator documentation in `docs/RUNBOOK.md` and `docs/DEPLOYMENT.md` matches the dashboard's endpoint-local and merged-proof wording. [D-12, OPER-05]

## Traceability

| Decision | Contract Section | Downstream Phase | Downstream Requirement | Notes |
| --- | --- | --- | --- | --- |
| D-01 | `### L1. Endpoint-Local Framing (D-01)`; `## Acceptance Criteria` items 1-2 | 184 | DASH-01 | Locks endpoint-local framing. |
| D-02 | `### L2. No Implied Parity With wanctl.history (D-02)`; `## Acceptance Criteria` item 7 | 184 | DASH-03 | Forbids parity language with merged CLI. |
| D-03 | `### L3. Plainly Visible Explanation (D-03)`; `## Acceptance Criteria` item 1 | 184 | DASH-01 | Requires visible in-tab explanation. |
| D-04 | `### S1. metadata.source Is Required Context (D-04)`; `## Acceptance Criteria` items 3 and 11 | 184 | DASH-02 | Makes `metadata.source` mandatory context. |
| D-05 | `### S2. Mode Surfacing In Operator Wording (D-05)`; `## Acceptance Criteria` items 3-4 and 11 | 184 | DASH-02 | Requires mode and DB-path-derived context. |
| D-06 | `### S3. Raw Field Values Allowed In Diagnostics Only (D-06)`; `## Acceptance Criteria` items 3 and 5 | 184 | DASH-02 | Keeps raw internals out of primary wording. |
| D-07 | `### H1. Canonical Merged-Proof Path (D-07)`; `## Acceptance Criteria` item 6 | 184 | DASH-03 | Names the canonical merged-proof invocation. |
| D-08 | `### H2. Framed As "Use When You Need Merged Proof" (D-08)`; `## Acceptance Criteria` item 6 | 184 | DASH-03 | Locks framing intent for handoff. |
| D-09 | `### H3. Wording Intent Locked, Placement Deferred (D-09)` | 184 | DASH-03 | Placement is intentionally deferred. |
| D-10 | `### F1. Explicit Failure Messaging, No Silent Fallback (D-10)`; `## Acceptance Criteria` item 8 | 185 | DASH-04 | Fetch failure must be explicit. |
| D-11 | `### F2. Missing/Incomplete metadata.source Is Ambiguous, Not Silent (D-11)`; `## Acceptance Criteria` items 9-10 | 185 | DASH-04 | Missing source context stays degraded. |
| D-12 | `### F3. Regression Surface Areas For Phase 185 (D-12)`; `## Acceptance Criteria` item 12 | 185 | DASH-04, OPER-05 | Defines regression and doc-alignment surface. |
| D-13 | `## Scope And Non-Goals`; `## Traceability` | - | - | This phase produces both the audit and the contract. |
| D-14 | `## Scope And Non-Goals`; `## Acceptance Criteria` | - | - | Contract is specific enough for Phases 184 and 185. |

## Out Of Scope

- Backend changes to `/metrics/history`
- Storage topology, retention, or compaction work
- Control-loop semantics
- Exact widget placement, styling, visual treatment, or interaction details
- Regression test implementation details
- Broader dashboard redesign beyond the history tab

*Contract locked by Phase 183-02. Implemented by Phase 184. Verified by Phase 185.*
