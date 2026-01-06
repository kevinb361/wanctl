# SSH Security Setup - Host Key Validation

## What Changed

SSH host key validation has been **enabled** across all wanctl code. The insecure `StrictHostKeyChecking=no` flag has been removed from:

### Production Code (Critical)
- ✅ `src/cake/autorate_continuous_v2.py` - Main bandwidth controller
- ✅ `src/cake/wan_steering_daemon.py` - WAN steering daemon
- ✅ `src/cake/cake_stats.py` - CAKE statistics collector
- ✅ `src/cake/autorate_continuous.py` - Alternative controller
- ✅ `src/cake/adaptive_cake.py` - CAKE management

### Utility Scripts
- ✅ `fetch_logs.py` - Log fetching tool
- ✅ `fetch_logs_pexpect.py` - Alternative log fetcher
- ✅ `scripts/deploy.sh` - Deployment script

## Why This Matters

**Before (Insecure):**
- SSH connections accepted ANY host key
- Vulnerable to Man-in-the-Middle (MITM) attacks
- Attacker could intercept and modify RouterOS commands
- Could manipulate CAKE queues, routing rules, firewall settings

**After (Secure):**
- SSH verifies router's identity using known_hosts
- MITM attacks blocked (connection refused if key doesn't match)
- Router identity validated on every connection

## Required Setup (One-Time)

You must add the router's SSH host key to `~/.ssh/known_hosts` on **both containers**:

### Step 1: On cake-att Container (10.10.110.247)

```bash
ssh kevin@10.10.110.247

# Add router's SSH host keys
ssh-keyscan -H 10.10.99.1 >> ~/.ssh/known_hosts

# Verify it was added
grep 10.10.99.1 ~/.ssh/known_hosts
```

### Step 2: On cake-spectrum Container (10.10.110.246)

```bash
ssh kevin@10.10.110.248

# Add router's SSH host keys
ssh-keyscan -H 10.10.99.1 >> ~/.ssh/known_hosts

# Verify it was added
grep 10.10.99.1 ~/.ssh/known_hosts
```

### Step 3: On Your Build Machine (Optional)

If you run scripts from your build machine (10.10.99.x):

```bash
# Add router's SSH host keys
ssh-keyscan -H 10.10.99.1 >> ~/.ssh/known_hosts

# Verify
grep 10.10.99.1 ~/.ssh/known_hosts
```

## Testing

After adding the host keys, test SSH connectivity:

### From cake-att:
```bash
ssh kevin@10.10.110.247
ssh -i ~/.ssh/mikrotik_cake admin@10.10.99.1 '/system resource print'
```

Should connect WITHOUT prompting to accept host key.

### From cake-spectrum:
```bash
ssh kevin@10.10.110.246
ssh -i ~/.ssh/mikrotik_cake admin@10.10.99.1 '/system resource print'
```

Should connect WITHOUT prompting.

## Troubleshooting

### Error: "Host key verification failed"

**Cause:** Router's host key not in known_hosts

**Fix:**
```bash
ssh-keyscan -H 10.10.99.1 >> ~/.ssh/known_hosts
```

### Error: "Permission denied (publickey)"

**Cause:** SSH key file permissions or authentication issue (unrelated to this change)

**Fix:**
```bash
chmod 600 ~/.ssh/mikrotik_cake
ls -la ~/.ssh/mikrotik_cake  # Should show -rw-------
```

### Warning: "REMOTE HOST IDENTIFICATION HAS CHANGED"

**Cause:** Router was replaced, reinstalled, or host key regenerated

**Impact:** SSH will REFUSE to connect (this is intentional security!)

**Fix (only if you know why the key changed):**
```bash
# Remove old key
ssh-keygen -R 10.10.99.1

# Add new key
ssh-keyscan -H 10.10.99.1 >> ~/.ssh/known_hosts
```

**⚠️ WARNING:** Only do this if you know WHY the host key changed (e.g., you reinstalled RouterOS). If it changed unexpectedly, you may be under MITM attack!

## What Happens If You Don't Do This

If you deploy the updated code WITHOUT adding host keys to known_hosts:

**Symptom:**
- CAKE controllers will fail to connect to router
- Logs will show: `Host key verification failed`
- CAKE limits will NOT be updated
- System falls back to last known good state (queues unchanged)

**Impact:**
- Bandwidth shaping stops adapting
- WAN steering stops working
- Bufferbloat returns (no CAKE adjustments)

**Resolution:**
- Add host keys to known_hosts (see Step 1 & 2 above)
- Restart systemd timers: `systemctl restart cake-att.timer cake-spectrum.timer`

## Deployment Checklist

Before deploying security-fixed code:

- [ ] Added router host key to cake-att container's known_hosts
- [ ] Added router host key to cake-spectrum container's known_hosts
- [ ] Tested SSH connectivity from both containers
- [ ] Verified autorate can execute RouterOS commands
- [ ] Checked systemd logs for "Host key verification failed" errors

## Security Notes

### Good Practice
- Host keys should be added via `ssh-keyscan` (automated, scriptable)
- Alternative: SSH manually once and accept key (interactive)

### What NOT To Do
- ❌ Don't add `-o StrictHostKeyChecking=no` back to the code
- ❌ Don't disable host key checking globally in ~/.ssh/config
- ❌ Don't copy known_hosts from untrusted sources

### Verifying Host Key Fingerprint (Paranoid Mode)

If you want to verify the host key is legitimate:

1. **On the router (MikroTik):**
   ```routeros
   /ip ssh print
   ```
   Shows SSH host key fingerprint

2. **Compare with what you added:**
   ```bash
   ssh-keygen -l -f <(ssh-keyscan 10.10.99.1 2>/dev/null)
   ```
   Fingerprints should match!

## Related Security Fixes

This is part of a larger security hardening effort:

1. ✅ **Removed hardcoded passwords** - Now uses environment variables
2. ✅ **Enabled SSH host key validation** - This document
3. 🔜 **Input validation** - Queue names and mangle rule comments
4. 🔜 **Fixed bare except clauses** - Proper error handling

See `docs/SECURITY_FIXES.md` for complete list.

---

**Created:** 2026-01-06
**Impact:** Critical - Required for system operation after update
**Priority:** Must complete BEFORE deploying security-fixed code
