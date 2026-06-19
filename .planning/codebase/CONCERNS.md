# Codebase Concerns

**Analysis Date:** 2026-06-19

## Tech Debt

**`wan_controller.py` god file:**
- Issue: `src/wanctl/wan_controller.py` is 4,776 lines — the largest file by a significant margin, containing the control state machine, flash wear protection, flapping detection, reflector scoring dispatch, maintenance scheduling, and state restoration. This makes incremental changes difficult to audit.
- Files: `src/wanctl/wan_controller.py`
- Impact: Every SAFE invariant check becomes a high-noise diff review. The SAFE-17/18 mutation-boundary scripts exist partly as compensation for this complexity.
- Fix approach: Slice into sub-modules (congestion state machine, rate application, maintenance, flapping detection). Deferred pending ROLE-01 native-controller retirement decision.

**IRTT backend is a dead stub:**
- Issue: `src/wanctl/rtt_backend.py` contains `IrttRttBackend` which unconditionally raises `NotImplementedError("IRTT-MIG-01")`. The class is present in the public module and importable, but provides no functionality.
- Files: `src/wanctl/rtt_backend.py:94-99`
- Impact: Misleads code readers about IRTT integration being available. Any path that constructs `IrttRttBackend` will fail at runtime.
- Fix approach: Either remove the stub and block the migration explicitly in planning docs, or implement `IRTT-MIG-01`. Currently deferred with no milestone assignment.

**fping/reflector scorer attribution is deferred:**
- Issue: In fping backend mode, `wan_controller.py` skips reflector scorer updates when the backend is `fping` (`skip_scorer_for_backend = snapshot_backend == "fping"`, line 1201). fping packet-loss data is captured but not fed into reflector quality scoring.
- Files: `src/wanctl/wan_controller.py:1201-1208`
- Impact: Reflector quality degrades silently if fping is used; bad reflectors are not demoted. Acknowledged deferred to a later "attribution phase."
- Fix approach: Wire fping per-host loss into `ReflectorScorer.record_results()` in the same per-cycle path. Gated on `FPING-PROFILE-01` evidence verdict from Phase 248.

**State bridge baseline RTT is bootstrap-only:**
- Issue: `deploy/scripts/cake-autorate-spectrum-state-bridge` reads `ewma.baseline_rtt` from the existing state file on startup via `old_rtt()`. If no state file exists, it falls back to `DEFAULT_BASELINE_RTT` (hardcoded in the systemd unit as `WANCTL_EXTERNAL_BASELINE_RTT=22.535852814520855` for Spectrum, `28.42043789020452` for ATT). The bridge does not parse `baseline_rtt` from cake-autorate log output — it only parses `dl_rate`, `ul_rate`, `dl_status`, and `ul_status` from `SUMMARY/LOAD` lines. The baseline persists in the state file between restarts, but if the state file is deleted or corrupted, the bridge bootstraps from the hardcoded deployment-time constant indefinitely.
- Files: `deploy/scripts/cake-autorate-spectrum-state-bridge:96-104`, `deploy/systemd/cake-autorate-spectrum-state-bridge.service:14`, `deploy/systemd/cake-autorate-att-state-bridge.service:14`
- Impact: After a state-file loss, steering delta calculations use a potentially stale bootstrap baseline until the state file is repopulated through normal operation (which only writes the value from the previous state file, so the staleness propagates). Low frequency risk; medium impact if triggered during a congestion event.
- Fix approach: Extract cake-autorate's EWMA baseline from the log when available, or add a periodic baseline refresh from the health endpoint `measurement.raw_rtt_ms`.

**`soft_red_streak`/`red_streak` always zero in state bridge:**
- Issue: The state bridge always writes `soft_red_streak: 0` and `red_streak: 0` to the state file (lines 202, 208). The bridge's `status_to_state()` only maps to `GREEN` or `YELLOW` — `SOFT_RED` and `RED` states are never emitted. `wan_controller.py` reads these streak fields for state restoration on startup (lines 4718-4727).
- Files: `deploy/scripts/cake-autorate-spectrum-state-bridge:182-188`, `src/wanctl/wan_controller.py:4718-4727`
- Impact: Under cake-autorate mode the native `wanctl@` controller is not active, so `wan_controller.py` does not consume this state. Risk becomes relevant only if there is a rollback from cake-autorate to native wanctl@ mode — the state would show no accumulated streak state.
- Fix approach: Document explicitly in `WANCTL_CAKE_AUTORATE_FUTURE.md` that streak state is reset on rollback to native mode.

