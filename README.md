# Adaptive CAKE Auto-Tuning System - Refactored

Production-grade bufferbloat elimination system for dual-WAN Mikrotik routers.

## What's New in the Refactor

### ✅ Improvements

1. **Unified Script** - Single `adaptive_cake.py` with config file support
2. **Proper Bufferbloat Testing** - Measures latency UNDER LOAD (concurrent netperf + ping)
3. **Outlier Rejection** - Statistical filtering of bad measurements
4. **Lock File Mechanism** - Prevents concurrent test runs
5. **Measurement History** - Tracks last 12 measurements (2 hours)
6. **Consistent Logging** - Structured logging throughout
7. **Config-Driven** - All tuning parameters in YAML
8. **Robust Error Handling** - Comprehensive exception handling and recovery

### Key Difference: Latency Under Load

**Old Method (Sequential)**:
```
1. netperf download test (5s)
2. netperf upload test (5s)
3. ping test (5s) ← measures IDLE latency
```

**New Method (Concurrent)**:
```
1. Measure baseline latency (idle, 3s)
2. Start netperf IN BACKGROUND (15s)
3. Ping WHILE netperf is running (10s)
4. Calculate: bloat = loaded_latency - baseline
```

This actually measures bufferbloat as defined: **latency increase under load**.

---

## Quick Start

### 1. Deploy

```bash
cd /home/kevin/CAKE
./deploy_refactored.sh
```

This will:
- Install dependencies (PyYAML, pexpect)
- Copy files to both containers
- Set up systemd timers
- Start services

### 2. Monitor

```bash
# View timer status
ssh kevin@10.10.110.247 'systemctl list-timers cake-*'
ssh kevin@10.10.110.246 'systemctl list-timers cake-*'

# Watch logs live
ssh kevin@10.10.110.247 'journalctl -u cake-att.service -f'
ssh kevin@10.10.110.246 'journalctl -u cake-spectrum.service -f'
```

### 3. Manual Test (Recommended First)

```bash
# ATT
ssh kevin@10.10.110.247
cd /home/kevin/fusion_cake
python3 adaptive_cake.py --config configs/att_config.yaml --debug

# Spectrum
ssh kevin@10.10.110.246
cd /home/kevin/fusion_cake
python3 adaptive_cake.py --config configs/spectrum_config.yaml --debug
```

---

## File Structure

```
/home/kevin/CAKE/                    # Build directory (this machine)
├── adaptive_cake.py                 # Unified script
├── requirements.txt                 # Python dependencies
├── configs/
│   ├── att_config.yaml             # ATT configuration
│   └── spectrum_config.yaml        # Spectrum configuration
├── systemd/
│   ├── cake-att.service            # ATT service
│   ├── cake-att.timer              # ATT 10-min timer
│   ├── cake-att-reset.service      # ATT reset service
│   ├── cake-att-reset.timer        # ATT reset timer (3am/3pm)
│   ├── cake-spectrum.service       # Spectrum service
│   ├── cake-spectrum.timer         # Spectrum 10-min timer (+5min offset)
│   ├── cake-spectrum-reset.service # Spectrum reset service
│   └── cake-spectrum-reset.timer   # Spectrum reset timer (3am/3pm)
├── deploy_refactored.sh            # Deployment script
└── README.md                        # This file

/home/kevin/fusion_cake/            # On each container (deployed)
├── adaptive_cake.py
├── requirements.txt
└── configs/
    └── <isp>_config.yaml
```

---

## Configuration

All tuning parameters are in YAML config files. Key settings:

### Bandwidth Limits
```yaml
bandwidth:
  down_max: 85   # Maximum bandwidth (Mbps)
  down_min: 20   # Minimum bandwidth (safety floor)
  up_max: 16
  up_min: 4
```

### EWMA Tuning
```yaml
tuning:
  alpha: 0.35                    # Smoothing factor (lower = smoother)
  alpha_good_conditions: 0.40    # Higher alpha when no bloat
  base_rtt: 48                   # Baseline RTT for this WAN (ms)
```

### K-Factor (Congestion Response)
```yaml
k_factor:
  delta_0_5ms: 1.00     # No bloat → full speed
  delta_5_15ms: 0.90    # Light bloat → 10% reduction
  delta_15_30ms: 0.75   # Moderate bloat → 25% reduction
  delta_30plus: 0.60    # Severe bloat → 40% reduction
```

