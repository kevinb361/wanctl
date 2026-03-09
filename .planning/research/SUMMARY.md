# Project Research Summary

**Project:** wanctl v1.11 WAN-Aware Steering
**Domain:** Inter-daemon signal fusion for dual-WAN congestion-aware failover
**Researched:** 2026-03-09
**Confidence:** HIGH

## Executive Summary

WAN-aware steering closes a specific observability gap in wanctl's dual-daemon architecture: autorate measures ISP-level congestion via end-to-end RTT (the WAN path) and expresses it as a 4-state zone (GREEN/YELLOW/SOFT_RED/RED), but this signal is computed and discarded each cycle -- never persisted to the state file. Steering currently relies only on CAKE queue stats (local link congestion) and its own independent RTT measurement. When the ISP is congested but local CAKE queues are clean -- because CAKE is doing its job clamping bandwidth to floor -- steering has no reason to act. This is the exact scenario where rerouting latency-sensitive connections to the alternate WAN would help most, and v1.11 addresses it.

The recommended approach requires zero new dependencies and approximately 100 lines of new production code, all in existing files. Autorate extends its state file with a `congestion.dl_state` field (already computed, currently discarded after logging). Steering reads this field from the same file it already opens every cycle for baseline RTT (zero additional I/O), filters it through a lightweight hysteresis gate, and feeds it into the existing `compute_confidence()` additive scoring pipeline. The WAN signal is strictly amplifying: WAN RED (30 points) alone cannot cross the steer threshold (55), requiring corroboration from at least one CAKE-based signal. All existing sustain timers, flap detection, hold-down, and dry-run infrastructure apply automatically.

The primary risks are dirty-tracking regression (adding a volatile field to the state dict could cause 20x write amplification), stale state causing phantom congestion (autorate crash leaves RED in the file indefinitely), and hysteresis stacking (each layer adds delay, potentially making the WAN-amplified path slower than CAKE-only). All three have concrete mitigations: exclude zone from dirty-tracking comparison, enforce a 5-second staleness threshold defaulting to GREEN, and read autorate's zone as-is without adding another hysteresis layer. The feature ships disabled by default (`wan_state.enabled: false`) for safe rollout, following the same pattern used for confidence scoring dry-run.

## Key Findings

### Recommended Stack

No new external libraries, frameworks, or tools are needed. Every primitive required for WAN-aware steering already exists in the codebase. The atomic JSON state file IPC (`state_utils.py:atomic_write_json()`), counter-based hysteresis (three existing pattern instances), additive confidence scoring (`steering_confidence.py:compute_confidence()`), and config schema validation (`config_base.py:validate_schema()`) are all proven patterns with 11 milestones of production validation. See `STACK.md` for full component inventory.

**Core technologies (all existing, reuse as-is):**
- `atomic_write_json()` / `safe_json_load_file()`: inter-daemon state sharing -- proven at 50ms write cadence for 11 milestones
- `compute_confidence()` additive scoring: signal fusion point -- WAN state becomes one more weighted term
- `SteeringConfig` SCHEMA validation: config extension point -- add `wan_state:` section with defaults
- Counter-based streak tracking: hysteresis pattern -- identical to three existing implementations

### Expected Features

See `FEATURES.md` for full analysis including competitor comparison and signal priority model.

**Must have (table stakes):**
- Autorate exports `congestion.dl_state` to state file -- foundation for all WAN awareness
- Steering reads WAN zone from autorate state file (extends BaselineLoader)
- Map autorate 4-state zone to confidence weights (WAN_RED=30, WAN_SOFT_RED=15)
- Sustained WAN RED/GREEN via existing sustain timers -- transient filtering
- CAKE remains primary signal (enforced by weight values: WAN alone < threshold)
- YAML configuration with `wan_state.enabled: false` default
- Graceful degradation when autorate unavailable (None = skip WAN weight)
- Backward compatibility for pre-upgrade state files (`.get()` with defaults)

**Should have (differentiators):**
- SOFT_RED as pre-failure early warning (5-10s ahead of full RED, unique to wanctl)
- Health endpoint exposes WAN awareness state, staleness, confidence contribution
- SQLite metrics for WAN awareness events (post-hoc analysis)
- Startup grace period (ignore WAN signal for first 30s after daemon start)

**Defer (v2+):**
- Upload zone awareness -- download is the authoritative ISP health signal
- RTT delta export in state file -- only if steering needs more granular WAN data
- Asymmetric WAN-specific sustain timers -- only if shared timers prove too coarse

### Architecture Approach

The integration requires exactly 4 changes to the existing architecture: (1) autorate writes its congestion zone to the state file, (2) steering reads that zone from the same file it already reads for baseline RTT, (3) a small hysteresis gate (~60 lines) filters the raw zone before scoring, and (4) `compute_confidence()` gains WAN weight constants. No architectural spine changes. No new IPC mechanisms. No daemon coupling. The unidirectional data flow (autorate publishes, steering reads) is preserved. See `ARCHITECTURE.md` for full data flow diagrams and component inventory.

