# Phase 199: OBS-02 Spec/Impl Reconciliation - Pattern Map

**Mapped:** 2026-05-02
**Files analyzed:** 4 (1 verify-only, 2 doc edits, 1 new artifact)
**Analogs found:** 4 / 4
**Phase scope:** docs-only -- no Python source modification permitted

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `.planning/REQUIREMENTS.md` | spec (machine-checkable) | verify-only (read) | n/a -- already amended in tree | n/a (no edit) |
| `docs/SUBSYSTEMS.md` | operator doc -- payload-shape reference | targeted-note insertion (additive bullet under existing section) | self: lines 130-138 (`Major response sections` enumeration in `## Health And Metrics`) | exact (in-section style continuation) |
| `docs/RUNBOOK.md` | operator doc -- incident-triage runbook | targeted-note insertion (additive callout in existing reader block) | self: lines 281-287 (`>` blockquote callout in measurement-resilience section); lines 349-365 (`/metrics/history` reader block -- insertion site) | exact (existing in-file callout idiom) |
| `199-VERIFICATION.md` | phase-close verification artifact | YAML frontmatter + body invariant proofs | `.planning/phases/198-spectrum-cake-primary-b-leg-rerun/198-VERIFICATION.md` | exact (project precedent) |

## Pattern Assignments

### `.planning/REQUIREMENTS.md` (spec, verify-only)

**Analog:** none required -- file is verify-only.

**Pre-staged content** (REQUIREMENTS.md:27, verbatim -- quote in operator notes):

The OBS-02 row already contains the contract text the operator notes must reuse. The exact phrase to quote (preserving the em-dash) is:

    cold-start and invalid-snapshot cycles produce absent SQLite rows
    and `/health` nulls -- no NaN, -1, or sentinel emission.

(In the actual REQUIREMENTS.md file the dash character used is the Unicode em-dash; preserve it verbatim when copying. This pattern map renders it as a double hyphen for hook-safety.)

The full row begins `- [x] **OBS-02**:` and ends with the annotation `*Wording amended in Phase 199 to formally specify absent-row semantics.*` -- four anchor phrases must remain present: `absent SQLite rows`, `cold-start`, `invalid-snapshot`, `wanctl_arbitration_active_primary`.

**Pattern rule:** Do NOT re-edit. VERIFICATION.md check 2 greps for the four anchor phrases plus the `*Wording amended in Phase 199` annotation.

---

### `docs/SUBSYSTEMS.md` (doc, targeted-note insertion)

**Analog:** self -- `## Health And Metrics` "Major response sections" bullet block (lines 130-138).

**Surrounding section style** (lines 121-138, the form to imitate):

    ## Health And Metrics

    Implementation map:

    - `src/wanctl/health_check.py`: `HealthCheckHandler`, `/health`, `/metrics`, and `/metrics/history` handlers.
    - `src/wanctl/metrics.py`: `MetricsRegistry`, autorate, steering, storage, runtime, and process metrics.

    `GET /health` returns HTTP 200 when healthy and HTTP 503 when degraded. Degraded means at least one of: repeated controller failures, router unreachable, or disk/runtime critical status.

    Major response sections:

    - `wans[]`: per-WAN rate, state, hysteresis, RTT, connectivity, measurement, IRTT, reflector, fusion, CAKE, tuning, storage, and runtime status.
    - `alerting`: alert engine enabled state, fired count, and active cooldowns.
    - `disk_space`: free/total bytes and warning state for `/var/lib/wanctl`.
    - `summary`: compact operator-facing status rows.
    - `storage` and `runtime`: bounded pressure status for SQLite and process memory.

    `GET /metrics/history` queries stored SQLite metrics. Query parameters include `range`, `from`, `to`, `metrics`, `wan`, `limit`, and `offset`. Responses include `metadata.source.mode` and `metadata.source.db_paths` so callers can distinguish endpoint-local data from merged discovery fallback.

