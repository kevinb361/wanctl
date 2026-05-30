# Feature Research

**Domain:** Production network-quality forensics (target/path sensitivity matrix) + production-DB write-rate observability for evidence audits on a 24/7 adaptive CAKE controller (wanctl)
**Researched:** 2026-05-30
**Confidence:** HIGH

> **Scope guard:** v1.47 has two bounded scopes: (A) `tcp_12down` target/path sensitivity matrix to confirm-or-kill the Phase 214 hypothesis, and (D) an ingestion-rate observability tool. Everything below is feature-shape research for those two scopes only. Anything that would tune controller thresholds, mutate production hot paths, introduce ML/prediction, or break the read-only posture is an explicit anti-feature, regardless of how reasonable it sounds in isolation.

## Feature Landscape

### Category map

| Category | Scope (A or D) | Examples |
|----------|----------------|----------|
| TARGET | A | Which destination hosts the matrix probes (Vultr Dallas, Vultr Chicago, 1.1.1.1, RIPE Atlas anchor, CDN edge) |
| PATH | A | Egress WAN bind (Spectrum vs ATT vs steered), DSCP/tin marking, IPv4 vs IPv6, intra-ISP vs cross-ISP |
| STATISTICAL | A | Replicates per cell, pass/fail/ambiguous gates, per-cell verdict, matrix-level aggregator, driver attribution, supplemental vs canonical separation |
| WINDOW | A | Time-of-day strata (off-peak, daytime, prime-time), per-window quorum rules, ATT-contrast slot, retry-policy on invalid artifacts |
| OBSERVABILITY | D | Per-WAN per-metric ingestion-rate counts, surfacing (CLI digest vs `/health` vs both), real-time vs windowed, anomaly hints (read-only) |

---

### Table Stakes (Reviewers Expect These)

Features any reasonable reviewer of this matrix or observability tool will ask for. Missing them = report is not closeable.

#### Scope A — target/path sensitivity matrix

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| **Target diversity ≥ 3 hosts** (Vultr Dallas reproduced; Vultr Chicago reproduced; +1 control) | Phase 214 already implicated target sensitivity; a single-target rerun cannot kill the hypothesis | S | Reuse `zylone.org` (Vultr Dallas) and `planetcaravan.org` (Vultr Chicago) from Phase 214 supplemental; add canonical Phase 214 `dallas` netperf target as control; this is two reproductions + one control, not a sweep |
| **Phase 214 canonical target carried as control** (same `dallas` host, same source-bind 10.10.110.226) | Without the canonical cell, you cannot tell if a Vultr result is target-specific or run-specific | S | Already wired through Phase 213 harness; do not refork |
| **Per-cell verdict via the six-driver classifier** (reflector_loss, loss, jitter, queue_delay, host_kernel, signal_none) | Phase 214 classifier exists, is the closure contract, and its taxonomy is what the closeout report has to cite | S | Reuse `scripts/phase214-classify.py` unchanged; do not rewrite |
| **Matrix-level aggregator with explicit pass/fail/ambiguous gates** (default: `p99 > 1000ms` = fail candidate; `p99 < 500ms` clean = pass candidate; middle = ambiguous) | This is the Phase 214 D-06 contract; reusing it makes Phase 214 and v1.47 directly comparable | S | Reuse `scripts/phase214-matrix-summary.py`; extend output schema for target/path axis |
| **Per-second time-aligned `/health` correlation per cell** (1Hz health NDJSON joined to flent window) | Without alignment, "bad p99 while healthy" cannot be claimed; this is the entire Phase 214 forensic contract | S | Reuse `scripts/phase214-align.py` |
| **Fail-closed flent latency extractor** (stdlib `gzip`+`json`, sorted-index p50/p95/p99, raise on missing `raw_values['Ping (ms) ICMP']`) | Phase 213 swallowed missing keys and emitted zeros; Phase 214 fixed it; v1.47 must not regress | S | Reuse `scripts/phase214-extract.py` |
| **One canonical valid attempt per (target, path, window) cell, with bounded retry** (one retry allowed only for invalid artifacts or netperf no-data) | Phase 214 D-02 anti-cherry-pick rule; reviewers will reject any matrix that retried until it got the answer | S | Inherit Phase 214 retry policy verbatim |
| **Manifest-pinned source-bind + egress IP verification per cell** (refuse cell if Spectrum egress != known IP) | Without bind verification, you cannot claim the flow actually used the intended WAN | S | Already in `phase213-baseline-capture.sh` |
| **Read-only safety attestation** (zero `src/wanctl/` edits; zero RouterOS writes; zero service restarts; zero YAML edits; mutation-boundary pytest) | v1.46 closeout invariant + v1.47 scope says read-only until evidence isolates a cause | S | Reuse Phase 214 mutation-boundary tests; rename for Phase A |
| **Closeout decision verdict** (defect located, hypothesis killed, or carried-narrower with rationale) | Operator-stated v1.47 deliverable; the report MUST commit to one of three outcomes, not three open questions | S | Template inherits Phase 214 REPORT shape; closeout section is the single source of truth |
| **Supplemental-vs-canonical separation in the report** (Phase 214 made this distinction; v1.47 must too) | Reviewers can challenge ad-hoc cells; the canonical matrix needs to stand on its own | S | Report has two sections; supplemental cells listed but excluded from matrix verdict |

