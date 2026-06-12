---
phase: 233
reviewers: [codex]
reviewed_at: 2026-06-11T18:47:09Z
plans_reviewed: [233-01-PLAN.md, 233-02-PLAN.md, 233-03-PLAN.md, 233-04-PLAN.md]
---

# Cross-AI Plan Review — Phase 233

## Codex Review

## Summary

The Phase 233 plan set is directionally sound: it keeps controller code out of scope, uses the Phase 232 boundary guard, avoids new `$wan` abstractions, and puts human gates in front of the destructive and behavior-sensitive parts. The main gaps are evidence hygiene and proof strength. I spot-checked the repo: `.planning/` is ignored while many existing planning files are force-tracked, `scripts/check-cleanup-boundary.sh` defaults to a Phase 232 evidence path, the Spectrum bridge unit really does rely on script defaults, and the doc `wanctl@` hits are real. Fix those mechanics before execution.

## Cross-Plan Concerns

- **MEDIUM:** New `.planning/phases/233-.../evidence/*.json` and `*-SUMMARY.md` files are ignored by `.gitignore`, so normal `git add` will not commit them. Plans should explicitly use `git add -f` for new planning artifacts.
- **MEDIUM:** Several tasks run `bash scripts/check-cleanup-boundary.sh` without `--out`; the script’s default output path is Phase 232 evidence. Use `/tmp/...` for throwaway guard runs or a Phase 233 evidence path every time.
- **MEDIUM:** Wave 1 is described as parallel, but the plans share phase evidence/summary space. If executed concurrently, use distinct evidence filenames per plan or serialize evidence commits.

## 233-01 — SWEEP-01 Trial Cleanup

### Strengths

- Correctly separates deletion safety from the boundary guard; the guard cannot see ignored trial files.
- Uses a blocking human checkpoint for destructive `rm`.
- Preserves `WANCTL_CAKE_AUTORATE_FUTURE.md` and findings markdown by default.
- Good threat model for accidental deletion.

### Concerns

- **MEDIUM:** The removal set is underspecified. The plan says `run_*`, `parse_flent_summary.py`, and “timestamped result dirs,” but the directory also contains non-timestamped result-like dirs such as `att`, `periodic`, and named experiment dirs. Decide explicitly what happens to those.
- **MEDIUM:** Task 3 says “commit only the new evidence JSON,” but the plan also requires a summary. Both are new ignored files and need force-add if they are meant to be durable.
- **LOW:** The automated verification samples only a few names; acceptance says every removed file must have zero tracked refs.
- **LOW:** `git grep` should use fixed-string matching to avoid regex surprises from dots or other characters.

### Suggestions

- Generate a removal manifest before deletion and include it in `233-01-SUMMARY.md`.
- Use `git grep -F -l -- "$basename" -- ':!.planning/cake-autorate-trials'`.
- Add post-checks: no `run_*` files remain, keep-list files still exist, and any remaining top-level dirs are intentionally retained.
- Explicitly `git add -f` the summary/evidence artifacts.

### Risk Assessment

**LOW-MEDIUM.** The repo risk is low because files are untracked and referenced nowhere tracked, but the operation is destructive and currently has ambiguous directory scope.

## 233-02 — SWEEP-02 Doc Disambiguation

### Strengths

- Correct default posture: annotate native examples instead of deleting them.
- Clear handling for the three obvious docs: `PROFILING`, `PERFORMANCE`, `RUNBOOK`.
- Human decision point for docs where historical/by-design meaning matters.
- Keeps denylisted native docs out of scope.

### Concerns

- **MEDIUM:** `grep -ciE 'cake-autorate|external mode' >= 1` proves only that a note exists somewhere. It does not prove no stale native-ownership claim remains.
- **MEDIUM:** The “native-unit example counts are not reduced” criterion needs a captured pre-edit baseline, otherwise it is not reproducible.
- **MEDIUM:** `annotate-none` may be too weak for `docs/STEERING.md`; the current stop/start examples look operational, not purely historical.
- **LOW:** Guard calls without `--out` will write the Phase 232 default evidence path.

### Suggestions

- After edits, produce a table of every remaining `wanctl@` hit with disposition: native-mode example, historical note, by-design bypass reference, or covered by nearby external-mode note.
- Capture before/after `wanctl@` counts or assert via diff that no removed lines contain `wanctl@`.
- Prefer annotating `STEERING.md` unless inspection proves those commands are historical-only.
- Use phase-specific guard output or `/tmp` for non-evidence guard runs.

### Risk Assessment

**MEDIUM.** The edit risk is low, but the plan can falsely close SWEEP-02 with a weak grep proof.

## 233-03 — SWEEP-03 Spectrum Unit Explicit Env

### Strengths

- Minimal, correct scope: mirror ATT’s explicit env block rather than creating a new template or shared script.
- Preserves unit name, `ExecStart`, health host/port, and bridge scripts.
- Human checkpoint for the baseline RTT pin is appropriate.
- Correctly states repo edit does not apply live until redeploy.

