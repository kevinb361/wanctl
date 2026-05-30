# Architecture: v1.47 Measurement Evidence Closure

**Domain:** wanctl adaptive CAKE controller — read-only evidence harness extensions
**Researched:** 2026-05-29
**Scope:** Integration design for (A) `tcp_12down` target/path sensitivity matrix and (D) ingestion-rate observability tool
**Confidence:** HIGH — anchored on Phase 214 evidence-only pattern already in production and Phase 208 `wanctl-history --ingestion-rate` already shipped.

## Architectural Anchors (Non-Negotiable)

These predate v1.47 and constrain every design choice below:

- **ARCH-01** Link-agnostic controller — no per-WAN Python branching. Any per-target / per-path knob lives in YAML/JSON config, not in `src/wanctl/`.
- **ARCH-09** `/health` payload shape is contractual — additive fields only.
- **ARCH-12** Hot-path I/O is deferred off the 50ms control thread. New synchronous SQLite or subprocess calls in the cycle are forbidden.
- **ARCH-17** Per-WAN SQLite WAL with retention + downsampling — schema changes require explicit migration.
- **ARCH-20** Stability > safety > clarity > elegance. Read-only until evidence isolates a cause.
- **Phase 214 mutation-boundary contract** — A scope MUST NOT mutate `src/wanctl/` at all (D-14 triple-check guard enforces it in CI/local). D scope MAY touch `history.py` and/or `health_check.py` only if `read-only-over-DB` analysis proves insufficient.

## Recommended Architecture — Scope A (tcp_12down matrix)

**One-liner:** Pure `scripts/` + `.planning/perf/` extension of the Phase 214 wrapper pattern. Zero `src/wanctl/` mutation. Operator-supplied matrix definition. Closeout report draws evidence from per-cell `signal-sheet.json` artifacts via the same `phase214-matrix-summary.py` aggregator shape.

### Component Boundaries

| Component | Responsibility | Communicates With |
|-----------|---------------|-------------------|
| `phase220-target-path-matrix.sh` (new) | Per-cell wrapper; reads matrix YAML; iterates cells; delegates per-cell traffic to `phase213-baseline-capture.sh`; D-14 triple-check src-diff guard; per-cell journal pull; sidecar manifest | `phase213-baseline-capture.sh`, `ssh cake-shaper`, `.planning/phases/220-.../evidence/` |
| `phase220-matrix.yaml` (new, operator-supplied) | Matrix definition: target hosts × source binds × window labels × flent test names × per-cell duration overrides | Read by `phase220-target-path-matrix.sh` |
| `phase214-extract.py` (reused as-is) | Fail-closed flent latency / throughput extractor | Imported via `importlib.util` by classifier (already the pattern) |
| `phase214-align.py` (reused as-is) | Per-second alignment of flent ping + `/health` NDJSON | Reads RUN tree artifacts |
| `phase214-classify.py` (reused as-is OR forked thin) | Six-driver classifier per cell → `signal-sheet.json` | Reads aligned-window JSON + journal NDJSON |
| `phase220-matrix-aggregator.py` (new, forked from `phase214-matrix-summary.py`) | Roll up per-cell `signal-sheet.json` into target/path/window verdict cube + closeout-grade `matrix-summary.json` | Reads `.planning/phases/220-.../evidence/RUN-*/...` |
| `220-CLOSEOUT.md` (new, hand-authored from aggregator output) | Closeout decision report: defect located / hypothesis killed / carried-narrower | Cites `matrix-summary.json` cells |

### Data Flow

