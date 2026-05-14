---
phase: 205
reviewers: [codex]
reviewed_at: 2026-05-14T00:00:00Z
plans_reviewed: [205-01-PLAN.md, 205-02-PLAN.md, 205-03-PLAN.md, 205-04-PLAN.md]
review_input: [205-RESEARCH.md, 205-PATTERNS.md, 205-VALIDATION.md, ROADMAP.md (Phase 205 + v1.44 closeout invariants), REQUIREMENTS.md (TOPO-01, TOPO-02), PROJECT.md (first 80 lines)]
codex_model: default (codex-cli 0.125.0)
codex_tokens: 112739
---

# Cross-AI Plan Review — Phase 205

## Codex Review

**Summary**

The plan-set is technically pointed in the right direction: TOPO-01 is a small active-tin policy fix, and TOPO-02 correctly recognizes that `allow_wash` is not real unless it reaches both backend emitters and the config allowlist. The main risk is not the implementation itself; it is plan mechanics. Several RED-gate expectations are wrong, the SAFE-09 scope amendment happens too late, and a few verification checks would falsely fail or provide weaker evidence than claimed.

**Strengths**

- The TOPO-01 implementation shape is conservative: change the active tin index set, not EWMA/classifier math.
- The four-site TOPO-02 gate is correctly identified: `cake_params.py`, `linux_cake.py`, `netlink_cake.py`, and `check_config_validators.py`.
- Keeping `EXCLUDED_PARAMS = {"nat", "wash", "autorate-ingress"}` intact preserves D-08 default-deny behavior.
- Strict `allow_wash is True` is the right default; it avoids `"false"` becoming truthy.
- The plan explicitly defers `_DIFFSERV_NAME_TO_INT["besteffort"]` and `check_cake.py` auditor drift, which avoids smuggling Phase 209 work into Phase 205.

**Concerns**

- **HIGH:** Plan 205-01's RED expectations are inaccurate. Several new tests will pass before production changes: `allow_wash_false_rejects_wash`, `allow_wash_absent_rejects_wash`, and the `nat` / `autorate_ingress` rejection tests all pass today because `cake_params.py:150` rejects excluded params unconditionally. Treat them as guard tests, not RED tests.

- **HIGH:** The SAFE-09 ROADMAP amendment is surfaced after the source changes in Plan 205-04. Since Plan 205-03 knowingly expands the allowed source set from 2 files to 5, amend or explicitly approve the SAFE-09 allowlist before Plan 205-03 lands.

- **HIGH:** Plan 205-02 has a bad acceptance check: `grep -cE 'range\(len\(tins_raw\)\)' ... returns 1`. Current valid code has at least three uses: tin snapshot construction at `cake_signal.py:251`, total drops at `cake_signal.py:308`, and steady tin snapshots at `cake_signal.py:340`. That check will falsely fail.

- **MEDIUM:** "Diffserv4 byte-identical" is claimed more strongly than it is pinned. Passing replay tests is good, but unless those tests assert exact numeric snapshots across the CAKE signal fields, it is not byte-identity proof. Add a direct 4-tin fixture equality test before/after helper semantics.

- **MEDIUM:** TOPO-02 "end-to-end" does not include readback validation. `build_expected_readback()` at `cake_params.py:176` never includes `wash`, and `_VALIDATE_KEY_TO_TCA` at `backends/netlink_cake.py:68` has no `TCA_CAKE_WASH` mapping. Emission tests catch command construction, but runtime validation would not detect a missing wash state.

- **MEDIUM:** Spectrum currently uses `overhead: "docsis"`, which causes `NetlinkCakeBackend.initialize_cake()` to fall back to `LinuxCakeBackend.initialize_cake()` at `backends/netlink_cake.py:442`. Add a test that `{"overhead_keyword": "docsis", "wash": True}` reaches the fallback unchanged.

