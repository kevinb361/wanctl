---
phase: 245
reviewers: [codex, opencode]
reviewed_at: 2026-06-18T23:04:49Z
plans_reviewed: [245-01-PLAN.md, 245-02-PLAN.md, 245-03-PLAN.md, 245-04-PLAN.md]
---

# Cross-AI Plan Review — Phase 245: Live A/B + Rollback Anchor

> **Reviewer note:** Running inside Claude Code (CLAUDE_CODE_ENTRYPOINT=cli), so Claude was
> skipped for independence. Gemini not installed. Reviewers: **Codex** (OpenAI Codex CLI
> v0.141.0) and **OpenCode** (qwen3-32b via local vLLM at ai.home.arpa).

---

## Codex Review

**Overall Summary**

The plan set is directionally solid: preregistration comes before data, the live-path change is
intentionally small, and rollback/operator gates are treated as first-class work. The main gaps
are production-significant: `/health` currently drops any future `wanctl_backend` counter; the
SAFE-17 protected-body layer does not tightly protect the daemon/health edit surface; the A/B
design conflicts with the "zero daemon restarts" gate if backend switching requires restarts;
and "Snapshot-A rollback" is ambiguous between config-only rollback and code rollback to
`ffaa8a0e`. Also, current repo `HEAD` is `a9eff623`, so any `HEAD == ffaa8a0e` check must be
scoped to the production preflight state, not the implementation branch after Plans 01–03 land.

### Plan 01: SAFE-17 Verifier + Preregistration Scaffold

**Summary**: Correct ordering—verifier and thresholds are committed before daemon flip or live
data. Blob SHA plus descendancy provenance is the right basic preregistration shape. Keeping
the SAFE-17 allowlist frozen avoids quiet scope creep.

**Strengths**
- Correct ordering: verifier and thresholds committed before daemon flip or live data.
- Blob SHA + descendancy provenance is the right basic preregistration shape.
- Keeping the SAFE-17 allowlist frozen avoids quiet scope creep.

**Concerns**
- **MEDIUM:** "Anchor swap only" may preserve stale Phase 244 wording and assumptions. Not
  dangerous by itself, but bad evidence labels cause audit confusion.
- **MEDIUM:** The existing SAFE-17 verifier is strong for path allowlisting and protected RTT-
  controller bodies, but it does not tightly classify edits inside `steering/daemon.py` or
  `steering/health.py`. Phase 245's risky change lives exactly there.
- **MEDIUM:** Thresholds do not appear to preregister sample/window minimums, exclusion rules,
  control-WAN instability handling, or the definition of "clear improvement" for
  `switch-eligible`.
- **LOW:** If Plan 02 must modify health count surfacing, "diff bounded to daemon.py" will
  become false.

**Suggestions**
- Add a Phase 245-specific diff-shape check for exactly the permitted daemon/health hunks:
  source gate constant, count key, seam-first probe block, and health count exposure.
- Commit a machine-readable `phase245-prereg.json` containing threshold blob, prereg commit,
  anchor commit, endpoints, planned restart semantics, window length/count, exclusion rules,
  and improvement criteria.
- Make gate-eval require that prereg file explicitly, not merely call `record` against whatever
  `HEAD` contains later.

**Risk Assessment: MEDIUM** — Mostly scaffold work, but the integrity story is not complete
unless prereg and SAFE-17 checks are machine-enforced against Phase 245's actual risky surfaces.

---

### Plan 02: Selection-A Live-Path Flip in daemon.py

**Summary**: Minimal control-path edit with fallback chain preserved. Reuses
`_record_rtt_source_success`, which keeps attribution logic centralized. Activating the Phase
244 metadata gate through `_WANCTL_BACKEND_RTT_SOURCES` is a clean design.

**Strengths**
- Minimal control-path edit with fallback chain preserved.
- Reuses `_record_rtt_source_success`, keeping attribution logic centralized.
- Activating the Phase 244 metadata gate through `_WANCTL_BACKEND_RTT_SOURCES` is a clean design.

**Concerns**
- **HIGH:** Existing health output only emits `autorate_health`, `autorate_irtt`, and
  `history_fallback` counts in health.py:372. If AB-03 relies on `/health` for
  `wanctl_backend / total`, Plan 02 must expose that count.
- **HIGH:** The proposed probe call is unguarded. If `probe()` raises due to subprocess/fping/
  socket failure, steering can fail before fallback. For production, catch expected exceptions,
  log rate-limited, and fall through.
- **MEDIUM:** Numeric validation should reject `NaN`, `inf`, zero, and negative RTT, not only
  check `int | float`.
