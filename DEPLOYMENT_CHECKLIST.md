# Raspberry Pi Deployment Checklist - Single-WAN Fiber

**Target System:** Dad's Fiber Connection
**Platform:** Raspberry Pi (ARM architecture)
**Deployment Type:** Single-WAN (no steering, no dual-WAN complexity)

## Overview

This guide covers deploying the CAKE auto-tuning system to a Raspberry Pi for a single fiber WAN connection. The dual-WAN steering components are **not needed** and should not be deployed.

## Prerequisites

### Hardware
- [ ] Raspberry Pi (any model with Ethernet, Pi 3/4/5 recommended)
- [ ] MikroTik router with CAKE queue configured
- [ ] Stable fiber internet connection
- [ ] SSH access to router configured

### Software
- [ ] Raspberry Pi OS installed (Debian-based)
- [ ] SSH access to Raspberry Pi configured
- [ ] Python 3.7+ installed (check: `python3 --version`)

## Deployment Decision: Continuous vs Binary Search

**Recommended for Raspberry Pi: Continuous Monitoring**

### Option A: Continuous Monitoring (Recommended)
- **Script:** `autorate_continuous.py`
- **Frequency:** Every 2 seconds
- **CPU Impact:** Low (~1-2% on Pi 4)
- **Advantages:** Lightweight, reactive, continuous adaptation
- **Best for:** Fiber connections, resource-constrained devices

### Option B: Binary Search Calibration
- **Script:** `adaptive_cake.py`
- **Frequency:** Every 60+ minutes
- **CPU Impact:** Medium during test (~5-10% on Pi 4)
- **Advantages:** Proactive capacity discovery, detects ISP changes
- **Best for:** Variable connections, capacity monitoring

**This guide covers Option A (continuous monitoring).**

## Step 1: Verify Router Configuration

### Check CAKE Queue Exists

```bash
ssh admin@<router-ip> '/queue tree print where name~"CAKE"'
```

**Expected output:** Queue named like "WAN-Download-CAKE" or similar

**Note the exact queue name** - you'll need it for the config file.

### Verify SSH Key Access

```bash
# Generate SSH key if needed (on Raspberry Pi)
ssh-keygen -t ed25519 -f ~/.ssh/id_ed25519 -N ""

# Copy public key to router
ssh-copy-id admin@<router-ip>

# Test passwordless access
ssh admin@<router-ip> '/system resource print'
```

## Step 2: Install Dependencies

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Python dependencies
sudo apt install -y python3 python3-pip python3-yaml

# Install netperf (for testing)
sudo apt install -y netperf

# Install pexpect (for RouterOS interaction)
pip3 install --user pexpect

# Verify installation
python3 -c "import pexpect, yaml; print('Dependencies OK')"
```

## Step 3: Create Directory Structure

```bash
# Create main directory
mkdir -p ~/fusion_cake/configs
mkdir -p ~/fusion_cake/logs

# Create state directory
mkdir -p ~/adaptive_cake_fiber

# Verify structure
tree ~/fusion_cake
```

## Step 4: Copy Required Files

From your build machine, copy only the files needed for single-WAN:

```bash
# On build machine, copy to Raspberry Pi
scp /home/kevin/CAKE/autorate_continuous.py pi@<raspi-ip>:~/fusion_cake/
scp /home/kevin/CAKE/configs/dad_fiber_config.yaml pi@<raspi-ip>:~/fusion_cake/configs/
scp /home/kevin/CAKE/requirements.txt pi@<raspi-ip>:~/fusion_cake/

# Verify files copied
ssh pi@<raspi-ip> 'ls -lh ~/fusion_cake/'
```

**DO NOT COPY:**
- ❌ `wan_steering_daemon.py` - Requires dual-WAN
- ❌ `cake_stats.py` - Steering dependency only
- ❌ `congestion_assessment.py` - Steering dependency only
- ❌ `steering_config*.yaml` - Steering configs

## Step 5: Create Configuration File

Edit `~/fusion_cake/configs/fiber_config.yaml` on the Raspberry Pi:

```yaml
# CAKE Configuration - Fiber Single-WAN
# Continuous monitoring mode

wan_name: "Fiber"

# RouterOS connection
router:
  host: "192.168.1.1"  # Change to your router IP
  user: "admin"
  ssh_key: "/home/pi/.ssh/id_ed25519"

# Queue names in RouterOS
queues:
  download: "WAN-Download-CAKE"  # Change to your queue name
  upload: "WAN-Upload-CAKE"      # Change to your queue name

# Test servers
test:
  netperf_host: "104.200.21.31"  # Dallas, TX (change if needed)
  ping_host: "1.1.1.1"

# Bandwidth bounds (adjust for your fiber plan)
bandwidth:
  down_max: 900   # Mbps (adjust for your plan)
  down_min: 50
  up_max: 900     # Symmetric fiber
  up_min: 50

