---
phase: 219-ingestion-rate-observability-scope-d
plan: 04
subsystem: observability
tags: [ingestion-rate, cron, snapshot, atomic-write, retention, docs, cycle-budget, d-27]

requires:
  - phase: 219-02
    provides: [wanctl-history ingestion-rate by-table/rolling JSON envelope]
  - phase: 219-03
    provides: [operator-summary ingestion-rate digest block]
  - phase: 217
    provides: [production cycle-budget baseline gates]
provides:
  - Cron-callable Phase 219 ingestion-rate snapshot writer
  - Staleness semantics and cron stanza documentation for stored ingestion snapshots
  - Production D-27 cycle-budget evidence proving Phase 219 remains within hot-path gates
affects: [phase-218-audit-fallback, phase-220, operator-runbooks]

tech-stack:
  added: []
  patterns:
    - stdlib cron helper with bounded subprocess execution
    - reused wanctl.state_utils.atomic_write_json for collision-safe snapshot persistence
    - count-based retention for flash-wear-safe cron snapshots

key-files:
  created:
    - scripts/phase219_ingestion_digest.py
    - .planning/perf/v1.47-phase219-spectrum-20260530.profile.json
    - .planning/phases/219-ingestion-rate-observability-scope-d/219-04-SUMMARY.md
  modified:
    - tests/test_phase219_ingestion_digest.py
    - docs/CONFIGURATION.md

key-decisions:
  - "D-19 kept the cron script at the underscore path so `python -m scripts.phase219_ingestion_digest` is valid."
  - "D-21 reused `wanctl.state_utils.atomic_write_json` despite the normal scripts-to-src boundary because the mkstemp-based helper provides collision-safe atomic writes."
  - "D-23 validates subprocess stdout with `json.loads` before persistence so malformed audit evidence is rejected without writing garbage files."
  - "D-27 accepted production profile gates after a live cron-active capture: avg 2.857ms and p99 6.4ms."

patterns-established:
  - "Ingestion snapshot files are named `<unix_ts>.json` under `/var/lib/wanctl/snapshots/ingestion/` and retained by newest-count, not age sweep."
  - "Stored ingestion snapshots carry `_snapshot_unix` and `_snapshot_age_sec` semantics matching the v1.38 measurement_stale precedent."

requirements-completed: [INGEST-05, SAFE-11]

duration: checkpointed; production capture 62min
completed: 2026-05-30
---

# Phase 219 Plan 04: Cron Snapshot Writer + Production Cycle-Budget Summary

**Cron-callable ingestion-rate snapshots now persist the Phase 219 by-table/rolling JSON envelope, with production D-27 profiling proving the out-of-band cron path stayed within the 50ms controller cycle budget.**

## Performance

- **Duration:** Checkpointed; automated tasks completed before the human-verify gate, followed by a 62-minute production profiling window.
- **Started:** 2026-05-30T15:50:18Z production capture start for D-27 evidence.
- **Completed:** 2026-05-30T16:53:49Z summary closeout.
- **Tasks:** 4/4 completed.
- **Files modified:** 5 plan files/artifacts.

## Accomplishments

- Added `scripts/phase219_ingestion_digest.py`, a cron-callable snapshot writer that runs `wanctl-history --ingestion-rate --by-table --rolling=60,300,3600 --json`, validates the JSON payload, and persists it atomically.
- Flipped the Phase 219 ingestion digest tests green, including retention, malformed JSON, deterministic subprocess failure, directory mode, and default retention coverage.
- Documented the Phase 219 staleness contract and cron stanza in `docs/CONFIGURATION.md` without adding tuning guidance.
- Captured and committed production D-27 cycle-budget evidence showing `cycle_total.avg_ms=2.857` and `cycle_total.p99_ms=6.4`, both passing Phase 217-derived gates.
- Resolved folded todo `2026-04-17-ingestion-rate-tool` for the v1.47 Scope D surface: smoothed tail-rate evidence is now available through `--rolling=60,300,3600` and persisted cron snapshots.

## Task Commits

Each task was committed atomically:

1. **Task 1: Create cron snapshot writer** - `f97eea9` (feat)
2. **Task 2: Flip ingestion digest tests green** - `ef75e9c` (test)
3. **Task 3: Document staleness semantics + cron stanza** - `ff20008` (docs)
4. **Task 4: Record production cycle-budget verification** - committed with plan metadata after this summary is written.

## Files Created/Modified

- `scripts/phase219_ingestion_digest.py` - Cron-callable snapshot writer using list-form subprocess argv, JSON validation, atomic persistence, and count-based retention.
- `tests/test_phase219_ingestion_digest.py` - Active regression coverage for the snapshot writer; xfail scaffolds removed.
- `docs/CONFIGURATION.md` - Phase 219 staleness semantics, D-17 back-compat note, D-21/D-23 behavior, and operator cron stanza.
- `.planning/perf/v1.47-phase219-spectrum-20260530.profile.json` - Production profile artifact from the D-27 post-deploy capture.
- `.planning/phases/219-ingestion-rate-observability-scope-d/219-04-SUMMARY.md` - This execution and production verification record.

## Decisions Made

- **D-19 underscore filename:** The script is `scripts/phase219_ingestion_digest.py`, not a hyphenated path, so direct invocation and `python -m scripts.phase219_ingestion_digest` both work. This resolves Codex H3 and makes the documented cron stanza module-safe.
- **D-21 atomic helper reuse:** The script imports `wanctl.state_utils.atomic_write_json` rather than hand-rolling `<target>.tmp` + rename. This relaxes the normal `scripts/` → `src/wanctl` boundary for one utility import because the existing helper uses collision-safe `mkstemp` temp files and `os.replace`, resolving Codex H4.
- **D-23 JSON validation before write:** Subprocess stdout is parsed with `json.loads` before `atomic_write_json`; malformed payloads log to stderr, return `1`, and leave no garbage snapshot. This resolves Codex M8 and protects audit evidence integrity.
- **D-27 production verification:** Phase 219 is marked complete only after a post-deploy, cron-active production profile passed both inherited cycle-budget gates.
- **Cron stanza is documentation/runbook only:** The repository documents the cron entry; installation remains an operator action on production.

## D-19 / D-21 / D-23 / D-27 Notes

- **D-19:** Underscore script naming is enforced in source, docs, and tests; no hyphenated `phase219-ingestion-digest.py` path is used.
- **D-21:** Snapshot writes reuse `wanctl.state_utils.atomic_write_json`, whose mkstemp-based temp path avoids concurrent same-second writer collisions. The helper's default `0o600` file mode is accepted for local wanctl evidence readers.
- **D-23:** The write path rejects malformed JSON before persistence. The regression test `test_malformed_json_payload_returns_1_no_file_written` pins this behavior.
- **D-27:** Production cycle-budget verification ran after deployment and with cron active. Both gates passed, so ROADMAP success criterion #5 is satisfied.

## Production Verification (D-27)

### Deployment and cron evidence

- **Production host:** `cake-shaper`.
- **Deployment path:** Phase 219 code deployed to `/opt/wanctl` via targeted `src/wanctl` rsync.
- **Script installation:** `scripts/phase219_ingestion_digest.py` installed under both `/opt/scripts` and `/opt/wanctl/scripts`.
- **Cron installation:** `/etc/cron.d/wanctl-ingestion-digest` with `PYTHONPATH=/opt:/opt/wanctl` and `/usr/bin/python3 -m scripts.phase219_ingestion_digest`.
- **Pre-profile smoke:** Manual smoke as user `wanctl` succeeded before profiling.
- **Cron activity before profiling:** Actual cron tick observed before profiling; snapshot count increased from 1 to 2.
- **Cron activity during profiling:** After profiling, `snapshot_count=27`; latest snapshot `1780159801.json`. Cron was active throughout the capture window.

### Profiling capture

- **Local raw capture file:** `.planning/perf/capture/phase219-spectrum-live.ndjson` (gitignored raw capture).
- **Committed profile artifact:** `.planning/perf/v1.47-phase219-spectrum-20260530.profile.json`.
- **Capture start:** 2026-05-30T15:50:18Z.
- **Capture end:** 2026-05-30T16:52:18Z.
- **Cycle samples:** 73,603.
- **`cycle_total.avg_ms`:** 2.857.
- **`cycle_total.p99_ms`:** 6.4.

