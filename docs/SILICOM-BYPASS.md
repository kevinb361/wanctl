# Silicom Bypass NIC Runbook

Operational notes for the Silicom `PE2G4BPI35A-SD REV:1.1` bypass NIC in the
`cake-shaper` VM on `odin`.

## Hardware Model

- Card: Silicom `PE2G4BPI35A-SD REV:1.1`
- Driver/tool location on `cake-shaper`: `/opt/bpctl-silicom/`
- Utility: `/opt/bpctl-silicom/bpctl_util`
- Module: `/opt/bpctl-silicom/bpctl_mod.ko`
- DKMS module: `bpctl_mod/5.2.0.46`
- Device node: `/dev/bpctl0`
- Boot service: `bpctl-silicom.service`

## Boot Persistence

`cake-shaper` loads the Silicom control module at boot with a local oneshot
systemd unit:

```text
/etc/systemd/system/bpctl-silicom.service
/usr/local/sbin/wanctl-bpctl-init
```

The init script first loads `bpctl_mod` with `modprobe`, which uses the DKMS-built
module under `/lib/modules/.../updates/dkms/`. If no module-tree copy is
available, it falls back to `/opt/bpctl-silicom/bpctl_mod.ko`. It then waits for
`bpctl` to register in `/proc/devices`, recreates `/dev/bpctl0` with the
registered major number when needed, and verifies `bpctl_util info` succeeds.

The unit is enabled and ordered before the WAN controller services:

```text
Before=wanctl@att.service wanctl@spectrum.service
```

Verify after a VM reboot:

```bash
systemctl status bpctl-silicom.service --no-pager -l
ls -l /dev/bpctl0
lsmod | grep bpctl
cd /opt/bpctl-silicom
sudo ./bpctl_util att-modem get_bypass_slave
sudo ./bpctl_util spec-modem get_bypass_slave
```

This was validated on 2026-04-28 by forcing both ATT and Spectrum into powered
bypass, rebooting the `cake-shaper` VM, confirming `bpctl-silicom.service`
recreated `/dev/bpctl0`, then restoring both pairs to non-bypass inline mode.

## Kernel Upgrades And DKMS

`bpctl_mod` is an out-of-tree kernel module. It is registered with DKMS on
`cake-shaper` so kernel upgrades can rebuild it automatically when matching
headers are installed.

Current source and helper paths:

```text
/root/bpctl-src/bpctl-silicom
/usr/src/bpctl_mod-5.2.0.46
/usr/local/sbin/wanctl-bpctl-dkms-install
```

Repo source for the helper:

```text
scripts/wanctl-bpctl-dkms-install
```

Before rebooting into a newly installed kernel, verify DKMS built the module for
that kernel:

```bash
dkms status bpctl_mod
modinfo bpctl_mod | grep -E '^(filename|vermagic|name):'
```

If DKMS did not build it automatically, install the matching headers and rebuild:

```bash
sudo apt install dkms "linux-headers-$(uname -r)"
sudo /usr/local/sbin/wanctl-bpctl-dkms-install
```

After booting the new kernel, verify the control path before depending on
powered fail-open automation:

```bash
systemctl status bpctl-silicom.service --no-pager -l
systemctl status silicom-bypass-watchdog@att.service --no-pager -l
systemctl status silicom-bypass-watchdog@spectrum.service --no-pager -l
dkms status bpctl_mod
ls -l /dev/bpctl0
cd /opt/bpctl-silicom
sudo ./bpctl_util att-modem get_bypass_wd
sudo ./bpctl_util spec-modem get_bypass_wd
```

If `bpctl-silicom.service` fails after a kernel upgrade, assume the DKMS rebuild
failed or matching headers are missing. Until fixed, the WAN bridges may still
come up inline, but `bpctl` control and Silicom watchdog fail-open automation are
not available.

The source used here is from the public GitHub repository
`https://github.com/ddos-mitigator/bpctl-silicom`. It is not known to be an
official Silicom upstream, but the source contains BSD/GPL licensing notices and
the GitHub project accepts normal fork/pull-request workflows. Future
kernel-compatibility fixes should be proposed there first unless Silicom provides
an official public repository.

## Per-WAN Watchdog Fail-Open

Each WAN pair has an independent Silicom watchdog service:

