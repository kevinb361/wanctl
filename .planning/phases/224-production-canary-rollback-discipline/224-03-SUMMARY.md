---
phase: 224-production-canary-rollback-discipline
plan: 03
type: execute
status: complete
completed: 2026-06-03
requirements:
  - CANARY-01
  - CANARY-02
snapshot_anchor: "20260603T122925Z"
pre_deploy_commit_sha: 2341226412259a7ba937b9c633542539e76cda86
pre_deploy_version: "1.39.0"
post_deploy_version: "1.47.0"
deploy_exit_code: 0
restart_exit_code: 0
restart_to_healthy_seconds: 2
observation_start_ts: "2026-06-03T12:35:38Z"
---

# 224-03 Summary — Production Deploy + Leg B Post-Deploy Proof

## Outcome

The single production-mutation event of Phase 224 executed successfully. The aligned steering
daemon was deployed to production `cake-shaper` under the Snapshot A rollback anchor, the
`steering.service` restarted, came up `healthy` inside the 30s watchdog budget, and emitted the
expected version. No rollback fired. Controller path was not touched (SAFE-12 holds at runtime).

## Key Facts

| Field | Value |
|-------|-------|
| Snapshot A anchor | `20260603T122925Z` (commit `2341226`) |
| Pre-deploy steering version | `1.39.0` |
| Post-deploy steering version | `1.47.0` (expected `1.47.0` from `src/wanctl/__init__.py`) |
| Deploy exit code | `0` |
| Restart exit code | `0` |
| Restart-to-healthy | `2s` (budget 30s) |
| Observation start ts (Plan 04 input) | `2026-06-03T12:35:38Z` |
| Bound/controller version (unchanged) | `1.45.0` running; on-disk source synced to `1.47.0`, byte-identical, not restarted |

## Governance Preconditions (Task 1)

- Risk-acceptance signed: `.planning/decisions/phase-224-clean-restart-risk-acceptance.md` (Accepted,
  Kevin Blalock, 2026-06-03; Default Disposition — bounded ~15-cycle / ~0.75s post-restart window).
- Evidence copy: `evidence/risk-acceptance-signed.redacted.md`.

## Rehearsal Gate — Honest Override (NOT a measured pass)

`evidence/rehearsal-budget.md` carries `operator_override: unmeasured-waived`,
`within_budget: false`. No staging host was available to time the rollback path, so the
measured-rehearsal gate was waived by operator decision via `/gsd-progress` 2026-06-03. The
rollback path remains **UNPROVEN by measurement**. Mitigation in force: operator ran the deploy at
the keyboard with the 30s watchdog poll and `scripts/phase224-rollback.sh` staged for immediate
manual rollback. Downstream automated gates asserting `within_budget == true` will correctly read
this as not-satisfied; the override is the recorded human decision, not a faked measurement.

## Leg A (pre-deploy) Evidence

- `evidence/snapshot-a/20260603T122925Z/` — MANIFEST.md, redacted configs/health, `pre-deploy-git-ref.txt`,
  `baseline-daemon-source.sha256.txt` (`c7280976…d00d`); raw restore artifacts in operator-private
  `~/.wanctl-phase224-raw/` (mode 0600, uncommitted).
- `evidence/leg-a-prealignment/health.steering.pre-deploy.json` — raw `/health` (`1.39.0`, healthy).
- `evidence/leg-a-prealignment/canary-check.pre-deploy.summary.json` — secondary signal (exit 2,
  version-mismatch expected pre-alignment).
- `evidence/leg-a-prealignment/spine-probe.pre-deploy.json` — no pre-existing violation
  (`spectrum_state_not_written_by_daemon=true`; `binary_on_off`/`only_new_connections`=null, steering disabled).

## Leg B (post-deploy) Evidence

- `evidence/deploy/deploy-stdout.redacted.log`, `restart-stdout.redacted.log`, `restart-to-healthy.log`,
  `anchor.txt`, `deploy-summary.json`.
- `evidence/leg-b-postalignment/health.steering.postdeploy.json` — raw `/health` PRIMARY
  (`version=1.47.0`, `status=healthy`, `decision`/`rtt_source` populated).
- `evidence/leg-b-postalignment/health.bound.postdeploy.redacted.json` — bound `/health`.
- `evidence/leg-b-postalignment/spine-probe.json` — `spectrum_state_not_written_by_daemon=true`,
  `only_new_connections=null`, `binary_on_off=null`.
- `evidence/leg-b-postalignment/canary-check.summary.json` — secondary signal.

## Spine Caveat for Plan 04

`binary_on_off` and `only_new_connections` are `null` (not `true`) at this first sample because
steering is `SPECTRUM_GOOD` / `enabled: false` — no active steering rule exists to positively
evaluate. `null ≠ false`, so this is not a violation. These two invariants become positively
provable only if/when steering activates during the Plan 04 observation window. The continuously
checkable daemon-source-hash invariant (`spectrum_state_not_written_by_daemon`) is `true`.

## SAFE-12 (runtime-confirmed)

- `git diff` controller-path vs `v1.47`: 0 files.
- Runtime proof: `wanctl@spectrum.service` `ActiveEnterTimestamp = 2026-05-30 11:52:19 CDT` (unchanged);
  `steering.service = 2026-06-03 07:35:38 CDT` (restarted). Only the steering unit cycled.

## Next

Plan 04 — canary observation window sampling from `observation_start_ts=2026-06-03T12:35:38Z`,
verdict, and conditional rollback. Rollback remains armed via `scripts/phase224-rollback.sh
--snapshot evidence/snapshot-a/20260603T122925Z --raw-dir ~/.wanctl-phase224-raw --ssh-host
cake-shaper --target-wan spectrum`.
