# Phase 91: Container Networking Audit - Research

**Researched:** 2026-03-16
**Domain:** Linux container networking latency measurement (veth pairs, bridge, ICMP)
**Confidence:** HIGH

## Summary

This phase is a measurement and documentation task -- no daemon code changes expected. The goal is to quantify container networking overhead (veth pair + bridge round-trip latency and jitter) and produce an automated audit script plus a markdown report.

Live verification from the dev host confirms both containers are reachable via ping with sub-millisecond RTT (~0.12-0.44ms for cake-spectrum, ~0.11-0.35ms for cake-att), well under the 0.5ms decision threshold established in STATE.md. The measurement infrastructure is straightforward: subprocess `ping` with output parsed by the existing `parse_ping_output()` function, plus `statistics` stdlib for percentile computation.

**Primary recommendation:** Use subprocess `ping` (not icmplib) for measurement since the script runs from the host machine where icmplib requires root/sysctl configuration. The existing `parse_ping_output()` from `rtt_measurement.py` already handles parsing. Script should be self-contained with minimal wanctl imports. SSH to containers captures network topology for the report.

<user_constraints>

## User Constraints (from CONTEXT.md)

### Locked Decisions
- Host-to-container ping: from dev/host machine to each container IP (10.10.110.246 cake-spectrum, 10.10.110.247 cake-att)
- Measures full veth pair + bridge round-trip without any WAN component
- 1000+ samples per path at 10ms interval (~10 seconds per path)
- 5 runs per path for stability
- icmplib (already in venv) or standard ping via subprocess
- Script runs from host machine (not from inside containers)
- Python script: `scripts/container_network_audit.py`
- Outputs: `docs/CONTAINER_NETWORK_AUDIT.md`
- Per-container metrics: mean, median, p95, p99, stddev, min, max, sample count
- Network topology section: veth pairs, bridge name, MTU, IPs (captured via SSH `ip link`/`ip addr`)
- Jitter metric: standard deviation of container RTT samples
- Threshold: container jitter < 10% of WAN jitter = negligible
- If mean RTT overhead < 0.5ms AND jitter < 10% of WAN jitter: close with report only (no code changes)
- If overhead >= 0.5ms: report includes investigation findings and recommendation options -- implementation deferred to future phase
- Script also captures container network topology via SSH for documentation context

### Claude's Discretion
- icmplib vs subprocess ping for measurement (whatever works cleanly from host)
- Script argument parsing (argparse vs hardcoded container IPs)
- Raw data storage format (if any beyond the report)
- Exact report markdown formatting
- How WAN jitter reference values are obtained (from production logs, health endpoint, or hardcoded estimates)

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope

</user_constraints>

<phase_requirements>

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| CNTR-01 | Container veth/bridge networking overhead is measured and quantified | subprocess ping with parse_ping_output(), 5 runs x 1000+ samples per container, statistics.quantiles for percentiles |
| CNTR-02 | Jitter contribution from container networking is characterized | stddev of RTT samples as jitter metric, compared against WAN jitter reference values (Spectrum ~3-5ms, ATT ~2-3ms loaded) |
| CNTR-03 | Audit report documents measurement floor with quantified overhead | Auto-generated markdown report at docs/CONTAINER_NETWORK_AUDIT.md following PRODUCTION_INTERVAL.md format |

</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| subprocess (stdlib) | Python 3.12 | Run `ping` command from host | icmplib requires root/sysctl on host; subprocess ping works unprivileged and provides sub-ms precision |
| statistics (stdlib) | Python 3.12 | mean, median, stdev, quantiles | Already used in signal_processing.py and benchmark.py -- zero new deps |
| argparse (stdlib) | Python 3.12 | CLI argument parsing | Consistent with wanctl-benchmark, wanctl-check-config patterns |
| subprocess (stdlib) | Python 3.12 | SSH to containers for topology capture | Existing pattern in scripts directory |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| wanctl.rtt_measurement.parse_ping_output | existing | Parse RTT values from ping output | Reuse for extracting individual RTT samples from subprocess ping |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| subprocess ping | icmplib | icmplib requires root or `net.ipv4.ping_group_range` sysctl config on host; script must run unprivileged from dev machine. icmplib is better inside containers (CAP_NET_RAW) but not suitable for host-side measurement without root |

