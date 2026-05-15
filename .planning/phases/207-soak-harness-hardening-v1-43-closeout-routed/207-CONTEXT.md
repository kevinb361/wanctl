# Phase 207: Soak / harness hardening (v1.43 closeout-routed) - Context

**Gathered:** 2026-05-15
**Status:** Ready for planning
**Source:** discuss-phase (user delegated decisions to Claude — "you decide")

<domain>
## Phase Boundary

Close the v1.43-deferred soak/harness debt cleanly:

- HRDN-01: fail-closed source-diff verifier (no more manual compensation).
- HRDN-02: soak-capture survives transient `curl`/`jq` blips under a bounded counter.
- HRDN-03: `secondary_gate_legacy` block dropped end-to-end (aggregator + tests + docs + CHANGELOG).
- HRDN-04: explicit YES/NO + rationale on CALIB-02 threshold YAML promotion.

**Out of scope:** controller source edits (SAFE-09 invariant — zero `src/wanctl/` diff in this phase), SAFE-09 closeout rebadge (Phase 209 owns the mechanical closeout + ATT-config whitelist mode), T17(b) deep schema-design work (deferred to v1.45+ per REQUIREMENTS.md).

</domain>

<decisions>
## Implementation Decisions

### HRDN-04 — CALIB-02 YAML promotion: **NO** (defer to T17(b))

- **D-01: Route HRDN-04 to NO.** The CALIB-02 threshold stays in `scripts/calib_02_threshold.json` (operator-approved, fail-closed loader at `scripts/soak_summary_aggregate.py:54`); no controller-side YAML key, no validator schema entry, no `continuous_monitoring.upload.calib_02_threshold`.
- **D-02: Rationale anchors.** CHANGELOG entry references (a) CALIB-04 PASS evidence at threshold 175 from soak `20260512T004208Z` (recorded in `scripts/calib_02_threshold.json` + v1.43-ROADMAP.md Plan 204-09); (b) the existing fail-closed JSON-file convention is sufficient — operators tune by editing one file with operator-approval artifact link baked in; (c) T17(b) in REQUIREMENTS.md "Future Requirements" is the right home for the deeper schema-design question, gated on SEED-005 outcomes that would inform knob shape.
- **D-03: No JSON-file changes in this phase.** `scripts/calib_02_threshold.json` is byte-identical at phase close (no value bump, no schema bump). The HRDN-04 deliverable is documentation only.
- **Why NO over YES:** Premature YAML promotion locks knob shape (restart-required semantics, validator entry, default-vs-override precedence) before SEED-005 tells us what semantics actually matter operationally. Lowest-risk closeout, fully reversible — T17(b) can revisit with the right inputs.

### HRDN-01 — Verifier scope: **surgical fail-closed extension only**

- **D-04: Keep `scripts/check-safe07-source-diff.sh` name + SAFE-07 messaging.** No rebadge to SAFE-09 in this phase. Phase 209 owns SAFE-09 mechanical closeout — rebadging here splits the closeout commit across phases and makes Phase 209's diff harder to audit.
- **D-05: Add fail-closed dirty-tree check.** Script gains a new check at startup that runs `git diff --quiet -- src/wanctl/` and `git diff --cached --quiet -- src/wanctl/`; if either has output, exit non-zero with a clear "uncommitted/staged src/wanctl/ edit detected" message, BEFORE evaluating the committed-diff vs ref. This is the entire fail-closed gap.
- **D-06: Don't ship ATT-config whitelist mode in this phase.** That deliverable belongs to Phase 209 (SAFE-08 mechanical closeout). HRDN-01 = src/wanctl/ scope only.
- **D-07: Ref handling unchanged.** Default ref `b72b463` stays; `PHASE_202_CLOSE` env var override stays; Phase 209 will update the default ref + add the ATT whitelist arg as part of its closeout commit. Version-bump tolerance for `__init__.py` 1.42.1→1.43.0 stays — Phase 209 owns updating that pattern when 1.43.0→1.44.0 lands.

