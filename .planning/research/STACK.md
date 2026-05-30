# Stack Research — v1.47 Measurement Evidence Closure

**Domain:** Network measurement forensics (target/path sensitivity matrix) + per-WAN SQLite ingestion-rate observability on a production CAKE controller.
**Researched:** 2026-05-30
**Confidence:** HIGH (everything proposed is either Python stdlib, already on the dev VM, or already shipped wanctl tooling)

---

## TL;DR

v1.47 needs **zero new third-party dependencies**. Both scopes are composition of existing tools:

- **Scope A (tcp_12down target/path matrix)**: extend the Phase 213 baseline harness + Phase 214 fail-closed flent extractor + classifier with three new thin shell/Python wrappers (multi-target orchestrator, time-of-day gate, matrix-comparison aggregator). Statistical comparison method: **Mann-Whitney U + bootstrap CI** computed in stdlib (`random` + `statistics`), no SciPy.
- **Scope D (ingestion-rate observability)**: extend the existing `wanctl-history --ingestion-rate` subcommand (v1.44 Phase 208 TOOL-02) with per-metric breakdown and a `--digest`-style periodic summary. Optional additive `/health.metrics.ingestion` field for real-time exposure. No new runtime code path; **read-only consumers only**.

**Anti-additions (do NOT introduce):** Prometheus, Grafana, pandas, numpy, scipy, asyncio framework, new daemon, new systemd unit. The controller is read-only for v1.47; performance is not the limit (Phase 217: cycle p99 6.9 ms over 71,560 samples).

---

## Recommended Stack

### Core Technologies (all already present)

| Technology | Version | Purpose | Why Standard |
|------------|---------|---------|--------------|
| Python stdlib `gzip`, `json`, `statistics` | 3.11+ | `.flent.gz` raw ping percentile extraction | Phase 214 already standardized on this; D-10 (Phase 214) mandated stdlib-only and the extractor is pinned-fixture verified. **[VERIFIED: `scripts/phase214-extract.py`]** |
| Python stdlib `random`, `math` | 3.11+ | Bootstrap confidence intervals (resample with replacement) for matrix-cell comparison | Stdlib-only; reproducible via `random.Random(seed)` for replayable golden tests. Phase 203/204 already used stdlib aggregators with deterministic golden fixtures. |
| `flent` 2.1.1 (system) | 2.1.1 | `tcp_12down` test driver (12-flow TCP download with ICMP ping latency series) | Pinned by Phase 213 manifest (`flent_version=2.1.1, Python 3.12.3`). Multi-target is `-H <host>`; no library version bump needed. **[VERIFIED: Phase 213 manifest]** |
| `bash`, `jq` 1.6+, `curl`, `ssh`, `sqlite3 -readonly` (remote) | per dev VM | Orchestration shell, manifest emission, source-bind egress probe, read-only metrics.db pulls | All four are the Phase 213/214 harness substrate. No version bumps. |
| `pyroute2` (existing) | controller-only | Not exercised in v1.47 read-only scope | Mentioned only to confirm: no netlink work in v1.47. |
| Phase 213 leaf scripts | current HEAD | Reused unchanged: `phase213-baseline-capture.sh`, `phase213-health-poller.sh`, `phase213-alert-window.sh`, `phase213-steering-snapshot.sh` | Bind-map handling, 1Hz `/health` NDJSON poll, egress refuse-on-mismatch, redacted steering snapshot, poller PID trap cleanup. |
| Phase 214 analyzer chain | current HEAD | Reused with multi-cell input: `phase214-extract.py`, `phase214-align.py`, `phase214-classify.py`, `phase214-matrix-summary.py` | Six-driver classifier and aligned-window joiner are link-agnostic — they don't know or care which target host produced the `.flent.gz`. |
| `wanctl-history --ingestion-rate` | v1.44 Phase 208 (TOOL-02) | Per-WAN rows/sec over a window, table or JSON, `--db` + `--wan` filters | Already lands on operator surface. v1.47 extends it; does not replace it. **[VERIFIED: `src/wanctl/history.py:438-715`]** |
| `wanctl-operator-summary --digest` | v1.44 Phase 208 (TOOL-03) | Per-WAN tolerant digest with schema-corruption preservation | Pattern reuse target for v1.47 ingestion-rate digest mode. |

