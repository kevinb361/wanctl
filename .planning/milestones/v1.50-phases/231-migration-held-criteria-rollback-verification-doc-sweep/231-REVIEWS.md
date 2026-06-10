---
phase: 231
reviewers: [codex]
reviewed_at: 2026-06-10T03:33:50Z
plans_reviewed: [231-01-PLAN.md, 231-02-PLAN.md, 231-03-PLAN.md]
convergence_cycle: 2
plans_revision: 36c76305
---

# Cross-AI Plan Review — Phase 231

# Cycle 2 (current) — review of revised plans (commit 36c76305)

## Codex Review — Cycle 2

### Cycle-1 HIGH Resolution

| Concern | Verdict | Evidence |
|---|---:|---|
| HIGH-1 C3 underspecified | RESOLVED | 231-01 defines `C3_MAX_TOTAL=5`, `C3_MAX_DISTINCT_HOURS=2`, `C3_CLEAN_TRAILING_HOURS=6` and states the verdict "never depends on post-hoc operator judgment." The pass rule is predeclared and script-encoded. |
| HIGH-2 rollback before SOAK-01 | RESOLVED | 231-01 requires SOAK-01 live capture before any 231-02 exercise. 231-02 Task 3 hard-gates live exercise on existing, operator-accepted `231-SOAK01-EVIDENCE.md` and says never offer it early. |
| HIGH-3 watchdog/unit inventory ambiguity | RESOLVED | 231-01 now lists seven active / three inactive expected units including `steering.service`, `silicom-bypass-watchdog@spectrum.service`, and inactive `silicom-bypass-watchdog@att.service`. 231-02 explicitly defines external/native rollback watchdog states per WAN. |
| HIGH-4 SAFE "last task" invalidation | RESOLVED | 231-03 adds final ordering, parent-reference semantics, post-boundary `.planning/**` allowlist, and a later audit command using `git log --name-only <tracking-commit>..HEAD`. |

### 231-01 Summary

Strong plan. The SOAK-01 criteria are now concrete, read-only, and evidence-oriented. The C3 fix is real, not cosmetic. The evaluator has good fail-closed behavior, unit inventory awareness, timeout requirements, and raw evidence capture.

Strengths:
- Objective sustained-error rule with fixed constants.
- Explicit read-only boundary: curl, ssh, journalctl, sqlite SELECT, `tc qdisc show`.
- Captures both formal criteria and live outputs with UTC timestamps.
- Adds the Spectrum watchdog and `steering.service` gap from cycle 1.
- Uses repo config as qdisc envelope source instead of hardcoded rates.

Concerns:
- MEDIUM: Step A pipes `script --json | python3 -m json.tool`; without `set -o pipefail`, a FAIL exit from the evaluator can be masked by successful JSON formatting.
- MEDIUM: Tests lean heavily on source-text assertions. For evidence-critical parsing, fake-output tests should exercise C3 journal parsing, qdisc unit conversion, metrics SQL construction, and fail-closed paths.
- LOW: C3 says "distinct UTC hours," but `journalctl -o short-iso` does not by itself force UTC output. Use `TZ=UTC` remotely or parse `-o json` timestamps.
- LOW: C1 only checks HTTP 200 + `status: healthy`; if GREEN/GREEN is intended as part of "bridge health," make that explicit or record state as corroborating evidence.

Suggestions:
- Run live command as `set -o pipefail; bash ... --json | python3 -m json.tool`, and record the evaluator exit code.
- Add fake command fixtures for qdisc, sqlite, journal, and curl cases.
- Prefer `journalctl -o json` for C3 timestamp logic.

Risk: LOW-MEDIUM. Evidence validity is good; main risk is implementation/test brittleness.

### 231-02 Summary

The SOAK-02 plan is materially better. It defaults to the provable path, isolates production mutation behind two gates, and documents watchdog state transitions clearly. The optional live exercise is now correctly ordered after SOAK-01.

Strengths:
- Provable path can complete with no mutation.
- `--confirm` plus `--i-have-operator-approval` is the right shape.
- Per-WAN watchdog expectations are explicit and match the known ATT cake-specific watchdog issue.
- Dry-run includes rollback and return-to-cake sequences.
- Preflight captures raw outputs and exact `is-enabled == disabled` state.

Concerns:
- MEDIUM: Confirm mode should run a fresh preflight immediately before mutation. Task 2 preflight could be stale by the time Task 3 runs.
- MEDIUM: Return-to-cake verification after an exercised ATT rollback should include explicit bpctl/non-bypass/WDT state, not only health + soak-monitor. Prior ATT failure mode can look superficially healthy while bypassing Linux qdiscs.
- MEDIUM: If Spectrum is chosen for live exercise, the plan should explicitly pause/resume the Spectrum hourly validation cron or prove it cannot interfere.
- LOW: The gate permits live exercise after accepted `SOAK-01 FAIL`. That no longer invalidates captured evidence, but it should require an explicit remediation decision, not normal phase progression.
- LOW: "external trio" wording is slightly confusing for Spectrum, where the cake services are two plus the existing Spectrum watchdog.