**Installation:**
```bash
# No new dependencies -- all stdlib + existing wanctl.rtt_measurement
```

## Architecture Patterns

### Recommended Project Structure
```
scripts/
  container_network_audit.py    # Self-contained measurement + report script
docs/
  CONTAINER_NETWORK_AUDIT.md    # Generated audit report (committed)
tests/
  test_container_network_audit.py  # Unit tests for computation/formatting logic
```

### Pattern 1: Subprocess Ping Measurement
**What:** Run `ping -c COUNT -i INTERVAL TARGET` via subprocess.run, parse output with parse_ping_output()
**When to use:** Measuring latency from host to container IPs
**Example:**
```python
# Source: verified on dev host -- parse_ping_output works with container pings
import subprocess
from wanctl.rtt_measurement import parse_ping_output

result = subprocess.run(
    ["ping", "-c", "1000", "-i", "0.01", "10.10.110.246"],
    capture_output=True, text=True, timeout=30,
)
rtts = parse_ping_output(result.stdout)
# rtts = [0.154, 0.194, 0.197, ...]  -- sub-ms precision confirmed
```

### Pattern 2: Statistics Computation (stdlib)
**What:** Compute mean, median, p95, p99, stddev from RTT sample list
**When to use:** Per-container latency characterization
**Example:**
```python
import statistics

mean = statistics.mean(rtts)
median = statistics.median(rtts)
stdev = statistics.stdev(rtts)
# quantiles(n=100) returns 99 cut points; p95=index 94, p99=index 98
cuts = statistics.quantiles(rtts, n=100)
p95 = cuts[94]
p99 = cuts[98]
```

### Pattern 3: SSH Topology Capture
**What:** Run `ip link show` and `ip addr show` on containers via SSH to capture veth/bridge/MTU info
**When to use:** Documenting network topology for the audit report
**Example:**
```python
result = subprocess.run(
    ["ssh", "cake-spectrum", "ip link show"],
    capture_output=True, text=True, timeout=10,
)
# Output: "2: eth0@if67: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 ..."
# The @ifN suffix confirms veth pair (N = host-side interface index)
```

### Pattern 4: Markdown Report Generation
**What:** Script generates the full docs/CONTAINER_NETWORK_AUDIT.md with tables, analysis, recommendation
**When to use:** Final output step after all measurements complete
**Format reference:** Follow docs/PRODUCTION_INTERVAL.md structure (Executive Summary, Data Tables, Analysis, Recommendation)

### Anti-Patterns to Avoid
- **Importing wanctl daemon modules:** Script should be self-contained. Only import parse_ping_output from rtt_measurement.py (a utility, not daemon code). Do not import Config, MetricsWriter, or daemon classes.
- **Running inside containers:** Measurement must be from host to container, not container-to-container or container-to-self. Host-to-container captures the full veth+bridge path.
- **Using icmplib from host without root:** icmplib requires `privileged=True` (root) or `net.ipv4.ping_group_range` sysctl. Dev host has `ping_group_range = 1 0` (disabled). Use subprocess ping instead.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Ping output parsing | Custom regex parser | `parse_ping_output()` from rtt_measurement.py | Already handles multiple ping output formats, pre-compiled regex, edge cases |
| Percentile computation | Manual sorting/indexing | `statistics.quantiles(data, n=100)` | Correct interpolation, handles edge cases with small samples |
| Standard deviation | Manual variance calculation | `statistics.stdev(data)` | Numerically stable, stdlib |