- **MEDIUM:** Wave 2 parallelism conflicts with per-plan global diff checks. If Plans 205-02 and 205-03 run in the same worktree, Plan 205-02's "only `cake_signal.py` changed" check can fail after Plan 205-03 lands. Either serialize those checks or make them patch-local.

- **LOW:** The tin-name heuristic is scope creep unless tested. Current single-tin default would be `"Bulk"` because `_tin_names[0]` is used at `cake_signal.py:237`, not `"Tin0"`. If you keep the heuristic, use `self._tin_names`, not `self.tin_names`, and add `snap.tins[0].name == "BestEffort"`.

- **LOW:** The synthetic besteffort oracle is valid as a structural aggregation oracle, but it is not a captured replay oracle. Name it honestly, then add a real captured fixture in Phase 209 or from a dev qdisc if "captured" is a hard requirement.

**Suggestions**

- Move the SAFE-09 ROADMAP amendment to the start of Plan 205-03, or add a short Plan 205-00/205-01 planning-artifact update that approves the 5-file TOPO-02 scope before source mutation.
- Split Wave 0 tests into `RED behavior tests` and `GREEN invariant guard tests`; do not require all new tests to fail.
- Replace the bad `range(len(tins_raw)) == 1` grep with a targeted check that only `range(1, len(tins_raw))` is gone and `total_drops` still uses all tins.
- Add tests for `allow_wash: "true"` / `"false"` rejecting wash, and `allow_wash: true, wash: false` producing `params["wash"] is False`.
- Add a Spectrum-shaped netlink fallback test with `overhead_keyword: "docsis"` plus `wash`.
- Either add `wash` to readback validation or explicitly document that Phase 205 validates emission only and Phase 209 validates live qdisc state.
- Update source comments in `cake_signal.py` so "active excludes Bulk" becomes "active excludes Bulk only for multi-tin layouts."

**Risk Assessment**

**MEDIUM.** The code changes themselves are narrow and should be low runtime risk if implemented exactly: no thresholds, EWMA constants, dwell, deadband, burst logic, or rate algorithms need to move. The plan risk is medium because several verification gates are currently wrong or too weak, and the SAFE-09 scope expansion should be approved before implementation, not reconciled afterward. Fix those plan mechanics and Phase 205 becomes a reasonable surgical precursor to the riskier Phase 209 config flip.

---

## Consensus Summary

*Single reviewer (Codex) — not a true cross-AI consensus. Findings reflect Codex's read against `src/wanctl/` source at the time of review (2026-05-14).*

### Reviewer-Agreed Strengths

(N=1; no consensus surface, but the strongest individual signals are:)
- Conservative TOPO-01 shape (active-tin policy, not classifier math).
- Correct identification of the four-site TOPO-02 atomic gate.
- D-08 default-deny preservation via untouched `EXCLUDED_PARAMS`.

### Reviewer-Agreed Concerns

(Treat all HIGH + MEDIUM as actionable in a single-reviewer pass; cannot weight by consensus.)

**Must-fix before execution (HIGH):**
1. Plan 01 RED-test framing is a category error for ≥3 tests that pass today against the existing `EXCLUDED_PARAMS` check. Reframe as GREEN guard tests.
2. SAFE-09 ROADMAP amendment ordering: amendment must land *before* Plan 03's 5-file scope expansion lands, not after. Move the operator checkpoint earlier in the plan chain.
3. Plan 02 acceptance check `grep -cE 'range\(len\(tins_raw\)\)' ... returns 1` is broken — current code has ≥3 such uses. Replace with a `range(1, len(tins_raw))`-targeted check.

**Should-fix before execution (MEDIUM):**
4. Diffserv4 byte-identity needs a direct numeric-equality fixture test, not a replay-test pass.
5. TOPO-02 "end-to-end" gap: `build_expected_readback()` and `_VALIDATE_KEY_TO_TCA` don't carry `wash`. Either extend the gate or document that Phase 205 = emission-only and Phase 209 = readback.
6. Spectrum's `overhead: "docsis"` triggers a netlink→linux backend fallback; add a fallback-path test for `{overhead_keyword: docsis, wash: true}`.
7. Wave 2 parallelism + per-plan global diff checks: Plan 02's "only `cake_signal.py` changed" check breaks when run after Plan 03 in the same worktree. Make checks patch-local or serialize.

