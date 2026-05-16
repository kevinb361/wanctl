# Roadmap: wanctl

## Milestones

- 🚧 **v1.44 Topology-Correct CAKE — Spectrum besteffort wash migration** — active (planning → execution; phases 205–209)
- ✅ **v1.43 UL Suppression Metrics & Gate Calibration** — shipped 2026-05-13 (audit `passed` 15/15; gap-closure cycle 204-07..10 closed post-d44e2fd evidence; threshold 175 dual-gate verified) — `milestones/v1.43-ROADMAP.md`
- ✅ **v1.42 DOCSIS-Aware UL Congestion Control** — shipped 2026-05-06 (gaps_found Route B; D-19 PASS / D-14 deferred to v1.43) — `milestones/v1.42-ROADMAP.md`
- ✅ **v1.41 Per-Direction Control Surfaces** — closed 2026-05-04 (gaps_found; ARB-05/SAFE-06/DOCS-03 satisfied; VALN-06 deferred-and-closed via v1.42) — `milestones/v1.41-ROADMAP.md`
- ✅ **v1.40 Queue-Primary Signal Arbitration** — shipped 2026-05-03 — `milestones/v1.40-ROADMAP.md`
- ✅ **v1.39 Control-Path Timing & Measurement Accounting** — shipped 2026-04-24 (operator waiver; archived 2026-05-06 gaps_found) — `milestones/v1.39-ROADMAP.md`
- 📁 **v1.0 — v1.38** — see `MILESTONES.md` for the full historical index

---

## Active Milestone: v1.44 Topology-Correct CAKE — Spectrum besteffort wash migration

**Goal:** Migrate Spectrum CAKE qdisc from `940Mbit diffserv4 nowash` to topology-correct `920Mbit besteffort wash` (validated out-of-band 2026-04-22 flent), removing classification theater that the carrier strips upstream — without disturbing ATT (DSL, separately validated) and without changing controller thresholds/algorithms.

**Phase numbering:** continues from v1.43 (last phase 204) → v1.44 starts at Phase 205.

**Closeout invariants:**
- **SAFE-08 (mechanical):** ATT config + ATT-specific code paths byte-identical between v1.43 close (`6508d68`) and v1.44 close.
- **SAFE-09 (behavioral):** No controller threshold / algorithm / EWMA / dwell / deadband / burst changes. Control-path source diff bounded to TOPO-01 (`cake_signal.py`), TOPO-02 (`cake_params.py` allow_wash gate, `backends/linux_cake.py` + `backends/netlink_cake.py` wash token/kwarg emission, `check_config_validators.py` allowlist), TOOL-03 (`operator_summary.py` perm handling), and the `__init__.py` version bump. Verified at every phase boundary; mechanical closeout in Phase 209.

**Granularity:** fine (per `.planning/config.json`)
**Coverage:** 16 / 16 v1.44 requirements mapped (TOPO 1–7, HRDN 1–4, TOOL 1–3, SAFE 8–9)
**Spine seed:** SEED-001 (dormant → active at milestone open)

### Phases

- [x] **Phase 205: Tin-agnostic CAKE signal + allow_wash gate** — pure-code refactor; `cake_signal.py` becomes layout-agnostic and `cake_params.py` gains a per-WAN `allow_wash` gate. No deploy. (completed 2026-05-14)
- [ ] **Phase 206: A/B replay harness + rollback gates** — captures pre-migration controller behavior as the comparison baseline and wires machine-readable rollback criteria into a predeploy gate script. (gaps_found 2026-05-15; TOPO-05 non-finite `--window-hours` fail-closed gap remains; see `206-VERIFICATION.md`)
- [x] **Phase 207: Soak / harness hardening (v1.43 closeout-routed)** — fail-closed source-diff verifier, soak-capture transient-failure tolerance, `secondary_gate_legacy` removal, CALIB-02 YAML-promotion decision. (completed 2026-05-15)
- [x] **Phase 208: Carry-on quick-tasks (T17a / T9 / T12)** — aggregator schema closeout, `wanctl-history --ingestion-rate`, operator-summary digest perm guard. (gap closure planned 2026-05-16 for explicit legacy `--db` + `--wan` ingestion-rate filtering)
- [ ] **Phase 209: Spectrum config migration, production canary, and docs** — Spectrum YAML flips to `920Mbit besteffort wash`, two-snapshot rollback ritual canary, docs updated, SAFE-08 / SAFE-09 mechanical closeout.

