# Phase 211: Production Verification & Milestone Closure - Context

**Gathered:** 2026-05-26
**Status:** Ready for planning

<domain>
## Phase Boundary

Deploy the Phase 210 build (windowed peak accumulator) to production on cake-shaper Spectrum then ATT under a two-snapshot rollback ritual, observe at least one real DOCSIS flapping event where `details.peak_transition_count > details.flap_threshold` (>30) lands in the alerts table, prove `cooldown_sec` dedup holds end-to-end during that event (ALERT-03), re-verify SAFE-10 at the milestone boundary, ship version bump `1.44.0 → 1.45.0` in a single closeout commit, and archive v1.45 to `.planning/milestones/v1.45-phases/`.

**In scope:** ALERT-03 (alert-once-per-episode in production), VERIFY-01 (real production event proves the metric carries intensity), SAFE-10 closeout re-verification at milestone close, version bump + CHANGELOG entry, v1.45 milestone archive.

**Out of scope (SAFE-10 hard fence):** Any `src/wanctl/` source diff outside the `wan_controller.py:4275-4360` flapping block and the version-bump lines (Phase 210 already passed 11/11 SAFE-10 truths). No controller threshold/algorithm/EWMA/dwell/deadband/burst change. No `alert_engine.py` semantic change. No netlink/CAKE/topology/steering change. Phase 206 A/B soak harness is explicitly NOT used as a verification gate — wrong tool for an alerting-payload fix. No other deferred SEED items (SEED-003..007) pulled forward.

</domain>

<decisions>
## Implementation Decisions

### VERIFY-01 observation gate
- **D-01:** Hard observation window is 7 days post-deploy on Spectrum (Spectrum historically fires `flapping_ul` ~daily during DOCSIS-stress periods; ATT fires `flapping_dl` more rarely — 3 events in 30d). ATT deploy starts the day after Spectrum, so its 7d window runs in parallel-staggered.
- **D-02:** Minimum-viable evidence is **one** qualifying alerts-table row — either `flapping_dl` or `flapping_ul` on either WAN — where `details.peak_transition_count > details.flap_threshold` (>30). Matches REQUIREMENTS.md ALERT-01 literal text; Codex round-2 review signed off on single-event sufficiency.
- **D-03:** Evidence artifact lands at `.planning/phases/211-production-verification-milestone-closure/211-VERIFY-01-evidence/` as per-event JSON (one file per qualifying alert row, raw `details` payload + alerts.id + timestamps) plus a top-level `EVIDENCE.md` narrative pointing at the SQL snippet used, the alerts.id selected, episode boundaries, and the `peak vs flap_threshold` delta. Self-contained closeout that survives alerts-table rotation/pruning.
- **D-04:** If the 7-day window expires with no qualifying event: operator-review branch — inspect alerts volume + DOCSIS plant state, choose between (a) extend window 7d, or (b) defer VERIFY-01 to v1.46 close as a watch-list item with synthetic-proof acceptable (Phase 210 unit + integration tests already prove the mechanism; production observation is the open gate). Do NOT auto-close v1.45 without operator gate; do NOT roll back (alerting-only change cannot regress traffic).

