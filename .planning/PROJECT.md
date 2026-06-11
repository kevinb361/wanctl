# wanctl

## What This Is

wanctl is an adaptive CAKE bandwidth controller for MikroTik RouterOS that continuously monitors network latency and adjusts queue limits in real-time, with optional multi-WAN steering for latency-sensitive traffic. On Linux CAKE shapers it additionally supports an external-controller mode where upstream cake-autorate owns per-WAN rate control and wanctl provides the state bridge, health/metrics contract, steering, deployment, and ops tooling (`.planning/cake-autorate-trials/WANCTL_CAKE_AUTORATE_FUTURE.md`).

## Core Value

Sub-second congestion detection with 50ms control loops, achieved through systematic performance optimization and code quality improvements while maintaining production reliability.

## Current Milestone: v1.51 Post-Migration Consolidation

**Goal:** Consolidate the two-mode (native + cake-autorate) reality and close the pre-existing carry-forward stack — repo hygiene, rollback-tooling fixes, and planning-artifact reconciliation, with zero controller-path mutation.

**Target features:**

- **Cleanup boundary encoded first** — binding no-delete list (native controller `autorate_continuous.py`, `wanctl@` deploy path, native tests/config validation, rollback commands/docs) guards the entire sweep; sourced from `WANCTL_CAKE_AUTORATE_FUTURE.md` "Not safe to remove until after ATT migration soak"
- **`phase231-rollback.sh` confirm-path fix** — residual from v1.50 Phase 231 code review; pre-live-rollback hygiene only, NO rollback exercise this milestone
- **Operator-summary digest permission todo closure** — validate live behavior first (v1.44 Phase 208 T12/TOOL-03 may already satisfy it), close with tests or evidence
- **"Safe to remove soon" sweep** — superseded one-off trial scripts, stale Spectrum-native-ownership docs, Spectrum-only hardcoding remnants (per the future-doc cleanup policy)
- **Planning metadata reconciliation** — 12 orphan quick-task slugs (`/gsd-cleanup` sweep), silicom todo/SEED-006 inconsistency (both 2026-04-28 todos still in pending/), Phase 230 retroactive Nyquist validation decision
- **SAFE-15** — controller-path zero-diff at every phase boundary and milestone close (9th consecutive milestone)

**Key context:**

- Joint Claude + Codex scope decision 2026-06-10: consolidation top pick; SEED-006 silicom harness runner-up, explicitly out.
- Out of scope: SEED-007 (deferred — bridge-writer storage-hygiene audit is its own thesis and the biggest scope-explosion risk), ROLE-01 native retirement (time-gated; ~2 days soak is not "observed"), TAIL-01 Spectrum tail (valid future milestone — Codex: managed-inline qdisc path + Dallas repeat branch unexplored, NOT exhausted), SEED-005 (deferred not dead — native wanctl first-class on RouterOS), any live rollback exercise, anything on the future-doc denylist.
- Codex landmine watch: sweep must not touch denylist surfaces; rollback confirm fix ≠ permission to exercise rollback; silicom todo reconciliation must not false-close operationally real bypass work.

## Recently Shipped: v1.50 cake-autorate Migration Hardening (shipped 2026-06-10)

**Delivered:** Made the 2026-06-08 cake-autorate migration reproducible, observable, and provably held. 3 phases (229–231), 8 plans, 19 tasks, 10/10 REQs satisfied, milestone audit `passed` (10/10 integration seams wired). Full record: `milestones/v1.50-ROADMAP.md`, `milestones/v1.50-MILESTONE-AUDIT.md`, phase evidence in `milestones/v1.50-phases/`.

**What shipped:**

- Phase 229 — `deploy.sh --with-att-cake-autorate` at Spectrum parity (six-artifact set incl. silicom watchdog variant); ATT artifact-contract tests + bidirectional deploy-list drift gate; read-only sha256 audit proving live cake-shaper bytes equal repo (DEPLOY-02 ALL EQUAL).
- Phase 230 — soak-monitor watches the live ATT external-controller units instead of disabled `wanctl@att.service`; WAN-parameterized external-mode detection with native fallback; representative-error proof (post-fix catches `errors_1h=3` the pre-fix scan missed).
- Phase 231 — formal migration-held criteria (C1–C4) evaluated read-only against live evidence: both WANs `SOAK-01 PASS`; native rollback proven via double-gated script + both-WAN preflight `overall_pass: true` (Kevin accepted no-mutation provable path, SOAK-02); two-mode doc sweep (DOCS-04); SAFE-14 zero-diff proven at every boundary and milestone close.

**Key context:**

- SAFE-14 (successor to SAFE-07..13) held end-to-end: zero controller-path diff vs `87980bdf`; surface was deploy/test/ops/doc only.
- Generic `$wan` parameterization went only as far as the ATT deploy path required — no symmetry refactor (sibling function, not abstraction).
- **Still deferred (binding Out-of-Scope honored):** ROLE-01 native-controller retirement (event/time-gated on soak), TAIL-01 Spectrum loaded-latency tail, SEED-006/007, CAKE retuning.
- Residual from Phase 231 code review: confirm-path risk in `phase231-rollback.sh` to fix before any future live rollback exercise.

## Recently Closed: v1.49 Spectrum DSCP Tinning Re-evaluation (closed 2026-06-09, overtaken-by-events)

**Outcome:** Phases 225–227 shipped (DSCP trace, Snapshot A anchor, locked GATE-01 thresholds, matched baseline-vs-candidate evidence incl. AB-04 EF arm). Phase 228 verdict/rollback never executed: between 2026-06-05 and 2026-06-08 the operator migrated both WANs from wanctl@ controllers to upstream cake-autorate (`fc47a0c`), moving Spectrum CAKE from bridge-root to member-NIC placement — the topology the verdict gated no longer exists. The Phase 227 evidence direction pointed to REJECT `diffserv4 wash` in the old topology (RRUL p99 +11.5%, EF loss ~44×) but was never formally computed and does not transfer; wash-vs-nowash was independently re-tested under cake-autorate and `wash` won. GATE-02/GATE-03 closed unmet-overtaken. SAFE-13 held through all executed phases. Full record: `milestones/v1.49-ROADMAP.md`, MILESTONES.md.

**Original goal (for the record):** Re-test whether per-tin `diffserv4 wash` CAKE earns its keep on Spectrum now that end-to-end DSCP plumbing exists — confirming or overturning the v1.44 "classification theater" decision with fresh evidence under the current CRS/Ruckus/bridge topology.

**Thesis origin:** Pending todo `2026-06-03-retest-spectrum-diffserv4-wash-after-local-qos-changes` (created 2026-06-03, `area: validation`). Re-opens the decision closed by fulfilled seed SEED-001 — which concluded diffserv4 was theater _because ISPs strip DSCP and the shaper sees unmarked ingress_. The load-bearing premise may no longer hold: CRS switches now apply hardware QoS trust/maps, Ruckus `Tik` QoS mirroring is on, and the cake-shaper bridge can classify download flows into EF/AF41/CS1 _before_ CAKE. v1.49 tests whether marks now survive to CAKE ingress and, if so, whether tinning produces a real latency/jitter win.

**Target features:**

- **DSCP survival trace (read-only):** verify marks survive CRS trust maps → Ruckus mirroring → cake-shaper bridge → CAKE ingress; document where DSCP is set / preserved / stripped. If marks do not arrive at CAKE ingress, diffserv4 remains theater (early-exit finding that confirms v1.44).
- **Spectrum-only diffserv4-wash A/B:** baseline `920/18 besteffort wash` vs candidate `diffserv4 wash` (DL+UL), under a Snapshot A rollback anchor (v1.44 / v1.46 Phase 215 precedent).
- **Evidence capture:** `tc -s qdisc` on spec-router/spec-modem, per-tin counters/drops/backlog/delay under load, Spectrum health/state, RRUL/flent latency-under-load, marked-EF-UDP vs unmarked-UDP vs unmarked-bulk-TCP check, restart-count + pressure-state/transition-rate deltas.
- **Accept/rollback gates:** accept `diffserv4 wash` only on a clear latency/jitter or realtime-flow protection win with no throughput loss, daemon instability, or pressure-state churn; rollback to `besteffort wash` on RRUL p99 regression beyond the v1.44 gate tolerance, higher restart rate, more flapping, UL instability, or no useful non-BestEffort tin separation.
- **Negative result is a valid close** — "keep besteffort wash" closes the milestone cleanly (v1.46/v1.47 evidence-milestone precedent).

**Key context:**

- **ATT untouched** the entire milestone — Spectrum-only A/B. ATT is a different carrier (DSL, not DOCSIS) with different DSCP behavior; the Spectrum finding does not generalize.
- **External network gear (CRS / Ruckus / router) is NOT mutated in-milestone** — read-only end-to-end trace only. Any needed gear change is a separate operator-approved action outside v1.49. The cake-shaper bridge nftables rules (wanctl-owned deploy) may change.
- **SAFE-13** controller-path zero-diff invariant (`wan_controller.py`, `queue_controller.py`, `cake_signal.py`, backends, `alert_engine.py`, fusion) held through the audit + evidence phases; **liftable only if A/B evidence proves a control-path change is warranted** — the "decide after evidence" call is made inside the roadmap, not at milestone open. Same discipline as SAFE-07..12 through v1.43–v1.48.
- Tin-agnostic CAKE signal + `allow_wash` gate already shipped (v1.44 Phase 205); the controller can already drive diffserv4 wash, so the A/B is expected to be a config (`configs/spectrum.yaml`) + validation exercise, not an algorithm change.
- Phase numbering continues from v1.48 (last phase 224) → v1.49 starts at **Phase 225**.
- Phase 218 (v1.45 VERIFY flapping watch-list) continues **event-gated in parallel** — not a v1.49 driver.

## Recently Shipped: v1.48 Steering Runtime Drift Closure (shipped 2026-06-03)

**Delivered:** Aligned the live steering daemon from runtime `1.39` to source `1.47` via sliced audit → offline proof → production canary, closing six milestones of unabsorbed steering evolution without compromising the spine. Canary verdict `kept_aligned`; SAFE-12 controller-path zero-diff held at every phase boundary and at milestone close. 3 phases (222–224), 12 plans, 11/11 REQs (DRIFT/PROOF/CANARY/SAFE-12). Full detail: `milestones/v1.48-ROADMAP.md`, `phases/224-*/224-REPORT.md`.

**What shipped:**

- Phase 222 — git-history drift audit: the sole behavior-changing steering commit (`84ad6aa`) is contract-preserving (`go` disposition).
- Phase 223 — offline replay/fixture harness + clean-restart reproduction (fail-closed documented; risk-acceptance committed).
- Phase 224 — production deploy `1.39 → 1.47`, canary `kept_aligned`, full spine proof (incl. operator-authorized router rule-read `*313`), bounded rollback armed (not fired).

**Key context:**

- Single-thesis milestone — SEED-007 storage hygiene, operator-summary digest permission sweep, and `/gsd-cleanup` orphan sweep all explicitly **out of scope**.
- Joint Claude + Codex scope decision 2026-06-02: STEER-DRIFT-01 selected over runner-up SEED-007 because spine-level drift across six milestones is the highest-leverage bounded risk reduction available post-v1.47.
- Codex pushback adopted: do NOT absorb six milestones as one big rollout — slice it (audit → staging proof → canary with rollback). RECLAIM-04 stays carried indefinitely (Phase 215 bounded VOID already exhausted; no new probe shape).
- Expected SAFE-12 invariant: bounded source surface = steering daemon + its tests/configs/units; controller-path (`wan_controller.py`, `queue_controller.py`, `cake_signal.py`, backends, `alert_engine.py`, fusion) remains zero-diff per the same discipline that held SAFE-07/08/09/11 through v1.43–v1.47.
- Phase 222 shipped 2026-06-02: read-only steering drift audit passed verification 5/5. The sole in-scope steering-surface commit (`84ad6aa`) is behavior-changing but contract-preserving with `go` disposition; SAFE-12 passed committed, staged, unstaged, untracked, and porcelain controller-path checks.
- Phase 223 shipped 2026-06-03: offline steering replay and clean-restart reproduction passed verification 11/11 after Plan 04 gap closure. The clean-restart restart-persistence behavior remains intentionally unfixed, but Phase 224 entry is unblocked by the committed risk-acceptance artifact.
- Phase 218 (v1.45 VERIFY watch-list) continues event-gated in parallel — not a v1.48 driver.
- Folded todo: `2026-04-17-investigate-steering-degraded-on-clean-restart` → reproduced and fail-closed documented in Phase 223; pending todo archival remains an operator/archive decision.

## Recently Shipped: v1.47 Measurement Evidence Closure

**Shipped:** 2026-06-02 (Phases 219–221 complete; Phase 218 continues parallel as event-gated v1.45 VERIFY watch-list)

**Delivered:** Bounded read-only evidence milestone. Scope D (ingestion-rate observability) shipped first per Pitfall 11 to support Phase 218 audit evidence regardless of v1.47 timing. Scope A (`tcp_12down` target/path sensitivity hypothesis) ran an 18-cell target × path × window matrix against pre-registered CRITERIA thresholds locked at Phase 220 plan time. The Phase 221 closeout published `carried_narrower_with_close_with_prejudice_rule` as the authoritative post-D-10-BGP-overlay verdict — raw aggregator returned `defect_located` on three supplemental Vultr cells, but the D-10 BGP overlay excluded those cells because BGP path drift contaminated them mid-run. Folded `2026-04-08-investigate-tcp-12down` todo closed with the CRITERIA-02 close-with-prejudice rule attached verbatim; no v1.48+ reopen permitted without independent new production evidence.

**Key outcomes:**

- **Phase 219 (Scope D, D-first per Pitfall 11)** — `wanctl-history --ingestion-rate --by-table` and `--rolling=60,300,3600` additive JSON envelope with `schema_version: 1` and per-snapshot staleness fields; `wanctl-operator-summary --digest` ingestion-rate block; cron-callable `scripts/phase219_ingestion_digest.py` with atomic-write snapshot persistence + count-based retention. D-27 production cycle-budget: `avg_ms=2.857`, `p99_ms=6.4` over 73,603 samples.
- **Phase 220 (Scope A1)** — Pre-registered 18-cell `scripts/phase220-matrix.yaml` with locked CRITERIA-01 thresholds, ATT egress signature, and `base_sha` source-floor anchor; stdlib + PyYAML cube aggregator with Mann-Whitney U + bootstrap 95% percentile CI (B=2000, seeded); per-cell wrapper composing Phase 213/214 unchanged. Wet daytime dallas/Spectrum rehearsal reproduced the Phase 214 anchor (`ambiguous` / `reflector_loss` / `✓ MATCH`).
- **Phase 221 (Scope A2)** — 54/54 deduplicated valid replicates across 18 cells captured over multi-day operator-driven windows; closeout JSON + 11-section report with pre-/post-D-10-BGP-overlay verdict trace; folded `tcp_12down` todo closed with CRITERIA-02 attached verbatim.
- **SAFE-11 invariant held end-to-end** — zero controller-path source diff across `wan_controller.py`, `queue_controller.py`, `cake_signal.py`, backends, `alert_engine.py`, fusion across all three phases. Expanded allowlist (`configs/`, `deploy/systemd/`, `scripts/`, `tests/fixtures/phase22*/`, `docs/`, additive `src/wanctl/history.py` for Scope D) honored at every phase boundary.
- **Stdlib-only mandate** carried forward from Phase 214 D-10 — no SciPy/NumPy/pandas.