### New Scripts and Modules (v1.47 deliverables)

| File | Phase | Purpose | Net new code |
|------|-------|---------|--------------|
| `scripts/phase21X-tcp12down-matrix.sh` | Scope A orchestrator | Iterate (target × path × window) cells, call `phase213-baseline-capture.sh --tests tcp_12down --wans <wan>` per cell, label each RUN dir with `phase21X-cell.json` sidecar (`{target, path, window, repetition}`) | ~150 lines bash |
| `scripts/phase21X-targets.json` | Scope A config | Target host registry: `{name, dns, expected_ip, role: "canonical"|"supplemental"|"libreqos", flent_host_arg}`. Includes Dallas (`dallas`/canonical), Vultr Dallas (`zylone.org`), Vultr Chicago (`planetcaravan.org`), LibreQoS Dallas. | ~60 lines JSON |
| `scripts/phase21X-matrix-compare.py` | Scope A aggregator | Read N RUN dirs (already extracted by `phase214-extract.py`), group by (target × path × window), produce per-cell p50/p95/p99 with bootstrap 95% CI and Mann-Whitney U vs canonical cell. Stdlib only. Fail-closed on insufficient samples per cell. | ~250 lines Python |
| `scripts/phase21X-matrix-report.py` | Scope A reporter | Render Markdown matrix table + signal-disposition verdict (`target_sensitive` / `path_sensitive` / `window_sensitive` / `confounded` / `null_result`). | ~150 lines Python |
| `scripts/phase21X-ingestion-digest.py` | Scope D extender | Per-WAN per-table rows/sec breakdown over rolling/explicit windows; supports `--digest` flag mirroring `wanctl-operator-summary --digest` tolerance semantics. Optionally writable as cron sidecar. | ~200 lines Python |
| (Optional) `src/wanctl/health_check.py` patch | Scope D real-time | Additive `/health.metrics.ingestion` block (per-WAN `rows_per_sec_60s`, `rows_per_sec_300s`, `last_write_unix`, per-table counts). Read-only daemon emission; control loop ignores it. | <80 lines diff |
| `tests/test_phase21X_*.py` | Both | Wave 0 unit tests with pinned `.flent.gz` fixtures, pinned `metrics.db` fixtures, bootstrap CI golden seeds, and Mann-Whitney U reference values. | ~400 lines |

**No new package dependencies.** All scripts are stdlib + reused Phase 213/214 chain.

