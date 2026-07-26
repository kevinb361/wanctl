# Requirements — wanctl

## v1.65 Historical & Operator-Tool Correctness

**Goal:** Preserve historical metric meaning and make operator tools reject incomplete or invalid evidence.

- [ ] **REM-013** — Downsampling preserves canonical label identity, including distinct CAKE tins, across raw, `1m`, `5m`, and `1h` rows without duplicate aggregation. (milestone: v1.65)
  Source: 2026-07-25 `ops-assess` ASSESS-008 at `63ad2ef6`. Proof: deterministic multi-tin and mixed labeled/unlabeled SQLite fixtures survive repeated maintenance with exact label identity.
- [ ] **REM-014** — Every supported history range returns continuous data from the finest available retention tiers without gaps or duplicate boundary rows. (milestone: v1.65)
  Source: 2026-07-25 `ops-assess` ASSESS-013 at `63ad2ef6`. Proof: endpoint/reader tests cross 15m, 6h, 1d, and 7d retention boundaries.
- [ ] **REM-015** — Dashboard history either consumes the complete requested result set or prominently reports that the result is partial; summaries never silently describe only the first page. (milestone: v1.65)
  Source: 2026-07-25 `ops-assess` ASSESS-014 at `63ad2ef6`. Proof: a response over 1,000 rows is fully paginated or deterministically rendered incomplete.
- [ ] **REM-016** — Benchmark grading and persistence require a valid positive latency baseline distinct from server reachability. (milestone: v1.65)
  Source: 2026-07-25 `ops-assess` ASSESS-015 at `63ad2ef6`. Proof: netperf success with both RTT methods unavailable blocks grading/storage while valid baselines retain current behavior.
- [ ] **REM-017** — Every calibration exit after temporary queue mutation attempts restoration of both queues, preserves the original failure, and reports any restoration disagreement. (milestone: v1.65)
  Source: 2026-07-25 `ops-assess` ASSESS-016 at `63ad2ef6`. Proof: injected upload-search exception and interrupt tests assert both reset attempts and failure precedence.

### SAFE-28 — Synthetic proof before data or network mutation

- [ ] **SAFE-28** — v1.65 closes using synthetic databases and mocked network/router boundaries; any production data repair, benchmark traffic, queue mutation, or calibration execution remains separately approval-gated with backup/rollback evidence. (milestone: v1.65)
  Proof: changed-path inventory plus independent close-out confirms no live/database mutation and verifies each REM regression plus full `make ci`.

---

## v1.64 Control-Path Correctness

**Goal:** Make portable native control and active steering obey their documented failure contracts under deterministic injected failures.

- [ ] **REM-005** — Failover bridges resolve health sources, state, and failure counters by configured WAN identity; arbitrary WAN names work without ISP-specific literals or cross-WAN accounting. (milestone: v1.64)
  Source: 2026-07-25 `ops-assess` ASSESS-003 at `63ad2ef6`. Proof: arbitrary-WAN tests cover independent endpoint selection, RED/GREEN transitions, failure counting, and recovery.
- [ ] **REM-006** — Retryable RouterOS REST connection failures exercise bounded retry and then SSH fallback under one explicit transport-failure contract. (milestone: v1.64)
  Source: 2026-07-25 `ops-assess` ASSESS-004 at `63ad2ef6`. Proof: a real `RouterOSREST` wrapped by `FailoverRouterClient` retries injected `RequestException` and performs exactly one fallback transition.
- [ ] **REM-007** — Queued/no-I/O rate handling leaves router connectivity unchanged, and failed pending-rate replay remains pending while reporting router failure; success is recorded only after confirmed contact. (milestone: v1.64)
  Source: 2026-07-25 `ops-assess` ASSESS-005 at `63ad2ef6`. Proof: direct unreachable-entry, false-return replay, exception replay, success replay, stale-discard, and watchdog-distinction tests.
- [ ] **REM-008** — Disabling CAKE immediately removes stale snapshots from arbitration, and re-enabling cold-starts counters, EWMAs, and refractory state. (milestone: v1.64)
  Source: 2026-07-25 `ops-assess` ASSESS-006 at `63ad2ef6`. Proof: disable-with-snapshot, disabled-arbitration, and re-enable-cold-start regressions.