**Carry-forward (parallel to next milestone):**

- **Phase 218 (event-gated v1.45 VERIFY watch-list)** — VERIFY-01 / VERIFY-02 still event-gated on natural production DOCSIS flapping event with `details.peak_transition_count > 30`. **No synthetic event generation per ROADMAP constraint.** Plan only when qualifying evidence exists. INGEST-01..05 tool now available as Phase 218 audit fallback enhancement vs the v1.44 Phase 208 CLI as-is.

<details>
<summary>Archived v1.46 Internet Quality Recovery milestone (collapsed for brevity)</summary>

### v1.46 Internet Quality Recovery (shipped-with-deferral 2026-05-30)

**Shipped:** 2026-05-30 (Phases 212–217 complete; Phase 218 carried as event-gated v1.45 VERIFY watch-list)

**Delivered:** Evidence-first quality recovery. Production drift inventoried; experience baseline harness operational; measurement-collapse classifier returned `ambiguous`/`reflector_loss` with severe loaded p99 NOT reproduced in the official Spectrum/Dallas window; upload-reclaim canary tried ceiling 18→20 and rolled back safely after bounded VOID exhausted on three attempts; Phase 196 refractory thread closed as no-change/resolved-by-197; production cycle-budget profiled at 71,560 timing samples and the profiling baseline todo closed as no-action. v1.45 VERIFY-01/02 carried forward to Phase 218.

**Key outcomes:**

- Production state inventoried with D-08 secret-safe redaction; **steering runtime `1.39` vs source `1.45` drift surfaced** as known unaligned.
- Single-command per-WAN experience baseline harness with offline six-bucket signal classification.
- Six-driver measurement-collapse classifier; canonical Spectrum verdict `ambiguous`/`reflector_loss`/`signal none`.
- One-knob upload ceiling canary (`18 → 20`) with Snapshot A rollback anchor; **no quality reclaim** at ceiling 20 — Spectrum safely rolled back to 18.
- Phase 196 queue-primary refractory thread closed as no-change/resolved-by-197 with evidence cite.
- Spectrum profiled at 50ms cycle interval: `cycle_total.avg_ms=2.883`, `cycle_total.p99_ms=6.9` over `71560` JSON Cycle samples; performance is **not** the quality limit.

**v1.46 carry-forward (now also v1.47 carry):** VERIFY-01 / VERIFY-02 → Phase 218 event-gated.

</details>

<details>
<summary>Archived v1.45 milestone goals (collapsed for brevity)</summary>

### v1.45 Flapping Peak-Counter Window Repair (shipped-with-deferral 2026-05-27 — VERIFY-01 deferred → Phase 218)

**Goal:** Restore the intensity signal in `flapping_dl` / `flapping_ul` alert payloads by tracking peak transition count via a windowed accumulator that survives the per-fire deque clear.

**Shipped:** Per-direction windowed peak accumulator independent of deque-clear-on-fire (Phase 210); preserved alert-once-per-episode semantics; updated `TestFlappingDequeClear` + new tests asserting `peak_transition_count > flap_threshold` during sustained oscillation; Spectrum + ATT deployed at `1.45.0`.

**Deferred:** Production verification — at least one real flapping event with `peak > flap_threshold` — operator sign-off 2026-05-27. Carry-forward now rolled into v1.46 Phase 218 (event-gated, no synthetic generation).

**Root cause located:** `src/wanctl/wan_controller.py:4322-4323` (DL) and `:4353-4354` (UL) — in-fire `deque.clear()` + `peak = 0` destroyed window state at the exact moment the alert fired. Design Option A (windowed peak accumulator) selected over Option B (rename payload) to preserve the intensity signal.

</details>

<details>
<summary>Archived v1.44 milestone goals (collapsed for brevity)</summary>

### v1.44 Topology-Correct CAKE — Spectrum besteffort wash migration (shipped 2026-05-26)

**Goal:** Migrate Spectrum CAKE qdisc from `940Mbit diffserv4 nowash` to topology-correct `920Mbit besteffort wash` (validated out-of-band 2026-04-22 flent), removing classification theater that the carrier strips upstream — without disturbing ATT (DSL, separately validated) and without changing controller thresholds/algorithms.

**Shipped features:**

- **Tin-agnostic CAKE signal + allow_wash gate** (Phase 205) — `cake_signal.py` aggregation now handles both single-tin besteffort and multi-tin diffserv4 without per-deployment branching; per-WAN `cake_params.allow_wash: bool = false` permits `wash` only when explicitly enabled; D-08 transparent-bridge protection preserved by default.
- **A/B replay harness + rollback gates** (Phase 206) — deterministic golden NDJSON-driven A/B replay against the 2026-04-22 out-of-band finding; predeploy gate script with JSON-sourced thresholds (RRUL p99 >5%, restart-rate, transition-rate); fail-closed on malformed inputs (partial counters, zero-duration soak, hidden override, non-finite window).
- **Soak / harness hardening** (Phase 207, v1.43 closeout-routed) — SAFE-07 source-diff verifier fails closed on dirty/staged/untracked `src/wanctl/` surfaces; `soak-capture.sh` tolerates bounded curl/HTTP/jq blips with sidecar TSV diagnostics; `secondary_gate_legacy` block retired; CALIB-02 YAML promotion routed to NO.
- **Carry-on operator tooling** (Phase 208) — completed-window watchdog fail-closed on misconfigured gate columns/statistics; `wanctl-history --ingestion-rate` with `--wan` filtering; `wanctl-operator-summary --digest` tolerates per-WAN open/write failures without masking schema corruption.
- **Spectrum config migration + production canary** (Phase 209) — Spectrum committed config is now `920Mbit besteffort wash`; wash readback validation is controller-internal and hard-fail in both CAKE backends; `docs/BRIDGE_QOS.md` documents the operator topology decision; 24h soak `20260521T222622Z` passed with rollback gates green; SAFE-08 (ATT byte-identical) + SAFE-09 (no controller threshold/algorithm changes) passed mechanically against `6508d68`.

**Closeout invariant held:** Zero controller-path source diff from `6508d68` (v1.43 close) through v1.44 close. The five-file SAFE-09 allowlist (`linux_cake.py`, `netlink_cake.py`, `cake_params.py`, `cake_signal.py`, `check_config_validators.py`) was operator-approved before any source mutation. ATT remained `diffserv4 nowash` throughout.

**Key decisions:**

- 2026-05-09: v1.44 thesis B selected from joint Claude + Codex peer review over alternatives A (storage hygiene), C (UL tuning), D (Silicom buildout). Codex caught SEED-003 premature-closure attempt during scoping.
- 2026-05-14: Phase numbering continues from v1.43 (last phase 204) → v1.44 starts at Phase 205. 16/16 v1.44 REQ-IDs mapped (TOPO 1-7, HRDN 1-4, TOOL 1-3, SAFE 8-9). Spine: SEED-001.
- 2026-05-19: Plan 209-02 closed Phase 206 TOPO-05 nan/inf gap cross-phase via `math.isfinite()` guard (commit `d70112f`). Ratified by v1.44 audit 2026-05-23 and restamped 2026-05-26.
- 2026-05-22: Plan 209-04 PASS after approved SAFE-09 allowlist amendment for `src/wanctl/history.py` (Phase 208 TOOL-02 operator tooling, not controller-path).

**Routed to v1.45+:** SEED-005 conservative UL tuning sweep (prereqs satisfied; deferred to avoid 3 consecutive UL-only milestones); T6/T7 storage hygiene (autorate flat-gauge fire-on-change + CAKE tin skip-on-unchanged consumer audit); T17(b) CALIB-02 YAML knob shape evaluation; phase-196 queue-primary refractory semantics thread; 12 legacy quick_tasks + 12 pending todos awaiting `/gsd-review-backlog`.

</details>

## Current State

**Version:** v1.50 shipped 2026-06-10 (audit passed, tagged). **Production controller state:** both WANs run upstream cake-autorate with wanctl state bridges (`cake-autorate-{spectrum,att}.service` + `-state-bridge.service`, live since 2026-06-08); `wanctl@{spectrum,att}` disabled as the **verified** rollback path (SOAK-02 provable-path, preflight `overall_pass: true` both WANs); steering consumes bridge-written state; native wanctl remains the MikroTik/RouterOS controller and portable default. Spectrum CAKE: member-NIC `diffserv4 wash` 550M base DL autorate / fixed 18M UL. ATT: `diffserv4 nowash` 95M base DL autorate / fixed 19M UL. **Current position:** v1.51 Post-Migration Consolidation — Phase 232 complete; Phase 233 gated repo hygiene sweep ready to plan.
**Tests:** Phase 231 verification passed 16/16; SOAK-01 evidence recorded both-WAN `SOAK-01 PASS`, SOAK-02 closed by Kevin accepting the no-mutation provable path, Phase 231 focused tests passed `16 passed`, hot-path slice passed `673 passed`, and SAFE-14 milestone-close controller-path zero-diff passed. Phase 230 verification passed 7/7; soak-monitor ATT coverage tests passed `.venv/bin/pytest tests/test_soak_monitor_att_coverage.py -q` (`5 passed`), `shellcheck -S error scripts/soak-monitor.sh` passed, code review was clean, and SAFE-14 controller-path zero-diff passed. Phase 229 verification passed 14/14; ATT artifact tests passed `.venv/bin/pytest tests/test_att_cake_autorate_artifacts.py -q` (`6 passed`) and ATT + Spectrum parity tests passed (`11 passed`). Phase 227 focused suite passed `.venv/bin/pytest tests/test_phase227_marked_ef.py tests/test_phase227_qdisc_verify.py tests/test_phase227_safe13_boundary.py tests/test_phase227_evidence_completeness.py -q` (`25 passed`) plus evidence completeness `verdict-ready` and SAFE-13 boundary checks. Phase 226 Plan 05 gap closure passed `.venv/bin/pytest tests/phase226/ -q` (`7 passed`) plus retained evidence hash/provenance and SAFE-13 checks. Phase 223 full post-merge regression passed `5320 passed, 10 skipped, 2 deselected`; steering replay package passed `19 passed`, and `replay_harness.py --all` emits all seven fixtures including `clean-restart-degraded`. Phase 221 verification + closeout published `carried_narrower_with_close_with_prejudice_rule` (post-D-10 BGP overlay, authoritative); raw aggregator `defect_located` overlaid. Phase 220 verification passed 5/5 after the repaired wet rehearsal harness reproduced the Phase 214 dallas/Spectrum daytime anchor and the hot-path + Phase 220 regression slice passed `726 passed`. Phase 219 verification passed 5/5 after full regression `5238 passed, 14 skipped, 2 deselected` and production D-27 cycle-budget evidence (`avg_ms=2.857`, `p99_ms=6.4`). Phase 217 verification passed 12/12; Phase 216 verification passed 11/11; Phase 215 verification passed 25/25; Phase 214 UAT passed 8/8; Phase 213 verification passed 15/15; Phase 212 verification passed 16/16.
**LOC:** ~40,915 Python (src/) — v1.47 source-surface delta was +3,361 / -28 across 15 files (additive observability + matrix tooling; zero controller-path mutation).
**Milestones:** 51 shipped, shipped-with-deferral, or closed (v1.0–v1.50).
**Active milestone:** v1.51 Post-Migration Consolidation (opened 2026-06-10; joint Claude + Codex scope decision). Phase 218 watch is dormant (its instrumentation lives in the native controller, which no longer runs Spectrum/ATT).

