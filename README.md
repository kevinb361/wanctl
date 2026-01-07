# Adaptive CAKE Auto-Tuning System

Production-grade bufferbloat elimination system for dual-WAN MikroTik routers with intelligent traffic steering.

## Features

- ✅ **Continuous RTT Monitoring** - Real-time latency tracking (2-second cycles)
- ✅ **Phase 2A State Machine** - 4-state download control (GREEN/YELLOW/SOFT_RED/RED)
- ✅ **Adaptive WAN Steering** - Routes latency-sensitive traffic to healthiest WAN
- ✅ **CAKE-Aware Architecture** - Multi-signal congestion detection (RTT + drops + queue depth)
- ✅ **Unified Codebase** - Same code on both containers, different configs
- ✅ **Backward Compatible** - Supports both legacy (3-state) and Phase 2A (4-state) configs
- ✅ **Near-Zero Latency** - Typical operation: GREEN/GREEN state, <3ms delta RTT
- ✅ **Validated Production** - 18+ days continuous operation, 89% GREEN uptime

## Architecture

```
┌─────────────────────────────────────────────┐
│  MikroTik rb5009 Router (10.10.99.1)       │
│  - ATT VDSL (85/16 Mbps)                   │
│  - Spectrum Cable (900/38 Mbps)            │
│  - CAKE queues for bufferbloat elimination │
└─────────────────────────────────────────────┘
              ▲
              │ SSH (RouterOS commands)
              │
┌─────────────┴──────────────┬────────────────┐
│  ATT Container             │  Spectrum Container
│  (10.10.110.247)           │  (10.10.110.246)
│                            │
│  autorate_continuous.py    │  autorate_continuous.py
│  ├─ 3-state config         │  ├─ 4-state config (Phase 2A)
│  ├─ Legacy floor format    │  ├─ State-based floors
│  └─ Every 2 seconds        │  └─ Every 2 seconds
│                            │
│                            │  wan_steering_daemon.py
│                            │  ├─ CAKE-aware monitoring
│                            │  ├─ Multi-signal voting
│                            │  └─ Latency-sensitive routing
└────────────────────────────┴────────────────┘
```

## Quick Start

### Deploy to Production

**Single command deployment:**
```bash
cd /home/kevin/projects/wanctl
./scripts/deploy_clean.sh
```

This will:
- ✅ Deploy to both ATT and Spectrum containers
- ✅ Copy unified `autorate_continuous.py` (Phase 2A)
- ✅ Copy steering daemon to Spectrum
- ✅ Deploy container-specific configs
- ✅ Copy systemd units to `/tmp/`
- ✅ Verify all files deployed correctly

**Then manually install systemd units (requires root):**

See `scripts/DEPLOYMENT.md` for complete instructions, or follow the output from `deploy_clean.sh`.

### Monitor System

```bash
# Check service status
ssh cake-att 'systemctl status cake-att-continuous.service'
ssh cake-spectrum 'systemctl status cake-spectrum-continuous.service wan-steering.service'

# View live logs
ssh cake-att 'tail -f /home/kevin/wanctl/logs/cake_auto.log'
ssh cake-spectrum 'tail -f /home/kevin/wanctl/logs/cake_auto.log'
ssh cake-spectrum 'tail -f /home/kevin/wanctl/logs/steering.log'

# Check for errors
ssh cake-att 'tail -100 /home/kevin/wanctl/logs/cake_auto.log | grep -i error'
ssh cake-spectrum 'tail -100 /home/kevin/wanctl/logs/cake_auto.log | grep -i error'
```

## What's Running

### ATT Container (10.10.110.247)
- **Script:** `autorate_continuous.py` (Phase 2A with backward compatibility)
- **Config:** `att_config.yaml` (legacy 3-state format)
- **State Machine:** GREEN → YELLOW → RED
- **Floors:** DL=25M, UL=6M
- **Ceiling:** DL=95M, UL=18M
- **Frequency:** Every 2 seconds
- **Typical State:** GREEN/GREEN (delta RTT ~0ms)

