# FIX-02 Digest Permission Validation Evidence

**Phase:** 232 — cleanup-boundary-guard-tooling-fixes  
**Plan:** 03  
**Requirement:** FIX-02  
**Validated:** 2026-06-11  
**Verdict:** T12/TOOL-03 acceptance criterion **MET** — no reimplementation required.

## Scope

This evidence closes `.planning/todos/pending/2026-04-17-operator-summary-digest-permission-handling.md` by validating the current `wanctl-operator-summary --digest` implementation against the v1.44 Phase 208 T12/TOOL-03 unreadable-DB tolerance contract.

No source reimplementation was performed. The current evidence shows the acceptance criterion is already met by the Phase 208 implementation plus later ingestion-rate digest extension.

## Implementation Anchor

- Source: `src/wanctl/operator_summary.py::print_digest`
- Stable skip prefix: `_DIGEST_SKIP_PREFIX = "operator-summary digest: skipped"`
- DB open boundary: `sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)` catches `(sqlite3.OperationalError, OSError)` per DB and continues.
- Write boundary: `print(line)` catches `OSError` per DB and continues with the `(write)` skip marker.
- Discovery boundary: `main()` catches discovery `OSError` with `operator-summary digest: discovery failed (...)` and returns failure for discovery-level access errors.
- Query-time behavior: `_query_digest_rows(conn)` errors are **not** classified as permission skips. Current code catches `(sqlite3.OperationalError, sqlite3.DatabaseError)` per DB, logs a distinct `operator-summary digest: hard-red query failed ...` stderr message, increments `read_skipped`, and continues. Command-level exit 1 surfaces through `main()`'s `operator-summary digest: hard-red output unavailable` path only when readable DBs existed but no hard-red digest line was printed. A mixed good+corrupt DB run can still exit 0 with the stderr warning if another DB prints successfully.

## T12/TOOL-03 Truth → Pinning Test Mapping

| T12/TOOL-03 truth | Pinning test | Evidence |
|---|---|---|
| A single unreadable WAN DB does not abort the digest; remaining DBs are processed and printed. | `tests/test_operator_digest.py::test_digest_skips_unreadable_db` | Test monkeypatches `sqlite3.connect` to fail for `metrics-att.db`; `main()` returns 0 and stdout still contains the Spectrum digest line. |
| Skip message uses the stable stderr prefix with `wan=` and `db=` context. | `tests/test_operator_digest.py::test_digest_skips_unreadable_db` | Asserts `operator-summary digest: skipped`, `wan=att`, and `db=` in stderr. |
| When all discovered WAN DBs are unreadable, command exits 0 with `no readable WAN DBs - try sudo`. | `tests/test_operator_digest.py::test_digest_all_unreadable_exits_zero_with_hint` | All DB opens raise `sqlite3.OperationalError`; test asserts rc 0 and the stable sudo hint. |
| Output-write failures are caught only around stdout writes; remaining DBs continue. | `tests/test_operator_digest.py::test_digest_skips_on_output_write_oserror` | First stdout write raises `OSError`, second DB still prints; test asserts rc 0 and `(write)` skip marker. |
| When all readable DBs fail stdout-write, command exits 1 with `operator-summary digest: all output writes failed`. | `tests/test_operator_digest.py::test_digest_all_writes_fail_emits_distinct_message` | All stdout writes raise `OSError`; test asserts rc 1 and the distinct all-writes-failed message, not the unreadable-DB hint. |
| Query-time errors are not classified as permission skips. | `tests/test_operator_digest.py::test_digest_missing_alerts_table_bubbles_not_skipped` | DB opens successfully but lacks `alerts`; test asserts non-zero rc and that stderr does **not** contain the skip prefix. Current implementation logs a distinct hard-red query failure and surfaces command-level failure only when no digest line printed. |
| Discovery-level `OSError` is caught with a stable distinct message. | `tests/test_operator_digest.py::test_digest_discovery_oserror_caught` | `discover_wan_dbs()` raises `OSError`; test asserts rc 1 and `operator-summary digest: discovery failed`. |

## Fresh Deterministic Test Run

Command:

```bash
.venv/bin/pytest -o addopts='' tests/test_operator_digest.py -q
```

Output:

```text
.........                                                                [100%]
9 passed in 0.23s
```

## Best-Effort Read-Only Live Check

Command:

```bash
ssh -o ConnectTimeout=10 -o BatchMode=yes kevin@10.10.110.223 'wanctl-operator-summary --digest; echo rc=$?'
```

Recorded output:

```text
operator-summary digest: discovery failed ([Errno 13] Permission denied: '/var/lib/wanctl/metrics.db')
rc=0
```

Interpretation: the live check remained inspection-only and recorded the deployed wrapper/environment behavior verbatim. It is supplemental only; the deterministic pinning tests above are the primary FIX-02 evidence per the Phase 232 research note about live environment drift.

## Verdict

T12/TOOL-03 acceptance criterion **MET**. The todo's requested operator-facing behavior is already implemented in stricter, test-pinned form by v1.44 Phase 208 and subsequent digest hardening:

- unreadable per-WAN DBs are skipped with stable stderr context;
- all-unreadable cases produce the sudo hint;
- write failures have a distinct path;
- query/schema faults are not mislabeled as permission skips;
- discovery failures have a distinct message.

No `src/wanctl/operator_summary.py` reimplementation was required or performed in Phase 232 Plan 03.