# Tuning parameters (continuous monitoring)
tuning:
  alpha: 0.35                 # EWMA smoothing
  base_rtt: 10                # Fiber baseline (typically <10ms)
  use_binary_search: false    # Continuous mode

# K-factor (bloat response)
k_factor:
  delta_0_5ms: 1.00
  delta_5_15ms: 0.95
  delta_15_30ms: 0.85
  delta_30plus: 0.75

# Safety mechanisms
safety:
  max_up_factor: 1.10
  max_down_factor: 1.10
  sanity_fraction: 0.25
  health_fraction: 0.10
  outlier_std_dev: 2.5

# State persistence
state:
  file: "/home/pi/adaptive_cake_fiber/fiber_state.json"
  history_size: 12

# Logging
logging:
  main_log: "/home/pi/fusion_cake/logs/cake_auto.log"
  debug_log: "/home/pi/fusion_cake/logs/cake_auto_debug.log"

# Lock file
lock_file: "/tmp/fusion_cake_fiber.lock"
lock_timeout: 300
```

**Important changes:**
- Update `router.host` to your router IP
- Update `queues.download` and `queues.upload` to match your router queue names
- Adjust `bandwidth` values to match your fiber plan
- Set `base_rtt` appropriately for fiber (typically 5-15ms)

## Step 6: Create Systemd Service

Create `/etc/systemd/system/cake-fiber.service`:

```bash
sudo tee /etc/systemd/system/cake-fiber.service << 'EOF'
[Unit]
Description=Adaptive CAKE Continuous Monitoring for Fiber
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
User=pi
WorkingDirectory=/home/pi/fusion_cake
ExecStart=/usr/bin/python3 /home/pi/fusion_cake/autorate_continuous.py --config /home/pi/fusion_cake/configs/fiber_config.yaml
StandardOutput=journal
StandardError=journal
SyslogIdentifier=cake-fiber

[Install]
WantedBy=multi-user.target
EOF
```

Create `/etc/systemd/system/cake-fiber.timer`:

```bash
sudo tee /etc/systemd/system/cake-fiber.timer << 'EOF'
[Unit]
Description=Run Adaptive CAKE Fiber Continuous Monitoring every 2 seconds

[Timer]
OnBootSec=1min
OnUnitActiveSec=2s
AccuracySec=1s

