---
phase: "247"
plan: "03"
status: complete
completed_at: "2026-06-19T11:15:00Z"
requirements:
  - PROF-01
key_files:
  created:
    - scripts/phase247-fping-shadow.py
    - tests/test_phase247_shadow_script.py
  modified:
    - .planning/phases/247-fping-shadow-capture-phase-245-evidence-review/evidence/safe18-boundary-247.json
verification:
  - .venv/bin/python scripts/phase247-fping-shadow.py --help
  - .venv/bin/pytest tests/test_phase247_shadow_script.py --collect-only -q
  - .venv/bin/pytest tests/test_phase247_shadow_script.py -v
  - .venv/bin/ruff check scripts/phase247-fping-shadow.py tests/test_phase247_shadow_script.py
  - .venv/bin/pytest tests/test_phase247_shadow_script.py tests/test_phase247_safe18_verifier.py -v
  - bash scripts/phase247-safe18-boundary-check.sh
---

# Plan 247-03 Summary — fping Shadow Capture Script

## What changed

Created `scripts/phase247-fping-shadow.py`, a standalone read-only shadow capture script for cake-shaper. It imports the real `FpingMeasurement` and `FpingThread` code path, reads Spectrum config, maps root-level `ping_source_ip` to the constructor key `source_ip`, and appends NDJSON records to `/var/lib/wanctl/phase247-fping-shadow.ndjson` by default.

Created `tests/test_phase247_shadow_script.py` with 21 tests covering the script contract.

## Behavior implemented

The script writes a `run_start` record before the polling loop with provenance fields: source IP, reflector list, config path, script version, cadence, count, period, and timeout grace.

For each observed new `RttSample`, it writes a `probe_cycle` record with:

- wall-clock `ts`
- monotonic `sample_monotonic_ts`
- cumulative observed `probe_index`
- `elapsed_ms` from `sample.measurement_ms`
- `rtt_ms`
- `success`, `all_loss`, and `inferred=false`
- `reflector_count` and `source_ip`
- `per_host_results`, `per_host_loss`, `active_hosts`, and `successful_hosts`

Cached all-loss samples are logged as first-class `probe_cycle` records with `success=false`, `all_loss=true`, `inferred=false`, and numeric elapsed timing from the sample.

When no new cached sample appears after cadence plus grace, the script writes an inferred dropped-burst record with the exact planned schema: `elapsed_ms=null`, `rtt_ms=null`, `inferred=true`, `dropped=true`, `reason=no_new_sample_within_cadence`, and `expected_probe_index`. It does not fabricate timing for unobserved dropped bursts and does not increment the observed `probe_index` for inferred records.

`probe_stats` snapshots are emitted every configured observed-probe interval and omit the raw `samples` key. `probe_stats_final` is written during shutdown. Each stats record includes `probe_count_at_snapshot`, the cumulative observed-burst count, distinct from the OperationProfiler rolling-window `count`.

## Phase 248 data contract

The script embeds and implements the Phase 248 warning: full-window p99 values must be computed from `probe_cycle` records, not from the rolling `probe_stats.p99_ms` value. Phase 248 gets two distinct first-class distributions:

- `rtt_p99_ms` from successful `probe_cycle.rtt_ms`
- `probe_elapsed_p99_ms_full_window` from successful `probe_cycle.elapsed_ms`, excluding inferred/dropped records where `elapsed_ms=null`

## Verification

Commands run successfully:

- `.venv/bin/python scripts/phase247-fping-shadow.py --help`
- `.venv/bin/pytest tests/test_phase247_shadow_script.py --collect-only -q` — 21 tests collected
- `.venv/bin/pytest tests/test_phase247_shadow_script.py -v` — 21 passed
- `.venv/bin/ruff check scripts/phase247-fping-shadow.py tests/test_phase247_shadow_script.py` — all checks passed
- `.venv/bin/pytest tests/test_phase247_shadow_script.py tests/test_phase247_safe18_verifier.py -v` — 31 passed
- `bash scripts/phase247-safe18-boundary-check.sh` — pass, protected-file diff remains empty

## Self-check: PASSED
