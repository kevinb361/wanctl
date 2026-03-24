# Architecture Research: CAKE Offload to Linux VM

**Domain:** Linux CAKE offload integration with existing wanctl dual-WAN controller
**Researched:** 2026-03-24
**Confidence:** HIGH (codebase fully explored, hardware known, tc CAKE well-documented)

## Current Architecture (Baseline)

```
                    ┌──────────────────────────────────────────┐
                    │            MikroTik RB5009                │
                    │  CAKE queues + routing + firewall + NAT   │
                    │  queue tree: WAN-Download-Spectrum, etc.  │
                    └───────┬──────────────────┬───────────────┘
                            │ REST/SSH API     │ REST/SSH API
                    ┌───────┴──────┐   ┌──────┴──────────┐
                    │ cake-spectrum │   │    cake-att      │
                    │   (LXC)      │   │     (LXC)        │
                    │ wanctl@spec  │   │  wanctl@att      │
                    │ wanctl-steer │   │                   │
                    └──────────────┘   └──────────────────┘
```

**Router interaction points (6 total, all via FailoverRouterClient.run_cmd):**

| Component | Module | What it does | RouterOS commands used |
|-----------|--------|-------------|----------------------|
| `RouterOS.set_limits()` | autorate_continuous.py:1205 | Set DL+UL bandwidth | `/queue tree set ... max-limit=<bps>` |
| `CakeStatsReader.read_stats()` | steering/cake_stats.py:193 | Read CAKE drops/queue depth | `/queue/tree print stats detail` |
| `RouterOSController.get_rule_status()` | steering/daemon.py:732 | Check mangle rule state | `/ip firewall mangle print` |
| `RouterOSController.enable_steering()` | steering/daemon.py:767 | Enable steering rule | `/ip firewall mangle enable` |
| `RouterOSController.disable_steering()` | steering/daemon.py:796 | Disable steering rule | `/ip firewall mangle disable` |
| `check_cake.py` validators | check_cake.py | Audit CAKE params, queue tree | Multiple `/queue tree/type` commands |

**Key observation:** The `RouterBackend` ABC in `backends/base.py` exists but the autorate/steering code does NOT use it. The autorate loop uses the `RouterOS` class (wrapping `FailoverRouterClient` directly), and the steering daemon has its own `RouterOSController` class. Both construct raw RouterOS CLI strings and call `client.run_cmd()`. The `RouterBackend` interface was designed for future backend abstraction but the actual hot-path code bypasses it.

## Target Architecture (CAKE Offload)

```
  Spectrum Modem          ATT Modem
       │                      │
       │ nic0 (i210)          │ nic2 (i350)
  ┌────┴──────────────────────┴────────────────┐
  │          Debian 12 VM on odin              │
  │                                            │
  │  br-spectrum (nic0+nic1)  br-att (nic2+3)  │
  │     CAKE egress on nic1      CAKE on nic3  │
  │     CAKE ingress via IFB     IFB for DL    │
  │                                            │
  │  wanctl@spectrum   wanctl@att              │
  │  wanctl-steering                           │
  │                                            │
  │  LinuxCakeBackend: tc qdisc change         │
  │  RTT: icmplib (unchanged)                  │
  │  Steering: still talks to router via REST  │
  └────┬──────────────────────┬────────────────┘
       │ nic1 (i210)          │ nic3 (i350)
       │                      │
  ┌────┴──────────────────────┴────────────────┐
  │            MikroTik RB5009                 │
  │  Routing + firewall + NAT + DSCP mangle    │
  │  NO queue trees, NO CAKE                   │
  │  Pure router/firewall appliance            │
  └────────────────────────────────────────────┘
```

## Component Changes: New vs Modified vs Unchanged

### NEW Components

#### 1. LinuxCakeBackend (new file: `backends/linux_cake.py`)

**Purpose:** Implement the same bandwidth control and stats collection that `RouterOS.set_limits()` and `CakeStatsReader.read_stats()` currently do, but using local `tc` commands instead of RouterOS REST/SSH.

**Interface contract (maps to existing operations):**

