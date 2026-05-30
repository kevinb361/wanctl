# Roadmap: wanctl

## Milestones

- 🟢 **v1.47 Measurement Evidence Closure** — opened 2026-05-30 (Phases 219–221; 3-phase LOCKED scope per joint Claude + Codex operator decision; D-first per Pitfall 11)
- ✅ **v1.46 Internet Quality Recovery** — shipped-with-deferral 2026-05-30 (Phases 212–217 complete; Phase 218 carried as event-gated v1.45 VERIFY watch-list) — `milestones/v1.46-ROADMAP.md`
- ✅ **v1.45 Flapping Peak-Counter Window Repair** — shipped-with-deferral 2026-05-27 (Phases 210–211; VERIFY-01 deferred to v1.46+ per D-04(b); rolled into Phase 218 carry)
- ✅ **v1.44 Topology-Correct CAKE — Spectrum besteffort wash migration** — shipped 2026-05-26 (Phases 205–209; audit `passed` after 206 restamp, 16/16) — `milestones/v1.44-ROADMAP.md`
- ✅ **v1.43 UL Suppression Metrics & Gate Calibration** — shipped 2026-05-13 — `milestones/v1.43-ROADMAP.md`
- ✅ **v1.42 DOCSIS-Aware UL Congestion Control** — shipped 2026-05-06 — `milestones/v1.42-ROADMAP.md`
- ✅ **v1.41 Per-Direction Control Surfaces** — closed 2026-05-04 — `milestones/v1.41-ROADMAP.md`
- ✅ **v1.40 Queue-Primary Signal Arbitration** — shipped 2026-05-03 — `milestones/v1.40-ROADMAP.md`
- ✅ **v1.39 Control-Path Timing & Measurement Accounting** — shipped 2026-04-24 — `milestones/v1.39-ROADMAP.md`
- 📁 **v1.0 — v1.38** — see `MILESTONES.md` for the full historical index

**Current milestone:** v1.47 — 3 phases LOCKED. Phase 218 stays parallel (event-gated v1.45 VERIFY watch-list).

---

## Phases

### 🟢 v1.47 Measurement Evidence Closure (Phases 219–221)

- [ ] **Phase 219: Ingestion-Rate Observability (Scope D)** — Per-WAN per-table SQLite ingestion-rate visibility as additive extensions to `wanctl-history --ingestion-rate`; ships first to support Phase 218 audit evidence regardless of v1.47 timing.
- [ ] **Phase 220: Matrix Runner (Scope A1)** — Target/path/window matrix wrapper + stdlib aggregator + Wave 0 tests + pre-registered CRITERIA gate (kill / defect / close-with-prejudice rule).
- [ ] **Phase 221: Matrix Evidence + Closeout (Scope A2)** — Operator-driven matrix execution against pre-registered criteria; explicit verdict report; folded `tcp_12down` todo closed-or-carried with close-with-prejudice rule.

### 🔄 Event-Gated Watch (Carried from v1.45 + v1.46; parallel to v1.47)

- [ ] **Phase 218: Deferred v1.45 VERIFY Watch-List Closure** — Close VERIFY-01/VERIFY-02 and run ALERT-03 per-`cooldown_sec` bucket audit when a natural production flapping event on either WAN produces an alerts row with `details.peak_transition_count > 30`. **No synthetic event generation.** Plan only when evidence exists. Retained v1.45 phase directories archive after VERIFY-01 + ALERT-03 pass. **Not a v1.47 gate.**

<details>
<summary>✅ v1.46 Internet Quality Recovery (Phases 212–217) — SHIPPED-WITH-DEFERRAL 2026-05-30</summary>

- [x] Phase 212: Production Inventory And Drift Audit (3/3 plans) — completed 2026-05-27
- [x] Phase 213: Experience Baseline Harness (5/5 plans) — completed 2026-05-27
- [x] Phase 214: Measurement Collapse Investigation (6/6 plans) — completed 2026-05-29
- [x] Phase 215: Spectrum Upload Reclaim Canary (3/3 plans) — completed 2026-05-29
- [x] Phase 216: Recovery/Refractory Decision (1/1 plan) — completed 2026-05-29
- [x] Phase 217: Production Cycle-Budget Baseline (3/3 plans) — completed 2026-05-30

Full v1.46 roadmap archived to `milestones/v1.46-ROADMAP.md`. v1.46 stats and accomplishments in `MILESTONES.md`.

</details>

---

## Phase Details

### Phase 219: Ingestion-Rate Observability (Scope D)

**Goal**: Ship per-WAN per-metric ingestion-rate observability as additive extensions to `wanctl-history --ingestion-rate` so Phase 218 audit evidence is available regardless of v1.47 timing.

**Depends on**: Nothing in v1.47 (ships first per Pitfall 11 D-first ordering); composes existing v1.44 Phase 208 TOOL-02 surface.