**Style anchors extracted from this section:**
- Bullet items lead with a backticked field name and a comma-separated descriptor list (e.g., `` `wans[]`: per-WAN rate, state, hysteresis, ... ``).
- Sentences are short, declarative; no second-person voice.
- Backticks are used for every JSON field name, every metric name, and every endpoint path.
- No `> Note:` or `**Note:**` callouts appear in this file (verified by grep). The section's idiom is plain prose plus bullet lists.
- Cross-doc references in this file are inline parenthetical or bare path (no `[link](path)` markdown links observed in the section).

**Recommended insertion form:** sub-bullet expansion immediately under the existing `wans[]` line -- preserves bullet-list rhythm of the "Major response sections" block. Alternative: a single short sentence appended after the bullet list referencing OBS-02 (less preferred -- it isolates the field-shape note from its parent enumeration).

**Skeleton** (final wording is planner's call; quote D-04 verbatim, restoring the actual em-dash from REQUIREMENTS.md):

    - `wans[]`: per-WAN rate, state, hysteresis, RTT, connectivity, measurement, IRTT, reflector, fusion, CAKE, tuning, storage, and runtime status.
      - `signal_arbitration` (per OBS-01): `active_primary_signal`, `rtt_confidence` (float 0.0-1.0 or `null`), `cake_av_delay_delta_us` (int or `null`), `control_decision_reason`. Per REQUIREMENTS.md OBS-02, cold-start and invalid-snapshot cycles produce absent SQLite rows and `/health` nulls -- no NaN, -1, or sentinel emission. See RUNBOOK.md `/metrics/history` for the operator-side denominator note.

**Anti-pattern rule:** Do NOT enumerate the fifth `signal_arbitration` field `refractory_active`. It is emitted by `get_health_data()` at `wan_controller.py:4222-4239` but is **not** part of the OBS-01 contract; documenting it here silently expands the spec.

---

### `docs/RUNBOOK.md` (doc, targeted-note insertion)

**Analog:** self -- two patterns in this file.

**Pattern A -- `>` blockquote callout idiom** (lines 281-287, the established in-file callout style):

    > What This Does Not Change: SAFE-02 ICMP-failure fallback, total-connectivity
    > handling, controller thresholds, and steering policy are unchanged by the
    > measurement-resilience milestone.
    > This section is inspection-only and must not be read as a tuning instruction.
    > Follow the post-deploy flow in [DEPLOYMENT.md](DEPLOYMENT.md)
    > and escalate through [Escalation Flow](#escalation-flow) when the rubric
    > shows degraded measurement.

**Style anchors from Pattern A:**
- Uses bare `>` blockquote (no `> Note:` prefix; the leading capitalized phrase carries the role).
- Plain English imperative; can run multiple sentences.
- Cross-doc references use markdown link form `[DEPLOYMENT.md](DEPLOYMENT.md)`.
- In-file section references use anchor links: `[Escalation Flow](#escalation-flow)`.

**Pattern B -- insertion site, `/metrics/history` reader block** (lines 349-365, the surrounding context the new callout joins):

    For retained history, use the supported readers instead of guessing a single DB path:

        ssh <host> 'sudo -n env PYTHONPATH=/opt python3 -m wanctl.history --last 1h --metrics wanctl_rtt_ms --json | python3 -m json.tool | head -n 40'
        ssh <host> 'curl -s "http://<health-ip>:9101/metrics/history?range=1h&limit=5" | python3 -m json.tool'

    On the current production hosts:

    - `/metrics/history` is the endpoint-local HTTP history view for the connected autorate daemon.
    - `python3 -m wanctl.history` is the authoritative merged cross-WAN proof path.

    Use the `curl` command above to confirm endpoint availability, response shape, and that WAN's
    local history view. Use the `python3 -m wanctl.history` command above -- falling back to direct
    DB inventory only if the CLI is unavailable -- when you need merged cross-WAN verification. The
    dashboard history tab surfaces this same distinction through `metadata.source`, so the rule is
    identical in the TUI and in this runbook.

(Render note: the inner shell-fence block in the actual file is a real ```bash ...``` fenced block; here it is shown indented for hook-safety.)

**Recommended insertion form:** Pattern A `>` blockquote callout placed immediately after the "endpoint-local vs. merged cross-WAN" paragraph that closes at line 365, before the per-WAN DB compaction subsection at line 367. Rationale: that location terminates the reader block with the operator-query rule; an operator doing coverage triage finishes the block holding the right denominator anchor.

**Skeleton** (final wording is planner's call; quote D-04 verbatim, restoring the actual em-dash from REQUIREMENTS.md):

    > Per-cycle SQLite denominator: `wanctl_arbitration_active_primary` is emitted on every
    > CAKE-metrics-enabled cycle and is the reliable denominator for coverage queries against the
    > per-WAN metrics SQLite store. `wanctl_rtt_confidence` and `wanctl_cake_avg_delay_delta_us`
    > are emitted only when valid. Per REQUIREMENTS.md OBS-02: cold-start and invalid-snapshot
    > cycles produce absent SQLite rows and `/health` nulls -- no NaN, -1, or sentinel emission.
    > Absent rows for those two metrics are expected, not data loss.

---

### `199-VERIFICATION.md` (verification artifact, new file)

**Analog:** `.planning/phases/198-spectrum-cake-primary-b-leg-rerun/198-VERIFICATION.md` (lines 1-7 frontmatter + section headings).

**Frontmatter pattern** (198-VERIFICATION.md lines 1-7, minimal shape to mirror):

    ---
    phase: 198-spectrum-cake-primary-b-leg-rerun
    verified: 2026-05-02T10:48:52Z
    status: passed
    score: 4/4 must-haves verified
    overrides_applied: 0
    requirements: [VALN-04, VALN-05a, SAFE-05]
    ...
    ---

**Style anchors from frontmatter:**
- `phase:` is the full padded `{NNN-name}` slug (matches the phase directory name).
- `verified:` is ISO-8601 UTC timestamp `YYYY-MM-DDTHH:MM:SSZ`.
- `status:` is one of `passed` / `failed` (from observed precedent).
- `score:` is `<n>/<m> must-haves verified` free-text.
- `overrides_applied:` is integer (typically 0).
- `requirements:` is an inline YAML list of REQ-IDs.
- Phase 198 extends with phase-specific keys (`closed_via_rerun_attempt`, `rerun_history`); Phase 199 will extend with `phase_scope: docs-only` and `files_touched: [...]` per D-06.

**Phase-199 frontmatter (target shape, per D-06):**

    ---
    phase: 199-obs-02-spec-impl-reconciliation
    verified: 2026-05-XXTHH:MM:SSZ
    status: passed
    score: 4/4 must-haves verified  # or 5/5 if optional pytest check is included
    overrides_applied: 0
    requirements: [OBS-02]
    phase_scope: docs-only
    files_touched:
      - .planning/REQUIREMENTS.md
      - docs/SUBSYSTEMS.md
      - docs/RUNBOOK.md
    ---

**Body section pattern** (198-VERIFICATION.md lines 89-209, structure to reuse selectively):

| Section | Phase 198 form | Phase 199 disposition |
|---------|----------------|------------------------|
| Title `# Phase NNN: <Name> Verification Report` | line 89 | mirror exactly |
| `**Phase Goal:**`, `**Verified:**`, `**Status:**`, `**Re-verification:**` block | lines 91-94 | mirror -- describe spec/impl/doc lockstep goal |
| `## Goal Achievement` then `### Observable Truths` table | lines 97-107 | mirror -- rows 1..4 are the four D-05 checks |
| `### Required Artifacts` table | lines 109-131 | trim to three rows: REQUIREMENTS.md, SUBSYSTEMS.md, RUNBOOK.md (no flent/audit JSON chain in a docs phase) |
| `### Key Link Verification` table | lines 133-141 | replace with `### Spec Lockstep` mapping REQUIREMENTS.md OBS-02 to quoted text in SUBSYSTEMS.md and RUNBOOK.md |
| `### Data-Flow Trace (Level 4)` | lines 143-152 | OMIT -- empty noise for a docs-only phase |
| `### Behavioral Spot-Checks` table | lines 154-164 | trim to the four (or five) one-line shell/grep/pytest invocations |
| `### Requirements Coverage` table | lines 166-172 | one row: OBS-02 |
| `### Anti-Patterns Found` table | lines 174-180 | empty (or document any noticed mid-phase doc-organization risks) |
| `### Human Verification Required` | lines 182-184 | note: none -- every check is mechanizable |
| `### Rerun History` | lines 186-200 | OMIT -- only relevant to soak rerun phases |
| `### Cascade Closure` | lines 202-204 | OMIT -- only relevant to multi-phase cascades |
| `### Gaps Summary` | lines 206-208 | mirror -- record any caveats found during verify pass |
| Footer `_Verified: ..._` and `_Verifier: ..._` | lines 211-213 | mirror exactly |

**Body skeleton excerpt** (Phase 198 lines 96-107, the Observable Truths form to mirror):

    ## Goal Achievement

    ### Observable Truths

    | # | Truth | Status | Evidence |
    |---|---|---|---|
    | 1 | Queue-primary invariant holds during each corrected `tcp_12down` loaded window: ... | check VERIFIED | Canonical `loaded-window-audit-run1..3.json` from promoted attempt 11 each report `verdict: pass`, `health_sample_count: 30`, `queue_primary_health_pct: 100.0`, and `health_non_queue: 0`. |

**Phase-199 Observable Truths target (four-or-five rows, command-backed):**

| # | Truth | Verifying command |
|---|-------|-------------------|
| 1 | Docs-only invariant: no Python source under `src/wanctl/` changed during Phase 199. | `[ -z "$(git diff --name-only "$PHASE_BASE..HEAD" -- src/wanctl/)" ]` |
| 2 | REQUIREMENTS.md OBS-02 contains all four anchor phrases plus the Phase 199 amendment annotation. | `for p in 'absent SQLite rows' 'cold-start' 'invalid-snapshot' 'wanctl_arbitration_active_primary' 'amended in Phase 199'; do grep -qF "$p" .planning/REQUIREMENTS.md \|\| echo "MISSING: $p"; done` |
| 3 | SUBSYSTEMS.md mentions `signal_arbitration` plus the four OBS-01 contract field names. | `for p in signal_arbitration active_primary_signal rtt_confidence cake_av_delay_delta_us control_decision_reason; do grep -qF "$p" docs/SUBSYSTEMS.md \|\| echo "MISSING: $p"; done` |
| 4 | RUNBOOK.md names `wanctl_arbitration_active_primary` as the per-cycle denominator. | `grep -qF "wanctl_arbitration_active_primary" docs/RUNBOOK.md && grep -qF "denominator" docs/RUNBOOK.md` |
| 5 (optional) | Test pin sanity: absent-row test still encodes the spec behavior. | `.venv/bin/pytest -o addopts='' tests/test_wan_controller.py -k "skip_rtt_confidence_when_none" -q` (measured 0.40s) |

**Footer pattern** (198-VERIFICATION.md lines 211-213):

    ---

    _Verified: 2026-05-02T10:48:52Z_
    _Verifier: the agent (gsd-verifier)_

---

## Shared Patterns

### Verbatim spec quote with parenthetical back-reference
**Source:** REQUIREMENTS.md OBS-02 (line 27) -- single source of truth for the absent-row contract phrase.
**Apply to:** both `docs/SUBSYSTEMS.md` and `docs/RUNBOOK.md` notes.
**Rule (from D-04):** quote the exact phrase from REQUIREMENTS.md OBS-02 verbatim (including its em-dash) and add an inline back-reference of the form `Per REQUIREMENTS.md OBS-02:` so future readers can trace the contract source.
**Anti-pattern:** paraphrasing the phrase. Creates a third drifting surface.

### Backticked identifier convention
**Source:** SUBSYSTEMS.md `## Health And Metrics` (lines 121-140) and RUNBOOK.md `/metrics/history` block (lines 349-365).
**Apply to:** every metric name (`wanctl_arbitration_active_primary`, `wanctl_rtt_confidence`, `wanctl_cake_avg_delay_delta_us`), every JSON field name (`signal_arbitration`, `active_primary_signal`, `rtt_confidence`, `cake_av_delay_delta_us`, `control_decision_reason`), every endpoint path (`/health`, `/metrics/history`), and every CLI invocation (`python3 -m wanctl.history`).
**Excerpt** (SUBSYSTEMS.md:138 -- model line):

    `GET /metrics/history` queries stored SQLite metrics. Query parameters include `range`, `from`, `to`, `metrics`, `wan`, `limit`, and `offset`.

### Cross-doc reference convention
**Source:** RUNBOOK.md (line 285) -- `[DEPLOYMENT.md](DEPLOYMENT.md)` markdown-link form.
**Apply to:** any explicit forward link from RUNBOOK.md to SUBSYSTEMS.md (Pitfall 4 in RESEARCH.md says skip the optional CONFIGURATION.md to SUBSYSTEMS.md link). Inside SUBSYSTEMS.md, the existing section idiom uses bare path or parenthetical text rather than markdown links -- match the surrounding form rather than introducing new link syntax.
**Anti-pattern:** adding a markdown link in CONFIGURATION.md without surrounding `/health` context (Pitfall 4).

### YAML frontmatter shape for verification artifacts
**Source:** `.planning/phases/198-spectrum-cake-primary-b-leg-rerun/198-VERIFICATION.md` lines 1-7.
**Apply to:** `199-VERIFICATION.md`.
**Required keys (precedent):** `phase`, `verified`, `status`, `score`, `overrides_applied`, `requirements`.
**Phase-199-specific extensions (per D-06):** `phase_scope: docs-only`, `files_touched: [list]`.

### Mechanizable verification check
**Source:** Phase 198 Observable Truths and Behavioral Spot-Checks tables (lines 100-107, 156-164) -- every row backed by a one-line shell predicate.
**Apply to:** every Observable Truth row in `199-VERIFICATION.md`. No row may be backed by "we eyeballed the doc."
**Rule:** the Phase 199 verdict is a re-runnable shell sequence; an auditor copy-pasting the body of VERIFICATION.md must reach the same verdict.

## No Analog Found

None. Every Phase 199 file has a strong analog already in the working tree:

- REQUIREMENTS.md is verify-only, no analog needed.
- SUBSYSTEMS.md note imitates its own existing `## Health And Metrics` bullet block.
- RUNBOOK.md note imitates its own existing `>` blockquote callout idiom (lines 281-287).
- 199-VERIFICATION.md mirrors `198-VERIFICATION.md` (same project, same artifact class).

## Metadata

**Analog search scope:**
- `.planning/REQUIREMENTS.md` (single section, OBS-02 row at line 27) -- single-pass read.
- `docs/SUBSYSTEMS.md:115-164` -- `## Health And Metrics` section plus immediate neighbors for style continuity.
- `docs/RUNBOOK.md:280-380` -- measurement-resilience callout (lines 281-287) for `>` form, `/metrics/history` reader block (lines 349-365) for insertion site.
- `.planning/phases/198-spectrum-cake-primary-b-leg-rerun/198-VERIFICATION.md` -- full file, single read for frontmatter and body skeleton.
- `grep '^> ' docs/{SUBSYSTEMS,RUNBOOK}.md` -- confirmed RUNBOOK has `>` callouts; SUBSYSTEMS does not.
- `grep -E 'see (REQUIREMENTS|SUBSYSTEMS|RUNBOOK|DEPLOYMENT)\.md|REQUIREMENTS\.md|OBS-0[12]' docs/*.md` -- confirmed no existing OBS- or REQUIREMENTS.md cross-references in `docs/`; safe to introduce as inline parenthetical text per D-04 without competing convention.

**Files scanned:** 4 source/spec/doc files plus the analog VERIFICATION.md.
**Pattern extraction date:** 2026-05-02

**Hook-safety note:** This file uses double-hyphen (`--`) in prose where REQUIREMENTS.md OBS-02 uses an em-dash. When the planner copies the OBS-02 phrase into operator docs (D-04), they must restore the em-dash from REQUIREMENTS.md verbatim -- this rendering is for pattern-map display only.