### Deploy ritual scope
- **D-05:** Full two-snapshot ritual per host. Both cake-shaper Spectrum and ATT get pre-deploy: `/opt/wanctl-prephase211-{ISO8601}.tar.gz` plus `/etc/wanctl/{spectrum,att}.yaml.prephase211-{ISO8601}`. Snapshot A is the unconditional rollback target. No Snapshot B is needed — there's no soak comparator to validate against. Mirrors Phase 201-15 / Phase 209 D-10 naming convention (substitute `prephase211`).
- **D-06:** Phase 206 A/B soak harness is **NOT** run as a verification gate. v1.45 cannot affect zone/cause-tag distributions — only the alert payload field value changes. A/B vs v1.43 baseline is the wrong comparator for an alerting-payload fix. Saves 24h soak + harness wiring + operator effort.
- **D-07:** Deploy ordering is canary-style: Spectrum first, ATT next-day (T+24h minimum after Spectrum deploy). Spectrum's higher flapping cadence gives ALERT-01/02/03 evidence within ~24h; only then ship ATT. Mirrors v1.44 canary discipline. Avoids simultaneous-fleet exposure.
- **D-08:** Pre-deploy gate per host = (1) Phase 210 verification report `passed` on file (already on disk: `.planning/phases/210-windowed-peak-accumulator-implementation/210-VERIFICATION.md`, 11/11 truths verified 2026-05-26), (2) pre-deploy snapshot captured per D-05, (3) post-deploy `curl http://127.0.0.1:9101/health | jq .version` reports `1.45.0` on each host. **No** rerun of `scripts/phase206-predeploy-gate.py` — that gate is topology/soak-flavored and not relevant for an alerting-payload fix.

### ALERT-03 verification approach
- **D-09:** Primary signal that `cooldown_sec` dedup holds end-to-end is **alerts-table row count vs episode duration**. For the qualifying VERIFY-01 event, count `alerts` rows with `rule_id='congestion_flapping'` on that WAN+direction over the episode window. Authoritative because the alerts table is the operator-visible surface ALERT-03 actually cares about.
- **D-10:** Secondary cross-check is `journalctl -u wanctl@<wan>` grepped for the `congestion_flapping` logger over the same episode window. Independent surface; captures the literal "log-spam" wording from REQUIREMENTS.md ALERT-03. Sanity check, not the decision-gate.
- **D-11:** Required margin is strict: **exactly 1 alerts row per sustained episode**. Matches the "alert-once-per-episode" literal phrasing in ALERT-03. If a single sustained event produces ≥2 rows in the alerts table, ALERT-03 fails.
- **D-12:** Failure handling: if ALERT-03 fails (log spam observed or alerts-table row count > 1 per episode) but VERIFY-01 passes (peak > threshold visible), **block v1.45 milestone close** and open a follow-up phase for the cooldown regression. ALERT-03 is a literal v1.45 requirement, not soft — milestone is not shipped without it. Do NOT roll back v1.45 entirely (v1.44 had the same dedup behavior; rolling back would not help).

### Milestone closure mechanics
- **D-13:** Version bump `1.44.0 → 1.45.0` lands in a **single closeout commit BEFORE Spectrum deploy**, with exactly these files: `pyproject.toml`, `src/wanctl/__init__.py`, `docker/Dockerfile`, `CHANGELOG.md`. Binary deployed for canary IS `1.45.0`; rollback restores `1.44.0` via Snapshot A. Mirrors Phase 209 D-11 — avoids "1.44.x-with-1.45-CHANGELOG" intermediate state and rollback artifact-naming confusion.
- **D-14:** SAFE-10 milestone-close re-verification = run existing `scripts/check-safe07-source-diff.sh` against v1.44 close anchor `21ee630` (the same baseline Phase 210-03 used). Pass anchor as positional arg / env override; no script edit, no new `--v145` flag required. SAFE-10 invariant: zero `src/wanctl/` diff outside `wan_controller.py:4275-4360` flapping block plus the version-bump lines (`__init__.py:1` only). `alert_engine.py` and the five-file SAFE-09 allowlist remain empty-diff.
- **D-15:** v1.45 archive happens in the **same commit/PR as Phase 211 closeout**: `.planning/phases/210-*` and `.planning/phases/211-*` move to `.planning/milestones/v1.45-phases/`. Single "v1.45 closed" moment in git history. Mirrors v1.44 archive pattern from 2026-05-26.
- **D-16:** CHANGELOG.md `v1.45.0` heading content = (a) bug-fix line for the windowed peak accumulator (`flapping_dl/ul peak_transition_count now reflects 120s-window peak instead of fire-cycle value`), (b) payload-compatibility note (`transition_count` still emitted), (c) explicit invariant statement (`cooldown_sec dedup unchanged — alert-once-per-episode preserved`). Operator-decision-driving tone, matches Phase 209 D-16 precedent. No inline Codex-review narrative — that belongs in the archive, not the CHANGELOG.

