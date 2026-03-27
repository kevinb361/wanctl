# Phase 110: Production Cutover - Context

**Gathered:** 2026-03-25
**Status:** Ready for planning

<domain>
## Phase Boundary

Migrate both WAN links from MikroTik queue tree CAKE shaping to Linux VM CAKE shaping on cake-shaper (VM 206). Staged approach: ATT first, then Spectrum. Includes rollback drill testing, before/after benchmarking, and MikroTik queue tree disabling. No new code — this is deployment, cabling, config, and validation.

</domain>

<decisions>
## Implementation Decisions

### Physical Cabling
- **D-01:** Direct connections, no patch panel or switch. 4 cables total.
- **D-02:** Spectrum modem -> odin ens16 (i210 hostpci0) -> br-spectrum -> ens17 (i210 hostpci1) -> MikroTik ether1-WAN-Spectrum
- **D-03:** ATT modem -> odin ens27 (i350 hostpci2) -> br-att -> ens28 (i350 hostpci3) -> MikroTik ether2-WAN-ATT
- **D-04:** odin is physically near the router and both modems. Cable runs are short.

### Config YAML
- **D-05:** Clone existing production configs (spectrum.yaml, att.yaml), change transport to linux-cake, add cake_params section. Preserves all tuned thresholds, IRTT, fusion, signal processing settings.
- **D-06:** Keep REST API connection to MikroTik for steering mangle rules. linux-cake handles bandwidth control, REST handles steering.
- **D-07:** cake_params must include: upload_interface (ens17/ens28), download_interface (ens17/ens28), overhead, memlimit, rtt. Direction-specific params (ingress for download, ack-filter for upload) per Phase 106.
- **D-08:** ecn keyword NOT supported by iproute2-6.15.0 on cake-shaper. Omit from cake_params (CAKE enables ECN by default).

### Migration Order
- **D-09:** ATT first (lower risk, lower bandwidth), then Spectrum. Per CUTR-03.
- **D-10:** ATT soaks 1 hour on VM with monitoring before cutting Spectrum.
- **D-11:** Both WANs soak 24 hours before declaring v1.21 milestone complete.

### MikroTik Queue Trees
- **D-12:** Disable MikroTik queue tree entries (not delete). Per CUTR-01.
- **D-13:** Queue trees to disable: WAN-Download-Spectrum, WAN-Upload-Spectrum, WAN-Download-ATT, WAN-Upload-ATT.
- **D-14:** Disable per-WAN as cutover happens (disable ATT queues when ATT moves to VM, etc.).

### Rollback Strategy
- **D-15:** Two rollback levels:
  - Level 1 (soft): Stop wanctl daemon -> bridges still forward unshaped -> re-enable MikroTik queue trees
  - Level 2 (hard): Unplug cables from odin -> reconnect modems directly to MikroTik
- **D-16:** Drill BOTH levels during ATT migration (while Spectrum stays on MikroTik as safety net).
- **D-17:** Rollback drill happens AFTER ATT is migrated and validated, not before.

### Benchmark Validation
- **D-18:** Baseline benchmark BEFORE cabling changes (MikroTik CAKE performance). Run RRUL on each WAN.
- **D-19:** After-benchmark on each WAN after VM CAKE is active. Compare throughput and latency under load.
- **D-20:** Success criteria: Spectrum exceeds 740Mbps ceiling AND latency under load is comparable or better.
- **D-21:** Use wanctl-benchmark and/or flent RRUL via Dallas netperf server.

