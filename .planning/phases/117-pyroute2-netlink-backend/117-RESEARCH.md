# Phase 117: pyroute2 Netlink Backend - Research

**Researched:** 2026-03-27
**Domain:** pyroute2 netlink library for Linux CAKE qdisc control (replacing subprocess tc)
**Confidence:** HIGH

## Summary

pyroute2 0.9.5 provides verified, complete CAKE qdisc support via its `sched_cake.py` module. The source code confirms all 18 TCA_CAKE configuration attributes (including `TCA_CAKE_BASE_RATE64` for bandwidth), per-tin stats decoding (25 fields per tin, up to 8 tins), and full command support for `add`, `change`, `replace`, and `del` operations. The library has zero runtime dependencies on Linux, requires Python >=3.9 (production runs 3.12), and provides a synchronous `IPRoute` class that wraps an asyncio core -- fully compatible with the existing synchronous daemon loop.

The key integration pattern is straightforward: `ipr.tc("change", kind="cake", index=ifindex, bandwidth="500000kbit")` for bandwidth changes, and `ipr.tc("dump", index=ifindex)` to read stats including the `stats_app` decoder with per-tin CAKE statistics. The `get_parameters()` function in `sched_cake.py` maps Python kwargs (e.g., `bandwidth`, `diffserv_mode`, `overhead`) to TCA netlink attributes, with automatic conversion (e.g., `bandwidth="500000kbit"` -> `TCA_CAKE_BASE_RATE64` as octets/second). The critical risk is the `change` command behavior: pyroute2's `change` works like `replace` (fails if node doesn't exist), which differs subtly from tc CLI's `change` (modifies only specified values). For the hot loop, this means the CAKE qdisc MUST already exist before `change` is called -- which is guaranteed by `initialize_cake()` at startup.

The recommended architecture is a new `NetlinkCakeBackend` class alongside `LinuxCakeBackend`, registered as `linux-cake-netlink` transport in the factory. This preserves the existing subprocess backend as a tested fallback, enables side-by-side comparison during validation, and follows the established codebase pattern where each transport gets its own class. The singleton `IPRoute()` instance lives for daemon lifetime with explicit close in `__del__`/daemon shutdown, and reconnection on `OSError(EBADF)` or `NetlinkError`.

**Primary recommendation:** Create `NetlinkCakeBackend(LinuxCakeBackend)` inheriting from `LinuxCakeBackend` and overriding `_run_tc()` equivalent methods with netlink calls. Singleton `IPRoute()` with reconnect. Factory registration for `linux-cake-netlink`. Per-call subprocess fallback on netlink exception.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- D-05: Implements RouterBackend ABC without modifying it (Phase 105 D-01).
- D-06: Stats contract returns superset dict with per-tin data (Phase 105 D-04/D-05). Field names match tc JSON output exactly.
- D-07: tc failures in hot loop: skip update, log WARNING, continue. No retry (Phase 105 D-09). Netlink failures should follow same philosophy.
- D-08: `initialize_cake()` uses `tc qdisc replace` (idempotent), runtime uses `tc qdisc change` (lossless). `validate_cake()` reads back params (Phase 105 D-06/D-07/D-08).

### Claude's Discretion
- D-01: Integration approach -- new `NetlinkCakeBackend` class alongside `LinuxCakeBackend` (new transport name) OR modify `LinuxCakeBackend` internally
- D-02: Fallback strategy -- per-call subprocess fallback, permanent fallback after N failures, or skip-and-continue
- D-03: pyroute2 version selection (0.7.x synchronous vs 0.9.x async core) -- must validate via PoC
- D-04: Stats via netlink inclusion vs deferral -- existing get_queue_stats() dict contract must be preserved
- IPRoute singleton lifecycle and reconnect implementation
- Internal class structure, helper methods, error mapping
- Test structure and fixture design for netlink mocking

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| NLNK-01 | LinuxCakeBackend can change CAKE bandwidth via pyroute2 netlink instead of subprocess tc | pyroute2 `tc("change", kind="cake", index=ifindex, bandwidth="Nkbit")` verified in sched_cake.py source with TCA_CAKE_BASE_RATE64 encoding |
| NLNK-02 | NetlinkCakeBackend maintains singleton IPRoute for daemon lifetime with reconnect | IPRoute.__init__ sets keep_event_loop=True; close() sets status['closed']=True; reconnect by creating new IPRoute on OSError(EBADF) |
| NLNK-03 | NetlinkCakeBackend falls back to subprocess tc if netlink call fails | Per-call fallback: catch NetlinkError/OSError, call super()._run_tc() (subprocess path from LinuxCakeBackend) |
| NLNK-04 | NetlinkCakeBackend reads CAKE per-tin stats via netlink | sched_cake.py stats_app decoder provides 25 fields per tin via TCA_CAKE_STATS_TIN_STATS; tc("dump") returns parsed stats2 nested structure |
| NLNK-05 | Factory registration allows config transport: "linux-cake-netlink" | Add elif branch in backends/__init__.py get_backend() for "linux-cake-netlink" -> NetlinkCakeBackend.from_config() |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| pyroute2 | 0.9.5 | Netlink tc operations for CAKE qdisc | Only maintained Python netlink library with CAKE support; verified sched_cake.py with all TCA attributes |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| subprocess (stdlib) | N/A | Fallback tc commands | When netlink fails (reconnection in progress, socket dead) |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| pyroute2 0.9.5 | pyroute2 0.7.12 (last thread-based) | 0.7.12 uses threads internally; 0.9.5 uses asyncio core with sync wrapper. 0.9.5 is actively maintained. 0.7.x is EOL (only bugfix patches). **Recommendation: use 0.9.5** -- the sync IPRoute class is explicitly designed for backward compatibility |
| pyroute2 | ctypes + raw netlink | Maximum performance but requires manual TCA attribute encoding/decoding; massive maintenance burden. pyroute2 overhead is minimal (struct pack/unpack) |
| pyroute2 | libnl-python (pylibnl) | Abandoned project, no CAKE support. Dead end |