```
operator: phase220-target-path-matrix.sh --cell <cell-id> <window>
   │
   ├── reads phase220-matrix.yaml → resolves cell (target_host, source_bind, test, duration)
   ├── D-14 triple-check: unstaged + staged + committed-since-base src/wanctl/ diff guard
   ├── window-hour gate (off-peak | daytime | prime-time, same as 214 wrapper)
   └── delegates to phase213-baseline-capture.sh \
            --bind-map <wan>=<source_bind> \
            --wans <wan> \
            --tests <test> \
            --flent-duration <duration> \
            --host <target_host> \
            --evidence-root .planning/phases/220-target-path-matrix/evidence
        │
        └── produces RUN-<ts>/<wan>/<test>/{flent.gz, health.ndjson, manifest.json}
   │
   ├── post-run: ssh cake-shaper journalctl --since=@t_start --until=@t_end → journal-window.ndjson
   └── writes phase220-cell.json sidecar (cell-id, target, bind, window, git_head_sha, mutation_posture)

then offline (operator may batch):
   phase214-align.py  → aligned-window.json (per cell)
   phase214-classify.py → signal-sheet.{json,md} (per cell)
   phase220-matrix-aggregator.py → matrix-summary.json (cube across cells)
       │
       └── inputs to 220-CLOSEOUT.md verdict
```

### Mutation-Boundary Contract (Carried From Phase 214)

The wrapper enforces D-14 verbatim, with one upgrade: the matrix may run across multiple commit windows over days, so the base SHA goes in `phase220-matrix.yaml` (`base_sha:` field) instead of an env var. The wrapper still triple-checks (unstaged + staged + committed-since-base).

**Result:** `src/wanctl/` is unchanged through all of Scope A. Phase 214's existing mutation-boundary tests (`tests/test_phase214_mutation_boundary.py` — if present, otherwise the convention) are extended to cover phase220 scripts.

### Matrix Definition — Where It Lives

**Decision: operator-supplied YAML at `scripts/phase220-matrix.yaml`** (not JSON, not hardcoded, not `.planning/`).

Rationale:
- Operator edits without touching scripts (consistent with `configs/*.yaml` ethos).
- YAML allows comments next to each cell rationale (target choice, expected signal, prior p99).
- Lives in `scripts/` because it is harness configuration, not phase research — it survives across the 3-phase v1.47 milestone.
- `.planning/phases/220-.../evidence/RUN-*/phase220-cell.json` records the resolved cell, so the YAML is reproducible from artifacts even if it later changes.

**Shape (illustrative, not normative):**
```yaml
base_sha: <phase220 mutation-boundary base>
default_duration_sec: 30
cells:
  - id: vultr-dallas-baseline
    target: dallas              # phase213 host alias
    wan: spectrum
    source_bind: 10.10.110.226
    test: tcp_12down
    duration_sec: 30
    rationale: "Phase 214 canonical Spectrum/Dallas — anchor cell."
  - id: vultr-chicago
    target: chicago
    wan: spectrum
    source_bind: 10.10.110.226
    test: tcp_12down
    rationale: "Phase 214 supplemental p99 651ms — hypothesis live."
  - id: vultr-dallas-att-contrast
    target: dallas
    wan: att
    source_bind: 10.10.110.233
    test: tcp_12down
    rationale: "Path-wide vs Spectrum-specific disambiguation."
  # Additional cells per operator scoping at v1.47 plan time
```

### Closeout Decision Report — How It Draws Evidence

`phase220-matrix-aggregator.py` produces a `matrix-summary.json` shaped as a 3-D cube:

```json
{
  "cells": [
    {"cell_id": "...", "target": "...", "wan": "...", "window": "...",
     "p50_ms": ..., "p95_ms": ..., "p99_ms": ...,
     "verdict": "pass|ambiguous|fail",
     "primary_driver": "reflector_loss|...",
     "ranked_drivers": [...],
     "signal_disposition": "form_a|form_b|form_c|none"}
  ],
  "rollups": {
    "by_target":   {"dallas": {...}, "chicago": {...}},
    "by_wan":      {"spectrum": {...}, "att": {...}},
    "by_window":   {"off-peak": {...}, "daytime": {...}, "prime-time": {...}}
  },
  "matrix_verdict": "defect_located | hypothesis_killed | carried_narrower",
  "carry_narrower_reasons": [...]
}
```