**Latest:** v1.51 Phase 232 complete — BOUND-01 cleanup boundary guard now fails closed for protected-file removal, git-index removal, immutable drift, and directory replacement; `phase231-rollback.sh` confirm-path CR-01 is fixed without live rollback; operator-summary digest permission todo closed by v1.44 T12/TOOL-03 validation evidence; SAFE-15 controller-path zero-diff verified at the phase boundary. Advisory follow-ups remain for broader rollback external-unit post-check coverage and CLI missing-value polish.
**Previous:** v1.50 cake-autorate Migration Hardening shipped clean 2026-06-10 — 10/10 REQs, audit passed (10/10 integration seams), git tag v1.50. ATT deploy/test/monitor parity, both-WAN `SOAK-01 PASS`, rollback provable-path accepted, two-mode docs, SAFE-14 held at every boundary and close. Phase evidence archived to `milestones/v1.50-phases/`.
**Previous:** v1.50 Phase 231 complete — formal migration-held criteria evaluated both WANs as `SOAK-01 PASS`, rollback verification closed by Kevin accepting the no-mutation provable path (`SOAK-02 PROVABLE-PATH PASS`), active docs now describe native and external cake-autorate modes, and SAFE-14 milestone-close zero-diff passed. Code review recorded a residual confirm-path risk to fix before any future live rollback exercise.
**Previous:** v1.50 Phase 230 complete — `scripts/soak-monitor.sh` now detects external cake mode per WAN, routes ATT through `cake-autorate-att.service`, `cake-autorate-att-state-bridge.service`, and `silicom-bypass-watchdog-cake-autorate-att.service`, and records read-only/live plus fake-ssh contrast evidence that the post-fix scan catches ATT-unit errors the pre-fix `wanctl@att.service` scan missed.
**Previous:** v1.50 Phase 229 complete — `deploy.sh --with-att-cake-autorate` now deploys the full ATT artifact set, ATT artifact-contract tests and deploy-list drift gate pass, read-only cake-shaper SHA evidence shows all six ATT artifacts equal to repo, and SAFE-14 Phase 229 boundary proof is clean.
**Previous:** v1.49 closed overtaken-by-events — both WANs migrated to cake-autorate external-controller mode (`fc47a0c`): repo-owned configs, qdisc-init scripts, parameterized state bridge (cake-autorate log → wanctl state JSON + metrics DB + wanctl-compatible `/health`), systemd units with `Conflicts=wanctl@`, silicom watchdog variant, `deploy.sh --with-spectrum-cake-autorate`, soak-monitor bridge fallback, and artifact tests. Known follow-ups became v1.50 scope.
**Previous:** v1.49 Phase 227 complete — Spectrum candidate `diffserv4 wash` was live with qdisc proof on `spec-router`/`spec-modem`, matched baseline/candidate evidence captured with marked-EF and unmarked references, SAFE-13 passed with zero controller/ATT diff. The Phase 228 verdict never ran (see Latest).
**Previous:** v1.49 Phase 226 complete — Snapshot A rollback anchor, retained `920/18 besteffort wash` baseline evidence, GATE-01 threshold lock, dry-run restore proof, and SAFE-13 boundary verification all passed. Plan 05 closed the prior parser/threshold verification gaps by parsing real CAKE per-tin rows and re-provenancing `NOISE_BAND_MS.value=24.206` from regenerated retained evidence.
**Previous:** v1.48 Phase 224 Production Canary complete — aligned steering daemon deployed to production `cake-shaper` (`1.39 → 1.47`, healthy in 2s), 16-sample observation window closed `kept_aligned`, all three spine invariants proven (incl. operator-authorized router rule-read), SAFE-12 boundary + milestone-close checks passed, rollback armed but not fired. Residual: rollback wall-clock unproven (no staging host; honestly waived).
**Previous:** v1.48 Phase 222 Steering Drift Audit complete — read-only evidence packet covers DRIFT-01/02/03/04 plus SAFE-12. The audit found one steering-surface commit between runtime `1.39` and source-floor `v1.47`: `84ad6aa`, classified behavior-changing but preserving binary steering, only-new-connection rerouting, and autorate-baseline authority, so the operator disposition is `go`. No runtime/source mutation, production probe, deploy, controller threshold, CAKE, RouterOS, or production service change occurred.
**Previous:** v1.47 milestone complete — Phase 221 Matrix Evidence + Closeout (Scope A2) closed the folded `tcp_12down` todo with CRITERIA-02 close-with-prejudice rule attached verbatim; 54/54 deduplicated valid replicates across 18 target/path/window cells; D-10 BGP overlay flipped raw `defect_located` to `carried_narrower_with_close_with_prejudice_rule` because three Spectrum supplemental Vultr cells were BGP-path-contaminated mid-run. No controller, threshold, CAKE, steering, RouterOS, or Phase 213/214 source behavior changed.
**Previous:** v1.47 Phase 220 Matrix Runner (Scope A1) complete — canonical 18-cell target/path/window YAML with locked CRITERIA thresholds; stdlib/PyYAML aggregator handles fixture and live wrapper evidence; wrapper composes Phase 213 capture with unchanged Phase 214 align/classify output; wet dallas/Spectrum daytime rehearsal matched the Phase 214 anchor (`ambiguous` / `reflector_loss`).
**Previous:** v1.47 Phase 219 Ingestion-Rate Observability complete — `wanctl-history --ingestion-rate` now has additive `--by-table` and `--rolling` Phase 219 JSON envelope modes, `wanctl-operator-summary --digest` emits ingestion-rate lines, and `scripts/phase219_ingestion_digest.py` persists cron-callable snapshots with atomic writes and count-based retention. Production D-27 verified the deployed snapshot path during a 73,603-sample profiling window with `cycle_total.avg_ms=2.857` and `p99_ms=6.4`; the profiling override was reverted and `wanctl@spectrum` returned to the normal ExecStart.
**Previous:** v1.46 Phase 217 Production Cycle-Budget Baseline complete — Spectrum `1.45.0` was profiled with a validated live journal streaming capture after a pilot and short rehearsal; `71560` cycle records produced `cycle_total.avg_ms=2.883`, `cycle_total.p99_ms=6.9`, and dominant category `logging_metrics=8.26%`. The profiling todo is closed as no-action, performance work is deprioritized in favor of quality/tuning work, and the JSON collector now fails closed if `autorate_cycle_total` samples are absent.
**Previous:** v1.46 Phase 216 Recovery/Refractory Decision complete — the Phase 196 queue-primary refractory semantics thread is closed as `no-change / resolved-by-197`; Phase 197 replay tests are the semantic proof, Phase 213 only shows no current symptom, and RECOV-03 is satisfied only as a no-change gate/waiver rather than a basis for future tuning. No control-path code, YAML config, systemd unit, script, test, RouterOS surface, or production service was changed.
**Previous:** v1.46 Phase 215 Spectrum Upload Reclaim Canary complete — upload-throughput extraction and reclaim-gate tooling landed, Snapshot A was captured read-only, and the approved one-knob Spectrum upload ceiling canary (`18 -> 20`) was deployed/restarted/proved. Leg-B produced bounded `void` on all attempts, so the safe default targeted rollback restored repo and production to `ceiling_mbps: 18` with DB/canary-check proof; code review warnings remain advisory hardening items.
**Previous:** v1.46 Phase 214 Measurement Collapse Investigation complete — read-only analyzer pipeline (matrix wrapper, fail-closed flent extractor, per-second aligner, six-driver classifier, matrix aggregator) plus the official three-window Spectrum/Dallas matrix. Verdict `ambiguous`, primary driver `reflector_loss`, signal disposition `none`: daytime/prime-time stayed in the high-tail ambiguous band (p99 606/560ms) with one-cycle measurement collapse while `/health` read healthy, but the historical catastrophic `p99 > 1000ms` was not reproduced and there was no in-window journal corroboration. Folded `tcp_12down` todo carried-narrower; zero `src/wanctl`/RouterOS/service/steering/yaml mutation, enforced by passing mutation-boundary tests.
**Previous:** v1.46 Phase 213 Experience Baseline Harness complete — read-only harness, live serialized Spectrum→ATT evidence, signal-sheet classification, and operator report recommended Phase 215 primary with Phase 216/214 as runners-up.
**Previous:** v1.46 Phase 212 Production Inventory And Drift Audit complete — read-only evidence captured from `cake-shaper`, drift classified without production mutation, final report preserves downstream constraints for Phase 213/214/215 and the `/health` vs user-perceived-quality distinction.
**Previous:** v1.46 Internet Quality Recovery opened — evidence-first project reset focused on real user-perceived quality, production drift, measurement collapse, conservative upload reclaim, refractory/recovery semantics, and cycle-budget baseline.
**Older:** v1.45 Flapping Peak-Counter Window Repair shipped-with-deferral — windowed peak accumulator is live on Spectrum and ATT at `1.45.0`; VERIFY-01 production observation is deferred to v1.46/watch-list by operator sign-off, and phase directories/REQUIREMENTS/spine todo remain in place.
**Older:** v1.44 Phase 208 Carry-on quick tasks — completed TOOL-01/T17(a) watchdog fail-closed hardening, TOOL-02/T9 `wanctl-history --ingestion-rate` with legacy/ad-hoc `--db` + `--wan` gap closure, and TOOL-03/T12 digest permission/write tolerance. Phase 208 verification passed 8/8 after gap closure, code review was clean, security threats are closed, and SAFE-09 remains bounded to operator tooling rather than controller thresholds/algorithms.
**Older:** v1.44 Phase 207 Soak harness hardening — SAFE-07 source-diff verification now fails closed on dirty/staged/untracked `src/wanctl/` surfaces, `soak-capture.sh` tolerates bounded transient capture failures with sidecar TSV diagnostics, `secondary_gate_legacy` is removed from live soak summaries, and CALIB-02 YAML promotion is explicitly routed to NO pending T17(b)/SEED-005. Phase 207 preserved SAFE-09 with zero controller-path source diff and full/hot-path test passes.
**Older:** v1.43 UL Suppression Metrics & Gate Calibration — additive `/health` completed-window suppression counters by cause, per-sample `load_rtt_delta_us` in soak NDJSON with zone × cause-tag aggregation, and soak-grounded D-14 successor threshold `175` replacing the qualitative Phase 200 inheritance. Boundary-marker remediation cycle (Plans 204-07..10) re-derived CALIB-01/04 evidence under corrected aggregator. SAFE-07 closeout invariant held end-to-end: zero control-path source diff from Phase 201 close (`b72b463`).
**Older:** v1.42 DOCSIS-Aware UL Congestion Control — Spectrum upload runs a YAML setpoint clamp (`docsis_mode: true`, `setpoint_mbps: 12`) with windowed RTT-integral classifier and CAKE-backlog secondary corroborator; bounded absolute RED decay and integral anti-windup landed in Plan 201-14; recanary `20260505T122513Z` PASSED with `ul_floor_hits_during_load=0`; 24h soak `20260505T132736Z` D-19 floor-hit delta `0` on production v1.42.1.
**Older:** v1.41 Per-Direction Control Surfaces — UL/DL threshold split shipped behind per-key presence flags (ARB-05); validator now WARNs on unknown `continuous_monitoring.*` keys (SAFE-06); `CHANGELOG.md` and `docs/CONFIGURATION.md` carry restart-required migration semantics (DOCS-03); VALN-06 deferred-and-closed via Phase 201 Route B.
**Older:** v1.40 Ordering Rationale — DL queue-primary arbitration with confidence-gated RTT demotion; v1.39 Control-Path Timing & Measurement Accounting — netlink overlap instrumentation + reflector scorer blackout-awareness; v1.38 Measurement Resilience Under Load — machine-readable degraded measurement truth.

<details>
<summary>Archived v1.43 milestone goals (collapsed for brevity)</summary>

### v1.43 UL Suppression Metrics & Gate Calibration (shipped 2026-05-13)

**Goal:** Repair the metric contract behind the failed D-14 secondary watchdog from Phase 201, capture target-edge evidence in the same baseline soak, and recalibrate a soak-grounded D-14 successor gate — without changing controller behavior.

**Shipped features:**

- **Metric semantics fix** (SEED-002, Phase 202) — additive `/health.wans[].upload` completed-window suppression counts with `dwell_hold` / `backlog_recovery` / `other` cause tags; `suppressions_per_min` preserved untouched.
- **Target-edge churn instrumentation** (SEED-004, Phase 203) — per-sample `load_rtt_delta_us` in soak NDJSON; zone × cause-tag histogram + p50/p95/p99/max aggregation in `soak-summary.json`.
- **D-14 successor recalibration** (SEED-003, Phase 204) — soak-grounded threshold `175` against `by_cause.dwell_hold.p99`; dual-emission watchdog loaded from `scripts/calib_02_threshold.json`; verification soak `20260512T004208Z` dual gate PASS.

**Closeout invariant held:** No controller tuning within v1.43. SAFE-07 verified at every phase boundary — zero control-path source diff between Phase 201 close (`b72b463`) and v1.43 close.

**Phase order shipped:** 202 → 203 → 204 (executed as 002 → 004 → 003 by seed-id). Joint Claude + Codex `gpt-5.5 xhigh` scope decision 2026-05-06.

**Gap-closure cycle (Plans 204-07..10):** Post-`d44e2fd` boundary-marker remediation invalidated pre-remediation CALIB-01/04 soak summaries. Corrected-boundary CALIB-01 rerun `20260509T183037Z` produced valid distribution; Branch B threshold 150 produced verification `FAIL-A` (`secondary_value=151.0`); Branch A continuation re-approved threshold 175 and verification soak `20260512T004208Z` passed cleanly.

**Phase status:** Phases 202 (4/4 plans), 203 (3/3 plans), 204 (10/10 plans) all complete. Phase 202 VALIDATION.md reconstructed retroactively (`nyquist_compliant: false`, test coverage intact); operator accepted at v1.43 close.

**Routed to v1.44:** SEED-005 conservative UL tuning sweep (prereqs now met); WR-01/WR-02 soak-harness hardening; `secondary_gate_legacy` block removal; CALIB-02 YAML-promotion evaluation.

</details>

<details>
<summary>Archived v1.40 milestone goals (collapsed for brevity)</summary>

### v1.40 Queue-Primary Signal Arbitration (shipped 2026-05-03)

**Goal:** Replace RTT-primary DL congestion classification with kernel-local CAKE queue-delay as the primary signal under load, demoting RTT to a confidence-gated secondary. Restore Spectrum DOCSIS throughput without making the controller vulnerable to carrier ICMP/UDP deprioritization. DL-only scope; UL stays RTT-led.

**Target features:**

- Queue-delay delta (`avg_delay_us - base_delay_us` from CAKE) as DL distress primary signal under load
- RTT demoted to confidence-gated secondary; rtt_confidence derived from ICMP/UDP agreement + queue direction agreement
- Fusion healer bypass requires BOTH queue-distress AND RTT-distress aligned for 6 cycles; single-path flips never bypass
- New `/health` `signal_arbitration` block + numeric Prometheus metrics (no string labels)
- Spectrum A/B soak: 24h rtt-blend baseline then 24h cake-primary on same deployment; ATT canary gated on Phase 191 closure

**Key context:**

- 2026-04-23 production measurements: Spectrum DOCSIS 940/40 delivers ~280 Mbps with wanctl active vs 591 Mbps CAKE-only static floor. ATT fusion already disabled (2026-04-17) for same root cause; fusion disabled on Spectrum 2026-04-23 as a workaround. Neither workaround recovers throughput.
- Root cause: carrier deprioritizes BOTH ICMP and UDP/irtt at different times (ICMP/UDP ratio flipped 1.96 → 0.54 within minutes same test). Fusion.healer correctly suspends on anti-correlation then controller falls back to ICMP-only and clamps on phantom bloat. No YAML tuning recovers because signal itself is carrier-jittered.
- Architectural decision: CAKE kernel-local queue delay is not vulnerable to carrier deprioritization. Use `base_delay_us` from CAKE (kernel-computed idle reference) — no Python-learned baseline.
- Parallel milestone: v1.39 remains open. Phase 191 closure pending ATT weather-rerun. Phase 192 (reflector scorer blackout-awareness + log hygiene) still planned and required by MEAS-06/VALN-03 24h soak.
- Priority: stability > safety > clarity > elegance. No state-machine, threshold, EWMA, dwell, deadband, or burst-detection changes. Arbitration changes input to classification, not classification rules themselves.

**Phase status:** v1.40 Phases 193-199 all complete. Phase 196 was blocked at phase level on Spectrum B-leg evidence; Phase 198 closed the gap with attempt 11 canonical promotion (VALN-04, VALN-05a). Phase 199 closed the OBS-02 spec/impl/doc drift caveat docs-only. SAFE-05 enforced throughout. VALN-05b (ATT canary) remains deferred-by-design pending v1.39 Phase 191 closure.

