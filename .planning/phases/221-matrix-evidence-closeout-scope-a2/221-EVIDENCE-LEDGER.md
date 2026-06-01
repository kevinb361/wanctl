---
phase: 221
slug: matrix-evidence-closeout-scope-a2
status_vocabulary:
  - pending
  - partial
  - complete
  - incomplete
last_session_utc: '2026-06-01T20:03:19Z'
completed_replicates: 18
target_replicates: 54
canonical_target: dallas
supplemental_targets:
  - vultr-dallas
  - vultr-chicago
canonical_complete: 2
supplemental_incomplete: 0
quarantined_run_dirs:
  - .planning/phases/220-matrix-runner-scope-a1/evidence/RUN-20260601T150527Z
duplicate_sidecars:
  - .planning/phases/220-matrix-runner-scope-a1/evidence/dallas__spectrum__daytime__r1/phase220-cell.json
unexpected_cell_ids: []
---

# Phase 221 — Matrix Evidence Ledger

> Multi-session resume surface for the 54-run target/path/window matrix. Operator triggers cell runs out-of-session via `./scripts/phase220-target-path-matrix.sh --cell <cell_id> --replicate <N>`; each Claude session reads `.planning/phases/220-matrix-runner-scope-a1/evidence/`, updates this ledger, commits, exits. The aggregator (Phase 220-02) is NOT invoked from this ledger — only from the dedicated closeout-writing plan (Plan 03) at end-of-matrix or D-09 valid-with-footnote readiness.

## Status Vocabulary (no `bgp-changed` — BGP is an independent column)

| Status | Meaning |
|--------|---------|
| `pending` | 0/3 replicates run |
| `partial` | 1 or 2 of 3 replicates run, no D-08 failure |
| `complete` | 3/3 replicates with no D-08 failure (regardless of mtr_post_flag — BGP is reported separately) |
| `incomplete` | D-08 retry budget exhausted (≥1 replicate hit 3 failed attempts via the ledger `attempts` annotation) — cell does NOT enter the closeout canonical/supplemental table |

`mtr_post_flag` is an INDEPENDENT boolean column derived from `phase220-cell.json["path_change_detected"]` (NOT from `mtr-post-*.txt` file existence; the wrapper writes that file every replicate per scripts/phase220-target-path-matrix.sh:372). A `complete 3/3` cell with `mtr_post_flag: true` is still `complete`; the flag affects §6 decision-tree exclusion in Plan 03 but does NOT downgrade cell status here.

## Matrix-Fail Triggers (CONTEXT D-09)

- **INVALID:** ANY canonical control cell `incomplete` in any window OR > 2 supplemental cells `incomplete`. Phase 221 reopens for replan; no closeout written; Plan 02 writes `221-MATRIX-INVALID.md` and halts.
- **VALID with footnote:** ≤ 2 supplemental cells `incomplete` AND all 6 canonical cells `complete`. Plan 03 fires at this state too — see "Plan 03 Readiness Signal" below.

## Operator Runbook

### Per-Window Operator Session (out-of-Claude-session)

Operator picks a calendar day matching ONE of the three window-hour gates from Phase 220 YAML:
- off-peak: hours 01–05 local
- daytime: hours 10–16 local
- prime-time: hours 19–22 local

Within the gate, operator runs ONE OR MORE cells for that window. Each cell-replicate is ONE wrapper invocation:

```bash
./scripts/phase220-target-path-matrix.sh \
  --cell <cell_id> \
  --replicate <N>
```

Per CONTEXT D-02: multiple cells inside the same window-slot on the same day are permitted; Phase 220 60s inter-cell spacing already covers this.

Per CONTEXT D-08: on replicate failure, RE-RUN the same `--cell/--replicate` invocation. Up to 3 total attempts per replicate index. After 3 failed attempts on the same replicate, operator MUST add an `attempts:3` token to the ledger row's `notes` column for that cell (or `attempts:2`/`attempts:1` if the operator is recording partial progress). Plan 02's next session reads this annotation and marks the cell `incomplete` if `attempts >= 3 AND valid_replicates < 3`. The wrapper writes NO sidecar on hard failure, so this annotation IS the failure record.

