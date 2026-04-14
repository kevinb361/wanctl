---
phase: 183
slug: dashboard-history-contract-audit
status: approved
nyquist_compliant: true
wave_0_complete: true
created: 2026-04-14
---

# Phase 183 — Validation Strategy

> Reconstructed Nyquist validation contract for a completed docs-only phase.
> Phase 183 changed only planning artifacts, so validation is artifact- and
> history-based rather than implementation-test-based.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | shell / grep / git history audit |
| **Config file** | `pyproject.toml` |
| **Quick run command** | `bash .planning/phases/183-dashboard-history-contract-audit/validate-183-quick.sh` |
| **Full suite command** | `bash .planning/phases/183-dashboard-history-contract-audit/validate-183-full.sh` |
| **Estimated runtime** | ~5 seconds |

### Command Expansion

`validate-183-quick.sh` is represented by these commands:

```bash
grep -c "health_check.py:" .planning/phases/183-dashboard-history-contract-audit/183-dashboard-ambiguity-audit.md | awk '{ exit ($1 >= 5 ? 0 : 1) }'
grep -c "history_browser.py:" .planning/phases/183-dashboard-history-contract-audit/183-dashboard-ambiguity-audit.md | awk '{ exit ($1 >= 5 ? 0 : 1) }'
bash -c 'F=.planning/phases/183-dashboard-history-contract-audit/183-dashboard-ambiguity-audit.md; grep -q "## Ambiguity Points" "$F" && grep -q "## Degraded And Failure Behavior Today" "$F" && grep -q "## Operator Doc Wording Alignment" "$F" && grep -q "## Handoff To 183-02" "$F" && [ $(grep -cE "D-0[1-9]|D-1[0-4]" "$F") -ge 5 ]'
```

`validate-183-full.sh` is represented by these commands:

```bash
bash -c 'F=.planning/phases/183-dashboard-history-contract-audit/183-dashboard-source-contract.md; grep -q "## Scope And Non-Goals" "$F" && grep -q "## Labeling Requirements" "$F" && grep -q "## Source Metadata Requirements" "$F" && grep -q "metadata.source.mode" "$F" && grep -q "metadata.source.db_paths" "$F" && grep -q "local_configured_db" "$F" && grep -q "D-01" "$F" && grep -q "D-02" "$F" && grep -q "D-03" "$F" && grep -q "D-04" "$F" && grep -q "D-05" "$F" && grep -q "D-06" "$F" && grep -q "D-14" "$F"'
bash -c 'F=.planning/phases/183-dashboard-history-contract-audit/183-dashboard-source-contract.md; grep -q "## Operator Handoff Requirements" "$F" && grep -q "## Degraded And Failure Requirements" "$F" && grep -q "D-07" "$F" && grep -q "D-08" "$F" && grep -q "D-09" "$F" && grep -q "D-10" "$F" && grep -q "D-11" "$F" && grep -q "D-12" "$F" && grep -qE "wanctl\.history|wanctl-history" "$F"'
bash -c 'F=.planning/phases/183-dashboard-history-contract-audit/183-dashboard-source-contract.md; set -e; grep -q "## Acceptance Criteria" "$F"; grep -q "## Traceability" "$F"; grep -q "## Out Of Scope" "$F"; for id in D-01 D-02 D-03 D-04 D-05 D-06 D-07 D-08 D-09 D-10 D-11 D-12 D-13 D-14; do grep -q "$id" "$F" || exit 1; done; for id in DASH-01 DASH-02 DASH-03 DASH-04 OPER-05; do grep -q "$id" "$F" || exit 1; done; N=$(grep -cE "^[[:space:]]*[0-9]+\." "$F"); [ "$N" -ge 10 ]'
git diff --name-only b37b424^..c13af6d -- src/ tests/ docs/ deploy/ scripts/ CLAUDE.md | grep -q . && exit 1 || exit 0
```

The final `git diff` line is a historical-safe replacement for the original
clean-worktree checks in the plan. The current repo has unrelated later edits in
`src/` and `tests/`, so validation uses the actual Phase 183 commit range to
preserve the intended invariant: Phase 183 itself did not modify implementation
or operator-facing runtime files.

## Sampling Rate

