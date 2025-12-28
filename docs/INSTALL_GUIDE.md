# Installation Guide - No Root SSH

Since the containers don't allow root SSH access, installation is a simple 3-step process:

## Step 1: Deploy Files to Containers

From your build machine, run:

```bash
cd /home/kevin/CAKE
./deploy_refactored.sh
```

This copies:
- Script and configs to `/home/kevin/wanctl/`
- Systemd units to `/tmp/`
- Install scripts to `/tmp/`

## Step 2: Install on ATT Container

SSH into ATT container and run installation script:

```bash
# From build machine, copy install script
scp container_cleanup.sh container_install_att.sh kevin@10.10.110.247:/tmp/

# SSH to ATT container
ssh kevin@10.10.110.247

# Become root (use su or sudo depending on your setup)
su -
# or
sudo -i

# Cleanup old services
bash /tmp/container_cleanup.sh

# Install new services
bash /tmp/container_install_att.sh

# Exit root
exit

# Verify timers are running
systemctl list-timers cake-*

# Watch first run (optional)
tail -f /home/kevin/wanctl/logs/cake_auto.log
```

## Step 3: Install on Spectrum Container

SSH into Spectrum container and run installation script:

```bash
# From build machine, copy install script
scp container_cleanup.sh container_install_spectrum.sh kevin@10.10.110.246:/tmp/

# SSH to Spectrum container
ssh kevin@10.10.110.246

# Become root (use su or sudo depending on your setup)
su -
# or
sudo -i

# Cleanup old services
bash /tmp/container_cleanup.sh

# Install new services (includes Python dependency installation)
bash /tmp/container_install_spectrum.sh

# Exit root
exit

# Verify timers are running
systemctl list-timers cake-*

# Watch first run (optional)
tail -f /home/kevin/wanctl/logs/cake_auto.log
```

---

## Alternative: Manual Commands

If you prefer to run commands manually instead of using scripts:

### On ATT Container (as root):

```bash
# Cleanup
systemctl stop cake-*.timer cake-*.service
systemctl disable cake-*.timer cake-*.service
rm -f /etc/systemd/system/cake-*.service /etc/systemd/system/cake-*.timer
systemctl daemon-reload

# Install
mv /tmp/cake-att*.service /tmp/cake-att*.timer /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now cake-att.timer cake-att-reset.timer
systemctl list-timers cake-*
```

### On Spectrum Container (as root):

```bash
# Install dependencies
apt update && apt install -y python3-pexpect python3-yaml

# Cleanup
systemctl stop cake-*.timer cake-*.service
systemctl disable cake-*.timer cake-*.service
rm -f /etc/systemd/system/cake-*.service /etc/systemd/system/cake-*.timer
systemctl daemon-reload

# Install
mv /tmp/cake-spectrum*.service /tmp/cake-spectrum*.timer /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now cake-spectrum.timer cake-spectrum-reset.timer
systemctl list-timers cake-*
```

---

## Verification

After installation on both containers, verify:

```bash
# Check timer schedule (next run times)
ssh kevin@10.10.110.247 'systemctl list-timers cake-*'
ssh kevin@10.10.110.246 'systemctl list-timers cake-*'

# Watch logs in real-time
ssh kevin@10.10.110.247 'tail -f /home/kevin/wanctl/logs/cake_auto.log'
ssh kevin@10.10.110.246 'tail -f /home/kevin/wanctl/logs/cake_auto.log'

# Check state files (after first run)
ssh kevin@10.10.110.247 'cat /home/kevin/wanctl/att_state.json'
ssh kevin@10.10.110.246 'cat /home/kevin/wanctl/spectrum_state.json'

# View systemd journal
ssh kevin@10.10.110.247 'journalctl -u cake-att.service -n 50'
ssh kevin@10.10.110.246 'journalctl -u cake-spectrum.service -n 50'
```

---

## Expected Timeline

- **First run**: Starts 2 min (ATT) / 7 min (Spectrum) after enabling timers
- **Convergence**: 60-120 minutes for EWMA to stabilize
- **Steady state**: Adjustments every 10 minutes based on conditions
- **Resets**: Twice daily at 3:00 AM and 3:00 PM

---

## Troubleshooting

### Timers not starting
```bash
systemctl status cake-att.timer
journalctl -u cake-att.timer
```

### Script errors
```bash
journalctl -u cake-att.service -n 50
tail /home/kevin/wanctl/logs/cake_auto.log
```

### Manual test
```bash
cd /home/kevin/wanctl
python3 adaptive_cake.py --config configs/att_config.yaml --debug
```

### Dependencies missing
```bash
python3 -c "import yaml; import pexpect"
# If fails: apt install python3-pexpect python3-yaml
```

---

## Quick Reference

| Container | IP | Offset | Config |
|-----------|---------|--------|--------|
| ATT | 10.10.110.247 | :02, :12, :22... | `/home/kevin/wanctl/configs/att_config.yaml` |
| Spectrum | 10.10.110.246 | :07, :17, :27... | `/home/kevin/wanctl/configs/spectrum_config.yaml` |
