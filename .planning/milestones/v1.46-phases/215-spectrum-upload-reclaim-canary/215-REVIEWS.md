---
phase: 215
reviewers: [codex]
reviewed_at: 2026-05-29T13:59:54Z
plans_reviewed: [215-01-PLAN.md, 215-02-PLAN.md, 215-03-PLAN.md]
---

# Cross-AI Plan Review — Phase 215

## Codex Review

**Overall Summary**
The phase structure is sound: tooling first, Snapshot A/read-only evidence second, one approved production mutation last. The risky part is not the `18 -> 20` YAML edit; it is false confidence from stale or ambiguous measurement gates. As written, I would not execute Plan 03 until the baseline reference, VOID semantics, and rollback mechanics are tightened.

**215-01 Review**
Summary: Good Wave 0 scope, but the extractor/gate contract has a couple of blocking ambiguities.

Strengths:
- Keeps production untouched.
- Preserves the existing download extractor contract in `scripts/phase214-extract.py`.
- Adds offline tests before live canary work.
- Models the gate after a proven verdict/exit-code pattern.

Concerns:
- **HIGH:** If `main()` still calls download `extract_flent_throughput()` unconditionally, upload artifacts will still fail before `upload_throughput` is useful.
- **HIGH:** Hard-coded `58.7`, `75.9`, `12.9` conflicts with the stated fresh leg-A A/B baseline. The gate should accept leg-A extract/health inputs and derive thresholds from them, while recording the old Phase 213 reference as a sanity check.
- **HIGH:** `void` vs `abort` exit behavior is unclear. A nonzero gate under `set -e` can prevent rollback/report logic unless Plan 03 captures the exit code deliberately.
- **MEDIUM:** "Sustained" `signal_outlier_rate` and warn-bloat excursion are not numerically defined.
- **MEDIUM:** `alerting_fire_count` is global; use alert-window rows filtered to Spectrum/flapping type, or document why global count is acceptable.
- **MEDIUM:** `TCP totals` is an ambiguous upload fallback key. Prefer upload-specific series unless metadata proves an upload-only test.

Suggestions:
- Add `--throughput-direction upload` or equivalent, preserving the default download behavior.
- Make gate inputs explicit: `--baseline-extract`, `--candidate-extract`, `--baseline-health`, `--candidate-health`.
- Define VOID thresholds exactly, e.g. p90/max policy for `signal_outlier_rate`, and units for `load_rtt_delta_us`.
- Add a `--score-only`/`--self-test` path that exercises the real scoring code, not fixture-specific stubs.

Risk: **MEDIUM-HIGH** until the gate contract is fixed; **LOW-MEDIUM** after that.

**215-02 Review**
Summary: Snapshot A is well-designed, but leg-A capture placement undermines same-session A/B.

Strengths:
- Snapshot A contents are thorough and reversible.
- Uses bound `/health` endpoint, not loopback.
- Validates loaded ceiling through DB evidence, not health echo.
- Explicitly confirms leg-A is non-VOID.

Concerns:
- **HIGH:** Leg A is in a separate wave from Plan 03. If approval/mutation happens hours later, D-10 "same session" is no longer true.
- **HIGH:** Capturing raw repo/deployed config into evidence will include `${ROUTER_PASSWORD}` / `${DISCORD_WEBHOOK_URL}` placeholders unless redacted; the acceptance grep will likely fail.
- **HIGH:** Revert instructions using `git checkout configs/spectrum.yaml` can discard unrelated user/worktree edits.
- **MEDIUM:** A 120s `tcp_upload` run is read-only but still production-impacting traffic. `autonomous: true` is questionable without an agreed window.
- **MEDIUM:** The config-snapshot query is not specified enough; the value lives in JSON labels in the `metrics` table.

Suggestions:
- Keep Plan 02 to Snapshot A only, or require Plan 03 to rerun leg-A immediately before mutation if leg-A is stale.
- Store only `.redacted.yaml` / `.redacted.json` evidence.
- Replace `git checkout` rollback with a targeted YAML restore of `continuous_monitoring.upload.ceiling_mbps`.
- Include the exact SQLite query using `json_extract(labels, '$.autorate.upload_ceiling_mbps')`.

Risk: **MEDIUM**, mostly from timing and evidence hygiene.

**215-03 Review**
Summary: The mutation/restart/rollback discipline is mostly right, but execution needs stronger preflight and fail-path handling.

Strengths:
- Correctly requires operator approval.
- Mutates only the intended config knob in concept.
- Explicitly restarts the daemon after deploy.
- Uses DB/log proof because `/health` does not expose ceiling.
- Requires rollback on non-pass outcomes.

