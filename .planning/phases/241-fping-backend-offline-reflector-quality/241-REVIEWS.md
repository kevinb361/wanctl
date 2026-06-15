---
phase: 241
reviewers: [codex]
reviewed_at: 2026-06-15T21:11:28Z
plans_reviewed: [241-01-PLAN.md, 241-02-PLAN.md, 241-03-PLAN.md, 241-04-PLAN.md]
review_cycle: 2
note: "Re-review of post-replan plans (commit 617cd6fd). Prior cycle 1 HIGHs H1/H2/H3 confirmed FULLY RESOLVED; two NEW HIGHs raised."
---

# Cross-AI Plan Review — Phase 241

## Codex Review

Overall: the revised plans materially improve the prior version and the prior HIGH findings are resolved in the plan text. I would still require a small revision before execution because there are two new HIGH risks: a direct D-07 scheduling-decision contradiction, and a likely incorrect process-death capture return code in the bash fixture helper.

## 241-01-PLAN.md

### Summary
Strong backend implementation plan: new `fping_measurement.py`, combined stdout/stderr parsing, explicit parse-result seam, all-fail scorer feed, lifecycle tests, and no live wiring yet.

### Strengths
- H1 is directly addressed: `FpingParseResult` separates parsing from sample return, and scorer feed happens before `probe()` returns `None`.
- H2 is directly addressed: combined `stdout + "\n" + stderr` parsing, plus stderr-only tests.
- Good containment: one new allowlisted module, frozen controller files untouched.
- Good tests for `-` tokens, all-fail, unknown hosts, negative returncode, aggregation, and real `measurement_ms`.

### Concerns
- **HIGH:** Plan contradicts D-07 from the provided decisions. Context says “Reuse `BackgroundRTTThread`… No new scheduler thread”; Plan 01 says “a new `FpingThread`… BackgroundRTTThread is NOT edited.” Either the decision record must be updated with rationale, or the plan must follow D-07.
- **MEDIUM:** Return-code handling is inconsistent. Must-have says only expected fping return codes are parseable, but action says parse regardless of any non-negative returncode. `returncode=3`/usage errors should not feed scorer loss.
- **MEDIUM:** `_scorer_results` maps `loss is None` to `False`. That means missing/garbled/no parsed host lines can penalize reflectors even when loss was not actually measured.
- **MEDIUM:** FPING-01 says operator can select fping, but this plan explicitly says no factory/wiring and “inert/test-reachable.” That is okay for “offline backend,” but not okay if FPING-01 is marked complete here.
- **LOW:** `_build_command()` discovers `self._binary_path` but runs `"fping"` rather than the resolved path.

### Suggestions
- Reconcile D-07 before execution.
- Restrict parseable return codes to `{0, 1, 2}`; treat `>2` as subprocess/config failure with no scorer feed.
- Add `parsed_hosts` or `observed_hosts` to `FpingParseResult`; only feed scorer for measured loss, or explicitly test/justify missing-host-as-fail.
- Mark FPING-01 as partially satisfied until Phase 242 factory/wiring, unless Phase 241 adds actual selectable construction.

### Risk Assessment
**MEDIUM-HIGH** until D-07 and return-code/scorer semantics are clarified.

## 241-02-PLAN.md

### Summary
Good verifier/validator plan: clones Phase 240 SAFE-17 verifier, expands allowlist, adds fping knob validators, and registers `measurement.fping.*`.

### Strengths
- M2 is fully addressed: all `measurement.fping.*` keys, including `timeout_grace_sec`, are registered in `KNOWN_AUTORATE_PATHS`.
- Keeps validator additions additive and absent-key-safe.
- Mirror verifier tests preserve fail-closed behavior for dirty tree, out-of-allowlist drift, protected body drift, and RTT seam drift.

### Concerns
- **MEDIUM:** Adding `reflector_scorer.py` to the verifier allowlist is broader than the actual implementation, since the plan says it remains byte-unchanged. Plan 04 catches phase-local drift, but the verifier itself would allow scorer edits.
- **MEDIUM:** Validators are added only to `check_config_validators.py`. If steering later accepts the same `measurement.fping.*` block, make sure Phase 242/244 covers steering-side validation.
- **LOW:** Validator warning for `timeout >= cadence_sec` may conflict with runtime behavior if Plan 01 chooses to raise rather than warn.

### Suggestions
- Prefer not allowlisting `reflector_scorer.py` unless a plan actually edits it, or add an explicit “allowed but expected unchanged” assertion into the script/evidence.
- Decide whether `timeout >= cadence` is warning-only or construction-failing, then keep validator/runtime behavior aligned.

### Risk Assessment
**MEDIUM** due to allowlist breadth; otherwise solid.