</details>

## Recently Archived / Shipped: v1.39, v1.41, v1.42, v1.43, v1.44, v1.45, v1.46, v1.47

- **v1.47 Measurement Evidence Closure** (shipped 2026-06-02; 3 phases, 12 plans, 40 tasks; tcp_12down closed with close-with-prejudice rule per CRITERIA-02 post-D-10 BGP overlay) — `.planning/milestones/v1.47-ROADMAP.md`
- **v1.46 Internet Quality Recovery** (shipped-with-deferral 2026-05-30, VERIFY-01/02 deferred to Phase 218 event-gated watch-list; 6 phases, 21 plans, 42 tasks) — `.planning/milestones/v1.46-ROADMAP.md`
- **v1.45 Flapping Peak-Counter Window Repair** (shipped-with-deferral 2026-05-27, VERIFY-01 deferred → rolled into v1.46 Phase 218; archived 2026-05-30 alongside v1.47 open) — `.planning/milestones/v1.45-phases/211-production-verification-milestone-closure/211-03-SUMMARY.md`
- **v1.44 Topology-Correct CAKE — Spectrum besteffort wash migration** (shipped 2026-05-26, audit `passed` 16/16 after 206 restamp) — `.planning/milestones/v1.44-ROADMAP.md`
- **v1.43 UL Suppression Metrics & Gate Calibration** (shipped 2026-05-13, audit `passed` 15/15) — `.planning/milestones/v1.43-ROADMAP.md`
- **v1.42 DOCSIS-Aware UL Congestion Control** (shipped 2026-05-06, gaps_found Route B) — `.planning/milestones/v1.42-ROADMAP.md`
- **v1.41 Per-Direction Control Surfaces** (closed 2026-05-04, gaps_found, VALN-06 deferred-then-closed via v1.42) — `.planning/milestones/v1.41-ROADMAP.md`
- **v1.39 Control-Path Timing & Measurement Accounting** (effectively shipped 2026-04-24 under operator waiver, archived 2026-05-06 gaps_found) — `.planning/milestones/v1.39-ROADMAP.md`

## Completed Milestone: v1.38 Measurement Resilience Under Load

**Shipped:** 2026-04-15 | 5 phases, 12 plans, 26 tasks, 30 milestone commits

**Delivered:** `/health` now exposes degraded measurement truth via `state`,
`successful_count`, and `stale`; zero-success RTT cycles no longer masquerade
as healthy current measurement; replayable regression evidence and operator
guidance close the milestone contract; and the later backfill/traceability
phases repaired the final audit bookkeeping without reopening controller
thresholds or steering behavior.

## Requirements

### Validated

**v1.50 cake-autorate Migration Hardening (shipped 2026-06-10):**

- ✓ DEPLOY-01..02 — ATT cake-autorate deploy path at Spectrum parity; live cake-shaper bytes proven equal to repo (six artifacts, ALL EQUAL) — v1.50 Phase 229.
- ✓ TEST-01..02 — ATT artifact-contract tests at Spectrum parity + bidirectional deploy-list drift gate — v1.50 Phase 229.
- ✓ MON-01..02 — soak-monitor watches live ATT external-controller units; WAN-parameterized mode detection, no Spectrum-only hardcoding — v1.50 Phase 230.
- ✓ SOAK-01 — formal migration-held criteria (C1–C4) evaluated read-only; both WANs PASS — v1.50 Phase 231.
- ✓ SOAK-02 — native rollback proven via double-gated script + both-WAN preflight; operator accepted no-mutation provable path — v1.50 Phase 231.
- ✓ DOCS-04 — active docs describe both deployment modes; stale native-ownership claims swept — v1.50 Phase 231.
- ✓ SAFE-14 — controller-path zero-diff vs `87980bdf` at every phase boundary AND milestone close — v1.50 cross-phase.

**v1.48 Steering Runtime Drift Closure (shipped 2026-06-03):**

- ✓ DRIFT-01..04 — steering runtime/source drift audited; sole behavior-changing commit `84ad6aa` contract-preserving (`go`).
- ✓ PROOF-01..03 — offline replay/fixture harness + clean-restart reproduction; spine contract held across corpus.
- ✓ CANARY-01..03 — production deploy `1.39 → 1.47` under Snapshot A anchor, canary `kept_aligned`, bounded rollback armed.
- ✓ SAFE-12 — controller-path zero-diff vs v1.47 at every phase boundary AND milestone close.

**v1.49 Spectrum DSCP Tinning Re-evaluation (closed 2026-06-09 overtaken-by-events; 11/13 REQs, GATE-02/03 unmet-overtaken):**

- ✓ DSCP-01..03 — read-only DSCP survival trace completed with `MARKS_SURVIVE_QUALIFIED`; no external gear mutation; Phase 226 unblocked rather than early-exiting negative — Phase 225.
- ✓ AB-01..02 — Snapshot A rollback anchor captured; retained `920/18 besteffort wash` baseline evidence regenerated from real CAKE per-tin rows with non-zero deltas/spreads — Phase 226.
- ✓ GATE-01 — accept/rollback thresholds locked before candidate deploy, including `NOISE_BAND_MS.value=24.206` hash-provenanced to regenerated retained baseline evidence — Phase 226.
- ✓ AB-03..04 — candidate Spectrum `diffserv4 wash` deployed under Snapshot A, matched qdisc/health/RRUL/realtime-flow evidence captured incl. marked-EF arm — Phase 227.
- ✗ GATE-02..03 — verdict computation and rollback/closeout unexecuted; overtaken by the cake-autorate migration (`fc47a0c`) which removed the gated topology. Evidence direction (REJECT diffserv4-wash, old topology only) recorded in MILESTONES.md.
- ✓ SAFE-13 — controller-path zero-diff vs v1.48 and ATT byte-identical held through Phases 225–227; the Phase 228 lift question is moot (native controller no longer live on Spectrum/ATT).

**Core Features:**

- ✓ Continuous RTT monitoring with 50ms control loops — v1.0
- ✓ Multi-state congestion control (GREEN/YELLOW/SOFT_RED/RED) — existing
- ✓ Multi-signal detection (RTT + CAKE drops + queue depth) — existing
- ✓ Dual-transport router control (REST API + SSH fallback) — existing
- ✓ Optional multi-WAN steering with latency-aware routing — existing
- ✓ Configuration-driven (YAML-based for multiple WAN types) — existing
- ✓ File-based state persistence with locking — existing
- ✓ systemd integration with persistent event loop — v1.0

**v1.0 Performance Optimization:**

- ✓ 50ms cycle interval (40x faster than 2s baseline) — v1.0
- ✓ EWMA time constants preserved via alpha scaling — v1.0
- ✓ Sub-second congestion detection (50-100ms response) — v1.0

**v1.1 Code Quality:**

- ✓ Shared signal_utils.py and systemd_utils.py modules — v1.1
- ✓ Consolidated utility modules (paths, lockfile, ping, rate_limiter) — v1.1
- ✓ CORE-ALGORITHM-ANALYSIS.md with protected zones defined — v1.1
- ✓ WANController refactored (4 methods extracted from run_cycle) — v1.1
- ✓ SteeringDaemon refactored (5 methods extracted) — v1.1
- ✓ Unified state machine (CAKE-aware + legacy combined) — v1.1
- ✓ Phase2BController integrated with dry-run mode — v1.1

**v1.2 Configuration & Polish:**

- ✓ Phase2B timer interval fix (cycle_interval param) — v1.2
- ✓ baseline_rtt_bounds documentation and validation — v1.2
- ✓ Deprecation warnings for legacy steering params — v1.2
- ✓ Config edge case tests (+77 tests) — v1.2
- ✓ Phase2B confidence scoring enabled (dry-run mode) — v1.2

**v1.4 Observability:**

- ✓ HTTP health endpoint for steering daemon (port 9102) — v1.4
- ✓ Steering state exposure (enabled/disabled, decision timestamp) — v1.4
- ✓ Confidence scores from ConfidenceController in health response — v1.4
- ✓ WAN congestion states (primary/secondary) in health response — v1.4
- ✓ Uptime and version in health response — v1.4
- ✓ Health server lifecycle integrated with steering daemon — v1.4

**v1.5 Quality & Hygiene:**

- ✓ Test coverage infrastructure (pytest-cov, 72% baseline, HTML reports) — v1.5
- ✓ Coverage badge in README.md — v1.5
- ✓ Dead code and TODO cleanup verified — v1.5
- ✓ Complexity analysis (11 high-complexity functions documented) — v1.5
- ✓ Documentation verified to v1.4.0 (6 files updated, 14 issues fixed) — v1.5
- ✓ Security audit (zero CVEs, 4 tools, `make security` target) — v1.5

**v1.6 Test Coverage 90%:**

- ✓ 90%+ statement coverage (90.08% achieved) — v1.6
- ✓ CI enforcement via fail_under=90 in pyproject.toml — v1.6
- ✓ 743 new tests added (747 → 1,490 total) — v1.6
- ✓ All major modules tested: backends, state, metrics, controllers, CLI tools — v1.6

**v1.9 Performance & Efficiency:**

- ✓ Per-subsystem cycle profiling with PerfTimer and OperationProfiler — v1.9
- ✓ --profile CLI flag for production profiling data collection — v1.9
- ✓ icmplib raw ICMP sockets replacing subprocess ping (-3.4ms avg) — v1.9
- ✓ Structured DEBUG logs with per-subsystem timing every cycle — v1.9
- ✓ Cycle budget telemetry in both health endpoints — v1.9
- ✓ Profiling analysis pipeline with 50ms budget context — v1.9

**v1.10 Architectural Review Fixes:**

- ✓ Sub-cycle retry delays (50ms max per attempt, single retry) — v1.10
- ✓ Transport config authoritative (router_transport controls primary) — v1.10
- ✓ Self-healing failover (periodic re-probe of primary REST) — v1.10
- ✓ Steering state normalization with legacy warnings — v1.10
- ✓ Safe JSON loading and stale baseline detection — v1.10
- ✓ SSL verify_ssl=True default across all layers — v1.10
- ✓ SQLite integrity check with auto-rebuild on corruption — v1.10
- ✓ Disk space monitoring in health endpoints — v1.10
- ✓ Daemon duplication consolidated (daemon_utils.py, perf_profiler.py) — v1.10
- ✓ Test fixture consolidation (-481 lines, shared conftest.py) — v1.10
- ✓ 27/27 requirements satisfied, all 6 E2E flows verified — v1.10

**v1.11 WAN-Aware Steering:**

- ✓ Autorate state file exports congestion zone (dl_state/ul_state) each cycle — v1.11
- ✓ Backward-compatible state file extension (unknown keys ignored) — v1.11
- ✓ Write-amplification-safe zone persistence (dirty-tracking exclusion) — v1.11
- ✓ WAN zone fused into confidence scoring (WAN_RED=25, WAN_SOFT_RED=12) — v1.11
- ✓ CAKE-primary invariant enforced (WAN alone cannot trigger steering) — v1.11
- ✓ Recovery gate requires WAN GREEN (or unavailable) — v1.11
- ✓ Zero additional I/O (zone piggybacked on existing state file read) — v1.11
- ✓ Stale zone (>5s) defaults to GREEN, autorate unavailable skips WAN weight — v1.11
- ✓ 30s startup grace period ignores WAN signal — v1.11
- ✓ Feature ships disabled by default (wan_state.enabled: false) — v1.11
- ✓ YAML wan_state: section with schema validation — v1.11
- ✓ Health endpoint wan_awareness section with zone, staleness, confidence contribution — v1.11
- ✓ SQLite metrics for WAN zone, weight, and staleness per cycle — v1.11
- ✓ WAN context in steering transition and degrade timer logs — v1.11
- ✓ 17/17 requirements satisfied, 14/14 integration, 3/3 E2E flows — v1.11

**v1.12 Deployment & Code Health:**

- ✓ Deployment artifacts aligned with pyproject.toml (Dockerfile, install.sh, deploy.sh) — v1.12
- ✓ Dead code removed (pexpect, subprocess import, timeout_total API) — v1.12
- ✓ Security hardened (password scrubbing, scoped SSL warnings, safe defaults) — v1.12
- ✓ Fragile areas stabilized (state file contract tests, check_flapping contract, WAN config warnings) — v1.12
- ✓ Config boilerplate consolidated (BaseConfig with 6 common fields) — v1.12
- ✓ Log rotation via RotatingFileHandler (10MB/3 backups) — v1.12
- ✓ Dockerfile/dependency contract tests parametrized from pyproject.toml — v1.12
- ✓ 18/18 requirements satisfied, audit passed — v1.12

**v1.13 Legacy Cleanup & Feature Graduation:**

- ✓ Production configs confirmed modern-only (zero legacy fallbacks exercised) — v1.13
- ✓ cake_aware mode branching removed, CAKE three-state is sole code path — v1.13
- ✓ 7 obsolete ISP-specific config files deleted — v1.13
- ✓ deprecate_param() helper with warn+translate for 8 legacy config parameters — v1.13
- ✓ Legacy config validation cleaned (validate_sample_counts 2-param API) — v1.13
- ✓ RTT-only mode (cake_aware: false) retired with deprecation warning — v1.13
- ✓ Test suite cleaned of vestigial legacy-mode fixtures and naming — v1.13
- ✓ SIGUSR1 generalized hot-reload for dry_run and wan_state.enabled — v1.13
- ✓ Confidence-based steering graduated to live mode (dry_run: false) — v1.13
- ✓ WAN-aware steering enabled in production (wan_state.enabled: true) — v1.13
- ✓ 4-step degradation verification passed (stale fallback, SIGUSR1 rollback, grace period re-trigger) — v1.13
- ✓ 13/13 requirements satisfied — v1.13

**v1.14 Operational Visibility:**

- ✓ TUI dashboard with live per-WAN panels, color-coded congestion, rates, RTT — v1.14
- ✓ Async dual-poller engine with independent backoff and offline isolation — v1.14
- ✓ Sparkline trends (DL/UL/RTT) with bounded deques and color gradients — v1.14
- ✓ Cycle budget gauge showing 50ms utilization percentage — v1.14
- ✓ Historical metrics browser with time range selector and summary stats — v1.14
- ✓ Responsive layout (side-by-side >=120 cols, stacked below) with hysteresis — v1.14
- ✓ Terminal compatibility (--no-color, --256-color, tmux/SSH verified) — v1.14
- ✓ 27/27 requirements satisfied — v1.14

**v1.15 Alerting & Notifications:**