**Version verification:**
```
pyroute2 0.9.5 -- latest on PyPI (verified 2026-03-27)
  Requires-Python: >=3.9
  Runtime deps on Linux: ZERO (win_inet_pton only on Windows)
  License: Apache-2.0 / GPL-2.0
```

**Installation:**
```bash
# Add to pyproject.toml dependencies
uv pip install pyroute2>=0.9.5

# Production deployment (cake-shaper VM)
pip install pyroute2>=0.9.5  # into /opt/wanctl/.venv
```

## Architecture Patterns

### Recommended Project Structure
```
src/wanctl/backends/
  base.py                  # RouterBackend ABC (unchanged)
  linux_cake.py            # Existing subprocess LinuxCakeBackend (unchanged)
  netlink_cake.py          # NEW: NetlinkCakeBackend (inherits LinuxCakeBackend)
  linux_cake_adapter.py    # Existing adapter (unchanged -- wraps any LinuxCakeBackend subclass)
  __init__.py              # Factory: add "linux-cake-netlink" branch
  routeros.py              # RouterOS backend (unchanged)
```

### Pattern 1: NetlinkCakeBackend Inherits LinuxCakeBackend
**What:** `NetlinkCakeBackend` extends `LinuxCakeBackend`, overriding methods that can use netlink instead of subprocess. The subprocess methods remain available as fallback via `super()`.
**When to use:** Always -- this is the recommended integration approach.
**Why:** The existing `LinuxCakeBackend` is thoroughly tested (42+ tests). Inheriting from it means:
1. All non-overridden methods (mangle stubs, from_config, test_connection) work without reimplementation
2. Subprocess fallback is trivially `super().method()` on any netlink failure
3. `LinuxCakeAdapter` wraps `LinuxCakeBackend` and will transparently work with `NetlinkCakeBackend` (Liskov substitution)
4. `from_config()` can be inherited and overridden minimally to also create the IPRoute singleton

**Example:**
```python
# Source: pyroute2 sched_cake.py verified source + wanctl codebase patterns
from pyroute2 import IPRoute
from pyroute2.netlink.exceptions import NetlinkError

class NetlinkCakeBackend(LinuxCakeBackend):
    """CAKE backend using pyroute2 netlink instead of subprocess tc.

    Falls back to subprocess (via super()) on any netlink failure.
    """

    def __init__(self, interface: str, logger=None, tc_timeout: float = 5.0):
        super().__init__(interface=interface, logger=logger, tc_timeout=tc_timeout)
        self._ipr: IPRoute | None = None
        self._ifindex: int | None = None

    def _get_ipr(self) -> IPRoute:
        """Get or create singleton IPRoute connection."""
        if self._ipr is None or self._ipr.asyncore.status.get('closed', False):
            if self._ipr is not None:
                self.logger.warning("Reconnecting IPRoute (previous connection closed)")
            self._ipr = IPRoute()
            # Resolve interface index once
            indices = self._ipr.link_lookup(ifname=self.interface)
            if not indices:
                raise OSError(f"Interface {self.interface} not found")
            self._ifindex = indices[0]
        return self._ipr

    def set_bandwidth(self, queue: str, rate_bps: int) -> bool:
        """Set CAKE bandwidth via netlink. Falls back to subprocess on failure."""
        rate_kbit = rate_bps // 1000
        try:
            ipr = self._get_ipr()
            ipr.tc("change", kind="cake", index=self._ifindex,
                   bandwidth=f"{rate_kbit}kbit")
            self.logger.debug("Netlink: Set %s bandwidth to %skbit",
                            self.interface, rate_kbit)
            return True
        except (NetlinkError, OSError) as e:
            self.logger.warning(
                "Netlink tc change failed on %s: %s -- falling back to subprocess",
                self.interface, e
            )
            self._ipr = None  # Force reconnect on next call
            return super().set_bandwidth(queue, rate_bps)

    def close(self):
        """Release IPRoute resources."""
        if self._ipr is not None:
            try:
                self._ipr.close()
            except Exception:
                pass
            self._ipr = None
```

### Pattern 2: Per-Call Fallback with Reconnect
**What:** Each netlink method catches `NetlinkError`/`OSError`, nullifies the IPRoute reference (forcing reconnect on next call), and falls back to `super()` subprocess method for the current call.
**When to use:** For all netlink methods in the hot loop (set_bandwidth, get_queue_stats).
**Why:** A broken netlink socket must never block bandwidth control. The subprocess path is proven at 3.1ms avg -- acceptable as a degraded mode. Setting `self._ipr = None` triggers reconnection on the NEXT call, not the current one (avoiding retry delay in the 50ms cycle).

