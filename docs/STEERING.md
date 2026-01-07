# Multi-WAN Steering

This document describes the optional WAN steering feature for multi-WAN setups.

## Overview

The steering daemon monitors your primary WAN for congestion and automatically routes latency-sensitive traffic to an alternate WAN when needed.

**Use case:** You have a fast-but-sometimes-congested primary WAN (cable) and a slower-but-stable backup WAN (DSL). During congestion on the primary, VoIP/gaming traffic routes to the backup for better latency.

## How It Works

Every 2 seconds:

1. **Collect signals** from primary WAN:
   - RTT delta (from autorate state file)
   - CAKE drops (from RouterOS queue stats)
   - Queue depth (from RouterOS queue stats)

2. **Assess congestion** using multi-signal voting:
   - GREEN: All signals healthy
   - YELLOW: Early warning (1 signal elevated)
   - RED: Confirmed congestion (2+ signals elevated, or drops > 0)

3. **Apply hysteresis:**
   - RED requires 2 consecutive samples (4 seconds) to enable steering
   - GREEN requires 15 consecutive samples (30 seconds) to disable

4. **Control mangle rule** via SSH:
   - RED: Enable steering rule
   - GREEN: Disable steering rule

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
sudo systemctl enable --now steering.timer
```

## Monitoring

```bash
# Service status
systemctl status steering.timer

# Live logs
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
