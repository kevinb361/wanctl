---
phase: 227-candidate-diffserv4-wash-deploy-matched-capture
plan: 01
subsystem: validation-tooling
tags: [capture-harness, iperf3, diffserv4, marked-ef, pytest]
requires:
  - phase: 226-baseline-capture-threshold-lock-snapshot-a
    provides: [matched Phase 226 baseline capture harness and baseline summary shape]
provides:
  - additive default-off marked-EF UDP reference arm for the Phase 226 matched capture harness
  - validity-guarded iperf JSON parsing for unmarked UDP, unmarked TCP, and marked-EF references
  - regression tests locking additive-not-forked, distinct EF port, degrade-to-best-effort, and validity contracts
affects: [phase-227-capture, phase-228-verdict, AB-04, GATE-01]
tech-stack:
  added: []
  patterns: [stdlib JSON parsing, subprocess dry-run regression, fixture-built capture trees]
key-files:
  created:
    - tests/test_phase227_marked_ef.py
  modified:
    - scripts/phase226-baseline-capture.sh
    - scripts/phase226-baseline-summary.py
    - .claude/context.md
key-decisions:
  - "Marked-EF remains default-off and additive; the existing RRUL, unmarked UDP, and unmarked TCP reference invocations still target REF_PORT."
  - "Marked-EF uses a distinct EF_REF_PORT defaulting to REF_PORT+2 and refuses collisions with REF_PORT."
  - "GATE-01 reads matched EF-loaded captures while AB-04 reads marked_ef versus ref_udp_unmarked metrics from the same summary."
patterns-established:
  - "Iperf artifacts are valid only when JSON parses, has no top-level error, and exposes the expected end.sum/end.sum_received block."
  - "EF marking cleanliness is recorded from the marking method path, with an explicit none/false degrade-to-best-effort fallback."
requirements-completed: [AB-04]
duration: 6 min
completed: 2026-06-04
---

# Phase 227 Plan 01: Marked-EF Matched Capture Harness Summary

**Default-off marked-EF iperf3 arm with distinct port separation and validity-guarded reference metrics for AB-04 realtime comparison.**

## Performance

- **Duration:** 6 min
- **Started:** 2026-06-04T14:28:56Z
- **Completed:** 2026-06-04T14:35:14Z
- **Tasks:** 3
- **Files modified:** 4

## Accomplishments

- Added `--marked-ef` and `--ef-ref-port` to the existing Phase 226 capture harness without changing the default unmarked dry-run shape.
- Added per-flow iperf JSON validity checks and EF marking records (`EF_MARK_METHOD`, `EF_CLEAN_MARK`, `EF_REF_PORT`).
- Built summary parsing for `ref_udp_unmarked`, `ref_tcp_unmarked`, and optional `marked_ef` blocks, including valid:false handling for top-level iperf errors or missing expected summary blocks.
- Added regression tests proving matched-arm preservation, EF port separation, degrade-to-best-effort record paths, and unmarked/marked metric emission.

## Task Commits

Each task was committed atomically:

1. **Task 1: Add the additive --marked-ef UDP arm to the capture harness** - `2389642` (feat)
2. **Task 2: BUILD iperf-JSON parsing in the summary generator** - `c27c2cc` (feat)
3. **Task 3: Regression test — matched arms unchanged, --marked-ef purely additive** - `67bab64` (test)

**Plan metadata:** pending final metadata commit

## Files Created/Modified

- `scripts/phase226-baseline-capture.sh` - Adds default-off marked-EF arm, distinct EF port, iperf validity records, and manifest EF provenance.
- `scripts/phase226-baseline-summary.py` - Parses unmarked UDP jitter/loss, unmarked TCP throughput/retransmits, marked-EF jitter/loss, and validity outcomes from iperf JSON artifacts.
- `tests/test_phase227_marked_ef.py` - Locks additive-not-forked, port separation, EF fallback, and iperf-validity behavior without live targets.
- `.claude/context.md` - Captures the Phase 227 Plan 01 tooling contract for future sessions.

## Verification

- `bash -n scripts/phase226-baseline-capture.sh` — PASS
- `scripts/phase226-baseline-capture.sh --output-dir /tmp/p227-ef-dry --marked-ef --dry-run 2>&1 | grep -qi "marked_ef\|ef_ref_port\|udp_rate"` — PASS
- `python3 -c "import ast; ast.parse(open('scripts/phase226-baseline-summary.py').read())" && python3 scripts/phase226-baseline-summary.py --help` — PASS
- `.venv/bin/pytest tests/test_phase227_marked_ef.py -q` — PASS (`7 passed`)

## Decisions Made

- Marked-EF is additive and default-off; existing matched reference invocations remain unchanged when `--marked-ef` is absent.
- EF uses a separate iperf3 port (`REF_PORT+2`, default `5203`) to avoid reference server contention and preserve unmarked UDP fidelity.
- Iperf success requires parseable JSON with no top-level `error` and the expected `end.sum`/`end.sum_received`; invalid flows are recorded as invalid instead of converted to zero metrics.
- EF cleanliness is based on the successful marking method path (`dscp`/`tos`/`none`), not merely on iperf accepting traffic.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

- The pre-commit documentation hook required `.claude/context.md` updates for new helper functions/tests; task commits included targeted context notes so hooks ran normally.

## User Setup Required

None for this plan. Later live captures using `--marked-ef` require an iperf3 server listening on the chosen EF reflector port (`dallas:5203` by default).

## Known Stubs

None found in files created or modified by this plan.

## Threat Flags

None. The only new network surface is the planned optional iperf3 marked-EF client flow to a distinct reflector port, already covered by the plan threat model.

## Next Phase Readiness

Ready for Plan 227-02. The shared harness now emits the AB-04 marked-vs-unmarked fields and preserves GATE-01 matched-arm comparability for EF-loaded captures.

## Self-Check: PASSED

- Created/modified files exist: `scripts/phase226-baseline-capture.sh`, `scripts/phase226-baseline-summary.py`, `tests/test_phase227_marked_ef.py`.
- Task commits found: `2389642`, `c27c2cc`, `67bab64`.
- SUMMARY created at `.planning/phases/227-candidate-diffserv4-wash-deploy-matched-capture/227-01-SUMMARY.md`.

---
*Phase: 227-candidate-diffserv4-wash-deploy-matched-capture*
*Completed: 2026-06-04*
