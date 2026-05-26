---
phase: 209
reviewers: [codex]
reviewed_at: 2026-05-19T01:11:12Z
plans_reviewed:
  - 209-01-PLAN.md
  - 209-02-PLAN.md
  - 209-03-PLAN.md
  - 209-04-PLAN.md
codex_cli_version: codex-cli 0.125.0
---

# Cross-AI Plan Review — Phase 209

## Codex Review

## HIGH Concerns Found

The phase shape is good, but I would not execute Plan 209-04 as written. The canary/gate commands do not match the actual Phase 206 scripts, and Plan 209-01 misses production-relevant readback cases that can either hide a bad qdisc state or create a restart-loop risk.

## Summary

**209-01:** Good objective: keep wash validation internal, hard-fail only the new wash invariant, and avoid touching `linux_cake_adapter.py`. The gap is test realism. The plan tests wash mostly in isolation, but production Spectrum readback will include at least `diffserv=besteffort` plus `wash=true`, and current netlink diffserv normalization looks wrong for `besteffort`.

**209-02:** The single verifier entry point is the right design. Extending the existing fail-closed script is better than adding a second script. However, the plan has a sequencing contradiction: it expects the default SAFE-09 verifier to pass before the 1.44.0 version bump exists.

**209-03:** The doc split is sound. `BRIDGE_QOS.md` as the topology decision guide and `CONFIGURATION.md` as a short schema reference is the right source-of-truth model. There are minor consistency errors in the CHANGELOG acceptance gates and one false threat-model claim.

**209-04:** The Snapshot A/B semantics are mostly correct: Snapshot A before gate/reconcile, Snapshot B as evidence only, rollback from A. But the Phase 206 harness commands are not executable against the current repo, and the plan relies on a rollback gate whose own verification still records a fail-open gap.

**Phase-level:** The phase is well-scoped and the D-19 commit separation is worth keeping. No, the 209-04 closeout commit should not become six files; the script work belongs in 209-02. The phase risk remains high until the gate invocation, non-finite window gap, and full readback tests are fixed.

## Strengths

- Plan 209-01 keeps D-17 narrow: hard-fail in backend validation, adapter warning behavior preserved for non-wash mismatches.
- Plan 209-02 correctly reuses [scripts/check-safe07-source-diff.sh](/home/kevin/projects/wanctl/scripts/check-safe07-source-diff.sh:1) rather than creating verifier sprawl.
- Plan 209-03 avoids duplicating topology rationale across docs.
- Plan 209-04’s D-11/D-19 commit discipline is strong: config/version/date closeout is separate from code/verifier/docs prerequisites.
- Snapshot A is correctly defined as rollback-clean and captured before any production mutation.

## Concerns

- **HIGH — 209-04, Phase 206 commands are wrong/non-executable.**  
  [209-04-PLAN.md](/home/kevin/projects/wanctl/.planning/phases/209-spectrum-config-migration-production-canary-and-docs/209-04-PLAN.md:390) calls nonexistent `scripts/phase206-ab-replay-harness.py` with `--a-leg/--b-leg/--output`. Actual [scripts/phase206-ab-replay.py](/home/kevin/projects/wanctl/scripts/phase206-ab-replay.py:176) supports `--fixture`, `--out`, `--flent-gz-pre`, `--flent-gz-post`.  
  [209-04-PLAN.md](/home/kevin/projects/wanctl/.planning/phases/209-spectrum-config-migration-production-canary-and-docs/209-04-PLAN.md:398) uses nonexistent `--post-soak` / `--ab-comparison`; actual [phase206-predeploy-gate.sh](/home/kevin/projects/wanctl/scripts/phase206-predeploy-gate.sh:48) requires `--baseline PATH --candidate PATH` and `--mode post-soak`.

- **HIGH — 209-01, production Spectrum readback is not tested end-to-end.**  
  Current [netlink_cake.py](/home/kevin/projects/wanctl/src/wanctl/backends/netlink_cake.py:62) maps `"besteffort": 2`, but local pyroute2 declares `CAKE_DIFFSERV_BESTEFFORT = 3`. Plan tests at [209-01-PLAN.md](/home/kevin/projects/wanctl/.planning/phases/209-spectrum-config-migration-production-canary-and-docs/209-01-PLAN.md:191) only cover `expected={"wash": ...}`. That can miss a real Spectrum expected dict where `diffserv` validation soft-fails while wash passes.