### Phase Details

#### Phase 205: Tin-agnostic CAKE signal + allow_wash gate

**Goal:** The controller can ingest both single-tin besteffort and multi-tin diffserv4 CAKE state without per-deployment branching, and the qdisc args list can include `wash` only when an explicit per-WAN config gate is set.

**Depends on:** Nothing (first v1.44 phase; v1.43 already closed)
**Requirements:** TOPO-01, TOPO-02
**Success Criteria** (what must be TRUE):
  1. `src/wanctl/cake_signal.py` aggregation at lines 13/173/306 iterates over the actual tin set and produces identical outputs for ATT's multi-tin diffserv4 layout (regression evidence: existing ATT-shape unit/replay tests pass byte-for-byte).
  2. A new replay-oracle test exercises `cake_signal.py` against a captured single-tin besteffort CAKE state fixture and produces signal values consistent with the diffserv4 oracle for the same load profile.
  3. `cake_params.allow_wash` reads as `False` by default; with `allow_wash: false` the qdisc args list excludes `wash`; with `allow_wash: true` the args list includes `wash`. D-08 transparent-bridge protection (`EXCLUDED_PARAMS = {"nat", "wash", "autorate-ingress"}`) still excludes `nat` and `autorate-ingress` unconditionally.
  4. SAFE-09 phase-boundary check: control-path source diff vs v1.43 close (`6508d68`) is bounded to `cake_signal.py` (TOPO-01) and the TOPO-02 set (`cake_params.py`, `backends/linux_cake.py`, `backends/netlink_cake.py`, `check_config_validators.py`); no threshold/EWMA/dwell/deadband/burst values changed. Wash readback validation (`build_expected_readback()` + `_VALIDATE_KEY_TO_TCA`) is explicitly out of Phase 205 scope — Phase 205 validates emission only; Phase 209 owns live qdisc readback.
**Plans:** 5/5 plans complete
- [x] 205-00-PLAN.md — Operator gate: SAFE-09 allowlist expansion pre-approval + planning-artifact amendment
- [x] 205-01-PLAN.md — Wave 0: failing tests for besteffort aggregation, allow_wash gate, backend wash emission, validator allowlist
- [x] 205-02-PLAN.md — TOPO-01: tin-agnostic cake_signal.py via _active_tin_indices helper; diffserv4 byte-identical
- [x] 205-03-PLAN.md — TOPO-02 end-to-end: cake_params.py allow_wash gate + linux_cake/netlink_cake wash emission + check_config_validators allowlist
- [x] 205-04-PLAN.md — SAFE-09 boundary verification + ROADMAP amendment checkpoint

#### Phase 206: A/B replay harness + rollback gates

**Goal:** A deterministic A/B replay harness captures pre-migration controller behavior against the 2026-04-22 out-of-band flent finding, and rollback criteria are encoded as a machine-readable predeploy gate script that fails closed.

