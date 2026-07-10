---
created: 2026-06-04T13:30:00Z
title: Evaluate fping as wanctl RTT measurement backend option
area: performance
resolves_phase: 247
files:
  - src/wanctl/rtt_measurement.py
  - src/wanctl/autorate_continuous.py
  - src/wanctl/steering/daemon.py
  - configs/spectrum.yaml
---

## Problem

wanctl currently relies on Python ICMP RTT measurement for autorate/steering inputs. During the Spectrum cake-autorate trial, `fping` was installed and verified on cake-shaper, but cake-autorate's `fping` mode entered STALL under the first systemd/service setup while classic `ping` mode produced live samples.

That does not prove `fping` is bad for wanctl. It means `fping` should be evaluated deliberately as an optional wanctl measurement backend rather than assumed as a drop-in replacement.

Potential reasons to evaluate it:

- purpose-built multi-target ping loop
- efficient reflector fanout
- machine-readable timestamped output
- source address binding with `-S`
- already packaged on Debian/OpenWrt-style systems

Risks and constraints:

- subprocess lifecycle management can be fragile in a fast autorate loop
- output parsing needs tests and timeout handling
- must not regress the 50ms cycle budget
- must preserve source-address/interface binding for ATT/Spectrum policy routing
- should be fallback-capable; no hard dependency unless packaging handles it cleanly
- compare against existing icmplib and prior IRTT research before changing production defaults

## Solution

Research and prototype a pluggable RTT backend abstraction:

1. Document current wanctl RTT measurement path and where autorate/steering consume it.
2. Add an experimental `fping` backend behind config, not as the default.
3. Support source IP binding (`fping -S <source_ip>`) and multiple reflectors.
4. Parse timestamped output robustly; handle packet loss, partial lines, stalls, and process death.
5. Add unit tests using captured `fping` output samples.
6. Benchmark cycle time and CPU against current icmplib backend under idle and load.
7. Run a controlled cake-shaper A/B test:
   - current backend
   - fping backend
   - optional IRTT backend if still relevant
8. Decide whether fping should become default, fallback, or rejected.

## Acceptance Criteria

- No production default changes without A/B evidence.
- Backend is selectable per WAN/config.
- Missing `fping` produces a clear health/config error or automatic fallback.
- RTT sample output includes enough metadata to distinguish backend/source/reflector.
- Steering and autorate cycle budgets do not regress.
- Spectrum-specific source binding works on cake-shaper.

## Closure (2026-07-09)

Superseded by cake-autorate cutover. cake-autorate already uses fping natively as the production RTT measurement backend (active since 2026-07-05). FLIP-02 closed as moot per STATE.md. No wanctl-side fping backend needed.
