# Multi-WAN Steering

This document describes the optional WAN steering feature for multi-WAN setups.

## Overview

The steering daemon monitors your primary WAN for congestion and automatically routes latency-sensitive traffic to an alternate WAN when needed.

**Use case:** You have a fast-but-sometimes-congested primary WAN (cable) and a slower-but-stable backup WAN (DSL). During congestion on the primary, VoIP/gaming traffic routes to the backup for better latency.

## How It Works

The steering daemon runs continuously with a 50ms cycle (configurable):

1. **Collect signals** from primary WAN:
   - RTT delta from autorate baseline state
   - Current RTT from the primary autorate health endpoint when available
   - CAKE drops (from RouterOS queue stats)
   - Queue depth (from RouterOS queue stats)

2. **Assess congestion** using multi-signal voting:
   - GREEN: All signals healthy
   - YELLOW: Early warning (1 signal elevated)
   - RED: Confirmed congestion (2+ signals elevated, or drops > 0)

3. **Apply hysteresis:**
   - RED requires 2 consecutive samples (4 seconds) to enable steering
   - GREEN requires 15 consecutive samples (30 seconds) to disable

4. **Control mangle rule** via REST API (or SSH):
   - RED: Enable steering rule
   - GREEN: Disable steering rule

The daemon includes systemd watchdog integration for automatic recovery from hangs.

## RTT Source Contract

Steering now prefers the colocated autorate daemon's live ICMP measurement feed
instead of running an independent steady-state ping loop.

- Autorate publishes the current direct-ICMP snapshot in the WAN `/health` payload
  under `wans[].measurement`
- Steering reads that live RTT from the primary WAN health endpoint derived from
  `topology.primary_wan_config`
- If the autorate measurement is missing or stale, steering falls back to its
  existing self-probe path

This keeps steering aligned with the same reflector set autorate is already
using and avoids duplicate probe noise during congestion investigations.

## Traffic Classification

**Steered to alternate WAN (latency-sensitive):**

- VoIP/SIP traffic
- Gaming (common ports)
- DNS queries
- SSH/RDP
- Push notifications
- Small HTTP requests

**Stays on primary WAN (bulk):**

- Large downloads
- Video streaming
- Background updates
- Bulk uploads

Classification is done via RouterOS mangle rules using:

- DSCP marking (EF, AF31)
- Port-based matching
- Packet size heuristics
- Connection tracking (only NEW connections are steered)

## Configuration

### Steering Config (`/etc/wanctl/steering.yaml`)

```yaml
# Which WANs to monitor and steer between
topology:
  primary_wan: "wan1"
  primary_wan_config: "/etc/wanctl/wan1.yaml"
  alternate_wan: "wan2"

# Router connection
router:
  host: "192.168.1.1"
  user: "admin"
  ssh_key: "/etc/wanctl/ssh/router.key"

  # Mangle rule comment (must match your RouterOS config)
  steering_rule_comment: "ADAPTIVE: Steer latency-sensitive to WAN2"

# Congestion thresholds
thresholds:
  green_rtt_ms: 5
  yellow_rtt_ms: 15
  red_rtt_ms: 15
  min_drops_red: 1
  min_queue_yellow: 10
  min_queue_red: 50
  red_samples_required: 2
  green_samples_required: 15

# CAKE queue to monitor
cake_queue: "WAN-Download-1"
```

### RouterOS Mangle Rule

Create a mangle rule on your router that marks traffic for steering:

```routeros
/ip firewall mangle add chain=prerouting \
    comment="ADAPTIVE: Steer latency-sensitive to WAN2" \
    disabled=yes \
    connection-state=new \
    dscp=ef,af31 \
    action=mark-routing new-routing-mark=via-wan2
```

The steering daemon enables/disables this rule based on congestion state.

## Enabling Steering

```bash
# Copy config
sudo cp configs/examples/steering.yaml.example /etc/wanctl/steering.yaml
sudo nano /etc/wanctl/steering.yaml

# Enable service
sudo systemctl enable --now steering.service
```

## Monitoring

```bash
# Service status
systemctl status steering.service

# Live logs (journalctl)
journalctl -u steering.service -f

# Or via log files
tail -f /var/log/wanctl/steering.log

# Current state
cat /var/lib/wanctl/steering_state.json
```

**Healthy output:**

```
[WAN1_GOOD] rtt=0.0ms ewma=0.1ms drops=0 q=0 | congestion=GREEN
```

