# Phase 113: Network Engineering Audit - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md -- this log preserves the alternatives considered.

**Date:** 2026-03-26
**Phase:** 113-network-engineering-audit
**Areas discussed:** CAKE parameter source of truth, DSCP trace methodology, Steering logic audit depth, Queue depth baseline conditions

---

## CAKE Parameter Source of Truth

| Option | Description | Selected |
|--------|-------------|----------|
| YAML config files | Read /etc/wanctl/*.yaml, extract CAKE params, compare against tc -j output | x |
| Code defaults + YAML | Check both cake_params.py defaults AND config overrides | |
| check_cake.py output | Run the existing wanctl-check-cake CLI on the VM | |

**User's choice:** YAML config files
**Notes:** Config IS the intent. YAML is the source of truth.

### Follow-up: Secondary verification

| Option | Description | Selected |
|--------|-------------|----------|
| Both -- tc readback + check-cake | Belt and suspenders: raw tc -j AND check-cake CLI output | x |
| tc -j readback only | Manual tc -j is authoritative, check-cake is convenience | |

**User's choice:** Both -- tc readback + check-cake
**Notes:** Documents that the tooling itself works correctly on production.

---

## DSCP Trace Methodology

| Option | Description | Selected |
|--------|-------------|----------|
| Document the design path | Read MikroTik mangle rules + CAKE diffserv4 config, map the logical flow | x |
| Live traffic verification | Generate test traffic with known DSCP marks, check tc -s stats | |
| Both -- design + live | Document AND verify with live test traffic | |

**User's choice:** Document the design path
**Notes:** Configuration is deterministic -- no live test traffic needed.

### Follow-up: Router data source

| Option | Description | Selected |
|--------|-------------|----------|
| REST API from workstation | Query MikroTik REST API (10.10.99.1) for /ip/firewall/mangle | x |
| SSH to router | /ip firewall mangle print via SSH | |
| Screenshot/export from Winbox | Manual export from Winbox GUI | |

**User's choice:** REST API from workstation
**Notes:** Already proven fast and reliable from wanctl tooling.

---

## Steering Logic Audit Depth

| Option | Description | Selected |
|--------|-------------|----------|
| Code review + config verification | Read steering source, document weights/thresholds, verify config match | x |
| Code review + runtime log analysis | Same plus pull production logs and verify decisions match logic | |
| Code review only | Pure source code audit, trust config-to-behavior correctness | |

**User's choice:** Code review + config verification
**Notes:** No runtime log analysis needed.

---

## Queue Depth Baseline Conditions

| Option | Description | Selected |
|--------|-------------|----------|
| Idle + load snapshots | Capture tc -s at idle AND during benchmark. Shows operating range. | x |
| Idle only | Single capture at steady state | |
| Load only | Capture during benchmark only | |

**User's choice:** Idle + load snapshots
**Notes:** Uses existing wanctl-benchmark / flent tooling for load generation.

---

## Claude's Discretion

- Findings report structure and section ordering
- Level of detail in signal chain documentation
- Whether to capture tc -s stats for both WANs separately or combined

## Deferred Ideas

None -- discussion stayed within phase scope.