```text
silicom-bypass-watchdog@att.service
silicom-bypass-watchdog@spectrum.service
```

The services use these local files on `cake-shaper`:

```text
/etc/systemd/system/silicom-bypass-watchdog@.service
/usr/local/sbin/wanctl-bpctl-watchdog-petter
/usr/local/sbin/wanctl-bpctl-watchdog-bypass
/etc/wanctl/bpctl-watchdog/att.env
/etc/wanctl/bpctl-watchdog/spectrum.env
```

Repo source files:

```text
deploy/systemd/bpctl-silicom.service
deploy/systemd/silicom-bypass-watchdog@.service
deploy/scripts/bpctl-watchdog-att.env.example
deploy/scripts/bpctl-watchdog-spectrum.env.example
scripts/wanctl-bpctl-init
scripts/wanctl-bpctl-dkms-install
scripts/wanctl-bpctl-watchdog-petter
scripts/wanctl-bpctl-watchdog-bypass
```

Current mapping:

```text
att.env: IFACE=att-modem, WANCTL_UNIT=wanctl@att.service
spectrum.env: IFACE=spec-modem, WANCTL_UNIT=wanctl@spectrum.service
```

The petter arms the hardware watchdog for bypass expiry, disables watchdog
autoreset, and resets the watchdog every second only while the paired
`wanctl@...` service is active. The requested timeout is 5000ms; the card rounds
this to a 6400ms hardware timeout because its watchdog uses fixed timer steps.

If a paired `wanctl@...` service stops, only that WAN pair is put into powered
bypass. When the `wanctl@...` service comes back, the petter restores that pair
to non-bypass inline mode and resumes watchdog resets.

Verify watchdog state:

```bash
systemctl status silicom-bypass-watchdog@att.service --no-pager -l
systemctl status silicom-bypass-watchdog@spectrum.service --no-pager -l
cd /opt/bpctl-silicom
sudo ./bpctl_util att-modem get_bypass_wd
sudo ./bpctl_util att-modem get_wd_exp_mode
sudo ./bpctl_util spec-modem get_bypass_wd
sudo ./bpctl_util spec-modem get_wd_exp_mode
```

Validated on 2026-04-28:

```text
Stopping wanctl@att.service put only ATT into bypass; Spectrum stayed inline.
Restarting wanctl@att.service restored ATT to inline mode.

Stopping wanctl@spectrum.service put only Spectrum into bypass; ATT stayed inline.
Restarting wanctl@spectrum.service restored Spectrum to inline mode.

Gracefully warm-rebooting odin stopped both watchdog services, put both pairs
into powered bypass, autostarted cake-shaper after host boot, and restored both
pairs to inline mode. A continuous external ping to 1.1.1.1 from the LAN did not
drop during the host reboot.
```

This is powered fail-open protection. It covers controller/service failure while
the VM, Proxmox host, and Silicom PCIe card remain powered. It does not change
the physical power-loss conclusion below: full `odin` power loss still drops the
card and cannot be solved by the internal watchdog.

If `/dev/bpctl0` is missing but the module is loaded and `/proc/devices` shows
`bpctl`, recreate it with the registered major number:

```bash
major=$(awk '$2 == "bpctl" {print $1}' /proc/devices)
sudo mknod /dev/bpctl0 c "$major" 0
sudo chmod 600 /dev/bpctl0
```

## LED Meanings

Each physical port `P0`/`P1`/`P2`/`P3` has three indicators:

- `LINK/ACT`: link/activity for the host-facing NIC path.
- `BYP`: bypass/fail-to-wire status.
- `DISC`: disconnect/fail-to-block status.

Known-good normal operation for a live WAN pair:

```text
LINK/ACT blinking
BYP off
DISC off
```

`BYP` or `DISC` lit while the host is powered and the WAN pair is expected to be
bridged through Linux means the pair is not in normal NIC mode.

## ATT Pair Mapping

- ATT modem side: `att-modem`, MAC `00:e0:ed:57:b6:84`
- ATT router side: `att-router`, MAC `00:e0:ed:57:b6:85`
- Control interface for the pair: `att-modem`
- Confirmed bypass slave: `att-modem` -> `att-router`

Known-good ATT software state:

```text
get_bypass: non-Bypass
get_disc: non-Disconnect
get_std_nic: not in Standard NIC mode
get_dis_bypass: Bypass mode enabled
get_dis_disc: Disconnect mode disabled
get_bypass_pwoff: Bypass at power off
get_bypass_pwup: non-Bypass at power up
get_disc_pwup: non-Disconnect at power up
```

Known-good ATT link state:

```text
att-modem  UP, LOWER_UP, 1Gbps
att-router UP, LOWER_UP, 1Gbps
br-att     UP, carrier
```

## Spectrum Pair Mapping

Spectrum was moved from the Supermicro I350 ports to the remaining Silicom pair
on 2026-04-28. The Silicom ports were then renamed to match the existing
Spectrum naming pattern.

- Spectrum modem side: `spec-modem`, MAC `00:e0:ed:57:b6:86`
- Spectrum router side: `spec-router`, MAC `00:e0:ed:57:b6:87`
- Control interface for the pair: `spec-modem`
- Confirmed bypass slave: `spec-modem` -> `spec-router`
- Old Spectrum ports are disconnected from `br-spectrum`:
  - `old-spec-modem`, MAC `ac:1f:6b:19:a9:9a`
  - `old-spec-router`, MAC `ac:1f:6b:19:a9:9b`

Persistent VM config now points Spectrum at the Silicom pair:

```text
/etc/systemd/network/10-wan-spare1.link: MAC 00:e0:ed:57:b6:86 -> Name=spec-modem
/etc/systemd/network/10-wan-spare2.link: MAC 00:e0:ed:57:b6:87 -> Name=spec-router
/etc/systemd/network/10-wan-spec-modem.link: MAC ac:1f:6b:19:a9:9a -> Name=old-spec-modem
/etc/systemd/network/10-wan-spec-router.link: MAC ac:1f:6b:19:a9:9b -> Name=old-spec-router
/etc/systemd/network/20-spec-modem.network: Name=spec-modem
/etc/systemd/network/20-spec-router.network: Name=spec-router
/etc/wanctl/spectrum.yaml: upload_interface="spec-modem"
/etc/wanctl/spectrum.yaml: download_interface="spec-router"
/etc/wanctl/spectrum.yaml: cake_params.ack_filter=false
/etc/wanctl/spectrum.yaml: cake_params.ingress=false
/etc/wanctl/spectrum.yaml: cake_params.rtt="1s"  # provisional mitigation
```

Backups from the migration are timestamped with `20260428150434` and
`20260428150917`.

Known-good Spectrum software state:

```text
get_bypass: non-Bypass
get_disc: non-Disconnect
get_dis_disc: Disconnect mode disabled
```

Known-good Spectrum link state:

```text
spec-modem  UP, LOWER_UP, 1Gbps
spec-router UP, LOWER_UP, 1Gbps
br-spectrum UP, carrier
```

## Spectrum Migration Validation And Pitfalls

Additional Spectrum migration diagnostics on 2026-04-28 isolated two separate
classes of symptoms:

- A severe download cap around `10-17 Mbps` was caused by reversed physical port
  roles relative to `spectrum.yaml`. The 32 Mbps upload CAKE qdisc was placed on
  the download egress path, so downloads were shaped as uploads.
- A later upload shortfall was not caused by the Silicom bridge path. After the
  raw bridge path was allowed to stabilize, Spectrum upload to the Dallas test
  host reached `38.9 Mbit/s` with CAKE and `wanctl@spectrum` removed from the
  path.

Use live byte counters to verify direction before assuming a hardware problem:

```bash
ip -s link show dev spec-modem
ip -s link show dev spec-router
tc -s qdisc show dev spec-modem
tc -s qdisc show dev spec-router
```

Expected direction in the current Silicom topology:

```text
Download: modem -> spec-modem RX -> br-spectrum -> spec-router TX -> RouterOS ether1-WAN-Spectrum
Upload:   RouterOS ether1-WAN-Spectrum -> spec-router RX -> br-spectrum -> spec-modem TX -> modem

CAKE download qdisc: spec-router
CAKE upload qdisc:   spec-modem
```

If the high-volume download test increments the upload qdisc, the cables or
`spectrum.yaml` interface roles are reversed. Fix the mapping before changing
rates, thresholds, or hardware.

