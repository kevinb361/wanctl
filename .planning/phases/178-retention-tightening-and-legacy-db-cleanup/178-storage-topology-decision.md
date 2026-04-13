# Phase 178 Storage Topology Decision

Date: 2026-04-13
Phase: 178-retention-tightening-and-legacy-db-cleanup
Plan: 178-01
Requirement: STOR-05

## Decision

Phase 178 keeps `/var/lib/wanctl/metrics.db` intentionally for steering and makes that role
explicit in shipped configuration. This plan does not retire or relocate the shared DB.

## Why `metrics.db` Remains Active Today

Phase 177 established that `/var/lib/wanctl/metrics.db` is not inert residue:

- the DB file and WAL had fresh `2026-04-13` mtimes
- fresh `metrics` rows were still present in the legacy DB
- steering still inherits `get_storage_config()` when `storage.db_path` is omitted

`configs/steering.yaml` previously omitted `storage.db_path`, so steering implicitly wrote to
the shared default in `src/wanctl/config_base.py`. That runtime behavior is now represented
explicitly in config instead of being left as tribal knowledge.

## Intended Runtime Topology After Plan 178-01

Authoritative active DB set:

- `/var/lib/wanctl/metrics-spectrum.db`
  - active autorate DB for Spectrum
  - authoritative for Spectrum autorate storage and retention
- `/var/lib/wanctl/metrics-att.db`
  - active autorate DB for ATT
  - authoritative for ATT autorate storage and retention
- `/var/lib/wanctl/metrics.db`
  - active shared DB for steering metrics
  - retained intentionally in Phase 178 because steering still uses it

This means the authoritative active DB set after this plan is three files, not one:
the two per-WAN autorate DBs plus the shared steering DB.

## Stale Zero-Byte Artifact Disposition

Phase 177 also found two files that are separate from the authoritative active DB set:

- `/var/lib/wanctl/spectrum_metrics.db`
- `/var/lib/wanctl/att_metrics.db`

Disposition for Phase 178:

- classify both files as stale zero-byte artifacts
- they are not part of the authoritative active DB set
- they may be removed during a host cleanup step because the evidence shows zero-byte size,
  older mtimes, and no repo-side references
- any cleanup must stay limited to these two files

This plan does not remove them from a live host directly. It closes the ambiguity by recording
that they are safe cleanup candidates while leaving active files untouched.

## What This Plan Does Not Do

- does not redesign storage discovery
- does not move steering onto a per-WAN DB
- does not delete `/var/lib/wanctl/metrics.db`
- does not mark `/var/lib/wanctl/metrics-spectrum.db` or `/var/lib/wanctl/metrics-att.db`
  for cleanup
- does not mark `/var/lib/wanctl/metrics.db`, `/var/lib/wanctl/metrics-spectrum.db`, or
  `/var/lib/wanctl/metrics-att.db` as stale artifacts

Those changes would require additional runtime validation because misclassifying an active DB
would be destructive.
