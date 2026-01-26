# wanctl - Adaptive Dual-WAN Control System

**IMPORTANT:** Production network control system. Change conservatively.

## What It Does

Dual-WAN system for MikroTik: eliminates bufferbloat via CAKE queue tuning + intelligent WAN steering based on real-time congestion.

**Type:** Production (24/7), Python 3.12, deployed to `/opt/wanctl`
**Version:** 1.7.0
**Cycle Interval:** 50ms (20Hz polling, 40x faster than original 2s baseline)

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

| Container     | Purpose                           |
| ------------- | --------------------------------- |
| cake-spectrum | Primary WAN (Spectrum) + steering |
| cake-att      | Secondary WAN (ATT)               |

## RouterOS Integration

**Recommended:** REST API (2x faster than SSH)

```yaml
router:
  transport: "rest" # or "ssh"
  host: "10.10.99.1"
  password: "${ROUTER_PASSWORD}" # From /etc/wanctl/secrets
```

## Development Commands

```bash
# Tests (use venv directly, not system python)
.venv/bin/pytest tests/ -v
.venv/bin/pytest tests/test_foo.py -v  # specific file

# Linting and type checking
.venv/bin/ruff check src/ tests/
.venv/bin/mypy src/wanctl/

# Format code
.venv/bin/ruff format src/ tests/
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
- Rate decreases: immediate | Rate increases: require sustained GREEN cycles (configurable, default 5)

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

## ICMP Blackout Handling

**Resolved:** Spectrum ISP ICMP blocking (v1.1.0 fix)

When ICMP is blocked/filtered, controller now measures TCP RTT as fallback during connectivity checks. This prevents watchdog restarts and provides accurate latency data even during ICMP outages. See `CHANGELOG.md` for details.

## Known Issues

None currently. See `CHANGELOG.md` for resolved issues.

## Version

**Current:** v1.7.0 (Metrics History Release)

- SQLite metrics storage with automatic downsampling
- `wanctl-history` CLI for querying historical data
- `/metrics/history` HTTP API endpoint
- 1727 unit tests passing, 90%+ coverage

## Performance Characteristics

**Cycle Interval:** 50ms (production standard, deployed 2026-01-13)
**Congestion Response:** 50-100ms detection time (sub-second)
**Router Impact:** 0% CPU at idle, 45% peak under load (MikroTik RB5009)
**Utilization:** 60-80% (30-40ms execution per 50ms cycle)

See `docs/PRODUCTION_INTERVAL.md` for complete performance analysis, validation results, and rollback procedures.

## Documentation

- `CHANGELOG.md` - Version history and changes
- `docs/PRODUCTION_INTERVAL.md` - **50ms interval decision and performance validation**
- `docs/PORTABLE_CONTROLLER_ARCHITECTURE.md` - Design principles
- `docs/CONFIG_SCHEMA.md` - Configuration reference
- `docs/TRANSPORT_COMPARISON.md` - REST vs SSH performance