Concerns:
- **HIGH:** The single-knob diff guard only checks that floor/setpoint/step lines are untouched; it does not prove no unrelated config drift is being deployed.
- **HIGH:** Gate nonzero exits must not short-circuit rollback. The plan should explicitly run gate with captured rc, read `verdict.json`, then branch.
- **HIGH:** VOID retry policy is underspecified. If the candidate window is unscorable, the safe default should be rollback after a bounded retry count/window.
- **MEDIUM:** The expected CAKE log string may be wrong; current code logs params, likely containing `bandwidth: 20000kbit`, not `bandwidth_kbit=20000`.
- **MEDIUM:** 120s may be too short to validate alert-flapping cooldown behavior; add a passive post-change observation window or make that limitation explicit.

Suggestions:
- Before deploy, parse pre/post YAML and assert the only semantic delta is `continuous_monitoring.upload.ceiling_mbps: 18 -> 20`.
- Require a clean or allowlisted worktree for `src/wanctl/` and `configs/spectrum.yaml` before deploy.
- Use targeted rollback to ceiling `18`, deploy, restart, verify DB row `18`, then `canary-check`.
- Add a bounded post-pass watch, especially for floor hits and flapping alerts.

Risk: **MEDIUM-HIGH as written** because false pass/failed rollback handling is still possible. With the above changes, the live mutation risk becomes **MEDIUM** and appropriate for a conservative one-knob canary.

---

## Consensus Summary

Single reviewer (Codex). The structure — tooling → read-only evidence → one gated mutation — was endorsed. The flagged risk is not the YAML edit itself but **false confidence from the measurement/gate contract and fail-path mechanics**. Highest-priority items below would block a safe Plan 03 execution if left unaddressed.

### Top Concerns (HIGH)

1. **Hard-coded gate thresholds vs. fresh leg-A baseline (Plan 01).** `58.7 / 75.9 / 12.9` are baked in, but the design says the gate scores leg-B against a same-session leg-A. Either derive thresholds from leg-A inputs (and keep the Phase 213 numbers as a sanity check) or document why the static numbers are authoritative.
2. **Gate exit-code vs. rollback short-circuit (Plans 01 + 03).** A nonzero gate exit under `set -e` can skip the rollback/report branch. Plan 03 must run the gate with a captured rc, read `verdict.json`, then branch deliberately. `void` vs `abort` exit semantics need to be pinned in Plan 01.
3. **VOID retry policy underspecified (Plans 01 + 03).** "Re-run a VOID leg, never score it" has no bound. Safe default: rollback after a bounded retry count/window so an unscorable candidate can't strand production at ceiling 20.
4. **`git checkout configs/spectrum.yaml` rollback is too broad (Plans 02 + 03).** It can discard unrelated worktree edits. Replace with a targeted restore of `continuous_monitoring.upload.ceiling_mbps: 18`.
5. **Same-session A/B drift (Plan 02).** Leg-A in Wave 2, mutation in Wave 3 behind a human checkpoint — if approval lands hours later, D-10 "same session" is violated. Either keep Plan 02 to Snapshot A only and capture leg-A immediately before mutation, or require Plan 03 to re-capture leg-A if stale.
6. **Single-knob diff guard is incomplete (Plan 03).** It only checks floor/setpoint/step lines are untouched; it doesn't prove the absence of unrelated config drift. Add a pre/post YAML semantic-delta assertion that the ONLY change is the ceiling, and require a clean/allowlisted worktree before deploy.

### Worth Verifying Before Execution (MEDIUM)

- **CAKE log proof string** (`bandwidth_kbit=20000`) may not match what the code actually logs (likely `bandwidth: 20000kbit`). Verify the real log format against `src/wanctl` before relying on it as deploy proof.
- **Config-snapshot DB query** under-specified — value lives in JSON labels; use `json_extract(labels, '$.autorate.upload_ceiling_mbps')`.
- **`alerting_fire_count` is global** — filter to Spectrum/flapping rows or document why global is acceptable.
- **120s window** may be too short to exercise flapping-cooldown behavior; add a bounded post-pass watch or state the limitation.
- **`TCP totals` ambiguous fallback key** for upload extraction — prefer upload-specific series.
- **Evidence hygiene** — store only redacted `.redacted.yaml`/`.redacted.json`; raw config carries `${ROUTER_PASSWORD}`/`${DISCORD_WEBHOOK_URL}` placeholders that will trip the acceptance grep.

### Divergent Views

N/A — single reviewer.

## To incorporate feedback into planning

```
/gsd-plan-phase 215 --reviews
```
