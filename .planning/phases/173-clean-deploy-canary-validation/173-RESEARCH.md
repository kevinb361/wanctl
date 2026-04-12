# Phase 173: Clean Deploy & Canary Validation - Research

**Researched:** 2026-04-12
**Domain:** Deployment operations, version management, post-deploy health validation
**Confidence:** HIGH

## Summary

Phase 173 is a deployment/operations phase with minimal code changes (version bump only). All tooling is mature and already verified by Phase 172: `deploy.sh` handles rsync-based code deployment, `migrate-storage.sh` archives the legacy 925 MB shared metrics.db, and `canary-check.sh` validates health endpoints with version checking, storage pressure, and service state. Production is currently running v1.32.2 with manually-copied v1.34 modules, so this deploy brings everything to a clean v1.35.0 state.

The critical sequencing is: version bump (3 files) -> deploy code (Spectrum first, then ATT) -> run storage migration (if not already done in Phase 172) -> restart services -> wait for health stabilization -> run canary. The canary's exit code contract is precise: exit 0 requires ALL checks to pass (version match, storage ok, router reachable, uptime >= 10s, download/upload not in unknown state). Any WARN condition produces exit 2, which does NOT satisfy the DEPL-01 requirement of "canary-check.sh returns exit 0."

**Primary recommendation:** Plan as a sequential operational runbook with 2 plans: (1) version bump + commit + push, (2) deploy + migrate + restart + canary validation. Keep it simple -- the scripts are mature.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** Version bump to 1.35.0 in `src/wanctl/__init__.py`, `pyproject.toml`, and `CLAUDE.md`. Standard first release of the v1.35 milestone.
- **D-02:** Rolling deploy -- Spectrum first, then ATT. Spectrum is the primary WAN and validates the deploy path before touching ATT.
- **D-03:** Per-WAN sequence: stop service -> deploy code -> restart service. deploy.sh syncs code via rsync but does NOT restart services -- operator handles start/stop manually.
- **D-04:** Deploy command: `./scripts/deploy.sh spectrum kevin@10.10.110.223` then `./scripts/deploy.sh att kevin@10.10.110.223 --with-steering` (steering only on ATT deploy to avoid duplicate).
- **D-05:** Run `./scripts/migrate-storage.sh --ssh kevin@10.10.110.223` AFTER code deploy but BEFORE service restart. This archives the legacy shared metrics.db so the new per-WAN DB paths (from Phase 172 D-05) are ready when services start.
- **D-06:** If migrate-storage.sh has already been run during Phase 172 execution, skip it here. Check for archived DB file to determine if migration already happened.
- **D-07:** Run `./scripts/canary-check.sh --ssh kevin@10.10.110.223 --expect-version 1.35.0` after both services are restarted. Must exit 0 for both Spectrum and ATT.
- **D-08:** Verify per-WAN DB files exist (metrics-spectrum.db, metrics-att.db) after canary passes -- confirms Phase 172 DB split is live.
- **D-09:** Check storage pressure status is not `critical` post-deploy -- validates Phase 172 retention tuning took effect.

### Claude's Discretion
- Exact systemctl stop/start commands and waiting strategy between operations
- Whether to run a quick dry-run deploy first (`deploy.sh --dry-run`)
- Config diff verification approach before deploy (per feedback memory: always diff production config before deploy.sh)

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| DEPL-01 | A clean `deploy.sh` run deploys v1.35 with version bump, and canary-check.sh returns exit 0 on all services | Version bump in 3 files, deploy.sh rsync pipeline, canary exit code contract (0/1/2), service restart sequencing, storage migration timing |
</phase_requirements>

## Standard Stack

