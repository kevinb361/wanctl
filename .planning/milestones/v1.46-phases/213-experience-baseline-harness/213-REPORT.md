# Phase 213 Final Operator Report: Experience Baseline Harness

Phase 213 completed the evidence-only baseline harness and one real production evidence run. The run generated dev-VM-originated traffic only, preserved the no-mutation boundary, and serialized the WAN suites: Spectrum completed first, then ATT.

## Summary

| Requirement | Coverage note | Verdict | Evidence path | Downstream impact |
|---|---|---|---|---|
| BASE-01 | Runbook, orchestrator, and live run capture normal browsing, upload, download, RRUL, and `tcp_12down`. | Covered | `docs/RUNBOOKS/baseline.md`, `evidence/RUN-20260527T222043Z/manifest.json`, `evidence/RUN-20260527T222043Z/signal-sheet.md` | Phase 215 can cite real serialized baseline evidence before upload reclaim. |
| BASE-02 | Each test window captured paired `/health` NDJSON, alert windows, steering pre/post redacted snapshots, manifests, and browse/flent artifacts. | Covered | `evidence/RUN-20260527T222043Z/spectrum/tcp_upload/health-spectrum.ndjson`, `evidence/RUN-20260527T222043Z/att/tcp_upload/health-att.ndjson` | Later phases can inspect aligned windows without re-running the baseline. |
| BASE-03 | Signal sheet classified six buckets and recommended a single next phase with runners-up. | Covered | `evidence/RUN-20260527T222043Z/signal-sheet.json`, `evidence/RUN-20260527T222043Z/signal-sheet.md` | Proceed first to Phase 215, with Phase 216 then Phase 214 as runners-up. |

Run `RUN-20260527T222043Z` started at `2026-05-27T22:20:43+00:00` and ended at `2026-05-27T22:36:45+00:00`. The manifest records `bind_map.spectrum=10.10.110.226`, `bind_map.att=10.10.110.233`, Spectrum egress `70.123.224.169`, ATT egress `99.126.115.47`, netperf host `dallas`, and 10 ordered tests: all five Spectrum windows followed by all five ATT windows.

## Per-Bucket Verdict

### 1. Upload ceiling / setpoint — FLAGGED

The upload ceiling/setpoint bucket is flagged. The signal sheet reports ATT upload samples pegged near configured ceiling for `98.86%` of `176` samples and Spectrum upload samples pegged for `81.46%` of `178` samples during `tcp_upload`.

- Evidence row: `evidence/RUN-20260527T222043Z/signal-sheet.md` lines 7-28 (`upload_ceiling_setpoint: FLAGGED`).
- Supporting paths: `evidence/RUN-20260527T222043Z/spectrum/tcp_upload/health-spectrum.ndjson`, `evidence/RUN-20260527T222043Z/att/tcp_upload/health-att.ndjson`.
- Ceiling source: `configs/spectrum.yaml upload.ceiling_mbps` and `configs/att.yaml upload.ceiling_mbps`, consumed as per-WAN config facts rather than link-specific arithmetic.

Operator verdict: the baseline points first at the upload operating point axis. Spectrum's `18 Mbps` upload ceiling remains intentional current config from Phase 212, not drift, but the live baseline shows enough ceiling-pegged behavior to justify the planned one-knob reclaim phase.

### 2. Download recovery lag — NOT FLAGGED

The download recovery lag bucket is clear. The signal sheet reports `time_to_green_after_red_sec=0.0` for RRUL and `tcp_12down` on both WANs, with low CAKE download peak delay p99 values: ATT `140.0` / `127.0` us and Spectrum `95.0` / `30.0` us.

- Evidence row: `evidence/RUN-20260527T222043Z/signal-sheet.md` lines 30-61 (`download_recovery_lag: clear`).
- Supporting paths: `evidence/RUN-20260527T222043Z/spectrum/rrul/health-spectrum.ndjson`, `evidence/RUN-20260527T222043Z/spectrum/tcp_12down/health-spectrum.ndjson`, `evidence/RUN-20260527T222043Z/att/rrul/health-att.ndjson`.

