# Phase 134: Diffserv Tin Separation - Research

**Researched:** 2026-04-03
**Domain:** MikroTik mangle rules (prerouting DSCP), CAKE diffserv4 tin classification, wanctl-check-cake CLI extension
**Confidence:** HIGH

## Summary

Phase 134 fixes the download DSCP marking gap identified in Phase 133: CAKE on ens17 sees download packets before MikroTik's postrouting DSCP SET rules mark them, so all download traffic lands in BestEffort. The fix is to add equivalent `change-dscp` rules in MikroTik's prerouting chain, matching on `connection-mark` (confirmed available in prerouting via conntrack) and `in-interface-list=WAN`. Rules are applied via MikroTik REST API (PUT to create, POST /move to position). The second deliverable extends `wanctl-check-cake` with a tin distribution check that reads per-tin packet counts from local `tc` stats and flags degenerate distributions.

Research confirms: (1) `connection-mark` IS available in prerouting because the connection tracking module labels every packet with its connection's mark; (2) `change-dscp` action works in all chains including prerouting; (3) MikroTik REST API uses PUT for resource creation and POST /move for rule ordering; (4) CAKE diffserv4 maps DSCP to 4 tins via a well-defined lookup table in kernel source.

**Primary recommendation:** Add 4 prerouting `change-dscp` rules mirroring the postrouting pattern, positioned after WASH and connection-mark assignment rules. Extend check_cake.py with a subprocess-based `tc` stats reader for tin distribution validation.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** Add MikroTik prerouting `change-dscp` rules for download direction. After the existing WAN WASH rule and after connection-mark assignment, re-mark based on connection-mark so DSCP marks survive through the bridge to CAKE on ens17. This is the cleanest fix -- marks exist before packets reach the cake-shaper bridge.
- **D-02:** Try prerouting first. If connection-marks aren't available for `change-dscp` action in that chain, investigate alternatives (forward chain, etc.). Data-driven decision.
- **D-03:** Mirror the existing postrouting DSCP SET pattern in prerouting. Same connection-mark-to-DSCP mapping: QOS_HIGH->EF(46), QOS_MEDIUM->AF31(26), QOS_LOW->CS1(8), QOS_NORMAL->CS0(0). Only match `in-interface-list=WAN` to avoid double-marking LAN-originated traffic.
- **D-04:** Apply rules via MikroTik REST API (curl commands). Reproducible, documentable, and verifiable by the executor. Same approach as existing wanctl router communication.
- **D-05:** Add a tin distribution threshold check to `wanctl-check-cake`. Read per-tin packet counts from tc stats. Flag if any non-BestEffort tin has 0 packets (or below a configurable threshold %). Output: table of tins with packet counts + PASS/WARN verdict.
- **D-06:** CLI check only -- no AlertEngine integration. wanctl-check-cake is a manual diagnostic tool. Runtime monitoring belongs in Phase 136 (hysteresis observability).
- **D-07:** Verify tin separation using Python `socket.setsockopt(IP_TOS, ...)` + tc tin stats (same proven approach from Phase 133). Test both upload (ens16) and download (ens17) directions. Send 100 packets per DSCP class, verify correct tin delta.