### Claude's Discretion
- Exact order of operations within each WAN cutover (disable queues before or after cabling)
- Config file deployment method (scp, deploy.sh, manual)
- Monitoring approach during soak (journalctl, health endpoint, Discord alerts)
- Checkpoint placement for human verification steps

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Infrastructure (Phase 109 output)
- `docs/VM_INFRASTRUCTURE.md` -- Complete runbook: VFIO, VM, bridges, NIC mapping, deployment, operational reference
- `.planning/phases/109-vm-infrastructure-bridges/109-01-SUMMARY.md` -- VFIO verification results
- `.planning/phases/109-vm-infrastructure-bridges/109-02-SUMMARY.md` -- VM creation, NIC name discovery
- `.planning/phases/109-vm-infrastructure-bridges/109-03-SUMMARY.md` -- Bridge configuration results
- `.planning/phases/109-vm-infrastructure-bridges/109-04-SUMMARY.md` -- wanctl deployment, CAKE test results

### Production Config (current MikroTik-based)
- `configs/spectrum.yaml` -- Current Spectrum production config (to be cloned)
- `configs/att.yaml` -- Current ATT production config (to be cloned)
- `configs/steering.yaml` -- Steering config (stays REST-based)

### Code References
- `src/wanctl/backends/linux_cake.py` -- LinuxCakeBackend implementation
- `src/wanctl/check_config.py` -- validate_linux_cake() for config validation
- `src/wanctl/cake_params.py` -- build_cake_params() for param construction
- `scripts/deploy.sh` -- Deployment script
- `systemd/wanctl@.service` -- Service template

### Router Documentation
- `docs/EF_QUEUE_PROTECTION.md` -- MikroTik interface names (ether1-WAN-Spectrum, ether2-WAN-ATT)

### Memory
- `~/.claude/projects/-home-kevin-projects-wanctl/memory/project_cake_shaper_vm.md` -- VM 206 details, NIC names, IP

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `wanctl-benchmark` CLI -- can run RRUL benchmarks against Dallas netperf server
- `wanctl-check-config` CLI -- validates linux-cake transport settings before daemon start
- `wanctl-check-cake` CLI -- audits CAKE qdisc state on router (needs adaptation for local tc)
- `deploy.sh` -- handles rsync + systemd deployment to target host
- Discord webhook alerts -- already configured, will fire on new VM instances

### Established Patterns
- Production deployment: /opt/wanctl, /etc/wanctl, /var/lib/wanctl, /var/log/wanctl
- System Python, pip3 --break-system-packages
- wanctl@.service template with instance name (spectrum, att)
- Secrets at /etc/wanctl/secrets (ROUTER_PASSWORD, DISCORD_WEBHOOK_URL)

### Integration Points
- New configs go to /etc/wanctl/spectrum.yaml and /etc/wanctl/att.yaml on cake-shaper
- Steering daemon needs access to MikroTik REST API (10.10.99.1) from cake-shaper management NIC
- Health endpoints (9101/9102) will be on 10.10.110.223 instead of .246/.247
- IRTT measurements go out via management NIC (ens18) to Dallas server

</code_context>

<specifics>
## Specific Ideas

- Cutover sequence for each WAN:
  1. Baseline benchmark (MikroTik CAKE)
  2. Cable modem -> odin NIC, odin NIC -> MikroTik port
  3. Verify bridge forwarding (traffic flows unshaped)
  4. Deploy config to cake-shaper
  5. Start wanctl daemon (CAKE activates)
  6. Verify CAKE active via tc qdisc show
  7. Disable MikroTik queue tree for that WAN
  8. After-benchmark (Linux CAKE)
  9. Monitor soak period

- ATT cutover includes full rollback drill (both levels) before proceeding to Spectrum

- MikroTik queue tree disable via REST API:
  ```
  /queue/tree/set .id=WAN-Download-ATT disabled=yes
  /queue/tree/set .id=WAN-Upload-ATT disabled=yes
  ```

</specifics>

<deferred>
## Deferred Ideas

- Automated cutover script (single command to do all steps) -- manual is safer for first cutover
- Health endpoint monitoring dashboard for cake-shaper
- Container decommission (cake-spectrum, cake-att containers) -- keep running as fallback until v1.21 milestone is closed

</deferred>

---

*Phase: 110-production-cutover*
*Context gathered: 2026-03-25*
