# Phase 174: Production Soak - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md -- this log preserves the alternatives considered.

**Date:** 2026-04-12
**Phase:** 174-production-soak
**Areas discussed:** Soak timeline & checkpoints, End-of-soak validation, Failure response protocol, Completion artifacts

---

## Soak Timeline & Checkpoints

### When should the 24h soak clock start?

| Option | Description | Selected |
|--------|-------------|----------|
| From deploy completion | Clock starts when Phase 173 canary-check.sh returned exit 0 on both WANs | ✓ |
| From explicit start command | Manually declare soak start after verifying everything looks good | |
| From next clean hour | Round up to next hour boundary for cleaner log queries | |

**User's choice:** From deploy completion (Recommended)
**Notes:** None

### Should there be intermediate check-ins during the 24h soak?

| Option | Description | Selected |
|--------|-------------|----------|
| Bookend only | Check at soak start and soak end. soak-monitor.sh --watch available ad-hoc | ✓ |
| Scheduled snapshots | Capture soak-monitor.sh --json at 6h, 12h, 18h, 24h | |
| Continuous watch | Run soak-monitor.sh --watch throughout the soak | |

**User's choice:** Bookend only (Recommended)
**Notes:** None

### Does the 24h need to be strictly consecutive?

| Option | Description | Selected |
|--------|-------------|----------|
| Strictly consecutive | Full 24h without interruption. Any restart resets clock | ✓ (Claude's discretion) |
| Cumulative with tolerance | Single brief restart acceptable if root cause understood | |
| Best-effort window | Accept 20+ clean hours with known gap cause | |

**User's choice:** "You decide"
**Notes:** Claude selected strictly consecutive -- the right default for production stability proofs.

### Should the soak clock count from canary pass or start fresh?

| Option | Description | Selected |
|--------|-------------|----------|
| Count from canary pass | Phase 173 canary already validated. Hours since then count toward 24h | ✓ |
| Start fresh from now | Begin clean 24h from this moment | |

**User's choice:** Count from canary pass (Recommended)
**Notes:** None

---

## End-of-Soak Validation

### What validation commands should run at the 24h mark?

| Option | Description | Selected |
|--------|-------------|----------|
| canary-check.sh exit 0 | Run with --expect-version 1.35.0, must exit 0 for both WANs | ✓ |
| soak-monitor.sh snapshot | Capture final health state, uptime, CAKE signal, error counts | ✓ |
| journalctl error scan | Query -p err for unhandled errors over 24h window, must be zero | ✓ |
| wanctl-operator-summary | Run for both WANs to verify all v1.34 surfaces produce valid output | ✓ |

**User's choice:** All four selected
**Notes:** None

### How should storage pressure be verified at soak end?

| Option | Description | Selected |
|--------|-------------|----------|
| Health endpoint check | curl /health, verify storage.status is ok or warning. Part of canary-check.sh | ✓ |
| Direct DB size check | SSH in and du -sh /var/lib/wanctl/metrics-*.db | |
| Both | Health endpoint for pass/fail, direct size for the record | |

**User's choice:** Health endpoint check (Recommended)
**Notes:** None

---

## Failure Response Protocol

### If a service restarts unexpectedly mid-soak?

| Option | Description | Selected |
|--------|-------------|----------|
| Investigate + restart clock | Diagnose root cause, fix, restart 24h clock | ✓ |
| Log and continue | Note restart, don't reset clock if self-recovered | |
| Immediate fail | Any unexpected restart fails the soak outright | |

**User's choice:** Investigate + restart clock (Recommended)
**Notes:** None

### Non-fatal errors in journalctl?

| Option | Description | Selected |
|--------|-------------|----------|
| Zero unhandled errors | Matches ROADMAP criteria. Known-benign messages don't count | ✓ |
| Error budget | Allow up to N errors per 24h if non-fatal | |
| You decide | Claude uses judgment based on severity | |

**User's choice:** Zero unhandled errors (Recommended)
**Notes:** None

---

## Completion Artifacts

### What should be recorded when the soak passes?

| Option | Description | Selected |
|--------|-------------|----------|
| Soak summary in SUMMARY.md | Start/end timestamps, validation results, final health, DB sizes | ✓ |
| Raw validation output | canary-check --json, soak-monitor --json, journalctl saved as evidence | ✓ |
| REQUIREMENTS.md update | Mark STOR-03 and SOAK-01 as satisfied | ✓ |
| Milestone completion | Run /gsd-complete-milestone to archive v1.35 | ✓ |

**User's choice:** All four selected
**Notes:** None

### Plan structure?

| Option | Description | Selected |
|--------|-------------|----------|
| Single plan (174-01) | One plan covering setup, wait, and validation | ✓ |
| Two plans | 174-01: setup/start, 174-02: validation/artifacts | |

**User's choice:** Single plan (Recommended)
**Notes:** None

---

## Claude's Discretion

- Exact journalctl query flags and time window formatting
- Whether to capture additional diagnostic data in evidence files
- Format and naming of evidence output files
- Strictly consecutive soak (selected by Claude when user deferred)

## Deferred Ideas

None -- discussion stayed within phase scope.
