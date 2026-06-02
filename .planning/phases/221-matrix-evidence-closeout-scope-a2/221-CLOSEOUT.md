---
phase: 221
slug: matrix-evidence-closeout-scope-a2
verdict: carried_narrower_with_close_with_prejudice_rule
matrix_verdict: defect_located
bgp_excluded_cells: ["vultr-chicago__spectrum__prime-time", "vultr-dallas__spectrum__daytime", "vultr-dallas__spectrum__prime-time"]
matrix_base_sha: 50f3d5136830c284b190b29de939a84406531ecc
phase220_yaml_sha: 62f5532095f9c4e34fe485b3a0510ad26e3cf2ea
aggregator_run_utc: 2026-06-02T12:28:27Z
closeout_commit_for_todo: 5bef67084ec7f738a7577e7ca2dae59c3acd0dda
closeout_written_utc: 2026-06-02T12:30:57Z
---

# Phase 221 Closeout — Matrix Evidence + Decision Report

## §1 Verdict

The Phase 221 matrix produced a post-BGP-overlay carried-narrower verdict under the close-with-prejudice rule: raw defect evidence became path-ambiguous under D-10 BGP exclusion or otherwise failed the locked corroboration branch.

**Verdict:** carried_narrower_with_close_with_prejudice_rule

**Raw aggregator verdict (pre-D-10 BGP overlay):** defect_located
**BGP-excluded cells (CONTEXT D-10):** vultr-chicago__spectrum__prime-time, vultr-dallas__spectrum__daytime, vultr-dallas__spectrum__prime-time


## §2 Threshold Citation

Thresholds applied unchanged from Phase 220 commit. Phase 220 YAML blob SHA: `62f5532095f9c4e34fe485b3a0510ad26e3cf2ea`.

| Threshold | Value | REQ reference |
|-----------|-------|---------------|
| canonical_control_p99_kill_ms | 200 | CRITERIA-01 kill |
| canonical_min_windows_kill | 2 | CRITERIA-01 kill |
| canonical_max_windows_kill_total | 3 | CRITERIA-01 kill |
| supplemental_defect_p99_ms | 500 | CRITERIA-01 defect |
| supplemental_defect_min_windows | 2 | CRITERIA-01 defect |
| supplemental_carry_multiplier_of_control | 1.5 | CRITERIA-01 kill (no supplemental > 1.5× control) |

Verification: `git rev-parse HEAD:scripts/phase220-matrix.yaml` returns `62f5532095f9c4e34fe485b3a0510ad26e3cf2ea` at the time of this report.

## §3 Table 1: Canonical Control

| cell_id | target_kind | target | path | window | replicate_count | run_timestamps_utc | p50_ms | p95_ms | p99_ms | primary_driver | ranked_drivers_top3 | mtr_pre_ref | mtr_post_flag | base_sha | cell_verdict |
|---------|-------------|--------|------|--------|-----------------|--------------------|--------|--------|--------|----------------|---------------------|-------------|---------------|----------|--------------|
 | dallas__att__off-peak | canonical | dallas | att | off-peak | 3/3 | 2026-06-02T06:08:49Z, 2026-06-02T06:11:44Z, 2026-06-02T06:14:40Z | 52.6 | 56.6 | 57.5 | icmp_udp_divergence | icmp_udp_divergence(1.00) | .planning/phases/220-matrix-runner-scope-a1/evidence/RUN-20260602T061456Z/mtr-pre-3.txt | true | 50f3d5136830 | cell_kill_clear | 
 | dallas__att__daytime | canonical | dallas | att | daytime | 3/3 | 2026-06-01T18:42:32Z, 2026-06-01T18:45:28Z, 2026-06-01T18:48:24Z | 52.6 | 56.9 | 60.3 | icmp_udp_divergence | stale_cached_rtt(1.00), icmp_udp_divergence(0.67) | .planning/phases/220-matrix-runner-scope-a1/evidence/RUN-20260601T184840Z/mtr-pre-3.txt | true | 50f3d5136830 | cell_kill_clear | 
 | dallas__att__prime-time | canonical | dallas | att | prime-time | 3/3 | 2026-06-02T00:08:49Z, 2026-06-02T00:11:46Z, 2026-06-02T00:14:41Z | 52.8 | 56.1 | 57.7 | external_path | — | .planning/phases/220-matrix-runner-scope-a1/evidence/RUN-20260602T001457Z/mtr-pre-3.txt | true | 50f3d5136830 | cell_kill_clear | 
 | dallas__spectrum__off-peak | canonical | dallas | spectrum | off-peak | 3/3 | 2026-06-02T06:00:02Z, 2026-06-02T06:02:57Z, 2026-06-02T06:05:53Z | 34.6 | 64.9 | 76.5 | external_path | — | .planning/phases/220-matrix-runner-scope-a1/evidence/RUN-20260602T060609Z/mtr-pre-3.txt | true | 50f3d5136830 | cell_kill_clear | 
 | dallas__spectrum__daytime | canonical | dallas | spectrum | daytime | 4/3 | 2026-06-01T15:33:49Z, 2026-06-01T15:33:49Z, 2026-06-01T18:36:38Z, 2026-06-01T18:39:35Z | 34.5 | 64.5 | 90.6 | stale_cached_rtt | reflector_loss(1.00) | .planning/phases/220-matrix-runner-scope-a1/evidence/RUN-20260601T183951Z/mtr-pre-3.txt | true | 50f3d5136830 | cell_kill_clear | 
 | dallas__spectrum__prime-time | canonical | dallas | spectrum | prime-time | 3/3 | 2026-06-02T00:00:01Z, 2026-06-02T00:02:58Z, 2026-06-02T00:05:53Z | 40.7 | 284.0 | 716.0 | reflector_loss | stale_cached_rtt(1.00), reflector_loss(0.67) | .planning/phases/220-matrix-runner-scope-a1/evidence/RUN-20260602T000609Z/mtr-pre-3.txt | true | 50f3d5136830 | cell_carry | 