## 241-03-PLAN.md

### Summary
Good intent: replace synthetic fixtures with real fping 5.1 captures, preserve stdout/stderr/returncode metadata, and mechanically verify capture command parity.

### Strengths
- M3 is addressed in design: `--print-command` compared mechanically to `_build_command()`.
- Tests are required to feed `CompletedProcess(args, stdout, stderr, returncode)`, not bare text.
- Human checkpoint is appropriate; this cannot honestly be fully autonomous if real live-host captures are required.
- Non-mutating production-safety language is clear.

### Concerns
- **HIGH:** Bash signal return codes are likely wrong for the process-death fixture. A shell typically reports SIGTERM as `143`, not Python’s `CompletedProcess.returncode == -15`. The plan says “negative returncode,” but a bash helper must explicitly normalize `128+signal` to `-signal` or use Python `Popen` to capture the real negative returncode.
- **MEDIUM:** Real partial-loss capture is not deterministic. “Distant/lossy target” may produce 0% or 100%, and the script forbids automatic `tc/netem`. This can block the phase.
- **MEDIUM:** TEST-NET `192.0.2.1` may produce routing/ICMP errors rather than a clean `host : - - - - -` line. The helper should validate fixture shape.
- **LOW:** Fixtures may record source IPs, reflectors, and commands. Confirm this repo is allowed to carry that operational detail, or sanitize where possible.

### Suggestions
- Implement capture using a small Python helper, or normalize bash status `128+N` to `-N` in metadata.
- Make the script fail if each scenario does not match its required shape: partial loss must include both RTTs and `-` tokens for the same host; total loss must include all `-`; process death must have normalized negative returncode.
- Add a redaction policy for fixture metadata if live source IPs should not be committed.

### Risk Assessment
**HIGH** until process-death returncode and partial-loss capture reliability are fixed.

## 241-04-PLAN.md

### Summary
Strong boundary-gate plan: separates cumulative SAFE-17 changed paths from phase-local diff, fixes prior H3, and requires clean `src/wanctl` before running the verifier.

### Strengths
- H3 is fully addressed: cumulative changed paths are correctly stated as 5, not 2.
- Phase-local diff uses the Phase 240 close commit `a181ca27`, not tautological `HEAD` checks.
- Verifier checks dirty tree, disallowed paths, protected bodies, and RTT seam drift.

### Concerns
- **MEDIUM:** Evidence `head_commit == HEAD` is only true before committing the evidence file. If the evidence JSON is later committed, HEAD changes and the evidence appears stale. The plan needs explicit semantics: either evidence is uncommitted, or `head_commit` is expected to equal the parent/source commit.
- **LOW:** Full suite and hot-path slice are in the verification block, but not strongly represented in task acceptance criteria.

### Suggestions
- Define evidence freshness as `head_commit == source_commit_before_evidence_commit`, or commit evidence with a check that `HEAD^ == evidence.head_commit`.
- Add full-suite/hot-path acceptance criteria to Plan 04, not only the final verification prose.

### Risk Assessment
**MEDIUM**; boundary logic is good, evidence commit semantics need tightening.

## Prior-MEDIUM Disposition

- **M1 parser robustness:** **PARTIALLY RESOLVED.** Negative returncode, unknown host, whitespace tolerance, and `measurement_ms` are addressed. Remaining gap: action parses all non-negative returncodes, not only expected fping codes, and missing/garbled output can feed scorer failure.
- **M2 `KNOWN_AUTORATE_PATHS`:** **FULLY RESOLVED.** Plan 02 registers all fping keys and adds a zero unknown-key warning test.
- **M3 capture-vs-command / CompletedProcess tests:** **FULLY RESOLVED in plan intent.** Mechanical `--print-command` comparison and stdout/stderr/returncode fixture metadata are present. Fix the signal returncode capture detail above.

## Prior-HIGH Disposition

- **H1 all-fail scorer feed dropped:** **FULLY RESOLVED.** Plan 01 explicitly feeds scorer from `FpingParseResult.per_host_loss` before returning `None`, and Plan 01/03 require `test_all_fail_feeds_scorer`.
- **H2 stdout-only parsing misses stderr:** **FULLY RESOLVED.** Plan 01 parses combined stdout+stderr, and Plan 03 requires tests using captured split streams.
- **H3 Plan 04 cumulative changed_paths wrong:** **FULLY RESOLVED.** Plan 04 correctly distinguishes cumulative 5-path SAFE-17 diff from 2-path phase-local diff against `a181ca27`.

Overall verdict: **approve after revision**, not as-is. The prior HIGHs are fixed, but D-07 must be reconciled and the process-death capture path must produce Python-equivalent negative returncodes before execution.

