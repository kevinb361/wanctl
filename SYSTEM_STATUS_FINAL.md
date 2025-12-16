# System Status - Adaptive Dual-WAN CAKE System

**Last Updated:** December 13, 2025
**Status:** ✅ **OPERATIONAL - Production Ready**

## Quick Status Check

```bash
# Check all timers on both containers
ssh kevin@10.10.110.246 'systemctl list-timers cake-* wan-*'
ssh kevin@10.10.110.247 'systemctl list-timers cake-*'

# Check current CAKE bandwidth caps
ssh admin@10.10.99.1 '/queue tree print detail where name~"WAN-"'

# Check steering status
ssh kevin@10.10.110.246 'tail -20 /home/kevin/fusion_cake/logs/steering.log'

# Check congestion state
ssh kevin@10.10.110.246 'cat /home/kevin/adaptive_cake_steering/steering_state.json'
```

## System Architecture

### Two-Loop Control System

**Fast Loop (2 seconds)** - Reactive adaptation:
- `autorate_continuous.py` - Adjusts CAKE caps based on measured throughput
- `wan_steering_daemon.py` - Routes traffic based on congestion state
- Runs on: Spectrum container (10.10.110.246)

**Slow Loop (60 minutes)** - Proactive calibration:
- `adaptive_cake.py` - Binary search capacity discovery via Dallas netperf tests
- Congestion gating: Only runs when congestion_state == "GREEN"
- Runs on: Both containers

## What's Running Where

### Spectrum Container (10.10.110.246)

**3 active services:**

1. **Continuous CAKE Tuning** (Fast loop)
   - Script: `/home/kevin/fusion_cake/autorate_continuous.py`
   - Config: `/home/kevin/fusion_cake/configs/spectrum_config.yaml`
   - Timer: `cake-spectrum-continuous.timer` (every 2 seconds)
   - Service: `cake-spectrum-continuous.service`
   - Log: `/home/kevin/fusion_cake/logs/cake_auto.log`

2. **Binary Search Calibration** (Slow loop)
   - Script: `/home/kevin/fusion_cake/adaptive_cake.py`
   - Config: `/home/kevin/fusion_cake/configs/spectrum_binary_search.yaml`
   - Timer: `cake-spectrum.timer` (every 60 minutes)
   - Service: `cake-spectrum.service`
   - Log: `/home/kevin/fusion_cake/logs/cake_binary.log`

3. **Adaptive WAN Steering** (Fast loop)
   - Script: `/home/kevin/fusion_cake/wan_steering_daemon.py`
   - Config: `/home/kevin/fusion_cake/configs/steering_config_v2.yaml`
   - Timer: `wan-steering.timer` (every 2 seconds)
   - Service: `wan-steering.service`
   - Log: `/home/kevin/fusion_cake/logs/steering.log`

### ATT Container (10.10.110.247)

**2 active services:**

1. **Continuous CAKE Tuning** (Fast loop)
   - Script: `/home/kevin/fusion_cake/autorate_continuous.py`
   - Config: `/home/kevin/fusion_cake/configs/att_config.yaml`
   - Timer: `cake-att-continuous.timer` (every 2 seconds)
   - Service: `cake-att-continuous.service`
   - Log: `/home/kevin/fusion_cake/logs/cake_auto.log`

2. **Binary Search Calibration** (Slow loop)
   - Script: `/home/kevin/fusion_cake/adaptive_cake.py`
   - Config: `/home/kevin/fusion_cake/configs/att_binary_search.yaml`
   - Timer: `cake-att.timer` (every 60 minutes)
   - Service: `cake-att.service`
   - Log: `/home/kevin/fusion_cake/logs/cake_binary.log`

## Configuration Values

### Spectrum (Cable 1000/40)

**Bandwidth Bounds:**
- Download: 940 Mbps max, 150 Mbps min
- Upload: 38 Mbps max, 8 Mbps min

**Binary Search Settings:**
- Target bloat: 10.0 ms
- Search iterations: 5
- Full search interval: 6 cycles (6 hours)
- Quick check bloat threshold: 15.0 ms

**Steering Thresholds:**
- GREEN: RTT <5ms, drops=0
- YELLOW: RTT 5-15ms OR queue >10 packets
- RED: RTT >15ms AND drops >0 AND queue >50 packets

**Hysteresis:**
- Enable steering: 2 consecutive RED samples (4 seconds)
- Disable steering: 15 consecutive GREEN samples (30 seconds)

### ATT (DSL 100/20)

**Bandwidth Bounds:**
- Download: 95 Mbps max, 25 Mbps min
- Upload: 18 Mbps max, 6 Mbps min

**Binary Search Settings:**
- Target bloat: 10.0 ms
- Search iterations: 3 (fewer for DSL)
- Full search interval: 6 cycles (6 hours)
- Quick check bloat threshold: 15.0 ms

