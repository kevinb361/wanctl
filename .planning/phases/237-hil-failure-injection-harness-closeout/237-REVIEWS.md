---
phase: 237
reviewers: [codex]
reviewed_at: 2026-06-12T23:31:20Z
review_cycle: 2
plans_reviewed: [237-01-PLAN.md, 237-02-PLAN.md, 237-03-PLAN.md, 237-04-PLAN.md]
prior_cycle_high_count: 4
current_cycle_high_count: 0
---

# Cross-AI Plan Review — Phase 237 (Cycle 2)

> Reviewer environment: executed from Claude Code CLI (claude self-skipped for independence); Codex invoked as the external reviewer.
> Cycle 2: plans were revised in direct response to the cycle-1 review. This cycle verifies whether the four prior HIGH concerns are resolved and surfaces any remaining/new HIGHs.

## Codex Review (Cycle 2)

### Prior-HIGH Disposition

| Concern | Disposition | Evidence |
|---|---|---|
| 1. (237-02) Signal-trap correctness | **RESOLVED** | 237-02 now requires separate handlers: `on_exit()` preserves rc with `return "$rc"`, while `on_signal()` restores, disables EXIT, and `exit 130` / `exit 143`. 237-01 pins this with `test_restore_on_signal`, asserting signal-derived termination, not just restore calls. |
| 2. (237-02) Live/fake gate separation underspecified | **RESOLVED** | 237-01 defines fake-mode vs live-mode and adds RED tests for real-path refusal without `SILICOM_TEST_LIVE_CONFIRM` and att refusal without `SILICOM_TEST_ATT_CONFIRM`. 237-02 implements the boundary via `realpath "$SILICOM_BYPASS"` compared to `/usr/local/sbin/silicom-bypass`. |
| 3. (237-02 + 237-03) Capture-helper deploy gap | **RESOLVED** | 237-03 now installs `phase213-steering-snapshot.sh` and `phase213-health-poller.sh` to `/usr/local/libexec/wanctl/`, matching the harness defaults; extends artifact-ownership tests and docs to cover both helpers, so deployed harness capture no longer depends on repo CWD. |
| 4. (237-04) `dirty_tree_clean` semantics overstated | **RESOLVED** | 237-04 repeatedly clarifies `dirty_tree_clean` covers only protected controller paths + `configs/att.yaml`, not the whole worktree; adds a separate `git status --short` snapshot requirement and instructs not to conflate it with the SAFE JSON fields. |

### New or Remaining HIGH Concerns

No remaining HIGH concerns from the revised plan text.

Caveat: this is plan-level resolution. The HIGHs are resolved because the revised plans now specify concrete behavior PLUS tests or acceptance checks that would catch regressions.

### Residual MEDIUM/LOW

- **MEDIUM:** Live-mode detection only treats the canonical `/usr/local/sbin/silicom-bypass` as live. A copied real CLI at another path could be classified fake-mode. The revised text says "real custom paths must not accidentally bypass live gating," but the implementation rule still gates only canonical realpath. Safer default: fake exemption should require an explicit test-only marker or tmp-path allowlist, not merely "not canonical."
- **LOW:** `trap ... RETURN` in 237-03 is shell-function-specific and easy to get wrong with quoting over SSH. The plan allows "equivalent function-scoped cleanup," which is fine, but implementation should be reviewed carefully.
- **LOW:** The signal-test expectation says `proc.returncode == -15` "i.e. 143," but a shell script that *catches* TERM and `exit 143` reports `143`, not `-15` (`-15` is only for an *uncaught* signal). The plan includes both forms elsewhere; the test should accept the actual intended shell behavior (143 from the trap-then-exit path).
- **LOW:** `grep -rEL ... >/dev/null` in 237-02 verification looks inverted for "no scheduling tokens"; `grep -rE ...` returning nonzero is the usual assertion. Acceptance text is clearer than the command.

### Overall Risk

**MEDIUM:** the prior HIGH plan gaps are closed, but the live/fake gate still has a meaningful edge case around non-canonical real `SILICOM_BYPASS` paths.

