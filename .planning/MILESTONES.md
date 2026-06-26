# Project Milestones: wanctl

## v1.57 Supported read-only RouterOS ownership inspection (Shipped: 2026-06-26)

**Phases completed:** 3 phases (258–260), 8 plans

**Key accomplishments:**

- Repaired the v1.56 read-only RouterOS access blocker: added a supported GET-only REST inspection path (`_handle_netwatch_print`/`_handle_script_print` + `readonly_validator` allowlist), replacing the inaccessible nested-SSH `router.key`; live `ACCESS02_PROOF_PASS route=17 netwatch=3 script=20`.
- Read live Netwatch + default-route ownership over the validated path and attributed Netwatch as owner, surfaced distinctly from `:9101` bridge and `:9102` steering health with no payload-shape regression (`INSPECT_PROOF_PASS observed_owner=netwatch route_mutating_active=4`).
- Reran the v1.56-blocked bounded 636s dry-run observation from `cake-shaper` and emitted a 257-shaped canary-readiness packet.
- Caught and fixed a D-07 cross-check detector mismatch post-close (commit `7a96aa8f`): the harness cross-check missed `/system script run` indirection the live guard resolves; unified both on one `detect_netwatch_route_conflicts()`, verified live (cross-check 0→4, divergence cleared) — final verdict `ready-for-approval`.
- Preserved SAFE-21 end-to-end: read-only inspection / dry-run observation only, Netwatch remains owner, no route mutation, owner flip, or active canary.

**Audit:** `passed` — 10/10 REQs satisfied, 3/3 phases complete, 4/4 integration/flows complete (`milestones/v1.57-MILESTONE-AUDIT.md`). Tech debt: ACCESS-03 procedural-read-only residual (credential can write at RBAC); reconcile `/opt/wanctl` on cake-shaper via full `deploy.sh` before any mutating canary (one file ahead from the behavior-preserving D-07 fix).

**Known deferred items at close:** pre-existing todos/seeds carried forward per v1.56 close; `SEED-008` planted for v1.58 (active route-management canary). Zero UAT/verification/context-question blockers.

---

## v1.56 Route Management Surface Deployment (Shipped: 2026-06-20)

**Phases completed:** 3 phases, 4 plans, 4 tasks

**Key accomplishments:**

- Proved the live `cake-shaper` steering deployment shape before mutation: flat `/opt/wanctl`, system Python service, localhost steering health, and separate bridge health endpoints.
- Created rollback anchors and deployed route-management-capable steering code/config in dry-run mode under explicit approval, without changing RouterOS routes, Netwatch, CAKE/qdisc, thresholds, or route ownership.
- Exposed route-management operator health on `127.0.0.1:9102/health` with owner/mode/guard/last-action/rollback fields while keeping bridge/state health separate.
- Ran a bounded 636s dry-run observation from `cake-shaper`; final packet correctly returned `Verdict: not-ready` because supported RouterOS ownership inspection was not proven.
- Preserved SAFE-20 end-to-end: Netwatch remains owner and no active canary was requested or granted.

**Audit:** `passed` — 13/13 REQs satisfied, 3/3 phases complete, 4/4 integration/flows complete (`milestones/v1.56-MILESTONE-AUDIT.md`). Advisory debt: repair/prove supported read-only RouterOS ownership inspection before any future active route-management canary.

**Known deferred items at close:** 11 open pre-existing artifacts acknowledged and carried forward (1 debug-index item, 5 listed todos plus audit remainder, 5 seeds). Zero UAT/verification/context-question blockers.

---

## v1.55 Route Ownership / Netwatch Retirement (Shipped: 2026-06-20)

**Phases completed:** 4 phases, 8 plans, 0 tasks

**Key accomplishments:**

- Documented WAN route ownership policy: Netwatch remains interim owner until wanctl route ownership is proven, canaried, and explicitly accepted.
- Captured read-only RouterOS Netwatch/script/default-route inventory plus Snapshot-A rollback evidence without live route mutation.
- Added safe/off route-management config, dry-run semantics, validation, RouterOS route API wrappers, idempotence, and fail-closed error handling.
- Added Netwatch ownership guard, multi-signal/hysteretic route decision policy, startup reconciliation, circuit breaker semantics, and health/operator observability in repo code/tests.
- Executed Phase 254 read-only observation and operator gate; declined active canary because deployed cake-shaper steering lacked `route_management` health/config surface.
- Final decision: `keep-netwatch`; SAFE-19 held with no route, Netwatch, production config, systemd, CAKE/qdisc, or default ownership mutation.

**Audit:** `passed` — 28/28 REQs satisfied, 4/4 phases complete, 4/4 integration/flows complete (`milestones/v1.55-MILESTONE-AUDIT.md`). Advisory debt: deploy/expose route-management health/config surface on cake-shaper before any future active canary.

**Known deferred items at close:** 11 open pre-existing artifacts acknowledged and carried forward (1 debug-index item, 5 listed todos plus audit remainder, 5 seeds). Zero UAT/verification/context-question blockers.

---

## v1.54 fping Profiling + Storage Hygiene (Shipped-with-deferral: 2026-06-19)

**Phases completed:** 8 phases, 11 plans, 0 tasks

**Key accomplishments:**

- fping shadow/profiling work produced a post-v1.53 path forward without flipping production defaults blindly.
- Operator-gated native Spectrum fping canary was run and rolled back safely; the canary exposed real native fping cadence/startup issues instead of producing a keep verdict.
- Native fping mechanical blockers were fixed and verified: cadence-aware cached-sample staleness, native Spectrum CAKE parity against the external cake-autorate envelope, and startup first-sample readiness.
- Autorate flat-gauge storage hygiene was audited live and closed as a no-op because current stable windows had no >=2Hz flat-gauge candidates.
- CAKE tin skip-on-unchanged was deliberately deferred: `wanctl-history --tins` is raw-history and dropped/ECN are counter-shaped, so sparse emission needs a v1.55 consumer redesign or explicit semantic acceptance.
- SAFE-18 was preserved honestly: the original no-controller-diff invariant held through Phase 248.1, was superseded only for the operator-directed fping freshness repair, and storage hygiene introduced no unrelated controller behavior drift.

**Known deferred items at close:** 11 open artifacts acknowledged and carried forward (1 debug-index item, 5 listed todos plus audit remainder, 5 seeds). Zero UAT/verification gaps. TIN-02/TIN-03 intentionally deferred to v1.55.

---

## v1.53 Pluggable RTT Measurement Backend (Shipped: 2026-06-19)

**Phases completed:** 9 phases, 32 plans, 78 tasks

**Key accomplishments:**

- Lightweight SAFE-17 controller-path git-diff assertion vs v1.52 with constrained evidence output and committed passing JSON proof
- Read-only fping egress proof captured a real non-pass topology result: both WAN route queries resolved on `dev ens18`, not the repo-derived `spec-modem` / `att-modem` uplinks
- Operator-ratified Selection A for live steering RTT A/B, with provenance evidence preserved and SAFE-17 re-asserted after all Phase 238 artifacts landed
- Corrected the egress-proof criterion to the live host-route topology, re-ran the read-only proof (both WANs PASS), and refreshed SAFE-17 — closing the only open Phase 238 item.
- RttBackend Protocol and RttSample value seam with pure IRTT mapping, acyclic imports, and byte-preserving RTTSnapshot coercion
- RTTMeasurement now structurally implements RttBackend via an import-safe probe() wrapper with zero-success None semantics and hot-path regression proof
- Fail-closed SAFE-17 verifier with path allowlist, AST protected-body identity, complete allowed-diff-shape proof, and passed boundary evidence
- Inert `measurement.backend: icmplib|fping` validation for both autorate and steering, with malformed-shape errors and real-config delta proof.
- Fail-closed Phase 240 SAFE-17 verifier with union allowlist plus a second Phase-239-close RTT-seam no-drift gate.
- Offline fping RTT backend with source-bound multi-reflector bursts, loss-safe parser, observed-host scorer feed, and cloned cadence thread.
- Phase 241 SAFE-17 verifier with scorer-byte-identity guard plus additive fping config knob validation and unknown-key registry coverage.
- Real fping 5.1 captures from cake-shaper now bind the offline parser/scorer tests through metadata-backed CompletedProcess fixtures.
- SAFE-17 boundary evidence proves Phase 241 controller-path drift stayed inside the approved fping/validator surface with protected bodies byte-identical.
- RED factory contracts and fail-closed SAFE-17 boundary tooling for the Phase 242 backend factory.
- RTT backend factory with loud per-WAN fping fallback, resolved fping cadence, and icmplib controller helper compatibility.
- Factory-wired autorate and steering RTT construction with per-WAN backend fallback attribution in `/health`.
- Passing SAFE-17 boundary evidence plus live-fping functional proof for the backend factory rollout.
- Fping background RTT samples keep backend attribution and no longer feed ReflectorScorer, with SAFE-17 evidence refreshed for the exact guarded exception.
- BENCH-02 cycle-budget thresholds are frozen before data collection, with git-mechanical provenance and a SAFE-17 empty-controller-diff boundary gate.
- Invocation-scoped cycle-budget rollup plus systemd hygiene NDJSON sampler for BENCH-01 evidence collection.
- Frozen BENCH-02 verdict evaluator with hard icmplib representativeness aborts and full fail-mode test coverage.
- Isolation-gated 8-arm production benchmark harness with committed evidence and an input_error BENCH verdict that blocks treating Phase 243 as passed.
- Amended the benchmark gate semantics with a new provenance-bearing threshold blob so it measures fping regression instead of rejecting Spectrum link jitter, then re-ran the evaluator over existing fixed evidence to produce an `outcome: pass` amended verdict — with no controller-path changes and no new production run.
- Phase 244 SAFE-17 verifier plus ordered health-payload attribution contract targets for autorate, steering, and bridge health surfaces.
- Autorate /health measurement now appends producer/backend/source_ip attribution while preserving the existing measurement contract order.
- Steering /health rtt_source now exposes a seam-gated attribution triple that stays null for all pre-245 autorate/history RTT sources.
- Both cake-autorate state bridges now emit honest producer/backend/source_ip attribution on healthy and degraded /health measurement paths.
- Phase 245 rollback/A-B integrity gates: SAFE-17 boundary proof, frozen AB-03 thresholds, and git provenance tooling committed before live data.
- Steering now consumes its wanctl RttBackend seam first, exposes wanctl-backend attribution in /health, and preserves the full autorate fallback chain on None or exceptions.
- Phase 245 now has the offline tooling to run an interleaved Spectrum backend A/B, compute the AB-03 verdict, and perform a confirm-gated config-only rollback to icmplib.
- Phase 245 live production A/B completed on `cake-shaper`; the frozen-threshold verdict is `rollback_trigger` with recommendation `keep-icmplib`. Production was returned to the Snapshot-A config state: Spectrum backend `icmplib`, Phase-245 code deployed.
- Phase 246 completed the v1.53 default-flip decision by choosing the no-flip branch: `stay-on-icmplib`. No production deploy, restart, RouterOS mutation, or default flip was performed.

---

## v1.52 Silicom Bypass Operationalization (Shipped: 2026-06-14)

**Phases completed:** 3 phases, 11 plans

**Key accomplishments:**

- `silicom-bypass` guarded operator CLI shipped for live card state, idempotent pair state changes, journal marks, destructive-op confirmation, and dual-WAN non-NIC protection.
- `silicom-bypass-init.service` applies and read-back-asserts the known-good boot baseline while preserving module/device setup ownership in `bpctl-silicom.service`.
- Watchdog fail-open units were reconciled to external cake-autorate mode for both WAN pairs, with per-pair opt-in `arm`/`disarm`, sentinel-clean stop discipline, and live ATT variant retirement evidence.
- `silicom-test` HIL harness shipped `failover`, `ab-cake`, and named `chaos` scenarios with always-on NIC restore traps, structured ignored result capture, pair allowlist safety, and PATH-resolved live CLI gates.
- `deploy.sh --silicom-bypass-only` now owns all bypass tooling artifacts through one install-only/off-by-default deploy path.
- SAFE-16 held at every phase boundary and milestone close: zero protected controller-path / `configs/att.yaml` drift against `v1.51`.