#### Scope D — ingestion-rate observability

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| **Per-WAN write-rate breakdown** (rows/sec for `metrics-spectrum.db` and `metrics-att.db` separately) | Already shipped in v1.44 Phase 208 `wanctl-history --ingestion-rate`; the v1.47 ask is to extend, not rebuild | S | `_per_wan_ingestion_rate()` is in `src/wanctl/history.py`; build on it |
| **Per-metric breakdown within each WAN** (counts grouped by metric name, not just total rows) | Phase 218 audit needs to ask "is `flapping_dl` writing at the expected rate?", not "is the DB writing" | S | Add `GROUP BY metric_name` to the existing query path |
| **Windowed view** (`--last 1h`, `--last 24h`, default 5m) | Existing CLI already accepts `--last`; reuse | S | Already exists |
| **JSON output mode** (stable schema for scripting + audit cite) | v1.44 already ships this; needed by Phase 218 evidence | S | Already exists; extend schema for per-metric axis |
| **Unreadable-DB tolerance** (0-row entry per WAN, not an exception that masks the other WAN) | v1.44 Phase 208 hardened this; preserve | S | Already done |
| **Documented "what counts as a row"** (1 row = 1 metric sample written by the autorate loop) | Without this, the number is uninterpretable | S | Doc-only |
| **No production hot-path cost** (CLI tool reads, daemon does not emit anything extra) | Hot-path performance is sacred; Phase 217 proved cycle budget headroom is not the limit but write-cost of new fields is non-trivial flash-wear risk | S | Read-only SQL; no daemon code touched |

---

### Differentiators (Real Phase 214 Hypothesis Killer / Operator Value)

Features beyond "minimum closeout report" that make this matrix actually persuasive and the obs tool actually useful.

