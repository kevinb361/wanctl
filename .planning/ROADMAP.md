# Roadmap: wanctl

## Milestones

- 🚧 **v1.53 Pluggable RTT Measurement Backend** — in progress (Phases 238–246; 26 REQs; `RttBackend` seam behind icmplib default, `fping` first alternate, cycle-budget gate, live A/B on the verified RTT producer, conditional default flip — first controller-path-touching milestone in 10, SAFE-17 narrowed allowlist)
- ✅ **v1.52 Silicom Bypass Operationalization** — shipped 2026-06-14 (Phases 235–237; 15/15 REQs; guarded bypass CLI + boot baseline, two-mode watchdog fail-open, HIL harness, standalone deploy ownership, SAFE-16 held — 10th consecutive zero-controller-diff milestone) — `milestones/v1.52-ROADMAP.md`
- ✅ **v1.51 Post-Migration Consolidation** — shipped 2026-06-12 (Phases 232–234; 10/10 REQs; BOUND-01 cleanup guard fail-closed, gated repo sweep, planning-metadata reconciliation, SAFE-15 held — 9th consecutive zero-controller-diff milestone) — `milestones/v1.51-ROADMAP.md`
- ✅ **v1.50 cake-autorate Migration Hardening** — shipped 2026-06-10 (Phases 229–231; 10/10 REQs, audit passed; ATT deploy/test/monitor parity, both-WAN migration-held PASS, rollback provable, SAFE-14 held) — `milestones/v1.50-ROADMAP.md`
- ✅ **v1.49 Spectrum DSCP Tinning Re-evaluation** — closed 2026-06-09 overtaken-by-events (Phases 225–227 complete; Phase 228 verdict unexecuted — production migrated both WANs to cake-autorate before it ran) — `milestones/v1.49-ROADMAP.md`
- ✅ **v1.48 Steering Runtime Drift Closure** — shipped 2026-06-03 (Phases 222–224; live steering daemon aligned `1.39 → 1.47` in production, canary kept_aligned, SAFE-12 held) — `milestones/v1.48-ROADMAP.md`
- ✅ **v1.47 Measurement Evidence Closure** — shipped 2026-06-02 (Phases 219–221; 18/18 REQs satisfied; `tcp_12down` closed-with-prejudice per CRITERIA-02) — `milestones/v1.47-ROADMAP.md`
- ✅ **v1.46 Internet Quality Recovery** — shipped-with-deferral 2026-05-30 (Phases 212–217; VERIFY-01/02 carried to Phase 218 event-gated watch-list) — `milestones/v1.46-ROADMAP.md`
- ✅ **v1.45 Flapping Peak-Counter Window Repair** — shipped-with-deferral 2026-05-27 (Phases 210–211; VERIFY-01 deferred → rolled into Phase 218) — `milestones/v1.45-phases/`
- ✅ **v1.44 Topology-Correct CAKE — Spectrum besteffort wash migration** — shipped 2026-05-26 (Phases 205–209) — `milestones/v1.44-ROADMAP.md`
- ✅ **v1.43 UL Suppression Metrics & Gate Calibration** — shipped 2026-05-13 — `milestones/v1.43-ROADMAP.md`
- ✅ **v1.42 DOCSIS-Aware UL Congestion Control** — shipped 2026-05-06 — `milestones/v1.42-ROADMAP.md`
- ✅ **v1.41 Per-Direction Control Surfaces** — closed 2026-05-04 (gaps_found) — `milestones/v1.41-ROADMAP.md`
- ✅ **v1.40 Queue-Primary Signal Arbitration** — shipped 2026-05-03 — `milestones/v1.40-ROADMAP.md`
- ✅ **v1.39 Control-Path Timing & Measurement Accounting** — shipped 2026-04-24 (operator waiver; archived 2026-05-06 gaps_found) — `milestones/v1.39-ROADMAP.md`
- 📁 **v1.0 — v1.38** — see `MILESTONES.md` for the full historical index