The operator-authored `220-CLOSEOUT.md` consumes this and renders the explicit verdict per v1.47 PROJECT.md goal — no production tuning unless evidence isolates a cause.

## Recommended Architecture — Scope D (ingestion-rate observability)

**One-liner:** Strictly bounded scope. Default path is CLI-only enhancement to existing `wanctl-history --ingestion-rate` (v1.44 Phase 208 surface). Only escalate to a daemon-side counter (`history.py` and/or `health_check.py` additive field) if Phase 218 audit explicitly proves the SQL-after-the-fact path is insufficient.

### Existing Surface (DO NOT REBUILD)

`src/wanctl/history.py` already implements (v1.44 Phase 208 TOOL-02):
- `--ingestion-rate` CLI flag.
- `_per_wan_ingestion_rate(db_paths, start_ts, end_ts, wan, metrics)` — per-WAN row counter over a window.
- `format_ingestion_rate_table()` and `format_ingestion_rate_json()` — operator-readable outputs.
- Per-WAN DB filename filter (`metrics-<wan>.db`) + legacy/ad-hoc `--db` + `--wan` SQL filter semantics.
- Unreadable DBs surface as 0-row entries (fail-visible, not fail-silent).

**This is the boundary.** v1.47 Scope D extends, never replaces, this surface.

### Component Boundaries (Default Path — CLI-Only)

| Component | Responsibility | Communicates With |
|-----------|---------------|-------------------|
| `history.py` (modified, additive) | New `--ingestion-rate-bucketed` flag: emit per-bucket rows/sec series over the window (e.g., 60s buckets) instead of one aggregate row | Existing `count_metrics()` reader; bucketed via `granularity` + repeated SQL or a new bucketed reader fn |
| `reader.py` (possibly modified, additive) | New `count_metrics_bucketed(start_ts, end_ts, bucket_sec)` helper if not already expressible via existing reader | Same SQLite WAL DBs |
| `phase221-ingestion-rate-audit.sh` (new) | Operator script: snapshot per-WAN ingestion rate over the Phase 218 audit window; write to `.planning/perf/` for evidence | Calls `wanctl-history --ingestion-rate-bucketed --json` |

**Mutation surface:** `src/wanctl/history.py` (+ possibly `src/wanctl/storage/reader.py`), additive only. Both files are operator-tooling, not controller-path — SAFE-09 precedent from v1.44 Phase 208 (TOOL-01/02/03) applies: `history.py` is on the operator-tooling allowlist, not the controller-path forbid list.

### Component Boundaries (Escalation Path — IF AND ONLY IF Required)

Reach for this only if `Phase 218 audit` evidence proves bucketed SQL is insufficient (e.g., the audit needs sub-second write-rate granularity that DB-row-counting cannot reconstruct).

| Component | Responsibility | Communicates With |
|-----------|---------------|-------------------|
| `storage/writer.py` (modified, additive) | Bump per-WAN `write_count` atomic counter on each `write_metric` / `write_metrics_batch` / `write_alert` / `write_reflector_event` | In-memory; not on hot path because `DeferredIOWorker` already runs off-thread (ARCH-12) |
| `storage/deferred_writer.py` (modified, additive) | Expose `get_write_counts() -> dict[str, int]` for periodic snapshot | Health check reader |
| `health_check.py` (modified, additive) | New `/health.storage.ingestion` sub-block with `{rows_written_total, rows_per_sec_1m, rows_per_sec_5m}` per-WAN | DeferredIOWorker snapshot |

**Critical constraint:** Counter increments must stay in the deferred worker (off the 50ms loop) per ARCH-12. The 1m/5m sliding windows are computed at `/health` GET time from a small ring buffer maintained by the deferred worker — not on the control thread.

### Periodic Flush vs Sliding Window