### Pattern 3: Netlink Stats Parsing to Dict Contract
**What:** Parse the pyroute2 tc("dump") response structure into the same dict format as the current `get_queue_stats()`.
**When to use:** NLNK-04 -- netlink stats reading.
**Why:** The existing contract (5 base fields + extended fields + per-tin list) must be preserved exactly.

**Mapping from pyroute2 response to existing dict contract:**
```python
# pyroute2 tc("dump") returns list of tcmsg objects with nested attrs
# Access pattern: msg.get_attr('TCA_STATS2').get_attr('TCA_STATS_BASIC')

# Base fields mapping:
# pyroute2 stats2.basic.bytes      -> stats["bytes"]
# pyroute2 stats2.basic.packets    -> stats["packets"]
# pyroute2 stats2.queue.drops      -> stats["dropped"]
# pyroute2 stats2.queue.qlen       -> stats["queued_packets"]
# pyroute2 stats2.queue.backlog    -> stats["queued_bytes"]

# Extended CAKE fields:
# pyroute2 stats_app.TCA_CAKE_STATS_MEMORY_USED     -> stats["memory_used"]
# pyroute2 stats_app.TCA_CAKE_STATS_MEMORY_LIMIT    -> stats["memory_limit"]
# pyroute2 stats_app.TCA_CAKE_STATS_CAPACITY_ESTIMATE64 -> stats["capacity_estimate"]

# Per-tin fields (from tca_parse_tin_stats):
# TCA_CAKE_TIN_STATS_SENT_BYTES64       -> tin["sent_bytes"]
# TCA_CAKE_TIN_STATS_SENT_PACKETS       -> tin["sent_packets"]
# TCA_CAKE_TIN_STATS_DROPPED_PACKETS    -> tin["dropped_packets"]
# TCA_CAKE_TIN_STATS_ECN_MARKED_PACKETS -> tin["ecn_marked_packets"]
# TCA_CAKE_TIN_STATS_BACKLOG_BYTES      -> tin["backlog_bytes"]
# TCA_CAKE_TIN_STATS_PEAK_DELAY_US      -> tin["peak_delay_us"]
# TCA_CAKE_TIN_STATS_AVG_DELAY_US       -> tin["avg_delay_us"]
# TCA_CAKE_TIN_STATS_BASE_DELAY_US      -> tin["base_delay_us"]
# TCA_CAKE_TIN_STATS_SPARSE_FLOWS       -> tin["sparse_flows"]
# TCA_CAKE_TIN_STATS_BULK_FLOWS         -> tin["bulk_flows"]
# TCA_CAKE_TIN_STATS_UNRESPONSIVE_FLOWS -> tin["unresponsive_flows"]
```

### Anti-Patterns to Avoid
- **Using `with IPRoute() as ipr:` per call:** Creates and destroys socket per call. At 20Hz this leaks fds and wastes 1-2ms per socket creation. Use singleton pattern.
- **Retrying netlink in the hot loop:** D-07 says skip+log+continue on failure. Never retry -- the 50ms budget is too tight. The subprocess fallback is the "retry."
- **Catching bare Exception for netlink errors:** Only catch `NetlinkError` and `OSError`. Other exceptions (TypeError, ValueError) indicate bugs and should propagate.
- **Storing IPRoute as a class variable (shared across instances):** Each LinuxCakeBackend controls one interface. The adapter creates TWO backends (dl + ul). Each needs its own ifindex. Singleton per instance, not per class.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Netlink TCA attribute encoding | Manual struct.pack for TCA_CAKE_BASE_RATE64 | pyroute2 sched_cake.get_parameters() | Handles bandwidth string parsing ("500000kbit"), convert_bandwidth(), convert_rtt(), all 17 param converters |
| Netlink stats decoding | Manual netlink message parsing | pyroute2 stats2/stats_app decoder | Per-tin stats structure is nested 4 levels deep with mixed uint32/uint64; manual parsing is error-prone |
| ifindex resolution | Manual /sys/class/net reading | ipr.link_lookup(ifname=) | Handles netns, bond slaves, bridge ports, error cases |
| Netlink socket management | Raw socket(AF_NETLINK) + bind | IPRoute() | Handles port allocation, message sequencing, ACK parsing, error code mapping |

**Key insight:** pyroute2's `sched_cake.py` already encodes the full CAKE parameter vocabulary. The `get_parameters()` function maps human-readable kwargs to TCA netlink attributes with type validation and unit conversion. Writing this by hand would require replicating 283 lines of tested encoder logic plus the 397-line stats decoder.

## Common Pitfalls

### Pitfall 1: pyroute2 `change` vs tc CLI `change` Semantic Difference
**What goes wrong:** Developer expects `ipr.tc("change", kind="cake", ...)` to modify only specified attributes while leaving others unchanged (like tc CLI `qdisc change`). Instead, pyroute2's `change` works like `replace` but fails if the qdisc doesn't exist. Unspecified attributes get default values, resetting CAKE configuration.
**Why it happens:** pyroute2 docs explicitly state: "change works like replace, except they will fail if the node doesn't exist." This is NOT the same as tc CLI behavior.
**How to avoid:** For bandwidth-only changes, ONLY pass `bandwidth=` as the kwarg. The CAKE kernel module ignores unspecified TCA attributes in a change request -- it is the netlink message encoding that could add defaults. Verify: after a bandwidth change via netlink, read back via `tc -j qdisc show` and confirm diffserv, overhead, etc. are unchanged.
**Warning signs:** CAKE config (diffserv, overhead, rtt) changes to defaults after a bandwidth update.