```python
class LinuxCakeBackend:
    """Local CAKE qdisc control via tc commands.

    Replaces RouterOS queue tree control for bandwidth shaping.
    Does NOT handle steering rules (those stay on the router).
    """

    def __init__(
        self,
        dl_interface: str,      # e.g., "ifb-spectrum" (IFB device for download CAKE)
        ul_interface: str,      # e.g., "nic1" (egress interface for upload CAKE)
        logger: logging.Logger,
    ):
        ...

    def set_bandwidth(self, direction: str, rate_bps: int) -> bool:
        """tc qdisc change dev <iface> root cake bandwidth <rate>"""
        ...

    def get_stats(self, direction: str) -> dict | None:
        """tc -s -j qdisc show dev <iface> -- parse JSON for drops, queue depth"""
        ...

    def test_connection(self) -> bool:
        """Verify interfaces exist and CAKE qdiscs are attached"""
        ...
```

**Critical design decisions:**

1. **Use `subprocess.run()` for tc commands, not pyroute2.** pyroute2 adds a dependency and its CAKE netlink attribute parsing is not well-documented. `tc -s -j qdisc show` gives JSON output since iproute2 5.x. The subprocess overhead (fork+exec) is ~2-5ms, well within the 50ms cycle budget.

2. **`tc qdisc change` is non-destructive.** Per official CAKE documentation: "Most parameters can be updated without losing packets using tc's change command." Bandwidth changes specifically "don't cause any packet flushing or other trouble." This matches the existing flash-wear-protection pattern perfectly.

3. **Two interfaces per WAN, not one.** CAKE shapes egress traffic. For download shaping, an IFB (Intermediate Functional Block) device mirrors ingress to egress, where CAKE shapes it. So each WAN needs:
   - Upload: CAKE on the physical egress interface (nic1 for Spectrum, nic3 for ATT)
   - Download: CAKE on an IFB device (ifb-spectrum, ifb-att) with traffic mirrored from the modem-side NIC

4. **Requires CAP_NET_ADMIN capability.** The `tc` command needs `CAP_NET_ADMIN` (not root). The systemd service already grants `CAP_NET_RAW` for ICMP; add `CAP_NET_ADMIN` for tc.

#### 2. Bridge Setup Scripts (new: `scripts/setup-bridge-*.sh`)

**Purpose:** Create bridges, IFB devices, attach CAKE qdiscs at boot. Separate from wanctl Python code.

**Per-WAN bridge setup (example for Spectrum):**

```bash
# Create bridge (transparent L2, no IP)
ip link add br-spectrum type bridge
ip link set nic0 master br-spectrum  # modem side
ip link set nic1 master br-spectrum  # router side
ip link set br-spectrum up
ip link set nic0 up
ip link set nic1 up

# Upload CAKE: egress on router-side NIC
tc qdisc replace dev nic1 root cake bandwidth 38mbit \
    diffserv4 nat triple-isolate wash ack-filter \
    ethernet overhead 34

# Download CAKE: IFB mirrors ingress from modem-side NIC
ip link add ifb-spectrum type ifb
ip link set ifb-spectrum up
tc qdisc add dev nic0 handle ffff: ingress
tc filter add dev nic0 parent ffff: protocol all \
    u32 match u32 0 0 action mirred egress redirect dev ifb-spectrum
tc qdisc replace dev ifb-spectrum root cake bandwidth 900mbit \
    diffserv4 nat triple-isolate noack \
    ethernet overhead 34
```

This runs at VM boot (systemd oneshot before wanctl starts). wanctl only adjusts bandwidth via `tc qdisc change`.

#### 3. Config Schema Extension

New transport value in YAML config:

```yaml
router:
  transport: "linux-cake"  # NEW: local tc commands
  # Fields below only for steering (mangle rules still on router)
  host: "10.10.99.1"
  password: "${ROUTER_PASSWORD}"

# NEW: Linux CAKE interface mapping
linux_cake:
  download_interface: "ifb-spectrum"
  upload_interface: "nic1"
  overhead: 34           # Ethernet framing overhead
  diffserv: "diffserv4"  # Match existing 4-tier QoS
```

### MODIFIED Components

#### 1. `RouterOS` class in autorate_continuous.py (wrapped via factory)

**Current:** `RouterOS.__init__()` creates `FailoverRouterClient`, `set_limits()` builds RouterOS queue tree commands.

**Change:** Factory pattern -- when `transport: "linux-cake"`, instantiate `LinuxCakeShaper` (a thin wrapper around `LinuxCakeBackend` matching the `set_limits(wan, down_bps, up_bps)` signature) instead. The method signature stays identical.