- **MEDIUM:** A seam-first probe every 50ms can exceed budget when backend failure falls through
  to autorate fallback. Tests should include slow/None/error probe behavior and assert fallback
  remains bounded enough.
- **LOW:** Existing tests named around "no self-ping fallback" will become stale and should be
  rewritten to reflect the new contract.

**Suggestions**
- Add `"wanctl_backend"` to both daemon counts and the public health builder counts.
- Wrap probe with `try/except Exception` narrowly enough to preserve steering, and record a
  failure counter if available.
- Use `math.isfinite(rtt) and rtt > 0`.
- Add a test proving `producer="wanctl-backend"`, `backend`, `source_ip`, and
  `counts.wanctl_backend` survive the actual `/health` server path, not just
  `daemon.get_health_data()`.

**Risk Assessment: MEDIUM-HIGH** — This is the live control-path flip. The edit is small, but
failure handling and observability need to be airtight before production.

---

### Plan 03: Gate-Eval + A/B Run + Rollback Scripts

**Summary**: Good separation between tooling build and live execution. Six gate dimensions
cover the right broad concerns. `keep-icmplib` as a passing outcome prevents forcing a flip
from weak evidence. Mutation requiring `--confirm` is the right posture.

**Strengths**
- Good separation between tooling build and live execution.
- Six gate dimensions cover the right broad concerns.
- `keep-icmplib` as a passing outcome prevents forcing a flip from weak evidence.
- Mutation requiring `--confirm` is the right posture for a 24/7 system.

**Concerns**
- **HIGH:** Alternating `icmplib`/`fping` windows are interleaved crossover, not concurrent A/B.
  That may be acceptable, but the plan should say so and define how the ATT control normalizes
  drift.
- **HIGH:** If switching backend requires config deploy or `steering.service` restart per window,
  `MAX_DAEMON_RESTARTS=0` is impossible unless planned restarts are explicitly excluded and
  measured separately.
- **HIGH:** Gate-eval needs per-window counter deltas. Absolute cumulative counts will be
  contaminated across windows and restarts.
- **HIGH:** Rollback script only describes restoring Spectrum config. That is not a rollback to
  code anchor `ffaa8a0e` if Phase 245 code remains deployed.
- **MEDIUM:** "Loss-detection non-regression" is weak unless live data actually contains loss
  events or the plan defines "inconclusive" rather than pass.
- **MEDIUM:** Steering decision stability by enable/disable distribution can hide oscillation.
  Transition count, route action count, or decision flip rate should be included.

**Suggestions**
- Decide explicitly: either build a passive shadow sampler for true concurrent backend
  comparison, or preregister this as an interleaved crossover with control-WAN stationarity
  gates.
- Define planned restart accounting: baseline after planned restart, abort on unexpected
  restarts, and record planned restart count separately.
- Make rollback either deploy exact Snapshot-A code+config, or rename it to "return to icmplib
  under Phase 245 code."
- Gate on raw evidence hashes and reject aggregate-only inputs.

**Risk Assessment: HIGH** — The tooling can mutate production repeatedly. The A/B and restart
semantics must be clarified before it is safe to use.

---

### Plan 04: Live Production Execution (Operator-Gated)

**Summary**: Operator checkpoints are appropriate for a 24/7 network controller. Read-only
preflight first is correct. Leaving the production default flip to Phase 246 is the right
safety boundary.

**Strengths**
- Operator checkpoints are appropriate for a 24/7 network controller.
- Read-only preflight first is correct; no mutation without explicit operator approval.
- Leaving the production default flip to Phase 246 is the right safety boundary.

**Concerns**
- **HIGH:** `git rev-parse --short HEAD == ffaa8a0e` conflicts with running after Plans 01–03
  unless it means "production currently deployed Snapshot-A before mutation." Clarify the
  target of that check.
- **HIGH:** Restarting `steering.service` is a global steering event. ATT config may be
  untouched, but ATT as a control is still exposed to service restart effects.
- **HIGH:** "Recommend >= one diurnal cycle" is a long production exposure if backend switching
  is mutating/restarting. Add a short canary and hard abort conditions before long runs.
- **HIGH:** "Return steering to safe state (Snapshot-A)" is ambiguous. Snapshot-A as code anchor
  and "icmplib backend under new code" are different states.
- **MEDIUM:** The final SAFE-17 evidence should be generated after all implementation commits and
  should fail if health.py was required but not included in expected Phase 245 hunks.

**Suggestions**
- Split preflight checks into: production-deployed ref, local implementation ref, rollback ref.
- Record ATT control health before and after every planned restart, not just during sample
  windows.
- Add automatic abort on: missing `wanctl_backend` count growth, stale `/health`, unexpected
  restart, backend mismatch, or fallback fraction breach.