Suggestions:
- Make `--confirm` internally call the same preflight and refuse mutation unless it passes at that moment.
- Add post-return checks: cake units active, native units inactive, watchdog state correct, bpctl non-bypass/WDT enabled for ATT, qdisc counters or cake log load plausibility.
- Add a Spectrum-cron handling step for any Spectrum exercise.

Risk: MEDIUM if live exercise is used; LOW if the provable path is accepted.

### 231-03 Summary

The doc sweep and SAFE closeout plan is solid and correctly depends on 231-01/231-02. The SAFE-14 ordering fix is adequate and audit-friendly. The doc work is scoped to the right files and preserves native mode instead of deleting it.

Strengths:
- Correctly frames native `wanctl@` as portable mode, external cake-autorate as deployed mode.
- Avoids timer-era resurrection and private IP leakage.
- Uses two-baseline SAFE model: `SAFE_BASE` for protected controller diff, `PHASE231_START` for scope accounting.
- Adds post-boundary `.planning/**` allowlist to handle summaries/metadata.

Concerns:
- MEDIUM: Automated private-IP verification shown in `<verify>` only checks `10.10.110.*`, while acceptance claims all RFC1918 ranges and private hostnames.
- LOW: Boundary wording says the "note's tracking commit is the LAST commit that touches anything outside `.planning/**`," but the boundary note itself is `.planning/**`; rephrase to avoid ambiguity.
- LOW: If the boundary note wants to include its own tracking commit hash, that cannot be known before the commit. Parent-reference semantics are fine, but the note should say that explicitly.

Suggestions:
- Strengthen doc leakage grep to cover `10.*`, `192.168.*`, `172.16-31.*`, and known private hostnames.
- In SAFE note, record `boundary_parent=<sha>` and audit `git log --name-only ${boundary_parent}..HEAD`, requiring all paths to be `.planning/**`.

Risk: LOW.

### Overall Verdict — Cycle 2

Ready to execute with minor amendments. The four cycle-1 HIGH concerns are resolved. I do not see a new HIGH issue. The main remaining risks are operational hygiene around the optional live rollback exercise and test depth for the new scripts. Defaulting SOAK-02 to the provable path keeps production risk acceptably low.

---

## Consensus Summary — Cycle 2

Single external reviewer this cycle (Codex). Convergence achieved: all 4 cycle-1 HIGH concerns judged RESOLVED, no new HIGH concerns raised. Remaining items are MEDIUM/LOW execution-hygiene amendments, suitable to fold in during execution rather than another replan cycle.

### Cycle-1 HIGH disposition

- HIGH-1 (231-01, C3 objectivity): RESOLVED — fixed constants `C3_MAX_TOTAL=5` / `C3_MAX_DISTINCT_HOURS=2` / `C3_CLEAN_TRAILING_HOURS=6`, script-encoded, no post-hoc judgment.
- HIGH-2 (231-02, ordering vs SOAK-01): RESOLVED — hard gate on operator-accepted `231-SOAK01-EVIDENCE.md` before any live exercise.
- HIGH-3 (watchdog/unit inventory): RESOLVED — seven-active/three-inactive inventory incl. `steering.service` and per-WAN silicom watchdog states for both modes.
- HIGH-4 (231-03, SAFE-14 ordering): RESOLVED — final-commit ordering, parent-reference semantics, post-boundary `.planning/**` allowlist with audit command.

### Remaining concerns (MEDIUM, fold into execution)

1. 231-01: `set -o pipefail` when piping evaluator `--json` output through `json.tool`; record evaluator exit code.
2. 231-01: add fake-output fixture tests for C3 journal parsing, qdisc unit conversion, metrics SQL, fail-closed paths (not just source-text assertions).
3. 231-02: `--confirm` must rerun preflight immediately before mutation (Task 2 preflight can go stale).
4. 231-02: post-return-to-cake verification on ATT must include bpctl non-bypass/WDT state, not just health + soak-monitor.
5. 231-02: pause/resume (or prove non-interference of) the Spectrum hourly validation cron if Spectrum is chosen for live exercise.
6. 231-03: broaden private-IP leakage grep from `10.10.110.*` to all RFC1918 ranges + known private hostnames.

### Verdict

Phase 231 plans are ready to execute. No further replan cycle required.

---

# Cycle 1 (historical) — review of original plans (commit eae957a9)

All 4 HIGH concerns below were addressed by the replan at commit 36c76305 and verified RESOLVED in cycle 2.

## Codex Review — Cycle 1

## 231-01 Plan Review