See `docs/PHASE220-MATRIX-RUNNER.md` for wrapper invocation details (read-only — Phase 221 does not modify).

### Per-Claude-Session Ledger Update Protocol

1. Claude globs `.planning/phases/220-matrix-runner-scope-a1/evidence/**/phase220-cell.json` and filters to VALID sidecars (`schema_version == 1` AND `cell_id` non-null). Invalid/null sidecars (e.g. the historical `RUN-20260601T150527Z/` false-start) are added to frontmatter `quarantined_run_dirs[]` and skipped.
2. Claude deduplicates valid sidecars by `(base_cell_id, replicate_index)`, preserving dropped sidecar paths in `duplicate_sidecars[]`, then groups by base cell_id and reconciles each of 18 ledger rows against the grouped state per Task 1.
3. Claude bumps frontmatter `completed_replicates`, `canonical_complete`, `supplemental_incomplete`, and `last_session_utc`.
4. Claude detects matrix-fail (canonical incomplete OR supplemental_incomplete > 2). If triggered → Task 3 (write 221-MATRIX-INVALID.md, halt). Otherwise → commit ledger and exit.
5. Claude DOES NOT invoke `scripts/phase220-matrix-aggregator.py`. Aggregator runs only in Plan 03 after readiness latch sets.

### Calendar Spread Guidance (CONTEXT D-02)

The 18 cells × 3 replicates spread across at minimum 3 calendar days (one per window-slot) and realistically 1–2 weeks (operator availability + alignment with off-peak hours). The matrix is run-to-completion per CONTEXT D-01 — even if kill OR defect criteria appear satisfied mid-matrix, every replicate completes before Plan 03 fires.

### BGP Path-Change Reporting (CONTEXT D-10)

The `mtr_post_flag` column derives from `phase220-cell.json["path_change_detected"]` using OR-across-all-contributing-replicates. The wrapper writes `mtr-post-<N>.txt` UNCONDITIONALLY per replicate (line 372 of `scripts/phase220-target-path-matrix.sh`) — file existence is NOT a usable BGP signal. A `complete 3/3` cell with `mtr_post_flag: true` is still `complete`; the flag affects §6 decision-tree exclusion in Plan 03 (cells with `mtr_post_flag: true` AND `cell_verdict: cell_defect` are excluded from defect-corroboration arguments) but does NOT downgrade ledger status here.

## Plan 03 Readiness Signal (resolves Codex Plan 02 HIGH deadlock)

Plan 03 is ready to fire when EITHER:
- Ledger frontmatter shows `canonical_complete: 6` AND `supplemental_incomplete: 0..2` AND every other supplemental cell `complete` (success path including D-09 valid-with-footnote — resolves Codex Plan 02 HIGH deadlock), OR
- File `.planning/phases/221-matrix-evidence-closeout-scope-a2/221-MATRIX-INVALID.md` exists (failure path — Plan 03 short-circuits and the phase reopens for replan).

Plan 03 will refuse to write `221-CLOSEOUT.md` if neither condition is met. When the success branch first becomes true, Plan 02 latches the time in frontmatter as `plan_03_ready_at_utc`.

## Cell Status

Rehearsal row substitutions: `last_replicate_utc` is `started_utc` from `.planning/phases/220-matrix-runner-scope-a1/evidence/dallas__spectrum__daytime__r1/phase220-cell.json`; `mtr_pre_sha256` is the first 8 hex characters of `mtr-pre-1.txt`'s SHA-256; `base_sha` is the 40-character `base_sha` field in `phase220-cell.json`; `mtr_post_flag` is `bool(path_change_detected)` from `phase220-cell.json`.

