# Phase 174: Production Soak - Context

**Gathered:** 2026-04-12
**Status:** Ready for planning

<domain>
## Phase Boundary

24h production soak validating that the v1.35 storage health fixes, per-WAN DB split, and full v1.34 observability stack run cleanly under real load. This is an observation/validation phase -- no code changes. Proves STOR-03 and SOAK-01 requirements.

</domain>

<decisions>
## Implementation Decisions

### Soak Timeline
- **D-01:** Soak clock starts from Phase 173 canary-check.sh exit 0 on both WANs. No separate start ceremony -- the deploy completion IS the soak start.
- **D-02:** Soak window is strictly consecutive 24 hours. Any unexpected service restart resets the 24h clock after investigation and fix.
- **D-03:** Count valid uptime already accumulated since Phase 173 canary pass toward the 24h window.

### Check-in Cadence
- **D-04:** Bookend only -- check at soak start (already done via Phase 173 canary) and soak end (24h mark). No mandatory intermediate snapshots.
- **D-05:** soak-monitor.sh --watch available for ad-hoc curiosity checks but not required.

### End-of-Soak Validation
- **D-06:** Run all four validation tools at the 24h mark:
  1. `canary-check.sh --ssh kevin@10.10.110.223 --expect-version 1.35.0` -- must exit 0 for both WANs
  2. `soak-monitor.sh --json` -- capture final health state, uptime, CAKE signal, error counts
  3. `journalctl -u wanctl@spectrum -u wanctl@att --since '24 hours ago' -p err` -- must show zero unhandled errors
  4. `wanctl-operator-summary` for both WANs -- verify all v1.34 surfaces produce valid output
- **D-07:** Storage pressure verified via health endpoint (storage.status must be 'ok' or 'warning', not 'critical'). Already part of canary-check.sh contract.

### Failure Response Protocol
- **D-08:** Unexpected service restart: investigate root cause, fix if needed, then restart the 24h clock. The soak proves stability -- a restart means it hasn't proved it yet.
- **D-09:** Error standard: zero unhandled errors in journalctl over the 24h window. Known-benign messages (e.g., DOCSIS MAP jitter suppression logs) don't count if already documented.

### Completion Artifacts
- **D-10:** Single plan (174-01) covering setup, wait, and validation. Simple structure for an observation phase.
- **D-11:** On soak pass, produce:
  1. Phase SUMMARY.md with soak start/end timestamps, validation results, final health state, DB sizes
  2. Raw validation output (canary-check --json, soak-monitor --json, journalctl excerpt) saved as evidence files in phase directory
  3. REQUIREMENTS.md updated -- mark STOR-03 and SOAK-01 as satisfied
  4. Milestone completion via /gsd-complete-milestone to archive v1.35

### Claude's Discretion
- Exact journalctl query flags and time window formatting
- Whether to capture additional diagnostic data (DB file sizes, WAL sizes) in the evidence files
- Format and naming of evidence output files

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Validation Scripts
- `scripts/canary-check.sh` -- Post-deploy health validation: endpoint checks, version verification, exit code contract (0=pass, 1=fail, 2=warn)
- `scripts/soak-monitor.sh` -- Real-time soak monitoring: --watch for continuous, --json for machine-readable output
- `src/wanctl/cli/operator_summary.py` -- Operator summary CLI entry point (wanctl-operator-summary)

### Health & Pressure
- `src/wanctl/health_check.py` -- Health endpoint integrating storage pressure, WAN state, CAKE signal
- `src/wanctl/runtime_pressure.py` -- DB size thresholds, WAL monitoring, RSS classification, storage.status field

### Phase 172 Context (prerequisite)
- `.planning/phases/172-storage-health-code-fixes/172-CONTEXT.md` -- Per-WAN DB split (D-05 through D-07), 24h retention (D-01 through D-04), maintenance error fix (D-08/D-09)

### Phase 173 Context (prerequisite)
- `.planning/phases/173-clean-deploy-canary-validation/173-CONTEXT.md` -- Deploy sequence, canary validation, version bump

### Requirements
- `.planning/REQUIREMENTS.md` -- STOR-03 (storage pressure 24h) and SOAK-01 (observability stack 24h) mapped to this phase

### Service Units
- `deploy/systemd/wanctl@.service` -- Template unit for per-WAN autorate services
- `deploy/systemd/steering.service` -- Steering daemon unit

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `soak-monitor.sh` -- Full soak dashboard with health, uptime, CAKE signal, error counts, colorized output. Supports --json for machine-readable capture.
- `canary-check.sh` -- Comprehensive health validation with --expect-version, --ssh, --json modes. Exit code contract (0/1/2) provides clear pass/fail.
- `wanctl-operator-summary` -- CLI for operator summaries across both WANs. Validates all v1.34 operator surfaces.

### Established Patterns
- Health endpoints: Spectrum at 10.10.110.223:9101, ATT at 10.10.110.227:9101
- Production host: cake-shaper VM 206 at 10.10.110.223 (SSH: kevin@10.10.110.223)
- Service names: wanctl@spectrum.service, wanctl@att.service, steering.service
- Per-WAN DB files: /var/lib/wanctl/metrics-spectrum.db, /var/lib/wanctl/metrics-att.db

### Integration Points
- journalctl for service log analysis (error scanning, restart detection)
- systemd service status for uptime verification
- /health endpoint JSON for storage pressure status

</code_context>

<specifics>
## Specific Ideas

No specific requirements -- standard soak procedure guided by the decisions above. The key insight is that valid uptime since Phase 173 canary pass counts toward the 24h window, so the soak may already be partially complete.

</specifics>

<deferred>
## Deferred Ideas

None -- discussion stayed within phase scope.

</deferred>

---

*Phase: 174-production-soak*
*Context gathered: 2026-04-12*