**~34 stale SAFE-17 mutation-boundary tests in `pytest` suite:**
- Issue: Per-phase SAFE-17 verifier tests (`test_phaseNNN_safe17_verifier.py`, `*_mutation_boundary.py`, `*_safe13_boundary.py`) are point-in-time gates pinned to their phase's close commit. Later phases that legitimately touch the protected files cause earlier verifier tests to go red against `HEAD`. The full `pytest tests/` run carries approximately 34 pre-existing stale-boundary/topology failures from phases 220/221/227/231 and ATT soak tests.
- Files: `tests/test_phase2*.py` (all SAFE/mutation-boundary verifiers)
- Impact: `pytest tests/` is misleading — the failures are structural, not regressions. Engineers (or agents) running full pytest need to know this is expected.
- Fix approach: The authoritative test slice is `pytest -o addopts='' tests/test_cake_signal.py tests/test_queue_controller.py tests/test_wan_controller.py tests/test_health_check.py` plus the current-phase SAFE verifier. Older phase verifiers should be skipped or moved to an `archive/` subdirectory.

**SEED-007 storage write volume unquantified per-metric:**
- Issue: GAUGE-01 (Phase 249) requires auditing per-metric write rates to identify flat-emitting gauges. Only `wanctl_steering_enabled` has had fire-on-change applied so far (saving ~172k rows/day). Other candidate flat gauges are not yet audited.
- Files: `src/wanctl/steering/daemon.py:2265-2279`, `src/wanctl/metrics.py`
- Impact: Metrics SQLite DBs accumulate redundant rows at 2Hz for gauges that never change, growing storage pressure over time.
- Fix approach: Run `wanctl-history --ingestion-rate --wan spectrum` (and ATT) against the live DB; apply fire-on-change to confirmed flat candidates one per canary cycle (GAUGE-01, GAUGE-02, GAUGE-03 in v1.54 Phase 249).

## Known Bugs

**`peak_transition_count` alert metric implementation unverified post-fix:**
- Symptoms: All pre-fix production `flapping_dl`/`flapping_ul` alert rows showed `transition_count=30, peak_transition_count=30`. The fix (separate `_dl_peak_window_transitions` / `_ul_peak_window_transitions` deques, independent of the fire window) has shipped, but no qualifying production DOCSIS flapping event has occurred to confirm `peak > 30` in practice.
- Files: `src/wanctl/wan_controller.py:753-754, 4337, 4346-4349, 4358, 4371, 4380-4383, 4392`
- Trigger: Requires a real Spectrum or ATT DOCSIS oscillation event with more than 30 transitions in the `flap_window` interval.
- Workaround: Alert still fires correctly; only the `peak_transition_count` diagnostic field has unverified post-fix semantics.
- Status: Fix shipped. Pending validation via next qualifying DOCSIS event. Todo: `.planning/todos/pending/2026-04-17-monitor-flapping-peak-count-on-next-docsis-event.md`.

**Steering daemon loads persisted DEGRADED state on restart:**
- Symptoms: On steering daemon restart, if the previous run ended in `SPECTRUM_DEGRADED` state, `SteeringStateManager.load()` restores that state from `steering_state.json`. The daemon effectively keeps traffic steered for new latency-sensitive connections for ~15 cycles (~0.75 seconds at 50ms intervals) until fresh autorate measurements override the state.
- Files: `src/wanctl/steering/daemon.py`, `src/wanctl/state_manager.py`, `/var/lib/wanctl/steering_state.json`
- Trigger: Any daemon restart while `SPECTRUM_DEGRADED` is persisted to state file.
- Workaround: Risk-accepted at Phase 224 (`decisions/phase-224-clean-restart-risk-acceptance.md`). Recovery window is ~0.75s. No in-code fix has shipped.
- Status: Reproduced (Phase 223 PROOF-02), risk-accepted, unfixed. Not regressed.

## Security Considerations