### Core
| Tool | Version | Purpose | Why Standard |
|------|---------|---------|--------------|
| deploy.sh | N/A (bash) | rsync-based code + config + systemd deployment | Mature, handles all deployment artifacts including profiling scripts, analysis scripts, NIC tuning, bridge QoS, sysctl, systemd units [VERIFIED: scripts/deploy.sh] |
| canary-check.sh | 1.0.0 | Post-deploy health validation with exit code contract | Checks version, storage, router, runtime, download/upload state. Exit 0/1/2. [VERIFIED: scripts/canary-check.sh] |
| migrate-storage.sh | N/A (bash) | One-shot DB archival (legacy shared -> per-WAN) | Purges >24h data, VACUUMs, archives. Idempotent (skips if archive exists). [VERIFIED: scripts/migrate-storage.sh] |
| systemctl | system | Service lifecycle management | Standard for wanctl@{wan}.service and steering.service |

### Supporting
| Tool | Version | Purpose | When to Use |
|------|---------|---------|-------------|
| ssh | system | Remote command execution on cake-shaper VM | All remote operations (deploy.sh uses it internally) |
| diff | system | Config comparison | MUST diff production config before deploy (per feedback_diff_config_before_deploy.md) |

## Architecture Patterns

### Deploy Sequence (Locked by D-02, D-03)

```
1. Version bump (3 files) + commit + push
2. Config diff: ssh production, diff deployed configs vs repo configs
3. Spectrum deploy:
   a. Stop wanctl@spectrum.service
   b. ./scripts/deploy.sh spectrum kevin@10.10.110.223
   c. (do NOT restart yet)
4. ATT deploy:
   a. Stop wanctl@att.service + steering.service
   b. ./scripts/deploy.sh att kevin@10.10.110.223 --with-steering
   c. (do NOT restart yet)
5. Storage migration (if not already done):
   a. Check: ssh ... "sudo test -f /var/lib/wanctl/metrics.db.pre-v135-archive"
   b. If archive does NOT exist: ./scripts/migrate-storage.sh --ssh kevin@10.10.110.223
   c. If archive exists: skip (D-06)
6. Restart services:
   a. sudo systemctl start wanctl@spectrum.service
   b. sudo systemctl start wanctl@att.service
   c. sudo systemctl start steering.service
7. Wait for stabilization (~30s for uptime check + initial health data)
8. Canary:
   a. ./scripts/canary-check.sh --ssh kevin@10.10.110.223 --expect-version 1.35.0
   b. Must exit 0
9. Post-canary verification:
   a. Verify per-WAN DB files exist
   b. Verify storage pressure not critical
```

### Version Bump Pattern
Three files must be updated atomically in a single commit [VERIFIED: codebase grep]:

| File | Field | Current | Target |
|------|-------|---------|--------|
| `src/wanctl/__init__.py` | `__version__` | `"1.32.2"` | `"1.35.0"` |
| `pyproject.toml` | `version` | `"1.32.2"` | `"1.35.0"` |
| `CLAUDE.md` | `**Version:**` | `1.32.2` | `1.35.0` |

### Version Propagation Path
`__init__.py` -> `health_check.py` imports `__version__` -> `/health` JSON `.version` field -> canary `--expect-version` check [VERIFIED: grep of import chain]

### Canary Exit Code Contract [VERIFIED: scripts/canary-check.sh]

| Exit Code | Meaning | Conditions |
|-----------|---------|------------|
| 0 (PASS) | All checks passed | Every check is PASS |
| 1 (FAIL) | Blocking failures | Any: endpoint unreachable, router unreachable, storage critical, runtime critical, download/upload state unknown |
| 2 (WARN) | Warnings present | Any: version mismatch, storage warning, runtime warning, uptime < 10s, download/upload SOFT_RED/RED |

**Critical insight:** DEPL-01 requires exit 0, not just "no failures." A version mismatch (exit 2) or uptime < 10s (exit 2) or storage warning (exit 2) would fail the requirement. The plan must ensure:
- Version is bumped before deploy so the health endpoint reports 1.35.0
- Services have been running >= 10 seconds before canary
- Storage is `ok` not just `not critical` (migration must complete before service restart)

