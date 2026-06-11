---
created: 2026-04-18T02:11:13.000Z
title: operator-summary --digest should handle PermissionError gracefully
area: tooling
resolves_phase: 232
files:
  - src/wanctl/operator_summary.py
closed_by_phase: 232
verdict: validated_already_implemented_v144_phase208_tool03
---

## Problem

`wanctl-operator-summary --digest` (added in commit e6d85da) currently errors out with `[Errno 13] Permission denied: '/var/lib/wanctl/metrics.db'` when run as a user that cannot read the DBs. The metrics DBs are owned by `wanctl:wanctl` with mode 0640; `kevin` user can't read them without sudo.

Practical impact: the operator has to either `sudo wanctl-operator-summary --digest` (which changes env) or fix group membership. The CLI should just skip unreadable DBs with a clear message.

## Solution

In `print_digest()` in `src/wanctl/operator_summary.py`:
- Wrap the `sqlite3.connect(db_path)` call in try/except catching `sqlite3.OperationalError` and `PermissionError`
- Emit a single line per unreadable DB: `<wan_name>: cannot read DB (try sudo)` and continue to the next
- If no DBs readable at all, exit 0 with the message "no readable WAN DBs — try sudo"

Small test addition in `tests/test_operator_digest.py`: mock `sqlite3.connect` raising `PermissionError` on one path, assert the next path is still queried and output contains the skip message.

## Resolution

**Closed by Phase 232 Plan 03 (FIX-02).** The proposed behavior was implemented in stricter, test-pinned form by v1.44 Phase 208 Plan 208-03 (T12/TOOL-03), so Phase 232 validated and closed the todo instead of reimplementing it.

Evidence: `.planning/phases/232-cleanup-boundary-guard-tooling-fixes/evidence/fix02-digest-validation.md` maps each T12/TOOL-03 tolerance truth to the current pinning tests in `tests/test_operator_digest.py` and records a fresh green run.

The stderr message text intentionally differs from this todo's draft wording. Phase 208 established stable `operator-summary digest:` prefixes with `wan=`/`db=` context, plus distinct discovery, write, and hard-red query failure paths; those stable messages supersede the original sketch of `<wan_name>: cannot read DB (try sudo)`.