**Stats:** 108 matching milestone commits; 77 files changed since `v1.51`; ~30,852 Python LOC in `src/wanctl`; scripts/tests/docs/units/planning only for milestone implementation surface.

**Audit:** `tech_debt` — 15/15 REQs satisfied, 5/5 integration seams wired, 5/5 E2E flows complete (`milestones/v1.52-MILESTONE-AUDIT.md`). Advisory debt: normal deploy `eval rsync`, legacy raw watchdog docs, and partial 235/237 Nyquist metadata.

**Known deferred items at close:** 11 (see STATE.md Deferred Items) — 1 debug-index item, 5 listed todos plus 1 audit remainder, 5 dormant seeds. Zero requirement/integration/flow blockers.

---

## v1.51 Post-Migration Consolidation (Shipped: 2026-06-12)

**Phases completed:** 3 phases, 10 plans, 24 tasks

**Key accomplishments:**

- Git-anchored cleanup denylist guard with per-file policy semantics and default-suite fail-closed pytest coverage.
- Fail-fast rollback confirm script with external-writer fail-closed verification, proven entirely through a PATH-injected SSH shim.
- Digest permission tolerance closed by Phase 208 evidence validation, plus committed SAFE-15 JSON proving phase-232 controller-path zero-diff versus v1.50.
- Cleanup boundary guard now fails closed on git-index removal and protected directory replacement bypasses.
- Manifest-approved removal of superseded ignored cake-autorate trial scripts and outputs with protected FUTURE/findings docs preserved.
- Native `wanctl@` operational examples now carry external cake-autorate mode context where current procedures needed it, with every remaining native-unit hit classified as covered, native-mode, historical, or by-design.
- Spectrum cake-autorate state bridge now pins its identity, interface, path, metrics, and approved baseline RTT env explicitly while preserving current script-default behavior.
- Phase 233 closed its controller-path and cleanup-boundary gates with committed JSON evidence; full-suite green was explicitly operator-waived for known historical Phase 220/221 boundary-test noise.
- Quick-archive slugs indexed in place and stale silicom pending todos closed with SEED-006 pointers, with hash proof that canonical dormant records stayed unchanged.
- Operator-approved Phase 230 Nyquist waiver plus SAFE-15 boundary/close zero-diff evidence using existing read-only proof scripts.

**Stats:** 73 commits over 3 days (2026-06-10 → 06-12); 74 files (+9,216/−283), scripts/tests/docs/planning only — zero `src/wanctl/` mutation (SAFE-15, 9th consecutive). UAT 5/5 passed; 234-VERIFICATION re-verified 11/11 at close (SAFE-15 close evidence regenerated at HEAD `aa200dd3`).

**Known deferred items at close:** 12 (see STATE.md Deferred Items) — 1 debug-index false positive, 6 event-gated/operational todos, 5 dormant seeds. Zero new v1.51 debt; open set shrank from 23 to 12 (META-01/02/03 + FIX-01/02 retired 11 items).

---

## v1.50 cake-autorate Migration Hardening (Shipped: 2026-06-10)

**Phases completed:** 3 phases, 8 plans, 19 tasks

**Key accomplishments:**

- ATT cake-autorate deploy path with full artifact list, silicom watchdog unit handling, and WAN-gated dry-run/dispatch support.
- ATT cake-autorate artifact-contract tests plus a deploy.sh drift gate covering all six repo-owned ATT artifacts.
- Read-only ATT artifact sha256 audit proving live cake-shaper bytes match repo plus SAFE-14 controller-path zero-diff at phase boundary.
- soak-monitor now routes ATT external-controller error scans through the live cake-autorate ATT units, with fake-ssh regression coverage for aggregate JSON output.
- Read-only ATT live-unit evidence plus local representative-error proof show soak-monitor now sees ATT external-mode failures, while SAFE-14 controller-path zero-diff remains clean.
- Read-only both-WAN migration-held evaluator with operator-approved SOAK-01 PASS evidence for the 2026-06-08 cake-autorate migration.
- Native `wanctl@{wan}` rollback is proven by a double-gated script, live read-only both-WAN preflight evidence, documented rollback/return-to-cake renders, and Kevin's no-mutation acceptance.
- Two-mode deployment docs now distinguish native `wanctl@` control from external cake-autorate control, and SAFE-14 is proven for both the Phase 231 boundary and v1.50 milestone close.

**Stats:** 59 commits over 2 days (2026-06-09 → 2026-06-10); 62 files changed (+8,956/−69) total; code surface 14 files (+1,874/−38) — `scripts/deploy.sh`, `scripts/soak-monitor.sh`, `scripts/phase231-*.sh`, tests, docs. Zero controller-path mutation (SAFE-14, base `87980bdf`).

**Audit:** `passed` — 10/10 REQs satisfied, 10/10 integration seams wired, 3/3 E2E flows complete (`milestones/v1.50-MILESTONE-AUDIT.md`).

**Known deferred items at close:** 23 (see STATE.md Deferred Items) — all pre-existing carry-forward from v1.47/v1.48/v1.49 closes; zero new v1.50 debt. Residuals noted: Phase 230 Nyquist PARTIAL (optional `/gsd:validate-phase 230`), `phase231-rollback.sh` confirm-path fix before any future live rollback exercise.

---

## v1.49 Spectrum DSCP Tinning Re-evaluation (Closed: 2026-06-09, overtaken-by-events)

**Phases completed:** 3 of 4 (Phases 225–227, 14 plans); Phase 228 (verdict + rollback + closeout) NOT executed

**Delivered:** Read-only DSCP survival trace (QUALIFIED verdict, operator override to proceed), Snapshot A rollback anchor, pre-registered GATE-01 thresholds, baseline `besteffort wash` evidence, and matched candidate `diffserv4 wash` evidence including the AB-04 realtime-protection arm. SAFE-13 controller-path zero-diff held at every executed phase boundary.

**Why closed without Phase 228:** Between 2026-06-05 and 2026-06-08 the operator migrated both WANs (Spectrum + ATT) from wanctl@ controllers to upstream cake-autorate (`fc47a0c`), moving Spectrum CAKE from bridge-root to member-NIC placement. The topology Phase 228's verdict and Snapshot-A rollback gate no longer exists in production. See `.planning/cake-autorate-trials/WANCTL_CAKE_AUTORATE_FUTURE.md` and `SPECTRUM_CAKE_FINDINGS.md`.

**Evidence direction recorded faithfully (verdict never formally computed):** The Phase 227 matched A/B pointed to REJECT `diffserv4 wash` in the old wanctl-bridge topology — D-01 RRUL p99 345.1 → 384.9 ms (+11.5%, past the locked >+5% reject gate) and marked-EF UDP loss 0.15% → 6.84% (~44×). This does NOT transfer to the new member-NIC cake-autorate topology, where wash-vs-nowash was independently re-tested and `diffserv4 wash` won on tail latency.

**Known gaps:** GATE-02 (verdict computation) and GATE-03 (rollback + closeout recording) close unmet-overtaken, not failed. The SAFE-13 lift question is moot — the native controller path is no longer the live Spectrum/ATT rate controller (it remains the rollback path and the MikroTik controller).

**Known deferred items at close:** 23 (pre-existing carry-forward, unchanged since v1.47 close — see STATE.md Deferred Items)

**Key accomplishments:**

- QUALIFIED DSCP survival verdict with read-only end-to-end trace, pre-wash histogram capture, and direction-split EF probe evidence
- Snapshot A rollback anchor with dry-run restore proof and byte-identical config hash verification
- Pre-registered GATE-01 threshold JSON (RRUL p99, restart-rate, transition-rate, UL stability, tin separation) locked before candidate deploy
- Matched baseline-vs-candidate evidence sets including real CAKE per-tin parsing and the AB-04 marked-EF realtime-protection arm
- SAFE-13 controller-path zero-diff proof at every executed phase boundary; ATT byte-identical through Phases 225–227
- Fail-closed GATE-01 evidence-completeness checker delivered for the (ultimately unexecuted) Phase 228 verdict

---

## v1.48 Steering Runtime Drift Closure (Shipped: 2026-06-03)

**Phases completed:** 3 phases, 12 plans, 31 tasks

**Delivered:** Aligned the live steering daemon `1.39 → 1.47` in production via sliced audit → offline proof → production canary. Canary verdict `kept_aligned`; SAFE-12 controller-path zero-diff held at every phase boundary and milestone close. 11/11 REQs (DRIFT/PROOF/CANARY/SAFE-12). Git range `103c776 → a9a23c5`.

**Key accomplishments:**

- Pinned git-history audit proving the v1.39-to-v1.47 steering surface delta is one behavior-changing hardening commit, with reproducible JSON and operator-readable reports.
- Steering drift contract audit proving the sole behavior-changing v1.39-to-v1.47 commit preserves the spine and is safe to absorb without mitigation.
- Fail-closed SAFE-12 controller-path boundary evidence proving zero committed drift and clean staged/unstaged/untracked state against the v1.47 close baseline.
- Offline SteeringDaemon replay harness with fake RouterOS/CAKE/baseline seams and deterministic PROOF-01 evidence artifacts.
- Clean-restart replay proof reproducing persisted DEGRADED + pre-enabled steering as an effective-steering bug, with evidence and folded-todo closure annotation.
- Per-fixture steering-spine verdict evidence plus Phase 222-compatible SAFE-12 controller-path zero-diff proof for the Phase 224 pre-canary gate.
- Replay harness regeneration now includes clean-restart evidence, daemon-side spectrum write semantics, explicit Phase 224 risk acceptance, and SAFE-12 steering-boundary proof.
- Snapshot A and targeted rollback wrappers now provide a reversible steering canary anchor, with staging budget evidence explicitly pending until real raw artifacts are available.
- Read-only steering spine probe plus restart-window-aware gate evaluator now produce canary verdicts from raw `/health` and live spine evidence.
- Production deploy of the aligned steering daemon under a Snapshot A rollback anchor; canary `kept_aligned` with all three spine invariants proven (binary on/off, only-new-connections, daemon-source fingerprint) including an operator-authorized router rule-read of mangle rule `*313`; bounded rollback armed but not fired.

**Known deferred items at close:** 23 — all pre-existing carry-forward, zero new v1.48 debt (see STATE.md Deferred Items). Acknowledged via `/gsd-complete-milestone` Acknowledge-&-close path 2026-06-03.

**Known residual:** rollback wall-clock unproven (no staging host; honestly waived per `rehearsal-budget.md` `operator_override: unmeasured-waived`).

---

## v1.47 Measurement Evidence Closure (Shipped: 2026-06-02)

**Delivered:** Bounded read-only evidence milestone. Scope D (ingestion-rate observability) shipped first per Pitfall 11 to support Phase 218 audit evidence regardless of v1.47 timing. Scope A (`tcp_12down` target/path sensitivity hypothesis) ran an 18-cell target × path × window matrix with pre-registered CRITERIA thresholds locked at Phase 220 plan time. The Phase 221 closeout published `carried_narrower_with_close_with_prejudice_rule` as the authoritative post-D-10-BGP-overlay verdict — raw aggregator returned `defect_located` on three supplemental Vultr cells, but the D-10 BGP overlay excluded those cells because BGP path drift contaminated them mid-run. Folded `2026-04-08-investigate-tcp-12down` todo closed with the CRITERIA-02 close-with-prejudice rule attached verbatim; no v1.48+ reopen permitted without independent new production evidence.

