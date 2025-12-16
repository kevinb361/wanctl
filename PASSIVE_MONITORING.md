# Passive Queue Monitoring

## What It Does

Passive monitoring adds lightweight queue health checks that run **between** active tests without disrupting traffic.

### How It Works

```
Active Test:   [═══════]         [═══════]         [═══════]
               (50 sec)          (50 sec)          (50 sec)
               Every 10 min      Every 10 min      Every 10 min

Passive Check: ·····█···█···█···█···█···█···█···█···█···█···
                    Every 2 minutes (quick check)
```

**Active Test** (10 minutes):
- Saturates link with netperf
- Measures bloat under load
- Takes ~50 seconds
- Adjusts CAKE bandwidth

**Passive Monitor** (2 minutes):
- Queries CAKE queue statistics
- Checks drop rate, backlog, delays
- Takes <1 second (SSH query only)
- Logs warnings if issues detected
- **Does NOT adjust CAKE** - just monitors

## What It Monitors

The passive monitor checks CAKE queue statistics via RouterOS:

```python
# For each queue (download/upload):
- Packets sent/dropped
- Drop rate percentage
- Queue backlog (packets waiting)
- Queue delay estimate
- Overlimit events
```

**Health Thresholds** (configurable in YAML):
- Drop rate > 1% → Warning logged
- Queue delay > 10ms → Warning logged
- Excessive overlimits → Warning logged

## Benefits

1. **Early Detection**: Spot queue issues between active tests
2. **No Network Impact**: Just reads statistics (no traffic generated)
3. **Fast**: Completes in <1 second
4. **Complementary**: Works alongside active testing

## Limitations

**Important**: RouterOS (Mikrotik) may not fully support `tc` (Linux traffic control) commands.

The passive monitor attempts to use:
```bash
tc -s qdisc show dev <interface>
```

If this fails (likely on RouterOS), you'll see:
```
WARNING: Could not retrieve queue statistics (RouterOS may not support tc)
```

This is **normal** - the passive monitor is most effective on:
- Linux-based routers (OpenWrt, pfSense, etc.)
- Systems with native `tc` support

On RouterOS, the active tests remain your primary monitoring method.

## Installation

### 1. Deploy Files

```bash
cd /home/kevin/CAKE

# Copy to containers
scp passive_monitor.py configs/*.yaml kevin@10.10.110.247:/home/kevin/fusion_cake/
scp passive_monitor.py configs/*.yaml kevin@10.10.110.246:/home/kevin/fusion_cake/

# Copy systemd units
scp systemd/cake-*-passive.{service,timer} kevin@10.10.110.247:/tmp/
scp systemd/cake-*-passive.{service,timer} kevin@10.10.110.246:/tmp/
```

### 2. Install on ATT Container

```bash
ssh kevin@10.10.110.247
sudo mv /tmp/cake-att-passive.* /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now cake-att-passive.timer
systemctl list-timers cake-*
exit
```

### 3. Install on Spectrum Container

```bash
ssh kevin@10.10.110.246
sudo mv /tmp/cake-spectrum-passive.* /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now cake-spectrum-passive.timer
systemctl list-timers cake-*
exit
```

### 4. Test Manually First

```bash
# On ATT container
ssh kevin@10.10.110.247
cd /home/kevin/fusion_cake
python3 passive_monitor.py --config configs/att_config.yaml --verbose
```

Expected output if RouterOS doesn't support tc:
```
WARNING: Could not retrieve queue statistics (RouterOS may not support tc)
INFO: Passive monitoring works best on Linux-based routers with tc support
```

This is fine - you can still run it, but it won't provide useful data on RouterOS.

## Configuration

In `configs/att_config.yaml` and `configs/spectrum_config.yaml`:

```yaml
passive_monitoring:
  enabled: true
  queue_delay_threshold_ms: 10      # Alert if queue delay > 10ms
  drop_rate_threshold_percent: 1.0  # Alert if drop rate > 1%
  alert_on_issues: true              # Log warnings when issues detected
```

Adjust thresholds based on your tolerance for latency/drops.

## Monitoring

### View Passive Monitor Logs

```bash
# ATT
ssh kevin@10.10.110.247 'tail -f /home/kevin/fusion_cake/logs/cake_passive.log'

# Spectrum
ssh kevin@10.10.110.246 'tail -f /home/kevin/fusion_cake/logs/cake_passive.log'
```

### Check Timer Status

```bash
ssh kevin@10.10.110.247 'systemctl list-timers cake-*-passive*'
```

### Systemd Journal

```bash
ssh kevin@10.10.110.247 'journalctl -u cake-att-passive.service -f'
```

## Timing Schedule

With both active and passive monitoring:

```
Time    ATT           Spectrum
:00     Active Test
:01     Passive
:02                   Passive
:03     Passive
:04                   Passive
:05     Passive
:06                   Passive
:07                   Active Test
:08     Passive
:09                   Passive
:10     Active Test
:11     Passive
:12                   Passive
...
```

- **Active tests**: Every 10 minutes (ATT at :02, :12, :22; Spectrum at :07, :17, :27)
- **Passive checks**: Every 2 minutes (1 minute offset between WANs)
- **Total monitoring frequency**: Every ~1 minute one of the four monitors runs

## Disabling Passive Monitoring

If it's not working on your RouterOS setup or you want to disable it:

```bash
# Stop and disable timers
sudo systemctl stop cake-att-passive.timer
sudo systemctl disable cake-att-passive.timer
sudo systemctl stop cake-spectrum-passive.timer
sudo systemctl disable cake-spectrum-passive.timer
```

The active monitoring will continue working normally.

## Future Enhancement

If you migrate to a Linux-based router (OpenWrt, pfSense, etc.) with full `tc` support, the passive monitor will automatically start providing useful queue statistics.

No code changes needed - just works when `tc` commands succeed.

## Summary

| Feature | Active Test | Passive Monitor |
|---------|-------------|-----------------|
| **Frequency** | 10 minutes | 2 minutes |
| **Duration** | ~50 seconds | <1 second |
| **Network Impact** | Saturates link | None (just queries) |
| **What It Does** | Measures bloat, adjusts CAKE | Checks queue health, logs warnings |
| **RouterOS Support** | ✅ Full | ⚠️ Limited (may not work) |
| **Linux Router Support** | ✅ Full | ✅ Full |

Passive monitoring is a **bonus feature** that enhances your system when available, but the active tests remain the core functionality.
