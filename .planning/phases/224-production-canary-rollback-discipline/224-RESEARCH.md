# Phase 224 Research: Production Canary + Rollback Discipline

**Phase:** 224 — Production Canary + Rollback Discipline
**Researched:** 2026-06-02
**Confidence:** HIGH (precedent from v1.46 Phase 215 is concrete; tooling already exists)
**Source:** CONTEXT.md + Phase 215 evidence + Phase 222/223 closure artifacts + live code surface

## User Constraints

**Locked decisions from CONTEXT.md (D-01 through D-14) are NON-NEGOTIABLE. Verbatim summary:**

### Locked Decisions

- **D-01 Snapshot A pattern:** Pre-deploy snapshot captures binary + `/etc/wanctl/steering.yaml` + persisted state under `/var/lib/wanctl/` + `/health` JSON. Timestamped under `evidence/snapshot-a/<TS>/` with a manifest.
- **D-02 Revert mechanism:** Restore captured binary + config + state to pre-deploy paths, `systemctl restart wanctl-steering.service`, re-query `/health` to confirm reverted version matches snapshot.
- **D-03 Snapshot ownership:** Operator-runnable script or documented command sequence; idempotent; explicit; no cluster-state dependency.
- **D-04 Deploy path:** Use existing paved path (`scripts/deploy.sh ... --with-steering` or equivalent). No one-off procedure. Any small adjustment to deploy tooling is its own small, reviewable plan.
- **D-05 Version alignment proof:** `/health.version` matches the expected v1.48 release line; `/health.steering`, `/health.decision`, `/health.congestion` populate with well-formed fields; `/health.status == "healthy"` within a documented settling window.
- **D-06 Contract invariant probes:** Binary on/off (router rule presence ↔ `steering.enabled`), only-new-connections rerouted (router rule selector shape), autorate-baseline-RTT authoritative (`/health.decision.rtt_source` cites autorate-baseline).
- **D-07 Decision continuity:** Decision-log fields populate at expected cadence; stuck section across N cycles is fail-closed.
- **D-08 Time budget:** Bounded rollback time budget (≤ small minutes — concrete number is a discretion call below).
- **D-09 Fail-closed gates:** Any of {version drift, spine invariant fail, decision staleness > N cycles, daemon `degraded` dwell > documented, router rule shape deviation} triggers rollback inside the budget.
- **D-10 Rollback report:** Cite snapshot anchor + gate that fired + post-revert `/health` proof; if no rollback, cite window duration + gate verdicts + kept-aligned disposition.
- **D-11 Decision-artifact governance:** Bounded ~15-cycle / ~0.75-second post-restart effective-steering window is NOT a rollback trigger; governed by `.planning/decisions/phase-224-clean-restart-risk-acceptance.md` (Default Disposition stands).
- **D-12 Restart-window vs steady-state distinction:** Restart-window symptoms noted in report but not gating. Only steady-state spine violations trigger rollback.
- **D-13 SAFE-12 phase boundary:** Phase 222/223 schema (`safe12-boundary-check.{json,md}`); zero controller-path source diff vs v1.47 close; `src/wanctl/steering/` IS in scope, controller-path is NOT.
- **D-14 SAFE-12 milestone close:** Also checked at v1.48 milestone close, mirroring SAFE-07/08/09/11 precedent.

### Claude's Discretion (research recommends below)

- Exact rollback time budget number (D-08).
- Exact canary observation window duration.
- Exact decision-section staleness cycle count.
- Snapshot capture = new script vs documented sequence (D-03).
- Canary report shape / publication location.

### Deferred Ideas (out of scope)

- Daemon-side fix for the clean-restart window (governed by decision artifact; Override Path is a separate phase).
- Multi-host canary rollout, multi-WAN canary.
- Storage hygiene fire-on-change (SEED-007), conservative UL tuning (SEED-005).
- Steering algorithm tuning during canary.
- VERIFY-01 / VERIFY-02 watch-list (event-gated, not a Phase 224 driver).

## Project Constraints (from CLAUDE.md)

