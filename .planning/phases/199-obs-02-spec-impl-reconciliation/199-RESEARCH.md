# Phase 199: OBS-02 Spec/Impl Reconciliation - Research

**Researched:** 2026-05-02
**Domain:** Documentation reconciliation (spec → operator docs lockstep)
**Confidence:** HIGH

## Summary

Phase 199 is a **docs-only gap-closure phase** for v1.40. The OBS-02 implementation is already shipped and test-pinned; the absent-row behavior (cold-start and invalid-snapshot cycles produce no SQLite row for `wanctl_rtt_confidence` / `wanctl_cake_avg_delay_delta_us` and emit `null` in `/health`) is intentional, the audit accepted it, and the REQUIREMENTS.md OBS-02 row has already been amended in the working tree to formally specify it. Phase 199's job is to verify the staged wording, propagate it verbatim into operator-facing docs at the two correct insertion points, and produce a four-check `199-VERIFICATION.md` that proves the docs-only invariant. Anchors named in CONTEXT.md by line number have shifted slightly at HEAD (verified by symbol/test-name search and reported below); no Python source change is required or permitted.

The roadmap-named candidate for the operator note (`docs/CONFIGURATION.md`) does **not** currently document `/health` — verified by grep. SUBSYSTEMS.md already owns `/health` payload-shape documentation in the `## Health And Metrics` section (lines 121–140) and is the correct home for the `signal_arbitration` field-shape note. RUNBOOK.md already documents both `/metrics/history` and `python3 -m wanctl.history` reader paths in a contiguous block (lines 349–365) and is the correct home for the `wanctl_arbitration_active_primary` per-cycle denominator note.

**Primary recommendation:** Treat the wording in REQUIREMENTS.md OBS-02 as the single source of truth, quote it verbatim in two targeted notes (one in SUBSYSTEMS.md `## Health And Metrics`, one in RUNBOOK.md adjacent to the `python3 -m wanctl.history` example), and emit `199-VERIFICATION.md` with the four mechanizable checks D-05 prescribes plus an optional fifth pytest check (the absent-row test runs in 0.4s — well under the 5s budget). Make no edits under `src/wanctl/`.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**D-01: REQUIREMENTS.md OBS-02 wording is already pre-staged.** The amended OBS-02 row in `.planning/REQUIREMENTS.md` already states absent-row semantics ("cold-start and invalid-snapshot cycles produce absent SQLite rows and `/health` nulls — no NaN, -1, or sentinel emission") and is annotated `*Wording amended in Phase 199 to formally specify absent-row semantics.*`. The traceability table also already shows `OBS-02 | Phase 193 + Phase 199 (wording amendment) | Complete (caveat resolved by Phase 199)`. Phase 199's task is to **verify** the staged wording matches the implementation contract and capture that verification in `199-VERIFICATION.md` — not to re-amend.

**D-02: Add the `signal_arbitration` payload-shape note to `docs/SUBSYSTEMS.md`.** SUBSYSTEMS.md already owns the `/health` "Major response sections" enumeration (lines 128–138). Add a short subsection or bullet expansion under the `wans[]` row that names the four `signal_arbitration` fields (`active_primary_signal`, `rtt_confidence`, `cake_av_delay_delta_us`, `control_decision_reason`), documents nullability of the two numeric fields, and points to the metrics-store absent-row note in RUNBOOK.md.

**D-03: Add the operator-query note to `docs/RUNBOOK.md` in the SQLite/metrics-history section.** RUNBOOK.md already documents `/metrics/history` queries and `python3 -m wanctl.history` invocations (lines ~340–365). The note states: `wanctl_arbitration_active_primary` is the always-emitted per-cycle row and is the reliable denominator for any coverage query against the per-WAN metrics SQLite store; `wanctl_rtt_confidence` and `wanctl_cake_avg_delay_delta_us` are emitted only when valid, so absent rows for those metrics represent cold-start or invalid-snapshot cycles, not data loss.

**D-04: Quote REQUIREMENTS.md OBS-02 verbatim in the operator note.** Reuse the exact phrase from REQUIREMENTS.md OBS-02: "cold-start and invalid-snapshot cycles produce absent SQLite rows and `/health` nulls — no NaN, -1, or sentinel emission." Add a short inline reference back to REQUIREMENTS.md OBS-02 so future readers can trace the contract source.

**D-05: `199-VERIFICATION.md` records four invariant checks.** Pattern follows `198-VERIFICATION.md` (YAML frontmatter + body). Required checks:
1. **Docs-only invariant:** `git diff --name-only <phase-base>..HEAD -- src/wanctl/` returns empty.
2. **REQUIREMENTS.md OBS-02 wording:** the OBS-02 row contains the four anchor phrases (`absent SQLite rows`, `cold-start`, `invalid-snapshot`, `wanctl_arbitration_active_primary`) and the Phase 199 annotation.
3. **Doc edits exist:** `docs/SUBSYSTEMS.md` mentions `signal_arbitration` and the four field names; `docs/RUNBOOK.md` mentions `wanctl_arbitration_active_primary` as the per-cycle denominator.
4. **Test-pin sanity:** the absent-row test still encodes the absent-row behavior the spec describes (locate by test-name search, not exact line).

**D-06: Verification frontmatter records phase scope as `docs-only` and lists the three changed/verified files.** YAML frontmatter mirrors `198-VERIFICATION.md` shape: `phase`, `verified`, `status`, `score`, `requirements: [OBS-02]`, plus a `phase_scope: docs-only` field and a `files_touched: [.planning/REQUIREMENTS.md, docs/SUBSYSTEMS.md, docs/RUNBOOK.md]` list.

**D-07: No Python behavior change.** No new metric, no new field, no new emission gate, no sentinel substitution, no `signal_arbitration` schema change. The CHANGELOG.md / control-flow code paths in `wan_controller.py` and `health_check.py` are not edited.

**D-08: Do not re-document `/health` from scratch.** Phase 199 adds short, targeted notes; it does not reorganize SUBSYSTEMS.md or RUNBOOK.md.

