# Requirements: wanctl v1.47 Measurement Evidence Closure

**Defined:** 2026-05-30
**Core Value:** Sub-second congestion detection with 50ms control loops, achieved through systematic performance optimization and code quality improvements while maintaining production reliability.

## Milestone v1.47 Requirements

Bounded read-only evidence milestone. Two scopes: A (tcp_12down target/path sensitivity closure) + D (ingestion-rate observability). 3 phases, D-first per Pitfall 11. Phase 218 watch-list runs in parallel — not a v1.47 gate. No controller threshold/algorithm/CAKE/steering changes from matrix results: v1.47 closeout may recommend, never implement.

### CRITERIA — Pre-Registered Decision Rules (Scope A, Phase 220 gate)

- [x] **CRITERIA-01**: Kill criteria and defect criteria for the `tcp_12down` target/path sensitivity hypothesis are written into `220-CONTEXT.md` BEFORE any live matrix cell run. Both are quantitative and time-bound (e.g., kill: canonical control cell p99 ≤ 200ms on ≥ 2/3 windows AND zero supplemental cell exceeds 1.5x control p99 across all windows; defect: ≥ 1 supplemental cell p99 > 500ms reproduced across ≥ 2 windows with corroborating reflector_loss / loss / queue_delay driver — exact thresholds locked at Phase 220 plan time, never edited after first live run).
- [x] **CRITERIA-02**: Close-with-prejudice rule documented: if matrix verdict is again `ambiguous`, the folded `2026-04-08-investigate-tcp-12down` todo is closed-with-prejudice and no v1.48+ follow-up may reopen the thread without independent new evidence (e.g., a real production p99 incident captured in DB).

### MATRIX — Target/Path Matrix Definition + Runner (Scope A, Phase 220)

- [x] **MATRIX-01**: `scripts/phase220-matrix.yaml` defines the canonical cell list with at minimum (a) Phase 214 canonical `dallas` reflector as the control cell present in EVERY window, (b) Vultr Dallas + Vultr Chicago as the supplemental hypothesis targets, (c) Spectrum + ATT as the path axis, (d) off-peak + daytime + prime-time as the window axis. `base_sha` field anchors mutation-boundary across multi-day runs.
- [x] **MATRIX-02**: `scripts/phase220-target-path-matrix.sh` per-cell wrapper carries the Phase 214 Wrapper Composition Pattern verbatim: gate entry → triple-check `src/wanctl/` cleanliness via D-14 guard → window-hour gate → delegate to `phase213-baseline-capture.sh` → pull journal via SSH → write phase-owned sidecar manifest. Zero edits to existing Phase 213/214 scripts.
- [x] **MATRIX-03**: Source-bind + egress IP verification per cell (Phase 213 harness enforces; harness fails closed on bind/egress mismatch). Per-replicate mtr/traceroute snapshot captured to detect mid-run BGP path changes.
- [ ] **MATRIX-04**: Per-cell run delegates analysis to the unchanged Phase 214 fail-closed extractor + per-second aligner + six-driver classifier (`reflector_loss`, `loss`, `jitter`, `queue_delay`, `host_kernel`, `signal_none`).

### AGGREGATE — Stdlib Aggregator + Matrix Verdict (Scope A, Phase 220)

- [x] **AGGREGATE-01**: `scripts/phase220-matrix-aggregator.py` forks `phase214-matrix-summary.py` and extends to a (target × path × window) cube rollup. Stdlib-only (`statistics`, `random`, `math`, `json`); no SciPy/NumPy/pandas.
- [x] **AGGREGATE-02**: Per-cell vs per-target/path/window rollup vs matrix-level verdict are emitted as distinct fields. Supplemental-vs-canonical cells are separated in the report; the canonical control cell is never aggregated with supplemental cells.
- [x] **AGGREGATE-03**: Statistical comparison uses Mann-Whitney U (two-sided, normal approximation) + bootstrap 95% percentile CI (B=2000, seeded via `random.Random(seed)`). Golden-test fixtures with pinned p-values + CI bounds make the statistics testable. Wave 0 unit tests with pinned `.flent.gz` fixtures land BEFORE any live cell run.

### CLOSEOUT — Decision Report + Folded Todo (Scope A, Phase 221)

