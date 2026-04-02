# Phase 125: Boot Resilience - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md -- this log preserves the alternatives considered.

**Date:** 2026-04-02
**Phase:** 125-boot-resilience
**Areas discussed:** Failure behavior, Script vs inline, Systemd cleanup, Ethtool scope, Reboot test strategy

---

## Failure Behavior

| Option | Description | Selected |
|--------|-------------|----------|
| Block startup (Requires=) | wanctl won't start without tuned NICs. Forces investigation. | |
| Warn but start (Wants=) | wanctl starts with degraded NIC settings. Relies on validation. | |
| You decide | Claude picks based on production context | ✓ |

**User's choice:** You decide
**Notes:** Claude leaning toward Wants= -- running with suboptimal settings better than not running.

---

## Script vs Inline

| Option | Description | Selected |
|--------|-------------|----------|
| Shell script (Recommended) | Move to /usr/local/bin/wanctl-nic-tuning.sh for logging, idempotency, error handling | ✓ |
| Keep inline ExecStart | Add ExecStartPre checks and -/ prefixes. Simpler but less capable. | |

**User's choice:** Shell script (Recommended)
**Notes:** Follows same pattern as wanctl-recovery.sh.

---

## Systemd Cleanup

| Option | Description | Selected |
|--------|-------------|----------|
| deploy/ is canonical | Keep deploy/systemd/ as source of truth. Remove systemd/ dir. | |
| Merge into systemd/ | Move hardened versions to systemd/. deploy/ for scripts only. | |
| You decide | Claude picks cleanest structure | ✓ |

**User's choice:** You decide
**Notes:** Two copies of wanctl@.service have diverged. deploy/ version is hardened and deployed.

---

## Ethtool Scope

| Option | Description | Selected |
|--------|-------------|----------|
| Current set is complete | Ring buffers + GRO forwarding + IRQ affinity covers known optimizations | |
| Audit and capture all | Read current ethtool settings from production and persist non-defaults | ✓ |

**User's choice:** Audit and capture all
**Notes:** May discover optimizations not yet in the unit file.

---

## Reboot Test Strategy

| Option | Description | Selected |
|--------|-------------|----------|
| Late-night reboot | Schedule for 2-4am CDT. Brief CAKE shaping outage acceptable. | |
| Dry-run first | Validate statically first (systemd-analyze, manual script run), then schedule reboot. | ✓ |
| You decide | Claude picks safest approach | |

**User's choice:** Dry-run first
**Notes:** Two-step: static validation without reboot, then scheduled reboot as confidence check.

---

## Claude's Discretion

- Failure mode: Requires= vs Wants= for NIC tuning dependency
- Systemd directory structure reconciliation
- Specific ethtool settings beyond current set (determined by audit)

## Deferred Ideas

- Steering service version sync (v1.23 -> v1.24)
