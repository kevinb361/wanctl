---
phase: 208
slug: carry-on-quick-tasks-t17a-t9-t12
status: verified
threats_open: 0
asvs_level: 1
created: 2026-05-16
verified: 2026-05-16
---

# Phase 208 Security Verification

**Phase:** 208 — carry-on quick tasks T17a / T9 / T12  
**ASVS Level:** 1  
**Verified:** 2026-05-16  
**Threats Open:** 0  

## Scope

This artifact verifies only the declared Phase 208 threat register. It does not represent a blind vulnerability scan.

## Threat Verification

| Threat ID | Category | Component | Disposition | Status | Evidence |
|-----------|----------|-----------|-------------|--------|----------|
| T-208-01 | Tampering | `aggregate_watchdog()` misconfig false pass | mitigate | CLOSED | `scripts/soak_summary_aggregate.py:311-348` sets `config_reason`, gates `config_ok`, forces bad config to `value=0.0`, `verdict="fail"`, and non-null `reason`; tests at `tests/test_phase_204_watchdog.py:140-185` cover unknown cause, unknown top-level gate, and unsupported statistic. |
| T-208-02 | Denial-of-Service | oversized NDJSON aggregator memory | accept | CLOSED | Accepted risk documented below. Plan acceptance at `208-01-PLAN.md:423-425`; summary threat flags report none at `208-01-SUMMARY.md:118-120`. |
| T-208-03 | Information Disclosure | aggregator stack trace leaks paths | accept | CLOSED | Accepted risk documented below. Plan acceptance at `208-01-PLAN.md:423-425`; summary threat flags report none at `208-01-SUMMARY.md:118-120`. |
| T-208-04 | Tampering | `--wan` arg used in SQL filter | mitigate | CLOSED | `src/wanctl/history.py:660-666` passes `wan` into `count_metrics()`; `src/wanctl/storage/reader.py:46-48` uses `wan_name = ?` with `params.append(wan)`, not string interpolation. |
| T-208-05 | Denial-of-Service | malformed DB kills ingestion-rate command | mitigate | CLOSED | `_per_wan_ingestion_rate()` catches residual `(sqlite3.DatabaseError, OSError)` per DB and continues at `src/wanctl/history.py:668-671`; `count_metrics()` also returns `0` on open/query `OperationalError` at `src/wanctl/storage/reader.py:482-501`. |
| T-208-06 | Information Disclosure | ingestion-rate JSON exposes absolute DB paths | accept | CLOSED | Accepted risk documented below. Plan acceptance at `208-02-PLAN.md:652-657`; implementation emits `wan_db` by design at `src/wanctl/history.py:477-480`. |
| T-208-11 | Tampering | unreadable DB silently shows zero rows | accept with documentation | CLOSED | Help text documents suspicious zero-row cross-check at `src/wanctl/history.py:559-566`; accepted operational tradeoff recorded in `208-02-SUMMARY.md:110-114` and below. |
| T-208-07 | Denial-of-Service | one unreadable DB aborts whole digest | mitigate | CLOSED | `print_digest()` catches DB-open `(sqlite3.OperationalError, OSError)` only and continues at `src/wanctl/operator_summary.py:169-177`; regression test at `tests/test_operator_digest.py:106-133`. |
| T-208-08 | Tampering | new guard swallows schema/query corruption | mitigate | CLOSED | `_query_digest_rows(conn)` runs outside the DB-open catch at `src/wanctl/operator_summary.py:180-184`; bubbled `sqlite3.DatabaseError` is caught by `main()` with rc=1 at `src/wanctl/operator_summary.py:238-242`; regression test at `tests/test_operator_digest.py:193-211`. |
| T-208-09 | Information Disclosure | skip message exposes full DB path | accept | CLOSED | Accepted risk documented below. Plan acceptance at `208-03-PLAN.md:573-578`; skip messages intentionally include `db=` at `src/wanctl/operator_summary.py:172-174` and `189-191`. |
| T-208-10 | Denial-of-Service | stdout OSError aborts after partial output | mitigate | CLOSED | Per-line `print(line)` catches `OSError` and continues at `src/wanctl/operator_summary.py:186-194`; partial-write regression test at `tests/test_operator_digest.py:159-190`. |
| T-208-12 | Denial-of-Service | `discover_wan_dbs()` OSError traceback | mitigate | CLOSED | `main()` wraps discovery in `try/except OSError`, emits stable prefix, returns rc=1 at `src/wanctl/operator_summary.py:228-236`; regression test at `tests/test_operator_digest.py:246-258`. |
| T-208-13 | Availability | all stdout writes fail misleading no-readable hint | mitigate | CLOSED | `print_digest()` tracks `readable` and `printed` separately at `src/wanctl/operator_summary.py:159,179,195`; `main()` distinguishes no-readable from all-writes-failed at `src/wanctl/operator_summary.py:244-252`; regression test at `tests/test_operator_digest.py:214-243`. |

## Accepted Risks Log

| Threat ID | Risk | Acceptance Rationale | Operational Note |
|-----------|------|----------------------|------------------|
| T-208-02 | Oversized NDJSON can exhaust aggregator memory. | Operator-owned ad-hoc soak captures are bounded by the soak window; local CLI target, not daemon/network exposed. | Keep soak windows intentional; rerun with smaller capture if local memory pressure occurs. |
| T-208-03 | Malformed aggregator input may produce stack traces with local paths. | Operator CLI only; trace-on-fail is acceptable diagnostic output for local tooling. | Do not publish raw tracebacks from private systems. |
| T-208-06 | Ingestion-rate JSON includes absolute DB paths in `wan_db`. | Local operator-owned CLI path; DB path is useful for diagnosis and not network exposed. | Treat JSON output as operator/internal diagnostic data. |
| T-208-11 | Unreadable DB can appear as zero rows because `count_metrics()` returns `0`. | Existing storage-reader silent-0 contract was intentionally reused to keep scope small; help text documents the cross-check. | For suspicious zero-rate WANs, run `wanctl-history --wan <name> --last 1h` and verify permissions/DB readability. |
| T-208-09 | Digest skip message includes full DB path. | Local operator-controlled path; full path is needed to identify which DB needs permission/sudo remediation. | Treat stderr from operator-summary as internal diagnostic output. |

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-05-16 | 13 | 13 | 0 | gsd-security-auditor |

## Unregistered Flags

None. `208-01-SUMMARY.md`, `208-02-SUMMARY.md`, and `208-03-SUMMARY.md` each report `## Threat Flags: None`.

## Notes

- `208-REVIEW.md` and `208-VERIFICATION.md` contain correctness follow-ups, but they are not new executor `## Threat Flags` and were not reclassified as Phase 208 security threats in this secure-phase pass.
- Implementation files were read only; only this `208-SECURITY.md` artifact was created.

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-05-16
