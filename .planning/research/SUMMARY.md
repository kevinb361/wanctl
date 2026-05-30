# Project Research Summary

**Project:** wanctl v1.47 Measurement Evidence Closure
**Domain:** Production network measurement forensics (target/path sensitivity matrix) + per-WAN SQLite ingestion-rate observability on a 24/7 adaptive CAKE controller
**Researched:** 2026-05-30
**Confidence:** HIGH

## Executive Summary

v1.47 is a bounded, read-only evidence milestone with two scopes: Scope A confirms or kills the `tcp_12down` target/path sensitivity hypothesis left live by Phase 214 (supplemental Vultr Dallas p99 745ms / Chicago p99 651ms never reproduced on the canonical Spectrum/Dallas matrix), and Scope D lands a per-WAN per-metric ingestion-rate observability tool sized for Phase 218 evidence audits. The milestone closes with an explicit verdict — defect located, hypothesis killed, or carried-narrower — and that verdict is the gate, not performance metrics, not user-perceived quality, and not Phase 218 evidence. Pre-registered kill and defect criteria must be written before any live matrix run; "carried-narrower forever" is explicitly not an acceptable outcome.

The recommended approach is composition of existing tooling with zero new dependencies. Scope A extends the Phase 214 analyzer chain (extractor, aligner, classifier, aggregator) to a new (target x path x window) axis via new `scripts/phase22*` wrappers; the controller source is untouched and mutation-boundary tests enforce that. Scope D extends `wanctl-history --ingestion-rate` (v1.44 Phase 208 TOOL-02) with per-table breakdown and rolling windows; no daemon-side hot path is touched. The optional `/health.metrics.ingestion` additive block remains deferred unless Phase 218 audit evidence proves CLI-only is insufficient. Nothing in v1.47 requires a new third-party dependency.

The key risk is not technical — the tooling is straightforward. The key risk is evidence discipline: confirmation bias toward the Vultr supplemental hypothesis, clustered replicates masking confounders, and single-cell "defect found" calls before corroboration across an orthogonal axis. All three are mitigated by pre-registering kill/defect criteria, including a canonical control cell in every matrix window, and requiring minimum 30-minute replicate spacing per cell.

## Key Findings

### Recommended Stack

v1.47 requires no new package dependencies. Scope A composes the Phase 213 baseline-capture harness and Phase 214 analyzer chain with three new thin scripts: a matrix orchestrator shell wrapper (`phase22X-tcp12down-matrix.sh`, ~150 lines), an operator-supplied matrix definition YAML, and a multi-axis aggregator/reporter in stdlib Python (~400 lines). Statistical comparison uses Mann-Whitney U + bootstrap 95% CI implemented in `statistics`/`random` — the stdlib-only mandate from Phase 214 D-10 holds. Scope D extends `src/wanctl/history.py` additively with `--by-table` and `--rolling` flags plus a `scripts/phase22X-ingestion-digest.py` cron primitive. The optional `/health.metrics.ingestion` block is additive-only if it proceeds and follows the ARCH-09 payload-shape contract.

**Core technologies:**
- Python 3.11+/stdlib (`statistics`, `random`, `math`, `gzip`, `json`, `sqlite3`): all analysis, extraction, and ingestion queries — stdlib-only mandate from Phase 214 D-10; no SciPy/numpy/pandas
- `flent` 2.1.1 (system-installed, pinned by Phase 213 manifest): `tcp_12down` test driver; multi-target via `-H <host>`, no version bump needed
- Phase 213 leaf scripts (reused unchanged): bind-map handling, 1Hz `/health` NDJSON poll, egress refuse-on-mismatch, poller PID trap cleanup
- Phase 214 analyzer chain (reused unchanged): fail-closed flent extractor, per-second aligner, six-driver classifier, matrix aggregator
- `wanctl-history --ingestion-rate` (v1.44 Phase 208 TOOL-02, extended): per-WAN rows/sec; v1.47 adds `--by-table` and `--rolling` flags additively

### Expected Features

**Must have (table stakes — required for v1.47 close):**