### Claude's Discretion
- Exact MikroTik mangle rule ordering relative to existing Trust/WASH rules
- Whether to add the prerouting DSCP rules before or after connection-mark assignment rules
- Threshold percentage for tin distribution check in wanctl-check-cake
- Whether to also verify download direction with iperf3 -R as secondary validation

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| QOS-02 | CAKE tins correctly separate traffic by DSCP class so EF/CS5 traffic gets lower latency than BE/BK | MikroTik prerouting `change-dscp` rules fix download gap; connection-mark available in prerouting (verified); CAKE diffserv4 mapping confirmed; Phase 133 proved upload already works |
| QOS-03 | `wanctl-check-cake` validates DSCP mark survival through the bridge path as an automated check | check_cake.py extension pattern documented; per-tin stats available via `tc -s -j qdisc show`; threshold-based PASS/WARN approach with existing CheckResult/Severity framework |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| MikroTik REST API | RouterOS 7.x | Add prerouting mangle rules | Already used by wanctl for all router communication |
| tc (iproute2) | System | Read CAKE per-tin stats | Already used by linux_cake backend for all CAKE operations |
| Python subprocess | stdlib | Run tc commands from check_cake | Same pattern as LinuxCakeBackend._run_tc() |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| wanctl.check_config.CheckResult | existing | Structured audit results | For tin distribution check results |
| wanctl.check_config.Severity | existing | PASS/WARN/ERROR levels | For tin distribution verdicts |
| wanctl.backends.linux_cake.TIN_NAMES | existing | Tin index-to-name mapping | For human-readable tin labels in check output |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| REST API PUT + POST /move | SSH CLI `/ip firewall mangle add place-before=` | SSH has native place-before support but REST is project standard |
| subprocess tc | LinuxCakeBackend.get_queue_stats() | Would need to instantiate a backend instance; subprocess is simpler for a CLI tool that runs once |
| Passive tin stats check | Active probe (send DSCP packets) | Active probe is more thorough but slower; passive check is sufficient per D-05 |

## Architecture Patterns

### MikroTik Prerouting Rule Ordering

The existing prerouting chain has this structure (from Phase 133 audit):

```
Prerouting chain (current order):
1. "Trust EF": action=accept, dscp=46
2. "Trust AF4x": action=accept, dscp=34/36/38
3. "DSCP WASH: inbound from WAN": action=change-dscp, new-dscp=0, in-interface-list=WAN
4. Connection-mark assignment rules (QOS_HIGH, QOS_MEDIUM, QOS_NORMAL, QOS_LOW)
```

**New rules go AFTER connection-mark assignment (position 5+):**

```
Prerouting chain (target order):
1. "Trust EF": action=accept, dscp=46
2. "Trust AF4x": action=accept, dscp=34/36/38
3. "DSCP WASH: inbound from WAN": action=change-dscp, new-dscp=0, in-interface-list=WAN
4. Connection-mark assignment rules (QOS_HIGH, QOS_MEDIUM, etc.)
5. NEW: "DSCP SET DL: HIGH (EF)": action=change-dscp, new-dscp=46, connection-mark=QOS_HIGH, in-interface-list=WAN, dscp=0
6. NEW: "DSCP SET DL: MEDIUM (AF31)": action=change-dscp, new-dscp=26, connection-mark=QOS_MEDIUM, in-interface-list=WAN, dscp=0
7. NEW: "DSCP SET DL: LOW (CS1)": action=change-dscp, new-dscp=8, connection-mark=QOS_LOW, in-interface-list=WAN, dscp=0
8. NEW: "DSCP SET DL: NORMAL (CS0)": action=change-dscp, new-dscp=0, connection-mark=QOS_NORMAL, in-interface-list=WAN, dscp=0
```

