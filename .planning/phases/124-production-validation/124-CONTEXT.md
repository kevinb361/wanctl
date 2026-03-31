# Phase 124: Production Validation - Context

**Gathered:** 2026-03-31
**Status:** Ready for planning

<domain>
## Phase Boundary

Deploy hysteresis code to production, validate flapping is eliminated during one prime-time evening window, verify genuine congestion detection latency, then version bump + CHANGELOG + tag + push to complete the v1.24 milestone.

</domain>

<decisions>
## Implementation Decisions

### Deploy Strategy
- **D-01:** Deploy via `deploy.sh` to cake-shaper VM (10.10.110.223 Spectrum, 10.10.110.227 ATT). Hysteresis defaults (dwell_cycles=3, deadband_ms=3.0) take effect automatically with no YAML config changes needed. Diff production config before deploy per standard practice. No explicit YAML values — rely on code defaults.

### Validation Window
- **D-02:** One prime-time evening (7pm-11pm CDT) soak. Pass criteria: zero flapping alerts during the window AND health endpoint `transitions_suppressed > 0` confirming hysteresis is actively absorbing transients. RRUL stress test during or after the window to verify genuine congestion detection within 500ms latency budget.

### Rollback
- **D-03:** If flapping worsens or genuine congestion goes undetected during soak, set dwell_cycles=0 via YAML + SIGUSR1 to disable hysteresis without rollback. This is the escape hatch designed in Phase 122 (CONF-01: min=0 allows disabling).

### Version & Release
- **D-04:** After validation passes, bundle into this phase: bump pyproject.toml + __init__.py to v1.24.0, update CHANGELOG (move [Unreleased] to [1.24.0] section, add hysteresis entries for phases 121-124), update CLAUDE.md version reference, git tag v1.24, push all commits + tag to origin. Single phase closes the entire milestone.

### Claude's Discretion
- Exact CHANGELOG entry wording for hysteresis features
- Whether to update Known Issues section (remove EWMA flapping entry if validation passes)
- RRUL test parameters (duration, streams)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Deployment
- `scripts/deploy.sh` — Unified deployment script (rsync-based, FHS paths)
- `.planning/phases/121-core-hysteresis-logic/121-CONTEXT.md` — D-01 through D-05 on dwell/deadband behavior
- `.planning/phases/122-hysteresis-configuration/122-01-SUMMARY.md` — Config parsing details
- `.planning/phases/123-hysteresis-observability/123-01-SUMMARY.md` — Health endpoint hysteresis fields

### Version Files
- `pyproject.toml` line 3 — `version = "1.20.0"` (STALE — needs bump to 1.24.0)
- `src/wanctl/__init__.py` line 3 — `__version__ = "1.23.0"` (needs bump to 1.24.0)
- `CHANGELOG.md` — [Unreleased] section has spike detector fix + analysis record; needs v1.24.0 section with hysteresis entries
- `CLAUDE.md` — Version reference says v1.23.0, needs update to v1.24.0

### Production
- Memory: `project_cake_shaper_vm.md` — VM 206, SSH via `kevin@10.10.110.223`, sudo required for config/state
- Memory: `feedback_diff_config_before_deploy.md` — ALWAYS diff production config before deploy.sh

### Requirements
- `.planning/REQUIREMENTS.md` — VALN-01 (zero flapping) and VALN-02 (RRUL latency budget)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `deploy.sh` handles full deployment: rsync code, sync config, restart services
- `scripts/soak-monitor.sh` for monitoring during validation
- Health endpoint at `http://127.0.0.1:9101/health` exposes hysteresis state directly
- `wanctl-check-cake` CLI verifies CAKE qdiscs are active

### Established Patterns
- Prior validation pattern (v1.23.1 spike fix): deploy, observe N prime-time windows, document results in CHANGELOG analysis record
- Version bump: update pyproject.toml + __init__.py + CHANGELOG + CLAUDE.md, then `git tag vX.Y`
- Deploy incident learning: always diff config, always check exclude_params after deploy

### Integration Points
- `ssh kevin@10.10.110.223` for Spectrum WAN (primary validation target)
- `ssh kevin@10.10.110.227` for ATT WAN (secondary)
- Discord webhooks on all 3 services will fire alerts during soak
- `journalctl -u wanctl@spectrum -f` for live log monitoring
- `curl -s http://127.0.0.1:9101/health | python3 -m json.tool` for health endpoint

</code_context>

<specifics>
## Specific Ideas

- Validation criteria from REQUIREMENTS.md:
  - VALN-01: Zero flapping alerts during 7pm-11pm CDT (vs 1-3 pairs/evening baseline)
  - VALN-02: RRUL stress test triggers YELLOW within 500ms of no-hysteresis baseline (dwell_cycles=3 at 50ms = 150ms additional latency)
  - Health endpoint transitions_suppressed > 0 (confirms active suppression)
- Version 1.24.0 naming: "EWMA Boundary Hysteresis" (from milestone name)
- pyproject.toml is currently 3 versions behind (1.20.0) — single bump to 1.24.0

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 124-production-validation*
*Context gathered: 2026-03-31*
