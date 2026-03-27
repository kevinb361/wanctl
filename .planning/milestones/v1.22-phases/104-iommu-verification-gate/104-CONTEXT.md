# Phase 104: IOMMU Verification Gate - Context

**Gathered:** 2026-03-24
**Status:** Ready for planning

<domain>
## Phase Boundary

Verify that all 4 target NICs on Proxmox host odin are in separate IOMMU groups, confirming PCIe passthrough feasibility for the CAKE offload VM. This is a prerequisite gate -- no code, no software changes. Pass = proceed with v1.21. Fail = apply fallback.

</domain>

<decisions>
## Implementation Decisions

### Verification Method
- **D-01:** SSH to odin and read `/sys/kernel/iommu_groups/` to map PCI addresses to IOMMU groups
- **D-02:** Target NICs: nic0 (i210, 08:00.0), nic1 (i210, 09:00.0), nic2 (i350, 0c:00.0), nic3 (i350, 0c:00.1)

### Fallback Strategy
- **D-03:** If IOMMU groups are shared, first fallback is ACS override patch (`pcie_acs_override=downstream` kernel parameter). This is a common homelab approach that slightly reduces PCI isolation safety but is acceptable for a home network environment.
- **D-04:** If ACS override is insufficient, secondary fallback is swapping to X552 10GbE NICs (nic6/nic7, IOMMU groups 43/44).
- **D-05:** Abort milestone only as last resort if no NIC combination provides clean passthrough.

### Claude's Discretion
- Documentation format for IOMMU verification results
- Whether to script the check or run manually

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Infrastructure
- `.planning/research/PITFALLS.md` -- IOMMU group pitfalls (especially i350 multi-port sharing)
- `.planning/research/ARCHITECTURE.md` -- NIC passthrough plan with PCI addresses
- `.planning/research/STACK.md` -- VM provisioning stack (Proxmox VFIO workflow)

### Project Memory
- `~/.claude/projects/-home-kevin-projects-wanctl/memory/project_cake_offload_milestone.md` -- Detailed NIC/IOMMU mapping and passthrough plan

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- None -- this phase is pure infrastructure verification, no code involved

### Established Patterns
- None applicable

### Integration Points
- Phase 104 result gates all subsequent phases (105-110)
- Phase 109 (VM Infrastructure) directly consumes the verified PCI addresses and IOMMU group mappings

</code_context>

<specifics>
## Specific Ideas

- odin is Supermicro X10SDV-TP8F, Xeon D-1518, 8 NICs total
- All NICs believed to be in separate IOMMU groups per prior investigation
- i350 4-port cards are known for shared groups -- must verify empirically
- Proxmox host IP: 10.10.110.124

</specifics>

<deferred>
## Deferred Ideas

### Reviewed Todos (not folded)
- "Investigate LXC container network optimizations" -- out of scope, relates to old container topology being replaced by this milestone

</deferred>

---

*Phase: 104-iommu-verification-gate*
*Context gathered: 2026-03-24*