- ✓ AlertEngine with per-event (type, WAN) cooldown suppression and SQLite persistence — v1.15
- ✓ Discord webhook delivery with color-coded severity embeds and retry with backoff — v1.15
- ✓ Sustained congestion alerts (DL/UL independent timers, recovery gate) — v1.15
- ✓ Steering transition alerts (activation/recovery with duration and context) — v1.15
- ✓ WAN offline/recovery, baseline drift, and congestion flapping detection — v1.15
- ✓ YAML alerting config with rules, thresholds, cooldowns, webhook URL — v1.15
- ✓ Health endpoint alerting section and `wanctl-history --alerts` CLI — v1.15
- ✓ Alerting disabled by default, opt-in via alerting.enabled — v1.15
- ✓ SIGUSR1 reload chain extended for webhook_url hot-reload — v1.15
- ✓ 17/17 requirements satisfied — v1.15

**v1.16 Validation & Operational Confidence:**

- ✓ `wanctl-check-config` CLI tool for offline config validation (autorate + steering) — v1.16
- ✓ Auto-detection of config type from YAML contents — v1.16
- ✓ 6 validation categories (schema, cross-field, unknown keys, paths, env vars, deprecated) — v1.16
- ✓ Cross-config topology validation (primary_wan_config path + wan_name match) — v1.16
- ✓ JSON output mode for CI/scripting integration — v1.16
- ✓ `wanctl-check-cake` CLI tool for live router CAKE queue audit — v1.16
- ✓ Router connectivity, queue tree, CAKE type, max-limit diff, mangle rule validators — v1.16
- ✓ Reusable CheckResult/Severity data model shared between CLI tools — v1.16
- ✓ 16/16 requirements satisfied — v1.16

**v1.17 CAKE Optimization & Benchmarking:**

- ✓ Sub-optimal CAKE parameter detection with severity and rationale — v1.17
- ✓ Auto-fix CAKE params via REST API (`wanctl-check-cake --fix`) with snapshot rollback — v1.17
- ✓ RRUL bufferbloat benchmarking via flent (`wanctl-benchmark`) with A+-F grading — v1.17
- ✓ Benchmark result storage in SQLite with auto-store on every run — v1.17
- ✓ Before/after comparison (`wanctl-benchmark compare`) with color-coded grade deltas — v1.17
- ✓ Benchmark history with time-range filtering (`wanctl-benchmark history`) — v1.17
- ✓ 23/23 requirements satisfied — v1.17

**v1.18 Measurement Quality:**

- ✓ Hampel outlier filter with rolling window median replacement — v1.18
- ✓ Jitter EWMA and variance EWMA from raw RTT samples — v1.18
- ✓ Confidence scoring (variance-based 0-1 scale) — v1.18
- ✓ Signal processing in observation mode (filters EWMA input, no state changes) — v1.18
- ✓ IRTT UDP RTT measurement via subprocess wrapper with JSON parsing — v1.18
- ✓ IRTT background daemon thread (10s cadence, lock-free cache) — v1.18
- ✓ ICMP vs UDP protocol correlation with deprioritization detection — v1.18
- ✓ Container networking overhead 0.17ms (negligible, no code changes needed) — v1.18
- ✓ Health endpoint signal_quality and irtt sections per WAN — v1.18
- ✓ SQLite persistence for signal quality (per-cycle) and IRTT (per-measurement) metrics — v1.18
- ✓ 21/21 requirements satisfied — v1.18

**v1.19 Signal Fusion:**

- ✓ Weighted ICMP+IRTT fusion via \_compute_fused_rtt for congestion control input — v1.19
- ✓ Fusion ships disabled by default with SIGUSR1 zero-downtime toggle — v1.19
- ✓ Fusion weights YAML-configurable with warn+default validation — v1.19
- ✓ IRTT unavailable/stale falls back to icmplib-only with zero behavioral change — v1.19
- ✓ Health endpoint fusion section (enabled/disabled, weights, active sources, RTT values) — v1.19
- ✓ OWD asymmetric congestion detection from IRTT send_delay vs receive_delay — v1.19
- ✓ Asymmetric congestion direction as named attribute for downstream consumers — v1.19
- ✓ Asymmetric congestion persisted in SQLite for trend analysis — v1.19
- ✓ Per-reflector rolling quality scores with automatic deprioritization — v1.19
- ✓ Deprioritized reflectors re-checked on configurable interval for recovery — v1.19
- ✓ Reflector quality scores visible in health endpoint — v1.19
- ✓ Sustained upstream IRTT loss alerts via AlertEngine — v1.19
- ✓ Sustained downstream IRTT loss alerts via AlertEngine — v1.19
- ✓ IRTT loss alerts use per-event cooldown consistent with existing types — v1.19
- ✓ 15/15 requirements satisfied — v1.19

**v1.20 Adaptive Tuning:**

- ✓ Tuning framework with pluggable strategies, safety bounds, SQLite persistence — v1.20
- ✓ Congestion threshold calibration from GREEN-state RTT delta percentiles — v1.20
- ✓ Safety/revert detection with auto-rollback and parameter locks — v1.20
- ✓ Signal processing tuning: Hampel sigma/window, load time constant — v1.20
- ✓ Advanced tuning: fusion weight, reflector min_score, baseline bounds — v1.20
- ✓ Fusion baseline deadlock fix (ICMP-only baseline, fused load) — v1.20
- ✓ `wanctl-history --tuning` CLI for operator visibility — v1.20
- ✓ State file persistence to /var/lib/ + tuning param restore on restart — v1.20
- ✓ 30/30 requirements satisfied — v1.20

**v1.21 CAKE Offload (Shipped: 2026-03-25):**

- ✓ LinuxCakeBackend using `tc qdisc replace/change` for CAKE management — v1.21
- ✓ Transparent L2 bridges (br-spectrum, br-att) with 4 PCIe passthrough NICs — v1.21
- ✓ VM 206 (cake-shaper) on Proxmox with VLAN 110 management — v1.21
- ✓ Config transport: `linux-cake` alongside `rest`/`ssh` — v1.21
- ✓ Production cutover from containers to VM completed — v1.21
- ✓ `exclude_params` tuning feature for DOCSIS cable links — v1.21

**v1.22 Full System Audit (Shipped: 2026-03-26):**

- ✓ Test quality audit, docs freshness review, container script archival — v1.22
- ✓ CONFIG_SCHEMA.md alignment, systemd hardening, NIC tuning persistence — v1.22

**v1.23 Self-Optimizing Controller (Shipped: 2026-03-27):**

- ✓ pyroute2 netlink for CAKE tc calls (3ms → 0.3ms, 10x faster) — v1.23
- ✓ Configurable per-granularity metrics retention with tuner safety validation — v1.23
- ✓ Auto-fusion healing: Pearson correlation, 3-state machine, Discord alerts — v1.23
- ✓ Adaptive rate step tuning: 5-layer rotation, episode detection, oscillation lockout — v1.23
- ✓ 18/22 requirements satisfied (4 OBSV deferred to v1.24) — v1.23

**v1.24 EWMA Boundary Hysteresis:**

- ✓ State transition hysteresis (dwell_cycles=3, 150ms gate on GREEN->YELLOW) — v1.24
- ✓ Deadband thresholds (deadband_ms=3.0, split enter/exit for YELLOW->GREEN recovery) — v1.24
- ✓ Flapping elimination: zero alert pairs during prime-time (4,226 suppressions/24h) — v1.24
- ✓ YAML config + SIGUSR1 hot-reload for hysteresis params — v1.24
- ✓ Health endpoint hysteresis section (dwell_counter, deadband_ms, transitions_suppressed) — v1.24
- ✓ Spike detector confirmation counter (accel_confirm_cycles=3) — v1.24

**v1.25 Reboot Resilience:**

- ✓ Idempotent NIC tuning script (ring buffers, GRO forwarding, IRQ affinity) with journal logging — v1.25
- ✓ systemd dependency wiring (After= + Wants= on wanctl@.service) — v1.25
- ✓ deploy.sh updated to deploy NIC tuning artifacts — v1.25
- ✓ Dry-run validated on production (script idempotent, dependencies correct) — v1.25

**v1.28 Infrastructure Optimization (Shipped: 2026-04-05):**

- ✓ cake-shaper VM expanded to 3 vCPUs, load avg -16% — v1.28
- ✓ NIC IRQ affinity balanced across 3 cores (ens17 moved to CPU2), load avg -23% — v1.28
- ✓ Kernel network sysctls tuned (netdev_budget=600, max_backlog=10000) with sysctl.d persistence — v1.28
- ✓ SFP+ multi-queue-ethernet-default, 404K TX queue drops eliminated — v1.28
- ✓ RB5009 switch IRQ redistributed (cpu3 31%→20% under RRUL) — v1.28
- ✓ WireGuard TX errors root-caused (ZeroTier binding to wireguard1), 43K/day→0 — v1.28
- ✓ Bridge download DSCP classification via nftables (Voice/Bulk/BestEffort tin separation on both WANs) — v1.28
- ✓ CAKE ceiling sweep validated (ul32/dl940 confirmed optimal, daytime vs nighttime analysis) — v1.28

**v1.40 Queue-Primary Signal Arbitration (Phase 195 validated: 2026-04-24):**

- ✓ RTT delta is demoted behind `rtt_confidence`, with RTT unable to override queue-GREEN unless confidence and queue direction agree — Phase 195
- ✓ Fusion healer bypass requires sustained queue distress and confident RTT distress in the same worsening-or-held direction for 6 cycles; single-path flips do not bypass — Phase 195

**v1.39 Control-Path Timing & Measurement Accounting (effectively shipped 2026-04-24 under operator waiver):**

- ✓ Reflector scorer treats all-host zero-success cycles as path-wide blackouts (`reflector_scorer.py` blackout gate) — Phase 192
- ✓ "Protocol deprioritization detected" INFO logs are rate-limited / demoted when fusion is suspended/disabled (OPER-02; soak ±0.3% drift on both WANs) — Phase 192
- ✓ `cake_stats_thread` cadence is YAML-configurable at daemon start (`cake_stats_cadence_sec`); netlink overlap fields exposed in `/health.signal_arbitration` and slow-apply enrichment logs — Phase 191
- ◐ TIME-03/04, MEAS-06, VALN-02/03 measurement-validation gates against v1.38.0 baseline NOT closed; superseded by v1.40+ measurement evidence — see `.planning/milestones/v1.39-MILESTONE-AUDIT.md`

**v1.41 Per-Direction Control Surfaces (closed 2026-05-04 gaps_found):**

- ✓ Per-direction UL RTT bloat thresholds with per-key presence flags (`continuous_monitoring.upload.target_bloat_ms`, `continuous_monitoring.upload.warn_bloat_ms`) — ARB-05, Phase 200
- ✓ Autorate validator emits audible WARNING for unknown `continuous_monitoring.*` keys at startup — SAFE-06, Phase 200
- ✓ `CHANGELOG.md` and `docs/CONFIGURATION.md` carry restart-required migration semantics for the new UL threshold keys (SIGUSR1 does not reload them) — DOCS-03, Phase 200
- ◐ VALN-06 saturation canary deferred-then-closed via v1.42 Phase 201 Route B

**v1.42 DOCSIS-Aware UL Congestion Control (shipped 2026-05-06, gaps_found Route B):**

- ✓ DOCSIS-mode UL control (setpoint clamp + windowed RTT-integral classifier + CAKE backlog secondary corroborator) with bounded absolute RED decay and integral anti-windup — Phase 201, Plans 201-04 / 201-14
- ✓ VALN-06 D-19 primary floor-hit gate PASSED on canary `20260505T122513Z` and 24h soak `20260505T132736Z` — production v1.42.1
- ✓ Five additive `/health.upload.*` runtime-state fields: `setpoint_mbps`, `headroom_mbps`, `rtt_integral_ms_s`, `docsis_state`, `docsis_mode_active`
- ✓ Predeploy gate (`scripts/phase201-predeploy-gate.sh`) reconciles or fails closed against v1.41-rejected-hypothesis YAML keys before any Spectrum deploy
- ◐ D-14 secondary suppression watchdog FAIL on YELLOW-edge dwell-hold path deferred to v1.43+ as `metric_semantics_and_recalibration` — closed by v1.43

**v1.43 UL Suppression Metrics & Gate Calibration (shipped 2026-05-13, audit `passed`):**

- ✓ METRIC-01..05 — UL suppression-counter metric semantics fix: additive `/health.wans[].upload` completed-window counts with `dwell_hold`/`backlog_recovery`/`other` cause tags; `suppressions_per_min` preserved untouched; replay against v1.42 reference soak matched codex re-aggregation; SAFE-05 v1.43 pins added — SEED-002, Phase 202
- ✓ OBSV-05..08 — Target-edge churn instrumentation: per-sample `load_rtt_delta_us` in soak NDJSON; `soak-summary.json` zone × cause-tag histogram + p50/p95/p99/max; stdlib-only aggregator with deterministic golden fixtures — SEED-004, Phase 203
- ✓ CALIB-01..05 — D-14 successor recalibration: soak-grounded threshold `175` against `by_cause.dwell_hold.p99`; dual-emission watchdog (`secondary_gate_legacy` + `secondary_gate_completed_window`) loaded from `scripts/calib_02_threshold.json`; v1.42 legacy oracle regression pinned at `6.466842...`; verification soak `20260512T004208Z` dual gate PASS (D-19 primary delta 0, p99 dwell_hold `135.62 ≤ 175`); threshold-basis hygiene captured in 204-RETRO.md Key Lesson #1 — SEED-003, Phase 204
- ✓ SAFE-07 — Milestone-closeout invariant held: zero control-path source diff between Phase 201 close (`b72b463`) and v1.43 close, verified at every phase boundary by `scripts/check-safe07-source-diff.sh`; only planned `src/wanctl/__init__.py` version bump permitted
- ✓ Boundary-marker remediation cycle (Plans 204-07..10) re-derived CALIB-01/04 evidence under corrected post-`d44e2fd` aggregator; Branch A threshold 175 superseded Branch B threshold 150 after FAIL-A at `secondary_value=151.0`

**v1.44 Topology-Correct CAKE — Spectrum besteffort wash migration (shipped 2026-05-26, audit `passed`):**

