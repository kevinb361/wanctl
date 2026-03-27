# Phase 113: Network Engineering Audit - Context

**Gathered:** 2026-03-26
**Status:** Ready for planning

<domain>
## Phase Boundary

Verify that CAKE configuration, DSCP mapping, steering logic, and measurement methodology on the production VM are correct. Compare actual production state against intended design. All auditing via SSH inline commands to cake-shaper (10.10.110.223) and MikroTik REST API (10.10.99.1). No code changes -- documentation and verification only.

Requirements: NETENG-01 through NETENG-05 (5 requirements)

</domain>

<decisions>
## Implementation Decisions

### CAKE Parameter Verification (NETENG-01)
- **D-01:** YAML config files (`/etc/wanctl/{spectrum,att}.yaml`) are the source of truth for expected CAKE parameters. Read config, extract CAKE params, compare against `tc -j qdisc show` readback.
- **D-02:** Use BOTH raw `tc -j qdisc show` readback AND `wanctl-check-cake` CLI tool on the VM as complementary verification. Documents that the tooling itself works correctly on production.
- **D-03:** Parameters to verify per WAN: overhead, diffserv4, ack-filter, split-gso, memlimit (from NETENG-01 success criteria).

### DSCP End-to-End Trace (NETENG-02)
- **D-04:** Document the design path -- no live test traffic needed. Configuration is deterministic: read the rules, map the flow, document the proof.
- **D-05:** Read MikroTik mangle rules via REST API (`/ip/firewall/mangle` on 10.10.99.1). Already proven fast and reliable from wanctl tooling.
- **D-06:** Map the full chain: MikroTik mangle marks -> bridge passthrough -> CAKE diffserv4 tin classification. Document EF->Voice, AF41->Video, CS1->Bulk mappings.

### Steering Logic Audit (NETENG-03)
- **D-07:** Code review + config verification. No runtime log analysis needed.
- **D-08:** Document confidence scoring weights and thresholds from `steering_confidence.py`.
- **D-09:** Verify degrade timers match between config YAML and code defaults.
- **D-10:** Confirm CAKE-primary invariant is enforced in steering logic (primary WAN always handles CAKE shaping).

### Measurement Methodology (NETENG-04)
- **D-11:** Document the signal chain: reflector selection -> raw RTT -> Hampel filter -> Fusion (ICMP+IRTT weighted average) -> EWMA smoothing -> delta calculation.
- **D-12:** Document IRTT vs ICMP measurement paths with correctness rationale for each.
- **D-13:** Validate reflector selection logic in `reflector_scorer.py` -- scoring criteria and min_score threshold.

### Queue Depth Baseline (NETENG-05)
- **D-14:** Capture `tc -s qdisc show` at BOTH idle AND under load (during benchmark run). Shows operating range.
- **D-15:** Use existing `wanctl-benchmark` / flent tooling for load generation during capture.

### Production VM Access (carried from Phase 112)
- **D-16:** SSH inline commands from workstation to cake-shaper at 10.10.110.223.
- **D-17:** MikroTik REST API at 10.10.99.1 for router data (mangle rules, routing tables).

### Claude's Discretion
- Findings report structure and section ordering
- Level of detail in signal chain documentation (high-level flow vs code-line-level tracing)
- Whether to capture tc -s stats for both WANs separately or combined

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### CAKE Configuration
- `src/wanctl/cake_params.py` -- CAKE parameter definitions and defaults
- `src/wanctl/check_cake.py` -- Existing CAKE verification CLI tool
- `src/wanctl/backends/linux_cake.py` -- Linux CAKE backend (tc command construction)
- `src/wanctl/backends/linux_cake_adapter.py` -- CAKE adapter for controller integration
- `docs/CONFIG_SCHEMA.md` -- Configuration reference

### Steering
- `src/wanctl/steering/daemon.py` -- Steering daemon main loop
- `src/wanctl/steering/steering_confidence.py` -- Confidence scoring weights and logic
- `src/wanctl/steering/congestion_assessment.py` -- Congestion detection for steering
- `src/wanctl/steering/cake_stats.py` -- CAKE statistics reader for steering

### Measurement / Signal Processing
- `src/wanctl/signal_processing.py` -- Hampel filter and signal chain
- `src/wanctl/reflector_scorer.py` -- Reflector selection and scoring
- `src/wanctl/rtt_measurement.py` -- RTT measurement (ICMP + IRTT paths)
- `src/wanctl/baseline_rtt_manager.py` -- Baseline RTT freeze/update logic
- `src/wanctl/autorate_continuous.py` -- Main controller with fusion logic

### Production Config
- `/etc/wanctl/spectrum.yaml` -- Production Spectrum WAN config (on cake-shaper VM)
- `/etc/wanctl/att.yaml` -- Production ATT WAN config (on cake-shaper VM)

### Prior Phase Context
- `.planning/phases/112-foundation-scan/112-CONTEXT.md` -- Phase 112 decisions (SSH access, VM details)
- `.planning/phases/112-foundation-scan/112-02-findings.md` -- VM security audit (systemd units, permissions)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `wanctl-check-cake` CLI tool: already verifies CAKE params against config, can run on production VM
- `wanctl-check-config` CLI tool: validates config YAML
- `wanctl-benchmark` CLI tool: runs flent benchmarks with FORCE_OUT routing
- MikroTik REST API client (`routeros_rest.py`): proven REST API access to router

### Established Patterns
- CAKE params defined as dataclass in `cake_params.py` with per-WAN overrides from YAML
- Signal chain: raw measurement -> Hampel outlier filter -> Fusion (ICMP+IRTT weighted) -> EWMA smoothing
- Steering uses congestion assessment from autorate state files (inter-process communication via JSON)
- `tc -j qdisc show` for JSON machine-readable CAKE readback

### Integration Points
- Production YAML configs at `/etc/wanctl/{spectrum,att}.yaml` (sudo required to read)
- MikroTik router at 10.10.99.1 (REST API, password in `/etc/wanctl/secrets`)
- CAKE qdiscs on bridge interfaces (spectrum: br-spectrum, att: br-att)
- State files at `/var/lib/wanctl/` for inter-process steering data

</code_context>

<specifics>
## Specific Ideas

No specific requirements -- standard network engineering audit with the decisions captured above.

</specifics>

<deferred>
## Deferred Ideas

None -- discussion stayed within phase scope.

</deferred>

---

*Phase: 113-network-engineering-audit*
*Context gathered: 2026-03-26*