**Phases completed:** 3 phases (219, 220, 221), 12 plans, 40 tasks
**Phase 218 carried in parallel:** event-gated v1.45 VERIFY watch-list remains open (no synthetic event generation); INGEST-01..05 ingestion-rate tool now available as Phase 218 audit fallback enhancement vs the v1.44 Phase 208 CLI.

**Final verdict on tcp_12down hypothesis:** `carried_narrower_with_close_with_prejudice_rule` (post-D-10 BGP overlay, authoritative). Raw aggregator: `defect_located`. Three BGP-contaminated cells (vultr-chicago/prime-time, vultr-dallas/daytime, vultr-dallas/prime-time on Spectrum) excluded by D-10 rule. CRITERIA-02 rule applied — close-with-prejudice locked in.

**Key accomplishments:**

1. **Phase 219 — Ingestion-Rate Observability (Scope D, D-first per Pitfall 11):** Additive `wanctl-history --ingestion-rate --by-table` and `--rolling=60,300,3600` flags with `schema_version: 1` envelope and per-snapshot staleness fields; `wanctl-operator-summary --digest` emits compact per-WAN ingestion-rate lines from the bucketed helper while preserving hard-red digest accounting and failure isolation; cron-callable `scripts/phase219_ingestion_digest.py` with atomic-write snapshot persistence + count-based retention. D-27 production cycle-budget evidence: `avg_ms=2.857`, `p99_ms=6.4` over 73,603 samples — out-of-band cron path stays within the 50ms control cycle budget.
2. **Phase 220 — Matrix Runner (Scope A1):** Pre-registered 18-cell `scripts/phase220-matrix.yaml` with locked CRITERIA-01 thresholds, ATT egress signature, and `base_sha` source-floor anchor; stdlib + PyYAML cube aggregator with Mann-Whitney U (two-sided, normal approximation) + bootstrap 95% percentile CI (B=2000, seeded `random.Random`); per-cell wrapper composing Phase 213 capture and Phase 214 analyzer chain unchanged with hard-failing source-drift and ATT egress validation. Wet daytime dallas/Spectrum rehearsal reproduced the Phase 214 canonical anchor (`ambiguous`/`reflector_loss`/`✓ MATCH`).
3. **Phase 221 — Matrix Evidence + Closeout (Scope A2):** 54/54 deduplicated valid replicates across 18 cells captured across multiple operator-driven days; Phase 221 SAFE-11 boundary guard plus 18-cell evidence ledger seeded with Phase 220 rehearsal replicate; closeout JSON + 11-section human-readable report with pre-/post-D-10-BGP-overlay verdict trace; folded `tcp_12down` todo closed with CRITERIA-02 close-with-prejudice rule attached verbatim and bidirectionally cited from `221-CLOSEOUT.md`.
4. **SAFE-11 invariant held end-to-end:** Zero controller-path source diff (`wan_controller.py`, `queue_controller.py`, `cake_signal.py`, backends, `alert_engine.py`, fusion) across all three phases. Expanded allowlist (`configs/`, `deploy/systemd/`, `scripts/`, `tests/fixtures/phase22*/`, `docs/`, additive `src/wanctl/history.py` for Scope D) honored at every phase boundary via mutation-boundary pytest. Stdlib-only mandate (no SciPy/NumPy/pandas) carried forward from Phase 214 D-10.
5. **Read-only milestone closed cleanly:** No controller threshold/algorithm/CAKE/steering changes triggered by matrix results. Tuning explicitly deferred to v1.48+ after evidence isolates a cause.

**Stats:**

- 107 commits (`8c50309..613bec1`)
- 522 files changed (+26,702 / -447 — mostly evidence fixtures + per-replicate matrix sidecars)
- Source surface: 15 files changed (+3,361 / -28 across `src/`, `scripts/`, `tests/`, `docs/`)
- 12 plans across 3 phases
- Timeline: 2026-05-29 → 2026-06-02 (~5 days, plus multi-day operator-driven matrix execution window)
- Git range: `chore: archive v1.46 milestone files` → `docs(phase-221): mark roadmap checklist complete`

**Known deferred items at close:** 23 (carry-forward from v1.46 close 2026-05-30, no new v1.47 debt — see STATE.md "Deferred Items"). Categories: 1 debug-session index, 12 quick_task metadata-noise slugs, 5 todos (4 carry-forward + Phase 218 watch primary), 5 dormant seeds.

**What's next:** v1.48 — TBD. Phase 218 stays open until a natural production DOCSIS flapping event produces a qualifying `peak_transition_count > 30` row. Folded `tcp_12down` todo CLOSED with close-with-prejudice (no v1.48+ reopen without independent new evidence). Candidate v1.48 scope inputs: steering runtime/source version-drift alignment (STEER-DRIFT-01, Phase 212 carry), Spectrum upload reclaim re-attempt with revised probe shape (RECLAIM-04), dormant SEEDs 005/006/007.

---

## v1.46 Internet Quality Recovery (Shipped: 2026-05-30 — VERIFY-01/02 DEFERRED)

**Delivered:** Evidence-first quality recovery across Spectrum, ATT, and steering. Production drift inventoried; experience baseline harness shipped; measurement-collapse classifier returned `ambiguous`/`reflector_loss` (severe loaded p99 NOT reproduced in official window); upload-reclaim canary tried ceiling 18→20, bounded VOID exhausted, Spectrum rolled back to 18; Phase 196 refractory thread closed as no-change/resolved-by-197; production cycle-budget profiled at 71,560 timing samples, profiling baseline todo closed as no-action. v1.45 VERIFY-01/02 carried forward to Phase 218 as event-gated watch-list.

**Phases completed:** 6 of 7 (Phase 218 deferred — event-gated on natural DOCSIS flapping event)
**Plans:** 21 / 21 plannable
**Tasks:** 42

**Key accomplishments:**

1. **Phase 212 — Production drift audit:** Read-only Spectrum/ATT/steering inventory with D-08 secret-safe redaction; steering runtime `1.39` vs source `1.45` surfaced as known unaligned drift.
2. **Phase 213 — Experience baseline harness:** Single-command per-WAN baseline harness with co-sampled health/CAKE/SQLite/steering capture and offline six-bucket signal classification.
3. **Phase 214 — Measurement collapse investigation:** Fail-closed flent ping percentile extractor + per-second alignment + six-driver classifier; canonical Spectrum matrix verdict `ambiguous`/`reflector_loss`/`signal none`.
4. **Phase 215 — Spectrum upload reclaim canary:** One-knob ceiling 18→20 canary with Snapshot A rollback anchor; bounded VOID exhausted on three attempts; Spectrum safely rolled back to ceiling 18.
5. **Phase 216 — Recovery/refractory decision:** Closed Phase 196 queue-primary refractory semantics thread as no-change / resolved-by-197 with evidence-cited rationale.
6. **Phase 217 — Cycle-budget baseline:** Operator-gated Spectrum profiling captured 71,560 JSON Cycle records with router-write coverage; production safely reverted; profiling baseline todo closed as no-action.

**Stats:**

- 156 commits (bab4a59..d27fa81)
- 76 source/test/script/deploy files changed (+8,101 LOC, additive)
- 21 plans across 6 phases (Phase 218 deferred)
- Timeline: 2026-05-27 → 2026-05-30 (~3 days)
- Git range: `docs(212): capture phase context` → `docs(phase-217): evolve PROJECT after completion`

**Known deferred items at close:** 2 (VERIFY-01, VERIFY-02 — both carried to Phase 218 as event-gated watch-list; see STATE.md "Deferred Items (carried from v1.46 close)")

**What's next:** v1.47 — TBD. Phase 218 stays open until a natural production DOCSIS flapping event produces a qualifying `peak_transition_count > 30` row. Candidate v1.47 scope inputs: `tcp_12down` target/path sensitivity (Phase 214 follow-up), steering version-drift alignment (Phase 212 carry), Spectrum upload reclaim re-attempt with revised gate, ingestion-rate observability tool.

---

## v1.44 Topology-Correct CAKE — Spectrum besteffort wash migration (Shipped: 2026-05-26)

**Phases completed:** 5 phases, 27 plans, 68 tasks

**Key accomplishments:**

- Operator-approved 5-file SAFE-09 TOPO-02 scope with ROADMAP, validation, and review artifacts aligned before any source mutation.
- Tin-agnostic CAKE signal and allow_wash behavior gates are now authored before production source changes.
- CAKE signal aggregation now handles single-tin besteffort without changing diffserv4 active/total aggregation behavior.
- `allow_wash` now gates `wash` emission end-to-end while preserving default D-08 protection and deferring readback validation to Phase 209.
- Deterministic Phase 206 A/B replay harness with scrubbed golden NDJSON, per-sample CAKE snapshot consumption, schema-v1 JSON output, and optional real flent RRUL parsing.
- TOPO-05 rollback gate with JSON-sourced thresholds, wrapper-owned restart-counter SSH sampling, fail-closed post-soak mode, and full shell-integration coverage.
- Operator-facing rollback gates with JSON-sourced thresholds plus audit-grade provenance for the 2026-04-29 golden fixture substitution.
- Phase 206 is closed with four-surface SAFE-09 source-boundary proof, threshold doc/JSON drift evidence, full-suite test evidence, and a live SHA256 fixture pin.
- Phase 206 rollback gate now aborts on malformed soak evidence and inconsistent restart counters instead of silently passing full-enforcement post-soak mode.
- Predeploy gate shell parser now turns missing or option-like values for all value-consuming flags into structured rc=2 ABORTs before threshold logic runs.
- Phase 206 predeploy gate now aborts on RRUL metric-source mismatches before numeric comparison, preventing misleading ms-vs-Mbps BLOCK output.
- Phase 206 verification is now `status: verified` after rerunning the four fail-closed gap checks, SAFE-09 boundary checks, full suite, hot-path slice, and Phase 206 focused tests.
- Phase 206 rollback gate now fails closed for malformed restart counters, invalid post-soak timing, and hidden local override state while preserving SAFE-09 control-path boundaries.
- SAFE-07 source-diff verifier now rejects unstaged, staged, and untracked `src/wanctl/` edits before evaluating committed diffs.
- Soak capture now survives bounded curl/HTTP/jq row failures with sidecar TSV diagnostics while preserving the NDJSON consumer schema.
- The v1.43 `secondary_gate_legacy` transition block is removed end-to-end; v1.44 soak summaries now emit only the completed-window watchdog secondary signal.
- CALIB-02 threshold YAML promotion routed to NO in the v1.44 CHANGELOG, preserving the fail-closed JSON threshold artifact and deferring schema design to T17(b)/SEED-005.
- P207_BASE-anchored SAFE-09 closeout report proving zero `src/wanctl/` phase diff across committed, staged, unstaged, and untracked surfaces at gate-time and report-write-time.
- Completed-window watchdog aggregation now fails closed on misconfigured gate columns/statistics while preserving the v1.44 10-key schema contract.
- Per-WAN `wanctl-history --ingestion-rate` reporting with count_metrics-backed rows/sec, --wan-aware iteration filtering, and stable window/totals JSON.
- `wanctl-operator-summary --digest` now tolerates per-WAN DB open failures and stdout-write failures without masking schema/query corruption.
- `wanctl-history --ingestion-rate --db metrics.db --wan spectrum` now retains the explicit DB path and reports SQL-filtered Spectrum row counts without changing per-WAN DB filtering.
- Controller-internal CAKE wash readback validation with symmetric ATT/Spectrum assertions and pyroute2-correct diffserv enums.
- Single-entry SAFE verifier now covers ATT config byte-identity and v1.44 source allowlist contracts, with Phase 206 restart-window non-finite inputs closed fail-closed.
- Standalone bridge QoS operator guide for per-WAN `allow_wash`, with focused configuration guidance and compact v1.44 Phase 209 release notes.
- Spectrum now runs the v1.44.0 `920Mbit besteffort wash` migration with 24h production soak evidence, Phase 206 rollback gates clear, and SAFE-08/SAFE-09 mechanical closeout passing against `6508d68`.

