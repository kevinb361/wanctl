---
phase: 221
slug: matrix-evidence-closeout-scope-a2
status_vocabulary: [pending, partial, complete, incomplete]
last_session_utc: 2026-06-01T00:00:00Z
completed_replicates: 1
target_replicates: 54
canonical_target: dallas
supplemental_targets: [vultr-dallas, vultr-chicago]
canonical_complete: 0
supplemental_incomplete: 0
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

## Plan 03 Readiness Signal (resolves Codex Plan 02 HIGH deadlock)

Plan 03 is ready to fire when EITHER:
1. `completed_replicates: 54` AND all 18 cells `complete` (canonical happy path), OR
2. All 6 canonical cells `complete` AND between 0 and 2 supplemental cells `incomplete` AND every other supplemental cell is `complete` (D-09 valid-with-footnote path), OR
3. `221-MATRIX-INVALID.md` exists (matrix-fail short-circuit; Plan 03 writes nothing).

Acceptance encoded via two frontmatter helper fields maintained by Plan 02:
- `canonical_complete: <0..6>` — number of canonical cells with status=complete
- `supplemental_incomplete: <0..12>` — number of supplemental cells with status=incomplete

Plan 03 reads frontmatter and fires iff (canonical_complete == 6 AND supplemental_incomplete <= 2) OR matrix-fail file present.

## Cell Status

Rehearsal row substitutions: `last_replicate_utc` is `started_utc` from `.planning/phases/220-matrix-runner-scope-a1/evidence/dallas__spectrum__daytime__r1/phase220-cell.json`; `mtr_pre_sha256` is the first 8 hex characters of `mtr-pre-1.txt`'s SHA-256; `base_sha` is the 40-character `base_sha` field in `phase220-cell.json`; `mtr_post_flag` is `bool(path_change_detected)` from `phase220-cell.json`.

| cell_id | replicates | window | path | target | last_replicate_utc | mtr_pre_sha256 | mtr_post_flag | base_sha | status | notes |
|---------|------------|--------|------|--------|--------------------|----------------|---------------|----------|--------|-------|
| dallas__spectrum__off-peak | 0/3 | off-peak | spectrum | dallas | — | — | — | — | pending | canonical control |
| dallas__spectrum__daytime | 1/3 | daytime | spectrum | dallas | 2026-06-01T15:33:49Z | 07371ae2 | true | 50f3d5136830c284b190b29de939a84406531ecc | partial | Phase 220-04 wet rehearsal r1 only; verdict ambiguous, primary_driver reflector_loss |
| dallas__spectrum__prime-time | 0/3 | prime-time | spectrum | dallas | — | — | — | — | pending | canonical control |
| dallas__att__off-peak | 0/3 | off-peak | att | dallas | — | — | — | — | pending | canonical control |
| dallas__att__daytime | 0/3 | daytime | att | dallas | — | — | — | — | pending | canonical control |
| dallas__att__prime-time | 0/3 | prime-time | att | dallas | — | — | — | — | pending | canonical control |
| vultr-dallas__spectrum__off-peak | 0/3 | off-peak | spectrum | vultr-dallas | — | — | — | — | pending | supplemental |
| vultr-dallas__spectrum__daytime | 0/3 | daytime | spectrum | vultr-dallas | — | — | — | — | pending | supplemental |
| vultr-dallas__spectrum__prime-time | 0/3 | prime-time | spectrum | vultr-dallas | — | — | — | — | pending | supplemental |
| vultr-dallas__att__off-peak | 0/3 | off-peak | att | vultr-dallas | — | — | — | — | pending | supplemental |
| vultr-dallas__att__daytime | 0/3 | daytime | att | vultr-dallas | — | — | — | — | pending | supplemental |
| vultr-dallas__att__prime-time | 0/3 | prime-time | att | vultr-dallas | — | — | — | — | pending | supplemental |
| vultr-chicago__spectrum__off-peak | 0/3 | off-peak | spectrum | vultr-chicago | — | — | — | — | pending | supplemental |
| vultr-chicago__spectrum__daytime | 0/3 | daytime | spectrum | vultr-chicago | — | — | — | — | pending | supplemental |
| vultr-chicago__spectrum__prime-time | 0/3 | prime-time | spectrum | vultr-chicago | — | — | — | — | pending | supplemental |
| vultr-chicago__att__off-peak | 0/3 | off-peak | att | vultr-chicago | — | — | — | — | pending | supplemental |
| vultr-chicago__att__daytime | 0/3 | daytime | att | vultr-chicago | — | — | — | — | pending | supplemental |
| vultr-chicago__att__prime-time | 0/3 | prime-time | att | vultr-chicago | — | — | — | — | pending | supplemental |

## Evidence Durability Policy

Raw evidence under `.planning/phases/220-matrix-runner-scope-a1/evidence/` is not committed by Phase 221. Phase 221 commits only ledger, closeout, and todo disposition artifacts; this ledger's `last_replicate_utc`, `mtr_pre_sha256`, `mtr_post_flag`, and `base_sha` columns are the durable per-cell audit trail for operator sessions.
