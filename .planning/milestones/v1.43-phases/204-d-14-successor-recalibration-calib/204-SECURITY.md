---
phase: 204
slug: d-14-successor-recalibration-calib
status: verified
threats_open: 0
asvs_level: 1
created: 2026-05-13
updated: 2026-05-13
---

# Phase 204 — Security

Per-phase security contract: threat register, accepted risks, and audit trail for Phase 204 D-14 Successor Recalibration (CALIB).

## Trust Boundaries

| Boundary | Description | Data Crossing |
|---|---|---|
| local dev -> cake-shaper SSH | Operator-driven deploy, soak launch, scp-back, and tmux/systemd-run controls. | Deployment scripts, soak scripts, NDJSON evidence. |
| cake-shaper `/health` -> soak capture | Production `/health` endpoint consumed by soak harness using deployment-bound health URL. | Operational health JSON and derived NDJSON rows. |
| soak capture -> aggregator -> verdict | Committed soak evidence feeds Python aggregation and CALIB verdict artifacts. | Operational metrics, completed-window counts, gate values. |
| operator decision -> committed artifact | CALIB-02 approvals and CALIB-04 verdict branches are captured as discrete files. | Threshold decisions and rationale. |
| approval artifact -> JSON constants | `204-CALIB-02-OPERATOR-APPROVAL.md` is mirrored into `scripts/calib_02_threshold.json`. | Gate statistic, threshold, headroom, gate column. |
| SAFE-07 gate -> ship readiness | Source-diff helper constrains v1.43 to no controller tuning beyond planned version bump. | Git diff state and closeout decision. |
| closeout artifacts -> milestone state | Verification, roadmap, requirements, state, changelog, and PROJECT updates define shipped state. | Planning metadata and archive readiness. |

## Threat Register

