# Phase 115: Operational Hardening - Context

**Gathered:** 2026-03-26
**Status:** Ready for planning

<domain>
## Phase Boundary

Harden production VM services: systemd security directives, NIC tuning persistence, resource limits, backup/recovery documentation, dependency locking, circuit breaker consistency. All changes deployed to the live cake-shaper VM with safety protocols.

Requirements: OPSEC-01 through OPSEC-06 (6 requirements)

</domain>

<decisions>
## Implementation Decisions

### systemd Hardening (OPSEC-01)
- **D-01:** Apply ALL hardening directives that don't conflict with CAP_NET_RAW. Target score ~4.0 (down from 8.4 EXPOSED).
- **D-02:** Use `systemd-analyze verify` on modified unit files BEFORE reloading. Catches syntax and capability errors without risking service interruption.
- **D-03:** Directives from Phase 112-02 findings: ProtectKernelTunables, SystemCallFilter, RestrictNamespaces, PrivateTmp, ProtectHome, ProtectControlGroups, etc. Only skip directives that break CAP_NET_RAW or tc/ethtool operations.
- **D-04:** All 3 runtime services (wanctl@spectrum, wanctl@att, steering.service) plus NIC tuning oneshot need hardening.

### NIC Persistence (OPSEC-02)
- **D-05:** Use the existing `wanctl-nic-tuning.service` oneshot — it's already on the VM. Update it to include all needed ethtool commands (rx-udp-gro-forwarding, ring buffers).
- **D-06:** Verify persistence by rebooting the VM and checking ethtool output post-boot.

### Resource Limits (OPSEC-03)
- **D-07:** Set MemoryMax, TasksMax, and LimitNOFILE on all 3 service units.
- **D-08:** Size values based on observed production metrics (from Phase 113 findings and production monitoring), not arbitrary defaults.

### Backup/Recovery (OPSEC-04)
- **D-09:** Document procedure only — no automated backup implementation. Write a clear runbook covering configs, metrics.db, VM snapshots, and rollback steps.
- **D-10:** Backup scope: /etc/wanctl/*.yaml, /etc/wanctl/secrets, /var/lib/wanctl/metrics.db, systemd unit files, Proxmox VM snapshot procedure.

### Dependency Lock (OPSEC-05)
- **D-11:** Create requirements-production.txt from the running VM's pip freeze output. This locks the exact versions deployed.

### Circuit Breaker Consistency (OPSEC-06)
- **D-12:** Verify circuit breaker config (Restart=on-failure, RestartSec, StartLimitBurst, StartLimitIntervalSec) is identical across all 3 service units. Fix any inconsistencies.

### Production Change Safety
- **D-13:** Take Proxmox VM snapshot BEFORE any changes. Staged rollout: systemd hardening first (verify services start), then NIC persistence (verify networking), then resource limits (verify under load).
- **D-14:** Rollback plan: revert to VM snapshot if any stage fails. Document rollback steps in the backup/recovery runbook.

### Production VM Access (carried from Phase 112)
- **D-15:** SSH inline commands to cake-shaper at 10.10.110.223.

### Claude's Discretion
- Specific systemd directive list (within CAP_NET_RAW compatibility constraint)
- Resource limit values (based on production observation)
- Backup runbook format and detail level
- Order of staged rollout stages

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Prior Phase Findings
- `.planning/phases/112-foundation-scan/112-02-findings.md` -- systemd security assessment (exposure scores, hardening opportunities, unit file contents, CAP_NET_RAW notes)
- `.planning/phases/113-network-engineering-audit/113-03-findings.md` -- Queue depth baselines (memory usage under load)

### Production Unit Files (on cake-shaper VM)
- `/etc/systemd/system/wanctl@.service` -- Template unit for spectrum/att
- `/etc/systemd/system/steering.service` -- Steering daemon unit
- `/etc/systemd/system/wanctl-nic-tuning.service` -- NIC tuning oneshot

### Production Config
- `/etc/wanctl/spectrum.yaml` -- Spectrum WAN config
- `/etc/wanctl/att.yaml` -- ATT WAN config
- `/etc/wanctl/secrets` -- Secrets file (0640, wanctl group)

### Project Documentation
- `CLAUDE.md` -- Circuit breaker policy section, deployment details
- `docs/PRODUCTION_INTERVAL.md` -- 50ms interval performance analysis

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `wanctl-nic-tuning.service` already exists on production VM -- update rather than create
- Phase 112-02 findings contain full `systemd-analyze security` output with per-directive scores
- Phase 112-02 captured current unit file contents for reference

### Established Patterns
- systemd template unit (`wanctl@.service`) instantiated as `wanctl@spectrum` and `wanctl@att`
- Steering runs as separate `steering.service` (not template-based)
- CAP_NET_RAW in AmbientCapabilities for icmplib ICMP probes
- Circuit breaker: `Restart=on-failure`, 5 failures in 5 minutes triggers stop

### Integration Points
- systemd unit modifications require `sudo systemctl daemon-reload`
- NIC tuning requires `ethtool` commands on bridge member NICs
- Resource limits interact with 50ms cycle budget (don't starve the control loop)

</code_context>

<specifics>
## Specific Ideas

No specific requirements -- standard operational hardening with the decisions captured above.

</specifics>

<deferred>
## Deferred Ideas

None -- discussion stayed within phase scope.

</deferred>

---

*Phase: 115-operational-hardening*
*Context gathered: 2026-03-26*
