# Phase 201 — Codex Stop-Time Review (D-18, second leg)

**Reviewed:** 2026-05-04
**Reviewer:** Codex (codex-cli 0.125.0 via `codex exec -s read-only`)
**Scope:** Implemented code from Plans 201-03 through 201-08
**Pre-review reference:** `201-09-CODEX-PRE-REVIEW.md`
**Verdict:** GO WITH FOLLOW-UPS

## Review Inputs

- `201-CONTEXT.md`, `201-RESEARCH.md`, `201-PATTERNS.md`
- `201-09-CODEX-PRE-REVIEW.md`
- `201-04-SUMMARY.md` through `201-08-SUMMARY.md`
- `src/wanctl/queue_controller.py`
- `src/wanctl/wan_controller.py`
- `src/wanctl/autorate_config.py`
- `src/wanctl/check_config_validators.py`
- `configs/spectrum.yaml`
- `scripts/phase201-predeploy-gate.sh`
- `scripts/phase200-saturation-canary.sh`

## Codex Verdict

Codex returned **GO WITH FOLLOW-UPS**. Controller behavior and fail-closed canary gates are acceptable for the live VALN-06 floor-hit gate, with no HIGH-severity findings. Codex identified two MED follow-ups that do not block canary launch if explicitly accepted/deferred by the operator.

> Controller behavior and fail-closed canary gates are good enough for the VALN-06 floor-hit canary, but I found one real evidence-path gap: `max_delay_delta_us` is not actually serialized into public `/health`, so the canary will not capture that field for future replay despite Plan 201-08 claiming it will.

## Pre-review accepted comments — verification

| Pre-review comment # | Implementation status (LANDED / DRIFTED / MISSING) | Operator note |
|----------------------|----------------------------------------------------|---------------|
| 1 — floor-hit accounting after final bounds | LANDED | Codex verified `queue_controller.py` increments `floor_hit_cycles` after `enforce_rate_bounds`; Plan 201-04 summary records post-bounds counter semantics. |
| 2 — DOCSIS YELLOW/R5+R3 semantics | LANDED | Codex verified DOCSIS YELLOW pull-down uses existing `_yellow_decay_streak`; legacy path remains gated by `docsis_mode=False`. |
| 3 — replay thresholds / integral framing | LANDED | Codex verified replay thresholds now match runtime fallback (`15/75`) and Attempt 3 replay is a RED-heavy diagnostic, not synthetic VALN-06 closure. |
| 4 — Spectrum-only predeploy gate defaults | LANDED | Codex verified `deploy.sh` gates only `WAN_NAME=spectrum`, derives remote defaults from deploy variables, and skips non-Spectrum deploys. |
| 5 — Phase 201 canary env fail-closed | LANDED | Codex verified Phase 201 runs require `PHASE201_DOCSIS_MODE=true` and `PHASE201_SETPOINT_MBPS=12`; legacy requires explicit `PHASE201_LEGACY_MODE=true`. |
| 6 — setpoint 12 is assumed, not sweep-supported | LANDED | Codex verified Spectrum YAML/docs/changelog frame `setpoint_mbps: 12` as an assumption validated by the canary. |
| 7 — exact RED fast-trip test | LANDED | Codex verified RED fast-trip exactness is preserved and tested independently of integral/CAKE state. |
| 8 — QueueController size-budget reconciliation | LANDED | Codex accepted the reviewed Plan 201-04 budget reconciliation; no new drift found. |
| 9 — six additive health fields | LANDED | Codex verified the six upload runtime fields are exposed through the QueueController/HealthCheckHandler path. |

## New stop-time comments

| # | Severity (HIGH/MED/LOW) | File / line | Issue | Operator disposition (ACCEPT / DEFER / REJECT) | Rationale |
|---|--------------------------|-------------|-------|------------------------------------------------|-----------|
| 1 | MED | `src/wanctl/health_check.py:720` | `max_delay_delta_us` is present in `CakeSignalSnapshot` but omitted from public `/health.cake_signal.{download,upload}` serialization, so canary full-health captures will not include `cake_signal.upload.max_delay_delta_us` despite Plan 201-08's claim. | DEFER | Non-blocking for VALN-06 because the live canary verdict gates on `floor_hit_cycles_total_delta_loaded_window` plus `ul_floor_hits_during_load`, not on `max_delay_delta_us`. Track as v1.43+ replay-corpus fidelity follow-up before relying on that field in future replay analysis. |
| 2 | MED | `scripts/phase201-predeploy-gate.sh:41`, `scripts/deploy.sh:173` | `PHASE201_LOCAL_YAML_OVERRIDE` is intended for tests but deploy does not clear it; a leaked env var could bypass remote production YAML inspection. | DEFER | Non-blocking with an explicit operator pre-canary check: ensure `PHASE201_LOCAL_YAML_OVERRIDE` is unset before Plan 201-11 deploy/canary. Track a hardening follow-up to clear or test-mode-guard the variable in deploy tooling. |

