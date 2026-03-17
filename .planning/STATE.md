---
gsd_state_version: 1.0
milestone: v1.18
milestone_name: Measurement Quality
status: completed
last_updated: "2026-03-17T12:35:24.776Z"
last_activity: 2026-03-17 -- Completed 92-02-PLAN.md (signal quality + IRTT metrics persistence to SQLite)
progress:
  total_phases: 5
  completed_phases: 5
  total_plans: 10
  completed_plans: 10
  percent: 100
---

# Session State

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-16)

**Core value:** Sub-second congestion detection with 50ms control loops
**Current focus:** v1.18 Measurement Quality -- Phase 92 in progress (Observability)

## Position

**Milestone:** v1.18 Measurement Quality
**Phase:** 92 of 92 (Observability)
**Plan:** 2 of 2 complete
**Status:** v1.18 milestone complete
**Last activity:** 2026-03-17 -- Completed 92-02-PLAN.md (signal quality + IRTT metrics persistence to SQLite)

Progress: [##########] 100%

## Performance Metrics

**Velocity:**

- Total plans completed: 8
- Average duration: 15min
- Total execution time: 1.9 hours

**By Phase:**

| Phase        | Plans | Total   | Avg/Plan |
| ------------ | ----- | ------- | -------- |
| 88           | 2     | 47min   | 24min    |
| Phase 89 P01 | 3min  | 1 tasks | 2 files  |
| Phase 89 P02 | 13min | 2 tasks | 5 files  |
| Phase 90 P01 | 11min | 2 tasks | 6 files  |
| Phase 90 P02 | 19min | 1 tasks | 3 files  |
| Phase 91 P01 | 10min | 1 tasks | 3 files  |
| Phase 91 P02 | 24min | 2 tasks | 1 files  |
| Phase 92 P01 | 6min  | 1 tasks | 2 files  |
| Phase 92 P02 | 24min | 2 tasks | 4 files  |

## Accumulated Context

### Key Decisions

- Hampel warm-up is window_size cycles (check before append), MAD=0 guard skips detection on identical windows
- typing.Any used for config dict (mypy-clean); from **future** import annotations for forward refs
- All signal processing ships in observation mode (metrics/logs only, no congestion control changes) -- v1.19+ adds fusion
- IRTT runs in background thread on 5-10s cadence, never in 50ms hot loop (subprocess overhead incompatible)
- Signal processing config always active (no enable/disable flag), warn+default on invalid values, optional YAML section
- All inline mock configs in test files must have signal_processing_config dict when WANController is constructed
- Zero new Python dependencies -- all signal processing uses stdlib (statistics, collections.deque, math)
- One new system binary: irtt via apt on production containers
- Container networking audit may close with report only if overhead < 0.5ms
- Dual-signal fusion explicitly deferred to v1.19+ (needs production data from both signals)
- Cache shutil.which('irtt') at init time -- binary availability is immutable for process lifetime
- Try JSON parsing even on non-zero IRTT exit code (Pitfall 4: 100% loss returns non-zero but JSON may be valid)
- Verified IRTT JSON field paths: upstream_loss_percent/downstream_loss_percent (not send_call.lost/receive_call.lost)
- IRTT config follows identical warn+default pattern as signal_processing and alerting config loaders
- IRTT disabled by default; requires both enabled: true and server to activate
- IRTTThread uses lock-free caching via frozen dataclass pointer swap (GIL-atomic), no threading.Lock needed
- IRTTThread daemon=True so thread dies with process, shutdown_event.wait(timeout=cadence_sec) for interruptible sleep
- cadence_sec validated as number >= 1, default 10, warn+default pattern (consistent with other IRTT config fields)
- Protocol correlation thresholds: ratio > 1.5 (ICMP deprioritized) or < 0.67 (UDP deprioritized)
- Stale IRTT results (>3x cadence) skip correlation, set \_irtt_correlation to None
- IRTT thread stopped at step 0.5 in finally block (after state save, before lock cleanup)
- Autouse \_mock_irtt_thread fixture needed in entry point tests when irtt binary installed on dev machine
- Subprocess ping (not icmplib) for host-to-container measurement -- icmplib requires root/sysctl on host
- scripts/**init**.py added to make scripts/ importable for testing
- WAN jitter reference values hardcoded (0.5ms idle for both WANs) -- conservative estimates from production data
- Container audit PASS: cake-spectrum mean=0.171ms, cake-att mean=0.166ms -- both well below 0.5ms threshold
- Container jitter NEGLIGIBLE: 9.2% and 9.6% of WAN idle jitter -- no measurement infrastructure changes needed
- veth/bridge networking adds no meaningful noise to RTT measurements (confirmed with 10,000 real samples)
- Signal quality health section uses optional pattern (omitted when \_last_signal_result is None)
- IRTT health section always present with available flag + reason (disabled/binary_not_found/awaiting_first_measurement)
- All mock WAN controllers need explicit None for \_last_signal_result, \_irtt_thread, \_irtt_correlation to prevent MagicMock truthy issues
- All mock configs need irtt_config dict for health endpoint tests
- Signal quality metrics written every cycle (same cadence as existing RTT metrics); IRTT deduplicated via monotonic timestamp
- IRTT \_last_irtt_write_ts tracks last-written monotonic timestamp; prevents 200x duplication at 20Hz
- STORED_METRICS now 18 entries total (10 original + 4 signal + 4 IRTT)

### Known Issues

- IRTT JSON field paths verified from man pages (upstream_loss_percent, downstream_loss_percent, ipdv_round_trip) -- live verification still needed during container install
- LXC container veth/bridge config format needs investigation during Phase 91
- Hampel filter default sigma=3.0/window=7 is conservative; may need per-WAN tuning

### Blockers

None.

### Pending Todos

5 todos in `.planning/todos/pending/`:

- Research IRTT as RTT measurement alternative (general) -- addressed by v1.18
- Integration test for router communication (testing) -- low priority
- Narrow layout truncates WAN panel content (dashboard/ui) -- low priority
- Investigate LXC container network optimizations (infrastructure) -- addressed by Phase 91
- Audit CAKE qdisc configuration for Spectrum and ATT links (networking) -- completed in v1.17