Operator verdict: no baseline evidence says download recovery lag should precede upload reclaim. Phase 214 still owns the folded bad-p99 investigation, but this single baseline run did not make it the primary next step.

### 3. Measurement collapse — NOT FLAGGED FOR NEXT-PHASE PRIORITY

The classifier marked measurement collapse clear despite high `signal_outlier_rate_max` rows during several windows. The emitted rows show `flent_p99=0.0` and `flent_median=0.0` for classifier latency fields while outlier-rate values reached `0.933` on Spectrum `tcp_upload` and `0.867` on several ATT/Spectrum windows.

- Evidence row: `evidence/RUN-20260527T222043Z/signal-sheet.md` lines 63-140 (`measurement_collapse: clear`).
- Supporting paths: `evidence/RUN-20260527T222043Z/spectrum/tcp_upload/health-spectrum.ndjson`, `evidence/RUN-20260527T222043Z/att/rrul/health-att.ndjson`.

Operator verdict: preserve this as a runner-up concern, not the primary. Phase 214 remains the correct bounded investigation for bad `tcp_12down` p99 while GREEN, especially because flent emitted repeated netperf reset/no-valid-data warnings during `tcp_12down`; however, the Phase 213 bucket recommendation is upload-first.

### 4. Steering drift — NOT FLAGGED

The steering drift bucket is clear in the raw counter/state terms allowed by D-14. Every row reports `pre_post_state_transition="present -> present"`, `good_count_delta=0.0`, `red_count_delta=0.0`, and `cake_read_failures_delta=0.0`.

- Evidence row: `evidence/RUN-20260527T222043Z/signal-sheet.md` lines 142-279 (`steering_drift: clear`).
- Supporting paths: `evidence/RUN-20260527T222043Z/spectrum/browse/steering-pre-state.redacted.json`, `evidence/RUN-20260527T222043Z/spectrum/browse/steering-post-state.redacted.json`, `evidence/RUN-20260527T222043Z/att/rrul/steering-post-state.redacted.json`.

Operator verdict: no raw transition/counter evidence makes steering drift the primary cause bucket. This report does not compare any v1.39 threshold-name fields to v1.45 repo semantics; Phase 216 must still carry the version/threshold drift constraint from Phase 212.

### 5. Refractory semantics — FLAGGED AS RUNNER-UP

The refractory semantics bucket is flagged. The signal sheet reports backlog suppression deltas across all windows: ATT consistently `14451.0`, Spectrum ranging from `13097.0` to `14451.0`, while `pct_samples_refractory_active=0.0`.

- Evidence row: `evidence/RUN-20260527T222043Z/signal-sheet.md` lines 281-348 (`refractory_semantics: FLAGGED`).
- Supporting paths: `evidence/RUN-20260527T222043Z/spectrum/tcp_download/health-spectrum.ndjson`, `evidence/RUN-20260527T222043Z/spectrum/tcp_upload/health-spectrum.ndjson`, `evidence/RUN-20260527T222043Z/att/tcp_download/health-att.ndjson`.

Operator verdict: this deserves the first runner-up slot because suppression counters moved materially while refractory-active sample percentage stayed zero. It is not selected as primary because the upload ceiling evidence is more direct and Phase 215 already has Snapshot A / one-knob discipline for a safe first canary.

### 6. External ISP conditions — NOT FLAGGED

The external ISP bucket is clear. Curl TTFB p99 stayed below the `2000 ms` threshold (`332.557 ms` Spectrum and `414.863 ms` ATT), and flent throughput drop versus plan is recorded as `0.0` in all rows despite high outlier-rate observations.

- Evidence row: `evidence/RUN-20260527T222043Z/signal-sheet.md` lines 350-426 (`external_isp: clear`).
- Supporting paths: `evidence/RUN-20260527T222043Z/spectrum/browse/browse.curl.csv`, `evidence/RUN-20260527T222043Z/att/browse/browse.curl.csv`.

