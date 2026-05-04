# Phase 200 Retrospective: Per-Direction RTT Bloat Thresholds

**Phase outcome:** Hypothesis tested in production, REJECTED. v1.41 binary rolled back to v1.40 baseline; gap-closure phase required.
**Plans completed:** 5 of 8 (Plans 01-05 shipped to repo; Plan 06 closed FAIL; Plans 07-08 blocked).
**Time-on-phase:** ~10 days planning + ~2.5 hours production deploy/canary/rollback (2026-04-23 → 2026-05-03).

## What Was Built

- D-03 fix: per-key presence flags for upload_target_bloat_ms / upload_warn_bloat_ms (Codex pre-review catch).
- SAFE-05 v1.41 count baseline (warn=12, target=14).
- SAFE-06 startup unknown-config-key warnings.
- v1.41.0 version bump + Spectrum YAML D-05 settings + restart-required migration docs.
- Saturation canary tooling (`scripts/phase200-saturation-canary.sh` + env template).
- Plan 06 deploy machinery: byte-identity fingerprint check, D-06 INFO-line journal grep, D-07 saturation canary gate, D-10 rollback protocol.

## What Was Tested in Production

- **Hypothesis:** raising Spectrum UL `target_bloat_ms` 15 → 42 ms and `warn_bloat_ms` 75 → 105 ms (per-direction thresholds independent of DL globals) prevents UL collapse-to-floor on Spectrum DOCSIS upload at saturation.
- **Result:** REJECTED. Saturation canary recorded 122 UL collapse-to-floor events in 900s loaded window (≈1 every 7.4s). Bimodal oscillation pattern: 53% at ceiling (18 Mbps), 14% at floor (8 Mbps), 33% intermediate decay; 59% YELLOW state, 7% RED, 35% GREEN.
- **Evidence file:** `.planning/phases/200-per-direction-rtt-bloat-thresholds/canary/20260503T215734Z/`.

## What Worked

- **D-07/D-10 design:** the deploy gate machinery held under all three failure modes encountered today — logger bug (Attempt 1 ABORT), canary script bug (Attempt 2 sub-attempt 1 ABORT), eventual hypothesis FAIL. Each failure triggered the documented response, not ad-hoc improvisation. This is the gold-standard outcome for a deploy gate: it caught real production-only bugs that smoke checks couldn't.
- **Byte-identity fingerprint deploy verification:** caught nothing this session (the rsync was clean both times) but established a stronger contract than `deploy.sh::verify_deployment` alone.
- **Pre-deploy snapshot tarball + D-10 rollback protocol:** rolled back twice in ~30 seconds each time; both rollbacks restored production cleanly with `is-active=active` and `/health upload state=GREEN` verified.
- **Operator-driven gating at Tasks 1 & 2:** keeping production deploy commands under human control (per CLAUDE.md "stability > safety > clarity > elegance") meant Claude never issued a destructive command without explicit approval. Plan integrity preserved across two attempts.
- **Codex pre-review catch on D-03:** the value-derived `_upload_thresholds_explicit` flag would have shipped a real bug; Codex caught it before plan 01 closed. Per-key presence-based flag is the correct design.
- **Codex stop-time review catch on canary env drift:** after the `dd67493` env-var fix landed and the canary FAIL closeout was committed, Codex stop-time review caught that env-var-driven floor without a deployed-YAML cross-check is open to false-PASS via stale env values. Fixed at `43838f4` with an SSH-based YAML probe in preflight. Two-AI review found a regression that single-AI review and operator review both missed.

## What Was Inefficient (Four Plan 0X Verification-Surface Bugs)

All four were caught **only** by real production contact or post-fact second-AI review — none by upstream Plan 0X smoke checks. Common pattern: smoke checks ran against JSON/YAML fixtures or invoked `--help`, never against a live `/health` endpoint, a running daemon's journal, or the actual deployed YAML.