Scope A:
- Pre-registered kill and defect criteria written in phase CONTEXT before any live matrix run — top-line requirement, not a subbullet
- Three-target x two-path x three-window canonical matrix (Vultr Dallas, Vultr Chicago, Phase 214 canonical `dallas` control; Spectrum + ATT; off-peak/daytime/prime-time) with >=1 valid attempt per cell and Phase 214 bounded retry policy
- Per-cell verdict via reused Phase 214 six-driver classifier (reflector_loss, loss, jitter, queue_delay, host_kernel, signal_none)
- Per-second `/health` NDJSON alignment per cell (Phase 214 aligner reused unchanged)
- Matrix-level aggregator extended for (target x path x window) cube with matrix-level verdict
- Closeout decision report committing to one of {defect-located, hypothesis-killed, carried-narrower-with-close-with-prejudice-rule}
- Read-only safety attestation + mutation-boundary pytest covering `src/wanctl/`, `configs/`, `deploy/systemd/`, `scripts/`, `tests/fixtures/phase22*/`, `docs/` against allowlist
- Source-bind + egress IP verification per cell (Phase 213 harness already enforces this)
- Supplemental-vs-canonical cell separation in the report

Scope D:
- Per-WAN per-metric ingestion-rate counts (new `--by-table` flag on `wanctl-history --ingestion-rate`)
- Stable JSON schema with `schema_version: 1`
- Surface in `wanctl-operator-summary --digest`
- Unit tests with golden SQLite fixture
- Staleness field (`_snapshot_age_sec` or `_snapshot_unix`) on every snapshot output

**Should have (within v1.47 budget):**
- Replicates >=2 per canonical cell (boosts matrix verdict confidence; doubles wall-clock time so scope carefully)
- Public anycast control target (`1.1.1.1` ping-only) as a sanity floor
- Per-metric category grouping in Scope D output (signal, fusion, alerts, cake_stats)
- Anomaly hint (flag zero-row metric in window) in Scope D output

**Defer (v2+/post-v1.47):**
- Optional `/health.metrics.ingestion` block — defer unless Phase 218 audit evidence proves CLI-only insufficient; if it proceeds, additive-only, never on hot path, ARCH-09 contract applies
- DSCP marking probe — optional differentiator; risk of scope drift
- Threshold-based ingestion-rate alerts — explicit anti-feature for v1.47
- Auto-rotating target pool, ML predictor, schema migration — anti-features
- Prometheus/Grafana export — deferred from v1.23; no infrastructure deployed

### Architecture Approach

Scope A is a pure `scripts/` extension of the Phase 214 wrapper composition pattern. The controller source (`src/wanctl/`) is not touched; zero modification of existing Phase 213/214 scripts. The matrix is defined in operator-supplied YAML (`scripts/phase220-matrix.yaml`) so the harness iterates cells without knowing target identities. Each cell delegates to `phase213-baseline-capture.sh`, then the existing Phase 214 analyzer chain processes offline. The new `phase220-matrix-aggregator.py` rolls per-cell signal sheets into a 3-D cube (`cells` x `rollups.by_target/wan/window` x `matrix_verdict`). Scope D extends `src/wanctl/history.py` and optionally `src/wanctl/storage/reader.py` additively; the controller hot path is not touched. The escalation path to a daemon-side `/health` block is gated on Phase 218 evidence proving CLI-only insufficient.

**Major components:**
1. `scripts/phase220-target-path-matrix.sh` — per-cell wrapper: reads matrix YAML, D-14 triple-check src-diff guard, window-hour gate, delegates to phase213-baseline-capture.sh, writes cell sidecar manifest
2. `scripts/phase220-matrix.yaml` — operator-supplied matrix definition (target x source_bind x window x test x duration); `base_sha` field for mutation-boundary baseline across multi-day runs
3. `scripts/phase220-matrix-aggregator.py` — forked from `phase214-matrix-summary.py`; Mann-Whitney U + bootstrap 95% CI (stdlib); (target x path x window) cube rollup; `matrix_verdict` field
4. `src/wanctl/history.py` (Scope D, additive only) — `--by-table` and `--rolling` flags; `_per_wan_ingestion_rate_bucketed()` helper; tolerant of per-table read failure (emit null, not abort)
5. `scripts/phase221-ingestion-rate-audit.sh` — Phase 218-audit-window snapshot script; calls extended `wanctl-history --ingestion-rate` in JSON mode