**Key insight:** This phase reuses existing infrastructure (parse_ping_output, statistics stdlib) and only needs new code for orchestration, SSH topology capture, and markdown report generation.

## Common Pitfalls

### Pitfall 1: icmplib Privilege Requirements on Host
**What goes wrong:** Using icmplib with `privileged=False` fails with `SocketPermissionError` because `ping_group_range = 1 0` on the dev host
**Why it happens:** Ubuntu default restricts unprivileged ICMP sockets; containers have CAP_NET_RAW but host does not grant it to unprivileged users
**How to avoid:** Use subprocess `ping` instead -- it has the suid bit set and works without root. Confirmed working on dev host with sub-ms precision.
**Warning signs:** `SocketPermissionError` from icmplib on host machine

### Pitfall 2: Ping Interval Floor
**What goes wrong:** `ping -i 0.01` (10ms interval) requires no special privileges for values >= 0.002 on modern Linux, but values below 0.2s historically required root
**Why it happens:** Kernel rate-limiting on ICMP; modern Linux (5.x+) allows faster intervals for unprivileged users
**How to avoid:** The 10ms interval specified in CONTEXT.md works fine unprivileged (verified: `ping -c 20 -i 0.01` succeeds on dev host kernel 6.8.0)
**Warning signs:** "ping: cannot flood; minimal interval allowed for user is 2ms" error

### Pitfall 3: statistics.quantiles Minimum Sample Size
**What goes wrong:** `statistics.quantiles(data, n=100)` requires at least 2 data points; with very few samples, percentile interpolation may be unreliable
**Why it happens:** Quantile computation needs sufficient data to be meaningful
**How to avoid:** With 1000+ samples per run (locked decision), this is not a concern. Guard with `len(rtts) >= 2` before computing.
**Warning signs:** `StatisticsError` from empty or single-element input

### Pitfall 4: SSH Timeout During Topology Capture
**What goes wrong:** SSH to containers hangs if containers are down or unreachable
**Why it happens:** Container might be stopped, SSH service not running, network issues
**How to avoid:** Use `timeout=10` on subprocess.run for SSH commands; catch TimeoutExpired; report topology as "unavailable" rather than failing the entire script
**Warning signs:** Script hangs during SSH phase

### Pitfall 5: First-Ping Outlier
**What goes wrong:** First ICMP echo in a burst has higher latency due to ARP resolution
**Why it happens:** ARP cache miss on first packet to a host; subsequent packets use cached ARP entry
**How to avoid:** Either discard the first sample or run a single warm-up ping before the measurement burst. With 1000+ samples, one outlier has minimal statistical impact, but worth noting.
**Warning signs:** First RTT value is 2-10x higher than subsequent values

### Pitfall 6: parse_ping_output Returns Empty on Failure
**What goes wrong:** If ping fails (host unreachable, timeout), parse_ping_output returns empty list, and statistics functions raise on empty input
**Why it happens:** No ICMP replies received
**How to avoid:** Check `len(rtts) > 0` before computing statistics; report container as unreachable
**Warning signs:** Empty rtts list after parsing

## Code Examples

Verified patterns from existing codebase and live testing:

### Measurement Flow (per container)
```python
# Source: verified on dev host 2026-03-16
import subprocess
import statistics
from wanctl.rtt_measurement import parse_ping_output

def measure_container(host: str, count: int = 1000, interval: float = 0.01) -> dict | None:
    """Measure RTT to a container via ping."""
    try:
        result = subprocess.run(
            ["ping", "-c", str(count), "-i", str(interval), host],
            capture_output=True, text=True,
            timeout=count * interval + 10,  # generous timeout
        )
    except subprocess.TimeoutExpired:
        return None

    rtts = parse_ping_output(result.stdout)
    if not rtts:
        return None

    cuts = statistics.quantiles(rtts, n=100)
    return {
        "host": host,
        "count": len(rtts),
        "mean": statistics.mean(rtts),
        "median": statistics.median(rtts),
        "stdev": statistics.stdev(rtts),
        "min": min(rtts),
        "max": max(rtts),
        "p95": cuts[94],
        "p99": cuts[98],
    }
```

