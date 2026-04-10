# Phase 105: LinuxCakeBackend Core - Research

**Researched:** 2026-03-24
**Domain:** Python RouterBackend implementation for Linux CAKE qdisc control via subprocess + tc
**Confidence:** HIGH

## Summary

Phase 105 creates a new `LinuxCakeBackend` class in `src/wanctl/backends/linux_cake.py` that implements the existing `RouterBackend` ABC using local `tc` subprocess calls instead of SSH/REST to a MikroTik router. The backend handles four operations: bandwidth updates via `tc qdisc change`, stats collection via `tc -j -s qdisc show` (JSON), CAKE initialization via `tc qdisc replace`, and parameter validation via readback. All operations are local subprocess calls (~1-3ms) with zero new Python dependencies.

The implementation follows established patterns: `RouterOSBackend` provides the reference implementation for ABC compliance, `subprocess.run` with `capture_output=True, text=True, timeout=N` is the proven subprocess pattern used throughout wanctl (irtt, calibrate, benchmark), and the `CommandResult` type from `router_command_utils.py` provides type-safe error handling. Per-tin statistics parsing from CAKE JSON output adds significant observability over the current MikroTik aggregate-only stats.

**Primary recommendation:** Implement LinuxCakeBackend as a single file (`linux_cake.py`) with subprocess tc calls, JSON parsing via stdlib `json`, no-op stubs for mangle rule methods, and comprehensive tests in a new `tests/test_linux_cake_backend.py`. Follow RouterOSBackend patterns exactly for ABC compliance and test structure.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- D-01: LinuxCakeBackend implements the existing RouterBackend ABC in `backends/base.py` without modifying the ABC.
- D-02: Mangle rule methods (`enable_rule`, `disable_rule`, `is_rule_enabled`) use no-op stubs: `enable_rule` returns True, `disable_rule` returns True, `is_rule_enabled` returns None. These are never called in the Linux CAKE flow -- steering handles mangle rules through its separate RouterOSController (Phase 108).
- D-03: No ABC refactoring. Splitting into BandwidthBackend/RuleBackend protocols is deferred unless the ABC becomes a real integration bottleneck.
- D-04: `get_queue_stats()` returns a superset dict -- the existing 5 fields (`packets`, `bytes`, `dropped`, `queued_packets`, `queued_bytes`) PLUS new fields: `tins` (list of per-tin dicts), `memory_used`, `memory_limit`, `ecn_marked`, `capacity_estimate`. Consumers that only read old fields work unchanged.
- D-05: Per-tin dicts contain: `sent_bytes`, `sent_packets`, `dropped_packets`, `ecn_marked_packets`, `backlog_bytes`, `peak_delay_us`, `avg_delay_us`, `base_delay_us`, `sparse_flows`, `bulk_flows`, `unresponsive_flows`. Field names match tc JSON output exactly.
- D-06: LinuxCakeBackend owns CAKE initialization via `initialize_cake()` method using `tc qdisc replace`. Called at daemon startup. This is required because systemd-networkd silently drops CAKE params if a qdisc already exists (systemd issue #31226).
- D-07: `validate_cake()` reads back params via `tc -j qdisc show` and verifies diffserv mode, overhead, bandwidth, and other parameters match expectations. Called after `initialize_cake()`.
- D-08: Runtime bandwidth updates use `set_bandwidth()` -> `tc qdisc change dev <iface> root cake bandwidth <rate>kbit`. Only bandwidth changes -- other CAKE params persist from initialization.
- D-09: tc command failures in the 50ms control loop: skip the update, log at WARNING level, continue to next cycle. No retry -- tc is local (~2ms), failures indicate system issues (module unloaded, permissions) not transient network blips. Next cycle retries naturally.
- D-10: `test_connection()` verifies both `tc` binary availability and CAKE qdisc presence on the configured interface.

### Claude's Discretion
- Internal class structure (helper methods, dataclasses for stats)
- subprocess.run timeout values
- Log message formatting and levels
- Test structure and fixture design

### Deferred Ideas (OUT OF SCOPE)
- ABC refactoring into BandwidthBackend/RuleBackend protocols -- revisit if interface mismatch causes real problems
- pyroute2 netlink backend -- deferred requirement PERF-01, only if subprocess tc proves too slow
- "Investigate LXC container network optimizations" todo -- out of scope, relates to old container topology
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| BACK-01 | LinuxCakeBackend implements RouterBackend with `set_bandwidth()` via `tc qdisc change` | RouterBackend ABC fully documented (base.py), `tc qdisc change` is lossless bandwidth update (confirmed by cake-autorate, tc-cake(8) man page). Rate unit is kbit. |
| BACK-02 | LinuxCakeBackend parses queue stats via `tc -j -s qdisc show` with JSON output | Full JSON schema verified from iproute2 source: top-level fields (bytes, packets, drops, backlog, qlen) + CAKE xstats (memory_used, memory_limit, capacity_estimate, tins[]) |
| BACK-03 | LinuxCakeBackend validates CAKE params after `tc qdisc replace` -- reads back via `tc -j qdisc show` and verifies diffserv mode, overhead, bandwidth match expectations | JSON options section contains: bandwidth (numeric bps), diffserv (string), overhead (int), wash (bool), nat (bool), ingress (bool), ack-filter (string), split_gso (bool), rtt (int usec) |
| BACK-04 | Per-tin statistics parsed from CAKE (Voice/Video/BE/Bulk -- drops, delays, flows per tin) | 20 per-tin fields verified from iproute2 source. Tin order in diffserv4: index 0=Bulk, 1=BestEffort, 2=Video, 3=Voice. |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| subprocess (stdlib) | Python 3.12 | Execute tc commands locally | Zero new deps. Established wanctl pattern (irtt_measurement.py, calibrate.py, benchmark.py). `subprocess.run(cmd, capture_output=True, text=True, timeout=N)` with `shell=False`. |
| json (stdlib) | Python 3.12 | Parse tc -j JSON output | Zero new deps. CAKE JSON output is well-formed JSON from iproute2 6.1.0. |
| logging (stdlib) | Python 3.12 | Structured logging | Existing pattern -- RouterBackend ABC provides `self.logger`. |
| shutil (stdlib) | Python 3.12 | `shutil.which("tc")` for binary detection | Lightweight way to check tc availability in `test_connection()`. |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| wanctl.backends.base | existing | RouterBackend ABC | Always -- LinuxCakeBackend extends this |
| wanctl.router_command_utils | existing | CommandResult type | Optional -- for type-safe returns in internal helpers |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| subprocess + tc | pyroute2 netlink | pyroute2 has only a stats decoder for CAKE (PR #662, 2020). No verified CAKE control operations. Adds ~15MB dependency. Deferred as PERF-01. |
| json.loads() | regex parsing | tc JSON is stable structured output since iproute2 4.19. JSON parsing is cleaner, less fragile, and captures per-tin arrays naturally. |

**Installation:**
```bash
# No new Python packages needed. tc is from iproute2 (OS package).
# On the target VM:
apt install iproute2  # Already default in Debian 12
```

**Version verification:** All stdlib -- no version check needed. tc version confirmed at 6.1.0-3 on Debian 12 (bookworm).

## Architecture Patterns

### Recommended Project Structure
```
src/wanctl/backends/
    __init__.py          # get_backend() factory (Phase 107 adds linux-cake branch)
    base.py              # RouterBackend ABC (READ-ONLY, do not modify)
    routeros.py          # RouterOSBackend (reference implementation)
    linux_cake.py        # NEW: LinuxCakeBackend implementation

tests/
    test_backends.py              # Existing RouterBackend + RouterOSBackend tests
    test_linux_cake_backend.py    # NEW: LinuxCakeBackend tests
```

### Pattern 1: subprocess.run for tc Commands
**What:** Execute tc commands via subprocess.run with shell=False, capture_output, text mode, and timeout.
**When to use:** Every tc command (change, show, replace).
**Example:**
```python
# Source: Established wanctl pattern from irtt_measurement.py
import subprocess

def _run_tc(self, args: list[str], timeout: float = 5.0) -> tuple[int, str, str]:
    """Execute a tc command and return (returncode, stdout, stderr).

    Args:
        args: tc subcommand arguments (e.g., ["qdisc", "show", "dev", "eth0"])
        timeout: Command timeout in seconds

    Returns:
        Tuple of (return_code, stdout, stderr)
    """
    cmd = ["tc"] + args
    try:
        result = subprocess.run(  # noqa: S603 -- hardcoded tc invocation
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        self.logger.warning(f"tc command timed out after {timeout}s: {' '.join(cmd)}")
        return -1, "", "timeout"
    except FileNotFoundError:
        self.logger.error("tc binary not found")
        return -1, "", "tc not found"
```

### Pattern 2: JSON Stats Parsing with Superset Dict
**What:** Parse tc -j -s output into dict with both legacy 5-field contract and new extended fields.
**When to use:** `get_queue_stats()` implementation.
**Example:**
```python
# Source: Verified from iproute2 q_cake.c source
import json

def _parse_cake_stats(self, json_output: str) -> dict | None:
    """Parse tc -j -s qdisc show JSON into stats dict.

    Returns superset dict compatible with existing consumers (5 base fields)
    plus extended CAKE fields (tins, memory, ecn, capacity).
    """
    try:
        data = json.loads(json_output)
    except json.JSONDecodeError as e:
        self.logger.error(f"Failed to parse tc JSON: {e}")
        return None

    if not data or not isinstance(data, list):
        self.logger.warning("Empty or invalid tc JSON output")
        return None

    # Find CAKE qdisc entry
    cake_entry = None
    for entry in data:
        if isinstance(entry, dict) and entry.get("kind") == "cake":
            cake_entry = entry
            break

    if cake_entry is None:
        self.logger.error("No CAKE qdisc found in tc output")
        return None

    # Base 5 fields (backward-compatible contract)
    stats: dict = {
        "packets": cake_entry.get("packets", 0),
        "bytes": cake_entry.get("bytes", 0),
        "dropped": cake_entry.get("drops", 0),      # tc uses "drops"
        "queued_packets": cake_entry.get("qlen", 0),
        "queued_bytes": cake_entry.get("backlog", 0),
    }

    # Extended CAKE fields
    stats["memory_used"] = cake_entry.get("memory_used", 0)
    stats["memory_limit"] = cake_entry.get("memory_limit", 0)
    stats["ecn_marked"] = 0  # Sum across tins below
    stats["capacity_estimate"] = cake_entry.get("capacity_estimate", 0)

    # Per-tin statistics
    raw_tins = cake_entry.get("tins", [])
    tins = []
    total_ecn = 0
    for tin in raw_tins:
        tin_stats = {
            "sent_bytes": tin.get("sent_bytes", 0),
            "sent_packets": tin.get("sent_packets", 0),
            "dropped_packets": tin.get("drops", 0),        # NOTE: tc JSON = "drops"
            "ecn_marked_packets": tin.get("ecn_mark", 0),  # NOTE: tc JSON = "ecn_mark"
            "backlog_bytes": tin.get("backlog_bytes", 0),
            "peak_delay_us": tin.get("peak_delay_us", 0),
            "avg_delay_us": tin.get("avg_delay_us", 0),
            "base_delay_us": tin.get("base_delay_us", 0),
            "sparse_flows": tin.get("sparse_flows", 0),
            "bulk_flows": tin.get("bulk_flows", 0),
            "unresponsive_flows": tin.get("unresponsive_flows", 0),
        }
        total_ecn += tin_stats["ecn_marked_packets"]
        tins.append(tin_stats)
    stats["tins"] = tins
    stats["ecn_marked"] = total_ecn

    return stats
```

### Pattern 3: No-op Stubs for Inapplicable Methods
**What:** Mangle rule methods return safe defaults since LinuxCakeBackend only handles shaping.
**When to use:** `enable_rule`, `disable_rule`, `is_rule_enabled`.
**Example:**
```python
def enable_rule(self, comment: str) -> bool:
    """No-op: mangle rules stay on MikroTik router (Phase 108)."""
    self.logger.debug(f"enable_rule no-op on linux-cake backend: {comment}")
    return True

def disable_rule(self, comment: str) -> bool:
    """No-op: mangle rules stay on MikroTik router (Phase 108)."""
    self.logger.debug(f"disable_rule no-op on linux-cake backend: {comment}")
    return True

def is_rule_enabled(self, comment: str) -> bool | None:
    """No-op: mangle rules stay on MikroTik router (Phase 108)."""
    return None
```

### Pattern 4: Constructor with Interface Names
**What:** LinuxCakeBackend takes interface name instead of host/user/key.
**When to use:** `__init__` and `from_config`.
**Example:**
```python
class LinuxCakeBackend(RouterBackend):
    def __init__(
        self,
        interface: str,
        logger: logging.Logger | None = None,
        tc_timeout: float = 5.0,
    ):
        super().__init__(logger)
        self.interface = interface
        self.tc_timeout = tc_timeout
```

### Anti-Patterns to Avoid
- **CAKE on bridge interface itself:** Forwarded traffic bypasses bridge device qdisc. Always attach to member ports.
- **shell=True in subprocess.run:** Command injection risk. Always use list-form `cmd` with `shell=False`.
- **Parsing text output from tc:** Use `tc -j` for JSON. Text parsing with regex is fragile and already proven problematic in the RouterOS backend.
- **Using `tc qdisc replace` for runtime bandwidth changes:** `replace` does atomic remove+add (resets counters, drops in-flight). `change` modifies in-place without packet loss. Only use `replace` at initialization.
- **Retrying on tc failure:** tc is local (~2ms). Failures mean system issues (module unloaded, permissions). Next cycle retries naturally per D-09.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| JSON parsing | Custom regex parser | `json.loads()` on `tc -j` output | tc JSON is stable, structured. Regex is fragile. |
| tc binary detection | Custom PATH search | `shutil.which("tc")` | Stdlib, handles all edge cases. |
| Error result type | Custom tuple returns | `CommandResult` from `router_command_utils.py` | Already exists, type-safe, supports unwrap pattern. |
| Stats dict structure | Custom dataclass | Plain dict matching `get_queue_stats()` contract | ABC contract returns `dict | None`. Dataclass adds unnecessary conversion layer. |

**Key insight:** This backend is simple -- 7 ABC methods + 2 new methods (initialize_cake, validate_cake). The complexity is in correct tc command construction and JSON field mapping, not in architecture.

## Common Pitfalls

### Pitfall 1: tc JSON Field Name Mismatch (Per-Tin)
**What goes wrong:** D-05 specifies `dropped_packets` and `ecn_marked_packets` as per-tin field names matching tc JSON. But the actual iproute2 source (q_cake.c `cake_print_json_tin`) uses `drops` and `ecn_mark` for per-tin JSON fields.
**Why it happens:** The CONTEXT.md decision D-05 appears to have been based on earlier research that assumed longer field names. The iproute2 source uses abbreviated names in JSON.
**How to avoid:** Map tc JSON field names to the D-05 consumer-facing names in the parsing layer. The per-tin dict returned to consumers uses D-05 names (`dropped_packets`, `ecn_marked_packets`), but the JSON parser reads `drops` and `ecn_mark` from tc output. This mapping is shown in Pattern 2 above.
**Warning signs:** Tests that mock tc JSON output with wrong field names will pass but production will fail.

### Pitfall 2: Bandwidth Value Format in JSON
**What goes wrong:** Assuming bandwidth in tc JSON output is a human-readable string like `"500Mbit"`.
**Why it happens:** Text-mode `tc qdisc show` outputs human-readable rates. The STACK.md research examples incorrectly show `"bandwidth": "500Mbit"` in JSON.
**How to avoid:** In JSON mode (`tc -j`), iproute2 outputs bandwidth as a **numeric value in bits per second** (verified from iproute2 `json_print.c`: `print_color_rate` calls `print_color_lluint` in JSON context). Parse as int, not string. Similarly, `capacity_estimate` and `threshold_rate` are numeric bps in JSON. The `rtt` field is numeric microseconds.
**Warning signs:** `json.loads()` will parse the number correctly, but `get_bandwidth()` must return bps (matching the ABC contract) and `validate_cake()` must compare numeric bps.

### Pitfall 3: Top-Level "drops" vs Stats Dict "dropped"
**What goes wrong:** The tc JSON top-level field is `"drops"` (plural), but the RouterBackend stats contract uses `"dropped"`. Mixing them up causes consumers to get zero drops.
**Why it happens:** Generic qdisc stats layer uses `drops`, RouterOS backend historically used `dropped`.
**How to avoid:** Explicit mapping in `_parse_cake_stats()`: `stats["dropped"] = cake_entry.get("drops", 0)`.

### Pitfall 4: subprocess.TimeoutExpired Exception
**What goes wrong:** `subprocess.run` raises `subprocess.TimeoutExpired` if tc hangs (unlikely but possible during kernel module issues). If uncaught, it crashes the 50ms control loop.
**Why it happens:** tc is normally ~1-3ms, but kernel issues or resource exhaustion could cause delays.
**How to avoid:** Wrap `subprocess.run` in try/except catching both `TimeoutExpired` and `FileNotFoundError`. Return error tuple, let caller handle per D-09 (skip and log).

### Pitfall 5: `tc qdisc change` on Non-Existent CAKE Qdisc
**What goes wrong:** If CAKE qdisc was not initialized (or was removed), `tc qdisc change` returns error "RTNETLINK answers: No such file or directory".
**Why it happens:** `change` modifies an existing qdisc. If none exists, it cannot modify anything.
**How to avoid:** `test_connection()` verifies CAKE qdisc presence at startup. `initialize_cake()` must be called before the control loop starts. If `set_bandwidth()` fails, the next cycle retries naturally (D-09).

### Pitfall 6: Security Annotations for subprocess
**What goes wrong:** Ruff/bandit flags `subprocess.run` with S603 (subprocess call with non-constant arguments).
**Why it happens:** Static analysis cannot verify the arguments are safe.
**How to avoid:** Add `# noqa: S603` or `# nosec B603` comment with explanation, matching existing wanctl pattern (see irtt_measurement.py line 90, calibrate.py line 201). The tc command arguments are constructed from config values, not user input.

### Pitfall 7: Tin Order Assumption
**What goes wrong:** Assuming tin index maps to a specific traffic class without verifying.
**Why it happens:** CAKE diffserv4 tin order is: 0=Bulk, 1=BestEffort, 2=Video, 3=Voice. But this order could theoretically change in future kernel versions.
**How to avoid:** For Phase 105, use index-based mapping (0=Bulk, 1=BE, 2=Video, 3=Voice) per confirmed CAKE diffserv4 semantics. Document the assumption. A future enhancement could parse `threshold_rate` to infer tin identity.

## Code Examples

### Complete set_bandwidth Implementation
```python
# Source: RouterBackend ABC contract + tc-cake(8) man page
def set_bandwidth(self, queue: str, rate_bps: int) -> bool:
    """Set CAKE bandwidth via tc qdisc change.

    Args:
        queue: Ignored for linux-cake (interface set at init). Kept for ABC compat.
        rate_bps: Bandwidth limit in bits per second.

    Returns:
        True if tc command succeeded, False otherwise.
    """
    rate_kbit = rate_bps // 1000
    rc, _, err = self._run_tc(
        ["qdisc", "change", "dev", self.interface, "root", "cake",
         "bandwidth", f"{rate_kbit}kbit"],
        timeout=self.tc_timeout,
    )
    if rc == 0:
        self.logger.debug(f"Set {self.interface} bandwidth to {rate_kbit}kbit")
        return True
    self.logger.warning(f"tc qdisc change failed on {self.interface}: {err}")
    return False
```

### Complete get_bandwidth Implementation
```python
# Source: iproute2 json_print.c -- bandwidth is numeric bps in JSON
def get_bandwidth(self, queue: str) -> int | None:
    """Get current CAKE bandwidth from tc JSON output.

    Returns:
        Current bandwidth in bps, or None on error.
    """
    rc, out, err = self._run_tc(
        ["-j", "qdisc", "show", "dev", self.interface],
        timeout=self.tc_timeout,
    )
    if rc != 0:
        self.logger.error(f"tc qdisc show failed on {self.interface}: {err}")
        return None

    try:
        data = json.loads(out)
        for entry in data:
            if isinstance(entry, dict) and entry.get("kind") == "cake":
                options = entry.get("options", {})
                bw = options.get("bandwidth")
                if bw is not None:
                    return int(bw)  # Already bps in JSON mode
        self.logger.warning(f"No CAKE qdisc found on {self.interface}")
        return None
    except (json.JSONDecodeError, ValueError, TypeError) as e:
        self.logger.error(f"Failed to parse bandwidth from tc output: {e}")
        return None
```

### Complete test_connection Implementation
```python
# Source: D-10 decision
def test_connection(self) -> bool:
    """Verify tc binary exists and CAKE qdisc is present on interface.

    Returns:
        True if tc is available AND CAKE qdisc found on self.interface.
    """
    if not shutil.which("tc"):
        self.logger.error("tc binary not found in PATH")
        return False

    rc, out, err = self._run_tc(
        ["-j", "qdisc", "show", "dev", self.interface],
        timeout=self.tc_timeout,
    )
    if rc != 0:
        self.logger.error(f"tc qdisc show failed on {self.interface}: {err}")
        return False

    try:
        data = json.loads(out)
        for entry in data:
            if isinstance(entry, dict) and entry.get("kind") == "cake":
                return True
        self.logger.warning(f"No CAKE qdisc found on {self.interface}")
        return False
    except json.JSONDecodeError:
        self.logger.error("Failed to parse tc JSON output")
        return False
```

### Complete initialize_cake Implementation
```python
# Source: D-06, OPENSOURCE-CAKE.md ecosystem patterns
def initialize_cake(self, params: dict) -> bool:
    """Initialize CAKE qdisc on interface via tc qdisc replace.

    Uses 'replace' for idempotency: creates if absent, replaces if present.
    Called once at daemon startup, NOT during the 50ms control loop.

    Args:
        params: CAKE parameters dict with keys like:
            bandwidth (str): e.g., "500000kbit"
            diffserv (str): e.g., "diffserv4"
            overhead_keyword (str): e.g., "docsis" or "bridged-ptm"
            Extra params: "split-gso", "ack-filter", "ingress", "ecn", etc.

    Returns:
        True if tc qdisc replace succeeded.
    """
    cmd_args = ["qdisc", "replace", "dev", self.interface, "root", "cake"]

    # Add each parameter
    if "bandwidth" in params:
        cmd_args.extend(["bandwidth", params["bandwidth"]])
    if "diffserv" in params:
        cmd_args.append(params["diffserv"])
    # ... additional params per Phase 106 CAKE config

    rc, _, err = self._run_tc(cmd_args, timeout=10.0)
    if rc == 0:
        self.logger.info(f"Initialized CAKE on {self.interface}")
        return True
    self.logger.error(f"Failed to initialize CAKE on {self.interface}: {err}")
    return False
```

### Complete validate_cake Implementation
```python
# Source: D-07, systemd issue #31226 mitigation
def validate_cake(self, expected: dict) -> bool:
    """Read back CAKE params and verify they match expectations.

    Args:
        expected: Dict of expected values, e.g.:
            {"diffserv": "diffserv4", "overhead": 18, "bandwidth": 500000000}

    Returns:
        True if all expected params match, False on mismatch or error.
    """
    rc, out, err = self._run_tc(
        ["-j", "qdisc", "show", "dev", self.interface],
        timeout=self.tc_timeout,
    )
    if rc != 0:
        self.logger.error(f"Validate: tc qdisc show failed: {err}")
        return False

    try:
        data = json.loads(out)
        for entry in data:
            if isinstance(entry, dict) and entry.get("kind") == "cake":
                options = entry.get("options", {})
                for key, expected_value in expected.items():
                    actual = options.get(key)
                    if actual != expected_value:
                        self.logger.error(
                            f"CAKE param mismatch on {self.interface}: "
                            f"{key}={actual!r}, expected {expected_value!r}"
                        )
                        return False
                self.logger.info(f"CAKE params validated on {self.interface}")
                return True
        self.logger.error(f"No CAKE qdisc found on {self.interface}")
        return False
    except json.JSONDecodeError as e:
        self.logger.error(f"Failed to parse tc output for validation: {e}")
        return False
```

## tc JSON Schema Reference (Verified from iproute2 Source)

### Top-Level Generic Qdisc Fields
```
bytes: int         -- total bytes processed
packets: int       -- total packets processed
drops: int         -- total drops (NOTE: "drops" not "dropped")
overlimits: int    -- total overlimit events
requeues: int      -- total requeues
backlog: int       -- current queue depth in bytes (maps to queued_bytes)
qlen: int          -- current queue depth in packets (maps to queued_packets)
```

### Options Section (from tc -j qdisc show, no -s needed)
```
bandwidth: int     -- configured rate in bps (NUMERIC in JSON, not string)
autorate: bool     -- autorate-ingress enabled
diffserv: str      -- "diffserv3"|"diffserv4"|"diffserv8"|"besteffort"|"precedence"
flowmode: str      -- "triple-isolate"|"dual-srchost"|"dual-dsthost"|etc.
nat: bool          -- NAT mode
wash: bool         -- DSCP wash mode
ingress: bool      -- ingress accounting mode
ack-filter: str    -- "ack-filter"|"ack-filter-aggressive"|"no-ack-filter" (NOTE: hyphenated key)
split_gso: bool    -- GSO splitting (NOTE: underscore key)
rtt: int           -- configured RTT in microseconds (NUMERIC)
raw: bool          -- raw mode
atm: str           -- "atm"|"ptm"|"noatm"
overhead: int      -- overhead bytes (-64 to 256)
mpu: int           -- minimum packet unit (0-256)
memlimit: int      -- memory limit in bytes (NUMERIC in JSON)
fwmark: int        -- firewall mark
```

### CAKE xstats Fields (from tc -j -s qdisc show)
```
memory_used: int        -- current memory consumption bytes
memory_limit: int       -- configured memory limit bytes
capacity_estimate: int  -- CAKE's estimated link capacity bps
min_network_size: int
max_network_size: int
min_adj_size: int
max_adj_size: int
avg_hdr_offset: int
```

### Per-Tin Fields (tins[] array, verified from cake_print_json_tin)
```
threshold_rate: int            -- tin's rate threshold bps
sent_bytes: int                -- cumulative bytes sent
sent_packets: int              -- cumulative packets sent
drops: int                     -- cumulative drops (NOT "dropped_packets")
ecn_mark: int                  -- cumulative ECN marks (NOT "ecn_marked_packets")
ack_drops: int                 -- cumulative ACK drops
backlog_bytes: int             -- current backlog bytes
target_us: int                 -- Cobalt AQM target delay usec
interval_us: int               -- Cobalt AQM interval usec
peak_delay_us: int             -- peak sojourn delay usec
avg_delay_us: int              -- average sojourn delay usec
base_delay_us: int             -- base (minimum) delay usec
way_indirect_hits: int
way_misses: int
way_collisions: int
sparse_flows: int              -- active sparse flows
bulk_flows: int                -- active bulk flows
unresponsive_flows: int        -- active unresponsive flows
max_pkt_len: int               -- max packet length seen
flow_quantum: int              -- per-flow quantum bytes
```

**CRITICAL NOTE ON D-05 vs iproute2:** Decision D-05 specifies consumer-facing field names `dropped_packets` and `ecn_marked_packets`. The actual tc JSON uses `drops` and `ecn_mark`. The parser must MAP: `tin.get("drops") -> "dropped_packets"` and `tin.get("ecn_mark") -> "ecn_marked_packets"` in the returned dict. This preserves the consumer API while correctly reading the tc output.

### Diffserv4 Tin Order
```
Index 0: Bulk       (CS1 / Low Priority)
Index 1: Best Effort (Default)
Index 2: Video      (AF4x/AF3x/CS3/AF2x/CS2)
Index 3: Voice      (CS7/CS6/EF/VA/CS5/CS4)
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Text parsing of `tc -s` output | JSON parsing via `tc -j -s` | iproute2 4.19 (2018) | Eliminates fragile regex. Debian 12 ships 6.1.0. |
| `tc qdisc add` for setup | `tc qdisc replace` for idempotent setup | Always available | `replace` is safe for restarts. systemd issue #31226 proves `add` is unreliable. |
| IFB for ingress shaping | Bridge member port egress | Architecture choice | Bridge topology eliminates need for IFB entirely. |
| pyroute2 for tc control | subprocess + tc CLI | Current recommendation | pyroute2 CAKE control operations unverified. subprocess is proven in wanctl. |

**Deprecated/outdated:**
- `brctl` (bridge-utils): Deprecated. Use `ip link` from iproute2.
- `tc qdisc add` for CAKE setup: Use `replace` for idempotency. `add` fails if qdisc exists.
- Text parsing of tc output: Use `tc -j` JSON mode. Available since iproute2 4.19.

## Open Questions

1. **queue parameter semantics in LinuxCakeBackend**
   - What we know: RouterBackend ABC methods take `queue: str` parameter. RouterOS uses it as queue tree name. LinuxCakeBackend uses interface name instead.
   - What's unclear: Should `queue` param be ignored (interface set at init) or should it serve as the interface name? The `from_config` pattern suggests interface at init.
   - Recommendation: Ignore the `queue` parameter in set_bandwidth/get_bandwidth/get_queue_stats -- the interface is set in `__init__`. Log a debug note if queue != interface for transparency. This matches how the controller currently uses queue names from config.

2. **subprocess.run timeout value**
   - What we know: tc is local ~1-3ms. wanctl runs 50ms cycles.
   - What's unclear: Optimal timeout for the control loop path vs initialization path.
   - Recommendation: Use 5.0s default for control loop (generous but prevents hanging), 10.0s for initialize_cake (first-time setup may be slower). Both are well within cycle budget (tc normally completes in <5ms).

3. **ack-filter key name inconsistency**
   - What we know: The tc JSON key is `"ack-filter"` (hyphenated) while other keys use underscores (e.g., `"split_gso"`).
   - What's unclear: Whether this inconsistency affects `validate_cake()` dict lookups.
   - Recommendation: Use the exact key name from tc JSON (`"ack-filter"`) when validating. Document the inconsistency.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.0.2 |
| Config file | pyproject.toml `[tool.pytest.ini_options]` |
| Quick run command | `.venv/bin/pytest tests/test_linux_cake_backend.py -v` |
| Full suite command | `.venv/bin/pytest tests/ -v` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| BACK-01 | set_bandwidth calls tc qdisc change with correct args, returns True/False | unit | `.venv/bin/pytest tests/test_linux_cake_backend.py::TestSetBandwidth -x` | Wave 0 |
| BACK-01 | set_bandwidth converts bps to kbit correctly | unit | `.venv/bin/pytest tests/test_linux_cake_backend.py::TestSetBandwidth::test_rate_conversion -x` | Wave 0 |
| BACK-02 | get_queue_stats parses JSON with base 5 fields | unit | `.venv/bin/pytest tests/test_linux_cake_backend.py::TestGetQueueStats -x` | Wave 0 |
| BACK-02 | get_queue_stats returns extended fields (memory, capacity) | unit | `.venv/bin/pytest tests/test_linux_cake_backend.py::TestGetQueueStats::test_extended_fields -x` | Wave 0 |
| BACK-03 | validate_cake verifies diffserv, overhead, bandwidth match | unit | `.venv/bin/pytest tests/test_linux_cake_backend.py::TestValidateCake -x` | Wave 0 |
| BACK-03 | validate_cake detects param mismatch | unit | `.venv/bin/pytest tests/test_linux_cake_backend.py::TestValidateCake::test_mismatch -x` | Wave 0 |
| BACK-04 | get_queue_stats parses per-tin array with all 11 fields | unit | `.venv/bin/pytest tests/test_linux_cake_backend.py::TestPerTinStats -x` | Wave 0 |
| BACK-04 | per-tin field name mapping (drops->dropped_packets) | unit | `.venv/bin/pytest tests/test_linux_cake_backend.py::TestPerTinStats::test_field_mapping -x` | Wave 0 |

### Additional Test Coverage
| Behavior | Test Type | Command |
|----------|-----------|---------|
| initialize_cake calls tc qdisc replace | unit | `.venv/bin/pytest tests/test_linux_cake_backend.py::TestInitializeCake -x` |
| test_connection checks tc binary + CAKE presence | unit | `.venv/bin/pytest tests/test_linux_cake_backend.py::TestTestConnection -x` |
| get_bandwidth parses numeric bps from JSON | unit | `.venv/bin/pytest tests/test_linux_cake_backend.py::TestGetBandwidth -x` |
| no-op stubs return correct values | unit | `.venv/bin/pytest tests/test_linux_cake_backend.py::TestNoOpStubs -x` |
| subprocess timeout handling | unit | `.venv/bin/pytest tests/test_linux_cake_backend.py::TestErrorHandling -x` |
| from_config classmethod | unit | `.venv/bin/pytest tests/test_linux_cake_backend.py::TestFromConfig -x` |

### Sampling Rate
- **Per task commit:** `.venv/bin/pytest tests/test_linux_cake_backend.py -v`
- **Per wave merge:** `.venv/bin/pytest tests/ -v`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_linux_cake_backend.py` -- covers BACK-01, BACK-02, BACK-03, BACK-04
- No framework install needed (pytest 9.0.2 already configured)
- No conftest changes needed (existing conftest.py is sufficient, tests use local fixtures like test_backends.py does)

## Test Design Notes

Tests should follow `test_backends.py` patterns exactly:
- `@unittest.mock.patch` on `subprocess.run` (not on tc itself)
- Fixtures return mock subprocess.CompletedProcess with `.returncode`, `.stdout`, `.stderr`
- Test classes mirror the API: TestSetBandwidth, TestGetBandwidth, TestGetQueueStats, TestInitializeCake, TestValidateCake, TestTestConnection, TestNoOpStubs, TestErrorHandling
- Use realistic tc JSON output strings as test data (copy from the schema reference above)
- Test both success and failure paths for every method
- Test the field name mapping explicitly (tc's `drops` -> consumer's `dropped_packets`)

Sample fixture pattern:
```python
@pytest.fixture
def mock_subprocess():
    """Patch subprocess.run for tc command mocking."""
    with patch("wanctl.backends.linux_cake.subprocess") as mock_sp:
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = ""
        mock_result.stderr = ""
        mock_sp.run.return_value = mock_result
        yield mock_sp

@pytest.fixture
def backend():
    """Create LinuxCakeBackend for testing."""
    return LinuxCakeBackend(interface="eth0")
```

## Sources

### Primary (HIGH confidence)
- iproute2 source `q_cake.c` (cake_print_json_tin, cake_print_opt, cake_print_xstats) -- exact JSON field names
- iproute2 source `json_print.c` (print_color_rate) -- bandwidth is numeric bps in JSON mode
- `src/wanctl/backends/base.py` -- RouterBackend ABC method signatures and contracts
- `src/wanctl/backends/routeros.py` -- Reference implementation patterns
- `src/wanctl/router_command_utils.py` -- CommandResult type, check_command_success, extract_queue_stats
- `src/wanctl/irtt_measurement.py` -- subprocess.run pattern with timeout handling
- `tests/test_backends.py` -- Test structure and fixture patterns

### Secondary (MEDIUM confidence)
- `.planning/research/OPENSOURCE-CAKE.md` -- tc command patterns, CAKE parameter recommendations, ecosystem patterns
- `.planning/research/STACK.md` -- tc command reference (NOTE: JSON examples have incorrect bandwidth format)
- `.planning/research/FEATURES.md` -- Feature mapping, anti-patterns, dependency graph
- [tc-cake(8) man page](https://man7.org/linux/man-pages/man8/tc-cake.8.html) -- CAKE parameter documentation
- [systemd issue #31226](https://github.com/systemd/systemd/issues/31226) -- systemd-networkd CAKE race condition

### Tertiary (LOW confidence)
- Per-tin field name discrepancy between CONTEXT.md D-05 and iproute2 source -- needs explicit mapping in code

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- subprocess + json stdlib, zero deps, proven wanctl patterns
- Architecture: HIGH -- clear ABC to implement, reference implementation exists, JSON schema verified from source
- Pitfalls: HIGH -- critical field name discrepancies discovered and documented with mitigations
- Test design: HIGH -- follows exact existing test_backends.py patterns

**Research date:** 2026-03-24
**Valid until:** 2026-04-24 (stable kernel/iproute2 interface, unlikely to change)
