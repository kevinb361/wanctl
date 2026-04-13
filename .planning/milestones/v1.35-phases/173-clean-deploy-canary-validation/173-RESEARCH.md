# Phase 173: Clean Deploy & Canary Validation - Research (Refreshed)

**Researched:** 2026-04-12 (forced re-research after Codex review)
**Domain:** Deployment operations, version management, post-deploy health validation
**Confidence:** HIGH

## Summary

Phase 173 deploys v1.35.0 to production. All tooling is mature. The critical concern raised by the Codex review is that the original plan stopped all services up front (coordinated outage) rather than doing a true per-WAN rolling canary. This research confirms the Codex concern is valid but also identifies a structural constraint: `canary-check.sh` always checks BOTH Spectrum and ATT in a single invocation with no per-WAN mode. True per-WAN isolation requires using manual `curl` commands for the intermediate Spectrum-only validation, then running the full canary after ATT is also up.

The second key finding is that `migrate-storage.sh` stops both services itself (line 114: `sudo systemctl stop wanctl@spectrum.service wanctl@att.service`). This means: (1) you cannot migrate while one WAN is running and another is stopped, and (2) migration is inherently a global operation. The per-WAN canary sequence must account for migration happening after Spectrum deploy but before Spectrum restart, which also stops ATT if ATT was still running.

Rollback feasibility is limited. `deploy.sh` has no rollback mechanism. The only path is re-running `deploy.sh` from a git checkout of the previous known-good commit. Since rsync `--delete` is used, the deploy atomically replaces all Python files on target.

**Primary recommendation:** Plan as 2 waves: (1) version bump + commit + push, (2) rolling deploy with manual per-WAN health checks between Spectrum and ATT, full canary at the end. Account for migrate-storage.sh stopping both services.

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
| DEPL-01 | A clean `deploy.sh` run deploys v1.35 with version bump, and canary-check.sh returns exit 0 on all services | Version bump in 3 files, deploy.sh rsync pipeline, canary exit code contract (0/1/2), per-WAN rolling sequence, storage migration timing, rollback strategy |
</phase_requirements>

## Standard Stack

### Core
| Tool | Version | Purpose | Why Standard |
|------|---------|---------|--------------|
| deploy.sh | N/A (bash) | rsync-based code + config + systemd deployment | Mature, handles all deployment artifacts. Uses `rsync -av --delete` so deploys are atomic replace. [VERIFIED: scripts/deploy.sh] |
| canary-check.sh | 1.0.0 | Post-deploy health validation with exit code contract | Checks version, storage, router, runtime, download/upload state. Exit 0/1/2. [VERIFIED: scripts/canary-check.sh] |
| migrate-storage.sh | N/A (bash) | One-shot DB archival (legacy shared -> per-WAN) | Purges >24h data, VACUUMs, archives. Idempotent. STOPS BOTH SERVICES. [VERIFIED: scripts/migrate-storage.sh] |
| systemctl | system | Service lifecycle management | Standard for wanctl@{wan}.service and steering.service |

## Architecture Patterns

### Critical Finding: migrate-storage.sh Stops Both Services

The migration script contains this on line 114 [VERIFIED: scripts/migrate-storage.sh]:

```bash
run_cmd sudo systemctl stop wanctl@spectrum.service wanctl@att.service 2>/dev/null || true
```

This means:
1. Migration is a **global** operation -- it stops both WANs regardless of current state
2. You cannot run migration while one WAN service is still active
3. The `|| true` means it succeeds even if services are already stopped
4. After migration completes, NEITHER service is running -- manual restart required

**Impact on per-WAN canary:** The original plan's approach of "stop both services, deploy both, migrate, restart both" is actually what the migration script forces anyway. The Codex review's concern about "stop-all-services defeats rolling/canary purpose" is valid in principle, but the migration step inherently requires both services down. The per-WAN isolation happens AFTER migration, during the restart/validation phase.

### Recommended Deploy Sequence (Addressing Codex Review)

