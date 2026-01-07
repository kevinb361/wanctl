# Quick Start Guide

This guide walks you through setting up wanctl for the first time.

## Prerequisites Checklist

Before starting, ensure you have:

- [ ] **Mikrotik Router** running RouterOS 7.x
- [ ] **CAKE queues** already configured on the router (see [Setting Up CAKE](#setting-up-cake-on-routeros))
- [ ] **Linux host** (Ubuntu 22.04+, Debian 12+, or similar) with Python 3.12+
- [ ] **SSH key** for router access (password auth not supported)
- [ ] **Network access** from host to router

## Step 1: Verify Router Setup

First, ensure CAKE queues exist on your router:

```bash
# SSH to your router and check for CAKE queues
ssh admin@<router_ip> '/queue tree print where queue=cake'
```

You should see output like:

```
Flags: X - disabled, I - invalid
0    name="WAN-Download" parent=wan-interface queue=cake priority=8 limit-at=0
1    name="WAN-Upload" parent=wan-interface queue=cake priority=8 limit-at=0
```

If no queues exist, see [Setting Up CAKE](#setting-up-cake-on-routeros) below.

## Step 2: Prepare SSH Access

Generate or prepare an SSH key for router access:

```bash
# Generate a dedicated key (if needed)
ssh-keygen -t ed25519 -f ~/.ssh/router_key -N ""

# Copy public key to router (one-time)
ssh admin@<router_ip>
# In RouterOS:
/user ssh-keys import public-key-file=router_key.pub user=admin

# Test key-based access
ssh -i ~/.ssh/router_key admin@<router_ip> '/system resource print'
```

## Step 3: Install wanctl

```bash
# Clone the repository
git clone https://github.com/kevinb361/wanctl.git
cd wanctl

# Run installation (creates user, directories, systemd units)
sudo ./scripts/install.sh

# Copy example config
sudo cp configs/examples/wan1.yaml.example /etc/wanctl/wan1.yaml

# Copy SSH key
sudo cp ~/.ssh/router_key /etc/wanctl/ssh/router.key
sudo chown wanctl:wanctl /etc/wanctl/ssh/router.key
sudo chmod 600 /etc/wanctl/ssh/router.key
```

## Step 4: Configure for Your Network

Edit `/etc/wanctl/wan1.yaml`:

```yaml
# Minimal required configuration
wan_name: "WAN1"

router:
  host: "192.168.1.1" # Your router IP
  user: "admin" # Router SSH user
  ssh_key: "/etc/wanctl/ssh/router.key"

queues:
  download: "WAN-Download" # Must match RouterOS queue name
  upload: "WAN-Upload" # Must match RouterOS queue name

# Bandwidth settings (adjust to your connection)
continuous_monitoring:
  enabled: true
  download:
    floor_mbps: 50 # Minimum during congestion
    ceiling_mbps: 500 # Your max download speed
  upload:
    floor_mbps: 5
    ceiling_mbps: 50
```

## Step 5: Test Before Enabling

Run a manual test to verify configuration:

```bash
# Run as wanctl user to test permissions
sudo -u wanctl python3 -m cake.autorate_continuous \
    --config /etc/wanctl/wan1.yaml \
    --debug \
    --dry-run
```

**Expected output:**

- Connection to router successful
- Baseline RTT measurement shown
- No errors about queue names or permissions

## Step 6: Enable the Service

```bash
# Enable and start the timer
sudo systemctl enable --now wanctl@wan1.timer

# Verify it's running
systemctl status wanctl@wan1.timer

# Watch the logs
journalctl -u wanctl@wan1 -f
```

## Step 7: Verify Operation

After a few minutes, check the state file:

```bash
cat /var/lib/wanctl/wan1_state.json
```

You should see:

```json
{
  "baseline_rtt": 24.5,
  "ewma_down": 485.2,
  "ewma_up": 48.1,
  "state_down": "GREEN",
  "state_up": "GREEN"
}
```

---

## Setting Up CAKE on RouterOS

If you don't have CAKE queues yet, here's a minimal setup:

```routeros
# Create CAKE queue for download (adjust interface name)
/queue tree add name="WAN-Download" parent=ether1 \
    queue=cake packet-mark=no-mark priority=8

# Create CAKE queue for upload
/queue tree add name="WAN-Upload" parent=ether1 \
    queue=cake packet-mark=no-mark priority=8
```

See the [Mikrotik CAKE documentation](https://help.mikrotik.com/docs/display/ROS/Queue#Queue-CAKE) for advanced configuration.

---

## Common First-Run Issues

### "Host key verification failed"

Router's SSH host key not in known_hosts:

```bash
# Add router host key
sudo -u wanctl ssh-keyscan -H <router_ip> >> /home/wanctl/.ssh/known_hosts
```

### "Permission denied (publickey)"

SSH key not properly configured:

```bash
# Check key permissions
ls -la /etc/wanctl/ssh/router.key
# Should be: -rw------- wanctl wanctl

# Test manually
sudo -u wanctl ssh -i /etc/wanctl/ssh/router.key admin@<router_ip> '/system resource print'
```

### "Queue not found"

Queue name mismatch between config and router:

```bash
# List actual queue names on router
ssh admin@<router_ip> '/queue tree print'

# Update config to match exactly
sudo nano /etc/wanctl/wan1.yaml
```

### "Connection refused" or timeout

Network connectivity issue:

```bash
# Test basic connectivity
ping <router_ip>

# Test SSH port
nc -zv <router_ip> 22
```

---

## Next Steps

Once running:

1. **Monitor** with `journalctl -u wanctl@wan1 -f`
2. **Tune thresholds** in config if needed (GREEN/YELLOW/RED boundaries)
3. **Add second WAN** if multi-WAN setup (see main README)
4. **Enable steering** for dual-WAN latency-sensitive routing

See the main [README](../README.md) for advanced configuration and multi-WAN steering setup.
