# wanctl - Technical Context

Current project-specific operational context for local work.

## Core Runtime

`wanctl` is a production, long-running adaptive CAKE controller for MikroTik RouterOS with optional WAN steering.

Current assumptions:
- Python `>=3.11`
- Code installs to `/opt/wanctl`
- Config lives in `/etc/wanctl`
- State lives in `/var/lib/wanctl`
- Logs live in `/var/log/wanctl`
- Runtime files live in `/run/wanctl`
- Active systemd units are `wanctl@<wan>.service` and optional `steering.service`

## Router Access

### MikroTik Router

**Router:** RB5009 at `10.10.99.1`

**REST API:** preferred transport
- Host: `10.10.99.1`
- Port: `443`
- Password source: `/etc/wanctl/secrets` via `ROUTER_PASSWORD`

**SSH Access:** still supported
```bash
ssh -i ~/.ssh/mikrotik_cake admin@10.10.99.1
```

**Key Location:** `~/.ssh/mikrotik_cake`

## Active Operational Flow

Primary scripts:
- `scripts/install.sh`
- `scripts/deploy.sh`
- `scripts/install-systemd.sh`

Primary unit files:
- `deploy/systemd/wanctl@.service`
- `deploy/systemd/steering.service`

Legacy timer-era helper scripts in `scripts/` are intentionally stubbed and should not be used as active deployment guidance.

## Development Commands

```bash
.venv/bin/pytest tests/ -v
.venv/bin/ruff check src/ tests/
.venv/bin/mypy src/wanctl/
.venv/bin/ruff format src/ tests/
```

Focused hot-path regression slice:

```bash
.venv/bin/pytest -o addopts='' tests/test_cake_signal.py tests/test_queue_controller.py tests/test_wan_controller.py tests/test_health_check.py -q
```

## Useful Operational Checks

```bash
./scripts/soak-monitor.sh
ssh <host> 'journalctl -u wanctl@<wan> -f'
ssh <host> 'curl -s http://127.0.0.1:9101/health | python3 -m json.tool'
```

## Change Constraints

- Change conservatively; this is production network-control software.
- Do not alter control logic, thresholds, timing, or safety bounds without explicit approval.
- Keep the controller link-agnostic; deployment-specific behavior belongs in YAML.
- Keep docs and scripts aligned with the current service-based deployment model.

## Current References

Use these as the primary current docs:
- `README.md`
- `CLAUDE.md`
- `AGENTS.md`
- `docs/GETTING-STARTED.md`
- `docs/CONFIGURATION.md`
- `docs/DEPLOYMENT.md`
- `docs/TESTING.md`
- `docs/STEERING.md`
- `docs/SILICOM-BYPASS.md`

## Current Hardware Mapping

- `cake-shaper` uses the Silicom `PE2G4BPI35A-SD REV:1.1` passthrough NIC for both inline WAN pairs.
- ATT uses `att-modem` / `att-router`.
- Spectrum uses `spec-modem` / `spec-router`; these names now refer to the Silicom ports, while the old Supermicro ports are `old-spec-modem` / `old-spec-router`.
- The Silicom card supports powered bypass, but verified unpowered fail-open does not work on `odin`; do not rely on it for chassis-power-loss continuity.

## Current Validation Note

