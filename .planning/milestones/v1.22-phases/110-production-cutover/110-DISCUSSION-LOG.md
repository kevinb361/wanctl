# Phase 110: Production Cutover - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md -- this log preserves the alternatives considered.

**Date:** 2026-03-25
**Phase:** 110-production-cutover
**Areas discussed:** Physical Cabling, Config YAML, Rollback Strategy, Benchmark Validation

---

## Physical Cabling

| Option | Description | Selected |
|--------|-------------|----------|
| Direct connections | Modem straight into odin NIC, odin NIC straight into MikroTik. 4 cables, no switch. | ✓ |
| Through patch panel | Cables through patch panel | |
| Mix / other | Some direct, some through switch | |

**User's choice:** Direct connections
**Notes:** odin is physically near the router and both modems.

### Port Mapping

| Option | Description | Selected |
|--------|-------------|----------|
| Check router config | User requested Claude check the actual config | ✓ |

**User's choice:** "go check!" -- Claude found ether1-WAN-Spectrum and ether2-WAN-ATT from docs/EF_QUEUE_PROTECTION.md
**Notes:** Full topology confirmed: Spectrum modem -> ens16 -> br-spectrum -> ens17 -> ether1, ATT modem -> ens27 -> br-att -> ens28 -> ether2

---

## Config YAML

| Option | Description | Selected |
|--------|-------------|----------|
| Clone and modify | Copy existing configs, change transport + add cake_params | ✓ |
| Fresh minimal configs | Start from scratch | |
| Dual-mode single file | One config switchable between rest and linux-cake | |

**User's choice:** Clone and modify

### Steering

| Option | Description | Selected |
|--------|-------------|----------|
| Keep REST for steering | linux-cake for bandwidth + REST for steering mangle rules | ✓ |
| Disable steering initially | Focus on bandwidth control first | |
| Steering runs separately | Steering stays on old container | |

**User's choice:** Keep REST for steering

---

## Rollback Strategy

| Option | Description | Selected |
|--------|-------------|----------|
| Drill both levels | Test soft rollback (stop daemon + re-enable queues) AND hard rollback (recable) | ✓ |
| Level 1 only | Just soft rollback | |
| Level 2 only | Just hard rollback | |

**User's choice:** Drill both levels

### Drill Timing

| Option | Description | Selected |
|--------|-------------|----------|
| After ATT migration | Drill on live ATT traffic, Spectrum stays on MikroTik as safety net | ✓ |
| Before any migration | Drill with test traffic before production | |
| Both | Dry run then real | |

**User's choice:** After ATT migration

---

## Benchmark Validation

| Option | Description | Selected |
|--------|-------------|----------|
| Throughput + latency under load | RRUL throughput > 740Mbps AND latency comparable/better | ✓ |
| Throughput only | Just prove ceiling is higher | |
| Full RRUL suite | All metrics: throughput, latency, jitter, loss | |

**User's choice:** Throughput + latency under load

### Soak Time

| Option | Description | Selected |
|--------|-------------|----------|
| ATT: 1 hour, Both: 24 hours | ATT soaks 1h, then Spectrum. Both soak 24h before milestone. | ✓ |
| ATT: 15 min, Both: 4 hours | Quick validation | |
| ATT: 24 hours, Both: 7 days | Most conservative | |

**User's choice:** ATT: 1 hour, Both: 24 hours

### Baseline

| Option | Description | Selected |
|--------|-------------|----------|
| Yes, baseline before cabling | Run RRUL on each WAN while still on MikroTik | ✓ |
| Use existing historical data | Already have performance data | |

**User's choice:** Yes, baseline before cabling

---

## Claude's Discretion

- Exact order of operations within each WAN cutover
- Config deployment method
- Monitoring approach during soak
- Checkpoint placement

## Deferred Ideas

- Automated cutover script
- Health endpoint monitoring dashboard for cake-shaper
- Container decommission (keep as fallback until milestone close)
