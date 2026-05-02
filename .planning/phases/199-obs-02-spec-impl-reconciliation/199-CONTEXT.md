# Phase 199: OBS-02 Spec/Impl Reconciliation - Context

**Gathered:** 2026-05-02
**Status:** Ready for planning

<domain>
## Phase Boundary

Close the OBS-02 spec/implementation drift caveat from the v1.40 audit by formally specifying absent-row semantics for the per-WAN metrics SQLite store and propagating that wording to operator-facing documentation. **Docs-only.** No Python source under `src/wanctl/` may change. Implementation behavior is intentional and test-pinned (`_select_dl_primary_scalar_ms()` reads `_last_rtt_confidence` directly in-process at `wan_controller.py:2785`; SQLite emission gate at `wan_controller.py:3142`; absent-row test pin at `tests/test_wan_controller.py:2629`).

The audit predicate keys on always-emitted `wanctl_arbitration_active_primary`, so no Phase 196 / Phase 198 verdict depends on per-cycle `wanctl_rtt_confidence` row coverage. Sentinel emission (NaN, -1) is rejected as a violation of the metric's documented `[0.0, 1.0]` contract that would skew downstream Prometheus-style aggregates. The reconciliation is therefore a wording fix in REQUIREMENTS.md plus operator documentation that names the reliable per-cycle denominator.

</domain>

<decisions>
## Implementation Decisions

### REQUIREMENTS.md Verification

- **D-01: REQUIREMENTS.md OBS-02 wording is already pre-staged.** The amended OBS-02 row in `.planning/REQUIREMENTS.md` already states absent-row semantics ("cold-start and invalid-snapshot cycles produce absent SQLite rows and `/health` nulls — no NaN, -1, or sentinel emission") and is annotated `*Wording amended in Phase 199 to formally specify absent-row semantics.*`. The traceability table also already shows `OBS-02 | Phase 193 + Phase 199 (wording amendment) | Complete (caveat resolved by Phase 199)`. Phase 199's task is to **verify** the staged wording matches the implementation contract and capture that verification in `199-VERIFICATION.md` — not to re-amend.
  **Why:** Re-amending re-opens the wording. The audit already accepted the staged wording as the resolution; Phase 199 closes the loop by recording that the wording matches the test-pinned behavior at the three referenced source locations.

### Doc Home for Absent-Row Semantics

- **D-02: Add the `signal_arbitration` payload-shape note to `docs/SUBSYSTEMS.md`.** SUBSYSTEMS.md already owns the `/health` "Major response sections" enumeration (lines 128–138). Add a short subsection or bullet expansion under the `wans[]` row that names the four `signal_arbitration` fields (`active_primary_signal`, `rtt_confidence`, `cake_av_delay_delta_us`, `control_decision_reason`), documents nullability of the two numeric fields, and points to the metrics-store absent-row note in RUNBOOK.md.
  **Why:** SUBSYSTEMS.md is the canonical home for `/health` payload shape. `docs/CONFIGURATION.md` is the YAML config schema doc and currently does not mention `/health` fields at all — putting the note there would create a doc-organization drift. The roadmap entry explicitly allows "or wherever per-WAN `signal_arbitration` is documented." This exercises that flexibility for the location that matches existing doc organization.

- **D-03: Add the operator-query note to `docs/RUNBOOK.md` in the SQLite/metrics-history section.** RUNBOOK.md already documents `/metrics/history` queries and `python3 -m wanctl.history` invocations (lines ~340–365). The note states: `wanctl_arbitration_active_primary` is the always-emitted per-cycle row and is the reliable denominator for any coverage query against the per-WAN metrics SQLite store; `wanctl_rtt_confidence` and `wanctl_cake_avg_delay_delta_us` are emitted only when valid, so absent rows for those metrics represent cold-start or invalid-snapshot cycles, not data loss.
  **Why:** Operators reading RUNBOOK.md to investigate metrics coverage need this guidance in the same section that already shows how to query the store. Putting it elsewhere risks the guidance being missed exactly when it is needed (during incident triage). RUNBOOK.md is also the doc most likely to be reread per incident.

### Wording Source-of-Truth

- **D-04: Quote REQUIREMENTS.md OBS-02 verbatim in the operator note.** The operator-query note in RUNBOOK.md and the field-nullability note in SUBSYSTEMS.md should reuse the exact phrase from REQUIREMENTS.md OBS-02: "cold-start and invalid-snapshot cycles produce absent SQLite rows and `/health` nulls — no NaN, -1, or sentinel emission." Add a short inline reference back to REQUIREMENTS.md OBS-02 so future readers can trace the contract source.
  **Why:** The whole point of this phase is spec/impl/doc lockstep. Paraphrasing in operator docs creates a third surface that can drift independently. Quoting verbatim makes the spec the single source of truth and makes future audits (e.g., a Phase 200 traceability check) trivial.