## Phase 200 known bugs check

| Bug pattern | Phase 201 status | Evidence |
|-------------|------------------|----------|
| Module-scope logger silent-drop | NOT REINTRODUCED | `grep -n "logging.getLogger(__name__).info" src/wanctl/wan_controller.py` returned no matches; Codex verified the Phase 201 opt-in log uses `self.logger`. |
| Value-derived presence flag | NOT REINTRODUCED | `grep -R -n "self\._.*_explicit = self\." src/wanctl` returned no matches; Codex verified Config flags use `"key" in ul`. |
| `/health` YAML echo | NOT REINTRODUCED | Upload DOCSIS fields are read from `QueueController.get_health_data()` / live controller state, not directly from YAML config. |
| `/health` field assumption (canary three-branch) | HANDLED | Canary probe handles key absent, false, true, and invalid with explicit verdict reasons (`health_docsis_key_absent`, `health_docsis_false`, `health_docsis_invalid`). |
| Predeploy gate auto-strip regression | NOT REINTRODUCED | Gate emits PASS/BLOCK/ABORT and does not implement auto-strip; rejected keys require operator action. |
| Canary env/YAML false-PASS regression | NOT REINTRODUCED | DOCSIS mode and setpoint mismatches abort with named verdict reasons (`env_yaml_docsis_mode_mismatch`, `env_yaml_setpoint_mismatch`). |
| Remote YAML path validation regression | NOT REINTRODUCED | Codex verified safe absolute-path regex remains present in canary and predeploy gate. |

## Additional verification evidence

- Full test suite: `.venv/bin/pytest -q` → `4864 passed, 6 skipped, 2 deselected in 189.38s`.
- Codex narrow review checks: DOCSIS byte identity, RED fast-trip, legacy replay identity, and Attempt 3 replay diagnostic passed.
- Codex shell checks: canary/predeploy script syntax passed.
- Codex canary self-tests confirmed DOCSIS YAML mismatch, setpoint mismatch, health key absent, and mutually-exclusive env cases abort with rc `2`.
- Version surfaces verified at `1.42.0` in `pyproject.toml`, `src/wanctl/__init__.py`, and `docker/Dockerfile`.
- `Config('configs/spectrum.yaml')` reports `docsis_mode=True`, `setpoint_mbps=12`, explicit DOCSIS/setpoint flags, and runtime upload threshold fallback `15/75`.
- `KNOWN_AUTORATE_PATHS` contains all six Phase 201 upload keys.

## Live canary launch decision

- [x] All HIGH stop-time comments have ACCEPT or REJECT-with-rationale — no HIGH comments were returned.
- [x] All accepted pre-review comments verified LANDED (no DRIFTED, no MISSING).
- [x] Phase 200 known-bug grep checks confirm clean for module logger and value-derived presence flags.
- [x] Test suite green: `4864 passed, 6 skipped, 2 deselected in 189.38s`.
- [x] Operator confirms canary may proceed (Plan 201-11) under GO WITH FOLLOW-UPS constraints below.

**Decision:** Plan 201-11 may proceed as **GO WITH FOLLOW-UPS** if the operator confirms `PHASE201_LOCAL_YAML_OVERRIDE` is not exported in the deploy/canary environment. The `max_delay_delta_us` serialization gap is non-blocking for the VALN-06 floor-hit gate but must be tracked before future replay-corpus analysis depends on that field.

## Follow-ups (GO WITH FOLLOW-UPS)

1. **Replay-corpus fidelity:** Add `max_delay_delta_us` to public `/health.cake_signal.{download,upload}` serialization, or correct future replay documentation so it does not claim the field is captured.
2. **Predeploy hardening:** Clear `PHASE201_LOCAL_YAML_OVERRIDE` in `scripts/deploy.sh` production invocation or guard it behind an explicit test-mode variable so leaked shell environment cannot bypass remote YAML inspection.

## Raw Codex Output

Saved during execution at `/tmp/opencode/phase201-codex-stop-time-review.txt`.