### Safety Limits
```yaml
safety:
  max_up_factor: 1.35       # Max 35% increase per cycle
  max_down_factor: 0.65     # Max 35% decrease per cycle
  outlier_std_dev: 2.5      # Reject measurements > 2.5σ
```

---

## How It Works

### Measurement Cycle (Every 10 Minutes)

1. **Acquire Lock** - Ensures no other test is running
2. **Baseline Latency** - Measure idle RTT (3 seconds)
3. **Download Test**:
   - Start netperf TCP_MAERTS in background (15s)
   - Ping simultaneously (10s) → measure loaded latency
   - Calculate download bloat = loaded_RTT - baseline_RTT
4. **Upload Test**:
   - Start netperf TCP_STREAM in background (15s)
   - Ping simultaneously (10s) → measure loaded latency
   - Calculate upload bloat = loaded_RTT - baseline_RTT
5. **Outlier Check** - Compare to recent history, reject if >2.5σ
6. **EWMA Update** - Smooth new measurement into running average
7. **Compute New Caps**:
   - Apply k-factor based on bloat level
   - Limit rate-of-change (max ±35%)
   - Clamp to min/max bounds
8. **Apply to RouterOS** - Set queue max-limits via SSH
9. **Verify** - Read back values to confirm correct application
10. **Persist State** - Save EWMA and history to JSON

**Total cycle time**: ~50-60 seconds

### Safety Mechanisms

1. **Sanity Check** - If speeds drop below 25% of max, unshape and retest
2. **Health Check** - Reject measurements below 10% of max (clearly wrong)
3. **Outlier Detection** - Statistical filtering of anomalous measurements
4. **Rate-of-Change Limiting** - Prevents wild swings (max 35% change per cycle)
5. **Post-Write Verification** - Confirms RouterOS applied settings correctly
6. **Lock Files** - Prevents simultaneous tests (despite timer offset)
7. **Twice-Daily Reset** - Clears state at 3am/3pm to prevent drift

---

## Timer Schedule

### Regular Tests
- **ATT**: Boots +2min, then every 10 min (:02, :12, :22, :32, :42, :52)
- **Spectrum**: Boots +7min, then every 10 min (:07, :17, :27, :37, :47, :57)
- **5-minute offset** prevents test interference

### Nightly Resets
- **Both WANs**: 3:00 AM and 3:00 PM
- Clears EWMA state
- Removes CAKE shaping (max-limit=0)
- Next measurement cycle rebuilds baseline

---

## Monitoring & Debugging

### Check Timer Status
```bash
systemctl list-timers cake-*
```

Output shows next run time and last run status.

### View Recent Logs
```bash
# Systemd journal (last 50 entries)
journalctl -u cake-att.service -n 50

# Live tail
journalctl -u cake-att.service -f

# Since specific time
journalctl -u cake-att.service --since "1 hour ago"
```

### View Log Files
```bash
# Main log (INFO level)
tail -f /var/log/cake_auto.log

# Debug log (if --debug flag used)
tail -f /var/log/cake_auto_debug.log
```

### View State
```bash
# ATT state
cat /home/kevin/adaptive_cake_att/att_state.json

# Spectrum state
cat /home/kevin/adaptive_cake_spectrum/spectrum_state.json
```

Shows current EWMA values, last caps, and measurement history.

### Manual Test Run
```bash
# Normal run
cd /home/kevin/fusion_cake
python3 adaptive_cake.py --config configs/att_config.yaml

# Debug run (verbose output)
python3 adaptive_cake.py --config configs/att_config.yaml --debug

# Reset state
python3 adaptive_cake.py --config configs/att_config.yaml --reset
```

---

## Troubleshooting

### Service Won't Start

```bash
# Check service status
systemctl status cake-att.service

# View errors
journalctl -u cake-att.service --since "10 minutes ago"

# Check script permissions
ls -l /home/kevin/fusion_cake/adaptive_cake.py

# Test manually
cd /home/kevin/fusion_cake
python3 adaptive_cake.py --config configs/att_config.yaml --debug
```

### Zero Throughput Measured

Possible causes:
- Netperf server unreachable
- Netperf not installed (`sudo apt install netperf`)
- Firewall blocking traffic
- Network routing issue

