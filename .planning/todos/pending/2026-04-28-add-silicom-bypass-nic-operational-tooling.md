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
used per its design intent. As of 2026-04-28 both ATT and Spectrum WANs run
through the card (Spectrum migrated to the formerly-spare `sil-spare1` /
`sil-spare2` pair). Three operational gaps:

1. **No watchdog-driven fail-open.** The card's intended use is to fire its
   bypass relays when a software heartbeat stops (VM hang, kernel panic,
   userspace daemon death). With the card still powered, this works correctly
   — validated by the powered live-bypass test on 2026-04-28. The card is
   currently sitting unused in this mode for both pairs.

2. **No manual toggle for maintenance.** No supported way to put either pair
   into bypass before a planned VM reboot or maintenance window. Today the
   only path is `bpctl_util <pair> set_bypass on` typed by hand, with no
   safety guard, no status reporting, and no coordination with reboot/restart.

3. **No structured failure-injection or A/B test affordances.** The card's
   `set_disc` (clean simulated cable pull) and `set_bypass` (host-out-of-path,
   raw ISP) modes turn it into a scriptable WAN test rig, but using them today
   means raw `bpctl_util` invocations with no logging of what state the test
   ran under.

Background: full RCA of the card and platform behavior is in
`docs/SILICOM-BYPASS.md`. Key constraint — this card cannot do unpowered
fail-open on this platform (monostable relays, `AuxCurrent=0mA` on PCIe
power-mgmt cap). Powered watchdog bypass works. Unpowered fail-open does not.
That constraint is settled and not in scope to retest here.

`odin` is already on UPS and modems are on battery, so unpowered fail-open is
already covered architecturally without this card. Watchdog, manual-toggle,
and scriptable failure injection are the remaining underutilized capabilities.

## Solution

Three components, all on `cake-shaper`, deployed from this repo:

1. **`silicom-bypass` CLI wrapper** (`scripts/silicom-bypass`, bash):
   - Subcommands:
     - `status [pair|all]` — print get_bypass / get_disc / get_std_nic / WD
       state for one or all pairs
     - `on <pair>` — set_bypass on (host out, ports bridged via relay)
     - `off <pair>` — set_bypass off + set_disc off (return to NIC mode)
     - `disc <pair>` — set_disc on (simulated cable pull, both PHYs dark)
     - `conn <pair>` — set_disc off (restore link)
     - `arm <pair> [timeout_ms]` — set_bypass_wd (arm watchdog)
     - `disarm <pair>` — set_bypass_wd 0
     - `mark <label>` — log current state of all pairs to journal with a
       caller-supplied label, for test-run boundary capture
   - Idempotent. Refuses non-bypass-capable interfaces.
   - `on` requires `--yes` flag (live bypass drops Linux bridge carrier).
   - `disc` requires `--yes` flag (kills WAN on that pair until restored).
   - **Both-WAN safety:** if a destructive op (`on` or `disc`) would put both
     pairs simultaneously into a non-NIC state, require an extra
     `--both-wan-confirm` flag. Prevents typo-induced full WAN loss.

2. **`silicom-bypass-watchdog@.service`** (systemd template, one instance per
   pair, deployed for both `att-modem` and `sil-spare1`):
   - Heartbeat loop: `set_bypass_wd 10000` then `reset_bypass_wd` every
     3000ms. Process death → relay fires bypass after 10s.
   - `Restart=on-failure`, journal-only logging.
   - Off-by-default after install. Operator opts in per pair via
     `systemctl enable --now silicom-bypass-watchdog@<pair>`.

3. **`silicom-bypass-init.service`** (oneshot at boot):
   - Applies known-good baseline to **both pairs**: `set_dis_bypass off`,
     `set_bypass_pwoff on`, `set_bypass_pwup off`, `set_disc_pwup off`,
     `set_std_nic off`.
   - Runs after `bpctl_mod` load and after `att-modem` / `att-router` /
     `sil-spare1` / `sil-spare2` interfaces exist. Verifies state on completion.

Config: `/etc/silicom-bypass.conf` with `WD_TIMEOUT_MS=10000`,
`HEARTBEAT_MS=3000`, `PAIRS="att-modem sil-spare1"`.

**Scope:** Both WAN pairs (ATT and Spectrum). Original "ATT only" constraint
is obsolete after the 2026-04-28 Spectrum migration onto the Silicom card.

**Out of scope (handled by separate todo):**
- Test orchestration / A/B harness composing these CLI verbs into experiments.
  Tracked in `2026-04-28-add-silicom-bypass-test-harness.md`. This todo
  delivers the verbs; that one builds experiments on top.
- Integration with wanctl Python control loop. Bypass = path skips Linux
  entirely; wanctl has no role in that data path.
- Any retest of unpowered fail-open. Settled per RCA.

**Open questions for plan phase:**
- Test warm-reboot bypass preservation on `sil-spare1` (Spectrum) before
  relying on manual toggle for VM reboots — hard reboot won't preserve, warm
  reboot might. With Spectrum now on the card, this is the only safe pair to
  test against (ATT is the canary in many other workstreams).
- Expose bypass state via wanctl health endpoint as observability-only signal
  (no control coupling)?
- Reuse `scripts/install.sh` deployment flow, or keep this as a separate
  installer to avoid coupling bypass tooling to wanctl release cadence?
- `mark` subcommand output destination: journal only, or also append to
  `/var/log/silicom-bypass-marks.log` for easy `grep` during test analysis?

Recommended defaults (carry into plan phase unless changed):
- Repo location: `wanctl/scripts/` + `wanctl/deploy/systemd/`
- WD timeout: 10000ms (3× margin on 3000ms heartbeat)
- Default boot state: watchdog off (operator opt-in per pair)
- Manual `on` and `disc`: `--yes` required
- Both-WAN destructive op: extra `--both-wan-confirm` required
- Logging: journal only for state changes; `mark` may also write to flat log

Source: SILICOM-BYPASS.md RCA session 2026-04-28.
