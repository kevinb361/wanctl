---
phase: 232
reviewers: [codex]
reviewed_at: 2026-06-10T22:30:00Z
plans_reviewed: [232-01-PLAN.md, 232-02-PLAN.md, 232-03-PLAN.md]
---

# Cross-AI Plan Review — Phase 232

## Codex Review

**Summary**

The phase is well sliced and mostly execution-ready: guard first, rollback tooling second, evidence/SAFE proof last. I would not execute unchanged, though. Two issues need tightening first: Plan 02 preserves `ssh -n ... "bash -s" <script`, which can invalidate the remote payload test, and Plan 03 overclaims the digest "query errors bubble" behavior versus current code.

**232-01: Cleanup Boundary Guard**

**Strengths**
- Good first-phase boundary: BOUND-01 lands before sweep work.
- Uses existing repo patterns: bash wrapper, Python JSON evidence, git anchor.
- Synthetic scratch-repo tests cover missing file, immutable modification, allowlisted modification, and bad anchor.
- Guard is wired into default pytest, not just documented.

**Concerns**
- **MEDIUM:** The real-repo gate can skip when `.planning/cake-autorate-trials` is absent (232-01-PLAN.md:152). That weakens "default suite blocks sweep violations" outside Kevin's dev checkout.
- **MEDIUM:** Allowlisting `docs/UPGRADING.md`, `docs/DEPLOYMENT.md`, and the future doc for modification conflicts with the plan's "removed or modified" wording (232-01-PLAN.md:104). Decide whether BOUND-01 is a no-delete guard or no-touch guard.
- **LOW:** The future doc is actually ignored/untracked via .gitignore:12, so hash-based protection is impossible unless it becomes tracked.

**Suggestions**
- Rename the policy language to `must-exist` vs `must-match-anchor` so the guard's intent is explicit.
- Add one test for an anchor-absent ignored/planning-file row, since that is a real manifest case.
- Make the skip loud enough to fail in CI-like contexts unless an explicit env var allows planning-less checkouts.

**Risk Assessment:** **MEDIUM**. The guard design is solid, but policy ambiguity could either block valid docs work or silently permit more drift than BOUND-01 intends.

**232-02: Rollback Confirm Hardening**

**Strengths**
- Correctly targets the actual CR-01 failure mode: partial remote rollback masked by final command success.
- External writer post-check is the right safety check for dual-writer prevention.
- Preserves double gate and avoids live rollback.
- WR-02 negative assertions are a useful upgrade to the preflight test.

**Concerns**
- **HIGH:** The plan explicitly keeps `ssh -n ... "bash -s" <"$remote_script"` (232-02-PLAN.md:86, current code at scripts/phase231-rollback.sh:279). `ssh -n` redirects stdin from `/dev/null`; the fake ssh shim may still read stdin, so the payload test can pass while real OpenSSH sends an empty script.
- **MEDIUM:** "NOT active" only fails on exact `active`; `activating` should probably fail too for a rate-control writer.
- **LOW:** WR-02 regexes catch common mutation verbs but are narrow. They will miss some reordered systemctl forms.

**Suggestions**
- Remove `-n` for the `bash -s` execution only; keep it for read-only probe commands.
- Add a test asserting the confirm `bash -s` ssh argv does not include `-n`.
- Treat `active` and `activating` as failure for `cake-autorate-${WAN}.service`.
- Broaden read-only regexes to catch `systemctl .* (enable|disable|restart|start|stop)`.

**Risk Assessment:** **HIGH until fixed**, then **LOW-MEDIUM**. This is the one plan touching mutation-capable tooling, and the current transport detail can make the main fix unproven.

**232-03: Digest Evidence + SAFE-15**

**Strengths**
- Correctly depends on 232-01 and 232-02.
- Uses tests as primary evidence and live read-only digest as best-effort evidence.
- Todo closure is evidence-based, not silent deletion.
- SAFE-15 is run last, which is the right boundary timing.

**Concerns**
- **MEDIUM:** The plan says query errors "bubble" (232-03-PLAN.md:17), but current code catches hard-red query `DatabaseError`, logs, increments `read_skipped`, and continues (src/wanctl/operator_summary.py:238). The existing test only proves "not classified as skipped" for an all-bad case (tests/test_operator_digest.py:193).
- **MEDIUM:** Reusing `phase225-safe13-boundary-check.sh` is convenient, but it also checks `configs/att.yaml`, not only controller path (scripts/phase225-safe13-boundary-check.sh:76). It passes now, but it is semantically broader than SAFE-15.
- **LOW:** The independent `git diff` verify omits `wan_controller_state.py` even though the reused checker includes it.

