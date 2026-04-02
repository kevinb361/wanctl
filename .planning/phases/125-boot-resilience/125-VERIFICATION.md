---
phase: 125-boot-resilience
verified: 2026-04-02T16:00:00Z
status: human_needed
score: 3/4 must-haves verified
re_verification: false
human_verification:
  - test: "Reboot cake-shaper VM and confirm full boot chain"
    expected: "bridges up -> NIC tuning oneshot runs -> wanctl@spectrum and wanctl@att start with CAKE qdiscs initialized -> recovery timer active, all confirmed via systemctl status"
    why_human: "Actual reboot was deferred to Phase 126 / low-traffic window per D-05. Cannot verify end-to-end boot behavior programmatically without rebooting the production VM."
  - test: "Update REQUIREMENTS.md checkboxes for BOOT-03 and BOOT-04"
    expected: "BOOT-03 checked [x] (code is wired), BOOT-04 updated with reboot-deferred note or checked after reboot passes"
    why_human: "REQUIREMENTS.md shows BOOT-03 [ ] and BOOT-04 [ ] even though BOOT-03 is fully implemented in code. The tracking file was never updated post-completion."
---

# Phase 125: Boot Resilience Verification Report

**Phase Goal:** cake-shaper VM fully self-configures after reboot -- NIC optimizations are applied automatically before wanctl starts, with correct systemd dependency ordering across the entire boot chain
**Verified:** 2026-04-02
**Status:** human_needed
**Re-verification:** No -- initial verification

## Goal Achievement

### Observable Truths

All truths are from the PLAN must_haves frontmatter (Plans 01 and 02 combined).

| #  | Truth | Status | Evidence |
|----|-------|--------|----------|
| 1  | NIC tuning shell script applies ring buffers, rx-udp-gro-forwarding, and IRQ affinity to all 4 bridge NICs | ✓ VERIFIED | `deploy/scripts/wanctl-nic-tuning.sh`: ens16/ens17/ens27/ens28 present, RING_RX=RING_TX=4096, `ethtool -K ... rx-udp-gro-forwarding on`, `smp_affinity_list` with per-NIC CPU pinning |
| 2  | Script logs every action to journal via logger -t wanctl-nic-tuning | ✓ VERIFIED | TAG="wanctl-nic-tuning"; 9 `logger -t "$TAG"` calls covering start, per-NIC ring, GRO, IRQ affinity, warnings, and completion |
| 3  | Script handles missing NICs gracefully (warns, continues, does not fail) | ✓ VERIFIED | `ip link show "$nic"` check with `return 0` on failure; all tuning functions return 0; `exit 0` unconditionally at end |
| 4  | Script is idempotent (safe to re-run with identical results) | ✓ VERIFIED | ethtool commands re-apply same settings; failures logged as warnings and do not propagate; confirmed by production dry-run (0 errors on second run) |
| 5  | systemd service unit calls shell script instead of raw ExecStart lines | ✓ VERIFIED | `wanctl-nic-tuning.service`: exactly 1 `ExecStart=/usr/local/bin/wanctl-nic-tuning.sh`; 0 raw ethtool commands remain |
| 6  | wanctl@spectrum and wanctl@att wait for NIC tuning to complete before starting | ✓ VERIFIED | `deploy/systemd/wanctl@.service` line 4: `After=network-online.target systemd-networkd-wait-online.service wanctl-nic-tuning.service`; line 5: `Wants=network-online.target wanctl-nic-tuning.service` |
| 7  | deploy.sh deploys both the NIC tuning script and service unit to the target | ✓ VERIFIED | `deploy_nic_tuning_script()` function present and called at line 524; `SYSTEMD_FILES` includes `deploy/systemd/wanctl-nic-tuning.service` |
| 8  | The old systemd/wanctl@.service is removed; deploy/systemd/ is the canonical location | ✓ VERIFIED | `systemd/` directory absent from filesystem; git commit d6914be removed both `systemd/wanctl@.service` and `systemd/steering.service` |
| 9  | Full boot chain is verified: bridges -> NIC tuning -> wanctl (CAKE) -> recovery timer | ? PARTIAL | Systemd dependency ordering is wired correctly (dry-run confirmed); actual VM reboot deferred per D-05 |

**Score:** 8/9 truths fully verified; truth #9 requires human/reboot test

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `deploy/scripts/wanctl-nic-tuning.sh` | Idempotent NIC tuning with logging and error handling | ✓ VERIFIED | 117 lines, bash syntax valid, executable, 9 logger calls, all 4 NICs, ring buffers via constants, IRQ affinity, always exit 0 |
| `deploy/systemd/wanctl-nic-tuning.service` | systemd oneshot calling the shell script | ✓ VERIFIED | Single ExecStart, Type=oneshot, RemainAfterExit=yes, hardening preserved, Before= wanctl@spectrum/att/steering |
| `deploy/systemd/wanctl@.service` | Hardened wanctl service template with NIC tuning dependency | ✓ VERIFIED | After= and Wants= include wanctl-nic-tuning.service; full hardening (CapabilityBoundingSet, MemoryMax=512M, SystemCallFilter, etc.) preserved |
| `scripts/deploy.sh` | Deployment script including NIC tuning script and service | ✓ VERIFIED | 6 references to wanctl-nic-tuning; deploy_nic_tuning_script() function + call at line 524; SYSTEMD_FILES updated to deploy/systemd/ paths; bash syntax valid |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `deploy/systemd/wanctl-nic-tuning.service` | `deploy/scripts/wanctl-nic-tuning.sh` | ExecStart=/usr/local/bin/wanctl-nic-tuning.sh | ✓ WIRED | gsd-tools: pattern found in source |
| `deploy/systemd/wanctl@.service` | `deploy/systemd/wanctl-nic-tuning.service` | After= and Wants= directives | ✓ WIRED | gsd-tools: pattern found; confirmed by `grep 'After='` showing exact service name |
| `scripts/deploy.sh` | `deploy/scripts/wanctl-nic-tuning.sh` | scp to /usr/local/bin/ | ✓ WIRED | gsd-tools: wanctl-nic-tuning.sh in scp command with /usr/local/bin/ target |
| `scripts/deploy.sh` | `deploy/systemd/wanctl-nic-tuning.service` | SYSTEMD_FILES array | ✓ WIRED | gsd-tools: wanctl-nic-tuning.service in SYSTEMD_FILES array |