- **CLI-only path:** No daemon-side counter; SQL row count over operator-chosen window. Naturally a "look-back" window, not a sliding window. Interacts cleanly with retention/downsample because it queries the raw `metrics` table over a bounded `start_ts..end_ts` range.
- **Escalation path:** Sliding window (1m + 5m) at `/health` is computed from a ring buffer in `DeferredIOWorker`. Does NOT touch retention/downsample because the counter is in-process memory, not on disk. Daemon restart resets the counter — this is fine because `/health.uptime` discloses the reset implicitly.

### Boundary: vs Existing `wanctl-history --ingestion-rate` (v1.44 Phase 208)

| Capability | v1.44 Phase 208 (shipped) | v1.47 Scope D (proposed) |
|-----------|---------------------------|---------------------------|
| Per-WAN row count over window | Yes | Reused as-is |
| Single aggregate rows/sec | Yes | Reused as-is |
| JSON + table output | Yes | Reused as-is |
| `--wan` filter | Yes | Reused as-is |
| **Bucketed time series across window** | No | New (`--ingestion-rate-bucketed`) |
| **Real-time write counter in `/health`** | No | Escalation-only, gated on Phase 218 evidence |
| **Phase 218 audit harness script** | No | New (`phase221-ingestion-rate-audit.sh`) |

**Stop line:** if the bucketed CLI path satisfies Phase 218 audit needs, do NOT cut the escalation path. The escalation path's additive `/health` block is a contractual surface (ARCH-09) and costs perpetual support.

## Patterns to Follow

### Pattern 1: Phase 214 Wrapper Composition Pattern
**What:** Thin per-window/per-cell `bash` wrapper that (a) gates entry, (b) triple-checks `src/wanctl/` cleanliness, (c) delegates traffic generation to `phase213-baseline-capture.sh`, (d) post-pulls journal NDJSON via SSH, (e) writes a phase-owned sidecar manifest.

**When:** Any read-only evidence-capture phase that needs `tcp_12down` (or similar flent test) data correlated with `/health` NDJSON.

**Example:** `scripts/phase214-flent-matrix.sh` (verbatim reference).

### Pattern 2: Stdlib-Only Offline Analyzer Pattern
**What:** Python analyzers import `phase214_extract` via `importlib.util.spec_from_file_location` (NOT a regular `import`) to make the dependency on `phase214-extract.py` explicit and to avoid coupling analyzers to a Python package.

**When:** Any phase that needs to compute percentiles from flent artifacts.

**Example:** `scripts/phase214-classify.py:41-49`. Reuse for Scope A.

### Pattern 3: Mutation-Boundary Test Pattern
**What:** A pytest test (e.g., `tests/test_phase214_mutation_boundary.py`) that diffs `src/wanctl/` against the phase base SHA and fails if any source mutation is present. Pinned to the phase wrapper.

**When:** Phases that contract zero controller-path mutation.

**Example:** Carry forward for Scope A; not needed for Scope D (which is additive-allowed in `history.py`).

### Pattern 4: Additive `/health` Sub-Block Pattern (Escalation Only)
**What:** New optional sub-block under existing top-level key, never renaming or removing fields. Numeric metrics only (per Phase 195/v1.40 convention — no string labels for Prometheus).

**When:** Operator visibility needs that cannot be served by offline CLI tools.

**Example:** `signal_arbitration` block from v1.40, `download.hysteresis.dwell_bypassed_count` from Phase 192.

## Anti-Patterns to Avoid

### Anti-Pattern 1: Hardcoded matrix definition in the shell wrapper
**Why bad:** Operator edits require shell-script diff review; rationale comments get lost; reproducibility from artifacts is broken.
**Instead:** YAML at `scripts/phase220-matrix.yaml` + resolved cell in sidecar.

### Anti-Pattern 2: New Python module in `src/wanctl/` for matrix orchestration
**Why bad:** Violates Phase 214 mutation-boundary contract; couples evidence harness to controller release cycle; triggers SAFE-09-class allowlist debates.
**Instead:** Scripts in `scripts/`. The harness is allowed to be Python; it just lives next to other `phase21X-*.py` analyzers.

