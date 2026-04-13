---
phase: 174-production-soak
plan: 01
subsystem: production
tags: [soak, production, storage, observability, validation]
requires:
  - phase: 173-clean-deploy-canary-validation
    plan: 03
    provides: "Dual-WAN canary exit 0, v1.35.0 deployed"
provides:
  - "24h production soak passed for STOR-03 and SOAK-01"
  - "Storage pressure remained non-critical at soak end"
  - "Zero unhandled WAN-service errors over the final 24h window"
  - "Canary, soak monitor, and operator summary evidence captured for production closeout"
affects: [production, storage, observability]
tech-stack:
  added: []
  patterns: ["Bookend soak validation", "4-tool evidence capture"]
key-files:
  created:
    - .planning/phases/174-production-soak/174-soak-evidence-canary.json
    - .planning/phases/174-production-soak/174-soak-evidence-monitor.json
    - .planning/phases/174-production-soak/174-soak-evidence-journalctl.txt
    - .planning/phases/174-production-soak/174-soak-evidence-operator-spectrum.txt
    - .planning/phases/174-production-soak/174-soak-evidence-operator-att.txt
    - .planning/phases/174-production-soak/174-01-SUMMARY.md
  modified:
    - .planning/REQUIREMENTS.md
key-decisions:
  - "Used the latest service start time (steering at 2026-04-12 13:23:35 CDT) as the conservative all-services soak gate."
  - "Validated operator-summary using the deployed CLI contract (`python3 operator_summary.py <health-url>`) because the plan's `--wan` entrypoint was stale on production."
patterns-established:
  - "Soak closeout uses live production evidence files instead of ad hoc terminal transcripts."
requirements-completed: [STOR-03, SOAK-01]
duration: 24h 22m
completed: 2026-04-13
---

# Phase 174 Plan 01: Production Soak Summary

**v1.35.0 cleared the 24-hour production soak with healthy canary results, zero WAN-service errors, and non-critical storage on both WANs.**

## Performance

- **Duration:** 24h 22m
- **Started:** 2026-04-12T13:23:35-05:00
- **Completed:** 2026-04-13T13:45:22-05:00
- **Tasks:** 3
- **Files modified:** 7

## Soak Window

- Conservative all-services gate started from the latest service activation time:
  `steering.service` at `Sun 2026-04-12 13:23:35 CDT`
- Other service start times:
  - `wanctl@spectrum.service`: `Sun 2026-04-12 13:21:59 CDT`
  - `wanctl@att.service`: `Sun 2026-04-12 13:23:21 CDT`
- Final validation artifacts were captured at `2026-04-13 13:45:22 CDT`, leaving all three services past the 24-hour mark.

## Validation Results

### Canary Check

- `./scripts/canary-check.sh --ssh kevin@10.10.110.223 --expect-version 1.35.0 --json`
- Result: pass for `spectrum`, `att`, and `steering`
- Exit code: `0`
- Versions: both autorate services reported `1.35.0`
- Storage status at soak end: `ok` for Spectrum, `ok` for ATT, `ok` for steering

### Soak Monitor

- `./scripts/soak-monitor.sh --json`
- Spectrum health: `healthy`
- Spectrum uptime at capture: `87781.9s`
- Spectrum version: `1.35.0`
- Spectrum states: `DL GREEN`, `UL GREEN`
- Spectrum storage status: `ok`
- Spectrum `errors_1h`: `0`

### Journalctl Error Scan

- `journalctl -u wanctl@spectrum -u wanctl@att --since "24 hours ago" -p err --no-pager`
- Result: `-- No entries --`
- Interpretation: zero unhandled WAN-service errors over the soak closeout window

### Operator Summary

- Spectrum operator summary rendered successfully from the live health URL
- ATT operator summary rendered successfully from the live health URL
- Both outputs produced valid multi-line tables, not tracebacks

## Storage Health

- Spectrum DB/WAL at soak end: `5.1G` / `4.3M`
- ATT DB/WAL at soak end: `4.8G` / `4.3M`
- Spectrum storage status: `ok`
- ATT storage status: `ok`
- Steering storage status at canary closeout: `ok`, DB `621M`

## Requirements Satisfied

- `STOR-03`: satisfied. Storage pressure remained `ok` at soak end for both WANs and never entered `critical` during closeout validation.
- `SOAK-01`: satisfied. Canary passed, operator summaries rendered, soak monitor returned healthy data, and the WAN-service error scan showed zero unhandled errors.

## Task Commits

No code or doc commit was created for this plan because `commit_docs=false` and the plan only captured production evidence plus planning artifacts.

## Files Created/Modified

- `.planning/phases/174-production-soak/174-soak-evidence-canary.json` - JSON canary results with appended exit code
- `.planning/phases/174-production-soak/174-soak-evidence-monitor.json` - machine-readable soak monitor snapshot
- `.planning/phases/174-production-soak/174-soak-evidence-journalctl.txt` - 24-hour WAN-service error scan output
- `.planning/phases/174-production-soak/174-soak-evidence-operator-spectrum.txt` - live Spectrum operator summary output
- `.planning/phases/174-production-soak/174-soak-evidence-operator-att.txt` - live ATT operator summary output
- `.planning/phases/174-production-soak/174-01-SUMMARY.md` - soak closeout summary
- `.planning/REQUIREMENTS.md` - requirement status updated for completed milestone scope

## Decisions Made

- Used the latest service activation time as the formal soak gate, which is the strictest interpretation of "all services clean for 24 hours."
- Treated the deployed operator-summary CLI as authoritative and used live health URLs as sources because the plan's `--wan` syntax no longer matched production.

## Deviations from Plan

### Auto-fixed Issues

**1. Stale operator-summary invocation in the plan**
- **Found during:** Task 2 (4-tool validation capture)
- **Issue:** `/opt/wanctl/.venv/bin/wanctl-operator-summary --wan ...` did not exist on production, and `operator_summary.py` does not accept `--wan`
- **Fix:** Used `sudo -u wanctl python3 operator_summary.py http://<health-endpoint>/health` for each WAN
- **Files modified:** `.planning/phases/174-production-soak/174-soak-evidence-operator-spectrum.txt`, `.planning/phases/174-production-soak/174-soak-evidence-operator-att.txt`
- **Verification:** Both commands produced valid operator tables

**2. DB size lookup required elevated read permissions**
- **Found during:** Task 2 (bonus diagnostics)
- **Issue:** direct listing of `/var/lib/wanctl` failed with permission denied
- **Fix:** Re-ran the size capture with `sudo ls -lh` on the specific DB/WAL paths
- **Files modified:** none
- **Verification:** captured exact `5.1G` / `4.8G` DB sizes and `4.3M` WAL sizes

---

**Total deviations:** 2 auto-fixed
**Impact on plan:** No scope change. Both deviations corrected stale operational commands while preserving the planned evidence and acceptance criteria.

## Issues Encountered

None beyond the stale operator-summary invocation and the need for elevated file listing on production.

## User Setup Required

None.

## Self-Check: PASSED

- Canary exited `0` for Spectrum, ATT, and steering
- Storage was `ok` for both WANs at soak end
- `journalctl -p err` returned no WAN-service errors in the last 24 hours
- Operator summaries rendered successfully for both WANs
- Evidence files and summary were written
- `STOR-03` and `SOAK-01` were marked satisfied in requirements

## Next Phase Readiness

Phase 174 is complete. The v1.35 milestone is ready for `/gsd-complete-milestone`.

---
*Phase: 174-production-soak*
*Completed: 2026-04-13*