```
1. Version bump (3 files) + commit + push

2. Pre-flight:
   a. Config diff: compare repo configs with production configs
   b. Optional: deploy.sh --dry-run for both WANs

3. Stop Spectrum ONLY:
   a. ssh ... "sudo systemctl stop wanctl@spectrum.service"

4. Deploy Spectrum:
   a. ./scripts/deploy.sh spectrum kevin@10.10.110.223

5. Migration (global -- stops ATT too):
   a. Check idempotency: ssh ... "sudo test -f /var/lib/wanctl/metrics.db.pre-v135-archive"
   b. If NOT migrated: ./scripts/migrate-storage.sh --ssh kevin@10.10.110.223
      (This stops wanctl@att.service internally)
   c. If already migrated: stop ATT manually for deploy

6. Deploy ATT:
   a. Stop ATT + steering (if not already stopped by migration)
   b. ./scripts/deploy.sh att kevin@10.10.110.223 --with-steering

7. Restart Spectrum FIRST (canary isolation):
   a. ssh ... "sudo systemctl start wanctl@spectrum.service"
   b. Wait 20s for health stabilization
   c. Manual Spectrum-only health check:
      ssh kevin@10.10.110.223 "curl -s http://10.10.110.223:9101/health | python3 -m json.tool"
   d. Verify: version=1.35.0, storage.status=ok, status=healthy
   e. HARD STOP: If Spectrum fails, do NOT start ATT. Investigate.

8. Restart ATT + Steering:
   a. ssh ... "sudo systemctl start wanctl@att.service"
   b. Wait 5s
   c. ssh ... "sudo systemctl start steering.service"
   d. Wait 20s for health stabilization

9. Full canary:
   a. ./scripts/canary-check.sh --ssh kevin@10.10.110.223 --expect-version 1.35.0
   b. Must exit 0

10. Post-canary verification:
    a. Verify per-WAN DB files exist
    b. Verify storage pressure not critical
```

### Canary Does Not Support Per-WAN Mode [VERIFIED: scripts/canary-check.sh lines 26-30]

The canary hardcodes both targets:
```bash
AUTORATE_TARGETS=(
    "spectrum|10.10.110.223|9101"
    "att|10.10.110.227|9101"
)
```

There is no flag to check only one WAN. The canary iterates all targets and accumulates ERRORS/WARNINGS globally. If ATT is down, the Spectrum check passes but ATT's check FAILS, making the overall exit 1.

**Implication:** For the intermediate Spectrum-only validation (step 7c), use a direct `curl` to the health endpoint instead of canary-check.sh. The full canary runs only after ALL services are up (step 9).

### Canary Exit Code Contract [VERIFIED: scripts/canary-check.sh lines 496-504]

| Exit Code | Meaning | Trigger Conditions |
|-----------|---------|-------------------|
| 0 (PASS) | All checks passed | ERRORS=0 AND WARNINGS=0 |
| 1 (FAIL) | Blocking failures | ERRORS > 0: endpoint unreachable, router unreachable, storage critical, runtime critical, download/upload state unknown, summary rows missing |
| 2 (WARN) | Warnings only | ERRORS=0 AND WARNINGS > 0: version mismatch, storage warning, runtime warning, uptime < 10s, download/upload SOFT_RED/RED |

**Critical for DEPL-01:** The requirement says "canary-check.sh returns exit 0." Exit 2 (WARN) does NOT satisfy it.

Conditions that produce WARN (exit 2) and would fail DEPL-01:
- `--expect-version 1.35.0` but health reports different version -> WARN
- Service uptime < 10s -> WARN
- `storage_status == "warning"` (pending_writes >= 5 OR WAL >= 128 MB) -> WARN
- `runtime_status == "warning"` -> WARN
- download/upload state is SOFT_RED or RED at check time -> WARN

### Storage Status Classification [VERIFIED: src/wanctl/runtime_pressure.py lines 89-110]

| Status | Condition |
|--------|-----------|
| ok | pending_writes < 5 AND wal_bytes < 128 MB |
| warning | pending_writes >= 5 OR wal_bytes >= 128 MB |
| critical | lock_failures > 0 OR checkpoint_busy > 0 OR pending_writes >= 20 OR wal_bytes >= 256 MB |

**Fresh per-WAN DBs start with 0 pending writes and 0 WAL bytes = `ok`.** No risk of transient `warning` on fresh start.

### Version Propagation Chain [VERIFIED: grep of import chain]

```
__init__.py (__version__ = "1.35.0")
  -> health_check.py line 25: from wanctl import __version__
  -> health_check.py line 200: "version": __version__
  -> /health JSON response: .version field
  -> canary-check.sh: --expect-version compares against this
```

All consumers read from the same `__init__.py` source. No intermediate caching or build step.

### Version Bump Targets [VERIFIED: current codebase]