### Claude's Discretion
- Exact wording of CHANGELOG.md v1.45.0 entry (D-16 constrains content; phrasing open).
- Plan breakdown shape (1 plan vs 3 plans). The natural cleavages are: (a) closeout-commit + Spectrum deploy + Spectrum 7d watch, (b) ATT deploy + ATT 7d watch + VERIFY-01 evidence capture, (c) ALERT-03 cross-check + SAFE-10 milestone-close + archive. Planner's call to fold or split.
- Per-event JSON filename convention under `211-VERIFY-01-evidence/` (e.g., `alert-{id}.json` vs `flapping-{wan}-{ISO8601}.json`). Operator-readable, not load-bearing.
- Whether to add a small `scripts/capture-flapping-evidence.sh` helper that does the alerts-table SQL → JSON dump for D-03. Useful if the wait window extends; planner's call.
- Whether the alerts-table SQL query lives in EVIDENCE.md or as a separate `211-VERIFY-01-evidence/QUERY.sql` file. Default: inline in EVIDENCE.md for self-contained closeout.
- Exact systemd-unit name and journalctl filter pattern for D-10 secondary cross-check — operator-environment-specific.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Roadmap and requirements
- `.planning/ROADMAP.md` §"Phase 211: Production Verification & Milestone Closure" — success criteria 1–4
- `.planning/ROADMAP.md` §"Cross-Cutting Invariants" — SAFE-10 verification at every phase boundary
- `.planning/REQUIREMENTS.md` — ALERT-03 (alert-once-per-episode), VERIFY-01 (production-gate closure), SAFE-10 (cross-cutting)
- `.planning/PROJECT.md` — current milestone context (v1.45 Flapping Peak-Counter Window Repair)
- `.planning/STATE.md` — v1.45 progress, deferred items carried from v1.44 close

### Prior-phase artifacts that bind Phase 211
- `.planning/phases/210-windowed-peak-accumulator-implementation/210-VERIFICATION.md` — 11/11 SAFE-10 truths verified 2026-05-26; SAFE-10 baseline = `21ee630`
- `.planning/phases/210-windowed-peak-accumulator-implementation/210-03-SUMMARY.md` — SAFE-10 closeout audit trail (baseline, worktree status, diff inventory, hunk-range check, clear-absence check, PASS verdict)
- `.planning/phases/210-windowed-peak-accumulator-implementation/210-01-PLAN.md` — windowed peak accumulator implementation (`wan_controller.py:4275-4360`)
- `.planning/phases/210-windowed-peak-accumulator-implementation/210-02-PLAN.md` — `TestFlappingDequeClear` + `TestFlappingPeakWindow` tests
- `.planning/milestones/v1.44-phases/209-spectrum-config-migration-production-canary-and-docs/209-CONTEXT.md` — two-snapshot rollback ritual reference (D-10/D-11), closeout-commit shape (D-19), CHANGELOG tone (D-16)
- `.planning/milestones/v1.42-phases/201-docsis-aware-ul-congestion-control/` — original two-snapshot rollback ritual reference implementation (Plan 201-15 / 201-16)

### Code touched by Phase 211 (expected diff surface)
- `pyproject.toml` — `version = "1.45.0"`
- `src/wanctl/__init__.py` — `__version__ = "1.45.0"`
- `docker/Dockerfile` — version label bump
- `CHANGELOG.md` — new `v1.45.0` heading per D-16
- **NO** `src/wanctl/` diff beyond `__init__.py:1` (SAFE-10 hard fence — Phase 210 already shipped `wan_controller.py:4275-4360`)
- **NO** test changes (Phase 210 already shipped `tests/test_alert_engine.py` and `tests/integration/test_flapping_integration.py` updates)