- ✓ TOPO-01..07 — Tin-agnostic CAKE signal + per-WAN `allow_wash` gate; A/B replay harness with deterministic golden NDJSON; predeploy gate with JSON-sourced thresholds (RRUL p99 >5%, restart-rate, transition-rate); Spectrum committed config migrated to `920Mbit besteffort wash`; 24h soak `20260521T222622Z` passed with rollback gates green — Phases 205, 206, 209
- ✓ HRDN-01..04 — SAFE-07 source-diff verifier fail-closed on dirty/staged/untracked surfaces; `soak-capture.sh` bounded-blip tolerance with sidecar diagnostics; `secondary_gate_legacy` retired from live summaries — Phase 207
- ✓ TOOL-01..03 — Watchdog fail-closed on bad gate columns/statistics; `wanctl-history --ingestion-rate` with `--wan` filtering; `wanctl-operator-summary --digest` tolerates per-WAN open/write failures without masking schema corruption — Phase 208
- ✓ SAFE-08/SAFE-09 — ATT byte-identical; zero controller-path source diff from `6508d68`; five-file SAFE-09 allowlist operator-approved

**v1.45 Flapping Peak-Counter Window Repair (shipped-with-deferral 2026-05-27, VERIFY-01 → Phase 218):**

- ✓ ALERT-01/02/03 — Per-direction windowed peak accumulator independent of deque-clear-on-fire; alert-once-per-`cooldown_sec` semantics preserved (`alert_engine.fire()` dedupe unchanged); Spectrum + ATT deployed at `1.45.0` — Phase 210, 211
- ✓ TEST-01..03 — Updated `TestFlappingDequeClear` for Option A; new tests asserting `peak_transition_count > flap_threshold` during sustained oscillation; `132/132` alerting/integration slice passing — Phase 210
- ✓ SAFE-10 — Manual closeout against `21ee630` with `AWK_EXIT=0` — Phase 211
- ◐ VERIFY-01 — Production verification deferred via operator sign-off 2026-05-27; **carried forward to v1.46 Phase 218** (event-gated, no synthetic generation)

**v1.46 Internet Quality Recovery (shipped-with-deferral 2026-05-30, 18/20 v1.46 REQ-IDs satisfied):**

- ✓ DRIFT-01..03 — Read-only Spectrum/ATT/steering inventory with service/version/endpoint/config/health/persisted-state classification; D-08 secret-safe redaction; steering runtime `1.39` vs source `1.45` surfaced as known unaligned drift — Phase 212
- ✓ BASE-01..03 — Single-command per-WAN baseline harness with co-sampled `/health`, CAKE state, SQLite alert windows, current rates, measurement quality, steering state; offline six-bucket signal classification produced Phase 215 upload-reclaim recommendation — Phase 213
- ✓ MEAS-01..03 — Fail-closed flent ping percentile extractor (raw `Ping (ms) ICMP`, sorted-index method, pinned fixture) + per-second alignment + six-driver classifier; canonical Spectrum/Dallas verdict `ambiguous`/`reflector_loss`/`signal none`; severe loaded p99 NOT reproduced in official window; `tcp_12down` folded todo **carried narrower**, not closed — Phase 214
- ✓ RECLAIM-01..03 — Snapshot A rollback anchor (read-only); approved one-knob Spectrum upload canary `18 → 20`; **bounded VOID exhausted on three attempts**, Spectrum safely rolled back to ceiling 18 — Phase 215
- ✓ RECOV-01..03 — Phase 196 queue-primary refractory semantics thread closed as **no-change / resolved-by-197** with evidence-cited rationale; Phase 213 confirmed no current symptom; RECOV-03 satisfied only as a no-change gate/waiver — Phase 216
- ✓ PERF-01..03 — Production-safe JSON cycle-budget capture with stdlib NDJSON parser; operator-gated Spectrum profiling window captured `71,560` JSON Cycle records (`cycle_total.avg_ms=2.883`, `p99=6.9ms`); dominant category `logging_metrics=8.26%`; profiling baseline todo **closed as no-action** — performance is not the quality limit — Phase 217
- ◐ VERIFY-01/02 — Deferred to Phase 218 (event-gated; carried forward from v1.45 + extended to ALERT-03 per-`cooldown_sec` bucket audit)

**v1.47 Measurement Evidence Closure (shipped 2026-06-02, 18/18 v1.47 REQ-IDs satisfied):**

- ✓ INGEST-01..05 — Per-WAN per-table SQLite ingestion-rate observability: `wanctl-history --ingestion-rate --by-table` and `--rolling=60,300,3600` additive flags with `schema_version: 1` envelope and per-snapshot staleness fields (`_snapshot_unix`, `_snapshot_age_sec`); `wanctl-operator-summary --digest` ingestion-rate block; cron-callable `scripts/phase219_ingestion_digest.py` with atomic-write snapshot persistence + count-based retention. D-27 production cycle-budget: `avg_ms=2.857`, `p99_ms=6.4` over 73,603 samples — Phase 219
- ✓ CRITERIA-01..02 — Pre-registered kill criteria + defect criteria written into `220-CONTEXT.md` before any live matrix cell run; close-with-prejudice rule documented and locked at Phase 220 plan time, never edited after first live run — Phase 220
- ✓ MATRIX-01..04 — 18-cell `scripts/phase220-matrix.yaml` with canonical Phase 214 `dallas` control cell in every window, supplemental Vultr Dallas + Vultr Chicago, Spectrum + ATT path axis, off-peak + daytime + prime-time window axis, `base_sha` source-floor anchor; per-cell wrapper composes Phase 213 + Phase 214 unchanged; source-bind + egress IP verification per cell — Phase 220
- ✓ AGGREGATE-01..03 — Stdlib + PyYAML cube aggregator with replicate-aware verdicts, Mann-Whitney U (two-sided, normal approximation), and bootstrap 95% percentile CI (B=2000, seeded `random.Random`); canonical control cell never aggregated with supplemental cells; pinned `.flent.gz` fixtures + golden p-values/CI bounds — Phase 220
- ✓ CLOSEOUT-01..03 — `221-CLOSEOUT.md` published `carried_narrower_with_close_with_prejudice_rule` as authoritative post-D-10-BGP-overlay verdict; per-cell verdict table + matrix-level verdict + per-driver attribution; folded `2026-04-08-investigate-tcp-12down` todo closed with CRITERIA-02 rule attached verbatim; bidirectional commit-SHA-anchored cross-cite — Phase 221
- ✓ SAFE-11 — Mutation-boundary pytest enforced expanded allowlist (`configs/`, `deploy/systemd/`, `scripts/`, `tests/fixtures/phase22*/`, `docs/`, additive `src/wanctl/history.py`) at every phase boundary across all three phases; zero controller-path source diff — Phases 219, 220, 221

### Active

**v1.51 Post-Migration Consolidation** (requirements being defined — REQ-IDs assigned in REQUIREMENTS.md):

- [ ] **Cleanup boundary** — encode the binding no-delete list before any sweep work
- [ ] **`phase231-rollback.sh` confirm-path fix** — pre-live-rollback hygiene, no rollback exercise
- [ ] **Digest permission todo closure** — validate-then-close against Phase 208 T12/TOOL-03 behavior
- [ ] **"Safe to remove soon" sweep** — trial scripts, stale docs, Spectrum-only hardcoding remnants
- [ ] **Planning metadata reconciliation** — orphan quick-tasks, silicom todo/SEED-006 consistency, Phase 230 Nyquist decision
- [ ] **SAFE-15** — controller-path zero-diff invariant

(Note: prior candidate list here shipped in v1.50 — ATT deploy path, soak-monitor ATT coverage, ATT artifact tests, soak criteria all delivered. Upload autorate and the native-controller role decision remain future/gated.)

### Deferred

- [ ] **VERIFY-01 / VERIFY-02 (v1.45 + v1.46)** — Phase 218 event-gated; needs natural production DOCSIS flapping event with `peak_transition_count > 30` on either WAN; no synthetic event generation per ROADMAP.
- ✓ **Steering runtime/source version-drift alignment** — RESOLVED in v1.48 (Phases 222–224): live steering daemon aligned `1.39 → 1.47` in production, canary `kept_aligned`, SAFE-12 held.
- [ ] **Spectrum upload reclaim re-attempt (v1.46 carry → v1.48+)** — Phase 215 bounded VOID exhausted at ceiling 20; revised gate / different probe shape needed.
- [ ] SSH connection pooling — Low ROI, REST API already optimal.
- [ ] CAKE stats caching — Not needed, flash wear protection working.
- [ ] Prometheus/Grafana export (OBSV-01..04) — Infrastructure not yet deployed; deferred from v1.23.
- [ ] v1.39 measurement-validation gates (TIME-03/04, MEAS-06, VALN-02/03) — superseded by v1.40+ measurement axis; not retroactively retargetable.
- [ ] VALN-05b ATT cake-primary canary — administratively deferred since v1.40; gating phrase historical; requires its own ADR for resolution.
- [ ] SEED-006 — Silicom bypass NIC tooling + test harness. Dormant; candidate for v1.47+ depending on scoping.
- [ ] SEED-007 — Storage hygiene (autorate flat-gauge fire-on-change + CAKE tin skip-on-unchanged consumer audit). Dormant; candidate for v1.47+ depending on PERF evidence.
- ✓ WR-01 — `scripts/check-safe07-source-diff.sh` dirty-tree fail-closed gap resolved in v1.44 Phase 207 (unstaged, staged, and untracked `src/wanctl/` surfaces covered).
- ✓ WR-02 — `scripts/soak-capture.sh` transient capture abort gap resolved in v1.44 Phase 207 with bounded failure tolerance and sidecar TSV diagnostics.
- ✓ `secondary_gate_legacy` block removal — completed in v1.44 Phase 207; live soak summaries now emit only `secondary_gate_completed_window`.
- ✓ CALIB-02 YAML-promotion evaluation — routed to NO in v1.44 Phase 207; threshold remains in `scripts/calib_02_threshold.json`, with deeper YAML knob-shape design deferred to T17(b)/SEED-005.
- ✓ T17(a) / TOOL-01 — `aggregate_watchdog()` bad `gate_column` / unsupported `statistic` now fails closed in v1.44 Phase 208 while preserving the 10-key `secondary_gate_completed_window` schema.
- ✓ T9 / TOOL-02 — `wanctl-history --ingestion-rate` landed in v1.44 Phase 208 with table/object JSON output, per-WAN counts, and explicit legacy/ad-hoc `--db` + `--wan` SQL-filter semantics.
- ✓ T12 / TOOL-03 — `wanctl-operator-summary --digest` now tolerates unreadable DB opens, output-write `OSError`, and discovery `OSError` without masking schema/query corruption.

### Out of Scope

- Machine learning-based bandwidth prediction — unnecessary complexity
- Full Prometheus/Grafana stack as hard dependency — export is optional, core operation remains self-contained
- Breaking changes to configuration format — maintain compatibility
- Generic multi-vendor router support — Linux CAKE backend is specific to transparent bridge offload, not general non-MikroTik support

## Context

wanctl is a production dual-WAN controller deployed in a home network environment. Reliability and backward compatibility are critical.

**Current production issue (2026-04-15):** a live 30-second `flent tcp_12down` run to Dallas reproduced multi-second tail latency (`p99 3059.16ms`) while Spectrum still reported `healthy`, stayed `GREEN`, and did not fire burst detection. The same run showed repeated three-reflector miss bursts plus protocol-correlation churn, while steering remained healthy and VM steal stayed low.

**Current engineering hypothesis:** the active gap is measurement resilience rather than core congestion-state logic. The background RTT path can degrade from 3 reflectors to 2 to 1 with no confidence penalty, and on zero-success cycles it preserves stale cached RTT until the hard stale threshold trips.

**Architecture:** Layered design (Router Control → Measurement → Congestion Assessment → State Management → Control Logic). Python 3.12 with Ruff linting, pytest testing, proper error handling.

**v1.0 Performance Optimization (2026-01-13):**

- Profiled 352,730 samples, discovered 30-41ms cycles (not ~200ms as assumed)
- Reduced cycle interval from 2s to 50ms (40x faster)
- Event loop architecture replaced timer-based execution
- See: `docs/PRODUCTION_INTERVAL.md`

**v1.1 Code Quality (2026-01-14):**

- 10 phases of systematic refactoring (Phases 6-15)
- Created shared modules: signal_utils.py, systemd_utils.py
- Consolidated 4 redundant utility modules
- Documented 12 refactoring opportunities in CORE-ALGORITHM-ANALYSIS.md
- Extracted methods from WANController and SteeringDaemon
- Unified state machine (CAKE-aware + legacy)
- Integrated Phase2BController with dry-run mode
- Added 120 new tests (474 → 594)

**v1.2 Configuration & Polish (2026-01-14):**

- 5 phases of configuration improvements (Phases 16-20)
- Fixed Phase2B timer interval bug
- Added baseline_rtt_bounds validation
- Deprecated legacy steering params with warnings
- Added 77 edge case tests (594 → 671)
- Enabled Phase2B confidence scoring in dry-run mode

**v1.3 Reliability & Hardening (2026-01-21):**

- 4 phases of safety and deployment improvements (Phases 21-24)
- REST-to-SSH failover with FailoverRouterClient
- Baseline freeze invariant tests, state corruption recovery
- Deployment validation script (423 lines)
- 54 new tests (671 → 725)

**v1.4 Observability (2026-01-24):**

- 2 phases of monitoring infrastructure (Phases 25-26)
- HTTP health endpoint for steering daemon on port 9102
- Live steering state exposure (confidence, congestion, decisions)
- Kubernetes-compatible health probes (200/503)
- 28 new tests (725 → 752)

**v1.5 Quality & Hygiene (2026-01-24):**

- 4 phases of quality infrastructure (Phases 27-30)
- Test coverage infrastructure (pytest-cov, 72% baseline)
- Codebase cleanup (zero dead code, zero TODOs)
- Documentation verified to v1.4.0 (14 issues fixed)
- Security audit (zero CVEs, `make security` target)

**v1.6 Test Coverage 90% (2026-01-25):**

- 7 phases of comprehensive testing (Phases 31-37)
- Coverage increased from 45.7% to 90.08%
- 743 new tests added (747 → 1,490 total)
- CI enforcement via fail_under=90
- All major modules tested: backends, state, metrics, controllers, CLI tools

**v1.7 Metrics History (2026-01-25):**

- 5 phases of metrics infrastructure (Phases 38-42)
- SQLite storage with automatic downsampling
- `wanctl-history` CLI tool for queries
- `/metrics/history` HTTP API endpoint
- 237 new tests (1,490 → 1,727 total)

**v1.8 Resilience & Robustness (2026-01-29 → 2026-03-06):**

- Phase 43: Error detection & reconnection (RouterConnectivityState, classify_failure_type)
- Phase 44: Fail-safe behavior (PendingRateChange, watchdog distinction)
- Phase 44.1: Codebase health & coverage recovery (test pollution fix, 91%+ coverage)
- Phase 45: Graceful shutdown (cleanup parity, deadline tracking)
- Phase 46: Contract tests — deferred (mocks accurate, no drift observed)
- 154 new tests (1,727 → 1,881 total)