**Suggestions**
- In the evidence doc, either narrow the claim to "query errors are not classified as permission skips" or add a mixed good+corrupt DB test proving the desired command-level behavior.
- Use `git diff --quiet v1.50..HEAD -- <full SAFE-15 target list>` as the independent SAFE check, including `wan_controller_state.py`.
- Note that the phase225 checker has the extra `configs/att.yaml` constraint, so a future failure there is not automatically a SAFE-15 controller violation.

**Risk Assessment:** **MEDIUM**. It likely closes FIX-02 correctly, but the evidence wording needs to stop overclaiming relative to the implementation.

**Overall Risk**

Overall risk is **MEDIUM**, dominated by the Plan 02 SSH transport issue. Fix that before execution. After that, the remaining concerns are mostly evidence precision and guard-policy clarity, not controller-path risk.

---

## Consensus Summary

Single reviewer this cycle (Codex) — consensus is the Codex verdict itself.

### Agreed Strengths
- Correct phase slicing: guard before sweep, SAFE-15 proof last, dependencies honored.
- Plan 02 targets the real CR-01 failure mode (partial remote rollback masked by final command success) with the right dual-writer post-check.
- Evidence-based todo closure; no silent deletion.

### Agreed Concerns
- **HIGH** (Plan 02): keeping `ssh -n ... "bash -s" <"$remote_script"` undermines the payload-delivery proof — `-n` redirects stdin from /dev/null in real OpenSSH while the fake shim may still read stdin, so the test can pass while production sends an empty script. Fix: drop `-n` for the `bash -s` execution only; add a test asserting the confirm-path ssh argv excludes `-n`; treat `activating` as failure alongside `active`.
- **MEDIUM** (Plan 01): guard policy ambiguity — decide `must-exist` vs `must-match-anchor` semantics per manifest row; real-repo gate skip when `.planning/cake-autorate-trials` absent weakens the default-suite block.
- **MEDIUM** (Plan 03): evidence wording overclaims "query errors bubble" vs actual `DatabaseError` catch-and-continue behavior; SAFE-15 independent check should use the full target list incl. `wan_controller_state.py` and note the phase225 checker's extra `configs/att.yaml` constraint.

### Divergent Views
None — single reviewer.

---

# Cycle 2 Re-Review (post-revision, commit 5dabadc8)

## Codex Review (Cycle 2)

**Summary**

The revisions address the cycle-1 concerns. Plan 02 now explicitly fixes the `ssh -n ... bash -s` payload bug, pins it with argv-level tests, treats `activating` as a dual-writer failure, and broadens read-only assertions. Plan 01 now has explicit per-row guard policy plus loud planning-less checkout handling. Plan 03 now matches actual `operator_summary.py` behavior and adds the missing full SAFE-15 diff list plus the `configs/att.yaml` caveat. I found no new blocking issues.

**Prior Concern Resolution**

- **HIGH, Plan 02:** RESOLVED. The revised plan drops `-n` only for the `bash -s` payload execution, keeps `-n` on probes, adds an argv test excluding `-n`, fails on `active` and `activating`, and uses broader mutation regexes. This directly targets the current defect at scripts/phase231-rollback.sh:279.
- **MEDIUM, Plan 01:** RESOLVED. The guard now distinguishes `must-match-anchor` vs `must-exist`, keeps deletion forbidden for all rows, makes planning-less checkout skips opt-in via `WANCTL_BOUND01_ALLOW_NO_PLANNING=1`, and adds an anchor-absent/untracked future-doc test.
- **MEDIUM, Plan 03:** RESOLVED. The digest wording now says query-time DB errors are caught per DB with `hard-red query failed`, not bubbled; this matches operator_summary.py:241. SAFE-15 now includes `wan_controller_state.py` and records that the reused checker also checks `configs/att.yaml` via phase225-safe13-boundary-check.sh:67.

**New Concerns**

- **LOW:** Plan 01's scratch-repo fixture description says the helper commits the full manifest tree, while the anchor-absent test needs the future doc ignored before commit. Make that fixture parameterized or use a separate fixture for the untracked-row case so the test is not accidentally impossible.
- **LOW:** Plan 01 still has some broad prose like "fails closed on touch/removal of any denylisted surface," while `must-exist` rows intentionally allow content drift. The policy table is clear, but tighten summary wording to avoid audit confusion.

**Risk Assessment**

Overall risk: **LOW**. The revised plans are conservative, test-heavy, and keep controller-path changes out of scope. Reviewer verified the digest slice locally (`9 passed`), confirmed the ShellCheck `SC2318` target exists in phase231-migration-held.sh:136, and confirmed the current SAFE diff vs `v1.50` is clean across the full controller target list.

## Convergence Verdict (Cycle 2)

- HIGH concerns remaining: **0** — converged.
- Cycle-1 HIGH (Plan 02 ssh -n) FULLY RESOLVED with reviewer sign-off above.
- Two LOW notes (Plan 01 fixture parameterization, summary prose tightening) are executor-discretion polish, not blockers.