- [ ] **REM-009** — First-class IRTT mode accepts a target distinct from ICMP reflectors, rejects total-loss/zero-received samples, and reports backend-aware one-target health without crashing or fabricating success. (milestone: v1.64)
  Source: 2026-07-25 `ops-assess` ASSESS-007 at `63ad2ef6`; supersedes deferred `IRTT-MIG-01`. Proof: controller-level tests cover distinct server, 100% loss, cold start, health rendering, and ICMP fallback.
- [ ] **REM-010** — Upload adaptive-response strategies consume upload evidence, and Hampel sigma adjustments demonstrably move outlier behavior toward the configured target without positive feedback. (milestone: v1.64)
  Source: 2026-07-25 `ops-assess` ASSESS-009 at `63ad2ef6`. Proof: divergent upload/download datasets plus high/low/oscillating detector replay converge within bounds and retain revert safety.
- [ ] **REM-011** — Concurrent RTT helper timeout parameters bound caller wall-clock time within a tested margin and clean up unfinished workers safely. (milestone: v1.64)
  Source: 2026-07-25 `ops-assess` ASSESS-012 at `63ad2ef6`. Proof: deliberately slow-worker tests enforce elapsed-time bounds and lifecycle cleanup.
- [ ] **REM-012** — A timed-out persistent SSH command closes both channel and client before the connection reference is discarded, while preserving bounded reconnect behavior. (milestone: v1.64)
  Source: 2026-07-25 `ops-assess` ASSESS-017 at `63ad2ef6`. Proof: timeout-path tests assert channel/client closure and one bounded reconnect path.

### SAFE-27 — Control-path remediation without implicit production change

- [ ] **SAFE-27** — v1.64 changes remain repo-only and preserve the documented 50ms loop, native/external mode boundary, rate/state-machine safety invariants, and active route ownership; any live proof or deployment is separately approval-gated with exact rollback. (milestone: v1.64)
  Proof: changed-path/safety-contract review, focused regressions, full `make ci`, and independent close-out addressing ASSESS-003..007/009/012/017.

---

## v1.63 Repository & Deployment Integrity

**Goal:** Restore a fail-closed public/private boundary and make supported installs reproducible, dependency-audited, and uniquely identifiable.

- [ ] **REM-001** — The public tracked tree contains only explicitly public-safe planning/configuration material, and required CI rejects a synthetic secret addition without modifying its baseline. (milestone: v1.63)
  Source: 2026-07-25 `ops-assess` ASSESS-001 at `63ad2ef6`. Proof: credential-safe tracked-tree/history inventory, explicit allowlist, private rotation disposition if needed, and synthetic fail-closed CI regression. History rewrite or credential rotation is not implied.
- [ ] **REM-002** — The frozen runtime dependency closure contains no known unwaived advisories, and supported RouterOS REST/SSH behavior remains compatible after the staged upgrade. (milestone: v1.63)
  Source: 2026-07-25 `ops-assess` ASSESS-002 at `63ad2ef6`. Proof: runtime-only dependency audit, focused transport tests, and full `make ci`; any unavoidable advisory has an explicit owner, scope, and revisit trigger.
- [ ] **REM-003** — Docker continuous/calibrate/steering/oneshot modes and the supported clean host installer resolve the same authoritative frozen runtime, start through the installed package surface, and fail nonzero when dependencies cannot be installed. (milestone: v1.63) (depends: REM-002)
  Source: 2026-07-25 `ops-assess` ASSESS-010 and ASSESS-018 at `63ad2ef6`. Proof: clean image/startup contracts for every mode plus clean host/container install and injected dependency-install failure.
- [ ] **REM-004** — Built artifacts and health/operator surfaces expose a consistent release identity plus immutable source revision so materially different runtimes cannot report the same build. (milestone: v1.63)
  Source: 2026-07-25 `ops-assess` ASSESS-011 at `63ad2ef6`. Proof: package/image metadata and health readback agree in a clean build and differ when the source revision differs.

### SAFE-26 — Fail-closed boundary and staged supply-chain repair

