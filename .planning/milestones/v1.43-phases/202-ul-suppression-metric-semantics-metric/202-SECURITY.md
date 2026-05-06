---
phase: 202
slug: ul-suppression-metric-semantics-metric
status: verified
threats_open: 0
asvs_level: 1
created: 2026-05-06
updated: 2026-05-06
---

# Phase 202 — Security

Per-phase security contract: threat register, accepted risks, and audit trail.

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| Operator -> `/health` HTTP endpoint | Read-only JSON; Phase 202 adds aggregate suppression-counter fields and no new authentication path. | Aggregate integer counters and cause labels (`dwell_hold`, `backlog_recovery`, `other`) |
| Internal controller callsites -> `_record_suppression` | Three in-process suppression callsites update additive per-cause counters in the same trust domain as existing counter increments. | Cause strings and integer counter increments |
| Test suite -> archived NDJSON fixture | Local read-only test fixture under `.planning/milestones/v1.42-phases/...`; no runtime or external input. | Historical `/health` samples used for offline aggregation |
| Test suite -> source tree token scan | SAFE-05 pin tests read `src/wanctl/**/*.py` to detect drift. | Source-code token occurrence counts |
| Operator-readable docs | Public-safe documentation in `CHANGELOG.md` and `docs/CONFIGURATION.md`. | Metric semantics and repo-internal fixture path references |
| Repo-internal planning artifacts | `.planning/REQUIREMENTS.md`, `.planning/ROADMAP.md`, and milestone phase artifacts. | Traceability and fixture-path references |

---

## Threat Register

| Threat ID | Category | Component | Disposition | Mitigation | Status |
|-----------|----------|-----------|-------------|------------|--------|
| T-202-01-01 | Tampering | `_record_suppression` cause arg | mitigate | Closed by cause allowlist/fallback: `queue_controller.py` maps unknown causes to `"other"` before counter updates (`cause not in self._window_suppressions_by_cause`; `cause = "other"`). | closed |
| T-202-01-02 | Information Disclosure | `/health` schema additions | accept | Accepted risk: emitted values are aggregate counters and cause labels only; no PII, secrets, hostnames, or operator-identifying data. | closed |
| T-202-01-03 | Denial of Service | Per-cycle dict math at suppression callsites | accept | Accepted risk: additive O(1) integer-dict updates only; no I/O, logging, alert firing, or network work. Hot-path slice passed with 667 tests and full suite passed. | closed |
| T-202-01-04 | Repudiation / drift | Control-path diff | mitigate | Closed by SAFE-07 evidence: `wan_controller.py` diff empty; Phase 202 verifier found only additive counter/schema instrumentation and no threshold/rate tuning changes. | closed |
| T-202-02-01 | Tampering | Fixture NDJSON | accept | Accepted risk: fixture is in-tree and reviewed by git diff; oracle assertions are tight enough to fail on trivial corruption (`mean ~= 13.9`, p95 `41`, max `124`). | closed |
| T-202-02-02 | Information Disclosure | Test logging | accept | Accepted risk: tests expose aggregate statistics only (`84117` samples, `1331` observable windows, mean/p95/max); no operator-identifying data. | closed |
| T-202-02-03 | Repudiation / drift | Codex oracle citation vs computed value | mitigate | Closed by `tests/test_phase_202_replay.py::aggregate_completed_windows` and oracle constants; verified spot-check matched `13.890308039068369`, p95 `41.0`, max `124`. | closed |
| T-202-03-01 | Tampering / drift | v1.40/v1.41/v1.42 pin dicts | mitigate | Closed by `tests/test_phase_195_replay.py`; Phase 202 verifier confirmed existing pins plus new `phase202_expected_counts` pass. | closed |
| T-202-03-02 | Repudiation | Future auto-bump of failed pins | mitigate | Closed by explicit test comment: drift is a real signal and must be reconciled manually; do not auto-bump. | closed |
| T-202-03-03 | Information Disclosure | Pin counts | accept | Accepted risk: source token counts are integers only and contain no operator-identifying data. | closed |
| T-202-04-01 | Information Disclosure | `docs/CONFIGURATION.md` content | mitigate | Closed by public-safe wording: docs use generic operator phrasing (`your link`) and contain no IPs, hostnames, identities, or secrets. | closed |
| T-202-04-02 | Repudiation / drift | Future operator misreading new fields | mitigate | Closed by locked docs: `docs/CONFIGURATION.md` warns not to use `suppressions_per_min` as a rate and recommends `suppressions_completed_window_count` for watchdog/alert gating. | closed |
| T-202-04-03 | Tampering | Fixture-path correction scope | mitigate | Closed by scoped path corrections: active `.planning/REQUIREMENTS.md` and `.planning/ROADMAP.md` point to the canonical archived fixture path; v1.42 milestone evidence was not modified. | closed |

*Status: open · closed*
*Disposition: mitigate (implementation required) · accept (documented risk) · transfer (third-party)*

---

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---------|------------|-----------|-------------|------|
| AR-202-01 | T-202-01-02 | `/health` additions expose aggregate suppression counts only; no sensitive or operator-identifying data. | PLAN disposition | 2026-05-06 |
| AR-202-02 | T-202-01-03 | Per-cycle counter updates are O(1), in-process, and verified by hot-path/full-suite tests; no new I/O or logging path. | PLAN disposition | 2026-05-06 |
| AR-202-03 | T-202-02-01 | Archived in-tree fixture tampering is adequately controlled by git review plus tight oracle assertions. | PLAN disposition | 2026-05-06 |
| AR-202-04 | T-202-02-02 | Test output contains aggregate statistics only. | PLAN disposition | 2026-05-06 |
| AR-202-05 | T-202-03-03 | Token counts are non-sensitive integers. | PLAN disposition | 2026-05-06 |

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-05-06 | 13 | 13 | 0 | OpenCode secure-phase workflow |

---

## Evidence Checked

| Evidence | Result |
|----------|--------|
| `src/wanctl/queue_controller.py` cause allowlist/fallback | `_record_suppression()` maps unknown causes to `"other"` before updating counters. |
| `src/wanctl/health_check.py` `/health` passthrough | New keys are copied into the common hysteresis section for both upload and download. |
| `tests/test_phase_202_replay.py` oracle | Offline reset-boundary aggregation verifies mean `13.890308039068369`, p95 `41.0`, max `124`. |
| `tests/test_phase_195_replay.py` SAFE-05 pins | v1.43 token pins present; comment blocks prohibit automatic pin bumps. |
| `docs/CONFIGURATION.md` public docs | Warning and per-cycle semantics present; wording is public-safe. |
| `202-VERIFICATION.md` | Phase verifier passed `11/11` must-haves; no human verification gaps. |
| `202-REVIEW.md` | Code review status `clean`; no security findings. |

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-05-06