---

## v1.43 UL Suppression Metrics & Gate Calibration (Shipped: 2026-05-13)

**Phases completed:** 3 phases (202, 203, 204), 17/17 plans (4 + 3 + 10; Plan 204-05 superseded by gap-closure 204-09 Branch A)

**Key accomplishments:**

- Shipped additive `/health.wans[].upload` completed-window UL suppression counters with per-cause classification (`dwell_hold` / `backlog_recovery` / `other`); `suppressions_per_min` preserved untouched for backward compat. METRIC-03 replay against v1.42 reference soak `20260505T132736Z` confirmed counts match codex re-aggregation (peak mean ~13.9/min, p95=41, max=124).
- Shipped per-sample `load_rtt_delta_us` in soak NDJSON + zone × cause-tag histogram aggregation in `soak-summary.json` with stdlib-only aggregator, deterministic golden fixtures, and re-runnable SAFE-07 source-diff gate.
- Closed the D-14 secondary watchdog inherited from v1.42 Phase 201 (`6.466842.../60s mean` FAIL) via soak-grounded completed-window p99 dwell-hold gate at threshold `175`; dual-emission watchdog (`secondary_gate_legacy` + `secondary_gate_completed_window`) loaded from `scripts/calib_02_threshold.json`; verification soak `20260512T004208Z` dual gate PASS (`primary_gate.delta=0`, completed-window p99 dwell_hold `135.62 ≤ 175`).
- Boundary-marker remediation cycle (Plans 204-07..10) post-`d44e2fd` re-derived CALIB-01 distribution under corrected aggregator and re-validated CALIB-04 via Branch A continuation after Branch B `FAIL-A` at `secondary_value=151.0` vs threshold 150; final threshold 175 operator-approved.
- SAFE-07 closeout invariant held end-to-end: zero control-path source diff between Phase 201 close (`b72b463`) and v1.43 close at every phase boundary, verified by `scripts/check-safe07-source-diff.sh`. Only planned `src/wanctl/__init__.py` version bump permitted.
- Version bumps `1.42.1` → `1.43.0` propagated across `pyproject.toml`, `src/wanctl/__init__.py`, `docker/Dockerfile`; CHANGELOG and `docs/CONFIGURATION.md` document additive `/health` fields, soak NDJSON / summary schema, and live-counter vs completed-window framing.
- Two production deploys on cake-shaper via Plan 201-15 two-snapshot rollback ritual: Deploy 1 (`v1.43.0` binary + METRIC-01/OBSV-05) before CALIB-01 baseline soak, Deploy 2 (recalibrated threshold harness-only) before CALIB-04 verification soak.

**Closure verdict:** `passed`. Audit 2026-05-13 (re-audit, supersedes 2026-05-06) confirmed 15/15 requirements satisfied, 3/3 phases verified, 14/14 integration wired, 1/1 E2E flow complete. RETRO Key Lesson #1 captures threshold-basis hygiene as durable lesson.

**Known deferred items at close:** WR-01 / WR-02 (soak-harness hardening), `secondary_gate_legacy` block removal, CALIB-02 YAML-promotion evaluation, SEED-005 conservative UL tuning sweep — all routed to v1.44. Phase 202 VALIDATION.md `nyquist_compliant: false` (reconstructed retroactively; test coverage in place); optional `/gsd-validate-phase 202` backfill.

---

## v1.42 DOCSIS-Aware UL Congestion Control (Shipped: 2026-05-06)

**Phases completed:** 1 phase (201), 16/16 active plans (Plan 201-12 superseded by 201-16; 17 PLAN.md files materialized total)

**Key accomplishments:**

- Shipped DOCSIS-aware UL control mode: YAML setpoint clamp (`continuous_monitoring.upload.docsis_mode: true`, `setpoint_mbps: 12`), windowed RTT-integral classifier, and CAKE backlog secondary corroborator landed in `queue_controller.py` with bounded absolute RED decay and integral anti-windup (Plans 201-04, 201-13, 201-14).
- Closed v1.41-inherited blocking VALN-06 via D-19 primary floor-hit gate: recanary `20260505T122513Z` `verdict=pass`, `primary_gate_value=0`, `ul_floor_hits_during_load=0`; 24h soak `20260505T132736Z` D-19 floor-hit delta `0` on production v1.42.1.
- Five additive `/health.upload.*` runtime-state fields landed: `setpoint_mbps`, `headroom_mbps`, `rtt_integral_ms_s`, `docsis_state`, `docsis_mode_active` — runtime semantics, not config echoes (Phase 200 RETRO lesson absorbed).
- Predeploy gate (`scripts/phase201-predeploy-gate.sh`) reconciles or fails closed against v1.41-rejected-hypothesis YAML keys (`target_bloat_ms`, `warn_bloat_ms`, `consecutive_yellow_decay_clamp`, `factor_down_yellow=1.0`) before any Spectrum deploy proceeds.
- Two cross-AI Codex review checkpoints (pre-implementation BLOCK with amendments; stop-time GO WITH FOLLOW-UPS, no HIGH findings) became required gates per Phase 200 RETRO discipline.
- Version bumps `1.42.0` → `1.42.1` propagated across `pyproject.toml`, `src/wanctl/__init__.py`, `docker/Dockerfile`; CHANGELOG and `docs/CONFIGURATION.md` carry restart-required migration semantics for `docsis_mode`/`setpoint_mbps`/RTT-integral keys.

**Closure verdict:** `gaps_found` (operator Route B 2026-05-06). D-19 primary VALN-06 floor-hit gate PASS shipped on v1.42.1. D-14 secondary suppression watchdog FAILED at `ul_hysteresis_suppression_rate_per_60s_mean=6.466842364880155` (vs `<5.0`); FAIL traced to YELLOW-edge dwell-hold path (`queue_controller.py:348`), unrelated to bounded RED decay path Plan 201-14 fixed (`queue_controller.py:361-376`). Original threshold never soak-calibrated against post-fix control surface — classified `metric_semantics_and_recalibration` and deferred to v1.43+ as four ordered backlog items (`SEED-002`..`SEED-005`). VALN-06 phase-goal control behavior achieved. See `201-RETRO.md`, `201-VERIFICATION.md` `closure_route` block.

---

## v1.41 Per-Direction Control Surfaces (Closed: 2026-05-04, gaps_found)

**Phases completed:** 1 phase (200), 16/16 plans

**Key accomplishments:**

- Per-direction UL RTT bloat threshold schema landed with per-key presence flags (`_upload_target_bloat_ms_explicit`, `_upload_warn_bloat_ms_explicit`) — UL writes gated independently of DL, byte-identical fallback to DL globals when keys absent (ARB-05). Codex pre-review D-11 caught the value-derived bug pre-merge.
- Autorate validator now emits an audible WARNING for any unknown `continuous_monitoring.*` key on startup — closes the v1.40-era silent-ignore gap that masked 4 unrecognized prod keys for 3 days (SAFE-06).
- Migration documentation in `CHANGELOG.md` and `docs/CONFIGURATION.md` makes restart-required semantics explicit (SIGUSR1 reload scope is dwell/deadband only — not these keys) (DOCS-03).
- Three operator evidence-trail notes (`spectrum-*-2026-04-29.md`) anchored the per-direction hypothesis as a falsifiable claim against the live Spectrum UL hysteresis storm at 5 → 15 → 31 suppressions/60s with DL=0.
- Plan 200-14 Attempt 3 canary improved Spectrum loaded-window UL floor hits 122 → 4, narrowing the residual failure regime to shaping-headroom (not threshold) — direct seed for v1.42 Phase 201's DOCSIS-aware design.

**Closure verdict:** `gaps_found` with operator-escalated VALN-06 deferral 2026-05-04. ARB-05/SAFE-06/DOCS-03 satisfied. VALN-06 zero-floor-hit gate not reached under per-direction-thresholds hypothesis; D-10 rollback used `/opt/wanctl-prephase200-gap-20260504T132936Z.tar.gz`; soak watchdog skipped fail-closed; binary held at v1.40 through this milestone. VALN-06 inherited as blocking requirement to v1.42 Phase 201 (closed Route B 2026-05-06).

---

## v1.40 Ordering Rationale — Queue-Primary Signal Arbitration (Shipped: 2026-05-03)

**Phases completed:** 7 phases (193–199), 28 plans, 30 SUMMARYs (Phase 198 had multiple attempts canonicalized at attempt 11)

**Key accomplishments:**

- Replaced RTT-primary DL congestion classification with kernel-local CAKE queue delay (`avg_delay_us - base_delay_us`) as the primary signal under load (ARB-01, MEAS-07), demoting RTT to a confidence-gated secondary scalar `rtt_confidence ∈ [0.0, 1.0]` (ARB-02).
- Tightened the fusion healer bypass gate so single-path flips no longer destabilize the control path; bypass requires sustained queue + RTT distress for 6 consecutive cycles in agreeing direction (ARB-03).
- Established the queue-primary refractory split: `dl_cake_for_detection` masked during 40-cycle refractory (preserving Phase 160 cascade safety) vs `dl_cake_for_arbitration` live during refractory (so primary classifier sees valid CAKE signal). Resolved Phase 196 Spectrum throughput regression root-caused to refractory masking forcing RTT fallback under legitimate queue-primary load.
- Validated Spectrum cake-primary in production: Phase 198 Plan 06 attempt 11 throughput verdict `medians_above_532=3`, MoM 674.156379 Mbps (vs 532 Mbps acceptance threshold) — VALN-04 + VALN-05a closed; canonical `ab-comparison.json` with `comparison_verdict: pass` regenerated against Phase 196 A-leg control evidence.
- Preserved UL byte-identity throughout (ARB-04, SAFE-05): the test pin `tests/test_phase_195_replay.py::test_safe05_threshold_name_counts_are_unchanged` confirms no threshold-name drift in `wan_controller.py` at v1.40 closure.
- Closed the OBS-02 spec/impl/doc drift caveat docs-only in Phase 199: REQUIREMENTS.md, `docs/SUBSYSTEMS.md`, and `docs/RUNBOOK.md` now carry the absent-row semantic verbatim.

**Closure verdict:** `tech_debt` — 9/9 actionable requirements satisfied. VALN-05b (ATT regression canary) deferred-by-design pending v1.39 Phase 191 closure (cross-milestone dependency). Pre-archive cleanup commits `58d2255` (lint + whitespace) and `b4ce583` (mypy) closed v1.40 hygiene debt that escaped Phase 199's docs-only verification.

**Known deferred items at close:** 21 (1 debug session, 11 quick tasks, 1 thread, 5 todos, 1 seed, 2 UAT gaps) — see STATE.md `## Deferred Items`.

**Tech debt acknowledged:** `make ci` coverage 89.64% (0.36% under 90% threshold), 9 vulture dead-code findings at 60% confidence, Nyquist VALIDATION.md gaps in phases 193 (by-design replay-equivalence) and 195 (production UAT substituted).

---

## v1.39 Control-Path Timing & Measurement Accounting (Effectively shipped 2026-04-24 under operator waiver; archived 2026-05-06 gaps_found)

**Phases completed:** 3 phases (191, 191.1 inserted closure, 192), 11 plans

**Key accomplishments:**

- Apply-path overlap instrumentation now visible in `/health.signal_arbitration` and slow-apply enrichment logs; `cake_stats_cadence_sec` YAML knob honored at daemon start (TIME-01/TIME-02 PARTIAL — code shipped; A/B vs v1.38.0 baseline never closed).
- Reflector scorer no longer decrements per-host quality during all-host-blackout cycles (`reflector_scorer.py` blackout gate; MEAS-05).
- Fusion-aware INFO-log cooldown trims `Protocol deprioritization detected` volume during `disabled`/`healer_suspended` (OPER-02 satisfied — soak ±0.3% drift on both WANs).
- Phase 191.1 (inserted) established the phase-local SAFE-03 comparator as the authoritative closure rule for narrow phase scopes (D-05/D-06/D-07).
- Production v1.39.0 deployed 2026-04-24 to cake-shaper from clean `git archive` of HEAD `663d468...`; subsequent v1.40/v1.41/v1.42 milestones built on top of it.