### Claude's Discretion

- Exact heading or bullet shape inside `docs/SUBSYSTEMS.md` for the `signal_arbitration` field expansion (sub-bullet, subsection, or paragraph) — pick the form most consistent with surrounding doc style.
- Whether the RUNBOOK.md operator note attaches to the `curl /metrics/history` example, the `python3 -m wanctl.history` example, or as a `> Note:` callout — pick the form that minimizes the chance an operator misses it.
- Whether `199-VERIFICATION.md` adds an optional fifth check that runs the absent-row pytest — fine if it stays under 5 seconds; skip otherwise. (See **Pitfall 3 / Test pin runtime** below — measured at 0.4s; safe to include.)
- Whether to add an optional one-line cross-link from `docs/CONFIGURATION.md` to SUBSYSTEMS.md — only if the repo already has a docs-cross-link convention. (See **Pitfall 4 / Cross-link convention** below — convention does not currently exist; skip.)

### Deferred Ideas (OUT OF SCOPE)

- **Sentinel emission (NaN or -1) for `wanctl_rtt_confidence` / `wanctl_cake_avg_delay_delta_us`.** Rejected by the roadmap as a violation of the documented `[0.0, 1.0]` contract for `rtt_confidence` and as Prometheus-aggregate-skewing.
- **Reorganizing `docs/SUBSYSTEMS.md` `## Health And Metrics` into a per-field reference table.** Future docs-quality phase.
- **Cross-link from CONFIGURATION.md to SUBSYSTEMS.md** — Claude's discretion only if convention exists; otherwise future docs-organization phase.
- **A live `make audit-traceability` hook** to re-run OBS-02 anchor checks on CI — future tooling phase.
- 16 keyword-matched todos already reviewed and explicitly not folded (see CONTEXT.md `<deferred>`).
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| OBS-02 | Per-cycle numeric metrics are written to the per-WAN metrics SQLite store when defined for that cycle. `wanctl_arbitration_active_primary` (0=none, 1=queue, 2=rtt) is emitted for each CAKE-metrics-enabled cycle and serves as the reliable per-cycle denominator for coverage queries. `wanctl_rtt_confidence` and `wanctl_cake_avg_delay_delta_us` are emitted only when valid; cold-start and invalid-snapshot cycles produce absent SQLite rows and `/health` nulls — no NaN, -1, or sentinel emission. | Verified at three test-pinned anchors (see **Architectural Responsibility Map** + **Code Anchor Table**). REQUIREMENTS.md row already amended at line 27. Traceability table line 122 already credits Phase 199. Source enforces field nullability at `wan_controller.py:4222–4239`. |
</phase_requirements>

## Architectural Responsibility Map

This phase touches three documentation surfaces only. Tier mapping is in service of "where does each fact belong?", not "where does code run?".

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| OBS-02 spec contract | `.planning/REQUIREMENTS.md` (machine-checkable spec) | — | Single source of truth. Already amended; Phase 199 verifies. |
| `/health` payload-shape documentation | `docs/SUBSYSTEMS.md` `## Health And Metrics` | — | Owns the `wans[]` Major Response Sections enumeration today. CONFIGURATION.md does **not** document `/health` (verified by grep). |
| Operator SQLite-coverage guidance | `docs/RUNBOOK.md` `/metrics/history` + `wanctl.history` block (lines 349–365) | — | Operators investigating coverage already land here during incident triage. |
| `signal_arbitration` payload (Python contract) | `src/wanctl/wan_controller.py:4222` (`get_health_data` block) | `src/wanctl/wan_controller.py:3083–3097` (SQLite emission gate) | **Read-only for this phase.** Anchors verified — do not edit. |
| Absent-row behavior (test pin) | `tests/test_wan_controller.py:2654` (`test_phase195_metrics_skip_rtt_confidence_when_none`) | — | **Read-only for this phase.** Locks the spec wording. |

## Standard Stack

This is a docs-only phase. No new tooling. The only "stack" is the existing Markdown convention in `docs/`, the YAML frontmatter convention from `198-VERIFICATION.md`, and the existing pytest suite for the test-pin sanity check.

### Core
| Tool | Version | Purpose | Why Standard |
|------|---------|---------|--------------|
| `.venv/bin/pytest` | 9.0.2 | Optional fifth verification check (absent-row test) | [VERIFIED: `.venv/bin/pytest --version`] Already the project test runner. |
| `git diff --name-only` | system | Docs-only invariant check | Standard, scriptable, audit-replayable. |
| `grep -F` | system | REQUIREMENTS.md anchor-phrase check | One-line, deterministic. |
| `jq` | 1.7+ | (Optional) parse VERIFICATION.md frontmatter for machine audits | [VERIFIED: `command -v jq` returns `/usr/bin/jq`] Used by Phase 198 verification scripts. |

### Supporting
None. No new libraries, no new files outside the three already named.

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Verbatim quote of REQUIREMENTS.md OBS-02 | Operator-friendly paraphrase | Locked out by D-04 (paraphrase creates a third surface that drifts independently). |
| SUBSYSTEMS.md as the field-shape home | CONFIGURATION.md (roadmap-named candidate) | CONFIGURATION.md does not currently document `/health` — verified. Putting payload shape there creates new doc-organization drift. |
| Four-check VERIFICATION.md | Single docs-only invariant check | Insufficient: the spec → impl → doc lockstep claim needs all three surfaces independently asserted. |

**Installation:** None required.

**Version verification:** `pytest 9.0.2` confirmed at HEAD against `.venv/bin/pytest --version`. `jq 1.7` confirmed via `/usr/bin/jq`. Both are environmental, not vendored.

## Architecture Patterns

### System Architecture Diagram (data-flow for OBS-02 contract)

