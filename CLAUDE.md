# wanctl - Adaptive Dual-WAN Control System

**IMPORTANT:** Production network control system. Change conservatively.

## What It Does

Dual-WAN system for MikroTik: eliminates bufferbloat via CAKE queue tuning + intelligent WAN steering based on real-time congestion.

**Type:** Production (24/7), Python 3.12, deployed to `/opt/wanctl`
**Version:** 1.0.0-rc8

## Change Policy

- Explain before changing, prefer analysis over implementation
- Never refactor core logic, algorithms, thresholds, or timing without approval
- **Priority:** stability > safety > clarity > elegance

## Portable Controller Architecture

🔒 **NON-NEGOTIABLE:** Controller is link-agnostic. Identical code runs on all deployments (cable/DSL/fiber). All variability in config parameters (YAML).

See `docs/PORTABLE_CONTROLLER_ARCHITECTURE.md` for details.

## File Locations

```
/opt/wanctl/          # Application code
/etc/wanctl/          # Config (*.yaml, secrets)
/var/lib/wanctl/      # State files
/var/log/wanctl/      # Logs
```

## Container Details

| Container      | Purpose                         |
| -------------- | ------------------------------- |
| cake-spectrum  | Primary WAN (Spectrum) + steering |
| cake-att       | Secondary WAN (ATT)             |

## RouterOS Integration

**Recommended:** REST API (2x faster than SSH)

```yaml
router:
  transport: "rest"  # or "ssh"
  host: "10.10.99.1"
  password: "${ROUTER_PASSWORD}"  # From /etc/wanctl/secrets
```

## Quick Commands

```bash
# Status
./scripts/soak-monitor.sh

# Monitor logs
ssh cake-spectrum 'journalctl -u wanctl@spectrum -f'

# Health check
ssh cake-spectrum 'curl -s http://127.0.0.1:9101/health | python3 -m json.tool'
```

## Architectural Spine (READ-ONLY)

**Do not modify without explicit instruction:**

### Control Model
- All decisions based on RTT **delta** (not absolute RTT)
- Baseline must remain frozen during load (only updates when delta < 3ms)
- Rate decreases: immediate | Rate increases: require sustained GREEN (5 cycles)

### State Logic
- Download: 4-state (GREEN/YELLOW/SOFT_RED/RED)
- Upload: 3-state (GREEN/YELLOW/RED)
- SOFT_RED clamps to floor and holds (no repeated decay)

### Flash Wear Protection
- Queue limits ONLY sent to router when values change
- `last_applied_dl_rate`/`last_applied_ul_rate` tracking MANDATORY

### Steering Spine
- Only secondary WAN (cake-spectrum) makes routing decisions
- Steering is binary: enabled or disabled
- Only new latency-sensitive connections rerouted
- Autorate baseline RTT is authoritative (steering must not alter)

## Known Issues

None currently. See `CHANGELOG.md` for resolved issues.

## Version

**Current:** v1.0.0-rc8 (Fallback Connectivity Checks)
- Fallback connectivity checks reduce watchdog restarts
- Steering daemon operational
- 474 unit tests passing

## Documentation

- `CHANGELOG.md` - Version history and changes
- `docs/PORTABLE_CONTROLLER_ARCHITECTURE.md` - Design principles
- `docs/CONFIG_SCHEMA.md` - Configuration reference
- `docs/TRANSPORT_COMPARISON.md` - REST vs SSH performance