**Requirements**: INGEST-01, INGEST-02, INGEST-03, INGEST-04, INGEST-05, SAFE-11

**Success Criteria** (what must be TRUE):
  1. `wanctl-history --ingestion-rate --by-table` and `--rolling=60,300,3600` produce valid JSON output with `schema_version: 1` and per-snapshot staleness fields (`_snapshot_unix`, `_snapshot_age_sec`) on every row.
  2. `wanctl-operator-summary --digest` renders the compact per-WAN ingestion-rate block (per-WAN totals + dominant-table) sourced from the new bucketed CLI output without aborting on per-WAN read failure.
  3. Golden SQLite fixture test (`tests/test_history_ingestion_rate_bucketed.py`) pins `schema_version=1` and both `--by-table` + `--rolling` output shapes; passes green.
  4. Mutation-boundary pytest (SAFE-11) passes green for the Phase 219 allowlist: additive edits to `src/wanctl/history.py` are explicitly allowlisted; controller-path files (`wan_controller.py`, `queue_controller.py`, `cake_signal.py`, backends, `alert_engine.py`, fusion) remain untouched.
  5. Post-deploy production cycle budget unchanged within Phase 217 baseline tolerance: `cycle_total.avg_ms ≤ 3.0` and `p99_ms ≤ 7.5` (matches v1.46 Phase 217 anchor + small headroom).

**Plans**: 4 plans

- [x] 219-01-PLAN.md — Wave 0 test scaffolds (golden-fixture pin, cron-script xfailed scaffold, SAFE-11 boundary clone)
- [x] 219-02-PLAN.md — Wave 1: core CLI extension (--by-table + --rolling, public per_wan_ingestion_rate_bucketed, envelope formatter, v1.44 envelope test migration)
- [ ] 219-03-PLAN.md — Wave 2: operator-summary --digest ingestion block (tie-break + tolerance)
- [ ] 219-04-PLAN.md — Wave 3: cron snapshot script + docs/CONFIGURATION.md staleness paragraph

### Phase 220: Matrix Runner (Scope A1)

**Goal**: Land the target/path/window matrix runner with pre-registered decision criteria and a verified harness so Phase 221 evidence collection runs against immutable rules.

**Depends on**: Phase 219 (D-first ordering; Phase 219 deployed and stable before agent attention shifts to matrix tooling). Composes Phase 213 `phase213-baseline-capture.sh` and Phase 214 analyzer chain unchanged.

**Requirements**: CRITERIA-01, CRITERIA-02, MATRIX-01, MATRIX-02, MATRIX-03, MATRIX-04, AGGREGATE-01, AGGREGATE-02, AGGREGATE-03, SAFE-11

**Success Criteria** (what must be TRUE):
  1. `scripts/phase220-matrix.yaml` is committed with the canonical cell list (Phase 214 canonical `dallas` control cell in every window; Vultr Dallas + Vultr Chicago supplemental targets; Spectrum + ATT path axis; off-peak + daytime + prime-time window axis) AND pre-registered quantitative kill criteria + defect criteria + close-with-prejudice rule. Thresholds are locked at Phase 220 plan time, never edited after first live cell run.
  2. `scripts/phase220-target-path-matrix.sh` dry-run executes a zero-cell rehearsal cleanly: D-14 src-diff triple-check passes, window-hour gate fires, delegation to `phase213-baseline-capture.sh` is wired, sidecar manifest writes, no edits to existing Phase 213/214 scripts.
  3. One wet daytime control cell (Spectrum + Phase 214 canonical `dallas`) reproduces the Phase 214 canonical anchor verdict against the unchanged extractor + aligner + classifier chain — proves the harness is faithful before any supplemental cells are run.
  4. Wave 0 unit tests pass green: pinned `.flent.gz` fixtures + Mann-Whitney U + bootstrap 95% percentile CI golden-test seeds (`B=2000`, `random.Random(seed)`) land BEFORE any live supplemental-cell run.
  5. Mutation-boundary pytest (SAFE-11) passes green against the expanded allowlist (`scripts/`, `tests/fixtures/phase22*/`, `docs/`, `configs/`, `deploy/systemd/`); `src/wanctl/` controller surface remains untouched; `docs/` edits describe new CLI tools only — no threshold-tuning language, no future-tuning prediction.

**Plans**: TBD

### Phase 221: Matrix Evidence + Closeout (Scope A2)

**Goal**: Execute the matrix, write the closeout decision report, and close-or-carry the folded `tcp_12down` todo with explicit verdict and close-with-prejudice rule applied.

**Depends on**: Phase 220 (harness + pre-registered criteria + Wave 0 tests must exist before any operator-driven evidence collection). Operator-driven; spans multiple days for replicate spacing.

**Requirements**: CLOSEOUT-01, CLOSEOUT-02, CLOSEOUT-03, SAFE-11

