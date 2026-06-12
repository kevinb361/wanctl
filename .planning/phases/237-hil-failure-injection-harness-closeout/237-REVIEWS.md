---
phase: 237
reviewers: [codex]
reviewed_at: 2026-06-12T23:14:22Z
plans_reviewed: [237-01-PLAN.md, 237-02-PLAN.md, 237-03-PLAN.md, 237-04-PLAN.md]
---

# Cross-AI Plan Review — Phase 237

> Reviewer environment: executed from Claude Code CLI (claude self-skipped for independence); Codex invoked as the external reviewer.

## Codex Review

I spot-checked the referenced repo patterns: `phase225-safe13-boundary-check.sh`, `silicom-bypass`, `deploy.sh`, existing Silicom tests, and the Phase 237 research/pattern docs. Overall, the plans are well-scoped and aligned with the phase: bash/tests/docs only, compose `silicom-bypass`, keep SAFE-16 out of the controller path. The main risks are shell trap semantics, deployed harness dependencies, and overclaiming what the SAFE evidence proves.

## 237-01-PLAN

### Summary
Good RED-first scaffold. It pins the safety contract before implementation and copies a proven SAFE boundary tool. Risk is mostly test quality, not production behavior.

### Strengths
- RED tests for HARN-01..05 before `scripts/silicom-test` exists.
- Includes both mid-run failure and signal restore tests, which are the right HARN-04 pressure points.
- SAFE-16 tool is copied from an existing proven pattern and anchored to `v1.51`.
- Uses `spec-modem` only and keeps tests off `wanctl.*`.

### Concerns
- **MEDIUM:** `test_restore_on_signal` can be flaky or weak unless the fake CLI deliberately blocks after `disc`; otherwise the harness may exit before SIGTERM lands.
- **MEDIUM:** The RED verifier greps for generic “error”; this could hide collection/import failures. It should prove tests are collected and fail for expected missing harness behavior.
- **LOW:** The `att-modem` grep acceptance is wrong: `grep -c ... | grep -v '^#'` does not filter comment lines meaningfully.
- **LOW:** The SAFE copy instructions should explicitly update the JSON `notes` string from SAFE-13 to SAFE-16, not just header/final echo.
- **LOW:** `key_links` has `ANCHOR=.v1.51`, but the real assignment should be `ANCHOR="v1.51"`.

### Suggestions
- Add fake CLI support for `SILICOM_TEST_BLOCK_AFTER=disc` or similar for the signal test.
- Assert collected test names before expecting RED.
- Replace ATT checks with `grep -nE '^[^#]*att-modem|--both-wan-confirm'`.

### Risk Assessment
**LOW-MEDIUM.** No live mutation, no controller path. Main risk is building tests that do not actually prove the trap behavior.

## 237-02-PLAN

### Summary
This is the critical plan. The decomposition is right, but the trap design needs tighter Bash semantics before I would trust it around live WAN state.

### Strengths
- Composes `silicom-bypass` only; no raw `bpctl_util`.
- Requires trap registration before mutation.
- Restores with idempotent `off`/`conn`, which matches the existing CLI contract.
- Includes path traversal guard for `chaos`.
- Keeps scheduling out of scope.

### Concerns
- **HIGH:** `trap restore_all_touched EXIT INT TERM` plus `return "$rc"` is not a robust signal handler. For `INT`/`TERM`, the handler should restore and then exit with a signal-derived code. Returning from a signal trap can allow script continuation.
- **HIGH:** The fake/live gate separation is underspecified. Tests need to bypass `SILICOM_TEST_LIVE_CONFIRM`, but real custom paths should not accidentally bypass live gating.
- **HIGH:** Installed harness defaults reference `scripts/phase213-steering-snapshot.sh` and `scripts/phase213-health-poller.sh`, but Plan 03 does not install those helpers. The standalone deployed harness may not capture state.
- **MEDIUM:** Background health poller lifecycle is underdefined. The trap should kill/wait poller PIDs without masking the original rc.
- **MEDIUM:** ATT “louder gate” is required but not concretely named or tested.
- **MEDIUM:** HARN-05 needs explicit `result.json`, raw tool output, and journal extraction behavior, including best-effort failure handling.
- **MEDIUM:** `chaos` sources shell files. Path traversal guard is necessary, but add a strict scenario-name regex and document that deployed scenario dir is root-owned.