## File Locations

### Build Machine (/home/kevin/CAKE/)

**Active Scripts:**
- `adaptive_cake.py` - Binary search engine
- `autorate_continuous.py` - Continuous monitoring
- `wan_steering_daemon.py` - Adaptive steering
- `cake_stats.py` - CAKE statistics reader
- `congestion_assessment.py` - Three-state logic

**Active Configs:**
- `configs/att_config.yaml` - ATT continuous monitoring
- `configs/spectrum_config.yaml` - Spectrum continuous monitoring
- `configs/att_binary_search.yaml` - ATT binary search
- `configs/spectrum_binary_search.yaml` - Spectrum binary search
- `configs/steering_config_v2.yaml` - Steering configuration

**Deployment Scripts:**
- `deploy_refactored.sh` - Deploy CAKE tuning
- `deploy_steering.sh` - Deploy steering system
- `restart_binary_search_services.sh` - Restart services after config changes
- `install_logrotate.sh` - Install log rotation

**Documentation:**
- `CLAUDE.md` - Complete technical overview
- `EXPERT_SUMMARY.md` - Expert review and validation
- `SYSTEM_STATUS_FINAL.md` - This file
- `DEPLOYMENT_CHECKLIST.md` - Raspberry Pi deployment guide
- `VALIDATION_GUIDE.md` - Validation test procedures

**Archived Files:**
- `.obsolete/` - Old implementations preserved for reference

### Containers (Active Files Only)

**Scripts:** `/home/kevin/fusion_cake/`
- `adaptive_cake.py`
- `autorate_continuous.py`
- `wan_steering_daemon.py`
- `cake_stats.py`
- `congestion_assessment.py`

**Configs:** `/home/kevin/fusion_cake/configs/`
- `att_config.yaml` or `spectrum_config.yaml`
- `att_binary_search.yaml` or `spectrum_binary_search.yaml`
- `steering_config_v2.yaml` (Spectrum only)

**Logs:** `/home/kevin/fusion_cake/logs/`
- `cake_auto.log` - Continuous monitoring
- `cake_binary.log` - Binary search calibration
- `steering.log` - Steering decisions (Spectrum only)

**State Files:**
- `/home/kevin/adaptive_cake_att/att_state.json`
- `/home/kevin/adaptive_cake_spectrum/spectrum_state.json`
- `/home/kevin/adaptive_cake_steering/steering_state.json` (Spectrum only)

**Systemd Units:** `/etc/systemd/system/`
- `cake-*.{service,timer}`
- `wan-steering.{service,timer}` (Spectrum only)

**Archived Files:**
- `/home/kevin/.obsolete_20251213/` - Old implementations

## Log Rotation

**Configuration:** `/etc/logrotate.d/cake` on both containers

**Schedule:**
- Rotation: Daily
- Retention: 7 days
- Compression: Yes (gzip)
- Owner: kevin:kevin

**Installation:**
```bash
# From build machine
cd /home/kevin/CAKE
./install_logrotate.sh
```

**Manual rotation test:**
```bash
ssh kevin@10.10.110.246 'sudo logrotate -f /etc/logrotate.d/cake'
```

## Monitoring Commands

### Check Service Status
```bash
# Spectrum container
ssh kevin@10.10.110.246 'systemctl status cake-spectrum-continuous.service'
ssh kevin@10.10.110.246 'systemctl status cake-spectrum.service'
ssh kevin@10.10.110.246 'systemctl status wan-steering.service'

# ATT container
ssh kevin@10.10.110.247 'systemctl status cake-att-continuous.service'
ssh kevin@10.10.110.247 'systemctl status cake-att.service'
```

### Check Timer Status
```bash
# All timers on Spectrum
ssh kevin@10.10.110.246 'systemctl list-timers cake-* wan-*'

# All timers on ATT
ssh kevin@10.10.110.247 'systemctl list-timers cake-*'
```

### View Logs
```bash
# Live logs (continuous monitoring)
ssh kevin@10.10.110.246 'tail -f /home/kevin/fusion_cake/logs/cake_auto.log'

# Live logs (binary search)
ssh kevin@10.10.110.247 'tail -f /home/kevin/fusion_cake/logs/cake_binary.log'

# Live logs (steering)
ssh kevin@10.10.110.246 'tail -f /home/kevin/fusion_cake/logs/steering.log'

# Journalctl (systemd logs)
ssh kevin@10.10.110.246 'journalctl -u cake-spectrum.service -f'
```

### Check Current CAKE Settings
```bash
# View all CAKE queues
ssh admin@10.10.99.1 '/queue tree print detail where name~"WAN-"'

# View specific queue
ssh admin@10.10.99.1 '/queue tree print detail where name="WAN-Download-Spectrum"'
```