### Anti-Pattern 3: Hot-path write counter for Scope D
**Why bad:** Violates ARCH-12 (hot-path I/O off control thread). Adds synchronous counter mutation to the 50ms cycle.
**Instead:** Counter lives in `DeferredIOWorker` — already off-thread.

### Anti-Pattern 4: Replacing `wanctl-history --ingestion-rate` instead of extending it
**Why bad:** Breaks operator muscle memory; v1.44 Phase 208 contract is shipped; "bucketed" is purely additive.
**Instead:** New `--ingestion-rate-bucketed` flag alongside existing `--ingestion-rate`.

### Anti-Pattern 5: Per-target Python branching in `phase220-*` scripts
**Why bad:** Same trap ARCH-01 prevents in controller. Operator-supplied matrix YAML keeps the harness link-agnostic.
**Instead:** YAML cells; the script iterates the cube without knowing target identities.

## Integration Points — New vs Modified Files (Explicit)

### Scope A — new files

| Path | Purpose |
|------|---------|
| `scripts/phase220-target-path-matrix.sh` | Per-cell wrapper (Pattern 1) |
| `scripts/phase220-matrix.yaml` | Operator-supplied matrix definition |
| `scripts/phase220-matrix-aggregator.py` | Forked from `phase214-matrix-summary.py`; cube rollup |
| `.planning/phases/220-target-path-matrix/220-CLOSEOUT.md` | Hand-authored decision report |
| `.planning/phases/220-target-path-matrix/evidence/RUN-*/...` | Generated per-cell artifacts |
| `tests/test_phase220_mutation_boundary.py` | Carry mutation-boundary pattern |

### Scope A — reused unchanged

- `scripts/phase213-baseline-capture.sh`
- `scripts/phase214-extract.py`
- `scripts/phase214-align.py`
- `scripts/phase214-classify.py`

### Scope A — modified

**None.** Zero `src/wanctl/` mutation. Zero modification of existing `phase21*` scripts.

### Scope D — modified (default path)

| Path | Modification |
|------|--------------|
| `src/wanctl/history.py` | Additive: `--ingestion-rate-bucketed` flag + `_per_wan_ingestion_rate_bucketed()` helper + `format_ingestion_rate_bucketed_{table,json}()` formatters |
| `src/wanctl/storage/reader.py` | Additive (if needed): `count_metrics_bucketed(start_ts, end_ts, bucket_sec, ...)` |

### Scope D — new files (default path)

| Path | Purpose |
|------|---------|
| `scripts/phase221-ingestion-rate-audit.sh` | Phase 218-audit-window snapshot script |
| `tests/test_history_ingestion_rate_bucketed.py` | Coverage for new flag |

### Scope D — modified (escalation path, gated on Phase 218 evidence)

| Path | Modification |
|------|--------------|
| `src/wanctl/storage/writer.py` | Additive per-WAN write counter |
| `src/wanctl/storage/deferred_writer.py` | Snapshot accessor + 1m/5m ring buffer |
| `src/wanctl/health_check.py` | Additive `/health.storage.ingestion` sub-block |

## Suggested Build Order (Cross-Phase Dependencies)

The roadmap should target three phases. Build order matters because the closeout report depends on the matrix runner, and Phase 218 may inform whether Scope D escalates.

**Phase v1.47-A1 — Matrix Runner (Scope A, harness only)**
1. `scripts/phase220-target-path-matrix.sh` (Pattern 1 carry-forward)
2. `scripts/phase220-matrix.yaml` (operator-authored initial cell set)
3. `scripts/phase220-matrix-aggregator.py` (cube rollup)
4. `tests/test_phase220_mutation_boundary.py`

   Gate: D-14 src-diff guard passing; dry-run regression test green; one wet `daytime` cell against the Phase 214 anchor (Spectrum/Dallas) to confirm the harness reproduces Phase 214 verdict.

