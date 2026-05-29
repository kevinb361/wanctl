# Phase 215: Spectrum Upload Reclaim Canary - Context

**Gathered:** 2026-05-29
**Status:** Ready for planning

<domain>
## Phase Boundary

A controlled, one-knob production canary on Spectrum's **upload** operating point to test
whether the conservative latency-first cap is leaving usable upstream throughput unclaimed.

Current Spectrum upload config (`configs/spectrum.yaml` `continuous_monitoring.upload`):
`floor_mbps: 8`, `setpoint_mbps: 12`, `ceiling_mbps: 18`, `step_up_mbps: 5`, `docsis_mode: true`.
Plan upstream is 40 Mbps (disclosure checked 2026-05-20).

This phase delivers exactly one of:
- A canary that raises a single upload knob, measures against the Phase 213 baseline behind
  explicit success/rollback gates with Snapshot A revert, and either keeps the change (win) or
  rolls back cleanly (lose) — both with evidence; or
- An explicit, evidenced decision NOT to tune (valid RECLAIM-02 outcome).

**Out of scope:** download-side tuning, the control-model itself (DOCSIS mode stays), steering,
ATT, multi-knob sweeps, and any second canary cycle (one knob per cycle — a follow-up cycle is
its own decision).

</domain>

<decisions>
## Implementation Decisions

### Knob & Direction (RECLAIM-02)
- **D-01:** The canary moves exactly one knob: `ceiling_mbps: 18 → 20`. `setpoint_mbps`,
  `floor_mbps`, `step_up_mbps`, and all other parameters stay frozen.
- **D-02:** Setpoint was deliberately rejected as the lever. The Phase 213 baseline shows
  Spectrum upload pegged near `ceiling_mbps: 18` for 81.46% of samples under `tcp_upload` —
  the controller already operates above setpoint 12 and stays healthy, so the **ceiling is the
  binding constraint** and a setpoint raise (12→14) would be a near-no-op / false pass.
- **D-03:** Magnitude is +2 (→20), not +4 (→22), because `step_up_mbps` is 5 and +2 is the
  smallest controlled probe — it bounds first-cycle latency exposure and cleanly tests
  "was 18 over-conservative?". A raise to 22 is deferred to a possible follow-up cycle only if
  20 passes (see Deferred Ideas).

### Success Gate — WIN condition (RECLAIM-03)
- **D-04:** Throughput reclaim. Sustained upload throughput under `tcp_upload` must improve by a
  meaningful margin vs the Phase 213 baseline — target most of the +2 raise realized
  (≈ median upload up ≥ ~1.5 Mbps). Latency is NOT part of the win condition (it is the rollback
  gate) — do not double-count it.

### Rollback Gate — LOSE condition + Snapshot A (RECLAIM-02/03)
- **D-05:** Strict / latency-first gate. Roll back if ANY of:
  - loaded upload p95/p99 (`tcp_upload` window) exceeds the Phase 213 baseline by **>10%**, OR
  - any sustained excursion above `warn_bloat_ms` (75 ms), OR
  - floor-hit cycles **> 0** (prior canary `20260504T231334Z` held 0 across an 18-cycle RED burst), OR
  - alert flapping beyond Spectrum's cooldown-bounded rate (`cooldown_sec: 600`, ≈ ≤3 firings/event).
  Rationale: 18 was chosen specifically as the p95/p99 winner; ceiling=20 only sticks if it costs
  almost no latency, so a "pass" is trustworthy and marginal regressions revert.
- **D-06:** Snapshot A reuses the Phase 211 canary pattern: capture current `configs/spectrum.yaml`
  (ceiling=18) + state file + `/health` baseline before mutation. Revert = restore config →
  `scripts/deploy.sh spectrum cake-shaper` → restart `wanctl@spectrum.service` → verify the bound
  health endpoint (`http://10.10.110.223:9101/health`) returns the reverted config/version.

### Measurement + Phase 214 Confounder
- **D-07:** Primary instrument is the Phase 213 harness (`scripts/phase213-baseline-capture.sh` →
  `tcp_upload` + paired `/health` NDJSON) for apples-to-apples windows against the baseline.
- **D-08:** Latency percentiles come from the Phase 214 **fail-closed extractor**
  (`scripts/phase214-extract.py`, raw `Ping (ms) ICMP` as source of truth — no zero-fill).
- **D-09:** **VOID-on-collapse rule:** if a measurement window shows collapse (high
  `signal_outlier_rate` / `measurement_state=collapsed` — Phase 213 saw 0.933 on Spectrum
  `tcp_upload`), that window is VOID and re-run, never scored pass/fail.
- **D-10:** A/B method: run ceiling 18 → 20 **back-to-back in the same session** to control for
  Phase 214's documented time-of-day and target/path sensitivity.
- **D-11:** `scripts/libreqos-cli.mjs` runs as **non-gating** perceived-quality corroboration only.
  Its own noise floor is not yet baselined against a 213-style run, so it does not enter pass/fail.

### Claude's Discretion
- **D-01/D-03 (knob + magnitude)** and **D-05 (rollback gate strictness)** were both "you decide" —
  resolved to ceiling 18→20 and strict/latency-first per the rationale above. The operator approves
  the final mutation at deploy time (Snapshot A + gates make it reversible).