---

## Consensus Summary

Single reviewer (Codex) this cycle. The revised plans (post cycle-1 replan) are a
material improvement: all three prior-cycle HIGH concerns are confirmed **FULLY
RESOLVED**, and two of three prior MEDIUMs are FULLY RESOLVED (M2, M3-intent), with
M1 PARTIALLY RESOLVED. Verdict: **approve after revision** — not blocking-broken, but
two NEW HIGH issues should be reconciled before execution.

### Agreed Strengths
- Containment: all backend logic in one new allowlisted module `fping_measurement.py`; frozen controller files untouched.
- `FpingParseResult` parse/scorer-feed seam correctly resolves H1 (all-fail still penalizes reflectors before `probe()` returns `None`).
- Combined stdout+stderr parsing resolves H2; tests required to feed real `CompletedProcess(stdout, stderr, returncode)`.
- Plan 04 correctly separates cumulative 5-path SAFE-17 diff from the 2-path phase-local diff vs `a181ca27` (resolves H3).
- `-C` (not `-c`), loss-safe `-` handling, and fping-gated scorer feed keep the icmplib path byte-unchanged.

### Agreed Concerns (highest priority)
- **NEW-HIGH (D-07 contradiction):** CONTEXT decision D-07 says "Reuse `BackgroundRTTThread`… No new scheduler thread", but Plan 01 introduces a NEW `FpingThread` and explicitly leaves `BackgroundRTTThread` unedited. The decision record and the plan disagree. Reconcile: either update D-07 with rationale (a new cloned thread keeps the icmplib `BackgroundRTTThread` byte-frozen, which is the stronger SAFE-17 posture) or follow D-07. **Recommendation: ratify the FpingThread choice and amend D-07** — cloning is the more conservative SAFE-17 move and is consistent with the byte-frozen `irtt_thread.py` posture.
- **NEW-HIGH (process-death returncode, Plan 03):** A bash capture helper reports SIGTERM as shell exit `143` (`128+15`), NOT Python's `CompletedProcess.returncode == -15`. Plan 01's process-death gate keys on a NEGATIVE returncode, so the captured fixture metadata must normalize `128+N → -N` (or capture via a Python `Popen` helper) or the `process_death` fixture will not exercise the negative-returncode gate the tests assert.

### Other Concerns Worth Folding
- **MEDIUM (return-code parse breadth, Plan 01):** Action parses any non-negative returncode; restrict parseable codes to `{0,1,2}` and treat `>2` (usage/config error) as failure with NO scorer feed.
- **MEDIUM (`_scorer_results` None→fail, Plan 01):** `loss is None` (unmeasured/garbled) currently maps to fail; an unmeasured host should not be penalized as a real loss. Add `observed_hosts` to `FpingParseResult` and feed scorer only for measured hosts, or explicitly justify/test missing-host-as-fail.
- **MEDIUM (`reflector_scorer.py` allowlist breadth, Plan 02):** the verifier allowlists `reflector_scorer.py` though it stays byte-unchanged; Plan 04 catches phase-local drift but the verifier itself would permit scorer edits. Consider an explicit "allowed-but-expected-unchanged" assertion.
- **MEDIUM (partial-loss/TEST-NET capture determinism, Plan 03):** "distant/lossy target" may yield 0% or 100%; `192.0.2.1` may emit routing/ICMP-error lines rather than a clean `host : - - - - -`. Add per-scenario shape validation so a bad capture fails loudly instead of producing a misleading fixture.
- **MEDIUM (evidence `head_commit == HEAD` semantics, Plan 04):** once the evidence JSON is committed, HEAD advances and the evidence looks stale. Define freshness as `HEAD^ == evidence.head_commit` (evidence committed as the next commit) or keep evidence uncommitted.
- **LOW:** `_build_command` resolves `self._binary_path` but invokes `"fping"`; FPING-01 marked complete here despite no live wiring (selectable-but-inert) — consider marking partially-satisfied until Phase 242; fixture metadata may carry source IPs/reflectors (confirm repo policy / sanitize).

### Divergent Views
- Single reviewer; no cross-reviewer divergence this cycle.

### Prior-Cycle HIGH Disposition (carried, for audit)
- **H1 all-fail scorer feed dropped** — FULLY RESOLVED (FpingParseResult seam + `test_all_fail_feeds_scorer`).
- **H2 stdout-only parsing misses stderr** — FULLY RESOLVED (combined-stream parse + split-stream tests).
- **H3 Plan 04 cumulative changed_paths wrong (2 vs 5)** — FULLY RESOLVED (cumulative-vs-phase-local diff distinction).