### Stabilized Raw Bridge Test Procedure

Stopping `wanctl@spectrum.service` while `silicom-bypass-watchdog@spectrum` is
active intentionally lets the hardware watchdog expire into powered bypass. That
invalidates CAKE/raw bridge tests because traffic may skip the VM qdiscs.

For a valid raw bridge isolation test:

```bash
sudo systemctl stop silicom-bypass-watchdog@spectrum.service
cd /opt/bpctl-silicom
sudo ./bpctl_util spec-modem set_bypass_wd 0
sudo ./bpctl_util spec-modem set_bypass off
sudo systemctl stop wanctl@spectrum.service
sudo ./bpctl_util spec-modem set_bypass off
sudo tc qdisc del dev spec-router root 2>/dev/null || true
sudo tc qdisc del dev spec-modem root 2>/dev/null || true
```

Then wait for the path to stabilize before measuring. Verify all of the following:

```bash
cd /opt/bpctl-silicom
sudo ./bpctl_util spec-modem get_bypass      # non-Bypass
sudo ./bpctl_util spec-modem get_bypass_wd   # disabled for the test
ip -br link show spec-modem spec-router br-spectrum
tc qdisc show dev spec-router
tc qdisc show dev spec-modem
curl -4 --interface 10.10.110.223 https://ifconfig.me
```

Validated 2026-04-28 result after stabilization:

```text
iperf3 -4 -c 104.200.21.31 -p 5201 -B 10.10.110.223 -P 4 -t 20
SUM receiver: 38.9 Mbit/s
qdisc drops: 0
Silicom path: inline, non-bypass, WDT disabled only for the test
```

Restore powered fail-open after testing:

```bash
cd /opt/bpctl-silicom
sudo ./bpctl_util spec-modem set_bypass off
sudo systemctl restart wanctl@spectrum.service
sleep 3
sudo systemctl restart silicom-bypass-watchdog@spectrum.service
sudo ./bpctl_util spec-modem get_bypass_wd
```

As of this validation, the Silicom/riser/bridge path is capable of full Spectrum
upload. Remaining Spectrum upload loss under normal operation is a CAKE/controller
tuning issue, not a bypass-card or PCIe-riser finding.

### Managed Spectrum Mitigation Notes

The 2026-04-28 validation produced an operational mitigation, not a settled final
tuning answer. Keep the distinction explicit when changing Spectrum settings.

Evidence-supported pieces:

- The Spectrum Silicom ports need `gro`, `gso`, `tso`, and `hw-tc-offload` disabled
  before `wanctl@spectrum` starts. This is handled by `wanctl-nic-tuning.service`.
- Upload shaping belongs on `spec-modem`; download shaping belongs on `spec-router`.
- Upload CAKE with `no-ack-filter` avoids the ACK-filter-specific loss mode seen
  during the migration tests.
- Download CAKE with `ingress` on `spec-router` collapsed upload tests; the current
  Spectrum config disables that flag.
- Upload shaping has an experimental `upload_qdisc: "htb_fq_codel"` escape hatch.
  Static isolation showed HTB/fq_codel outperforming CAKE for upload on this
  hardware path. Managed testing exposed and fixed a systemd sandbox interaction:
  `ProcSubset=pid` hides `/proc/net/psched`, which `tc` uses for HTB timing and
  burst accounting. With that fixed, HTB preserved `256Kb` burst during rate
  changes, but managed upload still underperformed, so it remains disabled for
  normal Spectrum operation.

Provisional pieces that need retesting:

- `cake_params.rtt: "1s"` was a diagnostic artifact from static CAKE testing, not
  a valid operating value. Keep Spectrum on a sane WAN interval such as `100ms`;
  only compare `200ms` or similar bounded values under controlled A/B tests.
- Gateway-only `ping_hosts: ["10.10.110.1"]` was a diagnostic control for upload
  collapse during testing, not a valid operating mode. It masks WAN congestion and
  prevents autorate from seeing WAN-path RTT. Keep Spectrum on WAN-path reflectors
  unless deliberately running an isolation test.
- `irtt.enabled: false` remains a provisional mitigation until IRTT cadence,
  duration, and packet pattern are re-tested with raw/static/managed controls.

Observed managed-mode behavior:

- IRTT probe traffic contributed to the upload collapse, but disabling IRTT alone
  did not fully solve it.
- A single public ICMP reflector (`1.1.1.1`) still reproduced the collapse in a
  managed test.
- Gateway-only ICMP plus IRTT disabled produced the best managed upload run in the
  original session, about `25.3 Mbit/s` receiver throughput with no ping loss, but
  it is unsuitable for normal operation because it removes WAN-path RTT signal.
- A later browser bufferbloat test under the mitigation reported grade `B`,
  `735.2 Mbps` down, `25.4 Mbps` up, download active latency `+47 ms`, and upload
  active latency `+42 ms`. This is usable, but not fully tuned.
- Managed HTB/fq_codel upload with the `/proc/net/psched` fix preserved `256Kb`
  burst and recovered from rate reductions, but upload-only speedtest still only
  reached `12.32 Mbit/s` and drove autorate down to the `8Mbit` floor during the
  test. Keep Spectrum on CAKE unless a later controlled sweep proves otherwise.

Public `iperf3` caution:

- Late in the test session, Dallas and Novoserve public `iperf3` targets produced
  broken pipes, busy-server errors, and `0.00 Bytes` receiver output even in raw
  bridge mode. Treat those runs as test-target failures unless bracketed by a
  healthy raw bridge control.

Restore checklist after any Spectrum isolation test:

```bash
sudo systemctl restart wanctl-nic-tuning.service
sudo systemctl restart wanctl@spectrum.service
sleep 3
sudo systemctl restart silicom-bypass-watchdog@spectrum.service
systemctl is-active wanctl@spectrum.service silicom-bypass-watchdog@spectrum.service bpctl-silicom.service
tc qdisc show dev spec-modem
tc qdisc show dev spec-router
cd /opt/bpctl-silicom
sudo ./bpctl_util spec-modem get_bypass
sudo ./bpctl_util spec-modem get_bypass_wd
```

Expected restored state:

```text
wanctl@spectrum.service: active
silicom-bypass-watchdog@spectrum.service: active
bpctl-silicom.service: active
spec-modem: CAKE upload qdisc, non-bypass
spec-router: CAKE download qdisc, no ingress keyword
WDT: enabled with 6400 ms timeout value
```

## ATT Recovery Sequence

Use this only when ATT is stuck with `BYP`/`DISC` lit or Linux reports no carrier
after a bypass-control change. This sequence recovered ATT on 2026-04-28.

```bash
cd /opt/bpctl-silicom
sudo ./bpctl_util att-modem set_bypass off
sudo ./bpctl_util att-modem set_std_nic on
sudo ip link set att-modem down
sudo ip link set att-router down
sleep 2
sudo ip link set att-modem up
sudo ip link set att-router up
```

Verify after recovery:

```bash
cd /opt/bpctl-silicom
for c in get_bypass get_disc get_std_nic get_dis_bypass get_dis_disc get_bypass_pwoff get_bypass_pwup; do
  printf '%s: ' "$c"
  sudo ./bpctl_util att-modem "$c"
done
ip -br link show att-modem
ip -br link show att-router
ip -br link show br-att
```

## Fail-Open Goal And Result

The intended fail-open state is not live bypass while the host is running.

The intended behavior is:

```text
Host/card powered: non-bypass, non-disconnect, Linux bridge in path.
Host/card unpowered: relay bypass bridges adjacent ports directly.
```

Do not run live `set_bypass on` on an active WAN pair casually. It removes the
host from the path and drops the Linux bridge carrier. In this deployment,
powered live bypass was safe to test on ATT only because live internet was on
Spectrum.

Final result as of 2026-04-28: unpowered fail-open does not work in the
`odin`/`cake-shaper` setup with this card. Powered live bypass works, but the
ATT path dies when `odin` is powered off, even when the pair is already in live
bypass before power loss.

## Fail-Open Configuration Tested

This sequence was validated on the unused `sil-spare1`/`sil-spare2` pair first,
then applied to ATT on 2026-04-28 without forcing live bypass or dropping
carrier. It did not make unpowered fail-open work.

The first physical `odin` power-off test failed while `get_std_nic` still
reported Standard NIC mode: the card showed no lights, ATT connectivity was lost,
and service did not return until the VM was running again. After that failure,
`get_bypass_slave` confirmed `att-modem` and `att-router` are a real hardware
bypass pair, so the next test state disables Standard NIC mode while keeping live
bypass and disconnect off.