- **Production network control system; change conservatively.** Stability > safety > clarity > elegance.
- **Cycle interval is 50ms** (20 Hz) — staleness budgets and observation windows should reference this cadence.
- **REST API preferred** for RouterOS interactions; SSH is fallback.
- **Spine constraints (immutable):** binary on/off, only-new-latency-sensitive-connections rerouted, autorate baseline RTT authoritative.
- **Project-finalizer agent before commits** is required by the doc-check pre-commit hook (or `SKIP_DOC_CHECK=1` for planning-only commits).
- **Tests via `.venv/bin/pytest`**, lint via `.venv/bin/ruff`, type via `.venv/bin/mypy`. Don't reinvent.
- **No timer-era guidance** — service-based deployment is the active model.

## Phase Boundary

Operator can deploy the aligned steering daemon to production with a Snapshot-A-pattern rollback anchor, prove version alignment + contract invariants live via `/health`, and roll back within a bounded time budget if any invariant fires fail-closed during canary observation. The output is a canary report citing snapshot anchor, gate verdicts, and either kept-aligned or rolled-back disposition. SAFE-12 holds at phase boundary and at v1.48 milestone close.

## Standard Stack (use these — already wired into the project)

- **Deploy:** `scripts/deploy.sh <wan_name> <target_host> --with-steering` — paved path for steering daemon deploy. Pairs with `scripts/install-systemd.sh <wan_name> [--steering]` for unit installation.
- **Service unit:** `deploy/systemd/steering.service` — `wanctl-steering.service` Type=simple; `WatchdogSec=30s`; `MemoryMax=384M`; `CAP_NET_RAW`. Production unit name is `wanctl-steering.service` (NOT `wanctl-steering@*` — steering is single-instance per host).
- **Health endpoint:** `src/wanctl/steering/health.py` — binds default port 9102; responds 200 healthy / 503 degraded; emits `version`, `status`, `steering`, `decision`, `congestion`, `counters`, `confidence`, `errors`, `summary`, `router_reachable`, `disk_space`.
- **Snapshot helper precedent:** `scripts/phase213-steering-snapshot.sh` already captures redacted `/health` + `state.redacted.json` over SSH with a `--output <prefix>` interface. Extend or wrap this for Phase 224 (NOT a from-scratch new script).
- **Post-deploy validation:** `scripts/canary-check.sh` already exists with `--expect-version`, `--skip-steering`, `--ssh kevin@<host>`, `--json`, `--timeout` flags. Steering target is hard-coded to `steering|127.0.0.1|9102` — Phase 224 should validate the steering check works for a remote host via `--ssh` (or wrap it with the right SSH context).
- **Spine boundary check:** `scripts/check-safe07-source-diff.sh` (SAFE-07 family) is the precedent; Phase 223 produced `safe12-boundary-check.{json,md}` schema — reuse that.
- **Live router probe (REST preferred):** `src/wanctl/routeros/rest_backend.py` (or equivalent) — read-only queries for steering rule presence + selector shape.
- **Persisted state path:** `/var/lib/wanctl/spectrum_state.json` (and equivalent for ATT). Steering daemon state file location is captured by the existing snapshot helper.

## Architecture Patterns

- **Snapshot-A directory shape:** `evidence/snapshot-a/<TS>/{MANIFEST.md, repo-config.redacted.yaml, deployed-config.redacted.yaml, state.redacted.json, snapshot-a-health.redacted.json, db-query.redacted.json}` — mirror Phase 215 exactly.
- **Manifest content:** Captured timestamp, source posture statement ("read-only; no deploy"), health source URL, health version, health uptime, deployed-config equality assertion, persisted-state fields, **targeted revert sequence** as numbered steps.
- **Health-endpoint proof artifact:** `evidence/leg-a-prealignment/health-baseline.redacted.json` (pre-deploy) and `evidence/leg-b-postalignment/health-postdeploy.redacted.json` (post-deploy) — same shape as Phase 215 `leg-a-ceiling18/` and `leg-b-ceiling20/`.
- **Gate evidence:** `evidence/gate-verdicts.json` records per-gate boolean + the field/value that satisfied it. Final canary outcome: `evidence/verdict.json` with `{outcome: kept-aligned | rolled-back, reason: <gate-id or null>, snapshot_anchor: <TS>}`.
- **Canary report:** `224-REPORT.md` at phase root, format mirrors `215-REPORT.md` (Verdict, CANARY closeout per REQ-ID, Evidence Index, Notes).
- **SAFE-12 boundary proof:** `evidence/safe12-boundary-check.{json,md}` using the Phase 223 schema; phase boundary check happens at plan close; milestone close re-runs against full v1.48 source-surface delta.
- **Rollback rehearsal artifact:** `evidence/rollback-rehearsal/<TS>/` from staging dry-run — time-budget evidence comes from this, not estimate.

