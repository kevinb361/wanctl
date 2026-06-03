# Phase 224 Production Canary + Rollback Discipline Report

## Verdict

**KEPT-ALIGNED** — aligned steering daemon deployed to production `cake-shaper` under Snapshot A anchor `20260603T122925Z`, version `1.39.0 → 1.47.0`, healthy in 2s; 16-sample / ~902s observation window closed `kept_aligned` with all six gates passing and no rollback.

## CANARY Closeout

### CANARY-01 — Snapshot A rollback anchor

- Snapshot A: `evidence/snapshot-a/20260603T122925Z/MANIFEST.md` (commit `2341226`, config equality `equal`, persisted-state sha256 captured).
- Raw restore artifacts: operator-private `~/.wanctl-phase224-raw/` (mode 0600, uncommitted) — `deployed-steering.yaml`, `deployed-steering-state.json`, `deployed-steering-state.source-path.txt`.
- Rollback rehearsal budget (`evidence/rehearsal-budget.md`): **`operator_override: unmeasured-waived`**, `within_budget: false`. No staging host was available to time the rollback path; operator waived the measured-rehearsal gate via `/gsd-progress` 2026-06-03 and accepted that rollback duration is UNPROVEN. Mitigation: operator ran the deploy at the keyboard with the 30s watchdog poll and `scripts/phase224-rollback.sh` staged for immediate manual rollback.
- Signed risk-acceptance: `evidence/risk-acceptance-signed.redacted.md` (Accepted, Kevin Blalock, 2026-06-03).

### CANARY-02 — Version alignment + contract invariant proof

- Pre-deploy raw `/health.version`: `1.39.0` (`evidence/leg-a-prealignment/health.steering.pre-deploy.json`).
- Post-deploy raw `/health.version`: `1.47.0`, `status: healthy` (`evidence/leg-b-postalignment/health.steering.postdeploy.json`).
- Spine invariants (final observation sample `evidence/observation/sample-16.spine.composed.json`):
  - `binary_on_off.match = true` — router rule-read, rule `*313` toggled via `disabled` flag (single binary rule).
  - `only_new_connections.match = true` — router rule-read, `connection-state=new`; existing flows never rerouted.
  - `spectrum_state_not_written_by_daemon.match = true` — `method: "code-fingerprint"`, `deployed_sha256 = c7280976…d00d` == `baseline_sha256` (vs `evidence/snapshot-a/20260603T122925Z/baseline-daemon-source.sha256.txt`).
- Note: file-presence of `/var/lib/wanctl/spectrum_state.json` is NOT the signal — that file is the autorate baseline input per `configs/steering.yaml:26-30` and exists in production by design. The production proxy for invariant-3 is the daemon-source code-fingerprint above.
- Rule-shape proof source: `evidence/leg-b-postalignment/spine-rule-proof.json` + `mangle.main-router.json` (operator-authorized read-only REST mangle read). The credentialless spine probe returns `null` for the two rule-shape gates; the composed sample injects the authoritative rule-read values with `provenance` labels (rule shape is constant over the window absent a redeploy).

### CANARY-03 — Rollback discipline

- Gate verdicts at observation close (`evidence/verdict.json`, `outcome: kept_aligned`):

  | Gate | Verdict |
  |------|---------|
  | gate_version_alignment | pass |
  | gate_rtt_source_fresh | pass (0.314s ≤ 5s) |
  | gate_daemon_not_degraded | pass |
  | gate_spectrum_state_not_written_by_daemon | pass |
  | gate_binary_on_off | pass |
  | gate_only_new_connections | pass |

- `rollback_trigger: None`. No gate fired; no rollback executed. `evidence/rollback/` is empty.
- Rollback wall-clock vs budget: N/A (no rollback fired). Rollback remained armed via `scripts/phase224-rollback.sh --snapshot evidence/snapshot-a/20260603T122925Z --raw-dir ~/.wanctl-phase224-raw --ssh-host cake-shaper --target-wan spectrum`.

## SAFE-12 Boundary