| # | Plan | File | Bug | Fixed at |
|---|---|---|---|---|
| 1 | Plan 01 Task 2 | `src/wanctl/wan_controller.py:440` | Used `logging.getLogger(__name__)` (module logger, no handlers in production); D-06 verification grep silently dropped. | `417e2b9` |
| 2 | Plan 05 | `scripts/phase200-saturation-canary.sh:217-219, 257` | Asserted `/health.wans[].upload.{floor_mbps, ceiling_mbps}` — fields that do not exist; `/health` carries runtime state only, not config. | `dd67493` |
| 3 | Plan 05 | `scripts/phase200-saturation-canary.sh::summarize_baseline` | Looks for `.wans[0].rtt.baseline_rtt_ms` but `/health` exposes it at `.wans[0].baseline_rtt_ms` (no `.rtt` wrapper). Verdict unaffected (RTT was advisory) but RTT baseline evidence was lost. | (not yet fixed; tracked) |
| 4 | Plan 05 / `dd67493` regression | `scripts/phase200-saturation-canary.sh` env-var-driven floor source | Env vars are not fail-closed against operator drift: stale `PHASE200_UL_FLOOR_MBPS` would silently produce false-PASS verdicts because the floor-collapse selector compared `current_rate_mbps` against the wrong number. Today's run was unaffected (env=8 matched YAML=8 by manual check), but the gate was open to drift. | `43838f4` |

Bug 4 is structurally interesting: the `dd67493` fix for bug 2 (replace nonexistent `/health` fields with operator env vars) created a new false-PASS path. The real fix is "env vars as declared expectation + cross-check against deployed YAML" — preserving operator clarity AND making the gate fail-closed. The remediation added a required `PHASE200_REMOTE_YAML_SSH` env var and an SSH-based YAML probe in preflight that ABORTs on any mismatch.

## Patterns Established (carry into future phases)

- **Smoke checks for verification surfaces must include at least one real-system probe**, not just JSON/YAML fixtures. A new INFO log line should be smoke-tested by starting a daemon with the new config and grepping the *actual* journal. A new `/health` field should be smoke-tested by curl'ing the *actual* endpoint. JSON fixtures encode the author's mental model, not what the production system emits.
- **Module-scope `logging.getLogger(__name__)` is unsafe for production INFO/WARNING in this project**. Production wires only the per-WAN named logger (`cake_continuous_<wan>`); all other loggers drop records. Future code that needs journal visibility should use `self.logger` (the per-WAN logger passed in via constructor) or be explicitly wired in `setup_logging`.
- **`/health.wans[].{download,upload}` carries runtime state only**, not config. Floor / ceiling / threshold values must come from a different source (env var, YAML reader, or operator-supplied parameter). Adding config fields to `/health` requires a payload-shape change that CLAUDE.md flags as risky.
- **Bimodal sample distribution under controller load is a stronger signal than any single metric**: 53% ceiling / 14% floor / 33% transitional reveals oscillation, which a mean or median would average away. Future canary-style gates should always report distribution, not just verdict.
- **Operator-supplied parameters that gate verdicts must be cross-checked against the deployed system at preflight**, not trusted on declaration. "Trust the operator's env file" is not fail-closed. For control-system gates, the canonical pattern is: operator declares expectation as env var → preflight reads the deployed YAML / `/health` / journal and ABORTs on mismatch. Captured in `dd67493` → `43838f4` regression cycle.

## Key Lessons

1. **Smoke checks are not verification.** Three plans this phase shipped with smoke checks that "passed" but missed bugs that production-contact found in seconds. Treat smoke as syntax/shape sanity only; require at least one live-system probe before accepting a plan as done.
2. **The per-direction-thresholds hypothesis was the wrong hypothesis.** The data shows UL queue delay during DOCSIS saturation routinely exceeds 200-500 ms regardless of shaping, because wanctl's 18 Mbit ceiling is barely below provisioned upstream rate, leaving no shaping headroom. The fix is a different control model (DOCSIS-aware UL congestion control with a setpoint well below ceiling), not wider thresholds.
3. **Failed hypotheses still produce knowledge.** The 122-collapse evidence file and the bimodal distribution finding are the seed for Phase 201's design. Phase 200 wasn't wasted; it ruled out the simplest fix and quantified the gap to the right one.
4. **Side-discoveries are real findings.** Spectrum had ALL alerting silently disabled since 2026-04-17 due to a missing `severity` field. Surfaced only because every restart this session emitted the disable warning. Fixed in repo at this phase close; quick task `260503-cfs` tracks the production YAML edit.