Test manually:
```bash
netperf -H 104.200.21.31 -t TCP_STREAM -l 5
ping -c 5 104.200.21.31
```

### RouterOS Verification Failed

Possible causes:
- SSH key not working
- Queue names don't match config
- RouterOS syntax changed

Test SSH access:
```bash
ssh -i /home/kevin/.ssh/mikrotik_cake admin@10.10.99.1 \
    '/queue tree print'
```

### Outliers Being Rejected

This is normal if your WAN is highly variable. Check logs:
```bash
grep "Outlier" /var/log/cake_auto.log
```

If too many outliers, consider:
- Increasing `outlier_std_dev` in config (2.5 → 3.0)
- Lowering `alpha` for more smoothing (0.35 → 0.25)

### Bufferbloat Not Improving

1. Check that bloat is being measured:
   ```bash
   journalctl -u cake-att.service | grep "bloat="
   ```

2. Verify k-factor is responding:
   ```bash
   journalctl -u cake-att.service | grep "k-factor"
   ```

3. Check actual CAKE limits on Mikrotik:
   ```bash
   ssh -i /home/kevin/.ssh/mikrotik_cake admin@10.10.99.1 \
       '/queue tree print detail'
   ```

4. Test bufferbloat manually (from container):
   ```bash
   # Start loading link
   netperf -H 104.200.21.31 -t TCP_STREAM -l 60 &

   # Ping while loaded
   ping -i 0.2 -c 50 104.200.21.31

   # Kill netperf
   killall netperf

   # Ping again (idle)
   ping -i 0.2 -c 20 104.200.21.31
   ```

---

## Adding a New WAN

To add a third WAN connection:

1. **Create config file**:
   ```bash
   cp configs/att_config.yaml configs/newwan_config.yaml
   # Edit with appropriate values
   ```

2. **Create systemd units**:
   ```bash
   # Copy and modify ATT units
   cp systemd/cake-att.service systemd/cake-newwan.service
   cp systemd/cake-att.timer systemd/cake-newwan.timer
   # Edit WorkingDirectory, ExecStart paths, timer offset
   ```

3. **Deploy**:
   ```bash
   scp configs/newwan_config.yaml user@container:/home/user/fusion_cake/configs/
   scp adaptive_cake.py user@container:/home/user/fusion_cake/
   scp systemd/cake-newwan* user@container:/tmp/

   ssh user@container
   sudo mv /tmp/cake-newwan* /etc/systemd/system/
   sudo systemctl daemon-reload
   sudo systemctl enable --now cake-newwan.timer
   ```

---

## Performance Impact

- **Test duration**: ~50-60 seconds per WAN
- **Frequency**: Every 10 minutes
- **Overhead**: <1% of time spent testing
- **Bandwidth used**: ~100-150 MB per day per WAN
- **CPU**: Negligible (<1% during tests)
- **Memory**: ~50 MB per Python process

---

## Dependencies

- **Python 3**: 3.7+
- **pexpect**: For interactive command execution
- **PyYAML**: For config file parsing
- **netperf**: Network performance measurement tool
- **ping**: ICMP latency measurement
- **ssh**: RouterOS communication
- **systemd**: Timer scheduling

---

## Security Notes

- SSH keys used for RouterOS authentication (no passwords in configs)
- Lock files prevent DoS via concurrent runs
- State files are user-readable only
- No network services exposed (pull-based architecture)

---

## Future Enhancements

Possible additions:

1. **Dashboard** - Web UI showing both WANs, graphs, history
2. **Alerting** - Email/webhook when degradation detected
3. **Prometheus Export** - Metrics for Grafana integration
4. **Traffic Steering** - Intelligent routing based on latency/capacity
5. **Multi-Server Testing** - Redundant netperf servers for reliability
6. **Jitter Measurement** - Additional QoS metric
7. **Historical Analysis** - Detect time-of-day patterns

---

## License & Credits

Created by Kevin for Mikrotik rb5009 dual-WAN bufferbloat elimination.

Based on fusion-core design principles:
- EWMA stabilization
- Latency-aware k-factor
- Post-write verification
- Autonomous operation

---

## Support

For issues or questions:
1. Check logs: `journalctl -u cake-<isp>.service`
2. Run manual test with `--debug`
3. Verify RouterOS connectivity
4. Check config file syntax