### Suggestions
- Use separate handlers: `EXIT` preserves rc; `INT`/`TERM` restore, disable duplicate traps if needed, then `exit 130/143`.
- Add tests for ATT refusal without the louder gate.
- Install or vendor the capture helpers, or set deployed defaults to absolute installed paths.
- Track `HEALTH_POLLER_PIDS`, kill/wait them in cleanup, then restore pairs.

### Risk Assessment
**HIGH until trap/gate/dependency details are fixed.** The design is sound, but this is the live-WAN mutation layer.

## 237-03-PLAN

### Summary
Reusing `deploy.sh --silicom-bypass-only` is the right DEPLOY-03 decision. The main gap is that it installs the harness but not all runtime dependencies the harness defaults to using.

### Strengths
- Single documented standalone path avoids installer drift.
- Preserves off-by-default posture: daemon-reload only, no enable/start.
- Extends repo-owned artifact tests and docs.
- Keeps deployment scoped to scripts/docs/tests.

### Concerns
- **HIGH:** Deploying `silicom-test` without `phase213-steering-snapshot.sh` and `phase213-health-poller.sh` makes HARN-05 fragile or unusable outside repo CWD.
- **MEDIUM:** Existing deploy cleanup is not trap-based; added `scp`/`ssh` steps increase chances of leaking remote tmp dirs on failure.
- **MEDIUM:** Artifact ownership parsing may break if scenarios are installed via glob/loop. The plan notes this, but the test change must handle it deliberately.
- **LOW:** The acceptance says no second mktemp inside `deploy_silicom_bypass`, but current nested `deploy_watchdog_artifacts` already creates its own staging dir. Avoid making this assertion too literal.
- **LOW:** Dry-run output should include every runtime dependency, not only harness/scenarios.

### Suggestions
- Install capture helpers under a stable path such as `/usr/local/libexec/wanctl/`, and set harness defaults accordingly.
- Add deploy tests asserting helper references if they become harness dependencies.
- Use a cleanup trap around `remote_tmp` in `deploy_silicom_bypass` if touching this area anyway.

### Risk Assessment
**MEDIUM.** Deployment is off-by-default, but incomplete installed dependencies would undermine DEPLOY-03.

## 237-04-PLAN

### Summary
The closeout shape is right: ignore runtime HIL artifacts, regenerate SAFE-16 evidence, and require operator sign-off. The evidence wording should be tightened so nobody mistakes protected-path cleanliness for global worktree cleanliness.

### Strengths
- `.gitignore tests/silicom/` is the right default for runtime HIL output.
- SAFE-16 anchor is correct: `v1.51` resolves to `531f36ac36ceccb2e4dd2d47edd84fba9081c053`.
- Human checkpoint is appropriate for milestone close.
- Explicit stop condition on controller-path diff is correct.

### Concerns
- **HIGH:** `dirty_tree_clean` in the copied SAFE tool only covers protected controller paths plus `configs/att.yaml`; it does not prove the whole worktree is clean.
- **MEDIUM:** SAFE-16 is detected at boundaries, not structurally guaranteed by the plans. Add per-wave protected-path checks to catch drift earlier.
- **MEDIUM:** The boundary tool is “read-only git inspection,” but it does write the evidence JSON. Phrase that precisely.
- **LOW:** `237-04-SUMMARY.md` is an output/signoff artifact but not listed in `files_modified`.

### Suggestions
- Add `git diff --exit-code v1.51..HEAD -- src/wanctl configs/att.yaml` to every wave verification.
- Add separate `git status --short` reporting for milestone close, distinct from SAFE JSON fields.
- Include summary/signoff file in the plan metadata.

### Risk Assessment
**MEDIUM.** The SAFE mechanism is strong, but the plan overstates one field and relies on final detection unless per-wave checks are added.

## Overall Risk

**MEDIUM, trending LOW after fixes.** The phase goals are achievable and the scope discipline is good. The key fixes before execution are: make signal traps exit correctly, make live/fake gating explicit and tested, install or path the capture helpers, define result/journal schema concretely, and clarify SAFE evidence semantics. SAFE-16 is well protected by final evidence, but it is not structurally guaranteed unless each wave also runs protected-path diff checks.

