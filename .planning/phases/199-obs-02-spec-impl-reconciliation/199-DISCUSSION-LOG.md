# Phase 199: OBS-02 Spec/Impl Reconciliation - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-02
**Phase:** 199-obs-02-spec-impl-reconciliation
**Mode:** `--auto` (autonomous; recommended option selected per area)
**Areas discussed:** REQUIREMENTS.md verification approach, Doc home for absent-row semantics, Wording source-of-truth, Operator-query note placement, VERIFICATION.md form, Out-of-scope confirmation, Todo cross-reference

---

## REQUIREMENTS.md Verification Approach

| Option | Description | Selected |
|--------|-------------|----------|
| Re-amend OBS-02 wording | Edit OBS-02 row again to add or refine wording | |
| Verify pre-staged wording | Confirm staged amendment matches test-pinned implementation; record in VERIFICATION.md | ✓ |
| Skip verification | Treat OBS-02 row as already accepted by audit | |

**[auto] Selected:** "Verify pre-staged wording" (recommended). The OBS-02 row already contains the amended wording and the traceability table already credits Phase 199. Re-amending would re-open the wording; skipping verification leaves no artifact to point to. Verification is the closing artifact the audit expects.

---

## Doc Home for Absent-Row Semantics

| Option | Description | Selected |
|--------|-------------|----------|
| `docs/CONFIGURATION.md` | Roadmap-named candidate; YAML config schema doc | |
| `docs/SUBSYSTEMS.md` `## Health And Metrics` | Existing canonical home for `/health` payload-shape documentation | ✓ |
| `docs/RUNBOOK.md` | Operator-facing runbook; documents `/health` inspection commands | (operator-query note only) |

**[auto] Selected:** `docs/SUBSYSTEMS.md` for payload shape; `docs/RUNBOOK.md` for operator-query note. CONFIGURATION.md is the YAML schema doc and does not currently document `/health` — placing payload-shape notes there would create cross-doc drift. The roadmap explicitly allows "or wherever per-WAN `signal_arbitration` is documented" — exercising that flexibility for the doc that already owns this surface.

---

## Wording Source-of-Truth

| Option | Description | Selected |
|--------|-------------|----------|
| Paraphrase REQUIREMENTS.md OBS-02 | Re-word for operator audience | |
| Quote REQUIREMENTS.md OBS-02 verbatim | Reuse exact phrase; add inline reference back to spec | ✓ |

**[auto] Selected:** "Quote verbatim". Eliminates a third surface that could drift. Spec/doc lockstep is the entire point of this phase.

---

## Operator-Query Note Placement

| Option | Description | Selected |
|--------|-------------|----------|
| Top of RUNBOOK.md | Most prominent; prone to skim-skipping | |
| `/metrics/history` + `python3 -m wanctl.history` section | Adjacent to existing operator queries against the SQLite store | ✓ |
| Separate new heading | New `## Metrics Coverage` heading | |

**[auto] Selected:** Adjacent to existing `/metrics/history` and `wanctl.history` examples. Operators investigating coverage already land in this section during incident triage; co-locating the denominator guidance maximizes discovery.

---

## VERIFICATION.md Form

| Option | Description | Selected |
|--------|-------------|----------|
| Single docs-only-invariant check | Just `git diff --name-only -- src/wanctl/` | |
| Four-check artifact mirroring 198-VERIFICATION.md | Docs-only invariant + REQUIREMENTS.md anchors + doc-edit anchors + test-pin sanity | ✓ |
| Full re-audit re-running OBS-02 anchor scripts | Re-execute all v1.40 audit predicates against this branch | |

**[auto] Selected:** Four-check artifact. Mirrors the project's established VERIFICATION.md pattern (Phase 197/198), gives the audit a reproducible verdict, and keeps the artifact small (each check is one shell line). Full re-audit is overkill for a docs-only phase whose runtime invariants did not change.

---

## Out-of-Scope Confirmation

| Option | Description | Selected |
|--------|-------------|----------|
| Allow targeted Python touch-ups | Permit small-comment edits in `wan_controller.py` near anchor lines | |
| Lock zero Python source change | No `src/wanctl/` edits at all | ✓ |

**[auto] Selected:** Lock zero Python source change. Roadmap entry already locks this. Phase 199's invariant proof depends on it.

---

## Todo Cross-Reference

| Option | Description | Selected |
|--------|-------------|----------|
| Auto-fold all 16 matches >= 0.4 (literal rule) | Absorb every keyword-matched todo into Phase 199 scope | |
| Override: review and defer all (none topical) | List all matches under "Reviewed Todos (not folded)" with deferral reason | ✓ |

**[auto] Selected:** Override and defer all. All 16 matches scored 0.6 from generic keyword overlap on common terms (`wanctl`, `src`, `cycle`, `under`, `code`). None are about docs-only OBS-02 wording. Folding any would expand a tightly-scoped reconciliation phase into a runtime/perf grab bag.

---

## Claude's Discretion

- Exact heading or bullet shape inside `docs/SUBSYSTEMS.md` for the `signal_arbitration` field expansion (sub-bullet, subsection, or paragraph) — pick the form most consistent with surrounding doc style.
- Whether the RUNBOOK.md operator note attaches to the `curl /metrics/history` example, the `python3 -m wanctl.history` example, or as a `> Note:` callout — pick the form that minimizes the chance an operator misses it.
- Whether `199-VERIFICATION.md` adds an optional fifth check that runs the absent-row pytest — fine if it stays under 5 seconds; skip otherwise.
- Whether to add an optional one-line cross-link from `docs/CONFIGURATION.md` to SUBSYSTEMS.md — only if the repo already has a docs-cross-link convention.

## Deferred Ideas

- Sentinel emission for `wanctl_rtt_confidence` / `wanctl_cake_avg_delay_delta_us` — locked out by spec contract; out of charter for v1.40+.
- Reorganizing SUBSYSTEMS.md `## Health And Metrics` into a per-field reference table — future docs-quality phase.
- Cross-link from CONFIGURATION.md to SUBSYSTEMS.md — Claude's discretion only if convention exists; otherwise future docs-organization phase.
- A live `make audit-traceability` hook to re-run OBS-02 anchor checks on CI — future tooling phase.
- 16 keyword-matched todos — see CONTEXT.md `<deferred>` "Reviewed Todos" subsection for full list and per-todo deferral reasons.