**Closure verdict:** `gaps_found` (strict). 9 of 11 requirements (TIME-01/02/03/04, MEAS-05/06, SAFE-04, VALN-02/03) never closed against the v1.38.0 measurement baseline they referenced — superseded by v1.40 cake-primary arbitration and v1.42 DOCSIS-aware UL evidence before strict closure could be captured. Phase 192 closed under explicit operator waiver (`192-PRECONDITION-WAIVER.md`); Phase 191 VALN-02 ATT RRUL FAIL preserved as contextual debt. See `.planning/milestones/v1.39-MILESTONE-AUDIT.md`.

---

## v1.38 Measurement Resilience Under Load (Shipped: 2026-04-15)

**Phases completed:** 5 phases, 12 plans, 26 tasks

**Key accomplishments:**

- Defined and shipped an explicit measurement-health contract so reflector quorum and stale/current RTT status are machine-readable.
- Fixed the zero-success cached-RTT honesty gap without retuning congestion thresholds or disturbing existing outage fallback behavior.
- Added regression coverage across controller behavior, health payloads, fallback safety, and producer-side RTT status publication.
- Aligned runbook, deployment, and replayable verification evidence with the new measurement-resilience contract.
- Backfilled Phase 186 verification and closed the final traceability drift so all eight v1.38 requirements are now satisfied and archive-ready.

---

## v1.37 Dashboard History Source Clarity (Shipped: 2026-04-14)

**Phases completed:** 3 phases, 8 plans, 23 tasks

**Key accomplishments:**

- Locked the dashboard-facing source contract so endpoint-local HTTP history, merged CLI proof, and degraded-source behavior are explicit and stable.
- Surfaced endpoint-local framing, translated source detail, and an immutable merged-CLI handoff in the History tab without changing backend history semantics.
- Added focused regressions for success, fetch-error, source-missing, mode-missing, and db-paths-missing history states.
- Aligned deployment, runbook, and getting-started docs to the same endpoint-local HTTP versus authoritative merged CLI history rule.
- Closed all five milestone requirements and refreshed the milestone audit to `passed` after validation backfill and integration re-check.

---

## v1.36 Storage Retention And DB Footprint (Shipped: 2026-04-14)

**Phases completed:** 6 phases, 17 plans, 33 tasks

**Key accomplishments:**

- Identified the real production DB topology and explained why the per-WAN footprint stayed multi-GB.
- Tightened per-WAN retention and aligned history-reader/operator docs to the authoritative storage layout without changing controller logic.
- Closed `OPER-04` with a repeatable operator proof path for DB inventory, storage status, and merged CLI history checks.
- Repaired the startup/watchdog regression caused by heavy pre-health storage work during footprint-reduction rollout.
- Finished the ATT-only compaction pass and reduced `metrics-att.db` from about `5.08 GB` to about `202 MB`, closing `STOR-06`.

---

## v1.35 Storage Health & Stabilization (Shipped: 2026-04-13)

**Phases completed:** 5 phases, 16 plans, 23 tasks

**Key accomplishments:**

- Rebounded v1.34 storage fallout by fixing per-WAN metrics storage handling, hardening periodic SQLite maintenance, and repairing the production `analyze_baseline` deploy path.
- Deployed v1.35.0 cleanly through the active service flow and validated Spectrum, ATT, and steering with a passing canary.
- Closed the 24-hour production soak with non-critical storage, healthy operator surfaces, and zero err-level journal entries for the WAN services.
- Backfilled the missing verification and audit evidence so all six v1.35 requirements are now phase-verified and traceable.
- Aligned deploy/install/operator-summary/soak documentation and helper scripts with the actual production flow, including steering-aware evidence coverage.

---

## v1.34 Production Observability and Alerting Hardening (Shipped: 2026-04-12)

**Phases completed:** 5 phases, 9 plans, 2 tasks

**Key accomplishments:**

- Added bounded latency-regression and burst-churn alerts to the existing autorate alert path without touching the control algorithm.
- Validated that the new alert rules stay quiet on the live autorate service and are ready for production use.
- Added bounded storage and runtime pressure visibility to the existing operator surfaces without touching controller thresholds or adding a new persistence path.
- Validated that the new storage and runtime pressure signals are healthy, readable, and low-noise on the live host.
- Added compact operator summary surfaces on top of the existing bounded health contract and locked the shape with focused regression coverage.
- Validated the new compact summary contract on live services and confirmed ATT/Spectrum parity in the operator-facing view.
- Built the post-deploy canary script and covered its classification contract with offline pytest fixtures.
- Validated the canary on live services, fixed a storage-status false positive, and added deploy guidance so operators run the canary after restart.
- Operator-facing threshold runbook for v1.34 alerts, health summaries, canary exit codes, and escalation guidance

---

## v1.33 Detection Threshold Tuning (Shipped: 2026-04-11)

**Phases completed:** 5 phases, 10 plans, 14 milestone requirements

**Key accomplishments:**

- 24-hour idle baseline captured before any tuning, giving the threshold sweep a real production reference instead of anecdotal load behavior
- Five CAKE detection and recovery parameters A/B tested under RRUL, with the winning set deployed together and confirmed in a 24-hour production soak
- Production runtime hardened during the milestone: metrics-history performance, steering health, retention cadence, and shared SQLite maintenance coordination all improved on the live host
- Storage contention observability added to autorate and steering, and the explicit live decision was to keep the shared SQLite topology for now
- Burst-aware clamp behavior plus health/Prometheus observability added, then retuned to bring `tcp_12down` p99 back out of the multi-second range without regressing `rrul_be`

---

## v1.32 CAKE-Aware Congestion Detection (Shipped: 2026-04-10)

**Phases completed:** 3 phases, 5 plans, 9 tasks

**Key accomplishments:**

- 1. [Rule 1 - Bug] MagicMock leaking into JSON serialization
- CAKE-aware zone classification with dwell bypass on elevated drop rate and green_streak suppression on elevated backlog
- Refractory period anti-oscillation with CAKE snapshot wiring through congestion assessment, YAML threshold parsing, and health endpoint detection state
- Exponential rate recovery probing with 1.5x multiplier, 90% ceiling linear fallback, and 9-path multiplier reset via CAKE signal guards

---

## v1.29 Code Health & Cleanup (Shipped: 2026-04-08)

**Phases completed:** 9 phases, 28 plans, 59 tasks

**Key accomplishments:**

- Vulture dead code detection configured with 90+ whitelist entries covering framework, protocol, and test-only false positives; 8 ruff lint errors fixed in tests; make dead-code CI target enforcing ongoing detection
- Removed 10 dead code items across 8 files and deleted 2 orphaned modules with tests, achieving zero vulture findings and zero ruff F401 violations with 4,177 tests passing
- make check-deps target verifying all 8 runtime pip dependencies are imported in src/wanctl/, integrated into make ci
- Bidirectional config key audit: ~50 missing paths added to KNOWN_AUTORATE_PATHS, 6 example files cleaned of dead/deprecated keys, undocumented keys added as commented-out sections
- Corrected stale docstrings (is_ok/is_err, wrong path), synced CONFIG_SCHEMA.md with 5 new/updated sections (storage.retention, owd_asymmetry, fusion.healing, ping_source_ip, deprecated table), and fixed alpha_baseline/alpha_load references in ARCHITECTURE.md and CONFIGURATION.md
- Extracted QueueController, Config, and RouterOS from 5,218-LOC monolith into 3 focused modules, reducing autorate_continuous.py by 1,558 lines
- Extracted WANController (~2,396 LOC) and _apply_tuning_to_controller (~93 LOC) to wan_controller.py, completing the monolith decomposition into 5 modules
- Split 4 CLI tool modules (check_config, check_cake, calibrate, benchmark) into 8 focused modules, extracting validators, fix infrastructure, measurements, and comparison logic
- Split check_config_validators.py (1026 eff LOC) into autorate-only (569 eff LOC) and steering-only (478 eff LOC) validator modules, closing the SC1 gap
- Extracted WANController's 3 largest functions (408+447+102 LOC) into 22 focused private methods with AST verification script
- main() decomposed from 612 to 47 lines via 23 lifecycle helpers; __init__() from 81 to 13 lines; all 32 functions under 50 lines
- Extracted 5 mega-functions (run_cycle 220, main 158, _load_alerting_config 108, __init__ 88, _load_wan_state_config 88 LOC) into 21 focused private helpers, all under 50 lines
- Extracted _get_health_status() in both health handlers into section-builder assembler pattern (347->40 LOC autorate, 212->25 LOC steering)
- Extracted 12 functions (100-167 LOC) across 8 files into ~35 focused helpers, plus proactive medium-function cleanup in target files
- 1. [Rule 3 - Blocking] Fixed _apply_tuning_to_controller C901 violation (not in original plan)
- Deleted 18 stale phase tests, extracted shared helpers, moved 9 steering and 4 backends test files into mirrored subdirectories with dedicated conftest.py files
- Moved 6 storage + 16 tuning test files into mirrored subdirectories and renamed test_dashboard to dashboard, with shared fixture extraction
- TestCLI.test_main_connectivity_error_returns_1
- 4 runtime-checkable Protocol definitions in interfaces.py plus AST boundary check script with 109-violation allowlist and CI integration
- Public facade API on WANController (13 methods/properties) eliminating all 35+ cross-module private accesses from autorate_continuous.py, plus public properties on 4 component classes
- One-liner:
- SteeringDaemon.get_health_data() facade + zero cross-module violations with empty allowlist and enhanced AST boundary checker
- Fix 46 steering test failures from Phase 147 interface promotion, add _make_health_data() test helper, delete ghost duplicate file
- pytest-xdist parallel execution with 2s timeout, CI brittleness gate, and 7 MagicMock test failures fixed via typed return values
- Eliminated 21 real time.sleep() calls from tests via mocked time, tightened brittleness to 0, verified xdist isolation with randomized ordering -- 74.5% speed improvement vs baseline
- 1. [Rule 3 - Blocking] TypedDict not compatible with dict[str, Any] in mypy 1.19
- 1. [Rule 1 - Bug] routeros.py accessed config.router attribute not on BaseConfig

---

## v1.28 Infrastructure Optimization (Shipped: 2026-04-05)

**Phases completed:** 4 phases, 5 plans, 9 tasks

**Key accomplishments:**

- 3-core IRQ affinity splits Spectrum bridge across CPU0+CPU2, netdev_budget doubled to 600, RRUL load avg drops 23% (1.13 to 0.87)
- SFP+ switched to multi-queue mq-pfifo eliminating 404K TX queue drops; heaviest switch IRQ (36) pinned from cpu2 to cpu1 for load rebalancing
- ZeroTier binding to wireguard1 caused 850K+ TX errors (43K/day); restricting ZT to WAN/LAN interfaces reduced error rate to 0
- nftables bridge forward rules with conntrack marks classifying download traffic into CAKE diffserv4 Voice/Bulk/BestEffort tins on both Spectrum and ATT bridges
- Bridge QoS deployed to cake-shaper VM with nftables DSCP classification active on both bridges -- ATT tin separation verified, Spectrum showing 1.8M Voice + 95K Bulk packets, RRUL validation pending after ceiling sweep

---

## v1.27 Performance & QoS (Shipped: 2026-04-03)

**Phases completed:** 6 phases, 11 plans, 12 tasks

**Key accomplishments:**