**Major components:**
1. **State File Extension** (autorate side) -- add `congestion: {dl_state, ul_state}` to existing JSON state dict
2. **AutorateStateLoader** (renamed BaselineLoader) -- single file read returns both baseline_rtt and wan_dl_state
3. **WANStateGate** (~60 lines, inline in daemon.py) -- Schmitt-trigger hysteresis filter for zone stability
4. **Confidence scoring extension** -- `ConfidenceWeights.WAN_RED=30`, `WAN_SOFT_RED=15` in existing `compute_confidence()`

### Critical Pitfalls

See `PITFALLS.md` for full analysis (15 pitfalls total: 5 critical, 6 moderate, 4 minor).

1. **Dirty-tracking write amplification** -- Adding volatile `dl_zone` to state dict triggers 20x more disk writes (every 50ms vs. every 1s). Exclude zone from dirty-tracking comparison or write zone changes only on transitions.
2. **Stale state causing phantom congestion** -- Autorate crash leaves RED in state file. Enforce 5-second staleness threshold; stale state defaults to GREEN (fail-safe).
3. **Signal conflict (CAKE GREEN + WAN RED)** -- WAN RED alone must NOT trigger steering. Enforced by weight values: WAN_RED(30) < steer_threshold(55). Only amplifies existing CAKE signals.
4. **Oscillation amplification** -- Faster degrade path (WAN boosts score) with unchanged recovery creates asymmetry. WAN state should affect only confidence score, not hysteresis counters. Add invariant tests.
5. **Hysteresis stacking** -- Layering WAN hysteresis on top of autorate's already-filtered zone adds delay. Read autorate zone as-is (already filtered by streak counters); avoid adding another sustained-cycle gate on the steering side.

## Implications for Roadmap

Based on research, suggested phase structure (4 core phases + 1 optional):

### Phase 1: State File Extension (Writer Side)
**Rationale:** Every other feature depends on autorate publishing `congestion.dl_state`. This is the single foundation -- a ~15-line change in existing files with zero risk to steering.
**Delivers:** Autorate state file contains congestion zone, backward-compatible, dirty-tracking preserved.
**Addresses:** "Autorate exports dl_state" (P1 table stake), backward compatibility.
**Avoids:** Pitfall 1 (missing zone), Pitfall 2 (dirty-tracking regression), Pitfall 9 (backward compat).

### Phase 2: WAN State Reader + Hysteresis Gate (Reader Side)
**Rationale:** Reader must exist before it can be wired into scoring. WANStateGate is testable in isolation. BaselineLoader rename to AutorateStateLoader eliminates the double-read anti-pattern.
**Delivers:** AutorateStateLoader returns both baseline_rtt and wan_dl_state from single file read. WANStateGate filters zone through configurable hysteresis.
**Addresses:** "Steering reads WAN state" (P1), graceful degradation, staleness detection.
**Avoids:** Pitfall 3 (stale state), Pitfall 6 (hot-loop blocking), Pitfall 11 (SOFT_RED mapping), Pitfall 13 (disabled path).

### Phase 3: Confidence Scoring + Signal Fusion
**Rationale:** Depends on Phase 2 data model (ConfidenceSignals.wan_state field). This is the core logic: WAN zone becomes a weighted additive signal in the existing scoring pipeline.
**Delivers:** WAN_RED and WAN_SOFT_RED confidence weights, signal fusion rules enforcing "CAKE primary, WAN amplifying", recovery eligibility check includes WAN state.
**Addresses:** Confidence weight mapping (P1), sustained degradation/recovery (P1), SOFT_RED early warning (differentiator).
**Avoids:** Pitfall 4 (signal conflict), Pitfall 5 (oscillation amplification), Pitfall 7 (over-engineering third state machine).

### Phase 4: Wiring + Config + Health + Testing
**Rationale:** End-to-end wiring depends on all components existing. Config is the final enablement mechanism. Integration testing validates the full pipeline.
**Delivers:** SteeringDaemon.run_cycle() wired to WAN state, YAML configuration, health endpoint exposure, full signal combination test matrix.
**Addresses:** YAML configuration (P1), health endpoint (P2 differentiator), startup grace period (P2).
**Avoids:** Pitfall 8 (hysteresis stacking -- end-to-end latency test), Pitfall 10 (testing isolation), Pitfall 14 (recovery bounce), Pitfall 15 (config sprawl).

### Phase 5 (Optional): Observability + Metrics
**Rationale:** Only needed once WAN awareness is proven working in production. SQLite metrics enable post-hoc analysis of WAN signal effectiveness.
**Delivers:** SQLite metrics for WAN awareness events, log format updates for WAN state decisions.
**Addresses:** SQLite metrics recording (P2 differentiator).

### Phase Ordering Rationale