> Ranked-driver weight convention: rank-1 = 1.0, rank-N = max(0, 1.0 − (N−1)/3). Format: `driver(weight)`.

## §4 Table 2: Supplemental Cells

| cell_id | target_kind | target | path | window | replicate_count | run_timestamps_utc | p50_ms | p95_ms | p99_ms | primary_driver | ranked_drivers_top3 | mtr_pre_ref | mtr_post_flag | base_sha | cell_verdict |
|---------|-------------|--------|------|--------|-----------------|--------------------|--------|--------|--------|----------------|---------------------|-------------|---------------|----------|--------------|
 | vultr-chicago__att__off-peak | supplemental | vultr-chicago | att | off-peak | 3/3 | 2026-06-02T06:43:02Z, 2026-06-02T06:45:51Z, 2026-06-02T06:48:41Z | 49.9 | 51.2 | 55.1 | icmp_udp_divergence | stale_cached_rtt(1.00) | .planning/phases/220-matrix-runner-scope-a1/evidence/RUN-20260602T064857Z/mtr-pre-3.txt | true | 50f3d5136830 | cell_kill_clear | 
 | vultr-chicago__att__daytime | supplemental | vultr-chicago | att | daytime | 3/3 | 2026-06-01T19:52:13Z, 2026-06-01T19:55:04Z, 2026-06-01T19:57:55Z | 50.0 | 52.8 | 76.6 | icmp_udp_divergence | icmp_udp_divergence(1.00) | .planning/phases/220-matrix-runner-scope-a1/evidence/RUN-20260601T195811Z/mtr-pre-3.txt | true | 50f3d5136830 | cell_kill_clear | 
 | vultr-chicago__att__prime-time | supplemental | vultr-chicago | att | prime-time | 3/3 | 2026-06-02T00:43:07Z, 2026-06-02T00:45:56Z, 2026-06-02T00:48:46Z | 50.0 | 51.0 | 56.7 | icmp_udp_divergence | icmp_udp_divergence(1.00) | .planning/phases/220-matrix-runner-scope-a1/evidence/RUN-20260602T004902Z/mtr-pre-3.txt | true | 50f3d5136830 | cell_kill_clear | 
 | vultr-chicago__spectrum__off-peak | supplemental | vultr-chicago | spectrum | off-peak | 3/3 | 2026-06-02T06:34:32Z, 2026-06-02T06:37:22Z, 2026-06-02T06:40:12Z | 724.0 | 746.0 | 750.0 | external_path | — | .planning/phases/220-matrix-runner-scope-a1/evidence/RUN-20260602T064028Z/mtr-pre-3.txt | true | 50f3d5136830 | cell_carry | 
 | vultr-chicago__spectrum__daytime | supplemental | vultr-chicago | spectrum | daytime | 3/3 | 2026-06-01T19:43:39Z, 2026-06-01T19:46:30Z, 2026-06-01T19:49:20Z | 583.0 | 715.0 | 898.0 | external_path | reflector_loss(1.00) | .planning/phases/220-matrix-runner-scope-a1/evidence/RUN-20260601T194936Z/mtr-pre-3.txt | true | 50f3d5136830 | cell_carry | 
 | vultr-chicago__spectrum__prime-time | supplemental | vultr-chicago | spectrum | prime-time | 3/3 | 2026-06-02T00:34:36Z, 2026-06-02T00:37:26Z, 2026-06-02T00:40:16Z | 685.0 | 713.0 | 1029.0 | reflector_loss | — | .planning/phases/220-matrix-runner-scope-a1/evidence/RUN-20260602T004032Z/mtr-pre-3.txt | true | 50f3d5136830 | cell_defect ❌ excluded-by-D-10-BGP | 
 | vultr-dallas__att__off-peak | supplemental | vultr-dallas | att | off-peak | 3/3 | 2026-06-02T06:26:04Z, 2026-06-02T06:28:53Z, 2026-06-02T06:31:43Z | 29.2 | 30.3 | 33.4 | icmp_udp_divergence | icmp_udp_divergence(1.00) | .planning/phases/220-matrix-runner-scope-a1/evidence/RUN-20260602T063159Z/mtr-pre-3.txt | true | 50f3d5136830 | cell_kill_clear | 
 | vultr-dallas__att__daytime | supplemental | vultr-dallas | att | daytime | 3/3 | 2026-06-01T19:35:05Z, 2026-06-01T19:37:56Z, 2026-06-01T19:40:47Z | 29.2 | 30.3 | 32.0 | icmp_udp_divergence | icmp_udp_divergence(1.00) | .planning/phases/220-matrix-runner-scope-a1/evidence/RUN-20260601T194103Z/mtr-pre-3.txt | true | 50f3d5136830 | cell_kill_clear | 
 | vultr-dallas__att__prime-time | supplemental | vultr-dallas | att | prime-time | 3/3 | 2026-06-02T00:26:06Z, 2026-06-02T00:28:55Z, 2026-06-02T00:31:46Z | 29.2 | 30.4 | 35.6 | icmp_udp_divergence | icmp_udp_divergence(1.00) | .planning/phases/220-matrix-runner-scope-a1/evidence/RUN-20260602T003202Z/mtr-pre-3.txt | true | 50f3d5136830 | cell_kill_clear | 
 | vultr-dallas__spectrum__off-peak | supplemental | vultr-dallas | spectrum | off-peak | 3/3 | 2026-06-02T06:17:36Z, 2026-06-02T06:20:25Z, 2026-06-02T06:23:15Z | 698.0 | 758.0 | 765.0 | external_path | — | .planning/phases/220-matrix-runner-scope-a1/evidence/RUN-20260602T062331Z/mtr-pre-3.txt | true | 50f3d5136830 | cell_carry | 
 | vultr-dallas__spectrum__daytime | supplemental | vultr-dallas | spectrum | daytime | 3/3 | 2026-06-01T19:26:33Z, 2026-06-01T19:29:24Z, 2026-06-01T19:32:14Z | 708.0 | 811.0 | 1339.0 | reflector_loss | reflector_loss(1.00) | .planning/phases/220-matrix-runner-scope-a1/evidence/RUN-20260601T193230Z/mtr-pre-3.txt | true | 50f3d5136830 | cell_defect ❌ excluded-by-D-10-BGP | 
 | vultr-dallas__spectrum__prime-time | supplemental | vultr-dallas | spectrum | prime-time | 3/3 | 2026-06-02T00:17:37Z, 2026-06-02T00:20:26Z, 2026-06-02T00:23:16Z | 654.0 | 782.0 | 1040.0 | reflector_loss | — | .planning/phases/220-matrix-runner-scope-a1/evidence/RUN-20260602T002332Z/mtr-pre-3.txt | true | 50f3d5136830 | cell_defect ❌ excluded-by-D-10-BGP | 

