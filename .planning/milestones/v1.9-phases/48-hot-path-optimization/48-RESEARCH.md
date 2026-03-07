# Phase 48: Hot Path Optimization - Research

**Researched:** 2026-03-06
**Domain:** RTT measurement optimization (subprocess ping -> raw ICMP sockets)
**Confidence:** HIGH

## Summary

Phase 48 replaces `subprocess.run(["ping", ...])` in `rtt_measurement.py` with the `icmplib` library for direct ICMP socket communication. Profiling data (Phase 47) shows 97-98% of cycle time is irreducible network RTT, with subprocess fork/exec/pipe/parse overhead contributing ~2-5ms per cycle. Eliminating this overhead is the single actionable optimization.

The `icmplib` library (v3.0.4, LGPLv3, pure Python) provides a `ping()` function that creates a raw ICMP socket, sends/receives packets directly, and returns a `Host` object with RTT data as floats. Each `ping()` call creates its own socket via context manager, shares no mutable state between calls, and uses a thread-safe `unique_identifier()` function with a lock -- making it safe for use with the existing `ThreadPoolExecutor` concurrency pattern.

**Primary recommendation:** Replace `subprocess.run(["ping", ...])` with `icmplib.ping()` in `RTTMeasurement.ping_host()`. Keep `ThreadPoolExecutor` for concurrent pings. Do NOT use `icmplib.multiping()` (it calls `asyncio.run()` internally, adding complexity for no benefit with 1-3 hosts). Preserve `parse_ping_output()` for `calibrate.py` backward compatibility.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- D1: Replace subprocess ping with icmplib library for raw ICMP sockets
- D2: Keep current reflector configuration unchanged (median-of-three for Spectrum, single for ATT)
- D3: Revised success criteria (3ms avg reduction, not 50% reduction; P99 <= 55ms Spectrum, <= 33ms ATT)
- D4: Revised utilization target (~55-65%, not ~40%)
- D5: OPTM-02/03/04 satisfied by profiling evidence or measurement, no code changes needed
- D6: State management P99 deferred

### Claude's Discretion
- Implementation details of icmplib integration (parameter choices, error mapping, test structure)

### Deferred Ideas (OUT OF SCOPE)
- State management P99 optimization
- CAKE stats optimization
- Async I/O rewrite
- 25ms cycle interval exploration
- Steering daemon interval change (2s -> 50ms)
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| OPTM-01 | RTT measurement hot path optimized to reduce cycle time contribution | icmplib.ping() eliminates subprocess fork/exec/pipe/parse overhead (~2-5ms). Direct socket I/O returns RTT as float. |
| OPTM-02 | Router communication path optimized | Satisfied by profiling evidence: 0.0-0.2ms avg. No code change needed. Document finding. |
| OPTM-03 | CAKE stats collection optimized if significant contributor | Not applicable: CAKE stats only in steering daemon at 2s intervals. Document finding. |
| OPTM-04 | MikroTik router CPU impact reduced from 45% peak | Redefined as measurement task: measure before/after icmplib change. Target <= 40%. |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| icmplib | 3.0.4 | Raw ICMP socket ping | Pure Python, MIT-compatible (LGPLv3), well-maintained, no C extensions, returns RTT as float |

### Supporting (Already in Project)
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| concurrent.futures | stdlib | ThreadPoolExecutor for parallel pings | Already used in ping_hosts_concurrent() |
| statistics | stdlib | Median/mean aggregation | Already used for RTT aggregation |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| icmplib.ping() | icmplib.multiping() | multiping uses asyncio.run() internally -- unnecessary complexity for 1-3 hosts, and cannot be called from within an existing event loop |
| ThreadPoolExecutor + ping() | multiping() | multiping manages its own concurrency but adds asyncio overhead; keeping ThreadPoolExecutor preserves existing tested pattern |
| icmplib | fping subprocess | fping requires lifecycle management, fragile output parsing -- same problem we're solving |

**Installation:**
```bash
uv add icmplib
# Or in pyproject.toml: "icmplib>=3.0.4"
```

## Architecture Patterns

### Recommended Change Structure
```
src/wanctl/rtt_measurement.py   # Modify: ping_host() uses icmplib.ping() instead of subprocess
                                 # Modify: remove subprocess import from hot path
                                 # Keep: parse_ping_output() for calibrate.py backward compat
                                 # Keep: _aggregate_rtts(), RTTAggregationStrategy unchanged
                                 # Keep: ping_hosts_concurrent() structure (ThreadPoolExecutor)
tests/test_rtt_measurement.py    # Modify: mock icmplib.ping instead of subprocess.run
                                 # Keep: all test class structure and assertions
pyproject.toml                   # Add: icmplib>=3.0.4 to dependencies
```