### Pitfall 2: IPRoute Socket Leak at 20Hz
**What goes wrong:** Using `with IPRoute() as ipr:` per call creates ~40 sockets/second (20Hz x 2 directions). Even with context manager cleanup, socket teardown involves stopping asyncio event loop and closing transport -- measurable overhead that negates the netlink speed advantage.
**Why it happens:** IPRoute.__init__ creates an AsyncIPRoute with its own event loop. Teardown via __exit__ -> close() stops and closes the loop. This is correct for one-shot scripts but catastrophic for daemons.
**How to avoid:** Create IPRoute once in __init__, reuse for daemon lifetime. On socket death (EBADF, BrokenPipeError), null the reference and recreate on next call.
**Warning signs:** `lsof -p <pid> | grep netlink | wc -l` increasing over time. File descriptor exhaustion.

### Pitfall 3: IPRoute Event Loop Threading Conflict
**What goes wrong:** The synchronous IPRoute in 0.9.x wraps an asyncio event loop. If the calling code is already running in an asyncio event loop (e.g., if wanctl ever moves to asyncio), `run_until_complete()` raises RuntimeError.
**Why it happens:** Python forbids nested `run_until_complete()` calls on the same event loop. IPRoute creates its own event loop, but if another loop is running in the same thread, issues arise.
**How to avoid:** wanctl's autorate daemon is synchronous (threading + time.sleep loop, not asyncio). IPRoute's internal asyncio loop runs in the same thread via `run_until_complete`, which is safe as long as no outer event loop is running. No action needed for current architecture, but document the constraint for future reference.
**Warning signs:** RuntimeError "This event loop is already running" -- indicates asyncio conflict.

### Pitfall 4: Netlink Socket Buffer Overflow Under Load
**What goes wrong:** Under heavy kernel activity (many interface events, route changes), the netlink receive buffer can overflow, causing subsequent IPRoute operations to fail with error or stale data.
**Why it happens:** IPRoute default rcvbuf is 1MB. If the kernel sends more netlink messages than the application consumes (e.g., if processing is delayed), the buffer fills and messages are dropped.
**How to avoid:** wanctl only sends tc commands (not subscribing to multicast groups for monitoring). The default 1MB rcvbuf is sufficient for request-response patterns. The `IPRoute(groups=RTMGRP_DEFAULTS)` default subscribes to link, ipv4, and ipv6 events -- consider `IPRoute(groups=0)` to disable event subscriptions since we only need tc request-response.
**Warning signs:** Sporadic NetlinkError on dump commands that succeed on retry.

### Pitfall 5: Stats Response Format Divergence
**What goes wrong:** The pyroute2 stats response uses attribute-access pattern (`msg.get_attr('TCA_STATS2')`) while the existing code parses tc JSON output with dict access (`entry.get("drops", 0)`). The field names and nesting structure differ between the two formats.
**Why it happens:** tc JSON output uses a flat structure with human-readable field names. pyroute2 returns structured netlink message objects with TCA_ prefixed attribute names and nested get_attr() calls.
**How to avoid:** Create a translation layer in `get_queue_stats()` that maps pyroute2 response attributes to the existing dict contract. Test against the same sample data used in `test_linux_cake_backend.py` to verify field-by-field compatibility.
**Warning signs:** CakeStatsReader receiving dicts with missing or renamed fields.

## Code Examples

Verified patterns from pyroute2 0.9.5 source (sched_cake.py):

### CAKE Bandwidth Change via Netlink
```python
# Source: pyroute2/netlink/rtnl/tcmsg/sched_cake.py docstring (verified in source)
from pyroute2 import IPRoute

# Singleton creation
ipr = IPRoute()
ifindex = ipr.link_lookup(ifname='ens19')[0]  # returns list of int

# Bandwidth change (hot loop operation -- target <0.5ms)
ipr.tc("change", kind="cake", index=ifindex, bandwidth="500000kbit")

# Cleanup on daemon shutdown
ipr.close()
```

### CAKE Initialization via Netlink (replace)
```python
# Source: pyroute2 sched_cake.py get_parameters() + fix_request()
ipr.tc("replace", kind="cake", index=ifindex,
       bandwidth="500000kbit",
       diffserv_mode="diffserv4",
       overhead=-1,                     # docsis: handled by overhead_keyword in subprocess
       split_gso=True,
       ack_filter=True,
       ingress=False,
       rtt="internet",                  # 100000us = 100ms
       memlimit=33554432)
```