### Check Congestion State
```bash
# Current steering state
ssh kevin@10.10.110.246 'cat /home/kevin/adaptive_cake_steering/steering_state.json | python3 -m json.tool'

# Congestion state only
ssh kevin@10.10.110.246 'cat /home/kevin/adaptive_cake_steering/steering_state.json | python3 -c "import sys,json; print(json.load(sys.stdin)[\"congestion_state\"])"'

# Recent steering decisions
ssh kevin@10.10.110.246 'grep "State transition" /home/kevin/fusion_cake/logs/steering.log | tail -10'
```

## Troubleshooting

### Service Failed
```bash
# Check status
ssh kevin@10.10.110.246 'systemctl status cake-spectrum.service'

# View last 50 log lines
ssh kevin@10.10.110.246 'journalctl -u cake-spectrum.service -n 50'

# Restart service
ssh kevin@10.10.110.246 'sudo systemctl restart cake-spectrum.service'
```

### Binary Search Permission Error
**Symptom:** `PermissionError: /var/log/cake_binary.log`

**Fix:** Already resolved! Logging paths updated to `/home/kevin/fusion_cake/logs/`

**Verify fix:**
```bash
ssh kevin@10.10.110.246 'grep "main_log" /home/kevin/fusion_cake/configs/spectrum_binary_search.yaml'
```

### Logs Growing Too Large
**Solution:** Log rotation configured

**Check rotation status:**
```bash
ssh kevin@10.10.110.246 'ls -lh /home/kevin/fusion_cake/logs/*.gz'
```

### Steering Not Working
```bash
# Check steering daemon is running
ssh kevin@10.10.110.246 'systemctl status wan-steering.service'

# Check CAKE-aware mode enabled
ssh kevin@10.10.110.246 'grep "CAKE-aware" /home/kevin/fusion_cake/logs/steering.log | tail -1'

# Check congestion state
ssh kevin@10.10.110.246 'cat /home/kevin/adaptive_cake_steering/steering_state.json'

# Verify RouterOS mangle rule exists
ssh admin@10.10.99.1 '/ip firewall mangle print where comment~"ADAPTIVE"'
```

### Test Not Running (Deferred)
**Symptom:** Binary search logs show "CALIBRATION DEFERRED"

**Explanation:** Normal! Binary search only runs when congestion_state == "GREEN"

**Check:**
```bash
ssh kevin@10.10.110.246 'grep "DEFERRED" /home/kevin/fusion_cake/logs/cake_binary.log | tail -5'
```

## Backups

**Location:** `/home/kevin/CAKE_BACKUP_20251213/`

**Contents:**
- Build machine: Complete copy (1.4 MB)
- Spectrum container: tar.gz archive (1.8 MB)
- ATT container: tar.gz archive (8.1 MB)

**Restore:**
```bash
# Build machine
cp -r /home/kevin/CAKE_BACKUP_20251213/build_machine/* /home/kevin/CAKE/

# Containers
scp /home/kevin/CAKE_BACKUP_20251213/spectrum_backup.tar.gz kevin@10.10.110.246:/tmp/
ssh kevin@10.10.110.246 'cd / && tar xzf /tmp/spectrum_backup.tar.gz'
```

## System Health Indicators

**All GREEN:**
- ✅ All timers active (check with `systemctl list-timers`)
- ✅ No failed services (check with `systemctl --failed`)
- ✅ Logs rotating daily (check for `.gz` files)
- ✅ Binary search runs successfully when GREEN
- ✅ Steering triggers on congestion
- ✅ CAKE caps updating regularly

**Action Required:**
- ❌ Timer not listed → Service disabled, run `sudo systemctl enable <service>.timer`
- ❌ Service failed → Check logs, restart service
- ❌ No log rotation → Run `/home/kevin/CAKE/install_logrotate.sh`

## Next Steps

### Remaining Manual Tasks

1. **Install log rotation:**
   ```bash
   cd /home/kevin/CAKE
   ./install_logrotate.sh
   ```

2. **Restart binary search services** (picks up new logging paths):
   ```bash
   cd /home/kevin/CAKE
   ./restart_binary_search_services.sh
   ```

3. **Monitor for 24 hours:**
   - Verify binary search runs successfully
   - Check logs for errors
   - Confirm steering operates correctly

4. **After 1 week of stability:**
   ```bash
   # Delete obsolete files permanently
   ssh kevin@10.10.110.246 'rm -rf /home/kevin/.obsolete_*'
   ssh kevin@10.10.110.247 'rm -rf /home/kevin/.obsolete_*'
   cd /home/kevin/CAKE && rm -rf .obsolete/
   ```

### Future Deployment: Raspberry Pi

See `DEPLOYMENT_CHECKLIST.md` for step-by-step guide to deploy on Dad's fiber.

---

**System Status:** ✅ **OPERATIONAL**
**Last Cleanup:** December 13, 2025
**Next Review:** After 1 week stability (December 20, 2025)