**SSL verification disabled in all deployed configs:**
- Risk: RouterOS REST API connections use self-signed certificates. All production configs and all example configs set `verify_ssl: false`. Connections are MITM-able on the management network.
- Files: `configs/spectrum.yaml:30`, `configs/att.yaml:31`, `configs/steering.yaml:24`, `configs/examples/*.yaml`, `src/wanctl/routeros_rest.py:79-99`
- Current mitigation: RouterOS REST runs on a dedicated management VLAN with no public exposure. The password is passed via `${ROUTER_PASSWORD}` env var from `/etc/wanctl/secrets`, not in config files.
- Recommendations: Import the RouterOS self-signed CA and enable verification, or use SSH transport instead of REST where feasible.

**Health endpoint consumed over unencrypted LAN HTTP:**
- Risk: `steering/daemon.py` reads live RTT and WAN zone from the autorate health endpoint over plain `http://` (line 222). In cake-autorate mode, the bridge health servers bind to LAN IPs (`10.10.110.223:9101`, `10.10.110.227:9101`). An attacker on the management VLAN could inject a crafted health payload to alter baseline RTT or WAN zone seen by steering. The C4 fix bounds baseline RTT to 10-60ms (`daemon.py:978-988`), limiting the RTT injection window, but zone spoofing (GREEN/YELLOW) is unconstrained.
- Files: `src/wanctl/steering/daemon.py:203-222, 1044-1055`, `deploy/systemd/cake-autorate-spectrum-state-bridge.service:15`
- Current mitigation: C4 bounds baseline_rtt. Traffic is on an internal management VLAN. Health server is not internet-exposed.
- Recommendations: Bind health servers to loopback only and access via local socket, or add HMAC verification to health payloads.

## Performance Bottlenecks

**50ms cycle budget shared across RTT probe, CAKE stats, router apply, and state I/O:**
- Problem: The production 50ms (20Hz) cycle must complete RTT measurement, CAKE queue stats collection, congestion state update, rate calculation, conditional router API call, and SQLite write within budget. A cycle overrun of more than a few ms causes control loop jitter.
- Files: `src/wanctl/autorate_continuous.py`, `src/wanctl/wan_controller.py`
- Cause: Each subsystem uses `PerfTimer`; the deferred I/O worker (`DeferredIOWorker`) offloads SQLite writes; router API calls are the highest-latency step and are coalesced via flash wear protection. Profiling baseline: 71,560 timing samples captured in Phase 217.
- Improvement path: fping background thread (`FpingThread`) moves RTT probing off the hot path. Phase 248 is analyzing the actual fping p99 cycle contribution from Phase 247 shadow soak data.

**Metrics DB write rate unquantified (GAUGE-01 pending):**
- Problem: Without per-metric ingestion rate data, it is unknown how many rows/day are useful vs redundant flat-gauge emissions. `steering_enabled` alone was emitting ~172k rows/day before the fire-on-change fix.
- Files: `src/wanctl/steering/daemon.py:2265`, `src/wanctl/metrics.py`
- Cause: Most metrics are emitted at every cycle (2Hz) regardless of value changes.
- Improvement path: Phase 249 (GAUGE-01, GAUGE-02, GAUGE-03) will audit write rates and apply fire-on-change to confirmed flat-emitting gauges.

## Fragile Areas

**`SteeringDaemon` RTT source chain can silently shift under topology change:**
- Files: `src/wanctl/steering/daemon.py:1784-1816`, `src/wanctl/rtt_backend_factory.py`
- Why fragile: `SteeringDaemon.measure_current_rtt()` uses a three-tier fallback: (1) wanctl icmplib backend probe, (2) autorate health endpoint `measurement.raw_rtt_ms`, (3) autorate IRTT RTT. In current cake-autorate mode the icmplib probe runs successfully. If icmplib probes start failing silently (no loss events reported, just latency), the daemon silently degrades to the autorate health fallback without a clear operator signal unless `_rtt_source_counts` is inspected.
- Safe modification: Do not remove the probe exception counter (`_rtt_source_counts["probe_exception_count"]`). Do not change the fallback chain without re-reading Phase 242/245 provenance docs.
- Test coverage: `tests/test_rtt_measurement.py`, `tests/test_rtt_backend.py`

