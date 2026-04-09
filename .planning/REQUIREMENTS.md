# Requirements: wanctl v1.31

**Defined:** 2026-04-09
**Core Value:** Sub-second congestion detection with 50ms control loops

## v1.31 Requirements

Requirements for Linux-CAKE Optimization milestone. Removes legacy router-era constraints and optimizes controller for local CAKE management.

### Transport Performance

- [ ] **XPORT-01**: Controller applies CAKE bandwidth changes via pyroute2 netlink instead of subprocess tc fork
- [ ] **XPORT-02**: Netlink FD leak in _reset_ipr() is fixed — socket closed before reference nulled
- [ ] **XPORT-03**: CAKE parameters (diffserv, overhead, rtt) are validated via readback after every netlink bandwidth change

### Cycle Reliability

- [ ] **CYCLE-01**: State file writes use fdatasync instead of fsync for reduced metadata sync overhead
- [ ] **CYCLE-02**: Per-cycle SQLite metrics writes are offloaded to a background thread via queue
- [ ] **CYCLE-03**: State JSON writes are coalesced — only written when dirty flag set AND minimum interval elapsed

### Congestion Intelligence

- [ ] **ASYM-01**: Upload rate reduction is attenuated (50%) when IRTT detects downstream-only congestion
- [ ] **ASYM-02**: Asymmetry suppression requires N consecutive asymmetric IRTT readings before activating
- [ ] **ASYM-03**: Asymmetry gate disables automatically when IRTT data is stale (>30s), failing open to current behavior

### Tuning & Validation

- [ ] **TUNE-01**: Post-DSCP hysteresis suppression rate is measured and documented (may already be resolved)
- [ ] **TUNE-02**: step_up_mbps, warn_bloat_ms, hard_red_bloat_ms are A/B re-validated on linux-cake post-DSCP-fix

## Future Requirements

- Directional state machines (separate DL/UL congestion states) — v1.32+
- CAKE tin-aware floors (adjust floor_mbps based on tin bandwidth allocation) — v1.32+
- Adaptive hysteresis (auto-tune dwell/deadband from jitter profile) — v1.32+
- CakeStatsReader upgrade to netlink (steering daemon stats reads) — v1.32+

## Out of Scope

- **Async event loop rewrite**: The synchronous single-threaded loop is proven across 31 milestones. Background threads for specific I/O is sufficient.
- **CAKE tin-aware rate control**: Reading per-tin stats to influence rate decisions adds complexity. CAKE's internal FQ handles this.
- **Separate DL/UL RTT measurement**: Would require dedicated upload-only reflectors. IRTT asymmetry detection achieves the goal without this.

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| XPORT-01 | Phase 154 | Pending |
| XPORT-02 | Phase 154 | Pending |
| XPORT-03 | Phase 154 | Pending |
| CYCLE-01 | Phase 155 | Pending |
| CYCLE-02 | Phase 155 | Pending |
| CYCLE-03 | Phase 155 | Pending |
| ASYM-01 | Phase 156 | Pending |
| ASYM-02 | Phase 156 | Pending |
| ASYM-03 | Phase 156 | Pending |
| TUNE-01 | Phase 157 | Pending |
| TUNE-02 | Phase 158 | Pending |
