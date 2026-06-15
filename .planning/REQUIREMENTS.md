# Requirements: wanctl v1.53 — Pluggable RTT Measurement Backend

**Defined:** 2026-06-13
**Core Value:** Sub-second congestion detection with 50ms control loops, achieved through systematic performance optimization and code quality improvements while maintaining production reliability.

**Milestone thesis:** Introduce a config-selectable RTT measurement backend abstraction with `fping` as the first alternate, validate it against the live RTT consumer via a pre-registered A/B, and flip the production default to `fping` only if evidence clearly wins — under a rollback anchor. This is the first controller-path-touching milestone in 10; the SAFE-07..16 zero-diff streak ends by design and is replaced by a narrowed SAFE-17 allowlist.

## v1 Requirements

Requirements for this milestone. Each maps to exactly one roadmap phase.

### Provenance (read-only entry gate)

- [x] **PROV-01**: Operator can read a documented map of which producer feeds live steering RTT in the current cake-autorate production topology (state bridge / autorate `/health` `measurement.raw_rtt_ms` vs wanctl `RTTMeasurement`), captured read-only with no production mutation.
- [x] **PROV-02**: The A/B target interpretation — (A) revive steering's own pinger as the live RTT source, or (B) evaluate at the autorate/bridge producer — is selected and recorded with evidence before any backend code is written.
- [x] **PROV-03**: Operator can confirm `fping -S <source_ip>` egresses the intended WAN under the host's current `ip rule` policy routing via a read-only `ip route get <reflector> from <source_ip>` proof. _(Satisfied by Plan 04 corrected source-bound router-hop proof: both WANs PASS on host egress dev `ens18` with distinct source-bound route keys; `spec-modem`/`att-modem` are downstream `ul_if` labels, not host route devs.)_

### Backend Seam

- [x] **SEAM-01**: wanctl exposes a single `RttBackend` abstraction (Protocol) consumed by both steering and autorate, with the existing icmplib measurement refactored behind it.
- [x] **SEAM-02**: icmplib-default RTT behavior is byte-identical to pre-refactor, proven by the hot-path test slice plus snapshot equivalence.
- [x] **SEAM-03**: RTT samples carry backend / source-IP / loss metadata (`RttSample` as a strict superset of `RTTSnapshot`) without breaking `WANController.measure_rtt()`, the scorer, or other existing consumers.
- [x] **SEAM-04**: The abstraction is shaped to absorb the existing IRTT measurement path (adapter seam present); full IRTT migration is deferred.

### fping Backend

- [ ] **FPING-01**: Operator can select an `fping` RTT backend that probes via one-shot `subprocess.run` bursts on a background cadence, never on the synchronous 50ms control loop.
- [x] **FPING-02**: The fping backend binds source IP per WAN via `-S`, matching the existing `ping_source_ip` configuration.
- [x] **FPING-03**: The fping backend probes multiple reflectors in a single process and returns per-reflector results.
- [x] **FPING-04**: The fping output parser, built from captured real fping 5.1 samples, handles reply, total loss, partial loss, partial lines, banner, and process-death output; loss tokens map to "no sample" and are never recorded as `0ms`.
- [x] **FPING-05**: The fping backend tolerates subprocess stall and death without crashing the daemon (bounded timeout, recover-and-continue), mirroring the existing `irtt_measurement.py` lifecycle.

### Config & Validation

- [x] **CFG-01**: Operator can set `measurement.backend: icmplib|fping` per WAN/consumer in YAML; an absent key resolves to `icmplib`.
- [x] **CFG-02**: The config validator rejects unknown backend values and WARNs (does not fail) when `fping` is selected but the binary is absent.
- [x] **CFG-03**: All existing deployment configs validate unchanged — no migration required.

### Fallback

- [ ] **FALL-01**: When the `fping` binary is unavailable, the backend factory falls back to `icmplib` automatically.
- [ ] **FALL-02**: Fallback is loud and observable (WARN-once + fallback counter + `/health` attribution), never silent.

### Cycle-Budget Benchmark

- [ ] **BENCH-01**: Operator can run an idle-and-under-load cycle-budget + CPU benchmark of `fping` vs `icmplib` under a real systemd unit (not an interactive shell).
- [ ] **BENCH-02**: A pre-registered no-regression gate, committed before the run, blocks the live A/B if fping regresses cycle budget (vs `avg≈2.85ms` / `p99≈6.9ms` baseline), leaks file descriptors or zombies, or stalls under systemd.

### Health / Observability

- [ ] **HEALTH-01**: `/health` additively exposes `measurement.backend` and `source_ip` so every RTT sample is attributable during the A/B; the existing payload contract (`raw_rtt_ms`, `available`, `staleness_sec`) is byte-preserved.

### Reflector Quality (differentiator)

- [x] **REFL-01**: Per-reflector loss reported by fping feeds reflector-quality scoring (additive, gated to the fping backend). This is an explicitly-accepted controller-path touch covered by the SAFE-17 allowlist exception.

### A/B Evidence