- Make Plan 04 call rollback with the same `--confirm` semantics Plan 03 requires.

**Risk Assessment: HIGH** — This is live production mutation of the RTT source for steering.
With the above fixes it becomes a controlled operator run; without them, the evidence can be
confounded and rollback may not actually restore the stated anchor.

---

## OpenCode Review (qwen3-32b)

> **Reviewer note:** OpenCode (qwen3-32b) performed live codebase inspection before producing
> this review. Some findings reference implementation details confirmed from source. One finding
> incorrectly references SQLite (not present in these plans) — flag as hallucination; other
> findings are substantive.

### Plan 01: SAFE-17 Verifier + Preregistration Scaffold

**Summary**: Establishes a preregistration mechanism for A/B test participants with SAFE-17
gate checks. The anchor-swap-only clone approach is efficient and reduces error surface.

**Strengths**
- Preregistration is enforced via SAFE-17 gate; ensures only verified entries are registered.
- Uses blob-SHA-based registration with deterministic assignment to avoid bias.
- Preregistration state is persisted via git (blob SHA + descendancy proof), enabling auditability.

**Concerns**
- **HIGH:** No mechanism to prevent duplicate preregistration via the same commit. Could allow
  gaming if the thresholds are amended before data collection completes. *(Partially addressed
  by AMENDMENT_ID convention, but not machine-enforced.)*
- **MEDIUM:** Preregistration window duration not defined. Could lead to stale entries or a
  preregistration-to-collection gap that weakens the integrity story.
- **LOW:** No explicit confirmation step for registration completion. Operator may not have
  clear signal that the prereg commit is the correct one.

**Suggestions**
- Add a `unique` constraint or hash-check on the preregistered blob SHA before any evidence
  commit is allowed to descend from it.
- Add `registration_expiry_sec` or a window start/end timestamp to the thresholds JSON.
- Log a registration confirmation message upon successful `record` subcommand execution.

**Risk Assessment: MEDIUM** — Preregistration scaffolding is sound but needs tighter amendment
protection before it can truly prevent post-hoc threshold gaming.

---

### Plan 02: daemon.py Live-Path Flip (3 Edits)

**Summary**: Implements minimal changes to `daemon.py` to flip the RTT source at the seam.
The three-edit-site design is conservative and correct, and reading actual source confirms the
seam is already constructed but dormant.

**Strengths**
- Changes are minimal and isolated (3 edit sites).
- Uses config-driven backend selection for safe switchover.
- No code path alteration beyond the three identified edit sites.

**Concerns**
- **HIGH:** No exception handling in the `probe()` failure path. If `probe()` raises an
  exception (subprocess crash, fping binary missing at runtime, socket error), the daemon
  may crash before reaching the autorate fallback.
- **HIGH:** No explicit fallback path on a raised exception from `probe()`. The plan's behavior
  tests cover `probe()` returning `None`, but not `probe()` raising.
- **MEDIUM:** No logging of backend switch events for observability during the live A/B.

**Suggestions**
- Add `try/except` around the probe call; on exception, log rate-limited and fall through to
  the existing autorate_health chain.
- Add a `probe_exception_count` metric to `_rtt_source_counts` for observability.
- Add `logger.debug` on seam-first success showing backend name and RTT value.

**Risk Assessment: HIGH** — Risk of daemon crash under failure. The `try/except` fix is
required before production deployment.

---

### Plan 03: Gate-Eval + A/B Run + Rollback Scripts

**Summary**: Implements 6-dimension gate evaluation, interleaved crossover test, and rollback
scripts. The keep-icmplib-as-pass design is correct and prevents forced outcome bias.

**Strengths**
- 6-dimension gate covers RTT, cycle budget, loss, backend fraction, restarts, and steering
  stability.
- Interleaved crossover design ensures the same diurnal conditions for both backends.
- Rollback script correctly confirms `/health` state after revert.

**Concerns**
- **HIGH:** `MAX_DAEMON_RESTARTS=0` conflicts with the interleaved design if each backend window
  requires a steering restart to apply. The threshold needs to account for planned apply-restarts.
- **HIGH:** `HEAD==ffaa8a0e` check in the rollback path is ambiguous after Plans 01–03 land new
  commits on the implementation branch. Clarify whether this check targets the production host
  deployment ref or the local repo state.
- **MEDIUM:** No test of rollback script in a staging/dry-run mode before production execution.

**Suggestions**
- Define `MAX_PLANNED_RESTARTS` separately from `MAX_DAEMON_RESTARTS` (unexpected restarts);
  the gate-eval should check both independently.
