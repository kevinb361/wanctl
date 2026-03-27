---
phase: 109-vm-infrastructure-bridges
verified: 2026-03-25T00:00:00Z
status: human_needed
score: 4/5 must-haves verified
human_verification:
  - test: "Confirm health endpoint responds on 10.10.110.223:9101 after wanctl daemon is started"
    expected: "curl -s http://10.10.110.223:9101/health returns JSON with status fields"
    why_human: "Health endpoint requires wanctl daemon running — daemon not yet started in Phase 109 (Phase 110 concern)"
  - test: "Confirm IRTT connectivity from dallas to cake-shaper (10.10.110.223:2112)"
    expected: "irtt client can reach port 2112 on 10.10.110.223 when irtt daemon is started"
    why_human: "IRTT daemon installation and startup not completed in Phase 109; INFR-06 partially covers this"
  - test: "Confirm ICMP reachability of 10.10.110.223 from the management network"
    expected: "ping 10.10.110.223 succeeds with normal RTTs"
    why_human: "ICMP reachability requires physical network connectivity — cannot verify from codebase"
---

# Phase 109: VM Infrastructure & Bridges Verification Report

**Phase Goal:** A production-ready Debian 12 VM on odin with passthrough NICs, transparent bridges, and CAKE initialized on bridge member port egress
**Verified:** 2026-03-25
**Status:** human_needed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Proxmox VM runs Debian 12 with 4 VFIO-passthrough NICs (2x i210, 2x i350) visible inside the guest | VERIFIED | VM_INFRASTRUCTURE.md Section 2: NIC discovery output shows ens16/ens17 (device 0x1533=i210) and ens27/ens28 (device 0x1521=i350); commit 964c335 records actual verification |
| 2 | Transparent L2 bridges (br-spectrum, br-att) forward traffic with STP disabled and forward_delay=0 | VERIFIED | VM_INFRASTRUCTURE.md Section 3 verification results (2026-03-25): STP=0, forward_delay=0 on both bridges; commit 7b09033 |
| 3 | CAKE qdisc is attached and shaping traffic on bridge member port egress via `tc qdisc replace` (not systemd-networkd CAKE section) | VERIFIED | VM_INFRASTRUCTURE.md Section 4 shows tc qdisc replace on ens17 and ens28; JSON stats "CAKE found: True" for both; explicit CAKE-NOT-in-systemd-networkd warning; commit c8a60b2 |
| 4 | systemd-networkd configuration persists bridges and interfaces across reboots (CAKE setup owned by wanctl startup, not systemd) | VERIFIED | VM_INFRASTRUCTURE.md Section 3: 9 config files documented, "Survived reboot: all config persisted"; explicit "CAKE is NOT configured via systemd-networkd" note referencing systemd #31226; commit 7b09033 |
| 5 | VLAN 110 management interface provides SSH, health endpoint, ICMP, and IRTT connectivity | PARTIAL | SSH verified (SSH output captured in plans 02/03/04). Health endpoint and IRTT require daemon startup — not done in Phase 109. ICMP requires physical network. Interface (ens18 at 10.10.110.223/24, VLAN 110) exists and is persistent. |

**Score:** 4/5 truths verified (1 partial — human verification needed for health/ICMP/IRTT)

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `docs/VM_INFRASTRUCTURE.md` | Production runbook documenting all infrastructure | VERIFIED | 386 lines, 5 sections, actual verification output captured for all plans; 5 commits spanning plans 01-04 |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `/etc/modprobe.d/vfio.conf` | vfio-pci driver binding for 4 NICs | initramfs rebuild + reboot | VERIFIED | Runbook Section 1 shows actual output: all 4 NICs on vfio-pci, ixgbe on management; documented in VM_INFRASTRUCTURE.md with `options vfio-pci ids=8086:1533,8086:1521` and `softdep igb pre: vfio-pci` |
| `10-br-spectrum.netdev` / `10-br-att.netdev` | Bridge devices with STP=false | systemd-networkd .netdev parsing | VERIFIED | All 9 files listed in VM_INFRASTRUCTURE.md Section 3 table; 2 .netdev files, 4 member .network files, 2 bridge .network files, 1 mgmt .network file |
| `20-*.network` Bridge= directives | Bridge member port enslavement (ens16/ens17/ens27/ens28) | Bridge= directive in .network file | VERIFIED | Documented in VM_INFRASTRUCTURE.md: RequiredForOnline=enslaved on member ports, RequiredForOnline=carrier on bridges |
| `tc qdisc replace dev ens17/ens28` | CAKE qdisc on router-side member ports | iproute2-6.15.0 + sch_cake module | VERIFIED | VM_INFRASTRUCTURE.md Section 4 shows actual tc output for ens17 and ens28 with bandwidth/diffserv/memlimit parameters; JSON verified |
| `wanctl@.service After=` | systemd-networkd-wait-online ordering | systemd ordering dependency | VERIFIED | VM_INFRASTRUCTURE.md Section 4: systemd ordering chain documented as `systemd-networkd → systemd-networkd-wait-online → wanctl@.service → initialize_cake()` |

### Data-Flow Trace (Level 4)

Not applicable — this is an infrastructure documentation phase. The artifact is a runbook (`docs/VM_INFRASTRUCTURE.md`), not a component that renders dynamic data. Data flows on remote hardware, not in this codebase.