`set_dis_bypass off` is intentionally counterintuitive: it clears the bypass
disable bit, so `get_dis_bypass` should report `Bypass mode is enabled`.

```bash
cd /opt/bpctl-silicom
sudo ./bpctl_util att-modem set_dis_bypass off
sleep 2
sudo ./bpctl_util att-modem set_bypass_pwoff on
sleep 2
sudo ./bpctl_util att-modem set_bypass_pwup off
sudo ./bpctl_util att-modem set_disc_pwup off
sudo ./bpctl_util att-modem set_std_nic off
```

Verify the live state remains normal and only the power-off policy changed:

```bash
cd /opt/bpctl-silicom
for c in get_bypass get_disc get_std_nic get_dis_bypass get_dis_disc get_bypass_pwoff get_bypass_pwup get_disc_pwup; do
  printf '%s: ' "$c"
  sudo ./bpctl_util att-modem "$c"
done
ip -br link show att-modem
ip -br link show att-router
ip -br link show br-att
```

Expected powered result:

```text
get_bypass: non-Bypass
get_disc: non-Disconnect
get_std_nic: not in Standard NIC mode
get_dis_bypass: Bypass mode enabled
get_dis_disc: Disconnect mode disabled
get_bypass_pwoff: Bypass at power off
get_bypass_pwup: non-Bypass at power up
get_disc_pwup: non-Disconnect at power up
att-modem: UP, LOWER_UP
att-router: UP, LOWER_UP
br-att: UP, LOWER_UP
```

Physical power-off result:

```text
Failed. ATT connectivity was lost when odin powered off.
```

A VM reboot is not a valid power-off test because the PCIe card remains powered
by the host.

## Powered Live-Bypass Test

ATT was forced into live bypass on 2026-04-28 while Spectrum carried live
internet.

Command used:

```bash
cd /opt/bpctl-silicom
sudo ./bpctl_util att-modem set_bypass on
```

Observed state while bypassed:

```text
Relays clicked.
ATT LINK/ACT LEDs went out.
ATT BYP LEDs lit on both ports.
Linux host-side att-modem/att-router/br-att reported NO-CARRIER.
RouterOS ether2-WAN-ATT remained running.
RouterOS ATT DHCP remained bound during the first 20s, then briefly reported renewing.
Spectrum remained UP.
```

Restore command:

```bash
cd /opt/bpctl-silicom
sudo ./bpctl_util att-modem set_bypass off
sudo ./bpctl_util att-modem set_disc off
```

Observed state after restore:

```text
ATT LINK/ACT LEDs blinking again.
ATT BYP/DISC LEDs off.
att-modem, att-router, and br-att UP/LOWER_UP.
RouterOS ether2-WAN-ATT running and DHCP bound.
ATT and Spectrum health endpoints healthy/green.
```

Interpretation: the card can switch the ATT pair into hardware bypass while
powered, RouterOS keeps carrier on the ATT WAN interface, and the pair can
restore cleanly. The remaining failure is specific to full `odin` poweroff: the
powered bypass path works, but the card did not preserve that path once host
power was removed in two physical tests.

## Already-Bypassed Power-Off Test

Final diagnostic on 2026-04-28:

1. Force ATT into powered live bypass with `set_bypass on`.
2. Verify RouterOS `ether2-WAN-ATT` remains running and DHCP remains bound.
3. Power off `odin` while ATT is already bypassed.

Result:

```text
Failed. ATT connectivity still died when odin powered off.
```

Interpretation: this is not a command-order issue and not a failure to enter
live bypass. The Silicom card can bypass while powered, but it does not preserve
the copper bypass path when the host/card loses power in this platform.

Operational conclusion: do not rely on this internal Silicom card for unpowered
fail-open on `odin`. Use one of these mitigations instead:

- External passive/managed bypass switch for the WAN pair.
- UPS/runtime design where `odin` outlasts the modem/router path.
- Keep live internet on a path that does not depend on the powered VM host.

## Root Cause Analysis

Diagnosis on 2026-04-28 after the physical power-off tests failed.

### Evidence Collected