```
┌─────────────────────────────────────────────────────────────────────┐
│                     OBS-02 Contract Surface                         │
│                                                                     │
│  REQUIREMENTS.md OBS-02 row  ◄──── single source of truth (spec)    │
│         │                                                           │
│         │ verbatim quote                                            │
│         ├────────────────────► docs/SUBSYSTEMS.md (payload shape)   │
│         │                       │ "wans[].signal_arbitration"       │
│         │                       │ field nullability note            │
│         │                                                           │
│         └────────────────────► docs/RUNBOOK.md (operator guidance)  │
│                                 │ "denominator = active_primary"    │
│                                 │ absent-row semantics for triage   │
│                                                                     │
│  Implementation (READ-ONLY this phase):                             │
│    wan_controller.py:4222  get_health_data() emits null fields ────┐│
│    wan_controller.py:3097  _append_rtt_confidence_metric() gate   ─┤│
│    wan_controller.py:3092  always-emit active_primary metric  ────┘│
│    test_wan_controller.py:2654  test_phase195_metrics_skip_*  ◄─── │
│                                                                    │
│  Verification artifact:                                            │
│    .planning/phases/199-.../199-VERIFICATION.md                    │
│        Check 1: git diff --name-only -- src/wanctl/ → empty        │
│        Check 2: grep anchor phrases in REQUIREMENTS.md             │
│        Check 3: grep field names + denominator in SUBSYSTEMS / RUN │
│        Check 4: pytest -k "skip_rtt_confidence_when_none" passes   │
└─────────────────────────────────────────────────────────────────────┘
```

A reader following the arrows can trace: spec line in REQUIREMENTS.md → quoted text in two operator docs → audit-replayable greps in VERIFICATION.md → pinned implementation behavior in source/test. No box on the diagram represents a Python code change.

### Recommended Project Structure (no new files)

```
.planning/
├── REQUIREMENTS.md                                  # already amended, verify only
├── ROADMAP.md                                       # Phase 199 entry (line 364) — read only
└── phases/199-obs-02-spec-impl-reconciliation/
    ├── 199-CONTEXT.md                               # exists
    ├── 199-DISCUSSION-LOG.md                        # exists
    ├── 199-RESEARCH.md                              # this file
    ├── 199-PLAN.md (or N×PLAN.md)                   # written by planner
    └── 199-VERIFICATION.md                          # written at phase close

docs/
├── SUBSYSTEMS.md                                    # one targeted note (D-02)
├── RUNBOOK.md                                       # one targeted note (D-03)
└── CONFIGURATION.md                                 # untouched (D-08 sub-bullet)
```

