# Phase 104: IOMMU Verification Gate - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md -- this log preserves the alternatives considered.

**Date:** 2026-03-24
**Phase:** 104-iommu-verification-gate
**Areas discussed:** Fallback if IOMMU fails

---

## Fallback if IOMMU Fails

| Option | Description | Selected |
|--------|-------------|----------|
| ACS override patch | Kernel parameter pcie_acs_override=downstream -- common homelab approach | ✓ |
| Swap to X552 10GbE NICs | Use nic6/nic7 instead -- more bandwidth, different cabling | |
| Abort milestone | Defer CAKE offload entirely if passthrough isn't possible | |

**User's choice:** ACS override patch
**Notes:** Pragmatic choice for homelab environment. Slightly reduces PCI isolation safety but acceptable for home network.

---

## Claude's Discretion

- Documentation format and scripting approach for IOMMU verification

## Deferred Ideas

- "Investigate LXC container network optimizations" todo reviewed, not folded (out of scope)
