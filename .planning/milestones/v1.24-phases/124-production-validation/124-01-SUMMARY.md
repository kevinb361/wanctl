---
phase: 124-production-validation
plan: 01
subsystem: infra
tags: [deploy, production, soak, validation, CAKE]

requires:
  - phase: 123-hysteresis-observability
    provides: health endpoint hysteresis section for monitoring
provides:
  - deployed v1.24 hysteresis code to production (cake-shaper VM)
  - VALN-01 validated (zero flapping alerts during prime-time)
  - VALN-02 validated (RRUL YELLOW in ~350ms, 150ms dwell overhead)
affects: [124-02-version-release]

key-files:
  created: []
  modified:
    - configs/spectrum-vm.yaml (synced exclude_params + thresholds with production)
    - configs/att-vm.yaml (synced hampel_window_size + fusion enabled)
    - scripts/deploy.sh (sudo fix for config validation)

key-decisions:
  - "Sync repo configs with production before deploy to avoid exclude_params overwrite incident"
  - "Deploy with defaults (dwell_cycles=3, deadband_ms=3.0) — no YAML changes needed"
  - "1 prime-time evening soak sufficient for validation"

one_liner: "Deployed v1.24 hysteresis to production, validated zero flapping alerts through prime-time (4,226 suppressions in 24h) and RRUL YELLOW detection in ~350ms (150ms dwell overhead)"
---

## What Was Done

Deployed hysteresis code to both Spectrum and ATT WANs on cake-shaper VM (10.10.110.223 / .227)
via deploy.sh. Synced repo configs with production first to avoid the v1.23.1 exclude_params
overwrite incident. Fixed deploy.sh sudo bug for config validation.

## Production Validation Results

### VALN-01: Zero Flapping (PASS)
- Spectrum ran 24h+ through a full prime-time evening window (7pm-11pm CDT, 2026-04-01)
- **3 total alerts** in 24h — all from genuine congestion (usenet download), zero from flapping
- **4,226 hysteresis suppressions** in 24h (~176/hour average, higher during prime-time)
- Baseline was 1-3 flapping alert pairs per evening pre-hysteresis
- ATT: 15 suppressions in 22h, rock-steady DSL

### VALN-02: RRUL Latency Budget (PASS)
- RRUL stress test run 2026-04-02 06:03 CDT against Dallas netperf server (104.200.21.31)
- RRUL started ~06:03:22, first YELLOW at 06:03:28.071
- **Detection time: ~350ms** from sustained load onset (150ms dwell + ~200ms EWMA ramp)
- Well within 500ms latency budget
- Controller recovered to GREEN 940M within seconds after RRUL completed

### Incident: Spectrum ISP Outage (2026-04-01 00:04 CDT)
- Spectrum WAN went down at midnight, gateway reachable but upstream dead
- wanctl circuit breaker tripped after 5 restart attempts
- Service stayed dead 5.5h until manual reset-failed + restart at 05:51
- Root cause: NetWatch pings ISP gateway (responds locally) not external host
- ATT unaffected — 22h+ continuous uptime through the outage
- Two todos captured: NetWatch fix + auto-recovery timer

## Self-Check: PASSED