**Phase v1.47-A2 — Matrix Evidence + Closeout (Scope A, evidence)**
1. Operator-driven matrix runs (off-peak × daytime × prime-time × N cells).
2. Per-cell `phase214-classify.py` runs → `signal-sheet.json`.
3. `phase220-matrix-aggregator.py` → `matrix-summary.json`.
4. `.planning/phases/220-.../220-CLOSEOUT.md`: explicit verdict.

   Gate: matrix verdict = `defect_located` | `hypothesis_killed` | `carried_narrower` with rationale.

**Phase v1.47-D — Ingestion-Rate Observability (Scope D, default path first)**
1. `src/wanctl/history.py` additive `--ingestion-rate-bucketed`.
2. `src/wanctl/storage/reader.py` additive bucketed helper if needed.
3. `scripts/phase221-ingestion-rate-audit.sh`.
4. `tests/test_history_ingestion_rate_bucketed.py`.

   Gate: Phase 218 audit window can be reconstructed from CLI output. If yes, STOP — do not cut escalation path. If no, document the evidence gap in the phase SUMMARY and route escalation-path work to v1.48+.

### Cross-Phase Dependency Notes

- A1 → A2: A2 cannot start until A1's wrapper exists. A2 is operator-driven, so the agent only builds A1; A2 evidence is operator-captured between agent runs.
- D is independent of A and may run in parallel with A1/A2.
- Phase 218 (v1.46 carry-forward, event-gated) is parallel and may consume D output for its audit, but D does NOT block on Phase 218 firing.

## Scalability Considerations

| Concern | Single cell | Full matrix (≥9 cells) | Year-long evidence corpus |
|---------|-------------|------------------------|----------------------------|
| Disk under `.planning/phases/220-.../evidence/` | ~5MB | ~50MB | Periodic archive to `.planning/perf/` per v1.46 closeout pattern |
| SSH session count to `cake-shaper` | 1 per run | 1 per cell | No change — sequential, not concurrent |
| Aggregator runtime | <1s | <5s | Bounded by cell count, not history |
| `/health.storage.ingestion` ring buffer (escalation) | n/a | n/a | 5m × 2 windows = ~600 floats per WAN — trivial |

## Open Questions for Roadmapper

1. **Phase boundary:** Should A1 (wrapper) + A2 (evidence + closeout) be one phase or two? Phase 214 was one phase that included both wrapper-build and operator-driven evidence. Recommend same single-phase shape for v1.47-A, with A1/A2 as plans within it.
2. **Scope D default-vs-escalation decision point:** Who decides? Recommend the roadmap fix the decision to "Phase 218 audit lead at audit time," not v1.47 planning time.
3. **Phase 220 vs Phase 219 numbering:** v1.46 closed at Phase 218 (event-gated). v1.47 should number starting at Phase 219 unless 218 closes first.

## Sources

- `.planning/PROJECT.md` (v1.47 scope statement) — HIGH
- `.planning/intel/arch.md` (ARCH-01, 09, 12, 17, 20) — HIGH
- `.planning/milestones/v1.46-phases/214-measurement-collapse-investigation/214-CONTEXT.md` — HIGH
- `.planning/milestones/v1.46-phases/214-measurement-collapse-investigation/214-01-PLAN.md` — HIGH
- `scripts/phase214-flent-matrix.sh` (Pattern 1 reference) — HIGH
- `scripts/phase214-extract.py` (Pattern 2 reference) — HIGH
- `scripts/phase214-classify.py` (importlib pattern) — HIGH
- `scripts/phase214-matrix-summary.py` (aggregator fork base) — HIGH
- `src/wanctl/history.py:438-489, 558-567, 651-696` (existing `--ingestion-rate` surface) — HIGH
- `src/wanctl/storage/writer.py`, `storage/deferred_writer.py` (escalation-path anchors) — HIGH
- CLAUDE.md (Change Policy, mutation discipline) — HIGH