### deploy.sh Behavior [VERIFIED: scripts/deploy.sh]
- Deploys: code (rsync), config, profiling scripts, analysis scripts, docs, NIC tuning, sysctl, bridge QoS, systemd units, validation script, wanctl-history CLI
- Does NOT restart services (operator responsibility per D-03)
- Has `--dry-run` mode for pre-flight check
- Has `--with-steering` flag for steering daemon deployment
- Runs `verify_deployment()` which checks file counts, core script, config, secrets, systemd template
- Runs `validate-deployment.sh` pre-startup check

### migrate-storage.sh Behavior [VERIFIED: scripts/migrate-storage.sh]
- Stops both wanctl services before migration (lines 113-114)
- Purges data older than 24h from legacy DB
- Runs VACUUM to reclaim space
- Archives legacy DB as `metrics.db.pre-v135-archive`
- Handles WAL and SHM files
- Idempotent: exits cleanly if archive already exists or legacy DB is missing
- Has `--dry-run` and `--ssh` flags
- Prints next steps including service start and canary

**Migration service stop concern:** migrate-storage.sh stops both services itself (line 114). If services are already stopped (from the deploy sequence), the `|| true` suffix means it won't error. But the plan must account for the fact that after migration, services need to be manually restarted -- the migration script does NOT restart them.

### Anti-Patterns to Avoid
- **Restarting services before migration:** Per-WAN DB paths are configured but if legacy metrics.db still exists and is large, the first write cycle could hit contention or stale state.
- **Running canary too early:** Uptime < 10s triggers a WARN (exit 2). Wait at least 15-20 seconds after service start.
- **Forgetting steering.service:** The canary checks steering by default. If steering isn't running, it will FAIL. Use `--skip-steering` only if steering is intentionally down.
- **Deploying without config diff:** Per project feedback memory, always diff production config before deploy.sh because it syncs config too.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Code deployment | Manual scp/rsync commands | `deploy.sh` | Handles 10+ deployment targets atomically, with verification |
| Health validation | Manual curl + parsing | `canary-check.sh` | Comprehensive checks with proper exit codes, SSH tunneling, JSON mode |
| DB migration | Manual sqlite3 commands | `migrate-storage.sh` | Handles purge, VACUUM, archive, WAL/SHM cleanup, idempotency |
| Service management | Ad-hoc systemctl | Structured stop-deploy-migrate-start sequence | Order matters for data integrity |

**Key insight:** All three scripts are mature, verified by Phase 172, and support `--dry-run` and `--ssh` flags. The plan should execute them as-is, not reimplement any logic.

## Common Pitfalls

### Pitfall 1: Canary Exit 2 Treated as Success
**What goes wrong:** Canary reports WARN (exit 2) due to version mismatch, low uptime, or storage warning. Operator assumes "no failures = success."
**Why it happens:** Exit 2 is not exit 1, so it doesn't feel like a failure.
**How to avoid:** The DEPL-01 requirement explicitly says "exit 0." The plan must check `$?` and only proceed if it equals 0.
**Warning signs:** Canary output shows any `[WARN]` lines.

### Pitfall 2: Service Start Order Creates Brief Failure Window
**What goes wrong:** Starting steering before autorate means steering can't read WAN state, causing temporary health check failures.
**Why it happens:** Steering depends on autorate WAN state files.
**How to avoid:** Start autorate services first (spectrum, att), wait a few seconds, then start steering.
**Warning signs:** Steering health endpoint shows router unreachable or missing WAN data.

### Pitfall 3: Migration Script Stops Services Redundantly
**What goes wrong:** migrate-storage.sh stops wanctl@spectrum and wanctl@att (line 114). If the plan already stopped them, this is harmless but confusing. If the plan hasn't stopped them, the migration will stop them.
**Why it happens:** The migration script is designed to be safe standalone.
**How to avoid:** The plan should stop services as part of deploy sequence (D-03), then run migration. The script's stop commands are no-ops in that case.
**Warning signs:** None -- this is handled gracefully by `|| true`.