- **HIGH — 209-01, netlink ATT off-by-omission can restart-loop.**  
  Linux backend gets `None -> False` normalization for wash omission, but netlink does not. See [209-01-PLAN.md](/home/kevin/projects/wanctl/.planning/phases/209-spectrum-config-migration-production-canary-and-docs/209-01-PLAN.md:259) versus netlink tests at [209-01-PLAN.md](/home/kevin/projects/wanctl/.planning/phases/209-spectrum-config-migration-production-canary-and-docs/209-01-PLAN.md:191). Since adapter validation calls [backend.validate_cake()](/home/kevin/projects/wanctl/src/wanctl/backends/linux_cake_adapter.py:342), a wash `RuntimeError` propagates and blocks startup. ATT uses `linux-cake-netlink`, so this is an ATT behavioral risk even if ATT YAML is byte-identical.

- **HIGH — Phase dependency, TOPO-05 is still blocked.**  
  Phase 206 verification still says non-finite `--window-hours` returns rc=0 instead of fail-closed rc=2: [206-VERIFICATION.md](/home/kevin/projects/wanctl/.planning/phases/206-a-b-replay-harness-rollback-gates/206-VERIFICATION.md:16), with the code gap at [phase206-gate-check.py](/home/kevin/projects/wanctl/scripts/phase206-gate-check.py:339). 209-04 treats Phase 206 gates as binding anyway.

- **MEDIUM — 209-02, verifier acceptance is impossible before 209-04.**  
  [209-02-PLAN.md](/home/kevin/projects/wanctl/.planning/phases/209-spectrum-config-migration-production-canary-and-docs/209-02-PLAN.md:341) says current mid-phase tree should pass, but [209-02-PLAN.md](/home/kevin/projects/wanctl/.planning/phases/209-spectrum-config-migration-production-canary-and-docs/209-02-PLAN.md:381) says `__init__.py` must already be `1.44.0`. That does not happen until 209-04.

- **MEDIUM — 209-03 has contradictory CHANGELOG gates.**  
  It inserts DSCP text at [209-03-PLAN.md](/home/kevin/projects/wanctl/.planning/phases/209-spectrum-config-migration-production-canary-and-docs/209-03-PLAN.md:207), then requires near-zero DSCP matches at [209-03-PLAN.md](/home/kevin/projects/wanctl/.planning/phases/209-spectrum-config-migration-production-canary-and-docs/209-03-PLAN.md:239).

- **LOW — 209-04 has execution nits.**  
  The automated grep has a mangled `^**version**` pattern at [209-04-PLAN.md](/home/kevin/projects/wanctl/.planning/phases/209-spectrum-config-migration-production-canary-and-docs/209-04-PLAN.md:207), and Task 1 says “stages” without a `git add`, then Task 4a assumes staged files.

## Suggestions

- In 209-01, add full readback tests for actual production-shaped expected dicts:
  - Spectrum netlink: `{"diffserv": "besteffort", "wash": True}` with `TCA_CAKE_DIFFSERV_MODE=3`, `TCA_CAKE_WASH=1`.
  - ATT netlink: `{"diffserv": "diffserv4", "wash": False}` with `TCA_CAKE_WASH=None` accepted as false.
  - Linux JSON equivalents, including omitted wash=false.
- Fix `_DIFFSERV_NAME_TO_INT["besteffort"]` before relying on netlink readback.
- Verify `TCA_CAKE_WASH` via `sched_cake.options.nla_map`, not `dir(sched_cake)`.
- Add a small prerequisite plan to close TOPO-05: `math.isfinite(args.window_hours)` plus `nan`/`inf` wrapper tests.
- Rewrite 209-04 Task 3 against real CLIs. If zone × cause-tag comparison is required, use or extend `soak_summary_aggregate.py`; `phase206-ab-replay.py` does not consume arbitrary A/B soak NDJSON.
- Move 209-02 live-repo default-mode rc=0 checks to 209-04 after the version bump, or make them tmp-repo-only in 209-02.
- Keep 209-04 closeout at exactly five files. Do not bundle the verifier script into it.

## Risk Assessment

**Overall phase risk: HIGH right now.** The implementation scope is reasonable, but the deployment verification path is not currently executable as written, and one known fail-open rollback-gate issue remains unresolved. After fixing the Phase 206 invocation shape, finite-window validation, and production-shaped wash/diffserv readback tests, this drops to **MEDIUM**, mostly because any hard-fail at controller startup is inherently risky on a 24/7 network controller.