All 4 key links verified.

### Data-Flow Trace (Level 4)

Not applicable. This phase produces bash scripts and systemd unit files, not components that render dynamic data.

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| NIC tuning script has valid bash syntax | `bash -n deploy/scripts/wanctl-nic-tuning.sh` | Exit 0 | ✓ PASS |
| deploy.sh has valid bash syntax | `bash -n scripts/deploy.sh` | Exit 0 | ✓ PASS |
| Script is executable | `test -x deploy/scripts/wanctl-nic-tuning.sh` | True | ✓ PASS |
| NIC tuning service has exactly 1 ExecStart | `grep -c 'ExecStart=' deploy/systemd/wanctl-nic-tuning.service` | 1 | ✓ PASS |
| wanctl@.service After= includes NIC tuning | `grep 'After=' deploy/systemd/wanctl@.service` | Contains wanctl-nic-tuning.service | ✓ PASS |
| Old systemd/ directory removed | `test ! -d systemd/` | True | ✓ PASS |
| Full VM reboot produces working chain | (requires rebooting 10.10.110.223) | NOT RUN | ? SKIP — deferred per D-05 |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| BOOT-01 | 125-01 | All 4 bridge NICs have ethtool optimizations persisted and applied at boot before wanctl starts | ✓ SATISFIED | Script applies ring 4096, rx-udp-gro-forwarding, IRQ affinity for ens16/17/27/28; service runs Before=wanctl@spectrum |
| BOOT-02 | 125-01 | NIC tuning oneshot is idempotent, logs what was applied, and fails gracefully if a NIC is missing | ✓ SATISFIED | `ip link show` guard + `return 0` on missing NIC; 9 logger calls; always `exit 0`; dry-run confirmed 0 errors on repeat run |
| BOOT-03 | 125-02 | wanctl services have explicit systemd dependency on NIC tuning completion | ✓ SATISFIED | `deploy/systemd/wanctl@.service`: `After=...wanctl-nic-tuning.service` and `Wants=...wanctl-nic-tuning.service`; dry-run systemd-analyze verify passed |
| BOOT-04 | 125-02 | Full boot chain works end-to-end: bridges up -> NIC tuning -> wanctl (CAKE) -> recovery timer | ? PARTIAL | Systemd ordering wired and dry-run verified; actual reboot test deferred to Phase 126/low-traffic window per D-05 |

**REQUIREMENTS.md tracking discrepancy:** The file shows BOOT-03 [ ] and BOOT-04 [ ] (both Pending). BOOT-03 is fully implemented in code and should be [x]. BOOT-04 is legitimately partial (reboot deferred). The traceability table was never updated after Phase 125 completed.

### Anti-Patterns Found

None. Scanned `deploy/scripts/wanctl-nic-tuning.sh`, `deploy/systemd/wanctl-nic-tuning.service`, `deploy/systemd/wanctl@.service`, and `scripts/deploy.sh` for TODO/FIXME/placeholder/stub patterns. Clean.

### Human Verification Required

#### 1. Reboot Test (BOOT-04 completion gate)

**Test:** Schedule a low-traffic window, then: `ssh kevin@10.10.110.223 'sudo reboot'`. After VM comes back:
```bash
ssh kevin@10.10.110.223 'systemctl status wanctl-nic-tuning wanctl@spectrum wanctl@att --no-pager'
ssh kevin@10.10.110.223 'journalctl -t wanctl-nic-tuning --no-pager -n 20'
ssh kevin@10.10.110.223 'sudo tc qdisc show dev br-spectrum; sudo tc qdisc show dev br-att'
```

**Expected:** wanctl-nic-tuning.service shows `active (exited)` with journal entries for all 4 NICs; wanctl@spectrum and wanctl@att are active/running; CAKE qdiscs are present on br-spectrum and br-att.

**Why human:** Production VM reboot cannot be performed programmatically. Requires scheduling a maintenance window.

#### 2. REQUIREMENTS.md Checkbox Update

**Test:** Update `.planning/REQUIREMENTS.md` to mark BOOT-03 as complete:
- Line 14: change `- [ ] **BOOT-03**` to `- [x] **BOOT-03**`
- Line 38-41 traceability table: change BOOT-03 status from "Pending" to "Complete"

**Expected:** BOOT-03 checkbox is [x]; BOOT-04 remains [ ] until reboot test passes.

**Why human:** Documentation update should be intentional; requires confirming the reboot gate for BOOT-04 before marking the traceability table.

### Gaps Summary

No blocking gaps. All code artifacts exist, are substantive, and are correctly wired. The one outstanding item is BOOT-04 (end-to-end reboot test), which was intentionally deferred per D-05 decision in the planning context. The phase is functionally complete for all automated-verifiable requirements.

Minor tracking issue: REQUIREMENTS.md was not updated after phase completion — BOOT-03 should be [x] (the wiring is done) and the traceability table needs updating.

---

_Verified: 2026-04-02_
_Verifier: Claude (gsd-verifier)_