- [ ] **CLOSEOUT-01**: `221-CLOSEOUT.md` records one explicit verdict from `{defect_located, hypothesis_killed, carried_narrower_with_close_with_prejudice_rule}` against the CRITERIA-01 thresholds. No single-cell `defect_located` declaration without corroboration across an orthogonal axis (target or path or driver).
- [ ] **CLOSEOUT-02**: Per-cell verdict table + matrix-level verdict + per-driver attribution appear in the report. Each cell row carries replicate count, run timestamps, mtr snapshot reference, and classifier output.
- [ ] **CLOSEOUT-03**: Folded `2026-04-08-investigate-tcp-12down` todo is updated with the verdict and either marked closed (any verdict ≠ `carried_narrower`) or carried forward with the explicit close-with-prejudice rule attached.

### INGEST — Ingestion-Rate Observability (Scope D, Phase 219)

- [x] **INGEST-01**: `wanctl-history --ingestion-rate --by-table` flag added additively to `src/wanctl/history.py`. Output is per-WAN × per-table rows/sec for the configured window. Per-table read failures emit `null` for that table rather than aborting (tolerant pattern from v1.44 TOOL-03).
- [x] **INGEST-02**: `wanctl-history --ingestion-rate --rolling=60,300,3600` flag added additively. Output includes a rolling-window block for each specified window in one call. Default behavior (no `--rolling`, no `--by-table`) is unchanged from v1.44 Phase 208.
- [x] **INGEST-03**: JSON output mode carries `schema_version: 1` plus per-snapshot staleness fields (`_snapshot_unix` and `_snapshot_age_sec` on every snapshot row).
- [x] **INGEST-04**: `wanctl-operator-summary --digest` surfaces a compact ingestion-rate block (per-WAN totals + dominant-table) sourced from the new bucketed output. Read tolerance from v1.44 TOOL-03 carries forward.
- [x] **INGEST-05**: `scripts/phase219_ingestion_digest.py` is cron-callable (not a systemd unit) and calls extended `wanctl-history --ingestion-rate` in JSON mode for snapshot capture. Golden SQLite fixture in `tests/test_history_ingestion_rate_bucketed.py` pins schema_version=1 and `--by-table` + `--rolling` output shape.

### SAFE — Cross-Cutting Read-Only Discipline (Phases 219/220/221)

- [x] **SAFE-11**: Mutation-boundary pytest covers expanded allowlist beyond `src/wanctl/`: `configs/`, `deploy/systemd/`, `scripts/`, `tests/fixtures/phase22*/`, `docs/`. Test fails closed at every phase boundary. Test fixtures encode evidence (`observed_*.json` shape), never controller specifications (`expected_behavior_*.json` forbidden). `docs/` edits restricted to describing new CLI tools — no threshold-tuning language, no future tuning predictions. Phase 219 Scope D additive edits to `src/wanctl/history.py` are explicitly allowlisted; controller-path files (`wan_controller.py`, `queue_controller.py`, `cake_signal.py`, backends, alert_engine, fusion) remain forbidden.

### Phase 218 Fallback (Documented Carry)

If Phase 218 (event-gated v1.45 VERIFY watch-list) fires during the v1.47 matrix execution window BEFORE INGEST-01..05 ship, the fallback is the v1.44 Phase 208 `wanctl-history --ingestion-rate` CLI as-is (per-WAN totals, no per-table breakdown). This fallback is documented to prevent re-litigation mid-incident.

## Future Requirements (Deferred)

### Steering Version-Drift Alignment (B)

- **STEER-DRIFT-01**: Align steering runtime (`1.39.0`) with source (`1.45.0`). Requires operator approval at v1.47+ planning. Surfaced as known drift by Phase 212.

### Spectrum Upload Reclaim Re-Attempt (C)

- **RECLAIM-04**: Revised probe shape for Spectrum upload ceiling re-attempt. Phase 215 bounded VOID exhausted at ceiling 20; needs fundamentally different evidence design before re-attempt.

### Dormant Seeds

- **SEED-005**: Conservative UL tuning sweep (dormant since v1.43; prereqs met since v1.44).
- **SEED-006**: Silicom bypass NIC tooling + test harness (dormant since v1.45).
- **SEED-007**: Storage hygiene — autorate flat-gauge fire-on-change + CAKE tin skip-on-unchanged consumer audit (dormant since v1.45).

### Optional `/health.metrics.ingestion` Block

Defer unless Phase 218 audit evidence proves CLI-only insufficient. If escalated: additive-only, numeric metrics only, payload-shape regression test mandatory, counters live in `DeferredIOWorker` (ARCH-12) — never on the 50ms control thread. Post-deploy profiling must confirm `cycle_total.avg_ms ≤ 3.0` and `p99_ms ≤ 7.5`.

## Out of Scope