```python
# In autorate_continuous.py, factory replaces direct RouterOS() construction:
def get_shaper_backend(config: Config, logger: logging.Logger):
    """Create appropriate bandwidth control backend."""
    if config.router_transport == "linux-cake":
        from wanctl.backends.linux_cake import LinuxCakeShaper
        return LinuxCakeShaper.from_config(config, logger)
    else:
        return RouterOS(config, logger)  # existing MikroTik path
```

**Impact:** WANController receives this from its constructor. WANController itself does NOT change. The `router` attribute just becomes polymorphic.

#### 2. `CakeStatsReader` in steering/cake_stats.py

**Current:** Reads CAKE stats via `client.run_cmd("/queue/tree print stats detail")` over REST/SSH.

**Change:** When transport is `linux-cake`, read stats from local `tc -s -j qdisc show dev <iface>` instead. The delta-tracking logic (`_calculate_stats_delta`) stays identical. Only the data source changes.

**Recommended approach:** CakeStatsReader constructor detects transport and delegates to `LinuxCakeBackend.get_stats()` for the raw data read, keeping all delta calculation logic in CakeStatsReader unchanged.

#### 3. Steering daemon's `RouterOSController`

**Partial change.** Steering needs to toggle mangle rules on the MikroTik router even when CAKE runs locally. The steering daemon must keep its `FailoverRouterClient` for mangle rule operations (enable/disable/check), while CAKE stats come from the local LinuxCakeBackend.

This means the steering daemon needs TWO backends:
- `LinuxCakeBackend` for `read_stats()` (local tc)
- `FailoverRouterClient` for `enable_steering()`/`disable_steering()` (router REST/SSH)

#### 4. Config class `_load_router_transport_config()`

**Current:** Loads REST/SSH settings (password, port, SSL).

**Change:** When `transport: "linux-cake"`, load interface names from `linux_cake` config section. Router settings are still loaded if present (steering still needs them for mangle rules).

#### 5. `check_cake.py` CLI tool

**Current:** Audits CAKE parameters on the RouterOS queue tree.

**Change:** When transport is `linux-cake`, audit the local `tc` qdisc configuration instead. Check that CAKE is attached to the correct interfaces with expected parameters. The `--fix` mode would run `tc qdisc change` locally.

#### 6. Systemd service template

**Current:** `AmbientCapabilities=CAP_NET_RAW` for ICMP.

**Change:** Add `CAP_NET_ADMIN` for tc commands: `AmbientCapabilities=CAP_NET_RAW CAP_NET_ADMIN`.

### UNCHANGED Components (majority of codebase)

| Component | Why unchanged |
|-----------|---------------|
| WANController | Calls `router.set_limits()` -- polymorphic, doesn't care about transport |
| QueueController | Pure state machine logic, no router awareness |
| RTT measurement (icmplib) | Pings reflectors directly, no router dependency |
| Signal processing chain | Operates on RTT values, transport-agnostic |
| IRTT measurement | Independent UDP probes |
| Fusion, tuning, calibration | All work on metrics, not router commands |
| AlertEngine, Discord webhooks | Consume events, no router interaction |
| State persistence (JSON, SQLite) | File-based, transport-agnostic |
| Dashboard (TUI), history CLI | Read from health endpoint / SQLite |
| BaseConfig, config validation | Additive change only (new transport value) |
| Flash wear protection | Still valuable -- dedup prevents unnecessary subprocess calls |
| Rate limiter | Still valuable -- protects against rapid tc calls in oscillation |

## Data Flow Changes

### Current Data Flow (RouterOS CAKE)

```
measure RTT (icmplib) -> signal processing -> congestion state
    -> QueueController calculates new rate
    -> RouterOS.set_limits() -> FailoverRouterClient.run_cmd()
    -> RouterOS REST API -> queue tree max-limit update
```

### New Data Flow (Linux CAKE)

```
measure RTT (icmplib) -> signal processing -> congestion state
    -> QueueController calculates new rate
    -> LinuxCakeShaper.set_limits() -> subprocess.run(["tc", ...])
    -> kernel tc netlink -> CAKE qdisc bandwidth update (non-destructive)
```

**Latency improvement:** ~2-5ms for local subprocess vs ~15-25ms for REST API round-trip. Frees cycle budget headroom within the 50ms interval.

### CAKE Stats Data Flow Change

```
CURRENT: CakeStatsReader -> client.run_cmd("/queue/tree print stats") -> parse REST JSON or SSH text
NEW:     CakeStatsReader -> subprocess.run(["tc", "-s", "-j", "qdisc", "show"]) -> parse tc JSON
```

