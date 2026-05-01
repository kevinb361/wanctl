# Phase 198 Plan 06: Off-Peak Rerun Attempt Log

Cross-attempt audit log of every off-peak rerun attempt. Each section records
one attempt with verdict numbers and the operator decision. Multi-night
attempts are stacked in chronological order. The hard-abort threshold is
3 accumulated attempts in {abort, retry, failed:true}; further attempts
require a `continuation_justification:` line below before the harness will
allow them.

Locked rules (do not edit):
- Throughput verdict: PASS iff `medians_above_532 >= 2 AND median_of_medians_mbps >= 532`
- Per-run audit pass: `health_sample_count >= 25 AND queue_primary_health_pct >= 95 AND health_non_queue == 0`
- Off-peak window: 02:00-04:59 local (extended 01:00-05:59 with `--allow-extended-window`)

continuation_justification: Operator requested one additional retry after three failed/forced attempts; attempt 4 is scheduled for the standard off-peak window and will not use --force-window.

---
## Attempt 1

- **Attempted at (UTC):** unknown
- **Local hour at start:** unknown
- **Off-peak window used:** forced:operator requested immediate run outside off-peak
- **HEAD SHA at attempt:** 070b3d2
- **Failed:** true
- **Harness exit code:** 255
- **Failure stage:** sqlite
- **Completed runs:** 0
- **Operator decision:** retry
- **Operator note:** Operator requested retry via Hermes on 2026-04-29T14:12:53Z; schedule one additional standard off-peak attempt.

---

## Attempt 2

- **Attempted at (UTC):** 2026-04-29T12:14:27Z
- **Local hour at start:** 7
- **Off-peak window used:** forced:operator requested immediate run outside off-peak
- **HEAD SHA at attempt:** 070b3d2
- **SAFE-05 protected diff empty:** true
- **Throughput verdict:** FAIL
  - run1: 405.709919 Mbps
  - run2: 414.31425 Mbps
  - run3: 411.917833 Mbps
  - median-of-medians: 411.917833 Mbps
- **Per-run loaded-window audit verdicts:** fail / fail / fail
- **All per-run audits pass:** false
- **Failed:** false
- **Operator decision:** retry
- **Operator note:** Operator requested retry via Hermes on 2026-04-29T14:12:53Z; schedule one additional standard off-peak attempt.

---

## Attempt 3

- **Attempted at (UTC):** 2026-04-29T12:19:40Z
- **Local hour at start:** 7
- **Off-peak window used:** forced:operator requested immediate run outside off-peak
- **HEAD SHA at attempt:** 070b3d2
- **SAFE-05 protected diff empty:** true
- **Throughput verdict:** FAIL
  - run1: 395.241285 Mbps
  - run2: 334.083778 Mbps
  - run3: 333.618492 Mbps
  - median-of-medians: 334.083778 Mbps
- **Per-run loaded-window audit verdicts:** fail / fail / fail
- **All per-run audits pass:** false
- **Failed:** false
- **Operator decision:** retry
- **Operator note:** Operator requested retry via Hermes on 2026-04-29T14:12:53Z; schedule one additional standard off-peak attempt.

---

## Attempt 4
<!-- attempt-key: rerun-attempt-4 -->

- **Attempted at (UTC):** 2026-04-30T07:31:39Z
- **Local hour at start:** unknown
- **Off-peak window used:** standard:02-04
- **HEAD SHA at attempt:** 070b3d2
- **Failed:** true
- **Harness exit code:** 255
- **Failure stage:** sqlite
- **Completed runs:** 0
- **Throughput verdict:** n/a
- **Per-run loaded-window audit verdicts:** n/a
- **All per-run audits pass:** false
- **Operator decision:** retry
- **Evidence dir:** `.planning/phases/198-spectrum-cake-primary-b-leg-rerun/soak/cake-primary/rerun-attempt-4`
- **Harness log:** `.planning/phases/198-spectrum-cake-primary-b-leg-rerun/soak/cake-primary/scheduled-attempt-20260430T073139Z-run1.log`

---

## Attempt 5
<!-- attempt-key: rerun-attempt-5 -->

