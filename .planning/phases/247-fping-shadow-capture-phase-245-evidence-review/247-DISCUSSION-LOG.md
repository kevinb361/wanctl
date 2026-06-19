# Phase 247 Discussion Log

**Date:** 2026-06-19
**Areas discussed:** Shadow mechanism, AB-03 review method, Capture scope

---

## Area 1: Shadow Mechanism

**Q:** How should fping run in shadow alongside icmplib on production?
**Options:** Script-based standalone / Daemon sidecar config flag
**Selected:** Script-based standalone
**Notes:** Zero daemon code changes; SAFE-18 holds trivially.

**Q:** What should the shadow script reuse from the codebase?
**Options:** Import FpingMeasurement directly / Raw fping subprocess
**Selected:** Import FpingMeasurement directly
**Notes:** Uses exact same code path as production; reads configs/spectrum.yaml for reflectors + source_ip + cadence.

---

## Area 2: AB-03 Review Method

**Q:** Goal of re-examining Phase 245 AB-03 thresholds?
**Options:** Diagnose latency vs calibration / Produce replacement methodology
**Selected:** Diagnose latency vs calibration
**Notes:** Read Phase 245 pre-committed threshold JSON + verdict evidence. Determine if rollback_trigger was fping latency or threshold calibration mismatch (e.g., thresholds tuned for icmplib EWMA shape vs fping burst-sampling shape).

**Q:** Where does the diagnosis document land?
**Options:** 247-METHODOLOGY-REVIEW.md / Inline in summary
**Selected:** 247-METHODOLOGY-REVIEW.md
**Notes:** Standalone artifact: one row per AB-03 dimension (threshold, measured value, margin, diagnosis). Feeds Phase 248 directly.

---

## Area 3: Capture Scope

**Q:** Which WANs for shadow capture?
**Options:** Spectrum only / Both Spectrum + ATT
**Selected:** Spectrum only
**Notes:** Phase 245 ran on Spectrum; comparable data. ATT is DSL with different RTT characteristics — would muddy the comparison.

**Q:** Capture window duration?
**Options:** Overnight ~12h / 24h full soak / Short ~2h
**Selected:** Overnight soak ≈12h
**Notes:** Spans idle + peak patterns without blocking Phase 248. Matches prior evidence-phase soak discipline.

---

## Claude's Discretion

- Output format for shadow NDJSON (field names, timestamp format) — follow Phase 219 pattern
- Polling interval for `FpingThread.get_latest()` in script — match live config cadence

## Deferred Ideas

- Replacement AB-03 methodology (new design) → Phase 248
- ATT shadow capture → future if needed