### Pattern 1: icmplib.ping() as Drop-In Replacement

**What:** Replace subprocess ping with icmplib.ping() in ping_host()
**When to use:** Every call to ping_host() (the RTT measurement hot path)
**Example:**
```python
# Source: icmplib official docs (https://github.com/ValentinBELYN/icmplib)
import icmplib

def ping_host(self, host: str, count: int = 1) -> float | None:
    try:
        result = icmplib.ping(
            address=host,
            count=count,
            interval=0,      # No delay between packets (hot path)
            timeout=self.timeout_ping,  # Per-packet timeout in seconds
            privileged=True,  # Use raw sockets (CAP_NET_RAW granted)
        )

        if not result.is_alive:
            self.logger.warning(f"Ping to {host} failed (no response)")
            return None

        if not result.rtts:
            self.logger.warning(f"No RTT samples from {host}")
            return None

        # Aggregate using existing strategy
        aggregated_rtt = self._aggregate_rtts(result.rtts)
        return aggregated_rtt

    except icmplib.NameLookupError:
        self.logger.warning(f"DNS lookup failed for {host}")
        return None
    except icmplib.SocketPermissionError:
        self.logger.error(f"Insufficient privileges for ICMP (need CAP_NET_RAW)")
        return None
    except icmplib.ICMPLibError as e:
        self.logger.error(f"Ping error to {host}: {e}")
        return None
    except Exception as e:
        self.logger.error(f"Ping error to {host}: {e}")
        return None
```

### Pattern 2: Error Mapping (subprocess -> icmplib)

**What:** Map subprocess error conditions to icmplib equivalents
**When to use:** Error handling in ping_host()

| Old (subprocess) | New (icmplib) | Behavior |
|-------------------|---------------|----------|
| `subprocess.TimeoutExpired` | `timeout` param + `result.is_alive == False` | Return None, log warning |
| `returncode != 0` | `result.is_alive == False` or `result.packet_loss == 1.0` | Return None, log warning |
| `OSError` (network unreachable) | `icmplib.ICMPSocketError` | Return None, log error |
| Parse failure (no RTT in output) | `result.rtts == []` | Return None, log warning |
| N/A (new) | `icmplib.SocketPermissionError` | Return None, log error (CAP_NET_RAW missing) |
| N/A (new) | `icmplib.NameLookupError` | Return None, log warning |

### Pattern 3: Host Object Property Access

**What:** icmplib.ping() returns a Host object, not raw text
**When to use:** Extracting RTT values after ping

```python
# Source: icmplib official docs
# Host object properties:
#   .address: str          - responding IP
#   .min_rtt: float        - minimum RTT in ms
#   .avg_rtt: float        - average RTT in ms
#   .max_rtt: float        - maximum RTT in ms
#   .rtts: list[float]     - all individual RTTs in ms (unrounded)
#   .packets_sent: int     - number of requests sent
#   .packets_received: int - number of responses received
#   .packet_loss: float    - 0.0 to 1.0
#   .jitter: float         - RTT variance in ms
#   .is_alive: bool        - True if any response received

# For single ping (count=1):
result = icmplib.ping(host, count=1, timeout=1)
if result.is_alive and result.rtts:
    rtt_ms = result.rtts[0]  # Single RTT value
```

### Anti-Patterns to Avoid
- **Using multiping() for 1-3 hosts:** Overkill. It calls asyncio.run() internally, which adds an event loop setup/teardown. Use ping() with ThreadPoolExecutor as already implemented.
- **Setting privileged=False:** This uses SOCK_DGRAM (unprivileged sockets). On Linux, the kernel replaces ICMP packet IDs with port numbers, making concurrent correlation unreliable. Use privileged=True (CAP_NET_RAW is already granted).
- **Removing parse_ping_output():** calibrate.py still uses it for subprocess ping output. Keep it in the module but it exits the hot path.
- **Catching bare Exception without icmplib-specific catches first:** icmplib raises specific exceptions (NameLookupError, SocketPermissionError, etc.) that should be caught for proper logging before the generic fallback.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| ICMP packet construction | Raw socket + struct.pack | icmplib.ping() | ICMP sequence numbering, ID management, checksum calculation, IPv4/v6 detection, timeout handling |
| Concurrent ICMP timing | Manual select/poll loop | ThreadPoolExecutor + icmplib.ping() | Each ping() creates its own socket, thread-safe by design |
| RTT extraction from responses | Manual reply parsing | Host.rtts property | icmplib handles all reply matching, sequence tracking, loss detection |
| Privilege detection | os.geteuid() checks | icmplib.SocketPermissionError | icmplib tries raw socket, raises clear error if CAP_NET_RAW missing |