### Summary
Strong plan for SOAK-01. It correctly turns “migration held” from vibes into explicit criteria, keeps live checks read-only, and adds regression coverage around command construction. Main risk is ambiguity in the service-error criterion and some live-unit inventory drift.

### Strengths
- Defines criteria before evaluation, which is exactly what SOAK-01 needs.
- Read-only boundary is explicit: `curl`, `ssh`, `journalctl`, `tc qdisc show`, `sqlite3 -readonly`.
- Pulling qdisc envelopes from `configs/cake-autorate/config.*.sh` avoids stale hardcoded thresholds.
- Fail-closed JSON output is the right shape for committed evidence.
- Focused shellcheck + pytest coverage is appropriate.

### Concerns
- **HIGH:** `no_sustained_errors` is underspecified. “Zero errors OR manually assessed non-sustained” creates room for post-hoc judgment unless the script has an objective sustained-error rule.
- **MEDIUM:** The Spectrum watchdog inventory looks inconsistent with current patterns. `soak-monitor.sh` external mode scans Spectrum cake + bridge, ATT cake + bridge + ATT watchdog, plus `steering.service`; it does not include `silicom-bypass-watchdog@spectrum.service`.
- **MEDIUM:** The plan’s “six active/two inactive” corroboration should explicitly include `steering.service`, or clearly state why steering is out of SOAK-01.
- **MEDIUM:** Journal window uses `--since "2026-06-08"`; that is local-time ambiguous. Use an explicit timestamp/timezone.
- **LOW:** `tc qdisc show` bandwidth parsing needs robust Kbit/Mbit/Gbit conversion. `tc` may render `550Mbit`, `550000Kbit`, etc.

### Suggestions
- Make `no_sustained_errors` objective: either any err-priority line fails, or define a threshold/rule before execution.
- Align live unit lists with `scripts/soak-monitor.sh` external-mode logic, including `steering.service`.
- Use `--since '2026-06-08 00:00:00 UTC'` or record the exact local timezone.
- Add SSH/curl timeouts everywhere so a bad endpoint cannot hang the evaluator.
- Generate JSON through Python/jq helpers rather than hand-built shell strings.

### Risk Assessment
**MEDIUM.** The plan achieves SOAK-01 if the live-unit set and error criterion are tightened. Without that, it can produce evidence that looks formal but still depends on operator interpretation after the fact.

## 231-02 Plan Review

### Summary
Good rollback-verification structure: the provable path is default, production mutation is double-gated, and the script/test split is sensible. The major risk is the optional live exercise path: Spectrum watchdog behavior and return-to-cake recovery need to be more explicit before any production mutation.

### Strengths
- Correctly defaults to the non-mutating provable path.
- `--confirm` plus `--i-have-operator-approval` is a good safety gate.
- Preflight checks target the right rollback prerequisites: native unit/config/code present, native inactive, `Conflicts=` guard present.
- Historical ATT rollback citation is useful supporting evidence.
- Tests for dry-run/no-mutation behavior are well scoped.

### Concerns
- **HIGH:** Optional live rollback exercise can conflict with 231-01 if both Wave 1 plans run in parallel. A live exercise before SOAK-01 capture would invalidate “migration held” evidence.
- **HIGH:** Spectrum watchdog handling is under-specified. The template watchdog has `Wants=wanctl@%i.service`; the plan should say whether `silicom-bypass-watchdog@spectrum.service` is expected active/inactive in external mode and native rollback mode.
- **MEDIUM:** The re-migration path is described but not made as concrete or regression-tested as rollback. If live exercise is approved, recovery deserves the same exact rendered command sequence.
- **MEDIUM:** ATT preflight should check `/opt/bpctl-silicom/bpctl_util` executable, not only the directory.
- **MEDIUM:** `systemctl is-enabled` outputs are messier than “disabled or not-enabled”; normalize exact acceptable outputs.
- **LOW:** Add preflight JSON shape tests, not only source/dry-run assertions.

### Suggestions
- Add a hard ordering rule: no live rollback exercise until 231-01 SOAK-01 evidence is captured and accepted.
- Extend the rollback script to render a `return_to_cake` plan, even if mutation remains operator-gated/manual.
- Add explicit Spectrum watchdog preflight/state expectations.
- Verify external units are currently active before any live exercise.
- Test `bpctl_util` executable and ATT native watchdog env file presence.

### Risk Assessment
**MEDIUM-HIGH.** Provable path risk is low. Optional exercised rollback risk is materially higher unless ordering and recovery commands are tightened.

## 231-03 Plan Review

### Summary
The docs sweep is well scoped and the SAFE-14 proof is appropriately conservative. The biggest issue is ordering: “SAFE last” conflicts with later summary/metadata commits unless the plan handles parent-reference semantics very explicitly.

