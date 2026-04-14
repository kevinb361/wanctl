---
phase: 183-dashboard-history-contract-audit
plan: 01
status: completed
requirements-completed: ""
date: 2026-04-14
---

# Plan 183-01 Summary

## Outcome

The Phase 183 audit is complete and it now records the current dashboard history behavior against code and docs instead of assumptions.

## Key findings

- `/metrics/history` still returns a `{data, metadata}` envelope with `metadata.source.mode` and `metadata.source.db_paths`, and it stays newest-first.
- The endpoint can emit `local_configured_db` for endpoint-local controller reads and `merged_discovery` for standalone fallback.
- `HistoryBrowserWidget` renders only `data` rows and summary stats; it does not read `metadata` or surface any source semantics.
- The dashboard tab currently exposes no operator handoff to the authoritative merged CLI path.
- The widget's degraded states cover generic fetch failure only and do not warn when source metadata is missing or ambiguous.

## Repo-side effect

- created [183-dashboard-ambiguity-audit.md](/home/kevin/projects/wanctl/.planning/phases/183-dashboard-history-contract-audit/183-dashboard-ambiguity-audit.md)

## Decision

Plan 02 can now lock the dashboard-facing contract directly against this audit without reopening backend history semantics.
