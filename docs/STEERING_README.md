# Adaptive WAN Steering System - Deployment Guide

## What Was Created

### Python Daemon
- **`wan_steering_daemon.py`** (~650 lines)
  - State machine with hysteresis (SPECTRUM_GOOD ↔ SPECTRUM_DEGRADED)
  - Measures Spectrum RTT every 2 seconds
  - Reads baseline RTT from autorate_continuous state file (local filesystem)
  - Toggles RouterOS mangle rule based on latency delta
  - Follows patterns from adaptive_cake.py and autorate_continuous.py

### Configuration
- **`configs/steering_config.yaml`**
  - Thresholds: 25ms to degrade, 12ms to recover
  - Streak counts: 8 bad samples (16s), 15 good samples (30s)
  - Ping configuration: 1.1.1.1 via Spectrum
  - State persistence and logging paths

### Systemd Units
- **`systemd/wan-steering.service`**
  - One-shot execution (invoked by timer)
  - Runs as user `kevin`
  - Security hardening enabled

- **`systemd/wan-steering.timer`**
  - Triggers every 2 seconds
  - 1-minute boot delay
  - 1-second accuracy

### Deployment Scripts
- **`deploy_steering.sh`**
  - Deploys to cake-spectrum container (10.10.110.246)
  - Copies daemon, config, and systemd units
  - Provides manual installation instructions

- **`add_steering_rules.sh`**
  - RouterOS mangle rule commands
  - Adds LATENCY_SENSITIVE translation rules
  - Adds ADAPTIVE steering rule (disabled by default)
  - Includes verification commands

---

## Deployment Steps

### 1. Add RouterOS Mangle Rules (First!)

```bash
# Review the commands
cd /home/kevin/CAKE
./add_steering_rules.sh

# Then manually run the commands on RouterOS
ssh admin@10.10.99.1

# Copy/paste the commands from the script output
# This adds:
# - 3 LATENCY_SENSITIVE translation rules
# - 1 ADAPTIVE steering rule (initially disabled)
```

**Verify:**
```bash
ssh admin@10.10.99.1 '/ip firewall mangle print where comment~"ADAPTIVE"'
# Should show rule with disabled=yes
```

### 2. Deploy Steering Daemon

```bash
cd /home/kevin/CAKE
./deploy_steering.sh
```

This deploys to **cake-spectrum container (10.10.110.246)** - colocated with autorate_continuous.

### 3. Install Systemd Units (Manual, as root)

```bash
# SSH to cake-spectrum container
ssh root@10.10.110.246

# Install systemd units
mv /tmp/wan-steering.service /etc/systemd/system/
mv /tmp/wan-steering.timer /etc/systemd/system/
systemctl daemon-reload

# Enable and start
systemctl enable wan-steering.timer
systemctl start wan-steering.timer

# Verify
systemctl status wan-steering.timer
systemctl list-timers wan-steering.timer
```

### 4. Monitor Operation

```bash
# Live daemon logs
ssh kevin@10.10.110.246 'journalctl -u wan-steering.service -f'

# State file
ssh kevin@10.10.110.246 'cat /home/kevin/adaptive_cake_steering/steering_state.json'

# Log file
ssh kevin@10.10.110.246 'tail -f /home/kevin/wanctl/logs/steering.log'

# RouterOS rule status
ssh admin@10.10.99.1 '/ip firewall mangle print where comment~"ADAPTIVE"'
```

---

## How It Works

### Architecture

```
cake-spectrum (10.10.110.246)
├─ autorate_continuous.py (every 2s)
│   └─ Measures Spectrum RTT, tunes CAKE
│   └─ Writes: /home/kevin/adaptive_cake_spectrum/spectrum_state.json
│
└─ wan_steering_daemon.py (every 2s)
    └─ Reads baseline_rtt from autorate state (local file)
    └─ Measures current Spectrum RTT
    └─ Calculates delta = current_rtt - baseline_rtt
    └─ State machine with hysteresis
    └─ Toggles RouterOS mangle rule via SSH
```

### State Machine

**SPECTRUM_GOOD (default):**
- All traffic uses Spectrum (default routing)
- RouterOS ADAPTIVE rule is **disabled**
- Monitors delta RTT

