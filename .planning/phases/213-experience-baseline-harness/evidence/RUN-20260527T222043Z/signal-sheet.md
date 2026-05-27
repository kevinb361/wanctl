# Phase 213 Signal Sheet

Run dir: `.planning/phases/213-experience-baseline-harness/evidence/RUN-20260527T222043Z`

## Buckets

### upload_ceiling_setpoint: FLAGGED

Upload samples pegged near configured per-WAN ceiling.

```json
[
  {
    "pct_samples_at_ceiling": 0.9886,
    "sample_count": 176,
    "test": "tcp_upload",
    "upload_ceiling_mbps": 18.0,
    "wan": "att"
  },
  {
    "pct_samples_at_ceiling": 0.8146,
    "sample_count": 178,
    "test": "tcp_upload",
    "upload_ceiling_mbps": 18.0,
    "wan": "spectrum"
  }
]
```

### download_recovery_lag: clear

No download recovery lag threshold exceeded.

```json
[
  {
    "cake_dl_peak_delay_us_p99": 140.0,
    "test": "tcp_12down",
    "time_to_green_after_red_sec": 0.0,
    "wan": "att"
  },
  {
    "cake_dl_peak_delay_us_p99": 127.0,
    "test": "rrul",
    "time_to_green_after_red_sec": 0.0,
    "wan": "att"
  },
  {
    "cake_dl_peak_delay_us_p99": 95.0,
    "test": "tcp_12down",
    "time_to_green_after_red_sec": 0.0,
    "wan": "spectrum"
  },
  {
    "cake_dl_peak_delay_us_p99": 30.0,
    "test": "rrul",
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
    "signal_outlier_rate_max": 0.667,
    "test": "tcp_12down",
    "wan": "att"
  },
  {
    "flent_median": 0.0,
    "flent_p99": 0.0,
    "signal_outlier_rate_max": 0.733,
    "test": "browse",
    "wan": "att"
  },
  {
    "flent_median": 0.0,
    "flent_p99": 0.0,
    "signal_outlier_rate_max": 0.667,
    "test": "tcp_download",
    "wan": "att"
  },
  {
    "flent_median": 0.0,
    "flent_p99": 0.0,
    "signal_outlier_rate_max": 0.733,
    "test": "tcp_upload",
    "wan": "att"
  },
  {
    "flent_median": 0.0,
    "flent_p99": 0.0,
    "signal_outlier_rate_max": 0.867,
    "test": "rrul",
    "wan": "att"
  },
  {
    "flent_median": 0.0,
    "flent_p99": 0.0,
    "signal_outlier_rate_max": 0.667,
    "test": "tcp_12down",
    "wan": "spectrum"
  },
  {
    "flent_median": 0.0,
    "flent_p99": 0.0,
    "signal_outlier_rate_max": 0.867,
    "test": "browse",
    "wan": "spectrum"
  },
  {
    "flent_median": 0.0,
    "flent_p99": 0.0,
    "signal_outlier_rate_max": 0.8,
    "test": "tcp_download",
    "wan": "spectrum"
  },
  {
    "flent_median": 0.0,
    "flent_p99": 0.0,
    "signal_outlier_rate_max": 0.933,
    "test": "tcp_upload",
    "wan": "spectrum"
  },
  {
    "flent_median": 0.0,
    "flent_p99": 0.0,
    "signal_outlier_rate_max": 0.867,
    "test": "rrul",
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
    "wan": "att",
    "yellow_rtt_ms": null
  },
  {
    "cake_read_failures_delta": 0.0,
    "good_count_delta": 0.0,
    "green_rtt_ms": null,
    "green_samples_required": null,
    "pre_post_state_transition": "present -> present",
    "red_count_delta": 0.0,
    "red_rtt_ms": null,
    "red_samples_required": null,
    "test": "browse",
    "wan": "att",
    "yellow_rtt_ms": null
  },
  {
    "cake_read_failures_delta": 0.0,
    "good_count_delta": 0.0,
    "green_rtt_ms": null,
    "green_samples_required": null,
    "pre_post_state_transition": "present -> present",
    "red_count_delta": 0.0,
    "red_rtt_ms": null,
    "red_samples_required": null,
    "test": "tcp_download",
    "wan": "att",
    "yellow_rtt_ms": null
  },
  {
    "cake_read_failures_delta": 0.0,
    "good_count_delta": 0.0,
    "green_rtt_ms": null,
    "green_samples_required": null,
    "pre_post_state_transition": "present -> present",
    "red_count_delta": 0.0,
    "red_rtt_ms": null,
    "red_samples_required": null,
    "test": "tcp_upload",
    "wan": "att",
    "yellow_rtt_ms": null
  },
  {
    "cake_read_failures_delta": 0.0,
    "good_count_delta": 0.0,
    "green_rtt_ms": null,
    "green_samples_required": null,
    "pre_post_state_transition": "present -> present",
    "red_count_delta": 0.0,
    "red_rtt_ms": null,
    "red_samples_required": null,
    "test": "rrul",
    "wan": "att",
    "yellow_rtt_ms": null
  },
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
  },
  {
    "cake_read_failures_delta": 0.0,
    "good_count_delta": 0.0,
    "green_rtt_ms": null,
    "green_samples_required": null,
    "pre_post_state_transition": "present -> present",
    "red_count_delta": 0.0,
    "red_rtt_ms": null,
    "red_samples_required": null,
    "test": "browse",
    "wan": "spectrum",
    "yellow_rtt_ms": null
  },
  {
    "cake_read_failures_delta": 0.0,
    "good_count_delta": 0.0,
    "green_rtt_ms": null,
    "green_samples_required": null,
    "pre_post_state_transition": "present -> present",
    "red_count_delta": 0.0,
    "red_rtt_ms": null,
    "red_samples_required": null,
    "test": "tcp_download",
    "wan": "spectrum",
    "yellow_rtt_ms": null
  },
  {
    "cake_read_failures_delta": 0.0,
    "good_count_delta": 0.0,
    "green_rtt_ms": null,
    "green_samples_required": null,
    "pre_post_state_transition": "present -> present",
    "red_count_delta": 0.0,
    "red_rtt_ms": null,
    "red_samples_required": null,
    "test": "tcp_upload",
    "wan": "spectrum",
    "yellow_rtt_ms": null
  },
  {
    "cake_read_failures_delta": 0.0,
    "good_count_delta": 0.0,
    "green_rtt_ms": null,
    "green_samples_required": null,
    "pre_post_state_transition": "present -> present",
    "red_count_delta": 0.0,
    "red_rtt_ms": null,
    "red_samples_required": null,
    "test": "rrul",
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
    "backlog_suppressed_delta": 14451.0,
    "pct_samples_refractory_active": 0.0,
    "test": "tcp_12down",
    "wan": "att"
  },
  {
    "backlog_suppressed_delta": 14451.0,
    "pct_samples_refractory_active": 0.0,
    "test": "browse",
    "wan": "att"
  },
  {
    "backlog_suppressed_delta": 14451.0,
    "pct_samples_refractory_active": 0.0,
    "test": "tcp_download",
    "wan": "att"
  },
  {
    "backlog_suppressed_delta": 14451.0,
    "pct_samples_refractory_active": 0.0,
    "test": "tcp_upload",
    "wan": "att"
  },
  {
    "backlog_suppressed_delta": 14451.0,
    "pct_samples_refractory_active": 0.0,
    "test": "rrul",
    "wan": "att"
  },
  {
    "backlog_suppressed_delta": 14451.0,
    "pct_samples_refractory_active": 0.0,
    "test": "tcp_12down",
    "wan": "spectrum"
  },
  {
    "backlog_suppressed_delta": 13097.0,
    "pct_samples_refractory_active": 0.0,
    "test": "browse",
    "wan": "spectrum"
  },
  {
    "backlog_suppressed_delta": 14003.0,
    "pct_samples_refractory_active": 0.0,
    "test": "tcp_download",
    "wan": "spectrum"
  },
  {
    "backlog_suppressed_delta": 13487.0,
    "pct_samples_refractory_active": 0.0,
    "test": "tcp_upload",
    "wan": "spectrum"
  },
  {
    "backlog_suppressed_delta": 14451.0,
    "pct_samples_refractory_active": 0.0,
    "test": "rrul",
    "wan": "spectrum"
  }
]
```

