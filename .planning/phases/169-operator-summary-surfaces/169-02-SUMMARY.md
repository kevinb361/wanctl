---
phase: 169-operator-summary-surfaces
plan: 02
subsystem: observability
tags: [validation, production, health, parity]

# Dependency graph
requires:
  - phase: 169-operator-summary-surfaces
    plan: 01
    provides: compact summary contract for autorate and steering health plus operator helper
provides:
  - healthy-live validation of the compact summary contract
  - explicit ATT/Spectrum parity decision for the operator summary surface
  - handoff-ready summary contract for Phase 170 canary work
affects: []

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Healthy-live validation should prove a new summary contract is quiet, bounded, and readable on real services before canary automation depends on it"
    - "Parity checks should compare compact row keys and helper output directly instead of relying on manual nested JSON inspection"

key-files:
  created:
    - .planning/phases/169-operator-summary-surfaces/169-02-SUMMARY.md
  modified:
    - src/wanctl/steering/health.py
    - .planning/ROADMAP.md
    - .planning/REQUIREMENTS.md
    - .planning/STATE.md
    - .planning/HANDOFF.json
    - .planning/WAITING.json

key-decisions:
  - "Approved outcome: summaries ready"
  - "Tightened steering `wan_zone` fallback to `unknown` so the compact contract stays bounded and operator-readable even when WAN awareness has no effective zone"
  - "Kept the helper contract sourced only from `/health`; Phase 169 does not pull Phase 170 canary scripting into the implementation"

patterns-established:
  - "When new summary surfaces are validated live, the helper output should be archived alongside raw health captures so future canary work can reuse both"

requirements-completed: [SURF-01, SURF-02]

# Metrics
duration: 45min
completed: 2026-04-12
status: complete
---

# Phase 169 Plan 02 Summary

**Validated the new compact summary contract on live services and confirmed ATT/Spectrum parity in the operator-facing view.**

## Local Validation
- `.venv/bin/pytest -o addopts='' tests/test_health_check.py tests/steering/test_steering_health.py tests/test_operator_summary.py -q`
- Result: `186 passed`
- `.venv/bin/mypy src/wanctl/health_check.py src/wanctl/steering/health.py src/wanctl/operator_summary.py`
- Result: `Success: no issues found in 3 source files`
- `.venv/bin/ruff check src/wanctl/health_check.py src/wanctl/steering/health.py src/wanctl/operator_summary.py tests/test_health_check.py tests/steering/test_steering_health.py tests/test_operator_summary.py`
- Result: clean

## Manual Gate Result
- **Decision:** `approved: summaries ready`
- Deployment target: `cake-shaper` (`wanctl@spectrum`, `wanctl@att`, `steering.service`)
- Deploy action: copied [health_check.py](/home/kevin/projects/wanctl/src/wanctl/health_check.py), [steering/health.py](/home/kevin/projects/wanctl/src/wanctl/steering/health.py), and [operator_summary.py](/home/kevin/projects/wanctl/src/wanctl/operator_summary.py) to `/opt/wanctl/`, then restarted all three services.
- Live healthy-state checks after deploy:
  - `systemctl is-active wanctl@spectrum wanctl@att steering.service` -> `active active active`
  - Spectrum `/health` sampled twice -> `summary.service=autorate`, `summary.status=healthy`, row status `ok`, storage/runtime `ok`, alert status `idle`
  - ATT `/health` sampled twice -> same `summary` row keys as Spectrum, row status `ok`, storage/runtime `ok`, alert status `idle`
  - Steering `/health` sampled twice -> `summary.service=steering`, `summary.status=healthy`, row status `ok`, bounded `wan_zone` and congestion state present
  - Operator helper output from [operator_summary.py](/home/kevin/projects/wanctl/src/wanctl/operator_summary.py) rendered all three services consistently:
    - `spectrum`: `DL GREEN/UL GREEN`, storage `ok`, runtime `ok`, alerts `idle f=0 c=0`
    - `att`: `DL GREEN/UL GREEN`, storage `ok`, runtime `ok`, alerts `idle f=0 c=0`
    - `steering`: `SPECTRUM_GOOD / GREEN`, storage `ok`, runtime `ok`, alerts `disabled f=0 c=0`

## Notes
- ATT and Spectrum are now parity-aligned on the compact autorate summary contract even though their absolute rates differ in production.
- Steering uses a different row shape because it summarizes steering state rather than per-WAN shaping state, but it still uses the same bounded status vocabulary (`ok`/`warning`/`degraded`, storage/runtime status, alert summary) expected by the helper and by future canary automation.
- Live captures and helper output were written under `/tmp/phase169-live/` during the gate and can be reused for Phase 170 canary design.