---

## Consensus Summary

Single external reviewer (Codex) this cycle, so "consensus" reflects Codex's findings cross-checked against the plan text and the binding milestone constraints (SAFE-16, default-safe spec-modem, no scheduling, compose-silicom-bypass-only). The review is substantive and spot-checked against live repo patterns (`phase225-safe13-boundary-check.sh`, `silicom-bypass`, `deploy.sh`, existing Silicom tests). Overall verdict: **MEDIUM, trending LOW after fixes** — phase goals achievable, scope discipline good, but five execution-detail fixes should land before/early in execution.

### Agreed Strengths
- RED-first scaffold pins the HARN-01..05 safety contract (incl. both mid-run-failure AND signal restore proofs) before `scripts/silicom-test` exists.
- Harness composes `silicom-bypass` verbs only — never raw `bpctl_util`; idempotent `off`/`conn` restore matches the existing CLI contract.
- DEPLOY-03 reuses the proven `deploy.sh --silicom-bypass-only` standalone path (avoids installer drift) and preserves the off-by-default posture (daemon-reload only).
- SAFE-16 anchor is correct (`v1.51` → `531f36ac...`); explicit stop-on-controller-diff guard; human checkpoint at milestone close.
- spec-modem is the only exercised pair; tests stay off `wanctl.*`.

### Agreed Concerns (highest priority — the 6 HIGHs)
1. **(237-02) Signal-trap correctness** — `trap restore_all_touched EXIT INT TERM` + `return "$rc"` is not a robust signal handler; for INT/TERM the handler should restore then `exit` with a signal-derived code (130/143). Returning from a signal trap can allow script continuation.
2. **(237-02) Live/fake gate separation underspecified** — tests must bypass `SILICOM_TEST_LIVE_CONFIRM`, but real custom paths must not accidentally bypass live gating; needs explicit, tested boundary.
3. **(237-02 + 237-03) Capture-helper deploy gap** — the installed harness defaults to `scripts/phase213-steering-snapshot.sh` / `phase213-health-poller.sh`, but Plan 03 does not install them. Deployed harness may not capture state → HARN-05 fragile/unusable outside repo CWD. (Raised as HIGH in both 237-02 and 237-03.)
4. **(237-04) `dirty_tree_clean` semantics overstated** — the copied SAFE tool's `dirty_tree_clean` only covers protected controller paths + `configs/att.yaml`; it does NOT prove the whole worktree is clean. Evidence wording must not let protected-path cleanliness be read as global cleanliness.

### Divergent Views
None — single reviewer this cycle. The MEDIUM-severity items worth tracking alongside the HIGHs: background health-poller PID lifecycle in the trap (kill/wait without masking rc); ATT "louder gate" not concretely named or tested; HARN-05 result.json/journal-extract schema underspecified; SAFE-16 detected-not-structurally-guaranteed (add per-wave `git diff --exit-code v1.51..HEAD -- src/wanctl configs/att.yaml`); deploy remote_tmp cleanup not trap-based.

### Recommended pre-execution fixes (Codex)
- Separate EXIT vs INT/TERM handlers: EXIT preserves rc; INT/TERM restore then `exit 130/143`.
- Add fake-CLI block-after-disc seam (e.g. `SILICOM_TEST_BLOCK_AFTER=disc`) so the signal test is deterministic, not racy.
- Install/vendor the phase213 capture helpers under a stable path (e.g. `/usr/local/libexec/wanctl/`) and set harness defaults to absolute installed paths; add deploy tests asserting the helper references.
- Define HARN-05 `result.json` + journal-extract schema and best-effort failure handling concretely.
- Add per-wave protected-path diff check (`git diff --exit-code v1.51..HEAD -- src/wanctl configs/att.yaml`) so SAFE-16 drift is caught early, not only at the boundary; tighten the "read-only git inspection" wording (the tool does write evidence JSON) and report `git status --short` separately at close.
- Minor: fix `att-modem` grep acceptance (`grep -nE '^[^#]*att-modem|--both-wan-confirm'`); update SAFE JSON `notes` SAFE-13→SAFE-16; list `237-04-SUMMARY.md` in `files_modified`.