| Threat ID | Category | Component | Disposition | Mitigation / Evidence | Status |
|---|---|---|---|---|---|
| T-204-01-01 | Tampering | `scripts/deploy.sh` rsync target | mitigate | Snapshot A rollback evidence plus SAFE-07 source-diff gate in `204-01-SUMMARY.md` and `204-VERIFICATION.md`. | closed |
| T-204-01-02 | Denial of Service | `wanctl@spectrum.service` restart | accept | Standard production restart risk; Snapshot A rollback path and soak-monitor/canary checks documented. | closed |
| T-204-01-03 | Information Disclosure | Snapshot files with `/etc/wanctl/spectrum.yaml` | accept | Stored on cake-shaper in the existing production trust zone; no new exposure. | closed |
| T-204-01-04 | Repudiation | Operator approval | mitigate | `204-01-DEPLOY-VERIFICATION.md` records timestamped operator approval and verdict. | closed |
| T-204-02-01 | Tampering | `scripts/soak_summary_aggregate.py` distribution extension | mitigate | Golden/replay tests and Phase 202/203/204 regression slices passed. | closed |
| T-204-02-02 | Information Disclosure | CALIB-01 soak NDJSON | accept | Operational metrics only; existing committed-evidence precedent; no secrets or PII. | closed |
| T-204-02-03 | Denial of Service | 24h CALIB-01 soak job | accept | Same production soak pattern as prior phases; tmux plus systemd-run kill timer. | closed |
| T-204-03-01 | Repudiation | CALIB-02 operator approval | mitigate | Distinct committed approval artifact `204-CALIB-02-OPERATOR-APPROVAL.md`. | closed |
| T-204-03-02 | Tampering | `scripts/calib_02_threshold.json` drift | mitigate | Artifact/JSON mirror checks; final JSON threshold `175` matches approval. | closed |
| T-204-03-03 | Information Disclosure | Operator justification text | accept | Public-safe operational rationale; no secrets or PII. | closed |
| T-204-04-01 | Tampering | CALIB-02 JSON constants | mitigate | Constants committed with approval artifacts and checked by Plan 204-04/204-10 gates. | closed |
| T-204-04-02 | Tampering | `aggregate_watchdog()` Python port | mitigate | `tests/test_phase_204_watchdog.py` verifies v1.42 legacy oracle and active threshold behavior. | closed |
| T-204-04-03 | Information Disclosure | `soak-summary.json` watchdog output | accept | Operational aggregate metrics only; existing `.planning/` evidence pattern. | closed |
| T-204-04-04 | Repudiation | Approval flow consumed by aggregator | mitigate | Approval remains in `204-CALIB-02-OPERATOR-APPROVAL.md`; aggregator consumes mirrored JSON. | closed |
| T-204-05-01 | Tampering | CALIB-04 `soak-summary.json` gate fields | mitigate | Aggregator oracle-tested; final verdict fields match `soak/20260512T004208Z/soak-summary.json`. | closed |
| T-204-05-02 | Repudiation | CALIB-04 verdict | mitigate | `204-05-CALIB-04-SOAK-VERDICT.md` records timestamp, soak TS, superseded soaks, numerics, and verdict. | closed |
| T-204-05-03 | Denial of Service | 24h CALIB-04 soak window | accept | Same risk profile as Plan 204-02; bounded by tmux/systemd-run pattern. | closed |
| T-204-05-04 | Information Disclosure | CALIB-04 soak NDJSON | accept | Operational metrics only; no PII; existing committed precedent. | closed |
| T-204-06-01 | Tampering | SAFE-07 `b72b463` reference | mitigate | `scripts/check-safe07-source-diff.sh` exits nonzero if ref is missing and passed final closeout. | closed |
| T-204-06-02 | Repudiation | Closeout decisions | mitigate | Closeout recorded in `204-RETRO.md`, `204-VERIFICATION.md`, `STATE.md`, `ROADMAP.md`, and commits. | closed |
| T-204-06-03 | Information Disclosure | RETRO / VERIFICATION / TODO content | accept | Public-safe planning content; no secrets. | closed |
| T-204-07-01 | Tampering | CALIB-01 boundary-marker projection | mitigate | Capture included `ul_hysteresis_window_start_epoch`; aggregator fails closed on missing marker; corrected evidence has zero missing markers. | closed |
| T-204-07-02 | Repudiation | CALIB-01 rerun outcome | mitigate | New timestamped evidence path `soak/20260509T183037Z/`; old evidence retained as superseded provenance. | closed |
| T-204-07-03 | Denial of Service | 24h CALIB-01 rerun | accept | Same tmux/systemd-run production soak risk pattern. | closed |
| T-204-07-04 | Information Disclosure | CALIB-01 rerun NDJSON | accept | Operational metrics only; no PII. | closed |
| T-204-08-01 | Repudiation | CALIB-02 reevaluation outcome | mitigate | `204-08-CALIB-02-REEVALUATION.md` records branch, material-change table, and threshold history. | closed |
| T-204-08-02 | Tampering | JSON drift from approval artifact | mitigate | JSON threshold/reference mirror final approval and were validated in closeout. | closed |
| T-204-08-03 | Spoofing | Incorrect branch selection | mitigate | Mechanical criterion table documents failed tests and branch decisions; final Branch A continuation is recorded. | closed |
| T-204-09-01 | Tampering | CALIB-04 rerun gate fields | mitigate | `aggregate_watchdog()` tests passed; boundary-marker invariant zero; final summary and verdict agree. | closed |
| T-204-09-02 | Repudiation | CALIB-04 re-execution verdict | mitigate | Verdict frontmatter includes superseded soaks and rerun reason; git log preserves prior FAIL-A and final PASS. | closed |
| T-204-09-03 | Spoofing | PASS declared against stale code | mitigate | Boundary-marker checks and fail-closed aggregator behavior prove post-d44e2fd evidence. | closed |
| T-204-09-04 | Denial of Service | 24h CALIB-04 rerun window | accept | Same bounded production soak pattern as Plan 204-05. | closed |
| T-204-09-05 | Information Disclosure | CALIB-04 rerun NDJSON | accept | Operational metrics only; no PII. | closed |
| T-204-10-01 | Spoofing | Satisfied claim against fail verdict | mitigate | Plan 204-10 blocked on FAIL, then ran only after final `verdict: pass`. | closed |
| T-204-10-02 | Tampering | REQUIREMENTS/ROADMAP flips without evidence | mitigate | Closeout cites gap-closure soaks and verifier report; final verifier passed 6/6. | closed |
| T-204-10-03 | Repudiation | v1.43 ship date | mitigate | `CHANGELOG.md`, `STATE.md`, `ROADMAP.md`, and `PROJECT.md` record final completion date and evidence. | closed |
| T-204-10-04 | Information Disclosure | Closeout artifact content | accept | Public-safe planning metadata; no PII/secrets. | closed |
| T-204-10-05 | Denial of Service | Closeout refresh | accept | No production deploy in closeout. | closed |
| T-204-10-06 | Elevation of Privilege | Source-code scope | accept | No new `src/wanctl/` code beyond planned version bump; SAFE-07 final gate passed. | closed |

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---|---|---|---|---|
| R-204-01 | T-204-01-02 | Production restart risk is standard for deploy validation and bounded by Snapshot A rollback plus monitoring. | operator/GSD | 2026-05-13 |
| R-204-02 | T-204-01-03 | Snapshot files stay in the same production trust zone and do not create a new exposure path. | operator/GSD | 2026-05-13 |
| R-204-03 | T-204-02-02, T-204-05-04, T-204-07-04, T-204-09-05 | Soak NDJSON contains operational metrics only and follows existing committed-evidence precedent. | operator/GSD | 2026-05-13 |
| R-204-04 | T-204-02-03, T-204-05-03, T-204-07-03, T-204-09-04 | 24h production soak windows are required evidence-gathering operations and are bounded by tmux plus systemd-run cleanup timers. | operator/GSD | 2026-05-13 |
| R-204-05 | T-204-03-03, T-204-04-03, T-204-06-03, T-204-10-04 | Approval, aggregate, retro, verification, and closeout artifacts are public-safe operational/planning content with no secrets. | operator/GSD | 2026-05-13 |
| R-204-06 | T-204-10-05, T-204-10-06 | Closeout performed no production deploy and no control-path code changes beyond planned version bump; SAFE-07 verified. | operator/GSD | 2026-05-13 |

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|---|---:|---:|---:|---|
| 2026-05-13 | 39 | 39 | 0 | gsd-security-auditor |

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-05-13