| File | Field | Current | Target |
|------|-------|---------|--------|
| `src/wanctl/__init__.py` | `__version__` | `"1.32.2"` | `"1.35.0"` |
| `pyproject.toml` line 3 | `version` | `"1.32.2"` | `"1.35.0"` |
| `CLAUDE.md` | `**Version:**` | `1.32.2` | `1.35.0` |

### Service Dependency Ordering [VERIFIED: systemd unit files]

**wanctl@.service:**
- After: `network-online.target`, `systemd-networkd-wait-online.service`, `wanctl-nic-tuning.service`
- Wants: `network-online.target`, `wanctl-nic-tuning.service`
- NO dependency on other wanctl@ instances

**steering.service:**
- After: `network-online.target`
- Wants: `network-online.target`
- **NO explicit dependency on wanctl@ services** -- steering does not have a systemd-level dependency on autorate

**Implication:** Steering can start before autorate. However, steering reads WAN state files written by autorate services. Starting steering before autorate means steering may have stale/missing state. The safe order is: autorate services first, wait for health, then steering.

### deploy.sh Behavior [VERIFIED: scripts/deploy.sh]

Key facts:
- Deploys code via `rsync -av --delete` -- complete replacement of /opt/wanctl/
- Also deploys: config, profiling scripts, analysis scripts, docs, NIC tuning, sysctl, bridge QoS, systemd units
- Does NOT stop or restart services (operator responsibility per D-03)
- Running deploy.sh twice for two WANs: the CODE is shared (same /opt/wanctl/ tree), but CONFIG is per-WAN. Second deploy overwrites the code again (no-op since same commit).
- Has `--dry-run` mode
- Has `--with-steering` flag that deploys steering.service + steering.yaml
- Runs internal verification (file counts, core script, config, secrets, systemd)
- **Both deploy.sh calls deploy the SAME code tree.** The per-WAN difference is only in which config file is deployed.

### Rollback Strategy [VERIFIED: deploy.sh has no rollback mechanism]

`deploy.sh` has NO rollback command, no backup of previous code, no snapshot mechanism. Rollback options:

1. **Re-deploy from prior git state:**
   ```bash
   git checkout v1.32.2  # or appropriate tag/commit
   ./scripts/deploy.sh spectrum kevin@10.10.110.223
   ./scripts/deploy.sh att kevin@10.10.110.223 --with-steering
   ```

2. **The rsync `--delete` flag means** the deploy is a complete code replacement. There's no delta to undo -- you just deploy the old version.

3. **Config rollback:** Configs are also deployed by deploy.sh. If the repo configs are wrong, you must fix the repo first or manually restore production configs.

4. **Migration rollback:** If migrate-storage.sh has archived the legacy DB, it can be restored:
   ```bash
   ssh kevin@10.10.110.223 "sudo mv /var/lib/wanctl/metrics.db.pre-v135-archive /var/lib/wanctl/metrics.db"
   ```
   But the per-WAN configs would still point to per-WAN DB paths. Rollback of migration requires also reverting configs.

**Practical rollback posture:** Since production is currently on v1.32.2 with manually-patched v1.34 modules, a true rollback is messy. The safest approach is to fix forward -- if canary fails, investigate and fix the issue rather than trying to restore the mixed-version state.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Code deployment | Manual scp/rsync | `deploy.sh` | Handles 10+ deployment targets atomically, with verification |
| Health validation | Manual curl + parsing | `canary-check.sh` (for full check) | Comprehensive checks with proper exit codes |
| DB migration | Manual sqlite3 | `migrate-storage.sh` | Handles purge, VACUUM, archive, WAL/SHM, idempotency, service stop |
| Per-WAN health spot-check | New script | Direct `curl` to health endpoint | canary-check.sh cannot do per-WAN; curl is simpler than modifying the script |

## Common Pitfalls

### Pitfall 1: Canary Exit 2 Treated as Success
**What goes wrong:** Canary reports WARN (exit 2) due to version mismatch, low uptime, or storage warning. Operator assumes "no failures = success."
**Why it happens:** Exit 2 is not exit 1, so it doesn't feel like a failure.
**How to avoid:** DEPL-01 explicitly requires exit 0. Check `$?` equals 0. Any WARN line means exit 2.
**Warning signs:** Any `[WARN]` lines in canary output.