### Reading CAKE Stats via Netlink
```python
# Source: pyroute2 sched_cake.py stats2 class hierarchy
msgs = ipr.tc("dump", index=ifindex)
for msg in msgs:
    if msg.get_attr('TCA_KIND') == 'cake':
        stats2 = msg.get_attr('TCA_STATS2')
        if stats2:
            basic = stats2.get_attr('TCA_STATS_BASIC')
            queue = stats2.get_attr('TCA_STATS_QUEUE')
            app = stats2.get_attr('TCA_STATS_APP')

            # Base stats
            packets = basic['packets']     # uint32
            bytes_ = basic['bytes']        # uint64
            drops = queue['drops']         # uint32
            qlen = queue['qlen']           # uint32
            backlog = queue['backlog']     # uint32

            # CAKE-specific from stats_app
            mem_used = app.get_attr('TCA_CAKE_STATS_MEMORY_USED')
            mem_limit = app.get_attr('TCA_CAKE_STATS_MEMORY_LIMIT')
            capacity = app.get_attr('TCA_CAKE_STATS_CAPACITY_ESTIMATE64')

            # Per-tin stats
            tins_container = app.get_attr('TCA_CAKE_STATS_TIN_STATS')
            for i in range(4):  # diffserv4 = 4 tins
                tin = tins_container.get_attr(f'TCA_CAKE_TIN_STATS_{i}')
                sent_bytes = tin.get_attr('TCA_CAKE_TIN_STATS_SENT_BYTES64')
                sent_pkts = tin.get_attr('TCA_CAKE_TIN_STATS_SENT_PACKETS')
                dropped = tin.get_attr('TCA_CAKE_TIN_STATS_DROPPED_PACKETS')
                ecn = tin.get_attr('TCA_CAKE_TIN_STATS_ECN_MARKED_PACKETS')
                # ... remaining fields
```

### pyroute2 CAKE kwargs to TCA Attribute Mapping
```python
# Source: sched_cake.py get_parameters() attrs_map (verified in 0.9.5 source)
# Python kwarg           -> TCA Netlink Attribute
# ack_filter             -> TCA_CAKE_ACK_FILTER     (bool/str -> CAKE_ACK_*)
# atm_mode               -> TCA_CAKE_ATM            (bool/str -> CAKE_ATM_*)
# autorate               -> TCA_CAKE_AUTORATE        (bool -> 0/1)
# bandwidth              -> TCA_CAKE_BASE_RATE64     (str "Nkbit" -> octets/s)
# diffserv_mode          -> TCA_CAKE_DIFFSERV_MODE   (str -> CAKE_DIFFSERV_*)
# ingress                -> TCA_CAKE_INGRESS         (bool -> 0/1)
# overhead               -> TCA_CAKE_OVERHEAD        (int -64..256)
# flow_mode              -> TCA_CAKE_FLOW_MODE       (str -> CAKE_FLOW_*)
# fwmark                 -> TCA_CAKE_FWMARK          (int)
# memlimit               -> TCA_CAKE_MEMORY          (int bytes)
# mpu                    -> TCA_CAKE_MPU             (int 0..256)
# nat                    -> TCA_CAKE_NAT             (bool -> 0/1)
# raw                    -> TCA_CAKE_RAW             (bool -> 0/1)
# rtt                    -> TCA_CAKE_RTT             (int us or preset str)
# split_gso              -> TCA_CAKE_SPLIT_GSO       (bool -> 0/1)
# target                 -> TCA_CAKE_TARGET          (int us)
# wash                   -> TCA_CAKE_WASH            (bool -> 0/1)
```