- `bpctl_util` exposes no `save`, `commit`, `nvram`, or `flash` verb. Settings
  appear to apply directly.
- `bypass.h` defines `EEPROM_WR_DELAY 20 /* msec */`, confirming the driver does
  write `set_bypass_pwoff`-class settings to onboard EEPROM. Persistence of the
  policy bit is not the failure mode.
- `lspci -vvv` on the card reports
  `AuxCurrent=0mA PME(D0-,D1-,D2-,D3hot-,D3cold-)`. The card explicitly requests
  zero PCIe AUX standby current and advertises no PME wake capability. The card
  does not consume slot standby power and was not designed to.
- `get_bypass_caps` returns `0x7803ffff` — the card advertises
  `BP_PWOFF_ON_CAP`, `BP_PWOFF_CTL_CAP`, `BP_PWUP_*_CAP` capabilities. Software
  is told the card can do unpowered bypass.
- Firmware version per `get_bypass_info` is `0xaa`. This is an early-mid Silicom
  BPI35 firmware revision.
- Already-bypassed power-off test (relays known to be in bypass position
  _before_ host power was cut) still lost ATT connectivity.

### Mechanism

The already-bypassed power-off failure is the decisive data point. If the
bypass relays were truly bistable / latching, removing card power would leave
the contacts in their last commanded position (bypass) and the copper path
would survive. Connectivity died anyway. Combined with `AuxCurrent=0mA`, the
relay set on this card behaves as **monostable**: it requires continuous coil
energization to hold the bypass position, and a spring returns it to the
non-bypass (PHY-in-path) position when the coil de-energizes.

The advertised `BP_PWOFF_ON_CAP` does not imply mechanical fail-to-wire. It
indicates the firmware will attempt to fire the relay coil during a graceful
power-down using onboard reservoir capacitance. On this card, in this chassis,
that attempt either does not occur or does not retain the bypass position long
enough for any external observer to see. Possible contributors include
capacitor aging on used hardware and the older 0xaa firmware. The behavior is
also consistent with a card whose relay set is monostable by design and which
was never intended to survive full host power loss.

### Design Intent of This Card Family

Silicom internal-bypass NICs in the `PE2G4BPI*-SD` line target **inline
security appliances** (IDS/IPS, firewalls, NDR, WAF). The expected failure
mode is software, not building power. Operationally:

1. The appliance arms the per-pair watchdog: `bpctl_util eth0 set_bypass_wd 5000`.
2. A userspace heartbeat process resets the watchdog every few seconds while
   the inspection stack is healthy.
3. If userspace hangs, panics, or crashes, the watchdog expires.
4. The card — **still powered** — drives its relay coils into the bypass
   position. Traffic passes through uninspected until operators restore the
   inspection software, at which point bypass is released.

In that workflow the card never loses power. Monostable relays are acceptable
because coil power is always available. The "fail-to-wire" marketing language
refers to fail-to-wire on **software failure**, with the card itself remaining
powered, not fail-to-wire on chassis power loss.

The market product for true power-loss fail-open is an **external passive
bypass switch**: a separate sheet-metal box with spring-NC mechanical relays,
no firmware, no host dependency, copper-bridges-on-power-loss by physics.
Silicom sells those as a distinct SKU line; other vendors include Garland,
Niagara Networks, and Profitap. This card is not in that category and cannot
be reconfigured into it.

### Implication For This Deployment

`odin` is already on UPS. The internal Silicom card was procured as belt-and-
suspenders coverage on top of UPS for a chassis-power-loss scenario. That
specific scenario is not in this card's design envelope and cannot be made to
work through configuration. The card remains useful for:

- Software-failure fail-open via the watchdog feature, if a future workload
  on `cake-shaper` warrants it.
- Powered live bypass for maintenance windows where the VM is taken down but
  WAN continuity is required (validated 2026-04-28, see
  _Powered Live-Bypass Test_).

For chassis-power-loss survival the architecture is:

- UPS on `odin` (already in place).
- Modem-side battery backup (already in place).
- These two together give effective fail-open without relying on the internal
  card's relay behavior at host power loss.

If a future requirement demands true power-independent passthrough on the ATT
pair, an external passive bypass switch is the correct hardware class. Do not
re-test this internal card against that requirement.