### Tooling touched by Phase 211 (observation/evidence/closeout)
- `scripts/check-safe07-source-diff.sh` — invoked with v1.44 close anchor `21ee630`; no edit, just re-run (D-14)
- `.planning/phases/211-production-verification-milestone-closure/211-VERIFY-01-evidence/` — new evidence subdir (D-03)
- `.planning/phases/211-production-verification-milestone-closure/211-VERIFICATION.md` — Phase 211 verification report destination
- Operational helpers (potentially) — `scripts/capture-flapping-evidence.sh`, JSON query against alerts table; planner's call (Claude's Discretion)

### Reference SHAs and baselines
- `21ee630` — v1.44 archive marker; SAFE-10 source-diff anchor (Phase 210-03 already verified against this)
- `c9932d2` — v1.44 close commit cited in REQUIREMENTS.md SAFE-10 (resolves to v1.42-era in this checkout per 210-03 note; `21ee630` is the operational local equivalent)
- Phase 210 deploy artifact: built from current `main` HEAD post-Phase-210 closeout commits

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **`scripts/check-safe07-source-diff.sh`** (v1.43-shipped via Phase 203, hardened by Phase 207 HRDN-01, extended by Phase 209 `--att-config-whitelist`) — already has fail-closed dirty-tree pre-check, operator-overridable ref via positional arg + `PHASE_209_ATT_REF` env, and bounded-allowlist mode. SAFE-10 milestone-close uses default mode with anchor `21ee630`; no script edit needed.
- **Phase 201-15 / Phase 209 two-snapshot pattern** — `/opt/wanctl-prephase{N}-{ISO8601}.tar.gz` + `/etc/wanctl/{wan}.yaml.prephase{N}-{ISO8601}` is the established rollback artifact contract. Phase 211 substitutes `prephase211` for both cake-shaper Spectrum and ATT hosts.
- **`/health` endpoint version readback** — `curl http://127.0.0.1:9101/health | jq .version` confirms deployed binary on each host. Standard post-deploy smoke check; no new tooling needed.
- **Phase 210 verification report** — 11/11 truths verified 2026-05-26 against baseline `21ee630`. Phase 211 inherits this as the implementation-side evidence; no re-test needed beyond static `.venv/bin/pytest` smoke before deploy.

### Established Patterns
- **Closeout commit shape (Phase 209 D-19)** — single closeout commit with a pinned file list. Phase 211 closeout commit = exactly 4 files: `pyproject.toml` + `src/wanctl/__init__.py` + `docker/Dockerfile` + `CHANGELOG.md`. Identical commit-shape mechanics; smaller file count because no YAML/topology changes ship in v1.45.
- **Milestone-archive pattern (v1.44 2026-05-26 / v1.43 2026-05-13)** — `.planning/phases/*` for the closed milestone move to `.planning/milestones/v1.45-phases/` in the closeout PR. Roadmap status flips from 🚧 → ✅ with shipped date. STATE.md updates `last shipped milestone` to v1.45 and `current milestone` to v1.46 (or blank, awaiting next-milestone discussion).
- **SAFE invariant verifier as fail-closed gate (Phase 207 HRDN-01)** — `scripts/check-safe07-source-diff.sh` exits non-zero on violation; CI/pre-commit hookable. Phase 211 SAFE-10 close runs this and captures the exit-0 output as the closeout audit artifact.
- **Production-canary phase pattern (Phase 209)** — Phase that splits the production-gate from the PR-merge-time implementation phase (mirrors Phase 209 vs Phase 205/206/207/208 split). Phase 211 inherits this discipline: no code, no tests, just deploy + observe + close.

### Integration Points
- Deploy targets are cake-shaper Spectrum (primary canary) and cake-shaper ATT (T+24h fleet completion). Both run `wanctl@<wan>.service` systemd units; `/opt/wanctl` is the install root per `runtime layout` in CLAUDE.md.
- Alerts table is the durable VERIFY-01 evidence surface — captured payloads include `details.peak_transition_count`, `details.transition_count`, `details.flap_threshold`, `details.flap_window`. Phase 211 reads, never writes.
- `journalctl -u wanctl@<wan>` is the secondary log surface for D-10 cross-check; standard systemd integration, no new logging configured.
- Git history: Phase 211 closeout PR is the v1.45 ship-PR. Tag `v1.45.0` lands post-merge on `main`; release notes derive from CHANGELOG.md v1.45.0 heading.

