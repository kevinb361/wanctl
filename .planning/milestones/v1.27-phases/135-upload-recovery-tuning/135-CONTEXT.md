# Phase 135: Upload Recovery Tuning - Context

**Gathered:** 2026-04-03
**Status:** Ready for planning

<domain>
## Phase Boundary

A/B test UL step_up_mbps and factor_down on linux-cake transport via RRUL flent for faster recovery under bidirectional load. Deploy winning parameters. No code changes — config tuning only.

</domain>

<decisions>
## Implementation Decisions

### Parameters to Test
- **D-01:** Test UL step_up_mbps and factor_down only. green_required=3 is already lower than DL's 5 and not suspected as the bottleneck. Testing 2 params keeps the matrix manageable.

### Candidate Values
- **D-02:** step_up_mbps candidates: 3, 4, 5 (current: 2). DL uses 15 on 940Mbps (1.6% of ceiling). For UL at 38Mbps, step_up=5 would be 13% of ceiling — proportionally aggressive.
- **D-03:** factor_down candidates: 0.80, 0.90 (current: 0.85). Test one step in each direction. DL validated at 0.90 (gentler decay). Total matrix: 3 step_up x 2 factor_down = 6 configs.

### Test Methodology
- **D-04:** 60s RRUL flent, 3 runs per config. Same proven v1.26 methodology: `flent rrul -H 104.200.21.31 -l 60`. Compare median/p99 latency + UL throughput sum. 6 configs x 3 runs = 18 flent runs.
- **D-05:** Apply parameter changes via SIGUSR1 hot-reload between tests (no restart needed). Record config state before each run.
- **D-06:** Run flent from dev machine (10.10.110.226), not from cake-shaper VM.

### Success Threshold
- **D-07:** A parameter change is "worth it" if it produces 15%+ UL throughput improvement OR 20%+ latency improvement over current baseline (step_up=2, factor_down=0.85). If neither metric improves by threshold, keep current params.

### Claude's Discretion
- Order of parameter testing (step_up sweep first vs factor_down first, or interleaved)
- Whether to include a current-params baseline run in the test matrix (recommended)
- Analysis document format and comparison tables
- Whether to also capture DL metrics as regression check during UL-focused tests

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Current UL Configuration
- `configs/spectrum-vm.yaml` §upload — Current UL params: step_up=2, factor_down=0.85, green_required=3, floor=8, ceiling=38
- `configs/spectrum-vm.yaml` §thresholds — Shared thresholds: target_bloat=9, warn_bloat=60, hard_red=100

### v1.26 Tuning Precedent
- MEMORY feedback_ul_params_validated.md — UL factor_down=0.85 and step_up=1 confirmed on REST transport (pre-linux-cake)
- MEMORY feedback_step_up_15_validated.md — DL step_up=15 methodology (same A/B approach)
- MEMORY project_v126_test_analysis_2026_04_02.md — v1.26 test findings: UL only 3.9 Mbps during RRUL (10% of ceiling)

### Test Infrastructure
- MEMORY reference_netperf_server.md — Netperf/flent server on Dallas (104.200.21.31)
- MEMORY feedback_flent_from_dev_only.md — Always run flent from dev machine, never from cake-shaper VM
- MEMORY feedback_verify_transport_before_tuning.md — Verify transport backend before any tuning

### SIGUSR1 Hot-Reload
- `src/wanctl/autorate_continuous.py` — SIGUSR1 handler reloads YAML config including tuning params

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- SIGUSR1 reload: Change YAML config, send SIGUSR1 to wanctl service, params applied on next cycle. No restart needed.
- `wanctl-check-config`: Validates YAML before applying
- Health endpoint: `/health` shows current params and cycle metrics for verification

### Established Patterns
- v1.26 A/B methodology: change one param, run 3x 60s RRUL, record metrics, compare
- Results documented in `.planning/` analysis document with comparison tables
- MEMORY captures validated params with test dates

### Integration Points
- `configs/spectrum-vm.yaml` — production config file to update with winners
- `systemctl kill -s SIGUSR1 wanctl@spectrum` — hot-reload command
- `flent rrul -H 104.200.21.31 -l 60` — test command from dev machine

</code_context>

<specifics>
## Specific Ideas

- v1.26 showed UL at only 3.9 Mbps sum during RRUL (10% of 38 Mbps ceiling) — this is the baseline to beat
- DOCSIS upload is asymmetric and more sensitive than download — step_up needs to be proportionally smaller than DL
- Current step_up=2 is 5.3% of ceiling — may be too conservative given DL uses 1.6% and works
- factor_down=0.85 means 15% decay per YELLOW cycle — testing 0.80 (20% decay, more aggressive) and 0.90 (10% decay, gentler like DL)

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 135-upload-recovery-tuning*
*Context gathered: 2026-04-03*
