# Phase 125: Boot Resilience - Context

**Gathered:** 2026-04-02
**Status:** Ready for planning

<domain>
## Phase Boundary

cake-shaper VM fully self-configures after reboot -- NIC optimizations applied automatically before wanctl starts, with correct systemd dependency ordering across the entire boot chain. This phase hardens and completes the existing `wanctl-nic-tuning.service` (already deployed since 2026-03-26), adds explicit dependency wiring, fixes deploy.sh coverage, and reconciles diverged systemd unit files.

</domain>

<decisions>
## Implementation Decisions

### Failure behavior
- **D-01:** Claude's Discretion. Leaning toward `Wants=` (warn but start) -- wanctl running with suboptimal NIC settings is better than no wanctl. Phase 126 validation will surface the problem.

### Script approach
- **D-02:** Move NIC tuning from bare ExecStart lines to a shell script (`/usr/local/bin/wanctl-nic-tuning.sh`). Enables per-NIC error handling, logging to journal via `logger`, idempotency checks, and graceful handling of missing NICs. Follows the same pattern as `wanctl-recovery.sh`.

### Systemd unit cleanup
- **D-03:** Claude's Discretion on directory structure. Reconcile the two diverged copies of `wanctl@.service` (`deploy/systemd/` has hardened version, `systemd/` has older version). Pick whichever structure is cleaner for the project. Fix `deploy.sh` to include the NIC tuning unit in its deployment.

### Ethtool scope
- **D-04:** Audit live production NICs for all non-default ethtool settings and persist them. Current unit has ring buffers (rx/tx 4096), rx-udp-gro-forwarding, and IRQ affinity. Capture anything else that's been tuned.

### Reboot test strategy
- **D-05:** Two-step validation. First: dry-run everything without rebooting (systemd-analyze verify, dependency graph check, manual script execution for idempotency). Second: schedule a low-traffic reboot window as a separate step after dry-run passes.

### Claude's Discretion
- Failure mode choice (Requires= vs Wants=) for NIC tuning dependency
- Systemd directory structure (deploy/systemd/ vs systemd/ canonical location)
- Specific ethtool settings to persist beyond current set (determined by production audit)
- deploy.sh changes needed to include NIC tuning unit

</decisions>

<specifics>
## Specific Ideas

- Shell script pattern: follow `wanctl-recovery.sh` style (logger for journal output, per-item error handling)
- The NIC tuning service already has systemd hardening (ProtectSystem=strict, etc.) -- preserve this
- IRQ affinity pinning: Spectrum NICs (ens16/ens17) -> CPU 0, ATT NICs (ens27/ens28) -> CPU 1

</specifics>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Existing systemd units (source of truth for current state)
- `deploy/systemd/wanctl-nic-tuning.service` -- Current NIC tuning oneshot (deployed to production)
- `deploy/systemd/wanctl@.service` -- Hardened wanctl service template (deployed version)
- `deploy/systemd/steering.service` -- Steering daemon unit
- `systemd/wanctl@.service` -- Older copy, diverged from deploy/ version

### Deployment
- `scripts/deploy.sh` -- Deployment script that needs NIC tuning unit added
- `scripts/install.sh` -- Installation script

### Recovery
- Production file: `/usr/local/bin/wanctl-recovery.sh` -- Pattern to follow for NIC tuning script (SSH to 10.10.110.223 to read)
- Production file: `/etc/systemd/system/wanctl-recovery.timer` -- Existing recovery timer

### VM infrastructure
- `docs/VM_INFRASTRUCTURE.md` -- cake-shaper VM setup documentation

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `deploy/systemd/wanctl-nic-tuning.service`: Already deployed, working, enabled. Needs hardening not rewriting.
- `wanctl-recovery.sh` on production: Shell script pattern with `logger -t` for journal logging, per-item checks.
- `scripts/validate-deployment.sh`: Existing deployment validation -- may be extended for boot chain validation.

### Established Patterns
- systemd hardening: All units use ProtectSystem=strict, capability bounding, syscall filtering
- FHS paths: /opt/wanctl (code), /etc/wanctl (config), /var/lib/wanctl (state), /var/log/wanctl (logs)
- deploy.sh uses rsync for code, explicit file lists for systemd units and configs

### Integration Points
- `wanctl@.service` needs `After=wanctl-nic-tuning.service` added
- `deploy.sh` SYSTEMD_FILES array needs NIC tuning unit added
- NIC tuning script goes to `/usr/local/bin/` on target (same as recovery script)

### Key Production Details
- VM: cake-shaper (10.10.110.223), Debian 13, 2 vCPUs, 1.9GB RAM
- NICs: ens16/ens17 (i210 Spectrum bridge), ens27/ens28 (i350 ATT bridge)
- Bridges: br-spectrum, br-att (systemd-networkd, already persistent)
- Services: wanctl@spectrum, wanctl@att, steering (port 9102)
- Recovery: wanctl-recovery.timer (5min interval, checks for failed units)

</code_context>

<deferred>
## Deferred Ideas

- Steering service version sync (v1.23 -> v1.24) -- noted but not in Phase 125 scope

</deferred>

---

*Phase: 125-boot-resilience*
*Context gathered: 2026-04-02*