### Strengths
- Preserves portable native `wanctl@` docs instead of deleting valid generic guidance.
- Correctly adds external cake-autorate/state-bridge mode to README, DEPLOYMENT, CONFIGURATION, and ARCHITECTURE.
- Public-safe doc policy is explicit.
- SAFE-14 protected set and `SAFE_BASE=87980bdf...` are correctly pinned.
- Hot-path regression slice plus focused tests is the right verification mix.

### Concerns
- **HIGH:** Boundary proof “last task” can be invalidated by `231-03-SUMMARY.md` or GSD metadata commits after it. The plan mentions parent-reference semantics, but the execution ordering needs to be explicit.
- **MEDIUM:** Scope accounting only checks `scripts/ tests/ docs/ README.md`; it should also account for `.planning/phases/231-*` artifacts and summaries, or run a full diff allowlist.
- **MEDIUM:** Full suite is expected to fail with 21 known failures. Make sure that capture does not accidentally fail the plan runner.
- **MEDIUM:** `PHASE231_START` derivation is fragile if commits are squashed or files are introduced together. Prefer recording it once at phase start and reusing that exact SHA.
- **LOW:** The “no new private IPs” grep only checks `10.10.110.*`; broader private-IP/hostname checks would better enforce the doc policy.

### Suggestions
- Define final commit order explicitly: either include SAFE boundary + summary in one final tracking commit, or rerun SAFE after summary/metadata writes.
- Add full `git diff --name-only $PHASE231_START` allowlist including `.planning/phases/...`.
- Capture full-suite output with a non-blocking command and classify known failures in the artifact.
- Broaden doc leakage check for RFC1918 ranges and known private hostnames.
- Allow `docs/README.md` to remain untouched if no stale claim exists.

### Risk Assessment
**MEDIUM.** Docs work is low risk; SAFE-close semantics are the risky part. Fix the final-commit ordering and scope accounting, and this becomes low risk.

## Overall Assessment
The plans are generally strong and aligned with the phase goals. The main fixes before execution are: make SOAK-01 error criteria objective, align live unit/watchdog inventory with actual service patterns, prevent optional rollback exercise from racing SOAK-01 evidence, and make SAFE-14 truly final after all summaries/metadata.

---

## Consensus Summary — Cycle 1

Single external reviewer this cycle (Codex, gpt-5.5); consensus reflects one independent perspective.

### Agreed Strengths

- Read-only-by-default discipline across all three plans: SOAK-01 evaluator is strictly read-only, SOAK-02 defaults to the non-mutating provable path with double-gated mutation (`--confirm` + `--i-have-operator-approval`), and the doc sweep stays out of the controller path.
- Criteria-before-evaluation framing for SOAK-01 and thresholds sourced from repo-committed configs rather than hardcoded values.
- SAFE-14 protected set and pinned `SAFE_BASE` are correct; verification mix (shellcheck, focused pytest, hot-path regression slice) is appropriate.

### Agreed Concerns

Highest-priority items to address before/during execution:

1. **HIGH (231-01):** `no_sustained_errors` (C3) is underspecified — "zero errors OR operator-assessed non-sustained" allows post-hoc judgment. Define an objective sustained-error rule before evaluation.
2. **HIGH (231-02):** Wave-1 parallelism hazard — an optional live rollback exercise (231-02 Task 3, option 2) executed before 231-01's SOAK-01 live capture would invalidate the "migration held" evidence. Needs a hard ordering rule: no live exercise until SOAK-01 evidence is captured and accepted.
3. **HIGH (231-02):** Spectrum silicom watchdog (`silicom-bypass-watchdog@spectrum.service`, `Wants=wanctl@%i.service`) expected state is unspecified for both external mode and native rollback mode; 231-01's "six active / two inactive" corroboration may also be inconsistent with the actual external-mode unit inventory (incl. `steering.service`).
4. **HIGH (231-03):** SAFE-14 "last task" boundary proof can be invalidated by `231-03-SUMMARY.md` and GSD metadata commits landing after it. Final commit ordering / parent-reference semantics must be explicit, or the SAFE proof must be rerun after summary/metadata writes.

Secondary (MEDIUM): journal `--since "2026-06-08"` timezone ambiguity; `tc` bandwidth unit parsing (Kbit/Mbit/Gbit); re-migration path not rendered/regression-tested at parity with rollback; ATT preflight should test `bpctl_util` executable, not just the directory; `systemctl is-enabled` output normalization; 231-03 scope accounting should allowlist `.planning/phases/231-*`; full-suite 21-known-failures capture must not fail the plan runner; `PHASE231_START` SHA should be recorded once, not derived.

### Divergent Views

None — single reviewer. Per-plan risk: 231-01 MEDIUM, 231-02 MEDIUM-HIGH (provable path low; exercised path higher until ordering/recovery tightened), 231-03 MEDIUM (drops to LOW once SAFE-close ordering is fixed).