#### Scope A — target/path sensitivity matrix

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| **Path axis = (Spectrum, ATT) per target** | Lets the matrix answer "is this Spectrum-specific or Vultr-specific?"; ATT-clean Vultr Dallas kills the carrier hypothesis and points to target; ATT-also-bad would reopen target hypothesis | M | Already supported by Phase 213 harness via `--wans`; needs explicit cross-WAN cells, not a single ATT-contrast run |
| **Replicates per cell ≥ 2** (one canonical + one repeat) | Phase 214 had n=1 per cell; the supplemental Vultr cells had n=1 each; reviewers will discount one-shot results | M | Doubles the matrix size; bound carefully to keep total runtime sane |
| **Time-of-day stratification matched to Phase 214** (off-peak, daytime, prime-time; 3 windows × 3 targets × 2 paths = 18 cells if maxed) | Direct comparability with Phase 214 verdicts | M | If 18 is too heavy, drop ATT off-peak and prime-time and keep ATT daytime as a single contrast cell — bounded matrix |
| **Public anycast control target** (1.1.1.1 or 8.8.8.8 via flent ping-only mode) | Anycast control is a sanity floor — if a public anycast endpoint passes from both WANs, the matrix has rejected "global internet broken" as an explanation | S | Cheap; runs as ping-only, not full `tcp_12down` |
| **DSCP marking probe** (one cell at non-default DSCP to test if carrier reclassifies under load) | Phase 214 supplemental hinted at carrier-side effects; one DSCP cell either rules this in or rules it out | M | Risky to add late; mark as optional differentiator |
| **Per-driver attribution honesty** (when classifier returns `signal_none` or `ambiguous`, the report calls it out rather than papering it as "carried-narrower" again) | Phase 214 was honest about `signal_none`; v1.47 has to be at least as honest, or the milestone closes false | S | Inherit Phase 214 disposition logic |
| **Closeout categories beyond binary** (defect-located, hypothesis-killed, carried-narrower-with-explicit-trigger) | Operator already named these three; making "carried-narrower" require a concrete future-trigger condition prevents indefinite carry | S | Report template enforces a "trigger to reopen" field if carried-narrower |
| **LibreQoS or similar third-party corroboration** (Phase 214 used LibreQoS CLI once; treat as supplemental) | Independent measurement lifts confidence when matrix is ambiguous | S | Optional supplemental, never canonical |

#### Scope D — ingestion-rate observability

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| **Surface in BOTH `wanctl-history --ingestion-rate` (CLI) AND `wanctl-operator-summary --digest`** | CLI for ad-hoc audit; digest for periodic operator view; matches existing surface pattern | S | Digest already exists; extend to consume the same per-metric counts |
| **Per-metric counts grouped by category** (signal, fusion, alerts, cake_stats) so Phase 218 audit can scan one block instead of 30 metric names | Operator readability; mirrors `/health` section grouping | M | Categorization table is doc-data; small mapping in `history.py` |
| **Optional `/health` summary block** — read-only one-line summary `{ ingestion_rate_per_min: <N>, last_write_age_sec: <M> }` per WAN | Lets `/health` consumers (TUI, alerting) see a cheap heartbeat without scraping SQLite | M | Only if cost is zero in hot path; piggyback on existing periodic SQLite stats call; **anti-feature if it adds a SQL count per cycle** |
| **Anomaly hint, NOT alert** (e.g., flag when a known metric has zero rows in last window) | Phase 218 audit needs "this looks wrong" affordances; staying short of a real alert keeps scope honest | S | CLI-only flag; no alerting wiring |
| **Stable JSON schema versioned** (`schema_version: 1` field) | Lets Phase 218 cite specific fields without breaking on future shape changes | S | Cheap; do it once |
| **Deterministic fixture for tests** (golden SQLite snapshot with known counts) | History/digest path already has tests; preserve the pattern | S | Inherit Phase 208 fixture style |

---

### Anti-Features (Tempting, Explicitly Out of Scope for v1.47)

Things a reasonable reviewer might propose that would either break the read-only posture, expand scope past confirm-or-kill, or push wanctl toward ML/prediction. These are explicit NOs.