### Gates

| Gate | Threshold | Actual | Verdict |
|------|-----------|--------|---------|
| `cycle_total.avg_ms` | `<= 3.0` | `2.857` | PASS |
| `cycle_total.p99_ms` | `<= 7.5` | `6.4` | PASS |

### Baseline comparison

- **Baseline artifact:** `.planning/perf/v1.45-baseline-spectrum-20260529.profile.json`.
- **Baseline `cycle_total.avg_ms`:** 2.883.
- **Baseline `cycle_total.p99_ms`:** 6.9.
- **Avg drift:** -0.90% vs baseline.
- **P99 drift:** -7.25% vs baseline (favorable/lower).
- **Verdict:** PASS. Phase 219 post-deploy profile is within gates and favorable against the baseline.

### Revert proof

- **Profiling drop-in removed:** `/etc/systemd/system/wanctl@spectrum.service.d/phase219-profile.conf` absent.
- **Service state:** Service active after revert.
- **ExecStart restored:** `/usr/bin/python3 /opt/wanctl/autorate_continuous.py --config /etc/wanctl/spectrum.yaml`.
- **Environment restored:** `PYTHONPATH=/opt`, `WANCTL_STATE_DIR=/var/lib/wanctl`, `WANCTL_LOG_DIR=/var/log/wanctl`, `WANCTL_RUN_DIR=/run/wanctl`; no `WANCTL_LOG_FORMAT=json`.

## Deviations from Plan

None - plan executed as specified after the human-verify checkpoint was approved. The production verification evidence was supplied by the operator and recorded as the planned Task 4 closeout.

## Issues Encountered

- Task 4 intentionally paused at the human-verify gate because production deployment/profiling required operator action. The operator returned `approved` after both cycle-budget gates passed.

## Known Stubs

None.

## Threat Flags

None beyond the plan threat model. The production evidence confirms the T-219-13 performance-regression mitigation passed.

## Verification

Previously completed before checkpoint:

```bash
.venv/bin/pytest tests/test_phase219_ingestion_digest.py -x
.venv/bin/pytest tests/test_phase219_mutation_boundary.py -x
.venv/bin/pytest tests/test_history_ingestion_rate_bucketed.py -x
.venv/bin/pytest -o addopts='' tests/test_cake_signal.py tests/test_queue_controller.py tests/test_wan_controller.py tests/test_health_check.py -q
.venv/bin/ruff check scripts/phase219_ingestion_digest.py tests/test_phase219_ingestion_digest.py
.venv/bin/python scripts/phase219_ingestion_digest.py --help | grep -E -- "--snapshot-dir|--max-snapshots|--payload-from-stdin|--inject-timestamp"
.venv/bin/python scripts/phase219_ingestion_digest.py --help 2>&1 | grep -c -- "--window-sec"
.venv/bin/python -m scripts.phase219_ingestion_digest --help 2>&1 | grep -q "snapshot"
```

Task 4 production verification passed with `cycle_total.avg_ms=2.857 <= 3.0` and `cycle_total.p99_ms=6.4 <= 7.5` over 73,603 samples while cron snapshots were active.

## User Setup Required

None for repository state. Production cron has been installed by the operator and verified active during the D-27 capture.

## Next Phase Readiness

Phase 219 Scope D is complete. Phase 220 can now rely on ingestion-rate observability being shipped, documented, and production cycle-budget verified before matrix-runner work begins.

## Self-Check: PASSED

- Found created/modified files: `scripts/phase219_ingestion_digest.py`, `tests/test_phase219_ingestion_digest.py`, `docs/CONFIGURATION.md`, `.planning/perf/v1.47-phase219-spectrum-20260530.profile.json`, this summary.
- Found prior task commits: `f97eea9`, `ef75e9c`, `ff20008`.
- D-27 evidence section exists and records both passing gates plus revert proof.

---
*Phase: 219-ingestion-rate-observability-scope-d*
*Completed: 2026-05-30*
