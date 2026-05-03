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

## What Was Inefficient (Three Plan 0X Verification-Surface Bugs)

All three were caught **only** when Plan 06 made real production contact. None were caught by upstream Plan 0X smoke checks. Common pattern: smoke checks ran against JSON/YAML fixtures or invoked `--help`, never against a live `/health` endpoint or a running daemon's journal.

| # | Plan | File | Bug | Fixed at |
|---|---|---|---|---|
| 1 | Plan 01 Task 2 | `src/wanctl/wan_controller.py:440` | Used `logging.getLogger(__name__)` (module logger, no handlers in production); D-06 verification grep silently dropped. | `417e2b9` |
| 2 | Plan 05 | `scripts/phase200-saturation-canary.sh:217-219, 257` | Asserted `/health.wans[].upload.{floor_mbps, ceiling_mbps}` — fields that do not exist; `/health` carries runtime state only, not config. | `dd67493` |
| 3 | Plan 05 | `scripts/phase200-saturation-canary.sh::summarize_baseline` | Looks for `.wans[0].rtt.baseline_rtt_ms` but `/health` exposes it at `.wans[0].baseline_rtt_ms` (no `.rtt` wrapper). Verdict unaffected (RTT was advisory) but RTT baseline evidence was lost. | (not yet fixed; tracked) |

## Patterns Established (carry into future phases)

- **Smoke checks for verification surfaces must include at least one real-system probe**, not just JSON/YAML fixtures. A new INFO log line should be smoke-tested by starting a daemon with the new config and grepping the *actual* journal. A new `/health` field should be smoke-tested by curl'ing the *actual* endpoint. JSON fixtures encode the author's mental model, not what the production system emits.
- **Module-scope `logging.getLogger(__name__)` is unsafe for production INFO/WARNING in this project**. Production wires only the per-WAN named logger (`cake_continuous_<wan>`); all other loggers drop records. Future code that needs journal visibility should use `self.logger` (the per-WAN logger passed in via constructor) or be explicitly wired in `setup_logging`.
- **`/health.wans[].{download,upload}` carries runtime state only**, not config. Floor / ceiling / threshold values must come from a different source (env var, YAML reader, or operator-supplied parameter). Adding config fields to `/health` requires a payload-shape change that CLAUDE.md flags as risky.
- **Bimodal sample distribution under controller load is a stronger signal than any single metric**: 53% ceiling / 14% floor / 33% transitional reveals oscillation, which a mean or median would average away. Future canary-style gates should always report distribution, not just verdict.

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

---
*Phase: 200-per-direction-rtt-bloat-thresholds*
*Retro written: 2026-05-03*
*Status: closed with FAIL outcome; gap-closure → Phase 201*
