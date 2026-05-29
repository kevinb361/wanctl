# Phase 213 Signal Sheet

Run dir: `.planning/phases/214-measurement-collapse-investigation/evidence/RUN-20260528T150507Z`

## Buckets

### upload_ceiling_setpoint: clear

No upload ceiling peg detected.

```json
[]
```

### download_recovery_lag: clear

No download recovery lag threshold exceeded.

```json
[
  {
    "cake_dl_peak_delay_us_p99": 9622.0,
    "test": "tcp_12down",
    "time_to_green_after_red_sec": 0.0,
    "wan": "spectrum"
  }
]
```

### measurement_collapse: clear

No measurement-collapse threshold crossed.

```json
[
  {
    "flent_median": 0.0,
    "flent_p99": 0.0,
    "signal_outlier_rate_max": 0.933,
    "test": "tcp_12down",
    "wan": "spectrum"
  }
]
```

### steering_drift: clear

No raw steering transition or counter delta observed.

```json
[
  {
    "cake_read_failures_delta": 0.0,
    "good_count_delta": 0.0,
    "green_rtt_ms": null,
    "green_samples_required": null,
    "pre_post_state_transition": "present -> present",
    "red_count_delta": 0.0,
    "red_rtt_ms": null,
    "red_samples_required": null,
    "test": "tcp_12down",
    "wan": "spectrum",
    "yellow_rtt_ms": null
  }
]
```

### refractory_semantics: FLAGGED

Refractory/backlog suppression activity observed during test windows.

```json
[
  {
    "backlog_suppressed_delta": 18928.0,
    "pct_samples_refractory_active": 0.0,
    "test": "tcp_12down",
    "wan": "spectrum"
  }
]
```

### external_isp: clear

No external-ISP AND-gate crossed.

```json
[
  {
    "curl_ttfb_p99_ms": 0.0,
    "flent_throughput_drop_pct_vs_plan": 0.0,
    "signal_outlier_rate_max": 0.933,
    "test": "tcp_12down",
    "wan": "spectrum"
  }
]
```

## Recommended Next Phase

Primary: Phase 216
Runners-up: [214, 215]
Primary bucket: refractory_semantics