### external_isp: clear

No external-ISP AND-gate crossed.

```json
[
  {
    "curl_ttfb_p99_ms": 414.863,
    "flent_throughput_drop_pct_vs_plan": 0.0,
    "signal_outlier_rate_max": 0.667,
    "test": "tcp_12down",
    "wan": "att"
  },
  {
    "curl_ttfb_p99_ms": 414.863,
    "flent_throughput_drop_pct_vs_plan": 0.0,
    "signal_outlier_rate_max": 0.733,
    "test": "browse",
    "wan": "att"
  },
  {
    "curl_ttfb_p99_ms": 414.863,
    "flent_throughput_drop_pct_vs_plan": 0.0,
    "signal_outlier_rate_max": 0.667,
    "test": "tcp_download",
    "wan": "att"
  },
  {
    "curl_ttfb_p99_ms": 414.863,
    "flent_throughput_drop_pct_vs_plan": 0.0,
    "signal_outlier_rate_max": 0.733,
    "test": "tcp_upload",
    "wan": "att"
  },
  {
    "curl_ttfb_p99_ms": 414.863,
    "flent_throughput_drop_pct_vs_plan": 0.0,
    "signal_outlier_rate_max": 0.867,
    "test": "rrul",
    "wan": "att"
  },
  {
    "curl_ttfb_p99_ms": 332.557,
    "flent_throughput_drop_pct_vs_plan": 0.0,
    "signal_outlier_rate_max": 0.667,
    "test": "tcp_12down",
    "wan": "spectrum"
  },
  {
    "curl_ttfb_p99_ms": 332.557,
    "flent_throughput_drop_pct_vs_plan": 0.0,
    "signal_outlier_rate_max": 0.867,
    "test": "browse",
    "wan": "spectrum"
  },
  {
    "curl_ttfb_p99_ms": 332.557,
    "flent_throughput_drop_pct_vs_plan": 0.0,
    "signal_outlier_rate_max": 0.8,
    "test": "tcp_download",
    "wan": "spectrum"
  },
  {
    "curl_ttfb_p99_ms": 332.557,
    "flent_throughput_drop_pct_vs_plan": 0.0,
    "signal_outlier_rate_max": 0.933,
    "test": "tcp_upload",
    "wan": "spectrum"
  },
  {
    "curl_ttfb_p99_ms": 332.557,
    "flent_throughput_drop_pct_vs_plan": 0.0,
    "signal_outlier_rate_max": 0.867,
    "test": "rrul",
    "wan": "spectrum"
  }
]
```

## Recommended Next Phase

Primary: Phase 215
Runners-up: [216, 214]
Primary bucket: upload_ceiling_setpoint