### Steering Data Flow (Hybrid)

```
CAKE stats:    LinuxCakeBackend.get_stats() -> local tc (fast, ~2ms)
RTT:           icmplib pings (unchanged)
Mangle rules:  FailoverRouterClient -> RouterOS REST API (still remote, ~15ms)
State files:   local filesystem (unchanged)
```

## Interface Topology (Physical + Virtual)

### Per-WAN Interface Set

```
For Spectrum:
  nic0 (i210, PCIe passthrough) --- modem-side
      |-- ingress: tc filter -> mirred to ifb-spectrum
      +-- member of br-spectrum

  nic1 (i210, PCIe passthrough) --- router-side
      |-- egress: CAKE qdisc (upload shaping)
      +-- member of br-spectrum

  ifb-spectrum (virtual IFB device)
      +-- egress: CAKE qdisc (download shaping, mirrored from nic0 ingress)

  br-spectrum (Linux bridge, no IP address)
      +-- transparent L2 forwarding between nic0 and nic1

For ATT: identical structure with nic2/nic3/ifb-att/br-att
```

### Why IFB (Not Direct Ingress)

Linux tc cannot shape ingress traffic directly. The IFB (Intermediate Functional Block) pattern is the standard approach:
1. Attach ingress qdisc to the modem-side NIC
2. Mirror all ingress packets to an IFB device via `tc filter ... mirred egress redirect`
3. Attach CAKE to the IFB device's egress
4. Packets flow: modem NIC ingress -> IFB egress (shaped by CAKE) -> bridge -> router NIC

This is well-established Linux networking practice since kernel 2.6 and is used by OpenWrt's SQM scripts, pfSense, and every other Linux-based CAKE deployment.

### DSCP Preservation Through Bridge

DSCP marks set by the RB5009 mangle rules on outbound traffic are preserved through the transparent L2 bridge. CAKE's diffserv4 mode reads these marks for priority classification:
- EF (DSCP 46) -> Voice tin
- AF31 (DSCP 26) -> Video tin
- CS0 (default) -> Best Effort tin
- CS1 (DSCP 8) -> Bulk tin

For download (ISP -> LAN), the ISP does not set DSCP marks, so all download traffic enters the Best Effort tin. This matches current behavior on the RB5009.

## Architectural Patterns

### Pattern 1: Transport Polymorphism via Factory

**What:** Replace the direct `RouterOS()` construction with a factory that returns the appropriate backend based on config.

**When to use:** Any time the control loop needs to apply rates or read stats.

**Trade-offs:** Simple and low-risk. Does not require refactoring WANController or QueueController. The polymorphic object just needs `set_limits(wan, down_bps, up_bps)` and the stats methods.

```python
class LinuxCakeShaper:
    """Drop-in replacement for RouterOS class when transport=linux-cake."""

    def __init__(self, config, logger):
        from wanctl.backends.linux_cake import LinuxCakeBackend
        self.backend = LinuxCakeBackend.from_config(config, logger)

    def set_limits(self, wan: str, down_bps: int, up_bps: int) -> bool:
        """Same signature as RouterOS.set_limits()."""
        dl_ok = self.backend.set_bandwidth("download", down_bps)
        ul_ok = self.backend.set_bandwidth("upload", up_bps)
        return dl_ok and ul_ok
```

### Pattern 2: Subprocess with JSON Parsing for tc

**What:** Use `tc -s -j qdisc show dev <iface>` for machine-readable CAKE stats.

**When to use:** Anywhere wanctl needs to read CAKE qdisc state (stats, current bandwidth, parameters).

**Trade-offs:** The `-j` JSON flag is available in iproute2 5.x+ (Debian 12 ships iproute2 6.1). Faster to parse than regex on text output. Falls back cleanly if JSON parsing fails.

```python
def get_stats(self, interface: str) -> dict | None:
    result = subprocess.run(
        ["tc", "-s", "-j", "qdisc", "show", "dev", interface],
        capture_output=True, text=True, timeout=5,
    )
    if result.returncode != 0:
        return None
    data = json.loads(result.stdout)
    # tc JSON returns a list of qdiscs; find the cake one
    for qdisc in data:
        if qdisc.get("kind") == "cake":
            return {
                "packets": qdisc.get("packets", 0),
                "bytes": qdisc.get("bytes", 0),
                "dropped": qdisc.get("drops", 0),
                "queued_packets": qdisc.get("backlog", {}).get("packets", 0),
                "queued_bytes": qdisc.get("backlog", {}).get("bytes", 0),
            }
    return None
```

