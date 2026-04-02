# Phase 128: UL Parameter Sweep - Context

**Gathered:** 2026-04-02
**Status:** Ready for planning

<domain>
## Phase Boundary

A/B test all 3 upload parameters sequentially on linux-cake transport using RRUL flent methodology. Each winner applied before the next test. Document results alongside DL results.

Parameters (in test order):
1. factor_down: 0.85 vs 0.90
2. step_up_mbps: 1 vs 2
3. green_required: 3 vs 5

Current production UL values: factor_down=0.85, step_up_mbps=1, green_required=3

</domain>

<decisions>
## Implementation Decisions

All methodology decisions inherited from Phase 127 (DL Parameter Sweep):

### Test methodology (from Phase 127)
- **D-01:** RRUL flent against Dallas netperf server (104.200.21.31), 60s test duration
- **D-02:** YAML edit + SIGUSR1 on cake-shaper VM for config changes
- **D-03:** 1 run per value, re-test if delta <5%. Sequential and cumulative.
- **D-04:** Run ASAP, document time of day with each result
- **D-05:** Document results in docs/CABLE_TUNING.md alongside DL results

### UL-specific context
- **D-06:** UL on DOCSIS is asymmetric — much lower bandwidth (~38 Mbps vs 940 Mbps DL). UL params may need different tuning than DL (confirmed in original REST sweep: UL factor_down=0.85 while DL was 0.90).
- **D-07:** UL config section is under `upload:` in spectrum.yaml, separate from `download:`
- **D-08:** DL params from Phase 127 are already applied (6 changed). UL tests run with the new DL config active.

### Claude's Discretion
- Exact YAML keys for UL params (verify actual key names in config)
- Whether to run a UL-specific baseline or use the Phase 127 baseline

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Prior phase results
- `.planning/phases/127-dl-parameter-sweep/127-DL-RESULTS.md` — DL sweep results, methodology reference
- `.planning/phases/127-dl-parameter-sweep/127-CONTEXT.md` — Full methodology decisions

### Tuning reference
- `docs/CABLE_TUNING.md` — Existing A/B results including new linux-cake DL section
- `docs/CONFIG_SCHEMA.md` — Configuration reference for upload parameters

### Memory
- `feedback_ul_params_validated.md` — UL factor_down=0.85 and step_up=1 confirmed on REST — UL needs different tuning than DL on DOCSIS

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `scripts/check-tuning-gate.sh` — Gate check (run before testing)
- Phase 127 established the full SSH + sed + SIGUSR1 + flent workflow

### Established Patterns
- SSH: `ssh kevin@10.10.110.223`
- Config: `sudo sed -i 's/old/new/' /etc/wanctl/spectrum.yaml`
- Reload: `sudo kill -USR1 $(pgrep -f 'autorate_continuous.*spectrum')`
- Test: `flent rrul_be -H 104.200.21.31 -l 60 -t 'label'`

### Integration Points
- UL config under `upload:` section in spectrum.yaml
- Results append to docs/CABLE_TUNING.md linux-cake section

</code_context>

<specifics>
## Specific Ideas

- Only 3 params = ~6-8 flent runs (3 two-way tests + possible re-tests)
- ~10-15 minutes of active testing
- UL throughput on Spectrum is ~38 Mbps — much smaller than DL, so parameter effects may be more pronounced or more noisy

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 128-ul-parameter-sweep*
*Context gathered: 2026-04-02*
