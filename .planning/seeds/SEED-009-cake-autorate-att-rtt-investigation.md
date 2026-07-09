---
id: SEED-009
status: resolved
planted: 2026-07-06
resolved: 2026-07-06
resolved_by: investigation — ATT RTT was normal (190-5826us OWD delta, 25-29ms fping RTT)
trigger_when: cake-autorate is the active rate controller AND ATT RTT measurement is suspected broken
scope: Small
priority: 2
prerequisites: []
---

# SEED-009: cake-autorate ATT RTT measurement investigation

## Why This Matters

cake-autorate reports ~2000ms RTT for ATT (pinger_method=fping, reflectors 1.1.1.1, 8.8.8.8, 151.101.1.57, source IP 10.10.110.227). The steering daemon sees RTT 24-28ms for Spectrum, which is correct. ATT RTT of 2000ms is likely a reflector issue or fping parsing problem.

## Scope

- Verify fping RTT from cake-shaper to ATT reflectors
- Check if the ATT path is actually broken or if it's a measurement artifact
- Determine if cake-autorate's rate decisions for ATT are being impacted

## Resolution (2026-07-06)

- fping RTT from cake-shaper to ATT reflectors: 25-29ms (normal)
- ATT OWD delta: 190-5826us (0.19-5.8ms, normal)
- The ~2000ms was from initial startup when baselines were initializing (default 100000us = 100ms)
- No issue found. ATT RTT measurement is working correctly.
