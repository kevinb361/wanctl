---
gsd_state_version: 1.0
milestone: none
milestone_name: between_milestones
status: between_milestones
stopped_at: none
last_updated: "2026-07-05T15:05:00-05:00"
last_activity: "v1.60 shipped — all items proven, ROADMAP archived"
---

## v1.60 Shipped 2026-07-05

Three work items completed, 5/5 PROVEN in TRACEABILITY.md:

1. **SEED-007 (Storage hygiene):** wanctl_state fire-on-change — 95% row reduction verified live (`31e82d8d`).
2. **SEED-006 (Silicom bypass):** Phase B completed, 7 scenarios + orchestrator deployed (`acaaeadd`).
3. **steering-degraded-on-clean-restart:** Phase 224 fix verified via live restart — SPECTRUM_GOOD immediately (`dccca17b`).

Decision record: `decisions/2702-saga-mode-for-ops-work.md`

### Deferred

- UL rate soak (floor 30, ceiling 36 Mbps) — completed 2026-07-08. Floor 30 Mbps: clean upload latency (median 14.2ms, 95th 18.2ms), adaptive pullback during DOCSIS congestion (8-18 Mbps observed). Ceiling 36 Mbps: untested (actual demand ~22 Mbps < floor), leaving as-is (90% of 40 Mbps circuit). No changes needed.

### Key State

- 6 routes managed, guard ok, 0 conflicts
- Both failover bridges armed
- Steering daemon: healthy, SPECTRUM_GOOD
- Spectrum UL: floor 30 Mbps, ceiling 36 Mbps (soak complete — no changes)
- cake-autorate active rate controller (since 2026-07-05)
- State-bridge downsampling: raw→1m every 15 min (commit `5c410373`)