**Key insight:** The subprocess approach required 4 separate concerns (fork process, construct ping CLI args, capture stdout, parse text output). icmplib collapses all 4 into a single function call returning structured data.

## Common Pitfalls

### Pitfall 1: CAP_NET_RAW in Docker Containers
**What goes wrong:** icmplib raises SocketPermissionError because container lacks raw socket capability
**Why it happens:** Docker containers default to a restricted capability set. The current Dockerfile runs as non-root user `wanctl`.
**How to avoid:** The systemd service files already grant `AmbientCapabilities=CAP_NET_RAW`. For Docker, add `cap_add: [NET_RAW]` to docker-compose.yml services. The docker-compose.yml currently uses `network_mode: host` which inherits host capabilities.
**Warning signs:** `SocketPermissionError` in logs at startup

### Pitfall 2: icmplib.ping() interval Parameter
**What goes wrong:** Using default interval=1 adds 1-second delays between packets in multi-count pings
**Why it happens:** icmplib defaults to `interval=1` (1 second between packets), mimicking standard ping behavior
**How to avoid:** Set `interval=0` for count=1 (no delay needed) or a very small value for count>1. Since wanctl uses count=1 for hot path, this is not an issue for the primary use case but important to set correctly.
**Warning signs:** Cycle time increases after migration

### Pitfall 3: icmplib Timeout vs subprocess Timeout
**What goes wrong:** Confusing icmplib's `timeout` (per-packet wait) with subprocess `timeout` (total process timeout)
**Why it happens:** Different semantics: icmplib `timeout=2` means "wait up to 2s for each reply." Subprocess timeout was total wall-clock for the entire process.
**How to avoid:** For count=1, icmplib `timeout` equals the old subprocess timeout_ping. For count>1, total time is approximately `count * (timeout + interval)`. The `timeout_total` parameter on RTTMeasurement should be mapped to appropriate icmplib timeout values.
**Warning signs:** Timeouts happening faster or slower than expected

### Pitfall 4: Host.rtts Empty vs Host.is_alive
**What goes wrong:** Assuming is_alive implies rtts has data
**Why it happens:** Edge case: is_alive can be False with rtts=[] (all packets lost), but also is_alive can be True with partial packet loss
**How to avoid:** Always check `result.rtts` before accessing elements, not just `result.is_alive`. Check both conditions.
**Warning signs:** IndexError on `result.rtts[0]`

### Pitfall 5: Test Mocking Strategy
**What goes wrong:** Tests mock subprocess.run but after migration, that mock has no effect
**Why it happens:** Tests need to mock `icmplib.ping` instead of `subprocess.run`
**How to avoid:** Mock at `wanctl.rtt_measurement.icmplib.ping` or create a lightweight Host-like mock object. icmplib.Host can be constructed directly for test fixtures.
**Warning signs:** Tests pass but don't actually test the new code path

### Pitfall 6: DNS Resolution in icmplib
**What goes wrong:** icmplib resolves hostnames to IPs internally; wanctl passes IPs, but config could contain hostnames
**Why it happens:** icmplib calls `resolve()` if given a hostname, which adds DNS lookup time
**How to avoid:** wanctl already uses IP addresses in ping_hosts config. Verify configs don't use hostnames. If they do, icmplib handles it but with added latency.
**Warning signs:** Sporadic DNS lookup latency in cycle times

## Code Examples

Verified patterns from official sources:

### Creating Host Mock Objects for Tests
```python
# Source: icmplib API analysis
from unittest.mock import MagicMock, patch

def make_host_result(address="8.8.8.8", rtts=None, is_alive=True):
    """Create a mock icmplib Host result for testing."""
    host = MagicMock()
    host.address = address
    host.rtts = rtts or [12.3]
    host.min_rtt = min(host.rtts) if host.rtts else 0.0
    host.avg_rtt = sum(host.rtts) / len(host.rtts) if host.rtts else 0.0
    host.max_rtt = max(host.rtts) if host.rtts else 0.0
    host.packets_sent = len(host.rtts) if is_alive else 1
    host.packets_received = len(host.rtts) if is_alive else 0
    host.packet_loss = 0.0 if is_alive else 1.0
    host.is_alive = is_alive
    host.jitter = 0.0
    return host

# Usage in test:
@patch("wanctl.rtt_measurement.icmplib.ping")
def test_ping_host_success(self, mock_ping):
    mock_ping.return_value = make_host_result(rtts=[12.3])
    result = self.rtt_measurement.ping_host("8.8.8.8", count=1)
    assert result == pytest.approx(12.3)
```

### Exception Handling Pattern
```python
# Source: icmplib exception hierarchy (verified from source)
import icmplib

try:
    result = icmplib.ping(host, count=1, timeout=1, privileged=True)
except icmplib.NameLookupError:
    # DNS resolution failed -- host is a hostname that can't resolve
    pass
except icmplib.SocketPermissionError:
    # CAP_NET_RAW not granted -- critical deployment issue
    pass
except icmplib.ICMPSocketError as e:
    # Socket-level errors (address assignment, unavailable, broadcast)
    pass
except icmplib.ICMPLibError as e:
    # Base exception for all icmplib errors
    pass
```

### icmplib.ping() Parameters for wanctl Hot Path
```python
# Source: icmplib official docs + wanctl requirements
icmplib.ping(
    address="8.8.8.8",    # IP address (avoid hostnames for speed)
    count=1,               # Single packet per cycle (wanctl default)
    interval=0,            # No delay between packets (irrelevant for count=1)
    timeout=1,             # Match existing timeout_ping config value
    privileged=True,       # Use raw sockets (CAP_NET_RAW required)
)
# Returns: Host object with .rtts = [12.3], .is_alive = True
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| subprocess.run(["ping", ...]) | icmplib.ping() raw sockets | icmplib 1.0 (2017), mature by 3.0.4 (2024) | Eliminates fork/exec/pipe/parse per cycle |
| Parse "time=X" from stdout | Host.rtts list of floats | icmplib 2.0 (2020) | No text parsing, structured data |
| icmplib threading (v2.x) | icmplib asyncio (v3.x) | 3.0.0 (Jun 2023) | multiping() uses asyncio internally; sync ping() still uses per-call sockets |

**Deprecated/outdated:**
- `parse_ping_output()`: No longer needed for hot path. Retained only for `calibrate.py` backward compatibility.
- `subprocess` import: Can be removed from `rtt_measurement.py` after migration (calibrate.py has its own import).
- `_RTT_PATTERN` regex: No longer used in hot path. Keep only if parse_ping_output() is kept.

## Open Questions

1. **Docker Capability Verification**
   - What we know: systemd services grant CAP_NET_RAW via AmbientCapabilities. docker-compose uses network_mode: host.
   - What's unclear: Whether network_mode: host + non-root USER in Dockerfile is sufficient for raw sockets, or if explicit cap_add is needed.
   - Recommendation: Test in development Docker environment. If SocketPermissionError occurs, add `cap_add: [NET_RAW]` to docker-compose.yml.

2. **Bandit Security Scanner**
   - What we know: Current code has `# nosec B404` and `# nosec B603` comments for subprocess usage.
   - What's unclear: Whether bandit flags icmplib socket usage.
   - Recommendation: Run bandit after migration. icmplib uses raw sockets (not subprocess), so B404/B603 won't apply. Remove those nosec comments. Check if any new bandit rules trigger.

3. **Production Baseline Collection**
   - What we know: Phase 47 collected 1-hour baseline. CONTEXT.md verification approach requires before/after comparison.
   - What's unclear: Whether prior Phase 47 data is recent enough or if a fresh baseline is needed.
   - Recommendation: Use Phase 47 data as "before" if collected within the same week. Otherwise collect fresh baseline before implementing changes.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.0+ with pytest-cov |