- **Attempted at (UTC):** 2026-04-30T07:37:21Z
- **Local hour at start:** unknown
- **Off-peak window used:** standard:02-04
- **HEAD SHA at attempt:** 070b3d2
- **Failed:** true
- **Harness exit code:** 255
- **Failure stage:** sqlite
- **Completed runs:** 0
- **Throughput verdict:** n/a
- **Per-run loaded-window audit verdicts:** n/a
- **All per-run audits pass:** false
- **Operator decision:** retry
- **Evidence dir:** `.planning/phases/198-spectrum-cake-primary-b-leg-rerun/soak/cake-primary/rerun-attempt-5`
- **Harness log:** `.planning/phases/198-spectrum-cake-primary-b-leg-rerun/soak/cake-primary/scheduled-attempt-20260430T073721Z-run2.log`

---

## Attempt 6
<!-- attempt-key: rerun-attempt-6 -->

- **Attempted at (UTC):** 2026-04-30T07:43:02Z
- **Local hour at start:** unknown
- **Off-peak window used:** standard:02-04
- **HEAD SHA at attempt:** 070b3d2
- **Failed:** true
- **Harness exit code:** 255
- **Failure stage:** sqlite
- **Completed runs:** 0
- **Throughput verdict:** n/a
- **Per-run loaded-window audit verdicts:** n/a
- **All per-run audits pass:** false
- **Operator decision:** pending
- **Evidence dir:** `.planning/phases/198-spectrum-cake-primary-b-leg-rerun/soak/cake-primary/rerun-attempt-6`
- **Harness log:** `.planning/phases/198-spectrum-cake-primary-b-leg-rerun/soak/cake-primary/scheduled-attempt-20260430T074302Z-run3.log`

---

## Attempt 7
<!-- attempt-key: rerun-attempt-7 -->

- **Attempted at (UTC):** 2026-05-01T07:30:07Z
- **Local hour at start:** 2
- **Off-peak window used:** standard:02-04
- **HEAD SHA at attempt:** ff6673a
- **Failed:** true
- **Harness exit code:** 1
- **Failure stage:** sqlite
- **Completed runs:** 0
- **Throughput verdict:** n/a
- **Per-run loaded-window audit verdicts:** n/a
- **All per-run audits pass:** false
- **Operator decision:** retry
- **Evidence dir:** `.planning/phases/198-spectrum-cake-primary-b-leg-rerun/soak/cake-primary/rerun-attempt-7`
- **Harness log:** `/home/kevin/projects/wanctl/.planning/phases/198-spectrum-cake-primary-b-leg-rerun/soak/cake-primary/scheduled-attempt-20260501T073007Z-run1.log`

---

## Attempt 8
<!-- attempt-key: rerun-attempt-8 -->

- **Attempted at (UTC):** 2026-05-01T07:35:49Z
- **Local hour at start:** 2
- **Off-peak window used:** standard:02-04
- **HEAD SHA at attempt:** ff6673a
- **Failed:** true
- **Harness exit code:** 1
- **Failure stage:** sqlite
- **Completed runs:** 0
- **Throughput verdict:** n/a
- **Per-run loaded-window audit verdicts:** n/a
- **All per-run audits pass:** false
- **Operator decision:** retry
- **Evidence dir:** `.planning/phases/198-spectrum-cake-primary-b-leg-rerun/soak/cake-primary/rerun-attempt-8`
- **Harness log:** `/home/kevin/projects/wanctl/.planning/phases/198-spectrum-cake-primary-b-leg-rerun/soak/cake-primary/scheduled-attempt-20260501T073549Z-run2.log`

---

## Attempt 9
<!-- attempt-key: rerun-attempt-9 -->

- **Attempted at (UTC):** 2026-05-01T07:41:30Z
- **Local hour at start:** 2
- **Off-peak window used:** standard:02-04
- **HEAD SHA at attempt:** ff6673a
- **Failed:** true
- **Harness exit code:** 1
- **Failure stage:** sqlite
- **Completed runs:** 0
- **Throughput verdict:** n/a
- **Per-run loaded-window audit verdicts:** n/a
- **All per-run audits pass:** false
- **Operator decision:** pending
- **Evidence dir:** `.planning/phases/198-spectrum-cake-primary-b-leg-rerun/soak/cake-primary/rerun-attempt-9`
- **Harness log:** `/home/kevin/projects/wanctl/.planning/phases/198-spectrum-cake-primary-b-leg-rerun/soak/cake-primary/scheduled-attempt-20260501T074130Z-run3.log`

---

WARNING: hard-abort threshold reached (3 accumulated abort/retry/failed attempts). Further attempts require a 'continuation_justification:' line in this file. The harness will refuse attempt 4 without it.
