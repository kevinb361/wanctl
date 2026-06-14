---
phase: 238
reviewers: [codex]
reviewed_at: 2026-06-14T17:43:19Z
plans_reviewed: [238-01-PLAN.md, 238-02-PLAN.md, 238-03-PLAN.md]
cycles:
  - cycle: 1
    reviewers: [codex]
    unresolved_high: 6
  - cycle: 2
    reviewers: [codex]
    unresolved_high: 2
---

# Cross-AI Plan Review — Phase 238

> Cross-AI peer review of the Phase 238 read-only entry-gate plans. Claude was skipped
> for independence (this review ran inside Claude Code); Codex is the external reviewer.
> Phase 238 is a READ-ONLY entry gate: zero source changes, zero production mutation.
> The locked decisions D-01..D-09 (238-CONTEXT.md) were out of scope for the review —
> reviewers were instructed to flag plan execution/rigor/safety risks, not the decisions.

## Codex Review

**Summary**

The plans are directionally sound and respect the locked Phase 238 framing: no controller code, no prod mutation, evidence-first, and operator-gated live reads. The main weakness is not intent; it is enforcement. Several "read-only" and "evidence complete" claims are stronger than the automated gates actually prove. Treat this as executable after tightening the script guardrails, final SAFE-17 ordering, and markdown evidence checks.

### 238-01 Plan (SAFE-17 lightweight boundary check)

**Strengths**
- Good scoped SAFE-17 implementation: local git inspection only, no source edits, no full verifier creep.
- Reuses the prior SAFE target list and keeps D-09 lightweight.
- JSON evidence record is useful and reproducible.

**Concerns**
- **HIGH:** `--out` is an arbitrary write path. The script claims it does not modify worktree/controller source, but it writes JSON and could be run as `--out src/wanctl/...`, overwriting controller code.
- **HIGH:** Boundary evidence can become stale. Plan 01 runs before Plan 02/03, but later plans are not required to rerun it as a final phase gate.
- **MEDIUM:** `--anchor` is passed into git as a raw argument. It avoids shell injection, but not git option/revision ambiguity. Resolve it to a commit SHA first.
- **MEDIUM:** The verify gate does not prove the controller target list byte-matches phase237; it only greps for one target.
- **LOW:** The read-only banner is inaccurate as written because the script intentionally creates an evidence file.

**Suggestions**
- Restrict `--out` to the phase evidence dir, or remove `--out` entirely for this phase.
- Resolve anchor with `git rev-parse --verify --end-of-options "$ANCHOR^{commit}"` and use the SHA.
- Add an automated exact list comparison against the phase237 target list.
- Add a final "rerun SAFE-17 after all Phase 238 artifacts are complete" gate.

**Risk Assessment:** MEDIUM. Conceptually right, but the arbitrary output path and stale evidence problem need fixing.

### 238-02 Plan (both-WAN egress proof)

**Strengths**
- Correctly focuses on `ip route get` / `ip rule`, which are the right read-only primitives.
- Handles Spectrum's no-source-IP case explicitly with `<none>`.
- Keeps live execution operator-gated and avoids credential escalation.

**Concerns**
- **HIGH:** The plan says exit 0 iff egress matches the intended WAN, but it never defines the expected interface/path/table values. That leaves the core pass/fail logic underspecified.
- **HIGH:** The automated mutation guard is too weak. It only rejects a few `ip route/rule` mutators and would not catch accidental inherited `sudo`, `systemctl`, `tc qdisc change`, redirects, `tee`, `nft`, etc.
- **MEDIUM:** Run location is ambiguous. The script SSHes to `kevin@10.10.110.223`, but the human step says run it "on the live host."
- **MEDIUM:** Output schema is not specified, yet Plan 03 depends on embedding and interpreting it.
- **LOW:** Automated verify does not include `git status --porcelain -- src/wanctl/`.

**Suggestions**
- Add expected route criteria to `TARGETS`, e.g. expected dev/table/gateway regex, or explicitly compare Spectrum to current default route and ATT to the source-bound ATT table/path.
- Add a denylist/allowlist static check for remote commands; ideally only allow `ip route get ...` and `ip rule`.
- Define JSON fields: command, stdout, parsed dev/src/via/table, pass, error, ip_rule_context.
- Clarify whether the script runs from the dev repo over SSH or locally on cake-shaper.
- Add a `--print-commands` mode for the operator fallback.

