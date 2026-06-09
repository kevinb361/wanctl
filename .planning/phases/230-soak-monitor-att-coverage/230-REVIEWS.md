---
phase: 230
reviewers: [codex]
reviewed_at: 2026-06-09T21:31:15Z
plans_reviewed: [230-01-PLAN.md, 230-02-PLAN.md]
---

# Cross-AI Plan Review — Phase 230

## Codex Review

## 230-01 Plan Review

**Summary**  
Strong, well-scoped implementation plan. It targets the actual blind spot in [scripts/soak-monitor.sh](/home/kevin/projects/wanctl/scripts/soak-monitor.sh:327): ATT still falls through to `wanctl@att.service` while Spectrum gets cake-autorate handling. The scope guardrails are good: bash + tests only, no controller path, no ATT health rewrite. Main weakness is test depth: the proposed tests prove literals/helpers exist, but not that `--json` and aggregate output actually use the right units.

**Strengths**
- Correctly identifies all four current hardcoded paths: per-WAN JSON/table and aggregate JSON/table.
- Keeps native `wanctl@${wan}.service` fallback, which preserves rollback usefulness.
- Includes the ATT-only silicom watchdog, avoiding false symmetry.
- Avoids risky production mutation and avoids unnecessary ATT health fallback work.
- Shellcheck gate is appropriate and cheap.

**Concerns**
- **MEDIUM:** Static substring tests can pass while aggregate behavior is still wrong. A helper can exist without `--json` emitting the correct unit list.
- **MEDIUM:** `check_errors "$ssh_target" $(external_units_for "$wan_name")` works for current unit names, but intentionally relies on word splitting and suppressing ShellCheck. Safer to convert helper output into an array and call `check_errors "$ssh_target" "${units[@]}"`.
- **LOW:** Repeated `is_external_cake_mode` SSH probes add latency in `--watch`. Probably fine for 60s cadence, but avoidable.
- **LOW:** The predicate treats “cake active + wanctl active” as non-external, so a conflict state would scan native only. Existing Spectrum behavior does this too, but it is weaker observability.

**Suggestions**
- Add one behavior test with a fake `ssh` in `PATH` that runs `scripts/soak-monitor.sh --json` and asserts the aggregate `units` list contains the three ATT units and excludes `wanctl@att.service` when fake systemctl reports ATT cake active/native inactive.
- Prefer:
  ```bash
  read -r -a units <<< "$(external_units_for "$wan_name")"
  errors=$(check_errors "$ssh_target" "${units[@]}")
  ```
  over command substitution word splitting.
- Consider a tiny `mode_units_for "$ssh_target" "$wan"` helper so per-WAN and aggregate paths cannot drift.
- If cheap, treat conflict mode as “scan both cake and wanctl units” or at least document that the native fallback is deliberate.

**Risk Assessment**  
**LOW-MEDIUM.** The implementation surface is small and observability-only, but bash JSON/manual array handling plus weak static tests leave room for a green test suite with broken runtime output.

## 230-02 Plan Review

**Summary**  
The intent is right: field evidence plus SAFE-14 boundary proof. The read-only discipline is good. However, there are two material problems: the evidence plan may not satisfy the roadmap’s “representative error condition” wording if it only records a unit-list contrast, and the SAFE-14 “only files changed since baseline” check is currently wrong because `87980bdf` predates Phase 229 script/test changes.

**Strengths**
- Keeps live validation read-only: no fault injection, no systemd mutation.
- Separates MON-01 evidence from SAFE-14 proof cleanly.
- Uses the established protected controller-path set, including `wan_controller_state.py`.
- Correctly keeps `87980bdf` as a valid controller-path zero-diff baseline.