**Depends on:** Phase 205 (replayed code is the post-refactor controller; baseline must exist before Phase 209 ships)
**Requirements:** TOPO-04, TOPO-05
**Success Criteria** (what must be TRUE):
  1. The A/B replay harness reuses the Phase 193/194/195 replay pattern, ingests a committed deterministic golden fixture, and emits RRUL p99 latency, throughput, and jitter for both pre- and post-migration controller configurations in a single run.
  2. The harness produces an A/B summary JSON whose schema is stable enough that a follow-up post-canary diff is a one-line consumer change.
  3. `PHASE-205-ROLLBACK-GATES.md` (or equivalent) documents the three rollback triggers in operator-readable form: RRUL p99 latency regression > 5%, Spectrum daemon restart-rate increase, pressure-state transition-rate increase per hour.
  4. A predeploy gate script exits non-zero when any of the three rollback triggers is breached against a captured baseline; an operator dry-run on the v1.43 baseline exits zero.
  5. SAFE-09 phase-boundary check: zero control-path source diff introduced in this phase (harness + scripts only, no `src/wanctl/` edits beyond Phase 205's bounded set).
**Plans:** 9/9 plans complete
- [x] 206-01-PLAN.md — A/B replay harness core: golden NDJSON fixture + corpus loader + harness CLI emitting schema-v1 A/B summary JSON (TOPO-04)
- [x] 206-02-PLAN.md — Predeploy rollback-gate script + Python core with three threshold checks + tests (TOPO-05)
- [x] 206-03-PLAN.md — Operator-readable rollback doc (PHASE-205-ROLLBACK-GATES.md) + golden-fixture provenance doc
- [x] 206-04-PLAN.md — SAFE-09 phase-boundary verification + cross-plan threshold drift check + fixture SHA256 pin
- [x] 206-05-PLAN.md — Fail-closed gate gap closure: malformed soak NDJSON and restart-counter monotonicity (TOPO-05)
- [x] 206-06-PLAN.md — Fail-closed shell wrapper gap closure: missing value-consuming option values ABORT rc=2 (TOPO-05)
- [x] 206-07-PLAN.md — Fail-closed metric-source guard: mixed RRUL sources ABORT rc=2 instead of mixed-unit BLOCK (TOPO-05)
- [x] 206-08-PLAN.md — Gap closure follow-up

#### Phase 207: Soak / harness hardening (v1.43 closeout-routed)

**Goal:** The v1.43-deferred soak/harness debt is closed: source-diff verifier is trustworthy without manual compensation, soak captures survive transient curl/jq blips, the dual-gate legacy block is gone, and CALIB-02's YAML-promotion question has an explicit YES/NO answer with rationale.

**Depends on:** Nothing (touches scripts and aggregator only — no controller source; safely interleavable with Phases 205/206)
**Requirements:** HRDN-01, HRDN-02, HRDN-03, HRDN-04
**Success Criteria** (what must be TRUE):
  1. `scripts/check-safe07-source-diff.sh` exits non-zero when there are uncommitted or staged edits inside `src/wanctl/`; running it on a clean tree exits zero. The SAFE-09 closeout gate no longer requires a manual verifier compensation step (HRDN-01).
  2. `scripts/soak-capture.sh` runs to completion across a simulated 24h soak in which a single `curl`/`jq` invocation fails transiently; the run records the failure under a bounded counter and only aborts when the documented failure-rate threshold is exceeded (HRDN-02).
  3. The `secondary_gate_legacy` block is removed from `aggregate_watchdog()` in `scripts/soak_summary_aggregate.py`; only the completed-window dual gate remains; `tests/test_phase_204_watchdog.py::TestV142WatchdogRegression` is either retired or rewritten against the new contract and the full test suite passes (HRDN-03).
  4. CALIB-02 threshold YAML-promotion has an explicit YES/NO decision recorded in CHANGELOG with rationale. If YES: `continuous_monitoring.upload.calib_02_threshold` is exposed with restart-required semantics, autorate validator schema entry, and default `175` matching `scripts/calib_02_threshold.json`. If NO: rationale references CALIB-04 PASS evidence (HRDN-04).
  5. SAFE-09 phase-boundary check: zero control-path source diff in this phase (scripts + aggregator + tests only; the optional CALIB-02 YAML knob, if YES, lives in config schema not threshold logic).
**Plans:** 5/5 plans complete
- [x] 207-01-PLAN.md — HRDN-01: fail-closed source-diff verifier (scripts/check-safe07-source-diff.sh dirty-tree pre-check) + pytest coverage
- [x] 207-02-PLAN.md — HRDN-02: soak-capture transient-failure tolerance (scripts/soak-capture.sh bounded counters + sidecar TSV) + pytest coverage
- [x] 207-03-PLAN.md — HRDN-03: legacy gate cleanup (atomic 5-site sweep: aggregator + 2 test files + docs + CHANGELOG)
- [x] 207-04-PLAN.md — HRDN-04: CALIB-02 YAML-promotion NO decision (CHANGELOG entry only; JSON file byte-identical)
- [x] 207-05-PLAN.md — SAFE-09 phase-boundary verification: four-surface diff check + post-HRDN-01 self-test + defensive plan-grep

#### Phase 208: Carry-on quick-tasks (T17a / T9 / T12)

**Goal:** Three small carry-on items land as a single bundle: aggregator schema is stable across the v1.43→v1.44 transition with the legacy regression retired, operators can read per-WAN ingestion rate from `wanctl-history`, and `operator_summary.py` no longer raises on permission-denied digest writes.

**Depends on:** Phase 207 (HRDN-03 retires the legacy regression test in the same direction TOOL-01 stabilizes the schema; Phase 208 confirms the schema contract end-to-end after the retirement)
**Requirements:** TOOL-01, TOOL-02, TOOL-03
**Success Criteria** (what must be TRUE):
  1. `scripts/soak_summary_aggregate.py` produces an output schema that round-trips through both a v1.43 reference soak summary and a v1.44 fresh soak summary unchanged; the legacy regression test is retired in the same commit that confirms the new contract (TOOL-01, T17a).
  2. `wanctl-history --ingestion-rate` prints per-WAN rows/sec plus a windowed mean in operator-readable form, and emits a stable JSON object when `--json` is set; both outputs derived from `src/wanctl/storage/reader.py` (TOOL-02, T9).
  3. `src/wanctl/operator_summary.py` wraps the digest write in `try/except OSError`; an injected permission-denied write logs a stable skip-message and does not propagate; a unit test pins both the no-raise behavior and the skip-message format (TOOL-03, T12).
  4. SAFE-09 phase-boundary check: control-path source diff vs v1.43 close stays bounded to the cumulative TOPO-01/TOPO-02/TOOL-03 + `__init__.py` set. TOOL-01 and TOOL-02 land in scripts/CLI/storage-reader, not the control loop.
**Plans:** 4/4 plans complete
- [x] 208-01-PLAN.md — TOOL-01: aggregate_watchdog() fail-closed guard for unknown gate_column/statistic + v1.43/v1.44 schema round-trip
- [x] 208-02-PLAN.md — TOOL-02: wanctl-history --ingestion-rate flag (per-WAN rows/sec table + object-shaped JSON)
- [x] 208-03-PLAN.md — TOOL-03: operator_summary print_digest() narrow permission/IO guard with stable stderr skip prefix
- [x] 208-04-PLAN.md — Gap closure: keep explicit legacy/ad-hoc `--db` paths in scope when `--wan` is used with `--ingestion-rate`

#### Phase 209: Spectrum config migration, production canary, and docs

**Goal:** Spectrum runs `920Mbit besteffort wash` in production behind the documented two-snapshot rollback ritual, post-migration soak evidence matches or improves on the v1.43 baseline distribution, ATT remains byte-identical, and the docs reflect the new topology-correct contract.

**Depends on:** Phase 205 (tin-agnostic signal + allow_wash gate must exist), Phase 206 (A/B harness + rollback gate script must exist), Phase 207 (HRDN-01 fail-closed source-diff verifier required by SAFE-08/SAFE-09 closeout)
**Requirements:** TOPO-03, TOPO-06, TOPO-07, SAFE-08, SAFE-09
**Success Criteria** (what must be TRUE):
  1. `configs/spectrum.yaml` migrates: `ceiling_mbps: 940 → 920`, `diffserv: diffserv4 → besteffort`, `allow_wash: true`. `configs/att.yaml` is byte-identical to v1.43 close (`6508d68`); `scripts/check-safe07-source-diff.sh` extended with the ATT-config whitelist mode confirms it (TOPO-03, SAFE-08).
  2. The production canary on Spectrum executes the v1.42/v1.43 two-snapshot rollback ritual: predeploy gate (Phase 206 script) → deploy → 24h soak under post-migration controller → verification soak comparing zone × cause-tag distributions to the v1.43 baseline (`20260509T183037Z`). The Phase 206 rollback gates do not trip (TOPO-06).
  3. `CHANGELOG.md`, `docs/BRIDGE_QOS.md`, and `docs/CONFIGURATION.md` document besteffort/wash semantics, the per-WAN `allow_wash` knob (default-false), and the topology rationale (DSCP not preserved across ISP) (TOPO-07).
  4. SAFE-09 closeout: end-to-end control-path source diff between v1.43 close (`6508d68`) and v1.44 close is bounded to `cake_signal.py` (TOPO-01), the TOPO-02 set (`cake_params.py`, `backends/linux_cake.py`, `backends/netlink_cake.py`, `check_config_validators.py`), `operator_summary.py` (TOOL-03), and `src/wanctl/__init__.py` (version bump). HRDN-01's fail-closed verifier confirms mechanically. Phase 209 also adds wash to `build_expected_readback()` + `_VALIDATE_KEY_TO_TCA` so live readback validates the new qdisc state.
  5. Version bump `1.43.0 → 1.44.0` propagates across `pyproject.toml`, `src/wanctl/__init__.py`, and `docker/Dockerfile`.
**Plans:** 4 plans
- [x] 206-01-PLAN.md — A/B replay harness core: golden NDJSON fixture + corpus loader + harness CLI emitting schema-v1 A/B summary JSON (TOPO-04)
- [x] 206-02-PLAN.md — Predeploy rollback-gate script + Python core with three threshold checks + tests (TOPO-05)
- [x] 206-03-PLAN.md — Operator-readable rollback doc (PHASE-205-ROLLBACK-GATES.md) + golden-fixture provenance doc
- [x] 206-04-PLAN.md — SAFE-09 phase-boundary verification + cross-plan threshold drift check + fixture SHA256 pin

### Progress

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 205 — Tin-agnostic CAKE signal + allow_wash gate | 5/5 | Complete    | 2026-05-14 |
| 206 — A/B replay harness + rollback gates | 9/9 | Complete   | 2026-05-15 |
| 207 — Soak / harness hardening | 5/5 | Complete    | 2026-05-15 |
| 208 — Carry-on quick-tasks (T17a / T9 / T12) | 4/4 | Complete   | 2026-05-16 |
| 209 — Spectrum config migration + canary + docs | 0/0 | Not started | - |

### Coverage Map (v1.44)

| Requirement | Phase |
|-------------|-------|
| TOPO-01 | Phase 205 |
| TOPO-02 | Phase 205 |
| TOPO-03 | Phase 209 |
| TOPO-04 | Phase 206 |
| TOPO-05 | Phase 206 |
| TOPO-06 | Phase 209 |
| TOPO-07 | Phase 209 |
| HRDN-01 | Phase 207 |
| HRDN-02 | Phase 207 |
| HRDN-03 | Phase 207 |
| HRDN-04 | Phase 207 |
| TOOL-01 | Phase 208 |
| TOOL-02 | Phase 208 |
| TOOL-03 | Phase 208 |
| SAFE-08 | Phase 209 (mechanical closeout; verified at every phase boundary) |
| SAFE-09 | Phase 209 (mechanical closeout; verified at every phase boundary) |

**Coverage:** 16/16 ✓ (no orphans, no duplicates)

### Cross-Cutting Notes

- **SAFE-08 / SAFE-09 verification cadence:** Both invariants are checked at every phase boundary (205, 206, 207, 208, 209), not only at Phase 209. Phase 209 owns the mechanical closeout because that is where the ATT-config whitelist comparison and the final control-path diff land.
- **Harness-before-deploy ordering:** Phase 206 (A/B harness + rollback gate script) must complete before Phase 209's production canary ships — the rollback gate script is a required input to Phase 209's predeploy step.
- **HRDN-01 as SAFE closeout dependency:** Phase 207's HRDN-01 (fail-closed source-diff verifier) is a prerequisite for the SAFE-09 closeout gate in Phase 209; the manual-compensation workaround used in v1.43 is not acceptable for v1.44 close.
- **Parallel-eligible:** Phase 207 touches no controller source and is interleavable with Phases 205/206. Phase 208 sequences after Phase 207 because TOOL-01 confirms the schema contract that HRDN-03 retires.
- **ATT untouched:** No phase introduces ATT config edits or ATT-specific code-path changes. SAFE-08 is a mechanical invariant verified by extended source-diff verifier in Phase 209.

## Backlog

(None at root scope. Historical 999.x items lived under earlier ROADMAPs and are preserved in milestone archives.)

### Deferred to v1.45+ (per REQUIREMENTS.md "Future Requirements")

- **SEED-005** conservative UL tuning sweep (prereqs satisfied; deferred to avoid 3 consecutive UL-only milestones)
- **T6 / T7** storage-hygiene phase (autorate flat-gauge fire-on-change + CAKE tin skip-on-unchanged consumer audit)
- **T17(b)** CALIB-02 YAML knob shape evaluation (gated on SEED-005 outcomes; HRDN-04 in v1.44 only answers YES/NO)