- [ ] **AB-01**: Operator runs a pre-registered live A/B (`icmplib` vs `fping`) on the Phase-238-selected target, one WAN under test with the other as control, under a Snapshot-A rollback anchor.
- [ ] **AB-02**: The A/B supports concurrent / interleaved comparison within the same window to control diurnal confounding.
- [ ] **AB-03**: The A/B verdict is computed against thresholds committed before data collection (RTT agreement within tolerance, cycle-budget non-regression, loss-detection non-regression, minimum intended-backend cycle fraction, zero daemon restarts, steering-decision stability); "keep icmplib" is a valid passing close.

### Default Flip

- [ ] **FLIP-01**: If and only if the A/B clearly wins, the operator can flip the production default to `fping` under an armed rollback with sign-off recorded; otherwise the milestone records a documented "stay on icmplib" recommendation.

### Safety Invariant

- [x] **SAFE-17**: Controller-path changes stay within a narrowed, pre-approved v1.53 allowlist — the RTT-measurement seam (`rtt_backend.py`, `fping_measurement.py`, `rtt_measurement.py`, factory/config/validator/health wiring) plus the explicitly-accepted reflector-scorer touch for REFL-01. A fail-closed source-diff verifier proves no out-of-allowlist controller-path drift (state machine, thresholds, EWMA, dwell, deadband, arbitration, fusion) at every phase boundary and at milestone close.

## Future Requirements

Deferred to a later milestone. Tracked but not in this roadmap.

### IRTT Migration

- **IRTT-MIG-01**: Existing IRTT measurement migrated to run as a first-class `IrttBackend` behind the seam (not just adapter-shaped).

### fping Enhancements

- **FPING-JSON-01**: Adopt `fping -J` structured JSON output once the schema is stable and present in the Debian/Ubuntu deploy baseline.

### Native Validation

- **NATIVE-AB-01**: Stand up native autorate to validate fping on the native control path (currently dormant; inherits the seam passively).

## Out of Scope

Explicitly excluded. Anti-features from research documented here with reasoning.

| Feature | Reason |
|---------|--------|
| IRTT as a *new* backend / full IRTT migration | IRTT already exists; this milestone only shapes the Protocol to absorb it (SEAM-04). Full migration is IRTT-MIG-01 (future). |
| `fping -J` JSON output | Alpha schema (fping 5.5), absent from the 5.1 deploy baseline. Parse stable text only. |
| Long-lived `fping -l` loop process | Root cause of the observed systemd STALL is pipe block-buffering (pre-v4.3). One-shot subprocess bursts only. |
| Per-cycle `subprocess.run` inside the 50ms loop | Fork/exec cost blows the cycle budget. Probing runs on a background cadence. |
| Hard `fping` dependency | Must be fallback-capable (FALL-01/02); no deployment may hard-require fping. |
| Flipping the production default without A/B evidence | FLIP-01 is conditional and operator-gated; negative result is a valid close. |
| Controller threshold / algorithm / state-machine changes (EWMA, dwell, deadband, arbitration, fusion) | This milestone changes the measurement *input*, not classification. SAFE-17 fails closed on any such drift. |
| Native autorate retirement (ROLE-01), Spectrum loaded-latency tail (TAIL-01) | Out of thesis; carried deferred. |
| Dormant seeds SEED-003/004/005/007 | Tune the dormant native controller or are storage-hygiene; not this thesis. |

## Traceability

Populated during roadmap creation. Each requirement maps to exactly one phase.

| Requirement | Phase | Status |
|-------------|-------|--------|
| PROV-01 | Phase 238 | Complete |
| PROV-02 | Phase 238 | Complete |
| PROV-03 | Phase 238 | Complete |
| SEAM-01 | Phase 239 | Complete |
| SEAM-02 | Phase 239 | Complete |
| SEAM-03 | Phase 239 | Complete |
| SEAM-04 | Phase 239 | Complete |
| FPING-01 | Phase 241 | Pending |
| FPING-02 | Phase 241 | Complete |
| FPING-03 | Phase 241 | Complete |
| FPING-04 | Phase 241 | Complete |
| FPING-05 | Phase 241 | Complete |
| CFG-01 | Phase 240 | Complete |
| CFG-02 | Phase 240 | Complete |
| CFG-03 | Phase 240 | Complete |
| FALL-01 | Phase 242 | Pending |
| FALL-02 | Phase 242 | Pending |
| BENCH-01 | Phase 243 | Pending |
| BENCH-02 | Phase 243 | Pending |
| HEALTH-01 | Phase 244 | Pending |
| REFL-01 | Phase 241 | Complete |
| AB-01 | Phase 245 | Pending |
| AB-02 | Phase 245 | Pending |
| AB-03 | Phase 245 | Pending |
| FLIP-01 | Phase 246 | Pending |
| SAFE-17 | Phase 246 (cross-phase; verified at every boundary) | Complete |

**Coverage:**
- v1 requirements: 26 total
- Mapped to phases: 26 ✓
- Unmapped: 0 — 100% coverage, zero orphans (roadmap created 2026-06-13, Phases 238-246)

---
*Requirements defined: 2026-06-13*
*Last updated: 2026-06-13 after roadmap creation (Phases 238-246; 26/26 mapped)*