### Pitfall 2: Stopping All Services Up Front (Codex HIGH Concern)
**What goes wrong:** Both WANs go down simultaneously, creating a coordinated outage rather than a rolling deploy.
**Why it happens:** Natural instinct to "stop everything, deploy, restart." Also, migrate-storage.sh stops both services internally.
**How to avoid:** Stop Spectrum first, deploy, then trigger migration (which stops ATT). Deploy ATT. Restart Spectrum, validate, then restart ATT. The outage window per WAN is minimized.
**Warning signs:** Both services down for more than a few minutes.

### Pitfall 3: Running Canary Before Both Services Are Up
**What goes wrong:** canary-check.sh checks both Spectrum and ATT. If ATT is still down, the canary FAILs (exit 1) even though Spectrum is healthy.
**Why it happens:** No per-WAN canary mode exists.
**How to avoid:** Run the full canary only after ALL services (Spectrum, ATT, steering) are started and stabilized. Use direct `curl` for intermediate per-WAN checks.
**Warning signs:** Canary shows FAIL for one WAN, PASS for another.

### Pitfall 4: Running Canary Too Soon After Service Start
**What goes wrong:** Service uptime < 10s triggers WARN (exit 2), failing DEPL-01.
**Why it happens:** canary-check.sh line 236-239 checks `uptime_seconds >= 10`.
**How to avoid:** Wait at least 20s after last service start before running canary. The 20s provides margin above the 10s threshold.
**Warning signs:** `[WARN] autorate {target}: uptime {N}s is below 10s`

### Pitfall 5: Config Drift Overwritten by deploy.sh
**What goes wrong:** deploy.sh overwrites production config with repo config. If production was manually tuned, those changes are lost.
**Why it happens:** `deploy_config()` in deploy.sh copies the repo's config to production.
**How to avoid:** Always diff production config against repo before deploying (per feedback_diff_config_before_deploy.md).
**Warning signs:** Unexpected config values or behavioral changes after deploy.

### Pitfall 6: Migration Already Happened in Phase 172
**What goes wrong:** Running migrate-storage.sh when it's already been run wastes time but doesn't break anything.
**Why it happens:** Phase 172 verification says "human_needed" -- the operator may have already run migration.
**How to avoid:** Check for archive file before running: `ssh ... "sudo test -f /var/lib/wanctl/metrics.db.pre-v135-archive"`. The script itself is idempotent (exits cleanly if archive exists).
**Warning signs:** `[WARN] Archive already exists, migration already completed`

### Pitfall 7: Uncommitted Phase 172 Changes in migrate-storage.sh
**What goes wrong:** The local migrate-storage.sh has uncommitted changes from Phase 172 (table_exists function, sudo test fixes). If not committed, the deploy won't include these fixes.
**Why it happens:** Phase 172 execution modified the script but version bump commit hasn't been made yet.
**How to avoid:** Ensure all Phase 172 changes are committed before or as part of the version bump commit.
**Warning signs:** `git status` shows `M scripts/migrate-storage.sh`

### Pitfall 8: Download/Upload State WARN at Check Time
**What goes wrong:** If a WAN happens to be in SOFT_RED or RED state when canary runs (legitimate congestion), canary exits 2 (WARN).
**Why it happens:** Canary checks current congestion state. Network conditions are unpredictable.
**How to avoid:** This is transient. If canary exits 2 due to congestion state only, wait for congestion to clear and re-run. Check the canary output to distinguish congestion WARN from version/storage WARN.
**Warning signs:** `[WARN] autorate {target}/{wan}: download state elevated` or `upload state elevated`

## Code Examples

### Version Bump (3 files)
```python
# src/wanctl/__init__.py
# Source: verified current is "1.32.2"
__version__ = "1.35.0"
```

```toml
# pyproject.toml line 3
# Source: verified current is "1.32.2"
version = "1.35.0"
```

```markdown
# CLAUDE.md
# Source: verified current is 1.32.2
**Version:** 1.35.0
```

### Config Diff Before Deploy
```bash
# Source: feedback_diff_config_before_deploy.md pattern
ssh kevin@10.10.110.223 "sudo cat /etc/wanctl/spectrum.yaml" | diff - configs/spectrum.yaml
ssh kevin@10.10.110.223 "sudo cat /etc/wanctl/att.yaml" | diff - configs/att.yaml
ssh kevin@10.10.110.223 "sudo cat /etc/wanctl/steering.yaml" | diff - configs/steering.yaml 2>/dev/null || true
```