- Replace `HEAD` check with production-host-side `git rev-parse HEAD` query, not local repo.
- Add a rollback self-test mode (without `--confirm`) that validates the plan steps via
  dry-run printing plus a read-only `/health` scrape.

**Risk Assessment: HIGH** — Restart accounting mismatch and HEAD check ambiguity must be
resolved before the scripts can safely run against production.

---

### Plan 04: Production Execution with Operator Checkpoints

**Summary**: Executes A/B test in production with operator checkpoints at key decision points.
The checkpoint design is appropriate for a 24/7 system.

**Strengths**
- Checkpoints are at the right decision points (preflight, seam-live confirm, verdict compute,
  rollback confirm).
- Human-in-the-loop at 3 critical mutation nodes.
- Full rollback path documented and operator-gated.

**Concerns**
- **HIGH:** Checkpoint timing is not synchronized with real-time observability. If the operator
  is unavailable during a window transition, the A/B may continue in an indeterminate state.
- **MEDIUM:** No automated alert on checkpoint delay or missed window.
- **LOW:** No verification that operator approval was given by an authenticated operator (not
  just a resume signal).

**Suggestions**
- Add `CHECKPOINT_TIMEOUT_SEC` with an automatic safe-stop if the operator does not respond
  within the window.
- Use `/health` NRestarts and `wanctl_backend` count growth as automated abort triggers within
  each window, not just at the verdict step.
- Require operator to acknowledge the verdict outcome explicitly before the rollback step.

**Risk Assessment: HIGH** — Risk of drift if checkpoints are missed without automated safe-stop.
The checkpoint timeout and automated abort triggers should be implemented before production run.

---

## Consensus Summary

Both reviewers flagged consistent themes across the four plans.

### Agreed Strengths

- **Correct ordering**: preregistration (thresholds committed) before daemon flip before live
  data — both reviewers confirmed this as the right structural approach.
- **keep-icmplib as a valid passing close**: both reviewers confirmed this as the right design;
  forcing a flip from weak evidence is explicitly prevented.
- **Minimal daemon.py edit surface**: three identified edit sites with fallback chain preserved
  is a sound minimal-diff approach for a production control path.
- **`--confirm`-gated mutation**: both reviewers agreed this is the right posture for a 24/7
  production network control system.
- **Operator checkpoints in Plan 04**: appropriate for a system where production RTT source is
  being switched.

### Agreed Concerns

- **HIGH — probe() exception handling absent** (Plan 02): both reviewers independently flagged
  that `probe()` raising an exception (as opposed to returning `None`) is not handled and could
  crash the daemon before reaching the autorate fallback. A `try/except` wrapper around the
  probe call is required.
- **HIGH — MAX_DAEMON_RESTARTS=0 conflicts with interleaved backend switching** (Plan 03): both
  reviewers noted that if each window flip requires a `steering.service` restart to apply,
  `MAX_DAEMON_RESTARTS=0` will trivially fail. Planned vs unexpected restart accounting must be
  separated in the thresholds.
- **HIGH — HEAD==ffaa8a0e check is ambiguous** (Plans 03/04): both reviewers flagged that after
  Plans 01–03 land commits, the local repo HEAD will no longer be `ffaa8a0e`. The check in
  Plan 04 Task 1 should target the production-deployed ref on `cake-shaper`, not the local repo
  state.
- **HIGH — "Snapshot-A rollback" is ambiguous** (Plans 03/04): "returning to Snapshot-A" means
  config-revert to icmplib under Phase-245 code — NOT a code rollback to the `ffaa8a0e` commit.
  The rollback script documentation and Plan 04 task descriptions should use unambiguous language.
- **MEDIUM — wanctl_backend count may not surface in /health** (Plan 02): if the counts dict
  update in Plan 02 Task 1 is not also surfaced in the health builder, AB-03's
  `min_backend_cycle_fraction` gate cannot read it from `/health`.

### Divergent Views

- **OpenCode (qwen3-32b)** flagged checkpoint timeout automation (MEDIUM-HIGH), suggesting
  automated safe-stop on operator absence. **Codex** did not raise this but did flag ATT
  control exposure to service restarts as a gap Codex considered HIGH.
- **Codex** raised gate-eval needing per-window counter deltas (not cumulative counts) — a
  subtle but important correctness gap not raised by OpenCode.
- **Codex** raised rollback evidence integrity (gate on raw evidence hashes, reject aggregate-
  only inputs) — not raised by OpenCode.
- **OpenCode** raised preregistration amendment protection (unique constraint / hash-check) as
  HIGH — Codex raised it as a suggestion rather than a severity finding.

---

*To incorporate feedback into planning:*

```
/gsd:plan-phase 245 --reviews
```