**v1.9 Performance & Efficiency (2026-03-06 → 2026-03-07):**

- Phase 47: Cycle profiling infrastructure (PerfTimer, OperationProfiler, --profile flag)
- Phase 48: Hot path optimization (icmplib raw ICMP sockets, -3.4ms avg cycle)
- Phase 49: Telemetry & monitoring (structured logs, health endpoint cycle budget)
- 97 new tests (1,881 → 1,978 total)

**v1.10 Architectural Review Fixes (2026-03-07 → 2026-03-09):**

- Phase 50: Critical hot-loop & transport fixes (sub-cycle retries, config authority, failover re-probe)
- Phase 51: Steering reliability (state normalization, anomaly semantics, stale baseline, safe JSON)
- Phase 52: Operational resilience (SSL defaults, SQLite recovery, disk monitoring, CVE patch)
- Phase 53: Code cleanup (self.ssh → self.client, stale docstrings, import cleanup, ruff fixes)
- Phase 54: Codebase audit (duplication consolidated, module boundaries, complexity extraction)
- Phase 55: Test quality (behavioral integration, failure cascade, reduced-mock tests)
- Phase 56-57: Gap closure (verify_ssl chain, config docs, fixture consolidation)
- 131 new tests (1,978 → 2,109 total), 27/27 requirements satisfied

**v1.11 WAN-Aware Steering (2026-03-09 → 2026-03-10):**

- Phase 58: State file extension (congestion zone persistence, dirty-tracking exclusion)
- Phase 59: WAN state reader + signal fusion (confidence scoring, recovery gate, BaselineLoader extraction)
- Phase 60: Configuration + safety + wiring (YAML wan_state, grace period, enabled gate, config-driven weights)
- Phase 61: Observability + metrics (health endpoint, 3 SQLite metrics, WAN context in logs)
- 101 new tests (2,109 → 2,210 total), 17/17 requirements satisfied

**v1.12 Deployment & Code Health (2026-03-10 → 2026-03-11):**

- Phase 62: Deployment alignment (pyproject.toml as canonical source for all artifacts)
- Phase 63: Dead code removal (pexpect, dead subprocess import, stale timeout_total)
- Phase 64: Security hardening (password clearing, per-request SSL suppression, safe defaults)
- Phase 65: Fragile area stabilization (state file schema contract, check_flapping contract)
- Phase 66: Config extraction (BaseConfig consolidation, RotatingFileHandler, deployment contract tests)
- 53 new tests (2,210 → 2,263 total)

**v1.14 Operational Visibility (2026-03-11):**

- Phase 73: Dashboard foundation (config, poller, CLI, WanPanel, SteeringPanel, StatusBar, app wiring)
- Phase 74: Visualization & history (sparklines, cycle gauge, history browser, TabbedContent)
- Phase 75: Layout & compatibility (responsive layout, resize hysteresis, color flags, tmux verified)
- 145 new dashboard tests (2,300 → 2,445 total)
- Post-milestone: sparkline rate normalization and zero-anchor fix for visual consistency

**v1.15 Alerting & Notifications (2026-03-12):**

- Phase 76: Alert engine core (AlertEngine class, per-event cooldown, SQLite persistence, YAML config parsing)
- Phase 77: Webhook delivery (AlertFormatter Protocol, DiscordFormatter, WebhookDelivery with retry/rate-limit, SIGUSR1 webhook_url reload)
- Phase 78: Congestion & steering alerts (sustained congestion DL/UL timers, steering activation/recovery with duration)
- Phase 79: Connectivity & anomaly alerts (WAN offline/recovery, baseline drift, congestion flapping)
- Phase 80: Observability & CLI (health endpoint alerting section, wanctl-history --alerts)
- 221 new tests (2,445 → 2,666 total)
- Deployed to production with Discord webhook delivery verified

**v1.16 Validation & Operational Confidence (2026-03-12 → 2026-03-13):**

- Phase 81: Config validation foundation (`wanctl-check-config` with 6 categories, CheckResult model)
- Phase 82: Steering config support (auto-detection, cross-config topology checks, JSON output)
- Phase 83: CAKE qdisc audit (`wanctl-check-cake` with connectivity, queue tree, CAKE type, max-limit, mangle)
- 157 new tests (2,666 → 2,823 total)
- Key: Never instantiate Config() in check tools — use SCHEMA class attributes only
- Key: SimpleNamespace wraps router config dict for RouterOSREST.from_config() compatibility

**v1.17 CAKE Optimization & Benchmarking (2026-03-13 → 2026-03-16):**

- Phase 84: CAKE detection & optimizer foundation (get_queue_types, OPTIMAL_CAKE_DEFAULTS, diff engine)
- Phase 85: Auto-fix CLI integration (--fix flag, daemon lock check, snapshot backup, PATCH to /rest/queue/type)
- Phase 86: Bufferbloat benchmarking (BenchmarkResult dataclass, compute_grade, flent RRUL orchestration)
- Phase 87: Benchmark storage & comparison (benchmarks table, auto-store, compare/history subcommands)
- 70 new tests (2,823 → 2,893 total)
- Production tested: 19 runs on Spectrum (Grade A early morning), 7 runs on ATT (Grade A+ consistently)
- Production bugs found and fixed: flent -D flag, icmplib baseline, **main** block
- CAKE params optimized on both WANs (nat, ack-filter, wash), ATT overhead corrected (pppoe-ptm → bridged-ptm)
- Router mangle rule ordering fix: FORCE_OUT_ATT and ADAPTIVE steering moved before Trust EF accept rules

**v1.18 Measurement Quality (2026-03-16 → 2026-03-17):**

- Phase 88: Signal processing core (Hampel filter, jitter/variance EWMA, confidence scoring, observation mode)
- Phase 89: IRTT foundation (subprocess wrapper, JSON parsing, graceful fallback, Dockerfile)
- Phase 90: IRTT daemon integration (background thread, lock-free cache, protocol correlation)
- Phase 91: Container networking audit (0.17ms overhead, negligible jitter, report-only closure)
- Phase 92: Observability (health endpoint signal_quality + irtt sections, SQLite metrics persistence)
- 363 new tests (2,893 → 3,256 total)
- Production deployed and verified on both containers
- IRTT enabled with Dallas server (104.200.21.31:2112), live measurements confirmed
- Signal processing active: Spectrum 14% outlier rate, ATT 0% — validates per-WAN design

**v1.19 Signal Fusion (2026-03-17 to 2026-03-18):**

- Phase 93: Reflector quality scoring (rolling deques, deprioritization, recovery probes, graceful degradation)
- Phase 94: OWD asymmetric detection (send_delay vs receive_delay from IRTT bursts, SQLite persistence)
- Phase 95: IRTT loss alerts (sustained loss timers, AlertEngine integration, Discord delivery)
- Phase 96: Dual-signal fusion core (\_compute_fused_rtt, weighted average, multi-gate fallback)
- Phase 97: Fusion safety & observability (disabled by default, SIGUSR1 toggle, health endpoint fusion section)
- ~202 new tests (3,256 to ~3,458 total)
- Fusion ships disabled — graduation requires production SIGUSR1 enable after deploy

**v1.13 Legacy Cleanup & Feature Graduation (2026-03-11):**

- Phase 67: Production config audit (SSH-verified modern params on both containers)
- Phase 68: Dead code removal (cake_aware branching eliminated, 7 obsolete config files deleted)
- Phase 69: Legacy fallback removal (deprecate_param() helper, 8 params retired with warnings)
- Phase 70: Legacy test cleanup (docstrings, fixture names, comments updated)
- Phase 71: Confidence graduation (SIGUSR1 hot-reload, dry_run: false, production verified)
- Phase 72: WAN-aware enablement (SIGUSR1 wan_state reload, 4-step degradation verification)
- 37 new tests (2,263 → 2,300 total)

## Constraints

- **Production deployment**: Running in home network — must maintain stability and reliability
- **No breaking changes**: Existing configurations and APIs must continue to work
- **Python 3.12**: Runtime and tooling locked to this version
- **systemd integration**: Deployment pattern is fixed (service templates, timers)
- **Dual transport**: Must maintain both REST API (preferred) and SSH (fallback) support
- **No external monitoring**: Keep self-contained for core operation (Prometheus export is optional, not required for function)
- **Backward compatibility**: Existing state files and configuration must remain compatible
- **Scope**: Do not retune congestion thresholds, change CAKE control semantics, or reopen steering policy unless measurement-resilience work proves a direct dependency

## Key Decisions

| Decision                                          | Rationale                                                  | Outcome                         | Date       |
| ------------------------------------------------- | ---------------------------------------------------------- | ------------------------------- | ---------- |
| Profile before optimizing                         | Measure actual performance vs assumptions                  | ✓ Assumptions were wrong        | 2026-01-10 |
| 50ms cycle interval (40x faster)                  | Use headroom for faster congestion response                | ✓ Production stable             | 2026-01-13 |
| Preserve EWMA time constants via alpha scaling    | Mathematical correctness, predictable behavior             | ✓ Implemented correctly         | 2026-01-13 |
| Risk-based refactoring (LOW/MEDIUM/HIGH)          | Protect production stability during code quality work      | ✓ All protected zones preserved | 2026-01-13 |
| Define 9 protected zones with exact line ranges   | Prevent accidental core algorithm modification             | ✓ Documented in analysis        | 2026-01-13 |
| Phase2BController dry-run mode for integration    | Safe production validation before enabling routing changes | ✓ Integrated, validating        | 2026-01-14 |
| Unified state machine (CAKE-aware + legacy)       | Reduce code duplication, single code path                  | ✓ Implemented with tests        | 2026-01-14 |
| Extract methods from run_cycle() systematically   | Improve testability and maintainability                    | ✓ 120 new tests added           | 2026-01-14 |
| Port 9102 for steering health (9101 for autorate) | Separate health endpoints per daemon                       | ✓ Deployed, Kubernetes-ready    | 2026-01-24 |