> **Production controller state (2026-06-10):** Both WANs run upstream cake-autorate with wanctl state bridges (`cake-autorate-{spectrum,att}.service` + `-state-bridge.service`, live since 2026-06-08); `wanctl@{spectrum,att}` disabled as the **verified** rollback path (v1.50 SOAK-02 provable path, both-WAN preflight `overall_pass: true`). Steering consumes bridge-written state. Native wanctl remains the MikroTik/RouterOS controller and the portable default. Repo is the drift-proof source of truth for both WANs' artifact sets (`deploy.sh --with-{spectrum,att}-cake-autorate`). Spectrum CAKE: member-NIC `diffserv4 wash` 550M base DL autorate / fixed 18M UL. ATT: `diffserv4 nowash` 95M base DL autorate / fixed 19M UL.

> **v1.53 RTT-provenance caveat:** `SteeringDaemon.rtt_measurement` is *constructed but never called* in the live cake-autorate topology — steering RTT flows from the state bridge via autorate `/health` `measurement.raw_rtt_ms`. The new seam may not be on the live path. Phase 238 is a read-only entry gate that maps provenance and **selects the A/B target** (interpretation A: revive steering's own pinger vs B: evaluate at the autorate/bridge producer) before any code is written. All downstream phases — especially the live A/B (Phase 245) — depend on that selection.

---

## 🚧 v1.53 Pluggable RTT Measurement Backend (In Progress)

**Milestone Goal:** Introduce a config-selectable `RttBackend` abstraction with `fping` as the first alternate, refactor `icmplib` behind it as the byte-identical default, validate `fping` against the live RTT consumer via a pre-registered A/B under a cycle-budget gate and rollback anchor, and flip the production default to `fping` only if the evidence clearly wins. Otherwise the milestone closes cleanly on a documented "stay on `icmplib`" recommendation (v1.46/v1.47 negative-result precedent). This is the **first controller-path-touching milestone in 10** — the SAFE-07..16 zero-diff streak ends *by design*, replaced by the narrowed SAFE-17 allowlist + fail-closed source-diff verifier at every phase boundary and milestone close.

**Dependency spine (researcher-converged):** provenance gate (238) → seam refactor behind icmplib, byte-identical (239) → config+validator (240) → fping backend offline + reflector-quality touch (241) → factory+fallback (242) → cycle-budget benchmark hard gate under real systemd (243) → additive health attribution metadata (244) → live A/B + rollback anchor (245) → conditional default flip / closeout (246). Phases 240 (config) and 241 (fping) may overlap after the seam (239) lands.

- [x] **Phase 238: RTT-Provenance Verification (Read-Only Entry Gate)** — Map which producer feeds live steering RTT; select and record the A/B target with evidence; no code changes. ✅ verified 2026-06-15 (4/4 truths; PROV-01/02/03 + SAFE-17; Selection A ratified)
- [x] **Phase 239: Seam Refactor + IcmplibBackend (Byte-Identical)** — Land the `RttBackend` Protocol with icmplib refactored behind it, provably byte-identical to pre-refactor; define the SAFE-17 allowlist. ✅ verified 2026-06-16 (5/5 truths; SEAM-01..04 + SAFE-17; icmplib byte-identical proven)
- [x] **Phase 240: Config + Validator** — Additive `measurement.backend` per WAN/consumer; validator allow-list; absent key resolves to icmplib; all existing configs validate unchanged. ✅ verified 2026-06-16 (4/4 truths; CFG-01/02/03 + SAFE-17)
- [x] **Phase 241: fping Backend (Offline) + Reflector Quality** — One-shot subprocess fping backend with `-S` binding, multi-reflector fanout, robust loss-safe parser from captured 5.1 samples, stall/death handling, and per-reflector loss feeding reflector scoring. ✅ verified 2026-06-16 (5/5 truths; FPING-01..05 + REFL-01 + SAFE-17)
- [x] **Phase 242: Backend Factory + Loud Fallback** — `build_rtt_backend()` centralizing construction with automatic, loud, observable icmplib fallback when fping is absent. ✅ verified 2026-06-16 (12/12 truths; FALL-01/02 + SAFE-17; WR-01 reflector-scorer gap closed by 242-05, re-verified)
- [ ] **Phase 243: Cycle-Budget Benchmark Gate** — Pre-registered idle+load cycle-budget/CPU benchmark under a real systemd unit; hard no-regression gate that blocks the live A/B.
- [ ] **Phase 244: Health-Payload Attribution Metadata** — Additively expose `measurement.backend` / `source_ip` in `/health` (existing contract byte-preserved) so every A/B sample is attributable.
- [ ] **Phase 245: Live A/B + Rollback Anchor** — Pre-registered live A/B (icmplib vs fping) on the Phase-238-selected target, one WAN under test, concurrent/interleaved, under a Snapshot-A rollback anchor; verdict computed against pre-committed thresholds.
- [ ] **Phase 246: Conditional Default Flip + Milestone Closeout** — Operator-gated flip to fping iff the A/B clearly wins (armed rollback + sign-off) or a documented stay-on-icmplib recommendation; SAFE-17 milestone-close accounting.

## Phase Details

### Phase 238: RTT-Provenance Verification (Read-Only Entry Gate)
**Goal**: The operator has a documented, evidence-backed map of which producer actually feeds live steering RTT in the current cake-autorate topology, and the A/B target interpretation is selected and committed — before any backend code exists.
**Depends on**: Phase 237 (v1.52 close)
**Requirements**: PROV-01, PROV-02, PROV-03, SAFE-17
**Success Criteria** (what must be TRUE):
  1. Operator can read a documented provenance map showing whether live steering RTT comes from the state bridge / autorate `/health` `measurement.raw_rtt_ms` or from wanctl's `RTTMeasurement`, captured read-only with zero production mutation.
  2. The A/B target interpretation (A = revive steering's own pinger as the live RTT source, or B = evaluate at the autorate/bridge producer) is selected and recorded with supporting evidence, with scope boundaries stated.
  3. Operator can confirm via `ip route get <reflector> from <source_ip>` that `fping -S <source_ip>` would egress the intended WAN under the host's current `ip rule` policy routing.
  4. No source files changed; SAFE-17 boundary verifier passes (no controller-path drift).
**Plans**: 5 plans
- [x] 238-01-PLAN.md — SAFE-17 lightweight controller-path git-diff boundary assertion (vs v1.52 anchor)
- [x] 238-02-PLAN.md — Both-WAN read-only fping-egress proof script (PROV-03; operator-run on live host)
- [x] 238-03-PLAN.md — PROVENANCE-MAP.md evidence artifact + A/B recommendation with operator-ratification slot (PROV-01, PROV-02)
- [x] 238-04-PLAN.md — PROV-03 gap closure: corrected host-route criterion, fresh passing egress evidence, and SAFE-17 refresh

### Phase 239: Seam Refactor + IcmplibBackend (Byte-Identical)
**Goal**: A single `RttBackend` abstraction exists with the existing icmplib measurement refactored behind it, provably behavior-identical to the pre-refactor default so any later regression is unambiguously attributable to a backend, not the seam.
**Depends on**: Phase 238
**Requirements**: SEAM-01, SEAM-02, SEAM-03, SEAM-04, SAFE-17
**Success Criteria** (what must be TRUE):
  1. A single `RttBackend` Protocol is consumed by both steering and autorate, with the existing icmplib path refactored behind it (no second silo introduced).
  2. icmplib-default RTT behavior is byte-identical to pre-refactor, proven by the hot-path test slice plus snapshot equivalence.
  3. RTT samples carry backend / source-IP / loss metadata (`RttSample` as a strict superset of `RTTSnapshot`) without breaking `WANController.measure_rtt()`, the scorer, or other existing consumers.
  4. The abstraction is shaped to absorb the existing IRTT path (adapter seam present), with full IRTT migration explicitly deferred.
  5. The narrowed SAFE-17 allowlist is defined and the fail-closed source-diff verifier runs at the phase boundary, proving no out-of-allowlist controller-path drift.
**Plans**: 3 plans
  - [x] 239-01-PLAN.md — RttBackend Protocol + RttSample superset + IRTT adapter stub (SEAM-01/03/04) with unit tests
  - [x] 239-02-PLAN.md — Additive RTTMeasurement.probe() returning RttSample; byte-identity via hot-path slice (SEAM-01/02)
  - [x] 239-03-PLAN.md — Fail-closed SAFE-17 v1.53 allowlist verifier + phase-boundary evidence (SAFE-17)

### Phase 240: Config + Validator
**Goal**: An operator can select the RTT backend per WAN/consumer in YAML, with safe defaults and validation, and every existing deployment config keeps validating with no migration.
**Depends on**: Phase 239
**Requirements**: CFG-01, CFG-02, CFG-03, SAFE-17
**Success Criteria** (what must be TRUE):
  1. Operator can set `measurement.backend: icmplib|fping` per WAN/consumer; an absent key resolves to `icmplib`.
  2. The config validator rejects unknown backend values and WARNs (does not fail) when `fping` is selected but the binary is absent.
  3. All existing deployment configs validate unchanged — no migration required.
  4. SAFE-17 boundary verifier passes (additive config/validator surface only; no controller-path drift).
**Plans**: 2 plans
  - [x] 240-01-PLAN.md — Shared measurement.backend validator + registry wiring in both validators + unit/CFG-03 tests (CFG-01/02/03)
  - [x] 240-02-PLAN.md — Phase 240 SAFE-17 boundary verifier (expanded allowlist clone of 239) + regression test (SAFE-17)

### Phase 241: fping Backend (Offline) + Reflector Quality
**Goal**: A selectable `fping` backend probes off the hot loop via one-shot subprocess bursts, binds the correct source IP, fans out across reflectors, parses real fping 5.1 output safely (loss never read as 0ms), survives subprocess stall/death, and feeds per-reflector loss into reflector-quality scoring — all proven offline against captured fixtures.
**Depends on**: Phase 239 (may overlap Phase 240)
**Requirements**: FPING-01, FPING-02, FPING-03, FPING-04, FPING-05, REFL-01, SAFE-17
**Success Criteria** (what must be TRUE):
  1. Operator can select an `fping` backend that probes via one-shot `subprocess.run` bursts on a background cadence, never on the synchronous 50ms control loop.
  2. The backend binds source IP per WAN via `-S` (matching `ping_source_ip`) and probes multiple reflectors in a single process, returning per-reflector results.
  3. The parser — built from captured real fping 5.1 samples — handles reply, total loss, partial loss, partial lines, banner, and process-death output; loss tokens map to "no sample" and are never recorded as `0ms`.
  4. The backend tolerates subprocess stall and death without crashing the daemon (bounded timeout, recover-and-continue), mirroring `irtt_measurement.py`.
  5. Per-reflector loss reported by fping feeds reflector-quality scoring (additive, gated to the fping backend) — the explicitly-accepted SAFE-17 reflector-scorer exception — with the boundary verifier confirming no other controller-path drift.
**Plans**: 4 plans
- [x] 241-01-PLAN.md — fping backend: FpingMeasurement.probe + loss-safe parser + FpingThread + REFL-01 loss→bool scorer feed + bootstrap fixtures (FPING-01..05, REFL-01)
- [x] 241-02-PLAN.md — SAFE-17 expanded-allowlist boundary verifier + mirror test + light fping sub-param validators (SAFE-17, FPING-01)
- [x] 241-03-PLAN.md — D-08 operator-run capture helper + real fping 5.1 fixtures + re-pointed parser/scorer tests (FPING-04, REFL-01)
- [x] 241-04-PLAN.md — [BLOCKING] SAFE-17 boundary gate: zero out-of-allowlist drift, byte-identical protected bodies (SAFE-17)
**UI hint**: no

### Phase 242: Backend Factory + Loud Fallback
**Goal**: A single factory centralizes backend construction for both consumers and falls back to icmplib automatically and loudly whenever fping is unavailable — never silently.
**Depends on**: Phase 240, Phase 241
**Requirements**: FALL-01, FALL-02, SAFE-17
**Success Criteria** (what must be TRUE):
  1. When the `fping` binary is unavailable, the backend factory falls back to `icmplib` automatically.
  2. Fallback is loud and observable (WARN-once + fallback counter + `/health` attribution), never silent.
  3. The factory is the single construction site used by `autorate_continuous.py` and (if Phase 238 routed it there) `steering/daemon.py`.
  4. SAFE-17 boundary verifier passes.
**Plans**: 4 plans
  - [x] 242-01-PLAN.md — Wave 0: FALL-01/FALL-02 factory tests + /health byte-preservation + SAFE-17 boundary verifier (clone of 241, expanded allowlist)
  - [x] 242-02-PLAN.md — build_rtt_backend() factory module: resolution + construction-time loud fallback + (backend, thread) bundle
  - [x] 242-03-PLAN.md — Collapse both call sites to the factory (+ steering source_ip, D-01a); thread additive /health fallback signal through the producer
  - [x] 242-04-PLAN.md — SAFE-17 boundary gate: zero out-of-allowlist drift + byte-identical protected bodies + full-suite/hot-path green
  - [x] 242-05-PLAN.md — Gap closure: preserve fping attribution, skip reflector scorer updates for fping background samples, and refresh SAFE-17 evidence

### Phase 243: Cycle-Budget Benchmark Gate
**Goal**: A pre-registered, committed-before-the-run benchmark proves fping introduces no 50ms cycle-budget regression under a real systemd unit, and acts as a hard gate that blocks the live A/B on regression.
**Depends on**: Phase 242
**Requirements**: BENCH-01, BENCH-02, SAFE-17
**Success Criteria** (what must be TRUE):
  1. Operator can run an idle-and-under-load cycle-budget + CPU benchmark of `fping` vs `icmplib` under a real systemd unit (not an interactive shell — TTY-vs-pipe is the STALL fingerprint).
  2. A pre-registered no-regression gate, committed before the run, blocks the live A/B if fping regresses cycle budget (vs `avg≈2.85ms` / `p99≈6.9ms` baseline), leaks file descriptors or zombies, or stalls under systemd.
  3. Benchmark evidence (cycle avg/p99 idle+load, CPU% delta, zombie/fd/Tasks counts over soak) is captured and the gate verdict is recorded.
  4. SAFE-17 boundary verifier passes.
**Plans**: 4 plans
- [ ] 243-01-PLAN.md — Pre-registration (frozen D-04 thresholds JSON + PREREGISTRATION.md) + empty-diff SAFE-17 verifier + mirror/prereg tests (BENCH-02, SAFE-17)
- [ ] 243-02-PLAN.md — Cycle-budget rollup (+ STALL gap detector) + fd/zombie/Tasks hygiene sampler + fixture unit tests (BENCH-01)
- [ ] 243-03-PLAN.md — Frozen-threshold gate evaluator (same-run delta + ceiling/hygiene/STALL/n-floor, fail-closed) + full pass/fail-mode matrix (BENCH-02)
- [ ] 243-04-PLAN.md — Bench-run launcher (throwaway journal-pipe unit, flent load, collision preflight) + operator runbook + operator-gated 8-arm live run → recorded verdict (BENCH-01, BENCH-02, SAFE-17)

### Phase 244: Health-Payload Attribution Metadata
**Goal**: Every RTT sample is attributable to a backend and source IP via `/health` before the A/B starts, with the existing health contract byte-preserved.
**Depends on**: Phase 242 (independent of Phase 243; both gate Phase 245)
**Requirements**: HEALTH-01, SAFE-17
**Success Criteria** (what must be TRUE):
  1. `/health` additively exposes `measurement.backend` and `source_ip` so every RTT sample is attributable during the A/B.
  2. The existing payload contract (`raw_rtt_ms`, `available`, `staleness_sec`) is byte-preserved.
  3. SAFE-17 boundary verifier passes (additive health surface only).
**Plans**: TBD

### Phase 245: Live A/B + Rollback Anchor
**Goal**: A pre-registered live A/B on the Phase-238-selected target produces a clean, attributable verdict — icmplib vs fping, one WAN under test with the other as control, under a Snapshot-A rollback anchor — against thresholds committed before any data is collected.
**Depends on**: Phase 243 (cycle-budget gate), Phase 244 (attribution metadata)
**Requirements**: AB-01, AB-02, AB-03, SAFE-17
**Success Criteria** (what must be TRUE):
  1. Operator runs a pre-registered live A/B (`icmplib` vs `fping`) on the Phase-238-selected target, one WAN under test with the other as control, under a Snapshot-A rollback anchor.
  2. The A/B supports concurrent / interleaved comparison within the same window to control diurnal confounding.
  3. The verdict is computed against thresholds committed before data collection (RTT agreement within tolerance, cycle-budget non-regression, loss-detection non-regression, minimum intended-backend cycle fraction, zero daemon restarts, steering-decision stability); "keep icmplib" is a valid passing close.
  4. `/health` attribution confirms the intended backend produced samples on the WAN under test during the A/B window.
  5. SAFE-17 boundary verifier passes.
**Plans**: TBD

### Phase 246: Conditional Default Flip + Milestone Closeout
**Goal**: The production default is flipped to fping under an armed rollback with recorded sign-off iff the A/B clearly wins; otherwise the milestone records a documented "stay on icmplib" recommendation — and SAFE-17 controller-path accounting is proven fresh at milestone close.
**Depends on**: Phase 245
**Requirements**: FLIP-01, SAFE-17
**Success Criteria** (what must be TRUE):
  1. If and only if the A/B clearly wins, the operator can flip the production default to `fping` under an armed rollback with sign-off recorded.
  2. If the A/B does not clearly win, the milestone records a documented "stay on icmplib" recommendation as a valid passing close (v1.46/v1.47 negative-result precedent); the flip is operator-gated, not automated.
  3. The SAFE-17 narrowed-allowlist source-diff verifier passes at milestone close, proving controller-path changes stayed within the RTT-measurement seam plus the accepted reflector-scorer touch, with no state-machine / threshold / EWMA / dwell / deadband / arbitration / fusion drift.
**Plans**: TBD

---

## Progress

**Execution Order:** Phases execute in numeric order: 238 → 239 → 240 → 241 → 242 → 243 → 244 → 245 → 246

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 238. RTT-Provenance Verification (Read-Only Entry Gate) | v1.53 | 3/4 | Gaps found | - |
| 239. Seam Refactor + IcmplibBackend (Byte-Identical) | v1.53 | 3/3 | Complete    | 2026-06-15 |
| 240. Config + Validator | v1.53 | 2/2 | Complete    | 2026-06-15 |
| 241. fping Backend (Offline) + Reflector Quality | v1.53 | 4/4 | Complete    | 2026-06-16 |
| 242. Backend Factory + Loud Fallback | v1.53 | 5/5 | Complete    | 2026-06-16 |
| 243. Cycle-Budget Benchmark Gate | v1.53 | 0/4 | Not started | - |
| 244. Health-Payload Attribution Metadata | v1.53 | 0/TBD | Not started | - |
| 245. Live A/B + Rollback Anchor | v1.53 | 0/TBD | Not started | - |
| 246. Conditional Default Flip + Milestone Closeout | v1.53 | 0/TBD | Not started | - |

---

## Phases (Archived Milestones)

<details>
<summary>✅ v1.52 Silicom Bypass Operationalization (Phases 235–237) — SHIPPED 2026-06-14</summary>

- [x] Phase 235: Bypass Operator CLI + Boot Baseline (4/4 plans) — completed 2026-06-12
- [x] Phase 236: Watchdog Fail-Open Two-Mode Reconciliation (2/2 plans) — completed 2026-06-12
- [x] Phase 237: HIL Failure-Injection Harness + Closeout (5/5 plans) — completed 2026-06-14

Full details: `milestones/v1.52-ROADMAP.md` · Requirements: `milestones/v1.52-REQUIREMENTS.md` · Audit: `milestones/v1.52-MILESTONE-AUDIT.md`

</details>

<details>
<summary>✅ v1.51 Post-Migration Consolidation (Phases 232–234) — SHIPPED 2026-06-12</summary>

- [x] Phase 232: Cleanup Boundary Guard + Tooling Fixes (4/4 plans) — completed 2026-06-11
- [x] Phase 233: Gated Repo Hygiene Sweep (4/4 plans) — completed 2026-06-11
- [x] Phase 234: Planning Metadata Reconciliation + Closeout (2/2 plans) — completed 2026-06-12

Full details: `milestones/v1.51-ROADMAP.md` · Phases: `milestones/v1.51-phases/`

</details>

<details>
<summary>✅ v1.50 cake-autorate Migration Hardening (Phases 229–231) — SHIPPED 2026-06-10</summary>

- [x] Phase 229: ATT Deploy Path + Artifact Tests (3/3 plans) — completed 2026-06-09
- [x] Phase 230: soak-monitor ATT Coverage (2/2 plans) — completed 2026-06-10
- [x] Phase 231: Migration-Held Criteria, Rollback Verification & Doc Sweep (3/3 plans) — completed 2026-06-10

Full details: `milestones/v1.50-ROADMAP.md` · Audit: `milestones/v1.50-MILESTONE-AUDIT.md`

</details>

---

## Backlog

### Parallel (event-gated)

- **Phase 218 (v1.45 VERIFY watch-list)** — dormant. The flapping peak-counter instrumentation lives in the native wanctl controller, which no longer runs Spectrum/ATT; this watch item stays dormant unless `wanctl@` returns to live duty or the check is reimplemented against bridge/cake-autorate telemetry.

### Deferred (post-v1.53 candidates)

- **ROLE-01 (native-controller retirement decision)** — time/event-gated; needs ≥14 consecutive stable cake-autorate days PLUS one exercised rollback drill (v1.52 HIL harness enables the drill). `WANCTL_CAKE_AUTORATE_FUTURE.md` "What not to delete yet" governs until then; BOUND-01 guard protects the surface.
- **TAIL-01 (Spectrum loaded-latency tail)** — NOT exhausted per 2026-06-10 Codex review; valid future evidence/investigation milestone, different shape.
- **SEED-007 (storage hygiene fire-on-change)** — must be reshaped for bridge writers (state bridges now own metrics-DB writes) and requires a consumer audit before any sparse-write change. Deferred as its own thesis.
- **SEED-005 (conservative UL tuning sweep)** — deferred not dead; native wanctl remains first-class on RouterOS deployments.
- **RECLAIM-04** — Spectrum upload reclaim re-attempt with a fundamentally different probe shape. Carried indefinitely after Phase 215 bounded VOID exhaustion; now a cake-autorate config question (`adjust_ul_shaper_rate=1`) under fixed-18M UL.

### Deferred from v1.53 (future RTT-backend work)

- **IRTT-MIG-01** — migrate the existing IRTT path to a first-class `IrttBackend` behind the seam (v1.53 only shapes the Protocol to absorb it via SEAM-04).
- **FPING-JSON-01** — adopt `fping -J` structured JSON once the schema stabilizes and lands in the Debian/Ubuntu deploy baseline (5.1 ships alpha-only `-J`; parse stable text in v1.53).
- **NATIVE-AB-01** — stand up native autorate to validate fping on the native control path (currently dormant; inherits the seam passively).
