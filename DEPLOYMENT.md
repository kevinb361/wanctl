# Adaptive CAKE Deployment Instructions

## Quick Deployment (Automated)

```bash
cd /home/kevin/CAKE
./deploy.sh
```

This will automatically deploy and enable all timers on both containers.

---

## Manual Deployment

### For ATT Container (10.10.110.247)

```bash
# Copy files
scp cake-att*.service cake-att*.timer kevin@10.10.110.247:/tmp/

# SSH into container
ssh kevin@10.10.110.247

# Install units
sudo mv /tmp/cake-att*.service /tmp/cake-att*.timer /etc/systemd/system/
sudo systemctl daemon-reload

# Enable and start timers
sudo systemctl enable cake-att.timer
sudo systemctl enable cake-att-reset.timer
sudo systemctl start cake-att.timer
sudo systemctl start cake-att-reset.timer

# Verify
systemctl list-timers cake-*
```

### For Spectrum Container (10.10.110.246)

```bash
# Copy files
scp cake-spectrum*.service cake-spectrum*.timer kevin@10.10.110.246:/tmp/

# SSH into container
ssh kevin@10.10.110.246

# Install units
sudo mv /tmp/cake-spectrum*.service /tmp/cake-spectrum*.timer /etc/systemd/system/
sudo systemctl daemon-reload

# Enable and start timers
sudo systemctl enable cake-spectrum.timer
sudo systemctl enable cake-spectrum-reset.timer
sudo systemctl start cake-spectrum.timer
sudo systemctl start cake-spectrum-reset.timer

# Verify
systemctl list-timers cake-*
```

---

## Timer Schedule

### Regular Tests (Every 10 minutes)
- **ATT**: Starts 2 min after boot, then every 10 minutes (e.g., :00, :10, :20, :30...)
- **Spectrum**: Starts 7 min after boot, then every 10 minutes (e.g., :05, :15, :25, :35...)
- **Offset**: 5 minutes between tests to prevent interference

### Nightly Resets (Twice Daily)
- **Both WANs**: 3:00 AM and 3:00 PM
- Clears EWMA state and unshapes queues to prevent drift

---

## Monitoring

### View Timer Status
```bash
# On ATT container
ssh kevin@10.10.110.247 'systemctl list-timers cake-*'

# On Spectrum container
ssh kevin@10.10.110.246 'systemctl list-timers cake-*'
```

### View Live Logs
```bash
# ATT logs
ssh kevin@10.10.110.247 'journalctl -u cake-att.service -f'

# Spectrum logs
ssh kevin@10.10.110.246 'journalctl -u cake-spectrum.service -f'
```

### View Historical Logs
```bash
# Last 50 entries
ssh kevin@10.10.110.247 'journalctl -u cake-att.service -n 50'

# Since yesterday
ssh kevin@10.10.110.247 'journalctl -u cake-att.service --since yesterday'
```

### Check Log Files (from scripts)
```bash
# Main log
ssh kevin@10.10.110.247 'tail -f /var/log/cake_auto.log'

# Debug log (if --debug was used)
ssh kevin@10.10.110.247 'tail -f /var/log/cake_auto_debug.log'
```

---

## Troubleshooting

### Service Not Running
```bash
# Check service status
systemctl status cake-att.service

# Check timer status
systemctl status cake-att.timer

# View recent errors
journalctl -u cake-att.service --since "10 minutes ago"
```

### Manual Test Run
```bash
# On ATT container
cd ~/adaptive_cake_att
python3 adaptive_cake_att.py --debug

# On Spectrum container
cd ~/adaptive_cake_spectrum
python3 adaptive_cake_spectrum.py --debug
```

### Reset State Manually
```bash
# On either container
cd ~/adaptive_cake_<isp>
python3 adaptive_cake_<isp>.py --reset
```

### Stop Timers Temporarily
```bash
# Stop without disabling (will restart after reboot)
sudo systemctl stop cake-att.timer

# Stop and disable (won't restart after reboot)
sudo systemctl disable --now cake-att.timer
```

### Re-enable After Stopping
```bash
sudo systemctl enable --now cake-att.timer
```

---

## Files Created

### ATT Container
- `/etc/systemd/system/cake-att.service` - Main service
- `/etc/systemd/system/cake-att.timer` - 10-minute timer
- `/etc/systemd/system/cake-att-reset.service` - Reset service
- `/etc/systemd/system/cake-att-reset.timer` - Twice-daily reset timer

### Spectrum Container
- `/etc/systemd/system/cake-spectrum.service` - Main service
- `/etc/systemd/system/cake-spectrum.timer` - 10-minute timer (offset +5min)
- `/etc/systemd/system/cake-spectrum-reset.service` - Reset service
- `/etc/systemd/system/cake-spectrum-reset.timer` - Twice-daily reset timer

---

## Expected Behavior

1. **First Run**: Scripts will measure throughput and establish baseline EWMA values
2. **Convergence**: Over 30-60 minutes, EWMA will stabilize around true capacity
3. **Steady State**: CAKE limits adjust automatically based on measured conditions
4. **Under Load**: k-factor reduces limits when latency increases
5. **Idle**: Limits increase gradually when headroom available
6. **Reset**: Twice daily, state clears and queues unshaped to prevent drift

## Performance Expectations

- **Test Duration**: ~20 seconds per WAN
- **Overhead**: <1% of time spent testing
- **Response Time**: Adjustments within 30-60 minutes of condition change
- **Stability**: Rate-of-change limited to prevent wild swings
- **Safety**: Health checks reject implausible measurements
