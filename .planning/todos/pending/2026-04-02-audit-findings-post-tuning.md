---
title: Post-tuning audit findings (2026-04-02)
area: operations
priority: high
created: 2026-04-02
---

# Post-Tuning Session Audit Findings

Discovered during expert audit after 23-RRUL A/B tuning sweep + Phase 125 execution.

## CRITICAL — Fixed

- [x] **Deploy v1.25 code to production** — Done. All 3 services now v1.25.0.
- [x] **A/B test UL factor_down (0.85 vs 0.90)** — 0.85 confirmed (UL needs aggressive RED decay).
- [x] **A/B test UL step_up_mbps (1 vs 2)** — 1 confirmed (2 overshoots on constrained upstream).
- [x] **Restart steering to v1.25 code** — Done. Was v1.23.0, now v1.25.0.

## HIGH — Address Soon

- [ ] **Investigate CAKE rtt parameter** — All qdiscs use rtt 100ms but baseline is 22ms. CAKE docs say use actual RTT. May explain tcp_12down 9.3s tail spikes. Test rtt 50ms vs 100ms.
- [ ] **metrics.db growth** — 359MB and growing. Review retention config, confirm hourly downsample is working.

## MEDIUM — Monitor

- [ ] **Fusion correlation on Spectrum** — Healer immediately suspended after re-enable. Check if transient (startup) or persistent (path divergence).
- [ ] **Recovery timer + NIC tuning interaction** — Verify Wants= + RemainAfterExit works correctly during recovery restarts.