**Route ownership ambiguity between RouterOS Netwatch and wanctl/steering:**
- Files: `src/wanctl/steering/daemon.py`, `src/wanctl/routeros_client.py`, `docs/STEERING.md`
- Why fragile: RouterOS Netwatch (`Monitor-Spectrum`, `Monitor-ATT` entries) directly enables/disables WAN routes via `Enable-*` / `Disable-*` scripts. Netwatch scripts were repaired with narrower policy (`read,write,test`) on 2026-06-18 after a permission failure caused Netwatch to fire but not execute routes. If wanctl/steering ever grows route mutation capability while Netwatch remains active, both systems could fight over the same RouterOS routes causing route flapping.
- Safe modification: Any wanctl routing code must check for active Netwatch route-mutating entries before enabling route mutation. See `.planning/todos/pending/2026-06-18-route-ownership-netwatch-to-wanctl-failover.md` for ownership guard requirements.
- Test coverage: None — route ownership logic is not yet implemented.

**VERIFY-01/VERIFY-02 deferred event-gated requirements are dormant:**
- Files: `src/wanctl/wan_controller.py:4307-4398` (flapping logic), `src/wanctl/alert_engine.py`
- Why fragile: VERIFY-01 requires a natural production DOCSIS flapping event with `peak_transition_count > 30` to verify the windowed peak accumulator behavior. VERIFY-02 requires VERIFY-01 plus an ALERT-03 cooldown bucket audit. Phase 218 is dormant because the native wanctl@ controller is not live (cake-autorate mode) and the flapping instrumentation path runs through the native controller. If/when the native controller is re-enabled, these requirements become active blockers.
- Status: Deferred to Phase 218; listed in `.planning/STATE.md` Deferred Items.

**ATT cake-primary canary (VALN-05b) is unresolved:**
- Files: `.planning/todos/pending/2026-04-24-resolve-att-cake-primary-canary-after-phase-196.md`
- Why fragile: Phase 196 ATT canary was blocked on Phase 191 closure (ATT throughput regression). Phase 191 has not been formally closed. VALN-05 (queue-primary arbitration validation on ATT) remains in a `blocked` state. If ATT control behavior is investigated in future phases, this unresolved canary is a precondition.
- Safe modification: Do not treat ATT as having passed `cake-primary` signal validation without completing the Phase 191→196 closure sequence.

**`autorate_continuous.py` native controller is preserved but untested in production:**
- Files: `src/wanctl/autorate_continuous.py` (1,408 lines), `deploy/systemd/wanctl@.service`
- Why fragile: `wanctl@{wan}.service` has been disabled since 2026-06-08 (both WANs on cake-autorate). `autorate_continuous.py` is preserved per `WANCTL_CAKE_AUTORATE_FUTURE.md` "What not to delete yet" clause (ROLE-01 gate: ≥14 stable cake-autorate days + one exercised rollback drill required before retirement decision). Any bugs introduced to this file would not surface until a rollback is needed.
- Safe modification: Do not reduce test coverage for `autorate_continuous.py` or related native controller tests while ROLE-01 is unresolved.
- Test coverage: Covered by existing test suite; not exercised in production since 2026-06-08.

## Scaling Limits

**SQLite metrics DB per WAN:**
- Current capacity: Separate `metrics-spectrum.db` and `metrics-att.db`, each receiving ~2Hz writes across ~20-30 metric names. Retention is managed by periodic maintenance (bounded downsampling/deletion).
- Limit: Large databases cause startup maintenance timing pressure. The system has watchdog-safe time-budgeted cleanup, but at sustained write rates without fire-on-change hygiene the DBs grow faster than intended.
- Scaling path: Phase 249 (GAUGE-01..03) fire-on-change audit is the nearest-term fix. WAL mode + periodic vacuum already in place per `src/wanctl/storage/maintenance.py`.

## Dependencies at Risk

**`icmplib` as default RTT measurement backend:**
- Risk: icmplib requires `CAP_NET_RAW` capability; the systemd unit grants this. If the icmplib API changes or the package drops support for the AVERAGE aggregation strategy, measurement will degrade silently to autorate health fallback. The v1.53 live A/B returned `rollback_trigger` verdict for fping, so icmplib remains the default.
- Impact: RTT measurement accuracy and baseline stability.
- Migration plan: Phase 248 analyzes fping p99 from Phase 247 shadow soak. Future verdict may flip the default. `IRTT-MIG-01` stub exists but is unimplemented (`src/wanctl/rtt_backend.py:94-99`).

## Missing Critical Features

**No wanctl-owned WAN route failover:**
- Problem: Netwatch is the only active mechanism for WAN route failover/failback. wanctl/steering has full multi-signal health evidence but no route mutation capability, creating ownership ambiguity and dependency on a single-target RouterOS polling script.
- Blocks: Robust multi-signal failover using congestion + latency + steering state together.
- Status: Design captured in `.planning/todos/pending/2026-06-18-route-ownership-netwatch-to-wanctl-failover.md`. Not scheduled in v1.54.