**Risk Assessment:** MEDIUM-HIGH. The production commands are intended to be read-only, but the plan does not yet prove the script stays within that boundary or can make a deterministic verdict.

### 238-03 Plan (provenance map artifact)

**Strengths**
- Covers the required evidence set: live `/health`, code-path trace, bridge identity, egress proof, and A/B recommendation.
- Correctly leaves operator ratification as a separate binding step.
- Keeps internal operational details in phase-dir evidence only.

**Concerns**
- **HIGH:** The automated verification is mostly grep-based. It could pass with placeholder text and no real two-WAN health capture, no real sha reconciliation, or no embedded egress stdout.
- **MEDIUM:** It allows transcribing source citations from research without requiring a fresh source check. For a provenance artifact, stale citations are a real quality risk.
- **MEDIUM:** The ratification slot is human-checked only; there is no mechanical check that the final artifact contains an actual A/B selection after Task 3.
- **LOW:** Live capture provenance should include command, host, timestamp, and whether output was from prod vs repo.

**Suggestions**
- Add checks for both WAN labels, two parseable fenced JSON health blocks, `raw_rtt_ms` in each, four 64-hex shas, match/mismatch text, embedded `ip rule`, and no `TODO`/`CAPTURE_PENDING`.
- Require executor to re-open the cited source lines before writing the map.
- After operator ratification, grep for a concrete `Selection: A` or `Selection: B` field.
- Include the final SAFE-17 JSON result or link it from the map.

**Risk Assessment:** MEDIUM. Low mutation risk, but high false-completion risk unless evidence checks are tightened.

### Cross-Plan Notes

- **HIGH:** Dependency ordering does not match the stated foundation. Make `238-02` depend on `238-01`, and `238-03` depend on both. Then rerun SAFE-17 at the very end.
- **MEDIUM:** `files_modified` metadata omits summary files and later ratification edits. If enforcement is strict, list all expected phase-dir outputs.
- **MEDIUM:** The phase succeeds only if human-provided evidence is captured verbatim. Add explicit "no placeholder evidence" checks.

**Overall risk:** MEDIUM. The plan set is well-scoped and mostly safe by intent, but should not execute unchanged. The must-fix items are: constrain `--out`, define egress pass/fail criteria, harden mutation static checks, and make the final SAFE-17 rerun a blocking gate.

---

## Consensus Summary

Only one external reviewer (Codex) was invoked (Claude self-skipped for independence), so "consensus" reflects Codex's findings as the single external signal. The throughline is enforcement-vs-claim gap: the plans are correctly scoped and safe by intent, but the automated verify gates are weaker than the read-only / evidence-complete guarantees they assert.

### Agreed Strengths
- Read-only primitives are the right ones (`git diff --numstat` / `status --porcelain`; `ip route get` / `ip rule`).
- Live, privileged reads are operator-gated with no credential escalation.
- Evidence-first, both-interpretations-honest A/B with a separate binding ratification step.

### Agreed Concerns (highest priority)
- **HIGH — 238-01 unconstrained `--out`:** arbitrary write path could target `src/wanctl/...`, breaking the read-only guarantee the script asserts. Constrain `--out` to the evidence dir (or drop it).
- **HIGH — SAFE-17 staleness / no final rerun gate:** Plan 01 runs first but nothing re-runs it after Plans 02/03 land. Add a blocking end-of-phase SAFE-17 rerun.
- **HIGH — 238-02 egress pass/fail undefined:** "exit 0 iff egress matches intended WAN" with no expected dev/table/path values means the verdict is underspecified.
- **HIGH — 238-02 weak mutation guard:** the static check only blocks a few `ip route/rule` mutators; misses `sudo`/`systemctl`/`tc ... change`/`tee`/`nft`/redirects. Tighten to an allowlist of remote commands.
- **HIGH — 238-03 grep-only verification / false-completion risk:** acceptance greps could pass on placeholder text with no real two-WAN health capture, sha reconciliation, or embedded egress stdout. Add structural evidence checks (parseable JSON blocks, 4x 64-hex shas, no `TODO`/`CAPTURE_PENDING`).
- **HIGH — Cross-plan dependency ordering:** declare `238-02` depends on `238-01` and `238-03` depends on both, then rerun SAFE-17 at the very end.

