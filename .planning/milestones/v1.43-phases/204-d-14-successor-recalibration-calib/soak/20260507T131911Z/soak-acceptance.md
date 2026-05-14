# CALIB-01 Soak Acceptance

timestamp: 2026-05-08T13:19:28Z
soak_ts: 20260507T131911Z
decision: accepted_with_documented_deviation
operator_response: "Do it. Accept the completed CALIB-01 soak without extending."

## Capture Quality

| Check | Result |
|------|--------|
| Remote capture | `/var/tmp/wanctl-soak-20260507T131911Z/soak-capture.ndjson` |
| Local capture | `.planning/phases/204-d-14-successor-recalibration-calib/soak/20260507T131911Z/soak-capture.ndjson` |
| First sample | `2026-05-07T13:19:29+00:00` |
| Last sample | `2026-05-08T13:19:28+00:00` |
| Elapsed inclusive seconds | `86400` |
| Line count | `84098` |
| Plan line-count proxy | `>= 86000` |
| Coverage vs elapsed seconds | `97.335648%` |
| Parse errors | `0` |
| Minute buckets present | `1441` |
| Missing minute buckets | `0` |
| Completed-window value changes | `1343` |
| Floor-hit delta | `0` |

## Deviation

The capture missed the plan's strict line-count proxy by `1902` samples:

```text
84098 < 86000
```

This is accepted as a documented deviation rather than extending the soak because
the stronger evidence-quality checks passed:

- Full contiguous 24h wall-clock window (`86400` inclusive seconds).
- Zero parse errors.
- Zero missing minute buckets.
- `97.335648%` sample coverage against elapsed seconds.
- `1343` completed-window value changes, enough for the CALIB-01 distribution.
- Floor-hit delta stayed `0`.
- Operator explicitly requested not to create a non-contiguous extension window.

## Distribution Block

From `soak-summary.json::suppressions_completed_window_count_distribution`:

```json
{
  "by_cause": {
    "backlog_recovery": {
      "max": 77,
      "mean": 25.322580645161292,
      "p50": 20.0,
      "p95": 58.849999999999994,
      "p99": 75.77,
      "window_count": 124
    },
    "dwell_hold": {
      "max": 119,
      "mean": 11.408888888888889,
      "p50": 6.0,
      "p95": 41.0,
      "p99": 70.25999999999999,
      "window_count": 675
    },
    "other": {
      "max": 0,
      "mean": 0.0,
      "p50": 0.0,
      "p95": 0.0,
      "p99": 0.0,
      "window_count": 0
    }
  },
  "max": 119,
  "mean": 14.63527653213752,
  "p50": 8.0,
  "p95": 55.0,
  "p99": 82.0,
  "window_count": 669
}
```

## Plan 204-03 Hand-Off

Plan 204-03 should use these CALIB-01 reference values for the operator threshold
session:

- Top-level `p99`: `82.0`
- `dwell_hold.p99`: `70.25999999999999`
- `backlog_recovery.p99`: `75.77`
- Top-level `max`: `119`
- Top-level `window_count`: `669`