### Pattern 3: Dual-Backend for Steering Daemon

**What:** Steering daemon holds both a local LinuxCakeBackend (for stats) and a remote FailoverRouterClient (for mangle rules).

**When to use:** Only in the steering daemon, where CAKE stats and mangle rule control are on different hosts.

**Trade-offs:** Slightly more complex init, but clean separation. The autorate daemon only needs the LinuxCakeBackend (no router communication at all in the hot path).

## Anti-Patterns

### Anti-Pattern 1: Refactoring WANController to Know About Backends

**What people do:** Pass the backend type into WANController, add if/else branches.

**Why it's wrong:** WANController is the architectural spine (READ-ONLY per CLAUDE.md). Its control logic, state machine, and threshold evaluation must not change. The transport should be invisible to it.

**Do this instead:** Make `RouterOS` and `LinuxCakeShaper` share the same `set_limits()` interface. WANController calls `self.router.set_limits()` regardless.

### Anti-Pattern 2: Running tc Commands as Root

**What people do:** Run wanctl as root to get tc access.

**Why it's wrong:** Violates the existing security model (non-root wanctl user, minimal capabilities).

**Do this instead:** Add `CAP_NET_ADMIN` ambient capability in systemd. The wanctl user can then run tc commands without root.

### Anti-Pattern 3: Recreating CAKE Qdiscs on Every Rate Change

**What people do:** `tc qdisc del` then `tc qdisc add` with new bandwidth.

**Why it's wrong:** Causes packet loss during the delete-recreate gap. CAKE explicitly supports `tc qdisc change` for non-destructive bandwidth updates.

**Do this instead:** Always use `tc qdisc change dev <iface> root cake bandwidth <rate>`. Only the initial setup (bridge scripts) uses `tc qdisc replace`.

### Anti-Pattern 4: Using pyroute2 for CAKE Control

**What people do:** Import pyroute2 for "proper" netlink access instead of subprocess.

**Why it's wrong:** Adds a heavy dependency (~50+ modules). pyroute2's CAKE attribute parsing is poorly documented and may lag kernel changes. Subprocess `tc` is battle-tested, and the 2-5ms overhead is negligible vs the 15-25ms saved by not talking to the router.

**Do this instead:** Use `subprocess.run(["tc", ...])` with JSON parsing. Zero new dependencies.

## Integration Points

### External Services

| Service | Current | After Offload | Notes |
|---------|---------|---------------|-------|
| MikroTik REST API | Bandwidth + stats + mangle rules | Mangle rules ONLY | Autorate stops talking to router entirely |
| MikroTik SSH | Failover for REST | Failover for mangle rules only | Reduced surface area |
| Local tc command | Not used | Bandwidth + stats | New integration, subprocess |
| Kernel CAKE qdisc | N/A (on router) | Local kernel module | Must be loaded at boot |

### Internal Boundaries

| Boundary | Communication | Change |
|----------|---------------|--------|
| WANController -> Shaper | `set_limits(wan, dl, ul)` | Interface unchanged, implementation swapped |
| SteeringDaemon -> CakeStats | `read_stats(queue_name)` | Source changes (local tc vs remote REST) |
| SteeringDaemon -> MangleRules | `enable_steering()`, `disable_steering()` | Unchanged (still talks to router) |
| check_cake CLI -> CAKE | Audits CAKE params | Splits: local tc audit OR remote router audit |
| Health endpoint | Reports backend type, cycle budget | Add transport type to health response |

### Filesystem Layout (VM)

```
/opt/wanctl/                  # Application code (same structure)
/etc/wanctl/                  # Config files
  spectrum.yaml               # transport: linux-cake
  att.yaml                    # transport: linux-cake
  steering.yaml               # Still has router: section for mangle rules
  secrets                     # ROUTER_PASSWORD (for steering)
/var/lib/wanctl/              # State files (same)
/var/log/wanctl/              # Logs (same)
/etc/systemd/system/
  wanctl@.service             # +CAP_NET_ADMIN
  wanctl-bridge-setup.service # NEW: oneshot to create bridges/IFBs/CAKE at boot
```

## Suggested Build Order

Based on dependency analysis and risk:

### Phase 1: LinuxCakeBackend Core (lowest risk, highest value)