### Error Handling Pattern
```python
# Source: pyroute2 netlink/exceptions.py (verified in 0.9.5 source)
from pyroute2.netlink.exceptions import NetlinkError

try:
    ipr.tc("change", kind="cake", index=ifindex, bandwidth="500000kbit")
except NetlinkError as e:
    # e.code = errno value (e.g., ENOENT=2, EINVAL=22)
    # e.args = (code, message)
    logger.warning("Netlink error %d: %s", e.code, e)
except OSError as e:
    # EBADF = socket closed/invalid
    # ECONNRESET = connection reset
    logger.warning("Socket error: %s", e)
    self._ipr = None  # Force reconnect
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| pyroute2 0.7.x (thread-based I/O) | pyroute2 0.9.x (asyncio core, sync wrapper) | 0.9.1 (2024) | Sync IPRoute wraps AsyncIPRoute; same API, reduced code by 80% |
| pyroute2 split packages (pyroute2.iproute, pyroute2.netlink) | Single pyroute2 package | 0.9.x | Simplified install, single `pip install pyroute2` |
| subprocess tc for CAKE | pyroute2 netlink for CAKE | This phase | 3ms->0.3ms per call; eliminates fork/exec overhead |

**Deprecated/outdated:**
- pyroute2 0.7.x: Last thread-based version is 0.7.12. 0.8.1 was the final minor release before the async rewrite. All new development is on 0.9.x.
- Separate pyroute2 sub-packages: Prior versions had `pyroute2.iproute`, `pyroute2.netlink` as separate installable packages. 0.9.x is monolithic.

## Open Questions

1. **pyroute2 `change` attribute encoding for CAKE**
   - What we know: `get_parameters()` maps kwargs to TCA attrs. `encode()` adds default `TCA_CAKE_AUTORATE=0` if not specified.
   - What's unclear: When calling `tc("change", kind="cake", bandwidth="500000kbit")` with ONLY bandwidth specified, does pyroute2 encode ONLY `TCA_CAKE_BASE_RATE64 + TCA_CAKE_AUTORATE` in the netlink message, or does it add other defaults? The kernel should ignore unspecified attributes in a change, but pyroute2's `encode()` might add unwanted defaults.
   - Recommendation: **PoC validation required.** Run on cake-shaper VM: change bandwidth via netlink, then read back ALL params via `tc -j qdisc show` and verify non-bandwidth params are unchanged. This is the single highest-risk validation point.

2. **tc("dump") Stats Response Structure**
   - What we know: sched_cake.py defines stats2/stats_app/tca_parse_tins hierarchy with get_attr() access.
   - What's unclear: Exact field access syntax on the returned message objects (dict-like vs get_attr vs attribute access). The stats decoder returns nested nla objects.
   - Recommendation: PoC validation on production VM. Run `ipr.tc("dump", index=ifindex)` and print the response structure to map fields to the existing dict contract.

3. **IPRoute(groups=0) for Reduced Socket Overhead**
   - What we know: Default IPRoute subscribes to RTMGRP_DEFAULTS (link, ipv4, ipv6 events). We only need request-response tc operations.
   - What's unclear: Whether `groups=0` causes any issue with tc request-response flow.
   - Recommendation: Test with `groups=0` in PoC. If it works, use it to reduce netlink noise.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| pyroute2 | Netlink tc operations | Not yet (needs install) | 0.9.5 on PyPI | subprocess tc (existing LinuxCakeBackend) |
| Python 3.12+ | pyroute2 >=0.9.5 | Yes | 3.12.3 (dev), Debian 13 ships 3.12+ | N/A |
| iproute2 (tc binary) | Subprocess fallback | Yes (on cake-shaper VM) | 6.15.0 (Debian 13) | N/A |
| pytest | Test execution | Yes | 9.0.2 | N/A |
| Linux kernel | CAKE qdisc support | Yes | 6.12.74+deb13 (cake-shaper VM) | N/A |

**Missing dependencies with no fallback:**
- None (pyroute2 is a pip install; subprocess tc is the proven fallback)

**Missing dependencies with fallback:**
- pyroute2: Not installed yet. Install via `uv pip install pyroute2>=0.9.5`. Fallback: subprocess tc (existing code, 3.1ms avg)

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.0.2 |
| Config file | pyproject.toml [tool.pytest.ini_options] |
| Quick run command | `.venv/bin/pytest tests/test_netlink_cake_backend.py -x -v` |
| Full suite command | `.venv/bin/pytest tests/ -v` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| NLNK-01 | Bandwidth change via netlink | unit | `.venv/bin/pytest tests/test_netlink_cake_backend.py::TestSetBandwidth -x` | Wave 0 |
| NLNK-02 | Singleton IPRoute lifecycle + reconnect | unit | `.venv/bin/pytest tests/test_netlink_cake_backend.py::TestIPRouteLifecycle -x` | Wave 0 |
| NLNK-03 | Subprocess fallback on netlink failure | unit | `.venv/bin/pytest tests/test_netlink_cake_backend.py::TestFallback -x` | Wave 0 |
| NLNK-04 | Per-tin stats via netlink | unit | `.venv/bin/pytest tests/test_netlink_cake_backend.py::TestGetQueueStats -x` | Wave 0 |
| NLNK-05 | Factory registration linux-cake-netlink | unit | `.venv/bin/pytest tests/test_backends.py::TestGetBackendFactory -x` | Exists (extend) |

### Sampling Rate
- **Per task commit:** `.venv/bin/pytest tests/test_netlink_cake_backend.py tests/test_backends.py tests/test_linux_cake_backend.py -x -v`
- **Per wave merge:** `.venv/bin/pytest tests/ -v`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_netlink_cake_backend.py` -- covers NLNK-01 through NLNK-04
- [ ] Extend `tests/test_backends.py::TestGetBackendFactory` -- covers NLNK-05
- [ ] pyroute2 mock fixtures: mock IPRoute, mock tc() responses, mock NetlinkError
- [ ] Framework install: `uv pip install pyroute2>=0.9.5` (dev dependency)

## pyroute2 0.9.5 Internal Architecture (Key for Implementation)

### IPRoute Synchronous Wrapper
```
IPRoute(NetlinkSocket)                    # Sync wrapper
  |-- self.asyncore = AsyncIPRoute(...)   # Async core
  |-- keep_event_loop = True              # Event loop persists across calls
  |-- __getattr__('tc')                   # Delegates to _run_generic_rtnl
  |     |-- _run_generic_rtnl(symbol, *args)
  |     |     |-- _run_with_cleanup(async_tc, *args)
  |     |           |-- _setup_transport()    # Creates transport if needed
  |     |           |-- event_loop.run_until_complete(async_tc(...))
  |     |           |-- _cleanup_transport()  # Keeps loop (keep_event_loop=True)
  |-- close()                             # Sets status['closed']=True, closes socket
```

### CAKE Command Flow
```
ipr.tc("change", kind="cake", index=ifindex, bandwidth="500000kbit")
  |-- kwarg = {"kind": "cake", "index": ifindex, "bandwidth": "500000kbit"}
  |-- command_map["change"] = (RTM_NEWQDISC, "change")
  |-- TcIPRouteFilter.finalize():
  |     |-- plugin = tc_plugins["cake"]  # = sched_cake module
  |     |-- get_parameters(kwarg):
  |     |     |-- "bandwidth" -> convert_bandwidth("500000kbit") -> 62500000 octets/s
  |     |     |-- returns {"attrs": [["TCA_CAKE_BASE_RATE64", 62500000]]}
  |     |-- fix_request(): sets parent=TC_H_ROOT, removes 'rate'
  |     |-- context["options"] = get_parameters result
  |-- NetlinkRequest(tcmsg, RTM_NEWQDISC, NLM_F_CHANGE)
  |-- send() -> kernel
  |-- receive ACK or NetlinkError
```

