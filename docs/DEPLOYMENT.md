# Adaptive CAKE Deployment Instructions

## Quick Deployment (Automated)

```bash
cd /path/to/wanctl
./scripts/deploy.sh <wan_name> <target_host>
```

This will automatically deploy and enable all timers on the target container.

---

## Manual Deployment

### For Primary WAN Container

```bash
# Copy files to target (adjust hostname/IP for your setup)
scp wanctl@<wan1-host>.service wanctl@<wan1-host>.timer user@<wan1-host>:/tmp/

# SSH into container
ssh user@<wan1-host>

# Install units
sudo mv /tmp/wanctl@*.service /tmp/wanctl@*.timer /etc/systemd/system/
sudo systemctl daemon-reload

# Enable and start timers
sudo systemctl enable wanctl@wan1.timer
sudo systemctl enable wanctl@wan1-reset.timer
sudo systemctl start wanctl@wan1.timer
sudo systemctl start wanctl@wan1-reset.timer

# Verify
systemctl list-timers wanctl@*
```

### For Secondary WAN Container (Dual-WAN Setup)

```bash
# Copy files to target
scp wanctl@<wan2-host>.service wanctl@<wan2-host>.timer user@<wan2-host>:/tmp/

# SSH into container
ssh user@<wan2-host>

# Install units
sudo mv /tmp/wanctl@*.service /tmp/wanctl@*.timer /etc/systemd/system/
sudo systemctl daemon-reload

# Enable and start timers
sudo systemctl enable wanctl@wan2.timer
sudo systemctl enable wanctl@wan2-reset.timer
sudo systemctl start wanctl@wan2.timer
sudo systemctl start wanctl@wan2-reset.timer

# Verify
systemctl list-timers wanctl@*
```

---

## Timer Schedule

### Regular Tests (Every 10 minutes)
- **WAN1**: Starts 2 min after boot, then every 10 minutes
- **WAN2**: Starts 7 min after boot, then every 10 minutes
- **Offset**: 5 minutes between tests to prevent interference

### Nightly Resets (Twice Daily)
- **Both WANs**: 3:00 AM and 3:00 PM
- Clears EWMA state and unshapes queues to prevent drift

---

## Monitoring

### View Timer Status
```bash
# On target container
ssh user@<wan-host> 'systemctl list-timers wanctl@*'
```

### View Live Logs
```bash
# WAN1 logs
ssh user@<wan1-host> 'journalctl -u wanctl@wan1.service -f'

# WAN2 logs
ssh user@<wan2-host> 'journalctl -u wanctl@wan2.service -f'
```

### View Historical Logs
```bash
# Last 50 entries
ssh user@<wan-host> 'journalctl -u wanctl@wan1.service -n 50'

# Since yesterday
ssh user@<wan-host> 'journalctl -u wanctl@wan1.service --since yesterday'
```

### Check Log Files
```bash
# Main log
ssh user@<wan-host> 'tail -f /var/log/wanctl/continuous.log'

# Debug log (if --debug was used)
ssh user@<wan-host> 'tail -f /var/log/wanctl/continuous_debug.log'
```

---

## Troubleshooting

### Service Not Running
```bash
# Check service status
systemctl status wanctl@wan1.service

# Check timer status
systemctl status wanctl@wan1.timer

# View recent errors
journalctl -u wanctl@wan1.service --since "10 minutes ago"
```

### Manual Test Run
```bash
# On target container
cd /opt/wanctl
python3 -m cake.autorate_continuous --config /etc/wanctl/wan1.yaml --debug
```

### Reset State Manually
```bash
# On target container
python3 -m cake.autorate_continuous --config /etc/wanctl/wan1.yaml --reset
```

### Stop Timers Temporarily
```bash
# Stop without disabling (will restart after reboot)
sudo systemctl stop wanctl@wan1.timer

# Stop and disable (won't restart after reboot)
sudo systemctl disable --now wanctl@wan1.timer
```

### Re-enable After Stopping
```bash
sudo systemctl enable --now wanctl@wan1.timer
```

---

## Files Created

### Per-WAN Container
- `/etc/systemd/system/wanctl@.service` - Main service template
- `/etc/systemd/system/wanctl@.timer` - 10-minute timer template
- `/etc/systemd/system/wanctl@-reset.service` - Reset service template
- `/etc/systemd/system/wanctl@-reset.timer` - Twice-daily reset timer

### Configuration
- `/etc/wanctl/<wan_name>.yaml` - WAN-specific configuration

### State Files
- `/var/lib/wanctl/<wan_name>_state.json` - Persisted EWMA state

---

## Expected Behavior

1. **First Run**: Scripts will measure throughput and establish baseline EWMA values
2. **Convergence**: Over 30-60 minutes, EWMA will stabilize around true capacity
3. **Steady State**: CAKE limits adjust automatically based on measured conditions
4. **Under Load**: Bandwidth reduces when latency increases
5. **Idle**: Limits increase gradually when headroom available
6. **Reset**: Twice daily, state clears and queues unshaped to prevent drift

## Performance Expectations

- **Test Duration**: ~20 seconds per WAN
- **Overhead**: <1% of time spent testing
- **Response Time**: Adjustments within 30-60 minutes of condition change
- **Stability**: Rate-of-change limited to prevent wild swings
- **Safety**: Health checks reject implausible measurements