### Divergent Views
None — single external reviewer this cycle.

### Disposition Note
All six HIGH findings are plan-rigor / enforcement-hardening items on read-only deliverables, not production-mutation defects that have occurred. They are unresolved as of this review cycle and should be addressed via `/gsd:plan-phase 238 --reviews` (tighten verify gates, constrain `--out`, define egress criteria, harden mutation static checks, add structural evidence checks, fix declared dependency ordering + final SAFE-17 rerun).

---

# Cross-AI Plan RE-REVIEW — Phase 238 — Cycle 2 (2026-06-14T18:09:09Z)

> Re-review after the Phase 238 plans were revised to address the 6 cycle-1 HIGH concerns
> (unconstrained `--out`, no final SAFE-17 rerun gate, undefined egress pass/fail criteria,
> weak mutation guard, grep-only/placeholder false-completion risk, cross-plan dependency
> ordering). Claude was skipped for independence (review ran inside Claude Code); Codex
> (gpt-5.5, xhigh reasoning) is the external reviewer. Locked decisions D-01..D-09 were
> out of scope — only plan execution/rigor/safety risks were in scope.

## Codex Review (Cycle 2)

**Summary**  
The revisions materially tighten Phase 238. The `--out` boundary, final SAFE-17 rerun, Plan dependencies, and provenance-map structural checks are mostly fixed. Two prior HIGHs remain only **PARTIALLY RESOLVED** because the automated guarantees still fall short of the claimed guarantees: 238-02 still does not mechanically prove ATT egress is the ATT uplink, and its mutation guard is still grep/denylist-based rather than a true remote-command allowlist.

**Prior-HIGH Adjudication**

1. **238-01 unconstrained `--out` write path — RESOLVED**  
   Plan 01 now requires: “`--out` path is constrained to the phase evidence dir… any `--out` outside it… is refused with exit 2 BEFORE any file is created or written,” plus a concrete negative test: `--out src/wanctl/__should_not_write.json` must fail and not create the file. This is a concrete script-level guard with an automated verification path.

2. **SAFE-17 staleness / no final gate — RESOLVED**  
   Plan 03 now depends on both prior plans and adds Task 4: “This is the FINAL gate of Phase 238… after ALL other Phase 238 artifacts are in place… re-run `scripts/phase238-safe17-boundary-check.sh`.” The verify asserts `passed:true` and empty `git status --porcelain -- src/wanctl/`.

3. **238-02 egress pass/fail undefined — PARTIAL**  
   The plan now defines concrete expected source observables: “Spectrum src `10.10.110.223`, ATT src `10.10.110.227`,” and adds `--self-test` fixtures including an ATT wrong-src negative case. That resolves the “undefined” part. Remaining gap: the plan still relies on human confirmation that “the resolved `dev` is the ATT uplink”; the automated exit-0 logic is source-IP plus distinctness, not an encoded expected ATT dev/table/gateway. So the claimed “egresses intended WAN” guarantee is not fully mechanical.

4. **238-02 weak mutation guard — PARTIAL**  
   The revision says the script issues “ONLY `ip route get` and `ip rule` as remote commands” and adds grep checks for `sudo`, `systemctl`, `tc`, `tee`, `nft`, and common `ip` mutators. This is much stronger. But the automated guard is still mostly denylist grepping, not a parser/enumerator that proves every SSH command is exactly `ip route get …` or `ip rule`; it would miss other mutators or redirections not in the denylist.

5. **238-03 grep-only verification / placeholder false-completion — RESOLVED**  
   Plan 03 now requires structural checks: at least two parseable fenced JSON blocks with `raw_rtt_ms`, four unique 64-hex SHAs, embedded `ip rule` and `ip route get`, both WAN labels, and no `TODO|CAPTURE_PENDING|FIXME|XXX|<paste`. That is no longer grep-only placeholder acceptance.