### Behavioral Spot-Checks

Step 7b: SKIPPED — Infrastructure is on remote hardware (odin + cake-shaper VM). No runnable entry points exist in this codebase for the infrastructure. All verification was performed via SSH by the operator and documented in VM_INFRASTRUCTURE.md with captured output.

### Requirements Coverage

| Requirement | Source Plan(s) | Description | Status | Evidence |
|-------------|---------------|-------------|--------|----------|
| INFR-02 | 109-01, 109-02 | Proxmox VM with VFIO passthrough for 4 NICs (2x i210, 2x i350) | SATISFIED | VM_INFRASTRUCTURE.md Sections 1+2: VFIO binding verified (commit 964c335), NIC discovery ens16/ens17/ens27/ens28 (commit a251f30) |
| INFR-03 | 109-03 | Transparent L2 bridges (br-spectrum, br-att) with STP disabled, forward_delay=0 | SATISFIED | VM_INFRASTRUCTURE.md Section 3: br-spectrum (ens16+ens17), br-att (ens27+ens28), STP=0, forward_delay=0, no IP (commit 7b09033) |
| INFR-04 | 109-04 | CAKE qdisc initialized on bridge member port egress via `tc qdisc replace` | SATISFIED | VM_INFRASTRUCTURE.md Section 4: tc qdisc replace verified on ens17 and ens28, JSON stats parseable (commit c8a60b2) |
| INFR-05 | 109-03 | systemd-networkd persistent bridge and interface configuration (CAKE setup owned by wanctl, NOT systemd) | SATISFIED | VM_INFRASTRUCTURE.md Section 3: 9 config files, reboot survival verified, explicit CAKE-NOT-in-systemd-networkd note (commit 7b09033) |
| INFR-06 | 109-02, 109-03 | VLAN 110 management interface on virtio NIC for SSH/health/ICMP/IRTT | PARTIALLY SATISFIED | ens18 on VLAN 110, 10.10.110.223/24, SSH access verified through all 4 plans. Health endpoint and IRTT daemon startup are Phase 110 scope (daemon not yet enabled). |

**Orphaned requirements check:** No orphaned requirements. All 5 IDs (INFR-02 through INFR-06) are claimed by at least one plan and supported by evidence in the runbook.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `docs/VM_INFRASTRUCTURE.md` | 30 | "Modem vs router role within each NIC pair deferred to physical cabling (Phase 110)" | Info | Expected — modem/router role is determined at cable insertion time, not in software |
| REQUIREMENTS.md | 39-43 | All INFR-02 through INFR-06 still marked `- [ ]` (unchecked) | Warning | REQUIREMENTS.md checkboxes were not updated after phase completion — cosmetic only, not a functional gap |

No stub implementations found. This is a documentation phase; VM_INFRASTRUCTURE.md contains actual verification output (not placeholder text) for all 4 plans.

### Human Verification Required

#### 1. Health Endpoint Connectivity

**Test:** Start `wanctl@spectrum` service on cake-shaper and run: `curl -s http://10.10.110.223:9101/health | python3 -m json.tool`
**Expected:** JSON response with health status fields (service running, no errors)
**Why human:** Health endpoint requires the wanctl daemon to be running. The daemon was not started during Phase 109 (Phase 110 concern: production cutover includes enabling the service and configuring YAML).

#### 2. IRTT Daemon Reachability

**Test:** Install and start `irtt server` on cake-shaper, then from dallas: `irtt client 10.10.110.223:2112 --duration 5s`
**Expected:** IRTT measures RTT to cake-shaper with normal latencies
**Why human:** IRTT daemon installation and startup are not Phase 109 tasks. Phase 109 established the interface; IRTT setup is Phase 110 scope.

#### 3. ICMP Reachability from Management Network

**Test:** `ping -c 5 10.10.110.223` from any host on the 10.10.110.0/24 management VLAN
**Expected:** 5/5 packets returned with normal RTT
**Why human:** Requires physical network connectivity to the management switch. Cannot verify from code.

### Gaps Summary

No blocking gaps. The phase goal is substantively achieved: the runbook (`docs/VM_INFRASTRUCTURE.md`) documents all four infrastructure layers with captured verification output from the actual hardware. All 5 success criteria are either fully verified (4/5) or partially verified with the remaining portion clearly scoped to Phase 110 (health endpoint + IRTT daemon startup).

The status is `human_needed` rather than `passed` because Success Criterion 5 includes "health endpoint, ICMP, and IRTT connectivity" which cannot be verified from the codebase. The management interface itself is established and SSH-verified.

**Acceptable deviations applied:**
- Debian 13 (trixie) instead of Debian 12 — functionally equivalent, confirmed by operator
- VM ID 206 instead of 106 — backup numbering conflict avoidance, no functional impact
- IP 10.10.110.223 instead of 10.10.110.106 — user preference during Debian install
- Kernel 6.17.4-2-pve (not pinned) — user chose not to pin to avoid blocking security patches
- `ecn` keyword dropped from tc commands — not supported by iproute2-6.15.0; CAKE enables ECN by default

---

_Verified: 2026-03-25_
_Verifier: Claude (gsd-verifier)_
