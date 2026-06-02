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
