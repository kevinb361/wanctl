# Phase 105: LinuxCakeBackend Core - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-03-24
**Phase:** 105-linuxcakebackend-core
**Areas discussed:** Interface mismatch, Stats contract mapping, CAKE init ownership, Error handling in 50ms loop

---

## Interface Mismatch

| Option | Description | Selected |
|--------|-------------|----------|
| Split ABC into two protocols | BandwidthBackend + RuleBackend. Clean separation. | |
| No-op stubs on LinuxCakeBackend | enable_rule returns True, disable_rule returns True. Keeps single ABC. | ✓ |
| Raise NotImplementedError | Fails fast if called incorrectly. | |

**User's choice:** "What do you recommend?" — Claude recommended no-op stubs.
**Notes:** Splitting ABC is overkill since WANController/SteeringDaemon don't use it yet. No-op stubs are pragmatic. NotImplementedError would be wrong — violates ABC contract.

---

## Stats Contract Mapping

| Option | Description | Selected |
|--------|-------------|----------|
| Superset dict with backward compat | Existing 5 fields + new fields (tins, memory_used, etc). | ✓ |
| Separate methods | get_queue_stats() basic + get_tin_stats() per-tin. Two calls. | |

**User's choice:** "You decide" — Claude chose superset dict.
**Notes:** Fits existing codebase pattern of flexible dicts. Avoids doubling tc subprocess calls.

---

## CAKE Init Ownership

| Option | Description | Selected |
|--------|-------------|----------|
| Yes, backend initializes | initialize_cake() with tc qdisc replace. Self-contained. | |
| No, external init only | Assumes CAKE exists. Only tc qdisc change. | |
| Both — init + validate | init_cake() + validate_cake(). Startup inits, runtime changes. | ✓ |

**User's choice:** "You decide what is best" — Claude chose both init + validate.
**Notes:** systemd-networkd can't be trusted for CAKE setup (silent misconfiguration pitfall from research). Backend should own initialization.

---

## Error Handling in 50ms Loop

| Option | Description | Selected |
|--------|-------------|----------|
| Match existing pattern | Sub-cycle retry (single attempt, 50ms max). Consistent with REST backend. | |
| Skip and log only | tc failure = skip cycle. No retry. Log WARNING. | ✓ |

**User's choice:** "You decide" — Claude chose skip and log.
**Notes:** tc is local (~2ms), not network. Failures indicate system issues, not transient blips. Next cycle retries naturally.

---

## Claude's Discretion

- Internal class structure, subprocess timeout values, log formatting, test design
- Superset dict approach for stats contract
- init + validate pattern for CAKE initialization
- Skip-and-log error handling for tc failures

## Deferred Ideas

- ABC refactoring into BandwidthBackend/RuleBackend — revisit if interface mismatch causes problems
- pyroute2 netlink backend (PERF-01) — only if subprocess proves too slow