| Advisory coverage threshold (no fail_under) | Measure first before enforcing | ✓ Baseline at 72% | 2026-01-24 |
| 4-tool security scanning (`make security`) | Comprehensive coverage: deps, code, secrets, licenses | ✓ All scans pass | 2026-01-24 |
| icmplib replaces subprocess ping | Eliminate fork/exec overhead in RTT hot path | ✓ -3.4ms avg (8.3%) | 2026-03-06 |
| OPTM-02/03 closed by profiling evidence | Router comm 0.0-0.2ms, CAKE stats at 2s interval | ✓ No code change needed | 2026-03-06 |
| Shared \_build_cycle_budget() helper | Single source of truth for health endpoint telemetry | ✓ Both endpoints consistent | 2026-03-06 |
| Sub-cycle retry with single attempt | Prevent multi-second blocking in 50ms hot loop | ✓ Max 50ms retry delay | 2026-03-07 |
| Self-healing transport failover | Auto-recover primary REST after SSH fallback | ✓ Exponential backoff 30-300s | 2026-03-07 |
| verify_ssl=True default everywhere | Secure by default, explicit opt-out for self-signed | ✓ All 3 layers aligned | 2026-03-09 |
| Daemon duplication → shared helpers | daemon_utils.py + perf_profiler.py reduce copy-paste | ✓ Both daemons import shared | 2026-03-08 |
| Fixture delegation over duplication | Shared conftest + class overrides vs. copy-paste | ✓ -481 lines, 21 fixtures | 2026-03-09 |
| WAN state strictly amplifying | WAN alone < steer_threshold; CAKE remains primary signal | ✓ WAN_RED=25 < threshold=55 | 2026-03-09 |
| Dirty-tracking exclusion for zone | Prevent 20x write amplification from zone changes at 20Hz | ✓ Zero extra writes | 2026-03-09 |
| Ship disabled by default | No behavioral change on upgrade; explicit opt-in required | ✓ wan_state.enabled: false | 2026-03-09 |
| Warn+disable for invalid config | Invalid wan_state config degrades gracefully, never crashes | ✓ Daemon stays running | 2026-03-09 |
| Zone piggybacked on existing read | Zero additional I/O; BaselineLoader returns (rtt, zone) tuple | ✓ FUSE-01 satisfied | 2026-03-09 |
| pyproject.toml as single source of truth | Dockerfile, install.sh, deploy.sh derive from one place | ✓ Contract tests enforce | 2026-03-10 |
| BaseConfig consolidation (6 fields) | Eliminate duplicate YAML-to-attribute boilerplate | ✓ Both daemons use shared | 2026-03-11 |
| RotatingFileHandler with getattr defaults | Backward-compatible log rotation without config changes | ✓ 10MB/3 backups default | 2026-03-11 |
| Password clearing after construction | Minimize credential lifetime in memory | ✓ Eager resolve + delete | 2026-03-10 |
| Contract tests parametrized from source | Adding deps auto-creates test cases | ✓ 17 deployment tests | 2026-03-11 |
| deprecate_param warn+translate pattern | Legacy params produce clear warnings, not silent fallback | ✓ 8 params retired | 2026-03-11 |
| SIGUSR1 generalized hot-reload | Single signal reloads both dry_run and wan_state.enabled | ✓ Zero-downtime config toggle | 2026-03-11 |
| Confidence steering live (dry_run: false) | Validated in dry-run since v1.2, all signals correct | ✓ Production active | 2026-03-11 |
| WAN-aware steering live (wan_state.enabled: true) | 4-step degradation verification passed | ✓ Production active | 2026-03-11 |
| Grace period re-trigger on SIGUSR1 re-enable | Safe ramp-up after operator toggle | ✓ 30s grace confirmed | 2026-03-11 |
| Textual framework for TUI dashboard | Async-native, CSS-styled widgets, active maintenance | ✓ Clean widget composition | 2026-03-11 |
| Dashboard standalone — zero daemon imports | All data via HTTP health endpoints | ✓ No code coupling | 2026-03-11 |
| Rich Text renderer + Widget wrapper pattern | Enables unit testing without App.run_test() | ✓ 133 tests, no async machinery | 2026-03-11 |
| Bounded deques (maxlen=120) for sparklines | Constant memory regardless of dashboard uptime | ✓ ~2min rolling window | 2026-03-11 |
| Dual autorate pollers for multi-container | Each container has its own health endpoint | ✓ Independent polling + backoff | 2026-03-11 |
| Sparkline zero-anchor for consistent rendering | Textual min==max renders as flat line | ✓ Both WANs show full bars | 2026-03-11 |
| Alert engine embedded in both daemons | Not standalone process — fires in control loop context | ✓ Zero IPC overhead | 2026-03-12 |
| Per-event (type, WAN) cooldown key | Independent suppression per alert type per WAN | ✓ Fine-grained control | 2026-03-12 |
| AlertFormatter Protocol for delivery | New backends (ntfy.sh) need only a formatter class | ✓ Extensible, no engine changes | 2026-03-12 |
| Inline retry in WebhookDelivery | Cleaner thread-context control than decorator | ✓ Background thread dispatch | 2026-03-12 |
| fire_count before persistence | Counts intent, not storage success | ✓ Accurate even if SQLite fails | 2026-03-12 |
| Alerting disabled by default | No behavioral change on upgrade | ✓ Explicit opt-in required | 2026-03-12 |
| SIGUSR1 chain: dry_run + wan_state + webhook | Three independent reloads from single signal | ✓ Zero-downtime config toggle | 2026-03-12 |
| Never instantiate Config() in check tools | Avoid daemon side effects (locks, log dirs) | ✓ SCHEMA class attrs only | 2026-03-12 |
| CheckResult/Severity shared data model | Consistent output format across CLI tools | ✓ Both tools import from check_config | 2026-03-13 |
| SimpleNamespace for router config wrapping | get_router_client() needs attr access, not dict | ✓ No daemon imports needed | 2026-03-13 |
| Max-limit diff as informational PASS | max-limit changes dynamically during congestion | ✓ Not flagged as error | 2026-03-13 |
| CAKE params on /rest/queue/type endpoint | Queue tree is dynamic (autorate), queue type is static config | ✓ Separate from tree PATCH | 2026-03-13 |
| --fix requires daemon stopped (lock check) | Prevent autorate from overwriting fix immediately | ✓ Safe mutation | 2026-03-13 |
| flent/netperf as subprocess, not Python import | Unstable internal API, heavy GUI deps | ✓ subprocess.run | 2026-03-13 |
| flent -D (data dir) instead of -o | flent 2.1.1 ignores -o for gzipped data | ✓ Glob for .flent.gz | 2026-03-16 |
| icmplib for benchmark baseline RTT | subprocess ping races with daemon ICMP probes | ✓ Reliable 3/3 | 2026-03-16 |
| Direct SQLite writes (not MetricsWriter) | CLI runs once and exits, singleton is overkill | ✓ Simple connect/insert/close | 2026-03-15 |
| Flat benchmarks table (one row per run) | Simple queries, rarely >50 rows, all fields as columns | ✓ 19 columns | 2026-03-15 |
| Bare invocation = run (no `run` subcommand) | Backward compatible, argparse optional subparsers | ✓ compare/history as subcommands | 2026-03-15 |
| ATT overhead bridged-ptm not pppoe-ptm | BGW320 IP passthrough = no PPPoE on router segment | ✓ 22 bytes (was 30) | 2026-03-16 |
| Pre-EWMA signal processing (observation mode) | Filter EWMA input without changing congestion control | ✓ Hampel replaces outliers, state untouched | 2026-03-17 |
| Lock-free IRTTThread caching | Frozen dataclass + GIL = atomic pointer swap, zero lock contention | ✓ 50ms hot path unaffected | 2026-03-17 |
| IRTT write-on-new-measurement deduplication | Prevent 200x SQLite row duplication at 20Hz cycle rate | ✓ \_last_irtt_write_ts tracking | 2026-03-17 |
| Container overhead negligible (0.17ms) | Audit confirmed veth/bridge adds <0.5ms, jitter <10% of WAN | ✓ Report-only closure | 2026-03-17 |
| Protocol correlation as simple ratio | icmp_rtt / irtt_rtt with 1.5/0.67 thresholds | ✓ Path asymmetry on ATT expected | 2026-03-17 |
| Signal processing always active (no enable flag) | Lightweight stdlib math, observation mode = zero risk | ✓ Activates on deploy without config | 2026-03-17 |
| IRTT disabled by default | Requires enabled: true + server in YAML | ✓ Safe upgrade path | 2026-03-17 |
| Reflector warmup guard (>=10 measurements) | Prevent false deprioritization on startup | ✓ No startup false positives | 2026-03-17 |
| Graceful degradation for reflector count | 3+=median, 2=avg, 1=single, 0=force-best | ✓ Never fully loses measurement | 2026-03-17 |
| OWD uses burst-internal delays (no NTP) | NTP clock sync fragile in LXC containers | ✓ Same-path, no external dependency | 2026-03-18 |
| OWD ratio capped at 100.0 | Prevent SQLite overflow from near-zero denominator | ✓ Bounded safely | 2026-03-18 |
| Single irtt_loss_recovered alert type | Direction field distinguishes up/down recovery | ✓ Simpler than separate types | 2026-03-18 |
| Fusion default ICMP 0.7 / IRTT 0.3 | ICMP at 20Hz vs IRTT at 0.1Hz — dominance reflects cadence | ✓ Weighted appropriately | 2026-03-18 |
| \_fusion_icmp_weight read once in **init** | Avoid per-cycle config lookup in 50ms hot path | ✓ Zero per-cycle overhead | 2026-03-18 |
| Fusion ships disabled (fusion.enabled: false) | Proven graduation pattern from v1.13 | ✓ Zero behavioral change on deploy | 2026-03-18 |
| SIGUSR1 reloads both enabled + icmp_weight | Atomic config snapshot prevents inconsistent state | ✓ Single reload updates both | 2026-03-18 |
| No SQLite for fusion state | Input signals already persisted, fused_rtt derivable | ✓ No additional persistence needed | 2026-03-18 |
| fused_rtt + load_ewma persisted to SQLite metrics | Operators need trend analysis of fusion behavior | ✓ 2 new metrics | 2026-03-18 |
| Boot scripts always exit 0 | Availability over correctness — wanctl with suboptimal NICs better than no wanctl | ✓ Missing NIC warns, doesn't block | 2026-04-02 |
| NIC tuning as shell script, not systemd ExecStart | Script is testable, loggable, and reusable vs inline ethtool lines | ✓ 9 logger calls, idempotent | 2026-04-02 |
| Wants= not Requires= for NIC tuning dep | wanctl should start even if NIC tuning fails | ✓ Availability-first design | 2026-04-02 |
| 3-core IRQ affinity (ens16=CPU0, ens17=CPU2, ATT=CPU1) | Distribute bridge+CAKE softirq load across all cores | ✓ RRUL load avg 1.13→0.87 (-23%) | 2026-04-04 |
| netdev_budget=600 (doubled from default) | Bridge+CAKE workload processes more packets per softirq cycle | ✓ Persisted via sysctl.d | 2026-04-04 |
| SFP+ multi-queue-ethernet-default (mq-pfifo) | Eliminate TX queue drops under burst traffic | ✓ 404K drops → 0 | 2026-04-04 |
| RouterOS IRQ cpu format: numeric string not 'cpu1' | REST API requires '1' not 'cpu1' for IRQ affinity | ✓ Switch IRQ 36 pinned to cpu1 | 2026-04-04 |
| ZeroTier interface restriction (WAN/LAN only) | ZT binding to wireguard1 caused 850K+ TX errors | ✓ Error rate 43K/day → 0 | 2026-04-05 |
| nftables create-then-delete for idempotent reload | flush fails on first boot (table doesn't exist) | ✓ Safe on boot and reload | 2026-04-04 |
| Bridge DSCP via conntrack marks (not direct DSCP set) | nftables bridge hooks can't set DSCP directly on forwarded packets | ✓ Voice/Bulk/BE tin separation | 2026-04-04 |
| Measurement degradation must be explicit, not inferred from cached RTT | Production `tcp_12down` can show catastrophic latency while autorate still reports healthy/GREEN | — Pending | 2026-04-15 |
| v1.43 phase order 002 → 004 → 003 (not seed-priority order) | The 24h Spectrum soak is the milestone's most expensive evidence primitive; SEED-004 per-sample delta must be live before that soak fires so one run produces both recalibration baseline and target-edge distribution | ✓ Encoded in ROADMAP (joint Codex+Claude scope decision) | 2026-05-06 |
| v1.43 closeout invariant: no controller tuning | SEED-005 conservative UL tuning sweep is structurally barred from v1.43 to keep the observe/calibrate/tune boundary clean; v1.42 RETRO Lesson #1 was metric-semantics framing, and tuning under unverified observability would re-confound the evidence | ✓ Encoded as SAFE-07 milestone invariant | 2026-05-06 |
| Decisions made jointly with Codex are explicitly recorded | Avoids re-deriving same decisions in future sessions; Codex's reasoning over the seed dependency DAG and soak economics belongs in project memory | ✓ Joint Claude+Codex scope decision row added | 2026-05-06 |
| v1.46 spine: drift audit → baseline harness → measurement-collapse → reclaim canary → recovery decision → cycle budget | Evidence-first quality recovery — observe before tuning; never treat `/health.GREEN` as proof of user-perceived quality | ✓ All 6 phases shipped; classifier returned `ambiguous`/`reflector_loss`; reclaim VOID; performance is not the limit | 2026-05-30 |
| v1.46 reclaim canary stops at first bounded VOID, no force-promote | Production control loop: a tested negative answer with rollback anchor beats unverified optimism | ✓ Spectrum rolled back to ceiling 18 after 3 ceiling-20 attempts; no quality reclaim claimed | 2026-05-30 |
| Phase 218 (v1.45 + v1.46 VERIFY) deferred to event-gated watch | Synthetic event generation would invalidate the very metric VERIFY is designed to measure; production-side natural evidence is the only sound trigger | ✓ Encoded in ROADMAP as no-synthetic-generation rule | 2026-05-30 |
| Codex consulted at v1.46 close on milestone-shape decision | Independent second opinion on whether to start v1.47 vs drain backlog vs stand by; Codex recommended A + tiny B housekeeping, matching primary analysis | ✓ Recorded in /gsd-progress conversation; v1.47 path chosen | 2026-05-30 |
| v1.47 spine: D-first (ingestion-rate) → A1 (matrix runner) → A2 (matrix evidence + closeout) | Scope D ships first per Pitfall 11 to support Phase 218 audit evidence regardless of v1.47 timing; A1 lands pre-registered CRITERIA + harness before any operator-driven evidence collection in A2 | ✓ All 3 phases shipped; 18/18 REQs satisfied; tcp_12down closed with close-with-prejudice | 2026-06-02 |
| v1.47 pre-registered CRITERIA thresholds locked at Phase 220 plan time | Prevents Pitfall 2 (threshold-after-data bias); thresholds written into `220-CONTEXT.md` before any live cell run, never edited after | ✓ Encoded in CRITERIA-01; YAML SHA replay anchor in closeout report | 2026-06-02 |
| D-10 BGP overlay applied to raw matrix verdict | BGP path drift mid-run contaminates supplemental Vultr cells; raw aggregator `defect_located` on three cells is not a valid defect locator if the network underneath was a moving target | ✓ Authoritative post-overlay verdict published in `221-CLOSEOUT.md`; raw verdict preserved for audit | 2026-06-02 |
| Close-with-prejudice rule applied to tcp_12down folded todo | Prevents Pitfall 2's degenerate "carried-narrower forever" outcome; carrying a hypothesis without a forcing function is not closure | ✓ CRITERIA-02 attached verbatim to folded todo; no v1.48+ reopen without independent new production evidence (e.g., real production p99 incident captured in DB) | 2026-06-02 |
| v1.47 read-only milestone — no controller mutation triggered by matrix results | Tuning under unverified evidence re-confounds the very signal the matrix was designed to measure; v1.47 may recommend, never implement | ✓ Encoded as SAFE-11 milestone invariant; zero controller-path source diff across all three phases | 2026-06-02 |
| cake-autorate replaces native wanctl autorate on Linux CAKE shapers | Spectrum trial showed materially better user-visible tail latency than continued native-controller tuning; upstream cake-autorate is purpose-built for variable-rate links | ✓ Both WANs live 2026-06-08; wanctl@ disabled as rollback; bridge preserves health/state/metrics contract so steering + tooling unchanged | 2026-06-08 |
| wanctl role split: cake-autorate owns rate control, wanctl owns supervision/observability/steering/MikroTik | Keep the proven contract surfaces (health, metrics, steering, deploy, ops) while delegating the rate algorithm; MikroTik/RouterOS control remains first-class native wanctl | ✓ Recorded in WANCTL_CAKE_AUTORATE_FUTURE.md; native controller NOT deleted until post-soak decision | 2026-06-05 |
| v1.49 closed overtaken-by-events without Phase 228 verdict | The verdict/rollback gated a bridge-root CAKE topology that no longer exists; computing it post-hoc would be theater. Evidence direction (REJECT diffserv4-wash, old topology) recorded faithfully, marked non-transferable | ✓ GATE-02/03 unmet-overtaken; wash re-validated independently under cake-autorate member-NIC topology | 2026-06-09 |
| ATT deploy path as sibling function, not generic WAN abstraction | Only parameterize as far as the ATT path requires; premature `$wan` symmetry refactor adds risk without payoff in a two-WAN deployment | ✓ Good — Phase 229 shipped at Spectrum parity with zero controller-path diff; drift gates protect both lists | 2026-06-09 |
| SOAK-02 closed via no-mutation provable path, not live rollback exercise | Live rollback flaps production WANs for a procedural proof; double-gated script + both-WAN read-only preflight (`overall_pass: true`) proves the path without the risk | ✓ Good — operator-accepted 2026-06-10; residual confirm-path fix noted before any future live exercise | 2026-06-10 |
| Native `wanctl@<wan>` kept as soak-monitor fallback scanning path | External cake-autorate mode is detected per WAN; portable deployments still run native mode, so the fallback preserves link-agnostic behavior | ✓ Good — `is_external_cake_mode` + `external_units_for` generalize without Spectrum-only hardcoding | 2026-06-09 |
| SOAK-01 C3 criterion encoded as objective constants, not operator judgment | "No sustained errors" must be machine-derivable or the migration-held verdict is vibes; historical bounded err lines pass only under encoded thresholds | ✓ Good — both-WAN PASS machine-derived, operator confirmed after capture | 2026-06-10 |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd:transition`):

1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd:complete-milestone`):

1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---

_Last updated: 2026-06-10 at v1.51 milestone open (Post-Migration Consolidation — joint Claude + Codex scope decision). Both WANs run cake-autorate external-controller mode with wanctl state bridges; `wanctl@{spectrum,att}` disabled as the verified rollback path; native wanctl remains the MikroTik controller and portable default. Phase 218 watch dormant (instrumentation lives in the non-live native controller)._