### Pitfall 4: Config Drift Between Repo and Production
**What goes wrong:** deploy.sh deploys config from the repo. If production has been manually tuned since last deploy, those changes are overwritten.
**Why it happens:** rsync syncs the full config, not just code.
**How to avoid:** Diff production configs against repo configs BEFORE deploying (per feedback_diff_config_before_deploy.md). Resolve any differences first.
**Warning signs:** Unexpected config values after deploy; changed behavior in autorate.

### Pitfall 5: Stale metrics.db Prevents Clean Per-WAN Start
**What goes wrong:** If migration is skipped and old metrics.db is still present, services might use legacy path instead of per-WAN paths.
**Why it happens:** Phase 172 added per-WAN db_path in configs, but if the config wasn't deployed yet, old code uses old path.
**How to avoid:** Migration archives the legacy DB. Even if skipped (D-06), the per-WAN config in spectrum.yaml/att.yaml explicitly sets `db_path` so the new code creates fresh per-WAN DBs regardless.
**Warning signs:** Only one metrics.db file instead of metrics-spectrum.db + metrics-att.db after restart.

## Code Examples

### Version Bump (3 files)
```python
# src/wanctl/__init__.py
# Source: verified from current codebase
__version__ = "1.35.0"  # was "1.32.2"
```

```toml
# pyproject.toml line 3
# Source: verified from current codebase
version = "1.35.0"  # was "1.32.2"
```

```markdown
# CLAUDE.md line 11
# Source: verified from current codebase
**Version:** 1.35.0  # was 1.32.2
```

### Config Diff Before Deploy
```bash
# Source: feedback_diff_config_before_deploy.md pattern
ssh kevin@10.10.110.223 "sudo cat /etc/wanctl/spectrum.yaml" | diff - configs/spectrum.yaml
ssh kevin@10.10.110.223 "sudo cat /etc/wanctl/att.yaml" | diff - configs/att.yaml
```

### Migration Idempotency Check
```bash
# Source: migrate-storage.sh line 98-102
ssh kevin@10.10.110.223 "sudo test -f /var/lib/wanctl/metrics.db.pre-v135-archive && echo 'ALREADY_MIGRATED' || echo 'NEEDS_MIGRATION'"
```

### Service Lifecycle
```bash
# Stop (before deploy)
ssh kevin@10.10.110.223 "sudo systemctl stop wanctl@spectrum.service"
ssh kevin@10.10.110.223 "sudo systemctl stop wanctl@att.service"
ssh kevin@10.10.110.223 "sudo systemctl stop steering.service"

# Start (after deploy + migration)
ssh kevin@10.10.110.223 "sudo systemctl start wanctl@spectrum.service"
ssh kevin@10.10.110.223 "sudo systemctl start wanctl@att.service"
ssh kevin@10.10.110.223 "sudo systemctl start steering.service"
```

### Canary with Version Expectation
```bash
# Source: canary-check.sh usage + CONTEXT D-07
./scripts/canary-check.sh --ssh kevin@10.10.110.223 --expect-version 1.35.0
echo "Exit code: $?"  # Must be 0
```

### Post-Canary DB File Verification
```bash
# Source: CONTEXT D-08
ssh kevin@10.10.110.223 "sudo ls -lh /var/lib/wanctl/metrics-spectrum.db /var/lib/wanctl/metrics-att.db"
```

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.x with xdist |
| Config file | `pyproject.toml` [tool.pytest.ini_options] |
| Quick run command | `.venv/bin/pytest tests/ -x -q --timeout=10` |
| Full suite command | `.venv/bin/pytest tests/ -v` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| DEPL-01 (version bump) | Version string updated in 3 files | smoke | `python3 -c "from wanctl import __version__; assert __version__ == '1.35.0'"` | N/A (inline) |
| DEPL-01 (deploy) | deploy.sh completes without error | manual-only | `./scripts/deploy.sh spectrum kevin@10.10.110.223` | N/A (live operation) |
| DEPL-01 (canary) | canary-check.sh returns exit 0 | manual-only | `./scripts/canary-check.sh --ssh kevin@10.10.110.223 --expect-version 1.35.0` | N/A (live operation) |