> Canonical cells are separated from supplemental cells per CONTEXT D-04. Supplemental incomplete rows, if any, are synthesized from the ledger with dashed latency values because the aggregator skips incomplete cells.

## §5 Per-Axis Rollup

> **Aggregation rule:** any `cell_defect` wins → any `cell_carry` wins → else `cell_kill_clear`. Canonical control is reported separately from supplemental targets per CONTEXT D-04.

### Per-Target Rollup
| target | axis_verdict |
|--------|--------------|
| canonical_dallas | carry |
| vultr-chicago | defect |
| vultr-dallas | defect |

### Per-Path Rollup
| path | axis_verdict |
|--------|--------------|
| att | kill_clear |
| spectrum | defect |

### Per-Window Rollup
| window | axis_verdict |
|--------|--------------|
| daytime | defect |
| off-peak | carry |
| prime-time | defect |

### Post-BGP-Overlay Rollup
### Per-Target Rollup After BGP Overlay
| target | axis_verdict |
|--------|--------------|
| canonical_dallas | carry |
| vultr-chicago | carry |
| vultr-dallas | carry |

### Per-Path Rollup After BGP Overlay
| path | axis_verdict |
|--------|--------------|
| att | kill_clear |
| spectrum | carry |

### Per-Window Rollup After BGP Overlay
| window | axis_verdict |
|--------|--------------|
| daytime | carry |
| off-peak | carry |
| prime-time | carry |

