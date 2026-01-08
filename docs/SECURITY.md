# Security

## SSH Host Key Validation

wanctl validates SSH host keys on every connection. This prevents Man-in-the-Middle (MITM) attacks where an attacker could intercept and modify RouterOS commands.

**Implementation:** The SSH client uses `paramiko.RejectPolicy()` which refuses connections unless the router's host key is present in `known_hosts`.

**Why this matters:**

- Without validation, an attacker on your network could intercept SSH traffic
- They could modify CAKE bandwidth limits or mangle rules
- They could redirect your traffic or read router credentials

**REST API alternative:** If SSH key management is burdensome, consider using the REST API transport instead (password-based, over HTTPS).

## Required Setup (One-Time)

You must add the router's SSH host key to the `wanctl` service user's known_hosts file.

### For the wanctl Service User

The `wanctl` service runs as the `wanctl` user with home directory `/var/lib/wanctl`. Add the router's host key:

```bash
# On each controller host (as root)
sudo -u wanctl ssh-keyscan -H <router_ip> >> /var/lib/wanctl/.ssh/known_hosts

# Verify it was added
sudo -u wanctl cat /var/lib/wanctl/.ssh/known_hosts | grep <router_ip>
```

### Alternative: Use Your User Account for Testing

For manual testing or development:

```bash
# Add to your user's known_hosts
ssh-keyscan -H <router_ip> >> ~/.ssh/known_hosts
```

## Testing

After adding the host keys, test SSH connectivity:

### From Controller:

```bash
ssh user@<controller-host>
ssh -i ~/.ssh/<router_ssh_key> admin@<router_ip> '/system resource print'
```

Should connect WITHOUT prompting to accept host key.

## Troubleshooting

### Error: "Host key verification failed"

**Cause:** Router's host key not in known_hosts

**Fix:**

```bash
ssh-keyscan -H <router_ip> >> ~/.ssh/known_hosts
```

### Error: "Permission denied (publickey)"

**Cause:** SSH key file permissions or authentication issue (unrelated to this change)

**Fix:**

```bash
chmod 600 ~/.ssh/<router_ssh_key>
ls -la ~/.ssh/<router_ssh_key>  # Should show -rw-------
```

### Warning: "REMOTE HOST IDENTIFICATION HAS CHANGED"

**Cause:** Router was replaced, reinstalled, or host key regenerated

**Impact:** SSH will REFUSE to connect (this is intentional security!)

**Fix (only if you know why the key changed):**

```bash
# Remove old key
ssh-keygen -R <router_ip>

# Add new key
ssh-keyscan -H <router_ip> >> ~/.ssh/known_hosts
```

**WARNING:** Only do this if you know WHY the host key changed (e.g., you reinstalled RouterOS). If it changed unexpectedly, you may be under MITM attack!

## What Happens If You Don't Do This

If you deploy the updated code WITHOUT adding host keys to known_hosts:

**Symptom:**

- CAKE controllers will fail to connect to router
- Logs will show: `Host key verification failed`
- CAKE limits will NOT be updated
- System falls back to last known good state (queues unchanged)

**Impact:**

- Bandwidth shaping stops adapting
- WAN steering stops working (if configured)
- Bufferbloat returns (no CAKE adjustments)

**Resolution:**

- Add host keys to known_hosts (see Steps above)
- Restart systemd timers: `systemctl restart wanctl@wan1.timer`

## Deployment Checklist

Before deploying security-fixed code:

- [ ] Added router host key to each controller's known_hosts
- [ ] Tested SSH connectivity from each controller
- [ ] Verified autorate can execute RouterOS commands
- [ ] Checked systemd logs for "Host key verification failed" errors

## Security Notes

### Good Practice

- Host keys should be added via `ssh-keyscan` (automated, scriptable)
- Alternative: SSH manually once and accept key (interactive)

### What NOT To Do

- Don't add `-o StrictHostKeyChecking=no` back to the code
- Don't disable host key checking globally in ~/.ssh/config
- Don't copy known_hosts from untrusted sources

### Verifying Host Key Fingerprint (Paranoid Mode)

If you want to verify the host key is legitimate:

1. **On the router (MikroTik):**

   ```routeros
   /ip ssh print
   ```

   Shows SSH host key fingerprint

2. **Compare with what you added:**
   ```bash
   ssh-keygen -l -f <(ssh-keyscan <router_ip> 2>/dev/null)
   ```
   Fingerprints should match!

## Related Security Improvements

This is part of a larger security hardening effort:

1. **Removed hardcoded passwords** - Now uses environment variables/config files
2. **Enabled SSH host key validation** - This document
3. **Input validation** - Queue names and mangle rule comments validated
4. **Proper error handling** - Fixed bare except clauses

---

**Impact:** Critical - Required for system operation after update
**Priority:** Must complete BEFORE deploying security-fixed code
