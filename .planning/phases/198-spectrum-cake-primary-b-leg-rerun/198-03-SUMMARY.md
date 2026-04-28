---
phase: 198-spectrum-cake-primary-b-leg-rerun
plan: 03
subsystem: validation
tags: [spectrum, flent, source-bind, throughput, valn-05a]

requires:
  - phase: 198-spectrum-cake-primary-b-leg-rerun
    plan: 02
    provides: Completed cake-primary B-leg duration gate and Phase 197 primary-signal audit
provides:
  - Three corrected Spectrum-bound tcp_12down flent raw captures
  - Per-run source-bind egress proof for 10.10.110.226
  - VALN-05a throughput verdict using the locked 2-of-3 plus median-of-medians rule
affects: [phase-198, valn-05a, plan-198-04-gate]

tech-stack:
  added: []
  patterns: [phase191-flent-helper-reuse, pre-run-egress-probe, median-of-medians-verdict]

key-files:
  created:
    - .planning/phases/198-spectrum-cake-primary-b-leg-rerun/soak/cake-primary/flent/run1.flent.gz
    - .planning/phases/198-spectrum-cake-primary-b-leg-rerun/soak/cake-primary/flent/run2.flent.gz
    - .planning/phases/198-spectrum-cake-primary-b-leg-rerun/soak/cake-primary/flent/run3.flent.gz
    - .planning/phases/198-spectrum-cake-primary-b-leg-rerun/soak/cake-primary/flent/manifest.json
    - .planning/phases/198-spectrum-cake-primary-b-leg-rerun/soak/cake-primary/throughput-verdict.json
  modified:
    - .planning/phases/198-spectrum-cake-primary-b-leg-rerun/soak/cake-primary/source-bind-egress-proof.json

key-decisions:
  - "Used `TCP download sum` from flent as the aggregate tcp_12down throughput series; the initial `TCP download avg` parse was per-stream average and was corrected before verdicting."
  - "Recorded the VALN-05a outcome as FAIL because only one median was at or above 532 Mbps and the median-of-medians was 494.834220 Mbps."

requirements-completed: []

duration: ~7m active execution
completed: 2026-04-28T15:38:46Z
---

# Phase 198 Plan 03: Corrected Spectrum tcp_12down flent Verdict Summary

**Three source-bound Spectrum flent captures were produced with per-run Charter egress proof, and VALN-05a failed under the locked 2-of-3 plus median-of-medians rule.**

## Performance

- **Tasks:** 2/2 complete
- **Runs captured:** 3 sequential `tcp_12down` runs, 30 seconds each, all with `--local-bind 10.10.110.226`
- **Egress:** all three pre-run probes resolved to `70.123.224.169` / `AS11427 Charter Communications Inc`
- **Regression slice:** 572 tests passed
- **Verdict:** `FAIL` — Plan 04 should not proceed without operator decision

## Throughput Result

| Run | Median Mbps | Egress IP | Egress Org | Raw artifact |
| --- | ---: | --- | --- | --- |
| 1 | 450.468331 | 70.123.224.169 | AS11427 Charter Communications Inc | `flent/run1.flent.gz` |
| 2 | 681.802267 | 70.123.224.169 | AS11427 Charter Communications Inc | `flent/run2.flent.gz` |
| 3 | 494.834220 | 70.123.224.169 | AS11427 Charter Communications Inc | `flent/run3.flent.gz` |

Acceptance rule, applied verbatim: `PASS` iff `medians_above_532 >= 2 AND median_of_medians_mbps >= 532`.

- `medians_above_532`: `1`
- `median_of_medians_mbps`: `494.834220`
- `two_of_three_at_or_above_532_mbps`: `false`
- `median_of_medians_at_or_above_532_mbps`: `false`
- `verdict`: `FAIL`

## Accomplishments

