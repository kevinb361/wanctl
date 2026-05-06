---
phase: 203
slug: target-edge-churn-instrumentation-obsv
status: verified
threats_open: 0
asvs_level: 1
created: 2026-05-06
updated: 2026-05-06
---

# Phase 203 — Security

Per-phase security contract for Target-Edge Churn Instrumentation (OBSV). State B audit: no prior SECURITY.md existed; executed PLAN and SUMMARY artifacts were used as the source register.

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| Operator environment -> `scripts/soak-capture.sh` | Operator-trusted shell input for the soak harness. | `SOAK_TS`, `HEALTH_URL`, `SOAK_DURATION_SEC`, `CAPTURE_DIR` |
| Daemon `/health` endpoint -> capture harness | Read-only JSON over HTTP; same trust boundary as earlier soak evidence scripts. | Public-safe health payload fields |
| Local NDJSON file -> `scripts/soak_summary_aggregate.py` | Operator-trusted local analysis input; no daemon/runtime effect. | Soak capture rows |
| Generator/test code -> checked-in fixtures | Repo-trusted deterministic test fixtures. | Synthetic NDJSON and golden JSON |
| Repo artifacts -> public mirror/docs | Public-safe tracked content. | Docs, changelog, scripts, tests |
| Operator CLI -> SAFE-07 verifier | Operator-trusted git ref input. | Git ref / environment override |

---

## Threat Register

| Threat ID | Category | Component | Disposition | Mitigation | Status |
|-----------|----------|-----------|-------------|------------|--------|
| T-203-01-01 | Tampering | `SOAK_TS` / `CAPTURE_DIR` path construction | mitigate | `scripts/soak-capture.sh` uses strict shell mode, required `SOAK_TS`, quoted `CAPTURE_DIR`, and quoted append path. Operator input remains same-trust-domain. | closed |
| T-203-01-02 | Information Disclosure | Hardcoded endpoints in `scripts/soak-capture.sh` | mitigate | `HEALTH_URL` is mandatory with no default; public-safe grep/verification found no Phase 203 hardcoded endpoints. | closed |
| T-203-01-03 | Tampering | JQ projection extraction drift | mitigate | `tests/test_phase_203_capture_projection.py` extracts the projection from the script and raises on layout desync. | closed |
| T-203-01-04 | Denial of Service | SIGTERM during NDJSON append | accept | Accepted low risk: at most one dropped 1-second sample in an offline 24h soak. | closed |
| T-203-01-05 | Repudiation / drift | Capture script diverges from test expectations | mitigate | Projection tests use the script body as the single source of truth. | closed |
| T-203-01-06 | SAFE-07 invariant violation | Any `src/wanctl/` change | mitigate | SAFE-07 script and explicit committed/staged/unstaged `src/wanctl/` diff checks passed. | closed |
| T-203-02-01 | Tampering | NDJSON input rows | accept | Accepted low risk: offline operator-trusted input; `json.loads` rejects malformed rows without execution. | closed |
| T-203-02-02 | Information Disclosure | `scripts/soak_summary_aggregate.py` | accept | Accepted low risk: stdlib-only local analysis script; no network, shell-out, auth, or env-var secret surface. | closed |
| T-203-02-03 | Denial of Service | Histogram integer overflow | accept | Accepted low risk: Python integers are arbitrary precision and real RTT deltas are bounded far below pathological sizes. | closed |
| T-203-02-04 | Repudiation / drift | Synthetic fixture diverges from generator | mitigate | Generator drift test re-runs the generator and asserts byte-identical fixture output. | closed |
| T-203-02-05 | Repudiation / drift | Python aggregator drops v1.42 diagnostic behavior | mitigate | v1.42 replay regression verifies diagnostic_distribution math against historical soak evidence. | closed |
| T-203-02-06 | SAFE-07 invariant violation | Any `src/wanctl/` change | mitigate | SAFE-07 gate passed; no committed, staged, or unstaged `src/wanctl/` diff found. | closed |
| T-203-02-07 | Tampering | Phase 202 replay import regression | mitigate | Phase slice including `tests/test_phase_202_replay.py` passed. | closed |
| T-203-03-01 | Information Disclosure | `docs/SOAK_HARNESS.md` content | mitigate | Docs use `<host>` placeholders; public-safe verification found no Phase 203 endpoint/IP evidence. | closed |
| T-203-03-02 | Information Disclosure | `CHANGELOG.md` Phase 203 entries | mitigate | Entries name only scripts/schema/REQ IDs; no Phase 203 hardcoded endpoint/IP evidence. | closed |
| T-203-03-03 | Repudiation / drift | Operator misreads schema semantics | mitigate | `docs/SOAK_HARNESS.md` documents cause attribution, histogram interpretation, and upload-only zone axis. | closed |
| T-203-03-04 | Tampering | SAFE-07 verifier bypass | mitigate | `scripts/check-safe07-source-diff.sh` is the explicit reusable closeout gate and was run during verification. | closed |
| T-203-03-05 | Repudiation / drift | Phase 202 close ref rot | mitigate | Script has default `b72b463`, positional/env override, and invalid-ref exit 2. | closed |
| T-203-03-06 | SAFE-07 invariant violation | Any `src/wanctl/` change | mitigate | SAFE-07 gate and extra working-tree checks passed. | closed |
| T-203-03-07 | Tampering | Accidental `phase203_expected_counts` pin block | mitigate | Search found no `phase203_expected_counts`; SAFE-05 pin test was included in passing phase slice. | closed |

---

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---------|------------|-----------|-------------|------|
| AR-203-01 | T-203-01-04 | A SIGTERM during one sample write may lose one second of offline soak evidence; this does not affect daemon behavior or controller safety. | security audit | 2026-05-06 |
| AR-203-02 | T-203-02-01 | NDJSON is operator-trusted local analysis input; malformed rows fail closed through JSON parser errors. | security audit | 2026-05-06 |
| AR-203-03 | T-203-02-02 | Aggregator is local stdlib-only analysis code with no network, shell, auth, or secret boundary. | security audit | 2026-05-06 |
| AR-203-04 | T-203-02-03 | Python arbitrary-precision integers avoid fixed-width overflow; practical RTT delta values are bounded. | security audit | 2026-05-06 |

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-05-06 | 20 | 20 | 0 | gsd-security-auditor |

### Evidence Summary

- `bash scripts/check-safe07-source-diff.sh` passed.
- Explicit committed, unstaged, and staged `src/wanctl/` diff checks were clean.
- `.venv/bin/pytest tests/test_phase_203_capture_projection.py tests/test_phase_203_replay.py tests/test_phase_202_replay.py tests/test_phase_195_replay.py -q` passed with 56 tests.
- Phase 203 public-safe artifact checks found no Phase 203 hardcoded endpoint/IP evidence; whole-file CHANGELOG matches were legacy content outside Phase 203 entries.
- `203-02-SUMMARY.md` and `203-03-SUMMARY.md` report no threat flags; `203-01-SUMMARY.md` has no threat flags section.

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-05-06