**Concerns**
- **HIGH:** `git diff --stat 87980bdf -- scripts/ tests/` will not show only Phase 230 files. Today it already shows Phase 229 changes: `scripts/deploy.sh`, `scripts/phase229-att-artifact-diff.sh`, and `tests/test_att_cake_autorate_artifacts.py`. Use a separate Phase 230 start ref for in-scope file accounting.
- **MEDIUM:** `git show 230-01~1:scripts/soak-monitor.sh` is brittle unless `230-01` is guaranteed to be a real git ref. Prefer `git show 87980bdf:scripts/soak-monitor.sh` or pin `PHASE230_START`.
- **MEDIUM:** Unit-list contrast proves targeting, but not necessarily “surfaces an injected/representative ATT-unit error condition.” If no live ATT errors exist, the criterion needs either an approved wording change or a local/fake-ssh representative run.
- **LOW:** If `--json` falls back to native because SSH/systemctl mode detection fails, the evidence becomes inconclusive. Record the mode-detection inputs too.

**Suggestions**
- Use two baselines:
  - `SAFE_BASE=87980bdf` for controller-path zero-diff.
  - `PHASE230_START=<commit before 230-01>` for “only Phase 230 files changed.”
- Add a read-only mode-status capture:
  `systemctl is-active cake-autorate-att.service cake-autorate-att-state-bridge.service silicom-bypass-watchdog-cake-autorate-att.service wanctl@att.service`
- If live journals have no ATT errors, satisfy criterion 3 with a local fake-ssh run that simulates one ATT unit error and proves post-fix soak-monitor reports it while the pre-fix scan path would not.
- Record Plan 01 verification outputs in the evidence or summary: shellcheck, focused pytest, and full pytest result.

**Risk Assessment**  
**MEDIUM.** SAFE-14 itself is low risk, but the current scripts/tests diff check will fail against the chosen baseline, and the evidence strategy may undershoot the roadmap criterion unless tightened.

---

## Consensus Summary

Single external reviewer this cycle (Codex); consensus reflects that one review plus
local verification of its load-bearing claims.

### Agreed Strengths

- Plan 01 targets the real blind spot: all four Spectrum-hardcoded call sites in
  `scripts/soak-monitor.sh` (per-WAN JSON/table, aggregate JSON/table), with ATT-only
  silicom watchdog handling and native `wanctl@${wan}.service` fallback preserved.
- Scope guardrails are sound: bash + tests only, observability-only surface, no
  controller-path changes, no production mutation; read-only live evidence in Plan 02.
- SAFE-14 discipline carried correctly: protected controller-path file set matches
  the SAFE-07..13 precedent and `87980bdf` is a valid controller-path zero-diff baseline.

### Agreed Concerns

- **HIGH (verified locally):** Plan 02's "only Phase 230 files changed since baseline"
  check using `git diff --stat 87980bdf -- scripts/ tests/` is wrong — that diff already
  contains Phase 229 changes (`scripts/deploy.sh`, `scripts/phase229-att-artifact-diff.sh`,
  `tests/test_att_cake_autorate_artifacts.py`). Fix: split baselines — keep
  `SAFE_BASE=87980bdf` for the controller-path zero-diff proof, add a pinned
  `PHASE230_START` ref (commit immediately before 230-01 lands) for in-scope file
  accounting.
- **MEDIUM:** Criterion 3 wording risk — a unit-list contrast proves targeting, not that
  a "representative ATT-unit error condition" is surfaced. If live ATT journals are clean,
  either tighten the criterion wording (operator-approved) or add a local fake-ssh run
  simulating one ATT unit error that the pre-fix scan would have missed.
- **MEDIUM:** Plan 01 test depth — static substring/helper-existence tests can pass while
  `--json`/aggregate output is still wrong. Add at least one behavior test with a fake
  `ssh` shim asserting the aggregate `units` list includes the three ATT units and
  excludes `wanctl@att.service` when ATT is in external mode.
- **MEDIUM:** `git show 230-01~1:...` in Plan 02 is brittle unless `230-01` is a real git
  ref; prefer the pinned `PHASE230_START` (or `87980bdf:scripts/soak-monitor.sh`).
- **MEDIUM:** Word-splitting `$(external_units_for "$wan_name")` into `check_errors` args
  works for current unit names but is fragile; prefer `read -r -a units <<<` and pass
  `"${units[@]}"`.

### Divergent Views

- None — single reviewer. Local verification confirmed the HIGH finding rather than
  contradicting it.