### Pattern 1: Verbatim spec quote with inline back-reference
**What:** Each operator-doc note quotes REQUIREMENTS.md OBS-02 in a fenced quote block (or inline blockquote) and includes a parenthetical back-reference like `(see REQUIREMENTS.md OBS-02)`.
**When to use:** Whenever an operator doc restates a contract phrase — in this phase, both notes.
**Example skeleton (final wording is the planner's call):**

```markdown
> `rtt_confidence` and `cake_av_delay_delta_us` may be `null`.
> Per REQUIREMENTS.md OBS-02: cold-start and invalid-snapshot cycles
> produce absent SQLite rows and `/health` nulls — no NaN, -1, or
> sentinel emission. Use `wanctl_arbitration_active_primary` as the
> per-cycle denominator for SQLite coverage queries.
```

### Pattern 2: Four-check `VERIFICATION.md` mirroring Phase 198 frontmatter

**What:** YAML frontmatter (`phase`, `verified`, `status`, `score`, `requirements`) plus the two Phase-199-specific keys `phase_scope: docs-only` and `files_touched: [...]`, then a body that records the four checks plus a Goal Achievement table mirroring Phase 198.
**When to use:** Phase close.
**Example (frontmatter shape):**

```yaml
---
phase: 199-obs-02-spec-impl-reconciliation
verified: 2026-05-XXTHH:MM:SSZ
status: passed
score: 4/4 must-haves verified
requirements: [OBS-02]
phase_scope: docs-only
files_touched:
  - .planning/REQUIREMENTS.md
  - docs/SUBSYSTEMS.md
  - docs/RUNBOOK.md
---
```

### Anti-Patterns to Avoid

- **Paraphrasing OBS-02 wording in operator docs.** Creates a third drifting surface; locked out by D-04.
- **Editing any file under `src/wanctl/`.** Locked out by D-07. The first VERIFICATION.md check explicitly fails on any such edit.
- **Reorganizing `## Health And Metrics` into a per-field table.** Inflates the diff and masks the targeted note (D-08, deferred).
- **Adding `signal_arbitration` doc fields beyond the four enumerated in OBS-01.** A fifth field, `refractory_active`, is also emitted by `get_health_data()` (verified at `wan_controller.py:4236`) but is **not** part of OBS-01's contract enumeration. Document only the four named in REQUIREMENTS.md OBS-01: `active_primary_signal`, `rtt_confidence`, `cake_av_delay_delta_us`, `control_decision_reason`. Mentioning `refractory_active` would expand the spec under cover of a docs phase.
- **Bumping CHANGELOG.md.** No code or behavior change; a CHANGELOG entry would mislead readers into expecting one. (If repo convention requires a `docs:` CHANGELOG entry for documentation-only changes, defer to project-finalizer at commit time.)

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Spec/doc drift detection | A custom traceability checker | Plain `grep -F` of anchor phrases inside `199-VERIFICATION.md` | One-line, audit-replayable, zero dependency. The audit framework reads VERIFICATION.md frontmatter directly. |
| Docs-only invariant proof | A custom file-mode checker | `git diff --name-only <base>..HEAD -- src/wanctl/` returns empty | Single git invocation, deterministic, identical to Phase 198 SAFE-05 pattern. |
| VERIFICATION.md scaffolding | A new doc structure | Copy `198-VERIFICATION.md` frontmatter and body skeleton, swap requirements + scope keys | Project precedent already exists; deviating creates auditor friction. |

**Key insight:** The spec → impl → doc lockstep contract is verified by **trivial shell commands**. Any custom tooling for this phase would itself need verification, defeating the point.

## Runtime State Inventory

> Required because Phase 199 propagates a contract phrase across multiple doc surfaces — a "rename of language" rather than a code rename, but the same drift-class question applies.

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | None — verified by inspection. The only stored-state references to OBS-02 wording are in markdown files inside the repo (REQUIREMENTS.md, ROADMAP.md, phase contexts). No database stores OBS-02 wording. | None |
| Live service config | None — verified by absence of `/health` documentation in CONFIGURATION.md (grep confirmed). No live service configuration carries OBS-02 wording. | None |
| OS-registered state | None — `wanctl@<wan>.service` and `steering.service` units in `deploy/systemd/` do not embed OBS-02 wording. | None |
| Secrets/env vars | None — no env vars or secrets carry OBS-02 wording. | None |
| Build artifacts | None — `.venv/`, `*.egg-info/`, and any compiled artifacts do not carry doc text. | None |
| **Doc surfaces (additional category for this phase)** | `.planning/REQUIREMENTS.md` (already amended at line 27); `.planning/ROADMAP.md` lines 364–386 (Phase 199 entry; describes the propagation work but is not the operator surface — leave unchanged); `docs/SUBSYSTEMS.md` lines 121–138 (target #1 — needs note added); `docs/RUNBOOK.md` lines 339–365 (target #2 — needs note added); `docs/CONFIGURATION.md` (does NOT document `/health` — leave untouched per D-08). | One targeted note per target file, verbatim quote per D-04. |
| **Phase audit/state files (additional)** | `.planning/STATE.md` line 6 records `stopped_at: Phase 199 context gathered`; `.planning/MILESTONES.md`, `.planning/v1.40-MILESTONE-AUDIT.md` reference OBS-02 caveat. These are normally updated by the GSD workflow at phase close — do not pre-edit. | Workflow-driven only; not a Phase 199 plan task. |

**Canonical question check:** *After every doc edit lands, what runtime systems still have outdated OBS-02 wording?* Answer: **none**. The OBS-02 wording lives only in markdown files inside this repo; there is no runtime system, no secrets store, no service config, and no build artifact that caches it.

## Common Pitfalls

### Pitfall 1: Line-number drift between CONTEXT.md and HEAD
**What goes wrong:** CONTEXT.md cites `wan_controller.py:2785`, `wan_controller.py:3142`, and `tests/test_wan_controller.py:2629`. At HEAD (commit `41f96e6`, branch `main`), the actual canonical anchors are at different lines.
**Why it happens:** The CONTEXT.md was written before the most recent commits; line numbers shift with edits even when symbols are unchanged.
**How to avoid:** Always locate by symbol or test name, never by line number. Confirmed mappings (verified at HEAD):

| CONTEXT.md anchor | Canonical anchor at HEAD | Verified |
|-------------------|--------------------------|----------|
| `wan_controller.py:2785` ("`_select_dl_primary_scalar_ms()` reads `_last_rtt_confidence` directly in-process") | `wan_controller.py:2683` (def) and **line 2724** (`confidence = self._last_rtt_confidence` inside `_select_dl_primary_scalar_ms`) | grep `_select_dl_primary_scalar_ms` |
| `wan_controller.py:3142` ("SQLite emission gate") | `wan_controller.py:3097` (`self._append_rtt_confidence_metric(metrics_batch, ts)`) — gate body is at lines **3148–3159** in `_append_rtt_confidence_metric` (the `if self._last_rtt_confidence is not None:` guard at 3149 is the actual emission gate) | grep `_append_rtt_confidence_metric` |
| Always-emit denominator (not in CONTEXT line citations) | `wan_controller.py:3091–3093` (unconditional append of `wanctl_arbitration_active_primary` inside the cake-metrics-enabled branch) | grep `wanctl_arbitration_active_primary` |
| `tests/test_wan_controller.py:2629` ("absent-row test pin") | `tests/test_wan_controller.py:2654` (`def test_phase195_metrics_skip_rtt_confidence_when_none`) and assertion at line **2678** (`assert ("wanctl_rtt_confidence", dl_key) not in metrics`) | grep test name |
| `signal_arbitration` payload shape (not in CONTEXT line citations) | `wan_controller.py:4222–4239` (`get_health_data` returns the four contract fields plus an out-of-OBS-01-scope `refractory_active`) | grep `signal_arbitration` |

**Warning signs:** Plan tasks that cite line numbers verbatim from CONTEXT.md will not match HEAD. Verification scripts must use symbol/test-name lookup or risk false negatives.

### Pitfall 2: CONFIGURATION.md as the doc home (roadmap-named candidate)
**What goes wrong:** ROADMAP.md line 374 names `docs/CONFIGURATION.md` as the candidate doc home ("update `/health` documentation in `docs/CONFIGURATION.md` (or wherever per-WAN `signal_arbitration` is documented)").
**Why it happens:** The roadmap was written before checking which doc actually documents `/health`.
**How to avoid:** **Verified by grep** — `grep -n "signal_arbitration\|/health\|wans\|rtt_confidence" docs/CONFIGURATION.md` returns **zero matches**. CONFIGURATION.md is the YAML config schema doc; it does not document `/health` at all. Putting a payload-shape note there would create a new doc-organization surface that does not exist today. SUBSYSTEMS.md is the correct home (D-02). The roadmap's "or wherever" clause exists precisely to allow this substitution; document the choice in `199-VERIFICATION.md`'s body so future readers see why CONFIGURATION.md was bypassed.
**Warning signs:** A planner task that says "edit CONFIGURATION.md" — block at plan-check.

### Pitfall 3: Test pin runtime budget for the optional fifth verification check
**What goes wrong:** D-05 allows an optional fifth check that runs the absent-row pytest, but only "if it stays under 5 seconds". If the test requires the full controller fixture stack, it would blow the budget and force skipping.
**Why it happens:** Some tests in `tests/test_wan_controller.py` use heavyweight fixtures (controller construction, mocked router, SQLite writer mocks).
**How to avoid:** **Verified by direct measurement.** Running `.venv/bin/pytest -o addopts='' tests/test_wan_controller.py -k "skip_rtt_confidence_when_none" -q` completes in **0.40 seconds** with `1 passed, 202 deselected`. The fifth check is well under the 5s budget; **include it**. The exact command for VERIFICATION.md:

```bash
.venv/bin/pytest -o addopts='' tests/test_wan_controller.py -k "skip_rtt_confidence_when_none" -q
```

**Warning signs:** A planner that defaults to skipping the optional check despite a measured budget — push back; the data is in this research file.

### Pitfall 4: Cross-link convention check (Claude's discretion item)
**What goes wrong:** A CONFIGURATION.md → SUBSYSTEMS.md cross-link is conditioned on "if there is already a docs-cross-link convention established in the repo". Adding the link without a convention introduces a new convention under cover of a docs-only reconciliation phase.
**Why it happens:** Operator-doc improvements feel like wins; the planner may add the link without checking.
**How to avoid:** Search `docs/*.md` for existing inline cross-links of the form `[other-doc](OTHER.md)` or `see SUBSYSTEMS.md`. There **are** plenty of inline cross-references in RUNBOOK.md and SUBSYSTEMS.md (e.g., RUNBOOK.md line 422 references DEPLOYMENT.md), but **CONFIGURATION.md itself** has no `/health`-related context that would naturally host a forward link. **Recommendation:** skip the optional cross-link. The condition "convention exists" is technically true repo-wide but not in the right context inside CONFIGURATION.md. Adding a link to a doc that does not discuss `/health` is more confusing than helpful.
**Warning signs:** Plan task that adds a cross-link to CONFIGURATION.md without specifying the surrounding context where it lands — flag.

### Pitfall 5: Adding `refractory_active` to the field-shape note in SUBSYSTEMS.md
**What goes wrong:** The actual `get_health_data()` payload at `wan_controller.py:4222–4239` emits **five** fields under `signal_arbitration`: the four named in OBS-01 plus `refractory_active` (boolean). A planner reading source could be tempted to document all five.
**Why it happens:** Source is the most authoritative-feeling reference.
**How to avoid:** OBS-01 (REQUIREMENTS.md line 26) **enumerates four fields** as the contract: `active_primary_signal`, `rtt_confidence` (float 0.0–1.0 or null), `cake_av_delay_delta_us` (int or null), `control_decision_reason`. `refractory_active` is implementation telemetry from Phase 197, not part of the OBS-01 contract. Documenting it in SUBSYSTEMS.md would silently expand the contract surface — out of scope for Phase 199. If `refractory_active` deserves spec/doc treatment, it belongs in a separate phase that amends OBS-01.
**Warning signs:** Plan task wording that says "all `signal_arbitration` fields" without enumerating — push back; specify the four.

### Pitfall 6: REQUIREMENTS.md OBS-02 already amended — re-amending re-opens the wording
**What goes wrong:** A planner who treats Phase 199 as a "wording amendment" task may re-edit OBS-02 to "improve" the staged wording. Re-editing reopens the audit's already-accepted wording.
**Why it happens:** The phase name says "spec/impl reconciliation"; "edit the spec" is the obvious reading.
**How to avoid:** REQUIREMENTS.md OBS-02 **was amended in commit `2e0211f`** (verified by `git log` showing `2e0211f docs(phase-199): capture phase context` as the most recent context-bearing commit before 199-CONTEXT.md was finalized). The amendment text already includes the four anchor phrases (`absent SQLite rows`, `cold-start`, `invalid-snapshot`, `wanctl_arbitration_active_primary`) and the `*Wording amended in Phase 199 to formally specify absent-row semantics.*` annotation. The traceability table line 122 already credits Phase 199. Phase 199's task on REQUIREMENTS.md is **verify-only** — VERIFICATION.md check 2 greps for the four anchor phrases, that's it.
**Warning signs:** Plan task that includes "edit REQUIREMENTS.md" — block; should read "verify REQUIREMENTS.md."

## Code Examples

Exact-text patterns from official sources, ready for the planner.

### Example 1: REQUIREMENTS.md OBS-02 verbatim quote (the wording every doc edit must reuse)

```
Source: .planning/REQUIREMENTS.md:27 (verified at HEAD)

Per-cycle numeric metrics are written to the per-WAN metrics SQLite store
when defined for that cycle. wanctl_arbitration_active_primary (0=none,
1=queue, 2=rtt) is emitted for each CAKE-metrics-enabled cycle and serves
as the reliable per-cycle denominator for coverage queries.
wanctl_rtt_confidence and wanctl_cake_avg_delay_delta_us are emitted only
when valid; cold-start and invalid-snapshot cycles produce absent SQLite
rows and /health nulls — no NaN, -1, or sentinel emission. All emitted
values are numeric and compatible with the existing Prometheus-style
exporter schema.
```

### Example 2: SUBSYSTEMS.md current "Major response sections" enumeration (insertion target)

```
Source: docs/SUBSYSTEMS.md:130–138 (verified at HEAD)

Major response sections:

- `wans[]`: per-WAN rate, state, hysteresis, RTT, connectivity,
  measurement, IRTT, reflector, fusion, CAKE, tuning, storage, and
  runtime status.
- `alerting`: alert engine enabled state, fired count, and active
  cooldowns.
- `disk_space`: free/total bytes and warning state for /var/lib/wanctl.
- `summary`: compact operator-facing status rows.
- `storage` and `runtime`: bounded pressure status for SQLite and
  process memory.
```

The `signal_arbitration` block is currently subsumed under the catch-all "hysteresis" / "CAKE" / "tuning" descriptors in the `wans[]` row and is not separately enumerated. Insertion target: a sub-bullet (or a short `### Per-WAN signal arbitration` subsection) immediately after the `wans[]` line, describing the four contract fields and the nullability of the two numeric fields.

### Example 3: RUNBOOK.md current `/metrics/history` reader block (insertion target)

```
Source: docs/RUNBOOK.md:349–365 (verified at HEAD)

For retained history, use the supported readers instead of guessing a
single DB path:

```bash
ssh <host> 'sudo -n env PYTHONPATH=/opt python3 -m wanctl.history --last 1h --metrics wanctl_rtt_ms --json | python3 -m json.tool | head -n 40'
ssh <host> 'curl -s "http://<health-ip>:9101/metrics/history?range=1h&limit=5" | python3 -m json.tool'
```

On the current production hosts:

- `/metrics/history` is the endpoint-local HTTP history view for the
  connected autorate daemon.
- `python3 -m wanctl.history` is the authoritative merged cross-WAN
  proof path.
```

Insertion target: a `> Note:` callout immediately after this block (or after the second bullet), naming `wanctl_arbitration_active_primary` as the per-cycle denominator and quoting the OBS-02 absent-row sentence.

### Example 4: Implementation anchor — SQLite emission gate (READ-ONLY)

```python
# Source: src/wanctl/wan_controller.py:3091–3097 (verified at HEAD)
metrics_batch.extend([
    (ts, self.wan_name, "wanctl_arbitration_active_primary",
     float(ARBITRATION_PRIMARY_ENCODING[active_primary]), self._download_labels, "raw"),
    (ts, self.wan_name, "wanctl_arbitration_refractory_active",
     1.0 if refractory_active else 0.0, self._download_labels, "raw"),
])
self._append_rtt_confidence_metric(metrics_batch, ts)
```

```python
# Source: src/wanctl/wan_controller.py:3148–3159 (verified at HEAD)
def _append_rtt_confidence_metric(self, metrics_batch: list, ts: int) -> None:
    if self._last_rtt_confidence is not None:
        metrics_batch.append(
            (
                ts,
                self.wan_name,
                "wanctl_rtt_confidence",
                float(self._last_rtt_confidence),
                self._download_labels,
                "raw",
            )
        )
```

This is the absent-row gate: when `_last_rtt_confidence is None`, no row is appended, no NaN/-1 is substituted. The text "no NaN, -1, or sentinel emission" in REQUIREMENTS.md OBS-02 is true at HEAD.

### Example 5: Implementation anchor — `/health` payload nullability (READ-ONLY)

```python
# Source: src/wanctl/wan_controller.py:4222–4239 (verified at HEAD)
"signal_arbitration": {
    "active_primary_signal": getattr(self, "_last_arbitration_primary", "rtt"),
    "rtt_confidence": getattr(self, "_last_rtt_confidence", None),
    "control_decision_reason": getattr(
        self,
        "_last_arbitration_reason",
        ARBITRATION_REASON_RTT_PRIMARY_NORMAL,
    ),
    "cake_av_delay_delta_us": (
        int(self._dl_cake_snapshot.max_delay_delta_us)
        if self._dl_cake_snapshot is not None
        and not self._dl_cake_snapshot.cold_start
        else None
    ),
    "refractory_active": getattr(
        self, "_dl_arbitration_used_refractory_snapshot", False
    ),
},
```

`rtt_confidence` is `None` whenever `_last_rtt_confidence is None`. `cake_av_delay_delta_us` is `None` whenever the DL CAKE snapshot is absent or cold-start. The `null` in `/health` is direct, not sentinel-substituted.

### Example 6: Test pin (READ-ONLY)

```python
# Source: tests/test_wan_controller.py:2654–2678 (verified at HEAD; passes in 0.40s)
def test_phase195_metrics_skip_rtt_confidence_when_none(self, controller):
    controller._dl_cake_snapshot = self._make_snapshot(
        cold_start=False, max_delay_delta_us=20000
    )
    controller._ul_cake_snapshot = None
    controller._last_rtt_confidence = None

    with patch("wanctl.wan_controller.time.time", return_value=1234):
        controller._run_logging_metrics(
            measured_rtt=25.0,
            fused_rtt=25.0,
            dl_zone="GREEN",
            ul_zone="GREEN",
            dl_rate=100_000_000,
            ul_rate=20_000_000,
            delta=5.0,
            dl_transition_reason=None,
            ul_transition_reason=None,
            irtt_result=None,
        )

    batch = controller._metrics_writer.write_metrics_batch.call_args.args[0]
    metrics = self._metrics_by_name(batch)
    dl_key = (("direction", "download"),)
    assert ("wanctl_rtt_confidence", dl_key) not in metrics
```

This is the absent-row test pin. Verification check 4 locates this test by name, not by line number.

### Code Anchor Table (single-source-of-truth for the planner)

| CONTEXT.md citation | HEAD location (symbol-resolved) | Used by |
|---------------------|--------------------------------|---------|
| `_select_dl_primary_scalar_ms()` reads `_last_rtt_confidence` (CONTEXT line 2785) | `wan_controller.py:2683` (def) → `wan_controller.py:2724` (`confidence = self._last_rtt_confidence`) | OBS-02 spec rationale ("in-process consumer doesn't need a SQLite row") |
| SQLite emission gate (CONTEXT line 3142) | `wan_controller.py:3148` (`def _append_rtt_confidence_metric`) → guard at `wan_controller.py:3149` | OBS-02 absent-row contract |
| Always-emit denominator (no CONTEXT line) | `wan_controller.py:3091–3093` | OBS-02 denominator claim |
| `signal_arbitration` payload shape (no CONTEXT line) | `wan_controller.py:4222–4239` | OBS-01 contract enumeration; SUBSYSTEMS.md note basis |
| Absent-row test pin (CONTEXT line 2629) | `tests/test_wan_controller.py:2654` (`test_phase195_metrics_skip_rtt_confidence_when_none`) | VERIFICATION.md check 4 |

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| OBS-02 contract silent on absent-row semantics | OBS-02 explicitly specifies absent-row + `/health` null behavior | REQUIREMENTS.md amendment pre-staged in commit `2e0211f` (2026-05-02) | Spec now matches the test-pinned implementation; Phase 199 propagates to operator docs. |
| `wanctl_arbitration_active_primary` denominator role implied by audit scripts | Denominator role explicitly named in operator docs | Phase 199 (this) | Operators investigating coverage have a documented anchor instead of folklore. |

**Deprecated/outdated:** Nothing. Phase 199 is additive documentation only.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Project does not have a documented "docs CHANGELOG" convention requiring a CHANGELOG.md entry for documentation-only changes. | Anti-Patterns | Low. project-finalizer is the gate at commit time; if convention does require an entry, it will be added then. Phase 199 plan does not need to mandate it. |
| A2 | The optional cross-link from CONFIGURATION.md to SUBSYSTEMS.md is best skipped because CONFIGURATION.md has no surrounding `/health` context. | Pitfall 4 | Low. If a future docs-organization phase wants the link, it can add it with proper surrounding context. |
| A3 | The fifth verification check (pytest absent-row test) should be included because measured runtime is 0.4s. | Pitfall 3 | None — measurement is empirical, repeated on this machine; risk only if CI machine is dramatically slower (~10x), still under budget. |

**If this table is empty:** all claims were verified or cited. (It is not empty; A1–A3 are flagged for the planner.)

## Open Questions

1. **Exact insertion form in SUBSYSTEMS.md (sub-bullet vs. subsection).**
   - What we know: D-02 + Claude's discretion item give freedom; surrounding `## Health And Metrics` uses a flat bullet list under "Major response sections".
   - What's unclear: Whether a new `### Per-WAN signal arbitration` subsection (one heading down from `## Health And Metrics`) is more readable than a sub-bullet expansion of the existing `wans[]` row.
   - Recommendation: Sub-bullet expansion of the `wans[]` row; preserves the section's existing rhythm and avoids inflating the diff with new heading TOC entries. Planner can override.

2. **Whether RUNBOOK.md note attaches to the curl example, the `wanctl.history` example, or as a `> Note:` callout.**
   - What we know: D-03 + Claude's discretion item give freedom; both readers are documented in the same block (lines 349–365).
   - What's unclear: Operator skim behavior — which placement gets the most eyeballs during incident triage.
   - Recommendation: `> Note:` callout immediately after the "endpoint-local vs. merged cross-WAN" paragraph (after line 365). A blockquote callout is visually distinct, gets noticed even when the operator is scanning for a curl invocation, and does not interrupt the example chain.

3. **Whether `199-VERIFICATION.md` needs a Goal Achievement / Observable Truths table mirroring Phase 198, or a slimmer body.**
   - What we know: Phase 198's body has Observable Truths, Required Artifacts, Key Link Verification, Data-Flow Trace, Behavioral Spot-Checks, Requirements Coverage. Most of these don't apply to a docs-only phase.
   - What's unclear: How much body structure the auditor expects.
   - Recommendation: Mirror frontmatter fully (per D-06); use a lightweight body with three sections — "Observable Truths" (the four checks), "Files Touched" (with diff stats), and "Spec Lockstep" (the REQUIREMENTS.md ↔ SUBSYSTEMS.md ↔ RUNBOOK.md mapping). Skip Required Artifacts, Data-Flow Trace, Cascade Closure — those exist for Phase 198's complex evidence chain and would be empty noise here.

## Environment Availability

> Phase has minimal external dependencies (markdown editing, git, pytest). Audit included for completeness.

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| `git` | VERIFICATION.md check 1 (docs-only invariant) | ✓ | system | — |
| `grep` (POSIX) | VERIFICATION.md checks 2 + 3 | ✓ | system | — |
| `.venv/bin/pytest` | Optional VERIFICATION.md check 5 | ✓ | 9.0.2 | Skip check 5 if venv broken |
| `jq` | (Optional) VERIFICATION.md frontmatter parsing | ✓ | system (`/usr/bin/jq`) | Use `python3 -c "import yaml; ..."` |
| `python3` | VERIFICATION.md check 5 (via pytest) and any frontmatter scripts | ✓ | system | — |

**Missing dependencies with no fallback:** None.
**Missing dependencies with fallback:** None.

## Validation Architecture

> Required because `workflow.nyquist_validation: true` in `.planning/config.json` (verified). For a docs-only phase, "Nyquist sampling" maps to: every doc edit has at least one mechanizable check that re-runs in seconds.

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 9.0.2 (verified via `.venv/bin/pytest --version`) |
| Config file | `pyproject.toml` (`[tool.pytest.ini_options]`); `tests/conftest.py` |
| Quick run command | `.venv/bin/pytest -o addopts='' tests/test_wan_controller.py -k "skip_rtt_confidence_when_none" -q` (0.40s, verified) |
| Full suite command | `.venv/bin/pytest tests/ -v` (full project suite — not required for a docs-only phase) |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| OBS-02 | Cold-start / `_last_rtt_confidence is None` cycles emit no `wanctl_rtt_confidence` row. | unit (test pin) | `.venv/bin/pytest -o addopts='' tests/test_wan_controller.py -k "skip_rtt_confidence_when_none" -q` | ✅ `tests/test_wan_controller.py:2654` |
| OBS-02 (spec line) | REQUIREMENTS.md OBS-02 contains four anchor phrases + amendment annotation. | doc-grep | `for p in 'absent SQLite rows' 'cold-start' 'invalid-snapshot' 'wanctl_arbitration_active_primary' 'amended in Phase 199'; do grep -qF "$p" .planning/REQUIREMENTS.md || echo "MISSING: $p"; done` | ✅ `.planning/REQUIREMENTS.md:27` |
| OBS-02 (SUBSYSTEMS surface) | SUBSYSTEMS.md mentions `signal_arbitration` and the four field names. | doc-grep | `for p in signal_arbitration active_primary_signal rtt_confidence cake_av_delay_delta_us control_decision_reason; do grep -qF "$p" docs/SUBSYSTEMS.md || echo "MISSING: $p"; done` | ❌ Wave 0 (note must be added by plan) |
| OBS-02 (RUNBOOK surface) | RUNBOOK.md mentions `wanctl_arbitration_active_primary` as the per-cycle denominator. | doc-grep | `grep -qF "wanctl_arbitration_active_primary" docs/RUNBOOK.md && grep -qF "denominator" docs/RUNBOOK.md` | ❌ Wave 0 (note must be added by plan) |
| OBS-02 (docs-only invariant) | No file under `src/wanctl/` changed for this phase. | git-diff | `[ -z "$(git diff --name-only "$PHASE_BASE..HEAD" -- src/wanctl/)" ]` (where `$PHASE_BASE` = the SHA at Phase 199 start, e.g., `41f96e6`) | ✅ check infra exists |

### Sampling Rate

- **Per task commit:** the appropriate doc-grep above (1–2s).
- **Per wave merge:** all four doc-greps + `git diff --name-only` invariant + the optional pytest pin (sum < 5s).
- **Phase gate:** all five checks recorded in `199-VERIFICATION.md` body; auditor reruns from the artifact.

### Wave 0 Gaps

- [ ] `docs/SUBSYSTEMS.md` — add `signal_arbitration` field-shape note covering OBS-02 absent-row semantics. **No new file; targeted edit only.**
- [ ] `docs/RUNBOOK.md` — add operator-query note naming `wanctl_arbitration_active_primary` as the per-cycle denominator. **No new file; targeted edit only.**
- [ ] `199-VERIFICATION.md` — write phase-close artifact mirroring Phase 198 frontmatter shape with `phase_scope: docs-only` + `files_touched`.
- [ ] No framework install. No new fixtures. No new test files. Test pin already exists at `tests/test_wan_controller.py:2654`.

## Project Constraints (from CLAUDE.md)

The project root `CLAUDE.md` and `~/CLAUDE.md` add the following directives the planner must honor:

- **Production network controller; conservative changes only.** This phase is docs-only — naturally complies.
- **Priority order: stability > safety > clarity > elegance.** Docs-only edits land in the "elegance" tier; targeted notes (D-08) win over rewrites.
- **No `IPs/hostnames/usernames/company names` in `CLAUDE.md`.** Not relevant — this phase touches `docs/`, not `CLAUDE.md`.
- **Pre-commit hook + `project-finalizer` mandatory before commits.** Plan tasks must end with a finalizer step before any commit (a wanctl convention; not Phase-199-specific).
- **Use the venv directly (`.venv/bin/pytest`), no `pip` or `make ci` substitutions.** All test commands in this research file use `.venv/bin/pytest`.
- **`wanctl_arbitration_active_primary` as the per-cycle denominator is established convention** across Phase 196 / 197 / 198 audit scripts (per CONTEXT.md `<code_context>` lines 108). Phase 199 propagates that into operator docs — no new convention being introduced.
- **Knowledge map: `query_rag(query, project="wanctl")` is the canonical investigation tool.** Not used in this research because every fact is verified against files in the working tree at HEAD; for the planner's purposes, RAG is fine as a secondary lookup.

## Sources

### Primary (HIGH confidence)
- `.planning/REQUIREMENTS.md:26–27` — OBS-01 (contract enumeration) and OBS-02 (amended absent-row wording). [VERIFIED: read directly at HEAD]
- `.planning/REQUIREMENTS.md:122` — v1.40 traceability table line `OBS-02 | Phase 193 + Phase 199 (wording amendment) | Complete (caveat resolved by Phase 199)`. [VERIFIED: read directly]
- `.planning/ROADMAP.md:364–386` — Phase 199 entry (Goal, Scope, Out-of-scope, Success Criteria). [VERIFIED: read directly]
- `.planning/STATE.md:1–34` — milestone v1.40, phase 199, status `ready_to_plan`. [VERIFIED: read directly]
- `.planning/phases/198-spectrum-cake-primary-b-leg-rerun/198-VERIFICATION.md` — frontmatter and body shape for `199-VERIFICATION.md`. [VERIFIED: read directly]
- `src/wanctl/wan_controller.py:2683, 2724, 3091–3097, 3148–3159, 4222–4239` — implementation anchors. [VERIFIED: read directly + grep by symbol name]
- `tests/test_wan_controller.py:2654–2678` — absent-row test pin (`test_phase195_metrics_skip_rtt_confidence_when_none`). [VERIFIED: read directly + ran test, 1 passed in 0.40s]
- `docs/SUBSYSTEMS.md:121–140` — `## Health And Metrics` section, current state. [VERIFIED: read directly]
- `docs/RUNBOOK.md:339–365` — `/metrics/history` + `python3 -m wanctl.history` block. [VERIFIED: read directly]
- `docs/CONFIGURATION.md` — does **not** mention `/health` (zero grep matches). [VERIFIED: `grep -n "signal_arbitration\|/health\|wans\|rtt_confidence" docs/CONFIGURATION.md` returned empty]

### Secondary (MEDIUM confidence)
- `.planning/phases/199-obs-02-spec-impl-reconciliation/199-CONTEXT.md` — phase decisions, marked authoritative for this research. [VERIFIED: read directly]
- `.planning/phases/199-obs-02-spec-impl-reconciliation/199-DISCUSSION-LOG.md` — alternatives considered audit trail. [VERIFIED: read directly]

### Tertiary (LOW confidence)
- None. All factual claims in this research file were verified at HEAD against the working tree, by direct read or grep or test execution.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all tools verified by `command -v` / `--version`.
- Architecture: HIGH — every anchor verified by symbol-name grep + direct read at HEAD.
- Pitfalls: HIGH — line-number drift, CONFIGURATION.md absence, test runtime, and refractory_active scope all empirically verified.
- Validation Architecture: HIGH — pytest invocation timed at 0.40s; all greps composable from `man grep`.

**Research date:** 2026-05-02
**Valid until:** 2026-06-01 (30 days; documentation surfaces and test pins are stable on this timescale; revisit only if a new phase amends OBS-01 / OBS-02 or restructures `docs/SUBSYSTEMS.md`).
