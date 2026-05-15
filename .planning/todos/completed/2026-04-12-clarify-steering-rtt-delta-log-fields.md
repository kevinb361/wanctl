---
created: 2026-04-12T14:35:23.510Z
title: Clarify steering RTT delta log fields
area: performance
files:
  - src/wanctl/steering/cake_stats.py:41
  - src/wanctl/steering/daemon.py:1492
  - src/wanctl/steering/daemon.py:1671
  - src/wanctl/steering/congestion_assessment.py:61
---

## Problem

Live production review on `cake-shaper` surfaced misleading steering log lines such as `rtt=0.0ms ewma=15.3ms ... [YELLOW]`. This looked like a possible measurement bug or fallback artifact, but code inspection shows the log field labeled `rtt=` is actually `CongestionSignals.rtt_delta`, not the raw measured RTT.

`CongestionSignals.__str__()` formats `rtt={self.rtt_delta:.1f}ms`, and `rtt_delta` is computed as `current_rtt - baseline_rtt` with a floor of `0.0`. The YELLOW decision path uses `rtt_delta_ewma`, not the instantaneous delta, so `rtt=0.0ms` can legitimately appear at the same time as `ewma=15.3ms` and `YELLOW` while the smoothed warning state decays.

Operationally, this is a real observability problem. The current log wording is easy to misread as a literal zero-millisecond RTT sample, which sends investigation effort in the wrong direction during production incidents.

## Solution

Make the steering log/output semantics explicit so operators can distinguish raw RTT from RTT delta and smoothed delta.

Focus areas:
- Rename the `rtt=` field in steering congestion logs to `delta=` or `rtt_delta=`.
- Review nearby steering log messages for the same ambiguity and keep terminology consistent.
- Preserve health payload compatibility unless there is a deliberate contract change.
- Add or update tests around the affected string formatting so the clarified field names do not regress.

This should stay scoped to observability and naming. It should not change congestion thresholds, smoothing behavior, or steering decisions.

## Resolution — FIXED 2026-04-14

The misleading steering congestion label was corrected in production and in the repo.

- `src/wanctl/steering/cake_stats.py` now formats congestion summaries with `delta=` instead of `rtt=`.
- `tests/steering/test_cake_stats.py` was updated to lock the clarified wording in place.
- `steering.service` was restarted and live logs now show the corrected field name during degradation events.

This closed the operator confusion that surfaced during live RRUL investigation without changing congestion logic or thresholds.