- Exact baseline-freshness mechanics (reuse `RUN-20260527T222043Z` vs capture a fresh ceiling-18
  baseline in the same A/B session), observation-window duration for floor-hit/alert accumulation,
  and time-of-day window selection are left to research/planning, guided by D-10.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Knob source of truth & control model
- `configs/spectrum.yaml` — `continuous_monitoring.upload` block (lines ~74-108): the live
  upload knobs, the "keep 12/18 until a fresh sweep proves better / fallback drop setpoint to 10"
  note, and DOCSIS-mode congestion-control parameters being canaried.
- `docs/BRIDGE_QOS.md` — DOCSIS/DSCP/wash topology decisions that constrain Spectrum shaping.

### Baseline comparison (what the canary measures against)
- `.planning/phases/213-experience-baseline-harness/213-REPORT.md` — per-bucket verdict;
  "Upload ceiling / setpoint — FLAGGED" is the justification for this phase.
- `.planning/phases/213-experience-baseline-harness/evidence/RUN-20260527T222043Z/` — the
  serialized baseline run (signal-sheet, `tcp_upload` `/health` NDJSON, manifest).
- `scripts/phase213-baseline-capture.sh` — the capture harness to reuse for the canary A/B.
- `docs/RUNBOOKS/baseline.md` — baseline runbook.

### Phase 214 confounder + fail-closed measurement
- `.planning/phases/214-measurement-collapse-investigation/214-REPORT.md` — `ambiguous` verdict,
  `reflector_loss` driver, target/path sensitivity still live for Phase 215+.
- `.planning/phases/214-measurement-collapse-investigation/evidence/matrix-summary.json` — canonical matrix.
- `scripts/phase214-extract.py` — fail-closed flent latency extractor (VOID-on-collapse source of truth).
- `scripts/phase214-align.py`, `scripts/phase214-flent-matrix.sh`, `scripts/phase214-matrix-summary.py`.

### Canary / gate / deploy precedents
- `scripts/canary-check.sh`, `scripts/phase200-saturation-canary.sh`, `scripts/phase201-predeploy-gate.sh` —
  existing canary + predeploy-gate patterns.
- `scripts/deploy.sh`, `scripts/validate-deployment.sh` — deploy + Snapshot A revert path.
- `scripts/libreqos-cli.mjs` — supplementary (non-gating) perceived-quality probe.

### Requirements & safety posture
- `.planning/REQUIREMENTS.md` — RECLAIM-01/02/03 (lines ~40-42).
- `.planning/STATE.md` — v1.46 safety posture (no tuning before baseline+gates; one knob per canary;
  GREEN/healthy ≠ good UX) and Phase 211 canary deploy/Snapshot-A decisions.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `scripts/phase213-baseline-capture.sh`: produces the exact `tcp_upload` + `/health` windows the
  canary compares against — reuse for both A (18) and B (20) legs.
- `scripts/phase214-extract.py`: fail-closed percentile extraction; gives the VOID-on-collapse guard.
- Phase 211 deploy sequence (`scripts/deploy.sh` + service restart + bound-endpoint verify) is the
  proven Snapshot-A / mutation / revert mechanism.

### Established Patterns
- One knob per production canary (v1.46 invariant); Snapshot A before any mutation.
- Health endpoint binds to the Spectrum IP (`10.10.110.223:9101`), not loopback (per Phase 211).
- `scripts/deploy.sh` copies code but does NOT restart the daemon — an explicit
  `wanctl@spectrum.service` restart is required for the new config to take effect.

### Integration Points
- Only `configs/spectrum.yaml` `upload.ceiling_mbps` changes (18→20). No `src/wanctl/` edits —
  this is a parameter tune, not a control-model change.

</code_context>

<specifics>
## Specific Ideas

- The config comment pre-declares the conservative fallback as `setpoint → 10`; this phase moves
  the *ceiling* up instead, so that fallback is not the revert path here — Snapshot A (restore 18) is.
- 18 was set by the 2026-04-29 latency-first gaming-server soak as the stopped-controller p95/p99
  winner; the canary's job is to test whether that cap was over-conservative, not to relitigate the
  control model.

</specifics>

<deferred>
## Deferred Ideas

- **ceiling_mbps → 22 follow-up cycle** — only if 18→20 passes cleanly. One knob per cycle, so a
  second raise is its own canary decision in a later phase/cycle, not this one.
- **Baseline libreqos-cli.mjs's own noise floor** against a 213-style run so it could become a
  gating signal in a future phase.
- **setpoint reclaim** — ruled out for this phase by the pegged-at-ceiling evidence; could revisit
  if a future regime is setpoint-bound rather than ceiling-bound.

### Reviewed Todos (not folded)
- `2026-04-24-resolve-att-cake-primary-canary-after-phase-196.md` — matched on canary/gate keywords
  but is a different concern (ATT cake-primary control-model canary, gated on Phase 191/196 closure),
  not Spectrum upload-parameter reclaim. Stays deferred.

</deferred>

---

*Phase: 215-spectrum-upload-reclaim-canary*
*Context gathered: 2026-05-29*
