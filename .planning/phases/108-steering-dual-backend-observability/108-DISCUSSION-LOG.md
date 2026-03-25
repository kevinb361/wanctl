# Phase 108: Steering Dual-Backend & Observability - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.

**Date:** 2026-03-25
**Phase:** 108-steering-dual-backend-observability
**Areas discussed:** Dual-backend wiring, Per-tin health endpoint, Per-tin metrics & history

---

## Dual-Backend Wiring

Claude recommended: CakeStatsReader alternate path for linux-cake (local tc), keep FailoverRouterClient for mangle rules. Steering config retains router section for mangle connectivity. User accepted.

## Per-Tin Health Endpoint

Claude recommended: Nest under congestion.primary.tins array, 4 dicts with tin_name + stats fields. Omit when not linux-cake. User accepted.

## Per-Tin Metrics & History

Claude recommended: New metric names with tin labels, --tins flag for wanctl-history. Only written for linux-cake transport. User accepted.

## Claude's Discretion

- Transport detection in CakeStatsReader, metric batch construction, history display format, test fixtures

## Deferred Ideas

- Per-tin dashboard sparklines, per-tin alerting, CakeStatsReader ABC refactor