**During congestion:**

```
[WAN1_DEGRADED] rtt=45.2ms ewma=38.5ms drops=12 q=85 | congestion=RED
Enabling steering rule: ADAPTIVE: Steer latency-sensitive to WAN2
```

## Design Principles

### Never Reroute Mid-Flow

Steering only affects NEW connections. Existing flows continue on their original path. This prevents:

- TCP sequence number issues
- VoIP call drops
- Game disconnections

### Autorate is Primary

The steering daemon defers to autorate for congestion control. Steering is a secondary override that only activates when autorate cannot maintain acceptable latency.

The SOFT_RED state in autorate handles RTT-only congestion without triggering steering, reducing false positives by ~85%.

### Multi-Signal Reduces False Positives

Single-signal detection (RTT only) produces false positives from "internet weather" (route changes, reflector issues). Multi-signal voting requires agreement:

- RTT spike + no drops = probably internet weather (no steering)
- RTT spike + drops = definitely congested (enable steering)
- Drops alone = definitely congested (enable steering)

### Hysteresis Prevents Flapping

Without hysteresis, steering would rapidly toggle during marginal conditions. The required consecutive samples (2 for RED, 15 for GREEN) ensure:

- Fast response to confirmed congestion (4 seconds)
- Slow return to normal (30 seconds)
- Stable operation during borderline conditions

## Confidence-Based Steering

Confidence scoring replaces the binary RED-triggers-steer model with a multi-signal weighted scoring system (0-100 scale). Signals include RTT delta, CAKE drops, queue depth, and WAN-aware zone data. Each signal contributes a weighted score, and steering activates only when the combined confidence exceeds the configured threshold.

**Current mode:** LIVE (`dry_run: false`) -- confidence decisions actively route traffic.

### How Confidence Scoring Works

1. Each cycle, signals are collected and scored:
   - RTT delta above threshold adds weight
   - CAKE drops above zero add weight
   - Queue depth above threshold adds weight
   - WAN zone RED/SOFT_RED adds configurable weight (if WAN-aware enabled)
2. Scores are summed into a confidence value (0-100)
3. Steering activates when confidence exceeds `steer_threshold` (default: 55)
4. Steering recovers when confidence drops below `recovery_threshold` (default: 20)
5. Sustain timers prevent flapping (degrade: 2s, recovery: 3s)

### SIGUSR1 Hot-Reload

The steering daemon supports hot-reload of `dry_run` and `wan_state.enabled` via SIGUSR1. This allows toggling between live/dry-run mode and enabling/disabling WAN-aware steering without restarting the daemon.

**Note:** SIGUSR1 reloads `dry_run` and `wan_state.enabled` only. All other config changes require a daemon restart.

### Rollback to Dry-Run Mode

To revert confidence steering to log-only mode without restarting the daemon:

1. Edit the steering config:

   ```bash
   ssh cake-spectrum 'sudo sed -i "s/dry_run: false/dry_run: true/" /etc/wanctl/steering.yaml'
   ```

2. Send SIGUSR1 to reload:

   ```bash
   ssh cake-spectrum 'sudo kill -USR1 $(pgrep -f "steering.*--config")'
   ```

3. Verify via health endpoint:
   ```bash
   ssh cake-spectrum 'curl -s http://127.0.0.1:9102/health | python3 -m json.tool | grep mode'
   # Should show: "mode": "dry_run"
   ```

To re-enable live mode:

1. Edit: set `dry_run: false`

   ```bash
   ssh cake-spectrum 'sudo sed -i "s/dry_run: true/dry_run: false/" /etc/wanctl/steering.yaml'
   ```

2. Send SIGUSR1:

   ```bash
   ssh cake-spectrum 'sudo kill -USR1 $(pgrep -f "steering.*--config")'
   ```

3. Verify: health endpoint shows `"mode": "active"`
   ```bash
   ssh cake-spectrum 'curl -s http://127.0.0.1:9102/health | python3 -m json.tool | grep mode'
   # Should show: "mode": "active"
   ```

## WAN-Aware Steering

WAN zone data from autorate fuses into confidence scoring. When enabled, WAN RED and SOFT_RED congestion zones add configurable weight to the confidence score, allowing the steering daemon to factor in WAN-level congestion signals. WAN-aware steering ships disabled by default (`wan_state.enabled: false` in the example config) and must be explicitly enabled.

### Enabling WAN-Aware Steering

