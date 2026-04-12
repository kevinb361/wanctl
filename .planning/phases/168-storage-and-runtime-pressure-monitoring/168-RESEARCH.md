# Phase 168: Storage And Runtime Pressure Monitoring - Research

**Researched:** 2026-04-11
**Domain:** Bounded storage and runtime pressure observability for long-running autorate and steering daemons
**Confidence:** MEDIUM

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Reuse existing in-memory telemetry and health/metrics surfaces where possible.
- Do not add new SQLite tables or noisy high-rate writes just to observe storage/runtime pressure.
- Keep signals bounded and operator-oriented; this phase is about visibility, not autonomous remediation.
- Cover both autorate and steering where the same pressure signal is relevant.

### Claude's Discretion
None explicitly listed in `168-CONTEXT.md`. [VERIFIED: .planning/phases/168-storage-and-runtime-pressure-monitoring/168-CONTEXT.md]

### Gray areas resolved for planning
- It is acceptable to add low-rate filesystem/runtime inspection at read/export time if it does not create material hot-path cost.
- It is acceptable to add alert-ready severity/status fields to health/metrics as long as payload shape stays stable and bounded.
- Production validation should use healthy live services plus current DB/WAL/runtime state; it should not force a failure condition on the host.

### Deferred Ideas (OUT OF SCOPE)
- Alert thresholds and notification policy beyond what is necessary for clear status classification belong to later phases.
- Full operator dashboard/CLI redesign belongs to Phase 169.
- Post-deploy scripting belongs to Phase 170.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| OPER-01 | Metrics DB, WAL growth, maintenance failures, and shared-storage pressure are exposed clearly enough to alert before service quality slips | Add a shared read-side storage pressure snapshot and summary status that reuses existing in-memory contention counters, adds DB/WAL filesystem size, and surfaces maintenance outcome state without writing observer rows back to SQLite. [VERIFIED: .planning/REQUIREMENTS.md] |
| OPER-02 | Memory growth, cycle-budget degradation, and service health drift are exposed through stable operator-visible summaries | Add a shared runtime pressure snapshot with bounded process memory and cycle-budget summary fields to both autorate and steering health/metrics surfaces. [VERIFIED: .planning/REQUIREMENTS.md] |
| OPER-03 | Operator surfaces remain bounded and low-overhead; new observability does not write noisy high-rate telemetry back into SQLite | Keep collection scrape-time or TTL-cached, use existing in-memory metrics registry, and preserve the Phase 165 rule that `wanctl_storage_*` observability stays out of SQLite rows. [VERIFIED: tests/test_autorate_metrics_recording.py:128-145] |
</phase_requirements>

## Summary

The repo already has bounded in-memory storage contention telemetry for both autorate and steering, exposed through `get_storage_metrics_snapshot()` and rendered into `/health` without persisting observer rows back into SQLite. [VERIFIED: src/wanctl/metrics.py:651-674] [VERIFIED: src/wanctl/health_check.py:649-695] [VERIFIED: src/wanctl/steering/health.py:295-340] The current gap is not raw contention counters; it is operator-facing pressure visibility for database file growth, WAL growth, maintenance failure state, and process memory pressure. [VERIFIED: .planning/phases/168-storage-and-runtime-pressure-monitoring/168-CONTEXT.md]

The safest implementation path is to add a shared read-side pressure sampler that reuses existing in-memory counters, inspects the DB and WAL files at low frequency, and publishes a bounded summary into both `/health` and `/metrics`. [VERIFIED: .planning/phases/168-storage-and-runtime-pressure-monitoring/168-CONTEXT.md] [VERIFIED: src/wanctl/storage/writer.py:134-157] This fits the repo’s existing facade pattern, avoids hot-path writes, and keeps the controller and steering logic unchanged. [VERIFIED: src/wanctl/wan_controller.py:3285-3363] [VERIFIED: src/wanctl/steering/daemon.py:1249-1277] [VERIFIED: CLAUDE.md]