**Why this ordering:**
- Trust rules (1-2) MUST come first -- they `accept` client-set DSCP and skip further processing
- WASH (3) zeros WAN-inbound DSCP -- ISP marks are untrusted
- Connection-mark assignment (4) classifies flows into QOS_HIGH/MEDIUM/LOW/NORMAL
- NEW DSCP SET rules (5-8) re-stamp DSCP based on connection-mark, ONLY for WAN-inbound (download)
- `dscp=0` match ensures we only mark packets that WASH already zeroed (don't overwrite trusted marks)

### Pattern 1: MikroTik REST API Rule Creation (PUT)

**What:** Add a new mangle rule via REST API
**When to use:** Creating the 4 new prerouting DSCP SET rules

RouterOS REST API uses PUT to create resources:
```bash
# Source: https://help.mikrotik.com/docs/spaces/ROS/pages/47579162/REST+API
curl -k -u admin:$ROUTER_PASSWORD -X PUT \
  https://10.10.99.1/rest/ip/firewall/mangle \
  -H "content-type: application/json" \
  -d '{
    "chain": "prerouting",
    "action": "change-dscp",
    "new-dscp": "46",
    "connection-mark": "QOS_HIGH",
    "dscp": "0",
    "in-interface-list": "WAN",
    "comment": "DSCP SET DL: HIGH (EF)",
    "passthrough": "yes"
  }'
```

**Response:** Returns JSON with `.id` field (e.g., `"*1A"`) for the newly created rule.

### Pattern 2: MikroTik REST API Rule Positioning (POST /move)

**What:** Move a newly created rule to the correct position
**When to use:** After creating each rule, move it to the desired position in the chain

```bash
# Source: https://help.mikrotik.com/docs/spaces/ROS/pages/47579162/REST+API
# Move rule *1A to position before rule *1B
curl -k -u admin:$ROUTER_PASSWORD -X POST \
  https://10.10.99.1/rest/ip/firewall/mangle/move \
  -H "content-type: application/json" \
  -d '{"numbers": "*1A", "destination": "*1B"}'
```

**NOTE:** REST API rule IDs (e.g., `*1A`) do NOT match Winbox/SSH rule numbers. Always use the `.id` from the GET/PUT response. The `destination` field specifies the rule ID to move BEFORE.

**Alternative approach:** Create rules in the correct order and they append to the end of the prerouting chain. Since the new DSCP SET rules go AFTER all existing prerouting rules, they may naturally end up in the correct position without needing /move. Verify after creation.

### Pattern 3: check_cake.py Tin Distribution Check

**What:** Read per-tin packet counts and flag degenerate distributions
**When to use:** As a new audit section in wanctl-check-cake

```python
# Follow existing check_cake.py pattern
def check_tin_distribution(
    interface: str,
    direction: str,
    min_percent: float = 0.1,  # 0.1% threshold
) -> list[CheckResult]:
    """Check CAKE tin distribution on a local interface.

    Reads per-tin sent_packets from tc JSON stats. Flags non-BestEffort
    tins with 0 packets as WARN (expected traffic not reaching that tin).

    Args:
        interface: Network interface (e.g., "ens17" for download)
        direction: "download" or "upload" for labeling
        min_percent: Minimum % of total packets for non-BE tins

    Returns:
        List of CheckResult with PASS/WARN verdicts.
    """
    results: list[CheckResult] = []
    category = f"Tin Distribution ({direction})"

    # Run tc command (same as LinuxCakeBackend)
    rc, out, _ = subprocess.run(
        ["tc", "-s", "-j", "qdisc", "show", "dev", interface],
        capture_output=True, text=True, timeout=5
    )
    # Parse JSON, find CAKE entry, extract tins
    # TIN_NAMES = ["Bulk", "BestEffort", "Video", "Voice"]
    # For each tin: calculate % of total, PASS if > threshold, WARN if 0
    return results
```

### Anti-Patterns to Avoid
- **Adding DSCP SET rules BEFORE connection-mark assignment:** Connection-marks won't be set yet for new connections, so rules won't match.
- **Omitting `dscp=0` match on new rules:** Without this, the rules would re-mark traffic that already has DSCP set by Trust rules, defeating the purpose of Trust EF / Trust AF4x.
- **Omitting `in-interface-list=WAN`:** Without this, LAN-originated traffic (already marked in postrouting) would get double-processed in prerouting.
- **Using check_cake's existing MikroTik client for tin stats:** The tin stats come from the cake-shaper VM's local tc, not from the MikroTik router. Must use subprocess, not the REST API client.
- **Matching on `passthrough=no` for DSCP SET rules:** The existing postrouting DSCP SET rules use passthrough. Use `passthrough=yes` so packets continue through the chain for any additional processing.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| DSCP-to-tin mapping | Custom mapping table | CAKE diffserv4 kernel mapping | The kernel has the authoritative mapping; custom code would drift |
| tc JSON parsing | Custom parser | Reuse pattern from `linux_cake.py:237-256` | Proven, tested, handles edge cases |
| CheckResult formatting | Custom output | `check_config.format_results()` | Already supports --json, --no-color, --quiet modes |
| Rule ID discovery | Hardcoded IDs | GET /rest/ip/firewall/mangle to find IDs by comment | IDs are opaque (*XX format), must be discovered at runtime |

## Common Pitfalls

### Pitfall 1: REST API Rule Ordering
**What goes wrong:** Rules created via PUT append to the END of the chain by default. If prerouting has rules from other chains mixed in (unlikely but possible), the new rules could end up in the wrong position.
**Why it happens:** REST API has limited support for `place-before` compared to CLI.
**How to avoid:** After creating all 4 rules, GET the full prerouting chain and verify order. Use POST /move if needed. The most reliable approach: since the new rules go AFTER all existing prerouting rules, appending to the end should be correct.
**Warning signs:** After creation, `curl GET /rest/ip/firewall/mangle` shows DSCP SET DL rules positioned before connection-mark rules.

### Pitfall 2: Connection-Mark Timing for New Connections
**What goes wrong:** The very first packet of a NEW connection may not have a connection-mark yet when it hits the DSCP SET rules in prerouting.
**Why it happens:** Connection-mark is set by prerouting rules with `connection-state=new`. Subsequent packets of the same connection inherit the mark from conntrack. But the initial SYN packet triggers BOTH the mark-connection rule AND the DSCP SET rule in the same prerouting pass.
**How to avoid:** This is actually fine -- MikroTik processes rules sequentially within a chain. If the connection-mark assignment rule comes BEFORE the DSCP SET rule (which it does), the connection-mark IS available for matching on the same first packet. Passthrough=yes on the mark-connection rule is key.
**Warning signs:** Test with tcpdump on first packet of a flow -- if DSCP=0 on first packet but correct on subsequent packets, this is the issue.

### Pitfall 3: check_cake Running on Wrong Host
**What goes wrong:** The tin distribution check tries to run `tc` on the developer's machine instead of the cake-shaper VM.
**Why it happens:** check_cake.py currently runs locally and talks to the MikroTik router via REST. The new tin check must run `tc` on the cake-shaper VM where CAKE qdiscs live.
**How to avoid:** The tin distribution check should be designed for local execution on cake-shaper. check_cake is already run from the same host where wanctl runs. The YAML config has `cake_params.download_interface` and `cake_params.upload_interface` for the local NIC names.
**Warning signs:** "No CAKE qdisc found" error when running from a machine that doesn't have CAKE qdiscs.

### Pitfall 4: DSCP SET DL: NORMAL Rule is a No-Op
**What goes wrong:** The `DSCP SET DL: NORMAL (CS0)` rule matches `connection-mark=QOS_NORMAL, dscp=0` and sets `new-dscp=0` -- it changes nothing.
**Why it happens:** CS0 is DSCP 0, same as the WASH output. The postrouting version exists for completeness/logging.
**How to avoid:** Still add the rule for symmetry and logging (MikroTik counts packets per rule), but document that it's a no-op for DSCP values. It provides useful traffic accounting.
**Warning signs:** No warning sign -- this is expected behavior.

### Pitfall 5: linux-cake Transport Config vs REST Router Config
**What goes wrong:** check_cake currently only creates a MikroTik REST/SSH client. For tin distribution, it needs local `tc` access. If the config has `router.transport: linux-cake`, the router client creation will fail.
**Why it happens:** linux-cake transport doesn't connect to the MikroTik router for CAKE operations -- it manages CAKE locally.
**How to avoid:** The tin distribution check should be independent of the router client. Read `cake_params.download_interface` and `cake_params.upload_interface` from the YAML config and run `tc` locally. For router-related checks, the config also has `router.host` for the MikroTik REST connection.
**Warning signs:** `check_cake.py` crashes with "Unsupported transport: linux-cake" when trying to create a router client.

## CAKE diffserv4 Tin Mapping Reference

From CAKE kernel source (`sch_cake/gen_cake_const.c`):

| Tin | Index | DSCP Classes | Bandwidth Threshold |
|-----|-------|-------------|---------------------|
| Bulk | 0 | CS1 (8) | 6.25% |
| BestEffort | 1 | CS0 (0), all unassigned | 100% |
| Video | 2 | AF2x (18/20/22), AF3x (24/26/28), AF4x (32/34/36), CS2 (16), CS3 (24), TOS1 (1), TOS4 (4) | 50% |
| Voice | 3 | EF (46), VA (44), CS4 (32), CS5 (40), CS6 (48), CS7 (56) | 25% |

**Key DSCP values for this phase:**
- EF (46) = Voice tin (3) -- QOS_HIGH mapping
- AF31 (26) = Video tin (2) -- QOS_MEDIUM mapping
- CS1 (8) = Bulk tin (0) -- QOS_LOW mapping
- CS0 (0) = BestEffort tin (1) -- QOS_NORMAL mapping

All 4 connection-mark-to-DSCP mappings land in the correct expected tins.

## MikroTik REST API Mangle Rule Fields

For the prerouting DSCP SET rules, these are the JSON fields for the PUT request:

| Field | Value | Purpose |
|-------|-------|---------|
| `chain` | `"prerouting"` | Target chain |
| `action` | `"change-dscp"` | Set DSCP value |
| `new-dscp` | `"46"` / `"26"` / `"8"` / `"0"` | Target DSCP |
| `connection-mark` | `"QOS_HIGH"` / `"QOS_MEDIUM"` / etc. | Match on connection classification |
| `dscp` | `"0"` | Only match packets WASH already zeroed |
| `in-interface-list` | `"WAN"` | Only match WAN-inbound (download) |
| `comment` | `"DSCP SET DL: HIGH (EF)"` etc. | Human-readable label |
| `passthrough` | `"yes"` | Continue processing after match |

**REST API endpoint:** `PUT https://10.10.99.1/rest/ip/firewall/mangle`

**Verify after creation:** `GET https://10.10.99.1/rest/ip/firewall/mangle?chain=prerouting` to confirm rule order.

## Code Examples

### Example 1: Create All 4 Prerouting DSCP SET Rules via REST API

```bash
# Source: MikroTik REST API docs + existing wanctl routeros_rest.py patterns

ROUTER="https://10.10.99.1/rest"
AUTH="-u admin:$ROUTER_PASSWORD"

# Rule 1: QOS_HIGH -> EF (DSCP 46)
curl -k $AUTH -X PUT "$ROUTER/ip/firewall/mangle" \
  -H "content-type: application/json" \
  -d '{
    "chain": "prerouting",
    "action": "change-dscp",
    "new-dscp": "46",
    "connection-mark": "QOS_HIGH",
    "dscp": "0",
    "in-interface-list": "WAN",
    "comment": "DSCP SET DL: HIGH (EF)",
    "passthrough": "yes"
  }'

# Rule 2: QOS_MEDIUM -> AF31 (DSCP 26)
curl -k $AUTH -X PUT "$ROUTER/ip/firewall/mangle" \
  -H "content-type: application/json" \
  -d '{
    "chain": "prerouting",
    "action": "change-dscp",
    "new-dscp": "26",
    "connection-mark": "QOS_MEDIUM",
    "dscp": "0",
    "in-interface-list": "WAN",
    "comment": "DSCP SET DL: MEDIUM (AF31)",
    "passthrough": "yes"
  }'

# Rule 3: QOS_LOW -> CS1 (DSCP 8)
curl -k $AUTH -X PUT "$ROUTER/ip/firewall/mangle" \
  -H "content-type: application/json" \
  -d '{
    "chain": "prerouting",
    "action": "change-dscp",
    "new-dscp": "8",
    "connection-mark": "QOS_LOW",
    "dscp": "0",
    "in-interface-list": "WAN",
    "comment": "DSCP SET DL: LOW (CS1)",
    "passthrough": "yes"
  }'

# Rule 4: QOS_NORMAL -> CS0 (DSCP 0) -- no-op but useful for accounting
curl -k $AUTH -X PUT "$ROUTER/ip/firewall/mangle" \
  -H "content-type: application/json" \
  -d '{
    "chain": "prerouting",
    "action": "change-dscp",
    "new-dscp": "0",
    "connection-mark": "QOS_NORMAL",
    "dscp": "0",
    "in-interface-list": "WAN",
    "comment": "DSCP SET DL: NORMAL (CS0)",
    "passthrough": "yes"
  }'
```

### Example 2: Verify Rule Order via REST API

```bash
# Get all prerouting rules and check order
curl -k $AUTH -X GET "$ROUTER/ip/firewall/mangle?chain=prerouting" \
  -H "content-type: application/json" | python3 -m json.tool
```

Expected output shows Trust rules first, then WASH, then connection-mark assignment, then the new DSCP SET DL rules.

### Example 3: Move Rule to Correct Position (if needed)

```bash
# If rule *1A needs to be before rule *1B:
curl -k $AUTH -X POST "$ROUTER/ip/firewall/mangle/move" \
  -H "content-type: application/json" \
  -d '{"numbers": "*1A", "destination": "*1B"}'
```

### Example 4: Tin Distribution Check Pattern for check_cake.py

```python
import json
import subprocess
from wanctl.check_config import CheckResult, Severity
from wanctl.backends.linux_cake import TIN_NAMES

def check_tin_distribution(
    interface: str,
    direction: str,
    min_percent: float = 0.1,
) -> list[CheckResult]:
    """Check CAKE tin distribution on a local interface."""
    results: list[CheckResult] = []
    category = f"Tin Distribution ({direction})"

    try:
        proc = subprocess.run(
            ["tc", "-s", "-j", "qdisc", "show", "dev", interface],
            capture_output=True, text=True, timeout=5,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        results.append(CheckResult(
            category, "tc_command", Severity.ERROR,
            f"Failed to run tc on {interface}: {e}",
        ))
        return results

    if proc.returncode != 0:
        results.append(CheckResult(
            category, "tc_command", Severity.ERROR,
            f"tc failed on {interface}: {proc.stderr.strip()}",
        ))
        return results

    # Parse JSON and find CAKE entry
    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError:
        results.append(CheckResult(
            category, "tc_parse", Severity.ERROR,
            f"Failed to parse tc JSON output for {interface}",
        ))
        return results

    cake_entry = None
    for entry in data:
        if entry.get("kind") == "cake":
            cake_entry = entry
            break

    if cake_entry is None:
        results.append(CheckResult(
            category, "cake_qdisc", Severity.ERROR,
            f"No CAKE qdisc found on {interface}",
        ))
        return results

    tins = cake_entry.get("tins", [])
    if len(tins) != 4:
        results.append(CheckResult(
            category, "tin_count", Severity.ERROR,
            f"Expected 4 tins (diffserv4), found {len(tins)} on {interface}",
        ))
        return results

    # Calculate total and per-tin percentages
    total_packets = sum(t.get("sent_packets", 0) for t in tins)
    if total_packets == 0:
        results.append(CheckResult(
            category, "total_packets", Severity.WARN,
            f"No packets processed on {interface} -- run traffic first",
        ))
        return results

    for i, tin in enumerate(tins):
        name = TIN_NAMES[i] if i < len(TIN_NAMES) else f"Tin{i}"
        packets = tin.get("sent_packets", 0)
        pct = (packets / total_packets) * 100

        if name == "BestEffort":
            # BestEffort always has traffic -- just report
            results.append(CheckResult(
                category, f"tin_{name.lower()}", Severity.PASS,
                f"{name}: {packets:,} packets ({pct:.1f}%)",
            ))
        else:
            if packets == 0:
                results.append(CheckResult(
                    category, f"tin_{name.lower()}", Severity.WARN,
                    f"{name}: 0 packets (0%) -- no {name} traffic reaching CAKE",
                    suggestion=f"Verify DSCP marks for {name} tin survive the bridge path",
                ))
            elif pct < min_percent:
                results.append(CheckResult(
                    category, f"tin_{name.lower()}", Severity.WARN,
                    f"{name}: {packets:,} packets ({pct:.2f}%) -- below {min_percent}% threshold",
                ))
            else:
                results.append(CheckResult(
                    category, f"tin_{name.lower()}", Severity.PASS,
                    f"{name}: {packets:,} packets ({pct:.1f}%)",
                ))

    return results
```

### Example 5: Python Socket DSCP Validation (from Phase 133)

```python
import socket

def send_dscp_test_packets(target_ip: str, dscp: int, count: int = 100) -> None:
    """Send UDP packets with specific DSCP marking for tin validation."""
    tos_byte = dscp << 2  # DSCP is top 6 bits of TOS byte
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_TOS, tos_byte)
    for _ in range(count):
        sock.sendto(b"DSCP_TEST", (target_ip, 9999))
    sock.close()

# Test all 4 DSCP classes:
# send_dscp_test_packets("10.10.99.1", 46, 100)  # EF -> Voice
# send_dscp_test_packets("10.10.99.1", 26, 100)  # AF31 -> Video
# send_dscp_test_packets("10.10.99.1", 8, 100)   # CS1 -> Bulk
# send_dscp_test_packets("10.10.99.1", 0, 100)   # CS0 -> BestEffort
```

## Connection-Mark Availability in Prerouting

**Confidence: HIGH** (verified via MikroTik community expert + documentation)

Connection-marks ARE available for matching in the prerouting chain. The connection tracking module labels every packet with the connection-mark of the connection to which the packet belongs. Key facts:

1. Connection-mark is set on the FIRST packet (connection-state=new) and stored in conntrack
2. All subsequent packets of the same connection inherit the mark from conntrack
3. The mark is available in ALL chains (prerouting, forward, postrouting, input, output)
4. Within a single chain pass, if a mark-connection rule sets the mark with passthrough=yes, subsequent rules in the SAME pass can match on it

This means the prerouting approach WILL work:
- WASH zeros DSCP (rule 3)
- Connection-mark assignment rules classify the flow (rule 4+)
- DSCP SET DL rules match on connection-mark and re-stamp DSCP (rule 5-8)
- All in a single prerouting pass, sequential processing

Source: [MikroTik community forum discussion](https://forum.mikrotik.com/t/mangle-prerouting-postrouting/145721) -- expert confirms "the connection tracking module labels each packet with the connection-mark of the connection to which the packet belongs."

## check_cake.py Integration Architecture

### Current check_cake.py Structure

```
main() → load YAML → detect config type → create router client → run_audit()
  run_audit():
    1. check_env_vars()      → Environment
    2. check_connectivity()   → Connectivity
    3. check_queue_tree()     → Queue Tree, CAKE Type, ceiling
    3.5. check_cake_params()  → CAKE Params, Link Params
    4. check_mangle_rule()    → Mangle Rule (steering only)
```

### Extended Structure (Phase 134)

```
main() → load YAML → detect config type → create router client → run_audit()
  run_audit():
    1-4. (existing checks unchanged)
    5. NEW: check_tin_distribution() → Tin Distribution (download/upload)
       - Reads cake_params.download_interface / upload_interface from YAML
       - Runs tc locally (subprocess, NOT via router client)
       - Reports per-tin packet counts + PASS/WARN
```

**Key design decisions:**
- The tin check is independent of the router client (runs local tc)
- Uses `cake_params` from YAML config for interface names
- Only runs when `cake_params` is present (linux-cake transport)
- For REST/SSH transport configs, skip tin check (CAKE is on router, not accessible via tc)

### Threshold Recommendation

**Recommended: 0.1% minimum for non-BestEffort tins.**

Rationale: In production, Voice has ~8.1% of download traffic (from Phase 133 ens17 stats). Video and Bulk are much smaller. A 0% threshold would only catch total absence. 0.1% is low enough to avoid false positives while catching degenerate distributions. The threshold should be a constant, not configurable via CLI args (too many args already).

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| DSCP marking only in postrouting | Add prerouting DSCP for download direction | This phase | Download CAKE tins will separate traffic |
| iperf3 --dscp for testing | Python socket.setsockopt(IP_TOS) | Phase 133 | Reliable DSCP injection (iperf3 control stream misleads) |
| check_cake: router-only checks | check_cake: router + local tc tin stats | This phase | Validates end-to-end DSCP-to-tin pipeline |

## Open Questions

1. **REST API `place-before` support for mangle rules**
   - What we know: CLI has `place-before` natively; REST API uses PUT (appends to end) + POST /move (reposition). A forum thread from 2022 asked about REST `place-before` with no answer.
   - What's unclear: Whether modern RouterOS 7.x supports `place-before` as a PUT field (not just `/add place-before` CLI).
   - Recommendation: Use PUT to create (appends to end) then verify position. Since new rules go at the END of prerouting anyway, this should work without /move. If position is wrong, use POST /move to fix.

2. **set-priority from-dscp in prerouting**
   - What we know: The existing postrouting chain has a `set-priority from-dscp` rule that maps DSCP to 802.1p PCP for VLAN/WMM. The CONTEXT.md mentions this may need a prerouting equivalent.
   - What's unclear: Whether bridge-forwarded traffic needs 802.1p priority set in prerouting, or whether the postrouting set-priority already covers it.
   - Recommendation: Do NOT add set-priority in prerouting for now. The bridge is pure L2 without VLAN filtering -- 802.1p priority tags only matter for VLAN-tagged frames. CAKE reads DSCP directly, not 802.1p. Defer unless testing reveals a need.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.0.2 |
| Config file | pyproject.toml |
| Quick run command | `.venv/bin/pytest tests/test_check_cake.py -x -v` |
| Full suite command | `.venv/bin/pytest tests/ -v` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| QOS-02 | Download tins separate by DSCP class | manual (production validation) | Python socket + tc tin delta on cake-shaper | N/A (production test) |
| QOS-03 | check_cake tin distribution check | unit | `.venv/bin/pytest tests/test_check_cake.py -x -k tin_distribution` | No -- Wave 0 |

### Sampling Rate
- **Per task commit:** `.venv/bin/pytest tests/test_check_cake.py -x -v`
- **Per wave merge:** `.venv/bin/pytest tests/ -v`
- **Phase gate:** Full suite green before /gsd:verify-work

### Wave 0 Gaps
- [ ] `tests/test_check_cake.py` -- add tests for `check_tin_distribution()` function
  - Test with mocked subprocess output (4-tin happy path, 0-packet tin, no CAKE qdisc, tc failure)
  - Test integration into `run_audit()` flow (only when cake_params present)
- [ ] No new test files needed -- extend existing `tests/test_check_cake.py` (148 tests currently)

## Sources

### Primary (HIGH confidence)
- MikroTik REST API official docs: https://help.mikrotik.com/docs/spaces/ROS/pages/47579162/REST+API -- PUT for creation, POST /move for ordering
- MikroTik Mangle official docs: https://help.mikrotik.com/docs/spaces/ROS/pages/48660587/Mangle -- change-dscp action, connection-mark matching
- CAKE kernel source (gen_cake_const.c): https://github.com/dtaht/sch_cake/blob/master/gen_cake_const.c -- diffserv4 DSCP-to-tin mapping
- tc-cake(8) man page: https://man7.org/linux/man-pages/man8/tc-cake.8.html -- diffserv4 tin descriptions
- Phase 133 ANALYSIS.md -- hop-by-hop audit results, download gap identification, mangle rule dump

### Secondary (MEDIUM confidence)
- MikroTik forum on connection-mark in prerouting: https://forum.mikrotik.com/t/mangle-prerouting-postrouting/145721 -- expert confirms connection-mark available in prerouting
- MikroTik forum on REST API rule positioning: https://forum.mikrotik.com/t/rest-api-insert-firewall-rule/161471 -- rule ID mismatch between REST and CLI noted

### Tertiary (LOW confidence)
- REST API `place-before` as PUT field -- no confirmed documentation; forum thread unanswered. Workaround via PUT + POST /move is confirmed.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- using existing project tools (REST API, tc, check_cake.py)
- Architecture: HIGH -- prerouting rule ordering well understood from Phase 133 audit; connection-mark in prerouting confirmed
- Pitfalls: HIGH -- Phase 133 thoroughly mapped the bridge path and failure modes; REST API rule ordering is the only MEDIUM-confidence area

**Research date:** 2026-04-03
**Valid until:** 2026-05-03 (stable domain -- MikroTik RouterOS and CAKE kernel behavior rarely change)
