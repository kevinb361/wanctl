# Steering Daemon Configuration Mismatch Issue

**Status:** RESOLVED (temporary fix applied 2026-01-11)
**Severity:** Medium (steering non-functional for 3+ days, but no impact on bufferbloat control)
**Discovered:** 2026-01-11 during debug log review
**Root Cause:** Deployment script filename mismatch + generic template deployed

---

## Executive Summary

The steering daemon has been failing continuously since 2026-01-08 due to configuration mismatches between the deployed config and actual system state. The wrong configuration template was deployed because of a filename mismatch in the deployment workflow.

**Impact:** Zero impact on network performance (autorate continued working perfectly), but steering features were non-functional for 3+ days.

---

## Root Cause Analysis

### The Problem

The deployment script (`scripts/deploy.sh:354-361`) looks for configs in this order:

1. **First choice:** `configs/steering.yaml` (DOES NOT EXIST ❌)
2. **Fallback:** `configs/examples/steering.yaml.example` (generic template ⚠️)

But the actual production config exists as:
- `configs/steering_config.yaml` ✅ (correct values for this deployment)

**Result:** The generic example template was deployed with placeholder values.

### Configuration Mismatches

| Setting | Generic Template (Deployed) | Correct Value (Not Deployed) | Impact |
|---------|---------------------------|----------------------------|--------|
| `cake_state_sources.primary` | `/run/wanctl/wan1_state.json` | `/run/wanctl/spectrum_state.json` | File not found, baseline RTT unavailable |
| `cake_queues.primary_download` | `WAN-Download-1` | `WAN-Download-Spectrum` | CAKE stats failed to read |
| `cake_queues.primary_upload` | `WAN-Upload-1` | `WAN-Upload-Spectrum` | CAKE stats failed to read |
| `router.host` | `192.168.1.1` | `10.10.99.1` | Connection timeouts |
| `topology.primary_wan` | `wan1` | `spectrum` | Mismatch with actual WAN names |
| `topology.alternate_wan` | `wan2` | `att` | Mismatch with actual WAN names |

### Error Evidence

**Logs showed continuous failures every 2 seconds:**

```
2026-01-11 13:51:17,244 [steering] [WARNING] Primary WAN state file not found: /run/wanctl/wan1_state.json
2026-01-11 13:51:17,244 [steering] [WARNING] No baseline RTT available, cannot make steering decisions
2026-01-11 13:51:17,244 [steering] [ERROR] Cannot proceed without baseline RTT
2026-01-11 13:51:17,244 [steering] [ERROR] Cycle failed
```

**Actual state files that exist:**
```
/run/wanctl/spectrum_state.json  ✅ (Spectrum WAN, updated every 2s)
/run/wanctl/att_state.json       ✅ (ATT WAN, updated every 2s)
```

---

## Why This Happened

### Deployment Workflow

1. **Repository has:**
   - `configs/steering_config.yaml` (production config with correct values)
   - `configs/examples/steering.yaml.example` (generic template for documentation)