**Patterns to follow:**
- Phase 214 Wrapper Composition Pattern: gate entry -> triple-check src/ cleanliness -> delegate to phase213-baseline-capture.sh -> pull journal via SSH -> write phase-owned sidecar manifest
- Stdlib-only Offline Analyzer Pattern: import via `importlib.util.spec_from_file_location` (not regular import) to keep harness decoupled from Python package
- Mutation-Boundary Test Pattern: pytest diffs src/wanctl/ (and configs/, deploy/, scripts/, tests/fixtures/phase22*/, docs/ against allowlist) against the phase base SHA
- Additive `/health` Sub-Block Pattern (escalation only): new optional sub-block under existing key, numeric metrics only, payload-shape regression test mandatory

### Critical Pitfalls

From 12 pitfalls identified, the top 5 for phase planning:

1. **Missing pre-registered kill/defect criteria (Pitfall 2)** — write kill and defect criteria in the phase CONTEXT before any live run; quantitative and time-bound; if verdict is again `ambiguous`, the todo is closed-with-prejudice — no v1.48+ follow-up without new independent evidence. "Carried-narrower forever" is explicitly disallowed.

2. **Confirmation bias on Vultr supplemental evidence (Pitfall 1)** — the matrix must include the Phase 214 canonical `dallas` control cell in every window; cell list cannot be Vultr-only; time windows must not be weighted toward off-peak to favor prior supplemental conditions. The Phase 214 off-peak `RUN-20260529T060507Z` showed clean p99 120ms — that result must be reproducible.

3. **Self-perturbing ingestion-rate observability (Pitfall 5)** — ingestion rate must be computed from SQLite row-count deltas out-of-band, never from live SELECT queries on the hot path or in-daemon write counters; any `/health` field must be O(1) from already-computed counters; post-deploy profiling must confirm `cycle_total.avg_ms` <= 3.0 and `p99_ms` <= 7.5.

4. **Mutation-boundary expansion — fixtures/configs/scripts/docs allowlists (Pitfall 8)** — the read-only boundary must cover more than `src/wanctl/`; test fixtures must encode evidence (`observed_*.json`), not controller specifications (`expected_behavior_*.json`); `docs/` edits are restricted to describing new CLI tools — no threshold-tuning language, no future predictions. This is cross-cutting across all three phases.

5. **Scope D sequencing before matrix execution (Pitfall 11)** — ship Scope D before the matrix-execution phase so the ingestion-rate tool is available if Phase 218 fires during the matrix window; if Phase 218 fires before Scope D ships, the fallback is v1.44 Phase 208 `wanctl-history --ingestion-rate`; document this fallback explicitly in REQUIREMENTS.

## Implications for Roadmap

Based on research, the scope-lock decision is 3 phases at phase numbers starting at 219. ARCHITECTURE proposed A1/A2 as sub-plans within a single phase; FEATURES proposed 3 separate phases; PITFALLS pushes D before matrix execution. Resolution: **3 phases, D first**.

### Phase 219: Scope D — Ingestion-Rate Observability

**Rationale:** Must ship before matrix-execution phase so Phase 218 has the tool available if it fires during v1.47. Scope D is fully independent of Scope A technically (different files, different surfaces). Shipping it first eliminates Pitfall 11 coupling risk. It also exercises the test harness and CI pipeline before the more operator-intensive matrix work.

**Delivers:**
- Extended `wanctl-history --ingestion-rate --by-table --rolling=60,300,3600`
- `scripts/phase219-ingestion-digest.py` (cron-callable, not a systemd unit)
- `wanctl-operator-summary --digest` surfacing
- `tests/test_history_ingestion_rate_bucketed.py` with golden SQLite fixture
- Staleness fields on all snapshot outputs; JSON mode with `schema_version: 1`

**Addresses:** All Scope D P1 features from FEATURES.md

**Avoids:** Pitfalls 5 (no hot-path queries), 6 (per-WAN x per-table is the default output), 7 (staleness fields mandatory), 11 (ships before matrix execution)

**Research flag:** Standard patterns — Phase 208 TOOL-02 is the established extension template. No additional research phase needed.