### Spectrum Container (10.10.110.246)
- **Autorate Script:** `autorate_continuous.py` (Phase 2A)
- **Config:** `spectrum_config.yaml` (4-state format)
- **State Machine:** GREEN → YELLOW → SOFT_RED → RED
- **Floors:** DL=550M/350M/275M/200M, UL=8M
- **Ceiling:** DL=940M, UL=38M
- **Frequency:** Every 2 seconds
- **Typical State:** GREEN/GREEN (delta RTT ~2-5ms)

**Steering Daemon:**
- **Script:** `wan_steering_daemon.py`
- **Purpose:** Routes latency-sensitive traffic to ATT during Spectrum congestion
- **Frequency:** Every 2 seconds
- **Typical State:** SPECTRUM_GOOD (no steering needed)
- **Congestion Detection:** Multi-signal (RTT + CAKE drops + queue depth)

## Project Structure

```
/home/kevin/projects/wanctl/       # Development directory
├── src/cake/
│   ├── autorate_continuous.py     # Main controller (Phase 2A, unified)
│   ├── wan_steering_daemon.py     # WAN steering daemon
│   ├── cake_stats.py              # CAKE statistics collector
│   ├── congestion_assessment.py   # Congestion detection
│   └── steering_confidence.py     # Steering decision logic
├── configs/
│   ├── att_config.yaml            # ATT configuration (3-state)
│   ├── spectrum_config.yaml       # Spectrum configuration (4-state)
│   └── steering_config_v2.yaml    # Steering configuration
├── systemd/
│   ├── cake-att-continuous.{service,timer}
│   ├── cake-spectrum-continuous.{service,timer}
│   └── wan-steering.{service,timer}
├── scripts/
│   ├── deploy_clean.sh            # Unified deployment script
│   └── DEPLOYMENT.md              # Deployment guide
├── docs/                          # Technical documentation
├── .claude/
│   └── context.md                 # Project context for Claude Code
├── CLAUDE.md                      # Complete technical reference
└── README.md                      # This file

/home/kevin/wanctl/                # On containers (deployed)
├── autorate_continuous.py
├── wan_steering_daemon.py         # Spectrum only
├── cake_stats.py                  # Spectrum only
├── congestion_assessment.py       # Spectrum only
├── steering_confidence.py         # Spectrum only
├── requirements.txt
├── configs/
│   ├── att_config.yaml            # ATT only
│   ├── spectrum_config.yaml       # Spectrum only
│   └── steering_config_v2.yaml    # Spectrum only
└── logs/
    ├── cake_auto.log              # Both containers
    └── steering.log               # Spectrum only
```

## How It Works

### Continuous Monitoring (Primary Control Loop)

Every 2 seconds:
1. **Measure baseline RTT** (3 pings to reference hosts)
2. **Track baseline via EWMA** (slow alpha: 0.015-0.02)
3. **Measure loaded RTT** (during normal traffic)
4. **Calculate delta RTT** (loaded - baseline)
5. **Determine state** based on delta thresholds:
   - **GREEN:** delta ≤ 15ms (ATT: 3ms) - Healthy
   - **YELLOW:** 15ms < delta ≤ 45ms (ATT: 3-10ms) - Early warning
   - **SOFT_RED:** 45ms < delta ≤ 80ms (Spectrum only) - RTT-only congestion
   - **RED:** delta > 80ms - Hard congestion
6. **Adjust CAKE limits** based on state (state-dependent floors)
7. **Apply to RouterOS** via SSH