**Success Criteria** (what must be TRUE):
  1. `221-CLOSEOUT.md` carries a per-cell verdict table where each row records replicate count, run timestamps, mtr/traceroute snapshot reference, and six-driver classifier output (`reflector_loss` | `loss` | `jitter` | `queue_delay` | `host_kernel` | `signal_none`).
  2. Matrix-level verdict is exactly one of `{defect_located, hypothesis_killed, carried_narrower_with_close_with_prejudice_rule}` against the CRITERIA-01 thresholds locked at Phase 220. No single-cell `defect_located` declaration without corroboration across an orthogonal axis (target OR path OR driver).
  3. Folded `2026-04-08-investigate-tcp-12down-latency-spikes-under-multi-flow-downl` todo is either marked closed (verdict ≠ `carried_narrower`) or carried forward with the close-with-prejudice rule from CRITERIA-02 attached verbatim.
  4. CRITERIA-01 thresholds applied unchanged from Phase 220 commit — verified by replaying the Phase 220 YAML SHA against the closeout report's threshold citation.
  5. Mutation-boundary pytest (SAFE-11) passes green at milestone-close boundary against the Phase 220 base SHA; no controller-path source diff; `docs/` edits cite report by reference only, never carry threshold-tuning language.

**Plans**: TBD

---

## Progress

| Phase | Milestone | Plans Complete | Status   | Completed  |
| ----- | --------- | -------------- | -------- | ---------- |
| 219. Ingestion-Rate Observability (Scope D)   | v1.47       | 2/4 | In Progress|  |
| 220. Matrix Runner (Scope A1)                 | v1.47       | 0/? | Not started             | —          |
| 221. Matrix Evidence + Closeout (Scope A2)    | v1.47       | 0/? | Not started             | —          |
| 218. Deferred v1.45 VERIFY Watch-List Closure | v1.46 carry | 0/? | Deferred (event-gated; parallel to v1.47)  | —          |
| 217. Production Cycle-Budget Baseline         | v1.46       | 3/3 | Complete                | 2026-05-30 |
| 216. Recovery/Refractory Decision             | v1.46       | 1/1 | Complete                | 2026-05-29 |
| 215. Spectrum Upload Reclaim Canary           | v1.46       | 3/3 | Complete                | 2026-05-29 |
| 214. Measurement Collapse Investigation       | v1.46       | 6/6 | Complete                | 2026-05-29 |
| 213. Experience Baseline Harness              | v1.46       | 5/5 | Complete                | 2026-05-27 |
| 212. Production Inventory And Drift Audit     | v1.46       | 3/3 | Complete                | 2026-05-27 |

---

## Backlog

### Deferred / Carried Forward (post-v1.47-open)

- **VERIFY-01 / ALERT-03 production verification** — mapped to Phase 218; execute only when a qualifying natural production DOCSIS flapping event appears (`details.peak_transition_count > 30` on either WAN). Parallel to v1.47, not a v1.47 gate.
- **STEER-DRIFT-01** Steering runtime (`1.39.0`) vs source (`1.45.0`) alignment — Phase 212 surfaced; pending operator approval at v1.47+ planning.
- **RECLAIM-04** Spectrum upload reclaim re-attempt with revised probe shape — Phase 215 bounded VOID exhausted at ceiling 20; needs different evidence design before re-attempt.
- **SEED-005** Conservative UL tuning sweep — dormant since v1.43; prereqs met since v1.44.
- **SEED-006** Silicom bypass NIC tooling + test harness — dormant since v1.45.
- **SEED-007** Storage hygiene (autorate flat-gauge fire-on-change + CAKE tin skip-on-unchanged consumer audit) — dormant since v1.45.
- **Optional `/health.metrics.ingestion` block** — escalation deferred unless Phase 218 audit evidence proves CLI-only insufficient; if escalated, ARCH-09 payload-shape contract + ARCH-12 DeferredIOWorker mandatory, post-deploy `cycle_total.avg_ms ≤ 3.0` and `p99_ms ≤ 7.5` required.
- **T17(b)** CALIB-02 YAML knob shape evaluation — still gated on RECLAIM outcomes.
- **knowledge-base debug session** — status unknown; triage outside this roadmap unless it affects active quality work.

### Resolved In v1.46

- `2026-04-08-investigate-tcp-12down-latency-spikes-under-multi-flow-downl` → Phase 214 (carried-narrower; targeted by v1.47 Phase 220/221 for confirm-or-kill).
- `2026-04-15-profile-post-hotpath-baseline-on-production-wan` → Phase 217 (closed as no-action 2026-05-30).
- `phase-196 queue-primary refractory semantics` thread → Phase 216 (closed no-change / resolved-by-197).
- `SEED-005 conservative UL tuning sweep` partial → Phase 215 (canary ran; bounded VOID exhausted; Spectrum rolled back to ceiling 18; seed remains dormant for revised probe in v1.48+).
