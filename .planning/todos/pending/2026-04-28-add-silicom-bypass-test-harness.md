---
created: 2026-04-28T20:30:00.000Z
title: Add Silicom bypass NIC test harness
area: testing
files:
  - docs/SILICOM-BYPASS.md
  - .planning/todos/pending/2026-04-28-add-silicom-bypass-nic-operational-tooling.md
  - scripts/silicom-test (planned)
  - scripts/silicom-test-scenarios/ (planned)
---

## Problem

With both ATT and Spectrum WANs now on the Silicom bypass NIC (per
2026-04-28 migration documented in `docs/SILICOM-BYPASS.md`), the card has
become a de-facto network test rig. It supports three orthogonal per-pair
states (NIC / bypass / disconnect) over two pairs, scriptable from a single
SSH command, with all transitions reversible in milliseconds.

That capability is too valuable to leave as ad-hoc `bpctl_util` invocations.
Several recurring test scenarios benefit from a structured harness:

1. **CAKE worth-it A/B.** Run RRUL/flent against a WAN with `set_bypass off`
   (CAKE shaped) then `set_bypass on` (raw ISP) and diff. Same hardware, same
   minute, same client — only the host-in-path changes. The cleanest CAKE
   measurement available short of physical recabling.

2. **Failover timing.** `set_disc on <pair>` simulates a cable pull. Measure
   detection-to-migration latency for steering, health endpoint flip latency,
   wanctl autorate state transitions, and convergence-back time on
   `set_disc off`.

3. **Wanctl resilience / chaos.** Bypass a WAN, kill `wanctl@<wan>.service`,
   observe — does the WAN keep working? Push bad config, restart, un-bypass,
   measure recovery. Long-bypass-then-restore to test baseline RTT
   re-convergence. Etc.

4. **Combined chaos.** One WAN dead (`set_disc on`) plus the other raw
   (`set_bypass on`) to validate "emergency bypass during outage" handling.

5. **Carrier flap / debounce validation.** Toggle `set_disc on/off` at varying
   intervals to confirm flapping detection thresholds behave as designed.

Today the blocker isn't capability — it's that running these tests means
hand-typed `bpctl_util` calls, no logging of which state a measurement was
taken under, no canned scenarios, and high risk of forgetting to restore
state at end of test.

## Solution

A test harness layer that **composes** the verbs delivered by the operational
tooling todo (`silicom-bypass on/off/disc/conn/mark/...`) into reusable
scenarios. This is intentionally a separate concern from the operational
tooling.

Components:

1. **`silicom-test` orchestrator** (`scripts/silicom-test`, bash or python):
   - `silicom-test ab-cake <pair> [--duration 60s] [--tool flent]` — runs a
     baseline measurement with CAKE in path, switches to bypass, repeats,
     diffs results, restores state, prints summary.
   - `silicom-test failover <dead-pair> [--duration 30s]` — disconnects one
     pair, captures steering/health/autorate state at fixed intervals,
     reconnects, captures recovery, prints timing summary.
   - `silicom-test chaos <scenario-name>` — runs a named scenario file from
     `scripts/silicom-test-scenarios/`.
   - `silicom-test status` — show what state is currently in effect (wraps
     `silicom-bypass status all` plus wanctl/steering health).
   - **Always-on safety:** every command registers a trap to call
     `silicom-bypass off <every-pair-it-touched>` on exit, regardless of
     success or failure. Crashed test must not leave WAN in bypass state.

2. **Scenario files** (`scripts/silicom-test-scenarios/*.sh` or `.yaml`):
   - `cake-ab-att.sh`, `cake-ab-spectrum.sh` — single-WAN A/B
   - `failover-att-to-spectrum.sh`, `failover-spectrum-to-att.sh` — directional
   - `dual-wan-loss.sh` — both WANs disconnected simultaneously
   - `wanctl-restart-during-bypass.sh` — service restart resilience
   - `long-bypass-recovery.sh` — extended bypass with autorate state freeze
   - Each scenario is self-contained: pre-conditions, steps, post-conditions,
     restore, summary capture.

3. **Result capture convention**:
   - Every test run gets a directory `tests/silicom/<timestamp>-<scenario>/`
   - Pre-state, post-state, intermediate snapshots, raw test tool output
     (flent/iperf/RRUL), wanctl `/health` snapshots at boundaries, journal
     extracts via `journalctl --since/--until`
   - `silicom-bypass mark` (from operational todo) used at every state
     transition to anchor the journal narrative

**Out of scope:**
- Operational tooling itself (CLI verbs, watchdog daemon, init service).
  Delivered by `2026-04-28-add-silicom-bypass-nic-operational-tooling.md`.
  This todo depends on that one being complete.
- Continuous / scheduled test runs. Initial scope is operator-invoked only.
  Could later be extended to nightly soak slot if useful.
- Integration with existing wanctl test harness (`tests/`, pytest). The
  Silicom test harness is system-level / hardware-in-the-loop; pytest is
  unit/integration on the Python side. Different lifecycles, different
  artifacts, intentionally not unified.

**Open questions for plan phase:**
- Scenario file format: bash (max flexibility, low ceremony) or YAML +
  interpreter (declarative, more uniform output, more code to write)?
- Result store retention policy. Test runs accumulate fast; `tests/silicom/`
  could fill the disk if every run is kept forever. 30-day rolling window?
- Whether to capture full pcaps during runs by default. Useful for
  post-hoc analysis, expensive in disk, may need explicit opt-in.
- Whether the harness should refuse to run if `wanctl@<wan>.service` is in a
  failed state, or allow chaos to compound deliberately.
- Scheduling: should multi-pair scenarios serialize (one WAN at a time) or
  allow simultaneous chaos? Operator confirmation gate likely needed for
  the latter.

**Dependencies:**
- Operational tooling todo (above) must be complete first. This harness
  composes those verbs.
- Optional but valuable: warm-reboot bypass-preservation finding from the
  operational todo's open questions, since it determines whether
  bypass-during-deploy patterns are safe to bake into scenarios.

Source: SILICOM-BYPASS.md migration session 2026-04-28, follow-on discussion
about using the card's three modes (NIC/bypass/disc) as a structured test
harness.