- 6 sub-timers added to run_cycle hot path + health endpoint subsystems breakdown for identifying 138% cycle budget overrun sources
- RTT measurement consumes 84.6% of 50ms cycle budget under RRUL load (42ms avg, p99=116ms); SQLite hypothesis disproven at 6.6%; Phase 132 to optimize ICMP path + non-blocking I/O
- Decoupled RTT measurement from control loop via BackgroundRTTThread with persistent ThreadPoolExecutor and GIL-protected atomic swap, eliminating 42ms blocking I/O from hot path
- Health endpoint gains ok/warning/critical status field from rolling utilization vs configurable threshold (80%), with AlertEngine cycle_budget_warning after 60 consecutive overruns and SIGUSR1 hot-reload
- check_tin_distribution() validates per-tin CAKE packet counts via local tc subprocess with PASS/WARN verdicts for DSCP mark survival
- 60s windowed suppression counter in QueueController with health endpoint exposure and periodic INFO logging during congestion
- Discord alert fires via AlertEngine when windowed suppression rate exceeds configurable threshold during congestion, with SIGUSR1 hot-reload for threshold

---

## v1.26 Tuning Validation (Shipped: 2026-04-03)

**Phases completed:** 5 phases, 5 plans, 31 tasks

**Key accomplishments:**

- Reusable bash gate script validates 5 pre-tuning conditions on production cake-shaper VM -- all 5/5 pass, environment confirmed ready for linux-cake A/B testing
- 9 DL parameters A/B tested on linux-cake transport via RRUL flent -- 6 of 9 changed from REST-validated values, revealing transport-dependent tuning shift toward gentler response and wider thresholds
- 3 UL parameters A/B tested on linux-cake transport -- step_up_mbps changed from 1 to 2, factor_down=0.85 and green_required=3 confirmed
- CAKE rtt=40ms validated (5-way test), confirmation pass caught target_bloat_ms interaction flip from 15 back to 9 -- final linux-cake config has 7 total changes from REST baseline
- Verified all 13 tuning parameters on production cake-shaper match linux-cake A/B winners, updated example config and CHANGELOG v1.26.0 with per-parameter metrics

---

## v1.25 Reboot Resilience (Shipped: 2026-04-02)

**Phases completed:** 1 phase (125), 2 plans, 4 tasks

**Key accomplishments:**

- Idempotent NIC tuning shell script with ring buffers (4096), rx-udp-gro-forwarding, and IRQ affinity for 4 bridge NICs with journal logging
- systemd dependency wiring (After= + Wants=) ensuring wanctl waits for NIC tuning completion
- deploy.sh updated to deploy NIC tuning script and service alongside wanctl code
- Dry-run validated on production: script idempotent, dependencies verified, services unaffected

**Known gaps (deferred to v1.26):**

- BOOT-04: Full reboot E2E test (requires physical access)
- VALN-01/VALN-02: Boot validation CLI tool (Phase 126 scope)

---

## v1.24 EWMA Boundary Hysteresis (Shipped: 2026-04-02)

**Phases completed:** 8 phases, 14 plans, 20 tasks

**Key accomplishments:**

- NetlinkCakeBackend with pyroute2 netlink for CAKE bandwidth control, singleton IPRoute lifecycle, and per-call subprocess fallback
- Netlink-based per-tin CAKE stats via pyroute2 TCA_STATS2 decoder with factory dispatch for linux-cake-netlink transport
- Per-granularity retention thresholds in YAML config with cross-section tuner validation and prometheus_compensated mode
- Per-granularity retention wired into both daemons with SIGUSR1 reload, cross-section validation at startup, and config-driven downsample thresholds
- Standalone FusionHealer with incremental rolling Pearson correlation, 3-state machine (ACTIVE/SUSPENDED/RECOVERING), AlertEngine alerts, parameter locking, and SIGUSR1 grace period
- FusionHealer wired into WANController with per-cycle delta feeding, state-transition-driven fusion toggling, SIGUSR1 grace period, and heal state in health endpoint
- 3 pure-function response tuning strategies (step_up, factor_down, green_required) with episode detection infrastructure analyzing wanctl_state 1m time series for congestion-recovery patterns
- RESPONSE_LAYER wired as 5th rotation layer with oscillation lockout, 6-param controller mapping, and RTUN-05 default-exclude graduation pattern
- Dwell timer (3-cycle gate) and deadband margin (3ms hysteresis band) on QueueController GREEN/YELLOW boundary for both upload and download state machines
- YAML config wiring for dwell_cycles and deadband_ms with schema validation, sensible defaults (3/3.0), and QueueController pass-through
- SIGUSR1 hot-reload for dwell_cycles and deadband_ms with bounds validation, old->new logging, and E2E chain integration
- Per-direction suppression counter and health endpoint hysteresis sub-dict with dwell_counter, dwell_cycles, deadband_ms, transitions_suppressed; DEBUG/INFO logging on suppressed and confirmed transitions

---

## v1.23 Self-Optimizing Controller (Shipped: 2026-03-27)

**Phases completed:** 4 phases, 8 plans, 12 tasks

**Key accomplishments:**

- NetlinkCakeBackend with pyroute2 netlink for CAKE bandwidth control, singleton IPRoute lifecycle, and per-call subprocess fallback
- Netlink-based per-tin CAKE stats via pyroute2 TCA_STATS2 decoder with factory dispatch for linux-cake-netlink transport
- Per-granularity retention thresholds in YAML config with cross-section tuner validation and prometheus_compensated mode
- Per-granularity retention wired into both daemons with SIGUSR1 reload, cross-section validation at startup, and config-driven downsample thresholds
- Standalone FusionHealer with incremental rolling Pearson correlation, 3-state machine (ACTIVE/SUSPENDED/RECOVERING), AlertEngine alerts, parameter locking, and SIGUSR1 grace period
- FusionHealer wired into WANController with per-cycle delta feeding, state-transition-driven fusion toggling, SIGUSR1 grace period, and heal state in health endpoint
- 3 pure-function response tuning strategies (step_up, factor_down, green_required) with episode detection infrastructure analyzing wanctl_state 1m time series for congestion-recovery patterns
- RESPONSE_LAYER wired as 5th rotation layer with oscillation lockout, 6-param controller mapping, and RTUN-05 default-exclude graduation pattern

---

## v1.22 Full System Audit (Shipped: 2026-03-27)

**Phases completed:** 14 phases, 33 plans, 55 tasks

**Key accomplishments:**

- All 4 target NICs (2x i210, 2x i350) confirmed in separate single-device IOMMU groups on odin -- PCIe passthrough feasible, Phase 109 unblocked
- LinuxCakeBackend implementing RouterBackend ABC with tc subprocess calls for CAKE bandwidth control, per-tin stats parsing, and qdisc initialization/validation
- Direction-aware CakeParamsBuilder with upload ack-filter, download ingress+ecn, overhead keyword validation, and readback-to-numeric conversion
- Extended initialize_cake with overhead_keyword standalone tc token support, elif priority over numeric fallback, and build_cake_params integration tests
- get_backend() factory routes linux-cake transport to LinuxCakeBackend with direction-parameterized from_config reading cake_params interfaces
- validate_linux_cake() added to wanctl-check-config: validates cake_params structure, interfaces, overhead keywords, and tc binary with 14 TDD tests
- Transport-aware CakeStatsReader delegates to LinuxCakeBackend for linux-cake transport with per-tin CAKE stats in health endpoint
- Per-tin CAKE observability pipeline: 4 metrics registered in STORED_METRICS, batch writes in daemon gated on linux-cake transport, --tins flag in wanctl-history with pivoted table display
- VFIO passthrough active on odin: 4 NICs (2x i210, 2x i350) bound to vfio-pci, management X552 unaffected
- VM 206 (cake-shaper) running Debian 13 with 4 VFIO passthrough NICs: ens16/ens17 (i210 Spectrum), ens27/ens28 (i350 ATT)
- Two transparent L2 bridges (br-spectrum, br-att) configured via systemd-networkd with STP disabled, verified across reboot
- wanctl deployed to cake-shaper with CAKE qdiscs verified on ens17 (Spectrum) and ens28 (ATT) — JSON stats parseable
- linux-cake configs created for both WANs, baseline RRUL benchmarks captured: Spectrum 696 Mbps avg download (MikroTik ceiling to beat)
- ATT migrated to Linux CAKE on cake-shaper: +8.5% download, +97% upload, -3.8% latency vs MikroTik baseline
- Rollback proven organically during ATT cutover — bridge forwards L2 without CAKE, MikroTik queues re-enableable
- Full production cutover complete: both WANs on Linux CAKE, steering active, grade A bufferbloat
- Fixed 60x outlier rate underestimate in SIGP-01 via time-gap-aware normalization, updated MAX_WINDOW to 21, widened 4 config bounds stuck at limits
- pip-audit zero critical CVEs, 2 unused deps removed (cryptography + pyflakes), 8 orphaned fixtures cataloged, log rotation verified at 10MB/3 backups
- File permissions verified (31 items, 0 FAIL) and systemd exposure scores documented (8.4 EXPOSED for 3 runtime services) with prioritized hardening roadmap for Phase 115
- Enabled 8 new ruff categories (C901/SIM/PERF/RET/PT/TRY/ARG/ERA), resolved 839 findings via autofix + manual fix + triage, established complexity baseline for Phase 114
- Vulture 2.16 scan of 28,629 LOC identifying 0 true dead items at 80% confidence after whitelisting all 15 PITFALLS.md false positive patterns
- CAKE parameters verified correct for 4 qdiscs across 2 WANs; DSCP classification chain traced end-to-end from MikroTik mangle through transparent bridge to CAKE diffserv4 tins
- Confidence scoring audit with all 10 weights documented, timer match verified, CAKE-primary invariant confirmed; signal chain traced from reflector selection through Hampel/Fusion/EWMA to delta, with IRTT/ICMP/TCP paths and reflector scoring validated against production config
- Production CAKE queue statistics baseline: 0-60.9% memory across 4 qdiscs, zero backlog in GREEN state, 32mb memlimit confirmed appropriate
- Triaged all 96 except Exception catches: 88 safety nets, 5 bug-swallowing catches fixed with DEBUG logging
- MyPy strictness probe (5/5 leaf modules pass), complexity hotspot analysis with 8 extraction recommendations for v1.23, and import graph audit finding 2 safe TYPE_CHECKING-guarded cycles
- Thread safety audit of 10 files (24 shared state instances, 0 high-severity races) plus SIGUSR1 reload chain catalog with 10 E2E tests covering all 5 reload targets
- Hardened all 4 systemd units on production VM -- wanctl@ scored 2.1 OK and steering 1.9 OK (down from 8.4 EXPOSED), with circuit breaker config made consistent across all 3 runtime services
- Production dependency lock from live VM pip freeze (28 pinned packages) plus comprehensive backup/recovery runbook covering configs, metrics.db, VM snapshots, and Phase 115 rollback procedures
- Resource limits (MemoryMax/MemoryHigh/TasksMax/LimitNOFILE) applied to all runtime services from production observation, NIC tuning persistence confirmed across full VM reboot with all 4 services healthy post-boot
- AST-scanned 126 test files (3,888 tests), found 20 assertion-free tests (4 fixed), 0 tautological, 9 over-mocked (documented only)
- CONFIG_SCHEMA.md aligned with 6 missing config sections (storage, cake_params, fallback_checks, linux-cake transport, logging rotation, cake_optimization), 12 docs updated for VM architecture, container audit script archived
- Capstone v1.22 audit document aggregating 15 findings files across 5 phases: 87 findings identified, 34 resolved, 38 remaining debt (0 P0, 4 P1, 11 P2, 9 P3, 14 P4) with v1.23 recommendations

---

## v1.20 Adaptive Tuning (Shipped: 2026-03-19)

**Delivered:** Self-optimizing controller that learns optimal parameters from production metrics via 4-layer tuning rotation, with safety revert detection, signal processing optimization, and fusion baseline deadlock fix.

**Phases completed:** 98-103 (13 plans total)

**Key accomplishments:**