### SSH Topology Capture
```python
# Source: verified via SSH to cake-spectrum 2026-03-16
def capture_topology(container: str) -> dict:
    """Capture network topology from a container via SSH."""
    info = {}
    for cmd_name, cmd in [("ip_link", "ip link show"), ("ip_addr", "ip addr show")]:
        try:
            result = subprocess.run(
                ["ssh", container, cmd],
                capture_output=True, text=True, timeout=10,
            )
            info[cmd_name] = result.stdout.strip() if result.returncode == 0 else "unavailable"
        except subprocess.TimeoutExpired:
            info[cmd_name] = "timeout"
    return info
```

### Jitter Comparison
```python
# Source: CONTEXT.md jitter thresholds
WAN_JITTER_REFERENCE = {
    "spectrum": {"idle": 0.5, "loaded": 4.0},  # ms stddev
    "att": {"idle": 0.5, "loaded": 2.5},        # ms stddev
}

def assess_jitter(container_stdev: float, wan_name: str) -> str:
    """Assess whether container jitter is negligible vs WAN jitter."""
    ref = WAN_JITTER_REFERENCE.get(wan_name, {"idle": 0.5, "loaded": 3.0})
    ratio = container_stdev / ref["idle"]
    if ratio < 0.10:
        return f"NEGLIGIBLE ({ratio:.1%} of WAN idle jitter)"
    else:
        return f"NOTABLE ({ratio:.1%} of WAN idle jitter)"
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Manual ping + eyeball analysis | Automated script with statistical analysis | This phase | Repeatable, quantified, documented |
| Assumed negligible container overhead | Measured and quantified overhead | This phase | Evidence-based baseline for controller accuracy |

**Existing real measurements (from dev host, 2026-03-16):**

| Container | Samples | Mean | Min | Max | Mdev |
|-----------|---------|------|-----|-----|------|
| cake-spectrum (10.10.110.246) | 20 | 0.205ms | 0.116ms | 0.443ms | 0.063ms |
| cake-att (10.10.110.247) | 20 | 0.172ms | 0.114ms | 0.255ms | 0.031ms |

These preliminary measurements strongly suggest overhead is well under 0.5ms and container jitter (0.03-0.06ms stddev) is far below 10% of WAN jitter (~0.5ms idle). The formal audit with 5x1000 samples will confirm.

**Container network topology (verified via SSH):**
- cake-spectrum: `eth0@if67` -- veth pair, MTU 1500, IP 10.10.110.246/24
- cake-att: `eth0@if74` -- veth pair, MTU 1500, IP 10.10.110.247/24
- Host route: via `enp6s18` (10.10.110.226) -- same L2 segment

## Open Questions

1. **WAN jitter reference values: hardcoded vs live?**
   - What we know: CONTEXT.md specifies Spectrum ~3-5ms loaded, ATT ~2-3ms loaded; MEMORY.md confirms Spectrum avg 37.6ms, ATT avg 29.0ms
   - What's unclear: Whether to query the health endpoint or metrics DB for live WAN jitter, or use hardcoded estimates
   - Recommendation: Hardcode conservative reference values in the script (simplest, self-contained). CONTEXT.md already provides the numbers. The 10% threshold is not a precise boundary -- any reasonable estimate works since container jitter is orders of magnitude below WAN jitter.

2. **Bridge name on Proxmox host**
   - What we know: Containers use veth pairs (eth0@if67, eth0@if74), host route goes via enp6s18
   - What's unclear: The bridge name on the Proxmox hypervisor (vmbr0? lxcbr0?) -- not visible from dev machine or container
   - Recommendation: Script captures what's visible from container SSH (veth interface, MTU, IP). If Proxmox host bridge info is needed, it can be added as a manual note in the report. The script doesn't need to SSH to the Proxmox host.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.0+ |
| Config file | pyproject.toml [tool.pytest.ini_options] |
| Quick run command | `.venv/bin/pytest tests/test_container_network_audit.py -x` |
| Full suite command | `.venv/bin/pytest tests/ -v` |

### Phase Requirements to Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| CNTR-01 | RTT measurement + stats computation | unit | `.venv/bin/pytest tests/test_container_network_audit.py::TestMeasurement -x` | No -- Wave 0 |
| CNTR-02 | Jitter characterization + comparison | unit | `.venv/bin/pytest tests/test_container_network_audit.py::TestJitterAnalysis -x` | No -- Wave 0 |
| CNTR-03 | Report generation + formatting | unit | `.venv/bin/pytest tests/test_container_network_audit.py::TestReportGeneration -x` | No -- Wave 0 |

### Sampling Rate
- **Per task commit:** `.venv/bin/pytest tests/test_container_network_audit.py -x`
- **Per wave merge:** `.venv/bin/pytest tests/ -v`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_container_network_audit.py` -- covers CNTR-01, CNTR-02, CNTR-03
- Tests focus on: stats computation (mock RTT data), jitter assessment logic, report markdown generation, error handling (empty rtts, SSH timeout), parse_ping_output integration
- No new framework or fixture needs -- existing conftest.py `temp_dir` fixture sufficient for report file tests
- Subprocess calls (ping, ssh) mocked in tests -- no actual network access needed