- [ ] **SAFE-26** — Secret inspection never emits credential values; destructive history rewrite, credential rotation, release publication, deployment, restart, or network mutation occurs only under separate explicit approval; dependency/install changes preserve Python 3.11+ and RouterOS REST/SSH compatibility. (milestone: v1.63)
  Proof: action ledger, changed-path review, synthetic boundary checks, compatibility tests, full `make ci`, and independent close-out.

---

## v1.62 QoS Validation & Trust Hardening

**Goal:** Add packet-level evidence and bounded hardening to the proven RouterOS-classifies / cake-shaper-enforces contract without retuning or broadening production scope.

- [x] **QVT-001** — A fresh read-only baseline proves the strict RouterOS QoS contract, live cake-shaper service/health posture, both-WAN CAKE continuity, and the exact nature of current bridge artifact drift. (milestone: v1.62)
  Evidence: `.planning/evidence/v1.62-baseline-20260719.md`; `../infra-ansible/artifacts/network-audits/20260719_211000-main-router-firewall-qos/qos-contract-audit.json`; `.planning/evidence/live-preflight/wanctl-live-preflight-20260719T210924Z.json`.
- [x] **QVT-002** — A bounded Spectrum proof demonstrates EF, AF31, CS1, and CS0 on the RouterOS-to-cake-shaper path and shows CAKE remains structurally healthy, with no saturation requirement. (milestone: v1.62)
  Evidence: `.planning/evidence/v1.62-qvt002-second-attempt-pass-20260719.md`; exact live artifacts under `.planning/evidence/qvt002-spectrum-20260719T220859Z/`.
- [x] **QVT-003** — The zero-hit IoT DSCP wash rule is explained by read-only path evidence or a separately approved single-probe test that proves wash/normalization; ambiguity is not recorded as pass. (milestone: v1.62)
  Evidence: `.planning/evidence/v1.62-qvt003-natural-canary-proof-20260720.md`; the exact source-subnet canary increased `1429/377172 → 1458/385374` over ten seconds of natural traffic while the untouched interface rule remained `0/0`, matching the earlier proven EF packet mismatch and bridge/trunk root-cause evidence. No re-proof packet was generated.
- [x] **QVT-004** — DSCP trust is either narrowed to explicit legitimate marking sources through an exact reversible change, or retained by an explicit evidence-backed risk acceptance; broad trust is not left accidental. (milestone: v1.62)
  Evidence: explicit operator LOW-risk acceptance on 2026-07-20; `.planning/evidence/v1.62-qvt004-dscp-trust-analysis-20260720.md`; `.planning/evidence/v1.62-qvt004-ephemeral-v5-observation-20260720.md`. Broad EF/AF4x trust is intentionally retained with no RouterOS rule change: bounded observation found legitimate EF sources, AF4x remained inconclusive, CAKE limits scheduling abuse, and strict/postflight audits stayed healthy.
- [x] **QVT-005** — Repository/live `bridge-qos.nft` drift is reconciled or formally classified with executable-rule parity mechanically proven; no executable nftables change may hide inside comment convergence. (milestone: v1.62)
  Evidence: `.planning/evidence/v1.62-qvt005-bridge-drift-disposition-20260720.md`; fresh repo/live executable lines are ordered-equal `55/55`, both files pass nft syntax, and loaded five-chain/41-rule semantics equal repo. Raw difference is comment-only and formally retained until the next justified executable deployment; no reload occurred.
- [x] **QVT-006** — Disabled `QOS_GAME_DL` output and its absent producer receive an evidence-backed keep/remove disposition; any removal is exact, reversible, and separately approved. (milestone: v1.62)
  Evidence: `.planning/evidence/v1.62-qvt006-game-dl-disposition-20260720.md`. Keep exact `*308` disabled: fresh live scan finds one consumer, zero producers, zero counters, and no script/scheduler references; disabled state has no traffic/audit overhead, while standalone deletion adds rollback risk with no runtime benefit. No removal occurred.

### SAFE-25 — Bounded production proof and hardening