- Self-optimizing tuning engine with per-WAN analysis, SIGUSR1 toggle, SQLite persistence, and health endpoint visibility (Phase 98)
- Congestion threshold calibration deriving target/warn bloat from GREEN-state RTT delta percentiles with convergence detection (Phase 99)
- Safety & revert system monitoring post-adjustment congestion rate with automatic rollback and hysteresis locks (Phase 100)
- Signal processing tuning: Hampel sigma/window and EWMA alpha optimized per-WAN via 4-layer round-robin rotation (Phase 101)
- Advanced tuning: fusion weight, reflector min_score, baseline bounds auto-adjusted from signal reliability (Phase 102)
- Fusion baseline deadlock fix: signal path split — fused RTT for load EWMA, ICMP-only for baseline EWMA (Phase 103)

**Stats:**

- 6 phases, 13 plans
- 112 commits, 41 files changed
- +8,534 / -184 lines changed
- ~265 new tests (3,458 to ~3,723)
- 28,629 LOC Python (src/)
- 3 days (2026-03-18 to 2026-03-20)

**Git range:** `v1.19..v1.20`

**What's next:** v1.21 planning.

---

## v1.19 Signal Fusion (Shipped: 2026-03-18)

**Delivered:** Dual-signal fusion engine combining ICMP and IRTT RTT measurements for congestion control, with reflector quality scoring, OWD asymmetric congestion detection, IRTT loss alerting, and zero-downtime SIGUSR1 toggle.

**Phases completed:** 93-97 (9 plans total)

**Key accomplishments:**

- Reflector quality scoring with rolling deques, automatic deprioritization of unreliable ping_hosts, and periodic recovery probes with graceful degradation (3/2/1/0 active hosts)
- OWD asymmetric congestion detection from IRTT burst-internal send_delay vs receive_delay ratios (no NTP dependency), with SQLite persistence
- IRTT sustained loss alerting (upstream/downstream) via AlertEngine with per-event cooldown and Discord notifications
- Dual-signal fusion engine: weighted ICMP+IRTT average (\_compute_fused_rtt) as congestion control input, with multi-gate fallback (thread/result/freshness/validity)
- Fusion safety gate: ships disabled by default (fusion.enabled: false) with SIGUSR1 zero-downtime toggle — first reload capability in autorate daemon
- Full health endpoint fusion visibility (enabled/disabled state, active weights, signal sources, fused RTT values)

**Stats:**

- 5 phases, 9 plans
- 40 commits, 86 files changed
- +6,437 / -8,547 lines changed
- ~202 new tests (3,256 to ~3,458)
- 26,098 LOC Python (src/)
- ~18 hours (2026-03-17 to 2026-03-18)

**Git range:** `docs(95): capture phase context` to `docs: add config sections`

**What's next:** v1.19 deploy + fusion graduation, then v1.20 planning.

---

## v1.18 Measurement Quality (Shipped: 2026-03-17)

**Delivered:** RTT signal quality improvements with Hampel outlier filtering, IRTT UDP measurements via background thread, protocol correlation, container networking audit, and full observability.

**Phases completed:** 88-92 (10 plans total)

**Key accomplishments:**

- Hampel outlier filter with jitter/variance EWMA and confidence scoring in observation mode
- IRTT UDP RTT measurement via subprocess wrapper with JSON parsing and graceful fallback
- Background IRTT daemon thread with lock-free caching (frozen dataclass + GIL atomic swap)
- ICMP vs UDP protocol correlation with deprioritization detection
- Container networking audit confirmed 0.17ms overhead (negligible, report-only closure)
- Health endpoint signal_quality + irtt sections with SQLite persistence for both
- 363 new tests (2,893 to 3,256), 21/21 requirements satisfied

---

## v1.17 CAKE Optimization & Benchmarking (Shipped: 2026-03-16)

**Delivered:** Automated CAKE queue type parameter detection and optimization via `wanctl-check-cake --fix`, plus RRUL bufferbloat benchmarking with A-F grading, SQLite storage, and before/after comparison.

**Phases completed:** 84-87 (8 plans total)

**Key accomplishments:**

- Sub-optimal CAKE parameter detection via REST API (`GET /rest/queue/type`) with severity, rationale, and diff output for link-independent and link-dependent params
- Auto-fix CAKE parameters via `--fix` flag with daemon lock check, JSON snapshot rollback, interactive confirmation, and REST PATCH to `/rest/queue/type/{id}`
- RRUL bufferbloat benchmarking via `wanctl-benchmark` wrapping flent with A+-F grading, P50/P95/P99 latency percentiles, and throughput reporting
- Benchmark result storage in SQLite with auto-store, before/after comparison (`wanctl-benchmark compare`), and history with time-range filtering
- Full operator loop validated in production: check-cake → fix → benchmark → compare on both Spectrum and ATT WANs
- CAKE params optimized on both WANs (nat, ack-filter, wash), ATT overhead corrected (pppoe-ptm → bridged-ptm)

**Stats:**

- 4 phases, 8 plans
- 59 commits, 87 files changed
- +20,534 / -1,135 lines changed
- 70 new tests (2,823 to 2,893)
- 24,056 LOC Python (src/)
- 3 days (2026-03-13 to 2026-03-16)

**Git range:** `v1.16..v1.17`

**What's next:** v1.18 Measurement Quality — IRTT integration, container networking optimization, RTT signal quality improvements.

---

## v1.16 Validation & Operational Confidence (Shipped: 2026-03-13)

**Delivered:** Operator-facing CLI tools that catch misconfigurations before runtime and verify router queue state matches expectations.

**Phases completed:** 81-83 (4 plans total)

**Key accomplishments:**

- `wanctl-check-config` CLI tool for offline config validation with 6 categories (schema, cross-field, unknown keys, paths, env vars, deprecated params)
- Auto-detection of config type (autorate vs steering) from YAML contents without `--type` flag
- Steering-specific validation with cross-config topology checks (primary_wan_config path existence, wan_name match)
- JSON output mode (`--json`) for CI/scripting integration with structured category/severity/suggestion output
- `wanctl-check-cake` CLI tool for live router CAKE queue audit (connectivity, queue tree, CAKE type, max-limit diff, mangle rules)
- Reusable CheckResult/Severity data model shared between both CLI tools

**Stats:**

- 3 phases, 4 plans
- 32 commits
- 157 new tests (2,666 to 2,823)
- 22,180 LOC Python (src/)
- 2 days (2026-03-12 to 2026-03-13)

**Git range:** `v1.15..v1.16`

**What's next:** Next milestone planning.

---

## v1.15 Alerting & Notifications (Shipped: 2026-03-12)

**Delivered:** Proactive alerting system with Discord webhook delivery, per-event cooldown suppression, and 7 alert types covering congestion, steering, connectivity, and anomaly events.

**Phases completed:** 76-80 (10 plans total)

**Key accomplishments:**

- AlertEngine embedded in both daemons with per-event (type, WAN) cooldown suppression and SQLite persistence, disabled by default
- Discord webhook delivery with color-coded severity embeds (red/yellow/green), retry with exponential backoff, and extensible AlertFormatter Protocol
- Sustained congestion detection with independent DL/UL timers, zone-dependent severity (RED=critical, SOFT_RED=warning), and recovery gate
- Steering transition alerts tracking activation/recovery with duration, confidence score, and WAN context
- WAN offline/recovery detection, baseline RTT drift alerts (>25% deviation), and congestion zone flapping detection (6+ transitions in 5min)
- Health endpoint alerting section (enabled, fire_count, active_cooldowns) and `wanctl-history --alerts` CLI with time-range filtering

**Stats:**

- 5 phases, 10 plans
- 31 commits
- 221 new tests (2,445 to 2,666)
- 20,140 LOC Python (src/)
- 1 day (2026-03-12)

**Git range:** `v1.14..v1.15`

**What's next:** Next milestone planning.

---

## v1.14 Operational Visibility (Shipped: 2026-03-11)

**Delivered:** Full TUI dashboard (`wanctl-dashboard`) for real-time monitoring and historical analysis of both WAN links with adaptive layout and terminal compatibility.

**Phases completed:** 73-75 (7 plans total)

**Key accomplishments:**

- Full TUI dashboard with live per-WAN panels showing color-coded congestion state, DL/UL rates, RTT baseline/load/delta, and router connectivity
- Async dual-poller engine with independent endpoint backoff and offline isolation for multi-container WAN monitoring
- Sparkline trend widgets (DL/UL with green-to-yellow gradient, RTT delta with green-to-red) using bounded deques for constant memory
- Cycle budget gauge showing 50ms utilization percentage from health endpoint data
- Historical metrics browser with time range selector (1h/6h/24h/7d), DataTable, and client-side summary stats (min/max/avg/p95/p99)
- Responsive layout: side-by-side at >=120 cols, stacked below, with 0.3s resize hysteresis
- Terminal compatibility: --no-color, --256-color CLI flags, tmux/SSH verified

**Stats:**

- 3 phases, 7 plans
- 51 commits, 71 files changed
- +10,425 / -1,247 lines changed
- 145 new dashboard tests (2,300 to 2,445)
- 1,289 LOC dashboard module, 18,393 LOC total (src/)
- 1 day (2026-03-11)

**Git range:** `v1.13..v1.14`

**What's next:** Next milestone planning.

---

## v1.13 Legacy Cleanup & Feature Graduation (Shipped: 2026-03-11)

**Delivered:** Legacy code removal, config fallback retirement with deprecation warnings, and graduation of both confidence-based steering and WAN-aware steering from dry-run/disabled to production-live.

**Phases completed:** 67-72 (10 plans total)

**Key accomplishments:**

- Production config audit confirmed all active configs use modern parameters exclusively — zero legacy fallbacks exercised
- Dead code eliminated: cake_aware mode branching removed (119 lines), 7 obsolete ISP-specific config files deleted, CAKE three-state is now sole code path
- Centralized `deprecate_param()` helper with warn+translate for 8 legacy config parameters — old names produce clear deprecation warnings
- SIGUSR1 generalized hot-reload: single signal toggles both `dry_run` and `wan_state.enabled` without daemon restart
- Confidence-based steering graduated from dry-run to live mode with production-verified SIGUSR1 rollback path
- WAN-aware steering enabled in production with 4-step degradation verification (stale fallback, SIGUSR1 rollback, grace period re-trigger)

**Stats:**

- 6 phases, 10 plans
- 53 commits, 57 files changed
- +6,408 / -715 lines changed
- 37 new tests (2,263 to 2,300)
- 17,095 LOC Python (src/)
- 1 day (2026-03-11)

**Git range:** `v1.12..v1.13`

**What's next:** Next milestone planning.

---

## v1.12 Deployment & Code Health (Shipped: 2026-03-11)

**Delivered:** Deployment alignment, dead code removal, security hardening, fragile area stabilization, and infrastructure consolidation for production hygiene.

**Phases completed:** 62-66 (7 plans total)

**Key accomplishments:**

- Deployment artifacts (Dockerfile, install.sh, deploy.sh) aligned with pyproject.toml as single source of truth, version bumped to 1.12.0
- Dead code removed: pexpect dependency eliminated, dead subprocess import and stale timeout_total API cleaned from RTT measurement
- Security hardened: router password cleared after client construction, SSL warnings scoped per-request, safe fallback gateway default, integration test hosts parameterized
- Fragile areas stabilized: state file schema contract tests catch key renames, check_flapping side-effect contract documented, WAN config warnings at proper level
- Config boilerplate consolidated: 6 common fields extracted to BaseConfig, eliminating duplicate YAML-to-attribute loading across both daemons
- Infrastructure validated: RotatingFileHandler for log rotation (10MB/3 backups), 17 Dockerfile/dependency contract tests parametrized from pyproject.toml

**Stats:**

- 5 phases, 7 plans
- 53 new tests (2,210 to 2,263)
- 16,993 LOC Python (src/)
- 2 days (2026-03-10 to 2026-03-11)

**Git range:** `v1.11..v1.12`

**What's next:** Next milestone planning.