| cell_id | replicates | window | path | target | last_replicate_utc | mtr_pre_sha256 | mtr_post_flag | base_sha | status | notes |
|---------|------------|--------|------|--------|--------------------|----------------|---------------|----------|--------|-------|
| dallas__spectrum__off-peak | 0/3 | off-peak | spectrum | dallas | — | — | — | — | pending | canonical control |
| dallas__spectrum__daytime | 3/3 | daytime | spectrum | dallas | 2026-06-01T18:39:35Z | 54e4d89a | true | 50f3d5136830c284b190b29de939a84406531ecc | complete | r1 rehearsal + daytime r2-r3 canonical replicates; primary_driver details in Phase 220 sidecars; bgp-flagged |
| dallas__spectrum__prime-time | 0/3 | prime-time | spectrum | dallas | — | — | — | — | pending | canonical control |
| dallas__att__off-peak | 0/3 | off-peak | att | dallas | — | — | — | — | pending | canonical control |
| dallas__att__daytime | 3/3 | daytime | att | dallas | 2026-06-01T18:48:24Z | d8a82bb7 | true | 50f3d5136830c284b190b29de939a84406531ecc | complete | canonical control; bgp-flagged |
| dallas__att__prime-time | 0/3 | prime-time | att | dallas | — | — | — | — | pending | canonical control |
| vultr-dallas__spectrum__off-peak | 0/3 | off-peak | spectrum | vultr-dallas | — | — | — | — | pending | supplemental |
| vultr-dallas__spectrum__daytime | 3/3 | daytime | spectrum | vultr-dallas | 2026-06-01T19:32:14Z | 03f5fa17 | true | 50f3d5136830c284b190b29de939a84406531ecc | complete | supplemental; bgp-flagged |
| vultr-dallas__spectrum__prime-time | 0/3 | prime-time | spectrum | vultr-dallas | — | — | — | — | pending | supplemental |
| vultr-dallas__att__off-peak | 0/3 | off-peak | att | vultr-dallas | — | — | — | — | pending | supplemental |
| vultr-dallas__att__daytime | 3/3 | daytime | att | vultr-dallas | 2026-06-01T19:40:47Z | f0ad6009 | true | 50f3d5136830c284b190b29de939a84406531ecc | complete | supplemental; bgp-flagged |
| vultr-dallas__att__prime-time | 0/3 | prime-time | att | vultr-dallas | — | — | — | — | pending | supplemental |
| vultr-chicago__spectrum__off-peak | 0/3 | off-peak | spectrum | vultr-chicago | — | — | — | — | pending | supplemental |
| vultr-chicago__spectrum__daytime | 3/3 | daytime | spectrum | vultr-chicago | 2026-06-01T19:49:20Z | 22f1dd6e | true | 50f3d5136830c284b190b29de939a84406531ecc | complete | supplemental; bgp-flagged |
| vultr-chicago__spectrum__prime-time | 0/3 | prime-time | spectrum | vultr-chicago | — | — | — | — | pending | supplemental |
| vultr-chicago__att__off-peak | 0/3 | off-peak | att | vultr-chicago | — | — | — | — | pending | supplemental |
| vultr-chicago__att__daytime | 3/3 | daytime | att | vultr-chicago | 2026-06-01T19:57:55Z | e5c80d3d | true | 50f3d5136830c284b190b29de939a84406531ecc | complete | supplemental; bgp-flagged |
| vultr-chicago__att__prime-time | 0/3 | prime-time | att | vultr-chicago | — | — | — | — | pending | supplemental |

## Evidence Durability Policy

Raw evidence under `.planning/phases/220-matrix-runner-scope-a1/evidence/` is not committed by Phase 221. Phase 221 commits only ledger, closeout, and todo disposition artifacts; this ledger's `last_replicate_utc`, `mtr_pre_sha256`, `mtr_post_flag`, and `base_sha` columns are the durable per-cell audit trail for operator sessions.