- [x] **SAFE-25** — Every controlled packet-generation step and every RouterOS/nftables/service mutation uses a fresh baseline, explicit action-specific approval, deterministic acceptance, and exact rollback; CAKE rates, autorate thresholds, routing/steering, NAT, firewall policy, topology, and saturation are unchanged. (milestone: v1.62)
  Evidence: `.planning/evidence/v1.62-safe25-invariant-20260720.md`; complete action ledger covers both QVT-002 packet attempts, QVT-003 failed packet and additive canary, all QVT-004 blocked/ephemeral attempts, retained failures, exact cleanup, no-retry/token rotation, risk acceptance, and declined nft/rule cleanup. Fresh strict audit PASS and wanctl `25/25`.

### Out of scope

- CAKE bandwidth/rate or controller-threshold tuning.
- Route ownership, WAN steering, NAT, firewall, VLAN, or topology changes.
- Broad load/saturation tests or clearing conntrack.
- Replacing the split-edge architecture or claiming per-LAN-host fairness.

---

## v1.61 QoS Classification Contract

**Goal:** Make RouterOS the authoritative host-aware classifier and route selector, make cake-shaper the authoritative CAKE enforcement point, and use a tested DSCP/conntrack contract between them without duplicating application policy.

- [x] **REQ-001** — An operator-facing contract documents ownership, trust boundaries, the EF/AF31/CS0/CS1 class map, rejected alternatives, and rollback behavior. (milestone: v1.61)
  Evidence: `docs/QOS_CLASSIFICATION_CONTRACT.md`, `.planning/decisions/2703-routeros-classifies-cake-enforces.md`.
- [x] **REQ-002** — RouterOS-originated AF31 packets on both WAN upload paths seed the bridge connection mark that restores replies into the CAKE Video tin. (milestone: v1.61)
  Evidence: `deploy/nftables/bridge-qos.nft`, `tests/test_bridge_qos_nft.py::test_router_dscp_classification_is_propagated_to_download_replies`, `make ci` 2026-07-17.
- [x] **REQ-003** — Both WAN paths apply the same four-class contract and unclassified traffic falls back to Best Effort; duplicate bridge application classifiers are removed only after equivalent contract coverage is proven. (milestone: v1.61)
  Evidence: exact symmetric import/restore and Best Effort fallback assertions in `tests/test_bridge_qos_nft.py`; the finite registry in `../infra-ansible/artifacts/network-changes/20260717_routeros-qos-composite-policy/generic_rtp_canary.py`; and the read-only audit in `../infra-ansible/scripts/routeros-qos-contract-audit.py`. Root-cause repair commit `21187c3` fixed catch-all semantics and fails closed if no catch-all exists. Generic RTP, WireGuard, SSH, UDP/3480, and NNTP are now active and mechanically audit-proven; fresh audit `20260718_180152-routeros-qos-contract` returned overall PASS with exact coverage at #15/#35/#36/#37/#38 before default #39. Generic RTP, WireGuard, and SSH have natural traffic proof; UDP/3480 and NNTP immediate counters are `0/0`, so natural proof is deferred without synthetic probes. Evidence: `../infra-ansible/artifacts/network-changes/20260717_routeros-qos-composite-policy/live-canary-result-wireguard-20260718T135914Z.md`, `../infra-ansible/artifacts/network-changes/20260717_routeros-qos-composite-policy/wireguard-natural-counter-proof-20260718T151235Z.md`, `../infra-ansible/artifacts/network-changes/20260717_routeros-qos-composite-policy/live-canary-result-ssh-20260718T155557Z.md`, `../infra-ansible/artifacts/network-changes/20260717_routeros-qos-composite-policy/live-canary-result-realtime-udp-3480-20260718T174527Z.md`, and `../infra-ansible/artifacts/network-changes/20260717_routeros-qos-composite-policy/live-canary-result-nntp-20260718T180241Z.md`. Application equivalence is proven. Spectrum and ATT bridge duplicate retirement are live-verified at final staged hash `e1063434...03d8`; bounded natural deltas moved all four tins on both WANs with zero new drops/backlog. Evidence: `../infra-ansible/artifacts/network-changes/20260717_routeros-qos-composite-policy/live-canary-result-spectrum-bridge-retirement-20260718T183654Z.md` and `../infra-ansible/artifacts/network-changes/20260717_routeros-qos-composite-policy/live-canary-result-att-bridge-retirement-20260718T190353Z.md`. The first approved AF31 convergence attempt reached exact target `a6b85d55...04884` and passed structural, audit, preflight, service, health, DNS, and HTTPS checks, but a natural 15-second observation found concurrent Spectrum Bulk saturation with `11,979` drops and `337,644` bytes ending backlog. Per the approved zero-drop/backlog acceptance, exact rollback restored healthy baseline `e1063434...03d8`; evidence: `../infra-ansible/artifacts/network-changes/20260717_routeros-qos-composite-policy/live-attempt-result-af31-convergence-rollback-20260718T201849Z.md`. A fresh independently reviewed v2 package added a mandatory three-window uncongested precondition and load-aware CAKE continuity while retaining exact rollback for structural, audit, service, health, DNS, HTTPS, or qdisc disagreement. The approved v2 reload reached and independently verified final live hash `a6b85d55...04884`, exact one-per-WAN AF31 imports, immutable baseline backup, RouterOS audit overall PASS, wanctl `25/25`, healthy service/endpoints, both resolvers, HTTPS, exact CAKE handles/`diffserv4`/four tins, monotonic counters, and zero ending backlog. Evidence: `../infra-ansible/artifacts/network-changes/20260717_routeros-qos-composite-policy/live-canary-result-af31-convergence-v2-20260718T220448Z.md`.