### Migration Idempotency Check
```bash
# Source: migrate-storage.sh lines 98-102
ssh kevin@10.10.110.223 "sudo test -f /var/lib/wanctl/metrics.db.pre-v135-archive && echo 'ALREADY_MIGRATED' || echo 'NEEDS_MIGRATION'"
```

### Per-WAN Health Spot Check (for intermediate validation)
```bash
# Source: health_check.py /health endpoint, used in lieu of canary for single-WAN check
ssh kevin@10.10.110.223 "curl -s http://10.10.110.223:9101/health" | python3 -c "
import json, sys
h = json.load(sys.stdin)
print(f'version:  {h.get(\"version\", \"unknown\")}')
print(f'status:   {h.get(\"status\", \"unknown\")}')
print(f'uptime:   {h.get(\"uptime_seconds\", 0)}s')
print(f'storage:  {h.get(\"storage\", {}).get(\"status\", \"unknown\")}')
ok = h.get('version') == '1.35.0' and h.get('status') == 'healthy' and h.get('uptime_seconds', 0) >= 10
print(f'VERDICT:  {\"PASS\" if ok else \"INVESTIGATE\"}')"
```

### Service Lifecycle
```bash
# Stop Spectrum (before deploy)
ssh kevin@10.10.110.223 "sudo systemctl stop wanctl@spectrum.service"

# Stop ATT + Steering (before deploy -- may be redundant if migration already stopped them)
ssh kevin@10.10.110.223 "sudo systemctl stop wanctl@att.service steering.service"

# Restart Spectrum FIRST (canary isolation)
ssh kevin@10.10.110.223 "sudo systemctl start wanctl@spectrum.service"

# Restart ATT + Steering (after Spectrum validated)
ssh kevin@10.10.110.223 "sudo systemctl start wanctl@att.service"
ssh kevin@10.10.110.223 "sudo systemctl start steering.service"
```

### Observable Readiness Gates (vs Fixed Sleeps)
```bash
# Wait for service to be active (replaces fixed sleep)
ssh kevin@10.10.110.223 "while ! systemctl is-active --quiet wanctl@spectrum.service; do sleep 1; done"

# Wait for health endpoint to respond (replaces fixed 20s wait)
ssh kevin@10.10.110.223 "
timeout 30 bash -c '
while true; do
  code=\$(curl -s -o /dev/null -w \"%{http_code}\" --connect-timeout 2 --max-time 3 http://10.10.110.223:9101/health 2>/dev/null)
  if [[ \"\$code\" == \"200\" || \"\$code\" == \"503\" ]]; then break; fi
  sleep 2
done'"
```

### Full Canary
```bash
# Source: CONTEXT D-07
./scripts/canary-check.sh --ssh kevin@10.10.110.223 --expect-version 1.35.0
echo "Canary exit code: $?"  # Must be exactly 0
```

### Post-Canary DB Verification
```bash
# Source: CONTEXT D-08
ssh kevin@10.10.110.223 "sudo ls -lh /var/lib/wanctl/metrics-spectrum.db /var/lib/wanctl/metrics-att.db"
```