## Don't Hand-Roll

- **Don't build a new deploy path** — `scripts/deploy.sh` is the contract.
- **Don't build a new health-endpoint parser** — `scripts/canary-check.sh --json` returns structured output; consume it.
- **Don't fabricate the snapshot script** — extend / wrap `scripts/phase213-steering-snapshot.sh` (it already does the redaction and the `/health` capture).
- **Don't write a new SAFE-12 checker** — Phase 223 schema is the target shape.
- **Don't write a new RouterOS rule reader** — use existing REST/SSH backend helpers; read-only queries only.
- **Don't define rule-shape spec in-plan** — the spec is what Phase 222 audit recorded. Probe reads live state and compares against that recorded shape.

## Common Pitfalls

1. **`/health` endpoint binding.** Phase 215 Snapshot A explicitly used the **bound external IP** (`http://10.10.110.223:9101/health`), not `127.0.0.1`. Steering daemon's default bind is `127.0.0.1:9102`. If post-deploy proof must come from external monitoring, document which surface is the source of truth. Recommend: collect both, treat bound `/health` as the operator-facing source of truth, loopback as internal probe.
2. **Version-string source.** `__version__` is in `src/wanctl/__init__.py` AND `pyproject.toml` AND likely `docker/Dockerfile` LABEL (per v1.45 precedent). If Phase 224 bumps to `1.48.0`, all three surfaces must be touched in the same commit, mirroring Phase 211. If Phase 224 does NOT bump, expected version is `1.45.0` and the canary report must say so explicitly.
3. **Snapshot drift between capture and deploy.** Phase 215 captured Snapshot A, then deployed. If any file under the snapshot scope changes between capture and deploy (e.g., operator edits config in between), the snapshot anchor is stale. Mitigation: capture-time freshness check or git-clean assertion on the relevant config dir before deploy.
4. **Steering rule scope drift.** Phase 222 audit recorded the rule shape. If a prior production touch (outside v1.48 work) altered the deployed rule, the live router rule shape may not match the recorded spec. Probe must read the live rule first and surface drift as a pre-deploy block (not a post-deploy false-fail).
5. **Clean-restart symptom misclassified as gate failure.** The bounded ~15-cycle / ~0.75-second post-restart effective-steering window is the accepted symptom per `.planning/decisions/phase-224-clean-restart-risk-acceptance.md`. The gate code must explicitly distinguish "restart-window symptom (≤ ~15 cycles after restart, recovers to GOOD)" from "steady-state spine violation". Without this distinction, every canary will trip rollback at deploy second 0.
6. **Decision staleness cadence at 50ms.** A "stuck for 4 cycles" budget = 200ms wall-clock. The decision section update cadence is set by the daemon's cycle interval. Recommend: anchor staleness threshold in observed cadence from Phase 222 evidence, not arithmetic ("`decision.last_update` should advance once per cycle; 4-cycle stall = 200ms = fail-closed").
7. **`scripts/canary-check.sh` steering target is hard-coded to `127.0.0.1:9102`.** For a remote-host steering canary check, either run the script via `--ssh kevin@<host>` (script handles SSH-encapsulated probes) or wrap the steering check with the right host context. Verify in staging rehearsal which mode works.
8. **WatchdogSec=30s on the service unit.** During snapshot capture or planned restart, watchdog may fire if the daemon takes >30s to come up healthy. Documented restart-to-healthy budget must be inside 30s, or the unit needs a one-shot watchdog disable for the restart — but the latter is a mutation to systemd file scope that crosses outside the safe path. Recommend: validate restart-to-healthy <30s in staging rehearsal before production touch.
9. **SAFE-12 boundary check timing.** It must run AFTER deploy completes and BEFORE rollout is declared kept-aligned. A pre-deploy check is necessary too (to confirm Phase 222/223 close state is byte-identical at canary time).
10. **Decision-artifact sign-off is human-only.** D-11 says operator accepts the risk window. Phase 224 work must NOT fabricate the sign-off; the sign-off line in `.planning/decisions/phase-224-clean-restart-risk-acceptance.md` must be operator-completed at deploy time, captured as evidence (signed artifact path under `evidence/`).
11. **Rule-shape spec is captured, not invented.** The "binary on/off + only-new-connections + autorate-authoritative" probes need a frozen reference shape. Source of truth: Phase 222 audit evidence + Phase 223 spine-evidence.json. Phase 224 reads live state and compares against those recorded shapes byte-for-byte (or field-for-field where byte-equality is brittle).
12. **No production mutation outside the deploy itself.** Probes, snapshot capture, and report generation are read-only. The single mutation event is `scripts/deploy.sh + systemctl restart wanctl-steering.service`. Any rollback is also a mutation event but bounded to restoring snapshot artifacts.