- [x] **REQ-004** — Adaptive WAN steering is selected independently from QoS priority, applies only to eligible new connections, and does not move recursive DNS merely because DNS is high priority. (milestone: v1.61)
  Evidence: `src/wanctl/steering/daemon.py::reconcile_steering_rule`, `tests/steering/test_steering_daemon.py`, `docs/QOS_CLASSIFICATION_CONTRACT.md`, and `../infra-ansible/artifacts/network-changes/20260717_routeros-qos-composite-policy/live-canary-result.txt`. The broad `QOS_HIGH` selector is retired; the exact Work-VPN/new-connection producer is controller-owned and DNS-safe.
- [x] **REQ-005** — The effective RouterOS QoS and steering policy has a version-controlled, read-only audit surface that detects ordering, FastTrack, DSCP-map, per-application equivalence, and steering-eligibility drift. (milestone: v1.61)
  Evidence: `../infra-ansible/scripts/routeros-qos-contract-audit.py`, `../infra-ansible/tests/test_routeros_qos_contract_audit.py`, `../infra-ansible/tests/test_routeros_qos_composite_policy.py`, live `make routeros-qos-contract-audit` 2026-07-17.
- [x] **REQ-006** — A reversible live canary under controlled bulk load proves DNS responsiveness, work-VPN reachability, expected CAKE tin counters, both-WAN behavior, and successful rollback. (milestone: v1.61)
  Evidence: `../infra-ansible/artifacts/network-changes/20260717_routeros-qos-composite-policy/live-canary-result.txt`. The corrected canary passed bounded both-WAN load, the real FortiVPN reconnect, DNS probes, expected CAKE counters, approval-gated demigration, and approval-gated remigration to the DNS-safe adaptive layout without clearing conntrack.

### SAFE-24 — Production QoS convergence

- [x] **SAFE-24** — Every production mutation requires a fresh exact rollback anchor and explicit operator approval; unrelated CAKE rates, autorate thresholds, route ownership, NAT, and topology changes remain out of scope. (milestone: v1.61)

- Repo-only docs, tests, audits, and undeployed rules are permitted without a live gate.
- RouterOS mangle, nftables deployment, qdisc changes, steering activation, service restarts, and controlled saturation are production mutations requiring an exact rollback anchor and explicit operator approval.
- CAKE rates, autorate thresholds, route ownership, NAT, and the split-edge topology are outside this milestone unless separately approved.

### Out of scope

- Moving NAT/routing to Linux or replacing the split edge with a DIY router.
- Claiming per-LAN-host CAKE fairness while NAT remains on a different host.
- Application-layer inspection or broad port-list expansion on cake-shaper.
- CAKE rate or controller-threshold tuning.

---