- **After every task commit:** Run `validate-183-quick.sh`
- **After every plan wave:** Run `validate-183-full.sh`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 5 seconds

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 183-01-01 | 01 | 1 | N/A — enables `DASH-01`..`OPER-05` | — | Audit artifact cites the real `/metrics/history` envelope and source fields without inventing new ones | artifact-grep | `grep -c "health_check.py:" .planning/phases/183-dashboard-history-contract-audit/183-dashboard-ambiguity-audit.md | awk '{ exit ($1 >= 5 ? 0 : 1) }'` | ✅ | ✅ green |
| 183-01-02 | 01 | 1 | N/A — enables `DASH-01`..`OPER-05` | — | Audit artifact cites the real widget behavior and current operator-visible surface | artifact-grep | `grep -c "history_browser.py:" .planning/phases/183-dashboard-history-contract-audit/183-dashboard-ambiguity-audit.md | awk '{ exit ($1 >= 5 ? 0 : 1) }'` | ✅ | ✅ green |
| 183-01-03 | 01 | 1 | N/A — enables `DASH-01`..`OPER-05` | — | Audit artifact enumerates ambiguity, degraded behavior, doc alignment, and handoff sections | artifact-grep | `bash -c 'F=.planning/phases/183-dashboard-history-contract-audit/183-dashboard-ambiguity-audit.md; grep -q "## Ambiguity Points" "$F" && grep -q "## Degraded And Failure Behavior Today" "$F" && grep -q "## Operator Doc Wording Alignment" "$F" && grep -q "## Handoff To 183-02" "$F" && [ $(grep -cE "D-0[1-9]|D-1[0-4]" "$F") -ge 5 ]'` | ✅ | ✅ green |
| 183-02-01 | 02 | 2 | N/A — enables `DASH-01`..`OPER-05` | — | Contract file locks scope, labeling, and source metadata requirements with correct field names and decision traceability | artifact-grep | `bash -c 'F=.planning/phases/183-dashboard-history-contract-audit/183-dashboard-source-contract.md; grep -q "## Scope And Non-Goals" "$F" && grep -q "## Labeling Requirements" "$F" && grep -q "## Source Metadata Requirements" "$F" && grep -q "metadata.source.mode" "$F" && grep -q "metadata.source.db_paths" "$F" && grep -q "local_configured_db" "$F" && grep -q "D-01" "$F" && grep -q "D-02" "$F" && grep -q "D-03" "$F" && grep -q "D-04" "$F" && grep -q "D-05" "$F" && grep -q "D-06" "$F" && grep -q "D-14" "$F"'` | ✅ | ✅ green |
| 183-02-02 | 02 | 2 | N/A — enables `DASH-01`..`OPER-05` | — | Contract file locks canonical CLI handoff and degraded/failure requirements without reopening backend semantics | artifact-grep | `bash -c 'F=.planning/phases/183-dashboard-history-contract-audit/183-dashboard-source-contract.md; grep -q "## Operator Handoff Requirements" "$F" && grep -q "## Degraded And Failure Requirements" "$F" && grep -q "D-07" "$F" && grep -q "D-08" "$F" && grep -q "D-09" "$F" && grep -q "D-10" "$F" && grep -q "D-11" "$F" && grep -q "D-12" "$F" && grep -qE "wanctl\.history|wanctl-history" "$F"'` | ✅ | ✅ green |
| 183-02-03 | 02 | 2 | N/A — enables `DASH-01`..`OPER-05` | — | Contract file contains acceptance criteria, traceability, out-of-scope closure, and Phase 183 remains docs-only in the actual commit range | artifact-grep + git-history | `bash -c 'F=.planning/phases/183-dashboard-history-contract-audit/183-dashboard-source-contract.md; set -e; grep -q "## Acceptance Criteria" "$F"; grep -q "## Traceability" "$F"; grep -q "## Out Of Scope" "$F"; for id in D-01 D-02 D-03 D-04 D-05 D-06 D-07 D-08 D-09 D-10 D-11 D-12 D-13 D-14; do grep -q "$id" "$F" || exit 1; done; for id in DASH-01 DASH-02 DASH-03 DASH-04 OPER-05; do grep -q "$id" "$F" || exit 1; done; N=$(grep -cE "^[[:space:]]*[0-9]+\." "$F"); [ "$N" -ge 10 ]' && git diff --name-only b37b424^..c13af6d -- src/ tests/ docs/ deploy/ scripts/ CLAUDE.md | grep -q . && exit 1 || exit 0` | ✅ | ✅ green |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

## Wave 0 Requirements

Existing infrastructure covers all phase requirements.

## Manual-Only Verifications

All phase behaviors have automated verification.

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 5s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved 2026-04-14