## Validation Architecture

**Nyquist Dimension 8 strategy:**

| Dimension | Validation surface | How |
|---|---|---|
| 1 — Source existence | Snapshot scripts, gate scripts, report exist as named files. | Grep file paths. |
| 2 — Source content | Snapshot manifest sections present; gate JSON keys present. | Schema check against fixtures. |
| 3 — Composition | `canary-check.sh --json` parsed into gate-verdicts.json. | Run `--json` mode in dry-run; verify keys. |
| 4 — Data flow | Snapshot → deploy → /health → gate-verdicts → verdict.json → REPORT.md. | End-to-end staging rehearsal. |
| 5 — Behavior | Gate trips → rollback executes → /health shows reverted version. | Staging fault-injection (mock /health that flips version mid-window). |
| 6 — Cross-cutting | SAFE-12 zero-diff at boundary; clean-restart window NOT mis-classified. | `safe12-boundary-check.json`, clean-restart fixture in gate test corpus. |
| 7 — Persistence | Snapshot artifacts on disk, redacted, idempotent capture. | Re-run snapshot script twice; assert deterministic redaction + manifest. |
| 8 — Validation | Staging rehearsal evidence proves rollback inside budget. | `evidence/rollback-rehearsal/<TS>/duration_ms` < budget. |

**Critical:** Validation surfaces 5, 6, 8 require a STAGING rehearsal before the production touch. Plan must include rehearsal as a gating step.

## Code Examples (concrete identifiers)

- **Snapshot helper invocation pattern** (from `scripts/phase213-steering-snapshot.sh`):
  ```
  scripts/phase213-steering-snapshot.sh --output evidence/snapshot-a/<TS>/steering --ssh-host cake-shaper
  ```
  Phase 224 wraps this with config-capture + manifest synthesis.

- **Canary check invocation:**
  ```
  scripts/canary-check.sh --ssh kevin@cake-shaper --expect-version <expected> --json > evidence/leg-b-postalignment/canary-check.json
  ```

- **Deploy paved path:**
  ```
  scripts/deploy.sh <wan_name> cake-shaper --with-steering
  ssh cake-shaper 'sudo systemctl restart wanctl-steering.service'
  ```

- **Targeted revert:**
  ```
  # Restore snapshot artifacts to deployed paths (binary, config, state)
  # systemctl restart wanctl-steering.service
  # canary-check.sh --ssh ... --expect-version <pre-deploy-version> --json
  ```

- **SAFE-12 boundary check (schema from Phase 223):**
  - JSON keys: `passed`, `committed_clean`, `dirty_tree_clean`, `steering_daemon_clean`, `controller_path_paths`, `steering_paths`.
  - Allowlist: `src/wanctl/steering/`, `tests/integration/steering_replay/`, `configs/`, `deploy/systemd/`, `scripts/`, `docs/`, `.planning/`.

- **Decision-artifact link from canary report:**
  ```
  See `.planning/decisions/phase-224-clean-restart-risk-acceptance.md` —
  restart-window symptoms are governed there, NOT by this canary's gates.
  ```

## Recommendations (for discretion calls)

### Rollback time budget (D-08)
**Recommend:** **≤ 5 minutes** from gate fire to reverted-and-proven `/health`. Rationale: Phase 215 precedent (targeted YAML revert + deploy + restart + canary-check completed in similar wall-clock); steering daemon restart is simpler than full controller restart; `WatchdogSec=30s` bounds restart-to-healthy. Staging rehearsal MUST measure actual wall-clock and report it before production touch.