#### Scope A — target/path sensitivity matrix

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| **New controller signal from matrix evidence** (e.g., "add target-quality input to congestion classifier") | Matrix may show real measurement-quality issue | Controller-path change; Phase 214 D-13 / v1.47 read-only posture; needs its own milestone | Carry as observational signal proposal in v1.47 report; controller change requires a separate phase ONLY if v1.47 locates a defect |
| **Auto-rotating target host pool** (controller picks "best" target per cycle) | Sounds like resilience | Adds production hot-path cost; introduces target-selection logic that needs its own correctness proof; flash-wear risk; out of evidence-only scope | Static target list per cell; no daemon target-rotation |
| **ML-based target/path quality predictor** | "We have all this telemetry, let's predict" | Out-of-scope per PROJECT.md; introduces model state machine; opaque failure modes | Statistical thresholds on aggregated cells; report shows raw numbers |
| **Threshold or CAKE tuning based on matrix results** | "We saw bad p99, let's tune" | v1.47 scope explicitly says no tuning unless evidence isolates a cause; "ambiguous" or "carried-narrower" does NOT meet that bar | Closeout report logs the recommendation as future work, not as a v1.47 deliverable |
| **Steering policy change** ("steer away from Vultr-affected paths") | Plausible from supplemental evidence | Steering is a non-negotiable spine; needs its own milestone; v1.46 already carries steering version-drift work | Defer to a separate steering-aware milestone |
| **Synthetic load injection on production WANs** beyond what Phase 213/214 already do | "Let's stress it harder" | Risks production traffic; SAFE-09 / SAFE-14 posture; not closure-grade evidence | Bounded matrix only; same `tcp_12down` shape as Phase 214 |
| **Open-ended sweep across all public Vultr DCs** | "More data is better" | Unbounded scope; not closure-grade; cherry-pick risk | Two reproductions (Dallas+Chicago) + canonical control + one anycast control |
| **Reopen Phase 214 closed dispositions** (e.g., rewrite the classifier) | "Maybe the classifier is wrong" | Phase 214 classifier was operator-accepted; rewriting it inside v1.47 makes A unbounded | Treat Phase 214 classifier as fixed contract; if classifier is wrong, that is its own future phase |
| **`/health` field for per-target quality** | "Operator visibility" | Hot-path cost; needs cross-WAN aggregation; out of v1.47 read-only scope | Document as observational-signal proposal in closeout report |
| **Reopen the canary** ("matrix proves we can push ceiling 18→20 again") | Phase 215 carry forward | Different scope (RECLAIM-04); v1.47 D-02 said evidence-only until a cause is located | Defer per existing carry-forward note |

#### Scope D — ingestion-rate observability

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| **Threshold-based alerts on ingestion rate** ("alert when rows/sec drops below X") | Audit affordance for Phase 218 | Adds alerting surface; needs cooldown/dedupe semantics; v1.47 scope is read-only observability | Anomaly *hint* in CLI/digest output only; real alerting is a future phase |
| **Real-time streaming view** (`watch`-style live update inside daemon) | "Live operator dashboard" | Daemon-side cost; new state machine; hot-path risk | Operator runs CLI `--last 1m`; TUI is already a separate v1.14 surface |
| **Per-cycle ingestion counter inside the autorate hot path** | "Cheap to count there" | Adds hot-path counter; risk to 50ms budget contract; flash-wear if persisted | Count is derived from existing SQLite rows out-of-band; no daemon change |
| **Schema migration** (add `ingestion_audit` table or per-row metadata) | "Make queries faster" | Schema change to production SQLite; rollback-unsafe; v1.46 closeout invariant says zero `src/wanctl` controller-path edits | Operate on existing `metrics` schema via `COUNT(*) ... GROUP BY metric_name`; accept O(scan-window) cost in offline CLI |
| **Predictive write-rate model** ("expected vs observed") | ML temptation | Out of scope; ML anti-feature carries over | Static expected ranges in operator doc; no model |
| **Bundling Phase 218 alert verification into Scope D** | "Phase 218 needs this anyway" | v1.47 explicitly puts Phase 218 in parallel; bundling makes v1.47 unbounded | Ship Scope D so Phase 218 can consume it; do not gate v1.47 close on Phase 218 |
| **`/health` block that adds a SQL count per cycle** | "Make it visible" | Hot-path SQL = flash-wear + cycle-budget hit | Optional `/health` block ONLY if value comes from an already-running periodic stats job; if not free, skip and keep it CLI-only |

---

## Feature Dependencies

