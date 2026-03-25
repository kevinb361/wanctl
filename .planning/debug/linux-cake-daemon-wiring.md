---
status: investigating
trigger: "LinuxCakeBackend factory exists but is not wired into the daemon. CAKE never initializes on cake-shaper VM."
created: 2026-03-25T00:00:00Z
updated: 2026-03-25T00:00:00Z
---

## Current Focus

hypothesis: CONFIRMED - three integration gaps: (1) ContinuousAutoRate.**init** line 3460 hardcodes RouterOS() instead of using get_backend(), (2) WANController.apply_rate_changes_if_needed() calls router.set_limits(wan, dl, ul) which is RouterOS-specific -- LinuxCakeBackend uses per-queue set_bandwidth(queue, rate_bps), (3) LinuxCakeBackend needs TWO instances (dl on ens28, ul on ens27) but from_config() only creates one. Also config bug: att-vm.yaml has upload_interface=ens28 but should be ens27 per bridge traffic model.
test: Map all integration points, design minimal adapter
expecting: Fix all gaps with minimal changes to existing code
next_action: Implement fix -- adapter in ContinuousAutoRate.**init** that routes to correct backend based on config.router_transport

## Symptoms

expected: When wanctl@att starts on cake-shaper VM with transport: linux-cake config, the daemon should call initialize_cake() to create CAKE qdiscs on bridge member NICs, then use tc qdisc change for rate adjustments each cycle.
actual: Daemon starts, pings reflectors successfully (28ms ATT RTT), but CAKE never initializes. Every cycle fails with "Router communication failed (unknown, 1 consecutive)" because the code still uses RouterOS class (which tries MikroTik SSH/REST commands) instead of LinuxCakeBackend.
errors: "Router communication failed (unknown, 1 consecutive)" every 50ms cycle. "Sustained failure: 3 consecutive failed cycles" triggers watchdog. No CAKE qdisc on ens28 (tc qdisc show shows fq_codel default).
reproduction: sudo systemctl start wanctl@att on cake-shaper (10.10.110.223) with /etc/wanctl/att.yaml containing transport: linux-cake
started: First ever attempt to run linux-cake transport in production. The factory get_backend() was built in Phase 107 but never integrated into the daemon.

## Eliminated

## Evidence

- timestamp: 2026-03-25T00:01:00Z
  checked: ContinuousAutoRate.**init** (line 3460)
  found: Hardcodes `router = RouterOS(config, logger)` regardless of config.router_transport value. Never calls get_backend() factory.
  implication: Root cause #1 -- linux-cake transport config is ignored at daemon startup.

- timestamp: 2026-03-25T00:01:00Z
  checked: WANController.apply_rate_changes_if_needed (line 2308)
  found: Calls `self.router.set_limits(wan=self.wan_name, down_bps=dl_rate, up_bps=ul_rate)` -- this is a RouterOS-specific method that sets BOTH download+upload in one batched MikroTik command. LinuxCakeBackend has `set_bandwidth(queue, rate_bps)` per ABC contract.
  implication: Root cause #2 -- even if backend were instantiated correctly, the call site uses RouterOS-specific API, not the ABC interface.

- timestamp: 2026-03-25T00:01:00Z
  checked: LinuxCakeBackend.**init** and from_config()
  found: Each instance controls ONE interface. Download needs ens28 (router-side), upload needs ens27 (modem-side). from_config() takes direction param but get_backend() factory doesn't pass it.
  implication: Root cause #3 -- need two LinuxCakeBackend instances (dl + ul) and an adapter that presents the set_limits(wan, dl, ul) interface WANController expects.

- timestamp: 2026-03-25T00:01:00Z
  checked: configs/att-vm.yaml line 30
  found: upload_interface set to "ens28" but per bridge traffic model, upload CAKE should be on ens27 (modem-side egress with ack-filter).
  implication: Config bug -- will cause upload shaping to target wrong NIC. Must fix to ens27.

- timestamp: 2026-03-25T00:01:00Z
  checked: LinuxCakeBackend.initialize_cake() method
  found: Exists and takes params dict from build_cake_params(). Called nowhere in daemon code. No CAKE initialization happens at startup.
  implication: Root cause #4 -- even with correct backend wiring, CAKE qdiscs are never created on the interfaces.

## Resolution

root_cause:
fix:
verification:
files_changed: []