### Canary observation window duration
**Recommend:** **≥ 15 minutes wall-clock OR ≥ 200 decision cycles, whichever is longer.** Rationale: at 50ms cadence, 200 cycles = 10 seconds — way too short to catch steady-state drift. 15 minutes catches multiple congestion-state transitions during representative production load. Time-of-day balance: prefer a window that overlaps with at least one observable load shift (cite Phase 222 observation pattern if specified).

### Decision-section staleness cycle count (D-09)
**Recommend:** **4 cycles (200ms)** for stuck-decision fail-closed signal. Rationale: at 50ms cycle, 4 cycles is comfortably above noise but tight enough to catch a wedged daemon before steady-state drift accumulates. Anchor in `decision.last_update_cycle` field if it exists; otherwise compare `decision.last_cycle_ts` deltas.

### Snapshot capture: script vs documented sequence (D-03)
**Recommend:** **Wrap existing `scripts/phase213-steering-snapshot.sh` with a thin Phase 224 wrapper** (`scripts/phase224-snapshot-a.sh`) that ALSO captures the binary version, deployed config diff, and writes the MANIFEST.md per Phase 215 shape. Rationale: don't reinvent redaction logic, but Phase 224 has more capture scope than the bare steering snapshot. Keep it small (< 100 lines), shellcheck-clean, idempotent.

### Canary report (D-10)
**Recommend:** **`224-REPORT.md` at phase root**, mirroring `215-REPORT.md` exactly: Verdict line, CANARY-01/02/03 closeout sections, Evidence Index. Publish in the same commit as the verdict.json.

### Version bump decision (Pitfall 2)
**Recommend:** **Defer the version-string bump to a separate small commit if at all** — or, if v1.48 has decided to bump, do it as Plan 01 first (pre-deploy) so the snapshot anchor records the pre-bump version and post-deploy proof records the post-bump version. Without a bump, the canary proves alignment of source `1.45.0` daemon code with production deployment — that's still a valid CANARY-02 outcome, because the *aligned daemon* is what's shipping, not the version-string label.

**Operator confirmation needed at plan time:** Does Phase 224 bump `__version__` to `1.48.0`? Default to NO bump unless the operator says otherwise — see PROJECT.md note that v1.48 is the milestone name, not a guaranteed version-string change.

## Validation Decision: Walking Skeleton

Phase 224 is NOT a walking-skeleton phase. It's a final-phase production canary on an established codebase with established patterns. Plans should be horizontal: snapshot → rehearsal → deploy → observation → report.

## Architectural Responsibility Map

| Responsibility | Owner | File / surface |
|---|---|---|
| Pre-deploy snapshot capture | Phase 224 wrapper script + existing steering-snapshot helper | `scripts/phase224-snapshot-a.sh` (new wrapper) + `scripts/phase213-steering-snapshot.sh` (existing) |
| Deploy execution | Existing paved path | `scripts/deploy.sh` + `systemctl restart wanctl-steering.service` |
| `/health` proof emission | Existing endpoint, unchanged | `src/wanctl/steering/health.py` |
| Version-alignment check | Existing canary-check | `scripts/canary-check.sh --expect-version` |
| Spine invariant probe | Phase 224 script (small) reading live router state + /health | `scripts/phase224-spine-probe.sh` (new) — read-only, REST preferred |
| Decision continuity probe | `/health.decision.last_update_cycle` polled by phase 224 monitor | `scripts/phase224-canary-monitor.sh` (new, or inline in observation phase) |
| Gate evaluation + verdict.json | Phase 224 evaluator | `scripts/phase224-gate-eval.py` (new, small, stdlib-only) |
| Rollback execution | Documented sequence + Phase 224 helper | `scripts/phase224-rollback.sh` (new wrapper around snapshot restore + restart + canary-check) |
| SAFE-12 boundary check | Phase 223 schema, reused | `evidence/safe12-boundary-check.{json,md}` |
| Canary report | Author at phase close | `224-REPORT.md` |
| Decision-artifact sign-off | Operator-only | `.planning/decisions/phase-224-clean-restart-risk-acceptance.md` |