```
SCOPE A (target/path sensitivity matrix)

[Fail-closed flent extractor (Phase 214)]                  [reused as-is]
        |
        v
[Per-second aligner (Phase 214)]                           [reused as-is]
        |
        v
[Six-driver classifier (Phase 214)]                        [reused as-is]
        |
        v
[Per-cell verdict] ───┐
                      |
[Matrix aggregator (Phase 214 extended)] ──> [Matrix-level verdict] ──> [Closeout decision report]
                      ^                                                          ^
                      |                                                          |
[Path axis: Spectrum + ATT] ──────────────────────────────────────────┐          |
[Target axis: Vultr-Dallas + Vultr-Chicago + canonical + anycast] ────┘          |
[Window axis: off-peak/daytime/prime-time matched to Phase 214] ─────────────────┘
        |
[Replicates >= 2 per cell] ──enhances──> [Matrix verdict confidence]
[Source-bind + egress IP verification] ──required by──> [Per-cell verdict integrity]
[Read-only safety attestation] ──required by──> [Closeout decision report]
[Supplemental-vs-canonical separation] ──required by──> [Closeout decision report]


SCOPE D (ingestion-rate observability)

[Existing wanctl-history --ingestion-rate (v1.44 Phase 208)]
        |
        v
[Per-metric GROUP BY extension] ──> [Per-metric counts]
                                          |
                                          v
                          [CLI rendering: table + JSON]
                                          |
                                          ├──> wanctl-history --ingestion-rate
                                          └──> wanctl-operator-summary --digest
                                                       |
                                                       v
                                          [Optional /health block]   <-- only if hot-path-free
                                                       |
                                                       v
                                          [Phase 218 audit consumer]
```

### Dependency notes

- **Scope A reuses Phase 214 analyzer chain verbatim.** The extractor, aligner, classifier, and matrix summary are operator-accepted contracts. v1.47 extends the matrix axis (target, path) and the matrix-level aggregator, **not** the per-cell analyzer. Treating the analyzer as fixed is the single biggest scope-control discipline for Scope A.
- **Path axis depends on Phase 213 harness.** The `--wans spectrum,att` pattern is already implemented; the new work is iterating cells across paths, not changing the harness.
- **Replicates per cell vs runtime budget.** Two replicates × 3 targets × 2 paths × 3 windows = 36 cells. At Phase 214's ~30-60s per flent run plus surrounding capture window, that is a real time investment but bounded. Roadmap phase boundary should be chosen with this budget in mind; an early-cut variant (drop ATT off-peak and ATT prime-time; keep ATT daytime only) gets to ~30 cells.
- **Closeout report depends on every other Scope A feature.** It is the v1.47 deliverable. Everything else exists to feed it.
- **Scope D extends Phase 208 incrementally.** The risk is sliding from "extend CLI output" into "add daemon-side instrumentation"; the dependency graph keeps daemon out of the picture entirely except for the optional `/health` block, which is itself gated on being hot-path-free.
- **Scope D is parallel to Scope A.** Different files, different surfaces, no shared dependency. Roadmap can phase them concurrently or sequentially without coupling.

---

## MVP Definition

### Launch with (v1.47 close)

Minimum viable v1.47 — what's required for the milestone to close as evidence-first read-only with an honest verdict.

- [ ] **Three-target × two-path × three-window canonical matrix** (Vultr Dallas, Vultr Chicago, Phase 214 canonical `dallas`; Spectrum + ATT; off-peak/daytime/prime-time) with at least 1 valid attempt per cell and Phase 214-style bounded retry policy — Scope A core
- [ ] **Per-cell verdict via reused Phase 214 classifier**, per-cell driver attribution — Scope A
- [ ] **Matrix-level aggregator extended for (target, path) axis**, producing matrix-level verdict + per-axis breakdown — Scope A
- [ ] **Per-second `/health` correlation per cell** (aligned-window.json artifact) — Scope A
- [ ] **Closeout decision report** committing to one of {defect-located, hypothesis-killed, carried-narrower-with-explicit-trigger} — Scope A
- [ ] **Read-only safety attestation + mutation-boundary pytest** — Scope A
- [ ] **Per-WAN per-metric ingestion-rate counts** via extended `wanctl-history --ingestion-rate` — Scope D
- [ ] **Stable JSON schema with `schema_version: 1`** — Scope D
- [ ] **Surface in `wanctl-operator-summary --digest`** — Scope D
- [ ] **Unit tests + fixture** for the per-metric query path — Scope D