</code_context>

<specifics>
## Specific Ideas

- **Two-snapshot artifact naming:** `/opt/wanctl-prephase211-{ISO8601}.tar.gz` + `/etc/wanctl/{spectrum|att}.yaml.prephase211-{ISO8601}` — directly inherits Phase 201-11 / 198-01 / 209 naming convention. ISO8601 timestamp is the per-deploy unique key.
- **SAFE-10 baseline is `21ee630`**, not the REQUIREMENTS.md-cited `c9932d2`. Phase 210-03 already established this — `c9932d2` resolves to v1.42-era in this checkout; `21ee630` is the operational local equivalent and the established Phase 210/211 anchor.
- **VERIFY-01 single-event sufficiency** is the Codex round-2 design decision (2026-05-26) — one DL OR UL event with `peak > flap_threshold` is the closure bar. Don't gold-plate to "both paths required" — that creates a slow-ATT failure mode without strengthening the proof.
- **No A/B soak comparator for v1.45** is intentional — Phase 209 used the Phase 206 A/B harness because topology/distribution shifts were the failure mode. v1.45 is alerting-payload-only; the harness has no purchase on the failure mode it's designed to catch.
- **Spectrum-first canary is operational discipline, not a SAFE invariant** — alerting-only scope means simultaneous-fleet deploy carries no traffic-path risk, but the per-WAN observability signal (catch an ALERT-03 regression on Spectrum before ATT has the same code in flight) is the canary's value.
- **ALERT-03 strict-1-row-per-episode is the literal REQUIREMENTS.md bar** — don't loosen to a margin (e.g., ≤3 rows) just to make the test easier to pass. If the alerts table shows ≥2 rows for a sustained event, that IS the regression ALERT-03 protects against.

</specifics>

<deferred>
## Deferred Ideas

- **Operator-summary integration for peak-vs-threshold delta** — surfacing the `(peak - flap_threshold)` delta in `wanctl-check` / `/health` JSON as an at-a-glance "how intense was this episode?" signal came up implicitly during ALERT-03 discussion. Deferred: belongs in a future observability phase if peak-intensity forensics become a recurring operator question.
- **Automated rollback trigger on ALERT-03 regression** — instead of operator-gated rollback, auto-rollback if alerts-table row count > 1 per episode within 1h of deploy. Came up during D-12 design but deferred — alerting-only scope doesn't justify the automation complexity, and operator review is the established Phase 198/201/209 pattern.
- **Phase 206 A/B harness extension for alerting-payload distributions** — if future milestones change alert payload shape (not just field values), the A/B harness could be extended to compare payload-field distributions. Out of scope for v1.45; speculative.
- **`scripts/capture-flapping-evidence.sh` operator-callable** — turn the VERIFY-01 evidence-capture SQL into a reusable script. Came up under D-03; deferred to Claude's Discretion / planner's call. Belongs as a small utility if the 7d wait extends or if future flapping forensics need replay.
- **CHANGELOG.md broader v1.45 cleanup** — only the v1.45.0 heading lands in Phase 211 closeout. Any wider CHANGELOG reorganization is its own phase.
- **Codex round-2 design-review narrative archive** — Codex peer-review log for Design Option A vs Option B (2026-05-26) lives in the source todo and milestone REQUIREMENTS.md. Could be promoted into a `docs/decisions/` ADR if v1.45 forensics need to cite it externally. Deferred to v1.46+ if needed.
- **SEED-003..007 deferred items** — explicitly NOT pulled into v1.45. Carried to v1.46+ per STATE.md. Phase 211 does not touch them.

</deferred>

---

*Phase: 211-production-verification-milestone-closure*
*Context gathered: 2026-05-26*
