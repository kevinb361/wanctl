# Phase 173: Clean Deploy & Canary Validation - Context

**Gathered:** 2026-04-12
**Status:** Ready for planning

<domain>
## Phase Boundary

Version bump to 1.35.0, deploy to production via deploy.sh for both WANs, run storage migration, restart services, and validate with canary-check.sh exit 0. This is a deployment/operations phase -- no code changes beyond version bump.

</domain>

<decisions>
## Implementation Decisions

### Version Number
- **D-01:** Version bump to 1.35.0 in `src/wanctl/__init__.py`, `pyproject.toml`, and `CLAUDE.md`. Standard first release of the v1.35 milestone.

### Deploy & Restart Sequence
- **D-02:** Rolling deploy -- Spectrum first, then ATT. Spectrum is the primary WAN and validates the deploy path before touching ATT.
- **D-03:** Per-WAN sequence: stop service -> deploy code -> restart service. deploy.sh syncs code via rsync but does NOT restart services -- operator handles start/stop manually.
- **D-04:** Deploy command: `./scripts/deploy.sh spectrum kevin@10.10.110.223` then `./scripts/deploy.sh att kevin@10.10.110.223 --with-steering` (steering only on ATT deploy to avoid duplicate).

### Storage Migration Timing
- **D-05:** Run `./scripts/migrate-storage.sh --ssh kevin@10.10.110.223` AFTER code deploy but BEFORE service restart. This archives the legacy shared metrics.db so the new per-WAN DB paths (from Phase 172 D-05) are ready when services start.
- **D-06:** If migrate-storage.sh has already been run during Phase 172 execution, skip it here. Check for archived DB file to determine if migration already happened.

### Canary Validation
- **D-07:** Run `./scripts/canary-check.sh --ssh kevin@10.10.110.223 --expect-version 1.35.0` after both services are restarted. Must exit 0 for both Spectrum and ATT.
- **D-08:** Verify per-WAN DB files exist (metrics-spectrum.db, metrics-att.db) after canary passes -- confirms Phase 172 DB split is live.
- **D-09:** Check storage pressure status is not `critical` post-deploy -- validates Phase 172 retention tuning took effect.

### Claude's Discretion
- Exact systemctl stop/start commands and waiting strategy between operations
- Whether to run a quick dry-run deploy first (`deploy.sh --dry-run`)
- Config diff verification approach before deploy (per feedback memory: always diff production config before deploy.sh)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Deployment Scripts
- `scripts/deploy.sh` -- Unified deployment script: rsync code, deploy configs, systemd units, scripts, QoS assets
- `scripts/canary-check.sh` -- Post-deploy health validation: endpoint checks, version verification, exit code contract
- `scripts/migrate-storage.sh` -- One-shot DB archival for shared-to-per-WAN migration

### Version Files
- `src/wanctl/__init__.py` -- `__version__` string (currently 1.32.2)
- `pyproject.toml` -- `version` field (currently 1.32.2)
- `CLAUDE.md` -- `**Version:**` field (currently 1.32.2)

### Phase 172 Context (prerequisite)
- `.planning/phases/172-storage-health-code-fixes/172-CONTEXT.md` -- Per-WAN DB split decisions (D-05 through D-07), retention tuning (D-01 through D-04)

### Configuration
- `configs/spectrum.yaml` -- Spectrum WAN production config (updated with 24h retention in Phase 172)
- `configs/att.yaml` -- ATT WAN production config (updated with 24h retention in Phase 172)

### Service Units
- `deploy/systemd/wanctl@.service` -- Template unit for per-WAN autorate services
- `deploy/systemd/steering.service` -- Steering daemon unit

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `deploy.sh` -- Full deployment pipeline with rsync, config deploy, systemd, verification, next-steps output. Mature and well-tested.
- `canary-check.sh` -- Comprehensive health validation with `--expect-version`, `--ssh`, `--json` modes. Already supports all needed validation.
- `migrate-storage.sh` -- Purpose-built for the DB migration. Has `--dry-run` and `--ssh` flags.

### Established Patterns
- Version bump requires 3 files: `__init__.py`, `pyproject.toml`, `CLAUDE.md` (per feedback memory: feedback_always_bump_version.md)
- deploy.sh is per-WAN: must be run once for each WAN (spectrum, att)
- Production host is cake-shaper VM at 10.10.110.223 (SSH: `kevin@10.10.110.223`)
- Config diff before deploy is mandatory (per feedback memory: feedback_diff_config_before_deploy.md)

### Integration Points
- systemd services: `wanctl@spectrum.service`, `wanctl@att.service`, `steering.service`
- Health endpoints: Spectrum at 10.10.110.223:9101, ATT at 10.10.110.227:9101
- Storage state: `/var/lib/wanctl/` -- where per-WAN DBs and state files live

</code_context>

<specifics>
## Specific Ideas

No specific requirements -- standard deploy procedure guided by the decisions above. Production is currently running v1.32.2 with manually-copied v1.34 modules, so this deploy brings everything into a clean, versioned state.

</specifics>

<deferred>
## Deferred Ideas

None -- discussion stayed within phase scope.

### Reviewed Todos (not folded)
- **Evaluate download DSCP tin classification** -- controller tuning, not deployment scope
- **Improve reflector path diversity for ICMP resilience** -- controller tuning, not deployment scope
- **Keep ATT feature parity with Spectrum** -- operations concern, but not specific to this deploy
- **Investigate shared metrics.db write contention** -- already addressed by Phase 172 D-05 (per-WAN DB split)

</deferred>

---

*Phase: 173-clean-deploy-canary-validation*
*Context gathered: 2026-04-12*
