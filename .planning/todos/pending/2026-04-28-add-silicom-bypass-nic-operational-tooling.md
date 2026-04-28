---
created: 2026-04-28T19:56:51.002Z
title: Add Silicom bypass NIC operational tooling
area: operations
files:
  - docs/SILICOM-BYPASS.md
  - scripts/silicom-bypass (planned)
  - deploy/systemd/silicom-bypass-watchdog@.service (planned)
  - deploy/systemd/silicom-bypass-init.service (planned)
---

## Problem

The Silicom PE2G4BPI35A-SD bypass NIC on `cake-shaper` (passed through from
`odin`) is installed and the kernel module loads, but the card is not being
used per its design intent. Two operational gaps:

1. **No watchdog-driven fail-open.** The card's intended use is to fire its
   bypass relays when a software heartbeat stops (VM hang, kernel panic,
   userspace daemon death). With the card still powered, this works correctly
   — validated by the powered live-bypass test on 2026-04-28. The card is
   currently sitting unused in this mode.

2. **No manual toggle for maintenance.** No supported way to put the ATT pair
   into bypass before a planned VM reboot or maintenance window. Today the
   only path is `bpctl_util att-modem set_bypass on` typed by hand, with no
   safety guard, no status reporting, and no coordination with reboot/restart.

Background: full RCA of the card and platform behavior is in
`docs/SILICOM-BYPASS.md`. Key constraint — this card cannot do unpowered
fail-open on this platform (monostable relays, `AuxCurrent=0mA` on PCIe
power-mgmt cap). Powered watchdog bypass works. Unpowered fail-open does not.
That constraint is settled and not in scope to retest here.

`odin` is already on UPS and modems are on battery, so unpowered fail-open is
already covered architecturally without this card. Watchdog and manual-toggle
are the remaining underutilized capabilities.

## Solution

Three components, all on `cake-shaper`, deployed from this repo:

1. **`silicom-bypass` CLI wrapper** (`scripts/silicom-bypass`, bash):
   - Subcommands: `status`, `on`, `off`, `arm`, `disarm`
   - Idempotent. Refuses non-bypass-capable interfaces.
   - `on` requires `--yes` flag (live bypass drops Linux bridge carrier).

2. **`silicom-bypass-watchdog@.service`** (systemd template per pair):
   - Heartbeat loop: `set_bypass_wd 10000` then `reset_bypass_wd` every
     3000ms. Process death → relay fires bypass after 10s.
   - `Restart=on-failure`, journal-only logging.
   - Off-by-default after install. Operator opts in via
     `systemctl enable --now silicom-bypass-watchdog@att-modem`.

3. **`silicom-bypass-init.service`** (oneshot at boot):
   - Applies known-good baseline: `set_dis_bypass off`, `set_bypass_pwoff on`,
     `set_bypass_pwup off`, `set_disc_pwup off`, `set_std_nic off`.
   - Runs after `bpctl_mod` load and after `att-modem` / `att-router`
     interfaces exist. Verifies state on completion.

Config: `/etc/silicom-bypass.conf` with `WD_TIMEOUT_MS=10000`,
`HEARTBEAT_MS=3000`, `PAIR=att-modem`.

**Initial scope:** ATT pair only. `sil-spare1`/`sil-spare2` excluded — no
traffic, no benefit, added risk.

**Out of scope:**
- Integration with wanctl Python control loop. Bypass = path skips Linux
  entirely; wanctl has no role in that data path.
- Any retest of unpowered fail-open. Settled per RCA.

**Open questions for plan phase:**
- Test warm-reboot bypass preservation on the spare pair before relying on
  manual toggle for VM reboots? Hard reboot won't preserve, warm reboot might.
- Expose bypass state via wanctl health endpoint as observability-only signal
  (no control coupling)?
- Reuse `scripts/install.sh` deployment flow, or keep this as a separate
  installer to avoid coupling bypass tooling to wanctl release cadence?

Recommended defaults (carry into plan phase unless changed):
- Repo location: `wanctl/scripts/` + `wanctl/deploy/systemd/`
- WD timeout: 10000ms (3× margin on 3000ms heartbeat)
- Default boot state: watchdog off (operator opt-in)
- Manual `on`: `--yes` required
- Logging: journal only

Source: SILICOM-BYPASS.md RCA session 2026-04-28.