### Phase 220: Scope A1 — Matrix Runner

**Rationale:** Wrapper and harness must exist before operator-driven evidence collection. This phase is agent-deliverable (no live flent runs required). Contains the CONTEXT document where pre-registered kill/defect criteria are written — Pitfall 2's prevention is locked here before any live data exists. The matrix YAML is operator-authored in this phase, enforcing cell design review (Pitfall 1) before runs begin.

**Delivers:**
- `scripts/phase220-target-path-matrix.sh` (Phase 214 Wrapper Composition Pattern carry-forward)
- `scripts/phase220-matrix.yaml` with pre-registered kill criteria, defect criteria, control cell (Phase 214 canonical `dallas`), anchor cell, and close-with-prejudice rule for `carried-narrower`
- `scripts/phase220-matrix-aggregator.py` (forked from `phase214-matrix-summary.py`; Mann-Whitney U + bootstrap CI; cube rollup)
- `tests/test_phase220_mutation_boundary.py` (src/ + configs/ + deploy/ + scripts/ + fixtures/ + docs/ allowlist)
- Wave 0 unit tests with pinned `.flent.gz` fixtures and bootstrap CI golden seeds

**Gate:** D-14 src-diff guard passing; dry-run regression green; one wet `daytime` cell against Phase 214 anchor (Spectrum/Dallas) to confirm harness reproduces Phase 214 verdict

**Avoids:** Pitfalls 1 (control cell + anchor mandatory in YAML before any runs), 2 (kill/defect criteria in CONTEXT as a gate condition), 8 (mutation-boundary expanded)

**Research flag:** Standard patterns — `phase214-flent-matrix.sh` and `phase213-baseline-capture.sh` are the direct templates. No additional research phase needed.

### Phase 221: Scope A2 — Matrix Evidence + Closeout

**Rationale:** Operator-driven evidence collection followed by agent-assisted aggregation and closeout report authoring. Cannot start until Phase 220's wrapper exists. Evidence collection spans multiple days (proper replicate spacing >=30 min per cell; n>=2 per canonical cell). The closeout decision report is the v1.47 deliverable.

**Delivers:**
- Operator-driven matrix runs (off-peak x daytime x prime-time x N cells) with IP-pinning and mtr snapshots per replicate
- Per-cell `phase214-classify.py` runs -> `signal-sheet.json` artifacts
- `phase220-matrix-aggregator.py` -> `matrix-summary.json` (3-D cube)
- `220-CLOSEOUT.md`: explicit verdict from one of {defect-located, hypothesis-killed, carried-narrower-with-close-with-prejudice-rule}
- Folded `2026-04-08-investigate-tcp-12down` todo closed or carried with a hard stopping rule

**Gate:** Matrix verdict = `defect_located` | `hypothesis_killed` | `carried_narrower` with rationale; per-cell verdict table present; no single-cell defect declaration without corroboration across an orthogonal axis

**Avoids:** Pitfalls 2 (pre-registered criteria applied), 3 (replicate spacing enforced in runbook), 4 (IP-pinning + mtr per replicate), 9 (docs only cite report by reference), 10 (corroboration required for defect-located), 12 (`/health` never cited as quality signal — always paired with flent evidence)

**Research flag:** Operator-execution phase; no agent research phase needed. The CONTEXT document from Phase 220 is the research substitute.

### Phase Ordering Rationale

- D-before-A: PITFALLS Pitfall 11 requires ingestion-rate tool available before Phase 218 fires; Phase 218 is parallel and event-gated and could fire at any time during v1.47
- A1-before-A2: A2 evidence collection is operator-driven; agent delivers the harness in A1, operator captures evidence between agent sessions; closeout report cannot be written until evidence exists
- Pre-registered criteria enforced in A1 CONTEXT: prevents Pitfall 2 by making kill/defect thresholds a gate condition before any live matrix data exists that could bias the threshold choices
- Mutation-boundary expansion is cross-cutting: every phase gates on the expanded allowlist test; Pitfall 8 is structurally prevented, not just reviewed at code review

### Research Flags