`evidence/safe12-boundary-check.json`: `passed: true`, `committed_clean: true`, `dirty_tree_clean: true`, `steering_daemon_clean: true`. Controller path (`wan_controller.py`, `queue_controller.py`, `cake_signal.py`, `alert_engine.py`, `fusion_healer.py`, `backends/`) byte-identical to v1.47 close (`bee343b0`, per-file sha256 equal). Runtime-confirmed: `wanctl@spectrum.service` was never restarted (ActiveEnterTimestamp `2026-05-30`); only `steering.service` cycled. `milestone_close_passed: true` — v1.48 closes cleanly under SAFE-12.

## Clean-Restart Window Governance

Governed by `.planning/decisions/phase-224-clean-restart-risk-acceptance.md` (Default Disposition accepted: bounded ~15-cycle / ~0.75s post-restart steering window). Restart-window symptoms observed during the canary: **0** — `observation-start-ts` (restart) `2026-06-03T12:35:38Z`; all observation samples were ~5h post-restart, far outside the 15-cycle window, with steering steady in `SPECTRUM_GOOD`. Per D-11/D-12, no restart-window symptom could (or did) trigger rollback. Supporting: the 4h soak (`evidence/leg-b-postalignment/soak/`) ran 48 clean cycles including one live SPECTRUM_DEGRADED activate→recover (cycle 17), exercising the binary toggle under real congestion with no spine violation.

## Evidence Index

**RAW `/health` (PRIMARY — gate-eval inputs):**
- `evidence/leg-a-prealignment/health.steering.pre-deploy.json`
- `evidence/leg-b-postalignment/health.steering.postdeploy.json`
- `evidence/observation/sample-01..16.health.json`

**Spine probes:**
- `evidence/leg-a-prealignment/spine-probe.pre-deploy.json`
- `evidence/leg-b-postalignment/spine-probe.json`
- `evidence/observation/sample-01..16.spine.json` + `sample-16.spine.composed.json` (verdict input)
- `evidence/leg-b-postalignment/spine-rule-proof.json` + `mangle.main-router.json` (rule-read proof)

**Snapshot / deploy / verdict:**
- `evidence/snapshot-a/20260603T122925Z/MANIFEST.md` + `baseline-daemon-source.sha256.txt`
- `evidence/deploy/deploy-summary.json`, `deploy-stdout.redacted.log`, `restart-stdout.redacted.log`, `restart-to-healthy.log`
- `evidence/verdict.json`
- `evidence/safe12-boundary-check.{json,md}`
- `evidence/rollback/` (empty — no rollback)

**Secondary signal (canary-check summaries — NOT gate-eval inputs):**
- `evidence/leg-a-prealignment/canary-check.pre-deploy.summary.json`
- `evidence/leg-b-postalignment/canary-check.summary.json`

**Governance:**
- `evidence/risk-acceptance-signed.redacted.md`, `evidence/rehearsal-budget.md`, `.planning/decisions/phase-224-clean-restart-risk-acceptance.md`

## Notes

- Observation cadence: 60s × 16 samples = ~902s window (≥900s / ≥15-sample requirement met).
- Version decision: `__version__` already at `1.47.0` in source (v1.46/v1.47 string-only drift reconciled in commit `4edaf9d` pre-deploy); deploy aligned the runtime steering daemon `1.39.0 → 1.47.0`. Bound/controller daemon remains `1.45.0` running (on-disk source `1.47.0`, byte-identical, not restarted).
- Staging rehearsal host: redacted — none available; measured-rehearsal gate waived (see CANARY-01).
- Deviation from planned defaults: spine rule-shape gates evaluated from an authoritative router rule-read rather than per-sample probe fetch (probe had no router creds); composition is provenance-labeled and constant over the window. Per-sample admin-cred router reads were not run to avoid repeated production-secret access.
- Anchor: SAFE-12 baseline `bee343b0` (Phase 223) and live `v1.47` tag `0eb05300` have identical trees; controller-path zero-diff vs both.