### Concerns

- **MEDIUM:** `systemd-analyze verify` currently fails locally because `/usr/local/sbin/cake-autorate-spectrum-state-bridge` is not present. The fallback is mentioned, but the plan should make the fallback criteria explicit.
- **LOW:** Guard runs need explicit `--out`.
- **LOW:** “Sets WANCTL_EXTERNAL_* env explicitly” should be precise: it sets identity/path/baseline env, not every possible bridge env like poll interval or max state age.
- **LOW:** If the operator provides a different baseline than the script default, the “behavior-preserving” claim no longer holds and should be recorded as intentional drift.

### Suggestions

- Add a structural verification command that checks all expected `Environment=` keys and confirms `ExecStart` is unchanged.
- Treat `systemd-analyze verify` failure due only to missing installed `ExecStart` as acceptable; fail on parse/unit syntax errors.
- If baseline differs from current live/default value, split that into a separate operator-approved behavior change.

### Risk Assessment

**LOW** if baseline is confirmed as the current live/default value. **MEDIUM** if a new baseline is pinned during this hygiene phase.

## 233-04 — SAFE-15 Boundary Closeout

### Strengths

- Correctly runs full suite, BOUND-01, SAFE checker, and independent `git diff --quiet`.
- Good phase-boundary purpose: prove SAFE-15 after the sweep, not per-plan assumptions.
- Uses the established `v1.50` anchor and controller path list.

### Concerns

- **MEDIUM:** The action rewrites `cleanup-boundary-233.json` but says to commit only `safe15-boundary-233.json`. Either commit both final evidence files or write cleanup evidence to `/tmp`.
- **MEDIUM:** The verify block again runs the boundary guard without `--out`, mutating the Phase 232 default evidence file.
- **MEDIUM:** New SAFE evidence and summary are ignored unless force-added.
- **LOW:** “SUMMARYs exist” is weaker than “SUMMARYs are committed/tracked” if planning durability matters.

### Suggestions

- Emit `cleanup-boundary-233-final.json` and `safe15-boundary-233.json`, then `git add -f` both plus `233-04-SUMMARY.md`.
- Add `git status --short` and cached-file checks before commit to ensure only expected evidence/summary files are staged.
- Keep the full suite gate; it is appropriate for the phase boundary.

### Risk Assessment

**LOW-MEDIUM.** The validation coverage is strong; the risk is mainly bookkeeping that could leave evidence uncommitted or dirty.

## Overall Risk

**MEDIUM before tweaks, LOW-MEDIUM after tweaks.** The actual code/runtime blast radius is small: docs, ignored trial artifacts, and one deploy unit. The phase can achieve its goals, but tighten ignored-file commits, guard output paths, SWEEP-02 residual proof, and final evidence handling before execution.

---

## Consensus Summary

Single external reviewer (Codex) this cycle — consensus reflects one independent reviewer's repo-verified findings (Codex spot-checked the live repo: `.gitignore` behavior, guard default output path, Spectrum unit, and doc `wanctl@` hits).

### Agreed Strengths

- Scope discipline: controller code stays out of scope, BOUND-01 boundary guard gates every plan, no new `$wan` abstraction is introduced for SWEEP-03.
- Human gates sit in front of the destructive (`rm` in 233-01) and behavior-sensitive (BASELINE_RTT pin in 233-03) steps.
- 233-04 closeout proof set is strong: full suite + BOUND-01 + SAFE checker + independent `git diff --quiet` vs v1.50.

### Agreed Concerns

No HIGH-severity concerns raised. Top recurring MEDIUM concerns (cross-plan):

1. **Ignored evidence files** — `.planning/phases/233-*/evidence/*.json` and `*-SUMMARY.md` are gitignored; plans must `git add -f` new planning artifacts or evidence silently goes uncommitted (affects 233-01, 233-04, and cross-plan).
2. **Guard output path collisions** — `scripts/check-cleanup-boundary.sh` without `--out` writes to the Phase 232 default evidence path; every Phase 233 guard run needs an explicit `--out` (phase-specific path or `/tmp`).
3. **Weak SWEEP-02 residual proof** — `grep -ciE 'cake-autorate|external mode' >= 1` proves a note exists, not that no stale native-ownership claim remains; needs a per-hit disposition table and pre/post `wanctl@` counts.
4. **233-01 removal set underspecified** — non-timestamped result-like dirs (`att`, `periodic`, named experiment dirs) need an explicit keep/remove decision; generate a removal manifest before deletion.
5. **Wave 1 parallel evidence collisions** — plans share phase evidence/summary space; use distinct evidence filenames per plan or serialize evidence commits.

### Divergent Views

Single reviewer — no divergence to report. Notable conditional finding: 233-03 risk is LOW only if the operator-confirmed BASELINE_RTT matches the current live/default value; pinning a *new* baseline during a hygiene phase should be split into a separate operator-approved behavior change (would shift 233-03 to MEDIUM).