### Rollback (if needed)
```bash
# Emergency rollback: re-deploy from known-good commit
# Note: this is the ONLY rollback path -- deploy.sh has no undo
git stash  # or git checkout <known-good-commit>
./scripts/deploy.sh spectrum kevin@10.10.110.223
./scripts/deploy.sh att kevin@10.10.110.223 --with-steering
ssh kevin@10.10.110.223 "sudo systemctl restart wanctl@spectrum.service wanctl@att.service steering.service"
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
- **Per wave merge:** N/A (deployment phase)
- **Phase gate:** Canary exit 0 on live production

### Wave 0 Gaps
None -- this phase uses existing test infrastructure and live operational validation. No new test files needed.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Steering should start after autorate services for clean health state | Architecture Patterns | LOW -- steering has no systemd dependency on autorate but may produce degraded health without WAN state files [ASSUMED] |
| A2 | Fresh per-WAN DBs will immediately report storage.status=ok | Storage Status Classification | LOW -- verified from classify_storage_status logic: 0 pending writes + 0 WAL = ok [VERIFIED: runtime_pressure.py] |
| A3 | Download/upload congestion state at canary time is non-deterministic | Pitfall 8 | MEDIUM -- if congestion is persistent at deploy time, canary may never exit 0. Plan should note this possibility [ASSUMED] |

## Open Questions

1. **Has migrate-storage.sh already been run during Phase 172?**
   - What we know: Phase 172 verification status is "human_needed" with instruction to run the migration. Kevin may or may not have done this.
   - What's unclear: Whether the archive file exists on production.
   - Recommendation: Plan includes idempotency check (D-06). If archive exists, skip migration. The script handles this gracefully.

2. **Are all Phase 172 code changes committed?**
   - What we know: `git status` shows `M scripts/migrate-storage.sh` and other Phase 172 artifacts. These changes must be committed before deploy.
   - What's unclear: Whether there are other uncommitted Phase 172 code changes.
   - Recommendation: The version bump commit should include all uncommitted Phase 172 changes. Check `git status` carefully.

3. **What if congestion state causes persistent exit 2 during canary?**
   - What we know: SOFT_RED/RED download or upload state produces WARN. Network conditions are unpredictable.
   - What's unclear: How often this would happen and how long it would persist.
   - Recommendation: If canary exits 2 solely due to congestion state (not version/storage/runtime), wait a few minutes and re-run. Document this as an expected possibility.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| SSH to 10.10.110.223 | All deploy/canary operations | Assumed available (used in prior phases) | N/A | None -- blocking |
| rsync (local) | deploy.sh | Likely available | N/A | deploy.sh checks and errors |
| rsync (remote) | deploy.sh | Likely available | N/A | deploy.sh checks and errors |
| sqlite3 (remote) | migrate-storage.sh | Likely available | N/A | Migration fails -- blocking |
| systemctl (remote) | Service management | Available | N/A | N/A |
| python3 (remote) | canary-check.sh jq fallback | Available | 3.11+ | N/A |
| curl (remote) | Health endpoint checks | Available | N/A | N/A |
| jq (remote) | canary-check.sh (optional) | May not be present | N/A | Falls back to python3 (built-in) |

**Missing dependencies with no fallback:** None expected.

## Sources

### Primary (HIGH confidence)
- `scripts/deploy.sh` -- 643 lines, read in entirety. No rollback mechanism, rsync --delete, no service restart. [VERIFIED]
- `scripts/canary-check.sh` -- 505 lines, read in entirety. Hardcoded dual-WAN targets, exit 0/1/2 contract, no per-WAN mode. [VERIFIED]
- `scripts/migrate-storage.sh` -- 243 lines, read in entirety. Stops BOTH services (line 114), idempotent archive check, dry-run support. [VERIFIED]
- `deploy/systemd/wanctl@.service` -- No cross-WAN dependency. After: network, NIC tuning. [VERIFIED]
- `deploy/systemd/steering.service` -- No dependency on wanctl@ instances. After: network only. [VERIFIED]
- `src/wanctl/runtime_pressure.py` -- classify_storage_status: ok/warning/critical thresholds. WAL_WARNING=128MB. [VERIFIED]
- `src/wanctl/health_check.py` -- Version from `__init__.py`, storage from first WAN, summary rows structure. [VERIFIED]
- `src/wanctl/__init__.py` -- Current version "1.32.2". [VERIFIED]
- `pyproject.toml` -- Current version "1.32.2". [VERIFIED]
- `configs/spectrum.yaml` -- Per-WAN db_path already configured (Phase 172 change). [VERIFIED]
- `configs/att.yaml` -- Per-WAN db_path already configured (Phase 172 change). [VERIFIED]
- `.planning/phases/172-storage-health-code-fixes/172-VERIFICATION.md` -- Phase 172: 14/14 must-haves verified, status human_needed for live migration. [VERIFIED]
- `.planning/phases/173-clean-deploy-canary-validation/173-REVIEWS.md` -- Codex review: HIGH concerns on stop-all-services, no rollback, migration blast radius. [VERIFIED]

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- all scripts read in full, behavior confirmed from source
- Architecture: HIGH -- deploy sequence re-analyzed against Codex review concerns, migration service-stop behavior verified
- Pitfalls: HIGH -- derived from reading actual script logic, project feedback memories, and Codex review findings
- Canary semantics: HIGH -- exit code logic verified line-by-line from bash source
- Rollback: HIGH -- confirmed deploy.sh has no rollback; only option is re-deploy from git

**Research date:** 2026-04-12
**Valid until:** 2026-05-12 (stable -- scripts and deploy process are mature)