### HRDN-02 — Transient-failure tolerance shape

- **D-08: Tolerance model.** Per-row failure bypass under `set -euo pipefail` (use a subshell or explicit `|| true` with capture, NOT a global `set +e`). When `curl | jq` fails: log to sidecar, increment counter, sleep 1, continue. When the failure rate exceeds threshold: emit a final stderr message naming the failure mode breakdown and abort non-zero.
- **D-09: What counts as a failure.** Single aggregate "row failed" counter (incremented when the pipeline produced no valid NDJSON row that second). Distinct failure-mode counters tracked alongside for the postmortem sidecar: `curl_exit_nonzero`, `curl_http_nonzero` (HTTP code != 200 — requires curl `-w "%{http_code}"` pattern or `--fail` + exit code disambiguation), `jq_parse_error`, `empty_body`. Aggregate counter is what's compared to threshold; the breakdown is informational only.
- **D-10: Threshold semantics.** Lifetime failure-rate cap, default `0.01` (1% of expected rows = 864 missed rows out of 86400 in a 24h soak). Configurable via env var `SOAK_FAIL_RATE_THRESHOLD`. Threshold is evaluated only after `MIN_SAMPLES_BEFORE_EVAL=60` rows of expected wall-clock progress (avoids spurious abort in the first minute when one transient failure = 100% rate). Evaluated once per second after the sleep.
- **D-11: Counter persistence + sentinel.** Sidecar TSV file at `${CAPTURE_DIR}/soak-capture-errors.tsv` with columns: `t_wall \t failure_mode \t last_curl_exit \t last_message`. NOT a sentinel NDJSON row — keeps `soak-capture.ndjson` schema clean for `soak_summary_aggregate.py` consumers. Final summary line on abort goes to stderr.
- **D-12: Tests.** Pytest with a fake `curl`/`jq` shim on PATH that injects a configurable failure schedule (one transient → continues; sustained → aborts above threshold). Mark slow tests `@pytest.mark.slow` with truncated `SOAK_DURATION_SEC` for CI.

### HRDN-03 — Legacy gate cleanup: **retire, sweep all 5 sites**

- **D-13: Retire `TestV142WatchdogRegression` entirely** rather than rewrite. The class exists to pin the transition-cycle artifact's value; once `secondary_gate_legacy` is gone, the contract it pinned no longer exists. CHANGELOG already promised "drops in v1.44" — keep that promise literally.
- **D-14: Replace with one positive-removal contract test.** New test asserts `aggregate_watchdog()` returns a dict whose key-set is exactly `{"secondary_gate_completed_window"}` (no legacy key, no extras) and that the top-level summary dict similarly omits `secondary_gate_legacy`. Lives in `tests/test_phase_204_watchdog.py` (file kept, class retired, one new contract class added) so the test-file rename isn't needed.
- **D-15: Sweep all 5 sites in one plan/commit (Wave atomic):**
  1. `scripts/soak_summary_aggregate.py` — drop `legacy_block` computation, drop the `secondary_gate_legacy` key from `aggregate_watchdog()` return (line ~377), drop the top-level summary mirror (line ~476), drop the "Replaces secondary_gate_legacy" comment fragment (line ~360) or rewrite it as past-tense provenance.
  2. `tests/test_phase_204_watchdog.py` — retire `TestV142WatchdogRegression`, retire any other test that asserts `secondary_gate_legacy` presence, add the positive-removal contract test.
  3. `tests/test_phase_204_replay.py` — line 53-55 assertions of `secondary_gate_legacy` removed (or inverted to assert absence — pick whichever keeps the test's intent).
  4. `docs/SOAK_HARNESS.md` — lines 175-207 section deleted; brief past-tense note in the "Version history" area pointing to v1.43 → v1.44 transition. No dangling references in nav/TOC.
  5. `CHANGELOG.md` — line 29 references the legacy key as "drops in v1.44"; convert to a past-tense v1.44 entry: "`secondary_gate_legacy` removed end-to-end; completed-window dual gate is now the sole watchdog secondary signal."

### Plan slicing (Claude's discretion)

- **D-16: Plan-per-requirement, except HRDN-03 is one atomic plan.** Recommend 4 plans for the planner: `207-01` HRDN-01, `207-02` HRDN-02, `207-03` HRDN-03 (all 5 sites atomic), `207-04` HRDN-04 (docs-only). Then a `207-05` SAFE-09 phase-boundary verification plan (zero `src/wanctl/` diff confirmed). Planner has final say on slicing — this is a recommendation, not a constraint.

### Claude's Discretion (user explicitly delegated)

The user invoked discuss-phase, was offered four gray areas, and replied "you decide." All decisions D-01..D-16 above are Claude's calls anchored to:
1. Lowest-risk closeout per phase-boundary SAFE-09 invariant.
2. Phase 209's closeout commit cohesion (don't spread mechanical rebadging across phases).
3. Existing v1.43 evidence + roadmap deferral structure (T17(b) for HRDN-04 deepwork).
4. The user's stated preferences in CLAUDE.md ("conservative changes, minimal control-path edits, verify before mutating").