Operator verdict: do not pivot to ISP/path blame from this baseline. The evidence does not cross the external-ISP AND-gate.

## Recommended Next Phase

**Primary: Phase 215 — Spectrum Upload Reclaim Canary.** The strongest direct signal is upload ceiling/setpoint: Spectrum hit the configured `18 Mbps` upload ceiling for `81.46%` of Spectrum `tcp_upload` samples, and Phase 212 already established Spectrum's `floor=8`, `setpoint=12`, `ceiling=18`, DOCSIS mode active state as intentional current config.

**Runner-up 1: Phase 216 — Recovery/Refractory Decision.** Refractory/backlog suppression was flagged in every test window, with Spectrum deltas up to `14451.0`. That deserves follow-up after upload canary evidence unless Phase 215 immediately regresses or rejects tuning.

**Runner-up 2: Phase 214 — Measurement Collapse Investigation.** Measurement collapse was not flagged as the primary bucket, and download recovery lag was clear. Still, high outlier-rate rows and netperf reset/no-valid-data warnings during `tcp_12down` mean the folded bad-p99 investigation remains valid if upload reclaim does not explain operator experience.

## Downstream Constraints

- Phase 215 must treat Spectrum `setpoint_mbps=12` and `ceiling_mbps=18` as intentional current config, not drift, and use Snapshot A rollback plus one-knob canary discipline before any production mutation.
- Phase 216 must not interpret v1.39-shaped steering threshold names as v1.45 semantics until operator-approved alignment resolves Phase 212 steering drift.
- Phase 214 must preserve the daemon-health versus user-experience distinction: `/health.status=healthy` and GREEN remain daemon-state only.
- The run order is serialized Spectrum-first then ATT; downstream comparisons must not describe the evidence as concurrent dual-WAN loading.
- Phase 212 inventory facts remain the authoritative live-state baseline for endpoints, versions, service identity, and steering drift constraints.

## Run Metadata

| Field | Value |
|---|---|
| RUN | `RUN-20260527T222043Z` |
| Started / ended | `2026-05-27T22:20:43+00:00` / `2026-05-27T22:36:45+00:00` |
| Serialized order | `spectrum` suite, then `att` suite |
| bind_map | `{"spectrum":"10.10.110.226","att":"10.10.110.233"}` |
| Observed egress | Spectrum `70.123.224.169`; ATT `99.126.115.47` |
| netperf_host | `dallas` |
| flent_version | `Starting Flent 2.1.1 using Python 3.12.3.` |
| host_dev_vm | `dev` |
| wanctl_version_spectrum_runtime | `offline-fixture` in manifest; Phase 212 live inventory says Spectrum runtime `1.45.0` |
| wanctl_version_att_runtime | `offline-fixture` in manifest; Phase 212 live inventory says ATT runtime `1.45.0` |
| wanctl_version_steering_runtime | `offline-fixture` in manifest; Phase 212 live inventory says steering runtime `1.39.0` |
| signal sheet JSON | `evidence/RUN-20260527T222043Z/signal-sheet.json` |
| signal sheet Markdown | `evidence/RUN-20260527T222043Z/signal-sheet.md` |
| Artifact count | 136 files under `evidence/RUN-20260527T222043Z/` |

## Safety And Redaction Closeout

| Check | Result | Evidence path | Notes |
|---|---|---|---|
| No raw steering state under evidence | PASS | `evidence/RUN-20260527T222043Z/` | `find ... -name "*.raw.json"` returned empty. |
| D-08 key-pattern scan | PASS | `evidence/RUN-20260527T222043Z/**/*.redacted.json` and staged evidence | No unredacted secret-bearing key/value hits. |
| Poller cleanup | PASS | process table after run | `pgrep -af '[p]hase213-health-poller'` returned empty. |
| Mutation boundary | PASS | command log + report scope | No restarts, deploys, RouterOS writes, steering toggles, or production config writes. |

Phase 213 complete; next phase: 215 per operator verdict; runners-up: 216, 214.