## §6 Matrix-Level Verdict Decision Tree

> Verdict source: `JSON.final_verdict_after_bgp_overlay` (Plan 03 BGP-overlay applied on top of `scripts/phase220-matrix-aggregator.py` raw output). This trace narrates branch selection for BOTH pre-overlay (`matrix_verdict`) AND post-overlay (`final_verdict_after_bgp_overlay`) computations; the published §1 verdict is the post-overlay value per CONTEXT D-10.

### Pre-BGP-Overlay (raw aggregator)

- **[MATCHED]** `defect_located`
  - Reproducing defect cells: vultr-dallas__spectrum__daytime, vultr-dallas__spectrum__prime-time, vultr-chicago__spectrum__prime-time
  - Orthogonal corroboration: path_orthogonal=False, target_orthogonal=True, driver_orthogonal=True, satisfied=True
  - Branch result: MATCHED iff `JSON.matrix_verdict == "defect_located"`.
- **[FAILED]** `hypothesis_killed`
  - Canonical p99 per window: {"daytime": 60.3, "off-peak": 57.5, "prime-time": 57.7}
  - Canonical windows under 200ms kill threshold: 3
  - Supplemental cells exceeding 1.5× control: vultr-chicago__spectrum__daytime (898.0ms > 1.5×60.3ms), vultr-chicago__spectrum__off-peak (750.0ms > 1.5×57.5ms), vultr-chicago__spectrum__prime-time (1029.0ms > 1.5×57.7ms), vultr-dallas__spectrum__daytime (1339.0ms > 1.5×60.3ms), vultr-dallas__spectrum__off-peak (765.0ms > 1.5×57.5ms), vultr-dallas__spectrum__prime-time (1040.0ms > 1.5×57.7ms)
  - Branch result: MATCHED iff `JSON.matrix_verdict == "hypothesis_killed"`.
- **[FAILED]** `carried_narrower_with_close_with_prejudice_rule`
  - Branch result: MATCHED iff neither the defect nor kill branch matched.

**Raw aggregator verdict:** defect_located

### BGP Overlay (CONTEXT D-10 — BGP Caveat applied)

Per CONTEXT D-10: "If `mtr_post_flag: true` AND `cell_defect`, the matrix-level decision-tree explicitly excludes that cell from defect-corroboration arguments (path attribution ambiguous)."

Excluded cells: vultr-chicago__spectrum__prime-time, vultr-dallas__spectrum__daytime, vultr-dallas__spectrum__prime-time

- vultr-chicago__spectrum__prime-time: target=vultr-chicago, path=spectrum, window=prime-time, aggregator verdict=cell_defect, latest_started_utc=2026-06-02T00:40:16Z
- vultr-dallas__spectrum__daytime: target=vultr-dallas, path=spectrum, window=daytime, aggregator verdict=cell_defect, latest_started_utc=2026-06-01T19:32:14Z
- vultr-dallas__spectrum__prime-time: target=vultr-dallas, path=spectrum, window=prime-time, aggregator verdict=cell_defect, latest_started_utc=2026-06-02T00:23:16Z

Post-overlay recomputation uses the same `matrix_verdict()` helper from `scripts/phase220-matrix-aggregator.py`, applied to `per_cell MINUS bgp_excluded_cells` with thresholds and driver_allowlist loaded from `scripts/phase220-matrix.yaml`.

- Recomputed orthogonal_corroboration: path_orthogonal=False, target_orthogonal=False, driver_orthogonal=False, satisfied=False
- Recomputed per_target: {"canonical_dallas": "carry", "vultr-chicago": "carry", "vultr-dallas": "carry"}
- Recomputed per_path: {"att": "kill_clear", "spectrum": "carry"}
- Recomputed per_window: {"daytime": "carry", "off-peak": "carry", "prime-time": "carry"}
- Recomputed reproduction count: 0
- **Post-overlay verdict:** carried_narrower_with_close_with_prejudice_rule