[Install]
WantedBy=timers.target
EOF
```

## Step 7: Create Log Rotation

```bash
sudo tee /etc/logrotate.d/cake << 'EOF'
/home/pi/fusion_cake/logs/*.log {
    daily
    rotate 7
    compress
    delaycompress
    missingok
    notifempty
    create 0644 pi pi
}
EOF
```

Test log rotation:
```bash
sudo logrotate -f /etc/logrotate.d/cake
```

## Step 8: Initial Test Run

**Test manually before enabling timer:**

```bash
cd ~/fusion_cake
python3 autorate_continuous.py --config configs/fiber_config.yaml --debug
```

**Expected output:**
- Connection to router successful
- Baseline RTT measured
- Download/upload throughput measured
- CAKE limits calculated and applied
- No errors

**If errors occur:**
- Check router SSH access
- Verify queue names match config
- Check netperf server reachability: `ping 104.200.21.31`

## Step 9: Enable and Start Service

```bash
# Reload systemd
sudo systemctl daemon-reload

# Enable timer (start on boot)
sudo systemctl enable cake-fiber.timer

# Start timer
sudo systemctl start cake-fiber.timer

# Check status
systemctl status cake-fiber.timer
systemctl list-timers cake-*
```

## Step 10: Verify Operation

### Check Service Logs
```bash
# Live log monitoring
tail -f ~/fusion_cake/logs/cake_auto.log

# Systemd journal
journalctl -u cake-fiber.service -f
```

### Check CAKE Settings
```bash
ssh admin@<router-ip> '/queue tree print detail where name~"CAKE"'
```

**Verify:**
- Max-limit values are being set (not 0)
- Values change over time as conditions vary
- No errors in logs

### Check State File
```bash
cat ~/adaptive_cake_fiber/fiber_state.json | python3 -m json.tool
```

**Verify:**
- `ewma_down` and `ewma_up` values are reasonable
- `history_down` and `history_up` arrays are populating
- State file updates every 2 seconds (check mtime: `ls -lh ~/adaptive_cake_fiber/`)

## Step 11: Monitor for 24 Hours

### Health Indicators

**Good signs:**
- ✅ Timer runs every 2 seconds (check `systemctl list-timers`)
- ✅ Logs show successful measurements
- ✅ CAKE limits update regularly
- ✅ State file updates (check timestamp)
- ✅ No errors in journalctl

**Warning signs:**
- ❌ Service fails repeatedly → Check logs, verify router access
- ❌ Zero throughput measured → Check netperf server, network connectivity
- ❌ "Verification failed" → Check queue names in config
- ❌ High CPU usage → Consider increasing timer interval to 5s

### Performance Check

Run speed test while system is active:
```bash
# From another device on the network
speedtest-cli  # or use fast.com

# Check bufferbloat
# Visit: https://www.waveform.com/tools/bufferbloat
```

**Expected:** A or A+ grade with <20ms added latency under load

## Troubleshooting

### Service Fails to Start
```bash
# Check detailed logs
journalctl -u cake-fiber.service -n 50

# Common issues:
# - SSH key not set up → Verify passwordless SSH access
# - Config file not found → Check path in service file
# - Python dependencies missing → Reinstall pexpect, PyYAML
```

### High CPU Usage
```bash
# Check CPU usage during test
top -b -n 1 | grep python3

# If >10% CPU sustained:
# Option 1: Increase timer interval to 5s (edit cake-fiber.timer)
# Option 2: Use binary search mode instead (60min intervals)
```

### Logs Not Rotating
```bash
# Test logrotate manually
sudo logrotate -d /etc/logrotate.d/cake

# Check logrotate is enabled
systemctl status logrotate.timer
```

### Caps Not Updating on Router
```bash
# Verify SSH access
ssh admin@<router-ip> '/system resource print'

# Check queue names
ssh admin@<router-ip> '/queue tree print'

# Manually test setting limit
ssh admin@<router-ip> '/queue tree set [find name="WAN-Download-CAKE"] max-limit=800000000'
```

## Optional: Binary Search Mode

If you prefer proactive calibration over continuous monitoring:

1. Use `adaptive_cake.py` instead of `autorate_continuous.py`
2. Create binary search config (copy from `att_binary_search.yaml` as template)
3. Update systemd timer to run every 60 minutes instead of 2 seconds
4. Benefits: Detects ISP capacity changes, more thorough testing
5. Drawbacks: Higher CPU usage during tests, less frequent updates

## Comparison: Dual-WAN vs Single-WAN

| Feature | Dual-WAN (Current) | Single-WAN (Raspberry Pi) |
|---------|-------------------|--------------------------|
| Containers | 2 (cake-att, cake-spectrum) | 1 (Raspberry Pi) |
| Services per container | 2-3 | 1 |
| Steering daemon | ✅ Yes (Spectrum only) | ❌ Not needed |
| Scripts needed | 3 (adaptive_cake.py, autorate_continuous.py, wan_steering_daemon.py) | 1 (autorate_continuous.py) |
| Config files | 5 (2x continuous, 2x binary, 1x steering) | 1 (fiber_config.yaml) |
| Complexity | High (multi-signal voting, hysteresis, state sharing) | Low (single queue, straightforward) |

## Maintenance

### Weekly Check
```bash
# Check service status
systemctl status cake-fiber.timer

# Check log size
du -sh ~/fusion_cake/logs/

# Verify rotation working
ls -lh ~/fusion_cake/logs/*.gz
```

### Monthly Review
- Review log for errors or warnings
- Check router CAKE statistics: drops, queue depth
- Verify performance: Run bufferbloat test
- Update config if fiber plan changes

## Backup

```bash
# Backup entire fusion_cake directory
tar czf ~/cake_backup_$(date +%Y%m%d).tar.gz ~/fusion_cake ~/adaptive_cake_fiber /etc/systemd/system/cake-fiber.*

# Copy backup off Raspberry Pi
scp pi@<raspi-ip>:~/cake_backup_*.tar.gz ~/backups/
```

## Restore from Backup

```bash
# Copy backup to Raspberry Pi
scp ~/backups/cake_backup_20251213.tar.gz pi@<raspi-ip>:~

# Extract
ssh pi@<raspi-ip>
tar xzf ~/cake_backup_20251213.tar.gz -C /

# Reload systemd and restart
sudo systemctl daemon-reload
sudo systemctl restart cake-fiber.timer
```

---

## Summary

**Deployed:**
- ✅ Continuous CAKE monitoring (every 2 seconds)
- ✅ Single-WAN configuration (no steering complexity)
- ✅ Log rotation (daily, 7-day retention)
- ✅ Systemd service (auto-start on boot)

**Not Deployed (Dual-WAN Only):**
- ❌ WAN steering daemon
- ❌ Congestion assessment
- ❌ CAKE statistics monitoring
- ❌ Multi-signal voting logic

**Next Steps:**
- Monitor for 24 hours
- Verify A/A+ bufferbloat grade
- Adjust config if needed (bandwidth limits, alpha, k-factor)
- Enjoy zero-bufferbloat fiber! 🎉

---

**Created:** December 13, 2025
**For:** Dad's Fiber - Raspberry Pi Single-WAN Deployment
**Based on:** Validated dual-WAN system (production-ready since Dec 13, 2025)
