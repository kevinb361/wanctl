# Phase 247: fping Shadow Capture + Phase 245 Evidence Review - Context

**Gathered:** 2026-06-19
**Status:** Ready for planning

<domain>
## Phase Boundary

Run fping in shadow/read-only mode alongside the live icmplib backend on Spectrum, capturing raw RTT samples and cycle p99 timing using the real wanctl FpingMeasurement code path. Simultaneously re-examine the Phase 245 AB-03 threshold methodology to determine whether `rollback_trigger` was driven by genuine fping latency issues or by threshold calibration mismatch. No production config changes, no control-loop mutation.

</domain>

<decisions>
## Implementation Decisions

### Shadow Mechanism

- **D-01:** Shadow capture is **script-based standalone** — a profiling script runs on cake-shaper without any daemon code changes. No touches to `autorate_continuous.py`, `rtt_backend_factory.py`, or any controller-path file. SAFE-18 holds trivially.
- **D-02:** The script **imports `FpingMeasurement` directly** from `src/wanctl/fping_measurement.py` and reads `configs/spectrum.yaml` to obtain the live reflector list, `source_ip`, and cadence. This ensures the shadow fping runs the exact same code path production would use — not a diverged raw-fping subprocess call.
- **D-03:** Shadow samples are logged to an NDJSON file (one JSON object per sample, timestamped) on cake-shaper's filesystem. No DB writes in shadow mode.

### AB-03 Methodology Review

- **D-04:** The goal is **diagnosis** — read the Phase 245 pre-committed threshold JSON and verdict evidence files, compare fping's measured values against each AB-03 dimension's pass/fail bound, and determine: was `rollback_trigger` caused by genuine fping RTT inferiority, or by threshold calibration mismatch (e.g., thresholds designed around icmplib's continuous-EWMA shape, not fping's burst-sampling shape)?
- **D-05:** Diagnosis output is a standalone artifact: **`247-METHODOLOGY-REVIEW.md`** — one row per AB-03 dimension (threshold, Phase 245 measured value, margin, diagnosis). This feeds Phase 248's distribution analysis directly and is the authoritative record of the methodology finding.

### Capture Scope

- **D-06:** **Spectrum only** — Phase 245 ran on Spectrum; profiling the same WAN produces directly comparable data. ATT is DSL (different RTT characteristics) and would muddy the comparison.
- **D-07:** Capture window: **overnight soak ≈12h**. Enough to span idle + peak traffic patterns without delaying Phase 248. Matches soak discipline used in prior evidence phases.

### Folded Todos

- **`evaluate-fping-as-wanctl-rtt-measurement-backend`** (2026-06-04, `resolves_phase: 247`): Original scoping todo for evaluating fping as a wanctl backend. v1.53 built and shipped the backend; this phase provides the profiling evidence the todo originally asked for. Todo closes when Phase 247 + 248 are complete.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase 245 Evidence (AB-03 methodology review source)
- `.planning/milestones/v1.53-ROADMAP.md` §Phase 245 — Phase 245 goal, AB-03 requirements, and success criteria
- `.planning/milestones/v1.53-REQUIREMENTS.md` — AB-01, AB-02, AB-03 requirement definitions
- `.planning/milestones/v1.53-MILESTONE-AUDIT.md` — audit findings and FPING-PROFILE-01 deferred item

### v1.54 Requirements
- `.planning/REQUIREMENTS.md` — PROF-01, PROF-02, SAFE-18 definitions for this phase

### RTT Backend Seam
- `src/wanctl/rtt_backend.py` — `RttBackend` Protocol and `RttSample` dataclass
- `src/wanctl/fping_measurement.py` — `FpingMeasurement`, `FpingThread`, `FpingParseResult`
- `src/wanctl/rtt_backend_factory.py` — factory construction (scope note: fping feeds background thread only; icmplib owns controller_measurement)

### Config Reference
- `configs/spectrum.yaml` — live Spectrum config with reflectors, source_ip, measurement.backend, cadence settings

### Test Patterns
- `tests/steering/test_steering_metrics_recording.py` — SimpleNamespace-based test pattern (reference for Phase 249, not this phase)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `FpingMeasurement` / `FpingThread` (`src/wanctl/fping_measurement.py`): The shadow script imports and instantiates this directly. Reads configs/spectrum.yaml for source IP + reflectors + cadence. No changes needed.
- `RttSample` (`src/wanctl/rtt_backend.py`): The dataclass returned by `FpingThread.get_latest()` — use this as the logging unit in the NDJSON output.

### Established Patterns
- Phase 245 AB-03 threshold JSON: pre-committed at `.planning/phases/245-*/` — locate the threshold file and verdict JSON for D-04 methodology review.
- NDJSON soak capture pattern: established in Phase 219 (`scripts/phase219_ingestion_digest.py`) — atomic write, timestamped, one object per line.

### Integration Points
- Shadow script runs standalone on cake-shaper; no systemd unit, no DB writes, no controller interaction.
- `FpingThread.get_latest()` returns `RttSample | None` — poll on the same cadence as the live config.
- `FpingThread.get_profile_stats()` exists and returns profiling data directly — check if this already captures p99.

</code_context>

<specifics>
## Specific Ideas

- Check `FpingThread.get_profile_stats()` — if it already computes p99, the shadow script can use it directly rather than computing from raw samples.
- The Phase 245 threshold JSON files live under `.planning/phases/245-live-a-b-rollback-anchor/` — the planner should locate the exact pre-committed threshold artifact and verdict JSON from that directory.

</specifics>

<deferred>
## Deferred Ideas

- Replacement AB-03 threshold methodology (new design from scratch) — Phase 248 scope, after shadow data is in hand.
- ATT shadow capture — deferred; ATT is DSL and would muddy Spectrum comparison.
- 24h full soak — not needed for Phase 247; 12h overnight is sufficient.

</deferred>

---

*Phase: 247-fping-shadow-capture-phase-245-evidence-review*
*Context gathered: 2026-06-19*