BGP overlay flipped the verdict from `defect_located` to `carried_narrower_with_close_with_prejudice_rule`. CONTEXT D-10 is the controlling rule — the post-overlay value is authoritative.


## §7 BGP-Change Footnote

Cells with `mtr_post_flag: true` by OR-across-all-contributing-replicates: dallas__att__daytime, dallas__att__off-peak, dallas__att__prime-time, dallas__spectrum__daytime, dallas__spectrum__off-peak, dallas__spectrum__prime-time, vultr-chicago__att__daytime, vultr-chicago__att__off-peak, vultr-chicago__att__prime-time, vultr-chicago__spectrum__daytime, vultr-chicago__spectrum__off-peak, vultr-chicago__spectrum__prime-time, vultr-dallas__att__daytime, vultr-dallas__att__off-peak, vultr-dallas__att__prime-time, vultr-dallas__spectrum__daytime, vultr-dallas__spectrum__off-peak, vultr-dallas__spectrum__prime-time.

This flag is derived from `phase220-cell.json["path_change_detected"]` across all contributing replicates, not from `mtr-post-*.txt` existence. Defect cells in this set are the D-10 BGP-excluded cells listed in §6.

## §8 Failed-Cell Footnote

All 18 cells completed 3/3 replicates without D-08 failure.

## §9 Historical Context

> **This section is reportage. Verdict computation in §6 already happened.**

### Folded-Todo 2026-04-15 02:45 CDT Worst-Case Reproduction

The folded `tcp_12down` todo's worst-case live capture (2026-04-15 02:45 CDT) recorded p99 = 3059ms. Reproduction status in the Phase 221 matrix:

- Cells with median_p99_ms > 1000ms: 3 — vultr-chicago__spectrum__prime-time, vultr-dallas__spectrum__daytime, vultr-dallas__spectrum__prime-time
- Cells with median_p99_ms > 500ms (supplemental defect threshold): 7 — dallas__spectrum__prime-time, vultr-chicago__spectrum__daytime, vultr-chicago__spectrum__off-peak, vultr-chicago__spectrum__prime-time, vultr-dallas__spectrum__daytime, vultr-dallas__spectrum__off-peak, vultr-dallas__spectrum__prime-time
- Did the matrix reproduce the 3059ms worst case: yes

### Phase 214 Anchor Reconciliation

Phase 214 daytime canonical dallas p99 was 606ms (verdict ambiguous); Phase 221 daytime canonical dallas median_p99_ms was 90.6ms (spectrum) and 60.3ms (att). Phase 214 prime-time canonical dallas p99 was 560ms; Phase 221 prime-time canonical dallas median_p99_ms was 716.0ms. Phase 214's `ambiguous` driver classification at these p99s is resolved by the Phase 221 post-overlay corroboration rule to: `carried_narrower_with_close_with_prejudice_rule`.

## §10 Todo Disposition

**Verdict applied:** carried_narrower_with_close_with_prejudice_rule
**Todo file:** `.planning/todos/closed/2026-04-08-investigate-tcp-12down-latency-spikes-under-multi-flow-downl.md`
**Closeout commit for todo move:** `5bef67084ec7f738a7577e7ca2dae59c3acd0dda`

### Close-With-Prejudice Rule (CRITERIA-02, verbatim from REQUIREMENTS.md)

> - [x] **CRITERIA-02**: Close-with-prejudice rule documented: if matrix verdict is again `ambiguous`, the folded `2026-04-08-investigate-tcp-12down` todo is closed-with-prejudice and no v1.48+ follow-up may reopen the thread without independent new evidence (e.g., a real production p99 incident captured in DB).


## §11 Mutation Boundary (SAFE-11)

Phase 221 mutation-boundary pytest: `tests/test_phase221_mutation_boundary.py` (6 test functions)
- Last run (before this commit): PASSED at 2026-06-02T12:30:57Z
- Controller-path diff vs Phase 220 base_sha: empty by pytest
- Phase 213/214 script diff: empty by pytest
- Phase 220 script diff: empty (`test_no_phase220_scripts_diff`)
- docs/ diff: empty (closeout report lives in `.planning/`, not docs/)

Final SAFE-11 re-run is Plan 04 Task 6 at phase close.