### Supporting Libraries (already in tree, recap)

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| Python `csv` (stdlib) | 3.11+ | Optional sidecar export of matrix cells for operator spreadsheet inspection | Only if operator requests; JSON is canonical |
| `pytest` (existing) | per pyproject | Wave 0 unit tests + replay regressions for matrix-compare bootstrap and ingestion digest | Mandatory before live matrix run (Phase 214 Pitfall 5: don't burn time-of-day slots on tooling bugs) |
| `ruff`, `mypy`, `black` (existing) | per pyproject | Lint/type/format for the new Python scripts | Project standard via `make ci` |

### Development Tools

| Tool | Purpose | Notes |
|------|---------|-------|
| `make ci` | Run full lint/type/test pipeline before merge | Project-standard gate. Already wired. |
| `.venv/bin/pytest` | Direct test execution | Per project CLAUDE.md: use venv directly, not `pip install`. |
| `flent --list-tests` | Verify `tcp_12down` (synthesized to `tcp_ndown -p 12`) is still resolvable on dev VM | Sanity check pre-matrix. No version bump. |

---

## Installation

**Nothing to install.** All requirements satisfied by the existing dev VM:

```bash
# Verify (do not install) — all should already report present:
which flent jq curl ssh sqlite3
flent --version          # expect 2.1.1
python3 --version        # expect 3.11 or 3.12
.venv/bin/pytest --version
```

If any of the above are missing on the dev VM, that is a Phase 213 prerequisite drift — treat as a separate triage, not v1.47 scope.

---

## Statistical Method Choice (Scope A)

The Vultr Dallas/Chicago supplemental finding (p99 745/651 ms) was a **single off-peak run per target**. To confirm or kill the target/path sensitivity hypothesis, each matrix cell needs enough samples for a defensible comparison.

### Recommended: Mann-Whitney U + Bootstrap 95% CI

| Decision | Choice | Rationale |
|----------|--------|-----------|
| **Sample size per cell** | ≥3 independent flent runs per (target × path × window) cell, each 30s `tcp_12down` (D-03 Phase 214 default duration) yielding ≥600 raw ping samples | 3 runs per cell gives bootstrap CI room; 30s preserves Phase 214 comparability; ≥600 samples means the p99 index is on a real sample, not an interpolated tail. |
| **Cell comparison method** | **Mann-Whitney U** (two-sided) for "is cell X's tail latency distribution different from canonical cell?" | Non-parametric; ping latency is heavy-tailed and not normal. Stdlib implementation is ~30 lines using `statistics.NormalDist` for the U → z approximation. SciPy not needed for this shape. |
| **Confidence interval method** | **Bootstrap percentile CI (B=2000 resamples)** for per-cell p50/p95/p99 | Distribution-free; matches the Phase 214 sorted-index percentile method already in use. Seedable via `random.Random(seed)` so golden tests stay deterministic. ~50 lines stdlib. |
| **Verdict thresholds** | `target_sensitive` if any non-canonical target's p99 CI lower bound > canonical cell's p99 CI upper bound on the same path/window. `path_sensitive` if Spectrum vs ATT cells diverge with non-overlapping CIs on the same target/window. `null_result` if all CIs overlap. | Mirrors Phase 214's D-06 pass/ambiguous/fail rubric, now extended with CI-based decision instead of single-shot threshold. |

### Why not SciPy / pandas / numpy

| Considered | Why rejected |
|------------|--------------|
| SciPy `mannwhitneyu` | Adds ~80 MB install footprint for one function call. Algorithm is publicly documented; <40 lines of stdlib. Project preference: stdlib-first (D-10 Phase 214). |
| `numpy.percentile(method="lower")` | Phase 214 extractor already uses sorted-index method with stdlib. Switching to numpy would diverge from the pinned-fixture verified extractor — actively harmful. |
| `pandas.DataFrame.groupby` | Matrix has at most ~30 cells (5 targets × 3 paths × 2 windows). Dict-of-list is faster to write, faster to test, and matches Phase 214 patterns. |
| `scipy.stats.bootstrap` | Bootstrap with `random.Random(seed)` is ~50 lines. Determinism for golden tests is easier without an external dep version pin. |

### Sample Math (for plan/roadmap sizing)

- 5 targets × 3 paths (Spectrum, ATT, steered) × 2 windows (daytime, off-peak) × 3 runs/cell = **90 flent runs**.
- At 30s/run + ~30s harness overhead per run + per-window gating, this is realistically **two to three operator sessions** spread across multiple days. The matrix runner script must support **resume** (skip cells whose RUN dir already exists with a valid `.flent.gz`).
- Anti-pattern (Phase 214 Pitfall 5): don't burn an off-peak window because the analyzer crashed. Wave 0 unit tests must lock the bootstrap + Mann-Whitney implementation against a stored golden fixture before any live cell runs.

---

## Ingestion-Rate Observability (Scope D)

### What v1.44 Phase 208 already ships (do NOT rebuild)

From `src/wanctl/history.py:438-715` (verified):

- `wanctl-history --ingestion-rate` with `--start`, `--end`, `--wan`, `--db`, `--json` flags.
- Per-WAN rows-per-second over an explicit window.
- Tolerant of per-WAN DB open/write failures (Phase 208 TOOL-03 pattern).
- `format_ingestion_rate_table()` and `format_ingestion_rate_json()` for operator and machine consumers.

### What v1.47 adds

| Surface | Addition | Justification |
|---------|----------|---------------|
| `wanctl-history --ingestion-rate` | New optional `--by-table` flag: break out rows/sec per metric table (`autorate_metrics`, `signal_arbitration_metrics`, `irtt_metrics`, `cake_metrics`, `alerts`, …) within the existing per-WAN bucket. Stays additive to the v1.44 default output. | Phase 218 evidence audits need to know which metric stream stopped writing, not just "ingestion dropped." Operator post-mortems benefit from the same. |
| `wanctl-history --ingestion-rate` | New optional `--rolling=60,300,3600` flag: emit rolling rates over multiple windows in one call. | Replaces ad-hoc multi-invocation patterns. Single SQL pass per window. |
| `scripts/phase21X-ingestion-digest.py` | Periodic CLI digest (CSV/JSON sidecar) for ops review. Mirrors `wanctl-operator-summary --digest` tolerance semantics. Designed to be cron-callable but **NOT installed as a systemd unit in v1.47** (production read-only invariant). | Gives Phase 218 a reproducible audit primitive. |
| `/health.metrics.ingestion` (OPTIONAL, Scope D-2 sub-phase) | Additive per-WAN block: `{rows_per_sec_60s, rows_per_sec_300s, last_write_unix, by_table: {…}}`. Daemon emits; control loop never reads. | Real-time exposure for operator dashboards. **Must be opt-in or always-on additive (existing payload shape unchanged)** — Phase 214 PATTERN5 and the v1.46 spine forbid breaking `/health` payload shape casually. |

### What v1.47 does NOT add

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| Prometheus exporter | Per `### Out of Scope` (PROJECT.md: "Prometheus/Grafana export deferred from v1.23; infrastructure not yet deployed") | The optional `/health.metrics.ingestion` block is JSON-pollable; any future exporter is a separate milestone. |
| Grafana dashboards | Same — no Grafana in production | CLI digest is the operator surface; TUI dashboard (v1.14) consumes `/health` if needed. |
| New SQLite tables or schema migrations | Production read-only invariant for v1.47 | Compute rates from existing per-WAN `metrics.db` row timestamps. |
| New systemd timer/service for digest | v1.46 closeout invariant: zero service mutation; v1.47 read-only until evidence isolates a cause | Ship as CLI; operator runs ad-hoc or via cron stanza documented in `docs/RUNBOOKS/`. Not deployed as a unit. |
| asyncio / aiohttp / FastAPI | The existing `/health` HTTP server is sufficient; the controller does not need an async framework | Stdlib `http.server` already serves `/health`. |
| pandas/numpy/duckdb for ingestion analysis | Per-WAN row counts over a window is one `SELECT COUNT(*) … GROUP BY` per table | Stdlib `sqlite3` already in use by `history.py`. |

---

## Alternatives Considered

| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|-------------------------|
| Stdlib `gzip`+`json` flent extractor (reuse Phase 214) | flent CLI `-f csv` shell-out | Never. D-10 mandate; the pinned-fixture verified extractor is the canonical method. |
| Stdlib Mann-Whitney + bootstrap CI | SciPy `scipy.stats.mannwhitneyu` + `scipy.stats.bootstrap` | Only if the analyzer ever needed multivariate tests (Kruskal-Wallis with post-hoc Dunn). Out of scope for v1.47. |
| Multi-cell matrix via `phase21X-tcp12down-matrix.sh` shell wrapper calling `phase213-baseline-capture.sh` per cell | Fork a new Python capture daemon | Never. Phase 213 orchestrator handles bind-map, egress refusal, poller cleanup. Duplicating it is forbidden by `## Don't Hand-Roll` from Phase 214 research. |
| Extend `wanctl-history --ingestion-rate` with `--by-table` and `--rolling` | New top-level CLI (`wanctl-ingestion`) | Never. Single operator surface; mirrors the v1.44 TOOL-02 pattern. |
| Additive `/health.metrics.ingestion` (read-only, daemon-emitted) | New `/metrics` Prometheus endpoint | Only if production deploys Prometheus. Currently out of scope. |
| Cron-callable digest script (no systemd unit in v1.47) | Permanent systemd timer + delivery to Discord | Only after v1.47 + Phase 218 evidence justify it. v1.47 ships the primitive; future milestone decides delivery. |

---

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| SciPy / NumPy / pandas | Heavyweight deps for problems Python stdlib solves in <100 lines; project explicitly prefers stdlib (D-10 Phase 214, multiple v1.43/v1.44 aggregator patterns) | Stdlib `statistics`, `random`, `math` |
| Prometheus client library | No Prometheus infrastructure deployed; `OBSV-01..04` (v1.23) explicitly deferred | `/health` JSON poll for now |
| Grafana / external dashboard tooling | Same — no Grafana in production | wanctl TUI dashboard (v1.14) + `wanctl-history --digest` |
| asyncio for new orchestrator | The Phase 213/214 chain is bash + offline Python; introducing async adds debugging surface for zero throughput gain on a 30s-per-run synchronous loop | bash orchestrator + stdlib Python analyzer |
| `flent -f summary` text format for percentiles | Version-coupled to flent CLI; harder to unit-test; Phase 214 anti-pattern | `gzip`+`json` raw extractor reading `raw_values['Ping (ms) ICMP']` |
| `data['results']['Ping (ms) ICMP']` (binned/interpolated) | Phase 214 Pitfall 1: synthesized values between real samples, p99 will be smoothed and understated | `raw_values['Ping (ms) ICMP']` with sorted-index percentiles (already pinned-fixture verified) |
| Back-editing Phase 213/214 scripts | D-11 (Phase 214) forbids back-edit; Phase 213/214 fixtures are operator-signed evidence | New `scripts/phase21X-*.{sh,py}` files |
| New SQLite write path from CLI digest | v1.47 read-only invariant | Read-only `SELECT` queries; emit JSON/CSV; never `INSERT`/`UPDATE` |
| Multi-knob production changes from matrix verdict | v1.46 spine + v1.47 goal: "no production tuning unless evidence isolates a cause" | Matrix verdict feeds a Phase 218 follow-up or a deferred v1.48 milestone; not v1.47 controller changes |
| Synthetic event generation for Phase 218 | Explicit ROADMAP constraint: event-gated on natural DOCSIS flapping | Wait for natural event; v1.47 only ships the ingestion-rate audit primitive |

---

## Stack Patterns by Variant

### If Scope A matrix verdict is `target_sensitive` or `path_sensitive`
- Use the existing Phase 214 classifier + matrix aggregator unchanged on the canonical Spectrum/Dallas axis.
- Use the new `phase21X-matrix-compare.py` for the cross-target/path bootstrap CI math.
- Because the verdict justifies follow-up but D-12 (Phase 214) keeps signal-additions observational-first.

### If Scope A matrix verdict is `null_result` (all CIs overlap)
- Use the existing Phase 214 `carried-narrower` todo state and close the supplemental Vultr hypothesis with documented evidence.
- Use the matrix-compare bootstrap output as the closure proof (CI bounds, sample counts).
- Because v1.47 goal explicitly accepts "hypothesis killed" as a valid outcome.

### If Scope D operator validates `/health.metrics.ingestion` block
- Use the additive payload pattern (existing keys untouched, new block under `metrics.ingestion`).
- Update `docs/CONFIGURATION.md` payload shape inventory.
- Because Phase 214 anti-patterns explicitly forbid breaking `/health` payload shape.

### If Scope D operator declines `/health` field (CLI-only)
- Use `wanctl-history --ingestion-rate --by-table --rolling` as the sole exposure.
- Ship `phase21X-ingestion-digest.py` as the cron primitive.
- Because Phase 217 confirms performance is not the limit; no urgency to add a hot-path emission.

---

## Version Compatibility

| Package A | Compatible With | Notes |
|-----------|-----------------|-------|
| Python 3.11 / 3.12 | flent 2.1.1, pyroute2 (existing), `sqlite3` stdlib | Phase 213 manifest pins `Python 3.12.3` on dev VM; production has 3.11+. Both work. |
| flent 2.1.1 | netperf (system, already on `dallas`) | No version concern; `tcp_12down` synthesis is stable. |
| Phase 214 extractor pinned fixture | Any flent ≥2.0 producing `raw_values['Ping (ms) ICMP']` | Schema verified against existing `.flent.gz` artifacts; v1.47 should add one fixture per non-canonical target to lock the schema for those targets too. |
| `wanctl-history` SQLite reader | Per-WAN `metrics-<wan>.db` schema as of v1.44 | New `--by-table` flag must enumerate tables via `sqlite_master` and fail-closed on unknown table set (Phase 208 TOOL-01 pattern). |
| `/health.metrics.ingestion` (if shipped) | Existing `/health` consumers (TUI dashboard v1.14, `wanctl-history`, operator scripts) | Additive-only; existing keys unchanged. Must pass `tests/test_health_check_payload_shape.py`-style guard. |

---

## Integration With Existing Surfaces

| Existing Surface | v1.47 Integration | Constraint |
|------------------|-------------------|------------|
| `scripts/phase213-baseline-capture.sh` | New `phase21X-tcp12down-matrix.sh` calls it once per cell with `--wans <wan> --tests tcp_12down --host <target>` | Do not modify Phase 213 script. Reuse-only. |
| `scripts/phase214-extract.py` (pinned fixture) | Called unchanged on every cell's `.flent.gz` | Do not modify. New fixtures added for non-canonical targets are additive. |
| `scripts/phase214-classify.py` (six-driver classifier) | Called unchanged per cell | Driver classification stays per-cell; cross-cell statistics are the new layer's job. |
| `scripts/phase214-matrix-summary.py` | Reused or extended for multi-axis (target × path × window) summary; if extended, add a `--schema-version` bump | Aggregator schema bump must be documented in `214` evidence README so Phase 215+ consumers stay compatible. |
| `src/wanctl/history.py` (Phase 208 TOOL-02) | `--by-table`, `--rolling` flag additions; existing flags unchanged | Tolerance semantics from Phase 208 TOOL-03 must extend to new flags (per-table read failure → emit `null` for that cell, do not abort). |
| `src/wanctl/health_check.py` (OPTIONAL `/health.metrics.ingestion`) | Additive block only | Payload-shape regression test mandatory; rollback path is "remove the block" with no consumer breakage. |
| `wanctl-operator-summary --digest` (Phase 208 TOOL-03) | Pattern reused by `phase21X-ingestion-digest.py`; not modified | Reference, not modified. |
| `docs/RUNBOOKS/baseline.md` | New runbook `docs/RUNBOOKS/tcp12down-matrix.md` for Scope A | Reuses Phase 213 runbook conventions. |

---

## Sources

- `.planning/milestones/v1.46-phases/214-measurement-collapse-investigation/214-RESEARCH.md` — D-09/D-10 stdlib mandate, Pattern 1 flent extractor schema **[HIGH]**
- `.planning/milestones/v1.46-phases/214-measurement-collapse-investigation/214-REPORT.md` — Vultr Dallas/Chicago supplemental p99 745/651 ms, `carried-narrower` decision **[HIGH]**
- `.planning/milestones/v1.46-phases/213-experience-baseline-harness/213-REPORT.md` — Phase 213 leaf script inventory, manifest schema, bind-map pattern **[HIGH]**
- `.planning/PROJECT.md` — v1.47 goal, v1.46 closeout invariants, deferred OBSV-01..04 Prometheus posture **[HIGH]**
- `/home/kevin/projects/wanctl/CLAUDE.md` — Production change policy: stability > safety > clarity > elegance; read-only spine **[HIGH]**
- `src/wanctl/history.py:438-715` — `wanctl-history --ingestion-rate` existing implementation **[VERIFIED: source read]**
- Phase 214 verified flent.gz schema (`raw_values['Ping (ms) ICMP']`, `metadata.T0`, `metadata.LENGTH`) **[VERIFIED: schema inspection in 214-RESEARCH.md]**
- Mann-Whitney U two-sided test using normal approximation: standard non-parametric reference; algorithm <40 lines stdlib **[MEDIUM — reference algorithm; golden-test pinning compensates for absence of SciPy verification]**
- Bootstrap percentile CI: standard resampling reference; seedable via `random.Random(seed)` **[MEDIUM — same]**

---

*Stack research for: v1.47 Measurement Evidence Closure (Scope A tcp_12down target/path matrix + Scope D ingestion-rate observability)*
*Researched: 2026-05-30*