**Transition to DEGRADED:**
- Trigger: delta > 25ms for 8 consecutive samples (16 seconds)
- Action: Enable RouterOS ADAPTIVE rule
- Effect: New LATENCY_SENSITIVE connections route to ATT

**SPECTRUM_DEGRADED:**
- Latency-sensitive traffic (QOS_HIGH, GAMES, QOS_MEDIUM) → ATT
- Bulk traffic (QOS_LOW, QOS_NORMAL) → Spectrum (unchanged)
- Existing connections unaffected (connection-state=new)
- Monitors delta RTT for recovery

**Transition to GOOD:**
- Trigger: delta < 12ms for 15 consecutive samples (30 seconds)
- Action: Disable RouterOS ADAPTIVE rule
- Effect: All new connections return to default routing (Spectrum)

### Traffic Classification (Three Layers)

**Layer 1 - DSCP (Semantic):**
- EF (46) = Highest priority (VoIP, gaming)
- AF31 (26) = Interactive (SSH, small web)
- CS0 (0) = Best effort
- CS1 (8) = Bulk

**Layer 2 - Connection Marks (Control):**
- QOS_HIGH, GAMES, QOS_MEDIUM → LATENCY_SENSITIVE
- QOS_LOW, QOS_NORMAL → NOT marked

**Layer 3 - Address Lists (Overrides):**
- FORCE_OUT_ATT → Always ATT (highest priority, always active)
- auto-games, rtc-high-clients → Automatically classified