### Add after validation (within v1.47 if budget allows)

- [ ] **Replicates ≥ 2 per cell** for Scope A canonical cells (boosts matrix verdict confidence)
- [ ] **Public anycast control target** (1.1.1.1 ping-only) — cheap, high-value sanity floor
- [ ] **Anomaly hint** in Scope D output (flag zero-row metrics in window)
- [ ] **Per-metric category grouping** in Scope D output

### Future consideration (deferred from v1.47 by design)

- [ ] **DSCP marking probe** — defer unless v1.47 specifically calls it out; risk of scope drift
- [ ] **Observational `/health` field from matrix evidence** — closeout report can recommend it; implementation is a separate phase
- [ ] **Threshold-based ingestion-rate alerts** — Scope D is read-only observability for v1.47
- [ ] **Auto-rotating target pool / steering-aware target picker / ML predictor** — anti-features
- [ ] **Schema migration for ingestion audit** — anti-feature for v1.47

---

## Feature Prioritization Matrix

### Scope A (target/path sensitivity matrix)

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| Reuse Phase 214 extractor/aligner/classifier/aggregator unchanged | HIGH | LOW (S) | P1 |
| Target axis = Vultr Dallas + Vultr Chicago + canonical control | HIGH | LOW (S) | P1 |
| Path axis = Spectrum + ATT, explicit cells | HIGH | MEDIUM (M) | P1 |
| Time-of-day stratification matched to Phase 214 | HIGH | MEDIUM (M) | P1 |
| Matrix-level aggregator extended for (target, path) | HIGH | LOW (S) | P1 |
| Per-second `/health` alignment per cell | HIGH | LOW (S) | P1 |
| Closeout decision report with explicit verdict | HIGH | LOW (S) | P1 |
| Read-only safety attestation + mutation-boundary pytest | HIGH | LOW (S) | P1 |
| Source-bind + egress IP verification per cell | HIGH | LOW (S) | P1 |
| Supplemental-vs-canonical separation | MEDIUM | LOW (S) | P1 |
| Replicates ≥ 2 per cell | MEDIUM | MEDIUM (M) | P2 |
| Public anycast control target | MEDIUM | LOW (S) | P2 |
| LibreQoS supplemental corroboration | LOW | LOW (S) | P3 |
| DSCP marking probe | MEDIUM | MEDIUM (M) | P3 |
| Observational `/health` field proposal in closeout | MEDIUM | LOW (S, doc-only) | P2 |

### Scope D (ingestion-rate observability)

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| Per-WAN per-metric ingestion-rate counts | HIGH | LOW (S) | P1 |
| Stable JSON schema with `schema_version: 1` | HIGH | LOW (S) | P1 |
| Surface in `wanctl-history --ingestion-rate` (extend existing) | HIGH | LOW (S) | P1 |
| Surface in `wanctl-operator-summary --digest` | HIGH | LOW (S) | P1 |
| Unit tests + golden SQLite fixture | HIGH | LOW (S) | P1 |
| Documented "what counts as a row" | MEDIUM | LOW (S) | P1 |
| Unreadable-DB tolerance preserved | HIGH | LOW (S, already done) | P1 |
| Per-metric category grouping | MEDIUM | MEDIUM (M) | P2 |
| Anomaly hint (zero-row flag) | MEDIUM | LOW (S) | P2 |
| Optional `/health` block (hot-path-free) | MEDIUM | MEDIUM (M) | P3 |
| Threshold alerts | n/a | n/a | DROP (anti-feature) |
| Schema migration | n/a | n/a | DROP (anti-feature) |