## Cross-Reference

- DEPLOY-LOG.md: full operator-keyed Plan 06 timeline, both attempts, FAIL verdict, rollback record, candidate gap-closure directions.
- 200-06-SUMMARY.md: skeleton with TBD sections (still need to flip from TBD to FAIL-branch concrete in a follow-up edit).
- Quick task `.planning/quick/260503-cfs-fix-spectrum-alerting-severity/260503-cfs-PLAN.md`: side-discovery alerting fix.
- Phase 201 seed `.planning/phases/201-docsis-aware-ul-congestion-control/201-CONTEXT.md`: gap-closure direction with 122-collapse evidence reference.

## Gap-Closure Cycle (Plans 09-15)

### What worked

- The hypothesis-first Plan 200-09 flow kept the production-control change behind a BLOCKING operator approval checkpoint, matching the project priority of stability before elegance.
- Splitting WR-01 / WR-02 / WR-03 into separate Wave-1 plans (200-11/12/13) reduced wall-clock cost without crossing file scopes.
- Codex cross-AI review in `200-REVIEWS.md` caught the original file-target error (UL decay lives in `queue_controller.py`, not `wan_controller.py`) and surfaced the missing R5 YAML-only YELLOW hold as the conservative remediation path; both findings shaped the reviews-mode revision.
- The Plan 200-11 jq path fix proved itself live in Plan 200-14 by populating `pre_baseline_rtt_ms=21.7` and `post_baseline_rtt_ms=22.23` in `canary/20260504T133207Z/verdict.json`.
- The fail-closed deploy protocol held again: Attempt 3 failed the canary, rolled back via `/opt/wanctl-prephase200-gap-20260504T132936Z.tar.gz`, and correctly skipped the 24h soak.

### What did not work / what was harder than expected

- The approved R5+R3 branch was insufficient to satisfy VALN-06. Attempt 3 improved the loaded-window floor-hit count from 122 to 4, but the contract requires zero floor hits, so the canary still failed.
- The large improvement is operationally meaningful but not shippable evidence. Plan 200-15 therefore closes the phase as `gaps_found`, not passed, verified, or partially verified.
- Because the canary failed, no 24h soak ran; the soak watchdog remains unexercised rather than failed with data.

### Lessons for v1.42

- DOCSIS-aware UL congestion mode remains the likely v1.42 candidate if the remaining failure is dominated by insufficient shaping headroom or modem/CMTS queue behavior rather than simple YELLOW decay.
- Per-direction `/health` telemetry is more attractive after Plan 200-14: explicit UL suppression and floor-hit counters would have shortened analysis of the remaining 4 floor samples.
- Cross-AI review before implementation is high-leverage on production-control work. Codex caught the file-target error, missing R5 option, and later the risky hybrid `verified-with-soak-gap` closeout state before archive.
- Future gap-closure plans should treat “materially improved but still failed” as a distinct branch: preserve the improvement evidence, but do not dilute acceptance criteria or mark requirements satisfied.

### Cross-milestone reference

- The deferred todo `.planning/todos/pending/2026-04-24-resolve-att-cake-primary-canary-after-phase-196.md` remains related operational context for v1.42 planning because ATT cake-primary validation is still gated on Phase 191 closure while Spectrum work continues to generate production-canary debt.

## Final Closure (2026-05-04)

**Operator decision:** VALN-06 is **deferred to Phase 201 (`docsis-aware-ul-congestion-control`) as an inherited blocking requirement**. Phase 200 / v1.41 closes as `gaps_found` via operator escalation rather than running a second gap-closure cycle.

### Decision rationale

Two findings drove the escalation:

