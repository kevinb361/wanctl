---
phase: 181-production-footprint-reduction-and-reader-parity
plan: 01
status: partial
requirements-completed: ""
date: 2026-04-14
---

# Plan 181-01 Summary

## Shipped repo changes

- added [`scripts/compact-metrics-dbs.sh`](/home/kevin/projects/wanctl/scripts/compact-metrics-dbs.sh) for explicit per-WAN offline prune+vacuum work
- deployed the helper through [`scripts/deploy.sh`](/home/kevin/projects/wanctl/scripts/deploy.sh)
- documented the chosen storage-only reduction path in [181-footprint-reduction-design.md](/home/kevin/projects/wanctl/.planning/phases/181-production-footprint-reduction-and-reader-parity/181-footprint-reduction-design.md)

## Important execution correction

The first attempt to reduce footprint by shortening shipped `aggregate_5m_age_seconds` in the live WAN configs was backed out during execution.

Reason:
- production restarts immediately began colliding with the systemd watchdog budget
- pushing heavier retention cleanup into normal daemon startup was not safe enough

The reduction path for this phase therefore moved to the explicit offline helper instead of a runtime retention-profile change.

## Live outcome so far

- Spectrum offline compaction completed
- result: `5.2 GB -> 4.8 GB`
- saved: `408 MB`

That is real production footprint reduction, but it does not by itself close `STOR-06`.

Latest phase outcome:

- Spectrum remained materially smaller versus the fixed `2026-04-13` baseline
- ATT remained effectively unchanged versus baseline
- the startup regression that originally blocked later validation was fixed separately in the phase closeout

So Plan 01 is best treated as a partial reduction win, not as full requirement completion.