User should review and override any of D-01..D-16 by editing this CONTEXT.md before `/gsd-plan-phase 207` resumes.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase / milestone planning
- `.planning/ROADMAP.md` §"Phase 207" — phase goal, success criteria, requirement coverage, cross-cutting notes
- `.planning/REQUIREMENTS.md` §"HRDN — Soak / harness hardening" — requirement IDs HRDN-01..04 with current contract
- `.planning/milestones/v1.43-ROADMAP.md` §82-83 (WR-01/WR-02 waivers), §149 (CALIB-02 YAML-promotion TODO origin), §92-111 (CALIB-01/02/03/04 history)
- `.planning/v1.43-CLOSEOUT-PLAYBOOK.md` §Step 2 + §142-179 (CALIB-02 re-evaluation + gate-key history)
- `.planning/v1.44-THESIS-DRAFT.md` — v1.44 cross-cutting thesis (read for milestone-level scope)

### HRDN-01 (source-diff verifier)
- `scripts/check-safe07-source-diff.sh` — current verifier; HRDN-01 patches into this file
- `src/wanctl/__init__.py` — version-bump tolerance reference (current `__version__ = "1.43.0"`)

### HRDN-02 (soak-capture transient tolerance)
- `scripts/soak-capture.sh` — current 24h capture harness; HRDN-02 patches into this file
- `docs/SOAK_HARNESS.md` — per-row NDJSON schema (must not break)
- `scripts/soak_summary_aggregate.py` — downstream consumer of `soak-capture.ndjson`; verify schema unchanged

### HRDN-03 (legacy gate cleanup)
- `scripts/soak_summary_aggregate.py` lines 290 (`aggregate_watchdog`), 360 (legacy comment), 377 (legacy_block return), 476 (top-level summary mirror)
- `tests/test_phase_204_watchdog.py` — `TestV142WatchdogRegression` class to retire; sibling tests to audit
- `tests/test_phase_204_replay.py` lines 53-55 — additional legacy-key assertion to remove
- `docs/SOAK_HARNESS.md` lines 175-207 — `secondary_gate_legacy` section to delete
- `CHANGELOG.md` line 29 — "drops in v1.44" promise to fulfill in past-tense