- **Writer before reader:** Autorate must publish the zone before steering can consume it. The data dependency is strict. Phase 1 is also completely safe to deploy alone (steering ignores unknown state file keys).
- **Reader before scoring:** The data model (AutorateSnapshot, WANStateGate) must exist before confidence scoring can reference it. Phase 2 is testable in isolation.
- **Scoring before wiring:** Weight constants and fusion logic must be defined before the end-to-end run_cycle integration. Phase 3 has zero behavioral change until Phase 4 wires the wan_state field.
- **Testing alongside wiring:** The signal combination matrix (PITFALLS.md Pitfall 10) must be validated during the wiring phase, not deferred. Phase 4 makes it live, controlled by `wan_state.enabled`.
- **Observability last:** Metrics and health endpoint additions are valuable but not functionally required. They can ship after the core is stable.

### Research Flags

Phases likely needing deeper research during planning:
- **Phase 2 (Reader + Gate):** Dirty-tracking interaction requires profiling. Decision between same-file read vs. separate zone file impacts I/O characteristics. STACK.md recommends same-file (zero additional I/O), PITFALLS.md suggests separate file as alternative to avoid dirty-tracking regression. Resolve during phase planning.
- **Phase 3 (Signal Fusion):** Weight values need scenario modeling. Research files propose slightly different ranges (FEATURES.md: 20-25 for WAN_RED; STACK.md: 30; ARCHITECTURE.md: 30). Settle on exact values during planning and validate with the signal combination test matrix.

Phases with standard patterns (skip research-phase):
- **Phase 1 (State File):** Well-documented existing pattern. Adding a key to a JSON dict with dirty-tracking exclusion is straightforward.
- **Phase 4 (Wiring + Config):** Config schema extension follows established BaseConfig/SCHEMA pattern. Health endpoint extension is a dict addition.
- **Phase 5 (Observability):** MetricsWriter integration follows existing metric recording patterns.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | Zero new dependencies. All from direct codebase analysis of proven patterns. |
| Features | HIGH | Competitor analysis grounded in official docs (pfSense, OPNsense, MikroTik). Signal model validated against existing weight table. |
| Architecture | HIGH | All findings from 16,493 LOC codebase analysis. Data flow traced through specific line numbers. Architectural spine compliance verified. |
| Pitfalls | HIGH | 15 pitfalls identified from control systems principles + production failure modes. All mapped to specific code locations. |

**Overall confidence:** HIGH

This is the highest-confidence research possible: the entire milestone is wiring existing primitives together inside a mature, well-tested codebase. No external APIs, no new protocols, no unfamiliar libraries. Every integration point was traced to specific source lines.

### Gaps to Address

- **Exact WAN_RED weight value:** Research files propose slightly different ranges (20-25 vs. 30). Resolve during Phase 3 planning by modeling the full signal combination matrix with both values. The difference is minor: both enforce "WAN alone < threshold."
- **Same-file vs. separate-file for zone data:** STACK.md recommends extending the existing state file (zero additional I/O). PITFALLS.md notes dirty-tracking regression risk and suggests a separate file as an alternative. Resolve during Phase 1 planning by profiling dirty-tracking behavior with the zone field added.
- **Hysteresis stacking latency budget:** PITFALLS.md (Pitfall 8) identifies a potential 3.6-3.7s end-to-end latency if all hysteresis layers compound. ARCHITECTURE.md recommends reading the zone as-is (already filtered). An integration test measuring wall-clock latency from congestion injection to steering activation is needed in Phase 4.
- **Staleness threshold:** 5 seconds is proposed but has no production data backing. Phase 2 planning could analyze autorate state file write frequency to set this optimally.

## Sources

### Primary (HIGH confidence)
- Direct codebase analysis of `src/wanctl/` (16,493 LOC, 2,109 tests, 91%+ coverage)
- `wan_controller_state.py` -- state persistence, dirty tracking
- `autorate_continuous.py` -- zone computation, save_state(), run_cycle()
- `steering/daemon.py` -- BaselineLoader, SteeringDaemon, run_cycle(), SteeringConfig
- `steering/steering_confidence.py` -- ConfidenceWeights, ConfidenceSignals, compute_confidence()
- `steering/congestion_assessment.py` -- CongestionState, assess_congestion_state()
- `state_utils.py` -- atomic_write_json(), safe_json_load_file()
- `configs/steering.yaml`, `configs/spectrum.yaml` -- production configuration

### Secondary (MEDIUM confidence)
- pfSense gateway groups + failback bugs (#5090, #9054) -- competitor failover behavior
- OPNsense Multi-WAN docs -- sticky connections, time_period evaluation
- MikroTik Netwatch docs -- probe-based failover limitations
- Juniper VRRP failover-delay -- asymmetric timer patterns
- Fortinet convergence timers -- hold-up time semantics

### Tertiary (LOW confidence)
- Hysteresis stacking in control systems (instrunexus.com) -- general principle, applied by analogy
- POSIX write atomicity (utcc.utoronto.ca) -- confirms atomic rename sufficiency

---
*Research completed: 2026-03-09*
*Ready for roadmap: yes*