**Routing Logic:**
1. FORCE_OUT_ATT addresses → always ATT (rule #0)
2. LATENCY_SENSITIVE traffic → ATT **only when ADAPTIVE rule enabled**
3. Everything else → Spectrum (default)

---

## Testing

### Test 1: Normal Operation
```bash
# Watch logs (should stay in SPECTRUM_GOOD)
ssh kevin@10.10.110.246 'journalctl -u wan-steering.service -f'

# Verify rule is disabled
ssh admin@10.10.99.1 '/ip firewall mangle print where comment~"ADAPTIVE"'
# Should show "disabled=yes" or "X" flag
```

### Test 2: Artificial Degradation
```bash
# Throttle Spectrum to trigger degradation
ssh admin@10.10.99.1 '/queue tree set WAN-Download-Spectrum max-limit=10M'

# Watch for state transition (should happen within 16-30 seconds)
ssh kevin@10.10.110.246 'journalctl -u wan-steering.service -f'
# Look for: "Spectrum DEGRADED detected"

# Verify rule is enabled
ssh admin@10.10.99.1 '/ip firewall mangle print where comment~"ADAPTIVE"'
# Should show "disabled=no" (no X flag)

# Check connections (gaming/VoIP should be routed to ATT)
ssh admin@10.10.99.1 '/ip firewall connection print where connection-mark=LATENCY_SENSITIVE'
```

### Test 3: Recovery
```bash
# Restore Spectrum bandwidth
ssh admin@10.10.99.1 '/queue tree set WAN-Download-Spectrum max-limit=870M'

# Watch for recovery (should happen within 30-60 seconds)
ssh kevin@10.10.110.246 'journalctl -u wan-steering.service -f'
# Look for: "Spectrum RECOVERED"

# Verify rule is disabled again
ssh admin@10.10.99.1 '/ip firewall mangle print where comment~"ADAPTIVE"'
# Should show "disabled=yes" (X flag)
```

### Test 4: Flap Prevention
```bash
# Observe state file during normal operation
watch -n 1 "ssh kevin@10.10.110.246 'cat /home/kevin/adaptive_cake_steering/steering_state.json | jq'"

# Look for:
# - bad_count incrementing but not reaching threshold (8)
# - good_count resetting when spikes occur
# - No state transitions from temporary spikes
```

---

## Troubleshooting

### Daemon Not Running
```bash
ssh kevin@10.10.110.246 'systemctl status wan-steering.timer'
ssh kevin@10.10.110.246 'systemctl status wan-steering.service'
```

### No Baseline RTT
```bash
# Check autorate_continuous state file
ssh kevin@10.10.110.246 'cat /home/kevin/adaptive_cake_spectrum/spectrum_state.json | jq .ewma.baseline_rtt'

# Verify autorate_continuous is running
ssh kevin@10.10.110.246 'systemctl status cake-spectrum-continuous.timer'
```

### RouterOS Rule Not Found
```bash
# Check if rule exists
ssh admin@10.10.99.1 '/ip firewall mangle print where comment~"ADAPTIVE"'

# If not found, re-run add_steering_rules.sh commands
```

### Ping Failures
```bash
# Test ping manually
ssh kevin@10.10.110.246 'ping -c 5 1.1.1.1'

# Check routing (should use Spectrum)
ssh kevin@10.10.110.246 'ip route get 1.1.1.1'
```

---

## Monitoring Commands

### Quick Status Check
```bash
# State machine status
ssh kevin@10.10.110.246 'cat /home/kevin/adaptive_cake_steering/steering_state.json | jq "{state: .current_state, bad_count, good_count, baseline_rtt, last_transition: .last_transition_time}"'

# RouterOS rule status
ssh admin@10.10.99.1 '/ip firewall mangle print stats where comment~"ADAPTIVE"'
```

### Historical Analysis
```bash
# Recent transitions
ssh kevin@10.10.110.246 'cat /home/kevin/adaptive_cake_steering/steering_state.json | jq .transitions'

# RTT history (last 60 samples = 2 minutes)
ssh kevin@10.10.110.246 'cat /home/kevin/adaptive_cake_steering/steering_state.json | jq .history_delta'
```

### DSCP Counters (Validate Traffic Mix)
```bash
# See how much traffic is in each QoS class
ssh admin@10.10.99.1 '/ip firewall mangle print stats where comment~"COUNT DSCP"'

# EF (46) = VoIP/gaming (should be small)
# AF31 (26) = Interactive (should be moderate)
# CS0 (0) = Best effort (should be largest)
# CS1 (8) = Bulk (should be moderate)
```

---

## Next Steps / Future Enhancements

### Phase 2: ATT Capacity Protection
- Read ATT utilization from autorate_continuous state
- Prevent steering if ATT > 80% saturated
- Log warning: "ATT at capacity, cannot offload"

### Phase 3: Shared RTT Measurement
- Steering reads current_rtt from autorate state (no separate ping)
- Saves 3 pings every 2 seconds (negligible, but cleaner)

### Phase 4: Multi-Site Deployment
- Package for dad's fiber line on Raspberry Pi
- Same architecture, different location
- Each site self-contained

### Phase 5: Dashboard
- Flask + charts.js web interface
- Real-time RTT graph
- State transition log
- DSCP traffic breakdown

### Phase 6: Prometheus Metrics
- Export state, transitions, RTT
- Grafana dashboards
- Alerting on frequent transitions

---

## Files Reference

### On Build Machine (/home/kevin/CAKE/)
- `wan_steering_daemon.py` - Main daemon
- `configs/steering_config.yaml` - Configuration
- `systemd/wan-steering.{service,timer}` - Systemd units
- `deploy_steering.sh` - Deployment script
- `add_steering_rules.sh` - RouterOS rule commands
- `STEERING_README.md` - This file
- `/home/kevin/.claude/plans/optimized-mapping-ullman.md` - Full implementation plan

### On cake-spectrum Container (10.10.110.246)
- `/home/kevin/wanctl/wan_steering_daemon.py` - Daemon
- `/home/kevin/wanctl/configs/steering_config.yaml` - Config
- `/home/kevin/adaptive_cake_steering/steering_state.json` - State
- `/home/kevin/wanctl/logs/steering.log` - Main log
- `/home/kevin/wanctl/logs/steering_debug.log` - Debug log
- `/tmp/wanctl_steering.lock` - Lock file

### On RouterOS (10.10.99.1)
- Mangle rules: LATENCY_SENSITIVE translation + ADAPTIVE steering

---

## Success Criteria

✅ Daemon runs continuously (every 2s) without crashes
✅ State transitions occur within expected windows (16-30s → DEGRADED, 30-60s → GOOD)
✅ No route flapping (hysteresis works)
✅ Latency-sensitive traffic moves to ATT when Spectrum degrades
✅ Bulk traffic never moves to ATT
✅ Existing connections preserved during transitions
✅ ATT bandwidth protected (CAKE prevents saturation)
✅ Logs show clear decision rationale

---

**Created:** 2025-12-12
**Architecture:** Colocated with autorate_continuous on cake-spectrum
**Purpose:** Zero-latency adaptive dual-WAN steering