1. **The hypothesis was already diagnosed insufficient by Phase 200's own retro.** The "What did not work" subsection above states that the residual failure regime — bimodal ceiling/floor oscillation under saturated DOCSIS upload — is dominated by shaping headroom (CMTS-side queue filling before wanctl's qdisc can absorb bufferbloat), not by threshold geometry. Wider thresholds slow the descent but do not stop the controller from reaching the floor when the upstream queue is already deep. This is the architectural conclusion the retro reached after Plans 09-15 ran.

2. **Marginal returns on further Phase 200 work were judged low.** Plans 200-09 -> 200-14 reduced loaded-window UL floor hits from 122 (Attempt 2, 2026-05-03) to 4 (Attempt 3, 2026-05-04 canary `20260504T133207Z`) — a 96.7% improvement under the per-direction-thresholds + R5 + R3 stack. The deploy gate is fail-closed at zero, so the canary still failed and rolled back via `/opt/wanctl-prephase200-gap-20260504T132936Z.tar.gz` at `2026-05-04T13:49:19Z`. The remaining 4 hits live in a regime where additional threshold or decay tuning is unlikely to reach zero without changing the control model. Phase 201 is the right scope for that change; it already exists as a seed and is loaded with the 122-collapse evidence as its design input.

### What was not attempted

- **No second Phase 200 remediation cycle.** The plan to enumerate further candidate causes (additional R-options, lower ceiling, integral-of-RTT) was not undertaken. A second cycle would consume planning + production-canary cost while testing variants of the hypothesis that the retro already rejected as architecturally insufficient.
- **No production binary change.** Spectrum remains on the v1.40 binary post the 2026-05-04T13:49:19Z rollback. The v1.41 YAML keys (`continuous_monitoring.upload.target_bloat_ms=42`, `warn_bloat_ms=105`, `consecutive_yellow_decay_clamp=40`, `factor_down_yellow=1.0`, `ceiling_mbps=18`) remain on disk under `/etc/wanctl/spectrum.yaml` and are inactive under the rolled-back v1.40 binary, but they MUST be reconciled before any future Spectrum deploy or service restart that uses a binary which re-recognizes those keys. A future binary that consumes them would reactivate rejected-hypothesis state silently. This is not a "harmless" condition — it is rejected-hypothesis state sitting in production config and is a real operational risk that Phase 201's PLAN must address with a predeploy gate (inspect `/etc/wanctl/spectrum.yaml` for v1.41-only keys; reconcile or fail closed).
- **No re-cut of v1.41.** The 1.41.0 version was already minted in `pyproject.toml`, `src/wanctl/__init__.py`, and `docker/Dockerfile`, and the CHANGELOG entry stays. The version is recorded in history as the milestone that proved the per-direction-thresholds hypothesis insufficient. v1.42 will pick up the binary again under Phase 201.

### VALN-06 routing

- **Owning phase:** Phase 201 (`docsis-aware-ul-congestion-control`).
- **Inheritance status:** **Inherited blocking requirement.** Phase 201 SPEC and PLAN must carry VALN-06 forward — it cannot be silently dropped during 201 scoping. Future Phase 201 planning that fails to enumerate VALN-06 in its requirements list MUST be treated as a planning defect.
- **Inheritance trail:** `200-VERIFICATION.md` frontmatter `closure: deferred-to-phase-201` + `inherited_as: blocking_requirement` -> `REQUIREMENTS.md` row `Deferred -> Phase 201 (inherited blocking requirement)` -> `201-CONTEXT.md` `## Inherited Requirements` block.
- **Direct evidence pointer:** `.planning/phases/200-per-direction-rtt-bloat-thresholds/canary/20260504T133207Z/verdict.json` records the Attempt 3 verdict (`verdict: fail`, `ul_floor_hits_during_load: 4`, `ul_floor_threshold_hit: true`, baseline RTT bookends populated).
- **Closure shape:** Phase 201 will produce its own canary verdict against its own (DOCSIS-aware) control model. VALN-06 closes when that canary passes with zero loaded-window floor hits AND its 24h soak watchdog passes; the same fail-closed gate applies. Phase 201 does NOT inherit Phase 200's "must use 18 Mbit ceiling" or "must use 42/105 ms thresholds" — those were Phase 200's hypothesis-under-test, not the requirement.