**Build:** `backends/linux_cake.py` with `set_bandwidth()` and `get_stats()`.
**Test:** Unit tests with mocked subprocess. Integration test on dev machine with dummy interface.
**Why first:** Self-contained module, no changes to existing code. Can be developed and fully tested in isolation.

**Depends on:** Nothing.
**Blocks:** Everything else.

### Phase 2: Config + Factory Wiring

**Build:** Config schema extension (`linux_cake:` section), factory function in autorate_continuous.py.
**Test:** Config parsing tests, factory returns correct backend type.
**Why second:** Minimal surgical changes to existing code. Factory pattern means WANController stays untouched.

**Depends on:** Phase 1 (LinuxCakeBackend exists).
**Blocks:** Phases 3-5.

### Phase 3: CakeStatsReader Adaptation

**Build:** Modify CakeStatsReader to use LinuxCakeBackend when transport is linux-cake.
**Test:** Unit tests with mocked tc output. Verify delta tracking still works.
**Why third:** Steering daemon needs stats from local tc.

**Depends on:** Phase 1 (LinuxCakeBackend.get_stats).
**Blocks:** Phase 5 (steering integration).

### Phase 4: check_cake CLI Adaptation

**Build:** Add linux-cake mode to check_cake.py for local qdisc auditing.
**Test:** Verify it can audit CAKE params via tc.
**Why fourth:** Operator tooling. Needed before production cutover but not for functional testing.

**Depends on:** Phase 1.
**Blocks:** Nothing critical (nice-to-have before cutover).

### Phase 5: Steering Dual-Backend

**Build:** Steering daemon holds LinuxCakeBackend (stats) + FailoverRouterClient (mangle rules).
**Test:** Integration tests verifying both paths work.
**Why fifth:** Most complex change -- two backends in one daemon.

**Depends on:** Phases 1, 2, 3.
**Blocks:** Production cutover.

### Phase 6: VM Setup + Bridge Scripts + Systemd

**Build:** Bridge setup scripts, systemd oneshot service, updated service template, VM creation.
**Test:** VM creation on odin, interface verification, basic tc tests.
**Why last code phase:** Infrastructure, not application logic.

**Depends on:** All prior phases.
**Blocks:** Production cutover.

### Phase 7: Cutover

**Execute:** Cabling change, VM deploy, wanctl start, verify, disable RB5009 queue trees.
**Rollback:** Re-cable modems direct to RB5009, re-enable queue trees.

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Bridge/VM failure = total WAN outage | LOW | CRITICAL | Manual bypass cables, RB5009 fallback config |
| tc JSON format differs from expected | LOW | MEDIUM | Validate JSON schema on Debian 12 before deployment |
| IFB mirroring adds latency | VERY LOW | LOW | Measured at <0.1ms in Linux kernel |
| 1GbE NIC bottleneck for Spectrum | KNOWN | LOW | 900Mbps ceiling already set; X552 10G upgrade path exists |
| VM resource contention with other VMs | LOW | MEDIUM | Dedicate 2 CPU cores, 2GB RAM; CAKE is CPU-light on x86 |
| DSCP marks lost through bridge | VERY LOW | HIGH | L2 bridge preserves all packet headers by definition |
| Steering split-brain (local stats + remote rules) | LOW | MEDIUM | Atomic state file reads, same as current cross-container |

## Sources

- [tc-cake(8) man page](https://man7.org/linux/man-pages/man8/tc-cake.8.html) -- CAKE parameters, change semantics, statistics
- [CAKE Technical Wiki](https://www.bufferbloat.net/projects/codel/wiki/CakeTechnical/) -- Statistics fields, design rationale
- [CAKE dynamic bandwidth change discussion](https://cerowrt-devel.bufferbloat.narkive.com/WGpQmsKp/cake-changing-bandwidth-on-the-rate-limiter-dynamically) -- Confirms non-destructive change
- [Linux IFB Wiki](https://wiki.linuxfoundation.org/networking/ifb) -- IFB device pattern for ingress shaping
- [Proxmox PCI Passthrough](https://pve.proxmox.com/wiki/PCI(e)_Passthrough) -- NIC passthrough requirements
- [Network bridge - ArchWiki](https://wiki.archlinux.org/title/Network_bridge) -- Transparent bridge configuration
- Existing codebase: `backends/base.py`, `autorate_continuous.py`, `steering/cake_stats.py`, `steering/daemon.py`, `check_cake.py` -- analyzed directly

---
*Architecture research for: CAKE offload to Linux VM (wanctl v1.21)*
*Researched: 2026-03-24*