**Spectrum diffserv4 wash re-evaluation pending:**
- Problem: Spectrum currently runs `besteffort wash` (shipped v1.44 Phase 209). The surrounding QoS topology has since changed (CRS hardware QoS maps, Ruckus Tik QoS Mirroring, bridge QoS rules). The old "classification theater" assumption may no longer hold, but no A/B has been run under the current topology.
- Blocks: Tin-based traffic prioritization for Spectrum (EF/Voice traffic).
- Status: Captured at `.planning/todos/pending/2026-06-03-retest-spectrum-diffserv4-wash-after-local-qos-changes.md`. Not scheduled in v1.54.

**Per-metric write rate tooling not yet available:**
- Problem: No per-metric breakdown exists for steady-state write rates. The `--ingestion-rate` CLI provides bulk per-WAN totals but not per-metric breakdown needed for GAUGE-01 fire-on-change audit.
- Blocks: GAUGE-01 audit for fire-on-change candidates.
- Status: Captured at `.planning/todos/pending/2026-04-17-ingestion-rate-tool.md`. Required for Phase 249.

## Test Coverage Gaps

**SAFE-17/18 boundary verifier tests rot against HEAD:**
- What's not tested: Any per-phase mutation-boundary verifier older than the current phase will fail against `HEAD` because later phases legitimately touched the protected files. This makes `pytest tests/` noisy and masks real failures.
- Files: `tests/test_phase2*_safe17_verifier.py`, `tests/test_phase2*_mutation_boundary.py`, `tests/test_phase2*_safe13_boundary.py`
- Risk: A real regression could be missed in the noise of expected stale failures.
- Priority: Medium. Mitigation: use the focused hot-path slice as the real gate (documented in `CLAUDE.md`).

**Route ownership / Netwatch guard has no tests:**
- What's not tested: Interaction between wanctl and RouterOS Netwatch route mutation entries. No tests for ownership guard, conflict detection, or idempotent route enable/disable.
- Files: `src/wanctl/routeros_client.py`, `src/wanctl/steering/daemon.py`
- Risk: If route mutation is added without tests, conflicts with Netwatch are invisible until production.
- Priority: High (blocked on implementation).

**Spectrum diffserv4 A/B canary has no test scaffold:**
- What's not tested: CAKE mode switch from `besteffort wash` to `diffserv4 wash` and its rollback gate.
- Files: `configs/spectrum.yaml`, `src/wanctl/backends/linux_cake.py`
- Risk: Mode switch would run without automated rollback verification.
- Priority: Low (event-gated validation work, no imminent schedule).

## Process / Operational Concerns

**Phase directory archival gap on milestone transition:**
- Issue: At v1.53 milestone close, the phase directories (238-246) were staged for deletion but not yet committed. The git working tree shows 246 staged deletions with no `milestones/v1.53-phases/` directory. The established convention (used for v1.52, v1.9, etc.) requires a `git mv` from `.planning/phases/` to `milestones/vX.Y-phases/` before any `phases.clear --confirm` step.
- Files: `.planning/phases/238-*` through `246-*` (246 files staged for deletion in `git status`)
- Impact: Evidence for v1.53 phases (AB verdict, SAFE-17 boundary proofs, rollback proofs) becomes unreachable if the staged deletions are committed without the archive move. Note: STATE.md now shows `milestones/v1.53-phases/` referenced, suggesting this may have been resolved post-analysis — verify before committing.
- Fix approach: Confirm `milestones/v1.53-phases/` exists and contains the phase subdirectories before committing staged deletions. See `project_v153_milestone_and_archival_gap` in session memory.

**`/var/lib/wanctl/spectrum_state.json` state format is bridge-specific:**
- Issue: The state bridge writes a reduced state schema (no `SOFT_RED`, no streak fields beyond green streak, no arbitration state). If diagnostic tooling or future code reads these fields expecting native-controller semantics, it will see zero/missing values.
- Files: `deploy/scripts/cake-autorate-spectrum-state-bridge:191-219`
- Impact: Low in current topology (native controller is off). Risk on rollback to native mode without warning.

---

*Concerns audit: 2026-06-19*