### HRDN-04 (CALIB-02 YAML decision)
- `scripts/calib_02_threshold.json` — current operator-approved threshold artifact (threshold 175, gate_column by_cause.dwell_hold)
- `scripts/soak_summary_aggregate.py:50-72` — current `load_calib_02_constants()` loader + fail-closed fallback
- `src/wanctl/check_config_validators.py` lines 48-79 — `continuous_monitoring.upload.*` allowlist (where a YAML key WOULD have lived if HRDN-04 routed YES)
- `.planning/phases/204-d-14-successor-recalibration-calib/204-CALIB-02-OPERATOR-APPROVAL.md` — operator approval artifact referenced by the JSON
- `CHANGELOG.md` §1.43.0 — for past CALIB-02/03/04 entries that the v1.44 entry should be consistent with

### SAFE-09 invariant (every phase boundary)
- `.planning/ROADMAP.md` §"Closeout invariants" — SAFE-08 / SAFE-09 contract
- `scripts/check-safe07-source-diff.sh` — verifier (post-HRDN-01) used for phase-boundary check

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **`scripts/check-safe07-source-diff.sh`** — already has the structure for a clean exit-code contract (0 OK, 1 violation, 2 usage error). HRDN-01 just adds a dirty-tree pre-check before the existing committed-diff check.
- **`scripts/soak_summary_aggregate.py::load_calib_02_constants()`** — already fail-closed (threshold=0 fallback). The pattern is the right shape; HRDN-04 NO route preserves it unchanged.
- **`scripts/soak_summary_aggregate.py::aggregate_watchdog()`** — well-isolated function; legacy-block removal is local.
- **Pytest fixture pattern from v1.43 Phase 204** — soak fixture testing already uses pyfakefs + subprocess.run; HRDN-02 tests can follow the same approach with a fake `curl`/`jq` shim.

### Established Patterns
- **JSON-file convention for operator-approved knobs** — `scripts/calib_02_threshold.json` is the precedent. Fail-closed loader, approval-artifact link baked into the JSON, gate_column explicitly named. HRDN-04 NO route validates and extends this pattern.
- **SAFE-N invariant verifier scripts** — `check-safe07-source-diff.sh` is the template; future SAFE-N closeouts (Phase 209) will adapt the same shape.
- **Phase-boundary checks per ROADMAP** — every v1.44 phase verifies SAFE-08 + SAFE-09 at close; the verifier IS the gate. HRDN-01 makes that gate trustworthy.

### Integration Points
- `soak-capture.sh` writes to NDJSON consumed by `soak_summary_aggregate.py`. NDJSON schema must not break. Sidecar TSV for errors (D-11) keeps NDJSON untouched.
- `aggregate_watchdog()` return shape is consumed by the top-level `aggregate_soak()` (line 462) which mirrors `secondary_gate_legacy` into the summary dict (line 476). Both must change atomically (D-15).

</code_context>

<specifics>
## Specific Ideas

- HRDN-02 tolerance threshold default `0.01` (1%) is conservative — even a flaky network producing 86 missed rows out of 86400 is operationally acceptable for a 24h soak whose statistics use p99 of completed-window counts.
- The sidecar TSV (D-11) doubles as an artifact for the v1.43-style operator-approval workflow: if a soak run hits 0.5% transient failures, the operator can read the breakdown to decide whether to re-soak.

</specifics>

<deferred>
## Deferred Ideas

- **T17(b) CALIB-02 YAML knob shape evaluation** — REQUIREMENTS.md "Future Requirements"; gated on SEED-005 outcomes. Deferred from HRDN-04 NO route (D-01).
- **SAFE-09 verifier rebadge + ATT-config whitelist mode** — Phase 209 owns; HRDN-01 stays surgical (D-04, D-06).
- **Storage-hygiene CAKE tin skip-on-unchanged consumer audit (T6/T7)** — REQUIREMENTS.md "Future Requirements"; orthogonal to Phase 207 scope.
- **SEED-005 conservative UL tuning sweep** — REQUIREMENTS.md "Future Requirements"; gates T17(b) which gates the deep version of HRDN-04.

</deferred>

---

*Phase: 207-soak-harness-hardening-v1-43-closeout-routed*
*Context gathered: 2026-05-15 via /gsd-discuss-phase (user delegated decisions)*
