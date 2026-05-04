# Requirements: wanctl Active Milestones

**Core Value:** Sub-second congestion detection with 50ms control loops, achieved through systematic performance optimization and code quality improvements while maintaining production reliability.

**Active Milestones:**
- **v1.41 Per-Direction Control Surfaces** — current active work (defined 2026-05-03)
- **v1.39 Control-Path Timing & Measurement Accounting** — in closure; Phase 191 ATT weather-rerun + Phase 192 closeout soak remain

**Recently Archived:** v1.40 Queue-Primary Signal Arbitration (shipped 2026-05-03 — see `.planning/milestones/v1.40-REQUIREMENTS.md`).

---

## v1.41 Requirements (defined 2026-05-03)

### Signal Arbitration (ARB)

- [x] **ARB-05**: When `continuous_monitoring.upload.target_bloat_ms` and/or `continuous_monitoring.upload.warn_bloat_ms` are present in the deployment YAML, the legacy 3-state UL distress classifier consumes those values as the UL RTT bloat thresholds independent of the DL 4-state thresholds. When the keys are absent, UL falls back to the DL globals byte-identically (preserves all non-Spectrum deployments). Per-key explicit-presence flags gate live-tuning writes (`_apply_threshold_param` cannot silently overwrite UL thresholds when an operator pushes a global tuning update).

### Control Safety (SAFE)

- [x] **SAFE-06**: The autorate config validator rejects (or emits an audible WARNING log entry on every startup) any unknown `continuous_monitoring.*` key. Silent-ignore is forbidden. This closes the v1.40-era gap where `/etc/wanctl/spectrum.yaml` carried 4 unrecognized keys for 3 days without a single warning, leaving production half-shipped.

### Verification (VALN)

- [ ] **VALN-06**: Spectrum UL saturation gate — a 10–15 min `iperf3 -P4` saturated upload loop at the deployed UL ceiling does not collapse to the UL floor in any cycle. Verified pre/post idle baselines bookend the run. This is the deploy-gate acceptance test; it must pass before the binary is promoted to `/opt/wanctl`. A 24-hour Spectrum regression soak runs after as a watchdog, not as the verdict. **Blocked in Phase 200 gap closure:** Plan 200-14 Attempt 3 canary repaired the baseline bookends and improved from 122 to 4 UL floor hits, but still failed the zero-floor-hit gate; D-10 rollback used `/opt/wanctl-prephase200-gap-20260504T132936Z.tar.gz` and the soak was skipped fail-closed. See `200-VERIFICATION.md`. **Operator-escalated 2026-05-04: deferred to Phase 201 (`docsis-aware-ul-congestion-control`) as an inherited blocking requirement** because Phase 200's per-direction-thresholds hypothesis was diagnosed insufficient by its own RETRO; the residual failure regime is shaping-headroom dominated, not threshold dominated. Phase 201 SPEC and PLAN must carry VALN-06 forward; it cannot be silently dropped during 201 scoping. See `200-RETRO.md` Final Closure section and `201-CONTEXT.md` Inherited Requirements block.

### Documentation (DOCS)

- [x] **DOCS-03**: `CHANGELOG.md` and `docs/CONFIGURATION.md` document the new optional UL threshold keys (`continuous_monitoring.upload.target_bloat_ms`, `continuous_monitoring.upload.warn_bloat_ms`) and explicitly note that SIGUSR1 does **not** reload these keys — a service restart is required after changing them. Verified against `wan_controller.py` SIGUSR1 reload scope (lines ~1894–1899: dwell/deadband only).

### v1.41 Out of Scope

| Feature | Reason |
|---------|--------|
| Per-direction DL state-machine threshold split | DL is healthy; v1.41 is UL-only. DL stays governed by the v1.40 4-state path. |
| New `/health` per-direction telemetry block | UL behavior is already observable via the existing `/health` upload state and CAKE peak-delay surfaces. Adding a new block would be premature. |
| Refactoring `initialize_cake` complexity (C901 noqa) | Control-path refactor risk under "stability > safety > clarity" rule. The function is correct; the `noqa: C901` was the right call in v1.40 cleanup. |
| Coverage push back over 90% | Pre-existing v1.40 debt at 89.64%. v1.41's new tests will likely cross 90% naturally; if they don't, that's a separate cleanup phase. |
| ATT cake-primary canary (VALN-05b) | Inherited cross-milestone deferral from v1.40. Still gated on v1.39 Phase 191 closure. Tracks `.planning/todos/pending/2026-04-24-resolve-att-cake-primary-canary-after-phase-196.md`. |

---

## v1.39 Requirements

### Control-Path Timing (TIME)