- v1.49 Phase 226 Plan 01 adds `scripts/phase226-baseline-capture.sh` as a read-only 3-run Spectrum baseline wrapper for `920/18 besteffort wash`: dry-run performs local prereq/default checks without creating evidence; live runs are off-peak gated and capture before/during/after `tc -s qdisc` for `spec-router`/`spec-modem`, continuous `/health` NDJSON, RRUL flent artifacts, concurrent unmarked UDP/TCP reference-flow summaries, DSCP-neutrality proof, validity/retained manifest fields, and required-artifact assertions. It must not deploy, restart services, change CAKE mode, mutate `tc`/`nft`, write `/etc/wanctl`, or reference controller-path source.
- v1.49 Phase 226 Plan 01 live baseline evidence is committed under `.planning/phases/226-baseline-capture-threshold-lock-snapshot-a/evidence/baseline/baseline-20260604T113435Z/`: the retained forced-window run used `vultr-chicago` after objective invalid `dallas` run-sets were discarded for netperf errors and recorded in the retained manifest. The wrapper normalizes Flent's timestamped raw RRUL data into stable per-run `flent-rrul.NN.flent.gz` artifacts and records console summaries for validity review.
- v1.49 Phase 226 Plan 01 completion metadata lives in `226-01-SUMMARY.md`; AB-02 is marked complete while GATE-01 remains pending for the threshold-lock plan.
- v1.49 Phase 226 Plan 01 also adds `scripts/phase226-baseline-summary.py`, a stdlib parser/summary helper for the baseline evidence tree. It computes CAKE tin packet/drop/backlog values as per-run `during - before` DELTAS with `after - before` cross-checks, derives `baseline_window` restart/transition/floor-hit/SOFT_RED dwell figures from continuous `health.window.ndjson`, and emits `tin_queue_delay_spread_ms` plus RRUL p99 headline fields in `baseline-summary.json` and `BASELINE-SUMMARY.md` for Phase 227/228 reuse.
- v1.49 Phase 226 Plan 01 parser coverage lives in `tests/phase226/test_tc_qdisc_parser.py` with fixtures under `tests/phase226/fixtures/`. The regression guard asserts CAKE tin packet counters are parsed from the packet field and reported as `during - before` deltas, not raw cumulative values, and checks continuous health-window restart/transition/floor-hit/SOFT_RED dwell derivation.
- v1.49 Phase 226 Plan 02 adds `scripts/phase226-snapshot-a.sh` as a read-only Spectrum CAKE Snapshot A wrapper: it captures redacted repo/deployed `spectrum.yaml`, `tc -s qdisc` for `spec-router`/`spec-modem`, live/repo `bridge qos` nft evidence, Spectrum `/health`, pre-deploy git refs, and writes unredacted `deployed-spectrum.yaml` restore source mode 0600 under an operator-private `--raw-dir` outside the git tree. It must not deploy, restart services, change CAKE mode, mutate `tc`/`nft`, write `/etc/wanctl`, or reference controller-path source. The committed Snapshot A evidence and `226-02-SUMMARY.md` live under `.planning/phases/226-baseline-capture-threshold-lock-snapshot-a/`; raw restore bytes stay outside the repo.
- v1.49 Phase 226 Plan 03 adds `scripts/phase226-thresholds.json` as the GATE-01 single-source-of-truth threshold artifact and `.planning/phases/226-baseline-capture-threshold-lock-snapshot-a/GATE-01-THRESHOLDS.md` as the public-safe provenance record. The JSON inherits the Phase 206 rollback gate keys, adds UL-stability and tin-separation machine-readable objects, freezes the tin-separation magnitude rule before Phase 227, and fills only the baseline-derived noise-band constant from `baseline-20260604T113435Z/baseline-summary.json`; this is a scripts/planning artifact only and must not deploy, restart services, change CAKE mode, mutate `tc`/`nft`, write `/etc/wanctl`, or reference controller-path source.
- v1.49 Phase 226 Plan 03 completion metadata is `226-03-SUMMARY.md`; GATE-01 is now marked complete, and Phase 226 should continue with Plan 04 dry-run restore proof plus SAFE-13 boundary verification before any Phase 227 candidate deploy.
- v1.49 Phase 226 Plan 04 adds `scripts/phase226-restore.sh` as a dry-run-only Snapshot A restore proof wrapper. It compares the operator-private raw `deployed-spectrum.yaml` against repo and read-only deployed Spectrum config SHA-256 values, writes `evidence/restore-proof/restore-{dry-run,equivalence}.*`, and asserts the printed Phase 228 rollback command matches the Snapshot A manifest. It refuses non-dry-run execution and does not deploy, restart services, change CAKE mode, mutate `tc`/`nft`, write `/etc/wanctl`, or touch controller-path source. SAFE-13 boundary evidence for Phase 226 lives in `evidence/safe13-boundary-check.json`.
- v1.49 Phase 226 post-execution code review (`226-REVIEW.md`) found five warning-level follow-ups: real CAKE row parsing coverage, zero-value numeric validation, stricter SSH/iface input allowlists, and explicit health JSON redaction. These are advisory review findings pending fix/triage.
- v1.48 Phase 223 Plan 01 builds an offline steering replay harness under `tests/integration/steering_replay/` with a FULL I/O SEAL: `FakeRouterTransport`, `FakeCakeReader`, `FixtureBaselineLoader`, tempdir state files, pytest urlopen/socket seals, and evidence artifacts under `.planning/phases/223-staging-proof-clean-restart-reproduction/evidence/`. It must not touch production router/state paths or controller-path source protected by SAFE-12.
- v1.48 Phase 223 Plan 02 adds the `clean-restart-degraded` PROOF-02 fixture for the folded `2026-04-17-investigate-steering-degraded-on-clean-restart` todo: persisted `SPECTRUM_DEGRADED`, `good_count: 0`, canonical autorate baseline shape, pre-enabled fake steering rule, and observation-mode cycles that classify effective steering during the recovery window without landing a steering-source fix.
- v1.48 Phase 223 Plan 03 writes PROOF-03 `spine-evidence.json` and `.md` from Plan 01/02 replay evidence only. Verdicts are per-fixture across binary on/off, daemon-side new-only surrogate, autorate-baseline authority, and separate restart-persistence; `clean-restart-degraded` remains a Phase 224 blocker unless a fix lands or the operator accepts risk.
- v1.48 Phase 223 Plan 03 also writes SAFE-12 `safe12-boundary-check.json` and `.md` using the Phase 222 schema (`allowlist_paths`, `dirty_tree.status_porcelain`) against v1.47 close `bee343b0c2f16207101aec82007a5e55fa9b6407`; controller-path committed, staged, unstaged, untracked, and porcelain checks pass with zero diff.
- v1.48 Phase 223 Plan 03 summary (`223-03-SUMMARY.md`) completes Phase 223 and updates STATE/ROADMAP/REQUIREMENTS. SAFE-12 is clear, but Phase 224 should treat clean-restart restart-persistence as blocked unless a fix lands or the operator explicitly accepts the risk.
- v1.48 Phase 223 Plan 04 repairs post-verification replay evidence gaps: `fixture_paths()` now includes `clean-restart-degraded` by default for operator `replay_harness.py --all` regeneration, while pytest corpus tests explicitly pass `include_clean_restart=False` for the non-clean corpus checks.
- Phase 223 Plan 04 reclassifies replay harness `spectrum_state_write_attempted` as daemon-side detection only: the harness seeds `spectrum_state.json`, fingerprints it with stat fields plus SHA-256 around `SteeringDaemon.run_cycle()`, and does not count harness-side seeding as a daemon write.
- Phase 223 Plan 04 closes clean-restart review warnings: the fixture observation target is `cycle_1_observed_state`, and `test_clean_restart_outcome_is_documented` generates fresh evidence with `run_fixture()` / `_build_evidence()` instead of reading committed evidence.
- Phase 223 Plan 04 adds `.planning/decisions/phase-224-clean-restart-risk-acceptance.md` as the concrete Phase 224 risk-acceptance artifact for the bounded clean-restart steering window; `spine-evidence.md` should link to this artifact as the closure mechanism.
- Phase 223 Plan 04 regenerates `replay-results.{json,md}`, `clean-restart-reproduction.{json,md}`, and `spine-evidence.{json,md}` end-to-end. Invariant 3 now preserves for all replay fixtures; the only remaining corpus break is `clean-restart-degraded.restart_persistence_verdict == breaks`, closed for Phase 224 entry by the risk-acceptance artifact.
- Phase 223 Plan 04 SAFE-12 re-check extends the allowlist verification to `src/wanctl/steering/` with `steering_daemon_clean: true`; controller-path and steering-daemon source remain byte-identical to v1.47 close.
- Phase 223 Plan 04 summary is `223-04-SUMMARY.md`; it closes the Phase 223 verification gaps and records Phase 224 readiness under the risk-acceptance default disposition.
- Phase 223 post-execution code review (`223-REVIEW.md`) found two warning-level replay reliability follow-ups: confidence-mode fixtures can skip expected-decision checks, and `build_replay_config()` is repo-CWD-dependent for operator-runnable harness use.
- Phase 223 verification now passes (`223-VERIFICATION.md`, 11/11 must-haves): PROOF-01/02/03 and SAFE-12 are satisfied, previous verification gaps are closed, and the two review warnings are advisory follow-ups rather than blockers.
- PROJECT.md now routes v1.48 from completed Phase 223 to Phase 224 production canary + rollback discipline, with the clean-restart risk-acceptance artifact as the default entry disposition.
- `tests/integration/steering_replay/test_clean_restart.py` writes PROOF-02 `clean-restart-reproduction.json` and `.md`; the default pre-enabled-rule fixture currently classifies as `reproduced-bug` because effective steering remains true through cycles 0–13 before recovery disables steering at cycle 14. The report names the fix scope but intentionally does not land a steering-source fix in Phase 223 Plan 02.
- Clean-restart evidence normalizes pytest tempdir baseline paths to `staging-workspace/clean-restart-degraded/spectrum_state.json` so rerunning `test_clean_restart.py` does not create path-only evidence churn.
- Plan 02 integrates the clean-restart result into `evidence/replay-results.{json,md}` with `verdict: observe` and appends a `PROOF-02 Closure (Phase 223)` block to the folded clean-restart todo; the todo stays in `.planning/todos/pending/` until a separate operator archival decision.
- Phase 223 Plan 02 summary is `223-02-SUMMARY.md`; PROOF-02 is now marked complete, and Phase 223 should continue with Plan 03 for spine evidence / SAFE-12 boundary verification before any Phase 224 canary decision.
- Phase 223 replay fixtures live under `tests/integration/steering_replay/fixtures/` and use an explicit schema with `harness_mode`, `cycle_budget_derivation`, split `pre_state.steering_pre_state` / `pre_state.autorate_state_by_cycle`, and corpus-source provenance. Confidence fixtures derive cycle counts from `configs/steering.yaml` against the 0.05s steering interval.
- `tests/integration/steering_replay/replay_harness.py --all` writes PROOF-01 `replay-results.json` and `replay-results.md` into the Phase 223 evidence directory. The pytest corpus asserts fixture verdicts, no production-path leakage, full I/O seal coverage, and the confidence-mode cycle-budget gate.
- Replay fake interaction timestamps and persisted transition timestamps are normalized per cycle so regenerating `replay-results.json` does not create timestamp-only evidence churn.
- Phase 223 Plan 01 summary is `223-01-SUMMARY.md`; PROOF-01 is now marked complete and Phase 223 should continue with Plan 02 clean-restart reproduction.
- v1.47 Phase 221 Plan 04 closes the folded `tcp_12down` todo by moving it from `.planning/todos/pending/` to `.planning/todos/closed/`, appending the post-D-10 verdict and CRITERIA-02 close-with-prejudice stanza, then backfilling `221-CLOSEOUT.md` with the todo-move commit SHA. Its final summary/state/roadmap/requirements update is planning metadata only and does not change controller, threshold, CAKE, steering, RouterOS, Phase 220 harness/script/YAML, deployment, or active docs behavior.
- v1.47 Phase 221 Plan 03 writes the read-only matrix closeout artifacts only: `221-CLOSEOUT.json` is the Phase 220 aggregator output amended with D-10 BGP-overlay fields, and `221-CLOSEOUT.md` mirrors `final_verdict_after_bgp_overlay` while preserving raw `matrix_verdict` for audit. No controller, threshold, CAKE, steering, RouterOS, Phase 220 harness/script/YAML, deployment, or active docs behavior changes are part of this closeout.
- v1.47 Phase 221 Plan 03 metadata updates mark CLOSEOUT-01/CLOSEOUT-02 and SAFE-11 status only; folded todo closure remains Plan 04 and `closeout_commit_for_todo` stays `PENDING_PLAN_04_COMMIT` until that move is committed.
- v1.47 Phase 221 Wave 0 adds `tests/test_phase221_mutation_boundary.py` as the SAFE-11 closeout guard: Phase 221 anchors to the `docs(phase-221): begin phase execution` marker, freezes Phase 220 scripts, and keeps the Phase 221 script allowlist empty while the evidence ledger/closeout artifacts evolve under `.planning/phases/221-matrix-evidence-closeout-scope-a2/`.
- v1.47 Phase 221 Plan 02 reconciled the operator-run Phase 220 evidence ledger to 54/54 deduplicated valid replicates, latched Plan 03 readiness (`canonical_complete: 6`, `supplemental_incomplete: 0`), and intentionally left aggregation/reporting to Plan 03.
- v1.47 Phase 221 Plan 01 completed the Wave 0 closeout metadata: `221-01-SUMMARY.md` records the marker/test/ledger commits, and `ROADMAP.md` / `STATE.md` now advance Phase 221 to Plan 02 of 4.
- v1.46 Internet Quality Recovery is the active milestone. v1.45 shipped with VERIFY-01 explicitly deferred under D-04(b): Spectrum and ATT are running `1.45.0` healthy after Phase 211, but natural flapping evidence (`details.peak_transition_count > 30`) remains on the retained watch list for Phase 218-style closure.
- v1.46 Phase 212 context is captured as a read-only production inventory/drift audit: classify live Spectrum/ATT/steering drift before tuning, redact sensitive config values in artifacts, and avoid production mutation unless an explicit operator approval gate is added later.
- v1.46 Phase 214 Plan 01 adds `scripts/phase214-flent-matrix.sh`: a read-only Spectrum `tcp_12down` wrapper over Phase 213 capture with off-peak/daytime/prime-time dry-run gates, `PHASE214_BASE_SHA` `src/wanctl/` mutation refusal, per-test `journal-window.ndjson`, and per-test `phase214-window.json` provenance sidecars. It does not change controller code or production config.
- v1.46 Phase 212 research/validation frames the audit as capture → redact → compare → classify → report, with artifact review as the primary gate unless reusable helper code is added.
- v1.46 Phase 212 is planned as three read-only waves: capture redacted production evidence from `cake-shaper`, compare/classify drift, then write the operator report and source-coverage closeout; plans passed GSD checker after D-01..D-13 citation coverage.
- v1.46 Phase 212 execution is complete and verified: 3/3 plans, final report `212-REPORT.md`, verification `passed` 16/16, no production mutation, prior flapping regression slice `132 passed`.
- v1.43 Phase 204 Plan 204-04 is complete: `scripts/soak_summary_aggregate.py` now emits CALIB-03 dual watchdog blocks (`secondary_gate_legacy` for transition visibility and `secondary_gate_completed_window` as the D-14 successor gate), loading the approved p99/125 dwell-hold constants from `scripts/calib_02_threshold.json`. Deploy 2 is harness-only: no production binary/YAML change and `scripts/soak-capture.sh` is unchanged.
- v1.43 Phase 202 is complete and verified: additive completed-window suppression counters and per-cause suppression metrics are exposed through `/health`, `suppressions_per_min` remains the legacy live dwell-hold counter, SAFE-05 v1.43 pins are established, verification passed with no gaps (`202-VERIFICATION.md`), and security verification closed all 13 registered threats with `threats_open: 0` (`202-SECURITY.md`).
- v1.42 Phase 201 Plan 201-16 24h soak (`20260505T132736Z`) completed against v1.42.1 with remote NDJSON copied back from `cake-shaper`. The operator-approved D-19 primary gate passed (`floor_hit_cycles_total_delta_soak_window=0`), but the preserved D-14 secondary watchdog failed (`ul_hysteresis_suppression_rate_per_60s_mean=6.466842364880155` vs `<5.0`). Phase 201 remains `gaps_found`; next action needs operator choice between A5-style controlled reattempt and a v1.43+ follow-up.
- v1.42 Phase 201 Plan 201-10 Codex stop-time review is complete with `GO WITH FOLLOW-UPS` (see `201-10-CODEX-STOP-TIME-REVIEW.md` and `201-10-SUMMARY.md`): no HIGH findings block Plan 201-11 canary launch, but operators must ensure `PHASE201_LOCAL_YAML_OVERRIDE` is unset before deploy/canary, and v1.43+ should add `max_delay_delta_us` to public `/health.cake_signal.{download,upload}` serialization before relying on that field for replay-corpus fidelity.
- v1.42 Phase 201 Plan 201-08 is complete: `scripts/phase200-saturation-canary.sh` now fails closed unless Phase 201 runs explicitly set `PHASE201_DOCSIS_MODE=true` and `PHASE201_SETPOINT_MBPS=12`, while legacy A/B compatibility requires `PHASE201_LEGACY_MODE=true`; the canary also cross-checks DOCSIS/setpoint YAML, probes `/health.wans[0].upload.docsis_mode_active`, verifies remote python3+pyyaml, and gates verdicts on `floor_hit_cycles_total` counter deltas as the primary VALN-06 evidence path.
- v1.42 Phase 201 Plan 201-07 is complete: `scripts/deploy.sh` invokes the Spectrum-scoped predeploy gate before `/opt/wanctl` rsync, derives `REMOTE_SSH_TARGET` from `TARGET_HOST` and `REMOTE_YAML_PATH` from `/etc/wanctl/${WAN_NAME}.yaml` when unset, fails closed on gate errors, and skips ATT/non-Spectrum deploys without inspecting Spectrum YAML.
- v1.42 Phase 201 Plan 201-06 is complete: Spectrum repo YAML opts into DOCSIS upload mode with `setpoint_mbps: 12` as an explicit canary-validated assumption, v1.42.0 version surfaces are aligned, and CHANGELOG/CONFIGURATION document restart-required migration plus the fallback preference of 10 before 14 on setpoint-specific canary failure.
- v1.42 Phase 201 Plan 201-05 is complete: WANController pins restart-required DOCSIS keys and per-WAN `self.logger` INFO emission; `/health.wans[].upload` exposes six additive DOCSIS runtime fields via the HealthCheckHandler rate/hysteresis builder; VALN-06 remains open for Plan 201-11 live canary proof.
- v1.42 Phase 201 controller-core replay uses the archived Phase 200 Attempt 3 hold-last-expanded corpus as a safety diagnostic, not a synthetic VALN-06 proof. Plan 201-14 superseded the earlier 1003-floor-hit diagnostic with bounded-absolute RED decay; the replay now pins the post-fix zero-floor-hit invariant.
- v1.41 Phase 200 is active for per-direction upload RTT bloat thresholds. Plan 200-02 intentionally superseded the v1.40 SAFE-05 replay count pins for `warn_bloat` and `target_bloat` only, using the live post-Plan-01 `wan_controller.py` counts (`warn_bloat=12`, `target_bloat=14`) while preserving the seven non-UL count pins.
- Phase 196 Spectrum cake-primary documented B-leg exceptions were accepted for continuation, but the follow-up tcp_12down throughput check failed at 73.92243773827883 Mbps versus the 532 Mbps acceptance threshold; the A/B comparison remains blocked until passing throughput evidence exists.
- Spectrum Silicom remains on CAKE for normal operation: `spec-modem` upload at 28Mbit, `spec-router` download at 940Mbit, `rtt: "100ms"`, WAN-path reflectors, IRTT disabled provisionally. Gateway-only RTT and `rtt: "1s"` are diagnostic controls only.
- `deploy/systemd/wanctl@.service` must keep `/proc/net` visible because `tc` reads `/proc/net/psched` for HTB timing and burst accounting; do not reintroduce `ProcSubset=pid` while Linux shapers may use HTB.
- `upload_qdisc: "htb_fq_codel"` is an experimental escape hatch. Static tests looked promising, but managed Spectrum testing preserved `256Kb` burst yet still underperformed and drove upload to the 8Mbit floor, so HTB/fq_codel is not the live Spectrum mode.