### VERIFICATION.md Form

- **D-05: `199-VERIFICATION.md` records four invariant checks.** Pattern follows `198-VERIFICATION.md` (YAML frontmatter + body). Required checks:
  1. **Docs-only invariant:** `git diff --name-only <phase-base>..HEAD -- src/wanctl/` returns empty (zero Python source changes under `src/wanctl/`).
  2. **REQUIREMENTS.md OBS-02 wording:** the OBS-02 row contains the four anchor phrases (`absent SQLite rows`, `cold-start`, `invalid-snapshot`, `wanctl_arbitration_active_primary`) and the Phase 199 annotation.
  3. **Doc edits exist:** `docs/SUBSYSTEMS.md` mentions `signal_arbitration` and the four field names; `docs/RUNBOOK.md` mentions `wanctl_arbitration_active_primary` as the per-cycle denominator.
  4. **Test-pin sanity:** `tests/test_wan_controller.py:2629` still encodes the absent-row behavior the spec describes (line range may shift; check by test-name search instead of exact line).
  **Why:** Audit reproducibility. Each check is a one-line `git`/`grep` invocation that any operator or future auditor can rerun. The phase's verdict rests entirely on these four checks, so they must be mechanizable.

- **D-06: Verification frontmatter records phase scope as `docs-only` and lists the three changed/verified files.** YAML frontmatter mirrors `198-VERIFICATION.md` shape: `phase`, `verified`, `status`, `score`, `requirements: [OBS-02]`, plus a `phase_scope: docs-only` field and a `files_touched: [.planning/REQUIREMENTS.md, docs/SUBSYSTEMS.md, docs/RUNBOOK.md]` list.
  **Why:** Grep-able verdict + machine-checkable scope assertion. A post-merge audit script can parse the frontmatter to confirm no Python files appear in `files_touched`.

### Out of Scope (Locked)

- **D-07: No Python behavior change.** No new metric, no new field, no new emission gate, no sentinel substitution, no `signal_arbitration` schema change. The CHANGELOG.md / control-flow code paths in `wan_controller.py` and `health_check.py` are not edited.
  **Why:** Roadmap entry locks this explicitly. The audit already accepted the implementation as correct; the gap is purely a wording one.

- **D-08: Do not re-document `/health` from scratch.** Phase 199 adds short, targeted notes; it does not reorganize SUBSYSTEMS.md or RUNBOOK.md. Major rewrites would mask the targeted spec/impl/doc reconciliation in a doc refactor.
  **Why:** Keeps the diff small and reviewable; preserves the audit-friendly "this is what changed for OBS-02" property.

### Claude's Discretion

- **Exact heading or bullet shape** for the SUBSYSTEMS.md `signal_arbitration` field expansion (sub-bullet under `wans[]`, separate `### Signal Arbitration` subsection, or paragraph under "Major response sections") — pick the form most consistent with the surrounding doc style. Preserve existing surrounding wording.
- **Whether the RUNBOOK.md operator note** lives next to the `/metrics/history` curl example, the `python3 -m wanctl.history` example, or as a `> Note:` callout. Pick the form that most reduces the chance an operator misses it during incident triage.
- **Whether `199-VERIFICATION.md` adds a fifth check** that runs `pytest -k "absent_rtt_confidence_row" -q tests/test_wan_controller.py` to re-prove the test pin — fine to add if it stays under 5 seconds; skip if it requires the full controller fixture stack.
- **Whether to also add a one-line cross-reference** in `docs/CONFIGURATION.md` ("for `/health` field semantics, see SUBSYSTEMS.md") — only if there is already a docs-cross-link convention established in the repo; do not introduce a new convention.

### Folded Todos

None. The 16 todos that matched on keyword overlap (`wanctl`, `src`, `cycle`, `code`, `under`, etc.) are all about runtime / performance / operations investigations (latency spikes, CPU steal, profiling, soak verification, gauge audits, ATT canary, Silicom NICs, archive cleanup). None align with a docs-only OBS-02 wording-reconciliation phase. All scored 0.6 from generic keyword overlap, not topical relevance. Auto-mode literal rule (`fold >= 0.4`) was overridden because the score is keyword noise rather than topical signal — folding any of these would expand a docs-only phase into a runtime/performance grab bag and break the locked phase scope.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase scope and locked invariants
- `.planning/ROADMAP.md` — Phase 199 entry; `Scope`, `Out of scope (locked)`, and `Success Criteria` define the docs-only contract and the three deliverables (REQUIREMENTS.md verify, doc note, operator-query note).
- `.planning/REQUIREMENTS.md` — OBS-02 row (already amended) and the v1.40 traceability table line `OBS-02 | Phase 193 + Phase 199 (wording amendment) | Complete (caveat resolved by Phase 199)`. This is the **spec source of truth** that operator docs must quote.
- `.planning/STATE.md` — v1.40 status `ready_to_plan`; Phase 199 is the last open phase in v1.40.
- `.planning/PROJECT.md` — milestone v1.40 summary; sub-section "Current Milestone: v1.40 Queue-Primary Signal Arbitration" frames why OBS-02 matters.

