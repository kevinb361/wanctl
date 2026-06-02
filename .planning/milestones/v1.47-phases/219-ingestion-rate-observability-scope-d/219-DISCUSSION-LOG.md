# Phase 219: Ingestion-Rate Observability (Scope D) — Discussion Log

**Discussed:** 2026-05-29
**Mode:** default (4 single-area turns, batched recommendations)

## Pre-loaded context (carried forward, not re-asked)

From `.planning/research/PITFALLS.md` and `.planning/research/SUMMARY.md`:

- Hot-path safety: out-of-band CLI only, no daemon writes (Pitfall 5)
- Staleness fields mandatory, match v1.38 `measurement_stale` precedent (Pitfall 7)
- Read tolerance: per-table read failure → null per table, never abort (v1.44 TOOL-03)
- `/health.metrics.ingestion` block deferred unless Phase 218 audit proves CLI insufficient (ARCH-09 stop-line)
- Mutation boundary: additive edits to `src/wanctl/history.py` allowlisted; controller files forbidden (SAFE-11)
- D-first ordering: Phase 219 ships before Phase 220 matrix work (Pitfall 11)

## Gray areas presented

User selected all four (multi-select), with "you decide" annotation indicating the recommendations should drive the decisions.

## Area 1: Snapshot vs live-query model

**Options presented:**
- (a) Live-query + single fetch_time (Recommended)
- (b) CLI reads from snapshot file
- (c) Hybrid: live by default, `--from-snapshot` to read file

**User selection:** Live-query + single fetch_time

**Rationale captured in CONTEXT.md:**
- CLI stays stateless; no new daemon state path (Pitfall 5)
- `_snapshot_unix` = batch-start wall-clock, carried into every row in one invocation
- "Snapshot" semantic is produced at the file-consumer layer by `phase219-ingestion-digest.py` persisting the JSON

## Area 2: JSON output shape

**Options presented:**
- (a) Flat rows + discriminator fields (Recommended)
- (b) Nested map `{wan: {window: {table: row}}}`
- (c) Separate `rolling[]` and `by_table[]` arrays

**User selection:** Flat rows + discriminator fields

**Rationale captured in CONTEXT.md:**
- Append-only extension of history.py:683–691 pattern
- Easy fixture pin against a literal row list
- `table_name` / `window_seconds` discriminator fields explicit
- Backward-compatible with v1.44 Phase 208 default-flag mode

## Area 3: Dominant-table tie-break (operator-summary --digest)

**Options presented:**
- (a) >=20% lead, else `mixed: top1/top2` (Recommended)
- (b) Alphabetical first on tie
- (c) First-encountered (insertion order)
- (d) Always top-2: `table1, table2`

**User selection:** >=20% lead, else `mixed: top1/top2`

**Rationale captured in CONTEXT.md:**
- Honest one-glance signal: near-ties surface as `mixed:`, not silently as one winner
- 20% matches by-design-vs-anomaly threshold elsewhere
- Both branches deterministic + fixture-testable

## Area 4: Snapshot target + retention

**Options presented:**
- (a) `/var/lib/wanctl/snapshots/ingestion/`, atomic, retain 288 (Recommended)
- (b) Same path, retain by age (24h)
- (c) `/run/wanctl/snapshots/` (tmpfs)
- (d) Operator-configurable path via flag/env

**User selection:** `/var/lib/wanctl/snapshots/ingestion/`, atomic, retain 288

**Rationale captured in CONTEXT.md:**
- Persistent dir per CLAUDE.md layout — survives reboot (Phase 218 audit window safety)
- `.tmp` + `os.rename()` atomic write pattern (universal)
- Count-based retention avoids per-cron `stat()`/`unlink()` sweeps
- ~288 × 10KB = 3MB ceiling, flash-safe
- 24h coverage at 5-min cron cadence

## Folded todos

| Todo | Status |
|---|---|
| `2026-04-17-ingestion-rate-tool.md` (score 0.6) | **Folded** — already tagged `resolves_phase: 219`. Smoothing intent satisfied by `--rolling=60,300,3600`. |

## Reviewed but not folded

| Todo | Status |
|---|---|
| `2026-04-17-operator-summary-digest-permission-handling.md` (score 0.6) | **Noted** — PermissionError handling in `operator-summary --digest` is tangentially related (read-tolerance pattern). Not folded into Phase 219 scope; the new ingestion block should follow the same tolerance pattern but the PermissionError fix is its own todo. |
| `2026-04-08-investigate-tcp-12down-latency-spikes-under-multi-flow-downl.md` (score 0.6) | Not relevant — Scope A/matrix work, belongs to Phase 220. |
| `2026-04-17-investigate-steering-degraded-on-clean-restart.md` (score 0.6) | Not relevant — steering, out of scope. |
| `2026-04-17-monitor-flapping-peak-count-on-next-docsis-event.md` (score 0.6) | Not relevant — Phase 218 watch-list, parallel work. |
| `2026-04-28-add-silicom-bypass-test-harness.md` (score 0.6) | Not relevant — bypass NIC. |
| `2026-04-24-resolve-att-cake-primary-canary-after-phase-196.md` (score 0.4) | Not relevant. |
| `2026-04-28-add-silicom-bypass-nic-operational-tooling.md` (score 0.4) | Not relevant. |

## Deferred ideas surfaced during discussion

- `/health.metrics.ingestion` daemon-side block — locked deferred (ARCH-09 stop-line)
- Per-metric category grouping — P2, post-v1.47
- Zero-row anomaly hints — P2
- Operator-configurable snapshot path — v2
- Threshold-based ingestion alerts — explicit anti-feature for v1.47

## Claude's discretion (documented)

- Argparse mutual-exclusion handling between new flags and legacy `--summary`
- Exact column set for non-JSON (table) view of bucketed output
- Whether to emit per-snapshot staleness fields in default-flag mode (recommended: yes)
- Internal structure of `_per_wan_ingestion_rate_bucketed()` (single SQL grouped pass vs N per-table calls) — planner to research
- Alphabetical ordering inside the `mixed:` payload

---

*Generated by /gsd:discuss-phase on 2026-05-29.*