---

## Consensus Summary

Single external reviewer (Codex) this cycle. All four cycle-1 HIGH concerns are dispositioned **RESOLVED** against the revised plan text, each backed by a concrete must_have truth / action / acceptance criterion plus a regression-catching test or check:

1. **Signal-trap correctness** — separate `on_exit()` (rc-preserving `return`) and `on_signal()` (restore → `trap - EXIT` → `exit 130/143`) handlers, both registered before first mutation; proven by `test_restore_on_signal` asserting a signal-derived EXIT.
2. **Live/fake gate** — concrete `realpath` comparison to the canonical installed CLI; RED tests `test_live_gate_refuses_real_path` + `test_att_requires_louder_gate` pin real-path refusal without the gates.
3. **Capture-helper deploy gap** — `deploy_silicom_bypass` now installs both `phase213-*` helpers to `/usr/local/libexec/wanctl/` (the harness's absolute defaults), with artifact-ownership tests and dry-run coverage.
4. **`dirty_tree_clean` semantics** — 237-04 scopes the field to protected paths + `configs/att.yaml` and adds a separate `git status --short` worktree snapshot, explicitly distinct from the SAFE JSON fields.

The cycle-1 MEDIUMs were also folded in: poller-PID lifecycle (`HEALTH_POLLER_PIDS` + `stop_pollers` before restore), ATT louder gate named and tested (`SILICOM_TEST_ATT_CONFIRM`), HARN-05 `result.json` fixed-schema key set defined and asserted, per-wave `git diff --exit-code v1.51..HEAD -- src/wanctl configs/att.yaml` SAFE-16 drift check on every plan, trap-cleaned `remote_tmp` in deploy, corrected `att-modem` grep, SAFE JSON `notes` SAFE-13→SAFE-16, and `237-04-SUMMARY.md` listed in `files_modified`.

### Agreed Strengths
- TDD discipline: RED tests (237-01) pin the full HARN-01..05 + signal-EXIT + gate-refusal contract before the orchestrator exists; 237-02 turns them GREEN.
- Safety-critical trap design now correct: signal restores THEN exits with signal-derived code; cannot let the script continue.
- DEPLOY-03 closes the runtime-dependency gap — deployed harness can capture state outside repo CWD.
- SAFE-16 is no longer detected-only-at-boundary: per-wave protected-path diff checks catch drift early; close-time evidence + separate worktree snapshot avoid overclaim.

### Agreed Concerns (highest priority)
- **MEDIUM (live/fake gate edge case):** classifying live-mode solely by canonical-realpath equality means a *real* `silicom-bypass` copied to a non-canonical path would be treated as fake-mode (exempt from live-confirm). Consider an explicit fake marker / tmp-path allowlist rather than "not canonical = fake." This is the one item keeping overall risk at MEDIUM rather than LOW. Not a blocker; worth tightening during execution.

### Divergent Views
None — single reviewer this cycle.

### Recommended pre/early-execution tightening (non-blocking)
- Tighten fake-mode determination to a positive test-only marker or tmp-path allowlist (closes the non-canonical-real-CLI edge case).
- Make the signal-test assertion accept the trap-then-exit shell code (`143`) rather than only the uncaught-signal Popen form (`-15`); a handler that exits 143 will report 143.
- Review the `trap ... RETURN` SSH-quoting cleanup in 237-03 carefully at implementation time.
- Sanity-check the 237-02 "no scheduling" grep direction (`grep -rE` returning nonzero is the usual fail-closed assertion; the acceptance prose is correct).

---

## Cycle History (retrospective)

| Cycle | Reviewer | HIGH count | Disposition |
|---|---|---|---|
| 1 | codex | 4 | Signal-trap; live/fake gate; capture-helper deploy gap; `dirty_tree_clean` overclaim |
| 2 | codex | 0 | All four cycle-1 HIGHs RESOLVED; no new HIGH; one MEDIUM (live/fake gate edge case) + 3 LOW remain |