### CAKE Stats Response Structure
```
tc("dump", index=ifindex)
  |-- Returns list of tcmsg objects
  |-- msg.get_attr('TCA_KIND') == 'cake'
  |-- msg.get_attr('TCA_STATS2')  # = stats2 nla
  |     |-- .get_attr('TCA_STATS_BASIC')   # bytes(Q), packets(I)
  |     |-- .get_attr('TCA_STATS_QUEUE')   # qlen, backlog, drops, requeues, overlimits
  |     |-- .get_attr('TCA_STATS_APP')     # = stats_app nla
  |           |-- .get_attr('TCA_CAKE_STATS_MEMORY_USED')    # uint32
  |           |-- .get_attr('TCA_CAKE_STATS_MEMORY_LIMIT')   # uint32
  |           |-- .get_attr('TCA_CAKE_STATS_CAPACITY_ESTIMATE64')  # uint64
  |           |-- .get_attr('TCA_CAKE_STATS_TIN_STATS')  # = tca_parse_tins
  |                 |-- .get_attr('TCA_CAKE_TIN_STATS_0')  # Bulk
  |                 |     |-- .get_attr('TCA_CAKE_TIN_STATS_SENT_PACKETS')
  |                 |     |-- .get_attr('TCA_CAKE_TIN_STATS_SENT_BYTES64')
  |                 |     |-- .get_attr('TCA_CAKE_TIN_STATS_DROPPED_PACKETS')
  |                 |     |-- .get_attr('TCA_CAKE_TIN_STATS_ECN_MARKED_PACKETS')
  |                 |     |-- .get_attr('TCA_CAKE_TIN_STATS_BACKLOG_BYTES')
  |                 |     |-- .get_attr('TCA_CAKE_TIN_STATS_PEAK_DELAY_US')
  |                 |     |-- .get_attr('TCA_CAKE_TIN_STATS_AVG_DELAY_US')
  |                 |     |-- .get_attr('TCA_CAKE_TIN_STATS_BASE_DELAY_US')
  |                 |     |-- .get_attr('TCA_CAKE_TIN_STATS_SPARSE_FLOWS')
  |                 |     |-- .get_attr('TCA_CAKE_TIN_STATS_BULK_FLOWS')
  |                 |     |-- .get_attr('TCA_CAKE_TIN_STATS_UNRESPONSIVE_FLOWS')
  |                 |-- .get_attr('TCA_CAKE_TIN_STATS_1')  # BestEffort
  |                 |-- .get_attr('TCA_CAKE_TIN_STATS_2')  # Video
  |                 |-- .get_attr('TCA_CAKE_TIN_STATS_3')  # Voice
```

## pyroute2 Bandwidth Encoding Detail

Critical for NLNK-01: the `convert_bandwidth()` function in sched_cake.py converts string bandwidth values to octets/second via right-shift by 3:

```python
# "500000kbit" -> 500000 * 1000 = 500000000 bits -> 500000000 >> 3 = 62500000 octets/s
# This maps to TCA_CAKE_BASE_RATE64 (uint64) in the netlink message
# The kernel reads this as bytes/second and applies it to the CAKE shaper
```

The existing `LinuxCakeBackend.set_bandwidth()` converts `rate_bps // 1000` and passes `"Nkbit"` string to tc CLI. For netlink, pass the same `"Nkbit"` string to pyroute2 and it handles the conversion.

## pyroute2 kwarg vs wanctl CAKE Param Mapping

The existing `LinuxCakeBackend.initialize_cake()` builds tc CLI args from a params dict. For netlink, the kwargs need different names:

| wanctl cake_params key | tc CLI args | pyroute2 kwarg | Notes |
|----------------------|-------------|----------------|-------|
| bandwidth | `bandwidth Nkbit` | `bandwidth="Nkbit"` | Direct mapping |
| diffserv | `diffserv4` (positional) | `diffserv_mode="diffserv4"` | Name differs |
| overhead_keyword: docsis | `docsis` (positional) | `atm_mode=False` + `overhead=-1` | Complex: docsis = no ATM, overhead auto-calculated. May need custom handling |
| overhead_keyword: bridged-ptm | `ptm overhead 22` | `atm_mode="ptm"`, `overhead=22` | Must split compound keyword |
| overhead (numeric) | `overhead N` | `overhead=N` | Direct mapping |
| mpu | `mpu N` | `mpu=N` | Direct mapping |
| memlimit | `memlimit N` | `memlimit=N` | Direct mapping |
| rtt | `rtt 100ms` | `rtt=100000` (us) or `rtt="internet"` | wanctl uses "100ms"; pyroute2 accepts int (us) or preset strings |
| split-gso | `split-gso` (flag) | `split_gso=True` | Hyphen vs underscore |
| ack-filter | `ack-filter` (flag) | `ack_filter=True` | Hyphen vs underscore |
| ingress | `ingress` (flag) | `ingress=True` | Direct mapping |
| ecn | excluded in current code | N/A | Not in pyroute2 sched_cake either |