| Feature | Reason |
|---------|--------|
| Controller threshold/algorithm changes from matrix results | v1.47 is read-only evidence; tuning decisions belong to v1.48+ after evidence isolates a cause |
| CAKE policy changes | Same — read-only milestone |
| Steering policy changes | Same — read-only milestone |
| Bridge QoS / nftables / RouterOS surface edits | Same — read-only milestone |
| Threshold-based alerts on ingestion-rate | Read-only observability only; alert design is out of scope |
| Synthetic Phase 218 event generation | Forbidden by v1.46 ROADMAP carry; event-gated must remain natural |
| Auto-rotating target pool for matrix | Anti-feature — undermines reproducibility |
| ML/prediction for target/path or write-rate | Anti-feature — anti-evidence |
| New third-party Python dependencies | Stdlib-only mandate from Phase 214 D-10 holds; SciPy/NumPy/pandas forbidden |
| Prometheus/Grafana export | Infrastructure not deployed; deferred since v1.23 |
| Spectrum upload reclaim re-attempt (C) | Phase 215 bounded VOID exhausted; needs different probe — out of scope for v1.47 |
| Steering runtime/source alignment (B) | Pending operator approval; out of scope for v1.47 |
| SEED-005/006/007 | Dormant; out of scope for v1.47 |
| DSCP marking probe | Risk of scope drift from confirm-or-kill narrow scope |
| Schema migration on production SQLite | Read-only observability is additive only |

## Traceability

Every v1.47 REQ-ID is mapped to exactly one phase. SAFE-11 is cross-cutting and re-verified at each phase boundary (mirrors v1.45 SAFE-10, v1.44 SAFE-08/09, v1.43 SAFE-07 pattern); it is listed on all three phases.

| Requirement | Phase | Scope | Status |
|-------------|-------|-------|--------|
| INGEST-01 | Phase 219 | D (Ingestion-Rate Observability) | Complete |
| INGEST-02 | Phase 219 | D (Ingestion-Rate Observability) | Complete |
| INGEST-03 | Phase 219 | D (Ingestion-Rate Observability) | Complete |
| INGEST-04 | Phase 219 | D (Ingestion-Rate Observability) | Complete |
| INGEST-05 | Phase 219 | D (Ingestion-Rate Observability) | Complete |
| SAFE-11 (Phase 219 boundary) | Phase 219 | Cross-cutting | Complete |
| CRITERIA-01 | Phase 220 | A1 (Matrix Runner) | Pending |
| CRITERIA-02 | Phase 220 | A1 (Matrix Runner) | Pending |
| MATRIX-01 | Phase 220 | A1 (Matrix Runner) | Pending |
| MATRIX-02 | Phase 220 | A1 (Matrix Runner) | Pending |
| MATRIX-03 | Phase 220 | A1 (Matrix Runner) | Pending |
| MATRIX-04 | Phase 220 | A1 (Matrix Runner) | Pending |
| AGGREGATE-01 | Phase 220 | A1 (Matrix Runner) | Pending |
| AGGREGATE-02 | Phase 220 | A1 (Matrix Runner) | Pending |
| AGGREGATE-03 | Phase 220 | A1 (Matrix Runner) | Pending |
| SAFE-11 (Phase 220 boundary) | Phase 220 | Cross-cutting | Pending |
| CLOSEOUT-01 | Phase 221 | A2 (Matrix Evidence + Closeout) | Pending |
| CLOSEOUT-02 | Phase 221 | A2 (Matrix Evidence + Closeout) | Pending |
| CLOSEOUT-03 | Phase 221 | A2 (Matrix Evidence + Closeout) | Pending |
| SAFE-11 (Phase 221 boundary) | Phase 221 | Cross-cutting | Pending |

**Coverage:** 18 unique REQ-IDs (INGEST x5, CRITERIA x2, MATRIX x4, AGGREGATE x3, CLOSEOUT x3, SAFE-11 x1) mapped across 3 phases. SAFE-11 appears as a phase-boundary gate three times because it is re-verified at every phase boundary; this is not a duplicate mapping, it is the v1.43-onward SAFE-cross-cutting convention.

**Phase 218 fallback:** If Phase 218 (event-gated v1.45 VERIFY watch-list) fires during v1.47 matrix execution BEFORE INGEST-01..05 ship, the fallback is the v1.44 Phase 208 `wanctl-history --ingestion-rate` CLI as-is (per-WAN totals, no per-table breakdown). Phase 218 is parallel to v1.47, not a v1.47 gate, and is not counted in v1.47 traceability.
