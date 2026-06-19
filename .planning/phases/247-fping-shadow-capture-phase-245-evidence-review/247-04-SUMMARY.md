---
phase: "247"
plan: "04"
status: complete
completed_at: "2026-06-19T13:45:00-05:00"
requirements:
  - PROF-01
  - PROF-02
key_files:
  created:
    - .planning/phases/247-fping-shadow-capture-phase-245-evidence-review/evidence/phase247-fping-shadow.ndjson
    - .planning/phases/247-fping-shadow-capture-phase-245-evidence-review/evidence/phase247-shadow-summary.json
  modified:
    - .planning/phases/247-fping-shadow-capture-phase-245-evidence-review/evidence/safe18-boundary-247.json
verification:
  - clean SIGINT stop produced probe_stats_final
  - copied NDJSON from cake-shaper runtime storage into phase evidence
  - generated full-window phase247-shadow-summary.json from probe_cycle records
  - bash scripts/phase247-safe18-boundary-check.sh
---

# Plan 247-04 Summary — fping Shadow Soak Evidence

## Outcome

Stopped the Phase 247 fping shadow soak early by operator decision; the captured window is sufficient to move forward. The process was stopped cleanly with SIGINT and wrote a final `probe_stats_final` record.

Runtime output on cake-shaper:

- Source NDJSON: `/var/lib/wanctl/phase247-fping-shadow.ndjson`
- Runtime log: `/var/log/wanctl/phase247-shadow.log`
- Run user: `wanctl`
- Config: `/etc/cake-autorate/config.spectrum.sh`
- Script: `/opt/wanctl/scripts/phase247-fping-shadow.py`

Phase evidence copied into the repo:

- `.planning/phases/247-fping-shadow-capture-phase-245-evidence-review/evidence/phase247-fping-shadow.ndjson`
- `.planning/phases/247-fping-shadow-capture-phase-245-evidence-review/evidence/phase247-shadow-summary.json`

## Full-window summary

Computed from `probe_cycle` records, not rolling `probe_stats.p99_ms`:

- Duration: 6.964 h
- Probe cycles: 2299
- Successful cycles: 2299
- Success rate: 100.0%
- All-loss cycles: 0
- Inferred/drop cycles: 0
- Final stats records: 1

RTT distribution:

- min: 18.05 ms
- median: 21.8 ms
- avg: 22.91 ms
- p95: 29.55 ms
- p99: 38.15 ms
- max: 101.75 ms

fping probe elapsed distribution:

- min: 884.95 ms
- median: 893.49 ms
- avg: 897.04 ms
- p95: 913.97 ms
- p99: 946.65 ms
- max: 1074.00 ms

## Interpretation

The shadow soak supports moving forward to Phase 248 switch-eligibility analysis:

- fping shadow capture was stable for the partial window.
- No inferred drops occurred.
- No all-loss probe-cycle records occurred.
- RTT median is below both Phase 245 medians (`fping=33.22 ms`, `icmplib=33.58 ms`), though the Phase 247 window uses the active cake-autorate reflector set and is not a concurrent icmplib comparison.
- Phase 245's rollback was already diagnosed as an invalid absolute cycle-p99 gate (`CYCLE_P99_ABS_CEILING_MS=10.0`) rather than a demonstrated fping inferiority: fping was better than icmplib on relative daemon-cycle p99 in that observed window.

This plan does not flip production defaults. It closes the shadow evidence capture and hands the decision to Phase 248.

## Verification

Observed stop/finalization:

- `pgrep -af "[p]hase247-fping-shadow.py"` returned no running process after SIGINT.
- Runtime log recorded `caught signal 2`, `fping thread stopped`, and `shadow capture complete; total_observed_probes=2299`.
- Last NDJSON record was `type="probe_stats_final"`.

SAFE-18 should remain the phase boundary guard before closeout.

## Self-check: PASSED