6. **Cross-plan dependency ordering — RESOLVED**  
   Plan 02 declares `depends_on: ["238-01"]`; Plan 03 declares `depends_on: ["238-01", "238-02"]`; Plan 03 Task 4 reruns SAFE-17 last. This directly fixes the ordering concern.

**New Concerns**

- **MEDIUM — Final provenance-map structure is not rechecked after operator ratification.**  
  Task 2 performs the strong structural map verification before Task 3. Task 3 then edits the map and only verifies `Selection: A|B`; Task 4 reruns SAFE-17 but does not rerun the provenance-map structural checks. Add a post-ratification map verification before or alongside the final SAFE-17 rerun.

- **MEDIUM — 238-02 run location remains somewhat ambiguous.**  
  The plan says the operator runs `scripts/phase238-egress-proof.sh --json` “on the live cake-shaper host,” but the script structure SSHes to `kevin@10.10.110.223`. Pick one canonical mode: run from dev over SSH, or run locally on cake-shaper without SSH.

**Per-Plan Notes**

**238-01**  
Strong fix. The `--out` guard, anchor resolution with `rev-parse --verify --end-of-options`, and negative write test address the prior HIGH cleanly. Remaining non-high issue: the “byte-identical target list” claim is still stronger than grep-for-each-target unless the implementation compares the exact list/order.

**238-02**  
The expected-src criteria and self-test are a real improvement. Remaining concern is guarantee mismatch: source-IP matching is automated, but ATT-uplink identity is still human-confirmed. The mutation guard should become a true static allowlist over generated SSH commands, not only denylist greps.

**238-03**  
The evidence checks are much better: parseable JSON, SHA structure, no placeholders, egress output, and final SAFE-17 rerun. Add one final structural provenance-map verification after the `Selection:` edit.

**Final Tally**

HIGH concerns that remain unresolved or partially resolved:

- **238-02 egress pass/fail criteria — PARTIAL:** expected source values are automated, but intended ATT uplink/dev is not mechanically enforced.
- **238-02 mutation guard — PARTIAL:** improved denylist plus allowlist intent, but no automated proof that every remote command is exactly `ip route get` or `ip rule`.

No newly introduced HIGH concerns.

**Risk Assessment**  
**MEDIUM.** The read-only phase shape is now mostly sound, and the worst Phase 238 boundary issues are fixed. The remaining risk is concentrated in 238-02’s automated proof strength: it can still overclaim egress correctness and read-only enforcement unless the script encodes exact remote-command and ATT-uplink expectations.

---

## Cycle 2 Disposition

**Prior 6 HIGHs:** 4 FULLY RESOLVED (238-01 `--out` guard, final SAFE-17 rerun gate,
238-03 structural evidence checks, cross-plan dependency ordering), 2 PARTIALLY RESOLVED
(both in 238-02).

**Unresolved HIGH count this cycle: 2** (both PARTIAL, both in 238-02):
- **238-02 egress pass/fail (PARTIAL):** expected per-WAN `src` observables (Spectrum
  10.10.110.223 / ATT 10.10.110.227) and a negative self-test fixture are now automated,
  but the ATT *uplink dev* identity is still operator-confirmed, not mechanically encoded.
  The "egresses the intended WAN" guarantee is therefore not fully mechanical.
- **238-02 mutation guard (PARTIAL):** hardened from a few mutators to a broad
  denylist (sudo/systemctl/tc-change/tee/nft/ip-mutators/redirects) plus stated allowlist
  intent, but the automated check is still denylist-grep, not a parser proving every
  generated SSH command is exactly `ip route get …` or `ip rule`.

**New HIGHs introduced this cycle:** none. Two new MEDIUMs (no post-ratification
provenance-map structural recheck; 238-02 run-location dev-over-SSH vs local ambiguity).

**Recommendation:** Both remaining HIGHs are PARTIAL plan-rigor items confined to 238-02
on a read-only deliverable (no production-mutation defect). Tighten 238-02 via
`/gsd:plan-phase 238 --reviews`: (a) encode the expected ATT uplink `dev` as a per-WAN
`verdict_for_line` criterion (add an ATT-correct-src-wrong-dev negative self-test fixture),
and (b) convert the mutation guard to an allowlist that asserts every generated remote
command matches exactly `^ip route get ` or `^ip rule$`.