**Nice-to-fix (LOW):**
8. Tin-name heuristic uses wrong attribute (`self.tin_names` vs `self._tin_names`); single-tin default would land as `"Bulk"`, not `"Tin0"`. Test it or drop it.
9. Rename the besteffort "replay-oracle" → "structural aggregation oracle" for honesty (Q1 deliberately synthesized; not a captured replay).

### Divergent Views

N/A — single reviewer.

---

## Next Step

To incorporate this feedback into a replan:

```
/gsd-plan-phase 205 --reviews
```

The replanner will read this REVIEWS.md and revise the plan-set. Recommended priority:
1. Address all HIGH concerns first (RED-test framing, SAFE-09 amendment ordering, Plan 02 grep).
2. MEDIUM #4–7 are real but slightly more design-discussion territory; pick which ones materially affect Phase 209 confidence.
3. LOW are cleanup; address inline if cheap.

For HIGH #2 (SAFE-09 amendment ordering), consider a Plan 205-00 (pure planning-artifact: ROADMAP wording amendment) that runs before Plan 205-01, so the 5-file scope is operator-approved before any source change.

---

## Resolution Status (2026-05-14)

Replanned via `/gsd-plan-phase 205 --reviews`. Outcome:

- **HIGH-1 (RED-test framing):** Resolved — Plan 01 split into RED-behavior tests (Task 1+2: 9 tests, must fail before Plan 02/03) and GREEN-invariant guard tests (Task 3+4: 5 tests, must pass before AND after Plan 02/03 to prove no regression). Each test tagged with expected color in acceptance criteria.
- **HIGH-2 (SAFE-09 ordering):** Resolved APPROVE — operator chose approve / Option B in Plan 00 Task 1; ROADMAP amended BEFORE source mutation in Plans 02/03.
- **HIGH-3 (broken grep acceptance):** Resolved — Plan 02 acceptance criteria replaced with positive (helper exists + applied at sites), negative (no `range(1, len(tins_raw))` literal remains), and total-drops invariant (`range(len(tins_raw))` count unchanged at 308 + adjacent total sites) checks.
- **MEDIUM-4 (byte-identity not pinned):** Resolved — Plan 02 Task 2 adds 4-tin diffserv4 fixture snapshot test asserting bit-equal numeric output before AND after helper extraction.
- **MEDIUM-5 (readback validation gap):** Resolved APPROVE — operator chose approve / Option B: Phase 205 validates emission only; Phase 209 owns live qdisc readback validation.
- **MEDIUM-6 (docsis fallback uncovered):** Resolved — Plan 01 RED test for `{overhead_keyword: "docsis", wash: True}` exercises the LinuxCakeBackend fallback path (netlink_cake.py:442-447). Plan 03 turns it GREEN.
- **MEDIUM-7 (wave-2 diff race):** Resolved — Plan 02 + Plan 03 acceptance criteria use file-scoped diff checks (`git diff <commit> -- <file>`) instead of cross-cutting `--name-only`. Parallelism preserved.
- **LOW-8 (tin-name attribute):** Resolved — Plan 02 Task action uses `self._tin_names` (verified by grep at b82abf0 — Codex correct on attribute name); test added asserting `snap.tins[0].name == "BestEffort"` for single-tin path.
- **LOW-9 (oracle naming):** Resolved — RESEARCH/PATTERNS/VALIDATION + new test class names use "structural aggregation oracle" terminology; class renamed `TestCakeSignalProcessorBestEffortStructuralOracle`.

Plan-set is now 5 plans (was 4): 205-00 (operator gate), 205-01 (RED+GREEN tests), 205-02 (TOPO-01), 205-03 (TOPO-02), 205-04 (SAFE-09 audit only).
