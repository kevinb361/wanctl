# Phase 197 Primary-Signal Audit Predicate

**Purpose:** Phase 197 introduces two new `signal_arbitration.control_decision_reason`
strings (`queue_during_refractory`, `rtt_fallback_during_refractory`) and a new
`signal_arbitration.refractory_active` boolean. The Phase 196 cake-primary B-leg
audit predicate (which produced 153 false-failures in `196-07`) must be updated
to recognize these as queue-primary or regime-aware-RTT-fallback samples instead
of treating any non-queue reason as a verdict failure.

This document is the audit contract for the Phase 197 Spectrum cake-primary
B-leg rerun on `same_deployment_token cake-shaper:wanctl@spectrum.service:/etc/wanctl/spectrum.yaml`.

## Health-sample classification

A sample (one row of `/health` `signal_arbitration`) is classified as:

- `queue_primary` when:
  - `active_primary_signal == "queue"` AND
  - `control_decision_reason ∈ ACCEPT_LIST_QUEUE`
- `queue_primary_refractory_rtt_fallback` when:
  - `control_decision_reason == "rtt_fallback_during_refractory"` AND
  - `refractory_active == true`
  - This is a documented-exception bucket: queue snapshot was unavailable
    (None or cold_start) during the refractory window, so the controller
    correctly fell back to RTT for that single cycle. NOT a verdict failure.
- `non_queue` otherwise.

```jq
ACCEPT_LIST_QUEUE = ["queue_distress", "green_stable", "queue_during_refractory"]

def classify:
  if .active_primary_signal == "queue"
     and (.control_decision_reason | IN($accept_list_queue[]))
  then "queue_primary"
  elif .control_decision_reason == "rtt_fallback_during_refractory"
       and (.refractory_active == true)
  then "queue_primary_refractory_rtt_fallback"
  else "non_queue"
  end ;
```

### Why `green_stable` is in the accept-list

`green_stable` is the queue-path's "no distress detected, but cake_signal is the
primary input" outcome. It is the queue equivalent of `rtt_primary_operating_normally`.
Including it in the accept-list ensures that queue-driven idle cycles count toward
queue-primary coverage. (See Phase 194 PATTERNS §"Stable arbitration vocabulary".)

### Why `rtt_primary_operating_normally`, `rtt_veto`, and `healer_bypass` are NOT in the accept-list

- `rtt_primary_operating_normally`: pre-Phase-194 fallback path (cake_signal not supported); no queue input was consumed.
- `rtt_veto` (Phase 195): queue read GREEN but RTT vetoed; queue was NOT the deciding signal.
- `healer_bypass` (Phase 195): aligned queue+RTT distress for 6 cycles; documents the bypass event but is not the per-cycle queue-primary classification.

These three reasons remain `non_queue` to preserve the original Phase 196 audit
intent: "did queue-primary actually drive arbitration on this cycle?".

## Metric-sample classification

Per-cycle SQLite metric rows are filtered to `granularity = 'raw'` first
(carry-over from `raw-only-primary-signal-audit.json` corrected lineage —
1-minute aggregates of categorical encodings are mathematically nonsensical
and produced 147 of the 153 false-failures in `196-07`).

A raw row classifies as:

- `metric_queue_samples` when `wanctl_arbitration_active_primary == 1.0`.
- `metric_queue_samples_via_refractory_rtt_fallback` when:
  - `wanctl_arbitration_active_primary == 2.0` AND
  - `wanctl_arbitration_refractory_active == 1.0`
- `metric_non_queue_samples` otherwise.

This corresponds to "Option A" in Phase 197 PATTERNS §"Audit-script update":
preserve the regime distinction (queue-primary vs queue-primary-via-fallback)
that `wanctl_arbitration_refractory_active` was added to expose.

## Verdict rules (unchanged from Phase 196 lineage)

- `pass`: zero `non_queue` samples in either health or metric paths.
- `pass_with_documented_exceptions`: `non_queue` samples ≤ a documented threshold,
  with each exception timestamp recorded in `exception_timestamps`.
- `fail`: `non_queue` samples exceed the threshold or include a regime not
  acknowledged in this document.

## Field expectations

The capture script `scripts/phase196-soak-capture.sh` (Phase 197 update) now
emits `refractory_active` alongside the other `signal_arbitration` fields in
the per-sample summary JSON. Pre-Phase-197 controller builds emit
`refractory_active: false` via the jq default.

## Phase 196-07 false-failure context

The original Phase 196-07 audit treated any sample where
`wanctl_arbitration_active_primary != 1.0` as a verdict failure. Of the 153
flagged samples in `soak/cake-primary/primary-signal-audit.json`:

- 147 were 1-minute aggregate rows where the categorical encoding averaged to
  ~1.0008 — fixed in `raw-only-primary-signal-audit.json` by filtering to
  `granularity = 'raw'`.
- 6 were genuine raw RTT samples (`active_primary == 2.0`) during refractory
  windows where the queue snapshot was masked. These are precisely the events
  Phase 197's split-locals fix addresses: under Phase 197 these would emit
  `queue_during_refractory` (with valid snapshot) or
  `rtt_fallback_during_refractory` + `refractory_active=true` (with invalid
  snapshot), both of which are now correctly classified as queue-primary or
  documented-exception buckets — NOT verdict failures.

## Source-bind discipline

`same_deployment_token cake-shaper:wanctl@spectrum.service:/etc/wanctl/spectrum.yaml`
remains mandatory for the Phase 197 rerun (per Phase 196-11 source-bind egress
proof: `10.10.110.226` exits Spectrum, `10.10.110.233` exits AT&T). The
audit document above does not alter this — it inherits the bind from the
Phase 196 lineage.

---

*Phase 197 audit predicate documented: 2026-04-27*
*Implements decision D-09 (Claude's discretion #2: accept-list form chosen over derived prefix predicate).*
