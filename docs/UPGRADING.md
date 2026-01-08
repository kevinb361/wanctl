# Upgrading wanctl

This document covers upgrade procedures and compatibility between versions.

## General Upgrade Procedure

1. **Stop the service**
   ```bash
   sudo systemctl stop wanctl@wan1.service
   # If using steering:
   sudo systemctl stop steering.service
   ```

2. **Backup current state** (optional but recommended)
   ```bash
   sudo cp /var/lib/wanctl/wan1_state.json /var/lib/wanctl/wan1_state.json.backup
   ```

3. **Deploy new code**
   ```bash
   # From your dev machine:
   ./scripts/deploy.sh wan1 target-host
   ```

4. **Review config changes** (if upgrading across major versions)
   - Check release notes for new required fields
   - Update your config file if needed

5. **Restart the service**
   ```bash
   sudo systemctl start wanctl@wan1.service
   ```

6. **Verify operation**
   ```bash
   sudo journalctl -u wanctl@wan1.service -f
   ```

## State File Compatibility

### State File Location
- `/var/lib/wanctl/<wan_name>_state.json`

### State File Format (v1.0.0)

```json
{
  "download": {
    "green_streak": 0,
    "soft_red_streak": 0,
    "red_streak": 0,
    "current_rate": 500000000
  },
  "upload": {
    "green_streak": 0,
    "soft_red_streak": 0,
    "red_streak": 0,
    "current_rate": 50000000
  },
  "ewma": {
    "baseline_rtt": 25.0,
    "load_rtt": 26.5
  },
  "timestamp": "2025-01-08T12:00:00.000000"
}
```

### Compatibility Notes

- **Missing fields**: The code uses `.get()` with defaults for all state fields. Missing fields are initialized to safe defaults (streaks to 0, rates to ceiling).

- **Extra fields**: Unknown fields are ignored. You can safely upgrade without losing data.

- **State reset**: If you want to start fresh, simply delete the state file:
  ```bash
  sudo rm /var/lib/wanctl/wan1_state.json
  sudo systemctl restart wanctl@wan1.service
  ```

- **No version field**: The state file format is designed to be forward-compatible. New fields are added with defaults, old fields are preserved.

## Version-Specific Notes

### Upgrading to v1.0.0 from rc3/rc4

**Config changes:**
- REST API transport is now recommended over SSH
- Add `transport: "rest"` to your router config (optional, SSH still works)

**New optional config fields:**
- `thresholds.baseline_update_threshold_ms` - Controls when baseline RTT updates (default: 3.0ms)

**SSH transport users:**
- Host key validation is now enforced
- Add router's host key before upgrading:
  ```bash
  sudo -u wanctl ssh-keyscan -H <router_ip> >> /var/lib/wanctl/.ssh/known_hosts
  ```

### Upgrading from v0.x (pre-release)

If upgrading from early development versions:

1. **Backup and remove old state files**
   ```bash
   sudo mv /var/lib/wanctl/*.json /var/lib/wanctl/backup/
   ```

2. **Update config to new schema**
   - See `configs/examples/wan1.yaml.example` for current schema
   - Key changes: `continuous_monitoring` section structure, state-based floors

3. **Fresh start recommended**
   - Delete old state files
   - Let the system re-converge (takes 5-10 minutes)

## Rollback Procedure

If an upgrade causes issues:

1. **Stop the service**
   ```bash
   sudo systemctl stop wanctl@wan1.service
   ```

2. **Restore old code**
   ```bash
   # If you have a backup:
   sudo cp -r /opt/wanctl.backup/* /opt/wanctl/
   ```

3. **Restore old state** (if backed up)
   ```bash
   sudo cp /var/lib/wanctl/wan1_state.json.backup /var/lib/wanctl/wan1_state.json
   ```

4. **Restart**
   ```bash
   sudo systemctl start wanctl@wan1.service
   ```

## Troubleshooting Upgrades

### Service fails to start after upgrade

**Check logs:**
```bash
sudo journalctl -u wanctl@wan1.service -n 50
```

**Common causes:**
- Config validation error (new required field)
- SSH host key missing (if using SSH transport)
- Python dependency missing

### State file errors

**Symptom:** "JSONDecodeError" in logs

**Fix:** Delete corrupted state file:
```bash
sudo rm /var/lib/wanctl/wan1_state.json
sudo systemctl restart wanctl@wan1.service
```

### Bandwidth oscillation after upgrade

**Cause:** New thresholds or floors not matching your link

**Fix:** Review and adjust your config thresholds, then restart:
```bash
sudo systemctl restart wanctl@wan1.service
```

## Best Practices

1. **Test on non-production first** if you have multiple WANs

2. **Upgrade during low-traffic periods** to minimize impact

3. **Keep state file backups** before major upgrades

4. **Monitor logs** after upgrade for unexpected behavior

5. **Review release notes** for breaking changes