Phases with standard established patterns (skip `/gsd-research-phase`):
- **Phase 219 (Scope D):** Extension of Phase 208 TOOL-02; all patterns established; tests have precedent in `tests/test_history_*`
- **Phase 220 (A1 wrapper):** Phase 214 Wrapper Composition Pattern is the template; `phase214-flent-matrix.sh` and `phase213-baseline-capture.sh` are the direct references
- **Phase 221 (A2 evidence):** Operator-driven; CONTEXT document from Phase 220 is the plan; no agent research phase needed

No phases in v1.47 require a research phase. All patterns are established.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | All technologies verified in-tree; STACK.md confirmed `src/wanctl/history.py:438-715`, Phase 213/214 manifests, Phase 208 TOOL-02 surface. No third-party deps introduced. |
| Features | HIGH | FEATURES.md grounded in Phase 214 D-06 contract (existing pass/ambiguous/fail rubric) and Phase 208 TOOL-02. P1/P2/P3/DROP prioritization is unambiguous. |
| Architecture | HIGH | ARCHITECTURE.md anchored on operator-accepted ARCH-01/09/12/17/20 constraints and Phase 214 mutation-boundary contract. Scope D escalation path clearly gated. |
| Pitfalls | HIGH | PITFALLS.md drawn from concrete Phase 214/215/217 artifacts and production controller behavior. All 12 pitfalls include prevention and recovery steps. |

**Overall confidence:** HIGH

### Gaps to Address

- **Matrix cell count and replicate budget:** FEATURES.md estimates 90 flent runs (5 targets x 3 paths x 2 windows x 3 runs) but also notes a bounded variant at ~30 cells. Exact cell set and per-cell replicate count is an operator decision for Phase 220 CONTEXT and matrix YAML authoring — settle at Phase 220 plan time, not at REQUIREMENTS time.

- **Scope D escalation decision timing:** ARCHITECTURE.md correctly defers the CLI-vs-daemon decision to Phase 218 audit evidence. REQUIREMENTS should name the escalation trigger and the fallback (v1.44 Phase 208 CLI as-is) so it is not re-litigated mid-phase.

- **`/health.metrics.ingestion` opt-in gate:** STACK.md flags as optional; ARCHITECTURE.md names a hard stop-line ("if bucketed CLI path satisfies Phase 218 audit needs, do NOT cut the escalation path"). Phase 219 CONTEXT should make this gating explicit.

- **Phase 218 fallback documentation:** Must appear in REQUIREMENTS (not just in research) so it is not forgotten when the milestone opens. Fallback: `wanctl-history --ingestion-rate` from v1.44 Phase 208.

## Sources

### Primary (HIGH confidence)
- `.planning/milestones/v1.46-phases/214-measurement-collapse-investigation/214-REPORT.md` — Phase 214 canonical matrix verdict, supplemental Vultr evidence, six-driver classifier taxonomy, carried-narrower decision
- `.planning/milestones/v1.46-phases/214-measurement-collapse-investigation/214-RESEARCH.md` — D-01..D-14 constraints, stdlib-only mandate, fail-closed extractor schema, mutation-boundary pattern
- `.planning/milestones/v1.46-phases/213-experience-baseline-harness/213-REPORT.md` — Phase 213 leaf script inventory, manifest schema, bind-map pattern
- `src/wanctl/history.py:438-715` — `wanctl-history --ingestion-rate` existing implementation (VERIFIED source read)
- `.planning/PROJECT.md` — v1.47 goal, v1.46 closeout invariants, Phase 218 watch-list posture, joint scope decision 2026-05-30
- `/home/kevin/projects/wanctl/CLAUDE.md` — production change policy (stability > safety > clarity > elegance), read-only spine
- `.planning/intel/arch.md` — ARCH-01, 09, 12, 17, 20 architectural constraints
- Phase 217 production cycle-budget baseline — `cycle_total.avg_ms=2.883`, `p99_ms=6.9` over 71,560 samples

### Secondary (MEDIUM confidence)
- Mann-Whitney U two-sided test using normal approximation — standard non-parametric algorithm; stdlib implementation ~40 lines; golden-test pinning compensates for absence of SciPy verification
- Bootstrap percentile CI via `random.Random(seed)` — standard resampling; seedable for deterministic golden tests

---
*Research completed: 2026-05-30*
*Ready for roadmap: yes*