- Ran three pre-run `curl --interface 10.10.110.226 https://ipinfo.io/json` probes and preserved them in `source-bind-egress-proof.json` under `pre_run_probes[]` while retaining the Plan 01 `preflight_probe`.
- Captured three sequential raw flent files with the existing `scripts/phase191-flent-capture.sh` helper.
- Bundled the raw `.flent.gz` files into the phase evidence directory and created `flent/manifest.json` with external raw paths, egress linkage, sample counts, and aggregate median Mbps values.
- Created `throughput-verdict.json` with the locked VALN-05a rule, per-run medians, median-of-medians, 2-of-3 count, boolean rule components, and FAIL decision text.

## Task Commits

1. **Task 1: Three sequential flent runs with pre-each-run egress probe** — `5912acd`
2. **Task 2: Compute throughput verdict (2-of-3 + median-of-medians)** — `70c57e6`

## Verification

- `test $(ls .planning/phases/198-spectrum-cake-primary-b-leg-rerun/soak/cake-primary/flent/run[123].flent.gz 2>/dev/null | wc -l) -eq 3` — PASS
- Python gzip/JSON parse of all three `.flent.gz` files and `TCP download sum` series — PASS
- `jq -e '(.preflight_probe.egress_ip_matches == true) and (.pre_run_probes | length) == 3 and all(.pre_run_probes[]; .egress_ip_matches == true and (.org | test("Charter|AS11427")))' source-bind-egress-proof.json` — PASS
- `jq -e '(.rule == "VALN-05a: medians_above_532 >= 2 AND median_of_medians_mbps >= 532") and ((.verdict == "PASS") == ((.medians_above_532 >= 2) and (.median_of_medians_mbps >= 532)))' throughput-verdict.json` — PASS
- `git diff --quiet -- src/wanctl/` — PASS
- `.venv/bin/pytest -o addopts='' tests/test_cake_signal.py tests/test_queue_controller.py tests/test_wan_controller.py tests/test_health_check.py -q` — PASS (`572 passed in 39.54s`)

## Decisions Made

- The aggregate throughput median is computed from flent `TCP download sum`, not `TCP download avg`, because `tcp_12down` uses 12 streams and `avg` is per-stream average.
- The failed throughput rule is recorded as a real validation outcome, not retried or hidden; Plan 04 is blocked pending operator direction.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Corrected flent aggregate median parser**
- **Found during:** Task 1 manifest generation
- **Issue:** The first parser selected `TCP download avg`, which is the per-stream average and understated total tcp_12down throughput by roughly 12x.
- **Fix:** Recomputed manifest medians from `TCP download sum`, preserved sample counts, and verified the gzip JSON contents before committing.
- **Files modified:** `flent/manifest.json`
- **Commit:** `5912acd`

**2. [Rule 3 - Blocking] Used documented non-interactive doc-check bypass for evidence commits**
- **Found during:** Task commits
- **Issue:** The repository pre-commit documentation hook opened an interactive prompt for evidence artifacts containing security-related terms.
- **Fix:** Used the repository-documented `SKIP_DOC_CHECK=1` environment variable, matching Phase 197 precedent, while still running normal git hooks and never using `--no-verify`.
- **Files modified:** none
- **Commit:** `5912acd`, `70c57e6`

## Issues Encountered

- VALN-05a failed: medians were `450.468331`, `681.802267`, and `494.834220` Mbps. Only one run met the 532 Mbps individual threshold, and the median-of-medians was below 532 Mbps.
- Existing untracked `graphify-out/` remained unrelated and was left untouched.

## Known Stubs

None.

## Threat Flags

None.

## Next Phase Readiness

Not ready for autonomous `198-04` closeout. The throughput verdict explicitly says: `VALN-05a throughput acceptance failed; do not proceed to Plan 04 closeout without operator decision.`

---
*Phase: 198-spectrum-cake-primary-b-leg-rerun*
*Completed: 2026-04-28T15:38:46Z*

## Self-Check: PASSED

- Found `run1.flent.gz`, `run2.flent.gz`, `run3.flent.gz`, `flent/manifest.json`, `source-bind-egress-proof.json`, and `throughput-verdict.json` on disk.
- Found task commits `5912acd` and `70c57e6` in git history.
- Verified no `src/wanctl/` files were modified.