| Config file | pyproject.toml [tool.pytest.ini_options] |
| Quick run command | `.venv/bin/pytest tests/test_rtt_measurement.py -v` |
| Full suite command | `.venv/bin/pytest tests/ -v` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| OPTM-01 | ping_host() uses icmplib instead of subprocess | unit | `.venv/bin/pytest tests/test_rtt_measurement.py -x` | Needs update (mock target changes) |
| OPTM-01 | ping_host() returns correct RTT from icmplib Host object | unit | `.venv/bin/pytest tests/test_rtt_measurement.py::TestPingHostEdgeCases -x` | Needs update |
| OPTM-01 | ping_hosts_concurrent() works with icmplib-based ping_host() | unit | `.venv/bin/pytest tests/test_rtt_measurement.py::TestPingHostsConcurrent -x` | Needs update |
| OPTM-01 | icmplib exceptions mapped to correct return values (None) | unit | `.venv/bin/pytest tests/test_rtt_measurement.py -x -k "error or exception or timeout"` | Needs new tests |
| OPTM-01 | SocketPermissionError logged at ERROR level | unit | `.venv/bin/pytest tests/test_rtt_measurement.py -x -k "permission"` | Needs new test |
| OPTM-01 | No subprocess import in RTT hot path | unit | `.venv/bin/pytest tests/test_rtt_measurement.py -x -k "no_subprocess"` | Needs new test |
| OPTM-02 | Router communication already near-zero (profiling evidence) | manual-only | N/A - document finding in phase summary | N/A |
| OPTM-03 | CAKE stats not applicable at current intervals | manual-only | N/A - document finding in phase summary | N/A |
| OPTM-04 | Router CPU measured before/after | manual-only | Production measurement via router monitoring | N/A |

### Sampling Rate
- **Per task commit:** `.venv/bin/pytest tests/test_rtt_measurement.py -v`
- **Per wave merge:** `.venv/bin/pytest tests/ -v`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] Update mock targets in all test classes (subprocess.run -> icmplib.ping)
- [ ] New test: SocketPermissionError handling
- [ ] New test: NameLookupError handling
- [ ] New test: verify no subprocess import leak to hot path
- [ ] Install icmplib in dev venv: `uv add icmplib`

## Sources

### Primary (HIGH confidence)
- [icmplib PyPI](https://pypi.org/project/icmplib/) - Version 3.0.4, Python >=3.7, LGPLv3 license
- [icmplib GitHub README](https://github.com/ValentinBELYN/icmplib/blob/main/README.md) - Full ping() API, Host class properties, exception hierarchy
- [icmplib ping.py source](https://github.com/ValentinBELYN/icmplib/blob/main/icmplib/ping.py) - Confirmed: one socket per ping() call via context manager
- [icmplib utils.py source](https://raw.githubusercontent.com/ValentinBELYN/icmplib/main/icmplib/utils.py) - unique_identifier() is thread-safe (uses Lock)
- [icmplib exceptions.py source](https://github.com/ValentinBELYN/icmplib/blob/main/icmplib/exceptions.py) - Full exception hierarchy verified
- [icmplib releases](https://github.com/ValentinBELYN/icmplib/releases) - v3.0.4 released Oct 2024, latest stable
- [icmplib sockets docs](https://github.com/ValentinBELYN/icmplib/blob/main/docs/3-sockets.md) - Socket lifecycle details
- [icmplib issue #6](https://github.com/ValentinBELYN/icmplib/issues/6) - privileged=False uses SOCK_DGRAM, kernel replaces IDs

### Secondary (MEDIUM confidence)
- [icmplib multiping source](https://raw.githubusercontent.com/ValentinBELYN/icmplib/main/icmplib/multiping.py) - multiping() uses asyncio.run() internally (confirmed via WebFetch)
- wanctl systemd service files - AmbientCapabilities=CAP_NET_RAW already configured (local file verification)
- wanctl Dockerfile - Runs as non-root `wanctl` user, uses network_mode: host (local file verification)

### Tertiary (LOW confidence)
- Thread safety of ping() across ThreadPoolExecutor - No explicit thread safety documentation from icmplib. Inferred safe from: each call creates own socket, unique_identifier() uses Lock, no shared mutable state. Should be validated with a simple multi-thread test.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - icmplib is well-documented, v3.0.4 is stable, API verified from source
- Architecture: HIGH - Change is surgical (one file, one function), API boundary preserved, callers unchanged
- Pitfalls: HIGH - Privilege requirements verified against existing systemd/Docker configs, timeout semantics verified from source
- Thread safety: MEDIUM - Inferred from source code analysis (each ping() creates own socket, unique_identifier uses Lock), but no explicit thread safety guarantee in docs

**Research date:** 2026-03-06
**Valid until:** 2026-04-06 (stable library, unlikely to change)