### Prior-phase implementation pins (DO NOT modify)
- `src/wanctl/wan_controller.py:2785` — `_select_dl_primary_scalar_ms()` reads `_last_rtt_confidence` directly in-process; this is the in-process consumer that does not need a SQLite row to function.
- `src/wanctl/wan_controller.py:3142` — SQLite emission gate that produces the absent-row behavior when `_last_rtt_confidence is None`.
- `tests/test_wan_controller.py:2629` — the test that locks absent-row semantics; the spec wording must remain consistent with what this test asserts.
- `.planning/phases/193-queue-signal-contract-and-arbitration-telemetry/193-CONTEXT.md` — Phase 193 OBS-01 + OBS-02 origin; D-01..D-08 frame the original `signal_arbitration` payload shape.

### Doc surfaces edited or referenced
- `docs/SUBSYSTEMS.md` — `## Health And Metrics` section (lines ~120–145); the `wans[]` field enumeration is the natural home for the `signal_arbitration` field-shape note (D-02).
- `docs/RUNBOOK.md` — `/health` inspection examples (lines ~239–265) and `/metrics/history` + `python3 -m wanctl.history` reader section (lines ~340–365); operator-query note lands here (D-03).
- `docs/CONFIGURATION.md` — YAML config schema doc; **does not currently document `/health`**. Touch only for an optional one-line cross-reference if a cross-link convention already exists (Claude's discretion).

### Verification artifacts
- `.planning/phases/198-spectrum-cake-primary-b-leg-rerun/198-VERIFICATION.md` — pattern reference for `199-VERIFICATION.md`: YAML frontmatter shape, `requirements:` list, scoring convention.
- `.planning/phases/197-queue-primary-refractory-semantics-split-dl-cake-for-detecti/197-CONTEXT.md` — prior-phase context structure used as template here.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **REQUIREMENTS.md OBS-02 row, already pre-staged.** The amended wording is in place; Phase 199 reuses it verbatim instead of rewriting. Direct-quoting it in operator docs (D-04) inherits the spec language without paraphrase risk.
- **Phase 198 VERIFICATION.md frontmatter pattern.** YAML frontmatter (`phase`, `verified`, `status`, `score`, `requirements`) is the project precedent. Phase 199 extends with `phase_scope: docs-only` and `files_touched: [...]` (D-06) without inventing new conventions.
- **`docs/SUBSYSTEMS.md` "Major response sections" enumeration.** Already lists `wans[]` fields including `signal_arbitration` by virtue of being a `wans[]` member. Phase 199 expands the existing line into a sub-bullet, not a new top-level section.

### Established Patterns
- **Spec → impl → doc lockstep, audited per phase.** The v1.40 audit caught the OBS-02 doc gap precisely because traceability tables map every REQ-ID to the phase that satisfies it. Phase 199 closes the audit's last open caveat using that same machinery.
- **Docs-only phases produce a `phase-VERIFICATION.md` invariant proof.** Precedent: any phase that touches docs only must prove no source files changed; checked via `git diff --name-only -- src/wanctl/` returning empty.
- **Per-cycle metric coverage uses `wanctl_arbitration_active_primary` as the denominator.** Established across Phase 196 / 197 / 198 audit scripts; Phase 199 propagates this convention into operator-facing docs (D-03).

### Integration Points
- **SUBSYSTEMS.md `## Health And Metrics` section** — single insertion point for the field-shape note. The surrounding paragraph already lists `wans[]`/`alerting`/`disk_space`/`summary`/`storage`/`runtime` rows, so a sub-bullet under `wans[]` slots in cleanly without re-flowing the section.
- **RUNBOOK.md `/metrics/history` operator example** (lines ~353–365) — single insertion point for the operator-query note. The note attaches to the existing `curl .../metrics/history` example as additional guidance, not a new heading.
- **`tests/test_wan_controller.py` absent-row test** — referenced from `199-VERIFICATION.md` to anchor the test-pin sanity check (D-05 check 4). Do not edit the test.

</code_context>

<specifics>
## Specific Ideas

- The roadmap entry already names the deliverables in operational order: (1) REQUIREMENTS.md OBS-02 verify, (2) `docs/CONFIGURATION.md` (or wherever) absent-row note, (3) operator-query note. Phase 199 keeps that order and substitutes SUBSYSTEMS.md + RUNBOOK.md for "or wherever" with documented justification (D-02, D-03).
- The phrase "absent SQLite rows for `wanctl_rtt_confidence` and `wanctl_cake_avg_delay_delta_us`" from the roadmap is the operator-facing wording the audit expects — quote it (or its REQUIREMENTS.md verbatim equivalent) in the doc edits rather than rewording.
- `wanctl_arbitration_active_primary` as the per-cycle denominator is the **single most important** thing operators need to learn from this phase. It deserves a `Note:` callout or bold inline phrase rather than burial inside a paragraph.
- The audit framing — "no Phase 196 / Phase 198 verdict depended on per-cycle `wanctl_rtt_confidence` row coverage" — is the assurance that justifies docs-only resolution. It does not need to appear in operator docs but should appear in `199-VERIFICATION.md` as the rationale for the `phase_scope: docs-only` decision.

</specifics>

<deferred>
## Deferred Ideas

- **Sentinel emission (NaN or -1) for `wanctl_rtt_confidence` / `wanctl_cake_avg_delay_delta_us` to make every cycle row-present.** Rejected by the roadmap as a violation of the documented `[0.0, 1.0]` contract for `rtt_confidence` and as Prometheus-aggregate-skewing. Out of charter for v1.40 and beyond unless a future audit predicate genuinely requires per-cycle row coverage.
- **Reorganizing `docs/SUBSYSTEMS.md` `## Health And Metrics` into a per-field reference table.** A doc-quality improvement worth doing later, but it inflates Phase 199's diff and breaks the "small targeted note" property the audit needs. Capture as a future docs phase.
- **Cross-reference link in `docs/CONFIGURATION.md` pointing at SUBSYSTEMS.md `/health` field docs.** Tracked as Claude's-discretion only if a cross-link convention is already in repo (D-08 sub-bullet); otherwise deferred to a future docs-organization phase.
- **A live audit hook** (e.g., `make audit-traceability`) that re-runs the OBS-02 spec/doc anchor check on every CI run. Useful but out of scope for a one-shot reconciliation phase. Capture as a tooling phase under a future milestone.

### Reviewed Todos (not folded)

All 16 keyword-matched todos reviewed and explicitly **not folded**: each is a runtime / performance / operations investigation that does not relate to docs-only OBS-02 wording reconciliation. Listed for traceability so a future phase can pick them up:

- `2026-04-08-investigate-tcp-12down-latency-spikes-under-multi-flow-downl.md` — performance investigation; unrelated.
- `2026-04-10-monitor-proxmox-steal-cpu.md` — operations monitoring; unrelated.
- `2026-04-12-investigate-steering-cycle-overruns-and-blocking-i-o.md` — performance investigation on steering daemon; unrelated.
- `2026-04-15-profile-post-hotpath-baseline-on-production-wan.md` — performance profiling; unrelated.
- `2026-04-17-24h-soak-checkpoint-verification.md` — soak operations; unrelated.
- `2026-04-17-audit-autorate-flat-gauge-fire-on-change.md` — gauge emission audit (different metrics class); unrelated.
- `2026-04-17-cake-tin-skip-on-unchanged-consumer-audit.md` — CAKE tin metrics emission audit; unrelated.
- `2026-04-17-gitignore-codex-and-redirect-artifact.md` — repo hygiene; unrelated.
- `2026-04-17-ingestion-rate-tool.md` — tooling for measuring write rates; unrelated.
- `2026-04-17-investigate-steering-degraded-on-clean-restart.md` — steering ops; unrelated.
- `2026-04-17-monitor-flapping-peak-count-on-next-docsis-event.md` — DOCSIS event monitoring; unrelated.
- `2026-04-17-operator-summary-digest-permission-handling.md` — operator-summary CLI bug; unrelated.
- `2026-04-24-resolve-att-cake-primary-canary-after-phase-196.md` — VALN-05b deferred work; unrelated to OBS-02.
- `2026-04-28-add-silicom-bypass-nic-operational-tooling.md` — Silicom NIC ops tooling; unrelated.
- `2026-04-28-add-silicom-bypass-test-harness.md` — Silicom NIC test harness; unrelated.
- `2026-05-01-delete-archive-2026-04-17.md` — repo hygiene; unrelated.

</deferred>

---

*Phase: 199-obs-02-spec-impl-reconciliation*
*Context gathered: 2026-05-02*