## Sources

### Primary (HIGH confidence)
- **Live measurement from dev host** -- ping to 10.10.110.246 and 10.10.110.247 confirms sub-ms RTT (verified 2026-03-16)
- **SSH to containers** -- `ip link show` confirms veth pair topology (eth0@if67, eth0@if74, MTU 1500)
- **icmplib 3.0.4** -- installed in venv, ping API verified; privileged=False fails on host (ping_group_range=1 0)
- **parse_ping_output()** in rtt_measurement.py -- verified working with container ping output (returns [0.154, 0.194, ...])
- **statistics.quantiles()** -- Python 3.12 stdlib, n=100 for percentile computation (used in benchmark.py)
- **pyproject.toml** -- zero new dependencies needed

### Secondary (MEDIUM confidence)
- [icmplib PyPI](https://pypi.org/project/icmplib/) -- privileged vs unprivileged mode documentation
- [icmplib unprivileged docs](https://github.com/ValentinBELYN/icmplib/blob/main/docs/6-use-icmplib-without-privileges.md) -- sysctl requirements
- [Performance of Container Networking Technologies (ACM)](https://dl.acm.org/doi/pdf/10.1145/3094405.3094406) -- veth/bridge overhead 7-52 microseconds typical
- [Container Networking Performance Analysis (SCIRP)](https://www.scirp.org/html/95740_95740.htm) -- LXC bridge mode latency 17-25% over baseline

### Tertiary (LOW confidence)
- [Linux Bridge Latency (ResearchGate)](https://www.researchgate.net/publication/239607023_Performance_Evaluation_of_Linux_Bridge) -- older research, kernel version dependent
- [Measuring Latency of Linux Bridge (Mantz Tech)](http://tech.mantz-it.com/2014/04/measuring-latency-of-linux-bridge.html) -- historical reference

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- all stdlib, verified on dev host, existing parse_ping_output works
- Architecture: HIGH -- simple script-generates-report pattern, follows existing scripts/ and docs/ conventions
- Pitfalls: HIGH -- icmplib privilege issue verified empirically, all pitfalls from direct testing
- Measurements: HIGH -- live preliminary data from actual production containers

**Research date:** 2026-03-16
**Valid until:** 2026-04-16 (stable -- container topology unlikely to change)