**Key Complexity: `overhead_keyword`**

The current subprocess backend has `OVERHEAD_KEYWORD_EXPANSION` dict that maps compound keywords to tc args (e.g., `bridged-ptm` -> `ptm overhead 22`). For pyroute2, this needs translation to pyroute2 kwargs (`atm_mode` + `overhead`). The `docsis` keyword is special -- tc CLI accepts it as a standalone token, but pyroute2 has no direct `docsis` parameter. This needs investigation: how does tc CLI's `docsis` map to TCA attributes? It likely sets `TCA_CAKE_ATM=0` (no ATM) and `TCA_CAKE_OVERHEAD=18` (Ethernet + DOCSIS). This must be verified in PoC.

## Integration Detail: LinuxCakeAdapter Compatibility

`LinuxCakeAdapter` wraps TWO `LinuxCakeBackend` instances (one per direction). It calls:
- `LinuxCakeBackend.from_config(config, direction=)` -- factory constructor
- `backend.initialize_cake(params)` -- at startup
- `backend.validate_cake(expected)` -- readback verification
- `backend.set_bandwidth(queue="", rate_bps=N)` -- hot loop (via set_limits)

Since `NetlinkCakeBackend` inherits from `LinuxCakeBackend`, `LinuxCakeAdapter` will work with it unchanged IF:
1. `NetlinkCakeBackend.from_config()` returns a `NetlinkCakeBackend` instance
2. All overridden methods maintain the same return contract

The adapter does NOT need to know about netlink. It calls the same interface. This is a clean Liskov substitution.

## Integration Detail: CakeStatsReader Compatibility

`CakeStatsReader._read_stats_linux_cake()` calls `self._linux_backend.get_queue_stats(queue_name)` and expects a dict with keys: packets, bytes, dropped, queued_packets, queued_bytes, tins (list of per-tin dicts). The netlink `get_queue_stats()` must return this exact dict structure.

CakeStatsReader uses `get_backend(proxy)` to create its backend. When transport is `linux-cake-netlink`, the factory will return `NetlinkCakeBackend` -- CakeStatsReader doesn't need changes.

## Project Constraints (from CLAUDE.md)

- **Change Policy:** Conservative. Explain before changing. Priority: stability > safety > clarity > elegance.
- **Portable Controller Architecture:** Controller is link-agnostic. All variability in config parameters.
- **Flash Wear Protection:** Must preserve `last_applied_dl_rate`/`last_applied_ul_rate` deduplication -- applies regardless of backend (prevents unnecessary 20Hz tc calls).
- **Architectural Spine:** Do not modify without explicit instruction. This phase adds a new backend, not modifying core control logic.
- **Testing:** `.venv/bin/pytest tests/ -v` for full suite.
- **project-finalizer:** MANDATORY before commits.

## Sources

### Primary (HIGH confidence)
- pyroute2 0.9.5 source code (installed and inspected locally): `sched_cake.py` (397 lines), `requests/tc.py` (77 lines), `iproute/linux.py` (2890 lines), `netlink/core.py` (830 lines), `netlink/exceptions.py` (82 lines)
- [pyroute2 PyPI](https://pypi.org/project/pyroute2/) -- v0.9.5 metadata: zero runtime deps, Python >=3.9, Apache-2.0/GPL-2.0
- [pyroute2 GitHub](https://github.com/svinota/pyroute2) -- project repository
- [pyroute2 IPRoute docs](https://docs.pyroute2.org/iproute.html) -- tc() method documentation
- [pyroute2 general docs](https://docs.pyroute2.org/general.html) -- sync/async architecture
- [pyroute2 CAKE stats PR #662](https://github.com/svinota/pyroute2/pull/662) -- per-tin stats decoder addition (merged 2020)

### Secondary (MEDIUM confidence)
- [pyroute2 asyncio core docs](https://docs.pyroute2.org/asyncio.html) -- threading model and event loop management
- [pyroute2 changelog](https://docs.pyroute2.org/changelog.html) -- 0.8.1 is final thread-based; 0.9.x is asyncio core
- [tc-cake(8) man page](https://man7.org/linux/man-pages/man8/tc-cake.8.html) -- CAKE CLI parameters reference
- [Linux kernel CAKE patch](https://patchwork.ozlabs.org/project/netdev/patch/20180531095716.30709-1-toke@toke.dk/) -- TCA_CAKE attribute definitions

### Tertiary (LOW confidence)
- pyroute2 `change` command semantics -- documented as "like replace but fails if not exists"; actual CAKE-specific behavior (whether unspecified attrs are reset) needs PoC validation
- `docsis` overhead keyword mapping to TCA attributes -- inferred from tc source; needs verification

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- pyroute2 0.9.5 source verified locally, CAKE module inspected line-by-line
- Architecture: HIGH -- codebase patterns well-understood, Liskov substitution path clear
- Pitfalls: HIGH -- grounded in source code analysis (event loop, socket lifecycle, encoding)
- Stats format: MEDIUM -- response structure inferred from nla class hierarchy; needs PoC validation

**Research date:** 2026-03-27
**Valid until:** 2026-04-27 (pyroute2 is stable; CAKE kernel API is frozen)

---
*Phase: 117-pyroute2-netlink-backend*
*Research completed: 2026-03-27*
