# wanctl - Adaptive Dual-WAN Control System

**IMPORTANT:** This is a **production network control system**. Change conservatively.

## What It Does

Dual-WAN system for MikroTik router: eliminates bufferbloat via CAKE queue tuning + intelligent WAN steering based on real-time congestion.

**Type:** Production (24/7), Python 3.12, deployed to `/opt/wanctl`
**Version:** 1.0.0-rc7

## Change Policy

**Default approach:**
- Explain before changing
- Prefer analysis and suggestions
- Propose changes as a plan, not implementation
- Make minimal, surgical changes only when approved

**Never (unless explicitly instructed):**
- Refactor core logic
- Change algorithms, thresholds, or timing
- Rename files/modules
- Reorganize project structure
- "Clean up" for style alone

**Priority:** stability > safety > clarity > elegance

## Portable Controller Architecture

🔒 **NON-NEGOTIABLE:** The controller is link-agnostic.

**Identical code** runs on all deployments (DOCSIS cable, VDSL2 DSL, GPON fiber).
**All variability in config parameters** (YAML).

See `docs/PORTABLE_CONTROLLER_ARCHITECTURE.md` for details.

## Key Components

### 1. Main Controller: `src/wanctl/autorate_continuous.py`
- Single script, config-driven (~800 lines)
- Runs on both containers with different configs

### 2. Adaptive Steering: `src/wanctl/steering/daemon.py`
- Routes latency-sensitive traffic to secondary WAN when primary congests
- 3-state model: GREEN/YELLOW/RED
- Multi-signal decision: RTT delta (EWMA), CAKE drops, queue depth
- Requires 2 consecutive RED samples (4s) to enable
- Requires 15 consecutive GREEN samples (30s) to disable

### 3. Configuration: `configs/*.yaml`
- All tuning parameters externalized
- Floors, thresholds, alphas, etc.

## File Locations

```
/opt/wanctl/                   # Application code (FHS compliant)
/etc/wanctl/                   # Configuration (*.yaml, secrets)
/var/lib/wanctl/               # State files (*_state.json)
/var/log/wanctl/               # Logs
```

## Container Details

| Container       | Purpose                  |
| --------------- | ------------------------ |
| wan1-container  | Primary WAN tuning       |
| wan2-container  | Secondary WAN tuning + steering |

**Access:** Use hostnames configured in your environment

## RouterOS Integration

**Recommended:** REST API (2x faster than SSH)
```yaml
router:
  transport: "rest"  # or "ssh"
  host: "router-ip"
  password: "${ROUTER_PASSWORD}"  # From /etc/wanctl/secrets
```

**Secrets:** `/etc/wanctl/secrets` (mode 640, root:wanctl)

## Commands

```bash
# Monitor
ssh <container> 'systemctl list-timers wanctl@*'
ssh <container> 'journalctl -u wanctl@wan1.service -f'
ssh <container> 'cat /var/lib/wanctl/wan1_state.json'

# Manual test
ssh <container> 'cd /opt/wanctl && python3 -m wanctl.autorate_continuous --config /etc/wanctl/wan1.yaml --debug'

# Reset state
ssh <container> 'python3 -m wanctl.autorate_continuous --config /etc/wanctl/wan1.yaml --reset'
```

## Observability (v1.0.0-rc7)

**Health check:** `curl http://127.0.0.1:9101/health` (enabled by default)
**Metrics:** `curl http://127.0.0.1:9100/metrics` (disabled by default, enable in config)
**JSON logging:** `export WANCTL_LOG_FORMAT=json`
**Config validation:** `wanctl --config spectrum.yaml --validate-config`

## Security

- Signal handling: Thread-safe shutdown via `threading.Event()`
- PID-based locks: Validates process liveness, removes stale locks
- Watchdog: Tracks failures (threshold: 3), stops heartbeat on degradation
- Rate limiting: Router config changes limited to 10/minute
- EWMA overflow protection: Bounds checking prevents numeric overflow
- Backup recovery: Auto-recovery from `.backup` before defaults

## Architectural Spine (READ-ONLY)

**Do not modify these behaviors without explicit instruction:**

### Control Model
- All decisions based on RTT _delta_ relative to baseline
- Absolute RTT values are NOT a control signal

### Baseline RTT
- Baseline must remain frozen during load
- May only update when delta < ~3ms
- **Baseline drift under load is forbidden**

### Asymmetric Response
- Rate decreases: immediate
- Rate increases: require sustained GREEN state
- Recovery must be slower than backoff

### State Logic
- Download: 4-state (GREEN/YELLOW/SOFT_RED/RED)
- Upload: 3-state (GREEN/YELLOW/RED)
- SOFT_RED clamps to floor and holds (no repeated decay)

### Flash Wear Protection
- Queue limits ONLY sent to router when values change
- `last_applied_dl_rate`/`last_applied_ul_rate` tracking MANDATORY
- Prevents premature NAND flash wear

### Steering Spine
- Only secondary WAN controller makes routing decisions
- Steering is binary: enabled or disabled
- Only new latency-sensitive connections rerouted
- Decisions based on primary WAN congestion only
- Autorate baseline RTT is authoritative (steering must not alter)

## Code Reviews

Stored in `.claude/reviews/` (version-controlled).

**Latest:** `comprehensive-2026-01-10.md` - All recommendations implemented
**Status:** LOW risk, production-ready, 474 tests passing

## Known Issues

### 1. Steering Config Filename Mismatch (Temporary Fix Applied)

**Status:** RESOLVED with temporary fix, permanent fix pending

**What happened:** Deployment script expects `configs/steering.yaml` but actual config is named `configs/steering_config.yaml`. Deploy script falls back to generic example template, causing steering to fail with wrong config values.

**Impact:** Steering was non-functional for several days, but autorate continued working perfectly. No network performance impact.

**Current fix:** Manual deployment of correct values to production.

**Permanent fix options:**
1. **Rename file:** `git mv configs/steering_config.yaml configs/steering.yaml` (simplest, recommended)
2. **Update deploy script:** Modify `scripts/deploy.sh` to look for `steering_config.yaml` first
3. **Add validation:** Deploy script should validate config before deployment (prevent future occurrences)

**Related documentation:** `docs/STEERING_CONFIG_MISMATCH_ISSUE.md`

## Version

**Current:** v1.0.0-rc7 (Observability & Reliability)
- Health check endpoint (/health)
- Prometheus metrics (/metrics)
- JSON structured logging
- Rate limiting for router changes
- EWMA overflow protection
- State backup recovery
- 474 unit tests

## Documentation

- `docs/PORTABLE_CONTROLLER_ARCHITECTURE.md` - Design principles
- `docs/CONFIG_SCHEMA.md` - Configuration semantics
- `docs/TRANSPORT_COMPARISON.md` - REST vs SSH comparison