2. **Deploy script expects:**
   - `configs/steering.yaml` (doesn't exist)

3. **What got deployed:**
   - Generic template from `configs/examples/steering.yaml.example`
   - Warning printed: "Using example steering config - customize /etc/wanctl/steering.yaml"

4. **What should have happened:**
   - Production config `steering_config.yaml` should have been renamed or symlinked to `steering.yaml`
   - OR deploy script should look for `steering_config.yaml`

### Why It Went Unnoticed

- **Autorate continued working perfectly** - bufferbloat control unaffected
- **Steering failures logged but not monitored** - no alerts set up for steering daemon
- **No functional impact** - network remained stable on primary WAN (Spectrum)
- **Timer kept retrying silently** - systemd steering.timer attempted restart every 2s

---

## Temporary Fix Applied (2026-01-11)

**Manual correction deployed to cake-spectrum:/etc/wanctl/steering.yaml:**

```yaml
# Fixed values:
cake_state_sources:
  primary: "/run/wanctl/spectrum_state.json"  # Was: wan1_state.json

cake_queues:
  primary_download: "WAN-Download-Spectrum"   # Was: WAN-Download-1
  primary_upload: "WAN-Upload-Spectrum"       # Was: WAN-Upload-1

router:
  host: "10.10.99.1"                          # Was: 192.168.1.1
```

**Verification:**
```bash
# After fix:
✅ Baseline RTT reading: 23.31ms (from spectrum_state.json)
✅ Steering decisions: WAN1_GOOD, congestion=GREEN
✅ No errors in logs since 13:59 UTC
✅ State file updating every cycle
```

---

## Permanent Fix Options

### Option 1: Rename Production Config (RECOMMENDED)

**Action:** Rename `configs/steering_config.yaml` → `configs/steering.yaml`

**Pros:**
- Minimal code changes
- Deploy script works as-is
- Clear naming (no `_config` suffix needed)

**Cons:**
- Need to update any documentation referencing old filename
- Git history shows as file deletion + addition (not a rename)

**Implementation:**
```bash
cd ~/projects/wanctl
git mv configs/steering_config.yaml configs/steering.yaml
git commit -m "fix: Rename steering config to match deploy script expectations"
```

### Option 2: Update Deploy Script

**Action:** Modify `scripts/deploy.sh:354-361` to look for `steering_config.yaml` first

**Pros:**
- Maintains consistent naming pattern (`spectrum.yaml`, `att.yaml`, `steering_config.yaml`)
- No config file changes needed

**Cons:**
- Deploy script becomes less intuitive (non-standard naming)
- Doesn't fix the underlying inconsistency

**Implementation:**
```bash
# In scripts/deploy.sh line 354:
if [[ -f "$PROJECT_ROOT/configs/steering_config.yaml" ]]; then
    scp "$PROJECT_ROOT/configs/steering_config.yaml" "$TARGET_HOST:/tmp/steering.yaml"
    # ... rest of deployment
```

### Option 3: Symlink Approach

**Action:** Create symlink `steering.yaml` → `steering_config.yaml`

**Pros:**
- Both names work
- No code changes needed

**Cons:**
- Adds complexity
- Symlinks in git can be problematic
- Doesn't solve the naming inconsistency

### Option 4: Template + Variable Substitution (FUTURE)

**Action:** Deploy uses template with variable substitution for deployment-specific values

**Pros:**
- Single source of truth for config schema
- Deployment-specific values in separate file (like `.env`)
- Prevents future config drift

**Cons:**
- Significant refactoring needed
- Overkill for current 2-container deployment
- Better suited for multi-site deployments

**Future Enhancement Idea:**
```yaml
# configs/steering.yaml.template
cake_state_sources:
  primary: "/run/wanctl/${PRIMARY_WAN}_state.json"

cake_queues:
  primary_download: "${PRIMARY_WAN_DOWNLOAD_QUEUE}"

# deployment.env (per-site)
PRIMARY_WAN=spectrum
PRIMARY_WAN_DOWNLOAD_QUEUE=WAN-Download-Spectrum
ROUTER_IP=10.10.99.1
```

---

## Recommended Solution

**Option 1: Rename to `steering.yaml`**

This is the simplest, cleanest fix that aligns with the deploy script's expectations and eliminates future confusion.

**Rationale:**
1. Other configs use simple names: `spectrum.yaml`, `att.yaml` (not `spectrum_config.yaml`)
2. The `_config` suffix is redundant (all files in `configs/` are configs)
3. Deploy script already expects `steering.yaml`
4. Minimal changes needed

**Implementation Steps:**
```bash
# 1. Rename in repo
git mv configs/steering_config.yaml configs/steering.yaml
git commit -m "fix: Rename steering config to match deploy expectations"

# 2. Update any references in docs
grep -r "steering_config.yaml" docs/ README.md .claude/

# 3. Next deployment will automatically use correct config
./scripts/deploy.sh spectrum cake-spectrum --with-steering
```

---

## Prevention for Future

### Deployment Checklist

Add to deployment documentation:

1. **Verify config exists before deploying:**
   ```bash
   ls -l configs/steering.yaml  # Must exist for --with-steering
   ```

2. **Check deployed config after deployment:**
   ```bash
   ssh target-host 'diff /etc/wanctl/steering.yaml - < configs/steering.yaml'
   ```

3. **Verify steering daemon starts successfully:**
   ```bash
   ssh target-host 'sudo journalctl -u steering.service -n 20'
   # Should see: "Initialized baseline RTT: XX.XXms"
   # Should NOT see: "Primary WAN state file not found"
   ```

### Monitoring Recommendations

1. **Add health check alert for steering daemon:**
   - Monitor `/health` endpoint on port 9101
   - Alert if steering unavailable for > 5 minutes

2. **Log aggregation:**
   - Parse steering logs for "ERROR" patterns
   - Alert on repeated "Cannot proceed without baseline RTT"

3. **State file validation:**
   - Verify all referenced state files exist in `/run/wanctl/`
   - Check that state files are being updated (mtime within last 10s)

---

## Lessons Learned

1. **Configuration validation needed:**
   - Deploy script should validate config BEFORE deployment
   - Check that referenced files/queues/IPs are reachable

2. **Example templates are dangerous:**
   - Should not be used as fallback without explicit confirmation
   - Deploy should FAIL if production config missing (fail-fast)

3. **Naming consistency matters:**
   - `steering_config.yaml` vs `steering.yaml` caused confusion
   - Stick to one naming convention: `<wan_name>.yaml`

4. **Silent failures accumulate:**
   - Steering failed for 3+ days without detection
   - Need proactive monitoring, not just reactive debugging

5. **Template warnings get ignored:**
   - Deploy script printed: "Using example steering config - customize..."
   - This warning was never acted upon
   - Critical warnings should block deployment, not just inform

---

## Related Files

**Configuration:**
- ✅ `configs/steering_config.yaml` (correct production config)
- ❌ `configs/steering.yaml` (missing - should exist)
- ⚠️ `configs/examples/steering.yaml.example` (generic template - deployed by mistake)

**Deployment:**
- `scripts/deploy.sh` (deployment automation)
- `scripts/install-systemd.sh` (systemd setup)

**Runtime:**
- `/etc/wanctl/steering.yaml` (deployed config - currently fixed manually)
- `/run/wanctl/spectrum_state.json` (autorate state - correct source)
- `/var/log/wanctl/steering.log` (steering daemon logs)

**Documentation:**
- `docs/DEPLOYMENT.md` (should document steering setup)
- `docs/STEERING.md` (steering feature documentation)
- `README.md` (quick start)

---

## Action Items

- [x] **Immediate:** Manual fix applied to production (2026-01-11) ✅
- [ ] **Week 1:** Rename `steering_config.yaml` → `steering.yaml` in repo
- [ ] **Week 1:** Update deployment documentation with verification steps
- [ ] **Week 2:** Add config validation to `scripts/deploy.sh`
- [ ] **Week 2:** Add steering health check monitoring
- [ ] **Future:** Consider template + variable substitution for multi-site deployments

---

## References

- Issue discovered during: Debug log analysis (2026-01-11)
- Related docs: `docs/DEPLOYMENT.md`, `docs/STEERING.md`
- Deploy script: `scripts/deploy.sh:354-361`
- Steering daemon code: `src/wanctl/steering/daemon.py`

---

**Document created:** 2026-01-11
**Last updated:** 2026-01-11
**Status:** Issue documented, temporary fix applied, permanent fix pending