### Sampling Rate
- **Per task commit:** Version string check only (no deploy in CI)
- **Per wave merge:** N/A (single wave)
- **Phase gate:** Canary exit 0 on live production

### Wave 0 Gaps
None -- this phase uses existing test infrastructure and live operational validation. No new test files needed.

## Assumptions Log

> List all claims tagged [ASSUMED] in this research.

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Steering service should be started after autorate services for clean health state | Common Pitfalls | LOW -- steering may handle missing WAN state gracefully, but ordering is safer |
| A2 | Services need ~15-20s before canary to avoid uptime WARN | Architecture Patterns | LOW -- 10s is the threshold; 15-20s provides margin |

**If this table is empty:** Most claims in this research were verified directly from script source code.

## Open Questions

1. **Has migrate-storage.sh already been run during Phase 172?**
   - What we know: Phase 172 verification says "human_needed" for STOR-01, requiring the operator to run the migration.
   - What's unclear: Whether the operator (Kevin) already ran it as part of Phase 172 work.
   - Recommendation: Plan includes an idempotency check (D-06). If archive exists, skip. No action needed from planner -- the script handles this.

2. **Will storage status be `ok` or `warning` after migration + fresh per-WAN DBs?**
   - What we know: Fresh per-WAN DBs start empty. 24h retention is configured. Storage pressure thresholds are generous for small DBs.
   - What's unclear: Whether first few minutes of data collection could trigger a brief `warning` state.
   - Recommendation: Fresh empty DBs should read as `ok`. If `warning` appears transiently, it would clear within a cycle. Canary has 30s timeout, so a brief transient should resolve.

## Environment Availability

> This is a deployment phase. All execution happens on the remote cake-shaper VM, accessed via SSH.

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| SSH to 10.10.110.223 | All deploy/canary operations | Assumed available | N/A | None -- blocking |
| rsync (local) | deploy.sh | Likely available | N/A | deploy.sh checks and exits with error |
| rsync (remote) | deploy.sh | Likely available | N/A | deploy.sh checks and exits with error |
| sqlite3 (remote) | migrate-storage.sh | Likely available | N/A | Migration fails -- blocking |
| systemctl (remote) | Service management | Available | N/A | N/A |
| python3 (remote) | canary-check.sh (jq fallback) | Available | 3.11+ | N/A |

**Missing dependencies with no fallback:**
- None expected. SSH connectivity to cake-shaper VM is a prerequisite verified in prior phases.

## Sources

### Primary (HIGH confidence)
- `scripts/deploy.sh` -- Full deployment pipeline (643 lines), read in entirety
- `scripts/canary-check.sh` -- Canary validation (505 lines), read in entirety
- `scripts/migrate-storage.sh` -- DB migration (243 lines), read in entirety
- `src/wanctl/__init__.py` -- Version string, confirmed 1.32.2
- `pyproject.toml` -- Version field, confirmed 1.32.2
- `CLAUDE.md` -- Version field, confirmed 1.32.2
- `src/wanctl/health_check.py:200` -- Version exposed via `__version__` import
- `deploy/systemd/wanctl@.service` -- Service unit, confirmed configuration
- `deploy/systemd/steering.service` -- Steering unit, confirmed configuration
- `.planning/phases/172-storage-health-code-fixes/172-VERIFICATION.md` -- Phase 172 completion status
- `.planning/phases/173-clean-deploy-canary-validation/173-CONTEXT.md` -- All locked decisions

### Secondary (MEDIUM confidence)
- Canary exit code semantics derived from reading the bash case statements and exit logic in canary-check.sh

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- all scripts read in full, behavior confirmed from source
- Architecture: HIGH -- deploy sequence locked by CONTEXT.md decisions, verified against script behavior
- Pitfalls: HIGH -- derived from reading actual script logic and project feedback memories

**Research date:** 2026-04-12
**Valid until:** 2026-05-12 (stable -- scripts and deploy process are mature)