**Priority key:**
- **P1** — required for v1.47 close; everything in the MVP launch list
- **P2** — add if v1.47 budget allows; preserves the verdict-confidence and operator-readability gains
- **P3** — defer; not required for the v1.47 confirm-or-kill closure
- **DROP** — explicit anti-feature; should not be in the roadmap at all

---

## "Competitor" / Precedent Analysis

This is internal forensics work, not a competitive product. The relevant precedents are:

| Pattern | Phase 214 (predecessor) | LibreQoS bufferbloat grade | RIPE Atlas matrix | wanctl v1.47 approach |
|---------|--------------------------|----------------------------|--------------------|------------------------|
| Target axis | Single canonical `dallas`; supplemental Vultr added late | Single LibreQoS endpoint | Anchor matrix, many vantage points | Vultr Dallas + Vultr Chicago + canonical control + (P2) anycast control |
| Path axis | Single WAN (Spectrum) | Single path | Path-implied via vantage point | Spectrum + ATT explicit |
| Replicates per cell | n=1 | per-run | many | n≥1 baseline; n≥2 as P2 |
| Verdict gate | p99>1000ms fail / p99<500ms pass / between=ambiguous | A+..F grade | per-probe stats | Reuse Phase 214 gate verbatim |
| Driver attribution | Six-driver classifier | Bufferbloat + grade only | per-probe statistics | Reuse Phase 214 classifier verbatim |
| Time-of-day strata | Off-peak/daytime/prime-time | per-run | continuous | Reuse Phase 214 strata verbatim |
| Output shape | Per-cell signal-sheet.md + matrix-summary.json | Single grade per run | per-probe JSON | Reuse Phase 214 shape; extend matrix-summary for new axes |

**Implication for roadmap:** v1.47 Scope A is essentially Phase 214 with the matrix axis extended from "windows only" to "(target × path × window)". The analyzer is fixed; the harness orchestration is the new work. This is a small, well-bounded delta — the right shape for a confirm-or-kill phase.

For Scope D the precedents are even tighter: it is a CLI extension to an existing operator tool. The relevant "competitor" is the existing `wanctl-history --ingestion-rate` itself, which already handles per-WAN counts cleanly; the v1.47 work is per-metric breakdown + digest surfacing.

---

## Sources

- `/home/kevin/projects/wanctl/.planning/PROJECT.md` (v1.47 scope, v1.46 closeout, Phase 214 verdict, ingestion-rate carry from v1.44 Phase 208)
- `/home/kevin/projects/wanctl/.planning/milestones/v1.46-phases/214-measurement-collapse-investigation/214-REPORT.md` (Phase 214 verdict `ambiguous`/`reflector_loss`/`signal none`; supplemental Vultr Dallas p99 745ms / Chicago p99 651ms; LibreQoS Dallas grade B; canonical bounded-retry rules)
- `/home/kevin/projects/wanctl/.planning/milestones/v1.46-phases/214-measurement-collapse-investigation/214-RESEARCH.md` (D-01..D-14 constraints, classifier taxonomy, analyzer chain shape, evidence schema)
- `/home/kevin/projects/wanctl/src/wanctl/history.py` (existing `--ingestion-rate` CLI: `_per_wan_ingestion_rate`, `format_ingestion_rate_table`, `format_ingestion_rate_json`, `--wan` filter, unreadable-DB tolerance)
- `/home/kevin/projects/wanctl/CLAUDE.md` (read-only posture; stability > safety > clarity > elegance; hot-path/flash-wear protection model)
- `/home/kevin/projects/wanctl/.planning/intel/arch.md` and `.planning/intel/files.json` (via RAG: confirmed `wanctl-history` CLI is the canonical operator surface for SQLite-derived observability)

---

*Feature research for: v1.47 Measurement Evidence Closure (Scope A: tcp_12down target/path sensitivity matrix; Scope D: ingestion-rate observability)*
*Researched: 2026-05-30*