---

## v1.11 WAN-Aware Steering (Shipped: 2026-03-10)

**Delivered:** WAN-aware steering that fuses autorate congestion zone into confidence scoring, with fail-safe defaults, YAML configuration, and full observability.

**Phases completed:** 58-61 (8 plans total)

**Key accomplishments:**

- Autorate state file exports congestion zone (dl_state/ul_state) with dirty-tracking exclusion preventing write amplification
- WAN zone fused into confidence scoring (WAN_RED=25, WAN_SOFT_RED=12) — CAKE-primary invariant enforced (WAN alone < steer_threshold)
- Fail-safe defaults at every boundary: stale zone (>5s) defaults GREEN, autorate unavailable skips WAN weight, 30s startup grace period
- YAML `wan_state:` configuration with warn+disable graceful degradation, ships disabled by default
- Full observability: health endpoint `wan_awareness` section, 3 SQLite metrics (zone/weight/staleness), WAN context in steering transition and degrade timer logs

**Stats:**

- 16 files modified
- +2,437 / -78 lines changed
- 4 phases, 8 plans, 56 commits
- 101 new tests (2,109 to 2,210)
- 16,880 LOC Python (src/)
- 2 days (2026-03-09 to 2026-03-10)

**Git range:** `v1.10..v1.11`

**What's next:** Next milestone planning.

---

## v1.10 Architectural Review Fixes (Shipped: 2026-03-09)

**Delivered:** Hot-loop fixes, steering reliability, operational resilience, codebase audit, and test quality improvements from senior architectural review.

**Phases completed:** 50-57 (14 plans executed, 1 superseded)

**Key accomplishments:**

- Hot-loop blocking delays eliminated (sub-cycle retries, 50ms max per attempt)
- Self-healing transport failover with periodic primary REST re-probe (30-300s backoff)
- SSL verify_ssl=True default across all layers, SQLite corruption auto-recovery, disk space monitoring
- Daemon duplication consolidated (daemon_utils.py, perf_profiler.py), systematic codebase audit
- Test fixture consolidation (-481 lines), 24 new behavioral/integration tests
- 27/27 requirements satisfied, 6/6 E2E flows verified

---

## v1.9 Performance & Efficiency (Shipped: 2026-03-07)

**Delivered:** Profiling-driven cycle optimization with icmplib raw ICMP sockets, per-subsystem telemetry, and health endpoint cycle budget visibility.

**Phases completed:** 47-49 (6 plans total)

**Key accomplishments:**

- Instrumented both daemons with per-subsystem PerfTimer hooks and OperationProfiler accumulation (8 labeled timers)
- Replaced subprocess.run(["ping"]) with icmplib raw ICMP sockets, reducing Spectrum avg cycle by 3.4ms (8.3%) and ATT by 2.1ms (6.8%)
- Added structured DEBUG logging with per-subsystem timing and rate-limited overrun detection
- Exposed cycle_budget telemetry (avg/P95/P99, utilization %, overrun count) in both health endpoints via shared \_build_cycle_budget() helper
- Updated profiling analysis pipeline for 50ms budget context with P50 percentile and --budget CLI flag

**Stats:**

- 16 files modified
- +2,532 / -538 lines changed
- 3 phases, 6 plans, 39 commits
- 97 new tests (1,881 to 1,978)
- 16,136 LOC Python (src/)
- 1 day (2026-03-06)

**Git range:** `feat(47-01)` → `docs(phase-49)`

**What's next:** Next milestone planning.

---

## v1.8 Resilience & Robustness (Shipped: 2026-03-06)

**Delivered:** Error recovery, fail-safe behavior, and graceful shutdown for production reliability.

**Phases completed:** 43-46 (8 plans total, Phase 46 deferred)

**Key accomplishments:**

- Router error detection and reconnection with 6 failure categories and rate-limited logging
- Fail-closed rate queuing with 60s stale threshold and monotonic timestamps
- Watchdog continues on router failures, stops on auth failures
- Graceful shutdown with bounded cleanup deadlines and state persistence
- Coverage recovery to 91%+ after test pollution fix

**Stats:**

- 4 phases (including 44.1 inserted), 8 plans
- 154 new tests (1,727 to 1,881)
- ~1 month (2026-01-29 to 2026-03-06)

**Git range:** `feat(43-01)` → `docs(phase-45)`

**What's next:** v1.9 Performance & Efficiency milestone.

---

## v1.7 Metrics History (Shipped: 2026-01-25)

**Delivered:** SQLite metrics storage with automatic downsampling, CLI tool, and HTTP API for historical metrics access.

**Phases completed:** 38-42 (8 plans total)

**Key accomplishments:**

- SQLite storage layer (8 modules, 1,038 lines) with schema versioning
- Both daemons record metrics each cycle (<5ms overhead)
- `wanctl-history` CLI tool for querying metrics
- `/metrics/history` HTTP API endpoint
- Automatic startup maintenance (cleanup, downsample)

**Stats:**

- 5 phases, 8 plans
- 237 new tests (1,490 to 1,727)
- 1 day (2026-01-25)

**Git range:** `feat(38-01)` → `docs(42)`

**What's next:** v1.8 Resilience & Robustness milestone.

---

## v1.6 Test Coverage 90% (Shipped: 2026-01-25)

**Delivered:** Comprehensive test coverage from 45.7% to 90.08% with CI enforcement.

**Phases completed:** 31-37 (17 plans total)

**Key accomplishments:**

- Coverage increased from 45.7% to 90.08% (target: 90%)
- 743 new tests added (747 to 1,490 total)
- CI enforcement via fail_under=90 in pyproject.toml
- All major modules tested: backends, state, metrics, controllers, CLI tools

**Stats:**

- 7 phases, 17 plans
- 743 new tests
- 2 days (2026-01-25)

**Git range:** `feat(31-01)` → `docs(37)`

**What's next:** v1.7 Metrics History milestone.

---

## v1.5 Quality & Hygiene (Shipped: 2026-01-24)

**Delivered:** Code quality infrastructure with test coverage measurement, security scanning, and documentation verification.

**Phases completed:** 27-30 (8 plans total)

**Key accomplishments:**

- Established test coverage infrastructure (pytest-cov, 72% baseline, HTML reports, README badge)
- Verified codebase cleanliness (zero dead code, zero TODOs, complexity analysis for 11 functions)
- Standardized documentation to v1.4.0 (6 files updated, 14 doc issues fixed)
- Achieved security posture (zero CVEs, 4 security tools, `make security` target)

**Stats:**

- 20+ files modified
- ~13,273 lines of Python (src/)
- 4 phases, 8 plans
- 747 tests, 72% coverage
- 1 day (2026-01-24)

**Git range:** `chore(27-01)` → `docs(30): complete`

**What's next:** Next milestone planning.

---

## v1.4 Observability (Shipped: 2026-01-24)

**Delivered:** HTTP health endpoint for steering daemon enabling external monitoring and container orchestration.

**Phases completed:** 25-26 (4 plans total)

**Key accomplishments:**

- Created steering daemon HTTP health endpoint on port 9102 with JSON responses
- Implemented 200/503 status codes for Kubernetes probe compatibility
- Exposed live steering state: confidence scores, congestion states, decision timestamps
- Integrated health server lifecycle with daemon (start/stop automatically)
- Added 28 tests covering all 14 requirements (HLTH-_, STEER-_, INTG-\*)
- Achieved 100% requirement coverage with zero tech debt

**Stats:**

- 14 files modified
- +2,375 lines changed
- 2 phases, 4 plans
- 28 new tests (725 → 752)
- 1 day (2026-01-24)

**Git range:** `feat(25-01)` → `docs(26-02)`

**What's next:** Deploy to production, integrate with monitoring dashboards.

---

## v1.3 Reliability & Hardening (Shipped: 2026-01-21)

**Delivered:** Safety invariant test coverage, deployment validation, and production wiring for REST-to-SSH failover.

**Phases completed:** 21-24 (5 plans total)

**Key accomplishments:**

- Implemented FailoverRouterClient with automatic REST-to-SSH failover (16 tests)
- Proved baseline RTT freeze invariant under 100+ cycles of sustained load (5 tests)
- Proved state file corruption recovery across 12 distinct failure scenarios
- Created 423-line deployment validation script (config, router, state checks)
- Hardened deploy.sh with fail-fast on missing steering.yaml
- Wired safety features into all 3 production entry points

**Stats:**

- 11 files modified
- +1,526 lines changed
- 4 phases, 5 plans
- 54 new tests (671 → 725)
- 1 day (2026-01-21)

**Git range:** `test(21-01)` → `docs(24): complete`

**What's next:** Monitor production failover behavior, consider Phase2BController enablement.

---

## v1.2 Configuration & Polish (Shipped: 2026-01-14)

**Delivered:** Phase2B confidence-based steering enabled in dry-run mode, configuration documentation and validation improvements.

**Phases completed:** 16-20 (5 plans total)

**Key accomplishments:**

- Fixed Phase2B timer interval to use cycle_interval instead of hardcoded 2s
- Documented baseline_rtt_bounds in CONFIG_SCHEMA.md with validation
- Added deprecation warnings for legacy steering params (bad_samples, good_samples)
- Added 77 edge case tests for config validation (boundary lengths, Unicode attacks, numeric boundaries)
- Enabled Phase2B confidence scoring in production with dry_run=true for safe validation

**Stats:**

- 9 commits
- ~22,065 lines of Python
- 5 phases, 5 plans
- 77 new tests (594 → 671)
- 1 day (2026-01-14)

**Git range:** `fix(phase2b)` → `docs(20-01)`

**What's next:** Monitor Phase2B dry-run validation (1 week), then set dry_run=false for live confidence-based steering.

---

## v1.1 Code Quality (Shipped: 2026-01-14)

**Delivered:** Systematic code quality improvements through refactoring, consolidation, and documentation while preserving production stability.

**Phases completed:** 6-15 (34 plans total)

**Key accomplishments:**

- Created signal_utils.py and systemd_utils.py shared modules, eliminating ~110 lines of duplicated code
- Consolidated 4 redundant utility modules (~350 lines removed), reducing module fragmentation
- Documented 12 refactoring opportunities in CORE-ALGORITHM-ANALYSIS.md with risk assessment and protected zones
- Refactored WANController (4 methods extracted) and SteeringDaemon (5 methods extracted) from run_cycle()
- Unified state machine methods (CAKE-aware + legacy) in SteeringDaemon
- Integrated Phase2BController confidence scoring with dry-run mode for safe production validation

**Stats:**

- 100 commits
- ~20,960 lines of Python
- 10 phases, 34 plans
- 120 new tests (474 → 594)
- 1 day (2026-01-13 to 2026-01-14)

**Git range:** `feat(06-01)` → `docs(15-06)`

**What's next:** Production validation of Phase2BController confidence scoring, then next milestone planning.

---

## v1.0 Performance Optimization (Shipped: 2026-01-13)

**Delivered:** 40x performance improvement (2s → 50ms cycle time) through interval optimization and event loop architecture.

**Phases completed:** 1-5 (8 plans total, 2 skipped/pre-implemented)

**Key accomplishments:**

- Profiled measurement infrastructure: discovered 30-41ms cycles (2-4% of budget), not ~200ms as assumed
- Converted timer-based execution to persistent event loop architecture
- Reduced cycle interval from 2s to 50ms (40x faster congestion response)
- Preserved EWMA time constants via alpha scaling
- Validated 50ms interval under RRUL stress testing
- Documented findings in PRODUCTION_INTERVAL.md

**Stats:**

- Phases 1-3 active, Phases 4-5 pre-implemented
- 352,730 profiling samples analyzed
- Sub-second congestion detection (50-100ms response)
- 0% router CPU at idle, 45% peak under load

**Git range:** `feat(01-01)` → `docs(03-02)`

**What's next:** v1.1 Code Quality milestone (systematic refactoring).

---
