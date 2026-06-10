---
phase: 231
reviewers: [codex]
reviewed_at: 2026-06-10T03:13:10Z
plans_reviewed: [231-01-PLAN.md, 231-02-PLAN.md, 231-03-PLAN.md]
---

# Cross-AI Plan Review — Phase 231

## Codex Review

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

## Consensus Summary

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