**All new scripts MUST land in `scripts/` (project convention), use stdlib where possible, be shellcheck-clean, and not touch the controller path or modify the steering daemon source.**

## Package Legitimacy Audit

**N/A** — no new external packages are required. Snapshot, probe, monitor, and gate scripts use stdlib Python (per `scripts/phase219_ingestion_digest.py` precedent) and bash + curl + jq (already available; no new npm/pip/cargo installs).

## Honest Reporting

- **High confidence:** Phase 215 precedent is concrete and replicable. Tooling (`deploy.sh`, `canary-check.sh`, `phase213-steering-snapshot.sh`) already exists in the right shape. Health-endpoint contract is stable post-Phase 222. SAFE-12 schema is already proven in Phase 223.
- **Medium confidence:** Exact decision-section field names (`last_update_cycle` vs `last_cycle_ts`) — needs a quick grep against `src/wanctl/steering/health.py` at plan time. Rollback wall-clock budget — must be measured in staging rehearsal, not assumed.
- **Low confidence:** Whether `canary-check.sh --skip-steering` behavior + remote-host steering probe interact cleanly via `--ssh`. Staging rehearsal will catch this; plan must include the rehearsal step as gating.

## Open Questions for Plan Time

1. Does v1.48 bump `__version__` to `1.48.0`? (Recommend: NO. Operator confirms.)
2. What is the production target host for the canary? (Assumed: `cake-shaper` based on Phase 215 + Snapshot manifest precedent — operator confirms which WAN host(s) and whether the canary is steering-specific so it's the steering host rather than a per-WAN host.)
3. What is the agreed observation window duration? (Recommend: 15 minutes minimum; operator may extend.)
4. Is the operator sign-off on `.planning/decisions/phase-224-clean-restart-risk-acceptance.md` captured before or at deploy time? (Recommend: captured immediately before the deploy gate, as part of pre-deploy checklist evidence.)

## RESEARCH COMPLETE

**Phase:** 224 — Production Canary + Rollback Discipline
**Confidence:** HIGH

### Key Findings

- All required tooling exists: `scripts/deploy.sh --with-steering`, `scripts/canary-check.sh --expect-version --json`, `scripts/phase213-steering-snapshot.sh`. Phase 224 wraps and orchestrates rather than reinventing.
- Phase 215 Snapshot A precedent provides a directly replicable directory shape, manifest format, and report shape.
- SAFE-12 boundary check schema is already proven in Phase 223 — reuse, don't redesign.
- Clean-restart risk artifact at `.planning/decisions/phase-224-clean-restart-risk-acceptance.md` governs the restart window — plans MUST explicitly distinguish restart-window vs steady-state in the gate logic.
- Version-bump decision is a discretion call surfaced for operator confirmation; recommend NO bump.
- Staging rehearsal of the rollback path is a gating prerequisite, not an optional add — actual wall-clock budget measurement is the only honest source.
- No new packages, no controller-path mutation, no algorithm changes — Phase 224 is pure orchestration + observation + report.

### Plan Skeleton (recommendation to planner)

5 plans, 3 waves:

- **Plan 01 — Pre-deploy Snapshot A + spine baseline + staging rehearsal** (Wave 1). Snapshot script wrapper, captured artifacts, rehearsal of the rollback sequence in staging, measured rollback wall-clock budget.
- **Plan 02 — Spine invariant probe + decision continuity probe + gate-eval script** (Wave 1, parallel to 01 — no file overlap). Read-only probes, gate JSON shape, fixture-driven tests.
- **Plan 03 — Production deploy + post-deploy health-endpoint proof** (Wave 2, depends on 01 + 02). Single mutation event; expects rehearsed rollback path; captures Leg B health.
- **Plan 04 — Canary observation window + gate verdicts + rollback discipline** (Wave 3, depends on 03). Runs gates over the observation window; either kept-aligned or rolls back inside budget; emits verdict.json.
- **Plan 05 — Canary report + SAFE-12 boundary + decision-artifact sign-off** (Wave 3, depends on 04). REPORT.md, safe12-boundary-check evidence, signed risk-acceptance artifact.

Each plan: 2-3 tasks, ~50% context budget, files_modified disjoint where parallel.