### What ARB-05, SAFE-06, DOCS-03 closed

These three Phase 200 requirements remain satisfied and are not affected by the deferral:

- **ARB-05** (per-direction UL thresholds with absent-key fallback and per-key explicit-presence flags) shipped in Plan 200-01, validated by Plan 200-02 and Plan 200-12.
- **SAFE-06** (validator audibly warns on unknown `continuous_monitoring.*` keys) shipped in Plan 200-03 and is exercised by tests in `tests/test_autorate_config.py::TestSafe06UnknownKeyWarning`.
- **DOCS-03** (CHANGELOG.md and docs/CONFIGURATION.md document the new keys plus restart-required migration) shipped in Plan 200-04 and Plan 200-13.

The deferral is scoped to VALN-06 only.

### Open advisory items (do not block VALN-06's Phase 201 path)

- `200-REVIEW.md` WR-01 (Dockerfile unquoted shell-form pip constraints) and IN-01 (stale top-of-file comment) remain advisory. They have no controller-path impact.
- `200-REVIEW.md` WR-02 (canary script Python/PyYAML dependency precheck) remains advisory; Attempt 3's canary did produce a verdict, so this did not affect VALN-06 evidence.
- These can become quick tasks if the operator wants them closed; they are not on the VALN-06 critical path.

### Non-controller mitigation option

While Phase 201 is being designed and shipped, the Spectrum production UL hysteresis storm (5 -> 15 -> 31 suppressions/60s, observed 2026-04-29 onward and again now post-rollback) is operational debt. A non-controller mitigation — e.g., manually lowering Spectrum's deployed UL ceiling well below provisioned upstream rate via YAML-only edit, no code change, AND/OR reverting prod `/etc/wanctl/spectrum.yaml` to its v1.40-shape values to remove the rejected-hypothesis keys — is available as a quick task if the suppression rate becomes operationally painful before Phase 201 ships. Plan 200-16's Task 1 explicitly exposes this as Branch B of the operator countersignature decision. That is a separate operator decision and is **not** a Phase 200 / 201 plan; it is a quick-task mitigation tracked outside the milestone graph.

### Cross-milestone reference

- `.planning/todos/pending/2026-04-24-resolve-att-cake-primary-canary-after-phase-196.md` — the deferred ATT cake-primary canary is unrelated to VALN-06 (different WAN, different control mode) but lives in the same operational neighborhood; v1.42 planning may want to consolidate Spectrum + ATT control-mode work into a single milestone if the timing aligns.

### Lessons reinforced for v1.42

- **A retro that diagnoses the hypothesis as architecturally wrong is a stronger signal than further tuning.** When the retro itself says "the fix is a different control model, not wider thresholds," operator escalation to the next-architecture phase is the correct response, not a second gap-closure cycle on the rejected hypothesis.
- **Diminishing returns under fail-closed gates.** A 96.7% improvement (122 -> 4 floor hits) is operationally meaningful but is not shippable evidence under a zero-hit gate. Future plans involving fail-closed deploy gates should treat "materially improved but still failed" as a distinct, terminal branch — not as license to relax the gate.
- **Operator escalation as a first-class closure path.** ROADMAP.md explicitly allowed operator escalation as a VALN-06 closure path. Treating it as a first-class option (with its own traceability seal — this plan) is cleaner than implicit deferral via inactivity.
- **Rejected-hypothesis state in prod config is real risk, not "harmless."** v1.41 YAML keys on `/etc/wanctl/spectrum.yaml` are inactive under v1.40 but would silently reactivate under any future binary that recognizes them. Future deferrals that leave config-side state behind should mandate a successor-phase predeploy gate, not assume binary rollback alone is sufficient.

---
*Phase: 200-per-direction-rtt-bloat-thresholds*
*Retro written: 2026-05-03*
*Status: closed with FAIL outcome; gap-closure → Phase 201*