**Key Innovation (Phase 2A):**
- **SOFT_RED state** (Spectrum only) handles RTT-only congestion without triggering steering
- Clamps to 275 Mbps floor and holds (doesn't enable steering)
- Prevents ~85% of unnecessary steering activations
- ATT uses simpler 3-state model (adequate for VDSL)

### WAN Steering (Secondary Override)

Runs on Spectrum container only, every 2 seconds:
1. **Collect CAKE statistics** (drops, queue depth, packet counts)
2. **Assess congestion** using multi-signal voting:
   - RTT delta (EWMA smoothed, α=0.3)
   - CAKE drops (hard congestion proof)
   - Queue depth (early warning)
3. **Determine action:**
   - **GREEN:** All signals healthy → steering OFF
   - **YELLOW:** Early warning → no action yet
   - **RED:** Confirmed congestion → steering ON (requires 2 consecutive samples)
4. **Enable/disable mangle rule** for latency-sensitive traffic

**What gets steered to ATT:**
- VoIP, DNS, push notifications, gaming, SSH, interactive web
- DSCP-marked traffic (EF, AF31)

**What stays on Spectrum:**
- Bulk downloads/uploads, video streaming, background traffic

## Configuration

All tuning parameters are in YAML config files.

### ATT Config (Legacy 3-State)
```yaml
continuous_monitoring:
  download:
    floor_mbps: 25           # Single floor value
    ceiling_mbps: 95
  thresholds:
    target_bloat_ms: 3       # GREEN → YELLOW
    warn_bloat_ms: 10        # YELLOW → RED
```

### Spectrum Config (Phase 2A 4-State)
```yaml
continuous_monitoring:
  download:
    floor_green_mbps: 550    # GREEN state floor
    floor_yellow_mbps: 350   # YELLOW state floor
    floor_soft_red_mbps: 275 # SOFT_RED state floor (RTT-only)
    floor_red_mbps: 200      # RED state floor (hard congestion)
    ceiling_mbps: 940
  thresholds:
    target_bloat_ms: 15      # GREEN → YELLOW
    warn_bloat_ms: 45        # YELLOW → SOFT_RED
    critical_bloat_ms: 80    # SOFT_RED → RED
```

**The same `autorate_continuous.py` script handles both formats!** It detects the config schema and adapts accordingly.

## Performance Characteristics

| Metric | ATT | Spectrum |
|--------|-----|----------|
| **Typical State** | GREEN/GREEN | GREEN/GREEN |
| **Delta RTT** | 0-1ms | 2-5ms |
| **GREEN Uptime** | ~90% | 89.3% (validated) |
| **Steering Active** | N/A | <0.03% of time |
| **Control Frequency** | Every 2s | Every 2s |
| **Baseline RTT** | 28ms | 24-27ms |

## Safety Mechanisms

1. ✅ **SSH Host Key Validation** - MITM attack prevention
2. ✅ **State-Dependent Floors** - Prevents bandwidth collapse
3. ✅ **EWMA Smoothing** - Prevents rapid oscillation
4. ✅ **Multi-Signal Voting** - Reduces false positives in steering
5. ✅ **Hysteresis** - Requires sustained state changes (2s for RED, 30s for GREEN recovery)
6. ✅ **Connection State Preservation** - Never reroutes existing flows
7. ✅ **SOFT_RED Clamping** - Absorbs RTT spikes without steering

## Monitoring & Troubleshooting

### Check System Health
```bash
# Quick health check
ssh cake-att 'systemctl status cake-att-continuous.service'
ssh cake-spectrum 'systemctl status cake-spectrum-continuous.service wan-steering.service'

# View current state
ssh cake-att 'tail -5 /home/kevin/wanctl/logs/cake_auto.log | grep "ATT:"'
ssh cake-spectrum 'tail -5 /home/kevin/wanctl/logs/cake_auto.log | grep "Spectrum:"'

# Check steering status
ssh cake-spectrum 'tail -5 /home/kevin/wanctl/logs/steering.log | grep SPECTRUM'
```

### Expected Healthy Output
```
ATT: [GREEN/GREEN] RTT=28.0ms, load_ewma=28.0ms, baseline=28.0ms, delta=0.0ms | DL=95M, UL=18M
Spectrum: [GREEN/GREEN] RTT=25.5ms, load_ewma=27.6ms, baseline=26.9ms, delta=0.7ms | DL=940M, UL=38M
[SPECTRUM_GOOD] rtt=0.0ms ewma=0.1ms drops=0 q=0 | congestion=GREEN
```

### Troubleshooting

**Service won't start:**
```bash
# Check logs
journalctl -u cake-att-continuous.service -n 50

# Test manually
ssh cake-att
cd /home/kevin/wanctl
python3 autorate_continuous.py --configs configs/att_config.yaml --debug
```

**Config schema error:**
```
KeyError: 'floor_mbps'  →  Wrong script/config combination
```
- ATT should use legacy config (`floor_mbps`)
- Spectrum should use Phase 2A config (`floor_green_mbps`, etc.)
- Both use the same unified `autorate_continuous.py` script

**Steering not working:**
```bash
# Check steering daemon is running
ssh cake-spectrum 'systemctl status wan-steering.service'

# Check for errors
ssh cake-spectrum 'journalctl -u wan-steering.service -n 50'

# Verify config
ssh cake-spectrum 'cat /home/kevin/wanctl/configs/steering_config_v2.yaml | head -20'
```

## Documentation

- **`scripts/DEPLOYMENT.md`** - Complete deployment guide
- **`CLAUDE.md`** - Full technical reference (architecture, algorithms, validated behavior)
- **`.claude/context.md`** - Project context for Claude Code sessions
- **`docs/SSH_SECURITY_SETUP.md`** - SSH key deployment instructions
- **`docs/*.md`** - Additional technical documentation

## Recent Changes (2026-01-07)

### ✅ Config Bug Fixed
- Fixed schema mismatch causing `KeyError: 'floor_mbps'`
- Deployed correct configs to both containers
- ATT: Legacy 3-state format
- Spectrum: Phase 2A 4-state format

### ✅ Unified Codebase
- Eliminated version file confusion (`_v2`, `_original`)
- Single `autorate_continuous.py` (Phase 2A with backward compatibility)
- Same code on both containers, different configs

### ✅ Container Cleanup
- Removed ~65K of cruft (obsolete scripts, backups, `__pycache__`)
- Archived to `.obsolete_20260107/` directories

### ✅ Deployment Unified
- New `scripts/deploy_clean.sh` - single command for both containers
- SSH key-based (no password prompts)
- Color-coded progress indicators
- Automatic verification
- Replaces 7 obsolete deployment scripts

## Production Status

**Last Validated:** 2026-01-07 02:35 UTC

- ✅ **ATT:** GREEN/GREEN, delta RTT 0.0ms, no errors
- ✅ **Spectrum:** GREEN/GREEN, delta RTT 2.5ms, no errors
- ✅ **Steering:** SPECTRUM_GOOD, 0 drops, no congestion
- ✅ **Uptime:** 1 week, 5 days, 13 hours (both containers)
- ✅ **Commits:** All changes pushed to git

**System is healthy and operational.** 🎉

## Security

- ✅ SSH host key validation enabled (MITM protection)
- ✅ No hardcoded passwords (environment variables only)
- ✅ SSH key-based authentication for RouterOS
- ✅ Unprivileged containers (systemd requires manual root install)
- ✅ No exposed network services (pull-based architecture)

## License

Created by Kevin for MikroTik rb5009 dual-WAN adaptive CAKE system.

## Support

For deployment issues:
1. Check `scripts/DEPLOYMENT.md`
2. Review logs: `journalctl -u cake-*.service` or `/home/kevin/wanctl/logs/`
3. Verify SSH connectivity to containers and router
4. Test manually with `--debug` flag
5. Check `CLAUDE.md` for technical details

---

**Note:** This system is production infrastructure. Always test deployments and monitor logs after changes.