1. Edit the steering config -- uncomment the `wan_state` section and set `enabled: true`:

   ```bash
   ssh cake-spectrum 'sudo nano /etc/wanctl/steering.yaml'
   # Set: wan_state.enabled: true
   ```

2. Send SIGUSR1 to reload without restart:

   ```bash
   ssh cake-spectrum 'sudo kill -USR1 $(pgrep -f "steering.*--config")'
   ```

3. Verify via health endpoint:

   ```bash
   ssh cake-spectrum 'curl -s http://127.0.0.1:9102/health | python3 -m json.tool | grep -A5 wan_awareness'
   # Should show: "enabled": true
   ```

**Note:** A 30-second grace period activates on enable. During this window, the WAN zone signal is ignored while the system ramps up safely.

### Rollback (Disable WAN-Aware Steering)

To disable WAN-aware steering without restarting the daemon:

```bash
# 1. Set enabled to false in config
ssh cake-spectrum 'sudo sed -i "s/enabled: true/enabled: false/" /etc/wanctl/steering.yaml'

# 2. Send SIGUSR1 to reload
ssh cake-spectrum 'sudo kill -USR1 $(pgrep -f "steering.*--config")'

# 3. Verify via health endpoint
ssh cake-spectrum 'curl -s http://127.0.0.1:9102/health | python3 -m json.tool | grep -A5 wan_awareness'
# Should show: "enabled": false
```

### Degradation Validation Runbook

Step-by-step procedures to validate WAN-aware steering degrades safely under failure conditions.

#### Stale Zone Fallback

When autorate stops writing state, the WAN zone becomes stale and its confidence contribution drops to zero.

```bash
# 1. Note current state
ssh cake-spectrum 'curl -s http://127.0.0.1:9102/health | python3 -m json.tool | grep -A10 wan_awareness'

# 2. Stop autorate (creates stale zone condition)
ssh cake-spectrum 'sudo systemctl stop wanctl@spectrum'

# 3. Wait for staleness threshold (default 5 seconds)
sleep 10

# 4. Check health -- stale=true, confidence_contribution=0
ssh cake-spectrum 'curl -s http://127.0.0.1:9102/health | python3 -m json.tool | grep -A10 wan_awareness'
# Expected: "stale": true, "confidence_contribution": 0

# 5. Restart autorate
ssh cake-spectrum 'sudo systemctl start wanctl@spectrum'
```

#### Autorate Unavailable (No State File)

When the autorate state file is missing, the WAN zone reads as null and contributes zero weight.

```bash
# 1. Rename state file
ssh cake-spectrum 'sudo mv /run/wanctl/spectrum_state.json /run/wanctl/spectrum_state.json.bak'

# 2. Wait a few cycles
sleep 3

# 3. Check health -- zone should be null, confidence_contribution=0
ssh cake-spectrum 'curl -s http://127.0.0.1:9102/health | python3 -m json.tool | grep -A10 wan_awareness'
# Expected: "zone": null, "confidence_contribution": 0

# 4. Restore state file
ssh cake-spectrum 'sudo mv /run/wanctl/spectrum_state.json.bak /run/wanctl/spectrum_state.json'
```

### Configuration Parameters

| Parameter                           | Default | Description                                       |
| ----------------------------------- | ------- | ------------------------------------------------- |
| `wan_state.enabled`                 | `false` | Enable WAN zone signal in confidence scoring      |
| `wan_state.grace_period_sec`        | `30`    | Seconds to ignore WAN signal after enable/startup |
| `wan_state.red_weight`              | `25`    | Confidence weight added when WAN zone is RED      |
| `wan_state.soft_red_weight`         | `12`    | Confidence weight added when WAN zone is SOFT_RED |
| `wan_state.staleness_threshold_sec` | `5`     | Seconds before stale zone falls back to zero      |

## Troubleshooting

### Steering Not Activating

1. Check steering service is running
2. Verify autorate state file exists and is readable
3. Check CAKE queue stats are being collected
4. Verify mangle rule exists with correct comment

### Steering Activating Too Often

1. Raise thresholds in steering config
2. Ensure autorate SOFT_RED state is configured
3. Check for persistent network issues
4. Review logs for pattern

### Traffic Not Being Steered

1. Verify mangle rule is enabled (check with `/ip firewall mangle print`)
2. Check routing marks are configured
3. Verify traffic classification matches your traffic
4. Check connection-state=new is working