Maintenance already runs as bounded, watchdog-aware best-effort work, and the DB already uses WAL mode plus a 64 MB `journal_size_limit`, so Phase 168 should summarize pressure rather than add new maintenance behavior. [VERIFIED: src/wanctl/autorate_continuous.py:585-654] [VERIFIED: src/wanctl/storage/maintenance.py:85-179] [VERIFIED: src/wanctl/storage/writer.py:148-157] [CITED: https://a1.sqlite.org/pragma.html] [CITED: https://www.sqlite.org/draft/wal.html]

**Primary recommendation:** Add one shared `storage_pressure` and one shared `runtime_pressure` snapshot helper, feed both `/health` and `/metrics` from it, and keep all new state in memory only. [VERIFIED: src/wanctl/metrics.py:651-674] [VERIFIED: tests/storage/test_storage_contention_observability.py:73-102]

## Project Constraints (from CLAUDE.md)

- Explain risky changes before changing behavior. [VERIFIED: CLAUDE.md]
- Never refactor core logic, algorithms, thresholds, or timing without approval. [VERIFIED: CLAUDE.md]
- Prefer targeted fixes over broad cleanup in the control path. [VERIFIED: CLAUDE.md]
- Stability is the top priority for this production network control system. [VERIFIED: CLAUDE.md]
- The controller must remain link-agnostic; deployment-specific behavior belongs in YAML, not Python branching. [VERIFIED: CLAUDE.md]
- Baseline RTT and congestion-control logic are architectural spine and out of scope for this phase. [VERIFIED: CLAUDE.md]
- Queue updates are flash-wear sensitive and should only be sent when values change. [VERIFIED: CLAUDE.md]
- Steering must not perturb autorate baseline logic. [VERIFIED: CLAUDE.md]
- Background cleanup and retention work must stay bounded. [VERIFIED: CLAUDE.md]
- Use the project virtualenv tooling for validation: `.venv/bin/pytest`, `.venv/bin/ruff`, `.venv/bin/mypy`. [VERIFIED: CLAUDE.md]

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `wanctl.metrics` registry and snapshots | repo-local | Hold bounded in-memory gauges/counters and provide process-labeled storage snapshots | This is already the project’s contract for storage observability and does not create SQLite observer rows. [VERIFIED: src/wanctl/metrics.py:530-674] [VERIFIED: tests/storage/test_storage_contention_observability.py:95-102] |
| Health facade pattern (`WANController.get_health_data`, `SteeringDaemon.get_health_data`) | repo-local | Feed `/health` from pre-shaped data instead of cross-module private access | Both daemons already centralize observability through facade methods. [VERIFIED: src/wanctl/wan_controller.py:3285-3363] [VERIFIED: src/wanctl/steering/daemon.py:1249-1277] |
| Python stdlib: `pathlib`, `os`, `sqlite3`, `time`, `resource` | Python `>=3.11` | Read DB/WAL file size, query lightweight PRAGMAs, capture process resource usage, and cache scrape-time samples | The repo already depends on Python `>=3.11` and uses stdlib SQLite directly, so no new package is needed. [VERIFIED: pyproject.toml] [VERIFIED: src/wanctl/storage/writer.py:1-157] [CITED: https://docs.python.org/3/library/resource.html] |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| SQLite WAL PRAGMAs (`wal_checkpoint`, `page_count`, `page_size`, `freelist_count`, `journal_size_limit`) | SQLite runtime used by Python stdlib | Derive bounded DB/WAL pressure detail without new tables | Use in a low-frequency read-side sampler or TTL cache, not in the 50 ms hot path. [VERIFIED: src/wanctl/autorate_continuous.py:631-639] [CITED: https://a1.sqlite.org/pragma.html] [CITED: https://www.sqlite.org/draft/wal.html] |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Shared read-side sampler | Periodic background polling thread | A background poller would make freshness independent of scrape cadence, but it adds always-on work to a production daemon for a problem this phase can solve on demand. [VERIFIED: .planning/phases/168-storage-and-runtime-pressure-monitoring/168-CONTEXT.md] |
| Stdlib resource/process inspection | `psutil` | `psutil` would simplify current-RSS sampling, but the repo does not depend on it today and this phase does not require a new runtime dependency. [VERIFIED: pyproject.toml] |
| Top-level process pressure summary in autorate | Repeating process fields under every WAN | Repetition would be misleading in multi-WAN mode because one process and one DB back multiple WAN entries. [VERIFIED: src/wanctl/health_check.py:182-214] [VERIFIED: src/wanctl/wan_controller.py:3363] |

**Installation:**
```bash
# No new package installation recommended for Phase 168.
```

**Version verification:** Python requirement is `>=3.11` in project metadata, and the available validation tools in this workspace are `Python 3.12.3`, `pytest 9.0.2`, `ruff 0.14.10`, and `mypy 1.19.1`. [VERIFIED: pyproject.toml] [VERIFIED: local command probes on 2026-04-11]

## Architecture Patterns

### Recommended Project Structure
```text
src/wanctl/
├── metrics.py                 # in-memory gauges/counters and Prometheus exporter
├── health_check.py            # autorate /health JSON rendering
├── steering/health.py         # steering /health JSON rendering
├── wan_controller.py          # autorate get_health_data() facade
├── steering/daemon.py         # steering get_health_data() facade
└── observability_pressure.py  # recommended shared read-side DB/WAL/runtime sampler
```

### Pattern 1: Shared Read-Side Pressure Sampler
**What:** Create one shared helper that accepts `process_role`, resolves the active DB path, samples DB/WAL size plus lightweight runtime state, and returns a bounded dict with raw numbers and a derived status. [VERIFIED: src/wanctl/metrics.py:651-674] [VERIFIED: src/wanctl/storage/writer.py:80-82]

**When to use:** Use this from health and metrics export paths with a short TTL cache so repeated scrapes do not keep reopening SQLite or restatting files on every request. [VERIFIED: .planning/phases/168-storage-and-runtime-pressure-monitoring/168-CONTEXT.md]

**Example:**
```python
# Source: repo facade pattern in src/wanctl/wan_controller.py and src/wanctl/steering/daemon.py
from pathlib import Path
import sqlite3

def sample_storage_pressure(db_path: Path) -> dict[str, object]:
    db_size = db_path.stat().st_size if db_path.exists() else 0
    wal_path = Path(f"{db_path}-wal")
    wal_size = wal_path.stat().st_size if wal_path.exists() else 0
    with sqlite3.connect(f"file:{db_path}?mode=ro", uri=True) as conn:
        page_count = int(conn.execute("PRAGMA page_count").fetchone()[0])
        page_size = int(conn.execute("PRAGMA page_size").fetchone()[0])
        freelist_count = int(conn.execute("PRAGMA freelist_count").fetchone()[0])
        journal_size_limit = int(conn.execute("PRAGMA journal_size_limit").fetchone()[0])
    return {
        "db_size_bytes": db_size,
        "wal_size_bytes": wal_size,
        "page_count": page_count,
        "page_size_bytes": page_size,
        "freelist_count": freelist_count,
        "journal_size_limit_bytes": journal_size_limit,
    }
```

### Pattern 2: Summary Overlay, Not Schema Replacement
**What:** Keep the existing `storage` section and storage Prometheus metrics intact, then add new sibling summary sections such as `storage_pressure` and `runtime_pressure`. [VERIFIED: src/wanctl/health_check.py:649-695] [VERIFIED: src/wanctl/steering/health.py:295-340]

**When to use:** Use this when the raw Phase 165 counters still matter for diagnosis, but operators need an immediate status summary for Phase 168. [VERIFIED: .planning/phases/168-storage-and-runtime-pressure-monitoring/168-CONTEXT.md]

**Example:**
```python
# Source: existing health builders in src/wanctl/health_check.py and src/wanctl/steering/health.py
health["storage_pressure"] = {
    "status": "ok",
    "db_size_bytes": snapshot["db_size_bytes"],
    "wal_size_bytes": snapshot["wal_size_bytes"],
    "freelist_pct": round(snapshot["freelist_count"] / max(snapshot["page_count"], 1), 3),
    "maintenance": {
        "last_status": "ok",
        "error_total": 0,
        "lock_skipped_total": storage["checkpoint"]["maintenance_lock_skipped_total"],
    },
}
```

### Pattern 3: Health/Metrics Symmetry
**What:** Use the same shared snapshot to update Prometheus gauges and JSON health sections so `/metrics`, `/health`, and helper scripts classify the same reality. [VERIFIED: scripts/analyze_storage_contention.py:39-116]

**When to use:** Always; duplicating classification logic in multiple endpoints will drift. [VERIFIED: scripts/analyze_storage_contention.py:39-116]

**Example:**
```python
# Source: existing metrics exporter pattern in src/wanctl/metrics.py
metrics.set_gauge("wanctl_storage_db_size_bytes", snapshot["db_size_bytes"], labels=labels)
metrics.set_gauge("wanctl_storage_wal_size_bytes", snapshot["wal_size_bytes"], labels=labels)
metrics.set_gauge("wanctl_runtime_memory_bytes", runtime["memory_bytes"], labels=labels)
metrics.set_gauge("wanctl_storage_pressure_status", status_code(storage_status), labels=labels)
metrics.set_gauge("wanctl_runtime_pressure_status", status_code(runtime_status), labels=labels)
```

### Recommended Payload Additions

Use these bounded fields for Phase 168:

- `storage_pressure.status`: `ok|warning|critical|unknown`. [VERIFIED: existing status pattern in src/wanctl/health_check.py:33-51 and src/wanctl/health_check.py:195-214]
- `storage_pressure.db_size_bytes`, `storage_pressure.wal_size_bytes`, `storage_pressure.page_count`, `storage_pressure.page_size_bytes`, `storage_pressure.freelist_count`, `storage_pressure.freelist_pct`, `storage_pressure.journal_size_limit_bytes`. [VERIFIED: src/wanctl/storage/writer.py:148-157] [CITED: https://a1.sqlite.org/pragma.html] [CITED: https://www.sqlite.org/draft/wal.html]
- `storage_pressure.maintenance.last_status`, `storage_pressure.maintenance.error_total`, `storage_pressure.maintenance.lock_skipped_total`, `storage_pressure.maintenance.last_checkpoint_busy`. [VERIFIED: src/wanctl/autorate_continuous.py:631-654] [VERIFIED: src/wanctl/metrics.py:611-647]
- `runtime_pressure.status`: `ok|warning|critical|unknown`. [VERIFIED: existing status pattern in src/wanctl/health_check.py:74-128]
- `runtime_pressure.pid`, `runtime_pressure.memory_bytes`, `runtime_pressure.memory_high_water_bytes`, `runtime_pressure.cycle_utilization_pct`, `runtime_pressure.overrun_count`. [VERIFIED: src/wanctl/steering/health.py:155] [VERIFIED: src/wanctl/health_check.py:74-128] [CITED: https://docs.python.org/3/library/resource.html]

### Placement Recommendation

- Autorate health should add top-level `storage_pressure` and `runtime_pressure` sections while keeping the existing per-WAN `storage` and `cycle_budget` fields for compatibility. [VERIFIED: src/wanctl/health_check.py:182-214] [VERIFIED: tests/test_health_check.py:369-453]
- Steering health should add the same top-level `storage_pressure` and `runtime_pressure` sections next to its existing top-level `storage` and `cycle_budget` sections. [VERIFIED: src/wanctl/steering/health.py:117-170] [VERIFIED: tests/steering/test_steering_health.py:91-147]
- Metrics should expose per-process gauges only; do not label these by WAN because the DB and process pressure are process-scoped. [VERIFIED: src/wanctl/metrics.py:524-674]

### Anti-Patterns to Avoid
- **Per-request uncached SQLite inspection:** Opening SQLite and running multiple PRAGMAs on every scrape can turn observability into load. Use a shared TTL cache. [VERIFIED: .planning/phases/168-storage-and-runtime-pressure-monitoring/168-CONTEXT.md]
- **Per-WAN duplication of process state:** Repeating DB size or RSS under each autorate WAN obscures the fact that the pressure source is shared. [VERIFIED: src/wanctl/wan_controller.py:3363]
- **New observer rows in SQLite:** Phase 165 explicitly reserved `wanctl_storage_*` for in-memory telemetry only. Keep it that way. [VERIFIED: tests/test_autorate_metrics_recording.py:128-145] [VERIFIED: tests/storage/test_storage_contention_observability.py:95-102]
- **Unbounded error detail in health:** Export counters, timestamps, and enum status, not tracebacks or growing lists. [VERIFIED: existing bounded health sections in src/wanctl/health_check.py and src/wanctl/steering/health.py]

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Storage observability persistence | A new SQLite table for DB/WAL/runtime pressure | Existing in-memory metrics registry + health sections | The repo already enforces in-memory-only storage observability for queue/writer telemetry. [VERIFIED: src/wanctl/metrics.py:530-674] [VERIFIED: tests/test_autorate_metrics_recording.py:128-145] |
| Process-level pressure under autorate | A separate per-WAN pressure model | One process-scoped summary plus existing per-WAN detail | DB and process resources are shared across WANs inside the autorate process. [VERIFIED: src/wanctl/health_check.py:182-214] [VERIFIED: src/wanctl/wan_controller.py:3363] |
| WAL growth inference | A custom interpretation of checkpoint counters alone | Filesystem `stat()` plus lightweight SQLite PRAGMAs | `wal_checkpoint` counters describe checkpoint outcomes, while WAL file persistence and size limits are filesystem-visible state. [VERIFIED: src/wanctl/metrics.py:611-647] [CITED: https://www.sqlite.org/draft/wal.html] [CITED: https://a1.sqlite.org/pragma.html] |
| Memory telemetry | A new third-party dependency by default | Stdlib `resource` plus Linux current-RSS fallback if implemented | The project already targets Python 3.11+ and does not depend on `psutil`. [VERIFIED: pyproject.toml] [CITED: https://docs.python.org/3/library/resource.html] |
| Status derivation | Separate classification logic in health, metrics, and helper scripts | One shared status/classification helper | Divergent severity rules will confuse operators and later canary phases. [VERIFIED: scripts/analyze_storage_contention.py:39-116] |

**Key insight:** This phase should summarize pressure from existing signals and read-only state, not create a second observability subsystem. [VERIFIED: .planning/phases/168-storage-and-runtime-pressure-monitoring/168-CONTEXT.md]

## Common Pitfalls

### Pitfall 1: Treating Shared Pressure as Per-WAN
**What goes wrong:** Autorate exposes storage through each WAN entry today, so a naive extension can duplicate identical DB and memory values across all WANs. [VERIFIED: src/wanctl/health_check.py:182-214]  
**Why it happens:** `WANController.get_health_data()` currently injects process-scoped storage into a per-WAN render path. [VERIFIED: src/wanctl/wan_controller.py:3363]  
**How to avoid:** Add top-level process summaries and keep per-WAN fields only for compatibility and local diagnosis. [VERIFIED: tests/test_health_check.py:369-453]  
**Warning signs:** Operators see two WANs with the same DB size and interpret them as independent measurements. [VERIFIED: src/wanctl/health_check.py:182-214]

### Pitfall 2: Scrape-Time Inspection Becoming the New Pressure Source
**What goes wrong:** The health or metrics endpoint becomes expensive enough that frequent polling perturbs the daemon. [VERIFIED: .planning/phases/168-storage-and-runtime-pressure-monitoring/168-CONTEXT.md]  
**Why it happens:** DB PRAGMAs, filesystem stats, and status derivation are cheap individually but not free when repeated on every scrape. [CITED: https://a1.sqlite.org/pragma.html]  
**How to avoid:** Cache pressure samples by process for a short TTL and do only tiny reads. [VERIFIED: .planning/phases/168-storage-and-runtime-pressure-monitoring/168-CONTEXT.md]  
**Warning signs:** Endpoint latency increases, cycle-budget warning counts rise during scrape storms, or helper scripts disagree across back-to-back scrapes. [VERIFIED: src/wanctl/health_check.py:74-128] [VERIFIED: scripts/analyze_storage_contention.py:39-116]

### Pitfall 3: Confusing High-Water Memory with Current Memory
**What goes wrong:** An operator interprets `ru_maxrss` as current RSS and assumes a leak is still active after memory has stabilized. [CITED: https://docs.python.org/3/library/resource.html]  
**Why it happens:** `resource.getrusage()` exposes maximum resident set size, not a guaranteed current RSS field. [CITED: https://docs.python.org/3/library/resource.html]  
**How to avoid:** Name the stdlib field `memory_high_water_bytes` if sourced from `ru_maxrss`, and only expose `memory_bytes` when you have a verified current-RSS source. [CITED: https://docs.python.org/3/library/resource.html]  
**Warning signs:** The “current” value never falls even after workload subsides. [CITED: https://docs.python.org/3/library/resource.html]

### Pitfall 4: Relying on WAL Pages Without Page Size or File Size
**What goes wrong:** WAL pressure is understated or overstated because page counts are reported without byte context. [CITED: https://a1.sqlite.org/pragma.html]  
**Why it happens:** `wal_pages` and `checkpointed_pages` are counts, while operator pressure decisions are usually byte-oriented. [VERIFIED: src/wanctl/metrics.py:611-647]  
**How to avoid:** Export both raw counts and byte-oriented fields: WAL file size, page size, and derived ratios. [CITED: https://a1.sqlite.org/pragma.html] [CITED: https://www.sqlite.org/draft/wal.html]  
**Warning signs:** A large retained WAL file shows `checkpointed_pages=0` but no obvious size-based warning. [CITED: https://www.sqlite.org/draft/wal.html]

### Pitfall 5: Surfacing Maintenance Failures Only in Logs
**What goes wrong:** Operators miss startup or periodic maintenance degradation until the DB is already large or fragmented. [VERIFIED: src/wanctl/autorate_continuous.py:362-364] [VERIFIED: src/wanctl/autorate_continuous.py:654] [VERIFIED: src/wanctl/steering/daemon.py:2235-2243]  
**Why it happens:** Current maintenance failures are logged, but not summarized into health or Prometheus state. [VERIFIED: src/wanctl/autorate_continuous.py:362-364] [VERIFIED: src/wanctl/autorate_continuous.py:654]  
**How to avoid:** Add in-memory maintenance outcome counters and last-status fields, then include them in `storage_pressure.maintenance`. [VERIFIED: src/wanctl/metrics.py:641-647]  
**Warning signs:** `maintenance_lock_skipped_total` rises or periodic errors appear in logs while health remains superficially “healthy.” [VERIFIED: src/wanctl/metrics.py:641-647] [VERIFIED: src/wanctl/health_check.py:195-214]

## Code Examples

Verified patterns from repo and official docs:

### Shared Process-Scoped Snapshot Hook
```python
# Source: repo health facade pattern + metrics registry pattern
def enrich_process_pressure(health: dict[str, object], process_role: str, db_path: Path) -> None:
    storage = sample_storage_pressure(db_path)
    runtime = sample_runtime_pressure()
    health["storage_pressure"] = classify_storage_pressure(storage, health)
    health["runtime_pressure"] = classify_runtime_pressure(runtime, health)
    publish_pressure_metrics(process_role, storage, runtime)
```

### Memory High-Water Extraction with Explicit Naming
```python
# Source: https://docs.python.org/3/library/resource.html
import resource

usage = resource.getrusage(resource.RUSAGE_SELF)
runtime = {
    "memory_high_water_bytes": int(usage.ru_maxrss) * 1024,
}
```

### WAL and Freelist Detail for Pressure Summaries
```python
# Source: https://a1.sqlite.org/pragma.html and https://www.sqlite.org/draft/wal.html
from pathlib import Path
import sqlite3

with sqlite3.connect(f"file:{db_path}?mode=ro", uri=True) as conn:
    journal_size_limit = int(conn.execute("PRAGMA journal_size_limit").fetchone()[0])
    page_count = int(conn.execute("PRAGMA page_count").fetchone()[0])
    page_size = int(conn.execute("PRAGMA page_size").fetchone()[0])
    freelist_count = int(conn.execute("PRAGMA freelist_count").fetchone()[0])

freelist_pct = freelist_count / max(page_count, 1)
wal_path = Path(f"{db_path}-wal")
wal_size_bytes = wal_path.stat().st_size if wal_path.exists() else 0
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Raw storage contention only (`pending_writes`, write failures, checkpoint counters) | Raw contention plus derived process pressure summaries | Phase 168 target state | Operators get actionable status without losing low-level counters. [VERIFIED: src/wanctl/health_check.py:649-695] |
| Maintenance failures visible only in logs | Maintenance outcome summarized into health/metrics | Phase 168 target state | Phase 170 canary work can consume a stable signal instead of grep-based checks. [VERIFIED: src/wanctl/autorate_continuous.py:362-364] [VERIFIED: src/wanctl/autorate_continuous.py:654] |
| Storage pressure inferred manually from mixed snapshots | Shared classification helper used by health, metrics, and scripts | Phase 168 target state | Prevents drift between endpoints and helper tooling. [VERIFIED: scripts/analyze_storage_contention.py:39-116] |

**Deprecated/outdated:**
- Relying on logs alone for storage/runtime pressure is insufficient for this milestone’s requirements. [VERIFIED: .planning/REQUIREMENTS.md]

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Linux current-RSS collection can be implemented cheaply by parsing `/proc/self/status` if the team wants a true current-memory gauge instead of only `ru_maxrss`. | Architecture Patterns | Low to medium; if unavailable, Phase 168 should fall back to high-water memory only and keep the field naming explicit. [ASSUMED] |

## Open Questions

1. **Should autorate expose process pressure only at top level, or also repeat it under each WAN for convenience?**
   - What we know: The autorate process and DB are shared while health currently renders per-WAN storage detail. [VERIFIED: src/wanctl/health_check.py:182-214] [VERIFIED: src/wanctl/wan_controller.py:3363]
   - What's unclear: Whether any downstream consumer already expects process-scoped storage only inside `wans[*].storage`. [VERIFIED: tests/test_health_check.py:369-453]
   - Recommendation: Add top-level summaries now and leave existing per-WAN detail intact for compatibility.

2. **Is `ru_maxrss` sufficient for OPER-02, or does the team want current RSS specifically?**
   - What we know: Python stdlib exposes `ru_maxrss` portably on Unix, and it is a maximum resident set size field. [CITED: https://docs.python.org/3/library/resource.html]
   - What's unclear: Whether operators care more about current working set or peak memory watermark for this phase.
   - Recommendation: Ship `memory_high_water_bytes` in all cases; add `memory_bytes` only if the implementation has a verified current-RSS source.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| `python3` | Helper scripts, validation, stdlib runtime sampling | ✓ | 3.12.3 | — |
| `.venv/bin/pytest` | Phase validation | ✓ | 9.0.2 | `python3 -m pytest` if needed |
| `.venv/bin/ruff` | Lint verification | ✓ | 0.14.10 | — |
| `.venv/bin/mypy` | Type-check verification | ✓ | 1.19.1 | — |

**Missing dependencies with no fallback:**
- None. [VERIFIED: local command probes on 2026-04-11]

**Missing dependencies with fallback:**
- None. [VERIFIED: local command probes on 2026-04-11]

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | `pytest` 9.0.2 [VERIFIED: local command probes on 2026-04-11] |
| Config file | `pyproject.toml` [VERIFIED: pyproject.toml] |
| Quick run command | `.venv/bin/pytest -o addopts='' tests/test_health_check.py tests/steering/test_steering_health.py tests/test_metrics.py tests/test_analyze_storage_contention.py -q` |
| Full suite command | `.venv/bin/pytest tests/ -v` [VERIFIED: CLAUDE.md] |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| OPER-01 | Autorate and steering expose bounded DB/WAL pressure detail and maintenance status in health | unit | `.venv/bin/pytest -o addopts='' tests/test_health_check.py tests/steering/test_steering_health.py -q` | ✅ |
| OPER-01 | Metrics exporter exposes per-process DB/WAL/maintenance gauges without writing observer rows to SQLite | unit | `.venv/bin/pytest -o addopts='' tests/test_metrics.py tests/storage/test_storage_contention_observability.py tests/test_autorate_metrics_recording.py -q` | ✅ |
| OPER-01 | Helper script or classifier consumes new pressure fields consistently | unit | `.venv/bin/pytest -o addopts='' tests/test_analyze_storage_contention.py -q` | ✅ |
| OPER-02 | Runtime pressure summaries cover memory and cycle-budget degradation for autorate and steering | unit | `.venv/bin/pytest -o addopts='' tests/test_health_check.py tests/steering/test_steering_health.py -q` | ✅ |
| OPER-03 | Added observability remains bounded, low-overhead, and in-memory only | unit | `.venv/bin/pytest -o addopts='' tests/storage/test_storage_contention_observability.py tests/test_autorate_metrics_recording.py tests/test_metrics.py -q` | ✅ |

### Sampling Rate
- **Per task commit:** `.venv/bin/pytest -o addopts='' tests/test_health_check.py tests/steering/test_steering_health.py tests/test_metrics.py tests/test_analyze_storage_contention.py -q`
- **Per wave merge:** `.venv/bin/pytest -o addopts='' tests/storage/test_storage_contention_observability.py tests/test_autorate_metrics_recording.py tests/test_health_check.py tests/steering/test_steering_health.py tests/test_metrics.py tests/test_analyze_storage_contention.py -q`
- **Phase gate:** Full targeted slice above plus relevant lint/type checks green before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] Add focused unit tests for the shared pressure sampler helper: missing DB, retained WAL sidecar, read-only PRAGMA failure, and cache TTL behavior.
- [ ] Extend `tests/test_health_check.py` and `tests/steering/test_steering_health.py` to assert new top-level `storage_pressure` and `runtime_pressure` shapes without regressing existing `storage` sections.
- [ ] Extend `tests/test_metrics.py` to assert Prometheus output for DB size, WAL size, maintenance error counters, and runtime memory gauges.
- [ ] Extend `tests/test_analyze_storage_contention.py` if the helper script begins consuming summary status or byte-size thresholds in addition to raw contention counters.

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | Health and metrics endpoints remain unauthenticated local services in current architecture. [VERIFIED: src/wanctl/health_check.py] [VERIFIED: src/wanctl/metrics.py] |
| V3 Session Management | no | No session state is introduced by this phase. [VERIFIED: scope in .planning/REQUIREMENTS.md] |
| V4 Access Control | no | Phase 168 adds observability fields only; no new access-control path is introduced. [VERIFIED: .planning/REQUIREMENTS.md] |
| V5 Input Validation | yes | Parse only config-derived DB paths and bounded numeric scrape params; keep new fields typed and bounded. [VERIFIED: src/wanctl/health_check.py:719-861] |
| V6 Cryptography | no | No cryptographic behavior is touched in this phase. [VERIFIED: .planning/REQUIREMENTS.md] |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Expensive scrape amplification | Denial of Service | Use TTL-cached read-side inspection and only lightweight filesystem/PRAGMA reads. [VERIFIED: .planning/phases/168-storage-and-runtime-pressure-monitoring/168-CONTEXT.md] |
| Sensitive host detail leakage | Information Disclosure | Export bounded counters, sizes, and enum statuses; avoid raw tracebacks or environment detail in health. [VERIFIED: current health payload style in src/wanctl/health_check.py and src/wanctl/steering/health.py] |
| SQLite lock interference from observability | Denial of Service | Use read-only connections and keep all new observability state in memory rather than writing back to SQLite. [VERIFIED: src/wanctl/storage/reader.py:94-169] [VERIFIED: tests/test_autorate_metrics_recording.py:128-145] |

## Sources

### Primary (HIGH confidence)
- `src/wanctl/health_check.py` - current autorate health schema, cycle-budget status, and storage section renderer. [VERIFIED: src/wanctl/health_check.py:74-128] [VERIFIED: src/wanctl/health_check.py:649-695]
- `src/wanctl/steering/health.py` - current steering health schema and storage section renderer. [VERIFIED: src/wanctl/steering/health.py:117-170] [VERIFIED: src/wanctl/steering/health.py:295-340]
- `src/wanctl/metrics.py` - storage metrics registry, checkpoint counters, and bounded snapshot contract. [VERIFIED: src/wanctl/metrics.py:530-674]
- `src/wanctl/wan_controller.py` and `src/wanctl/steering/daemon.py` - facade pattern and current process-scoped storage injection. [VERIFIED: src/wanctl/wan_controller.py:3285-3363] [VERIFIED: src/wanctl/steering/daemon.py:1249-1277]
- `src/wanctl/storage/writer.py`, `src/wanctl/storage/maintenance.py`, and `src/wanctl/autorate_continuous.py` - WAL mode, journal size limit, and maintenance behavior. [VERIFIED: src/wanctl/storage/writer.py:148-157] [VERIFIED: src/wanctl/storage/maintenance.py:85-179] [VERIFIED: src/wanctl/autorate_continuous.py:585-654]
- Repo tests defining current contracts: `tests/test_health_check.py`, `tests/steering/test_steering_health.py`, `tests/test_metrics.py`, `tests/storage/test_storage_contention_observability.py`, `tests/test_autorate_metrics_recording.py`, `tests/test_analyze_storage_contention.py`. [VERIFIED: repo grep]

### Secondary (MEDIUM confidence)
- Python `resource` docs - Unix availability and `ru_maxrss` semantics. [CITED: https://docs.python.org/3/library/resource.html]
- SQLite PRAGMA docs - `wal_checkpoint`, `page_count`, `page_size`, `freelist_count`, and `journal_size_limit`. [CITED: https://a1.sqlite.org/pragma.html]
- SQLite WAL docs - WAL file naming, persistence, auto-checkpoint behavior, and unbounded-growth failure modes. [CITED: https://www.sqlite.org/draft/wal.html]

### Tertiary (LOW confidence)
- None.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - This phase can stay within existing repo patterns and stdlib capabilities already verified in code and metadata.
- Architecture: MEDIUM - The shared sampler and top-level summary placement are strong fits, but the exact current-RSS source still needs implementation choice.
- Pitfalls: HIGH - The main risks are directly visible in existing code structure, tests, and SQLite/Python docs.

**Research date:** 2026-04-11
**Valid until:** 2026-05-11