---

## Consensus Summary

*Only one reviewer (codex) ran in this pass. No multi-reviewer consensus to synthesize. Re-run with `/gsd-review 209 --gemini --claude` for adversarial confirmation.*

### Top Concerns (single-reviewer signal — treat as high-confidence)

1. **HIGH — 209-04 Phase 206 invocation is non-executable.** Calls `scripts/phase206-ab-replay-harness.py --a-leg/--b-leg/--output` and `--post-soak/--ab-comparison` that don't exist. Actual scripts: `phase206-ab-replay.py` (`--fixture/--out/--flent-gz-pre/--flent-gz-post`) and `phase206-predeploy-gate.sh` (`--baseline PATH --candidate PATH --mode post-soak`). 209-04 Task 3 needs full rewrite against real CLIs — possibly using `soak_summary_aggregate.py` for zone × cause-tag comparison since `phase206-ab-replay.py` does not consume arbitrary A/B soak NDJSON.

2. **HIGH — 209-01 ATT-side netlink wash readback can restart-loop the controller in production.** Linux backend has `None → False` normalization for omitted wash key, but netlink backend does not. ATT runs `linux-cake-netlink`. If kernel omits wash field in netlink readback (likely on older iproute2/kernel), `expected=False` vs `actual=None` mismatches → RuntimeError → systemd restart loop on the WAN we're explicitly NOT trying to touch (SAFE-08 ATT-untouched invariant). The normalization MUST land in netlink backend too, symmetric with linux backend.

3. **HIGH — 209-01 production Spectrum readback not tested end-to-end + diffserv constant bug.** `_DIFFSERV_NAME_TO_INT["besteffort"]: 2` in `netlink_cake.py:62` does not match pyroute2's `CAKE_DIFFSERV_BESTEFFORT = 3`. Plan tests only cover `expected={"wash": ...}` in isolation — production Spectrum readback will be `{"diffserv": "besteffort", "wash": True}`. Need to (a) fix `_DIFFSERV_NAME_TO_INT["besteffort"]: 3`, (b) add full production-shaped readback tests for both Spectrum (`{"diffserv": "besteffort", "wash": True}` with `TCA_CAKE_DIFFSERV_MODE=3, TCA_CAKE_WASH=1`) and ATT (`{"diffserv": "diffserv4", "wash": False}` with `TCA_CAKE_WASH=None`).

4. **HIGH — TOPO-05 cross-phase blocker still open.** Phase 206 verification `206-VERIFICATION.md:16` records that non-finite `--window-hours` returns rc=0 instead of fail-closed rc=2 (gap at `phase206-gate-check.py:339`). 209-04 treats Phase 206 rollback gates as binding comparator. Either close TOPO-05 inside Phase 209 (small prerequisite plan: `math.isfinite(args.window_hours)` + nan/inf wrapper tests) or document the fail-open risk and accept it for the canary.

5. **MEDIUM — 209-02 verifier acceptance sequencing.** Plan says default-mode test should pass mid-phase, but also requires `__init__.py == 1.44.0` which doesn't happen until 209-04 closeout. Either move the live-repo default-mode rc=0 checks into 209-04 Task 4b, or make 209-02's default-mode tests tmp-repo-only with synthesized refs.

6. **MEDIUM — 209-03 CHANGELOG gates contradict each other.** Plan inserts DSCP text at line 207 then requires near-zero DSCP matches at line 239 (D-16 "no inline DSCP-rationale").

7. **LOW — 209-04 execution nits.** Mangled `^**version**` grep pattern at line 207. Task 1 says "stages" without an explicit `git add` step that Task 4a then assumes.

### Strengths Confirmed by Reviewer

- D-17 placement (wash hard-fail in backends, adapter untouched) — narrow and correct
- D-19 commit separation — 209-04 closeout at 5 files (not 6) is the right call
- Snapshot A pre-mutation capture semantics
- Single-verifier extension over verifier sprawl in 209-02
- Doc split between BRIDGE_QOS.md and CONFIGURATION.md

### Overall Risk per Codex

**HIGH right now**; drops to MEDIUM after fixing the Phase 206 invocation shape, the TOPO-05 finite-window gap, the netlink wash normalization symmetry, and the diffserv besteffort constant + production-shaped readback tests.