- [ ] **TIME-01**: Operators can observe, on the live health endpoint or in production logs, the concurrency overlap between `cake_stats_thread` tc-dump calls and `netlink_cake` tc-change apply calls, including per-call timestamps and elapsed time.
- [ ] **TIME-02**: The `cake_stats_thread` poll cadence is configurable via YAML at daemon start without requiring code changes, with a documented default that preserves current behavior until A/B evidence justifies a change.
- [ ] **TIME-03**: Cycle overrun count per hour, measured over a 24-hour window on both Spectrum and ATT, is strictly lower than the v1.38.0 baseline established in the 2026-04-20 production audit.
- [ ] **TIME-04**: `write_download_ms` and `write_upload_ms` p99 values logged in "Slow CAKE apply" warnings, measured over a 24-hour window, are strictly lower than the v1.38.0 baseline on both WANs.

### Measurement Accounting (MEAS)

- [ ] **MEAS-05**: When a background RTT cycle has zero successful reflectors (all-host blackout), the reflector scorer does not decrement per-host quality scores for any reflector in that cycle.
- [ ] **MEAS-06**: Reflector scores during prolonged carrier ICMP blackout episodes stop sinking to the 0.8 deprioritize threshold for path-wide failures, verified by health-endpoint reflector score trends on Spectrum over a 24-hour window.

### Operational Log Hygiene (OPER)

- [ ] **OPER-02**: "Protocol deprioritization detected" INFO log entries are rate-limited or demoted when fusion is in `disabled` or `healer_suspended` state, reducing Spectrum's 2.5k/day baseline volume while preserving the first occurrence and any state-transition events.

### Control Safety (SAFE)

- [x] **SAFE-03**: No control threshold, EWMA alpha, dwell-cycle count, deadband value, burst detection parameter, or state-machine rule is modified during v1.39. Any PR touching those files is rejected.
- [ ] **SAFE-04**: Immediate rate-decrease latency from congestion detection to `tc change` issuance is not increased by any timing change introduced in this milestone.

### Verification (VALN)

- [x] **VALN-02**: Each timing or scorer change is A/B-compared against the v1.38.0 baseline using at least one RRUL, one tcp_12down, and one VoIP flent run before shipping, with results captured in the phase VERIFICATION.md.
- [ ] **VALN-03**: A 24-hour production soak after merge confirms that TIME-03, TIME-04, and MEAS-06 hold, and that no regression appears in dwell-bypass responsiveness, burst detection trigger count, or fusion state transitions.

## Out of Scope

| Feature | Reason |
|---------|--------|
| Changing any control threshold (state machine, EWMA, dwell, deadband, burst) | Locked per SAFE-03 — this milestone is timing and accounting, not algorithm tuning |
| Re-enabling fusion on Spectrum or ATT | Fusion stays suspended; any change requires separate analysis |
| Steering daemon work | Steering is disabled in production; cycle overruns there are non-operational |
| Asymmetry gate work | ATT asymmetry is stable and characteristic of the link |
| Adding a 4th reflector | Deferred — fix scorer accounting first; 4th reflector only reconsidered if MEAS-06 proves insufficient |
| Atomic DL+UL netlink write batching | High risk, unclear API support, would add latency to rate decreases |
| User-space RTNL lock around netlink calls | Would serialize reads and writes, can delay rate-decrease path |

## Traceability

### v1.39

| Requirement | Phase | Status |
|-------------|-------|--------|
| TIME-01 | Phase 191 | Pending |
| TIME-02 | Phase 191 | Pending |
| TIME-03 | Phase 191 (+ VALN-03 soak) | Pending |
| TIME-04 | Phase 191 (+ VALN-03 soak) | Pending |
| MEAS-05 | Phase 192 | Pending |
| MEAS-06 | Phase 192 (+ VALN-03 soak) | Pending |
| OPER-02 | Phase 192 | Pending |
| SAFE-03 | Phase 191 + Phase 192 (enforced throughout) | Complete |
| SAFE-04 | Phase 191 | Pending |
| VALN-02 | Phase 191 + Phase 192 | Complete |
| VALN-03 | Phase 192 closeout soak | Pending |

### v1.41

| Requirement | Phase | Status |
|-------------|-------|--------|
| ARB-05  | Phase 200 | Satisfied (`200-VERIFICATION.md`) |
| SAFE-06 | Phase 200 | Satisfied (`200-VERIFICATION.md`) |
| VALN-06 | Phase 200 (deferred to Phase 201) | Deferred -> Phase 201 (inherited blocking requirement) (`200-VERIFICATION.md` closure: deferred-to-phase-201; `200-RETRO.md` Final Closure 2026-05-04; `201-CONTEXT.md` Inherited Requirements; `canary/20260504T133207Z/verdict.json`). Plan 200-14 Attempt 3 canary improved 122 -> 4 UL floor hits but did not reach zero; operator escalated to DOCSIS-aware control (Phase 201) rather than running a second Phase 200 gap-closure cycle. **Inherited as blocking requirement; Phase 201 SPEC and PLAN must carry VALN-06 forward — cannot be silently dropped during 201 scoping.** |
| DOCS-03 | Phase 200 | Satisfied (`200-VERIFICATION.md`) |

---
*v1.39 requirements defined: 2026-04-20*
*v1.40 archived: 2026-05-03 (see `.planning/milestones/v1.40-REQUIREMENTS.md`)*
*v1.41 requirements defined: 2026-05-03*
